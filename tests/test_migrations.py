"""Phase 40 / VAL-02: Alembic migration parity (fresh DB → head + subprocess idempotent)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from jellyswipe.migrations import build_sqlite_url, upgrade_to_head

REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_REVISION = "0001_phase36"


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {r[0] for r in rows}




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
        rev = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
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
        rev2 = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        assert rev2 is not None
        assert rev2[0] == _EXPECTED_REVISION
    finally:
        conn.close()
