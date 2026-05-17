"""Chapter 4 UI — 貸款槓桿與科目四過水密技（重構後）。

UI 層：純 widgets + 渲染；增貸 + 科目四階段判定由 services.leverage。
"""

from __future__ import annotations

import streamlit as st

from app.services.leverage import (
    calculate_building_gap,
    diagnose_wash_progress,
)
from app.ui.components.metric_grid import render_metric_row


WASH_STAGE_LABELS: list[str] = [
    "未啟動", "資金已增貸", "資金已過水", "工具持有中", "已洗白",
]
WASH_SAFETY_LABELS: list[str] = [
    "🔴 高風險", "🟠 進行中", "🟡 部分過水", "🟢 即將完成", "✅ 安全",
]


def _render_gap_tab() -> None:
    st.subheader("💎 整棟大廈價差／增貸計算機")
    st.caption("學長公式：(同棟最高單價 − 你的目標單價) × 權狀坪數 = 潛在增貸空間")

    col_a, col_b = st.columns(2)
    with col_a:
        max_unit_price_wan = st.number_input(
            "同棟／同社區最高實價登錄單價（萬／坪）",
            min_value=0.0, value=70.0, step=0.5, format="%.1f",
            help="去『實價登錄』撈同棟最近一年成交記錄，取最高那筆當銀行估價的天花板。",
            key="ch4_max_unit_price",
        )
        target_unit_price_wan = st.number_input(
            "你的目標出價單價（萬／坪）",
            min_value=0.0, value=60.0, step=0.5, format="%.1f",
            help="你計劃簽約成交的單價。越低，可拗的價差越大。",
            key="ch4_target_unit_price",
        )
    with col_b:
        ping_size = st.number_input(
            "房屋權狀坪數（坪）",
            min_value=0.0, value=30.0, step=0.5, format="%.1f",
            key="ch4_ping_size",
        )

    result = calculate_building_gap(
        max_unit_price_wan=float(max_unit_price_wan),
        target_unit_price_wan=float(target_unit_price_wan),
        ping_size=float(ping_size),
    )

    st.markdown("---")
    st.markdown("##### 📊 銀行估價拆解")
    render_metric_row([
        {
            "label": "同棟最高總價",
            "value": f"{result.total_max_price_wan:,.1f} 萬",
            "help": f"{max_unit_price_wan:.1f} 萬／坪 × {ping_size:.1f} 坪",
        },
        {
            "label": "你的目標總價",
            "value": f"{result.total_target_price_wan:,.1f} 萬",
            "help": f"{target_unit_price_wan:.1f} 萬／坪 × {ping_size:.1f} 坪",
        },
        {
            "label": "單坪價差",
            "value": f"{result.unit_gap_wan:+.1f} 萬／坪",
            "delta": (
                f"{(result.unit_gap_wan / max_unit_price_wan * 100):.1f}%"
                if max_unit_price_wan > 0 else None
            ),
        },
    ])

    st.metric(
        "💰 預估未來可超額增貸空間", f"{result.potential_refinance_gap_wan:,.1f} 萬",
        delta=(
            f"{(result.potential_refinance_gap_wan / result.total_target_price_wan * 100):.1f}% of 出價"
            if result.total_target_price_wan > 0 else None
        ),
        help="交屋後 6 個月以上向銀行申請增貸時，可能拗出來的合法現金。",
    )

    if result.potential_refinance_gap_wan > 0:
        st.info(
            "💡 **銀行估價看整棟！** 只要你買得比高價戶便宜，"
            "這個價差就是你交屋後能從銀行『搬出來的合法現金』！\n\n"
            f"以你目前的數字：交屋滿 6 個月後申請增貸，"
            f"有機會合法拿出 **{result.potential_refinance_gap_wan:,.1f} 萬**，"
            "再轉投入下一間或做其他金融操作。"
        )
    elif result.potential_refinance_gap_wan == 0:
        st.warning(
            "⚠️ 出價與同棟最高價持平，**沒有價差套利空間**。"
            "建議再殺價或換物件。"
        )
    else:
        st.error(
            f"❌ 你的出價比同棟最高價還貴 **{-result.potential_refinance_gap_wan:,.1f} 萬**！"
            "這是『追高』的買法，銀行估價可能不到，**自備款會被迫拉高**。"
        )


def _render_wash_tab() -> None:
    st.subheader("🌊 科目四洗白過水追蹤器")
    st.caption(
        "資金來源分流時間軸：科目四（理財／裝潢貸）→ 他行 → 金融工具 → 滿 1 年 → 重回科目一"
    )

    st.error(
        "⚠️ **絕對紅線：** 不可在『未滿一年』內直接拿這筆錢買房，"
        "或用它還清舊房貸再馬上借出——**極可能被銀行 Call Loan、信用全毀！**"
    )

    st.markdown("---")
    st.markdown("##### 🛤️ 四階段過水時間軸")

    step1 = st.checkbox(
        "**步驟 1**：已用『理財／透天裝潢』名義從原銀行增貸出資金（科目四）",
        key="ch4_wash_step1",
        help="原房貸增貸或信貸均可，重點是名目不是『購屋』。",
    )
    step2 = st.checkbox(
        "**步驟 2**：已將資金轉出至『他行帳戶』並設定 3 個月定存（建立資金斷點）",
        key="ch4_wash_step2",
        help="一定要轉到不同銀行，並做定存才有完整的『金流軌跡』可佐證。",
        disabled=not step1,
    )
    step3 = st.checkbox(
        "**步驟 3**：定存解約，已投入 0050／保單等金融工具，並保留對帳單證據",
        key="ch4_wash_step3",
        help="證據要齊：申購對帳單、配息紀錄、贖回明細都要存。",
        disabled=not step2,
    )
    step4 = st.checkbox(
        "**步驟 4**：資金已在金融工具放滿『1 年以上』",
        key="ch4_wash_step4",
        help="銀行追金流通常只查 6~12 個月內，滿 1 年安全係數最高。",
        disabled=not step3,
    )

    progress = diagnose_wash_progress((step1, step2, step3, step4))
    completed = progress.completed_steps

    st.markdown("---")
    st.markdown("##### 📊 過水進度")
    p1, p2, p3 = st.columns(3)
    p1.metric("完成步驟", f"{completed} / 4")
    p2.metric("目前階段", WASH_STAGE_LABELS[completed])
    p3.metric("安全等級", WASH_SAFETY_LABELS[completed])
    st.progress(completed / 4)

    if step3 and not step4:
        st.info(
            "💡 **若遇銀行抽查，請拿出對帳單回覆**：\n\n"
            "> 「發現自己不會投資、睡不好所以賣掉」\n\n"
            "這是合法且合理的理由，搭配申購／贖回對帳單就是完整證據鏈。"
        )

    if progress.is_whitened:
        st.success(
            "🚀 **資金已徹底洗白！**\n\n"
            "現在你可以合法變現，轉去買下一間房子，"
            "重回 **低利息的科目一（購屋貸款）** 循環！\n\n"
            "👉 **下一步建議：**\n"
            "1. 鎖定下一間目標物件（單價要再壓低）\n"
            "2. 向不同銀行詢價，搶 2 段式利率\n"
            "3. 把剛贖回的金融工具當作『新自備款來源』"
        )


def render_chapter_4() -> None:
    """🏦 槓桿魔法：科目四金流過水 SOP（Chapter 4）— UI 入口。"""
    st.title("🏦 槓桿魔法：科目四金流過水 SOP")
    st.info(
        "💡 **學長的實戰金句**：「銀行看的不是你有多少錢，是你『看起來』有多少錢。"
        "金流要做給銀行看、自備款要做給代書看——數字會說話，但你要先教它怎麼說。」"
    )

    tab_gap, tab_wash = st.tabs(
        ["💎 整棟大廈價差／增貸計算機", "🌊 科目四洗白過水追蹤器"]
    )

    with tab_gap:
        _render_gap_tab()
    with tab_wash:
        _render_wash_tab()
