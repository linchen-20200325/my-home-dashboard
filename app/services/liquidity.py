"""流動性與安全離場服務（Ch.5 + Ch.7 共用）。

涵蓋：
    - Ch.5 區塊一：流動性極差排雷針（4 大死亡特徵）
    - Ch.5 區塊二：出價前 7 步驟議價 SOP 準備度
    - Ch.7 左欄：老屋脫手年限逆推 + 銀行可貸年期
    - Ch.7 右欄：自用 5 年免稅鐵證強度

純函式設計：
    - 嚴禁 `import streamlit`
    - 輸入：基本型別 / tuple[bool, ...]
    - 輸出：本模組 dataclass / NamedTuple
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from app.models.constants import (
    BANK_MAX_LOAN_YEARS_PER_PROPERTY,
    EXIT_AGE_RED_LINE_YEARS,
    NEGOTIATION_SOP_INCOMPLETE_THRESHOLD,
    NEGOTIATION_SOP_TOTAL_STEPS,
    RC_DURABILITY_YEARS,
    RESIDENCY_EVIDENCE_GAPPED_THRESHOLD,
    RESIDENCY_EVIDENCE_TOTAL,
)


# ============================================================
# Ch.5 區塊一：流動性極差排雷針
# ============================================================
class LiquidityTrapVerdict(NamedTuple):
    """中古屋 4 大流動性地雷檢測結果。

    任一勾選即視為高風險（has_any_trap=True）；
    呼叫端應以此為『拒絕往下評估』的硬性門檻。
    """

    trap_count: int
    has_any_trap: bool


def diagnose_liquidity_traps(traps_hit: tuple[bool, ...]) -> LiquidityTrapVerdict:
    """根據流動性地雷勾選結果回傳統計。"""
    n = sum(traps_hit)
    return LiquidityTrapVerdict(trap_count=n, has_any_trap=n > 0)


# ============================================================
# Ch.5 區塊二：議價前 7 步驟 SOP 準備度
# ============================================================
class NegotiationReadiness(str, Enum):
    """出價準備度分級。

    NOT_READY:  完成 < 5 步 → 仲介眼中的『盤子』
    INCOMPLETE: 完成 5-6 步 → 還缺火候
    READY:      完成全部 7 步 → 可以進場出價
    """

    NOT_READY = "not_ready"
    INCOMPLETE = "incomplete"
    READY = "ready"


@dataclass(frozen=True)
class NegotiationSopVerdict:
    completed_count: int
    total_steps: int
    readiness: NegotiationReadiness


def diagnose_negotiation_sop(steps_done: tuple[bool, ...]) -> NegotiationSopVerdict:
    """根據 7 步驟 SOP 勾選結果評估出價準備度。"""
    done = sum(steps_done)
    total = NEGOTIATION_SOP_TOTAL_STEPS

    if done >= total:
        readiness = NegotiationReadiness.READY
    elif done >= NEGOTIATION_SOP_INCOMPLETE_THRESHOLD:
        readiness = NegotiationReadiness.INCOMPLETE
    else:
        readiness = NegotiationReadiness.NOT_READY

    return NegotiationSopVerdict(
        completed_count=done,
        total_steps=total,
        readiness=readiness,
    )


# ============================================================
# Ch.7 左欄：老屋脫手年限逆推
# ============================================================
@dataclass(frozen=True)
class ExitAgeResult:
    """脫手年限推演結果。

    distance_to_red_line < 0 表示尚有緩衝；> 0 表示已踩過紅線。
    is_over_red_line 採嚴格 `>` 比較（35 為邊界本身視為安全）。
    """

    exit_age: int
    max_bank_loan_years: int
    distance_to_red_line: int
    is_over_red_line: bool


def calculate_exit_age(current_age: int, holding_years: int) -> ExitAgeResult:
    """逆推脫手時屋齡 + 銀行可貸年期。

    銀行貸款年期公式：min(RC 耐用 50 年 − 脫手屋齡, 30 年上限)，
    並 clamp 至 [0, 30]，防止屋齡過高得負數、過低超過 30 上限。
    """
    exit_age = current_age + holding_years
    raw_loan_years = RC_DURABILITY_YEARS - exit_age
    max_loan = max(0, min(raw_loan_years, BANK_MAX_LOAN_YEARS_PER_PROPERTY))
    distance = exit_age - EXIT_AGE_RED_LINE_YEARS

    return ExitAgeResult(
        exit_age=exit_age,
        max_bank_loan_years=max_loan,
        distance_to_red_line=distance,
        is_over_red_line=exit_age > EXIT_AGE_RED_LINE_YEARS,
    )


# ============================================================
# Ch.7 右欄：自用 5 年免稅鐵證強度
# ============================================================
class ResidencyStrength(str, Enum):
    """生活軌跡證據強度分級。

    INSUFFICIENT: < 3 件 → 極可能被國稅局否准自用稅率
    GAPPED:       3-4 件 → 尚可但有破口
    IRONCLAD:     5 件   → 堅不可摧鐵證
    """

    INSUFFICIENT = "insufficient"
    GAPPED = "gapped"
    IRONCLAD = "ironclad"


@dataclass(frozen=True)
class ResidencyVerdict:
    evidence_count: int
    total_evidence: int
    strength: ResidencyStrength


def diagnose_residency_evidence(
    evidence_collected: tuple[bool, ...],
) -> ResidencyVerdict:
    """根據 5 道生活軌跡鐵證勾選結果評估證據強度。"""
    n = sum(evidence_collected)
    total = RESIDENCY_EVIDENCE_TOTAL

    if n >= total:
        strength = ResidencyStrength.IRONCLAD
    elif n >= RESIDENCY_EVIDENCE_GAPPED_THRESHOLD:
        strength = ResidencyStrength.GAPPED
    else:
        strength = ResidencyStrength.INSUFFICIENT

    return ResidencyVerdict(
        evidence_count=n,
        total_evidence=total,
        strength=strength,
    )
