"""
Claude Code platform adapter.

Claude Code sends hook events via stdin as JSON with these shapes:

SessionStart:
    {"session_id": "...", "cwd": "/path"}

UserPromptSubmit:
    {"session_id": "...", "cwd": "/path", "prompt": "..."}

PostToolUse:
    {
      "session_id": "...",
      "cwd": "/path",
      "tool_name": "...",
      "tool_input": {...},
      "tool_response": {"output": "..."}  OR  "..."
    }

Stop:
    {"session_id": "...", "cwd": "/path", "stop_hook_active": true}

PreCompact / Summary:
    {"session_id": "...", "cwd": "/path", "transcript": "..."}
"""

from __future__ import annotations

from ariadne.hooks.base import BasePlatformAdapter
from ariadne.session.models import NormalizedHookInput, Platform


class ClaudeCodeAdapter(BasePlatformAdapter):
    """Adapter for Claude Code hook events."""

    @property
    def platform(self) -> Platform:
        return Platform.CLAUDE_CODE

    def detect(self, raw: dict) -> bool:
        # Claude Code always sends session_id and cwd
        return "session_id" in raw and "cwd" in raw

    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        inp = NormalizedHookInput(
            event=event,
            session_id=raw.get("session_id"),
            project_path=raw.get("cwd", ""),
            platform=Platform.CLAUDE_CODE,
            raw=raw,
        )

        if event == "post_tool":
            inp.tool_name = raw.get("tool_name", "")
            raw_input = raw.get("tool_input", {})
            inp.tool_input = raw_input if isinstance(raw_input, dict) else {}

            # tool_response can be a dict with "output" key or a plain string
            tool_response = raw.get("tool_response", "")
            if isinstance(tool_response, dict):
                inp.tool_output = tool_response.get("output", "")
            else:
                inp.tool_output = str(tool_response)

        elif event in ("user_prompt", "user_prompt_submit"):
            inp.user_message = raw.get("prompt", "")

        elif event in ("stop", "summary", "pre_compact"):
            inp.transcript = raw.get("transcript", "")

        return inp
