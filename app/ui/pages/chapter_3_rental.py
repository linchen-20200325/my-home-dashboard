"""Chapter 3 UI — 出租策略與滿租定價法（重構後）。

UI 層：純 widgets + 渲染；定價公式 + 階梯降價 + 租客評分由 services 計算。
"""

from __future__ import annotations

import streamlit as st

from app.models.constants import (
    AGE_COEFFICIENT_MAP,
    FLOOR_COEFFICIENT_MAP,
    TENANT_CHECK_POINTS_PER_ITEM,
    TENANT_CHECK_TOTAL_MAX,
    VACANCY_DAYS_DANGER,
)
from app.models.tenant import CreditDefenseScore, RentalPricingInput
from app.services.pricing import (
    calculate_rental_pricing,
    vacancy_stepdown_prices,
)
from app.services.tenant_radar import TenantSeverity, diagnose_tenant
from app.ui.components.metric_grid import render_metric_row


# ===== UI labels（保留原文）=====
GENERAL_CHECKS: list[tuple[str, str]] = [
    ("① 是否查驗交通罰單無遲繳紀錄？（測信用意識）", "ch3_tn_traffic"),
    ("② 是否已打電話至租客公司照會確認在職？", "ch3_tn_employer"),
    ("③ 司法院簡易判決書查詢是否無前科？", "ch3_tn_court"),
    ("④ 警政署 APP 查詢是否無通緝／報案紀錄？", "ch3_tn_police"),
    ("⑤ 是否能提供有力的連帶保證人？", "ch3_tn_guarantor"),
    ("⑥ 居住人數與關係是否單純交代清楚？", "ch3_tn_household"),
]
BOSS_LABEL = "⑦ 【魔王題】租客『沒有』一開口就要求押金分期 / 押金優惠？"


def _render_pricing_tab() -> None:
    st.subheader("🎯 滿租科學定價計算機")
    st.caption("學長公式：基礎租金 × 樓層係數 × 屋齡係數 = 建議極限租金")

    col_a, col_b = st.columns(2)
    with col_a:
        avg_rent_per_ping = st.number_input(
            "區域平均單坪租金（元 / 坪）", min_value=0, value=1200, step=50,
            help="參考實價登錄租賃案件，取近期同區、相近屋型的中位數。",
        )
        ping_size = st.number_input(
            "房屋坪數（坪）", min_value=0.0, value=25.0, step=0.5, format="%.1f",
        )
    with col_b:
        floor_choice = st.selectbox(
            "所在樓層", list(FLOOR_COEFFICIENT_MAP.keys()), index=1,
            help="低樓層治安/採光較差打 9 折；高樓層視野/採光較好加 1 成。",
        )
        age_choice = st.selectbox(
            "房屋屋齡", list(AGE_COEFFICIENT_MAP.keys()), index=1,
            help="新屋附加感較強加 2 成；老屋打 8 折避免空租。",
        )

    result = calculate_rental_pricing(RentalPricingInput(
        avg_rent_per_ping_ntd=float(avg_rent_per_ping),
        ping_size=float(ping_size),
        floor_label=floor_choice,
        age_label=age_choice,
    ))

    st.markdown("---")
    st.markdown("##### 📊 學長定價公式拆解")
    render_metric_row([
        {"label": "基礎租金", "value": f"{result.base_rent_ntd:,.0f} 元",
         "help": "平均單坪租金 × 坪數"},
        {"label": "樓層係數", "value": f"× {result.floor_coef}", "help": floor_choice},
        {"label": "屋齡係數", "value": f"× {result.age_coef}", "help": age_choice},
    ])

    st.metric(
        "🎯 建議極限租金（上架價）", f"{result.suggested_rent_ntd:,.0f} 元 / 月",
        delta=f"{(result.suggested_rent_ntd - result.base_rent_ntd):,.0f} 元 vs 基礎租金",
        help="這是市場能接受的上限。實際上架可從此數字試水溫，1~2 週無人詢問再考慮微調。",
    )
    st.caption(f"≒ 約 {result.suggested_rent_ntd / 10_000:.2f} 萬／月")

    st.markdown("---")
    st.markdown("##### ⏰ 空租天數監控（階梯式降價停損）")
    vacancy_days = st.slider(
        "目前已空租天數", min_value=0, max_value=90, value=10, step=1,
        help="超過 20 天就要主動下殺，不要硬撐。",
    )

    if vacancy_days > VACANCY_DAYS_DANGER:
        tiers = vacancy_stepdown_prices(result.suggested_rent_ntd)
        st.warning(
            f"⚠️ **空租超過 {VACANCY_DAYS_DANGER} 天！學長建議立刻啟動階梯式降價：**\n\n"
            f"- 第一階：先降 **5%** → 約 **{tiers.step1_5pct_off:,.0f} 元**\n"
            f"- 第二階：若無效再降 **3%** → 約 **{tiers.step2_8pct_off:,.0f} 元**\n"
            f"- 🚧 **極限不可超過原價 15%** → 不可低於 **{tiers.floor_15pct_off:,.0f} 元**\n\n"
            "**再低就是賠錢做功德了。**"
        )
    elif vacancy_days > 10:
        st.info("🟡 空租已超過 10 天，再觀察一週。檢查照片、標題、看房時段是否友善。")
    else:
        st.success("🟢 空租天數在安全範圍內，維持現有策略繼續累積看屋人潮。")


def _render_radar_tab() -> None:
    st.subheader("🛡️ 租客七道信用防線雷達")
    st.caption(
        f"七題勾選 × 每題 {TENANT_CHECK_POINTS_PER_ITEM} 分 = 滿分 {TENANT_CHECK_TOTAL_MAX}。"
        "第 ⑦ 題為魔王題，未過直接判退。"
    )

    col_l, col_r = st.columns(2)
    general_results: list[bool] = []
    for idx, (label, key) in enumerate(GENERAL_CHECKS):
        target_col = col_l if idx < 3 else col_r
        with target_col:
            general_results.append(st.checkbox(label, key=key))

    st.markdown("---")
    boss_ok = st.checkbox(BOSS_LABEL, key="ch3_tn_boss")

    score = CreditDefenseScore(general_passed=tuple(general_results), boss_passed=boss_ok)
    verdict = diagnose_tenant(score)

    st.markdown("---")
    st.markdown("##### 📊 防線評分結果")
    render_metric_row([
        {"label": "通過項數", "value": f"{score.passed_count} / 7"},
        {"label": "總分", "value": f"{score.total_score} / {TENANT_CHECK_TOTAL_MAX} 分"},
        {"label": "魔王題", "value": "✅ 通過" if boss_ok else "❌ 失守"},
    ])

    if verdict.severity == TenantSeverity.DANGEROUS:
        failure_reasons: list[str] = []
        if verdict.boss_failed:
            failure_reasons.append("**魔王題失守**：對方一開口就談押金分期 / 優惠")
        if verdict.below_pass_threshold:
            failure_reasons.append(
                f"**總分不及格**：{score.total_score} 分 < 75 分門檻"
            )
        st.error(
            "🚫 **高危險租客！**\n\n"
            + "\n".join(f"- {r}" for r in failure_reasons)
            + "\n\n連押金都付不出來或信用有瑕疵，未來極高機率變租霸——"
            "**寧可空租絕對不租！**"
        )
    elif verdict.severity == TenantSeverity.EXCELLENT:
        st.success(
            f"✅ **優質租客！** 總分 {score.total_score} / {TENANT_CHECK_TOTAL_MAX}，"
            "七道防線全數過關。\n\n"
            "👉 **立刻動作清單：**\n"
            "1. **法院公證** 租約（強制執行省下一年訴訟時間）\n"
            "2. **換裝電子鎖**（搬離當天即時更換密碼／磁扣）\n"
            "3. 押金收滿 2 個月、租金一律匯款留紀錄"
        )
    else:  # MODERATE
        st.warning(
            f"🟡 **中等租客（{score.total_score} 分）**：基本門檻雖過，但安全係數不夠。\n\n"
            "建議：要求加保證人 + 押金提高為 3 個月 + 租約公證後再決定是否簽約。"
        )


def render_chapter_3() -> None:
    """💰 租金精算與優質租客雷達（Chapter 3）— UI 入口。"""
    st.title("💰 租金精算與優質租客雷達")
    st.info(
        "💡 **學長的實戰金句**：「寧可空租一個月，也不要租給麻煩客。"
        "租客選錯，整年白做工；房子被搞爛，五年的租金都不夠補。」"
    )

    tab_pricing, tab_radar = st.tabs(
        ["🎯 滿租科學定價計算機", "🛡️ 租客七道信用防線雷達"]
    )

    with tab_pricing:
        _render_pricing_tab()
    with tab_radar:
        _render_radar_tab()
