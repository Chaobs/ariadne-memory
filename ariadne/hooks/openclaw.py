"""
OpenClaw platform adapter.

OpenClaw sends hook events via the MCP protocol (ariadne_session_* tools)
rather than via stdin/hooks.  This adapter handles the case where OpenClaw
is configured to call ariadne CLI hooks directly (compatibility mode).

OpenClaw stdin format (compatible with Claude Code but with extra fields):
    {
      "session_id": "...",
      "cwd": "/path",
      "platform": "openclaw",
      "tool_name": "...",      # for post_tool
      "tool_input": {...},
      "tool_output": "...",
      "user_message": "...",   # for user_prompt
      "transcript": "..."      # for stop
    }
"""

from __future__ import annotations

from ariadne.hooks.base import BasePlatformAdapter
from ariadne.session.models import NormalizedHookInput, Platform


class OpenClawAdapter(BasePlatformAdapter):
    """Adapter for OpenClaw hook events."""

    @property
    def platform(self) -> Platform:
        return Platform.OPENCLAW

    def detect(self, raw: dict) -> bool:
        return raw.get("platform", "").lower() in ("openclaw", "claw", "workbuddy")

    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        inp = NormalizedHookInput(
            event=event,
            session_id=raw.get("session_id"),
            project_path=raw.get("cwd", raw.get("project_path", "")),
            platform=Platform.OPENCLAW,
            raw=raw,
        )

        if event == "post_tool":
            inp.tool_name = raw.get("tool_name", "")
            raw_input = raw.get("tool_input", {})
            inp.tool_input = raw_input if isinstance(raw_input, dict) else {}
            inp.tool_output = str(raw.get("tool_output", ""))

        elif event in ("user_prompt", "user_prompt_submit"):
            inp.user_message = raw.get("user_message", raw.get("prompt", ""))

        elif event in ("stop", "summary"):
            inp.transcript = raw.get("transcript", "")

        return inp
