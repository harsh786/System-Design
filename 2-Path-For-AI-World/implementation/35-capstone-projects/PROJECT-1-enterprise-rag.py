"""
==============================================================================
PROJECT 1: Enterprise RAG Platform
==============================================================================
A production-grade Retrieval-Augmented Generation system demonstrating:
- Multi-format document ingestion (PDF, DOCX, HTML, Markdown, Confluence)
- Multiple chunking strategies (fixed, semantic, recursive, parent-child)
- Hybrid retrieval (dense + sparse with reciprocal rank fusion)
- Cross-encoder reranking with calibrated scores
- Citation builder with span-level source attribution
- ACL-based retrieval filtering (pre-filter approach)
- Evaluation dashboard with comprehensive metrics
- Complete API with configuration management

This is a Staff AI Architect capstone demonstrating end-to-end system design,
production concerns (auth, monitoring, cost tracking), and evaluation rigor.
==============================================================================
"""

import asyncio
import hashlib
import json
import logging
import math
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, Literal,
    Optional, Protocol, Set, Tuple, Union
)

import numpy as np

# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class EmbeddingConfig:
    model: str = "text-embedding-3-large"
    dimensions: int = 3072
    batch_size: int = 100
    max_retries: int = 3
    timeout_seconds: float = 30.0


@dataclass
class ChunkingConfig:
    strategy: Literal["fixed", "semantic", "recursive", "parent_child"] = "recursive"
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 50  # tokens
    min_chunk_size: int = 100  # tokens
    max_chunk_size: int = 1024  # tokens
    semantic_threshold: float = 0.7
    parent_chunk_size: int = 2048  # for parent-child strategy


@dataclass
class RetrievalConfig:
    top_k: int = 20
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    rerank_top_k: int = 5
    similarity_threshold: float = 0.3
    enable_reranking: bool = True
    enable_acl_filter: bool = True
    max_context_tokens: int = 4096


@dataclass
class GenerationConfig:
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 2048
    enable_citations: bool = True
    enable_streaming: bool = True


@dataclass
class SystemConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    log_level: str = "INFO"
    enable_metrics: bool = True
    cache_ttl_seconds: int = 3600
    max_concurrent_ingestions: int = 5


# ==============================================================================
# DOMAIN MODELS
# ==============================================================================

class DocumentFormat(Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "markdown"
    CONFLUENCE = "confluence"
    SLACK = "slack"
    PLAINTEXT = "plaintext"


class ChunkStrategy(Enum):
    FIXED = "fixed"
    SEMANTIC = "semantic"
    RECURSIVE = "recursive"
    PARENT_CHILD = "parent_child"


class AccessLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DocumentMetadata:
    doc_id: str
    title: str
    source: str
    format: DocumentFormat
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    access_level: AccessLevel = AccessLevel.INTERNAL
    allowed_groups: List[str] = field(default_factory=list)
    allowed_users: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    content: str
    token_count: int
    position: int  # ordinal position in document
    metadata: Dict[str, Any] = field(default_factory=dict)
    # For parent-child strategy
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)
    # Structural info
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    # Embedding (populated after encoding)
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    chunk: Chunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: Optional[float] = None
    final_score: float = 0.0


@dataclass
class Citation:
    citation_id: str
    chunk_id: str
    doc_id: str
    doc_title: str
    source: str
    text_span: str  # exact text from source
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    confidence: float = 0.0


@dataclass
class GeneratedAnswer:
    answer: str
    citations: List[Citation]
    confidence: float
    tokens_used: int
    latency_ms: float
    model: str
    retrieval_results: List[RetrievalResult]
    query: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserContext:
    user_id: str
    groups: List[str]
    access_level: AccessLevel = AccessLevel.INTERNAL
    tenant_id: Optional[str] = None


# ==============================================================================
# DOCUMENT PARSERS
# ==============================================================================

class DocumentParser(ABC):
    """Base class for document format parsers."""

    @abstractmethod
    async def parse(self, content: bytes, metadata: DocumentMetadata) -> str:
        """Parse document bytes into plain text."""
        pass

    @abstractmethod
    def supported_format(self) -> DocumentFormat:
        pass


class PDFParser(DocumentParser):
    """Parse PDF documents extracting text, tables, and structure."""

    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.PDF

    async def parse(self, content: bytes, metadata: DocumentMetadata) -> str:
        """
        Production implementation would use:
        - PyMuPDF (fitz) for text extraction
        - pdfplumber for table extraction
        - OCR fallback (Tesseract) for scanned PDFs
        - Layout analysis for structure detection
        """
        # Simulated parsing with structure detection
        text = content.decode("utf-8", errors="replace")

        # Extract structural elements
        sections = self._detect_sections(text)
        tables = self._extract_tables(text)

        # Reconstruct with structure markers
        structured_text = self._rebuild_with_structure(text, sections, tables)

        # Update metadata
        metadata.page_count = text.count("\f") + 1
        metadata.word_count = len(text.split())

        return structured_text

    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """Detect section headers based on formatting patterns."""
        sections = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Heuristic: short lines in ALL CAPS or ending with specific patterns
            if stripped and len(stripped) < 100:
                if stripped.isupper() or re.match(r"^\d+\.\s+\w", stripped):
                    sections.append({
                        "title": stripped,
                        "line_number": i,
                        "level": 1 if stripped.isupper() else 2
                    })
        return sections

    def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract tabular data from text."""
        # Simplified table detection
        tables = []
        lines = text.split("\n")
        table_start = None
        for i, line in enumerate(lines):
            if "|" in line and line.count("|") >= 2:
                if table_start is None:
                    table_start = i
            else:
                if table_start is not None:
                    tables.append({
                        "start_line": table_start,
                        "end_line": i,
                        "content": "\n".join(lines[table_start:i])
                    })
                    table_start = None
        return tables

    def _rebuild_with_structure(
        self, text: str,
        sections: List[Dict[str, Any]],
        tables: List[Dict[str, Any]]
    ) -> str:
        """Rebuild text with explicit structure markers."""
        # In production, this would create a rich structured representation
        return text


class HTMLParser(DocumentParser):
    """Parse HTML documents preserving semantic structure."""

    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.HTML

    async def parse(self, content: bytes, metadata: DocumentMetadata) -> str:
        """
        Production implementation would use:
        - BeautifulSoup for HTML parsing
        - Readability algorithm for content extraction
        - Preservation of headings, lists, code blocks
        """
        text = content.decode("utf-8", errors="replace")
        # Strip HTML tags but preserve structure
        text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n## \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n", text, flags=re.DOTALL)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        metadata.word_count = len(text.split())
        return text.strip()


class MarkdownParser(DocumentParser):
    """Parse Markdown preserving structure for intelligent chunking."""

    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.MARKDOWN

    async def parse(self, content: bytes, metadata: DocumentMetadata) -> str:
        text = content.decode("utf-8", errors="replace")
        metadata.word_count = len(text.split())
        return text


class DocxParser(DocumentParser):
    """Parse DOCX documents."""

    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.DOCX

    async def parse(self, content: bytes, metadata: DocumentMetadata) -> str:
        """
        Production: use python-docx to extract paragraphs, tables, headers.
        """
        text = content.decode("utf-8", errors="replace")
        metadata.word_count = len(text.split())
        return text


class ParserRegistry:
    """Registry of document parsers with format detection."""

    def __init__(self):
        self._parsers: Dict[DocumentFormat, DocumentParser] = {}
        # Register default parsers
        for parser_cls in [PDFParser, HTMLParser, MarkdownParser, DocxParser]:
            parser = parser_cls()
            self._parsers[parser.supported_format()] = parser

    def get_parser(self, format: DocumentFormat) -> DocumentParser:
        parser = self._parsers.get(format)
        if not parser:
            raise ValueError(f"No parser registered for format: {format}")
        return parser

    def register(self, parser: DocumentParser):
        self._parsers[parser.supported_format()] = parser


# ==============================================================================
# CHUNKING STRATEGIES
# ==============================================================================

class ChunkingStrategy(ABC):
    """Base class for document chunking strategies."""

    @abstractmethod
    def chunk(self, text: str, doc_id: str, config: ChunkingConfig) -> List[Chunk]:
        pass


class FixedSizeChunker(ChunkingStrategy):
    """Fixed-size chunking with configurable overlap."""

    def chunk(self, text: str, doc_id: str, config: ChunkingConfig) -> List[Chunk]:
        chunks = []
        # Approximate token count (4 chars per token)
        chars_per_token = 4
        chunk_chars = config.chunk_size * chars_per_token
        overlap_chars = config.chunk_overlap * chars_per_token

        start = 0
        position = 0
        while start < len(text):
            end = start + chunk_chars
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end within last 20% of chunk
                search_start = end - int(chunk_chars * 0.2)
                sentence_end = self._find_sentence_boundary(text, search_start, end)
                if sentence_end > 0:
                    end = sentence_end

            chunk_text = text[start:end].strip()
            if chunk_text and len(chunk_text) > config.min_chunk_size * chars_per_token // 2:
                token_count = len(chunk_text) // chars_per_token
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_chunk_{position}",
                    doc_id=doc_id,
                    content=chunk_text,
                    token_count=token_count,
                    position=position,
                ))
                position += 1

            start = end - overlap_chars
            if start >= len(text):
                break

        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """Find the best sentence boundary in the given range."""
        # Look for period, question mark, or exclamation followed by space/newline
        best_pos = -1
        for match in re.finditer(r'[.!?]\s', text[start:end]):
            best_pos = start + match.end()
        return best_pos


class SemanticChunker(ChunkingStrategy):
    """Chunk based on semantic similarity between consecutive sentences."""

    def chunk(self, text: str, doc_id: str, config: ChunkingConfig) -> List[Chunk]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks = []
        current_sentences = [sentences[0]]
        position = 0
        chars_per_token = 4

        for i in range(1, len(sentences)):
            current_text = " ".join(current_sentences)
            current_tokens = len(current_text) // chars_per_token

            # Check if adding next sentence exceeds max size
            next_text = " ".join(current_sentences + [sentences[i]])
            next_tokens = len(next_text) // chars_per_token

            if next_tokens > config.max_chunk_size:
                # Emit current chunk
                if current_text.strip():
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}_semantic_{position}",
                        doc_id=doc_id,
                        content=current_text.strip(),
                        token_count=current_tokens,
                        position=position,
                    ))
                    position += 1
                current_sentences = [sentences[i]]
            else:
                # Compute semantic similarity (simplified - in production use embeddings)
                similarity = self._compute_similarity(
                    current_sentences[-1], sentences[i]
                )
                if similarity < config.semantic_threshold and current_tokens >= config.min_chunk_size:
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}_semantic_{position}",
                        doc_id=doc_id,
                        content=current_text.strip(),
                        token_count=current_tokens,
                        position=position,
                    ))
                    position += 1
                    current_sentences = [sentences[i]]
                else:
                    current_sentences.append(sentences[i])

        # Final chunk
        final_text = " ".join(current_sentences).strip()
        if final_text:
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_semantic_{position}",
                doc_id=doc_id,
                content=final_text,
                token_count=len(final_text) // chars_per_token,
                position=position,
            ))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _compute_similarity(self, sent_a: str, sent_b: str) -> float:
        """
        Compute semantic similarity between sentences.
        Production: use sentence embeddings and cosine similarity.
        Simplified: use word overlap (Jaccard similarity).
        """
        words_a = set(sent_a.lower().split())
        words_b = set(sent_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)


class RecursiveChunker(ChunkingStrategy):
    """
    Recursively split text using a hierarchy of separators.
    Tries to keep semantically coherent units together.
    """

    SEPARATORS = [
        "\n\n\n",   # Major section breaks
        "\n\n",     # Paragraph breaks
        "\n",       # Line breaks
        ". ",       # Sentence breaks
        " ",        # Word breaks
    ]

    def chunk(self, text: str, doc_id: str, config: ChunkingConfig) -> List[Chunk]:
        chunks_text = self._recursive_split(text, config, 0)
        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            if chunk_text.strip():
                chars_per_token = 4
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_recursive_{i}",
                    doc_id=doc_id,
                    content=chunk_text.strip(),
                    token_count=len(chunk_text) // chars_per_token,
                    position=i,
                ))
        return chunks

    def _recursive_split(
        self, text: str, config: ChunkingConfig, separator_idx: int
    ) -> List[str]:
        chars_per_token = 4
        max_chars = config.chunk_size * chars_per_token

        if len(text) <= max_chars:
            return [text]

        if separator_idx >= len(self.SEPARATORS):
            # Force split at max size
            return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

        separator = self.SEPARATORS[separator_idx]
        parts = text.split(separator)

        chunks = []
        current_parts = []
        current_length = 0

        for part in parts:
            part_length = len(part) + len(separator)
            if current_length + part_length > max_chars and current_parts:
                chunk_text = separator.join(current_parts)
                if len(chunk_text) > max_chars:
                    # Recursively split with next separator
                    sub_chunks = self._recursive_split(
                        chunk_text, config, separator_idx + 1
                    )
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(chunk_text)
                current_parts = [part]
                current_length = part_length
            else:
                current_parts.append(part)
                current_length += part_length

        if current_parts:
            chunk_text = separator.join(current_parts)
            if len(chunk_text) > max_chars:
                sub_chunks = self._recursive_split(
                    chunk_text, config, separator_idx + 1
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(chunk_text)

        return chunks


class ParentChildChunker(ChunkingStrategy):
    """
    Create parent (large context) and child (precise retrieval) chunks.
    Retrieve on child chunks, but pass parent chunk to LLM for more context.
    """

    def chunk(self, text: str, doc_id: str, config: ChunkingConfig) -> List[Chunk]:
        chars_per_token = 4

        # Create parent chunks
        parent_chunker = FixedSizeChunker()
        parent_config = ChunkingConfig(
            chunk_size=config.parent_chunk_size,
            chunk_overlap=config.chunk_overlap * 2,
            min_chunk_size=config.chunk_size,
            max_chunk_size=config.parent_chunk_size * 2,
        )
        parent_chunks = parent_chunker.chunk(text, doc_id, parent_config)

        # Rename parent chunk IDs
        for i, parent in enumerate(parent_chunks):
            parent.chunk_id = f"{doc_id}_parent_{i}"

        # Create child chunks from each parent
        child_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            min_chunk_size=config.min_chunk_size,
            max_chunk_size=config.max_chunk_size,
        )

        all_chunks = []
        child_position = 0
        for parent in parent_chunks:
            child_chunker = FixedSizeChunker()
            children = child_chunker.chunk(parent.content, doc_id, child_config)

            # Link children to parent
            for child in children:
                child.chunk_id = f"{doc_id}_child_{child_position}"
                child.parent_chunk_id = parent.chunk_id
                child.position = child_position
                parent.child_chunk_ids.append(child.chunk_id)
                child_position += 1

            all_chunks.extend(children)
            all_chunks.append(parent)

        return all_chunks


class ChunkerFactory:
    """Factory for creating chunking strategy instances."""

    _strategies = {
        ChunkStrategy.FIXED: FixedSizeChunker,
        ChunkStrategy.SEMANTIC: SemanticChunker,
        ChunkStrategy.RECURSIVE: RecursiveChunker,
        ChunkStrategy.PARENT_CHILD: ParentChildChunker,
    }

    @classmethod
    def create(cls, strategy: Union[str, ChunkStrategy]) -> ChunkingStrategy:
        if isinstance(strategy, str):
            strategy = ChunkStrategy(strategy)
        chunker_cls = cls._strategies.get(strategy)
        if not chunker_cls:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
        return chunker_cls()


# ==============================================================================
# EMBEDDING SERVICE
# ==============================================================================

class EmbeddingService:
    """Service for generating text embeddings with batching and retry."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._cache: Dict[str, List[float]] = {}
        self._call_count = 0
        self._total_tokens = 0

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts, using cache when available."""
        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []

        # Check cache
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                texts_to_embed.append(text)
                indices_to_embed.append(i)

        # Batch embed uncached texts
        if texts_to_embed:
            for batch_start in range(0, len(texts_to_embed), self.config.batch_size):
                batch = texts_to_embed[batch_start:batch_start + self.config.batch_size]
                embeddings = await self._call_embedding_api(batch)
                for j, embedding in enumerate(embeddings):
                    idx = indices_to_embed[batch_start + j]
                    results[idx] = embedding
                    cache_key = self._cache_key(texts_to_embed[batch_start + j])
                    self._cache[cache_key] = embedding

        return results

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query text."""
        results = await self.embed_texts([query])
        return results[0]

    async def _call_embedding_api(self, texts: List[str]) -> List[List[float]]:
        """
        Call embedding API with retry logic.
        Production: uses OpenAI/Azure OpenAI API.
        Simulated: generates deterministic pseudo-embeddings.
        """
        self._call_count += 1
        self._total_tokens += sum(len(t.split()) for t in texts)

        # Simulate API call with deterministic embeddings for reproducibility
        embeddings = []
        for text in texts:
            # Generate a deterministic embedding based on text content
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            embedding = rng.randn(self.config.dimensions).tolist()
            # Normalize
            norm = math.sqrt(sum(x*x for x in embedding))
            embedding = [x / norm for x in embedding]
            embeddings.append(embedding)

        # Simulate latency
        await asyncio.sleep(0.01 * len(texts))
        return embeddings

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "api_calls": self._call_count,
            "total_tokens": self._total_tokens,
            "cache_size": len(self._cache),
        }


# ==============================================================================
# VECTOR STORE
# ==============================================================================

class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def upsert(self, chunks: List[Chunk]) -> int:
        pass

    @abstractmethod
    async def search(
        self, query_embedding: List[float], top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        pass

    @abstractmethod
    async def delete_by_doc_id(self, doc_id: str) -> int:
        pass


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store for development and testing.
    Production: replace with pgvector, Qdrant, Pinecone, or Weaviate.
    """

    def __init__(self):
        self._chunks: Dict[str, Chunk] = {}
        self._embeddings: Dict[str, np.ndarray] = {}
        self._doc_index: Dict[str, Set[str]] = defaultdict(set)
        # ACL indices
        self._group_index: Dict[str, Set[str]] = defaultdict(set)
        self._user_index: Dict[str, Set[str]] = defaultdict(set)
        self._access_level_index: Dict[AccessLevel, Set[str]] = defaultdict(set)

    async def upsert(self, chunks: List[Chunk]) -> int:
        count = 0
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            self._chunks[chunk.chunk_id] = chunk
            self._embeddings[chunk.chunk_id] = np.array(chunk.embedding)
            self._doc_index[chunk.doc_id].add(chunk.chunk_id)
            count += 1
        return count

    async def index_acl(
        self, chunk_id: str, groups: List[str],
        users: List[str], access_level: AccessLevel
    ):
        """Index ACL information for pre-filtering."""
        for group in groups:
            self._group_index[group].add(chunk_id)
        for user in users:
            self._user_index[user].add(chunk_id)
        self._access_level_index[access_level].add(chunk_id)

    async def search(
        self, query_embedding: List[float], top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        """Search with optional ACL pre-filtering."""
        query_vec = np.array(query_embedding)

        # Determine candidate set based on filters
        if filters:
            candidates = self._apply_filters(filters)
        else:
            candidates = set(self._chunks.keys())

        # Compute cosine similarities
        scores = []
        for chunk_id in candidates:
            if chunk_id not in self._embeddings:
                continue
            doc_vec = self._embeddings[chunk_id]
            similarity = float(np.dot(query_vec, doc_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-10
            ))
            scores.append((chunk_id, similarity))

        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for chunk_id, score in scores[:top_k]:
            results.append((self._chunks[chunk_id], score))

        return results

    def _apply_filters(self, filters: Dict[str, Any]) -> Set[str]:
        """Apply ACL filters to get candidate chunk IDs."""
        all_chunks = set(self._chunks.keys())

        # User filter
        user_id = filters.get("user_id")
        user_groups = filters.get("groups", [])
        access_level = filters.get("access_level", AccessLevel.INTERNAL)

        # Chunks accessible by user's groups OR directly by user
        accessible = set()

        # Public chunks are always accessible
        accessible.update(self._access_level_index.get(AccessLevel.PUBLIC, set()))

        # Group-based access
        for group in user_groups:
            accessible.update(self._group_index.get(group, set()))

        # Direct user access
        if user_id:
            accessible.update(self._user_index.get(user_id, set()))

        # Access level hierarchy
        level_order = [AccessLevel.PUBLIC, AccessLevel.INTERNAL,
                       AccessLevel.CONFIDENTIAL, AccessLevel.RESTRICTED]
        user_level_idx = level_order.index(access_level)
        for level in level_order[:user_level_idx + 1]:
            accessible.update(self._access_level_index.get(level, set()))

        return accessible & all_chunks

    async def delete_by_doc_id(self, doc_id: str) -> int:
        chunk_ids = self._doc_index.get(doc_id, set()).copy()
        for chunk_id in chunk_ids:
            self._chunks.pop(chunk_id, None)
            self._embeddings.pop(chunk_id, None)
        self._doc_index.pop(doc_id, None)
        return len(chunk_ids)


# ==============================================================================
# SPARSE INDEX (BM25)
# ==============================================================================

class BM25Index:
    """
    BM25 sparse retrieval index.
    Production: use Elasticsearch, OpenSearch, or Tantivy.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: Dict[str, List[str]] = {}  # chunk_id -> tokens
        self._doc_lengths: Dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._term_doc_freq: Dict[str, int] = defaultdict(int)
        self._inverted_index: Dict[str, Set[str]] = defaultdict(set)
        self._total_docs: int = 0

    def index(self, chunk_id: str, text: str):
        """Index a chunk for BM25 retrieval."""
        tokens = self._tokenize(text)
        self._docs[chunk_id] = tokens
        self._doc_lengths[chunk_id] = len(tokens)
        self._total_docs += 1

        # Update average doc length
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / self._total_docs

        # Update term frequencies
        seen_terms = set()
        for token in tokens:
            self._inverted_index[token].add(chunk_id)
            if token not in seen_terms:
                self._term_doc_freq[token] += 1
                seen_terms.add(token)

    def search(
        self, query: str, top_k: int = 20,
        candidate_ids: Optional[Set[str]] = None
    ) -> List[Tuple[str, float]]:
        """Search using BM25 scoring."""
        query_tokens = self._tokenize(query)
        scores: Dict[str, float] = defaultdict(float)

        for token in query_tokens:
            if token not in self._inverted_index:
                continue

            df = self._term_doc_freq[token]
            idf = math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1)

            for chunk_id in self._inverted_index[token]:
                if candidate_ids and chunk_id not in candidate_ids:
                    continue

                doc_tokens = self._docs[chunk_id]
                tf = doc_tokens.count(token)
                doc_len = self._doc_lengths[chunk_id]

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / self._avg_doc_length
                )
                scores[chunk_id] += idf * numerator / denominator

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization. Production: use proper NLP tokenizer."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove stopwords (simplified)
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'shall', 'can',
                     'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'from',
                     'it', 'this', 'that', 'these', 'those', 'and', 'or', 'but'}
        return [t for t in tokens if t not in stopwords and len(t) > 1]


# ==============================================================================
# HYBRID RETRIEVAL WITH RECIPROCAL RANK FUSION
# ==============================================================================

class HybridRetriever:
    """
    Combines dense (vector) and sparse (BM25) retrieval using
    Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        embedding_service: EmbeddingService,
        config: RetrievalConfig,
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedding_service = embedding_service
        self.config = config
        self._rrf_k = 60  # RRF constant

    async def retrieve(
        self, query: str, user_context: Optional[UserContext] = None
    ) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval:
        1. Dense retrieval via vector similarity
        2. Sparse retrieval via BM25
        3. Reciprocal Rank Fusion to combine
        4. Optional ACL filtering
        """
        # Build ACL filters
        filters = None
        if user_context and self.config.enable_acl_filter:
            filters = {
                "user_id": user_context.user_id,
                "groups": user_context.groups,
                "access_level": user_context.access_level,
            }

        # Dense retrieval
        query_embedding = await self.embedding_service.embed_query(query)
        dense_results = await self.vector_store.search(
            query_embedding, self.config.top_k, filters
        )

        # Sparse retrieval
        candidate_ids = None  # Could filter by ACL here too
        sparse_results = self.bm25_index.search(query, self.config.top_k, candidate_ids)

        # Build chunk lookup
        chunk_lookup: Dict[str, Chunk] = {}
        for chunk, score in dense_results:
            chunk_lookup[chunk.chunk_id] = chunk

        # Reciprocal Rank Fusion
        rrf_scores: Dict[str, RetrievalResult] = {}

        # Score dense results
        for rank, (chunk, score) in enumerate(dense_results):
            chunk_id = chunk.chunk_id
            if chunk_id not in rrf_scores:
                rrf_scores[chunk_id] = RetrievalResult(chunk=chunk)
            rrf_scores[chunk_id].dense_score = score
            rrf_scores[chunk_id].fused_score += (
                self.config.dense_weight / (self._rrf_k + rank + 1)
            )

        # Score sparse results
        for rank, (chunk_id, score) in enumerate(sparse_results):
            if chunk_id not in rrf_scores:
                # Need to look up the chunk - in production, fetch from store
                if chunk_id in chunk_lookup:
                    chunk = chunk_lookup[chunk_id]
                else:
                    continue  # Skip if chunk not in dense results (simplified)
                rrf_scores[chunk_id] = RetrievalResult(chunk=chunk)
            rrf_scores[chunk_id].sparse_score = score
            rrf_scores[chunk_id].fused_score += (
                self.config.sparse_weight / (self._rrf_k + rank + 1)
            )

        # Sort by fused score
        results = sorted(
            rrf_scores.values(),
            key=lambda x: x.fused_score,
            reverse=True
        )

        # Apply similarity threshold
        results = [r for r in results if r.fused_score > 0]

        return results[:self.config.top_k]


# ==============================================================================
# RERANKER
# ==============================================================================

class Reranker:
    """
    Cross-encoder reranker for improving retrieval precision.
    Production: use sentence-transformers cross-encoder or Cohere rerank API.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        self.model_name = model_name
        self._call_count = 0

    async def rerank(
        self, query: str, results: List[RetrievalResult], top_k: int = 5
    ) -> List[RetrievalResult]:
        """Rerank retrieval results using cross-encoder scoring."""
        if not results:
            return []

        self._call_count += 1

        # Score each query-document pair
        scored_results = []
        for result in results:
            score = await self._score_pair(query, result.chunk.content)
            result.rerank_score = score
            result.final_score = score
            scored_results.append(result)

        # Sort by rerank score
        scored_results.sort(key=lambda x: x.final_score, reverse=True)

        return scored_results[:top_k]

    async def _score_pair(self, query: str, document: str) -> float:
        """
        Score a query-document pair.
        Production: use actual cross-encoder model inference.
        Simulated: combine text overlap with length normalization.
        """
        # Simplified scoring based on term overlap and position
        query_terms = set(query.lower().split())
        doc_terms = set(document.lower().split())

        if not query_terms:
            return 0.0

        # Term overlap
        overlap = len(query_terms & doc_terms) / len(query_terms)

        # Position bonus: terms appearing early in doc score higher
        doc_words = document.lower().split()
        position_score = 0.0
        for term in query_terms:
            if term in doc_words:
                pos = doc_words.index(term)
                position_score += 1.0 / (1 + pos / len(doc_words))

        position_score /= max(len(query_terms), 1)

        # Combine scores
        score = 0.6 * overlap + 0.4 * position_score

        # Add small random noise for tie-breaking (deterministic)
        seed = hash(query + document) % 10000
        noise = (seed / 10000) * 0.01
        score += noise

        return min(score, 1.0)


# ==============================================================================
# CITATION BUILDER
# ==============================================================================

class CitationBuilder:
    """
    Builds span-level citations mapping generated text to source chunks.
    Uses claim extraction and source attribution.
    """

    def __init__(self):
        self._citation_count = 0

    async def build_citations(
        self,
        generated_text: str,
        retrieval_results: List[RetrievalResult],
        doc_metadata_lookup: Dict[str, DocumentMetadata],
    ) -> List[Citation]:
        """
        Build citations by:
        1. Extract claims from generated text
        2. For each claim, find best matching source span
        3. Create citation with source reference
        """
        claims = self._extract_claims(generated_text)
        citations = []

        for claim in claims:
            best_match = await self._find_best_source(claim, retrieval_results)
            if best_match:
                result, span, confidence = best_match
                doc_meta = doc_metadata_lookup.get(result.chunk.doc_id)

                self._citation_count += 1
                citation = Citation(
                    citation_id=f"cite_{self._citation_count}",
                    chunk_id=result.chunk.chunk_id,
                    doc_id=result.chunk.doc_id,
                    doc_title=doc_meta.title if doc_meta else "Unknown",
                    source=doc_meta.source if doc_meta else "Unknown",
                    text_span=span,
                    page_number=result.chunk.page_number,
                    section_title=result.chunk.section_title,
                    confidence=confidence,
                )
                citations.append(citation)

        return citations

    def _extract_claims(self, text: str) -> List[str]:
        """Extract individual claims/statements from generated text."""
        # Split by sentences as a proxy for claims
        sentences = re.split(r'(?<=[.!?])\s+', text)
        claims = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20:  # Filter trivial sentences
                claims.append(sent)
        return claims

    async def _find_best_source(
        self, claim: str, results: List[RetrievalResult]
    ) -> Optional[Tuple[RetrievalResult, str, float]]:
        """Find the best source span for a given claim."""
        best_score = 0.0
        best_result = None
        best_span = ""

        claim_words = set(claim.lower().split())

        for result in results:
            # Find the best matching span within the chunk
            sentences = re.split(r'(?<=[.!?])\s+', result.chunk.content)
            for sentence in sentences:
                sent_words = set(sentence.lower().split())
                if not sent_words:
                    continue
                # Compute overlap as attribution confidence
                overlap = len(claim_words & sent_words) / max(len(claim_words), 1)
                if overlap > best_score:
                    best_score = overlap
                    best_result = result
                    best_span = sentence

        if best_score > 0.3:  # Minimum attribution threshold
            return (best_result, best_span, best_score)
        return None

    def format_citations(self, citations: List[Citation]) -> str:
        """Format citations as references."""
        if not citations:
            return ""

        lines = ["\n\n---\n**Sources:**"]
        for i, cite in enumerate(citations, 1):
            source_info = f"[{i}] {cite.doc_title}"
            if cite.section_title:
                source_info += f" > {cite.section_title}"
            if cite.page_number:
                source_info += f" (p. {cite.page_number})"
            source_info += f" — confidence: {cite.confidence:.0%}"
            lines.append(source_info)

        return "\n".join(lines)


# ==============================================================================
# GENERATION SERVICE
# ==============================================================================

class GenerationService:
    """LLM generation service with citation-aware prompting."""

    def __init__(self, config: GenerationConfig):
        self.config = config
        self._call_count = 0
        self._total_tokens = 0

    async def generate(
        self,
        query: str,
        context_chunks: List[RetrievalResult],
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, int]:
        """Generate answer using retrieved context."""
        self._call_count += 1

        if not system_prompt:
            system_prompt = self._default_system_prompt()

        # Build context string with source markers
        context = self._build_context(context_chunks)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]

        # Call LLM (simulated)
        response = await self._call_llm(messages)
        tokens_used = len(response.split()) * 2  # Rough approximation
        self._total_tokens += tokens_used

        return response, tokens_used

    def _default_system_prompt(self) -> str:
        return """You are a helpful assistant that answers questions based on the provided context.

Rules:
1. Only answer based on the provided context. If the context doesn't contain enough information, say so.
2. Cite your sources using [Source N] notation where N corresponds to the source number in the context.
3. Be precise and concise.
4. If you're uncertain about any claim, indicate your uncertainty.
5. Never fabricate information not present in the sources."""

    def _build_context(self, results: List[RetrievalResult]) -> str:
        """Build context string with source markers for the LLM."""
        parts = []
        for i, result in enumerate(results, 1):
            section = result.chunk.section_title or "General"
            parts.append(
                f"[Source {i}] (Section: {section})\n{result.chunk.content}\n"
            )
        return "\n".join(parts)

    async def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        Call LLM API.
        Production: use OpenAI/Azure OpenAI/Anthropic API.
        Simulated: return a template response.
        """
        # Simulate API latency
        await asyncio.sleep(0.05)

        # In production, this calls the actual LLM
        # Simulated response for demonstration
        query = messages[-1]["content"].split("Question: ")[-1] if messages else ""
        return (
            f"Based on the provided sources, here is the answer to your question "
            f"about '{query[:50]}...': The information indicates that the relevant "
            f"details can be found in the referenced documents [Source 1]. "
            f"Additional context from [Source 2] supports this finding."
        )


# ==============================================================================
# EVALUATION METRICS
# ==============================================================================

@dataclass
class RetrievalMetrics:
    precision_at_k: float
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    map_score: float
    latency_ms: float


@dataclass
class RAGMetrics:
    faithfulness: float  # Is the answer grounded in sources?
    answer_relevance: float  # Does the answer address the question?
    context_relevance: float  # Are retrieved contexts relevant?
    citation_precision: float  # Are citations accurate?
    citation_recall: float  # Are all claims cited?


@dataclass
class SystemMetrics:
    total_queries: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    cache_hit_rate: float
    avg_tokens_per_query: int
    avg_cost_per_query: float
    error_rate: float


class EvaluationEngine:
    """Compute retrieval and RAG quality metrics."""

    def __init__(self):
        self._query_latencies: List[float] = []
        self._query_count = 0
        self._error_count = 0
        self._cache_hits = 0

    def compute_retrieval_metrics(
        self,
        retrieved_ids: List[str],
        relevant_ids: Set[str],
        k: int = 10,
        latency_ms: float = 0.0,
    ) -> RetrievalMetrics:
        """Compute standard retrieval metrics."""
        retrieved_at_k = retrieved_ids[:k]

        # Precision@K
        relevant_retrieved = [1 if doc_id in relevant_ids else 0
                             for doc_id in retrieved_at_k]
        precision = sum(relevant_retrieved) / k if k > 0 else 0

        # Recall@K
        recall = (sum(relevant_retrieved) / len(relevant_ids)
                  if relevant_ids else 0)

        # MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                mrr = 1.0 / (i + 1)
                break

        # NDCG@K
        ndcg = self._compute_ndcg(retrieved_at_k, relevant_ids, k)

        # MAP
        map_score = self._compute_map(retrieved_ids, relevant_ids)

        return RetrievalMetrics(
            precision_at_k=precision,
            recall_at_k=recall,
            mrr=mrr,
            ndcg_at_k=ndcg,
            map_score=map_score,
            latency_ms=latency_ms,
        )

    def _compute_ndcg(
        self, retrieved: List[str], relevant: Set[str], k: int
    ) -> float:
        """Compute Normalized Discounted Cumulative Gain."""
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k]):
            rel = 1.0 if doc_id in relevant else 0.0
            dcg += rel / math.log2(i + 2)  # +2 because log2(1) = 0

        # Ideal DCG
        ideal_rels = sorted([1.0] * min(len(relevant), k) +
                           [0.0] * max(0, k - len(relevant)), reverse=True)
        idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_rels))

        return dcg / idcg if idcg > 0 else 0.0

    def _compute_map(self, retrieved: List[str], relevant: Set[str]) -> float:
        """Compute Mean Average Precision."""
        if not relevant:
            return 0.0

        precisions = []
        relevant_count = 0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                relevant_count += 1
                precisions.append(relevant_count / (i + 1))

        return sum(precisions) / len(relevant) if precisions else 0.0

    async def compute_rag_metrics(
        self,
        query: str,
        answer: str,
        sources: List[str],
        citations: List[Citation],
    ) -> RAGMetrics:
        """
        Compute RAG quality metrics.
        Production: use LLM-as-judge for faithfulness and relevance.
        Simplified: use heuristic proxies.
        """
        # Faithfulness: overlap between answer claims and source content
        answer_words = set(answer.lower().split())
        source_words = set(" ".join(sources).lower().split())
        faithfulness = (len(answer_words & source_words) / max(len(answer_words), 1))

        # Answer relevance: overlap between answer and query
        query_words = set(query.lower().split())
        answer_relevance = (len(answer_words & query_words) / max(len(query_words), 1))

        # Context relevance: average overlap between sources and query
        context_scores = []
        for source in sources:
            src_words = set(source.lower().split())
            score = len(src_words & query_words) / max(len(query_words), 1)
            context_scores.append(score)
        context_relevance = (sum(context_scores) / len(context_scores)
                            if context_scores else 0.0)

        # Citation precision: fraction of citations that are accurate
        citation_precision = (
            sum(1 for c in citations if c.confidence > 0.5) / max(len(citations), 1)
        )

        # Citation recall: simplified as having at least one citation
        citation_recall = min(len(citations) / 3.0, 1.0)  # Expect ~3 citations

        return RAGMetrics(
            faithfulness=min(faithfulness, 1.0),
            answer_relevance=min(answer_relevance, 1.0),
            context_relevance=min(context_relevance, 1.0),
            citation_precision=citation_precision,
            citation_recall=citation_recall,
        )

    def record_query(self, latency_ms: float, is_error: bool = False, cache_hit: bool = False):
        """Record query metrics for system-level tracking."""
        self._query_count += 1
        self._query_latencies.append(latency_ms)
        if is_error:
            self._error_count += 1
        if cache_hit:
            self._cache_hits += 1

    def get_system_metrics(self) -> SystemMetrics:
        """Compute system-level metrics."""
        latencies = sorted(self._query_latencies) if self._query_latencies else [0]
        n = len(latencies)

        return SystemMetrics(
            total_queries=self._query_count,
            avg_latency_ms=sum(latencies) / max(n, 1),
            p50_latency_ms=latencies[n // 2] if n > 0 else 0,
            p95_latency_ms=latencies[int(n * 0.95)] if n > 0 else 0,
            p99_latency_ms=latencies[int(n * 0.99)] if n > 0 else 0,
            cache_hit_rate=self._cache_hits / max(self._query_count, 1),
            avg_tokens_per_query=500,  # Tracked separately in production
            avg_cost_per_query=0.02,  # Tracked separately in production
            error_rate=self._error_count / max(self._query_count, 1),
        )


# ==============================================================================
# INGESTION PIPELINE
# ==============================================================================

class IngestionPipeline:
    """
    End-to-end document ingestion pipeline:
    Parse → Chunk → Embed → Store → Index ACLs
    """

    def __init__(
        self,
        parser_registry: ParserRegistry,
        chunker: ChunkingStrategy,
        embedding_service: EmbeddingService,
        vector_store: InMemoryVectorStore,
        bm25_index: BM25Index,
        config: SystemConfig,
    ):
        self.parser_registry = parser_registry
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.config = config
        self._ingestion_count = 0
        self._doc_metadata: Dict[str, DocumentMetadata] = {}
        self.logger = logging.getLogger(__name__)

    async def ingest_document(
        self, content: bytes, metadata: DocumentMetadata
    ) -> Dict[str, Any]:
        """Ingest a single document through the full pipeline."""
        start_time = time.time()
        self._ingestion_count += 1

        # 1. Parse
        parser = self.parser_registry.get_parser(metadata.format)
        text = await parser.parse(content, metadata)
        metadata.content_hash = hashlib.sha256(content).hexdigest()

        # 2. Check for duplicates (skip if content unchanged)
        existing = self._doc_metadata.get(metadata.doc_id)
        if existing and existing.content_hash == metadata.content_hash:
            return {"status": "skipped", "reason": "content_unchanged"}

        # 3. Delete old chunks if updating
        if existing:
            await self.vector_store.delete_by_doc_id(metadata.doc_id)

        # 4. Chunk
        chunks = self.chunker.chunk(text, metadata.doc_id, self.config.chunking)

        # 5. Embed
        chunk_texts = [c.content for c in chunks]
        embeddings = await self.embedding_service.embed_texts(chunk_texts)
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        # 6. Store in vector DB
        stored_count = await self.vector_store.upsert(chunks)

        # 7. Index in BM25
        for chunk in chunks:
            self.bm25_index.index(chunk.chunk_id, chunk.content)

        # 8. Index ACLs
        for chunk in chunks:
            await self.vector_store.index_acl(
                chunk.chunk_id,
                metadata.allowed_groups,
                metadata.allowed_users,
                metadata.access_level,
            )

        # 9. Store metadata
        self._doc_metadata[metadata.doc_id] = metadata

        elapsed_ms = (time.time() - start_time) * 1000

        result = {
            "status": "success",
            "doc_id": metadata.doc_id,
            "chunks_created": len(chunks),
            "chunks_stored": stored_count,
            "ingestion_time_ms": elapsed_ms,
            "content_hash": metadata.content_hash,
        }

        self.logger.info(f"Ingested document {metadata.doc_id}: {len(chunks)} chunks in {elapsed_ms:.0f}ms")
        return result

    async def ingest_batch(
        self, documents: List[Tuple[bytes, DocumentMetadata]]
    ) -> List[Dict[str, Any]]:
        """Ingest multiple documents with concurrency control."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_ingestions)

        async def _ingest_with_semaphore(content, metadata):
            async with semaphore:
                try:
                    return await self.ingest_document(content, metadata)
                except Exception as e:
                    self.logger.error(f"Failed to ingest {metadata.doc_id}: {e}")
                    return {"status": "error", "doc_id": metadata.doc_id, "error": str(e)}

        tasks = [_ingest_with_semaphore(content, meta) for content, meta in documents]
        return await asyncio.gather(*tasks)

    def get_document_metadata(self, doc_id: str) -> Optional[DocumentMetadata]:
        return self._doc_metadata.get(doc_id)


# ==============================================================================
# RAG QUERY ENGINE
# ==============================================================================

class RAGQueryEngine:
    """
    Main query engine orchestrating retrieval, reranking, generation, and citation.
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: Reranker,
        generator: GenerationService,
        citation_builder: CitationBuilder,
        evaluation_engine: EvaluationEngine,
        doc_metadata_lookup: Dict[str, DocumentMetadata],
        config: SystemConfig,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator
        self.citation_builder = citation_builder
        self.evaluation_engine = evaluation_engine
        self.doc_metadata_lookup = doc_metadata_lookup
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Query cache
        self._cache: Dict[str, GeneratedAnswer] = {}

    async def query(
        self, query: str, user_context: Optional[UserContext] = None
    ) -> GeneratedAnswer:
        """Execute a full RAG query pipeline."""
        start_time = time.time()

        # Check cache
        cache_key = self._cache_key(query, user_context)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            latency_ms = (time.time() - start_time) * 1000
            self.evaluation_engine.record_query(latency_ms, cache_hit=True)
            return cached

        try:
            # 1. Retrieve
            retrieval_results = await self.retriever.retrieve(query, user_context)

            if not retrieval_results:
                return self._empty_answer(query, start_time)

            # 2. Rerank
            if self.config.retrieval.enable_reranking:
                retrieval_results = await self.reranker.rerank(
                    query, retrieval_results, self.config.retrieval.rerank_top_k
                )

            # 3. Generate
            answer_text, tokens_used = await self.generator.generate(
                query, retrieval_results
            )

            # 4. Build citations
            citations = []
            if self.config.generation.enable_citations:
                citations = await self.citation_builder.build_citations(
                    answer_text, retrieval_results, self.doc_metadata_lookup
                )

            # 5. Compute confidence
            confidence = self._compute_confidence(retrieval_results, citations)

            latency_ms = (time.time() - start_time) * 1000

            answer = GeneratedAnswer(
                answer=answer_text,
                citations=citations,
                confidence=confidence,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                model=self.config.generation.model,
                retrieval_results=retrieval_results,
                query=query,
            )

            # Cache result
            self._cache[cache_key] = answer

            # Record metrics
            self.evaluation_engine.record_query(latency_ms)

            return answer

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.evaluation_engine.record_query(latency_ms, is_error=True)
            self.logger.error(f"Query failed: {e}")
            raise

    def _compute_confidence(
        self, results: List[RetrievalResult], citations: List[Citation]
    ) -> float:
        """Compute confidence score based on retrieval quality and citations."""
        if not results:
            return 0.0

        # Factor 1: Top retrieval score
        top_score = results[0].final_score if results else 0.0

        # Factor 2: Score spread (high spread = clear winner = high confidence)
        if len(results) >= 2:
            score_spread = results[0].final_score - results[-1].final_score
        else:
            score_spread = 0.5

        # Factor 3: Citation confidence
        avg_citation_conf = (
            sum(c.confidence for c in citations) / max(len(citations), 1)
        )

        # Weighted combination
        confidence = (
            0.4 * min(top_score * 2, 1.0) +
            0.3 * min(score_spread * 3, 1.0) +
            0.3 * avg_citation_conf
        )

        return min(max(confidence, 0.0), 1.0)

    def _empty_answer(self, query: str, start_time: float) -> GeneratedAnswer:
        """Return an explicit 'no answer' when retrieval finds nothing."""
        latency_ms = (time.time() - start_time) * 1000
        return GeneratedAnswer(
            answer="I could not find relevant information to answer this question. "
                   "The documents I have access to don't appear to cover this topic.",
            citations=[],
            confidence=0.0,
            tokens_used=0,
            latency_ms=latency_ms,
            model=self.config.generation.model,
            retrieval_results=[],
            query=query,
        )

    def _cache_key(self, query: str, user_context: Optional[UserContext]) -> str:
        """Generate cache key from query and user context."""
        user_id = user_context.user_id if user_context else "anonymous"
        groups = ",".join(sorted(user_context.groups)) if user_context else ""
        raw = f"{query}|{user_id}|{groups}"
        return hashlib.sha256(raw.encode()).hexdigest()


# ==============================================================================
# API LAYER
# ==============================================================================

class RAGPlatformAPI:
    """
    API layer for the Enterprise RAG Platform.
    Production: implement as FastAPI/Flask endpoints.
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.parser_registry = ParserRegistry()
        self.embedding_service = EmbeddingService(config.embedding)
        self.vector_store = InMemoryVectorStore()
        self.bm25_index = BM25Index()

        chunker = ChunkerFactory.create(config.chunking.strategy)
        self.ingestion_pipeline = IngestionPipeline(
            parser_registry=self.parser_registry,
            chunker=chunker,
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            config=config,
        )

        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            embedding_service=self.embedding_service,
            config=config.retrieval,
        )

        self.reranker = Reranker()
        self.generator = GenerationService(config.generation)
        self.citation_builder = CitationBuilder()
        self.evaluation_engine = EvaluationEngine()

        self.query_engine = RAGQueryEngine(
            retriever=self.retriever,
            reranker=self.reranker,
            generator=self.generator,
            citation_builder=self.citation_builder,
            evaluation_engine=self.evaluation_engine,
            doc_metadata_lookup=self.ingestion_pipeline._doc_metadata,
            config=config,
        )

    # --- Document Management Endpoints ---

    async def ingest_document(
        self, content: bytes, metadata: DocumentMetadata
    ) -> Dict[str, Any]:
        """POST /api/v1/documents - Ingest a document."""
        return await self.ingestion_pipeline.ingest_document(content, metadata)

    async def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """DELETE /api/v1/documents/{doc_id}"""
        deleted = await self.vector_store.delete_by_doc_id(doc_id)
        return {"doc_id": doc_id, "chunks_deleted": deleted}

    async def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/documents/{doc_id}/metadata"""
        meta = self.ingestion_pipeline.get_document_metadata(doc_id)
        return asdict(meta) if meta else None

    # --- Query Endpoints ---

    async def query(
        self, query: str, user_id: str, groups: List[str],
        access_level: str = "internal"
    ) -> Dict[str, Any]:
        """POST /api/v1/query - Execute a RAG query."""
        user_context = UserContext(
            user_id=user_id,
            groups=groups,
            access_level=AccessLevel(access_level),
        )

        answer = await self.query_engine.query(query, user_context)

        return {
            "answer": answer.answer,
            "citations": [asdict(c) for c in answer.citations],
            "confidence": answer.confidence,
            "model": answer.model,
            "tokens_used": answer.tokens_used,
            "latency_ms": answer.latency_ms,
            "sources_used": len(answer.retrieval_results),
        }

    # --- Evaluation Endpoints ---

    async def get_metrics(self) -> Dict[str, Any]:
        """GET /api/v1/metrics - Get system metrics."""
        system_metrics = self.evaluation_engine.get_system_metrics()
        embedding_stats = self.embedding_service.stats

        return {
            "system": asdict(system_metrics),
            "embedding_service": embedding_stats,
            "config": {
                "chunking_strategy": self.config.chunking.strategy,
                "chunk_size": self.config.chunking.chunk_size,
                "retrieval_top_k": self.config.retrieval.top_k,
                "reranking_enabled": self.config.retrieval.enable_reranking,
                "generation_model": self.config.generation.model,
            },
        }

    async def evaluate_retrieval(
        self, query: str, expected_doc_ids: List[str]
    ) -> Dict[str, Any]:
        """POST /api/v1/evaluate/retrieval - Evaluate retrieval quality."""
        query_embedding = await self.embedding_service.embed_query(query)
        results = await self.vector_store.search(
            query_embedding, self.config.retrieval.top_k
        )
        retrieved_ids = [chunk.doc_id for chunk, _ in results]
        relevant_set = set(expected_doc_ids)

        metrics = self.evaluation_engine.compute_retrieval_metrics(
            retrieved_ids, relevant_set, k=10
        )
        return asdict(metrics)

    # --- Health & Admin ---

    async def health_check(self) -> Dict[str, Any]:
        """GET /api/v1/health"""
        return {
            "status": "healthy",
            "documents_indexed": len(self.ingestion_pipeline._doc_metadata),
            "total_queries": self.evaluation_engine._query_count,
            "uptime_seconds": time.time(),  # Simplified
        }


# ==============================================================================
# DEMONSTRATION / MAIN
# ==============================================================================

async def main():
    """Demonstrate the Enterprise RAG Platform end-to-end."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize platform
    config = SystemConfig()
    platform = RAGPlatformAPI(config)

    logger.info("=" * 60)
    logger.info("Enterprise RAG Platform - Demonstration")
    logger.info("=" * 60)

    # --- 1. Ingest sample documents ---
    documents = [
        (
            b"Machine learning is a subset of artificial intelligence. "
            b"It involves training algorithms on data to make predictions. "
            b"Deep learning uses neural networks with many layers. "
            b"Transformers revolutionized NLP with self-attention mechanisms. "
            b"Large language models like GPT-4 are trained on vast text corpora.",
            DocumentMetadata(
                doc_id="doc_001",
                title="Introduction to Machine Learning",
                source="internal_wiki",
                format=DocumentFormat.PLAINTEXT,
                author="Dr. Smith",
                access_level=AccessLevel.INTERNAL,
                allowed_groups=["engineering", "data-science"],
                tags=["ml", "ai", "introduction"],
            )
        ),
        (
            b"Retrieval-Augmented Generation combines retrieval systems with generative models. "
            b"The key components are: document ingestion, chunking, embedding, retrieval, and generation. "
            b"Hybrid retrieval uses both dense vectors and sparse BM25 for better recall. "
            b"Reranking with cross-encoders improves precision at the cost of latency. "
            b"Citation tracking ensures generated answers are grounded in source documents.",
            DocumentMetadata(
                doc_id="doc_002",
                title="RAG Architecture Guide",
                source="architecture_docs",
                format=DocumentFormat.PLAINTEXT,
                author="Jane Architect",
                access_level=AccessLevel.INTERNAL,
                allowed_groups=["engineering", "architecture"],
                tags=["rag", "architecture", "retrieval"],
            )
        ),
        (
            b"Vector databases store high-dimensional embeddings for similarity search. "
            b"Popular options include Pinecone, Qdrant, Weaviate, and pgvector. "
            b"pgvector is ideal for teams already using PostgreSQL. "
            b"Qdrant offers the best filtering performance for ACL-based retrieval. "
            b"Index types include HNSW, IVF-Flat, and PQ for different tradeoffs.",
            DocumentMetadata(
                doc_id="doc_003",
                title="Vector Database Selection Guide",
                source="tech_radar",
                format=DocumentFormat.PLAINTEXT,
                author="Platform Team",
                access_level=AccessLevel.CONFIDENTIAL,
                allowed_groups=["platform", "architecture"],
                allowed_users=["admin@company.com"],
                tags=["vector-db", "infrastructure"],
            )
        ),
    ]

    logger.info("\n--- Ingesting Documents ---")
    for content, metadata in documents:
        result = await platform.ingest_document(content, metadata)
        logger.info(f"  {metadata.title}: {result['status']} ({result.get('chunks_created', 0)} chunks)")

    # --- 2. Query with ACL ---
    logger.info("\n--- Querying (Engineering User) ---")
    result = await platform.query(
        query="How does hybrid retrieval work in RAG systems?",
        user_id="engineer@company.com",
        groups=["engineering"],
        access_level="internal",
    )
    logger.info(f"  Answer: {result['answer'][:100]}...")
    logger.info(f"  Confidence: {result['confidence']:.2f}")
    logger.info(f"  Citations: {len(result['citations'])}")
    logger.info(f"  Latency: {result['latency_ms']:.1f}ms")

    # --- 3. Query with restricted access ---
    logger.info("\n--- Querying (Restricted - Platform Team) ---")
    result2 = await platform.query(
        query="Which vector database should we use?",
        user_id="platform@company.com",
        groups=["platform", "architecture"],
        access_level="confidential",
    )
    logger.info(f"  Answer: {result2['answer'][:100]}...")
    logger.info(f"  Sources used: {result2['sources_used']}")

    # --- 4. System Metrics ---
    logger.info("\n--- System Metrics ---")
    metrics = await platform.get_metrics()
    logger.info(f"  Total queries: {metrics['system']['total_queries']}")
    logger.info(f"  Avg latency: {metrics['system']['avg_latency_ms']:.1f}ms")
    logger.info(f"  Error rate: {metrics['system']['error_rate']:.2%}")
    logger.info(f"  Embedding API calls: {metrics['embedding_service']['api_calls']}")

    # --- 5. Health Check ---
    logger.info("\n--- Health Check ---")
    health = await platform.health_check()
    logger.info(f"  Status: {health['status']}")
    logger.info(f"  Documents indexed: {health['documents_indexed']}")

    logger.info("\n" + "=" * 60)
    logger.info("Demonstration complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
