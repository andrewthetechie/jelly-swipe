"""Authentication and session management routes.

Per D-06, D-09, D-10: 6 auth routes with identical URL paths, methods, and response shapes.
Uses dependency injection for authentication (require_auth) and rate limiting.
"""

import logging
import traceback

from fastapi import APIRouter, Request, Depends, Response
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    get_provider,
    require_auth,
)
from jellyswipe.auth import create_session, destroy_session, resolve_active_room

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
auth_router = APIRouter()


def make_error_response(
    message: str, status_code: int, request: Request, extra_fields: dict = None
) -> XSSSafeJSONResponse:
    """Create a standardized error response with request ID tracking."""
    if status_code >= 500:
        message = "Internal server error"
    body = {"error": message}
    body["request_id"] = getattr(request.state, "request_id", "unknown")
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    """Log exception with request context."""
    log_data = {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "route": request.url.path,
        "method": request.method,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "stack_trace": traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    _logger.error("unhandled_exception", extra=log_data)


@auth_router.get("/auth/provider")
def auth_provider(request: Request):
    """Return authentication provider information."""
    payload = {"provider": "jellyfin", "jellyfin_browser_auth": "delegate"}
    return payload


@auth_router.post("/auth/jellyfin-use-server-identity")
async def jellyfin_use_server_identity(request: Request, uow: DBUoW):
    """Authenticate using Jellyfin server delegate identity."""
    prov = get_provider()
    try:
        token = prov.server_access_token_for_delegate()
        uid = prov.server_primary_user_id_for_delegate()
    except RuntimeError:
        return make_error_response("Jellyfin delegate unavailable", 401, request)
    await create_session(token, uid, request.session, uow)
    return {"userId": uid}


@auth_router.post("/auth/jellyfin-login")
async def jellyfin_login(request: Request, uow: DBUoW):
    """Authenticate user with Jellyfin username and password."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return XSSSafeJSONResponse(
            content={"error": "Username and password are required"}, status_code=400
        )
    try:
        out = get_provider().authenticate_user_session(username, password)
        await create_session(out["token"], out["user_id"], request.session, uow)
        return {"userId": out["user_id"]}
    except Exception:
        return make_error_response("Jellyfin login failed", 401, request)


@auth_router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
):
    """Destroy the current user session."""
    await destroy_session(request.session, uow)
    response.delete_cookie("session", path="/")
    return {"status": "logged_out"}


@auth_router.get("/me")
async def get_me(request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)):
    """Return current user information."""
    active_room = await resolve_active_room(request.session, uow)
    info = get_provider().server_info()
    return {
        "userId": user.user_id,
        "displayName": user.user_id,
        "serverName": info.get("name", ""),
        "serverId": info.get("machineIdentifier", ""),
        "activeRoom": active_room,
    }


@auth_router.get("/jellyfin/server-info")
def jellyfin_server_info(request: Request):
    """Return Jellyfin server information."""
    try:
        info = get_provider().server_info()
        return {
            "baseUrl": info.get("machineIdentifier", ""),
            "webUrl": info.get("webUrl", ""),
        }
    except Exception:
        return XSSSafeJSONResponse(
            content={"baseUrl": "", "webUrl": ""}, status_code=200
        )
