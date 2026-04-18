"""
Word document ingestor for Ariadne.

Extracts text from .docx files using python-docx.
"""

from pathlib import Path
from typing import List

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class WordIngestor(BaseIngestor):
    """
    Ingest Microsoft Word (.docx) documents.

    Extracts paragraphs as semantic units. Tables are flattened
    to plain text. Images are skipped (text-only for now).
    """

    source_type = SourceType.WORD

    def _extract(self, path: Path) -> List[str]:
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ImportError(
                "python-docx is required to ingest .docx files. "
                "Install it with: pip install python-docx"
            )

        doc = DocxDocument(str(path))
        chunks = []
        current = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                # Empty paragraph — flush current chunk if non-empty
                if current:
                    chunk_text = "\n".join(current)
                    if len(chunk_text) > 1000:
                        chunks.extend(self.chunk_text(chunk_text, max_chars=600, overlap=80))
                    else:
                        chunks.append(chunk_text)
                    current = []
                continue

            style = para.style.name if para.style else ""

            # Start a new chunk on heading styles
            if "Heading" in style or style.startswith("Title"):
                if current:
                    chunk_text = "\n".join(current)
                    chunks.append(chunk_text)
                    current = []
                current.append(text)
            else:
                current.append(text)

        # Flush remaining
        if current:
            chunk_text = "\n".join(current)
            if len(chunk_text) > 1000:
                chunks.extend(self.chunk_text(chunk_text, max_chars=600, overlap=80))
            else:
                chunks.append(chunk_text)

        return chunks if chunks else []
