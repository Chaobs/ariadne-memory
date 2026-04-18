"""
Ariadne Memory Package — Vector storage and retrieval using ChromaDB.

Inspired by MemPalace's pluggable backend architecture:
https://github.com/MemPalace/mempalace

The VectorStore class provides a unified interface over ChromaDB,
abstracting away collection management, embedding, and querying details.
"""

from ariadne.memory.store import VectorStore
from ariadne.memory.manager import MemoryManager, MemorySystem, get_manager

__all__ = ["VectorStore", "MemoryManager", "MemorySystem", "get_manager"]
