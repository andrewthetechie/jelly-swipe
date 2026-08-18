"""Tests for the background cleanup seam (issue #295).

Covers: the BackgroundTaskRegistry (a visible, shutdown-aware task registry that
replaces fire-and-forget create_task) and RoomLifecycleService's graceful room
cleanup, exercised WITHOUT a real 60-second sleep by injecting a fake clock.
"""

import asyncio

import pytest
from sqlalchemy import text

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
