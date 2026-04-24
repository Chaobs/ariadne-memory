"""
Ariadne Hooks — platform adapters for cross-session memory lifecycle hooks.

Supported platforms:
- Claude Code  (SessionStart / UserPromptSubmit / PostToolUse / Stop hooks)
- OpenClaw     (same protocol, with platform="openclaw" field)
- Cursor       (camelCase JSON variant)
- Windsurf     (same as Claude Code)
- Generic      (flexible fallback)

Usage (in shell / CI):
    echo '{"session_id": "abc", "cwd": "/my/project"}' | \\
        ariadne hook --event session_start --platform claude_code

Hook configuration for Claude Code (~/.claude/settings.json):
    {
      "hooks": {
        "SessionStart":     [{"hooks": [{"type": "command", "command": "ariadne hook --event session_start"}]}],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "ariadne hook --event user_prompt"}]}],
        "PostToolUse":      [{"hooks": [{"type": "command", "command": "ariadne hook --event post_tool"}]}],
        "Stop":             [{"hooks": [{"type": "command", "command": "ariadne hook --event stop"}]}]
      }
    }
"""

from ariadne.hooks.base import BasePlatformAdapter, HookResult
from ariadne.hooks.claude_code import ClaudeCodeAdapter
from ariadne.hooks.cursor import CursorAdapter, WindsurfAdapter
from ariadne.hooks.generic import GenericAdapter
from ariadne.hooks.openclaw import OpenClawAdapter
from ariadne.hooks.runner import run_hook

__all__ = [
    "BasePlatformAdapter",
    "HookResult",
    "ClaudeCodeAdapter",
    "OpenClawAdapter",
    "CursorAdapter",
    "WindsurfAdapter",
    "GenericAdapter",
    "run_hook",
]
