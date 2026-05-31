"""
Multi-Modal RAG Pipeline Simulator
===================================
Demonstrates how a production multi-modal RAG system processes documents
containing text, tables, images, and charts - then retrieves across modalities.

Run: python3 main.py
No dependencies required (standard library only).
"""

import hashlib
import json
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# Domain Models
# =============================================================================

class ContentType(Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    HEADING = "heading"


@dataclass
class DocumentRegion:
    """A region within a document page identified by layout analysis."""
    content_type: ContentType
    content: str
    page: int
    bbox: tuple  # (x1, y1, x2, y2) normalized coordinates
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """A processed chunk ready for indexing."""
    chunk_id: str
    doc_id: str
    content_type: ContentType
    text_content: str
    embedding: list  # simulated vector
    metadata: dict = field(default_factory=dict)


@dataclass
class Document:
    """A simulated multi-modal document."""
    doc_id: str
    title: str
    pages: int
    regions: list = field(default_factory=list)


# =============================================================================
# Simulated Embedding Models
# =============================================================================

class SimulatedEmbedder:
    """Simulates embedding generation with deterministic pseudo-vectors."""

    def __init__(self, dim: int = 64, model_name: str = "text-embedding"):
        self.dim = dim
        self.model_name = model_name

    def embed(self, text: str) -> list:
        """Generate a deterministic pseudo-embedding from text."""
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dim)]
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec]


class SimulatedCLIP:
    """Simulates CLIP-like cross-modal embeddings."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed_text(self, text: str) -> list:
        """Embed text into shared space."""
        seed = int(hashlib.md5(f"clip_text:{text}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec]

    def embed_image(self, image_description: str) -> list:
        """Embed image (via description) into shared space - simulates visual encoding."""
        # In reality, this would process raw pixels
        # Simulate by using description with different hash prefix for partial alignment
        keywords = set(image_description.lower().split())
        seed = int(hashlib.md5(f"clip_img:{sorted(keywords)}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec]


# =============================================================================
# Document Understanding Pipeline
# =============================================================================

class LayoutAnalyzer:
    """Simulates document layout analysis (LayoutLMv3-like)."""

    def analyze(self, doc: Document) -> list:
        """Identify regions and their types in the document."""
        print(f"  [Layout Analysis] Analyzing {doc.pages} pages...")
        regions = []
        for region in doc.regions:
            # Simulate classification confidence
            confidence = random.uniform(0.85, 0.99)
            region.metadata["layout_confidence"] = confidence
            regions.append(region)
            print(f"    Page {region.page}: {region.content_type.value} "
                  f"(confidence: {confidence:.2f}) bbox={region.bbox}")
        return regions


class OCREngine:
    """Simulates OCR processing for scanned content."""

    def process(self, region: DocumentRegion) -> str:
        """Extract text from image-based region."""
        # Simulate OCR with potential errors
        text = region.content
        ocr_confidence = random.uniform(0.80, 0.98)
        region.metadata["ocr_confidence"] = ocr_confidence
        print(f"    [OCR] Extracted text (confidence: {ocr_confidence:.2f}): "
              f"{text[:60]}...")
        return text


class TableExtractor:
    """Simulates table structure extraction."""

    def extract(self, region: DocumentRegion) -> dict:
        """Extract structured table data."""
        # Parse simulated table content
        lines = region.content.strip().split("\n")
        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        rows = []
        for line in lines[1:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells and not all(c.startswith("-") for c in cells):
                rows.append(cells)

        result = {"headers": headers, "rows": rows, "num_cells": len(headers) * len(rows)}
        accuracy = random.uniform(0.88, 0.98)
        region.metadata["table_extraction_accuracy"] = accuracy
        print(f"    [Table Extraction] {len(headers)} columns × {len(rows)} rows "
              f"(accuracy: {accuracy:.2f})")
        return result


class ImageCaptioner:
    """Simulates vision model captioning."""

    def caption(self, region: DocumentRegion) -> str:
        """Generate description for image/chart content."""
        # In production: send to GPT-4V / Claude Vision
        description = region.metadata.get("description", region.content)
        processing_time = random.uniform(0.5, 2.0)
        print(f"    [Vision Model] Generated caption ({processing_time:.1f}s): "
              f"{description[:80]}...")
        return description


# =============================================================================
# Chunking Strategy
# =============================================================================

class LayoutAwareChunker:
    """Chunks documents respecting layout boundaries."""

    def __init__(self, max_chunk_size: int = 500):
        self.max_chunk_size = max_chunk_size

    def chunk(self, doc: Document, regions: list) -> list:
        """Create chunks that respect content boundaries."""
        print(f"\n  [Chunking] Layout-aware chunking (max {self.max_chunk_size} chars)...")
        chunks = []

        for region in regions:
            if region.content_type == ContentType.TABLE:
                # Tables are ALWAYS kept as atomic units
                chunk = Chunk(
                    chunk_id=f"{doc.doc_id}_table_p{region.page}",
                    doc_id=doc.doc_id,
                    content_type=ContentType.TABLE,
                    text_content=region.content,
                    embedding=[],
                    metadata={"page": region.page, "atomic": True, **region.metadata}
                )
                chunks.append(chunk)
                print(f"    Table chunk (atomic, page {region.page}): {len(region.content)} chars")

            elif region.content_type in (ContentType.IMAGE, ContentType.CHART):
                # Images/charts stored with their captions
                chunk = Chunk(
                    chunk_id=f"{doc.doc_id}_visual_p{region.page}",
                    doc_id=doc.doc_id,
                    content_type=region.content_type,
                    text_content=region.metadata.get("caption", region.content),
                    embedding=[],
                    metadata={"page": region.page, "visual": True, **region.metadata}
                )
                chunks.append(chunk)
                print(f"    Visual chunk (page {region.page}): {region.content_type.value}")

            else:
                # Text is split respecting paragraph boundaries
                text = region.content
                if len(text) <= self.max_chunk_size:
                    chunk = Chunk(
                        chunk_id=f"{doc.doc_id}_text_p{region.page}_{len(chunks)}",
                        doc_id=doc.doc_id,
                        content_type=ContentType.TEXT,
                        text_content=text,
                        embedding=[],
                        metadata={"page": region.page, **region.metadata}
                    )
                    chunks.append(chunk)
                else:
                    # Split at paragraph boundaries
                    parts = text.split(". ")
                    current = ""
                    for part in parts:
                        if len(current) + len(part) > self.max_chunk_size:
                            if current:
                                chunk = Chunk(
                                    chunk_id=f"{doc.doc_id}_text_p{region.page}_{len(chunks)}",
                                    doc_id=doc.doc_id,
                                    content_type=ContentType.TEXT,
                                    text_content=current.strip(),
                                    embedding=[],
                                    metadata={"page": region.page, **region.metadata}
                                )
                                chunks.append(chunk)
                            current = part + ". "
                        else:
                            current += part + ". "
                    if current.strip():
                        chunk = Chunk(
                            chunk_id=f"{doc.doc_id}_text_p{region.page}_{len(chunks)}",
                            doc_id=doc.doc_id,
                            content_type=ContentType.TEXT,
                            text_content=current.strip(),
                            embedding=[],
                            metadata={"page": region.page, **region.metadata}
                        )
                        chunks.append(chunk)
                print(f"    Text chunks from page {region.page}: "
                      f"{sum(1 for c in chunks if c.metadata.get('page') == region.page and c.content_type == ContentType.TEXT)}")

        return chunks


# =============================================================================
# Multi-Modal Index
# =============================================================================

class MultiModalIndex:
    """Simulates separate indexes for different modalities."""

    def __init__(self):
        self.text_embedder = SimulatedEmbedder(dim=64, model_name="text-embedding-3-large")
        self.clip = SimulatedCLIP(dim=64)
        self.text_index: list = []
        self.visual_index: list = []
        self.table_index: list = []

    def index_chunk(self, chunk: Chunk):
        """Index a chunk in the appropriate modality-specific index."""
        if chunk.content_type == ContentType.TEXT or chunk.content_type == ContentType.HEADING:
            chunk.embedding = self.text_embedder.embed(chunk.text_content)
            self.text_index.append(chunk)
        elif chunk.content_type in (ContentType.IMAGE, ContentType.CHART):
            # Dual index: CLIP embedding + text description embedding
            chunk.embedding = self.clip.embed_image(chunk.text_content)
            chunk.metadata["text_embedding"] = self.text_embedder.embed(chunk.text_content)
            self.visual_index.append(chunk)
        elif chunk.content_type == ContentType.TABLE:
            chunk.embedding = self.text_embedder.embed(chunk.text_content)
            self.table_index.append(chunk)

    def search(self, query: str, top_k: int = 3) -> list:
        """Cross-modal search across all indexes."""
        text_query_emb = self.text_embedder.embed(query)
        clip_query_emb = self.clip.embed_text(query)

        results = []

        # Search text index
        for chunk in self.text_index:
            score = self._cosine_sim(text_query_emb, chunk.embedding)
            results.append((chunk, score, "text_index"))

        # Search visual index (use CLIP embedding)
        for chunk in self.visual_index:
            clip_score = self._cosine_sim(clip_query_emb, chunk.embedding)
            text_score = self._cosine_sim(text_query_emb, chunk.metadata.get("text_embedding", []))
            # Fuse scores
            score = 0.6 * clip_score + 0.4 * text_score
            results.append((chunk, score, "visual_index"))

        # Search table index
        for chunk in self.table_index:
            score = self._cosine_sim(text_query_emb, chunk.embedding)
            results.append((chunk, score, "table_index"))

        # Sort by score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _cosine_sim(a: list, b: list) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# =============================================================================
# Document Creation (Simulated)
# =============================================================================

def create_sample_documents() -> list:
    """Create realistic simulated documents with mixed content."""
    docs = []

    # Document 1: Financial Report
    doc1 = Document(doc_id="fin_report_2024", title="Q3 2024 Financial Report", pages=5)
    doc1.regions = [
        DocumentRegion(ContentType.HEADING, "Q3 2024 Financial Results", page=1, bbox=(0.1, 0.05, 0.9, 0.12)),
        DocumentRegion(ContentType.TEXT,
                       "Revenue grew 23% year-over-year to $4.2 billion in Q3 2024, driven by strong cloud "
                       "adoption and enterprise expansion. Operating margins improved to 28%, up from 24% in "
                       "the prior year quarter. Customer acquisition costs decreased by 15% while retention "
                       "rates reached an all-time high of 97%.",
                       page=1, bbox=(0.1, 0.15, 0.9, 0.45)),
        DocumentRegion(ContentType.TABLE,
                       "Metric | Q3 2024 | Q3 2023 | Change\n"
                       "Revenue | $4.2B | $3.4B | +23%\n"
                       "Operating Margin | 28% | 24% | +4pp\n"
                       "Net Income | $890M | $612M | +45%\n"
                       "Free Cash Flow | $1.1B | $780M | +41%",
                       page=2, bbox=(0.1, 0.1, 0.9, 0.45)),
        DocumentRegion(ContentType.CHART,
                       "Bar chart showing quarterly revenue from Q1 2023 to Q3 2024 with steady upward trend",
                       page=2, bbox=(0.1, 0.5, 0.9, 0.9),
                       metadata={"description": "Revenue bar chart showing growth from $2.8B to $4.2B over 7 quarters",
                                 "chart_type": "bar", "data_points": 7}),
        DocumentRegion(ContentType.IMAGE,
                       "Geographic revenue distribution map showing North America 55%, Europe 28%, Asia 17%",
                       page=3, bbox=(0.1, 0.1, 0.9, 0.6),
                       metadata={"description": "World map with revenue distribution: NA 55%, EU 28%, Asia 17%",
                                 "image_type": "infographic"}),
    ]
    docs.append(doc1)

    # Document 2: Technical Architecture Document
    doc2 = Document(doc_id="arch_doc_v2", title="Platform Architecture v2.0", pages=4)
    doc2.regions = [
        DocumentRegion(ContentType.HEADING, "Microservices Architecture Overview", page=1, bbox=(0.1, 0.05, 0.9, 0.1)),
        DocumentRegion(ContentType.TEXT,
                       "The platform uses an event-driven microservices architecture with Kafka as the "
                       "central event backbone. Services communicate asynchronously through events, enabling "
                       "independent scaling and deployment. The system handles 50,000 requests per second "
                       "at peak with p99 latency under 200ms.",
                       page=1, bbox=(0.1, 0.12, 0.9, 0.4)),
        DocumentRegion(ContentType.IMAGE,
                       "Architecture diagram showing API Gateway, Auth Service, Order Service, Payment Service, "
                       "Notification Service all connected through Kafka event bus with Redis cache layer",
                       page=1, bbox=(0.1, 0.45, 0.9, 0.95),
                       metadata={"description": "Microservices architecture diagram with 5 services connected via Kafka",
                                 "image_type": "architecture_diagram"}),
        DocumentRegion(ContentType.TABLE,
                       "Service | Language | Instances | RPS | p99 Latency\n"
                       "API Gateway | Go | 12 | 50000 | 15ms\n"
                       "Order Service | Java | 8 | 12000 | 85ms\n"
                       "Payment Service | Java | 6 | 8000 | 120ms\n"
                       "Auth Service | Rust | 4 | 30000 | 5ms\n"
                       "Notification | Python | 10 | 20000 | 45ms",
                       page=2, bbox=(0.1, 0.1, 0.9, 0.5)),
    ]
    docs.append(doc2)

    # Document 3: Medical Research Paper
    doc3 = Document(doc_id="med_paper_2024", title="AI-Assisted Radiology Screening", pages=3)
    doc3.regions = [
        DocumentRegion(ContentType.TEXT,
                       "Our study demonstrates that AI-assisted screening reduces radiologist reading time "
                       "by 40% while maintaining diagnostic accuracy above 95%. The model was trained on "
                       "1.2 million chest X-rays and validated on a held-out set of 50,000 cases across "
                       "12 hospitals. False negative rate was 0.3%, significantly below the 1.2% baseline.",
                       page=1, bbox=(0.1, 0.2, 0.9, 0.5)),
        DocumentRegion(ContentType.CHART,
                       "ROC curve comparing AI model (AUC 0.97) vs radiologist alone (AUC 0.92) vs combined (AUC 0.99)",
                       page=2, bbox=(0.1, 0.1, 0.5, 0.5),
                       metadata={"description": "ROC curve showing AI achieves 0.97 AUC, human 0.92, combined 0.99",
                                 "chart_type": "line", "data_points": 3}),
        DocumentRegion(ContentType.IMAGE,
                       "Sample chest X-ray with AI-highlighted regions showing potential nodule in right lower lobe",
                       page=2, bbox=(0.5, 0.1, 0.9, 0.5),
                       metadata={"description": "Chest X-ray with AI overlay highlighting suspicious nodule region",
                                 "image_type": "medical_imaging"}),
    ]
    docs.append(doc3)

    return docs


# =============================================================================
# Main Pipeline Execution
# =============================================================================

def run_pipeline():
    """Execute the full multi-modal RAG pipeline."""
    print("=" * 70)
    print("MULTI-MODAL RAG PIPELINE SIMULATOR")
    print("=" * 70)

    # Initialize components
    layout_analyzer = LayoutAnalyzer()
    ocr_engine = OCREngine()
    table_extractor = TableExtractor()
    image_captioner = ImageCaptioner()
    chunker = LayoutAwareChunker(max_chunk_size=400)
    index = MultiModalIndex()

    # Create documents
    documents = create_sample_documents()
    print(f"\nLoaded {len(documents)} documents for processing\n")

    all_chunks = []

    # Process each document
    for doc in documents:
        print(f"\n{'─' * 60}")
        print(f"Processing: {doc.title} ({doc.pages} pages)")
        print(f"{'─' * 60}")

        # Stage 1: Layout Analysis
        print("\n[Stage 1] Layout Analysis")
        regions = layout_analyzer.analyze(doc)

        # Stage 2: Content-specific processing
        print("\n[Stage 2] Content Processing")
        for region in regions:
            if region.content_type == ContentType.TABLE:
                table_data = table_extractor.extract(region)
                region.metadata["structured_data"] = table_data
            elif region.content_type in (ContentType.IMAGE, ContentType.CHART):
                caption = image_captioner.caption(region)
                region.metadata["caption"] = caption
            elif region.content_type == ContentType.TEXT:
                # Check if OCR needed (simulate: 20% of text regions are scanned)
                if random.random() < 0.2:
                    ocr_engine.process(region)

        # Stage 3: Layout-aware chunking
        print("\n[Stage 3] Chunking")
        chunks = chunker.chunk(doc, regions)
        all_chunks.extend(chunks)

        # Stage 4: Indexing
        print(f"\n[Stage 4] Indexing {len(chunks)} chunks")
        for chunk in chunks:
            index.index_chunk(chunk)

    # Summary
    print(f"\n\n{'=' * 70}")
    print("INDEXING COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Total chunks indexed: {len(all_chunks)}")
    print(f"  Text index:   {len(index.text_index)} chunks")
    print(f"  Visual index: {len(index.visual_index)} chunks")
    print(f"  Table index:  {len(index.table_index)} chunks")

    # =========================================================================
    # Cross-Modal Retrieval Demo
    # =========================================================================
    print(f"\n\n{'=' * 70}")
    print("CROSS-MODAL RETRIEVAL DEMO")
    print(f"{'=' * 70}")

    queries = [
        "What was the revenue growth in Q3 2024?",
        "Show me the system architecture diagram",
        "What are the service latency numbers?",
        "How does AI compare to radiologists in accuracy?",
        "Geographic distribution of revenue",
    ]

    for query in queries:
        print(f"\n{'─' * 50}")
        print(f"Query: \"{query}\"")
        print(f"{'─' * 50}")

        results = index.search(query, top_k=3)

        for i, (chunk, score, source_index) in enumerate(results):
            print(f"\n  Result {i + 1} (score: {score:.4f}, source: {source_index}):")
            print(f"    Doc: {chunk.doc_id}")
            print(f"    Type: {chunk.content_type.value}")
            print(f"    Page: {chunk.metadata.get('page', '?')}")
            content_preview = chunk.text_content[:100].replace('\n', ' ')
            print(f"    Content: {content_preview}...")
            if chunk.metadata.get("visual"):
                print(f"    [CROSS-MODAL: Text query matched visual content]")

    # =========================================================================
    # Pipeline Metrics
    # =========================================================================
    print(f"\n\n{'=' * 70}")
    print("PIPELINE METRICS")
    print(f"{'=' * 70}")

    total_regions = sum(len(d.regions) for d in documents)
    type_counts = {}
    for doc in documents:
        for region in doc.regions:
            type_counts[region.content_type.value] = type_counts.get(region.content_type.value, 0) + 1

    print(f"\n  Documents processed: {len(documents)}")
    print(f"  Total regions identified: {total_regions}")
    print(f"  Region type distribution:")
    for rtype, count in sorted(type_counts.items()):
        print(f"    {rtype:10s}: {count}")
    print(f"\n  Chunks created: {len(all_chunks)}")
    print(f"  Avg chunks/document: {len(all_chunks) / len(documents):.1f}")

    # Cost estimation
    print(f"\n  Estimated costs (at scale, per 1000 documents):")
    print(f"    OCR processing:       ${total_regions * 0.5:.2f}")
    print(f"    Vision model calls:   ${len(index.visual_index) * 10:.2f}")
    print(f"    Text embeddings:      ${len(index.text_index) * 0.1:.2f}")
    print(f"    Image embeddings:     ${len(index.visual_index) * 0.2:.2f}")
    print(f"    Total per 1000 docs:  ${total_regions * 0.5 + len(index.visual_index) * 10 + len(index.text_index) * 0.1 + len(index.visual_index) * 0.2:.2f}")

    print(f"\n{'=' * 70}")
    print("Pipeline complete. Multi-modal RAG system ready for queries.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    random.seed(42)
    run_pipeline()
