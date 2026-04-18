"""
Knowledge Graph query interface.

Provides methods for querying the knowledge graph,
including cross-source queries and timeline views.
"""

from ariadne.graph.storage import GraphStorage
from ariadne.graph.models import Entity, Relation, EntityType, RelationType
from ariadne.memory.store import VectorStore
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class GraphQuery:
    """
    Query interface for the knowledge graph.
    
    Provides methods for:
    - Direct entity and relation queries
    - Cross-source queries (combining graph + vector search)
    - Timeline queries (temporal organization)
    
    Example:
        query = GraphQuery(graph_storage, vector_store)
        results = query.query("quantum mechanics")
        timeline = query.get_timeline(entity_id)
    """
    
    def __init__(
        self,
        graph: GraphStorage,
        vector_store: Optional[VectorStore] = None,
    ):
        """
        Initialize the query interface.
        
        Args:
            graph: The knowledge graph storage.
            vector_store: Optional vector store for hybrid queries.
        """
        self.graph = graph
        self.vector_store = vector_store
    
    # ==================== Direct Queries ====================
    
    def find_entity(self, name: str) -> Optional[Entity]:
        """Find an entity by name."""
        return self.graph.get_entity_by_name(name)
    
    def find_related(
        self,
        entity_name: str,
        relation_type: Optional[RelationType] = None,
        depth: int = 1,
    ) -> List[Tuple[Entity, Relation, int]]:
        """
        Find entities related to a given entity.
        
        Args:
            entity_name: Name of the source entity.
            relation_type: Optional filter by relation type.
            depth: How many hops to traverse (1 = direct neighbors only).
            
        Returns:
            List of (Entity, Relation, depth) tuples.
        """
        entity = self.find_entity(entity_name)
        if not entity:
            return []
        
        results = []
        visited: Set[str] = {entity.entity_id}
        
        def traverse(current_id: str, current_depth: int):
            if current_depth > depth:
                return
            
            for neighbor, relation in self.graph.get_neighbors(current_id, relation_type):
                if neighbor.entity_id not in visited:
                    visited.add(neighbor.entity_id)
                    results.append((neighbor, relation, current_depth))
                    traverse(neighbor.entity_id, current_depth + 1)
        
        traverse(entity.entity_id, 1)
        
        # Sort by depth, then by relevance
        results.sort(key=lambda x: (x[2], -x[1].confidence))
        
        return results
    
    def query_by_type(
        self,
        entity_type: EntityType,
        min_confidence: float = 0.0,
    ) -> List[Entity]:
        """
        Query all entities of a specific type.
        
        Args:
            entity_type: The type to filter by.
            min_confidence: Minimum confidence threshold.
            
        Returns:
            List of matching entities.
        """
        entities = self.graph.get_entities_by_type(entity_type)
        return [e for e in entities if e.confidence >= min_confidence]
    
    def query_relations(
        self,
        source_name: Optional[str] = None,
        target_name: Optional[str] = None,
        relation_type: Optional[RelationType] = None,
    ) -> List[Relation]:
        """
        Query relations by various filters.
        
        Args:
            source_name: Filter by source entity name.
            target_name: Filter by target entity name.
            relation_type: Filter by relation type.
            
        Returns:
            List of matching relations.
        """
        relations = self.graph.get_all_relations()
        results = []
        
        for rel in relations:
            if relation_type and rel.relation_type != relation_type:
                continue
            
            if source_name:
                source = self.graph.get_entity(rel.source_id)
                if not source or source.name.lower() != source_name.lower():
                    continue
            
            if target_name:
                target = self.graph.get_entity(rel.target_id)
                if not target or target.name.lower() != target_name.lower():
                    continue
            
            results.append(rel)
        
        return results
    
    # ==================== Cross-Source Queries ====================
    
    def hybrid_query(
        self,
        query: str,
        entity_filter: Optional[EntityType] = None,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Hybrid query combining vector search and graph traversal.
        
        Args:
            query: Natural language query.
            entity_filter: Optional entity type filter.
            top_k: Number of results to return.
            
        Returns:
            Dict with 'vector_results' and 'graph_insights'.
        """
        results = {
            "query": query,
            "vector_results": [],
            "graph_insights": {
                "related_entities": [],
                "path_analysis": {},
            },
        }
        
        # Vector search
        if self.vector_store:
            try:
                vector_results = self.vector_store.search(query, top_k=top_k * 2)
                results["vector_results"] = [
                    {"content": doc.content[:200], "score": score, "source": doc.source_path}
                    for doc, score in vector_results
                ]
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # Extract entity names from query for graph analysis
        query_entities = self._extract_entity_hints(query)
        
        for entity_name in query_entities:
            entity = self.find_entity(entity_name)
            if entity:
                if entity_filter and entity.entity_type != entity_filter:
                    continue
                
                # Get related entities
                related = self.find_related(entity_name, depth=2)
                results["graph_insights"]["related_entities"].extend([
                    {
                        "name": e.name,
                        "type": e.entity_type.value,
                        "relation": r.relation_type.value,
                        "depth": d,
                    }
                    for e, r, d in related[:5]
                ])
                
                # Find paths to other query entities
                for other_name in query_entities:
                    if other_name != entity_name:
                        other = self.find_entity(other_name)
                        if other:
                            path = self.graph.find_path(entity.entity_id, other.entity_id)
                            if path:
                                path_entities = [
                                    self.graph.get_entity(pid).name
                                    for pid in path if self.graph.get_entity(pid)
                                ]
                                results["graph_insights"]["path_analysis"][
                                    f"{entity_name} -> {other_name}"
                                ] = path_entities
        
        return results
    
    def _extract_entity_hints(self, query: str) -> List[str]:
        """Extract potential entity names from a query."""
        # Simple extraction: capitalized words
        import re
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        return list(set(words))
    
    # ==================== Timeline Queries ====================
    
    def get_timeline(
        self,
        entity_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get events/entities organized by timeline.
        
        Args:
            entity_id: Optional specific entity (shows its history).
            start_date: ISO date string for range start.
            end_date: ISO date string for range end.
            
        Returns:
            List of timeline entries with dates and descriptions.
        """
        timeline = []
        
        # Get entities with dates in properties
        for entity in self.graph.get_all_entities():
            if entity_id and entity.entity_id != entity_id:
                continue
            
            # Check for date properties
            date_str = entity.properties.get("date") or entity.properties.get("created")
            
            if date_str:
                timeline.append({
                    "type": "entity",
                    "date": date_str,
                    "entity_name": entity.name,
                    "entity_id": entity.entity_id,
                    "description": entity.description or f"{entity.entity_type.value} entity",
                    "sources": entity.sources,
                })
            
            # Check for temporal relations
            for neighbor, relation in self.graph.get_neighbors(entity.entity_id):
                if relation.relation_type in {
                    RelationType.OCCURRED_BEFORE,
                    RelationType.OCCURRED_AFTER,
                    RelationType.CONTEMPORARY,
                }:
                    timeline.append({
                        "type": "relation",
                        "date": relation.properties.get("date", ""),
                        "relation": relation.relation_type.value,
                        "source": entity.name,
                        "target": neighbor.name,
                        "description": relation.description,
                        "sources": relation.sources,
                    })
        
        # Sort by date
        timeline.sort(key=lambda x: x.get("date", ""))
        
        # Filter by date range
        if start_date:
            timeline = [t for t in timeline if t.get("date", "") >= start_date]
        if end_date:
            timeline = [t for t in timeline if t.get("date", "") <= end_date]
        
        return timeline
    
    def get_entity_history(self, entity_name: str) -> Dict[str, Any]:
        """
        Get the history of an entity (sources where it appears).
        
        Args:
            entity_name: Name of the entity.
            
        Returns:
            Dict with entity info and its history.
        """
        entity = self.find_entity(entity_name)
        if not entity:
            return {}
        
        # Get sources ordered by date
        sources_with_dates = []
        for source in entity.sources:
            sources_with_dates.append({
                "source": source,
                "first_mentioned": entity.created_at,
                "last_updated": entity.updated_at,
            })
        
        return {
            "entity": entity.to_dict(),
            "history": sources_with_dates,
            "stats": {
                "num_sources": len(entity.sources),
                "num_relations": len(self.graph.get_neighbors(entity.entity_id)),
            },
        }
    
    # ==================== Analysis Queries ====================
    
    def get_central_entities(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most central/important entities.
        
        Based on degree centrality (number of connections).
        
        Returns:
            List of dicts with entity info and centrality score.
        """
        centrality = self.graph.get_degree_centrality(top_k)
        
        return [
            {
                "name": entity.name,
                "type": entity.entity_type.value,
                "centrality": score,
                "num_connections": len(self.graph.get_neighbors(entity.entity_id)),
            }
            for entity, score in centrality
        ]
    
    def get_communities(self) -> List[List[Entity]]:
        """
        Detect communities (clusters) in the knowledge graph.
        
        Uses the Louvain method for community detection.
        
        Returns:
            List of entity clusters.
        """
        import networkx as nx
        
        # Convert to undirected graph for community detection
        undirected = self.graph.graph.to_undirected()
        
        try:
            # Use Louvain community detection
            import community as community_louvain
            partition = community_louvain.best_partition(undirected)
        except ImportError:
            # Fallback: connected components
            components = list(nx.connected_components(undirected))
            return [
                [self.graph.get_entity(n) for n in comp if self.graph.get_entity(n)]
                for comp in components
            ]
        
        # Group entities by community
        communities: Dict[int, List[str]] = {}
        for node, comm_id in partition.items():
            if comm_id not in communities:
                communities[comm_id] = []
            communities[comm_id].append(node)
        
        return [
            [self.graph.get_entity(n) for n in nodes if self.graph.get_entity(n)]
            for nodes in communities.values()
        ]
    
    def find_bridge_entities(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find entities that bridge different topic areas.
        
        These are entities with high betweenness centrality.
        
        Returns:
            List of bridge entities with their scores.
        """
        betweenness = self.graph.get_betweenness_centrality(top_k * 2)
        
        return [
            {
                "name": entity.name,
                "type": entity.entity_type.value,
                "betweenness": score,
                "connections": [
                    {
                        "name": self.graph.get_entity(pid).name if self.graph.get_entity(pid) else pid,
                        "relation": rel.relation_type.value,
                    }
                    for _, rel, _ in self.find_related(entity.name, depth=1)[:3]
                ],
            }
            for entity, score in betweenness[:top_k]
        ]
