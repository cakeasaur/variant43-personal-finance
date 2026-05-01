from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.core.models import Transaction, TransactionType
from src.infra.db.connection import connect, transaction
from src.infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)
from src.infra.db.schema import SCHEMA_VERSION, init_schema


@pytest.fixture()
def conn(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    c = connect(db_path)
    init_schema(c)
    try:
        yield c
    finally:
        c.close()


def test_schema_version_is_persisted(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='schema_version';").fetchone()
    assert row is not None
    assert int(row["value"]) == SCHEMA_VERSION


def test_transaction_commit_persists_changes(conn):
    repo = TransactionRepository(conn)
    tx = Transaction(
        type=TransactionType.EXPENSE,
        amount_cents=12345,
        occurred_at=datetime.now(UTC),
        category_id=None,
        note="coffee",
    )
    with transaction(conn):
        tx_id = repo.create(tx)
    assert tx_id > 0

    stored = repo.list_between(
        start=datetime.now(UTC) - timedelta(days=1),
        end=datetime.now(UTC) + timedelta(days=1),
    )
    assert len(stored) == 1
    assert stored[0].transaction.amount_cents == 12345


def test_transaction_rollback_on_error(conn):
    repo = TransactionRepository(conn)
    tx = Transaction(
        type=TransactionType.EXPENSE,
        amount_cents=100,
        occurred_at=datetime.now(UTC),
    )
    with pytest.raises(RuntimeError):
        with transaction(conn):
            repo.create(tx)
            raise RuntimeError("boom")

    stored = repo.list_between(
        start=datetime.now(UTC) - timedelta(days=1),
        end=datetime.now(UTC) + timedelta(days=1),
    )
    assert stored == []


def test_nested_transaction_does_not_fail(conn):
    """Guard against `cannot start a transaction within a transaction`."""
    repo = TransactionRepository(conn)
    tx = Transaction(
        type=TransactionType.INCOME,
        amount_cents=500,
        occurred_at=datetime.now(UTC),
    )
    with transaction(conn):
        with transaction(conn):
            repo.create(tx)

    stored = repo.list_between(
        start=datetime.now(UTC) - timedelta(days=1),
        end=datetime.now(UTC) + timedelta(days=1),
    )
    assert len(stored) == 1


def test_category_ensure_defaults_is_idempotent(conn):
    cat_repo = CategoryRepository(conn)
    with transaction(conn):
        cat_repo.ensure_defaults()
    with transaction(conn):
        cat_repo.ensure_defaults()  # second run should not fail or duplicate

    names = [c.name for c in cat_repo.list_all()]
    assert len(names) == len(set(names))
    assert "Еда" in names


def test_list_between_ordering_and_filtering(conn):
    repo = TransactionRepository(conn)
    base = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    with transaction(conn):
        repo.create(Transaction(TransactionType.EXPENSE, 100, base))
        repo.create(Transaction(TransactionType.INCOME, 200, base + timedelta(hours=1)))
        repo.create(Transaction(TransactionType.EXPENSE, 300, base - timedelta(days=40)))

    rows = repo.list_between(start=base - timedelta(days=1), end=base + timedelta(days=1))
    assert [r.transaction.amount_cents for r in rows] == [200, 100]  # DESC by occurred_at


def test_list_between_type_filter_income_only(conn):
    repo = TransactionRepository(conn)
    base = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    with transaction(conn):
        repo.create(Transaction(TransactionType.INCOME,  500, base))
        repo.create(Transaction(TransactionType.EXPENSE, 200, base + timedelta(minutes=1)))
        repo.create(Transaction(TransactionType.INCOME,  300, base + timedelta(minutes=2)))

    result = repo.list_between(
        start=base - timedelta(hours=1),
        end=base + timedelta(hours=1),
        tx_type=TransactionType.INCOME,
    )
    assert all(r.transaction.type == TransactionType.INCOME for r in result)
    assert len(result) == 2


def test_list_between_type_filter_expense_only(conn):
    repo = TransactionRepository(conn)
    base = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    with transaction(conn):
        repo.create(Transaction(TransactionType.INCOME,  100, base))
        repo.create(Transaction(TransactionType.EXPENSE, 400, base + timedelta(minutes=1)))

    result = repo.list_between(
        start=base - timedelta(hours=1),
        end=base + timedelta(hours=1),
        tx_type=TransactionType.EXPENSE,
    )
    assert len(result) == 1
    assert result[0].transaction.amount_cents == 400


def test_list_between_rejects_invalid_range(conn):
    repo = TransactionRepository(conn)
    now = datetime.now(UTC)
    with pytest.raises(ValueError):
        repo.list_between(start=now, end=now - timedelta(seconds=1))


def test_goals_crud_and_validation(conn):
    goals = GoalRepository(conn)

    with pytest.raises(ValueError):
        goals.create(name="bad", target_cents=0)
    with pytest.raises(ValueError):
        goals.create(name="bad", target_cents=100, current_cents=-1)

    with transaction(conn):
        gid = goals.create(
            name="Подушка безопасности",
            target_cents=100_00,
            current_cents=25_00,
            deadline_at=datetime(2026, 12, 31, 0, 0, tzinfo=UTC),
            note="копим",
        )
    all_ = goals.list_all()
    assert any(g.id == gid for g in all_)

    with transaction(conn):
        goals.update(
            goal_id=gid,
            name="Подушка",
            target_cents=200_00,
            current_cents=50_00,
            deadline_at=None,
            note=None,
        )
    g = next(x for x in goals.list_all() if x.id == gid)
    assert g.name == "Подушка"
    assert g.target_cents == 200_00
    assert g.current_cents == 50_00
    assert g.deadline_at is None
    assert g.note is None

    with transaction(conn):
        goals.delete(goal_id=gid)
    assert [x for x in goals.list_all() if x.id == gid] == []


def test_goal_get_returns_none_for_missing(conn):
    goals = GoalRepository(conn)
    assert goals.get(goal_id=9999) is None


def test_goal_deposit_increments_and_caps(conn):
    goals = GoalRepository(conn)
    with transaction(conn):
        gid = goals.create(name="Отпуск", target_cents=10_000, current_cents=0)

    with transaction(conn):
        g = goals.deposit(goal_id=gid, amount_cents=3_000)
    assert g.current_cents == 3_000
    assert round(g.progress_ratio, 2) == 0.3

    # Deposit more than remaining — must cap at target
    with transaction(conn):
        g = goals.deposit(goal_id=gid, amount_cents=99_999)
    assert g.current_cents == g.target_cents
    assert g.progress_ratio == 1.0


def test_goal_deposit_rejects_non_positive(conn):
    goals = GoalRepository(conn)
    with transaction(conn):
        gid = goals.create(name="Тест", target_cents=500)
    with pytest.raises(ValueError):
        goals.deposit(goal_id=gid, amount_cents=0)
    with pytest.raises(ValueError):
        goals.deposit(goal_id=gid, amount_cents=-100)


def test_goal_deposit_raises_for_missing_goal(conn):
    goals = GoalRepository(conn)
    with pytest.raises(ValueError):
        goals.deposit(goal_id=9999, amount_cents=100)


def test_reminders_create_list_mark_done_and_delete(conn):
    repo = ReminderRepository(conn)
    due = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)

    with transaction(conn):
        rid_none = repo.create(name="Оплатить интернет", due_at=due, recurrence="none", amount_cents=500_00)
        rid_daily = repo.create(name="Напоминание", due_at=due, recurrence="daily")

    items = repo.list_due_sorted()
    assert {r.id for r in items} >= {rid_none, rid_daily}

    with transaction(conn):
        repo.mark_done(reminder_id=rid_none)  # one-off -> removed
    assert all(r.id != rid_none for r in repo.list_due_sorted())

    with transaction(conn):
        repo.mark_done(reminder_id=rid_daily)  # recurring -> postponed
    next_item = next(r for r in repo.list_due_sorted() if r.id == rid_daily)
    assert next_item.due_at == due + timedelta(days=1)

    with transaction(conn):
        repo.delete(reminder_id=rid_daily)
    assert [r for r in repo.list_due_sorted() if r.id == rid_daily] == []


def test_reminder_list_upcoming_filters_by_window(conn):
    repo = ReminderRepository(conn)
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    with transaction(conn):
        repo.create(name="Сегодня",    due_at=now + timedelta(hours=2))
        repo.create(name="Через 5д",   due_at=now + timedelta(days=5))
        repo.create(name="Через 10д",  due_at=now + timedelta(days=10))
        repo.create(name="Прошлое",    due_at=now - timedelta(days=1))

    upcoming = repo.list_upcoming(within_days=7, now=now)
    names = [r.name for r in upcoming]
    assert "Сегодня"   in names
    assert "Через 5д"  in names
    assert "Через 10д" not in names
    assert "Прошлое"   not in names


def test_reminder_list_upcoming_empty_window(conn):
    repo = ReminderRepository(conn)
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    with transaction(conn):
        repo.create(name="Будущее", due_at=now + timedelta(days=5))

    assert repo.list_upcoming(within_days=0, now=now) == []


def test_reminder_list_upcoming_rejects_negative(conn):
    repo = ReminderRepository(conn)
    with pytest.raises(ValueError):
        repo.list_upcoming(within_days=-1)


def test_reminders_validation(conn):
    repo = ReminderRepository(conn)
    due = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        repo.create(name="  ", due_at=due)
    with pytest.raises(ValueError):
        repo.create(name="x", due_at=due, recurrence="yearly")
    with pytest.raises(ValueError):
        repo.create(name="x", due_at=due, amount_cents=-1)
