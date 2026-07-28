"""Shared helper functions for router modules.

``make_error_response`` and ``log_exception`` live in
``jellyswipe.http_utils`` (neutral ground usable by both routers and
services) and are re-exported here for backward compatibility.
"""

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.http_utils import log_exception, make_error_response
from jellyswipe.notifier import notifier

__all__ = ["commit_and_wake", "log_exception", "make_error_response"]


async def commit_and_wake(uow: DatabaseUnitOfWork, code: str) -> None:
    """Commit the UoW transaction, then wake SSE subscribers for the room.

    Must be called AFTER all database writes are complete.
    Commit happens before notify to ensure subscribers read committed data.
    """
    await uow.session.commit()
    notifier.notify(code)
