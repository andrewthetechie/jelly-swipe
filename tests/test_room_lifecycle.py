"""Room lifecycle service tests (Phase 39 plan 02)."""

from __future__ import annotations

import json

import jellyswipe.db
import jellyswipe.db_runtime
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
from jellyswipe.models.match import Match
from jellyswipe.models.room import Room
from jellyswipe.room_types import MatchRecord
from jellyswipe.services.room_lifecycle import RoomLifecycleService
from tests.conftest import FakeProvider


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


async def force_create_room(
    svc: RoomLifecycleService, prov: FakeProvider, user_id: str, uow
) -> str:
    sess: dict = {}
    out = await svc.create_room(sess, user_id, prov, uow)
    return str(out["pairing_code"])


@pytest.mark.anyio
async def test_create_and_solo_set_session_cursor_defaults(runtime_sessionmaker):
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    # Test hosted room (default behavior)
    sess_multi: dict = {}
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        out = await svc.create_room(sess_multi, uid, prov, uow)
        pc = out["pairing_code"]
        rec = await uow.rooms.get_room(pc)
        assert rec is not None
        deck = json.loads(rec.deck_position_json or "{}")
        assert deck[uid] == 0
        assert rec.ready is False
        assert rec.solo_mode is False
        assert rec.include_movies is True
        assert rec.include_tv_shows is False
        await session.commit()

    assert sess_multi["active_room"] == pc
    assert sess_multi["solo_mode"] is False

    # Test solo room
    sess_solo: dict = {}
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        out2 = await svc.create_room(sess_solo, uid, prov, uow, solo=True)
        pc2 = out2["pairing_code"]
        rec2 = await uow.rooms.get_room(pc2)
        assert rec2 is not None
        deck2 = json.loads(rec2.deck_position_json or "{}")
        assert deck2[uid] == 0
        assert rec2.ready is True
        assert rec2.solo_mode is True
        await session.commit()

    assert sess_solo["active_room"] == pc2
    assert sess_solo["solo_mode"] is True


@pytest.mark.anyio
async def test_create_room_with_mixed_media_interleaves(runtime_sessionmaker):
    """Test that when both movies and TV shows are requested, deck interleaves them."""
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    sess: dict = {}
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        out = await svc.create_room(
            sess, uid, prov, uow, include_movies=True, include_tv_shows=True
        )
        pc = out["pairing_code"]
        rec = await uow.rooms.get_room(pc)
        assert rec is not None

        deck = json.loads(rec.movie_data_json or "[]")
        assert len(deck) == 50  # 25 movies + 25 TV shows

        # Verify round-robin interleaving: movie, tv, movie, tv, ...
        for i in range(len(deck)):
            if i % 2 == 0:
                assert deck[i]["media_type"] == "movie", f"Position {i} should be movie"
            else:
                assert deck[i]["media_type"] == "tv_show", (
                    f"Position {i} should be tv_show"
                )

        assert rec.include_movies is True
        assert rec.include_tv_shows is True
        await session.commit()


@pytest.mark.anyio
async def test_create_room_with_tv_shows_only(runtime_sessionmaker):
    """Test that when only TV shows are requested, deck contains only TV shows."""
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    sess: dict = {}
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        out = await svc.create_room(
            sess, uid, prov, uow, include_movies=False, include_tv_shows=True
        )
        pc = out["pairing_code"]
        rec = await uow.rooms.get_room(pc)
        assert rec is not None

        deck = json.loads(rec.movie_data_json or "[]")
        assert len(deck) == 25
        for card in deck:
            assert card["media_type"] == "tv_show"

        assert rec.include_movies is False
        assert rec.include_tv_shows is True
        await session.commit()


@pytest.mark.anyio
async def test_join_marks_ready_and_merges_deck(runtime_sessionmaker):
    svc = RoomLifecycleService()
    prov = FakeProvider()
    creator = "user-a"
    joiner = "user-b"

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, creator, uow)
        sess_join: dict = {}
        resp = await svc.join_room(pc, sess_join, joiner, uow)
        await session.commit()

    assert resp == {"status": "success"}
    assert sess_join["active_room"] == pc
    assert sess_join["solo_mode"] is False

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        snap = await uow.rooms.fetch_status(pc)
        assert snap is not None and snap.ready is True
        rec = await uow.rooms.get_room(pc)
        assert rec is not None
        deck = json.loads(rec.deck_position_json or "{}")
        assert deck[joiner] == 0
        assert deck[creator] == 0


@pytest.mark.anyio
async def test_quit_session_ended_archives_matches_to_history(runtime_sessionmaker):
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)
        session.add(
            Match(
                room_code=pc,
                movie_id="m1",
                title="T",
                thumb="/t",
                status="active",
                user_id=uid,
                deep_link=None,
                rating="",
                duration="",
                year="",
            )
        )
        sess: dict = {"active_room": pc, "solo_mode": False}
        out = await svc.quit_room(pc, sess, uid, uow)
        await session.commit()

    assert out == {"status": "session_ended"}
    assert "active_room" not in sess
    assert "solo_mode" not in sess

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        room = await uow.rooms.get_room(pc)
        assert room is None
        archived = await uow.matches.list_history_for_user(uid)
        assert any(
            isinstance(r, MatchRecord) and r.room_code == "HISTORY" for r in archived
        )


@pytest.mark.anyio
async def test_deck_genre_status_matches_semantics(runtime_sessionmaker):
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        deck_page = await svc.get_deck(pc, uid, 1, uow)
        assert len(deck_page) == svc.page_size

        assert await svc.get_deck("9999", uid, 1, uow) == []

        genre_deck = await svc.set_genre(pc, "Action", prov, uow)
        assert isinstance(genre_deck, list) and genre_deck
        rec_after = await uow.rooms.get_room(pc)
        assert rec_after is not None
        assert json.loads(rec_after.deck_position_json or "{}") == {}

        status = await svc.get_status(pc, uow)
        assert status["ready"] is False
        assert status["genre"] == "Action"
        assert status["solo"] is False

        assert isinstance(await svc.get_matches(pc, uid, None, uow), list)
        assert isinstance(await svc.get_matches(pc, uid, "history", uow), list)

        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        missing_status = await svc.get_status("0000", uow)
        await session.commit()
    assert missing_status == {"ready": False}


@pytest.mark.anyio
async def test_fetch_status_returns_hide_watched_false_for_new_room(
    runtime_sessionmaker,
):
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        snap = await uow.rooms.fetch_status(pc)
        assert snap is not None
        assert snap.hide_watched is False



@pytest.mark.anyio
async def test_set_watched_filter_excludes_watched_items(runtime_sessionmaker):
    """Test that watched filter excludes watched items from rebuilt deck."""

    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # Initially hide_watched should be False
        snap = await uow.rooms.fetch_status(pc)
        assert snap is not None
        assert snap.hide_watched is False

        # Set watched filter to True - should rebuild deck
        new_deck = await svc.set_watched_filter(pc, True, prov, uow)
        await session.commit()

        # Verify hide_watched is now True
        snap_after = await uow.rooms.fetch_status(pc)
        assert snap_after is not None
        assert snap_after.hide_watched is True

        # Verify deck was rebuilt and cursors reset
        rec = await uow.rooms.get_room(pc)
        assert rec is not None
        assert json.loads(rec.deck_position_json or "{}") == {}
        assert isinstance(new_deck, list)
        assert len(new_deck) > 0


@pytest.mark.anyio
async def test_swipe_exclusion_on_deck_rebuild(runtime_sessionmaker):
    """Test that swiped items are excluded from rebuilt deck."""
    from jellyswipe.models.swipe import Swipe

    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # Get initial deck
        initial_deck = await svc.get_deck(pc, uid, 1, uow)
        assert len(initial_deck) > 0

        # Swipe right on first item
        first_item_id = initial_deck[0]["media_id"]
        session.add(
            Swipe(
                room_code=pc,
                movie_id=first_item_id,
                user_id=uid,
                direction="right",
                session_id=None,
            )
        )
        await session.commit()

        # Rebuild deck by changing genre
        new_deck = await svc.set_genre(pc, "Action", prov, uow)
        await session.commit()

        # Verify swiped item is excluded from new deck
        swiped_ids = await uow.swipes.list_swiped_media_ids(pc)
        assert first_item_id in swiped_ids
        for item in new_deck:
            assert item["media_id"] != first_item_id, (
                "Swiped item should be excluded from rebuilt deck"
            )


@pytest.mark.anyio
async def test_empty_deck_rollback_on_genre_change(runtime_sessionmaker):
    """Test that empty deck on genre change rolls back without state change."""
    from jellyswipe.services.room_lifecycle import EmptyDeckError

    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # Get initial state
        initial_room = await uow.rooms.get_room(pc)
        assert initial_room is not None
        initial_genre = initial_room.current_genre
        initial_deck_json = initial_room.movie_data_json
        initial_cursors = initial_room.deck_position_json

        # Mock provider to return empty deck for "Action" genre
        original_fetch = prov.fetch_deck

        def mock_fetch(media_types=None, genre_name=None, hide_watched=False):
            if genre_name == "Action":
                return []
            return original_fetch(
                media_types=media_types,
                genre_name=genre_name,
                hide_watched=hide_watched,
            )

        prov.fetch_deck = mock_fetch

        # Attempt to change genre to Action (should raise EmptyDeckError)
        with pytest.raises(EmptyDeckError):
            await svc.set_genre(pc, "Action", prov, uow)

        # Verify no state change occurred
        await session.commit()
        room_after = await uow.rooms.get_room(pc)
        assert room_after is not None
        assert room_after.current_genre == initial_genre
        assert room_after.movie_data_json == initial_deck_json
        assert room_after.deck_position_json == initial_cursors


@pytest.mark.anyio
async def test_empty_deck_rollback_on_watched_filter(runtime_sessionmaker):
    """Test that empty deck on watched filter toggle rolls back without state change."""
    from jellyswipe.services.room_lifecycle import EmptyDeckError

    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # Get initial state
        initial_room = await uow.rooms.get_room(pc)
        assert initial_room is not None
        initial_hide_watched = initial_room.hide_watched
        initial_deck_json = initial_room.movie_data_json

        # Mock provider to return empty deck when hide_watched=True
        original_fetch = prov.fetch_deck

        def mock_fetch(media_types=None, genre_name=None, hide_watched=False):
            if hide_watched:
                return []
            return original_fetch(
                media_types=media_types,
                genre_name=genre_name,
                hide_watched=hide_watched,
            )

        prov.fetch_deck = mock_fetch

        # Attempt to enable hide_watched (should raise EmptyDeckError)
        with pytest.raises(EmptyDeckError):
            await svc.set_watched_filter(pc, True, prov, uow)

        # Verify no state change occurred
        await session.commit()
        room_after = await uow.rooms.get_room(pc)
        assert room_after is not None
        assert room_after.hide_watched == initial_hide_watched
        assert room_after.movie_data_json == initial_deck_json


@pytest.mark.anyio
async def test_genre_change_with_watched_filter_active(runtime_sessionmaker):
    """Test that genre change respects active watched filter."""
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # First enable watched filter
        await svc.set_watched_filter(pc, True, prov, uow)
        await session.commit()

        # Verify hide_watched is True
        snap = await uow.rooms.fetch_status(pc)
        assert snap is not None
        assert snap.hide_watched is True

        # Change genre - should maintain watched filter
        new_deck = await svc.set_genre(pc, "Comedy", prov, uow)
        await session.commit()

        # Verify hide_watched is still True after genre change
        snap_after = await uow.rooms.fetch_status(pc)
        assert snap_after is not None
        assert snap_after.hide_watched is True
        assert snap_after.genre == "Comedy"
        assert isinstance(new_deck, list)


@pytest.mark.anyio
async def test_cursor_reset_after_deck_rebuild(runtime_sessionmaker):
    """Test that deck_position_json resets to {} after any rebuild."""
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        pc = await force_create_room(svc, prov, uid, uow)

        # Set some cursor positions
        room = await uow.rooms.get_room(pc)
        assert room is not None
        await uow.rooms.set_deck_position(pc, json.dumps({uid: 5, "other-user": 3}))
        await session.commit()

        # Verify cursors are set
        room_before = await uow.rooms.get_room(pc)
        assert room_before is not None
        cursors_before = json.loads(room_before.deck_position_json or "{}")
        assert cursors_before.get(uid) == 5

        # Rebuild deck
        await svc.set_genre(pc, "Action", prov, uow)
        await session.commit()

        # Verify cursors reset to {}
        room_after = await uow.rooms.get_room(pc)
        assert room_after is not None
        cursors_after = json.loads(room_after.deck_position_json or "{}")
        assert cursors_after == {}


@pytest.mark.anyio
async def test_solo_session_watched_filter(runtime_sessionmaker):
    """Test that watched filter works identically for solo sessions."""
    svc = RoomLifecycleService()
    prov = FakeProvider()
    uid = prov._user_id

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        # Create solo room
        sess_solo: dict = {}
        out = await svc.create_room(sess_solo, uid, prov, uow, solo=True)
        pc = out["pairing_code"]
        await session.commit()

        # Verify solo mode
        snap = await uow.rooms.fetch_status(pc)
        assert snap is not None
        assert snap.solo is True
        assert snap.hide_watched is False

        # Set watched filter
        new_deck = await svc.set_watched_filter(pc, True, prov, uow)
        await session.commit()

        # Verify hide_watched is True
        snap_after = await uow.rooms.fetch_status(pc)
        assert snap_after is not None
        assert snap_after.hide_watched is True
        assert snap_after.solo is True
        assert isinstance(new_deck, list)
        assert len(new_deck) > 0
