"""
Context Builder — generates injected context for session start.

Mirrors Claude-Mem's ContextBuilder.ts: queries recent sessions and
observations, then produces a formatted context block to inject into
the AI's system prompt at the beginning of a new session.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ariadne.session.models import Observation, Platform, SessionRecord, SessionStatus
from ariadne.session.observation_store import ObservationStore
from ariadne.session.privacy import wrap_context_injection
from ariadne.session.store import SessionStore, get_store
from ariadne.session.summarizer import SessionSummarizer

logger = logging.getLogger(__name__)

# Maximum number of recent sessions to look back
_MAX_SESSIONS = 5
# Maximum observations to include per session
_MAX_OBS_PER_SESSION = 10
# Maximum total observations for semantic search injection
_MAX_SEMANTIC_OBS = 5


class ContextBuilder:
    """
    Builds context blocks for injection into a new AI session.

    Three injection points (mirroring Claude-Mem):
    1. SessionStart — inject full prior context (summaries + timeline)
    2. UserPromptSubmit — inject semantically relevant observations
    3. (Internal) — build plain text for storage/summary
    """

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        obs_store: Optional[ObservationStore] = None,
        summarizer: Optional[SessionSummarizer] = None,
        llm=None,
    ):
        self._session_store = session_store or get_store()
        self._obs_store = obs_store or ObservationStore(self._session_store)
        self._summarizer = summarizer or SessionSummarizer(llm)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_session_start_context(
        self,
        project_path: str,
        platform: Platform = Platform.GENERIC,
        max_tokens_hint: int = 1500,
    ) -> str:
        """
        Build the full context injection for a SessionStart hook.

        Returns context wrapped in <ariadne-context> tags, ready to prepend
        to the AI's system prompt or first user message.
        """
        sessions = self._session_store.list_sessions(
            project_path=project_path,
            status=None,          # All completed sessions
            limit=_MAX_SESSIONS,
        )
        # Filter out active sessions (only include completed/summarized)
        sessions = [
            s for s in sessions
            if s.status in (SessionStatus.COMPLETED, SessionStatus.SUMMARIZED)
        ]

        if not sessions:
            return ""

        # Gather recent observations from the last session
        recent_obs: List[Observation] = []
        if sessions:
            recent_obs = self._obs_store.list_for_session(
                sessions[0].id, limit=_MAX_OBS_PER_SESSION
            )

        content = self._summarizer.build_context_injection(
            sessions=sessions,
            recent_observations=recent_obs,
            max_tokens=max_tokens_hint,
        )

        if not content:
            return ""

        return wrap_context_injection(content)

    def build_semantic_context(
        self,
        query: str,
        project_path: str,
        limit: int = _MAX_SEMANTIC_OBS,
    ) -> str:
        """
        Build semantically relevant context for a UserPromptSubmit hook.

        Searches ChromaDB for observations matching the user's prompt,
        and returns a concise context injection.
        """
        results = self._obs_store.search_semantic(
            query=query,
            limit=limit,
            project_path=project_path,
        )

        if not results:
            return ""

        lines = ["## Relevant Prior Observations\n"]
        for obs, score in results:
            if score < 0.3:
                continue  # Skip low-relevance results
            line = f"- [{obs.obs_type.value}] {obs.summary}"
            if obs.files:
                line += f" (files: {', '.join(obs.files[:3])})"
            lines.append(line)

        if len(lines) <= 1:
            return ""

        content = "\n".join(lines)
        return wrap_context_injection(content)

    def build_timeline(
        self,
        session_id: str,
    ) -> dict:
        """
        Build a structured timeline for a session (MCP tool response).

        Returns:
            {
                "session": {...},
                "observations": [...],
                "summary": "...",
            }
        """
        session = self._session_store.get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        observations = self._obs_store.list_for_session(session_id, limit=200)

        return {
            "session": session.to_dict(),
            "observations": [o.to_dict() for o in observations],
            "observation_count": len(observations),
            "summary": session.summary,
        }

    def get_recent_context_text(
        self,
        project_path: str,
        limit: int = 3,
    ) -> str:
        """
        Get a plain-text summary of recent work (for CLI display or debugging).
        """
        sessions = self._session_store.list_sessions(
            project_path=project_path,
            limit=limit,
        )

        if not sessions:
            return "No prior session history found."

        lines = []
        for s in sessions:
            lines.append(f"\n### Session {s.started_at[:19]} ({s.platform.value})")
            if s.summary:
                lines.append(s.summary)
            else:
                obs = self._obs_store.list_for_session(s.id, limit=5)
                if obs:
                    for o in obs:
                        lines.append(f"  - [{o.obs_type.value}] {o.summary}")
                else:
                    lines.append("  (no observations recorded)")

        return "\n".join(lines)
