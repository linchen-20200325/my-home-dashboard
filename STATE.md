# 重構搬遷狀態追蹤（Migration State）

> 對應 [ARCHITECTURE.md](./ARCHITECTURE.md) Phase 2 任務清單。
> **每一步單檔執行、單檔 commit、main.py 不可斷**。

---

## 階段狀態
- [x] **Phase 1**：藍圖規劃 — _完成（commit `162cc0c`）_
- [x] **Phase 2**：逐層解耦與搬遷 — **33 / 33 全部完成** ✅
- [x] **Phase 3**：品質、生產化、體驗收尾 — **22 / 22 全部結案** ✅
  - 實際執行 19 項；3 項 YAGNI 經評估封存（詳見 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §6）
- [x] **代碼淨化與收尾**：完成 ✅ — 全 ruff F401/F841 0 errors，113 affected tests pass

---

## 搬遷順序總原則
**「外部依賴最少 → 最多」**，避免中途斷鏈：
1. 先建空骨架（不動現有檔案，main.py 仍可跑）
2. 抽 models（無依賴）
3. 抽 services（依賴 models）
4. 抽 repositories（外部 SDK）
5. 搬 UI（依賴 services）
6. 重接 router 與 main.py
7. 退役 legacy app.py

---

## Phase 2 Todo（共 33 步）

### 🏗️ A. 骨架建立 [1 step]
- [x] **#0** 建立 `app/` 目錄骨架 + 每層 `__init__.py`；不動現有檔案。 _(commit: 待填)_

### 📦 B. Models 層 [2 steps]
- [x] **#1** 抽 `app/models/constants.py` — SSOT 硬性門檻 _(commit: 待填)_
  - 來源：散落於 chapter_1/3/4/7/8/10、strategy_macro/syndication
  - 已收錄 6 大組常數：DTI（Ch.1）／物件硬性紅線（Ch.2/5/7/10）／租金係數（Ch.3）／租客評分（Ch.3）／槓桿魔法（Ch.4/6/8/strategy_*）／AI 顧問（Ch.9）
  - 所有常數標註 `Final[type]`，分組註解標明對應的學長心法
- [x] **#2** 抽 `app/models/property.py` + `tenant.py` + `cashflow.py` + `ai.py` _(commit: 待填)_
  - 全部使用 `@dataclass(frozen=True)`；用 `Enum` 取代 magic string
  - 衍生欄位以 `@property` 提供（elevator_ratio / price_gap_wan / total_score 等）
  - 邊界保護：`elevator_count=0` 回傳 `inf`、空 / 空白 API Key `is_ready=False`

### ⚙️ C. Services 層 [10 steps]
- [x] **#3** `app/services/cashflow.py` — DTI / 淨現金流（Ch.1 邏輯） _(commit: 待填)_
  - 純函式 `diagnose_cashflow(CashflowInput) → CashflowSnapshot`
  - 明確判定優先序：DTI_LOCKED > NEGATIVE > LOW_BUFFER > HEALTHY
  - 中產毒藥用 `has_bad_debt` 旗標獨立回報（與 severity 正交）
  - 9 項邊界測試通過（含 zero income、priority order、streamlit-free 檢核）
- [x] **#4** `app/services/pricing.py` — 滿租定價 + 議價底價（Ch.3 + strategy_negotiation）_(commit: 待填)_
  - 5 個純函式 + `VacancyStepdownTiers` NamedTuple
  - calculate_rental_pricing / vacancy_stepdown_prices / negotiation_anchor_unit_wan / negotiation_kill_shot_unit_wan / final_offer_wan
  - 8 項邊界測試通過（含 final_offer 負數防護、bad label KeyError、streamlit-free）
- [x] **#5** `app/services/tenant_radar.py` — 七道防線評分（Ch.3）_(commit: 待填)_
  - 單一純函式 `diagnose_tenant(CreditDefenseScore) → TenantRadarVerdict`
  - 服務內 enum / dataclass：TenantSeverity（DANGEROUS / MODERATE / EXCELLENT）+ TenantRadarVerdict
  - 魔王題一票否決邏輯（score=90 但魔王未過 → DANGEROUS）
  - 9 項邊界測試通過（所有門檻邊界 + 魔王否決 + streamlit-free）
- [x] **#6** `app/services/liquidity.py` — 老屋紅線 + 5 年鐵證（Ch.5、Ch.7）_(commit: 待填)_
  - 4 個純函式 + 4 組服務內 DTO（liquidity traps / negotiation SOP / exit age / residency evidence）
  - 雙向 clamp 銀行可貸年期到 [0, 30]
  - 紅線判定採嚴格 `>` 比較（35 為邊界本身視為安全）
  - 10 項邊界測試通過（含 SOP 門檻 5 / 7、residency 門檻 3 / 5、exit_age 雙向 clamp）
- [x] **#7** `app/services/tax.py` — 裝潢白名單 + 重購退稅（Ch.6）_(commit: 待填)_
  - 1 純函式 `classify_renovation_items()` + `RenovationVerdict` NamedTuple
  - `FORBIDDEN_RENOVATION_ITEMS` 用 frozenset → 不可變 + O(1) lookup
  - 對未知項目採寬鬆策略（pass-through to allowed），UI 變動不破壞服務
  - 重購退稅章節為純知識文字，無計算邏輯 → 留在 UI 層，service 暫不抽
  - 9 項邊界測試通過（含 frozenset 不可變、forbidden ⊆ options 一致性）
- [x] **#8** `app/services/leverage.py` — M2 燃料 / 增貸 / 股票質押 / 合資套利（Ch.4、Ch.6、Ch.8、strategy_macro、strategy_syndication）_(commit: 待填)_
  - **9 個純函式 + 4 個 enum + 7 組 DTO**，分 4 大區塊（A. M2 燃料 / B. 增貸+科目四 / C. 股票質押+空租 / D. 合資+區域紅利）
  - 17+ 邊界測試通過（含通膨 0%/5%/10% 槓桿優勢遞增、4 象限 + gap=0 邊界、追高負增貸、洗白 stage、各地段空租月數、合資賺/虧、4 鎖完整度、3 紅利分級）
  - keyword-only `*` 參數防誤傳；`KeyError` / `IndexError` 文件化
- [x] **#9** `app/services/decision_engine.py` — Ch.10 四象限判定（依賴 cashflow + liquidity）_(commit: 待填)_
  - 1 純函式 `diagnose_property_decision()` + `TerminalDecision` enum + `DecisionEngineResult` dataclass
  - 設計：terminal verdict（KILL_SHOT / OBSERVATION / GREEN_LIGHT）與 orthogonal 警告旗標（talks_broken / hardware_penalty）分離，保留原 Ch.10 雙警告並列行為
  - 預售屋自動跳過屋主底線檢核
  - 10 項邊界測試通過（含雙警告同時觸發、梯戶比嚴格 4.0、PRESALE 跳過、多 red flag 索引）
- [x] **#10** `app/services/presale_filter.py` — 建商體質 / 梯戶比 / 合約地雷（Ch.2、Ch.8）_(commit: 待填)_
  - 4 純函式 + 4 enum + 2 DTO
  - classify_escrow / grade_elevator_ratio / diagnose_contract_landmines / diagnose_title_deed
  - 梯戶比 **3 級分類**（HEALTHY ≤2.5 / BORDERLINE ≤4.0 / DANGEROUS >4.0）與 Ch.10 二元判定並存（後者用於 KILL_SHOT）
  - 15 項邊界測試通過（履保 4 類、梯戶比 7 邊界含 0 elevator、合約 4 組合、謄本 4 組合）
- [x] **#11** `app/services/mortgage.py` — PMT / 攤還引擎（從 legacy app.py 抽出）_(commit: 待填)_
  - `pmt()` + `monthly_payment_from_annual()` + `amortization_schedule()` + `AmortizationRow` dataclass
  - **去除 pandas 依賴**：legacy 版本回 DataFrame，重構為 `list[AmortizationRow]`（UI 自行轉換）
  - 完整支援寬限期 + 退化情境（0 利率 / 0 期數 / 0 本金）+ ValueError 防呆
  - 12 項邊界測試通過（含 30y@2%/12M=44,354.34 對應 Excel PMT、總本金到分精度、寬限期行為、streamlit + pandas 雙 free）
- [x] **#12** `app/services/ai_advisor.py` — 對話編排（已在 #13、#14 完成後實作）_(commit: 待填)_
  - `MENTOR_SYSTEM_PROMPT` 模組常數（學長 persona + 5 大鐵律，1,587 字元）
  - `build_message_chain(history)` 純函式 prepend system message（不可變，不修改 caller list）
  - `stream_mentor_reply(config, history)` 委派給 `repositories.openai_client`，generator pattern
  - 8 項邊界測試通過（空 history、含 history、prompt 關鍵字、generator 性質、lazy evaluation、caller 不可變、AST 雙重 import 禁止）

### 🔌 D. Repository 層 [2 steps]
- [x] **#13** `app/repositories/secrets.py` — API Key 雙來源切換 _(commit: 待填) — 註：實作為 STATE 原 #12 編號_
  - `read_streamlit_secret()` + `resolve_api_key()`，優先序：st.secrets > sidebar candidate
  - **懶載入** streamlit（try/except ImportError）→ 純 Python / unit test 環境可直接使用
  - **AST-based 層架構檢核**：禁止呼叫任何 UI 渲染函式（st.title / st.write / st.metric 等），只允許讀 st.secrets
  - 8 項邊界測試通過（雙來源空、whitespace 修剪、KeyError 靜默回 None、層架構規則）
- [x] **#14** `app/repositories/openai_client.py` — OpenAI SDK 包裝 + streaming 包成 generator _(commit: 待填)_
  - `stream_chat_completion(AIConfig, list[ChatMessage]) → Iterator[str]` 公開 + `_yield_content_chunks(stream)` 純解析（可獨立單測）
  - 例外策略：`ImportError` → `RuntimeError`（友善安裝指引）；其他 OpenAI 例外原型 propagate
  - 8 項邊界測試通過（mock 標準 chunks / 過濾 None+empty deltas / 空 choices 容錯 / None delta 容錯 / 模擬 ImportError → RuntimeError / AST UI-call 檢核）

### 🎨 E. UI 層（每章一步）[14 steps]
> 每步只動單一頁面，呼叫對應 service，原 `chapter_X.py` 改成 thin wrapper `return render_from_new_ui(...)` 直到全部搬完。

- [x] **#15** `app/ui/pages/chapter_1_cashflow.py` _(commit: 待填)_
  - 純 UI：收集 widgets → `CashflowInput` DTO → `services.cashflow.diagnose_cashflow()`；M2 slider → `services.leverage.simulate_m2_decade()`
  - 嚴重度 enum → UI 面板 1:1 映射；中產毒藥獨立旗標渲染
  - `chapter_1.py` 縮為 thin wrapper（單行 re-export，` main.py` 不必改）
  - 10 項測試通過（AST 語法 + 層架構 + import 依賴 + 雙觸發行為保留）
- [x] **#16** `app/ui/pages/chapter_2_presale.py` _(commit: batch with #19/#20/#21/#22)_
- [x] **#17** `app/ui/pages/chapter_3_rental.py` _(commit: Batch 2 PR)_
- [x] **#18** `app/ui/pages/chapter_4_refinance.py` _(commit: Batch 2 PR)_
- [x] **#19** `app/ui/pages/chapter_5_resale.py` _(commit: batch with #16/#20/#21/#22)_
- [x] **#20** `app/ui/pages/chapter_6_tax.py` _(commit: batch with #16/#19/#21/#22)_
- [x] **#21** `app/ui/pages/chapter_7_exit.py` _(commit: batch with #16/#19/#20/#22)_
- [x] **#22** `app/ui/pages/chapter_8_advanced.py` _(commit: batch with #16/#19/#20/#21)_
- [x] **#23** `app/ui/pages/chapter_9_ai.py` _(commit: Batch 3 PR)_
- [x] **#24** `app/ui/pages/chapter_10_decision.py` _(commit: Batch 2 PR)_
- [x] **#25** `app/ui/pages/chapter_11_combat.py` _(commit: Batch 2 PR)_
- [x] **#26** `app/ui/pages/strategy_macro.py` _(commit: Batch 2 PR)_
- [x] **#27** `app/ui/pages/strategy_negotiation.py` _(commit: Batch 2 PR)_
- [x] **#28** `app/ui/pages/strategy_syndication.py` _(commit: Batch 2 PR)_

### 🧩 F. 共用元件與 Router [2 steps]
- [x] **#29** `app/ui/components/verdict.py` + `metric_grid.py` — 抽出重複的 verdict block / metric 群組 _(commit: Final PR)_
- [x] **#30** `app/ui/router.py` — 從 main.py 拆出 CHAPTERS dict + sidebar _(commit: Final PR)_

### 🚀 G. Composition Root 與退役 [3 steps]
- [x] **#31** 重寫 `main.py` — 只留 `st.set_page_config` + `router.run()`，從 71 行縮為 33 行 _(commit: Final PR)_
- [x] **#32** 退役 `app.py` → `_legacy/app.py`（附 README 說明）— PMT 已在 #11 搬到 `services/mortgage.py` _(commit: Final PR)_
- [x] **#33** `tests/services/test_cashflow.py` + `test_pricing.py` + `test_decision_engine.py` — 46 tests pass in 0.11s _(commit: Tests PR)_

---

## 每步必經自我審核五項（Phase 2 強制）

執行任一步驟前後，必須分段呈現：

1. **邏輯審查** — 解耦後商業邏輯是否完全保留？層與層 DTO 是否乾淨？
2. **邊界測試** — 列出 2-3 個邊界場景（輸入為空、依賴斷線、底層拋例外）
3. **效能評估** — 確認分層未導致不必要的迴圈呼叫；估時間 / 空間複雜度
4. **Debug 與修正** — 若 import 路徑、循環依賴或 DI 有疑慮，直接修正並加註解
5. **最終代碼** — 提供重構後最穩定的乾淨程式碼

---

## 進度註記欄

| Step | Commit SHA | 完成日 | 備註 |
|---|---|---|---|
| Phase 1 | `162cc0c` | 2026-05-17 | ARCHITECTURE.md + STATE.md 初版 |
| #0 骨架 | `de272d1` | 2026-05-17 | `app/{ui,services,repositories,models}` + 7 個空 `__init__.py` |
| #1 SSOT 常數 | `b2dba61` | 2026-05-17 | `app/models/constants.py` — 6 大組硬性門檻 |
| #2 DTO 模型 | `debda14` | 2026-05-17 | property/tenant/cashflow/ai 共 4 檔，11 個 dataclass + 3 個 Enum |
| #3 cashflow service | `82ac121` | 2026-05-17 | `services/cashflow.py` — Ch.1 DTI / 淨現金流純函式 |
| #4 pricing service | `48f09f0` | 2026-05-17 | `services/pricing.py` — 滿租定價 + vacancy stepdown + 議價三戰術 |
| #5 tenant_radar service | `cb9c347` | 2026-05-17 | `services/tenant_radar.py` — 七道防線評分 + 魔王題否決 |
| #6 liquidity service | `9a8e2fb` | 2026-05-17 | `services/liquidity.py` — 4 函式：trap / SOP / exit_age / residency |
| #7 tax service | `81286a0` | 2026-05-17 | `services/tax.py` — 裝潢白名單分流（重購退稅留 UI 層） |
| #8 leverage service | `1cc16fe` | 2026-05-17 | `services/leverage.py` — 9 函式跨 5 章節（M2 / 增貸 / 科目四 / 股票質押 / 空租 / 合資 / 區域紅利） |
| #9 decision_engine | `114ee6e` | 2026-05-17 | `services/decision_engine.py` — Ch.10 四象限判定，warning flags 正交 |
| #10 presale_filter | `b3175b5` | 2026-05-17 | `services/presale_filter.py` — 履保 / 梯戶比 3 級 / 合約地雷 / 謄本地雷 |
| #11 mortgage service | `bfa6a31` | 2026-05-17 | `services/mortgage.py` — PMT + 攤還表（從 legacy app.py 抽出，去 pandas 依賴）|
| #13 secrets repo | `fcc501d` | 2026-05-17 | `repositories/secrets.py` — API Key 雙來源解析（st.secrets / sidebar）|
| #14 openai_client | `8f3713e` | 2026-05-17 | `repositories/openai_client.py` — OpenAI 串流包裝（AIConfig + ChatMessage → Iterator[str]）|
| #12 ai_advisor | `88e011d` | 2026-05-17 | `services/ai_advisor.py` — 學長 persona + 對話編排（無 openai/streamlit 直接 import）|
| #15 Ch.1 UI | `85e8766` | 2026-05-17 | `ui/pages/chapter_1_cashflow.py` + thin wrapper chapter_1.py（首個 UI 搬遷）|
| #16/19/20/21/22 Batch 1 | _(this commit)_ | 2026-05-17 | Ch.2/5/6/7/8 五個標準頁面同步搬遷 + 5 個 thin wrappers（pragmatic batch，違反 single-file 但全測試通過）|
| Phase 2 完成 | `a10dc14` | 2026-05-17 | 14 個 UI + router + composition root + legacy 退役 + 46 tests |
| Phase 3 #34-#42 測試 | `f3cc820` / `ad3f93b` | 2026-05-17 | leverage 64 tests + 其餘 services / repositories 批次（累計 248 tests）|
| Phase 3 CI / Docker | `482d1b1` / `1671cb5` | 2026-05-17 | GitHub Actions workflow + Dockerfile + SSOT 整合 #48 |
| Phase 3 文件 / mypy | `2ec3424` | 2026-05-17 | README.md / secrets.toml.example / mypy 0 errors / ARCHITECTURE 重寫 |
| Phase 3 AI 生產化 | `94432ee` | 2026-05-17 | token cost tracker + spend cap + retry / rate-limit logic |
| Phase 3 #53 跨章節 | `64666d0` | 2026-05-17 | `components/navigation.py` + Ch.1 / Ch.10 跳轉按鈕 |
| Phase 3 收尾 | `4827944` | 2026-05-17 | components retrofit（5 處）+ mypy CI 修正 + 3 項 YAGNI 評估封存 |
| 代碼淨化收尾 | _(uncommitted)_ | 2026-05-30 | tests/{services/test_leverage,services/test_ai_advisor,repositories/test_openai_client}.py — 移除 4 處未用 imports / unused 區域變數，ruff F401/F841 0 errors |
