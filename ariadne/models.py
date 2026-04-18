"""
Core data models for Ariadne.

This module defines the foundational data structures:
- Document: Atomic unit of indexed knowledge
- Entity: Named entity extracted from documents (for knowledge graph, P3)
- Relation: Relationship between entities (for knowledge graph, P3)
"""

from .ingest.base import Document, SourceType

# Re-export Document for convenience
__all__ = ["Document", "SourceType"]
