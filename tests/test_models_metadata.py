"""Metadata-level tests for the declarative model graph."""

import subprocess
import sys

from jellyswipe.models.metadata import target_metadata

EXPECTED_TABLES = [
    "auth_sessions",
    "matches",
    "rooms",
    "session_events",
    "session_instances",
    "swipes",
    "tmdb_cache",
]


def test_target_metadata_contains_phase36_tables():
    assert sorted(target_metadata.tables.keys()) == EXPECTED_TABLES


def test_swipes_has_room_and_auth_session_foreign_keys():
    swipes = target_metadata.tables["swipes"]
    fk_targets = sorted(
        f"{fk.column.table.name}.{fk.column.name}" for fk in swipes.foreign_keys
    )
    assert fk_targets == ["auth_sessions.session_id", "rooms.pairing_code"]


def test_matches_has_no_room_foreign_key():
    matches = target_metadata.tables["matches"]
    assert list(matches.foreign_keys) == []


def test_auth_sessions_replaces_user_tokens():
    assert "auth_sessions" in target_metadata.tables
    assert "user_tokens" not in target_metadata.tables


def test_alembic_target_metadata_isolated():
    """Regression test: verify Alembic's target_metadata is complete in isolation.

    This test launches a fresh Python interpreter that imports ONLY
    `jellyswipe.models.metadata` — mirroring Alembic's import path in
    `alembic/env.py` — and asserts all 7 tables are registered. This
    catches regressions where a model import is removed from
    `models/metadata.py`, which would cause Alembic autogenerate to
    propose destructive migrations (e.g. dropping tables).

    The in-process test `test_target_metadata_contains_phase36_tables`
    is insufficient because the full test suite imports `db_uow` and
    repositories, which transitively register all models on the shared
    `Base.metadata` before that assertion runs.
    """
    script = (
        "from jellyswipe.models.metadata import target_metadata; "
        "print(' '.join(sorted(target_metadata.tables.keys())))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    tables = result.stdout.strip().split()
    assert tables == EXPECTED_TABLES
