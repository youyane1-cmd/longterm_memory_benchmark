"""目标状态的数据结构，以及累计目标与最终目标的生成入口。"""

import random
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt.target_state_plan.step2_domain_taxonomy_v3 import (
    CATEGORY_MAP,
    DOMAIN_DEFINITIONS,
    SUBCATEGORY_DEFINITIONS,
)
from .dialogue_prompt.target_state_plan.step_1_0_target_state import (
    HORIZON,
    MAIN_EXCLUDED_DOMAINS,
    ROUND_CHANGE_COUNT,
    ROUND_PLAN_SYSTEM_PROMPT,
    build_round_plan_user_prompt,
    SELECTED_DOMAIN_COUNT,
)
from .step0_0_0_person_profile import (
    DEFAULT_PERSON_DIR,
    PersonProfile,
    ProfileData,
    ProfileState,
)
from ..utils import load_data, save_data


class TargetStateModel(BaseModel):
    """目标状态数据的公共配置。"""

    model_config = ConfigDict(extra="forbid")


class StateVersion(TargetStateModel):
    """一个实体在某一轮的关系。"""

    version: int
    round_id: str
    op: Literal["initial", "update", "create"]
    value: str | list[str]
    reason: str | None = None
    event_id: str | None = None


class StateChain(TargetStateModel):
    """一个实体的关系版本链。subject 是实体，value 是用户与它的关系。"""

    domain: str
    subcategory: str
    subject: str
    mutable: bool
    versions: list[StateVersion]


class PlanningState(TargetStateModel):
    """累计目标状态，保存人物至今的全部状态链。"""

    person_id: str
    person_summary: str
    round_id: str
    states: list[StateChain] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_states(self) -> "PlanningState":
        seen: set[tuple[str, str, str]] = set()
        for item in self.states:
            key = (item.domain, item.subcategory, item.subject)
            if key in seen:
                raise ValueError("累计状态重复：" + "/".join(key))
            seen.add(key)
        return self

    def to_profile(self) -> ProfileData:
        """取每条状态链的最后一版，组成人物画像。版本号用累计状态自己的 round_id。"""
        states: list[ProfileState] = []
        for chain in self.states:
            path = "/".join((chain.domain, chain.subcategory, chain.subject))
            if not chain.versions:
                raise ValueError("累计状态缺少版本：" + path)
            states.append(
                ProfileState(
                    domain=chain.domain,
                    subcategory=chain.subcategory,
                    subject=chain.subject,
                    mutable=chain.mutable,
                    value=_value_items(chain.versions[-1].value),
                )
            )
        return ProfileData(
            person_id=self.person_id,
            round_id=self.round_id,
            states=states,
        )


class TargetChange(TargetStateModel):
    """最终目标中的一条状态转变。change 是这一次的差量，完整值在累计链上。"""

    change_id: str
    op: Literal["update", "create"]
    domain: str
    subcategory: str
    subject: str
    change: str
    reason: str


class FinalTargetState(TargetStateModel):
    """最终目标状态，只包含本轮必须完成的变化。"""

    plan_id: str
    person_id: str
    person_summary: str
    round_id: str
    horizon: Literal["3_months"] = "3_months"
    changes: list[TargetChange]


class CumulativeRound(TargetStateModel):
    """本轮规划结果。plan 就是目标状态，累计链是追加之后的全部历史。"""

    planning_state: PlanningState
    target_state: FinalTargetState


class DomainSelection(TargetStateModel):
    """本轮选中的 1 个主线和若干副线（合计 SELECTED_DOMAIN_COUNT 个）。"""

    main_domain: str
    side_domains: list[str]


class PlannedChange(TargetStateModel):
    """本轮计划写入的一条关系。subject 是实体，value 是用户与它的关系。"""

    domain: str
    subcategory: str
    subject: str
    op: Literal["update", "create"]
    value: str | list[str]
    mutable: bool
    reason: str


class RoundPlan(TargetStateModel):
    """第二次模型调用返回的本轮变化。"""

    changes: list[PlannedChange]


def _require_value(value: str | list[str], *, allow_empty: bool = False) -> None:
    """value 可以是非空字符串或字符串列表。update 允许空列表，表示最后一条被清空。"""
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("value 不能是空字符串")
        return
    if any(not item.strip() for item in value):
        raise ValueError("value 列表里的每一项都不能为空")
    if not value and not allow_empty:
        raise ValueError("value 列表必须非空")


def _value_items(value: str | list[str]) -> list[str]:
    """把单值或列表统一成列表，供新旧对比使用。"""
    if isinstance(value, str):
        return [value]
    return list(value)


def _format_change(before: list[str] | None, after: list[str]) -> str:
    """把完整新旧值收成一句差量。替换用箭头，增加只留新值，清空写成「旧 → 空」。"""
    previous = [] if before is None else list(before)
    previous_set = set(previous)
    after_set = set(after)
    added = [item for item in after if item not in previous_set]
    removed = [item for item in previous if item not in after_set]
    if len(added) == 1 and len(removed) == 1:
        return f"{removed[0]} → {added[0]}"
    if len(added) == 1 and not removed:
        return added[0]
    if len(removed) == 1 and not added:
        return f"{removed[0]} → 空"
    if not added and not removed:
        raise ValueError("没有实际变化")
    raise ValueError("一条变化只能有一项新增或一项移除")


def _version_number(round_id: str) -> int:
    """将 v0 形式的版本编号转换为整数。"""
    match = re.fullmatch(r"v(\d+)", round_id)
    if match is None:
        raise ValueError(f"无效的版本编号：{round_id}")
    return int(match.group(1))


def _next_round_id(round_id: str) -> str:
    """返回下一轮编号。v0 的下一轮是 v1。"""
    return f"v{_version_number(round_id) + 1}"


def _subcategory_guide(domain_code: str | None) -> list[dict[str, str]]:
    """返回一个领域的全部子类说明，不只是已有状态用过的子类名。"""
    domain_data = SUBCATEGORY_DEFINITIONS.get(domain_code or "", {})
    return [
        {
            "name": sub["name"],
            "question": sub["question"],
            "definition": sub["definition"],
            "examples": sub["examples"],
        }
        for sub in domain_data.get("subcategories", [])
    ]


def _domain_code(domain_name: str) -> str | None:
    """把领域中文名转回 V3 分类代码，供子类校验使用。"""
    for code, definition in DOMAIN_DEFINITIONS.items():
        if definition.get("name") == domain_name:
            return code
    return None


def _find_chain(
    states: list[StateChain],
    domain: str,
    subcategory: str,
    subject: str,
) -> StateChain | None:
    """按领域、子类和实体查找一条关系链。"""
    for chain in states:
        if (chain.domain, chain.subcategory, chain.subject) == (domain, subcategory, subject):
            return chain
    return None


class TargetState:
    """持有人物状态、累计状态和模型客户端。"""

    def __init__(
        self,
        profile: PersonProfile,
        planning_state: PlanningState,
        llm_client: LLMClient,
        save_dir: str | Path,
        domain_selection: DomainSelection | None = None,
        fixed_side_domains: list[str] | None = None,
    ) -> None:
        self.profile = profile
        self.planning_state = planning_state
        self.llm_client = llm_client
        self.save_dir = Path(save_dir)
        self.domain_selection = domain_selection
        self.fixed_side_domains = list(fixed_side_domains or [])

    def initial_target_state(self) -> PlanningState:
        """由人物状态补齐初始累计状态链，写入 JSON，并返回累计状态规划对象。"""
        profile = self.profile.profile_data
        version = _version_number(profile.round_id)
        updated = self.planning_state.model_copy(deep=True)
        if updated.person_id and updated.person_id != profile.person_id:
            raise ValueError("人物状态与累计状态的 person_id 不一致")
        if not updated.states:
            updated.person_id = profile.person_id
            updated.round_id = profile.round_id

        for item in profile.states:
            if _find_chain(updated.states, item.domain, item.subcategory, item.subject):
                continue
            updated.states.append(
                StateChain(
                    domain=item.domain,
                    subcategory=item.subcategory,
                    subject=item.subject,
                    mutable=item.mutable,
                    versions=[
                        StateVersion(
                            version=version,
                            round_id=profile.round_id,
                            op="initial",
                            value=item.value,
                        )
                    ],
                )
            )
        updated.person_summary = self.profile.load_summary()
        self.planning_state = updated
        self.save_planning_state()
        return updated

    def cumulative_state(self) -> CumulativeRound:
        """规划未来三个月的变化，返回本轮目标状态和追加后的累计状态链。"""
        if not self.planning_state.person_summary.strip():
            raise ValueError("累计状态缺少人物摘要，请先生成初始累计状态")
        if not self.planning_state.states:
            raise ValueError("累计状态为空，请先生成初始累计状态")
        selection = self._select_domains()
        plan = self._plan_changes(selection)
        planning_state = self._apply_changes(plan)
        return CumulativeRound(
            planning_state=planning_state,
            target_state=self._target_state_from_plan(plan, planning_state),
        )

    @staticmethod
    def planning_state_file(save_dir: str | Path, person_id: str, round_id: str) -> Path:
        """累计状态文件：{person_id}_{round_id}_planning_state.json。"""
        return Path(save_dir) / f"{person_id}_{round_id}_planning_state.json"

    @staticmethod
    def target_state_file(save_dir: str | Path, person_id: str, round_id: str) -> Path:
        """最终目标文件：{person_id}_{round_id}_target_state.json。"""
        return Path(save_dir) / f"{person_id}_{round_id}_target_state.json"

    @property
    def planning_state_path(self) -> Path:
        """当前累计状态对应的 JSON 路径。"""
        state = self.planning_state
        return self.planning_state_file(self.save_dir, state.person_id, state.round_id)

    @property
    def target_state_path(self) -> Path:
        """当前轮次对应的最终目标 JSON 路径。"""
        state = self.planning_state
        return self.target_state_file(self.save_dir, state.person_id, state.round_id)

    @classmethod
    def load_planning_state(
        cls,
        save_dir: str | Path,
        person_id: str,
        round_id: str,
    ) -> PlanningState:
        """按人物和轮次读取累计状态，不需要先创建规划器。"""
        return PlanningState.model_validate(
            load_data(cls.planning_state_file(save_dir, person_id, round_id))
        )

    @classmethod
    def load_target_state(
        cls,
        save_dir: str | Path,
        person_id: str,
        round_id: str,
    ) -> FinalTargetState:
        """按人物和轮次读取最终目标状态，不需要先创建规划器。"""
        return FinalTargetState.model_validate(
            load_data(cls.target_state_file(save_dir, person_id, round_id))
        )

    @classmethod
    def load_round(
        cls,
        save_dir: str | Path,
        person_id: str,
        round_id: str,
    ) -> CumulativeRound:
        """读取同一轮的累计状态和最终目标状态。"""
        return CumulativeRound(
            planning_state=cls.load_planning_state(save_dir, person_id, round_id),
            target_state=cls.load_target_state(save_dir, person_id, round_id),
        )

    def save_planning_state(self) -> PlanningState:
        """把当前累计状态写入 JSON。轮次与人物档案一致。"""
        save_data(
            self.planning_state_path,
            self.planning_state.model_dump(mode="json"),
        )
        return self.planning_state

    def save_round(self, result: CumulativeRound) -> None:
        """把本轮累计状态链和最终目标状态保存为两个 JSON 文件。"""
        planning_state = result.planning_state
        target_state = result.target_state
        save_data(
            self.planning_state_file(
                self.save_dir,
                planning_state.person_id,
                planning_state.round_id,
            ),
            planning_state.model_dump(mode="json"),
        )
        save_data(
            self.target_state_file(
                self.save_dir,
                planning_state.person_id,
                planning_state.round_id,
            ),
            target_state.model_dump(mode="json"),
        )

    def _target_state_from_plan(
        self,
        plan: RoundPlan,
        planning_state: PlanningState,
    ) -> FinalTargetState:
        """用模型给出的新值和累计链上一条版本做差，写成状态转变。"""
        changes = [
            self._target_change(change, planning_state, index)
            for index, change in enumerate(plan.changes, start=1)
        ]
        return FinalTargetState(
            plan_id=f"TP-{planning_state.person_id}-{planning_state.round_id}",
            person_id=planning_state.person_id,
            person_summary=planning_state.person_summary,
            round_id=planning_state.round_id,
            changes=changes,
        )

    def _target_change(
        self,
        change: PlannedChange,
        planning_state: PlanningState,
        index: int,
    ) -> TargetChange:
        """create 没有旧值。update 的旧值是累计链上刚被盖住的那一版。"""
        path = "/".join((change.domain, change.subcategory, change.subject))
        after = _value_items(change.value)
        before = None
        if change.op == "update":
            chain = _find_chain(
                planning_state.states,
                change.domain,
                change.subcategory,
                change.subject,
            )
            if chain is None or len(chain.versions) < 2:
                raise ValueError("累计状态里找不到更新前的值：" + path)
            before = _value_items(chain.versions[-2].value)
        try:
            change_text = _format_change(before, after)
        except ValueError as error:
            raise ValueError(f"{error}：{path}") from error
        return TargetChange(
            change_id=f"CH{index:02d}",
            op=change.op,
            domain=change.domain,
            subcategory=change.subcategory,
            subject=change.subject,
            change=change_text,
            reason=change.reason,
        )

    def _select_domains(self) -> DomainSelection:
        """确定本轮领域。

        优先级：
        1. 完整 domain_selection（主线+副线全指定）
        2. fixed_side_domains（指定副线，主线与其余副线仍随机）
        3. 全随机
        """
        if self.domain_selection is not None:
            selection = self.domain_selection
            selected = [selection.main_domain, *selection.side_domains]
            if len(selected) != SELECTED_DOMAIN_COUNT:
                raise ValueError(
                    f"本轮需要正好 {SELECTED_DOMAIN_COUNT} 个 domain，当前为 {len(selected)} 个"
                )
            if len(set(selected)) != len(selected):
                raise ValueError("domain 不能重复")
            known = {item["name"] for item in DOMAIN_DEFINITIONS.values()}
            unknown = [name for name in selected if name not in known]
            if unknown:
                raise ValueError("未知 domain：" + "、".join(unknown))
            return selection

        domains = [item["name"] for item in DOMAIN_DEFINITIONS.values()]
        fixed_sides = self._validated_fixed_side_domains(domains)
        remaining = [domain for domain in domains if domain not in set(fixed_sides)]
        side_slots = SELECTED_DOMAIN_COUNT - 1
        extra_side_count = side_slots - len(fixed_sides)

        main_candidates = [
            domain
            for domain in remaining
            if domain not in MAIN_EXCLUDED_DOMAINS
        ]
        if not main_candidates:
            raise ValueError("指定副线之后没有可抽的主线 domain")
        main_domain = random.choice(main_candidates)

        side_pool = [domain for domain in remaining if domain != main_domain]
        if extra_side_count > len(side_pool):
            raise ValueError("剩余 domain 不足以补齐副线")
        extra_sides = (
            random.sample(side_pool, extra_side_count) if extra_side_count else []
        )
        return DomainSelection(
            main_domain=main_domain,
            side_domains=[*fixed_sides, *extra_sides],
        )

    def _validated_fixed_side_domains(self, domains: list[str]) -> list[str]:
        """校验指定副线：必须存在、不重复，且数量不超过副线名额。"""
        fixed_sides = self.fixed_side_domains
        if not fixed_sides:
            return []
        side_slots = SELECTED_DOMAIN_COUNT - 1
        if len(fixed_sides) > side_slots:
            raise ValueError(
                f"指定副线最多 {side_slots} 个，当前 {len(fixed_sides)} 个"
            )
        if len(set(fixed_sides)) != len(fixed_sides):
            raise ValueError("指定副线不能重复")
        known = set(domains)
        unknown = [name for name in fixed_sides if name not in known]
        if unknown:
            raise ValueError("未知指定副线：" + "、".join(unknown))
        return list(fixed_sides)

    def _plan_changes(self, selection: DomainSelection) -> RoundPlan:
        """第二次调用模型，只根据摘要和三个领域的当前状态生成变化。"""
        payload = {
            "horizon": HORIZON,
            "person_summary": self.planning_state.person_summary,
            "change_count": ROUND_CHANGE_COUNT,
            "main_domain": self._domain_payload(selection.main_domain),
            "side_domains": [
                self._domain_payload(domain) for domain in selection.side_domains
            ],
        }
        return self._chat_validated(
            [
                ChatMessage.system(ROUND_PLAN_SYSTEM_PROMPT),
                ChatMessage.user(build_round_plan_user_prompt(payload)),
            ],
            RoundPlan,
            lambda plan: self._validate_changes(plan, selection),
        )

    def _chat_validated(self, messages, response_format, validate):
        """调用结构化输出，并在校验失败时把错误交回模型重试一次。"""
        conversation = list(messages)
        last_error: ValueError | None = None
        for _ in range(3):
            parsed = self.llm_client.chat_json(conversation, response_format)
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

    def _validate_changes(self, plan: RoundPlan, selection: DomainSelection) -> None:
        if len(plan.changes) != ROUND_CHANGE_COUNT:
            raise ValueError(f"本轮必须正好输出 {ROUND_CHANGE_COUNT} 条变化")
        selected = {selection.main_domain, *selection.side_domains}
        seen: set[tuple[str, str, str]] = set()
        for change in plan.changes:
            if change.domain not in selected:
                raise ValueError(f"{change.domain} 不在本轮选中的领域中")
            path = (change.domain, change.subcategory, change.subject)
            if path in seen:
                raise ValueError("同一实体本轮只能变化一次：" + "/".join(path))
            seen.add(path)
            if (
                not change.subcategory.strip()
                or not change.subject.strip()
                or not change.reason.strip()
            ):
                raise ValueError("子类、subject 和 reason 都不能为空")
            _require_value(change.value, allow_empty=change.op == "update")
            if change.op == "update":
                self._validate_update(change)
            else:
                self._validate_create(change)

    def _validate_update(self, change: PlannedChange) -> None:
        chain = _find_chain(
            self.planning_state.states,
            change.domain,
            change.subcategory,
            change.subject,
        )
        if chain is None:
            raise ValueError(
                "update 的实体不存在："
                + "/".join((change.domain, change.subcategory, change.subject))
            )
        if change.mutable != chain.mutable:
            raise ValueError(
                "update 必须沿用该实体当前的 mutable："
                + "/".join((change.domain, change.subcategory, change.subject))
            )
        if not chain.mutable:
            raise ValueError(
                "不可变实体不能更新："
                + "/".join((change.domain, change.subcategory, change.subject))
            )
        if not chain.versions or change.value == chain.versions[-1].value:
            raise ValueError(
                "update 的 value 必须不同于当前 value："
                + "/".join((change.domain, change.subcategory, change.subject))
            )

    def _validate_create(self, change: PlannedChange) -> None:
        code = _domain_code(change.domain)
        allowed = CATEGORY_MAP.get(code or "", [])
        if code is None or change.subcategory not in allowed:
            raise ValueError(f"{change.subcategory} 不是 {change.domain} 的合法子类")
        existing = _find_chain(
            self.planning_state.states,
            change.domain,
            change.subcategory,
            change.subject,
        )
        if existing is not None:
            raise ValueError(
                "create 的实体已经存在："
                + "/".join((change.domain, change.subcategory, change.subject))
            )

    def _apply_changes(self, plan: RoundPlan) -> PlanningState:
        updated = self.planning_state.model_copy(deep=True)
        next_round_id = _next_round_id(updated.round_id)
        created_version = _version_number(next_round_id)
        for change in plan.changes:
            if change.op == "update":
                chain = _find_chain(
                    updated.states,
                    change.domain,
                    change.subcategory,
                    change.subject,
                )
                if chain is None:
                    raise ValueError(
                        "update 的实体不存在："
                        + "/".join((change.domain, change.subcategory, change.subject))
                    )
                last = chain.versions[-1]
                chain.versions.append(
                    StateVersion(
                        version=last.version + 1,
                        round_id=next_round_id,
                        op="update",
                        value=change.value,
                        reason=change.reason,
                    )
                )
            else:
                updated.states.append(
                    StateChain(
                        domain=change.domain,
                        subcategory=change.subcategory,
                        subject=change.subject,
                        mutable=change.mutable,
                        versions=[
                            StateVersion(
                                version=created_version,
                                round_id=next_round_id,
                                op="create",
                                value=change.value,
                                reason=change.reason,
                            )
                        ],
                    )
                )
        updated.round_id = next_round_id
        self.planning_state = updated
        return updated

    def _domain_payload(self, domain: str) -> dict[str, object]:
        code = _domain_code(domain)
        definition = DOMAIN_DEFINITIONS.get(code or "", {})
        current_subjects = []
        for chain in self.planning_state.states:
            if chain.domain != domain or not chain.versions:
                continue
            latest = chain.versions[-1]
            record = {
                "version": latest.version,
                "round_id": latest.round_id,
                "op": latest.op,
                "value": latest.value,
            }
            if latest.reason:
                record["reason"] = latest.reason
            if latest.event_id:
                record["event_id"] = latest.event_id
            current_subjects.append(
                {
                    "subcategory": chain.subcategory,
                    "subject": chain.subject,
                    "mutable": chain.mutable,
                    "version": record,
                }
            )
        return {
            "domain": domain,
            "name": definition.get("name", domain),
            "subcategories": _subcategory_guide(code),
            "current_subjects": current_subjects,
        }


if __name__ == "__main__":
    client = LLMClient(model="gpt-5.4")
    profile_path = DEFAULT_PERSON_DIR / "P001_v0_profile_data.json"
    output_dir = DEFAULT_PERSON_DIR.parent / "output"
    profile_data = ProfileData.model_validate(load_data(profile_path))
    profile = PersonProfile(profile_data, output_dir, client)
    if not profile.summary_path.exists():
        profile.save_summary(profile.summarize_profile())

    person_id = profile_data.person_id
    round_id = _next_round_id(profile_data.round_id)
    planning_path = TargetState.planning_state_file(output_dir, person_id, round_id)
    target_path = TargetState.target_state_file(output_dir, person_id, round_id)
    if not planning_path.exists() or not target_path.exists():
        planner = TargetState(
            profile,
            PlanningState(person_id="", person_summary="", round_id=profile_data.round_id),
            client,
            output_dir,
        )
        planner.initial_target_state()
        planner.save_round(planner.cumulative_state())

    result = TargetState.load_round(output_dir, person_id, round_id)
    print(planning_path)
    print(target_path)
    print(result.planning_state.model_dump_json(indent=2))
    print(result.target_state.model_dump_json(indent=2))
