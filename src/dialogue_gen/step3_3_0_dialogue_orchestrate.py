"""按一个事件编排一段对话。多段对话收进同一个对象后再写成 JSON。"""

from datetime import timedelta
from pathlib import Path

from pydantic import Field

from ...llm_client import LLMClient
from .step2_0_0_time_event_graph import TimeEventGraph
from .step3_0_0_dialogue_generate import (
    DialogueGenerator,
    DialogueModel,
    DialogueSession,
    SessionEvidence,
)
from .step3_1_0_dialogue_extract import DialogueExtractor
from .step3_2_0_dialogue_summary import DialogueSummaries, DialogueSummarizer
from ..utils import load_data, parse_date, save_data


class DialogueSessions(DialogueModel):
    """按顺序攒起来的多段对话，整份保存成一个 JSON。"""

    sessions: list[DialogueSession] = Field(default_factory=list)

    def add(self, session: DialogueSession) -> DialogueSession:
        """把一段对话加进集合。同一个 session_id 不能加两次。"""
        if any(item.session_id == session.session_id for item in self.sessions):
            raise ValueError(f"session_id 已存在：{session.session_id}")
        self.sessions.append(session)
        return session

    @classmethod
    def load(cls, save_dir: str | Path, person_id: str) -> "DialogueSessions":
        """读取这个人的对话集合。文件还不存在时返回空集合。"""
        path = cls.session_file(save_dir, person_id)
        if not path.exists():
            return cls()
        return cls.model_validate(load_data(path))

    def save(self, save_dir: str | Path, person_id: str) -> Path:
        """把全部对话写成一份 {person_id}_dialogue_sessions.json。"""
        file_path = self.session_file(save_dir, person_id)
        save_data(file_path, self.model_dump(mode="json"))
        return file_path

    @staticmethod
    def session_file(save_dir: str | Path, person_id: str) -> Path:
        """对话集合文件：{person_id}_dialogue_sessions.json。同一人物只有这一份。"""
        directory = Path(save_dir)
        if directory.suffix:
            raise ValueError("save_dir 必须是保存文件夹，不是文件路径")
        person_id = person_id.strip()
        if not person_id:
            raise ValueError("person_id 不能为空")
        return directory / f"{person_id}_dialogue_sessions.json"

    @classmethod
    def get(
        cls,
        save_dir: str | Path,
        person_id: str,
        event_id: str,
    ) -> DialogueSession:
        """从这一份对话文件载入，再按 event_id 找出那一段。"""
        event_id = event_id.strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        loaded = cls.load(save_dir, person_id)
        for session in loaded.sessions:
            if session.event_id == event_id:
                return session
        raise ValueError(f"没有这个事件的对话：{event_id}")


class DialogueOrchestrator:
    """对话编排。生成一段对话，提取并摘要后返回。"""

    def __init__(
        self,
        llm_client: LLMClient,
        event_graph: TimeEventGraph,
        person_summary: str,
        event_id: str,
        session_id: str,
        save_path: str | Path,
        extract_path: str | Path,
    ) -> None:
        self.llm_client = llm_client
        self.event_graph = event_graph
        self.person_summary = person_summary
        self.event_id = event_id.strip()
        self.session_id = session_id.strip()
        self.save_path = DialogueSummaries.summary_file(save_path)
        self.extract_path = DialogueExtractor.extract_file(extract_path)
        if not self.event_id:
            raise ValueError("event_id 不能为空")
        if not self.session_id:
            raise ValueError("session_id 不能为空")
        self._current_event()

    def build(self) -> DialogueSession:
        """生成这段对话，再提取和摘要，返回 DialogueSession。"""
        event = self._current_event()
        session_time = self._session_time(event.time)
        turns = DialogueGenerator(
            self.llm_client,
            self.event_graph,
            self.person_summary,
            self.event_id,
            DialogueSummaries.latest(self.save_path),
        ).generate()
        extracted = DialogueExtractor(
            self.llm_client,
            turns,
            self.session_id,
            session_time,
            event.goal_state,
            self.extract_path,
        ).extract()
        session_summary = DialogueSummarizer(
            self.llm_client,
            turns,
            session_time,
            self.save_path,
        ).summarize()
        return DialogueSession(
            session_id=self.session_id,
            event_id=self.event_id,
            session_time=session_time,
            turns=turns,
            session_summary=session_summary,
            facts=extracted.fact,
            events=extracted.event,
            evidence=[SessionEvidence(turn_id=item.turn_id) for item in extracted.evidence],
            states=[state.model_copy(deep=True) for state in event.goal_state],
        )

    def _session_time(self, event_time: str) -> str:
        """对话发生在事件的第二天。"""
        return (parse_date(event_time) + timedelta(days=1)).isoformat()

    def _current_event(self):
        for event in self.event_graph.events:
            if event.event_id == self.event_id:
                return event
        raise ValueError(f"事件图里没有这个事件：{self.event_id}")
