"""Unit tests — app.services.leverage（M2 / 增貸 / 科目四 / 股票質押 / 合資 / 區域紅利）。

Covers 9 純函式 / 4 區塊：
    A. M2 燃料  — simulate_m2_decade + diagnose_m2_regime
    B. 增貸 / 科目四 — calculate_building_gap + diagnose_wash_progress
    C. 股票質押 / 空租 — calculate_stock_pledge + calculate_vacancy_reserve
    D. 合資 / 區域紅利 — calculate_syndication_arbitrage +
       diagnose_syndication_safeguards + diagnose_regional_tailwinds
"""

from __future__ import annotations

import pytest

from app.models.constants import (
    BANK_REFINANCE_LTV,
    M2_INITIAL_CAPITAL_NTD,
    M2_LEVERAGE_MULTIPLIER,
    STOCK_PLEDGE_ANNUAL_RATE,
    STOCK_PLEDGE_LTV,
)
from app.services.leverage import (
    BuildingGapResult,
    M2Regime,
    M2RegimeVerdict,
    M2SimulationResult,
    RegionalGrade,
    RegionalTailwindVerdict,
    SafeguardCompleteness,
    SyndicationArbitrageResult,
    VacancyReserveResult,
    WashProgressVerdict,
    WashStage,
    calculate_building_gap,
    calculate_stock_pledge,
    calculate_syndication_arbitrage,
    calculate_vacancy_reserve,
    diagnose_m2_regime,
    diagnose_regional_tailwinds,
    diagnose_syndication_safeguards,
    diagnose_wash_progress,
    simulate_m2_decade,
)


pytestmark = [pytest.mark.services]


# ============================================================
# A1. simulate_m2_decade — 通膨槓桿模擬
# ============================================================
class TestSimulateM2Decade:
    def test_zero_inflation_yields_no_purchasing_power_decay(self) -> None:
        """通膨 = 0 → real == nominal（購買力因子為 1）。"""
        sim = simulate_m2_decade(0.0)
        assert sim.deposit_real_ntd == pytest.approx(sim.deposit_nominal_ntd)
        assert sim.equity_real_ntd == pytest.approx(sim.equity_nominal_ntd)

    def test_default_5pct_inflation_leverage_beats_deposit(self) -> None:
        """5% 通膨 → 槓桿買房實質購買力勝過定存。"""
        sim = simulate_m2_decade(0.05)
        assert sim.leverage_advantage_ntd > 0
        assert sim.equity_real_ntd > sim.deposit_real_ntd

    def test_higher_inflation_widens_leverage_advantage(self) -> None:
        """通膨越高，槓桿優勢越大（單調遞增）。"""
        low = simulate_m2_decade(0.03)
        mid = simulate_m2_decade(0.07)
        high = simulate_m2_decade(0.12)
        assert low.leverage_advantage_ntd < mid.leverage_advantage_ntd
        assert mid.leverage_advantage_ntd < high.leverage_advantage_ntd

    def test_property_initial_equals_capital_times_leverage(self) -> None:
        sim = simulate_m2_decade(0.05)
        expected = M2_INITIAL_CAPITAL_NTD * M2_LEVERAGE_MULTIPLIER
        assert sim.property_initial_value_ntd == expected

    def test_custom_params_via_kwargs(self) -> None:
        """所有參數都是 keyword-only（防位置誤傳）。"""
        sim = simulate_m2_decade(
            0.05,
            initial_capital_ntd=5_000_000,
            leverage_multiplier=10,
            deposit_annual_rate=0.02,
            years=5,
        )
        assert sim.property_initial_value_ntd == 50_000_000
        # 定存 5M × 1.02^5
        assert sim.deposit_nominal_ntd == pytest.approx(5_000_000 * 1.02**5)

    def test_keyword_only_enforced(self) -> None:
        """位置參數傳到 keyword-only 後該失敗。"""
        with pytest.raises(TypeError):
            # 第二個位置參數不該被接受
            simulate_m2_decade(0.05, 5_000_000)  # type: ignore[misc]

    def test_returns_m2_simulation_result(self) -> None:
        assert isinstance(simulate_m2_decade(0.05), M2SimulationResult)

    def test_leverage_advantage_equals_equity_minus_deposit(self) -> None:
        sim = simulate_m2_decade(0.08)
        assert sim.leverage_advantage_ntd == pytest.approx(
            sim.equity_real_ntd - sim.deposit_real_ntd
        )


# ============================================================
# A2. diagnose_m2_regime — M2 / M1B 四象限
# ============================================================
class TestDiagnoseM2Regime:
    @pytest.mark.parametrize(
        ("m1b", "m2", "easing", "expected"),
        [
            (8.0, 6.0, True, M2Regime.SURGE),       # 黃金交叉 + 寬鬆
            (4.0, 6.0, False, M2Regime.DRAIN),      # 死亡交叉 + 緊縮
            (8.0, 6.0, False, M2Regime.TRANSITION), # 黃金交叉 + 緊縮
            (4.0, 6.0, True, M2Regime.BUILDUP),     # 死亡交叉 + 寬鬆
        ],
    )
    def test_four_quadrants(
        self, m1b: float, m2: float, easing: bool, expected: M2Regime,
    ) -> None:
        verdict = diagnose_m2_regime(m1b, m2, easing)
        assert verdict.regime == expected

    @pytest.mark.boundary
    def test_gap_zero_is_not_golden_cross(self) -> None:
        """gap = 0（M1B == M2）採嚴格 `>` 判定，視為非黃金交叉。"""
        verdict = diagnose_m2_regime(6.0, 6.0, True)
        assert verdict.gap_pp == 0
        assert verdict.is_golden_cross is False
        # 寬鬆 + 非黃金交叉 → BUILDUP
        assert verdict.regime == M2Regime.BUILDUP

    def test_gap_preserved_in_verdict(self) -> None:
        verdict = diagnose_m2_regime(8.5, 6.2, True)
        assert verdict.gap_pp == pytest.approx(2.3)

    def test_is_easing_passthrough(self) -> None:
        v_easing = diagnose_m2_regime(8, 6, True)
        v_tight = diagnose_m2_regime(8, 6, False)
        assert v_easing.is_easing is True
        assert v_tight.is_easing is False

    def test_returns_m2_regime_verdict(self) -> None:
        assert isinstance(diagnose_m2_regime(8, 6, True), M2RegimeVerdict)


# ============================================================
# B1. calculate_building_gap — 整棟價差增貸
# ============================================================
class TestCalculateBuildingGap:
    def test_positive_gap(self) -> None:
        """同棟最高 70 萬/坪 vs 目標 60 萬/坪 × 30 坪 = +300 萬潛在增貸。"""
        r = calculate_building_gap(70.0, 60.0, 30.0)
        assert r.unit_gap_wan == pytest.approx(10.0)
        assert r.total_max_price_wan == pytest.approx(2100.0)
        assert r.total_target_price_wan == pytest.approx(1800.0)
        assert r.potential_refinance_gap_wan == pytest.approx(300.0)

    def test_negative_gap_chasing_high(self) -> None:
        """出價比最高還貴 → 追高，潛在增貸為負。"""
        r = calculate_building_gap(60.0, 70.0, 30.0)
        assert r.unit_gap_wan == pytest.approx(-10.0)
        assert r.potential_refinance_gap_wan == pytest.approx(-300.0)

    def test_zero_gap(self) -> None:
        r = calculate_building_gap(60.0, 60.0, 30.0)
        assert r.unit_gap_wan == 0
        assert r.potential_refinance_gap_wan == 0

    def test_zero_ping_size(self) -> None:
        r = calculate_building_gap(70.0, 60.0, 0.0)
        assert r.total_max_price_wan == 0
        assert r.total_target_price_wan == 0
        assert r.potential_refinance_gap_wan == 0

    def test_returns_building_gap_result(self) -> None:
        assert isinstance(calculate_building_gap(70, 60, 30), BuildingGapResult)


# ============================================================
# B2. diagnose_wash_progress — 科目四四階段
# ============================================================
class TestDiagnoseWashProgress:
    @pytest.mark.parametrize(
        ("steps", "expected_stage", "expected_whitened"),
        [
            ((False, False, False, False), WashStage.NOT_STARTED, False),
            ((True, False, False, False), WashStage.REFINANCED, False),
            ((True, True, False, False), WashStage.PARKED, False),
            ((True, True, True, False), WashStage.INSTRUMENT_HELD, False),
            ((True, True, True, True), WashStage.WHITENED, True),
        ],
    )
    def test_stage_mapping(
        self,
        steps: tuple[bool, bool, bool, bool],
        expected_stage: WashStage,
        expected_whitened: bool,
    ) -> None:
        verdict = diagnose_wash_progress(steps)
        assert verdict.stage == expected_stage
        assert verdict.is_whitened == expected_whitened

    def test_completed_steps_equals_sum(self) -> None:
        verdict = diagnose_wash_progress((True, True, False, True))
        # UI 通常 disabled 上鎖按順序勾，但服務只 sum；測試覆蓋亂序 input
        assert verdict.completed_steps == 3

    def test_wash_stage_int_value_equals_count(self) -> None:
        """WashStage IntEnum 的數值 == 完成步驟數。"""
        for n in range(5):
            steps = tuple([True] * n + [False] * (4 - n))
            verdict = diagnose_wash_progress(steps)
            assert int(verdict.stage) == n

    def test_returns_wash_progress_verdict(self) -> None:
        assert isinstance(
            diagnose_wash_progress((False, False, False, False)),
            WashProgressVerdict,
        )


# ============================================================
# C1. calculate_stock_pledge — 股票質押
# ============================================================
class TestCalculateStockPledge:
    def test_zero_market_value_yields_all_zeros(self) -> None:
        r = calculate_stock_pledge(0)
        assert r.pledgeable_amount_ntd == 0
        assert r.annual_interest_ntd == 0
        assert r.monthly_interest_ntd == 0

    def test_1000_wan_default_params(self) -> None:
        """1000 萬市值 × 60% LTV = 600 萬可質押，× 2.5% = 15 萬年息。"""
        r = calculate_stock_pledge(10_000_000)
        assert r.pledgeable_amount_ntd == pytest.approx(6_000_000)
        assert r.annual_interest_ntd == pytest.approx(150_000)
        assert r.monthly_interest_ntd == pytest.approx(12_500)

    def test_monthly_interest_equals_annual_div_12(self) -> None:
        r = calculate_stock_pledge(50_000_000)
        assert r.monthly_interest_ntd == pytest.approx(r.annual_interest_ntd / 12)

    def test_custom_ltv_and_rate_via_kwargs(self) -> None:
        r = calculate_stock_pledge(10_000_000, ltv=0.50, annual_rate=0.03)
        assert r.pledgeable_amount_ntd == pytest.approx(5_000_000)
        assert r.annual_interest_ntd == pytest.approx(150_000)  # 5M × 3%

    def test_keyword_only_enforced(self) -> None:
        with pytest.raises(TypeError):
            calculate_stock_pledge(10_000_000, 0.50)  # type: ignore[misc]

    def test_defaults_match_ssot_constants(self) -> None:
        """預設 LTV / 利率必須對齊 constants.py SSOT。"""
        assert STOCK_PLEDGE_LTV == 0.60
        assert STOCK_PLEDGE_ANNUAL_RATE == 0.025


# ============================================================
# C2. calculate_vacancy_reserve — 空租準備金
# ============================================================
class TestCalculateVacancyReserve:
    @pytest.mark.parametrize(
        ("level", "expected_months"),
        [(1, 1), (2, 2), (3, 3), (4, 4), (5, 6)],
    )
    def test_each_location_level(self, level: int, expected_months: int) -> None:
        r = calculate_vacancy_reserve(level, 30_000)
        assert r.estimated_vacancy_months == expected_months
        assert r.emergency_fund_ntd == expected_months * 30_000

    def test_level_5_jumps_one_month(self) -> None:
        """5 級偏遠地段空租 6 個月（不是 5），跳一個月以反映實務。"""
        assert calculate_vacancy_reserve(5, 1).estimated_vacancy_months == 6

    def test_bad_level_raises_keyerror(self) -> None:
        """文件化 KeyError — caller 必須用 LOCATION_VACANCY_MONTHS_MAP 的 key。"""
        for bad_level in (0, 6, 99, -1):
            with pytest.raises(KeyError):
                calculate_vacancy_reserve(bad_level, 30_000)

    def test_returns_vacancy_reserve_result(self) -> None:
        assert isinstance(
            calculate_vacancy_reserve(3, 30_000), VacancyReserveResult,
        )


# ============================================================
# D1. calculate_syndication_arbitrage — 合資套利
# ============================================================
class TestCalculateSyndicationArbitrage:
    def test_profitable_case(self) -> None:
        """市價 2000 / 現金 1400 / 裝修 50 → 增貸 1600 − 1400 − 50 = +150 萬。"""
        r = calculate_syndication_arbitrage(2000, 1400, 50)
        assert r.bank_revaluation_wan == 2000
        assert r.refinanced_amount_wan == pytest.approx(1600)
        assert r.net_arbitrage_wan == pytest.approx(150)
        assert r.is_profitable is True

    def test_break_even_at_zero(self) -> None:
        """net == 0 → is_profitable=False（嚴格 `>`）。"""
        # refinanced = 1600，cash 1500，reno 100 → net = 0
        r = calculate_syndication_arbitrage(2000, 1500, 100)
        assert r.net_arbitrage_wan == pytest.approx(0)
        assert r.is_profitable is False

    def test_loss_case(self) -> None:
        r = calculate_syndication_arbitrage(2000, 1600, 80)
        # net = 1600 − 1600 − 80 = -80
        assert r.net_arbitrage_wan == pytest.approx(-80)
        assert r.is_profitable is False

    def test_bank_revaluation_equals_market_price(self) -> None:
        """『半年後鑑價會回到市價』是學長公式核心假設。"""
        r = calculate_syndication_arbitrage(3000, 2400, 100)
        assert r.bank_revaluation_wan == 3000

    def test_custom_ltv_via_kwarg(self) -> None:
        r = calculate_syndication_arbitrage(2000, 1400, 50, ltv=0.70)
        # 2000 × 0.70 = 1400，net = 1400 − 1400 − 50 = -50
        assert r.refinanced_amount_wan == pytest.approx(1400)
        assert r.net_arbitrage_wan == pytest.approx(-50)

    def test_default_ltv_is_ssot(self) -> None:
        assert BANK_REFINANCE_LTV == 0.80

    def test_returns_syndication_arbitrage_result(self) -> None:
        assert isinstance(
            calculate_syndication_arbitrage(2000, 1400, 50),
            SyndicationArbitrageResult,
        )


# ============================================================
# D2. diagnose_syndication_safeguards — 合資 4 道防護鎖
# ============================================================
class TestDiagnoseSyndicationSafeguards:
    @pytest.mark.parametrize(
        ("locks", "expected_in_place", "expected_naked"),
        [
            ((False, False, False, False), 0, True),
            ((True, False, False, False), 1, True),
            ((True, True, False, False), 2, True),
            ((True, True, True, False), 3, True),
            ((True, True, True, True), 4, False),
            ((True, False, True, False), 2, True),  # 不連續也算
        ],
    )
    def test_lock_count_and_naked_flag(
        self,
        locks: tuple[bool, bool, bool, bool],
        expected_in_place: int,
        expected_naked: bool,
    ) -> None:
        v = diagnose_syndication_safeguards(locks)
        assert v.locks_in_place == expected_in_place
        assert v.is_naked == expected_naked

    def test_total_locks_always_4(self) -> None:
        """無論輸入長度，4 道鎖是固定的 schema。"""
        v = diagnose_syndication_safeguards((True, True, True, True))
        assert v.total_locks == 4

    def test_returns_safeguard_completeness(self) -> None:
        assert isinstance(
            diagnose_syndication_safeguards((True,) * 4),
            SafeguardCompleteness,
        )


# ============================================================
# D3. diagnose_regional_tailwinds — 區域紅利 3 引擎
# ============================================================
class TestDiagnoseRegionalTailwinds:
    @pytest.mark.parametrize(
        ("hits", "expected_count", "expected_grade"),
        [
            ((False, False, False), 0, RegionalGrade.ORDINARY),
            ((True, False, False), 1, RegionalGrade.POTENTIAL),
            ((True, True, False), 2, RegionalGrade.STRONG),
            ((True, True, True), 3, RegionalGrade.NUCLEAR),
        ],
    )
    def test_grade_by_count(
        self,
        hits: tuple[bool, bool, bool],
        expected_count: int,
        expected_grade: RegionalGrade,
    ) -> None:
        v = diagnose_regional_tailwinds(hits)
        assert v.tailwind_count == expected_count
        assert v.grade == expected_grade

    def test_returns_regional_tailwind_verdict(self) -> None:
        assert isinstance(
            diagnose_regional_tailwinds((False,) * 3),
            RegionalTailwindVerdict,
        )

    @pytest.mark.boundary
    def test_too_many_tailwinds_raises_indexerror(self) -> None:
        """文件化 IndexError — 正常 UI 不會送 4+ 個 True，但服務防呆。"""
        with pytest.raises(IndexError):
            diagnose_regional_tailwinds((True, True, True, True))
