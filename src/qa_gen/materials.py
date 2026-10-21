"""加载出题原料。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dialogue_gen.step1_0_0_target_state import PlanningState
from ..utils import load_data
from .models import PersonMaterials


def load_person_materials(
    person_id: str,
    *,
    output_dir: str | Path,
    planning_round: str,
) -> PersonMaterials:
    """从 data/output 装一个人的 planning + sessions + extracts。"""
    root = Path(output_dir)
    planning_path = root / f"{person_id}_{planning_round}_planning_state.json"
    sessions_path = root / f"{person_id}_dialogue_sessions.json"
    extracts_path = root / f"{person_id}_dialogue_extracts.jsonl"

    planning = PlanningState.model_validate(load_data(planning_path))
    sessions_raw: dict[str, Any] = load_data(sessions_path)
    sessions = list(sessions_raw.get("sessions") or [])
    extracts = list(load_data(extracts_path) or [])
    return PersonMaterials(
        person_id=person_id,
        planning=planning,
        sessions=sessions,
        extracts=extracts,
    )


def filter_single_qa_materials(materials: PersonMaterials) -> PersonMaterials:
    """筛出「单版本 subject」原料包，供单跳基础 QA 使用。

    - planning：只保留 len(versions)==1，且该版本带 event_id 的状态链
      （无 event_id 的多为 v0 initial，对不上对话证据）
    - extracts：只保留 goal_state 命中这些 subject 的 evidence
    - sessions：只保留上述 extracts 仍引用到的 session，且 turns 只保留用户发言
    """
    single_chains = [
        chain
        for chain in materials.planning.states
        if len(chain.versions) == 1 and chain.versions[0].event_id
    ]
    return _materials_for_chains(materials, single_chains)


def filter_update_chain_materials(materials: PersonMaterials) -> PersonMaterials:
    """筛出「多版本 subject」原料包，供同一 subject 的更新链使用。

    - planning：只保留 len(versions)>1 的状态链
    - extracts / sessions：与单跳相同，按这些 subject 裁证据，turns 只留用户发言
    """
    update_chains = [
        chain for chain in materials.planning.states if len(chain.versions) > 1
    ]
    return _materials_for_chains(materials, update_chains)


def _materials_for_chains(materials: PersonMaterials, chains: list) -> PersonMaterials:
    """按给定状态链裁 extracts 和 sessions。"""
    keys = {
        (chain.domain, chain.subcategory, chain.subject) for chain in chains
    }

    filtered_extracts: list[dict[str, Any]] = []
    for row in materials.extracts:
        kept_evidence = []
        for item in row.get("evidence") or []:
            if _evidence_key(item) in keys:
                kept_evidence.append(item)
        if kept_evidence:
            filtered_extracts.append({**row, "evidence": kept_evidence})

    keep_session_ids = {
        str(row["session_id"])
        for row in filtered_extracts
        if row.get("session_id")
    }
    filtered_sessions = [
        _user_only_session(session)
        for session in materials.sessions
        if str(session.get("session_id") or "") in keep_session_ids
    ]

    planning = materials.planning.model_copy(update={"states": chains})
    return PersonMaterials(
        person_id=materials.person_id,
        planning=planning,
        sessions=filtered_sessions,
        extracts=filtered_extracts,
    )


def iter_single_hop_payloads(materials: PersonMaterials) -> list[dict[str, Any]]:
    """单跳共用取数：每个单版本 subject → 一条平铺 payload。

    会先走 filter_single_qa_materials。缺 session / extract / 本 subject 证据则跳过。
    各 step1_* 的 build_candidates 再包成 QACandidate（ability / template 各自定）。
    """
    materials = filter_single_qa_materials(materials)

    sessions_by_event = {
        str(session["event_id"]): session
        for session in materials.sessions
        if session.get("event_id")
    }
    extracts_by_session = {
        str(row["session_id"]): row
        for row in materials.extracts
        if row.get("session_id")
    }

    payloads: list[dict[str, Any]] = []
    for chain in materials.planning.states:
        version = chain.versions[0]
        event_id = str(version.event_id)
        session = sessions_by_event.get(event_id)
        if session is None:
            continue

        session_id = str(session.get("session_id") or "")
        extract_row = extracts_by_session.get(session_id)
        if extract_row is None:
            continue

        subject_key = (chain.domain, chain.subcategory, chain.subject)
        subject_evidence = [
            item
            for item in (extract_row.get("evidence") or [])
            if _evidence_key(item) == subject_key
        ]
        if not subject_evidence:
            continue

        payloads.append(
            {
                "domain": chain.domain,
                "subcategory": chain.subcategory,
                "subject": chain.subject,
                "value": version.value,
                "op": version.op,
                "round_id": version.round_id,
                "event_id": event_id,
                "session": session,
                "extract": {**extract_row, "evidence": subject_evidence},
            }
        )
    return payloads


def iter_update_chain_payloads(materials: PersonMaterials) -> list[dict[str, Any]]:
    """同一 subject 的更新链：len(versions)>1 → 一条带 versions 的 payload。

    会先走 filter_update_chain_materials。每一版的挂法与单跳相同：
    按 event_id 找 session，extract 的 evidence 只留本 subject，turns 只有用户发言。
    没有 event_id，或对不上 session / extract / 本 subject 证据时，该版 session、extract 为 None。
    整条链一版证据都没有则跳过。
    """
    materials = filter_update_chain_materials(materials)
    sessions_by_event = {
        str(session["event_id"]): session
        for session in materials.sessions
        if session.get("event_id")
    }
    extracts_by_session = {
        str(row["session_id"]): row
        for row in materials.extracts
        if row.get("session_id")
    }

    payloads: list[dict[str, Any]] = []
    for chain in materials.planning.states:
        subject_key = (chain.domain, chain.subcategory, chain.subject)
        versions: list[dict[str, Any]] = []
        for version in chain.versions:
            versions.append(
                _version_payload(
                    version,
                    subject_key,
                    sessions_by_event,
                    extracts_by_session,
                )
            )
        if not any(item["extract"] for item in versions):
            continue
        payloads.append(
            {
                "domain": chain.domain,
                "subcategory": chain.subcategory,
                "subject": chain.subject,
                "versions": versions,
                "current_value": chain.versions[-1].value,
                "stale_value": chain.versions[-2].value,
            }
        )
    return payloads


def _version_payload(
    version: Any,
    subject_key: tuple[Any, Any, Any],
    sessions_by_event: dict[str, dict[str, Any]],
    extracts_by_session: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """把一个版本收成 payload 里的一条。对不上证据时 session、extract 留空。"""
    event_id = version.event_id
    payload: dict[str, Any] = {
        "version": version.version,
        "round_id": version.round_id,
        "op": version.op,
        "value": version.value,
        "event_id": event_id,
        "session": None,
        "extract": None,
    }
    if not event_id:
        return payload

    session = sessions_by_event.get(str(event_id))
    if session is None:
        return payload
    extract_row = extracts_by_session.get(str(session.get("session_id") or ""))
    if extract_row is None:
        return payload
    subject_evidence = [
        item
        for item in (extract_row.get("evidence") or [])
        if _evidence_key(item) == subject_key
    ]
    if not subject_evidence:
        return payload
    payload["session"] = session
    payload["extract"] = {**extract_row, "evidence": subject_evidence}
    return payload


def _evidence_key(item: dict[str, Any]) -> tuple[Any, Any, Any]:
    goal = item.get("goal_state") or {}
    return (goal.get("domain"), goal.get("subcategory"), goal.get("subject"))


def _user_only_session(session: dict[str, Any]) -> dict[str, Any]:
    """复制 session，并从 turns 中移除 assistant 回复。"""
    user_turns = [
        turn
        for turn in (session.get("turns") or [])
        if turn.get("speaker") == "user"
    ]
    return {**session, "turns": user_turns}


def event_to_session_id(materials: PersonMaterials) -> dict[str, str]:
    """event_id → session_id。"""
    mapping: dict[str, str] = {}
    for session in materials.sessions:
        event_id = session.get("event_id")
        session_id = session.get("session_id")
        if event_id and session_id:
            mapping[str(event_id)] = str(session_id)
    return mapping


def latest_session_time(materials: PersonMaterials) -> str | None:
    """取会话里最晚的 session_time，作默认 query_time。"""
    times = [
        str(s["session_time"])
        for s in materials.sessions
        if s.get("session_time")
    ]
    return max(times) if times else None
