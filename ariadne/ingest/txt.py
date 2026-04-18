"""
Plain text ingestor for Ariadne.

Extracts text from .txt files.
"""

from pathlib import Path
from typing import List

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class TxtIngestor(BaseIngestor):
    """
    Ingest plain text (.txt) files.

    Splits content on double newlines (paragraphs) and further
    chunks very long content.
    """

    source_type = SourceType.TXT

    def _extract(self, path: Path) -> List[str]:
        text = path.read_text(encoding="utf-8")

        # Split on paragraph boundaries (double newlines)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        for para in paragraphs:
            if len(para) > 1000:
                chunks.extend(self.chunk_text(para, max_chars=600, overlap=80))
            else:
                chunks.append(para)

        return chunks if chunks else [text.strip()]
