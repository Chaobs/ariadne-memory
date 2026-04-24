"""
Session Memory Models — data structures for cross-session observation capture.

Inspired by Claude-Mem's observation pipeline architecture.
Adapted for Ariadne's Python ecosystem and multi-provider LLM support.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ObservationType(str, Enum):
    """Categories of observations, mirroring Claude-Mem's mode profiles."""
    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    CHANGE = "change"
    DISCOVERY = "discovery"
    DECISION = "decision"
    SECURITY_ALERT = "security_alert"
    SECURITY_NOTE = "security_note"
    GENERAL = "general"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUMMARIZED = "summarized"
    ABANDONED = "abandoned"


class Platform(str, Enum):
    CLAUDE_CODE = "claude_code"
    OPENCLAW = "openclaw"
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    GEMINI_CLI = "gemini_cli"
    GENERIC = "generic"
    MCP = "mcp"


class MessageStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PROCESSED = "processed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Core Data Classes
# ---------------------------------------------------------------------------


@dataclass
class SessionRecord:
    """A coding / conversation session."""
    id: str
    project_path: str
    platform: Platform
    started_at: str
    ended_at: Optional[str] = None
    summary: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: dict = field(default_factory=dict)

    @classmethod
    def new(cls, project_path: str, platform: Platform = Platform.GENERIC) -> "SessionRecord":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=str(uuid.uuid4()),
            project_path=project_path,
            platform=platform,
            started_at=now,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "platform": self.platform.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": self.summary,
            "status": self.status.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        return cls(
            id=d["id"],
            project_path=d["project_path"],
            platform=Platform(d.get("platform", "generic")),
            started_at=d["started_at"],
            ended_at=d.get("ended_at"),
            summary=d.get("summary"),
            status=SessionStatus(d.get("status", "active")),
            metadata=d.get("metadata", {}),
        )


@dataclass
class Observation:
    """
    A structured observation extracted from a tool-use event or LLM analysis.

    Corresponds to Claude-Mem's <observation> XML block, stored in SQLite
    and synced to ChromaDB for semantic search.
    """
    id: str
    session_id: str
    obs_type: ObservationType
    summary: str
    detail: Optional[str] = None
    files: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    chroma_synced: bool = False

    @classmethod
    def new(
        cls,
        session_id: str,
        obs_type: ObservationType,
        summary: str,
        detail: Optional[str] = None,
        files: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_output: Optional[str] = None,
    ) -> "Observation":
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            obs_type=obs_type,
            summary=summary,
            detail=detail,
            files=files or [],
            concepts=concepts or [],
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "obs_type": self.obs_type.value,
            "summary": self.summary,
            "detail": self.detail,
            "files": self.files,
            "concepts": self.concepts,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "created_at": self.created_at,
            "chroma_synced": self.chroma_synced,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        return cls(
            id=d["id"],
            session_id=d["session_id"],
            obs_type=ObservationType(d.get("obs_type", "general")),
            summary=d["summary"],
            detail=d.get("detail"),
            files=json.loads(d["files"]) if isinstance(d.get("files"), str) else (d.get("files") or []),
            concepts=json.loads(d["concepts"]) if isinstance(d.get("concepts"), str) else (d.get("concepts") or []),
            tool_name=d.get("tool_name"),
            tool_input=json.loads(d["tool_input"]) if isinstance(d.get("tool_input"), str) else d.get("tool_input"),
            tool_output=d.get("tool_output"),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            chroma_synced=bool(d.get("chroma_synced", False)),
        )

    def to_text(self) -> str:
        """Serialize to plain text for ChromaDB / LLM context."""
        parts = [
            f"[{self.obs_type.value.upper()}] {self.summary}",
        ]
        if self.detail:
            parts.append(self.detail)
        if self.files:
            parts.append("Files: " + ", ".join(self.files))
        if self.concepts:
            parts.append("Concepts: " + ", ".join(self.concepts))
        if self.tool_name:
            parts.append(f"Tool: {self.tool_name}")
        return "\n".join(parts)


@dataclass
class SessionSummary:
    """
    LLM-generated summary of a completed session.
    Stored in the sessions table and also as an Observation for searchability.
    """
    session_id: str
    narrative: str          # Multi-sentence narrative (L1 layer ~500 tokens)
    key_decisions: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    concepts_covered: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_text(self) -> str:
        parts = [f"Session Summary:\n{self.narrative}"]
        if self.key_decisions:
            parts.append("Key Decisions:\n" + "\n".join(f"- {d}" for d in self.key_decisions))
        if self.files_changed:
            parts.append("Files Changed: " + ", ".join(self.files_changed))
        if self.concepts_covered:
            parts.append("Concepts: " + ", ".join(self.concepts_covered))
        return "\n\n".join(parts)


@dataclass
class PendingMessage:
    """Queue entry for async observation processing (CLAIM-CONFIRM pattern)."""
    id: str
    session_id: str
    payload: dict
    status: MessageStatus = MessageStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    claimed_at: Optional[str] = None
    processed_at: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def new(cls, session_id: str, payload: dict) -> "PendingMessage":
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            payload=payload,
        )


@dataclass
class NormalizedHookInput:
    """
    Platform-agnostic hook input, after adapter normalization.
    Equivalent to Claude-Mem's NormalizedHookInput interface.
    """
    event: str                          # session_start / user_prompt / post_tool / stop
    session_id: Optional[str] = None
    project_path: Optional[str] = None
    platform: Platform = Platform.GENERIC
    # For post_tool
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    # For user_prompt
    user_message: Optional[str] = None
    # For stop
    transcript: Optional[str] = None
    # Raw platform data
    raw: dict = field(default_factory=dict)
