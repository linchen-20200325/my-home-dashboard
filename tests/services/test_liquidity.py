"""Unit tests — app.services.liquidity（流動性 + 議價 SOP + 脫手年限 + 鐵證）。

Covers 4 純函式：
    diagnose_liquidity_traps     — Ch.5 區塊一
    diagnose_negotiation_sop     — Ch.5 區塊二
    calculate_exit_age           — Ch.7 左欄
    diagnose_residency_evidence  — Ch.7 右欄
"""

from __future__ import annotations

import pytest

from app.models.constants import (
    BANK_MAX_LOAN_YEARS_PER_PROPERTY,
    EXIT_AGE_RED_LINE_YEARS,
    RC_DURABILITY_YEARS,
)
from app.services.liquidity import (
    ExitAgeResult,
    LiquidityTrapVerdict,
    NegotiationReadiness,
    NegotiationSopVerdict,
    ResidencyStrength,
    ResidencyVerdict,
    calculate_exit_age,
    diagnose_liquidity_traps,
    diagnose_negotiation_sop,
    diagnose_residency_evidence,
)


pytestmark = [pytest.mark.services]


# ============================================================
# diagnose_liquidity_traps — 4 大死亡特徵
# ============================================================
class TestDiagnoseLiquidityTraps:
    @pytest.mark.parametrize(
        ("traps", "expected_count", "expected_any"),
        [
            ((False,)*4, 0, False),
            ((True, False, False, False), 1, True),
            ((True, True, False, False), 2, True),
            ((True,)*4, 4, True),
            ((False, True, False, True), 2, True),  # 不連續也算
        ],
    )
    def test_trap_count_and_any_flag(
        self,
        traps: tuple[bool, ...],
        expected_count: int,
        expected_any: bool,
    ) -> None:
        v = diagnose_liquidity_traps(traps)
        assert v.trap_count == expected_count
        assert v.has_any_trap == expected_any

    def test_returns_named_tuple(self) -> None:
        assert isinstance(diagnose_liquidity_traps((False,)*4), LiquidityTrapVerdict)


# ============================================================
# diagnose_negotiation_sop — 7 步驟 + 3 級準備度
# ============================================================
class TestDiagnoseNegotiationSop:
    @pytest.mark.parametrize(
        ("done_count", "expected_readiness"),
        [
            (0, NegotiationReadiness.NOT_READY),
            (4, NegotiationReadiness.NOT_READY),  # boundary: 4 仍 NOT_READY
            (5, NegotiationReadiness.INCOMPLETE),  # boundary: 5 升級到 INCOMPLETE
            (6, NegotiationReadiness.INCOMPLETE),
            (7, NegotiationReadiness.READY),
        ],
    )
    @pytest.mark.boundary
    def test_readiness_at_thresholds(
        self, done_count: int, expected_readiness: NegotiationReadiness,
    ) -> None:
        steps = tuple([True] * done_count + [False] * (7 - done_count))
        v = diagnose_negotiation_sop(steps)
        assert v.readiness == expected_readiness
        assert v.completed_count == done_count
        assert v.total_steps == 7

    def test_returns_dataclass(self) -> None:
        assert isinstance(
            diagnose_negotiation_sop((False,)*7), NegotiationSopVerdict,
        )


# ============================================================
# calculate_exit_age — 老屋脫手紅線
# ============================================================
class TestCalculateExitAge:
    def test_normal_safe_case(self) -> None:
        """屋齡 20 + 持有 10 = 脫手 30 年，紅線安全。"""
        r = calculate_exit_age(20, 10)
        assert r.exit_age == 30
        assert r.distance_to_red_line == 30 - EXIT_AGE_RED_LINE_YEARS
        assert r.distance_to_red_line == -5
        assert r.max_bank_loan_years == 20  # 50 − 30
        assert r.is_over_red_line is False

    @pytest.mark.boundary
    def test_exit_age_exactly_red_line(self) -> None:
        """脫手剛好 35 年——is_over_red_line 採嚴格 `>`，不觸發。"""
        r = calculate_exit_age(20, 15)
        assert r.exit_age == EXIT_AGE_RED_LINE_YEARS
        assert r.distance_to_red_line == 0
        assert r.is_over_red_line is False
        assert r.max_bank_loan_years == 15  # 50 − 35

    def test_over_red_line(self) -> None:
        r = calculate_exit_age(30, 10)
        assert r.exit_age == 40
        assert r.is_over_red_line is True
        assert r.max_bank_loan_years == 10  # 50 − 40

    @pytest.mark.boundary
    def test_max_loan_clamped_to_zero_for_very_old(self) -> None:
        """脫手 60 年：理論 50−60=−10，clamp 至 0。"""
        r = calculate_exit_age(50, 10)
        assert r.exit_age == 60
        assert r.max_bank_loan_years == 0  # NOT -10

    @pytest.mark.boundary
    def test_max_loan_clamped_to_30_for_brand_new(self) -> None:
        """脫手 0 年：理論 50−0=50，clamp 至 30 上限。"""
        r = calculate_exit_age(0, 0)
        assert r.exit_age == 0
        assert r.max_bank_loan_years == BANK_MAX_LOAN_YEARS_PER_PROPERTY  # 30

    def test_constants_match_assumptions(self) -> None:
        """RC 耐用 50、銀行上限 30 — 學長假設不該無聲變更。"""
        assert RC_DURABILITY_YEARS == 50
        assert BANK_MAX_LOAN_YEARS_PER_PROPERTY == 30

    def test_returns_exit_age_result(self) -> None:
        assert isinstance(calculate_exit_age(20, 10), ExitAgeResult)


# ============================================================
# diagnose_residency_evidence — 5 道生活軌跡鐵證
# ============================================================
class TestDiagnoseResidencyEvidence:
    @pytest.mark.parametrize(
        ("evidence_count", "expected"),
        [
            (0, ResidencyStrength.INSUFFICIENT),
            (2, ResidencyStrength.INSUFFICIENT),  # boundary: 2 仍 INSUFFICIENT
            (3, ResidencyStrength.GAPPED),         # boundary: 3 升級到 GAPPED
            (4, ResidencyStrength.GAPPED),
            (5, ResidencyStrength.IRONCLAD),
        ],
    )
    @pytest.mark.boundary
    def test_strength_at_thresholds(
        self, evidence_count: int, expected: ResidencyStrength,
    ) -> None:
        evidence = tuple([True] * evidence_count + [False] * (5 - evidence_count))
        v = diagnose_residency_evidence(evidence)
        assert v.strength == expected
        assert v.evidence_count == evidence_count
        assert v.total_evidence == 5

    def test_returns_residency_verdict(self) -> None:
        assert isinstance(
            diagnose_residency_evidence((False,)*5), ResidencyVerdict,
        )
