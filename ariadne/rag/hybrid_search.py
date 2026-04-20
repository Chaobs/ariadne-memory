"""
Hybrid search combining vector + BM25 keyword retrieval.

Hybrid search addresses a fundamental limitation of pure vector search:
semantic approaches excel at finding conceptually related content but
can miss documents that use different vocabulary for the same concept.

By combining:
- Vector similarity (captures semantic meaning)
- BM25 keyword scores (captures exact term matches)

We get better recall than either approach alone.

The combination uses Reciprocal Rank Fusion (RRF):
    score(d) = Σ 1 / (k + rank_i(d))

Where k=60 is a smoothing constant that prevents any single source
from dominating the ranking.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ariadne.ingest.base import Document

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    A single search result with combined scoring.

    Attributes:
        document: The Document object.
        vector_score: Cosine similarity from vector search (0-1, higher = better).
        bm25_score: Raw BM25 score from keyword search.
        rrf_score: Reciprocal Rank Fusion combined score.
        rank: Final ranking position (1 = best).
        source: Which retrieval method(s) found this result
                ("vector", "bm25", "hybrid").
    """
    document: Document
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rank: int = 0
    source: str = "hybrid"

    @property
    def combined_score(self) -> float:
        """Weighted combination of vector and BM25 scores."""
        # Weight vector more heavily for semantic queries, BM25 for keyword-heavy
        return 0.6 * self.vector_score + 0.4 * self.bm25_score


class HybridSearch:
    """
    Hybrid search combining vector similarity and BM25 keyword retrieval.

    Usage:
        >>> store = VectorStore()
        >>> search = HybridSearch(store)
        >>> search.rebuild_bm25_index()
        >>> results = search.search("machine learning optimization", top_k=5)
    """

    # Reciprocal Rank Fusion parameters
    DEFAULT_K = 60  # Smoothing constant; higher = more equal weighting
    DEFAULT_TOP_K = 20  # How many to fetch from each source before fusion

    def __init__(
        self,
        vector_store,
        bm25_retriever=None,
        k: int = DEFAULT_K,
    ):
        """
        Initialize hybrid search.

        Args:
            vector_store: An ariadne VectorStore instance.
            bm25_retriever: Optional pre-built BM25Retriever.
                           If None, a new one is created lazily.
            k: RRF smoothing constant. Higher = more weight to lower-ranked results.
        """
        self._store = vector_store
        self._bm25: Optional[object] = bm25_retriever  # BM25Retriever or None
        self._k = k

    @property
    def bm25(self):
        """Lazy-load BM25 retriever on first access."""
        if self._bm25 is None:
            from ariadne.rag.bm25_retriever import BM25Retriever
            self._bm25 = BM25Retriever(self._store)
            self._bm25.rebuild_index()
        return self._bm25

    def rebuild_bm25_index(self) -> int:
        """
        Rebuild the BM25 index from the vector store.

        Call this after adding many documents to keep BM25 in sync.

        Returns:
            Number of documents indexed.
        """
        return self.bm25.rebuild_index()

    def search(
        self,
        query: str,
        top_k: int = 5,
        fetch_k: int = DEFAULT_TOP_K,
        alpha: float = 0.5,
        min_score: float = 0.0,
        source_types: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Execute hybrid search and return ranked results.

        Args:
            query: Natural language search query.
            top_k: Number of final results to return after fusion.
            fetch_k: How many results to fetch from each source before fusion.
                     Set higher than top_k to capture more candidates.
            alpha: Weight for vector scores in the weighted combination
                   (1.0 = vector only, 0.0 = BM25 only). Default 0.5 = equal.
            min_score: Minimum combined score threshold. Results below this
                      are filtered out.
            source_types: Optional filter — only search these source types.

        Returns:
            List of SearchResult objects, sorted by rrf_score (best first).
        """
        if fetch_k < top_k:
            fetch_k = top_k

        # Phase 1: Parallel vector + BM25 retrieval
        vector_results = self._vector_search(query, fetch_k, source_types)
        bm25_results = self._bm25_search(query, fetch_k)

        # Phase 2: Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=self._k,
            alpha=alpha,
        )

        # Phase 3: Filter and rank
        filtered = [r for r in fused if r.combined_score >= min_score][:top_k]
        for i, result in enumerate(filtered, start=1):
            result.rank = i

        return filtered

    def _vector_search(
        self,
        query: str,
        top_k: int,
        source_types: Optional[List[str]],
    ) -> dict:
        """Execute pure vector similarity search."""
        try:
            raw_results = self._store.search(
                query=query,
                top_k=top_k,
                source_types=source_types,
            )
            # Convert to dict keyed by doc_id
            return {
                doc.doc_id: (doc, score)
                for doc, score in raw_results
            }
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return {}

    def _bm25_search(self, query: str, top_k: int) -> dict:
        """Execute BM25 keyword search."""
        try:
            if not self.bm25.is_ready:
                return {}

            results = self.bm25.search(query, top_k=top_k)
            # Normalize BM25 scores to 0-1 range (relative normalization)
            if not results:
                return {}

            max_score = max(score for _, score in results)
            if max_score == 0:
                return {}

            normalized = {
                doc_id: score / max_score
                for doc_id, score in results
            }

            # Fetch Document objects from store
            doc_dict = {}
            for doc_id, norm_score in normalized.items():
                # We need the Document object — fetch from store
                doc_obj = self._fetch_document(doc_id)
                if doc_obj:
                    doc_dict[doc_id] = (doc_obj, norm_score)

            return doc_dict
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return {}

    def _fetch_document(self, doc_id: str) -> Optional[Document]:
        """Fetch a single document by ID from the store."""
        try:
            result = self._store._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
            if not result["ids"]:
                return None

            from ariadne.ingest.base import SourceType

            content = result["documents"][0]
            metadata = result["metadatas"][0] if result["metadatas"] else {}

            source_type_str = metadata.get("source_type", "unknown")
            try:
                st = SourceType(source_type_str)
            except ValueError:
                st = SourceType.UNKNOWN

            return Document(
                content=content,
                source_type=st,
                source_path=metadata.get("source_path", ""),
                chunk_index=metadata.get("chunk_index", 0),
                total_chunks=metadata.get("total_chunks", 1),
                metadata={
                    k: v for k, v in metadata.items()
                    if k not in ("source_type", "source_path", "chunk_index", "total_chunks")
                },
            )
        except Exception:
            return None

    @staticmethod
    def _reciprocal_rank_fusion(
        vector_results: dict,
        bm25_results: dict,
        k: int = DEFAULT_K,
        alpha: float = 0.5,
    ) -> List[SearchResult]:
        """
        Fuse results using Reciprocal Rank Fusion with weighted scoring.

        RRF formula: score(d) = Σ 1 / (k + rank_i(d))
        Then combined with weighted score: alpha * vector + (1-alpha) * bm25

        Args:
            vector_results: Dict of doc_id -> (Document, vector_score)
            bm25_results: Dict of doc_id -> (Document, bm25_score)
            k: RRF smoothing constant.
            alpha: Weight for vector scores.

        Returns:
            List of SearchResult objects with all scoring metadata.
        """
        if not vector_results and not bm25_results:
            return []

        # Collect all unique doc_ids
        all_ids = set(vector_results.keys()) | set(bm25_results.keys())

        # Rank each result set (sorted by score, descending)
        vector_ranked = sorted(
            vector_results.items(),
            key=lambda x: x[1][1],
            reverse=True,
        )
        bm25_ranked = sorted(
            bm25_results.items(),
            key=lambda x: x[1][1],
            reverse=True,
        )

        # Build rank dicts (rank starts at 1)
        vector_ranks = {doc_id: rank + 1 for rank, (doc_id, _) in enumerate(vector_ranked)}
        bm25_ranks = {doc_id: rank + 1 for rank, (doc_id, _) in enumerate(bm25_ranked)}

        # Calculate fused scores
        results = []
        for doc_id in all_ids:
            vec_doc, vec_score = vector_results.get(doc_id, (None, 0.0))
            bm25_doc, bm25_score = bm25_results.get(doc_id, (None, 0.0))

            # Use whichever result set had the document
            doc = vec_doc or bm25_doc
            if doc is None:
                continue

            # RRF score from each source
            vec_rrf = 1.0 / (k + vector_ranks.get(doc_id, k))
            bm25_rrf = 1.0 / (k + bm25_ranks.get(doc_id, k))

            # Combined RRF (equal weight in rank fusion)
            rrf_score = vec_rrf + bm25_rrf

            # Weighted combination of raw scores
            combined_score = alpha * vec_score + (1 - alpha) * bm25_score

            # Determine source
            has_vector = doc_id in vector_results
            has_bm25 = doc_id in bm25_results
            if has_vector and has_bm25:
                source = "hybrid"
            elif has_vector:
                source = "vector"
            else:
                source = "bm25"

            results.append(SearchResult(
                document=doc,
                vector_score=vec_score,
                bm25_score=bm25_score,
                rrf_score=rrf_score,
                source=source,
            ))

        # Sort by combined score (or rrf_score as tiebreaker)
        results.sort(key=lambda r: (r.combined_score, r.rrf_score), reverse=True)

        return results
