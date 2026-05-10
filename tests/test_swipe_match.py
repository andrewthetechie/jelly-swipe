"""Service-level swipe/match mutation coverage — Phase 39-03."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import jellyswipe.db
import pytest

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.auth_session import AuthSession
from jellyswipe.services.swipe_match import SwipeMatchService


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", None)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


async def _auth_session(
    runtime_sessionmaker, session_id: str, *, jellyfin_user_id: str = "verified-user"
):
    iso = datetime.now(timezone.utc).isoformat()
    async with runtime_sessionmaker() as session:
        session.add(
            AuthSession(
                session_id=session_id,
                jellyfin_token="tok",
                jellyfin_user_id=jellyfin_user_id,
                created_at=iso,
            )
        )
        await session.commit()


async def _seed_shared_room(
    runtime_sessionmaker, *, code: str = "ROOM1", deck: dict | None = None
):
    deck_json = json.dumps(deck or {"user-A": 0, "user-B": 0})
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.rooms.create(
            code,
            movie_data_json="[]",
            ready=True,
            current_genre="All",
            solo_mode=False,
            deck_position_json=deck_json,
        )
        await uow.session_instances.create(instance_id="inst-room1", pairing_code=code)
        await session.commit()


async def _seed_solo_room(
    runtime_sessionmaker, *, code: str = "SOLO1", deck: dict | None = None
):
    deck_json = json.dumps(deck or {"user-A": 0})
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.rooms.create(
            code,
            movie_data_json="[]",
            ready=True,
            current_genre="All",
            solo_mode=True,
            deck_position_json=deck_json,
        )
        await uow.session_instances.create(instance_id="inst-solo1", pairing_code=code)
        await session.commit()


@pytest.mark.anyio
class TestSwipeMatchService:
    # TODO(ORCH-001): Migrate to test session events instead of last_match_data
    # async def test_dual_right_swipe_sets_last_match_ts_as_sqlite_rowid(self, runtime_sessionmaker):
    #     svc = SwipeMatchService()
    #     await _seed_shared_room(runtime_sessionmaker)
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         result = await svc.swipe(
    #             code="ROOM1",
    #             request_session={"session_id": "sess-a"},
    #             user_id="user-A",
    #             movie_id="m1",
    #             direction="right",
    #             title="Movie",
    #             thumb="/t.jpg",
    #             uow=uow,
    #         )
    #         assert result is None
    #         await session.commit()
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         rec = await uow.rooms.get_room("ROOM1")
    #         assert rec is not None and rec.last_match_data_json is not None
    #         lm = json.loads(rec.last_match_data_json)
    #         assert lm["media_id"] == "m1"
    #         assert isinstance(lm["ts"], int)
    pass

    # TODO(ORCH-001): Migrate to test session events instead of last_match_data
    # async def test_undo_swipe_recomputes_last_match_when_peer_match_survives(self, runtime_sessionmaker):
    #     svc = SwipeMatchService()
    #     await _seed_shared_room(runtime_sessionmaker)
    #
    #     async with runtime_sessionmaker() as session:
    #         session.add(
    #             Swipe(
    #                 room_code="ROOM1",
    #                 movie_id="m1",
    #                 user_id="user-B",
    #                 direction="right",
    #                 session_id=None,
    #             )
    #         )
    #         await session.commit()
    #
    #     await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         await svc.swipe(
    #             code="ROOM1",
    #             request_session={"session_id": "sess-a"},
    #             user_id="user-A",
    #             movie_id="m1",
    #             direction="right",
    #             title="Movie",
    #             thumb="/t.jpg",
    #             uow=uow,
    #         )
    #         await session.commit()
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         before = json.loads((await uow.rooms.get_room("ROOM1")).last_match_data_json or "{}")
    #         assert before["media_id"] == "m1"
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         out = await svc.undo_swipe(
    #             code="ROOM1",
    #             request_session={"session_id": "sess-a"},
    #             user_id="user-A",
    #             movie_id="m1",
    #             uow=uow,
    #         )
    #         assert out["status"] == "undone"
    #         await session.commit()
    #
    #     async with runtime_sessionmaker() as session:
    #         uow = DatabaseUnitOfWork(session)
    #         rec = await uow.rooms.get_room("ROOM1")
    #         survivor = await uow.matches.latest_active_for_room("ROOM1")
    #         assert survivor is not None
    #         lm = json.loads(rec.last_match_data_json or "{}")
    #         assert lm["media_id"] == "m1"
    #         assert lm["ts"] == survivor.match_order
    pass

    async def test_same_jellyfin_user_separate_sessions_can_match_via_service(
        self, runtime_sessionmaker
    ):
        svc = SwipeMatchService()
        await _seed_shared_room(runtime_sessionmaker, deck={"verified-user": 0})

        uid = "verified-user"
        await _auth_session(runtime_sessionmaker, "tab-a", jellyfin_user_id=uid)
        await _auth_session(runtime_sessionmaker, "tab-b", jellyfin_user_id=uid)

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="ROOM1",
                request_session={"session_id": "tab-a"},
                user_id=uid,
                movie_id="m-shared",
                direction="right",
                title="Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="ROOM1",
                request_session={"session_id": "tab-b"},
                user_id=uid,
                movie_id="m-shared",
                direction="right",
                title="Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            rows = await uow.matches.list_active_for_user("ROOM1", uid)
            assert len(rows) == 1

    async def test_solo_right_swipe_inserts_match_found_event(
        self, runtime_sessionmaker
    ):
        """Test that a solo right-swipe inserts a match_found event into session_events."""
        svc = SwipeMatchService()
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="SOLO1",
                request_session={"session_id": "sess-a"},
                user_id="user-A",
                movie_id="m1",
                direction="right",
                title="Test Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-solo1", after_event_id=0)
            assert len(events) == 1
            event = events[0]
            assert event.event_type == "match_found"
            payload = json.loads(event.payload_json)
            assert payload["media_id"] == "m1"
            assert payload["title"] == "Test Movie"
            assert payload["thumb"] == "/t.jpg"
            assert payload["media_type"] == "movie"
            assert (
                payload["deep_link"] == "http://test.jellyfin.local/web/#/details?id=m1"
            )

    async def test_hosted_mutual_right_swipe_inserts_match_found_event(
        self, runtime_sessionmaker
    ):
        """Test that a mutual right-swipe in a hosted room inserts a match_found event."""
        svc = SwipeMatchService()
        await _seed_shared_room(runtime_sessionmaker, code="ROOM1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")
        await _auth_session(runtime_sessionmaker, "sess-b", jellyfin_user_id="user-B")

        # First user swipes right
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="ROOM1",
                request_session={"session_id": "sess-a"},
                user_id="user-A",
                movie_id="m1",
                direction="right",
                title="Test Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        # Second user swipes right — this triggers the match
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="ROOM1",
                request_session={"session_id": "sess-b"},
                user_id="user-B",
                movie_id="m1",
                direction="right",
                title="Test Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-room1", after_event_id=0)
            assert len(events) == 1
            event = events[0]
            assert event.event_type == "match_found"
            payload = json.loads(event.payload_json)
            assert payload["media_id"] == "m1"
            assert payload["title"] == "Test Movie"

    async def test_left_swipe_does_not_insert_event(self, runtime_sessionmaker):
        """Test that a left-swipe does NOT insert any event into session_events."""
        svc = SwipeMatchService()
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="SOLO1",
                request_session={"session_id": "sess-a"},
                user_id="user-A",
                movie_id="m1",
                direction="left",
                title=None,
                thumb=None,
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-solo1", after_event_id=0)
            assert len(events) == 0

    async def test_right_swipe_without_match_does_not_insert_event(
        self, runtime_sessionmaker
    ):
        """Test that a right-swipe without a counterparty does NOT insert a match_found event."""
        svc = SwipeMatchService()
        await _seed_shared_room(runtime_sessionmaker, code="ROOM1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        # First user swipes right — no match yet
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="ROOM1",
                request_session={"session_id": "sess-a"},
                user_id="user-A",
                movie_id="m1",
                direction="right",
                title="Test Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-room1", after_event_id=0)
            assert len(events) == 0

    async def test_match_found_event_session_instance_id_matches_room(
        self, runtime_sessionmaker
    ):
        """Test that the event's session_instance_id matches the active instance for the room."""
        svc = SwipeMatchService()
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await svc.swipe(
                code="SOLO1",
                request_session={"session_id": "sess-a"},
                user_id="user-A",
                movie_id="m1",
                direction="right",
                title="Test Movie",
                thumb="/t.jpg",
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-solo1", after_event_id=0)
            assert len(events) == 1
            # Verify the instance_id is correct by checking the session_instances table
            instance = await uow.session_instances.get_by_pairing_code("SOLO1")
            assert instance is not None
            assert instance.instance_id == "inst-solo1"

    async def test_undo_swipe_no_last_match_data_recompute(self, runtime_sessionmaker):
        """Test that undo_swipe no longer calls _recompute_last_match_for_room."""
        svc = SwipeMatchService()
        # _recompute_last_match_for_room should not exist
        assert not hasattr(svc, "_recompute_last_match_for_room") or not callable(
            getattr(svc, "_recompute_last_match_for_room", None)
        )

    async def test_delete_match_no_last_match_data_recompute(
        self, runtime_sessionmaker
    ):
        """Test that delete_match no longer calls _recompute_last_match_for_room."""
        svc = SwipeMatchService()
        # _recompute_last_match_for_room should not exist
        assert not hasattr(svc, "_recompute_last_match_for_room") or not callable(
            getattr(svc, "_recompute_last_match_for_room", None)
        )

    async def test_match_record_as_last_match_json_removed(self, runtime_sessionmaker):
        """Test that match_record_as_last_match_json is removed from the module."""
        from jellyswipe.services import swipe_match

        assert not hasattr(swipe_match, "match_record_as_last_match_json")
