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
# 主入口 diagnose_cashflow — 5 個經典場景
# ============================================================
class TestDiagnoseCashflow:
    """diagnose_cashflow() 五大場景對映 Ch.1 UI 分支。"""

    def test_zero_income_dti_locked(self) -> None:
        """總收入 = 0 → DTI = inf，severity = DTI_LOCKED（不丟 ZeroDivisionError）。"""
        snap = diagnose_cashflow(CashflowInput(0, 10_000, 0))
        assert math.isinf(snap.dti)
        assert snap.severity == CashflowSeverity.DTI_LOCKED
        assert snap.net_cashflow_ntd == -10_000

    def test_healthy_baseline(self) -> None:
        """80k 收入 / 30k 生活費 / 0 壞債 → HEALTHY, net=50k, dti=0.5"""
        snap = diagnose_cashflow(CashflowInput(80_000, 30_000, 0))
        assert snap.net_cashflow_ntd == 50_000
        assert snap.dti == pytest.approx(0.5)
        assert snap.severity == CashflowSeverity.HEALTHY
        assert snap.has_bad_debt is False
        assert snap.is_healthy is True

    def test_dti_just_over_red_line(self) -> None:
        """60k 收入 + 5k 壞債 → dti = (5000+40000)/60000 = 0.75 → DTI_LOCKED"""
        snap = diagnose_cashflow(CashflowInput(60_000, 0, 5_000))
        assert snap.dti == pytest.approx(0.75)
        assert snap.severity == CashflowSeverity.DTI_LOCKED

    def test_healthy_plus_bad_debt_orthogonal_flags(self) -> None:
        """健康 + 中產毒藥同時觸發 — severity 與 has_bad_debt 為正交旗標。"""
        snap = diagnose_cashflow(CashflowInput(80_000, 30_000, 10_000))
        assert snap.net_cashflow_ntd == 40_000
        assert snap.dti == pytest.approx(0.625)
        assert snap.severity == CashflowSeverity.HEALTHY
        assert snap.has_bad_debt is True
        # is_healthy 反映 severity（不看 bad_debt）
        assert snap.is_healthy is True

    def test_pure_negative_cashflow(self) -> None:
        """DTI 合格但 net < 0 → NEGATIVE。需用大收入大支出避免 DTI 同時觸發。"""
        snap = diagnose_cashflow(CashflowInput(200_000, 220_000, 0))
        assert snap.net_cashflow_ntd == -20_000
        assert snap.dti == pytest.approx(0.2)
        assert snap.severity == CashflowSeverity.NEGATIVE

    def test_low_buffer_boundary(self) -> None:
        """net 介於 0 ~ 20,000 → LOW_BUFFER。"""
        snap = diagnose_cashflow(CashflowInput(80_000, 65_000, 0))
        assert snap.net_cashflow_ntd == 15_000
        assert snap.severity == CashflowSeverity.LOW_BUFFER

    def test_priority_dti_wins_over_negative(self) -> None:
        """DTI 死線 與 net < 0 同時觸發時，DTI_LOCKED 優先。"""
        snap = diagnose_cashflow(CashflowInput(30_000, 40_000, 0))
        # dti = (0 + 40_000) / 30_000 ≈ 1.33 > 0.70 → DTI_LOCKED
        assert snap.dti > 1.0
        assert snap.net_cashflow_ntd == -10_000
        assert snap.severity == CashflowSeverity.DTI_LOCKED


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
        snap = diagnose_cashflow(CashflowInput(80_000, 30_000, 0))
        with pytest.raises((AttributeError, Exception)):  # frozen → FrozenInstanceError
            snap.severity = CashflowSeverity.DTI_LOCKED  # type: ignore[misc]

    def test_two_identical_inputs_yield_equal_snapshots(self) -> None:
        """frozen dataclass 自動有 __eq__。"""
        a = diagnose_cashflow(CashflowInput(80_000, 30_000, 0))
        b = diagnose_cashflow(CashflowInput(80_000, 30_000, 0))
        assert a == b

    def test_snapshot_type(self) -> None:
        assert isinstance(
            diagnose_cashflow(CashflowInput(50_000, 20_000, 0)),
            CashflowSnapshot,
        )
