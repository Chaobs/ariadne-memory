"""
Ariadne Path Management.

Centralizes all path resolution so data lives under the project directory
rather than scattered across the user home directory (~/.ariadne, ~/.cache).

Layout (under project root / Ariadne/):
    .ariadne/
        config.json          # User configuration (NOT committed to git)
        .env                 # Environment variables (API keys etc.)
        memories/            # Multi-memory system directories
            manifest.json    # Memory system registry
            {name}/          # Per-system ChromaDB collections
        knowledge_graph.db   # SQLite knowledge graph
        chroma/              # ChromaDB persist directory (if configured)
    vendor/
        packages/            # Vendored pip wheels
        models/              # Cached embedding models (HF_HOME)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """
    Find the Ariadne project root directory.

    Strategy: start from the ariadne package and walk up until we find
    the project marker file or reach the filesystem root.
    """
    # Start from this file's location: ariadne/paths.py
    current = Path(__file__).resolve().parent.parent  # .../Ariadne/

    # If we're inside an editable install or venv, go higher
    for _ in range(6):  # max 6 levels up
        if (current / "vendor").is_dir() and (current / "ariadne" / "__init__.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return Path.cwd()


# ── Project Root ──────────────────────────────────────────────────────────

PROJECT_ROOT = _find_project_root()

# ── .ariadne Data Directory (under project root) ───────────────────────────

ARIADNE_DIR = PROJECT_ROOT / ".ariadne"

# Sub-directories
CONFIG_FILE = ARIADNE_DIR / "config.json"
ENV_FILE = ARIADNE_DIR / ".env"
MEMORIES_DIR = ARIADNE_DIR / "memories"
MANIFEST_FILE = MEMORIES_DIR / "manifest.json"
CHROMA_DEFAULT_DIR = ARIADNE_DIR / "chroma"
GRAPH_DB_PATH = ARIADNE_DIR / "knowledge_graph.db"

# ── Vendor Directory ───────────────────────────────────────────────────────

VENDOR_DIR = PROJECT_ROOT / "vendor"
VENDOR_PACKAGES = VENDOR_DIR / "packages"
VENDOR_MODELS = VENDOR_DIR / "models"


# ── Public API ────────────────────────────────────────────────────────────

def ensure_data_dirs() -> None:
    """Create all required data directories if they don't exist."""
    for d in [ARIADNE_DIR, MEMORIES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_config_path() -> str:
    """Get path to user config.json."""
    return str(CONFIG_FILE)


def get_env_path() -> str:
    """Get path to .env file."""
    return str(ENV_FILE)


def get_memories_dir() -> str:
    """Get path to memories base directory."""
    return str(MEMORIES_DIR)


def get_chroma_default_path() -> str:
    """Get default ChromaDB persistence path."""
    return str(CHROMA_DEFAULT_DIR)


def get_graph_db_path() -> str:
    """Get default knowledge graph database path."""
    return str(GRAPH_DB_PATH)


# Auto-create on import
ensure_data_dirs()
