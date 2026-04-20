"""
Academic literature metadata ingestor.

Handles BibTeX and RIS format files commonly used in academic citation management.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Dict, Optional
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class BibTeXIngestor(BaseIngestor):
    """
    Ingest BibTeX (.bib) files.
    
    Extracts structured metadata from BibTeX entries:
    - Title, authors, year
    - Journal/conference/publication venue
    - Abstract
    - Keywords, DOI, URL
    
    Example:
        ingestor = BibTeXIngestor()
        docs = ingestor.ingest("references.bib")
    """
    
    source_type = SourceType.ACADEMIC
    
    # BibTeX entry types we recognize
    ENTRY_TYPES = {
        'article', 'book', 'inbook', 'incollection', 'inproceedings',
        'conference', 'proceedings', 'phdthesis', 'mastersthesis',
        'techreport', 'manual', 'misc', 'unpublished',
    }
    
    def _extract(self, path: Path) -> List[str]:
        """Extract entries from BibTeX file."""
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        entries = self._parse_bibtex(content)
        
        blocks = []
        for entry in entries:
            block = self._format_entry(entry)
            blocks.append(block)
        
        return blocks if blocks else ["Empty BibTeX file"]
    
    def _parse_bibtex(self, content: str) -> List[Dict]:
        """Parse BibTeX content into structured entries."""
        entries = []
        
        # Remove comments
        content = re.sub(r'%.*$', '', content, flags=re.MULTILINE)
        
        # Find all entries
        entry_pattern = r'@(\w+)\s*\{\s*([^,]*)\s*,([^@]*?)(?=\n\s*@|\Z)'
        matches = re.findall(entry_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            entry_type = match[0].lower()
            citation_key = match[1].strip()
            fields_str = match[2]
            
            if entry_type not in self.ENTRY_TYPES:
                continue
            
            # Parse fields
            fields = {'entry_type': entry_type, 'citation_key': citation_key}
            
            # Match field = {value} or field = "value" or field = number
            field_pattern = r'(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)"|(\d+))'
            field_matches = re.findall(field_pattern, fields_str, re.DOTALL)
            
            for fm in field_matches:
                field_name = fm[0].lower()
                field_value = fm[1] or fm[2] or fm[3]
                fields[field_name] = field_value.strip()
            
            entries.append(fields)
        
        return entries
    
    def _format_entry(self, entry: Dict) -> str:
        """Format a BibTeX entry as readable text."""
        parts = []
        
        # Header
        entry_type = entry.get('entry_type', 'misc').upper()
        key = entry.get('citation_key', 'unknown')
        parts.append(f"[{entry_type}] {key}")
        
        # Core metadata
        if 'author' in entry:
            parts.append(f"Author(s): {entry['author']}")
        if 'title' in entry:
            parts.append(f"Title: {entry['title']}")
        if 'year' in entry:
            parts.append(f"Year: {entry['year']}")
        
        # Publication venue
        venue_fields = ['journal', 'booktitle', 'publisher', 'school', 'institution']
        for field in venue_fields:
            if field in entry:
                parts.append(f"{field.capitalize()}: {entry[field]}")
        
        # Abstract
        if 'abstract' in entry:
            parts.append(f"Abstract: {entry['abstract']}")
        
        # Identifiers
        if 'doi' in entry:
            parts.append(f"DOI: {entry['doi']}")
        if 'url' in entry:
            parts.append(f"URL: {entry['url']}")
        
        # Keywords
        if 'keywords' in entry:
            parts.append(f"Keywords: {entry['keywords']}")
        
        return '\n'.join(parts)


class RISIngestor(BaseIngestor):
    """
    Ingest RIS format (.ris) files.
    
    RIS is a standardized tag format for citation management software.
    
    Example:
        ingestor = RISIngestor()
        docs = ingestor.ingest("references.ris")
    """
    
    source_type = SourceType.ACADEMIC
    
    # Common RIS tags
    TAG_MAP = {
        'TY': 'entry_type',
        'AU': 'author',
        'A1': 'author',  # Primary author
        'A2': 'editor',  # Secondary author
        'TI': 'title',
        'T1': 'title',
        'PY': 'year',
        'DA': 'date',
        'JO': 'journal',
        'JF': 'journal_full',
        'T2': 'book_title',
        'PB': 'publisher',
        'KW': 'keywords',
        'AB': 'abstract',
        'N1': 'notes',
        'DO': 'doi',
        'UR': 'url',
        'SN': 'isbn_issn',
        'EP': 'end_page',
        'SP': 'start_page',
        'VL': 'volume',
        'IS': 'issue',
        'ER': '__END__',  # Entry terminator
    }
    
    def _extract(self, path: Path) -> List[str]:
        """Extract entries from RIS file."""
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        entries = self._parse_ris(content)
        
        blocks = []
        for entry in entries:
            block = self._format_entry(entry)
            blocks.append(block)
        
        return blocks if blocks else ["Empty RIS file"]
    
    def _parse_ris(self, content: str) -> List[Dict]:
        """Parse RIS content into structured entries."""
        entries = []
        current_entry = {}
        current_authors = []
        current_keywords = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse tag and value
            if len(line) >= 6 and line[2:4] == '  -':
                tag = line[0:2]
                value = line[6:].strip()
                
                field_name = self.TAG_MAP.get(tag, tag.lower())
                
                if field_name == '__END__':
                    # Save current entry
                    if current_entry:
                        if current_authors:
                            current_entry['author'] = '; '.join(current_authors)
                        if current_keywords:
                            current_entry['keywords'] = '; '.join(current_keywords)
                        entries.append(current_entry)
                    current_entry = {}
                    current_authors = []
                    current_keywords = []
                elif field_name == 'author':
                    current_authors.append(value)
                elif field_name == 'keywords':
                    current_keywords.append(value)
                elif field_name != '__END__':
                    current_entry[field_name] = value
        
        # Don't forget the last entry
        if current_entry:
            if current_authors:
                current_entry['author'] = '; '.join(current_authors)
            if current_keywords:
                current_entry['keywords'] = '; '.join(current_keywords)
            entries.append(current_entry)
        
        return entries
    
    def _format_entry(self, entry: Dict) -> str:
        """Format a RIS entry as readable text."""
        parts = []
        
        # Header
        entry_type = entry.get('entry_type', 'GEN').upper()
        parts.append(f"[{entry_type}]")
        
        # Core metadata
        if 'author' in entry:
            parts.append(f"Author(s): {entry['author']}")
        if 'title' in entry:
            parts.append(f"Title: {entry['title']}")
        if 'year' in entry:
            parts.append(f"Year: {entry['year']}")
        if 'date' in entry:
            parts.append(f"Date: {entry['date']}")
        
        # Publication venue
        if 'journal' in entry:
            parts.append(f"Journal: {entry['journal']}")
        if 'book_title' in entry:
            parts.append(f"Book Title: {entry['book_title']}")
        if 'publisher' in entry:
            parts.append(f"Publisher: {entry['publisher']}")
        
        # Abstract
        if 'abstract' in entry:
            parts.append(f"Abstract: {entry['abstract']}")
        
        # Identifiers
        if 'doi' in entry:
            parts.append(f"DOI: {entry['doi']}")
        if 'url' in entry:
            parts.append(f"URL: {entry['url']}")
        if 'isbn_issn' in entry:
            parts.append(f"ISBN/ISSN: {entry['isbn_issn']}")
        
        # Keywords
        if 'keywords' in entry:
            parts.append(f"Keywords: {entry['keywords']}")
        
        # Pagination
        if 'start_page' in entry or 'end_page' in entry:
            sp = entry.get('start_page', '')
            ep = entry.get('end_page', '')
            if sp and ep:
                parts.append(f"Pages: {sp}-{ep}")
            elif sp:
                parts.append(f"Page: {sp}")
        
        return '\n'.join(parts)
