"""
Ariadne Web API Extensions - 补充CLI缺失的功能

这个模块包含Web API中缺失的CLI功能对应的端点。
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio

from ariadne import __version__
from ariadne.memory import MemoryManager, get_manager
from ariadne.config import AriadneConfig, get_config
from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH


# ============================================================================
# Pydantic Models
# ============================================================================

class ConfigKeyRequest(BaseModel):
    key: str


class SetApiKeyRequest(BaseModel):
    provider: str
    api_key: str
    save_to_env: bool = False


class GraphQueryRequest(BaseModel):
    format: str = "text"  # text, dot, json, mermaid
    query: Optional[str] = None
    depth: int = 1
    max_nodes: int = 50


class SummarizeStreamRequest(BaseModel):
    query: str
    memory: Optional[str] = None
    output_lang: Optional[str] = None


class MCPRunRequest(BaseModel):
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765


# ============================================================================
# Dependency Injection
# ============================================================================

def get_memory_manager() -> MemoryManager:
    return get_manager()


def get_app_config() -> AriadneConfig:
    return get_config()


# ============================================================================
# Config Router Extensions
# ============================================================================

config_ext_router = APIRouter(prefix="/api/config", tags=["Config Extensions"])


@config_ext_router.get("/{key}")
async def get_config_value(
    key: str,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Get a specific configuration value.

   对应CLI命令: ariadne config get <key>
    """
    value = cfg.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return {"key": key, "value": value, "type": type(value).__name__}


@config_ext_router.post("/set-api-key")
async def set_api_key(
    req: SetApiKeyRequest,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Set API key for a provider.

   对应CLI命令: ariadne config set-api-key <provider> <key>
    """
    if req.save_to_env:
        import os
        env_var = f"{req.provider.upper()}_API_KEY"
        os.environ[env_var] = req.api_key
        return {
            "success": True,
            "message": f"Set {env_var} in environment (session only)",
            "env_var": env_var
        }

    cfg.set("llm.provider", req.provider)
    cfg.set("llm.api_key", req.api_key)
    cfg.save_user()
    return {
        "success": True,
        "message": f"API key set for {req.provider}",
        "saved_to": str(cfg.config_dir / "config.json")
    }


# ============================================================================
# Advanced Router
# ============================================================================

advanced_router = APIRouter(prefix="/api/advanced", tags=["Advanced Features"])


@advanced_router.post("/graph")
async def get_graph(
    req: GraphQueryRequest,
):
    """Get knowledge graph in various formats.

   对应CLI命令: ariadne advanced graph [--format] [--query] [--depth]
    """
    from ariadne.graph import GraphStorage
    from ariadne.advanced import GraphVisualizer

    try:
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph storage not available: {e}")

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

    # Build entity list
    all_entities = graph.get_all_entities()
    entity_list = [
        {
            "id": e.entity_id,
            "name": e.name,
            "type": e.entity_type.value,
            "description": e.description,
            "aliases": e.aliases,
        }
        for e in all_entities[:req.max_nodes]
    ]

    # Build relation list
    all_relations = graph.get_all_relations()
    if entity_ids:
        filtered_relations = [
            r for r in all_relations
            if r.source_id in entity_ids and r.target_id in entity_ids
        ]
    else:
        filtered_relations = all_relations

    relation_list = [
        {
            "id": r.relation_id,
            "source": r.source_id,
            "target": r.target_id,
            "type": r.relation_type.value,
            "description": r.description,
        }
        for r in filtered_relations[:req.max_nodes * 2]
    ]

    if req.format == "text":
        return {
            "format": "text",
            "entities": len(all_entities),
            "relations": len(all_relations),
            "entity_list": entity_list,
            "relation_list": relation_list,
        }
    elif req.format == "json":
        return {
            "format": "json",
            "graph": vis.to_json(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)
        }
    elif req.format == "mermaid":
        return {
            "format": "mermaid",
            "graph": vis.to_mermaid(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)
        }
    elif req.format == "dot":
        return {
            "format": "dot",
            "graph": vis.to_dot(entity_ids=list(entity_ids) if entity_ids else None, max_nodes=req.max_nodes)
        }
    elif req.format == "html":
        return {
            "format": "html",
            "html": vis.to_html(max_nodes=req.max_nodes)
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")


@advanced_router.post("/summarize/stream")
async def summarize_stream(
    req: SummarizeStreamRequest,
    manager: MemoryManager = Depends(get_memory_manager),
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Generate summary with streaming response.

   对应CLI命令: ariadne advanced summarize [query]
    """
    if not cfg.get("advanced.enable_summary"):
        raise HTTPException(
            status_code=400,
            detail="Summary feature is disabled. Enable with: ariadne config set advanced.enable_summary true"
        )

    llm = cfg.create_llm()
    if llm is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Please set up your API key first.")

    store = manager.get_store(req.memory)
    results = store.search(req.query, top_k=10)

    if not results:
        raise HTTPException(status_code=404, detail="No results found for the query.")

    context = "\n\n".join([
        f"[Document {i+1}]\n{doc.content[:500]}"
        for i, (doc, _) in enumerate(results)
    ])

    out_lang = req.output_lang or cfg.get_output_language()
    lang_prompts = {
        "zh_CN": "请用简体中文总结",
        "zh_TW": "請用繁體中文總結",
        "en": "Please summarize in English",
        "fr": "Veuillez résumer en français",
        "es": "Por favor, resuma en español",
        "de": "Bitte fassen Sie auf Deutsch zusammen",
        "ja": "日本語で要約してください",
        "ko": "한국어로 요약해 주세요",
    }
    lang_prompt = lang_prompts.get(out_lang, "Please summarize in English")

    prompt = f"""Based on the following search results, {lang_prompt}:

Search Query: {req.query}

{context}

Please provide:
1. Main topics and themes
2. Key insights or findings
3. A brief summary (2-3 sentences)
"""

    async def event_stream():
        try:
            # 使用流式响应
            response = await llm.chat_stream(prompt)
            async for chunk in response:
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@advanced_router.get("/graph/status")
async def graph_status_detailed():
    """Get detailed graph statistics.

   对应CLI命令: ariadne advanced graph --format text
    """
    from ariadne.graph import GraphStorage

    try:
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        all_entities = graph.get_all_entities()
        all_relations = graph.get_all_relations()

        # Count by type
        type_counts = {}
        for e in all_entities:
            t = e.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "entities": len(all_entities),
            "relations": len(all_relations),
            "entity_types": type_counts,
            "graph_db_path": str(GRAPH_DB_PATH),
        }
    except Exception as e:
        return {
            "entities": 0,
            "relations": 0,
            "error": str(e),
        }


# ============================================================================
# MCP Router
# ============================================================================

mcp_router = APIRouter(prefix="/api/mcp", tags=["MCP Server"])


@mcp_router.get("/info")
async def mcp_info():
    """Get MCP server information and available tools.

   对应CLI命令: ariadne mcp info
    """
    try:
        from ariadne.mcp import AriadneMCPServer
        from ariadne.mcp.tools import AriadneToolHandler
    except ImportError:
        raise HTTPException(status_code=500, detail="MCP module not available")

    handler = AriadneToolHandler(
        vector_store=str(MEMORIES_DIR),
        graph_storage=str(GRAPH_DB_PATH),
    )

    cfg = get_config()

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
        },
        "usage": {
            "claude_code": "claude --mcp ariadne python -m ariadne.cli mcp run",
            "cursor": "Add to Cursor MCP settings",
        }
    }


@mcp_router.post("/start")
async def mcp_start(req: MCPRunRequest):
    """Get MCP server start configuration.

    Note: This returns the configuration. Actual server startup should be done
    separately via CLI or process manager.

    对应CLI命令: ariadne mcp run [--transport] [--host] [--port]
    """
    return {
        "success": True,
        "message": "MCP server configuration prepared",
        "config": {
            "transport": req.transport,
            "host": req.host,
            "port": req.port,
            "start_command": f"ariadne mcp run -t {req.transport} -p {req.port}",
            "stdio_example": "claude --mcp ariadne python -m ariadne.cli mcp run",
            "http_example": f"curl -X POST http://{req.host}:{req.port}/mcp",
        },
        "paths": {
            "vector_store": str(MEMORIES_DIR),
            "graph_db": str(GRAPH_DB_PATH),
        }
    }


@mcp_router.get("/status")
async def mcp_status():
    """Check if MCP server is running and get status.

    对应CLI命令: ariadne mcp info
    """
    try:
        import psutil
        mcp_processes = []
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(p.info['cmdline'] or [])
                if 'ariadne' in cmdline.lower() and 'mcp' in cmdline.lower():
                    mcp_processes.append({
                        "pid": p.info['pid'],
                        "cmdline": cmdline,
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "running": len(mcp_processes) > 0,
            "processes": mcp_processes,
            "suggestion": "Use 'ariadne mcp run' to start the MCP server"
                          if not mcp_processes else None,
        }
    except ImportError:
        # psutil not available
        return {
            "running": None,
            "processes": [],
            "note": "psutil not available, cannot detect running processes",
        }


@mcp_router.get("/tools")
async def mcp_list_tools():
    """List all available MCP tools.

    对应CLI命令: ariadne mcp info
    """
    try:
        from ariadne.mcp.tools import AriadneToolHandler
    except ImportError:
        raise HTTPException(status_code=500, detail="MCP module not available")

    handler = AriadneToolHandler(
        vector_store=str(MEMORIES_DIR),
        graph_storage=str(GRAPH_DB_PATH),
    )

    return {
        "tools": handler.list(),
        "count": len(handler.list()),
    }


# ============================================================================
# System Router Extensions
# ============================================================================

system_ext_router = APIRouter(prefix="/api/system", tags=["System Extensions"])


@system_ext_router.get("/stats")
async def system_stats(
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Get detailed system statistics.

    对应CLI命令: ariadne info --stats
    """
    import os

    systems = manager.list_systems()
    total_docs = 0

    for s in systems:
        info = manager.get_info(s.name)
        total_docs += info.get("document_count", 0) if info else 0

    # Calculate storage size
    total_size = 0
    try:
        for root, dirs, files in os.walk(MEMORIES_DIR):
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except:
                    pass
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
        "version": __version__,
        "memory_systems": {
            "total": len(systems),
            "default": manager.DEFAULT_COLLECTION,
            "systems": [
                {
                    "name": s.name,
                    "description": s.description,
                    "path": s.path,
                }
                for s in systems
            ]
        },
        "documents": {
            "total": total_docs,
        },
        "storage": {
            "total_bytes": total_size,
            "total_mb": round(total_size / (1024 * 1024), 2),
            "path": str(MEMORIES_DIR),
        },
        "graph": {
            "entities": graph_entities,
            "relations": graph_relations,
            "path": str(GRAPH_DB_PATH),
        }
    }


@system_ext_router.get("/paths")
async def system_paths():
    """Get all system paths and directories."""
    from ariadne.paths import (
        HOME_DIR,
        DATA_DIR,
        MEMORIES_DIR,
        GRAPH_DB_PATH,
        CONFIG_DIR,
        LOG_DIR,
        CACHE_DIR,
    )

    return {
        "paths": {
            "home": str(HOME_DIR),
            "data": str(DATA_DIR),
            "memories": str(MEMORIES_DIR),
            "graph_db": str(GRAPH_DB_PATH),
            "config": str(CONFIG_DIR),
            "logs": str(LOG_DIR),
            "cache": str(CACHE_DIR),
        }
    }


# ============================================================================
# Integration: Register all routers with the main app
# ============================================================================

def register_extension_routers(app):
    """Register all extension routers with the main FastAPI app."""
    app.include_router(config_ext_router)
    app.include_router(advanced_router)
    app.include_router(mcp_router)
    app.include_router(system_ext_router)
