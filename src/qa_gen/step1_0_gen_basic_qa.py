"""Step1.0：信息抽取题。"""

from __future__ import annotations

from ...llm_client import ChatMessage
from .base import Hop, QuestionGenerator
from .materials import iter_single_hop_payloads, iter_update_chain_payloads
from .models import PersonMaterials, QACandidate
from .qa_prompt.IE import (
    IE_M_SYSTEM_PROMPT,
    IE_S_SYSTEM_PROMPT,
    build_ie_m_user_prompt,
    build_ie_s_user_prompt,
)


class BasicQAGenerator(QuestionGenerator):
    """信息抽取（单跳 / 多跳由 hop 区分）。"""

    ability = "information_extraction"

    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        """取数走公用逻辑；此处只包 QACandidate 壳。"""
        if hop == "single":
            payloads = iter_single_hop_payloads(materials)
            template = "IE-S"
        elif hop == "multi":
            payloads = iter_update_chain_payloads(materials)
            template = "IE-M"
        else:
            raise ValueError(f"未知 hop：{hop}")

        ability = self.resolve_ability(hop)
        candidates: list[QACandidate] = []
        for index, payload in enumerate(payloads):
            candidates.append(
                QACandidate(
                    candidate_id=(
                        f"{materials.person_id}_ie_{index:03d}_{payload['subject']}"
                    ),
                    person_id=materials.person_id,
                    ability=ability,
                    template=template,
                    query_time=query_time,
                    payload=payload,
                )
            )
        return candidates

    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        query_time = candidate.query_time or ""
        if candidate.template == "IE-S":
            system_prompt = IE_S_SYSTEM_PROMPT
            user_prompt = build_ie_s_user_prompt(
                query_time=query_time,
                payload=candidate.payload,
            )
        elif candidate.template == "IE-M":
            system_prompt = IE_M_SYSTEM_PROMPT
            user_prompt = build_ie_m_user_prompt(
                query_time=query_time,
                payload=candidate.payload,
            )
        else:
            raise NotImplementedError(f"尚未实现模板：{candidate.template}")
        return [
            ChatMessage.system(system_prompt),
            ChatMessage.user(user_prompt),
        ]
