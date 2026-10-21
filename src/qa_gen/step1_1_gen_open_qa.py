"""Step1.1：开放域题。"""

from ...llm_client import ChatMessage
from .base import Hop, QuestionGenerator
from .materials import iter_single_hop_payloads
from .models import PersonMaterials, QACandidate
from .qa_prompt.OD import OD_S_SYSTEM_PROMPT, build_od_s_user_prompt


class OpenQAGenerator(QuestionGenerator):
    """开放域（单跳 / 多跳由 hop 区分）。"""

    ability = "open_domain"

    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        if hop != "single":
            raise NotImplementedError("多跳开放域候选尚未实现")

        ability = self.resolve_ability(hop)
        candidates: list[QACandidate] = []
        for index, payload in enumerate(iter_single_hop_payloads(materials)):
            candidates.append(
                QACandidate(
                    candidate_id=(
                        f"{materials.person_id}_od_{index:03d}_{payload['subject']}"
                    ),
                    person_id=materials.person_id,
                    ability=ability,
                    template="OD-S",
                    query_time=query_time,
                    payload=payload,
                )
            )
        return candidates

    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        if candidate.template != "OD-S":
            raise NotImplementedError(f"尚未实现模板：{candidate.template}")
        return [
            ChatMessage.system(OD_S_SYSTEM_PROMPT),
            ChatMessage.user(
                build_od_s_user_prompt(
                    query_time=candidate.query_time or "",
                    payload=candidate.payload,
                )
            ),
        ]
