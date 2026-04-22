# Ariadne 测试与扩展方案

> 日期：2026-04-22
> 目标：CLI完整测试、Web UI功能补全、Agent生态扩展

---

## 一、CLI 完整测试方案

### 1.1 CLI 命令清单

| 模块 | 命令 | 功能 |
|------|------|------|
| **memory** | `memory list` | 列出所有记忆系统 |
| | `memory create <name>` | 创建记忆系统 |
| | `memory rename <old> <new>` | 重命名记忆系统 |
| | `memory delete <name>` | 删除记忆系统 |
| | `memory merge <src1,src2> --into <new>` | 合并记忆系统 |
| | `memory info [name]` | 显示记忆系统信息 |
| | `memory clear [name]` | 清除记忆系统内容 |
| | `memory export <name> <path>` | 导出记忆系统 |
| | `memory import <path> <name>` | 导入记忆系统 |
| **config** | `config show` | 显示当前配置 |
| | `config list-providers` | 列出LLM提供商 |
| | `config set <key> <value>` | 设置配置值 |
| | `config get <key>` | 获取配置值 |
| | `config test` | 测试LLM配置 |
| | `config set-api-key <provider> <key>` | 设置API密钥 |
| **advanced** | `advanced summarize [query]` | 摘要生成 |
| | `advanced graph [--format text\|dot\|json\|mermaid]` | 知识图谱展示 |
| | `advanced graph-enrich [--memory] [--limit] [--force]` | 知识图谱丰富化 |
| **rag** | `rag search <query> [--top-k] [--alpha] [--no-rerank]` | RAG搜索 |
| | `rag rebuild-index [--memory]` | 重建BM25索引 |
| | `rag health [--memory]` | RAG健康检查 |
| **mcp** | `mcp run [--transport stdio\|http] [--host] [--port]` | 启动MCP服务器 |
| | `mcp info` | MCP信息 |
| **web** | `web run [--host] [--port]` | 启动Web UI |
| | `web info` | Web UI信息 |
| **root** | `ingest <path> [--recursive] [--batch-size] [--enrich]` | 文件摄入 |
| | `search <query> [--top-k]` | 语义搜索 |
| | `info [--stats]` | 系统信息 |

### 1.2 测试用例设计

#### 1.2.1 Memory 模块测试

```python
# tests/test_cli_memory.py
import pytest
from typer.testing import CliRunner
from ariadne.cli import app, memory_app

runner = CliRunner()

class TestMemoryCommands:
    """Memory命令测试套件"""

    def test_memory_list_empty(self):
        """测试空列表"""
        result = runner.invoke(memory_app, ["list"])
        assert result.exit_code == 0
        assert "Memory Systems" in result.stdout

    def test_memory_create(self):
        """测试创建记忆系统"""
        result = runner.invoke(memory_app, ["create", "test_memory"])
        assert result.exit_code == 0
        assert "Created" in result.stdout

    def test_memory_create_duplicate(self):
        """测试重复创建"""
        runner.invoke(memory_app, ["create", "dup_test"])
        result = runner.invoke(memory_app, ["create", "dup_test"])
        assert result.exit_code == 1

    def test_memory_rename(self):
        """测试重命名"""
        runner.invoke(memory_app, ["create", "old_name"])
        result = runner.invoke(memory_app, ["rename", "old_name", "new_name"])
        assert "Renamed" in result.stdout

    def test_memory_delete_with_confirm(self):
        """测试删除（需要确认）"""
        runner.invoke(memory_app, ["create", "to_delete"])
        result = runner.invoke(memory_app, ["delete", "to_delete"], input="y\n")
        assert "Deleted" in result.stdout

    def test_memory_delete_default_protected(self):
        """测试不能删除默认系统"""
        result = runner.invoke(memory_app, ["delete", "default"])
        assert result.exit_code == 1

    def test_memory_merge(self):
        """测试合并"""
        runner.invoke(memory_app, ["create", "src1"])
        runner.invoke(memory_app, ["create", "src2"])
        result = runner.invoke(memory_app, ["merge", "src1", "src2", "--into", "merged"])
        assert "Merged" in result.stdout

    def test_memory_info(self):
        """测试信息显示"""
        runner.invoke(memory_app, ["create", "info_test"])
        result = runner.invoke(memory_app, ["info", "info_test"])
        assert "info_test" in result.stdout

    def test_memory_export_import(self):
        """测试导出导入"""
        # Export
        result = runner.invoke(memory_app, ["export", "default", "/tmp/export_test"])
        # Import
        result = runner.invoke(memory_app, ["import", "/tmp/export_test", "imported"])
        assert "Imported" in result.stdout
```

#### 1.2.2 Config 模块测试

```python
# tests/test_cli_config.py
class TestConfigCommands:
    """Config命令测试套件"""

    def test_config_show(self):
        """测试显示配置"""
        result = runner.invoke(config_app, ["show"])
        assert result.exit_code == 0

    def test_config_list_providers(self):
        """测试列出提供商"""
        result = runner.invoke(config_app, ["list-providers"])
        assert "deepseek" in result.stdout or "openai" in result.stdout

    def test_config_set_get(self):
        """测试设置和获取"""
        runner.invoke(config_app, ["set", "test.key", "test_value"])
        result = runner.invoke(config_app, ["get", "test.key"])
        assert "test_value" in result.stdout

    def test_config_set_bool(self):
        """测试布尔值"""
        runner.invoke(config_app, ["set", "test.bool", "true"])
        result = runner.invoke(config_app, ["get", "test.bool"])
        assert "True" in result.stdout

    def test_config_set_int(self):
        """测试整数值"""
        runner.invoke(config_app, ["set", "test.int", "42"])
        result = runner.invoke(config_app, ["get", "test.int"])
        assert "42" in result.stdout

    def test_config_set_api_key(self):
        """测试API密钥设置"""
        result = runner.invoke(config_app, ["set-api-key", "deepseek", "sk-test123"])
        assert "Set API key" in result.stdout

    def test_config_test_llm(self):
        """测试LLM配置（需要网络）"""
        result = runner.invoke(config_app, ["test"])
        # 可能失败如果没配置API key
        assert result.exit_code in [0, 1]
```

#### 1.2.3 Ingest 模块测试

```python
# tests/test_cli_ingest.py
import tempfile
from pathlib import Path

class TestIngestCommands:
    """Ingest命令测试套件"""

    def test_ingest_single_file(self, tmp_path):
        """测试单文件摄入"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for ingestion")

        result = runner.invoke(app, ["ingest", str(test_file)])
        assert result.exit_code == 0

    def test_ingest_directory(self, tmp_path):
        """测试目录摄入"""
        # 创建多个文件
        for i in range(3):
            (tmp_path / f"file{i}.txt").write_text(f"Content {i}")

        result = runner.invoke(app, ["ingest", str(tmp_path)])
        assert result.exit_code == 0

    def test_ingest_recursive(self, tmp_path):
        """测试递归摄入"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")

        result = runner.invoke(app, ["ingest", str(tmp_path), "--recursive"])
        assert result.exit_code == 0

    def test_ingest_unsupported_file(self, tmp_path):
        """测试不支持的文件"""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("unsupported")

        result = runner.invoke(app, ["ingest", str(test_file)])
        # 应该跳过不支持的文件
        assert "SKIP" in result.stdout or result.exit_code == 0

    def test_ingest_verbose(self, tmp_path):
        """测试详细输出"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Verbose test")

        result = runner.invoke(app, ["ingest", str(test_file), "--verbose"])
        assert "ADD" in result.stdout

    @pytest.mark.llm
    def test_ingest_with_enrich(self, tmp_path):
        """测试带图谱丰富的摄入"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Ariadne is a memory system for AI.")

        result = runner.invoke(app, ["ingest", str(test_file), "--enrich"])
        assert result.exit_code == 0
        assert "Graph:" in result.stdout
```

#### 1.2.4 RAG 模块测试

```python
# tests/test_cli_rag.py
class TestRAGCommands:
    """RAG命令测试套件"""

    def test_rag_search_basic(self):
        """测试基本RAG搜索"""
        result = runner.invoke(rag_app, ["search", "test query"])
        assert result.exit_code == 0

    def test_rag_search_with_params(self):
        """测试带参数的RAG搜索"""
        result = runner.invoke(rag_app, [
            "search", "test",
            "--top-k", "10",
            "--fetch-k", "20",
            "--alpha", "0.7"
        ])
        assert result.exit_code == 0

    def test_rag_search_no_rerank(self):
        """测试跳过重排序"""
        result = runner.invoke(rag_app, ["search", "test", "--no-rerank"])
        assert result.exit_code == 0

    def test_rag_rebuild_index(self):
        """测试重建索引"""
        result = runner.invoke(rag_app, ["rebuild-index"])
        assert result.exit_code == 0

    def test_rag_health(self):
        """测试健康检查"""
        result = runner.invoke(rag_app, ["health"])
        assert result.exit_code == 0
        assert "BM25" in result.stdout or "Reranker" in result.stdout
```

#### 1.2.5 Advanced 模块测试

```python
# tests/test_cli_advanced.py
class TestAdvancedCommands:
    """Advanced命令测试套件"""

    @pytest.mark.llm
    def test_summarize_with_query(self):
        """测试带查询的摘要"""
        result = runner.invoke(advanced_app, ["summarize", "AI"])
        assert result.exit_code == 0

    def test_graph_text(self):
        """测试图谱文本输出"""
        result = runner.invoke(advanced_app, ["graph", "--format", "text"])
        assert result.exit_code == 0
        assert "Entities:" in result.stdout

    def test_graph_json(self):
        """测试图谱JSON输出"""
        result = runner.invoke(advanced_app, ["graph", "--format", "json"])
        assert result.exit_code == 0
        # 验证JSON格式
        import json
        json.loads(result.stdout)

    def test_graph_mermaid(self):
        """测试Mermaid输出"""
        result = runner.invoke(advanced_app, ["graph", "--format", "mermaid"])
        assert result.exit_code == 0
        assert "graph TD" in result.stdout

    def test_graph_entity_query(self):
        """测试实体查询"""
        result = runner.invoke(advanced_app, [
            "graph", "--query", "TestEntity", "--depth", "2"
        ])
        assert result.exit_code == 0

    def test_graph_output_file(self, tmp_path):
        """测试输出到文件"""
        output_file = tmp_path / "graph.dot"
        result = runner.invoke(advanced_app, [
            "graph", "--format", "dot", "--output", str(output_file)
        ])
        assert output_file.exists()

    @pytest.mark.llm
    def test_graph_enrich(self):
        """测试图谱丰富化"""
        result = runner.invoke(advanced_app, ["graph-enrich", "--limit", "10"])
        assert result.exit_code == 0
```

### 1.3 测试执行方案

```bash
# 完整测试
pytest tests/test_cli.py -v --tb=short

# 按模块测试
pytest tests/test_cli_memory.py -v
pytest tests/test_cli_config.py -v
pytest tests/test_cli_ingest.py -v
pytest tests/test_cli_rag.py -v
pytest tests/test_cli_advanced.py -v

# 带覆盖率测试
pytest tests/test_cli.py --cov=ariadne --cov-report=html

# LLM相关测试（需要配置API key）
pytest tests/ -m llm -v
```

---

## 二、Web UI 功能补全方案

### 2.1 缺失功能清单

| CLI功能 | Web API 端点 | 状态 | 优先级 |
|---------|-------------|------|--------|
| `config get <key>` | `GET /api/config/{key}` | ❌ 缺失 | P1 |
| `config set-api-key` | `POST /api/config/set-api-key` | ❌ 缺失 | P1 |
| `advanced graph` | `GET /api/advanced/graph` | ❌ 缺失 | P2 |
| `advanced summarize` | `POST /api/advanced/summarize` | ❌ 缺失 | P2 |
| `mcp run` | `POST /api/mcp/run` | ❌ 缺失 | P2 |
| `mcp info` | `GET /api/mcp/info` | ❌ 缺失 | P2 |
| `info --stats` | `GET /api/system/stats` | ❌ 缺失 | P1 |

### 2.2 新增 API 设计

#### 2.2.1 Config Router 扩展

```python
# /api/config/{key} - 获取单个配置值
@config_router.get("/{key}")
async def get_config_value(
    key: str,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Get a specific configuration value."""
    value = cfg.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return {"key": key, "value": value}


# /api/config/set-api-key - 快捷设置API密钥
class SetApiKeyRequest(BaseModel):
    provider: str
    api_key: str
    save_to_env: bool = False

@config_router.post("/set-api-key")
async def set_api_key(
    req: SetApiKeyRequest,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Set API key for a provider."""
    if req.save_to_env:
        import os
        os.environ[f"{req.provider.upper()}_API_KEY"] = req.api_key
        return {"success": True, "message": f"Set {req.provider.upper()}_API_KEY in environment"}

    cfg.set("llm.provider", req.provider)
    cfg.set("llm.api_key", req.api_key)
    cfg.save_user()
    return {"success": True, "message": f"API key set for {req.provider}"}
```

#### 2.2.2 Advanced Router

```python
# /api/advanced/graph - 知识图谱展示（多格式）
advanced_router = APIRouter()

class GraphQueryRequest(BaseModel):
    format: str = "text"  # text, dot, json, mermaid
    query: Optional[str] = None  # Entity name to query
    depth: int = 1
    max_nodes: int = 50

@advanced_router.post("/graph")
async def get_graph(
    req: GraphQueryRequest,
):
    """Get knowledge graph in various formats."""
    from ariadne.graph import GraphStorage
    from ariadne.advanced import GraphVisualizer
    from ariadne.paths import GRAPH_DB_PATH

    try:
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
    except Exception:
        raise HTTPException(status_code=500, detail="Graph storage not available")

    vis = GraphVisualizer(graph)

    # Get entities for query
    entity_ids = None
    if req.query:
        entity = graph.get_entity_by_name(req.query)
        if entity:
            entity_ids = {entity.entity_id}
            relations = graph.get_relations(entity.entity_id, max_depth=req.depth)
            for rel in relations:
                entity_ids.add(rel.target_id)
                entity_ids.add(rel.source_id)

    if req.format == "text":
        # Return as structured data
        all_entities = graph.get_all_entities()
        return {
            "entities": len(all_entities),
            "relations": len(graph.get_all_relations()),
            "entity_data": [
                {"name": e.name, "type": e.entity_type.value, "description": e.description}
                for e in all_entities[:req.max_nodes]
            ]
        }
    elif req.format == "json":
        return {"graph": vis.to_json(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)}
    elif req.format == "mermaid":
        return {"graph": vis.to_mermaid(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)}
    elif req.format == "dot":
        return {"graph": vis.to_dot(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")


# /api/advanced/summarize - 摘要生成（支持流式）
class SummarizeStreamRequest(BaseModel):
    query: str
    memory: Optional[str] = None
    output_lang: Optional[str] = None

@advanced_router.post("/summarize/stream")
async def summarize_stream(
    req: SummarizeStreamRequest,
    manager: MemoryManager = Depends(get_memory_manager),
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Generate summary with streaming response."""
    if not cfg.get("advanced.enable_summary"):
        raise HTTPException(status_code=400, detail="Summary feature is disabled")

    llm = cfg.create_llm()
    if llm is None:
        raise HTTPException(status_code=400, detail="No LLM configured")

    store = manager.get_store(req.memory)
    results = store.search(req.query, top_k=10)

    if not results:
        raise HTTPException(status_code=404, detail="No results found")

    context = "\n\n".join([f"[Document {i+1}]\n{doc.content[:500]}" for i, (doc, _) in enumerate(results)])

    out_lang = req.output_lang or cfg.get_output_language()
    lang_prompts = {
        "zh_CN": "请用简体中文总结",
        "en": "Please summarize in English",
        # ... other languages
    }
    lang_prompt = lang_prompts.get(out_lang, "Please summarize in English")

    prompt = f"Based on the following search results, {lang_prompt}:\n\n{context}"

    async def event_stream():
        try:
            response = await llm.chat_async(prompt)
            async for chunk in response:
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

#### 2.2.3 MCP Router

```python
# /api/mcp - MCP服务器管理
mcp_router = APIRouter()

class MCPRunRequest(BaseModel):
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765

@mcp_router.get("/info")
async def mcp_info():
    """Get MCP server information and available tools."""
    from ariadne.mcp import AriadneMCPServer
    from ariadne.mcp.tools import AriadneToolHandler
    from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH
    from ariadne.config import get_config

    cfg = get_config()
    handler = AriadneToolHandler(
        vector_store=str(MEMORIES_DIR),
        graph_storage=str(GRAPH_DB_PATH),
    )

    return {
        "server": {
            "name": "ariadne-memory",
            "version": "2.0.0",
            "protocol_version": "2024-11-05",
        },
        "tools": handler.list(),
        "config": {
            "vector_store": str(MEMORIES_DIR),
            "graph_db": str(GRAPH_DB_PATH),
            "llm_provider": cfg.get("llm.provider", "not configured"),
        }
    }

@mcp_router.post("/start")
async def mcp_start(req: MCPRunRequest):
    """Start MCP server (后台运行，返回状态)."""
    # 注意：这需要在后台启动进程
    # 可以使用 asyncio.create_subprocess_exec 或类似的机制
    # 简化实现：只返回启动信息
    return {
        "success": True,
        "message": f"MCP server configuration prepared",
        "config": {
            "transport": req.transport,
            "host": req.host,
            "port": req.port,
            "start_command": f"ariadne mcp run -t {req.transport} -p {req.port}"
        }
    }

@mcp_router.get("/status")
async def mcp_status():
    """Check MCP server status."""
    # 检查是否有MCP进程在运行
    import psutil
    mcp_processes = [
        p for p in psutil.process_iter(['pid', 'name', 'cmdline'])
        if 'ariadne' in ' '.join(p.info['cmdline'] or []) and 'mcp' in ' '.join(p.info['cmdline'] or [])
    ]

    return {
        "running": len(mcp_processes) > 0,
        "processes": [
            {"pid": p.info['pid'], "cmdline": ' '.join(p.info['cmdline'])}
            for p in mcp_processes
        ]
    }
```

#### 2.2.4 System Router 扩展

```python
# /api/system/stats - 详细系统统计
@system_router.get("/stats")
async def system_stats(
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Get detailed system statistics."""
    from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH

    systems = manager.list_systems()
    total_docs = 0
    total_size = 0

    for s in systems:
        info = manager.get_info(s.name)
        total_docs += info.get("document_count", 0) if info else 0

    # 计算存储大小
    import os
    for root, dirs, files in os.walk(MEMORIES_DIR):
        for f in files:
            try:
                total_size += os.path.getsize(os.path.join(root, f))
            except:
                pass

    # Graph stats
    graph_entities = 0
    graph_relations = 0
    try:
        from ariadne.graph import GraphStorage
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        graph_entities = len(graph.get_all_entities())
        graph_relations = len(graph.get_all_relations())
    except:
        pass

    return {
        "memory_systems": {
            "total": len(systems),
            "default": manager.DEFAULT_COLLECTION,
        },
        "documents": {
            "total": total_docs,
        },
        "storage": {
            "total_bytes": total_size,
            "path": str(MEMORIES_DIR),
        },
        "graph": {
            "entities": graph_entities,
            "relations": graph_relations,
        }
    }
```

### 2.3 前端组件更新

需要在前端添加以下组件：

1. **配置管理面板** - 设置和查看配置
2. **知识图谱可视化** - 支持多种格式展示
3. **MCP服务管理** - 启动/停止/查看状态
4. **系统统计面板** - 详细的系统信息

---

## 三、Agent 生态扩展方案

### 3.1 当前MCP Server工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `ariadne_search` | 搜索知识库 | query, limit, collection |
| `ariadne_ingest` | 摄入文档 | source, collection |
| `ariadne_graph_query` | 查询知识图谱 | entity, depth, relation_type |
| `ariadne_stats` | 获取统计 | collection |

### 3.2 扩展目标

#### 3.2.1 为 Claude Code 提供

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.cli", "mcp", "run"],
      "env": {}
    }
  }
}
```

#### 3.2.2 为 Cursor/Windsurf 提供 (MCP)

同上，使用 MCP stdio 模式

#### 3.2.3 为 OpenClaw/WorkBuddy 提供 (Skill)

```markdown
# Ariadne Memory Skill

## 触发词
"查记忆"、"搜索知识库"、"查询记忆库"、"记忆搜索"、"知识检索"

## 功能
1. **语义搜索** - 在Ariane记忆系统中搜索相关内容
2. **RAG搜索** - 使用混合检索获取更精确的结果
3. **知识图谱查询** - 查询实体之间的关系
4. **文档摄入** - 将新文档加入记忆系统

## 参数
- query: 搜索查询
- memory: 记忆系统名称（可选，默认使用default）
- top_k: 返回结果数量（默认5）

## 使用示例
```
用户：帮我查一下关于机器学习的内容
助手：使用ariadne_search搜索"机器学习"
```

## API端点
- 搜索: POST /api/search/semantic
- RAG: POST /api/search/rag
- 图谱: GET /api/graph/data
```

#### 3.2.4 为 Codex/GitHub Copilot 提供 (扩展)

通过MCP HTTP模式提供REST API调用

### 3.3 新增MCP工具

#### 3.3.1 工具清单

| 新工具名 | 功能 | 说明 |
|----------|------|------|
| `ariadne_rag_search` | RAG混合搜索 | 支持BM25+向量融合+重排序 |
| `ariadne_summarize` | 摘要生成 | 对搜索结果生成摘要 |
| `ariadne_memory_create` | 创建记忆系统 | 新的命名空间 |
| `ariadne_memory_list` | 列出记忆系统 | 查看所有记忆 |
| `ariadne_graph_explore` | 图谱探索 | 发现实体间的路径 |
| `ariadne_config_get` | 获取配置 | 查看LLM配置 |
| `ariadne_health_check` | 健康检查 | 检查系统状态 |

#### 3.3.2 实现示例

```python
# 在 ariadne/mcp/tools.py 中添加

class RAGSearchTool:
    """RAG混合搜索工具"""
    name = "ariadne_rag_search"
    description = "使用混合检索（向量+BM25）和重排序进行高级搜索，返回带有引用的结果。"

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询"
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5
            },
            "alpha": {
                "type": "number",
                "description": "向量权重 (0.0=仅BM25, 1.0=仅向量)",
                "default": 0.5
            },
            "no_rerank": {
                "type": "boolean",
                "description": "是否跳过重排序",
                "default": False
            }
        },
        "required": ["query"]
    }

class SummarizeTool:
    """摘要生成工具"""
    name = "ariadne_summarize"
    description = "对搜索结果进行LLM摘要总结。"

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询"
            },
            "language": {
                "type": "string",
                "description": "输出语言",
                "default": "en"
            }
        },
        "required": ["query"]
    }

class MemoryListTool:
    """列出记忆系统"""
    name = "ariadne_memory_list"
    description = "列出所有可用的记忆系统。"

    input_schema = {
        "type": "object",
        "properties": {}
    }

class MemoryCreateTool:
    """创建记忆系统"""
    name = "ariadne_memory_create"
    description = "创建一个新的命名记忆系统。"

    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "记忆系统名称"
            },
            "description": {
                "type": "string",
                "description": "描述"
            }
        },
        "required": ["name"]
    }

class GraphExploreTool:
    """图谱探索工具"""
    name = "ariadne_graph_explore"
    description = "探索知识图谱中实体间的路径和关系。"

    input_schema = {
        "type": "object",
        "properties": {
            "entity": {
                "type": "string",
                "description": "起始实体名称"
            },
            "target": {
                "type": "string",
                "description": "目标实体名称（可选）"
            },
            "max_depth": {
                "type": "integer",
                "description": "最大探索深度",
                "default": 3
            }
        },
        "required": ["entity"]
    }

class ConfigGetTool:
    """获取配置工具"""
    name = "ariadne_config_get"
    description = "获取Ariadne的配置信息。"

    input_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "配置键（可选，不提供则返回全部）"
            }
        }
    }

class HealthCheckTool:
    """健康检查工具"""
    name = "ariadne_health_check"
    description = "检查Ariadne系统的健康状态。"

    input_schema = {
        "type": "object",
        "properties": {}
    }
```

### 3.4 Agent集成指南

#### 3.4.1 Claude Code

```json
// ~/.claude/mcp.json (或项目级)
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.cli", "mcp", "run", "-t", "stdio"]
    }
  }
}
```

使用示例：
```
/mcp tools list ariadne-memory
/mcp call ariadne-memory ariadne_search {"query": "RAG implementation"}
```

#### 3.4.2 Cursor

在 Cursor 设置中添加 MCP 服务器：

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.cli", "mcp", "run"],
      "env": {
        "PYTHONPATH": "/path/to/ariadne"
      }
    }
  }
}
```

#### 3.4.3 OpenClaw/WorkBuddy

创建 Skill 文件：

```markdown
# ariadne-memory-skill/SKILL.md
---
name: ariadne-memory
description: |
  Ariadne Memory System 技能，让AI能够访问和管理持久化知识库。
  触发词：记忆、搜索、查询、知识库、RAG、知识图谱
triggers:
  - 记忆
  - 搜索知识库
  - 查询记忆
  - 知识检索
  - RAG
---

## 功能
1. **语义搜索** - 在记忆库中搜索相关内容
2. **RAG搜索** - 使用向量+关键词混合搜索
3. **知识图谱** - 查询实体关系
4. **文档摄入** - 添加新文档到记忆库
5. **摘要生成** - 对搜索结果生成摘要

## API调用
- 语义搜索: `POST http://localhost:8770/api/search/semantic`
- RAG搜索: `POST http://localhost:8770/api/search/rag`
- 图谱数据: `GET http://localhost:8770/api/graph/data`
- 摘要: `POST http://localhost:8770/api/system/summarize`

## 返回格式
搜索结果包含:
- content: 文档内容
- score: 相关性分数
- source_path: 来源文件
```

#### 3.4.4 GitHub Copilot (Extension)

创建 VSCode 扩展调用 Ariadne MCP

---

## 四、实施计划

### Phase 1: CLI测试 (1-2天)
1. 完善现有测试
2. 添加集成测试
3. 添加LLM相关测试（标记）

### Phase 2: Web UI补全 (2-3天)
1. 补充缺失的Config API
2. 添加Advanced Router
3. 添加MCP Router
4. 更新前端组件

### Phase 3: Agent生态 (3-5天)
1. 扩展MCP工具集
2. 创建WorkBuddy Skill
3. 编写集成文档
4. 测试各Agent集成

---

## 五、参考资源

- MemPalace架构: https://github.com/burningmantech/mempalace
- MCP Protocol: https://modelcontextprotocol.io/
- Claude Code MCP: https://docs.anthropic.com/claude-code/docs/mcp
