"""
BM25 keyword-based retriever for Ariadne RAG Pipeline.

BM25 (Best Matching 25) is a probabilistic ranking function used for
information retrieval. Unlike vector similarity, BM25 captures exact
keyword matching — making it complementary to semantic vector search.

This module provides a lightweight BM25 implementation built on
rank_bm25, wrapping Ariadne's ChromaDB documents for hybrid retrieval.
"""

import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency
_bm25_impl = None


def _get_bm25():
    """Lazy-load rank_bm25 to make it optional."""
    global _bm25_impl
    if _bm25_impl is None:
        try:
            from rank_bm25 import BM25Okapi
            _bm25_impl = BM25Okapi
        except ImportError:
            raise ImportError(
                "rank_bm25 is required for keyword search. "
                "Install it with: pip install rank-bm25"
            )
    return _bm25_impl


class BM25Retriever:
    """
    BM25 keyword retriever backed by rank_bm25.

    This retriever operates on the full text of documents already stored
    in ChromaDB. It is used as the **keyword branch** of hybrid search:
    combining BM25 scores with vector similarity produces better results
    than either approach alone.

    Usage:
        >>> from ariadne.rag.bm25_retriever import BM25Retriever
        >>> retriever = BM25Retriever(vector_store)
        >>> retriever.rebuild_index()
        >>> results = retriever.search("machine learning", top_k=10)
    """

    def __init__(self, vector_store, tokenize: bool = True):
        """
        Initialize the BM25 retriever.

        Args:
            vector_store: An ariadne VectorStore instance to pull documents from.
            tokenize: If True, tokenize with a simple whitespace+punct splitter.
                      If False, pass raw text (for languages where this matters).
        """
        self._store = vector_store
        self._tokenize = tokenize
        self._bm25 = None
        self._doc_ids: List[str] = []
        self._doc_texts: List[str] = []

    def rebuild_index(self) -> int:
        """
        Rebuild the BM25 index from all documents in the store.

        This should be called:
        - On first use (lazy initialization)
        - After adding many new documents
        - Periodically in the background for large stores

        Returns:
            Number of documents indexed.
        """
        BM25Okapi = _get_bm25()

        # Fetch all documents from ChromaDB (paginate for large stores)
        self._doc_ids, self._doc_texts = self._fetch_all_documents()

        if not self._doc_texts:
            self._bm25 = None
            return 0

        # Tokenize corpus
        tokenized_corpus = [self._tokenize_text(text) for text in self._doc_texts]
        self._bm25 = BM25Okapi(tokenized_corpus)
        return len(self._doc_ids)

    def _fetch_all_documents(self) -> Tuple[List[str], List[str]]:
        """Retrieve all documents from the store in batches."""
        doc_ids: List[str] = []
        doc_texts: List[str] = []
        batch_size = 10000

        offset = 0
        while True:
            result = self._store._collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents"],
            )
            if not result["ids"]:
                break
            doc_ids.extend(result["ids"])
            doc_texts.extend(result["documents"])
            if len(result["ids"]) < batch_size:
                break
            offset += batch_size

        return doc_ids, doc_texts

    def _tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text for BM25.

        Uses a simple whitespace + punctuation splitter.
        For languages with different tokenization needs, subclass and
        override this method.

        Args:
            text: Raw document text.

        Returns:
            List of lowercase tokens.
        """
        if not self._tokenize:
            return text.split()

        # Remove non-alphanumeric characters and split on whitespace
        text = text.lower()
        # Split on non-alphanumeric sequences (preserving CJK as single tokens)
        tokens = re.findall(r'[a-z0-9]+|[^\x00-\x7F]+', text)
        # Filter very short tokens (length 1) as they add noise
        tokens = [t for t in tokens if len(t) >= 2]
        return tokens

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Search using BM25 keyword matching.

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of (doc_id, bm25_score) tuples, sorted by relevance (best first).
            Returns empty list if index is empty or not yet built.
        """
        if self._bm25 is None:
            logger.warning("BM25 index not built. Call rebuild_index() first.")
            return []

        tokens = self._tokenize_text(query)
        if not tokens:
            return []

        raw_scores = self._bm25.get_scores(tokens)
        # Pair with doc IDs and sort by score descending
        scored = sorted(
            zip(self._doc_ids, raw_scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return scored[:top_k]

    @property
    def document_count(self) -> int:
        """Number of documents currently in the BM25 index."""
        return len(self._doc_ids)

    @property
    def is_ready(self) -> bool:
        """Whether the BM25 index has been built."""
        return self._bm25 is not None
