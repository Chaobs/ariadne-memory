"""
Session Memory MCP Tools — 7 new tools for cross-session memory via MCP protocol.

Tools implement the 3-layer progressive disclosure pattern from Claude-Mem:
  Layer 1 (low token):  ariadne_session_search   — summaries only
  Layer 2 (mid token):  ariadne_session_timeline — session timeline
  Layer 3 (full):       ariadne_session_get      — full observation details

Plus lifecycle tools:
  ariadne_session_start     — init session + inject context
  ariadne_session_observe   — record a tool use / observation
  ariadne_session_summarize — trigger LLM summarization
  ariadne_session_end       — finalize session

Usage:
    from ariadne.mcp.session_tools import register_session_tools
    register_session_tools(tool_handler)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ariadne.mcp.server import MCPTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: get (or lazy-init) the session manager
# ---------------------------------------------------------------------------


def _get_mgr():
    from ariadne.session import get_manager
    return get_manager()


def _platform_from_str(s: str):
    from ariadne.session.models import Platform
    try:
        return Platform(s.lower())
    except ValueError:
        return Platform.MCP


# ---------------------------------------------------------------------------
# Tool 1: ariadne_session_start
# ---------------------------------------------------------------------------


@dataclass
class SessionStartTool(MCPTool):
    """Initialize a session and get prior-work context for injection."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_start",
            description=(
                "Initialize a new Ariadne session and retrieve prior-work context. "
                "Call this at the start of each AI session. "
                "Returns a context block to inject into the system prompt."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to the current project/workspace",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform: claude_code, openclaw, cursor, windsurf, generic, mcp",
                        "default": "mcp",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional: reuse a specific session ID",
                    },
                },
                "required": ["project_path"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_path = arguments.get("project_path", "")
        platform_str = arguments.get("platform", "mcp")
        session_id = arguments.get("session_id")

        try:
            mgr = _get_mgr()
            platform = _platform_from_str(platform_str)
            session, context = mgr.start_session(
                project_path=project_path,
                platform=platform,
                session_id=session_id,
            )
            return {
                "session_id": session.id,
                "project_path": session.project_path,
                "platform": session.platform.value,
                "context": context,
                "has_prior_context": bool(context),
            }
        except Exception as e:
            logger.error(f"session_start error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 2: ariadne_session_observe
# ---------------------------------------------------------------------------


@dataclass
class SessionObserveTool(MCPTool):
    """Record a tool-use observation in the current session."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_observe",
            description=(
                "Record a tool-use event or manual observation in the current session. "
                "This is called automatically by PostToolUse hooks, but can also be "
                "called manually to record important decisions or discoveries."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID (from ariadne_session_start)",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool that was used",
                    },
                    "tool_input": {
                        "type": "object",
                        "description": "Input arguments passed to the tool",
                    },
                    "tool_output": {
                        "type": "string",
                        "description": "Output from the tool (first 2000 chars)",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Project path override",
                    },
                    "use_llm": {
                        "type": "boolean",
                        "description": "Use LLM to extract structured observation (default: true)",
                        "default": True,
                    },
                },
                "required": ["session_id", "tool_name"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_id = arguments.get("session_id", "")
        tool_name = arguments.get("tool_name", "")
        tool_input = arguments.get("tool_input") or {}
        tool_output = str(arguments.get("tool_output", ""))[:2000]
        project_path = arguments.get("project_path", "")
        use_llm = arguments.get("use_llm", True)

        if not session_id:
            return {"error": "session_id is required"}
        if not tool_name:
            return {"error": "tool_name is required"}

        try:
            mgr = _get_mgr()
            observations = mgr.record_observation(
                session_id=session_id,
                tool_name=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else {},
                tool_output=tool_output,
                project_path=project_path,
                use_llm=use_llm,
            )
            return {
                "session_id": session_id,
                "observations_created": len(observations),
                "observations": [
                    {"id": o.id, "type": o.obs_type.value, "summary": o.summary}
                    for o in observations
                ],
            }
        except Exception as e:
            logger.error(f"session_observe error: {e}")
            return {"error": str(e), "observations_created": 0}


# ---------------------------------------------------------------------------
# Tool 3: ariadne_session_add
# ---------------------------------------------------------------------------


@dataclass
class SessionAddObservationTool(MCPTool):
    """Manually add a structured observation to a session."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_add",
            description=(
                "Manually add a structured observation to the current session. "
                "Use this to record important decisions, discoveries, or architectural notes "
                "that weren't captured automatically from tool use."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID",
                    },
                    "type": {
                        "type": "string",
                        "description": "Observation type",
                        "enum": ["bugfix", "feature", "refactor", "change", "discovery", "decision", "security_alert", "general"],
                        "default": "general",
                    },
                    "summary": {
                        "type": "string",
                        "description": "One-line summary of the observation",
                    },
                    "detail": {
                        "type": "string",
                        "description": "Optional detailed notes",
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of affected files",
                    },
                    "concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key concepts or topics",
                    },
                },
                "required": ["session_id", "summary"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_id = arguments.get("session_id", "")
        obs_type = arguments.get("type", "general")
        summary = arguments.get("summary", "")
        detail = arguments.get("detail")
        files = arguments.get("files", [])
        concepts = arguments.get("concepts", [])

        if not session_id:
            return {"error": "session_id is required"}
        if not summary:
            return {"error": "summary is required"}

        try:
            mgr = _get_mgr()
            obs = mgr.add_observation_direct(
                session_id=session_id,
                obs_type=obs_type,
                summary=summary,
                detail=detail,
                files=files,
                concepts=concepts,
            )
            return {
                "id": obs.id,
                "session_id": obs.session_id,
                "type": obs.obs_type.value,
                "summary": obs.summary,
                "created_at": obs.created_at,
            }
        except Exception as e:
            logger.error(f"session_add error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 4: ariadne_session_summarize
# ---------------------------------------------------------------------------


@dataclass
class SessionSummarizeTool(MCPTool):
    """Generate an LLM summary for a session."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_summarize",
            description=(
                "Trigger LLM summarization of the current session. "
                "Called automatically by the Stop hook, but can also be triggered manually. "
                "Generates a narrative summary stored for future context injection."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to summarize",
                    },
                    "mark_complete": {
                        "type": "boolean",
                        "description": "Mark the session as completed after summarizing (default: true)",
                        "default": True,
                    },
                },
                "required": ["session_id"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_id = arguments.get("session_id", "")
        mark_complete = arguments.get("mark_complete", True)

        if not session_id:
            return {"error": "session_id is required"}

        try:
            mgr = _get_mgr()
            summary = mgr.end_session(
                session_id=session_id,
                generate_summary=True,
            )

            if summary:
                return {
                    "session_id": session_id,
                    "summarized": True,
                    "narrative": summary.narrative,
                    "key_decisions": summary.key_decisions,
                    "files_changed": summary.files_changed,
                    "concepts_covered": summary.concepts_covered,
                }
            else:
                return {
                    "session_id": session_id,
                    "summarized": False,
                    "message": "Session ended but no observations to summarize",
                }
        except Exception as e:
            logger.error(f"session_summarize error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 5: ariadne_session_end
# ---------------------------------------------------------------------------


@dataclass
class SessionEndTool(MCPTool):
    """End a session without generating a summary."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_end",
            description=(
                "End the current session. Use ariadne_session_summarize instead "
                "if you want to generate an LLM summary before ending."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to end",
                    },
                },
                "required": ["session_id"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_id = arguments.get("session_id", "")
        if not session_id:
            return {"error": "session_id is required"}

        try:
            mgr = _get_mgr()
            mgr.end_session(session_id, generate_summary=False)
            return {"session_id": session_id, "ended": True}
        except Exception as e:
            logger.error(f"session_end error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 6: ariadne_session_search  (Progressive Disclosure Layer 1)
# ---------------------------------------------------------------------------


@dataclass
class SessionSearchTool(MCPTool):
    """Search session observations (progressive disclosure Layer 1)."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_search",
            description=(
                "Search session memory for relevant observations. "
                "Returns summaries only (low token cost). "
                "Use ariadne_session_timeline to expand a specific session, "
                "or ariadne_session_get to fetch full observation details."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Filter by project path",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "")
        project_path = arguments.get("project_path")
        limit = min(arguments.get("limit", 10), 50)

        if not query:
            return {"error": "query is required"}

        try:
            mgr = _get_mgr()
            results = mgr.search_observations(
                query=query,
                project_path=project_path,
                limit=limit,
            )

            return {
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "id": obs.id,
                        "session_id": obs.session_id,
                        "type": obs.obs_type.value,
                        "summary": obs.summary,           # Short summary only
                        "created_at": obs.created_at[:19],
                        "score": round(score, 3),
                        # Hint: use ariadne_session_timeline(session_id) or
                        #       ariadne_session_get([id]) for full details
                    }
                    for obs, score in results
                ],
                "hint": "Use ariadne_session_timeline(session_id) or ariadne_session_get([ids]) for details",
            }
        except Exception as e:
            logger.error(f"session_search error: {e}")
            return {"error": str(e), "results": []}


# ---------------------------------------------------------------------------
# Tool 7: ariadne_session_timeline  (Progressive Disclosure Layer 2)
# ---------------------------------------------------------------------------


@dataclass
class SessionTimelineTool(MCPTool):
    """Get full timeline for a session (progressive disclosure Layer 2)."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_timeline",
            description=(
                "Get the full timeline of observations for a specific session. "
                "Returns all observations with summaries (mid token cost). "
                "Use after ariadne_session_search to expand a specific session."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to get timeline for",
                    },
                },
                "required": ["session_id"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_id = arguments.get("session_id", "")
        if not session_id:
            return {"error": "session_id is required"}

        try:
            mgr = _get_mgr()
            timeline = mgr.get_timeline(session_id)
            if "error" in timeline:
                return timeline

            # Return summaries only (not full detail) — user can call ariadne_session_get for details
            observations = timeline.get("observations", [])
            return {
                "session_id": session_id,
                "session": {
                    k: v for k, v in timeline["session"].items()
                    if k in ("id", "project_path", "platform", "started_at", "ended_at", "status", "summary")
                },
                "observation_count": len(observations),
                "observations": [
                    {
                        "id": o["id"],
                        "type": o["obs_type"],
                        "summary": o["summary"],
                        "files": o.get("files", [])[:5],
                        "concepts": o.get("concepts", [])[:5],
                        "created_at": o["created_at"][:19],
                    }
                    for o in observations
                ],
                "hint": "Use ariadne_session_get([ids]) for full observation details",
            }
        except Exception as e:
            logger.error(f"session_timeline error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 8: ariadne_session_get  (Progressive Disclosure Layer 3)
# ---------------------------------------------------------------------------


@dataclass
class SessionGetTool(MCPTool):
    """Get full details for specific observations (progressive disclosure Layer 3)."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_get",
            description=(
                "Retrieve full details for specific observations by ID. "
                "This is the highest-token call — use only when full details are needed. "
                "Get IDs from ariadne_session_search or ariadne_session_timeline first."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of observation IDs to retrieve (max 20)",
                    },
                },
                "required": ["ids"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        ids = arguments.get("ids", [])
        if not ids:
            return {"error": "ids is required"}
        if len(ids) > 20:
            ids = ids[:20]

        try:
            mgr = _get_mgr()
            observations = mgr.get_observations(ids)

            return {
                "count": len(observations),
                "observations": [o.to_dict() for o in observations],
            }
        except Exception as e:
            logger.error(f"session_get error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 9: ariadne_session_list
# ---------------------------------------------------------------------------


@dataclass
class SessionListTool(MCPTool):
    """List recent sessions for a project."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_list",
            description="List recent sessions for a project with their summaries.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Filter by project path",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum sessions to return (default: 20)",
                        "default": 20,
                    },
                },
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_path = arguments.get("project_path")
        limit = min(arguments.get("limit", 20), 100)

        try:
            mgr = _get_mgr()
            sessions = mgr.list_sessions(project_path=project_path, limit=limit)
            return {
                "count": len(sessions),
                "sessions": [
                    {
                        "id": s.id,
                        "project_path": s.project_path,
                        "platform": s.platform.value,
                        "started_at": s.started_at[:19],
                        "ended_at": s.ended_at[:19] if s.ended_at else None,
                        "status": s.status.value,
                        "summary": (s.summary[:200] if s.summary else None),
                    }
                    for s in sessions
                ],
            }
        except Exception as e:
            logger.error(f"session_list error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 10: ariadne_session_context
# ---------------------------------------------------------------------------


@dataclass
class SessionContextTool(MCPTool):
    """Get semantic context for a user query from session memory."""

    def __init__(self):
        super().__init__(
            name="ariadne_session_context",
            description=(
                "Get semantically relevant session memory context for a user query. "
                "Returns a concise context block to inject alongside the user's message."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's current query/message",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Current project path",
                    },
                },
                "required": ["query", "project_path"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "")
        project_path = arguments.get("project_path", "")

        if not query:
            return {"error": "query is required"}

        try:
            mgr = _get_mgr()
            context = mgr.get_semantic_context(
                query=query,
                project_path=project_path,
            )
            return {
                "query": query,
                "context": context,
                "has_context": bool(context),
            }
        except Exception as e:
            logger.error(f"session_context error: {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_session_tools(tool_handler) -> None:
    """
    Register all session memory tools into an AriadneToolHandler.

    Args:
        tool_handler: AriadneToolHandler instance from ariadne/mcp/tools.py
    """
    session_tools = [
        SessionStartTool(),
        SessionObserveTool(),
        SessionAddObservationTool(),
        SessionSummarizeTool(),
        SessionEndTool(),
        SessionSearchTool(),
        SessionTimelineTool(),
        SessionGetTool(),
        SessionListTool(),
        SessionContextTool(),
    ]

    for tool in session_tools:
        tool_handler.register(tool.name, tool)

    logger.info(f"Registered {len(session_tools)} session memory tools")
