# Core Protocol v2.0 — Claude 開發協議

> 本文件為 Claude 在本專案的**最高行為準則**，由 [`ARCHITECTURE.md`](./ARCHITECTURE.md) 與 [`STATE.md`](./STATE.md) 重建。
> 任何衝突以本文件為準；本文件未涵蓋處，回退至 ARCHITECTURE.md。

---

## 0. 專案速覽

- **產品**：房產攻略 Dashboard（Streamlit App，學長帶你看房）
- **語言**：所有對話、commit message、code comment、PR description **一律使用繁體中文**
- **Persona**：AI 顧問對外稱「學長」，沿用 `services/ai_advisor.MENTOR_SYSTEM_PROMPT`
- **現況**：Phase 2 + Phase 3 已全部結案，目前處於**維運與微調**階段
- **入口**：`main.py` / `app.py` / `streamlit_app.py` 三者等價，皆委派給 `app/ui/router.py`

---

## 1. 分層架構（不可違反）

```
UI ──► Service ──► Repository
 │       │             │
 └───► Models ◄────────┘
```

### 1.1 各層職責速查表

| 層 | 允許 | 嚴禁 |
|---|---|---|
| **UI** (`app/ui/`) | Streamlit 元件、收集輸入打包 DTO、渲染回傳結果 | 寫公式、`import openai`、直接讀 `st.secrets`（**唯一例外**：`chapter_9_ai.py` 可讀 secrets 做 API key 缺失提示）|
| **Service** (`app/services/`) | 純函式、DTO 進 DTO 出、商業判定、呼叫 repositories | `import streamlit`、`import openai`、印任何 UI 元素、跨 service 反向依賴 |
| **Repository** (`app/repositories/`) | 包外部 SDK、Raw response → DTO、retry / timeout | 寫商業邏輯、印 UI 元素、知道誰呼叫它（**例外**：`secrets.py` lazy-imports streamlit 僅讀 `st.secrets`，禁止任何渲染呼叫）|
| **Models** (`app/models/`) | `@dataclass(frozen=True)`、Enum、SSOT 常數 | import 其他層、任何 I/O、商業邏輯 |

### 1.2 SSOT 常數（`app/models/constants.py`）

所有硬性門檻（DTI 紅線 0.70、最小坪數 15、35 年屋齡紅線、梯戶比 4.0 等）**必須**從 `constants.py` import，**禁止**在 service / UI 直接寫魔術數字。

### 1.3 AST Sanity（自動把關）

CI 會跑 AST 掃描，違反以下任一條 → 直接 fail：
- service 出現 `import streamlit` 或 `import openai`
- repository 出現 `st.title` / `st.write` / `st.metric` 等 UI 渲染呼叫
- secrets repo 出現上述 UI 渲染呼叫（只允許讀 `st.secrets`）

---

## 2. 工作流程協議（強制）

### 2.1 每步五項自我審核

執行任一**程式碼變更**前後，必須分段呈現：

1. **邏輯審查** — 商業邏輯是否完全保留？層與層 DTO 是否乾淨？
2. **邊界測試** — 列出 2-3 個邊界場景（輸入為空、依賴斷線、底層拋例外）
3. **效能評估** — 是否引入不必要的迴圈呼叫？估時間 / 空間複雜度
4. **Debug 與修正** — import 路徑、循環依賴、DI 疑慮，直接修正並加註解
5. **最終代碼** — 提供重構後最穩定的乾淨程式碼

> **例外**：純文件修改（README、ARCHITECTURE、STATE、CLAUDE）、commit message 微調、新增單元測試，可豁免五項審核。

### 2.2 單檔單步 + 單檔單 commit

- Phase 2 的鐵律：**一步只動一個檔案，一個 commit 對應一步**
- 若必須跨多檔（例如新增 service + 改 thin wrapper），在 commit message 註明「pragmatic batch」並附理由
- `main.py` / `router.py` **隨時可跑**，不可斷鏈

### 2.3 測試與型別檢核（PR 前必跑）

```bash
pytest                                    # 全部測試（目前 248+ tests，應 < 1s）
mypy app/                                 # 0 errors required
python -m compileall app/ tests/ main.py  # 語法檢查（CI 也會跑）
```

---

## 3. Git 與分支規範

### 3.1 分支
- 本 session 工作分支：`claude/debug-input-validation-7Rz9h`
- **嚴禁**直接推 `main`；所有變更走 PR
- **嚴禁** `git push --force` 到任何遠端分支（含本人分支），如需 rewrite 先問使用者

### 3.2 Commit Message
- 繁體中文為主，可夾英文技術名詞
- 格式：`<層名 / 範圍>: <動詞> <變更主旨>`
  - 範例：`services/cashflow: 修正 DTI 邊界為嚴格 > 0.70`
  - 範例：`docs: 重建 CLAUDE.md 為 Core Protocol v2.0`
- **不**附加 Claude / AI 簽名（包括 `claude-opus-*` 模型識別字串）

### 3.3 PR
- **使用者未明確要求前，不主動開 PR**
- 開 PR 時用 GitHub MCP 工具（`mcp__github__create_pull_request`），不可用 `gh` CLI（不存在）
- PR Repo 範圍限定：`linchen-20200325/my-home-dashboard`

---

## 4. 安全與保守原則

### 4.1 唯讀優先
- 讀取、grep、列目錄屬安全動作，可放心執行
- **危險動作必須先問**：`rm -rf`、`git reset --hard`、`git push --force`、刪除分支、刪除遠端資源、第三方付費 API 呼叫

### 4.2 API Key 與 Secrets
- 任何 API Key（OpenAI、Google Gemini）**絕不**寫入 commit；只能放在 `.streamlit/secrets.toml`（已被 `.gitignore` 排除）或環境變數
- 看到 secrets 在程式碼中 → 立即停止並警告使用者

### 4.3 依賴變更
- 動 `requirements.txt` / `requirements-dev.txt` 前先問使用者
- 升降版本必須在 commit message 中說明動機

---

## 5. 溝通風格

- 預設**繁體中文**回覆；除非使用者切換語言
- 回報盡可能精簡，避免過度解釋；複雜決策才展開
- 工具呼叫前用一句話說明意圖（符合 Claude Code 規範）
- 完成任務後一段話結尾：**變更了什麼 + 下一步建議**

---

## 6. 不做清單（Anti-patterns）

- ❌ 在 service 印 log 或塞 `print()`（用 return value 表達狀態）
- ❌ 加抽象層 / 介面，除非至少有兩個實作場景
- ❌ 新增註解解釋「WHAT」（命名好就不需要）；只在「WHY 非明顯」時加註解
- ❌ 加 try / except 包住內部呼叫只為「保險」；只在系統邊界（外部 API、使用者輸入）做防呆
- ❌ 動 legacy（`_legacy/app.py`）— 該檔已退役，僅供查閱
- ❌ 在沒有跑過 `pytest` 與 `mypy` 前宣告任務完成

---

## 7. 任務啟動 SOP

每次新 session 或上下文重建，依序：

1. 讀 `CLAUDE.md`（本檔）→ 載入協議
2. 讀 `STATE.md` → 掌握進度與 Bug
3. 輕掃目錄結構 → 確認核心檔案存在，不修改
4. 等使用者下達具體任務
5. 接到任務後若需大幅改動 → 先回報計畫，等核可再執行

---

> **修訂紀錄**
>
> | 版本 | 日期 | 變更 |
> |---|---|---|
> | v2.0 | 2026-05-19 | 由 ARCHITECTURE.md + STATE.md 重建（原始 CLAUDE.md 遺失） |
