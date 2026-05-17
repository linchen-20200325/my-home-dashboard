"""Streamlit Cloud 入口點（第一順位偵測檔名）。

Streamlit Cloud 部署時的檔名偵測順序：
    1. ``streamlit_app.py``（本檔，社群慣用）
    2. ``app.py``
    3. 由部署者在 dashboard 自訂

內容與 ``main.py`` 完全一致，目的是讓 ``streamlit run streamlit_app.py``
（或 Streamlit Cloud 自動偵測）能直接執行整個 APP。

Migration note (Phase 2 #32 後遺症修復):
    PR #12 把 legacy ``app.py`` 搬到 ``_legacy/`` 後，
    Streamlit Cloud 找不到原本的入口檔。本檔（與根目錄 ``app.py``）
    讓 Streamlit Cloud 的任一預設偵測順序都能成功啟動。
"""

from __future__ import annotations

import streamlit as st

from app.ui.router import run


st.set_page_config(
    page_title="房產攻略",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)


run()
