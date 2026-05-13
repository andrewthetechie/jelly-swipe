"""Tests for commit_and_wake helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jellyswipe.routers._helpers import commit_and_wake


@pytest.mark.anyio
async def test_commit_and_wake_commits_then_notifies():
    """commit_and_wake calls uow.session.commit() then notifier.notify(code)."""
    uow = MagicMock()
    uow.session.commit = AsyncMock()

    call_order = []

    async def track_commit():
        call_order.append("commit")

    def track_notify(code):
        call_order.append("notify")

    uow.session.commit.side_effect = track_commit

    with patch("jellyswipe.routers._helpers.notifier") as mock_notifier:
        mock_notifier.notify.side_effect = track_notify
        await commit_and_wake(uow, "ABCD")

    assert call_order == ["commit", "notify"]
    mock_notifier.notify.assert_called_once_with("ABCD")


@pytest.mark.anyio
async def test_commit_and_wake_propagates_commit_error():
    """If commit raises, the error propagates and notifier.notify is NOT called."""
    uow = MagicMock()
    uow.session.commit = AsyncMock(side_effect=RuntimeError("db error"))

    with patch("jellyswipe.routers._helpers.notifier") as mock_notifier:
        with pytest.raises(RuntimeError, match="db error"):
            await commit_and_wake(uow, "WXYZ")

    mock_notifier.notify.assert_not_called()
