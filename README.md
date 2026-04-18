# Ariadne · 阿里阿德涅

> 阿里阿德涅（Ariadne）是希腊神话中帮助忒修斯穿越迷宫的女神，手持线团引导归途。
> 正如我们的系统 —— 织入你所有的知识，在记忆的迷宫中为你指引方向。

**Ariadne** 是一个跨源 AI 记忆与知识织入系统，将来自不同来源的文档、对话、代码统一摄入，构建可检索的知识网络。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](pyproject.toml)

---

## 目录 / Table of Contents

- [功能特性 / Features](#功能特性--features)
- [支持格式 / Supported Formats](#支持格式--supported-formats)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [架构设计 / Architecture](#架构设计--architecture)
- [开发路线 / Roadmap](#开发路线--roadmap)
- [项目致谢 / Credits](#项目致谢--credits)

---

## 功能特性 / Features

| 特性 | 描述 |
|------|------|
| 🗂️ **多源摄入** | 同时支持 Markdown、Word、PPT、PDF、TXT、思维导图、代码等多种格式 |
| 🔍 **语义搜索** | 基于向量数据库的语义相似度搜索，返回最相关结果 |
| 🧠 **记忆持久化** | ChromaDB 本地持久化存储，数据完全归你所有 |
| 🔗 **知识图谱**（规划中）| 自动识别实体与关系，构建跨源知识关联网络 |
| 🤖 **AI 增强**（P2 规划中）| 调用 DeepSeek / Claude 等主流 AI 接口进行增强检索与智能摘要 |
| 🧮 **知识图谱**（P3 规划中）| 实体识别 + 跨源关联 + 时间线视图 |
| 📚 **媒体支持**（P4 规划中）| EPUB/MOBI 电子书、图片 OCR、扫描 PDF、学术文献元数据 |
| 🔌 **MCP Server**（P5 规划中）| 提供 MCP 工具接口，可接入 Claude Code / WorkBuddy / Cursor |

---

## 支持格式 / Supported Formats

| 格式 | 扩展名 | 摄入器 | 说明 |
|------|--------|--------|------|
| Markdown | `.md` | `MarkdownIngestor` | 使用标题切分语义块 |
| Word | `.docx` | `WordIngestor` | 提取段落，保留样式层级 |
| PPT | `.pptx` | `PPTIngestor` | 每张幻灯片为一 Chunk |
| PDF | `.pdf` | `PDFIngestor` | PyMuPDF 文本提取，智能合并短页 |
| 纯文本 | `.txt` | `TxtIngestor` | 按段落切分 |
| 对话导出 | `.json` | `ConversationIngestor` | 支持 ChatGPT/Claude/DeepSeek JSON 导出 |
| 思维导图 | `.mm` / `.xmind` | `MindMapIngestor` | 保留树形结构作为上下文 |
| 代码 | `.py/.java/.cpp/.js` | `CodeIngestor` | AST/正则提取函数、类、文档字符串 |

> 📖 **第四阶段规划**: EPUB / MOBI 电子书、图片 OCR、扫描 PDF 识别、学术文献元数据（BibTeX / RIS）

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

```bash
# 摄入单个文件
ariadne ingest ./my_notes.md

# 摄入整个目录（含子目录）
ariadne ingest ./my_research/ -r

# 语义搜索
ariadne search "犹太教与基督教的共同伦理观念"

# 查看系统信息
ariadne info --stats
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

## 架构设计 / Architecture

```
ariadne-memory/
├── ariadne/
│   ├── __init__.py          # 公共 API 入口
│   ├── cli.py                # 命令行工具
│   ├── ingest/               # 摄入模块
│   │   ├── base.py          # BaseIngestor 抽象基类 + Document 数据模型
│   │   ├── markdown.py       # Markdown 摄入器
│   │   ├── word.py          # Word (.docx) 摄入器
│   │   ├── ppt.py           # PowerPoint (.pptx) 摄入器
│   │   ├── pdf.py           # PDF 摄入器
│   │   ├── txt.py           # 纯文本摄入器
│   │   ├── conversation.py  # 对话历史摄入器
│   │   ├── mindmap.py       # 思维导图摄入器
│   │   └── code.py          # 代码注释摄入器
│   ├── memory/              # 向量记忆存储层
│   │   └── store.py         # ChromaDB 向量存储实现
│   ├── llm/                 # LLM 统一接口（第二阶段）
│   ├── graph/               # 知识图谱（第三阶段）
│   └── mcp/                 # MCP Server（第五阶段）
└── tests/
```

### 设计原则 / Design Principles

1. **统一接口**: 所有摄入器实现 `BaseIngestor`，对存储层透明
2. **可插拔存储**: VectorStore 抽象后端，ChromaDB 为默认实现
3. **本地优先**: 所有数据存储在本地，无需联网（LLM API 调用除外）
4. **增量摄入**: 相同文件重复摄入时执行 upsert，智能去重

---

## 开发路线 / Roadmap

### 第一阶段 MVP ✅ **进行中**
- [x] 项目骨架与目录结构
- [x] 8 种文档格式摄入器（Markdown/Word/PPT/PDF/TXT/对话/思维导图/代码）
- [x] ChromaDB 向量存储层
- [x] CLI 工具（ingest / search / info）
- [x] 中英双语 README
- [ ] 核心数据模型（Document / Entity / Relation）确认
- [ ] ChromaDB 运行时验证
- [ ] 各摄入器单元测试
- [ ] 批量摄入与进度条支持
- [ ] **Tkinter GUI 原型**（CLI/GUI 双入口）

### 第二阶段 LLM 增强（规划中）
- [ ] LLM 统一抽象接口（DeepSeek / Claude / Qwen / ChatGPT / Gemini / Grok）
- [ ] `config.json` 配置文件管理
- [ ] LLM 增强语义重排（Reranker）
- [ ] 智能动态分块（语义切分替代固定长度）

### 第三阶段 知识图谱（规划中）
- [ ] 实体识别 + 关系抽取（LLM API 驱动）
- [ ] NetworkX + SQLite 图数据库
- [ ] 跨源关联查询
- [ ] 知识时间线视图

### 第四阶段 媒体支持与学术工具（规划中）
- [ ] EPUB / MOBI 电子书摄入（ebooklib）
- [ ] 图片摄入（截图、照片等元数据提取）
- [ ] 图片 / 扫描版 PDF OCR（pytesseract / RapidOCR）
- [ ] 学术文献元数据（BibTeX / RIS）管理

### 第五阶段 MCP Server（规划中）
- [ ] FastMCP 实现
- [ ] 核心工具：`memory_write` / `memory_search` / `graph_query` / `timeline_view`
- [ ] 接入 Claude Code / WorkBuddy / Cursor 验证

### 第六阶段 社区运营与迭代（持续）
- [x] GitHub 正式发布
- [ ] 版本化发布（v0.1.0-alpha）
- [ ] **PyQt6 GUI 重写**（替代 Tkinter 原型）
- [ ] HackerNews / Reddit 投递
- [ ] 中文社区传播（掘金 / 知乎 / CSDN）

---

## 项目致谢 / Credits

### 核心灵感 / Core Inspiration

**MemPalace** 是 Ariadne 最重要的灵感来源之一。MemPalace 提出了"AI 记忆"的概念，证明本地向量存储 + 语义搜索可以极大地增强 AI 工具的上下文能力。

> "Ariadne's pluggable ingestor and storage architecture is inspired by [MemPalace](https://github.com/MemPalace/mempalace). MemPalace is released under the MIT License."

### 技术栈 / Tech Stack

| 组件 | 技术 | 用途 |
|------|------|------|
| 向量存储 | [ChromaDB](https://github.com/chroma-core/chroma) | 语义向量检索 |
| 文档解析 | PyMuPDF, python-docx, python-pptx | PDF/Word/PPT 解析 |
| 代码解析 | Python AST, 正则表达式 | 函数/类/注释提取 |
| CLI 框架 | Click | 命令行界面 |
| 图数据库 | NetworkX, SQLAlchemy | 知识图谱（P3）|

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
