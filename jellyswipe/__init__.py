"""Jelly Swipe app factory — thin factory mounting all 5 domain routers.

Per D-15: __init__.py is a thin app factory. All domain routes live in routers/*.
The SSE route (/room/{code}/stream) stays inline until Phase 34 migrates it.
The /plex/server-info route is deleted per D-10.
"""

import hashlib
import json
import logging
import os
import random
import secrets
import sqlite3
import time
import typing
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Config globals — single source of truth in config.py (D-01 through D-05).
# _provider_singleton and _JELLYFIN_URL re-exported here because dependencies.py
# accesses them via `import jellyswipe as _app`.
from jellyswipe.config import (
    _provider_singleton,
    _JELLYFIN_URL,
    JELLYFIN_URL,
    _token_user_id_cache,
    TOKEN_USER_ID_CACHE_TTL_SECONDS,
    IDENTITY_ALIAS_HEADERS,
)

# App root for static/template paths
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# DB path (kept here; config.py holds URL/token constants, __init__.py owns DB path)
DB_PATH = os.path.abspath(
    os.getenv("DB_PATH", os.path.join(_APP_ROOT, "..", "data", "jellyswipe.db"))
)

_logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    return f"req_{int(time.time())}_{secrets.token_hex(4)}"


class XSSSafeJSONResponse(JSONResponse):
    """JSON response that escapes HTML-sensitive characters for XSS defense.

    Per OWASP recommendation, < > & are encoded as \\u003c \\u003e \\u0026
    in JSON output so that raw HTTP bodies cannot contain executable HTML tags.
    JSON parsers correctly decode these back to the original characters.

    TRADEOFF (v1.5 security decision): This is applied as the default_response_class
    for the entire FastAPI app. All JSON string values containing & will appear as
    \\u0026 in the raw HTTP wire format (e.g., "Dungeons & Dragons" becomes
    "Dungeons \\u0026 Dragons"). JSON.parse() handles this transparently, but any
    client doing raw string matching on the response body must account for it.
    This is an intentional defense-in-depth measure — do NOT remove without a
    security review. See also: proxy_router returns plain Response for binary
    image data, bypassing this escaping.
    """

    def render(self, content: typing.Any) -> bytes:
        result = super().render(content)
        # NOTE: Replacement order matters. & is replaced LAST so that the
        # \u003c and \u003e sequences inserted above are not double-escaped
        # (they contain no & character). Pre-existing & in JSON values
        # (e.g., "Tom & Jerry") will be escaped to \u0026.
        return (result
                .replace(b"<", b"\\u003c")
                .replace(b">", b"\\u003e")
                .replace(b"&", b"\\u0026"))


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that generates a unique request ID and adds security headers.

    Per D-07: generates req_{unix_ts}_{4-byte hex} ID, stores in request.state.request_id,
    and injects X-Request-Id response header.
    Per D-08: also adds Content-Security-Policy header to all responses.
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "object-src 'none'; "
        "img-src 'self' https://image.tmdb.org; "
        "frame-src https://www.youtube.com"
    )

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = generate_request_id()
        response = await call_next(request)
        response.headers['X-Request-Id'] = request.state.request_id
        response.headers['Content-Security-Policy'] = self.CSP_POLICY
        return response


# ============================================================================
# SSE route helpers — kept inline for Phase 34 migration (D-15)
# ============================================================================

def _require_login(request: Request):
    """Phase 31 bridge: replaces @login_required. Phase 34 replaces with Depends(require_auth)."""
    from jellyswipe.db import get_db_closing
    sid = request.session.get('session_id')
    if not sid:
        raise HTTPException(status_code=401, detail='Authentication required')
    with get_db_closing() as conn:
        row = conn.execute(
            'SELECT jellyfin_token, jellyfin_user_id FROM user_tokens WHERE session_id = ?',
            (sid,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail='Authentication required')
    request.state.jf_token = row['jellyfin_token']
    request.state.user_id = row['jellyfin_user_id']


def _jellyfin_user_token_from_request(request: Request) -> str:
    from jellyswipe.dependencies import get_provider
    if request.session.get("jf_delegate_server_identity"):
        prov = get_provider()
        try:
            return prov.server_access_token_for_delegate()
        except RuntimeError:
            return ""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header:
        try:
            token = get_provider().extract_media_browser_token(auth_header)
        except Exception:
            token = None
    return token or ""


def _request_has_identity_alias_headers(request: Request) -> bool:
    for header in IDENTITY_ALIAS_HEADERS:
        if request.headers.get(header):
            return True
    return False


def _set_identity_rejection_reason(request: Request, reason: str) -> None:
    request.state.identity_rejected = reason


def _identity_rejection_reason(request: Request) -> Optional[str]:
    value = getattr(request.state, "identity_rejected", None)
    return str(value) if value else None


def _token_cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _resolve_user_id_from_token_cached(token: str) -> Optional[str]:
    from jellyswipe.dependencies import get_provider
    now = time.time()
    cache_key = _token_cache_key(token)
    cached = _token_user_id_cache.get(cache_key)
    if cached:
        user_id, expires_at = cached
        if expires_at > now:
            return user_id
        _token_user_id_cache.pop(cache_key, None)

    try:
        user_id = get_provider().resolve_user_id_from_token(token)
    except Exception:
        return None

    _token_user_id_cache[cache_key] = (
        user_id,
        now + TOKEN_USER_ID_CACHE_TTL_SECONDS,
    )
    return user_id


def _provider_user_id_from_request(request: Request):
    from jellyswipe.dependencies import get_provider
    if request.session.get("jf_delegate_server_identity"):
        prov = get_provider()
        try:
            return prov.server_primary_user_id_for_delegate()
        except RuntimeError:
            pass
    if _request_has_identity_alias_headers(request):
        _set_identity_rejection_reason(request, "spoofed_alias_header")
        return None

    token = _jellyfin_user_token_from_request(request)
    if not token:
        return None
    user_id = _resolve_user_id_from_token_cached(token)
    if user_id:
        return user_id
    _set_identity_rejection_reason(request, "token_resolution_failed")
    return None


# ============================================================================
# App factory
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import jellyswipe.db
    # Only set DB_PATH if it hasn't been set yet (e.g., by test_config)
    if jellyswipe.db.DB_PATH is None:
        jellyswipe.db.DB_PATH = DB_PATH
    from .db import init_db
    init_db()
    _logger.info("jellyswipe_startup")
    yield
    # Teardown
    global _provider_singleton
    _provider_singleton = None
    _logger.info("jellyswipe_shutdown")


def create_app(test_config=None):
    """
    Create and configure a FastAPI application instance.

    Args:
        test_config: Optional dictionary of test configuration to override defaults.
                     If provided, DB_PATH will be overridden before database initialization.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(
        lifespan=lifespan,
        default_response_class=XSSSafeJSONResponse,
    )

    # Middleware stack — add in LIFO order (last added = outermost):
    # 1. RequestIdMiddleware (innermost — sees request after session decoded)
    # 2. SessionMiddleware (middle)
    # 3. ProxyHeadersMiddleware (outermost — rewrites X-Forwarded first)

    # Add 1st: RequestIdMiddleware (innermost in request processing)
    app.add_middleware(RequestIdMiddleware)

    # Determine session secret — test_config overrides env var (D-07)
    if test_config and "SECRET_KEY" in test_config:
        session_secret = test_config["SECRET_KEY"]
    else:
        session_secret = os.environ["FLASK_SECRET"]

    # Add 2nd: SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        max_age=14 * 24 * 60 * 60,  # 14 days per D-05
        same_site="lax",
        https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
    )

    # Add 3rd: ProxyHeadersMiddleware (outermost) per D-04
    trusted = os.getenv('TRUSTED_PROXY_IPS', '127.0.0.1')
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)

    # Test config override
    if test_config:
        if 'DB_PATH' in test_config:
            import jellyswipe.db
            jellyswipe.db.DB_PATH = test_config['DB_PATH']

    # Static files mount (prevents path traversal vulnerabilities)
    app.mount('/static', StaticFiles(directory=os.path.join(_APP_ROOT, 'static')), name='static')

    # Mount all 5 domain routers (D-14: no prefix — routes define full paths)
    from jellyswipe.routers.auth import auth_router
    from jellyswipe.routers.rooms import rooms_router
    from jellyswipe.routers.media import media_router
    from jellyswipe.routers.proxy import proxy_router
    from jellyswipe.routers.static import static_router

    app.include_router(auth_router)
    app.include_router(rooms_router)
    app.include_router(media_router)
    app.include_router(proxy_router)
    app.include_router(static_router)

    return app


# Module-level app instance — required for deployment.
# Uvicorn is invoked as `uvicorn jellyswipe:app` (not --factory), so this
# module-level call is necessary. Removing it would break the Dockerfile CMD.
#
# SIDE EFFECT: importing jellyswipe for ANY reason (tests, IDE indexing, etc.)
# triggers create_app(), which reads os.environ["FLASK_SECRET"] and runs
# config.validate_jellyfin_url(). The test suite works around this by setting
# env vars at conftest module level before any jellyswipe imports.
#
# Future improvement: switch Uvicorn to --factory mode with
# `uvicorn jellyswipe:create_app --factory` and remove this line.
app = create_app()
