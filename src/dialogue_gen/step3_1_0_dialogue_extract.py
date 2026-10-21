"""从一段对话的发言里提取 fact、event、evidence，并按会话追加到 JSONL。"""

import json
from pathlib import Path

from pydantic import Field

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt.dialogue.step_3_1_dialogue_extract import (
    EXTRACT_SYSTEM_PROMPT,
    build_extract_user_prompt,
)
from .step2_0_0_time_event_graph import GoalState
from .step3_0_0_dialogue_generate import DialogueModel, SpokenTurn


class ExtractedEvidenceDraft(DialogueModel):
    """模型指出哪一句实现了哪一次变化，并抽出那句原话。"""

    turn_id: str
    subject: str
    gt_memory: str


class ExtractedContent(DialogueModel):
    """模型从一段对话里返回的事实、事件，以及每次变化对应的发言。"""

    fact: list[str] = Field(default_factory=list)
    event: list[str] = Field(default_factory=list)
    evidence: list[ExtractedEvidenceDraft] = Field(default_factory=list)


class ExtractedEvidence(DialogueModel):
    """一次状态变化的证据。gt_memory 由模型从对话中抽出，goal_state 由代码填入。"""

    turn_id: str
    gt_memory: str
    goal_state: GoalState


class ExtractedDialogue(DialogueModel):
    """一段对话的提取结果。会话编号和时间由调用方写入，不交给模型生成。"""

    session_id: str
    session_time: str
    fact: list[str] = Field(default_factory=list)
    event: list[str] = Field(default_factory=list)
    evidence: list[ExtractedEvidence] = Field(default_factory=list)


class DialogueExtractor:
    """只要有对话发言，就可以提取 fact、event、evidence，并追加保存。"""

    def __init__(
        self,
        llm_client: LLMClient,
        turns: list[SpokenTurn],
        session_id: str,
        session_time: str,
        goal_states: list[GoalState],
        save_path: str | Path,
    ) -> None:
        self.llm_client = llm_client
        self.turns = turns
        self.session_id = session_id.strip()
        self.session_time = session_time.strip()
        self.goal_states = goal_states
        self.save_path = self.extract_file(save_path)
        if not self.turns:
            raise ValueError("没有对话，无法提取")
        if not self.session_id:
            raise ValueError("session_id 不能为空")
        if not self.session_time:
            raise ValueError("session_time 不能为空")

    def extract(self) -> ExtractedDialogue:
        """提取这一段，并往 JSONL 追加一行。同一 session_id 已存在时替换那一行。"""
        extracted = self._extract_turns()
        record = ExtractedDialogue(
            session_id=self.session_id,
            session_time=self.session_time,
            fact=[item.strip() for item in extracted.fact],
            event=[item.strip() for item in extracted.event],
            evidence=self._build_evidence(extracted.evidence),
        )
        self.append(self.save_path, record)
        return record

    @classmethod
    def append(cls, save_path: str | Path, record: ExtractedDialogue) -> Path:
        """完成一段会话后追加一行。同一个 session_id 只保留最新一行。"""
        path = cls.extract_file(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        kept: list[str] = []
        replaced = False
        if path.exists():
            for raw in path.read_text(encoding="utf-8").splitlines():
                if not raw.strip():
                    continue
                item = json.loads(raw)
                if item.get("session_id") == record.session_id:
                    kept.append(line)
                    replaced = True
                else:
                    kept.append(raw)
        if not replaced:
            kept.append(line)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def extract_file(save_path: str | Path) -> Path:
        """提取文件必须是 jsonl 路径。"""
        path = Path(save_path)
        if path.suffix.lower() != ".jsonl":
            raise ValueError("save_path 必须是 jsonl 文件路径")
        return path

    def _extract_turns(self) -> ExtractedContent:
        messages = [
            ChatMessage.system(EXTRACT_SYSTEM_PROMPT),
            ChatMessage.user(self._user_prompt()),
        ]
        return self._chat_validated(messages, self._validate_draft)

    def _user_prompt(self) -> str:
        material = {
            "turns": [
                {
                    "turn_id": turn.turn_id,
                    "speaker": turn.speaker,
                    "content": turn.content,
                }
                for turn in self.turns
            ],
            "goal_states": [
                {"subject": state.subject, "change": state.change}
                for state in self.goal_states
            ],
        }
        return build_extract_user_prompt(material)

    def _chat_validated(self, messages: list[ChatMessage], validate) -> ExtractedContent:
        conversation = list(messages)
        last_error: ValueError | None = None
        for _ in range(3):
            parsed = self.llm_client.chat_json(conversation, ExtractedContent)
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

    def _validate_draft(self, draft: ExtractedContent) -> None:
        if not draft.fact and not draft.event:
            raise ValueError("fact 和 event 不能都是空的")
        if any(not item.strip() for item in draft.fact):
            raise ValueError("提取出的事实不能是空字符串")
        if any(not item.strip() for item in draft.event):
            raise ValueError("提取出的事件不能是空字符串")
        spoken = {turn.turn_id: turn.content for turn in self.turns}
        expected = [state.subject for state in self.goal_states]
        found = [item.subject.strip() for item in draft.evidence]
        if sorted(found) != sorted(expected):
            raise ValueError("证据必须覆盖每一次状态变化，且不能多出未给出的状态")
        for item in draft.evidence:
            turn_id = item.turn_id.strip()
            memory = item.gt_memory.strip()
            if not turn_id:
                raise ValueError("证据编号不能是空字符串")
            if turn_id not in spoken:
                raise ValueError(f"证据指向了这段对话里没有的发言：{item.turn_id}")
            if not memory:
                raise ValueError("gt_memory 不能是空字符串")
            if memory not in spoken[turn_id]:
                raise ValueError("gt_memory 必须是该句发言中的原话")

    def _build_evidence(self, drafts: list[ExtractedEvidenceDraft]) -> list[ExtractedEvidence]:
        """按 subject 把模型指出的发言配上对应的目标状态。"""
        remaining = list(drafts)
        evidence: list[ExtractedEvidence] = []
        for state in self.goal_states:
            match = next(
                (item for item in remaining if item.subject.strip() == state.subject),
                None,
            )
            if match is None:
                raise ValueError(f"没有找到这个状态变化的证据：{state.subject}")
            remaining.remove(match)
            evidence.append(
                ExtractedEvidence(
                    turn_id=match.turn_id.strip(),
                    gt_memory=match.gt_memory.strip(),
                    goal_state=state.model_copy(deep=True),
                )
            )
        return evidence
