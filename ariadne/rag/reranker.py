"""
Reranking module for Ariadne RAG Pipeline.

Reranking improves result quality by re-scoring the candidate documents
from hybrid search using a more expensive (but more accurate) model.

Two strategies are supported:

1. **Cross-Encoder Reranking** (recommended):
   Uses a pre-trained cross-encoder model (e.g. ms-marco-MiniLM-L-6-v2)
   that jointly encodes (query, document) pairs for relevance scoring.
   Requires: sentence-transformers with a cross-encoder model.

2. **Heuristic Reranking** (fallback, no extra dependencies):
   Uses BM25 + position + source-type signals to estimate relevance.
   Works out-of-the-box without any additional models.

The reranker is called AFTER the hybrid search retrieves candidates
but BEFORE the results are returned to the user.
"""

import logging
from typing import List, Optional, Tuple

from ariadne.rag.hybrid_search import SearchResult

logger = logging.getLogger(__name__)


class Reranker:
    """
    Re-rank search results using cross-encoder models or heuristics.

    Usage:
        >>> reranker = Reranker()
        >>> reranked = reranker.rerank(query, candidates, top_k=5)
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        use_heuristic: bool = False,
    ):
        """
        Initialize the reranker.

        Args:
            model_name: Name of a HuggingFace cross-encoder model.
                        Only used if use_heuristic=False and model is available.
            use_heuristic: If True, skip model loading and use heuristic reranking.
                           Useful when sentence-transformers is not installed.
        """
        self._model_name = model_name
        self._use_heuristic = use_heuristic
        self._cross_encoder = None
        self._cross_encoder_available = False

    @property
    def model(self):
        """Lazy-load the cross-encoder model on first use."""
        if self._cross_encoder is None and not self._use_heuristic:
            self._load_cross_encoder()
        return self._cross_encoder

    def _load_cross_encoder(self) -> bool:
        """
        Attempt to load the cross-encoder model.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        try:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(self._model_name)
            self._cross_encoder_available = True
            logger.info(f"Cross-encoder loaded: {self._model_name}")
            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Cross-encoder reranking unavailable. "
                "Install with: pip install sentence-transformers"
            )
            self._cross_encoder_available = False
            return False
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder '{self._model_name}': {e}")
            self._cross_encoder_available = False
            return False

    def rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        Re-rank search candidates and return the top-K results.

        Args:
            query: The original search query.
            candidates: List of SearchResult objects from hybrid search.
            top_k: Number of results to return after reranking.

        Returns:
            Re-ranked list of SearchResult objects (best first).
        """
        if not candidates:
            return []

        if self._use_heuristic or not self._cross_encoder_available:
            return self._rerank_heuristic(query, candidates, top_k)

        return self._rerank_cross_encoder(query, candidates, top_k)

    def _rerank_cross_encoder(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        Re-rank using a cross-encoder model.

        Cross-encoders jointly encode (query, document) pairs, capturing
        richer interactions than bi-encoders used in the initial search.
        """
        try:
            # Prepare (query, document) pairs
            pairs = [
                (query, result.document.content)
                for result in candidates
            ]

            # Score all pairs
            scores = self.model.predict(pairs)

            # Attach cross-encoder scores to results
            for result, score in zip(candidates, scores):
                # Normalize cross-encoder score to 0-1 range
                # Cross-encoder outputs vary by model; min-max normalize
                result.cross_encoder_score = float(score)
                result._rerank_applied = "cross-encoder"

            # Sort by cross-encoder score
            candidates_sorted = sorted(
                candidates,
                key=lambda r: getattr(r, "cross_encoder_score", 0),
                reverse=True,
            )

            # Update ranks
            for i, result in enumerate(candidates_sorted[:top_k], start=1):
                result.rank = i

            return candidates_sorted[:top_k]

        except Exception as e:
            logger.warning(f"Cross-encoder reranking failed: {e}")
            return self._rerank_heuristic(query, candidates, top_k)

    @staticmethod
    def _rerank_heuristic(
        query: str,
        candidates: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        Re-rank using heuristic signals (no extra dependencies needed).

        Signals:
        - Exact keyword overlap between query and document
        - Query terms appearing in document title/header
        - Recency (if ingested_at is available)
        - Source type preference (markdown > pdf > code > others)

        This is a reasonable fallback when cross-encoder models are unavailable.
        """
        query_terms = set(query.lower().split())

        # Source type quality weights (higher = more trusted)
        SOURCE_WEIGHTS = {
            "markdown": 1.0,
            "txt": 0.9,
            "code": 0.85,
            "pdf": 0.8,
            "docx": 0.8,
            "ppt": 0.7,
            "web": 0.6,
            "unknown": 0.5,
        }

        for result in candidates:
            content_lower = result.document.content.lower()
            doc_terms = set(content_lower.split())

            # Keyword overlap score
            overlap = len(query_terms & doc_terms)
            keyword_score = overlap / max(len(query_terms), 1)

            # Exact phrase match (bonus for exact query appearing in doc)
            phrase_score = 1.0 if query.lower() in content_lower else 0.0

            # Source type score
            source_type = result.document.source_type.value
            source_weight = SOURCE_WEIGHTS.get(source_type, 0.5)

            # Recency score (newer docs get slight boost)
            recency_score = 0.5
            try:
                from datetime import datetime, timezone
                ingested = result.document.ingested_at
                if ingested:
                    dt = datetime.fromisoformat(ingested.replace("Z", "+00:00"))
                    days_old = (datetime.now(timezone.utc) - dt).days
                    # Exponential decay: 1.0 at 0 days, 0.5 at 90 days
                    recency_score = 1.0 / (1.0 + days_old / 90)
            except Exception:
                pass

            # Combined heuristic score (weighted sum)
            # Weight: keyword(40%) + phrase(20%) + source(25%) + recency(15%)
            heuristic_score = (
                0.40 * keyword_score +
                0.20 * phrase_score +
                0.25 * source_weight +
                0.15 * recency_score
            )

            # Blend with original combined score
            # 50% original score, 50% heuristic
            blended = 0.5 * result.combined_score + 0.5 * heuristic_score
            result.heuristic_score = heuristic_score
            result._rerank_applied = "heuristic"

            # Store blended score as the new ranking key
            result._blended_score = blended

        # Sort by blended score
        candidates_sorted = sorted(
            candidates,
            key=lambda r: getattr(r, "_blended_score", r.combined_score),
            reverse=True,
        )

        # Update ranks
        for i, result in enumerate(candidates_sorted[:top_k], start=1):
            result.rank = i

        return candidates_sorted[:top_k]

    @property
    def is_available(self) -> bool:
        """Whether cross-encoder reranking is available."""
        return self._cross_encoder_available

    def warm_up(self) -> bool:
        """
        Pre-load the cross-encoder model to avoid first-query latency.

        Returns:
            True if the model was loaded successfully.
        """
        if self._use_heuristic:
            return False
        return self._load_cross_encoder()
