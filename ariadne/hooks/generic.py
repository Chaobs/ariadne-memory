"""
Generic platform adapter — fallback for unknown platforms.

Accepts any JSON with common field patterns.  Used when --platform is
not specified and auto-detection fails.
"""

from __future__ import annotations

from ariadne.hooks.base import BasePlatformAdapter
from ariadne.session.models import NormalizedHookInput, Platform


class GenericAdapter(BasePlatformAdapter):
    """
    Flexible adapter that tries to extract data from any JSON shape.

    Field aliases supported:
        session_id / sessionId / id
        cwd / workspaceFolder / project_path / path
        tool_name / toolName / tool
        tool_input / toolInput / input
        tool_output / toolOutput / output / response / tool_response
        prompt / user_message / userMessage / message
        transcript / summary
    """

    @property
    def platform(self) -> Platform:
        return Platform.GENERIC

    def detect(self, raw: dict) -> bool:
        return True  # Always matches as the last resort

    def parse(self, raw: dict, event: str) -> NormalizedHookInput:
        def get(*keys, default=""):
            for k in keys:
                if raw.get(k) is not None:
                    return raw[k]
            return default

        inp = NormalizedHookInput(
            event=event,
            session_id=get("session_id", "sessionId", "id"),
            project_path=get("cwd", "workspaceFolder", "project_path", "path"),
            platform=Platform.GENERIC,
            raw=raw,
        )

        if event == "post_tool":
            inp.tool_name = get("tool_name", "toolName", "tool")
            raw_input = get("tool_input", "toolInput", "input")
            inp.tool_input = raw_input if isinstance(raw_input, dict) else {}
            raw_output = get("tool_output", "toolOutput", "output", "response", "tool_response")
            if isinstance(raw_output, dict):
                inp.tool_output = raw_output.get("output") or str(raw_output)
            else:
                inp.tool_output = str(raw_output)

        elif event in ("user_prompt", "user_prompt_submit"):
            inp.user_message = get("prompt", "user_message", "userMessage", "message")

        elif event in ("stop", "summary", "session_end"):
            inp.transcript = get("transcript", "summary", "content")

        return inp
