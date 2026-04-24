"""
Session Store -- SQLite-backed persistence for sessions, observations,
pending messages, and user prompts.

Mirrors Claude-Mem's SessionStore + PendingMessageStore, adapted for Python.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional

from ariadne.session.models import (
    MessageStatus,
    Observation,
    ObservationType,
    PendingMessage,
    Platform,
    SessionRecord,
    SessionStatus,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    project_path    TEXT NOT NULL,
    platform        TEXT NOT NULL DEFAULT 'generic',
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    summary         TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    metadata        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS observations (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    obs_type        TEXT NOT NULL DEFAULT 'general',
    summary         TEXT NOT NULL,
    detail          TEXT,
    files           TEXT NOT NULL DEFAULT '[]',
    concepts        TEXT NOT NULL DEFAULT '[]',
    tool_name       TEXT,
    tool_input      TEXT,
    tool_output     TEXT,
    created_at      TEXT NOT NULL,
    chroma_synced   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pending_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    payload         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    claimed_at      TEXT,
    processed_at    TEXT,
    error           TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_obs_session  ON observations(session_id);
CREATE INDEX IF NOT EXISTS idx_obs_type     ON observations(obs_type);
CREATE INDEX IF NOT EXISTS idx_obs_created  ON observations(created_at);
CREATE INDEX IF NOT EXISTS idx_pm_status    ON pending_messages(status);
"""


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------


class SessionStore:
    """
    Thread-safe SQLite store for session memory data.

    Usage:
        store = SessionStore(db_path)
        session = SessionRecord.new(project_path="/my/project")
        store.create_session(session)
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from ariadne.paths import ARIADNE_DIR
            db_path = ARIADNE_DIR / "session_memory.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _init_db(self) -> None:
        # PRAGMAs + DDL must run OUTSIDE any DEFERRED transaction to take effect.
        # Use a dedicated auto-commit connection for this one-time init step.
        init_conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        try:
            init_conn.execute("PRAGMA journal_mode=WAL")
            init_conn.execute("PRAGMA foreign_keys=ON")
            init_conn.executescript(_SCHEMA)
        finally:
            init_conn.close()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Thread-local connection. Uses DEFERRED transactions (Python's default).

        IMPORTANT: Python's sqlite3 does NOT auto-commit — the caller must
        explicitly commit() on normal exit or rollback() on exception.
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        conn = self._local.conn
        try:
            yield conn
            if conn.in_transaction:
                conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(self, session: SessionRecord) -> SessionRecord:
        """Insert a new session. Silently handles duplicate IDs (idempotent)."""
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sessions
                    (id, project_path, platform, started_at, ended_at,
                     summary, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.id,
                        session.project_path,
                        session.platform.value,
                        session.started_at,
                        session.ended_at,
                        session.summary,
                        session.status.value,
                        json.dumps(session.metadata),
                    ),
                )
        except Exception:
            # If INSERT OR IGNORE still fails (e.g., other constraints),
            # try an UPDATE as fallback.
            with self._conn() as conn:
                conn.execute(
                    """
                    UPDATE sessions SET project_path=?, platform=?, summary=?,
                    status=?, metadata=? WHERE id=?
                    """,
                    (
                        session.project_path,
                        session.platform.value,
                        session.summary,
                        session.status.value,
                        json.dumps(session.metadata),
                        session.id,
                    ),
                )
        return session

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def update_session(self, session: SessionRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE sessions SET ended_at=?, summary=?, status=?, metadata=?
                WHERE id=?
                """,
                (
                    session.ended_at,
                    session.summary,
                    session.status.value,
                    json.dumps(session.metadata),
                    session.id,
                ),
            )

    def complete_session(self, session_id: str, summary: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE sessions SET ended_at=?, summary=?, status=?
                WHERE id=?
                """,
                (
                    now,
                    summary,
                    SessionStatus.SUMMARIZED.value if summary else SessionStatus.COMPLETED.value,
                    session_id,
                ),
            )

    def list_sessions(
        self,
        project_path: Optional[str] = None,
        platform: Optional[Platform] = None,
        status: Optional[SessionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SessionRecord]:
        conditions = []
        params = []
        if project_path:
            conditions.append("project_path = ?")
            params.append(project_path)
        if platform:
            conditions.append("platform = ?")
            params.append(platform.value)
        if status:
            conditions.append("status = ?")
            params.append(status.value)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM sessions {where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_latest_session(
        self, project_path: Optional[str] = None
    ) -> Optional[SessionRecord]:
        sessions = self.list_sessions(project_path=project_path, limit=1)
        return sessions[0] if sessions else None

    # ------------------------------------------------------------------
    # Observation CRUD
    # ------------------------------------------------------------------

    def add_observation(self, obs: Observation) -> Observation:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO observations
                (id, session_id, obs_type, summary, detail, files, concepts,
                 tool_name, tool_input, tool_output, created_at, chroma_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs.id,
                    obs.session_id,
                    obs.obs_type.value,
                    obs.summary,
                    obs.detail,
                    json.dumps(obs.files),
                    json.dumps(obs.concepts),
                    obs.tool_name,
                    json.dumps(obs.tool_input) if obs.tool_input else None,
                    obs.tool_output,
                    obs.created_at,
                    int(obs.chroma_synced),
                ),
            )
        return obs

    def get_observation(self, obs_id: str) -> Optional[Observation]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM observations WHERE id = ?", (obs_id,)
            ).fetchone()
        return self._row_to_obs(row) if row else None

    def list_observations(
        self,
        session_id: Optional[str] = None,
        obs_type: Optional[ObservationType] = None,
        unsynced_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Observation]:
        conditions = []
        params = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if obs_type:
            conditions.append("obs_type = ?")
            params.append(obs_type.value)
        if unsynced_only:
            conditions.append("chroma_synced = 0")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM observations {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [self._row_to_obs(r) for r in rows]

    def mark_chroma_synced(self, obs_ids: List[str]) -> None:
        if not obs_ids:
            return
        placeholders = ",".join("?" * len(obs_ids))
        with self._conn() as conn:
            conn.execute(
                f"UPDATE observations SET chroma_synced=1 WHERE id IN ({placeholders})",
                obs_ids,
            )

    # ------------------------------------------------------------------
    # Pending Messages (CLAIM-CONFIRM queue)
    # ------------------------------------------------------------------

    def enqueue_message(self, msg: PendingMessage) -> PendingMessage:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pending_messages
                (id, session_id, payload, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    msg.id,
                    msg.session_id,
                    json.dumps(msg.payload),
                    msg.status.value,
                    msg.created_at,
                ),
            )
        return msg

    def claim_next_message(self) -> Optional[PendingMessage]:
        """Atomically claim the oldest pending message."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_messages WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE pending_messages SET status='claimed', claimed_at=? WHERE id=?",
                (now, row["id"]),
            )
        msg = self._row_to_pm(row)
        msg.status = MessageStatus.CLAIMED
        msg.claimed_at = now
        return msg

    def confirm_processed(self, msg_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE pending_messages SET status='processed', processed_at=? WHERE id=?",
                (now, msg_id),
            )

    def mark_failed(self, msg_id: str, error: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE pending_messages SET status='failed', error=? WHERE id=?",
                (error, msg_id),
            )

    def count_pending(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM pending_messages WHERE status='pending'"
            ).fetchone()
        return row["n"] if row else 0

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        with self._conn() as conn:
            s = conn.execute("SELECT COUNT(*) as n FROM sessions").fetchone()
            o = conn.execute("SELECT COUNT(*) as n FROM observations").fetchone()
            p = conn.execute(
                "SELECT COUNT(*) as n FROM pending_messages WHERE status='pending'"
            ).fetchone()
        return {
            "sessions": s["n"] if s else 0,
            "observations": o["n"] if o else 0,
            "pending_messages": p["n"] if p else 0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> SessionRecord:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        return SessionRecord.from_dict(d)

    @staticmethod
    def _row_to_obs(row: sqlite3.Row) -> Observation:
        return Observation.from_dict(dict(row))

    @staticmethod
    def _row_to_pm(row: sqlite3.Row) -> PendingMessage:
        d = dict(row)
        return PendingMessage(
            id=d["id"],
            session_id=d["session_id"],
            payload=json.loads(d["payload"]),
            status=MessageStatus(d["status"]),
            created_at=d["created_at"],
            claimed_at=d.get("claimed_at"),
            processed_at=d.get("processed_at"),
            error=d.get("error"),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[SessionStore] = None
_store_lock = threading.Lock()


def get_store(db_path: Optional[Path] = None) -> SessionStore:
    """Get or create the module-level SessionStore singleton."""
    global _store
    with _store_lock:
        if _store is None:
            _store = SessionStore(db_path)
    return _store
