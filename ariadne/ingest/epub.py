"""
EPUB e-book ingestor for Ariadne.

Extracts text content and metadata from EPUB files.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class EPUBIngestor(BaseIngestor):
    """
    Ingest EPUB e-books.
    
    Extracts:
    - Full text content
    - Metadata (title, author, publisher, etc.)
    - Chapter structure
    
    Requires: ebooklib
    
    Example:
        ingestor = EPUBIngestor()
        docs = ingestor.ingest("book.epub")
    """
    
    source_type = SourceType.UNKNOWN  # Will be set dynamically
    
    def _extract(self, path: Path) -> List[str]:
        """Extract text content from EPUB file."""
        try:
            from ebooklib import epub
        except ImportError:
            raise ImportError(
                "ebooklib is required for EPUB support. "
                "Install it with: pip install ebooklib"
            )
        
        blocks = []
        metadata = {}
        
        # Load the book
        book = epub.read_epub(str(path))
        
        # Extract metadata
        if book.get_metadata('DC', 'title'):
            metadata['title'] = book.get_metadata('DC', 'title')[0][0]
        if book.get_metadata('DC', 'creator'):
            metadata['creator'] = book.get_metadata('DC', 'creator')[0][0]
        if book.get_metadata('DC', 'language'):
            metadata['language'] = book.get_metadata('DC', 'language')[0][0]
        if book.get_metadata('DC', 'publisher'):
            metadata['publisher'] = book.get_metadata('DC', 'publisher')[0][0]
        if book.get_metadata('DC', 'description'):
            metadata['description'] = book.get_metadata('DC', 'description')[0][0]
        
        # Extract chapter content
        chapters = []
        for item in book.get_items():
            if item.get_type() == 9:  # EPUBDocType.NAVIGATION_ITEM_DOCUMENT
                continue
            if item.get_content():
                content = item.get_content().decode('utf-8', errors='ignore')
                
                # Strip HTML tags
                from bs4 import BeautifulSoup
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                    
                    # Split by chapters (headers or significant breaks)
                    chapter_chunks = self._split_chapters(text)
                    chapters.extend(chapter_chunks)
                except Exception as e:
                    logger.warning(f"Failed to parse chapter: {e}")
        
        # Add metadata as first block
        if metadata:
            meta_text = " | ".join(f"{k}: {v}" for k, v in metadata.items())
            blocks.append(f"[Metadata] {meta_text}")
        
        blocks.extend(chapters)
        
        return blocks if blocks else [f"EPUB: {path.name}"]
    
    def _split_chapters(self, text: str) -> List[str]:
        """Split text into logical chapters."""
        import re
        
        # Try to split on chapter headers
        chapter_patterns = [
            r'Chapter\s+\d+',
            r'CHAPTER\s+\d+',
            r'第[一二三四五六七八九十百千\d]+章',
            r'^\d+\.\s+[A-Z]',  # "1. Introduction"
            r'\n#{1,3}\s+',  # Markdown headers
        ]
        
        chunks = []
        current = []
        
        for line in text.split('\n'):
            is_chapter_start = False
            for pattern in chapter_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_chapter_start = True
                    break
            
            if is_chapter_start and current:
                # Save current chapter
                chapter_text = ' '.join(current)
                if chapter_text.strip():
                    chunks.append(chapter_text)
                current = []
            
            current.append(line)
        
        # Don't forget the last chapter
        if current:
            chapter_text = ' '.join(current)
            if chapter_text.strip():
                chunks.append(chapter_text)
        
        return chunks if chunks else [text]
    
    def ingest(self, file_path: str) -> List["Document"]:
        """Ingest an EPUB file and return documents."""
        # Override to set correct source type
        self.source_type = SourceType.UNKNOWN
        return super().ingest(file_path)
