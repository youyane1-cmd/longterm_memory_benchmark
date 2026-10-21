"""顶层编排。档案、目标、事件图都先保存再载入，最后批量生成本轮对话。"""

import re
from pathlib import Path

from .src.api import (
    DialogueExtractor,
    DialogueOrchestrator,
    DialogueSessions,
    DialogueSummaries,
    DomainSelection,
    LLMClient,
    PersonProfile,
    PlanningState,
    ProfileData,
    TargetState,
    TimeEventGraph,
    TimeEventGraphPlanner,
    TimePlan,
    load_data,
)


STATE_COVERAGE_ERROR = "证据必须覆盖每一次状态变化，且不能多出未给出的状态"
DIALOGUE_ATTEMPTS = 3


def build_dialogues(
    save_dir: str | Path,
    event_graph: TimeEventGraph,
    round_id: str,
    person_summary: str,
    llm_client: LLMClient,
) -> DialogueSessions:
    """按传入的时间事件图，只为本轮还没有对话的事件生成一段。"""
    round_id = round_id.strip()
    if not round_id:
        raise ValueError("round_id 不能为空")
    if not event_graph.events:
        raise ValueError("事件图没有事件，无法生成对话")
    if not any(event.event_id.startswith(f"{round_id}-") for event in event_graph.events):
        raise ValueError(f"事件图里没有这一轮的事件：{round_id}")
    sessions = DialogueSessions.load(save_dir, event_graph.person_id)
    saved = {item.event_id: item for item in sessions.sessions}
    summary_path = _summary_path(save_dir, event_graph.person_id)
    extract_path = _extract_path(save_dir, event_graph.person_id)
    for event in event_graph.events:
        if saved.get(event.event_id) is not None:
            continue
        if not event.event_id.startswith(f"{round_id}-"):
            continue
        session = _build_session(
            llm_client,
            event_graph,
            person_summary,
            event.event_id,
            _session_id(event.event_id),
            summary_path,
            extract_path,
        )
        sessions.add(session)
        sessions.save(save_dir, event_graph.person_id)
        saved[event.event_id] = session
    return sessions


def _build_session(
    llm_client: LLMClient,
    event_graph: TimeEventGraph,
    person_summary: str,
    event_id: str,
    session_id: str,
    summary_path: Path,
    extract_path: Path,
):
    """生成一段对话。状态覆盖校验失败时，丢掉这段对话，按同一事件最多生成三次。"""
    last_error: ValueError | None = None
    for attempt in range(1, DIALOGUE_ATTEMPTS + 1):
        try:
            return DialogueOrchestrator(
                llm_client,
                event_graph,
                person_summary,
                event_id,
                session_id,
                summary_path,
                extract_path,
            ).build()
        except ValueError as error:
            if str(error) != STATE_COVERAGE_ERROR:
                raise
            last_error = error
            if attempt == DIALOGUE_ATTEMPTS:
                break
            print(
                f"{event_id} 状态校验未通过，重新生成这段对话 {attempt}/{DIALOGUE_ATTEMPTS}",
                flush=True,
            )
    raise ValueError(f"{event_id} 状态校验连续 {DIALOGUE_ATTEMPTS} 次未通过：{last_error}")


def run_dialogue(
    profile_path: str | Path,
    llm_client: LLMClient,
    save_dir: str | Path,
    round_id: int,
    time_start: str,
    dialogue_client: LLMClient | None = None,
    domains: DomainSelection | None = None,
    fixed_side_domains: list[str] | None = None,
) -> DialogueSessions:
    """按版本载入人物档案，每份档案规划它的下一轮并生成对话。time_start 是世界时间线的起始日期。

    round_id 是整数。传入 3 时，按 v0、v1、v2、v3 逐轮执行。
    每一轮开始时载入该版本的人物档案。下一版档案由上一轮结束时写出，不能提前查找。
    domains 若传入，则每轮新规划都使用这组领域。
    fixed_side_domains 若传入，则这些域固定为副线，主线与其余副线仍随机。

    伪代码：
    for index in 0 .. round_id:
        载入这一轮的人物画像，文件名是 {person_id}_v{index}_profile_data.json
        生成或载入摘要
        载入这一版累计状态，规划下一轮并保存，再载入
        载入事件图，只为本轮事件批量生成对话
        用这一轮累计状态的最后一版写成下一版人物画像
    """
    if round_id < 0:
        raise ValueError(f"round_id 必须是非负整数：{round_id}")
    if domains is not None and fixed_side_domains:
        raise ValueError("domains 与 fixed_side_domains 不能同时使用")
    dialogue_client = llm_client if dialogue_client is None else dialogue_client
    sessions: DialogueSessions | None = None
    for index in range(round_id + 1):
        person_file = _round_profile_file(profile_path, save_dir, index)
        if not person_file.exists():
            raise ValueError(f"人物档案还不存在：{person_file}")
        print(f"cycle {index + 1}/{round_id + 1} v{index} -> v{index + 1}", flush=True)
        profile = _load_profile(person_file, llm_client, save_dir)
        person_id = profile.profile_data.person_id
        work_round = _prepare_round(
            profile,
            llm_client,
            save_dir,
            domains,
            fixed_side_domains,
        )
        graph = _load_event_graph(
            person_id,
            work_round,
            llm_client,
            save_dir,
            time_start,
        )
        sessions = build_dialogues(save_dir, graph, work_round, profile.load_summary(), dialogue_client)
        _save_profile_from_state(save_dir, person_id, work_round, llm_client)
    if sessions is None:
        raise ValueError(f"到 v{round_id} 为止没有可载入的人物档案")
    return sessions


def _load_profile(
    profile_path: str | Path,
    llm_client: LLMClient,
    save_dir: str | Path,
) -> PersonProfile:
    """保存档案和摘要后，再从 JSON 载入人物档案。摘要已有则不再生成。"""
    profile = PersonProfile(
        ProfileData.model_validate(load_data(profile_path)),
        save_dir,
        llm_client,
    )
    profile.save_profile()
    if not profile.summary_path.exists():
        profile.save_summary(profile.summarize_profile())
    saved = ProfileData.model_validate(load_data(profile.profile_data_path))
    return PersonProfile(saved, save_dir, llm_client)


def _round_profile_file(
    profile_path: str | Path,
    save_dir: str | Path,
    index: int,
) -> Path:
    """按轮次载入人物画像：{person_id}_v{index}_profile_data.json。结果目录还没有 v0 时用入口文件。"""
    person_id = _person_id_from_profile(profile_path)
    saved = Path(save_dir) / f"{person_id}_v{index}_profile_data.json"
    if index == 0 and not saved.exists():
        return Path(profile_path)
    return saved


def _person_id_from_profile(profile_path: str | Path) -> str:
    """从 P001_v0_profile_data.json 这种入口文件名取出人物编号。"""
    path = Path(profile_path)
    match = re.fullmatch(r"(.+)_v\d+_profile_data", path.stem)
    if match is None:
        raise ValueError(
            f"档案路径需要是人物画像文件，例如 P001_v0_profile_data.json：{profile_path}"
        )
    return match.group(1)


def _save_profile_from_state(
    save_dir: str | Path,
    person_id: str,
    round_id: str,
    llm_client: LLMClient,
) -> ProfileData:
    """对话结束后，把这一轮累计状态的最后一版保存成人物画像。"""
    planning = TargetState.load_planning_state(save_dir, person_id, round_id)
    profile = PersonProfile(planning.to_profile(), save_dir, llm_client)
    return profile.save_profile()


def _prepare_round(
    profile: PersonProfile,
    llm_client: LLMClient,
    save_dir: str | Path,
    domains: DomainSelection | None = None,
    fixed_side_domains: list[str] | None = None,
) -> str:
    """用这份档案的版本载入累计状态，只规划它的下一轮。"""
    _ensure_initial_planning(profile, llm_client, save_dir)
    person_id = profile.profile_data.person_id
    source = profile.profile_data.round_id
    work = _next_round(source)
    if not TargetState.target_state_file(save_dir, person_id, work).exists():
        planning = TargetState.load_planning_state(save_dir, person_id, source)
        planner = TargetState(
            profile,
            planning,
            llm_client,
            save_dir,
            domain_selection=domains,
            fixed_side_domains=fixed_side_domains,
        )
        planner.save_round(planner.cumulative_state())
    return work


def _ensure_initial_planning(
    profile: PersonProfile,
    llm_client: LLMClient,
    save_dir: str | Path,
) -> None:
    """v0 还没有累计状态时先写成文件。后面使用的是载入后的对象。"""
    person_id = profile.profile_data.person_id
    round_id = profile.profile_data.round_id
    if TargetState.planning_state_file(save_dir, person_id, round_id).exists():
        return
    TargetState(
        profile,
        PlanningState(person_id="", person_summary="", round_id=round_id),
        llm_client,
        save_dir,
    ).initial_target_state()


def _load_event_graph(
    person_id: str,
    round_id: str,
    llm_client: LLMClient,
    save_dir: str | Path,
    time_start: str,
) -> TimeEventGraph:
    """本轮事件图没有文件时先生成并保存，再载入。上一轮事件图也从文件载入。"""
    if not _event_graph_exists(save_dir, person_id, round_id):
        cumulative = TargetState.load_round(save_dir, person_id, round_id)
        previous = None
        if _round_index(round_id) > 1:
            previous = TimeEventGraphPlanner.load(save_dir, person_id, f"v{_round_index(round_id) - 1}")
        TimeEventGraphPlanner(llm_client, cumulative, save_dir, previous).generate(
            TimePlan(time_start),
        )
    return TimeEventGraphPlanner.load(save_dir, person_id, round_id)


def _event_graph_exists(save_dir: str | Path, person_id: str, round_id: str) -> bool:
    return TimeEventGraphPlanner.event_graph_file(save_dir, person_id, round_id).exists()


def _next_round(round_id: str) -> str:
    return f"v{_round_index(round_id) + 1}"


def _round_index(round_id: str) -> int:
    match = re.fullmatch(r"v(\d+)", round_id)
    if match is None:
        raise ValueError(f"无效的版本编号：{round_id}")
    return int(match.group(1))


def _extract_path(save_dir: str | Path, person_id: str) -> Path:
    """提取结果文件：{person_id}_dialogue_extracts.jsonl。每段对话一行。"""
    return DialogueExtractor.extract_file(Path(save_dir) / f"{person_id}_dialogue_extracts.jsonl")


def _summary_path(save_dir: str | Path, person_id: str) -> Path:
    """滚动摘要文件：{person_id}_dialogue_summaries.jsonl。每段对话一行。"""
    return DialogueSummaries.summary_file(Path(save_dir) / f"{person_id}_dialogue_summaries.jsonl")


def _session_id(event_id: str) -> str:
    """v1-EV001 对应 v1-S001。"""
    prefix, separator, index = event_id.partition("-EV")
    if not separator or not index.isdigit():
        raise ValueError(f"无法从事件编号分配 session_id：{event_id}")
    return f"{prefix}-S{index}"
