"""
Ariadne Memory Package — Vector storage and retrieval using ChromaDB.

Inspired by MemPalace's pluggable backend architecture:
https://github.com/MemPalace/mempalace

The VectorStore class provides a unified interface over ChromaDB,
abstracting away collection management, embedding, and querying details.

Memory Stack Architecture:
- L0: Identity Layer (~100 tokens) - Core identity and preferences
- L1: Narrative Layer (~500-800 tokens) - Conversation summaries
- L2: On-Demand Layer (~200-500 tokens) - Contextual retrieval
- L3: Deep Search Layer - Full vector search
"""

from ariadne.memory.store import VectorStore
from ariadne.memory.manager import MemoryManager, MemorySystem, get_manager
from ariadne.memory.layers import (
    MemoryStack,
    MemoryLayer,
    MemoryEntry,
    IdentityLayer,
    NarrativeLayer,
    OnDemandLayer,
    DeepSearchLayer,
    LayerConfig,
    WakeUpContext,
    WakeUpHandler,
)
from ariadne.memory.closet import (
    ClosetIndex,
    DrawerEntry,
    AAKEntry,
    IndexFormat,
)

__all__ = [
    "VectorStore",
    "MemoryManager",
    "MemorySystem",
    "get_manager",
    # Memory Stack
    "MemoryStack",
    "MemoryLayer",
    "MemoryEntry",
    "IdentityLayer",
    "NarrativeLayer",
    "OnDemandLayer",
    "DeepSearchLayer",
    "LayerConfig",
    "WakeUpContext",
    "WakeUpHandler",
    # Closet Index
    "ClosetIndex",
    "DrawerEntry",
    "AAKEntry",
    "IndexFormat",
]
