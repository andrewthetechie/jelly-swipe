"""Authentication business logic extracted from the auth router."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.repositories.auth_sessions import AuthRecord

if TYPE_CHECKING:
    from jellyswipe.dependencies import AuthUser
    from jellyswipe.jellyfin_library import JellyfinLibraryProvider

_logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    """Result of a successful delegate login."""

    session_id: str
    user_id: str
    response_body: dict


@dataclass
class MeResult:
    """Result of a get_me query."""

    response_body: dict
    active_room: str | None = None


class AuthService:
    """Encapsulates auth business logic previously inline in router handlers."""

    @staticmethod
    async def login_delegate(
        provider: JellyfinLibraryProvider,
        uow: DatabaseUnitOfWork,
    ) -> LoginResult | None:
        """Authenticate via Jellyfin delegate identity.

        Returns LoginResult on success, None when the provider raises RuntimeError.
        """
        try:
            token = provider.server_access_token_for_delegate()
            uid = provider.server_primary_user_id_for_delegate()
        except RuntimeError:
            return None

        now = datetime.now(timezone.utc)
        session_id = secrets.token_urlsafe(32)
        await uow.auth_sessions.delete_expired((now - timedelta(days=14)).isoformat())
        await uow.auth_sessions.insert(
            AuthRecord(
                session_id=session_id,
                jf_token=token,
                user_id=uid,
                created_at=now.isoformat(),
            )
        )
        return LoginResult(
            session_id=session_id,
            user_id=uid,
            response_body={"userId": uid},
        )

    @staticmethod
    async def logout(
        session_id: str | None,
        uow: DatabaseUnitOfWork,
    ) -> None:
        """Delete the session record, swallowing exceptions per current behavior."""
        if session_id is None:
            return
        try:
            await uow.auth_sessions.delete_by_session_id(session_id)
        except Exception:
            _logger.error(
                "auth_session_delete_failed",
                exc_info=True,
                extra={"session_id": session_id},
            )

    @staticmethod
    async def get_me(
        user: AuthUser,
        active_room: str | None,
        provider: JellyfinLibraryProvider,
        uow: DatabaseUnitOfWork,
    ) -> MeResult:
        """Return user info, clearing active_room if the pairing code no longer exists."""
        if active_room is not None:
            if not await uow.rooms.pairing_code_exists(active_room):
                active_room = None
        info = provider.server_info()
        return MeResult(
            response_body={
                "userId": user.user_id,
                "displayName": user.user_id,
                "serverName": info.get("name", ""),
                "serverId": info.get("machineIdentifier", ""),
                "activeRoom": active_room,
            },
            active_room=active_room,
        )
