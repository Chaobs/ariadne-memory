# Ariadne 使用指南 / User Guide

> 全面介绍 Ariadne 命令行工具和图形界面的所有功能 / Complete guide to Ariadne CLI and GUI.

---

## 目录 / Table of Contents

- [基础概念 / Basic Concepts](#基础概念--basic-concepts)
- [基础用法 / Basic Usage](#基础用法--basic-usage)
- [CLI 命令详解 / CLI Command Reference](#cli-命令详解--cli-command-reference)
- [GUI 使用指南 / GUI Usage](#gui-使用指南--gui-usage)
- [小技巧 / Tips & Tricks](#小技巧--tips--tricks)
- [故障排查 / Troubleshooting](#故障排查--troubleshooting)

---

## 基础概念 / Basic Concepts

### 记忆系统 (Memory System)

Ariadne 支持多个独立的**记忆系统**，每个记忆系统就像一个独立的笔记本：

| 概念 | 说明 |
|------|------|
| **记忆系统** | 独立存储的知识库，有自己的目录和集合 |
| **默认系统** | 名为 "default" 的系统，首次运行自动创建 |
| **数据存储** | 每个系统存储在 `~/.ariadne/memories/{name}/` |
| **Manifest** | `manifest.json` 记录所有记忆系统元数据 |

### 工作原理 / How It Works

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
│  │  │ default │  │research │  │ personal│  ...        │    │
│  │  └─────────┘  └─────────┘  └─────────┘              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 是否需要 LLM API？/ LLM API Required?

**基础功能（摄入 + 搜索）不需要 LLM API：**
- 使用 ChromaDB 内置的 `all-MiniLM-L6-v2` 模型生成向量
- 所有数据本地存储，无需网络请求
- 语义搜索基于向量相似度计算

**LLM API 可选用于：**
- 知识图谱实体识别和关系抽取（P3）
- LLM 增强语义重排（P2）
- 智能动态分块（P2）

---

## 基础用法 / Basic Usage

### 调用方式 / Invocation

```bash
# CLI (推荐)
python -m ariadne.cli [COMMAND] [OPTIONS]

# GUI
python -m ariadne.cli gui
```

### 快速开始 / Quick Start

```bash
# 1. 查看所有记忆系统
python -m ariadne.cli memory list

# 2. 创建新记忆系统
python -m ariadne.cli memory create "Research Notes"

# 3. 摄入文件到指定记忆系统
python -m ariadne.cli ingest ./papers/ -r -m "Research Notes"

# 4. 搜索
python -m ariadne.cli search "AI ethics" -m "Research Notes"

# 5. 查看统计
python -m ariadne.cli info --stats -m "Research Notes"

# 6. 启动 GUI
python -m ariadne.cli gui
```

---

## CLI 命令详解 / CLI Command Reference

### 1. memory — 记忆系统管理

```bash
ariadne memory [COMMAND]
```

#### 子命令 / Subcommands

| 命令 | 说明 |
|------|------|
| `list` | 列出所有记忆系统 |
| `create <name>` | 创建新记忆系统 |
| `rename <old> <new>` | 重命名 |
| `delete <name>` | 删除记忆系统 |
| `merge <sources...> <new>` | 合并多个系统 |
| `info [name]` | 查看系统信息 |
| `clear [name]` | 清除所有文档 |

#### 示例 / Examples

```bash
# 列出所有记忆系统
ariadne memory list
# Output:
#    default: 42 documents
#      research: 156 documents
#      personal: 28 documents

# 创建新记忆系统
ariadne memory create "My Research" -d "Academic papers and notes"

# 重命名
ariadne memory rename "My Research" "Academic"

# 删除（需要确认）
ariadne memory delete "Old Notes"

# 删除（跳过确认）
ariadne memory delete "Old Notes" --yes

# 合并多个系统
ariadne memory merge research personal "All Knowledge"

# 合并并删除原系统
ariadne memory merge research personal "All Knowledge" --delete

# 查看系统信息
ariadne memory info research

# 清除文档
ariadne memory clear research --yes
```

---

### 2. ingest — 摄入文件

```bash
ariadne ingest <PATH> [OPTIONS]
```

#### 选项 / Options

| 选项 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--recursive` | `-r` | 标志 | False | 递归子目录 |
| `--verbose` | `-v` | 标志 | False | 详细输出 |
| `--batch-size` | `-b` | 整数 | 100 | 批处理大小 |
| `--memory` | `-m` | 字符串 | default | 目标记忆系统 |

#### 示例 / Examples

```bash
# 摄入到默认系统
ariadne ingest ./notes.md

# 摄入到指定系统
ariadne ingest ./papers/ -r -m "Research"

# 详细输出
ariadne ingest ./docs/ -r -v

# 指定批处理大小
ariadne ingest ./books/ -b 50 -m "Books"
```

---

### 3. search — 语义搜索

```bash
ariadne search <QUERY> [OPTIONS]
```

#### 选项 / Options

| 选项 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--top-k` | `-k` | 整数 | 5 | 返回结果数 |
| `--verbose` | `-v` | 标志 | False | 显示元数据 |
| `--memory` | `-m` | 字符串 | default | 搜索的记忆系统 |

#### 示例 / Examples

```bash
# 基本搜索
ariadne search "machine learning"

# 更多结果
ariadne search "deep learning" -k 10

# 详细输出
ariadne search "neural networks" -v

# 搜索指定系统
ariadne search "religion ethics" -m "Research"
```

---

### 4. info — 系统信息

```bash
ariadne info [OPTIONS]
```

#### 选项 / Options

| 选项 | 说明 |
|------|------|
| `--stats` | 显示文档统计 |
| `--memory` | 指定记忆系统 |

#### 示例 / Examples

```bash
ariadne info
ariadne info --stats
ariadne info --stats -m "Research"
```

---

### 5. gui — 图形界面

```bash
ariadne gui
```

启动完整的图形界面，支持所有 CLI 功能。

---

## GUI 使用指南 / GUI Usage

### 界面布局 / Layout

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

### 功能说明 / Features

#### 记忆系统管理 (Memory Systems Tab)

| 操作 | 说明 |
|------|------|
| **下拉选择** | 在顶部切换当前记忆系统 |
| **Refresh** | 刷新系统列表和统计 |
| **New** | 创建新记忆系统 |
| **Rename** | 重命名当前系统 |
| **Delete** | 删除当前系统 |
| **Merge** | 合并多个系统 |

#### 摄入功能 (Ingest Tab)

| 操作 | 说明 |
|------|------|
| **Add Files** | 添加单个或多个文件 |
| **Add Folder** | 添加文件夹（支持递归） |
| **Remove Selected** | 移除选中的文件 |
| **Clear All** | 清空文件列表 |
| **Ingest All** | 开始摄入所有文件 |

**选项：**
- ☑ Recursive - 递归子目录
- ☑ Verbose - 详细输出

#### 搜索功能 (Search Tab)

| 操作 | 说明 |
|------|------|
| **搜索框** | 输入查询语句，按回车搜索 |
| **Results (k)** | 调整返回结果数量 |
| ☑ Show metadata - 显示文档元数据 |

#### 信息功能 (Info Tab)

| 操作 | 说明 |
|------|------|
| **Refresh Info** | 刷新系统信息 |
| **View All Systems** | 查看所有系统列表 |
| **Clear This System** | 清除当前系统文档 |

---

## 小技巧 / Tips & Tricks

### 1. 多记忆系统工作流 / Multi-Memory Workflow

```bash
# 为不同项目创建独立记忆系统
ariadne memory create "PhD Research" -d "Dissertation materials"
ariadne memory create "Trading Notes" -d "Crypto and stock analysis"
ariadne memory create "Language Learning"

# 分类摄入
ariadne ingest ./papers/ -r -m "PhD Research"
ariadne ingest ./charts/ -m "Trading Notes"
ariadne ingest ./vocabulary/ -m "Language Learning"
```

### 2. 系统合并 / System Merging

```bash
# 将多个系统合并为一个
ariadne memory merge "old_notes" "temp" "consolidated"

# 合并并删除原系统（清理）
ariadne memory merge old_notes temp archive --delete
```

### 3. 数据备份 / Backup

```bash
# 备份整个记忆库
cp -r ~/.ariadne/memories ~/.ariadne/memories_backup

# 导出特定系统
ariadne memory export research ./backup/research_memory
```

### 4. 性能优化 / Performance

| 场景 | 建议 |
|------|------|
| 大量文件 | 使用 `-b 200` 增加批处理大小 |
| 首次摄入 | 使用 `-r -v` 查看处理进度 |
| 快速搜索 | 保持系统精简，定期清理无用文档 |

### 5. Shell 别名 / Shell Aliases

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc

# 核心命令
alias ariadne='python -m ariadne.cli'
alias ari='python -m ariadne.cli'

# 记忆系统操作
alias ari-list='ariadne memory list'
alias ari-new='ariadne memory create'
alias ari-del='ariadne memory delete'

# 快速操作
alias ari-info='ariadne info --stats'
alias ari-ingest='ariadne ingest'
alias ari-search='ariadne search'

# 使用示例
ari-list
ari-new "My Project"
ari-info -m "My Project"
ari-ingest ./notes.md -m "My Project"
ari-search "query" -m "My Project"
```

### 6. GUI 快捷操作

| 操作 | 快捷键 |
|------|--------|
| 搜索 | Enter（在搜索框中） |
| 添加文件 | Ctrl+O |
| 退出 | Ctrl+Q |

---

## 故障排查 / Troubleshooting

### 常见问题 / Common Issues

| 问题 | 解决方案 |
|------|----------|
| "No supported files found" | 检查文件扩展名是否匹配支持列表 |
| 搜索无结果 | 确认文件已成功摄入 (`ariadne info --stats`) |
| 编码错误 | 确保文件是 UTF-8 编码 |
| 记忆系统不存在 | 使用 `memory create` 创建新系统 |
| 无法删除默认系统 | 默认系统无法删除，这是设计保护 |

### 重置 / Reset

```bash
# 清除特定系统
ariadne memory clear <system_name> --yes

# 删除并重建
ariadne memory delete <system_name> --yes
ariadne memory create <system_name>
```

### 数据位置 / Data Location

```bash
# 默认数据目录
~/.ariadne/memories/

# 结构
~/.ariadne/memories/
├── manifest.json          # 系统元数据
├── default/              # 默认记忆系统
│   └── (chroma db files)
├── research/             # 研究记忆系统
│   └── (chroma db files)
└── ...
```

---

## 相关链接 / Related Links

- [README.md](README.md) - 项目介绍
- [Architecture](README.md#架构设计--architecture) - 架构设计
- [Roadmap](README.md#开发路线--roadmap) - 开发路线

---

*"Ariadne — weave your knowledge, navigate the maze of memory."*
