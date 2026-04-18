"""
CSV (Comma-Separated Values) ingestion for Ariadne.

Extracts tabular data from CSV files, preserving header context
and providing row-by-row chunking for semantic search.
"""

import csv
from pathlib import Path
from typing import List, Optional

from .base import BaseIngestor, SourceType


class CsvIngestor(BaseIngestor):
    """
    Ingestor for CSV files (.csv).
    
    Extracts:
    - CSV headers as column context
    - Row data as searchable chunks
    - Delimiter auto-detection
    
    Note: Python's csv module handles various delimiters.
    """
    
    source_type = SourceType.CSV
    
    # Common delimiters to try
    COMMON_DELIMITERS = [',', ';', '\t', '|']
    
    def _extract(self, path: Path) -> List[str]:
        """
        Extract content from CSV file.
        
        Returns structured blocks with:
        - Detected delimiter
        - Column headers
        - Row data chunks
        """
        blocks = []
        
        # Try to detect delimiter
        delimiter = self._detect_delimiter(path)
        
        try:
            with open(path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter)
                
                rows = list(reader)
                if not rows:
                    return blocks
                
                # First row as headers
                headers = rows[0] if rows else []
                header_line = f"Headers: {' | '.join(headers)}" if headers else ""
                
                blocks.append(header_line)
                
                # Data rows
                for row_idx, row in enumerate(rows[1:], start=2):
                    # Skip empty rows
                    if any(cell.strip() for cell in row):
                        # Include row number for reference
                        blocks.append(f"Row {row_idx}: {' | '.join(row)}")
                
        except UnicodeDecodeError:
            # Try alternative encodings
            for encoding in ['latin-1', 'cp1252', 'gbk', 'gb2312']:
                try:
                    with open(path, 'r', encoding=encoding, newline='') as f:
                        reader = csv.reader(f, delimiter=delimiter)
                        rows = list(reader)
                        
                        if rows:
                            headers = rows[0]
                            header_line = f"Headers: {' | '.join(headers)}"
                            blocks.append(header_line)
                            
                            for row_idx, row in enumerate(rows[1:], start=2):
                                if any(cell.strip() for cell in row):
                                    blocks.append(f"Row {row_idx}: {' | '.join(row)}")
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
        except Exception:
            pass
        
        return [b for b in blocks if b.strip()]
    
    def _detect_delimiter(self, path: Path) -> str:
        """
        Auto-detect the most likely delimiter by sampling the first few lines.
        
        Returns the delimiter with the most consistent column count.
        """
        try:
            with open(path, 'r', encoding='utf-8-sig', newline='') as f:
                sample = [f.readline() for _ in range(5)]
            
            delimiter_counts = {}
            for candidate in self.COMMON_DELIMITERS:
                col_counts = []
                for line in sample:
                    if line.strip():
                        col_counts.append(line.count(candidate) + 1)
                
                if col_counts and len(set(col_counts)) == 1:
                    delimiter_counts[candidate] = col_counts[0]
            
            # Return delimiter with highest consistent column count
            if delimiter_counts:
                return max(delimiter_counts, key=delimiter_counts.get)
        except Exception:
            pass
        
        return ','  # Default to comma
