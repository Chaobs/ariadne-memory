"""
ChromaDB-based vector store for Ariadne.

This module implements the core memory storage layer.
Design principle: keep the API simple and swappable — if you want to
replace ChromaDB with Qdrant, Weaviate, or pgvector later, only this
module needs to change.
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import List, Tuple, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ariadne.ingest.base import Document, SourceType


def _is_db_corruption_error(exc: Exception) -> bool:
    """Check if an exception indicates a corrupted/invalid SQLite database
    **or** a ChromaDB internal index failure (HNSW, compactor, segment).

    These errors are non-recoverable at the API level — the only safe remedy
    is to wipe the persisted files and let PersistentClient start fresh.
    """
    msg = str(exc).lower()
    return any(pattern in msg for pattern in [
        # --- SQLite-level ---
        "file is not a database",
        "database disk image is malformed",
        "file is encrypted",
        "not a valid sqlite db",
        "code: 26",       # SQLITE_NOTADB
        "code:11",        # SQLITE_CORRUPT
        "malformed",
        # --- ChromaDB / HNSW-level ---
        "hnsw",
        "compactor",
        "segment reader",
        "loading hnsw index",
        "backfill request",
        "error constructing",
        "error creating hnsw",
        "invalid index",
    ])


class VectorStore:
    """
    ChromaDB-backed vector memory store.

    Stores Document objects as vector embeddings, enabling semantic
    similarity search across all ingested content.

    Design notes:
    - Uses ChromaDB's built-in embedding function (all-MiniLM-L6-v2 via sentence-transformers)
    - Persists data to a local directory (default: ./ariadne_data)
    - Collection is auto-created on first add()
    - Documents are de-duplicated by doc_id
    - Supports multiple collections (for multi-memory systems)

    ⚠️  ChromaDB's PersistentClient uses *lazy* initialisation for its internal
    HNSW index.  The ``PersistentClient(path)`` constructor always succeeds even
    when the persisted index files are corrupt.  The real error is only thrown
    when you call ``count()``, ``query()``, or ``add()`` — i.e. when the index is
    first accessed.  This means recovery code must be placed at the **call site**
    (``get_store() / _probe()``), not just in ``__init__``.

    Usage:
        >>> store = VectorStore()
        >>> store.add(my_documents)
        >>> results = store.search("my query", top_k=5)
    """

    DEFAULT_COLLECTION = "ariadne_memory"

    # Class-level flag to avoid infinite recursion during recovery probe
    _recovering = False

    def __init__(self, persist_dir: Optional[str] = None, collection_name: Optional[str] = None):
        """
        Initialize the vector store.

        Args:
            persist_dir: Directory to persist ChromaDB data.
                         Defaults to ./ariadne_data in the working directory.
            collection_name: Name of the collection. Defaults to DEFAULT_COLLECTION.
                            Use different collection names for different memory systems.
        """
        if persist_dir is None:
            persist_dir = str(Path.cwd() / "ariadne_data")

        self.persist_dir = persist_dir
        self.collection_name = collection_name or self.DEFAULT_COLLECTION
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        # Try normal initialization; if DB is corrupted, recover automatically
        last_exc = None
        for attempt in range(2):
            try:
                self._client = chromadb.PersistentClient(
                    path=persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": f"Ariadne memory: {self.collection_name}"},
                )
                return  # Success
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and _is_db_corruption_error(exc) and self._wipe_chroma_files(persist_dir):
                    # Corrupted DB wiped; retry once with fresh DB
                    continue
                raise  # Non-corruption error or recovery failed

    def probe(self) -> bool:
        """Force a lightweight operation to trigger lazy HNSW index loading.

        ChromaDB defers HNSW index construction until the first read/write.
        If the persisted index files are corrupt, this method raises the
        exception immediately so callers can recover.

        Returns:
            True if the store is healthy and usable.

        Raises:
            Exception: Any corruption/lazy-load error from ChromaDB internals.
        """
        # count() is the cheapest operation that forces index activation
        self._collection.count()
        return True

    @staticmethod
    def _wipe_chroma_files(persist_dir: str) -> bool:
        """Remove **all** ChromaDB persisted content so PersistentClient can start fresh.

        ChromaDB's PersistentClient writes not just ``chroma.sqlite3`` but also
        HNSW index binaries in subdirectories (e.g. ``chroma-embeddings-*``).
        A corruption in any of these causes "Error loading hnsw index".  The
        only reliable recovery is to wipe **everything** inside the persist dir.
        """
        dir_path = Path(persist_dir)
        if not dir_path.exists() or not dir_path.is_dir():
            return False

        removed = False
        for item in list(dir_path.iterdir()):
            try:
                if item.is_file():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                removed = True
            except OSError:
                pass

        # Recreate the (now-empty) directory so PersistentClient has a target
        if removed and not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)

        return removed

    def add(self, documents: List[Document]) -> None:
        """
        Add documents to the vector store.

        Args:
            documents: List of Document objects to add.

        Note:
            If a document with the same doc_id already exists, it will be
            updated (upsert behavior).
        """
        if not documents:
            return

        ids = []
        contents = []
        metadatas = []
        source_types = []

        for doc in documents:
            ids.append(doc.doc_id)
            contents.append(doc.content)
            metadatas.append({
                "source_type": doc.source_type.value,
                "source_path": doc.source_path,
                "chunk_index": doc.chunk_index,
                "total_chunks": doc.total_chunks,
                **doc.metadata,
            })
            source_types.append(doc.source_type.value)

        self._collection.upsert(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: Optional[List[str]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Semantic search across all stored documents.

        Args:
            query: Natural language search query.
            top_k: Number of results to return.
            source_types: Optional filter — only search these source types
                          (e.g., ["pdf", "markdown"]).

        Returns:
            List of (Document, score) tuples, sorted by relevance (best first).
            Score is cosine similarity (0–1, higher = more relevant).
        """
        where_filter = None
        if source_types:
            where_filter = {"source_type": {"$in": source_types}}

        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        documents = []
        if results["documents"] and results["documents"][0]:
            for i, content in enumerate(results["documents"][0]):
                metadata = (results["metadatas"][0][i]) if results["metadatas"] else {}
                distance = (results["distances"][0][i]) if results["distances"] else 0.0

                # Convert distance to similarity score (ChromaDB uses Euclidean distance)
                score = 1.0 / (1.0 + distance)

                source_type_str = metadata.get("source_type", "unknown")
                try:
                    st = SourceType(source_type_str)
                except ValueError:
                    st = SourceType.UNKNOWN

                doc = Document(
                    content=content,
                    source_type=st,
                    source_path=metadata.get("source_path", ""),
                    chunk_index=metadata.get("chunk_index", 0),
                    total_chunks=metadata.get("total_chunks", 1),
                    metadata={k: v for k, v in metadata.items()
                              if k not in ("source_type", "source_path", "chunk_index", "total_chunks")},
                )
                documents.append((doc, score))

        return documents

    def count(self) -> int:
        """Return the total number of documents in the store."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all documents from the store."""
        self._client.delete_collection(name=self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": f"Ariadne memory: {self.collection_name}"},
        )
