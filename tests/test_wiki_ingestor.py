"""
Unit tests for Ariadne Wiki ingestor (ingest_source, batch_ingest).

These tests mock the LLM layer so they run without API keys or network access.

Run with: python -m pytest tests/test_wiki_ingestor.py -v
"""

import os
import pathlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ariadne.wiki.ingestor import ingest_source, batch_ingest
from ariadne.wiki.builder import read_wiki_page, list_wiki_pages


class TestIngestSource:
    """Test ingest_source with mocked LLM."""

    def test_ingest_no_llm_warns(self, wiki_project_fs, sample_source_md):
        """ingest_source returns warnings when no LLM is configured."""
        with patch("ariadne.wiki.ingestor._get_llm", return_value=None):
            result = ingest_source(
                project=wiki_project_fs,
                source_path=sample_source_md,
            )
        assert len(result.warnings) >= 1
        assert any("LLM" in w or "llm" in w for w in result.warnings)
        assert result.pages_written == []

    def test_ingest_reads_source_file(self, wiki_project_fs, sample_source_md, mock_llm):
        """ingest_source reads the source file content."""
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        # Should attempt LLM call (even if returns empty)
        mock_llm.chat.assert_called()
        # Should not warn about read failure
        assert not any("read" in w.lower() for w in result.warnings)

    def test_ingest_generates_pages_from_llm_output(self, wiki_project_fs, sample_source_md, mock_llm_response):
        """ingest_source writes wiki pages from LLM FILE blocks."""
        mock_llm_response.chat.return_value.content = """\
Here is the analysis of the source document.

---FILE: wiki/entities/test-article.md ---
---
type: entity
title: "Test Article Entity"
created: 2025-01-01
updated: 2025-01-01
tags: [test, article]
related: []
sources: []
---

# Test Article Entity

This entity was generated from the test article.

## Properties

- Property 1
- Property 2
---END FILE---

---FILE: wiki/sources/test-article.md ---
---
type: source
title: "Source: test-article.md"
created: 2025-01-01
updated: 2025-01-01
tags: []
related: []
sources: [test-article.md]
---

# Source: test-article.md

This is the summary of the source.
---END FILE---"""
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        assert len(result.pages_written) >= 1
        # Verify page was written to disk
        wiki_path = os.path.join(wiki_project_fs.root_path, "wiki", "entities", "test-article.md")
        assert os.path.exists(wiki_path)
        page = read_wiki_page(wiki_path)
        assert page is not None
        assert "Test Article Entity" in page.frontmatter.title

    def test_ingest_parses_review_blocks(self, wiki_project_fs, sample_source_md, mock_llm_response):
        """ingest_source extracts review items from LLM output."""
        mock_llm_response.chat.return_value.content = """\
---REVIEW: suggestion | Consider adding related links ---
PAGES: entities/related.md
---END REVIEW---

---FILE: wiki/sources/test.md ---
---
type: source
---
Content.
---END FILE---"""
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        assert len(result.review_items) >= 1
        assert any(item["type"] == "suggestion" for item in result.review_items)

    def test_ingest_truncates_long_sources(self, wiki_project_fs, sample_source_md, mock_llm_response):
        """ingest_source truncates very long source content."""
        # Write a very long source file
        long_content = "x" * 60000
        pathlib.Path(sample_source_md).write_text(long_content, encoding="utf-8")

        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test.md ---
---
type: source
---
Content.
---END FILE---"""
        # Re-read to get updated content
        from ariadne.wiki.builder import read_file_safe
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        # Should complete without error
        assert result.source_file == sample_source_md


class TestIngestCaching:
    """Test ingest caching behavior."""

    def test_ingest_uses_cache_when_source_unchanged(
        self, wiki_project_fs, sample_source_md, mock_llm_response
    ):
        """ingest_source returns cached result when source content is unchanged."""
        from ariadne.wiki.builder import save_ingest_cache, read_file_safe

        # First ingest: populate cache
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test-article.md ---
---
type: source
---
Content.
---END FILE---"""
        result1 = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        assert len(result1.pages_written) >= 1

        # Second ingest: same source → should use cache
        # Reset mock so we can verify it was NOT called
        mock_llm_response.chat.reset_mock()
        result2 = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        assert result2.cached is True
        # LLM should not be called for cached content
        mock_llm_response.chat.assert_not_called()

    def test_ingest_skips_cache_when_requested(self, wiki_project_fs, sample_source_md, mock_llm_response):
        """ingest_source bypasses cache when skip_cache=True."""
        # First ingest: populate cache
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test.md ---
---
type: source
---
Content.
---END FILE---"""
        ingest_source(project=wiki_project_fs, source_path=sample_source_md)

        # Second ingest with skip_cache=True: should call LLM again
        mock_llm_response.chat.reset_mock()
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test2.md ---
---
type: source
---
Content.
---END FILE---"""
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
            skip_cache=True,
        )
        assert result.cached is False
        mock_llm_response.chat.assert_called()

    def test_ingest_cache_detects_modified_source(
        self, wiki_project_fs, sample_source_md, mock_llm_response
    ):
        """Changing source file invalidates cache."""
        # First ingest
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test.md ---
---
type: source
---
Content v1.
---END FILE---"""
        ingest_source(project=wiki_project_fs, source_path=sample_source_md)

        # Modify source
        pathlib.Path(sample_source_md).write_text(
            "# Modified Source\n\nModified content v2.\n",
            encoding="utf-8",
        )

        # Re-ingest: cache should be invalidated
        mock_llm_response.chat.reset_mock()
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/test.md ---
---
type: source
---
Content v2.
---END FILE---"""
        result = ingest_source(
            project=wiki_project_fs,
            source_path=sample_source_md,
        )
        assert result.cached is False
        mock_llm_response.chat.assert_called()


class TestBatchIngest:
    """Test batch_ingest."""

    def test_batch_ingest_processes_all_files(
        self, wiki_project_fs, sample_source_md, sample_source_txt, mock_llm_response
    ):
        """batch_ingest calls ingest_source for each file in the list."""
        mock_llm_response.chat.return_value.content = """\
---FILE: wiki/sources/source.md ---
---
type: source
---
Content.
---END FILE---"""
        results = batch_ingest(
            project=wiki_project_fs,
            source_paths=[sample_source_md, sample_source_txt],
        )
        assert len(results) == 2
        assert all(isinstance(r, type(results[0])) for r in results)

    def test_batch_ingest_empty_list(self, wiki_project_fs):
        """batch_ingest handles empty source list."""
        results = batch_ingest(
            project=wiki_project_fs,
            source_paths=[],
        )
        assert results == []
