"""
Code ingestor for Ariadne.

Extracts structured content from source code files, including:
- Function/class names and signatures
- Docstrings (Google, NumPy, reStructuredText formats)
- Inline comments
- Decorators and type hints
"""

import ast
from pathlib import Path
from typing import List, Optional

from ariadne.ingest.base import BaseIngestor, SourceType


class CodeIngestor(BaseIngestor):
    """
    Ingest source code files and extract semantic units.

    Uses AST parsing for Python; regex-based for other languages.
    Extracts functions, classes, and their docstrings/comments
    as searchable knowledge chunks.
    """

    source_type = SourceType.CODE

    # Mapping of file extensions to parser methods
    PARSERS = {
        ".py": "_parse_python",
        ".java": "_parse_java",
        ".cpp": "_parse_cpp",
        ".c": "_parse_c",
        ".js": "_parse_js",
        ".ts": "_parse_js",  # TS uses same AST-lite approach
        ".jsx": "_parse_js",
        ".tsx": "_parse_js",
    }

    def _extract(self, path: Path) -> List[str]:
        suffix = path.suffix.lower()
        parser_name = self.PARSERS.get(suffix)

        if parser_name is None:
            # Fall back to plain text with basic extraction
            return self._extract_plain(path)

        parser = getattr(self, parser_name)
        return parser(path)

    def _parse_python(self, path: Path) -> List[str]:
        """Parse Python file using the AST."""
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return self._extract_plain(path)

        chunks = []
        for node in ast.walk(tree):
            chunk = self._extract_python_node(node, source)
            if chunk:
                chunks.append(chunk)
        return chunks

    def _extract_python_node(self, node: ast.AST, source: str) -> Optional[str]:
        """Extract docstring and signature from a Python AST node."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name

            # Get docstring
            docstring = ast.get_docstring(node) or ""

            # Get parameter names
            sig_parts = []
            if hasattr(node, "args") and node.args:
                args = node.args
                arg_names = [a.arg for a in args.args]
                sig_parts = arg_names[:6]  # cap at 6 params

            parts = [f"## {name}"]

            # Signature line
            if sig_parts:
                params = ", ".join(sig_parts)
                if len(params) > 100:
                    params = ", ".join(sig_parts[:4]) + ", ..."
                parts.append(f"Signature: {name}({params})")

            # Docstring (truncated)
            if docstring:
                docstring = docstring.strip()[:500]
                parts.append(f"Doc: {docstring}")

            # Return type hint
            if hasattr(node, "returns") and node.returns:
                parts.append(f"Returns: (type hint present)")

            return "\n".join(parts)

        return None

    def _parse_java(self, path: Path) -> List[str]:
        """Parse Java using regex-based extraction."""
        content = path.read_text(encoding="utf-8")
        import re

        chunks = []
        # Match method signatures
        method_pattern = re.compile(
            r"(?:public|private|protected)?\s*(?:static)?\s*[\w<>[\]]+\s+(\w+)\s*\(([^)]*)\)"
        )

        seen = set()
        for match in method_pattern.finditer(content):
            method_name = match.group(1)
            params = match.group(2).strip()[:100]

            if not method_name or method_name in seen or method_name.startswith("_"):
                continue
            seen.add(method_name)

            # Try to find Javadoc comment above this method
            start = max(0, match.start() - 300)
            snippet = content[start:match.start()]
            comment_match = re.search(r"/\*\*\s*([^*]*(?:\*(?!/)[^*]*)*)", snippet, re.DOTALL)
            comment = ""
            if comment_match:
                comment = comment_match.group(1).replace("*", "").strip()[:200]

            chunk = f"## {method_name}({params})\n"
            if comment:
                chunk += f"Doc: {comment}\n"
            chunk += f"Source: {path.name}"
            chunks.append(chunk)

        return chunks

    def _parse_cpp(self, path: Path) -> List[str]:
        """Parse C++ using regex-based extraction."""
        return self._parse_c(path)

    def _parse_c(self, path: Path) -> List[str]:
        """Parse C using regex-based extraction."""
        content = path.read_text(encoding="utf-8")
        import re

        chunks = []
        # Match function declarations
        func_pattern = re.compile(
            r"(?:void|int|char|float|double|bool|auto|struct|class|unsigned)\s*[*&]?\s*(\w+)\s*\(([^)]*)\)\s*(?:const)?\s*;"
        )

        seen = set()
        for match in func_pattern.finditer(content):
            name = match.group(1)
            params = match.group(2).strip()[:80]

            if not name or name in seen or name.startswith("_") or name in ("if", "while", "for", "switch"):
                continue
            seen.add(name)
            chunk = f"## {name}({params})\nSource: {path.name}"
            chunks.append(chunk)

        return chunks

    def _parse_js(self, path: Path) -> List[str]:
        """Parse JavaScript/TypeScript using regex-based extraction."""
        content = path.read_text(encoding="utf-8")
        import re

        chunks = []
        seen = set()

        # Match: function name(...) or async function name(...)
        for match in re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = match.group(2).strip()[:80]
            if name and name not in seen:
                seen.add(name)
                chunks.append(f"## {name}({params})\nSource: {path.name}")

        # Match: const/let/var name = (...) => ... or const/let/var name = async (...) => ...
        for match in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>", content):
            name = match.group(1)
            if name and name not in seen:
                seen.add(name)
                chunks.append(f"## {name}(...)\nSource: {path.name}")

        return chunks

    def _extract_plain(self, path: Path) -> List[str]:
        """Fallback: strip comments and treat remaining as searchable text."""
        content = path.read_text(encoding="utf-8")
        import re

        # Strip single-line comments
        lines = re.sub(r"//.*", "", content)
        # Strip multi-line comments
        lines = re.sub(r"/\*.*?\*/", "", lines, flags=re.DOTALL)
        # Strip doc strings
        lines = re.sub(r'""".*?"""', "", lines, flags=re.DOTALL)
        lines = re.sub(r"'''.*?'''", "", lines, flags=re.DOTALL)

        code_lines = [l.strip() for l in lines.split("\n") if l.strip()]
        return self.chunk_text("\n".join(code_lines), max_chars=500, overlap=50)
