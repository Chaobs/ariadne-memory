"""
Ariadne Wiki Models — Data structures for the LLM Wiki feature.

Implements the Karpathy LLM Wiki pattern:
- Three-layer architecture: Raw Sources → Wiki → Schema
- Three core operations: Ingest, Query, Lint
- index.md / log.md / overview.md
- [[wikilink]] cross-references
- YAML frontmatter on every page
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class WikiPageType(str, Enum):
    """Types of wiki pages."""
    SOURCE = "source"
    ENTITY = "entity"
    CONCEPT = "concept"
    COMPARISON = "comparison"
    QUERY = "query"
    SYNTHESIS = "synthesis"
    INDEX = "index"
    LOG = "log"
    OVERVIEW = "overview"


class LintIssueType(str, Enum):
    """Types of lint issues."""
    ORPHAN = "orphan"
    BROKEN_LINK = "broken-link"
    NO_OUTLINKS = "no-outlinks"
    CONTRADICTION = "contradiction"
    STALE = "stale"
    MISSING_PAGE = "missing-page"
    SUGGESTION = "suggestion"


class LintSeverity(str, Enum):
    """Severity levels for lint issues."""
    WARNING = "warning"
    INFO = "info"


@dataclass
class WikiFrontmatter:
    """YAML frontmatter for a wiki page."""
    page_type: WikiPageType = WikiPageType.CONCEPT
    title: str = ""
    created: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    updated: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    tags: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Serialize frontmatter to YAML string."""
        lines = ["---"]
        lines.append(f"type: {self.page_type.value}")
        if self.title:
            lines.append(f'title: "{self.title}"')
        lines.append(f"created: {self.created}")
        lines.append(f"updated: {self.updated}")
        lines.append(f"tags: {self.tags}")
        lines.append(f"related: {self.related}")
        lines.append(f"sources: {self.sources}")
        lines.append("---")
        return "\n".join(lines)

    @classmethod
    def from_yaml(cls, text: str) -> "WikiFrontmatter":
        """Parse frontmatter from YAML string."""
        import re
        fm = cls()
        if not text.startswith("---"):
            return fm

        # Find closing ---
        end_match = re.search(r'\n---\n?', text[3:])
        if not end_match:
            return fm

        body = text[3:end_match.start() + 3]

        # Parse type — accept both "type: value" and "type:value"
        m = re.search(r'^type:\s*(\S+)', body, re.MULTILINE)
        if m:
            try:
                fm.page_type = WikiPageType(m.group(1))
            except ValueError:
                pass

        # Parse title — accept quoted or unquoted, with or without space after colon
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', body, re.MULTILINE)
        if m:
            fm.title = m.group(1)

        # Parse dates
        m = re.search(r'^created:\s*(\S+)', body, re.MULTILINE)
        if m:
            fm.created = m.group(1)
        m = re.search(r'^updated:\s*(\S+)', body, re.MULTILINE)
        if m:
            fm.updated = m.group(1)

        # Parse lists
        m = re.search(r'^tags:\s*\[(.*?)\]', body, re.MULTILINE)
        if m:
            fm.tags = [t.strip().strip('"\'') for t in m.group(1).split(",") if t.strip()]
        m = re.search(r'^related:\s*\[(.*?)\]', body, re.MULTILINE)
        if m:
            fm.related = [t.strip().strip('"\'') for t in m.group(1).split(",") if t.strip()]
        m = re.search(r'^sources:\s*\[(.*?)\]', body, re.MULTILINE)
        if m:
            fm.sources = [t.strip().strip('"\'') for t in m.group(1).split(",") if t.strip()]

        return fm


@dataclass
class WikiPage:
    """A single wiki page with frontmatter and content."""
    path: str  # relative path within wiki/ (e.g., "entities/my-entity.md")
    frontmatter: WikiFrontmatter = field(default_factory=WikiFrontmatter)
    content: str = ""  # body content (after frontmatter)

    @property
    def slug(self) -> str:
        """Page slug (filename without extension)."""
        import os
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def full_content(self) -> str:
        """Complete page with frontmatter + body."""
        return f"{self.frontmatter.to_yaml()}\n\n{self.content}"

    @property
    def wikilinks(self) -> List[str]:
        """Extract [[wikilinks]] from content."""
        import re
        pattern = r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]'
        return [m.strip() for m in re.findall(pattern, self.content)]


@dataclass
class LintResult:
    """Result of a lint check."""
    issue_type: LintIssueType
    severity: LintSeverity
    page: str
    detail: str
    affected_pages: List[str] = field(default_factory=list)


@dataclass
class WikiProject:
    """A wiki project directory structure."""
    root_path: str  # absolute path to the project root
    name: str = ""

    @property
    def raw_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "raw")

    @property
    def sources_dir(self) -> str:
        import os
        return os.path.join(self.raw_dir, "sources")

    @property
    def assets_dir(self) -> str:
        import os
        return os.path.join(self.raw_dir, "assets")

    @property
    def wiki_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki")

    @property
    def schema_path(self) -> str:
        import os
        return os.path.join(self.root_path, "schema.md")

    @property
    def purpose_path(self) -> str:
        import os
        return os.path.join(self.root_path, "purpose.md")

    @property
    def index_path(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "index.md")

    @property
    def log_path(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "log.md")

    @property
    def overview_path(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "overview.md")

    @property
    def entities_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "entities")

    @property
    def concepts_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "concepts")

    @property
    def wiki_sources_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "sources")

    @property
    def queries_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "queries")

    @property
    def synthesis_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "synthesis")

    @property
    def comparisons_dir(self) -> str:
        import os
        return os.path.join(self.root_path, "wiki", "comparisons")


@dataclass
class IngestResult:
    """Result of a wiki ingest operation."""
    source_file: str
    pages_written: List[str] = field(default_factory=list)
    review_items: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cached: bool = False


@dataclass
class QueryResult:
    """Result of a wiki query operation."""
    question: str
    answer: str
    cited_pages: List[str] = field(default_factory=list)
    saved_to: Optional[str] = None  # path if answer was saved to wiki
