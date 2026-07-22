"""Unit tests for AuthService — testable with mocked UoW and provider."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from jellyswipe.dependencies import AuthUser
from jellyswipe.services.auth import AuthService, LoginResult, MeResult


def _make_mock_provider(
    token: str = "test-token",
    user_id: str = "test-user",
    raise_runtime_error: bool = False,
    server_info: dict | None = None,
) -> MagicMock:
    """Build a mock JellyfinLibraryProvider."""
    provider = MagicMock()
    if raise_runtime_error:
        provider.server_access_token_for_delegate.side_effect = RuntimeError(
            "unavailable"
        )
    else:
        provider.server_access_token_for_delegate.return_value = token
        provider.server_primary_user_id_for_delegate.return_value = user_id
    provider.server_info.return_value = (
        server_info
        if server_info is not None
        else {
            "machineIdentifier": "test-server-id",
            "name": "TestServer",
            "webUrl": "",
        }
    )
    return provider


def _make_mock_uow() -> MagicMock:
    """Build a mock DatabaseUnitOfWork."""
    uow = MagicMock()
    uow.auth_sessions.delete_expired = AsyncMock()
    uow.auth_sessions.insert = AsyncMock()
    uow.auth_sessions.delete_by_session_id = AsyncMock()
    uow.rooms.pairing_code_exists = AsyncMock()
    return uow


# ---------------------------------------------------------------------------
# login_delegate tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_login_delegate_returns_result():
    """login_delegate returns LoginResult with correct fields on success."""
    provider = _make_mock_provider(token="test-token", user_id="test-user")
    uow = _make_mock_uow()

    result = await AuthService.login_delegate(provider, uow)

    assert result is not None
    assert isinstance(result, LoginResult)
    assert len(result.session_id) >= 43  # secrets.token_urlsafe(32) produces 43 chars
    assert result.user_id == "test-user"
    assert result.response_body == {"userId": "test-user"}
    uow.auth_sessions.insert.assert_called_once()


@pytest.mark.anyio
async def test_login_delegate_returns_none_on_runtime_error():
    """login_delegate returns None when provider raises RuntimeError."""
    provider = _make_mock_provider(raise_runtime_error=True)
    uow = _make_mock_uow()

    result = await AuthService.login_delegate(provider, uow)

    assert result is None
    uow.auth_sessions.insert.assert_not_called()


@pytest.mark.anyio
async def test_login_delegate_cleans_expired_sessions():
    """login_delegate calls delete_expired with a 14-day cutoff."""
    provider = _make_mock_provider()
    uow = _make_mock_uow()

    await AuthService.login_delegate(provider, uow)

    cutoff_call = uow.auth_sessions.delete_expired.call_args[0][0]
    expected_cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    # Allow small time drift (within 2 seconds)
    called_dt = datetime.fromisoformat(cutoff_call)
    expected_dt = datetime.fromisoformat(expected_cutoff)
    assert abs((called_dt - expected_dt).total_seconds()) < 2


# ---------------------------------------------------------------------------
# logout tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_logout_deletes_session():
    """logout calls delete_by_session_id when session_id is provided."""
    uow = _make_mock_uow()

    await AuthService.logout("abc", uow)

    uow.auth_sessions.delete_by_session_id.assert_awaited_once_with("abc")


@pytest.mark.anyio
async def test_logout_swallows_exception():
    """logout does not re-raise exceptions from delete_by_session_id."""
    uow = _make_mock_uow()
    uow.auth_sessions.delete_by_session_id.side_effect = Exception("db error")

    # Should not raise
    await AuthService.logout("abc", uow)


@pytest.mark.anyio
async def test_logout_skips_delete_when_no_session():
    """logout does not call delete_by_session_id when session_id is None."""
    uow = _make_mock_uow()

    await AuthService.logout(None, uow)

    uow.auth_sessions.delete_by_session_id.assert_not_called()


# ---------------------------------------------------------------------------
# get_me tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_me_returns_user_info():
    """get_me returns MeResult with correct response_body fields."""
    provider = _make_mock_provider()
    uow = _make_mock_uow()
    user = AuthUser(jf_token="some-token", user_id="test-user")

    result = await AuthService.get_me(user, None, provider, uow)

    assert isinstance(result, MeResult)
    body = result.response_body
    assert body["userId"] == "test-user"
    assert body["displayName"] == "test-user"
    assert body["serverName"] == "TestServer"
    assert body["serverId"] == "test-server-id"
    assert body["activeRoom"] is None


@pytest.mark.anyio
async def test_get_me_clears_invalid_room():
    """get_me returns activeRoom=None when pairing_code_exists returns False."""
    provider = _make_mock_provider()
    uow = _make_mock_uow()
    uow.rooms.pairing_code_exists.return_value = False
    user = AuthUser(jf_token="some-token", user_id="test-user")

    result = await AuthService.get_me(user, "ABCD", provider, uow)

    assert result.response_body["activeRoom"] is None


@pytest.mark.anyio
async def test_get_me_preserves_valid_room():
    """get_me returns activeRoom when pairing_code_exists returns True."""
    provider = _make_mock_provider()
    uow = _make_mock_uow()
    uow.rooms.pairing_code_exists.return_value = True
    user = AuthUser(jf_token="some-token", user_id="test-user")

    result = await AuthService.get_me(user, "ABCD", provider, uow)

    assert result.response_body["activeRoom"] == "ABCD"
