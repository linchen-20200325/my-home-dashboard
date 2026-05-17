"""Chapter 7 UI — 安全離場策略與房地合一稅防禦（重構後）。

UI 層：純 widgets + 渲染；脫手年限推演 + 鐵證強度由 services.liquidity 計算。
"""

from __future__ import annotations

import streamlit as st

from app.models.constants import EXIT_AGE_RED_LINE_YEARS
from app.services.liquidity import (
    ResidencyStrength,
    calculate_exit_age,
    diagnose_residency_evidence,
)
from app.ui.components.metric_grid import render_metric_row


RESIDENCY_CHECKS: list[tuple[str, str]] = [
    ("① 本人、配偶或直系親屬已於該址『辦竣戶籍登記』", "ch7_res_household"),
    ("② 持有滿 5 年期間，絕對『無出租、無營業』使用", "ch7_res_no_rent"),
    ("③ 已收集並保留該址之『水電費帳單』且有實際使用度數", "ch7_res_utility"),
    ("④ 已保留寄送至該址的『網購包裹收據／信用卡帳單』", "ch7_res_parcel"),
    ("⑤ 擁有周邊商家的『日常消費發票』或鄰近診所之『就醫紀錄』", "ch7_res_receipt"),
]

# 鐵證強度顯示（對應已備齊證據數 0-5）
_STRENGTH_LADDER = [
    "🔴 薄弱", "🟠 不足", "🟡 普通", "🟢 紮實", "🟢 紮實", "🛡️ 滴水不漏",
]


def _render_exit_age_calculator() -> None:
    st.subheader("⏳ 老屋脫手年限逆推器")
    st.caption("學長公式：脫手時屋齡 = 目前屋齡 + 預計持有年限（35 年是紅線）")

    current_age = st.number_input(
        "欲購買物件之目前屋齡（年）", min_value=0, max_value=80, value=20, step=1,
        help="權狀上『建築完成日期』推算到今天。", key="ch7_current_age",
    )
    holding_years = st.number_input(
        "預計持有收租／自住年限（年）", min_value=0, max_value=50, value=10, step=1,
        help="你預計幾年後賣出？要把房地合一 5 年門檻一併考慮進去。",
        key="ch7_holding_years",
    )

    result = calculate_exit_age(int(current_age), int(holding_years))

    st.markdown("---")
    st.markdown("##### 📊 脫手時點推演")
    render_metric_row([
        {"label": "脫手時屋齡", "value": f"{result.exit_age} 年"},
        {
            "label": "下一手可貸年期",
            "value": f"{result.max_bank_loan_years} 年",
            "help": "銀行貸款年期上限：min(50 − 屋齡, 30)。",
        },
        {
            "label": "紅線距離",
            "value": f"{result.distance_to_red_line:+d} 年",
            "delta_color": "inverse",
            "help": f"以屋齡 {EXIT_AGE_RED_LINE_YEARS} 年為轉手紅線。",
        },
    ])

    st.markdown("---")
    if result.is_over_red_line:
        st.error(
            f"⚠️ **危險！脫手時屋齡高達 {result.exit_age} 年。**\n\n"
            "下一手買家將無法向銀行貸滿 30 年（受限於 **RC 耐用 50 年**），"
            "這會導致你的房子**極難轉手**！\n\n"
            "👉 **學長建議：** 請縮短持有年限或放棄此案。\n"
            "_（註：台北市精華區、捷運共構或都更熱區可酌情放寬。）_"
        )
    else:
        st.success(
            f"✅ **流動性安全！** 脫手時屋齡 {result.exit_age} 年仍在 "
            f"{EXIT_AGE_RED_LINE_YEARS} 年紅線內，"
            "下一手買方依然能順利申請長年期房貸，不影響房屋價值。"
        )


def _render_residency_checklist() -> None:
    st.subheader("🏠 自用 5 年免稅鐵證清單")
    st.caption(
        "房地合一稅 2.0 要享自用住宅免稅／優惠稅率，國稅局查極嚴——"
        "必須親手製造『生活軌跡』。"
    )

    st.info(
        "📚 **重點提醒：** 自用住宅優惠稅率 10%（vs 重稅 45%），"
        "前提是『本人或配偶、未成年子女設籍 + 連續居住滿 6 年』，"
        "且**前 5 年沒有出租、營業或執行業務**。"
    )

    checked = tuple(st.checkbox(label, key=key) for label, key in RESIDENCY_CHECKS)
    verdict = diagnose_residency_evidence(checked)

    st.markdown("---")
    st.markdown("##### 📊 鐵證強度")
    c1, c2 = st.columns(2)
    c1.metric("已備齊證據", f"{verdict.evidence_count} / {verdict.total_evidence}")
    c2.metric("鐵證強度", _STRENGTH_LADDER[verdict.evidence_count])
    st.progress(verdict.evidence_count / verdict.total_evidence)

    if verdict.strength == ResidencyStrength.IRONCLAD:
        st.info(
            "🛡️ **恭喜！你已經建立了堅不可摧的生活軌跡鐵證**，"
            "國稅局查帳也不怕，完美守住**數百萬的資本利得**！\n\n"
            "👉 **賣屋前最後檢查：**\n"
            "1. 戶籍謄本影本（證明連續設籍）\n"
            "2. 近 5 年水電帳單彙整\n"
            "3. 申報自用稅率時主動附上證據包，加速核定"
        )
    elif verdict.strength == ResidencyStrength.GAPPED:
        st.warning(
            f"🟡 已備齊 {verdict.evidence_count} / {verdict.total_evidence} 項，"
            "證據強度尚可但**仍有破口**。建議補齊剩餘項目後再進行賣屋，"
            "以免被認定為非自用、課重稅。"
        )
    else:
        st.error(
            f"🚫 僅備齊 {verdict.evidence_count} / {verdict.total_evidence} 項，"
            "生活軌跡明顯不足。若現在賣屋，**極可能被國稅局否准自用稅率**，"
            "課徵 35%~45% 重稅。"
        )


def render_chapter_7() -> None:
    """🚪 安全離場與流動性評估（Chapter 7）— UI 入口。"""
    st.title("🚪 安全離場與流動性評估")
    st.info(
        "💡 **學長的實戰金句**：「會買的是徒弟，會賣的才是師父。"
        "離場時機決定報酬率，流動性決定你能不能在『想下車時』下車——"
        "別讓自己成為最後一棒。」"
    )

    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        _render_exit_age_calculator()
    with col_right:
        _render_residency_checklist()
