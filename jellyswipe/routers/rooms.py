"""Rooms router with swipe transaction integrity.

This router handles all room-related routes including the critical swipe handler
with BEGIN IMMEDIATE transaction for proper race condition prevention.

Per D-12: The swipe handler's BEGIN IMMEDIATE transaction is preserved.
Per D-13: Swipe handler uses the async DBUoW bridge instead of a direct sync
request-scoped connection dependency.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.dependencies import AuthUser, DBUoW, get_provider, require_auth
from jellyswipe.notifier import notifier
from jellyswipe.services.room_lifecycle import (
    EmptyDeckError,
    RoomLifecycleService,
    UniqueRoomCodeExhaustedError,
)
from jellyswipe.services.session_event_stream import session_event_stream
from jellyswipe.services.swipe_match import SwipeMatchService

from jellyswipe.routers._helpers import make_error_response, log_exception  # noqa: F401

rooms_router = APIRouter()

_logger = logging.getLogger(__name__)

room_lifecycle_service = RoomLifecycleService()
swipe_match_service = SwipeMatchService()


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
        result = await room_lifecycle_service.create_room(
            request.session,
            user.user_id,
            get_provider(),
            uow,
            include_movies=include_movies,
            include_tv_shows=include_tv_shows,
            solo=solo,
        )
        # Commit the session to persist session_instances row
        await uow.session.commit()
        return result
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
    # Commit before notifying to ensure events are persisted
    await uow.session.commit()
    notifier.notify(code)
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

    # Commit before notifying to ensure events are persisted
    await uow.session.commit()
    notifier.notify(code)
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
    result = await room_lifecycle_service.quit_room(
        code, request.session, user.user_id, uow
    )
    # Commit before notifying to ensure events are persisted
    await uow.session.commit()
    notifier.notify(code)
    return result


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
        # Commit before notifying to ensure events are persisted
        await uow.session.commit()
        notifier.notify(code)
        return new_list
    except EmptyDeckError as e:
        return XSSSafeJSONResponse(content={"error": str(e)}, status_code=400)


@rooms_router.post("/room/{code}/watched-filter")
async def set_watched_filter_route(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Set the watched filter for the room and reload the deck."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    hide_watched = data.get("hide_watched")
    if hide_watched is None:
        return XSSSafeJSONResponse(
            content={"error": "hide_watched required"}, status_code=400
        )
    if not isinstance(hide_watched, bool):
        return XSSSafeJSONResponse(
            content={"error": "hide_watched must be a boolean"}, status_code=400
        )
    try:
        result = await room_lifecycle_service.set_watched_filter(
            code, hide_watched, get_provider(), uow
        )
        # Commit before notifying to ensure events are persisted
        await uow.session.commit()
        notifier.notify(code)
        return result
    except EmptyDeckError:
        return XSSSafeJSONResponse(
            content={"error": "No unwatched items available"}, status_code=422
        )


@rooms_router.get("/room/{code}/status")
async def room_status(
    code: str, _request: Request, uow: DBUoW, _user: AuthUser = Depends(require_auth)
):
    """Get the current status of the room."""
    return await room_lifecycle_service.get_status(code, uow)


@rooms_router.get("/room/{code}/stream")
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
    """SSE stream for session events. Event-driven with replay support."""

    async def generate():
        # Resolve instance and room
        async with get_sessionmaker()() as session:
            uow = DatabaseUnitOfWork(session)
            instance = await uow.session_instances.get_by_pairing_code(code)
            if instance is None or instance.status == "closed":
                yield {
                    "data": json.dumps(
                        {"event_type": "session_reset", "reason": "instance_changed"}
                    )
                }
                return
            room = await uow.rooms.get_room(code)

        cursor = request.headers.get("Last-Event-ID") or request.query_params.get(
            "after_event_id"
        )
        cursor = int(cursor) if cursor else None

        async for event in session_event_stream(
            code=code,
            instance_id=instance.instance_id,
            room=room,
            cursor=cursor,
            sessionmaker_factory=get_sessionmaker(),
            notifier=notifier,
            is_disconnected=request.is_disconnected,
        ):
            yield event

    # D-03: EventSourceResponse handles text/event-stream media type and SSE framing.
    # D-04: Verify Cache-Control and X-Accel-Buffering headers are present on response.
    return EventSourceResponse(
        generate(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
