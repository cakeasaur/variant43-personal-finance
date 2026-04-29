from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter

from .models import Transaction, TransactionType
from .reporting import expense_by_category, expense_by_day, totals_for_period


def generate_transactions(*, n: int, start: datetime) -> list[Transaction]:
    if n < 0:
        raise ValueError("n must be >= 0")
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    out: list[Transaction] = []
    for i in range(n):
        occurred_at = start + timedelta(minutes=i)
        ttype = TransactionType.EXPENSE if i % 3 else TransactionType.INCOME
        out.append(
            Transaction(
                type=ttype,
                amount_cents=100 + (i % 10),
                occurred_at=occurred_at,
                category_id=(i % 8) if ttype == TransactionType.EXPENSE else None,
                note=None,
            )
        )
    return out


def benchmark_reporting(*, n: int = 50_000) -> dict[str, float]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=365)
    tx = generate_transactions(n=n, start=start)

    t0 = perf_counter()
    totals_for_period(tx, start=start, end=end)
    t1 = perf_counter()

    expense_by_category(tx, start=start, end=end)
    t2 = perf_counter()

    expense_by_day(tx, start=start, end=end)
    t3 = perf_counter()

    return {
        "n": float(n),
        "totals_s": t1 - t0,
        "by_category_s": t2 - t1,
        "by_day_s": t3 - t2,
        "total_s": t3 - t0,
    }

