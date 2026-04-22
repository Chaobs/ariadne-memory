"""
Knowledge Graph core models for Ariadne.

Provides Entity, Relation, and GraphDocument data structures
for representing and storing structured knowledge.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Set
from pathlib import Path
import hashlib
import json


class EntityType(Enum):
    """Types of entities that can be extracted."""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    CONCEPT = "concept"
    WORK = "work"  # Creative works (books, papers, artworks)
    TOPIC = "topic"  # General topics/themes
    UNKNOWN = "unknown"


class RelationType(Enum):
    """Types of relations between entities."""
    # Semantic relations
    RELATED_TO = "related_to"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    INSTANCE_OF = "instance_of"
    
    # Hierarchical relations
    IS_A = "is_a"
    HAS_A = "has_a"
    BELONGS_TO = "belongs_to"
    
    # Temporal relations
    OCCURRED_BEFORE = "occurred_before"
    OCCURRED_AFTER = "occurred_after"
    CONTEMPORARY = "contemporary"
    
    # Causal relations
    CAUSES = "causes"
    ENABLES = "enables"
    PREVENTS = "prevents"
    
    # Action relations
    CREATED_BY = "created_by"
    LOCATED_IN = "located_in"
    PARTICIPATED_IN = "participated_in"
    
    # Knowledge relations (LLM-extracted)
    DEFINES = "defines"
    EXPLAINED_AS = "explained_as"
    CITES = "cites"
    REFERENCES = "references"
    DISCUSSES = "discusses"


@dataclass
class Entity:
    """
    A named entity extracted from documents.

    Attributes:
        name: The canonical name of the entity.
        entity_type: Type classification (Person, Organization, etc.)
        aliases: Alternative names or references to this entity.
        description: Brief description of the entity.
        properties: Additional key-value properties.
        sources: Document paths where this entity was found.
        confidence: Extraction confidence score (0.0-1.0).
        created_at: When the entity was first created.
        updated_at: When the entity was last updated.
        valid_from: Start of validity period (ISO timestamp, None = unknown)
        valid_to: End of validity period (ISO timestamp, None = current)
        temporal: Whether this entity has temporal constraints
    """
    name: str
    entity_type: EntityType = EntityType.UNKNOWN
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid_from: Optional[str] = None  # Temporal: when this fact becomes valid
    valid_to: Optional[str] = None    # Temporal: when this fact stops being valid
    temporal: bool = False            # Whether entity has temporal validity
    
    @property
    def entity_id(self) -> str:
        """Generate a stable unique ID for this entity."""
        raw = f"entity:{self.name.lower().strip()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    
    def add_source(self, source: str) -> None:
        """Add a source document to this entity."""
        if source not in self.sources:
            self.sources.append(source)
            self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def merge(self, other: "Entity") -> None:
        """
        Merge another entity into this one.
        
        Used when the same entity is extracted from multiple sources.
        """
        # Merge aliases
        for alias in other.aliases:
            if alias not in self.aliases:
                self.aliases.append(alias)
        
        # Merge sources
        for source in other.sources:
            if source not in self.sources:
                self.sources.append(source)
        
        # Update description if the other has more detail
        if other.description and len(other.description) > len(self.description):
            self.description = other.description
        
        # Merge properties
        for key, value in other.properties.items():
            if key not in self.properties:
                self.properties[key] = value
        
        # Update type if confidence is higher
        if other.confidence > self.confidence:
            self.entity_type = other.entity_type
            self.confidence = other.confidence
        
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.entity_id,
            "name": self.name,
            "type": self.entity_type.value,
            "aliases": self.aliases,
            "description": self.description,
            "properties": self.properties,
            "sources": self.sources,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "temporal": self.temporal,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create an entity from a dictionary."""
        return cls(
            name=data["name"],
            entity_type=EntityType(data.get("type", "unknown")),
            aliases=data.get("aliases", []),
            description=data.get("description", ""),
            properties=data.get("properties", {}),
            sources=data.get("sources", []),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            valid_from=data.get("valid_from"),
            valid_to=data.get("valid_to"),
            temporal=data.get("temporal", False),
        )

    def is_valid_at(self, timestamp: str) -> bool:
        """
        Check if this entity is valid at a given timestamp.

        Args:
            timestamp: ISO timestamp to check

        Returns:
            True if entity is valid at the given time
        """
        if not self.temporal:
            return True  # Non-temporal entities are always valid

        from datetime import datetime
        check_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        if self.valid_from:
            from_time = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
            if check_time < from_time:
                return False

        if self.valid_to:
            to_time = datetime.fromisoformat(self.valid_to.replace("Z", "+00:00"))
            if check_time > to_time:
                return False

        return True

    def set_validity_period(
        self,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> None:
        """Set the validity period for this entity."""
        if valid_from or valid_to:
            self.temporal = True
            self.valid_from = valid_from
            self.valid_to = valid_to
            self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class Relation:
    """
    A relationship between two entities.

    Attributes:
        source_id: ID of the source entity.
        target_id: ID of the target entity.
        relation_type: Type of relationship.
        properties: Additional properties (weight, evidence, etc.)
        description: Human-readable description of the relation.
        sources: Document paths supporting this relation.
        confidence: Extraction confidence score (0.0-1.0).
        bidirectional: Whether the relation works both ways.
        valid_from: Start of validity period (ISO timestamp)
        valid_to: End of validity period (ISO timestamp)
        temporal: Whether this relation has temporal constraints
    """
    source_id: str
    target_id: str
    relation_type: RelationType = RelationType.RELATED_TO
    properties: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0
    bidirectional: bool = False
    valid_from: Optional[str] = None  # Temporal: when this relation becomes valid
    valid_to: Optional[str] = None   # Temporal: when this relation stops being valid
    temporal: bool = False            # Whether relation has temporal validity
    
    @property
    def relation_id(self) -> str:
        """Generate a stable unique ID for this relation."""
        # Ensure consistent ordering for undirected relations
        ids = sorted([self.source_id, self.target_id])
        raw = f"relation:{ids[0]}:{self.relation_type.value}:{ids[1]}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    
    def add_source(self, source: str) -> None:
        """Add a supporting source document."""
        if source not in self.sources:
            self.sources.append(source)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relation_type.value,
            "properties": self.properties,
            "description": self.description,
            "sources": self.sources,
            "confidence": self.confidence,
            "bidirectional": self.bidirectional,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "temporal": self.temporal,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        """Create a relation from a dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=RelationType(data.get("type", "related_to")),
            properties=data.get("properties", {}),
            description=data.get("description", ""),
            sources=data.get("sources", []),
            confidence=data.get("confidence", 1.0),
            bidirectional=data.get("bidirectional", False),
            valid_from=data.get("valid_from"),
            valid_to=data.get("valid_to"),
            temporal=data.get("temporal", False),
        )

    def is_valid_at(self, timestamp: str) -> bool:
        """
        Check if this relation is valid at a given timestamp.

        Args:
            timestamp: ISO timestamp to check

        Returns:
            True if relation is valid at the given time
        """
        if not self.temporal:
            return True

        from datetime import datetime
        check_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        if self.valid_from:
            from_time = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
            if check_time < from_time:
                return False

        if self.valid_to:
            to_time = datetime.fromisoformat(self.valid_to.replace("Z", "+00:00"))
            if check_time > to_time:
                return False

        return True

    def set_validity_period(
        self,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> None:
        """Set the validity period for this relation."""
        if valid_from or valid_to:
            self.temporal = True
            self.valid_from = valid_from
            self.valid_to = valid_to


@dataclass
class GraphDocument:
    """
    A document enriched with extracted entities and relations.
    
    This wraps the original Document with knowledge graph data,
    enabling both vector search and graph traversal.
    
    Attributes:
        doc_id: ID of the original document.
        entities: Entities extracted from this document.
        relations: Relations extracted from this document.
        summary: Optional LLM-generated summary.
        keywords: Extracted keywords/topics.
    """
    doc_id: str
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Find an entity by name or alias."""
        name_lower = name.lower().strip()
        
        for entity in self.entities:
            if entity.name.lower() == name_lower:
                return entity
            if name_lower in [a.lower() for a in entity.aliases]:
                return entity
        
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "doc_id": self.doc_id,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "summary": self.summary,
            "keywords": self.keywords,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GraphDocument":
        """Create a graph document from a dictionary."""
        return cls(
            doc_id=data["doc_id"],
            entities=[Entity.from_dict(e) for e in data.get("entities", [])],
            relations=[Relation.from_dict(r) for r in data.get("relations", [])],
            summary=data.get("summary", ""),
            keywords=data.get("keywords", []),
        )
