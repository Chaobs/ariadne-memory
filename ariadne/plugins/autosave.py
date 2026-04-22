"""
Ariadne Auto-Save Hook System - MemPalace-inspired automatic memory persistence.

Provides automatic memory saving through hooks:
- StopHook: Saves after N messages
- PreCompactHook: Saves before context compression
- Claude Code integration
- Automatic wake-up on session start

Inspired by MemPalace's Hook system.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ariadne.memory.layers import MemoryStack

logger = logging.getLogger(__name__)


class HookType(str, Enum):
    """Types of auto-save hooks."""
    STOP = "stop"                    # Triggered after N messages
    PRE_COMPACT = "pre_compact"     # Triggered before context compression
    SESSION_START = "session_start"  # Triggered on session start
    SESSION_END = "session_end"     # Triggered on session end
    IDLE = "idle"                   # Triggered after idle period
    MANUAL = "manual"               # Manually triggered


@dataclass
class HookConfig:
    """Configuration for auto-save hooks."""
    # Stop hook settings
    stop_message_interval: int = 15  # Save after every N messages

    # Pre-compact hook settings
    pre_compact_enabled: bool = True

    # Session hook settings
    save_on_start: bool = True
    save_on_end: bool = True

    # Idle hook settings
    idle_timeout_seconds: float = 300  # 5 minutes
    idle_check_interval: float = 60    # Check every minute

    # General settings
    auto_backup: bool = True
    backup_count: int = 3
    persist_path: Optional[str] = None


@dataclass
class HookEvent:
    """Event passed to hook handlers."""
    hook_type: HookType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_count: int = 0
    context_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutoSaveHook:
    """
    Auto-save hook for automatic memory persistence.

    Provides various hook types for different save scenarios.

    Usage:
        hook = AutoSaveHook(memory_stack=stack, config=HookConfig())
        hook.start()

        # Manually trigger save
        hook.trigger(HookType.MANUAL)

        # Stop hooks
        hook.stop()
    """

    def __init__(
        self,
        memory_stack: "MemoryStack",
        config: Optional[HookConfig] = None,
    ):
        """
        Initialize auto-save hook.

        Args:
            memory_stack: The MemoryStack to save
            config: Hook configuration
        """
        self.memory_stack = memory_stack
        self.config = config or HookConfig()

        self._message_count = 0
        self._last_save_time: Optional[float] = None
        self._running = False
        self._hooks: Dict[HookType, List[Callable]] = {
            hook_type: [] for hook_type in HookType
        }
        self._lock = threading.RLock()

        # Background thread for idle detection
        self._idle_thread: Optional[threading.Thread] = None

    def register_hook(
        self,
        hook_type: HookType,
        handler: Callable[[HookEvent], None],
    ) -> None:
        """
        Register a hook handler.

        Args:
            hook_type: Type of hook to register for
            handler: Function to call when hook triggers
        """
        with self._lock:
            self._hooks[hook_type].append(handler)
        logger.info(f"Registered hook handler for {hook_type.value}")

    def unregister_hook(
        self,
        hook_type: HookType,
        handler: Callable[[HookEvent], None],
    ) -> None:
        """Unregister a hook handler."""
        with self._lock:
            if handler in self._hooks[hook_type]:
                self._hooks[hook_type].remove(handler)

    def on_message(self) -> None:
        """
        Call this after each message to track for stop hook.

        Increments message counter and triggers save if threshold reached.
        """
        with self._lock:
            self._message_count += 1

            if self._message_count >= self.config.stop_message_interval:
                self._message_count = 0
                self._trigger_hook(HookType.STOP)

    def trigger(self, hook_type: HookType, **metadata: Any) -> None:
        """
        Manually trigger a hook.

        Args:
            hook_type: Type of hook to trigger
            **metadata: Additional metadata for the event
        """
        self._trigger_hook(hook_type, metadata=metadata)

    def _trigger_hook(
        self,
        hook_type: HookType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal method to trigger a hook."""
        event = HookEvent(
            hook_type=hook_type,
            message_count=self._message_count,
            context_size=self._estimate_context_size(),
            metadata=metadata or {},
        )

        # Fire registered handlers
        with self._lock:
            handlers = list(self._hooks.get(hook_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Hook handler error ({hook_type.value}): {e}")

        # Perform default action based on hook type
        if hook_type == HookType.STOP:
            self._do_save("stop_hook")
        elif hook_type == HookType.PRE_COMPACT:
            self._do_save("pre_compact_hook")
        elif hook_type == HookType.SESSION_END:
            self._do_save("session_end_hook")
        elif hook_type == HookType.IDLE:
            self._do_save("idle_hook")
        elif hook_type == HookType.MANUAL:
            self._do_save("manual_trigger")

    def _estimate_context_size(self) -> int:
        """Estimate current context size in tokens."""
        try:
            context = self.memory_stack.generate_context(max_tokens=10000)
            return len(context) // 4
        except Exception:
            return 0

    def _do_save(self, reason: str) -> None:
        """Perform the actual save operation."""
        if not self.memory_stack:
            logger.warning("No memory stack to save")
            return

        save_path = self.config.persist_path or str(
            Path.cwd() / ".ariadne" / "memory_stack.json"
        )

        try:
            # Create backup if enabled
            if self.config.auto_backup:
                self._create_backup(save_path)

            # Save memory stack
            self.memory_stack.save(save_path)
            self._last_save_time = time.time()

            logger.info(f"Memory saved ({reason}) to {save_path}")

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def _create_backup(self, path: str) -> None:
        """Create a backup of the existing save file."""
        save_path = Path(path)
        if not save_path.exists():
            return

        backup_dir = save_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{save_path.stem}_{timestamp}{save_path.suffix}"

        try:
            import shutil
            shutil.copy2(save_path, backup_path)

            # Clean old backups
            self._clean_old_backups(backup_dir, save_path.stem, save_path.suffix)

        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def _clean_old_backups(
        self,
        backup_dir: Path,
        stem: str,
        suffix: str,
    ) -> None:
        """Remove old backups, keeping only the configured count."""
        try:
            backups = sorted(
                backup_dir.glob(f"{stem}_*{suffix}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for old_backup in backups[self.config.backup_count:]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")

        except Exception as e:
            logger.warning(f"Failed to clean old backups: {e}")

    def start(self) -> None:
        """Start the auto-save hook system."""
        self._running = True

        # Fire session start hook
        if self.config.save_on_start:
            self._trigger_hook(HookType.SESSION_START)

        # Start idle detection thread
        if self.config.idle_timeout_seconds > 0:
            self._idle_thread = threading.Thread(
                target=self._idle_detection_loop,
                daemon=True,
            )
            self._idle_thread.start()

        logger.info("Auto-save hook system started")

    def stop(self) -> None:
        """Stop the auto-save hook system."""
        self._running = False

        # Fire session end hook
        if self.config.save_on_end:
            self._trigger_hook(HookType.SESSION_END)

        # Wait for idle thread to finish
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=5)

        logger.info("Auto-save hook system stopped")

    def _idle_detection_loop(self) -> None:
        """Background loop for idle detection."""
        while self._running:
            time.sleep(self.config.idle_check_interval)

            if not self._running:
                break

            # Check if idle timeout reached
            if self._last_save_time:
                idle_time = time.time() - self._last_save_time
                if idle_time >= self.config.idle_timeout_seconds:
                    logger.debug("Idle timeout reached, triggering save")
                    self._trigger_hook(HookType.IDLE)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the hook system."""
        return {
            "running": self._running,
            "message_count": self._message_count,
            "last_save_time": self._last_save_time,
            "idle_seconds": (
                time.time() - self._last_save_time
                if self._last_save_time else None
            ),
            "hooks_registered": {
                hook_type.value: len(handlers)
                for hook_type, handlers in self._hooks.items()
            },
        }


class ClaudeCodeHook:
    """
    Hook system for Claude Code integration.

    Provides hooks specific to Claude Code Claude Code:
    - Tool usage tracking
    - File modification detection
    - Project context awareness

    Inspired by MemPalace's Claude Code integration.
    """

    def __init__(self, memory_stack: "MemoryStack"):
        """
        Initialize Claude Code hook.

        Args:
            memory_stack: The MemoryStack to update
        """
        self.memory_stack = memory_stack
        self._tool_usage_count: Dict[str, int] = {}
        self._files_modified: Set[str] = set()

    def on_tool_use(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """
        Track tool usage for memory.

        Args:
            tool_name: Name of the tool used
            tool_args: Arguments passed to the tool
        """
        self._tool_usage_count[tool_name] = self._tool_usage_count.get(tool_name, 0) + 1

        # Update memory with tool context
        narrative = self.memory_stack.narrative
        if narrative:
            narrative.add_narrative(
                content=f"Used tool: {tool_name}",
                source="claude_code",
                importance=0.3,
                tags=["tool", tool_name],
            )

    def on_file_modified(
        self,
        file_path: str,
        operation: str,  # "create", "modify", "delete"
    ) -> None:
        """
        Track file modifications.

        Args:
            file_path: Path to the modified file
            operation: Type of modification
        """
        self._files_modified.add(file_path)

        # Add to on-demand context
        on_demand = self.memory_stack.on_demand
        if on_demand:
            on_demand.add_context(
                content=f"File {operation}: {file_path}",
                source="claude_code",
                importance=0.6,
                tags=["file", operation],
            )

    def on_error(self, error: str, context: Optional[str] = None) -> None:
        """
        Record an error for later reference.

        Args:
            error: Error message
            context: Additional context
        """
        narrative = self.memory_stack.narrative
        if narrative:
            content = f"Error encountered: {error}"
            if context:
                content += f"\nContext: {context}"

            narrative.add_narrative(
                content=content,
                source="claude_code",
                importance=0.8,
                tags=["error"],
            )

    def on_project_context(
        self,
        project_name: str,
        project_type: str,
        key_files: Optional[List[str]] = None,
    ) -> None:
        """
        Record project context.

        Args:
            project_name: Name of the project
            project_type: Type of project (python, js, etc.)
            key_files: List of important files
        """
        # Set identity
        identity = self.memory_stack.identity
        if identity:
            identity.set_identity("current_project", project_name)
            identity.set_identity("project_type", project_type)

        # Add key files to on-demand context
        if key_files:
            on_demand = self.memory_stack.on_demand
            if on_demand:
                for file_path in key_files:
                    on_demand.add_context(
                        content=f"Key file: {file_path}",
                        source="claude_code",
                        importance=0.7,
                        tags=["project", "key_file"],
                    )

    def get_tool_usage_summary(self) -> Dict[str, int]:
        """Get summary of tool usage."""
        return dict(self._tool_usage_count)

    def get_modified_files(self) -> List[str]:
        """Get list of modified files."""
        return list(self._files_modified)


class HookManager:
    """
    Central hook manager for all Ariadne hooks.

    Coordinates between different hook systems:
    - Auto-save hooks
    - Claude Code hooks
    - Custom hooks
    """

    def __init__(
        self,
        memory_stack: "MemoryStack",
        auto_save_config: Optional[HookConfig] = None,
    ):
        """
        Initialize hook manager.

        Args:
            memory_stack: The MemoryStack to manage
            auto_save_config: Configuration for auto-save hooks
        """
        self.memory_stack = memory_stack
        self.auto_save: Optional[AutoSaveHook] = None
        self.claude_code: Optional[ClaudeCodeHook] = None

        # Initialize auto-save if config provided
        if auto_save_config:
            self.auto_save = AutoSaveHook(
                memory_stack=memory_stack,
                config=auto_save_config,
            )

        # Initialize Claude Code hook
        self.claude_code = ClaudeCodeHook(memory_stack=memory_stack)

    def start(self) -> None:
        """Start all hook systems."""
        if self.auto_save:
            self.auto_save.start()
        logger.info("Hook manager started")

    def stop(self) -> None:
        """Stop all hook systems."""
        if self.auto_save:
            self.auto_save.stop()
        logger.info("Hook manager stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all hook systems."""
        return {
            "auto_save": self.auto_save.get_status() if self.auto_save else None,
            "claude_code": {
                "tool_usage": self.claude_code.get_tool_usage_summary(),
                "modified_files_count": len(self.claude_code.get_modified_files()),
            } if self.claude_code else None,
        }


def create_default_hook_manager(
    memory_stack: "MemoryStack",
    persist_path: Optional[str] = None,
) -> HookManager:
    """
    Create a hook manager with sensible defaults.

    Args:
        memory_stack: The MemoryStack to manage
        persist_path: Path to save memory stack

    Returns:
        Configured HookManager instance
    """
    config = HookConfig(
        stop_message_interval=15,
        pre_compact_enabled=True,
        save_on_start=True,
        save_on_end=True,
        idle_timeout_seconds=300,
        persist_path=persist_path,
    )

    return HookManager(
        memory_stack=memory_stack,
        auto_save_config=config,
    )
