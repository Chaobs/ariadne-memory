# Ariadne User Guide

> Complete guide to Ariadne CLI and GUI.

**[中文版](USAGE_CN.md)** | English Version

---

## Table of Contents

- [Basic Concepts](#basic-concepts)
- [Basic Usage](#basic-usage)
- [CLI Command Reference](#cli-command-reference)
- [GUI Usage](#gui-usage)
- [Tips & Tricks](#tips--tricks)
- [Troubleshooting](#troubleshooting)

---

## Basic Concepts

### Memory System

Ariadne supports multiple independent **memory systems**, each like a separate notebook:

| Concept | Description |
|---------|-------------|
| **Memory System** | Independent knowledge base with its own directory and collection |
| **Default System** | Named "default", auto-created on first run |
| **Data Storage** | Each system stored at `.ariadne/memories/{name}/` |
| **Manifest** | `manifest.json` records all memory system metadata |

### 4-Layer Memory Stack

Ariadne implements a hierarchical memory architecture for AI context:

| Layer | Purpose | Token Budget |
|-------|---------|--------------|
| **L0 Identity** | Core identity and preferences | ~100 tokens |
| **L1 Narrative** | Conversation summaries | ~500-800 tokens |
| **L2 On-Demand** | Current task context | ~200-500 tokens |
| **L3 Deep Search** | Full vector search | Unlimited |

See [docs/MemoryStack.md](docs/MemoryStack.md) for details.

### MCP Server

Ariadne exposes its capabilities as MCP tools for AI agents:

| Tool | Description |
|------|-------------|
| `ariadne_search` | Semantic vector search |
| `ariadne_ingest` | Document ingestion |
| `ariadne_graph_query` | Knowledge graph queries |
| `ariadne_stats` | System statistics |

See [docs/MCP.md](docs/MCP.md) for MCP server configuration.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Ariadne Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Files  │───▶│  Ingestors  │───▶│  Documents (Chunks) │  │
│  └─────────┘    └─────────────┘    └──────────┬──────────┘  │
│                                              │              │
│  ┌─────────┐    ┌─────────────┐    ┌──────────▼──────────┐  │
│  │  Query  │───▶│  ChromaDB   │◀───│  Vector Embeddings  │  │
│  └─────────┘    └─────────────┘    └─────────────────────┘  │
│        │                │                                     │
│        │         ┌──────▼──────┐                              │
│        └────────▶│   Search    │                              │
│                  └─────────────┘                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Memory Systems (Multiple Independent Stores)       │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │    │
│  │  │ default │  │research │  │personal │  ...        │    │
│  │  └─────────┘  └─────────┘  └─────────┘              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Is LLM API Required?

**Basic features (ingest + search) do NOT require LLM API:**
- Uses ChromaDB's built-in `all-MiniLM-L6-v2` model for vector generation
- All data stored locally, no network requests
- Semantic search based on vector similarity

**LLM API is optional for:**
- Knowledge graph entity recognition and relation extraction (P3)
- LLM-enhanced semantic reranking (P2)
- Smart dynamic chunking (P2)

---

## Basic Usage

### Invocation

```bash
# CLI (recommended)
python -m ariadne.cli [COMMAND] [OPTIONS]

# GUI
python -m ariadne.cli gui
```

### Quick Start

```bash
# 1. List all memory systems
python -m ariadne.cli memory list

# 2. Create a new memory system
python -m ariadne.cli memory create "Research Notes"

# 3. Ingest files to specific memory system
python -m ariadne.cli ingest ./papers/ -r -m "Research Notes"

# 4. Search
python -m ariadne.cli search "AI ethics" -m "Research Notes"

# 5. View stats
python -m ariadne.cli info --stats -m "Research Notes"

# 6. Launch GUI
python -m ariadne.cli gui
```

---

## CLI Command Reference

### 1. memory — Memory System Management

```bash
ariadne memory [COMMAND]
```

#### Subcommands

| Command | Description |
|---------|-------------|
| `list` | List all memory systems |
| `create <name>` | Create new memory system |
| `rename <old> <new>` | Rename system |
| `delete <name>` | Delete memory system |
| `merge <sources...> <new>` | Merge multiple systems |
| `info [name]` | View system info |
| `clear [name]` | Clear all documents |

#### Examples

```bash
# List all memory systems
ariadne memory list
# Output:
#    default: 42 documents
#      research: 156 documents
#      personal: 28 documents

# Create new memory system
ariadne memory create "My Research" -d "Academic papers and notes"

# Rename
ariadne memory rename "My Research" "Academic"

# Delete (requires confirmation)
ariadne memory delete "Old Notes"

# Delete (skip confirmation)
ariadne memory delete "Old Notes" --yes

# Merge multiple systems
ariadne memory merge research personal "All Knowledge"

# Merge and delete originals
ariadne memory merge research personal "All Knowledge" --delete

# View system info
ariadne memory info research

# Clear documents
ariadne memory clear research --yes
```

---

### 2. ingest — File Ingestion

```bash
ariadne ingest <PATH> [OPTIONS]
```

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--recursive` | `-r` | flag | False | Recursive subdirectories |
| `--verbose` | `-v` | flag | False | Verbose output |
| `--batch-size` | `-b` | int | 100 | Batch size |
| `--memory` | `-m` | str | default | Target memory system |

#### Examples

```bash
# Ingest to default system
ariadne ingest ./notes.md

# Ingest to specific system
ariadne ingest ./papers/ -r -m "Research"

# Verbose output
ariadne ingest ./docs/ -r -v

# Specify batch size
ariadne ingest ./books/ -b 50 -m "Books"
```

---

### 3. search — Semantic Search

```bash
ariadne search <QUERY> [OPTIONS]
```

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--top-k` | `-k` | int | 5 | Number of results |
| `--verbose` | `-v` | flag | False | Show metadata |
| `--memory` | `-m` | str | default | Memory system to search |

#### Examples

```bash
# Basic search
ariadne search "machine learning"

# More results
ariadne search "deep learning" -k 10

# Verbose output
ariadne search "neural networks" -v

# Search specific system
ariadne search "religion ethics" -m "Research"
```

---

### 4. info — System Information

```bash
ariadne info [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--stats` | Show document statistics |
| `--memory` | Specify memory system |

#### Examples

```bash
ariadne info
ariadne info --stats
ariadne info --stats -m "Research"
```

---

### 5. gui — Graphical Interface

```bash
ariadne gui
```

Launch the full GUI with all CLI features.

---

### 6. rag — RAG Pipeline

```bash
ariadne rag [COMMAND]
```

#### Subcommands

| Command | Description |
|---------|-------------|
| `search <QUERY>` | Hybrid search with citations |
| `rebuild-index` | Rebuild BM25 index |
| `health` | Check RAG component health |

#### Examples

```bash
# Hybrid search with citations
ariadne rag search "What is the main topic?"

# Rebuild BM25 index
ariadne rag rebuild-index

# Check health
ariadne rag health
```

---

### 7. realtime — Real-time Agent Memory Vectorization

```bash
ariadne memory [COMMAND]
```

#### Subcommands

| Command | Description |
|---------|-------------|
| `watch <PATH>` | Start real-time monitoring of agent memory directory |
| `ingest-observation <FILE>` | Manually ingest an agent memory file (e.g., MEMORY.md) |
| `realtime-status` | Show real-time vectorization status |
| `realtime-config` | Configure real-time vectorization settings |

#### Examples

```bash
# Start watching a directory for agent memory files
ariadne memory watch /home/user/.workbuddy/memory/

# Manually ingest a specific memory file
ariadne memory ingest-observation /home/user/.workbuddy/memory/2026-04-28.md

# Check real-time vectorization status
ariadne memory realtime-status

# Configure platform and debounce interval
ariadne memory realtime-config --platform workbuddy --debounce 60

# Stop watching (via Web UI or MCP tool)
```

#### Platform Adapters

| Platform | Description |
|----------|-------------|
| WorkBuddy | WorkBuddy memory files (MEMORY.md, daily logs) |
| OpenClaw | OpenClaw session memory files |
| Cursor | Cursor AI agent memory files |
| Windsurf | Windsurf IDE memory files |
| Generic | Generic memory files (any text format) |

#### Configuration

Real-time vectorization settings can be configured via:
- CLI: `ariadne memory realtime-config`
- Web UI: Settings → Real-time Vectorization
- MCP: `ariadne_realtime_config` tool

---

### 8. advanced — Advanced Features

```bash
ariadne advanced [COMMAND]
```

#### Subcommands

| Command | Description |
|---------|-------------|
| `summarize [query]` | Generate summary |
| `graph [-f FORMAT]` | Export knowledge graph |
| `graph-enrich` | Enrich graph with LLM entity extraction |

#### Examples

```bash
# Generate summary
ariadne advanced summarize "AI ethics"

# Export graph as DOT
ariadne advanced graph -f dot -o graph.dot

# Export graph as Mermaid
ariadne advanced graph -f mermaid -o graph.mmd

# Enrich graph with LLM
ariadne advanced graph-enrich
```

---

## GUI Usage

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  File  Memory Systems                                              │
├──────────────────────────────────────────────────────────────────────┤
│  Ariadne v0.1.0                                                    │
├──────────────────────────────────────────────────────────────────────┤
│  Memory System: [Research ▼]  [Refresh] [New] [Rename] [Delete]    │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┬─────────────────┬─────────────────┐           │
│  │ Ingest / 摄入   │ Search / 搜索   │ Info / 信息     │           │
│  └─────────────────┴─────────────────┴─────────────────┘           │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  [Tab Content]                                               │   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────┤
│  Ready                                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Features

#### Memory System Management (Memory Systems Tab)

| Action | Description |
|--------|-------------|
| **Dropdown** | Switch current memory system at top |
| **Refresh** | Refresh system list and stats |
| **New** | Create new memory system |
| **Rename** | Rename current system |
| **Delete** | Delete current system |
| **Merge** | Merge multiple systems |

#### Ingest Tab

| Action | Description |
|--------|-------------|
| **Add Files** | Add single or multiple files |
| **Add Folder** | Add folder (recursive supported) |
| **Remove Selected** | Remove selected files |
| **Clear All** | Clear file list |
| **Ingest All** | Start ingesting all files |

**Options:**
- ☑ Recursive - Include subdirectories
- ☑ Verbose - Verbose output

#### Search Tab

| Action | Description |
|--------|-------------|
| **Search box** | Enter query, press Enter to search |
| **Results (k)** | Adjust number of results |
| ☑ Show metadata - Show document metadata |

#### Info Tab

| Action | Description |
|--------|-------------|
| **Refresh Info** | Refresh system info |
| **View All Systems** | View all system list |
| **Clear This System** | Clear current system documents |

---

## Tips & Tricks

### 1. Multi-Memory Workflow

```bash
# Create independent systems for different projects
ariadne memory create "PhD Research" -d "Dissertation materials"
ariadne memory create "Trading Notes" -d "Crypto and stock analysis"
ariadne memory create "Language Learning"

# Categorized ingestion
ariadne ingest ./papers/ -r -m "PhD Research"
ariadne ingest ./charts/ -m "Trading Notes"
ariadne ingest ./vocabulary/ -m "Language Learning"
```

### 2. System Merging

```bash
# Merge multiple systems into one
ariadne memory merge "old_notes" "temp" "consolidated"

# Merge and delete originals (cleanup)
ariadne memory merge old_notes temp archive --delete
```

### 3. Data Backup

```bash
# Backup entire memory store
cp -r .ariadne/memories .ariadne/memories_backup

# Export specific system
ariadne memory export research ./backup/research_memory
```

### 4. Performance Optimization

| Scenario | Recommendation |
|----------|----------------|
| Large files | Use `-b 200` to increase batch size |
| First ingestion | Use `-r -v` to see processing progress |
| Fast search | Keep systems lean, periodically clean unused docs |

### 5. Shell Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc

# Core commands
alias ariadne='python -m ariadne.cli'
alias ari='python -m ariadne.cli'

# Memory system operations
alias ari-list='ariadne memory list'
alias ari-new='ariadne memory create'
alias ari-del='ariadne memory delete'

# Quick operations
alias ari-info='ariadne info --stats'
alias ari-ingest='ariadne ingest'
alias ari-search='ariadne search'

# Usage examples
ari-list
ari-new "My Project"
ari-info -m "My Project"
ari-ingest ./notes.md -m "My Project"
ari-search "query" -m "My Project"
```

### 6. GUI Shortcuts

| Action | Shortcut |
|--------|----------|
| Search | Enter (in search box) |
| Add files | Ctrl+O |
| Exit | Ctrl+Q |

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| "No supported files found" | Check if file extensions match supported list |
| No search results | Verify files were ingested successfully (`ariadne info --stats`) |
| Encoding error | Ensure file is UTF-8 encoded |
| Memory system not found | Use `memory create` to create new system |
| Cannot delete default system | Default system cannot be deleted by design |

### Reset

```bash
# Clear specific system
ariadne memory clear <system_name> --yes

# Delete and recreate
ariadne memory delete <system_name> --yes
ariadne memory create <system_name>
```

### Data Location

```bash
# Default data directory (under project root)
.ariadne/memories/

# Structure
.ariadne/memories/
├── manifest.json          # System metadata
├── default/              # Default memory system
│   └── (chroma db files)
├── research/             # Research memory system
│   └── (chroma db files)
└── ...
```

---

## Related Links

- [README.md](README.md) - Project introduction
- [Architecture](README.md#architecture) - Architecture design
- [Roadmap](README.md#roadmap) - Development roadmap

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
