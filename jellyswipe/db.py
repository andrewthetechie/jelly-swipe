"""Database functions for Jelly Swipe."""

import os
import sqlite3
from contextlib import contextmanager

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
        conn.execute('CREATE TABLE IF NOT EXISTS swipes (room_code TEXT, movie_id TEXT, user_id TEXT, direction TEXT)')
        conn.execute('''CREATE TABLE IF NOT EXISTS matches (
            room_code TEXT, movie_id TEXT, title TEXT, thumb TEXT,
            status TEXT DEFAULT "active", user_id TEXT,
            UNIQUE(room_code, movie_id, user_id)
        )''')

        cursor = conn.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in columns:
            conn.execute('ALTER TABLE matches ADD COLUMN status TEXT DEFAULT "active"')
        if 'user_id' not in columns:
            # Add user_id column for older databases
            conn.execute('ALTER TABLE matches ADD COLUMN user_id TEXT')

        cursor = conn.execute("PRAGMA table_info(swipes)")
        sw_cols = [col[1] for col in cursor.fetchall()]
        if 'user_id' not in sw_cols:
            # Add user_id column for older databases
            conn.execute('ALTER TABLE swipes ADD COLUMN user_id TEXT')

        cursor = conn.execute("PRAGMA table_info(rooms)")
        room_cols = [col[1] for col in cursor.fetchall()]
        if 'solo_mode' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN solo_mode INTEGER DEFAULT 0')
        if 'last_match_data' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN last_match_data TEXT')


        conn.execute('DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)')
