"""Step1.4：知识更新题。"""

from __future__ import annotations

from ...llm_client import ChatMessage
from .base import Hop, QuestionGenerator
from .materials import iter_update_chain_payloads
from .models import PersonMaterials, QACandidate
from .qa_prompt.KU import KU_M_SYSTEM_PROMPT, build_ku_m_user_prompt


class KnowledgeUpdateQAGenerator(QuestionGenerator):
    """知识更新题；当前只支持同一 subject 更新链上的 KU-M。"""

    ability = "knowledge_update"

    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        # 知识更新必须同时读取新旧版本，不存在单跳形态。
        # 返回空列表可避免默认 single 编排因注册本生成器而中断。
        if hop == "single":
            return []
        if hop != "multi":
            raise ValueError(f"未知 hop：{hop}")

        ability = self.resolve_ability(hop)
        candidates: list[QACandidate] = []
        for index, payload in enumerate(iter_update_chain_payloads(materials)):
            candidates.append(
                QACandidate(
                    candidate_id=(
                        f"{materials.person_id}_ku_{index:03d}_{payload['subject']}"
                    ),
                    person_id=materials.person_id,
                    ability=ability,
                    template="KU-M",
                    query_time=query_time,
                    payload=payload,
                )
            )
        return candidates

    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        if candidate.template != "KU-M":
            raise NotImplementedError(f"尚未实现模板：{candidate.template}")
        return [
            ChatMessage.system(KU_M_SYSTEM_PROMPT),
            ChatMessage.user(
                build_ku_m_user_prompt(
                    query_time=candidate.query_time or "",
                    payload=candidate.payload,
                )
            ),
        ]
