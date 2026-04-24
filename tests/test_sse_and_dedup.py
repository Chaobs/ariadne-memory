"""
Unit tests for SSE Broadcaster and Deduplication Cache.

These tests verify the real-time streaming and content-hash deduplication features.
"""

import asyncio
import pytest
import time
from ariadne.session.sse_broadcaster import (
    SSEBroadcaster, SSEEvent, SSEEventType, SSEClient
)
from ariadne.session.deduplication import DeduplicationCache


# ============================================================================
# SSE Client Tests
# ============================================================================

class TestSSEClient:
    """Tests for SSEClient."""

    def test_client_creation(self):
        """Test SSEClient initializes correctly."""
        client = SSEClient(
            client_id="test-client",
            send_fn=lambda x: None,
            session_filter="session-1",
        )
        assert client.client_id == "test-client"
        assert client.session_filter == "session-1"
        assert client.is_connected is True

    def test_client_without_filter(self):
        """Test SSEClient without session filter (global subscription)."""
        client = SSEClient(
            client_id="global-client",
            send_fn=lambda x: None,
        )
        assert client.session_filter is None


# ============================================================================
# SSE Event Tests
# ============================================================================

class TestSSEEvent:
    """Tests for SSEEvent."""

    def test_event_creation(self):
        """Test SSEEvent creation with default timestamp."""
        event = SSEEvent(
            type=SSEEventType.NEW_OBSERVATION,
            session_id="session-1",
            data={"id": "obs1"},
        )
        assert event.type == SSEEventType.NEW_OBSERVATION
        assert event.session_id == "session-1"
        assert event.data["id"] == "obs1"
        assert event.timestamp is not None

    def test_to_sse_line(self):
        """Test SSE line formatting."""
        event = SSEEvent(
            type=SSEEventType.HEARTBEAT,
            session_id=None,
            data={},
        )
        line = event.to_sse_line()
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        assert "heartbeat" in line


# ============================================================================
# SSE Broadcaster Tests (Sync wrapper for async code)
# ============================================================================

class TestSSEBroadcaster:
    """Tests for SSEBroadcaster."""

    @pytest.fixture
    def broadcaster(self):
        """Create a fresh broadcaster for each test."""
        return SSEBroadcaster()

    def test_connect_disconnect(self, broadcaster):
        """Test client connect and disconnect."""
        async def _test():
            await broadcaster.connect("client1", lambda msg: None)
            assert len(broadcaster._clients) == 1
            assert "client1" in broadcaster._clients
            await broadcaster.disconnect("client1")
            assert len(broadcaster._clients) == 0

        asyncio.get_event_loop().run_until_complete(_test())

    def test_connect_with_session_filter(self, broadcaster):
        """Test client connects with session filter."""
        async def _test():
            await broadcaster.connect("client1", lambda msg: None, session_filter="session-1")
            assert "session-1" in broadcaster._session_subscribers
            assert "client1" in broadcaster._session_subscribers["session-1"]

        asyncio.get_event_loop().run_until_complete(_test())

    def test_connect_global_subscription(self, broadcaster):
        """Test global subscription (no filter)."""
        async def _test():
            await broadcaster.connect("global-client", lambda msg: None)
            assert "global-client" in broadcaster._global_clients

        asyncio.get_event_loop().run_until_complete(_test())

    def test_broadcast_to_session(self, broadcaster):
        """Test broadcasting to session-filtered clients."""
        async def _test():
            messages = []
            await broadcaster.connect("client1", lambda msg: messages.append(msg), session_filter="session-1")
            await broadcaster.broadcast_observation(
                observation={"id": "obs1", "summary": "Test"},
                session_id="session-1",
            )
            assert len(messages) == 1
            assert "new_observation" in messages[0]
            assert "obs1" in messages[0]

        asyncio.get_event_loop().run_until_complete(_test())

    def test_broadcast_to_global(self, broadcaster):
        """Test broadcasting to global subscribers."""
        async def _test():
            messages = []
            await broadcaster.connect("global-client", lambda msg: messages.append(msg))
            await broadcaster.broadcast_summary(
                summary={"narrative": "Test summary"},
                session_id="any-session",
            )
            assert len(messages) == 1
            assert "new_summary" in messages[0]

        asyncio.get_event_loop().run_until_complete(_test())

    def test_broadcast_session_end(self, broadcaster):
        """Test session end notification."""
        async def _test():
            messages = []
            await broadcaster.connect("client1", lambda msg: messages.append(msg), session_filter="session-1")
            await broadcaster.broadcast_session_end("session-1")
            assert len(messages) == 1
            assert "session_ended" in messages[0]

        asyncio.get_event_loop().run_until_complete(_test())

    def test_session_filter_not_receive_other(self, broadcaster):
        """Test that session-filtered client doesn't receive other session events."""
        async def _test():
            messages = []
            await broadcaster.connect("client1", lambda msg: messages.append(msg), session_filter="session-1")
            await broadcaster.broadcast_observation(
                observation={"id": "obs1"},
                session_id="session-2",  # Different session
            )
            assert len(messages) == 0  # Should not receive

        asyncio.get_event_loop().run_until_complete(_test())

    def test_stats(self, broadcaster):
        """Test broadcaster statistics."""
        async def _test():
            await broadcaster.connect("client1", lambda msg: None, session_filter="session-1")
            await broadcaster.connect("global-client", lambda msg: None)
            stats = broadcaster.get_stats()
            assert stats["total_clients"] == 2
            assert stats["global_subscribers"] == 1
            assert stats["session_subscriptions"] == 1

        asyncio.get_event_loop().run_until_complete(_test())

    def test_disconnect_nonexistent(self, broadcaster):
        """Test disconnecting non-existent client doesn't crash."""
        async def _test():
            await broadcaster.disconnect("nonexistent-client")  # Should not raise

        asyncio.get_event_loop().run_until_complete(_test())


# ============================================================================
# Deduplication Cache Tests
# ============================================================================

class TestDeduplicationCache:
    """Tests for DeduplicationCache."""

    def test_creation(self):
        """Test DeduplicationCache initialization."""
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache._window == 30.0
        assert len(cache._cache) == 0

    def test_invalid_window(self):
        """Test that invalid window raises ValueError."""
        with pytest.raises(ValueError):
            DeduplicationCache(window_seconds=0)
        with pytest.raises(ValueError):
            DeduplicationCache(window_seconds=-1)

    def test_is_duplicate_same_content(self):
        """Test same content within window is duplicate after mark_seen."""
        cache = DeduplicationCache(window_seconds=30.0)

        # First call - not duplicate
        assert cache.is_duplicate("s1", "title", "narrative") is False
        # Mark as seen
        cache.mark_seen("s1", "title", "narrative")

        # Second call - is duplicate
        assert cache.is_duplicate("s1", "title", "narrative") is True

    def test_is_duplicate_different_content(self):
        """Test different content is not duplicate."""
        cache = DeduplicationCache(window_seconds=30.0)

        cache.is_duplicate("s1", "title1", "narrative")
        assert cache.is_duplicate("s1", "title2", "narrative") is False
        assert cache.is_duplicate("s1", "title", "different narrative") is False

    def test_is_duplicate_different_session(self):
        """Test same content in different session is not duplicate."""
        cache = DeduplicationCache(window_seconds=30.0)

        cache.is_duplicate("s1", "title", "narrative")
        assert cache.is_duplicate("s2", "title", "narrative") is False

    def test_check_and_mark(self):
        """Test atomic check-and-mark operation."""
        cache = DeduplicationCache(window_seconds=30.0)

        # First call - not duplicate, marks as seen
        assert cache.check_and_mark("s1", "title", "narrative") is False

        # Second call - is duplicate
        assert cache.check_and_mark("s1", "title", "narrative") is True

    def test_mark_seen(self):
        """Test mark_seen manually."""
        cache = DeduplicationCache(window_seconds=30.0)

        # Without mark_seen - not duplicate
        assert cache.is_duplicate("s1", "title", "narrative") is False

        # After mark_seen - duplicate
        cache.mark_seen("s1", "title", "narrative")
        assert cache.is_duplicate("s1", "title", "narrative") is True

    def test_window_expiry(self):
        """Test that entries expire after window."""
        cache = DeduplicationCache(window_seconds=0.1)  # 100ms

        # First call - not duplicate
        assert cache.is_duplicate("s1", "title", "narrative") is False
        cache.mark_seen("s1", "title", "narrative")

        # Wait for expiry
        time.sleep(0.2)

        # Should not be duplicate (expired)
        assert cache.is_duplicate("s1", "title", "narrative") is False

    def test_clear(self):
        """Test cache clear."""
        cache = DeduplicationCache(window_seconds=30.0)

        cache.mark_seen("s1", "title", "narrative")
        assert len(cache._cache) == 1
        assert cache._misses == 1  # mark_seen increments misses

        stats_before_clear = cache.get_stats()
        assert stats_before_clear["misses"] == 1

        cache.clear()
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0  # clear() resets counters

    def test_stats(self):
        """Test statistics tracking."""
        cache = DeduplicationCache(window_seconds=30.0)

        cache.check_and_mark("s1", "title1", "narrative")  # miss
        cache.check_and_mark("s1", "title1", "narrative")  # hit
        cache.check_and_mark("s1", "title2", "narrative")  # miss

        stats = cache.get_stats()
        assert stats["window_seconds"] == 30.0
        assert stats["cached_entries"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert abs(stats["hit_rate"] - 1/3) < 0.01

    def test_hash_consistency(self):
        """Test hash is consistent for same input."""
        cache = DeduplicationCache(window_seconds=30.0)

        hash1 = cache._compute_hash("s1", "title", "narrative")
        hash2 = cache._compute_hash("s1", "title", "narrative")

        assert hash1 == hash2

    def test_hash_different_for_different_input(self):
        """Test hash is different for different inputs."""
        cache = DeduplicationCache(window_seconds=30.0)

        hash1 = cache._compute_hash("s1", "title1", "narrative")
        hash2 = cache._compute_hash("s1", "title2", "narrative")

        assert hash1 != hash2

    def test_cleanup_expired(self):
        """Test expired entries are cleaned up."""
        cache = DeduplicationCache(window_seconds=0.1)

        cache.mark_seen("s1", "title1", "narrative")
        cache.mark_seen("s1", "title2", "narrative")

        assert len(cache._cache) == 2

        time.sleep(0.2)
        cache._cleanup_expired(time.time())

        assert len(cache._cache) == 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestSSEAndDedupIntegration:
    """Integration tests for SSE + Deduplication together."""

    def test_dedup_prevents_sse_broadcast(self):
        """Test that deduplication prevents duplicate SSE broadcasts."""
        async def _test():
            broadcaster = SSEBroadcaster()
            dedup = DeduplicationCache(window_seconds=30.0)

            messages = []
            await broadcaster.connect("client1", lambda msg: messages.append(msg), session_filter="session-1")

            # First observation - should broadcast
            is_dup = dedup.check_and_mark("session-1", "Fixed bug", "Description")
            if not is_dup:
                await broadcaster.broadcast_observation(
                    observation={"id": "obs1", "summary": "Fixed bug"},
                    session_id="session-1",
                )

            assert len(messages) == 1

            # Second observation (duplicate) - should not broadcast
            is_dup = dedup.check_and_mark("session-1", "Fixed bug", "Description")
            if not is_dup:
                await broadcaster.broadcast_observation(
                    observation={"id": "obs2", "summary": "Fixed bug"},
                    session_id="session-1",
                )

            # Still only 1 message (no duplicate broadcast)
            assert len(messages) == 1

        asyncio.get_event_loop().run_until_complete(_test())
