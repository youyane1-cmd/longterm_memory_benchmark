"""对话生成。按时间事件图写对话，一段只覆盖当前时间点之前已经发生的事。"""

from datetime import timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt.dialogue.step_3_0_dialogue import (
    build_assistant_system_prompt,
    build_user_system_prompt,
)
from .step2_0_0_time_event_graph import Event, GoalState, TimeEventGraph
from ..utils import parse_date


class DialogueModel(BaseModel):
    """对话数据的公共配置。"""

    model_config = ConfigDict(extra="forbid")


class UserTurn(DialogueModel):
    """用户说的一句。编号由代码分配。"""

    turn_id: str
    content: str
    speaker: Literal["user"] = "user"


class AssistantTurn(DialogueModel):
    """助手说的一句。编号由代码分配。"""

    turn_id: str
    content: str
    speaker: Literal["assistant"] = "assistant"


SpokenTurn = Annotated[UserTurn | AssistantTurn, Field(discriminator="speaker")]


class SessionEvidence(DialogueModel):
    """点明目标状态的那句发言。生成时先留空。"""

    turn_id: str


class DialogueSession(DialogueModel):
    """一段已经发生的对话，对应事件图上的一个时间点。"""

    session_id: str
    event_id: str
    session_time: str
    turns: list[SpokenTurn]
    session_summary: str = ""
    facts: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    evidence: list[SessionEvidence] = Field(default_factory=list)
    states: list[GoalState] = Field(default_factory=list)
    goalstate: list[GoalState] = Field(default_factory=list)


TURN_LIMIT = 12


class DialogueGenerator:
    """对话生成。按事件时间写下一段对话。"""

    def __init__(
        self,
        llm_client: LLMClient,
        event_graph: TimeEventGraph,
        person_summary: str,
        event_id: str,
        previous_session_summary: str,
    ) -> None:
        self.llm_client = llm_client
        self.event_graph = event_graph
        self.person_summary = person_summary.strip()
        self.event_id = event_id.strip()
        self.previous_session_summary = previous_session_summary.strip()
        self.turns: list[SpokenTurn] = []
        if not self.person_summary:
            raise ValueError("人物摘要不能为空")
        if not self.event_id:
            raise ValueError("event_id 不能为空")
        if not self.event_graph.events:
            raise ValueError("事件图没有事件，无法生成对话")
        self._current_event()

    def generate(self) -> list[SpokenTurn]:
        """让用户和助手交替开口，满 12 句后返回 turns，供摘要和提取使用。"""
        while len(self.turns) < TURN_LIMIT:
            if len(self.turns) % 2 == 0:
                self.turns.append(self._user_turn())
            else:
                self.turns.append(self._assistant_turn())
        return self.turns

    def _user_turn(self) -> UserTurn:
        content = self.llm_client.chat(self._user_messages()).strip()
        if not content:
            raise ValueError("用户没有说出内容")
        return UserTurn(turn_id=self._next_turn_id(), content=content)

    def _assistant_turn(self) -> AssistantTurn:
        content = self.llm_client.chat(self._assistant_messages()).strip()
        if not content:
            raise ValueError("助手没有说出内容")
        return AssistantTurn(turn_id=self._next_turn_id(), content=content)

    def _user_messages(self) -> list[ChatMessage]:
        """用户侧把历史角色反过来：自己说过的话算助手，对方说过的话算用户。"""
        messages = [ChatMessage.system(self._user_system())]
        if not self.turns:
            messages.append(ChatMessage.user("请先向助手开口。"))
            return messages
        for turn in self.turns:
            if isinstance(turn, UserTurn):
                messages.append(ChatMessage.assistant(turn.content))
            else:
                messages.append(ChatMessage.user(turn.content))
        return messages

    def _assistant_messages(self) -> list[ChatMessage]:
        messages = [ChatMessage.system(self._assistant_system())]
        for turn in self.turns:
            if isinstance(turn, UserTurn):
                messages.append(ChatMessage.user(turn.content))
            else:
                messages.append(ChatMessage.assistant(turn.content))
        return messages

    def _user_system(self) -> str:
        event = self._current_event()
        return build_user_system_prompt(
            self.person_summary,
            self._past_events_text(),
            self._previous_summary(),
            self._event_text(event),
            self._goal_states_text(event),
            self._session_time(event.time),
        )

    def _assistant_system(self) -> str:
        event = self._current_event()
        return build_assistant_system_prompt(
            self._previous_summary(),
            self._session_time(event.time),
        )

    def _current_event(self) -> Event:
        for event in self.event_graph.events:
            if event.event_id == self.event_id:
                return event
        raise ValueError(f"事件图里没有这个事件：{self.event_id}")

    def _past_events(self) -> list[Event]:
        past: list[Event] = []
        for event in self.event_graph.events:
            if event.event_id == self.event_id:
                return past
            past.append(event)
        raise ValueError(f"事件图里没有这个事件：{self.event_id}")

    def _past_events_text(self) -> str:
        events = self._past_events()
        if not events:
            return "无"
        return "\n".join(self._event_text(event) for event in events)

    def _session_time(self, event_time: str) -> str:
        """对话发生在事件的第二天。"""
        return (parse_date(event_time) + timedelta(days=1)).isoformat()

    def _event_text(self, event: Event) -> str:
        """时间和事件绑在一起。"""
        return f"{event.time}：{event.event}"

    def _goal_states_text(self, event: Event) -> str:
        if not event.goal_state:
            return "无"
        lines = []
        for state in event.goal_state:
            lines.append(f"{state.subject}：{state.change}")
        return "\n\n".join(lines)

    def _previous_summary(self) -> str:
        return self.previous_session_summary or "无"

    def _next_turn_id(self) -> str:
        return f"{self.event_id}-T{len(self.turns) + 1:03d}"

    