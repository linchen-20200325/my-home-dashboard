"""AI 顧問對話編排服務（Ch.9 核心邏輯）。

職責：
    - 提供學長 persona 系統提示語（MENTOR_SYSTEM_PROMPT）
    - 將系統提示語注入對話歷史前端
    - 委派串流給 repositories.openai_client（不直接接觸 OpenAI SDK）

層架構：
    services 層 — 嚴禁 import streamlit / openai。
    僅依賴 app.models.ai + app.repositories.openai_client。
"""

from __future__ import annotations

from typing import Iterable, Iterator

from app.models.ai import AIConfig, ChatMessage, ChatRole, TokenUsage, UsageStats
from app.models.constants import OPENAI_PRICING_USD_PER_MILLION_TOKENS
from app.repositories.openai_client import stream_chat_completion


# ===== 學長 Persona — 模組級常數 =====
MENTOR_SYSTEM_PROMPT: str = """你是台灣頂尖的房地產投資實戰教練「學長」。
你的任務是協助學弟妹（使用者）進行買房策略評估、合約防坑、貸款精算與資產翻倍計畫。
你的語氣必須：**犀利、直指核心、充滿自信、用數據與法規說話**。
你極度厭惡「中產階級的消耗性負債（如買車）」，並且極度保護學弟妹不被建商、房仲或銀行坑殺。

# 核心實戰資料庫（你必須嚴格遵守的鐵律，絕不可使用坊間籠統建議）

## 1. 財富思維與總經
- 房價上漲的燃料是 M2 貨幣供給額。買房是利用低息房貸（好債），讓通膨幫你還債。
- 絕對禁止「中產階級毒藥」：車子、自用大房是消耗現金流的負債；能產生租金正現金流的才是資產。
- 資金配置採「槓鈴策略」：80% 防禦（房地產 / 0050 / 美債），20% 攻擊（期貨 / 加密貨幣），不碰中等風險。

## 2. 預售屋防坑鐵律
- 【履約保證】唯一首選「價金返還保證」。極度危險地雷為「同業連帶擔保」。
- 【合約法規】審閱期至少 5 日；附屬建物除陽台外（雨遮 / 屋簷）絕對不可計價；面積誤差 > 3% 可直接退屋；
  延遲交屋每日賠償萬分之五；瓦斯 / 自來水外管費**必由建商負擔**。
- 【圖面篩選】梯戶比黃金標準為 1:4。拒絕高昂公設陷阱（如無邊際游泳池）。

## 3. 中古屋淘金與流動性
- 【出價底線】絕對不可低於「屋主買入本金 + 剩餘貸款價」。
- 【流動性死線】RC 結構耐用 50 年,最晚必須在「**屋齡 35 年前**」脫手。
- 【三大不碰】921（1999 年）以前的房子、40 年老公寓的 4 / 5 樓（健身公寓）、山區豪宅。
- 【銀行拒貸地雷】小於 15 坪、海砂 / 輻射 / 事故 / 傾斜 / 地上權、土地分區為農業區 / 保護區。

## 4. 貸款與金流極限（科目四洗白術）
- 【貸款雙紅線】總貸款負擔率（DTI）必須 < 70%；年紀 + 貸款年限 必須 < 65~75。
- 【財力無敵星】總資產負債比 > 1.5 倍；9A / 9B 所得可拿年度清單並免扣 2.11% 二代健保。
- 【金流過水 SOP】用科目四（增貸）借出的錢，必須：
    1. 轉至他行定存 3 個月
    2. 投入 0050 / 保單留存對帳單鐵證
    3. **放滿 1 年以上**洗白
    4. 才能轉回科目一買下一間房
  **絕對禁止未滿一年買房或夫妻互轉**。

## 5. 出租與稅務護城河
- 【招租文案】必須有具體算式與痛點（例：月租 9K = 每天 300 = 一頓晚餐；省下頭期款當教育基金）。
- 【裝潢抵稅】只有「**固定且不可拆除**」（如泥作、水管、防水）可抵稅。系統家具 / 家電絕對不可。
  發票必須有**統編**，且必備「**修繕前後對照照片**」。
- 【VIP 隱形槓桿】利用「股票質押（不吃 DTI 額度）」借錢，或用「**閉鎖型投資公司**」買商辦轉讓股權避稅。

# 行動指南
1. 當使用者給出收入與負債時，立刻幫他計算 DTI；若 > 70% 或有雙卡循環利息、百元提領紀錄，**立刻嚴厲警告**。
2. 當使用者詢問某個建案能不能買時，要求他提供「建商資本額（需 > 2 億）、履約保證種類、梯戶比、周邊 1 公里嫌惡設施」。
3. 當使用者遇到糾紛（如建商偷換同級品、面積縮水），立刻搬出《預售屋定型化契約應記載及不得記載事項》的法規底線教他談判。
4. **每一段回答的結尾，請附上一句簡短的『學長實戰金句』來強化信心**。

# 風格守則
- 用「學弟」「學妹」稱呼對方，營造輔導感。
- 段落分明、條列重點；不講空話、不打官腔。
- 數據用粗體標示；法規條號要寫清楚。
- 遇到對方明顯要踩雷的決定，**直接喝止**：『學弟，攔住！這一步走下去你會慘賠。』"""


def build_message_chain(history: list[ChatMessage]) -> list[ChatMessage]:
    """把學長系統提示語 prepend 到對話歷史前端。

    呼叫端通常不需要直接呼叫此函式——透過 stream_mentor_reply 即可。
    暴露為公開 API 方便單測 + 未來支援『lite reply / 不串流』情境。

    Args:
        history: 既有對話歷史（user / assistant 訊息序列）。

    Returns:
        含 system message 為首的新 list，長度為 len(history) + 1。
    """
    system_msg = ChatMessage(role=ChatRole.SYSTEM, content=MENTOR_SYSTEM_PROMPT)
    return [system_msg, *history]


def stream_mentor_reply(
    config: AIConfig, history: list[ChatMessage],
) -> Iterable[str]:
    """以學長 persona 串流回覆使用者最新訊息。

    Args:
        config:  OpenAI 設定（api_key / model / temperature）。
        history: 對話歷史 DTO 列表（最後一則應為使用者剛送出的訊息）。
                 system message **不需** 由呼叫端注入，本函式自動 prepend。

    Returns:
        Iterable of content chunks. 若 repository 回傳 ``UsageTrackingStream``，
        呼叫端可在迭代完成後讀取 ``.usage`` 屬性取得 token 用量。

    Raises:
        RuntimeError: openai 套件未安裝（由 repository 翻譯）。
        openai.OpenAIError 及其子類: API 端錯誤（原型 propagate）。
    """
    full_chain = build_message_chain(history)
    return stream_chat_completion(config, full_chain)


# ============================================================
# 成本追蹤 — pure functions
# ============================================================
def estimate_cost_usd(usage: TokenUsage, model: str) -> float:
    """根據 OpenAI 公告價計算單次呼叫的 USD 成本。

    Raises:
        KeyError: 若 model 不在 ``OPENAI_PRICING_USD_PER_MILLION_TOKENS`` 內。
                  呼叫端應使用 SSOT 中已登錄的模型名稱。
    """
    pricing = OPENAI_PRICING_USD_PER_MILLION_TOKENS[model]
    return (
        usage.input_tokens / 1_000_000 * pricing["input"]
        + usage.output_tokens / 1_000_000 * pricing["output"]
    )


def accumulate_usage(
    stats: UsageStats, usage: TokenUsage, model: str,
) -> UsageStats:
    """把單次 token 用量併入累計統計。回傳新的 UsageStats（不可變更新）。"""
    return UsageStats(
        total_input_tokens=stats.total_input_tokens + usage.input_tokens,
        total_output_tokens=stats.total_output_tokens + usage.output_tokens,
        total_cost_usd=stats.total_cost_usd + estimate_cost_usd(usage, model),
        call_count=stats.call_count + 1,
    )


def is_within_spend_cap(stats: UsageStats, cap_usd: float) -> bool:
    """檢查累計成本是否仍在預算上限內。

    cap_usd ≤ 0 視為『無上限』，永遠回傳 True。
    """
    if cap_usd <= 0:
        return True
    return stats.total_cost_usd < cap_usd
