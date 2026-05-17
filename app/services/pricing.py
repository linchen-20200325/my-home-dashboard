"""租金科學定價 + 議價底價推演服務（Ch.3 + strategy_negotiation 共用）。

純函式設計：
    - 嚴禁 `import streamlit`
    - 輸入：app.models DTO 或基本型別
    - 輸出：app.models DTO 或本模組 NamedTuple
    - 無外部 I/O，可獨立 unit test
"""

from __future__ import annotations

from typing import NamedTuple

from app.models.constants import (
    AGE_COEFFICIENT_MAP,
    FINAL_OFFER_DEFAULT_DISCOUNT,
    FINAL_OFFER_DEFAULT_ROUNDOFF_WAN,
    FLOOR_COEFFICIENT_MAP,
    NEGOTIATION_ANCHOR_DISCOUNT,
    NEGOTIATION_KILL_SHOT_DISCOUNT,
    VACANCY_FLOOR_DISCOUNT,
    VACANCY_STEP1_DISCOUNT,
    VACANCY_STEP2_DISCOUNT,
)
from app.models.tenant import RentalPricingInput, RentalPricingResult


# ============================================================
# 服務層內部 DTO（不污染 models 層）
# ============================================================
class VacancyStepdownTiers(NamedTuple):
    """空租超過紅線天數時的三階段降價建議。

    欄位皆為月租金額（元），且滿足 step1 > step2 > floor。
    """

    step1_5pct_off: float    # 先降 5%
    step2_8pct_off: float    # 再降 3%（累計 8%）
    floor_15pct_off: float   # 絕對底線：不可低於原價 15%


# ============================================================
# Ch.3 滿租科學定價
# ============================================================
def calculate_rental_pricing(payload: RentalPricingInput) -> RentalPricingResult:
    """根據單坪租金 × 坪數 × 樓層係數 × 屋齡係數，算出建議極限租金。

    Raises:
        KeyError: 若 floor_label / age_label 不在係數表內。
                  呼叫端應確保使用 constants.FLOOR_COEFFICIENT_MAP /
                  AGE_COEFFICIENT_MAP 的 key。
    """
    floor_coef = FLOOR_COEFFICIENT_MAP[payload.floor_label]
    age_coef = AGE_COEFFICIENT_MAP[payload.age_label]
    base_rent = payload.avg_rent_per_ping_ntd * payload.ping_size
    suggested = base_rent * floor_coef * age_coef
    return RentalPricingResult(
        base_rent_ntd=base_rent,
        floor_coef=floor_coef,
        age_coef=age_coef,
        suggested_rent_ntd=suggested,
    )


def vacancy_stepdown_prices(suggested_rent_ntd: float) -> VacancyStepdownTiers:
    """空租超過紅線天數時觸發的三階段降價建議。

    所有百分比都以『建議極限租金』為基準（非上一階累計）。
    """
    return VacancyStepdownTiers(
        step1_5pct_off=suggested_rent_ntd * VACANCY_STEP1_DISCOUNT,
        step2_8pct_off=suggested_rent_ntd * VACANCY_STEP2_DISCOUNT,
        floor_15pct_off=suggested_rent_ntd * VACANCY_FLOOR_DISCOUNT,
    )


# ============================================================
# strategy_negotiation 議價底價推演
# ============================================================
def negotiation_anchor_unit_wan(ad_unit_price_wan: float) -> float:
    """戰術 1：定錨效應 — 以廣告戶單價 × 0.95 作為談判首槍。

    Returns:
        建議首槍單價（萬 / 坪）。
    """
    return ad_unit_price_wan * NEGOTIATION_ANCHOR_DISCOUNT


def negotiation_kill_shot_unit_wan(ad_unit_price_wan: float) -> float:
    """獵物確認：屋主有民間私人 lien → 直接砍 -10%。

    Returns:
        建議獵殺單價（萬 / 坪）。
    """
    return ad_unit_price_wan * NEGOTIATION_KILL_SHOT_DISCOUNT


def final_offer_wan(
    asking_price_wan: float,
    discount: float = FINAL_OFFER_DEFAULT_DISCOUNT,
    final_round_off_wan: float = FINAL_OFFER_DEFAULT_ROUNDOFF_WAN,
) -> float:
    """戰術 3：收尾擋箭牌 — 開價 × 折扣，再砍掉零頭。

    保證返回值 ≥ 0（用 max 防護扣零頭後變負數的退化情境）。

    Args:
        asking_price_wan: 屋主開價（萬）。
        discount: 折扣率（預設 0.85）。
        final_round_off_wan: 砍零頭金額（萬，預設 50）。

    Returns:
        建議最終出價（萬），最低為 0。
    """
    return max(0.0, asking_price_wan * discount - final_round_off_wan)
