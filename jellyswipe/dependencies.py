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
    # Stub implementation - will fail tests
    raise NotImplementedError("require_auth not implemented")


def get_db_dep():
    """Yield dependency for database connections.

    Wraps get_db_closing() to provide a connection that auto-closes.
    """
    # Stub implementation - will fail tests
    raise NotImplementedError("get_db_dep not implemented")


DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]


_RATE_LIMITS = {
    'get-trailer': 200,
    'cast': 200,
    'watchlist/add': 300,
    'proxy': 200,
}


def _infer_endpoint_key(path: str) -> Optional[str]:
    """Infer rate limit key from request path.

    Returns the first key from _RATE_LIMITS that is contained in the path.
    Returns None if no match found.
    """
    # Stub implementation - will fail tests
    raise NotImplementedError("_infer_endpoint_key not implemented")


def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces rate limiting.

    Raises HTTPException(429) if limit exceeded, passes through otherwise.
    """
    # Stub implementation - will fail tests
    raise NotImplementedError("check_rate_limit not implemented")


def destroy_session_dep(request: Request) -> None:
    """FastAPI dependency that destroys the current session.

    Calls auth.destroy_session(request.session).
    """
    # Stub implementation - will fail tests
    raise NotImplementedError("destroy_session_dep not implemented")


def get_provider():
    """FastAPI dependency that returns the JellyfinLibraryProvider singleton.

    Uses lazy import to avoid circular dependency with __init__.py.
    """
    # Stub implementation - will fail tests
    raise NotImplementedError("get_provider not implemented")


__all__ = [
    "AuthUser",
    "require_auth",
    "get_db_dep",
    "DBConn",
    "check_rate_limit",
    "destroy_session_dep",
    "get_provider",
]
