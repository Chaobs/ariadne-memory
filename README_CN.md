# Ariadne · 阿里阿德涅

> 阿里阿德涅（Ariadne）是希腊神话中帮助忒修斯穿越迷宫的女神，手持线团引导归途。
> 正如我们的系统 —— 织入你所有的知识，在记忆的迷宫中为你指引方向。

**Ariadne** 是一个跨源 AI 记忆与知识织入系统，将来自不同来源的文档、对话、代码统一摄入，构建可检索的知识网络。

**特色功能：** 多源摄入 + RAG + 知识图谱 + 记忆持久化 + AI 增强 (MCP/Agent/Skill) + LLM Wiki

**[English Version](README.md)** | 中文版

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](pyproject.toml)

---

## 目录 / Table of Contents

- [功能特性 / Features](#功能特性--features)
- [支持格式 / Supported Formats](#支持格式--supported-formats)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [CLI 使用指南 / CLI Usage](#cli-使用指南--cli-usage)
- [架构设计 / Architecture](#架构设计--architecture)
- [LLM Wiki / LLM Wiki](#llm-wiki--llm-wiki)
- [Agent 集成 / Agent Integration](#agent-集成--agent-integration)
- [开发路线 / Roadmap](#开发路线--roadmap)
- [项目致谢 / Credits](#项目致谢--credits)
- [第三方库许可 / Third-party Licenses](#第三方库许可--third-party-licenses)

---

## 功能特性 / Features

| 特性 | 描述 | 状态 |
|------|------|------|
| 🗂️ **多源摄入** | 同时支持 Markdown、Word、PPT、PDF、TXT、思维导图、代码等多种格式 | ✅ |
| 🔍 **语义搜索** | 基于向量数据库的语义相似度搜索，返回最相关结果 | ✅ |
| 🧠 **记忆持久化** | ChromaDB 本地持久化存储，数据完全归你所有 | ✅ |
| 📁 **多记忆系统** | 支持创建多个独立记忆系统，分类管理不同领域知识 | ✅ |
| 🔗 **知识图谱** | 自动识别实体与关系，构建跨源知识关联网络 | ✅ |
| 🤖 **AI 增强** | 支持 DeepSeek / Claude / Qwen / Gemini / Kimi / MiniMax / GLM / Grok 等主流 AI | ✅ |
| 🧮 **系统合并** | 支持合并多个记忆系统为一，便于知识整合 | ✅ |
| 💾 **记忆导出/导入** | 支持将记忆系统导出为目录或从目录导入（备份与分享） | ✅ |
| 📚 **媒体支持** | EPUB/MOBI 电子书、图片 OCR、扫描 PDF、学术文献元数据 | ✅ |
| 🔌 **MCP Server** | 提供 MCP 工具接口，可接入 Claude Code / WorkBuddy / Cursor | ✅ |
| 🖥️ **双界面** | CLI（Typer + Rich）+ Web UI（React + FastAPI），功能完全对齐 | ✅ |
| 🕸️ **Web UI** | 现代 React 单页应用，含语义搜索、记忆管理、D3 图谱、设置 | ✅ |
| 🕸️ **D3 图谱** | 交互式力导向知识图谱，支持缩放/平移/拖拽 | ✅ |
| 🌙 **暗色模式** | 亮色/暗色主题切换（保存在 localStorage） | ✅ |
| 📱 **响应式** | 移动端自适应布局（适配 <768px 和 <480px） | ✅ |
| 🌍 **多语言** | 支持 8 种语言（中文简繁体、日语、英、法、西、俄、阿） | ✅ |
| 📝 **智能摘要** | LLM 驱动的多语言摘要生成，支持指定输出语言 | ✅ |
| 📊 **可视化** | 知识图谱交互式可视化（HTML / DOT / Mermaid） | ✅ |
| 📤 **多格式导出** | 支持 Markdown、HTML、Word、PDF 格式导出 | ✅ |
| 📦 **本地化依赖** | 第三方库本地化，版本一致性好 | ✅ |
| 🎯 **二进制支持** | 自动处理二进制文件，提取文件名作为知识引用 | ✅ |
| 🔄 **通用摄入** | 通过 markitdown 支持 HTML/RSS/Jupyter/RTF/ODF 等 22+ 格式 | ✅ |
| ⏱️ **延迟删除** | 标记-批量删除机制，避免 SQLite 锁争用 | ✅ |
| 🔀 **RAG Pipeline** | 混合搜索(向量+BM25) + 重排序 + 引用生成 | ✅ |
| 📌 **智能引用** | 自动生成带高亮的文档引用，支持多种格式输出 | ✅ |
| 📖 **LLM Wiki** | Karpathy 风格持久化知识库，两步链式思考摄入、问答、整洁检查 | ✅ |

---

## 支持格式 / Supported Formats

### 文档格式 (Phase 1)

| 格式 | 扩展名 | 摄入器 | 说明 |
|------|--------|--------|------|
| Markdown | `.md`, `.markdown` | `MarkdownIngestor` | 使用标题切分语义块 |
| Word | `.docx`, `.doc` | `WordIngestor` | 提取段落，保留样式层级 |
| PPT | `.pptx`, `.ppt` | `PPTIngestor` | 每张幻灯片为一 Chunk |
| PDF | `.pdf` | `PDFIngestor` | PyMuPDF 文本提取，智能合并短页 |
| 纯文本 | `.txt` | `TxtIngestor` | 按段落切分 |
| 对话导出 | `.json` | `ConversationIngestor` | 支持 ChatGPT/Claude/DeepSeek JSON 导出 |
| 思维导图 | `.mm`, `.xmind` | `MindMapIngestor` | 支持 FreeMind/XMind 格式 |
| 代码 | `.py`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.js`, `.ts`, `.jsx`, `.tsx`, `.cs`, `.go`, `.rs`, `.rb`, `.php`, `.swift`, `.kt`, `.scala` | `CodeIngestor` | AST/正则提取函数、类、文档字符串 |
| Excel | `.xlsx`, `.xls` | `ExcelIngestor` | 按工作表/行列提取，含单元格注释 |
| CSV | `.csv` | `CsvIngestor` | 保留表头作为上下文，按行切分 |

### 媒体与学术工具 (Phase 4)

| 格式 | 扩展名 | 摄入器 | 处理方式 |
|------|--------|--------|----------|
| EPUB电子书 | `.epub` | `EPUBIngestor` | 元数据+章节结构提取 |
| 图片 | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp` | `ImageIngestor` | EXIF元数据提取 |
| OCR | 扫描PDF/图片 | `OCRIngestor` | RapidOCR/Tesseract文字识别 |
| BibTeX | `.bib` | `BibTeXIngestor` | 解析学术文献元数据 |
| RIS | `.ris` | `RISIngestor` | 解析学术引用数据 |
| 网页 | URL, `.html` | `WebIngestor` | 抓取标题/正文/元数据，支持在线URL和本地HTML文件 |
| 邮件 | `.eml`, `.mbox` | `EmailIngestor` | 解析邮件头/正文/附件 |
| 视频 | `.mp4`, `.avi`, `.mkv`, `.mov` | `VideoIngestor` | 元数据+字幕提取 |
| 音频 | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg` | `AudioIngestor` | 元数据+转录(Whisper) |

### 二进制文件 (新增)

| 格式 | 扩展名 | 摄入器 | 处理方式 |
|------|--------|--------|----------|
| 二进制 | `.exe`, `.dll`, `.so`, `.dylib`, `.bin`, `.dat`, `.iso`, `.apk`, `.ipa` 等 | `BinaryIngestor` | 提取文件名、大小、类型作为元数据引用 |

### 通用格式 (via markitdown)

| 格式 | 扩展名 | 摄入器 | 处理方式 |
|------|--------|--------|----------|
| HTML | `.html`, `.htm` | `MarkItDownIngestor` | 转换为 Markdown 后语义切分 |
| RSS | `.rss`, `.xml` | `MarkItDownIngestor` | RSS/Atom Feed 解析 |
| Jupyter | `.ipynb` | `MarkItDownIngestor` | 代码+输出 Markdown 转换 |
| Outlook | `.msg` | `MarkItDownIngestor` | MSG 邮件内容提取 |
| RTF | `.rtf` | `MarkItDownIngestor` | 富文本格式转换 |
| ODF | `.ods`, `.odt`, `.odp` | `MarkItDownIngestor` | OpenDocument 格式转换 |
| 其他 | 任何未匹配格式 | `MarkItDownIngestor` | 自动尝试 markitdown 转换 |

---

## 快速开始 / Quick Start

### 环境要求 / Requirements

- Python 3.9+
- 推荐系统: Windows / macOS / Linux

### 安装 / Installation

```bash
# 克隆仓库
git clone https://github.com/Chaobs/ariadne-memory.git
cd ariadne-memory

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows

# 安装依赖
pip install -e .

# 或仅安装核心依赖
pip install -r requirements.txt
```

### 使用方式 / Usage

**快捷入口（Windows）：**
```bash
# 双击 ariadne-cli.bat  打开命令行
# 双击 ariadne-web.bat   现代 Web UI（推荐）
```

**Linux / macOS：**
```bash
./ariadne-web.sh              # 默认端口 8770
./ariadne-web.sh 8080          # 自定义端口
./ariadne-web.sh --dev        # 开发模式（Vite 热重载 + FastAPI）
chmod +x ariadne-web.sh       # 首次使用需添加执行权限
```

**或使用 Python：**
```bash
# 启动 Web UI（推荐）
python -m ariadne.cli web run

# 摄入单个文件
python -m ariadne.cli ingest ./my_notes.md

# 摄入整个目录（含子目录）
python -m ariadne.cli ingest ./my_research/ -r

# 语义搜索
python -m ariadne.cli search "犹太教与基督教的共同伦理观念"

# 查看系统信息
python -m ariadne.cli info --stats

# 创建新的记忆系统
python -m ariadne.cli memory create "Research Notes"

# 摄入到指定记忆系统
python -m ariadne.cli ingest ./papers/ -r -m "Research Notes"

# 搜索指定记忆系统
python -m ariadne.cli search "AI ethics" -m "Research Notes"

# 合并多个记忆系统
python -m ariadne.cli memory merge old_notes temp --into "Consolidated"
```

### Python API

```python
from ariadne.ingest import MarkdownIngestor, PDFIngestor
from ariadne.memory import VectorStore

# 初始化存储
store = VectorStore()

# 摄入 Markdown 笔记
docs = MarkdownIngestor().ingest("path/to/notes.md")
store.add(docs)

# 摄入 PDF 论文
docs = PDFIngestor().ingest("path/to/paper.pdf")
store.add(docs)

# 语义搜索
results = store.search("关于AI伦理的讨论", top_k=5)
for doc, score in results:
    print(f"[{score:.4f}] {doc.content[:200]}")
```

---

## CLI 使用指南 / CLI Usage

> 详细的使用说明请参阅 [USAGE.md](USAGE.md)。

### 命令概览 / Command Overview

| 命令 | 说明 | 示例 |
|------|------|------|
| `ingest` | 摄入文件或目录 | `ariadne ingest ./notes.md` |
| `search` | 语义搜索 | `ariadne search "AI伦理"` |
| `info` | 查看系统信息 | `ariadne info --stats` |
| `web run` | 启动 Web UI | `ariadne web run --port 8770` |
| `memory list` | 列出所有记忆系统 | `ariadne memory list` |
| `memory create` | 创建新记忆系统 | `ariadne memory create "Research"` |
| `memory rename` | 重命名记忆系统 | `ariadne memory rename old new` |
| `memory delete` | 删除记忆系统 | `ariadne memory delete old` |
| `memory merge` | 合并记忆系统 | `ariadne memory merge a b --into new` |
| `memory export` | 导出记忆系统 | `ariadne memory export research ./backup/` |
| `memory import` | 导入记忆系统 | `ariadne memory import ./backup/ imported` |
| `config show` | 显示当前配置 | `ariadne config show` |
| `config set` | 设置配置项 | `ariadne config set llm.provider deepseek` |
| `config test` | 测试 LLM 连接 | `ariadne config test` |
| `config set-api-key` | 设置 API 密钥 | `ariadne config set-api-key deepseek sk-xxxxx` |
| `advanced summarize` | 生成摘要 | `ariadne advanced summarize "AI"` |
| `advanced graph` | 知识图谱 | `ariadne advanced graph -f dot` |
| `rag search` | RAG 混合搜索 | `ariadne rag search "query" -m default` |
| `rag rebuild-index` | 重建 BM25 索引 | `ariadne rag rebuild-index` |
| `rag health` | RAG 健康检查 | `ariadne rag health` |

---

## 架构设计 / Architecture

```
ariadne/
├── __init__.py              # 公共 API 入口（自动初始化 vendor）
├── cli.py                   # 命令行工具（Typer + Rich）
├── config.py               # 统一配置系统
├── paths.py                # 路径管理模块
├── advanced.py             # 高级功能（摘要/可视化/导出）
├── i18n.py                 # 多语言国际化支持（8种语言）
├── logging.py              # 会话日志（自动轮转）
├── models.py               # 共享数据模型
├── ingest/                 # 摄入模块
│   ├── base.py             # BaseIngestor 抽象基类 + Document 数据模型
│   ├── markdown.py         # Markdown 摄入器
│   ├── word.py             # Word (.docx) 摄入器
│   ├── ppt.py              # PowerPoint (.pptx) 摄入器
│   ├── pdf.py              # PDF 摄入器
│   ├── txt.py              # 纯文本摄入器
│   ├── conversation.py     # 对话历史摄入器
│   ├── mindmap.py          # 思维导图摄入器
│   ├── code.py             # 代码注释摄入器
│   ├── excel.py            # Excel 摄入器
│   ├── csv.py              # CSV 摄入器
│   ├── binary.py           # 二进制文件摄入器
│   ├── epub.py             # EPUB 电子书摄入器
│   ├── image.py            # 图片/OCR 摄入器
│   ├── academic.py         # BibTeX/RIS 摄入器
│   ├── web.py              # 网页摄入器
│   ├── email.py            # 邮件摄入器
│   ├── media.py            # 视频/音频摄入器
│   └── markitdown_ingestor.py  # 通用格式摄入（markitdown，22+ 格式）
├── memory/                 # 向量记忆存储层
│   ├── store.py            # ChromaDB 向量存储 + 延迟删除
│   └── manager.py          # 多记忆系统管理器 + 导出/导入
├── llm/                    # LLM 统一接口
│   ├── base.py             # BaseLLM 抽象基类
│   ├── factory.py          # LLM 工厂 + ConfigManager
│   ├── providers.py        # 各提供商实现（9个提供商）
│   ├── reranker.py         # 语义重排
│   └── chunker.py          # 智能分块
├── graph/                  # 知识图谱
│   ├── models.py           # Entity/Relation 数据模型
│   ├── extractor.py        # 实体/关系抽取
│   ├── storage.py          # NetworkX + SQLite 存储
│   └── query.py            # 图查询接口
├── plugins/                # 插件/Hook 系统
│   ├── registry.py         # IngestorRegistry（优先级注册、装饰器 API）
│   ├── hooks.py            # HookManager（4个生命周期钩子）
│   ├── loader.py           # 插件发现（entry_points + 目录扫描）
│   └── __init__.py         # 公共 API（ingest_hook, on, ...）
├── rag/                    # RAG 管道
│   ├── bm25_retriever.py   # BM25 检索器
│   ├── hybrid_search.py    # 混合搜索（向量 + BM25，RRF 融合）
│   ├── reranker.py         # 交叉编码器重排序
│   ├── citation.py         # 引用生成器
│   └── engine.py           # RAG 引擎
├── wiki/                   # LLM Wiki（Karpathy 模式）
│   ├── models.py          # WikiPage, WikiProject, LintResult 数据模型
│   ├── prompts.py        # 两步链式思考提示词构建
│   ├── builder.py        # 文件读写、块解析、增量缓存
│   ├── ingestor.py       # 两步 CoT 摄入管道
│   ├── linter.py         # 结构检查 + 语义检查
│   ├── query.py          # Wiki 问答（带引用）
│   └── obsidian.py       # Obsidian 笔记库导入
├── mcp/                    # MCP Server
│   ├── server.py           # MCP Server 核心实现（stdio / HTTP）
│   ├── tools.py            # MCP Tools（4个工具）
│   ├── resources.py        # MCP Resources
│   └── prompts.py          # MCP Prompts
├── web/                    # Web UI（React + FastAPI）
│   ├── api.py              # FastAPI REST API（20+ 端点）
│   ├── __init__.py         # Web 入口
│   ├── static/             # 部署的生产构建
│   └── frontend/           # React + Vite + TypeScript 源码
│       └── src/
│           ├── api/        # API 客户端（ariadne.ts）
│           ├── components/ # 布局、主题、国际化
│           └── pages/      # Home/Search/Memory/Ingest/Graph/Settings
└── locale/                 # (已移除 — Web UI 有自己的 i18n)

docs/                       # 文档目录
├── AGENT_INTEGRATION.md   # Agent 集成指南（Claude Code, Cursor, WorkBuddy）
├── MCP.md                 # MCP Server 文档
├── LLM_WIKI.md            # LLM Wiki 功能指南（Karpathy 模式）
├── Ariadne-Memory-SKILL.md    # Agent Skill 定义文件（Claude Code, Cursor 等）
├── TEST_AND_EXTENSION_PLAN.md
├── AutoSave.md
├── Closet.md
└── MemoryStack.md

examples/                   # 配置示例
└── mcp_config.json        # MCP 客户端配置模板

.ariadne/                   # 项目本地数据目录（不在 Git 中）
├── config.json             # 用户配置（API Key 等，不推送）
├── .env                    # 环境变量（可选）
├── memories/               # 记忆系统目录
│   ├── manifest.json       # 记忆系统注册表
│   └── {name}/             # 每个记忆系统的 ChromaDB 数据
├── knowledge_graph.db      # 知识图谱 SQLite 数据库
├── logs/                   # 会话日志（自动轮转，保留10次）
└── chroma/                 # ChromaDB 默认持久化目录

vendor/                     # 第三方库本地化
├── __init__.py             # 自动初始化脚本（HF_HOME / CHROMA_CACHE 重定向）
├── packages/               # pip whl 包
├── models/                 # 本地模型缓存（all-MiniLM-L6-v2）
└── cache/                  # 运行时缓存（Chroma ONNX 等）
```

---

## LLM Wiki / LLM Wiki

基于 [Karpathy 的 LLM Wiki 模式](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，Ariadne 提供了一个持久化、可查询的知识库，从源文档中有机生长。

### 架构 / Architecture

```
原始资料（不可变）→ Wiki（LLM 生成）→ Schema（规则配置）
```

### 三个核心操作 / Three Core Operations

| 操作 | 命令 | 说明 |
|------|------|------|
| **摄入 / Ingest** | `ariadne wiki ingest <文件>` | 两步 CoT：分析源文档 → 生成 Wiki 页面 |
| **问答 / Query** | `ariadne wiki query <问题>` | 搜索 Wiki → LLM 综合回答，带引用 |
| **检查 / Lint** | `ariadne wiki lint` | 结构检查（孤立页面/断链）+ 语义检查（LLM） |

### 目录结构 / Directory Structure

```
my-wiki/
├── raw/
│   ├── sources/       ← 放置源文档
│   └── assets/       ← 图片和附件
├── wiki/
│   ├── index.md      ← 自动生成的主题索引
│   ├── log.md        ← 摄入操作日志
│   ├── overview.md   ← Wiki 总览
│   ├── content/      ← 概念/实体页面
│   └── queries/      ← 存档的问答会话
├── schema.md         ← Wiki 结构规则
└── purpose.md       ← Wiki 目标和宗旨
```

### CLI 快速开始 / CLI Quick Start

```bash
# 初始化 Wiki 项目
ariadne wiki init my-wiki

# 摄入源文件（两步 CoT）
ariadne wiki ingest raw/papers/ml-survey.pdf -p my-wiki

# 提问
ariadne wiki query "主要发现是什么？" -p my-wiki

# 健康检查
ariadne wiki lint -p my-wiki

# 列出所有页面
ariadne wiki list -p my-wiki
```

### Obsidian 导入 / Obsidian Import

导入整个 Obsidian 笔记库，自动转换语法：

```bash
ariadne wiki ingest-vault /path/to/obsidian/vault -p my-wiki
```

自动转换：`[[wikilink]]` → markdown 链接，`==高亮==` → `**粗体**`，保留 frontmatter 和 `#标签`。

### MCP 工具 / MCP Tools

| 工具 | 说明 |
|------|------|
| `ariadne_wiki_ingest` | 两步 CoT 摄入源文档 |
| `ariadne_wiki_query` | Wiki 知识库问答，LLM 综合 |
| `ariadne_wiki_lint` | 结构 + 语义健康检查 |
| `ariadne_wiki_list` | 按类型/标签列出页面 |

详细文档见 [docs/LLM_WIKI.md](docs/LLM_WIKI.md)。

---

## Agent 集成 / Agent Integration

Ariadne 支持多种 AI Agent 集成：

| Agent | 集成方式 | 文档 |
|-------|--------|------|
| Claude Code | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#claude-code) |
| Cursor | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#cursor) |
| Windsurf | MCP Server | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#windsurf) |
| Claude Code | Skill + HTTP API | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#agent-skill) |
| 自定义 Agent | HTTP REST API | [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md#http-rest-api) |

### 快速配置

**MCP Server（Claude Code / Cursor / Windsurf）：**
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

**Agent Skill：**
将 `docs/Ariadne-Memory-SKILL.md` 复制到你的 Agent 的 skill 目录（如 `~/.workbuddy/skills/ariadne-memory/SKILL.md`）

**HTTP API：**
启动 Web UI：`python -m ariadne.cli web run`
然后访问 REST API：`http://localhost:8770`

---

## 开发路线 / Roadmap

> **当前阶段**：第二阶段 Web UI ✅ 已完成 | 第三阶段 插件系统 ✅ 已完成 | 第六阶段 社区运营与迭代 🔄

### 第一阶段 MVP ✅ **已完成**
- [x] 项目骨架与目录结构
- [x] 10 种文档格式摄入器（Markdown/Word/PPT/PDF/TXT/对话/思维导图/代码/Excel/CSV）
- [x] ChromaDB 向量存储层
- [x] CLI 工具（ingest / search / info）
- [x] 中英双语 README
- [x] 核心数据模型（Document / Entity / Relation）
- [x] ChromaDB 运行时验证
- [x] 各摄入器单元测试
- [x] 批量摄入与进度条支持
- [x] 记忆系统 CRUD 管理
- [x] 记忆系统导出/导入功能（CLI `memory export` / `memory import`）
- [x] 数据目录迁移至项目根目录 `.ariadne/`（不再使用 `~/.ariadne`）
- [x] 第三方库本地化（vendor 目录）+ 模型缓存本地化

### 第一阶段 LLM 增强 ✅ **已完成**
- [x] LLM 统一抽象接口（DeepSeek / Claude / Qwen / ChatGPT / Gemini / Grok / Kimi / MiniMax / GLM）
- [x] `config.json` 配置文件管理
- [x] LLM 增强语义重排（Reranker）
- [x] 智能动态分块（SemanticChunker 替代固定长度）
- [x] 新增 Kimi / MiniMax / GLM 提供商（9个提供商总计）
- [x] **智能摘要修复** — 修复 Summarize prompt 中 JSON 示例花括号转义问题

### 第二阶段 Web UI ✅ **已完成**
- [x] `ariadne web run/info` CLI 命令
- [x] FastAPI REST API（20+ 端点覆盖全部 CLI 功能）
- [x] React + Vite + TypeScript SPA（6 个页面：Home/Search/Memory/Ingest/Graph/Settings）
- [x] Vite 开发服务器配置 API 代理
- [x] **D3.js 交互式知识图谱** — 力导向图谱，支持缩放/平移/拖拽
- [x] **SSE 实时摄入进度** — Server-Sent Events 流式推送
- [x] **暗色/亮色主题切换**（保存在 localStorage）
- [x] **响应式移动端适配**（<768px / <480px）
- [x] **图谱导出** — HTML/Markdown/DOCX/SVG/JSON/Mermaid/PNG/DOT
- [x] **图谱筛选** — 按实体类型筛选
- [x] **图谱节点搜索** — 搜索并高亮指定节点
- [x] **图谱悬停高亮** — 鼠标悬停时高亮关联边
- [x] **搜索自动补全** — 实时搜索建议，支持键盘导航
- [x] **Web UI 国际化** — 8种语言支持，侧边栏语言切换器
- [x] **Web UI 功能对齐** — 记忆详情/清空、RAG 参数调节、实体查询、完整配置查看

### 第三阶段 知识图谱 ✅ **已完成**
- [x] 实体识别 + 关系抽取（LLM API 驱动）
- [x] NetworkX + SQLite 图数据库
- [x] 跨源关联查询
- [x] 知识时间线视图
- [x] 交互式图谱可视化（HTML/DOT/Mermaid 格式）
- [ ] 🔨 **知识系统分析比对**（多记忆系统间差异对比、知识覆盖度分析）

### 第三阶段+ 插件/Hook 系统 ✅ **已完成**
- [x] `ariadne/plugins/` — IngestorRegistry + HookManager + PluginLoader
- [x] 动态摄入器注册（优先级注册、装饰器 API）
- [x] 4 个生命周期钩子（before_ingest / after_ingest / before_search / after_search）
- [x] 插件发现（Python entry_points + 目录扫描）
- [x] 统一 SCAN_EXTENSIONS 从 IngestorRegistry 获取（61 个内置扩展名）
- [x] 配置支持：`plugins` 节

### 第四阶段 媒体支持与学术工具 🔄 **部分完成**
- [x] EPUB 电子书摄入
- [x] 图片摄入（元数据提取）
- [x] 图片 / 扫描版 PDF OCR（pytesseract / RapidOCR）
- [x] 学术文献元数据（BibTeX / RIS）
- [x] 网页链接摄入（URL 抓取 + 本地 HTML）
- [x] 电子邮件摄入（EML/MBOX 解析）
- [x] 视频文件摄入（元数据+字幕提取）
- [x] 音频文件摄入（语音转录）
- [ ] 🔨 **聊天记录摄取** — QQ、微信、飞书等 IM 对话记录解析
- [ ] 🔨 **OCR + 视听增强** — 非文字图片/视频调用转述模型（Whisper/视觉LLM）
- [ ] 🔨 **OFD 文件支持** — 国内税务/发票替代 PDF 格式

### 第五阶段 MCP Server ✅ **已完成**
- [x] AriadneMCPServer 核心实现（支持 stdio / HTTP 传输）
- [x] MCP Tools：`ariadne_search` / `ariadne_ingest` / `ariadne_graph_query` / `ariadne_stats`
- [x] MCP Resources：`collections` / `stats` / `config` / `graph`
- [x] MCP Prompts：`search` / `ingest` / `graph` / `context` / `compare`

#### 第五阶段 扩展功能 🔨 **待开发**
- [ ] 🔨 **AI Agent 对话记忆实时向量化** — 在与 AI Agent 对话时，自动将对话记忆实时向量化并摄入知识系统，实现对话历史的永久扩展检索

### v0.3.0 增强版 ✅ **已完成**
- [x] 第三方库本地化（vendor 目录）
- [x] 模型缓存本地化（all-MiniLM-L6-v2）
- [x] 二进制文件处理（提取文件名为知识引用）
- [x] 扩展 LLM 提供商示例（config.sample.json 含 9 个模板）
- [x] 快捷入口脚本（ariadne-cli.bat / ariadne-web.bat）
- [x] 日语支持（ja locale，总计 8 种语言）
- [x] .gitignore 更新（config.json / .ariadne 不推送）

### 第六阶段 社区运营与迭代（持续）
- [x] GitHub 正式发布 v0.2.0 → v0.6.3
- [x] **Web UI（FastAPI + React）** — 现代跨平台界面，替代旧版 Tkinter
- [x] **实时摄入进度** — SSE 实时上传进度
- [x] **精美图谱可视化** — D3.js 交互式知识图谱增强（筛选、高亮、导出）
- [x] **Web UI 功能对齐** — 记忆详情/清空、RAG 参数、实体查询、DOT 导出、完整配置
- [x] **会话日志** — `.ariadne/logs/` 自动轮转
- [ ] 🔨 **Wiki 页面与详细使用文档**
- [ ] 🔨 **Logo 与 Icon 设计**
- [ ] 🔨 **云备份与联网查询**（记忆系统云端同步 + 实时信息检索增强）
- [ ] 🔨 **指定目录自动摄入** — 后台监控文件变化，自动摄入知识系统
- [ ] 版本化发布（v0.7.0+）
- [ ] HackerNews / Reddit 投递
- [ ] 中文社区传播（掘金 / 知乎 / CSDN）

---

## 图例

| 标记 | 含义 |
|------|------|
| ✅ | 已完成 |
| 🔄 | 部分完成 |
| 🔨 | 待开发 |
| ⚡ | 当前优先任务 |

---

## 项目致谢 / Credits

### 核心灵感 / Core Inspiration

**MemPalace** 是 Ariadne 最重要的灵感来源之一。MemPalace 提出了"AI 记忆"的概念，证明本地向量存储 + 语义搜索可以极大地增强 AI 工具的上下文能力。

> "Ariadne's pluggable ingestor and storage architecture is inspired by [MemPalace](https://github.com/MemPalace/mempalace). MemPalace is released under the MIT License."

### 第三方库许可 / Third-party Licenses

本项目使用以下开源组件，感谢它们的贡献：

| 组件 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [ChromaDB](https://github.com/chroma-core/chroma) | ≥0.4.0 | Apache 2.0 | 向量存储与检索 |
| [Click](https://github.com/pallets/click) | ≥8.0.0 | BSD-3-Clause | CLI 框架 |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | latest | Apache 2.0 | 文本嵌入模型 |
| **all-MiniLM-L6-v2** | - | Apache 2.0* | 默认嵌入模型 |
| [python-docx](https://github.com/python-openxml/python-docx) | ≥1.0.0 | MIT | Word 文档解析 |
| [python-pptx](https://github.com/scanny/python-pptx) | ≥0.6.21 | MIT | PPT 解析 |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | ≥1.23.0 | AGPL-3.0 | PDF 解析 |
| [openpyxl](https://foss.heptanodon.org/openpyxl/) | ≥3.1.0 | MIT | Excel 解析 |
| [networkx](https://github.com/networkx/networkx) | ≥3.0 | BSD-3-Clause | 知识图谱 |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | ≥2.0.0 | MIT | 数据库 ORM |
| [requests](https://github.com/psf/requests) | ≥2.31.0 | Apache 2.0 | HTTP 请求 |
| [PyYAML](https://github.com/yaml/pyyaml) | ≥6.0 | MIT | YAML 解析 |
| [tqdm](https://github.com/tqdm/tqdm) | ≥4.65.0 | MIT | 进度条 |
| [Typer](https://github.com/tiangolo/typer) | ≥0.9.0 | MIT | CLI 框架 |
| [Rich](https://github.com/Textualize/rich) | ≥10.11.0 | MIT | 终端美化 |
| [markitdown](https://github.com/microsoft/markitdown) | ≥0.1.0 | MIT | 通用文档转换 |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | ≥4.12 | MIT | HTML 解析 |
| [ebooklib](https://github.com/aerkalov/ebooklib) | ≥0.20 | AGPL-3.0 | EPUB 解析 |
| [Pillow](https://github.com/python-pillow/Pillow) | ≥10.0 | HPND | 图片处理 |
| [lxml](https://github.com/lxml/lxml) | ≥6.0 | BSD-3-Clause | XML/HTML 解析 |
| [oletools](https://github.com/decalage2/oletools) | ≥0.60 | Apache 2.0 | MSG 文件解析 |
| [six](https://github.com/benjaminp/six) | ≥1.17 | MIT | Python 2/3 兼容 |

**注意**：all-MiniLM-L6-v2 模型采用 Apache 2.0 许可证，但训练数据包含 MS MARCO 等非商业可用数据集。如需商业使用，请注意相关限制。

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
