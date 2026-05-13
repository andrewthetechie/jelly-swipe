"""FastAPI dependency injection layer — Phase 32.

Exports AuthUser dataclass and Depends()-compatible callables for:
- Authentication (require_auth, destroy_session_dep)
- Database access (get_db_uow, DBUoW)
- Rate limiting (check_rate_limit)
- Jellyfin provider singleton (get_provider)
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Optional

from fastapi import Depends, HTTPException, Request

import logging
import threading

import jellyswipe.auth as auth
from jellyswipe.config import AppConfig, get_config
from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.rate_limiter import rate_limiter

if TYPE_CHECKING:
    from jellyswipe.jellyfin_library import JellyfinLibraryProvider

_logger = logging.getLogger(__name__)

_provider_lock = threading.Lock()
_provider_singleton: Optional["JellyfinLibraryProvider"] = None


@dataclass
class AuthUser:
    """Authenticated user data for FastAPI dependency injection."""

    jf_token: str
    user_id: str


async def get_db_uow():
    """Yield a request-scoped async unit of work.

    The caller owns commit. This dependency owns session lifecycle
    (open, rollback-on-error, close) but NOT commit.
    """
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
    except Exception:
        await session.rollback()
        raise
    finally:
        if session.dirty or session.new or session.deleted:
            _logger.warning(
                "UoW session closed with uncommitted dirty/new/deleted "
                "objects — writes were silently lost. Did you forget to commit?"
            )
        await session.close()


DBUoW = Annotated[DatabaseUnitOfWork, Depends(get_db_uow, scope="function")]


_RATE_LIMITS = {
    "get-trailer": 200,
    "cast": 200,
    "watchlist/add": 300,
    "proxy": 200,
}


def _infer_endpoint_key(path: str) -> Optional[str]:
    """Infer rate limit key from request path using prefix segment matching.

    Checks compound keys (e.g. 'watchlist/add') first, then single-segment keys.
    Returns None if no match found.
    """
    parts = path.lstrip("/").split("/", 2)
    # Check compound key first (e.g. 'watchlist/add')
    if len(parts) >= 2:
        compound = f"{parts[0]}/{parts[1]}"
        if compound in _RATE_LIMITS:
            return compound
    # Check single-segment key
    if parts and parts[0] in _RATE_LIMITS:
        return parts[0]
    return None


def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces rate limiting.

    Raises HTTPException(429) if limit exceeded, passes through otherwise.
    """
    key = _infer_endpoint_key(request.url.path)
    if key is None:
        return  # No limit for this path

    ip = request.client.host if request.client else "unknown"
    allowed, _retry_after = rate_limiter.check(key, ip, _RATE_LIMITS[key])

    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


async def require_auth(request: Request, uow: DBUoW) -> AuthUser:
    """FastAPI dependency that requires authentication."""
    prior_session_id = request.session.get("session_id")
    record = await auth.get_current_token(request.session, uow)
    if record is not None:
        return AuthUser(jf_token=record.jf_token, user_id=record.user_id)

    if prior_session_id is not None:
        auth.clear_session_state(request.session)
        request.state.clear_session_cookie = True

    raise HTTPException(status_code=401, detail="Authentication required")


async def destroy_session_dep(request: Request, uow: DBUoW) -> None:
    """FastAPI dependency that destroys the current session.

    Calls auth.destroy_session(request.session).
    """
    await auth.destroy_session(request.session, uow)


async def get_provider(config: AppConfig = Depends(get_config)):
    """FastAPI dependency that returns the JellyfinLibraryProvider singleton."""
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton

    with _provider_lock:
        if _provider_singleton is None:
            from jellyswipe.jellyfin_library import JellyfinLibraryProvider

            _provider_singleton = JellyfinLibraryProvider(config.jellyfin_url)

    return _provider_singleton


def reset_provider_singleton() -> None:
    """Reset the provider singleton on application shutdown."""
    global _provider_singleton
    _provider_singleton = None


__all__ = [
    "AuthUser",
    "require_auth",
    "get_db_uow",
    "DBUoW",
    "check_rate_limit",
    "destroy_session_dep",
    "get_provider",
]
