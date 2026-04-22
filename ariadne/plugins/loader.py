"""
Ariadne Plugin Loader — Discovers and loads plugins from multiple sources.

Plugin discovery order:
1. Python entry_points (ariadne.ingestors, ariadne.hooks)
2. Plugin directories (configured in config.json -> plugins.directories)
3. Auto-discovered .py files in plugin directories

Plugin file convention:
    A plugin file should define ingestors using the @ingest_hook decorator
    or hooks using the @on decorator at module level.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def load_plugins_from_entry_points() -> List[str]:
    """
    Load plugins registered via Python entry_points.

    Looks for:
    - ariadne.ingestors: Ingestor classes to register
    - ariadne.hooks: Hook functions to register

    Returns:
        List of loaded plugin module names.
    """
    loaded = []

    try:
        # Python 3.9+ uses importlib.metadata
        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points
        else:
            from importlib.metadata import entry_points as _ep

        # Load ingestor entry points
        try:
            if sys.version_info >= (3, 10):
                eps = entry_points(group="ariadne.ingestors")
            else:
                eps = _ep().get("ariadne.ingestors", [])

            for ep in eps:
                try:
                    ingestor_cls = ep.load()
                    from ariadne.plugins.registry import IngestorRegistry
                    # The class should have EXTENSIONS attribute or be registered manually
                    if hasattr(ingestor_cls, 'EXTENSIONS'):
                        IngestorRegistry.register(ingestor_cls.EXTENSIONS, ingestor_cls)
                    logger.info(f"Loaded ingestor plugin: {ep.name} -> {ingestor_cls.__name__}")
                    loaded.append(ep.name)
                except Exception as e:
                    logger.error(f"Failed to load ingestor plugin '{ep.name}': {e}")
        except Exception:
            pass

        # Load hook entry points
        try:
            if sys.version_info >= (3, 10):
                eps = entry_points(group="ariadne.hooks")
            else:
                eps = _ep().get("ariadne.hooks", [])

            for ep in eps:
                try:
                    hook_func = ep.load()
                    # The function should self-register via @on decorator
                    # or we register it here
                    logger.info(f"Loaded hook plugin: {ep.name} -> {hook_func.__name__}")
                    loaded.append(ep.name)
                except Exception as e:
                    logger.error(f"Failed to load hook plugin '{ep.name}': {e}")
        except Exception:
            pass

    except ImportError:
        logger.debug("importlib.metadata not available, skipping entry_points discovery")

    return loaded


def load_plugins_from_directory(directory: str) -> List[str]:
    """
    Load plugin .py files from a directory.

    Each .py file is imported as a module. The module can use
    @ingest_hook and @on decorators at module level to register
    ingestors and hooks.

    Args:
        directory: Path to the plugin directory.

    Returns:
        List of loaded plugin module names.
    """
    dir_path = Path(directory).expanduser()
    if not dir_path.exists() or not dir_path.is_dir():
        logger.debug(f"Plugin directory not found: {dir_path}")
        return []

    loaded = []
    for py_file in sorted(dir_path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"ariadne_plugin_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(py_file))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                logger.info(f"Loaded plugin: {py_file.name}")
                loaded.append(py_file.stem)
        except Exception as e:
            logger.error(f"Failed to load plugin '{py_file.name}': {e}")

    return loaded


def load_all_plugins(directories: Optional[List[str]] = None) -> List[str]:
    """
    Load plugins from all sources.

    Args:
        directories: Additional directories to scan for plugins.
                    Also reads from config.json if available.

    Returns:
        List of all loaded plugin names.
    """
    loaded = []

    # 1. Load from entry_points
    loaded.extend(load_plugins_from_entry_points())

    # 2. Load from configured directories
    plugin_dirs = list(directories or [])

    # Try to read from config
    try:
        from ariadne.config import get_config
        cfg = get_config()
        config_dirs = cfg.get("plugins.directories", [])
        if isinstance(config_dirs, list):
            plugin_dirs.extend(config_dirs)
    except Exception:
        pass

    # 3. Default plugin directory
    try:
        from ariadne.paths import ARIADNE_DIR
        default_plugin_dir = ARIADNE_DIR / "plugins"
        if default_plugin_dir.exists():
            plugin_dirs.append(str(default_plugin_dir))
    except Exception:
        pass

    # Load from each directory
    for directory in plugin_dirs:
        loaded.extend(load_plugins_from_directory(directory))

    if loaded:
        logger.info(f"Loaded {len(loaded)} plugins: {loaded}")

    return loaded
