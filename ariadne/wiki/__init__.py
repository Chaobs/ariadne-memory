"""
Ariadne Wiki Package — LLM Wiki feature.

Implements Karpathy's LLM Wiki pattern:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Three-layer architecture:
  Raw Sources (immutable) → Wiki (LLM-generated) → Schema (rules & config)

Three core operations:
  - Ingest: Two-step CoT — analyze source → generate wiki pages
  - Query: Search wiki → LLM synthesizes answer with citations
  - Lint: Structural + semantic health checks

Additional:
  - Obsidian vault import
  - index.md / log.md / overview.md management
  - [[wikilink]] cross-reference support
  - YAML frontmatter on every page
"""

from ariadne.wiki.models import (
    WikiProject,
    WikiPage,
    WikiFrontmatter,
    WikiPageType,
    LintResult,
    LintIssueType,
    LintSeverity,
    IngestResult,
    QueryResult,
)

from ariadne.wiki.builder import (
    init_wiki_project,
    read_wiki_page,
    write_wiki_page,
    list_wiki_pages,
    read_file_safe,
    write_file_safe,
    parse_file_blocks,
    parse_review_blocks,
    extract_wikilinks,
    append_log_entry,
    check_ingest_cache,
    save_ingest_cache,
)

from ariadne.wiki.ingestor import (
    ingest_source,
    batch_ingest,
)

from ariadne.wiki.linter import (
    run_structural_lint,
    run_semantic_lint,
    run_full_lint,
)

from ariadne.wiki.query import (
    query_wiki,
)

from ariadne.wiki.obsidian import (
    ObsidianIngestor,
    import_obsidian_vault,
    convert_obsidian_to_markdown,
    parse_obsidian_frontmatter,
)

__all__ = [
    # Models
    "WikiProject",
    "WikiPage",
    "WikiFrontmatter",
    "WikiPageType",
    "LintResult",
    "LintIssueType",
    "LintSeverity",
    "IngestResult",
    "QueryResult",
    # Builder
    "init_wiki_project",
    "read_wiki_page",
    "write_wiki_page",
    "list_wiki_pages",
    "read_file_safe",
    "write_file_safe",
    "parse_file_blocks",
    "parse_review_blocks",
    "extract_wikilinks",
    "append_log_entry",
    # Ingest
    "ingest_source",
    "batch_ingest",
    # Lint
    "run_structural_lint",
    "run_semantic_lint",
    "run_full_lint",
    # Query
    "query_wiki",
    # Obsidian
    "ObsidianIngestor",
    "import_obsidian_vault",
    "convert_obsidian_to_markdown",
    "parse_obsidian_frontmatter",
]
