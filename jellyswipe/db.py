"""Database functions for Jelly Swipe."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = None


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_closing():
    """Get a database connection that auto-closes on context exit.

    Use in route code as: with get_db_closing() as conn: ...
    """
    conn = get_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database schema and run migrations."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS rooms (pairing_code TEXT PRIMARY KEY, movie_data TEXT, ready INTEGER, current_genre TEXT, solo_mode INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS swipes (room_code TEXT, movie_id TEXT, user_id TEXT, direction TEXT, session_id TEXT)')
        conn.execute('''CREATE TABLE IF NOT EXISTS matches (
            room_code TEXT, movie_id TEXT, title TEXT, thumb TEXT,
            status TEXT DEFAULT "active", user_id TEXT,
            UNIQUE(room_code, movie_id, user_id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
            session_id TEXT PRIMARY KEY,
            jellyfin_token TEXT,
            jellyfin_user_id TEXT,
            created_at TEXT
        )''')

        cursor = conn.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in columns:
            conn.execute('ALTER TABLE matches ADD COLUMN status TEXT DEFAULT "active"')
        if 'user_id' not in columns:
            # Add user_id column for older databases
            conn.execute('ALTER TABLE matches ADD COLUMN user_id TEXT')

        # Fresh PRAGMA query for new match metadata columns (previous cursor consumed)
        cursor = conn.execute("PRAGMA table_info(matches)")
        match_cols = [col[1] for col in cursor.fetchall()]
        if 'deep_link' not in match_cols:
            conn.execute('ALTER TABLE matches ADD COLUMN deep_link TEXT')
        if 'rating' not in match_cols:
            conn.execute('ALTER TABLE matches ADD COLUMN rating TEXT')
        if 'duration' not in match_cols:
            conn.execute('ALTER TABLE matches ADD COLUMN duration TEXT')
        if 'year' not in match_cols:
            conn.execute('ALTER TABLE matches ADD COLUMN year TEXT')

        cursor = conn.execute("PRAGMA table_info(swipes)")
        sw_cols = [col[1] for col in cursor.fetchall()]
        if 'user_id' not in sw_cols:
            conn.execute('ALTER TABLE swipes ADD COLUMN user_id TEXT')
        if 'session_id' not in sw_cols:
            conn.execute('ALTER TABLE swipes ADD COLUMN session_id TEXT')

        cursor = conn.execute("PRAGMA table_info(rooms)")
        room_cols = [col[1] for col in cursor.fetchall()]
        if 'solo_mode' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN solo_mode INTEGER DEFAULT 0')
        if 'last_match_data' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN last_match_data TEXT')
        if 'deck_position' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN deck_position TEXT')
        if 'deck_order' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN deck_order TEXT')


        conn.execute('DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)')

    cleanup_expired_tokens()


def cleanup_expired_tokens():
    """Delete rows from user_tokens older than 24 hours.

    Called automatically on app startup (via init_db) and should also be
    called on every new session creation in Phase 24 (per D-03).

    Uses ISO 8601 string comparison for created_at timestamps.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with get_db() as conn:
        conn.execute(
            'DELETE FROM user_tokens WHERE created_at < ?',
            (cutoff,)
        )
