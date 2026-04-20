"""
Image and OCR ingestors for Ariadne.

Extracts metadata and text from images using OCR.
"""

from ariadne.ingest.base import BaseIngestor, SourceType
from typing import List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ImageIngestor(BaseIngestor):
    """
    Ingest image files and extract metadata.
    
    Extracts:
    - EXIF metadata (camera, date, location, etc.)
    - File metadata (size, dimensions)
    - Optional OCR text extraction
    
    Requires: Pillow (PIL) for metadata
    
    Example:
        ingestor = ImageIngestor()
        docs = ingestor.ingest("photo.jpg")
    """
    
    source_type = SourceType.IMAGE
    
    def _extract(self, path: Path) -> List[str]:
        """Extract metadata from image file."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
        except ImportError:
            raise ImportError(
                "Pillow is required for image support. "
                "Install it with: pip install Pillow"
            )
        
        blocks = []
        metadata = {}
        
        try:
            with Image.open(path) as img:
                # Basic info
                metadata['format'] = img.format
                metadata['mode'] = img.mode
                metadata['size'] = f"{img.width}x{img.height}"
                
                # EXIF data
                try:
                    exif = img._getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            metadata[f'exif_{tag}'] = str(value)[:200]
                except Exception:
                    pass
                
                # Properties
                if hasattr(img, 'info'):
                    for key, value in img.info.items():
                        if isinstance(value, (str, int, float)):
                            metadata[f'info_{key}'] = str(value)[:200]
                
        except Exception as e:
            logger.warning(f"Failed to read image metadata: {e}")
            return [f"Image file: {path.name}"]
        
        # Format metadata as text blocks
        if metadata:
            # Group by category
            exif_data = {k: v for k, v in metadata.items() if k.startswith('exif_')}
            basic_info = {k: v for k, v in metadata.items() if not k.startswith('exif_')}
            
            if basic_info:
                blocks.append(f"[Image Info] {', '.join(f'{k}: {v}' for k, v in basic_info.items())}")
            
            if exif_data:
                blocks.append(f"[EXIF] {', '.join(f'{k}: {v}' for k, v in list(exif_data.items())[:10])}")
        
        # Add filename as content
        blocks.append(f"Image file: {path.name}")
        
        return blocks


class OCRIngestor(BaseIngestor):
    """
    OCR ingestor for scanned PDFs and images.
    
    Extracts text from:
    - Scanned PDF documents
    - Images with text (screenshots, photos)
    
    Requires: pytesseract or RapidOCR
    
    Example:
        ingestor = OCRIngestor()
        docs = ingestor.ingest("scanned.pdf")
    """
    
    source_type = SourceType.OCR
    
    def __init__(self, use_rapidocr: bool = True, lang: str = 'eng+chi_sim'):
        """
        Initialize OCR ingestor.
        
        Args:
            use_rapidocr: Use RapidOCR if True (better for mixed languages), 
                         fallback to Tesseract if False.
            lang: Language code for OCR (e.g., 'eng', 'eng+chi_sim').
        """
        self.use_rapidocr = use_rapidocr
        self.lang = lang
    
    def _extract(self, path: Path) -> List[str]:
        """Extract text from image/PDF using OCR."""
        text_blocks = []
        
        if self.use_rapidocr:
            text = self._extract_rapidocr(path)
        else:
            text = self._extract_tesseract(path)
        
        if text:
            # Split long text into manageable chunks
            text_blocks = self.chunk_text(text, max_chars=500, overlap=50)
        
        if not text_blocks:
            text_blocks = [f"No text extracted from: {path.name}"]
        
        return text_blocks
    
    def _extract_rapidocr(self, path: Path) -> str:
        """Use RapidOCR for text extraction."""
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
            
            result, elapse = ocr(str(path))
            
            if result:
                lines = []
                for line in result:
                    # line format: [box, text, score]
                    text = line[1]
                    lines.append(text)
                return '\n'.join(lines)
            
            return ""
            
        except ImportError:
            logger.warning("RapidOCR not installed, falling back to Tesseract")
            self.use_rapidocr = False
            return self._extract_tesseract(path)
        except Exception as e:
            logger.warning(f"RapidOCR failed: {e}")
            self.use_rapidocr = False
            return self._extract_tesseract(path)
    
    def _extract_tesseract(self, path: Path) -> str:
        """Use Tesseract for text extraction."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "pytesseract and Pillow are required for OCR support. "
                "Install with: pip install pytesseract Pillow"
            )
        
        try:
            # Handle PDF
            if path.suffix.lower() == '.pdf':
                import fitz  # PyMuPDF
                doc = fitz.open(path)
                text_parts = []
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Render page as image
                    pix = page.get_pixmap(dpi=300)
                    img_data = pix.tobytes("png")
                    
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(img_data))
                    
                    text = pytesseract.image_to_string(img, lang=self.lang)
                    text_parts.append(f"[Page {page_num + 1}]\n{text}")
                
                doc.close()
                return '\n\n'.join(text_parts)
            else:
                # Handle image
                img = Image.open(path)
                return pytesseract.image_to_string(img, lang=self.lang)
                
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return ""
