"""
Ariadne MCP Server - Model Context Protocol integration for AI memory.

This module provides an MCP-compatible server that exposes Ariadne's
capabilities (search, ingest, graph) as MCP tools, resources, and prompts.

MCP Protocol Version: 2024-11-05

Features:
- WAL Audit Logging: Complete operation audit trail
- Parameter Schema Validation: JSON Schema-based validation
- Cache Invalidation Detection: inode/mtime based cache management
"""

from .server import AriadneMCPServer, create_server
from .resources import (
    AriadneResourceManager,
    DocumentResource,
    GraphResource,
    ConfigResource,
)
from .tools import (
    AriadneToolHandler,
    IngestTool,
    SearchTool,
    GraphQueryTool,
    StatsTool,
)
from .prompts import (
    AriadnePromptManager,
    SearchPrompt,
    IngestPrompt,
    GraphPrompt,
)
from .wal import (
    WALAuditLogger,
    WALEntry,
    OperationType,
    LogLevel,
)
from .validation import (
    SchemaValidator,
    ValidatedTool,
    ValidationError,
    FieldError,
)
from .cache import (
    CacheInvalidationDetector,
    CacheEntry,
    MCPCacheManager,
)

__all__ = [
    # Core server
    "AriadneMCPServer",
    "create_server",
    # Resources
    "AriadneResourceManager",
    "DocumentResource",
    "GraphResource",
    "ConfigResource",
    # Tools
    "AriadneToolHandler",
    "IngestTool",
    "SearchTool",
    "GraphQueryTool",
    "StatsTool",
    # Prompts
    "AriadnePromptManager",
    "SearchPrompt",
    "IngestPrompt",
    "GraphPrompt",
    # WAL Audit
    "WALAuditLogger",
    "WALEntry",
    "OperationType",
    "LogLevel",
    # Validation
    "SchemaValidator",
    "ValidatedTool",
    "ValidationError",
    "FieldError",
    # Cache
    "CacheInvalidationDetector",
    "CacheEntry",
    "MCPCacheManager",
]
