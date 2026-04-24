"""
Hook Runner — the main entry point for the `ariadne hook` CLI command.

Reads JSON from stdin, selects the appropriate platform adapter,
dispatches to the event handler, and writes context output to stdout.

Exit codes (mirrors Claude-Mem's hook-constants.ts):
    0 — success or graceful no-op
    2 — blocking error (bug in our code)

Note: Non-availability of storage or LLM should exit 0 (graceful degradation),
never exit 2, to avoid blocking the AI's normal operation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Dict, List, Optional, Type

from ariadne.hooks.base import BasePlatformAdapter, HookResult
from ariadne.hooks.claude_code import ClaudeCodeAdapter
from ariadne.hooks.cursor import CursorAdapter, WindsurfAdapter
from ariadne.hooks.generic import GenericAdapter
from ariadne.hooks.openclaw import OpenClawAdapter
from ariadne.session.models import NormalizedHookInput, Platform
from ariadne.session.privacy import strip_private_tags

logger = logging.getLogger(__name__)

# All registered adapters (in priority order)
_ADAPTERS: List[BasePlatformAdapter] = [
    ClaudeCodeAdapter(),
    OpenClawAdapter(),
    CursorAdapter(),
    WindsurfAdapter(),
    GenericAdapter(),          # always last
]

# Platform name → adapter map
_PLATFORM_MAP: Dict[str, BasePlatformAdapter] = {
    "claude_code":  ClaudeCodeAdapter(),
    "claude-code":  ClaudeCodeAdapter(),
    "claude":       ClaudeCodeAdapter(),
    "openclaw":     OpenClawAdapter(),
    "claw":         OpenClawAdapter(),
    "workbuddy":    OpenClawAdapter(),
    "cursor":       CursorAdapter(),
    "windsurf":     WindsurfAdapter(),
    "generic":      GenericAdapter(),
}


def run_hook(
    event: str,
    platform: Optional[str] = None,
    stdin_data: Optional[str] = None,
    project_path: Optional[str] = None,
    use_llm: bool = True,
) -> HookResult:
    """
    Main hook dispatch function.

    Args:
        event:       One of: session_start, user_prompt, post_tool, stop, session_end
        platform:    Platform name override (auto-detect if None)
        stdin_data:  Raw stdin JSON string (reads from sys.stdin if None)
        project_path: Override project path (uses stdin cwd if None)
        use_llm:     Whether to use LLM for observation analysis

    Returns:
        HookResult with exit_code and optional context text.
    """
    # Read stdin
    try:
        if stdin_data is None:
            stdin_data = _read_stdin()
        raw = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON on stdin: {e}")
        raw = {}
    except Exception as e:
        logger.warning(f"Failed to read stdin: {e}")
        raw = {}

    # Select adapter
    adapter = _select_adapter(platform, raw)

    # Parse into normalized input
    try:
        hook_input = adapter.parse(raw, event)
        if project_path:
            hook_input.project_path = project_path
    except Exception as e:
        logger.error(f"Adapter parse error: {e}")
        return HookResult.noop()   # Graceful degradation

    # Dispatch to handler
    try:
        return _dispatch(hook_input, use_llm=use_llm)
    except Exception as e:
        logger.exception(f"Hook handler error (event={event}): {e}")
        return HookResult.noop()   # Never block the AI


def _read_stdin() -> str:
    """Read all data from stdin (handles platforms that don't close stdin)."""
    import select
    import time

    lines = []
    # On Windows, select() doesn't work on stdin reliably
    if sys.platform == "win32":
        try:
            import msvcrt
            timeout = 2.0
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if msvcrt.kbhit():
                    chunk = sys.stdin.buffer.read(4096)
                    if chunk:
                        lines.append(chunk.decode("utf-8", errors="replace"))
                    else:
                        break
                else:
                    import time
                    time.sleep(0.05)
        except Exception:
            # Fallback: just read
            try:
                return sys.stdin.read()
            except Exception:
                return "{}"
    else:
        try:
            r, _, _ = select.select([sys.stdin], [], [], 2.0)
            if r:
                return sys.stdin.read()
        except Exception:
            try:
                return sys.stdin.read()
            except Exception:
                return "{}"

    return "".join(lines) or "{}"


def _select_adapter(
    platform_name: Optional[str], raw: dict
) -> BasePlatformAdapter:
    """Select the best adapter for the given platform and raw input."""
    if platform_name:
        adapter = _PLATFORM_MAP.get(platform_name.lower())
        if adapter:
            return adapter

    # Auto-detect (excluding GenericAdapter)
    for adapter in _ADAPTERS[:-1]:
        if adapter.detect(raw):
            return adapter

    return GenericAdapter()


def _dispatch(hook_input: NormalizedHookInput, use_llm: bool = True) -> HookResult:
    """Route hook input to the appropriate handler."""
    event = hook_input.event

    try:
        from ariadne.session import get_manager, Platform
        mgr = get_manager()
    except Exception as e:
        logger.warning(f"SessionManager unavailable: {e}")
        return HookResult.noop()

    platform = hook_input.platform

    # ---- SessionStart ----
    if event in ("session_start",):
        project_path = hook_input.project_path or os.getcwd()
        session, context = mgr.start_session(
            project_path=project_path,
            platform=platform,
            session_id=hook_input.session_id,
        )
        return HookResult.ok(context=context)

    # ---- UserPromptSubmit ----
    elif event in ("user_prompt", "user_prompt_submit"):
        if not hook_input.user_message:
            return HookResult.noop()

        clean_msg = strip_private_tags(hook_input.user_message)
        context = mgr.get_semantic_context(
            query=clean_msg,
            project_path=hook_input.project_path or os.getcwd(),
        )
        return HookResult.ok(context=context)

    # ---- PostToolUse ----
    elif event in ("post_tool", "post_tool_use"):
        if not hook_input.tool_name:
            return HookResult.noop()
        if not hook_input.session_id:
            return HookResult.noop()

        mgr.record_observation(
            session_id=hook_input.session_id,
            tool_name=hook_input.tool_name,
            tool_input=hook_input.tool_input or {},
            tool_output=hook_input.tool_output or "",
            project_path=hook_input.project_path or "",
            use_llm=use_llm,
        )
        return HookResult.noop()   # PostToolUse returns nothing to inject

    # ---- Stop / Summary ----
    elif event in ("stop", "summary", "pre_compact"):
        if not hook_input.session_id:
            return HookResult.noop()
        mgr.end_session(hook_input.session_id, generate_summary=True)
        return HookResult.noop()

    # ---- SessionEnd ----
    elif event in ("session_end",):
        if hook_input.session_id:
            mgr.end_session(hook_input.session_id, generate_summary=False)
        return HookResult.noop()

    else:
        logger.debug(f"Unknown hook event: {event}")
        return HookResult.noop()


def main() -> int:
    """
    CLI entry point for `ariadne hook`.

    Usage:
        echo '{"session_id": "...", "cwd": "/path"}' | ariadne hook --event session_start
        echo '{"session_id": "...", "cwd": "/path", "tool_name": "...", ...}' | ariadne hook --event post_tool
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Ariadne session memory hook runner"
    )
    parser.add_argument(
        "--event", "-e",
        required=True,
        choices=["session_start", "user_prompt", "post_tool", "stop", "session_end"],
        help="Hook event type",
    )
    parser.add_argument(
        "--platform", "-p",
        default=None,
        help="Platform override (claude_code, openclaw, cursor, windsurf, generic)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-powered observation analysis",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    result = run_hook(
        event=args.event,
        platform=args.platform,
        use_llm=not args.no_llm,
    )

    if result.context:
        print(result.context, flush=True)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
