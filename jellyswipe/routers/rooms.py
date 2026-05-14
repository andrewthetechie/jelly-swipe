"""Rooms router with swipe transaction integrity.

This router handles all room-related routes including the critical swipe handler
with BEGIN IMMEDIATE transaction for proper race condition prevention.

Per D-12: The swipe handler's BEGIN IMMEDIATE transaction is preserved.
Per D-13: Swipe handler uses the async DBUoW bridge instead of a direct sync
request-scoped connection dependency.
"""

import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.config import AppConfig, get_config
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
from jellyswipe.services.session_match_mutation import (
    CatalogFacts,
    DeleteChanged,
    SessionActor,
    SessionMatchMutation,
    SwipeRejected,
    UndoChanged,
)

from jellyswipe.routers._helpers import (
    commit_and_wake,
)  # noqa: F401
from jellyswipe.schemas.common import ErrorResponse
from jellyswipe.schemas.rooms import (
    CreateRoomRequest,
    CreateRoomResponse,
    DeleteMatchRequest,
    DeleteMatchResponse,
    MatchListResponse,
    JoinRoomResponse,
    QuitRoomResponse,
    RoomStatusResponse,
    SetGenreRequest,
    SetWatchedFilterRequest,
    SwipeRequest,
    SwipeResponse,
    UndoRequest,
    UndoResponse,
)

rooms_router = APIRouter()

_logger = logging.getLogger(__name__)

room_lifecycle_service = RoomLifecycleService()
session_match_mutation = SessionMatchMutation()


# ============================================================================
# Room routes
# ============================================================================


@rooms_router.post(
    "/room",
    tags=["Rooms"],
    response_model=CreateRoomResponse,
    responses={
        200: {"description": "Room created successfully"},
        422: {
            "description": "Validation error — check boolean fields and media type selection"
        },
        503: {
            "model": ErrorResponse,
            "description": "Could not generate a unique room code after 10 attempts",
        },
    },
    summary="Create a new room",
)
async def create_room(
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    provider=Depends(get_provider),
    body: Optional[CreateRoomRequest] = None,
):
    """Create a new room with setup choices.

    All boolean fields (``movies``, ``tv_shows``, ``solo``) must be JSON
    booleans — not strings. Sending ``"true"`` instead of ``true`` will
    result in a 422 validation error.

    If the request body is omitted entirely, defaults to a movies-only hosted
    session (``movies=true``, ``tv_shows=false``, ``solo=false``).

    At least one of ``movies`` or ``tv_shows`` must be ``true``.
    """
    resolved = body or CreateRoomRequest()

    try:
        result = await room_lifecycle_service.create_room(
            request.session,
            user.user_id,
            provider,
            uow,
            include_movies=resolved.movies,
            include_tv_shows=resolved.tv_shows,
            solo=resolved.solo,
        )
        await uow.session.commit()
        return result
    except UniqueRoomCodeExhaustedError:
        return XSSSafeJSONResponse(
            content={"error": "Could not generate unique room code"}, status_code=503
        )


@rooms_router.post("/room/solo", include_in_schema=False)
async def create_solo_room(
    request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Deprecated: POST /room/solo is removed. Use POST /room with {"solo": true} instead."""
    return XSSSafeJSONResponse(
        content={"error": 'Endpoint removed. Use POST /room with {"solo": true}'},
        status_code=404,
    )


@rooms_router.post(
    "/room/{code}/join",
    tags=["Rooms"],
    response_model=JoinRoomResponse,
    responses={
        200: {"description": "Successfully joined the room"},
        404: {"model": ErrorResponse, "description": "Room code not found"},
    },
    summary="Join an existing room",
)
async def join_room_route(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Join an existing room by its 4-digit pairing code.

    Sets the caller's session to the joined room and marks the room as ready
    for swiping. A ``session_ready`` event is published so connected SSE
    clients are notified immediately.
    """
    payload = await room_lifecycle_service.join_room(
        code, request.session, user.user_id, uow
    )
    if payload is None:
        return XSSSafeJSONResponse(content={"error": "Invalid Code"}, status_code=404)
    await commit_and_wake(uow, code)
    return payload


@rooms_router.post(
    "/room/{code}/swipe",
    tags=["Swiping"],
    response_model=SwipeResponse,
    responses={
        200: {"description": "Swipe recorded"},
        404: {
            "model": ErrorResponse,
            "description": "Room not found or swipe rejected",
        },
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Swipe on a media item",
)
async def swipe(
    code: str,
    body: SwipeRequest,
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    config: AppConfig = Depends(get_config),
    provider=Depends(get_provider),
):
    """Submit a swipe (left or right) on a media item within a room.

    Uses a ``BEGIN IMMEDIATE`` transaction to prevent race conditions in match
    detection when multiple users swipe concurrently (see D-12, D-13).

    Returns ``{"accepted": true}`` on success. If the room no longer exists or
    the swipe is otherwise invalid, returns 404.
    """
    mid = str(body.media_id)

    title = None
    thumb = None
    try:
        resolved = provider.resolve_item_for_tmdb(mid)
        title = resolved.title
        thumb = f"/proxy?path=jellyfin/{mid}/Primary"
    except RuntimeError as exc:
        logging.getLogger().warning(
            f"Failed to resolve metadata for media_id={mid}: {exc}"
        )

    actor = SessionActor(
        user_id=user.user_id,
        session_id=request.session.get("session_id"),
        active_room=request.session.get("active_room"),
    )
    catalog = CatalogFacts(title=title, thumb=thumb)
    result = await session_match_mutation.apply_swipe(
        code=code,
        actor=actor,
        media_id=mid,
        direction=body.direction,
        catalog_facts=catalog,
        uow=uow,
        jellyfin_url=config.jellyfin_url,
    )
    if isinstance(result, SwipeRejected):
        return XSSSafeJSONResponse(content={"error": result.reason}, status_code=404)
    # SwipeAccepted — commit and notify
    await commit_and_wake(uow, code)
    return SwipeResponse(accepted=True)


@rooms_router.get(
    "/matches",
    tags=["Matches"],
    response_model=MatchListResponse,
    responses={
        200: {"description": "Match list returned successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="List matches",
)
async def get_matches(
    request: Request,
    uow: DBUoW,
    view: Optional[Literal["history"]] = None,
    user: AuthUser = Depends(require_auth),
):
    """Return the current room's matches, or the user's full match history.

    Omit ``view`` to get matches for the caller's current active room.
    Pass ``view=history`` to retrieve archived matches across all past rooms.
    """
    code = request.session.get("active_room")
    rows = await room_lifecycle_service.get_matches(code, user.user_id, view, uow)
    return {"matches": rows}


@rooms_router.post(
    "/room/{code}/quit",
    tags=["Rooms"],
    response_model=QuitRoomResponse,
    responses={
        200: {"description": "Room session ended and matches archived"},
    },
    summary="Quit a room",
)
async def quit_room(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Quit a room, archive all active matches, and clean up the session.

    Deletes the room from the active rooms table, archives any outstanding
    matches, clears the caller's session state, and publishes a
    ``session_closed`` event so connected SSE clients can react.
    """
    result = await room_lifecycle_service.quit_room(
        code, request.session, user.user_id, uow
    )
    await commit_and_wake(uow, code)
    return result


@rooms_router.post(
    "/matches/delete",
    tags=["Matches"],
    response_model=DeleteMatchResponse,
    responses={
        200: {"description": "Match deleted successfully"},
        422: {"description": "Validation error — media_id is required"},
    },
    summary="Delete a match",
)
async def delete_match(
    request: Request,
    body: DeleteMatchRequest,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
):
    """Delete a single match from history by media ID.

    Removes the match row from the database. If no matching record is found,
    the operation still returns successfully.
    """
    actor = SessionActor(
        user_id=user.user_id,
        session_id=request.session.get("session_id"),
        active_room=request.session.get("active_room"),
    )
    result = await session_match_mutation.delete_match(
        actor=actor,
        media_id=body.media_id,
        uow=uow,
    )
    if isinstance(result, DeleteChanged):
        await uow.session.commit()
    return {"status": "deleted"}


@rooms_router.post(
    "/room/{code}/undo",
    tags=["Swiping"],
    response_model=UndoResponse,
    responses={
        200: {"description": "Swipe undone"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Undo the last swipe",
)
async def undo_swipe(
    code: str,
    body: UndoRequest,
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
):
    """Undo the last swipe on a media item within a room.

    Rolls back the most recent swipe for ``media_id`` by the calling user.
    Notifies connected SSE clients if the undo changed room state.
    """
    mid = str(body.media_id)
    actor = SessionActor(
        user_id=user.user_id,
        session_id=request.session.get("session_id"),
        active_room=request.session.get("active_room"),
    )
    result = await session_match_mutation.undo_swipe(
        code=code,
        actor=actor,
        media_id=mid,
        uow=uow,
    )
    if isinstance(result, UndoChanged):
        await commit_and_wake(uow, code)
    return UndoResponse(status="undone")


@rooms_router.get(
    "/room/{code}/deck",
    tags=["Swiping"],
    response_model=list,
    responses={
        200: {"description": "Page of cards from the deck"},
        400: {"model": ErrorResponse, "description": "Invalid page parameter"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get a page of cards from the deck",
)
async def get_deck(
    code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)
):
    """Return a paginated page of swipeable cards for the room.

    Pass ``?page=N`` (1-based) to retrieve subsequent pages. Returns 400 if the
    page parameter cannot be parsed as an integer.
    """
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        return XSSSafeJSONResponse(
            content={"error": "Invalid page parameter"}, status_code=400
        )
    return await room_lifecycle_service.get_deck(code, user.user_id, page, uow)


@rooms_router.post(
    "/room/{code}/genre",
    tags=["Swiping"],
    response_model=list,
    responses={
        200: {"description": "Genre updated; new deck returned"},
        400: {
            "model": ErrorResponse,
            "description": "No cards match the selected genre",
        },
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Set the genre filter for the room",
)
async def set_genre(
    code: str,
    body: SetGenreRequest,
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    provider=Depends(get_provider),
):
    """Change the active genre filter and reload the deck.

    Returns the updated list of ``CardItem`` objects for the room. If the chosen
    genre yields an empty deck, returns 400 with a descriptive error.
    """
    try:
        new_list = await room_lifecycle_service.set_genre(
            code, body.genre, provider, uow
        )
        await commit_and_wake(uow, code)
        return new_list
    except EmptyDeckError as e:
        return XSSSafeJSONResponse(content={"error": str(e)}, status_code=400)


@rooms_router.post(
    "/room/{code}/watched-filter",
    tags=["Swiping"],
    response_model=list,
    responses={
        200: {"description": "Watched filter updated; new deck returned"},
        422: {"model": ErrorResponse, "description": "No unwatched items available"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Toggle the watched-items filter for the room",
)
async def set_watched_filter_route(
    code: str,
    body: SetWatchedFilterRequest,
    request: Request,
    uow: DBUoW,
    user: AuthUser = Depends(require_auth),
    provider=Depends(get_provider),
):
    """Enable or disable the hide-watched filter and reload the deck.

    ``hide_watched`` must be a JSON boolean (``true``/``false``). Returns the
    updated list of ``CardItem`` objects. If enabling the filter leaves no
    unwatched items, returns 422.
    """
    try:
        result = await room_lifecycle_service.set_watched_filter(
            code, body.hide_watched, provider, uow
        )
        await commit_and_wake(uow, code)
        return result
    except EmptyDeckError:
        return XSSSafeJSONResponse(
            content={"error": "No unwatched items available"}, status_code=422
        )


@rooms_router.get(
    "/room/{code}/status",
    tags=["Rooms"],
    response_model=RoomStatusResponse,
    response_model_exclude_none=True,
    responses={
        200: {"description": "Current room status snapshot"},
    },
    summary="Get room status",
)
async def room_status(
    code: str, _request: Request, uow: DBUoW, _user: AuthUser = Depends(require_auth)
):
    """Return the current status snapshot for a room.

    If the room does not exist, returns ``{"ready": false}`` with no other
    fields. When ready, the response also includes ``genre``, ``solo``, and
    ``hide_watched`` settings.
    """
    return await room_lifecycle_service.get_status(code, uow)


@rooms_router.get(
    "/room/{code}/stream",
    tags=["Rooms"],
    summary="Subscribe to room events stream",
)
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
    """Server-Sent Events stream for real-time room session updates.

    Opens a persistent SSE connection that delivers events as JSON-encoded data
    frames. The first event on every fresh connection is always `session_bootstrap`,
    which carries a snapshot of current room state and a `replay_boundary` cursor.

    **Event types**: `session_bootstrap`, `session_reset`, `session_ready`,
    `session_closed`, `genre_changed`, `hide_watched_changed`, `match_found`.

    **Reconnection / replay**: pass the last received event id via the
    `Last-Event-ID` header or `after_event_id` query parameter to replay
    missed events. A stale cursor causes the server to emit `session_reset`
    so the client knows to drop local state and reconnect without a cursor.

    See [docs/sse-events.md](docs/sse-events.md) for full payload schemas and
    the complete protocol reference.
    """

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
