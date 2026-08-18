"""Authentication and session management routes.

Per D-06, D-09, D-10: 6 auth routes with identical URL paths, methods, and response shapes.
Uses dependency injection for authentication (require_auth) and rate limiting.
"""

from fastapi import APIRouter, Depends, Request, Response

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    get_provider,
    get_vault,
    require_auth,
)
from jellyswipe.routers._helpers import make_error_response
from jellyswipe.schemas import (
    ErrorResponse,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    ServerInfoResponse,
)
from jellyswipe.services.auth import AuthService

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
    request: Request, uow: DBUoW, vault=Depends(get_vault)
):
    """Authenticate using Jellyfin server delegate identity.

    This is a public endpoint that does not require a session cookie.
    It delegates authentication to the Jellyfin server, which holds the user's
    credentials. Upon success, a session cookie is issued for subsequent requests.

    The server acts as the identity provider—the client never handles credentials
    directly, only the session cookie for subsequent API calls.
    """
    result = await AuthService.login_delegate(vault, uow)
    if result is None:
        return make_error_response("Jellyfin delegate unavailable", 401, request)
    request.session["session_id"] = result.session_id
    return result.response_body


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
    await AuthService.logout(sid, uow)
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
    result = await AuthService.get_me(user, active_room, provider, uow)
    if result.response_body["activeRoom"] is None and active_room is not None:
        request.session.pop("active_room", None)
        request.session.pop("solo_mode", None)
    return result.response_body


@auth_router.get(
    "/jellyfin/server-info",
    tags=["Authentication"],
    response_model=ServerInfoResponse,
    responses={
        200: {"description": "Jellyfin server identifiers and URLs"},
    },
    summary="Get Jellyfin server information",
)
async def jellyfin_server_info(request: Request, provider=Depends(get_provider)):
    """Return Jellyfin server identifiers and web URLs.

    This is a public endpoint that does not require authentication.
    It provides the server's machine identifier and web URL for client-side
    reference. No credentials are exposed—this endpoint is safe to call
    before authentication.
    """
    try:
        info = await provider.server_info()
        return {
            "baseUrl": info.get("machineIdentifier", ""),
            "webUrl": info.get("webUrl", ""),
        }
    except Exception:
        return XSSSafeJSONResponse(
            content={"baseUrl": "", "webUrl": ""}, status_code=200
        )
