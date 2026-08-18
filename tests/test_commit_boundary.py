"""Tests for the get_db_uow request boundary (transaction completion).

Covers the centralized commit/rollback/notify contract introduced by issue
#295: the boundary commits on success then wakes subscribers (commit-before-
notify preserved), rolls back on error/abort, and fails loudly rather than
logging-and-dropping when an uncommitted write path slips through.

We drive the ``get_db_uow`` async generator directly (same pattern as
``tests/test_dependencies.py``): the code after ``yield`` runs when the
generator is exhausted, so the teardown (commit/rollback/notify) executes
during the terminating ``__anext__`` call.
"""

import pytest
from sqlalchemy import select, text

from jellyswipe import dependencies as deps
from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.dependencies import get_db_uow
from jellyswipe.domain.deck import Deck
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.room import Room


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    """A temp-DB sessionmaker plus a ``bridge_rows`` table for legacy-sync tests."""
    upgrade_to_head(build_sqlite_url(db_path))
    await dispose_runtime()
    await initialize_runtime(build_async_sqlite_url(db_path))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text(
                "CREATE TABLE bridge_rows (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
        )
        await session.commit()

    yield sessionmaker
    await dispose_runtime()


async def _make_dirty_uow(session):
    """Open a UoW and write an ORM object into session.new via a repository."""
    uow = DatabaseUnitOfWork(session)
    deck = Deck.from_cards([])
    await uow.rooms.create(
        "1234",
        deck=deck,
        ready=True,
        current_genre="All",
        solo_mode=True,
        include_movies=True,
        include_tv_shows=False,
    )
    return uow


@pytest.mark.anyio
async def test_boundary_commits_before_notify(runtime_sessionmaker, monkeypatch):
    """commit is observed before notifier.notify within a single boundary run."""
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    call_order = []
    real_commit = session.commit

    async def tracked_commit():
        call_order.append("commit")
        await real_commit()

    monkeypatch.setattr(session, "commit", tracked_commit)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(deps.notifier, "notify", lambda code: call_order.append("notify"))

        generator = get_db_uow()
        uow = await generator.__anext__()
        uow.wake_on_commit("ABCD")
        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

    assert call_order == ["commit", "notify"]


@pytest.mark.anyio
async def test_boundary_wakes_declared_code(runtime_sessionmaker, monkeypatch):
    """The declared wake code is passed to notifier.notify after commit."""
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    notified = []

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(deps.notifier, "notify", lambda code: notified.append(code))
        generator = get_db_uow()
        uow = await generator.__anext__()
        uow.wake_on_commit("ABCD")
        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

    assert notified == ["ABCD"]


@pytest.mark.anyio
async def test_boundary_commit_error_propagates_without_notify(
    runtime_sessionmaker, monkeypatch
):
    """If commit raises, the boundary rolls back and notifier is NOT woken."""
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    async def failing_commit():
        raise RuntimeError("db error")

    monkeypatch.setattr(session, "commit", failing_commit)

    with pytest.MonkeyPatch.context() as mp:
        notified = []
        mp.setattr(deps.notifier, "notify", lambda code: notified.append(code))

        generator = get_db_uow()
        uow = await generator.__anext__()
        uow.wake_on_commit("WXYZ")
        with pytest.raises(RuntimeError, match="db error"):
            await generator.__anext__()

    assert notified == []


@pytest.mark.anyio
async def test_boundary_abort_rolls_back_and_does_not_notify(
    runtime_sessionmaker, monkeypatch
):
    """abort() rolls back an error-return route's writes and skips notify."""
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    with pytest.MonkeyPatch.context() as mp:
        notified = []
        mp.setattr(deps.notifier, "notify", lambda code: notified.append(code))

        generator = get_db_uow()
        uow = await generator.__anext__()
        await _make_dirty_uow(session)
        uow.wake_on_commit("ABCD")
        uow.abort()
        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

    assert notified == []

    # Data NOT persisted
    async with runtime_sessionmaker() as verify:
        rows = (await verify.scalars(select(Room.pairing_code))).all()
    assert rows == []


@pytest.mark.anyio
async def test_boundary_loud_fail_when_dirty_after_commit(
    runtime_sessionmaker, monkeypatch
):
    """A write path that the commit doesn't clear fails loudly (RuntimeError)."""
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    async def noop_commit():
        # Simulate a commit that did not persist/clear the dirty session.
        return None

    monkeypatch.setattr(session, "commit", noop_commit)

    generator = get_db_uow()
    await generator.__anext__()
    await _make_dirty_uow(session)

    with pytest.raises(RuntimeError, match="after the request boundary committed"):
        await generator.__anext__()


@pytest.mark.anyio
async def test_run_sync_guard_rejects_external_commit(
    runtime_sessionmaker, monkeypatch
):
    """A sync callable that raw-COMMITs a BEGIN IMMEDIATE transaction is rejected.

    This is the lost-write failure mode from the issue: before this change a
    callable issuing its own commit would silently drop writes with only a log
    warning. Now the boundary's in_transaction guard raises immediately.
    """
    session = runtime_sessionmaker()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

    generator = get_db_uow()
    uow = await generator.__anext__()

    await uow.begin_immediate()

    def bad_callable(sync_session):
        conn = sync_session.connection()
        conn.exec_driver_sql("INSERT INTO bridge_rows (value) VALUES ('external')")
        # Violation: terminate the BEGIN IMMEDIATE transaction ourselves, which
        # would silently drop these writes if the boundary didn't guard.
        conn.exec_driver_sql("ROLLBACK")

    with pytest.raises(RuntimeError, match="transaction completion is owned by"):
        await uow.run_sync(bad_callable)

    # The external COMMIT already terminated the raw transaction; the boundary
    # would fail to commit again, so mark abort to roll back cleanly on teardown.
    uow.abort()
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    async with runtime_sessionmaker() as verify:
        rows = (
            (await verify.execute(text("SELECT value FROM bridge_rows")))
            .scalars()
            .all()
        )
    assert rows == []
