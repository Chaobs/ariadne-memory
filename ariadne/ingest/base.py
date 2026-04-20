"""
Base ingestion interface for Ariadne.

Inspired by MemPalace's pluggable backend architecture:
https://github.com/MemPalace/mempalace

Key design principle: every ingestor must implement the same interface,
allowing the memory system to treat all document formats uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pathlib import Path


class SourceType(Enum):
    """Supported document source types."""
    MARKDOWN = "markdown"
    WORD = "word"
    PPT = "ppt"
    PDF = "pdf"
    TXT = "txt"
    CONVERSATION = "conversation"
    MINDMAP = "mindmap"
    CODE = "code"
    EXCEL = "excel"
    CSV = "csv"
    EPUB = "epub"
    IMAGE = "image"
    OCR = "ocr"
    ACADEMIC = "academic"
    WEB = "web"
    EMAIL = "email"
    VIDEO = "video"
    AUDIO = "audio"
    BINARY = "binary"
    MARKITDOWN = "markitdown"
    UNKNOWN = "unknown"


@dataclass
class Document:
    """
    A single indexed unit of knowledge.

    In the MemPalace analogy, this corresponds to a Drawer —
    the atomic storage unit within the memory system.

    Attributes:
        content: The raw text content of this chunk.
        source_type: What kind of document this came from.
        source_path: Where the original file lives.
        chunk_index: Position of this chunk within the source file.
        total_chunks: Total number of chunks in this source file.
        metadata: Arbitrary key-value metadata (title, author, date, tags, etc.)
        ingested_at: ISO 8601 timestamp when this chunk was ingested.
                     Used for timeline view (P3) and cache invalidation.
    """
    content: str
    source_type: SourceType = SourceType.UNKNOWN
    source_path: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    metadata: dict = field(default_factory=dict)
    ingested_at: Optional[str] = None

    def __post_init__(self):
        if not self.content or not self.content.strip():
            raise ValueError("Document content cannot be empty")
        if self.ingested_at is None:
            self.ingested_at = datetime.now(timezone.utc).isoformat()

    @property
    def doc_id(self) -> str:
        """
        Stable unique ID based on source path + chunk index.

        Uses location-based (not content-based) hashing so that:
        - Editing the source file doesn't orphan previous chunks
        - Upsert correctly replaces the same logical chunk
        - Historical versions remain traceable for timeline view (P3)
        """
        import hashlib
        raw = f"{self.source_path}:{self.chunk_index}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.doc_id,
            "content": self.content,
            "source_type": self.source_type.value,
            "source_path": self.source_path,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "metadata": self.metadata,
            "ingested_at": self.ingested_at,
        }


class BaseIngestor(ABC):
    """
    Abstract base class for all document ingestors.

    Subclass this to add support for a new file format.
    The ingest() method is the contract — return a list of Documents.

    Example:
        class MyFormatIngestor(BaseIngestor):
            def _extract(self, path: Path) -> List[str]:
                # Return raw text blocks from the file
                ...

        ingestor = MyFormatIngestor()
        docs = ingestor.ingest("path/to/file.myformat")
    """

    source_type: SourceType = SourceType.UNKNOWN

    @abstractmethod
    def _extract(self, path: Path) -> List[str]:
        """
        Extract raw text content from a file.

        Subclasses must implement this to parse the specific file format
        and return a list of text blocks (one per logical chunk).

        Args:
            path: Path to the file to extract from.

        Returns:
            A list of raw text strings, one per chunk.
        """
        ...

    def ingest(self, file_path: str) -> List[Document]:
        """
        Ingest a file and return a list of Document objects.

        This method handles:
        1. File existence validation
        2. Chunking via _extract()
        3. Wrapping each chunk in a Document with metadata

        Args:
            file_path: Path to the file to ingest.

        Returns:
            A list of Document objects.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is not supported.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        blocks = self._extract(path)
        total = len(blocks)

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

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
                },
            )
            for i, block in enumerate(blocks)
            if block.strip()
        ]

    @staticmethod
    def chunk_text(text: str, max_chars: int = 500, overlap: int = 50) -> List[str]:
        """
        Split long text into overlapping chunks for better retrieval.

        This is a simple character-based splitter. More advanced implementations
        may use sentence boundaries, semantic similarity, or LLM-guided splitting.

        Args:
            text: Raw text to chunk.
            max_chars: Maximum characters per chunk.
            overlap: Number of overlapping characters between chunks.

        Returns:
            A list of text chunks.
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            chunks.append(text[start:end])
            start += max_chars - overlap
        return chunks
