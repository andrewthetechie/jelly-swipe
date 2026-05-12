"""SessionMatchMutation.apply_swipe tests — ORCH-027."""

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
from jellyswipe.services.session_match_mutation import (
    CatalogFacts,
    DeleteChanged,
    DeleteNoOp,
    SessionActor,
    SessionMatchMutation,
    SwipeAccepted,
    SwipeRejected,
    UndoChanged,
    UndoNoOp,
)


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


async def _seed_solo_room(
    runtime_sessionmaker,
    *,
    code: str = "SOLO1",
    deck: dict | None = None,
    movie_data: list | None = None,
):
    deck_json = json.dumps(deck or {"user-A": 0})
    movie_data_json = json.dumps(movie_data or [])
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.rooms.create(
            code,
            movie_data_json=movie_data_json,
            ready=True,
            current_genre="All",
            solo_mode=True,
            deck_position_json=deck_json,
        )
        await uow.session_instances.create(instance_id="inst-solo1", pairing_code=code)
        await session.commit()


async def _seed_hosted_room(
    runtime_sessionmaker,
    *,
    code: str = "ROOM1",
    deck: dict | None = None,
    movie_data: list | None = None,
):
    deck_json = json.dumps(deck or {"user-A": 0, "user-B": 0})
    movie_data_json = json.dumps(movie_data or [])
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.rooms.create(
            code,
            movie_data_json=movie_data_json,
            ready=True,
            current_genre="All",
            solo_mode=False,
            deck_position_json=deck_json,
        )
        await uow.session_instances.create(instance_id="inst-room1", pairing_code=code)
        await session.commit()


async def _count_swipes(session, code: str) -> int:
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT COUNT(*) FROM swipes WHERE room_code = :code"),
        {"code": code},
    )
    return result.scalar() or 0


async def _count_matches(session, code: str) -> int:
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT COUNT(*) FROM matches WHERE room_code = :code"),
        {"code": code},
    )
    return result.scalar() or 0


async def _get_deck_position(session, code: str) -> dict:
    from sqlalchemy import text

    row = (
        (
            await session.execute(
                text("SELECT deck_position FROM rooms WHERE pairing_code = :code"),
                {"code": code},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return {}
    return json.loads(row["deck_position"]) if row["deck_position"] else {}


async def _get_session_events(session, instance_id: str) -> list:
    from sqlalchemy import select

    from jellyswipe.models.session_event import SessionEvent

    result = await session.execute(
        select(SessionEvent)
        .where(SessionEvent.session_instance_id == instance_id)
        .order_by(SessionEvent.event_id.asc())
    )
    return list(result.scalars().all())


async def _get_match_for_user(session, code: str, media_id: str, user_id: str):
    from sqlalchemy import text

    row = (
        (
            await session.execute(
                text("""
            SELECT room_code, movie_id, title, thumb, status, user_id,
                   deep_link, rating, duration, year, media_type
            FROM matches
            WHERE room_code = :code AND movie_id = :media_id AND user_id = :user_id
        """),
                {"code": code, "media_id": media_id, "user_id": user_id},
            )
        )
        .mappings()
        .first()
    )
    return row


@pytest.mark.anyio
class TestApplySwipe:
    async def test_left_swipe_accepted_no_match(self, runtime_sessionmaker):
        """Left-swipe inserts Swipe row, advances cursor, returns SwipeAccepted(match_created=False)."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.apply_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                direction="left",
                catalog_facts=CatalogFacts(title=None, thumb=None),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, SwipeAccepted)
        assert result.match_created is False

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 1
            assert await _count_matches(session, "SOLO1") == 0
            events = await _get_session_events(session, "inst-solo1")
            assert len(events) == 0

    async def test_solo_right_swipe_creates_match(self, runtime_sessionmaker):
        """Solo right-swipe with title+thumb creates Match row and match_found event."""
        movie_data = [
            {
                "id": "m1",
                "title": "Test Movie",
                "rating": 8.5,
                "duration": "2h 10m",
                "year": 2024,
                "media_type": "movie",
            }
        ]
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1", movie_data=movie_data)
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.apply_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Test Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, SwipeAccepted)
        assert result.match_created is True

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 1
            match = await _get_match_for_user(session, "SOLO1", "m1", "user-A")
            assert match is not None
            assert match.title == "Test Movie"
            assert match.thumb == "/t.jpg"
            assert match.rating == "8.5"
            assert match.duration == "2h 10m"
            assert match.year == "2024"
            assert match.media_type == "movie"

            events = await _get_session_events(session, "inst-solo1")
            assert len(events) == 1
            assert events[0].event_type == "match_found"
            payload = json.loads(events[0].payload_json)
            assert payload["media_id"] == "m1"
            assert payload["title"] == "Test Movie"
            assert payload["thumb"] == "/t.jpg"
            assert payload["media_type"] == "movie"
            assert payload["rating"] == "8.5"
            assert payload["duration"] == "2h 10m"
            assert payload["year"] == "2024"
            assert (
                payload["deep_link"] == "http://test.jellyfin.local/web/#/details?id=m1"
            )

    async def test_hosted_right_swipe_no_counterparty(self, runtime_sessionmaker):
        """Hosted right-swipe without counterparty returns SwipeAccepted(match_created=False)."""
        await _seed_hosted_room(runtime_sessionmaker, code="ROOM1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="ROOM1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Test Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, SwipeAccepted)
        assert result.match_created is False

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "ROOM1") == 1
            assert await _count_matches(session, "ROOM1") == 0
            events = await _get_session_events(session, "inst-room1")
            assert len(events) == 0

    async def test_hosted_mutual_right_swipe_creates_match(self, runtime_sessionmaker):
        """Mutual right-swipe in hosted room creates Match rows for both users and one event."""
        await _seed_hosted_room(runtime_sessionmaker, code="ROOM1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")
        await _auth_session(runtime_sessionmaker, "sess-b", jellyfin_user_id="user-B")

        mutation = SessionMatchMutation()

        # First user swipes right — no match yet
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result1 = await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="ROOM1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Test Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result1, SwipeAccepted)
        assert result1.match_created is False

        # Second user swipes right — match created
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result2 = await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id="user-B", session_id="sess-b", active_room="ROOM1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Test Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result2, SwipeAccepted)
        assert result2.match_created is True

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "ROOM1") == 2
            match_a = await _get_match_for_user(session, "ROOM1", "m1", "user-A")
            match_b = await _get_match_for_user(session, "ROOM1", "m1", "user-B")
            assert match_a is not None
            assert match_b is not None

            events = await _get_session_events(session, "inst-room1")
            assert len(events) == 1
            assert events[0].event_type == "match_found"

    async def test_room_not_found_rejected(self, runtime_sessionmaker):
        """Swipe with non-existent code returns SwipeRejected."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.apply_swipe(
                code="NONEXISTENT",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room=None
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Test Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, SwipeRejected)
        assert result.reason == "room_not_found"

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 0

    async def test_cursor_advanced_after_swipe(self, runtime_sessionmaker):
        """After swipe, actor's position in deck_position is incremented by 1."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1", deck={"user-A": 0})
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await mutation.apply_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                direction="left",
                catalog_facts=CatalogFacts(title=None, thumb=None),
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            positions = await _get_deck_position(session, "SOLO1")
            assert positions == {"user-A": 1}

    async def test_cursor_advanced_independent_per_user(self, runtime_sessionmaker):
        """In hosted room, user-A swipes → user-A at 1, user-B still at 3."""
        await _seed_hosted_room(
            runtime_sessionmaker, code="ROOM1", deck={"user-A": 0, "user-B": 3}
        )
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="ROOM1"
                ),
                media_id="m1",
                direction="left",
                catalog_facts=CatalogFacts(title=None, thumb=None),
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            positions = await _get_deck_position(session, "ROOM1")
            assert positions == {"user-A": 1, "user-B": 3}

    async def test_match_metadata_derived_from_deck(self, runtime_sessionmaker):
        """Match row and event payload have derived metadata from movie_data_json."""
        movie_data = [
            {
                "id": "m1",
                "title": "Deck Movie",
                "rating": 9.0,
                "duration": "1h 45m",
                "year": 2023,
                "media_type": "tv_show",
            }
        ]
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1", movie_data=movie_data)
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await mutation.apply_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title="Catalog Title", thumb="/catalog.jpg"),
                uow=uow,
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            match = await _get_match_for_user(session, "SOLO1", "m1", "user-A")
            assert match is not None
            # Title/thumb come from CatalogFacts
            assert match.title == "Catalog Title"
            assert match.thumb == "/catalog.jpg"
            # Rating/duration/year/media_type come from deck
            assert match.rating == "9.0"
            assert match.duration == "1h 45m"
            assert match.year == "2023"
            assert match.media_type == "tv_show"

            events = await _get_session_events(session, "inst-solo1")
            assert len(events) == 1
            payload = json.loads(events[0].payload_json)
            assert payload["rating"] == "9.0"
            assert payload["duration"] == "1h 45m"
            assert payload["year"] == "2023"
            assert payload["media_type"] == "tv_show"

    async def test_right_swipe_without_catalog_facts_no_match(
        self, runtime_sessionmaker
    ):
        """Right-swipe with CatalogFacts(title=None, thumb=None) returns SwipeAccepted(match_created=False)."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _auth_session(runtime_sessionmaker, "sess-a", jellyfin_user_id="user-A")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.apply_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(title=None, thumb=None),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, SwipeAccepted)
        assert result.match_created is False

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 1
            assert await _count_matches(session, "SOLO1") == 0

    async def test_same_user_different_sessions_match(self, runtime_sessionmaker):
        """Same Jellyfin user on two sessions right-swipes same media_id → match created."""
        uid = "verified-user"
        await _seed_hosted_room(runtime_sessionmaker, code="ROOM1", deck={uid: 0})
        await _auth_session(runtime_sessionmaker, "tab-a", jellyfin_user_id=uid)
        await _auth_session(runtime_sessionmaker, "tab-b", jellyfin_user_id=uid)

        mutation = SessionMatchMutation()

        # First session swipes right
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result1 = await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id=uid, session_id="tab-a", active_room="ROOM1"
                ),
                media_id="m-shared",
                direction="right",
                catalog_facts=CatalogFacts(title="Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result1, SwipeAccepted)
        assert result1.match_created is False

        # Second session swipes right — match created
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result2 = await mutation.apply_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id=uid, session_id="tab-b", active_room="ROOM1"
                ),
                media_id="m-shared",
                direction="right",
                catalog_facts=CatalogFacts(title="Movie", thumb="/t.jpg"),
                uow=uow,
            )
            await session.commit()

        assert isinstance(result2, SwipeAccepted)
        assert result2.match_created is True

        async with runtime_sessionmaker() as session:
            match = await _get_match_for_user(session, "ROOM1", "m-shared", uid)
            assert match is not None


async def _seed_swipe(
    runtime_sessionmaker,
    *,
    code: str,
    media_id: str,
    user_id: str,
    session_id: str | None,
    direction: str = "right",
):
    from sqlalchemy import text

    # Ensure auth session exists for the FK constraint
    if session_id is not None:
        await _auth_session(runtime_sessionmaker, session_id, jellyfin_user_id=user_id)

    async with runtime_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) "
                "VALUES (:code, :media_id, :user_id, :direction, :session_id)"
            ),
            {
                "code": code,
                "media_id": media_id,
                "user_id": user_id,
                "direction": direction,
                "session_id": session_id,
            },
        )
        await session.commit()


async def _seed_match(
    runtime_sessionmaker,
    *,
    code: str,
    media_id: str,
    user_id: str,
    title: str = "Test Movie",
    thumb: str = "/t.jpg",
    status: str = "active",
):
    from sqlalchemy import text

    async with runtime_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO matches (room_code, movie_id, user_id, title, thumb, status) "
                "VALUES (:code, :media_id, :user_id, :title, :thumb, :status)"
            ),
            {
                "code": code,
                "media_id": media_id,
                "user_id": user_id,
                "title": title,
                "thumb": thumb,
                "status": status,
            },
        )
        await session.commit()


async def _count_matches_for_user(session, media_id: str, user_id: str) -> int:
    from sqlalchemy import text

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM matches WHERE movie_id = :media_id AND user_id = :user_id"
        ),
        {"media_id": media_id, "user_id": user_id},
    )
    return result.scalar() or 0


@pytest.mark.anyio
class TestUndoSwipe:
    async def test_undo_existing_swipe_returns_changed(self, runtime_sessionmaker):
        """Seed a swipe, undo it → UndoChanged(match_removed=False). Verify swipe row gone."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _seed_swipe(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
            session_id="sess-a",
        )

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.undo_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, UndoChanged)
        assert result.match_removed is False

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 0

    async def test_undo_swipe_that_created_match_removes_match(
        self, runtime_sessionmaker
    ):
        """Seed a right-swipe + match, undo → UndoChanged(match_removed=True). Verify swipe AND match rows gone."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _seed_swipe(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
            session_id="sess-a",
        )
        await _seed_match(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
        )

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.undo_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, UndoChanged)
        assert result.match_removed is True

        async with runtime_sessionmaker() as session:
            assert await _count_swipes(session, "SOLO1") == 0
            assert await _count_matches(session, "SOLO1") == 0

    async def test_undo_nonexistent_swipe_returns_noop(self, runtime_sessionmaker):
        """Undo a swipe that never happened → UndoNoOp(). No rows changed."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.undo_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m999",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, UndoNoOp)

    async def test_undo_does_not_remove_counterparty_match(self, runtime_sessionmaker):
        """Seed mutual match (two match rows), actor undoes → only actor's match row removed."""
        await _seed_hosted_room(runtime_sessionmaker, code="ROOM1")
        await _seed_swipe(
            runtime_sessionmaker,
            code="ROOM1",
            media_id="m1",
            user_id="user-A",
            session_id="sess-a",
        )
        await _seed_match(
            runtime_sessionmaker,
            code="ROOM1",
            media_id="m1",
            user_id="user-A",
        )
        await _seed_match(
            runtime_sessionmaker,
            code="ROOM1",
            media_id="m1",
            user_id="user-B",
        )

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.undo_swipe(
                code="ROOM1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="ROOM1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, UndoChanged)
        assert result.match_removed is True

        async with runtime_sessionmaker() as session:
            match_a = await _get_match_for_user(session, "ROOM1", "m1", "user-A")
            match_b = await _get_match_for_user(session, "ROOM1", "m1", "user-B")
            assert match_a is None
            assert match_b is not None


@pytest.mark.anyio
class TestDeleteMatch:
    async def test_delete_existing_match_returns_changed(self, runtime_sessionmaker):
        """Seed a match row, delete it → DeleteChanged(). Verify match row gone."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _seed_match(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
        )

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.delete_match(
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, DeleteChanged)

        async with runtime_sessionmaker() as session:
            assert await _count_matches_for_user(session, "m1", "user-A") == 0

    async def test_delete_nonexistent_match_returns_noop(self, runtime_sessionmaker):
        """Delete a match that doesn't exist → DeleteNoOp(). No rows changed."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.delete_match(
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m999",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, DeleteNoOp)

    async def test_delete_match_does_not_affect_counterparty(
        self, runtime_sessionmaker
    ):
        """Seed match rows for two users, actor deletes → only actor's match row removed."""
        await _seed_hosted_room(runtime_sessionmaker, code="ROOM1")
        await _seed_match(
            runtime_sessionmaker,
            code="ROOM1",
            media_id="m1",
            user_id="user-A",
        )
        await _seed_match(
            runtime_sessionmaker,
            code="ROOM1",
            media_id="m1",
            user_id="user-B",
        )

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.delete_match(
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="ROOM1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, DeleteChanged)

        async with runtime_sessionmaker() as session:
            match_a = await _get_match_for_user(session, "ROOM1", "m1", "user-A")
            match_b = await _get_match_for_user(session, "ROOM1", "m1", "user-B")
            assert match_a is None
            assert match_b is not None


@pytest.mark.anyio
class TestUndoAndEventStream:
    async def test_undo_does_not_emit_or_remove_events(self, runtime_sessionmaker):
        """Seed match + match_found event, undo swipe → event still exists in session_events."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _seed_swipe(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
            session_id="sess-a",
        )
        await _seed_match(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
        )

        # Seed a match_found event
        from sqlalchemy import text

        async with runtime_sessionmaker() as session:
            await session.execute(
                text(
                    "INSERT INTO session_events (session_instance_id, event_type, payload_json, created_at) "
                    "VALUES (:instance_id, 'match_found', :payload, :created_at)"
                ),
                {
                    "instance_id": "inst-solo1",
                    "payload": '{"media_id": "m1"}',
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await session.commit()

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.undo_swipe(
                code="SOLO1",
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, UndoChanged)
        assert result.match_removed is True

        async with runtime_sessionmaker() as session:
            events = await _get_session_events(session, "inst-solo1")
            assert len(events) == 1
            assert events[0].event_type == "match_found"


@pytest.mark.anyio
class TestDeleteAndEventStream:
    async def test_delete_does_not_emit_or_remove_events(self, runtime_sessionmaker):
        """Seed match + match_found event, delete match → event still exists."""
        await _seed_solo_room(runtime_sessionmaker, code="SOLO1")
        await _seed_match(
            runtime_sessionmaker,
            code="SOLO1",
            media_id="m1",
            user_id="user-A",
        )

        # Seed a match_found event
        from sqlalchemy import text

        async with runtime_sessionmaker() as session:
            await session.execute(
                text(
                    "INSERT INTO session_events (session_instance_id, event_type, payload_json, created_at) "
                    "VALUES (:instance_id, 'match_found', :payload, :created_at)"
                ),
                {
                    "instance_id": "inst-solo1",
                    "payload": '{"media_id": "m1"}',
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await session.commit()

        mutation = SessionMatchMutation()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            result = await mutation.delete_match(
                actor=SessionActor(
                    user_id="user-A", session_id="sess-a", active_room="SOLO1"
                ),
                media_id="m1",
                uow=uow,
            )
            await session.commit()

        assert isinstance(result, DeleteChanged)

        async with runtime_sessionmaker() as session:
            events = await _get_session_events(session, "inst-solo1")
            assert len(events) == 1
            assert events[0].event_type == "match_found"
