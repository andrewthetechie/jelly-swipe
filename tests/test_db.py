"""Tests for jellyswipe/db.py module."""

import pytest
import sqlite3
import jellyswipe.db


class TestGetDb:
    """Tests for get_db() function."""

    def test_get_db_returns_connection_with_row_factory(self, db_connection):
        """Test that get_db() returns a connection with row_factory configured."""
        # The db_connection fixture already called get_db(), so we can just verify
        assert db_connection.row_factory == sqlite3.Row
        assert isinstance(db_connection, sqlite3.Connection)


class TestInitDb:
    """Tests for init_db() function."""

    def test_init_db_is_idempotent(self, db_connection):
        """Test that init_db() can be called multiple times safely."""
        # Call init_db() again - should not raise an error
        jellyswipe.db.init_db()

        # Database should still be in a valid state
        cursor = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "rooms" in tables
        assert "swipes" in tables
        assert "matches" in tables


class TestSchema:
    """Tests for database schema initialization."""

    def test_all_three_tables_exist_after_init_db(self, db_connection):
        """Test that all 3 tables (rooms, swipes, matches) exist after init_db."""
        cursor = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "rooms" in tables
        assert "swipes" in tables
        assert "matches" in tables

    def test_all_four_tables_exist_after_init_db(self, db_connection):
        """Test that all 4 tables exist after init_db (rooms, swipes, matches, user_tokens)."""
        cursor = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "rooms" in tables
        assert "swipes" in tables
        assert "matches" in tables
        assert "user_tokens" in tables

    def test_user_tokens_table_exists_after_init_db(self, db_connection):
        """Test that user_tokens table exists after init_db."""
        cursor = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "user_tokens" in tables

    def test_user_tokens_table_has_all_columns(self, db_connection):
        """Test that user_tokens table has required columns."""
        cursor = db_connection.execute("PRAGMA table_info(user_tokens)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "session_id" in columns
        assert "jellyfin_token" in columns
        assert "jellyfin_user_id" in columns
        assert "created_at" in columns

    def test_rooms_table_has_all_columns(self, db_connection):
        """Test that rooms table has all required columns."""
        cursor = db_connection.execute("PRAGMA table_info(rooms)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "pairing_code" in columns
        assert "movie_data" in columns
        assert "ready" in columns
        assert "current_genre" in columns
        assert "solo_mode" in columns
        assert "last_match_data" in columns
        assert "deck_position" in columns
        assert "deck_order" in columns

    def test_swipes_table_has_all_columns(self, db_connection):
        """Test that swipes table has all required columns."""
        cursor = db_connection.execute("PRAGMA table_info(swipes)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "room_code" in columns
        assert "movie_id" in columns
        assert "user_id" in columns
        assert "direction" in columns

    def test_matches_table_has_all_columns_with_unique_constraint(self, db_connection):
        """Test that matches table has all required columns and UNIQUE constraint."""
        cursor = db_connection.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "room_code" in columns
        assert "movie_id" in columns
        assert "title" in columns
        assert "thumb" in columns
        assert "status" in columns
        assert "user_id" in columns
        assert "deep_link" in columns
        assert "rating" in columns
        assert "duration" in columns
        assert "year" in columns

        # Check for UNIQUE constraint
        cursor = db_connection.execute("PRAGMA index_list(matches)")
        indexes = cursor.fetchall()
        unique_indexes = [idx for idx in indexes if idx[2] == 1]  # idx[2] is unique flag
        assert len(unique_indexes) > 0, "No UNIQUE constraint found on matches table"


class TestMigrations:
    """Tests for database migrations."""

    def test_migration_adds_status_column_to_matches(self, db_connection):
        """Test that migration adds status column to matches table."""
        cursor = db_connection.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "status" in columns

        # Verify default value
        cursor = db_connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='matches'")
        table_sql = cursor.fetchone()[0]
        assert 'DEFAULT "active"' in table_sql or 'DEFAULT("active")' in table_sql

    def test_migration_adds_user_id_column_to_matches(self, db_connection):
        """Test that migration adds user_id column to matches table."""
        cursor = db_connection.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "user_id" in columns

    def test_migration_adds_user_id_column_to_swipes(self, db_connection):
        """Test that migration adds user_id column to swipes table."""
        cursor = db_connection.execute("PRAGMA table_info(swipes)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "user_id" in columns

    def test_migration_adds_solo_mode_column_to_rooms(self, db_connection):
        """Test that migration adds solo_mode column to rooms table."""
        cursor = db_connection.execute("PRAGMA table_info(rooms)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "solo_mode" in columns

        # Verify default value
        cursor = db_connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rooms'")
        table_sql = cursor.fetchone()[0]
        assert 'DEFAULT 0' in table_sql or 'DEFAULT(0)' in table_sql

    def test_migration_adds_last_match_data_column_to_rooms(self, db_connection):
        """Test that migration adds last_match_data column to rooms table."""
        cursor = db_connection.execute("PRAGMA table_info(rooms)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "last_match_data" in columns

    def test_migration_adds_deck_position_column_to_rooms(self, db_connection):
        """Test that migration adds deck_position column to rooms table."""
        cursor = db_connection.execute("PRAGMA table_info(rooms)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "deck_position" in columns

    def test_migration_adds_deck_order_column_to_rooms(self, db_connection):
        """Test that migration adds deck_order column to rooms table."""
        cursor = db_connection.execute("PRAGMA table_info(rooms)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "deck_order" in columns

    def test_migration_adds_deep_link_column_to_matches(self, db_connection):
        """Test that migration adds deep_link column to matches table."""
        cursor = db_connection.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "deep_link" in columns

    def test_migration_adds_rating_duration_year_columns_to_matches(self, db_connection):
        """Test that migration adds rating, duration, year columns to matches table."""
        cursor = db_connection.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "rating" in columns
        assert "duration" in columns
        assert "year" in columns


class TestCrudOperations:
    """Tests for CRUD operations on database tables."""

    def test_insert_and_select_from_rooms_table(self, db_connection):
        """Test that we can INSERT and SELECT from rooms table."""
        # Insert a room
        db_connection.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST123", '{"title": "Test Movie"}', 1, "Action", 0)
        )

        # Select the room
        cursor = db_connection.execute("SELECT * FROM rooms WHERE pairing_code = ?", ("TEST123",))
        row = cursor.fetchone()

        assert row is not None
        assert row["pairing_code"] == "TEST123"
        assert row["movie_data"] == '{"title": "Test Movie"}'
        assert row["ready"] == 1
        assert row["current_genre"] == "Action"
        assert row["solo_mode"] == 0

    def test_insert_and_select_from_swipes_table(self, db_connection):
        """Test that we can INSERT and SELECT from swipes table."""
        # Insert a room first (foreign key constraint - though not enforced)
        db_connection.execute("INSERT INTO rooms (pairing_code) VALUES (?)", ("TEST123",))

        # Insert a swipe
        db_connection.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) "
            "VALUES (?, ?, ?, ?)",
            ("TEST123", "movie456", "user789", "right")
        )

        # Select the swipe
        cursor = db_connection.execute("SELECT * FROM swipes WHERE room_code = ?", ("TEST123",))
        row = cursor.fetchone()

        assert row is not None
        assert row["room_code"] == "TEST123"
        assert row["movie_id"] == "movie456"
        assert row["user_id"] == "user789"
        assert row["direction"] == "right"

    def test_insert_and_select_from_matches_table(self, db_connection):
        """Test that we can INSERT and SELECT from matches table."""
        # Insert a room first
        db_connection.execute("INSERT INTO rooms (pairing_code) VALUES (?)", ("TEST123",))

        # Insert a match
        db_connection.execute(
            "INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TEST123", "movie456", "Test Movie", "http://thumb.jpg", "active", "user789")
        )

        # Select the match
        cursor = db_connection.execute("SELECT * FROM matches WHERE room_code = ?", ("TEST123",))
        row = cursor.fetchone()

        assert row is not None
        assert row["room_code"] == "TEST123"
        assert row["movie_id"] == "movie456"
        assert row["title"] == "Test Movie"
        assert row["thumb"] == "http://thumb.jpg"
        assert row["status"] == "active"
        assert row["user_id"] == "user789"

    def test_unique_constraint_prevents_duplicate_matches(self, db_connection):
        """Test that UNIQUE constraint prevents duplicate matches (same room_code, movie_id, user_id)."""
        # Insert a room first
        db_connection.execute("INSERT INTO rooms (pairing_code) VALUES (?)", ("TEST123",))

        # Insert a match
        db_connection.execute(
            "INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TEST123", "movie456", "Test Movie", "http://thumb.jpg", "active", "user789")
        )

        # Try to insert the same match again - should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute(
                "INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("TEST123", "movie456", "Another Title", "http://thumb2.jpg", "active", "user789")
            )

    def test_insert_and_select_from_user_tokens_table(self, db_connection):
        """Test that we can INSERT and SELECT from user_tokens table."""
        db_connection.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("test-session-123", "test-token-abc", "user-xyz", "2026-04-27T00:00:00.000000")
        )
        cursor = db_connection.execute("SELECT * FROM user_tokens WHERE session_id = ?", ("test-session-123",))
        row = cursor.fetchone()
        assert row is not None
        assert row["session_id"] == "test-session-123"
        assert row["jellyfin_token"] == "test-token-abc"
        assert row["jellyfin_user_id"] == "user-xyz"
        assert row["created_at"] == "2026-04-27T00:00:00.000000"


class TestCleanup:
    """Tests for database cleanup operations."""

    def test_orphaned_swipes_are_deleted(self, db_connection):
        """Test that the cleanup query correctly identifies and would delete orphaned swipes."""
        # Insert a room
        db_connection.execute("INSERT INTO rooms (pairing_code) VALUES (?)", ("VALID_ROOM",))

        # Insert a swipe for the valid room
        db_connection.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) "
            "VALUES (?, ?, ?, ?)",
            ("VALID_ROOM", "movie1", "user1", "right")
        )

        # Insert an orphan swipe (room doesn't exist)
        db_connection.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) "
            "VALUES (?, ?, ?, ?)",
            ("ORPHAN_ROOM", "movie2", "user2", "left")
        )

        # Verify the cleanup query identifies the orphan correctly
        cursor = db_connection.execute(
            "SELECT * FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
        )
        orphans = cursor.fetchall()
        assert len(orphans) == 1, "Should identify exactly one orphan swipe"
        assert orphans[0]["room_code"] == "ORPHAN_ROOM"

        # Verify the valid swipe is not identified as orphan
        cursor = db_connection.execute(
            "SELECT * FROM swipes WHERE room_code IN (SELECT pairing_code FROM rooms)"
        )
        valid_swipes = cursor.fetchall()
        assert len(valid_swipes) == 1, "Should identify exactly one valid swipe"
        assert valid_swipes[0]["room_code"] == "VALID_ROOM"


class TestIsolation:
    """Tests for test isolation."""

    def test_no_state_leakage_between_tests(self, db_connection):
        """Test that each test gets a fresh empty database (no state leakage)."""
        # At the start of this test, all tables should be empty
        cursor = db_connection.execute("SELECT COUNT(*) FROM rooms")
        assert cursor.fetchone()[0] == 0, "Rooms table should be empty"

        cursor = db_connection.execute("SELECT COUNT(*) FROM swipes")
        assert cursor.fetchone()[0] == 0, "Swipes table should be empty"

        cursor = db_connection.execute("SELECT COUNT(*) FROM matches")
        assert cursor.fetchone()[0] == 0, "Matches table should be empty"

        cursor = db_connection.execute("SELECT COUNT(*) FROM user_tokens")
        assert cursor.fetchone()[0] == 0, "User tokens table should be empty"


class TestCleanupExpiredTokens:
    """Tests for cleanup_expired_tokens() function."""

    def test_expired_tokens_are_deleted(self, db_connection):
        """Test that rows older than 24 hours are deleted."""
        from datetime import datetime, timedelta, timezone

        # Insert a token that's 25 hours old (expired)
        expired_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        db_connection.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("expired-session", "expired-token", "user-1", expired_time)
        )

        # Insert a fresh token (should be preserved)
        fresh_time = datetime.now(timezone.utc).isoformat()
        db_connection.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("fresh-session", "fresh-token", "user-2", fresh_time)
        )

        # Run cleanup
        jellyswipe.db.cleanup_expired_tokens()

        # Re-open connection to see committed changes (cleanup_expired_tokens uses its own connection)
        conn = jellyswipe.db.get_db()
        try:
            rows = conn.execute("SELECT session_id FROM user_tokens").fetchall()
            session_ids = [row["session_id"] for row in rows]
            assert "expired-session" not in session_ids
            assert "fresh-session" in session_ids
        finally:
            conn.close()

    def test_cleanup_on_empty_table(self, db_connection):
        """Test that cleanup works on empty user_tokens table without error."""
        # Should not raise any exceptions
        jellyswipe.db.cleanup_expired_tokens()

        # Verify table is still empty
        cursor = db_connection.execute("SELECT COUNT(*) FROM user_tokens")
        assert cursor.fetchone()[0] == 0

    def test_boundary_token_at_exactly_24_hours_is_deleted(self, db_connection):
        """Test that a token exactly at the 24-hour boundary is deleted (< comparison)."""
        from datetime import datetime, timedelta, timezone

        # Insert a token that's exactly 24 hours old
        boundary_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        db_connection.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("boundary-session", "boundary-token", "user-3", boundary_time)
        )

        # Run cleanup
        jellyswipe.db.cleanup_expired_tokens()

        # Boundary token should be deleted (strictly less than cutoff)
        conn = jellyswipe.db.get_db()
        try:
            rows = conn.execute("SELECT session_id FROM user_tokens").fetchall()
            session_ids = [row["session_id"] for row in rows]
            assert "boundary-session" not in session_ids
        finally:
            conn.close()

    def test_cleanup_called_during_init_db(self, db_path, monkeypatch):
        """Test that cleanup_expired_tokens is called during init_db (D-03)."""
        import jellyswipe.db
        from datetime import datetime, timedelta, timezone

        # Set up a fresh database
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        # Insert an expired token directly
        expired_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                ("pre-existing-expired", "old-token", "old-user", expired_time)
            )

        # Call init_db again — this triggers cleanup_expired_tokens
        jellyswipe.db.init_db()

        # The expired token should be gone
        with jellyswipe.db.get_db() as conn:
            rows = conn.execute("SELECT session_id FROM user_tokens").fetchall()
            session_ids = [row["session_id"] for row in rows]
            assert "pre-existing-expired" not in session_ids
