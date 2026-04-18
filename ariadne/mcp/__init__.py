"""
Ariadne MCP Server - Model Context Protocol integration for AI memory.

This module provides an MCP-compatible server that exposes Ariadne's
capabilities (search, ingest, graph) as MCP tools, resources, and prompts.

MCP Protocol Version: 2024-11-05
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

__all__ = [
    "AriadneMCPServer",
    "create_server",
    "AriadneResourceManager",
    "DocumentResource",
    "GraphResource",
    "ConfigResource",
    "AriadneToolHandler",
    "IngestTool",
    "SearchTool",
    "GraphQueryTool",
    "StatsTool",
    "AriadnePromptManager",
    "SearchPrompt",
    "IngestPrompt",
    "GraphPrompt",
]
