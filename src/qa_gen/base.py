"""题目生成基类与共用流程。

各题型自己负责：取数 / 组候选 / 拼 prompt / 题型校验。
共用部分：调 LLM 生成问答、把候选和模型输出拼成题目、通用字段校验、批量跑候选。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Sequence

from ...llm_client import ChatMessage, LLMClient
from .models import EvidenceRef, GeneratedQA, PersonMaterials, QACandidate, QuestionRecord

Hop = Literal["single", "multi"]


class QuestionGenerator(ABC):
    """单个题型的生成器。

    典型用法：
        gen = BasicQAGenerator(llm_client)
        records = gen.run(materials, query_time="2024-12-01", hop="single")
    """

    ability: str

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def resolve_ability(self, hop: Hop) -> str:
        """ability 带 single_ / multi_ 前缀，例如 single_information_extraction。"""
        return f"{hop}_{self.ability}"

    @abstractmethod
    def build_candidates(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QACandidate]:
        """从人物材料里筛出本题型候选。取什么数据由子类决定。"""

    @abstractmethod
    def build_messages(self, candidate: QACandidate) -> list[ChatMessage]:
        """把候选拼成送进模型的 messages（原料已在 candidate.payload）。"""

    def build_record(
        self,
        candidate: QACandidate,
        generated: GeneratedQA,
    ) -> QuestionRecord:
        """把候选和模型输出拼成题目。子类不覆盖时直接使用本实现。"""
        return QuestionRecord(
            question_id=candidate.candidate_id,
            ability=candidate.ability,
            template=candidate.template,
            person_id=candidate.person_id,
            query_time=candidate.query_time,
            question=generated.question or "",
            gold_answer=generated.answer or "",
            reasoning=generated.reasoning,
            evidence=_collect_evidence(candidate.payload),
        )

    def validate_specific(self, record: QuestionRecord, candidate: QACandidate) -> None:
        """题型专属校验。默认不做事，子类按需覆盖。"""

    def generate_qa(self, messages: Sequence[ChatMessage]) -> GeneratedQA:
        """共用：按 GeneratedQA schema 调结构化输出。"""
        if self.llm_client is None:
            raise RuntimeError("未注入 LLMClient，无法调用 generate_qa")
        return self.llm_client.chat_json(list(messages), GeneratedQA)

    def validate_common(self, record: QuestionRecord) -> None:
        """共用：字段完整性等通用检查。"""
        if not record.question_id.strip():
            raise ValueError("question_id 不能为空")
        if not record.ability.strip():
            raise ValueError("ability 不能为空")
        if not record.person_id.strip():
            raise ValueError("person_id 不能为空")
        if not record.question.strip():
            raise ValueError("question 不能为空")
        if not record.gold_answer.strip():
            raise ValueError("gold_answer 不能为空")
        base = record.ability.removeprefix("single_").removeprefix("multi_")
        if base != self.ability:
            raise ValueError(
                f"ability 不一致：record={record.ability} generator={self.ability}"
            )

    def run_candidate(self, candidate: QACandidate) -> QuestionRecord | None:
        """共用：单个候选 → 生成 → 组记录 → 校验。不适合出题时返回 None。"""
        messages = self.build_messages(candidate)
        generated = self.generate_qa(messages)
        if not generated.suitable:
            return None
        record = self.build_record(candidate, generated)
        self.validate_common(record)
        self.validate_specific(record, candidate)
        return record

    def run(
        self,
        materials: PersonMaterials,
        query_time: str,
        hop: Hop,
    ) -> list[QuestionRecord]:
        """共用：筛候选并逐个生成。suitable=false 的候选直接跳过。"""
        records: list[QuestionRecord] = []
        for candidate in self.build_candidates(materials, query_time, hop):
            record = self.run_candidate(candidate)
            if record is not None:
                records.append(record)
        return records


def _collect_evidence(payload: dict) -> list[EvidenceRef]:
    """从单条 extract、versions 或 hops 里收集证据。"""
    found: list[EvidenceRef] = []
    _walk_evidence(payload, found)
    return found


def _walk_evidence(node: object, found: list[EvidenceRef]) -> None:
    if not isinstance(node, dict):
        return

    extract = node.get("extract")
    if isinstance(extract, dict):
        session = node.get("session") if isinstance(node.get("session"), dict) else {}
        session_id = extract.get("session_id") or session.get("session_id")
        for item in extract.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            found.append(
                EvidenceRef(
                    session_id=None if session_id is None else str(session_id),
                    turn_id=item.get("turn_id"),
                    note=item.get("gt_memory"),
                )
            )

    for key in ("versions", "hops"):
        children = node.get(key) or []
        if isinstance(children, list):
            for child in children:
                _walk_evidence(child, found)
