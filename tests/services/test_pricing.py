"""Unit tests — app.services.pricing（租金科學定價 + 議價戰術）。"""

from __future__ import annotations

import pytest

from app.models.constants import (
    FINAL_OFFER_DEFAULT_DISCOUNT,
    FINAL_OFFER_DEFAULT_ROUNDOFF_WAN,
    NEGOTIATION_ANCHOR_DISCOUNT,
    NEGOTIATION_KILL_SHOT_DISCOUNT,
)
from app.models.tenant import RentalPricingInput, RentalPricingResult
from app.services.pricing import (
    VacancyStepdownTiers,
    calculate_rental_pricing,
    final_offer_wan,
    negotiation_anchor_unit_wan,
    negotiation_kill_shot_unit_wan,
    vacancy_stepdown_prices,
)


pytestmark = [pytest.mark.services]


# ============================================================
# calculate_rental_pricing — 滿租定價公式
# ============================================================
class TestCalculateRentalPricing:
    def test_baseline_neutral_coefficients(self) -> None:
        """1200 元/坪 × 25 坪 × 3-5 樓 (1.0) × 5-10 年 (1.0) = 30,000。"""
        result = calculate_rental_pricing(RentalPricingInput(
            avg_rent_per_ping_ntd=1200,
            ping_size=25.0,
            floor_label="3-5 樓",
            age_label="5-10 年",
        ))
        assert isinstance(result, RentalPricingResult)
        assert result.base_rent_ntd == 30_000
        assert result.floor_coef == 1.0
        assert result.age_coef == 1.0
        assert result.suggested_rent_ntd == 30_000

    def test_best_case_uplift_132_percent(self) -> None:
        """6 樓以上 (1.1) × 5 年內 (1.2) = 1.32 倍加成。"""
        result = calculate_rental_pricing(RentalPricingInput(
            avg_rent_per_ping_ntd=1000,
            ping_size=20.0,
            floor_label="6 樓以上",
            age_label="5 年內",
        ))
        assert result.base_rent_ntd == 20_000
        assert result.floor_coef == 1.1
        assert result.age_coef == 1.2
        assert result.suggested_rent_ntd == pytest.approx(26_400)

    def test_worst_case_discount_72_percent(self) -> None:
        """1-2 樓 (0.9) × 10 年以上 (0.8) = 0.72 倍折扣。"""
        result = calculate_rental_pricing(RentalPricingInput(
            avg_rent_per_ping_ntd=1000,
            ping_size=20.0,
            floor_label="1-2 樓",
            age_label="10 年以上",
        ))
        assert result.suggested_rent_ntd == pytest.approx(14_400)

    def test_unknown_floor_label_raises_keyerror(self) -> None:
        """文件化的 KeyError 行為，呼叫端應使用 SSOT keys。"""
        with pytest.raises(KeyError):
            calculate_rental_pricing(RentalPricingInput(
                avg_rent_per_ping_ntd=1200,
                ping_size=25.0,
                floor_label="99 樓",  # 不在 FLOOR_COEFFICIENT_MAP
                age_label="5-10 年",
            ))


# ============================================================
# vacancy_stepdown_prices — 空租階梯式降價
# ============================================================
class TestVacancyStepdownPrices:
    def test_returns_named_tuple_with_three_tiers(self) -> None:
        tiers = vacancy_stepdown_prices(30_000)
        assert isinstance(tiers, VacancyStepdownTiers)
        assert tiers.step1_5pct_off == pytest.approx(28_500)
        assert tiers.step2_8pct_off == pytest.approx(27_600)
        assert tiers.floor_15pct_off == pytest.approx(25_500)

    def test_tiers_strictly_decreasing(self) -> None:
        """step1 > step2 > floor 必須嚴格遞減。"""
        tiers = vacancy_stepdown_prices(50_000)
        assert tiers.step1_5pct_off > tiers.step2_8pct_off > tiers.floor_15pct_off

    def test_zero_input_yields_zero_tiers(self) -> None:
        tiers = vacancy_stepdown_prices(0)
        assert tiers == VacancyStepdownTiers(0.0, 0.0, 0.0)


# ============================================================
# 議價三戰術 — 單元測試
# ============================================================
class TestNegotiationTactics:
    @pytest.mark.parametrize(
        ("ad_unit", "expected_anchor", "expected_kill"),
        [
            (50.0, 47.5, 45.0),
            (100.0, 95.0, 90.0),
            (0.0, 0.0, 0.0),
        ],
    )
    def test_anchor_and_kill_shot_ladder(
        self, ad_unit: float, expected_anchor: float, expected_kill: float,
    ) -> None:
        """kill_shot (-10%) < anchor (-5%) < ad_unit — 嚴格遞減。"""
        anchor = negotiation_anchor_unit_wan(ad_unit)
        kill = negotiation_kill_shot_unit_wan(ad_unit)
        assert anchor == pytest.approx(expected_anchor)
        assert kill == pytest.approx(expected_kill)
        if ad_unit > 0:
            assert kill < anchor < ad_unit

    def test_multiplier_constants_match_doc(self) -> None:
        """確認 module constants 未被誤改。"""
        assert NEGOTIATION_ANCHOR_DISCOUNT == 0.95
        assert NEGOTIATION_KILL_SHOT_DISCOUNT == 0.90


class TestFinalOfferWan:
    def test_default_recipe(self) -> None:
        """預設：開價 × 0.85 − 50 萬零頭。"""
        # 1500 × 0.85 = 1275，− 50 = 1225
        assert final_offer_wan(1500.0) == pytest.approx(1225.0)

    def test_non_negative_guard(self) -> None:
        """開價過小導致扣零頭後負數 → clamp 至 0。"""
        # 40 × 0.85 = 34，− 50 = −16 → clamp 0
        assert final_offer_wan(40.0) == 0.0

    def test_zero_asking_price(self) -> None:
        assert final_offer_wan(0.0) == 0.0

    def test_custom_discount_and_roundoff(self) -> None:
        """支援呼叫端自訂折扣與零頭金額。"""
        # 1000 × 0.90 = 900，− 30 = 870
        result = final_offer_wan(1000.0, discount=0.90, final_round_off_wan=30.0)
        assert result == pytest.approx(870.0)

    def test_default_constants_unchanged(self) -> None:
        assert FINAL_OFFER_DEFAULT_DISCOUNT == 0.85
        assert FINAL_OFFER_DEFAULT_ROUNDOFF_WAN == 50.0
