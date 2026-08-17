"""FastAPI dependency injection layer — Phase 32.

Exports AuthUser dataclass and Depends()-compatible callables for:
- Authentication (require_auth)
- Database access (get_db_uow, DBUoW)
- Rate limiting (check_rate_limit)
- Jellyfin provider singleton (get_provider)
"""

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Optional

from fastapi import Depends, HTTPException, Request

from jellyswipe.config import AppConfig, get_config
from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.rate_limiter import rate_limiter

if TYPE_CHECKING:
    from jellyswipe.jellyfin.client import JellyfinClient
    from jellyswipe.jellyfin.library import JellyfinLibrary
    from jellyswipe.jellyfin.vault import JellyfinVault
    from jellyswipe.jellyfin.watchlist import JellyfinWatchlistWriter

_logger = logging.getLogger(__name__)

# Split-by-role Jellyfin integration singletons (ADR-0001). All three role
# objects share one async HTTP client and are constructed lazily on first
# dependency resolution, then reset (client closed) on application shutdown.
# ``_provider_singleton`` is retained under its historical name — it now holds
# the JellyfinLibrary (DeckProvider adapter) role, so existing test fixtures
# that seed ``deps._provider_singleton`` keep working unchanged.
_client_lock = threading.Lock()
_singletons_built: bool = False
_client_singleton: Optional["JellyfinClient"] = None
_vault_singleton: Optional["JellyfinVault"] = None
_provider_singleton: Optional["JellyfinLibrary"] = None
_watchlist_singleton: Optional["JellyfinWatchlistWriter"] = None


def _build_jellyfin_singletons(config: AppConfig) -> None:
    """Construct the shared client + role singletons if not already present."""
    global \
        _singletons_built, \
        _client_singleton, \
        _vault_singleton, \
        _provider_singleton, \
        _watchlist_singleton
    if _singletons_built:
        return
    with _client_lock:
        if _singletons_built:
            return
        from jellyswipe.jellyfin.client import JellyfinClient
        from jellyswipe.jellyfin.library import JellyfinLibrary
        from jellyswipe.jellyfin.vault import JellyfinVault
        from jellyswipe.jellyfin.watchlist import JellyfinWatchlistWriter

        _client_singleton = JellyfinClient(
            config.jellyfin_url,
            device_id=config.jellyfin_device_id,
        )
        _vault_singleton = JellyfinVault(
            _client_singleton,
            api_key=config.jellyfin_api_key,
            device_id=config.jellyfin_device_id,
        )
        _provider_singleton = JellyfinLibrary(_vault_singleton)
        _watchlist_singleton = JellyfinWatchlistWriter(_vault_singleton)
        _singletons_built = True


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


def _infer_endpoint_key(path: str) -> str | None:
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
    record = (
        await uow.auth_sessions.get_by_session_id(prior_session_id)
        if prior_session_id
        else None
    )
    if record is not None:
        return AuthUser(jf_token=record.jf_token, user_id=record.user_id)

    if prior_session_id is not None:
        request.session.clear()
        request.state.clear_session_cookie = True

    raise HTTPException(status_code=401, detail="Authentication required")


async def get_library(config: AppConfig = Depends(get_config)):
    """FastAPI dependency returning the shared JellyfinLibrary (DeckProvider adapter)."""
    _build_jellyfin_singletons(config)
    return _provider_singleton


async def get_vault(config: AppConfig = Depends(get_config)):
    """FastAPI dependency returning the shared JellyfinVault."""
    _build_jellyfin_singletons(config)
    return _vault_singleton


async def get_watchlist(config: AppConfig = Depends(get_config)):
    """FastAPI dependency returning the shared JellyfinWatchlistWriter."""
    _build_jellyfin_singletons(config)
    return _watchlist_singleton


async def get_provider(config: AppConfig = Depends(get_config)):
    """Backward-compatible alias returning the JellyfinLibrary (deck provider) singleton.

    Deprecated: use get_library() directly. This alias exists only for test
    fixtures that seed deps._provider_singleton and cannot yet be updated.
    """
    return await get_library(config)


async def reset_provider_singleton() -> None:
    """Close the Jellyfin client and reset role singletons on application shutdown."""
    global \
        _singletons_built, \
        _client_singleton, \
        _vault_singleton, \
        _provider_singleton, \
        _watchlist_singleton
    client = _client_singleton
    _singletons_built = False
    _client_singleton = None
    _vault_singleton = None
    _provider_singleton = None
    _watchlist_singleton = None
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            _logger.warning("jellyfin_client_close_failed", exc_info=True)


__all__ = [
    "AuthUser",
    "DBUoW",
    "check_rate_limit",
    "get_db_uow",
    "get_library",
    "get_provider",
    "get_vault",
    "get_watchlist",
    "require_auth",
]
