# 房產攻略 — 分層架構（Layered Architecture）

> **Phase 1 規劃 + Phase 2 完成現況**。本文件同時作為**歷史藍圖**與**現役架構參考**。

---

## 🚦 整體狀態（2026-05-17 截止）

| Phase | 內容 | 狀態 | 對應 PR |
|---|---|---|---|
| **Phase 1** | 藍圖規劃（本文件原版）| ✅ 完成 | commit `162cc0c` |
| **Phase 2** | 33 步搬遷（藍圖 → 實作）| ✅ **33 / 33** | PR #9, #10, #11, #12, #13 |
| **Phase 3** | 部署 / 測試 / 工具收尾 | 🚧 **14 / 22**（持續中）| PR #14-#19, …|

### Phase 2 成就

- 4 個 layer 全建立：`app/{models,services,repositories,ui}`
- 10 個 pure-function services（cashflow / pricing / tenant_radar / liquidity / tax / leverage / decision_engine / presale_filter / mortgage / ai_advisor）
- 2 個 repositories（secrets / openai_client）
- 14 個 UI pages 從根目錄 chapter/strategy 檔案搬遷到 `app/ui/pages/`
- 33 行 composition root（`main.py`）— 從 71 行縮減
- 223 pytest tests pass in 0.21s — 含 1 個 service / repository 都有覆蓋
- GitHub Actions CI + AST sanity + mypy 整合
- Legacy `app.py`（1,918 行）退役到 `_legacy/`

---

## 1. 重構動機（Why refactor）— 歷史紀錄

**重構前（Phase 1 起點）：**

```
my-house-2026/
├── main.py                       # 路由 + sidebar
├── chapter_1.py … chapter_11.py  # UI + 公式 + 常數 + (Ch.9 還含 OpenAI 呼叫)
├── strategy_macro.py             # 同上
├── strategy_negotiation.py       # 同上
├── strategy_syndication.py       # 同上
├── app.py                        # 1,918 行 legacy：PMT / 攤還 / 試算（未掛載）
└── requirements.txt
```

每個 `chapter_*.py` 同時做了：
1. **UI 渲染**（`st.title`, `st.metric`, `st.checkbox` …）
2. **商業邏輯**（DTI 計算、租金係數、判定門檻）
3. **常數定義**（學長硬性門檻散落 14 個檔案）
4. **資料存取**（`chapter_9.py` 直接 import openai SDK + 讀 secrets）

**痛點**：改 UI 必須讀公式、改公式必須讀 UI；公式重複定義（DTI 紅線 0.70 寫了兩三次）；OpenAI 呼叫無法被測試；無法接 unit test。

---

## 2. 最終分層結構（已實現）

```
my-house-2026/
├── main.py / app.py / streamlit_app.py    ← 三個等價入口（composition root）
├── chapter_*.py / strategy_*.py           ← 14 個 thin re-export wrappers
├── app/                                   ← 真正的四層架構
│   ├── ui/
│   │   ├── pages/                         ← 14 個純 Streamlit 頁面
│   │   ├── components/                    ← verdict + metric_grid
│   │   └── router.py                      ← CHAPTERS dict + sidebar + run()
│   ├── services/                          ← 10 個 pure-function 模組
│   ├── repositories/                      ← secrets + openai_client
│   └── models/                            ← 4 DTO + constants.py SSOT
├── tests/                                 ← 223 pytest tests
│   ├── services/                          ← 10 test modules
│   └── repositories/                      ← 2 test modules
├── _legacy/
│   ├── app.py                             ← 1,918 行原版（退役）
│   └── README.md
├── .streamlit/secrets.toml.example
├── .github/workflows/test.yml             ← CI（pytest + mypy + AST）
├── pyproject.toml                         ← mypy config
├── pytest.ini                             ← pytest config
├── requirements.txt / requirements-dev.txt
├── README.md
├── ARCHITECTURE.md                        ← 本檔
└── STATE.md                               ← Phase 2 33-step Todo (all done)
```

---

## 3. 各層嚴格職責（Strict Responsibilities）

### 3.1 UI Layer (`app/ui/`)

| 允許 | 嚴禁 |
|---|---|
| ✅ Streamlit 元件（title/metric/checkbox/error） | ❌ 寫公式（DTI、套利、增貸） |
| ✅ 收集使用者輸入 → 包成 DTO | ❌ 直接呼叫 OpenAI |
| ✅ 接收 Service 回傳 DTO → 渲染 | ❌ 直接讀 secrets |
| ✅ 版型編排（columns / tabs / expander） | ❌ 跨頁 import 別頁 widget |

**唯一例外**：`chapter_9_ai.py` 是唯一觸碰 `app.repositories.secrets` 的 UI 檔案，因為它需要對 API key 缺失做 UI 提示（這是合理的 UI 行為）。OpenAI SDK 呼叫仍經由 `services.ai_advisor` 中介。

### 3.2 Service Layer (`app/services/`)

| 允許 | 嚴禁 |
|---|---|
| ✅ 純 Python 函式 / pure functions | ❌ `import streamlit` |
| ✅ 輸入 DTO → 輸出 DTO | ❌ 印任何 UI 元素 |
| ✅ 商業判定（學長心法、公式） | ❌ 直接呼叫 OpenAI SDK |
| ✅ 呼叫 repositories 取資料 | ❌ 跨 service 反向依賴 |

**Phase 2 達成**：mypy 確認 0 errors 跨 41 個 source files；所有 services 通過 AST 掃描，零 streamlit / openai 直接 import。

### 3.3 Repository Layer (`app/repositories/`)

| 允許 | 嚴禁 |
|---|---|
| ✅ 包裝外部 SDK（openai、未來 DB） | ❌ 寫商業邏輯（如要重試幾次） |
| ✅ Raw response → model DTO 轉換 | ❌ 印任何 UI 元素 |
| ✅ 處理連線錯誤、retry、timeout | ❌ 知道誰要呼叫它 |

**唯一例外**：`secrets.py` lazy-imports streamlit（因為 `st.secrets` 是 Streamlit 提供的外部設定存取入口），但**只讀 `st.secrets`，禁止呼叫任何 UI 渲染函式**。AST scan + 8 個 pytest 確保此邊界。

### 3.4 Models Layer (`app/models/`)

| 允許 | 嚴禁 |
|---|---|
| ✅ `@dataclass(frozen=True)` 定義型別 | ❌ import 其他層 |
| ✅ 模組常數（門檻 SSOT） | ❌ 任何 I/O |
| ✅ Enum / typed alias | ❌ 商業邏輯 |

### 3.5 依賴方向（單向，不可逆）

```
   UI ────► Service ────► Repository
    │         │              │
    └────► Models ◄──────────┘
```

- UI **永遠不可直接** import repositories（**例外**：chapter_9_ai 的 secrets 讀取）
- Models 不依賴任何層
- 違反方向 → import 時會 circular，AST sanity + mypy 雙重把關

---

## 4. 搬遷地圖 — 實際成果（已完成）

| 原檔（重構前）| → | 拆分結果 |
|---|---|---|
| `main.py` (71 行) | → | `main.py` (33 行 composition root) + `app/ui/router.py` (CHAPTERS + sidebar) |
| `chapter_1.py` | → | `app/ui/pages/chapter_1_cashflow.py` + `services/cashflow.py` + `services/leverage.py` (M2) + `models/cashflow.py` |
| `chapter_2.py` | → | `app/ui/pages/chapter_2_presale.py` + `services/presale_filter.py` |
| `chapter_3.py` | → | `app/ui/pages/chapter_3_rental.py` + `services/pricing.py` + `services/tenant_radar.py` + `models/tenant.py` |
| `chapter_4.py` | → | `app/ui/pages/chapter_4_refinance.py` + `services/leverage.py` (增貸 + 科目四) |
| `chapter_5.py` | → | `app/ui/pages/chapter_5_resale.py` + `services/liquidity.py` (地雷 + SOP) |
| `chapter_6.py` | → | `app/ui/pages/chapter_6_tax.py` + `services/tax.py` + `services/leverage.py` (股票質押) |
| `chapter_7.py` | → | `app/ui/pages/chapter_7_exit.py` + `services/liquidity.py` (脫手 + 鐵證) |
| `chapter_8.py` | → | `app/ui/pages/chapter_8_advanced.py` + `services/presale_filter.py` + `services/leverage.py` (空租) |
| `chapter_9.py` | → | `app/ui/pages/chapter_9_ai.py` + `services/ai_advisor.py` + `repositories/openai_client.py` + `repositories/secrets.py` + `models/ai.py` |
| `chapter_10.py` | → | `app/ui/pages/chapter_10_decision.py` + `services/decision_engine.py` |
| `chapter_11.py` | → | `app/ui/pages/chapter_11_combat.py` (UI-only，無公式可抽) |
| `strategy_macro.py` | → | `app/ui/pages/strategy_macro.py` + `services/leverage.py` (M2 黃金交叉) |
| `strategy_negotiation.py` | → | `app/ui/pages/strategy_negotiation.py` + `services/pricing.py` (議價戰術) |
| `strategy_syndication.py` | → | `app/ui/pages/strategy_syndication.py` + `services/leverage.py` (合資套利 + 防護鎖) |
| `app.py` (legacy 1,918 行) | → | `_legacy/app.py` (退役) + `services/mortgage.py` (PMT / 攤還抽出) |

**14 個 chapter / strategy 原檔縮成 ~20 行 thin re-export wrappers**，保留向後相容。

---

## 5. 為什麼這樣切？

1. **Token 控管** — 改 UI 時不必再讀公式檔；改公式時不必再讀 UI 樣板。Claude / Codex 只讀「相關層」即可。
2. **可測性** — services 是 pure functions，pytest 不啟動 Streamlit、不打 OpenAI 也能跑（223 tests in 0.21s）。
3. **AI 安全性** — OpenAI 呼叫集中在 `repositories/openai_client.py`，未來要加 rate limit / token budget / retry / spend cap 改一處即可。
4. **未來擴展** — 若從 Streamlit 改 FastAPI + React，UI 層整層丟掉，services / repositories 完全不動。
5. **SSOT (Single Source of Truth)** — `models/constants.py` 統一硬性門檻（`DTI_DANGER_RATIO=0.70`, `MIN_SAFE_PING=15`, `EXIT_AGE_RED_LINE_YEARS=35`, `ELEVATOR_RATIO_DANGER=4.0`），杜絕硬編碼漂移。

---

## 6. Phase 3 進度（完成）

詳見 [`STATE.md`](./STATE.md) 末段「Phase 3 候選 Backlog」。

### 已執行（19 / 22）

| 類別 | 完成項目 |
|---|---|
| **測試擴充** | #34 leverage + #35-#42 全部剩餘 services / repositories（248 tests）|
| **CI / 部署** | #43 GitHub Actions workflow / #44 README.md / #45 secrets.toml.example / #46 Dockerfile + `.dockerignore` |
| **品質工具** | #47 mypy 靜態型別檢核 / #48 Module-level 常數整合 SSOT / #55 ARCHITECTURE.md 更新 |
| **生產化** | #51 AI token cost tracker / spend cap / #52 AI retry / rate-limit logic |
| **體驗** | #53 Cross-chapter 跳轉（Ch.1 HEALTHY / Ch.10 GREEN_LIGHT → 下一步）|
| **內聚** | #49 Components 部分導入（Ch.1 / 3 / 4 / 7 / 10 的 `render_metric_row` retrofit）|

### 評估後封存（3 項，附原因）

| Item | 結論 | 原因 |
|---|---|---|
| #49 components 全域 retrofit | **部分執行，其餘封存** | 5 個 metric row 已 retrofit；另 ~15 處 alert 的 message 為長 f-string，使用 `render_verdict` 反而會把 dict 撐到比 if/elif 更長，違反「helper 應簡化、不應遮蔽」原則。 |
| #50 Chapter 11 退回純文件 | **評估後維持現狀** | Ch.11 的 checkbox 提供『五神器打包進度 / 四大檢測完成度』即時回饋（progress bar + 條件警告），不是裝飾。改回純 markdown 會喪失現場使用價值。 |
| #54 `_legacy/app.py` UI 復活 | **評估後維持封存** | legacy 唯一獨特功能是 PMT 試算 / 攤還表，已在 #11 抽到 `services/mortgage.py`；其餘 12 個 tab 與重構後 14 章節重複度 > 90%。無新功能可救回。|

> **Phase 3 至此宣告結束** — 重要工作 19 項全部完成，3 項 YAGNI 經評估封存。所有 22 個 backlog item 皆有明確終局。

---

## 附錄：Phase 2 完整 33-step 紀錄

詳見 [`STATE.md`](./STATE.md)。所有步驟皆嚴格遵守「**單檔單步 + 五項自我審核**」協定（邏輯審查 → 邊界測試 → 效能評估 → Debug → 最終代碼），每步皆對應一個 git commit。
