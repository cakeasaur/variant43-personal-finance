from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from .models import Transaction, TransactionType


@dataclass(frozen=True, slots=True)
class Totals:
    income_cents: int
    expense_cents: int

    @property
    def balance_cents(self) -> int:
        return self.income_cents - self.expense_cents


def _filter_period(
    transactions: Iterable[Transaction],
    start: datetime,
    end: datetime,
) -> list[Transaction]:
    if end < start:
        raise ValueError("end must be >= start")
    return [t for t in transactions if start <= t.occurred_at <= end]


def totals_for_period(
    transactions: Iterable[Transaction],
    *,
    start: datetime,
    end: datetime,
) -> Totals:
    income = 0
    expense = 0
    for t in _filter_period(transactions, start, end):
        if t.type == TransactionType.INCOME:
            income += t.amount_cents
        else:
            expense += t.amount_cents
    return Totals(income_cents=income, expense_cents=expense)


def expense_by_category(
    transactions: Iterable[Transaction],
    *,
    start: datetime,
    end: datetime,
) -> dict[int | None, int]:
    out: dict[int | None, int] = {}
    for t in _filter_period(transactions, start, end):
        if t.type != TransactionType.EXPENSE:
            continue
        out[t.category_id] = out.get(t.category_id, 0) + t.amount_cents
    return out


def expense_by_day(
    transactions: Iterable[Transaction],
    *,
    start: datetime,
    end: datetime,
) -> dict[date, int]:
    out: dict[date, int] = {}
    for t in _filter_period(transactions, start, end):
        if t.type != TransactionType.EXPENSE:
            continue
        d = t.occurred_at.date()
        out[d] = out.get(d, 0) + t.amount_cents
    return out


def income_by_day(
    transactions: Iterable[Transaction],
    *,
    start: datetime,
    end: datetime,
) -> dict[date, int]:
    out: dict[date, int] = {}
    for t in _filter_period(transactions, start, end):
        if t.type != TransactionType.INCOME:
            continue
        d = t.occurred_at.date()
        out[d] = out.get(d, 0) + t.amount_cents
    return out
