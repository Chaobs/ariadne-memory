"""
Unit tests for Ariadne Wiki models.

Run with: python -m pytest tests/test_wiki_models.py -v
"""

import pytest
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


class TestWikiFrontmatter:
    """Test WikiFrontmatter YAML serialization and parsing."""

    def test_default_frontmatter(self):
        """Default frontmatter has sensible defaults."""
        fm = WikiFrontmatter()
        assert fm.page_type == WikiPageType.CONCEPT
        assert fm.title == ""
        assert fm.tags == []
        assert fm.related == []
        assert fm.sources == []

    def test_frontmatter_with_data(self):
        """Frontmatter accepts custom data."""
        fm = WikiFrontmatter(
            page_type=WikiPageType.ENTITY,
            title="Test Entity",
            tags=["tag1", "tag2"],
            related=["related-page-1", "related-page-2"],
            sources=["source-file.md"],
        )
        assert fm.page_type == WikiPageType.ENTITY
        assert fm.title == "Test Entity"
        assert fm.tags == ["tag1", "tag2"]

    def test_to_yaml_full(self):
        """to_yaml produces valid YAML with all fields."""
        fm = WikiFrontmatter(
            page_type=WikiPageType.CONCEPT,
            title="My Concept",
            tags=["ai", "memory"],
            related=["concept-a", "entity-b"],
            sources=["docs/intro.md"],
        )
        yaml_str = fm.to_yaml()
        assert yaml_str.startswith("---\n")
        assert yaml_str.endswith("\n---")
        assert 'type: concept' in yaml_str
        assert 'title: "My Concept"' in yaml_str
        assert "tags:" in yaml_str
        assert "related:" in yaml_str

    def test_to_yaml_minimal(self):
        """to_yaml works with only required fields."""
        fm = WikiFrontmatter(page_type=WikiPageType.SOURCE, title="")
        yaml_str = fm.to_yaml()
        assert "---\n" in yaml_str
        assert "type: source" in yaml_str

    def test_from_yaml_full(self):
        """from_yaml correctly parses a full frontmatter block."""
        yaml_text = """---
type: entity
title: "Parsed Entity"
created: 2025-01-01
updated: 2025-06-15
tags: [tag1, tag2, tag3]
related: [page-a, page-b]
sources: [src.md]
---"""
        fm = WikiFrontmatter.from_yaml(yaml_text)
        assert fm.page_type == WikiPageType.ENTITY
        assert fm.title == "Parsed Entity"
        assert fm.created == "2025-01-01"
        assert fm.updated == "2025-06-15"
        assert "tag1" in fm.tags
        assert "tag2" in fm.tags
        assert "page-a" in fm.related
        assert "src.md" in fm.sources

    def test_from_yaml_partial(self):
        """from_yaml handles partial/incomplete frontmatter."""
        yaml_text = """---
type: concept
---"""
        fm = WikiFrontmatter.from_yaml(yaml_text)
        assert fm.page_type == WikiPageType.CONCEPT
        assert fm.title == ""
        assert fm.tags == []

    def test_from_yaml_no_frontmatter(self):
        """from_yaml returns default for content without frontmatter."""
        fm = WikiFrontmatter.from_yaml("Just regular content without frontmatter.")
        assert fm.page_type == WikiPageType.CONCEPT
        assert fm.title == ""

    def test_from_yaml_invalid_type(self):
        """from_yaml ignores invalid type values."""
        yaml_text = """---
type: not-a-valid-type
title: "Test"
---"""
        fm = WikiFrontmatter.from_yaml(yaml_text)
        # Should fall back to default CONCEPT
        assert fm.page_type == WikiPageType.CONCEPT
        assert fm.title == "Test"

    def test_roundtrip(self):
        """Frontmatter survives to_yaml -> from_yaml round-trip."""
        original = WikiFrontmatter(
            page_type=WikiPageType.SYNTHESIS,
            title="Round-trip Test",
            tags=["test", "roundtrip"],
            related=["page-one"],
            sources=["doc.md"],
        )
        yaml_str = original.to_yaml()
        restored = WikiFrontmatter.from_yaml(yaml_str)
        assert restored.page_type == original.page_type
        assert restored.title == original.title
        assert restored.tags == original.tags
        assert restored.related == original.related
        assert restored.sources == original.sources


class TestWikiPage:
    """Test WikiPage data model."""

    def test_wiki_page_default(self):
        """WikiPage can be created with minimal data."""
        page = WikiPage(path="entities/test.md")
        assert page.path == "entities/test.md"
        assert page.content == ""
        assert page.frontmatter.page_type == WikiPageType.CONCEPT

    def test_wiki_page_slug(self):
        """slug property extracts filename without extension."""
        page = WikiPage(path="concepts/my-concept.md")
        assert page.slug == "my-concept"

        page2 = WikiPage(path="entities/DeepThoughts.md")
        assert page2.slug == "DeepThoughts"

    def test_wiki_page_full_content(self):
        """full_content combines frontmatter and body."""
        fm = WikiFrontmatter(page_type=WikiPageType.ENTITY, title="Entity Test")
        page = WikiPage(path="entities/test.md", frontmatter=fm, content="# Entity Test\n\nBody content.")
        full = page.full_content
        assert "type: entity" in full
        assert "# Entity Test" in full
        assert "Body content." in full

    def test_wiki_page_wikilinks(self):
        """wikilinks property extracts [[brackets]] from content."""
        page = WikiPage(
            path="test.md",
            content="See [[EntityA]] and [[EntityB|Display B]]. Also [[concept-x]]."
        )
        links = page.wikilinks
        assert "EntityA" in links
        assert "EntityB" in links
        assert "concept-x" in links

    def test_wiki_page_wikilinks_none(self):
        """wikilinks returns empty list when none present."""
        page = WikiPage(path="test.md", content="No links here, just text.")
        assert page.wikilinks == []


class TestWikiProject:
    """Test WikiProject model and its path properties."""

    def test_wiki_project_basic(self):
        """WikiProject initializes with a root_path."""
        proj = WikiProject(root_path="/path/to/my-project")
        assert proj.root_path == "/path/to/my-project"
        assert proj.name == ""

    def test_wiki_project_named(self):
        """WikiProject accepts an optional name."""
        proj = WikiProject(root_path="/path/to/project", name="My Wiki")
        assert proj.name == "My Wiki"

    def test_wiki_project_paths(self):
        """All path properties produce correct absolute paths."""
        import os
        proj = WikiProject(root_path="/home/user/wiki-proj")
        # Use os.sep for cross-platform path separator
        raw_sep = f"raw{os.sep}" if os.sep != "/" else "raw/"
        assert f"{os.sep}raw{os.sep}" in proj.raw_dir or proj.raw_dir.replace("\\", "/") == "/home/user/wiki-proj/raw"
        assert proj.schema_path.replace("\\", "/") == "/home/user/wiki-proj/schema.md"
        assert proj.purpose_path.replace("\\", "/") == "/home/user/wiki-proj/purpose.md"
        assert proj.index_path.replace("\\", "/") == "/home/user/wiki-proj/wiki/index.md"
        assert proj.log_path.replace("\\", "/") == "/home/user/wiki-proj/wiki/log.md"
        assert proj.overview_path.replace("\\", "/") == "/home/user/wiki-proj/wiki/overview.md"
        assert proj.queries_dir.replace("\\", "/") == "/home/user/wiki-proj/wiki/queries"
        assert proj.synthesis_dir.replace("\\", "/") == "/home/user/wiki-proj/wiki/synthesis"
        assert proj.comparisons_dir.replace("\\", "/") == "/home/user/wiki-proj/wiki/comparisons"


class TestLintResult:
    """Test LintResult model."""

    def test_lint_result_basic(self):
        """LintResult captures issue details."""
        result = LintResult(
            issue_type=LintIssueType.ORPHAN,
            severity=LintSeverity.WARNING,
            page="entities/orphan.md",
            detail="This page has no incoming links.",
        )
        assert result.issue_type == LintIssueType.ORPHAN
        assert result.severity == LintSeverity.WARNING
        assert result.page == "entities/orphan.md"
        assert result.detail == "This page has no incoming links."

    def test_lint_result_with_affected_pages(self):
        """LintResult can reference affected pages."""
        result = LintResult(
            issue_type=LintIssueType.BROKEN_LINK,
            severity=LintSeverity.WARNING,
            page="concepts/ai.md",
            detail="Links to missing page",
            affected_pages=["entities/gpt5.md", "concepts/agi.md"],
        )
        assert len(result.affected_pages) == 2


class TestIngestResult:
    """Test IngestResult model."""

    def test_ingest_result_default(self):
        """IngestResult has sensible defaults."""
        result = IngestResult(source_file="/path/to/source.md")
        assert result.source_file == "/path/to/source.md"
        assert result.pages_written == []
        assert result.review_items == []
        assert result.warnings == []
        assert result.cached is False

    def test_ingest_result_with_data(self):
        """IngestResult captures all ingestion data."""
        result = IngestResult(
            source_file="/path/to/source.md",
            pages_written=["wiki/sources/source.md", "wiki/entities/test.md"],
            review_items=[{"line": 10, "detail": "Check this claim."}],
            warnings=["Source file is very large."],
            cached=True,
        )
        assert len(result.pages_written) == 2
        assert result.cached is True
        assert len(result.review_items) == 1


class TestQueryResult:
    """Test QueryResult model."""

    def test_query_result_basic(self):
        """QueryResult captures query and answer."""
        result = QueryResult(
            question="What is Ariadne?",
            answer="Ariadne is a memory system.",
            cited_pages=["entities/ariadne.md", "concepts/memory.md"],
        )
        assert result.question == "What is Ariadne?"
        assert "memory system" in result.answer
        assert len(result.cited_pages) == 2

    def test_query_result_with_save_path(self):
        """QueryResult records saved file path."""
        result = QueryResult(
            question="Explain RAG.",
            answer="RAG is retrieval-augmented generation.",
            cited_pages=["concepts/rag.md"],
            saved_to="wiki/queries/rag-2025-01-01.md",
        )
        assert result.saved_to is not None
        assert "rag" in result.saved_to


class TestEnums:
    """Test enum values are stable and correct."""

    def test_wiki_page_types(self):
        """All WikiPageType values are defined."""
        expected = {
            "source", "entity", "concept", "comparison",
            "query", "synthesis", "index", "log", "overview",
        }
        actual = {t.value for t in WikiPageType}
        assert expected == actual

    def test_lint_issue_types(self):
        """All LintIssueType values are defined."""
        expected = {
            "orphan", "broken-link", "no-outlinks",
            "contradiction", "stale", "missing-page", "suggestion",
        }
        actual = {t.value for t in LintIssueType}
        assert expected == actual

    def test_lint_severities(self):
        """All LintSeverity values are defined."""
        expected = {"warning", "info"}
        actual = {s.value for s in LintSeverity}
        assert expected == actual
