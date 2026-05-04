"""FastAPI dependency injection layer — Phase 32.

Exports AuthUser dataclass and Depends()-compatible callables for:
- Authentication (require_auth, destroy_session_dep)
- Database access (get_db_dep, DBConn)
- Rate limiting (check_rate_limit)
- Jellyfin provider singleton (get_provider)
"""

from dataclasses import dataclass
from typing import Annotated, Optional

import sqlite3
from fastapi import Depends, HTTPException, Request

import jellyswipe.auth as auth
from jellyswipe.db import get_db_closing
from jellyswipe.rate_limiter import rate_limiter


@dataclass
class AuthUser:
    """Authenticated user data for FastAPI dependency injection."""
    jf_token: str
    user_id: str


def require_auth(request: Request) -> AuthUser:
    """FastAPI dependency that requires authentication.

    Returns AuthUser if session is valid, raises HTTPException(401) otherwise.
    """
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)


def get_db_dep():
    """Yield dependency for database connections.

    Wraps get_db_closing() to provide a connection that auto-closes.
    """
    with get_db_closing() as conn:
        yield conn


DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]


_RATE_LIMITS = {
    'get-trailer': 200,
    'cast': 200,
    'watchlist/add': 300,
    'proxy': 200,
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


def destroy_session_dep(request: Request) -> None:
    """FastAPI dependency that destroys the current session.

    Calls auth.destroy_session(request.session).
    """
    auth.destroy_session(request.session)


def get_provider():
    """FastAPI dependency that returns the JellyfinLibraryProvider singleton.

    Uses lazy import to avoid circular dependency with __init__.py.
    """
    # Lazy import to avoid circular import with __init__.py
    import jellyswipe as _app

    if _app._provider_singleton is None:
        from jellyswipe.jellyfin_library import JellyfinLibraryProvider
        _app._provider_singleton = JellyfinLibraryProvider(_app._JELLYFIN_URL)

    return _app._provider_singleton


__all__ = [
    "AuthUser",
    "require_auth",
    "get_db_dep",
    "DBConn",
    "check_rate_limit",
    "destroy_session_dep",
    "get_provider",
]
