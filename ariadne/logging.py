"""
Ariadne Rotating File Logger.

Provides structured logging with automatic rotation:
- One log file per server session (named by start timestamp)
- Keeps the most recent 10 log files, older ones are auto-deleted
- Logs include startup info, operations, errors, and timing
- Integrated with Python's standard logging framework

Log file location: .ariadne/logs/
File naming: ariadne_YYYYMMDD_HHMMSS.log
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Configuration ──────────────────────────────────────────────────────────

MAX_LOG_FILES = 10
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Path Setup ─────────────────────────────────────────────────────────────

from ariadne.paths import ARIADNE_DIR

LOGS_DIR = ARIADNE_DIR / "logs"


def _ensure_logs_dir() -> None:
    """Create logs directory if it doesn't exist."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_logs() -> None:
    """Delete oldest log files if count exceeds MAX_LOG_FILES."""
    _ensure_logs_dir()

    log_files = sorted(
        LOGS_DIR.glob("ariadne_*.log"),
        key=lambda p: p.stat().st_mtime,
    )

    while len(log_files) > MAX_LOG_FILES:
        oldest = log_files.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass


# ── Session Logger ─────────────────────────────────────────────────────────

class AriadneSessionLogger:
    """
    Manages a per-session log file with rotation.

    Usage:
        logger = AriadneSessionLogger()
        logger.start("web", host="127.0.0.1", port=8770)
        logger.info("ingest", file="notes.md", docs_added=3)
        logger.error("search", error="Connection timeout")
    """

    def __init__(self):
        self._start_time: Optional[float] = None
        self._start_method: str = ""
        self._handler: Optional[logging.FileHandler] = None
        self._logger = logging.getLogger("ariadne.session")
        self._logger.setLevel(logging.DEBUG)
        self._setup_done = False

    def start(self, method: str, **kwargs) -> None:
        """
        Start a new logging session.

        Args:
            method: How Ariadne was launched (e.g. "web", "cli")
            **kwargs: Additional startup parameters to log
        """
        if self._setup_done:
            return

        self._start_time = time.time()
        self._start_method = method
        _ensure_logs_dir()
        _rotate_logs()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"ariadne_{timestamp}.log"

        self._handler = logging.FileHandler(
            str(log_file), encoding="utf-8", mode="a"
        )
        self._handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        self._handler.setFormatter(formatter)
        self._logger.addHandler(self._handler)

        # Also add a console handler for ERROR level
        console = logging.StreamHandler()
        console.setLevel(logging.ERROR)
        console.setFormatter(formatter)
        self._logger.addHandler(console)

        # Log startup
        self._logger.info("=" * 70)
        self._logger.info(f"Ariadne session started | method={method}")
        for key, val in kwargs.items():
            self._logger.info(f"  {key}={val}")
        self._logger.info(f"  log_file={log_file}")
        self._logger.info(f"  pid={os.getpid()}")
        self._logger.info(f"  python={os.sys.version.split()[0]}")
        self._logger.info("=" * 70)

        self._setup_done = True

    def info(self, operation: str, **kwargs) -> None:
        """Log an informational operation."""
        details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"[{operation}] {details}" if details else f"[{operation}]"
        self._logger.info(msg)

    def warning(self, operation: str, **kwargs) -> None:
        """Log a warning."""
        details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"[{operation}] {details}" if details else f"[{operation}]"
        self._logger.warning(msg)

    def error(self, operation: str, **kwargs) -> None:
        """Log an error."""
        details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"[{operation}] {details}" if details else f"[{operation}]"
        self._logger.error(msg)

    def debug(self, operation: str, **kwargs) -> None:
        """Log debug information."""
        details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"[{operation}] {details}" if details else f"[{operation}]"
        self._logger.debug(msg)

    def shutdown(self) -> None:
        """Close the session and log final summary."""
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            self._logger.info("=" * 70)
            self._logger.info(
                f"Ariadne session ended | method={self._start_method} "
                f"| duration={elapsed:.1f}s"
            )
            self._logger.info("=" * 70)

        if self._handler:
            self._logger.removeHandler(self._handler)
            self._handler.close()
            self._handler = None


# ── Module-level singleton ─────────────────────────────────────────────────

_session_logger = AriadneSessionLogger()


def get_session_logger() -> AriadneSessionLogger:
    """Get the global session logger instance."""
    return _session_logger
