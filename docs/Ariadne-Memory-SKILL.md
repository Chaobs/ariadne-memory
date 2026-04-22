---
name: ariadne-memory
description: |
  Ariadne Memory System - 跨源AI记忆与知识织入系统。
  提供语义搜索、RAG混合检索、知识图谱、LLM摘要等功能。

  触发词（任一即可）：
  - 记忆、记忆库、搜索记忆
  - 知识库、知识检索、查询知识库
  - RAG、混合搜索、向量搜索
  - 知识图谱、实体关系
  - 摄入文档、添加记忆

triggers:
  # 搜索相关
  - 记忆
  - 记忆库
  - 搜索记忆
  - 查记忆
  - 知识库
  - 知识检索
  - 查询知识库
  - RAG
  - 混合搜索
  - 向量搜索
  - 语义搜索

  # 知识图谱相关
  - 知识图谱
  - 实体关系
  - 图谱查询
  - 实体探索

  # 文档管理相关
  - 摄入文档
  - 添加记忆
  - 存入记忆
  - 上传文档

  # 分析相关
  - 摘要
  - 总结
  - 分析

category: memory
version: 1.0.0
author: Ariadne Team
homepage: https://github.com/Chaobs/ariadne-memory

api:
  base_url: http://localhost:8770
  endpoints:
    search: /api/search/semantic
    rag_search: /api/search/rag
    graph: /api/graph/data
    graph_status: /api/graph/status
    graph_entity: /api/graph/entity/{name}
    summarize: /api/system/summarize
    memory_list: /api/memory/list
    memory_create: /api/memory/create
    ingest_files: /api/ingest/files
    config: /api/config
    system_stats: /api/system/stats
---

# Ariadne Memory Skill

## 概述

Ariadne 是一个跨源AI记忆与知识织入系统，类似于 MemPalace，提供：

- **向量存储**：基于 ChromaDB 的语义搜索
- **知识图谱**：基于 NetworkX + SQLite 的实体关系管理
- **RAG 检索**：BM25 + 向量混合检索 + Cross-encoder 重排序
- **LLM 增强**：DeepSeek、OpenAI 等多提供商支持
- **多格式摄入**：支持 PDF、Word、Markdown、EPUB、图片等 30+ 格式

## 核心能力

### 1. 语义搜索 (semantic_search)

在记忆库中执行语义向量搜索，返回最相关的文档片段。

```
POST /api/search/semantic
Body: {
  "query": "搜索查询",
  "top_k": 5,
  "memory": "default"
}
```

### 2. RAG 混合搜索 (rag_search)

使用 BM25 + 向量混合检索 + 重排序，返回带引用的精准结果。

```
POST /api/search/rag
Body: {
  "query": "搜索查询",
  "top_k": 5,
  "fetch_k": 20,
  "alpha": 0.5,
  "no_rerank": false
}
```

参数说明：
- `alpha`: 向量权重，1.0=仅向量，0.0=仅BM25
- `fetch_k`: 重排序前获取的候选数量
- `no_rerank`: 是否跳过重排序

### 3. 知识图谱查询 (graph_query)

查询实体之间的关系和连接。

```
GET /api/graph/entity/{entity_name}?depth=1
```

返回实体的详细信息和关联关系。

### 4. 图谱探索 (graph_explore)

深度探索知识图谱，发现实体间的路径。

```
POST /api/graph/enrich
Body: {
  "memory": "default",
  "limit": 100,
  "force": false
}
```

### 5. 摘要生成 (summarize)

对搜索结果进行 LLM 摘要总结。

```
POST /api/system/summarize
Body: {
  "query": "搜索查询",
  "memory": "default",
  "output_lang": "zh_CN"
}
```

支持语言：zh_CN, zh_TW, en, fr, es, de, ja, ko

### 6. 文档摄入 (ingest)

将文档摄入到记忆系统。

```
POST /api/ingest/files
FormData: {
  files: [文件列表],
  memory: "default",
  enrich: true
}
```

支持 SSE 流式进度：`POST /api/ingest/files/stream`

## 记忆系统管理

### 创建记忆系统

```
POST /api/memory/create
Body: {
  "name": "research",
  "description": "研究资料"
}
```

### 列出记忆系统

```
GET /api/memory/list
```

### 删除记忆系统

```
DELETE /api/memory/{name}
```

## MCP Server

Ariadne 还提供 MCP Server，可被 Claude Code、Cursor 等 AI 工具直接调用。

### 启动 MCP Server

```bash
ariadne mcp run
# 或 HTTP 模式
ariadne mcp run -t http -p 8765
```

### MCP 工具列表

| 工具名 | 功能 | 场景 |
|--------|------|------|
| ariadne_search | 语义搜索 | 快速查询 |
| ariadne_rag_search | RAG 混合搜索 | 精准问答 |
| ariadne_summarize | 摘要生成 | 内容总结 |
| ariadne_graph_query | 图谱查询 | 关系探索 |
| ariadne_graph_explore | 图谱探索 | 深度发现 |
| ariadne_ingest | 文档摄入 | 添加知识 |
| ariadne_memory_list | 列出记忆 | 查看系统 |
| ariadne_memory_create | 创建记忆 | 新建空间 |
| ariadne_stats | 统计信息 | 系统状态 |
| ariadne_health_check | 健康检查 | 故障排查 |
| ariadne_web_search | 网络搜索 | 补充实时信息 |

## 使用示例

### 示例 1：搜索记忆

```
用户：帮我查一下关于机器学习优化的内容
助手：使用 ariadne_search 搜索"机器学习优化"

请求：
POST /api/search/semantic
{
  "query": "机器学习优化",
  "top_k": 5
}

响应：
{
  "results": [
    {
      "content": "深度学习模型优化技术...",
      "source_path": "ml_optimization.md",
      "score": 0.92
    }
  ]
}
```

### 示例 2：RAG 精准问答

```
用户：用 RAG 搜索"Transformer 架构原理"
助手：使用 ariadne_rag_search 执行混合检索

请求：
POST /api/search/rag
{
  "query": "Transformer 架构原理",
  "top_k": 3,
  "alpha": 0.7,
  "include_citations": true
}

响应：
{
  "results": [
    {
      "content": "Transformer 使用自注意力机制...",
      "source": "transformer_paper.pdf",
      "scores": {
        "combined": 0.95,
        "vector": 0.92,
        "bm25": 0.88
      }
    }
  ],
  "citations": [...]
}
```

### 示例 3：知识图谱探索

```
用户：探索一下"深度学习"相关的实体
助手：使用 ariadne_graph_explore 探索图谱

请求：
GET /api/graph/entity/深度学习?depth=2

响应：
{
  "entity": {
    "name": "深度学习",
    "type": "concept"
  },
  "relations": [
    {
      "type": "related_to",
      "source": {...},
      "target": {"name": "神经网络", "type": "concept"}
    }
  ]
}
```

### 示例 4：摄入新文档

```
用户：把这份 PDF 加入记忆库
助手：使用 ariadne_ingest 摄入文档

请求：
POST /api/ingest/files
FormData: {
  files: [document.pdf],
  memory: "research",
  enrich: true
}

响应：
{
  "docs_added": 15,
  "skipped": 0,
  "errors": []
}
```

## 配置说明

### LLM 提供商配置

```
POST /api/config/llm
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "api_key": "sk-xxxxx"
}
```

支持的提供商：deepseek, openai, anthropic, gemini, groq, ollama, azure, Cohere, Mistral

### 启用高级功能

```
# 启用摘要
ariadne config set advanced.enable_summary true

# 启用重排序
ariadne config set advanced.enable_reranker true

# 设置语言
ariadne config set locale.language zh_CN
```

## 踩坑记录

### ChromaDB Windows 文件锁
删除/重命名记忆时必须调用 `SharedSystemClient.clear_system_cache()`

### UploadFile SSE 问题
SSE 流式响应中 UploadFile 的 SpooledTemporaryFile 在请求结束后被关闭，
必须先将内容读取到临时文件再开始流式响应

### GraphStorage API 限制
只有 `get_neighbors()` 和 `get_relations_between()`，无 `get_relations(entity_id, max_depth)`

## 相关资源

- GitHub: https://github.com/Chaobs/ariadne-memory
- 文档: https://github.com/Chaobs/ariadne-memory#readme
- MemPalace 参考: https://github.com/burningmantech/mempalace
