"""
MCP Prompt templates for Ariadne.

Prompts provide reusable templates for common knowledge base interactions.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import json

from .server import MCPPrompt


@dataclass
class SearchPrompt(MCPPrompt):
    """Prompt template for searching the knowledge base."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_search",
            description="Search the Ariadne knowledge base with a natural language query",
            arguments=[
                {
                    "name": "query",
                    "description": "The search query in natural language",
                    "required": True,
                },
                {
                    "name": "limit",
                    "description": "Maximum number of results to return",
                    "required": False,
                },
            ],
        )
        self._vector_store = vector_store

    def generate(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Generate prompt content for a search query."""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant with access to a comprehensive knowledge base called Ariadne. "
                    "The user is asking a question. Search the knowledge base and provide a helpful, accurate response "
                    "based on the retrieved information. Always cite your sources.",
                },
                {
                    "role": "user",
                    "content": f"Please search the knowledge base and answer: {query}\n\n"
                    f"Return up to {limit} relevant results with their sources.",
                },
            ]
        }


@dataclass
class IngestPrompt(MCPPrompt):
    """Prompt template for ingesting content."""

    def __init__(self):
        super().__init__(
            name="ariadne_ingest",
            description="Template for ingesting documents or URLs into the knowledge base",
            arguments=[
                {
                    "name": "source",
                    "description": "File path or URL to ingest",
                    "required": True,
                },
                {
                    "name": "description",
                    "description": "Brief description of the content",
                    "required": False,
                },
            ],
        )

    def generate(self, source: str, description: str = "") -> Dict[str, Any]:
        """Generate prompt content for ingestion."""
        desc_text = f"\nDescription: {description}" if description else ""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are helping to organize information into a knowledge base.",
                },
                {
                    "role": "user",
                    "content": f"Please ingest the following content into the knowledge base:\n\n"
                    f"Source: {source}{desc_text}\n\n"
                    f"The content will be processed, and entities will be extracted for the knowledge graph.",
                },
            ]
        }


@dataclass
class GraphPrompt(MCPPrompt):
    """Prompt template for exploring the knowledge graph."""

    def __init__(self, graph_storage=None):
        super().__init__(
            name="ariadne_graph",
            description="Explore entity relationships in the knowledge graph",
            arguments=[
                {
                    "name": "entity",
                    "description": "Starting entity name or concept",
                    "required": True,
                },
                {
                    "name": "depth",
                    "description": "Depth of graph traversal (how many levels of connections to explore)",
                    "required": False,
                },
            ],
        )
        self._graph_storage = graph_storage

    def generate(self, entity: str, depth: int = 2) -> Dict[str, Any]:
        """Generate prompt content for graph exploration."""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are exploring a knowledge graph that maps relationships between entities. "
                    "The graph shows how concepts, people, places, and things are connected through various relationships. "
                    "Use this structure to provide comprehensive answers that show the connections between ideas.",
                },
                {
                    "role": "user",
                    "content": f"Please explore the knowledge graph starting from: {entity}\n\n"
                    f"Show connections up to {depth} degrees of separation and explain how these entities are related.",
                },
            ]
        }


@dataclass
class ContextPrompt(MCPPrompt):
    """Prompt template for getting relevant context."""

    def __init__(self, vector_store=None):
        super().__init__(
            name="ariadne_context",
            description="Get relevant context from the knowledge base for a given topic or question",
            arguments=[
                {
                    "name": "topic",
                    "description": "The topic or question to get context about",
                    "required": True,
                },
                {
                    "name": "sources",
                    "description": "Comma-separated list of source types to prioritize (e.g., 'pdf,markdown,web')",
                    "required": False,
                },
            ],
        )
        self._vector_store = vector_store

    def generate(self, topic: str, sources: str = "") -> Dict[str, Any]:
        """Generate prompt content for context retrieval."""
        source_filter = ""
        if sources:
            source_filter = f"\n\nPrioritize sources of types: {sources}"

        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant with access to a comprehensive knowledge base. "
                    "The following context has been retrieved from the knowledge base to help answer the user's question. "
                    "Use this context to provide an accurate and well-informed response.",
                },
                {
                    "role": "user",
                    "content": f"Get relevant context from the knowledge base about: {topic}{source_filter}\n\n"
                    f"Provide the most relevant information that helps answer questions about this topic.",
                },
            ]
        }


@dataclass
class ComparePrompt(MCPPrompt):
    """Prompt template for comparing concepts in the knowledge base."""

    def __init__(self):
        super().__init__(
            name="ariadne_compare",
            description="Compare two or more concepts, entities, or topics from the knowledge base",
            arguments=[
                {
                    "name": "items",
                    "description": "Comma-separated list of items to compare",
                    "required": True,
                },
                {
                    "name": "aspect",
                    "description": "Specific aspect to compare (leave empty for general comparison)",
                    "required": False,
                },
            ],
        )

    def generate(self, items: str, aspect: str = "") -> Dict[str, Any]:
        """Generate prompt content for comparison."""
        aspect_text = f"\n\nFocus on comparing: {aspect}" if aspect else ""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are comparing concepts from a knowledge base. "
                    "Identify similarities, differences, and relationships between the items being compared.",
                },
                {
                    "role": "user",
                    "content": f"Please compare the following items from the knowledge base:\n\n"
                    f"Items: {items}{aspect_text}\n\n"
                    f"Highlight key similarities, differences, and how they relate to each other.",
                },
            ]
        }


class AriadnePromptManager:
    """Manages all MCP prompts for Ariadne."""

    def __init__(
        self,
        vector_store=None,
        graph_storage=None,
    ):
        self._prompts: Dict[str, MCPPrompt] = {}
        self._vector_store = vector_store
        self._graph_storage = graph_storage

        self._register_builtin_prompts()

    def _register_builtin_prompts(self):
        """Register built-in prompts."""
        self._prompts["ariadne_search"] = SearchPrompt(vector_store=self._vector_store)
        self._prompts["ariadne_ingest"] = IngestPrompt()
        self._prompts["ariadne_graph"] = GraphPrompt(graph_storage=self._graph_storage)
        self._prompts["ariadne_context"] = ContextPrompt(vector_store=self._vector_store)
        self._prompts["ariadne_compare"] = ComparePrompt()

    def register(self, name: str, prompt: MCPPrompt):
        """Register a new prompt."""
        self._prompts[name] = prompt

    def get(self, name: str) -> Optional[MCPPrompt]:
        """Get prompt by name."""
        return self._prompts.get(name)

    def list(self) -> List[Dict[str, Any]]:
        """List all prompts."""
        return [prompt.to_dict() for prompt in self._prompts.values()]

    def generate(self, name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Generate prompt content."""
        prompt = self._prompts.get(name)
        if not prompt or not hasattr(prompt, "generate"):
            return None
        return prompt.generate(**kwargs)

    def list_detailed(self) -> List[Dict[str, Any]]:
        """List all prompts with full details."""
        result = []
        for prompt in self._prompts.values():
            prompt_dict = prompt.to_dict()
            if hasattr(prompt, "arguments"):
                prompt_dict["arguments"] = prompt.arguments
            result.append(prompt_dict)
        return result
