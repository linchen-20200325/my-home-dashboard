"""共用 cross-chapter 跳轉元件。

設計：sidebar 的章節 ``st.radio`` 用 ``key=NAV_STATE_KEY`` 綁定 session_state；
任何頁面只要把 ``session_state[NAV_STATE_KEY]`` 改成另一個 CHAPTER label 後
呼叫 ``st.rerun()``，下次 render 時 sidebar 自動切到目標頁面。

由 ``chapter_jump_button`` 包裝這個流程，UI 端只要傳『目標章節 label』即可。

注意：``target_chapter_key`` 必須與 ``app.ui.router.CHAPTERS`` dict 的 key 完全一致
（含 emoji 前綴與全形冒號）。錯字會導致按下後 sidebar 不動，但不會崩潰
（radio 拒絕未知值會 fallback 到第一項，UI 不會炸）。
"""

from __future__ import annotations

import streamlit as st


# 與 router.run() 共用的 session_state key — 改名要同步更新 router.
NAV_STATE_KEY: str = "__current_chapter"


def chapter_jump_button(
    label: str,
    target_chapter_key: str,
    *,
    button_key: str | None = None,
    use_container_width: bool = False,
) -> bool:
    """渲染跳轉按鈕。按下後寫 session_state 並 rerun，sidebar 自動切換。

    Args:
        label:              按鈕顯示文字（例：『→ 去 Ch.4 算增貸空間』）
        target_chapter_key: 目標章節在 CHAPTERS dict 的 key 字串
        button_key:         st.button 的 key（避免重複 widget 衝突）；不傳則
                            自動以 ``f"jump_{target_chapter_key}"`` 推導
        use_container_width: 透傳給 st.button

    Returns:
        True 若按鈕被按下（之後 st.rerun() 會立即觸發，後續程式碼不會執行到）；
        False 表示沒按。
    """
    actual_key = button_key or f"jump_{target_chapter_key}"
    if st.button(label, key=actual_key, use_container_width=use_container_width):
        st.session_state[NAV_STATE_KEY] = target_chapter_key
        st.rerun()
        # 不會到這裡，但 mypy 要 return 值
        return True
    return False
