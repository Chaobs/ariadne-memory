"""
Ariadne Vendored Dependencies Setup

This module configures the environment to use vendored packages and local model cache.
Import this before any other ariadne modules when using vendored distribution.

Usage:
    from ariadne.vendor import setup
    setup()

    # Now proceed with normal imports
    from ariadne.memory import VectorStore
"""

import os
import sys
from pathlib import Path

# Get the vendor directory path (relative to this file)
_VENDOR_DIR = Path(__file__).parent
_PACKAGES_DIR = _VENDOR_DIR / "packages"
_MODELS_DIR = _VENDOR_DIR / "models"
_CACHE_DIR = _VENDOR_DIR / "cache"


def setup(force: bool = False) -> bool:
    """
    Configure Ariadne to use vendored packages and local model cache.

    All caches (HuggingFace, Chroma) are redirected under vendor/ so that:
    - No data is written outside the project directory
    - New users get everything pre-configured
    - The project is self-contained and portable

    Args:
        force: If True, override existing environment variables.

    Returns:
        True if setup was successful, False otherwise.
    """
    changed = False

    # 1. HuggingFace cache location (sentence-transformers embedding models)
    hf_home = str(_MODELS_DIR)
    if force or "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = hf_home
        os.environ["HF_HUB_CACHE"] = str(_MODELS_DIR / "hub")
        changed = True

    # 2. ChromaDB ONNX model cache
    chroma_cache = str(_CACHE_DIR / "chroma")
    if force or ("CHROMA_CACHE_DIR" not in os.environ
                 and "XDG_CACHE_HOME" not in os.environ):
        os.environ["CHROMA_CACHE_DIR"] = chroma_cache
        changed = True

    # 3. General XDG cache fallback (some libraries use this)
    xdg_cache = str(_CACHE_DIR)
    if force or "XDG_CACHE_HOME" not in os.environ:
        os.environ["XDG_CACHE_HOME"] = xdg_cache
        changed = True

    # 4. Add vendored packages to Python path if they exist
    if _PACKAGES_DIR.exists():
        import site
        site.addsitedir(str(_PACKAGES_DIR))
        changed = True

    return changed


def get_vendor_info() -> dict:
    """Return information about vendored packages."""
    info = {
        "vendor_dir": str(_VENDOR_DIR),
        "packages_dir_exists": _PACKAGES_DIR.exists(),
        "packages": [],
        "models_dir_exists": _MODELS_DIR.exists(),
        "models": [],
        "cache_dir_exists": _CACHE_DIR.exists(),
        "hf_home": os.environ.get("HF_HOME", "default"),
        "chroma_cache": os.environ.get("CHROMA_CACHE_DIR", "default"),
    }

    if _PACKAGES_DIR.exists():
        info["packages"] = [p.stem for p in _PACKAGES_DIR.glob("*.whl")]

    if _MODELS_DIR.exists():
        for model_dir in _MODELS_DIR.rglob("snapshots"):
            if model_dir.is_dir():
                info["models"].append(model_dir.parent.name)

    return info


# Auto-setup when imported
setup()
