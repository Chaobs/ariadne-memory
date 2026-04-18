"""
Ariadne Ingest Package — Unified ingestion interface for multiple document formats.

Each ingestor implements the BaseIngestor interface and converts a file into
a list of Document objects ready for vector storage.

Supported formats:
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
"""

from ariadne.ingest.base import BaseIngestor, Document
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

__all__ = [
    "BaseIngestor",
    "Document",
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
]
