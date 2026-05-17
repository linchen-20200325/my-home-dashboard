"""Chapter 9：學長 AI 實戰顧問 — Thin wrapper（重構後）。

實作已搬遷至 ``app.ui.pages.chapter_9_ai``。
Migration step: Phase 2 #23
"""

from __future__ import annotations

from app.ui.pages.chapter_9_ai import render_chapter_9_ai

__all__ = ["render_chapter_9_ai"]


if __name__ == "__main__":
    import streamlit as st

    st.set_page_config(
        page_title="Ch.9 學長 AI 實戰顧問",
        page_icon="🤖",
        layout="wide",
    )
    render_chapter_9_ai()
