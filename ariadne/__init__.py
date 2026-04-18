"""
Ariadne — Cross-Source AI Memory & Knowledge Weaving System

Ariadne weaves together knowledge from diverse sources — documents, conversations,
code, and more — into a unified memory system powered by vector search and
knowledge graphs.

Example:
    >>> from ariadne.ingest import MarkdownIngestor
    >>> from ariadne.memory import VectorStore
    >>> store = VectorStore()
    >>> docs = MarkdownIngestor().ingest("path/to/notes.md")
    >>> store.add(docs)
    >>> results = store.search("What did I write about AI?")
"""

__version__ = "0.1.0"
__author__ = "Chaobs"

from ariadne.memory import VectorStore
from ariadne.ingest.base import BaseIngestor

__all__ = [
    "__version__",
    "VectorStore",
    "BaseIngestor",
]

# GUI is optional (requires tkinter)
try:
    import tkinter
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False
