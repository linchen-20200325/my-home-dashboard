"""Unit tests — app.services.cashflow（DTI / 淨現金流診斷）。

對應 Phase 2 #33（首支 pytest 單元測試），驗證從 Ch.1 抽出的 service
判定邏輯與優先序。所有測試**不依賴 streamlit**，只 import service + model。
"""

from __future__ import annotations

import math

import pytest

from app.models.cashflow import CashflowInput, CashflowSeverity, CashflowSnapshot
from app.models.constants import LOW_BUFFER_THRESHOLD_NTD
from app.services.cashflow import _classify_severity, diagnose_cashflow


pytestmark = [pytest.mark.services]


# ============================================================
# 主入口 diagnose_cashflow — 經典場景
# ============================================================
class TestDiagnoseCashflow:
    """diagnose_cashflow() 場景對映 Ch.1 UI 分支。"""

    def test_zero_income_dti_locked(self) -> None:
        """總收入 = 0 → DTI = inf，severity = DTI_LOCKED（不丟 ZeroDivisionError）。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=0,
            living_cost_ntd=10_000,
        ))
        assert math.isinf(snap.dti)
        assert snap.severity == CashflowSeverity.DTI_LOCKED
        assert snap.net_cashflow_ntd == -10_000

    def test_healthy_baseline_no_debt(self) -> None:
        """80k 收入 / 30k 生活費 / 0 負債 → HEALTHY, net=50k, dti=0."""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=80_000,
            living_cost_ntd=30_000,
        ))
        assert snap.net_cashflow_ntd == 50_000
        assert snap.dti == pytest.approx(0.0)
        assert snap.total_debt_ntd == 0
        assert snap.severity == CashflowSeverity.HEALTHY
        assert snap.has_bad_debt is False
        assert snap.is_healthy is True

    def test_dti_locked_by_existing_mortgage(self) -> None:
        """收入 60k、現有房貸 45k → DTI = 0.75 > 0.70 → DTI_LOCKED（即便無毒藥）。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=60_000,
            living_cost_ntd=0,
            existing_mortgage_ntd=45_000,
        ))
        assert snap.dti == pytest.approx(0.75)
        assert snap.severity == CashflowSeverity.DTI_LOCKED
        assert snap.has_bad_debt is False  # 房貸不算毒藥

    def test_healthy_plus_bad_debt_orthogonal_flags(self) -> None:
        """健康 + 中產毒藥同時觸發 — severity 與 has_bad_debt 為正交旗標。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=180_000,
            living_cost_ntd=30_000,
            car_loan_ntd=10_000,
        ))
        # net = 180k - 30k - 10k = 140k；dti = 10k / 180k ≈ 0.0556
        assert snap.net_cashflow_ntd == 140_000
        assert snap.dti == pytest.approx(10_000 / 180_000)
        assert snap.severity == CashflowSeverity.HEALTHY
        assert snap.has_bad_debt is True
        # is_healthy 反映 severity（不看 bad_debt）
        assert snap.is_healthy is True

    def test_pure_negative_cashflow(self) -> None:
        """DTI 合格但 net < 0 → NEGATIVE。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=200_000,
            living_cost_ntd=220_000,
        ))
        assert snap.net_cashflow_ntd == -20_000
        assert snap.dti == pytest.approx(0.0)
        assert snap.severity == CashflowSeverity.NEGATIVE

    def test_low_buffer_boundary(self) -> None:
        """net 介於 0 ~ 20,000 → LOW_BUFFER。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=80_000,
            living_cost_ntd=65_000,
        ))
        assert snap.net_cashflow_ntd == 15_000
        assert snap.severity == CashflowSeverity.LOW_BUFFER

    def test_priority_dti_wins_over_negative(self) -> None:
        """DTI 死線 與 net < 0 同時觸發時，DTI_LOCKED 優先。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=30_000,
            living_cost_ntd=0,
            existing_mortgage_ntd=40_000,
        ))
        # dti = 40_000 / 30_000 ≈ 1.33 > 0.70 → DTI_LOCKED
        assert snap.dti > 1.0
        assert snap.net_cashflow_ntd == -10_000
        assert snap.severity == CashflowSeverity.DTI_LOCKED

    def test_five_debt_fields_aggregated_in_dti(self) -> None:
        """DTI 採五項負債合計 / 收入（標準銀行公式）。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=100_000,
            living_cost_ntd=20_000,
            existing_mortgage_ntd=20_000,
            car_loan_ntd=5_000,
            personal_loan_ntd=3_000,
            credit_card_min_ntd=1_000,
            other_debt_ntd=1_000,
        ))
        # total_debt = 20+5+3+1+1 = 30k；dti = 30/100 = 0.30
        assert snap.total_debt_ntd == 30_000
        assert snap.dti == pytest.approx(0.30)
        # net = 100 - 20 - 30 = 50k → HEALTHY
        assert snap.net_cashflow_ntd == 50_000
        assert snap.severity == CashflowSeverity.HEALTHY
        # 毒藥 = 車+信+卡+其他 = 10k > 0
        assert snap.has_bad_debt is True

    def test_mortgage_only_does_not_trigger_poison(self) -> None:
        """只有現有房貸（無消耗型負債）→ has_bad_debt = False。"""
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=100_000,
            living_cost_ntd=30_000,
            existing_mortgage_ntd=25_000,
        ))
        assert snap.dti == pytest.approx(0.25)
        assert snap.has_bad_debt is False
        assert snap.severity == CashflowSeverity.HEALTHY


# ============================================================
# 內部 _classify_severity — 直接測試判定核心
# ============================================================
class TestClassifySeverity:
    """直接測試純判定函式（不依賴 CashflowInput 包裝）。"""

    @pytest.mark.parametrize(
        ("net", "dti", "expected"),
        [
            (50_000, 0.5, CashflowSeverity.HEALTHY),
            (50_000, 0.70, CashflowSeverity.HEALTHY),  # 邊界：剛好 0.70 不算超過
            (50_000, 0.701, CashflowSeverity.DTI_LOCKED),
            (-1, 0.5, CashflowSeverity.NEGATIVE),
            (0, 0.5, CashflowSeverity.LOW_BUFFER),  # 邊界：剛好 0 不算負
            (19_999, 0.5, CashflowSeverity.LOW_BUFFER),
            (LOW_BUFFER_THRESHOLD_NTD, 0.5, CashflowSeverity.HEALTHY),  # 邊界：剛好 20k
            (1_000_000, float("inf"), CashflowSeverity.DTI_LOCKED),
        ],
    )
    @pytest.mark.boundary
    def test_severity_boundaries(
        self, net: int, dti: float, expected: CashflowSeverity,
    ) -> None:
        assert _classify_severity(net, dti) == expected


# ============================================================
# 回傳型別與不可變性
# ============================================================
class TestSnapshotImmutability:
    """CashflowSnapshot 是 frozen dataclass — 確保下游不會誤改。"""

    def test_snapshot_is_frozen(self) -> None:
        snap = diagnose_cashflow(CashflowInput(
            total_income_ntd=80_000,
            living_cost_ntd=30_000,
        ))
        with pytest.raises((AttributeError, Exception)):  # frozen → FrozenInstanceError
            snap.severity = CashflowSeverity.DTI_LOCKED  # type: ignore[misc]

    def test_two_identical_inputs_yield_equal_snapshots(self) -> None:
        """frozen dataclass 自動有 __eq__。"""
        a = diagnose_cashflow(CashflowInput(
            total_income_ntd=80_000,
            living_cost_ntd=30_000,
        ))
        b = diagnose_cashflow(CashflowInput(
            total_income_ntd=80_000,
            living_cost_ntd=30_000,
        ))
        assert a == b

    def test_snapshot_type(self) -> None:
        assert isinstance(
            diagnose_cashflow(CashflowInput(
                total_income_ntd=50_000,
                living_cost_ntd=20_000,
            )),
            CashflowSnapshot,
        )


# ============================================================
# CashflowInput 的 property（DTI / 毒藥分子）
# ============================================================
class TestCashflowInputProperties:
    """DTO 上的 total_debt_ntd / poison_debt_ntd 純加總邏輯。"""

    def test_total_debt_sums_five_fields(self) -> None:
        ci = CashflowInput(
            total_income_ntd=100_000,
            living_cost_ntd=0,
            existing_mortgage_ntd=20_000,
            car_loan_ntd=5_000,
            personal_loan_ntd=3_000,
            credit_card_min_ntd=1_000,
            other_debt_ntd=1_500,
        )
        assert ci.total_debt_ntd == 30_500
        assert ci.poison_debt_ntd == 10_500  # 扣掉房貸 20k

    def test_zero_debt_all_zero(self) -> None:
        ci = CashflowInput(total_income_ntd=100_000, living_cost_ntd=0)
        assert ci.total_debt_ntd == 0
        assert ci.poison_debt_ntd == 0
