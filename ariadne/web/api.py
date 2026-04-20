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
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

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


@ingest_router.post("/files/stream")
async def ingest_files_stream(
    files: List[UploadFile] = File(...),
    memory: Optional[str] = Query(None),
    enrich: bool = Query(False),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Ingest files with real-time SSE progress streaming."""
    target = memory or manager.DEFAULT_COLLECTION

    async def event_stream():
        try:
            store = manager.get_store(target)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': f'Memory system error: {e}'})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'docs_added': 0, 'skipped': 0, 'errors': [], 'total_files': len(files)})}\n\n"
            return

        total = len(files)
        docs_added = 0
        skipped = 0
        errors = []
        tmp_files = []

        for i, upload in enumerate(files):
            # Emit processing event
            progress = int((i / total) * 90)
            yield f"event: progress\ndata: {json.dumps({'file': upload.filename, 'progress': progress, 'phase': 'processing'})}\n\n"

            suffix = Path(upload.filename).suffix if upload.filename else ".txt"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="ariadne_ingest_")
            tmp_files.append(tmp.name)

            try:
                content = await upload.read()
                tmp.write(content)
                tmp.close()

                try:
                    ingestor = get_ingestor(tmp.name)
                except (ValueError, ImportError):
                    skipped += 1
                    yield f"event: skip\ndata: {json.dumps({'file': upload.filename, 'reason': 'Unsupported file type'})}\n\n"
                    continue

                try:
                    docs = ingestor.ingest(tmp.name)
                    if docs:
                        store.add(docs)
                        docs_added += len(docs)
                        yield f"event: success\ndata: {json.dumps({'file': upload.filename, 'docs': len(docs)})}\n\n"
                    else:
                        skipped += 1
                        yield f"event: skip\ndata: {json.dumps({'file': upload.filename, 'reason': 'No content extracted'})}\n\n"
                except Exception as e:
                    errors.append({"file": upload.filename or "unknown", "error": str(e)})
                    yield f"event: error\ndata: {json.dumps({'file': upload.filename, 'error': str(e)})}\n\n"
            except Exception as e:
                errors.append({"file": upload.filename or "unknown", "error": str(e)})
                yield f"event: error\ndata: {json.dumps({'file': upload.filename, 'error': str(e)})}\n\n"

            # Cleanup temp file per iteration
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except OSError:
                pass

        # Final result
        yield f"event: complete\ndata: {json.dumps({'docs_added': docs_added, 'skipped': skipped, 'errors': errors, 'total_files': total})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
                    "text": c.highlight,
                    "source": c.source_path,
                    "source_type": c.source_type,
                    "title": c.title,
                    "doc_id": c.doc_id,
                    "score": round(c.score, 4),
                    "format_markdown": c.format_markdown(),
                    "format_plain": c.format_plain(),
                })

        return {
            "results": formatted_results,
            "citations": citations,
            "metadata": result.metadata,
            "memory": target,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@search_router.post("/rag/rebuild-index")
async def rag_rebuild_index(
    memory: Optional[str] = Body(None),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """
    Rebuild the BM25 index for a memory system.
    Call this after ingesting many new documents.
    """
    try:
        from ariadne.rag import create_rag_engine

        store = manager.get_store(memory)
        engine = create_rag_engine(store)
        count = engine.rebuild_bm25_index()

        return {"success": True, "indexed_docs": count, "memory": memory or manager.DEFAULT_COLLECTION}
    except ImportError:
        raise HTTPException(status_code=500, detail="RAG dependencies not installed. Install rank-bm25 and sentence-transformers.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@search_router.get("/rag/health")
async def rag_health(
    memory: Optional[str] = Query(None),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """
    Check the health of RAG pipeline components.
    Returns status for BM25 index, Reranker, and VectorStore.
    """
    try:
        from ariadne.rag import create_rag_engine

        store = manager.get_store(memory)
        engine = create_rag_engine(store)
        status = engine.health_check()

        return {
            "healthy": all(v.get("healthy", False) for v in status.values()),
            "memory": memory or manager.DEFAULT_COLLECTION,
            "components": status,
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="RAG dependencies not installed")
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
    """Get knowledge graph data as nodes and edges, with optional entity type filter."""
    try:
        from ariadne.graph import GraphStorage
        from ariadne.advanced import GraphVisualizer

        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))

        # Get all entities
        all_entities = graph.get_all_entities()

        # Filter by type if specified
        if entity_type and entity_type.upper() != "ALL":
            filtered = [e for e in all_entities if e.entity_type.value.upper() == entity_type.upper()]
            entities = filtered[:max_nodes]
        else:
            entities = all_entities[:max_nodes]

        entity_ids = {e.entity_id for e in entities}
        all_relations = graph.get_all_relations()

        # Build nodes
        nodes = []
        for entity in entities:
            nodes.append({
                "id": entity.entity_id,
                "label": entity.name,
                "type": entity.entity_type.value,
                "description": entity.description,
                "aliases": entity.aliases,
            })

        # Build edges (only for filtered nodes)
        edges = []
        for relation in all_relations:
            if relation.source_id in entity_ids and relation.target_id in entity_ids:
                edges.append({
                    "id": relation.relation_id,
                    "source": relation.source_id,
                    "target": relation.target_id,
                    "type": relation.relation_type.value,
                    "description": relation.description,
                    "label": relation.relation_type.value,
                })

        # Stats
        type_counts: Dict[str, int] = {}
        for e in all_entities:
            t = e.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        stats = {
            "entities": len(all_entities),
            "relations": len(all_relations),
            "entity_types": type_counts,
        }

        return GraphDataResponse(nodes=nodes, edges=edges, stats=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@search_router.get("/suggest")
async def search_suggest(
    q: str = Query(..., min_length=2, description="Search query"),
    memory: Optional[str] = Query(None),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Get search suggestions based on indexed content."""
    try:
        store = manager.get_store(memory)

        # Get all documents and extract potential suggestions
        # Limit to 200 docs for performance
        docs = store.get_all_documents(limit=200)
        suggestions: List[str] = []
        seen = set()

        # Extract meaningful phrases (3-6 words, alphanumeric)
        import re
        word_pattern = re.compile(r"\b[a-zA-Z\u4e00-\u9fff]{3,30}\b")

        for doc in docs:
            # Use first 500 chars for keyword extraction
            text = doc.content[:500]
            words = word_pattern.findall(text)
            # Build 2-3 word phrases
            for i in range(len(words) - 1):
                phrase = " ".join(words[i : i + 2])
                if phrase.lower() not in seen and q.lower() in phrase.lower():
                    suggestions.append(phrase)
                    seen.add(phrase.lower())

        # Sort by relevance (exact prefix match first)
        suggestions = sorted(suggestions, key=lambda s: (0 if s.lower().startswith(q.lower()) else 1, -len(s)))
        return {"suggestions": suggestions[:10]}
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


@graph_router.get("/export/{format}")
async def graph_export(
    format: str,
    max_nodes: int = Query(50),
    title: str = Query("Knowledge Graph Export"),
):
    """
    Export knowledge graph in multiple formats.
    Supported formats: html, markdown, docx, svg, json, mermaid
    """
    try:
        from ariadne.graph import GraphStorage
        from ariadne.advanced import GraphVisualizer, Exporter

        graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
        cfg = get_config()
        ext_map = {
            "html": ".html",
            "markdown": ".md",
            "docx": ".docx",
            "svg": ".svg",
            "json": ".json",
            "mermaid": ".mm",
        }

        if format not in ext_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {format}. Supported: {list(ext_map.keys())}",
            )

        ext = ext_map[format]
        tmp_path = Path(tempfile.mkdtemp(prefix="ariadne_export_")) / f"graph{ext}"

        if format == "html":
            visualizer = GraphVisualizer(graph, cfg)
            content = visualizer.to_html(title=title, max_nodes=max_nodes)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            media_type = "text/html"
            filename = f"graph{ext}"

        elif format == "markdown":
            exporter = Exporter(graph=graph, config=cfg)
            content = exporter._to_markdown(title, include_graph=True, language="en")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            media_type = "text/markdown"
            filename = f"graph{ext}"

        elif format == "docx":
            exporter = Exporter(graph=graph, config=cfg)
            path = exporter._to_docx(title, include_graph=True, language="en", output_path=str(tmp_path))
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = Path(path).name

        elif format == "svg":
            visualizer = GraphVisualizer(graph, cfg)
            dot = visualizer.to_dot(max_nodes=max_nodes)
            # Convert DOT to SVG-like text representation
            svg_content = _dot_to_svg(dot, title=title, max_nodes=max_nodes)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            media_type = "image/svg+xml"
            filename = f"graph{ext}"

        elif format == "json":
            visualizer = GraphVisualizer(graph, cfg)
            content = visualizer.to_json(max_nodes=max_nodes)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            media_type = "application/json"
            filename = f"graph{ext}"

        elif format == "mermaid":
            visualizer = GraphVisualizer(graph, cfg)
            content = visualizer.to_mermaid(max_nodes=max_nodes)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            media_type = "text/plain"
            filename = f"graph{ext}"

        return FileResponse(
            path=str(tmp_path),
            filename=filename,
            media_type=media_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _dot_to_svg(dot: str, title: str = "Knowledge Graph", max_nodes: int = 50) -> str:
    """Convert DOT string to a simple SVG representation."""
    # Parse DOT to extract nodes and edges
    import re

    lines = dot.split("\n")
    nodes = []
    edges = []
    in_edges = False

    for line in lines:
        line = line.strip()
        if "->" in line:
            # Parse edge: "src" -> "tgt" [label="...", ...]
            match = re.match(r'"([^"]+)"\s*->\s*"([^"]+)"', line)
            if match:
                src, tgt = match.groups()
                label_match = re.search(r'label="([^"]+)"', line)
                edges.append((src, tgt, label_match.group(1) if label_match else ""))
        elif line.startswith('"') and "[" in line:
            # Parse node: "id" [label="name", ...]
            match = re.match(r'"([^"]+)"\s*\[.*?label="([^"]+)"', line)
            if match:
                node_id, label = match.groups()
                nodes.append((node_id, label[:30]))

    # Generate SVG
    n = len(nodes)
    if n == 0:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400"><text x="300" y="200" text-anchor="middle" fill="#999">No entities</text></svg>'

    cols = min(6, n)
    rows = (n + cols - 1) // cols
    node_w, node_h = 110, 50
    padding = 20
    svg_w = cols * (node_w + padding) + padding
    svg_h = rows * (node_h + padding * 2) + 60

    type_colors = {
        "person": "#5e6ad2",
        "organization": "#2ea44f",
        "location": "#f59e0b",
        "concept": "#e03e3e",
        "technology": "#9333ea",
        "event": "#06b6d4",
        "work": "#ffc107",
        "topic": "#607d8b",
        "unknown": "#6e6e73",
    }

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">',
        f'  <rect width="{svg_w}" height="{svg_h}" fill="#fafafa"/>',
        f'  <text x="{svg_w//2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#333">{title}</text>',
    ]

    for i, (node_id, label) in enumerate(nodes):
        col = i % cols
        row = i // cols
        x = padding + col * (node_w + padding)
        y = 50 + padding + row * (node_h + padding * 2)
        svg_lines.append(
            f'  <rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8" fill="#6e6e73" stroke="#fff" stroke-width="2"/>'
        )
        svg_lines.append(
            f'  <text x="{x + node_w//2}" y="{y + node_h//2 + 5}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#fff">{label}</text>'
        )

    for src, tgt, label in edges:
        src_i = next((i for i, (nid, _) in enumerate(nodes) if nid == src), -1)
        tgt_i = next((i for i, (nid, _) in enumerate(nodes) if nid == tgt), -1)
        if src_i >= 0 and tgt_i >= 0:
            sc, sr = src_i % cols, src_i // cols
            tc, tr = tgt_i % cols, tgt_i // cols
            sx = padding + sc * (node_w + padding) + node_w // 2
            sy = 50 + padding + sr * (node_h + padding * 2) + node_h
            tx = padding + tc * (node_w + padding) + node_w // 2
            ty = 50 + padding + tr * (node_h + padding * 2)
            mx = (sx + tx) // 2
            my = (sy + ty) // 2
            svg_lines.append(f'  <line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" stroke="#aaa" stroke-width="1.5"/>')
            if label:
                svg_lines.append(
                    f'  <text x="{mx}" y="{my - 5}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#666">{label}</text>'
                )

    svg_lines.append(f'  <text x="{svg_w//2}" y="{svg_h - 10}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#999">Generated by Ariadne | {n} entities</text>')
    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


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

class SPAStaticFiles(StaticFiles):
    """StaticFiles that also serves index.html for SPA fallback.

    Normal StaticFiles with html=True only serves index.html for directory
    paths (ending in /). This class additionally serves index.html for any
    non-file path (like /memory /search), enabling full SPA client-side routing.

    IMPORTANT — Fallback Safety Check:
    We MUST check os.path.isfile() before returning index.html on 404.
    Without this check, if a real static file (e.g. /assets/index-xxx.js)
    exists but StaticFiles raises 404 for some other reason (e.g. a
    permission or encoding error), we would incorrectly return index.html.
    The browser then receives HTML instead of JavaScript, causing:
        "Failed to load module script: Expected a JavaScript-or-Wasm module
         script but the server responded with a MIME type of text/html"
    This manifests as a blank page. The fix: only serve index.html when the
    file genuinely does not exist on disk.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                # Only serve index.html if the file truly does not exist.
                # See class docstring for the full explanation of why this check is needed.
                full_path = os.path.join(self.directory, path.lstrip("/"))
                if os.path.isfile(full_path):
                    raise  # File exists but failed for another reason — re-raise
                if not scope.get("path", "").startswith("/api"):
                    index_path = os.path.join(self.directory, "index.html")
                    if os.path.isfile(index_path):
                        return FileResponse(index_path)
            raise


def run_server(host: str = "127.0.0.1", port: int = 8770, reload: bool = False):
    """Run the Ariadne web server."""
    import uvicorn

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app = create_app()
        # SPAStaticFiles: serves static assets + index.html fallback for SPA routing
        app.mount("/", SPAStaticFiles(directory=str(static_dir), html=True), name="static")
        uvicorn.run(app, host=host, port=port)
    else:
        # API-only mode (frontend not built yet)
        uvicorn.run("ariadne.web.api:create_app", host=host, port=port, reload=reload, factory=True)
