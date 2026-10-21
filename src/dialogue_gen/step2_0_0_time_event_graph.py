"""时间事件图的数据结构与生成入口。"""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt.time_event_graph.step_2_0_time_event_graph import (
    EVENT_GRAPH_SYSTEM_PROMPT,
    build_event_graph_user_prompt,
)
from .step1_0_0_target_state import (
    CumulativeRound,
    PlanningState,
    StateVersion,
    TargetChange,
    TargetState,
)
from .step1_1_0_time_plan import TimePlan, TimeWindow
from ..utils import load_data, parse_date, save_data


class EventGraphModel(BaseModel):
    """时间事件图模型的公共配置。"""

    model_config = ConfigDict(extra="forbid")


class GoalState(EventGraphModel):
    """事件覆盖的一条状态转变。由 change_id 从本轮目标里复制，不保留编号。"""

    domain: str
    subcategory: str
    subject: str
    op: Literal["update", "create"]
    change: str


class Event(EventGraphModel):
    """时间事件图中的一个事件。"""

    event_id: str
    time: str
    event: str
    goal_state: list[GoalState] = Field(default_factory=list)


class TimeEventGraph(EventGraphModel):
    """一个人物按时间排列的事件图。"""

    person_id: str
    events: list[Event] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered_unique_events(self) -> "TimeEventGraph":
        seen: set[str] = set()
        previous: date | None = None
        for event in self.events:
            if event.event_id in seen:
                raise ValueError(f"事件编号重复：{event.event_id}")
            seen.add(event.event_id)
            current = parse_date(event.time)
            if previous is not None and current < previous:
                raise ValueError("事件必须按时间从早到晚排列")
            previous = current
        return self


class PlannedEvent(EventGraphModel):
    """模型返回的一条事件。编号由代码分配，时间由模型给出。"""

    time: str
    event: str
    goal_state: list[str] = Field(default_factory=list)


class PlannedEventGraph(EventGraphModel):
    """模型返回的本轮事件列表，列表顺序就是因果先后。"""

    events: list[PlannedEvent]


class TimeEventGraphPlanner:
    """根据本轮累计结果编排时间事件图。事件日期由模型在时间窗口内给出。"""

    def __init__(
        self,
        llm_client: LLMClient,
        cumulative_round: CumulativeRound,
        save_dir: str | Path,
        previous_graph: TimeEventGraph | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.cumulative_round = cumulative_round
        self.save_dir = Path(save_dir)
        self.previous_graph = previous_graph
        self.time_window: TimeWindow | None = None
        person_id = cumulative_round.target_state.person_id
        if previous_graph is not None and previous_graph.person_id != person_id:
            raise ValueError("上一轮事件图与本轮人物不一致")

    def generate(self, time_plan: TimePlan) -> TimeEventGraph:
        """把本轮时间窗口交给模型，由模型写出窗口内的事件和日期，并保存。"""
        if not self.cumulative_round.target_state.changes:
            raise ValueError("最终目标状态没有变化，无法编排事件图")
        self.time_window = time_plan.window(self.cumulative_round.target_state.round_id)
        messages = [
            ChatMessage.system(EVENT_GRAPH_SYSTEM_PROMPT),
            ChatMessage.user(self._user_prompt()),
        ]
        draft = self._chat_validated(messages, self._validate_draft)
        graph = self._append_previous(self._to_graph(draft))
        self.save(graph)
        return graph

    def _append_previous(self, new_graph: TimeEventGraph) -> TimeEventGraph:
        """把本轮新事件接到上一轮完整事件图后面。第一轮没有上一轮，就只保留新事件。"""
        if self.previous_graph is None:
            return new_graph
        previous = self.previous_graph.model_copy(deep=True)
        return TimeEventGraph(
            person_id=new_graph.person_id,
            events=[*previous.events, *new_graph.events],
        )

    def save(self, graph: TimeEventGraph) -> PlanningState:
        """保存本轮完整事件图。

        事件图已经是上一轮全部事件加上本轮新事件。这里只把本轮 event_id 写回对应版本，
        再把完整事件图和该轮 planning_state 一起写到 save_dir。
        """
        planning_state = self.fill_event_ids(graph)
        round_id = self.cumulative_round.target_state.round_id
        save_data(
            self.event_graph_file(self.save_dir, graph.person_id, round_id),
            graph.model_dump(mode="json"),
        )
        save_data(
            TargetState.planning_state_file(self.save_dir, graph.person_id, planning_state.round_id),
            planning_state.model_dump(mode="json"),
        )
        return planning_state

    @staticmethod
    def event_graph_file(save_dir: str | Path, person_id: str, round_id: str) -> Path:
        """时间事件图文件：{person_id}_{round_id}_time_event_graph.json。"""
        return Path(save_dir) / f"{person_id}_{round_id}_time_event_graph.json"

    @classmethod
    def load(cls, save_dir: str | Path, person_id: str, round_id: str) -> TimeEventGraph:
        """按人物和轮次读取已保存的时间事件图，不需要先创建规划器。"""
        return TimeEventGraph.model_validate(
            load_data(cls.event_graph_file(save_dir, person_id, round_id))
        )

    def fill_event_ids(self, graph: TimeEventGraph) -> PlanningState:
        """按事件里的状态，把 event_id 写回本轮累计状态里对应的版本。"""
        planning_state = self.cumulative_round.planning_state
        if graph.person_id != planning_state.person_id:
            raise ValueError("事件图与累计状态的人物不一致")
        round_id = self.cumulative_round.target_state.round_id
        for event in graph.events:
            if not event.event_id.startswith(f"{round_id}-"):
                continue
            for state in event.goal_state:
                version = self._round_version(state.domain, state.subcategory, state.subject)
                label = "/".join((state.domain, state.subcategory, state.subject))
                if version.event_id not in (None, event.event_id):
                    raise ValueError(
                        f"{label} 已经回填了 {version.event_id}，不能再写入 {event.event_id}"
                    )
                version.event_id = event.event_id
        return planning_state

    def _round_version(self, domain: str, subcategory: str, subject: str) -> StateVersion:
        """找到本轮追加到这条状态链上的版本。"""
        target_state = self.cumulative_round.target_state
        for chain in self.cumulative_round.planning_state.states:
            if (chain.domain, chain.subcategory, chain.subject) != (domain, subcategory, subject):
                continue
            matched = [
                version
                for version in chain.versions
                if version.round_id == target_state.round_id
            ]
            if len(matched) != 1:
                raise ValueError(
                    "本轮状态版本不唯一："
                    + "/".join((domain, subcategory, subject))
                )
            return matched[0]
        raise ValueError("累计状态里没有这条变化：" + "/".join((domain, subcategory, subject)))

    def _user_prompt(self) -> str:
        target_state = self.cumulative_round.target_state
        change_list = json.dumps(
            [
                {
                    "change_id": change.change_id,
                    "domain": change.domain,
                    "subcategory": change.subcategory,
                    "subject": change.subject,
                    "op": change.op,
                    "change": change.change,
                }
                for change in target_state.changes
            ],
            ensure_ascii=False,
            indent=2,
        )
        if self.time_window is None:
            raise ValueError("缺少一个月的时间范围")
        return build_event_graph_user_prompt(
            target_state.person_summary,
            change_list,
            self.time_window.start.isoformat(),
            self.time_window.end.isoformat(),
        )

    def _previous_events(self) -> list[dict[str, object]]:
        """上一轮事件。第一轮没有事件图，返回空列表。"""
        if self.previous_graph is None:
            return []
        return [
            {
                "event_id": event.event_id,
                "time": event.time,
                "event": event.event,
                "goal_state": [state.model_dump() for state in event.goal_state],
            }
            for event in self.previous_graph.events
        ]

    def _chat_validated(self, messages: list[ChatMessage], validate) -> PlannedEventGraph:
        conversation = list(messages)
        last_error: ValueError | None = None
        for _ in range(3):
            parsed = self.llm_client.chat_json(conversation, PlannedEventGraph)
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

    def _validate_draft(self, draft: PlannedEventGraph) -> None:
        if self.time_window is None:
            raise ValueError("缺少一个月的时间范围")
        if not draft.events:
            raise ValueError("事件图不能为空")
        allowed = {change.change_id for change in self.cumulative_round.target_state.changes}
        covered: set[str] = set()
        previous: date | None = None
        for event in draft.events:
            if not event.event.strip():
                raise ValueError("事件内容不能为空")
            current = parse_date(event.time)
            if current < self.time_window.start or current > self.time_window.end:
                raise ValueError(
                    f"事件时间 {current.isoformat()} 不在 "
                    f"{self.time_window.start.isoformat()} 至 {self.time_window.end.isoformat()} 内"
                )
            if previous is not None and current < previous:
                raise ValueError("事件必须按时间从早到晚排列")
            previous = current
            unknown = [item for item in event.goal_state if item not in allowed]
            if unknown:
                raise ValueError("事件引用了不存在的目标状态：" + "、".join(unknown))
            covered.update(event.goal_state)
        duplicated = sorted(item for item in covered if sum(item in event.goal_state for event in draft.events) > 1)
        if duplicated:
            raise ValueError("这些目标状态出现了多次：" + "、".join(duplicated))
        missing = sorted(allowed - covered)
        if missing:
            raise ValueError("这些目标状态还没有事件实现：" + "、".join(missing))

    def _to_graph(self, draft: PlannedEventGraph) -> TimeEventGraph:
        round_id = self.cumulative_round.target_state.round_id
        changes = {
            change.change_id: change
            for change in self.cumulative_round.target_state.changes
        }
        events = [
            Event(
                event_id=f"{round_id}-EV{index:03d}",
                time=parse_date(event.time).isoformat(),
                event=event.event.strip(),
                goal_state=[self._copy_state(changes[change_id]) for change_id in event.goal_state],
            )
            for index, event in enumerate(draft.events, start=1)
        ]
        return TimeEventGraph(
            person_id=self.cumulative_round.target_state.person_id,
            events=events,
        )

    def _copy_state(self, change: TargetChange) -> GoalState:
        """按 change_id 把身份和这一次的 change 抄进事件，不保留编号。"""
        return GoalState(
            domain=change.domain,
            subcategory=change.subcategory,
            subject=change.subject,
            op=change.op,
            change=change.change,
        )


if __name__ == "__main__":
    import sys

    from .step0_0_0_person_profile import DEFAULT_PERSON_DIR

    sys.stdout.reconfigure(encoding="utf-8")
    client = LLMClient()
    output_dir = DEFAULT_PERSON_DIR.parent / "output"
    person_id = "P001"
    round_id = "v1"
    cumulative = TargetState.load_round(output_dir, person_id, round_id)
    for chain in cumulative.planning_state.states:
        for version in chain.versions:
            if version.round_id == round_id:
                version.event_id = None
    print(f"model={client.model}", flush=True)
    graph = TimeEventGraphPlanner(client, cumulative, output_dir).generate(TimePlan("2025-01-01"))
    print(TimeEventGraphPlanner.event_graph_file(output_dir, person_id, round_id))
    for event in graph.events:
        print(f"{event.event_id}  {event.time}")
        print(event.event)
        for state in event.goal_state:
            print(f"  {state.subject}：{state.change}")
        print()
