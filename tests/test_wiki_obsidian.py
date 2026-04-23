"""
Unit tests for Ariadne Wiki Obsidian support.

Run with: python -m pytest tests/test_wiki_obsidian.py -v
"""

import os
import pytest
from pathlib import Path

from ariadne.wiki.obsidian import (
    parse_obsidian_frontmatter,
    extract_obsidian_tags,
    convert_obsidian_to_markdown,
    ObsidianIngestor,
    import_obsidian_vault,
)


class TestParseObsidianFrontmatter:
    """Test YAML frontmatter parsing for Obsidian notes."""

    def test_parse_valid_frontmatter(self):
        """parse_obsidian_frontmatter extracts YAML fields."""
        content = (
            "---\n"
            "alias: ['Test Note', 'TN']\n"
            "tags: [ai, memory]\n"
            "created: 2025-01-01\n"
            "---\n\n"
            "# Test Note\n"
            "Content here.\n"
        )
        fm = parse_obsidian_frontmatter(content)
        assert "alias" in fm
        assert "ai" in fm.get("tags", [])

    def test_parse_no_frontmatter(self):
        """parse_obsidian_frontmatter returns {} when no frontmatter."""
        content = "# Just a Heading\n\nPlain content without frontmatter."
        fm = parse_obsidian_frontmatter(content)
        assert fm == {}

    def test_parse_empty_content(self):
        """parse_obsidian_frontmatter handles empty content."""
        fm = parse_obsidian_frontmatter("")
        assert fm == {}


class TestExtractObsidianTags:
    """Test #tag extraction."""

    def test_extract_single_tags(self):
        """extract_obsidian_tags finds hash tags in content."""
        content = "This is about #artificial-intelligence and #machine-learning."
        tags = extract_obsidian_tags(content)
        assert "artificial-intelligence" in tags
        assert "machine-learning" in tags

    def test_extract_tags_excludes_code_blocks(self):
        """extract_obsidian_tags ignores tags inside code blocks."""
        content = "Use #real-tag here.\n```python\n# not_a_tag = 1\n```\nMore #real-tag here."
        tags = extract_obsidian_tags(content)
        assert "real-tag" in tags

    def test_extract_no_tags(self):
        """extract_obsidian_tags returns [] when no tags."""
        content = "Just plain text without any hash tags."
        assert extract_obsidian_tags(content) == []


class TestConvertObsidianToMarkdown:
    """Test Obsidian syntax → standard Markdown conversion."""

    def test_wikilink_kept_as_is(self):
        """Simple [[wikilinks]] are kept as-is."""
        content = "See [[Entity A]] for details."
        result = convert_obsidian_to_markdown(content)
        assert "[[Entity A]]" in result

    def test_wikilink_alias_converted(self):
        """[[link|alias]] is converted to markdown [alias](link)."""
        content = "See [[entity-x|Display Name]] for details."
        result = convert_obsidian_to_markdown(content)
        assert "[Display Name](entity-x)" in result
        assert "[[entity-x" not in result

    def test_image_embed_converted(self):
        """![[image.png]] is converted to markdown image syntax."""
        content = "See diagram ![[diagram.png]] here."
        result = convert_obsidian_to_markdown(content)
        assert "![diagram.png](diagram.png)" in result

    def test_file_embed_converted(self):
        """![[note.md]] is converted to markdown link."""
        content = "See ![[related-note]] for more."
        result = convert_obsidian_to_markdown(content)
        assert "[related-note](related-note)" in result

    def test_highlight_converted(self):
        """==highlight== is converted to **bold**."""
        content = "This is ==important highlight== text."
        result = convert_obsidian_to_markdown(content)
        assert "**important highlight**" in result

    def test_callout_converted(self):
        """Callout syntax is converted to styled blockquotes."""
        content = "> [!note]\n> This is a note."
        result = convert_obsidian_to_markdown(content)
        assert "**Note:**" in result

    def test_callout_multiple_types(self):
        """Different callout types are mapped correctly."""
        content = (
            "> [!tip]\n> Use this approach.\n\n"
            "> [!warning]\n> Be careful here.\n"
        )
        result = convert_obsidian_to_markdown(content)
        assert "**Tip:**" in result
        assert "**Warning:**" in result

    def test_no_changes_on_plain_markdown(self):
        """Plain markdown content is unchanged."""
        content = "# Heading\n\nPlain text with **bold**.\n"
        result = convert_obsidian_to_markdown(content)
        assert "# Heading" in result
        assert "**bold**" in result


class TestObsidianIngestor:
    """Test ObsidianIngestor for standard Ariadne pipeline."""

    @pytest.fixture
    def obsidian_note(self, wiki_temp_dir):
        """Create a sample Obsidian note file and return its path."""
        path = wiki_temp_dir / "obsidian-test.md"
        path.write_text(
            "---\n"
            "title: Obsidian Test Note\n"
            "tags: [test, obsidian]\n"
            "---\n\n"
            "# Obsidian Test Note\n\n"
            "This is a #test note with [[wikilink]].\n\n"
            "> [!note]\n"
            "> A callout block.\n\n"
            "==highlighted text==\n",
            encoding="utf-8",
        )
        return str(path)

    def test_can_handle_md_files(self, obsidian_note):
        """ObsidianIngestor.can_handle accepts .md files."""
        ingestor = ObsidianIngestor()
        assert ingestor.can_handle(obsidian_note) is True

    def test_ingest_extracts_metadata(self, obsidian_note):
        """ObsidianIngestor extracts frontmatter, tags, title."""
        ingestor = ObsidianIngestor()
        docs = ingestor.ingest(obsidian_note)
        assert len(docs) >= 1
        meta = docs[0].metadata
        assert meta["is_obsidian"] is True
        assert meta["source_type"] == "obsidian"
        assert "test" in meta["tags"]
        assert "obsidian" in meta["tags"]
        assert meta["title"] == "Obsidian Test Note"

    def test_ingest_converts_syntax(self, obsidian_note):
        """ObsidianIngestor converts Obsidian syntax in content."""
        ingestor = ObsidianIngestor()
        docs = ingestor.ingest(obsidian_note)
        content = docs[0].content
        # Wikilink kept as-is
        assert "[[wikilink]]" in content
        # Highlight converted
        assert "**highlighted text**" in content

    def test_ingest_missing_file(self):
        """ObsidianIngestor handles missing files gracefully."""
        ingestor = ObsidianIngestor()
        docs = ingestor.ingest("/nonexistent/obsidian/note.md")
        assert docs == []


class TestImportObsidianVault:
    """Test import_obsidian_vault for LLM Wiki pipeline."""

    @pytest.fixture
    def mock_vault(self, wiki_temp_dir):
        """Create a mock Obsidian vault with files."""
        vault_dir = wiki_temp_dir / "mock-vault"
        vault_dir.mkdir()

        # Excluded directories (need parents=True)
        (vault_dir / ".obsidian").mkdir()
        (vault_dir / "templates").mkdir()
        (vault_dir / "attachments").mkdir()

        # Main notes (should be imported)
        (vault_dir / "Note A.md").write_text("# Note A\n\nContent of A.", encoding="utf-8")
        (vault_dir / "Note B.md").write_text("# Note B\n\nContent of B.", encoding="utf-8")

        # Nested notes (should be imported with folder structure)
        (vault_dir / "sub").mkdir()
        (vault_dir / "sub" / "Nested.md").write_text("# Nested\n\nNested content.", encoding="utf-8")

        # Non-md file (should be skipped)
        (vault_dir / "data.json").write_text("{}", encoding="utf-8")

        return str(vault_dir)

    def test_import_copies_md_files(self, mock_vault, wiki_project_fs):
        """import_obsidian_vault copies .md files to raw/sources/."""
        result = import_obsidian_vault(
            vault_path=mock_vault,
            project=wiki_project_fs,
            copy_to_raw=True,
            ingest_immediately=False,
        )
        assert "error" not in result
        assert len(result["imported_files"]) >= 2

    def test_import_skips_excluded_dirs(self, mock_vault, wiki_project_fs):
        """import_obsidian_vault excludes .obsidian, templates, attachments."""
        result = import_obsidian_vault(
            vault_path=mock_vault,
            project=wiki_project_fs,
            copy_to_raw=True,
        )
        imported_paths = " ".join(result["imported_files"])
        # Should import .md files
        assert "Note A" in imported_paths or len(result["imported_files"]) >= 2

    def test_import_preserves_folder_structure(self, mock_vault, wiki_project_fs):
        """import_obsidian_vault preserves subdirectory structure."""
        result = import_obsidian_vault(
            vault_path=mock_vault,
            project=wiki_project_fs,
            copy_to_raw=True,
        )
        imported_paths = " ".join(result["imported_files"])
        assert "sub" in imported_paths

    def test_import_invalid_path(self, wiki_project_fs):
        """import_obsidian_vault handles invalid vault path gracefully."""
        result = import_obsidian_vault(
            vault_path="/nonexistent/vault/path",
            project=wiki_project_fs,
        )
        assert "error" in result
        assert result["imported"] == []
