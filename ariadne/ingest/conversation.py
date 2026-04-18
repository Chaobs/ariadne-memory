"""
Conversation history ingestor for Ariadne.

Handles exported chat logs from ChatGPT, Claude, and DeepSeek.
Supports their respective JSON export formats.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

from ariadne.ingest.base import BaseIngestor, Document, SourceType


class ConversationIngestor(BaseIngestor):
    """
    Ingest conversation export files from AI assistants.

    Supported formats:
    - ChatGPT JSON export
    - Claude JSON export
    - DeepSeek JSON export
    - Generic message JSON (list of {"role", "content"} objects)

    Each turn (user + assistant pair) becomes a document chunk,
    preserving the conversational context.
    """

    source_type = SourceType.CONVERSATION

    # Known export format schemas
    KNOWN_FORMATS = {
        "chatgpt": _detect_chatgpt,
        "claude": _detect_claude,
        "deepseek": _detect_deepseek,
    }

    def _extract(self, path: Path) -> List[str]:
        content = path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON file: {path}")

        # Detect format
        format_type = self._detect_format(data, path.name)
        messages = self._extract_messages(data, format_type)

        # Convert messages to searchable chunks
        chunks = []
        current_turn = []

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if not content:
                continue

            # Format as "[Role]: content"
            formatted = f"[{role.upper()}]\n{content}"
            current_turn.append(formatted)

            # When we hit the next user message, flush this turn
            if role == "user" and len(current_turn) > 1:
                chunks.append("\n\n".join(current_turn))
                current_turn = [current_turn[-1]]  # keep last assistant context

        if current_turn:
            chunks.append("\n\n".join(current_turn))

        return chunks if chunks else []

    def _detect_format(self, data: Any, filename: str) -> str:
        """Detect which chat platform this export is from."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # Generic message list
                if "role" in data[0] and "content" in data[0]:
                    return "generic"
        elif isinstance(data, dict):
            # Check for known keys
            if "conversations" in data:
                return "chatgpt"
            if "mapping" in data:
                return "claude"
            if "messages" in data:
                return "deepseek"

        return "generic"

    def _extract_messages(self, data: Any, format_type: str) -> List[Dict[str, str]]:
        """Extract a flat list of {role, content} messages."""
        messages = []

        if format_type == "chatgpt":
            for conv in data.get("conversations", []):
                role = conv.get("role", "user")
                content = conv.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        elif format_type == "claude":
            mapping = data.get("mapping", {})
            for node in mapping.values():
                msg = node.get("message", {})
                role = msg.get("role", "user")
                content_parts = []
                content_arr = msg.get("content", [])
                if isinstance(content_arr, list):
                    for part in content_arr:
                        if isinstance(part, dict) and part.get("type") == "text":
                            content_parts.append(part.get("text", ""))
                elif isinstance(content_arr, str):
                    content_parts.append(content_arr)
                content = "\n".join(content_parts)
                if content:
                    messages.append({"role": role, "content": content})

        elif format_type == "deepseek":
            for msg in data.get("messages", []):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        elif format_type == "generic":
            if isinstance(data, list):
                messages = [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in data
                    if m.get("content")
                ]

        return messages


# Helper functions for format detection (need to be at module level for isinstance checks)
def _detect_chatgpt(data):
    return isinstance(data, dict) and "conversations" in data


def _detect_claude(data):
    return isinstance(data, dict) and "mapping" in data


def _detect_deepseek(data):
    return isinstance(data, dict) and "messages" in data
