"""Async repository parity tests for room, swipe, and match persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.auth_session import AuthSession
from jellyswipe.models.match import Match
from jellyswipe.models.room import Room
from jellyswipe.models.swipe import Swipe
from jellyswipe.repositories.matches import MatchRecord
from jellyswipe.repositories.rooms import RoomRecord, RoomStatusSnapshot


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


@pytest.mark.anyio
class TestRoomRepository:
    async def test_create_fetch_status_round_trip_last_match(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            deck = json.dumps({"u1": 0})
            await uow.rooms.create(
                "4242",
                movie_data_json="[]",
                ready=False,
                current_genre="All",
                solo_mode=False,
                deck_position_json=deck,
            )
            await session.execute(
                update(Room)
                .where(Room.pairing_code == "4242")
                .values(
                    ready=1,
                    solo_mode=1,
                    current_genre="Action",
                )
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            snapshot = await uow.rooms.fetch_status("4242")
            record = await uow.rooms.get_room("4242")

        assert snapshot is not None
        assert isinstance(snapshot, RoomStatusSnapshot)
        assert snapshot.ready is True
        assert snapshot.genre == "Action"
        assert snapshot.solo is True

        assert record is not None
        assert isinstance(record, RoomRecord)
        assert record.pairing_code == "4242"
        assert record.ready is True
        assert record.solo_mode is True
        assert record.current_genre == "Action"
        assert isinstance(record, RoomRecord)
        assert record.pairing_code == "4242"
        assert record.ready is True
        assert record.solo_mode is True
        assert record.current_genre == "Action"
        assert record.movie_data_json == "[]"
        assert record.deck_position_json == deck

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            exists = await uow.rooms.pairing_code_exists("4242")
            assert exists is True

            n = await uow.rooms.set_genre_and_deck(
                "4242", "Comedy", "{}", json.dumps({"u1": 3})
            )
            assert n == 1
            md = await uow.rooms.fetch_movie_data("4242")
            assert md == "{}"
            await session.commit()

    async def test_create_with_media_type_fields(self, runtime_sessionmaker):
        """Test that RoomRepository.create() persists include_movies and include_tv_shows."""
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "MEDIA_TEST",
                movie_data_json="[]",
                ready=False,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
                include_movies=False,
                include_tv_shows=True,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.rooms.get_room("MEDIA_TEST")

        assert record is not None
        assert record.include_movies is False
        assert record.include_tv_shows is True

        # Also test default values (movies-only)
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "DEFAULT_TEST",
                movie_data_json="[]",
                ready=False,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.rooms.get_room("DEFAULT_TEST")

        assert record is not None
        assert record.include_movies is True
        assert record.include_tv_shows is False

    async def test_list_swiped_media_ids(self, runtime_sessionmaker):
        """Test that list_swiped_media_ids returns correct swiped media IDs."""
        # Create room
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "TEST123",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            # Add swipes for room TEST123
            session.add_all(
                [
                    Swipe(
                        room_code="TEST123",
                        movie_id="mv1",
                        user_id="user-a",
                        direction="right",
                    ),
                    Swipe(
                        room_code="TEST123",
                        movie_id="mv2",
                        user_id="user-b",
                        direction="left",
                    ),
                    Swipe(
                        room_code="TEST123",
                        movie_id="mv3",
                        user_id="user-a",
                        direction="right",
                    ),
                ]
            )
            # Add swipes for a different room (should not be included)
            await uow.rooms.create(
                "OTHER456",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            session.add(
                Swipe(
                    room_code="OTHER456",
                    movie_id="mv4",
                    user_id="user-c",
                    direction="right",
                )
            )
            await session.commit()

        # Test: returns all swiped media IDs for the room
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            swiped_ids = await uow.swipes.list_swiped_media_ids("TEST123")
        assert swiped_ids == {"mv1", "mv2", "mv3"}

        # Test: returns empty set for room with no swipes
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "EMPTY789",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            empty_swiped = await uow.swipes.list_swiped_media_ids("EMPTY789")
        assert empty_swiped == set()

        # Test: does not include swipes from other rooms
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            other_room_ids = await uow.swipes.list_swiped_media_ids("OTHER456")
        assert other_room_ids == {"mv4"}
        assert "mv1" not in other_room_ids
        assert "mv2" not in other_room_ids
        assert "mv3" not in other_room_ids


@pytest.mark.anyio
class TestMatchRepository:
    async def test_active_history_latest_and_archive(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "9999",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json=json.dumps({"a": 0}),
            )
            session.add_all(
                [
                    Match(
                        room_code="9999",
                        movie_id="m-old",
                        title="Older",
                        thumb="/t-old",
                        status="active",
                        user_id="user-1",
                        deep_link="/old",
                        rating="8",
                        duration="1h",
                        year="2020",
                    ),
                    Match(
                        room_code="9999",
                        movie_id="m-new",
                        title="Newer",
                        thumb="/t-new",
                        status="active",
                        user_id="user-1",
                        deep_link="/new",
                        rating="9",
                        duration="2h",
                        year="2024",
                    ),
                ]
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            latest = await uow.matches.latest_active_for_room("9999")
            assert latest is not None
            assert latest.movie_id == "m-new"
            assert isinstance(latest.match_order, int)

            newest_rowid = latest.match_order
            active_rows = await uow.matches.list_active_for_user("9999", "user-1")
            assert len(active_rows) == 2
            assert all(isinstance(r, MatchRecord) for r in active_rows)

            archived = await uow.matches.archive_active_for_room("9999")
            assert archived == 2
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            after_latest = await uow.matches.latest_active_for_room("9999")
            assert after_latest is None

            history = await uow.matches.list_history_for_user("user-1")
            assert len(history) == 2
            newer = next(r for r in history if r.movie_id == "m-new")
            older_match = next(r for r in history if r.movie_id == "m-old")

            assert newer.status == "archived"
            assert older_match.status == "archived"
            assert newer.room_code == "HISTORY"
            assert older_match.room_code == "HISTORY"

            assert isinstance(newer.match_order, int)
            assert isinstance(older_match.match_order, int)
            assert newer.match_order > older_match.match_order
            assert newer.match_order == newest_rowid


@pytest.mark.anyio
class TestSwipeRepository:
    async def test_find_other_right_swipe_session_and_user_fallback(
        self, runtime_sessionmaker
    ):
        sid_a = "session-a"
        sid_b = "session-b"
        now = datetime.now(timezone.utc).isoformat()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "7777",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            session.add_all(
                [
                    AuthSession(
                        session_id=sid_a,
                        jellyfin_token="ta",
                        jellyfin_user_id="user-a",
                        created_at=now,
                    ),
                    AuthSession(
                        session_id=sid_b,
                        jellyfin_token="tb",
                        jellyfin_user_id="user-b",
                        created_at=now,
                    ),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    Swipe(
                        room_code="7777",
                        movie_id="mv1",
                        user_id="user-a",
                        direction="right",
                        session_id=sid_a,
                    ),
                    Swipe(
                        room_code="7777",
                        movie_id="mv1",
                        user_id="user-b",
                        direction="right",
                        session_id=sid_b,
                    ),
                ]
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            cp = await uow.swipes.find_other_right_swipe(
                pairing_code="7777",
                movie_id="mv1",
                user_id="user-a",
                session_id=sid_a,
            )

        assert cp is not None
        assert cp.user_id == "user-b"
        assert cp.session_id == sid_b

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "7788",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=False,
                deck_position_json="{}",
            )
            session.add_all(
                [
                    Swipe(
                        room_code="7788",
                        movie_id="mv2",
                        user_id="user-x",
                        direction="right",
                        session_id=None,
                    ),
                    Swipe(
                        room_code="7788",
                        movie_id="mv2",
                        user_id="user-y",
                        direction="right",
                        session_id=None,
                    ),
                ]
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            cp2 = await uow.swipes.find_other_right_swipe(
                pairing_code="7788",
                movie_id="mv2",
                user_id="user-x",
                session_id=None,
            )
            removed = await uow.swipes.delete_by_room_movie_session("7788", "mv2", None)
            await session.commit()

        assert cp2 is not None
        assert cp2.user_id == "user-y"
        assert removed == 2

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            cleared = await uow.swipes.delete_room_swipes("7777")
            await session.commit()

        assert cleared == 2
