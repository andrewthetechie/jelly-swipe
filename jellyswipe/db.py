"""Synchronous SQLite runtime helpers for Jelly Swipe."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = None


def configure_sqlite_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Apply runtime SQLite settings required by the current sync code paths."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_sqlite_wal_mode(db_path: str | None = None) -> None:
    """Set WAL mode for the configured database file."""
    path = db_path or DB_PATH
    if not path:
        raise RuntimeError("DB_PATH is not configured")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")


def get_db():
    """Get a configured runtime connection."""
    if not DB_PATH:
        raise RuntimeError("DB_PATH is not configured")

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return configure_sqlite_connection(conn)


@contextmanager
def get_db_closing():
    """Get a database connection that auto-closes on context exit."""
    conn = get_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def cleanup_orphan_swipes() -> None:
    """Delete swipe rows whose room no longer exists."""
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
        )


def cleanup_expired_auth_sessions() -> None:
    """Delete auth session rows older than 14 days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM auth_sessions WHERE created_at < ?",
            (cutoff,),
        )


def prepare_runtime_database() -> None:
    """Apply runtime-only DB setup after schema migrations have already run."""
    ensure_sqlite_wal_mode()
    cleanup_orphan_swipes()
    cleanup_expired_auth_sessions()
