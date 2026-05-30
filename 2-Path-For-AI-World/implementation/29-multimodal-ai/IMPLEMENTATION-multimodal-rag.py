"""
Multimodal RAG Implementation
==============================
Retrieval-Augmented Generation across text, images, tables, and charts
with multimodal embedding, retrieval, and vision-language generation.
"""

import json
import hashlib
import logging
import numpy as np
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# Core Data Models
# =============================================================================

class ModalityType(Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    CHART = "chart"
    AUDIO = "audio"


@dataclass
class MultimodalChunk:
    """A chunk that can be text, image, table, or chart."""
    chunk_id: str
    modality: ModalityType
    content: str  # Text content or description
    embedding: Optional[np.ndarray] = None
    # Source info
    document_id: str = ""
    page: int = 0
    bbox: Optional[dict] = None
    # Modality-specific data
    image_data: Optional[bytes] = None
    table_data: Optional[list[dict]] = None
    chart_data: Optional[dict] = None
    # Metadata
    metadata: dict = field(default_factory=dict)
    # For text chunks
    section_title: str = ""
    heading_hierarchy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "modality": self.modality.value,
            "content": self.content,
            "document_id": self.document_id,
            "page": self.page,
            "bbox": self.bbox,
            "metadata": self.metadata,
            "section_title": self.section_title,
        }


@dataclass
class RetrievalResult:
    """A single retrieval result with score."""
    chunk: MultimodalChunk
    score: float
    retrieval_method: str = "embedding"  # embedding, keyword, hybrid

    @property
    def modality(self) -> ModalityType:
        return self.chunk.modality


@dataclass
class MultimodalContext:
    """Assembled context from multiple modalities for generation."""
    text_chunks: list[MultimodalChunk] = field(default_factory=list)
    images: list[MultimodalChunk] = field(default_factory=list)
    tables: list[MultimodalChunk] = field(default_factory=list)
    charts: list[MultimodalChunk] = field(default_factory=list)
    total_tokens_estimate: int = 0

    def all_chunks(self) -> list[MultimodalChunk]:
        return self.text_chunks + self.images + self.tables + self.charts


@dataclass
class MultimodalCitation:
    """Citation pointing to a specific modality and location."""
    text: str
    document_id: str
    page: int
    modality: ModalityType
    bbox: Optional[dict] = None
    table_cell: Optional[dict] = None  # {row, col} for table citations
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "document_id": self.document_id,
            "page": self.page,
            "modality": self.modality.value,
            "bbox": self.bbox,
            "table_cell": self.table_cell,
            "confidence": self.confidence
        }


@dataclass
class GenerationResult:
    """Result from multimodal generation."""
    answer: str
    citations: list[MultimodalCitation] = field(default_factory=list)
    context_used: Optional[MultimodalContext] = None
    model_used: str = ""
    confidence: float = 0.0


# =============================================================================
# Embedding Engines
# =============================================================================

class TextEmbedder:
    """Text embedding using OpenAI, Cohere, or local models."""

    def __init__(self, model: str = "text-embedding-3-large", dimension: int = 1536):
        self.model = model
        self.dimension = dimension

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts efficiently."""
        # In production:
        # from openai import OpenAI
        # client = OpenAI()
        # response = client.embeddings.create(model=self.model, input=texts)
        # return [np.array(e.embedding) for e in response.data]

        # Simulated embeddings
        return [np.random.randn(self.dimension).astype(np.float32) for _ in texts]


class ImageEmbedder:
    """Image embedding using CLIP/SigLIP for cross-modal search."""

    def __init__(self, model: str = "openai/clip-vit-large-patch14"):
        self.model = model
        self.dimension = 768

    def embed_image(self, image_data: bytes) -> np.ndarray:
        """Embed an image into the shared text-image space."""
        # In production:
        # from transformers import CLIPProcessor, CLIPModel
        # from PIL import Image
        # model = CLIPModel.from_pretrained(self.model)
        # processor = CLIPProcessor.from_pretrained(self.model)
        # image = Image.open(io.BytesIO(image_data))
        # inputs = processor(images=image, return_tensors="pt")
        # image_features = model.get_image_features(**inputs)
        # return image_features.detach().numpy().flatten()

        return np.random.randn(self.dimension).astype(np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed text into the shared text-image space (for cross-modal search)."""
        # In production:
        # inputs = processor(text=[text], return_tensors="pt")
        # text_features = model.get_text_features(**inputs)
        # return text_features.detach().numpy().flatten()

        return np.random.randn(self.dimension).astype(np.float32)

    def embed_image_batch(self, images: list[bytes]) -> list[np.ndarray]:
        return [self.embed_image(img) for img in images]


class TableEmbedder:
    """Specialized table embedding - linearizes table structure for embedding."""

    def __init__(self, text_embedder: TextEmbedder):
        self.text_embedder = text_embedder

    def embed_table(self, table_data: list[dict], caption: str = "") -> np.ndarray:
        """Embed a table by linearizing it into text."""
        linearized = self._linearize_table(table_data, caption)
        return self.text_embedder.embed(linearized)

    def embed_table_cells(self, table_data: list[dict]) -> list[tuple[dict, np.ndarray]]:
        """Embed individual cells for fine-grained retrieval."""
        cell_embeddings = []
        if not table_data:
            return []
        headers = list(table_data[0].keys())
        for row_idx, row in enumerate(table_data):
            for col_idx, (key, value) in enumerate(row.items()):
                cell_text = f"{key}: {value}"
                embedding = self.text_embedder.embed(cell_text)
                cell_embeddings.append((
                    {"row": row_idx, "col": col_idx, "header": key,
                     "value": str(value), "text": cell_text},
                    embedding
                ))
        return cell_embeddings

    def _linearize_table(self, table_data: list[dict], caption: str = "") -> str:
        """Convert table to text representation for embedding."""
        parts = []
        if caption:
            parts.append(f"Table: {caption}")

        if not table_data:
            return "Empty table"

        headers = list(table_data[0].keys())
        parts.append(f"Columns: {', '.join(headers)}")

        for i, row in enumerate(table_data[:20]):  # Limit rows for embedding
            row_text = " | ".join(f"{k}: {v}" for k, v in row.items())
            parts.append(f"Row {i+1}: {row_text}")

        if len(table_data) > 20:
            parts.append(f"... and {len(table_data) - 20} more rows")

        return "\n".join(parts)


# =============================================================================
# Multimodal Index
# =============================================================================

class MultimodalIndex:
    """
    Index that stores and retrieves chunks across all modalities.
    Uses separate embedding spaces with score normalization.
    """

    def __init__(self, text_embedder: TextEmbedder,
                 image_embedder: ImageEmbedder,
                 table_embedder: TableEmbedder):
        self.text_embedder = text_embedder
        self.image_embedder = image_embedder
        self.table_embedder = table_embedder

        # Storage (in production: use vector databases like Pinecone, Weaviate, Qdrant)
        self.text_chunks: list[MultimodalChunk] = []
        self.image_chunks: list[MultimodalChunk] = []
        self.table_chunks: list[MultimodalChunk] = []
        self.chart_chunks: list[MultimodalChunk] = []

        # Embedding matrices for fast search
        self._text_embeddings: Optional[np.ndarray] = None
        self._image_embeddings: Optional[np.ndarray] = None
        self._table_embeddings: Optional[np.ndarray] = None

    def add_text_chunk(self, chunk: MultimodalChunk):
        """Add a text chunk to the index."""
        if chunk.embedding is None:
            chunk.embedding = self.text_embedder.embed(chunk.content)
        self.text_chunks.append(chunk)
        self._text_embeddings = None  # Invalidate cache

    def add_image_chunk(self, chunk: MultimodalChunk):
        """Add an image chunk to the index."""
        if chunk.embedding is None and chunk.image_data:
            chunk.embedding = self.image_embedder.embed_image(chunk.image_data)
        elif chunk.embedding is None:
            # Fall back to text description embedding
            chunk.embedding = self.image_embedder.embed_text(chunk.content)
        self.image_chunks.append(chunk)
        self._image_embeddings = None

    def add_table_chunk(self, chunk: MultimodalChunk):
        """Add a table chunk to the index."""
        if chunk.embedding is None:
            chunk.embedding = self.table_embedder.embed_table(
                chunk.table_data or [], chunk.content
            )
        self.table_chunks.append(chunk)
        self._table_embeddings = None

    def add_chart_chunk(self, chunk: MultimodalChunk):
        """Add a chart chunk (treated similar to images with text description)."""
        if chunk.embedding is None:
            chunk.embedding = self.text_embedder.embed(chunk.content)
        self.chart_chunks.append(chunk)

    def add_chunk(self, chunk: MultimodalChunk):
        """Route chunk to appropriate modality index."""
        handlers = {
            ModalityType.TEXT: self.add_text_chunk,
            ModalityType.IMAGE: self.add_image_chunk,
            ModalityType.TABLE: self.add_table_chunk,
            ModalityType.CHART: self.add_chart_chunk,
        }
        handler = handlers.get(chunk.modality)
        if handler:
            handler(chunk)

    def _build_embedding_matrix(self, chunks: list[MultimodalChunk]) -> np.ndarray:
        """Build numpy matrix from chunk embeddings for vectorized search."""
        if not chunks:
            return np.array([])
        embeddings = [c.embedding for c in chunks if c.embedding is not None]
        if not embeddings:
            return np.array([])
        matrix = np.vstack(embeddings)
        # L2 normalize for cosine similarity
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return matrix / norms

    def search_text(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        """Search text chunks."""
        if not self.text_chunks:
            return []
        if self._text_embeddings is None:
            self._text_embeddings = self._build_embedding_matrix(self.text_chunks)
        query_emb = self.text_embedder.embed(query)
        return self._vector_search(query_emb, self._text_embeddings,
                                    self.text_chunks, top_k)

    def search_images(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Search images using text query (cross-modal via CLIP)."""
        if not self.image_chunks:
            return []
        if self._image_embeddings is None:
            self._image_embeddings = self._build_embedding_matrix(self.image_chunks)
        # Use CLIP text encoder for cross-modal search
        query_emb = self.image_embedder.embed_text(query)
        return self._vector_search(query_emb, self._image_embeddings,
                                    self.image_chunks, top_k)

    def search_tables(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Search tables."""
        if not self.table_chunks:
            return []
        if self._table_embeddings is None:
            self._table_embeddings = self._build_embedding_matrix(self.table_chunks)
        query_emb = self.text_embedder.embed(query)
        return self._vector_search(query_emb, self._table_embeddings,
                                    self.table_chunks, top_k)

    def search_all(self, query: str, top_k: int = 10,
                   modality_weights: Optional[dict] = None) -> list[RetrievalResult]:
        """
        Search across all modalities with score fusion.
        
        Args:
            query: Search query
            top_k: Total results to return
            modality_weights: Weight per modality (default equal)
        """
        weights = modality_weights or {
            "text": 1.0, "image": 0.8, "table": 0.9, "chart": 0.7
        }

        all_results = []

        # Search each modality
        text_results = self.search_text(query, top_k=top_k)
        for r in text_results:
            r.score *= weights.get("text", 1.0)
        all_results.extend(text_results)

        image_results = self.search_images(query, top_k=top_k // 2)
        for r in image_results:
            r.score *= weights.get("image", 0.8)
        all_results.extend(image_results)

        table_results = self.search_tables(query, top_k=top_k // 2)
        for r in table_results:
            r.score *= weights.get("table", 0.9)
        all_results.extend(table_results)

        # Sort by score and return top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    def _vector_search(self, query_embedding: np.ndarray,
                       index_matrix: np.ndarray,
                       chunks: list[MultimodalChunk],
                       top_k: int) -> list[RetrievalResult]:
        """Perform cosine similarity search."""
        if index_matrix.size == 0:
            return []

        # Normalize query
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)

        # Cosine similarity (matrix is already normalized)
        scores = index_matrix @ query_norm

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if idx < len(chunks) and scores[idx] > 0:
                results.append(RetrievalResult(
                    chunk=chunks[idx],
                    score=float(scores[idx]),
                    retrieval_method="embedding"
                ))

        return results

    @property
    def total_chunks(self) -> int:
        return (len(self.text_chunks) + len(self.image_chunks) +
                len(self.table_chunks) + len(self.chart_chunks))

    def stats(self) -> dict:
        return {
            "text_chunks": len(self.text_chunks),
            "image_chunks": len(self.image_chunks),
            "table_chunks": len(self.table_chunks),
            "chart_chunks": len(self.chart_chunks),
            "total": self.total_chunks
        }


# =============================================================================
# Context Assembly
# =============================================================================

class ContextAssembler:
    """
    Assembles retrieved results into a coherent context for generation.
    Handles token budgets, deduplication, and ordering.
    """

    def __init__(self, max_text_tokens: int = 4000,
                 max_images: int = 5,
                 max_tables: int = 3):
        self.max_text_tokens = max_text_tokens
        self.max_images = max_images
        self.max_tables = max_tables

    def assemble(self, results: list[RetrievalResult]) -> MultimodalContext:
        """Assemble retrieval results into structured context."""
        context = MultimodalContext()

        # Separate by modality
        text_results = [r for r in results if r.modality == ModalityType.TEXT]
        image_results = [r for r in results if r.modality == ModalityType.IMAGE]
        table_results = [r for r in results if r.modality == ModalityType.TABLE]
        chart_results = [r for r in results if r.modality == ModalityType.CHART]

        # Deduplicate
        text_results = self._deduplicate(text_results)
        image_results = self._deduplicate(image_results)
        table_results = self._deduplicate(table_results)

        # Apply limits
        token_count = 0
        for result in text_results:
            chunk_tokens = len(result.chunk.content.split()) * 1.3  # Rough estimate
            if token_count + chunk_tokens > self.max_text_tokens:
                break
            context.text_chunks.append(result.chunk)
            token_count += chunk_tokens

        context.images = [r.chunk for r in image_results[:self.max_images]]
        context.tables = [r.chunk for r in table_results[:self.max_tables]]
        context.charts = [r.chunk for r in chart_results[:2]]

        # Estimate total tokens
        context.total_tokens_estimate = int(token_count)
        # Images cost ~765 tokens each (low detail) or ~1105+ (high detail) in GPT-4V
        context.total_tokens_estimate += len(context.images) * 1000
        # Tables as text
        context.total_tokens_estimate += sum(
            len(t.content.split()) for t in context.tables
        )

        return context

    def _deduplicate(self, results: list[RetrievalResult],
                      overlap_threshold: float = 0.7) -> list[RetrievalResult]:
        """Remove near-duplicate results."""
        if not results:
            return []

        unique = [results[0]]
        for result in results[1:]:
            is_dup = False
            for existing in unique:
                overlap = self._compute_overlap(result.chunk.content,
                                                existing.chunk.content)
                if overlap > overlap_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(result)

        return unique

    def _compute_overlap(self, text1: str, text2: str) -> float:
        """Compute token overlap between two texts."""
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        return len(intersection) / min(len(tokens1), len(tokens2))


# =============================================================================
# Vision-Language Model Integration
# =============================================================================

class VisionLanguageGenerator:
    """
    Generates answers using vision-language models (GPT-4o, Claude, Gemini).
    Handles mixed text+image contexts.
    """

    def __init__(self, model: str = "gpt-4o", api_key: str = ""):
        self.model = model
        self.api_key = api_key

    def generate(self, query: str, context: MultimodalContext,
                 system_prompt: Optional[str] = None) -> GenerationResult:
        """Generate answer from multimodal context."""
        # Build messages
        messages = self._build_messages(query, context, system_prompt)

        # Call vision-language model
        response = self._call_model(messages)

        # Extract citations from response
        citations = self._extract_citations(response, context)

        return GenerationResult(
            answer=response,
            citations=citations,
            context_used=context,
            model_used=self.model,
            confidence=self._estimate_confidence(response, context)
        )

    def _build_messages(self, query: str, context: MultimodalContext,
                        system_prompt: Optional[str] = None) -> list[dict]:
        """Build message array for vision-language model."""
        messages = []

        # System message
        sys_prompt = system_prompt or self._default_system_prompt()
        messages.append({"role": "system", "content": sys_prompt})

        # User message with multimodal content
        user_content = []

        # Add text context
        if context.text_chunks:
            text_context = "\n\n---\n\n".join(
                f"[Source: {c.document_id}, Page {c.page}]\n{c.content}"
                for c in context.text_chunks
            )
            user_content.append({
                "type": "text",
                "text": f"## Text Context:\n{text_context}"
            })

        # Add table context
        if context.tables:
            table_context = "\n\n".join(
                f"[Table from {c.document_id}, Page {c.page}]\n{c.content}"
                for c in context.tables
            )
            user_content.append({
                "type": "text",
                "text": f"## Table Context:\n{table_context}"
            })

        # Add images
        for img_chunk in context.images:
            if img_chunk.image_data:
                import base64
                b64_image = base64.b64encode(img_chunk.image_data).decode()
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                        "detail": "high"
                    }
                })
                user_content.append({
                    "type": "text",
                    "text": f"[Image from {img_chunk.document_id}, Page {img_chunk.page}]"
                })
            else:
                # No image data, use description
                user_content.append({
                    "type": "text",
                    "text": f"[Image description: {img_chunk.content}]"
                })

        # Add the query
        user_content.append({
            "type": "text",
            "text": f"\n## Question:\n{query}\n\nProvide a detailed answer with citations to specific sources (document, page, element type)."
        })

        messages.append({"role": "user", "content": user_content})
        return messages

    def _call_model(self, messages: list[dict]) -> str:
        """Call the vision-language model."""
        # In production:
        # from openai import OpenAI
        # client = OpenAI(api_key=self.api_key)
        # response = client.chat.completions.create(
        #     model=self.model,
        #     messages=messages,
        #     max_tokens=2000,
        #     temperature=0.1
        # )
        # return response.choices[0].message.content

        return "This is a simulated response from the vision-language model."

    def _default_system_prompt(self) -> str:
        return """You are a document analysis assistant. Answer questions based on the provided context which may include text, tables, and images from documents.

Rules:
1. Only answer based on the provided context
2. Cite your sources using [Document: X, Page: Y] format
3. If information comes from a table, specify the table and relevant cells
4. If information comes from an image/chart, describe what you see
5. If the context doesn't contain enough information, say so clearly
6. Be precise and factual"""

    def _extract_citations(self, response: str, context: MultimodalContext) -> list[MultimodalCitation]:
        """Extract citations from the generated response."""
        citations = []
        import re

        # Find citation patterns like [Document: X, Page: Y]
        citation_pattern = r'\[Document:\s*([^,]+),\s*Page:\s*(\d+)\]'
        matches = re.finditer(citation_pattern, response)

        for match in matches:
            doc_id = match.group(1).strip()
            page = int(match.group(2))

            # Find the corresponding chunk
            for chunk in context.all_chunks():
                if chunk.document_id == doc_id and chunk.page == page:
                    citations.append(MultimodalCitation(
                        text=match.group(0),
                        document_id=doc_id,
                        page=page,
                        modality=chunk.modality,
                        bbox=chunk.bbox,
                        confidence=0.8
                    ))
                    break

        return citations

    def _estimate_confidence(self, response: str, context: MultimodalContext) -> float:
        """Estimate confidence of the generated answer."""
        if not response or response.strip() == "":
            return 0.0
        # Simple heuristics
        has_citations = "[Document:" in response or "[Source:" in response
        has_uncertainty = any(w in response.lower() for w in
                            ["i'm not sure", "unclear", "cannot determine", "insufficient"])
        score = 0.7
        if has_citations:
            score += 0.2
        if has_uncertainty:
            score -= 0.3
        return max(0.0, min(1.0, score))


# =============================================================================
# Multimodal RAG Pipeline
# =============================================================================

class MultimodalRAGPipeline:
    """
    End-to-end multimodal RAG pipeline.
    Ingests documents, indexes all modalities, retrieves, and generates.
    """

    def __init__(self, config: Optional[dict] = None):
        config = config or {}

        # Initialize embedders
        self.text_embedder = TextEmbedder(
            model=config.get("text_model", "text-embedding-3-large"),
            dimension=config.get("text_dimension", 1536)
        )
        self.image_embedder = ImageEmbedder(
            model=config.get("image_model", "openai/clip-vit-large-patch14")
        )
        self.table_embedder = TableEmbedder(self.text_embedder)

        # Initialize index
        self.index = MultimodalIndex(
            self.text_embedder, self.image_embedder, self.table_embedder
        )

        # Initialize context assembler
        self.assembler = ContextAssembler(
            max_text_tokens=config.get("max_text_tokens", 4000),
            max_images=config.get("max_images", 5),
            max_tables=config.get("max_tables", 3)
        )

        # Initialize generator
        self.generator = VisionLanguageGenerator(
            model=config.get("generation_model", "gpt-4o"),
            api_key=config.get("api_key", "")
        )

    def ingest_document(self, doc_id: str, elements: list[dict]):
        """
        Ingest a parsed document's elements into the multimodal index.
        
        Args:
            doc_id: Document identifier
            elements: List of element dicts with type, content, page, bbox, etc.
        """
        logger.info(f"Ingesting document {doc_id} with {len(elements)} elements")

        for elem in elements:
            modality = ModalityType(elem.get("type", "text"))
            chunk = MultimodalChunk(
                chunk_id=f"{doc_id}_{elem.get('page', 0)}_{hashlib.md5(elem.get('content', '')[:50].encode()).hexdigest()[:8]}",
                modality=modality,
                content=elem.get("content", ""),
                document_id=doc_id,
                page=elem.get("page", 0),
                bbox=elem.get("bbox"),
                image_data=elem.get("image_data"),
                table_data=elem.get("table_data"),
                chart_data=elem.get("chart_data"),
                metadata=elem.get("metadata", {}),
                section_title=elem.get("section_title", ""),
                heading_hierarchy=elem.get("heading_hierarchy", [])
            )
            self.index.add_chunk(chunk)

        logger.info(f"Index stats after ingestion: {self.index.stats()}")

    def query(self, question: str, top_k: int = 10,
              modality_weights: Optional[dict] = None) -> GenerationResult:
        """
        Answer a question using multimodal RAG.
        
        Args:
            question: User's question
            top_k: Number of chunks to retrieve
            modality_weights: Weights for each modality in retrieval
        """
        logger.info(f"Processing query: {question[:100]}")

        # Step 1: Retrieve
        results = self.index.search_all(question, top_k=top_k,
                                         modality_weights=modality_weights)
        logger.info(f"Retrieved {len(results)} results across modalities")

        # Step 2: Assemble context
        context = self.assembler.assemble(results)
        logger.info(f"Assembled context: {len(context.text_chunks)} text, "
                    f"{len(context.images)} images, {len(context.tables)} tables")

        # Step 3: Generate
        result = self.generator.generate(question, context)
        logger.info(f"Generated answer with {len(result.citations)} citations")

        return result

    def hybrid_search(self, query: str, top_k: int = 10,
                      keyword_weight: float = 0.3) -> list[RetrievalResult]:
        """
        Hybrid search combining embedding similarity with keyword matching.
        """
        # Embedding search
        embedding_results = self.index.search_all(query, top_k=top_k * 2)

        # Keyword search (BM25-style)
        keyword_results = self._keyword_search(query, top_k=top_k * 2)

        # Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            [embedding_results, keyword_results],
            weights=[1 - keyword_weight, keyword_weight]
        )

        return fused[:top_k]

    def _keyword_search(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        """Simple keyword-based search across all chunks."""
        query_terms = set(query.lower().split())
        results = []

        all_chunks = (self.index.text_chunks + self.index.table_chunks +
                     self.index.chart_chunks)

        for chunk in all_chunks:
            content_terms = set(chunk.content.lower().split())
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                score = overlap / len(query_terms)
                results.append(RetrievalResult(
                    chunk=chunk, score=score, retrieval_method="keyword"
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _reciprocal_rank_fusion(self, result_lists: list[list[RetrievalResult]],
                                 weights: list[float],
                                 k: int = 60) -> list[RetrievalResult]:
        """Combine multiple result lists using Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievalResult] = {}

        for results, weight in zip(result_lists, weights):
            for rank, result in enumerate(results):
                chunk_id = result.chunk.chunk_id
                rrf_score = weight / (k + rank + 1)
                scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = result

        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [
            RetrievalResult(
                chunk=chunk_map[cid].chunk,
                score=scores[cid],
                retrieval_method="hybrid"
            )
            for cid in sorted_ids if cid in chunk_map
        ]


# =============================================================================
# Evaluation
# =============================================================================

class MultimodalRAGEvaluator:
    """Evaluate multimodal RAG system quality."""

    def __init__(self, pipeline: MultimodalRAGPipeline):
        self.pipeline = pipeline

    def evaluate(self, test_cases: list[dict]) -> dict:
        """
        Evaluate on test cases.
        
        Each test case: {
            "question": str,
            "expected_answer": str,
            "expected_sources": [{"doc_id": str, "page": int, "modality": str}],
            "expected_modalities": [str]  # Which modalities should be used
        }
        """
        results = {
            "total": len(test_cases),
            "retrieval_recall": [],
            "modality_accuracy": [],
            "answer_relevance": [],
            "citation_accuracy": [],
        }

        for case in test_cases:
            # Run query
            gen_result = self.pipeline.query(case["question"])

            # Evaluate retrieval
            retrieval_recall = self._eval_retrieval_recall(
                gen_result.context_used, case.get("expected_sources", [])
            )
            results["retrieval_recall"].append(retrieval_recall)

            # Evaluate modality usage
            modality_acc = self._eval_modality_usage(
                gen_result.context_used, case.get("expected_modalities", [])
            )
            results["modality_accuracy"].append(modality_acc)

            # Evaluate answer relevance (simplified - use LLM judge in production)
            answer_rel = self._eval_answer_relevance(
                gen_result.answer, case.get("expected_answer", "")
            )
            results["answer_relevance"].append(answer_rel)

            # Evaluate citations
            citation_acc = self._eval_citations(
                gen_result.citations, case.get("expected_sources", [])
            )
            results["citation_accuracy"].append(citation_acc)

        # Aggregate
        return {
            "total_cases": results["total"],
            "avg_retrieval_recall": np.mean(results["retrieval_recall"]) if results["retrieval_recall"] else 0,
            "avg_modality_accuracy": np.mean(results["modality_accuracy"]) if results["modality_accuracy"] else 0,
            "avg_answer_relevance": np.mean(results["answer_relevance"]) if results["answer_relevance"] else 0,
            "avg_citation_accuracy": np.mean(results["citation_accuracy"]) if results["citation_accuracy"] else 0,
        }

    def _eval_retrieval_recall(self, context: Optional[MultimodalContext],
                                expected_sources: list[dict]) -> float:
        """What fraction of expected sources were retrieved?"""
        if not context or not expected_sources:
            return 0.0

        retrieved_sources = set()
        for chunk in context.all_chunks():
            retrieved_sources.add((chunk.document_id, chunk.page))

        hits = 0
        for source in expected_sources:
            if (source["doc_id"], source["page"]) in retrieved_sources:
                hits += 1

        return hits / len(expected_sources)

    def _eval_modality_usage(self, context: Optional[MultimodalContext],
                              expected_modalities: list[str]) -> float:
        """Were the right modalities used?"""
        if not context or not expected_modalities:
            return 0.0

        used_modalities = set()
        if context.text_chunks:
            used_modalities.add("text")
        if context.images:
            used_modalities.add("image")
        if context.tables:
            used_modalities.add("table")
        if context.charts:
            used_modalities.add("chart")

        expected = set(expected_modalities)
        if not expected:
            return 1.0
        return len(used_modalities & expected) / len(expected)

    def _eval_answer_relevance(self, answer: str, expected: str) -> float:
        """Simple token overlap relevance (use LLM judge in production)."""
        if not answer or not expected:
            return 0.0
        answer_tokens = set(answer.lower().split())
        expected_tokens = set(expected.lower().split())
        overlap = answer_tokens & expected_tokens
        return len(overlap) / max(len(expected_tokens), 1)

    def _eval_citations(self, citations: list[MultimodalCitation],
                        expected_sources: list[dict]) -> float:
        """Evaluate citation accuracy."""
        if not expected_sources:
            return 1.0 if not citations else 0.5
        if not citations:
            return 0.0

        hits = 0
        for citation in citations:
            for source in expected_sources:
                if (citation.document_id == source.get("doc_id") and
                    citation.page == source.get("page")):
                    hits += 1
                    break

        return min(1.0, hits / len(expected_sources))


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Initialize pipeline
    pipeline = MultimodalRAGPipeline(config={
        "text_model": "text-embedding-3-large",
        "text_dimension": 1536,
        "generation_model": "gpt-4o",
        "max_text_tokens": 4000,
        "max_images": 5,
    })

    # Ingest a document
    sample_elements = [
        {
            "type": "text",
            "content": "Annual revenue for 2024 was $5.2 billion, representing a 15% increase year-over-year.",
            "page": 1,
            "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.9, "y2": 0.25, "page": 1},
            "section_title": "Financial Summary"
        },
        {
            "type": "table",
            "content": "| Quarter | Revenue | Growth |\n|---|---|---|\n| Q1 | $1.1B | 12% |\n| Q2 | $1.3B | 16% |",
            "page": 2,
            "table_data": [
                {"Quarter": "Q1", "Revenue": "$1.1B", "Growth": "12%"},
                {"Quarter": "Q2", "Revenue": "$1.3B", "Growth": "16%"},
            ],
            "section_title": "Quarterly Breakdown"
        },
        {
            "type": "image",
            "content": "Bar chart showing quarterly revenue growth from Q1 to Q4 2024",
            "page": 3,
            "section_title": "Revenue Visualization"
        }
    ]

    pipeline.ingest_document("annual_report_2024", sample_elements)

    # Query
    result = pipeline.query("What was the revenue growth in Q2 2024?")
    print(f"Answer: {result.answer}")
    print(f"Citations: {len(result.citations)}")
    print(f"Index stats: {pipeline.index.stats()}")
