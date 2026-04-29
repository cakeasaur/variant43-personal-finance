from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK(kind IN ('income','expense','both')) DEFAULT 'both',
            color TEXT NULL,
            icon TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
            occurred_at TEXT NOT NULL,
            category_id INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL,
            note TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            target_cents INTEGER NOT NULL CHECK(target_cents > 0),
            current_cents INTEGER NOT NULL CHECK(current_cents >= 0) DEFAULT 0,
            deadline_at TEXT NULL,
            note TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            amount_cents INTEGER NULL CHECK(amount_cents >= 0),
            due_at TEXT NOT NULL,
            recurrence TEXT NOT NULL CHECK(recurrence IN ('none','daily','weekly','monthly')) DEFAULT 'none',
            note TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_transactions_occurred_at ON transactions(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_transactions_category_occurred ON transactions(category_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_transactions_type_occurred ON transactions(type, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_goals_deadline ON goals(deadline_at);
        CREATE INDEX IF NOT EXISTS idx_reminders_due_at ON reminders(due_at);
        CREATE INDEX IF NOT EXISTS idx_reminders_recurrence_due_at ON reminders(recurrence, due_at);
        """
    )
    conn.execute(
        "INSERT INTO settings(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
        (str(SCHEMA_VERSION),),
    )

