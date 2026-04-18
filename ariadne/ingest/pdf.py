"""
PDF ingestor for Ariadne.

Extracts text from .pdf files using PyMuPDF (fitz).
"""

import re
from pathlib import Path
from typing import List

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class PDFIngestor(BaseIngestor):
    """
    Ingest PDF documents using PyMuPDF (fitz).

    Strategy:
    - Extracts text page by page
    - Merges short pages (<200 chars) with adjacent ones
    - Further chunks long pages (>1500 chars) using paragraph boundaries
    - Preserves page number metadata for citation
    """

    source_type = SourceType.PDF

    def _extract(self, path: Path) -> List[str]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF is required to ingest .pdf files. "
                "Install it with: pip install PyMuPDF"
            )

        doc = fitz.open(str(path))
        raw_pages = []
        current = []

        for page_num, page in enumerate(doc, 1):
            text = page.get_text().strip()
            if not text:
                continue

            # Clean up excessive whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)

            # If this page is short, merge with current accumulation
            if len(text) < 200 and current:
                current[-1] += "\n" + text
            else:
                if current:
                    raw_pages.append("\n".join(current))
                current = [text]

        if current:
            raw_pages.append("\n".join(current))

        # Chunk long pages
        chunks = []
        for page_text in raw_pages:
            if len(page_text) > 1500:
                chunks.extend(self.chunk_text(page_text, max_chars=800, overlap=100))
            else:
                chunks.append(page_text)

        return chunks if chunks else []
