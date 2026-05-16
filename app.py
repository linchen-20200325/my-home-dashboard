"""
Ziv學長：買房前自我能力與現金流健檢
單頁式 Streamlit 應用程式 - 嚴格依據 Ziv學長房地產投資與財富思維實戰課程公式
"""

import streamlit as st


# ---------- 頁面基礎設定 ----------
st.set_page_config(
    page_title="Ziv學長：買房前自我能力與現金流健檢",
    page_icon="🏠",
    layout="wide",
)


# ---------- 標題區 ----------
st.title("🏠 Ziv學長：買房前自我能力與現金流健檢")
st.caption(
    "依據《Ziv學長房地產投資與財富思維》實戰筆記，"
    "從「階級現金流」與「貸款資格」兩大維度，幫你看清自己現在站在哪一階。"
)
st.divider()


# ---------- 側邊欄輸入區 ----------
with st.sidebar:
    st.header("📋 現況輸入區")
    st.caption("請誠實填寫，數字騙得了自己，騙不了銀行徵信。")

    st.subheader("👤 個人基本條件")
    age = st.number_input(
        "目前年齡",
        min_value=18,
        max_value=80,
        value=30,
        step=1,
        help="銀行核貸關鍵變數之一。",
    )
    loan_years = st.number_input(
        "預計申請貸款年限（年）",
        min_value=10,
        max_value=40,
        value=30,
        step=5,
        help="一般銀行最長 30 年，部分方案可拉至 40 年。",
    )

    st.subheader("💵 收支金流狀況")
    monthly_income = st.number_input(
        "每月總收入（薪資＋穩定副業）",
        min_value=0,
        value=60000,
        step=1000,
    )
    monthly_bad_debt = st.number_input(
        "每月壞債支出（信用卡分期、信貸、車貸…等「消耗現金流」負債）",
        min_value=0,
        value=10000,
        step=1000,
        help="這些是 Ziv學長口中典型的「窮人/中產陷阱」支出。",
    )
    monthly_living = st.number_input(
        "每月生活開銷（房租、伙食、孝親、交通…）",
        min_value=0,
        value=25000,
        step=1000,
    )

    st.subheader("🏦 財力證明狀況")
    total_assets = st.number_input(
        "名下總資產估值（含現金、定存單、有價證券、權狀…）",
        min_value=0,
        value=2_000_000,
        step=10_000,
    )
    total_liabilities = st.number_input(
        "名下總負債餘額（含信貸、車貸、卡債本金…）",
        min_value=0,
        value=500_000,
        step=10_000,
    )


# ---------- 核心計算 ----------
monthly_surplus = monthly_income - monthly_bad_debt - monthly_living

bad_debt_ratio = (monthly_bad_debt / monthly_income) if monthly_income > 0 else 0.0

dti_ratio = (monthly_bad_debt / monthly_income) if monthly_income > 0 else 1.0

age_plus_loan = age + loan_years

if total_liabilities > 0:
    asset_liability_ratio = total_assets / total_liabilities
else:
    asset_liability_ratio = float("inf")


# ============================================================
# 區塊一：階級現金流與財富思維診斷
# ============================================================
st.header("一、階級現金流與財富思維診斷")
st.caption("PPT 第一課：『不是收入決定階級，而是現金流決定階級。』")

col1, col2, col3 = st.columns(3)
col1.metric("每月總收入", f"NT$ {monthly_income:,.0f}")
col2.metric(
    "每月結餘（多餘現金流）",
    f"NT$ {monthly_surplus:,.0f}",
    delta=f"{monthly_surplus:,.0f}",
    delta_color="normal" if monthly_surplus >= 0 else "inverse",
)
col3.metric("壞債佔收入比", f"{bad_debt_ratio * 100:.1f}%")

st.markdown("##### 📊 Ziv學長階級現金流動態判定")

if monthly_surplus < 0:
    # 情境 A：窮人思維危險區
    st.error(
        "⚠️ **窮人現金流：努力工作賺錢，然後把錢花光。**\n\n"
        "你目前的現金流是 **負的**，等於每個月還沒月底就先被掏空。"
        "Ziv學長明白告訴你：這時候談買房、談槓桿都是空話。\n\n"
        "**👉 行動方針：先專注於『節流』並清除信用卡分期、循環利息等壞債，"
        "把現金流先拉回正號，才有資格進入下一階段。**"
    )
elif monthly_surplus > 0 and bad_debt_ratio > 0.15:
    # 情境 B：中產階級迷思
    st.warning(
        "⚠️ **中產階級迷思：把花錢的東西當成資產。**\n\n"
        f"你的結餘雖然是正的（每月 +NT$ {monthly_surplus:,.0f}），"
        f"但**壞債支出已佔總收入 {bad_debt_ratio * 100:.1f}%（>15%）**，"
        "這代表你正在把新車、3C、高消費、信貸支出，誤當成『生活品質』。"
        "Ziv學長提醒：這些是『把錢從你口袋拿走的東西』，是負債而不是資產。\n\n"
        "**👉 行動方針：把車貸／信貸／卡循還清，區分『好債（買生錢資產）』與"
        "『壞債（買花錢負債）』，才能真正開啟低利房貸的槓桿大門。**"
    )
else:
    # 情境 C：富人思維啟動
    st.success(
        "✅ **富人現金流！恭喜你具備累積『好債』的能力。**\n\n"
        f"每月結餘 +NT$ {monthly_surplus:,.0f}，且壞債比僅 "
        f"{bad_debt_ratio * 100:.1f}%（≤15%），這是 Ziv學長口中"
        "「準備好被銀行喜歡」的體質。\n\n"
        "**👉 下一步：持續建立信用、養財力證明，準備向銀行借低息房貸，"
        "買入『生錢資產（如預售屋／收租房／可增值地段）』，"
        "讓資產替你工作、用銀行的錢累積你的身家。**"
    )

st.divider()


# ============================================================
# 區塊二：房產貸款資格實戰檢核
# ============================================================
st.header("二、房產貸款資格實戰檢核")
st.caption("PPT 第二課：『銀行不是看你多有錢，是看你「能不能還」與「值不值得借」。』")

col_a, col_b, col_c = st.columns(3)
col_a.metric("年齡 + 貸款年限", f"{age_plus_loan} 年", help="銀行核貸關鍵第一道門檻。")
col_b.metric("收支負債比（DTI）", f"{dti_ratio * 100:.1f}%")
col_c.metric(
    "總資產 / 總負債",
    "∞ (無負債)" if total_liabilities == 0 else f"{asset_liability_ratio:.2f} 倍",
)

# ---- 1. 年齡 + 貸款年限門檻 ----
st.markdown("##### 🎯 檢核 1：年齡與貸款年限雙重門檻")
if age_plus_loan > 75:
    st.error(
        f"⚠️ **年齡＋年限 = {age_plus_loan} 年，已超過銀行 75 上限。**\n\n"
        "Ziv學長實戰提醒：銀行會自動**幫你縮短貸款年限**，"
        "結果就是每月本息攤還金額爆增、壓垮現金流，甚至被砍成數。\n\n"
        "**👉 對策：縮短預計年限、或請年輕共同借款人加保，"
        "也可考慮分段式還款方案。**"
    )
else:
    st.success(
        f"✅ **年齡＋年限 = {age_plus_loan} 年（≤ 75），通過銀行第一道門檻！**\n\n"
        "你還在銀行樂於承作長年期房貸的安全區，月付金可以壓低、現金流更彈性。"
    )

# ---- 2. DTI（收支負債比）紅線 ----
st.markdown("##### 🎯 檢核 2：銀行紅線 — 收支負債比（DTI）")
if dti_ratio >= 0.70:
    st.error(
        f"⚠️ **DTI = {dti_ratio * 100:.1f}%，已突破 70% 紅線！**\n\n"
        "Ziv學長實戰提醒：這是銀行直接亮紅燈的數字，"
        "**極可能遭拒貸、或大砍成數（從 8 成砍到 6 成以下）、利率也會被加碼。**\n\n"
        "**👉 對策：先把信貸、車貸、卡循一次性壓低，"
        "把 DTI 降到 60% 以下再送件，核貸成數差很多。**"
    )
else:
    st.success(
        f"✅ **DTI = {dti_ratio * 100:.1f}%（< 70%），安全通過！**\n\n"
        "你的月負債／月收入比落在銀行可接受區間，"
        "送件時被退案的機率大幅下降，談成數與利率都更有底氣。"
    )

# ---- 3. 總資產負債比（無敵財力證明） ----
st.markdown("##### 🎯 檢核 3：無敵財力證明 — 總資產負債比")
if total_liabilities == 0:
    st.success(
        "🚀 **無敵財力證明：你目前無任何負債！**\n\n"
        "資產負債比視為直接過關。Ziv學長口中的「乾淨身家」，"
        "送件時銀行幾乎搶著放款，可爭取最高成數＋最低利率。"
    )
elif asset_liability_ratio > 1.5:
    st.success(
        f"🚀 **無敵財力證明：資產負債比 = {asset_liability_ratio:.2f} 倍（> 1.5）！**\n\n"
        "這是 Ziv學長強調的「資產型財力證明超級加分項」。\n\n"
        "**👉 你能向銀行爭取：最高成數（8.5 ~ 9 成）、最低利率，"
        "甚至能加碼信貸做頭期款的『資金鏈疊加』。**"
    )
else:
    st.warning(
        f"⚠️ **資產負債比 = {asset_liability_ratio:.2f} 倍（≤ 1.5），財力證明偏弱。**\n\n"
        "Ziv學長建議：可以透過下列方式『養金流、養財力』：\n"
        "- 把活存資金集中轉成 **大額定存單**（綁約越久越漂亮）\n"
        "- 整理 **股票／ETF 對帳單**、基金對帳單\n"
        "- 不動產 **權狀、租賃契約** 一起附上\n"
        "- 適度提前清掉小額負債（卡循、信貸尾款），分母先降低\n\n"
        "送件前 6 ~ 12 個月就要開始佈局，臨時抱佛腳銀行看得出來。"
    )

st.divider()


# ---------- 總結與行動建議 ----------
st.header("📌 Ziv學長給你的下一步")

if monthly_surplus < 0:
    next_step = (
        "**第一階段：止血。** 現金流為負，所有買房計畫先暫停，"
        "回到節流＋清壞債，把每月結餘拉回正號。"
    )
elif (
    monthly_surplus > 0
    and bad_debt_ratio <= 0.15
    and age_plus_loan <= 75
    and dti_ratio < 0.70
    and (total_liabilities == 0 or asset_liability_ratio > 1.5)
):
    next_step = (
        "**全部過關！** 你已具備 Ziv學長口中的「銀行眼中乖寶寶」體質，"
        "可以開始挑物件、跑銀行、談條件。記得：**先過件、再殺價**，"
        "把利率與成數打到最甜的位置。"
    )
elif monthly_surplus > 0 and bad_debt_ratio > 0.15:
    next_step = (
        "**第二階段：轉骨。** 結餘是正的但壞債過重，"
        "請先還清車貸／信貸／卡循，把『中產迷思支出』砍掉，"
        "再進入買房規劃。"
    )
else:
    next_step = (
        "**第三階段：補強財力證明與年限結構。** 現金流體質沒問題，"
        "但年齡＋年限或資產負債比還沒達到最佳狀態，"
        "用 6 ~ 12 個月時間養金流、養存單、養對帳單，再送件最划算。"
    )

st.info(next_step)

st.caption(
    "※ 本工具僅依據 Ziv學長實戰課程公式提供方向性自我檢核，"
    "實際核貸條件以各銀行徵授信標準為準。"
)
