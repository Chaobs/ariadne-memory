"""
Ariadne Wiki Obsidian Support — Ingest Obsidian vaults and notes.

Supports:
- Obsidian vault directory import (preserves folder structure)
- [[wikilink]] syntax preservation
- YAML frontmatter passthrough
- Obsidian tags (#tag), callouts (> [!note]), embeds (![[file]])
- .md files with Obsidian-specific extensions

This module provides:
1. ObsidianIngestor — for Ariadne's vector store pipeline (standard ingest)
2. import_obsidian_vault — for LLM Wiki pipeline (copies vault as raw sources)
"""

import os
import re
import shutil
from typing import List, Optional, Dict, Any

from ariadne.ingest.base import BaseIngestor, Document, SourceType
from ariadne.wiki.models import WikiProject
from ariadne.wiki.builder import read_file_safe, write_file_safe


# ── Obsidian Markdown Parser ───────────────────────────────────────────────────

def parse_obsidian_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from an Obsidian note."""
    if not content.startswith("---"):
        return {}

    end = content.find("\n---\n", 3)
    if end == -1:
        return {}

    try:
        import yaml
        fm_text = content[3:end]
        return yaml.safe_load(fm_text) or {}
    except Exception:
        return {}


def extract_obsidian_tags(content: str) -> List[str]:
    """Extract #tags from Obsidian content (excluding code blocks)."""
    # Remove code blocks first
    clean = re.sub(r'```[\s\S]*?```', '', content)
    clean = re.sub(r'`[^`]+`', '', clean)
    # Match #tag patterns (not color codes)
    return re.findall(r'(?<!\w)#([a-zA-Z][a-zA-Z0-9_/-]*)', clean)


def convert_obsidian_to_markdown(content: str) -> str:
    """
    Convert Obsidian-specific syntax to standard Markdown.

    Handles:
    - [[wikilinks]] → kept as-is (Ariadne supports them)
    - [[wikilink|alias]] → [alias](wikilink)
    - ![[embed]] → ![embed](embed) for images, [embed](embed) for other files
    - ==highlight== → **highlight**
    - Callouts: > [!note] → > **Note:**
    """
    # Keep [[wikilinks]] as-is — Ariadne uses them natively
    # Convert [[link|alias]] to markdown
    content = re.sub(
        r'\[\[([^\]|]+)\|([^\]]+)\]\]',
        lambda m: f'[{m.group(2)}]({m.group(1)})',
        content
    )

    # Convert image embeds ![[image.png]] → ![image.png](image.png)
    content = re.sub(
        r'!\[\[([^\]]+\.(png|jpg|jpeg|gif|webp|svg))\]\]',
        lambda m: f'![{m.group(1)}]({m.group(1)})',
        content,
        flags=re.IGNORECASE
    )

    # Convert non-image embeds ![[file]] → [file](file)
    content = re.sub(
        r'!\[\[([^\]]+)\]\]',
        lambda m: f'[{m.group(1)}]({m.group(1)})',
        content
    )

    # Convert ==highlights== to **bold**
    content = re.sub(r'==([^=]+)==', r'**\1**', content)

    # Normalize callout syntax: > [!note] → > **Note:**
    def replace_callout(m):
        callout_type = m.group(1).lower()
        callout_map = {
            'note': 'Note', 'tip': 'Tip', 'warning': 'Warning',
            'danger': 'Danger', 'info': 'Info', 'important': 'Important',
            'abstract': 'Abstract', 'todo': 'TODO', 'question': 'Question',
        }
        label = callout_map.get(callout_type, callout_type.capitalize())
        return f'> **{label}:**'

    content = re.sub(r'> \[!(\w+)\]', replace_callout, content)

    return content


# ── ObsidianIngestor — for standard Ariadne vector store pipeline ──────────────

class ObsidianIngestor(BaseIngestor):
    """
    Ingestor for Obsidian Markdown notes (.md files from Obsidian vaults).

    Handles Obsidian-specific syntax:
    - [[wikilinks]] (kept as-is)
    - YAML frontmatter (parsed for metadata)
    - #tags extraction
    - ==highlights== conversion
    - Callout blocks
    """

    SUPPORTED_EXTENSIONS = [".md"]
    SOURCE_TYPE = SourceType.MARKDOWN

    def _extract(self, path: "Path") -> List[str]:
        """Return raw text content of the file as a single-element list."""
        content = read_file_safe(str(path))
        return [content] if content else []

    def can_handle(self, source: str) -> bool:
        return source.lower().endswith(".md")

    def ingest(self, source: str, **kwargs) -> List[Document]:
        """Ingest an Obsidian markdown file."""
        content = read_file_safe(source)
        if not content:
            return []

        # Parse frontmatter
        frontmatter = parse_obsidian_frontmatter(content)

        # Strip frontmatter from body
        body = content
        if content.startswith("---"):
            end = content.find("\n---\n", 3)
            if end != -1:
                body = content[end + 4:]

        # Extract Obsidian tags
        obs_tags = extract_obsidian_tags(body)

        # Convert Obsidian syntax
        converted = convert_obsidian_to_markdown(body)

        # Build metadata
        tags = frontmatter.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tags]
        tags = list(tags) + obs_tags

        title = (
            frontmatter.get("title")
            or frontmatter.get("aliases", [None])[0]
            or os.path.splitext(os.path.basename(source))[0]
        )

        metadata = {
            "source": source,
            "source_type": "obsidian",
            "title": title,
            "tags": list(set(tags)),
            "frontmatter": frontmatter,
            "is_obsidian": True,
        }

        # Split into chunks by heading
        chunks = self._split_by_heading(converted, source, metadata)
        return chunks if chunks else [Document(
            content=converted or content,
            metadata=metadata,
            source_path=source,
            source_type=self.SOURCE_TYPE,
        )]

    def _split_by_heading(
        self,
        content: str,
        source: str,
        base_metadata: Dict[str, Any],
    ) -> List[Document]:
        """Split Obsidian note by headings into multiple Documents."""
        sections = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

        if len(sections) <= 1:
            return []  # No headings — return as single doc

        docs = []
        current_heading = os.path.splitext(os.path.basename(source))[0]
        current_content_parts = []

        for section in sections:
            if re.match(r'^#{1,3}\s+', section):
                # Save previous section
                if current_content_parts:
                    body = "\n".join(current_content_parts).strip()
                    if body:
                        docs.append(Document(
                            content=f"{current_heading}\n\n{body}",
                            metadata={**base_metadata, "section": current_heading},
                            source_path=source,
                            source_type=self.SOURCE_TYPE,
                        ))
                current_heading = section
                current_content_parts = []
            else:
                current_content_parts.append(section)

        # Last section
        if current_content_parts:
            body = "\n".join(current_content_parts).strip()
            if body:
                docs.append(Document(
                    content=f"{current_heading}\n\n{body}",
                    metadata={**base_metadata, "section": current_heading},
                    source_path=source,
                    source_type=self.SOURCE_TYPE,
                ))

        return docs


# ── Vault Import — for LLM Wiki pipeline ──────────────────────────────────────

def import_obsidian_vault(
    vault_path: str,
    project: WikiProject,
    copy_to_raw: bool = True,
    ingest_immediately: bool = False,
    llm_config: Optional[Dict[str, Any]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Import an Obsidian vault into the wiki project.

    Two modes:
    1. copy_to_raw=True: Copies .md files to raw/sources/ for later LLM Wiki ingestion
    2. ingest_immediately=True: Also runs two-step LLM ingest on each file

    Args:
        vault_path: Path to the Obsidian vault directory
        project: Target WikiProject
        copy_to_raw: Copy files to raw/sources/
        ingest_immediately: Run LLM Wiki ingest after copying
        llm_config: LLM config for immediate ingest
        include_patterns: Glob patterns to include (default: all .md)
        exclude_patterns: Patterns to exclude (e.g., [".obsidian", "templates"])

    Returns:
        Dict with imported_files, skipped_files, errors
    """
    if not os.path.isdir(vault_path):
        return {"error": f"Not a directory: {vault_path}", "imported": [], "skipped": [], "errors": []}

    DEFAULT_EXCLUDES = [".obsidian", ".trash", "templates", "Templates", "attachments"]
    exclude = list(set((exclude_patterns or []) + DEFAULT_EXCLUDES))

    imported: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    os.makedirs(project.sources_dir, exist_ok=True)

    for root, dirs, files in os.walk(vault_path):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith(".")]

        for fname in files:
            if not fname.endswith(".md"):
                continue

            src_path = os.path.join(root, fname)
            rel_from_vault = os.path.relpath(src_path, vault_path).replace("\\", "/")

            # Check exclude patterns
            should_skip = any(
                excl.lower() in rel_from_vault.lower()
                for excl in exclude
            )
            if should_skip:
                skipped.append(rel_from_vault)
                continue

            # Target path in raw/sources/ (preserve folder structure)
            rel_folder = os.path.dirname(rel_from_vault)
            if rel_folder:
                target_dir = os.path.join(project.sources_dir, rel_folder)
            else:
                target_dir = project.sources_dir

            os.makedirs(target_dir, exist_ok=True)
            dst_path = os.path.join(target_dir, fname)

            if copy_to_raw:
                try:
                    shutil.copy2(src_path, dst_path)
                    imported.append(dst_path)
                except Exception as e:
                    errors.append(f"{rel_from_vault}: {e}")
                    continue

    # Optionally ingest immediately
    ingest_results = []
    if ingest_immediately and imported:
        from ariadne.wiki.ingestor import ingest_source
        for path in imported:
            try:
                result = ingest_source(
                    project=project,
                    source_path=path,
                    llm_config=llm_config,
                    folder_context=os.path.relpath(os.path.dirname(path), project.sources_dir),
                )
                ingest_results.append({
                    "file": path,
                    "pages": result.pages_written,
                    "cached": result.cached,
                })
            except Exception as e:
                errors.append(f"Ingest failed for {path}: {e}")

    return {
        "imported_files": imported,
        "skipped_files": skipped,
        "errors": errors,
        "ingest_results": ingest_results,
    }
