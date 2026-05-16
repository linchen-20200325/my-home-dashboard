"""
買房前自我能力與現金流健檢（整合完整版）
整合三份 Excel 公式：
  1. 05768 完整版：PMT 房貸引擎、寬限期、現金流、投資回收、房價增值3情境、利率/空租風險
  2. 1e812 懶人包：租金安全指數、底線租金
  3. 5f74150 個人負債比與房貸能力試算 + 反推所需月收入
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ===================== 頁面基礎設定 =====================
st.set_page_config(
    page_title="買房前自我能力與現金流健檢",
    page_icon="🏠",
    layout="wide",
)


# ===================== 公式工具函式 =====================
def pmt(monthly_rate: float, n_periods: int, principal: float) -> float:
    """本息平均攤還月付金（對應 Excel PMT）"""
    if n_periods <= 0 or principal <= 0:
        return 0.0
    if monthly_rate <= 0:
        return principal / n_periods
    factor = (1 + monthly_rate) ** n_periods
    return principal * monthly_rate * factor / (factor - 1)


def amortization_schedule(principal, annual_rate, years, grace_years=0):
    """逐月攤還表：月付金、利息、本金、剩餘本金"""
    monthly_rate = annual_rate / 12
    total_m = int(years * 12)
    grace_m = int(min(grace_years, years) * 12)
    pay_m = total_m - grace_m

    grace_pay = principal * monthly_rate
    post_pay = pmt(monthly_rate, pay_m, principal) if pay_m > 0 else 0.0

    rows = []
    balance = principal
    for m in range(1, total_m + 1):
        if m <= grace_m:
            payment = grace_pay
            interest = principal * monthly_rate
            principal_paid = 0.0
        else:
            payment = post_pay
            interest = balance * monthly_rate
            principal_paid = payment - interest
            balance = max(balance - principal_paid, 0.0)
        rows.append(
            {
                "期數": m,
                "年度": (m - 1) // 12 + 1,
                "月付金": payment,
                "利息": interest,
                "本金": principal_paid,
                "剩餘本金": balance,
            }
        )
    return pd.DataFrame(rows)


# ===================== 標題區 =====================
st.title("🏠 買房前自我能力與現金流健檢")
st.caption(
    "整合三份實戰試算表：階級現金流診斷 × 貸款資格 × PMT 房貸引擎 × "
    "投資收益 × 風險壓力測試 × 租金安全懶人包。所有數字會跟著側邊欄即時連動。"
)


# ===================== 側邊欄（僅放共用基本資料）=====================
with st.sidebar:
    st.header("📋 共用基本資料")
    st.caption("這三組是跨分頁共用的參數；其餘分頁專屬參數已移到各分頁上方。")

    with st.expander("👤 個人基本條件", expanded=True):
        age = st.number_input("目前年齡", 18, 80, 30, 1)
        loan_years = st.number_input("預計申請貸款年限（年）", 10, 40, 30, 5)

    with st.expander("💰 每月收入", expanded=True):
        st.caption("三項收入分開填寫，系統會自動加總（獎金÷12 均攤回每月），請勿重複計入。")
        monthly_salary = st.number_input(
            "① 每月本薪（稅後實領，不含獎金）",
            0,
            value=60_000,
            step=1_000,
            help="勞動所得的固定月薪，已扣除勞健保、稅款後的『實領金額』；不要把年終、季獎、加班費塞進來。",
        )
        annual_bonus = st.number_input(
            "② 每年獎金（年終、季獎、績效獎金總和）",
            0,
            value=120_000,
            step=10_000,
            help="一整年所有非固定的獎金加總（年終 + 季獎 + 績效 + 三節），系統會自動 ÷12 均攤到每月。若無則填 0。",
        )
        other_income = st.number_input(
            "③ 每月其他固定收入（兼職、租金、股息、利息）",
            0,
            value=0,
            step=1_000,
            help="本薪以外、每月或可換算成每月的穩定現金流（兼差、副業、房租收入、配息）。一次性收入不要填。",
        )
        st.markdown(
            f"**合計每月可用收入：NT$ "
            f"{monthly_salary + annual_bonus / 12 + other_income:,.0f}**"
        )

    with st.expander("💸 每月支出（不含房貸）", expanded=True):
        st.caption("房貸另在『基本資料』分頁的房屋條件中計算，這裡只填非房貸的固定支出。")
        monthly_bad_debt = st.number_input(
            "壞債支出（信貸／車貸／卡循／現金卡）",
            0,
            value=10_000,
            step=1_000,
            help="每月需固定還款的高利率負債：信用貸款、車貸、信用卡循環利息、現金卡。房貸不算。",
        )
        monthly_living = st.number_input(
            "生活開銷（含保險娛樂、孝親費）",
            0,
            value=25_000,
            step=1_000,
            help="日常吃喝、交通、水電瓦斯、通訊、保險費月攤、娛樂、孝親費等扣除房貸與壞債後的所有開銷。",
        )
        st.markdown(
            f"**合計每月固定支出：NT$ {monthly_bad_debt + monthly_living:,.0f}**"
        )

    with st.expander("🏦 財力證明", expanded=False):
        total_assets = st.number_input("名下總資產估值", 0, value=2_000_000, step=10_000)
        total_liabilities = st.number_input("名下總負債餘額", 0, value=500_000, step=10_000)
        cash_reserve = st.number_input("現金存款（緊急預備金來源）", 0, value=500_000, step=10_000)


# ===================== 共用核心計算（僅依賴側邊欄）=====================
total_monthly_income = monthly_salary + annual_bonus / 12 + other_income
total_monthly_expense = monthly_living + monthly_bad_debt
monthly_surplus = total_monthly_income - total_monthly_expense
bad_debt_ratio = monthly_bad_debt / total_monthly_income if total_monthly_income > 0 else 0.0
age_plus_loan = age + loan_years
asset_liability_ratio = (
    total_assets / total_liabilities if total_liabilities > 0 else float("inf")
)


# ===================== 分頁區 =====================
(
    tab_basic,
    tab_location,
    tab_builder,
    tab_presale,
    tab_used,
    tab_inspect,
    tab_rental,
    tab_faq,
) = st.tabs(
    [
        "🩺 基本資料",
        "📍 選址",
        "🏗️ 挑建商",
        "🏠 預售屋",
        "🏚️ 中古屋",
        "✅ 驗屋",
        "💵 房屋出租",
        "💡 財富迷思 FAQ",
    ]
)

# ---- 主分頁參數設定 + 子分頁宣告 ----
with tab_basic:
    st.caption("💡 流程第一步：先看自己能不能買、能買多少、現金流撐不撐得起。")
    with st.container(border=True):
        st.markdown("##### 🏠 房屋與貸款條件（房貸 / 現金流共用）")
        loan_col_a, loan_col_b = st.columns(2)
        with loan_col_a:
            house_price = st.number_input("房屋總價", 0, value=10_000_000, step=100_000, key="loan_house_price")
            down_payment = st.number_input("自備款", 0, value=2_000_000, step=100_000, key="loan_down_payment")
            renovation = st.number_input("裝潢費用", 0, value=300_000, step=10_000, key="loan_renovation")
        with loan_col_b:
            other_fees = st.number_input("其他費用（代書/稅費）", 0, value=50_000, step=10_000, key="loan_other_fees")
            annual_rate_pct = st.number_input(
                "貸款年利率（%）", 0.0, 10.0, 2.5, 0.05, format="%.2f", key="loan_rate_pct",
            )
            grace_years = st.number_input("寬限期（年，只繳利息）", 0, 10, 5, 1, key="loan_grace_years")

    annual_rate = annual_rate_pct / 100
    loan_amount = max(house_price - down_payment, 0)
    ltv = loan_amount / house_price if house_price > 0 else 0
    total_investment = down_payment + renovation + other_fees
    monthly_rate = annual_rate / 12
    total_months = int(loan_years * 12)
    grace_months = int(min(grace_years, loan_years) * 12)
    pay_months = total_months - grace_months
    grace_payment = loan_amount * monthly_rate
    post_grace_payment = pmt(monthly_rate, pay_months, loan_amount) if pay_months > 0 else 0
    avg_monthly_payment = (
        (grace_payment * grace_months + post_grace_payment * pay_months) / total_months
        if total_months > 0 else 0
    )
    total_interest = (
        grace_payment * grace_months + post_grace_payment * pay_months - loan_amount
    )
    total_repayment = total_interest + loan_amount
    interest_ratio = total_interest / total_repayment if total_repayment > 0 else 0
    mortgage_dti = (
        (monthly_bad_debt + post_grace_payment) / total_monthly_income
        if total_monthly_income > 0 else 1.0
    )

    sub_check, sub_loan, sub_cash = st.tabs(
        ["🩺 個人體質檢測", "💰 房貸試算引擎", "📈 現金流還款分析"]
    )

with tab_rental:
    st.caption("💡 買到後的營運分析：估價、租金回收、風險、找好租客。")
    with st.container(border=True):
        st.markdown("##### 📈 租金與投資參數（投資/風險/懶人包/租客共用）")
        prop_col_a, prop_col_b = st.columns(2)
        with prop_col_a:
            rent = st.number_input("預估月租金", 0, value=35_000, step=1_000, key="inv_rent")
            mgmt_fee = st.number_input("月管理費＋稅", 0, value=2_000, step=500, key="inv_mgmt_fee")
            vacancy_months = st.number_input(
                "年度空租月數預估", 0, 12, 2, 1, key="risk_vacancy_months",
            )
        with prop_col_b:
            vacancy_discount = st.slider(
                "空置保守打折比例（懶人包公式）", 0.0, 0.5, 0.10, 0.01,
                help="0.10 代表打 9 折；越保守可拉到 0.20",
                key="inv_vacancy_discount",
            )
            repair_pct = st.slider(
                "維修小金庫（佔租金 %）", 0.0, 0.2, 0.05, 0.01,
                help="新屋預設 5%、老屋建議 10%",
                key="inv_repair_pct",
            )
            location_rating = st.select_slider(
                "房屋地段等級",
                options=[1, 2, 3, 4, 5],
                value=2,
                format_func=lambda x: {1: "1 精華", 2: "2 優良", 3: "3 一般", 4: "4 偏遠", 5: "5 極偏"}[x],
                key="risk_location",
            )

    sub_price, sub_invest, sub_risk, sub_lazy, sub_tenant = st.tabs(
        [
            "💲 估價與增貸",
            "🏠 投資收益情境",
            "⚠️ 風險壓力測試",
            "📋 租金安全懶人包",
            "🎯 優質租客雷達",
        ]
    )


# ======================================================
# Tab 1：體質檢測（原區塊一+區塊二）
# ======================================================
with sub_check:
    st.header("一、階級現金流與財富思維診斷")
    st.caption("PPT 第一課：『不是收入決定階級，而是現金流決定階級。』")

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "每月可用總收入",
        f"NT$ {total_monthly_income:,.0f}",
        help=f"本薪 {monthly_salary:,.0f} ＋ 年獎金 ÷12 ({annual_bonus / 12:,.0f}) ＋ 其他 {other_income:,.0f}",
    )
    c2.metric(
        "每月結餘",
        f"NT$ {monthly_surplus:,.0f}",
        delta=f"{monthly_surplus:,.0f}",
        delta_color="normal" if monthly_surplus >= 0 else "inverse",
    )
    c3.metric("壞債佔收入比", f"{bad_debt_ratio * 100:.1f}%")

    if monthly_surplus < 0:
        st.error(
            "⚠️ **窮人現金流：努力工作賺錢，然後把錢花光。**\n\n"
            "你目前的現金流是 **負的**，先專注節流並清除信用卡、卡循等壞債，"
            "把現金流拉回正號，才有資格進入下一階段。"
        )
    elif monthly_surplus > 0 and bad_debt_ratio > 0.15:
        st.warning(
            "⚠️ **中產階級迷思：把花錢的東西當成資產。**\n\n"
            f"結餘雖正（+NT$ {monthly_surplus:,.0f}），但壞債佔比 "
            f"{bad_debt_ratio * 100:.1f}%（>15%）。請先還清車貸／信貸／卡循，"
            "區分『好債（買生錢資產）』與『壞債（買花錢負債）』，才能開啟低利房貸槓桿。"
        )
    else:
        st.success(
            "✅ **富人現金流！恭喜你具備累積『好債』的能力。**\n\n"
            f"每月結餘 +NT$ {monthly_surplus:,.0f}，壞債比僅 {bad_debt_ratio * 100:.1f}%。"
            "下一步：建立信用、養財力證明，向銀行借低息房貸買進生錢資產。"
        )

    st.divider()
    st.header("二、房產貸款資格實戰檢核")
    st.caption("PPT 第二課：『銀行不是看你多有錢，是看你能不能還、值不值得借。』")

    ca, cb, cc = st.columns(3)
    ca.metric("年齡 + 貸款年限", f"{age_plus_loan} 年")
    cb.metric("壞債負債比（DTI）", f"{bad_debt_ratio * 100:.1f}%")
    cc.metric(
        "總資產 / 總負債",
        "∞ (無負債)" if total_liabilities == 0 else f"{asset_liability_ratio:.2f} 倍",
    )

    st.markdown("##### 🎯 檢核 1：年齡＋貸款年限 ≤ 75")
    if age_plus_loan > 75:
        st.error(
            f"⚠️ 年齡＋年限 = {age_plus_loan} 年，已超過 75 上限。"
            "銀行會自動縮短年限、月付金爆增。"
        )
    else:
        st.success(f"✅ 年齡＋年限 = {age_plus_loan} 年（≤ 75），通過第一道門檻。")

    st.markdown("##### 🎯 檢核 2：壞債負債比 < 70%")
    if bad_debt_ratio >= 0.70:
        st.error(f"⚠️ DTI = {bad_debt_ratio * 100:.1f}%，突破 70% 紅線，極可能被拒貸。")
    else:
        st.success(f"✅ DTI = {bad_debt_ratio * 100:.1f}%，安全通過。")

    st.markdown("##### 🎯 檢核 3：總資產負債比 > 1.5")
    if total_liabilities == 0:
        st.success("🚀 **無敵財力證明：你目前無任何負債！** 銀行幾乎搶著放款。")
    elif asset_liability_ratio > 1.5:
        st.success(
            f"🚀 **無敵財力證明：資產負債比 = {asset_liability_ratio:.2f} 倍！** "
            "可爭取最高成數＋最低利率。"
        )
    else:
        st.warning(
            f"⚠️ 資產負債比 = {asset_liability_ratio:.2f} 倍（≤ 1.5），財力證明偏弱。"
            "建議集中定存單、整理對帳單，6~12 個月後再送件。"
        )


# ======================================================
# Tab 2：房貸試算引擎（PMT + 寬限期 + 攤還曲線）
# ======================================================
with sub_loan:
    st.header("💰 房貸試算引擎（PMT + 寬限期）")
    st.caption("公式來源：Excel 房貸計算引擎 — PMT 本息攤還、寬限期只繳利息、利率敏感度。")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("貸款金額", f"NT$ {loan_amount:,.0f}")
    m2.metric("貸款成數 (LTV)", f"{ltv * 100:.1f}%")
    m3.metric("總投資成本", f"NT$ {total_investment:,.0f}", help="自備款＋裝潢＋其他費用")
    m4.metric("月利率", f"{monthly_rate * 100:.4f}%")

    st.markdown("##### 💳 月付金結構")
    p1, p2, p3 = st.columns(3)
    p1.metric("寬限期月付金", f"NT$ {grace_payment:,.0f}", help="僅繳利息")
    p2.metric("寬限期後月付金", f"NT$ {post_grace_payment:,.0f}", help="本息平均攤還")
    p3.metric("加權平均月付", f"NT$ {avg_monthly_payment:,.0f}")

    s1, s2, s3 = st.columns(3)
    s1.metric("總利息支出", f"NT$ {total_interest:,.0f}")
    s2.metric("總還款金額", f"NT$ {total_repayment:,.0f}")
    s3.metric("利息佔總還款", f"{interest_ratio * 100:.1f}%")

    st.markdown("---")
    st.markdown("##### 📉 攤還曲線（剩餘本金 + 每年本金/利息比例）")

    if loan_amount > 0 and total_months > 0:
        sched = amortization_schedule(loan_amount, annual_rate, loan_years, grace_years)
        annual = sched.groupby("年度").agg(
            年利息=("利息", "sum"),
            年本金=("本金", "sum"),
            年底剩餘=("剩餘本金", "last"),
        ).reset_index()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=annual["年度"], y=annual["年利息"],
                name="年繳利息", marker_color="#E74C3C",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=annual["年度"], y=annual["年本金"],
                name="年繳本金", marker_color="#27AE60",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=annual["年度"], y=annual["年底剩餘"],
                name="年底剩餘本金", mode="lines+markers",
                line=dict(color="#2C3E50", width=3),
            ),
            secondary_y=True,
        )
        fig.update_layout(
            barmode="stack",
            xaxis_title="貸款年度",
            yaxis_title="當年現金流出（元）",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=450,
            margin=dict(t=20, b=40),
        )
        fig.update_yaxes(title_text="當年現金流出（元）", secondary_y=False)
        fig.update_yaxes(title_text="剩餘本金（元）", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📑 完整逐月攤還表（前 24 期預覽）"):
            st.dataframe(
                sched.head(24).style.format(
                    {
                        "月付金": "{:,.0f}",
                        "利息": "{:,.0f}",
                        "本金": "{:,.0f}",
                        "剩餘本金": "{:,.0f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("請於側邊欄輸入房屋總價與自備款。")

    st.markdown("---")
    st.markdown("##### 📊 利率敏感度分析")
    if loan_amount > 0 and pay_months > 0:
        deltas = [-0.005, 0.0, 0.005, 0.01, 0.015, 0.02]
        rows = []
        base_pay = post_grace_payment
        for d in deltas:
            new_rate = annual_rate + d
            new_monthly_rate = new_rate / 12
            new_pay = pmt(new_monthly_rate, pay_months, loan_amount)
            rows.append(
                {
                    "利率情境": f"{new_rate * 100:.2f}%（{('+' if d >= 0 else '')}{d * 100:.1f}%）",
                    "新月付金": new_pay,
                    "月付增加": new_pay - base_pay,
                    "佔月收入比": new_pay / total_monthly_income if total_monthly_income > 0 else 0,
                }
            )
        df_rate = pd.DataFrame(rows)

        fig2 = go.Figure()
        fig2.add_trace(
            go.Bar(
                x=df_rate["利率情境"],
                y=df_rate["新月付金"],
                marker_color=["#3498DB" if d <= 0 else "#E67E22" if d <= 0.01 else "#C0392B" for d in deltas],
                text=[f"NT$ {v:,.0f}" for v in df_rate["新月付金"]],
                textposition="outside",
                name="月付金",
            )
        )
        fig2.update_layout(
            xaxis_title="利率情境",
            yaxis_title="月付金（元）",
            height=400,
            margin=dict(t=20, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(
            df_rate.style.format(
                {"新月付金": "{:,.0f}", "月付增加": "{:,.0f}", "佔月收入比": "{:.1%}"}
            ),
            use_container_width=True,
            hide_index=True,
        )


# ======================================================
# Tab 3：現金流還款分析
# ======================================================
with sub_cash:
    st.header("📈 現金流還款分析")
    st.caption("公式來源：Excel 現金流分析（無寬限期）— 月/年現金流、累積現金流、負擔率。")

    # 兩種情境：寬限期內（只繳利息）vs 寬限期後（本息攤還）
    cf_grace = total_monthly_income - grace_payment - monthly_living - monthly_bad_debt
    cf_post = total_monthly_income - post_grace_payment - monthly_living - monthly_bad_debt
    cf_avg = total_monthly_income - avg_monthly_payment - monthly_living - monthly_bad_debt

    burden_grace = grace_payment / total_monthly_income if total_monthly_income > 0 else 0
    burden_post = post_grace_payment / total_monthly_income if total_monthly_income > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("寬限期月現金流", f"NT$ {cf_grace:,.0f}",
              delta_color="normal" if cf_grace >= 0 else "inverse")
    c2.metric("寬限後月現金流", f"NT$ {cf_post:,.0f}",
              delta_color="normal" if cf_post >= 0 else "inverse")
    c3.metric("加權平均月現金流", f"NT$ {cf_avg:,.0f}",
              delta_color="normal" if cf_avg >= 0 else "inverse")

    b1, b2, b3 = st.columns(3)
    b1.metric("純房貸負擔率（寬限後）", f"{burden_post * 100:.1f}%",
              help="銀行眼中真正的還款壓力")
    b2.metric("總貸款負擔率（含個人壞債）", f"{mortgage_dti * 100:.1f}%",
              help="若 ≥70% 銀行直接退件")
    b3.metric("送件 DTI 燈號",
              "✅ 安全" if mortgage_dti < 0.5 else ("⚠️ 注意" if mortgage_dti < 0.7 else "❌ 危險"))

    st.markdown("##### 📊 月現金流結構（含房貸 vs 不含房貸）")
    cf_breakdown = pd.DataFrame(
        {
            "項目": ["月收入", "月生活費", "月壞債", "月房貸（寬限期）", "月房貸（寬限後）"],
            "金額": [
                total_monthly_income,
                -monthly_living,
                -monthly_bad_debt,
                -grace_payment,
                -post_grace_payment,
            ],
            "類別": ["收入", "支出", "支出", "寬限期支出", "寬限後支出"],
        }
    )
    fig3 = go.Figure(
        go.Bar(
            x=cf_breakdown["項目"],
            y=cf_breakdown["金額"],
            marker_color=["#27AE60", "#E67E22", "#E67E22", "#3498DB", "#C0392B"],
            text=[f"NT$ {v:,.0f}" for v in cf_breakdown["金額"]],
            textposition="outside",
        )
    )
    fig3.update_layout(
        yaxis_title="金額（元）",
        height=380,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("##### 📈 累積現金流（30 年期）")
    years_range = list(range(1, int(loan_years) + 1))
    cumulative = []
    accum = 0.0
    for y in years_range:
        if y <= grace_years:
            yearly_cf = cf_grace * 12
        else:
            yearly_cf = cf_post * 12
        accum += yearly_cf
        cumulative.append(accum)

    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(
            x=years_range,
            y=cumulative,
            mode="lines+markers",
            fill="tozeroy",
            line=dict(color="#16A085", width=3),
            name="累積現金流",
        )
    )
    fig4.add_hline(y=0, line_dash="dash", line_color="red")
    fig4.update_layout(
        xaxis_title="貸款年度",
        yaxis_title="累積淨現金流（元）",
        height=400,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig4, use_container_width=True)

    # 個人負債比 + 反推所需月收入（5f74150 邏輯）
    st.markdown("---")
    st.markdown("##### 🧮 反推所需月收入（銀行 70% 紅線回推）")
    total_monthly_debt = monthly_bad_debt + post_grace_payment
    required_income = total_monthly_debt / 0.7 if total_monthly_debt > 0 else 0
    income_gap = max(required_income - total_monthly_income, 0)

    r1, r2, r3 = st.columns(3)
    r1.metric("每月總負債（含房貸）", f"NT$ {total_monthly_debt:,.0f}")
    r2.metric("通過 70% DTI 所需月收入", f"NT$ {required_income:,.0f}")
    r3.metric(
        "收入缺口",
        f"NT$ {income_gap:,.0f}",
        delta_color="inverse" if income_gap > 0 else "normal",
    )
    if income_gap > 0:
        st.warning(
            f"⚠️ 你還需要每月再多 **NT$ {income_gap:,.0f}** 的收入，"
            "才能讓 DTI 剛好壓在 70% 紅線下。建議拉副業、提高薪資、或縮減房貸總額／延長年限。"
        )
    else:
        st.success("✅ 收入已超過 70% 紅線回推門檻，DTI 安全。")


# ======================================================
# Tab 4：投資收益情境
# ======================================================
with sub_invest:
    st.header("🏠 投資收益情境（含房價增值3情境）")
    st.caption("公式來源：Excel 投資收益計算 — 租金回收率、投資回收期、樂觀/現實/悲觀房價增值。")

    annual_rent = rent * 12
    rental_yield = annual_rent / total_investment if total_investment > 0 else 0
    monthly_net = rent - post_grace_payment
    annual_net = monthly_net * 12
    payback_years = total_investment / annual_net if annual_net > 0 else float("inf")

    i1, i2, i3, i4 = st.columns(4)
    i1.metric("年租金收入", f"NT$ {annual_rent:,.0f}")
    i2.metric("租金收益率", f"{rental_yield * 100:.2f}%")
    i3.metric(
        "月淨現金流",
        f"NT$ {monthly_net:,.0f}",
        delta_color="normal" if monthly_net >= 0 else "inverse",
    )
    i4.metric(
        "投資回收期",
        "無法回收" if payback_years == float("inf") or payback_years < 0
        else f"{payback_years:.1f} 年",
    )

    if monthly_net >= 0:
        st.success(
            f"✅ 月淨收益 +NT$ {monthly_net:,.0f}，房客在幫你付房貸還有剩，標準的『生錢資產』。"
        )
    else:
        st.warning(
            f"⚠️ 月淨現金流 NT$ {monthly_net:,.0f}（為負），"
            "你每月還要倒貼，這是『負現金流物件』，需靠未來增值才有報酬。"
        )

    st.markdown("##### 📈 房價增值 3 情境試算（樂觀 4.5% / 現實 3.0% / 悲觀 2.0%）")
    years_list = [0, 5, 10, 15, 20]
    optimistic = [house_price * (1.045 ** y) for y in years_list]
    realistic = [house_price * (1.03 ** y) for y in years_list]
    pessimistic = [house_price * (1.02 ** y) for y in years_list]

    fig5 = go.Figure()
    fig5.add_trace(
        go.Scatter(
            x=years_list, y=optimistic, mode="lines+markers",
            name="樂觀 +4.5%/年",
            line=dict(color="#27AE60", width=3),
        )
    )
    fig5.add_trace(
        go.Scatter(
            x=years_list, y=realistic, mode="lines+markers",
            name="現實 +3.0%/年",
            line=dict(color="#2980B9", width=3),
        )
    )
    fig5.add_trace(
        go.Scatter(
            x=years_list, y=pessimistic, mode="lines+markers",
            name="悲觀 +2.0%/年",
            line=dict(color="#C0392B", width=3),
        )
    )
    fig5.update_layout(
        xaxis_title="持有年數",
        yaxis_title="預估房價（元）",
        height=420,
        margin=dict(t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig5, use_container_width=True)

    df_price = pd.DataFrame(
        {
            "持有年數": years_list,
            "樂觀(4.5%)": [f"NT$ {v:,.0f}" for v in optimistic],
            "現實(3.0%)": [f"NT$ {v:,.0f}" for v in realistic],
            "悲觀(2.0%)": [f"NT$ {v:,.0f}" for v in pessimistic],
        }
    )
    st.dataframe(df_price, use_container_width=True, hide_index=True)


# ======================================================
# Tab 5：風險壓力測試（利率 + 空租 + 收入下滑）
# ======================================================
with sub_risk:
    st.header("⚠️ 風險壓力測試")
    st.caption("公式來源：Excel 風險管理系統 — 空租準備金、利率衝擊、收入下滑。")

    # 空租風險
    st.markdown("##### 🏚️ 空租風險評估")
    monthly_cost = post_grace_payment + mgmt_fee
    required_vacancy_reserve = vacancy_months * monthly_cost
    reserve_adequacy = (
        cash_reserve / required_vacancy_reserve if required_vacancy_reserve > 0 else float("inf")
    )

    v1, v2, v3 = st.columns(3)
    v1.metric("月總固定成本（房貸+管理費）", f"NT$ {monthly_cost:,.0f}")
    v2.metric("建議空租準備金", f"NT$ {required_vacancy_reserve:,.0f}")
    v3.metric(
        "準備金充足度",
        "∞" if reserve_adequacy == float("inf") else f"{reserve_adequacy * 100:.1f}%",
    )
    if reserve_adequacy >= 1:
        st.success("✅ 現有預備金足以撐過預估空租期。")
    else:
        st.warning(
            f"⚠️ 預備金缺口 NT$ {required_vacancy_reserve - cash_reserve:,.0f}，"
            "建議補強現金存款再進場。"
        )

    # 利率衝擊
    st.markdown("##### 📈 利率衝擊壓力測試（+1% / +2%）")
    base_pay = post_grace_payment
    rate_scenarios = [
        ("目前利率", annual_rate, base_pay, 0),
    ]
    for d in [0.01, 0.02]:
        new_rate = annual_rate + d
        new_pay = pmt(new_rate / 12, pay_months, loan_amount)
        delta = new_pay - base_pay
        rate_scenarios.append((f"利率+{int(d * 100)}%", new_rate, new_pay, delta))

    df_rs = pd.DataFrame(rate_scenarios, columns=["情境", "新利率", "新月付金", "增加金額"])
    df_rs["影響評估"] = df_rs["增加金額"].apply(
        lambda x: "基準" if x == 0 else (
            "✅ 可承受" if x < cf_avg * 0.5 else "⚠️ 警戒"
        )
    )

    fig6 = go.Figure()
    fig6.add_trace(
        go.Bar(
            x=df_rs["情境"],
            y=df_rs["新月付金"],
            marker_color=["#3498DB", "#E67E22", "#C0392B"],
            text=[f"NT$ {v:,.0f}" for v in df_rs["新月付金"]],
            textposition="outside",
        )
    )
    fig6.update_layout(
        yaxis_title="月付金（元）",
        height=360,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig6, use_container_width=True)

    df_rs_display = df_rs.copy()
    df_rs_display["新利率"] = df_rs_display["新利率"].apply(lambda x: f"{x * 100:.2f}%")
    st.dataframe(
        df_rs_display.style.format(
            {"新月付金": "{:,.0f}", "增加金額": "{:,.0f}"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    # 收入下滑情境
    st.markdown("##### 📉 收入下滑情境（-20% / -30%）")
    inc_scenarios = []
    for pct, label in [(1.0, "正常收入"), (0.8, "收入 -20%"), (0.7, "收入 -30%")]:
        new_income = total_monthly_income * pct
        new_cf = new_income - post_grace_payment - monthly_living - monthly_bad_debt
        inc_scenarios.append(
            {
                "情境": label,
                "新月收入": new_income,
                "新月現金流": new_cf,
                "結果": "✅ 安全" if new_cf > 0 else "❌ 入不敷出",
            }
        )
    df_inc = pd.DataFrame(inc_scenarios)

    fig7 = go.Figure()
    fig7.add_trace(
        go.Bar(
            x=df_inc["情境"],
            y=df_inc["新月現金流"],
            marker_color=["#27AE60" if v > 0 else "#C0392B" for v in df_inc["新月現金流"]],
            text=[f"NT$ {v:,.0f}" for v in df_inc["新月現金流"]],
            textposition="outside",
        )
    )
    fig7.add_hline(y=0, line_dash="dash", line_color="red")
    fig7.update_layout(
        yaxis_title="月現金流（元）",
        height=360,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig7, use_container_width=True)
    st.dataframe(
        df_inc.style.format({"新月收入": "{:,.0f}", "新月現金流": "{:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )


# ======================================================
# Tab 6：租金安全懶人包（1e812 公式）
# ======================================================
with sub_lazy:
    st.header("📋 租金安全懶人包")
    st.caption("公式來源：Excel 懶人包 — 安全指數 = 實拿租金 / 月房貸；底線租金 = 總成本 / (1-折讓)。")

    real_rent = rent * (1 - vacancy_discount)
    repair_fund = rent * repair_pct
    monthly_total_cost_lazy = post_grace_payment + mgmt_fee + repair_fund
    breakeven_rent = (
        monthly_total_cost_lazy / (1 - vacancy_discount) if vacancy_discount < 1 else 0
    )
    safety_index = real_rent / post_grace_payment if post_grace_payment > 0 else 0

    l1, l2, l3 = st.columns(3)
    l1.metric("實拿租金（打折後）", f"NT$ {real_rent:,.0f}")
    l2.metric("月總成本（房貸+開銷+維修）", f"NT$ {monthly_total_cost_lazy:,.0f}")
    l3.metric("底線租金（上架不能低於）", f"NT$ {breakeven_rent:,.0f}")

    st.markdown("##### 🎯 安全指數（≥1.2 才能做，越高越舒服）")

    # Gauge chart
    fig8 = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=safety_index,
            number={"font": {"size": 48}},
            gauge={
                "axis": {"range": [0, 3]},
                "bar": {"color": "#2C3E50"},
                "steps": [
                    {"range": [0, 1.0], "color": "#F5B7B1"},
                    {"range": [1.0, 1.2], "color": "#F9E79F"},
                    {"range": [1.2, 3.0], "color": "#A9DFBF"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.8,
                    "value": 1.2,
                },
            },
            title={"text": "安全指數 (Real Rent / 月房貸)"},
        )
    )
    fig8.update_layout(height=320, margin=dict(t=40, b=20))
    st.plotly_chart(fig8, use_container_width=True)

    if safety_index >= 1.2 and rent >= breakeven_rent:
        st.success(
            f"✔ **安全（可上架）** — 安全指數 {safety_index:.2f}（≥1.2），"
            f"且實際租金 NT$ {rent:,.0f} ≥ 底線租金 NT$ {breakeven_rent:,.0f}。"
        )
    elif safety_index >= 1.0:
        st.warning(
            f"△ **偏緊（需要調整）** — 安全指數 {safety_index:.2f}（介於 1.0 ~ 1.19）。"
            "建議：降固定開銷、拉租金、壓房價、加自備款、或談更低利率/更長年限。"
        )
    else:
        st.error(
            f"✗ **危險（不建議買進）** — 安全指數 {safety_index:.2f}（<1.0），"
            "實拿租金連房貸都付不起，每月都要倒貼。"
        )

    st.markdown("---")
    st.info(
        "**怎麼用懶人包：**\n"
        "1. 改側邊欄『租金與投資』裡面四個藍色欄位（月租、管理費、空置折讓、維修比）。\n"
        "2. 看兩個重點：安全指數（≥1.2）+ 底線租金（你的上架價要 ≥ 它）。\n"
        "3. 偏緊或危險時的調整方法：降開銷、拉租金、壓房價、加頭期，或談更低利率/更長年限。"
    )


# ======================================================
# Tab 7：預售屋實戰掃雷與潛力評分表
# ======================================================
with tab_presale:
    st.header("🔍 預售屋實戰掃雷與潛力評分表")
    st.caption(
        "依據預售屋實戰策略 — "
        "一張表看清地段加分、嫌惡扣分、合約地雷。"
    )

    with st.container(border=True):
        st.markdown("##### 🏗️ 建案基本資料")
        pre_col_a, pre_col_b = st.columns(2)
        with pre_col_a:
            project_name = st.text_input("建案名稱", value="某某花園", key="pre_project_name")
            developer_name = st.text_input("建商名稱", value="", key="pre_developer_name")
            project_total_wan = st.number_input(
                "建案總價（萬元）", 0, value=2000, step=10, key="pre_total_wan",
            )
        with pre_col_b:
            floor_area = st.number_input("權狀坪數", 0.0, value=30.0, step=0.5, key="pre_floor_area")
            public_ratio = st.slider("公設比 (%)", 0, 50, 32, 1, key="pre_public_ratio")

    st.markdown("---")
    unit_price = (project_total_wan * 10_000 / floor_area) if floor_area > 0 else 0
    info_cols = st.columns(4)
    info_cols[0].metric("建案", project_name or "—")
    info_cols[1].metric("總價", f"{project_total_wan:,} 萬")
    info_cols[2].metric("權狀坪數", f"{floor_area:.1f} 坪")
    info_cols[3].metric("單價", f"{unit_price/10_000:,.1f} 萬/坪" if unit_price else "—")
    if developer_name:
        st.caption(f"🏗️ 建商：{developer_name}　|　公設比：{public_ratio}%")

    st.divider()

    # 一、地段增值潛力評分
    st.subheader("一、地段增值潛力評分（加分項）")
    st.caption("投資心法：『地段不是看現在，是看 5 年後政府帶你飛去哪。』")

    col_l, col_r = st.columns([1, 1])
    with col_l:
        plus_metro = st.checkbox("🚄 高鐵 / 台鐵 / 捷運站附近（步行 10 分鐘內）", key="plus_metro")
        plus_highway = st.checkbox("🛣️ 交流道 10 分鐘車程內", key="plus_highway")
        plus_science = st.checkbox("🏢 科學園區 / 大型商辦聚落周邊", key="plus_science")
        plus_redev = st.checkbox("🌳 政府大型重劃區 / 大型公園", key="plus_redev")

    plus_count = sum([plus_metro, plus_highway, plus_science, plus_redev])
    potential_score = plus_count * 25

    with col_r:
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=potential_score,
                number={"suffix": " 分", "font": {"size": 40}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2C3E50"},
                    "steps": [
                        {"range": [0, 25], "color": "#F5B7B1"},
                        {"range": [25, 50], "color": "#F9E79F"},
                        {"range": [50, 75], "color": "#A9DFBF"},
                        {"range": [75, 100], "color": "#52BE80"},
                    ],
                    "threshold": {
                        "line": {"color": "green", "width": 4},
                        "thickness": 0.8,
                        "value": 75,
                    },
                },
                title={"text": "增值潛力指數"},
            )
        )
        fig_gauge.update_layout(height=260, margin=dict(t=40, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    st.progress(potential_score / 100, text=f"增值潛力指數：{potential_score} / 100")

    if plus_count >= 3:
        st.success(
            f"✅ **超高潛力地段！命中 {plus_count}/4 項利多。** "
            "強烈推薦：這種題材建案就是『買就賺』的標的，"
            "未來 3-5 年增值動能強勁，可優先佈局！"
        )
    elif plus_count == 2:
        st.success(
            f"🟢 **不錯的潛力地段** — 命中 {plus_count}/4 項利多，"
            "具備中長期增值動能，可進一步評估價格合理性。"
        )
    elif plus_count == 1:
        st.info(
            f"📋 命中 {plus_count}/4 項利多，地段中規中矩。"
            "若價格夠便宜可考慮，否則建議再看看別案。"
        )
    else:
        st.warning(
            "⚠️ 沒有命中任何重大利多題材，純粹靠建商行銷話術撐盤。"
            "提醒：沒題材的預售屋，未來增值幾乎只能靠通膨。"
        )

    st.divider()

    # 二、嫌惡設施一鍵掃雷
    st.subheader("二、嫌惡設施一鍵掃雷（扣分與紅燈項）")
    st.caption("重要警語：『嫌惡設施會大幅影響未來轉手價與銀行鑑價。』")

    rc1, rc2 = st.columns(2)
    with rc1:
        bad_tower = st.checkbox("⚡ 高壓電塔 / 變電所 200 公尺內", key="bad_tower")
        bad_factory = st.checkbox("🏭 工廠污染源 / 焚化爐 / 垃圾掩埋場", key="bad_factory")
        bad_flood = st.checkbox("🌊 淹水紀錄區 / 順向坡 / 斷層帶", key="bad_flood")
    with rc2:
        bad_funeral = st.checkbox("⚰️ 殯葬設施 / 公墓 / 納骨塔 1 公里內", key="bad_funeral")
        bad_noise = st.checkbox("🛻 高速公路 / 鐵路噪音帶 / 機場航道", key="bad_noise")

    bad_flags = {
        "高壓電塔": bad_tower, "工廠污染": bad_factory, "淹水/斷層": bad_flood,
        "殯葬設施": bad_funeral, "高速公路噪音": bad_noise,
    }
    bad_hits = [k for k, v in bad_flags.items() if v]
    bad_count = len(bad_hits)

    if bad_count > 0:
        st.error(
            f"⚠️ **警報：包含 {bad_count} 項嚴重嫌惡設施 — {', '.join(bad_hits)}！**\n\n"
            "這會 **大幅影響未來轉手價與銀行鑑價**（鑑價砍 10~20% 是常態），"
            "甚至有的銀行會直接拒貸或大砍成數。\n\n"
            "**👉 強烈建議：直接放棄此案，不要因為便宜上鉤！** "
            "你買進的折讓，未來轉手時會被買家砍兩倍回來。"
        )
    else:
        st.success("✅ 周邊無重大嫌惡設施，建案環境條件過關。")

    st.divider()

    # 三、定型化契約防護網
    st.subheader("三、定型化契約防坑檢核")
    st.caption("依據內政部《預售屋買賣定型化契約應記載及不得記載事項》三大重點。")

    contract_equivalent = st.checkbox(
        "📝 合約中『建材設備』有出現「同級品」字眼",
        key="contract_equivalent",
        help="同級品=建商可任意換較便宜建材，是常見坑點",
    )
    contract_deadline = st.checkbox(
        "📅 開工日期 / 取得使照期限「未明確標示」（沒寫年月日）",
        key="contract_deadline",
        help="沒寫期限=建商可無限延期，沒違約金可求",
    )
    contract_retention = st.checkbox(
        "💰 交屋保留款「不足總價 5%」（內政部建議最低保障）",
        key="contract_retention",
        help="保留款是你交屋驗收時唯一的籌碼",
    )

    contract_hits = []
    if contract_equivalent:
        contract_hits.append("『同級品』字眼")
    if contract_deadline:
        contract_hits.append("期限未明確")
    if contract_retention:
        contract_hits.append("保留款不足 5%")

    if contract_hits:
        st.warning(
            f"⚠️ **發現 {len(contract_hits)} 個合約地雷：{', '.join(contract_hits)}**\n\n"
            "**👉 提醒：要求建商修改合約，否則直接走人！**\n\n"
            "- **「同級品」字眼**：要求改為**指定品牌型號**，或加註『須經買方書面同意』\n"
            "- **期限不明**：要求**寫明年月日**＋逾期違約金（每日總價萬分之五）\n"
            "- **保留款 < 5%**：依內政部範本，保留款應為**總價 5%**以上"
        )
    else:
        st.success(
            "✅ 三大合約地雷皆無發現，合約結構基本健全。"
            "仍建議將合約交由地政士或律師最後審閱一次。"
        )

    # 綜合評分
    st.divider()
    st.subheader("📊 預售屋綜合戰績")

    fc1, fc2, fc3 = st.columns(3)
    fc1.metric("地段加分項", f"{plus_count} / 4")
    fc2.metric(
        "嫌惡扣分項", bad_count,
        delta=f"-{bad_count}" if bad_count > 0 else "0",
        delta_color="inverse" if bad_count > 0 else "off",
    )
    fc3.metric("合約地雷數", len(contract_hits))

    if bad_count > 0:
        st.error("### ❌ 不及格 — 嫌惡設施直接淘汰，建議放棄此案。")
    elif contract_hits and plus_count <= 1:
        st.warning("### ⚠️ 警示 — 地段平庸＋合約有坑，建議再評估或大幅議價。")
    elif plus_count >= 3 and not contract_hits:
        st.success("### 🚀 高分通過 — 地段強＋合約淨，指定可下手。")
    elif plus_count >= 2 and not contract_hits:
        st.success("### 🟢 通過 — 條件不錯，可進入價格議價階段。")
    else:
        st.info("### 📋 一般 — 條件普通，建議多比較幾案。")


# ======================================================
# Tab 8：中古屋淘金與銀行貸款避險儀表板
# ======================================================
with tab_used:
    st.header("🏚️ 中古屋淘金與銀行貸款避險儀表板")
    st.caption("依據中古屋實戰指南— 三大不買、銀行拒貸地雷、真實居住成本。")

    st.subheader("📍 物件基本資料")
    uc1, uc2, uc3, uc4 = st.columns(4)
    with uc1:
        used_location = st.selectbox(
            "房屋地點",
            options=["雙北地區", "非雙北地區"],
            index=1,
            key="used_location",
        )
    with uc2:
        used_age = st.number_input("屋齡（年）", 0, 100, 25, 1, key="used_age")
    with uc3:
        used_floor = st.selectbox(
            "所在樓層",
            options=["2 樓", "頂樓", "其他中間樓層"],
            index=2,
            key="used_floor",
        )
    with uc4:
        used_type = st.selectbox(
            "房屋類型",
            options=["一般住宅", "山區豪宅", "地上權屋"],
            index=0,
            key="used_type",
        )

    st.divider()
    st.subheader("一、三大絕對不買類型診斷")

    diag_messages = []
    is_red = False

    # 規則 1：非雙北且屋齡 > 40
    if used_location == "非雙北地區" and used_age > 40:
        st.error(
            "⚠️ **超過 40 年的老公寓（雙北除外）未來極難轉手且貸款成數極低，"
            "建議避開！**\n\n"
            "非雙北的 40 年以上老屋通常面臨：銀行貸款成數砍到 5 成以下、"
            "鑑價遠低於行情、買家集中、轉手週期 6~12 個月起跳。"
        )
        is_red = True
        diag_messages.append("老屋（非雙北 >40 年）")
    else:
        st.success("✅ 屋齡與地點組合通過（非『非雙北 + 40 年以上老公寓』）。")

    # 規則 2：山區豪宅
    if used_type == "山區豪宅":
        st.error(
            "⚠️ **山區豪宅市場需求極低，流動性差，請勿投資！**\n\n"
            "山區豪宅普遍面臨：銀行鑑價保守、貸款成數低（多為 5~6 成）、"
            "潛在買家極少、開車進出不便、未來轉手週期動輒 1-2 年。"
        )
        is_red = True
        diag_messages.append("山區豪宅")
    elif used_type == "地上權屋":
        st.error(
            "🚫 **地上權屋等同銀行拒貸物件！**\n\n"
            "沒有土地持分、貸款成數極低（多為 4~5 成）、"
            "70 年使用權到期後歸零，僅適合自住不適合投資。"
        )
        is_red = True
        diag_messages.append("地上權屋")
    else:
        st.success("✅ 房屋類型過關（一般住宅）。")

    # 規則 3：2樓 或 頂樓 且舊大樓（>20年）
    if used_floor in ("2 樓", "頂樓") and used_age > 20:
        st.warning(
            f"⚠️ **舊大樓 {used_floor} 易有以下問題，市場接受度低，請謹慎評估或大幅殺價：**\n\n"
            "- **2 樓**：管線堵塞（廚廁污水從你家溢出是常見惡夢）、噪音傳導、私密性差\n"
            "- **頂樓**：夏天悶熱、漏水機率高、屋頂違建衍生糾紛\n\n"
            "**👉 對策：殺價殺到比同棟均價低 10~15%，或要求賣方先做防水處理後再交屋。**"
        )
        diag_messages.append(f"舊大樓 {used_floor}")
    elif used_floor in ("2 樓", "頂樓"):
        st.info(f"ℹ️ 樓層為 {used_floor}，因屋齡尚新影響有限，仍建議現場仔細看管線/防水。")
    else:
        st.success("✅ 樓層條件良好（中間樓層）。")

    st.divider()
    st.subheader("二、銀行拒貸地雷快篩")
    st.caption("提醒：『沒有銀行貸款，就沒有低成本槓桿。』")

    deny_options = ["海砂屋", "輻射屋", "傾斜屋", "凶宅", "地上權屋"]
    deny_hits = st.multiselect(
        "勾選下列屋況疑慮（一項都不能有）",
        options=deny_options,
        default=["地上權屋"] if used_type == "地上權屋" else [],
        help="銀行對這五類物件直接拒貸或大砍成數",
    )

    if deny_hits:
        st.error(
            f"🚫 **銀行拒貸物件！命中：{', '.join(deny_hits)}**\n\n"
            "這些物件會導致你 **無法使用『好債槓桿』**，"
            "必須全額現金或極高利率，**絕對不要碰！**\n\n"
            "即使賣方價格便宜 30%，沒有銀行貸款的低利成本，整體報酬率反而更差，"
            "且未來轉手時，下一手買家也面臨同樣問題。"
        )
    else:
        st.success("✅ 屋況無重大拒貸地雷，銀行可正常承作貸款。")

    st.divider()
    st.subheader("三、真實居住成本計算機")
    st.caption("投資心法：『出價前先算每年真實成本，才知道上限在哪。』")

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        used_price_wan = st.number_input(
            "預估購買總價（萬元）", 0, value=1500, step=10, key="used_price",
        )
    with cc2:
        used_hold_years = st.number_input("預計持有年限", 1, 50, 10, 1, key="used_hold")
    with cc3:
        used_renovation_wan = st.number_input(
            "預估裝潢／修繕費用（萬元）", 0, value=150, step=10, key="used_renov",
        )

    used_price = used_price_wan * 10_000
    used_renov = used_renovation_wan * 10_000
    total_cost = used_price + used_renov
    annual_cost = total_cost / used_hold_years if used_hold_years > 0 else 0
    monthly_cost_used = annual_cost / 12

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("總投入成本", f"NT$ {total_cost:,.0f}")
    rc2.metric("每年居住成本", f"NT$ {annual_cost:,.0f}")
    rc3.metric("每月居住成本", f"NT$ {monthly_cost_used:,.0f}")

    if is_red or deny_hits:
        st.error(
            f"❌ **此物件已觸發紅線警報，不建議出價。** "
            f"即使每月成本看起來 NT$ {monthly_cost_used:,.0f}，"
            "未來流動性與轉手損失會把你的報酬率吃光。"
        )
    elif diag_messages:
        st.warning(
            f"⚠️ 物件存在 **{', '.join(diag_messages)}** 等議價籌碼。"
            f"出價上限建議：以「每月成本 ≤ 同區租金 × 1.0」反推，"
            "並依議價籌碼再壓 10% 起跳。"
        )
    else:
        st.success(
            f"✅ 物件條件過關，每月真實居住成本 NT$ {monthly_cost_used:,.0f}。"
            "出價時建議：**月成本 ≤ 同區租金行情**，才符合『買比租划算』的進場原則。"
        )


# ======================================================
# Tab 9：數位驗屋防護網與待辦清單
# ======================================================
with tab_inspect:
    st.header("✅ 數位驗屋防護網與待辦清單")
    st.caption("逐項勾選，進度條即時前進；發現重大問題會自動列出議價籌碼。")

    inspect_pre, inspect_used = st.tabs(["🏗️ 預售屋交屋檢驗", "🏚️ 中古屋看屋檢驗"])

    # -------- 預售屋交屋檢驗 --------
    with inspect_pre:
        st.markdown("##### 💧 水電")
        pre_drain = st.checkbox(
            "排水管暢通無泥沙（含廚房、廁所、陽台地排）", key="pre_drain",
        )
        pre_circuit = st.checkbox("總電箱迴路標示清晰，且與圖面相符", key="pre_circuit")
        pre_water_pressure = st.checkbox("各出水口水壓正常、無漏水", key="pre_water_pressure")

        st.markdown("##### 📏 尺寸")
        pre_area = st.checkbox(
            "室內實際坪數與合約圖面相符（誤差 < 1%）", key="pre_area",
        )
        pre_height = st.checkbox("樓高與合約相符（淨高、樓板厚度）", key="pre_height")
        pre_beam = st.checkbox("樑柱位置與圖面相符，無誤差", key="pre_beam")

        st.markdown("##### 🧱 建材")
        pre_tile = st.checkbox("地磚、壁磚敲擊無空鼓聲", key="pre_tile")
        pre_door = st.checkbox("門窗密合度良好、隔音達合約標準", key="pre_door")
        pre_finish = st.checkbox(
            "建材品牌與型號與合約一致（無被『同級品』替換）", key="pre_finish",
        )

        pre_items = [
            pre_drain, pre_circuit, pre_water_pressure,
            pre_area, pre_height, pre_beam,
            pre_tile, pre_door, pre_finish,
        ]
        pre_progress = sum(pre_items) / len(pre_items)
        st.markdown("---")
        st.progress(
            pre_progress,
            text=f"預售屋驗屋完成度：{sum(pre_items)} / {len(pre_items)}（{pre_progress * 100:.0f}%）",
        )

        if pre_progress == 1.0:
            st.success(
                "🎉 **預售屋驗屋全部過關！** 可以準備辦理交屋手續，"
                "記得保留 5% 尾款直到所有缺失補正完畢。"
            )
        elif pre_progress >= 0.7:
            st.info(
                f"📋 已完成 {pre_progress * 100:.0f}%，剩餘項目請逐一檢查。"
                "未過項目務必白紙黑字列入交屋缺失單，限期改善。"
            )
        else:
            st.warning(
                f"⚠️ 完成度僅 {pre_progress * 100:.0f}%，請繼續完成所有項目。"
                "驗屋只有一次機會，務必逐項確認、拍照存證。"
            )

    # -------- 中古屋看屋檢驗 --------
    with inspect_used:
        st.markdown("##### 💦 漏水壁癌")
        used_leak_window = st.checkbox(
            "窗框四周無水痕、無壁癌", key="used_leak_window",
        )
        used_leak_bath = st.checkbox(
            "廁所外牆（與廁所相連的房間牆面）無水痕", key="used_leak_bath",
        )
        used_leak_ceiling = st.checkbox(
            "天花板無水痕、無剝落（特別是頂樓與廁所下方）", key="used_leak_ceiling",
        )

        st.markdown("##### 🏛️ 結構安全")
        used_crack = st.checkbox(
            "樑柱無 45 度交叉裂縫", key="used_crack",
        )
        used_wall = st.checkbox(
            "無自行打掉承重牆痕跡（廚房／浴室主牆）", key="used_wall",
        )
        used_tilt = st.checkbox(
            "地面與牆面垂直（彈珠不會自動滾動）", key="used_tilt",
        )

        st.markdown("##### 🔧 管線狀態")
        used_pipe = st.checkbox(
            "若屋齡 > 20 年，已重拉水電管線（請屋主出示證明）", key="used_pipe",
        )
        used_electric = st.checkbox(
            "電線無外露老化，總電量足夠（30A 以上）", key="used_electric",
        )
        used_sewage = st.checkbox(
            "排水順暢、無回堵異味", key="used_sewage",
        )

        used_items = [
            used_leak_window, used_leak_bath, used_leak_ceiling,
            used_crack, used_wall, used_tilt,
            used_pipe, used_electric, used_sewage,
        ]
        used_progress = sum(used_items) / len(used_items)
        st.markdown("---")
        st.progress(
            used_progress,
            text=f"中古屋驗屋完成度：{sum(used_items)} / {len(used_items)}（{used_progress * 100:.0f}%）",
        )

        # 重大議價籌碼提示
        critical_issues = []
        if not used_leak_window:
            critical_issues.append("窗框漏水")
        if not used_leak_bath:
            critical_issues.append("廁所外牆水痕")
        if not used_leak_ceiling:
            critical_issues.append("天花板水痕")
        if not used_crack:
            critical_issues.append("樑柱裂縫")
        if not used_wall:
            critical_issues.append("承重牆遭破壞")
        if not used_tilt:
            critical_issues.append("地面/牆面不平")

        if critical_issues:
            st.warning(
                f"⚠️ **發現重大修繕成本項目：{', '.join(critical_issues)}**\n\n"
                "請將此修繕費用計入買房總成本，並作為與房仲、屋主強力議價的籌碼：\n\n"
                "- **漏水/壁癌**：抓漏 + 防水工程約 NT$ 5~15 萬／處\n"
                "- **結構裂縫**：需鑑定報告，輕者補強約 NT$ 10~30 萬，重者建議放棄\n"
                "- **承重牆破壞**：違法且有結構風險，**強烈建議放棄此案**\n"
                "- **地面/牆面不平**：地基沉陷可能，務必請結構技師鑑定\n\n"
                "**👉 議價公式：總價 -（修繕成本 × 1.5）= 你的出價上限。**"
            )
        elif used_progress == 1.0:
            st.success(
                "🎉 **中古屋全項目過關！** 屋況良好，"
                "可以進入正式議價階段，記得仍要請地政士查謄本與凶宅資訊。"
            )
        else:
            st.info(
                f"📋 已完成 {used_progress * 100:.0f}%，"
                "請依序完成剩餘項目；未勾選 ≠ 沒問題，是『尚未確認』。"
            )


# ======================================================
# Tab 10：財富思維迷思破解與實戰回覆 FAQ
# ======================================================
with tab_faq:
    st.header("💡 財富思維迷思破解 × 實戰 FAQ")
    st.caption(
        "依據財富思維與貸款槓桿實戰— "
        "破解中產階級三大思維陷阱，公開實戰 SOP。"
    )

    # ---- 迷思破解器 ----
    st.subheader("🧠 迷思破解器（互動測驗）")
    st.markdown(
        "**測驗題：** 買一輛 100 萬的新車自己開，這是 **資產** 還是 **負債**？"
    )

    answer = st.radio(
        "請選擇你的答案：",
        options=["（請選擇）", "資產", "負債"],
        index=0,
        horizontal=True,
        key="faq_car_quiz",
    )

    if answer == "資產":
        st.error(
            "❌ **錯誤！這是中產階級迷思。**\n\n"
            "車子落地就折舊（第一年通常折 15~20%），還會吃掉你的現金流：\n"
            "- 每月油錢、保養、保險、停車費\n"
            "- 每年牌照稅、燃料稅、折舊\n"
            "- 五年後價值剩不到 40%\n\n"
            "**這是純粹的負債。** 我們定義：『**會把錢從你口袋拿走的東西，就是負債。**』\n\n"
            "💡 **真正的富人邏輯**：先用低利房貸買進生錢資產，等資產的『被動收入』超過買車成本，"
            "再用那筆被動收入養車——這才叫『用資產買負債』，而不是用薪水。"
        )
    elif answer == "負債":
        st.success(
            "✅ **正確！這就是富人思維。**\n\n"
            "富人鐵律：『**能把錢放進你口袋的才是資產，會把錢掏走的叫負債。**』\n\n"
            "- ✅ **資產**：收租房、預售屋（轉手價差）、股息ETF、版稅 → 替你工作\n"
            "- ❌ **負債**：自用新車、名牌包、信貸消費、卡循 → 你替它工作\n\n"
            "🚀 你已經跨過第一道思維門檻。下一步：**先累積資產，讓資產的現金流幫你養負債**，"
            "而不是用薪水硬扛——這就是富人與中產的根本差距。"
        )
    else:
        st.info("👆 請先選擇答案，看看你是中產思維還是富人思維。")

    st.divider()

    # ---- 實戰 FAQ ----
    st.subheader("📚 實戰 FAQ（心法解析）")
    st.caption("展開下方折疊面板，看最常見問題的實戰解析。")

    with st.expander("🏢 **Q1：整棟大廈估價的秘密是什麼？**"):
        st.markdown(
            "**A：銀行估價是以「整棟」為單位，而不是單戶。**\n\n"
            "這意味著：如果同棟大樓有不同戶的入手價落差很大（例如 40 萬、55 萬、65 萬／坪），"
            "你能買到越低於高價戶的價格，未來能從銀行「搬出來的錢（增貸）」就越多！\n\n"
            "**📐 實戰邏輯：**\n"
            "- 同棟成交價區間：40 ~ 65 萬／坪\n"
            "- 銀行鑑價會抓**加權平均約 55 萬／坪**\n"
            "- 你以 40 萬／坪買進 → 鑑價跟著平均往上走 → 未來可增貸出 **(55-40) × 坪數 × 8成** 的現金\n\n"
            "**👉 結論：價差越大越好，挑同棟最便宜那戶，等於挑了一個現成的增貸金雞母。**"
        )

    with st.expander("🏦 **Q2：富邦增貸 SOP 是什麼？（資金流必過水）**"):
        st.markdown(
            "**A：增貸出來的錢必須過水，絕不能直接買房。**\n\n"
            "銀行對「房屋增貸資金用途」管控極嚴，"
            "若直接拿增貸款項去買下一間房，會被視為 **違規轉貸炒房**，"
            "可能被收回貸款 + 列為黑名單。\n\n"
            "**✅ 實戰 SOP（富邦版）：**\n\n"
            "```\n"
            "1. 增貸入帳 → 立即轉出到其他銀行（脫離原戶頭金流追蹤）\n"
            "2. 在新銀行定存 3 個月（製造『非急用』軌跡）\n"
            "3. 到期解約 → 投入 0050 / 保單 / 基金（留存『投資用途』憑證）\n"
            "4. 滿 1 年後 → 才能合法解禁拿去買下一間房\n"
            "```\n\n"
            "**🚨 注意：每一步都要留下對帳單、轉帳記錄、投資成交單，"
            "未來被銀行抽查時這些就是你的免死金牌。**"
        )

    with st.expander("🔍 **Q3：為什麼要大量看房？看 10-20 間不浪費時間嗎？**"):
        st.markdown(
            "**A：不是浪費，而是『經驗值換籌碼』的必修課。**\n\n"
            "投資心法：**每月看 10-20 間，篩選 2-5 間進攻**。\n\n"
            "**🎯 大量看房的三大效益：**\n\n"
            "1. **累積行情敏銳度** — 你看過 100 間，才知道哪間是『蘋果案』（低於市場行情的好物件）。"
            "新手看 1-2 間就出價，幾乎一定買貴。\n\n"
            "2. **與房仲建立談判籌碼** — 房仲看你『會看、敢出』，會主動把好案子第一時間送來，"
            "而不是先給投資客或熟客。\n\n"
            "3. **訓練決斷力** — 真正的好物件出現時，你要在 24~48 小時內出價斡旋。"
            "沒看過量的人，會猶豫到錯過。\n\n"
            "**👉 結論：看房是一場數量遊戲，量到了才會出現質。"
            "10 間看不到蘋果案，20 間就會出現。不夠就繼續看，這是『複利型』的努力。**"
        )

    with st.expander("💎 **Q4（加碼）：什麼是「好債」與「壞債」？**"):
        st.markdown(
            "**A：用一句話分辨——『**這筆債借出來，是用來買資產還是負債？**』**\n\n"
            "| 類型 | 利率 | 用途 | 結果 |\n"
            "|---|---|---|---|\n"
            "| ✅ **好債** | 2~3% 房貸 | 買收租房、預售屋 | 資產替你還債，現金流為正 |\n"
            "| ✅ **好債** | 2~3% 增貸 | 投入 0050/保單 | 資產增值 > 利息成本 |\n"
            "| ❌ **壞債** | 15~20% 卡循 | 買新車、名牌、旅遊 | 你替負債工作，現金流為負 |\n"
            "| ❌ **壞債** | 5~8% 信貸 | 補生活費、繳卡費 | 雪球越滾越大，惡性循環 |\n\n"
            "**👉 富人不是不借錢，是只借『會增值的錢』。** "
            "壞債越多越窮，好債越多越富——這就是槓桿的本質。"
        )

    with st.expander("🏗️ **Q5（加碼）：為什麼推預售屋而不是新成屋？**"):
        st.markdown(
            "**A：因為預售屋是『用 1 成自備款，鎖定 100% 房價漲幅』的合法槓桿。**\n\n"
            "**📊 數字比較（假設房價 1000 萬、3 年後漲 20%）：**\n\n"
            "| 項目 | 預售屋 | 新成屋 |\n"
            "|---|---|---|\n"
            "| 自備款 | 100 萬（10%） | 200~300 萬（20-30%） |\n"
            "| 3 年後房價 | 1200 萬 | 1200 萬 |\n"
            "| 帳面獲利 | +200 萬 | +200 萬 |\n"
            "| **報酬率** | **+200%（200/100）** | **+67~100%（200/200~300）** |\n\n"
            "**👉 同樣的漲幅，預售屋因為自備款少，報酬率是新成屋的 2~3 倍。** "
            "這就是『買就賺』的數學。"
        )


# ======================================================
# 挑建商：建商安全性體檢
# ======================================================
with tab_builder:
    st.header("🏗️ 挑建商：安全性體檢")
    st.caption("投資心法：『選錯建商，神也救不了。』預售屋進場前的第一道防線。")

    st.subheader("建商四大硬指標")
    st.markdown("逐項確認，**未達 3 項以上者請直接放棄**。")

    bc1, bc2 = st.columns(2)
    with bc1:
        builder_capital = st.checkbox(
            "💰 資本額 > 2 億（顯示在公司登記資料）", key="adv_builder_capital",
        )
        builder_years = st.checkbox(
            "📅 公司成立 > 5 ~ 10 年（成立越久越穩）", key="adv_builder_years",
        )
    with bc2:
        builder_completed = st.checkbox(
            "🏗️ 至少 1 ~ 2 個完工建案紀錄（不是只有畫餅的紙上建商）",
            key="adv_builder_completed",
        )
        builder_warranty = st.checkbox(
            "🛡️ 履約保證機制為「價金返還」（非同業連帶或續建）",
            key="adv_builder_warranty",
            help="價金返還是最保護買方的機制：建商倒了，你的錢全額退",
        )

    builder_score = sum(
        [builder_capital, builder_years, builder_completed, builder_warranty]
    )

    if builder_score < 3:
        st.error(
            f"⚠️ **建商體質脆弱！僅符合 {builder_score} / 4 項硬指標。**\n\n"
            "極高機率遇到 **爛尾樓、延遲交屋、品質糾紛、廣告不實**。"
            "近年新聞上的爛尾建案，幾乎都是這類『資本不足 + 履約保證不完備』的小建商。\n\n"
            "**👉 強烈建議：直接避開此案。** "
            "便宜 10% 但拿不到房子，是 100% 的虧損。"
        )
    elif builder_score == 4:
        st.success(
            "✅ **建商體質完美達標！** 四大硬指標全數通過，"
            "可放心進入下一階段評估。"
        )
    else:
        st.success(
            f"✅ **建商體質通過（{builder_score} / 4 項符合）。** "
            "基礎安全門檻達成，但仍建議繼續查詢建商過往負評與消費糾紛紀錄。"
        )


# ======================================================
# 選址：三多指標 × 嫌惡掃雷
# ======================================================
with tab_location:
    st.header("📍 選址：三多指標 × 嫌惡掃雷")
    st.caption("地段心法：『地段三多——交通多、就業多、建設多——是未來增值的鐵三角。』")

    st.markdown("##### 🟢 加分項（三多）")
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        loc_traffic = st.checkbox(
            "🚄 **交通多**：捷運/高鐵/交流道 10 分鐘內", key="adv_loc_traffic",
        )
    with lc2:
        loc_job = st.checkbox(
            "🏢 **就業機會多**：科學園區/大型商辦聚落", key="adv_loc_job",
        )
    with lc3:
        loc_build = st.checkbox(
            "🏗️ **重大建設多**：重劃區/大型公園/特區計畫", key="adv_loc_build",
        )

    plus_count_adv = sum([loc_traffic, loc_job, loc_build])

    st.markdown("##### 🔴 扣分地雷（嫌惡設施）")
    bc3, bc4 = st.columns(2)
    with bc3:
        adv_bad_tower = st.checkbox("⚡ 高壓電塔 / 變電所 200 公尺內", key="adv_bad_tower")
        adv_bad_factory = st.checkbox(
            "🏭 工廠污染源 / 焚化爐", key="adv_bad_factory",
        )
    with bc4:
        adv_bad_flood = st.checkbox(
            "🌊 淹水紀錄區 / 順向坡 / 斷層帶", key="adv_bad_flood",
        )
        adv_bad_funeral = st.checkbox(
            "⚰️ 殯葬設施 / 公墓 / 納骨塔 1 公里內", key="adv_bad_funeral",
        )

    adv_bad_count = sum(
        [adv_bad_tower, adv_bad_factory, adv_bad_flood, adv_bad_funeral]
    )

    # 判定
    st.markdown("##### 📊 選址綜合判定")
    loc_progress = plus_count_adv / 3
    st.progress(
        loc_progress, text=f"三多達成度：{plus_count_adv} / 3（{loc_progress * 100:.0f}%）",
    )

    if adv_bad_count > 0:
        st.error(
            f"🚨 **警告：踩到 {adv_bad_count} 項嫌惡設施地雷！**\n\n"
            "嫌惡設施對房價的影響是 **不可逆的**：\n"
            "- 銀行鑑價會自動砍 10 ~ 20%\n"
            "- 未來轉手週期至少多 6 個月\n"
            "- 買家心理障礙難以化解，即使便宜也賣不掉\n\n"
            "**👉 鐵口直斷：建議立刻放棄此物件。**"
        )
    elif plus_count_adv == 3:
        st.success(
            "🚀 **三多全達標、無地雷！** 這就是 所謂的『精華地段』。"
            "可進入價格議價階段，並準備動手出價。"
        )
    elif plus_count_adv >= 2:
        st.success(
            f"🟢 **地段不錯（{plus_count_adv}/3）且無地雷。** "
            "中長期增值動能可期，可進一步比較價格合理性。"
        )
    elif plus_count_adv == 1:
        st.info(
            f"📋 地段中規中矩（{plus_count_adv}/3），無地雷但題材有限。"
            "建議再多看 5 ~ 10 案，找有題材的物件。"
        )
    else:
        st.warning(
            "⚠️ 三多一項都沒命中、純粹靠建商行銷話術。"
            "提醒：沒題材的物件，靠通膨抗跌都費力。"
        )


# ======================================================
# 決策助手：合理房價與增貸空間試算
# ======================================================
with sub_price:
    st.header("💲 整棟大廈估價法 × 增貸空間試算")
    st.caption("公式：(同棟最高單價 - 你的目標單價) × 坪數 = 預估潛在增貸空間。")

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        max_unit_price = st.number_input(
            "同社區/同棟最高實價登錄單價（萬/坪）",
            0.0, value=70.0, step=0.5, key="adv_max_price",
            help="可從內政部實價登錄網查同棟最近 12 個月的最高成交價",
        )
    with pc2:
        target_unit_price = st.number_input(
            "你的目標出價單價（萬/坪）",
            0.0, value=55.0, step=0.5, key="adv_target_price",
        )
    with pc3:
        ping_size = st.number_input(
            "房屋權狀坪數",
            0.0, value=30.0, step=0.5, key="adv_ping_size",
        )

    diff_per_ping = max_unit_price - target_unit_price
    total_target_price = target_unit_price * ping_size * 10_000
    total_max_price = max_unit_price * ping_size * 10_000
    potential_gap = diff_per_ping * ping_size * 10_000
    discount_pct = (
        (diff_per_ping / max_unit_price * 100) if max_unit_price > 0 else 0
    )

    st.markdown("---")
    st.markdown("##### 💰 估價結果")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("你的目標總價", f"NT$ {total_target_price:,.0f}")
    mc2.metric(
        "同棟最高總價",
        f"NT$ {total_max_price:,.0f}",
        delta=f"差價 NT$ {potential_gap:,.0f}",
        delta_color="normal" if potential_gap > 0 else "off",
    )
    mc3.metric(
        "預估潛在增貸空間",
        f"NT$ {potential_gap:,.0f}",
        delta=f"-{discount_pct:.1f}% vs 最高價" if diff_per_ping > 0 else "0%",
        delta_color="inverse" if diff_per_ping < 0 else "normal",
        help="你比同棟最高價便宜多少，就是未來銀行可能讓你『搬出來』的錢",
    )

    if potential_gap > 0:
        st.info(
            f"📌 **金句：『銀行估價看整棟，不看單戶！』**\n\n"
            f"你的入手價比同棟最高價低 **NT$ {potential_gap:,.0f}**"
            f"（{discount_pct:.1f}%），這部分就是未來能向銀行『搬出來的錢（增貸額度）』。\n\n"
            "**🧮 實戰換算（以增貸 80% 計）：**\n"
            f"- 預估可增貸金額：**NT$ {potential_gap * 0.8:,.0f}**\n"
            "- 用途：投入 0050 / 保單 / 下一間房頭期款（依富邦增貸 SOP 過水）\n\n"
            "**👉 結論：價差越大越好。挑同棟『最便宜那戶』，等於挑了一個現成的增貸金雞母。**"
        )
    elif potential_gap == 0:
        st.warning(
            "⚠️ 你的目標單價已經等於同棟最高價，**沒有增貸空間**。"
            "再殺價試試，或重新評估標的。"
        )
    else:
        st.error(
            f"❌ **你的目標單價 {target_unit_price} 萬/坪 已高於同棟最高價 "
            f"{max_unit_price} 萬/坪！**\n\n"
            "等於你買的瞬間就『資不抵債』，銀行鑑價會直接砍貸款成數。"
            "**立刻重新議價或放棄此案。**"
        )

    # 議價策略圖
    st.markdown("---")
    st.markdown("##### 📊 議價策略視覺化")
    fig_price = go.Figure()
    fig_price.add_trace(
        go.Bar(
            x=["同棟最高總價", "你的目標總價"],
            y=[total_max_price, total_target_price],
            marker_color=["#C0392B", "#27AE60"],
            text=[f"NT$ {total_max_price:,.0f}", f"NT$ {total_target_price:,.0f}"],
            textposition="outside",
        )
    )
    fig_price.update_layout(
        yaxis_title="總價（元）",
        height=380,
        margin=dict(t=30, b=40),
    )
    st.plotly_chart(fig_price, use_container_width=True)


# ======================================================
# 決策助手：優質租客嚴選雷達
# ======================================================
with sub_tenant:
    st.header("🎯 優質租客嚴選雷達")
    st.caption("租客心法：『寧可空租一個月，也不要租給麻煩客。』")

    st.markdown("##### 📋 看房 4 大檢核項（每項 25 分，滿分 100）")

    tc1, tc2 = st.columns(2)
    with tc1:
        tenant_id = st.checkbox(
            "🪪 能主動提供工作名片 / 在職證明", key="adv_tn_id",
            help="主動透明 = 沒在隱藏",
        )
        tenant_ontime = st.checkbox(
            "⏰ 看房準時、無遲到", key="adv_tn_ontime",
            help="連看房都遲到，繳房租也不會準時",
        )
    with tc2:
        tenant_polite = st.checkbox(
            "🙏 溝通態度有禮貌、無不良嗜好（菸/酒/毒品/八大）",
            key="adv_tn_polite",
        )
        tenant_deposit = st.checkbox(
            "💵 兩個月押金能一次付清、不拖欠", key="adv_tn_deposit",
            help="連押金都湊不出來，月租金更難穩定",
        )

    tenant_items = [tenant_id, tenant_ontime, tenant_polite, tenant_deposit]
    tenant_score = sum(tenant_items) * 25

    st.markdown("---")
    st.markdown("##### 🏆 租客評分結果")

    score_col, gauge_col = st.columns([1, 1])
    with score_col:
        st.metric("租客總分", f"{tenant_score} / 100", delta=f"{tenant_score - 75:+d} vs 通過線")
        st.progress(
            tenant_score / 100,
            text=f"通過率：{tenant_score}% (通過標準 ≥ 75%)",
        )
        st.caption(
            "勾選項目：\n"
            f"- {'✅' if tenant_id else '❌'} 工作證明\n"
            f"- {'✅' if tenant_ontime else '❌'} 看房準時\n"
            f"- {'✅' if tenant_polite else '❌'} 禮貌無不良嗜好\n"
            f"- {'✅' if tenant_deposit else '❌'} 押金一次付清"
        )

    with gauge_col:
        fig_tenant = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=tenant_score,
                number={"suffix": " 分", "font": {"size": 44}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2C3E50"},
                    "steps": [
                        {"range": [0, 50], "color": "#F5B7B1"},
                        {"range": [50, 75], "color": "#F9E79F"},
                        {"range": [75, 100], "color": "#A9DFBF"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.8,
                        "value": 75,
                    },
                },
                title={"text": "優質租客指數"},
            )
        )
        fig_tenant.update_layout(height=260, margin=dict(t=40, b=20))
        st.plotly_chart(fig_tenant, use_container_width=True)

    if tenant_score < 75:
        st.warning(
            f"⚠️ **租客評分 {tenant_score} 分（< 75 分通過線）。**\n\n"
            "**鐵則：寧可空租一個月，也不要租給麻煩客！**\n\n"
            "把問題租客請進來的代價：\n"
            "- 拖欠房租 → 訴訟成本 NT$ 20,000+，跑流程 6 個月起\n"
            "- 屋況破壞 → 修繕費吃掉押金還倒貼\n"
            "- 蟑螂租客（占住不走）→ 損失最高可達一年租金\n"
            "- 鄰居檢舉、社區糾紛 → 被列管後物件難轉手\n\n"
            "**👉 行動方針：果斷說「不」，繼續找下一位。** "
            "好的房子永遠不缺租客，不要急。"
        )
    else:
        st.success(
            f"✅ **租客評分 {tenant_score} 分（≥ 75 分通過線）！**\n\n"
            "此為 所謂的『優質租客體質』，可進入正式簽約階段。\n\n"
            "**📝 簽約前最後檢核：**\n"
            "- 押金、首月租金 **匯款入帳後** 再交鑰匙\n"
            "- 合約載明：禁止轉租、禁止違法用途、退租前 30 天通知\n"
            "- 拍照存證屋況、清點家電（雙方簽字）\n"
            "- 二聯式發票報稅可選擇『個人租賃所得』申報"
        )


# ===================== 頁尾 =====================
st.divider()
st.caption(
    "※ 本工具整合自三份房地產實戰試算表，"
    "提供方向性自我檢核；實際銀行核貸條件以各銀行徵授信標準為準。"
)
