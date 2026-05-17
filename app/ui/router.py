"""側邊欄路由：CHAPTERS dict + 分派器。

由 ``app/main.py`` composition root 呼叫 ``run()`` 啟動整個 APP。

直接 import 新分層的 ``app.ui.pages.*``（不經過根目錄 thin wrappers），
讓 router 成為架構藍圖的『唯一』正確 entry point。

Cross-chapter navigation：sidebar radio 用 ``key=NAV_STATE_KEY`` 綁定
session_state，``components.navigation.chapter_jump_button`` 可在任何頁面
寫該 key 後 rerun 來切換選擇的章節。``CHAPTER_KEY_*`` 字串常數讓
跨頁跳轉不必硬寫 sidebar label。
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from app.ui.components.navigation import NAV_STATE_KEY
from app.ui.pages.chapter_1_cashflow import render_chapter_1
from app.ui.pages.chapter_2_presale import render_chapter_2
from app.ui.pages.chapter_3_rental import render_chapter_3
from app.ui.pages.chapter_4_refinance import render_chapter_4
from app.ui.pages.chapter_5_resale import render_chapter_5
from app.ui.pages.chapter_6_tax import render_chapter_6
from app.ui.pages.chapter_7_exit import render_chapter_7
from app.ui.pages.chapter_8_advanced import render_chapter_8
from app.ui.pages.chapter_9_ai import render_chapter_9_ai
from app.ui.pages.chapter_10_decision import render_chapter_10_decision_engine
from app.ui.pages.chapter_11_combat import render_chapter_11_combat_manual
from app.ui.pages.strategy_macro import render_strategy_macro
from app.ui.pages.strategy_negotiation import render_strategy_negotiation
from app.ui.pages.strategy_syndication import render_strategy_syndication


# ===== 章節 key 常數（避免 cross-chapter 跳轉硬寫字串）=====
CHAPTER_KEY_CH1: str = "🏠 Ch.1 首頁與個人現金流診斷"
CHAPTER_KEY_CH2: str = "🏗️ Ch.2 預售屋：買就賺選址與合約快篩"
CHAPTER_KEY_CH3: str = "💰 Ch.3 租金精算與優質租客雷達"
CHAPTER_KEY_CH4: str = "🏦 Ch.4 槓桿魔法:科目四金流過水 SOP"
CHAPTER_KEY_CH5: str = "🏢 Ch.5 中古屋:居住成本與出價沙盤推演"
CHAPTER_KEY_CH6: str = "🛡️ Ch.6 節稅護城河與裝潢抵稅清單"
CHAPTER_KEY_CH7: str = "🚪 Ch.7 安全離場與流動性評估"
CHAPTER_KEY_CH8: str = "🔥 Ch.8 奈米級防坑與核彈策略"
CHAPTER_KEY_CH9_AI: str = "🎓 Ch.9 學長 AI 實戰顧問"
CHAPTER_KEY_CH10: str = "🧭 Ch.10 400 題極限防坑與決策雷達"
CHAPTER_KEY_CH11: str = "⚔️ Ch.11 看房現場實戰戰術手冊"
CHAPTER_KEY_STRATEGY_MACRO: str = "🌏 進階 ｜ 總體經濟與房價燃料理論"
CHAPTER_KEY_STRATEGY_NEGOTIATION: str = "💼 進階 ｜ 極限議價與談判心理戰"
CHAPTER_KEY_STRATEGY_SYNDICATION: str = "🤝 進階 ｜ 合資套利與科目四無限槓桿"


# ===== 章節對照表（標籤 → 渲染函式）=====
# 透過 emoji 前綴在視覺上分組：核心章節 / 進階策略
CHAPTERS: dict[str, Callable[[], None]] = {
    # ----- 核心章節（按 Ch.1 → Ch.11 順序）-----
    CHAPTER_KEY_CH1: render_chapter_1,
    CHAPTER_KEY_CH2: render_chapter_2,
    CHAPTER_KEY_CH3: render_chapter_3,
    CHAPTER_KEY_CH4: render_chapter_4,
    CHAPTER_KEY_CH5: render_chapter_5,
    CHAPTER_KEY_CH6: render_chapter_6,
    CHAPTER_KEY_CH7: render_chapter_7,
    CHAPTER_KEY_CH8: render_chapter_8,
    CHAPTER_KEY_CH9_AI: render_chapter_9_ai,
    CHAPTER_KEY_CH10: render_chapter_10_decision_engine,
    CHAPTER_KEY_CH11: render_chapter_11_combat_manual,
    # ----- 進階實戰策略 -----
    CHAPTER_KEY_STRATEGY_MACRO: render_strategy_macro,
    CHAPTER_KEY_STRATEGY_NEGOTIATION: render_strategy_negotiation,
    CHAPTER_KEY_STRATEGY_SYNDICATION: render_strategy_syndication,
}


SIDEBAR_TITLE: str = "📚 房產攻略"
SIDEBAR_CAPTION_TOP: str = "八大核心章節 × 進階策略 × AI 顧問"
SIDEBAR_CAPTION_BOTTOM: str = "v2.2 ｜ 含 cross-chapter 跳轉"


def run() -> None:
    """渲染側邊欄並分派到使用者選擇的頁面。

    呼叫端（``app/main.py`` 或根目錄 ``main.py``）只需要先做完
    ``st.set_page_config(...)``，然後呼叫本函式即可。

    session_state 設計：sidebar radio 用 ``key=NAV_STATE_KEY`` 綁定 state；
    其他頁面寫該 key + 呼叫 ``st.rerun()`` 即可程式化切頁。
    """
    # 初始預設值（只有 session 首次進入時生效）
    if NAV_STATE_KEY not in st.session_state:
        st.session_state[NAV_STATE_KEY] = CHAPTER_KEY_CH1

    with st.sidebar:
        st.title(SIDEBAR_TITLE)
        st.caption(SIDEBAR_CAPTION_TOP)
        st.markdown("---")
        selected = st.radio(
            "選擇章節",
            list(CHAPTERS.keys()),
            key=NAV_STATE_KEY,
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.caption(SIDEBAR_CAPTION_BOTTOM)

    CHAPTERS[selected]()
