"""
RAG Retrieval System — Complete Implementation

Production-grade retrieval with:
- Dense vector search (embedding generation)
- Sparse/BM25 keyword search
- Hybrid search (RRF fusion, weighted combination)
- Metadata filtering
- Reranking (cross-encoder)
- Multi-query retrieval
- Query rewriting
- HyDE (Hypothetical Document Embeddings)
- Access-controlled retrieval (ACL filtering)
- Citation building

Dependencies:
    pip install numpy openai sentence-transformers rank-bm25
    pip install pydantic tiktoken
"""

from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Domain Models ─────────────────────────────────────────────────────────────


class RetrievalMethod(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class ScoredChunk(BaseModel):
    """A chunk with retrieval scores."""
    chunk_id: str
    content: str
    score: float = 0.0
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rerank_score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_method: RetrievalMethod = RetrievalMethod.DENSE


class Citation(BaseModel):
    """A citation linking answer text to source chunk."""
    citation_id: int
    chunk_id: str
    source_id: str
    source_title: str = ""
    page_number: Optional[int] = None
    section_title: str = ""
    snippet: str = ""  # Relevant excerpt from the chunk


class RetrievalRequest(BaseModel):
    """Input to the retrieval system."""
    query: str
    top_k: int = 10
    method: RetrievalMethod = RetrievalMethod.HYBRID
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    user_acl_groups: list[str] = Field(default_factory=list)
    rerank: bool = True
    min_score_threshold: float = 0.0


class RetrievalResponse(BaseModel):
    """Output from the retrieval system."""
    chunks: list[ScoredChunk] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    query_used: str = ""
    method_used: RetrievalMethod = RetrievalMethod.HYBRID
    retrieval_time_ms: float = 0.0
    total_candidates: int = 0


# ─── Embedding Service ─────────────────────────────────────────────────────────


class EmbeddingService:
    """
    Generate embeddings using OpenAI or local models.
    Supports batching and caching.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        use_local: bool = False,
        local_model: str = "all-MiniLM-L6-v2",
    ):
        self.model = model
        self.use_local = use_local
        self.local_model = local_model
        self._local_encoder = None
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_local:
            embedding = self._embed_local(text)
        else:
            embedding = self._embed_openai(text)

        self._cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        if self.use_local:
            return self._embed_local_batch(texts)
        return self._embed_openai_batch(texts)

    def _embed_openai(self, text: str) -> list[float]:
        from openai import OpenAI
        client = OpenAI()
        response = client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding

    def _embed_openai_batch(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        client = OpenAI()
        response = client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    def _embed_local(self, text: str) -> list[float]:
        encoder = self._get_local_encoder()
        return encoder.encode(text).tolist()

    def _embed_local_batch(self, texts: list[str]) -> list[list[float]]:
        encoder = self._get_local_encoder()
        return encoder.encode(texts).tolist()

    def _get_local_encoder(self):
        if self._local_encoder is None:
            from sentence_transformers import SentenceTransformer
            self._local_encoder = SentenceTransformer(self.local_model)
        return self._local_encoder


# ─── Vector Store (In-Memory for Demo) ────────────────────────────────────────


class VectorStore:
    """
    In-memory vector store with cosine similarity search.
    In production, replace with: Qdrant, Pinecone, Weaviate, Azure AI Search, pgvector.
    """

    def __init__(self):
        self._vectors: list[np.ndarray] = []
        self._chunks: list[dict[str, Any]] = []  # chunk data
        self._ids: list[str] = []

    def add(self, chunk_id: str, embedding: list[float], chunk_data: dict[str, Any]) -> None:
        self._ids.append(chunk_id)
        self._vectors.append(np.array(embedding))
        self._chunks.append(chunk_data)

    def add_batch(self, items: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        for chunk_id, embedding, chunk_data in items:
            self.add(chunk_id, embedding, chunk_data)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        acl_groups: list[str] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """
        Cosine similarity search with optional filtering.
        Returns list of (chunk_id, score, chunk_data).
        """
        if not self._vectors:
            return []

        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        results = []
        for i, vec in enumerate(self._vectors):
            chunk_data = self._chunks[i]

            # ACL filtering
            if acl_groups:
                chunk_acl = chunk_data.get("access_control", [])
                if chunk_acl and not any(g in chunk_acl for g in acl_groups):
                    continue

            # Metadata filtering
            if metadata_filters:
                if not self._matches_filters(chunk_data, metadata_filters):
                    continue

            # Cosine similarity
            score = np.dot(query_vec, vec) / (query_norm * np.linalg.norm(vec))
            results.append((self._ids[i], float(score), chunk_data))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _matches_filters(self, chunk_data: dict, filters: dict) -> bool:
        for key, value in filters.items():
            chunk_value = chunk_data.get(key)
            if isinstance(value, list):
                if chunk_value not in value:
                    return False
            elif chunk_value != value:
                return False
        return True

    @property
    def count(self) -> int:
        return len(self._ids)

    def delete(self, chunk_id: str) -> None:
        if chunk_id in self._ids:
            idx = self._ids.index(chunk_id)
            self._ids.pop(idx)
            self._vectors.pop(idx)
            self._chunks.pop(idx)


# ─── BM25 Search ──────────────────────────────────────────────────────────────


class BM25Index:
    """
    BM25 sparse retrieval using rank_bm25 library.
    Provides keyword-based search complementary to vector search.
    """

    def __init__(self):
        self._documents: list[dict[str, Any]] = []
        self._corpus: list[list[str]] = []  # tokenized
        self._bm25 = None
        self._ids: list[str] = []

    def add(self, chunk_id: str, text: str, chunk_data: dict[str, Any]) -> None:
        self._ids.append(chunk_id)
        self._documents.append(chunk_data)
        self._corpus.append(self._tokenize(text))
        self._bm25 = None  # Invalidate index

    def add_batch(self, items: list[tuple[str, str, dict[str, Any]]]) -> None:
        for chunk_id, text, chunk_data in items:
            self._ids.append(chunk_id)
            self._documents.append(chunk_data)
            self._corpus.append(self._tokenize(text))
        self._bm25 = None

    def search(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        acl_groups: list[str] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """BM25 search. Returns (chunk_id, score, chunk_data)."""
        if not self._corpus:
            return []

        self._build_index()
        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        results = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            chunk_data = self._documents[i]

            # ACL filtering
            if acl_groups:
                chunk_acl = chunk_data.get("access_control", [])
                if chunk_acl and not any(g in chunk_acl for g in acl_groups):
                    continue

            # Metadata filtering
            if metadata_filters:
                if not self._matches_filters(chunk_data, metadata_filters):
                    continue

            results.append((self._ids[i], float(score), chunk_data))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _build_index(self):
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._corpus)

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercasing tokenization."""
        import re
        text = text.lower()
        tokens = re.findall(r"\b\w+\b", text)
        # Remove very short tokens
        return [t for t in tokens if len(t) > 1]

    def _matches_filters(self, chunk_data: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if chunk_data.get(key) != value:
                return False
        return True


# ─── Hybrid Search with Fusion ────────────────────────────────────────────────


class HybridSearcher:
    """
    Combines dense and sparse search results using score fusion.
    Supports RRF (Reciprocal Rank Fusion) and weighted combination.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        embedding_service: EmbeddingService,
        fusion_method: str = "rrf",  # "rrf" or "weighted"
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedding_service = embedding_service
        self.fusion_method = fusion_method
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        acl_groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        """Execute hybrid search with score fusion."""

        # Get more candidates than needed for fusion
        candidate_k = top_k * 3

        # Dense search
        query_embedding = self.embedding_service.embed(query)
        dense_results = self.vector_store.search(
            query_embedding, top_k=candidate_k,
            metadata_filters=metadata_filters, acl_groups=acl_groups,
        )

        # Sparse search
        sparse_results = self.bm25_index.search(
            query, top_k=candidate_k,
            metadata_filters=metadata_filters, acl_groups=acl_groups,
        )

        # Fuse results
        if self.fusion_method == "rrf":
            fused = self._reciprocal_rank_fusion(dense_results, sparse_results)
        else:
            fused = self._weighted_combination(dense_results, sparse_results)

        # Convert to ScoredChunks
        scored_chunks = []
        for chunk_id, score, dense_score, sparse_score, chunk_data in fused[:top_k]:
            scored_chunks.append(ScoredChunk(
                chunk_id=chunk_id,
                content=chunk_data.get("content", ""),
                score=score,
                dense_score=dense_score,
                sparse_score=sparse_score,
                metadata=chunk_data,
                retrieval_method=RetrievalMethod.HYBRID,
            ))

        return scored_chunks

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[tuple[str, float, dict]],
        sparse_results: list[tuple[str, float, dict]],
    ) -> list[tuple[str, float, float, float, dict]]:
        """
        RRF: score = sum(1 / (k + rank)) across result lists.
        Robust to score scale differences between methods.
        """
        scores: dict[str, dict] = {}

        for rank, (chunk_id, score, data) in enumerate(dense_results):
            if chunk_id not in scores:
                scores[chunk_id] = {"dense_score": score, "sparse_score": 0.0, "data": data, "rrf": 0.0}
            scores[chunk_id]["rrf"] += 1.0 / (self.rrf_k + rank + 1)
            scores[chunk_id]["dense_score"] = score

        for rank, (chunk_id, score, data) in enumerate(sparse_results):
            if chunk_id not in scores:
                scores[chunk_id] = {"dense_score": 0.0, "sparse_score": score, "data": data, "rrf": 0.0}
            scores[chunk_id]["rrf"] += 1.0 / (self.rrf_k + rank + 1)
            scores[chunk_id]["sparse_score"] = score

        results = [
            (chunk_id, info["rrf"], info["dense_score"], info["sparse_score"], info["data"])
            for chunk_id, info in scores.items()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _weighted_combination(
        self,
        dense_results: list[tuple[str, float, dict]],
        sparse_results: list[tuple[str, float, dict]],
    ) -> list[tuple[str, float, float, float, dict]]:
        """Weighted linear combination of normalized scores."""
        scores: dict[str, dict] = {}

        # Normalize dense scores to [0, 1]
        if dense_results:
            max_dense = max(r[1] for r in dense_results)
            min_dense = min(r[1] for r in dense_results)
            dense_range = max_dense - min_dense or 1.0
        else:
            dense_range = 1.0
            min_dense = 0.0

        for chunk_id, score, data in dense_results:
            norm_score = (score - min_dense) / dense_range
            scores[chunk_id] = {
                "dense_score": score,
                "sparse_score": 0.0,
                "data": data,
                "combined": norm_score * self.dense_weight,
            }

        # Normalize sparse scores
        if sparse_results:
            max_sparse = max(r[1] for r in sparse_results)
            min_sparse = min(r[1] for r in sparse_results)
            sparse_range = max_sparse - min_sparse or 1.0
        else:
            sparse_range = 1.0
            min_sparse = 0.0

        for chunk_id, score, data in sparse_results:
            norm_score = (score - min_sparse) / sparse_range
            if chunk_id not in scores:
                scores[chunk_id] = {"dense_score": 0.0, "sparse_score": score, "data": data, "combined": 0.0}
            scores[chunk_id]["combined"] += norm_score * self.sparse_weight
            scores[chunk_id]["sparse_score"] = score

        results = [
            (chunk_id, info["combined"], info["dense_score"], info["sparse_score"], info["data"])
            for chunk_id, info in scores.items()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ─── Reranker ──────────────────────────────────────────────────────────────────


class Reranker:
    """
    Cross-encoder reranker for precision improvement.
    Takes initial retrieval results and reorders by relevance.
    """

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, chunks: list[ScoredChunk], top_k: int = 5) -> list[ScoredChunk]:
        """Rerank chunks using cross-encoder scoring."""
        if not chunks:
            return []

        model = self._get_model()

        # Create query-document pairs
        pairs = [(query, chunk.content) for chunk in chunks]

        # Score all pairs
        scores = model.predict(pairs)

        # Attach rerank scores
        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)

        # Sort by rerank score
        chunks.sort(key=lambda c: c.rerank_score or 0, reverse=True)

        return chunks[:top_k]


class CohereReranker:
    """Reranker using Cohere Rerank API (production-grade)."""

    def __init__(self, model: str = "rerank-english-v3.0"):
        self.model = model

    def rerank(self, query: str, chunks: list[ScoredChunk], top_k: int = 5) -> list[ScoredChunk]:
        import cohere
        co = cohere.Client()

        documents = [chunk.content for chunk in chunks]
        response = co.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=top_k,
        )

        reranked = []
        for result in response.results:
            chunk = chunks[result.index]
            chunk.rerank_score = result.relevance_score
            reranked.append(chunk)

        return reranked


# ─── Multi-Query Retrieval ────────────────────────────────────────────────────


class MultiQueryRetriever:
    """
    Generate multiple query reformulations and retrieve for each.
    Merges results for better recall on ambiguous queries.
    """

    def __init__(self, searcher: HybridSearcher, num_queries: int = 3):
        self.searcher = searcher
        self.num_queries = num_queries

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        acl_groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        """Generate multiple queries and merge results."""
        queries = self._generate_queries(query)
        logger.info(f"Multi-query generated {len(queries)} queries: {queries}")

        all_chunks: dict[str, ScoredChunk] = {}

        for q in queries:
            results = self.searcher.search(q, top_k=top_k, metadata_filters=metadata_filters, acl_groups=acl_groups)
            for chunk in results:
                if chunk.chunk_id in all_chunks:
                    # Keep the higher score
                    if chunk.score > all_chunks[chunk.chunk_id].score:
                        all_chunks[chunk.chunk_id] = chunk
                else:
                    all_chunks[chunk.chunk_id] = chunk

        # Sort by score and return top_k
        merged = sorted(all_chunks.values(), key=lambda c: c.score, reverse=True)
        return merged[:top_k]

    def _generate_queries(self, query: str) -> list[str]:
        """Use LLM to generate query reformulations."""
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Generate {self.num_queries} different search queries that would help answer the user's question. "
                        "Each query should approach the question from a different angle. "
                        "Return only the queries, one per line."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.7,
            max_tokens=200,
        )

        generated = response.choices[0].message.content.strip().split("\n")
        # Include original query
        all_queries = [query] + [q.strip().lstrip("0123456789.-) ") for q in generated if q.strip()]
        return all_queries[: self.num_queries + 1]


# ─── Query Rewriting ──────────────────────────────────────────────────────────


class QueryRewriter:
    """
    Rewrite queries for better retrieval:
    - Expand abbreviations
    - Add context from conversation
    - Fix typos
    - Make queries more specific
    """

    def rewrite(self, query: str, conversation_history: list[dict] | None = None) -> str:
        """Rewrite query using LLM for better retrieval."""
        from openai import OpenAI
        client = OpenAI()

        system_prompt = (
            "You are a search query optimizer. Rewrite the user's query to be more effective for semantic search. "
            "Rules:\n"
            "- Expand abbreviations\n"
            "- Make implicit context explicit\n"
            "- Keep it concise (1-2 sentences max)\n"
            "- If conversation history is provided, resolve pronouns and references\n"
            "- Return ONLY the rewritten query, nothing else"
        )

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            context = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]
            )
            messages.append({"role": "user", "content": f"Conversation context:\n{context}\n\nQuery to rewrite: {query}"})
        else:
            messages.append({"role": "user", "content": query})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            max_tokens=100,
        )

        rewritten = response.choices[0].message.content.strip()
        logger.info(f"Query rewritten: '{query}' → '{rewritten}'")
        return rewritten


# ─── HyDE (Hypothetical Document Embeddings) ──────────────────────────────────


class HyDERetriever:
    """
    Hypothetical Document Embeddings:
    1. Generate a hypothetical answer to the query
    2. Embed the hypothetical answer
    3. Use that embedding to search for real documents

    This bridges the query-document semantic gap.
    """

    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        acl_groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        """Generate hypothetical doc, embed it, search with that embedding."""

        # Step 1: Generate hypothetical document
        hypothetical_doc = self._generate_hypothetical(query)
        logger.info(f"HyDE generated hypothetical ({len(hypothetical_doc)} chars)")

        # Step 2: Embed the hypothetical document
        hyde_embedding = self.embedding_service.embed(hypothetical_doc)

        # Step 3: Search using the hypothetical embedding
        results = self.vector_store.search(
            hyde_embedding, top_k=top_k,
            metadata_filters=metadata_filters, acl_groups=acl_groups,
        )

        return [
            ScoredChunk(
                chunk_id=chunk_id,
                content=data.get("content", ""),
                score=score,
                dense_score=score,
                metadata=data,
                retrieval_method=RetrievalMethod.DENSE,
            )
            for chunk_id, score, data in results
        ]

    def _generate_hypothetical(self, query: str) -> str:
        """Generate a hypothetical answer to use as search query."""
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short paragraph that would be a perfect answer to the user's question. "
                        "Write it as if it's from a textbook or documentation. "
                        "Be specific and factual. 3-5 sentences maximum."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=200,
        )

        return response.choices[0].message.content.strip()


# ─── Citation Builder ──────────────────────────────────────────────────────────


class CitationBuilder:
    """Build citations from retrieved chunks for attribution."""

    def build_citations(self, chunks: list[ScoredChunk]) -> list[Citation]:
        """Create numbered citations from retrieved chunks."""
        citations = []
        for i, chunk in enumerate(chunks, start=1):
            citation = Citation(
                citation_id=i,
                chunk_id=chunk.chunk_id,
                source_id=chunk.metadata.get("source_id", ""),
                source_title=chunk.metadata.get("title", ""),
                page_number=chunk.metadata.get("page_number"),
                section_title=chunk.metadata.get("section_title", ""),
                snippet=self._extract_snippet(chunk.content, max_length=150),
            )
            citations.append(citation)
        return citations

    def format_context_with_citations(self, chunks: list[ScoredChunk]) -> str:
        """Format chunks as numbered context for LLM consumption."""
        parts = []
        for i, chunk in enumerate(chunks, start=1):
            source = chunk.metadata.get("source_id", "unknown")
            parts.append(f"[{i}] (Source: {source})\n{chunk.content}")
        return "\n\n---\n\n".join(parts)

    def _extract_snippet(self, content: str, max_length: int = 150) -> str:
        """Extract a meaningful snippet from chunk content."""
        # Take first sentence or first max_length chars
        sentences = content.split(". ")
        if sentences and len(sentences[0]) <= max_length:
            return sentences[0] + "."
        return content[:max_length].rsplit(" ", 1)[0] + "..."


# ─── Complete Retrieval Service ────────────────────────────────────────────────


class RetrievalService:
    """
    Unified retrieval service combining all strategies.
    This is the main entry point for the RAG pipeline's retrieval stage.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        bm25_index: BM25Index | None = None,
        embedding_service: EmbeddingService | None = None,
        reranker: Reranker | None = None,
        enable_hyde: bool = False,
        enable_multi_query: bool = False,
        enable_query_rewriting: bool = False,
    ):
        self.vector_store = vector_store or VectorStore()
        self.bm25_index = bm25_index or BM25Index()
        self.embedding_service = embedding_service or EmbeddingService(use_local=True)
        self.reranker = reranker
        self.enable_hyde = enable_hyde
        self.enable_multi_query = enable_multi_query
        self.enable_query_rewriting = enable_query_rewriting

        # Composite components
        self.hybrid_searcher = HybridSearcher(
            self.vector_store, self.bm25_index, self.embedding_service
        )
        self.query_rewriter = QueryRewriter() if enable_query_rewriting else None
        self.multi_query = MultiQueryRetriever(self.hybrid_searcher) if enable_multi_query else None
        self.hyde = HyDERetriever(self.vector_store, self.embedding_service) if enable_hyde else None
        self.citation_builder = CitationBuilder()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """
        Execute full retrieval pipeline:
        1. Optional query rewriting
        2. Retrieval (dense/sparse/hybrid/HyDE/multi-query)
        3. Optional reranking
        4. ACL filtering (already applied in search)
        5. Citation building
        """
        start_time = time.perf_counter()
        query = request.query

        # Step 1: Query rewriting
        if self.query_rewriter and self.enable_query_rewriting:
            query = self.query_rewriter.rewrite(query)

        # Step 2: Retrieval
        if self.enable_multi_query and self.multi_query:
            chunks = self.multi_query.retrieve(
                query, top_k=request.top_k * 2,
                metadata_filters=request.metadata_filters,
                acl_groups=request.user_acl_groups,
            )
        elif self.enable_hyde and self.hyde:
            chunks = self.hyde.retrieve(
                query, top_k=request.top_k * 2,
                metadata_filters=request.metadata_filters,
                acl_groups=request.user_acl_groups,
            )
        elif request.method == RetrievalMethod.HYBRID:
            chunks = self.hybrid_searcher.search(
                query, top_k=request.top_k * 2,
                metadata_filters=request.metadata_filters,
                acl_groups=request.user_acl_groups,
            )
        elif request.method == RetrievalMethod.DENSE:
            embedding = self.embedding_service.embed(query)
            results = self.vector_store.search(
                embedding, top_k=request.top_k * 2,
                metadata_filters=request.metadata_filters,
                acl_groups=request.user_acl_groups,
            )
            chunks = [
                ScoredChunk(chunk_id=cid, content=data.get("content", ""), score=score, dense_score=score, metadata=data)
                for cid, score, data in results
            ]
        else:  # SPARSE
            results = self.bm25_index.search(
                query, top_k=request.top_k * 2,
                metadata_filters=request.metadata_filters,
                acl_groups=request.user_acl_groups,
            )
            chunks = [
                ScoredChunk(chunk_id=cid, content=data.get("content", ""), score=score, sparse_score=score, metadata=data)
                for cid, score, data in results
            ]

        total_candidates = len(chunks)

        # Step 3: Reranking
        if request.rerank and self.reranker and chunks:
            chunks = self.reranker.rerank(query, chunks, top_k=request.top_k)
        else:
            chunks = chunks[: request.top_k]

        # Step 4: Score threshold filtering
        if request.min_score_threshold > 0:
            chunks = [c for c in chunks if c.score >= request.min_score_threshold]

        # Step 5: Build citations
        citations = self.citation_builder.build_citations(chunks)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return RetrievalResponse(
            chunks=chunks,
            citations=citations,
            query_used=query,
            method_used=request.method,
            retrieval_time_ms=elapsed_ms,
            total_candidates=total_candidates,
        )

    def index_chunk(self, chunk_id: str, content: str, metadata: dict[str, Any]) -> None:
        """Add a chunk to both vector and BM25 indices."""
        embedding = self.embedding_service.embed(content)
        chunk_data = {**metadata, "content": content}
        self.vector_store.add(chunk_id, embedding, chunk_data)
        self.bm25_index.add(chunk_id, content, chunk_data)

    def index_batch(self, chunks: list[dict[str, Any]]) -> None:
        """Batch index chunks. Each dict needs: id, content, metadata."""
        texts = [c["content"] for c in chunks]
        embeddings = self.embedding_service.embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk_data = {**chunk.get("metadata", {}), "content": chunk["content"]}
            self.vector_store.add(chunk["id"], embedding, chunk_data)
            self.bm25_index.add(chunk["id"], chunk["content"], chunk_data)

        logger.info(f"Indexed {len(chunks)} chunks")


# ─── Usage Example ─────────────────────────────────────────────────────────────


def main():
    """Demonstrate the retrieval system."""

    # Initialize with local embeddings for demo
    service = RetrievalService(
        embedding_service=EmbeddingService(use_local=True),
    )

    # Index some sample chunks
    sample_chunks = [
        {"id": "1", "content": "RAG stands for Retrieval-Augmented Generation. It grounds LLM outputs in external data.", "metadata": {"source_id": "rag-guide", "title": "RAG Guide"}},
        {"id": "2", "content": "BM25 is a bag-of-words retrieval function that ranks documents by term frequency.", "metadata": {"source_id": "search-101", "title": "Search 101"}},
        {"id": "3", "content": "Reranking uses a cross-encoder model to rescore initial retrieval results for better precision.", "metadata": {"source_id": "rag-guide", "title": "RAG Guide"}},
        {"id": "4", "content": "Vector databases store embeddings and support approximate nearest neighbor search.", "metadata": {"source_id": "vector-db", "title": "Vector DBs"}},
        {"id": "5", "content": "Hybrid search combines dense vector search with sparse BM25 using reciprocal rank fusion.", "metadata": {"source_id": "rag-guide", "title": "RAG Guide"}},
    ]

    service.index_batch(sample_chunks)
    print(f"Indexed {service.vector_store.count} chunks")

    # Search
    request = RetrievalRequest(
        query="How does hybrid search work?",
        top_k=3,
        method=RetrievalMethod.HYBRID,
        rerank=False,
    )

    response = service.retrieve(request)
    print(f"\nQuery: {request.query}")
    print(f"Retrieved {len(response.chunks)} chunks in {response.retrieval_time_ms:.1f}ms")
    for chunk in response.chunks:
        print(f"  [{chunk.chunk_id}] score={chunk.score:.4f}: {chunk.content[:80]}...")


if __name__ == "__main__":
    main()
