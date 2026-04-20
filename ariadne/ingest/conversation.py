"""
Conversation history ingestor for Ariadne.

Handles exported chat logs from ChatGPT, Claude, and DeepSeek.
Supports their respective JSON export formats.

For non-conversation JSON files (e.g. localization files, config files),
falls back to serializing the JSON content as readable text chunks.
"""

import json
from pathlib import Path
from typing import Any

from ariadne.ingest.base import BaseIngestor, SourceType


def _read_text_robust(path) -> str:
    """Read text from a file, trying multiple encodings.

    Tries in order: utf-8-sig (handles BOM), utf-8, gb18030 (CJK),
    latin-1 (universal fallback).

    Args:
        path: Path to the file to read (str or Path).

    Returns:
        Decoded text content.

    Raises:
        UnicodeDecodeError: If all encodings fail (extremely rare).
    """
    from pathlib import Path as _Path
    if isinstance(path, str):
        path = _Path(path)
    encodings = ["utf-8-sig", "utf-8", "gb18030", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, ValueError):
            continue
    # Final fallback: ignore errors
    return path.read_text(encoding="utf-8", errors="replace")


class ConversationIngestor(BaseIngestor):
    """
    Ingest conversation export files from AI assistants.

    Supported formats:
    - ChatGPT JSON export
    - Claude JSON export
    - DeepSeek JSON export
    - Generic message JSON (list of {"role", "content"} objects)

    For non-conversation JSON files (e.g. game localization, config),
    the entire JSON content is serialized as readable text chunks,
    preserving key-value structure for searchability.

    Each turn (user + assistant pair) becomes a document chunk,
    preserving the conversational context.
    """

    source_type = SourceType.CONVERSATION

    def _extract(self, path: Path) -> list[str]:
        content = _read_text_robust(path)
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON file: {path}")

        format_type = self.__detect_format(data, path.name)
        messages = self.__extract_messages(data, format_type)

        # If messages were found, build conversation chunks
        if messages:
            chunks = []
            current_turn = []

            for msg in messages:
                role = msg.get("role", "unknown")
                msg_content = msg.get("content", "")

                if not msg_content:
                    continue

                formatted = f"[{role.upper()}]\n{msg_content}"
                current_turn.append(formatted)

                if role == "user" and len(current_turn) > 1:
                    chunks.append("\n\n".join(current_turn))
                    current_turn = [current_turn[-1]]

            if current_turn:
                chunks.append("\n\n".join(current_turn))

            if chunks:
                return chunks

        # Fallback: non-conversation JSON — serialize as readable text
        return self._json_to_text_chunks(data, path.name)

    def _json_to_text_chunks(self, data: Any, filename: str) -> list[str]:
        """Convert arbitrary JSON data into searchable text chunks.

        For dict: flatten key-value pairs into "key: value" lines.
        For list: group items into chunks of ~50 entries.
        For scalar: wrap in a single chunk.
        """
        chunks = []

        if isinstance(data, dict):
            # Flatten dict into key: value lines, chunked by size
            lines = []
            for key, value in data.items():
                val_str = json.dumps(value, ensure_ascii=False)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                lines.append(f"{key}: {val_str}")

            # Chunk lines into groups of ~50 lines or 5000 chars
            current_lines = []
            current_len = 0
            for line in lines:
                current_lines.append(line)
                current_len += len(line)
                if len(current_lines) >= 50 or current_len >= 5000:
                    chunks.append("\n".join(current_lines))
                    current_lines = []
                    current_len = 0
            if current_lines:
                chunks.append("\n".join(current_lines))

        elif isinstance(data, list):
            # Group list items into chunks
            items = [json.dumps(item, ensure_ascii=False) for item in data]
            current_items = []
            current_len = 0
            for item_str in items:
                current_items.append(item_str)
                current_len += len(item_str)
                if len(current_items) >= 50 or current_len >= 5000:
                    chunks.append("\n".join(current_items))
                    current_items = []
                    current_len = 0
            if current_items:
                chunks.append("\n".join(current_items))

        else:
            # Scalar value (string, number, bool, null)
            chunks.append(json.dumps(data, ensure_ascii=False))

        return chunks if chunks else []

    def __detect_format(self, data: Any, filename: str) -> str:
        """Detect which chat platform this export is from."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                if "role" in data[0] and "content" in data[0]:
                    return "generic"
        elif isinstance(data, dict):
            if "conversations" in data:
                return "chatgpt"
            if "mapping" in data:
                return "claude"
            if "messages" in data:
                return "deepseek"
        return "generic"

    def __extract_messages(self, data: Any, format_type: str) -> list[dict[str, str]]:
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
