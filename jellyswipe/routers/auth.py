"""Authentication and session management routes.

Per D-06, D-09, D-10: 6 auth routes with identical URL paths, methods, and response shapes.
Uses dependency injection for authentication (require_auth) and rate limiting.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Depends, Response
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    get_provider,
    require_auth,
)
from jellyswipe.auth import resolve_active_room
from jellyswipe.auth_types import AuthRecord
from jellyswipe.routers._helpers import make_error_response

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
auth_router = APIRouter()


@auth_router.post("/auth/jellyfin-use-server-identity")
async def jellyfin_use_server_identity(
    request: Request, uow: DBUoW, provider=Depends(get_provider)
):
    """Authenticate using Jellyfin server delegate identity."""
    try:
        token = provider.server_access_token_for_delegate()
        uid = provider.server_primary_user_id_for_delegate()
    except RuntimeError:
        return make_error_response("Jellyfin delegate unavailable", 401, request)
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
    request.session["session_id"] = session_id
    await uow.session.commit()
    return {"userId": uid}


@auth_router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
):
    """Destroy the current user session."""
    sid = request.session.get("session_id")
    request.session.clear()
    if sid is not None:
        try:
            await uow.auth_sessions.delete_by_session_id(sid)
        except Exception:
            _logger.error(
                "auth_session_delete_failed",
                exc_info=True,
                extra={"session_id": sid},
            )
    await uow.session.commit()
    response.delete_cookie("session", path="/")
    return {"status": "logged_out"}


@auth_router.get("/me")
async def get_me(
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    provider=Depends(get_provider),
):
    """Return current user information."""
    active_room = await resolve_active_room(request.session, uow)
    info = provider.server_info()
    return {
        "userId": user.user_id,
        "displayName": user.user_id,
        "serverName": info.get("name", ""),
        "serverId": info.get("machineIdentifier", ""),
        "activeRoom": active_room,
    }


@auth_router.get("/jellyfin/server-info")
def jellyfin_server_info(request: Request, provider=Depends(get_provider)):
    """Return Jellyfin server information."""
    try:
        info = provider.server_info()
        return {
            "baseUrl": info.get("machineIdentifier", ""),
            "webUrl": info.get("webUrl", ""),
        }
    except Exception:
        return XSSSafeJSONResponse(
            content={"baseUrl": "", "webUrl": ""}, status_code=200
        )
