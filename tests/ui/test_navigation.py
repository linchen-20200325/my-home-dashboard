"""Unit tests — app.ui.components.navigation。

Streamlit 元件本身需要 Streamlit runtime context 才能完整跑，本測試
聚焦於『行為合約』而非實際 UI rendering：
    - NAV_STATE_KEY 常數穩定
    - chapter_jump_button 在按下時設定 session_state 並 rerun
    - 找不到 button_key 時自動推導
"""

from __future__ import annotations

import pytest

# Skip 整個 module 若沒裝 streamlit（本地開發環境）。
# CI 有 streamlit（requirements.txt 拉進來），會正常執行。
pytest.importorskip("streamlit")

from app.ui.components.navigation import NAV_STATE_KEY, chapter_jump_button  # noqa: E402


pytestmark = [pytest.mark.repositories]  # 借用一個有效 marker — 純 UI 元件


class TestNavStateKey:
    def test_key_is_stable_string(self) -> None:
        """NAV_STATE_KEY 是 router.run() 與 chapter_jump_button 之間的合約，
        若被人不小心改名兩邊就會脫鉤。固定字串值用 assert 鎖住。"""
        assert NAV_STATE_KEY == "__current_chapter"
        assert isinstance(NAV_STATE_KEY, str)


class TestChapterJumpButton:
    def test_button_writes_state_and_reruns_on_click(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """按下按鈕 → session_state[NAV_STATE_KEY] = target，再呼叫 st.rerun()。"""
        from app.ui.components import navigation as nav_mod

        # 用 dict 模擬 session_state
        fake_state: dict[str, str] = {}
        rerun_calls: list[bool] = []

        class _FakeSt:
            session_state = fake_state

            @staticmethod
            def button(label, *, key=None, use_container_width=False):  # type: ignore[no-untyped-def]
                # 模擬「使用者按下」
                return True

            @staticmethod
            def rerun():  # type: ignore[no-untyped-def]
                rerun_calls.append(True)
                # 真實 st.rerun() 會拋例外中斷 script，這裡直接 raise 來
                # 驗證 chapter_jump_button 不會在 rerun 後執行任何後續邏輯
                raise RuntimeError("rerun_called")

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        with pytest.raises(RuntimeError, match="rerun_called"):
            chapter_jump_button("→ Ch.4", "🏦 Ch.4 槓桿魔法:科目四金流過水 SOP")

        assert fake_state[NAV_STATE_KEY] == "🏦 Ch.4 槓桿魔法:科目四金流過水 SOP"
        assert rerun_calls == [True]

    def test_returns_false_when_button_not_clicked(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.ui.components import navigation as nav_mod

        fake_state: dict[str, str] = {}

        class _FakeSt:
            session_state = fake_state

            @staticmethod
            def button(label, *, key=None, use_container_width=False):  # type: ignore[no-untyped-def]
                return False  # 未按下

            @staticmethod
            def rerun():  # type: ignore[no-untyped-def]
                raise AssertionError("should not rerun when button not clicked")

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        result = chapter_jump_button("→ Ch.4", "any_target")
        assert result is False
        assert fake_state == {}  # state 不被污染

    def test_button_key_auto_derived_from_target(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """不傳 button_key 時，自動以 ``f'jump_{target}'`` 推導。"""
        from app.ui.components import navigation as nav_mod
        captured: dict[str, object] = {}

        class _FakeSt:
            session_state = {}

            @staticmethod
            def button(label, *, key=None, use_container_width=False):  # type: ignore[no-untyped-def]
                captured["key"] = key
                return False

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        chapter_jump_button("→ Ch.X", "target_label")
        assert captured["key"] == "jump_target_label"
