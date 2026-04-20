"""
Pytest configuration and shared fixtures for Ariadne test suite.

Run with: python -m pytest tests/ -v
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_markdown(temp_dir):
    """Create a sample markdown file for testing."""
    path = temp_dir / "test.md"
    path.write_text("# Test Document\n\nThis is a test.\n", encoding="utf-8")
    return path


@pytest.fixture
def sample_text(temp_dir):
    """Create a sample text file for testing."""
    path = temp_dir / "test.txt"
    path.write_text("Hello, world!\n", encoding="utf-8")
    return path
