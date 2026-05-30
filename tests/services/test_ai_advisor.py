"""Unit tests — app.services.ai_advisor（對話編排 + persona prompt）。

ai_advisor 不直接接任何 SDK；OpenAI / Gemini 互動分別由
``repositories.openai_client`` 與 ``repositories.gemini_client`` 負責。
本測試模組 monkey-patch 兩個 repository 的 ``stream_chat_completion``
把整個 SDK 鏈路切斷，專注驗證 service 自己的編排邏輯。
"""

from __future__ import annotations

import pytest

from app.models.ai import (
    AIConfig,
    AIProvider,
    ChatMessage,
    ChatRole,
    TokenUsage,
    UsageStats,
)
from app.repositories import gemini_client, openai_client
from app.services.ai_advisor import (
    MENTOR_SYSTEM_PROMPT,
    accumulate_usage,
    build_message_chain,
    estimate_cost_usd,
    is_within_spend_cap,
    stream_mentor_reply,
)


pytestmark = [pytest.mark.services]


# ============================================================
# build_message_chain — 純函式 prepend SYSTEM
# ============================================================
class TestBuildMessageChain:
    def test_empty_history_yields_system_only(self) -> None:
        chain = build_message_chain([])
        assert len(chain) == 1
        assert chain[0].role == ChatRole.SYSTEM
        assert chain[0].content == MENTOR_SYSTEM_PROMPT

    def test_with_history_preserves_order(self) -> None:
        u1 = ChatMessage(ChatRole.USER, "學長，DTI 60% 可以買嗎？")
        a1 = ChatMessage(ChatRole.ASSISTANT, "可以，但要看你的壞債佔比。")
        u2 = ChatMessage(ChatRole.USER, "我有 2 萬車貸。")
        chain = build_message_chain([u1, a1, u2])
        assert len(chain) == 4
        assert chain[0].role == ChatRole.SYSTEM
        assert chain[1] is u1
        assert chain[2] is a1
        assert chain[3] is u2

    def test_does_not_mutate_caller_list(self) -> None:
        """frozen dataclass + 新 list 回傳 — caller history 不該被改。"""
        history = [ChatMessage(ChatRole.USER, "hello")]
        original_id = id(history)
        original_len = len(history)
        build_message_chain(history)
        assert id(history) == original_id
        assert len(history) == original_len


# ============================================================
# MENTOR_SYSTEM_PROMPT — 內容守則
# ============================================================
class TestMentorSystemPrompt:
    def test_prompt_is_nonempty(self) -> None:
        assert len(MENTOR_SYSTEM_PROMPT) > 500

    @pytest.mark.parametrize(
        "keyword",
        ["學長", "DTI", "履約保證", "M2", "科目四", "學弟"],
    )
    def test_contains_core_keywords(self, keyword: str) -> None:
        """系統提示語必須提到核心 persona / 鐵律字眼。"""
        assert keyword in MENTOR_SYSTEM_PROMPT


# ============================================================
# stream_mentor_reply — 串流委派（mock OpenAI / Gemini repository）
# ============================================================
class TestStreamMentorReply:
    def test_returns_iterable(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """stream_mentor_reply 委派給 repository，回傳物件需可被迭代。"""
        monkeypatch.setattr(
            openai_client, "stream_chat_completion",
            lambda c, m: iter(["chunk1", "chunk2"]),
        )
        result = stream_mentor_reply(AIConfig(api_key="sk-test"), [])
        assert hasattr(result, "__iter__")
        assert list(result) == ["chunk1", "chunk2"]

    def test_generator_creation_is_lazy(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """建立 generator 不該立刻呼叫 OpenAI（lazy evaluation）。"""
        called: list[bool] = []

        def fake_stream(config, messages):  # type: ignore[no-untyped-def]
            called.append(True)
            yield "x"

        monkeypatch.setattr(openai_client, "stream_chat_completion", fake_stream)
        gen = stream_mentor_reply(AIConfig(api_key="sk-test"), [])
        assert called == []  # 未消費 generator 前不該觸發
        next(gen)
        assert called == [True]

    def test_yields_chunks_from_repository(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """確認 yield 的內容來自 repository.stream_chat_completion。"""
        captured_chain: list[ChatMessage] = []

        def fake_stream(config, messages):  # type: ignore[no-untyped-def]
            captured_chain.extend(messages)
            yield "Hello"
            yield ", "
            yield "world!"

        monkeypatch.setattr(openai_client, "stream_chat_completion", fake_stream)
        cfg = AIConfig(api_key="sk-test")
        user_msg = ChatMessage(ChatRole.USER, "test")
        result = list(stream_mentor_reply(cfg, [user_msg]))
        assert result == ["Hello", ", ", "world!"]
        # repository 收到的 messages 應該是 [SYSTEM, USER]
        assert len(captured_chain) == 2
        assert captured_chain[0].role == ChatRole.SYSTEM
        assert captured_chain[1] == user_msg

    def test_passes_config_through(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AIConfig 原型傳遞給 repository（model / temperature / api_key）。"""
        seen_configs: list[AIConfig] = []

        def fake_stream(config, messages):  # type: ignore[no-untyped-def]
            seen_configs.append(config)
            yield ""

        monkeypatch.setattr(openai_client, "stream_chat_completion", fake_stream)
        cfg = AIConfig(api_key="sk-test", model="gpt-4o", temperature=0.3)
        list(stream_mentor_reply(cfg, []))
        assert len(seen_configs) == 1
        assert seen_configs[0] is cfg

    def test_exception_propagates(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """repository 拋的例外應該原型 propagate（不該被 service 吞掉）。"""
        class FakeRateLimitError(Exception):
            pass

        def fake_stream(config, messages):  # type: ignore[no-untyped-def]
            raise FakeRateLimitError("rate limit hit")
            yield  # pragma: no cover  (生成器需要 yield 才算 generator)

        monkeypatch.setattr(openai_client, "stream_chat_completion", fake_stream)
        with pytest.raises(FakeRateLimitError, match="rate limit"):
            list(stream_mentor_reply(AIConfig(api_key="sk-test"), []))

    def test_dispatches_to_gemini_when_provider_is_gemini(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """config.provider=GEMINI 時應走 gemini_client，不該碰 openai_client。"""
        openai_calls: list[bool] = []
        gemini_calls: list[bool] = []

        def fake_openai(config, messages):  # type: ignore[no-untyped-def]
            openai_calls.append(True)
            yield "from-openai"

        def fake_gemini(config, messages):  # type: ignore[no-untyped-def]
            gemini_calls.append(True)
            yield "from-gemini"

        monkeypatch.setattr(openai_client, "stream_chat_completion", fake_openai)
        monkeypatch.setattr(gemini_client, "stream_chat_completion", fake_gemini)

        cfg = AIConfig(
            api_key="AIzaSy-test",
            model="gemini-2.5-flash",
            provider=AIProvider.GEMINI,
        )
        result = list(stream_mentor_reply(cfg, []))
        assert result == ["from-gemini"]
        assert gemini_calls == [True]
        assert openai_calls == []  # OpenAI repo 不該被觸發

    def test_dispatches_to_openai_by_default(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未指定 provider 時應走 OpenAI（向後相容預設值）。"""
        openai_calls: list[bool] = []
        gemini_calls: list[bool] = []

        monkeypatch.setattr(
            openai_client, "stream_chat_completion",
            lambda c, m: (openai_calls.append(True), iter(["x"]))[1],
        )
        monkeypatch.setattr(
            gemini_client, "stream_chat_completion",
            lambda c, m: (gemini_calls.append(True), iter(["x"]))[1],
        )

        list(stream_mentor_reply(AIConfig(api_key="sk-test"), []))
        assert openai_calls == [True]
        assert gemini_calls == []


# ============================================================
# estimate_cost_usd — 成本計算純函式
# ============================================================
class TestEstimateCostUsd:
    def test_gpt_4o_mini_pricing(self) -> None:
        """gpt-4o-mini: $0.15/M input, $0.60/M output。
        1000 input + 500 output = 0.00015 + 0.00030 = 0.00045 USD。"""
        usage = TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500)
        cost = estimate_cost_usd(usage, "gpt-4o-mini")
        assert cost == pytest.approx(0.00045, abs=1e-9)

    def test_gpt_4o_pricing(self) -> None:
        """gpt-4o: $2.50/M input, $10.00/M output。
        1000 input + 500 output = 0.0025 + 0.005 = 0.0075 USD。"""
        usage = TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500)
        cost = estimate_cost_usd(usage, "gpt-4o")
        assert cost == pytest.approx(0.0075, abs=1e-9)

    def test_zero_tokens_zero_cost(self) -> None:
        usage = TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)
        assert estimate_cost_usd(usage, "gpt-4o-mini") == 0.0

    def test_unknown_model_raises_keyerror(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        with pytest.raises(KeyError):
            estimate_cost_usd(usage, "fake-model-name")

    def test_gemini_flash_pricing(self) -> None:
        """gemini-2.5-flash: $0.30/M input, $2.50/M output (paid-tier rate)。
        1000 input + 500 output = 0.0003 + 0.00125 = 0.00155 USD。"""
        usage = TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500)
        cost = estimate_cost_usd(usage, "gemini-2.5-flash", AIProvider.GEMINI)
        assert cost == pytest.approx(0.00155, abs=1e-9)

    def test_gemini_unknown_model_raises_keyerror(self) -> None:
        """provider=GEMINI 但 model 在 GEMINI 單價表外應拋 KeyError。"""
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        with pytest.raises(KeyError):
            estimate_cost_usd(usage, "gpt-4o-mini", AIProvider.GEMINI)

    def test_provider_routing_isolated(self) -> None:
        """同樣的 model 字串若搭配錯誤 provider 不該誤抓對方單價表。"""
        usage = TokenUsage(input_tokens=1000, output_tokens=0, total_tokens=1000)
        # gpt-4o-mini 只在 OPENAI 表，不在 GEMINI 表
        with pytest.raises(KeyError):
            estimate_cost_usd(usage, "gpt-4o-mini", AIProvider.GEMINI)
        # gemini-2.5-flash 只在 GEMINI 表，不在 OPENAI 表
        with pytest.raises(KeyError):
            estimate_cost_usd(usage, "gemini-2.5-flash", AIProvider.OPENAI)


# ============================================================
# accumulate_usage — 累計統計
# ============================================================
class TestAccumulateUsage:
    def test_first_call_from_zero_stats(self) -> None:
        stats = UsageStats()  # 全部 0
        usage = TokenUsage(1000, 500, 1500)
        new_stats = accumulate_usage(stats, usage, "gpt-4o-mini")
        assert new_stats.total_input_tokens == 1000
        assert new_stats.total_output_tokens == 500
        assert new_stats.call_count == 1
        assert new_stats.total_cost_usd == pytest.approx(0.00045)

    def test_second_call_accumulates(self) -> None:
        stats = UsageStats(
            total_input_tokens=500, total_output_tokens=200,
            total_cost_usd=0.001, call_count=1,
        )
        usage = TokenUsage(1000, 500, 1500)
        new_stats = accumulate_usage(stats, usage, "gpt-4o-mini")
        assert new_stats.total_input_tokens == 1500
        assert new_stats.total_output_tokens == 700
        assert new_stats.call_count == 2
        # 0.001 + 0.00045 = 0.00145
        assert new_stats.total_cost_usd == pytest.approx(0.00145)

    def test_returns_new_instance_not_mutates(self) -> None:
        """frozen dataclass: 不可變更新，回傳新實例。"""
        stats = UsageStats(total_input_tokens=100)
        new_stats = accumulate_usage(stats, TokenUsage(1, 1, 2), "gpt-4o-mini")
        assert stats.total_input_tokens == 100  # 原 stats 不變
        assert new_stats is not stats

    def test_total_tokens_property(self) -> None:
        stats = UsageStats(total_input_tokens=300, total_output_tokens=200)
        assert stats.total_tokens == 500

    def test_gemini_provider_uses_gemini_pricing(self) -> None:
        """accumulate_usage 傳 provider=GEMINI 時走 Gemini 單價表。"""
        stats = UsageStats()
        usage = TokenUsage(1000, 500, 1500)
        new_stats = accumulate_usage(
            stats, usage, "gemini-2.5-flash", AIProvider.GEMINI,
        )
        # 0.30/M * 1000 + 2.50/M * 500 = 0.0003 + 0.00125 = 0.00155
        assert new_stats.total_cost_usd == pytest.approx(0.00155, abs=1e-9)
        assert new_stats.call_count == 1


# ============================================================
# is_within_spend_cap — 預算上限檢查
# ============================================================
class TestIsWithinSpendCap:
    def test_below_cap(self) -> None:
        stats = UsageStats(total_cost_usd=0.50)
        assert is_within_spend_cap(stats, 1.0) is True

    def test_at_cap_exactly(self) -> None:
        """剛好達到 cap → 視為超過（嚴格 `<`）。"""
        stats = UsageStats(total_cost_usd=1.0)
        assert is_within_spend_cap(stats, 1.0) is False

    def test_over_cap(self) -> None:
        stats = UsageStats(total_cost_usd=2.5)
        assert is_within_spend_cap(stats, 1.0) is False

    @pytest.mark.parametrize("cap", [0.0, -1.0, -100.0])
    def test_zero_or_negative_cap_means_unlimited(self, cap: float) -> None:
        """cap ≤ 0 視為『無上限』，永遠 within。"""
        stats = UsageStats(total_cost_usd=999.0)
        assert is_within_spend_cap(stats, cap) is True
