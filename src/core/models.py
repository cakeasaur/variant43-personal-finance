from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

__all__ = [
    "TransactionType",
    "Transaction",
]


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True, slots=True)
class Transaction:
    type: TransactionType
    amount_cents: int
    occurred_at: datetime
    category_id: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.amount_cents <= 0:
            raise ValueError("amount_cents must be > 0")
