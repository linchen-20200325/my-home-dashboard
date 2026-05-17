"""Streamlit Cloud 入口點（第二順位偵測檔名 + 與既有部署 config 相容）。

與 ``main.py`` / ``streamlit_app.py`` 內容相同；提供多入口讓 Streamlit
Cloud 不論偵測到哪個檔名都能正確啟動。

Migration note (Phase 2 #32 後遺症修復):
    PR #12 把舊版 1,918 行的 standalone ``app.py`` 搬到了 ``_legacy/``，
    但 Streamlit Cloud 的部署 config 可能仍指向 root 的 ``app.py``，
    因此補回一個極輕量的版本作為入口點。

    legacy 標準版本仍可從 ``_legacy/app.py`` 取得。

    **Python import 不會衝突**：當 ``app.py`` 與 ``app/`` package 同存於
    root 時，``import app`` 優先載入 ``app/`` package（已實測驗證），
    本檔僅在 ``streamlit run app.py`` 時當作 script 執行。
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
