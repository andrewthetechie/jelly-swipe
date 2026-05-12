"""SSE session event stream generator with injectable dependencies.

Extracted from routers/rooms.py to allow direct unit testing with fake
dependencies (notifier, is_disconnected, sessionmaker).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from jellyswipe.db_uow import DatabaseUnitOfWork


async def session_event_stream(
    code: str,
    instance_id: str,
    room: Any,  # Room model/record
    cursor: int | None,
    sessionmaker_factory: Callable,
    notifier: Any,  # SessionNotifier
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncGenerator[dict, None]:
    """Session Event Stream generator with injectable dependencies.

    Yields dicts with keys: "id" (str), "data" (str), and/or "comment" (str).
    Same shape EventSourceResponse consumes.

    Args:
        code: Room pairing code.
        instance_id: Session instance ID for event ledger queries.
        room: Room model instance (or None).
        cursor: Last-Event-ID from client (or None for first attach).
        sessionmaker_factory: Callable returning an async session context manager.
        notifier: SessionNotifier instance for subscribe/unsubscribe.
        is_disconnected: Async callable returning True when client disconnected.
    """
    # 1. Cursor validation or bootstrap
    if cursor is not None:
        async with sessionmaker_factory() as session:
            uow = DatabaseUnitOfWork(session)
            events_after = await uow.session_events.read_after(
                instance_id, cursor, limit=1
            )
            if not events_after:
                yield {
                    "data": json.dumps(
                        {"event_type": "session_reset", "reason": "stale_cursor"}
                    )
                }
                return
    else:
        async with sessionmaker_factory() as session:
            uow = DatabaseUnitOfWork(session)
            latest_eid = await uow.session_events.read_latest_event_id(instance_id)
        bootstrap = {
            "event_type": "session_bootstrap",
            "instance_id": instance_id,
            "ready": room.ready if room else False,
            "genre": room.current_genre if room else "All",
            "solo": room.solo_mode if room else False,
            "hide_watched": room.hide_watched if room else False,
            "replay_boundary": latest_eid or 0,
        }
        yield {"id": str(latest_eid or 0), "data": json.dumps(bootstrap)}

    # 2. Replay missed events
    missed = []
    latest_eid = None
    if cursor is not None:
        async with sessionmaker_factory() as session:
            uow = DatabaseUnitOfWork(session)
            missed = await uow.session_events.read_after(instance_id, cursor, limit=100)
        for evt in missed:
            yield {
                "id": str(evt.event_id),
                "data": json.dumps(
                    {
                        "event_id": evt.event_id,
                        "event_type": evt.event_type,
                        **json.loads(evt.payload_json),
                    }
                ),
            }
            if evt.event_type == "session_closed":
                return

    # 3. Live event subscription loop
    last_event_id = (
        missed[-1].event_id if cursor is not None and missed else (latest_eid or 0)
    )
    last_event_time = time.time()

    while True:
        if await is_disconnected():
            break

        future = notifier.subscribe(code)
        try:
            await asyncio.wait_for(future, timeout=20.0)
        except asyncio.TimeoutError:
            if time.time() - last_event_time >= 15:
                yield {"comment": "ping"}
                last_event_time = time.time()
            continue

        async with sessionmaker_factory() as session:
            uow = DatabaseUnitOfWork(session)
            new_events = await uow.session_events.read_after(
                instance_id, last_event_id, limit=100
            )

        for evt in new_events:
            payload = {"event_id": evt.event_id, "event_type": evt.event_type}
            payload.update(json.loads(evt.payload_json))
            yield {"id": str(evt.event_id), "data": json.dumps(payload)}
            last_event_id = evt.event_id
            last_event_time = time.time()
            if evt.event_type == "session_closed":
                notifier.unsubscribe(code, future)
                return

        notifier.unsubscribe(code, future)
