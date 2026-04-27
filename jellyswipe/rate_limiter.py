"""
In-memory token-bucket rate limiter with zero external dependencies.

Provides TokenBucket and RateLimiter classes for per-(endpoint, IP) rate
limiting. Buckets start full, refill continuously, and are lazily evicted
when stale or when the max bucket cap is reached.

Thread-safe via threading.Lock (gevent-aware via monkey-patching).

Requirements: RL-01
"""

import logging
import threading
import time
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket that allows bursts up to capacity, then refuses until refilled.

    Args:
        capacity: Maximum tokens (burst size). Bucket starts full.
        refill_rate: Tokens added per second (continuous refill).
    """

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)  # D-03: start full
        self.last_refill = time.monotonic()
        self.last_access = self.last_refill

    def consume(self) -> bool:
        """Attempt to consume one token. Returns True if allowed, False if exhausted."""
        now = time.monotonic()
        self.last_access = now

        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after(self) -> float:
        """Return seconds until next token is available. 0.0 if tokens available."""
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate


class RateLimiter:
    """Manages independent token buckets keyed by (endpoint, ip).

    Args:
        max_buckets: Maximum number of buckets before oldest-accessed are evicted.
        stale_seconds: Seconds of inactivity before a bucket is considered stale.
    """

    def __init__(self, max_buckets: int = 10000, stale_seconds: float = 300.0):
        self._buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self._lock = threading.Lock()
        self.max_buckets = max_buckets
        self.stale_seconds = stale_seconds

    def check(
        self,
        endpoint: str,
        ip: str,
        limit: int,
        per_minutes: int = 1,
    ) -> Tuple[bool, float]:
        """Check rate limit for (endpoint, ip) pair.

        Args:
            endpoint: Flask endpoint name (e.g., 'proxy', 'get_trailer').
            ip: Client IP address from request.remote_addr.
            limit: Maximum requests allowed per per_minutes window.
            per_minutes: Time window in minutes (default 1).

        Returns:
            Tuple of (allowed: bool, retry_after: float).
        """
        with self._lock:
            self._evict_stale()

            key = (endpoint, ip)
            if key not in self._buckets:
                refill_rate = limit / (per_minutes * 60)  # D-02
                self._buckets[key] = TokenBucket(capacity=limit, refill_rate=refill_rate)

                # Enforce max bucket cap after adding new bucket
                if len(self._buckets) > self.max_buckets:
                    self._evict_oldest()

            bucket = self._buckets[key]
            allowed = bucket.consume()

            if allowed:
                return (True, 0.0)
            else:
                return (False, bucket.retry_after())

    def reset(self):
        """Clear all buckets. Useful for test isolation."""
        with self._lock:
            self._buckets.clear()

    def _evict_stale(self):
        """Remove buckets not accessed in stale_seconds. Called under lock."""
        now = time.monotonic()
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_access > self.stale_seconds
        ]
        for key in stale_keys:
            del self._buckets[key]

    def _evict_oldest(self):
        """Evict oldest-accessed buckets until under max_buckets cap. Called under lock."""
        while len(self._buckets) > self.max_buckets:
            # Find the bucket with the oldest last_access
            oldest_key = min(self._buckets, key=lambda k: self._buckets[k].last_access)
            del self._buckets[oldest_key]


# Module-level singleton — Flask routes import this.
rate_limiter = RateLimiter()
