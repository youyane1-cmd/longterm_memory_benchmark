"""Step1.2：时间题。"""

from ...llm_client import ChatMessage
from .base import Hop, QuestionGenerator
from .materials import iter_single_hop_payloads
from .models import PersonMaterials, QACandidate
from .qa_prompt.TR import TR_S_SYSTEM_PROMPT, build_tr_s_user_prompt


class TemporalQAGenerator(QuestionGenerator):
    """时间题（单跳 / 多跳由 hop 区分）。"""

    ability = "temporal"

    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        if hop != "single":
            raise NotImplementedError("多跳时间题候选尚未实现")

        ability = self.resolve_ability(hop)
        candidates: list[QACandidate] = []
        for index, payload in enumerate(iter_single_hop_payloads(materials)):
            candidates.append(
                QACandidate(
                    candidate_id=(
                        f"{materials.person_id}_tr_{index:03d}_{payload['subject']}"
                    ),
                    person_id=materials.person_id,
                    ability=ability,
                    template="TR-S",
                    query_time=query_time,
                    payload=payload,
                )
            )
        return candidates

    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        if candidate.template != "TR-S":
            raise NotImplementedError(f"尚未实现模板：{candidate.template}")
        return [
            ChatMessage.system(TR_S_SYSTEM_PROMPT),
            ChatMessage.user(
                build_tr_s_user_prompt(
                    query_time=candidate.query_time or "",
                    payload=candidate.payload,
                )
            ),
        ]
