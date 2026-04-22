"""
Ariadne Closet Index - AAAK (Almost All Answer Key) compressed indexing.

Provides fast LLM-accessible memory indexing using MemPalace's AAAK format:
- topic|entities|→drawer_ids
- Enables LLM to quickly locate relevant "drawers" (memory containers)
- Compressed format for minimal token overhead

Inspired by MemPalace's Closet system.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class IndexFormat(str, Enum):
    """AAAK index format types."""
    AAAK = "aaak"  # Main format: topic|entities|→drawer_ids
    TOPIC_ONLY = "topic"  # topic|→drawer_ids
    ENTITY_ONLY = "entity"  # |entities|→drawer_ids


@dataclass
class DrawerEntry:
    """
    A memory drawer containing related information.

    Drawers are the basic storage units in the closet system.
    They can contain documents, entities, or condensed memories.
    """
    drawer_id: str
    content: str
    content_type: str = "document"  # document, entity, summary, conversation
    tags: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)  # Entity names in this drawer
    topics: List[str] = field(default_factory=list)  # Topics covered
    token_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = len(self.content) // 4

    def to_aaak(self) -> str:
        """
        Convert drawer to AAAK format string.

        Returns:
            AAAK string: topic|entities|→drawer_id
        """
        topic_part = "+".join(self.topics) if self.topics else ""
        entity_part = "+".join(self.entities) if self.entities else ""
        return f"{topic_part}|{entity_part}|→{self.drawer_id}"

    @classmethod
    def from_aaak(cls, aaak: str) -> Tuple[List[str], List[str], str]:
        """Parse AAAK string back to components."""
        # Pattern: topic_part|entity_part|→drawer_id
        match = re.match(r"([^|]*)\|([^|]*)\|→(.+)", aaak)
        if not match:
            return [], [], ""

        topics = match.group(1).split("+") if match.group(1) else []
        entities = match.group(2).split("+") if match.group(2) else []
        drawer_id = match.group(3)

        return topics, entities, drawer_id


@dataclass
class AAKEntry:
    """
    Almost All Answer Key entry.

    Maps search queries or topics to relevant drawers.
    Used for quick LLM-based drawer lookup.
    """
    aak_id: str
    keywords: List[str]  # Keywords that trigger this entry
    topic: str  # Primary topic
    drawer_ids: List[str]  # Related drawers
    score: float = 0.5  # Relevance score
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_aaak(self) -> str:
        """Convert to AAAK format: topic|entities|→drawer_ids"""
        keyword_part = "+".join(self.keywords) if self.keywords else ""
        drawer_part = "+".join(self.drawer_ids) if self.drawer_ids else ""
        return f"{self.topic}|{keyword_part}|→{drawer_part}"


class ClosetIndex:
    """
    Closet Index with AAAK compressed format.

    Provides fast memory indexing and retrieval:
    - Creates AAAK index entries for LLM consumption
    - Maps topics/entities to drawers
    - Enables quick drawer lookup for context retrieval

    Usage:
        closet = ClosetIndex("./data/closet.db")
        closet.add_drawer(content="About Python...", topics=["python"], entities=["Guido"])
        aak_index = closet.build_aak_index()
        drawers = closet.lookup("python programming")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize Closet Index.

        Args:
            db_path: Path to SQLite database. Defaults to .ariadne/closet.db
        """
        if db_path is None:
            db_path = str(Path.cwd() / ".ariadne" / "closet.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._drawers: Dict[str, DrawerEntry] = {}
        self._aak_index: Dict[str, AAKEntry] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Drawers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drawers (
                drawer_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'document',
                tags TEXT,
                entities TEXT,
                topics TEXT,
                token_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)

        # AAAK index table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aak_index (
                aak_id TEXT PRIMARY KEY,
                keywords TEXT,
                topic TEXT,
                drawer_ids TEXT,
                score REAL DEFAULT 0.5,
                created_at TEXT
            )
        """)

        # Inverted index for entities
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_index (
                entity_name TEXT,
                drawer_id TEXT,
                frequency INTEGER DEFAULT 1,
                PRIMARY KEY (entity_name, drawer_id)
            )
        """)

        # Inverted index for topics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_index (
                topic TEXT,
                drawer_id TEXT,
                frequency INTEGER DEFAULT 1,
                PRIMARY KEY (topic, drawer_id)
            )
        """)

        # Keywords index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_index (
                keyword TEXT,
                drawer_id TEXT,
                frequency INTEGER DEFAULT 1,
                PRIMARY KEY (keyword, drawer_id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_index ON entity_index(entity_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic_index ON topic_index(topic)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keyword_index ON keyword_index(keyword)")

        conn.commit()
        conn.close()

        logger.info(f"Closet index initialized at {self.db_path}")

    def _generate_drawer_id(self, content: str, prefix: str = "drw") -> str:
        """Generate stable drawer ID from content."""
        hash_input = f"{content[:100]}{datetime.now(timezone.utc).isoformat()}"
        return f"{prefix}_{hashlib.sha256(hash_input.encode()).hexdigest()[:12]}"

    def add_drawer(
        self,
        content: str,
        content_type: str = "document",
        tags: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        drawer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DrawerEntry:
        """
        Add a drawer to the closet.

        Args:
            content: The main content of the drawer
            content_type: Type of content (document, entity, summary, conversation)
            tags: Associated tags
            entities: Entity names mentioned
            topics: Topics covered
            drawer_id: Optional custom drawer ID
            metadata: Additional metadata

        Returns:
            The created DrawerEntry
        """
        tags = tags or []
        entities = entities or []
        topics = topics or []
        metadata = metadata or {}

        drawer_id = drawer_id or self._generate_drawer_id(content)
        drawer = DrawerEntry(
            drawer_id=drawer_id,
            content=content,
            content_type=content_type,
            tags=tags,
            entities=entities,
            topics=topics,
            metadata=metadata,
        )

        self._drawers[drawer_id] = drawer

        # Persist to database
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO drawers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            drawer.drawer_id,
            drawer.content,
            drawer.content_type,
            json.dumps(drawer.tags),
            json.dumps(drawer.entities),
            json.dumps(drawer.topics),
            drawer.token_count,
            drawer.created_at,
            drawer.updated_at,
            json.dumps(drawer.metadata),
        ))

        # Update inverted indexes
        for entity in entities:
            cursor.execute("""
                INSERT OR REPLACE INTO entity_index VALUES (?, ?, 1)
            """, (entity.lower(), drawer_id))

        for topic in topics:
            cursor.execute("""
                INSERT OR REPLACE INTO topic_index VALUES (?, ?, 1)
            """, (topic.lower(), drawer_id))

        conn.commit()
        conn.close()

        logger.debug(f"Drawer added: {drawer_id}")
        return drawer

    def get_drawer(self, drawer_id: str) -> Optional[DrawerEntry]:
        """Get a drawer by ID."""
        if drawer_id in self._drawers:
            return self._drawers[drawer_id]

        # Load from database
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drawers WHERE drawer_id = ?", (drawer_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            drawer = self._row_to_drawer(row)
            self._drawers[drawer_id] = drawer
            return drawer

        return None

    def _row_to_drawer(self, row: tuple) -> DrawerEntry:
        """Convert database row to DrawerEntry."""
        return DrawerEntry(
            drawer_id=row[0],
            content=row[1],
            content_type=row[2] if len(row) > 2 else "document",
            tags=json.loads(row[3]) if len(row) > 3 and row[3] else [],
            entities=json.loads(row[4]) if len(row) > 4 and row[4] else [],
            topics=json.loads(row[5]) if len(row) > 5 and row[5] else [],
            token_count=row[6] if len(row) > 6 else 0,
            created_at=row[7] if len(row) > 7 else datetime.now(timezone.utc).isoformat(),
            updated_at=row[8] if len(row) > 8 else datetime.now(timezone.utc).isoformat(),
            metadata=json.loads(row[9]) if len(row) > 9 and row[9] else {},
        )

    def lookup(
        self,
        query: str,
        max_results: int = 5,
        include_types: Optional[List[str]] = None,
    ) -> List[DrawerEntry]:
        """
        Lookup drawers matching a query.

        Args:
            query: Search query (can be keywords, entity names, or topics)
            max_results: Maximum number of results
            include_types: Filter by content types

        Returns:
            List of matching DrawerEntry objects
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Search in inverted indexes
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        scores: Dict[str, float] = {}

        # Entity match
        cursor.execute("""
            SELECT drawer_id, SUM(frequency) as score
            FROM entity_index
            WHERE entity_name LIKE ?
            GROUP BY drawer_id
        """, (f"%{query_lower}%",))
        for row in cursor.fetchall():
            drawer_id, score = row
            scores[drawer_id] = scores.get(drawer_id, 0) + score * 2  # Weight entities higher

        # Topic match
        cursor.execute("""
            SELECT drawer_id, SUM(frequency) as score
            FROM topic_index
            WHERE topic LIKE ?
            GROUP BY drawer_id
        """, (f"%{query_lower}%",))
        for row in cursor.fetchall():
            drawer_id, score = row
            scores[drawer_id] = scores.get(drawer_id, 0) + score * 1.5  # Weight topics

        # Keyword match
        for word in query_words:
            cursor.execute("""
                SELECT drawer_id, SUM(frequency) as score
                FROM keyword_index
                WHERE keyword = ?
                GROUP BY drawer_id
            """, (word,))
            for row in cursor.fetchall():
                drawer_id, score = row
                scores[drawer_id] = scores.get(drawer_id, 0) + score

        conn.close()

        # Sort by score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for drawer_id, score in sorted_ids[:max_results]:
            drawer = self.get_drawer(drawer_id)
            if drawer:
                if include_types and drawer.content_type not in include_types:
                    continue
                results.append(drawer)

        return results

    def lookup_by_entities(
        self,
        entities: List[str],
        max_results: int = 5,
    ) -> List[DrawerEntry]:
        """
        Lookup drawers by entity names.

        Args:
            entities: List of entity names to match
            max_results: Maximum results

        Returns:
            List of matching drawers
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        entity_conditions = " OR ".join(["entity_name = ?" for _ in entities])
        params = [e.lower() for e in entities]

        cursor.execute(f"""
            SELECT drawer_id, SUM(frequency) as score
            FROM entity_index
            WHERE {entity_conditions}
            GROUP BY drawer_id
            ORDER BY score DESC
            LIMIT ?
        """, params + [max_results])

        drawer_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return [self.get_drawer(did) for did in drawer_ids if self.get_drawer(did)]

    def lookup_by_topics(
        self,
        topics: List[str],
        max_results: int = 5,
    ) -> List[DrawerEntry]:
        """
        Lookup drawers by topics.

        Args:
            topics: List of topics to match
            max_results: Maximum results

        Returns:
            List of matching drawers
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        cursor = conn.cursor()

        topic_conditions = " OR ".join(["topic = ?" for _ in topics])
        params = [t.lower() for t in topics]

        cursor.execute(f"""
            SELECT drawer_id, SUM(frequency) as score
            FROM topic_index
            WHERE {topic_conditions}
            GROUP BY drawer_id
            ORDER BY score DESC
            LIMIT ?
        """, params + [max_results])

        drawer_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return [self.get_drawer(did) for did in drawer_ids if self.get_drawer(did)]

    def build_aak_index(
        self,
        query_func: Optional[Callable[[str], List[str]]] = None,
    ) -> List[AAKEntry]:
        """
        Build AAAK (Almost All Answer Key) index.

        Creates compressed index entries that LLM can use for fast drawer lookup.

        Args:
            query_func: Optional function to generate related queries for each topic

        Returns:
            List of AAKEntry objects
        """
        self._aak_index.clear()
        entries = []

        # Group drawers by topic
        topic_groups: Dict[str, List[str]] = {}
        for drawer in self._drawers.values():
            for topic in drawer.topics:
                if topic not in topic_groups:
                    topic_groups[topic] = []
                topic_groups[topic].append(drawer.drawer_id)

        # Create AAK entries for each topic
        for topic, drawer_ids in topic_groups.items():
            # Extract keywords from content
            keywords = self._extract_keywords(topic)

            aak_id = self._generate_aak_id(topic, keywords)
            entry = AAKEntry(
                aak_id=aak_id,
                keywords=keywords,
                topic=topic,
                drawer_ids=drawer_ids,
            )

            self._aak_index[aak_id] = entry
            entries.append(entry)

            # Persist to database
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO aak_index VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.aak_id,
                json.dumps(entry.keywords),
                entry.topic,
                json.dumps(entry.drawer_ids),
                entry.score,
                entry.created_at,
            ))
            conn.commit()
            conn.close()

        logger.info(f"Built AAAK index with {len(entries)} entries")
        return entries

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction (in production, use NLP)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())

        # Common stop words to exclude
        stop_words = {
            'about', 'after', 'again', 'also', 'back', 'been', 'before',
            'being', 'between', 'both', 'each', 'find', 'from', 'have',
            'here', 'into', 'make', 'more', 'most', 'much', 'must', 'name',
            'need', 'next', 'only', 'other', 'over', 'such', 'take',
            'than', 'that', 'their', 'them', 'then', 'there', 'these',
            'they', 'this', 'those', 'through', 'under', 'very', 'want',
            'what', 'when', 'where', 'which', 'while', 'will', 'with', 'would'
        }

        keywords = [w for w in words if w not in stop_words]

        # Count frequency and return top keywords
        from collections import Counter
        counter = Counter(keywords)
        return [kw for kw, _ in counter.most_common(max_keywords)]

    def _generate_aak_id(self, topic: str, keywords: List[str]) -> str:
        """Generate AAAK entry ID."""
        content = f"{topic}:{','.join(keywords)}"
        return f"aak_{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def get_aaak_index(self, max_entries: int = 100) -> List[str]:
        """
        Get AAAK index as a list of AAAK strings.

        Format: topic|entities|→drawer_ids

        This is the LLM-friendly format that can be included in prompts.

        Args:
            max_entries: Maximum number of AAAK entries to return

        Returns:
            List of AAAK strings
        """
        if not self._aak_index:
            self.build_aak_index()

        entries = sorted(
            self._aak_index.values(),
            key=lambda e: len(e.drawer_ids),
            reverse=True
        )

        return [entry.to_aaak() for entry in entries[:max_entries]]

    def get_aaak_for_llm(
        self,
        max_entries: int = 20,
        max_token_budget: int = 500,
    ) -> str:
        """
        Get AAAK index formatted for LLM consumption.

        Args:
            max_entries: Maximum number of AAAK entries
            max_token_budget: Approximate token budget for the output

        Returns:
            Formatted AAAK index string
        """
        aaak_list = self.get_aaak_index(max_entries=max_entries)

        # Format with header
        header = "# Almost All Answer Key (AAAK) Index\n"
        header += "# Format: topic|entities|→drawer_ids\n"
        header += "# Use drawer_ids to quickly locate relevant memories\n\n"

        lines = [header]
        current_tokens = len(header) // 4

        for aaak in aaak_list:
            tokens = len(aaak) // 4
            if current_tokens + tokens > max_token_budget:
                break
            lines.append(aaak)
            current_tokens += tokens

        return "\n".join(lines)

    def get_drawer_contents(
        self,
        drawer_ids: List[str],
        max_tokens: int = 1000,
    ) -> str:
        """
        Get contents of specified drawers.

        Args:
            drawer_ids: List of drawer IDs to retrieve
            max_tokens: Maximum tokens to include

        Returns:
            Combined drawer contents
        """
        contents = []
        current_tokens = 0

        for drawer_id in drawer_ids:
            drawer = self.get_drawer(drawer_id)
            if not drawer:
                continue

            tokens = drawer.token_count
            if current_tokens + tokens > max_tokens:
                # Truncate content
                remaining = max_tokens - current_tokens
                truncated = drawer.content[:remaining * 4]
                contents.append(f"[{drawer_id}] {truncated}... (truncated)")
                break

            contents.append(f"[{drawer_id}] {drawer.content}")
            current_tokens += tokens

        return "\n\n".join(contents)

    def stats(self) -> Dict[str, Any]:
        """Get closet statistics."""
        return {
            "total_drawers": len(self._drawers),
            "aak_entries": len(self._aak_index),
            "database_path": str(self.db_path),
            "drawer_types": self._count_by_type(),
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count drawers by content type."""
        counts: Dict[str, int] = {}
        for drawer in self._drawers.values():
            counts[drawer.content_type] = counts.get(drawer.content_type, 0) + 1
        return counts

    def clear(self) -> None:
        """Clear all data from the closet."""
        self._drawers.clear()
        self._aak_index.clear()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drawers")
        cursor.execute("DELETE FROM aak_index")
        cursor.execute("DELETE FROM entity_index")
        cursor.execute("DELETE FROM topic_index")
        cursor.execute("DELETE FROM keyword_index")
        conn.commit()
        conn.close()

        logger.info("Closet cleared")
