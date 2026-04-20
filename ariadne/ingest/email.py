"""
Email ingestor for Ariadne.

Handles EML and MBOX format email files.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Optional
from pathlib import Path
import logging
import email
from email.policy import default

logger = logging.getLogger(__name__)


class EmailIngestor(BaseIngestor):
    """
    Ingest email files (EML/MBOX).
    
    Extracts:
    - Subject
    - From/To/CC
    - Date
    - Body text (plain and HTML)
    - Attachments info (not content)
    
    Example:
        ingestor = EmailIngestor()
        docs = ingestor.ingest("email.eml")
    """
    
    source_type = SourceType.EMAIL
    
    def _extract(self, path: Path) -> List[str]:
        """Extract content from email file."""
        content = path.read_bytes()
        
        try:
            msg = email.message_from_bytes(content, policy=default)
        except Exception:
            # Try as string
            try:
                text_content = path.read_text(encoding='utf-8', errors='ignore')
                msg = email.message_from_string(text_content)
            except Exception as e:
                logger.warning(f"Failed to parse email: {e}")
                return [f"Email file: {path.name}"]
        
        blocks = []
        
        # Extract headers
        headers_block = self._extract_headers(msg)
        if headers_block:
            blocks.append(headers_block)
        
        # Extract body
        body_block = self._extract_body(msg)
        if body_block:
            blocks.append(body_block)
        
        # Extract attachments info
        attachments_block = self._extract_attachments(msg)
        if attachments_block:
            blocks.append(attachments_block)
        
        return blocks if blocks else [f"Email: {path.name}"]
    
    def _extract_headers(self, msg: email.message.Message) -> str:
        """Extract email headers."""
        parts = []
        
        # Subject
        subject = msg.get('Subject', '')
        if subject:
            # Decode email subject if encoded
            import email.header
            if isinstance(subject, email.header.Header):
                subject = str(subject)
            parts.append(f"[Subject] {subject}")
        
        # From
        from_addr = msg.get('From', '')
        if from_addr:
            parts.append(f"[From] {from_addr}")
        
        # To
        to_addr = msg.get('To', '')
        if to_addr:
            parts.append(f"[To] {to_addr}")
        
        # CC
        cc = msg.get('CC', '')
        if cc:
            parts.append(f"[CC] {cc}")
        
        # Date
        date = msg.get('Date', '')
        if date:
            parts.append(f"[Date] {date}")
        
        # Message ID
        msg_id = msg.get('Message-ID', '')
        if msg_id:
            parts.append(f"[Message-ID] {msg_id}")
        
        return '\n'.join(parts)
    
    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract email body text."""
        body_texts = []
        
        if msg.is_multipart():
            # Walk through all parts
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get_content_disposition()
                
                # Skip attachments
                if content_disposition == 'attachment':
                    continue
                
                if content_type == 'text/plain':
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        text = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body_texts.append(('plain', text))
                    except Exception:
                        pass
                
                elif content_type == 'text/html' and not body_texts:
                    # Use HTML if no plain text
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        html = part.get_payload(decode=True).decode(charset, errors='ignore')
                        # Strip HTML tags
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        text = soup.get_text(separator=' ', strip=True)
                        body_texts.append(('html', text))
                    except Exception:
                        pass
        else:
            # Single part message
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or 'utf-8'
            
            try:
                text = msg.get_payload(decode=True).decode(charset, errors='ignore')
                
                if content_type == 'text/html':
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(text, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                
                body_texts.append(('text', text))
            except Exception as e:
                logger.warning(f"Failed to decode body: {e}")
        
        # Combine body texts
        if body_texts:
            combined = ' '.join(text for _, text in body_texts)
            # Limit length and split into chunks
            chunks = self.chunk_text(combined, max_chars=500, overlap=50)
            return '\n'.join(f"[Body] {chunk}" for chunk in chunks)
        
        return ""
    
    def _extract_attachments(self, msg: email.message.Message) -> str:
        """Extract attachment information."""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = part.get_content_disposition()
                if content_disposition == 'attachment':
                    filename = part.get_filename()
                    content_type = part.get_content_type()
                    if filename:
                        attachments.append(f"{filename} ({content_type})")
        
        if attachments:
            return f"[Attachments] {', '.join(attachments)}"
        return ""


class MBOXIngestor(BaseIngestor):
    """
    Ingest MBOX format mailbox files.
    
    Processes multiple emails from a single MBOX file.
    
    Example:
        ingestor = MBOXIngestor()
        docs = ingestor.ingest(" mailbox")
    """
    
    source_type = SourceType.EMAIL
    
    def _extract(self, path: Path) -> List[str]:
        """Extract all emails from MBOX file."""
        try:
            import mailbox
        except ImportError:
            raise ImportError(
                "mailbox module is required for MBOX support. "
                "This is part of Python standard library on most systems."
            )
        
        blocks = []
        
        try:
            mbox = mailbox.mbox(str(path))
            
            for i, message in enumerate(mbox):
                subject = message.get('Subject', 'No Subject')
                from_addr = message.get('From', 'Unknown')
                date = message.get('Date', 'Unknown Date')
                
                # Create entry for this email
                email_block = [
                    f"[Email {i+1}]",
                    f"From: {from_addr}",
                    f"Subject: {subject}",
                    f"Date: {date}",
                ]
                
                # Extract body
                body = self._get_message_body(message)
                if body:
                    email_block.append(f"Content: {body[:500]}")
                
                blocks.append('\n'.join(email_block))
                
        except Exception as e:
            logger.warning(f"Failed to parse MBOX: {e}")
            return [f"MBOX file: {path.name}"]
        
        return blocks if blocks else ["Empty MBOX file"]
    
    def _get_message_body(self, message: email.message.Message) -> str:
        """Extract body from a message."""
        body = None
        
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == 'text/plain':
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body = part.get_payload(decode=True).decode(charset, errors='ignore')
                        break
                    except Exception:
                        pass
        else:
            charset = message.get_content_charset() or 'utf-8'
            try:
                body = message.get_payload(decode=True).decode(charset, errors='ignore')
            except Exception:
                pass
        
        if body:
            # Clean up whitespace
            import textwrap
            body = ' '.join(body.split())
        
        return body or ""
    
    def ingest(self, file_path: str) -> List["Document"]:
        """Ingest MBOX file with multiple emails."""
        # Import Document here to avoid circular import
        from ariadne.ingest.base import Document
        
        path = Path(file_path)
        blocks = self._extract(path)
        
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return [
            Document(
                content=block.strip(),
                source_type=self.source_type,
                source_path=str(path.absolute()),
                chunk_index=i,
                total_chunks=len(blocks),
                ingested_at=now_iso,
                metadata={
                    "file_name": path.name,
                    "file_ext": path.suffix,
                    "format": "mbox",
                },
            )
            for i, block in enumerate(blocks)
            if block.strip()
        ]
