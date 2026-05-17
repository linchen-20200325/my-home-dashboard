"""Unit tests — app.services.presale_filter（履保 / 梯戶比 / 合約地雷 / 謄本）。"""

from __future__ import annotations

import pytest

from app.models.constants import HEALTHY_ELEVATOR_RATIO_MAX
from app.models.property import PropertySpec, PropertyType
from app.services.presale_filter import (
    ContractLandmineVerdict,
    ElevatorRatioGrade,
    EscrowSeverity,
    EscrowType,
    TitleDeedVerdict,
    classify_escrow,
    diagnose_contract_landmines,
    diagnose_title_deed,
    grade_elevator_ratio,
)


pytestmark = [pytest.mark.services]


# ============================================================
# classify_escrow — 履保 4 級
# ============================================================
class TestClassifyEscrow:
    @pytest.mark.parametrize(
        ("escrow", "expected"),
        [
            (EscrowType.PRICE_RETURN, EscrowSeverity.STRONGEST),
            (EscrowType.PRICE_TRUST, EscrowSeverity.MODERATE),
            (EscrowType.PEER_CO_GUARANTEE, EscrowSeverity.HIGH_RISK),
            (EscrowType.DEVELOPMENT_TRUST, EscrowSeverity.CRITICAL),
        ],
    )
    def test_each_escrow_type(
        self, escrow: EscrowType, expected: EscrowSeverity,
    ) -> None:
        assert classify_escrow(escrow) == expected


# ============================================================
# grade_elevator_ratio — 梯戶比 3 級
# ============================================================
class TestGradeElevatorRatio:
    def _spec(self, units: int, elevators: int) -> PropertySpec:
        return PropertySpec(PropertyType.RESALE, 25.0, units, elevators)

    def test_healthy_low_ratio(self) -> None:
        # 3 戶 / 2 梯 = 1.5
        assert grade_elevator_ratio(self._spec(3, 2)) == ElevatorRatioGrade.HEALTHY

    @pytest.mark.boundary
    def test_healthy_boundary_25(self) -> None:
        """ratio == 2.5 剛好踩 HEALTHY 上限（含），不升 BORDERLINE。"""
        # 5 戶 / 2 梯 = 2.5
        assert grade_elevator_ratio(self._spec(5, 2)) == ElevatorRatioGrade.HEALTHY
        assert HEALTHY_ELEVATOR_RATIO_MAX == 2.5

    def test_borderline_range(self) -> None:
        # 8 戶 / 3 梯 = 2.67
        assert grade_elevator_ratio(self._spec(8, 3)) == ElevatorRatioGrade.BORDERLINE

    @pytest.mark.boundary
    def test_borderline_boundary_at_4(self) -> None:
        """ratio == 4.0 剛好踩 BORDERLINE 上限（含），不升 DANGEROUS。"""
        # 8 戶 / 2 梯 = 4.0
        assert grade_elevator_ratio(self._spec(8, 2)) == ElevatorRatioGrade.BORDERLINE

    def test_dangerous_above_4(self) -> None:
        # 9 戶 / 2 梯 = 4.5
        assert grade_elevator_ratio(self._spec(9, 2)) == ElevatorRatioGrade.DANGEROUS

    @pytest.mark.boundary
    def test_zero_elevator_inherits_inf_guard(self) -> None:
        """電梯數為 0 → PropertySpec.elevator_ratio 回傳 inf → 觸發 DANGEROUS。"""
        spec = self._spec(4, 0)
        assert spec.elevator_ratio == float("inf")
        assert grade_elevator_ratio(spec) == ElevatorRatioGrade.DANGEROUS


# ============================================================
# diagnose_contract_landmines — 通用 n 變數合約地雷
# ============================================================
class TestDiagnoseContractLandmines:
    def test_empty(self) -> None:
        v = diagnose_contract_landmines(())
        assert v.landmine_count == 0
        assert v.has_any_landmine is False
        assert v.triggered_indices == ()

    def test_single_hit_index_preserved(self) -> None:
        v = diagnose_contract_landmines((False, False, True, False))
        assert v.landmine_count == 1
        assert v.has_any_landmine is True
        assert v.triggered_indices == (2,)

    def test_multi_hits_in_order(self) -> None:
        v = diagnose_contract_landmines((True, False, True, True))
        assert v.landmine_count == 3
        assert v.triggered_indices == (0, 2, 3)

    def test_all_hits(self) -> None:
        v = diagnose_contract_landmines((True,) * 5)
        assert v.landmine_count == 5
        assert v.triggered_indices == (0, 1, 2, 3, 4)

    def test_returns_named_tuple(self) -> None:
        assert isinstance(diagnose_contract_landmines(()), ContractLandmineVerdict)


# ============================================================
# diagnose_title_deed — 中古屋兩大謄本地雷（正交）
# ============================================================
class TestDiagnoseTitleDeed:
    @pytest.mark.parametrize(
        ("no_land", "private_lien", "any_landmine"),
        [
            (False, False, False),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        ],
    )
    def test_four_combinations(
        self, no_land: bool, private_lien: bool, any_landmine: bool,
    ) -> None:
        v = diagnose_title_deed(no_land, private_lien)
        assert v.no_land == no_land
        assert v.private_lien == private_lien
        assert v.has_any_landmine == any_landmine

    def test_returns_dataclass(self) -> None:
        assert isinstance(diagnose_title_deed(False, False), TitleDeedVerdict)
