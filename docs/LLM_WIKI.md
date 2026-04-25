# LLM Wiki — Karpathy 风格持久化知识库

> 基于 [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## 概述

LLM Wiki 是 Ariadne 的高级知识组织功能，遵循 Karpathy 的三层知识架构：

```
Raw Sources（原始资料，不可变）→ Wiki（LLM 生成）→ Schema（规则配置）
```

与向量记忆系统（ChromaDB）不同，Wiki 提供的是 **结构化、可编辑、可持续演进** 的知识体。

## 核心概念

### 三层架构

| 层级 | 说明 | 持久化位置 |
|------|------|-----------|
| **Raw Sources** | 原始文件（PDF、Markdown、图片等），只读 | `raw/sources/` |
| **Wiki** | LLM 从源文档生成的知识点页面，双向链接 | `wiki/content/` |
| **Schema** | Wiki 的结构规则和目标说明 | `schema.md`, `purpose.md` |

### 三个核心操作

| 操作 | 说明 | CLI 命令 |
|------|------|---------|
| **Ingest** | 两步 Chain-of-Thought 摄入 | `ariadne wiki ingest <file>` |
| **Query** | Wiki 知识库问答 | `ariadne wiki query <question>` |
| **Lint** | 结构 + 语义健康检查 | `ariadne wiki lint` |

## 目录结构

```
my-wiki/
├── raw/
│   ├── sources/       ← 放置源文档（只读）
│   └── assets/        ← 图片和附件
├── wiki/
│   ├── index.md      ← 自动生成的主题索引
│   ├── log.md        ← 摄入操作日志（含 SHA256 缓存键）
│   ├── overview.md   ← Wiki 总览摘要
│   ├── content/      ← 知识点页面（概念、实体、比较等）
│   │   ├── concepts/
│   │   ├── entities/
│   │   ├── comparisons/
│   │   └── sources/
│   └── queries/      ← 存档的问答（含引用）
├── schema.md         ← Wiki 结构规则（告诉 LLM 如何组织页面）
└── purpose.md       ← Wiki 目标和宗旨
```

## 摄入流程（Ingest）

### 两步 Chain-of-Thought

Ariadne 的摄入采用两步 LLM 处理，避免直接摘要导致的幻觉：

**Step 1 — 分析（Analysis）**
- LLM 阅读源文档
- 提取关键实体、概念、关系
- 生成结构化分析（不生成 Wiki 页面）

**Step 2 — 生成（Generation）**
- LLM 接收结构化分析
- 生成 Wiki 页面（`---FILE: path --- ... ---END FILE---` 块）
- 每个块对应一个 Wiki 页面

### 增量缓存

每次摄入后，结果以源文件 SHA256 哈希为键缓存到 `.ariadne-wiki-cache/`。

- 相同文件 → 跳过摄入（除非 `--force`）
- 修改过的文件 → 重新摄入
- 支持 `log.md` 查看历史缓存

### CLI 使用

```bash
# 初始化 Wiki 项目
ariadne wiki init my-wiki

# 摄入单个文件（两步 CoT）
ariadne wiki ingest raw/papers/ml-survey.pdf -p my-wiki

# 强制重新摄入（忽略缓存）
ariadne wiki ingest raw/papers/ml-survey.pdf -p my-wiki --force

# 批量摄入目录
for f in raw/sources/*.pdf; do
    ariadne wiki ingest "$f" -p my-wiki
done

# 查看摄入日志
cat my-wiki/wiki/log.md
```

## Web UI 使用指南

> **v0.7.1 新增**: Project Directory 目录选择器、Ingest 文件选择器、帮助按钮、统一按钮样式

### 快速开始

1. **设置 Project Directory** — 点击 📁 图标打开目录选择器，或直接在输入框手动输入路径
2. **保存到最近** — 点击 💾 Save to Recent，路径将出现在「🕒 最近使用」下拉菜单中
3. **初始化项目** — 点击 📋 Initialized Project，跳转 Overview 标签，输入名称后点击 ✨ Initialize
4. **摄入文档** — 切换到 📥 Ingest，点击 📂 选择文件，或手动输入路径，点击 Ingest into Wiki
5. **提问查询** — 切换到 ❓ Query，输入问题，点击 Ask Wiki

### Web API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/wiki/init` | 初始化项目（JSON body: `project_path`, `name`） |
| `POST` | `/api/wiki/ingest` | 摄入源文件（JSON body: `source_path`, `project_path`） |
| `POST` | `/api/wiki/query` | 问答（JSON body: `question`, `project_path`） |
| `POST` | `/api/wiki/lint` | Lint 检查 |
| `GET` | `/api/wiki/pages` | 列出页面 |
| `GET` | `/api/wiki/fs/browse` | 文件系统浏览（`?path=...&mode=dir\|file`） |
| `POST` | `/api/wiki/projects/save` | 保存到最近（JSON body: `project_path`） |



## 问答流程（Query）

1. 在 Wiki 页面中检索相关页面（关键词 + 标题匹配）
2. 将相关页面内容作为上下文发给 LLM
3. LLM 生成综合回答，附带引用（`[[页面名]]` 格式）
4. 可选：将问答存档到 `wiki/queries/`

### CLI 使用

```bash
# 基本问答
ariadne wiki query "这篇论文的主要发现是什么？" -p my-wiki

# 保存问答到 Wiki
ariadne wiki query "对比 RAG 和 Fine-tuning" -p my-wiki --save
```

### Web API

```bash
POST /api/wiki/query
Body: {
  "question": "主要发现是什么？",
  "project_dir": "/path/to/my-wiki",
  "save_to_wiki": true
}
```

## 健康检查（Lint）

### 结构检查（Structural）

| 检查项 | 说明 |
|--------|------|
| **孤立页面（Orphan）** | 没有其他页面链接到它 |
| **断链（Broken Link）** | `[[wikilink]]` 指向不存在的页面 |
| **无外链（No Outlinks）** | 页面没有链接到其他页面 |

### 语义检查（Semantic）

需要 LLM 配置，使用 LLM 检测：

| 检查项 | 说明 |
|--------|------|
| **矛盾（Contradiction）** | 同一主题的两个页面说法冲突 |
| **过时（Stale）** | 页面内容与源文档不符 |
| **缺失页面（Missing）** | 存在链接但无对应页面 |
| **建议（Suggestion）** | LLM 主动提出的改进建议 |

### CLI 使用

```bash
# 完整检查（结构 + 语义）
ariadne wiki lint -p my-wiki

# 仅结构检查（不需要 LLM）
ariadne wiki lint -p my-wiki --mode structural

# 仅语义检查
ariadne wiki lint -p my-wiki --mode semantic
```

## Obsidian 导入

### 支持的语法转换

| Obsidian 语法 | 转换结果 |
|--------------|---------|
| `[[wikilink]]` | `[名称](/path/to/page)` |
| `[[wikilink\|alias]]` | `[alias](/path/to/page)` |
| `==highlight==` | `**highlight**` |
| `#tag` | 保留（YAML frontmatter 中记录） |
| `![[embed]]` | 保留为原始链接 |
| YAML frontmatter | 保留并标准化 |
| Callout 语法（`>`） | 保留原样 |

### CLI 使用

```bash
# 导入 Obsidian 笔记库
ariadne wiki ingest-vault /path/to/obsidian/vault -p my-wiki

# 导入后立即执行 LLM 摄入
ariadne wiki ingest-vault /path/to/vault -p my-wiki --llm-ingest
```

### Web API

```bash
POST /api/wiki/ingest-vault
Body: {
  "vault_path": "/path/to/obsidian/vault",
  "project_dir": "/path/to/my-wiki",
  "llm_ingest": false
}
```

## Wiki 页面格式

### YAML Frontmatter

每个 Wiki 页面都有 YAML frontmatter：

```yaml
---
type: concept           # source | entity | concept | comparison | query | synthesis | index | log | overview
title: "机器学习优化"
created: 2026-04-23
updated: 2026-04-23
tags: [机器学习, 优化, 深度学习]
related: [梯度下降, 正则化]
sources: [raw/sources/ml-survey.pdf]
---
```

### Wikilink 语法

页面间使用 `[[pagename]]` 双向链接：

```
这篇技术基于 [[梯度下降]] 算法，与 [[正则化技术]] 有密切关系。
```

## MCP 工具

| 工具名 | 功能 | 场景 |
|--------|------|------|
| `ariadne_wiki_ingest` | 两步 CoT 摄入源文档 | 添加新知识 |
| `ariadne_wiki_query` | Wiki 知识库问答 | 知识检索 |
| `ariadne_wiki_lint` | 结构 + 语义健康检查 | Wiki 维护 |
| `ariadne_wiki_list` | 列出 Wiki 页面 | 浏览知识库 |

### MCP 配置示例

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

## LLM 配置

Wiki 功能需要 LLM 提供商配置。优先级：

1. 调用时传入 `llm_config` 参数
2. 环境变量 `ARIADNE_LLM_*`
3. `~/.ariadne/config.json`

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "max_tokens": 4096,
  "temperature": 0.1
}
```

## 与向量记忆系统的区别

| 特性 | Wiki | 向量记忆（ChromaDB） |
|------|------|---------------------|
| **组织方式** | 手动结构化页面 | 自动向量聚类 |
| **可编辑性** | 完全可编辑 | 只追加，不修改 |
| **双向链接** | ✅ `[[wikilink]]` | ❌ |
| **一致性检查** | ✅ Lint | ❌ |
| **增量缓存** | ✅ SHA256 | ✅ 语义相似度 |
| **适用场景** | 知识体系构建 | 快速语义检索 |

两者可以互补使用：向量系统用于快速检索，Wiki 用于知识体系建设。

## 故障排查

### 摄入失败

```bash
# 检查 LLM 配置
ariadne config show

# 查看详细日志
python -m ariadne wiki ingest <file> -p my-wiki --verbose
```

### 断链问题

```bash
# 运行结构检查
ariadne wiki lint -p my-wiki --mode structural

# 手动创建缺失页面
ariadne wiki create --path content/missing-page -p my-wiki
```

### 缓存问题

```bash
# 查看缓存状态
ls .ariadne-wiki-cache/

# 清除所有缓存（强制重新摄入）
rm -rf .ariadne-wiki-cache/
```
