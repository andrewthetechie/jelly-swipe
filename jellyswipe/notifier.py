"""Future-based pub/sub for waking SSE subscribers after committed events.

Single-process asyncio only. The event ledger is the source of truth;
this module is a latency optimization.
"""

from __future__ import annotations

import asyncio


class SessionNotifier:
    """Future-based pub/sub for waking SSE subscribers after committed events.

    Single-process asyncio only. The event ledger is the source of truth;
    this module is a latency optimization.
    """

    def __init__(self) -> None:
        """Initialize the notifier with an empty subscriber registry."""
        self._subscribers: dict[str, set[asyncio.Future]] = {}

    def subscribe(self, room_code: str) -> asyncio.Future:
        """Register a subscriber and return a Future that resolves on notify().

        The caller awaits this Future. When notify() fires, the Future
        resolves with None. The caller must then re-subscribe for the
        next event cycle.

        Args:
            room_code: The room code to subscribe to.

        Returns:
            An asyncio.Future that resolves when notify() is called for this room.
        """
        future: asyncio.Future = asyncio.Future()
        if room_code not in self._subscribers:
            self._subscribers[room_code] = set()
        self._subscribers[room_code].add(future)
        return future

    def notify(self, room_code: str) -> None:
        """Resolve all registered Futures for the given room code.

        Called ONLY after the event-append transaction commits successfully.
        Subscribers wake, read new events from the ledger, and re-subscribe.

        Args:
            room_code: The room code to notify.
        """
        if room_code not in self._subscribers:
            return

        futures = self._subscribers.pop(room_code)
        for future in futures:
            if not future.done():
                future.set_result(None)

    def unsubscribe(self, room_code: str, future: asyncio.Future) -> None:
        """Remove a subscriber's Future without resolving it.

        Called on SSE disconnect or stream exit to prevent leaks.

        Args:
            room_code: The room code to unsubscribe from.
            future: The Future to remove.
        """
        if room_code not in self._subscribers:
            return

        self._subscribers[room_code].discard(future)
        if not future.done():
            future.cancel()

        # Clean up empty sets to prevent memory leaks
        if not self._subscribers[room_code]:
            del self._subscribers[room_code]


# Module-level singleton instance
notifier = SessionNotifier()
