"""
Ariadne Plugin System — Extensible ingestors and lifecycle hooks.

This package provides the public API for Ariadne's plugin system:

- IngestorRegistry: Register custom ingestors for new file formats
- HookManager / on(): Register lifecycle hooks for ingest and search
- ingest_hook: Decorator to register ingestors
- load_all_plugins: Load plugins from entry_points and directories

Quick Start:
    # Register a custom ingestor
    from ariadne.plugins import ingest_hook
    from ariadne.ingest.base import BaseIngestor, SourceType

    @ingest_hook(extensions=[".log", ".syslog"])
    class LogIngestor(BaseIngestor):
        source_type = SourceType.TXT
        def _extract(self, path):
            with open(path) as f:
                return [f.read()]

    # Register a lifecycle hook
    from ariadne.plugins import on

    @on("after_ingest")
    def add_metadata(file_path, docs):
        for doc in docs:
            doc.metadata["custom_field"] = "custom_value"
        return docs
"""

from ariadne.plugins.registry import IngestorRegistry
from ariadne.plugins.hooks import HookManager, HookPoint, on
from ariadne.plugins.loader import load_all_plugins


def ingest_hook(extensions, priority: int = 0):
    """
    Decorator to register a custom ingestor.

    Usage:
        @ingest_hook(extensions=[".log", ".syslog"])
        class LogIngestor(BaseIngestor):
            source_type = SourceType.TXT
            def _extract(self, path): ...
    """
    return IngestorRegistry.register_decorator(extensions=extensions, priority=priority)


__all__ = [
    "IngestorRegistry",
    "HookManager",
    "HookPoint",
    "on",
    "ingest_hook",
    "load_all_plugins",
]
