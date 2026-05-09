"""Rooms router with swipe transaction integrity.

This router handles all room-related routes including the critical swipe handler
with BEGIN IMMEDIATE transaction for proper race condition prevention.

Per D-12: The swipe handler's BEGIN IMMEDIATE transaction is preserved.
Per D-13: Swipe handler uses the async DBUoW bridge instead of a direct sync
request-scoped connection dependency.
"""

import asyncio
import json
import logging
import random
import time
import traceback

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.dependencies import AuthUser, DBUoW, get_provider, require_auth
from jellyswipe.repositories.rooms import RoomRepository
from jellyswipe.services.room_lifecycle import (
    EmptyDeckError,
    RoomLifecycleService,
    UniqueRoomCodeExhaustedError,
)
from jellyswipe.services.swipe_match import SwipeMatchService

rooms_router = APIRouter()

_logger = logging.getLogger(__name__)

room_lifecycle_service = RoomLifecycleService()
swipe_match_service = SwipeMatchService()


# ============================================================================
# Module-level helpers (per D-11)
# ============================================================================


def make_error_response(
    message: str, status_code: int, request: Request, extra_fields: dict = None
) -> XSSSafeJSONResponse:
    """Create an error response with request_id."""
    if status_code >= 500:
        message = "Internal server error"
    body = {"error": message}
    body["request_id"] = getattr(request.state, "request_id", "unknown")
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    """Log exception with request context."""
    log_data = {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "route": request.url.path,
        "method": request.method,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "stack_trace": traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    logging.getLogger().error("unhandled_exception", extra=log_data)


# ============================================================================
# Room routes
# ============================================================================


@rooms_router.post("/room")
async def create_room(
    request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Create a new room with setup choices.

    Accepts JSON body: {"movies": true, "tv_shows": false, "solo": false}
    Backward compat: if body is empty/missing, defaults to movies-only hosted session.
    """
    # Parse setup choices with backward-compatible defaults
    # If body is empty/missing, default to movies-only hosted session
    raw_body = await request.body()
    if not raw_body:
        body = {}
    else:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return XSSSafeJSONResponse(
                content={"error": "Invalid JSON body"},
                status_code=400,
            )
    body = body or {}

    # Validate that boolean fields are actual booleans, not strings or other types
    movies_val = body.get("movies", True)
    tv_shows_val = body.get("tv_shows", False)
    solo_val = body.get("solo", False)

    if not isinstance(movies_val, bool):
        return XSSSafeJSONResponse(
            content={"error": "movies must be a boolean value"},
            status_code=400,
        )
    if not isinstance(tv_shows_val, bool):
        return XSSSafeJSONResponse(
            content={"error": "tv_shows must be a boolean value"},
            status_code=400,
        )
    if not isinstance(solo_val, bool):
        return XSSSafeJSONResponse(
            content={"error": "solo must be a boolean value"},
            status_code=400,
        )

    include_movies = movies_val
    include_tv_shows = tv_shows_val
    solo = solo_val

    # Validate: at least one media type must be selected
    if not include_movies and not include_tv_shows:
        return XSSSafeJSONResponse(
            content={"error": "At least one of movies or tv_shows must be true"},
            status_code=400,
        )

    try:
        return await room_lifecycle_service.create_room(
            request.session,
            user.user_id,
            get_provider(),
            uow,
            include_movies=include_movies,
            include_tv_shows=include_tv_shows,
            solo=solo,
        )
    except UniqueRoomCodeExhaustedError:
        return XSSSafeJSONResponse(
            content={"error": "Could not generate unique room code"}, status_code=503
        )


@rooms_router.post("/room/solo")
async def create_solo_room(
    request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Deprecated: POST /room/solo is removed. Use POST /room with {"solo": true} instead."""
    return XSSSafeJSONResponse(
        content={"error": 'Endpoint removed. Use POST /room with {"solo": true}'},
        status_code=404,
    )


@rooms_router.post("/room/{code}/join")
async def join_room_route(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Join an existing room."""
    payload = await room_lifecycle_service.join_room(
        code, request.session, user.user_id, uow
    )
    if payload is None:
        return XSSSafeJSONResponse(content={"error": "Invalid Code"}, status_code=404)
    return payload


@rooms_router.post("/room/{code}/swipe")
async def swipe(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Swipe on a movie with BEGIN IMMEDIATE transaction.

    CRITICAL: BEGIN IMMEDIATE transaction is preserved through the async bridge.
    This prevents race conditions in match detection when multiple users swipe concurrently.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get("media_id")
    if not mid:
        return JSONResponse(content={"error": "media_id required"}, status_code=400)
    mid = str(mid)

    title = None
    thumb = None
    try:
        resolved = get_provider().resolve_item_for_tmdb(mid)
        title = resolved.title
        thumb = f"/proxy?path=jellyfin/{mid}/Primary"
    except RuntimeError as exc:
        logging.getLogger().warning(
            f"Failed to resolve metadata for media_id={mid}: {exc}"
        )

    result = await swipe_match_service.swipe(
        code=code,
        request_session=request.session,
        user_id=user.user_id,
        movie_id=mid,
        direction=data.get("direction"),
        title=title,
        thumb=thumb,
        uow=uow,
    )
    if result is not None:
        body, status_code = result
        return XSSSafeJSONResponse(content=body, status_code=status_code)

    return {"accepted": True}


@rooms_router.get("/matches")
async def get_matches(
    request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Get matches for the current room or history."""
    code = request.session.get("active_room")
    view = request.query_params.get("view")
    return await room_lifecycle_service.get_matches(code, user.user_id, view, uow)


@rooms_router.post("/room/{code}/quit")
async def quit_room(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Quit a room and archive matches."""
    return await room_lifecycle_service.quit_room(
        code, request.session, user.user_id, uow
    )


@rooms_router.post("/matches/delete")
async def delete_match(
    request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Delete a match from history."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get("media_id")
    if not mid:
        return JSONResponse(content={"error": "media_id required"}, status_code=400)
    mid = str(mid)
    return await swipe_match_service.delete_match(
        movie_id=mid,
        user_id=user.user_id,
        active_room=request.session.get("active_room"),
        uow=uow,
    )


@rooms_router.post("/room/{code}/undo")
async def undo_swipe(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Undo the last swipe."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get("media_id")
    if not mid:
        return JSONResponse(content={"error": "media_id required"}, status_code=400)
    mid = str(mid)
    return await swipe_match_service.undo_swipe(
        code=code,
        request_session=request.session,
        user_id=user.user_id,
        movie_id=mid,
        uow=uow,
    )


@rooms_router.get("/room/{code}/deck")
async def get_deck(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Get a page of movies from the deck."""
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        return XSSSafeJSONResponse(
            content={"error": "Invalid page parameter"}, status_code=400
        )
    return await room_lifecycle_service.get_deck(code, user.user_id, page, uow)


@rooms_router.post("/room/{code}/genre")
async def set_genre(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Set the genre filter for the room and reload the deck."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    genre = data.get("genre")
    if not genre:
        return XSSSafeJSONResponse(content={"error": "Genre required"}, status_code=400)
    try:
        new_list = await room_lifecycle_service.set_genre(
            code, genre, get_provider(), uow
        )
        return new_list
    except EmptyDeckError as e:
        return XSSSafeJSONResponse(content={"error": str(e)}, status_code=400)


@rooms_router.get("/room/{code}/status")
async def room_status(
    code: str, _request: Request, uow: DBUoW, _user: AuthUser = Depends(require_auth)
):
    """Get the current status of the room."""
    return await room_lifecycle_service.get_status(code, uow)


@rooms_router.get("/room/{code}/stream")
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
    """SSE stream for room state changes.

    Per D-01: outer handler is sync def; only the inner generator is async.
    Per D-07: request is closed over from outer signature for disconnect detection.

    Each poll uses a short-lived async SQLAlchemy session (PAR-05) — no request-scoped UoW
    and no raw sqlite connection spanning the stream lifetime.
    """

    async def generate():
        last_genre = None
        last_ready = None
        last_match_ts = None
        last_hide_watched = None
        POLL = 1.5
        TIMEOUT = 3600
        _last_event_time = time.time()

        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            # D-06: Check disconnect BEFORE DB query — dead clients skip round-trip.
            if await request.is_disconnected():
                break
            try:
                async with get_sessionmaker()() as session:
                    repo = RoomRepository(session)
                    snapshot = await repo.fetch_stream_snapshot(code)

                if snapshot is None:
                    yield {"data": json.dumps({"closed": True})}
                    return

                ready = snapshot.ready
                genre = snapshot.genre
                solo = snapshot.solo
                last_match = snapshot.last_match
                match_ts = snapshot.last_match_ts
                hide_watched = snapshot.hide_watched

                payload = {}
                if ready != last_ready:
                    payload["ready"] = ready
                    payload["solo"] = solo
                    last_ready = ready
                if genre != last_genre:
                    payload["genre"] = genre
                    last_genre = genre
                if hide_watched != last_hide_watched:
                    payload["hide_watched"] = hide_watched
                    last_hide_watched = hide_watched
                if match_ts and match_ts != last_match_ts:
                    payload["last_match"] = last_match
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
                logging.getLogger().warning("SSE poll error for room %s: %s", code, exc)
                delay = POLL + random.uniform(0, 0.5)
                await asyncio.sleep(delay)  # SSE-2: non-blocking even in error path

    # D-03: EventSourceResponse handles text/event-stream media type and SSE framing.
    # D-04: Verify Cache-Control and X-Accel-Buffering headers are present on response.
    return EventSourceResponse(
        generate(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
