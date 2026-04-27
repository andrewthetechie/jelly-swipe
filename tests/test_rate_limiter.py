"""
Token bucket rate limiter unit tests.

Tests verify:
- TokenBucket: burst capacity, refill over time, retry_after calculation
- RateLimiter: per-(endpoint, IP) isolation, stale eviction, max bucket cap
- Thread safety under concurrent access

Requirements: RL-01
"""

import time
import threading
from unittest.mock import patch

import pytest


class TestTokenBucket:
    """Unit tests for TokenBucket class."""

    def test_new_bucket_starts_full(self):
        """Test 1: New bucket starts full at capacity — first N consume() calls return True."""
        from jellyswipe.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, refill_rate=0.5)
        results = [bucket.consume() for _ in range(5)]
        assert all(results), "First 5 consume() calls should all return True"

    def test_consume_returns_false_after_capacity_exhausted(self):
        """Test 2: consume() returns False after capacity exhausted."""
        from jellyswipe.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=3, refill_rate=0.5)
        # Exhaust capacity
        for _ in range(3):
            bucket.consume()
        # Next call should fail
        assert bucket.consume() is False, "consume() should return False after capacity exhausted"

    def test_refill_allows_consume_after_wait(self):
        """Test 3: After waiting sufficient time for refill, consume() returns True again."""
        from jellyswipe.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=2, refill_rate=100.0)  # Very fast refill
        # Exhaust
        bucket.consume()
        bucket.consume()
        assert bucket.consume() is False
        # Wait a tiny bit for refill
        time.sleep(0.05)
        assert bucket.consume() is True, "After refill, consume() should return True"

    def test_retry_after_zero_when_tokens_available(self):
        """Test 4: retry_after() returns ~0 when tokens available, positive float when exhausted."""
        from jellyswipe.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        # Tokens available
        assert bucket.retry_after() == 0.0, "retry_after should be 0 when tokens available"
        # Exhaust tokens
        for _ in range(5):
            bucket.consume()
        retry = bucket.retry_after()
        assert retry > 0.0, f"retry_after should be positive when exhausted, got {retry}"

    def test_refill_rate_calculation(self):
        """Test 5: Refill rate = capacity/60 tokens per second."""
        from jellyswipe.rate_limiter import TokenBucket
        # capacity=10 → refill_rate should be 10/60 ≈ 0.1667 tokens/sec
        bucket = TokenBucket(capacity=10, refill_rate=10 / 60)
        assert abs(bucket.refill_rate - 0.1667) < 0.01, \
            f"Expected refill_rate ~0.1667, got {bucket.refill_rate}"

    def test_rate_limiter_creates_independent_buckets_per_endpoint_ip(self):
        """Test 6: RateLimiter.check() creates independent buckets per (endpoint, ip) pair."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter()
        # Create bucket for (endpoint_a, ip_a)
        allowed1, _ = rl.check(endpoint="endpoint_a", ip="1.1.1.1", limit=2)
        assert allowed1
        # Different (endpoint, ip) should get its own bucket
        allowed2, _ = rl.check(endpoint="endpoint_b", ip="2.2.2.2", limit=2)
        assert allowed2

    def test_endpoint_isolation(self):
        """Test 7: Hitting limit on endpoint A does NOT affect endpoint B for same IP."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter()
        ip = "1.2.3.4"
        # Exhaust endpoint A
        for _ in range(3):
            rl.check(endpoint="ep_a", ip=ip, limit=3)
        allowed_a, _ = rl.check(endpoint="ep_a", ip=ip, limit=3)
        assert not allowed_a, "Endpoint A should be exhausted"
        # Endpoint B should still be fine
        allowed_b, _ = rl.check(endpoint="ep_b", ip=ip, limit=3)
        assert allowed_b, "Endpoint B should NOT be affected by endpoint A limit"

    def test_ip_isolation(self):
        """Test 8: Hitting limit on IP A does NOT affect IP B for same endpoint."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter()
        endpoint = "test_ep"
        # Exhaust IP A
        for _ in range(3):
            rl.check(endpoint=endpoint, ip="1.1.1.1", limit=3)
        allowed_a, _ = rl.check(endpoint=endpoint, ip="1.1.1.1", limit=3)
        assert not allowed_a, "IP A should be exhausted"
        # IP B should still be fine
        allowed_b, _ = rl.check(endpoint=endpoint, ip="2.2.2.2", limit=3)
        assert allowed_b, "IP B should NOT be affected by IP A limit"

    def test_stale_bucket_eviction(self):
        """Test 9: Stale buckets (last access >300 seconds ago) are evicted on next check."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter(stale_seconds=1.0)
        # Create a bucket
        rl.check(endpoint="stale_ep", ip="1.1.1.1", limit=5)
        assert len(rl._buckets) == 1
        # Wait for it to become stale
        time.sleep(1.5)
        # A new check to a DIFFERENT key should trigger eviction of the stale one
        rl.check(endpoint="other_ep", ip="2.2.2.2", limit=5)
        assert ("stale_ep", "1.1.1.1") not in rl._buckets, "Stale bucket should be evicted"

    def test_max_bucket_cap_eviction(self):
        """Test 10: When bucket count exceeds max_buckets, oldest-accessed buckets are evicted."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter(max_buckets=5, stale_seconds=9999)
        # Create 5 buckets
        for i in range(5):
            rl.check(endpoint=f"ep_{i}", ip="1.1.1.1", limit=10)
        assert len(rl._buckets) == 5
        # Create 1 more — should trigger eviction of oldest
        rl.check(endpoint="ep_overflow", ip="1.1.1.1", limit=10)
        assert len(rl._buckets) <= 5, f"Should not exceed max_buckets, got {len(rl._buckets)}"
        # The first bucket (ep_0) should be evicted as it was oldest-accessed
        assert ("ep_0", "1.1.1.1") not in rl._buckets, "Oldest bucket should be evicted"
        # The new one should exist
        assert ("ep_overflow", "1.1.1.1") in rl._buckets, "New bucket should exist"

    def test_thread_safety(self):
        """Test 11: Concurrent check() calls don't corrupt state."""
        from jellyswipe.rate_limiter import RateLimiter
        rl = RateLimiter()
        errors = []

        def worker(thread_id):
            try:
                for _ in range(50):
                    rl.check(endpoint="shared_ep", ip=f"ip_{thread_id}", limit=100)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # Each thread had its own IP bucket, so we should have 10 buckets
        assert len(rl._buckets) == 10, f"Expected 10 buckets, got {len(rl._buckets)}"
