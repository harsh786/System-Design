"""
Enterprise Knowledge Pipeline
==============================
Production-grade knowledge ingestion, processing, and indexing pipeline.
Handles: source connectors, change detection, parsing, cleaning, chunking,
metadata enrichment, PII classification, embedding, indexing, deletion, freshness.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional, Protocol

import numpy as np

# ============================================================================
# Configuration and Types
# ============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("knowledge_pipeline")


class SourceType(Enum):
    CONFLUENCE = "confluence"
    SHAREPOINT = "sharepoint"
    S3 = "s3"
    DATABASE = "database"
    GITHUB = "github"
    SLACK = "slack"
    EMAIL = "email"


class ContentFormat(Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"
    EMAIL = "email"
    SPREADSHEET = "spreadsheet"


class SensitivityLevel(Enum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3
    REGULATED = 4


class LifecycleState(Enum):
    ACTIVE = "active"
    STALE = "stale"
    TOMBSTONED = "tombstoned"
    ARCHIVED = "archived"


class PipelineStage(Enum):
    FETCH = "fetch"
    PARSE = "parse"
    CLEAN = "clean"
    CHUNK = "chunk"
    ENRICH = "enrich"
    CLASSIFY = "classify"
    EMBED = "embed"
    INDEX = "index"


@dataclass
class SourceDocument:
    """Raw document from a source system."""
    source_id: str
    source_type: SourceType
    source_url: str
    title: str
    raw_content: bytes
    content_format: ContentFormat
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    version: int = 1
    acl_groups: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.raw_content).hexdigest()


@dataclass
class ParsedContent:
    """Structured content after parsing."""
    document_id: str
    title: str
    sections: list[ContentSection]
    tables: list[TableData]
    images: list[ImageData]
    links: list[str]
    language: str = "en"
    parse_quality_score: float = 1.0


@dataclass
class ContentSection:
    """A logical section of a document."""
    heading: str
    level: int
    text: str
    position: int


@dataclass
class TableData:
    """Structured table extracted from a document."""
    headers: list[str]
    rows: list[list[str]]
    caption: Optional[str] = None
    position: int = 0


@dataclass
class ImageData:
    """Image extracted from a document."""
    image_bytes: bytes
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    ocr_text: Optional[str] = None
    position: int = 0


@dataclass
class Chunk:
    """A processable unit of knowledge."""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    content: str = ""
    heading_context: str = ""
    section_hierarchy: list[str] = field(default_factory=list)
    chunk_index: int = 0
    total_chunks: int = 0
    token_count: int = 0
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class EnrichedChunk:
    """Chunk with full metadata enrichment."""
    chunk: Chunk
    source_document: SourceDocument
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    content_type: str = "general"
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    pii_detected: bool = False
    pii_types: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    embedding: Optional[np.ndarray] = None
    keyword_tokens: list[str] = field(default_factory=list)
    lifecycle: LifecycleState = LifecycleState.ACTIVE


@dataclass
class PipelineMetrics:
    """Observability metrics for the pipeline."""
    stage: PipelineStage
    start_time: float = 0.0
    end_time: float = 0.0
    items_processed: int = 0
    items_failed: int = 0
    bytes_processed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def success_rate(self) -> float:
        total = self.items_processed + self.items_failed
        return self.items_processed / total if total > 0 else 0.0


# ============================================================================
# Source Connectors
# ============================================================================

class SourceConnector(ABC):
    """Base class for all source connectors."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"connector.{self.source_type.value}")

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        ...

    @abstractmethod
    async def list_documents(self, since: Optional[datetime] = None) -> AsyncIterator[str]:
        """List document IDs, optionally only those modified since a given time."""
        ...

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> SourceDocument:
        """Fetch a single document by ID."""
        ...

    @abstractmethod
    async def get_deleted_ids(self, since: Optional[datetime] = None) -> list[str]:
        """Return IDs of documents deleted since the given time."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify connector is operational."""
        ...


class ConfluenceConnector(SourceConnector):
    """Connector for Atlassian Confluence."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.CONFLUENCE

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config["base_url"]
        self.space_keys = config.get("space_keys", [])
        self.auth_token = config["auth_token"]
        self._last_sync: Optional[datetime] = None

    async def list_documents(self, since: Optional[datetime] = None) -> AsyncIterator[str]:
        """List Confluence page IDs using CQL search with modification filter."""
        self.logger.info(f"Listing documents since={since}")
        # In production: use Confluence REST API with CQL
        # cql = f'type=page AND space in ({spaces}) AND lastModified > "{since}"'
        # Paginate through results using start/limit
        sample_ids = ["page-001", "page-002", "page-003"]
        for doc_id in sample_ids:
            yield doc_id

    async def fetch_document(self, doc_id: str) -> SourceDocument:
        """Fetch page content with expand=body.storage,version,ancestors."""
        self.logger.info(f"Fetching document: {doc_id}")
        # In production: GET /rest/api/content/{id}?expand=body.storage,version,space,ancestors
        return SourceDocument(
            source_id=doc_id,
            source_type=SourceType.CONFLUENCE,
            source_url=f"{self.base_url}/pages/{doc_id}",
            title=f"Confluence Page {doc_id}",
            raw_content=b"<h1>Sample</h1><p>Content from Confluence</p>",
            content_format=ContentFormat.HTML,
            author="user@company.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            modified_at=datetime.now(timezone.utc),
            version=3,
            acl_groups=["engineering"],
            metadata={"space_key": "ENG", "ancestors": ["parent-page-001"]},
        )

    async def get_deleted_ids(self, since: Optional[datetime] = None) -> list[str]:
        """Check for deleted/trashed pages via Confluence trash API."""
        # GET /rest/api/content?status=trashed&limit=100
        return []

    async def health_check(self) -> bool:
        """Verify Confluence API is reachable."""
        # GET /rest/api/space?limit=1
        return True


class SharePointConnector(SourceConnector):
    """Connector for Microsoft SharePoint Online."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.SHAREPOINT

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.site_url = config["site_url"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.tenant_id = config["tenant_id"]
        self.drive_ids = config.get("drive_ids", [])

    async def list_documents(self, since: Optional[datetime] = None) -> AsyncIterator[str]:
        """List files using Microsoft Graph delta queries for incremental sync."""
        self.logger.info(f"Listing SharePoint documents since={since}")
        # In production: use Graph API delta queries
        # GET /sites/{site-id}/drive/root/delta
        sample_ids = ["sp-doc-001", "sp-doc-002"]
        for doc_id in sample_ids:
            yield doc_id

    async def fetch_document(self, doc_id: str) -> SourceDocument:
        """Download file content and metadata via Graph API."""
        self.logger.info(f"Fetching SharePoint document: {doc_id}")
        return SourceDocument(
            source_id=doc_id,
            source_type=SourceType.SHAREPOINT,
            source_url=f"{self.site_url}/documents/{doc_id}",
            title=f"SharePoint Document {doc_id}",
            raw_content=b"%PDF-1.4 sample content",
            content_format=ContentFormat.PDF,
            author="manager@company.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            modified_at=datetime.now(timezone.utc) - timedelta(hours=2),
            version=5,
            acl_groups=["all-employees"],
            metadata={"library": "Shared Documents", "site": "Engineering"},
        )

    async def get_deleted_ids(self, since: Optional[datetime] = None) -> list[str]:
        """Detect deletions via delta query @removed annotations."""
        return []

    async def health_check(self) -> bool:
        return True


class S3Connector(SourceConnector):
    """Connector for AWS S3 buckets."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.S3

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.bucket = config["bucket"]
        self.prefix = config.get("prefix", "")
        self.region = config.get("region", "us-east-1")

    async def list_documents(self, since: Optional[datetime] = None) -> AsyncIterator[str]:
        """List objects using S3 ListObjectsV2 with LastModified filtering."""
        self.logger.info(f"Listing S3 objects in s3://{self.bucket}/{self.prefix}")
        # In production: paginate with ContinuationToken, filter by LastModified
        sample_ids = ["documents/report-2024.pdf", "documents/guide.docx"]
        for doc_id in sample_ids:
            yield doc_id

    async def fetch_document(self, doc_id: str) -> SourceDocument:
        """Download object and extract metadata from S3 tags/metadata."""
        self.logger.info(f"Fetching S3 object: {doc_id}")
        ext = Path(doc_id).suffix.lower()
        format_map = {".pdf": ContentFormat.PDF, ".docx": ContentFormat.DOCX,
                      ".html": ContentFormat.HTML, ".md": ContentFormat.MARKDOWN}
        return SourceDocument(
            source_id=doc_id,
            source_type=SourceType.S3,
            source_url=f"s3://{self.bucket}/{doc_id}",
            title=Path(doc_id).stem,
            raw_content=b"binary content here",
            content_format=format_map.get(ext, ContentFormat.PLAINTEXT),
            modified_at=datetime.now(timezone.utc) - timedelta(hours=6),
            acl_groups=["data-team"],
            metadata={"bucket": self.bucket, "key": doc_id},
        )

    async def get_deleted_ids(self, since: Optional[datetime] = None) -> list[str]:
        """Compare current listing against known IDs to detect deletions."""
        return []

    async def health_check(self) -> bool:
        # HEAD bucket request
        return True


class DatabaseConnector(SourceConnector):
    """Connector for relational databases using CDC or polling."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.DATABASE

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.connection_string = config["connection_string"]
        self.tables = config.get("tables", [])
        self.timestamp_column = config.get("timestamp_column", "updated_at")

    async def list_documents(self, since: Optional[datetime] = None) -> AsyncIterator[str]:
        """Query for rows modified since last sync using timestamp column."""
        self.logger.info(f"Querying database for changes since {since}")
        # SELECT id FROM {table} WHERE {timestamp_col} > {since}
        sample_ids = ["row-1001", "row-1002"]
        for doc_id in sample_ids:
            yield doc_id

    async def fetch_document(self, doc_id: str) -> SourceDocument:
        """Fetch row data and serialize to structured document."""
        return SourceDocument(
            source_id=doc_id,
            source_type=SourceType.DATABASE,
            source_url=f"db://{self.tables[0]}/{doc_id}" if self.tables else f"db://table/{doc_id}",
            title=f"Record {doc_id}",
            raw_content=json.dumps({"id": doc_id, "data": "sample"}).encode(),
            content_format=ContentFormat.PLAINTEXT,
            modified_at=datetime.now(timezone.utc),
            metadata={"table": self.tables[0] if self.tables else "unknown"},
        )

    async def get_deleted_ids(self, since: Optional[datetime] = None) -> list[str]:
        """Check soft-delete flags or tombstone table."""
        return []

    async def health_check(self) -> bool:
        # SELECT 1
        return True


# ============================================================================
# Change Detection
# ============================================================================

class ChangeDetector:
    """Detects changes by comparing content hashes against stored state."""

    def __init__(self, state_store: dict[str, str] | None = None):
        # In production: Redis or database-backed state store
        self._state: dict[str, str] = state_store or {}
        self.logger = logging.getLogger("change_detector")

    def has_changed(self, doc: SourceDocument) -> bool:
        """Check if document content has changed since last sync."""
        stored_hash = self._state.get(doc.source_id)
        if stored_hash is None:
            self.logger.debug(f"New document: {doc.source_id}")
            return True
        changed = stored_hash != doc.content_hash
        if changed:
            self.logger.debug(f"Document changed: {doc.source_id}")
        return changed

    def mark_synced(self, doc: SourceDocument) -> None:
        """Record the current hash as the synced state."""
        self._state[doc.source_id] = doc.content_hash

    def get_known_ids(self) -> set[str]:
        """Return all document IDs we have previously synced."""
        return set(self._state.keys())

    def remove_id(self, doc_id: str) -> None:
        """Remove a document from tracked state (after deletion)."""
        self._state.pop(doc_id, None)


# ============================================================================
# Parser Orchestrator
# ============================================================================

class DocumentParser(ABC):
    """Base parser interface."""

    @abstractmethod
    def supported_formats(self) -> list[ContentFormat]:
        ...

    @abstractmethod
    async def parse(self, doc: SourceDocument) -> ParsedContent:
        ...


class PDFParser(DocumentParser):
    """PDF parser using PyMuPDF/Unstructured."""

    def supported_formats(self) -> list[ContentFormat]:
        return [ContentFormat.PDF]

    async def parse(self, doc: SourceDocument) -> ParsedContent:
        logger.info(f"Parsing PDF: {doc.title}")
        # In production: use PyMuPDF (fitz) or Unstructured
        # - Extract text blocks with position info
        # - Detect and extract tables
        # - Extract images with OCR
        # - Preserve reading order
        sections = [ContentSection(
            heading=doc.title,
            level=1,
            text="[PDF content would be extracted here with proper table/image handling]",
            position=0,
        )]
        return ParsedContent(
            document_id=doc.source_id,
            title=doc.title,
            sections=sections,
            tables=[],
            images=[],
            links=[],
            parse_quality_score=0.85,
        )


class HTMLParser(DocumentParser):
    """HTML parser using BeautifulSoup/Trafilatura."""

    def supported_formats(self) -> list[ContentFormat]:
        return [ContentFormat.HTML]

    async def parse(self, doc: SourceDocument) -> ParsedContent:
        logger.info(f"Parsing HTML: {doc.title}")
        content = doc.raw_content.decode("utf-8", errors="replace")
        # In production: use trafilatura for main content extraction
        # Remove navigation, ads, boilerplate
        # Extract headings hierarchy
        # Preserve tables as structured data
        sections = [ContentSection(
            heading=doc.title,
            level=1,
            text=self._strip_tags(content),
            position=0,
        )]
        return ParsedContent(
            document_id=doc.source_id,
            title=doc.title,
            sections=sections,
            tables=[],
            images=[],
            links=self._extract_links(content),
        )

    def _strip_tags(self, html: str) -> str:
        """Basic tag removal (use BeautifulSoup in production)."""
        return re.sub(r'<[^>]+>', ' ', html).strip()

    def _extract_links(self, html: str) -> list[str]:
        """Extract href values."""
        return re.findall(r'href="([^"]+)"', html)


class DOCXParser(DocumentParser):
    """DOCX parser using python-docx."""

    def supported_formats(self) -> list[ContentFormat]:
        return [ContentFormat.DOCX]

    async def parse(self, doc: SourceDocument) -> ParsedContent:
        logger.info(f"Parsing DOCX: {doc.title}")
        # In production: use python-docx
        # - Extract paragraphs with style info (heading levels)
        # - Extract tables as TableData
        # - Handle embedded images
        # - Process tracked changes
        sections = [ContentSection(
            heading=doc.title, level=1,
            text="[DOCX content extracted with structure preservation]",
            position=0,
        )]
        return ParsedContent(
            document_id=doc.source_id, title=doc.title,
            sections=sections, tables=[], images=[], links=[],
        )


class EmailParser(DocumentParser):
    """Email parser handling threads, attachments, signatures."""

    def supported_formats(self) -> list[ContentFormat]:
        return [ContentFormat.EMAIL]

    async def parse(self, doc: SourceDocument) -> ParsedContent:
        logger.info(f"Parsing email: {doc.title}")
        # In production: use email.parser
        # - Extract subject, from, to, date
        # - Parse MIME parts
        # - Remove signatures and disclaimers
        # - Handle thread quoting
        # - Extract attachments for separate processing
        sections = [ContentSection(
            heading=f"Email: {doc.title}", level=1,
            text="[Email body with signature removed]",
            position=0,
        )]
        return ParsedContent(
            document_id=doc.source_id, title=doc.title,
            sections=sections, tables=[], images=[], links=[],
        )


class ParserOrchestrator:
    """Routes documents to appropriate parsers."""

    def __init__(self):
        self._parsers: dict[ContentFormat, DocumentParser] = {}
        self.logger = logging.getLogger("parser_orchestrator")
        self._register_defaults()

    def _register_defaults(self):
        for parser in [PDFParser(), HTMLParser(), DOCXParser(), EmailParser()]:
            for fmt in parser.supported_formats():
                self._parsers[fmt] = parser

    def register_parser(self, parser: DocumentParser) -> None:
        for fmt in parser.supported_formats():
            self._parsers[fmt] = parser

    async def parse(self, doc: SourceDocument) -> ParsedContent:
        """Parse document using the appropriate parser."""
        parser = self._parsers.get(doc.content_format)
        if not parser:
            self.logger.warning(f"No parser for format {doc.content_format}, using plaintext fallback")
            return ParsedContent(
                document_id=doc.source_id, title=doc.title,
                sections=[ContentSection(
                    heading=doc.title, level=1,
                    text=doc.raw_content.decode("utf-8", errors="replace"),
                    position=0,
                )],
                tables=[], images=[], links=[],
            )
        return await parser.parse(doc)


# ============================================================================
# Cleaner and Normalizer
# ============================================================================

class ContentCleaner:
    """Cleans and normalizes parsed content."""

    def __init__(self):
        self.logger = logging.getLogger("content_cleaner")
        # Patterns to remove
        self._boilerplate_patterns = [
            r'(?i)confidential\s*-\s*do not distribute',
            r'(?i)page\s+\d+\s+of\s+\d+',
            r'(?i)©\s*\d{4}.*?all rights reserved',
            r'(?i)last updated:.*?\n',
        ]
        self._whitespace_pattern = re.compile(r'\s+')
        self._url_pattern = re.compile(r'https?://\S+')

    def clean(self, content: ParsedContent) -> ParsedContent:
        """Apply all cleaning transformations."""
        self.logger.debug(f"Cleaning document: {content.document_id}")
        cleaned_sections = []
        for section in content.sections:
            cleaned_text = self._clean_text(section.text)
            if len(cleaned_text.strip()) > 20:  # Skip trivially short sections
                cleaned_sections.append(ContentSection(
                    heading=section.heading,
                    level=section.level,
                    text=cleaned_text,
                    position=section.position,
                ))
        content.sections = cleaned_sections
        return content

    def _clean_text(self, text: str) -> str:
        """Apply text cleaning rules."""
        # Remove boilerplate
        for pattern in self._boilerplate_patterns:
            text = re.sub(pattern, '', text)
        # Normalize whitespace
        text = self._whitespace_pattern.sub(' ', text)
        # Normalize unicode
        text = text.replace('\u2019', "'").replace('\u2018', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('\u2014', '—').replace('\u2013', '–')
        # Remove null bytes
        text = text.replace('\x00', '')
        return text.strip()


# ============================================================================
# Chunking Strategies
# ============================================================================

class ChunkingStrategy(ABC):
    """Base chunking strategy."""

    @abstractmethod
    def chunk(self, content: ParsedContent, doc: SourceDocument) -> list[Chunk]:
        ...


class SemanticChunker(ChunkingStrategy):
    """
    Chunks content respecting semantic boundaries (sections, paragraphs).
    Includes heading context and overlap for continuity.
    """

    def __init__(self, max_tokens: int = 512, overlap_tokens: int = 50):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.logger = logging.getLogger("semantic_chunker")

    def chunk(self, content: ParsedContent, doc: SourceDocument) -> list[Chunk]:
        """Create semantically-aware chunks from parsed content."""
        chunks: list[Chunk] = []

        for section in content.sections:
            section_chunks = self._chunk_section(section, doc.source_id)
            chunks.extend(section_chunks)

        # Also chunk tables as separate units
        for table in content.tables:
            table_chunk = self._chunk_table(table, doc.source_id)
            chunks.append(table_chunk)

        # Set total_chunks and indices
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.total_chunks = total
            chunk.document_id = doc.source_id

        # Create parent-child relationships for hierarchical retrieval
        if len(chunks) > 1:
            parent = Chunk(
                chunk_id=str(uuid.uuid4()),
                document_id=doc.source_id,
                content="\n\n".join(c.content[:200] for c in chunks[:5]),  # Summary parent
                heading_context=content.title,
                chunk_index=0,
                total_chunks=1,
            )
            parent.child_chunk_ids = [c.chunk_id for c in chunks]
            for c in chunks:
                c.parent_chunk_id = parent.chunk_id
            chunks.insert(0, parent)

        self.logger.info(f"Created {len(chunks)} chunks for {doc.source_id}")
        return chunks

    def _chunk_section(self, section: ContentSection, doc_id: str) -> list[Chunk]:
        """Split a section into chunks respecting sentence boundaries."""
        text = section.text
        sentences = self._split_sentences(text)
        chunks = []
        current_text = ""
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            if current_tokens + sentence_tokens > self.max_tokens and current_text:
                chunks.append(Chunk(
                    content=current_text.strip(),
                    heading_context=section.heading,
                    section_hierarchy=[section.heading],
                    token_count=current_tokens,
                ))
                # Overlap: keep last portion
                overlap_text = current_text[-self.overlap_tokens * 4:]  # Rough char estimate
                current_text = overlap_text + " " + sentence
                current_tokens = self._estimate_tokens(current_text)
            else:
                current_text += " " + sentence
                current_tokens += sentence_tokens

        if current_text.strip():
            chunks.append(Chunk(
                content=current_text.strip(),
                heading_context=section.heading,
                section_hierarchy=[section.heading],
                token_count=current_tokens,
            ))

        return chunks

    def _chunk_table(self, table: TableData, doc_id: str) -> Chunk:
        """Convert table to a self-contained text chunk."""
        lines = []
        if table.caption:
            lines.append(f"Table: {table.caption}")
        lines.append(" | ".join(table.headers))
        lines.append("-" * 40)
        for row in table.rows:
            lines.append(" | ".join(row))
        return Chunk(
            content="\n".join(lines),
            heading_context=table.caption or "Table",
            token_count=self._estimate_tokens("\n".join(lines)),
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitter; use spaCy/nltk in production
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token)."""
        return len(text) // 4


# ============================================================================
# Metadata Enricher
# ============================================================================

class MetadataEnricher:
    """Enriches chunks with entities, topics, content type, and quality score."""

    def __init__(self):
        self.logger = logging.getLogger("metadata_enricher")
        # In production: load NER model, topic classifier, etc.
        self._entity_patterns = {
            "technology": re.compile(r'\b(Kubernetes|Docker|AWS|Azure|GCP|Python|Java|PostgreSQL|Redis|Kafka)\b', re.I),
            "process": re.compile(r'\b(deployment|migration|backup|monitoring|scaling|CI/CD)\b', re.I),
            "team": re.compile(r'\b(engineering|product|design|data|security|SRE|platform)\b', re.I),
        }
        self._topic_keywords = {
            "infrastructure": ["server", "cluster", "node", "network", "load balancer"],
            "security": ["authentication", "authorization", "encryption", "vulnerability", "firewall"],
            "data": ["database", "pipeline", "ETL", "warehouse", "lake", "streaming"],
            "operations": ["incident", "runbook", "alert", "on-call", "SLA", "uptime"],
        }

    def enrich(self, chunk: Chunk, doc: SourceDocument) -> EnrichedChunk:
        """Apply all enrichment steps to a chunk."""
        entities = self._extract_entities(chunk.content)
        topics = self._classify_topics(chunk.content)
        content_type = self._detect_content_type(chunk.content)
        quality_score = self._assess_quality(chunk)
        keywords = self._extract_keywords(chunk.content)

        return EnrichedChunk(
            chunk=chunk,
            source_document=doc,
            entities=entities,
            topics=topics,
            content_type=content_type,
            quality_score=quality_score,
            keyword_tokens=keywords,
        )

    def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities from text."""
        entities = []
        for entity_type, pattern in self._entity_patterns.items():
            matches = pattern.findall(text)
            entities.extend(matches)
        return list(set(entities))

    def _classify_topics(self, text: str) -> list[str]:
        """Classify text into topic categories."""
        text_lower = text.lower()
        topics = []
        for topic, keywords in self._topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        return topics or ["general"]

    def _detect_content_type(self, text: str) -> str:
        """Detect whether content is procedure, reference, tutorial, etc."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["step 1", "step 2", "first,", "then,", "finally,"]):
            return "procedure"
        if any(w in text_lower for w in ["api", "endpoint", "parameter", "returns"]):
            return "api_reference"
        if any(w in text_lower for w in ["error", "issue", "fix", "workaround", "solution"]):
            return "troubleshooting"
        return "general"

    def _assess_quality(self, chunk: Chunk) -> float:
        """Score chunk quality based on heuristics."""
        score = 1.0
        # Penalize very short chunks
        if chunk.token_count < 30:
            score -= 0.3
        # Penalize chunks without heading context
        if not chunk.heading_context:
            score -= 0.1
        # Penalize chunks that look like boilerplate
        if chunk.content.count("...") > 3:
            score -= 0.2
        return max(0.0, min(1.0, score))

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords for BM25 indexing."""
        # In production: use TF-IDF or RAKE
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Simple frequency-based extraction
        from collections import Counter
        freq = Counter(words)
        # Return top keywords excluding stopwords
        stopwords = {"the", "and", "for", "are", "this", "that", "with", "from", "have", "will", "not", "can"}
        return [w for w, _ in freq.most_common(20) if w not in stopwords]


# ============================================================================
# PII / Sensitivity Classifier
# ============================================================================

class PIIClassifier:
    """Detects PII and classifies sensitivity level."""

    def __init__(self):
        self.logger = logging.getLogger("pii_classifier")
        self._patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            "api_key": re.compile(r'\b(?:sk|pk|api[_-]?key)[_-][A-Za-z0-9]{20,}\b', re.I),
            "password": re.compile(r'(?i)password\s*[:=]\s*\S+'),
        }
        self._sensitivity_escalation = {
            "ssn": SensitivityLevel.REGULATED,
            "credit_card": SensitivityLevel.REGULATED,
            "api_key": SensitivityLevel.RESTRICTED,
            "password": SensitivityLevel.RESTRICTED,
            "email": SensitivityLevel.CONFIDENTIAL,
            "phone": SensitivityLevel.CONFIDENTIAL,
            "ip_address": SensitivityLevel.INTERNAL,
        }

    def classify(self, enriched: EnrichedChunk) -> EnrichedChunk:
        """Detect PII and set sensitivity level."""
        text = enriched.chunk.content
        detected_types: list[str] = []
        max_sensitivity = enriched.sensitivity

        for pii_type, pattern in self._patterns.items():
            if pattern.search(text):
                detected_types.append(pii_type)
                type_sensitivity = self._sensitivity_escalation[pii_type]
                if type_sensitivity.value > max_sensitivity.value:
                    max_sensitivity = type_sensitivity

        enriched.pii_detected = len(detected_types) > 0
        enriched.pii_types = detected_types
        enriched.sensitivity = max_sensitivity

        if detected_types:
            self.logger.warning(
                f"PII detected in chunk {enriched.chunk.chunk_id}: {detected_types} "
                f"→ sensitivity={max_sensitivity.name}"
            )

        return enriched


# ============================================================================
# Embedding Service
# ============================================================================

class EmbeddingService:
    """Generates embeddings with batching and retry logic."""

    def __init__(self, model_name: str = "text-embedding-3-small", batch_size: int = 32, dimensions: int = 1536):
        self.model_name = model_name
        self.batch_size = batch_size
        self.dimensions = dimensions
        self.logger = logging.getLogger("embedding_service")
        self._request_count = 0
        self._total_tokens = 0

    async def embed_batch(self, chunks: list[EnrichedChunk]) -> list[EnrichedChunk]:
        """Generate embeddings for a batch of chunks."""
        self.logger.info(f"Embedding batch of {len(chunks)} chunks")

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            texts = [self._prepare_text(c) for c in batch]

            # In production: call OpenAI/Azure OpenAI embeddings API
            # response = await openai.embeddings.create(input=texts, model=self.model_name)
            embeddings = await self._generate_embeddings(texts)

            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding = embedding

            self._request_count += 1
            self._total_tokens += sum(len(t.split()) for t in texts)

            # Rate limiting
            if i + self.batch_size < len(chunks):
                await asyncio.sleep(0.1)  # Respect rate limits

        return chunks

    def _prepare_text(self, chunk: EnrichedChunk) -> str:
        """Prepare text for embedding with context prefix."""
        # Prepend heading context to improve embedding quality
        parts = []
        if chunk.chunk.heading_context:
            parts.append(f"Section: {chunk.chunk.heading_context}")
        if chunk.source_document.title:
            parts.append(f"Document: {chunk.source_document.title}")
        parts.append(chunk.chunk.content)
        return "\n".join(parts)

    async def _generate_embeddings(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings (mock for demo; use real API in production)."""
        # Simulate API call
        await asyncio.sleep(0.05)
        return [np.random.randn(self.dimensions).astype(np.float32) for _ in texts]

    @property
    def stats(self) -> dict[str, int]:
        return {"requests": self._request_count, "total_tokens": self._total_tokens}


# ============================================================================
# Vector DB Writer
# ============================================================================

class VectorDBWriter:
    """Writes embeddings and metadata to vector database with versioning."""

    def __init__(self, collection_name: str = "knowledge_base"):
        self.collection_name = collection_name
        self.logger = logging.getLogger("vector_db_writer")
        # In production: Pinecone, Weaviate, Qdrant, Milvus, or pgvector client
        self._store: dict[str, dict] = {}  # Mock store
        self._version = 0

    async def upsert_batch(self, chunks: list[EnrichedChunk]) -> int:
        """Upsert chunks with embeddings into vector database."""
        self._version += 1
        upserted = 0

        for chunk in chunks:
            if chunk.embedding is None:
                self.logger.warning(f"Skipping chunk {chunk.chunk.chunk_id} - no embedding")
                continue

            record = {
                "id": chunk.chunk.chunk_id,
                "vector": chunk.embedding.tolist(),
                "metadata": {
                    "document_id": chunk.chunk.document_id,
                    "source_type": chunk.source_document.source_type.value,
                    "source_url": chunk.source_document.source_url,
                    "title": chunk.source_document.title,
                    "heading_context": chunk.chunk.heading_context,
                    "section_hierarchy": chunk.chunk.section_hierarchy,
                    "entities": chunk.entities,
                    "topics": chunk.topics,
                    "content_type": chunk.content_type,
                    "sensitivity": chunk.sensitivity.value,
                    "acl_groups": chunk.source_document.acl_groups,
                    "author": chunk.source_document.author,
                    "modified_at": chunk.source_document.modified_at.isoformat() if chunk.source_document.modified_at else None,
                    "version": self._version,
                    "quality_score": chunk.quality_score,
                    "chunk_index": chunk.chunk.chunk_index,
                    "total_chunks": chunk.chunk.total_chunks,
                    "lifecycle": chunk.lifecycle.value,
                },
                "content": chunk.chunk.content,
            }
            # In production: batch upsert to vector DB
            self._store[chunk.chunk.chunk_id] = record
            upserted += 1

        self.logger.info(f"Upserted {upserted} vectors (version={self._version})")
        return upserted

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document."""
        to_delete = [
            cid for cid, record in self._store.items()
            if record["metadata"]["document_id"] == document_id
        ]
        for cid in to_delete:
            del self._store[cid]
        self.logger.info(f"Deleted {len(to_delete)} vectors for document {document_id}")
        return len(to_delete)

    async def tombstone_by_document(self, document_id: str) -> int:
        """Soft-delete by marking lifecycle as tombstoned."""
        count = 0
        for record in self._store.values():
            if record["metadata"]["document_id"] == document_id:
                record["metadata"]["lifecycle"] = LifecycleState.TOMBSTONED.value
                count += 1
        self.logger.info(f"Tombstoned {count} vectors for document {document_id}")
        return count


# ============================================================================
# Keyword Index Writer
# ============================================================================

class KeywordIndexWriter:
    """Writes to keyword/BM25 index (Elasticsearch/OpenSearch)."""

    def __init__(self, index_name: str = "knowledge_keywords"):
        self.index_name = index_name
        self.logger = logging.getLogger("keyword_index_writer")
        self._index: dict[str, dict] = {}  # Mock

    async def index_batch(self, chunks: list[EnrichedChunk]) -> int:
        """Index chunks for keyword/BM25 search."""
        indexed = 0
        for chunk in chunks:
            doc = {
                "chunk_id": chunk.chunk.chunk_id,
                "document_id": chunk.chunk.document_id,
                "content": chunk.chunk.content,
                "title": chunk.source_document.title,
                "heading": chunk.chunk.heading_context,
                "keywords": chunk.keyword_tokens,
                "entities": chunk.entities,
                "topics": chunk.topics,
                "acl_groups": chunk.source_document.acl_groups,
                "sensitivity": chunk.sensitivity.value,
                "modified_at": chunk.source_document.modified_at.isoformat() if chunk.source_document.modified_at else None,
            }
            # In production: bulk index to Elasticsearch
            self._index[chunk.chunk.chunk_id] = doc
            indexed += 1

        self.logger.info(f"Indexed {indexed} documents in keyword index")
        return indexed

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all index entries for a document."""
        to_delete = [
            cid for cid, doc in self._index.items()
            if doc["document_id"] == document_id
        ]
        for cid in to_delete:
            del self._index[cid]
        return len(to_delete)


# ============================================================================
# Deletion Propagation Handler
# ============================================================================

class DeletionPropagator:
    """Handles deletion propagation across all stores."""

    def __init__(
        self,
        vector_db: VectorDBWriter,
        keyword_index: KeywordIndexWriter,
        change_detector: ChangeDetector,
    ):
        self.vector_db = vector_db
        self.keyword_index = keyword_index
        self.change_detector = change_detector
        self.logger = logging.getLogger("deletion_propagator")
        self._deletion_log: list[dict] = []

    async def propagate_deletion(self, document_id: str, source_type: SourceType, reason: str = "source_deleted") -> dict:
        """Propagate deletion across all stores with audit logging."""
        self.logger.warning(f"Propagating deletion: {document_id} (reason={reason})")
        start = time.time()

        results = {
            "document_id": document_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vector_deleted": 0,
            "keyword_deleted": 0,
            "success": False,
        }

        try:
            # 1. Tombstone in vector DB (soft delete first for safety)
            results["vector_deleted"] = await self.vector_db.tombstone_by_document(document_id)

            # 2. Delete from keyword index
            results["keyword_deleted"] = await self.keyword_index.delete_by_document(document_id)

            # 3. Remove from change detector state
            self.change_detector.remove_id(document_id)

            # 4. Hard delete from vector DB after confirmation
            await self.vector_db.delete_by_document(document_id)

            results["success"] = True
            results["duration_ms"] = (time.time() - start) * 1000

        except Exception as e:
            self.logger.error(f"Deletion propagation failed for {document_id}: {e}")
            results["error"] = str(e)

        # Audit log
        self._deletion_log.append(results)
        return results

    async def verify_deletion(self, document_id: str) -> bool:
        """Verify document is fully deleted from all stores."""
        # Check vector DB
        for record in self.vector_db._store.values():
            if record["metadata"]["document_id"] == document_id:
                if record["metadata"]["lifecycle"] != LifecycleState.TOMBSTONED.value:
                    return False
        # Check keyword index
        for doc in self.keyword_index._index.values():
            if doc["document_id"] == document_id:
                return False
        return True


# ============================================================================
# Freshness Monitor
# ============================================================================

class FreshnessMonitor:
    """Monitors knowledge freshness against SLAs."""

    def __init__(self):
        self.logger = logging.getLogger("freshness_monitor")
        self._slas: dict[SourceType, timedelta] = {
            SourceType.CONFLUENCE: timedelta(hours=1),
            SourceType.SHAREPOINT: timedelta(hours=4),
            SourceType.S3: timedelta(hours=4),
            SourceType.DATABASE: timedelta(minutes=5),
            SourceType.GITHUB: timedelta(minutes=15),
            SourceType.SLACK: timedelta(minutes=5),
        }
        self._last_sync_times: dict[str, datetime] = {}
        self._violations: list[dict] = []

    def record_sync(self, source_id: str, sync_time: datetime) -> None:
        """Record that a source was successfully synced."""
        self._last_sync_times[source_id] = sync_time

    def check_freshness(self, source_id: str, source_type: SourceType) -> dict:
        """Check if a source is within its freshness SLA."""
        now = datetime.now(timezone.utc)
        last_sync = self._last_sync_times.get(source_id)
        sla = self._slas.get(source_type, timedelta(hours=24))

        if last_sync is None:
            violation = {
                "source_id": source_id,
                "source_type": source_type.value,
                "status": "never_synced",
                "sla": str(sla),
                "checked_at": now.isoformat(),
            }
            self._violations.append(violation)
            return violation

        staleness = now - last_sync
        within_sla = staleness <= sla

        result = {
            "source_id": source_id,
            "source_type": source_type.value,
            "last_sync": last_sync.isoformat(),
            "staleness_seconds": staleness.total_seconds(),
            "sla_seconds": sla.total_seconds(),
            "within_sla": within_sla,
            "status": "fresh" if within_sla else "stale",
        }

        if not within_sla:
            self._violations.append(result)
            self.logger.warning(
                f"Freshness SLA violation: {source_id} is {staleness} stale (SLA={sla})"
            )

        return result

    def get_violations(self) -> list[dict]:
        """Return all current freshness violations."""
        return self._violations

    def get_compliance_rate(self) -> float:
        """Calculate overall freshness compliance rate."""
        if not self._last_sync_times:
            return 0.0
        total = len(self._last_sync_times)
        violations = len([v for v in self._violations if v.get("status") == "stale"])
        return (total - violations) / total


# ============================================================================
# Pipeline Observability
# ============================================================================

class PipelineObserver:
    """Collects and reports pipeline metrics."""

    def __init__(self):
        self.logger = logging.getLogger("pipeline_observer")
        self._metrics: list[PipelineMetrics] = []
        self._run_id: str = str(uuid.uuid4())
        self._start_time: float = time.time()

    def start_stage(self, stage: PipelineStage) -> PipelineMetrics:
        """Start tracking a pipeline stage."""
        metrics = PipelineMetrics(stage=stage, start_time=time.time())
        self._metrics.append(metrics)
        self.logger.info(f"[{self._run_id[:8]}] Starting stage: {stage.value}")
        return metrics

    def end_stage(self, metrics: PipelineMetrics, items_processed: int = 0,
                  items_failed: int = 0, bytes_processed: int = 0) -> None:
        """End tracking a pipeline stage."""
        metrics.end_time = time.time()
        metrics.items_processed = items_processed
        metrics.items_failed = items_failed
        metrics.bytes_processed = bytes_processed
        self.logger.info(
            f"[{self._run_id[:8]}] Completed stage: {metrics.stage.value} | "
            f"processed={items_processed} failed={items_failed} "
            f"duration={metrics.duration_ms:.1f}ms"
        )

    def get_summary(self) -> dict:
        """Get full pipeline run summary."""
        return {
            "run_id": self._run_id,
            "total_duration_ms": (time.time() - self._start_time) * 1000,
            "stages": [
                {
                    "stage": m.stage.value,
                    "duration_ms": m.duration_ms,
                    "items_processed": m.items_processed,
                    "items_failed": m.items_failed,
                    "success_rate": m.success_rate,
                    "bytes_processed": m.bytes_processed,
                }
                for m in self._metrics
            ],
        }


# ============================================================================
# Main Pipeline Orchestrator
# ============================================================================

class KnowledgePipeline:
    """
    Main pipeline orchestrator that coordinates all stages of knowledge ingestion.

    Flow:
    Source → Fetch → Parse → Clean → Chunk → Enrich → Classify → Embed → Index
    """

    def __init__(
        self,
        connectors: list[SourceConnector],
        parser: ParserOrchestrator | None = None,
        cleaner: ContentCleaner | None = None,
        chunker: ChunkingStrategy | None = None,
        enricher: MetadataEnricher | None = None,
        pii_classifier: PIIClassifier | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_db: VectorDBWriter | None = None,
        keyword_index: KeywordIndexWriter | None = None,
        freshness_monitor: FreshnessMonitor | None = None,
    ):
        self.connectors = connectors
        self.parser = parser or ParserOrchestrator()
        self.cleaner = cleaner or ContentCleaner()
        self.chunker = chunker or SemanticChunker()
        self.enricher = enricher or MetadataEnricher()
        self.pii_classifier = pii_classifier or PIIClassifier()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_db = vector_db or VectorDBWriter()
        self.keyword_index = keyword_index or KeywordIndexWriter()
        self.freshness_monitor = freshness_monitor or FreshnessMonitor()
        self.change_detector = ChangeDetector()
        self.deletion_propagator = DeletionPropagator(
            self.vector_db, self.keyword_index, self.change_detector
        )
        self.observer = PipelineObserver()
        self.logger = logging.getLogger("knowledge_pipeline")

    async def run_full_sync(self, since: Optional[datetime] = None) -> dict:
        """Execute full pipeline for all connectors."""
        self.logger.info(f"Starting pipeline run (since={since})")
        total_processed = 0
        total_failed = 0

        for connector in self.connectors:
            # Health check
            if not await connector.health_check():
                self.logger.error(f"Connector {connector.source_type.value} health check failed")
                continue

            try:
                # Process new/modified documents
                processed, failed = await self._process_connector(connector, since)
                total_processed += processed
                total_failed += failed

                # Handle deletions
                deleted_ids = await connector.get_deleted_ids(since)
                for doc_id in deleted_ids:
                    await self.deletion_propagator.propagate_deletion(
                        doc_id, connector.source_type, reason="source_deleted"
                    )

                # Record freshness
                self.freshness_monitor.record_sync(
                    connector.source_type.value,
                    datetime.now(timezone.utc),
                )

            except Exception as e:
                self.logger.error(f"Connector {connector.source_type.value} failed: {e}")
                total_failed += 1

        summary = self.observer.get_summary()
        summary["total_processed"] = total_processed
        summary["total_failed"] = total_failed
        self.logger.info(f"Pipeline run complete: {total_processed} processed, {total_failed} failed")
        return summary

    async def _process_connector(self, connector: SourceConnector, since: Optional[datetime]) -> tuple[int, int]:
        """Process all documents from a single connector."""
        processed = 0
        failed = 0

        async for doc_id in connector.list_documents(since):
            try:
                # Fetch
                metrics = self.observer.start_stage(PipelineStage.FETCH)
                doc = await connector.fetch_document(doc_id)
                self.observer.end_stage(metrics, items_processed=1, bytes_processed=len(doc.raw_content))

                # Change detection
                if not self.change_detector.has_changed(doc):
                    self.logger.debug(f"Skipping unchanged document: {doc_id}")
                    continue

                # Parse
                metrics = self.observer.start_stage(PipelineStage.PARSE)
                parsed = await self.parser.parse(doc)
                self.observer.end_stage(metrics, items_processed=1)

                # Clean
                metrics = self.observer.start_stage(PipelineStage.CLEAN)
                cleaned = self.cleaner.clean(parsed)
                self.observer.end_stage(metrics, items_processed=1)

                # Chunk
                metrics = self.observer.start_stage(PipelineStage.CHUNK)
                chunks = self.chunker.chunk(cleaned, doc)
                self.observer.end_stage(metrics, items_processed=len(chunks))

                # Enrich
                metrics = self.observer.start_stage(PipelineStage.ENRICH)
                enriched_chunks = [self.enricher.enrich(chunk, doc) for chunk in chunks]
                self.observer.end_stage(metrics, items_processed=len(enriched_chunks))

                # PII Classification
                metrics = self.observer.start_stage(PipelineStage.CLASSIFY)
                classified_chunks = [self.pii_classifier.classify(ec) for ec in enriched_chunks]
                self.observer.end_stage(metrics, items_processed=len(classified_chunks))

                # Embed
                metrics = self.observer.start_stage(PipelineStage.EMBED)
                embedded_chunks = await self.embedding_service.embed_batch(classified_chunks)
                self.observer.end_stage(metrics, items_processed=len(embedded_chunks))

                # Index (vector + keyword in parallel)
                metrics = self.observer.start_stage(PipelineStage.INDEX)
                vector_count, keyword_count = await asyncio.gather(
                    self.vector_db.upsert_batch(embedded_chunks),
                    self.keyword_index.index_batch(embedded_chunks),
                )
                self.observer.end_stage(metrics, items_processed=vector_count + keyword_count)

                # Mark as synced
                self.change_detector.mark_synced(doc)
                processed += 1

            except Exception as e:
                self.logger.error(f"Failed to process document {doc_id}: {e}")
                failed += 1

        return processed, failed

    async def process_single_document(self, doc: SourceDocument) -> list[EnrichedChunk]:
        """Process a single document through the full pipeline (for testing/on-demand)."""
        parsed = await self.parser.parse(doc)
        cleaned = self.cleaner.clean(parsed)
        chunks = self.chunker.chunk(cleaned, doc)
        enriched = [self.enricher.enrich(c, doc) for c in chunks]
        classified = [self.pii_classifier.classify(e) for e in enriched]
        embedded = await self.embedding_service.embed_batch(classified)
        await self.vector_db.upsert_batch(embedded)
        await self.keyword_index.index_batch(embedded)
        self.change_detector.mark_synced(doc)
        return embedded


# ============================================================================
# Entry Point
# ============================================================================

async def main():
    """Demo pipeline execution."""
    # Configure connectors
    connectors: list[SourceConnector] = [
        ConfluenceConnector({
            "base_url": "https://company.atlassian.net/wiki",
            "space_keys": ["ENG", "OPS"],
            "auth_token": "fake-token",
        }),
        SharePointConnector({
            "site_url": "https://company.sharepoint.com/sites/engineering",
            "client_id": "app-id",
            "client_secret": "secret",
            "tenant_id": "tenant-id",
        }),
        S3Connector({
            "bucket": "company-knowledge-base",
            "prefix": "documents/",
            "region": "us-east-1",
        }),
        DatabaseConnector({
            "connection_string": "postgresql://localhost:5432/knowledge",
            "tables": ["articles", "faqs"],
            "timestamp_column": "updated_at",
        }),
    ]

    # Create and run pipeline
    pipeline = KnowledgePipeline(connectors=connectors)
    summary = await pipeline.run_full_sync(since=datetime.now(timezone.utc) - timedelta(hours=1))

    # Print results
    print("\n" + "=" * 60)
    print("PIPELINE RUN SUMMARY")
    print("=" * 60)
    print(json.dumps(summary, indent=2, default=str))

    # Check freshness
    print("\n" + "=" * 60)
    print("FRESHNESS STATUS")
    print("=" * 60)
    for connector in connectors:
        status = pipeline.freshness_monitor.check_freshness(
            connector.source_type.value, connector.source_type
        )
        print(f"  {connector.source_type.value}: {status['status']}")

    print(f"\n  Compliance rate: {pipeline.freshness_monitor.get_compliance_rate():.1%}")


if __name__ == "__main__":
    asyncio.run(main())
