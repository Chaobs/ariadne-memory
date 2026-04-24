"""
Hook base types and platform adapter interface.

Mirrors Claude-Mem's src/cli/types.ts — defines the contract that all
platform adapters must fulfill, and the HookResult return type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ariadne.session.models import NormalizedHookInput, Platform


@dataclass
class HookResult:
    """
    Result returned by a hook handler.

    exit_code:
        0  — success (or graceful no-op)
        2  — blocking error (e.g. a bug, not just worker unavailability)

    context:
        If set, this text is printed to stdout and will be injected into
        the AI's context (for SessionStart / UserPromptSubmit events).

    suppress_output:
        If True, do not print context to stdout (used when caller handles
        context injection separately via MCP).
    """
    exit_code: int = 0
    context: str = ""
    message: str = ""
    suppress_output: bool = False

    @classmethod
    def ok(cls, context: str = "", message: str = "") -> "HookResult":
        return cls(exit_code=0, context=context, message=message)

    @classmethod
    def noop(cls) -> "HookResult":
        return cls(exit_code=0)

    @classmethod
    def error(cls, message: str) -> "HookResult":
        return cls(exit_code=2, message=message)


class BasePlatformAdapter(ABC):
    """
    Abstract base for platform-specific stdin → NormalizedHookInput parsers.

    Each platform (Claude Code, Cursor, OpenClaw, etc.) sends a different
    JSON structure via stdin.  The adapter normalizes it.
    """

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Which platform this adapter handles."""
        ...

    @abstractmethod
    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        """
        Parse raw stdin JSON into a NormalizedHookInput.

        Args:
            raw:   Decoded JSON dict from stdin.
            event: The --event flag value (session_start, user_prompt,
                   post_tool, stop, session_end).

        Returns:
            NormalizedHookInput ready for the event handler.
        """
        ...

    def detect(self, raw: dict) -> bool:
        """
        Optional auto-detection: return True if this adapter matches the raw input.

        Used when --platform is not explicitly specified.
        """
        return False
