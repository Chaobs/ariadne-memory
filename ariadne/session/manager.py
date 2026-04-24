"""
Session Manager — high-level API for the Session Memory feature.

This is the main entry point for all session-related operations:
  - Starting/ending sessions
  - Recording tool-use observations
  - Generating session summaries
  - Building context for injection
  - SSE real-time broadcasting

Used by:
  - ariadne/hooks/  (CLI hook adapters)
  - ariadne/mcp/tools.py (MCP Server tools)
  - ariadne/web/  (Web API endpoints)

SSE Integration:
  - When SSEBroadcaster is set, observations and summaries are broadcast in real-time
  - Content deduplication prevents duplicate observations within 30-second window
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ariadne.session.context_builder import ContextBuilder
from ariadne.session.deduplication import DeduplicationCache, get_dedup_cache
from ariadne.session.models import (
    Observation,
    ObservationType,
    Platform,
    PendingMessage,
    SessionRecord,
    SessionStatus,
    SessionSummary,
)
from ariadne.session.observation_store import ObservationStore
from ariadne.session.sse_broadcaster import SSEBroadcaster, get_broadcaster
from ariadne.session.store import SessionStore, get_store
from ariadne.session.summarizer import SessionSummarizer

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Orchestrates the full session memory lifecycle.

    Thread-safe singleton — use `get_manager()` for the global instance.

    Features:
    - SSE real-time broadcasting (when SSEBroadcaster is set)
    - Content-hash deduplication (prevents duplicate observations within 30s window)
    """

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        llm=None,
        sse_broadcaster: Optional[SSEBroadcaster] = None,
        dedup_cache: Optional[DeduplicationCache] = None,
    ):
        self._store = session_store or get_store()
        self._obs_store = ObservationStore(self._store)
        self._summarizer = SessionSummarizer(llm)
        self._context_builder = ContextBuilder(
            session_store=self._store,
            obs_store=self._obs_store,
            summarizer=self._summarizer,
        )
        # In-memory cache of active session IDs → SessionRecord
        self._active: Dict[str, SessionRecord] = {}
        self._lock = threading.Lock()
        # SSE real-time broadcasting
        self._sse_broadcaster: Optional[SSEBroadcaster] = sse_broadcaster
        # Content-hash deduplication
        self._dedup_cache: Optional[DeduplicationCache] = dedup_cache

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        project_path: str,
        platform: Platform = Platform.GENERIC,
        session_id: Optional[str] = None,
    ) -> Tuple[SessionRecord, str]:
        """
        Initialize a new session and build context for injection.

        Returns:
            (session, context_text) where context_text is ready to inject.
        """
        project_path = project_path or ""

        session = SessionRecord.new(project_path, platform)
        if session_id:
            session.id = session_id  # Allow caller to specify ID (e.g. from hook)

        self._store.create_session(session)

        with self._lock:
            self._active[session.id] = session

        # Build context from prior sessions
        try:
            context = self._context_builder.build_session_start_context(
                project_path=project_path,
                platform=platform,
            )
        except Exception as e:
            logger.warning(f"Context build failed (non-fatal): {e}")
            context = ""

        logger.info(f"Session started: {session.id} [{platform.value}] @ {project_path}")
        return session, context

    def end_session(
        self,
        session_id: str,
        generate_summary: bool = True,
    ) -> Optional[SessionSummary]:
        """
        Complete a session, optionally generating an LLM summary.

        Returns:
            SessionSummary if generated, else None.

        Features:
        - SSE real-time broadcast when summary is generated
        """
        session = self._store.get_session(session_id)
        if not session:
            logger.warning(f"end_session: unknown session {session_id}")
            return None

        observations = self._obs_store.list_for_session(session_id, limit=200)
        summary_obj: Optional[SessionSummary] = None

        if generate_summary and observations:
            try:
                summary_obj = self._summarizer.summarize_session(session, observations)
                if summary_obj:
                    self._store.complete_session(
                        session_id,
                        summary=summary_obj.narrative,
                    )
                    logger.info(f"Session summarized: {session_id}")

                    # SSE real-time broadcast
                    if self._sse_broadcaster:
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(
                                    self._sse_broadcaster.broadcast_summary(
                                        summary={
                                            "session_id": session_id,
                                            "narrative": summary_obj.narrative,
                                            "key_decisions": summary_obj.key_decisions,
                                        },
                                        session_id=session_id,
                                    )
                                )
                            else:
                                loop.run_until_complete(
                                    self._sse_broadcaster.broadcast_summary(
                                        summary={
                                            "session_id": session_id,
                                            "narrative": summary_obj.narrative,
                                        },
                                        session_id=session_id,
                                    )
                                )
                        except Exception as e:
                            logger.warning(f"SSE summary broadcast failed: {e}")

                    return summary_obj
            except Exception as e:
                logger.warning(f"Summarization failed: {e}")

        self._store.complete_session(session_id)

        # SSE session end notification
        if self._sse_broadcaster:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        self._sse_broadcaster.broadcast_session_end(session_id)
                    )
                else:
                    loop.run_until_complete(
                        self._sse_broadcaster.broadcast_session_end(session_id)
                    )
            except Exception as e:
                logger.warning(f"SSE session end broadcast failed: {e}")

        with self._lock:
            self._active.pop(session_id, None)

        return summary_obj

    def record_observation(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        project_path: str = "",
        use_llm: bool = True,
    ) -> List[Observation]:
        """
        Record a tool-use event, optionally analyzing it with LLM.

        This is called by the PostToolUse hook.
        Returns the list of observations created.

        Features:
        - Content-hash deduplication (prevents same observation within 30s)
        - SSE real-time broadcasting (when broadcaster is set)
        """
        session = self._store.get_session(session_id)
        if not session:
            # Auto-create a session if it doesn't exist
            session, _ = self.start_session(project_path, Platform.GENERIC, session_id)

        observations: List[Observation] = []

        if use_llm:
            try:
                observations = self._summarizer.analyze_tool_use(
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    project_path=project_path or session.project_path,
                )
            except Exception as e:
                logger.warning(f"LLM tool analysis failed: {e}")

        if not observations:
            # Fallback: store raw observation
            observations = self._summarizer._fallback_observation(
                session_id, tool_name, tool_input, tool_output
            )

        # Filter duplicates and broadcast
        if observations:
            dedup = self._dedup_cache or get_dedup_cache()
            filtered_obs: List[Observation] = []

            for obs in observations:
                # Check deduplication
                is_dup = dedup.check_and_mark(
                    session_id=session_id,
                    title=obs.summary,
                    narrative=obs.detail or "",
                )
                if not is_dup:
                    filtered_obs.append(obs)

            if filtered_obs:
                self._obs_store.add_many(filtered_obs)
                logger.debug(f"Recorded {len(filtered_obs)} observations for session {session_id}")

                # SSE real-time broadcast (async)
                if self._sse_broadcaster:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            for obs in filtered_obs:
                                loop.create_task(
                                    self._sse_broadcaster.broadcast_observation(
                                        observation=obs.to_dict(),
                                        session_id=session_id,
                                    )
                                )
                        else:
                            loop.run_until_complete(
                                self._sse_broadcaster.broadcast_observation(
                                    observation=filtered_obs[0].to_dict(),
                                    session_id=session_id,
                                )
                            )
                    except Exception as e:
                        logger.warning(f"SSE broadcast failed: {e}")

                return filtered_obs

        return []

    def add_observation_direct(
        self,
        session_id: str,
        obs_type: str,
        summary: str,
        detail: Optional[str] = None,
        files: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
    ) -> Observation:
        """
        Directly add a structured observation (for MCP tool or manual use).
        """
        try:
            otype = ObservationType(obs_type.lower())
        except ValueError:
            otype = ObservationType.GENERAL

        obs = Observation.new(
            session_id=session_id,
            obs_type=otype,
            summary=summary,
            detail=detail,
            files=files or [],
            concepts=concepts or [],
        )
        return self._obs_store.add(obs)

    # ------------------------------------------------------------------
    # Context injection
    # ------------------------------------------------------------------

    def get_session_start_context(
        self,
        project_path: str,
        platform: Platform = Platform.GENERIC,
    ) -> str:
        """Get context for SessionStart hook injection."""
        try:
            return self._context_builder.build_session_start_context(
                project_path=project_path,
                platform=platform,
            )
        except Exception as e:
            logger.warning(f"get_session_start_context error: {e}")
            return ""

    def get_semantic_context(
        self,
        query: str,
        project_path: str,
    ) -> str:
        """Get semantically relevant context for UserPromptSubmit hook."""
        try:
            return self._context_builder.build_semantic_context(
                query=query,
                project_path=project_path,
            )
        except Exception as e:
            logger.warning(f"get_semantic_context error: {e}")
            return ""

    # ------------------------------------------------------------------
    # Search & retrieval
    # ------------------------------------------------------------------

    def search_observations(
        self,
        query: str,
        project_path: Optional[str] = None,
        limit: int = 10,
    ) -> List[Tuple[Observation, float]]:
        """Search observations semantically."""
        return self._obs_store.search_semantic(
            query=query,
            limit=limit,
            project_path=project_path,
        )

    def get_timeline(self, session_id: str) -> dict:
        """Get full session timeline (for progressive disclosure)."""
        return self._context_builder.build_timeline(session_id)

    def list_sessions(
        self,
        project_path: Optional[str] = None,
        limit: int = 20,
    ) -> List[SessionRecord]:
        return self._store.list_sessions(project_path=project_path, limit=limit)

    def get_observations(self, obs_ids: List[str]) -> List[Observation]:
        """Get specific observations by ID (progressive disclosure step 3)."""
        result = []
        for oid in obs_ids:
            obs = self._obs_store.get(oid)
            if obs:
                result.append(obs)
        return result

    def stats(self) -> dict:
        """Return session memory statistics."""
        base = self._store.stats()
        base["active_sessions"] = len(self._active)
        return base

    def recent_context_text(self, project_path: str, limit: int = 3) -> str:
        """Human-readable recent context (for CLI display)."""
        return self._context_builder.get_recent_context_text(
            project_path=project_path, limit=limit
        )

    # -------------------------------------------------------------------------
    # SSE & Deduplication
    # -------------------------------------------------------------------------

    def set_sse_broadcaster(self, broadcaster: SSEBroadcaster) -> None:
        """Set SSE broadcaster for real-time Web UI updates."""
        self._sse_broadcaster = broadcaster

    def set_dedup_cache(self, cache: DeduplicationCache) -> None:
        """Set deduplication cache for content-hash deduplication."""
        self._dedup_cache = cache

    def get_sse_broadcaster(self) -> Optional[SSEBroadcaster]:
        """Get the SSE broadcaster instance."""
        return self._sse_broadcaster

    def get_dedup_cache(self) -> DeduplicationCache:
        """Get the deduplication cache instance."""
        return self._dedup_cache or get_dedup_cache()

    def get_dedup_stats(self) -> dict:
        """Get deduplication statistics."""
        return self.get_dedup_cache().get_stats()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[SessionManager] = None
_manager_lock = threading.Lock()


def get_manager(llm=None) -> SessionManager:
    """Get or create the module-level SessionManager singleton."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = SessionManager(llm=llm)
    return _manager


def set_manager_sse_broadcaster(broadcaster: SSEBroadcaster) -> None:
    """Set SSE broadcaster on the global SessionManager singleton."""
    manager = get_manager()
    manager.set_sse_broadcaster(broadcaster)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[SessionManager] = None
_manager_lock = threading.Lock()


def get_manager(llm=None) -> SessionManager:
    """Get or create the module-level SessionManager singleton."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = SessionManager(llm=llm)
    return _manager
