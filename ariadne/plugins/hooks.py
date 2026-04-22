"""
Ariadne Hook System — Lifecycle hooks for ingest and search operations.

Provides a lightweight event system that allows plugins to inject custom
logic at key points in the Ariadne pipeline:

- before_ingest / after_ingest: Modify documents during ingestion
- before_search / after_search: Transform queries or filter results

Usage:
    from ariadne.plugins.hooks import on

    @on("after_ingest")
    def add_language_metadata(file_path, docs):
        for doc in docs:
            doc.metadata["detected_language"] = detect(doc.content)
        return docs

    @on("after_search")
    def deduplicate(query, results):
        seen = set()
        return [r for r in results if r.doc_id not in seen and not seen.add(r.doc_id)]
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookPoint(str, Enum):
    """Well-defined hook points in the Ariadne pipeline."""
    # Ingestion hooks
    BEFORE_INGEST = "before_ingest"   # (file_path: str, docs: List[Document]) -> List[Document]
    AFTER_INGEST = "after_ingest"     # (file_path: str, docs: List[Document]) -> List[Document]

    # Search hooks
    BEFORE_SEARCH = "before_search"   # (query: str) -> str
    AFTER_SEARCH = "after_search"     # (query: str, results: list) -> list


class HookManager:
    """
    Lightweight hook system for Ariadne.

    Hooks are callables that run at specific points in the pipeline.
    They can modify data in-flight (e.g., adding metadata, filtering results).
    """

    # Registered hooks: hook_point -> list of (callable, priority)
    _hooks: Dict[str, List[tuple]] = {}

    @classmethod
    def register(
        cls,
        hook_point: str,
        func: Callable,
        priority: int = 0,
    ) -> None:
        """
        Register a hook function.

        Args:
            hook_point: One of the HookPoint values or a custom string.
            func: Callable to invoke when the hook fires.
            priority: Higher priority runs first. Default 0.
        """
        if hook_point not in cls._hooks:
            cls._hooks[hook_point] = []
        cls._hooks[hook_point].append((func, priority))
        # Sort by priority descending (higher runs first)
        cls._hooks[hook_point].sort(key=lambda x: x[1], reverse=True)
        logger.debug(f"Hook registered: {hook_point} -> {func.__name__} (priority={priority})")

    @classmethod
    def deregister(cls, hook_point: str, func: Optional[Callable] = None) -> None:
        """
        Deregister a hook function.

        If func is None, removes all hooks for that point.
        """
        if hook_point not in cls._hooks:
            return
        if func is None:
            del cls._hooks[hook_point]
        else:
            cls._hooks[hook_point] = [
                (f, p) for f, p in cls._hooks[hook_point] if f != func
            ]

    @classmethod
    def fire(cls, hook_point: str, *args, **kwargs) -> Any:
        """
        Fire all hooks registered for a point.

        Hooks are called in priority order. Each hook receives the output
        of the previous hook as input (pipeline pattern). The first hook
        receives the original arguments.

        For "before" hooks: the return value replaces the input for the
        next hook and ultimately the pipeline.

        For "after" hooks: same pattern — each hook can transform the result.

        Args:
            hook_point: The hook point to fire.
            *args: Positional arguments passed to the first hook.
            **kwargs: Keyword arguments passed to all hooks.

        Returns:
            The transformed result after all hooks have run.
        """
        hooks = cls._hooks.get(hook_point, [])
        if not hooks:
            # No hooks — return the first positional arg unchanged (if any)
            return args[0] if args else None

        result = args[0] if args else None

        for func, priority in hooks:
            try:
                # Call hook with the current result + any kwargs
                transformed = func(result, **kwargs)
                if transformed is not None:
                    result = transformed
            except Exception as e:
                logger.error(
                    f"Hook {func.__name__} failed at {hook_point}: {e}"
                )
                # Continue with other hooks even if one fails

        return result

    @classmethod
    def list_hooks(cls) -> Dict[str, List[str]]:
        """List all registered hooks (for diagnostics)."""
        return {
            point: [f"{func.__name__} (priority={pri})" for func, pri in hooks]
            for point, hooks in cls._hooks.items()
        }

    @classmethod
    def reset(cls) -> None:
        """Reset all hooks (useful for testing)."""
        cls._hooks.clear()


# ── Convenience decorator ─────────────────────────────────────────────────

def on(hook_point: str, priority: int = 0):
    """
    Decorator to register a hook function.

    Usage:
        @on("after_ingest")
        def my_hook(docs, **kwargs):
            # Modify docs...
            return docs

        @on("before_search", priority=10)
        def rewrite_query(query, **kwargs):
            return query + " expanded terms"
    """
    def decorator(func: Callable) -> Callable:
        HookManager.register(hook_point, func, priority=priority)
        return func
    return decorator
