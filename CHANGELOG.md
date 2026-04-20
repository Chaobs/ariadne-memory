# Changelog

All notable changes to Ariadne will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-04-20

### Added

- **D3.js Interactive Knowledge Graph** — Force-directed graph with zoom/pan/drag
  - Color-coded entity types (Person/Organization/Location/Concept/Technology/Event)
  - Node click to show detail panel
  - Adjustable max nodes (20/50/100/200)
  - Interactive legend with type colors

- **Theme Toggle** — Dark/Light mode switch (stored in localStorage)
  - Full dark theme with custom CSS variables
  - Toggle button in sidebar footer

- **Upload Progress Bar** — Visual feedback during file ingestion

- **Responsive Mobile Layout** — Adapts to screens < 768px and < 480px

- **`ariadne-web.bat`** — New Windows shortcut script to launch Web UI
  - `ariadne-web.bat` — Default port 8770
  - `ariadne-web.bat 8080` — Custom port

- **`ariadne-web.sh`** — New Unix shell script for Linux/macOS
  - `./ariadne-web.sh` — Default port 8770
  - `./ariadne-web.sh <port>` — Custom port
  - `./ariadne-web.sh --dev` — Development mode (Vite + FastAPI)
  - `./ariadne-web.sh --help` — Full help

- **`SCRIPTS.md`** — Documentation for all shortcut scripts (Windows + Unix)

### Changed

- **Graph page** — Replaced static list view with full D3Graph component
- **Ingest page** — Added animated progress bar during file upload
- **Settings page** — Theme toggle button visible in sidebar footer

## [0.6.0] - 2026-04-20

### Added

- **Web UI (Phase 2 Alpha)** — React + FastAPI modern graphical interface
  - `ariadne web run`: Start the web UI server on http://127.0.0.1:8770
  - `ariadne web info`: Show web UI status and configuration
  - React SPA frontend with 6 pages: Home, Search, Memory, Ingest, Graph, Settings
  - Full REST API coverage: memory CRUD, file ingestion, semantic/RAG search, knowledge graph, LLM config
  - Multi-language support (8 languages)
  - React + Vite + TypeScript frontend with react-router-dom and axios

- **Web Optional Dependencies**: `fastapi>=0.100.0`, `uvicorn>=0.23.0`, `pydantic>=2.0.0`

### Changed

- **Version**: Bumped from 0.5.0 to 0.6.0

## [0.5.0] - 2026-04-20

### Added

- **RAG Pipeline**: Complete Retrieval-Augmented Generation infrastructure
  - `ariadne/rag/` package with 6 new modules
  - `BM25Retriever`: Keyword search via rank-bm25 (pure Python, no extra model)
  - `HybridSearch`: Combines vector + BM25 via Reciprocal Rank Fusion (RRF)
  - `Reranker`: Cross-encoder reranking (ms-marco-MiniLM-L-6-v2) with heuristic fallback
  - `CitationGenerator`: Extracts highlighted excerpts with multiple output formats
  - `RAGEngine`: Unified pipeline orchestrator with timing, health checks, warm-up
  - Lazy initialization — models only loaded when needed
  - Graceful degradation: if cross-encoder unavailable, uses heuristic reranking

- **RAG CLI commands** (`ariadne rag`):
  - `ariadne rag search` — Hybrid search with citations, scoring, and timing
  - `ariadne rag rebuild-index` — Rebuild BM25 index after ingesting documents
  - `ariadne rag health` — Check health of all RAG components

- **RAG optional dependencies**: `rank-bm25` + `sentence-transformers` (separate install)

- **GUI Graph Enrichment**: Added "Enrich Graph" button to Advanced tab
  - `_do_enrich_graph()` method for LLM entity extraction
  - `_update_graph_status()` method to display entity/relation counts
  - Multi-language support (en/zh_CN/zh_TW/fr)

### Fixed

- **GUI Info panel refresh**: `_update_info()` now correctly handles DISABLED state
- **JSON/TXT encoding**: Robust multi-encoding detection (utf-8-sig → utf-8 → gb18030 → latin-1)
- **Memory rename/import**: ChromaDB collection migration for Windows compatibility
- **GUI Enrich Graph import error**: Removed invalid `_compute_doc_id` import from store.py

### Changed

- **Vendor dependencies**: Complete package localization with 24 whl files
  - Added: typer, rich, beautifulsoup4, ebooklib, Pillow, markitdown, oletools, lxml, six
  - All whl files extracted for direct Python import
  - Added `vendor/download_deps.py` and `vendor/extract_whl.py` scripts

- **Version**: Bumped from 0.4.0 to 0.5.0

## [0.4.0] - 2026-04-20

### Added

- **MarkItDown integration**: Universal ingestor powered by Microsoft's markitdown library
  - Supports 22+ formats including HTML, RSS, Jupyter notebooks, Outlook MSG, RTF, ODF
  - Automatic fallback for any format not covered by native ingestors
  - Header-aware Markdown chunking with H1 context preservation
  - `MarkItDownIngestor` class with lazy-loaded markitdown dependency
  - Priority resolution: native ingestors first → markitdown preferred → markitdown fallback → BinaryIngestor

- **Typer CLI**: Complete rewrite from Click to Typer + Rich
  - Type-hint driven CLI with automatic help generation
  - Rich-powered beautiful terminal output (panels, tables, progress bars)
  - Shell completion support (`--install-completion`)
  - All existing commands preserved with identical functionality
  - `ariadne memory merge` now uses `--into` flag for target name

- **Deferred deletion**: Mark-and-batch deletion for VectorStore
  - `delete_doc(doc_id)` marks documents for deferred deletion
  - `flush_deletes()` executes batch deletion in a single operation
  - Auto-flush when pending deletes exceed threshold (50)
  - Context manager support (`with VectorStore() as store:`)
  - Avoids SQLite lock contention from frequent small deletions

- **SourceType enum expansion**: Added 10 new source types
  - `EPUB`, `IMAGE`, `OCR`, `ACADEMIC`, `WEB`, `EMAIL`, `VIDEO`, `AUDIO`, `BINARY`, `MARKITDOWN`
  - All ingestors now use their correct `SourceType` instead of `UNKNOWN`

### Changed

- **`get_ingestor()` factory**: Unified resolution logic across CLI, GUI, and MCP
  - 3-tier priority: native → markitdown preferred → markitdown fallback → binary
  - Graceful degradation when markitdown is not installed

- **GUI ingestion**: Now uses `get_ingestor()` factory instead of hardcoded `INGESTORS` dict
  - Directory scanning uses expanded `SCAN_EXTENSIONS` set (61 formats)
  - Consistent behavior between CLI and GUI

- **Dependencies**: 
  - `click` → `typer>=0.9.0` (Click is still a transitive dependency)
  - Added `rich>=10.11.0` for terminal formatting
  - Added `markitdown>=0.1.0` for universal format support

- **Version**: Bumped from 0.3.0 to 0.4.0

## [0.3.0] - 2026-04-19

### Added

- Third-party library localization (vendor directory)
- Data directory migration to project root (.ariadne/)
- Summarize bug fix (JSON format string escaping)
- Memory export/import functionality
- BinaryIngestor for binary file handling
- Quick start scripts (ariadne-cli/gui .bat + .sh)
- Japanese locale support (8 languages total)
- config.sample.json with 9 LLM templates

## [0.2.0] - 2026-04-18

### Added

- Multi-memory system support (CRUD, merge, rename)
- LLM integration (DeepSeek, Claude, Qwen, Gemini, etc.)
- Knowledge graph extraction and visualization
- Multi-language i18n support (7 UN languages + Japanese)
- Advanced features (summarize, graph, export)
- MCP Server implementation

## [0.1.0] - 2026-04-17

### Added

- Initial release
- Core ingestion: Markdown, Word, PPT, PDF, TXT, Excel, CSV
- Semantic search with ChromaDB
- Tkinter GUI
- CLI with Click
