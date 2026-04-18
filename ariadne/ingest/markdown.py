"""
Markdown ingestor for Ariadne.

Extracts structured text from .md files, using headers to create
semantic chunks that preserve document hierarchy.
"""

import re
from pathlib import Path
from typing import List

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class MarkdownIngestor(BaseIngestor):
    """
    Ingest Markdown files, using headers as natural chunk boundaries.

    This makes search results more contextually relevant — a hit in
    "## Introduction" will surface the intro section rather than
    mixing it with unrelated sections.
    """

    source_type = SourceType.MARKDOWN

    def _extract(self, path: Path) -> List[str]:
        content = path.read_text(encoding="utf-8")

        # Strip YAML frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

        # Split on headers (## and below — ## is typically major section)
        sections = re.split(r"\n(?=#+\s)", content)

        chunks = []
        for section in sections:
            section = section.strip()
            if not section:
                continue

            # If section is very long, further chunk it
            if len(section) > 1000:
                sub_chunks = self.chunk_text(section, max_chars=600, overlap=80)
                chunks.extend(sub_chunks)
            else:
                chunks.append(section)

        return chunks if chunks else [content.strip()]
