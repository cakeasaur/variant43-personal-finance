from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.models import Transaction, TransactionType
from src.core.reporting import expense_by_category, expense_by_day, totals_for_period


def dt(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def test_transaction_rejects_negative_amount() -> None:
    with pytest.raises(ValueError):
        Transaction(type=TransactionType.EXPENSE, amount_cents=-1, occurred_at=dt(2026, 1, 1))


def test_transaction_rejects_zero_amount() -> None:
    with pytest.raises(ValueError):
        Transaction(type=TransactionType.INCOME, amount_cents=0, occurred_at=dt(2026, 1, 1))


def test_totals_for_period_filters_by_date_inclusive() -> None:
    start = dt(2026, 1, 1)
    end = dt(2026, 1, 31, 23, 59)

    tx = [
        Transaction(TransactionType.INCOME, 10_00, occurred_at=start),
        Transaction(TransactionType.EXPENSE, 3_00, occurred_at=end),
        Transaction(TransactionType.EXPENSE, 1_00, occurred_at=start - timedelta(seconds=1)),
        Transaction(TransactionType.INCOME, 2_00, occurred_at=end + timedelta(seconds=1)),
    ]

    totals = totals_for_period(tx, start=start, end=end)
    assert totals.income_cents == 10_00
    assert totals.expense_cents == 3_00
    assert totals.balance_cents == 7_00


def test_totals_for_period_rejects_invalid_range() -> None:
    with pytest.raises(ValueError):
        totals_for_period([], start=dt(2026, 2, 1), end=dt(2026, 1, 1))


def test_expense_by_category_sums_only_expenses() -> None:
    start = dt(2026, 1, 1)
    end = dt(2026, 1, 31, 23, 59)

    tx = [
        Transaction(TransactionType.EXPENSE, 5_00, occurred_at=dt(2026, 1, 10), category_id=1),
        Transaction(TransactionType.EXPENSE, 2_50, occurred_at=dt(2026, 1, 10), category_id=1),
        Transaction(TransactionType.EXPENSE, 1_00, occurred_at=dt(2026, 1, 20), category_id=None),
        Transaction(TransactionType.INCOME, 100_00, occurred_at=dt(2026, 1, 10), category_id=1),
    ]

    out = expense_by_category(tx, start=start, end=end)
    assert out == {1: 7_50, None: 1_00}


def test_expense_by_category_rejects_invalid_range() -> None:
    with pytest.raises(ValueError):
        expense_by_category([], start=dt(2026, 2, 1), end=dt(2026, 1, 1))


def test_expense_by_day_sums_only_expenses() -> None:
    start = dt(2026, 1, 1)
    end = dt(2026, 1, 31, 23, 59)

    tx = [
        Transaction(TransactionType.EXPENSE, 5_00, occurred_at=dt(2026, 1, 10, 10, 0)),
        Transaction(TransactionType.EXPENSE, 2_50, occurred_at=dt(2026, 1, 10, 18, 30)),
        Transaction(TransactionType.EXPENSE, 1_00, occurred_at=dt(2026, 1, 20, 9, 0)),
        Transaction(TransactionType.INCOME, 100_00, occurred_at=dt(2026, 1, 10, 12, 0)),
    ]

    out = expense_by_day(tx, start=start, end=end)
    assert out[dt(2026, 1, 10).date()] == 7_50
    assert out[dt(2026, 1, 20).date()] == 1_00


def test_expense_by_day_rejects_invalid_range() -> None:
    with pytest.raises(ValueError):
        expense_by_day([], start=dt(2026, 2, 1), end=dt(2026, 1, 1))

