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
        self._register_extended_tools()

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

    def _register_extended_tools(self):
        """Register extended tools (RAG, memory management, etc.)."""
        # RAG Search Tool
        self._tools["ariadne_rag_search"] = RAGSearchTool(vector_store=self._vector_store)

        # Summarize Tool
        self._tools["ariadne_summarize"] = SummarizeTool(vector_store=self._vector_store)

        # Memory Management Tools
        self._tools["ariadne_memory_list"] = MemoryListTool()
        self._tools["ariadne_memory_create"] = MemoryCreateTool()
        self._tools["ariadne_memory_delete"] = MemoryDeleteTool()

        # Graph Explore Tool
        self._tools["ariadne_graph_explore"] = GraphExploreTool(graph_storage=self._graph_storage)

        # Config Tool
        self._tools["ariadne_config_get"] = ConfigGetTool()

        # Health Check Tool
        self._tools["ariadne_health_check"] = HealthCheckTool(
            vector_store=self._vector_store,
            graph_storage=self._graph_storage,
        )

        # Web Search Tool (NEW)
        self._tools["ariadne_web_search"] = WebSearchTool()

        # Document Info Tool
        self._tools["ariadne_document_info"] = DocumentInfoTool(vector_store=self._vector_store)

        # LLM Wiki Tools (Karpathy pattern)
        self._tools["ariadne_wiki_ingest"] = WikiIngestTool()
        self._tools["ariadne_wiki_query"] = WikiQueryTool()
        self._tools["ariadne_wiki_lint"] = WikiLintTool()
        self._tools["ariadne_wiki_list"] = WikiListTool()

    def register(self, name: str, tool: MCPTool):
        """Register a new tool."""
        self._tools[name] = tool

    def get(self, name: str) -> Optional[MCPTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list(self) -> List[Dict[str, Any]]:
        """List all tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def list_categories(self) -> Dict[str, List[str]]:
        """List tools grouped by category."""
        categories = {
            "search": ["ariadne_search", "ariadne_rag_search"],
            "ingest": ["ariadne_ingest", "ariadne_web_search"],
            "memory": ["ariadne_memory_list", "ariadne_memory_create", "ariadne_memory_delete"],
            "graph": ["ariadne_graph_query", "ariadne_graph_explore"],
            "analytics": ["ariadne_stats", "ariadne_health_check", "ariadne_document_info"],
            "llm": ["ariadne_summarize"],
            "config": ["ariadne_config_get"],
            "wiki": ["ariadne_wiki_ingest", "ariadne_wiki_query", "ariadne_wiki_lint", "ariadne_wiki_list"],
        }
        return categories

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


# ============================================================================
# Extended Tool Implementations
# ============================================================================


@dataclass
class RAGSearchTool(MCPTool):
    """RAG hybrid search tool with BM25 + vector + reranking."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_rag_search",
            description="Advanced RAG search using hybrid retrieval (BM25 + vector) with optional reranking. Returns more accurate results than basic semantic search.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of final results to return (default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "fetch_k": {
                        "type": "integer",
                        "description": "Number of candidates to fetch before reranking (default: 20)",
                        "default": 20,
                        "minimum": 10,
                        "maximum": 100,
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Vector weight: 1.0=vector-only, 0.0=BM25-only (default: 0.5)",
                        "default": 0.5,
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "no_rerank": {
                        "type": "boolean",
                        "description": "Skip reranking stage",
                        "default": False,
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name (default: 'default')",
                        "default": "default",
                    },
                    "include_citations": {
                        "type": "boolean",
                        "description": "Include source citations",
                        "default": True,
                    },
                },
                "required": ["query"],
            },
        )
        self._vector_store = vector_store

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute RAG search."""
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        fetch_k = arguments.get("fetch_k", 20)
        alpha = arguments.get("alpha", 0.5)
        no_rerank = arguments.get("no_rerank", False)
        include_citations = arguments.get("include_citations", True)

        if not query:
            return {"error": "Query is required"}

        try:
            from ariadne.rag import create_rag_engine
            from ariadne.memory import VectorStore

            if self._vector_store:
                store = VectorStore(persist_dir=str(self._vector_store))
            else:
                store = VectorStore()

            engine = create_rag_engine(store, config={
                "rerank": not no_rerank,
                "alpha": alpha,
            })

            result = engine.query(
                query=query,
                top_k=top_k,
                fetch_k=fetch_k,
                alpha=alpha,
                include_citations=include_citations,
            )

            if result.is_empty:
                return {"results": [], "query": query, "count": 0}

            return {
                "query": query,
                "count": len(result.results),
                "results": [
                    {
                        "content": res.document.content[:500],
                        "source": res.document.source_path,
                        "source_type": res.document.source_type.value,
                        "scores": {
                            "combined": round(res.combined_score, 4),
                            "vector": round(res.vector_score, 4) if res.vector_score else None,
                            "bm25": round(res.bm25_score, 4) if res.bm25_score else None,
                            "rank": res.rank,
                        },
                    }
                    for res in result.results
                ],
                "metadata": result.metadata,
            }

        except ImportError:
            return {"error": "RAG dependencies not installed (pip install rank-bm25 sentence-transformers)"}
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return {"error": str(e)}


@dataclass
class SummarizeTool(MCPTool):
    """Summarize search results using LLM."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_summarize",
            description="Generate a concise summary of search results using LLM. Must be used after a search to summarize the findings.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The original search query to summarize results for",
                    },
                    "language": {
                        "type": "string",
                        "description": "Output language (default: 'en', also supports: 'zh_CN', 'zh_TW', 'fr', 'es', 'de', 'ja')",
                        "default": "en",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name (default: 'default')",
                        "default": "default",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum search results to summarize (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        )
        self._vector_store = vector_store

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute summarization."""
        query = arguments.get("query", "")
        language = arguments.get("language", "en")
        max_results = arguments.get("max_results", 10)

        if not query:
            return {"error": "Query is required"}

        try:
            from ariadne.memory import VectorStore
            from ariadne.config import get_config

            if self._vector_store:
                store = VectorStore(persist_dir=str(self._vector_store))
            else:
                store = VectorStore()

            results = store.search(query, top_k=max_results)
            if not results:
                return {"summary": "No results found for summarization.", "query": query}

            cfg = get_config()
            if not cfg.get("advanced.enable_summary"):
                return {"error": "Summary feature is disabled"}

            llm = cfg.create_llm()
            if llm is None:
                return {"error": "No LLM configured"}

            context = "\n\n".join([
                f"[Document {i+1}]\n{doc.content[:500]}"
                for i, (doc, _) in enumerate(results)
            ])

            lang_prompts = {
                "zh_CN": "请用简体中文总结",
                "zh_TW": "請用繁體中文總結",
                "en": "Please summarize in English",
                "fr": "Veuillez résumer en français",
                "es": "Por favor, resuma en español",
            }
            lang_prompt = lang_prompts.get(language, "Please summarize in English")

            prompt = f"""Based on the following search results, {lang_prompt}:

Search Query: {query}

{context}

Please provide:
1. Main topics and themes
2. Key insights or findings
3. A brief summary (2-3 sentences)
"""

            response = llm.chat(prompt)

            return {
                "query": query,
                "summary": response.content,
                "language": language,
                "sources": [doc.source_path for doc, _ in results],
            }

        except ImportError as e:
            return {"error": f"Missing dependency: {e}"}
        except Exception as e:
            logger.error(f"Summarize error: {e}")
            return {"error": str(e)}


@dataclass
class MemoryListTool(MCPTool):
    """List all memory systems."""

    def __init__(self):
        super().__init__(
            name="ariadne_memory_list",
            description="List all available memory systems. Each memory system is a separate namespace for storing documents.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory list."""
        try:
            from ariadne.memory import get_manager

            manager = get_manager()
            systems = manager.list_systems()

            return {
                "count": len(systems),
                "default": manager.DEFAULT_COLLECTION,
                "memory_systems": [
                    {
                        "name": s.name,
                        "description": s.description or "",
                        "path": s.path,
                    }
                    for s in systems
                ],
            }
        except Exception as e:
            logger.error(f"Memory list error: {e}")
            return {"error": str(e), "memory_systems": []}


@dataclass
class MemoryCreateTool(MCPTool):
    """Create a new memory system."""

    def __init__(self):
        super().__init__(
            name="ariadne_memory_create",
            description="Create a new named memory system. Useful for organizing different types of knowledge.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the new memory system (use snake_case or camelCase)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of this memory system",
                    },
                },
                "required": ["name"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory create."""
        name = arguments.get("name", "")
        description = arguments.get("description", "")

        if not name:
            return {"error": "Name is required"}

        try:
            from ariadne.memory import get_manager

            manager = get_manager()
            manager.create(name, description)

            return {
                "success": True,
                "name": name,
                "description": description,
                "message": f"Memory system '{name}' created",
            }
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Memory create error: {e}")
            return {"error": str(e)}


@dataclass
class MemoryDeleteTool(MCPTool):
    """Delete a memory system."""

    def __init__(self):
        super().__init__(
            name="ariadne_memory_delete",
            description="Delete a memory system. WARNING: This cannot be undone! The default memory system cannot be deleted.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the memory system to delete",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm deletion",
                    },
                },
                "required": ["name", "confirm"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory delete."""
        name = arguments.get("name", "")
        confirm = arguments.get("confirm", False)

        if not name:
            return {"error": "Name is required"}
        if not confirm:
            return {"error": "Must set confirm=true to delete"}

        try:
            from ariadne.memory import get_manager

            manager = get_manager()

            if name == manager.DEFAULT_COLLECTION:
                return {"error": "Cannot delete the default memory system"}

            manager.delete(name, confirm=True)

            return {
                "success": True,
                "name": name,
                "message": f"Memory system '{name}' deleted",
            }
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Memory delete error: {e}")
            return {"error": str(e)}


@dataclass
class GraphExploreTool(MCPTool):
    """Explore knowledge graph paths and relationships."""

    def __init__(self, graph_storage=None):
        super().__init__(
            name="ariadne_graph_explore",
            description="Explore the knowledge graph to discover paths and relationships between entities. More powerful than basic graph_query.",
            input_schema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Starting entity name or ID",
                    },
                    "target": {
                        "type": "string",
                        "description": "Optional target entity to find path to",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth (default: 3)",
                        "default": 3,
                        "maximum": 5,
                    },
                    "relation_filter": {
                        "type": "string",
                        "description": "Optional relation type to filter by",
                    },
                },
                "required": ["entity"],
            },
        )
        self._graph_storage = graph_storage

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute graph explore."""
        entity = arguments.get("entity", "")
        target = arguments.get("target")
        max_depth = arguments.get("max_depth", 3)
        relation_filter = arguments.get("relation_filter")

        if not entity:
            return {"error": "Entity is required"}

        try:
            from ariadne.graph import GraphStorage

            if self._graph_storage:
                graph = GraphStorage(str(self._graph_storage))
            else:
                return {"error": "Graph storage not configured"}

            start = graph.get_entity_by_name(entity)
            if not start:
                return {"error": f"Entity not found: {entity}"}

            # BFS to find all reachable entities
            visited = {start.entity_id}
            current_level = [start.entity_id]
            all_entities = []
            all_relations = []

            for depth in range(max_depth):
                next_level = []
                for eid in current_level:
                    neighbors = graph.get_neighbors(eid)
                    for neighbor, relation in neighbors:
                        if neighbor.entity_id not in visited:
                            visited.add(neighbor.entity_id)
                            next_level.append(neighbor.entity_id)
                            all_entities.append({
                                "id": neighbor.entity_id,
                                "name": neighbor.name,
                                "type": neighbor.entity_type.value,
                                "depth": depth + 1,
                            })

                        if relation_filter is None or relation.relation_type.value == relation_filter:
                            all_relations.append({
                                "source": relation.source_id,
                                "target": relation.target_id,
                                "type": relation.relation_type.value,
                                "description": relation.description,
                            })

                current_level = next_level
                if not current_level:
                    break

            return {
                "start_entity": entity,
                "target_entity": target,
                "depth_reached": depth + 1,
                "entities_found": len(all_entities),
                "entities": all_entities,
                "relations": all_relations[:50],  # Limit for response size
            }

        except Exception as e:
            logger.error(f"Graph explore error: {e}")
            return {"error": str(e)}


@dataclass
class ConfigGetTool(MCPTool):
    """Get Ariadne configuration."""

    def __init__(self):
        super().__init__(
            name="ariadne_config_get",
            description="Get Ariadne configuration values including LLM provider, model, and feature settings.",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Specific config key to retrieve (optional, returns all if omitted)",
                    },
                    "include_api_key": {
                        "type": "boolean",
                        "description": "Include API key in response (default: false)",
                        "default": False,
                    },
                },
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute config get."""
        key = arguments.get("key")
        include_api_key = arguments.get("include_api_key", False)

        try:
            from ariadne.config import get_config

            cfg = get_config()

            if key:
                value = cfg.get(key)
                return {"key": key, "value": value}
            else:
                config = cfg.to_dict()
                if not include_api_key:
                    if "llm" in config and "api_key" in config["llm"]:
                        config["llm"]["api_key"] = "****" if config["llm"]["api_key"] else None
                return {"config": config}

        except Exception as e:
            logger.error(f"Config get error: {e}")
            return {"error": str(e)}


@dataclass
class HealthCheckTool(MCPTool):
    """System health check."""

    def __init__(self, vector_store=None, graph_storage=None):
        super().__init__(
            name="ariadne_health_check",
            description="Check the health status of Ariadne components including vector store, graph database, and LLM connectivity.",
            input_schema={
                "type": "object",
                "properties": {
                    "check_llm": {
                        "type": "boolean",
                        "description": "Also test LLM connectivity",
                        "default": True,
                    },
                },
            },
        )
        self._vector_store = vector_store
        self._graph_storage = graph_storage

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute health check."""
        check_llm = arguments.get("check_llm", True)

        results = {
            "status": "healthy",
            "timestamp": self._get_timestamp(),
            "components": {},
        }

        # Check vector store
        try:
            from ariadne.memory import VectorStore
            store = VectorStore(persist_dir=str(self._vector_store)) if self._vector_store else VectorStore()
            count = store.count()
            results["components"]["vector_store"] = {
                "status": "ok",
                "documents": count,
            }
        except Exception as e:
            results["components"]["vector_store"] = {
                "status": "error",
                "error": str(e),
            }
            results["status"] = "degraded"

        # Check graph storage
        try:
            from ariadne.graph import GraphStorage
            graph = GraphStorage(str(self._graph_storage)) if self._graph_storage else None
            if graph:
                entities = len(graph.get_all_entities())
                relations = len(graph.get_all_relations())
                results["components"]["graph_storage"] = {
                    "status": "ok",
                    "entities": entities,
                    "relations": relations,
                }
        except Exception as e:
            results["components"]["graph_storage"] = {
                "status": "error",
                "error": str(e),
            }
            results["status"] = "degraded"

        # Check LLM
        if check_llm:
            try:
                from ariadne.config import get_config
                cfg = get_config()
                success, msg = cfg.test_llm()
                results["components"]["llm"] = {
                    "status": "ok" if success else "error",
                    "message": msg,
                    "provider": cfg.get("llm.provider", "unknown"),
                }
                if not success:
                    results["status"] = "degraded"
            except Exception as e:
                results["components"]["llm"] = {
                    "status": "error",
                    "error": str(e),
                }

        return results

    def _get_timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


@dataclass
class WebSearchTool(MCPTool):
    """Search the web and ingest results."""

    def __init__(self):
        super().__init__(
            name="ariadne_web_search",
            description="Search the web for information and optionally ingest results into memory. Useful for finding up-to-date information.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Web search query",
                    },
                    "ingest": {
                        "type": "boolean",
                        "description": "Ingest search results into memory",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5,
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection to ingest into (default: 'default')",
                        "default": "default",
                    },
                },
                "required": ["query"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search."""
        query = arguments.get("query", "")
        ingest = arguments.get("ingest", False)
        max_results = arguments.get("max_results", 5)

        if not query:
            return {"error": "Query is required"}

        try:
            # Try to use requests for web search
            import requests

            # Simple web search using DuckDuckGo HTML
            url = f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0"}

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return {"error": f"Web search failed: {response.status_code}"}

            # Parse results (simplified)
            results = []
            import re
            pattern = re.compile(r'<a class="result__a" href="([^"]+)">([^<]+)</a>')
            for match in pattern.finditer(response.text):
                url, title = match.groups()
                if len(results) < max_results:
                    results.append({
                        "title": title.strip(),
                        "url": url,
                    })

            if ingest and results:
                try:
                    from ariadne.ingest import get_ingestor
                    from ariadne.memory import VectorStore

                    ingested = 0
                    for result in results:
                        try:
                            # Use URL as source
                            content = f"# {result['title']}\n\nURL: {result['url']}\n\nQuery: {query}"
                            # Store as temporary file
                            import tempfile
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                                f.write(content)
                                temp_path = f.name

                            ingestor = get_ingestor(temp_path)
                            docs = ingestor.ingest(temp_path)
                            if docs:
                                store = VectorStore()
                                store.add(docs)
                                ingested += 1
                        except Exception:
                            pass

                    return {
                        "query": query,
                        "results": results,
                        "ingested": ingested,
                        "message": f"Ingested {ingested} results",
                    }
                except Exception as e:
                    return {
                        "query": query,
                        "results": results,
                        "ingest_error": str(e),
                    }

            return {
                "query": query,
                "results": results,
                "count": len(results),
            }

        except ImportError:
            return {"error": "requests library not installed for web search"}
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {"error": str(e)}


@dataclass
class DocumentInfoTool(MCPTool):
    """Get detailed information about documents."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_document_info",
            description="Get detailed information about indexed documents including metadata, chunk count, and source details.",
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Source file path to look up",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection to search in (default: 'default')",
                        "default": "default",
                    },
                    "list_sources": {
                        "type": "boolean",
                        "description": "List all unique source paths",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of sources to list (default: 20)",
                        "default": 20,
                    },
                },
            },
        )
        self._vector_store = vector_store

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document info."""
        source_path = arguments.get("source_path")
        list_sources = arguments.get("list_sources", False)
        limit = arguments.get("limit", 20)

        try:
            from ariadne.memory import VectorStore

            if self._vector_store:
                store = VectorStore(persist_dir=str(self._vector_store))
            else:
                store = VectorStore()

            if source_path:
                # Find documents by source path
                docs = store.get_all_documents(limit=1000)
                matching = [d for d in docs if d.source_path == source_path]

                if not matching:
                    return {"error": f"No documents found for: {source_path}"}

                return {
                    "source_path": source_path,
                    "total_chunks": len(matching),
                    "documents": [
                        {
                            "chunk_index": d.chunk_index,
                            "content_preview": d.content[:200],
                            "source_type": d.source_type.value,
                        }
                        for d in matching
                    ],
                }

            if list_sources:
                docs = store.get_all_documents(limit=1000)
                sources = {}
                for d in docs:
                    if d.source_path not in sources:
                        sources[d.source_path] = {
                            "source": d.source_path,
                            "source_type": d.source_type.value,
                            "chunk_count": 1,
                        }
                    else:
                        sources[d.source_path]["chunk_count"] += 1

                source_list = list(sources.values())[:limit]
                return {
                    "total_sources": len(sources),
                    "sources": source_list,
                }

            return {"error": "Must provide source_path or set list_sources=true"}

        except Exception as e:
            logger.error(f"Document info error: {e}")
            return {"error": str(e)}


# ============================================================================
# Wiki Tools (LLM Wiki — Karpathy pattern)
# ============================================================================

@dataclass
class WikiIngestTool(MCPTool):
    """Ingest a source file into the LLM Wiki."""

    def __init__(self):
        super().__init__(
            name="ariadne_wiki_ingest",
            description=(
                "Ingest a source file or URL into the LLM Wiki using Karpathy's "
                "two-step Chain-of-Thought pattern. Step 1: LLM analyzes the source "
                "and produces a structured analysis. Step 2: LLM generates wiki pages. "
                "Results are cached by source SHA256 to avoid re-processing unchanged files."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Path or URL of the source file to ingest into the wiki",
                    },
                    "project_dir": {
                        "type": "string",
                        "description": "Wiki project root directory (default: '<data_dir>/wiki')",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force re-ingest even if cache hit (default: False)",
                        "default": False,
                    },
                    "llm_config": {
                        "type": "object",
                        "description": "LLM provider config: {provider, model, api_key, base_url, max_tokens, temperature}",
                    },
                },
                "required": ["source"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        source = arguments["source"]
        project_dir = arguments.get("project_dir")
        force = arguments.get("force", False)
        llm_config = arguments.get("llm_config")

        try:
            from ariadne.wiki import (
                WikiProject, ingest_source, batch_ingest, init_wiki_project,
            )

            # Resolve project directory
            if project_dir:
                proj = WikiProject(wiki_dir=project_dir)
            else:
                # Use default project in data_dir
                from ariadne.config import ConfigManager
                data_dir = ConfigManager.load_default_data_dir()
                proj = WikiProject(wiki_dir=str(data_dir / "wiki"))

            # Ensure wiki project exists
            if not proj.wiki_dir_exists:
                init_wiki_project(proj)

            # Run ingest
            result = ingest_source(
                source=source,
                project=proj,
                force=force,
                llm_config=llm_config,
            )
            return {
                "source": source,
                "project_dir": proj.wiki_dir,
                "pages_created": result.pages_created,
                "reviews": [r.to_dict() if hasattr(r, "to_dict") else r for r in result.reviews],
                "cached": result.cached,
                "log_entry": result.log_entry,
            }
        except ImportError as e:
            return {"error": f"Wiki module not available: {e}"}
        except Exception as e:
            logger.error(f"Wiki ingest error: {e}")
            return {"error": str(e)}


@dataclass
class WikiQueryTool(MCPTool):
    """Query the LLM Wiki with a natural language question."""

    def __init__(self):
        super().__init__(
            name="ariadne_wiki_query",
            description=(
                "Ask the LLM Wiki a question. Searches relevant wiki pages, "
                "passes them to an LLM for synthesis, and returns an answer "
                "with citations. Optionally archives the Q&A back into the wiki."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question to ask the wiki",
                    },
                    "project_dir": {
                        "type": "string",
                        "description": "Wiki project root directory (default: '<data_dir>/wiki')",
                    },
                    "save_to_wiki": {
                        "type": "boolean",
                        "description": "Save the answer as a wiki query page (default: False)",
                        "default": False,
                    },
                    "llm_config": {
                        "type": "object",
                        "description": "LLM provider config: {provider, model, api_key, base_url}",
                    },
                },
                "required": ["question"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        question = arguments["question"]
        project_dir = arguments.get("project_dir")
        save_to_wiki = arguments.get("save_to_wiki", False)
        llm_config = arguments.get("llm_config")

        try:
            from ariadne.wiki import WikiProject, query_wiki

            # Resolve project directory
            if project_dir:
                proj = WikiProject(wiki_dir=project_dir)
            else:
                from ariadne.config import ConfigManager
                data_dir = ConfigManager.load_default_data_dir()
                proj = WikiProject(wiki_dir=str(data_dir / "wiki"))

            if not proj.wiki_dir_exists:
                return {"error": f"Wiki project not found: {proj.wiki_dir}"}

            result = query_wiki(
                question=question,
                project=proj,
                save_to_wiki=save_to_wiki,
                llm_config=llm_config,
            )
            return {
                "question": question,
                "answer": result.answer,
                "pages_used": result.pages_used,
                "citations": result.citations,
                "query_slug": result.query_slug if hasattr(result, "query_slug") else None,
            }
        except ImportError as e:
            return {"error": f"Wiki module not available: {e}"}
        except Exception as e:
            logger.error(f"Wiki query error: {e}")
            return {"error": str(e)}


@dataclass
class WikiLintTool(MCPTool):
    """Run lint checks on the LLM Wiki."""

    def __init__(self):
        super().__init__(
            name="ariadne_wiki_lint",
            description=(
                "Run health checks on the LLM Wiki. Structural lint detects "
                "orphan pages, broken wikilinks, and pages with no outgoing links. "
                "Semantic lint uses an LLM to detect contradictions, stale claims, "
                "and missing cross-references."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_dir": {
                        "type": "string",
                        "description": "Wiki project root directory (default: '<data_dir>/wiki')",
                    },
                    "mode": {
                        "type": "string",
                        "description": "Lint mode: 'structural', 'semantic', or 'full' (default: 'full')",
                        "default": "full",
                        "enum": ["structural", "semantic", "full"],
                    },
                    "llm_config": {
                        "type": "object",
                        "description": "LLM provider config for semantic lint: {provider, model, api_key, base_url}",
                    },
                },
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_dir = arguments.get("project_dir")
        mode = arguments.get("mode", "full")
        llm_config = arguments.get("llm_config")

        try:
            from ariadne.wiki import WikiProject, run_full_lint, run_structural_lint, run_semantic_lint

            # Resolve project directory
            if project_dir:
                proj = WikiProject(wiki_dir=project_dir)
            else:
                from ariadne.config import ConfigManager
                data_dir = ConfigManager.load_default_data_dir()
                proj = WikiProject(wiki_dir=str(data_dir / "wiki"))

            if not proj.wiki_dir_exists:
                return {"error": f"Wiki project not found: {proj.wiki_dir}"}

            if mode == "structural":
                issues = run_structural_lint(proj)
            elif mode == "semantic":
                issues = run_semantic_lint(proj, llm_config=llm_config)
            else:
                issues = run_full_lint(proj, llm_config=llm_config)

            return {
                "mode": mode,
                "project_dir": proj.wiki_dir,
                "total_issues": len(issues),
                "issues": [
                    {
                        "type": i.issue_type.value,
                        "severity": i.severity.value,
                        "page": i.page_path,
                        "message": i.message,
                        "details": i.details,
                    }
                    for i in issues
                ],
            }
        except ImportError as e:
            return {"error": f"Wiki module not available: {e}"}
        except Exception as e:
            logger.error(f"Wiki lint error: {e}")
            return {"error": str(e)}


@dataclass
class WikiListTool(MCPTool):
    """List all pages in an LLM Wiki project."""

    def __init__(self):
        super().__init__(
            name="ariadne_wiki_list",
            description="List all wiki pages in a project, optionally filtered by type or tag.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_dir": {
                        "type": "string",
                        "description": "Wiki project root directory (default: '<data_dir>/wiki')",
                    },
                    "page_type": {
                        "type": "string",
                        "description": "Filter by page type: source, entity, concept, comparison, query, synthesis",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter by tag in frontmatter",
                    },
                },
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_dir = arguments.get("project_dir")
        page_type = arguments.get("page_type")
        tag = arguments.get("tag")

        try:
            from ariadne.wiki import WikiProject, list_wiki_pages, read_wiki_page

            # Resolve project directory
            if project_dir:
                proj = WikiProject(wiki_dir=project_dir)
            else:
                from ariadne.config import ConfigManager
                data_dir = ConfigManager.load_default_data_dir()
                proj = WikiProject(wiki_dir=str(data_dir / "wiki"))

            if not proj.wiki_dir_exists:
                return {"error": f"Wiki project not found: {proj.wiki_dir}"}

            pages = list_wiki_pages(proj.wiki_dir)
            results = []

            for path in pages:
                page = read_wiki_page(path)
                if page is None:
                    continue

                rel = path.replace(proj.wiki_dir, "").lstrip("/\\")

                # Filter by page type
                if page_type and page.frontmatter.page_type.value != page_type:
                    continue

                # Filter by tag
                if tag and tag not in page.frontmatter.tags:
                    continue

                results.append({
                    "path": rel,
                    "title": page.frontmatter.title or rel,
                    "type": page.frontmatter.page_type.value,
                    "tags": page.frontmatter.tags,
                    "created": page.frontmatter.created,
                    "updated": page.frontmatter.updated,
                    "preview": page.content[:200],
                })

            return {
                "project_dir": proj.wiki_dir,
                "total_pages": len(results),
                "pages": results,
            }
        except ImportError as e:
            return {"error": f"Wiki module not available: {e}"}
        except Exception as e:
            logger.error(f"Wiki list error: {e}")
            return {"error": str(e)}

