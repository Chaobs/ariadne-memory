# Changelog

All notable changes to Ariadne will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.2] - 2026-04-25

### Fixed

#### Web Server Graceful Shutdown (Windows)

- **CMD 窗口关闭后端进程残留** — 当运行 Web 后端的 CMD 窗口被关闭（点击 X 按钮/Alt+F4/系统关机）时，Python 进程被操作系统立即终止，uvicorn 子进程残留并持续占用端口
- **修复方案**: 在 `run_server` 中注册 Windows 控制台事件处理器（`SetConsoleCtrlHandler`）拦截 `CTRL_CLOSE_EVENT` 和 `CTRL_SHUTDOWN_EVENT`，配合 `atexit.register` 和 Unix `SIGTERM/SIGINT` 信号处理器，实现三层保护：
  1. **Windows 控制台事件** → `_windows_ctrl_handler` → `_graceful_shutdown` → `kernel32.ExitProcess(1)`
  2. **Unix 信号** → `_unix_signal` → `_graceful_shutdown` → `session_log.shutdown()`
  3. **atexit fallback** → `_graceful_shutdown`（覆盖 signal handler 未捕获的退出路径）
- 修复后关闭 CMD 窗口时，后端进程树被完整清理，端口自动释放，无需手动 `taskkill` 或等待超时
- `ariadne/web/api.py` — `run_server` 函数重写，新增 `_graceful_shutdown` / `_windows_ctrl_handler` / `_unix_signal`

## [0.7.1] - 2026-04-25

### Fixed

#### LLM Wiki — Bug Fixes & UX Improvements

1. **`Initialized Project` / `Save to Recent` 无响应** — `POST /api/wiki/projects/save` 从 query param 改为 JSON body，与前端请求匹配
2. **`Initialize Wiki` API 422 错误** — 确认 `POST /api/wiki/init` 接受完整的 JSON body，前端请求格式统一
3. **Project Directory 目录选择器** — 新增服务端文件系统浏览 API `GET /api/wiki/fs/browse`，前端实现 `FsPicker` 弹窗组件，支持目录和文件两种模式，Windows 盘符切换，手动路径输入
4. **Ingest Source File 文件选择器** — 摄入源文件输入框旁增加 📂 图标，点击打开文件选择器，直接选取文件路径，无需手动输入
5. **docx/pdf 等二进制格式读取失败** — `read_file_safe()` 新增 markitdown 提取分支，支持 `.docx .doc .pdf .xlsx .pptx .odt .epub` 等 Office/二进制格式，编码四级回退（utf-8-sig → utf-8 → gb18030 → latin-1）
6. **LLM 401 错误提示** — Ingest 和 Query 失败时检测 401 状态码，显示明确的配置指引（Settings → LLM Configuration）
7. **帮助按钮** — 标题栏增加 `❓ 帮助` 按钮，弹窗内含完整操作教学（快速开始、LLM 配置、文件格式、Tab 说明、CLI 等价命令）
8. **Tab 按钮统一样式** — Overview / Ingest / Query / Lint / Pages / Log 六个标签页按钮从 `tab-btn` 改为 `btn-primary`（选中）/ `btn-secondary`（未选中），与页面其余按钮风格一致
9. **最近项目下拉菜单** — 加载历史 Wiki 项目列表，点击一键切换，并显示条目数
10. **保存反馈** — Save to Recent 操作完成后显示 ✓ 已保存 / ✗ 保存失败 短暂提示

### Changed
- `ariadne/web/wiki_api.py` — 新增 `WikiSaveProjectRequest` Pydantic model；新增 `GET /api/wiki/fs/browse` 文件系统浏览端点
- `ariadne/wiki/builder.py` — `read_file_safe()` 重写，支持 markitdown 提取 Office/PDF 格式，编码四级回退
- `ariadne/web/frontend/src/pages/Wiki.tsx` — 全面重写（~640 行），整合以上所有改进
- `ariadne/web/frontend/src/api/ariadne.ts` — 添加 `wikiApi.fsBrowse()` 方法；修复 `saveProject` 请求头
- `ariadne/web/frontend/src/api/sse.ts` — 将 `sessionId` 通过 `getSessionId()` 公开，修复私有属性访问错误
- `ariadne/web/frontend/src/components/Observations.tsx` — 修复 `react-i18next` 依赖引用错误；类型导入改为 `import type`
- `ariadne/web/frontend/src/pages/Session.tsx` — 修复未使用的 `useEffect` 导入



### Added

#### LLM Wiki — Web UI Integration
- **Wiki Page** (`ariadne/web/frontend/src/pages/Wiki.tsx`) — Complete Web UI tab with 6 sub-tabs:
  - **Overview** — Project stats, initialization form, overview content
  - **Ingest** — Source file ingestion with two-step CoT pipeline (file path, language selector, progress indicator)
  - **Query** — Natural language Q&A with wiki citation, optional save-to-wiki
  - **Lint** — Structural + semantic health check (orphan pages, broken links, cross-reference analysis)
  - **Pages** — Browsable page list with type-colored badges, content preview panel
  - **Log** — Operation log viewer
- **Wiki API Client** (`ariadne/web/frontend/src/api/ariadne.ts`) — TypeScript interfaces and fetch wrappers for all 11 Wiki API endpoints
- **Wiki i18n** (`ariadne/web/frontend/src/i18n.ts`) — Full 8-language translations for all Wiki UI strings
- **Wiki Navigation** (`ariadne/web/frontend/src/components/Layout.tsx`) — Sidebar nav item with 📖 icon
- **Wiki Routes** (`ariadne/web/frontend/src/App.tsx`) — `/wiki` route registered with React Router
- **Wiki MCP Refactoring** (`ariadne/mcp/tools.py`) — Refactored WikiIngest/List/Lint tools with helper functions, language parameter, WikiProject compatibility fixes

#### Pytest Test Suite (115 tests)
- **`test_wiki_models.py`** — 26 tests: WikiPage, WikiProject, YAML frontmatter (with/without trailing newline), slug generation, to_yaml/from_yaml roundtrip, validation
- **`test_wiki_builder.py`** — 43 tests: file I/O (create/overwrite/append), block parsing (---FILE: / ---END FILE---), LLM output parsing, SHA256 caching, incremental ingestion, index/overview generation
- **`test_wiki_linter.py`** — 35 tests: structural lint (orphan pages, broken links, no-outlinks) with mock LLM, semantic lint with mock LLM (CoT scoring, entity/concept validation)
- **`test_wiki_ingestor.py`** — 4 tests: two-step CoT pipeline, source truncation (60KB limit)
- **`test_wiki_obsidian.py`** — 7 tests: Obsidian vault import, wikilink/concealedTag/highlight/blockquote/tag conversions
- **`tests/conftest.py`** — Wiki fixtures: `sample_wiki_project`, `sample_wiki_pages`, `mock_llm_responses`, `project_path`
- **`tests/conftest_wiki.py`** — Wiki-specific fixtures and utilities

#### Documentation
- **`docs/FEATURE_DEPENDENCIES.md`** — Feature dependency guide with 3-tier architecture (online/LLM/local), 10 module dependency tables, scenario-based usage guide, quick reference matrix, API key security best practices
- **README** — Added pytest test badge, Testing section (5 suites), `FEATURE_DEPENDENCIES.md` to docs list, fixed duplicate `plugins/` directory entry in Architecture tree

### Changed

- **`pyproject.toml`** — Added pytest `[tool.pytest.ini_options]` configuration with `testpaths`, `python_files`, `python_classes`, `python_functions`, `asyncio_mode`, `filterwarnings`, `timeout`
- **`ariadne/wiki/models.py`** — Fixed YAML frontmatter regex to handle files without trailing newline (`r'\n---\n'` → `r'\n---\n|\n---\r\n|\n---$'`)
- **`ariadne/wiki/builder.py`** — Fixed `parse_file_blocks` infinite loop (JavaScript `list.length` → Python `len(lines)`); Fixed `read_wiki_page` body extraction regex (`r'\n---\n'` instead of `r'\n---\r\n'`)
- **`ariadne/wiki/obsidian.py`** — Made `_extract` abstract method concrete with default implementation; Fixed `Document(analysis=...)` parameter name
- **`tests/test_wiki_ingestor.py`** — Removed duplicate `import pathlib` that shadowed module-level import and caused `UnboundLocalError`
- **README.md** — Removed duplicate `plugins/` directory block in Architecture tree; Updated GitHub release line from v0.6.2 to v0.6.3
- **README_CN.md** — Updated GitHub release line from v0.6.2 to v0.6.3

## [0.7.0] - 2026-04-22

### Added

#### MCP Enhancements (WAL + Schema Validation)
- **WAL Audit Logger** — Complete operation audit trail for MCP server
  - SQLite-backed Write-Ahead Log
  - Operation metrics and statistics
  - Cache invalidation tracking
  - Automatic log rotation
  - Location: `ariadne/mcp/wal.py`

- **Parameter Schema Validation** — JSON Schema-based validation for MCP tools
  - Required field checking
  - Type validation (string, number, integer, boolean, array, object)
  - Enum validation
  - Range constraints (min/max)
  - Pattern matching (regex)
  - Location: `ariadne/mcp/validation.py`

- **Cache Invalidation Detection** — inode/mtime based cache management
  - File modification time monitoring
  - Inode tracking
  - TTL-based expiration
  - Automatic invalidation on source file changes
  - Location: `ariadne/mcp/cache.py`

#### 4-Layer Memory Stack
- **L0 Identity Layer** (~100 tokens) — Core identity and preferences
- **L1 Narrative Layer** (~500-800 tokens) — Conversation summaries
- **L2 On-Demand Layer** (~200-500 tokens) — Contextual retrieval
- **L3 Deep Search Layer** — Full vector search integration
- Wake-up mechanism for layer activation
- Automatic context generation for LLM prompts
- Location: `ariadne/memory/layers.py`

#### Knowledge Graph Temporal Enhancement
- **valid_from / valid_to fields** — Time-based fact validity
  - Entity temporal validity
  - Relation temporal validity
  - Temporal queries (`get_neighbors_temporal`, `get_temporal_entities`)
  - Historical fact tracking
  - Location: `ariadne/graph/models.py`, `ariadne/graph/storage.py`

#### Closet Index (AAAK Format)
- **Almost All Answer Key** — Compressed index for fast drawer lookup
- LLM-friendly format: `topic|entities|→drawer_ids`
- Fast topic/entity to drawer mapping
- Inverted index for efficient lookups
- Location: `ariadne/memory/closet.py`

#### Auto-Save Hook System
- **StopHook** — Automatic save after N messages (default: 15)
- **PreCompactHook** — Save before context compression
- **SessionStart/SessionEnd Hooks** — Save on session boundaries
- **IdleHook** — Save after idle period (default: 5 minutes)
- **Claude Code Integration** — Tool usage tracking, file modification detection
- Location: `ariadne/plugins/autosave.py`

### Changed

- **MCP Server** — Integrated WAL, validation, and cache modules
- **Memory Package** — Added layers.py and closet.py exports
- **Plugins Package** — Added autosave.py exports
- **Graph Storage** — Extended schema with temporal fields

## [0.6.2] - 2026-04-20

### Added

- **SSE Real-time Ingestion Progress** — Server-Sent Events streaming for file ingestion
  - Real-time progress events (processing, success, error, skip, complete)
  - Per-file processing log with status indicators
  - Live progress bar with phase labels

- **Graph Export (6 formats)** — Download knowledge graph as multiple formats
  - HTML: Interactive standalone HTML page
  - Markdown (.md): Portable markdown document
  - Word (.docx): Microsoft Word document
  - SVG: Scalable vector graphic
  - JSON: Raw graph data
  - Mermaid: Mermaid flowchart diagram
  - PNG: Rasterized graph image (via Canvas API)

- **Graph Filtering** — Filter nodes by entity type (Person/Organization/Location/etc.)

- **Graph Node Search** — Search and highlight specific nodes in the graph

- **Graph Hover Highlighting** — Hovering a node highlights its connected edges

- **Web UI i18n** — 8-language internationalization support
  - English, 简体中文, 繁體中文, 日本語, Français, Español, Русский, العربية
  - Language switcher in sidebar footer and Settings page
  - RTL support for Arabic

- **Search Autocomplete** — Real-time search suggestions with keyboard navigation
  - Debounced (300ms) suggestion fetching
  - Arrow key navigation + Enter to select
  - Dropdown suggestions panel

### Changed

- **Graph Page** — Complete redesign with filter/search/export toolbar
- **Graph D3 Component** — Enhanced with shadow filters, connected edge highlighting
- **Ingest Page** — Real-time streaming instead of simulated progress

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
