"""
Ariadne Wiki Query — Wiki-based Q&A with page retrieval and answer archiving.

Implements Karpathy's Query operation:
- Search wiki pages for relevant content
- LLM synthesizes an answer with citations
- Optionally save answer back to wiki as a query page
"""

import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from ariadne.wiki.models import WikiProject, QueryResult
from ariadne.wiki.builder import (
    read_file_safe, list_wiki_pages, write_file_safe,
    extract_wikilinks, append_log_entry,
)
from ariadne.wiki.prompts import build_query_prompt


def _search_wiki_pages(
    wiki_dir: str,
    query: str,
    max_pages: int = 10,
) -> List[Dict[str, str]]:
    """
    Simple tokenized search over wiki pages.
    Returns list of {path, rel_path, content, score} sorted by relevance.
    """
    keywords = [w.lower() for w in re.split(r'\W+', query) if len(w) > 1]
    if not keywords:
        return []

    results: List[Dict[str, Any]] = []

    for path in list_wiki_pages(wiki_dir):
        basename = os.path.basename(path)
        if basename in ("log.md",):
            continue

        content = read_file_safe(path)
        if not content:
            continue

        content_lower = content.lower()
        rel_path = os.path.relpath(path, wiki_dir).replace("\\", "/")

        score = 0
        for kw in keywords:
            # Title match bonus
            if kw in os.path.splitext(basename)[0].lower():
                score += 10
            score += content_lower.count(kw)

        if score > 0:
            results.append({
                "path": path,
                "rel_path": rel_path,
                "content": content,
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_pages]


def query_wiki(
    project: WikiProject,
    question: str,
    llm_config: Optional[Dict[str, Any]] = None,
    language: str = "",
    save_to_wiki: bool = False,
    max_context_pages: int = 8,
) -> QueryResult:
    """
    Answer a question using the wiki as knowledge base.

    Args:
        project: WikiProject instance
        question: The question to answer
        llm_config: Optional LLM configuration
        language: Output language
        save_to_wiki: Whether to save the answer back to wiki/queries/
        max_context_pages: Maximum number of wiki pages to include in context

    Returns:
        QueryResult with answer and cited pages
    """
    result = QueryResult(question=question, answer="")

    # Get LLM
    try:
        from ariadne.wiki.ingestor import _get_llm
        llm = _get_llm(llm_config)
    except Exception:
        llm = None

    if llm is None:
        result.answer = "No LLM configured. Please configure an LLM provider first."
        return result

    # Search wiki pages
    wiki_dir = project.wiki_dir
    relevant_pages = _search_wiki_pages(wiki_dir, question, max_pages=max_context_pages)

    # Read purpose and index for context
    purpose = read_file_safe(project.purpose_path)
    index = read_file_safe(project.index_path)

    # Build system prompt
    system_prompt = build_query_prompt(
        purpose=purpose,
        index=index,
        language=language,
    )

    # Build user message with context pages
    context_parts = []
    cited_paths = []

    for i, page in enumerate(relevant_pages, 1):
        context_parts.append(f"## [{i}] {page['rel_path']}\n\n{page['content'][:2000]}")
        cited_paths.append(page["rel_path"])

    context_str = "\n\n---\n\n".join(context_parts) if context_parts else "(No relevant wiki pages found)"

    user_msg = f"{question}\n\n---\n\n## Wiki Context\n\n{context_str}"

    # Get answer
    try:
        response = llm.chat(
            prompt=user_msg,
            system=system_prompt,
            temperature=0.3,
        )
        answer = response.content
    except Exception as e:
        result.answer = f"LLM query failed: {e}"
        return result

    result.answer = answer
    result.cited_pages = cited_paths

    # Optionally save to wiki
    if save_to_wiki:
        saved_path = _save_query_to_wiki(project, question, answer, cited_paths)
        result.saved_to = saved_path

    # Append log entry
    append_log_entry(
        project, "query", question[:60],
        f"Cited {len(cited_paths)} page(s)"
    )

    return result


def _save_query_to_wiki(
    project: WikiProject,
    question: str,
    answer: str,
    cited_pages: List[str],
) -> str:
    """Save a query answer as a wiki page in wiki/queries/."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug_base = re.sub(r'\W+', '-', question[:40].lower()).strip('-')
    slug = f"{slug_base}-{date_str}"
    relative_path = f"wiki/queries/{slug}.md"
    full_path = os.path.join(project.root_path, relative_path)

    # Build related links
    related_links = [f"[[{p.replace('.md', '')}]]" for p in cited_pages[:5]]

    content = "\n".join([
        "---",
        "type: query",
        f'title: "{question[:80]}"',
        f"created: {date_str}",
        f"updated: {date_str}",
        "tags: []",
        f"related: {cited_pages[:5]}",
        "sources: []",
        "---",
        "",
        f"# {question}",
        "",
        answer,
        "",
        "---",
        "",
        "## References",
        "",
        "\n".join(f"- {link}" for link in related_links) if related_links else "*(No references)*",
        "",
    ])

    write_file_safe(full_path, content)
    return relative_path
