"""
Plain text ingestor for Ariadne.

Extracts text from .txt files with robust encoding detection.
"""

from pathlib import Path
from typing import List

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class TxtIngestor(BaseIngestor):
    """
    Ingest plain text (.txt) files.

    Supports multiple text encodings (UTF-8 BOM, UTF-8, GB18030, Latin-1)
    with automatic fallback, so files like Chinese-localization texts or
    Windows-1252 documents are handled gracefully.

    Splits content on double newlines (paragraphs) and further
    chunks very long content.
    """

    source_type = SourceType.TXT

    def _extract(self, path: Path) -> List[str]:
        text = self._read_text_robust(path)

        # Split on paragraph boundaries (double newlines)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        for para in paragraphs:
            if len(para) > 1000:
                chunks.extend(self.chunk_text(para, max_chars=600, overlap=80))
            else:
                chunks.append(para)

        return chunks if chunks else [text.strip()]

    @staticmethod
    def _read_text_robust(path: Path) -> str:
        """Read text with automatic encoding detection.

        Tries in order: utf-8-sig (BOM), utf-8, gb18030 (CJK),
        latin-1 (universal fallback).
        """
        encodings = ["utf-8-sig", "utf-8", "gb18030", "latin-1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, ValueError):
                continue
        # Final fallback: ignore errors
        return path.read_text(encoding="utf-8", errors="replace")
