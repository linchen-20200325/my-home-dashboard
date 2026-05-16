"""Ziv學長：房產投資實戰攻略神機 — 主應用程式骨架。

七大模組以獨立 render_chapter_X() 函式分離，側邊欄選單分派渲染。
"""

import streamlit as st


# ===================== 頁面基本設定 =====================
st.set_page_config(
    page_title="Ziv房產攻略",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===================== 各章節渲染函式 =====================
def render_chapter_1() -> None:
    """🏠 首頁與個人現金流診斷（Chapter 1）"""
    st.title("🏠 首頁與個人現金流診斷")
    st.info(
        "💡 **Ziv學長的實戰金句**：「買房不是看你賺多少，是看你『留』下多少。"
        "現金流就是你的氧氣，氧氣斷掉那天，就是被強制下車那天。」"
    )


def render_chapter_2() -> None:
    """🏗️ 預售屋：買就賺選址與合約快篩（Chapter 2）"""
    st.title("🏗️ 預售屋：買就賺選址與合約快篩")
    st.info(
        "💡 **Ziv學長的實戰金句**：「預售屋的利潤鎖在『簽約那一刻』，不是交屋那一刻。"
        "便宜不是省下來的，是『選』下來的——選錯地段、選錯建商，再大的折扣都是糖衣。」"
    )


def render_chapter_3() -> None:
    """💰 租金精算與優質租客雷達（Chapter 3）"""
    st.title("💰 租金精算與優質租客雷達")
    st.info(
        "💡 **Ziv學長的實戰金句**：「寧可空租一個月，也不要租給麻煩客。"
        "租客選錯，整年白做工；房子被搞爛，五年的租金都不夠補。」"
    )


def render_chapter_4() -> None:
    """🏦 槓桿魔法：科目四金流過水 SOP（Chapter 4）"""
    st.title("🏦 槓桿魔法：科目四金流過水 SOP")
    st.info(
        "💡 **Ziv學長的實戰金句**：「銀行看的不是你有多少錢，是你『看起來』有多少錢。"
        "金流要做給銀行看、自備款要做給代書看——數字會說話，但你要先教它怎麼說。」"
    )


def render_chapter_5() -> None:
    """🏢 中古屋：居住成本與出價沙盤推演（Chapter 5）"""
    st.title("🏢 中古屋：居住成本與出價沙盤推演")
    st.info(
        "💡 **Ziv學長的實戰金句**：「實價登錄是給你看『他賣多少』，不是『你該出多少』。"
        "出價要往下砍、不要往上追；屋主開的是『心願價』，你要還的是『成交價』。」"
    )


def render_chapter_6() -> None:
    """🛡️ 節稅護城河與裝潢抵稅清單（Chapter 6）"""
    st.title("🛡️ 節稅護城河與裝潢抵稅清單")
    st.info(
        "💡 **Ziv學長的實戰金句**：「合法節稅不是逃稅，是知道規則的人才有的紅利。"
        "每一筆裝潢都該留發票——未來賣房時，這就是你抵稅的盔甲。」"
    )


def render_chapter_7() -> None:
    """🚪 安全離場與流動性評估（Chapter 7）"""
    st.title("🚪 安全離場與流動性評估")
    st.info(
        "💡 **Ziv學長的實戰金句**：「會買的是徒弟，會賣的才是師父。"
        "離場時機決定報酬率，流動性決定你能不能在『想下車時』下車——別讓自己成為最後一棒。」"
    )


# ===================== 章節對照表（標籤 → 渲染函式）=====================
CHAPTERS = {
    "🏠 首頁與個人現金流診斷": render_chapter_1,
    "🏗️ 預售屋：買就賺選址與合約快篩": render_chapter_2,
    "💰 租金精算與優質租客雷達": render_chapter_3,
    "🏦 槓桿魔法：科目四金流過水 SOP": render_chapter_4,
    "🏢 中古屋：居住成本與出價沙盤推演": render_chapter_5,
    "🛡️ 節稅護城河與裝潢抵稅清單": render_chapter_6,
    "🚪 安全離場與流動性評估": render_chapter_7,
}


# ===================== 側邊欄導航 =====================
with st.sidebar:
    st.title("📚 Ziv房產攻略")
    st.caption("七大實戰模組｜心法 × 工具 × 沙盤")
    st.markdown("---")
    selected_chapter = st.radio(
        "選擇章節",
        list(CHAPTERS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("v1.0 ｜ 攻略骨架版本")


# ===================== 路由分派：渲染所選章節 =====================
CHAPTERS[selected_chapter]()
