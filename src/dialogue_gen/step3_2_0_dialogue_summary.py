"""把一段对话总结成这一段的摘要。JSONL 保留全部历史，给模型的提示词只用最新 10 条。"""

from pathlib import Path

from pydantic import Field

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt.dialogue.step_3_2_dialogue_summary import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)
from .step3_0_0_dialogue_generate import DialogueModel, SpokenTurn
from ..utils import load_data, save_data


LATEST_SUMMARY_COUNT = 10


class SummarizedSession(DialogueModel):
    """模型返回的这一段对话摘要。"""

    session_summary: str


class DialogueSummaryEntry(DialogueModel):
    """一条已经落盘的对话摘要。对外拼成「时间：对话摘要」。"""

    session_time: str
    summary: str


class DialogueSummaries(DialogueModel):
    """按会话时间保存全部对话摘要。拼进提示词时只用最新 10 条。"""

    summaries: list[DialogueSummaryEntry] = Field(default_factory=list)

    def add(self, session_time: str, summary: str) -> DialogueSummaryEntry:
        """记下这一段。同一天的摘要会替换，更早的历史都保留。"""
        session_time = session_time.strip()
        summary = summary.strip()
        if not session_time:
            raise ValueError("session_time 不能为空")
        if not summary:
            raise ValueError("对话摘要不能为空")
        self.summaries = [
            item for item in self.summaries if item.session_time != session_time
        ]
        entry = DialogueSummaryEntry(session_time=session_time, summary=summary)
        self.summaries.append(entry)
        self.summaries.sort(key=lambda item: item.session_time)
        return entry

    @classmethod
    def load(cls, save_path: str | Path) -> "DialogueSummaries":
        """读取摘要文件。文件还不存在时返回空集合。每行是一条摘要。"""
        path = cls.summary_file(save_path)
        if not path.exists():
            return cls()
        records = load_data(path)
        if not isinstance(records, list):
            raise ValueError(f"摘要文件必须是 JSONL：{path}")
        return cls(summaries=[DialogueSummaryEntry.model_validate(item) for item in records])

    def save(self, save_path: str | Path) -> Path:
        """把当前集合写成 JSONL，保留全部历史摘要。每行一条。"""
        path = self.summary_file(save_path)
        self.summaries = sorted(self.summaries, key=lambda item: item.session_time)
        save_data(path, [item.model_dump(mode="json") for item in self.summaries])
        return path

    @classmethod
    def latest(cls, save_path: str | Path) -> str:
        """给模型提示词用：只返回最新 10 条，每条是「时间：对话摘要」。"""
        return cls.load(save_path).render()

    def render(self) -> str:
        """把最新 10 条拼成多行文本。没有摘要时为空字符串。"""
        entries = self._latest_entries()
        if not entries:
            return ""
        return "\n".join(f"{item.session_time}：{item.summary}" for item in entries)

    def _latest_entries(self) -> list[DialogueSummaryEntry]:
        ordered = sorted(self.summaries, key=lambda item: item.session_time)
        return ordered[-LATEST_SUMMARY_COUNT:]

    @staticmethod
    def summary_file(save_path: str | Path) -> Path:
        """摘要文件必须是 jsonl 路径。"""
        path = Path(save_path)
        if path.suffix.lower() != ".jsonl":
            raise ValueError("save_path 必须是 jsonl 文件路径")
        return path


class DialogueSummarizer:
    """根据本段发言写出这一段的摘要，并立刻写入滚动摘要文件。"""

    def __init__(
        self,
        llm_client: LLMClient,
        turns: list[SpokenTurn],
        session_time: str,
        save_path: str | Path,
    ) -> None:
        self.llm_client = llm_client
        self.turns = turns
        self.session_time = session_time.strip()
        self.save_path = DialogueSummaries.summary_file(save_path)
        if not self.turns:
            raise ValueError("没有对话，无法总结")
        if not self.session_time:
            raise ValueError("session_time 不能为空")

    def summarize(self) -> str:
        """写出这一段摘要，写入 JSONL，并返回「时间：对话摘要」。"""
        summary = self._summarize_turns().session_summary.strip()
        stored = DialogueSummaries.load(self.save_path)
        stored.add(self.session_time, summary)
        stored.save(self.save_path)
        return f"{self.session_time}：{summary}"

    def _summarize_turns(self) -> SummarizedSession:
        messages = [
            ChatMessage.system(SUMMARY_SYSTEM_PROMPT),
            ChatMessage.user(self._user_prompt()),
        ]
        return self._chat_validated(messages, self._validate_draft)

    def _user_prompt(self) -> str:
        material = {
            "session_time": self.session_time,
            "turns": [
                {
                    "turn_id": turn.turn_id,
                    "speaker": turn.speaker,
                    "content": turn.content,
                }
                for turn in self.turns
            ],
        }
        return build_summary_user_prompt(material)

    def _chat_validated(self, messages: list[ChatMessage], validate) -> SummarizedSession:
        conversation = list(messages)
        last_error: ValueError | None = None
        for _ in range(3):
            parsed = self.llm_client.chat_json(conversation, SummarizedSession)
            try:
                validate(parsed)
                return parsed
            except ValueError as error:
                last_error = error
                conversation = [
                    *conversation,
                    ChatMessage.assistant(parsed.model_dump_json()),
                    ChatMessage.user(f"校验未通过：{error}。请重新输出完整结果。"),
                ]
        raise ValueError(str(last_error))

    def _validate_draft(self, draft: SummarizedSession) -> None:
        if not draft.session_summary.strip():
            raise ValueError("这一段的对话摘要不能为空")
