"""
Unit tests for Ariadne Wiki builder functions.

Run with: python -m pytest tests/test_wiki_builder.py -v
"""

import os
import json
import pytest
from pathlib import Path

from ariadne.wiki.builder import (
    init_wiki_project,
    read_file_safe,
    write_file_safe,
    read_wiki_page,
    write_wiki_page,
    write_file_blocks,
    list_wiki_pages,
    get_wiki_page_slugs,
    parse_file_blocks,
    parse_review_blocks,
    extract_wikilinks,
    compute_content_hash,
    check_ingest_cache,
    save_ingest_cache,
    append_log_entry,
)


class TestInitWikiProject:
    """Test wiki project initialization."""

    def test_init_creates_directories(self, wiki_project):
        """init_wiki_project creates the full directory structure."""
        proj = init_wiki_project(str(wiki_project.root_path), name="Test Project")
        assert os.path.isdir(proj.raw_dir)
        assert os.path.isdir(proj.sources_dir)
        assert os.path.isdir(proj.assets_dir)
        assert os.path.isdir(proj.wiki_dir)
        assert os.path.isdir(proj.entities_dir)
        assert os.path.isdir(proj.concepts_dir)
        assert os.path.isdir(proj.queries_dir)
        assert os.path.isdir(proj.synthesis_dir)
        assert os.path.isdir(proj.comparisons_dir)

    def test_init_creates_schema(self, wiki_project):
        """init_wiki_project creates schema.md."""
        proj = init_wiki_project(str(wiki_project.root_path))
        assert os.path.isfile(proj.schema_path)
        content = Path(proj.schema_path).read_text(encoding="utf-8")
        assert "Wiki Schema" in content

    def test_init_creates_purpose(self, wiki_project):
        """init_wiki_project creates purpose.md."""
        proj = init_wiki_project(str(wiki_project.root_path))
        assert os.path.isfile(proj.purpose_path)
        content = Path(proj.purpose_path).read_text(encoding="utf-8")
        assert "Purpose" in content

    def test_init_creates_wiki_files(self, wiki_project):
        """init_wiki_project creates index.md, log.md, overview.md."""
        proj = init_wiki_project(str(wiki_project.root_path))
        assert os.path.isfile(proj.index_path)
        assert os.path.isfile(proj.log_path)
        assert os.path.isfile(proj.overview_path)

    def test_init_custom_schema(self, wiki_project):
        """init_wiki_project accepts custom schema content."""
        custom_schema = "# Custom Schema\n\nCustom rules here."
        proj = init_wiki_project(
            str(wiki_project.root_path),
            schema_content=custom_schema,
        )
        content = Path(proj.schema_path).read_text(encoding="utf-8")
        assert "Custom Schema" in content
        assert "Custom rules here" in content

    def test_init_custom_purpose(self, wiki_project):
        """init_wiki_project accepts custom purpose content."""
        custom_purpose = "# Custom Purpose\n\nCustom goals here."
        proj = init_wiki_project(
            str(wiki_project.root_path),
            purpose_content=custom_purpose,
        )
        content = Path(proj.purpose_path).read_text(encoding="utf-8")
        assert "Custom Purpose" in content

    def test_init_idempotent(self, wiki_project):
        """init_wiki_project is safe to call twice (exist_ok=True)."""
        proj1 = init_wiki_project(str(wiki_project.root_path))
        proj2 = init_wiki_project(str(wiki_project.root_path))
        # Both should return valid projects pointing to same location
        assert proj1.root_path == proj2.root_path


class TestReadWriteFile:
    """Test safe file I/O utilities."""

    def test_read_file_safe_utf8(self, wiki_temp_dir):
        """read_file_safe reads UTF-8 files correctly."""
        path = wiki_temp_dir / "utf8_test.txt"
        path.write_text("Hello 世界 🌍", encoding="utf-8")
        content = read_file_safe(str(path))
        assert content == "Hello 世界 🌍"

    def test_read_file_safe_missing(self):
        """read_file_safe returns empty string for missing files."""
        content = read_file_safe("/nonexistent/path/to/file.txt")
        assert content == ""

    def test_write_file_safe_basic(self, wiki_temp_dir):
        """write_file_safe creates file with content."""
        path = wiki_temp_dir / "written.txt"
        success = write_file_safe(str(path), "Test content")
        assert success is True
        assert path.read_text(encoding="utf-8") == "Test content"

    def test_write_file_safe_creates_parent_dirs(self, wiki_temp_dir):
        """write_file_safe creates parent directories."""
        path = wiki_temp_dir / "subdir" / "nested" / "file.txt"
        success = write_file_safe(str(path), "Nested content")
        assert success is True
        assert path.read_text(encoding="utf-8") == "Nested content"

    def test_write_file_safe_read_back(self, wiki_temp_dir):
        """write_file_safe can write and read back binary-safe text."""
        content = "Line 1\nLine 2\n中文内容\nemoji: 🎉"
        path = wiki_temp_dir / "roundtrip.txt"
        write_file_safe(str(path), content)
        assert read_file_safe(str(path)) == content


class TestWriteWikiPage:
    """Test write_wiki_page with its smart merge logic."""

    def test_write_log_merges(self, wiki_project_fs):
        """Writing to log.md appends content."""
        proj = wiki_project_fs
        initial = read_file_safe(proj.log_path)
        assert "Wiki Log" in initial

        entry = "## [2025-01-01] ingest | test-file.md\nTest detail."
        write_wiki_page(proj, "wiki/log.md", entry)
        after = read_file_safe(proj.log_path)
        assert entry in after

    def test_write_index_overwrites(self, wiki_project_fs):
        """Writing to index.md overwrites existing content."""
        proj = wiki_project_fs
        new_content = "# Index\n\n## Custom Index\n\nOverwritten content.\n"
        write_wiki_page(proj, "wiki/index.md", new_content)
        content = read_file_safe(proj.index_path)
        assert "Custom Index" in content
        assert "Overwritten content" in content

    def test_write_content_page_merge_sources(self, wiki_project_fs):
        """Writing a content page merges sources[] from existing page."""
        proj = wiki_project_fs
        existing_content = (
            "---\n"
            "type: concept\n"
            'title: "Existing"\n'
            "sources: [old-source.md]\n"
            "---\n\n"
            "# Existing\n"
        )
        existing_path = proj.concepts_dir + "/existing.md"
        Path(existing_path).write_text(existing_content, encoding="utf-8")

        new_content = (
            "---\n"
            "type: concept\n"
            'title: "Updated"\n'
            "sources: [new-source.md]\n"
            "---\n\n"
            "# Updated\n"
        )
        write_wiki_page(proj, "wiki/concepts/existing.md", new_content)
        final = read_file_safe(existing_path)
        # Both sources should be present
        assert "new-source.md" in final
        assert "old-source.md" in final


class TestReadWikiPage:
    """Test read_wiki_page parsing."""

    def test_read_wiki_page_basic(self, sample_wiki_page):
        """read_wiki_page parses a standard wiki page correctly."""
        page = read_wiki_page(sample_wiki_page)
        assert page is not None
        assert page.path == sample_wiki_page
        assert page.frontmatter.page_type.value == "entity"
        assert page.frontmatter.title == "Test Entity"
        assert "test entity page" in page.content.lower()
        assert "test-concept" in page.content

    def test_read_wiki_page_missing(self):
        """read_wiki_page returns None for missing files."""
        result = read_wiki_page("/nonexistent/wiki/page.md")
        assert result is None

    def test_read_wiki_page_no_frontmatter(self, wiki_temp_dir):
        """read_wiki_page handles pages without frontmatter."""
        path = wiki_temp_dir / "no-fm.md"
        path.write_text("# Just a Heading\n\nContent without frontmatter.", encoding="utf-8")
        page = read_wiki_page(str(path))
        assert page is not None
        assert page.frontmatter.page_type == WikiPageType.CONCEPT  # default
        assert "Just a Heading" in page.content


# Re-import to avoid unused import warning
from ariadne.wiki.models import WikiPageType


class TestListWikiPages:
    """Test list_wiki_pages."""

    def test_list_empty_dir(self, wiki_project):
        """list_wiki_pages returns empty list for empty wiki directory."""
        # Use wiki_project (no filesystem created) + manually create empty wiki_dir
        import os
        os.makedirs(wiki_project.wiki_dir, exist_ok=True)
        pages = list_wiki_pages(wiki_project.wiki_dir)
        assert pages == []

    def test_list_finds_markdown_files(self, wiki_project_fs):
        """list_wiki_pages recursively finds .md files."""
        # Create some pages
        Path(wiki_project_fs.entities_dir) / "a.md"
        Path(wiki_project_fs.entities_dir) / "b.md"
        Path(wiki_project_fs.concepts_dir) / "c.md"
        write_file_safe(Path(wiki_project_fs.entities_dir) / "a.md", "# A\n")
        write_file_safe(Path(wiki_project_fs.entities_dir) / "b.md", "# B\n")
        write_file_safe(Path(wiki_project_fs.concepts_dir) / "c.md", "# C\n")

        pages = list_wiki_pages(wiki_project_fs.wiki_dir)
        assert len(pages) >= 3
        assert any("a.md" in p for p in pages)
        assert any("b.md" in p for p in pages)
        assert any("c.md" in p for p in pages)

    def test_list_excludes_non_markdown(self, wiki_project_fs):
        """list_wiki_pages ignores non-.md files."""
        Path(wiki_project_fs.wiki_dir) / "data.json"
        Path(wiki_project_fs.wiki_dir) / "readme.txt"
        write_file_safe(Path(wiki_project_fs.wiki_dir) / "data.json", "{}")
        write_file_safe(Path(wiki_project_fs.wiki_dir) / "readme.txt", "Readme")

        pages = list_wiki_pages(wiki_project_fs.wiki_dir)
        assert all(p.endswith(".md") for p in pages)


class TestGetWikiPageSlugs:
    """Test get_wiki_page_slugs."""

    def test_slug_map_basic(self, sample_wiki_pages):
        """get_wiki_page_slugs builds a slug→path map."""
        # Use the first page's directory as wiki_dir
        wiki_dir = str(Path(list(sample_wiki_pages.values())[0]).parent.parent)
        slug_map = get_wiki_page_slugs(wiki_dir)
        assert len(slug_map) >= 2  # at least agent.md + memory.md
        assert any("agent" in k for k in slug_map.keys())

    def test_slug_map_case_insensitive(self, wiki_project_fs):
        """Slug map is case-insensitive."""
        Path(wiki_project_fs.entities_dir) / "TestCase.md"
        write_file_safe(Path(wiki_project_fs.entities_dir) / "TestCase.md", "# Test\n")
        slug_map = get_wiki_page_slugs(wiki_project_fs.wiki_dir)
        # Should find by lowercase
        assert "testcase" in slug_map


class TestParseFileBlocks:
    """Test LLM output block parsing."""

    def test_parse_single_block(self):
        """parse_file_blocks parses a single FILE block."""
        text = """---FILE: wiki/concepts/test.md ---
# Test Concept

Content of the concept.
---END FILE---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["path"] == "wiki/concepts/test.md"
        assert "# Test Concept" in blocks[0]["content"]

    def test_parse_multiple_blocks(self):
        """parse_file_blocks parses multiple FILE blocks."""
        text = """---FILE: wiki/entities/a.md ---
# A Entity
---END FILE---

Some preamble text.

---FILE: wiki/concepts/b.md ---
# B Concept
---END FILE---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 2
        assert any(b["path"] == "wiki/entities/a.md" for b in blocks)
        assert any(b["path"] == "wiki/concepts/b.md" for b in blocks)

    def test_parse_preserves_code_fences(self):
        """parse_file_blocks preserves content inside code fences."""
        text = """---FILE: wiki/sources/code.md ---
```python
def hello():
    return "world"
```
---END FILE---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 1
        assert "```python" in blocks[0]["content"]
        assert 'return "world"' in blocks[0]["content"]

    def test_parse_unclosed_block_warns(self):
        """Unclosed FILE blocks produce a warning."""
        text = """---FILE: wiki/concepts/unclosed.md ---
# Unclosed
This block is never closed.
(no ---END FILE--- here)"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 0
        assert len(warnings) >= 1
        assert any("not closed" in w for w in warnings)

    def test_parse_empty_path_skipped(self):
        """FILE blocks with empty paths are skipped with a warning."""
        text = """---FILE:  ---
# No Path
---END FILE---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 0
        assert any("empty path" in w.lower() for w in warnings)

    def test_parse_case_insensitive_markers(self):
        """FILE/END FILE markers are case-insensitive."""
        text = """---FILE: wiki/test.md ---
Content
---End File---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 1

    def test_parse_complex_nested_content(self):
        """parse_file_blocks handles complex content with multiple fences."""
        text = """---FILE: wiki/sources/complex.md ---
Text outside fences.

```html
<div>Block 1</div>
```

More text.

```css
.block { color: red; }
```

Final text.
---END FILE---"""
        blocks, warnings = parse_file_blocks(text)
        assert len(blocks) == 1
        content = blocks[0]["content"]
        assert "Text outside fences" in content
        assert "```html" in content
        assert "```css" in content


class TestParseReviewBlocks:
    """Test review block parsing."""

    def test_parse_review_block(self):
        """parse_review_blocks extracts review items from LLM output."""
        text = """---REVIEW: contradiction | Check this claim ---
OPTIONS: Confirm|Reject|Fix Later
PAGES: entities/test-entity.md
SEARCH: related-topic
DESCRIPTION:
This claim seems inconsistent with the index.
---END REVIEW---"""
        items = parse_review_blocks(text)
        assert len(items) == 1
        assert items[0]["type"] == "contradiction"
        assert "Check this claim" in items[0]["title"]
        assert "Confirm" in items[0]["options"]
        assert "entities/test-entity.md" in items[0]["affected_pages"]

    def test_parse_multiple_review_blocks(self):
        """parse_review_blocks handles multiple review items."""
        text = """---REVIEW: suggestion | Add a related page ---
DESCRIPTION: Consider linking to the main concept page.
---END REVIEW---

---REVIEW: missing-page | Create overview page ---
PAGES: concepts/overview.md
---END REVIEW---"""
        items = parse_review_blocks(text)
        assert len(items) == 2

    def test_parse_review_no_blocks(self):
        """parse_review_blocks returns empty list for text without reviews."""
        text = "Just some regular LLM output without review blocks."
        items = parse_review_blocks(text)
        assert items == []


class TestExtractWikilinks:
    """Test wikilink extraction."""

    def test_extract_simple_links(self):
        """extract_wikilinks finds simple [[links]]."""
        content = "See [[Entity A]] and [[Concept B]]."
        links = extract_wikilinks(content)
        assert "Entity A" in links
        assert "Concept B" in links

    def test_extract_alias_links(self):
        """extract_wikilinks handles [[target|display]] alias syntax."""
        content = "See [[entity-x|Display Name]]."
        links = extract_wikilinks(content)
        assert "entity-x" in links  # Extracts target, not alias
        assert "Display Name" not in links

    def test_extract_no_links(self):
        """extract_wikilinks returns empty list for no links."""
        content = "Just regular text with no wikilinks."
        assert extract_wikilinks(content) == []


class TestIngestCache:
    """Test ingest cache functions."""

    def test_compute_content_hash(self):
        """compute_content_hash is deterministic."""
        content = "Test content for hashing."
        h1 = compute_content_hash(content)
        h2 = compute_content_hash(content)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex length

    def test_compute_content_hash_different(self):
        """Different content produces different hashes."""
        h1 = compute_content_hash("Content A")
        h2 = compute_content_hash("Content B")
        assert h1 != h2

    def test_check_ingest_cache_miss(self, wiki_project_fs):
        """check_ingest_cache returns None for uncached source."""
        result = check_ingest_cache(
            wiki_project_fs, "new-source.md", "New content"
        )
        assert result is None

    def test_save_and_check_cache_hit(self, wiki_project_fs):
        """save_ingest_cache + check_ingest_cache round-trip works."""
        content = "Test content for caching."
        written = ["wiki/sources/test.md", "wiki/entities/test.md"]

        save_ingest_cache(wiki_project_fs, "test-source.md", content, written)
        cached = check_ingest_cache(wiki_project_fs, "test-source.md", content)

        assert cached is not None
        assert "wiki/sources/test.md" in cached

    def test_cache_detects_modified_source(self, wiki_project_fs):
        """check_ingest_cache returns None when source content changed."""
        content = "Original content."
        written = ["wiki/sources/test.md"]
        save_ingest_cache(wiki_project_fs, "test.md", content, written)

        # Content changed
        modified = "Modified content."
        cached = check_ingest_cache(wiki_project_fs, "test.md", modified)
        assert cached is None

    def test_append_log_entry(self, wiki_project_fs):
        """append_log_entry adds an entry to log.md."""
        proj = wiki_project_fs
        initial_content = read_file_safe(proj.log_path)
        assert "Wiki Log" in initial_content

        append_log_entry(proj, "ingest", "test-file.md", "Generated 3 wiki page(s).")
        after_content = read_file_safe(proj.log_path)
        assert "ingest" in after_content
        assert "test-file.md" in after_content


class TestWriteFileBlocks:
    """Test write_file_blocks integration."""

    def test_write_file_blocks_roundtrip(self, wiki_project_fs):
        """write_file_blocks parses and writes FILE blocks correctly."""
        llm_output = """---FILE: wiki/concepts/from-llm.md ---
---
type: concept
title: "From LLM"
created: 2025-01-01
updated: 2025-01-01
tags: []
related: []
sources: []
---

# From LLM

This page was generated from LLM output.
---END FILE---"""
        written, warnings = write_file_blocks(wiki_project_fs, llm_output)
        assert len(written) == 1
        assert written[0] == "wiki/concepts/from-llm.md"

        # Verify it was written to disk
        page = read_wiki_page(
            os.path.join(wiki_project_fs.root_path, written[0])
        )
        assert page is not None
        assert page.frontmatter.title == "From LLM"
