"""Step1.3：拒答题。"""

from ...llm_client import ChatMessage
from .base import Hop, QuestionGenerator
from .materials import iter_single_hop_payloads
from .models import PersonMaterials, QACandidate
from .qa_prompt.RJ import RJ_S_SYSTEM_PROMPT, build_rj_s_user_prompt


class RejectQAGenerator(QuestionGenerator):
    """拒答（单跳 / 多跳由 hop 区分）。"""

    ability = "reject"

    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        if hop != "single":
            raise NotImplementedError("多跳拒答候选尚未实现")

        ability = self.resolve_ability(hop)
        candidates: list[QACandidate] = []
        payloads = iter_single_hop_payloads(materials)
        known_memory = _known_memory_snapshot(materials, query_time)
        for index, payload in enumerate(payloads):
            candidates.append(
                QACandidate(
                    candidate_id=(
                        f"{materials.person_id}_rj_{index:03d}_{payload['subject']}"
                    ),
                    person_id=materials.person_id,
                    ability=ability,
                    template="RJ-S",
                    query_time=query_time,
                    payload={**payload, "known_memory": known_memory},
                )
            )
        return candidates

    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        if candidate.template != "RJ-S":
            raise NotImplementedError(f"尚未实现模板：{candidate.template}")
        return [
            ChatMessage.system(RJ_S_SYSTEM_PROMPT),
            ChatMessage.user(
                build_rj_s_user_prompt(
                    query_time=candidate.query_time or "",
                    payload=candidate.payload,
                )
            ),
        ]


def _known_memory_snapshot(
    materials: PersonMaterials,
    query_time: str,
) -> list[dict[str, object]]:
    """汇总 query_time 前已在对话中暴露的最新事实，供拒答题排除假空白。"""
    session_time_by_event = {
        str(session["event_id"]): str(session["session_time"])
        for session in materials.sessions
        if session.get("event_id") and session.get("session_time")
    }
    snapshot: list[dict[str, object]] = []
    for chain in materials.planning.states:
        latest = None
        latest_time = None
        for version in chain.versions:
            if not version.event_id:
                continue
            asserted_at = session_time_by_event.get(str(version.event_id))
            if asserted_at is None or (query_time and asserted_at > query_time):
                continue
            latest = version
            latest_time = asserted_at
        if latest is None:
            continue
        snapshot.append(
            {
                "domain": chain.domain,
                "subcategory": chain.subcategory,
                "subject": chain.subject,
                "value": latest.value,
                "asserted_at": latest_time,
            }
        )
    return snapshot
