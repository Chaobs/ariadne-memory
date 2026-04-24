"""
Content-hash deduplication for observation deduplication.

Mirrors Claude-Mem's SHA256 content hash with 30-second window.
Prevents duplicate observations when the same action is recorded multiple times.

Claude-Mem implementation reference:
```typescript
const contentHash = crypto
  .createHash('sha256')
  .update(`${sessionId}|${title}|${narrative}`)
  .digest('hex');
```
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deduplication Cache
# ---------------------------------------------------------------------------


class DeduplicationCache:
    """
    Time-windowed content hash deduplication cache.

    Uses a sliding window to track recently seen content hashes.
    Duplicate detection prevents the same observation from being recorded
    multiple times within the configured time window.

    Usage:
        cache = DeduplicationCache(window_seconds=30.0)

        # Check if content is a duplicate
        if not cache.is_duplicate(session_id="s1", title="Fixed bug", narrative="..."):
            # Not a duplicate, proceed to store
            cache.mark_seen(session_id="s1", title="Fixed bug", narrative="...")
            store_observation(...)
    """

    def __init__(self, window_seconds: float = 30.0):
        """
        Initialize the deduplication cache.

        Args:
            window_seconds: Time window for duplicate detection.
                           Default 30 seconds matches Claude-Mem.
        """
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._window = window_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()  # hash -> timestamp
        self._hits = 0
        self._misses = 0

    def _compute_hash(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> str:
        """
        Compute SHA256 content hash.

        Matches Claude-Mem's implementation:
        crypto.createHash('sha256')
            .update(`${sessionId}|${title}|${narrative}`)
            .digest('hex')
        """
        content = f"{session_id}|{title}|{narrative}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _cleanup_expired(self, current_time: float) -> None:
        """Remove expired entries from cache."""
        while self._cache and current_time - list(self._cache.values())[0] > self._window:
            self._cache.popitem(last=False)

    def is_duplicate(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> bool:
        """
        Check if content is a duplicate within the time window.

        Args:
            session_id: Session identifier
            title: Observation title (maps to summary in Ariadne)
            narrative: Observation narrative (maps to detail in Ariadne)

        Returns:
            True if content is a duplicate, False otherwise.
            If False, caller should call mark_seen() after storing.
        """
        current_time = time.time()
        self._cleanup_expired(current_time)

        hash_key = self._compute_hash(session_id, title, narrative)

        if hash_key in self._cache:
            self._hits += 1
            logger.debug(f"Duplicate detected: {title[:50]}...")
            return True

        return False

    def mark_seen(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> None:
        """
        Mark content as seen (after successful storage).

        Args:
            session_id: Session identifier
            title: Observation title
            narrative: Observation narrative
        """
        current_time = time.time()
        hash_key = self._compute_hash(session_id, title, narrative)
        self._cache[hash_key] = current_time
        self._misses += 1

    def check_and_mark(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> bool:
        """
        Atomically check for duplicate and mark as seen if not.

        Convenience method combining is_duplicate() and mark_seen().

        Args:
            session_id: Session identifier
            title: Observation title
            narrative: Observation narrative

        Returns:
            True if content was already seen (duplicate), False if newly marked.
        """
        if self.is_duplicate(session_id, title, narrative):
            return True
        self.mark_seen(session_id, title, narrative)
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """Return deduplication statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "window_seconds": self._window,
            "cached_entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_dedup_cache: Optional[DeduplicationCache] = None


def get_dedup_cache() -> DeduplicationCache:
    """Get or create the module-level deduplication cache."""
    global _dedup_cache
    if _dedup_cache is None:
        _dedup_cache = DeduplicationCache()
    return _dedup_cache


def reset_dedup_cache() -> None:
    """Reset the module-level deduplication cache (mainly for testing)."""
    global _dedup_cache
    _dedup_cache = None
