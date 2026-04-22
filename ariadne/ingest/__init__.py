"""
Ariadne Ingest Package — Unified ingestion interface for multiple document formats.

Each ingestor implements the BaseIngestor interface and converts a file into
a list of Document objects ready for vector storage.

Supported formats:
    Document formats:
        .md        — Markdown notes (MarkdownIngestor)
        .docx      — Word documents (WordIngestor)
        .pptx      — PowerPoint slides (PPTIngestor)
        .pdf       — PDF documents (PDFIngestor)
        .txt       — Plain text files (TxtIngestor)
        .json      — Chat conversation exports (ConversationIngestor)
        .mm/.xmind — Mind maps (MindMapIngestor)
        .py/.java/.cpp/.js — Code files with comments (CodeIngestor)
        .xlsx/.xls — Excel spreadsheets (ExcelIngestor)
        .csv       — CSV files (CsvIngestor)
    Media & Academic:
        .epub      — EPUB e-books (EPUBIngestor)
        .bib       — BibTeX bibliographies (BibTeXIngestor)
        .ris       — RIS citation files (RISIngestor)
        .eml       — Email files (EmailIngestor)
        .mbox      — Email mailboxes (MBOXIngestor)
        .jpg/.png/.gif — Images with metadata (ImageIngestor)
        .mp4/.avi/.mkv — Videos with subtitles (VideoIngestor)
        .mp3/.wav/.m4a — Audio files (AudioIngestor)
    OCR Support:
        Scanned PDFs and images with text extraction (OCRIngestor)
    URL Support:
        Web pages (WebIngestor)
    Universal (via markitdown):
        .html/.htm/.rss/.ipynb/.msg/.rtf/.ods/.odt/.odp/.xml
        + fallback for any format not covered by native ingestors
"""

from ariadne.ingest.base import BaseIngestor, Document, SourceType
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

# P4 Media & Academic ingestors
from ariadne.ingest.epub import EPUBIngestor
from ariadne.ingest.image import ImageIngestor, OCRIngestor
from ariadne.ingest.academic import BibTeXIngestor, RISIngestor
from ariadne.ingest.web import WebIngestor
from ariadne.ingest.email import EmailIngestor, MBOXIngestor
from ariadne.ingest.media import VideoIngestor, AudioIngestor

# Binary file handler
from ariadne.ingest.binary import BinaryIngestor

# Universal ingestor via markitdown
from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor

__all__ = [
    # Base
    "BaseIngestor",
    "Document",
    "SourceType",
    # Document formats
    "MarkdownIngestor",
    "WordIngestor",
    "PPTIngestor",
    "PDFIngestor",
    "TxtIngestor",
    "ConversationIngestor",
    "MindMapIngestor",
    "CodeIngestor",
    "ExcelIngestor",
    "CsvIngestor",
    # Media & Academic
    "EPUBIngestor",
    "ImageIngestor",
    "OCRIngestor",
    "BibTeXIngestor",
    "RISIngestor",
    "WebIngestor",
    "EmailIngestor",
    "MBOXIngestor",
    "VideoIngestor",
    "AudioIngestor",
    # Binary files
    "BinaryIngestor",
    # Universal (markitdown)
    "MarkItDownIngestor",
    # Factory function
    "get_ingestor",
]


def get_ingestor(source: str) -> BaseIngestor:
    """
    Factory function to get the appropriate ingestor for a source.

    This function delegates to IngestorRegistry.get_ingestor(), which
    supports both built-in and plugin-registered ingestors.

    Resolution priority:
    1. URL → WebIngestor
    2. Extension with a registered ingestor → that ingestor (highest priority)
    3. Extension in markitdown's preferred set → MarkItDownIngestor
    4. Extension in markitdown's fallback set → try native first, then markitdown
    5. Unknown extension → MarkItDownIngestor (if available), else BinaryIngestor

    Args:
        source: File path, URL, or other source identifier

    Returns:
        Appropriate ingestor instance

    Raises:
        ValueError: If no ingestor found for the source type
    """
    from ariadne.plugins.registry import IngestorRegistry
    return IngestorRegistry.get_ingestor(source)
