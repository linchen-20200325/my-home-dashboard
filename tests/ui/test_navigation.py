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

from app.ui.components.navigation import (  # noqa: E402
    NAV_PENDING_KEY,
    NAV_STATE_KEY,
    apply_pending_nav,
    chapter_jump_button,
)


pytestmark = [pytest.mark.repositories]  # 借用一個有效 marker — 純 UI 元件


class TestNavStateKey:
    def test_key_is_stable_string(self) -> None:
        """NAV_STATE_KEY 是 router.run() 與 chapter_jump_button 之間的合約，
        若被人不小心改名兩邊就會脫鉤。固定字串值用 assert 鎖住。"""
        assert NAV_STATE_KEY == "__current_chapter"
        assert isinstance(NAV_STATE_KEY, str)

    def test_pending_key_is_separate_from_state_key(self) -> None:
        """PENDING / STATE 必須是兩個不同的字串——同名會回到 widget-bound
        key 衝突的 bug。"""
        assert NAV_PENDING_KEY != NAV_STATE_KEY
        assert NAV_PENDING_KEY == "__pending_chapter"


class TestChapterJumpButton:
    def test_button_writes_pending_key_not_state_key(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """按下按鈕 → 寫 NAV_PENDING_KEY（**非** NAV_STATE_KEY，後者被 widget
        綁定，同 run 寫入會 StreamlitAPIException），再呼叫 st.rerun()。"""
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

        target = "🏦 Ch.4 槓桿魔法:科目四金流過水 SOP"
        with pytest.raises(RuntimeError, match="rerun_called"):
            chapter_jump_button("→ Ch.4", target)

        # 關鍵：寫 PENDING、不碰 STATE
        assert fake_state[NAV_PENDING_KEY] == target
        assert NAV_STATE_KEY not in fake_state
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


class TestApplyPendingNav:
    """router.run() 在 radio 建立前消化 pending key → NAV_STATE_KEY。"""

    def test_pending_with_valid_target_promotes_to_state(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.ui.components import navigation as nav_mod

        fake_state: dict[str, str] = {NAV_PENDING_KEY: "ch_target"}

        class _FakeSt:
            session_state = fake_state

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        apply_pending_nav(["ch_target", "ch_other"])

        assert fake_state.get(NAV_STATE_KEY) == "ch_target"
        assert NAV_PENDING_KEY not in fake_state  # pending 已 pop

    def test_pending_with_invalid_target_silently_dropped(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """錯字 / 不在 CHAPTERS 的 key 應該被靜默丟棄，不汙染 widget。"""
        from app.ui.components import navigation as nav_mod

        fake_state: dict[str, str] = {NAV_PENDING_KEY: "bogus_chapter"}

        class _FakeSt:
            session_state = fake_state

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        apply_pending_nav(["ch_a", "ch_b"])

        # NAV_STATE_KEY 不該被寫入；pending pop 掉
        assert NAV_STATE_KEY not in fake_state
        assert NAV_PENDING_KEY not in fake_state

    def test_no_pending_is_noop(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.ui.components import navigation as nav_mod

        fake_state: dict[str, str] = {NAV_STATE_KEY: "existing"}

        class _FakeSt:
            session_state = fake_state

        monkeypatch.setattr(nav_mod, "st", _FakeSt)

        apply_pending_nav(["existing", "other"])

        # NAV_STATE_KEY 維持原值，沒被改
        assert fake_state[NAV_STATE_KEY] == "existing"
