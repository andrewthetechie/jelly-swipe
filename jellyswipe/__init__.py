"""Jelly Swipe app factory -- thin factory mounting all 5 domain routers.

Per D-15: __init__.py is a thin app factory. All domain routes live in routers/*.
SSE route migrated to rooms_router in Phase 34.
"""

import logging
import os
import secrets
import time
import typing
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from jellyswipe.config import AppConfig
from jellyswipe.db_runtime import dispose_runtime

# App root for static/template paths
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))

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
        return (
            result.replace(b"<", b"\\u003c")
            .replace(b">", b"\\u003e")
            .replace(b"&", b"\\u0026")
        )


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

    # FastAPI's /docs (Swagger UI) and /redoc load assets from jsdelivr and
    # use inline scripts/styles; ReDoc additionally spawns a blob: worker and
    # the favicon is served from fastapi.tiangolo.com. The main app CSP would
    # break these pages, so we serve a scoped policy for the docs paths only.
    DOCS_CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com https://image.tmdb.org; "
        "worker-src 'self' blob:; "
        "object-src 'none'"
    )
    DOCS_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = generate_request_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        if request.url.path in self.DOCS_PATHS:
            response.headers["Content-Security-Policy"] = self.DOCS_CSP_POLICY
        else:
            response.headers["Content-Security-Policy"] = self.CSP_POLICY
        return response


# ============================================================================
# App factory
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("jellyswipe_startup")

    # Clean up orphaned session instances from previous runs
    try:
        import datetime

        from jellyswipe.db_runtime import get_sessionmaker
        from jellyswipe.db_uow import DatabaseUnitOfWork

        async with get_sessionmaker()() as session:
            uow = DatabaseUnitOfWork(session)
            # Find instances marked as "closing" for more than 5 minutes
            cutoff = (
                datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(minutes=5)
            ).isoformat()

            # For each stale closing instance, complete the cleanup
            closing_instances = await uow.session_instances.get_closing_before(cutoff)
            for instance in closing_instances:
                _logger.info("Cleaning up orphaned instance: %s", instance.instance_id)
                await uow.session_instances.mark_closed(instance.instance_id)
                await uow.session_events.delete_for_instance(instance.instance_id)
                await uow.session_instances.delete(instance.instance_id)

            await session.commit()
    except Exception:
        # If cleanup fails during startup, log and continue — the app should still start
        _logger.exception("Failed to clean up orphaned session instances on startup")

    yield
    from jellyswipe.dependencies import reset_provider_singleton

    reset_provider_singleton()
    await dispose_runtime()
    _logger.info("jellyswipe_shutdown")


def create_app(config: AppConfig | None = None):
    """
    Create and configure a FastAPI application instance.

    Args:
        config: Optional AppConfig instance. If None, constructed from env vars.

    Returns:
        A configured FastAPI application instance.
    """
    if config is None:
        config = AppConfig()

    # Get version for OpenAPI schema
    from importlib.metadata import PackageNotFoundError, version as pkg_version

    try:
        version = pkg_version("jellyswipe")
    except PackageNotFoundError:
        version = "0.0.0-dev"

    # Define OpenAPI tags with descriptions
    openapi_tags = [
        {
            "name": "Authentication",
            "description": "User authentication and session management using Jellyfin server identity.",
        },
        {
            "name": "Rooms",
            "description": "Room creation, joining, and management. Rooms contain multiple users and shared swipe sessions.",
        },
        {
            "name": "Swiping",
            "description": "Media swiping endpoints for liking and rejecting items in a room.",
        },
        {
            "name": "Matches",
            "description": "Match retrieval and management. Matches are media items liked by multiple users in the same room.",
        },
        {
            "name": "Media",
            "description": "Media browsing endpoints including genres, cast, trailers, and watchlist management.",
        },
        {
            "name": "Proxy",
            "description": "Proxy image and file requests to the Jellyfin server with path validation.",
        },
        {
            "name": "Health",
            "description": "Health check endpoints for monitoring system status and readiness.",
        },
    ]

    app = FastAPI(
        title="Jellyswipe API",
        version=version,
        description="Tinder-style swiping for Jellyfin media. Users authenticate via Jellyfin server identity and join rooms to collaboratively swipe on movies and TV shows. Matches are media items liked by multiple users. Real-time updates via Server-Sent Events (SSE). Session cookie required for all authenticated endpoints. Rate-limited endpoints are marked in route descriptions. XSS-safe JSON escaping: HTML-sensitive characters (<, &) are escaped in JSON output to prevent injection attacks.",
        license_info={
            "name": "MIT",
            "url": "https://github.com/andrewthetechie/jelly-swipe/blob/main/LICENSE",
        },
        openapi_tags=openapi_tags,
        lifespan=lifespan,
        default_response_class=XSSSafeJSONResponse,
    )

    app.state.config = config

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        response = XSSSafeJSONResponse(
            content={"detail": exc.detail},
            status_code=exc.status_code,
            headers=exc.headers,
        )
        if getattr(request.state, "clear_session_cookie", False):
            response.delete_cookie("session", path="/")
        return response

    # Middleware stack — add in LIFO order (last added = outermost):
    # 1. RequestIdMiddleware (innermost — sees request after session decoded)
    # 2. SessionMiddleware (middle)
    # 3. ProxyHeadersMiddleware (outermost — rewrites X-Forwarded first)

    # Add 1st: RequestIdMiddleware (innermost in request processing)
    app.add_middleware(RequestIdMiddleware)

    # Add 2nd: SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.session_secret,
        max_age=14 * 24 * 60 * 60,  # 14 days per D-05
        same_site="lax",
        https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    )

    # Add 3rd: ProxyHeadersMiddleware (outermost) per D-04
    trusted = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)

    # Static files mount (prevents path traversal vulnerabilities)
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(_APP_ROOT, "static")),
        name="static",
    )

    # Mount all 5 domain routers (D-14: no prefix — routes define full paths)
    from jellyswipe.routers.auth import auth_router
    from jellyswipe.routers.rooms import rooms_router
    from jellyswipe.routers.media import media_router
    from jellyswipe.routers.proxy import proxy_router
    from jellyswipe.routers.static import static_router
    from jellyswipe.routers.health import health_router

    app.include_router(auth_router)
    app.include_router(rooms_router)
    app.include_router(media_router)
    app.include_router(proxy_router)
    app.include_router(static_router)
    app.include_router(health_router)

    return app


def __getattr__(name: str):
    """Lazy-export the ASGI app so package imports stay side-effect free.

    Alembic and declarative metadata imports need to load `jellyswipe` the package
    without constructing the FastAPI app or validating runtime provider config.
    Uvicorn's `jellyswipe:app` import path still works because module attribute
    access triggers this loader on first access.
    """
    if name == "app":
        app = create_app()
        globals()["app"] = app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
