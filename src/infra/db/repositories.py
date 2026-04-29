from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ...core.models import Transaction, TransactionType


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _dt_from_iso(s: str) -> datetime:
    # Stored as ISO-8601 (with timezone). Python can parse this via fromisoformat.
    return datetime.fromisoformat(s)


def _dt_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    return dt.replace(microsecond=0).isoformat()


@dataclass(frozen=True, slots=True)
class Category:
    id: int
    name: str
    kind: str = "both"


class CategoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def ensure_defaults(self) -> None:
        defaults: Iterable[str] = ("Еда", "Транспорт", "Дом", "Здоровье", "Развлечения")
        now = _now_iso()
        for name in defaults:
            self.conn.execute(
                "INSERT INTO categories(name, kind, created_at, updated_at) VALUES (?, 'both', ?, ?) "
                "ON CONFLICT(name) DO NOTHING;",
                (name, now, now),
            )

    def list_all(self) -> list[Category]:
        rows = self.conn.execute("SELECT id, name, kind FROM categories ORDER BY name;").fetchall()
        return [Category(id=r["id"], name=r["name"], kind=r["kind"]) for r in rows]

    def create(self, *, name: str, kind: str = "both") -> int:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO categories(name, kind, created_at, updated_at) VALUES (?, ?, ?, ?);",
            (name, kind, now, now),
        )
        return int(cur.lastrowid)

    def update(self, *, category_id: int, name: str, kind: str = "both") -> None:
        now = _now_iso()
        self.conn.execute(
            "UPDATE categories SET name=?, kind=?, updated_at=? WHERE id=?;",
            (name, kind, now, int(category_id)),
        )

    def delete(self, *, category_id: int) -> None:
        self.conn.execute("DELETE FROM categories WHERE id=?;", (int(category_id),))


@dataclass(frozen=True, slots=True)
class StoredTransaction:
    id: int
    transaction: Transaction


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, t: Transaction) -> int:
        now = _now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO transactions(type, amount_cents, occurred_at, category_id, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(t.type),
                t.amount_cents,
                _dt_to_iso(t.occurred_at),
                t.category_id,
                t.note,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)

    def list_between(self, *, start: datetime, end: datetime) -> list[StoredTransaction]:
        if end < start:
            raise ValueError("end must be >= start")
        rows = self.conn.execute(
            """
            SELECT id, type, amount_cents, occurred_at, category_id, note
            FROM transactions
            WHERE occurred_at >= ? AND occurred_at <= ?
            ORDER BY occurred_at DESC, id DESC;
            """,
            (_dt_to_iso(start), _dt_to_iso(end)),
        ).fetchall()

        out: list[StoredTransaction] = []
        for r in rows:
            tx = Transaction(
                type=TransactionType(r["type"]),
                amount_cents=int(r["amount_cents"]),
                occurred_at=_dt_from_iso(r["occurred_at"]),
                category_id=r["category_id"],
                note=r["note"],
            )
            out.append(StoredTransaction(id=int(r["id"]), transaction=tx))
        return out

    def delete(self, *, tx_id: int) -> None:
        self.conn.execute("DELETE FROM transactions WHERE id=?;", (int(tx_id),))

    def update(self, *, tx_id: int, t: Transaction) -> None:
        """
        Update an existing transaction by id.

        `occurred_at` is stored as ISO-8601 string; `updated_at` is refreshed.
        """
        now = _now_iso()
        self.conn.execute(
            """
            UPDATE transactions
            SET type=?, amount_cents=?, occurred_at=?, category_id=?, note=?, updated_at=?
            WHERE id=?;
            """,
            (
                str(t.type),
                t.amount_cents,
                _dt_to_iso(t.occurred_at),
                t.category_id,
                t.note,
                now,
                int(tx_id),
            ),
        )


@dataclass(frozen=True, slots=True)
class Goal:
    id: int
    name: str
    target_cents: int
    current_cents: int
    deadline_at: datetime | None = None
    note: str | None = None

    @property
    def progress_ratio(self) -> float:
        if self.target_cents <= 0:
            return 0.0
        return min(1.0, self.current_cents / self.target_cents)


class GoalRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_all(self) -> list[Goal]:
        rows = self.conn.execute(
            """
            SELECT id, name, target_cents, current_cents, deadline_at, note
            FROM goals
            ORDER BY COALESCE(deadline_at, '9999-12-31T00:00:00+00:00') ASC, id DESC;
            """
        ).fetchall()
        return [
            Goal(
                id=int(r["id"]),
                name=str(r["name"]),
                target_cents=int(r["target_cents"]),
                current_cents=int(r["current_cents"]),
                deadline_at=_dt_from_iso(r["deadline_at"]) if r["deadline_at"] else None,
                note=r["note"],
            )
            for r in rows
        ]

    def create(
        self,
        *,
        name: str,
        target_cents: int,
        current_cents: int = 0,
        deadline_at: datetime | None = None,
        note: str | None = None,
    ) -> int:
        if target_cents <= 0:
            raise ValueError("target_cents must be > 0")
        if current_cents < 0:
            raise ValueError("current_cents must be >= 0")
        now = _now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO goals(name, target_cents, current_cents, deadline_at, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                name,
                int(target_cents),
                int(current_cents),
                _dt_to_iso(deadline_at) if deadline_at else None,
                note,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)

    def update(
        self,
        *,
        goal_id: int,
        name: str,
        target_cents: int,
        current_cents: int,
        deadline_at: datetime | None,
        note: str | None,
    ) -> None:
        if target_cents <= 0:
            raise ValueError("target_cents must be > 0")
        if current_cents < 0:
            raise ValueError("current_cents must be >= 0")
        now = _now_iso()
        self.conn.execute(
            """
            UPDATE goals
            SET name=?, target_cents=?, current_cents=?, deadline_at=?, note=?, updated_at=?
            WHERE id=?;
            """,
            (
                name,
                int(target_cents),
                int(current_cents),
                _dt_to_iso(deadline_at) if deadline_at else None,
                note,
                now,
                int(goal_id),
            ),
        )

    def delete(self, *, goal_id: int) -> None:
        self.conn.execute("DELETE FROM goals WHERE id=?;", (int(goal_id),))


@dataclass(frozen=True, slots=True)
class Reminder:
    id: int
    name: str
    due_at: datetime
    recurrence: str = "none"  # none|daily|weekly|monthly
    amount_cents: int | None = None
    note: str | None = None


def _add_months(dt: datetime, months: int) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("dt must be timezone-aware")
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1

    # Clamp day to last day of month.
    if m == 12:
        first_next = datetime(y + 1, 1, 1, tzinfo=dt.tzinfo)
    else:
        first_next = datetime(y, m + 1, 1, tzinfo=dt.tzinfo)
    last_day = (first_next - timedelta(days=1)).day
    day = min(dt.day, last_day)
    return datetime(y, m, day, dt.hour, dt.minute, dt.second, tzinfo=dt.tzinfo)


class ReminderRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_due_sorted(self) -> list[Reminder]:
        rows = self.conn.execute(
            """
            SELECT id, name, amount_cents, due_at, recurrence, note
            FROM reminders
            ORDER BY due_at ASC, id DESC;
            """
        ).fetchall()
        return [
            Reminder(
                id=int(r["id"]),
                name=str(r["name"]),
                amount_cents=int(r["amount_cents"]) if r["amount_cents"] is not None else None,
                due_at=_dt_from_iso(r["due_at"]),
                recurrence=str(r["recurrence"]),
                note=r["note"],
            )
            for r in rows
        ]

    def create(
        self,
        *,
        name: str,
        due_at: datetime,
        recurrence: str = "none",
        amount_cents: int | None = None,
        note: str | None = None,
    ) -> int:
        if not name.strip():
            raise ValueError("name must be non-empty")
        if due_at.tzinfo is None:
            raise ValueError("due_at must be timezone-aware")
        if recurrence not in {"none", "daily", "weekly", "monthly"}:
            raise ValueError("invalid recurrence")
        if amount_cents is not None and amount_cents < 0:
            raise ValueError("amount_cents must be >= 0")
        now = _now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO reminders(name, amount_cents, due_at, recurrence, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (name.strip(), amount_cents, _dt_to_iso(due_at), recurrence, note, now, now),
        )
        return int(cur.lastrowid)

    def delete(self, *, reminder_id: int) -> None:
        self.conn.execute("DELETE FROM reminders WHERE id=?;", (int(reminder_id),))

    def mark_done(self, *, reminder_id: int) -> None:
        row = self.conn.execute(
            "SELECT due_at, recurrence FROM reminders WHERE id=?;",
            (int(reminder_id),),
        ).fetchone()
        if row is None:
            return
        due = _dt_from_iso(row["due_at"])
        rec = str(row["recurrence"])
        now = _now_iso()

        if rec == "none":
            self.delete(reminder_id=reminder_id)
            return
        if rec == "daily":
            next_due = due + timedelta(days=1)
        elif rec == "weekly":
            next_due = due + timedelta(days=7)
        elif rec == "monthly":
            next_due = _add_months(due, 1)
        else:
            raise ValueError("invalid recurrence")

        self.conn.execute(
            "UPDATE reminders SET due_at=?, updated_at=? WHERE id=?;",
            (_dt_to_iso(next_due), now, int(reminder_id)),
        )
