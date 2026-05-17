"""Chapter 9 UI — 學長 AI 實戰顧問（重構後）。

UI 層：純 Streamlit 對話介面；
    - API Key 解析委派給 ``repositories.secrets.resolve_api_key``
    - 串流對話委派給 ``services.ai_advisor.stream_mentor_reply``
    - 訊息以 ``models.ai.ChatMessage`` DTO 儲存於 session_state

依層架構：
    UI 不直接 import openai。所有 SDK 互動經由 ai_advisor service
    → openai_client repository 中介；只有 SDK 例外（OpenAI API errors）
    會經由 ai_advisor.stream_mentor_reply 原型 propagate 上來，
    本層用一個 broad except 翻譯成使用者友善訊息。
"""

from __future__ import annotations

import streamlit as st

from app.models.ai import AIConfig, ChatMessage, ChatRole
from app.models.constants import (
    OPENAI_API_KEY_SECRET_NAME,
    OPENAI_DEFAULT_MODEL,
    OPENAI_DEFAULT_TEMPERATURE,
    OPENAI_MODEL_OPTIONS,
    OPENAI_TEMPERATURE_MAX,
    OPENAI_TEMPERATURE_MIN,
)
from app.repositories.secrets import resolve_api_key
from app.services.ai_advisor import stream_mentor_reply


# ===== 起手式問題（給使用者一鍵發問，純 UI display data）=====
STARTER_QUESTIONS: list[str] = [
    "學長，建商要我支付天然瓦斯與自來水管線費，這合理嗎？",
    "我月薪 6 萬、有車貸 1.2 萬，買得起 2,000 萬的房子嗎？",
    "新北中和某預售案『同業連帶擔保』履保，可以買嗎？",
    "謄本他項權利部寫了一個私人姓名，這代表什麼？",
    "我想用科目四洗白資金，學長能幫我擬時間軸嗎？",
    "屋齡 32 年的公寓 4 樓，學長覺得能進場嗎？",
]


def _render_sidebar_controls() -> AIConfig:
    """設定面板：API Key、模型、temperature。回傳 AIConfig DTO。"""
    with st.expander("⚙️ **AI 顧問設定**（API Key / 模型 / 創意度）", expanded=False):
        st.text_input(
            "🔑 OpenAI API Key",
            type="password",
            placeholder="sk-...（或設定於 .streamlit/secrets.toml）",
            help="不會儲存到伺服器，只在當前 session 使用。建議部署時改用 st.secrets。",
            key="ch9_api_key_input",
        )

        col_m, col_t = st.columns(2)
        with col_m:
            model = st.selectbox(
                "AI 模型",
                options=list(OPENAI_MODEL_OPTIONS),
                index=OPENAI_MODEL_OPTIONS.index(OPENAI_DEFAULT_MODEL),
                help="gpt-4o-mini 經濟快速；gpt-4o 回答最深入。",
                key="ch9_model",
            )
        with col_t:
            temperature = st.slider(
                "創意度（temperature）",
                min_value=OPENAI_TEMPERATURE_MIN,
                max_value=OPENAI_TEMPERATURE_MAX,
                value=OPENAI_DEFAULT_TEMPERATURE,
                step=0.1,
                help="低 = 嚴謹引用法規；高 = 更靈活的學長口氣。建議 0.5-0.9。",
                key="ch9_temperature",
            )

        if st.button("🧹 清空對話歷史", use_container_width=True, key="ch9_clear"):
            st.session_state.ch9_messages = []
            st.rerun()

    api_key = resolve_api_key(
        st.session_state.get("ch9_api_key_input"),
        OPENAI_API_KEY_SECRET_NAME,
    )
    return AIConfig(
        api_key=api_key or "",
        model=model,
        temperature=temperature,
    )


def _render_starter_chips() -> None:
    """顯示快速提問按鈕（首次進入或對話清空時）。"""
    st.caption("💡 **不知道從哪問起？點下面任一題快速開場：**")
    cols = st.columns(2)
    for idx, question in enumerate(STARTER_QUESTIONS):
        target_col = cols[idx % 2]
        with target_col:
            if st.button(
                question, key=f"ch9_starter_{idx}", use_container_width=True,
            ):
                st.session_state.ch9_pending_input = question
                st.rerun()


def _render_history(messages: list[ChatMessage]) -> None:
    """渲染對話歷史。"""
    for msg in messages:
        avatar = "🧑‍🎓" if msg.role == ChatRole.USER else "🎓"
        with st.chat_message(msg.role.value, avatar=avatar):
            st.markdown(msg.content)


def render_chapter_9_ai() -> None:
    """🤖 學長 AI 實戰顧問（Chapter 9）— UI 入口。"""
    st.title("🤖 學長 AI 實戰顧問")
    st.caption(
        "🛡️ 內建學長團隊鐵律 × OpenAI GPT 引擎｜"
        "建商坑你的合約、房仲的話術、銀行不會講的眉角——**問就對了**。"
    )

    config = _render_sidebar_controls()

    # ----- session_state 初始化 -----
    if "ch9_messages" not in st.session_state:
        st.session_state.ch9_messages: list[ChatMessage] = []
    if "ch9_pending_input" not in st.session_state:
        st.session_state.ch9_pending_input: str | None = None

    # ----- API Key 缺失警告 -----
    if not config.is_ready:
        st.warning(
            "🔑 **請先在上方設定區填入 OpenAI API Key**，或於部署環境設定 "
            "`.streamlit/secrets.toml`：\n\n"
            f"```toml\n{OPENAI_API_KEY_SECRET_NAME} = \"sk-...\"\n```"
        )

    st.markdown("---")

    # ----- 對話歷史或起手式按鈕 -----
    history: list[ChatMessage] = st.session_state.ch9_messages
    if not history:
        _render_starter_chips()
    else:
        _render_history(history)

    # ----- 取得使用者輸入（chat_input 或 starter chip 觸發）-----
    user_input = st.chat_input(
        "輸入你的問題（例：學長，建商要我付瓦斯管線費怎麼辦？）",
        disabled=not config.is_ready,
        key="ch9_chat_input",
    )
    if st.session_state.ch9_pending_input:
        user_input = st.session_state.ch9_pending_input
        st.session_state.ch9_pending_input = None

    if not user_input:
        return

    # ----- 寫入使用者訊息並渲染 -----
    user_msg = ChatMessage(role=ChatRole.USER, content=user_input)
    history.append(user_msg)
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    # ----- 委派 service 串流回應 -----
    try:
        with st.chat_message("assistant", avatar="🎓"):
            with st.spinner("學長思考中…"):
                response_text = st.write_stream(
                    stream_mentor_reply(config, history)
                )

        history.append(
            ChatMessage(role=ChatRole.ASSISTANT, content=response_text)
        )
    except Exception as exc:  # noqa: BLE001 — 對使用者轉譯任何 SDK 例外
        with st.chat_message("assistant", avatar="⚠️"):
            st.error(
                f"❌ **AI 服務呼叫失敗**：{type(exc).__name__}\n\n"
                f"```\n{exc}\n```\n\n"
                "請檢查 API Key 是否正確、額度是否足夠、或選用另一個模型重試。"
            )
        # 失敗訊息不寫入歷史，避免污染下次對話 context
        history.pop()
