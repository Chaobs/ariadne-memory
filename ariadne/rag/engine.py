"""
RAG Engine — Unified RAG pipeline orchestrator for Ariadne.

This module provides the main entry point for RAG-powered queries.
It orchestrates the full pipeline:

    Query → Hybrid Search → Reranking → Citation → Response Context

The engine is designed to be LLM-agnostic: it produces a well-structured
context string that can be fed to any LLM provider (DeepSeek, Claude, etc.).


Design philosophy:
- Lazy initialization: models are only loaded when first needed
- Graceful degradation: if cross-encoder is unavailable, use heuristic reranking
- Transparent: every result includes citations so users can verify sources
- Modular: each stage (search, rerank, cite) can be swapped individually

Usage:
    >>> engine = create_rag_engine(store)
    >>> result = engine.query("What are the key findings in the research paper?")
    >>> print(result.context)
    >>> for citation in result.citations:
    ...     print(citation.format_markdown())
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ariadne.rag.bm25_retriever import BM25Retriever
from ariadne.rag.hybrid_search import HybridSearch, SearchResult
from ariadne.rag.reranker import Reranker
from ariadne.rag.citation import CitationGenerator, Citation

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """
    The output of a RAG query.

    Attributes:
        query: The original search query.
        context: Formatted context string ready for LLM injection.
                 Includes citation markers and source references.
        results: Raw SearchResult objects (before formatting).
        citations: Citation objects for all returned results.
        timings: Timing information for each pipeline stage (ms).
        metadata: Additional metadata (total candidates, rerank method, etc.).
    """
    query: str
    context: str = ""
    results: List[SearchResult] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Whether the query returned any results."""
        return len(self.results) == 0

    @property
    def top_score(self) -> float:
        """Score of the top result (0-1, higher = better)."""
        if not self.results:
            return 0.0
        return self.results[0].combined_score


class RAGEngine:
    """
    Orchestrates the full RAG pipeline: search → rerank → cite → format.

    Usage:
        >>> engine = RAGEngine(vector_store)
        >>> result = engine.query("What is the main thesis?")
        >>> print(result.context)
    """

    def __init__(
        self,
        vector_store,
        enable_rerank: bool = True,
        rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        use_heuristic: bool = False,
        alpha: float = 0.5,
        default_top_k: int = 5,
        default_fetch_k: int = 20,
    ):
        """
        Initialize the RAG engine.

        Args:
            vector_store: An ariadne VectorStore instance.
            enable_rerank: Whether to apply reranking after hybrid search.
            rerank_model: Cross-encoder model name (only used if enable_rerank=True).
            use_heuristic: Use heuristic reranking instead of cross-encoder.
            alpha: Vector weight in hybrid search (1.0 = vector only, 0.0 = BM25 only).
            default_top_k: Default number of results to return.
            default_fetch_k: How many candidates to fetch before reranking.
        """
        self._store = vector_store
        self._enable_rerank = enable_rerank
        self._alpha = alpha
        self._default_top_k = default_top_k
        self._default_fetch_k = default_fetch_k

        # Lazy-initialized components
        self._hybrid_search: Optional[HybridSearch] = None
        self._reranker: Optional[Reranker] = None
        self._citation_generator: Optional[CitationGenerator] = None

    # ── Lazy component initialization ──────────────────────────────────

    @property
    def hybrid_search(self) -> HybridSearch:
        """Lazy-initialize the hybrid search component."""
        if self._hybrid_search is None:
            self._hybrid_search = HybridSearch(
                vector_store=self._store,
                k=60,
            )
        return self._hybrid_search

    @property
    def reranker(self) -> Reranker:
        """Lazy-initialize the reranker component."""
        if self._reranker is None:
            self._reranker = Reranker(
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
                use_heuristic=not self._enable_rerank,
            )
        return self._reranker

    @property
    def citation_generator(self) -> CitationGenerator:
        """Lazy-initialize the citation generator."""
        if self._citation_generator is None:
            self._citation_generator = CitationGenerator()
        return self._citation_generator

    # ── Public API ──────────────────────────────────────────────────────

    def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        fetch_k: Optional[int] = None,
        alpha: Optional[float] = None,
        include_citations: bool = True,
        include_context: bool = True,
        min_score: float = 0.0,
        source_types: Optional[List[str]] = None,
    ) -> RAGResult:
        """
        Execute a RAG query through the full pipeline.

        Args:
            query: Natural language search query.
            top_k: Number of results to return (default: self.default_top_k).
            fetch_k: Candidates to fetch before reranking (default: self.default_fetch_k).
            alpha: Vector weight in hybrid search (default: self.alpha).
            include_citations: Generate citation metadata for results.
            include_context: Build the formatted context string for LLM use.
            min_score: Minimum score threshold (0-1).
            source_types: Optional filter for specific source types.

        Returns:
            RAGResult with context, citations, and metadata.
        """
        import time

        top_k = top_k or self._default_top_k
        fetch_k = fetch_k or self._default_fetch_k
        alpha = alpha if alpha is not None else self._alpha

        # Fire before_search hook — allows query rewriting/expansion
        from ariadne.plugins.hooks import HookManager
        query = HookManager.fire("before_search", query)

        result = RAGResult(query=query)
        t0 = time.time()

        # Stage 1: Hybrid Search
        try:
            candidates = self.hybrid_search.search(
                query=query,
                top_k=top_k,
                fetch_k=fetch_k,
                alpha=alpha,
                min_score=min_score,
                source_types=source_types,
            )
            result.timings["hybrid_search_ms"] = (time.time() - t0) * 1000
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            result.metadata["error"] = str(e)
            return result

        if not candidates:
            result.timings["total_ms"] = (time.time() - t0) * 1000
            return result

        result.results = candidates
        result.metadata["total_candidates"] = len(candidates)

        # Stage 2: Reranking
        t_rerank = time.time()
        try:
            if self._enable_rerank:
                reranked = self.reranker.rerank(query, candidates, top_k=top_k)
                result.results = reranked
                result.metadata["rerank_method"] = getattr(
                    reranked[0], "_rerank_applied", "unknown"
                ) if reranked else "none"
            else:
                result.metadata["rerank_method"] = "none"
        except Exception as e:
            logger.warning(f"Reranking failed, using original order: {e}")
            result.metadata["rerank_error"] = str(e)
        result.timings["rerank_ms"] = (time.time() - t_rerank) * 1000

        # Stage 3: Citation Generation
        if include_citations:
            t_cite = time.time()
            try:
                result.citations = self.citation_generator.generate(
                    result.results, query
                )
            except Exception as e:
                logger.warning(f"Citation generation failed: {e}")
            result.timings["citation_ms"] = (time.time() - t_cite) * 1000

        # Stage 4: Context Formatting
        if include_context:
            t_ctx = time.time()
            result.context = self._build_context(query, result.results, result.citations)
            result.timings["context_ms"] = (time.time() - t_ctx) * 1000

        result.timings["total_ms"] = (time.time() - t0) * 1000

        # Fire after_search hook — allows result filtering, enrichment, etc.
        if result.results:
            result.results = HookManager.fire(
                "after_search", result.results, query=query
            )

        return result

    def _build_context(
        self,
        query: str,
        results: List[SearchResult],
        citations: List[Citation],
    ) -> str:
        """
        Build a formatted context string for LLM injection.

        Format:
        ```
        Query: {query}

        Context:
        [1] Title (source_type, chunk N/M)
        ---
        Excerpt text...
        ---

        [2] Title (source_type)
        ---
        Excerpt text...
        ---

        (repeat for each result)
        ```
        """
        if not results:
            return "No relevant documents found for this query."

        lines = [f"Query: {query}", "", "Context:", ""]

        for i, res in enumerate(results, start=1):
            doc = res.document

            # Title from metadata
            title = doc.metadata.get("title", "") or self._derive_title(doc.source_path)
            source_type = doc.source_type.value
            chunk_info = ""
            if doc.total_chunks > 1:
                chunk_info = f", chunk {doc.chunk_index + 1}/{doc.total_chunks}"

            # Score indicator
            score_bar = self._score_bar(res.combined_score)

            lines.append(f"[{i}] {title} ({source_type}){chunk_info} {score_bar}")
            lines.append("---")
            lines.append(doc.content[:800].strip())  # Truncate very long chunks
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _derive_title(source_path: str) -> str:
        """Derive title from source path."""
        import re
        from pathlib import Path
        try:
            name = Path(source_path).stem
            name = re.sub(r'[_-]+', ' ', name).strip()
            return name or "Untitled"
        except Exception:
            return "Unknown"

    @staticmethod
    def _score_bar(score: float, width: int = 10) -> str:
        """Create a simple ASCII score bar."""
        filled = int(score * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty} {score:.2f}]"

    # ── Convenience methods ─────────────────────────────────────────────

    def rebuild_bm25_index(self) -> int:
        """Rebuild the BM25 index from the vector store.

        Call this after adding many documents to keep the keyword index fresh.

        Returns:
            Number of documents indexed.
        """
        return self.hybrid_search.rebuild_bm25_index()

    def warm_up(self) -> None:
        """
        Pre-load models to avoid first-query latency.

        Loads both the BM25 index and the cross-encoder model (if available).
        """
        # Rebuild BM25
        self.rebuild_bm25_index()

        # Pre-load reranker
        if self._enable_rerank:
            self.reranker.warm_up()

        logger.info("RAG engine warm-up complete")

    def health_check(self) -> dict:
        """
        Check the health of all RAG components.

        Returns:
            Dict with status of each component (healthy/unavailable/error).
        """
        status = {}

        # BM25
        try:
            count = self.hybrid_search.bm25.rebuild_index()
            status["bm25"] = {"healthy": True, "doc_count": count}
        except Exception as e:
            status["bm25"] = {"healthy": False, "error": str(e)}

        # Reranker
        try:
            if self._enable_rerank:
                available = self.reranker.warm_up()
                status["reranker"] = {
                    "healthy": True,
                    "model": self.reranker._model_name if available else "heuristic",
                    "method": "cross-encoder" if available else "heuristic",
                }
            else:
                status["reranker"] = {"healthy": True, "method": "disabled"}
        except Exception as e:
            status["reranker"] = {"healthy": False, "error": str(e)}

        # Store
        try:
            count = self._store.count()
            status["vector_store"] = {"healthy": True, "doc_count": count}
        except Exception as e:
            status["vector_store"] = {"healthy": False, "error": str(e)}

        return status
