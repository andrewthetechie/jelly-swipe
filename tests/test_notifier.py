"""Unit tests for SessionNotifier."""

import asyncio

import pytest

from jellyswipe.notifier import SessionNotifier


@pytest.mark.anyio
async def test_subscribe_and_notify_resolves_future():
    """Test that subscribe + notify: subscriber's Future resolves."""
    notifier = SessionNotifier()
    future = notifier.subscribe("room123")

    assert not future.done()

    notifier.notify("room123")

    assert future.done()
    assert future.result() is None


@pytest.mark.anyio
async def test_multiple_subscribers_same_room_all_resolve():
    """Test multiple subscribers on same room: all Futures resolve on single notify."""
    notifier = SessionNotifier()
    future1 = notifier.subscribe("room123")
    future2 = notifier.subscribe("room123")
    future3 = notifier.subscribe("room123")

    assert not future1.done()
    assert not future2.done()
    assert not future3.done()

    notifier.notify("room123")

    assert future1.done()
    assert future2.done()
    assert future3.done()
    assert future1.result() is None
    assert future2.result() is None
    assert future3.result() is None


@pytest.mark.anyio
async def test_subscribers_different_rooms_isolated():
    """Test subscribers on different rooms: only the target room's Futures resolve."""
    notifier = SessionNotifier()
    future_room1 = notifier.subscribe("room1")
    future_room2 = notifier.subscribe("room2")

    notifier.notify("room1")

    assert future_room1.done()
    assert not future_room2.done()

    notifier.notify("room2")
    assert future_room2.done()


@pytest.mark.anyio
async def test_unsubscribe_removes_future_without_resolving():
    """Test unsubscribe: removed Future does NOT resolve on subsequent notify."""
    notifier = SessionNotifier()
    future = notifier.subscribe("room123")

    assert not future.done()

    notifier.unsubscribe("room123", future)

    assert future.cancelled()

    notifier.notify("room123")
    # Future should still be cancelled (not resolved with a result)
    assert future.cancelled()


@pytest.mark.anyio
async def test_unsubscribe_cleanup_empty_dict_entry():
    """Test unsubscribe cleanup: internal dict entry is cleaned up when last subscriber leaves."""
    notifier = SessionNotifier()
    future = notifier.subscribe("room123")

    assert "room123" in notifier._subscribers

    notifier.unsubscribe("room123", future)

    assert "room123" not in notifier._subscribers


@pytest.mark.anyio
async def test_notify_with_no_subscribers_no_error():
    """Test notify with no subscribers: no error raised."""
    notifier = SessionNotifier()

    # Should not raise
    notifier.notify("nonexistent_room")


@pytest.mark.anyio
async def test_futures_cleared_after_notify():
    """Test subscriber count after notify: Futures are cleared from the set after resolution."""
    notifier = SessionNotifier()
    notifier.subscribe("room123")
    notifier.subscribe("room123")

    assert "room123" in notifier._subscribers
    assert len(notifier._subscribers["room123"]) == 2

    notifier.notify("room123")

    # After notify, the room should be removed from subscribers
    assert "room123" not in notifier._subscribers


@pytest.mark.anyio
async def test_cancelled_future_handling():
    """Test cancelled Future handling: if a Future is already cancelled, notify does not raise."""
    notifier = SessionNotifier()
    future = notifier.subscribe("room123")

    # Cancel the future before notify
    future.cancel()
    assert future.cancelled()

    # Should not raise
    notifier.notify("room123")


@pytest.mark.anyio
async def test_unsubscribe_nonexistent_room_no_error():
    """Test unsubscribe from nonexistent room does not raise."""
    notifier = SessionNotifier()
    future = asyncio.Future()

    # Should not raise
    notifier.unsubscribe("nonexistent_room", future)


@pytest.mark.anyio
async def test_multiple_notify_cycles():
    """Test that subscribers must re-subscribe after each notify."""
    notifier = SessionNotifier()

    # First cycle
    future1 = notifier.subscribe("room123")
    notifier.notify("room123")
    assert future1.done()

    # Second cycle - must subscribe again
    future2 = notifier.subscribe("room123")
    assert not future2.done()

    notifier.notify("room123")
    assert future2.done()


@pytest.mark.anyio
async def test_unsubscribe_one_of_multiple_subscribers():
    """Test unsubscribing one subscriber leaves others intact."""
    notifier = SessionNotifier()
    future1 = notifier.subscribe("room123")
    future2 = notifier.subscribe("room123")
    future3 = notifier.subscribe("room123")

    notifier.unsubscribe("room123", future2)

    assert "room123" in notifier._subscribers
    assert len(notifier._subscribers["room123"]) == 2
    assert future1 in notifier._subscribers["room123"]
    assert future2 not in notifier._subscribers["room123"]
    assert future3 in notifier._subscribers["room123"]

    notifier.notify("room123")

    assert future1.done()
    assert future2.cancelled()  # Was cancelled
    assert future3.done()
