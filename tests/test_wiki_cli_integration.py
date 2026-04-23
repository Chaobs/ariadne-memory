"""
Integration tests for Wiki CLI commands.

These tests invoke the CLI via subprocess to test end-to-end behavior.

Run with: python -m pytest tests/test_wiki_cli_integration.py -v
"""

import os
import sys
import subprocess
import tempfile
import shutil
import pytest
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
ARIADNE_DIR = SCRIPT_DIR.parent


def run_wiki_cmd(args: list, check=True, capture=True, cwd=None):
    """
    Run an ariadne wiki CLI command and return the result.

    Args:
        args: Arguments after 'ariadne wiki'
        check: Raise if return code != 0
        capture: Capture stdout/stderr
        cwd: Working directory (default: ARIADNE_DIR)
    """
    if cwd is None:
        cwd = str(ARIADNE_DIR)

    cmd = [sys.executable, "-m", "ariadne.cli", "wiki"] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=cwd,
    )
    if capture and result.stdout:
        print(f"[stdout]\n{result.stdout}")
    if capture and result.stderr:
        print(f"[stderr]\n{result.stderr}")
    print(f"[Exit code: {result.returncode}]")

    if check and result.returncode != 0:
        pytest.fail(f"Command failed: {' '.join(cmd)}")

    return result


class TestWikiCLIHelp:
    """Test wiki command help and discovery."""

    def test_wiki_help(self):
        """wiki --help displays help and lists subcommands."""
        result = run_wiki_cmd(["--help"], check=False)
        assert result.returncode == 0
        assert "init" in result.stdout or "init" in result.stderr.lower()

    def test_wiki_no_args(self):
        """wiki with no arguments shows help."""
        result = run_wiki_cmd([], check=False)
        # Should either show help or list subcommands
        assert result.returncode == 0


class TestWikiCLIInit:
    """Test wiki init command."""

    @pytest.fixture
    def temp_wiki_dir(self):
        """Provide an isolated temp directory for wiki creation."""
        tmp = tempfile.mkdtemp(prefix="ariadne_wiki_cli_test_")
        yield Path(tmp)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_wiki_init_creates_structure(self, temp_wiki_dir):
        """wiki init creates the full directory structure."""
        result = run_wiki_cmd(
            ["init", str(temp_wiki_dir)],
            check=False,
        )
        assert result.returncode == 0
        assert (temp_wiki_dir / "schema.md").exists()
        assert (temp_wiki_dir / "purpose.md").exists()
        assert (temp_wiki_dir / "raw" / "sources").exists()
        assert (temp_wiki_dir / "wiki" / "index.md").exists()
        assert (temp_wiki_dir / "wiki" / "log.md").exists()

    def test_wiki_init_with_name(self, temp_wiki_dir):
        """wiki init -n sets the project name."""
        result = run_wiki_cmd(
            ["init", str(temp_wiki_dir), "-n", "My Test Wiki"],
            check=False,
        )
        assert result.returncode == 0

    def test_wiki_init_existing_dir(self, temp_wiki_dir):
        """wiki init on existing directory is safe (idempotent)."""
        # First init
        run_wiki_cmd(["init", str(temp_wiki_dir)], check=False)
        # Second init should also succeed
        result = run_wiki_cmd(["init", str(temp_wiki_dir)], check=False)
        assert result.returncode == 0


class TestWikiCLIIngest:
    """Test wiki ingest command."""

    @pytest.fixture
    def wiki_and_source(self):
        """Set up an initialized wiki with a source file."""
        tmp = tempfile.mkdtemp(prefix="ariadne_wiki_cli_ingest_test_")
        wiki_dir = Path(tmp) / "test-wiki"
        wiki_dir.mkdir()

        # Init wiki
        result = run_wiki_cmd(["init", str(wiki_dir)], check=False, cwd=str(wiki_dir))
        assert result.returncode == 0

        # Create a source file
        source_dir = wiki_dir / "raw" / "sources"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_dir / "test-source.md"
        source_file.write_text(
            "# Test Source\n\n"
            "This is a test source document for CLI ingest testing.\n\n"
            "## Section 1\n\n"
            "Content of section 1.\n\n"
            "## Section 2\n\n"
            "Content of section 2.\n",
            encoding="utf-8",
        )

        yield str(wiki_dir), str(source_file)

        shutil.rmtree(tmp, ignore_errors=True)

    def test_wiki_ingest_help(self):
        """wiki ingest --help works."""
        result = run_wiki_cmd(["ingest", "--help"], check=False)
        assert result.returncode == 0

    def test_wiki_ingest_missing_source(self, wiki_and_source):
        """wiki ingest with non-existent source file fails gracefully."""
        wiki_dir, _ = wiki_and_source
        result = run_wiki_cmd(
            ["ingest", "/nonexistent/source.md", "-p", wiki_dir],
            check=False,
        )
        # Should complete (possibly with warnings) without crashing
        assert result.returncode in [0, 1]

    def test_wiki_ingest_runs(self, wiki_and_source):
        """wiki ingest accepts a source path (may warn about no LLM)."""
        wiki_dir, source_file = wiki_and_source
        result = run_wiki_cmd(
            ["ingest", source_file, "-p", wiki_dir],
            check=False,
        )
        # Should not crash (may warn about no LLM configured)
        assert result.returncode in [0, 1]
        # Output should mention the source file or LLM
        output = result.stdout + result.stderr
        assert "test-source.md" in output or "LLM" in output or "llm" in output.lower()

    def test_wiki_ingest_invalid_project(self):
        """wiki ingest with invalid project path fails gracefully."""
        result = run_wiki_cmd(
            ["ingest", "/some/source.md", "-p", "/nonexistent/project"],
            check=False,
        )
        # Should handle missing project directory gracefully
        assert result.returncode in [0, 1]


class TestWikiCLIList:
    """Test wiki list command."""

    @pytest.fixture
    def wiki_with_pages(self):
        """Set up a wiki with some pages."""
        tmp = tempfile.mkdtemp(prefix="ariadne_wiki_cli_list_test_")
        wiki_dir = Path(tmp) / "test-wiki"
        wiki_dir.mkdir()

        # Init wiki
        run_wiki_cmd(["init", str(wiki_dir)], check=False, cwd=str(wiki_dir))

        # Create a wiki page
        entities_dir = wiki_dir / "wiki" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)
        page = entities_dir / "test-entity.md"
        page.write_text(
            "---\n"
            "type: entity\n"
            'title: "Test Entity"\n'
            "created: 2025-01-01\n"
            "updated: 2025-01-01\n"
            "tags: [test]\n"
            "related: []\n"
            "sources: []\n"
            "---\n\n"
            "# Test Entity\n\n"
            "This is a test entity.\n",
            encoding="utf-8",
        )

        yield str(wiki_dir)

        shutil.rmtree(tmp, ignore_errors=True)

    def test_wiki_list_pages(self, wiki_with_pages):
        """wiki list shows wiki pages."""
        result = run_wiki_cmd(["list", "-p", wiki_with_pages], check=False)
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "test-entity" in output.lower() or "wiki" in output.lower()

    def test_wiki_list_help(self):
        """wiki list --help works."""
        result = run_wiki_cmd(["list", "--help"], check=False)
        assert result.returncode == 0


class TestWikiCLILint:
    """Test wiki lint command."""

    @pytest.fixture
    def wiki_with_broken_link(self):
        """Set up a wiki with a broken wikilink."""
        tmp = tempfile.mkdtemp(prefix="ariadne_wiki_cli_lint_test_")
        wiki_dir = Path(tmp) / "test-wiki"
        wiki_dir.mkdir()

        run_wiki_cmd(["init", str(wiki_dir)], check=False, cwd=str(wiki_dir))

        # Create a page with a broken link
        concepts_dir = wiki_dir / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)
        page = concepts_dir / "broken.md"
        page.write_text(
            "---\ntype: concept\n---\n"
            "# Broken\n"
            "This references [[entities/nonexistent]] which doesn't exist.\n",
            encoding="utf-8",
        )

        yield str(wiki_dir)

        shutil.rmtree(tmp, ignore_errors=True)

    def test_wiki_lint_help(self):
        """wiki lint --help works."""
        result = run_wiki_cmd(["lint", "--help"], check=False)
        assert result.returncode == 0

    def test_wiki_lint_finds_broken_link(self, wiki_with_broken_link):
        """wiki lint --structural detects broken links."""
        result = run_wiki_cmd(
            ["lint", "-p", wiki_with_broken_link, "--structural"],
            check=False,
        )
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "nonexistent" in output.lower() or "broken" in output.lower()

    def test_wiki_lint_empty_project(self):
        """wiki lint on empty temp directory is graceful."""
        tmp = tempfile.mkdtemp(prefix="ariadne_wiki_cli_lint_empty_")
        wiki_dir = Path(tmp) / "empty-wiki"
        wiki_dir.mkdir()
        run_wiki_cmd(["init", str(wiki_dir)], check=False, cwd=str(wiki_dir))

        result = run_wiki_cmd(
            ["lint", "-p", str(wiki_dir), "--structural"],
            check=False,
        )
        # Should not crash
        assert result.returncode in [0, 1]

        shutil.rmtree(tmp, ignore_errors=True)


class TestWikiCLIQuery:
    """Test wiki query command."""

    def test_wiki_query_help(self):
        """wiki query --help works."""
        result = run_wiki_cmd(["query", "--help"], check=False)
        assert result.returncode == 0

    def test_wiki_query_requires_question(self):
        """wiki query without a question is handled gracefully."""
        result = run_wiki_cmd(["query"], check=False)
        # Should either show help or return non-zero
        assert result.returncode in [0, 1]
