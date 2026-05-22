"""Ch.1 個人現金流診斷服務。

純函式（pure function）設計：
    - 嚴禁 `import streamlit`
    - 輸入：app.models.cashflow.CashflowInput
    - 輸出：app.models.cashflow.CashflowSnapshot
    - 無外部 I/O，可獨立 unit test
"""

from __future__ import annotations

from app.models.cashflow import (
    CashflowInput,
    CashflowSeverity,
    CashflowSnapshot,
)
from app.models.constants import (
    DTI_DANGER_RATIO,
    LOW_BUFFER_THRESHOLD_NTD,
)


def diagnose_cashflow(payload: CashflowInput) -> CashflowSnapshot:
    """根據月度收支算出淨現金流、DTI、健康度分級。

    DTI 採銀行標準公式：
        DTI = (現有房貸 + 車貸 + 信貸 + 卡債最低應繳 + 其他) / 總收入

    判定優先序（severity 由壞至好）：
        1. total_income ≤ 0 → DTI = inf → DTI_LOCKED
        2. DTI > 0.70（DTI_DANGER_RATIO）→ DTI_LOCKED
        3. net_cashflow < 0 → NEGATIVE
        4. net_cashflow < LOW_BUFFER_THRESHOLD_NTD → LOW_BUFFER
        5. 其他 → HEALTHY

    毒藥旗標（has_bad_debt）：透過 ``payload.poison_debt_ntd > 0`` 判定，
    扣除「現有房貸」後若仍有車貸／信貸／卡債／其他即觸發，與 severity 正交。

    Args:
        payload: 月度收支輸入 DTO。

    Returns:
        CashflowSnapshot：含淨現金流、DTI、毒藥旗標、嚴重度、每月總負債。
    """
    total_debt = payload.total_debt_ntd
    net = payload.total_income_ntd - payload.living_cost_ntd - total_debt

    if payload.total_income_ntd <= 0:
        dti = float("inf")
    else:
        dti = total_debt / payload.total_income_ntd

    severity = _classify_severity(net, dti)

    return CashflowSnapshot(
        net_cashflow_ntd=net,
        dti=dti,
        has_bad_debt=payload.poison_debt_ntd > 0,
        severity=severity,
        total_debt_ntd=total_debt,
    )


def _classify_severity(net_cashflow_ntd: int, dti: float) -> CashflowSeverity:
    """嚴重度分級的純判定函式，方便獨立測試。"""
    if dti > DTI_DANGER_RATIO:
        return CashflowSeverity.DTI_LOCKED
    if net_cashflow_ntd < 0:
        return CashflowSeverity.NEGATIVE
    if net_cashflow_ntd < LOW_BUFFER_THRESHOLD_NTD:
        return CashflowSeverity.LOW_BUFFER
    return CashflowSeverity.HEALTHY
