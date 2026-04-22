# Ariadne Closet Index Documentation

> AAAK (Almost All Answer Key) Compressed Indexing System

## Overview

The Closet Index provides fast LLM-accessible memory indexing using the AAAK format, inspired by MemPalace's Closet system.

## AAAK Format

**Almost All Answer Key** is a compressed format for mapping topics/entities to memory drawers:

```
topic|entities|→drawer_ids
```

### Examples

```
python|Guido+programming|→drw_a1b2c3d4
machine_learning|algorithms+training|→drw_e5f6g7h8,drw_i9j0k1l2
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Closet Index                          │
├─────────────────────────────────────────────────────────┤
│  Drawers          AAAK Index       Inverted Index     │
│  ┌─────────┐     ┌───────────┐     ┌──────────────┐   │
│  │ drw_001 │     │ topic|→id │     │ entity → ids │   │
│  │ content │     │ ent|→id   │     │ topic → ids  │   │
│  └─────────┘     └───────────┘     └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Usage

### Basic Setup

```python
from ariadne.memory.closet import ClosetIndex

# Initialize closet
closet = ClosetIndex("./data/closet.db")
```

### Adding Drawers

```python
# Add a document drawer
drawer = closet.add_drawer(
    content="Python was created by Guido van Rossum in 1991...",
    content_type="document",
    topics=["python", "programming", "history"],
    entities=["Guido van Rossum"],
    tags=["language", "history"]
)
```

### Looking Up Drawers

```python
# By query
results = closet.lookup("Python history", max_results=5)
for drawer in results:
    print(f"{drawer.drawer_id}: {drawer.content[:50]}...")

# By entities
results = closet.lookup_by_entities(
    entities=["Guido van Rossum"],
    max_results=5
)

# By topics
results = closet.lookup_by_topics(
    topics=["python"],
    max_results=5
)
```

## LLM Integration

### Building AAAK Index

```python
# Build AAAK index for LLM
aak_entries = closet.build_aak_index()

# Each entry contains:
for entry in aak_entries:
    print(entry.to_aaak())
    # Output: python|Guido|→drw_a1b2c3d4
```

### Generating LLM Context

```python
# Get formatted AAAK for prompt
aak_context = closet.get_aaak_for_llm(
    max_entries=20,
    max_token_budget=500
)

print(aak_context)
# # Almost All Answer Key (AAAK) Index
# # Format: topic|entities|→drawer_ids
# #
# # Use drawer_ids to quickly locate relevant memories
#
# python|Guido+programming|→drw_a1b2c3d4
# machine_learning|algorithms|→drw_e5f6g7h8
```

### Retrieving Drawer Contents

```python
# After LLM selects drawer IDs
drawer_ids = ["drw_a1b2c3d4", "drw_e5f6g7h8"]

contents = closet.get_drawer_contents(
    drawer_ids=drawer_ids,
    max_tokens=1000
)
```

## Drawer Types

| Type | Description | Use Case |
|------|-------------|----------|
| document | General documents | PDFs, articles |
| entity | Entity information | Person/Org facts |
| summary | Condensed content | Meeting summaries |
| conversation | Chat history | Conversation context |

## Index Structure

### Drawers Table

```sql
CREATE TABLE drawers (
    drawer_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'document',
    tags TEXT,
    entities TEXT,
    topics TEXT,
    token_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    metadata TEXT
);
```

### AAAK Index Table

```sql
CREATE TABLE aak_index (
    aak_id TEXT PRIMARY KEY,
    keywords TEXT,
    topic TEXT,
    drawer_ids TEXT,
    score REAL DEFAULT 0.5,
    created_at TEXT
);
```

### Inverted Index Tables

```sql
-- Entity → Drawers
CREATE TABLE entity_index (
    entity_name TEXT,
    drawer_id TEXT,
    frequency INTEGER DEFAULT 1,
    PRIMARY KEY (entity_name, drawer_id)
);

-- Topic → Drawers
CREATE TABLE topic_index (
    topic TEXT,
    drawer_id TEXT,
    frequency INTEGER DEFAULT 1,
    PRIMARY KEY (topic, drawer_id)
);
```

## Advanced Usage

### Custom Drawer ID

```python
drawer = closet.add_drawer(
    content="Important meeting notes",
    drawer_id="meeting_2024_04",  # Custom ID
    topics=["meeting"],
    entities=["Team"]
)
```

### Multiple Topics/Entities

```python
drawer = closet.add_drawer(
    content="Multi-domain content...",
    topics=["python", "machine_learning", "data_science"],
    entities=["Python", "TensorFlow", "PyTorch"]
)
```

### Metadata

```python
drawer = closet.add_drawer(
    content="Project specification...",
    topics=["project"],
    metadata={
        "project_name": "MyProject",
        "version": "1.0",
        "priority": "high"
    }
)
```

## Performance

### Lookup Performance

| Lookup Type | Complexity | Use Case |
|-------------|-----------|----------|
| Entity lookup | O(log n) | Fast entity-based retrieval |
| Topic lookup | O(log n) | Fast topic-based retrieval |
| Keyword search | O(n) | Full-text search |
| AAAK build | O(n log n) | Index reconstruction |

### Optimization Tips

1. **Batch additions**: Add multiple drawers at once when possible
2. **Keyword extraction**: Let the system extract keywords automatically
3. **Index rebuild**: Rebuild AAAK index periodically for optimal performance

## Integration with Memory Stack

```python
from ariadne.memory.layers import MemoryStack
from ariadne.memory.closet import ClosetIndex

# Initialize both
stack = MemoryStack()
closet = ClosetIndex()

# When adding to L1 narrative
narrative = "Discussed Python performance optimization"
stack.narrative.add_narrative(narrative, source="meeting")

# Also add to closet
drawer = closet.add_drawer(
    content=narrative,
    content_type="conversation",
    topics=["python", "performance"],
    entities=["Python"]
)

# Build AAAK from memory
closet.build_aak_index()
```

## Statistics

```python
stats = closet.stats()

# Output:
# {
#     "total_drawers": 150,
#     "aak_entries": 45,
#     "database_path": "./data/closet.db",
#     "drawer_types": {
#         "document": 100,
#         "entity": 20,
#         "summary": 20,
#         "conversation": 10
#     }
# }
```

## Related

- [Memory Stack](MemoryStack.md) - 4-layer memory architecture
- [Auto-Save](AutoSave.md) - Automatic persistence
- [MCP Documentation](MCP.md) - MCP server integration
