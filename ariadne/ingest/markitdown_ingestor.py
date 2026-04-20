"""
MarkItDown-based universal ingestor for Ariadne.

Leverages Microsoft's markitdown library to convert 22+ file formats
to Markdown, then chunks the result for vector storage.

Supported formats (via markitdown):
    Documents: .pdf, .docx, .pptx, .xlsx, .xls, .csv, .epub
    Web: .html, .htm, .rss, .xml (RSS), Wikipedia URLs, YouTube URLs
    Data: .ipynb (Jupyter notebooks), .zip (nested extraction)
    Media: images (via EXIF/LLM caption), audio (via transcription)
    Email: .msg (Outlook MSG)
    Other: .rtf (via plain text), any text-based format

This ingestor serves as a **supplementary** path alongside the native
Ariadne ingestors. The native ingestors are tried first because they
have format-specific chunking logic. MarkItDown kicks in for formats
that don't have a native ingestor, or when the native ingestor fails.
"""

import logging
from pathlib import Path
from typing import List, Optional

from ariadne.ingest.base import BaseIngestor, Document, SourceType

logger = logging.getLogger(__name__)


class MarkItDownIngestor(BaseIngestor):
    """
    Universal ingestor powered by Microsoft's markitdown library.

    Converts any supported file to Markdown, then applies Ariadne's
    chunking logic for vector storage. This provides broad format
    coverage (22+ formats) with a single dependency.

    Usage:
        ingestor = MarkItDownIngestor()
        docs = ingestor.ingest("presentation.pptx")
    """

    source_type = SourceType.MARKITDOWN

    # Extensions where markitdown excels over native ingestors
    PREFERRED_EXTENSIONS = {
        ".html", ".htm", ".rss", ".ipynb", ".msg", ".rtf",
        ".ods", ".odt", ".odp", ".xml",
    }

    # Extensions where native ingestors exist but markitdown can
    # serve as a fallback
    FALLBACK_EXTENSIONS = {
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
        ".epub", ".txt", ".md",
    }

    def __init__(self, enable_plugins: bool = False):
        self.enable_plugins = enable_plugins
        self._markitdown = None

    @property
    def markitdown(self):
        """Lazy-load the MarkItDown instance."""
        if self._markitdown is None:
            try:
                from markitdown import MarkItDown
            except ImportError:
                raise ImportError(
                    "markitdown is required for MarkItDownIngestor. "
                    "Install it with: pip install markitdown"
                )
            self._markitdown = MarkItDown(
                enable_plugins=self.enable_plugins,
            )
        return self._markitdown

    def _extract(self, path: Path) -> List[str]:
        """
        Convert a file to Markdown using markitdown, then chunk.

        Args:
            path: Path to the file to convert.

        Returns:
            List of text chunks (Markdown-formatted).
        """
        result = self._convert(path)

        if result is None:
            return [f"File reference (conversion failed): {path.name}"]

        markdown_text = result["markdown"]
        self._cached_title = result["title"]  # Cache for ingest() to use

        if not markdown_text or not markdown_text.strip():
            logger.warning(f"MarkItDown produced empty output for {path}")
            return [f"File reference (empty conversion): {path.name}"]

        # Prepend title as a header if available and not already present
        title = result["title"]
        if title and not markdown_text.strip().startswith("#"):
            markdown_text = f"# {title}\n\n{markdown_text}"

        # Chunk the Markdown text using header-aware splitting
        chunks = self._chunk_markdown(markdown_text)

        return chunks if chunks else [markdown_text.strip()]

    def _convert(self, path: Path) -> Optional[dict]:
        """
        Perform the actual markitdown conversion.

        Returns a dict with 'markdown' and 'title' keys, or None on failure.
        This method is separate so ingest() can reuse the conversion result
        without calling convert() twice.
        """
        try:
            result = self.markitdown.convert(str(path))
            return {
                "markdown": result.markdown,
                "title": result.title or path.stem,
            }
        except Exception as e:
            logger.warning(f"MarkItDown conversion failed for {path}: {e}")
            return None

    def _chunk_markdown(self, text: str) -> List[str]:
        """
        Split Markdown text into semantic chunks.

        Strategy:
        1. Split on ## headers (preserve header context)
        2. For very long sections, apply character-based chunking
        3. Preserve hierarchy by including parent headers

        Args:
            text: Markdown text to chunk.

        Returns:
            List of Markdown chunks.
        """
        import re

        # Strip YAML frontmatter
        text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)

        # Split on ## headers (## and below)
        sections = re.split(r"\n(?=##\s)", text)

        chunks = []
        current_h1 = ""

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Track H1 for context
            h1_match = re.match(r"^#\s+(.+)$", section, re.MULTILINE)
            if h1_match:
                current_h1 = h1_match.group(1).strip()

            # If section is very long, further chunk it
            if len(section) > 1500:
                sub_chunks = self.chunk_text(
                    section, max_chars=800, overlap=100
                )
                # Add H1 context to sub-chunks that don't start with ##
                if current_h1:
                    enhanced = []
                    for sc in sub_chunks:
                        if not sc.strip().startswith("#"):
                            sc = f"[{current_h1}]\n{sc}"
                        enhanced.append(sc)
                    chunks.extend(enhanced)
                else:
                    chunks.extend(sub_chunks)
            else:
                chunks.append(section)

        return chunks

    def ingest(self, file_path: str) -> List[Document]:
        """
        Ingest a file using markitdown and return Document objects.

        Overrides the base ingest() to add markitdown-specific metadata
        like the extracted title.

        Args:
            file_path: Path to the file to ingest.

        Returns:
            List of Document objects.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        blocks = self._extract(path)
        total = len(blocks)

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

        # Use cached title from _extract (avoids double convert)
        title = getattr(self, "_cached_title", path.stem)

        return [
            Document(
                content=block.strip(),
                source_type=self.source_type,
                source_path=str(path.absolute()),
                chunk_index=i,
                total_chunks=total,
                ingested_at=now_iso,
                metadata={
                    "file_name": path.name,
                    "file_ext": path.suffix,
                    "file_size": path.stat().st_size,
                    "title": title,
                    "ingestor": "markitdown",
                },
            )
            for i, block in enumerate(blocks)
            if block.strip()
        ]
