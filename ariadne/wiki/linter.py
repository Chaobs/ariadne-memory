"""
Ariadne Wiki Linter — Structural and semantic lint for wiki health.

Implements Karpathy's Lint operation:
- Structural: orphan pages, broken links, no-outlink pages
- Semantic: contradictions, stale claims, missing pages, suggestions
"""

import os
import re
from typing import List, Optional, Dict, Any

from ariadne.wiki.models import (
    WikiProject, WikiPage, LintResult, LintIssueType, LintSeverity,
)
from ariadne.wiki.builder import (
    read_file_safe, read_wiki_page, list_wiki_pages, get_wiki_page_slugs,
    extract_wikilinks, LINT_BLOCK_PATTERN,
)
from ariadne.wiki.prompts import build_semantic_lint_prompt


def run_structural_lint(project: WikiProject) -> List[LintResult]:
    """
    Run structural lint checks on the wiki.

    Checks:
    - Orphan pages (no inbound links)
    - Broken wikilinks (target page not found)
    - Pages with no outbound links
    """
    wiki_dir = project.wiki_dir
    if not os.path.exists(wiki_dir):
        return []

    # Get all wiki pages
    page_paths = list_wiki_pages(wiki_dir)
    slug_map = get_wiki_page_slugs(wiki_dir)

    # Read all pages and extract data
    pages_data: List[Dict[str, Any]] = []
    for path in page_paths:
        page = read_wiki_page(path)
        if page is None:
            continue

        rel_path = os.path.relpath(path, wiki_dir).replace("\\", "/")
        slug = rel_path.replace(".md", "")
        outlinks = extract_wikilinks(page.content)

        # Skip index.md and log.md from orphan checks
        basename = os.path.basename(path)
        if basename in ("index.md", "log.md"):
            continue

        pages_data.append({
            "path": path,
            "rel_path": rel_path,
            "slug": slug,
            "content": page.content,
            "outlinks": outlinks,
        })

    # Build inbound link counts (case-insensitive)
    inbound_counts: Dict[str, int] = {}
    for p in pages_data:
        for link in p["outlinks"]:
            lookup = link.lower()
            target = slug_map.get(lookup)
            if target:
                target_rel = os.path.relpath(target, wiki_dir).replace("\\", "/").replace(".md", "").lower()
                inbound_counts[target_rel] = inbound_counts.get(target_rel, 0) + 1
            else:
                inbound_counts[lookup] = inbound_counts.get(lookup, 0) + 1

    results: List[LintResult] = []

    for p in pages_data:
        # Orphan check
        inbound = inbound_counts.get(p["slug"].lower(), 0)
        if inbound == 0:
            results.append(LintResult(
                issue_type=LintIssueType.ORPHAN,
                severity=LintSeverity.INFO,
                page=p["rel_path"],
                detail="No other pages link to this page.",
            ))

        # No outbound links
        if not p["outlinks"]:
            results.append(LintResult(
                issue_type=LintIssueType.NO_OUTLINKS,
                severity=LintSeverity.INFO,
                page=p["rel_path"],
                detail="This page has no [[wikilink]] references to other pages.",
            ))

        # Broken links
        for link in p["outlinks"]:
            lookup = link.lower()
            basename_lookup = os.path.basename(link).replace(".md", "").lower()
            exists = lookup in slug_map or basename_lookup in slug_map
            if not exists:
                results.append(LintResult(
                    issue_type=LintIssueType.BROKEN_LINK,
                    severity=LintSeverity.WARNING,
                    page=p["rel_path"],
                    detail=f"Broken link: [[{link}]] — target page not found.",
                ))

    return results


def run_semantic_lint(
    project: WikiProject,
    llm_config: Optional[Dict[str, Any]] = None,
    language: str = "",
) -> List[LintResult]:
    """
    Run semantic lint using LLM analysis.

    The LLM reviews wiki page summaries and identifies:
    - Contradictions between pages
    - Stale or outdated information
    - Missing pages for important concepts
    - Suggestions for improvement
    """
    wiki_dir = project.wiki_dir
    if not os.path.exists(wiki_dir):
        return []

    # Get all wiki pages
    page_paths = list_wiki_pages(wiki_dir)
    if not page_paths:
        return []

    # Build compact summaries (frontmatter + first 500 chars)
    summaries = []
    for path in page_paths:
        basename = os.path.basename(path)
        if basename == "log.md":
            continue
        content = read_file_safe(path)
        if not content:
            continue
        rel_path = os.path.relpath(path, wiki_dir).replace("\\", "/")
        preview = content[:500] + ("..." if len(content) > 500 else "")
        summaries.append(f"### {rel_path}\n{preview}")

    if not summaries:
        return []

    # Get LLM
    try:
        from ariadne.wiki.ingestor import _get_llm
        llm = _get_llm(llm_config)
    except Exception:
        return []

    if llm is None:
        return []

    # Build prompt
    prompt = build_semantic_lint_prompt(
        page_summaries="\n\n".join(summaries),
        language=language,
    )

    # Call LLM
    try:
        response = llm.chat(prompt=prompt, temperature=0.1)
        raw = response.content
    except Exception as e:
        return []

    # Parse LINT blocks
    results: List[LintResult] = []
    for match in LINT_BLOCK_PATTERN.finditer(raw):
        raw_type = match.group(1).strip().lower()
        severity = match.group(2).strip().lower()
        title = match.group(3).strip()
        body = match.group(4).strip()

        # Parse PAGES
        pages_match = re.search(r'^PAGES:\s*(.+)$', body, re.MULTILINE)
        affected_pages = [p.strip() for p in pages_match.group(1).split(",")] if pages_match else []

        detail = re.sub(r'^PAGES:.*$', '', body, flags=re.MULTILINE).strip()

        # Map type to our enum
        type_map = {
            "contradiction": LintIssueType.CONTRADICTION,
            "stale": LintIssueType.STALE,
            "missing-page": LintIssueType.MISSING_PAGE,
            "suggestion": LintIssueType.SUGGESTION,
        }
        issue_type = type_map.get(raw_type, LintIssueType.SUGGESTION)

        results.append(LintResult(
            issue_type=issue_type,
            severity=LintSeverity.WARNING if severity == "warning" else LintSeverity.INFO,
            page=title,
            detail=f"[{raw_type}] {detail}",
            affected_pages=affected_pages,
        ))

    return results


def run_full_lint(
    project: WikiProject,
    llm_config: Optional[Dict[str, Any]] = None,
    language: str = "",
    include_semantic: bool = True,
) -> List[LintResult]:
    """Run both structural and semantic lint checks."""
    results = run_structural_lint(project)

    if include_semantic:
        semantic_results = run_semantic_lint(project, llm_config, language)
        results.extend(semantic_results)

    # Append log entry
    from ariadne.wiki.builder import append_log_entry
    append_log_entry(
        project, "lint", "Full lint check",
        f"Found {len(results)} issue(s)"
    )

    return results
