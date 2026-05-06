"""Async auth service for Jelly Swipe session persistence."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from jellyswipe.auth_types import AuthRecord
from jellyswipe.db_uow import DatabaseUnitOfWork

_logger = logging.getLogger(__name__)


def clear_session_state(session_dict: dict) -> None:
    """Clear all local session-backed auth state."""
    session_dict.clear()


async def create_session(
    jf_token: str, jf_user_id: str, session_dict: dict, uow: DatabaseUnitOfWork
) -> str:
    """Create one persisted auth session and store its opaque ID locally."""
    now = datetime.now(timezone.utc)
    session_id = secrets.token_urlsafe(32)
    created_at = now.isoformat()
    cutoff_iso = (now - timedelta(days=14)).isoformat()

    await uow.auth_sessions.delete_expired(cutoff_iso)
    await uow.auth_sessions.insert(
        AuthRecord(
            session_id=session_id,
            jf_token=jf_token,
            user_id=jf_user_id,
            created_at=created_at,
        )
    )

    session_dict["session_id"] = session_id
    return session_id


async def get_current_token(session_dict: dict, uow: DatabaseUnitOfWork) -> AuthRecord | None:
    """Return the current persisted auth record, if present."""
    sid = session_dict.get("session_id")
    if sid is None:
        return None

    return await uow.auth_sessions.get_by_session_id(sid)


async def destroy_session(session_dict: dict, uow: DatabaseUnitOfWork) -> None:
    """Clear local auth state and best-effort delete the persisted record."""
    sid = session_dict.get("session_id")
    clear_session_state(session_dict)
    if sid is None:
        return

    try:
        await uow.auth_sessions.delete_by_session_id(sid)
    except Exception:
        _logger.error(
            "auth_session_delete_failed",
            exc_info=True,
            extra={"session_id": sid},
        )
