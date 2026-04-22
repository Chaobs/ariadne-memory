# Ariadne Memory Stack Documentation

> 4-Layer Hierarchical Memory System inspired by MemPalace

## Overview

Ariadne implements a 4-layer memory architecture that mirrors how humans organize information:

1. **L0: Identity** - Core self-knowledge
2. **L1: Narrative** - Story of experiences
3. **L2: On-Demand** - Situational context
4. **L3: Deep Search** - Complete knowledge base

## Architecture

### Layer Comparison

| Layer | Purpose | Token Budget | Persistence | Update Frequency |
|-------|---------|-------------|-------------|------------------|
| L0 Identity | Core identity/preferences | ~100 | Permanent | Rare |
| L1 Narrative | Conversation summaries | ~500-800 | Days | Per conversation |
| L2 On-Demand | Active context | ~200-500 | Hours | Per query |
| L3 Deep Search | Vector database | Unlimited | Permanent | Per ingestion |

## Usage

### Basic Setup

```python
from ariadne.memory.layers import MemoryStack

# Initialize with vector store and graph
stack = MemoryStack(
    vector_store=vector_store,
    graph_storage=graph_storage
)
```

### Setting Identity (L0)

```python
# Set core identity
stack.identity.set_identity("name", "Alice")
stack.identity.set_identity("role", "Software Engineer")

# Set preferences
stack.identity.set_preference("language", "English")
stack.identity.set_preference("timezone", "UTC")
```

### Adding Narrative (L1)

```python
# Add conversation summary
stack.narrative.add_narrative(
    content="Discussed project timeline with team",
    source="meeting_2024",
    importance=0.7,
    tags=["project", "meeting"]
)
```

### Managing Context (L2)

```python
# Add current context
stack.on_demand.add_context(
    content="Implementing new feature X",
    source="current_task",
    importance=0.9,
    tags=["development", "feature-x"]
)

# Register wake-up handler
from ariadne.memory.layers import WakeUpHandler

def extract_relevant_context(context):
    # Trigger retrieval from L3 based on query
    ...

stack.on_demand.register_wake_up(
    layer=MemoryLayer.L2_ON_DEMAND,
    handler=WakeUpHandler("context_extractor", extract_relevant_context)
)
```

### Deep Search (L3)

```python
# Search vector store
results = stack.deep_search.search(
    query="What were the key decisions?",
    top_k=10
)

# Query knowledge graph
graph_data = stack.deep_search.graph_query(
    entity="Project X",
    depth=2
)
```

### Generating Context

```python
# Generate full context for LLM
context = stack.generate_context(
    query="What am I working on?",
    max_tokens=4096
)

# Generate specific layers
context = stack.generate_context(
    query="Tell me about myself",
    include_layers=[
        MemoryLayer.L0_IDENTITY,
        MemoryLayer.L1_NARRATIVE
    ]
)
```

## Wake-Up Mechanism

The wake-up system allows layers to activate based on triggers:

```python
from ariadne.memory.layers import WakeUpContext, WakeUpHandler

def on_context_needed(context: WakeUpContext) -> List[MemoryEntry]:
    """Called when L2 context is needed."""
    # Retrieve from L3 based on query
    results = stack.deep_search.search(context.query, top_k=5)

    # Convert to memory entries
    return [
        MemoryEntry(
            content=r.content,
            layer=MemoryLayer.L2_ON_DEMAND,
            importance=0.8,
            tags=["retrieved"]
        )
        for r in results
    ]

stack.on_demand.register_wake_up(
    layer=MemoryLayer.L2_ON_DEMAND,
    handler=WakeUpHandler("context_retriever", on_context_needed)
)
```

## Persistence

### Saving

```python
# Save memory stack
stack.save("./data/memory_stack.json")

# Auto-save with hooks
from ariadne.plugins.autosave import create_default_hook_manager

hook_manager = create_default_hook_manager(
    memory_stack=stack,
    persist_path="./data/memory_stack.json"
)
hook_manager.start()
```

### Loading

```python
# Load memory stack
stack.load("./data/memory_stack.json")
```

## Configuration

### Layer Config

```python
from ariadne.memory.layers import LayerConfig, MemoryLayer

# Custom configuration
l0_config = LayerConfig(
    layer=MemoryLayer.L0_IDENTITY,
    token_limit=150,  # Larger L0
    auto_compact=True,
    compact_threshold=0.9
)

stack = MemoryStack(config={
    MemoryLayer.L0_IDENTITY: l0_config,
})
```

### Token Limits

| Layer | Default Limit | Minimum | Maximum |
|-------|--------------|---------|---------|
| L0 | 100 | 50 | 500 |
| L1 | 800 | 200 | 2000 |
| L2 | 500 | 100 | 1000 |
| L3 | Unlimited | - | - |

## Statistics

```python
stats = stack.stats()

# Output:
# {
#     "l0_identity": {"loaded": True, "attributes": 5},
#     "l1_narrative": {"count": 12, "total_tokens": 650},
#     "l2_on_demand": {"count": 5, "total_tokens": 200},
#     "l3_deep_search": {"configured": True}
# }
```

## Integration with MCP

The Memory Stack integrates with the MCP server for AI agent access:

```python
# MCP server uses Memory Stack for context
server = AriadneMCPServer()

# When generating tool context:
context = stack.generate_context(
    query=user_query,
    max_tokens=4096
)
```

## Related

- [Closet Index](Closet.md) - AAAK compressed indexing
- [Auto-Save Hooks](AutoSave.md) - Automatic persistence
- [Knowledge Graph](KnowledgeGraph.md) - L3 graph integration
