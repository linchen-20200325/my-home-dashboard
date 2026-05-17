"""共用 cross-chapter 跳轉元件。

設計：sidebar 的章節 ``st.radio`` 用 ``key=NAV_STATE_KEY`` 綁定 session_state，
**該 key 不可在 widget 已建立後手動寫入**（會觸發 ``StreamlitAPIException``）。
本元件因此採『pending → radio default』的兩段式：

    1. 按鈕被按下 → 寫入 ``NAV_PENDING_KEY``（**未綁定任何 widget**），再 ``st.rerun()``
    2. 下次 rerun 時，``router.run()`` 在 ``st.radio`` 建立**之前**呼叫
       ``apply_pending_nav()``：若有 pending，pop 出來寫進 ``NAV_STATE_KEY``
       作為 radio 的初始值（這個寫入是合法的，因為 widget 尚未存在）。

注意：``target_chapter_key`` 必須與 ``app.ui.router.CHAPTERS`` dict 的 key 完全一致
（含 emoji 前綴與全形冒號）。錯字會被 ``apply_pending_nav`` 忽略——sidebar 保持
原狀，不會崩潰。
"""

from __future__ import annotations

from typing import Iterable

import streamlit as st


# Widget-bound key — 由 router.run() 的 st.radio 持有。
# 任何頁面**不可**在同一 script run 內直接寫此 key，必須走 NAV_PENDING_KEY。
NAV_STATE_KEY: str = "__current_chapter"

# 未綁定 widget 的中介 key — 跨頁跳轉用。
NAV_PENDING_KEY: str = "__pending_chapter"


def chapter_jump_button(
    label: str,
    target_chapter_key: str,
    *,
    button_key: str | None = None,
    use_container_width: bool = False,
) -> bool:
    """渲染跳轉按鈕。按下後寫 pending key 並 rerun，下個 run sidebar 自動切換。

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
        # ⚠️ 不可直接寫 NAV_STATE_KEY——它被 sidebar radio 綁定，會拋
        # StreamlitAPIException。改寫未綁定的 pending key，由 router 在下次
        # rerun 的 radio 建立前消化。
        st.session_state[NAV_PENDING_KEY] = target_chapter_key
        st.rerun()
        # 不會到這裡，但 mypy 要 return 值
        return True
    return False


def apply_pending_nav(valid_chapter_keys: Iterable[str]) -> None:
    """由 router.run() 在 ``st.radio`` 建立**之前**呼叫，消化 pending 跳轉。

    若 ``NAV_PENDING_KEY`` 存在且目標 key 為合法章節，則寫進 ``NAV_STATE_KEY``
    作為 radio 的初始值，並 pop pending。未知 key 會被靜默丟棄（避免錯字
    汙染 widget）。

    Args:
        valid_chapter_keys: CHAPTERS dict 的所有合法 key（用來驗 target）。
    """
    pending = st.session_state.pop(NAV_PENDING_KEY, None)
    if pending and pending in set(valid_chapter_keys):
        # radio widget 尚未在本次 run 建立 → 直接寫 NAV_STATE_KEY 是合法的，
        # 等同提供 widget 的 default value。
        st.session_state[NAV_STATE_KEY] = pending
