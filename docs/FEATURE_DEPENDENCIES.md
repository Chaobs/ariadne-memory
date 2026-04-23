# 功能依赖指南 — 联网·本地·LLM 能力矩阵

> 本文档说明 Ariadne 各模块的运行依赖，帮助用户在离线环境或无 API Key 时了解哪些功能可用、哪些受限。

---

## 一、依赖层次总览

```
┌─────────────────────────────────────────────────────────┐
│                     联网层（Internet）                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  WebIngestor  │  │  LLM Providers  │  │  FastAPI Web   │  │
│  │  (requests)   │  │  (9家云服务API)  │  │   (uvicorn)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     LLM 层（LLM API）                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Wiki模块   │  │  GraphEnricher │  │  Summarizer  │  │
│  │  ingest/     │  │  EntityExtractor│  │  (advanced)  │  │
│  │  query_wiki  │  │  RelationExtr. │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     本地层（Local Only）                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   VectorStore │  │   GraphStorage │  │  RAG (BM25)  │  │
│  │   (ChromaDB)  │  │   (JSON文件)   │  │  (rank_bm25)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  插件/Config  │  │   MCP Server   │  │  文档摄取器   │  │
│  │  (纯Python)   │  │  (纯Python)    │  │ (除Web外)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 二、模块依赖明细

### 2.1 `llm/` — LLM 驱动层

| 类 / 函数 | 依赖类型 | 外部依赖 | 说明 |
|-----------|---------|---------|------|
| `DeepSeekLLM` | 🔴 联网 + 🔴 LLM | `api.deepseek.com` | DeepSeek 官方 API |
| `OpenAILLM` | 🔴 联网 + 🔴 LLM | `api.openai.com` | OpenAI GPT 系列 |
| `AnthropicLLM` | 🔴 联网 + 🔴 LLM | `api.anthropic.com` | Claude 3/3.5 |
| `QwenLLM` | 🔴 联网 + 🔴 LLM | `dashscope.aliyuncs.com` | 阿里通义千问 |
| `GeminiLLM` | 🔴 联网 + 🔴 LLM | `generativelanguage.googleapis.com` | Google Gemini |
| `GrokLLM` | 🔴 联网 + 🔴 LLM | `api.x.ai` | xAI Grok |
| `KimiLLM` | 🔴 联网 + 🔴 LLM | `api.moonshot.cn` | Moonshot Kimi |
| `MiniMaxLLM` | 🔴 联网 + 🔴 LLM | `api.minimax.chat` | MiniMax |
| `GLMLLM` | 🔴 联网 + 🔴 LLM | `open.bigmodel.cn` | 智谱 ChatGLM |
| `SemanticChunker` | 🟡 本地模型 | `sentence-transformers`（首次需下载） | 语义分块（本地向量模型） |
| `CrossEncoderReranker` | 🟡 本地模型 | HuggingFace 模型（首次需下载） | 交叉编码重排 |

> **⚠️ 注意**: `SemanticChunker` 和 `CrossEncoderReranker` 虽然是"本地"模型，但首次运行时需要从 HuggingFace 下载权重（约 100–500 MB）。下载完成后可离线使用。

---

### 2.2 `memory/` — 记忆/向量存储层

| 类 / 函数 | 依赖类型 | 外部依赖 | 说明 |
|-----------|---------|---------|------|
| `VectorStore` | 🟢 纯本地 | ChromaDB（SQLite） | 完全离线运行 |
| `MemoryManager` | 🟢 纯本地 | JSON manifest | 完全离线运行 |
| `MemoryStack` | 🟢 纯本地 | 无 | 完全离线运行 |
| `IdentityLayer` | 🟢 纯本地 | 无 | 完全离线运行 |
| `NarrativeLayer` | 🟢 纯本地 | 无 | 完全离线运行 |
| `OnDemandLayer` | 🟢 纯本地 | 无 | 完全离线运行 |
| `DeepSearchLayer` | 🟢 纯本地 | 无 | 完全离线运行 |
| `ClosetIndex` | 🟢 纯本地 | 无 | 完全离线运行 |

> **✅ 推荐**: 如需完全离线使用 Ariadne，Memory 模块（向量存储 + 多记忆系统）可以在任何环境下正常工作，无需任何网络或 API。

---

### 2.3 `rag/` — RAG 检索增强层

| 类 / 函数 | 依赖类型 | 外部依赖 | 说明 |
|-----------|---------|---------|------|
| `BM25Retriever` | 🟢 纯本地 | `rank_bm25`（纯 Python） | 完全离线运行 |
| `HybridSearch` | 🟢 纯本地 | ChromaDB + rank_bm25 | 完全离线运行 |
| `Reranker`（启发式） | 🟢 纯本地 | 无 | `use_heuristic=True` 时完全离线 |
| `Reranker`（Cross-Encoder） | 🟡 本地模型 | HuggingFace 模型（首次需下载） | 下载后可离线 |
| `CitationGenerator` | 🟢 纯本地 | 无 | 完全离线运行 |
| `RAGEngine` | 见各组件 | 取决于各组件 | 基础搜索可离线 |

> **💡 技巧**: 设置 `advanced.enable_reranker = false`（`config.yaml`）可完全禁用 Cross-Encoder，确保 RAG 全程离线运行。

---

### 2.4 `ingest/` — 文档摄取层

| 摄取器 | 依赖类型 | 外部依赖 | 离线可用 |
|--------|---------|---------|---------|
| `MarkdownIngestor` | 🟢 纯本地 | 无 | ✅ |
| `TxtIngestor` | 🟢 纯本地 | 无 | ✅ |
| `CsvIngestor` | 🟢 纯本地 | 无 | ✅ |
| `CodeIngestor` | 🟢 纯本地 | 无 | ✅ |
| `WordIngestor` | 🟢 纯本地 | `python-docx` | ✅（库已安装时） |
| `PDFIngestor` | 🟢 纯本地 | `PyMuPDF` | ✅（库已安装时） |
| `ExcelIngestor` | 🟢 纯本地 | `openpyxl` | ✅（库已安装时） |
| `PPTIngestor` | 🟢 纯本地 | `python-pptx` | ✅（库已安装时） |
| `ConversationIngestor` | 🟢 纯本地 | 无 | ✅ |
| `MindMapIngestor` | 🟢 纯本地 | 无 | ✅ |
| `EPUBIngestor` | 🟢 纯本地 | `ebooklib` | ✅（库已安装时） |
| `BibTeXIngestor` | 🟢 纯本地 | 无 | ✅ |
| `RISIngestor` | 🟢 纯本地 | 无 | ✅ |
| `EmailIngestor` | 🟢 纯本地 | 无 | ✅ |
| `MBOXIngestor` | 🟢 纯本地 | 无 | ✅ |
| `ImageIngestor` | 🟢 纯本地 | `Pillow` | ✅（库已安装时） |
| `AudioIngestor` | 🟢 纯本地 | 无 | ✅ |
| `VideoIngestor` | 🟢 纯本地 | 无（字幕解析） | ✅ |
| `MarkItDownIngestor` | 🟢 纯本地 | `markitdown` | ✅（库已安装时） |
| `WebIngestor` | 🔴 联网 | `requests` + `beautifulsoup4` | ❌ |
| `OCRIngestor` | 🟡 条件联网 | `easyocr` / `PaddleOCR`（本地 OCR 引擎，首次需下载模型） | 模型下载后可离线 |

> **📝 说明**: `WebIngestor` 是 ingest 模块中**唯一必须联网**的摄取器。处理 URL 时需要访问外部网络。其余 20+ 种格式完全本地处理。

---

### 2.5 `graph/` — 知识图谱层

| 类 / 函数 | 依赖类型 | 外部依赖 | 说明 |
|-----------|---------|---------|------|
| `Entity` / `Relation`（数据模型） | 🟢 纯本地 | 无 | 完全离线运行 |
| `GraphStorage` | 🟢 纯本地 | JSON 文件 | 完全离线运行 |
| `GraphQuery` | 🟢 纯本地 | 无 | 完全离线运行 |
| `EntityExtractor`（规则回退） | 🟢 纯本地 | 无 | 不使用 LLM 时使用正则回退 |
| `RelationExtractor`（共现回退） | 🟢 纯本地 | 无 | 不使用 LLM 时使用共现分析 |
| `EntityExtractor`（LLM） | 🔴 LLM | LLM API | 提取质量更高 |
| `RelationExtractor`（LLM） | 🔴 LLM | LLM API | 提取质量更高 |
| `GraphEnricher` | 🔴 LLM（如传入） | LLM API（可选） | 可配置为纯本地模式 |

> **💡 降级策略**: `EntityExtractor` 和 `RelationExtractor` 构造函数接受 `llm=None`。当不传入 LLM 时，自动使用正则/共现规则回退，保证图谱构建始终可用（只是精度较低）。

---

### 2.6 `wiki/` — LLM Wiki 模块

| 函数 | 依赖类型 | 说明 |
|------|---------|------|
| `WikiProject` / `WikiPage`（数据模型） | 🟢 纯本地 | 完全离线 |
| `init_wiki_project` | 🟢 纯本地 | 完全离线 |
| `read_wiki_page` | 🟢 纯本地 | 完全离线 |
| `write_wiki_page` | 🟢 纯本地 | 完全离线 |
| `list_wiki_pages` | 🟢 纯本地 | 完全离线 |
| `parse_file_blocks` | 🟢 纯本地 | 完全离线 |
| `extract_wikilinks` | 🟢 纯本地 | 完全离线 |
| `append_log_entry` | 🟢 纯本地 | 完全离线 |
| `run_structural_lint` | 🟢 纯本地 | 结构检查，完全离线 |
| `ingest_source` | 🔴 LLM | 需要 LLM 分析源文档 |
| `batch_ingest` | 🔴 LLM | 批量摄取，依赖 LLM |
| `run_semantic_lint` | 🔴 LLM | 语义检查，需要 LLM |
| `query_wiki` | 🔴 LLM | Wiki 问答，需要 LLM |
| `ObsidianIngestor`（部分） | 🟢 纯本地 | Obsidian 导入，解析本地文件 |
| `import_obsidian_vault` | 🟢 纯本地 | 完全离线 |

> **📝 Wiki 模块分层**:
> - **构建层**（builder）：纯本地，用于读写页面、管理结构
> - **检查层**（linter）：`structural` 本地，`semantic` 需 LLM
> - **摄取层**（ingestor）：必须 LLM
> - **问答层**（query）：必须 LLM
> - **导入层**（obsidian）：纯本地，Obsidian Vault 导入无需联网

---

### 2.7 `plugins/` — 插件系统

| 类 / 函数 | 依赖类型 | 说明 |
|-----------|---------|------|
| `IngestorRegistry` | 🟢 纯本地 | 完全离线 |
| `HookManager` | 🟢 纯本地 | 完全离线 |
| `AutoSaveHook` | 🟢 纯本地 | 完全离线 |
| `ClaudeCodeHook` | 🟢 纯本地 | 完全离线 |

> **✅ 插件系统完全独立于网络**，不依赖任何外部服务。

---

### 2.8 `mcp/` — MCP 服务器

| 类 / 函数 | 依赖类型 | 说明 |
|-----------|---------|------|
| `AriadneMCPServer` | 🟢 纯本地 | 完全离线 |
| `AriadneResourceManager` | 🟢 纯本地 | 完全离线 |
| `AriadneToolHandler` | 🟢 纯本地 | 完全离线 |
| `SchemaValidator` | 🟢 纯本地 | 完全离线 |
| `WALAuditLogger` | 🟢 纯本地 | 完全离线 |
| `CacheInvalidationDetector` | 🟢 纯本地 | 完全离线 |

> **✅ MCP Server 完全离线运行**。所有增强功能（WAL 审计、Schema 验证、缓存失效检测）均为本地实现。

---

### 2.9 `web/` — FastAPI Web 服务

| 类 / 函数 | 依赖类型 | 说明 |
|-----------|---------|------|
| `create_app` / `run_server` | 🟡 需要运行网络 | 提供 HTTP 服务，需网络通信 |
| `memory_router` | 🟢 纯本地（底层） | 路由层无依赖，但依赖 memory 模块 |
| `ingest_router` | 🟡 部分联网 | 路由本身无依赖，但部分 ingestor 需联网 |
| `search_router` | 🟢 纯本地（底层） | 底层 RAG 可离线 |
| `graph_router` | 🔴 LLM（如使用） | 底层图谱可离线，但 enrichment 需 LLM |
| `config_router` | 🟢 纯本地 | 完全离线 |

> **📝 Web 层说明**: Web 服务本身需要网络来接受 HTTP 请求，但其底层调用的模块依赖取决于具体功能。配置路由（`/api/config`）和内存路由（`/api/memory`）可完全离线运行。

---

### 2.10 `advanced.py` — 高级功能

| 类 / 函数 | 依赖类型 | 外部依赖 | 说明 |
|-----------|---------|---------|------|
| `Summarizer` | 🔴 LLM | LLM API | 必须 LLM |
| `GraphVisualizer` | 🟢 纯本地 | 无 | DOT / JSON / Mermaid / HTML 导出，完全离线 |
| `Exporter` | 🟢 纯本地（基础） | `python-docx` / `weasyprint`（可选） | Markdown/HTML 完全离线 |
| `summarize_documents` | 🔴 LLM | LLM API | 必须 LLM |
| `visualize_graph` | 🟢 纯本地 | 无 | 完全离线 |
| `export_data` | 🟢 纯本地（基础） | 可选库 | 完全离线 |

---

## 三、场景化使用指南

### 场景 A：完全离线工作（飞机上、隐私敏感环境）

**可用功能：**
- ✅ 文档摄取（Markdown / PDF / Word / 代码等 20+ 格式）
- ✅ 本地向量搜索（Semantic Search via ChromaDB）
- ✅ BM25 关键词搜索
- ✅ 混合搜索（HybridSearch，禁用 Cross-Encoder）
- ✅ 引用生成（CitationGenerator）
- ✅ 知识图谱构建（使用规则回退模式，非 LLM 提取）
- ✅ 图谱可视化（DOT / JSON / Mermaid / HTML）
- ✅ Wiki 页面读写管理
- ✅ Wiki 结构检查（structural lint）
- ✅ Obsidian Vault 导入
- ✅ 多记忆系统管理（创建/重命名/删除/合并）
- ✅ 数据导出（Markdown / HTML）
- ✅ MCP Server
- ✅ 插件系统

**不可用功能：**
- ❌ LLM 摘要生成
- ❌ Wiki 源文档摄取（ingest_source / batch_ingest）
- ❌ Wiki 语义检查（semantic lint）
- ❌ Wiki 问答（query_wiki）
- ❌ LLM 驱动的实体/关系提取
- ❌ Cross-Encoder 重排序（如未预下载模型）
- ❌ Web URL 抓取（WebIngestor）
- ❌ 在线 OCR（需下载模型）

**配置建议：**
```yaml
# config.yaml
llm:
  provider: ""  # 不填 API Key，所有 LLM 功能自动降级
advanced:
  enable_reranker: false  # 禁用 Cross-Encoder，确保 RAG 全程本地
```

---

### 场景 B：仅使用 LLM 能力（在线，但 API 有限）

**可用功能：**
- ✅ Wiki 完整功能（摄取 / 检查 / 问答）
- ✅ LLM 摘要生成
- ✅ LLM 实体/关系提取（知识图谱增强）
- ✅ Cross-Encoder 重排序
- ✅ 所有本地功能

**不可用功能：**
- ❌ Web URL 抓取（需要 `requests` 网络访问）
- ❌ 在线 OCR（需下载模型）

---

### 场景 C：完整功能（推荐开发/生产环境）

所有功能均可用，包括：
- 所有本地功能
- 所有 LLM 功能
- Web UI
- MCP Server
- URL 抓取

---

## 四、快速参考表

| 模块 | 纯本地 | 需要联网 | 需要 LLM | 需要首次下载模型 |
|------|--------|---------|---------|--------------|
| `memory/` | ✅ 全部 | — | — | — |
| `rag/` | ✅ 基础搜索 | — | —（可禁用） | 🟡 CrossEncoder |
| `ingest/` | ✅ 20+ 格式 | 🔴 WebIngestor | — | 🟡 OCRIngestor |
| `graph/` | ✅ 模型/存储 | — | 🟡 可选 | — |
| `wiki/` | ✅ builder 层 | — | 🔴 ingest/query/lint | — |
| `advanced/` | ✅ GraphVisualizer | — | 🔴 Summarizer | — |
| `plugins/` | ✅ 全部 | — | — | — |
| `mcp/` | ✅ 全部 | — | — | — |
| `llm/` | — | ✅ 全部 | ✅ 全部 | 🟡 SemanticChunker, CrossEncoder |

**图例**：
- 🟢 完全可用（零外部依赖）
- 🟡 条件可用（首次需联网下载模型/权重）
- 🔴 必须联网或必须 LLM

---

## 五、API Key 安全建议

| 环境 | 建议 |
|------|------|
| 本地开发 | 使用 `.env` 文件，通过 `ARIADNE_LANGUAGE=zh_CN ariadne ...` 或环境变量传入 |
| CI/CD | 使用 GitHub Secrets / 环境变量注入 |
| 生产部署 | 使用 Vault / Kubernetes Secret 管理 API Key |
| 共享环境 | 使用 `~/.ariadne/.env` 用户级配置，避免提交到 Git |

> **⚠️ 安全提醒**: 永远不要将 API Key 提交到 Git。建议在项目根目录添加 `.env.example`（不含真实 Key）并加入 `.gitignore`。

---

*本文档随 Ariadne 版本更新，建议配合 `pyproject.toml` 的 `[project.optional-dependencies]` 节对照阅读。*
