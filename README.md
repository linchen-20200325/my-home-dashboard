# 房產攻略（my-house-2026）

> 14 個模組的 Streamlit 房地產投資攻略 APP — 從現金流診斷到 AI 顧問，學長心法全收錄。

[![tests](https://github.com/CornCorn-2015/my-house-2026/actions/workflows/test.yml/badge.svg)](https://github.com/CornCorn-2015/my-house-2026/actions/workflows/test.yml)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![mypy](https://img.shields.io/badge/mypy-strict-2ea44f?logo=python)](./pyproject.toml)

---

## ✨ 功能總覽（14 個模組）

### 📘 八大核心章節
| # | 模組 | 內容重點 |
|---|---|---|
| Ch.1 | 首頁與個人現金流診斷 | DTI 死線判定 / M2 通膨 vs 槓桿買房 10 年對決 |
| Ch.2 | 預售屋：買就賺選址與合約快篩 | 建商體質 / 履保 4 級分類 / 梯戶比 / 合約地雷 |
| Ch.3 | 租金精算與優質租客雷達 | 滿租定價公式 / 七道信用防線評分 / 階梯式降價 |
| Ch.4 | 槓桿魔法：科目四金流過水 SOP | 整棟價差增貸 / 四階段洗白追蹤 |
| Ch.5 | 中古屋：居住成本與出價沙盤推演 | 4 大流動性地雷 / 7 步驟議價 SOP |
| Ch.6 | 節稅護城河與裝潢抵稅清單 | 國稅局白名單 / 股票質押試算 / 閉鎖型公司 + 他益信託 |
| Ch.7 | 安全離場與流動性評估 | 老屋脫手 35 年紅線 / 自用 5 年免稅鐵證 |
| Ch.8 | 奈米級防坑與核彈策略 | 預售屋陷阱 / 中古屋謄本地雷 / 空租準備金 / 文案銀行 |
| Ch.9 | 學長 AI 實戰顧問 | OpenAI 串流對話、內建學長 persona + 5 大鐵律 |
| Ch.10 | 400 題極限防坑與決策雷達 | 四象限終極判定（KILL_SHOT / GREEN_LIGHT / OBSERVATION）|
| Ch.11 | 看房現場實戰戰術手冊 | 四情境反問題金句、五神器工具清單、民法 365 條 |

### 🎯 三個進階策略
- **總體經濟與房價燃料理論** — M1B/M2 黃金交叉 + 區域紅利掃描
- **極限議價與談判心理戰** — 定錨 / 黑白臉 / 收尾擋箭牌
- **合資套利與科目四無限槓桿** — 破盤買進 + 半年後增貸抽本金 + 四道法律防護鎖

---

## 🚀 快速開始

### 本機開發

```bash
git clone https://github.com/CornCorn-2015/my-house-2026.git
cd my-house-2026

# 建議使用虛擬環境
python -m venv .venv && source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# (可選) 啟用 Ch.9 AI 顧問：複製 secrets 範本並填入 OpenAI key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 編輯 .streamlit/secrets.toml，把 OPENAI_API_KEY 換成真實值

# 啟動 APP
streamlit run main.py
# 或 streamlit run streamlit_app.py / app.py（三者皆可，內容相同）
```

預設打開 http://localhost:8501，側邊欄可切換 14 個頁面。

### Streamlit Cloud 部署

1. Fork 或匯入此 repo 到自己的 GitHub 帳號
2. 到 [share.streamlit.io](https://share.streamlit.io/) → **New app**
3. 連結 repo，**Main file path 選 `streamlit_app.py`**（推薦）或 `app.py` / `main.py`（任一皆可）
4. 在「Advanced settings → Secrets」貼上：
   ```toml
   OPENAI_API_KEY = "sk-proj-..."
   ```
   （不填的話 Ch.9 仍可載入，只是無法對話）
5. Deploy

### Docker（self-hosted）

```bash
# Build image（context 用 .dockerignore 自動排除 tests / _legacy / secrets）
docker build -t real-estate-app .

# Run（mount secrets 或直接 env var 注入 OpenAI key）
docker run -p 8501:8501 \
    -e OPENAI_API_KEY="sk-proj-..." \
    real-estate-app

# 開瀏覽器：http://localhost:8501
```

Image 設計：
- `python:3.11-slim` 基底，與 Streamlit Cloud 同版本
- 多階段 layer cache：`requirements.txt` 變動才重跑 `pip install`
- **非 root 使用者**執行（最小權限）
- **HEALTHCHECK** 每 30 秒 ping `/_stcore/health`，orchestrator（k8s / docker swarm）可自動恢復

---

## 🏗️ 架構（四層分層）

```
my-house-2026/
├── main.py / app.py / streamlit_app.py    ← 三個等價入口（composition root）
├── chapter_*.py / strategy_*.py           ← 14 個 thin re-export wrappers（向後相容）
├── app/                                   ← 真正的四層架構
│   ├── ui/
│   │   ├── pages/                         ← 14 個純 Streamlit 頁面
│   │   ├── components/                    ← 共用 verdict / metric_grid 元件
│   │   └── router.py                      ← CHAPTERS dict + sidebar + run()
│   ├── services/                          ← 10 個 pure-function 模組
│   ├── repositories/                      ← secrets + openai_client
│   └── models/                            ← 4 DTO + constants.py SSOT
├── tests/services/                        ← 46 pytest tests
├── _legacy/app.py                         ← 退役的早期 standalone 版本
├── ARCHITECTURE.md                        ← 完整藍圖文件
└── STATE.md                               ← Phase 1/2 33 步搬遷紀錄
```

### 層架構鐵律

| 層 | 允許 | 嚴禁 |
|---|---|---|
| **UI** (`app/ui/`) | streamlit + plotly + service / model imports | 寫公式、直接呼叫 openai、讀 secrets |
| **Service** (`app/services/`) | pure functions、DTO 轉換、repository 呼叫 | `import streamlit`、印 UI 元素 |
| **Repository** (`app/repositories/`) | 包裝外部 SDK（openai、未來 DB）、處理連線錯誤 | 寫商業邏輯、印 UI 元素 |
| **Models** (`app/models/`) | `@dataclass(frozen=True)`、Enum、常數 SSOT | import 其他層 |

依賴方向**單向**：`UI → Service → Repository`，所有層都可讀 `Models`。詳見 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。

---

## 🧪 測試

```bash
pip install -r requirements-dev.txt
pytest
```

```
============================== 46 passed in 0.11s ==============================
```

只跑邊界值測試：

```bash
pytest -m boundary
```

測試只覆蓋 services 層的 pure-function 邏輯（cashflow / pricing / decision_engine 三支），UI 層用 Streamlit 自身的執行時間驗證。

詳見 [`STATE.md`](./STATE.md) 的 Phase 3 backlog 取得擴充覆蓋率的剩餘待辦項目。

---

## 🤝 開發注意事項

- **單向依賴**：UI 不可 `import openai` 或 `from app.repositories.*`（透過 service 中介）。所有 service 不可 `import streamlit`。
- **DTO**：跨層傳遞用 `@dataclass(frozen=True)` 確保不可變。
- **SSOT**：硬性門檻（DTI=0.70、坪數=15、屋齡=35、梯戶比=4.0 …）集中於 `app/models/constants.py`。
- **新增章節**：先在 `app/services/*` 寫 pure function + 加 pytest，再在 `app/ui/pages/*` 寫 UI，最後到 `app/ui/router.py` 註冊 CHAPTERS。

---

## 📜 章節與 PR 歷史

| Phase 2 PR | 內容 | merged SHA |
|---|---|---|
| [#9](https://github.com/CornCorn-2015/my-house-2026/pull/9) | 14 模組 build + 藍圖 + 首批架構搬遷 | `d70a7a9` |
| [#10](https://github.com/CornCorn-2015/my-house-2026/pull/10) | Batch 2: Ch.3/4/10/11 + 3 strategy UI | `7b02b0c` |
| [#11](https://github.com/CornCorn-2015/my-house-2026/pull/11) | Batch 3: Ch.9 AI UI（完成 14/14）| `dcf90a4` |
| [#12](https://github.com/CornCorn-2015/my-house-2026/pull/12) | Final: router + composition root + legacy retire | `2fb5e2f` |
| [#13](https://github.com/CornCorn-2015/my-house-2026/pull/13) | pytest scaffold（46 tests）| `a10dc14` |
| [#14](https://github.com/CornCorn-2015/my-house-2026/pull/14) | 修復 Streamlit Cloud 部署入口 | `14fd524` |

---

## 📄 授權

無明確授權聲明 — 預設 all rights reserved。商業使用或衍生請先聯繫 owner。
