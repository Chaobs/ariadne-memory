"""
MCP Resource implementations for Ariadne.

Resources provide access to knowledge base data in a structured format.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import json

from .server import MCPResource


@dataclass
class DocumentResource(MCPResource):
    """Resource for accessing document content."""

    document_id: Optional[str] = None
    collection: str = "default"

    def __init__(
        self,
        document_id: str,
        collection: str = "default",
        vector_store=None,
    ):
        super().__init__(
            uri=f"ariadne://documents/{collection}/{document_id}",
            name=f"Document: {document_id}",
            description=f"Document {document_id} from collection {collection}",
            mime_type="text/plain",
        )
        self.document_id = document_id
        self.collection = collection
        self._vector_store = vector_store

    def read(self) -> Dict[str, Any]:
        """Read document content."""
        if self._vector_store:
            try:
                doc = self._vector_store.get(self.document_id)
                if doc:
                    return {
                        "id": self.document_id,
                        "content": doc.get("content", ""),
                        "metadata": doc.get("metadata", {}),
                    }
            except Exception:
                pass
        return {"error": "Document not found"}


@dataclass
class CollectionResource(MCPResource):
    """Resource for accessing collection information."""

    collection_name: str = "default"

    def __init__(self, collection_name: str = "default", vector_store=None):
        super().__init__(
            uri=f"ariadne://collections/{collection_name}",
            name=f"Collection: {collection_name}",
            description=f"Collection {collection_name} information",
            mime_type="application/json",
        )
        self.collection_name = collection_name
        self._vector_store = vector_store

    def read(self) -> Dict[str, Any]:
        """Read collection information."""
        if self._vector_store:
            try:
                count = self._vector_store.count(collection=self.collection_name)
                return {
                    "name": self.collection_name,
                    "document_count": count,
                }
            except Exception:
                pass
        return {"name": self.collection_name, "document_count": 0}


@dataclass
class GraphResource(MCPResource):
    """Resource for accessing knowledge graph data."""

    entity_id: Optional[str] = None
    graph_type: str = "entities"

    def __init__(
        self,
        entity_id: Optional[str] = None,
        graph_type: str = "entities",
        graph_storage=None,
    ):
        uri = f"ariadne://graph/{graph_type}"
        if entity_id:
            uri += f"/{entity_id}"

        super().__init__(
            uri=uri,
            name=f"Graph {graph_type}" + (f": {entity_id}" if entity_id else ""),
            description=f"Knowledge graph {graph_type}" + (f" for {entity_id}" if entity_id else ""),
            mime_type="application/json",
        )
        self.entity_id = entity_id
        self.graph_type = graph_type
        self._graph_storage = graph_storage

    def read(self) -> Dict[str, Any]:
        """Read graph data."""
        if not self._graph_storage:
            return {"error": "Graph storage not available"}

        try:
            if self.graph_type == "entities":
                entities = self._graph_storage.get_all_entities()
                return {"entities": [self._entity_to_dict(e) for e in entities[:100]]}
            elif self.graph_type == "relations":
                relations = self._graph_storage.get_all_relations()
                return {"relations": [self._relation_to_dict(r) for r in relations[:100]]}
            elif self.entity_id:
                entity = self._graph_storage.get_entity(self.entity_id)
                if entity:
                    relations = self._graph_storage.get_relations(self.entity_id)
                    return {
                        "entity": self._entity_to_dict(entity),
                        "relations": [self._relation_to_dict(r) for r in relations],
                    }
        except Exception as e:
            return {"error": str(e)}
        return {}

    def _entity_to_dict(self, entity) -> Dict[str, Any]:
        """Convert entity to dict."""
        return {
            "id": getattr(entity, "entity_id", ""),
            "name": getattr(entity, "name", ""),
            "type": getattr(entity, "entity_type", ""),
            "description": getattr(entity, "description", ""),
        }

    def _relation_to_dict(self, relation) -> Dict[str, Any]:
        """Convert relation to dict."""
        return {
            "source": getattr(relation, "source_id", ""),
            "target": getattr(relation, "target_id", ""),
            "type": getattr(relation, "relation_type", ""),
            "description": getattr(relation, "description", ""),
        }


@dataclass
class ConfigResource(MCPResource):
    """Resource for accessing Ariadne configuration."""

    def __init__(self, config_path: Optional[str] = None, config_manager=None):
        super().__init__(
            uri="ariadne://config",
            name="Configuration",
            description="Ariadne system configuration",
            mime_type="application/json",
        )
        self._config_path = config_path
        self._config_manager = config_manager

    def read(self) -> Dict[str, Any]:
        """Read configuration."""
        if self._config_manager:
            return self._config_manager.config

        if self._config_path:
            try:
                with open(self._config_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


class AriadneResourceManager:
    """Manages all MCP resources for Ariadne."""

    def __init__(
        self,
        vector_store=None,
        graph_storage=None,
        config_manager=None,
        config_path: Optional[str] = None,
    ):
        self._resources: Dict[str, MCPResource] = {}
        self._vector_store = vector_store
        self._graph_storage = graph_storage
        self._config_manager = config_manager
        self._config_path = config_path

        self._register_builtin_resources()

    def _register_builtin_resources(self):
        """Register built-in resources."""
        self._resources["ariadne://collections"] = MCPResource(
            uri="ariadne://collections",
            name="Collections",
            description="List of available document collections",
            mime_type="application/json",
        )

        self._resources["ariadne://stats"] = MCPResource(
            uri="ariadne://stats",
            name="Statistics",
            description="Knowledge base statistics",
            mime_type="application/json",
        )

        self._resources["ariadne://config"] = ConfigResource(
            config_path=self._config_path,
            config_manager=self._config_manager,
        )

    def register(self, resource: MCPResource):
        """Register a new resource."""
        self._resources[resource.uri] = resource

    def get(self, uri: str) -> Optional[MCPResource]:
        """Get resource by URI."""
        return self._resources.get(uri)

    def list(self) -> List[Dict[str, Any]]:
        """List all resources."""
        return [r.to_dict() for r in self._resources.values()]

    def read(self, uri: str) -> Dict[str, Any]:
        """Read resource content."""
        resource = self._resources.get(uri)
        if resource and hasattr(resource, "read"):
            return resource.read()

        if uri == "ariadne://collections":
            return self._get_collections()
        elif uri == "ariadne://stats":
            return self._get_stats()
        elif uri == "ariadne://config":
            return self._get_config()

        return {"error": "Resource not found"}

    def _get_collections(self) -> Dict[str, Any]:
        """Get collections list."""
        if self._vector_store:
            try:
                collections = self._vector_store.list_collections()
                return {"collections": collections}
            except Exception:
                pass
        return {"collections": ["default"]}

    def _get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        stats = {}
        if self._vector_store:
            try:
                stats["total_documents"] = self._vector_store.count()
            except Exception:
                pass
        if self._graph_storage:
            try:
                stats["total_entities"] = len(self._graph_storage)
            except Exception:
                pass
        return stats

    def _get_config(self) -> Dict[str, Any]:
        """Get configuration."""
        if self._config_manager:
            return self._config_manager.config
        return {}
