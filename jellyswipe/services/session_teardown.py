"""Session-instance teardown and orphan sweep.

Consolidates the teardown sequence for a closed session instance
(``mark_closed`` → delete events → delete instance row) and the orphan-sweep
cutoff policy into a single module, so a future change to teardown (e.g. adding
an archive step) touches exactly one place instead of being duplicated between
a domain service and the app factory.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork

logger = logging.getLogger(__name__)

# Instances marked as "closing" for longer than this are considered orphaned
# (their grace-period task died with the process). Deliberately exceeds the 60 s
# grace so the sweep never races a live grace task.
ORPHAN_SWEEP_CUTOFF_MINUTES = 5


async def teardown_session_instance(uow: DatabaseUnitOfWork, instance_id: str) -> None:
    """Tear down a closed session instance: events before the instance row.

    Performs exactly ``mark_closed`` → ``delete_for_instance`` (events) →
    ``delete`` (instance row), in that order. Events must be deleted before the
    instance row because ``session_events.session_instance_id`` is a plain FK
    with no ``ON DELETE CASCADE`` and ``PRAGMA foreign_keys=ON`` is enforced at
    runtime.

    Does NOT commit — the caller owns transaction completion (ADR-0004).
    """
    await uow.session_instances.mark_closed(instance_id)
    await uow.session_events.delete_for_instance(instance_id)
    await uow.session_instances.delete(instance_id)


async def sweep_orphaned_instances(
    sessionmaker: Any | None = None,
    now: datetime.datetime | None = None,
) -> int:
    """Reap stale ``closing`` instances left behind by dead grace tasks.

    Opens its own session from ``get_sessionmaker()`` (or the injectable
    ``sessionmaker``), selects instances with ``status='closing'`` and
    ``closed_at`` older than the 5-minute cutoff, runs
    ``teardown_session_instance`` for each, logs each reaped instance, and
    commits ONCE at the end. ``now`` pins the clock so tests can control the
    cutoff without sleeping.

    Returns the number of instances swept.
    """
    sessionmaker = sessionmaker or get_sessionmaker()
    current = now or datetime.datetime.now(datetime.UTC)
    cutoff = (
        current - datetime.timedelta(minutes=ORPHAN_SWEEP_CUTOFF_MINUTES)
    ).isoformat()

    async with sessionmaker() as session:
        uow = DatabaseUnitOfWork(session)
        closing_instances = await uow.session_instances.get_closing_before(cutoff)
        for instance in closing_instances:
            logger.info("Cleaning up orphaned instance: %s", instance.instance_id)
            await teardown_session_instance(uow, instance.instance_id)
        await session.commit()
    return len(closing_instances)
