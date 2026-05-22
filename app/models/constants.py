"""硬性門檻單一真實來源（Single Source of Truth）。

此模組蒐集散落於各 chapter / strategy 模組的『學長硬性門檻』，
未來所有 service 與 UI 都應從此處 import，杜絕重複定義漂移。

命名規則：
    - SCREAMING_SNAKE_CASE
    - 標註 `Final[type]` 防止誤改
    - 數值單位寫在常數名稱裡（如 _NTD / _RATIO / _PERCENT / _YEARS）

依賴方向：本模組**不依賴**任何其他模組（含同層 models）。
"""

from __future__ import annotations

from typing import Final


# ============================================================
# 1. 個人現金流 / DTI（Ch.1）
# ============================================================
# 學長鐵律：銀行核貸死線 — DTI > 70% 直接拒貸或大砍成數。
DTI_DANGER_RATIO: Final[float] = 0.70

# 淨現金流『可投資緩衝』門檻 — 低於此值視為 LOW_BUFFER（services.cashflow）。
LOW_BUFFER_THRESHOLD_NTD: Final[int] = 20_000


# ============================================================
# 2. 物件硬性紅線（Ch.2 / Ch.5 / Ch.7 / Ch.10）
# ============================================================
# 銀行幾乎不貸款的最小坪數 — 小於此值物件流動性極差。
MIN_SAFE_PING: Final[float] = 15.0

# 梯戶比紅線 — 大於此值租金天花板被砍 10-15%（戶數 / 電梯數）。
ELEVATOR_RATIO_DANGER: Final[float] = 4.0

# 老屋脫手紅線 — RC 耐用 50 年 − 銀行最長貸 30 年，實務取 35 年。
# 超過此屋齡的物件，下一手買方無法申請長年期房貸。
EXIT_AGE_RED_LINE_YEARS: Final[int] = 35

# 央行豪宅線（雙北）— 超過此總價適用豪宅限貸令、貸款成數大砍。
# 其他六都 6,000 萬 / 其他縣市 4,000 萬（暫不細分，由 service 層處理）。
MANSION_PRICE_TAIPEI_NTD: Final[int] = 70_000_000

# 銀行 RC 結構耐用年限（影響老屋脫手紅線推演）。
RC_DURABILITY_YEARS: Final[int] = 50

# 房貸年期天花板（即便屋齡 0 銀行也不會貸超過此值）。
BANK_MAX_LOAN_YEARS_PER_PROPERTY: Final[int] = 30

# 梯戶比『健康』上限 — ≤ 此值為 HEALTHY，介於此與 ELEVATOR_RATIO_DANGER 為 BORDERLINE。
HEALTHY_ELEVATOR_RATIO_MAX: Final[float] = 2.5


# ============================================================
# 3. 租金科學定價係數（Ch.3）
# ============================================================
# 樓層係數：1-2 樓治安/採光較差打 9 折；6 樓以上視野好加 1 成。
FLOOR_COEFFICIENT_MAP: Final[dict[str, float]] = {
    "1-2 樓": 0.9,
    "3-5 樓": 1.0,
    "6 樓以上": 1.1,
}

# 屋齡係數：新屋附加感強加 2 成；老屋打 8 折避免空租。
AGE_COEFFICIENT_MAP: Final[dict[str, float]] = {
    "5 年內": 1.2,
    "5-10 年": 1.0,
    "10 年以上": 0.8,
}

# 空租天數紅線 — 超過此天數啟動階梯式降價 SOP。
VACANCY_DAYS_DANGER: Final[int] = 20

# 空租階梯式降價三階段（以建議租金為基準）。
VACANCY_STEP1_DISCOUNT: Final[float] = 0.95   # 先降 5%
VACANCY_STEP2_DISCOUNT: Final[float] = 0.92   # 再降 3%（累計 8%）
VACANCY_FLOOR_DISCOUNT: Final[float] = 0.85   # 極限：不可低於原價 15%


# ============================================================
# 4. 租客七道信用防線（Ch.3）
# ============================================================
TENANT_CHECK_POINTS_PER_ITEM: Final[int] = 15
TENANT_CHECK_TOTAL_MAX: Final[int] = 105       # 7 × 15
TENANT_CHECK_PASS_THRESHOLD: Final[int] = 75
TENANT_CHECK_EXCELLENT_THRESHOLD: Final[int] = 90

# ===== 議價戰術 multiplier（strategy_negotiation）=====
NEGOTIATION_ANCHOR_DISCOUNT: Final[float] = 0.95   # 戰術 1：定錨單價（廣告戶 × 0.95）
NEGOTIATION_KILL_SHOT_DISCOUNT: Final[float] = 0.90  # 獵物確認：私人 lien × 0.90
FINAL_OFFER_DEFAULT_DISCOUNT: Final[float] = 0.85  # 戰術 3：開價 × 0.85
FINAL_OFFER_DEFAULT_ROUNDOFF_WAN: Final[float] = 50.0  # 戰術 3：再砍 50 萬零頭

# ===== 議價前必做 SOP（Ch.5 區塊二）=====
NEGOTIATION_SOP_TOTAL_STEPS: Final[int] = 7
NEGOTIATION_SOP_INCOMPLETE_THRESHOLD: Final[int] = 5  # < 此值為 NOT_READY

# ===== 自用 5 年免稅鐵證查核（Ch.7）=====
RESIDENCY_EVIDENCE_TOTAL: Final[int] = 5
RESIDENCY_EVIDENCE_GAPPED_THRESHOLD: Final[int] = 3   # < 此值為 INSUFFICIENT


# ============================================================
# 5. 槓桿魔法 — 增貸 / M2 / 股票質押（Ch.4、Ch.6、Ch.8、strategy_*）
# ============================================================
# 銀行重新鑑價後的可增貸成數（科目四增貸 / 合資套利公式）。
BANK_REFINANCE_LTV: Final[float] = 0.80

# 合資現金買斷的破盤折扣基準（市價 × 此係數）。
CASH_DEAL_DEFAULT_DISCOUNT: Final[float] = 0.80

# 等待銀行重新鑑價的最少月數。
WAIT_MONTHS_FOR_REVAL: Final[int] = 6

# 股票質押成數（市值 × 此係數＝可質押金額）。
STOCK_PLEDGE_LTV: Final[float] = 0.60

# 股票質押年利率（VIP 隱形槓桿）。
STOCK_PLEDGE_ANNUAL_RATE: Final[float] = 0.025

# 5 倍槓桿買房 vs 定存 10 年對決的模型參數（Ch.1 M2 計算機）。
M2_INITIAL_CAPITAL_NTD: Final[int] = 10_000_000
M2_LEVERAGE_MULTIPLIER: Final[int] = 5
M2_BANK_DEPOSIT_ANNUAL_RATE: Final[float] = 0.015
M2_SIMULATION_YEARS: Final[int] = 10

# 空租準備金：地段等級 → 預估空租月數（Ch.8）。
LOCATION_VACANCY_MONTHS_MAP: Final[dict[int, int]] = {
    1: 1,  # 極精華（雙北捷運站旁／信義內科）
    2: 2,  # 次精華（六都市中心、學區外圍）
    3: 3,  # 一般市區（縣市政府周邊）
    4: 4,  # 重劃區／市郊
    5: 6,  # 極偏遠（鄉鎮、無捷運／工作圈外）→ 跳一個月
}


# ============================================================
# 6. AI 顧問（Ch.9）
# ============================================================
# OpenAI 模型選項（依價格 / 品質排序）。
OPENAI_MODEL_OPTIONS: Final[tuple[str, ...]] = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
)
OPENAI_DEFAULT_MODEL: Final[str] = "gpt-4o-mini"
OPENAI_DEFAULT_TEMPERATURE: Final[float] = 0.7
OPENAI_TEMPERATURE_MIN: Final[float] = 0.0
OPENAI_TEMPERATURE_MAX: Final[float] = 1.5

# 環境變數 / Streamlit secrets 的 API Key 鍵名。
OPENAI_API_KEY_SECRET_NAME: Final[str] = "OPENAI_API_KEY"

# OpenAI 各模型每百萬 tokens 的 USD 報價（2026 年公告價，可隨更新）。
# 取值方式：input / output tokens 分開計費。
OPENAI_PRICING_USD_PER_MILLION_TOKENS: Final[dict[str, dict[str, float]]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}

# 預設每日 / 每 session 支出上限（USD），公開部署時建議在 secrets 覆寫。
OPENAI_DEFAULT_SPEND_CAP_USD: Final[float] = 1.00

# Repository 層自動重試的最大次數（針對 RateLimitError / APIConnectionError）。
# 第 N 次重試延遲 = 2 ** N 秒 → 1s, 2s, 4s, 最差合計 ~7 秒。
OPENAI_MAX_RETRIES: Final[int] = 3
OPENAI_RETRY_BASE_DELAY_SECONDS: Final[float] = 1.0


# ===== Gemini（Google AI Studio）— Ch.9 第二可選 provider =====
# Free tier 提供 gemini-2.5-flash / 2.0-flash 等，預設選 2.5-flash 兼顧速度與品質。
# 參考：https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL_OPTIONS: Final[tuple[str, ...]] = (
    "gemini-2.5-flash",          # 預設，free tier 可用、快速
    "gemini-2.5-flash-lite",     # 更輕量、free tier 可用
    "gemini-2.0-flash",          # 上一代 flash，仍維持 free tier
    "gemini-2.5-pro",            # 最高品質（無 free tier）
)
GEMINI_DEFAULT_MODEL: Final[str] = "gemini-2.5-flash"
GEMINI_API_KEY_SECRET_NAME: Final[str] = "GEMINI_API_KEY"

# Gemini 各模型每百萬 tokens 的 USD 報價（2026 年公告 paid-tier 價，free tier 為 0）。
# 用途：顯示『等同付費版會花多少』；free tier 用戶可視為估算上限。
GEMINI_PRICING_USD_PER_MILLION_TOKENS: Final[dict[str, dict[str, float]]] = {
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash":      {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
}

# Free tier 可用的模型集合（顯示時可用來標記「免費」徽章）。
GEMINI_FREE_TIER_MODELS: Final[frozenset[str]] = frozenset({
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
})
