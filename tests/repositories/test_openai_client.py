"""Unit tests — app.repositories.openai_client（OpenAI 串流包裝 + retry + usage）。

不仰賴實際 OpenAI SDK：
    - `_yield_content_chunks` + `UsageTrackingStream` 用 SimpleNamespace 模擬 chunk
    - `stream_chat_completion` 對 ImportError 翻譯為 RuntimeError 的測試，
      用 sys.meta_path 真的封鎖 openai import
    - retry 邏輯透過 monkey-patch openai.RateLimitError + 計數重試次數
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.models.ai import AIConfig, ChatMessage, ChatRole
from app.repositories.openai_client import (
    UsageTrackingStream,
    _yield_content_chunks,
    stream_chat_completion,
)


pytestmark = [pytest.mark.repositories]


# ============================================================
# Chunk helpers
# ============================================================
def _content_chunk(content):
    """Mock chunk with content delta only (no usage)."""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
        usage=None,
    )


def _usage_chunk(input_tokens: int, output_tokens: int):
    """Mock final chunk that carries token usage info."""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


# ============================================================
# _yield_content_chunks — 舊版純函式仍保留供單測
# ============================================================
class TestYieldContentChunks:
    def test_standard_chunks_join(self) -> None:
        stream = iter([_content_chunk("Hello"), _content_chunk(", "), _content_chunk("world!")])
        assert "".join(_yield_content_chunks(stream)) == "Hello, world!"

    def test_none_content_filtered(self) -> None:
        stream = iter([_content_chunk("ok"), _content_chunk(None), _content_chunk(" hi")])
        assert list(_yield_content_chunks(stream)) == ["ok", " hi"]

    def test_empty_string_filtered(self) -> None:
        stream = iter([_content_chunk("a"), _content_chunk(""), _content_chunk("b")])
        assert list(_yield_content_chunks(stream)) == ["a", "b"]

    def test_empty_choices_skipped(self) -> None:
        empty = SimpleNamespace(choices=[])
        stream = iter([empty, _content_chunk("after")])
        assert list(_yield_content_chunks(stream)) == ["after"]

    def test_delta_none_skipped(self) -> None:
        no_delta = SimpleNamespace(choices=[SimpleNamespace(delta=None)])
        stream = iter([no_delta, _content_chunk("after")])
        assert list(_yield_content_chunks(stream)) == ["after"]


# ============================================================
# UsageTrackingStream — content + usage 一起追蹤
# ============================================================
class TestUsageTrackingStream:
    def test_yields_content_and_captures_usage(self) -> None:
        chunks = [
            _content_chunk("Hello"),
            _content_chunk(", "),
            _content_chunk("world!"),
            _usage_chunk(input_tokens=100, output_tokens=50),
        ]
        stream = UsageTrackingStream(iter(chunks))
        result = list(stream)
        assert result == ["Hello", ", ", "world!"]
        assert stream.usage is not None
        assert stream.usage.input_tokens == 100
        assert stream.usage.output_tokens == 50
        assert stream.usage.total_tokens == 150

    def test_usage_none_before_iteration(self) -> None:
        stream = UsageTrackingStream(iter([_content_chunk("x")]))
        assert stream.usage is None  # 尚未迭代

    def test_usage_none_when_no_usage_chunk(self) -> None:
        """沒有最終 usage chunk（例如未啟用 include_usage） → usage 保持 None。"""
        stream = UsageTrackingStream(iter([_content_chunk("a"), _content_chunk("b")]))
        list(stream)
        assert stream.usage is None

    def test_malformed_usage_chunk_silently_ignored(self) -> None:
        """usage 屬性缺欄位（SDK 變動 / mock 殘缺） → 不丟例外。"""
        broken = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=100),  # 缺 completion_tokens
        )
        stream = UsageTrackingStream(iter([_content_chunk("ok"), broken]))
        list(stream)
        assert stream.usage is None  # 解析失敗，靜默


# ============================================================
# stream_chat_completion — ImportError 翻譯
# ============================================================
class _OpenAIBlocker:
    def find_module(self, name, path=None):  # type: ignore[no-untyped-def]
        if name == "openai" or name.startswith("openai."):
            return self
        return None

    def load_module(self, name):  # type: ignore[no-untyped-def]
        raise ImportError(f"mocked: {name} not installed")


@pytest.fixture
def block_openai():
    saved_modules = {
        k: sys.modules.pop(k) for k in list(sys.modules)
        if k == "openai" or k.startswith("openai.")
    }
    blocker = _OpenAIBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved_modules)


class TestStreamChatCompletionImportError:
    @pytest.mark.boundary
    def test_missing_openai_raises_runtime_error_with_hint(
        self, block_openai,
    ) -> None:
        """openai 套件未安裝 → 翻譯為 RuntimeError + 友善安裝指引。

        與舊版差異：stream_chat_completion 不再是 generator，
        直接呼叫即會 raise（不需先 next）。
        """
        cfg = AIConfig(api_key="sk-test")
        with pytest.raises(RuntimeError) as exc_info:
            stream_chat_completion(cfg, [ChatMessage(ChatRole.USER, "hi")])
        assert "openai" in str(exc_info.value).lower()
        assert isinstance(exc_info.value.__cause__, ImportError)


# ============================================================
# Retry logic — RateLimitError / APIConnectionError
# ============================================================
class TestRetryLogic:
    """模擬 openai 拋暫時性錯誤，驗證 repository 自動重試。"""

    @pytest.fixture
    def fake_openai_module(self, monkeypatch):
        """提供假的 openai module，可控制 create() 的行為。"""
        import types

        # 計數器與 behavior config
        call_log: list[int] = []
        behavior: dict = {"errors_then": 0, "exc_type": None}

        class FakeRateLimitError(Exception):
            pass

        class FakeAPIConnectionError(Exception):
            pass

        class FakeCompletions:
            def create(self, **kwargs):
                call_log.append(1)
                if len(call_log) <= behavior["errors_then"]:
                    raise behavior["exc_type"]("transient failure")
                # 成功：回傳一個簡單的 iterable
                return iter([_content_chunk("done")])

        class FakeChat:
            completions = FakeCompletions()

        class FakeOpenAI:
            def __init__(self, *, api_key):  # type: ignore[no-untyped-def]
                self.chat = FakeChat()

        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = FakeOpenAI  # type: ignore[attr-defined]
        fake_module.RateLimitError = FakeRateLimitError  # type: ignore[attr-defined]
        fake_module.APIConnectionError = FakeAPIConnectionError  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "openai", fake_module)
        # 避免 time.sleep 拖測試
        monkeypatch.setattr("time.sleep", lambda _s: None)
        return {
            "call_log": call_log,
            "behavior": behavior,
            "RateLimitError": FakeRateLimitError,
            "APIConnectionError": FakeAPIConnectionError,
        }

    def test_succeeds_on_first_attempt(self, fake_openai_module) -> None:
        cfg = AIConfig(api_key="sk-test")
        stream = stream_chat_completion(cfg, [ChatMessage(ChatRole.USER, "hi")])
        list(stream)  # 觸發迭代
        assert len(fake_openai_module["call_log"]) == 1

    def test_retries_on_rate_limit_then_succeeds(self, fake_openai_module) -> None:
        """前 2 次 RateLimitError，第 3 次成功 → 應總共呼叫 3 次。"""
        fake_openai_module["behavior"]["errors_then"] = 2
        fake_openai_module["behavior"]["exc_type"] = fake_openai_module["RateLimitError"]

        cfg = AIConfig(api_key="sk-test")
        stream_chat_completion(cfg, [ChatMessage(ChatRole.USER, "hi")])
        assert len(fake_openai_module["call_log"]) == 3

    def test_retries_on_connection_error(self, fake_openai_module) -> None:
        fake_openai_module["behavior"]["errors_then"] = 1
        fake_openai_module["behavior"]["exc_type"] = fake_openai_module["APIConnectionError"]

        cfg = AIConfig(api_key="sk-test")
        stream_chat_completion(cfg, [ChatMessage(ChatRole.USER, "hi")])
        assert len(fake_openai_module["call_log"]) == 2

    def test_propagates_after_max_retries_exceeded(self, fake_openai_module) -> None:
        """超過 MAX_RETRIES (3) 仍失敗 → propagate 原始例外。"""
        fake_openai_module["behavior"]["errors_then"] = 999  # 永遠失敗
        fake_openai_module["behavior"]["exc_type"] = fake_openai_module["RateLimitError"]

        cfg = AIConfig(api_key="sk-test")
        with pytest.raises(fake_openai_module["RateLimitError"]):
            stream_chat_completion(cfg, [ChatMessage(ChatRole.USER, "hi")])
        # 1 initial + 3 retries = 4 total
        assert len(fake_openai_module["call_log"]) == 4
