"""
Mind map ingestor for Ariadne.

Extracts structured content from .mm (FreeMind) and .xmind files,
preserving the hierarchical tree structure as nested text.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict

from ariadne.ingest.base import BaseIngestor, SourceType


class MindMapIngestor(BaseIngestor):
    """
    Ingest mind map files (.mm FreeMind, .xmind).

    Extracts the hierarchical tree structure as nested text chunks.
    Each node becomes a chunk with its ancestors as context,
    so search results include the structural path.
    """

    source_type = SourceType.MINDMAP

    def _extract(self, path: Path) -> List[str]:
        suffix = path.suffix.lower()

        if suffix == ".mm":
            return self._extract_freemind(path)
        elif suffix == ".xmind":
            return self._extract_xmind(path)
        else:
            raise ValueError(f"Unsupported mind map format: {suffix}")

    def _extract_freemind(self, path: Path) -> List[str]:
        """Parse FreeMind .mm XML format."""
        tree = ET.parse(str(path))
        root = tree.getroot()

        # Build parent map for O(1) ancestor lookups
        parent_map: Dict[ET.Element, ET.Element] = {child: root for child in root.iter()}

        chunks = []
        for node in root.iter("node"):
            text = node.get("TEXT", "").strip()
            if not text:
                continue

            # Build path from root to this node
            path_parts = self._get_node_ancestors(node, parent_map)
            path_parts.append(text)
            chunks.append(" > ".join(path_parts))

        return chunks if chunks else []

    def _extract_xmind(self, path: Path) -> List[str]:
        """Parse XMind .xmind XML format (zip-based, extract and parse)."""
        import zipfile

        try:
            with zipfile.ZipFile(str(path), "r") as zf:
                # XMind stores content in content.json or content.xml
                content_xml = None
                for name in zf.namelist():
                    if "content.json" in name or "content.xml" in name:
                        content_xml = zf.read(name)
                        break

                if content_xml is None:
                    return []

                root = ET.fromstring(content_xml)
                chunks = []
                for elem in root.iter():
                    text = (elem.text or "").strip()
                    if text and len(text) > 2:
                        chunks.append(text)
                return chunks
        except Exception:
            return []

    def _get_node_ancestors(
        self, node: ET.Element, parent_map: Dict[ET.Element, ET.Element]
    ) -> List[str]:
        """Walk up the tree using the parent_map to build the ancestor path."""
        parts = []
        current = node
        while True:
            parent = parent_map.get(current)
            if parent is None or parent == parent_map.get(parent_map.get(parent)):
                break
            parent_text = (parent.get("TEXT") or "").strip()
            if parent_text:
                parts.insert(0, parent_text)
            if parent == node:  # reached root
                break
            current = parent
        return parts
