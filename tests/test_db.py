"""Migration-focused database tests for Phase 36."""

from __future__ import annotations

import sqlite3

import jellyswipe.db
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head


def _migrate(db_path: str) -> sqlite3.Connection:
    upgrade_to_head(build_sqlite_url(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestAlembicBaseline:
    def test_upgrade_head_creates_expected_tables(self, db_path):
        conn = _migrate(db_path)
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            assert "rooms" in tables
            assert "swipes" in tables
            assert "matches" in tables
            assert "auth_sessions" in tables
            assert "user_tokens" not in tables
        finally:
            conn.close()

    def test_rooms_table_has_phase36_columns_and_defaults(self, db_path):
        conn = _migrate(db_path)
        try:
            columns = {
                row["name"]: row
                for row in conn.execute("PRAGMA table_info(rooms)").fetchall()
            }
            assert set(columns) == {
                "pairing_code",
                "movie_data",
                "ready",
                "current_genre",
                "solo_mode",
                "last_match_data",
                "deck_position",
                "deck_order",
            }
            assert columns["movie_data"]["dflt_value"] in ("'[]'", '"[]"', "[]")
            assert columns["ready"]["dflt_value"] in ("0", "'0'")
            assert columns["current_genre"]["dflt_value"] in ("'All'", '"All"')
            assert columns["solo_mode"]["dflt_value"] in ("0", "'0'")
        finally:
            conn.close()

    def test_auth_sessions_table_has_expected_columns(self, db_path):
        conn = _migrate(db_path)
        try:
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(auth_sessions)").fetchall()]
            assert columns == [
                "session_id",
                "jellyfin_token",
                "jellyfin_user_id",
                "created_at",
            ]
        finally:
            conn.close()

    def test_swipes_has_foreign_keys_and_indexes(self, db_path):
        conn = _migrate(db_path)
        try:
            fk_rows = conn.execute("PRAGMA foreign_key_list(swipes)").fetchall()
            fk_targets = sorted((row["table"], row["from"], row["to"]) for row in fk_rows)
            assert fk_targets == [
                ("auth_sessions", "session_id", "session_id"),
                ("rooms", "room_code", "pairing_code"),
            ]

            indexes = {row["name"] for row in conn.execute("PRAGMA index_list(swipes)").fetchall()}
            assert "ix_swipes_room_movie_direction" in indexes
            assert "ix_swipes_room_movie_session" in indexes
        finally:
            conn.close()

    def test_matches_keeps_unique_constraint_without_room_fk(self, db_path):
        conn = _migrate(db_path)
        try:
            indexes = conn.execute("PRAGMA index_list(matches)").fetchall()
            unique_indexes = [row["name"] for row in indexes if row["unique"] == 1]
            assert unique_indexes, "matches unique constraint missing"
            assert conn.execute("PRAGMA foreign_key_list(matches)").fetchall() == []
        finally:
            conn.close()

    def test_migrated_schema_supports_current_room_and_match_inserts(self, db_path):
        conn = _migrate(db_path)
        try:
            conn.execute("INSERT INTO rooms (pairing_code) VALUES (?)", ("ROOM1",))
            conn.execute(
                "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
                ("sid-1", "token", "user-1", "2026-05-05T00:00:00+00:00"),
            )
            conn.execute(
                "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)",
                ("ROOM1", "movie-1", "user-1", "right", "sid-1"),
            )
            conn.execute(
                "INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                ("ROOM1", "movie-1", "Movie", "thumb.jpg", "active", "user-1"),
            )
            conn.commit()

            room = conn.execute("SELECT movie_data, ready, current_genre, solo_mode FROM rooms WHERE pairing_code = ?", ("ROOM1",)).fetchone()
            assert room["movie_data"] == "[]"
            assert room["ready"] == 0
            assert room["current_genre"] == "All"
            assert room["solo_mode"] == 0
        finally:
            conn.close()

    def test_upgrade_head_is_safe_on_current_database(self, db_path):
        upgrade_to_head(build_sqlite_url(db_path))
        upgrade_to_head(build_sqlite_url(db_path))

        conn = sqlite3.connect(db_path)
        try:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            assert "rooms" in tables
            assert "auth_sessions" in tables
        finally:
            conn.close()


class TestRuntimeHelpersStillAvailable:
    def test_db_module_still_exports_runtime_entrypoints(self):
        assert hasattr(jellyswipe.db, "get_db")
        assert hasattr(jellyswipe.db, "get_db_closing")
        assert hasattr(jellyswipe.db, "init_db")
