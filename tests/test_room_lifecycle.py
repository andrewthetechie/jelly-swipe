"""Room lifecycle service tests (Phase 39 plan 02)."""

from __future__ import annotations

import json

import jellyswipe.db
import jellyswipe.db_runtime
import pytest
from sqlalchemy import update
from jellyswipe.db_runtime import build_async_sqlite_url, dispose_runtime, get_sessionmaker, initialize_runtime
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


async def force_create_room(svc: RoomLifecycleService, prov: FakeProvider, user_id: str, uow) -> str:
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
        assert any(isinstance(r, MatchRecord) and r.room_code == "HISTORY" for r in archived)


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

        lm = {"type": "match", "ts": 999.9}
        await session.execute(
            update(Room).where(Room.pairing_code == pc).values(last_match_data=json.dumps(lm))
        )

        genre_deck = await svc.set_genre(pc, "Action", prov, uow)
        assert isinstance(genre_deck, list) and genre_deck
        rec_after = await uow.rooms.get_room(pc)
        assert rec_after is not None
        assert json.loads(rec_after.deck_position_json or "{}") == {}

        status = await svc.get_status(pc, uow)
        assert status["ready"] is False
        assert status["genre"] == "Action"
        assert status["solo"] is False
        assert status["last_match"]["ts"] == 999.9

        assert isinstance(await svc.get_matches(pc, uid, None, uow), list)
        assert isinstance(await svc.get_matches(pc, uid, "history", uow), list)

        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        missing_status = await svc.get_status("0000", uow)
        await session.commit()
    assert missing_status == {"ready": False}


@pytest.mark.anyio
async def test_mixed_deck_interleaving(runtime_sessionmaker):
    """Test that mixed deck creation interleaves movies and TV shows in round-robin fashion."""
    svc = RoomLifecycleService()
    
    class MixedDeckProvider:
        """Provider that returns interleaved movies and TV shows (simulating JellyfinLibraryProvider behavior)."""
        
        def fetch_deck(self, media_types=None, genre_name=None):
            """Return interleaved deck with both media types - simulates round-robin interleaving."""
            cards = []
            if media_types is None:
                media_types = ["movie"]
            
            # Simulate what JellyfinLibraryProvider does: fetch all, then interleave
            movie_cards = []
            tv_cards = []
            
            if "movie" in media_types:
                movie_cards = [{"id": f"movie-{i}", "title": f"Movie {i}", "media_type": "movie"} for i in range(5)]
            if "tv_show" in media_types:
                tv_cards = [{"id": f"tv-{i}", "title": f"TV Show {i}", "media_type": "tv_show"} for i in range(5)]
            
            # Round-robin interleaving (same logic as JellyfinLibraryProvider)
            if len(media_types) > 1 and movie_cards and tv_cards:
                interleaved = []
                max_len = max(len(movie_cards), len(tv_cards))
                for i in range(max_len):
                    if i < len(movie_cards):
                        interleaved.append(movie_cards[i])
                    if i < len(tv_cards):
                        interleaved.append(tv_cards[i])
                return interleaved
            
            # Single type or empty: return as-is
            return movie_cards + tv_cards
    
    prov = MixedDeckProvider()
    uid = "test-user"
    
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        # Create room with both media types
        sess: dict = {}
        out = await svc.create_room(sess, uid, prov, uow, include_movies=True, include_tv_shows=True)
        pc = out["pairing_code"]
        
        rec = await uow.rooms.get_room(pc)
        assert rec is not None
        
        # Verify room configuration
        assert rec.include_movies is True
        assert rec.include_tv_shows is True
        
        # Verify deck is interleaved (movie, tv, movie, tv, ...)
        deck = json.loads(rec.movie_data_json)
        assert len(deck) == 10  # 5 movies + 5 TV shows
        
        # Check round-robin pattern: even indices are movies, odd are TV shows
        for i in range(len(deck)):
            if i % 2 == 0:
                assert deck[i]["media_type"] == "movie", f"Expected movie at index {i}, got {deck[i]['media_type']}"
            else:
                assert deck[i]["media_type"] == "tv_show", f"Expected tv_show at index {i}, got {deck[i]['media_type']}"
        
        await session.commit()


@pytest.mark.anyio
async def test_single_media_type_deck(runtime_sessionmaker):
    """Test that single media type decks contain only that type."""
    svc = RoomLifecycleService()
    
    class SingleTypeProvider:
        def fetch_deck(self, media_types=None, genre_name=None):
            if media_types == ["movie"]:
                return [{"id": f"movie-{i}", "title": f"Movie {i}", "media_type": "movie"} for i in range(5)]
            elif media_types == ["tv_show"]:
                return [{"id": f"tv-{i}", "title": f"TV Show {i}", "media_type": "tv_show"} for i in range(5)]
            return []
    
    uid = "test-user"
    
    # Test movies only
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        prov = SingleTypeProvider()
        sess: dict = {}
        out = await svc.create_room(sess, uid, prov, uow, include_movies=True, include_tv_shows=False)
        pc = out["pairing_code"]
        
        rec = await uow.rooms.get_room(pc)
        deck = json.loads(rec.movie_data_json)
        
        assert len(deck) == 5
        assert all(item["media_type"] == "movie" for item in deck)
        assert rec.include_movies is True
        assert rec.include_tv_shows is False
        await session.commit()
    
    # Test TV shows only
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        prov = SingleTypeProvider()
        sess: dict = {}
        out = await svc.create_room(sess, uid, prov, uow, include_movies=False, include_tv_shows=True)
        pc = out["pairing_code"]
        
        rec = await uow.rooms.get_room(pc)
        deck = json.loads(rec.movie_data_json)
        
        assert len(deck) == 5
        assert all(item["media_type"] == "tv_show" for item in deck)
        assert rec.include_movies is False
        assert rec.include_tv_shows is True
        await session.commit()


@pytest.mark.anyio
async def test_empty_genre_validation(runtime_sessionmaker):
    """Test that empty genre deck raises ValueError (returns 400)."""
    svc = RoomLifecycleService()
    
    class EmptyGenreProvider:
        def fetch_deck(self, media_types=None, genre_name=None):
            # Return empty list when genre is specified
            if genre_name:
                return []
            return [{"id": "movie-1", "title": "Movie 1", "media_type": "movie"}]
    
    prov = EmptyGenreProvider()
    uid = "test-user"
    
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        sess: dict = {}
        out = await svc.create_room(sess, uid, prov, uow)
        pc = out["pairing_code"]
        
        # Setting a genre that returns empty deck should raise ValueError
        with pytest.raises(ValueError, match="No items found for genre"):
            await svc.set_genre(pc, "EmptyGenre", prov, uow)
        
        await session.commit()
