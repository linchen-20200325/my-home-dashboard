"""Chapter 1 UI — 首頁與個人現金流診斷（重構後）。

UI 層：
    - 嚴禁直接寫公式 / 商業邏輯（DTI / M2 / severity 全由 services 計算）
    - 嚴禁 import openai / repositories（透過 services 中介）
    - 只依賴 streamlit + plotly + app.{models, services}
"""

from __future__ import annotations

import math

import plotly.graph_objects as go
import streamlit as st

from app.models.cashflow import CashflowInput, CashflowSeverity
from app.models.constants import (
    DTI_DANGER_RATIO,
    M2_BANK_DEPOSIT_ANNUAL_RATE,
    M2_INITIAL_CAPITAL_NTD,
    M2_SIMULATION_YEARS,
)
from app.services.cashflow import LOW_BUFFER_THRESHOLD_NTD, diagnose_cashflow
from app.services.leverage import simulate_m2_decade
from app.ui.components.metric_grid import render_metric_row

# Cross-chapter navigation helpers 透過 function-level import 引入，
# 因為 ``app.ui.router`` 反向 import 本 UI 模組，top-level import 會循環。


def _render_cashflow_tab() -> None:
    """分頁一：階級現金流診斷儀。"""
    st.subheader("💸 階級現金流診斷儀")
    st.caption("學長心法：『窮人賣時間，中產賣資產，富人買現金流。』")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        total_income = st.number_input(
            "月薪 + 被動收入總和（元）",
            min_value=0,
            value=80_000,
            step=5_000,
            help="主動勞動所得 + 股息／租金等被動收入。",
            key="ch1_total_income",
        )
    with col_b:
        living_cost = st.number_input(
            "每月基本生活費（元）",
            min_value=0,
            value=30_000,
            step=1_000,
            help="吃、住、交通、保險等剛性支出，**不含任何貸款**。",
            key="ch1_living_cost",
        )
    with col_c:
        existing_mortgage = st.number_input(
            "現有房貸月付金（元）",
            min_value=0,
            value=0,
            step=1_000,
            help="若已有自住或投資房，每月應繳房貸；無則填 0。",
            key="ch1_existing_mortgage",
        )

    st.caption("👇 中產毒藥負債（會消耗現金流的『偽資產』負債）：")
    col_d, col_e, col_f, col_g = st.columns(4)
    with col_d:
        car_loan = st.number_input(
            "車貸月付（元）",
            min_value=0,
            value=0,
            step=500,
            key="ch1_car_loan",
        )
    with col_e:
        personal_loan = st.number_input(
            "信貸月付（元）",
            min_value=0,
            value=0,
            step=500,
            key="ch1_personal_loan",
        )
    with col_f:
        credit_card_min = st.number_input(
            "卡債最低應繳（元）",
            min_value=0,
            value=0,
            step=500,
            help="信用卡循環利率 15%，務必先還清。",
            key="ch1_credit_card_min",
        )
    with col_g:
        other_debt = st.number_input(
            "其他貸款月付（元）",
            min_value=0,
            value=0,
            step=500,
            help="學貸、就學貸款、其他分期等。",
            key="ch1_other_debt",
        )

    # ---------- 委派給 service ----------
    snapshot = diagnose_cashflow(CashflowInput(
        total_income_ntd=int(total_income),
        living_cost_ntd=int(living_cost),
        existing_mortgage_ntd=int(existing_mortgage),
        car_loan_ntd=int(car_loan),
        personal_loan_ntd=int(personal_loan),
        credit_card_min_ntd=int(credit_card_min),
        other_debt_ntd=int(other_debt),
    ))

    # ---------- 渲染 metrics ----------
    st.markdown("---")
    st.markdown("##### 📊 學長現金流四維診斷")
    dti_is_inf = math.isinf(snapshot.dti)
    render_metric_row([
        {"label": "總收入", "value": f"{total_income:,.0f} 元"},
        {
            "label": "淨現金流",
            "value": f"{snapshot.net_cashflow_ntd:,.0f} 元",
            "delta": (
                f"{(snapshot.net_cashflow_ntd / total_income * 100):.0f}% of 收入"
                if total_income > 0 else None
            ),
            "delta_color": "normal" if snapshot.net_cashflow_ntd >= 0 else "inverse",
        },
        {
            "label": "每月總負債",
            "value": f"{snapshot.total_debt_ntd:,.0f} 元",
            "help": "現有房貸 + 車貸 + 信貸 + 卡債最低 + 其他。",
        },
        {
            "label": "DTI 總負債比",
            "value": f"{snapshot.dti * 100:.1f} %" if not dti_is_inf else "—",
            "delta": (
                f"{(snapshot.dti - DTI_DANGER_RATIO) * 100:+.1f} pp vs 70%"
                if not dti_is_inf else None
            ),
            "delta_color": "inverse",
            "help": "每月總負債 / 總收入。銀行死線為 70%。",
        },
    ])

    st.markdown("---")

    # ---------- 中產毒藥警告（與 severity 正交，可同時觸發）----------
    if snapshot.has_bad_debt:
        st.warning(
            "⚠️ **中產階級毒藥警告！**\n\n"
            "你買入了**消耗現金流的『偽資產』**——車子、3C、信貸投資⋯⋯"
            "這些東西的價值會隨時間歸零，但每個月吃掉你的薪水。\n\n"
            "**真正的富人只買能產生『正向現金流』的收租房**：\n"
            "- 房客幫你還房貸（負債轉嫁）\n"
            "- 每月有正現金流入帳（被動收入）\n"
            "- 標的本身隨通膨增值（資產升值）\n\n"
            "👉 **學長急救清單：**\n"
            "1. **車貸／信貸 → 提前還清**（即使要動到緊急預備金）\n"
            "2. **卡債循環利率 15% → 切換為信貸 3-5%** 救急\n"
            "3. **未還清前不可買房**——銀行聯徵會直接砍成數"
        )

    # ---------- severity → UI 面板映射 ----------
    if snapshot.severity == CashflowSeverity.DTI_LOCKED:
        st.error(
            f"🚫 **銀行核貸死線！** 你的 DTI = **{snapshot.dti * 100:.1f}%** > 70%。\n\n"
            "在銀行眼中你是『現金流隨時會斷氣』的高風險戶：\n"
            "- **成數被大砍**（一般 7-8 成 → 可能只給 5-6 成）\n"
            "- **利率被加碼**（一般 2.0% → 可能 2.3-2.5%）\n"
            "- **嚴重者直接拒貸**，連看屋的資格都沒有\n\n"
            "👉 **學長先理債再買房：**\n"
            "1. 把壞債從 DTI 公式裡『刪掉』（提前還清）\n"
            "2. 半年後重跑聯徵，分數養回來再進場\n"
            "3. **DTI < 60% 才是真正安全水位**"
        )
    elif snapshot.severity == CashflowSeverity.NEGATIVE:
        st.error(
            f"🚫 **現金流已破口！** 每月赤字 **{-snapshot.net_cashflow_ntd:,.0f} 元**——"
            "你現在連『活著』都靠借貸，買房只會加速破產。"
        )
    elif snapshot.severity == CashflowSeverity.LOW_BUFFER:
        st.warning(
            f"🟡 淨現金流 {snapshot.net_cashflow_ntd:,.0f} 元偏低，"
            f"建議先增加被動收入或減少生活費，"
            f"把『可投資現金』撐到 {LOW_BUFFER_THRESHOLD_NTD // 10_000} 萬以上再進場。"
        )
    else:  # HEALTHY
        st.success(
            f"✅ **體質健康！** 淨現金流 {snapshot.net_cashflow_ntd:,.0f} 元、"
            f"DTI {snapshot.dti * 100:.1f}%，"
            "可以開始認真看物件了。下一步：去 Ch.3 算租金、Ch.4 拗增貸。"
        )
        # ----- Cross-chapter 快速跳轉（避免使用者翻 sidebar）-----
        # 延後 import 避免 chapter / router / navigation 形成循環依賴。
        from app.ui.components.navigation import chapter_jump_button as _jump
        from app.ui.router import CHAPTER_KEY_CH3, CHAPTER_KEY_CH4
        col_nav_a, col_nav_b = st.columns(2)
        with col_nav_a:
            _jump("💰 去 Ch.3 算租金 →", CHAPTER_KEY_CH3,
                  button_key="ch1_jump_ch3", use_container_width=True)
        with col_nav_b:
            _jump("🏦 去 Ch.4 拗增貸 →", CHAPTER_KEY_CH4,
                  button_key="ch1_jump_ch4", use_container_width=True)


def _render_m2_tab() -> None:
    """分頁二：M2 貨幣與資產計算機。"""
    st.subheader("💱 M2 貨幣與資產計算機")
    st.caption("學長心法：『定存族不是輸給房地產，是輸給央行的印鈔機。』")

    inflation_rate = st.slider(
        "預估未來 10 年通膨與印鈔（M2）年化貶值率（%）",
        min_value=0.0,
        max_value=15.0,
        value=5.0,
        step=0.5,
        help="台灣 M2 年增率長期約 5-7%，輸入你最悲觀 / 樂觀的預估值。",
        key="ch1_inflation_rate",
    )

    # ---------- 委派給 service ----------
    sim = simulate_m2_decade(inflation_rate / 100)

    st.markdown("---")
    st.markdown(
        f"##### 📊 起點 **{M2_INITIAL_CAPITAL_NTD / 10_000:,.0f} 萬**，"
        f"{M2_SIMULATION_YEARS} 年後對決"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("###### 🏦 方案 A：放銀行定存")
        st.metric(
            f"{M2_SIMULATION_YEARS} 年後名目金額",
            f"{sim.deposit_nominal_ntd / 10_000:,.1f} 萬",
            delta=f"+{(sim.deposit_nominal_ntd - M2_INITIAL_CAPITAL_NTD) / 10_000:,.1f} 萬",
            help=f"{M2_BANK_DEPOSIT_ANNUAL_RATE * 100:.1f}% 年息複利。",
        )
        st.metric(
            f"{M2_SIMULATION_YEARS} 年後『實質購買力』",
            f"{sim.deposit_real_ntd / 10_000:,.1f} 萬",
            delta=f"{(sim.deposit_real_ntd - M2_INITIAL_CAPITAL_NTD) / 10_000:+,.1f} 萬",
            delta_color=(
                "inverse"
                if sim.deposit_real_ntd < M2_INITIAL_CAPITAL_NTD
                else "normal"
            ),
            help="扣除通膨後，真正能買到的東西。",
        )
    with col_b:
        st.markdown("###### 🏘️ 方案 B：5 倍槓桿買房")
        property_appreciation = sim.property_final_nominal_ntd - sim.property_initial_value_ntd
        st.metric(
            f"買 {sim.property_initial_value_ntd / 10_000:,.0f} 萬房 → "
            f"{M2_SIMULATION_YEARS} 年後房價",
            f"{sim.property_final_nominal_ntd / 10_000:,.1f} 萬",
            delta=f"+{property_appreciation / 10_000:,.1f} 萬（全歸你）",
            help="漲幅全部進到你口袋，因為房貸金額是固定的。",
        )
        st.metric(
            f"{M2_SIMULATION_YEARS} 年後『實質購買力』",
            f"{sim.equity_real_ntd / 10_000:,.1f} 萬",
            delta=f"{(sim.equity_real_ntd - M2_INITIAL_CAPITAL_NTD) / 10_000:+,.1f} 萬",
            delta_color=(
                "normal"
                if sim.equity_real_ntd >= M2_INITIAL_CAPITAL_NTD
                else "inverse"
            ),
        )

    st.markdown("---")

    # ---------- 對比長條圖 ----------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="名目金額",
            x=["🏦 銀行定存", "🏘️ 5 倍槓桿買房"],
            y=[sim.deposit_nominal_ntd / 10_000, sim.equity_nominal_ntd / 10_000],
            marker_color=["#9CA3AF", "#10B981"],
            text=[
                f"{sim.deposit_nominal_ntd / 10_000:,.0f} 萬",
                f"{sim.equity_nominal_ntd / 10_000:,.0f} 萬",
            ],
            textposition="outside",
            hovertemplate="%{x}<br>名目：%{y:,.1f} 萬<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="實質購買力（扣通膨）",
            x=["🏦 銀行定存", "🏘️ 5 倍槓桿買房"],
            y=[sim.deposit_real_ntd / 10_000, sim.equity_real_ntd / 10_000],
            marker_color=["#D1D5DB", "#34D399"],
            text=[
                f"{sim.deposit_real_ntd / 10_000:,.0f} 萬",
                f"{sim.equity_real_ntd / 10_000:,.0f} 萬",
            ],
            textposition="outside",
            hovertemplate="%{x}<br>實質：%{y:,.1f} 萬<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{M2_SIMULATION_YEARS} 年後資產對決（通膨 {inflation_rate:.1f}% / 年）",
        barmode="group",
        height=420,
        yaxis_title="金額（萬）",
        showlegend=True,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---------- 學長結論 ----------
    mortgage_amount = sim.property_initial_value_ntd - M2_INITIAL_CAPITAL_NTD
    st.info(
        "💡 **房價上漲的本質是法幣超發！**\n\n"
        "央行印鈔（M2 擴張）→ 錢變多 → 每塊錢購買力下降 → 實物資產（房子、黃金）漲價。\n\n"
        f"你借的 **{mortgage_amount / 10_000:,.0f} 萬房貸**，"
        f"{M2_SIMULATION_YEARS} 年後用『貶值後的錢』還，等於——\n\n"
        "👉 **借低息房貸買房 = 讓通膨幫你還債！**\n\n"
        f"**這個案例：5 倍槓桿比定存多賺 {sim.leverage_advantage_ntd / 10_000:+,.1f} 萬"
        "（實質購買力）。**通膨愈高，這個差距會愈大——把滑桿拉到 10% 看看就知道了。"
    )

    if inflation_rate >= 7:
        st.warning(
            f"🟠 你預估的通膨 {inflation_rate:.1f}% 已偏高，"
            "意味『現金族被通膨洗劫』的情境很嚴峻——**愈晚進場代價愈高**。"
        )
    elif inflation_rate <= 2:
        st.caption(
            "🔵 你預估的通膨偏低，槓桿優勢會縮小。但歷史告訴我們：央行印鈔機從未停下。"
        )


def render_chapter_1() -> None:
    """🏠 首頁與個人現金流診斷（Chapter 1）— UI 入口。"""
    st.title("🏠 首頁與個人現金流診斷")
    st.info(
        "💡 **學長的實戰金句**：「**買房不是看你賺多少，是看你『留』下多少。**\n"
        "現金流就是你的氧氣，氧氣斷掉那天，就是被強制下車那天。」"
    )

    tab_cashflow, tab_m2 = st.tabs(
        ["💸 階級現金流診斷儀", "💱 M2 貨幣與資產計算機"]
    )

    with tab_cashflow:
        _render_cashflow_tab()

    with tab_m2:
        _render_m2_tab()
