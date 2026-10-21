import os
from pathlib import Path
from typing import Literal, TypeVar

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import BadRequestError, OpenAI
from pydantic import BaseModel


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)

load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_BASE_URL = (
    "https://aif-dev-qt-jpe-latc01.openai.azure.com/openai/v1"
)
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TOKEN = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )

# 从 .env 读取的备用接口（有值时优先于上面的 Azure 默认）
ENV_BASE_URL = os.getenv("OPENAI_BASE_URL")
ENV_API_KEY = os.getenv("OPENAI_API_KEY")


class ChatMessage(BaseModel):
    """一条系统、用户或助手消息。"""

    role: Literal["system", "user", "assistant"]
    content: str

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)


class LLMClient:
    """Azure OpenAI 的轻量封装。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or os.getenv("AZURE_OPENAI_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(
            base_url=base_url or ENV_BASE_URL or DEFAULT_BASE_URL,
            api_key=api_key or ENV_API_KEY or DEFAULT_TOKEN,
        )

    def chat(self, messages: list[ChatMessage]) -> str:
        """发送一组对话消息。

        示例：
            messages = [
                ChatMessage.system("你是一个人物档案助手"),
                ChatMessage.user("请生成人物档案"),
                ChatMessage.assistant("人物档案已生成"),
                ChatMessage.user("继续生成目标状态"),
            ]
        """
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[message.model_dump() for message in messages],
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("模型返回了空内容")
        return content

    def chat_json(
        self,
        messages: list[ChatMessage],
        response_format: type[ResponseModel],
    ) -> ResponseModel:
        """按指定的 Pydantic 模型生成并校验结构化输出。"""
        payload = [message.model_dump() for message in messages]
        try:
            completion = self._client.chat.completions.parse(
                model=self.model,
                messages=payload,
                response_format=response_format,
            )
        except BadRequestError as error:
            if "response_format" not in str(error):
                raise
            return self._chat_json_object(payload, response_format)

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            refusal = completion.choices[0].message.refusal
            raise ValueError(refusal or "模型未返回有效的结构化内容")
        return parsed

    def _chat_json_object(
        self,
        messages: list[dict[str, str]],
        response_format: type[ResponseModel],
    ) -> ResponseModel:
        """接口不支持 schema 解析时，退回 JSON 对象再做本地校验。"""
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("模型返回了空内容")
        return response_format.model_validate_json(content)

    def embedding(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model="text-embedding-3-large",
            input=texts,
        )
        return [item.embedding for item in response.data]

if __name__ == "__main__":
    class NumberExtraction(BaseModel):
        extracted_number: int

    client = LLMClient(model="gpt-5.4")
    print(client.chat([
        ChatMessage.system("你是一个友好的AI助手"),
        ChatMessage.user("你好"),
        ChatMessage.assistant("你好，有什么可以帮你的吗？"),
        ChatMessage.user("我想知道你的名字"),
    ]))
    # print(client.embedding(["你好", "再见"]))

    number_result = client.chat_json(
        [
            ChatMessage.system("从用户提供的文本中抽取数字"),
            ChatMessage.user("仓库里现在还有 42 个纸箱。"),
        ],
        NumberExtraction,
    )
    print(number_result.model_dump())
