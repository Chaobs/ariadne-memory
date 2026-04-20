"""
Binary Ingestor - Handles binary files by extracting metadata.

This ingestor processes binary files (executables, unknown formats, etc.)
by extracting useful metadata like filename, size, and file type information.
This allows users to find references to these files in their memory search.
"""

import os
from pathlib import Path
from typing import List
import mimetypes
import logging

from .base import BaseIngestor, Document, SourceType

logger = logging.getLogger(__name__)


class BinaryIngestor(BaseIngestor):
    """
    Ingestor for binary and unknown file types.

    Extracts metadata from binary files and stores as a document reference,
    allowing users to search for references to these files.
    """

    source_type = SourceType.BINARY

    # Supported binary extensions
    SUPPORTED_EXTENSIONS = [
        # Executables
        ".exe", ".dll", ".so", ".dylib", ".app", ".framework",
        # Data files
        ".bin", ".dat", ".pak", ".sav",
        # Disk images
        ".iso", ".img", ".dmg", ".vdi", ".vmdk",
        # Package managers
        ".msi", ".deb", ".rpm", ".appimage",
        # Mobile apps
        ".apk", ".xapk", ".ipa",
        # Other binaries
        ".class", ".pyc", ".pyo", ".o", ".obj", ".lib",
    ]

    @property
    def supported_extensions(self) -> List[str]:
        return self.SUPPORTED_EXTENSIONS

    def _extract(self, path: Path) -> List[str]:
        """
        Extract metadata from a binary file as text.

        Args:
            path: Path to the binary file

        Returns:
            List containing one metadata block
        """
        # Get file stats
        stat = path.stat()
        file_size = stat.st_size
        file_size_str = self._format_size(file_size)

        # Try to detect mime type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type is None:
            mime_type = self._detect_mime_type(path)

        # Build metadata text
        content = self._build_metadata_content(path, file_size_str, mime_type)
        return [content]

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def _detect_mime_type(self, path: Path) -> str:
        """Attempt to detect mime type based on file extension."""
        ext_mime_map = {
            ".exe": "application/x-msdownload",
            ".dll": "application/x-msdownload",
            ".apk": "application/vnd.android.package-archive",
            ".ipa": "application/x-itunes-ipa",
            ".iso": "application/x-iso9660-image",
            ".dmg": "application/x-apple-diskimage",
            ".msi": "application/x-msi",
        }
        return ext_mime_map.get(path.suffix.lower(), "application/octet-stream")

    def _build_metadata_content(self, path: Path, size_str: str, mime_type: str) -> str:
        """Build the metadata content for the document."""
        return f"""Binary File Reference
======================
File Name: {path.name}
Location: {path.parent}
Size: {size_str}
Type: {mime_type or 'Unknown binary'}
Extension: {path.suffix}

This is a binary file that cannot be directly indexed for content search.
Reference stored for finding related documents and context."""
