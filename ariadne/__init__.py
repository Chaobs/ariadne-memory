"""
Ariadne — Cross-Source AI Memory & Knowledge Weaving System

Ariadne weaves together knowledge from diverse sources — documents, conversations,
code, and more — into a unified memory system powered by vector search and
knowledge graphs.

Features:
- Multi-format document ingestion (Markdown, PDF, Word, PPT, Excel, etc.)
- Semantic search with ChromaDB vector storage
- Multi-memory system support with CRUD operations
- Knowledge graph extraction and visualization
- LLM-powered features (summarization, entity extraction, reranking)
- Multi-language support (7 UN languages)
- CLI and Web UI interfaces

Example:
    >>> from ariadne.ingest import MarkdownIngestor
    >>> from ariadne.memory import VectorStore
    >>> store = VectorStore()
    >>> docs = MarkdownIngestor().ingest("path/to/notes.md")
    >>> store.add(docs)
    >>> results = store.search("What did I write about AI?")
"""

# Auto-setup vendored dependencies
from pathlib import Path as _Path
_vendor_init = _Path(__file__).parent.parent / "vendor" / "__init__.py"
if _vendor_init.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vendor", _vendor_init)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

__version__ = "0.6.2"
__author__ = "Chaobs"

from ariadne.memory import VectorStore
from ariadne.ingest.base import BaseIngestor

# Core exports
from ariadne.config import AriadneConfig, get_config
from ariadne.advanced import Summarizer, GraphVisualizer, Exporter

# Plugin system exports
from ariadne.plugins import ingest_hook, on, IngestorRegistry, HookManager

__all__ = [
    # Version info
    "__version__",
    
    # Core modules
    "VectorStore",
    "BaseIngestor",
    
    # Configuration
    "AriadneConfig",
    "get_config",
    
    # Advanced features
    "Summarizer",
    "GraphVisualizer",
    "Exporter",

    # Plugin system
    "ingest_hook",
    "on",
    "IngestorRegistry",
    "HookManager",
]

