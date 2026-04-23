"""
Ariadne Wiki Builder — Project initialization, file I/O, and utilities.

Handles:
- Wiki project directory creation (wiki init)
- Reading/writing wiki pages with frontmatter
- File block parsing (---FILE: ... ---END FILE---)
- Review block parsing (---REVIEW: ... ---END REVIEW---)
- Index and log management
"""

import os
import re
import hashlib
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from ariadne.wiki.models import (
    WikiProject, WikiPage, WikiFrontmatter, WikiPageType,
    IngestResult, LintResult, LintIssueType, LintSeverity,
)


# ── File Block Parser ──────────────────────────────────────────────────────────

# Regex patterns for parsing LLM output
OPENER_PATTERN = re.compile(r'^---\s*FILE:\s*(.+?)\s*---\s*$', re.IGNORECASE)
CLOSER_PATTERN = re.compile(r'^---\s*END\s+FILE\s*---\s*$', re.IGNORECASE)
FENCE_PATTERN = re.compile(r'^\s{0,3}(```+|~~~+)')

REVIEW_BLOCK_PATTERN = re.compile(
    r'---REVIEW:\s*(\w[\w-]*)\s*\|\s*(.+?)\s*---\n([\s\S]*?)---END REVIEW---'
)

LINT_BLOCK_PATTERN = re.compile(
    r'---LINT:\s*([^\n|]+?)\s*\|\s*([^\n|]+?)\s*\|\s*([^\n-]+?)\s*---\n([\s\S]*?)---END LINT---'
)


def parse_file_blocks(text: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parse LLM stage-2 output into FILE blocks.

    Returns:
        Tuple of (blocks, warnings) where each block has 'path' and 'content'.
    """
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")

    blocks: List[Dict[str, str]] = []
    warnings: List[str] = []

    i = 0
    while i < lines.length if hasattr(lines, 'length') else len(lines):
        opener_match = OPENER_PATTERN.match(lines[i])
        if not opener_match:
            i += 1
            continue

        path = opener_match.group(1).strip()
        i += 1

        content_lines: List[str] = []
        fence_marker: Optional[str] = None
        fence_len = 0
        closed = False

        while i < len(lines):
            line = lines[i]

            # Track code fences
            fence_match = FENCE_PATTERN.match(line)
            if fence_match:
                run = fence_match.group(1)
                char = run[0]
                length = len(run)
                if fence_marker is None:
                    fence_marker = char
                    fence_len = length
                elif char == fence_marker and length >= fence_len:
                    fence_marker = None
                    fence_len = 0
                content_lines.append(line)
                i += 1
                continue

            # Check closer only outside fences
            if fence_marker is None and CLOSER_PATTERN.match(line):
                closed = True
                i += 1
                break

            content_lines.append(line)
            i += 1

        if not closed:
            path_label = path or "(unnamed)"
            msg = f'FILE block "{path_label}" not closed — likely truncation. Block dropped.'
            warnings.append(msg)
            continue

        if not path:
            warnings.append("FILE block with empty path skipped.")
            continue

        blocks.append({"path": path, "content": "\n".join(content_lines)})

    return blocks, warnings


def parse_review_blocks(text: str, source_path: str = "") -> List[Dict[str, Any]]:
    """Parse REVIEW blocks from LLM output."""
    items: List[Dict[str, Any]] = []

    for match in REVIEW_BLOCK_PATTERN.finditer(text):
        raw_type = match.group(1).strip().lower()
        title = match.group(2).strip()
        body = match.group(3).strip()

        valid_types = ["contradiction", "duplicate", "missing-page", "suggestion"]
        review_type = raw_type if raw_type in valid_types else "confirm"

        # Parse OPTIONS
        options_match = re.search(r'^OPTIONS:\s*(.+)$', body, re.MULTILINE)
        options = []
        if options_match:
            options = [o.strip() for o in options_match.group(1).split("|")]
        else:
            options = ["Create Page", "Skip"]

        # Parse PAGES
        pages_match = re.search(r'^PAGES:\s*(.+)$', body, re.MULTILINE)
        affected_pages = [p.strip() for p in pages_match.group(1).split(",")] if pages_match else []

        # Parse SEARCH
        search_match = re.search(r'^SEARCH:\s*(.+)$', body, re.MULTILINE)
        search_queries = [q.strip() for q in search_match.group(1).split("|") if q.strip()] if search_match else []

        # Description without structured fields
        description = re.sub(r'^OPTIONS:.*$', '', body, flags=re.MULTILINE)
        description = re.sub(r'^PAGES:.*$', '', description, flags=re.MULTILINE)
        description = re.sub(r'^SEARCH:.*$', '', description, flags=re.MULTILINE)
        description = description.strip()

        items.append({
            "type": review_type,
            "title": title,
            "description": description,
            "source_path": source_path,
            "affected_pages": affected_pages,
            "search_queries": search_queries,
            "options": options,
        })

    return items


# ── Wiki Project Initialization ────────────────────────────────────────────────

SCHEMA_DEFAULT = """# Wiki Schema

This document defines the structure and conventions for this wiki.

## Page Types

| Type | Directory | Description |
|------|-----------|-------------|
| source | wiki/sources/ | Summary of an ingested source document |
| entity | wiki/entities/ | People, organizations, products, datasets |
| concept | wiki/concepts/ | Theories, methods, techniques, phenomena |
| query | wiki/queries/ | Saved Q&A and research results |
| synthesis | wiki/synthesis/ | Cross-source analysis |
| comparison | wiki/comparisons/ | Side-by-side comparisons |

## Conventions

- Use [[wikilinks]] for cross-references
- Every page has YAML frontmatter with type, title, created, updated, tags, related, sources
- Use kebab-case filenames
- Raw sources in raw/sources/ are immutable — never modify them
- The LLM owns the wiki layer — it creates, updates, and maintains all wiki pages
"""

PURPOSE_DEFAULT = """# Wiki Purpose

This document defines *why* this wiki exists.

## Goals

- [Define your research goals here]

## Key Questions

- [What are you trying to answer?]

## Research Scope

- [What topics and domains does this wiki cover?]

## Evolving Thesis

- [As you read more sources, your understanding will evolve. Capture that here.]
"""

INDEX_DEFAULT = """# Wiki Index

## Entities

*(No entities yet)*

## Concepts

*(No concepts yet)*

## Sources

*(No sources yet)*

## Queries

*(No saved queries yet)*
"""

OVERVIEW_DEFAULT = """# Wiki Overview

This wiki is a knowledge base built from your source documents. As you add more sources, this overview will be automatically updated to reflect the current state of knowledge.
"""

LOG_DEFAULT = """# Wiki Log

This is a chronological record of wiki operations.
"""


def init_wiki_project(
    project_path: str,
    name: str = "",
    schema_content: str = "",
    purpose_content: str = "",
) -> WikiProject:
    """
    Initialize a new wiki project directory structure.

    Creates:
        project_root/
        ├── schema.md
        ├── purpose.md
        ├── raw/
        │   ├── sources/
        │   └── assets/
        └── wiki/
            ├── index.md
            ├── log.md
            ├── overview.md
            ├── entities/
            ├── concepts/
            ├── sources/
            ├── queries/
            ├── synthesis/
            └── comparisons/
    """
    project = WikiProject(root_path=os.path.abspath(project_path), name=name)

    # Create directories
    dirs = [
        project.raw_dir,
        project.sources_dir,
        project.assets_dir,
        project.wiki_dir,
        project.entities_dir,
        project.concepts_dir,
        project.wiki_sources_dir,
        project.queries_dir,
        project.synthesis_dir,
        project.comparisons_dir,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # Create schema.md
    if not os.path.exists(project.schema_path):
        with open(project.schema_path, "w", encoding="utf-8") as f:
            f.write(schema_content or SCHEMA_DEFAULT)

    # Create purpose.md
    if not os.path.exists(project.purpose_path):
        with open(project.purpose_path, "w", encoding="utf-8") as f:
            f.write(purpose_content or PURPOSE_DEFAULT)

    # Create wiki files
    if not os.path.exists(project.index_path):
        with open(project.index_path, "w", encoding="utf-8") as f:
            f.write(INDEX_DEFAULT)

    if not os.path.exists(project.log_path):
        with open(project.log_path, "w", encoding="utf-8") as f:
            f.write(LOG_DEFAULT)

    if not os.path.exists(project.overview_path):
        with open(project.overview_path, "w", encoding="utf-8") as f:
            f.write(OVERVIEW_DEFAULT)

    return project


# ── File I/O ───────────────────────────────────────────────────────────────────

def read_file_safe(path: str) -> str:
    """Read file content, return empty string on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        try:
            with open(path, "r", encoding="gb18030") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return ""


def write_file_safe(path: str, content: str) -> bool:
    """Write file content, creating parent directories as needed."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except OSError as e:
        return False


def write_wiki_page(project: WikiProject, relative_path: str, content: str) -> bool:
    """
    Write a wiki page with smart merge logic:
    - log.md: append new content
    - index.md / overview.md: overwrite wholesale
    - content pages: merge sources[] from existing page
    """
    full_path = os.path.join(project.root_path, relative_path)

    # log.md: append
    if relative_path.endswith("/log.md") or relative_path == "wiki/log.md":
        existing = read_file_safe(full_path)
        new_content = f"{existing}\n\n{content.strip()}" if existing else content.strip()
        return write_file_safe(full_path, new_content)

    # index.md / overview.md: overwrite
    if (relative_path.endswith("/index.md") or relative_path == "wiki/index.md" or
            relative_path.endswith("/overview.md") or relative_path == "wiki/overview.md"):
        return write_file_safe(full_path, content)

    # Content pages: merge sources field
    existing = read_file_safe(full_path)
    if existing:
        content = _merge_sources(content, existing)

    return write_file_safe(full_path, content)


def _merge_sources(new_content: str, existing_content: str) -> str:
    """Merge sources[] from existing page into new content to preserve source history."""
    existing_fm = WikiFrontmatter.from_yaml(existing_content)
    new_fm = WikiFrontmatter.from_yaml(new_content)

    if not existing_fm.sources and not new_fm.sources:
        return new_content

    # Merge source lists (case-insensitive dedup, preserve order)
    merged = list(new_fm.sources)
    existing_lower = {s.lower() for s in new_fm.sources}
    for s in existing_fm.sources:
        if s.lower() not in existing_lower:
            merged.append(s)
            existing_lower.add(s.lower())

    # Replace sources in new content
    new_fm.sources = merged
    old_sources_line = re.search(r'^sources:\s*\[.*?\]', new_content, re.MULTILINE)
    if old_sources_line:
        new_content = re.sub(
            r'^sources:\s*\[.*?\]',
            f"sources: {merged}",
            new_content,
            flags=re.MULTILINE,
        )
    return new_content


def write_file_blocks(project: WikiProject, llm_output: str) -> Tuple[List[str], List[str]]:
    """
    Parse and write FILE blocks from LLM output.

    Returns:
        Tuple of (written_paths, warnings)
    """
    blocks, parse_warnings = parse_file_blocks(llm_output)
    written: List[str] = []
    warnings = list(parse_warnings)

    for block in blocks:
        relative_path = block["path"]
        content = block["content"]

        if write_wiki_page(project, relative_path, content):
            written.append(relative_path)
        else:
            msg = f'Failed to write "{relative_path}"'
            warnings.append(msg)

    return written, warnings


def read_wiki_page(path: str) -> Optional[WikiPage]:
    """Read and parse a wiki page from disk."""
    content = read_file_safe(path)
    if not content:
        return None

    fm = WikiFrontmatter.from_yaml(content)

    # Extract body (after frontmatter)
    body = content
    if content.startswith("---"):
        end_match = re.search(r'\n---\n', content[3:])
        if end_match:
            body = content[3 + end_match.start() + 4:]

    return WikiPage(
        path=path,
        frontmatter=fm,
        content=body.strip(),
    )


def list_wiki_pages(wiki_dir: str) -> List[str]:
    """List all .md files in wiki directory recursively."""
    pages = []
    for root, dirs, files in os.walk(wiki_dir):
        for f in files:
            if f.endswith(".md"):
                pages.append(os.path.join(root, f))
    return sorted(pages)


def get_wiki_page_slugs(wiki_dir: str) -> Dict[str, str]:
    """Build a slug→path map from wiki files (case-insensitive)."""
    slug_map: Dict[str, str] = {}
    for root, dirs, files in os.walk(wiki_dir):
        for f in files:
            if f.endswith(".md"):
                full_path = os.path.join(root, f)
                rel = os.path.relpath(full_path, wiki_dir)
                slug = rel.replace("\\", "/").replace(".md", "")
                slug_map[slug.lower()] = full_path
                # Also index by basename
                basename = os.path.splitext(f)[0].lower()
                slug_map[basename] = full_path
    return slug_map


# ── Ingest Cache ───────────────────────────────────────────────────────────────

def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content for cache checking."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def check_ingest_cache(project: WikiProject, source_file: str, content: str) -> Optional[List[str]]:
    """
    Check if source has already been ingested with identical content.

    Returns list of previously written paths if cached, None if not cached.
    """
    cache_dir = os.path.join(project.root_path, ".ariadne-wiki-cache")
    cache_file = os.path.join(cache_dir, "ingest_cache.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    content_hash = compute_content_hash(content)
    key = os.path.basename(source_file)

    if key in cache and cache[key].get("hash") == content_hash:
        return cache[key].get("files", [])

    return None


def save_ingest_cache(project: WikiProject, source_file: str, content: str, files_written: List[str]) -> None:
    """Save ingest result to cache."""
    cache_dir = os.path.join(project.root_path, ".ariadne-wiki-cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "ingest_cache.json")

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        cache = {}

    content_hash = compute_content_hash(content)
    key = os.path.basename(source_file)
    cache[key] = {
        "hash": content_hash,
        "files": files_written,
        "timestamp": datetime.now().isoformat(),
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ── Wikilink Utilities ─────────────────────────────────────────────────────────

def extract_wikilinks(content: str) -> List[str]:
    """Extract [[wikilinks]] from markdown content."""
    pattern = r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]'
    return [m.strip() for m in re.findall(pattern, content)]


def append_log_entry(project: WikiProject, operation: str, title: str, detail: str = "") -> None:
    """Append an entry to wiki/log.md."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n\n## [{date_str}] {operation} | {title}\n"
    if detail:
        entry += f"{detail}\n"
    existing = read_file_safe(project.log_path)
    write_file_safe(project.log_path, existing + entry)
