"""
Ariadne Realtime Vectorization Module.

Provides real-time ingestion of AI agent conversation memories into vector storage.
Supports:
- Automatic vectorization of session observations
- File watcher for external memory files (e.g., MEMORY.md)
- CLI and Web UI interfaces
"""

from ariadne.realtime.ingestor import ObservationIngestor
from ariadne.realtime.watcher import FileWatcher
from ariadne.realtime.vectorizer import RealtimeVectorizer

__all__ = [
    "ObservationIngestor",
    "FileWatcher",
    "RealtimeVectorizer",
]