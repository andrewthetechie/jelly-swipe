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
from jellyswipe.auth_types import AuthRecord
from jellyswipe.routers._helpers import make_error_response
from jellyswipe.schemas import (
    ErrorResponse,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    ServerInfoResponse,
)

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
auth_router = APIRouter()


@auth_router.post(
    "/auth/jellyfin-use-server-identity",
    tags=["Authentication"],
    response_model=LoginResponse,
    responses={
        200: {"description": "Successful authentication with user ID"},
        401: {
            "model": ErrorResponse,
            "description": "Jellyfin delegate unavailable or authentication failed",
        },
    },
    summary="Authenticate with Jellyfin server delegate identity",
)
async def jellyfin_use_server_identity(
    request: Request, uow: DBUoW, provider=Depends(get_provider)
):
    """Authenticate using Jellyfin server delegate identity.

    This is a public endpoint that does not require a session cookie.
    It delegates authentication to the Jellyfin server, which holds the user's
    credentials. Upon success, a session cookie is issued for subsequent requests.

    The server acts as the identity provider—the client never handles credentials
    directly, only the session cookie for subsequent API calls.
    """
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


@auth_router.post(
    "/auth/logout",
    tags=["Authentication"],
    response_model=LogoutResponse,
    responses={
        200: {"description": "User successfully logged out"},
        401: {
            "model": ErrorResponse,
            "description": "No valid session or authentication required",
        },
    },
    summary="Log out the current user",
)
async def logout(
    request: Request,
    response: Response,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
):
    """Destroy the current user session.

    **Requires authentication** — a valid session cookie in the request.

    Clears the session cookie and revokes the session token on the server side.
    After logout, all subsequent API calls will fail with 401 until the user
    authenticates again via the delegate identity endpoint.
    """
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


@auth_router.get(
    "/me",
    tags=["Authentication"],
    response_model=MeResponse,
    responses={
        200: {"description": "Current user and server information"},
        401: {
            "model": ErrorResponse,
            "description": "No valid session or authentication required",
        },
    },
    summary="Get current user and server information",
)
async def get_me(
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    provider=Depends(get_provider),
):
    """Return the current authenticated user and server information.

    **Requires authentication** — a valid session cookie in the request.

    Returns the user's ID, display name, Jellyfin server details, and the ID
    of any active swipe room. The server holds all credentials; the client only
    operates through the session cookie and server-provided data.
    """
    active_room = request.session.get("active_room")
    if active_room is not None:
        if not await uow.rooms.pairing_code_exists(active_room):
            request.session.pop("active_room", None)
            request.session.pop("solo_mode", None)
            active_room = None
    info = provider.server_info()
    return {
        "userId": user.user_id,
        "displayName": user.user_id,
        "serverName": info.get("name", ""),
        "serverId": info.get("machineIdentifier", ""),
        "activeRoom": active_room,
    }


@auth_router.get(
    "/jellyfin/server-info",
    tags=["Authentication"],
    response_model=ServerInfoResponse,
    responses={
        200: {"description": "Jellyfin server identifiers and URLs"},
    },
    summary="Get Jellyfin server information",
)
def jellyfin_server_info(request: Request, provider=Depends(get_provider)):
    """Return Jellyfin server identifiers and web URLs.

    This is a public endpoint that does not require authentication.
    It provides the server's machine identifier and web URL for client-side
    reference. No credentials are exposed—this endpoint is safe to call
    before authentication.
    """
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
