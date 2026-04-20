"""
Web page and URL ingestor for Ariadne.

Fetches and extracts content from web pages.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Optional
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

# Type hint import
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore


class WebIngestor(BaseIngestor):
    """
    Ingest web pages from URLs.
    
    Extracts:
    - Title
    - Meta description
    - Main content (cleaned text)
    - Links (as metadata)
    - Author, date published
    
    Requires: requests, beautifulsoup4
    
    Example:
        ingestor = WebIngestor()
        docs = ingestor.ingest("https://example.com/article")
    """
    
    source_type = SourceType.WEB
    
    def __init__(self, timeout: int = 30, user_agent: Optional[str] = None):
        """
        Initialize web ingestor.
        
        Args:
            timeout: Request timeout in seconds.
            user_agent: Custom User-Agent string.
        """
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Ariadne/1.0 (Knowledge Graph System; "
            "https://github.com/Chaobs/ariadne-memory)"
        )
    
    def _extract(self, path: Path) -> List[str]:
        """Fetch and extract content from URL."""
        import requests
        
        url = str(path)  # path is actually the URL
        
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml',
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            blocks = []
            
            # Extract title
            title = self._get_title(soup)
            if title:
                blocks.append(f"[Title] {title}")
            
            # Extract metadata
            meta_blocks = self._get_metadata(soup, url)
            blocks.extend(meta_blocks)
            
            # Extract main content
            content = self._get_main_content(soup)
            if content:
                # Split into chunks
                chunks = self.chunk_text(content, max_chars=500, overlap=50)
                blocks.extend(chunks)
            
            return blocks if blocks else [f"Web page: {url}"]
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch URL: {e}")
            return [f"Failed to fetch: {url} - {str(e)}"]
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try og:title first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        # Try regular title tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return ""
    
    def _get_metadata(self, soup: BeautifulSoup, url: str) -> List[str]:
        """Extract metadata like description, author, date."""
        blocks = []
        
        # Meta description
        desc = soup.find('meta', attrs={'name': 'description'})
        if desc and desc.get('content'):
            blocks.append(f"[Description] {desc['content'].strip()}")
        
        # Open Graph description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            blocks.append(f"[Summary] {og_desc['content'].strip()}")
        
        # Author
        author = soup.find('meta', attrs={'name': 'author'})
        if author and author.get('content'):
            blocks.append(f"[Author] {author['content'].strip()}")
        
        # Publication date
        date_tags = [
            soup.find('meta', attrs={'name': 'date'}),
            soup.find('meta', attrs={'property': 'article:published_time'}),
            soup.find('time', itemprop='datePublished'),
        ]
        for tag in date_tags:
            if tag:
                content = tag.get('content') or tag.get('datetime') or tag.get_text(strip=True)
                if content:
                    blocks.append(f"[Published] {content}")
                    break
        
        # Keywords
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        if keywords and keywords.get('content'):
            blocks.append(f"[Keywords] {keywords['content'].strip()}")
        
        # Source
        blocks.append(f"[Source URL] {url}")
        
        return blocks
    
    def _get_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main article/content area."""
        # Remove script, style, nav, header, footer
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 
                        'aside', 'iframe', 'noscript']):
            tag.decompose()
        
        # Try common content selectors
        content_selectors = [
            ('article',),
            ('main',),
            ('div', {'class': re.compile(r'content|article|post|entry', re.I)}),
            ('div', {'id': re.compile(r'content|article|post|entry', re.I)}),
        ]
        
        import re
        for selector in content_selectors:
            if len(selector) == 1:
                content = soup.find(selector[0])
            else:
                content = soup.find(selector[0], selector[1])
            
            if content:
                text = content.get_text(separator=' ', strip=True)
                if len(text) > 200:
                    return text
        
        # Fallback: body text
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def ingest(self, file_path: str) -> List["Document"]:
        """Ingest a URL."""
        # Override to handle URLs
        from ariadne.ingest.base import Document
        
        path = Path(file_path)
        
        blocks = self._extract(path)
        
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return [
            Document(
                content=block.strip(),
                source_type=self.source_type,
                source_path=file_path,
                chunk_index=i,
                total_chunks=len(blocks),
                ingested_at=now_iso,
                metadata={
                    "url": file_path,
                    "file_name": path.name or file_path,
                },
            )
            for i, block in enumerate(blocks)
            if block.strip()
        ]
