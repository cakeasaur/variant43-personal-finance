from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # Use DELETE journal mode (not WAL) for the temporary plaintext DB.
    # WAL creates sidecar files (*-wal, *-shm) that persist on disk even after
    # the main file is closed and re-encrypted, leaking plaintext data in the
    # temp directory. DELETE mode writes all changes directly to the main file —
    # no sidecar files, no plaintext leak after encryption.
    conn.execute("PRAGMA journal_mode = DELETE;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if conn.in_transaction:
        yield conn
        return
    try:
        conn.execute("BEGIN;")
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK;")
        raise
