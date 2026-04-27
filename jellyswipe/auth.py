"""Auth module for Jelly Swipe — token vault CRUD and @login_required decorator.

Server-side identity resolution: session cookie → vault lookup.
This module is the core building block for Phase 24's route refactoring.
"""

from flask import session, g, jsonify
from functools import wraps
from typing import Optional, Tuple
import secrets
from datetime import datetime, timezone

from jellyswipe.db import get_db, cleanup_expired_tokens


def create_session(jf_token: str, jf_user_id: str) -> str:
    """Store token in vault, set session cookie, return session_id.

    Generates a 64-char hex session_id, cleans up expired tokens,
    inserts the new session into user_tokens, and sets session['session_id'].

    Per D-03: cleanup runs on every new session creation.
    Per D-10: session_id is secrets.token_hex(32).
    Per D-15: created_at uses ISO 8601 string format.
    """
    session_id = secrets.token_hex(32)
    created_at = datetime.now(timezone.utc).isoformat()

    # Clean up expired tokens before inserting the new session
    cleanup_expired_tokens()

    # Insert into user_tokens
    with get_db() as conn:
        conn.execute(
            'INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) '
            'VALUES (?, ?, ?, ?)',
            (session_id, jf_token, jf_user_id, created_at)
        )

    # Set session cookie
    session['session_id'] = session_id

    return session_id


def get_current_token() -> Optional[Tuple[str, str]]:
    """Return (jf_token, jf_user_id) for current session, or None.

    Reads session_id from Flask session cookie, looks up the corresponding
    token in the user_tokens vault.

    Per D-14: trusts the vault entry — no Jellyfin API validation on every request.
    Per D-10: returns None for anonymous sessions and missing vault entries.
    """
    sid = session.get('session_id')
    if sid is None:
        return None

    with get_db() as conn:
        row = conn.execute(
            'SELECT jellyfin_token, jellyfin_user_id FROM user_tokens WHERE session_id = ?',
            (sid,)
        ).fetchone()

    if row is None:
        return None

    return (row['jellyfin_token'], row['jellyfin_user_id'])


def destroy_session():
    """Clear session cookie and delete vault entry.

    Per CLNT-01: logout removes the server-side vault entry and
    clears the session cookie so no auth state remains.
    """
    sid = session.get('session_id')
    if sid:
        with get_db() as conn:
            conn.execute('DELETE FROM user_tokens WHERE session_id = ?', (sid,))
        session.pop('session_id', None)


def login_required(f):
    """Decorator that requires authenticated session.

    Per D-09: populates g.user_id and g.jf_token for every authenticated request.
    Per D-14: trusts vault lookup only, no external API calls.
    Unauthenticated requests get {'error': 'Authentication required'}, 401.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        result = get_current_token()
        if not result:
            return jsonify({'error': 'Authentication required'}), 401
        g.jf_token, g.user_id = result
        return f(*args, **kwargs)
    return decorated
