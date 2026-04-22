"""
Ariadne 4-Layer Memory Stack - MemPalace-inspired memory architecture.

Implements a hierarchical memory system with different retrieval strategies:
- L0: Identity Layer (~100 tokens) - Core identity and preferences
- L1: Narrative Layer (~500-800 tokens) - Conversation summaries
- L2: On-Demand Layer (~200-500 tokens) - Contextual retrieval
- L3: Deep Search Layer - Full vector search

Inspired by MemPalace's Memory Stack architecture.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class MemoryLayer(str, Enum):
    """Memory layer types."""
    L0_IDENTITY = "l0_identity"      # ~100 tokens: identity, preferences
    L1_NARRATIVE = "l1_narrative"    # ~500-800 tokens: conversation summaries
    L2_ON_DEMAND = "l2_on_demand"    # ~200-500 tokens: contextual retrieval
    L3_DEEP_SEARCH = "l3_deep_search"  # Full vector search


@dataclass
class MemoryEntry:
    """A single memory entry with layer metadata."""
    content: str
    layer: MemoryLayer
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    token_count: int = 0
    source: str = ""  # Source of the memory (conversation, document, etc.)
    importance: float = 0.5  # 0-1, affects retention
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = self.estimate_tokens(self.content)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count (rough approximation: ~4 chars per token)."""
        return len(text) // 4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "layer": self.layer.value,
            "timestamp": self.timestamp,
            "token_count": self.token_count,
            "source": self.source,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class WakeUpContext:
    """Context passed to wake-up handlers."""
    layer: MemoryLayer
    query: str
    existing_memories: List[MemoryEntry]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WakeUpHandler:
    """Handler for layer wake-up events."""

    def __init__(self, name: str, handler: Callable[[WakeUpContext], List[MemoryEntry]]):
        self.name = name
        self.handler = handler

    def __call__(self, context: WakeUpContext) -> List[MemoryEntry]:
        return self.handler(context)


class LayerConfig:
    """Configuration for a memory layer."""

    # Token limits per layer
    TOKEN_LIMITS = {
        MemoryLayer.L0_IDENTITY: 100,
        MemoryLayer.L1_NARRATIVE: 800,
        MemoryLayer.L2_ON_DEMAND: 500,
        MemoryLayer.L3_DEEP_SEARCH: -1,  # Unlimited
    }

    # Retention settings
    DEFAULT_RETENTION = {
        MemoryLayer.L0_IDENTITY: 30 * 24 * 3600,  # 30 days
        MemoryLayer.L1_NARRATIVE: 7 * 24 * 3600,  # 7 days
        MemoryLayer.L2_ON_DEMAND: 24 * 3600,  # 1 day
        MemoryLayer.L3_DEEP_SEARCH: -1,  # Permanent
    }

    def __init__(
        self,
        layer: MemoryLayer,
        token_limit: Optional[int] = None,
        retention_seconds: Optional[int] = None,
        auto_compact: bool = True,
        compact_threshold: float = 0.9,
    ):
        self.layer = layer
        self.token_limit = token_limit or self.TOKEN_LIMITS.get(layer, -1)
        self.retention_seconds = retention_seconds or self.DEFAULT_RETENTION.get(layer, -1)
        self.auto_compact = auto_compact
        self.compact_threshold = compact_threshold

    @property
    def effective_token_limit(self) -> int:
        """Get effective token limit considering compaction threshold."""
        if self.compact_threshold < 1.0:
            return int(self.token_limit * self.compact_threshold)
        return self.token_limit


class IdentityLayer:
    """
    L0: Identity Layer - Stores core identity and preferences.

    This layer holds:
    - User's name, role, and core identity
    - Communication preferences
    - Key values and goals
    - Important relationships

    Size: ~100 tokens
    """

    def __init__(self, config: Optional[LayerConfig] = None):
        self.config = config or LayerConfig(MemoryLayer.L0_IDENTITY)
        self._identity: Dict[str, Any] = {}
        self._preferences: Dict[str, Any] = {}
        self._loaded = False

    def set_identity(self, key: str, value: Any) -> None:
        """Set an identity attribute."""
        self._identity[key] = value
        self._loaded = True

    def get_identity(self, key: str, default: Any = None) -> Any:
        """Get an identity attribute."""
        return self._identity.get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        """Set a preference."""
        self._preferences[key] = value
        self._loaded = True

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a preference."""
        return self._preferences.get(key, default)

    def to_memory_entries(self) -> List[MemoryEntry]:
        """Convert to memory entries for the stack."""
        entries = []

        if self._identity:
            identity_text = json.dumps(self._identity, ensure_ascii=False)
            entries.append(MemoryEntry(
                content=f"[Identity] {identity_text}",
                layer=MemoryLayer.L0_IDENTITY,
                source="identity_layer",
                importance=1.0,
                tags=["identity", "core"],
            ))

        if self._preferences:
            pref_text = json.dumps(self._preferences, ensure_ascii=False)
            entries.append(MemoryEntry(
                content=f"[Preferences] {pref_text}",
                layer=MemoryLayer.L0_IDENTITY,
                source="preferences_layer",
                importance=0.9,
                tags=["preferences"],
            ))

        return entries

    def from_memory_entries(self, entries: List[MemoryEntry]) -> None:
        """Load from memory entries."""
        for entry in entries:
            if entry.layer != MemoryLayer.L0_IDENTITY:
                continue

            if entry.content.startswith("[Identity]"):
                try:
                    self._identity = json.loads(entry.content[10:])
                    self._loaded = True
                except json.JSONDecodeError:
                    pass
            elif entry.content.startswith("[Preferences]"):
                try:
                    self._preferences = json.loads(entry.content[13:])
                    self._loaded = True
                except json.JSONDecodeError:
                    pass

    def to_context(self, max_tokens: int = 100) -> str:
        """Generate context string for LLM prompt."""
        if not self._loaded:
            return ""

        parts = []
        remaining_tokens = max_tokens

        if self._identity:
            identity_text = json.dumps(self._identity, ensure_ascii=False)
            if len(identity_text) // 4 <= remaining_tokens:
                parts.append(f"User Identity: {identity_text}")
                remaining_tokens -= len(identity_text) // 4

        if self._preferences and remaining_tokens > 20:
            pref_text = json.dumps(self._preferences, ensure_ascii=False)
            if len(pref_text) // 4 <= remaining_tokens:
                parts.append(f"User Preferences: {pref_text}")

        return "\n".join(parts) if parts else ""


class NarrativeLayer:
    """
    L1: Narrative Layer - Stores conversation summaries.

    This layer holds:
    - Conversation summaries
    - Key decisions and outcomes
    - Important context from recent interactions
    - Narrative arc of ongoing projects

    Size: ~500-800 tokens
    """

    def __init__(self, config: Optional[LayerConfig] = None):
        self.config = config or LayerConfig(MemoryLayer.L1_NARRATIVE)
        self._narratives: List[MemoryEntry] = []
        self._compactor: Optional[Callable] = None

    def add_narrative(
        self,
        content: str,
        source: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """Add a new narrative."""
        entry = MemoryEntry(
            content=content,
            layer=MemoryLayer.L1_NARRATIVE,
            source=source,
            importance=importance,
            tags=tags or [],
        )
        self._narratives.append(entry)
        self._maybe_compact()
        return entry

    def _maybe_compact(self) -> None:
        """Compact narratives if over limit."""
        if not self.config.auto_compact:
            return

        total_tokens = sum(e.token_count for e in self._narratives)
        limit = self.config.effective_token_limit

        if total_tokens > limit:
            self._compact(preserve_importance=True)

    def _compact(self, preserve_importance: bool = True) -> None:
        """Compact narratives to fit within token limit."""
        limit = self.config.effective_token_limit

        if preserve_importance:
            # Sort by importance, keep most important
            self._narratives.sort(key=lambda e: e.importance, reverse=True)

        # Remove least important until under limit
        while (
            self._narratives and
            sum(e.token_count for e in self._narratives) > limit
        ):
            removed = self._narratives.pop()
            logger.debug(f"Compacting narrative: {removed.content[:50]}...")

        logger.info(f"Narrative layer compacted to {len(self._narratives)} entries")

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        """Get most recent narratives."""
        sorted_narratives = sorted(
            self._narratives,
            key=lambda e: e.timestamp,
            reverse=True
        )
        return sorted_narratives[:limit]

    def to_context(self, max_tokens: int = 800) -> str:
        """Generate context string for LLM prompt."""
        narratives = self.get_recent(limit=10)
        if not narratives:
            return ""

        parts = ["[Recent Context]"]
        remaining_tokens = max_tokens - len("[Recent Context]") // 4

        for narrative in narratives:
            tokens = narrative.token_count
            if tokens <= remaining_tokens:
                parts.append(f"- {narrative.content}")
                remaining_tokens -= tokens
            else:
                break

        return "\n".join(parts) if len(parts) > 1 else ""

    def to_memory_entries(self) -> List[MemoryEntry]:
        """Get all narrative entries."""
        return self._narratives.copy()

    def from_memory_entries(self, entries: List[MemoryEntry]) -> None:
        """Load from memory entries."""
        self._narratives = [e for e in entries if e.layer == MemoryLayer.L1_NARRATIVE]


class OnDemandLayer:
    """
    L2: On-Demand Layer - Contextual retrieval layer.

    This layer holds:
    - Active project context
    - Current task details
    - Relevant domain knowledge
    - Retrieved memories for current query

    Size: ~200-500 tokens
    """

    def __init__(self, config: Optional[LayerConfig] = None):
        self.config = config or LayerConfig(MemoryLayer.L2_ON_DEMAND)
        self._context: List[MemoryEntry] = []
        self._wake_up_handlers: Dict[MemoryLayer, List[WakeUpHandler]] = {
            layer: [] for layer in MemoryLayer
        }

    def add_context(
        self,
        content: str,
        source: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """Add context entry."""
        entry = MemoryEntry(
            content=content,
            layer=MemoryLayer.L2_ON_DEMAND,
            source=source,
            importance=importance,
            tags=tags or [],
        )
        self._context.append(entry)
        self._maybe_compact()
        return entry

    def _maybe_compact(self) -> None:
        """Compact context if over limit."""
        if not self.config.auto_compact:
            return

        total_tokens = sum(e.token_count for e in self._context)
        limit = self.config.effective_token_limit

        if total_tokens > limit:
            self._compact()

    def _compact(self) -> None:
        """Compact to fit within token limit."""
        limit = self.config.effective_token_limit

        # Sort by importance, keep most important
        self._context.sort(key=lambda e: e.importance, reverse=True)

        while self._context and sum(e.token_count for e in self._context) > limit:
            self._context.pop()

    def register_wake_up(self, layer: MemoryLayer, handler: WakeUpHandler) -> None:
        """Register a wake-up handler for a layer."""
        self._wake_up_handlers[layer].append(handler)

    def wake_up(self, query: str, layer: MemoryLayer) -> List[MemoryEntry]:
        """Trigger wake-up handlers for a layer."""
        context = WakeUpContext(
            layer=layer,
            query=query,
            existing_memories=self._context,
        )

        results = []
        for handler in self._wake_up_handlers.get(layer, []):
            try:
                entries = handler(context)
                results.extend(entries)
            except Exception as e:
                logger.error(f"Wake-up handler {handler.name} failed: {e}")

        return results

    def to_context(self, max_tokens: int = 500) -> str:
        """Generate context string for LLM prompt."""
        if not self._context:
            return ""

        parts = ["[Current Context]"]
        remaining_tokens = max_tokens - len("[Current Context]") // 4

        for entry in sorted(self._context, key=lambda e: e.importance, reverse=True):
            tokens = entry.token_count
            if tokens <= remaining_tokens:
                parts.append(f"- {entry.content}")
                remaining_tokens -= tokens
            else:
                break

        return "\n".join(parts) if len(parts) > 1 else ""

    def to_memory_entries(self) -> List[MemoryEntry]:
        """Get all context entries."""
        return self._context.copy()

    def from_memory_entries(self, entries: List[MemoryEntry]) -> None:
        """Load from memory entries."""
        self._context = [e for e in entries if e.layer == MemoryLayer.L2_ON_DEMAND]

    def clear(self) -> None:
        """Clear all context."""
        self._context.clear()


class DeepSearchLayer:
    """
    L3: Deep Search Layer - Full vector search integration.

    This layer provides:
    - Vector similarity search
    - Knowledge graph queries
    - Full document retrieval
    - Cross-reference resolution
    """

    def __init__(self, config: Optional[LayerConfig] = None):
        self.config = config or LayerConfig(MemoryLayer.L3_DEEP_SEARCH)
        self._vector_store = None
        self._graph_storage = None

    def set_vector_store(self, vector_store: Any) -> None:
        """Set the vector store for search."""
        self._vector_store = vector_store

    def set_graph_storage(self, graph_storage: Any) -> None:
        """Set the graph storage for queries."""
        self._graph_storage = graph_storage

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search vector store.

        Returns:
            List of (content, score, metadata) tuples
        """
        if not self._vector_store:
            logger.warning("Vector store not configured for deep search")
            return []

        try:
            results = self._vector_store.search(query, top_k=top_k)
            return [(doc.content, score, doc.metadata) for doc, score in results]
        except Exception as e:
            logger.error(f"Deep search error: {e}")
            return []

    def graph_query(
        self,
        entity: str,
        depth: int = 2,
        relation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query the knowledge graph."""
        if not self._graph_storage:
            logger.warning("Graph storage not configured for deep search")
            return {}

        try:
            found = self._graph_storage.get_entity_by_name(entity)
            if not found:
                return {"entities": [], "relations": []}

            # Get relations (simplified - actual implementation would be more complex)
            neighbors = self._graph_storage.get_neighbors(found.entity_id)

            return {
                "center_entity": found.to_dict(),
                "neighbors": [n[0].to_dict() for n in neighbors],
            }
        except Exception as e:
            logger.error(f"Graph query error: {e}")
            return {}

    def to_context(self, query: str, max_tokens: int = 1000) -> str:
        """Generate context by searching and formatting results."""
        results = self.search(query, top_k=5)
        if not results:
            return ""

        parts = ["[Retrieved Knowledge]"]
        remaining_tokens = max_tokens - len("[Retrieved Knowledge]") // 4

        for content, score, metadata in results:
            # Estimate tokens
            tokens = len(content) // 4
            if tokens <= remaining_tokens:
                parts.append(f"[Relevance: {score:.2f}] {content}")
                remaining_tokens -= tokens
            else:
                # Truncate content
                truncated = content[:remaining_tokens * 4]
                parts.append(f"[Relevance: {score:.2f}] {truncated}...")
                break

        return "\n".join(parts)


class MemoryStack:
    """
    Complete 4-Layer Memory Stack.

    Integrates all memory layers with automatic context management:
    - L0: Identity Layer
    - L1: Narrative Layer
    - L2: On-Demand Layer
    - L3: Deep Search Layer

    Usage:
        stack = MemoryStack()
        stack.identity.set_identity("name", "Alice")
        stack.narrative.add_narrative("Working on Project X")
        stack.on_demand.add_context("Current task: implementing feature Y")

        # Generate full context for LLM
        context = stack.generate_context(query="What am I working on?")
    """

    def __init__(
        self,
        vector_store: Optional[Any] = None,
        graph_storage: Optional[Any] = None,
        config: Optional[Dict[MemoryLayer, LayerConfig]] = None,
    ):
        """Initialize memory stack."""
        self.identity = IdentityLayer(config.get(MemoryLayer.L0_IDENTITY) if config else None)
        self.narrative = NarrativeLayer(config.get(MemoryLayer.L1_NARRATIVE) if config else None)
        self.on_demand = OnDemandLayer(config.get(MemoryLayer.L2_ON_DEMAND) if config else None)
        self.deep_search = DeepSearchLayer(config.get(MemoryLayer.L3_DEEP_SEARCH) if config else None)

        # Set storage backends
        if vector_store:
            self.deep_search.set_vector_store(vector_store)
        if graph_storage:
            self.deep_search.set_graph_storage(graph_storage)

    def generate_context(
        self,
        query: Optional[str] = None,
        max_tokens: int = 4096,
        include_layers: Optional[List[MemoryLayer]] = None,
    ) -> str:
        """
        Generate context string from all layers.

        Args:
            query: Optional query to trigger L2 wake-up and L3 search
            max_tokens: Maximum tokens for context
            include_layers: Layers to include (default: all)

        Returns:
            Context string suitable for LLM prompt
        """
        include_layers = include_layers or [
            MemoryLayer.L0_IDENTITY,
            MemoryLayer.L1_NARRATIVE,
            MemoryLayer.L2_ON_DEMAND,
            MemoryLayer.L3_DEEP_SEARCH,
        ]

        contexts = []
        remaining_tokens = max_tokens

        # L0: Identity (always first, limited)
        if MemoryLayer.L0_IDENTITY in include_layers:
            l0_context = self.identity.to_context(max_tokens=100)
            if l0_context:
                contexts.append(l0_context)
                remaining_tokens -= len(l0_context) // 4

        # L1: Narrative
        if MemoryLayer.L1_NARRATIVE in include_layers:
            l1_context = self.narrative.to_context(max_tokens=remaining_tokens)
            if l1_context:
                contexts.append(l1_context)
                remaining_tokens -= len(l1_context) // 4

        # L2: On-Demand (triggered by query)
        if MemoryLayer.L2_ON_DEMAND in include_layers and query:
            # Trigger wake-up handlers
            self.on_demand.wake_up(query, MemoryLayer.L2_ON_DEMAND)
            l2_context = self.on_demand.to_context(max_tokens=remaining_tokens)
            if l2_context:
                contexts.append(l2_context)
                remaining_tokens -= len(l2_context) // 4

        # L3: Deep Search (triggered by query)
        if MemoryLayer.L3_DEEP_SEARCH in include_layers and query:
            l3_context = self.deep_search.to_context(query, max_tokens=remaining_tokens)
            if l3_context:
                contexts.append(l3_context)

        return "\n\n".join(contexts)

    def add_memory(
        self,
        content: str,
        layer: MemoryLayer,
        source: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """Add a memory entry to the appropriate layer."""
        entry = MemoryEntry(
            content=content,
            layer=layer,
            source=source,
            importance=importance,
            tags=tags or [],
        )

        if layer == MemoryLayer.L0_IDENTITY:
            # Special handling for identity
            self.identity._loaded = True
        elif layer == MemoryLayer.L1_NARRATIVE:
            self.narrative.add_narrative(content, source, importance, tags)
        elif layer == MemoryLayer.L2_ON_DEMAND:
            self.on_demand.add_context(content, source, importance, tags)
        elif layer == MemoryLayer.L3_DEEP_SEARCH:
            # L3 doesn't store inline, it searches vector store
            pass

        return entry

    def get_all_entries(self) -> List[MemoryEntry]:
        """Get all memory entries from all layers."""
        entries = []
        entries.extend(self.identity.to_memory_entries())
        entries.extend(self.narrative.to_memory_entries())
        entries.extend(self.on_demand.to_memory_entries())
        return entries

    def save(self, path: str) -> None:
        """Save memory stack to file."""
        data = {
            "identity": self.identity._identity,
            "preferences": self.identity._preferences,
            "narratives": [e.to_dict() for e in self.narrative._narratives],
            "context": [e.to_dict() for e in self.on_demand._context],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Memory stack saved to {path}")

    def load(self, path: str) -> None:
        """Load memory stack from file."""
        if not Path(path).exists():
            logger.warning(f"Memory stack file not found: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Load identity
        self.identity._identity = data.get("identity", {})
        self.identity._preferences = data.get("preferences", {})
        self.identity._loaded = bool(self.identity._identity)

        # Load narratives
        self.narrative._narratives = [
            MemoryEntry(**e) for e in data.get("narratives", [])
        ]

        # Load context
        self.on_demand._context = [
            MemoryEntry(**e) for e in data.get("context", [])
        ]

        logger.info(f"Memory stack loaded from {path}")

    def clear(self) -> None:
        """Clear all layers."""
        self.identity._identity.clear()
        self.identity._preferences.clear()
        self.identity._loaded = False
        self.narrative._narratives.clear()
        self.on_demand.clear()

    def stats(self) -> Dict[str, Any]:
        """Get statistics for all layers."""
        return {
            "l0_identity": {
                "loaded": self.identity._loaded,
                "attributes": len(self.identity._identity),
                "preferences": len(self.identity._preferences),
            },
            "l1_narrative": {
                "count": len(self.narrative._narratives),
                "total_tokens": sum(e.token_count for e in self.narrative._narratives),
                "token_limit": self.narrative.config.token_limit,
            },
            "l2_on_demand": {
                "count": len(self.on_demand._context),
                "total_tokens": sum(e.token_count for e in self.on_demand._context),
                "token_limit": self.on_demand.config.token_limit,
            },
            "l3_deep_search": {
                "vector_store_configured": self.deep_search._vector_store is not None,
                "graph_storage_configured": self.deep_search._graph_storage is not None,
            },
        }
