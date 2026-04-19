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
- [CLI 使用指南 / CLI Usage](#cli-使用指南--cli-usage)
- [架构设计 / Architecture](#架构设计--architecture)
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
| 📚 **媒体支持** | EPUB/MOBI 电子书、图片 OCR、扫描 PDF、学术文献元数据 | ✅ |
| 🔌 **MCP Server** | 提供 MCP 工具接口，可接入 Claude Code / WorkBuddy / Cursor | ✅ |
| 🖥️ **双入口** | CLI 和 GUI 两种界面，支持所有相同功能 | ✅ |
| 🌍 **多语言** | 支持 8 种语言（中文简繁体、日语、英、法、西、俄、阿） | ✅ |
| 📝 **智能摘要** | LLM 驱动的多语言摘要生成，支持指定输出语言 | ✅ |
| 📊 **可视化** | 知识图谱交互式可视化（HTML / DOT / Mermaid） | ✅ |
| 📤 **多格式导出** | 支持 Markdown、HTML、Word、PDF 格式导出 | ✅ |
| 📦 **本地化依赖** | 第三方库本地化，版本一致性好 | ✅ |
| 🎯 **二进制支持** | 自动处理二进制文件，提取文件名作为知识引用 | ✅ |

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
# 双击 ariadne-cli.bat 打开命令行
# 双击 ariadne-gui.bat 打开图形界面
```

**或使用命令行：**
```bash
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
python -m ariadne.cli memory merge old_notes temp "Consolidated"

# 启动 GUI
python -m ariadne.cli gui
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
| `gui` | 启动图形界面 | `ariadne gui` |
| `memory list` | 列出所有记忆系统 | `ariadne memory list` |
| `memory create` | 创建新记忆系统 | `ariadne memory create "Research"` |
| `memory rename` | 重命名记忆系统 | `ariadne memory rename old new` |
| `memory delete` | 删除记忆系统 | `ariadne memory delete old` |
| `memory merge` | 合并记忆系统 | `ariadne memory merge a b new` |
| `config show` | 显示当前配置 | `ariadne config show` |
| `config set` | 设置配置项 | `ariadne config set llm.provider deepseek` |
| `config test` | 测试 LLM 连接 | `ariadne config test` |
| `config set-api-key` | 设置 API 密钥 | `ariadne config set-api-key deepseek sk-xxxxx` |
| `advanced summarize` | 生成摘要 | `ariadne advanced summarize "AI"` |
| `advanced graph` | 知识图谱 | `ariadne advanced graph -f dot` |

---

## 架构设计 / Architecture

```
ariadne/
├── __init__.py              # 公共 API 入口（自动初始化 vendor）
├── cli.py                   # 命令行工具
├── gui.py                  # Tkinter GUI 图形界面
├── config.py               # 统一配置系统
├── advanced.py             # 高级功能（摘要/可视化/导出）
├── i18n.py                 # 多语言国际化支持（8种语言）
├── ingest/                 # 摄入模块
│   ├── base.py             # BaseIngestor 抽象基类 + Document 数据模型
│   ├── markdown.py        # Markdown 摄入器
│   ├── word.py            # Word (.docx) 摄入器
│   ├── ppt.py             # PowerPoint (.pptx) 摄入器
│   ├── pdf.py             # PDF 摄入器
│   ├── txt.py             # 纯文本摄入器
│   ├── conversation.py    # 对话历史摄入器
│   ├── mindmap.py         # 思维导图摄入器
│   ├── code.py            # 代码注释摄入器
│   ├── excel.py           # Excel 摄入器
│   ├── csv.py             # CSV 摄入器
│   ├── binary.py          # 二进制文件摄入器
│   ├── epub.py            # EPUB 电子书摄入器
│   ├── image.py           # 图片/OCR 摄入器
│   ├── academic.py        # BibTeX/RIS 摄入器
│   ├── web.py             # 网页摄入器
│   ├── email.py           # 邮件摄入器
│   └── media.py          # 视频/音频摄入器
├── memory/                # 向量记忆存储层
│   ├── store.py          # ChromaDB 向量存储实现
│   └── manager.py        # 多记忆系统管理器
├── llm/                   # LLM 统一接口
│   ├── base.py           # BaseLLM 抽象基类
│   ├── factory.py       # LLM 工厂 + ConfigManager
│   ├── providers.py     # 各提供商实现（9个提供商）
│   ├── reranker.py      # 语义重排
│   └── chunker.py       # 智能分块
├── graph/                 # 知识图谱
│   ├── models.py        # Entity/Relation 数据模型
│   ├── extractor.py    # 实体/关系抽取
│   ├── storage.py      # NetworkX + SQLite 存储
│   └── query.py        # 图查询接口
├── mcp/                   # MCP Server
│   ├── server.py       # MCP Server 核心实现
│   ├── tools.py        # MCP Tools
│   ├── resources.py   # MCP Resources
│   └── prompts.py     # MCP Prompts
└── locale/               # 国际化翻译文件（8种语言）

vendor/                    # 第三方库本地化
├── __init__.py           # 自动初始化脚本
├── packages/             # pip whl 包
└── models/               # 本地模型缓存（all-MiniLM-L6-v2）
```

---

## 开发路线 / Roadmap

### 第一阶段 MVP ✅ **已完成**
- [x] 项目骨架与目录结构
- [x] 10 种文档格式摄入器（Markdown/Word/PPT/PDF/TXT/对话/思维导图/代码/Excel/CSV）
- [x] ChromaDB 向量存储层
- [x] CLI 工具（ingest / search / info）
- [x] 中英双语 README
- [x] 核心数据模型（Document / Entity / Relation）确认
- [x] ChromaDB 运行时验证
- [x] 各摄入器单元测试
- [x] 批量摄入与进度条支持
- [x] **Tkinter GUI 原型**（CLI/GUI 双入口）

### 第二阶段 LLM 增强 ✅ **已完成**
- [x] LLM 统一抽象接口（DeepSeek / Claude / Qwen / ChatGPT / Gemini / Grok）
- [x] `config.json` 配置文件管理
- [x] LLM 增强语义重排（Reranker）
- [x] 智能动态分块（SemanticChunker 替代固定长度）
- [x] 新增 Kimi / MiniMax / GLM 提供商（9个提供商总计）

### 第三阶段 知识图谱 ✅ **已完成**
- [x] 实体识别 + 关系抽取（LLM API 驱动）
- [x] NetworkX + SQLite 图数据库
- [x] 跨源关联查询
- [x] 知识时间线视图
- [x] 交互式图谱可视化（HTML/DOT/Mermaid格式）

### 第四阶段 媒体支持与学术工具 ✅ **已完成**
- [x] EPUB / MOBI 电子书摄入（ebooklib）
- [x] 图片摄入（截图、照片等元数据提取）
- [x] 图片 / 扫描版 PDF OCR（pytesseract / RapidOCR）
- [x] 学术文献元数据（BibTeX / RIS）管理
- [x] 网页链接摄入（抓取标题、正文、元数据）
- [x] 电子邮件摄入（EML/MBOX 解析）
- [x] 视频文件摄入（提取字幕/音频转录/关键帧截图）
- [x] 音频文件摄入（音乐/播客语音转文字）

### 第五阶段 MCP Server ✅ **已完成**
- [x] AriadneMCPServer 核心实现（支持 stdio / HTTP 传输）
- [x] MCP Tools：`ariadne_search` / `ariadne_ingest` / `ariadne_graph_query` / `ariadne_stats`
- [x] MCP Resources：`collections` / `stats` / `config` / `graph`
- [x] MCP Prompts：`search` / `ingest` / `graph` / `context` / `compare`
- [x] Claude Desktop / Cursor 集成配置示例
- [x] 详细使用文档 (`docs/MCP.md`)

### v0.3.0 增强版 ✅ **已完成**
- [x] 第三方库本地化（vendor目录）
- [x] 模型缓存本地化（all-MiniLM-L6-v2）
- [x] 二进制文件处理（提取文件名为知识引用）
- [x] 扩展 LLM 提供商示例（config.sample.json）
- [x] 快捷入口脚本（ariadne-cli.bat / ariadne-gui.bat）
- [x] 日语支持（ja locale）
- [x] .gitignore 更新（config.json 不推送）

### 第六阶段 社区运营与迭代（持续）
- [x] GitHub 正式发布 v0.2.0
- [ ] 版本化发布（v0.3.0+）
- [ ] **PyQt6 GUI 重写**（替代 Tkinter 原型）🔨 进行中
- [ ] HackerNews / Reddit 投递
- [ ] 中文社区传播（掘金 / 知乎 / CSDN）

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
| [astor](https://github.com/simonpercivall/astor) | ≥0.8.1 | BSD-3-Clause | AST 解析 |
| [pathspec](https://github.com/cpburnz/python-pathspec) | ≥0.11.0 | MPL-2.0 | 路径匹配 |

**注意**：all-MiniLM-L6-v2 模型采用 Apache 2.0 许可证，但训练数据包含 MS MARCO 等非商业可用数据集。如需商业使用，请注意相关限制。

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
