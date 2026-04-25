"""
Ariadne Wiki Web API — FastAPI routes for the LLM Wiki feature.

Endpoints:
  POST /api/wiki/init           — Initialize a new wiki project
  POST /api/wiki/ingest         — Ingest a source file (two-step CoT)
  POST /api/wiki/ingest-vault   — Import an Obsidian vault
  POST /api/wiki/query          — Query the wiki
  POST /api/wiki/lint           — Run lint checks
  GET  /api/wiki/pages          — List all wiki pages
  GET  /api/wiki/page           — Get a single wiki page content
  GET  /api/wiki/log            — Get wiki operation log
  GET  /api/wiki/index          — Get wiki index
  GET  /api/wiki/overview       — Get wiki overview
  GET  /api/wiki/projects       — List recent wiki projects
"""

import os
import platform
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


# ── Request/Response Models ────────────────────────────────────────────────────

class WikiInitRequest(BaseModel):
    project_path: str
    name: Optional[str] = ""
    schema_content: Optional[str] = ""
    purpose_content: Optional[str] = ""


class WikiIngestRequest(BaseModel):
    source_path: str
    project_path: str = "."
    language: Optional[str] = ""
    folder_context: Optional[str] = ""
    skip_cache: bool = False


class WikiVaultImportRequest(BaseModel):
    vault_path: str
    project_path: str = "."
    language: Optional[str] = ""
    ingest_immediately: bool = False


class WikiQueryRequest(BaseModel):
    question: str
    project_path: str = "."
    language: Optional[str] = ""
    save_to_wiki: bool = False


class WikiLintRequest(BaseModel):
    project_path: str = "."
    structural_only: bool = False
    language: Optional[str] = ""


class WikiPageRequest(BaseModel):
    project_path: str
    relative_path: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def _get_project(project_path: str):
    from ariadne.wiki.models import WikiProject
    return WikiProject(root_path=os.path.abspath(project_path))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/init")
async def wiki_init(req: WikiInitRequest):
    """Initialize a new LLM Wiki project directory structure."""
    try:
        from ariadne.wiki import init_wiki_project
        project = init_wiki_project(
            req.project_path,
            name=req.name or "",
            schema_content=req.schema_content or "",
            purpose_content=req.purpose_content or "",
        )
        return {
            "ok": True,
            "project_path": project.root_path,
            "wiki_dir": project.wiki_dir,
            "message": "Wiki project initialized successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def wiki_ingest(req: WikiIngestRequest):
    """
    Ingest a source file into the wiki using two-step Chain-of-Thought.
    Returns the list of wiki pages written and any review items.
    """
    try:
        from ariadne.wiki import ingest_source
        project = _get_project(req.project_path)

        source_path = os.path.abspath(req.source_path)
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail=f"Source file not found: {source_path}")

        result = ingest_source(
            project=project,
            source_path=source_path,
            language=req.language or "",
            folder_context=req.folder_context or "",
            skip_cache=req.skip_cache,
        )

        return {
            "ok": True,
            "source_file": result.source_file,
            "pages_written": result.pages_written,
            "pages_count": len(result.pages_written),
            "review_items": result.review_items,
            "warnings": result.warnings,
            "cached": result.cached,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-vault")
async def wiki_ingest_vault(req: WikiVaultImportRequest):
    """Import an Obsidian vault into the wiki project."""
    try:
        from ariadne.wiki import import_obsidian_vault
        project = _get_project(req.project_path)

        vault_path = os.path.abspath(req.vault_path)
        if not os.path.isdir(vault_path):
            raise HTTPException(status_code=404, detail=f"Vault directory not found: {vault_path}")

        result = import_obsidian_vault(
            vault_path=vault_path,
            project=project,
            copy_to_raw=True,
            ingest_immediately=req.ingest_immediately,
            language=req.language or "",
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "ok": True,
            "imported_count": len(result["imported_files"]),
            "skipped_count": len(result["skipped_files"]),
            "errors": result["errors"],
            "ingest_results": result.get("ingest_results", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def wiki_query(req: WikiQueryRequest):
    """Query the wiki knowledge base and get a cited answer."""
    try:
        from ariadne.wiki import query_wiki
        project = _get_project(req.project_path)

        result = query_wiki(
            project=project,
            question=req.question,
            language=req.language or "",
            save_to_wiki=req.save_to_wiki,
        )

        return {
            "ok": True,
            "question": result.question,
            "answer": result.answer,
            "cited_pages": result.cited_pages,
            "saved_to": result.saved_to,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lint")
async def wiki_lint(req: WikiLintRequest):
    """Run structural and/or semantic lint checks on the wiki."""
    try:
        from ariadne.wiki import run_structural_lint, run_full_lint
        project = _get_project(req.project_path)

        if req.structural_only:
            results = run_structural_lint(project)
        else:
            results = run_full_lint(project, language=req.language or "")

        return {
            "ok": True,
            "issues": [
                {
                    "type": r.issue_type.value,
                    "severity": r.severity.value,
                    "page": r.page,
                    "detail": r.detail,
                    "affected_pages": r.affected_pages,
                }
                for r in results
            ],
            "total": len(results),
            "warnings": sum(1 for r in results if r.severity.value == "warning"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pages")
async def wiki_pages(project_path: str = "."):
    """List all wiki pages with metadata."""
    try:
        from ariadne.wiki import list_wiki_pages, read_wiki_page
        project = _get_project(project_path)

        if not os.path.exists(project.wiki_dir):
            return {"ok": True, "pages": [], "total": 0}

        page_paths = list_wiki_pages(project.wiki_dir)
        pages = []

        for path in page_paths:
            rel = os.path.relpath(path, project.wiki_dir).replace("\\", "/")
            page = read_wiki_page(path)
            if page:
                pages.append({
                    "path": rel,
                    "type": page.frontmatter.page_type.value,
                    "title": page.frontmatter.title,
                    "tags": page.frontmatter.tags,
                    "updated": page.frontmatter.updated,
                    "sources": page.frontmatter.sources,
                })
            else:
                pages.append({"path": rel, "type": "unknown", "title": rel})

        return {"ok": True, "pages": pages, "total": len(pages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page")
async def wiki_page(project_path: str = ".", relative_path: str = ""):
    """Get the content of a single wiki page."""
    try:
        from ariadne.wiki.builder import read_file_safe
        project = _get_project(project_path)

        full_path = os.path.join(project.root_path, relative_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail=f"Page not found: {relative_path}")

        content = read_file_safe(full_path)
        return {"ok": True, "path": relative_path, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/log")
async def wiki_log(project_path: str = "."):
    """Get the wiki operation log."""
    try:
        from ariadne.wiki.builder import read_file_safe
        project = _get_project(project_path)
        content = read_file_safe(project.log_path)
        return {"ok": True, "content": content or "(No log yet)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index")
async def wiki_index(project_path: str = "."):
    """Get the wiki index."""
    try:
        from ariadne.wiki.builder import read_file_safe
        project = _get_project(project_path)
        content = read_file_safe(project.index_path)
        return {"ok": True, "content": content or "(No index yet)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview")
async def wiki_overview(project_path: str = "."):
    """Get the wiki overview page."""
    try:
        from ariadne.wiki.builder import read_file_safe
        project = _get_project(project_path)
        content = read_file_safe(project.overview_path)
        return {"ok": True, "content": content or "(No overview yet)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def wiki_recent_projects():
    """List recent wiki projects from config."""
    try:
        config_path = os.path.join(os.path.expanduser("~"), ".ariadne", "wiki_projects.json")
        if not os.path.exists(config_path):
            return {"ok": True, "projects": []}

        import json
        with open(config_path, "r", encoding="utf-8") as f:
            projects = json.load(f)
        return {"ok": True, "projects": projects}
    except Exception as e:
        return {"ok": True, "projects": []}


class WikiSaveProjectRequest(BaseModel):
    project_path: str


@router.post("/projects/save")
async def wiki_save_project(req: WikiSaveProjectRequest):
    """Save a wiki project path to the recent projects list."""
    try:
        import json
        config_dir = os.path.join(os.path.expanduser("~"), ".ariadne")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "wiki_projects.json")

        projects = []
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                projects = json.load(f)

        abs_path = os.path.abspath(req.project_path)
        if abs_path not in projects:
            projects.insert(0, abs_path)
            projects = projects[:10]  # Keep last 10

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)

        return {"ok": True, "project_path": abs_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── File System Browser ────────────────────────────────────────────────────────

@router.get("/fs/browse")
async def fs_browse(path: str = "", mode: str = "dir"):
    """
    Browse the local filesystem.

    mode: "dir" — list directories only (for project dir selection)
          "file" — list files (for source file selection)
    Args:
        path: absolute directory to list; empty = platform drives or home
        mode: "dir" or "file"
    """
    try:
        # Default start: home directory
        if not path:
            path = os.path.expanduser("~")

        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=404, detail=f"Directory not found: {abs_path}")

        entries = []
        try:
            items = sorted(os.listdir(abs_path), key=lambda x: (not os.path.isdir(os.path.join(abs_path, x)), x.lower()))
        except PermissionError:
            items = []

        for name in items:
            full = os.path.join(abs_path, name)
            is_dir = os.path.isdir(full)
            if name.startswith('.'):
                continue
            if mode == "dir" and not is_dir:
                continue
            entries.append({
                "name": name,
                "path": full,
                "is_dir": is_dir,
            })

        # Build parent path
        parent = os.path.dirname(abs_path) if abs_path != os.path.dirname(abs_path) else None

        # Windows: add drives list at root
        drives = []
        if platform.system() == "Windows" and (not path or abs_path == parent):
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase
                      if os.path.exists(f"{d}:\\")]

        return {
            "ok": True,
            "current": abs_path,
            "parent": parent,
            "entries": entries,
            "drives": drives,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
