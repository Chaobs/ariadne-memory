"""
LLM-powered Reranker for improved search results.

Uses an LLM to re-rank initial search results based on semantic relevance
to the query, improving result quality beyond simple vector similarity.
"""

from ariadne.llm.base import BaseLLM, LLMResponse
from ariadne.ingest.base import Document
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LLMReranker:
    """
    LLM-powered semantic reranker.
    
    Takes initial search results and re-ranks them using an LLM to evaluate
    semantic relevance to the query. This can significantly improve
    result quality for complex queries.
    
    Example:
        reranker = LLMReranker(llm)
        results = vector_store.search("quantum physics", top_k=20)
        reranked = reranker.rerank("quantum physics", results, top_k=5)
    """
    
    RERANK_PROMPT = """You are a relevance expert. Given a query and a document, rate how relevant the document is to answering the query on a scale from 0 to 10.

Query: {query}

Document:
{document}

Consider:
- Does the document directly address the query topic?
- Does it contain information that helps answer the query?
- Is it more relevant than other documents about similar topics?

Provide only a single number (0-10) as your response."""

    RERANK_BATCH_PROMPT = """You are a relevance expert. Rate how relevant each document is to the query on a scale from 0 to 10.

Query: {query}

Documents:
{documents}

Provide ratings in this format, one per line:
[Document 1] score: X
[Document 2] score: X
...

Only provide the ratings, nothing else."""

    def __init__(
        self,
        llm: BaseLLM,
        rerank_top_k: int = 5,
        initial_top_k: int = 20,
        use_batch: bool = True,
    ):
        """
        Initialize the reranker.
        
        Args:
            llm: LLM instance for scoring.
            rerank_top_k: Number of results to return after reranking.
            initial_top_k: Number of results to fetch initially for reranking.
            use_batch: Use batch scoring when True (faster), sequential when False.
        """
        self.llm = llm
        self.rerank_top_k = rerank_top_k
        self.initial_top_k = initial_top_k
        self.use_batch = use_batch
    
    def rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Document, float, float]]:
        """
        Re-rank search results based on semantic relevance.
        
        Args:
            query: The search query.
            results: List of (Document, score) tuples from initial search.
            top_k: Number of results to return (defaults to self.rerank_top_k).
            
        Returns:
            List of (Document, original_score, rerank_score) tuples,
            sorted by rerank_score descending.
        """
        if not results:
            return []
        
        top_k = top_k or self.rerank_top_k
        
        # Limit to initial_top_k for efficiency
        results = results[:self.initial_top_k]
        
        if self.use_batch:
            return self._batch_rerank(query, results, top_k)
        else:
            return self._sequential_rerank(query, results, top_k)
    
    def _batch_rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float, float]]:
        """Batch rerank all documents at once."""
        docs_text = "\n".join(
            f"[Document {i+1}] {doc.content[:500]}"
            for i, (doc, _) in enumerate(results)
        )
        
        prompt = self.RERANK_BATCH_PROMPT.format(
            query=query,
            documents=docs_text,
        )
        
        try:
            response = self.llm.chat(
                prompt=prompt,
                system="You are a helpful assistant that rates document relevance.",
            )
            
            # Parse scores from response
            scores = self._parse_scores(response.content, len(results))
            
            # Combine scores with original
            reranked = []
            for i, (doc, orig_score) in enumerate(results):
                rerank_score = scores.get(i, 0.0)
                reranked.append((doc, orig_score, rerank_score))
            
            # Sort by rerank score
            reranked.sort(key=lambda x: x[2], reverse=True)
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, returning original results")
            return [(doc, score, 1.0) for doc, score in results[:top_k]]
    
    def _sequential_rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float, float]]:
        """Score each document individually."""
        reranked = []
        
        for doc, orig_score in results:
            prompt = self.RERANK_PROMPT.format(
                query=query,
                document=doc.content[:1000],  # Limit document length
            )
            
            try:
                response = self.llm.chat(prompt=prompt)
                score = self._parse_single_score(response.content)
            except Exception as e:
                logger.warning(f"Single reranking failed: {e}")
                score = orig_score
            
            reranked.append((doc, orig_score, score))
        
        # Sort by rerank score
        reranked.sort(key=lambda x: x[2], reverse=True)
        
        return reranked[:top_k]
    
    def _parse_scores(
        self,
        content: str,
        num_docs: int,
    ) -> dict:
        """Parse batch scores from LLM response."""
        scores = {}
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Try to extract document index and score
            for i in range(1, num_docs + 1):
                if f"[Document {i}]" in line or f"Document {i}" in line:
                    # Extract number from the line
                    import re
                    numbers = re.findall(r"\d+\.?\d*", line.split(":")[-1])
                    if numbers:
                        scores[i - 1] = min(10.0, max(0.0, float(numbers[0])))
                        break
        
        return scores
    
    def _parse_single_score(self, content: str) -> float:
        """Parse a single score from LLM response."""
        import re
        content = content.strip()
        
        # Try to find a number
        numbers = re.findall(r"\d+\.?\d*", content)
        if numbers:
            return min(10.0, max(0.0, float(numbers[0])))
        
        return 0.0


class CrossEncoderReranker:
    """
    Cross-encoder based reranker for faster reranking.
    
    Uses a cross-encoder model (if available) for faster reranking
    compared to LLM-based reranking. Falls back to LLM reranking if
    no model is available.
    """
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """
        Initialize the reranker.
        
        Args:
            llm: Optional LLM for fallback reranking.
        """
        self.llm = llm
        self._model = None
        self._try_load_model()
    
    def _try_load_model(self) -> None:
        """Try to load a cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except ImportError:
            logger.info("sentence-transformers not installed, using LLM reranking")
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}")
    
    def rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        top_k: int = 5,
    ) -> List[Tuple[Document, float, float]]:
        """
        Re-rank results using cross-encoder or LLM.
        """
        if not results:
            return []
        
        if self._model is not None:
            return self._cross_encode_rerank(query, results, top_k)
        elif self.llm is not None:
            reranker = LLMReranker(self.llm, rerank_top_k=top_k)
            return reranker.rerank(query, results, top_k)
        else:
            return [(doc, score, 1.0) for doc, score in results[:top_k]]
    
    def _cross_encode_rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float, float]]:
        """Use cross-encoder for fast reranking."""
        doc_texts = [doc.content for doc, _ in results]
        pairs = [(query, text) for text in doc_texts]
        
        scores = self._model.predict(pairs)
        
        reranked = [
            (doc, orig_score, float(score))
            for (doc, orig_score), score in zip(results, scores)
        ]
        
        reranked.sort(key=lambda x: x[2], reverse=True)
        
        return reranked[:top_k]
