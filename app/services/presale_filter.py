"""預售屋 / 中古屋判定服務 — 建商體質 + 梯戶比 + 合約地雷 + 謄本地雷。

涵蓋：
    Ch.2 區塊一 — 建商體質體檢（履約保證 4 級分類）
    Ch.2 區塊二 — 梯戶比 3 級分級（HEALTHY / BORDERLINE / DANGEROUS）
    Ch.2 區塊三 — 預售屋合約地雷（雨遮 / 面積誤差 / 第 18 條）
    Ch.8 預售屋 — 4 條合約陷阱（管線費 / 車位無高度 / 雨遮 / 履保費）
    Ch.8 中古屋 — 2 大謄本地雷（地上權 / 私人他項權利）

純函式設計：嚴禁 `import streamlit`；無外部 I/O。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from app.models.constants import (
    ELEVATOR_RATIO_DANGER,
    HEALTHY_ELEVATOR_RATIO_MAX,
)
from app.models.property import PropertySpec


# ============================================================
# A. 建商體質 — 履約保證 4 級分類（Ch.2）
# ============================================================
class EscrowType(str, Enum):
    """預售屋履約保證 4 種型態（由強至弱）。"""

    PRICE_RETURN = "price_return"           # 價金返還保證（最強）
    PRICE_TRUST = "price_trust"             # 價金信託
    PEER_CO_GUARANTEE = "peer_co_guarantee"  # 同業連帶擔保
    DEVELOPMENT_TRUST = "development_trust"  # 不動產開發信託（最弱）


class EscrowSeverity(str, Enum):
    """履保強度的 UI 渲染等級。"""

    STRONGEST = "strongest"   # ✅ 價金返還 — 可放心簽
    MODERATE = "moderate"     # 🟡 價金信託 — 有殘值風險
    HIGH_RISK = "high_risk"   # 🟠 同業擔保 — 連動風險
    CRITICAL = "critical"     # 🔴 開發信託 — 直接放棄


_ESCROW_SEVERITY_MAP: dict[EscrowType, EscrowSeverity] = {
    EscrowType.PRICE_RETURN: EscrowSeverity.STRONGEST,
    EscrowType.PRICE_TRUST: EscrowSeverity.MODERATE,
    EscrowType.PEER_CO_GUARANTEE: EscrowSeverity.HIGH_RISK,
    EscrowType.DEVELOPMENT_TRUST: EscrowSeverity.CRITICAL,
}


def classify_escrow(escrow_type: EscrowType) -> EscrowSeverity:
    """將履約保證型態映射到嚴重度。"""
    return _ESCROW_SEVERITY_MAP[escrow_type]


# ============================================================
# B. 梯戶比 3 級分級（Ch.2 — 比 Ch.10 二元更細）
# ============================================================
# 健康上限：ratio ≤ HEALTHY_ELEVATOR_RATIO_MAX → HEALTHY
# 警戒上限：HEALTHY_MAX < ratio ≤ DANGER（即 ELEVATOR_RATIO_DANGER） → BORDERLINE
# 危險：ratio > DANGER → DANGEROUS（與 Ch.10 strict-gt 一致）
class ElevatorRatioGrade(str, Enum):
    """梯戶比 3 級分類。

    與 Ch.10 decision_engine 的 strict-bool 並存：
        Ch.10 只關心『是否觸發 KILL_SHOT 警告』（boolean）
        Ch.2  需要 fine-grained 三色顯示（HEALTHY / BORDERLINE / DANGEROUS）
    """

    HEALTHY = "healthy"        # 動線優良，可衝高租金
    BORDERLINE = "borderline"  # 偏高，租金以區域均價下限定價
    DANGEROUS = "dangerous"    # 紅線，建議放棄此案


def grade_elevator_ratio(spec: PropertySpec) -> ElevatorRatioGrade:
    """根據 PropertySpec 的梯戶比回傳 3 級分類。

    邊界規則（與 Ch.2 原 UI 一致）：
        ratio ≤ 2.5  → HEALTHY
        2.5 < ratio ≤ 4.0 → BORDERLINE
        ratio > 4.0  → DANGEROUS

    重用 PropertySpec.elevator_ratio，自動繼承 0-elevator 防護（回傳 inf）。
    """
    ratio = spec.elevator_ratio
    if ratio > ELEVATOR_RATIO_DANGER:
        return ElevatorRatioGrade.DANGEROUS
    if ratio > HEALTHY_ELEVATOR_RATIO_MAX:
        return ElevatorRatioGrade.BORDERLINE
    return ElevatorRatioGrade.HEALTHY


# ============================================================
# C. 合約地雷（通用 — Ch.2 區塊三 + Ch.8 預售陷阱）
# ============================================================
class ContractLandmineVerdict(NamedTuple):
    """通用合約地雷檢測。

    landmines_hit 順序由呼叫端決定（與 UI 顯示順序一致）；
    triggered_indices 讓 UI 能列出具體條款。
    """

    landmine_count: int
    has_any_landmine: bool
    triggered_indices: tuple[int, ...]


def diagnose_contract_landmines(
    landmines_hit: tuple[bool, ...],
) -> ContractLandmineVerdict:
    """通用合約地雷數量檢測。

    可用於 Ch.2 區塊三（雨遮 / 面積誤差 / 第 18 條 3 條）
    與 Ch.8 區塊一（管線費 / 車位高度 / 雨遮 / 履保費 4 條）。
    """
    triggered = tuple(i for i, hit in enumerate(landmines_hit) if hit)
    return ContractLandmineVerdict(
        landmine_count=len(triggered),
        has_any_landmine=bool(triggered),
        triggered_indices=triggered,
    )


# ============================================================
# D. 中古屋謄本兩大地雷（Ch.8）
# ============================================================
@dataclass(frozen=True)
class TitleDeedVerdict:
    """謄本兩大致命地雷檢測結果。

    no_land 與 private_lien 為 orthogonal 旗標 — 可同時觸發；
    UI 應為每項命中渲染獨立的 st.error block。
    """

    no_land: bool        # 土地空白：地上權住宅
    private_lien: bool   # 他項權利為私人姓名：黑道高利貸
    has_any_landmine: bool


def diagnose_title_deed(
    no_land: bool, private_lien: bool,
) -> TitleDeedVerdict:
    """直接包裝兩個布林為 verdict（語義化命名 + 衍生 has_any 旗標）。"""
    return TitleDeedVerdict(
        no_land=no_land,
        private_lien=private_lien,
        has_any_landmine=no_land or private_lien,
    )
