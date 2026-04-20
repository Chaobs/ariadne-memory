"""
MCP Tool implementations for Ariadne.

Tools provide executable operations on the knowledge base.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
import json
import logging

from .server import MCPTool

logger = logging.getLogger(__name__)


@dataclass
class IngestTool(MCPTool):
    """Tool for ingesting documents into Ariadne."""

    def __init__(self, vector_store=None, graph_storage=None):
        super().__init__(
            name="ariadne_ingest",
            description="Ingest a document or URL into Ariadne's knowledge base. Supports various file formats including PDF, Word, Markdown, EPUB, images, and web URLs.",
            input_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "File path or URL to ingest",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name to store in (default: 'default')",
                        "default": "default",
                    },
                    "extract_entities": {
                        "type": "boolean",
                        "description": "Extract entities for knowledge graph (default: true)",
                        "default": True,
                    },
                },
                "required": ["source"],
            },
        )
        self._vector_store = vector_store
        self._graph_storage = graph_storage

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the ingest tool."""
        source = arguments.get("source")
        collection = arguments.get("collection", "default")
        extract_entities = arguments.get("extract_entities", True)

        if not source:
            return {"error": "Source is required"}

        try:
            from ariadne.ingest import get_ingestor
            from ariadne.memory import VectorStore

            ingestor = get_ingestor(source)
            documents = ingestor.ingest(source)

            vector_store = VectorStore(persist_dir=str(self._vector_store)) if self._vector_store else VectorStore()
            if documents:
                vector_store.add(documents)

            result = {
                "source": source,
                "documents_ingested": len(documents),
                "collection": collection,
                "chunks": sum(d.total_chunks for d in documents),
            }

            if extract_entities and self._graph_storage:
                try:
                    from ariadne.graph import GraphEnricher
                    enricher = GraphEnricher(llm=None)
                    for doc in documents:
                        graph_doc = enricher.extract_from_text(doc.get("content", ""))
                        for entity in graph_doc.entities:
                            self._graph_storage.add_entity(entity)
                        for relation in graph_doc.relations:
                            self._graph_storage.add_relation(relation)
                    result["entities_extracted"] = len(graph_doc.entities)
                except Exception as e:
                    logger.warning(f"Entity extraction skipped: {e}")

            return result

        except Exception as e:
            logger.error(f"Ingest error: {e}")
            return {"error": str(e), "documents_ingested": 0}


@dataclass
class SearchTool(MCPTool):
    """Tool for searching Ariadne's knowledge base."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_search",
            description="Search Ariadne's vector knowledge base. Returns relevant documents based on semantic similarity to the query.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5, max: 50)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name to search in (default: 'default')",
                        "default": "default",
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum relevance score threshold (0-1)",
                        "default": 0.0,
                    },
                },
                "required": ["query"],
            },
        )
        self._vector_store = vector_store

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the search tool."""
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        collection = arguments.get("collection", "default")
        min_score = arguments.get("min_score", 0.0)

        if not query:
            return {"error": "Query is required", "results": []}

        if not self._vector_store:
            return {"error": "Vector store not available", "results": []}

        try:
            from ariadne.memory import VectorStore
            vector_store = VectorStore(persist_dir=str(self._vector_store)) if self._vector_store else VectorStore()
            results = vector_store.search(query, top_k=limit)

            filtered = [
                {
                    "content": doc.content[:1000],
                    "source": doc.source_path,
                    "score": float(score),
                    "metadata": doc.metadata,
                }
                for doc, score in results
                if float(score) >= min_score
            ]

            return {
                "query": query,
                "count": len(filtered),
                "results": filtered,
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"error": str(e), "results": []}


@dataclass
class GraphQueryTool(MCPTool):
    """Tool for querying the knowledge graph."""

    def __init__(self, graph_storage=None):
        super().__init__(
            name="ariadne_graph_query",
            description="Query the knowledge graph to find entity relationships and connections. Useful for exploring how concepts are related.",
            input_schema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name or ID to query",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Filter by relation type (e.g., 'related_to', 'part_of')",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Traversal depth for finding connections (default: 2, max: 5)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "direction": {
                        "type": "string",
                        "description": "Relation direction: 'outgoing', 'incoming', or 'both'",
                        "enum": ["outgoing", "incoming", "both"],
                        "default": "both",
                    },
                },
                "required": ["entity"],
            },
        )
        self._graph_storage = graph_storage

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the graph query tool."""
        entity = arguments.get("entity", "")
        relation_type = arguments.get("relation_type")
        depth = arguments.get("depth", 2)
        direction = arguments.get("direction", "both")

        if not entity:
            return {"error": "Entity is required", "entities": [], "relations": []}

        if not self._graph_storage:
            return {"error": "Graph storage not available", "entities": [], "relations": []}

        try:
            from ariadne.graph import GraphStorage
            graph_storage = GraphStorage(str(self._graph_storage))

            found = graph_storage.get_entity_by_name(entity)
            if not found:
                return {"error": f"Entity not found: {entity}", "entities": [], "relations": []}

            relations = graph_storage.get_relations(
                found.entity_id,
                max_depth=depth,
                relation_type=relation_type,
                direction=direction,
            )

            entities = []
            seen = {found.entity_id}
            for r in relations:
                target_id = getattr(r, "target_id", None) or getattr(r, "source_id", None)
                if target_id and target_id not in seen:
                    target = graph_storage.get_entity(target_id)
                    if target:
                        entities.append({
                            "id": target.entity_id,
                            "name": target.name,
                            "type": target.entity_type.value if hasattr(target, "entity_type") else "",
                            "description": target.description[:200] if hasattr(target, "description") else "",
                        })
                        seen.add(target_id)

            return {
                "query_entity": entity,
                "depth": depth,
                "center_entity": {
                    "id": found.entity_id,
                    "name": found.name,
                    "type": found.entity_type.value if hasattr(found, "entity_type") else "",
                },
                "related_entities": entities,
                "relations": [
                    {
                        "type": str(getattr(r, "relation_type", "")),
                        "description": getattr(r, "description", ""),
                    }
                    for r in relations
                ],
            }

        except Exception as e:
            logger.error(f"Graph query error: {e}")
            return {"error": str(e), "entities": [], "relations": []}


@dataclass
class StatsTool(MCPTool):
    """Tool for getting knowledge base statistics."""

    def __init__(self, vector_store=None, graph_storage=None):
        super().__init__(
            name="ariadne_stats",
            description="Get statistics about the Ariadne knowledge base including document counts, entity counts, and storage information.",
            input_schema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name (default: 'default')",
                        "default": "default",
                    },
                    "detailed": {
                        "type": "boolean",
                        "description": "Include detailed breakdown by source type",
                        "default": False,
                    },
                },
            },
        )
        self._vector_store = vector_store
        self._graph_storage = graph_storage

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the stats tool."""
        collection = arguments.get("collection", "default")
        detailed = arguments.get("detailed", False)

        stats = {
            "collection": collection,
            "timestamp": self._get_timestamp(),
        }

        if self._vector_store:
            try:
                from ariadne.memory import VectorStore
                vector_store = VectorStore(persist_dir=str(self._vector_store))
                stats["document_count"] = vector_store.count()
            except Exception as e:
                logger.warning(f"Could not get vector stats: {e}")
                stats["document_count"] = 0

        if self._graph_storage:
            try:
                from ariadne.graph import GraphStorage
                graph_storage = GraphStorage(str(self._graph_storage))
                stats["entity_count"] = len(graph_storage)
                stats["relation_count"] = len(graph_storage.get_all_relations())
            except Exception as e:
                logger.warning(f"Could not get graph stats: {e}")
                stats["entity_count"] = 0
                stats["relation_count"] = 0

        if detailed:
            stats["details"] = {
                "storage": {
                    "vector_path": str(self._vector_store) if self._vector_store else None,
                    "graph_path": str(self._graph_storage) if self._graph_storage else None,
                },
                "capabilities": {
                    "vector_search": self._vector_store is not None,
                    "knowledge_graph": self._graph_storage is not None,
                    "llm_enhancement": True,
                    "media_ingestion": True,
                },
            }

        return stats

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


class AriadneToolHandler:
    """Manages all MCP tools for Ariadne."""

    def __init__(
        self,
        vector_store=None,
        graph_storage=None,
    ):
        self._tools: Dict[str, MCPTool] = {}
        self._vector_store = vector_store
        self._graph_storage = graph_storage

        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register built-in tools."""
        self._tools["ariadne_search"] = SearchTool(vector_store=self._vector_store)
        self._tools["ariadne_ingest"] = IngestTool(
            vector_store=self._vector_store,
            graph_storage=self._graph_storage,
        )
        self._tools["ariadne_graph_query"] = GraphQueryTool(graph_storage=self._graph_storage)
        self._tools["ariadne_stats"] = StatsTool(
            vector_store=self._vector_store,
            graph_storage=self._graph_storage,
        )

    def register(self, name: str, tool: MCPTool):
        """Register a new tool."""
        self._tools[name] = tool

    def get(self, name: str) -> Optional[MCPTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list(self) -> List[Dict[str, Any]]:
        """List all tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool."""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        try:
            return tool.execute(arguments)
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
