"""
MCP WAL (Write-Ahead Log) Audit System for Ariadne.

Provides comprehensive audit logging for all MCP operations:
- Operation tracking with timestamps
- Parameter validation logging
- Cache invalidation detection
- Performance metrics

Inspired by MemPalace's WAL implementation.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
import logging
import hashlib

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Types of operations logged in WAL."""
    TOOL_CALL = "tool_call"
    TOOL_LIST = "tool_list"
    RESOURCE_READ = "resource_read"
    RESOURCE_LIST = "resource_list"
    PROMPT_GET = "prompt_get"
    PROMPT_LIST = "prompt_list"
    SEARCH = "search"
    INGEST = "ingest"
    GRAPH_QUERY = "graph_query"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_INVALIDATE = "cache_invalidate"
    VALIDATION_ERROR = "validation_error"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class WALEntry:
    """A single WAL log entry."""
    timestamp: str
    operation: str
    operation_type: OperationType
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    cache_hit: bool = False
    log_level: LogLevel = LogLevel.INFO
    request_id: Optional[str] = None
    client_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "operation": self.operation,
            "operation_type": self.operation_type.value,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "cache_hit": self.cache_hit,
            "log_level": self.log_level.value,
            "request_id": self.request_id,
            "client_info": self.client_info,
        }


class WALAuditLogger:
    """
    Write-Ahead Log audit system for MCP operations.

    Features:
    - Thread-safe SQLite-backed WAL
    - Operation metrics and statistics
    - Cache invalidation tracking
    - Parameter schema validation logging
    - Automatic log rotation

    Usage:
        wal = WALAuditLogger("./data/.ariadne/wal.db")
        with wal.log_operation("ariadne_search", {"query": "test"}):
            results = search_vector_store("test")
        # Automatically logs duration, success/failure
    """

    _instance: Optional["WALAuditLogger"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_entries: int = 100000,
        rotation_size_mb: int = 100,
    ):
        """
        Initialize WAL audit logger.

        Args:
            db_path: Path to WAL SQLite database. Defaults to .ariadne/wal.db
            max_entries: Maximum entries before rotation warning
            rotation_size_mb: Size threshold for rotation warning
        """
        if db_path is None:
            db_path = str(Path.cwd() / ".ariadne" / "wal.db")

        self.db_path = Path(db_path)
        self.max_entries = max_entries
        self.rotation_size_mb = rotation_size_mb
        self._request_counter = 0
        self._start_time = time.time()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        # Metrics
        self._metrics_lock = threading.Lock()
        self._metrics: Dict[str, int] = {}
        self._total_duration_ms: Dict[str, float] = {}

        logger.info(f"WAL audit logger initialized at {db_path}")

    @classmethod
    def get_instance(cls, **kwargs) -> "WALAuditLogger":
        """Get singleton instance of WAL audit logger."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    def _init_db(self) -> None:
        """Initialize WAL database schema."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Main WAL table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                operation TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                params TEXT,
                result TEXT,
                error TEXT,
                duration_ms REAL DEFAULT 0,
                cache_hit INTEGER DEFAULT 0,
                log_level TEXT DEFAULT 'info',
                request_id TEXT,
                client_info TEXT,
                checksum TEXT
            )
        """)

        # Indexes for efficient queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON wal(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operation ON wal(operation)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operation_type ON wal(operation_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_id ON wal(request_id)")

        # Metrics summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                operation TEXT PRIMARY KEY,
                call_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                total_duration_ms REAL DEFAULT 0,
                cache_hit_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)

        # Cache invalidation log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_invalidation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                reason TEXT,
                source_file TEXT,
                source_inode INTEGER,
                source_mtime REAL
            )
        """)

        conn.commit()
        conn.close()

    def _generate_checksum(self, entry: Dict[str, Any]) -> str:
        """Generate checksum for log entry integrity."""
        data = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_counter += 1
        timestamp = int(time.time() * 1000)
        return f"req_{timestamp}_{self._request_counter:06d}"

    @contextmanager
    def log_operation(
        self,
        operation: str,
        operation_type: OperationType,
        params: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for logging MCP operations.

        Usage:
            with wal.log_operation("ariadne_search", OperationType.SEARCH, {"query": "test"}):
                results = search(query)
            # Automatically logs duration, success/failure
        """
        request_id = self._generate_request_id()
        start_time = time.time()

        entry = WALEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            operation_type=operation_type,
            params=params or {},
            request_id=request_id,
            client_info=client_info,
        )

        try:
            yield entry
            duration_ms = (time.time() - start_time) * 1000
            entry.duration_ms = duration_ms
            entry.log_level = LogLevel.INFO
            self._write_entry(entry)
            self._update_metrics(operation, entry, error=False)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            entry.duration_ms = duration_ms
            entry.error = str(e)
            entry.log_level = LogLevel.ERROR
            self._write_entry(entry)
            self._update_metrics(operation, entry, error=True)
            raise

    def _write_entry(self, entry: WALEntry) -> None:
        """Write entry to WAL database."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        entry_dict = entry.to_dict()
        checksum = self._generate_checksum(entry_dict)

        try:
            cursor.execute("""
                INSERT INTO wal (
                    timestamp, operation, operation_type, params, result, error,
                    duration_ms, cache_hit, log_level, request_id, client_info, checksum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp,
                entry.operation,
                entry.operation_type.value,
                json.dumps(entry.params),
                json.dumps(entry.result) if entry.result else None,
                entry.error,
                entry.duration_ms,
                1 if entry.cache_hit else 0,
                entry.log_level.value,
                entry.request_id,
                json.dumps(entry.client_info) if entry.client_info else None,
                checksum,
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to write WAL entry: {e}")
        finally:
            conn.close()

    def _update_metrics(
        self,
        operation: str,
        entry: WALEntry,
        error: bool = False,
    ) -> None:
        """Update running metrics for an operation."""
        with self._metrics_lock:
            # Update in-memory metrics
            self._metrics[operation] = self._metrics.get(operation, 0) + 1
            self._total_duration_ms[operation] = (
                self._total_duration_ms.get(operation, 0) + entry.duration_ms
            )

            # Update SQLite metrics
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO metrics (operation, call_count, error_count, total_duration_ms, cache_hit_count, last_updated)
                VALUES (?, 1, ?, ?, ?, ?)
                ON CONFLICT(operation) DO UPDATE SET
                    call_count = call_count + 1,
                    error_count = error_count + ?,
                    total_duration_ms = total_duration_ms + ?,
                    cache_hit_count = cache_hit_count + ?,
                    last_updated = ?
            """, (
                operation,
                1 if error else 0,
                entry.duration_ms,
                1 if entry.cache_hit else 0,
                datetime.now(timezone.utc).isoformat(),
                # Conflicted values
                1 if error else 0,
                entry.duration_ms,
                1 if entry.cache_hit else 0,
                datetime.now(timezone.utc).isoformat(),
            ))

            conn.commit()
            conn.close()

    def log_cache_invalidation(
        self,
        cache_key: str,
        reason: str,
        source_file: Optional[str] = None,
        source_inode: Optional[int] = None,
        source_mtime: Optional[float] = None,
    ) -> None:
        """
        Log a cache invalidation event.

        Args:
            cache_key: The cache key that was invalidated
            reason: Reason for invalidation
            source_file: File path that triggered invalidation
            source_inode: Inode number of source file
            source_mtime: Modified time of source file
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO cache_invalidation (
                timestamp, cache_key, reason, source_file, source_inode, source_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            cache_key,
            reason,
            source_file,
            source_inode,
            source_mtime,
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Cache invalidation logged: {cache_key} - {reason}")

    def log_validation_error(
        self,
        operation: str,
        params: Dict[str, Any],
        error: str,
        schema_errors: List[Dict[str, Any]],
    ) -> None:
        """
        Log parameter validation errors.

        Args:
            operation: The operation that failed validation
            params: Parameters that were validated
            error: Overall validation error message
            schema_errors: List of individual schema violations
        """
        entry = WALEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            operation_type=OperationType.VALIDATION_ERROR,
            params=params,
            error=error,
            log_level=LogLevel.WARNING,
        )
        entry.result = {"schema_errors": schema_errors}
        self._write_entry(entry)

    def get_metrics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get operation metrics.

        Args:
            operation: Specific operation to get metrics for, or None for all

        Returns:
            Dictionary of metrics by operation
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        if operation:
            cursor.execute("SELECT * FROM metrics WHERE operation = ?", (operation,))
        else:
            cursor.execute("SELECT * FROM metrics")

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        metrics = {}
        for row in rows:
            m = dict(zip(columns, row))
            # Calculate average duration
            if m["call_count"] > 0:
                m["avg_duration_ms"] = m["total_duration_ms"] / m["call_count"]
            else:
                m["avg_duration_ms"] = 0
            # Calculate error rate
            if m["call_count"] > 0:
                m["error_rate"] = m["error_count"] / m["call_count"]
            else:
                m["error_rate"] = 0
            metrics[m["operation"]] = m

        return metrics

    def get_recent_entries(
        self,
        limit: int = 100,
        operation_type: Optional[OperationType] = None,
        level: Optional[LogLevel] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent WAL entries.

        Args:
            limit: Maximum entries to return
            operation_type: Filter by operation type
            level: Filter by log level

        Returns:
            List of recent log entries
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        query = "SELECT * FROM wal WHERE 1=1"
        params = []

        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type.value)

        if level:
            query += " AND log_level = ?"
            params.append(level.value)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        entries = []
        for row in rows:
            entry = dict(zip(columns, row))
            # Parse JSON fields
            if entry.get("params"):
                entry["params"] = json.loads(entry["params"])
            if entry.get("result"):
                entry["result"] = json.loads(entry["result"])
            if entry.get("client_info"):
                entry["client_info"] = json.loads(entry["client_info"])
            entry["cache_hit"] = bool(entry["cache_hit"])
            entries.append(entry)

        return entries

    def get_cache_invalidation_history(
        self,
        cache_key: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get cache invalidation history."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        if cache_key:
            cursor.execute("""
                SELECT * FROM cache_invalidation
                WHERE cache_key = ?
                ORDER BY id DESC LIMIT ?
            """, (cache_key, limit))
        else:
            cursor.execute("""
                SELECT * FROM cache_invalidation
                ORDER BY id DESC LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall WAL statistics."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        # Total entries
        cursor.execute("SELECT COUNT(*) FROM wal")
        total_entries = cursor.fetchone()[0]

        # Entries by type
        cursor.execute("""
            SELECT operation_type, COUNT(*) as count
            FROM wal GROUP BY operation_type
        """)
        by_type = dict(cursor.fetchall())

        # Entries by level
        cursor.execute("""
            SELECT log_level, COUNT(*) as count
            FROM wal GROUP BY log_level
        """)
        by_level = dict(cursor.fetchall())

        # Recent errors
        cursor.execute("""
            SELECT COUNT(*) FROM wal
            WHERE log_level = 'error' AND timestamp > datetime('now', '-1 day')
        """)
        recent_errors = cursor.fetchone()[0]

        # Cache invalidations
        cursor.execute("SELECT COUNT(*) FROM cache_invalidation")
        total_invalidations = cursor.fetchone()[0]

        # Database size
        db_size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0

        conn.close()

        return {
            "total_entries": total_entries,
            "entries_by_type": by_type,
            "entries_by_level": by_level,
            "recent_errors_24h": recent_errors,
            "total_cache_invalidations": total_invalidations,
            "database_size_mb": round(db_size_mb, 2),
            "uptime_seconds": time.time() - self._start_time,
        }

    def vacuum(self) -> bool:
        """Vacuum the WAL database to reclaim space."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.close()
            logger.info("WAL database vacuumed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to vacuum WAL database: {e}")
            return False

    def reset(self) -> None:
        """Reset all WAL data (use with caution)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wal")
        cursor.execute("DELETE FROM metrics")
        cursor.execute("DELETE FROM cache_invalidation")
        conn.commit()
        conn.close()
        logger.warning("WAL data reset")

    def close(self) -> None:
        """Close the WAL logger and vacuum if needed."""
        stats = self.get_statistics()
        if stats["database_size_mb"] > self.rotation_size_mb:
            logger.warning(
                f"WAL database size ({stats['database_size_mb']}MB) exceeds "
                f"threshold ({self.rotation_size_mb}MB). Consider running vacuum."
            )
