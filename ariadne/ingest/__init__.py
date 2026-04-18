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
]
