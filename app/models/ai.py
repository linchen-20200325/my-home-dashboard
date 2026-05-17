"""AI 顧問對話 DTO（Ch.9 主要使用）。

注意：本模組僅定義資料型別，**不**依賴 openai SDK。
OpenAI 呼叫由 `app/repositories/openai_client.py` 負責。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.constants import (
    OPENAI_DEFAULT_MODEL,
    OPENAI_DEFAULT_TEMPERATURE,
)


class ChatRole(str, Enum):
    """OpenAI chat completion 的三種角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """單則對話訊息（不可變）。"""

    role: ChatRole
    content: str

    def to_openai_dict(self) -> dict[str, str]:
        """轉成 OpenAI SDK 期望的 dict 形狀。"""
        return {"role": self.role.value, "content": self.content}


@dataclass(frozen=True)
class AIConfig:
    """AI 呼叫設定。

    api_key 為空字串 → repository 層應視為『尚未提供』並拒絕呼叫。
    """

    api_key: str
    model: str = OPENAI_DEFAULT_MODEL
    temperature: float = OPENAI_DEFAULT_TEMPERATURE

    @property
    def is_ready(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(frozen=True)
class TokenUsage:
    """單次 chat completion 的 token 用量（從 OpenAI 串流末尾擷取）。"""

    input_tokens: int
    output_tokens: int
    total_tokens: int  # OpenAI API 給的總值（通常 = input + output）


@dataclass(frozen=True)
class UsageStats:
    """跨多次呼叫的累計用量與成本。所有 service 純函式以本型別操作。"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens
