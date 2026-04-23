"""
Pytest fixtures for Ariadne Wiki module tests.

Run Wiki tests with: python -m pytest tests/test_wiki_*.py -v
Run all tests with:  python -m pytest tests/ -v

Fixtures provided:
  - wiki_project       : WikiProject instance in a temp directory (isolated)
  - wiki_project_fs    : Same as wiki_project, but directory structure is actually created on disk
  - sample_source_md   : A markdown source file inside wiki_project's raw/sources/
  - sample_source_txt   : A plain text source file inside wiki_project's raw/sources/
  - mock_llm           : Patch that replaces the LLM factory with a no-op mock
  - mock_llm_response  : Fixture that returns a configurable mock response
"""

import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure vendor packages are on path for tests that import ariadne
VENDOR_INIT = Path(__file__).parent.parent / "vendor" / "__init__.py"
if VENDOR_INIT.exists() and str(VENDOR_INIT.parent.parent) not in sys.path:
    sys.path.insert(0, str(VENDOR_INIT.parent.parent))

# Initialize vendor (sets up sys.path and env vars)
import vendor


# ─────────────────────────────────────────────────────────────────────────────
# Temp directory fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def wiki_temp_dir():
    """Provide an isolated temp directory that is cleaned up after the test."""
    tmp = tempfile.mkdtemp(prefix="ariadne_wiki_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# WikiProject fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def wiki_project(wiki_temp_dir):
    """
    Provide a WikiProject pointing to an isolated temp directory.
    Does NOT create the directory structure on disk — use wiki_project_fs for that.
    """
    from ariadne.wiki.models import WikiProject
    return WikiProject(root_path=str(wiki_temp_dir), name="Test Wiki")


@pytest.fixture
def wiki_project_fs(wiki_project):
    """
    Create the full wiki directory structure on disk and return the WikiProject.
    Use this fixture when testing filesystem operations (read/write/list).
    """
    os.makedirs(wiki_project.raw_dir, exist_ok=True)
    os.makedirs(wiki_project.sources_dir, exist_ok=True)
    os.makedirs(wiki_project.assets_dir, exist_ok=True)
    os.makedirs(wiki_project.wiki_dir, exist_ok=True)
    os.makedirs(wiki_project.entities_dir, exist_ok=True)
    os.makedirs(wiki_project.concepts_dir, exist_ok=True)
    os.makedirs(wiki_project.queries_dir, exist_ok=True)
    os.makedirs(wiki_project.synthesis_dir, exist_ok=True)
    os.makedirs(wiki_project.comparisons_dir, exist_ok=True)

    # Write placeholder schema / purpose files
    schema_path = wiki_project.schema_path
    purpose_path = wiki_project.purpose_path
    Path(schema_path).write_text("# Schema\n\nRules for this wiki.\n", encoding="utf-8")
    Path(purpose_path).write_text("# Purpose\n\nPurpose of this wiki.\n", encoding="utf-8")

    # Write index.md
    Path(wiki_project.index_path).write_text(
        "# Index\n\n---\ntype: index\n---\n\n",
        encoding="utf-8",
    )

    return wiki_project


# ─────────────────────────────────────────────────────────────────────────────
# Source file fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_source_md(wiki_project_fs):
    """Create a sample markdown source file in raw/sources/."""
    src_path = Path(wiki_project_fs.sources_dir) / "test-article.md"
    src_path.write_text(
        "# Test Article\n\n"
        "This is a test article for the Wiki module.\n\n"
        "## Section One\n\n"
        "Content of section one.\n\n"
        "## Section Two\n\n"
        "Content of section two.\n",
        encoding="utf-8",
    )
    return str(src_path)


@pytest.fixture
def sample_source_txt(wiki_project_fs):
    """Create a sample plain-text source file in raw/sources/."""
    src_path = Path(wiki_project_fs.sources_dir) / "notes.txt"
    src_path.write_text(
        "Test Notes\n"
        "==========\n\n"
        "First paragraph of notes.\n"
        "Second paragraph of notes.\n\n"
        "Third paragraph with more detail.\n",
        encoding="utf-8",
    )
    return str(src_path)


# ─────────────────────────────────────────────────────────────────────────────
# Wiki page fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_wiki_page(wiki_project_fs):
    """Create a sample wiki page (entity) on disk."""
    page_path = Path(wiki_project_fs.entities_dir) / "test-entity.md"
    content = (
        "---\n"
        "type: entity\n"
        'title: "Test Entity"\n'
        "created: 2025-01-01\n"
        "updated: 2025-01-01\n"
        "tags: [test, entity]\n"
        "related: []\n"
        "sources: []\n"
        "---\n\n"
        "# Test Entity\n\n"
        "This is a test entity page. See also [[concepts/test-concept]].\n\n"
        "## Properties\n\n"
        "- Property A\n"
        "- Property B\n"
    )
    page_path.write_text(content, encoding="utf-8")
    return str(page_path)


@pytest.fixture
def sample_wiki_pages(wiki_project_fs):
    """
    Create a small interconnected set of wiki pages on disk.
    Returns a dict mapping role → path.
    """
    pages = {}

    # Entity
    entity_path = Path(wiki_project_fs.entities_dir) / "agent.md"
    entity_path.write_text(
        "---\ntype: entity\ntitle: \"Agent\"\ncreated: 2025-01-01\nupdated: 2025-01-01\ntags: [ai, agent]\nrelated: [concepts/memory]\nsources: []\n---\n\n"
        "# Agent\n\n"
        "An agent is a system that perceives and acts.\n"
        "Related: [[concepts/memory]], [[concepts/reasoning]].\n",
        encoding="utf-8",
    )
    pages["entity"] = str(entity_path)

    # Concept
    concept_path = Path(wiki_project_fs.concepts_dir) / "memory.md"
    concept_path.write_text(
        "---\ntype: concept\ntitle: \"Memory\"\ncreated: 2025-01-01\nupdated: 2025-01-01\ntags: [memory, ai]\nrelated: [entities/agent]\nsources: []\n---\n\n"
        "# Memory\n\n"
        "Memory allows agents to retain information.\n"
        "Used by: [[entities/agent]].\n",
        encoding="utf-8",
    )
    pages["concept"] = str(concept_path)

    # Orphan page (no links to/from other pages)
    orphan_path = Path(wiki_project_fs.concepts_dir) / "orphan.md"
    orphan_path.write_text(
        "---\ntype: concept\ntitle: \"Orphan\"\ncreated: 2025-01-01\nupdated: 2025-01-01\ntags: []\nrelated: []\nsources: []\n---\n\n"
        "# Orphan\n\n"
        "This page has no connections.\n",
        encoding="utf-8",
    )
    pages["orphan"] = str(orphan_path)

    # Page with broken link (links to non-existent page)
    broken_path = Path(wiki_project_fs.concepts_dir) / "broken-link-page.md"
    broken_path.write_text(
        "---\ntype: concept\ntitle: \"Broken Link\"\ncreated: 2025-01-01\nupdated: 2025-01-01\ntags: []\nrelated: []\nsources: []\n---\n\n"
        "# Broken Link\n\n"
        "This references [[entities/nonexistent-page]] which doesn't exist.\n",
        encoding="utf-8",
    )
    pages["broken_link"] = str(broken_path)

    return pages


# ─────────────────────────────────────────────────────────────────────────────
# LLM mocking fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    """
    Patch _get_llm in ariadne.wiki.ingestor so it returns a mock LLM.
    The mock's chat() method returns a response with empty content.
    Use mock_llm_response for more control.
    """
    mock_response = MagicMock()
    mock_response.content = ""

    mock_llm_instance = MagicMock()
    mock_llm_instance.chat.return_value = mock_response

    with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm_instance):
        yield mock_llm_instance


@pytest.fixture
def mock_llm_response():
    """
    Patch _get_llm and return a configurable mock LLM.
    Usage:
        def test_something(mock_llm_response):
            mock_llm_response.chat.return_value.content = "Generated page content"
    """
    mock_response = MagicMock()
    mock_response.content = "Mocked LLM response"

    mock_llm_instance = MagicMock()
    mock_llm_instance.chat.return_value = mock_response

    with patch("ariadne.wiki.ingestor._get_llm", return_value=mock_llm_instance):
        yield mock_llm_instance
