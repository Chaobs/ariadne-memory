"""
Semantic chunker for intelligent document splitting.

Unlike fixed-length chunking, semantic chunking uses natural boundaries
(sentences, paragraphs, code blocks) to create more meaningful chunks
that preserve context and improve retrieval quality.
"""

from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for semantic chunking."""
    chunk_size: int = 500  # Target size in characters
    chunk_overlap: int = 50  # Overlap between chunks
    min_chunk_size: int = 100  # Minimum chunk size
    max_chunk_size: int = 1000  # Maximum chunk size
    split_on_sentences: bool = True  # Split on sentence boundaries
    split_on_paragraphs: bool = True  # Split on paragraph boundaries
    split_on_code_blocks: bool = True  # Keep code blocks together
    split_on_headers: bool = True  # Split on markdown headers


class SemanticChunker:
    """
    Intelligent text chunker that preserves semantic boundaries.
    
    Instead of blindly splitting by character count, this chunker:
    1. Identifies natural boundaries (sentences, paragraphs, code blocks)
    2. Groups content by semantic units
    3. Creates chunks that respect these boundaries
    4. Falls back to character-based splitting only when necessary
    
    Example:
        chunker = SemanticChunker(chunk_size=500)
        chunks = chunker.chunk("Long document text...")
    """
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        """
        Initialize the chunker.
        
        Args:
            config: Chunking configuration.
        """
        self.config = config or ChunkConfig()
    
    def chunk(self, text: str) -> List[str]:
        """
        Split text into semantically coherent chunks.
        
        Args:
            text: Text to chunk.
            
        Returns:
            List of text chunks.
        """
        if not text or not text.strip():
            return []
        
        # Handle short texts
        if len(text) <= self.config.chunk_size:
            return [text.strip()]
        
        # Extract and protect special blocks
        protected = self._protect_special_blocks(text)
        text = protected["text"]
        code_blocks = protected["code_blocks"]
        headers = protected["headers"]
        
        # Split into paragraphs
        paragraphs = self._split_paragraphs(text)
        
        # Build chunks
        chunks = self._build_chunks(paragraphs)
        
        # Restore special blocks (markers remain for reference)
        chunks = [self._restore_special_blocks(chunk, code_blocks, headers) for chunk in chunks]
        
        # Filter and clean
        chunks = [c.strip() for c in chunks if c.strip()]
        
        return chunks if chunks else [text[:self.config.max_chunk_size]]
    
    def _protect_special_blocks(self, text: str) -> dict:
        """Extract and protect special content like code blocks."""
        protected = {
            "text": text,
            "code_blocks": [],
            "headers": [],
        }
        
        # Protect code blocks
        code_pattern = r"(```[\s\S]*?```|`[^`]+`)"
        matches = list(re.finditer(code_pattern, text))
        for i, match in enumerate(matches):
            placeholder = f"__CODEBLOCK_{i}__"
            protected["code_blocks"].append(match.group(0))
            protected["text"] = protected["text"].replace(match.group(0), placeholder)
        
        # Protect headers
        header_pattern = r"(^#{1,6}\s+.+$)"
        matches = list(re.finditer(header_pattern, text, re.MULTILINE))
        for i, match in enumerate(matches):
            placeholder = f"__HEADER_{i}__"
            protected["headers"].append(match.group(0))
            protected["text"] = protected["text"].replace(match.group(0), placeholder)
        
        return protected
    
    def _restore_special_blocks(self, chunk: str, code_blocks: list, headers: list) -> str:
        """Restore special blocks into chunk."""
        for i, code in enumerate(code_blocks):
            chunk = chunk.replace(f"__CODEBLOCK_{i}__", code)
        for i, header in enumerate(headers):
            chunk = chunk.replace(f"__HEADER_{i}__", header)
        return chunk
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r"\n\s*\n", text)
        
        # Also split on single newlines for dense text
        result = []
        for para in paragraphs:
            if len(para) > 2000:  # Dense paragraph, split further
                lines = para.split("\n")
                current = []
                current_len = 0
                
                for line in lines:
                    if current_len + len(line) > 500 and current:
                        result.append("\n".join(current))
                        current = [line]
                        current_len = len(line)
                    else:
                        current.append(line)
                        current_len += len(line)
                
                if current:
                    result.append("\n".join(current))
            else:
                result.append(para)
        
        return [p.strip() for p in result if p.strip()]
    
    def _build_chunks(self, paragraphs: List[str]) -> List[str]:
        """Build chunks from paragraphs."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # If single paragraph exceeds max, split it
            if para_size > self.config.max_chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split long paragraph
                sub_chunks = self._split_long_paragraph(para)
                chunks.extend(sub_chunks)
                continue
            
            # Try to add to current chunk
            if current_size + para_size + 2 <= self.config.chunk_size:
                current_chunk.append(para)
                current_size += para_size + 2  # +2 for newline
            else:
                # Current chunk is full
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                
                # Start new chunk
                if para_size <= self.config.chunk_size:
                    current_chunk = [para]
                    current_size = para_size
                else:
                    # This paragraph is still too big, split it
                    sub_chunks = self._split_long_paragraph(para)
                    current_chunk = []
                    current_size = 0
                    
                    for sub in sub_chunks[:-1]:
                        chunks.append(sub)
                    if sub_chunks:
                        current_chunk = [sub_chunks[-1]]
                        current_size = len(sub_chunks[-1])
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        return chunks
    
    def _split_long_paragraph(self, text: str) -> List[str]:
        """Split a paragraph that's too long."""
        chunks = []
        
        # Try sentence splitting first
        if self.config.split_on_sentences:
            sentences = self._split_sentences(text)
        else:
            sentences = [text]
        
        current = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size <= self.config.chunk_size:
                current.append(sentence)
                current_size += sentence_size
            else:
                if current:
                    chunks.append(" ".join(current))
                
                if sentence_size > self.config.max_chunk_size:
                    # Very long sentence, character split
                    chunks.extend(self._character_split(sentence))
                    current = []
                    current_size = 0
                else:
                    current = [sentence]
                    current_size = sentence_size
        
        if current:
            chunks.append(" ".join(current))
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitter (handles common cases)
        # This is a simplified version; production code might use NLTK or spaCy
        
        # Pattern for sentence endings
        pattern = r'(?<=[.!?])\s+'
        sentences = re.split(pattern, text)
        
        # Merge very short sentences (likely abbreviations or fragments)
        merged = []
        current = ""
        
        for sent in sentences:
            if len(sent) < 10 and sent.endswith((".", "!")):
                current += " " + sent
            else:
                if current:
                    merged.append(current.strip())
                    current = ""
                merged.append(sent.strip())
        
        if current:
            merged.append(current.strip())
        
        return [s for s in merged if s]
    
    def _character_split(self, text: str) -> List[str]:
        """Fallback: split by character count."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.config.chunk_size
            chunks.append(text[start:end])
            start += self.config.chunk_size - self.config.chunk_overlap
        
        return chunks


class LLMSemanticChunker(SemanticChunker):
    """
    LLM-powered semantic chunker for higher quality splitting.
    
    Uses an LLM to identify natural semantic boundaries in text,
    producing higher quality chunks than the rule-based approach.
    
    This is more expensive but produces better results for complex documents.
    """
    
    CHUNK_PROMPT = """Analyze the following text and suggest natural break points for splitting it into chunks of approximately {target_size} characters.

Text:
{text}

Consider:
1. Paragraph boundaries
2. Section headers
3. Topic changes
4. Logical discourse units

Return break point suggestions as a JSON array of character positions:
{{"breaks": [position1, position2, ...]}}

Only return the JSON, nothing else."""

    def __init__(
        self,
        llm: "BaseLLM",
        config: Optional[ChunkConfig] = None,
        use_llm_threshold: int = 2000,  # Only use LLM for texts > this size
    ):
        """
        Initialize LLM-powered chunker.
        
        Args:
            llm: LLM instance for determining chunk boundaries.
            config: Chunking configuration.
            use_llm_threshold: Minimum text size to trigger LLM chunking.
        """
        super().__init__(config)
        self.llm = llm
        self.use_llm_threshold = use_llm_threshold
    
    def chunk(self, text: str) -> List[str]:
        """Chunk using LLM for large or complex texts."""
        if len(text) <= self.use_llm_threshold:
            return super().chunk(text)
        
        try:
            return self._llm_chunk(text)
        except Exception as e:
            logger.warning(f"LLM chunking failed: {e}, falling back to rule-based")
            return super().chunk(text)
    
    def _llm_chunk(self, text: str) -> List[str]:
        """Use LLM to determine chunk boundaries."""
        prompt = self.CHUNK_PROMPT.format(
            target_size=self.config.chunk_size,
            text=text[:5000],  # Limit text for LLM
        )
        
        response = self.llm.chat(prompt)
        
        # Parse break points from response
        import json
        try:
            # Try to extract JSON from response
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            breaks = data.get("breaks", [])
        except Exception:
            # Fallback: estimate evenly
            breaks = list(range(
                self.config.chunk_size,
                len(text),
                self.config.chunk_size
            ))
        
        # Extract chunks
        chunks = []
        start = 0
        
        for break_point in breaks:
            if break_point > start and break_point < len(text):
                # Find a good break point near this position
                actual_break = self._find_break_point(text, start, break_point)
                chunks.append(text[start:actual_break].strip())
                start = actual_break
        
        # Add remaining text
        if start < len(text):
            chunks.append(text[start:].strip())
        
        # Filter empty chunks
        chunks = [c for c in chunks if c]
        
        return chunks if chunks else super().chunk(text)
    
    def _find_break_point(self, text: str, start: int, target: int) -> int:
        """Find a natural break point near the target position."""
        # Look for paragraph break first
        for i in range(target, max(start + 100, target - 100), -1):
            if i < len(text) and text[i] == "\n":
                if i + 1 < len(text) and text[i + 1] == "\n":
                    return i + 2
        
        # Look for sentence end
        for i in range(target, max(start + 50, target - 200), -1):
            if i < len(text) and text[i] in ".!?":
                if i + 2 < len(text) and text[i + 1] == " " and text[i + 2].isupper():
                    return i + 1
        
        # Look for comma/semicolon (weaker break)
        for i in range(target, max(start + 50, target - 100), -1):
            if i < len(text) and text[i] in ",;:\n":
                return i + 1
        
        # Fallback: just use target
        return target
