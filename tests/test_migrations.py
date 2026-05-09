"""Phase 40 / VAL-02: Alembic migration parity (fresh DB → head + subprocess idempotent)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


from jellyswipe.migrations import build_sqlite_url, upgrade_to_head

REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_REVISION = "0003_add_hide_watched"


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {r[0] for r in rows}


def _get_room_columns(conn: sqlite3.Connection) -> dict[str, str]:
    """Get column names and their default values for the rooms table."""
    rows = conn.execute("PRAGMA table_info(rooms)").fetchall()
    return {row[1]: row[4] for row in rows}  # column name -> default value


def test_fresh_database_upgrade_then_subprocess_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "migration_parity.db"
    url = build_sqlite_url(str(db_path))
    assert not db_path.exists(), "expected empty workspace before migration"

    upgrade_to_head(url)

    assert db_path.is_file()

    conn = sqlite3.connect(db_path)
    try:
        tables = _table_names(conn)
        for name in ("rooms", "auth_sessions", "swipes", "matches", "alembic_version"):
            assert name in tables, f"missing table {name}, have {sorted(tables)}"
        rev = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert rev is not None
        assert rev[0] == _EXPECTED_REVISION
    finally:
        conn.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    root_pp = str(REPO_ROOT)
    existing = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = root_pp if not existing else f"{root_pp}{os.pathsep}{existing}"
    cwd = str(REPO_ROOT)
    alembic = [
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
    ]
    subprocess.run(
        alembic,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        alembic,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    conn = sqlite3.connect(db_path)
    try:
        rev2 = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert rev2 is not None
        assert rev2[0] == _EXPECTED_REVISION
    finally:
        conn.close()


def test_migration_adds_media_type_columns_with_defaults(tmp_path: Path) -> None:
    """Test that migration adds include_movies and include_tv_shows columns with correct defaults."""
    db_path = tmp_path / "media_type_test.db"
    url = build_sqlite_url(str(db_path))

    # Apply migration
    upgrade_to_head(url)

    assert db_path.is_file()

    conn = sqlite3.connect(db_path)
    try:
        # Check columns exist with correct defaults
        columns = _get_room_columns(conn)
        assert "include_movies" in columns, (
            f"include_movies column missing, have {list(columns.keys())}"
        )
        assert "include_tv_shows" in columns, (
            f"include_tv_shows column missing, have {list(columns.keys())}"
        )

        # Verify defaults (SQLite stores defaults as strings)
        assert columns["include_movies"] == "1", (
            f"include_movies default is {columns['include_movies']}, expected '1'"
        )
        assert columns["include_tv_shows"] == "0", (
            f"include_tv_shows default is {columns['include_tv_shows']}, expected '0'"
        )

        # Create a room using INSERT to verify defaults work
        conn.execute(
            """
            INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode, deck_position)
            VALUES ('TEST', '[]', 0, 'All', 0, '{}')
            """
        )
        conn.commit()

        # Verify the room has correct defaults
        row = conn.execute(
            "SELECT include_movies, include_tv_shows FROM rooms WHERE pairing_code = 'TEST'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1, f"include_movies should default to 1, got {row[0]}"
        assert row[1] == 0, f"include_tv_shows should default to 0, got {row[1]}"
    finally:
        conn.close()
