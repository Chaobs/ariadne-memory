"""
Ariadne RAG Pipeline — Retrieval-Augmented Generation infrastructure.

This module provides the RAG (Retrieval-Augmented Generation) pipeline
for Ariadne, enabling high-quality retrieval through hybrid search,
reranking, and citation generation.

Architecture:
    Query → Hybrid Search (vector + BM25) → Reranking → Citations → LLM Context

Components:
    bm25_retriever  — Keyword search via BM25 (rank_bm25)
    hybrid_search   — Combines vector + BM25 with Reciprocal Rank Fusion
    reranker        — Cross-encoder or heuristic reranking
    citation        — Citation generation with highlight extraction
    engine          — Unified RAG pipeline orchestrating all components
"""

from ariadne.rag.bm25_retriever import BM25Retriever
from ariadne.rag.hybrid_search import HybridSearch, SearchResult
from ariadne.rag.reranker import Reranker
from ariadne.rag.citation import CitationGenerator, Citation, CitationContext

__all__ = [
    # Core pipeline
    "BM25Retriever",
    "HybridSearch",
    "SearchResult",
    "Reranker",
    "CitationGenerator",
    "Citation",
    "CitationContext",
    # Convenience — create a full RAG engine
    "create_rag_engine",
]


def create_rag_engine(vector_store, config: dict = None):
    """
    Create a fully configured RAG engine.

    Args:
        vector_store: An ariadne VectorStore instance.
        config: Optional configuration dict with keys:
            - rerank: bool (default True)
            - rerank_model: str (default "cross-encoder/ms-marco-MiniLM-L-6-v2")
            - use_heuristic_rerank: bool (default False)
            - alpha: float (default 0.5, vector weight in hybrid search)
            - top_k: int (default 5, default result count)

    Returns:
        A configured RAGEngine instance.
    """
    from ariadne.rag.engine import RAGEngine

    config = config or {}
    return RAGEngine(
        vector_store=vector_store,
        enable_rerank=config.get("rerank", True),
        rerank_model=config.get("rerank_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        use_heuristic=config.get("use_heuristic_rerank", False),
        alpha=config.get("alpha", 0.5),
        default_top_k=config.get("top_k", 5),
    )
