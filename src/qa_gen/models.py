"""题目生成共用的数据结构。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..dialogue_gen.step1_0_0_target_state import PlanningState


class QAModel(BaseModel):
    """题目相关模型的公共配置。"""

    model_config = ConfigDict(extra="forbid")


class PersonMaterials(QAModel):
    """一个人出题时共用的原料包（各题型按需取字段）。"""

    person_id: str
    planning: PlanningState
    # sessions.json 里的 sessions 列表；需要原文时用
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    # dialogue_extracts.jsonl；状态变更对齐 turn 时用
    extracts: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceRef(QAModel):
    """一条证据在对话中的定位。"""

    session_id: str | None = None
    turn_id: str | None = None
    note: str | None = None


class QACandidate(QAModel):
    """题型筛出的一个候选。payload 由各题型自定义。"""

    candidate_id: str
    person_id: str
    ability: str
    template: str | None = None
    query_time: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)  #题型自己塞的原料，比如旧值/新值、subject、证据 session


class GeneratedQA(QAModel):
    """LLM 结构化输出的最小问答壳（各题型可再包一层更严的 schema）。"""

    suitable: bool
    question: str | None = None
    answer: str | None = None
    reasoning: str | None = None


class QuestionRecord(QAModel):
    """落盘用的统一题目记录。"""

    question_id: str
    ability: str
    template: str | None = None
    person_id: str
    query_time: str | None = None
    question: str
    gold_answer: str
    reasoning: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
