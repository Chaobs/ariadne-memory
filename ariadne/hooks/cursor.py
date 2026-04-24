"""
Cursor platform adapter.

Cursor uses a similar hook structure to Claude Code but with slightly
different field names.

Cursor stdin format:
    {
      "sessionId": "...",          # camelCase
      "workspaceFolder": "/path",  # instead of "cwd"
      "toolName": "...",
      "toolInput": {...},
      "toolOutput": "...",
      "userMessage": "..."
    }
"""

from __future__ import annotations

from ariadne.hooks.base import BasePlatformAdapter
from ariadne.session.models import NormalizedHookInput, Platform


class CursorAdapter(BasePlatformAdapter):
    """Adapter for Cursor hook events."""

    @property
    def platform(self) -> Platform:
        return Platform.CURSOR

    def detect(self, raw: dict) -> bool:
        # Cursor uses camelCase keys
        return "sessionId" in raw or "workspaceFolder" in raw

    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        # Support both camelCase (Cursor) and snake_case (Claude Code)
        def get(camel: str, snake: str, default=""):
            return raw.get(camel) or raw.get(snake) or default

        inp = NormalizedHookInput(
            event=event,
            session_id=get("sessionId", "session_id"),
            project_path=get("workspaceFolder", "cwd"),
            platform=Platform.CURSOR,
            raw=raw,
        )

        if event == "post_tool":
            inp.tool_name = get("toolName", "tool_name")
            raw_input = raw.get("toolInput") or raw.get("tool_input") or {}
            inp.tool_input = raw_input if isinstance(raw_input, dict) else {}
            inp.tool_output = str(get("toolOutput", "tool_output"))

        elif event in ("user_prompt", "user_prompt_submit"):
            inp.user_message = get("userMessage", "user_message")

        elif event in ("stop", "summary"):
            inp.transcript = get("transcript", "transcript")

        return inp


class WindsurfAdapter(BasePlatformAdapter):
    """Adapter for Windsurf hook events (same structure as Cursor)."""

    @property
    def platform(self) -> Platform:
        return Platform.WINDSURF

    def detect(self, raw: dict) -> bool:
        return raw.get("platform", "").lower() == "windsurf"

    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        # Windsurf uses the same format as Claude Code
        inp = NormalizedHookInput(
            event=event,
            session_id=raw.get("session_id"),
            project_path=raw.get("cwd", ""),
            platform=Platform.WINDSURF,
            raw=raw,
        )
        if event == "post_tool":
            inp.tool_name = raw.get("tool_name", "")
            inp.tool_input = raw.get("tool_input") or {}
            inp.tool_output = str(raw.get("tool_response", ""))
        elif event in ("user_prompt", "user_prompt_submit"):
            inp.user_message = raw.get("prompt", "")
        return inp
