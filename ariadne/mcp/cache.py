"""
MCP Cache Invalidation Detection for Ariadne.

Provides cache invalidation based on file system metadata:
- inode tracking
- mtime (modified time) monitoring
- Automatic invalidation on source file changes
- Cache key generation

Inspired by MemPalace's cache invalidation mechanism.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from functools import wraps
import weakref

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with metadata for invalidation detection."""
    key: str
    value: Any
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_files: List[str] = field(default_factory=list)  # Source files this cache depends on
    source_inodes: List[int] = field(default_factory=list)  # Inodes of source files
    source_mtimes: List[float] = field(default_factory=list)  # mtimes at creation
    hit_count: int = 0
    size_bytes: int = 0

    def is_valid(self) -> bool:
        """Check if the cache entry is still valid based on source files."""
        for file_path in self.source_files:
            if not os.path.exists(file_path):
                return False
            try:
                file_stat = os.stat(file_path)
                idx = self.source_files.index(file_path)
                if idx < len(self.source_mtimes):
                    if file_stat.st_mtime != self.source_mtimes[idx]:
                        return False
                    if file_stat.st_ino != self.source_inodes[idx]:
                        return False
            except OSError:
                return False
        return True

    def touch(self) -> None:
        """Update access time."""
        self.accessed_at = datetime.now(timezone.utc).isoformat()
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "hit_count": self.hit_count,
            "size_bytes": self.size_bytes,
            "source_files": self.source_files,
        }


class CacheInvalidationDetector:
    """
    Detects cache invalidation needs based on file system changes.

    Monitors:
    - File modification times (mtime)
    - File inode numbers
    - Directory changes

    Usage:
        detector = CacheInvalidationDetector(wal_logger=wal)
        cache = detector.create_cached_function(
            my_function,
            source_files=["/path/to/data.json"]
        )
        result = cache("arg1", "arg2")  # Cached if data.json unchanged
    """

    def __init__(
        self,
        wal_logger: Optional[Any] = None,
        default_ttl_seconds: float = 3600,
    ):
        """
        Initialize cache invalidation detector.

        Args:
            wal_logger: Optional WALAuditLogger for audit logging
            default_ttl_seconds: Default TTL for cache entries
        """
        self.wal_logger = wal_logger
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._watched_files: Set[str] = set()
        self._invalidation_callbacks: Dict[str, List[Callable]] = {}

    def _generate_cache_key(self, func_name: str, args: Tuple, kwargs: Dict) -> str:
        """Generate a cache key from function name and arguments."""
        key_parts = [func_name]

        # Add positional arguments
        for arg in args:
            if hasattr(arg, "__file__"):
                key_parts.append(arg.__file__)
            else:
                key_parts.append(str(arg))

        # Add keyword arguments
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")

        key_str = "|".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def _get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file metadata for invalidation tracking."""
        try:
            file_stat = os.stat(file_path)
            return {
                "inode": file_stat.st_ino,
                "mtime": file_stat.st_mtime,
                "size": file_stat.st_size,
            }
        except OSError:
            return None

    def get_or_create(
        self,
        key: str,
        source_files: Optional[List[str]] = None,
        factory: Optional[Callable] = None,
        ttl: Optional[float] = None,
    ) -> Tuple[Any, bool]:
        """
        Get cached value or create if missing/stale.

        Args:
            key: Cache key
            source_files: Source files to track for invalidation
            factory: Factory function to create value if cache miss
            ttl: Time-to-live in seconds

        Returns:
            Tuple of (value, cache_hit)
        """
        ttl = ttl or self.default_ttl

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                # Cache miss
                if factory is None:
                    raise ValueError(f"No factory provided for cache key: {key}")
                value = factory()
                self._set(key, value, source_files=source_files)
                return value, False

            # Check if entry is still valid
            if not entry.is_valid():
                logger.debug(f"Cache invalidated for key: {key}")
                if self.wal_logger:
                    self.wal_logger.log_cache_invalidation(
                        cache_key=key,
                        reason="source_file_changed",
                        source_file=", ".join(entry.source_files) if entry.source_files else None,
                    )
                self._invalidate(key)
                if factory is None:
                    raise ValueError(f"Cache invalidated and no factory for key: {key}")
                value = factory()
                self._set(key, value, source_files=source_files)
                return value, False

            # Check TTL
            created_time = datetime.fromisoformat(entry.created_at)
            age_seconds = (datetime.now(timezone.utc) - created_time).total_seconds()
            if age_seconds > ttl:
                logger.debug(f"Cache TTL expired for key: {key}")
                if self.wal_logger:
                    self.wal_logger.log_cache_invalidation(
                        cache_key=key,
                        reason="ttl_expired",
                    )
                self._invalidate(key)
                if factory is None:
                    raise ValueError(f"Cache TTL expired and no factory for key: {key}")
                value = factory()
                self._set(key, value, source_files=source_files)
                return value, False

            # Cache hit
            entry.touch()
            return entry.value, True

    def _set(
        self,
        key: str,
        value: Any,
        source_files: Optional[List[str]] = None,
    ) -> CacheEntry:
        """Set a cache entry with source file tracking."""
        source_files = source_files or []
        source_inodes = []
        source_mtimes = []

        for file_path in source_files:
            metadata = self._get_file_metadata(file_path)
            if metadata:
                source_inodes.append(metadata["inode"])
                source_mtimes.append(metadata["mtime"])
                self._watched_files.add(file_path)

        # Estimate size
        import sys
        size = sys.getsizeof(value)

        entry = CacheEntry(
            key=key,
            value=value,
            source_files=source_files,
            source_inodes=source_inodes,
            source_mtimes=source_mtimes,
            size_bytes=size,
        )

        self._cache[key] = entry
        return entry

    def _invalidate(self, key: str) -> None:
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]

        # Fire callbacks
        if key in self._invalidation_callbacks:
            for callback in self._invalidation_callbacks[key]:
                try:
                    callback(key)
                except Exception as e:
                    logger.error(f"Invalidation callback failed: {e}")

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: Key pattern to match (supports * wildcard)

        Returns:
            Number of entries invalidated
        """
        count = 0
        with self._lock:
            keys_to_delete = []
            for key in self._cache:
                if self._matches_pattern(key, pattern):
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                self._invalidate(key)
                count += 1

        return count

    def invalidate_source_file(self, file_path: str) -> int:
        """
        Invalidate all cache entries that depend on a source file.

        Args:
            file_path: Source file path

        Returns:
            Number of entries invalidated
        """
        count = 0
        with self._lock:
            keys_to_delete = []
            for key, entry in self._cache.items():
                if file_path in entry.source_files:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                self._invalidate(key)
                count += 1

        if count > 0 and self.wal_logger:
            metadata = self._get_file_metadata(file_path)
            self.wal_logger.log_cache_invalidation(
                cache_key=f"pattern:*",
                reason=f"source_file_modified",
                source_file=file_path,
                source_inode=metadata["inode"] if metadata else None,
                source_mtime=metadata["mtime"] if metadata else None,
            )

        return count

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (supports * wildcard)."""
        if "*" not in pattern:
            return key == pattern

        import fnmatch
        return fnmatch.fnmatch(key, pattern)

    def on_invalidation(self, key_pattern: str, callback: Callable) -> None:
        """
        Register a callback for cache invalidation.

        Args:
            key_pattern: Pattern to match (supports * wildcard)
            callback: Function to call when matching keys are invalidated
        """
        if key_pattern not in self._invalidation_callbacks:
            self._invalidation_callbacks[key_pattern] = []
        self._invalidation_callbacks[key_pattern].append(callback)

    def create_cached_function(
        self,
        func: Callable,
        source_files: Optional[List[str]] = None,
        ttl: Optional[float] = None,
        key_prefix: Optional[str] = None,
    ) -> Callable:
        """
        Create a cached version of a function.

        Args:
            func: Function to cache
            source_files: Source files to track for invalidation
            ttl: Time-to-live in seconds
            key_prefix: Prefix for cache keys

        Returns:
            Cached version of the function
        """
        prefix = key_prefix or func.__name__

        @wraps(func)
        def cached_func(*args, **kwargs):
            cache_key = self._generate_cache_key(prefix, args, kwargs)

            value, hit = self.get_or_create(
                key=cache_key,
                source_files=source_files,
                factory=lambda: func(*args, **kwargs),
                ttl=ttl,
            )

            if hit and self.wal_logger:
                self.wal_logger.log_operation(
                    operation=func.__name__,
                    operation_type="cache_hit",
                    params={"key": cache_key},
                ).__enter__().__exit__()

            return value

        return cached_func

    def clear(self) -> int:
        """Clear all cache entries."""
        count = len(self._cache)
        with self._lock:
            self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        return count

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_hits = sum(e.hit_count for e in self._cache.values())
            total_size = sum(e.size_bytes for e in self._cache.values())

            return {
                "entry_count": len(self._cache),
                "total_hits": total_hits,
                "total_size_bytes": total_size,
                "watched_files_count": len(self._watched_files),
                "watched_files": list(self._watched_files),
            }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            return entry.is_valid()


class MCPCacheManager:
    """
    Manages MCP-specific caches with invalidation detection.

    Provides cached versions of common MCP operations.
    """

    def __init__(self, wal_logger: Optional[Any] = None):
        """
        Initialize MCP cache manager.

        Args:
            wal_logger: Optional WALAuditLogger
        """
        self.wal_logger = wal_logger
        self._detector = CacheInvalidationDetector(wal_logger=wal_logger)
        self._tools_cache = CacheInvalidationDetector(wal_logger=wal_logger)
        self._resources_cache = CacheInvalidationDetector(wal_logger=wal_logger)

    def cached_search(
        self,
        func: Callable,
        source_files: Optional[List[str]] = None,
        ttl: float = 300,
    ) -> Callable:
        """Create a cached search function."""
        return self._detector.create_cached_function(
            func,
            source_files=source_files,
            ttl=ttl,
            key_prefix="search",
        )

    def cached_tool_list(self, func: Callable) -> Callable:
        """Create a cached tool list function (tools rarely change)."""
        return self._detector.create_cached_function(
            func,
            ttl=3600,  # 1 hour default
            key_prefix="tool_list",
        )

    def cached_resource_list(self, func: Callable) -> Callable:
        """Create a cached resource list function."""
        return self._detector.create_cached_function(
            func,
            ttl=3600,
            key_prefix="resource_list",
        )

    def invalidate_on_file_change(self, file_path: str) -> None:
        """Register a file for change monitoring."""
        self._detector._watched_files.add(file_path)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches."""
        return {
            "main": self._detector.stats(),
            "tools": self._tools_cache.stats(),
            "resources": self._resources_cache.stats(),
        }

    def clear_all(self) -> None:
        """Clear all caches."""
        self._detector.clear()
        self._tools_cache.clear()
        self._resources_cache.clear()
