"""
Ariadne Web API — FastAPI application with full REST API.

Exposes all Ariadne CLI/GUI functionality as REST endpoints:
- Memory system CRUD (create, rename, delete, merge, export, import)
- File ingestion with progress tracking (SSE)
- Semantic search & RAG search
- Knowledge graph enrichment and visualization
- LLM configuration and testing
- Summarization
- System info & stats
- Multi-language support
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ariadne import __version__
from ariadne.memory import MemoryManager, get_manager
from ariadne.ingest import get_ingestor
from ariadne.config import AriadneConfig, get_config, reload_config
from ariadne.i18n import init_locale, get_locale, available_locales, set_locale, get_locale_display
from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH


# ============================================================================
# Pydantic Models (Request / Response)
# ============================================================================

class MemoryCreateRequest(BaseModel):
    name: str
    description: str = ""

class MemoryRenameRequest(BaseModel):
    old_name: str
    new_name: str

class MemoryMergeRequest(BaseModel):
    source_names: List[str]
    new_name: str
    delete_sources: bool = False

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    memory: Optional[str] = None
    verbose: bool = False

class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    fetch_k: int = 20
    alpha: float = 0.5
    no_rerank: bool = False
    memory: Optional[str] = None

class SummarizeRequest(BaseModel):
    query: str
    memory: Optional[str] = None
    output_lang: Optional[str] = None

class LLMConfigRequest(BaseModel):
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048

class ConfigSetRequest(BaseModel):
    key: str
    value: str

class GraphEnrichRequest(BaseModel):
    memory: Optional[str] = None
    limit: int = 100
    force: bool = False

class ExportRequest(BaseModel):
    format: str = "html"
    title: str = "Ariadne Export"
    include_graph: bool = True
    memory: Optional[str] = None

class LanguageRequest(BaseModel):
    locale: str


# ============================================================================
# Response Models
# ============================================================================

class MemoryInfoResponse(BaseModel):
    name: str
    description: str = ""
    path: str = ""
    document_count: int = 0
    created_at: str = ""
    updated_at: str = ""

class SearchResultItem(BaseModel):
    content: str
    source_type: str
    source_path: str
    chunk_index: int
    total_chunks: int
    score: float
    metadata: dict = {}

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
    memory: str

class LLMTestResponse(BaseModel):
    success: bool
    message: str

class GraphStatusResponse(BaseModel):
    entities: int
    relations: int

class SystemInfoResponse(BaseModel):
    version: str
    current_system: str
    total_systems: int
    systems: List[MemoryInfoResponse]
    llm_provider: str
    llm_model: str
    llm_configured: bool
    locale: str

class ConfigResponse(BaseModel):
    config: dict

class IngestResultResponse(BaseModel):
    docs_added: int
    skipped: int
    errors: List[dict]
    total_files: int

class GraphDataResponse(BaseModel):
    nodes: List[dict]
    edges: List[dict]
    stats: dict

class SummaryResponse(BaseModel):
    summary: str
    keywords: List[str]
    topics: List[str]
    language: str
    sources: List[str]


# ============================================================================
# Application Factory
# ============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    init_locale()

    app = FastAPI(
        title="Ariadne Web API",
        description="Cross-Source AI Memory & Knowledge Weaving System",
        version=__version__,
    )

    # CORS — allow React dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])
    app.include_router(ingest_router, prefix="/api/ingest", tags=["Ingest"])
    app.include_router(search_router, prefix="/api/search", tags=["Search"])
    app.include_router(graph_router, prefix="/api/graph", tags=["Graph"])
    app.include_router(config_router, prefix="/api/config", tags=["Config"])
    app.include_router(system_router, prefix="/api/system", tags=["System"])

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": __version__}

    return app


# ============================================================================
# Dependency Injection
# ============================================================================

def get_memory_manager() -> MemoryManager:
    return get_manager()

def get_app_config() -> AriadneConfig:
    return get_config()


# ============================================================================
# Memory System Router
# ============================================================================

from fastapi import APIRouter

memory_router = APIRouter()


@memory_router.get("/list", response_model=List[MemoryInfoResponse])
async def list_memories(
    manager: MemoryManager = Depends(get_memory_manager),
):
    """List all memory systems."""
    systems = manager.list_systems()
    result = []
    for s in systems:
        info = manager.get_info(s.name)
        result.append(MemoryInfoResponse(
            name=s.name,
            description=s.description or "",
            path=s.path,
            document_count=info.get("document_count", 0) if info else 0,
            created_at=info.get("created_at", "")[:10] if info else "",
            updated_at=info.get("updated_at", "")[:10] if info else "",
        ))
    return result


@memory_router.post("/create", response_model=MemoryInfoResponse)
async def create_memory(
    req: MemoryCreateRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Create a new memory system."""
    try:
        manager.create(req.name, req.description)
        info = manager.get_info(req.name)
        return MemoryInfoResponse(
            name=req.name,
            description=req.description,
            path=info.get("path", "") if info else "",
            document_count=0,
            created_at=info.get("created_at", "")[:10] if info else "",
            updated_at=info.get("updated_at", "")[:10] if info else "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@memory_router.post("/rename")
async def rename_memory(
    req: MemoryRenameRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Rename a memory system."""
    try:
        manager.rename(req.old_name, req.new_name)
        return {"success": True, "message": f"Renamed '{req.old_name}' to '{req.new_name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@memory_router.delete("/{name}")
async def delete_memory(
    name: str,
    confirm: bool = Query(False, description="Skip confirmation"),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Delete a memory system."""
    if name == manager.DEFAULT_COLLECTION:
        raise HTTPException(status_code=400, detail="Cannot delete the default memory system")
    try:
        manager.delete(name, confirm=False)
        return {"success": True, "message": f"Deleted '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@memory_router.post("/merge")
async def merge_memories(
    req: MemoryMergeRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Merge multiple memory systems into a new one."""
    try:
        manager.merge(req.source_names, req.new_name, delete_sources=req.delete_sources)
        return {"success": True, "message": f"Merged into '{req.new_name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@memory_router.get("/{name}/info", response_model=MemoryInfoResponse)
async def get_memory_info(
    name: str,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Get information about a memory system."""
    info = manager.get_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Memory system '{name}' not found")
    return MemoryInfoResponse(
        name=name,
        description=info.get("description", ""),
        path=info.get("path", ""),
        document_count=info.get("document_count", 0),
        created_at=info.get("created_at", "")[:10],
        updated_at=info.get("updated_at", "")[:10],
    )


@memory_router.post("/{name}/clear")
async def clear_memory(
    name: str,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Clear all documents from a memory system."""
    try:
        manager.clear(name)
        return {"success": True, "message": f"Cleared '{name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@memory_router.get("/{name}/export")
async def export_memory(
    name: str,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Export a memory system as a zip archive."""
    try:
        # Export to a temp directory, then zip it
        tmp_dir = tempfile.mkdtemp(prefix="ariadne_export_")
        export_path = Path(tmp_dir) / name
        manager.export(name, str(export_path))

        # Create zip
        zip_path = Path(tmp_dir) / f"{name}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(export_path))

        return FileResponse(
            path=str(zip_path),
            filename=f"{name}.zip",
            media_type="application/zip",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@memory_router.post("/import")
async def import_memory(
    name: str = Query(..., description="Name for the imported memory system"),
    file: UploadFile = File(...),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Import a memory system from a zip archive."""
    tmp_dir = tempfile.mkdtemp(prefix="ariadne_import_")
    try:
        # Save uploaded file
        zip_path = Path(tmp_dir) / file.filename
        with open(zip_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract zip
        extract_dir = Path(tmp_dir) / "extracted"
        shutil.unpack_archive(str(zip_path), str(extract_dir))

        # Find the actual data directory inside
        subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        source_path = str(subdirs[0]) if subdirs else str(extract_dir)

        manager.import_memory(source_path, name)
        return {"success": True, "message": f"Imported as '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Ingest Router
# ============================================================================

ingest_router = APIRouter()

# Supported extensions for scanning
SCAN_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".pdf", ".docx", ".pptx",
    ".xlsx", ".xls", ".csv", ".json",
    ".mm", ".xmind",
    ".py", ".java", ".cpp", ".c", ".h", ".hpp",
    ".js", ".ts", ".jsx", ".tsx", ".cs", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".scala",
    ".epub", ".bib", ".ris",
    ".eml", ".mbox",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp4", ".avi", ".mkv", ".mov",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
    ".html", ".htm", ".rss", ".ipynb", ".msg", ".rtf",
    ".ods", ".odt", ".odp", ".xml",
}


@ingest_router.post("/files", response_model=IngestResultResponse)
async def ingest_files(
    files: List[UploadFile] = File(...),
    memory: Optional[str] = Query(None),
    verbose: bool = Query(False),
    enrich: bool = Query(False),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Ingest uploaded files into a memory system."""
    store = manager.get_store(memory)
    target = memory or manager.DEFAULT_COLLECTION

    docs_added = 0
    skipped = 0
    errors = []
    tmp_files = []

    try:
        for upload in files:
            # Save to temp file
            suffix = Path(upload.filename).suffix if upload.filename else ".txt"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="ariadne_ingest_")
            tmp_files.append(tmp.name)

            try:
                content = await upload.read()
                tmp.write(content)
                tmp.close()

                # Get ingestor
                try:
                    ingestor = get_ingestor(tmp.name)
                except (ValueError, ImportError):
                    skipped += 1
                    continue

                # Ingest
                try:
                    docs = ingestor.ingest(tmp.name)
                    if docs:
                        store.add(docs)
                        docs_added += len(docs)
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append({
                        "file": upload.filename or "unknown",
                        "error": str(e),
                    })
            except Exception as e:
                errors.append({
                    "file": upload.filename or "unknown",
                    "error": str(e),
                })

        # Optional graph enrichment
        if enrich and docs_added > 0:
            try:
                from ariadne.graph import GraphStorage, GraphEnricher
                from ariadne.paths import GRAPH_DB_PATH
                cfg = get_config()
                llm = cfg.create_llm()
                if llm:
                    graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
                    enricher = GraphEnricher(llm=llm)
                    all_docs = store.get_all_documents(limit=1000)
                    for doc in all_docs:
                        try:
                            graph_doc = enricher.enrich(doc)
                            for entity in graph_doc.entities:
                                graph.add_entity(entity)
                            for relation in graph_doc.relations:
                                graph.add_relation(relation)
                        except Exception:
                            pass
            except Exception:
                pass

    finally:
        # Cleanup temp files
        for tmp_path in tmp_files:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

    return IngestResultResponse(
        docs_added=docs_added,
        skipped=skipped,
        errors=errors,
        total_files=len(files),
    )


@ingest_router.post("/directory", response_model=IngestResultResponse)
async def ingest_directory(
    directory: str = Query(..., description="Directory path to ingest"),
    memory: Optional[str] = Query(None),
    recursive: bool = Query(True),
    verbose: bool = Query(False),
    enrich: bool = Query(False),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Ingest all supported files from a directory."""
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {directory}")

    store = manager.get_store(memory)
    target = memory or manager.DEFAULT_COLLECTION

    # Collect files
    files = []
    for ext in SCAN_EXTENSIONS:
        if recursive:
            files.extend(dir_path.rglob(f"*{ext}"))
        else:
            files.extend(dir_path.glob(f"*{ext}"))

    docs_added = 0
    skipped = 0
    errors = []

    for file_path in files:
        try:
            try:
                ingestor = get_ingestor(str(file_path))
            except (ValueError, ImportError):
                skipped += 1
                continue

            try:
                docs = ingestor.ingest(str(file_path))
                if docs:
                    store.add(docs)
                    docs_added += len(docs)
                else:
                    skipped += 1
            except Exception as e:
                errors.append({
                    "file": str(file_path),
                    "error": str(e),
                })
        except Exception as e:
            errors.append({
                "file": str(file_path),
                "error": str(e),
            })

    # Optional graph enrichment
    if enrich and docs_added > 0:
        try:
            from ariadne.graph import GraphStorage, GraphEnricher
            cfg = get_config()
            llm = cfg.create_llm()
            if llm:
                graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
                enricher = GraphEnricher(llm=llm)
                all_docs = store.get_all_documents(limit=1000)
                for doc in all_docs:
                    try:
                        graph_doc = enricher.enrich(doc)
                        for entity in graph_doc.entities:
                            graph.add_entity(entity)
                        for relation in graph_doc.relations:
                            graph.add_relation(relation)
                    except Exception:
                        pass
        except Exception:
            pass

    return IngestResultResponse(
        docs_added=docs_added,
        skipped=skipped,
        errors=errors,
        total_files=len(files),
    )


# ============================================================================
# Search Router
# ============================================================================

search_router = APIRouter()


@search_router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    req: SearchRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Perform semantic search across a memory system."""
    try:
        store = manager.get_store(req.memory)
        target = req.memory or manager.DEFAULT_COLLECTION
        results = store.search(req.query, top_k=req.top_k)

        items = []
        for doc, score in results:
            items.append(SearchResultItem(
                content=doc.content[:500] + ("..." if len(doc.content) > 500 else ""),
                source_type=doc.source_type.value,
                source_path=doc.source_path,
                chunk_index=doc.chunk_index,
                total_chunks=doc.total_chunks,
                score=round(score, 4),
                metadata=doc.metadata if req.verbose else {},
            ))

        return SearchResponse(results=items, total=len(items), memory=target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@search_router.post("/rag", response_model=dict)
async def rag_search(
    req: RAGSearchRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Perform RAG search with hybrid vector+BM25 retrieval and reranking."""
    try:
        from ariadne.rag import create_rag_engine
    except ImportError:
        raise HTTPException(status_code=500, detail="RAG dependencies not installed")

    try:
        store = manager.get_store(req.memory)
        target = req.memory or manager.DEFAULT_COLLECTION

        engine = create_rag_engine(store, config={
            "rerank": not req.no_rerank,
            "alpha": req.alpha,
            "top_k": req.top_k,
        })

        result = engine.query(
            query=req.query,
            top_k=req.top_k,
            fetch_k=req.fetch_k,
            alpha=req.alpha,
            include_citations=True,
            include_context=False,
        )

        if result.is_empty:
            return {"results": [], "citations": [], "memory": target}

        # Format results
        formatted_results = []
        for res in result.results:
            doc = res.document
            formatted_results.append({
                "content": doc.content[:500] + ("..." if len(doc.content) > 500 else ""),
                "source_type": doc.source_type.value,
                "source_path": doc.source_path,
                "title": doc.metadata.get("title", Path(doc.source_path).stem),
                "scores": {
                    "combined": round(res.combined_score, 4),
                    "vector": round(res.vector_score, 4) if res.vector_score else None,
                    "bm25": round(res.bm25_score, 4) if res.bm25_score else None,
                    "rank": res.rank,
                },
            })

        # Format citations
        citations = []
        if result.citations:
            for c in result.citations:
                citations.append({
                    "text": c.text,
                    "source": c.source,
                    "format_markdown": c.format_markdown(),
                })

        return {
            "results": formatted_results,
            "citations": citations,
            "metadata": result.metadata,
            "memory": target,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Graph Router
# ============================================================================

graph_router = APIRouter()


@graph_router.get("/status", response_model=GraphStatusResponse)
async def graph_status():
    """Get knowledge graph status."""
    try:
        from ariadne.graph import GraphStorage
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        entities = graph.get_all_entities()
        relations = graph.get_all_relations()
        return GraphStatusResponse(entities=len(entities), relations=len(relations))
    except Exception:
        return GraphStatusResponse(entities=0, relations=0)


@graph_router.get("/data", response_model=GraphDataResponse)
async def graph_data(
    max_nodes: int = Query(50, description="Maximum nodes to return"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """Get knowledge graph data as nodes and edges."""
    try:
        from ariadne.graph import GraphStorage
        from ariadne.advanced import GraphVisualizer

        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        visualizer = GraphVisualizer(graph)

        # Get JSON data
        json_str = visualizer.to_json(max_nodes=max_nodes)
        data = json.loads(json_str)

        return GraphDataResponse(
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            stats=data.get("stats", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.post("/enrich")
async def enrich_graph(
    req: GraphEnrichRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Extract entities and relations from documents into the knowledge graph."""
    try:
        from ariadne.graph import GraphStorage, GraphEnricher
    except ImportError:
        raise HTTPException(status_code=500, detail="Graph module not available")

    cfg = get_config()
    llm = cfg.create_llm()
    if llm is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Please set up your API key first.")

    try:
        store = manager.get_store(req.memory)
        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        enricher = GraphEnricher(llm=llm)

        all_docs = store.get_all_documents(limit=req.limit if req.limit > 0 else 10000)
        if not all_docs:
            return {"success": True, "entities_added": 0, "relations_added": 0, "errors": 0}

        entities_added = 0
        relations_added = 0
        errors = 0

        for doc in all_docs:
            try:
                graph_doc = enricher.enrich(doc)
                for entity in graph_doc.entities:
                    graph.add_entity(entity)
                    entities_added += 1
                for relation in graph_doc.relations:
                    graph.add_relation(relation)
                    relations_added += 1
            except Exception:
                errors += 1

        return {
            "success": True,
            "entities_added": entities_added,
            "relations_added": relations_added,
            "errors": errors,
            "documents_processed": len(all_docs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get("/html")
async def graph_html(
    max_nodes: int = Query(50),
    title: str = Query("Knowledge Graph"),
):
    """Get interactive HTML visualization of the knowledge graph."""
    try:
        from ariadne.graph import GraphStorage
        from ariadne.advanced import GraphVisualizer

        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        visualizer = GraphVisualizer(graph)
        html = visualizer.to_html(title=title, max_nodes=max_nodes)

        return StreamingResponse(
            iter([html]),
            media_type="text/html",
            headers={"Content-Disposition": f"inline; filename=graph.html"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Config Router
# ============================================================================

config_router = APIRouter()


@config_router.get("/", response_model=ConfigResponse)
async def get_current_config(
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Get current configuration (excluding API keys)."""
    config_dict = cfg.to_dict()
    # Mask API keys
    if "llm" in config_dict and "api_key" in config_dict["llm"]:
        key = config_dict["llm"]["api_key"]
        if key:
            config_dict["llm"]["api_key"] = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
    return ConfigResponse(config=config_dict)


@config_router.post("/set")
async def set_config_value(
    req: ConfigSetRequest,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Set a configuration value."""
    # Convert value type
    value = req.value
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)
    elif value.replace(".", "", 1).isdigit():
        value = float(value)

    cfg.set(req.key, value)
    cfg.save_user()
    return {"success": True, "key": req.key, "value": value}


@config_router.post("/llm")
async def configure_llm(
    req: LLMConfigRequest,
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Configure LLM provider."""
    cfg.set("llm.provider", req.provider)
    if req.model:
        cfg.set("llm.model", req.model)
    if req.api_key:
        cfg.set("llm.api_key", req.api_key)
    if req.base_url:
        cfg.set("llm.base_url", req.base_url)
    cfg.set("llm.temperature", req.temperature)
    cfg.set("llm.max_tokens", req.max_tokens)
    cfg.save_user()
    return {"success": True, "message": "LLM configuration saved"}


@config_router.post("/llm/test", response_model=LLMTestResponse)
async def test_llm(
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Test the current LLM configuration."""
    success, msg = cfg.test_llm()
    return LLMTestResponse(success=success, message=msg)


@config_router.post("/language")
async def set_language(req: LanguageRequest):
    """Set the UI language."""
    success = set_locale(req.locale)
    if not success:
        raise HTTPException(status_code=400, detail=f"Unsupported locale: {req.locale}")
    return {"success": True, "locale": req.locale, "display_name": get_locale_display()}


@config_router.get("/languages")
async def list_languages():
    """List all supported languages."""
    return {"languages": [{"code": code, "name": name} for code, name in available_locales()]}


@config_router.get("/providers")
async def list_providers(
    cfg: AriadneConfig = Depends(get_app_config),
):
    """List all supported LLM providers."""
    return {
        "providers": [
            {"code": code, "name": name, "models": models}
            for code, name, models in cfg.SUPPORTED_PROVIDERS
        ]
    }


# ============================================================================
# System Router
# ============================================================================

system_router = APIRouter()


@system_router.get("/info", response_model=SystemInfoResponse)
async def system_info(
    manager: MemoryManager = Depends(get_memory_manager),
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Get system information."""
    systems = manager.list_systems()
    system_list = []
    for s in systems:
        info = manager.get_info(s.name)
        system_list.append(MemoryInfoResponse(
            name=s.name,
            description=s.description or "",
            path=s.path,
            document_count=info.get("document_count", 0) if info else 0,
            created_at=info.get("created_at", "")[:10] if info else "",
            updated_at=info.get("updated_at", "")[:10] if info else "",
        ))

    llm_info = cfg.get_llm_info()

    return SystemInfoResponse(
        version=__version__,
        current_system=manager.DEFAULT_COLLECTION,
        total_systems=len(systems),
        systems=system_list,
        llm_provider=llm_info.get("provider", ""),
        llm_model=llm_info.get("model", ""),
        llm_configured=llm_info.get("has_api_key", False),
        locale=get_locale(),
    )


@system_router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    req: SummarizeRequest,
    manager: MemoryManager = Depends(get_memory_manager),
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Generate a summary of search results."""
    if not req.query:
        raise HTTPException(status_code=400, detail="Query is required for summarization")

    try:
        from ariadne.advanced import Summarizer
        store = manager.get_store(req.memory)
        results = store.search(req.query, top_k=10)
        docs = [doc for doc, _ in results]

        if not docs:
            return SummaryResponse(
                summary="No documents found for the query.",
                keywords=[], topics=[], language=req.output_lang or "en", sources=[],
            )

        summarizer = Summarizer(config=cfg)
        result = summarizer.summarize(docs, query=req.query, language=req.output_lang)

        return SummaryResponse(
            summary=result.summary,
            keywords=result.keywords,
            topics=result.topics,
            language=result.language,
            sources=result.sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@system_router.post("/export")
async def export_data(
    req: ExportRequest,
    manager: MemoryManager = Depends(get_memory_manager),
    cfg: AriadneConfig = Depends(get_app_config),
):
    """Export memory system data."""
    try:
        from ariadne.advanced import Exporter
        from ariadne.graph import GraphStorage

        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        exporter = Exporter(graph=graph, config=cfg)

        tmp_dir = tempfile.mkdtemp(prefix="ariadne_export_")
        ext_map = {"markdown": ".md", "html": ".html", "docx": ".docx"}
        ext = ext_map.get(req.format, f".{req.format}")
        output_path = Path(tmp_dir) / f"ariadne_export{ext}"

        path = exporter.export(
            str(output_path),
            format=req.format,
            title=req.title,
            include_graph=req.include_graph,
        )

        media_types = {
            "markdown": "text/markdown",
            "html": "text/html",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        return FileResponse(
            path=path,
            filename=f"ariadne_export{ext}",
            media_type=media_types.get(req.format, "application/octet-stream"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Server Runner
# ============================================================================

def run_server(host: str = "127.0.0.1", port: int = 8770, reload: bool = False):
    """Run the Ariadne web server."""
    import uvicorn

    # Try to serve the React frontend static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app = create_app()
        from fastapi.staticfiles import StaticFiles

        # Mount static files for React SPA
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        uvicorn.run(app, host=host, port=port)
    else:
        # API-only mode (frontend not built yet)
        uvicorn.run("ariadne.web.api:create_app", host=host, port=port, reload=reload, factory=True)
