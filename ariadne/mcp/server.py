"""
MCP Server implementation for Ariadne.

Provides a complete MCP server with tools, resources, and prompts.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class MCPMessage:
    """MCP protocol message structure."""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create message from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            result["id"] = self.id
        if self.method is not None:
            result["method"] = self.method
        if self.params is not None:
            result["params"] = self.params
        if self.result is not None:
            result["result"] = self.result
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class MCPResource:
    """MCP resource definition."""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: str = "text/plain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPPrompt:
    """MCP prompt template definition."""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


class MCPHandler:
    """Base handler for MCP protocol operations."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup method handlers."""
        self._handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "ping": self._handle_ping,
        }

    def handle(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Dispatch to appropriate handler."""
        handler = self._handlers.get(method)
        if handler:
            return handler(params or {})
        raise ValueError(f"Unknown method: {method}")

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ariadne-memory",
                "version": "2.0.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": []}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        raise ValueError("No tools registered")

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {"resources": []}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        raise ValueError("No resources registered")

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {"prompts": []}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        raise ValueError("No prompts registered")

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True}


class AriadneMCPServer:
    """
    Main MCP Server for Ariadne Memory System.

    This server exposes Ariadne's capabilities as MCP tools, resources,
    and prompts that can be consumed by any MCP-compatible client.

    Example usage:
        # Create and run server
        server = AriadneMCPServer(
            vector_store_path="./data/vectors",
            graph_db_path="./data/graph.db"
        )
        server.run()

    Or use with stdio:
        server = AriadneMCPServer()
        server.run_stdio()
    """

    def __init__(
        self,
        vector_store_path: str = "./data/vectors",
        graph_db_path: str = "./data/graph.db",
        config_path: Optional[str] = None,
        log_level: str = "INFO",
    ):
        """Initialize Ariadne MCP Server."""
        self.vector_store_path = Path(vector_store_path)
        self.graph_db_path = Path(graph_db_path)
        self.config_path = Path(config_path) if config_path else None

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Initialize handlers
        self._handler = MCPHandler()
        self._tools: Dict[str, Callable] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}

        # Initialize Ariadne components (lazy import)
        self._vector_store = None
        self._graph_storage = None

        logger.info("Ariadne MCP Server initialized")

    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            try:
                from ariadne.memory import VectorStore
                self._vector_store = VectorStore(persist_dir=str(self.vector_store_path))
                logger.info(f"Loaded vector store from {self.vector_store_path}")
            except Exception as e:
                logger.warning(f"Could not load vector store: {e}")
        return self._vector_store

    @property
    def graph_storage(self):
        """Lazy load graph storage."""
        if self._graph_storage is None:
            try:
                from ariadne.graph import GraphStorage
                self._graph_storage = GraphStorage(str(self.graph_db_path))
                logger.info(f"Loaded graph storage from {self.graph_db_path}")
            except Exception as e:
                logger.warning(f"Could not load graph storage: {e}")
        return self._graph_storage

    def register_tool(self, name: str, handler: Callable, schema: Dict[str, Any], description: str = ""):
        """Register a tool."""
        self._tools[name] = handler
        logger.info(f"Registered tool: {name}")

    def register_resource(self, resource: MCPResource):
        """Register a resource."""
        self._resources[resource.uri] = resource
        logger.info(f"Registered resource: {resource.uri}")

    def register_prompt(self, prompt: MCPPrompt):
        """Register a prompt template."""
        self._prompts[prompt.name] = prompt
        logger.info(f"Registered prompt: {prompt.name}")

    def handle_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP request."""
        try:
            msg = MCPMessage.from_dict(message)
            method = msg.method

            if method == "initialize":
                result = self._handle_initialize(msg.params or {})
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(msg.params or {})
            elif method == "resources/list":
                result = self._handle_resources_list()
            elif method == "resources/read":
                result = self._handle_resources_read(msg.params or {})
            elif method == "prompts/list":
                result = self._handle_prompts_list()
            elif method == "prompts/get":
                result = self._handle_prompts_get(msg.params or {})
            elif method == "ping":
                result = {"pong": True}
            else:
                raise ValueError(f"Unknown method: {method}")

            return MCPMessage(id=msg.id, result=result).to_dict()

        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return MCPMessage(
                id=message.get("id"),
                error={"code": -32603, "message": str(e)},
            ).to_dict()

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize."""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ariadne-memory",
                "version": "2.0.0",
            },
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True},
            },
            "instructions": "Ariadne Memory System - AI-powered knowledge management with vector search and knowledge graph.",
        }

    def _handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list."""
        tools = [
            MCPTool(
                name="ariadne_search",
                description="Search Ariadne's vector knowledge base. Returns relevant documents based on semantic similarity.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query in natural language",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)",
                            "default": 5,
                        },
                        "collection": {
                            "type": "string",
                            "description": "Collection name to search in",
                            "default": "default",
                        },
                    },
                    "required": ["query"],
                },
            ).to_dict(),
            MCPTool(
                name="ariadne_ingest",
                description="Ingest a document or URL into Ariadne's knowledge base. Supports various file formats.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "File path or URL to ingest",
                        },
                        "collection": {
                            "type": "string",
                            "description": "Collection name (default: 'default')",
                            "default": "default",
                        },
                    },
                    "required": ["source"],
                },
            ).to_dict(),
            MCPTool(
                name="ariadne_graph_query",
                description="Query the knowledge graph to find entity relationships and connections.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Entity name to query",
                        },
                        "relation_type": {
                            "type": "string",
                            "description": "Filter by relation type (optional)",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Traversal depth (default: 2)",
                            "default": 2,
                        },
                    },
                    "required": ["entity"],
                },
            ).to_dict(),
            MCPTool(
                name="ariadne_stats",
                description="Get statistics about the Ariadne knowledge base.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "description": "Collection name (default: 'default')",
                            "default": "default",
                        },
                    },
                },
            ).to_dict(),
        ]
        return {"tools": tools}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "ariadne_search":
                result = self._tool_search(arguments)
            elif tool_name == "ariadne_ingest":
                result = self._tool_ingest(arguments)
            elif tool_name == "ariadne_graph_query":
                result = self._tool_graph_query(arguments)
            elif tool_name == "ariadne_stats":
                result = self._tool_stats(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}",
                    }
                ],
                "isError": True,
            }

    def _tool_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search tool."""
        query = args.get("query", "")
        limit = args.get("limit", 5)

        if not self.vector_store:
            return {"error": "Vector store not available", "results": []}

        try:
            results = self.vector_store.search(query, top_k=limit)
            return {
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "content": doc.content[:500],
                        "source": doc.source_path,
                        "score": float(score),
                        "metadata": doc.metadata,
                    }
                    for doc, score in results
                ],
            }
        except Exception as e:
            return {"error": str(e), "results": []}

    def _tool_ingest(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ingest tool."""
        source = args.get("source", "")
        collection = args.get("collection", "default")

        if not source:
            return {"error": "Source is required", "documents": []}

        try:
            from ariadne.ingest import get_ingestor
            from ariadne.memory import VectorStore

            ingestor = get_ingestor(source)
            documents = ingestor.ingest(source)

            vector_store = VectorStore(persist_dir=str(self.vector_store_path))
            if documents:
                vector_store.add(documents)

            return {
                "source": source,
                "documents_ingested": len(documents),
                "collection": collection,
            }
        except Exception as e:
            return {"error": str(e), "documents": []}

    def _tool_graph_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute graph query tool."""
        entity = args.get("entity", "")
        depth = args.get("depth", 2)

        if not self.graph_storage:
            return {"error": "Graph storage not available", "entities": [], "relations": []}

        try:
            found = self.graph_storage.get_entity_by_name(entity)
            if not found:
                return {"error": f"Entity not found: {entity}", "entities": [], "relations": []}

            relations = self.graph_storage.get_relations(found.entity_id, max_depth=depth)

            return {
                "entity": entity,
                "depth": depth,
                "entities": [
                    {
                        "name": r.target.name if hasattr(r, "target") else r.get("target_name", ""),
                        "type": r.target.entity_type.value if hasattr(r, "target") else "",
                    }
                    for r in relations
                ],
                "relations": [
                    {
                        "type": r.relation_type.value if hasattr(r, "relation_type") else "",
                        "description": r.description if hasattr(r, "description") else "",
                    }
                    for r in relations
                ],
            }
        except Exception as e:
            return {"error": str(e), "entities": [], "relations": []}

    def _tool_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute stats tool."""
        collection = args.get("collection", "default")

        stats = {"collection": collection}

        if self.vector_store:
            try:
                stats["vector_count"] = self.vector_store.count()
            except:
                stats["vector_count"] = 0

        if self.graph_storage:
            try:
                stats["entity_count"] = len(self.graph_storage)
            except:
                stats["entity_count"] = 0

        return stats

    def _handle_resources_list(self) -> Dict[str, Any]:
        """Handle resources/list."""
        resources = [
            MCPResource(
                uri="ariadne://collections",
                name="Collections",
                description="List of available document collections",
                mime_type="application/json",
            ).to_dict(),
            MCPResource(
                uri="ariadne://stats",
                name="Statistics",
                description="Knowledge base statistics",
                mime_type="application/json",
            ).to_dict(),
            MCPResource(
                uri="ariadne://config",
                name="Configuration",
                description="Ariadne configuration",
                mime_type="application/json",
            ).to_dict(),
        ]
        return {"resources": resources}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read."""
        uri = params.get("uri", "")

        try:
            if uri == "ariadne://collections":
                content = self._get_collections()
            elif uri == "ariadne://stats":
                content = self._get_stats()
            elif uri == "ariadne://config":
                content = self._get_config()
            else:
                raise ValueError(f"Unknown resource: {uri}")

            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(content, ensure_ascii=False, indent=2),
                    }
                ]
            }
        except Exception as e:
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Error: {str(e)}"}]}

    def _get_collections(self) -> Dict[str, Any]:
        """Get collections info."""
        if self.vector_store:
            try:
                return {"collections": [c for c in self.vector_store.list_collections()]}
            except:
                pass
        return {"collections": ["default"]}

    def _get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self._tool_stats({})

    def _get_config(self) -> Dict[str, Any]:
        """Get configuration."""
        return {
            "vector_store_path": str(self.vector_store_path),
            "graph_db_path": str(self.graph_db_path),
            "config_path": str(self.config_path) if self.config_path else None,
        }

    def _handle_prompts_list(self) -> Dict[str, Any]:
        """Handle prompts/list."""
        prompts = [
            MCPPrompt(
                name="ariadne_search",
                description="Search the knowledge base with a specific query",
                arguments=[
                    {"name": "query", "description": "The search query", "required": True},
                    {"name": "limit", "description": "Max results", "required": False},
                ],
            ).to_dict(),
            MCPPrompt(
                name="ariadne_graph",
                description="Explore entity relationships in the knowledge graph",
                arguments=[
                    {"name": "entity", "description": "Starting entity", "required": True},
                    {"name": "depth", "description": "Traversal depth", "required": False},
                ],
            ).to_dict(),
            MCPPrompt(
                name="ariadne_context",
                description="Get relevant context from the knowledge base for a topic",
                arguments=[
                    {"name": "topic", "description": "Topic to get context about", "required": True},
                    {"name": "sources", "description": "Source types to include", "required": False},
                ],
            ).to_dict(),
        ]
        return {"prompts": prompts}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if name == "ariadne_search":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            results = self._tool_search({"query": query, "limit": limit})

            return {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Search the Ariadne knowledge base for: {query}\n\nResults:\n{json.dumps(results, ensure_ascii=False, indent=2)}",
                    }
                ]
            }
        elif name == "ariadne_graph":
            entity = arguments.get("entity", "")
            depth = arguments.get("depth", 2)
            results = self._tool_graph_query({"entity": entity, "depth": depth})

            return {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Explore knowledge graph starting from: {entity}\n\nGraph data:\n{json.dumps(results, ensure_ascii=False, indent=2)}",
                    }
                ]
            }
        elif name == "ariadne_context":
            topic = arguments.get("topic", "")
            results = self._tool_search({"query": topic, "limit": 10})

            return {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Get context about: {topic}\n\nRelevant information from knowledge base:\n{json.dumps(results, ensure_ascii=False, indent=2)}",
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown prompt: {name}")

    def run_stdio(self):
        """Run server using stdio transport."""
        import sys

        logger.info("Starting Ariadne MCP Server (stdio mode)")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)

                if response.get("id") is not None:
                    print(json.dumps(response), flush=True)

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {line}")
            except Exception as e:
                logger.error(f"Error processing request: {e}")

    def run(self, host: str = "127.0.0.1", port: int = 8765):
        """Run server using HTTP transport."""
        import http.server
        import socketserver

        class MCPRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                try:
                    request = json.loads(body)
                    response = self.server.server.handle_request(request)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())

                except Exception as e:
                    logger.error(f"Error: {e}")
                    self.send_response(500)
                    self.end_headers()

        class MCTPServer(socketserver.TCPServer):
            allow_reuse_address = True

        with MCTPServer((host, port), MCPRequestHandler) as httpd:
            logger.info(f"Ariadne MCP Server running on {host}:{port}")
            httpd.serve_forever()


def create_server(
    vector_store_path: str = "./data/vectors",
    graph_db_path: str = "./data/graph.db",
    config_path: Optional[str] = None,
) -> AriadneMCPServer:
    """Factory function to create an Ariadne MCP server."""
    return AriadneMCPServer(
        vector_store_path=vector_store_path,
        graph_db_path=graph_db_path,
        config_path=config_path,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ariadne MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--vectors", default="./data/vectors", help="Vector store path")
    parser.add_argument("--graph", default="./data/graph.db", help="Graph database path")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="Transport mode")
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    server = create_server(
        vector_store_path=args.vectors,
        graph_db_path=args.graph,
        config_path=args.config,
    )

    if args.transport == "stdio":
        server.run_stdio()
    else:
        server.run(host=args.host, port=args.port)
