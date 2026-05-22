"""個人現金流診斷 DTO（Ch.1 主要使用，Ch.10 決策雷達引用）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CashflowSeverity(str, Enum):
    """淨現金流 / DTI 綜合健康度分級。

    順序由壞至好：DTI 死線 > 中產毒藥 > 現金流負 > 緩衝過低 > 健康。
    """

    DTI_LOCKED = "dti_locked"        # DTI > 70%，銀行核貸死線
    POISON_DEBT = "poison_debt"      # 有壞債（車貸／信貸／卡債）
    NEGATIVE = "negative"            # 淨現金流 < 0
    LOW_BUFFER = "low_buffer"        # 淨現金流 < 20,000
    HEALTHY = "healthy"              # 淨現金流 ≥ 20,000 且無壞債、DTI 合格


@dataclass(frozen=True)
class CashflowInput:
    """月度收支輸入（單位：元 NTD）。

    DTI 標準公式（銀行核貸）：
        DTI = (現有房貸 + 車貸 + 信貸 + 卡債最低應繳 + 其他) / 總收入

    毒藥負債（中產毒藥警告）：上述五項扣掉現有房貸後的總和
    —— 房貸對應「房子」這個資產，不計入毒藥；其餘四項皆為消耗型負債。
    """

    total_income_ntd: int
    living_cost_ntd: int
    existing_mortgage_ntd: int = 0
    car_loan_ntd: int = 0
    personal_loan_ntd: int = 0
    credit_card_min_ntd: int = 0
    other_debt_ntd: int = 0

    @property
    def total_debt_ntd(self) -> int:
        """每月負債總和（DTI 分子）。"""
        return (
            self.existing_mortgage_ntd
            + self.car_loan_ntd
            + self.personal_loan_ntd
            + self.credit_card_min_ntd
            + self.other_debt_ntd
        )

    @property
    def poison_debt_ntd(self) -> int:
        """中產毒藥負債（扣除現有房貸後的消耗型負債）。"""
        return (
            self.car_loan_ntd
            + self.personal_loan_ntd
            + self.credit_card_min_ntd
            + self.other_debt_ntd
        )


@dataclass(frozen=True)
class CashflowSnapshot:
    """現金流健康快照（service 計算後回傳給 UI）。"""

    net_cashflow_ntd: int
    dti: float
    has_bad_debt: bool
    severity: CashflowSeverity
    total_debt_ntd: int = 0

    @property
    def is_healthy(self) -> bool:
        return self.severity == CashflowSeverity.HEALTHY
