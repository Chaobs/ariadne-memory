# Ariadne MCP Server Documentation

> MCP (Model Context Protocol) Server for Ariadne Memory System

## Overview

The Ariadne MCP Server exposes Ariadne's capabilities (search, ingest, graph queries) as MCP tools, resources, and prompts that can be consumed by any MCP-compatible AI client.

## Features

### Core Features
- **4 MCP Tools**: `ariadne_search`, `ariadne_ingest`, `ariadne_graph_query`, `ariadne_stats`
- **MCP Resources**: `collections`, `stats`, `config`, `graph`
- **MCP Prompts**: `search`, `ingest`, `graph`, `context`, `compare`

### Enhanced Features (v0.7.0+)
- **WAL Audit Logger**: Complete operation audit trail with metrics
- **Parameter Schema Validation**: JSON Schema-based validation for all tools
- **Cache Invalidation Detection**: inode/mtime based cache management

## Installation

### Configuration

Add to your MCP configuration file (e.g., `~/.config/claude-code/mcp.json`):

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.mcp.server", "--transport", "stdio"],
      "env": {
        "ARIADNE_VECTOR_PATH": "./data/vectors",
        "ARIADNE_GRAPH_PATH": "./data/graph.db"
      }
    }
  }
}
```

### Alternative: HTTP Transport

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.mcp.server", "--transport", "http", "--port", "8765"]
    }
  }
}
```

## Tools

### ariadne_search

Search the knowledge base with semantic similarity.

**Parameters:**
```json
{
  "query": "string (required) - Search query in natural language",
  "limit": "integer (optional, default: 5, max: 50) - Maximum results",
  "collection": "string (optional, default: 'default') - Collection name",
  "min_score": "number (optional, default: 0.0) - Minimum relevance score"
}
```

**Example:**
```json
{
  "name": "ariadne_search",
  "arguments": {
    "query": "What is the capital of France?",
    "limit": 5
  }
}
```

### ariadne_ingest

Ingest documents into the knowledge base.

**Parameters:**
```json
{
  "source": "string (required) - File path or URL to ingest",
  "collection": "string (optional, default: 'default') - Collection name",
  "extract_entities": "boolean (optional, default: true) - Extract entities"
}
```

### ariadne_graph_query

Query the knowledge graph for entity relationships.

**Parameters:**
```json
{
  "entity": "string (required) - Entity name to query",
  "relation_type": "string (optional) - Filter by relation type",
  "depth": "integer (optional, default: 2, max: 5) - Traversal depth",
  "direction": "string (optional) - 'outgoing', 'incoming', or 'both'"
}
```

### ariadne_stats

Get knowledge base statistics.

**Parameters:**
```json
{
  "collection": "string (optional, default: 'default') - Collection name",
  "detailed": "boolean (optional, default: false) - Include detailed breakdown"
}
```

## Resources

### ariadne://collections

Returns list of available document collections.

### ariadne://stats

Returns knowledge base statistics.

### ariadne://config

Returns Ariadne configuration.

### ariadne://graph

Returns knowledge graph summary.

## WAL Audit Logger

The MCP server includes a Write-Ahead Log (WAL) for operation auditing.

### Features
- SQLite-backed persistent log
- Operation metrics (call count, error rate, average duration)
- Cache invalidation tracking
- Automatic log rotation

### Querying WAL

```python
from ariadne.mcp.wal import WALAuditLogger

wal = WALAuditLogger.get_instance()
stats = wal.get_statistics()
recent = wal.get_recent_entries(limit=100)
metrics = wal.get_metrics(operation="ariadne_search")
```

### WAL Schema

| Field | Type | Description |
|-------|------|-------------|
| timestamp | TEXT | ISO timestamp |
| operation | TEXT | Operation name |
| operation_type | TEXT | Type (tool_call, search, etc.) |
| params | TEXT | JSON parameters |
| result | TEXT | JSON result |
| error | TEXT | Error message |
| duration_ms | REAL | Execution time |
| cache_hit | INTEGER | Cache hit flag |
| log_level | TEXT | debug/info/warning/error |

## Parameter Schema Validation

All MCP tools validate parameters against JSON Schema definitions.

### Validation Rules
- **type**: string, number, integer, boolean, array, object
- **required**: Mandatory fields
- **enum**: Allowed values
- **minimum/maximum**: Numeric constraints
- **minLength/maxLength**: String length constraints
- **pattern**: Regex pattern matching

### Validation Errors

```json
{
  "error": "Validation failed: 2 error(s)",
  "errors": [
    {
      "path": "params.query",
      "message": "Required field 'query' is missing",
      "code": "required"
    }
  ]
}
```

## Cache Invalidation

The server tracks source file modifications using inode and mtime.

### Features
- Automatic cache invalidation on source file changes
- TTL-based expiration
- Manual invalidation API

```python
from ariadne.mcp.cache import CacheInvalidationDetector

detector = CacheInvalidationDetector(wal_logger=wal)
detector.invalidate_source_file("/path/to/data.json")
```

## Architecture

```
ariadne/mcp/
├── server.py       # Main MCP Server
├── tools.py        # Tool implementations
├── resources.py    # Resource handlers
├── prompts.py      # Prompt templates
├── wal.py          # WAL Audit Logger
├── validation.py    # Schema Validator
└── cache.py        # Cache Manager
```

## License

MIT License
