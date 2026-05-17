"""Chapter 10 UI — 400 題極限防坑與決策雷達（重構後）。

UI 層：純 widgets + 渲染；四象限終極判定由 services.decision_engine。
"""

from __future__ import annotations

import streamlit as st

from app.models.constants import ELEVATOR_RATIO_DANGER, MIN_SAFE_PING
from app.models.property import PriceInfo, PropertySpec, PropertyType
from app.services.decision_engine import (
    TerminalDecision,
    diagnose_property_decision,
)


FATAL_RED_FLAGS: list[tuple[str, str]] = [
    ("🌾 位於**農業區、保護區或斷層帶**", "ch10_flag_zoning"),
    ("📜 土地項目為**空白**（地上權住宅，無土地產權）", "ch10_flag_no_land"),
    ("🏚️ **921（1999）前的房子** 或 **40 年以上老公寓 4 / 5 樓**（健身公寓）",
     "ch10_flag_old_walkup"),
    ("💎 總價**超過央行豪宅線**（雙北 7,000 萬 / 其他六都 6,000 萬 / 其他 4,000 萬）",
     "ch10_flag_mansion"),
]


def _render_input_panel() -> tuple[PropertySpec, PriceInfo, tuple[bool, ...]]:
    st.markdown("### 📋 情報輸入區")
    st.caption("學長心法：『**買房像打仗——情報不齊，再勇也是送死。**』")

    st.markdown("##### 🏠 基本規格")
    property_type_label = st.radio(
        "房屋類型", options=["🏗️ 預售屋", "🏘️ 中古屋"],
        horizontal=True, index=1, key="ch10_property_type",
    )
    property_type = (
        PropertyType.RESALE if property_type_label.startswith("🏘️")
        else PropertyType.PRESALE
    )

    col_a, col_b = st.columns(2)
    with col_a:
        total_ping = st.number_input(
            "房屋總坪數（坪）", min_value=0.0, value=25.0, step=0.5, format="%.1f",
            help=f"**< {MIN_SAFE_PING:.0f} 坪銀行幾乎不貸款**——學長硬性紅線。",
            key="ch10_total_ping",
        )
    with col_b:
        units_per_floor = st.number_input(
            "單層戶數", min_value=1, max_value=30, value=4, step=1, key="ch10_units",
        )

    elevator_count = st.number_input(
        "電梯數量（含貨梯）", min_value=1, max_value=10, value=2, step=1,
        help="梯戶比 = 戶數 / 電梯數，**> 4 為紅線**。", key="ch10_elevators",
    )

    st.markdown("---")
    st.markdown("##### 💰 價格情報（萬元）")
    col_c, col_d = st.columns(2)
    with col_c:
        bank_appraisal = st.number_input(
            "🏦 預估銀行鑑價（萬）", min_value=0.0, value=2_000.0, step=10.0,
            format="%.1f", help="跑一次房貸試算 / 詢問熟識的代書估鑑價。",
            key="ch10_bank_appraisal",
        )
    with col_d:
        your_offer = st.number_input(
            "🎯 你的目標出價（萬）", min_value=0.0, value=1_800.0, step=10.0,
            format="%.1f", key="ch10_your_offer",
        )

    seller_bottom_line = 0.0
    if property_type == PropertyType.RESALE:
        seller_bottom_line = st.number_input(
            "🧑 屋主『**買入本金 + 剩餘貸款**』（萬，僅中古屋）",
            min_value=0.0, value=1_700.0, step=10.0, format="%.1f",
            help="逆推屋主停損點：原始買入價 + 殘留房貸——你的出價**不得低於此線**，"
            "否則屋主要倒貼銀行才能脫手，**保證談判破局**。",
            key="ch10_seller_bottom",
        )

    st.markdown("---")
    st.markdown("##### ☠️ 致命死穴勾選（Red Flags）")
    flag_results = tuple(st.checkbox(label, key=key) for label, key in FATAL_RED_FLAGS)

    spec = PropertySpec(
        property_type=property_type,
        total_ping=float(total_ping),
        units_per_floor=int(units_per_floor),
        elevator_count=int(elevator_count),
    )
    price = PriceInfo(
        bank_appraisal_wan=float(bank_appraisal),
        your_offer_wan=float(your_offer),
        seller_bottom_line_wan=float(seller_bottom_line),
    )
    return spec, price, flag_results


def _render_radar_panel(
    spec: PropertySpec, price: PriceInfo, red_flags: tuple[bool, ...],
) -> None:
    st.markdown("### 🎯 AI 決策雷達與學長判定")
    st.caption("學長心法：『**買房不是看『心動』，是看『冷數據』。**』")

    verdict = diagnose_property_decision(spec, price, red_flags)

    st.markdown("##### 💵 財務空間診斷")
    m1, m2, m3 = st.columns(3)
    m1.metric("銀行鑑價", f"{price.bank_appraisal_wan:,.0f} 萬")
    m2.metric("你的出價", f"{price.your_offer_wan:,.0f} 萬")
    m3.metric(
        "出價 − 鑑價", f"{verdict.price_gap_wan:+,.0f} 萬",
        delta=(
            f"{(verdict.price_gap_wan / price.bank_appraisal_wan * 100):+.1f}%"
            if price.bank_appraisal_wan > 0 else None
        ),
        delta_color="inverse",
    )

    if verdict.price_gap_wan > 0:
        st.error(
            f"🔴 **出價過高！** 差額 **{verdict.price_gap_wan:,.0f} 萬**需**全額自備現金**——"
            "銀行只會貸鑑價金額的 7-8 成，**剩下你自己掏腰包**。"
        )
    elif verdict.is_below_appraisal:
        st.success(
            f"🟢 **恭喜！買得比銀行鑑價便宜 {-verdict.price_gap_wan:,.0f} 萬**——"
            f"交屋後有約 **{verdict.excess_loan_room_wan:,.0f} 萬**超額增貸空間"
            f"（請參考 Ch.4 科目四操作）。"
        )
    else:
        st.info("⚪ 出價剛好等於銀行鑑價——**安全但無套利空間**。")

    st.markdown("---")
    st.markdown("##### ⚖️ 學長終極判定")

    # 1) 一刀斃命：KILL_SHOT
    if verdict.terminal == TerminalDecision.KILL_SHOT:
        triggered: list[str] = []
        for i in verdict.triggered_red_flag_indices:
            triggered.append(FATAL_RED_FLAGS[i][0].split("（")[0])
        if verdict.is_too_small:
            triggered.append(
                f"📐 坪數 {spec.total_ping:.1f} 坪 < {MIN_SAFE_PING:.0f} 坪（**銀行不貸款**）"
            )
        st.error(
            "🚫 **一刀斃命區！絕對放棄！**\n\n"
            "踩到以下死穴：\n"
            + "\n".join(f"- ❌ {t}" for t in triggered)
            + "\n\n---\n\n"
            "這間房子**銀行極難放貸**（或鑑價直接砍對折），\n"
            "**未來毫無流動性**——你買進去就是接最後一棒。\n\n"
            "👉 **學長動作：立刻關掉這個案件，去找下一間！**"
        )
        return

    # 2) 談判卡關：talks_broken warning
    if verdict.is_below_seller_bottom:
        shortage = price.seller_bottom_line_wan - price.your_offer_wan
        st.warning(
            f"⚠️ **談判卡關區！** 你的出價 **{price.your_offer_wan:,.0f} 萬** 低於"
            f"屋主底線 **{price.seller_bottom_line_wan:,.0f} 萬**——差 **{shortage:,.0f} 萬**。\n\n"
            "屋主賣你**還要倒貼銀行現金**，談判保證破局。\n\n"
            "👉 **學長建議：**\n"
            "1. 重新逆推屋主剩餘貸款本金（用買入年份 + 攤還公式）\n"
            "2. 出價底線 = **屋主本金 + 剩餘貸款 + 5%**（給屋主一點面子）\n"
            "3. 真的覺得屋主開太貴 → **換物件**，硬談只會浪費時間"
        )

    # 3) 硬體扣分：elevator warning
    if verdict.is_elevator_bad:
        st.warning(
            f"⚠️ **硬體扣分區！** 梯戶比 = **{verdict.elevator_ratio:.2f}** > {ELEVATOR_RATIO_DANGER}。\n\n"
            "租客上下班尖峰**等電梯會等到崩潰**：\n"
            "- 租金天花板被砍 **5-15%**\n"
            "- 二手轉手難度大幅提升\n\n"
            "👉 **學長建議**：除非價格極具吸引力（市價 8 折以下），否則**換物件**。"
        )

    # 4) 綠燈 vs 觀察區
    if verdict.terminal == TerminalDecision.GREEN_LIGHT:
        st.success(
            "✅ **綠燈進攻區！這就是『阿嬤照著買都會賺錢』的蘋果案！**\n\n"
            "📊 **檢核全數通過：**\n"
            f"- ✔️ 坪數 {spec.total_ping:.1f} 坪 ≥ {MIN_SAFE_PING:.0f} 坪（銀行愛貸）\n"
            f"- ✔️ 梯戶比 {verdict.elevator_ratio:.2f} ≤ {ELEVATOR_RATIO_DANGER}（動線健康）\n"
            f"- ✔️ 出價 {price.your_offer_wan:,.0f} 萬 < 鑑價 "
            f"{price.bank_appraisal_wan:,.0f} 萬"
            f"（套利空間 {-verdict.price_gap_wan:,.0f} 萬）\n"
            "- ✔️ 四大致命死穴**全數避開**\n"
            + ("- ✔️ 出價 ≥ 屋主底線（談判可成）\n" if spec.property_type == PropertyType.RESALE else "")
            + "\n---\n\n"
            "👉 **學長下一步動作：**\n"
            "1. **立刻帶 1000cc 寶特瓶**準備驗屋（測排水）\n"
            "2. 帶**強光手電筒、水平尺、小夜燈、衛生紙**（學長五神器）\n"
            "3. 啟動『**包廂議價 SOP**』——定錨單價、黑白臉雙簧、收尾擋箭牌\n"
            "4. 同時去 Ch.4 試算交屋後**超額增貸空間**\n\n"
            "**這種物件 3 個月才會出現一次——別猶豫，動手吧！**"
        )
        # ----- Cross-chapter 跳轉：綠燈進攻區的最佳下一步 -----
        from app.ui.components.navigation import chapter_jump_button as _jump
        from app.ui.router import (
            CHAPTER_KEY_CH4,
            CHAPTER_KEY_CH11,
            CHAPTER_KEY_STRATEGY_NEGOTIATION,
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            _jump("⚔️ 驗屋 SOP →", CHAPTER_KEY_CH11,
                  button_key="ch10_jump_combat", use_container_width=True)
        with col_b:
            _jump("💼 議價戰術 →", CHAPTER_KEY_STRATEGY_NEGOTIATION,
                  button_key="ch10_jump_negotiation", use_container_width=True)
        with col_c:
            _jump("🏦 算增貸空間 →", CHAPTER_KEY_CH4,
                  button_key="ch10_jump_refinance", use_container_width=True)
    else:  # OBSERVATION
        st.info(
            "🟡 **觀察區**：沒有一刀斃命的問題，但**存在扣分項**。\n\n"
            "若上述警告都能透過議價或條件補強解決，可以繼續評估；"
            "否則**寧可放棄這間，去找完美的下一間**。"
        )


def render_chapter_10_decision_engine() -> None:
    """🧭 400 題極限防坑與決策雷達（Chapter 10）— UI 入口。"""
    st.title("🧭 400 題極限防坑與決策雷達")
    st.info(
        "💡 **學長的實戰金句**：「**決策不要靠感覺，要靠冷冰冰的雷達**。\n"
        "情報全收齊、雷達跑完一輪，學長告訴你『**買還是不買**』——\n"
        "**這是 400 個案例淬煉出來的判斷力，幫你濃縮成 5 秒鐘。**」"
    )

    col_left, col_right = st.columns([1, 1.2], gap="large")
    with col_left:
        spec, price, red_flags = _render_input_panel()
    with col_right:
        _render_radar_panel(spec, price, red_flags)
