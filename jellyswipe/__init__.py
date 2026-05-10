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

from jellyswipe.db_runtime import dispose_runtime, set_runtime_database_url_override

# App root for static/template paths
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# DB path (kept here; config.py holds URL/token constants, __init__.py owns DB path)
DB_PATH = os.path.abspath(
    os.getenv("DB_PATH", os.path.join(_APP_ROOT, "..", "data", "jellyswipe.db"))
)

from jellyswipe.db_paths import application_db_path as _application_db_path  # noqa: E402

_application_db_path.path = DB_PATH

_logger = logging.getLogger(__name__)
_provider_singleton = None


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

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = generate_request_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
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
    global _provider_singleton
    _provider_singleton = None
    import jellyswipe.config as _config

    _config._provider_singleton = None
    await dispose_runtime()
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
        https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    )

    # Add 3rd: ProxyHeadersMiddleware (outermost) per D-04
    trusted = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)

    # Test config override
    if test_config:
        if "DATABASE_URL" in test_config:
            set_runtime_database_url_override(test_config["DATABASE_URL"])
        else:
            set_runtime_database_url_override(None)
        if "DB_PATH" in test_config:
            import jellyswipe.db_paths as _db_paths

            _db_paths.application_db_path.path = test_config["DB_PATH"]
    else:
        set_runtime_database_url_override(None)

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
