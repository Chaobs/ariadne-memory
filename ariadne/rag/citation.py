"""
Citation generation for Ariadne RAG Pipeline.

Citations are references that point back to specific documents/chunks
in the memory store. They serve two purposes:

1. **Transparency**: Users can verify where the AI's response came from
2. **Traceability**: Clicking a citation navigates to the original source

Supported citation formats:
- Inline references: "[1]", "[2]", etc. (numbered by rank)
- Source citations: "[Source: filename.pdf, chunk 2/5]"
- Markdown links: "[relevant text](source:doc_id)"
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ariadne.rag.hybrid_search import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """
    A single citation referencing a source document.

    Attributes:
        index: Citation index number (1 = most relevant).
        doc_id: Unique document identifier in the store.
        source_path: Path to the source file.
        source_type: Type of the source (pdf, markdown, etc.).
        title: Document title (from metadata or filename).
        chunk_index: Which chunk this citation refers to.
        total_chunks: Total chunks in the source document.
        highlight: The specific text excerpt being cited.
        highlight_start: Character offset of highlight in content.
        highlight_end: End character offset of highlight.
        score: Relevance score of this citation.
    """
    index: int
    doc_id: str
    source_path: str
    source_type: str
    title: str
    chunk_index: int = 0
    total_chunks: int = 1
    highlight: str = ""
    highlight_start: int = 0
    highlight_end: int = 0
    score: float = 0.0

    def format_plain(self) -> str:
        """Format citation as plain text."""
        chunk_info = ""
        if self.total_chunks > 1:
            chunk_info = f", chunk {self.chunk_index + 1}/{self.total_chunks}"
        return f"[{self.index}] {self.title} ({self.source_type}){chunk_info} — {self.source_path}"

    def format_markdown(self) -> str:
        """Format citation as a Markdown reference."""
        chunk_info = ""
        if self.total_chunks > 1:
            chunk_info = f" (chunk {self.chunk_index + 1}/{self.total_chunks})"
        return f"[{self.index}] **{self.title}**{chunk_info}: {self.source_path}"

    def format_inline(self) -> str:
        """Format citation index for inline use."""
        return f"[{self.index}]"


@dataclass
class CitationContext:
    """
    A chunk of text with surrounding context for display.

    Attributes:
        before: Text preceding the highlighted passage.
        highlight: The highlighted passage itself.
        after: Text following the highlighted passage.
        citation: The citation metadata for this chunk.
    """
    before: str = ""
    highlight: str = ""
    after: str = ""
    citation: Optional[Citation] = None

    def format(self, max_context_chars: int = 150) -> str:
        """
        Format the citation context as a readable excerpt.

        Args:
            max_context_chars: Maximum characters for before/after context.

        Returns:
            Formatted string like: "...surrounding text [highlighted] surrounding..."
        """
        before = self._truncate(self.before, max_context_chars, from_end=True)
        after = self._truncate(self.after, max_context_chars, from_end=False)

        sep_before = "..." if before else ""
        sep_after = "..." if after else ""

        return f"{sep_before}{before}[{self.highlight}]{after}{sep_after}"

    @staticmethod
    def _truncate(text: str, max_chars: int, from_end: bool = True) -> str:
        """Truncate text to max_chars, removing from start or end."""
        if len(text) <= max_chars:
            return text
        if from_end:
            return text[-max_chars:]
        return text[:max_chars]


class CitationGenerator:
    """
    Generate citations from search results with highlighted excerpts.

    Usage:
        >>> gen = CitationGenerator()
        >>> citations = gen.generate(results, query)
        >>> for ctx in gen.format_contexts(citations):
        ...     print(ctx.format())
    """

    # How many characters to extract around the best matching sentence
    CONTEXT_CHARS = 200

    def __init__(self, max_citations: int = 10):
        """
        Initialize the citation generator.

        Args:
            max_citations: Maximum number of citations to generate.
        """
        self._max_citations = max_citations

    def generate(
        self,
        results: List[SearchResult],
        query: Optional[str] = None,
    ) -> List[Citation]:
        """
        Generate citations from search results.

        Args:
            results: List of SearchResult objects (already ranked).
            query: Optional original query (used for keyword highlighting).

        Returns:
            List of Citation objects, one per result.
        """
        citations = []
        query_terms = set(query.lower().split()) if query else set()

        for i, result in enumerate(results[:self._max_citations], start=1):
            doc = result.document

            # Extract best highlight from content
            highlight, start, end = self._extract_highlight(
                doc.content, query_terms
            )

            # Get title from metadata or derive from path
            title = doc.metadata.get("title", "")
            if not title:
                title = self._derive_title(doc.source_path)

            citation = Citation(
                index=i,
                doc_id=doc.doc_id,
                source_path=doc.source_path,
                source_type=doc.source_type.value,
                title=title,
                chunk_index=doc.chunk_index,
                total_chunks=doc.total_chunks,
                highlight=highlight,
                highlight_start=start,
                highlight_end=end,
                score=result.combined_score,
            )
            citations.append(citation)

        return citations

    def _extract_highlight(
        self,
        content: str,
        query_terms: set,
    ) -> Tuple[str, int, int]:
        """
        Extract the most relevant passage from content.

        Strategy:
        1. If query terms exist, find the sentence with the most overlap
        2. Otherwise, use the first sentence
        3. Truncate to a reasonable length

        Returns:
            Tuple of (highlighted_text, start_offset, end_offset).
        """
        if not content:
            return "", 0, 0

        # Split into sentences
        sentences = re.split(r'(?<=[。！？.!?])\s+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            # Fallback: use beginning of content
            excerpt = content[:300].strip()
            return excerpt, 0, len(excerpt)

        # Score each sentence by query term overlap
        if query_terms:
            scored = []
            for sent in sentences:
                sent_lower = sent.lower()
                overlap = sum(1 for term in query_terms if term in sent_lower)
                # Bonus for exact phrase match
                exact_bonus = 2 if any(term in sent_lower for term in query_terms) else 0
                scored.append((overlap + exact_bonus, sent))
            scored.sort(key=lambda x: x[0], reverse=True)
            best_sentence = scored[0][1] if scored[0][0] > 0 else sentences[0]
        else:
            best_sentence = sentences[0]

        # Find position in original content
        start = content.find(best_sentence)
        if start == -1:
            start = 0
            best_sentence = content[:300]

        end = start + len(best_sentence)

        # Truncate if too long
        if len(best_sentence) > 400:
            best_sentence = best_sentence[:400] + "..."

        return best_sentence, start, end

    @staticmethod
    def _derive_title(source_path: str) -> str:
        """Derive a human-readable title from a file path."""
        from pathlib import Path
        try:
            path = Path(source_path)
            name = path.stem  # filename without extension
            # Clean up common patterns
            name = re.sub(r'[_-]+', ' ', name)
            name = name.strip()
            return name or "Untitled"
        except Exception:
            return "Unknown source"

    def format_contexts(
        self,
        citations: List[Citation],
        content_map: dict = None,
    ) -> List[CitationContext]:
        """
        Format citation contexts for display.

        Args:
            citations: List of Citation objects.
            content_map: Optional dict of doc_id -> full content.
                        If not provided, uses citation.highlight only.

        Returns:
            List of CitationContext objects.
        """
        contexts = []
        for citation in citations:
            content = None
            if content_map and citation.doc_id in content_map:
                content = content_map[citation.doc_id]
            else:
                # Use the highlight + surrounding text from original content
                # We reconstruct this from the highlight position
                content = citation.highlight

            # Extract surrounding context
            if content and len(content) > 400:
                # Show first 200 + highlight + last 200
                mid = len(content) // 2
                before = content[max(0, mid - 200):citation.highlight_start]
                highlight = content[citation.highlight_start:citation.highlight_end]
                after = content[citation.highlight_end:min(len(content), mid + 200)]
            else:
                before = ""
                highlight = citation.highlight
                after = ""

            contexts.append(CitationContext(
                before=before,
                highlight=highlight,
                after=after,
                citation=citation,
            ))

        return contexts

    def inject_citations(
        self,
        text: str,
        citations: List[Citation],
        style: str = "inline",
    ) -> str:
        """
        Inject citation markers into text.

        Args:
            text: The text to annotate with citations.
            citations: List of Citation objects.
            style: "inline" (just numbers) or "markdown" (full references).

        Returns:
            Text with citation markers injected.
        """
        if not citations:
            return text

        if style == "inline":
            # Append inline citation indices at the end
            indices = [f"[{c.index}]" for c in citations]
            return f"{text}\n\nSources: {', '.join(indices)}"

        elif style == "markdown":
            # Add a references section
            lines = ["", "## References", ""]
            for c in citations:
                lines.append(c.format_markdown())
            return text + "\n".join(lines)

        return text
