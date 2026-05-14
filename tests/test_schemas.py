"""Tests for jellyswipe.schemas models."""

import pytest
from jellyswipe.schemas import ErrorResponse, CardItem, MatchItem


class TestErrorResponse:
    def test_error_response_with_required_fields(self):
        """ErrorResponse can be created with error string and optional request_id."""
        resp = ErrorResponse(error="Something went wrong")
        assert resp.error == "Something went wrong"
        assert resp.request_id is None

    def test_error_response_with_request_id(self):
        """ErrorResponse can include a request_id."""
        resp = ErrorResponse(error="Not found", request_id="req-123")
        assert resp.error == "Not found"
        assert resp.request_id == "req-123"

    def test_error_response_json_serialization(self):
        """ErrorResponse serializes to JSON with both fields."""
        resp = ErrorResponse(error="Forbidden", request_id="req-456")
        data = resp.model_dump(exclude_none=False)
        assert data["error"] == "Forbidden"
        assert data["request_id"] == "req-456"


class TestCardItem:
    def test_card_item_required_fields(self):
        """CardItem can be created with required fields."""
        card = CardItem(
            media_id="movie-123",
            title="Inception",
            summary="A thief steals corporate secrets",
            thumb="http://example.com/thumb.jpg",
            year=2010,
            media_type="movie",
            rating="8.8",
        )
        assert card.media_id == "movie-123"
        assert card.title == "Inception"
        assert card.year == 2010
        assert card.duration is None
        assert card.season_count is None

    def test_card_item_with_optional_fields(self):
        """CardItem can include optional fields."""
        card = CardItem(
            media_id="show-456",
            title="Breaking Bad",
            summary="A teacher turns to crime",
            thumb="http://example.com/thumb.jpg",
            year=2008,
            media_type="series",
            rating="9.5",
            duration="47 min",
            season_count=5,
        )
        assert card.duration == "47 min"
        assert card.season_count == 5

    def test_card_item_json_serialization(self):
        """CardItem serializes to JSON."""
        card = CardItem(
            media_id="movie-789",
            title="The Matrix",
            summary="A hacker discovers reality is a simulation",
            thumb="http://example.com/thumb.jpg",
            year=1999,
            media_type="movie",
            rating="8.7",
        )
        data = card.model_dump(exclude_none=True)
        assert data["media_id"] == "movie-789"
        assert data["year"] == 1999
        assert "duration" not in data
        assert "season_count" not in data


class TestMatchItem:
    def test_match_item_all_optional(self):
        """MatchItem can be created with minimal fields."""
        match = MatchItem()
        assert match.title is None
        assert match.thumb is None
        assert match.media_id is None

    def test_match_item_with_fields(self):
        """MatchItem can include all fields."""
        match = MatchItem(
            title="Oppenheimer",
            thumb="http://example.com/thumb.jpg",
            media_id="movie-999",
            media_type="movie",
            deep_link="jellyfin://play/movie-999",
            rating="8.0",
            duration="180 min",
            year=2023,
        )
        assert match.title == "Oppenheimer"
        assert match.media_id == "movie-999"
        assert match.year == 2023

    def test_match_item_json_serialization(self):
        """MatchItem serializes to JSON with exclude_none."""
        match = MatchItem(
            title="Dune", thumb="http://example.com/thumb.jpg", media_id="movie-555"
        )
        data = match.model_dump(exclude_none=True)
        assert data["title"] == "Dune"
        assert "media_type" not in data
        assert "rating" not in data


class TestAuthResponse:
    def test_login_response_validates_user_id(self):
        """LoginResponse accepts userId string."""
        from jellyswipe.schemas.auth import LoginResponse

        resp = LoginResponse(userId="user123")
        assert resp.userId == "user123"

    def test_logout_response_validates_status(self):
        """LogoutResponse accepts status string."""
        from jellyswipe.schemas.auth import LogoutResponse

        resp = LogoutResponse(status="logged_out")
        assert resp.status == "logged_out"

    def test_me_response_validates_all_fields(self):
        """MeResponse accepts all user fields."""
        from jellyswipe.schemas.auth import MeResponse

        resp = MeResponse(
            userId="user456",
            displayName="alice",
            serverName="My Jellyfin",
            serverId="server-789",
            activeRoom=None,
        )
        assert resp.userId == "user456"
        assert resp.displayName == "alice"
        assert resp.serverName == "My Jellyfin"
        assert resp.serverId == "server-789"
        assert resp.activeRoom is None

    def test_me_response_with_active_room(self):
        """MeResponse can include an active room."""
        from jellyswipe.schemas.auth import MeResponse

        resp = MeResponse(
            userId="user789",
            displayName="bob",
            serverName="Jellyfin",
            serverId="server-123",
            activeRoom="room-abc",
        )
        assert resp.activeRoom == "room-abc"

    def test_server_info_response_validates_urls(self):
        """ServerInfoResponse accepts base and web URLs."""
        from jellyswipe.schemas.auth import ServerInfoResponse

        resp = ServerInfoResponse(
            baseUrl="server-id-123", webUrl="https://jellyfin.example.com"
        )
        assert resp.baseUrl == "server-id-123"
        assert resp.webUrl == "https://jellyfin.example.com"

    def test_auth_responses_json_serialization(self):
        """Auth responses serialize to JSON."""
        from jellyswipe.schemas.auth import (
            LoginResponse,
            LogoutResponse,
            MeResponse,
            ServerInfoResponse,
        )

        login = LoginResponse(userId="user-123")
        assert login.model_dump() == {"userId": "user-123"}

        logout = LogoutResponse(status="logged_out")
        assert logout.model_dump() == {"status": "logged_out"}

        me = MeResponse(
            userId="user-456",
            displayName="charlie",
            serverName="Server",
            serverId="id-456",
            activeRoom=None,
        )
        data = me.model_dump(exclude_none=True)
        assert data["userId"] == "user-456"
        assert "activeRoom" not in data

        info = ServerInfoResponse(baseUrl="id", webUrl="http://url")
        assert info.model_dump() == {"baseUrl": "id", "webUrl": "http://url"}


class TestSchemaExports:
    def test_schemas_are_exported_from_init(self):
        """All models are exported from jellyswipe.schemas."""
        from jellyswipe import schemas

        assert hasattr(schemas, "ErrorResponse")
        assert hasattr(schemas, "CardItem")
        assert hasattr(schemas, "MatchItem")
        assert hasattr(schemas, "LoginResponse")
        assert hasattr(schemas, "LogoutResponse")
        assert hasattr(schemas, "MeResponse")
        assert hasattr(schemas, "ServerInfoResponse")


class TestRoomSchemas:
    def test_create_room_request_defaults(self):
        """CreateRoomRequest defaults to movies=True, tv_shows=False, solo=False."""
        from jellyswipe.schemas.rooms import CreateRoomRequest

        req = CreateRoomRequest()
        assert req.movies is True
        assert req.tv_shows is False
        assert req.solo is False

    def test_create_room_request_explicit_values(self):
        """CreateRoomRequest accepts all boolean field combinations."""
        from jellyswipe.schemas.rooms import CreateRoomRequest

        req = CreateRoomRequest(movies=False, tv_shows=True, solo=True)
        assert req.movies is False
        assert req.tv_shows is True
        assert req.solo is True

    def test_create_room_request_rejects_strings(self):
        """CreateRoomRequest raises ValidationError when boolean fields receive strings."""
        import pytest
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import CreateRoomRequest

        with pytest.raises(ValidationError):
            CreateRoomRequest(movies="true", tv_shows=False, solo=False)

    def test_create_room_request_both_false_raises(self):
        """CreateRoomRequest raises ValidationError when both movies and tv_shows are False."""
        import pytest
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import CreateRoomRequest

        with pytest.raises(ValidationError, match="movies or tv_shows"):
            CreateRoomRequest(movies=False, tv_shows=False)

    def test_create_room_response_fields(self):
        """CreateRoomResponse holds pairing_code and instance_id."""
        from jellyswipe.schemas.rooms import CreateRoomResponse

        resp = CreateRoomResponse(pairing_code="1234", instance_id="abc123")
        assert resp.pairing_code == "1234"
        assert resp.instance_id == "abc123"

    def test_join_room_response_fields(self):
        """JoinRoomResponse holds status string."""
        from jellyswipe.schemas.rooms import JoinRoomResponse

        resp = JoinRoomResponse(status="success")
        assert resp.status == "success"

    def test_room_status_response_ready_only(self):
        """RoomStatusResponse works with only ready field."""
        from jellyswipe.schemas.rooms import RoomStatusResponse

        resp = RoomStatusResponse(ready=False)
        assert resp.ready is False
        assert resp.genre is None
        assert resp.solo is None
        assert resp.hide_watched is None

    def test_room_status_response_full(self):
        """RoomStatusResponse works with all fields."""
        from jellyswipe.schemas.rooms import RoomStatusResponse

        resp = RoomStatusResponse(
            ready=True, genre="Action", solo=False, hide_watched=True
        )
        assert resp.ready is True
        assert resp.genre == "Action"
        assert resp.solo is False
        assert resp.hide_watched is True

    def test_quit_room_response_fields(self):
        """QuitRoomResponse holds status string."""
        from jellyswipe.schemas.rooms import QuitRoomResponse

        resp = QuitRoomResponse(status="session_ended")
        assert resp.status == "session_ended"

    def test_room_schemas_exported_from_init(self):
        """Room schemas are exported from jellyswipe.schemas."""
        from jellyswipe import schemas

        assert hasattr(schemas, "CreateRoomRequest")
        assert hasattr(schemas, "CreateRoomResponse")
        assert hasattr(schemas, "JoinRoomResponse")
        assert hasattr(schemas, "RoomStatusResponse")
        assert hasattr(schemas, "QuitRoomResponse")


class TestSwipingSchemas:
    def test_swipe_request_requires_media_id(self):
        """SwipeRequest requires media_id field."""
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import SwipeRequest

        with pytest.raises(ValidationError):
            SwipeRequest()

    def test_swipe_request_accepts_media_id(self):
        """SwipeRequest accepts media_id and optional direction."""
        from jellyswipe.schemas.rooms import SwipeRequest

        req = SwipeRequest(media_id="movie-123")
        assert req.media_id == "movie-123"
        assert req.direction is None

    def test_swipe_request_accepts_direction(self):
        """SwipeRequest accepts direction alongside media_id."""
        from jellyswipe.schemas.rooms import SwipeRequest

        req = SwipeRequest(media_id="movie-123", direction="right")
        assert req.direction == "right"

    def test_swipe_response_accepted_field(self):
        """SwipeResponse holds accepted boolean."""
        from jellyswipe.schemas.rooms import SwipeResponse

        resp = SwipeResponse(accepted=True)
        assert resp.accepted is True

    def test_undo_request_requires_media_id(self):
        """UndoRequest requires media_id field."""
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import UndoRequest

        with pytest.raises(ValidationError):
            UndoRequest()

    def test_undo_request_accepts_media_id(self):
        """UndoRequest accepts media_id."""
        from jellyswipe.schemas.rooms import UndoRequest

        req = UndoRequest(media_id="movie-456")
        assert req.media_id == "movie-456"

    def test_undo_response_status_field(self):
        """UndoResponse holds status string."""
        from jellyswipe.schemas.rooms import UndoResponse

        resp = UndoResponse(status="undone")
        assert resp.status == "undone"

    def test_set_genre_request_requires_genre(self):
        """SetGenreRequest requires genre field."""
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import SetGenreRequest

        with pytest.raises(ValidationError):
            SetGenreRequest()

    def test_set_genre_request_accepts_genre(self):
        """SetGenreRequest accepts genre string."""
        from jellyswipe.schemas.rooms import SetGenreRequest

        req = SetGenreRequest(genre="Action")
        assert req.genre == "Action"

    def test_set_watched_filter_request_requires_hide_watched(self):
        """SetWatchedFilterRequest requires hide_watched field."""
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import SetWatchedFilterRequest

        with pytest.raises(ValidationError):
            SetWatchedFilterRequest()

    def test_set_watched_filter_request_accepts_bool(self):
        """SetWatchedFilterRequest accepts boolean hide_watched."""
        from jellyswipe.schemas.rooms import SetWatchedFilterRequest

        req = SetWatchedFilterRequest(hide_watched=True)
        assert req.hide_watched is True

    def test_set_watched_filter_request_rejects_string(self):
        """SetWatchedFilterRequest rejects string for hide_watched (StrictBool)."""
        from pydantic import ValidationError
        from jellyswipe.schemas.rooms import SetWatchedFilterRequest

        with pytest.raises(ValidationError):
            SetWatchedFilterRequest(hide_watched="true")

    def test_swiping_schemas_exported_from_init(self):
        """Swiping schemas are exported from jellyswipe.schemas."""
        from jellyswipe import schemas

        assert hasattr(schemas, "SwipeRequest")
        assert hasattr(schemas, "SwipeResponse")
        assert hasattr(schemas, "UndoRequest")
        assert hasattr(schemas, "UndoResponse")
        assert hasattr(schemas, "SetGenreRequest")
        assert hasattr(schemas, "SetWatchedFilterRequest")


class TestMediaSchemas:
    def test_trailer_response_fields(self):
        """TrailerResponse holds youtube_key string."""
        from jellyswipe.schemas.media import TrailerResponse

        resp = TrailerResponse(youtube_key="abc123")
        assert resp.youtube_key == "abc123"

    def test_trailer_response_requires_youtube_key(self):
        """TrailerResponse raises ValidationError when youtube_key is missing."""
        from pydantic import ValidationError
        from jellyswipe.schemas.media import TrailerResponse

        with pytest.raises(ValidationError):
            TrailerResponse()

    def test_cast_member_fields(self):
        """CastMember holds name, character, and optional profile_path."""
        from jellyswipe.schemas.media import CastMember

        member = CastMember(
            name="Actor", character="Role", profile_path="http://img/1.jpg"
        )
        assert member.name == "Actor"
        assert member.character == "Role"
        assert member.profile_path == "http://img/1.jpg"

    def test_cast_member_profile_path_optional(self):
        """CastMember accepts null profile_path."""
        from jellyswipe.schemas.media import CastMember

        member = CastMember(name="Actor", character="Role", profile_path=None)
        assert member.profile_path is None

    def test_cast_response_composes_cast_members(self):
        """CastResponse wraps a list of CastMember objects."""
        from jellyswipe.schemas.media import CastMember, CastResponse

        member = CastMember(name="Actor", character="Role", profile_path=None)
        resp = CastResponse(cast=[member])
        assert len(resp.cast) == 1
        assert resp.cast[0].name == "Actor"

    def test_cast_response_accepts_empty_cast(self):
        """CastResponse accepts an empty cast list."""
        from jellyswipe.schemas.media import CastResponse

        resp = CastResponse(cast=[])
        assert resp.cast == []

    def test_watchlist_add_request_requires_media_id(self):
        """WatchlistAddRequest raises ValidationError when media_id is missing."""
        from pydantic import ValidationError
        from jellyswipe.schemas.media import WatchlistAddRequest

        with pytest.raises(ValidationError):
            WatchlistAddRequest()

    def test_watchlist_add_request_accepts_media_id(self):
        """WatchlistAddRequest accepts media_id string."""
        from jellyswipe.schemas.media import WatchlistAddRequest

        req = WatchlistAddRequest(media_id="movie-123")
        assert req.media_id == "movie-123"

    def test_genre_list_response_is_list_of_strings(self):
        """GenreListResponse wraps a JSON array of genre strings."""
        from jellyswipe.schemas.media import GenreListResponse

        resp = GenreListResponse(["Action", "Comedy", "Drama"])
        assert list(resp.root) == ["Action", "Comedy", "Drama"]

    def test_media_schemas_exported_from_init(self):
        """All media models are exported from jellyswipe.schemas."""
        from jellyswipe import schemas

        assert hasattr(schemas, "TrailerResponse")
        assert hasattr(schemas, "CastMember")
        assert hasattr(schemas, "CastResponse")
        assert hasattr(schemas, "WatchlistAddRequest")
        assert hasattr(schemas, "GenreListResponse")
