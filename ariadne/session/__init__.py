"""
Ariadne Session Memory — cross-session observation capture and context injection.

Inspired by Claude-Mem's hook-based lifecycle architecture.
Adapted for Ariadne's Python ecosystem with multi-provider LLM support.

Key components:
- SessionManager  : High-level orchestrator (singleton via get_manager())
- SessionStore    : SQLite persistence (sessions + observations + queue)
- ObservationStore: ChromaDB-synced observation search
- SessionSummarizer: LLM-driven observation extraction and session summarization
- ContextBuilder  : Generates injected context for session start / user prompts
- SSEBroadcaster  : Real-time event streaming to Web UI
- DeduplicationCache: Content-hash deduplication (prevents duplicate observations)
- Platform adapters (ariadne/hooks/): Claude Code, OpenClaw, Cursor, Generic

Typical usage (MCP / Web API):
    from ariadne.session import get_manager

    mgr = get_manager()

    # Start a session (returns context to inject)
    session, context = mgr.start_session("/my/project", Platform.OPENCLAW)

    # Record a tool use
    mgr.record_observation(session.id, "write_file", {"path": "foo.py"}, "ok")

    # End and summarize
    summary = mgr.end_session(session.id)

    # Search across sessions
    results = mgr.search_observations("authentication bug", project_path="/my/project")

SSE Real-time Streaming:
    from ariadne.session import get_manager, SSEBroadcaster

    broadcaster = SSEBroadcaster()
    mgr = get_manager()
    mgr.set_sse_broadcaster(broadcaster)

    # Web UI connects to /api/sse endpoint
"""

from ariadne.session.models import (
    Observation,
    ObservationType,
    Platform,
    SessionRecord,
    SessionStatus,
    SessionSummary,
    NormalizedHookInput,
)
from ariadne.session.store import SessionStore, get_store
from ariadne.session.observation_store import ObservationStore
from ariadne.session.summarizer import SessionSummarizer
from ariadne.session.context_builder import ContextBuilder
from ariadne.session.manager import SessionManager, get_manager
from ariadne.session.privacy import strip_private_tags, wrap_context_injection
from ariadne.session.sse_broadcaster import SSEBroadcaster, get_broadcaster, SSEEvent, SSEEventType
from ariadne.session.deduplication import DeduplicationCache, get_dedup_cache, reset_dedup_cache

__all__ = [
    # Models
    "Observation",
    "ObservationType",
    "Platform",
    "SessionRecord",
    "SessionStatus",
    "SessionSummary",
    "NormalizedHookInput",
    # Storage
    "SessionStore",
    "get_store",
    "ObservationStore",
    # Processing
    "SessionSummarizer",
    "ContextBuilder",
    # Manager (main entry point)
    "SessionManager",
    "get_manager",
    # SSE real-time streaming
    "SSEBroadcaster",
    "get_broadcaster",
    "SSEEvent",
    "SSEEventType",
    # Deduplication
    "DeduplicationCache",
    "get_dedup_cache",
    "reset_dedup_cache",
    # Privacy
    "strip_private_tags",
    "wrap_context_injection",
]
