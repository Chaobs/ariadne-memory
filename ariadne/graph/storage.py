"""
Knowledge Graph storage using NetworkX and SQLite.

Provides persistent storage for entities and relations,
with graph analysis capabilities via NetworkX.
"""

import networkx as nx
from typing import List, Optional, Dict, Set, Tuple, Any
from pathlib import Path
import sqlite3
import json
import logging

from ariadne.graph.models import Entity, Relation, EntityType, RelationType, GraphDocument

logger = logging.getLogger(__name__)


class GraphStorage:
    """
    Persistent knowledge graph storage.
    
    Combines:
    - NetworkX: Fast in-memory graph operations
    - SQLite: Durable persistence
    
    Example:
        storage = GraphStorage("data/graph.db")
        storage.add_entity(entity)
        storage.add_relation(relation)
        neighbors = storage.get_neighbors("entity_id")
    """
    
    def __init__(
        self,
        db_path: str = ".ariadne/knowledge_graph.db",
        load_existing: bool = True,
    ):
        """
        Initialize the graph storage.
        
        Args:
            db_path: Path to SQLite database file.
            load_existing: Whether to load existing graph on startup.
        """
        self.db_path = db_path
        self._ensure_db_dir()
        
        # In-memory graph for fast operations
        self.graph = nx.MultiDiGraph()
        
        # Entity and relation caches
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        
        # Initialize database
        self._init_db()
        
        if load_existing:
            self._load_from_db()
    
    def _ensure_db_dir(self) -> None:
        """Ensure the database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                aliases TEXT,
                description TEXT,
                properties TEXT,
                sources TEXT,
                confidence REAL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Relations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                relation_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                properties TEXT,
                description TEXT,
                sources TEXT,
                confidence REAL,
                bidirectional INTEGER,
                FOREIGN KEY (source_id) REFERENCES entities(entity_id),
                FOREIGN KEY (target_id) REFERENCES entities(entity_id)
            )
        """)
        
        # Graph documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_documents (
                doc_id TEXT PRIMARY KEY,
                summary TEXT,
                keywords TEXT,
                created_at TEXT
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id)")
        
        conn.commit()
        conn.close()
    
    def _load_from_db(self) -> None:
        """Load entities and relations from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Load entities
        cursor.execute("SELECT * FROM entities")
        for row in cursor.fetchall():
            entity = self._row_to_entity(row)
            self._entities[entity.entity_id] = entity
            self.graph.add_node(entity.entity_id, **entity.to_dict())
        
        # Load relations
        cursor.execute("SELECT * FROM relations")
        for row in cursor.fetchall():
            relation = self._row_to_relation(row)
            self._relations[relation.relation_id] = relation
            self.graph.add_edge(
                relation.source_id,
                relation.target_id,
                key=relation.relation_id,
                **relation.to_dict()
            )
        
        conn.close()
        logger.info(f"Loaded {len(self._entities)} entities and {len(self._relations)} relations")
    
    def _row_to_entity(self, row: tuple) -> Entity:
        """Convert a database row to an Entity."""
        return Entity(
            name=row[1],
            entity_type=EntityType(row[2]),
            aliases=json.loads(row[3]) if row[3] else [],
            description=row[4] or "",
            properties=json.loads(row[5]) if row[5] else {},
            sources=json.loads(row[6]) if row[6] else [],
            confidence=row[7],
            created_at=row[8],
            updated_at=row[9],
        )
    
    def _row_to_relation(self, row: tuple) -> Relation:
        """Convert a database row to a Relation."""
        return Relation(
            source_id=row[1],
            target_id=row[2],
            relation_type=RelationType(row[3]),
            properties=json.loads(row[4]) if row[4] else {},
            description=row[5] or "",
            sources=json.loads(row[6]) if row[6] else [],
            confidence=row[7],
            bidirectional=bool(row[8]),
        )
    
    # ==================== Entity Operations ====================
    
    def add_entity(self, entity: Entity) -> None:
        """
        Add an entity to the graph.
        
        If entity already exists (by name), merges them.
        """
        existing = self.get_entity_by_name(entity.name)
        
        if existing:
            existing.merge(entity)
            self._update_entity(existing)
        else:
            self._entities[entity.entity_id] = entity
            self.graph.add_node(entity.entity_id, **entity.to_dict())
            self._insert_entity(entity)
    
    def _insert_entity(self, entity: Entity) -> None:
        """Insert entity into database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.entity_id,
            entity.name,
            entity.entity_type.value,
            json.dumps(entity.aliases),
            entity.description,
            json.dumps(entity.properties),
            json.dumps(entity.sources),
            entity.confidence,
            entity.created_at,
            entity.updated_at,
        ))
        
        conn.commit()
        conn.close()
    
    def _update_entity(self, entity: Entity) -> None:
        """Update entity in database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE entities SET
                name = ?, type = ?, aliases = ?, description = ?,
                properties = ?, sources = ?, confidence = ?, updated_at = ?
            WHERE entity_id = ?
        """, (
            entity.name,
            entity.entity_type.value,
            json.dumps(entity.aliases),
            entity.description,
            json.dumps(entity.properties),
            json.dumps(entity.sources),
            entity.confidence,
            entity.updated_at,
            entity.entity_id,
        ))
        
        conn.commit()
        conn.close()
        
        # Update in-memory graph
        if entity.entity_id in self.graph:
            self.graph.nodes[entity.entity_id].update(entity.to_dict())
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        return self._entities.get(entity_id)
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Get an entity by name (exact or alias match)."""
        name_lower = name.lower().strip()
        
        for entity in self._entities.values():
            if entity.name.lower() == name_lower:
                return entity
            if name_lower in [a.lower() for a in entity.aliases]:
                return entity
        
        return None
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """Get all entities of a specific type."""
        return [e for e in self._entities.values() if e.entity_type == entity_type]
    
    def get_all_entities(self) -> List[Entity]:
        """Get all entities."""
        return list(self._entities.values())
    
    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity and all its relations."""
        if entity_id not in self._entities:
            return
        
        # Remove from graph
        self.graph.remove_node(entity_id)
        
        # Remove relations
        relations_to_remove = [
            r.relation_id for r in self._relations.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]
        for rid in relations_to_remove:
            self.remove_relation(rid)
        
        # Remove from database
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id,))
        conn.commit()
        conn.close()
        
        del self._entities[entity_id]
    
    # ==================== Relation Operations ====================
    
    def add_relation(self, relation: Relation) -> None:
        """
        Add a relation to the graph.
        
        Does not add duplicate relations.
        """
        if relation.relation_id in self._relations:
            return
        
        self._relations[relation.relation_id] = relation
        
        # Add to graph
        self.graph.add_edge(
            relation.source_id,
            relation.target_id,
            key=relation.relation_id,
            **relation.to_dict()
        )
        
        # Add to database
        self._insert_relation(relation)
    
    def _insert_relation(self, relation: Relation) -> None:
        """Insert relation into database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            relation.relation_id,
            relation.source_id,
            relation.target_id,
            relation.relation_type.value,
            json.dumps(relation.properties),
            relation.description,
            json.dumps(relation.sources),
            relation.confidence,
            1 if relation.bidirectional else 0,
        ))
        
        conn.commit()
        conn.close()
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """Get a relation by ID."""
        return self._relations.get(relation_id)
    
    def get_relations_between(self, source_id: str, target_id: str) -> List[Relation]:
        """Get all relations between two entities."""
        return [
            r for r in self._relations.values()
            if (r.source_id == source_id and r.target_id == target_id) or
               (r.bidirectional and r.source_id == target_id and r.target_id == source_id)
        ]
    
    def get_all_relations(self) -> List[Relation]:
        """Get all relations."""
        return list(self._relations.values())
    
    def remove_relation(self, relation_id: str) -> None:
        """Remove a relation from the graph."""
        if relation_id not in self._relations:
            return
        
        relation = self._relations[relation_id]
        
        # Remove from graph
        try:
            self.graph.remove_edge(relation.source_id, relation.target_id, key=relation_id)
        except nx.NetworkXError:
            pass
        
        # Remove from database
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM relations WHERE relation_id = ?", (relation_id,))
        conn.commit()
        conn.close()
        
        del self._relations[relation_id]
    
    # ==================== Graph Operations ====================
    
    def get_neighbors(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None,
    ) -> List[Tuple[Entity, Relation]]:
        """
        Get neighboring entities with their connecting relations.
        
        Args:
            entity_id: The entity to get neighbors for.
            relation_type: Optional filter by relation type.
            
        Returns:
            List of (Entity, Relation) tuples.
        """
        if entity_id not in self.graph:
            return []
        
        results = []
        
        for _, target_id, key, data in self.graph.out_edges(entity_id, data=True, keys=True):
            relation = self._relations.get(key)
            if relation:
                if relation_type is None or relation.relation_type == relation_type:
                    target_entity = self._entities.get(target_id)
                    if target_entity:
                        results.append((target_entity, relation))
        
        return results
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 5,
    ) -> Optional[List[str]]:
        """
        Find a path between two entities.
        
        Args:
            source_id: Starting entity ID.
            target_id: Target entity ID.
            max_length: Maximum path length.
            
        Returns:
            List of entity IDs forming the path, or None if no path exists.
        """
        try:
            return nx.shortest_path(self.graph, source_id, target_id, weight=None)
        except nx.NetworkXNoPath:
            return None
    
    def find_all_paths(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 3,
    ) -> List[List[str]]:
        """
        Find all paths between two entities.
        
        Args:
            source_id: Starting entity ID.
            target_id: Target entity ID.
            max_length: Maximum path length.
            
        Returns:
            List of paths, each path is a list of entity IDs.
        """
        try:
            return list(nx.all_simple_paths(self.graph, source_id, target_id, cutoff=max_length))
        except nx.NetworkXError:
            return []
    
    def get_connected_component(self, entity_id: str) -> List[Entity]:
        """
        Get all entities in the same connected component.
        
        Returns:
            List of entities.
        """
        if entity_id not in self.graph:
            return []
        
        nodes = nx.node_connected_component(self.graph.to_undirected(), entity_id)
        return [self._entities[n] for n in nodes if n in self._entities]
    
    def get_degree_centrality(self, top_k: int = 10) -> List[Tuple[Entity, float]]:
        """
        Get most connected entities by degree centrality.
        
        Returns:
            List of (Entity, centrality_score) tuples.
        """
        centrality = nx.degree_centrality(self.graph)
        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        return [
            (self._entities[n], score)
            for n, score in sorted_entities[:top_k]
            if n in self._entities
        ]
    
    def get_betweenness_centrality(self, top_k: int = 10) -> List[Tuple[Entity, float]]:
        """
        Get entities that bridge other entities (betweenness centrality).
        
        Returns:
            List of (Entity, centrality_score) tuples.
        """
        centrality = nx.betweenness_centrality(self.graph)
        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        return [
            (self._entities[n], score)
            for n, score in sorted_entities[:top_k]
            if n in self._entities
        ]
    
    # ==================== Batch Operations ====================
    
    def add_graph_document(self, graph_doc: GraphDocument) -> None:
        """
        Add a full graph document (entities + relations).
        
        Args:
            graph_doc: The enriched document to add.
        """
        # Add all entities
        for entity in graph_doc.entities:
            self.add_entity(entity)
        
        # Add all relations (after entities are added)
        for relation in graph_doc.relations:
            self.add_relation(relation)
    
    def merge_graph(self, other: "GraphStorage") -> None:
        """
        Merge another graph into this one.
        
        Useful for combining graphs from different sources.
        """
        for entity in other.get_all_entities():
            self.add_entity(entity)
        
        for relation in other.get_all_relations():
            self.add_relation(relation)
    
    # ==================== Statistics ====================
    
    def stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            "num_entities": len(self._entities),
            "num_relations": len(self._relations),
            "num_entity_types": len(set(e.entity_type for e in self._entities.values())),
            "num_relation_types": len(set(r.relation_type for r in self._relations.values())),
            "graph_density": nx.density(self.graph) if len(self._entities) > 1 else 0,
            "graph_connected": nx.is_connected(self.graph.to_undirected()) if len(self._entities) > 1 else True,
        }
    
    def __len__(self) -> int:
        """Number of entities in the graph."""
        return len(self._entities)
