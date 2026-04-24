"""
Privacy — strip private / system tags from text before storage or injection.

Mirrors Claude-Mem's tag-stripping.ts logic, adapted for Python.

Tags stripped:
    <private>...</private>          — user-marked private content
    <ariadne-context>...</ariadne-context>  — injected context (prevent re-summarization)
    <system_instruction>...</system_instruction>
    <system-reminder>...</system-reminder>
    <system_reminder>...</system_reminder>
"""

from __future__ import annotations

import re
from typing import Optional


# Tags to strip entirely (including content inside)
_STRIP_TAGS = [
    "private",
    "ariadne-context",
    "ariadne_context",
    "system_instruction",
    "system-reminder",
    "system_reminder",
]

# Compiled patterns (case-insensitive, DOTALL for multiline)
_PATTERNS = [
    re.compile(
        r"<" + tag + r"(?:\s[^>]*)?>.*?</" + tag + r">",
        re.IGNORECASE | re.DOTALL,
    )
    for tag in _STRIP_TAGS
]

# Strip self-closing variants too
_SELF_CLOSING = [
    re.compile(r"<" + tag + r"(?:\s[^>]*)?/>", re.IGNORECASE)
    for tag in _STRIP_TAGS
]


def strip_private_tags(text: Optional[str]) -> str:
    """
    Remove all private/system tags from text.

    Args:
        text: Input text (may be None).

    Returns:
        Cleaned text with private content removed.
    """
    if not text:
        return ""

    result = text
    for pattern in _PATTERNS:
        result = pattern.sub("", result)
    for pattern in _SELF_CLOSING:
        result = pattern.sub("", result)

    # Clean up excess blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def contains_private_content(text: Optional[str]) -> bool:
    """Check whether text contains any private tags."""
    if not text:
        return False
    for tag in _STRIP_TAGS:
        if re.search(r"<" + tag + r"(?:\s[^>]*)?>", text, re.IGNORECASE):
            return True
    return False


def wrap_context_injection(context: str) -> str:
    """
    Wrap injected context in a tag so it won't be re-summarized
    in a future session.

    Claude-Mem uses <claude-mem-context>; Ariadne uses <ariadne-context>.
    """
    return f"<ariadne-context>\n{context}\n</ariadne-context>"
