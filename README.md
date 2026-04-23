# Ariadne · 阿里阿德涅

> Ariadne, in Greek mythology, was the goddess who helped Theseus navigate through the labyrinth, holding a ball of thread to guide his way back. 
> Just like our system - weaving in all your knowledge, it leads you through the maze of memory.

**Ariadne** is a cross-source AI memory and knowledge weaving system that ingests documents, conversations, and code from various sources into a searchable knowledge network.

**[中文版](README_CN.md)** | English Version

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](pyproject.toml)

---

## Table of Contents

- [Features](#features)
- [Supported Formats](#supported-formats)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Architecture](#architecture)
- [LLM Wiki](#llm-wiki)
- [Agent Integration](#agent-integration)
- [Roadmap](#roadmap)
- [Credits](#credits)
- [Third-party Licenses](#third-party-licenses)

---

## Features

| Feature | Description | Status |
|---------|-------------|--------|
| 🗂️ **Multi-source Ingestion** | Supports Markdown, Word, PPT, PDF, TXT, Mind Maps, Code and more | ✅ |
| 🔍 **Semantic Search** | Vector database-based semantic similarity search | ✅ |
| 🧠 **Persistent Memory** | ChromaDB local storage, your data stays with you | ✅ |
| 📁 **Multiple Memory Systems** | Create independent systems for different domains | ✅ |
| 🔗 **Knowledge Graph** | Auto-identify entities and relationships | ✅ |
| 🤖 **AI Enhancement** | Supports DeepSeek / Claude / Qwen / Gemini / Kimi / MiniMax / GLM / Grok | ✅ |
| 🧮 **System Merging** | Merge multiple memory systems | ✅ |
| 💾 **Export/Import** | Export/import memory systems for backup and sharing | ✅ |
| 📚 **Media Support** | EPUB/MOBI, Image OCR, Scanned PDF, Academic metadata | ✅ |
| 🔌 **MCP Server** | MCP tools interface for Claude Code / WorkBuddy / Cursor | ✅ |
| 🖥️ **Dual Interface** | CLI (Typer + Rich) + Web UI (React + FastAPI), both with full features | ✅ |
| 🕸️ **Web UI** | Modern React SPA with semantic search, memory management, D3 graph, settings | ✅ |
| 🕸️ **D3 Graph** | Interactive force-directed knowledge graph with zoom/pan/drag | ✅ |
| 🌙 **Dark Mode** | Toggle light/dark theme (stored in localStorage) | ✅ |
| 📱 **Responsive** | Mobile-friendly layout (adapts to <768px and <480px) | ✅ |
| 🌍 **Multi-language** | Supports 8 languages (zh_CN/zh_TW/ja/en/fr/es/ru/ar) | ✅ |
| 📝 **Smart Summarization** | LLM-driven multi-language summarization | ✅ |
| 📊 **Visualization** | Interactive knowledge graph (HTML / DOT / Mermaid) | ✅ |
| 📤 **Multi-format Export** | Markdown, HTML, Word, PDF export | ✅ |
| 📦 **Localized Dependencies** | Third-party packages bundled, version consistency | ✅ |
| 🎯 **Binary Support** | Auto-handle binary files, extract filenames as references | ✅ |
| 🔄 **Universal Ingestion** | markitdown support for HTML/RSS/Jupyter/RTF/ODF 22+ formats | ✅ |
| ⏱️ **Deferred Deletion** | Mark-batch delete to avoid SQLite lock contention | ✅ |
| 🔀 **RAG Pipeline** | Hybrid search (vector+BM25) + Reranking + Citations | ✅ |
| 📌 **Smart Citations** | Auto-generate highlighted document citations | ✅ |
| 🧠 **4-Layer Memory Stack** | L0 Identity + L1 Narrative + L2 On-Demand + L3 Deep Search | ✅ |
| 🔐 **WAL Audit Logging** | MCP operation audit trail with metrics | ✅ |
| ✅ **Schema Validation** | JSON Schema-based MCP parameter validation | ✅ |
| 🗄️ **Closet Index** | AAAK compressed index for fast drawer lookup | ✅ |
| ⏰ **Temporal KG** | Knowledge graph with valid_from/valid_to temporal support | ✅ |
| 💾 **Auto-Save Hooks** | Stop/PreCompact/Session hooks for automatic persistence | ✅ |
| 🤖 **Claude Code Integration** | Tool tracking, file modification, project context | ✅ |
| 📖 **LLM Wiki** | Karpathy-style persistent wiki with two-step CoT ingest, Q&A, lint | ✅ |

---

## Supported Formats

### Document Formats (Phase 1)

| Format | Extensions | Ingestor | Description |
|--------|-------------|----------|-------------|
| Markdown | `.md`, `.markdown` | `MarkdownIngestor` | Header-aware semantic chunking |
| Word | `.docx`, `.doc` | `WordIngestor` | Paragraph extraction with style hierarchy |
| PPT | `.pptx`, `.ppt` | `PPTIngestor` | Each slide as a chunk |
| PDF | `.pdf` | `PDFIngestor` | PyMuPDF text extraction, smart short-page merging |
| Plain Text | `.txt` | `TxtIngestor` | Paragraph chunking |
| Conversation | `.json` | `ConversationIngestor` | ChatGPT/Claude/DeepSeek JSON export |
| Mind Map | `.mm`, `.xmind` | `MindMapIngestor` | FreeMind/XMind format support |
| Code | `.py`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.js`, `.ts`, `.jsx`, `.tsx`, `.cs`, `.go`, `.rs`, `.rb`, `.php`, `.swift`, `.kt`, `.scala` | `CodeIngestor` | AST/regex function/class/docstring extraction |
| Excel | `.xlsx`, `.xls` | `ExcelIngestor` | Sheet/row extraction with cell notes |
| CSV | `.csv` | `CsvIngestor` | Header context preserved, row chunking |

### Media & Academic (Phase 4)

| Format | Extensions | Ingestor | Processing |
|--------|-------------|----------|------------|
| EPUB | `.epub` | `EPUBIngestor` | Metadata + chapter structure |
| Image | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp` | `ImageIngestor` | EXIF metadata extraction |
| OCR | Scanned PDF/Image | `OCRIngestor` | RapidOCR/Tesseract text recognition |
| BibTeX | `.bib` | `BibTeXIngestor` | Academic metadata parsing |
| RIS | `.ris` | `RISIngestor` | Academic citation data |
| Web | URL, `.html` | `WebIngestor` | Title/body/metadata, URL and local HTML |
| Email | `.eml`, `.mbox` | `EmailIngestor` | Header/body/attachment parsing |
| Video | `.mp4`, `.avi`, `.mkv`, `.mov` | `VideoIngestor` | Metadata + subtitle extraction |
| Audio | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg` | `AudioIngestor` | Metadata + transcription (Whisper) |

### Binary Files

| Format | Extensions | Ingestor | Processing |
|--------|-------------|----------|------------|
| Binary | `.exe`, `.dll`, `.so`, `.dylib`, `.bin`, `.dat`, `.iso`, `.apk`, `.ipa` etc. | `BinaryIngestor` | Filename, size, type metadata |

### Universal Format (via markitdown)

| Format | Extensions | Ingestor | Processing |
|--------|-------------|----------|------------|
| HTML | `.html`, `.htm` | `MarkItDownIngestor` | Markdown conversion + semantic chunking |
| RSS | `.rss`, `.xml` | `MarkItDownIngestor` | RSS/Atom feed parsing |
| Jupyter | `.ipynb` | `MarkItDownIngestor` | Code + output Markdown conversion |
| Outlook | `.msg` | `MarkItDownIngestor` | MSG email content extraction |
| RTF | `.rtf` | `MarkItDownIngestor` | Rich text format conversion |
| ODF | `.ods`, `.odt`, `.odp` | `MarkItDownIngestor` | OpenDocument format conversion |
| Other | Any unmatched format | `MarkItDownIngestor` | Auto markitdown conversion attempt |

---

## Quick Start

### Requirements

- Python 3.9+
- Recommended: Windows / macOS / Linux

### Installation

```bash
# Clone repository
git clone https://github.com/Chaobs/ariadne-memory.git
cd ariadne-memory

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -e .

# Or install core dependencies only
pip install -r requirements.txt
```

### Quick Commands

**Windows Shortcuts:**
```bash
# Double-click ariadne-cli.bat  — Command line interface
# Double-click ariadne-web.bat   — Modern Web UI (recommended)
```

**Linux / macOS:**
```bash
./ariadne-web.sh              # Default port 8770
./ariadne-web.sh 8080         # Custom port
./ariadne-web.sh --dev        # Development mode (Vite + FastAPI)
chmod +x ariadne-web.sh       # First-time only
```

**Or use Python directly:**
```bash
# Start Web UI (recommended)
python -m ariadne.cli web run

# Ingest a single file
python -m ariadne.cli ingest ./my_notes.md

# Ingest a directory (recursive)
python -m ariadne.cli ingest ./my_research/ -r

# Semantic search
python -m ariadne.cli search "Jewish-Christian ethical concepts"

# View system info
python -m ariadne.cli info --stats

# Create a new memory system
python -m ariadne.cli memory create "Research Notes"

# Ingest to specific memory system
python -m ariadne.cli ingest ./papers/ -r -m "Research Notes"

# Search in specific memory system
python -m ariadne.cli search "AI ethics" -m "Research Notes"

# Merge memory systems
python -m ariadne.cli memory merge old_notes temp --into "Consolidated"
```

### Python API

```python
from ariadne.ingest import MarkdownIngestor, PDFIngestor
from ariadne.memory import VectorStore

# Initialize storage
store = VectorStore()

# Ingest Markdown notes
docs = MarkdownIngestor().ingest("path/to/notes.md")
store.add(docs)

# Ingest PDF papers
docs = PDFIngestor().ingest("path/to/paper.pdf")
store.add(docs)

# Semantic search
results = store.search("AI ethics discussions", top_k=5)
for doc, score in results:
    print(f"[{score:.4f}] {doc.content[:200]}")
```

---

## CLI Usage

> For detailed usage guide, see [USAGE.md](USAGE.md).

### Command Overview

| Command | Description | Example |
|---------|-------------|---------|
| `ingest` | Ingest files or directories | `ariadne ingest ./notes.md` |
| `search` | Semantic search | `ariadne search "AI ethics"` |
| `info` | View system info | `ariadne info --stats` |
| `memory list` | List all memory systems | `ariadne memory list` |
| `memory create` | Create new system | `ariadne memory create "Research"` |
| `memory rename` | Rename system | `ariadne memory rename old new` |
| `memory delete` | Delete system | `ariadne memory delete old` |
| `memory merge` | Merge systems | `ariadne memory merge a b --into new` |
| `memory export` | Export system | `ariadne memory export research ./backup/` |
| `memory import` | Import system | `ariadne memory import ./backup/ imported` |
| `config show` | Show config | `ariadne config show` |
| `config set` | Set config | `ariadne config set llm.provider deepseek` |
| `config test` | Test LLM | `ariadne config test` |
| `config set-api-key` | Set API key | `ariadne config set-api-key deepseek sk-xxxxx` |
| `advanced summarize` | Generate summary | `ariadne advanced summarize "AI"` |
| `advanced graph` | Knowledge graph | `ariadne advanced graph -f dot` |
| `rag search` | RAG hybrid search | `ariadne rag search "query" -m default` |
| `rag rebuild-index` | Rebuild BM25 index | `ariadne rag rebuild-index` |
| `rag health` | RAG health check | `ariadne rag health` |
| `web run` | Launch web UI | `ariadne web run --port 8770` |
| `web info` | Web UI status | `ariadne web info` |

---

## Architecture

```
ariadne/
├── __init__.py              # Public API entry (auto-init vendor)
├── cli.py                   # CLI tool (Typer + Rich)
├── config.py               # Unified config system
├── paths.py                # Path management
├── advanced.py             # Advanced features (summary/visualization/export)
├── i18n.py                 # Multi-language support (8 languages)
├── logging.py              # Session logging with auto-rotation
├── models.py               # Shared data models
├── ingest/                 # Ingestion modules
│   ├── base.py             # BaseIngestor + Document model
│   ├── markdown.py         # Markdown ingestor
│   ├── word.py             # Word (.docx) ingestor
│   ├── ppt.py              # PowerPoint (.pptx) ingestor
│   ├── pdf.py              # PDF ingestor
│   ├── txt.py              # Plain text ingestor
│   ├── conversation.py     # Conversation history ingestor
│   ├── mindmap.py          # Mind map ingestor
│   ├── code.py             # Code comment ingestor
│   ├── excel.py            # Excel ingestor
│   ├── csv.py              # CSV ingestor
│   ├── binary.py           # Binary file ingestor
│   ├── epub.py             # EPUB ebook ingestor
│   ├── image.py            # Image/OCR ingestor
│   ├── academic.py         # BibTeX/RIS ingestor
│   ├── web.py              # Web page ingestor
│   ├── email.py            # Email ingestor
│   ├── media.py            # Video/audio ingestor
│   └── markitdown_ingestor.py  # Universal format via markitdown (22+ formats)
├── memory/                 # Vector memory storage
│   ├── store.py            # ChromaDB implementation + deferred deletion
│   ├── manager.py          # Multi-system manager + export/import
│   ├── layers.py           # 4-Layer Memory Stack (L0-L3)
│   └── closet.py           # Closet Index (AAAK format)
├── plugins/                # Plugin/Hook system
│   ├── registry.py         # IngestorRegistry (priority-based, decorator API)
│   ├── hooks.py            # HookManager (4 lifecycle hooks)
│   ├── autosave.py         # Auto-save hooks + Claude Code integration
│   ├── loader.py           # Plugin discovery (entry_points + directory scan)
│   └── __init__.py         # Public API (ingest_hook, on, ...)
├── llm/                    # LLM unified interface
│   ├── base.py             # BaseLLM abstract
│   ├── factory.py          # LLM factory + ConfigManager
│   ├── providers.py        # Provider implementations (9 providers)
│   ├── reranker.py         # Semantic reranking
│   └── chunker.py          # Smart chunking
├── graph/                  # Knowledge graph
│   ├── models.py           # Entity/Relation models
│   ├── extractor.py        # Entity/relation extraction
│   ├── storage.py          # NetworkX + SQLite storage
│   └── query.py            # Graph query interface
├── plugins/                # Plugin/Hook system
│   ├── registry.py         # IngestorRegistry (priority-based, decorator API)
│   ├── hooks.py            # HookManager (4 lifecycle hooks)
│   ├── loader.py           # Plugin discovery (entry_points + directory scan)
│   └── __init__.py         # Public API (ingest_hook, on, ...)
├── rag/                    # RAG Pipeline
│   ├── bm25_retriever.py   # BM25 retriever
│   ├── hybrid_search.py    # Hybrid search (vector + BM25, RRF fusion)
│   ├── reranker.py         # Cross-encoder reranker
│   ├── citation.py         # Citation generator
│   └── engine.py           # RAG engine
├── wiki/                   # LLM Wiki (Karpathy pattern)
│   ├── models.py          # WikiPage, WikiProject, LintResult models
│   ├── prompts.py        # Two-step CoT prompt builders
│   ├── builder.py        # File I/O, block parser, cache
│   ├── ingestor.py       # Two-step CoT ingest pipeline
│   ├── linter.py         # Structural + semantic lint
│   ├── query.py          # Wiki Q&A with citation
│   └── obsidian.py       # Obsidian vault import
├── mcp/                    # MCP Server
│   ├── server.py           # MCP Server core (stdio / HTTP)
│   ├── tools.py            # MCP Tools (4 tools)
│   ├── resources.py        # MCP Resources
│   ├── prompts.py          # MCP Prompts
│   ├── wal.py             # WAL Audit Logger
│   ├── validation.py      # Schema Validation
│   └── cache.py           # Cache Invalidation Detection
├── web/                    # Web UI (React + FastAPI)
│   ├── api.py              # FastAPI REST API (20+ endpoints)
│   ├── __init__.py         # Web entry point
│   ├── static/             # Deployed production build
│   └── frontend/           # React + Vite + TypeScript source
│       └── src/
│           ├── api/        # API client (ariadne.ts)
│           ├── components/ # Layout, theme, i18n
│           └── pages/      # Home/Search/Memory/Ingest/Graph/Settings
└── locale/                 # (removed — Web UI has its own i18n)

docs/                       # Documentation
├── AGENT_INTEGRATION.md   # Agent integration guide (Claude Code, Cursor, WorkBuddy)
├── MCP.md                 # MCP Server documentation
├── LLM_WIKI.md            # LLM Wiki feature guide (Karpathy pattern)
├── Ariadne-Memory-SKILL.md     # Agent Skill definition file (Claude Code, Cursor, etc.)
├── TEST_AND_EXTENSION_PLAN.md
├── AutoSave.md
├── Closet.md
└── MemoryStack.md

examples/                   # Configuration examples
└── mcp_config.json        # MCP client configuration template

.ariadne/                  # Project local data (not in Git)
├── config.json            # User config (API keys, not committed)
├── .env                   # Environment variables (optional)
├── memories/              # Memory systems
│   ├── manifest.json      # System registry
│   └── {name}/           # Each system's ChromaDB data
├── knowledge_graph.db     # Knowledge graph SQLite DB
├── logs/                  # Session logs (auto-rotated, 10 sessions)
└── chroma/               # ChromaDB default persistence

vendor/                    # Third-party packages
├── __init__.py             # Auto-init (HF_HOME / CHROMA_CACHE redirect)
├── packages/               # pip whl packages
├── models/                 # Local model cache (all-MiniLM-L6-v2)
└── cache/                  # Runtime cache (Chroma ONNX etc.)
```

---

## LLM Wiki

Based on [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), Ariadne provides a persistent, queryable knowledge base that grows organically from your source documents.

### Architecture

```
Raw Sources (immutable) → Wiki (LLM-generated) → Schema (rules & config)
```

### Three Core Operations

| Operation | Command | Description |
|-----------|---------|-------------|
| **Ingest** | `ariadne wiki ingest <file>` | Two-step CoT: analyze source → generate wiki pages |
| **Query** | `ariadne wiki query <question>` | Search wiki → LLM synthesizes answer with citations |
| **Lint** | `ariadne wiki lint` | Structural (orphan/broken links) + semantic (LLM) checks |

### Directory Structure

```
my-wiki/
├── raw/
│   ├── sources/       ← Drop source documents here
│   └── assets/       ← Images and attachments
├── wiki/
│   ├── index.md      ← Auto-generated topic index
│   ├── log.md        ← Ingest operation log
│   ├── overview.md   ← Wiki summary
│   ├── content/      ← Concept/entity pages
│   └── queries/      ← Archived Q&A sessions
├── schema.md         ← Wiki structure rules
└── purpose.md       ← Wiki goals and purpose
```

### CLI Quick Start

```bash
# Initialize a wiki project
ariadne wiki init my-wiki

# Ingest a source file (two-step CoT)
ariadne wiki ingest raw/papers/ml-survey.pdf -p my-wiki

# Ask a question
ariadne wiki query "What are the key findings?" -p my-wiki

# Health check
ariadne wiki lint -p my-wiki

# List all pages
ariadne wiki list -p my-wiki
```

### Obsidian Import

Import entire Obsidian vaults with syntax conversion:

```bash
ariadne wiki ingest-vault /path/to/obsidian/vault -p my-wiki
```

Converts: `[[wikilink]]` → markdown links, `==highlight==` → `**bold**`, preserves frontmatter and `#tags`.

### MCP Tools

For AI Agent integration:

| Tool | Description |
|------|-------------|
| `ariadne_wiki_ingest` | Ingest source with two-step CoT |
| `ariadne_wiki_query` | Query wiki with LLM synthesis |
| `ariadne_wiki_lint` | Structural + semantic health check |
| `ariadne_wiki_list` | List pages by type/tag |

See [docs/LLM_WIKI.md](docs/LLM_WIKI.md) for detailed documentation.

---

## Agent Integration

Ariadne supports multiple AI Agent integrations:

| Agent | Integration Method | Documentation |
|-------|-------------------|---------------|
| Claude Code | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#claude-code) |
| Cursor | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#cursor) |
| Windsurf | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#windsurf) |
| Claude Code | Skill + HTTP API | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#agent-skill) |
| Custom Agents | HTTP REST API | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#http-rest-api) |

### Quick Setup

**MCP Server (Claude Code / Cursor / Windsurf):**
```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.mcp.server", "--transport", "stdio"]
    }
  }
}
```

**Agent Skill:**
Copy `docs/Ariadne-Memory-SKILL.md` to your agent's skill directory (e.g., `~/.workbuddy/skills/ariadne-memory/SKILL.md`)

**HTTP API:**
Start Web UI: `python -m ariadne.cli web run`
Then access REST API at `http://localhost:8770`

---

## Roadmap

> **Current Phase**: Phase 2 — Web UI ✅ | Phase 3 — Plugin System ✅ | Phase 6 — Community & Iteration 🔄

### Phase 0 MVP ✅ **Completed**
- [x] Project skeleton and directory structure
- [x] 10 document format ingestors (Markdown/Word/PPT/PDF/TXT/Conversation/MindMap/Code/Excel/CSV)
- [x] ChromaDB vector storage layer
- [x] CLI tool (ingest / search / info)
- [x] Bilingual README (EN/CN)
- [x] Core data models (Document / Entity / Relation)
- [x] ChromaDB runtime verification
- [x] Unit tests for all ingestors
- [x] Batch ingestion with progress bar
- [x] **Tkinter GUI prototype** (replaced by Web UI)
- [x] Memory system CRUD management
- [x] Memory system export/import (CLI + GUI toolbar)
- [x] Data directory migrated to `.ariadne/` (not `~/.ariadne`)
- [x] Third-party library localization (vendor directory) + model cache

### Phase 1 RAG Pipeline ✅ **Completed**
- [x] LLM unified interface (DeepSeek / Claude / Qwen / ChatGPT / Gemini / Grok / Kimi / MiniMax / GLM)
- [x] `config.json` configuration management
- [x] LLM-enhanced semantic reranking (Reranker)
- [x] Smart dynamic chunking (SemanticChunker replacing fixed-length)
- [x] New providers: Kimi / MiniMax / GLM (9 total)
- [x] GUI LLM model switching
- [x] **Smart summarization fix** — Fixed JSON curly brace escaping in Summarize prompt

### Phase 2 Web UI ✅ **Completed**
- [x] `ariadne web run/info` CLI commands
- [x] FastAPI REST API (12+ endpoints covering all CLI/GUI functionality)
- [x] React + Vite + TypeScript SPA (6 pages: Home/Search/Memory/Ingest/Graph/Settings)
- [x] Vite dev server proxy for seamless API integration
- [x] **Beautiful graph visualization** — D3.js interactive knowledge graph
- [x] **Real-time ingestion progress** — SSE (Server-Sent Events) for live upload progress
- [x] **Dark/light theme toggle**
- [x] **Responsive mobile-friendly layout**
- [x] **Graph export** — HTML/Markdown/DOCX/SVG/JSON/Mermaid/PNG
- [x] **Graph filtering** — Filter by entity type (Person/Organization/etc.)
- [x] **Graph node search** — Search and highlight nodes
- [x] **Graph hover highlighting** — Connected edges highlight on hover
- [x] **Search autocomplete** — Real-time suggestions with keyboard navigation
- [x] **Web UI i18n** — 8 languages with language switcher in sidebar

### Phase 3 Knowledge Graph ✅ **Completed**
- [x] Entity recognition + relation extraction (LLM API)
- [x] NetworkX + SQLite graph database
- [x] Cross-source relationship queries
- [x] Knowledge timeline view
- [x] Interactive graph visualization (HTML/DOT/Mermaid)
- [ ] 🔨 **Knowledge system analysis** — Cross-memory system comparison, coverage analysis

### Phase 3.5 Plugin/Hook System ✅ **Completed**
- [x] `ariadne/plugins/` — IngestorRegistry + HookManager + PluginLoader
- [x] Dynamic ingestor registration (priority-based, decorator API)
- [x] 4 lifecycle hooks (before_ingest / after_ingest / before_search / after_search)
- [x] Plugin discovery via Python entry_points + directory scanning
- [x] Unified SCAN_EXTENSIONS from IngestorRegistry (61 built-in extensions)
- [x] Config support: `plugins` section in config.json

### Phase 4 Media & Academic Tools 🔄 **Partially Complete**
- [x] EPUB ebook ingestion
- [x] Image ingestion (metadata extraction)
- [x] Image / Scanned PDF OCR (pytesseract / RapidOCR)
- [x] Academic metadata (BibTeX / RIS)
- [x] Web link ingestion (URL crawling + local HTML)
- [x] Email ingestion (EML/MBOX parsing)
- [x] Video file ingestion (metadata + subtitle extraction)
- [x] Audio file ingestion (transcription via Whisper)
- [ ] 🔨 **Chat record ingestion** — QQ, WeChat, Feishu IM conversation parsing
- [ ] 🔨 **OCR + AV enhancement** — Non-text images/video via transcription models (Whisper/Vision LLM)
- [ ] 🔨 **OFD file support** — Chinese tax/invoice format (alternative to PDF)

### Phase 5 MCP Server ✅ **Completed**
- [x] AriadneMCPServer core (stdio / HTTP transport)
- [x] MCP Tools: `ariadne_search` / `ariadne_ingest` / `ariadne_graph_query` / `ariadne_stats`
- [x] MCP Resources: `collections` / `stats` / `config` / `graph`
- [x] MCP Prompts: `search` / `ingest` / `graph` / `context` / `compare`

#### Phase 5 Extended Features 🔨 **Planned**
- [ ] 🔨 **AI Agent Conversation Memory Real-time Vectorization** — When chatting with AI Agents (OpenClaw, Claude Code, Codex, Trae, WorkBuddy, QClaw, etc.), automatically vectorize conversation memories (like MEMORY.md) in real-time and ingest into the knowledge system, enabling permanent extended retrieval of conversation history. Reference MemPalace's session context management approach.

### v0.3.0 Enhancement ✅ **Completed**
- [x] Third-party library localization (vendor directory)
- [x] Model cache localization (all-MiniLM-L6-v2)
- [x] Binary file handling (extract filenames as knowledge references)
- [x] Extended LLM provider examples (config.sample.json with 9 templates)
- [x] Shortcut scripts (ariadne-cli.bat / ariadne-web.bat)
- [x] Japanese support (ja locale, 8 languages total)
- [x] .gitignore update (config.json / .ariadne not committed)

### Phase 6 Community & Iteration (Ongoing)
- [x] GitHub release v0.2.0 → v0.6.2
- [x] **Web UI (FastAPI + React)** — Modern cross-platform interface, replacing legacy Tkinter
- [x] **Real-time ingestion progress** — SSE for live upload progress
- [x] **Beautiful graph visualization** — D3.js interactive knowledge graph
- [x] **Web UI feature parity** — Memory clear/details, RAG params, entity query, DOT export, full config view
- [x] **Session logging** — `.ariadne/logs/` with auto-rotation
- [ ] 🔨 **Wiki pages and detailed documentation**
- [ ] 🔨 **Logo and icon design**
- [ ] 🔨 **Cloud backup & network query** (memory system cloud sync + real-time info retrieval)
- [ ] 🔨 **Auto-ingest from watch directory** — Background file monitoring + auto-ingest
- [ ] Versioned releases (v0.7.0+)
- [ ] HackerNews / Reddit posts
- [ ] Chinese community outreach (掘金 / 知乎 / CSDN)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Completed |
| 🔄 | Partially Complete |
| 🔨 | Planned / To Do |
| ⚡ | Current Priority |

---

## Credits

### Core Inspiration

**MemPalace** is one of the most important inspirations for Ariadne. MemPalace introduced the concept of "AI memory," demonstrating that local vector storage + semantic search can greatly enhance AI tool context capabilities.

> "Ariadne's pluggable ingestor and storage architecture is inspired by [MemPalace](https://github.com/MemPalace/mempalace). MemPalace is released under the MIT License."

### Third-party Licenses

This project uses the following open source components:

| Component | Version | License | Purpose |
|-----------|---------|---------|---------|
| [ChromaDB](https://github.com/chroma-core/chroma) | ≥0.4.0 | Apache 2.0 | Vector storage & retrieval |
| [Click](https://github.com/pallets/click) | ≥8.0.0 | BSD-3-Clause | CLI framework |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | latest | Apache 2.0 | Text embedding |
| **all-MiniLM-L6-v2** | - | Apache 2.0* | Default embedding model |
| [python-docx](https://github.com/python-openxml/python-docx) | ≥1.0.0 | MIT | Word document parsing |
| [python-pptx](https://github.com/scanny/python-pptx) | ≥0.6.21 | MIT | PPT parsing |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | ≥1.23.0 | AGPL-3.0 | PDF parsing |
| [openpyxl](https://foss.heptanodon.org/openpyxl/) | ≥3.1.0 | MIT | Excel parsing |
| [networkx](https://github.com/networkx/networkx) | ≥3.0 | BSD-3-Clause | Knowledge graph |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | ≥2.0.0 | MIT | Database ORM |
| [requests](https://github.com/psf/requests) | ≥2.31.0 | Apache 2.0 | HTTP requests |
| [PyYAML](https://github.com/yaml/pyyaml) | ≥6.0 | MIT | YAML parsing |
| [tqdm](https://github.com/tqdm/tqdm) | ≥4.65.0 | MIT | Progress bar |
| [Typer](https://github.com/tiangolo/typer) | ≥0.9.0 | MIT | CLI framework |
| [Rich](https://github.com/Textualize/rich) | ≥10.11.0 | MIT | Terminal beautification |
| [markitdown](https://github.com/microsoft/markitdown) | ≥0.1.0 | MIT | Universal document conversion |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | ≥4.12 | MIT | HTML parsing |
| [ebooklib](https://github.com/aerkalov/ebooklib) | ≥0.20 | AGPL-3.0 | EPUB parsing |
| [Pillow](https://github.com/python-pillow/Pillow) | ≥10.0 | HPND | Image processing |
| [lxml](https://github.com/lxml/lxml) | ≥6.0 | BSD-3-Clause | XML/HTML parsing |
| [oletools](https://github.com/decalage2/oletools) | ≥0.60 | Apache 2.0 | MSG file parsing |
| [six](https://github.com/benjaminp/six) | ≥1.17 | MIT | Python 2/3 compatibility |

**Note**: The all-MiniLM-L6-v2 model uses Apache 2.0 license, but training data includes MS MARCO and other non-commercial datasets. Please check relevant restrictions for commercial use.

---

## License

This project is open source under [MIT License](LICENSE).

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
