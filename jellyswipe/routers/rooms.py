"""Rooms router with swipe transaction integrity.

This router handles all room-related routes including the critical swipe handler
with BEGIN IMMEDIATE transaction for proper race condition prevention.

Per D-12: The swipe handler's BEGIN IMMEDIATE transaction is verbatim preserved.
Per D-13: Swipe handler uses DBConn dependency instead of direct get_db_closing()
to fix connection leak (CR-01).
"""

import asyncio
import json
import logging
import random
import secrets
import sqlite3
import time
import traceback
import typing

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.config import JELLYFIN_URL
from jellyswipe.dependencies import AuthUser, DBConn, check_rate_limit, get_db_dep, get_provider, require_auth
from jellyswipe.db import get_db_closing

rooms_router = APIRouter()

_logger = logging.getLogger(__name__)


# ============================================================================
# Module-level helpers (per D-11)
# ============================================================================

def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> XSSSafeJSONResponse:
    """Create an error response with request_id."""
    if status_code >= 500:
        message = 'Internal server error'
    body = {'error': message}
    body['request_id'] = getattr(request.state, 'request_id', 'unknown')
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    """Log exception with request context."""
    log_data = {
        'request_id': getattr(request.state, 'request_id', 'unknown'),
        'route': request.url.path,
        'method': request.method,
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'stack_trace': traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    _logger.error("unhandled_exception", extra=log_data)


def _get_cursor(conn, code, user_id):
    """Get user's deck cursor position. Returns 0 if no position stored."""
    room = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
    if room and room['deck_position']:
        positions = json.loads(room['deck_position'])
        return positions.get(user_id, 0)
    return 0


def _set_cursor(conn, code, user_id, position):
    """Set user's deck cursor position."""
    room = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
    positions = json.loads(room['deck_position']) if room and room['deck_position'] else {}
    positions[user_id] = position
    conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                 (json.dumps(positions), code))


def _resolve_movie_meta(movie_data_json, movie_id):
    """Resolve rating, duration, year from stored movie_data JSON (per D-09, D-10)."""
    try:
        movies = json.loads(movie_data_json)
        for m in movies:
            if str(m.get('id', '')) == str(movie_id):
                rating = m.get('rating')
                duration = m.get('duration')
                year = m.get('year')
                return {
                    'rating': str(rating) if rating is not None else '',
                    'duration': duration or '',
                    'year': str(year) if year is not None else '',
                }
    except (json.JSONDecodeError, TypeError):
        pass
    return {'rating': '', 'duration': '', 'year': ''}


# ============================================================================
# Room routes
# ============================================================================

@rooms_router.post('/room')
def create_room(request: Request, user: AuthUser = Depends(require_auth)):
    """Create a new room with a unique pairing code."""
    # Generate cryptographically secure pairing code with collision detection
    for _ in range(10):
        pairing_code = str(secrets.randbelow(9000) + 1000)
        with get_db_closing() as conn:
            existing = conn.execute(
                'SELECT 1 FROM rooms WHERE pairing_code = ?', (pairing_code,)
            ).fetchone()
            if not existing:
                movie_list = get_provider().fetch_deck()
                conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                             (pairing_code, json.dumps(movie_list), 0, 'All', 0))
                conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                             (json.dumps({user.user_id: 0}), pairing_code))
                request.session['active_room'] = pairing_code
                request.session['solo_mode'] = False
                return {'pairing_code': pairing_code}
    return XSSSafeJSONResponse(content={'error': 'Could not generate unique room code'}, status_code=503)


@rooms_router.post('/room/solo')
def create_solo_room(request: Request, user: AuthUser = Depends(require_auth)):
    """Create a solo room (single-player mode)."""
    # Generate cryptographically secure pairing code with collision detection
    for _ in range(10):
        pairing_code = str(secrets.randbelow(9000) + 1000)
        with get_db_closing() as conn:
            existing = conn.execute(
                'SELECT 1 FROM rooms WHERE pairing_code = ?', (pairing_code,)
            ).fetchone()
            if not existing:
                movie_list = get_provider().fetch_deck()
                conn.execute(
                    'INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                    (pairing_code, json.dumps(movie_list), 1, 'All', 1)
                )
                conn.execute(
                    'UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                    (json.dumps({user.user_id: 0}), pairing_code)
                )
                request.session['active_room'] = pairing_code
                request.session['solo_mode'] = True
                return {'pairing_code': pairing_code}
    return XSSSafeJSONResponse(content={'error': 'Could not generate unique room code'}, status_code=503)


@rooms_router.post('/room/{code}/join')
def join_room(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Join an existing room."""
    with get_db_closing() as conn:
        room = conn.execute('SELECT * FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        if room:
            conn.execute('UPDATE rooms SET ready = 1 WHERE pairing_code = ?', (code,))
            room2 = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            positions = json.loads(room2['deck_position']) if room2 and room2['deck_position'] else {}
            positions[user.user_id] = 0
            conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                         (json.dumps(positions), code))
            request.session['active_room'] = code
            request.session['solo_mode'] = False
            return {'status': 'success'}
    return XSSSafeJSONResponse(content={'error': 'Invalid Code'}, status_code=404)


@rooms_router.post('/room/{code}/swipe')
async def swipe(
    code: str,
    request: Request,
    conn: DBConn,
    user: AuthUser = Depends(require_auth)
):
    """Swipe on a movie with BEGIN IMMEDIATE transaction.

    CRITICAL: BEGIN IMMEDIATE transaction — verbatim from Phase 31 __init__.py. Do not refactor.
    This prevents race conditions in match detection when multiple users swipe concurrently.

    Per D-13: Uses DBConn dependency instead of get_db_closing() to fix connection leak (CR-01).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get('movie_id')
    if not mid:
        return JSONResponse(content={'error': 'movie_id required'}, status_code=400)
    mid = str(mid)

    title = None
    thumb = None
    try:
        resolved = get_provider().resolve_item_for_tmdb(mid)
        title = resolved.title
        thumb = f"/proxy?path=jellyfin/{mid}/Primary"
    except RuntimeError as exc:
        _logger.warning(f"Failed to resolve metadata for movie_id={mid}: {exc}")

    # Switch to autocommit mode so that explicit BEGIN IMMEDIATE does not conflict
    # with the implicit transaction started by get_db_closing()'s `with conn:` wrapper.
    # Without this, SQLite raises "cannot start a transaction within a transaction".
    conn.isolation_level = None
    # Use BEGIN IMMEDIATE for proper transaction isolation and to prevent race conditions
    conn.execute('BEGIN IMMEDIATE')
    try:
        # Insert swipe record
        conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)',
                     (code, mid, user.user_id, data.get('direction'), request.session.get('session_id')))

        # Update cursor position
        current_pos = _get_cursor(conn, code, user.user_id)
        _set_cursor(conn, code, user.user_id, current_pos + 1)

        if data.get('direction') == 'right':
            if title is not None and thumb is not None:
                room = conn.execute('SELECT solo_mode, movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()

                meta = _resolve_movie_meta(room['movie_data'], mid) if room else {'rating': '', 'duration': '', 'year': ''}
                deep_link = f"{JELLYFIN_URL}/web/#/details?id={mid}" if JELLYFIN_URL else ''

                if room and room['solo_mode']:
                    conn.execute(
                        'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                        (code, mid, title, thumb, user.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
                    )
                    match_data = json.dumps({
                        'type': 'match', 'title': title, 'thumb': thumb,
                        'movie_id': mid, 'rating': meta['rating'],
                        'duration': meta['duration'], 'year': meta['year'],
                        'deep_link': deep_link, 'ts': time.time()
                    })
                    conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))
                else:
                    # Multi-user mode: check for other user's swipe with proper locking.
                    # Use (? IS NULL OR session_id != ?) to handle NULL session_id correctly:
                    # SQLite's != NULL always evaluates to NULL (never true), so without this
                    # guard the match query returns nothing when the current session has no
                    # session_id set (e.g., sessions injected by tests or joined without swiping).
                    _session_id = request.session.get('session_id')
                    other_swipe = conn.execute(
                        'SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND (? IS NULL OR session_id != ?)',
                        (code, mid, _session_id, _session_id)
                    ).fetchone()

                    if other_swipe:
                        conn.execute(
                            'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                            (code, mid, title, thumb, user.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
                        )

                        if other_swipe['user_id'] and other_swipe['user_id'] != user.user_id:
                            conn.execute(
                                'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                                (code, mid, title, thumb, other_swipe['user_id'], deep_link, meta['rating'], meta['duration'], meta['year'])
                            )

                            match_data = json.dumps({
                                'type': 'match', 'title': title, 'thumb': thumb,
                                'movie_id': mid, 'rating': meta['rating'],
                                'duration': meta['duration'], 'year': meta['year'],
                                'deep_link': deep_link, 'ts': time.time()
                            })
                            conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))

        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    return {'accepted': True}


@rooms_router.get('/matches')
def get_matches(request: Request, user: AuthUser = Depends(require_auth)):
    """Get matches for the current room or history."""
    code = request.session.get('active_room')
    view = request.query_params.get('view')

    with get_db_closing() as conn:
        if view == 'history':
            rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE status = "archived" AND user_id = ?', (user.user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?', (code, user.user_id)).fetchall()
        return [dict(row) for row in rows]


@rooms_router.post('/room/{code}/quit')
def quit_room(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Quit a room and archive matches."""
    with get_db_closing() as conn:
        conn.execute('DELETE FROM rooms WHERE pairing_code = ?', (code,))
        conn.execute('DELETE FROM swipes WHERE room_code = ?', (code,))
        conn.execute('UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"', (code,))
    request.session.pop('active_room', None)
    request.session.pop('solo_mode', None)
    return {'status': 'session_ended'}


@rooms_router.post('/matches/delete')
async def delete_match(request: Request, user: AuthUser = Depends(require_auth)):
    """Delete a match from history."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get('movie_id')
    if not mid:
        return JSONResponse(content={'error': 'movie_id required'}, status_code=400)
    mid = str(mid)
    with get_db_closing() as conn:
        conn.execute('DELETE FROM matches WHERE movie_id = ? AND user_id = ?', (mid, user.user_id))
    return {'status': 'deleted'}


@rooms_router.post('/room/{code}/undo')
async def undo_swipe(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Undo the last swipe."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get('movie_id')
    if not mid:
        return JSONResponse(content={'error': 'movie_id required'}, status_code=400)
    mid = str(mid)
    with get_db_closing() as conn:
        conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND session_id = ?', (code, mid, request.session.get('session_id')))
        conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, user.user_id))
    return {'status': 'undone'}


@rooms_router.get('/room/{code}/deck')
def get_deck(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Get a page of movies from the deck."""
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        return XSSSafeJSONResponse(content={'error': 'Invalid page parameter'}, status_code=400)
    page_size = 20
    with get_db_closing() as conn:
        cursor_pos = _get_cursor(conn, code, user.user_id)
        room = conn.execute('SELECT movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        if not room:
            return []
        movies = json.loads(room['movie_data'])
        start = cursor_pos + (page - 1) * page_size
        end = start + page_size
        page_items = movies[start:end]
        return page_items


@rooms_router.post('/room/{code}/genre')
async def set_genre(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Set the genre filter for the room and reload the deck."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    genre = data.get('genre')
    if not genre:
        return XSSSafeJSONResponse(content={'error': 'Genre required'}, status_code=400)
    new_list = get_provider().fetch_deck(genre)
    with get_db_closing() as conn:
        conn.execute('UPDATE rooms SET movie_data = ?, deck_position = ?, current_genre = ? WHERE pairing_code = ?',
                     (json.dumps(new_list), json.dumps({}), genre, code))
    return new_list


@rooms_router.get('/room/{code}/status')
def room_status(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    """Get the current status of the room."""
    with get_db_closing() as conn:
        room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        if room:
            last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
            return {'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match}
        return {'ready': False}


@rooms_router.get('/room/{code}/stream')
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
    """SSE stream for room state changes.

    Per D-01: outer handler is sync def; only the inner generator is async.
    Per D-07: request is closed over from outer signature for disconnect detection.
    """
    async def generate():
        last_genre = None
        last_ready = None
        last_match_ts = None
        POLL = 1.5
        TIMEOUT = 3600
        _last_event_time = time.time()

        # Per D-10, SQL-1: Direct connection scoped to stream lifetime.
        # get_db_dep() is request-scoped and cannot serve a stream lasting up to 3600s.
        # check_same_thread=False: Uvicorn may resume the async generator on a
        # different thread than the one that created the connection.
        import jellyswipe.db
        conn = sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            deadline = time.time() + TIMEOUT
            while time.time() < deadline:
                # D-06: Check disconnect BEFORE DB query — dead clients skip round-trip.
                if await request.is_disconnected():
                    break
                try:
                    row = conn.execute(
                        'SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?',
                        (code,)
                    ).fetchone()

                    if row is None:
                        yield {"data": json.dumps({'closed': True})}
                        return

                    ready = bool(row['ready'])
                    genre = row['current_genre']
                    solo = bool(row['solo_mode'])
                    last_match = json.loads(row['last_match_data']) if row['last_match_data'] else None
                    match_ts = last_match['ts'] if last_match else None

                    payload = {}
                    if ready != last_ready:
                        payload['ready'] = ready
                        payload['solo'] = solo
                        last_ready = ready
                    if genre != last_genre:
                        payload['genre'] = genre
                        last_genre = genre
                    if match_ts and match_ts != last_match_ts:
                        payload['last_match'] = last_match
                        last_match_ts = match_ts

                    if payload:
                        yield {"data": json.dumps(payload)}
                        _last_event_time = time.time()
                    elif time.time() - _last_event_time >= 15:
                        # SSE-5: EventSourceResponse comment syntax for heartbeat ping
                        yield {"comment": "ping"}
                        _last_event_time = time.time()

                    delay = POLL + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)  # SSE-2: non-blocking sleep
                except Exception as exc:
                    # D-09, SSE-4: Re-raise CancelledError so try/finally can clean up.
                    # Do NOT swallow CancelledError — it is the asyncio disconnect signal.
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    _logger.warning("SSE poll error for room %s: %s", code, exc)
                    delay = POLL + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)  # SSE-2: non-blocking even in error path
        finally:
            conn.close()  # D-11: guaranteed cleanup regardless of exit path

    # D-03: EventSourceResponse handles text/event-stream media type and SSE framing.
    # D-04: Verify Cache-Control and X-Accel-Buffering headers are present on response.
    # If EventSourceResponse does not set them automatically, pass explicitly:
    #   return EventSourceResponse(generate(), headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    return EventSourceResponse(generate(), headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
