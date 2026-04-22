"""
Ariadne Ingestor Registry — Extensible ingestor registration system.

Replaces the hardcoded EXTENSION_MAP in ingest/__init__.py with a
dynamically extensible registry. Third-party plugins can register
custom ingestors for new file formats without modifying core code.

Usage:
    # Register an ingestor for .log files
    from ariadne.plugins.registry import IngestorRegistry

    @IngestorRegistry.register_decorator(extensions=[".log", ".syslog"])
    class LogIngestor(BaseIngestor):
        source_type = SourceType.TXT
        def _extract(self, path): ...

    # Or register directly
    IngestorRegistry.register([".log"], LogIngestor)

    # Get an ingestor for a file
    ingestor = IngestorRegistry.get_ingestor("server.log")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Type

from ariadne.ingest.base import BaseIngestor, SourceType

logger = logging.getLogger(__name__)


class IngestorRegistry:
    """
    Extensible ingestor registry for Ariadne.

    Supports:
    - Extension-based ingestor lookup (e.g. ".pdf" -> PDFIngestor)
    - URL-based ingestor lookup
    - Priority-based registration (higher priority wins conflicts)
    - Decorator-based registration for plugin authors
    - Runtime registration and deregistration
    """

    # Internal state: extension -> list of (ingestor_cls, priority)
    _extension_map: Dict[str, List[Tuple[Type[BaseIngestor], int]]] = {}
    # URL scheme handlers: list of (ingestor_cls, priority)
    _url_handlers: List[Tuple[Type[BaseIngestor], int]] = []
    # Markitdown preferred/fallback sets (for compatibility)
    _markitdown_preferred: Set[str] = {
        ".html", ".htm", ".rss", ".ipynb", ".msg", ".rtf",
        ".ods", ".odt", ".odp", ".xml",
    }
    _markitdown_fallback: Set[str] = {
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
        ".epub", ".txt", ".md",
    }
    # Whether built-in ingestors have been registered
    _builtins_registered: bool = False

    # ── Registration ─────────────────────────────────────────────────────

    @classmethod
    def register(
        cls,
        extensions: List[str],
        ingestor_cls: Type[BaseIngestor],
        priority: int = 0,
    ) -> None:
        """
        Register an ingestor for one or more file extensions.

        Args:
            extensions: List of file extensions (e.g. [".log", ".syslog"]).
            ingestor_cls: The BaseIngestor subclass to instantiate.
            priority: Higher priority wins when multiple ingestors match.
                     Default 0; built-in ingestors use priority 0.
        """
        for ext in extensions:
            ext = ext.lower()
            if not ext.startswith("."):
                ext = "." + ext
            if ext not in cls._extension_map:
                cls._extension_map[ext] = []
            cls._extension_map[ext].append((ingestor_cls, priority))
            # Sort by priority descending
            cls._extension_map[ext].sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"Registered {ingestor_cls.__name__} for {extensions} (priority={priority})")

    @classmethod
    def register_url_handler(
        cls,
        ingestor_cls: Type[BaseIngestor],
        priority: int = 0,
    ) -> None:
        """Register an ingestor as a URL handler."""
        cls._url_handlers.append((ingestor_cls, priority))
        cls._url_handlers.sort(key=lambda x: x[1], reverse=True)

    @classmethod
    def deregister(cls, extensions: List[str], ingestor_cls: Optional[Type[BaseIngestor]] = None) -> None:
        """
        Deregister an ingestor for given extensions.

        If ingestor_cls is None, removes all ingestors for those extensions.
        """
        for ext in extensions:
            ext = ext.lower()
            if not ext.startswith("."):
                ext = "." + ext
            if ext in cls._extension_map:
                if ingestor_cls is None:
                    del cls._extension_map[ext]
                else:
                    cls._extension_map[ext] = [
                        (cls_, pri) for cls_, pri in cls._extension_map[ext]
                        if cls_ != ingestor_cls
                    ]
                    if not cls._extension_map[ext]:
                        del cls._extension_map[ext]

    @classmethod
    def register_decorator(cls, extensions: List[str], priority: int = 0):
        """
        Decorator to register an ingestor class.

        Usage:
            @IngestorRegistry.register_decorator(extensions=[".log"])
            class LogIngestor(BaseIngestor):
                ...
        """
        def decorator(ingestor_cls: Type[BaseIngestor]) -> Type[BaseIngestor]:
            cls.register(extensions, ingestor_cls, priority=priority)
            return ingestor_cls
        return decorator

    # ── Lookup ───────────────────────────────────────────────────────────

    @classmethod
    def get_ingestor(cls, source: str) -> BaseIngestor:
        """
        Factory method: get the appropriate ingestor for a source.

        Resolution priority:
        1. URL → URL handler (if registered)
        2. Extension with registered ingestor → highest priority match
        3. Markitdown preferred extensions → MarkItDownIngestor
        4. Markitdown fallback extensions → MarkItDownIngestor
        5. Unknown → MarkItDownIngestor (if available), else BinaryIngestor

        Args:
            source: File path, URL, or other source identifier.

        Returns:
            Appropriate ingestor instance.

        Raises:
            ValueError: If no ingestor found for the source type.
        """
        # Ensure built-ins are registered
        cls._ensure_builtins()

        source_lower = source.lower()

        # Check for URL
        if source_lower.startswith(("http://", "https://", "ftp://")):
            if cls._url_handlers:
                return cls._url_handlers[0][0]()
            # Fallback to WebIngestor
            from ariadne.ingest.web import WebIngestor
            return WebIngestor()

        # Get file extension
        path = Path(source)
        ext = path.suffix.lower() if path.suffix else ""

        # Check registered ingestors
        if ext in cls._extension_map:
            ingestor_cls, _ = cls._extension_map[ext][0]
            return ingestor_cls()

        # Markitdown preferred — formats with no native ingestor
        if ext in cls._markitdown_preferred:
            try:
                from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor
                return MarkItDownIngestor()
            except ImportError:
                logger.warning(
                    f"markitdown not installed; falling back to BinaryIngestor for {ext}"
                )
                from ariadne.ingest.binary import BinaryIngestor
                return BinaryIngestor()

        # Markitdown fallback — try if native didn't match
        if ext in cls._markitdown_fallback:
            try:
                from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor
                return MarkItDownIngestor()
            except ImportError:
                from ariadne.ingest.binary import BinaryIngestor
                return BinaryIngestor()

        # Unknown extension — try markitdown first, then binary
        try:
            from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor
            return MarkItDownIngestor()
        except ImportError:
            from ariadne.ingest.binary import BinaryIngestor
            return BinaryIngestor()

    # ── Query ────────────────────────────────────────────────────────────

    @classmethod
    def get_supported_extensions(cls) -> Set[str]:
        """Get all registered file extensions (for directory scanning etc.)."""
        cls._ensure_builtins()
        extensions = set(cls._extension_map.keys())
        extensions |= cls._markitdown_preferred
        # Don't include fallback extensions (they overlap with native)
        return extensions

    @classmethod
    def list_ingestors(cls) -> Dict[str, List[Tuple[str, Type[BaseIngestor], int]]]:
        """List all registered ingestors by extension (for diagnostics)."""
        cls._ensure_builtins()
        result = {}
        for ext, entries in cls._extension_map.items():
            result[ext] = [
                (ingestor_cls.__name__, ingestor_cls, priority)
                for ingestor_cls, priority in entries
            ]
        return result

    # ── Built-in registration ────────────────────────────────────────────

    @classmethod
    def _ensure_builtins(cls) -> None:
        """Register all built-in ingestors if not already done."""
        if cls._builtins_registered:
            return

        from ariadne.ingest.markdown import MarkdownIngestor
        from ariadne.ingest.word import WordIngestor
        from ariadne.ingest.ppt import PPTIngestor
        from ariadne.ingest.pdf import PDFIngestor
        from ariadne.ingest.txt import TxtIngestor
        from ariadne.ingest.conversation import ConversationIngestor
        from ariadne.ingest.mindmap import MindMapIngestor
        from ariadne.ingest.code import CodeIngestor
        from ariadne.ingest.excel import ExcelIngestor
        from ariadne.ingest.csv import CsvIngestor
        from ariadne.ingest.epub import EPUBIngestor
        from ariadne.ingest.image import ImageIngestor
        from ariadne.ingest.academic import BibTeXIngestor, RISIngestor
        from ariadne.ingest.email import EmailIngestor, MBOXIngestor
        from ariadne.ingest.media import VideoIngestor, AudioIngestor
        from ariadne.ingest.web import WebIngestor

        # Document formats
        cls.register([".md", ".markdown"], MarkdownIngestor)
        cls.register([".docx"], WordIngestor)
        cls.register([".pptx"], PPTIngestor)
        cls.register([".pdf"], PDFIngestor)
        cls.register([".txt"], TxtIngestor)
        cls.register([".json"], ConversationIngestor)
        cls.register([".mm", ".xmind"], MindMapIngestor)

        # Code formats
        cls.register([
            ".py", ".java", ".cpp", ".c", ".h", ".hpp",
            ".js", ".ts", ".jsx", ".tsx", ".cs", ".go", ".rs",
            ".rb", ".php", ".swift", ".kt", ".scala",
        ], CodeIngestor)

        # Spreadsheet formats
        cls.register([".xlsx", ".xls"], ExcelIngestor)
        cls.register([".csv"], CsvIngestor)

        # Media & Academic formats
        cls.register([".epub"], EPUBIngestor)
        cls.register([".bib"], BibTeXIngestor)
        cls.register([".ris"], RISIngestor)
        cls.register([".eml"], EmailIngestor)
        cls.register([".mbox"], MBOXIngestor)
        cls.register([
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
        ], ImageIngestor)
        cls.register([".mp4", ".avi", ".mkv", ".mov"], VideoIngestor)
        cls.register([".mp3", ".wav", ".m4a", ".flac", ".ogg"], AudioIngestor)

        # URL handler
        cls.register_url_handler(WebIngestor)

        cls._builtins_registered = True

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (useful for testing)."""
        cls._extension_map.clear()
        cls._url_handlers.clear()
        cls._builtins_registered = False
