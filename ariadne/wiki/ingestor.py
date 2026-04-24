"""
Ariadne Wiki Ingestor — Two-step Chain-of-Thought ingestion.

Implements Karpathy's LLM Wiki ingest pattern:
  Step 1 (Analysis): LLM reads source → structured analysis
  Step 2 (Generation): LLM takes analysis → generates wiki files

Uses Ariadne's existing LLM infrastructure (ariadne.llm).
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from ariadne.wiki.models import WikiProject, IngestResult
from ariadne.wiki.builder import (
    read_file_safe, write_file_safe, write_file_blocks,
    parse_review_blocks, check_ingest_cache, save_ingest_cache,
    append_log_entry,
)
from ariadne.wiki.prompts import build_analysis_prompt, build_generation_prompt


def _get_llm(config: Optional[Dict[str, Any]] = None):
    """Get LLM instance from config or Ariadne's config manager."""
    from ariadne.llm.factory import LLMFactory

    if config:
        from ariadne.llm.base import LLMConfig, LLMProvider
        provider = LLMProvider(config.get("provider", "deepseek"))
        llm_config = LLMConfig(
            provider=provider,
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            max_tokens=config.get("max_tokens", 4096),
            temperature=config.get("temperature", 0.1),
            timeout=config.get("timeout", 300),  # 5 min for ingest
        )
        return LLMFactory.create(llm_config)

    # Try loading from project-root config.json (via centralized paths module)
    from ariadne.paths import CONFIG_FILE
    project_config = str(CONFIG_FILE)
    if os.path.exists(project_config):
        try:
            llm = LLMFactory.from_json_file(project_config)
            if llm:
                return llm
        except Exception:
            pass

    # Try using environment variables (DEEPSEEK_API_KEY, etc.)
    llm = LLMFactory.from_env("DEEPSEEK")
    if llm:
        return llm

    return None


def ingest_source(
    project: WikiProject,
    source_path: str,
    llm_config: Optional[Dict[str, Any]] = None,
    language: str = "",
    folder_context: str = "",
    skip_cache: bool = False,
) -> IngestResult:
    """
    Two-step Chain-of-Thought ingest of a source document into the wiki.

    Step 1: LLM reads source, produces structured analysis
    Step 2: LLM takes analysis, generates wiki files

    Args:
        project: WikiProject instance
        source_path: Path to the source file
        llm_config: Optional LLM configuration dict
        language: Output language (empty = auto-detect)
        folder_context: Folder path for classification hints
        skip_cache: Skip cache check even if source is unchanged

    Returns:
        IngestResult with pages written and review items
    """
    result = IngestResult(source_file=source_path)

    # Get LLM
    llm = _get_llm(llm_config)
    if llm is None:
        result.warnings.append("No LLM configured. Please configure an LLM provider first.")
        return result

    # Read source content
    source_content = read_file_safe(source_path)
    if not source_content:
        result.warnings.append(f"Could not read source file: {source_path}")
        return result

    # Truncate very long sources
    max_chars = 50000
    truncated = False
    if len(source_content) > max_chars:
        source_content = source_content[:max_chars] + "\n\n[...truncated...]"
        truncated = True

    source_file_name = os.path.basename(source_path)

    # Check cache
    if not skip_cache:
        cached = check_ingest_cache(project, source_file_name, source_content)
        if cached is not None:
            result.pages_written = cached
            result.cached = True
            return result

    # Read existing wiki context
    purpose = read_file_safe(project.purpose_path)
    schema = read_file_safe(project.schema_path)
    index = read_file_safe(project.index_path)
    overview = read_file_safe(project.overview_path)

    # ── Step 1: Analysis ─────────────────────────────────────────────
    analysis_prompt = build_analysis_prompt(
        purpose=purpose,
        index=index,
        language=language,
    )

    folder_hint = f"\n**Folder context:** {folder_context}" if folder_context else ""
    user_msg = (
        f"Analyze this source document:\n\n"
        f"**File:** {source_file_name}{folder_hint}\n\n"
        f"---\n\n{source_content}"
    )

    try:
        analysis_response = llm.chat(
            prompt=user_msg,
            system=analysis_prompt,
            temperature=0.1,
        )
        analysis = analysis_response.content
    except Exception as e:
        result.warnings.append(f"Analysis step failed: {e}")
        return result

    # ── Step 2: Generation ───────────────────────────────────────────
    generation_prompt = build_generation_prompt(
        source_file_name=source_file_name,
        schema=schema,
        purpose=purpose,
        index=index,
        overview=overview,
        language=language,
    )

    user_msg_2 = "\n".join([
        f"Source document to process: **{source_file_name}**",
        "",
        "The Stage 1 analysis below is CONTEXT to inform your output. Do NOT echo",
        "its tables, bullet points, or prose. Your output must be FILE/REVIEW",
        "blocks as specified in the system prompt — nothing else.",
        "",
        "## Stage 1 Analysis (context only — do not repeat)",
        "",
        analysis,
        "",
        "## Original Source Content",
        "",
        source_content,
        "",
        "---",
        "",
        f"Now emit the FILE blocks for the wiki files derived from **{source_file_name}**.",
        "Your response MUST begin with `---FILE:` as the very first characters.",
        "No preamble. No analysis prose. Start immediately.",
    ])

    try:
        generation_response = llm.chat(
            prompt=user_msg_2,
            system=generation_prompt,
            temperature=0.1,
            max_tokens=8192,
        )
        generation = generation_response.content
    except Exception as e:
        result.warnings.append(f"Generation step failed: {e}")
        return result

    # ── Step 3: Write files ──────────────────────────────────────────
    written, write_warnings = write_file_blocks(project, generation)
    result.pages_written = written
    result.warnings.extend(write_warnings)

    # Ensure source summary page exists
    source_base_name = os.path.splitext(source_file_name)[0]
    source_summary_path = f"wiki/sources/{source_base_name}.md"
    has_source_summary = any(p.startswith("wiki/sources/") for p in written)

    if not has_source_summary:
        date_str = datetime.now().strftime("%Y-%m-%d")
        fallback = "\n".join([
            "---",
            "type: source",
            f'title: "Source: {source_file_name}"',
            f"created: {date_str}",
            f"updated: {date_str}",
            f'sources: ["{source_file_name}"]',
            "tags: []",
            "related: []",
            "---",
            "",
            f"# Source: {source_file_name}",
            "",
            analysis[:3000] if analysis else "(Analysis not available)",
            "",
        ])
        write_file_safe(os.path.join(project.root_path, source_summary_path), fallback)
        if source_summary_path not in written:
            written.append(source_summary_path)

    # ── Step 4: Parse review items ───────────────────────────────────
    review_items = parse_review_blocks(generation, source_path)
    result.review_items = review_items

    # ── Step 5: Update cache ─────────────────────────────────────────
    if written:
        save_ingest_cache(project, source_file_name, source_content, written)

    # ── Step 6: Append log entry ─────────────────────────────────────
    append_log_entry(
        project, "ingest", source_file_name,
        f"Generated {len(written)} wiki page(s)"
    )

    return result


def batch_ingest(
    project: WikiProject,
    source_paths: List[str],
    llm_config: Optional[Dict[str, Any]] = None,
    language: str = "",
) -> List[IngestResult]:
    """
    Batch ingest multiple source files.
    Processes one at a time to maintain wiki consistency.
    """
    results = []
    for path in source_paths:
        result = ingest_source(
            project=project,
            source_path=path,
            llm_config=llm_config,
            language=language,
        )
        results.append(result)
    return results
