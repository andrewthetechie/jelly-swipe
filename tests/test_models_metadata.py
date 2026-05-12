"""Metadata-level tests for the declarative model graph."""

from jellyswipe.models.metadata import target_metadata


def test_target_metadata_contains_phase36_tables():
    assert sorted(target_metadata.tables.keys()) == [
        "auth_sessions",
        "matches",
        "rooms",
        "session_events",
        "session_instances",
        "swipes",
        "tmdb_cache",
    ]


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
