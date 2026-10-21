"""人物档案的数据结构与人物摘要生成入口。"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...llm_client import ChatMessage, LLMClient
from .dialogue_prompt import PROFILE_SUMMARY_SYSTEM_PROMPT
from ..utils import load_data, save_data


DEFAULT_PERSON_DIR = Path(__file__).resolve().parents[2] / "data" / "persons"
class ProfileModel(BaseModel):
    """人物档案模型的公共配置。"""

    model_config = ConfigDict(extra="forbid")


class ProfileState(ProfileModel):
    """一条人物状态。subject 固定，value 是会变的那个值。"""

    domain: str
    subcategory: str
    subject: str
    mutable: bool
    value: list[str]


class ProfileData(ProfileModel):
    """一个人物在某个版本下的完整档案。"""

    person_id: str
    round_id: str
    states: list[ProfileState] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_states(self) -> "ProfileData":
        seen: set[tuple[str, str, str]] = set()
        for item in self.states:
            key = (item.domain, item.subcategory, item.subject)
            if key in seen:
                raise ValueError("人物状态重复：" + "/".join(key))
            seen.add(key)
        return self


class PersonProfile:
    """持有当前人物档案、结果目录和模型客户端。"""

    def __init__(
        self,
        profile_data: ProfileData,
        save_dir: str | Path,
        llm_client: LLMClient,
    ) -> None:
        self.profile_data = profile_data
        self.save_dir = Path(save_dir)
        self.llm_client = llm_client
        if self.save_dir.suffix:
            raise ValueError("save_dir 必须是保存文件夹，不是文件路径")

    def profile_record(self) -> tuple[dict, str]:
        """返回档案数据和版本号。"""
        record = self.profile_data.model_dump(mode="json")
        return record, record["round_id"]

    @property
    def profile_data_path(self) -> Path:
        """人物档案文件：{person_id}_{round_id}_profile_data.json。"""
        data = self.profile_data
        filename = f"{data.person_id}_{data.round_id}_profile_data.json"
        return self.save_dir / filename

    def save_profile(self) -> ProfileData:
        """把当前人物档案对象写入 JSON。"""
        save_data(self.profile_data_path, self.profile_data.model_dump(mode="json"))
        return self.profile_data

    @property
    def summary_path(self) -> Path:
        """人物摘要文件：{person_id}_{round_id}_person_profile.txt。"""
        record, version = self.profile_record()
        filename = f"{record['person_id']}_{version}_person_profile.txt"
        return self.save_dir / filename

    def load_summary(self) -> str:
        """读取本轮人物摘要。"""
        summary = load_data(self.summary_path)
        if not isinstance(summary, str):
            raise ValueError("人物摘要必须是文本")
        return summary.strip()

    def summarize_profile(self) -> str:
        """根据当前人物档案生成摘要。"""
        record, _version = self.profile_record()
        messages = [
            ChatMessage.system(PROFILE_SUMMARY_SYSTEM_PROMPT),
            ChatMessage.user(json.dumps(record, ensure_ascii=False)),
        ]
        return self.llm_client.chat(messages).strip()

    def save_summary(self, summary: str) -> str:
        """把人物摘要写入结果目录。"""
        save_data(self.summary_path, summary)
        return summary


if __name__ == "__main__":
    client = LLMClient(model="gpt-5.4")
    profile_path = DEFAULT_PERSON_DIR / "P001_v0_profile_data.json"
    output_dir = DEFAULT_PERSON_DIR.parent / "output"
    profile_data = ProfileData.model_validate(load_data(profile_path))
    profile = PersonProfile(profile_data, output_dir, client)
    profile.save_profile()
    summary = profile.save_summary(profile.summarize_profile())
    print(profile.summary_path)
    print(summary)

