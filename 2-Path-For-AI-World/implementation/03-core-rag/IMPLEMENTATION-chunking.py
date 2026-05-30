"""
RAG Chunking Strategies — Complete Implementation

All major chunking approaches implemented with benchmarking support:
- Fixed-size chunking with overlap
- Sentence-based chunking
- Section-aware chunking (by headings)
- Parent-child chunking
- Semantic chunking (by embedding similarity)
- Table-aware chunking
- Recursive character splitting
- Chunk metadata enrichment
- Chunk quality validation
- Strategy benchmarking

Dependencies:
    pip install tiktoken numpy sentence-transformers nltk pydantic
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Domain Models ─────────────────────────────────────────────────────────────


class ChunkMetadata(BaseModel):
    """Rich metadata for each chunk."""
    chunk_id: str = ""
    document_id: str = ""
    source_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    parent_chunk_id: Optional[str] = None
    section_title: str = ""
    page_number: Optional[int] = None
    start_char: int = 0
    end_char: int = 0
    token_count: int = 0
    word_count: int = 0
    has_table: bool = False
    has_code: bool = False
    heading_hierarchy: list[str] = Field(default_factory=list)
    content_hash: str = ""


class Chunk(BaseModel):
    """A single chunk of text with metadata."""
    id: str = ""
    content: str
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.content.encode()).hexdigest()[:12]


class ChunkingConfig(BaseModel):
    """Configuration for chunking strategies."""
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 64  # tokens
    min_chunk_size: int = 50  # tokens — discard chunks smaller than this
    max_chunk_size: int = 1024  # tokens — hard limit
    tokenizer_model: str = "cl100k_base"  # tiktoken encoding


# ─── Tokenizer Utility ─────────────────────────────────────────────────────────


class TokenCounter:
    """Token counting utility using tiktoken."""

    def __init__(self, model: str = "cl100k_base"):
        import tiktoken
        self.encoding = tiktoken.get_encoding(model)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def truncate(self, text: str, max_tokens: int) -> str:
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens])


# ─── Base Chunking Strategy ───────────────────────────────────────────────────


class ChunkingStrategy(ABC):
    """Abstract base for all chunking strategies."""

    def __init__(self, config: ChunkingConfig | None = None):
        self.config = config or ChunkingConfig()
        self.token_counter = TokenCounter(self.config.tokenizer_model)

    @abstractmethod
    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        """Split text into chunks."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging/benchmarking."""
        ...

    def _enrich_metadata(self, chunks: list[Chunk], document_id: str, source_id: str) -> list[Chunk]:
        """Add standard metadata to all chunks."""
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.id = hashlib.md5(f"{document_id}:{i}:{chunk.content[:50]}".encode()).hexdigest()[:16]
            chunk.metadata.chunk_id = chunk.id
            chunk.metadata.document_id = document_id
            chunk.metadata.source_id = source_id
            chunk.metadata.chunk_index = i
            chunk.metadata.total_chunks = total
            chunk.metadata.token_count = self.token_counter.count(chunk.content)
            chunk.metadata.word_count = len(chunk.content.split())
            chunk.metadata.has_code = "```" in chunk.content or "    " in chunk.content
            chunk.metadata.content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()[:16]
        return chunks


# ─── Strategy 1: Fixed-Size Chunking ──────────────────────────────────────────


class FixedSizeChunking(ChunkingStrategy):
    """
    Split text into fixed token-size chunks with overlap.
    Simplest strategy — good baseline.
    """

    @property
    def name(self) -> str:
        return "fixed_size"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        import tiktoken
        encoding = tiktoken.get_encoding(self.config.tokenizer_model)
        tokens = encoding.encode(text)

        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + self.config.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)

            if self.token_counter.count(chunk_text) >= self.config.min_chunk_size:
                chunks.append(Chunk(content=chunk_text))

            start += self.config.chunk_size - self.config.chunk_overlap

        return self._enrich_metadata(chunks, document_id, source_id)


# ─── Strategy 2: Sentence-Based Chunking ──────────────────────────────────────


class SentenceChunking(ChunkingStrategy):
    """
    Split on sentence boundaries, accumulating sentences until chunk_size is reached.
    Respects natural language boundaries.
    """

    @property
    def name(self) -> str:
        return "sentence"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        sentences = self._split_sentences(text)
        chunks = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self.token_counter.count(sentence)

            if current_tokens + sentence_tokens > self.config.chunk_size and current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(Chunk(content=chunk_text))

                # Overlap: keep last N sentences
                overlap_sentences = []
                overlap_tokens = 0
                for s in reversed(current_sentences):
                    s_tokens = self.token_counter.count(s)
                    if overlap_tokens + s_tokens > self.config.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens

                current_sentences = overlap_sentences
                current_tokens = overlap_tokens

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            if self.token_counter.count(chunk_text) >= self.config.min_chunk_size:
                chunks.append(Chunk(content=chunk_text))

        return self._enrich_metadata(chunks, document_id, source_id)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex (NLTK-free fallback)."""
        try:
            import nltk
            nltk.data.find("tokenizers/punkt_tab")
            return nltk.sent_tokenize(text)
        except (ImportError, LookupError):
            # Fallback: regex-based sentence splitting
            pattern = r"(?<=[.!?])\s+(?=[A-Z])"
            sentences = re.split(pattern, text)
            return [s.strip() for s in sentences if s.strip()]


# ─── Strategy 3: Section-Aware Chunking ───────────────────────────────────────


class SectionAwareChunking(ChunkingStrategy):
    """
    Split by document headings/sections first, then sub-chunk if sections are too large.
    Preserves document structure.
    """

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    @property
    def name(self) -> str:
        return "section_aware"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        sections = self._split_by_headings(text)
        chunks = []
        fallback = SentenceChunking(self.config)

        for section_title, section_content in sections:
            section_tokens = self.token_counter.count(section_content)

            if section_tokens <= self.config.max_chunk_size:
                # Section fits in one chunk
                chunk = Chunk(content=section_content)
                chunk.metadata.section_title = section_title
                chunks.append(chunk)
            else:
                # Section too large — sub-chunk with sentence strategy
                sub_chunks = fallback.chunk(section_content)
                for sc in sub_chunks:
                    sc.metadata.section_title = section_title
                    chunks.append(sc)

        return self._enrich_metadata(chunks, document_id, source_id)

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """Split document into (heading, content) pairs."""
        sections = []
        matches = list(self.HEADING_PATTERN.finditer(text))

        if not matches:
            return [("", text)]

        # Content before first heading
        if matches[0].start() > 0:
            sections.append(("", text[: matches[0].start()].strip()))

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            # Include the heading in the content for context
            full_content = f"{match.group(0)}\n\n{content}"
            sections.append((heading, full_content))

        return [(title, content) for title, content in sections if content.strip()]


# ─── Strategy 4: Parent-Child Chunking ────────────────────────────────────────


class ParentChildChunking(ChunkingStrategy):
    """
    Create small child chunks for retrieval precision,
    but maintain parent chunks for context when returning results.

    Child chunks are what gets embedded and searched.
    Parent chunks are what gets returned to the LLM.
    """

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        parent_chunk_size: int = 1024,
        child_chunk_size: int = 256,
    ):
        super().__init__(config)
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size

    @property
    def name(self) -> str:
        return "parent_child"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        # First create parent chunks
        parent_config = ChunkingConfig(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=0,
            min_chunk_size=self.config.min_chunk_size,
        )
        parent_chunker = SentenceChunking(parent_config)
        parent_chunks = parent_chunker.chunk(text, document_id, source_id)

        # Then create child chunks from each parent
        child_config = ChunkingConfig(
            chunk_size=self.child_chunk_size,
            chunk_overlap=32,
            min_chunk_size=30,
        )
        child_chunker = SentenceChunking(child_config)

        all_children = []
        for parent in parent_chunks:
            parent.id = hashlib.md5(f"parent:{parent.content[:50]}".encode()).hexdigest()[:16]
            children = child_chunker.chunk(parent.content)
            for child in children:
                child.metadata.parent_chunk_id = parent.id
                all_children.append(child)

        # Return both parents and children — store separately
        # Children get embedded, parents get returned
        all_chunks = parent_chunks + all_children
        return self._enrich_metadata(all_chunks, document_id, source_id)

    def get_parents(self, chunks: list[Chunk]) -> list[Chunk]:
        """Filter to only parent chunks."""
        return [c for c in chunks if c.metadata.parent_chunk_id is None]

    def get_children(self, chunks: list[Chunk]) -> list[Chunk]:
        """Filter to only child chunks."""
        return [c for c in chunks if c.metadata.parent_chunk_id is not None]


# ─── Strategy 5: Semantic Chunking ────────────────────────────────────────────


class SemanticChunking(ChunkingStrategy):
    """
    Split text based on semantic similarity between consecutive segments.
    When similarity drops significantly, insert a chunk boundary.

    This produces chunks that are semantically coherent.
    """

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        similarity_threshold: float = 0.5,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        super().__init__(config)
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model
        self._model = None

    @property
    def name(self) -> str:
        return "semantic"

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.embedding_model)
        return self._model

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        # Split into sentences first
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return self._enrich_metadata([Chunk(content=text)], document_id, source_id)

        # Embed all sentences
        model = self._get_model()
        embeddings = model.encode(sentences)

        # Compute cosine similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i + 1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1])
            )
            similarities.append(sim)

        # Find split points where similarity drops below threshold
        # Use a percentile-based threshold for adaptability
        if similarities:
            adaptive_threshold = np.percentile(similarities, 25)  # Bottom quartile
            threshold = min(self.similarity_threshold, adaptive_threshold)
        else:
            threshold = self.similarity_threshold

        chunks = []
        current_sentences = [sentences[0]]

        for i, sim in enumerate(similarities):
            if sim < threshold and self.token_counter.count(" ".join(current_sentences)) >= self.config.min_chunk_size:
                chunks.append(Chunk(content=" ".join(current_sentences)))
                current_sentences = []
            current_sentences.append(sentences[i + 1])

        # Last chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            if self.token_counter.count(chunk_text) >= self.config.min_chunk_size:
                chunks.append(Chunk(content=chunk_text))
            elif chunks:
                # Merge with previous if too small
                chunks[-1].content += " " + chunk_text

        # Post-process: split any chunks that are too large
        final_chunks = []
        for chunk in chunks:
            if self.token_counter.count(chunk.content) > self.config.max_chunk_size:
                sub_chunker = SentenceChunking(self.config)
                final_chunks.extend(sub_chunker.chunk(chunk.content))
            else:
                final_chunks.append(chunk)

        return self._enrich_metadata(final_chunks, document_id, source_id)

    def _split_sentences(self, text: str) -> list[str]:
        pattern = r"(?<=[.!?])\s+(?=[A-Z])"
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]


# ─── Strategy 6: Table-Aware Chunking ─────────────────────────────────────────


class TableAwareChunking(ChunkingStrategy):
    """
    Detects tables in text and keeps them as atomic chunks.
    Non-table text is chunked with sentence strategy.
    """

    TABLE_PATTERN = re.compile(
        r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)",
        re.MULTILINE,
    )

    @property
    def name(self) -> str:
        return "table_aware"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        # Find all tables
        table_matches = list(self.TABLE_PATTERN.finditer(text))

        if not table_matches:
            # No tables — use sentence chunking
            fallback = SentenceChunking(self.config)
            return fallback.chunk(text, document_id, source_id)

        chunks = []
        fallback = SentenceChunking(self.config)
        last_end = 0

        for match in table_matches:
            # Chunk text before the table
            before_text = text[last_end:match.start()].strip()
            if before_text:
                text_chunks = fallback.chunk(before_text)
                chunks.extend(text_chunks)

            # Table as its own chunk
            table_chunk = Chunk(content=match.group(0))
            table_chunk.metadata.has_table = True
            chunks.append(table_chunk)

            last_end = match.end()

        # Remaining text after last table
        remaining = text[last_end:].strip()
        if remaining:
            text_chunks = fallback.chunk(remaining)
            chunks.extend(text_chunks)

        return self._enrich_metadata(chunks, document_id, source_id)


# ─── Strategy 7: Recursive Character Splitting ────────────────────────────────


class RecursiveCharacterSplitting(ChunkingStrategy):
    """
    LangChain-style recursive splitting: try to split on larger separators first,
    falling back to smaller ones if chunks are still too large.

    Separator hierarchy: \\n\\n → \\n → . → ' ' → ''
    """

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        separators: list[str] | None = None,
    ):
        super().__init__(config)
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    @property
    def name(self) -> str:
        return "recursive_character"

    def chunk(self, text: str, document_id: str = "", source_id: str = "") -> list[Chunk]:
        raw_chunks = self._recursive_split(text, self.separators)
        chunks = [Chunk(content=c) for c in raw_chunks if self.token_counter.count(c) >= self.config.min_chunk_size]
        return self._enrich_metadata(chunks, document_id, source_id)

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if not text:
            return []

        token_count = self.token_counter.count(text)
        if token_count <= self.config.chunk_size:
            return [text]

        if not separators:
            # Last resort: hard truncate
            return [self.token_counter.truncate(text, self.config.chunk_size)]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            # Character-level split
            parts = list(text)
        else:
            parts = text.split(separator)

        chunks = []
        current_parts = []
        current_tokens = 0

        for part in parts:
            part_with_sep = part + separator if separator else part
            part_tokens = self.token_counter.count(part_with_sep)

            if current_tokens + part_tokens > self.config.chunk_size and current_parts:
                merged = separator.join(current_parts) if separator else "".join(current_parts)
                # Recursively split if still too large
                if self.token_counter.count(merged) > self.config.chunk_size:
                    chunks.extend(self._recursive_split(merged, remaining_separators))
                else:
                    chunks.append(merged)

                # Overlap
                overlap_parts = []
                overlap_tokens = 0
                for p in reversed(current_parts):
                    p_tokens = self.token_counter.count(p)
                    if overlap_tokens + p_tokens > self.config.chunk_overlap:
                        break
                    overlap_parts.insert(0, p)
                    overlap_tokens += p_tokens
                current_parts = overlap_parts
                current_tokens = overlap_tokens

            current_parts.append(part)
            current_tokens += part_tokens

        if current_parts:
            merged = separator.join(current_parts) if separator else "".join(current_parts)
            if self.token_counter.count(merged) > self.config.chunk_size:
                chunks.extend(self._recursive_split(merged, remaining_separators))
            else:
                chunks.append(merged)

        return chunks


# ─── Chunk Quality Validator ──────────────────────────────────────────────────


class ChunkQualityValidator:
    """
    Validate chunk quality with configurable rules.
    Flags or filters chunks that don't meet quality criteria.
    """

    def __init__(
        self,
        min_tokens: int = 30,
        max_tokens: int = 1500,
        min_alpha_ratio: float = 0.5,  # At least 50% alphabetic characters
        max_repetition_ratio: float = 0.3,  # No more than 30% repeated lines
    ):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.min_alpha_ratio = min_alpha_ratio
        self.max_repetition_ratio = max_repetition_ratio
        self.token_counter = TokenCounter()

    def validate(self, chunk: Chunk) -> tuple[bool, list[str]]:
        """Returns (is_valid, list_of_issues)."""
        issues = []
        content = chunk.content

        # Token count check
        token_count = self.token_counter.count(content)
        if token_count < self.min_tokens:
            issues.append(f"Too short: {token_count} tokens (min: {self.min_tokens})")
        if token_count > self.max_tokens:
            issues.append(f"Too long: {token_count} tokens (max: {self.max_tokens})")

        # Alpha ratio check (catches chunks that are mostly numbers/symbols)
        alpha_chars = sum(1 for c in content if c.isalpha())
        total_chars = len(content.replace(" ", "").replace("\n", ""))
        if total_chars > 0:
            alpha_ratio = alpha_chars / total_chars
            if alpha_ratio < self.min_alpha_ratio:
                issues.append(f"Low alpha ratio: {alpha_ratio:.2f} (min: {self.min_alpha_ratio})")

        # Repetition check
        lines = content.split("\n")
        if len(lines) > 3:
            unique_lines = set(lines)
            repetition_ratio = 1 - (len(unique_lines) / len(lines))
            if repetition_ratio > self.max_repetition_ratio:
                issues.append(f"High repetition: {repetition_ratio:.2f}")

        # Empty content check
        if not content.strip():
            issues.append("Empty content")

        is_valid = len(issues) == 0
        return is_valid, issues

    def filter_valid(self, chunks: list[Chunk]) -> list[Chunk]:
        """Return only valid chunks, logging issues for filtered ones."""
        valid_chunks = []
        for chunk in chunks:
            is_valid, issues = self.validate(chunk)
            if is_valid:
                valid_chunks.append(chunk)
            else:
                logger.debug(f"Filtered chunk {chunk.id}: {issues}")
        logger.info(f"Quality filter: {len(valid_chunks)}/{len(chunks)} chunks passed")
        return valid_chunks


# ─── Chunking Benchmark ──────────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    strategy_name: str
    num_chunks: int
    avg_tokens: float
    min_tokens: int
    max_tokens: int
    std_tokens: float
    processing_time_ms: float
    quality_pass_rate: float


class ChunkingBenchmark:
    """
    Benchmark different chunking strategies on the same text.
    Helps choose the best strategy for your data.
    """

    def __init__(self):
        self.token_counter = TokenCounter()
        self.validator = ChunkQualityValidator()

    def benchmark(self, text: str, strategies: list[ChunkingStrategy]) -> list[BenchmarkResult]:
        """Run all strategies on the same text and compare."""
        results = []

        for strategy in strategies:
            start = time.perf_counter()
            chunks = strategy.chunk(text, document_id="benchmark")
            elapsed_ms = (time.perf_counter() - start) * 1000

            token_counts = [self.token_counter.count(c.content) for c in chunks]

            # Quality check
            valid_count = sum(1 for c in chunks if self.validator.validate(c)[0])
            pass_rate = valid_count / len(chunks) if chunks else 0

            result = BenchmarkResult(
                strategy_name=strategy.name,
                num_chunks=len(chunks),
                avg_tokens=np.mean(token_counts) if token_counts else 0,
                min_tokens=min(token_counts) if token_counts else 0,
                max_tokens=max(token_counts) if token_counts else 0,
                std_tokens=np.std(token_counts) if token_counts else 0,
                processing_time_ms=elapsed_ms,
                quality_pass_rate=pass_rate,
            )
            results.append(result)

        return results

    def print_results(self, results: list[BenchmarkResult]) -> None:
        """Pretty-print benchmark comparison."""
        print(f"\n{'Strategy':<25} {'Chunks':<8} {'Avg Tok':<10} {'Min':<6} {'Max':<6} {'Std':<8} {'Time(ms)':<10} {'Quality':<8}")
        print("-" * 90)
        for r in results:
            print(
                f"{r.strategy_name:<25} {r.num_chunks:<8} {r.avg_tokens:<10.1f} "
                f"{r.min_tokens:<6} {r.max_tokens:<6} {r.std_tokens:<8.1f} "
                f"{r.processing_time_ms:<10.1f} {r.quality_pass_rate:<8.1%}"
            )


# ─── Convenience: Strategy Factory ───────────────────────────────────────────


class ChunkingStrategyFactory:
    """Factory to create chunking strategies by name."""

    STRATEGIES = {
        "fixed_size": FixedSizeChunking,
        "sentence": SentenceChunking,
        "section_aware": SectionAwareChunking,
        "parent_child": ParentChildChunking,
        "semantic": SemanticChunking,
        "table_aware": TableAwareChunking,
        "recursive_character": RecursiveCharacterSplitting,
    }

    @classmethod
    def create(cls, name: str, config: ChunkingConfig | None = None, **kwargs) -> ChunkingStrategy:
        if name not in cls.STRATEGIES:
            raise ValueError(f"Unknown strategy: {name}. Available: {list(cls.STRATEGIES.keys())}")
        return cls.STRATEGIES[name](config=config, **kwargs)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls.STRATEGIES.keys())


# ─── Usage Example ─────────────────────────────────────────────────────────────


def main():
    """Demonstrate chunking strategies and benchmarking."""

    sample_text = """
# Introduction to RAG

Retrieval-Augmented Generation (RAG) is an AI framework that enhances Large Language Model outputs by grounding them in external knowledge sources. This approach addresses key limitations of LLMs including knowledge cutoff dates, hallucination, and lack of access to private data.

## How RAG Works

The RAG pipeline consists of three main phases: indexing, retrieval, and generation. During indexing, documents are processed, chunked, and embedded into a vector store. At query time, relevant chunks are retrieved and provided as context to the LLM.

### Indexing Phase

Documents are first parsed from their source format (PDF, HTML, etc.) into plain text. The text is then split into smaller chunks using various strategies. Each chunk is embedded using a model like text-embedding-3-large and stored in a vector database.

| Strategy | Best For | Chunk Size |
|----------|----------|------------|
| Fixed | Simple docs | 512 tokens |
| Sentence | Prose | Variable |
| Semantic | Technical | Variable |

### Retrieval Phase

When a user asks a question, the query is embedded using the same model. A similarity search finds the most relevant chunks. These chunks are then reranked for precision before being passed to the LLM.

### Generation Phase

The LLM receives the user's question along with the retrieved context. It generates an answer grounded in the provided information, including citations to source documents.

## Best Practices

1. Start with hybrid retrieval (dense + sparse)
2. Always add reranking in production
3. Benchmark your chunking strategy
4. Build evaluation before optimizing
5. Monitor retrieval quality metrics continuously
"""

    config = ChunkingConfig(chunk_size=256, chunk_overlap=32, min_chunk_size=30)

    strategies = [
        FixedSizeChunking(config),
        SentenceChunking(config),
        SectionAwareChunking(config),
        RecursiveCharacterSplitting(config),
        TableAwareChunking(config),
    ]

    # Run benchmark
    benchmark = ChunkingBenchmark()
    results = benchmark.benchmark(sample_text, strategies)
    benchmark.print_results(results)

    # Show chunks from one strategy
    print("\n\n--- Section-Aware Chunks ---")
    section_chunks = SectionAwareChunking(config).chunk(sample_text, document_id="demo")
    for chunk in section_chunks:
        print(f"\n[Chunk {chunk.metadata.chunk_index}] section='{chunk.metadata.section_title}' tokens={chunk.metadata.token_count}")
        print(chunk.content[:100] + "...")


if __name__ == "__main__":
    main()
