"""OpenAI Chat Completions API 包裝（Repository 層）。

職責：
    將外部 `openai` SDK 隔離在本模組；
    UI / Service 透過 ``AIConfig`` + ``list[ChatMessage]`` 介面互動，
    不需要知道 SDK 內部結構或 chunk 形狀。

例外策略：
    - ``ImportError``（openai 套件缺失）→ 翻譯為 ``RuntimeError``（含安裝指引）
    - 連線層錯誤（``RateLimitError`` / ``APIConnectionError``）→ 自動重試
      （指數退避，最多 ``OPENAI_MAX_RETRIES`` 次）
    - 其他 OpenAI 例外（``AuthenticationError`` 等）→ 直接 propagate

Token 用量追蹤：
    ``stream_chat_completion`` 回傳 ``UsageTrackingStream``，呼叫端迭代完成後
    可讀 ``.usage`` 屬性取得 ``TokenUsage``（input/output/total tokens）。

層架構規則：
    本模組屬 repository 層，**允許** import openai SDK，
    但**嚴禁**呼叫任何 streamlit UI 渲染函式。
"""

from __future__ import annotations

import time
from typing import Any, Iterator

from app.models.ai import AIConfig, ChatMessage, TokenUsage
from app.models.constants import OPENAI_MAX_RETRIES, OPENAI_RETRY_BASE_DELAY_SECONDS


class UsageTrackingStream:
    """OpenAI 串流的 iterable 包裝，迭代完成後在 ``.usage`` 暴露 token 用量。

    OpenAI SDK 啟用 ``stream_options={"include_usage": True}`` 後，
    最後一個 chunk 會帶 ``chunk.usage``；本 class 在迭代過程中擷取並保留。

    Note: ``.usage`` 在迭代未完成前固定為 ``None``。
    """

    def __init__(self, raw_stream: Iterator[Any]) -> None:
        self._raw = raw_stream
        self._usage: TokenUsage | None = None

    def __iter__(self) -> Iterator[str]:
        for chunk in self._raw:
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                delta = None
            if delta:
                yield delta
            # 最終 chunk 可能帶 usage（其他 chunks usage 為 None）
            usage_attr = getattr(chunk, "usage", None)
            if usage_attr is not None and self._usage is None:
                try:
                    self._usage = TokenUsage(
                        input_tokens=int(usage_attr.prompt_tokens),
                        output_tokens=int(usage_attr.completion_tokens),
                        total_tokens=int(usage_attr.total_tokens),
                    )
                except (AttributeError, TypeError):
                    # SDK 變動或 mock object 缺欄位 → 靜默忽略
                    pass

    @property
    def usage(self) -> TokenUsage | None:
        """迭代完成後可取得；尚未完成或未啟用 include_usage 時為 ``None``。"""
        return self._usage


def stream_chat_completion(
    config: AIConfig, messages: list[ChatMessage],
) -> UsageTrackingStream:
    """以串流模式取得 chat completion，回傳可迭代的 ``UsageTrackingStream``。

    Args:
        config:   AI 設定（api_key / model / temperature）
        messages: 對話歷史 DTO 序列（含 system prompt 由呼叫端置首）

    Returns:
        ``UsageTrackingStream`` — 迭代會 yield 每個 content delta；
        迭代完成後可讀 ``.usage`` 屬性。

    Raises:
        RuntimeError: openai 套件未安裝。
        openai.OpenAIError 及其子類: API 連線 / 認證 / 速率限制等錯誤
            （RateLimitError / APIConnectionError 已自動重試 ``OPENAI_MAX_RETRIES``
            次仍失敗才會 propagate）。
    """
    try:
        from openai import OpenAI
        from openai import APIConnectionError, RateLimitError
    except ImportError as exc:
        raise RuntimeError(
            "openai 套件未安裝；請執行 `pip install openai>=1.0`，"
            "或將 openai>=1.0 加入 requirements.txt 後重啟服務。"
        ) from exc

    client = OpenAI(api_key=config.api_key)
    payload = dict(
        model=config.model,
        messages=[m.to_openai_dict() for m in messages],
        temperature=config.temperature,
        stream=True,
        stream_options={"include_usage": True},
    )

    last_exc: Exception | None = None
    for attempt in range(OPENAI_MAX_RETRIES + 1):
        try:
            raw_stream = client.chat.completions.create(**payload)  # type: ignore[arg-type, call-overload]
            return UsageTrackingStream(raw_stream)
        except (RateLimitError, APIConnectionError) as exc:
            last_exc = exc
            if attempt >= OPENAI_MAX_RETRIES:
                raise
            time.sleep(OPENAI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))

    # 不應到達；for-loop 內已 return 或 raise
    raise RuntimeError("retry loop exited unexpectedly") from last_exc


def _yield_content_chunks(stream: Iterator[Any]) -> Iterator[str]:
    """純函式版本的 chunk 解析（供 unit test 直接呼叫，不需 OpenAI 連線）。

    對下列退化 chunk 形狀採『靜默略過』：
        - choices 為空 list（IndexError）
        - choices[0].delta 為 None（AttributeError）
        - delta.content 為 None / 空字串（falsy 過濾）
    """
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except (IndexError, AttributeError):
            delta = None
        if delta:
            yield delta
