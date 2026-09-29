"""Tests for the background cleanup seam (issue #295).

Covers: the BackgroundTaskRegistry (a visible, shutdown-aware task registry that
replaces fire-and-forget create_task) and RoomLifecycleService's graceful room
cleanup, exercised WITHOUT a real 60-second sleep by injecting a fake clock.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.domain.deck import Deck
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.services.background_tasks import (
    BackgroundTaskRegistry,
    background_task_registry,
)
from jellyswipe.services.room_lifecycle import RoomLifecycleService
from jellyswipe.services.session_teardown import (
    sweep_orphaned_instances,
    teardown_session_instance,
)


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    """A temp-DB sessionmaker bound to the global get_sessionmaker()."""
    upgrade_to_head(build_sqlite_url(db_path))
    await dispose_runtime()
    await initialize_runtime(build_async_sqlite_url(db_path))
    yield get_sessionmaker()
    await dispose_runtime()


async def _noop_sleep(_seconds: int) -> None:
    """Fake clock that never actually waits — lets tests run in milliseconds."""
    return


async def _seed_room_and_instance(session):
    uow = DatabaseUnitOfWork(session)
    deck = Deck.from_cards([])
    await uow.rooms.create(
        "7777",
        deck=deck,
        ready=True,
        current_genre="All",
        solo_mode=True,
        include_movies=True,
        include_tv_shows=False,
    )
    await uow.session_instances.create(instance_id="quitting", pairing_code="7777")
    return uow


# ---------------------------------------------------------------------------
# BackgroundTaskRegistry
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_registry_tracks_pending_and_completes():
    """A scheduled coroutine is tracked as pending, then removed on completion."""
    registry = BackgroundTaskRegistry()
    ran = []

    async def work():
        await asyncio.sleep(0)
        ran.append("done")

    task = registry.schedule(work())
    assert registry.pending == 1
    await task
    assert ran == ["done"]
    assert registry.pending == 0


@pytest.mark.anyio
async def test_registry_shutdown_cancels_pending():
    """shutdown() cancels and drains pending tasks, leaving none behind."""
    registry = BackgroundTaskRegistry()

    async def forever():
        await asyncio.Event().wait()

    registry.schedule(forever())
    assert registry.pending == 1
    await registry.shutdown()
    assert registry.pending == 0


@pytest.mark.anyio
async def test_registry_logs_rather_than_swallows_failures():
    """A throwing background task is logged, not silently dropped."""
    registry = BackgroundTaskRegistry()

    async def boom():
        raise RuntimeError("background boom")

    task = registry.schedule(boom())
    await task
    assert registry.pending == 0


def test_module_singleton_is_a_registry():
    """The app-wide background_task_registry is a BackgroundTaskRegistry."""
    assert isinstance(background_task_registry, BackgroundTaskRegistry)


# ---------------------------------------------------------------------------
# RoomLifecycle graceful cleanup
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cleanup_after_grace_runs_without_real_sleep(runtime_sessionmaker):
    """_cleanup_after_grace closes/deletes the instance with an injected fake clock."""
    # Seed an instance + event to be cleaned up.
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.session_instances.create(instance_id="clean-me", pairing_code="9999")
        await uow.session_events.append("clean-me", "session_ready", "{}")
        await session.commit()

    svc = RoomLifecycleService(sleep=_noop_sleep, grace_seconds=60)
    await svc._cleanup_after_grace("clean-me")

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        instance = await uow.session_instances.get_by_pairing_code("9999")
        remaining = (
            (
                await session.execute(
                    text(
                        "SELECT 1 FROM session_events "
                        "WHERE session_instance_id = 'clean-me'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert instance is None
    assert remaining == []


@pytest.mark.anyio
async def test_quit_room_schedules_cleanup_via_registry(runtime_sessionmaker):
    """quit_room hands the grace-period cleanup to the task registry (not create_task)."""
    registry = BackgroundTaskRegistry()
    svc = RoomLifecycleService(registry=registry, sleep=_noop_sleep)

    async with runtime_sessionmaker() as session:
        await _seed_room_and_instance(session)
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        result = await svc.quit_room("7777", "user", uow)
        await session.commit()

    assert result.status == "session_ended"
    assert registry.pending == 1

    # Let the (fake-clock) cleanup task run to completion, then verify cleanup.
    for _ in range(50):
        if registry.pending == 0:
            break
        await asyncio.sleep(0.01)
    assert registry.pending == 0

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        instance = await uow.session_instances.get_by_pairing_code("7777")
    assert instance is None


# ---------------------------------------------------------------------------
# Session-instance teardown service module
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_teardown_session_instance_removes_row_and_events(runtime_sessionmaker):
    """teardown_session_instance deletes the instance and its events after a caller commit."""
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.session_instances.create(instance_id="torn-down", pairing_code="1001")
        await uow.session_events.append("torn-down", "session_ready", "{}")
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await teardown_session_instance(uow, "torn-down")
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        instance = await uow.session_instances.get_by_instance_id("torn-down")
        remaining = (
            (
                await session.execute(
                    text(
                        "SELECT 1 FROM session_events "
                        "WHERE session_instance_id = 'torn-down'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert instance is None
    assert remaining == []


@pytest.mark.anyio
async def test_teardown_session_instance_does_not_commit_on_its_own(
    runtime_sessionmaker,
):
    """teardown_session_instance leaves transaction completion to the caller (ADR-0004)."""
    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.session_instances.create(
            instance_id="uncommitted", pairing_code="1002"
        )
        await uow.session_events.append("uncommitted", "session_ready", "{}")
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await teardown_session_instance(uow, "uncommitted")
        # teardown must not have committed on its own: rolling back discards the
        # pending deletion, so the instance should still exist afterwards.
        await session.rollback()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        instance = await uow.session_instances.get_by_instance_id("uncommitted")
    assert instance is not None


@pytest.mark.anyio
async def test_sweep_orphaned_instances_reaps_stale_closing_only(
    runtime_sessionmaker,
):
    """The sweep reaps stale closing instances and leaves fresh closing and active ones."""
    now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        await uow.session_instances.create(instance_id="stale", pairing_code="2001")
        await uow.session_instances.create(instance_id="fresh", pairing_code="2002")
        await uow.session_instances.create(instance_id="active", pairing_code="2003")
        await session.commit()

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        for iid in ("stale", "fresh"):
            await uow.session_instances.mark_closing(iid)
        # Backdate the stale one beyond the 5-minute cutoff; keep fresh recent.
        await session.execute(
            text(
                "UPDATE session_instances SET closed_at = :t "
                "WHERE instance_id = 'stale'"
            ),
            {"t": (now - timedelta(minutes=6)).isoformat()},
        )
        await session.execute(
            text(
                "UPDATE session_instances SET closed_at = :t "
                "WHERE instance_id = 'fresh'"
            ),
            {"t": (now - timedelta(minutes=1)).isoformat()},
        )
        await session.commit()

    swept = await sweep_orphaned_instances(sessionmaker=runtime_sessionmaker, now=now)
    assert swept == 1

    async with runtime_sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        stale = await uow.session_instances.get_by_instance_id("stale")
        fresh = await uow.session_instances.get_by_instance_id("fresh")
        active = await uow.session_instances.get_by_instance_id("active")
    assert stale is None
    assert fresh is not None and fresh.status == "closing"
    assert active is not None and active.status == "active"


@pytest.mark.anyio
async def test_sweep_orphaned_instances_returns_zero_when_nothing_stale(
    runtime_sessionmaker,
):
    """The sweep commits once and reports zero when no instance is stale."""
    now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
    swept = await sweep_orphaned_instances(sessionmaker=runtime_sessionmaker, now=now)
    assert swept == 0


def test_lifespan_survives_sweep_error(app, monkeypatch):
    """A raised sweep error is caught by lifespan; the app still starts."""

    async def boom():
        raise RuntimeError("sweep boom")

    monkeypatch.setattr("jellyswipe.sweep_orphaned_instances", boom)

    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
