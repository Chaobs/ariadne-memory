"""
Unit tests for Ariadne Wiki linter.

Tests structural lint (no LLM needed) and semantic lint (with LLM mock).

Run with: python -m pytest tests/test_wiki_linter.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from ariadne.wiki.linter import (
    run_structural_lint,
    run_semantic_lint,
    run_full_lint,
)
from ariadne.wiki.models import LintIssueType, LintSeverity, WikiProject


class TestStructuralLint:
    """Test run_structural_lint — no LLM dependency."""

    def test_empty_wiki_returns_empty_list(self, wiki_project_fs):
        """Structural lint on empty wiki returns no issues."""
        results = run_structural_lint(wiki_project_fs)
        assert results == []

    def test_detects_orphan_pages(self, wiki_project_fs):
        """Structural lint detects pages with no inbound links."""
        # Create an orphan page (no wikilinks pointing to it)
        orphan_dir = Path(wiki_project_fs.concepts_dir)
        orphan_dir.mkdir(exist_ok=True)
        (orphan_dir / "orphan.md").write_text(
            "---\ntype: concept\n---\n# Orphan\nNo links to this page.\n",
            encoding="utf-8",
        )
        results = run_structural_lint(wiki_project_fs)
        orphan_issues = [r for r in results if r.issue_type == LintIssueType.ORPHAN]
        assert len(orphan_issues) >= 1
        assert any("orphan" in r.page.lower() for r in orphan_issues)

    def test_detects_broken_links(self, wiki_project_fs):
        """Structural lint detects [[links]] to non-existent pages."""
        # Create a page with a broken wikilink
        concepts_dir = Path(wiki_project_fs.concepts_dir)
        concepts_dir.mkdir(exist_ok=True)
        (concepts_dir / "broken-link-page.md").write_text(
            "---\ntype: concept\n---\n# Broken\nSee [[entities/nonexistent-page]].\n",
            encoding="utf-8",
        )
        results = run_structural_lint(wiki_project_fs)
        broken_issues = [r for r in results if r.issue_type == LintIssueType.BROKEN_LINK]
        assert len(broken_issues) >= 1
        assert any("nonexistent" in r.detail.lower() for r in broken_issues)

    def test_detects_pages_with_no_outlinks(self, wiki_project_fs):
        """Structural lint flags pages with no [[wikilinks]]."""
        concepts_dir = Path(wiki_project_fs.concepts_dir)
        concepts_dir.mkdir(exist_ok=True)
        (concepts_dir / "no-links.md").write_text(
            "---\ntype: concept\n---\n# No Links\nJust plain text with no wikilinks.\n",
            encoding="utf-8",
        )
        results = run_structural_lint(wiki_project_fs)
        no_outlinks = [r for r in results if r.issue_type == LintIssueType.NO_OUTLINKS]
        assert len(no_outlinks) >= 1

    def test_connected_pages_not_orphan(self, wiki_project_fs):
        """Pages with incoming links are not flagged as orphans."""
        entities_dir = Path(wiki_project_fs.entities_dir)
        concepts_dir = Path(wiki_project_fs.concepts_dir)
        entities_dir.mkdir(exist_ok=True)
        concepts_dir.mkdir(exist_ok=True)
        # Agent entity links to Memory concept
        (entities_dir / "agent.md").write_text(
            "---\ntype: entity\n---\n# Agent\nRelated: [[concepts/memory]].\n",
            encoding="utf-8",
        )
        # Memory concept is linked from agent → should NOT be orphan
        (concepts_dir / "memory.md").write_text(
            "---\ntype: concept\n---\n# Memory\nUsed by [[entities/agent]].\n",
            encoding="utf-8",
        )
        results = run_structural_lint(wiki_project_fs)
        orphan_pages = {r.page for r in results if r.issue_type == LintIssueType.ORPHAN}
        assert not any("memory" in r for r in orphan_pages)

    def test_index_and_log_skipped_from_orphan_check(self, wiki_project_fs):
        """index.md and log.md are excluded from orphan detection."""
        results = run_structural_lint(wiki_project_fs)
        orphan_pages = [r.page for r in results if r.issue_type == LintIssueType.ORPHAN]
        assert not any("index.md" in p for p in orphan_pages)
        assert not any("log.md" in p for p in orphan_pages)

    def test_lint_result_fields(self, wiki_project_fs):
        """LintResult instances have correct fields."""
        concepts_dir = Path(wiki_project_fs.concepts_dir)
        concepts_dir.mkdir(exist_ok=True)
        (concepts_dir / "broken.md").write_text(
            "---\ntype: concept\n---\n# Broken\nSee [[entities/nonexistent]].\n",
            encoding="utf-8",
        )
        results = run_structural_lint(wiki_project_fs)
        assert len(results) > 0
        for r in results:
            assert r.issue_type in list(LintIssueType)
            assert r.severity in list(LintSeverity)
            assert r.page
            assert r.detail


class TestSemanticLint:
    """Test run_semantic_lint with mocked LLM."""

    def test_semantic_lint_no_llm_returns_empty(self, wiki_project_fs):
        """Semantic lint returns empty list when no LLM is available."""
        with patch("ariadne.wiki.ingestor._get_llm", return_value=None):
            results = run_semantic_lint(wiki_project_fs)
        assert results == []

    def test_semantic_lint_parses_llm_response(self, wiki_project_fs):
        """Semantic lint parses LINT blocks from LLM response."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value.content = (
            "---LINT: contradiction | warning | Inconsistent definitions ---\n"
            "PAGES: entities/agent.md, concepts/reasoning.md\n"
            "The term 'agent' is defined inconsistently.\n"
            "---END LINT---\n\n"
            "---LINT: suggestion | info | Add overview page ---\n"
            "PAGES:\n"
            "Consider creating a top-level overview page.\n"
            "---END LINT---"
        )
        with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm):
            results = run_semantic_lint(wiki_project_fs)
        assert len(results) >= 2

        contradiction = next(
            (r for r in results if r.issue_type == LintIssueType.CONTRADICTION), None
        )
        assert contradiction is not None
        assert "warning" in contradiction.severity.value
        assert len(contradiction.affected_pages) == 2

    def test_semantic_lint_catches_llm_exception(self, wiki_project_fs):
        """Semantic lint gracefully handles LLM exceptions."""
        with patch("ariadne.wiki.ingestor._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.chat.side_effect = Exception("LLM network error")
            mock_get_llm.return_value = mock_llm

            results = run_semantic_lint(wiki_project_fs)
            assert results == []

    def test_semantic_lint_handles_empty_wiki(self, wiki_project_fs):
        """Semantic lint handles wiki with only index.md gracefully."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value.content = ""
        with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm):
            results = run_semantic_lint(wiki_project_fs)
        assert isinstance(results, list)


class TestFullLint:
    """Test run_full_lint combining structural + semantic."""

    def test_full_lint_combines_results(self, wiki_project_fs):
        """run_full_lint includes both structural and semantic results."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value.content = (
            "---LINT: suggestion | info | LLM suggestion ---\n"
            "Consider adding more cross-links.\n"
            "---END LINT---"
        )
        with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm):
            results = run_full_lint(wiki_project_fs, include_semantic=True)
        assert len(results) >= 1
        issue_types = {r.issue_type for r in results}
        assert len(issue_types) >= 1

    def test_full_lint_skips_semantic_when_disabled(self, wiki_project_fs):
        """run_full_lint(include_semantic=False) skips semantic lint."""
        concepts_dir = Path(wiki_project_fs.concepts_dir)
        concepts_dir.mkdir(exist_ok=True)
        (concepts_dir / "broken.md").write_text(
            "---\ntype: concept\n---\n# Broken\nSee [[entities/nonexistent]].\n",
            encoding="utf-8",
        )

        with patch("ariadne.wiki.ingestor._get_llm", return_value=None):
            results = run_full_lint(wiki_project_fs, include_semantic=False)

        broken_links = [r for r in results if r.issue_type == LintIssueType.BROKEN_LINK]
        assert len(broken_links) >= 1

    def test_full_lint_appends_log_entry(self, wiki_project_fs):
        """run_full_lint appends an entry to log.md."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value.content = ""
        with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm):
            from ariadne.wiki.builder import read_file_safe
            initial_log = read_file_safe(wiki_project_fs.log_path)

            results = run_full_lint(wiki_project_fs, include_semantic=True)

            after_log = read_file_safe(wiki_project_fs.log_path)
            assert "lint" in after_log.lower()
