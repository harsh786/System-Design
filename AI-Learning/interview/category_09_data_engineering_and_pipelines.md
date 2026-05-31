# Data Pipelines and Document Ingestion (Questions 151-155)

## Q151: Design a document ingestion pipeline that handles 10 different file formats (PDF, DOCX, HTML, Markdown, PowerPoint, Excel, images, audio transcripts, video transcripts, code repos) with guaranteed processing and retry logic.

### Answer

**Architecture Overview:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Document Ingestion Pipeline                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────────┐    │
│  │  Upload  │───▶│  Format      │───▶│  Parser Router          │    │
│  │  Gateway │    │  Detector    │    │  (Content-Type Based)   │    │
│  └──────────┘    └──────────────┘    └─────────┬───────────────┘    │
│                                                 │                     │
│       ┌─────────────────────────────────────────┼──────────┐         │
│       ▼            ▼           ▼                ▼          ▼         │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐  ┌────────┐   │
│  │PDF     │  │DOCX    │  │HTML    │  │Image/Audio │  │Code    │   │
│  │Parser  │  │Parser  │  │Parser  │  │Transcriber │  │Parser  │   │
│  └───┬────┘  └───┬────┘  └───┬────┘  └─────┬──────┘  └───┬────┘   │
│      └───────────┴───────────┴──────────────┴──────────────┘         │
│                              │                                        │
│                    ┌─────────▼──────────┐                            │
│                    │  Chunking Engine   │                            │
│                    │  (Format-Aware)    │                            │
│                    └─────────┬──────────┘                            │
│                              │                                        │
│                    ┌─────────▼──────────┐                            │
│                    │  Embedding +       │                            │
│                    │  Index Writer      │                            │
│                    └────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Guaranteed Processing with Dead Letter Queue:**

```python
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import hashlib

class DocFormat(Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "markdown"
    PPTX = "pptx"
    XLSX = "xlsx"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE_REPO = "code_repo"

@dataclass
class IngestionJob:
    doc_id: str
    source_url: str
    format: DocFormat
    tenant_id: str
    retry_count: int = 0
    max_retries: int = 3
    backoff_base: float = 2.0
    checksum: str = ""
    metadata: dict = field(default_factory=dict)

class IngestionPipeline:
    def __init__(self, queue_client, parsers, embedding_service, index_writer):
        self.queue = queue_client  # SQS/Kafka
        self.parsers = parsers    # format -> parser mapping
        self.embedder = embedding_service
        self.index_writer = index_writer
        self.dlq = queue_client.get_dlq()

    async def process_job(self, job: IngestionJob):
        """Process with exactly-once semantics via idempotency key."""
        idempotency_key = f"{job.doc_id}:{job.checksum}"
        
        if await self.is_already_processed(idempotency_key):
            return  # Dedup
        
        try:
            # Step 1: Parse
            parser = self.parsers[job.format]
            raw_content = await parser.extract(job.source_url)
            
            # Step 2: Validate extraction quality
            quality_score = self.assess_quality(raw_content)
            if quality_score < 0.3:
                raise ExtractionQualityError(f"Score {quality_score}")
            
            # Step 3: Chunk with format-aware strategy
            chunks = self.chunk(raw_content, job.format)
            
            # Step 4: Embed
            embeddings = await self.embedder.embed_batch(chunks)
            
            # Step 5: Write to index (atomic)
            await self.index_writer.upsert(
                doc_id=job.doc_id,
                chunks=chunks,
                embeddings=embeddings,
                metadata=job.metadata
            )
            
            # Step 6: Mark complete
            await self.mark_processed(idempotency_key)
            
        except RetryableError as e:
            await self.handle_retry(job, e)
        except NonRetryableError as e:
            await self.send_to_dlq(job, e)

    async def handle_retry(self, job: IngestionJob, error):
        if job.retry_count >= job.max_retries:
            await self.send_to_dlq(job, error)
            return
        
        delay = job.backoff_base ** job.retry_count
        job.retry_count += 1
        await self.queue.send(job, delay_seconds=delay)
```

**Format-Specific Parsing Strategy:**

| Format | Parser | Challenges | Strategy |
|--------|--------|-----------|----------|
| PDF | PyMuPDF + OCR fallback | Scanned docs, tables | Layout analysis → text extraction → OCR for images |
| DOCX | python-docx | Embedded objects | Recursive extraction of text + tables + images |
| HTML | BeautifulSoup + Readability | Boilerplate, JS content | Content extraction with boilerplate removal |
| Image | Tesseract + GPT-4V | Handwriting, diagrams | Multi-model OCR with confidence scoring |
| Audio | Whisper | Accents, noise | VAD → Whisper → speaker diarization |
| Code | Tree-sitter | Dependencies, context | AST parsing → semantic chunking by function/class |

**Production Considerations:**
- **Poison pill protection**: Jobs that crash workers 3x go to DLQ automatically
- **Backpressure**: Consumer pulls from queue; scale workers with queue depth metric
- **Checkpointing**: Multi-step jobs checkpoint after each stage so retries resume mid-pipeline
- **Resource isolation**: CPU-bound parsers (PDF/image) run on separate worker pool from I/O-bound ones
- **Observability**: Track per-format success rate, p99 processing time, DLQ depth by error category

---

## Q152: Design a CDC (Change Data Capture) pipeline that keeps a RAG index synchronized with source databases in near-real-time (< 1 minute lag). Include conflict resolution and schema evolution handling.

### Answer

**Architecture:**

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│  Source DBs  │     │  CDC Capture │     │  Stream Processor │
│              │     │              │     │                   │
│ PostgreSQL ──┼────▶│  Debezium    │────▶│  Flink/Kafka      │
│ MongoDB    ──┼────▶│  Connectors  │     │  Streams          │
│ MySQL      ──┼────▶│              │     │                   │
└──────────────┘     └──────────────┘     └────────┬──────────┘
                                                    │
                           ┌────────────────────────┼────────┐
                           ▼                        ▼        ▼
                    ┌─────────────┐    ┌──────────────┐  ┌──────┐
                    │  Transform  │    │  Conflict    │  │Schema│
                    │  & Embed    │    │  Resolver    │  │Regis │
                    └──────┬──────┘    └──────────────┘  └──────┘
                           │
                    ┌──────▼──────┐
                    │ Vector Index│
                    │ (Atomic     │
                    │  Upsert)    │
                    └─────────────┘
```

**CDC Implementation:**

```python
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime
import json

@dataclass
class CDCEvent:
    source_db: str
    table: str
    operation: str  # INSERT, UPDATE, DELETE
    before: Optional[dict]
    after: Optional[dict]
    timestamp: datetime
    lsn: int  # Log Sequence Number
    schema_version: int

class CDCToRAGSync:
    def __init__(self, schema_registry, embedder, vector_store, conflict_resolver):
        self.schema_registry = schema_registry
        self.embedder = embedder
        self.vector_store = vector_store
        self.conflict_resolver = conflict_resolver
        self.watermark_store = {}  # Track processing position
    
    async def process_event(self, event: CDCEvent):
        """Process CDC event with exactly-once delivery to vector index."""
        
        # 1. Schema evolution check
        current_schema = self.schema_registry.get(event.table, event.schema_version)
        if current_schema.has_breaking_change():
            await self.handle_schema_migration(event, current_schema)
            return
        
        # 2. Transform to document representation
        doc = self.transform(event, current_schema)
        
        # 3. Conflict resolution for concurrent updates
        if event.operation == "UPDATE":
            existing = await self.vector_store.get(doc.id)
            if existing and existing.version > event.lsn:
                # Stale event, skip (last-writer-wins by LSN)
                return
        
        # 4. Apply change to vector index
        if event.operation == "DELETE":
            await self.vector_store.delete(doc.id)
        else:
            embedding = await self.embedder.embed(doc.content)
            await self.vector_store.upsert(
                id=doc.id,
                vector=embedding,
                metadata=doc.metadata,
                version=event.lsn
            )
        
        # 5. Update watermark
        self.watermark_store[event.source_db] = event.lsn
    
    async def handle_schema_migration(self, event, new_schema):
        """Handle breaking schema changes without downtime."""
        migration = new_schema.get_migration()
        
        if migration.type == "FIELD_RENAME":
            # Re-map field names, no re-embedding needed
            await self.apply_metadata_migration(migration)
        elif migration.type == "CONTENT_FIELD_CHANGE":
            # Content changed — need full re-embedding of affected docs
            await self.trigger_backfill(event.table, new_schema)
        elif migration.type == "FIELD_ADDED":
            # Additive — just start including new field
            pass  # Forward compatible
    
    def transform(self, event: CDCEvent, schema) -> "Document":
        """Transform DB row to document for RAG indexing."""
        row = event.after
        
        # Build content from configured content fields
        content_fields = schema.get_content_fields()
        content = " ".join(str(row.get(f, "")) for f in content_fields)
        
        # Extract metadata fields
        metadata_fields = schema.get_metadata_fields()
        metadata = {f: row.get(f) for f in metadata_fields if row.get(f)}
        metadata["_source_table"] = event.table
        metadata["_source_db"] = event.source_db
        metadata["_updated_at"] = event.timestamp.isoformat()
        
        return Document(
            id=f"{event.source_db}:{event.table}:{row[schema.primary_key]}",
            content=content,
            metadata=metadata,
            version=event.lsn
        )
```

**Conflict Resolution Strategies:**

| Strategy | Use Case | Tradeoff |
|----------|----------|----------|
| Last-Writer-Wins (LSN) | Single-source tables | Simple but may lose updates |
| Vector Clock | Multi-master replication | Complex but preserves all writes |
| Merge Function | Aggregated documents | Domain-specific, most accurate |
| Tombstone + Rebuild | Rare conflicts | Expensive but always correct |

**Lag Monitoring:**

```python
class LagMonitor:
    def check_lag(self):
        for source, watermark in self.watermark_store.items():
            current_lsn = self.get_source_current_lsn(source)
            lag_events = current_lsn - watermark
            lag_time = self.estimate_time_lag(source, lag_events)
            
            if lag_time > timedelta(seconds=60):
                self.alert(f"CDC lag {source}: {lag_time}")
                self.scale_up_consumers(source)
```

**Production Considerations:**
- **Slot management**: PostgreSQL replication slots must be monitored to prevent WAL bloat
- **Backfill strategy**: Initial full sync via snapshot, then switch to CDC stream
- **Ordering guarantees**: Partition by primary key ensures per-record ordering
- **Monitoring**: Track replication lag, consumer lag, embedding latency, and index sync delay separately

---

## Q153: Design a web crawling and scraping pipeline for RAG that respects robots.txt, handles dynamic JavaScript-rendered content, deduplicates content, and maintains freshness.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Crawling Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────┐    ┌─────────────┐    ┌──────────────────┐   │
│  │  Seed     │───▶│  Frontier   │───▶│  Politeness      │   │
│  │  URLs     │    │  Manager    │    │  Controller      │   │
│  └───────────┘    │  (Priority  │    │  (robots.txt +   │   │
│                   │   Queue)    │    │   rate limits)   │   │
│                   └─────────────┘    └────────┬─────────┘   │
│                                               │              │
│                        ┌──────────────────────┘              │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Fetch Layer                               │   │
│  │  ┌────────────┐         ┌─────────────────────────┐  │   │
│  │  │ HTTP Fetch │         │ Headless Browser (JS)   │  │   │
│  │  │ (Static)   │         │ Playwright/Puppeteer    │  │   │
│  │  └────────────┘         └─────────────────────────┘  │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│  ┌───────────────────────────▼──────────────────────────┐   │
│  │  Post-Processing                                      │   │
│  │  Content Extract → Dedup → Diff → Chunk → Index      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import hashlib
import asyncio
from urllib.robotparser import RobotFileParser
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

@dataclass
class CrawlPolicy:
    max_depth: int = 3
    max_pages_per_domain: int = 10000
    recrawl_interval: timedelta = timedelta(hours=24)
    js_render_domains: set = None  # Domains requiring JS rendering
    respect_noindex: bool = True

class PolitenessController:
    def __init__(self):
        self.robots_cache: dict[str, RobotFileParser] = {}
        self.last_access: dict[str, datetime] = {}
        self.min_delay = timedelta(seconds=1)
    
    async def can_fetch(self, url: str, user_agent: str) -> bool:
        domain = self.extract_domain(url)
        robot = await self.get_robots(domain)
        return robot.can_fetch(user_agent, url)
    
    async def wait_for_politeness(self, domain: str):
        last = self.last_access.get(domain)
        if last:
            elapsed = datetime.utcnow() - last
            if elapsed < self.min_delay:
                await asyncio.sleep((self.min_delay - elapsed).total_seconds())
        self.last_access[domain] = datetime.utcnow()

class ContentDeduplicator:
    """Near-duplicate detection using SimHash + MinHash."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def compute_simhash(self, text: str) -> int:
        """64-bit SimHash for near-duplicate detection."""
        shingles = self.get_shingles(text, k=3)
        v = [0] * 64
        for shingle in shingles:
            h = int(hashlib.md5(shingle.encode()).hexdigest(), 16) & ((1 << 64) - 1)
            for i in range(64):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1
        return sum(1 << i for i in range(64) if v[i] > 0)
    
    def is_near_duplicate(self, simhash: int, threshold: int = 3) -> bool:
        """Check if content is within hamming distance threshold."""
        # Check against existing hashes in partitioned buckets
        for existing in self.get_candidates(simhash):
            if bin(simhash ^ existing).count('1') <= threshold:
                return True
        return False

class FreshnessManager:
    """Adaptive recrawl scheduling based on change frequency."""
    
    def __init__(self, url_store):
        self.url_store = url_store
    
    def compute_next_crawl(self, url: str) -> datetime:
        history = self.url_store.get_change_history(url)
        
        if not history:
            return datetime.utcnow() + timedelta(hours=24)
        
        # Adaptive: frequently changing pages get crawled more often
        change_rate = len([h for h in history if h.changed]) / len(history)
        
        if change_rate > 0.8:
            interval = timedelta(hours=1)
        elif change_rate > 0.4:
            interval = timedelta(hours=6)
        elif change_rate > 0.1:
            interval = timedelta(hours=24)
        else:
            interval = timedelta(days=7)
        
        return datetime.utcnow() + interval
    
    def detect_content_change(self, url: str, new_content: str) -> bool:
        """Detect meaningful content changes (not just ads/timestamps)."""
        old_hash = self.url_store.get_content_hash(url)
        # Extract main content, strip boilerplate
        main_content = self.extract_main_content(new_content)
        new_hash = hashlib.sha256(main_content.encode()).hexdigest()
        return old_hash != new_hash
```

**JS Rendering Decision Logic:**

| Signal | Action |
|--------|--------|
| Static HTML has `<noscript>` content | Try static first |
| Response body < 1KB with JS frameworks | Use headless browser |
| Domain in known SPA list | Always render JS |
| `X-Robots-Tag: noindex` after render | Respect and skip |
| Render timeout > 30s | Fall back to static |

**Production Considerations:**
- **Cost optimization**: Only 10-15% of pages need JS rendering; classify first with lightweight HEAD request
- **Distributed frontier**: Use Redis sorted set (priority) + Bloom filter (visited check) for URL frontier
- **Content diffing**: Store content hashes; only re-embed if meaningful content changed (ignore nav/footer)
- **Legal compliance**: Respect `robots.txt`, `Crawl-delay`, `nofollow`, and site terms of service
- **Monitoring**: Track crawl coverage, freshness SLA, duplicate rate, and error rate per domain

---

## Q154: Design an incremental indexing system that efficiently updates a vector index when documents change. Compare full re-indexing vs partial updates vs append-only with tombstones.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│                  Incremental Indexing System                     │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐   │
│  │  Change      │───▶│  Diff Engine    │───▶│  Strategy    │   │
│  │  Detector    │    │  (What changed?)│    │  Selector    │   │
│  └──────────────┘    └─────────────────┘    └──────┬───────┘   │
│                                                     │           │
│              ┌──────────────────┬───────────────────┼────┐      │
│              ▼                  ▼                    ▼    │      │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────┐  │      │
│  │  Full Rebuild  │  │  Partial Update │  │  Append  │  │      │
│  │  (Blue/Green)  │  │  (In-Place)     │  │  +Tomb   │  │      │
│  └────────────────┘  └─────────────────┘  └──────────┘  │      │
│              │                  │                    │    │      │
│              └──────────────────┴────────────────────┘    │      │
│                              │                            │      │
│                    ┌─────────▼──────────┐                │      │
│                    │  Index Swapper     │                │      │
│                    │  (Atomic Cutover)  │                │      │
│                    └───────────────────┘                 │      │
└────────────────────────────────────────────────────────────────┘
```

**Strategy Comparison:**

| Aspect | Full Re-Index | Partial Update | Append + Tombstone |
|--------|--------------|----------------|-------------------|
| Consistency | Perfect | Eventual | Eventual (with compaction) |
| Latency to reflect change | Hours | Seconds-Minutes | Seconds |
| Cost | High (re-embed all) | Medium (embed changed) | Low (embed new only) |
| Index quality | Optimal | Good | Degrades over time |
| Complexity | Low | High | Medium |
| Best for | Model changes, schema changes | Document edits | High-write workloads |

**Implementation:**

```python
from abc import ABC, abstractmethod
from typing import List, Set
from datetime import datetime, timedelta

class IndexUpdateStrategy(ABC):
    @abstractmethod
    async def apply_changes(self, changes: List["DocChange"]) -> None:
        pass

class PartialUpdateStrategy(IndexUpdateStrategy):
    """In-place update of changed vectors only."""
    
    def __init__(self, vector_store, embedder, chunk_differ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.chunk_differ = chunk_differ
    
    async def apply_changes(self, changes: List["DocChange"]):
        for change in changes:
            if change.type == "DELETE":
                # Remove all chunks for this document
                await self.vector_store.delete_by_filter(
                    {"doc_id": change.doc_id}
                )
            elif change.type == "UPDATE":
                await self.handle_update(change)
            elif change.type == "INSERT":
                await self.handle_insert(change)
    
    async def handle_update(self, change: "DocChange"):
        """Only re-embed chunks that actually changed."""
        old_chunks = await self.vector_store.get_chunks(change.doc_id)
        new_chunks = self.chunk_differ.chunk(change.new_content)
        
        # Diff at chunk level
        added, removed, modified = self.chunk_differ.diff(old_chunks, new_chunks)
        
        # Batch operations
        if removed:
            await self.vector_store.delete_many([c.id for c in removed])
        
        if added or modified:
            texts = [c.text for c in added + modified]
            embeddings = await self.embedder.embed_batch(texts)
            await self.vector_store.upsert_many(
                ids=[c.id for c in added + modified],
                vectors=embeddings,
                metadata=[c.metadata for c in added + modified]
            )

class AppendOnlyWithTombstones(IndexUpdateStrategy):
    """Append new versions, mark old as tombstoned. Periodic compaction."""
    
    def __init__(self, vector_store, embedder, compaction_threshold=0.3):
        self.vector_store = vector_store
        self.embedder = embedder
        self.tombstone_ratio_threshold = compaction_threshold
    
    async def apply_changes(self, changes: List["DocChange"]):
        for change in changes:
            # Mark old version as tombstoned (soft delete)
            await self.vector_store.update_metadata(
                filter={"doc_id": change.doc_id, "is_active": True},
                update={"is_active": False, "tombstoned_at": datetime.utcnow()}
            )
            
            if change.type != "DELETE":
                # Append new version
                chunks = self.chunk(change.new_content)
                embeddings = await self.embedder.embed_batch(
                    [c.text for c in chunks]
                )
                await self.vector_store.insert_many(
                    vectors=embeddings,
                    metadata=[{**c.metadata, "is_active": True, 
                              "version": change.version} for c in chunks]
                )
        
        # Check if compaction needed
        await self.maybe_compact()
    
    async def maybe_compact(self):
        stats = await self.vector_store.get_stats()
        tombstone_ratio = stats.tombstoned / stats.total
        
        if tombstone_ratio > self.tombstone_ratio_threshold:
            # Trigger background compaction (rebuild without tombstones)
            await self.trigger_compaction()

class AdaptiveStrategySelector:
    """Select strategy based on change characteristics."""
    
    def select(self, changes: List["DocChange"], index_stats: dict) -> IndexUpdateStrategy:
        change_ratio = len(changes) / index_stats["total_docs"]
        
        if change_ratio > 0.5:
            # More than 50% changed — full rebuild is cheaper
            return FullRebuildStrategy()
        elif index_stats.get("embedding_model_changed"):
            # Model changed — must re-embed everything
            return FullRebuildStrategy()
        elif change_ratio < 0.01 and index_stats["write_rate"] > 1000:
            # Few changes, high write rate — append is fastest
            return AppendOnlyWithTombstones()
        else:
            # Default: surgical partial updates
            return PartialUpdateStrategy()
```

**Production Considerations:**
- **Blue-green for full rebuilds**: Build new index in background, atomic swap via alias
- **Chunk-level diffing**: Use content hashing per chunk to avoid unnecessary re-embedding (saves 60-80% cost)
- **Compaction scheduling**: Run during off-peak hours; track tombstone ratio as metric
- **Version vectors**: Each chunk carries a version; queries filter `is_active=True` in metadata
- **Consistency window**: Document the lag between source change and index reflection in SLA

---

## Q155: Design a data validation and enrichment pipeline for RAG documents. Include entity extraction, classification, quality scoring, deduplication, and metadata enrichment before indexing.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│            Data Validation & Enrichment Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Raw Docs ──▶ ┌─────────┐ ──▶ ┌──────────┐ ──▶ ┌───────────┐  │
│               │Validate │     │ Enrich   │     │ Quality   │  │
│               │         │     │          │     │ Gate      │  │
│               └─────────┘     └──────────┘     └─────┬─────┘  │
│                                                       │         │
│  Stages:                                              ▼         │
│  1. Schema validation          ┌──────────────────────────┐    │
│  2. Content quality scoring    │  Enriched Document Store │    │
│  3. Deduplication              │  (Ready for Indexing)    │    │
│  4. Entity extraction          └──────────────────────────┘    │
│  5. Classification                                              │
│  6. Metadata enrichment                                         │
│  7. Final quality gate                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import re

@dataclass
class QualityScore:
    completeness: float    # 0-1: Are required fields present?
    readability: float     # 0-1: Is content coherent?
    informativeness: float # 0-1: Information density
    freshness: float       # 0-1: How current is the content?
    overall: float = 0.0
    
    def compute_overall(self, weights=None):
        w = weights or {"completeness": 0.3, "readability": 0.25,
                       "informativeness": 0.3, "freshness": 0.15}
        self.overall = sum(
            getattr(self, k) * v for k, v in w.items()
        )

class ValidationEnrichmentPipeline:
    def __init__(self, entity_extractor, classifier, deduplicator, quality_scorer):
        self.entity_extractor = entity_extractor
        self.classifier = classifier
        self.deduplicator = deduplicator
        self.quality_scorer = quality_scorer
        self.min_quality_threshold = 0.4
    
    async def process(self, doc: "RawDocument") -> Optional["EnrichedDocument"]:
        """Full validation and enrichment pipeline."""
        
        # Stage 1: Schema validation
        validation_errors = self.validate_schema(doc)
        if validation_errors:
            await self.report_validation_failure(doc, validation_errors)
            return None
        
        # Stage 2: Content quality scoring
        quality = await self.quality_scorer.score(doc)
        quality.compute_overall()
        
        if quality.overall < self.min_quality_threshold:
            await self.route_to_low_quality_review(doc, quality)
            return None
        
        # Stage 3: Deduplication
        dedup_result = await self.deduplicator.check(doc)
        if dedup_result.is_duplicate:
            if dedup_result.is_newer:
                # Replace existing with this newer version
                await self.deduplicator.mark_superseded(dedup_result.existing_id)
            else:
                return None  # Skip older duplicate
        
        # Stage 4: Entity extraction
        entities = await self.entity_extractor.extract(doc.content)
        
        # Stage 5: Classification
        categories = await self.classifier.classify(doc.content)
        
        # Stage 6: Metadata enrichment
        enriched_metadata = await self.enrich_metadata(doc, entities, categories)
        
        return EnrichedDocument(
            id=doc.id,
            content=doc.content,
            entities=entities,
            categories=categories,
            quality_score=quality,
            metadata=enriched_metadata,
            enrichment_version="v2.3"
        )
    
    def validate_schema(self, doc) -> List[str]:
        errors = []
        if not doc.content or len(doc.content.strip()) < 50:
            errors.append("Content too short (< 50 chars)")
        if not doc.source_url:
            errors.append("Missing source URL")
        if doc.language and doc.language not in self.supported_languages:
            errors.append(f"Unsupported language: {doc.language}")
        return errors
    
    async def enrich_metadata(self, doc, entities, categories) -> dict:
        """Add computed metadata for better retrieval."""
        return {
            **doc.metadata,
            "entities": [e.to_dict() for e in entities],
            "categories": categories,
            "word_count": len(doc.content.split()),
            "language": self.detect_language(doc.content),
            "reading_level": self.compute_reading_level(doc.content),
            "key_topics": self.extract_topics(entities, categories),
            "content_hash": self.hash_content(doc.content),
            "enrichment_timestamp": datetime.utcnow().isoformat(),
            "quality_tier": "high" if doc.quality_score > 0.8 else "standard",
        }

class EntityExtractor:
    """Multi-strategy entity extraction."""
    
    async def extract(self, text: str) -> List["Entity"]:
        # Run multiple extractors in parallel
        ner_entities = await self.spacy_ner(text)
        regex_entities = self.regex_extract(text)  # Dates, emails, URLs
        llm_entities = await self.llm_extract(text)  # Complex entities
        
        # Merge and deduplicate
        all_entities = self.merge_entities(ner_entities, regex_entities, llm_entities)
        
        # Resolve to canonical forms (e.g., "AWS" = "Amazon Web Services")
        resolved = await self.resolve_entities(all_entities)
        
        return resolved
```

**Quality Scoring Dimensions:**

| Dimension | Signal | Measurement |
|-----------|--------|-------------|
| Completeness | Required fields present, content length | Rule-based checks |
| Readability | Sentence structure, vocabulary | Flesch-Kincaid + LLM judge |
| Informativeness | Unique information density | TF-IDF uniqueness score |
| Freshness | Publication date, last modified | Time decay function |
| Accuracy | Factual consistency | Cross-reference with known facts |

**Production Considerations:**
- **Pipeline idempotency**: Same doc processed twice yields same enrichment (use content hash as cache key)
- **Enrichment versioning**: Track which enrichment pipeline version produced each result; allow re-enrichment on pipeline upgrade
- **Cost control**: Use lightweight models (spaCy) first; only call LLM for high-value documents or ambiguous cases
- **Quality feedback loop**: Track which quality tiers get clicked/used; adjust thresholds based on real usage data
- **Batch vs streaming**: Batch for initial load, streaming for incremental updates; same enrichment logic for both
# Data Architecture for AI Systems (Questions 156-160)

## Q156: Design the data architecture for an AI platform that needs to serve both real-time inference (low latency) and batch analytics (high throughput). Include the lakehouse approach with vector data.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   AI Lakehouse Architecture                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐     ┌──────────────────────────────────────────┐   │
│  │ Real-Time   │     │         Lakehouse (Delta/Iceberg)         │   │
│  │ Serving     │     │                                           │   │
│  │ Layer       │     │  ┌──────────┐  ┌────────┐  ┌──────────┐ │   │
│  │             │     │  │  Bronze  │─▶│ Silver │─▶│  Gold    │ │   │
│  │ ┌─────────┐│     │  │ (Raw)    │  │(Clean) │  │(Feature) │ │   │
│  │ │Vector DB││     │  └──────────┘  └────────┘  └──────────┘ │   │
│  │ │(Pinecone)││     │                                          │   │
│  │ └─────────┘│     │  ┌──────────────────────────────────┐    │   │
│  │ ┌─────────┐│     │  │  Vector Tables (Parquet+Index)   │    │   │
│  │ │Redis    ││     │  │  - Embeddings as array columns   │    │   │
│  │ │(Cache)  ││     │  │  - Metadata co-located           │    │   │
│  │ └─────────┘│     │  └──────────────────────────────────┘    │   │
│  │ ┌─────────┐│     └──────────────────────────────────────────┘   │
│  │ │Feature  ││                                                      │
│  │ │Store    ││     ┌──────────────────────────────────────────┐   │
│  │ └─────────┘│     │         Batch Processing Layer            │   │
│  └─────────────┘     │  Spark/Dask for training data prep       │   │
│                       │  Embedding batch jobs                    │   │
│                       │  Analytics & reporting                   │   │
│                       └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Dual-Path Data Flow:**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class AIDataArchitecture:
    """Unified data architecture serving real-time and batch."""
    
    def __init__(self):
        # Real-time path
        self.vector_store = PineconeClient()      # <10ms vector search
        self.feature_store = FeastClient()         # <5ms feature lookup
        self.cache = RedisClient()                 # <1ms cached results
        
        # Batch path
        self.lakehouse = DeltaLakeClient()         # High-throughput analytics
        self.spark = SparkSession.builder.getOrCreate()
    
    # --- Real-Time Path (p99 < 50ms) ---
    async def serve_inference(self, query: str, user_id: str) -> dict:
        # 1. Get user features (real-time)
        features = await self.feature_store.get_online_features(
            entity_key=user_id,
            feature_refs=["user:embedding_pref", "user:domain_weights"]
        )
        
        # 2. Vector search
        results = await self.vector_store.query(
            vector=await self.embed(query),
            filter=features.get("domain_weights"),
            top_k=10
        )
        
        # 3. Log to streaming layer (async, non-blocking)
        asyncio.create_task(self.log_to_stream(query, results, user_id))
        
        return results
    
    # --- Batch Path (throughput optimized) ---
    def run_batch_analytics(self):
        """Daily batch job: compute analytics, retrain models, refresh features."""
        
        # Read from lakehouse gold layer
        df = self.spark.read.format("delta").load("s3://lake/gold/interactions")
        
        # Compute batch features
        user_features = df.groupBy("user_id").agg(
            F.collect_list("query_embedding").alias("recent_embeddings"),
            F.avg("click_position").alias("avg_click_position"),
            F.count("*").alias("query_count")
        )
        
        # Write back to feature store (offline → online sync)
        self.feature_store.materialize_to_online(user_features)
        
        # Compute embedding analytics
        self.compute_embedding_drift(df)

class LakehouseVectorTable:
    """Store vectors in lakehouse for batch operations + analytics."""
    
    def create_vector_table(self):
        """Delta table schema for vectors alongside metadata."""
        return """
        CREATE TABLE vectors.documents (
            doc_id STRING,
            chunk_id STRING,
            content STRING,
            embedding ARRAY<FLOAT>,  -- 1536-dim stored as array
            metadata MAP<STRING, STRING>,
            created_at TIMESTAMP,
            source STRING,
            quality_score FLOAT
        )
        USING DELTA
        PARTITIONED BY (source, date(created_at))
        TBLPROPERTIES (
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true'
        )
        """
    
    def sync_to_vector_db(self):
        """Periodic sync from lakehouse (source of truth) to serving vector DB."""
        # Read latest vectors from gold layer
        new_vectors = self.spark.read.format("delta") \
            .option("readChangeFeed", "true") \
            .option("startingVersion", self.last_sync_version) \
            .load("s3://lake/gold/vectors")
        
        # Batch upsert to vector DB
        for batch in new_vectors.toLocalIterator():
            self.vector_store.upsert(batch)
```

**Data Layer Responsibilities:**

| Layer | Latency | Use Case | Storage |
|-------|---------|----------|---------|
| Cache (Redis) | <1ms | Repeated queries, hot docs | In-memory |
| Vector DB | <10ms | Similarity search at serving | Specialized (Pinecone/Weaviate) |
| Feature Store | <5ms | User/item features for ranking | Online: Redis, Offline: Parquet |
| Lakehouse Gold | Seconds | Ad-hoc analytics, dashboards | Delta Lake / Iceberg |
| Lakehouse Silver | Minutes | Clean data for training | Delta Lake / Iceberg |
| Lakehouse Bronze | N/A | Raw ingestion, audit trail | Delta Lake / Iceberg |

**Production Considerations:**
- **Single source of truth**: Lakehouse is canonical; vector DBs are derived materialized views
- **Time travel**: Delta/Iceberg time travel enables reproducing any past index state
- **Cost optimization**: Hot vectors in vector DB ($$$), warm in lakehouse ($$), cold in object storage ($)
- **Schema evolution**: Lakehouse handles schema changes; vector DB sync handles projection
- **Consistency model**: Eventual consistency between lakehouse and serving layer; track sync lag

---

## Q157: Design a data lineage and provenance tracking system for AI. Trace every piece of training data, every document in RAG, every model version back to its origin. Include GDPR deletion tracking.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│               Data Lineage & Provenance System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                    Lineage Graph (DAG)                      │   │
│  │                                                             │   │
│  │  [Raw Source] ──▶ [Transform] ──▶ [Dataset] ──▶ [Model]   │   │
│  │       │                │               │            │       │   │
│  │       ▼                ▼               ▼            ▼       │   │
│  │  [Provenance     [Parameters]    [Version]    [Deployment] │   │
│  │   Metadata]                                                 │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │  Lineage   │  │  GDPR        │  │  Audit Log             │   │
│  │  Store     │  │  Deletion    │  │  (Immutable)           │   │
│  │  (Neo4j)   │  │  Tracker     │  │                        │   │
│  └────────────┘  └──────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Optional, Set
from datetime import datetime
from enum import Enum
import uuid

class AssetType(Enum):
    RAW_SOURCE = "raw_source"
    DOCUMENT = "document"
    CHUNK = "chunk"
    EMBEDDING = "embedding"
    DATASET = "dataset"
    MODEL = "model"
    PREDICTION = "prediction"

@dataclass
class LineageNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: AssetType = AssetType.DOCUMENT
    name: str = ""
    version: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    data_subjects: Set[str] = field(default_factory=set)  # For GDPR
    
@dataclass 
class LineageEdge:
    source_id: str = ""
    target_id: str = ""
    operation: str = ""  # "chunked", "embedded", "trained_on", "fine_tuned"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    parameters: dict = field(default_factory=dict)

class LineageTracker:
    def __init__(self, graph_db, audit_log):
        self.graph = graph_db  # Neo4j
        self.audit = audit_log  # Immutable append-only
    
    def track_document_ingestion(self, source_url: str, doc_id: str, 
                                  chunks: List[str], embeddings: List[str]):
        """Track full lineage from source to indexed embeddings."""
        
        # Create source node
        source = LineageNode(
            asset_type=AssetType.RAW_SOURCE,
            name=source_url,
            metadata={"fetched_at": datetime.utcnow().isoformat()}
        )
        
        # Create document node
        doc = LineageNode(
            asset_type=AssetType.DOCUMENT,
            name=doc_id,
            version="1.0"
        )
        
        # Track transformation
        self.graph.add_edge(LineageEdge(
            source_id=source.id, target_id=doc.id,
            operation="ingested",
            parameters={"parser": "pdf_v2", "date": str(datetime.utcnow())}
        ))
        
        # Track chunking
        for chunk_id in chunks:
            chunk = LineageNode(asset_type=AssetType.CHUNK, name=chunk_id)
            self.graph.add_edge(LineageEdge(
                source_id=doc.id, target_id=chunk.id,
                operation="chunked",
                parameters={"strategy": "semantic", "max_tokens": 512}
            ))
        
        # Track embedding
        for chunk_id, emb_id in zip(chunks, embeddings):
            emb = LineageNode(asset_type=AssetType.EMBEDDING, name=emb_id)
            self.graph.add_edge(LineageEdge(
                source_id=chunk_id, target_id=emb.id,
                operation="embedded",
                parameters={"model": "text-embedding-3-large", "dim": 1536}
            ))
    
    def trace_prediction_lineage(self, prediction_id: str) -> dict:
        """Given a prediction, trace back to all source data."""
        query = """
        MATCH path = (p:Prediction {id: $pred_id})<-[:GENERATED*]-(source)
        RETURN path
        """
        return self.graph.query(query, pred_id=prediction_id)

class GDPRDeletionTracker:
    """Track and execute right-to-deletion across AI pipeline."""
    
    def __init__(self, lineage_tracker, vector_store, model_registry):
        self.lineage = lineage_tracker
        self.vector_store = vector_store
        self.model_registry = model_registry
    
    async def process_deletion_request(self, data_subject_id: str) -> "DeletionReport":
        """GDPR Article 17: Right to erasure."""
        
        # 1. Find all assets containing this data subject
        affected_assets = self.lineage.find_by_data_subject(data_subject_id)
        
        report = DeletionReport(subject_id=data_subject_id)
        
        for asset in affected_assets:
            if asset.asset_type == AssetType.DOCUMENT:
                await self.vector_store.delete(asset.id)
                report.deleted_documents.append(asset.id)
                
            elif asset.asset_type == AssetType.EMBEDDING:
                await self.vector_store.delete_vector(asset.id)
                report.deleted_embeddings.append(asset.id)
                
            elif asset.asset_type == AssetType.MODEL:
                # Cannot delete from trained model — mark for retraining
                report.models_requiring_retrain.append(asset.id)
                await self.model_registry.mark_tainted(
                    asset.id, reason=f"GDPR deletion: {data_subject_id}"
                )
            
            elif asset.asset_type == AssetType.DATASET:
                # Remove rows and track
                await self.remove_from_dataset(asset.id, data_subject_id)
                report.cleaned_datasets.append(asset.id)
        
        # 2. Log deletion (audit requirement)
        self.lineage.audit.log(
            event="gdpr_deletion",
            subject=data_subject_id,
            report=report.to_dict()
        )
        
        return report
```

**Production Considerations:**
- **Performance**: Lineage writes are async and non-blocking to the main data path
- **Storage**: Graph DB for relationships; object store for large metadata payloads
- **Retention**: Lineage metadata kept longer than data itself (for compliance proof)
- **Machine unlearning**: For models trained on deleted data, track "tainted" models and schedule retraining
- **Query patterns**: "What data trained model X?" and "What models used document Y?" must both be fast

---

## Q158: Design a feature engineering pipeline for RAG that computes and serves real-time features (user behavior, content freshness, popularity signals) alongside vector similarity for better ranking.

### Answer

**Architecture:**

```
┌──────────────────────────────────────────────────────────────────┐
│           Feature Engineering Pipeline for RAG                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌──────────────────────────────────────────┐    │
│  │  Query   │───▶│          Retrieval + Ranking              │    │
│  └──────────┘    │                                           │    │
│                   │  1. Vector Similarity (embedding match)   │    │
│                   │  2. Real-time Features (user signals)     │    │
│                   │  3. Content Features (freshness, quality) │    │
│                   │  4. Learned Ranker (combines all)         │    │
│                   └──────────────────────────────────────────┘    │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                Feature Computation Layers                   │  │
│  │                                                              │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │  │
│  │  │ Streaming   │  │  Batch       │  │  On-Demand      │   │  │
│  │  │ Features    │  │  Features    │  │  Features       │   │  │
│  │  │             │  │              │  │                  │   │  │
│  │  │ - Click CTR │  │ - Popularity │  │ - Query-Doc     │   │  │
│  │  │ - Recency   │  │ - PageRank   │  │   relevance     │   │  │
│  │  │ - Session   │  │ - Topic dist │  │ - Cross-encoder │   │  │
│  │  │   context   │  │ - Quality    │  │   score         │   │  │
│  │  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │  │
│  │         └─────────────────┴───────────────────┘             │  │
│  │                           │                                  │  │
│  │                  ┌────────▼────────┐                        │  │
│  │                  │  Feature Store  │                        │  │
│  │                  │  (Online+Offline)│                        │  │
│  │                  └─────────────────┘                        │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from typing import List, Dict
import time

@dataclass
class FeatureVector:
    vector_similarity: float
    freshness_score: float
    popularity_score: float
    user_affinity: float
    quality_score: float
    click_through_rate: float
    session_relevance: float
    cross_encoder_score: float

class RAGFeaturePipeline:
    def __init__(self, feature_store, stream_processor, ranker):
        self.feature_store = feature_store
        self.stream = stream_processor
        self.ranker = ranker  # Learned ranking model (LambdaMART / neural)
    
    async def retrieve_and_rank(self, query: str, user_id: str, 
                                 session: "Session") -> List[dict]:
        """Two-stage: retrieve by vector, re-rank with features."""
        
        # Stage 1: Retrieve candidates (vector similarity)
        query_embedding = await self.embed(query)
        candidates = await self.vector_store.query(query_embedding, top_k=100)
        
        # Stage 2: Compute features for each candidate
        doc_ids = [c.id for c in candidates]
        
        # Batch fetch pre-computed features
        batch_features = await self.feature_store.get_online_features(
            entity_keys=doc_ids,
            feature_refs=[
                "doc:popularity_7d", "doc:quality_score",
                "doc:freshness_hours", "doc:click_rate"
            ]
        )
        
        # Compute real-time features
        user_features = await self.compute_user_features(user_id, session)
        
        # Build feature vectors for ranking
        feature_vectors = []
        for i, candidate in enumerate(candidates):
            fv = FeatureVector(
                vector_similarity=candidate.score,
                freshness_score=self.time_decay(batch_features[i]["freshness_hours"]),
                popularity_score=batch_features[i]["popularity_7d"],
                user_affinity=self.compute_affinity(user_features, candidate),
                quality_score=batch_features[i]["quality_score"],
                click_through_rate=batch_features[i]["click_rate"],
                session_relevance=self.session_relevance(session, candidate),
                cross_encoder_score=0.0  # Computed below for top candidates
            )
            feature_vectors.append(fv)
        
        # Stage 3: Expensive cross-encoder only on top-20
        top_20_indices = sorted(range(len(feature_vectors)), 
                                key=lambda i: feature_vectors[i].vector_similarity,
                                reverse=True)[:20]
        
        cross_scores = await self.cross_encoder.score_batch(
            query, [candidates[i].content for i in top_20_indices]
        )
        for idx, score in zip(top_20_indices, cross_scores):
            feature_vectors[idx].cross_encoder_score = score
        
        # Stage 4: Learned ranker combines all features
        final_scores = self.ranker.predict(feature_vectors)
        
        ranked = sorted(zip(candidates, final_scores), 
                       key=lambda x: x[1], reverse=True)
        return ranked[:10]
    
    def time_decay(self, hours_old: float) -> float:
        """Exponential decay with half-life of 7 days."""
        half_life = 7 * 24
        return 2 ** (-hours_old / half_life)

class StreamingFeatureComputer:
    """Compute real-time features from event stream."""
    
    def __init__(self, flink_env):
        self.env = flink_env
    
    def define_streaming_features(self):
        """Flink job for real-time feature computation."""
        # Click-through rate (sliding window)
        self.env.sql("""
            INSERT INTO feature_store.doc_click_rate
            SELECT 
                doc_id,
                COUNT(CASE WHEN event='click' THEN 1 END) / 
                    NULLIF(COUNT(CASE WHEN event='impression' THEN 1 END), 0) as ctr,
                TUMBLE_END(event_time, INTERVAL '1' HOUR) as window_end
            FROM events
            GROUP BY doc_id, TUMBLE(event_time, INTERVAL '1' HOUR)
        """)
```

**Feature Categories:**

| Category | Features | Computation | Latency |
|----------|----------|-------------|---------|
| Query-Doc | Vector similarity, BM25, cross-encoder | On-demand | 5-50ms |
| Document | Quality, freshness, length, readability | Batch (hourly) | <1ms lookup |
| User | Preferences, history, expertise level | Streaming + batch | <5ms lookup |
| Interaction | CTR, dwell time, bounce rate | Streaming (1min window) | <5ms lookup |
| Session | Recent queries, clicked docs, topic drift | On-demand | 2ms |

**Production Considerations:**
- **Feature freshness SLAs**: Streaming features < 1 minute, batch features < 1 hour
- **Feature monitoring**: Track feature distribution drift; alert on sudden changes
- **Ranker training**: Use logged implicit feedback (clicks, dwell) with position debiasing
- **Fallback**: If feature store is down, fall back to vector similarity only (graceful degradation)
- **A/B testing**: Compare vector-only vs feature-enhanced ranking; measure NDCG@10 improvement

---

## Q159: Design a data versioning system for AI applications. How do you version training datasets, evaluation sets, document corpora, and embedding indices so you can reproduce any past state?

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                   Data Versioning System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                  Version Control Layer                      │   │
│  │                                                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ Dataset  │  │ Eval Set │  │ Corpus   │  │ Index    │ │   │
│  │  │ v1.2.3   │  │ v2.0.1   │  │ v5.4.0   │  │ v3.1.0   │ │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │   │
│  │       └──────────────┴─────────────┴──────────────┘        │   │
│  │                          │                                  │   │
│  │              ┌───────────▼────────────┐                    │   │
│  │              │  Snapshot Manifest     │                    │   │
│  │              │  (Points-in-time)      │                    │   │
│  │              └───────────────────────┘                    │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                  Storage Layer                              │   │
│  │                                                             │   │
│  │  Object Store (S3) ─── Content-Addressed (dedup) ───       │   │
│  │  Delta Lake ─── Time Travel ─── Schema Evolution ───       │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class DataVersion:
    version: str           # Semantic version
    created_at: datetime = field(default_factory=datetime.utcnow)
    parent_version: Optional[str] = None
    content_hash: str = ""
    manifest: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
@dataclass
class Snapshot:
    """Point-in-time snapshot of entire AI system state."""
    snapshot_id: str
    timestamp: datetime
    components: Dict[str, str]  # component_name -> version
    # e.g., {"training_data": "v1.2.3", "eval_set": "v2.0.1", 
    #         "corpus": "v5.4.0", "embedding_model": "v3.1.0",
    #         "index": "v3.1.0", "prompts": "v1.5.0"}

class DataVersioningSystem:
    def __init__(self, storage_backend, metadata_db):
        self.storage = storage_backend  # Content-addressed store
        self.metadata = metadata_db
    
    def commit_dataset_version(self, dataset_name: str, 
                                data_path: str, 
                                message: str) -> DataVersion:
        """Commit a new version of a dataset (like git commit for data)."""
        
        # 1. Compute content hash (Merkle tree over files)
        content_hash = self.compute_merkle_hash(data_path)
        
        # 2. Check if this exact content already exists (dedup)
        existing = self.metadata.find_by_hash(dataset_name, content_hash)
        if existing:
            return existing  # No change, return existing version
        
        # 3. Compute diff from parent (for storage efficiency)
        parent = self.metadata.get_latest(dataset_name)
        if parent:
            diff = self.compute_diff(parent.content_hash, content_hash)
            self.storage.store_diff(content_hash, diff)
        else:
            self.storage.store_full(content_hash, data_path)
        
        # 4. Create version record
        new_version = self.bump_version(parent)
        version = DataVersion(
            version=new_version,
            parent_version=parent.version if parent else None,
            content_hash=content_hash,
            manifest=self.build_manifest(data_path),
            metadata={
                "message": message,
                "file_count": self.count_files(data_path),
                "total_size_bytes": self.compute_size(data_path),
                "schema_hash": self.compute_schema_hash(data_path)
            }
        )
        
        self.metadata.save(dataset_name, version)
        return version
    
    def checkout(self, dataset_name: str, version: str) -> str:
        """Restore a specific version to a local path."""
        ver = self.metadata.get(dataset_name, version)
        
        # Reconstruct from content-addressed store
        local_path = f"/tmp/data/{dataset_name}/{version}"
        self.storage.restore(ver.content_hash, local_path)
        
        return local_path
    
    def create_snapshot(self, name: str) -> Snapshot:
        """Capture current state of all components."""
        components = {}
        for component in self.metadata.list_all_datasets():
            latest = self.metadata.get_latest(component)
            components[component] = latest.version
        
        snapshot = Snapshot(
            snapshot_id=name,
            timestamp=datetime.utcnow(),
            components=components
        )
        self.metadata.save_snapshot(snapshot)
        return snapshot
    
    def reproduce(self, snapshot_id: str) -> Dict[str, str]:
        """Restore entire system to a past snapshot state."""
        snapshot = self.metadata.get_snapshot(snapshot_id)
        restored_paths = {}
        
        for component, version in snapshot.components.items():
            path = self.checkout(component, version)
            restored_paths[component] = path
        
        return restored_paths
    
    def compute_merkle_hash(self, data_path: str) -> str:
        """Content-addressed hashing for efficient dedup and diffing."""
        # Hash each file, then hash the sorted list of hashes
        file_hashes = []
        for file in sorted(self.list_files(data_path)):
            with open(file, 'rb') as f:
                file_hashes.append(hashlib.sha256(f.read()).hexdigest())
        
        return hashlib.sha256(
            json.dumps(file_hashes).encode()
        ).hexdigest()
```

**Versioning Strategies by Asset Type:**

| Asset | Strategy | Storage | Diff Method |
|-------|----------|---------|-------------|
| Training datasets | Content-addressed + Delta | S3 + DeltaLake | Row-level diff |
| Eval sets | Git-like snapshots | S3 | Full snapshot (small) |
| Document corpus | Incremental + manifest | S3 + manifest DB | File-level add/remove |
| Embedding index | Snapshot + rebuild recipe | S3 (binary) | Store recipe, not index |
| Prompts | Git (text files) | Git repo | Line diff |

**Production Considerations:**
- **Storage efficiency**: Content-addressed storage deduplicates identical files across versions (typically 80% overlap between versions)
- **Index reproducibility**: Store `(corpus_version, model_version, chunking_config)` tuple; rebuild index from these inputs rather than storing binary index
- **Garbage collection**: Versions older than retention policy get GC'd; pinned versions (used in production) never GC'd
- **Branching**: Support branches for experiments (like git branches for data)
- **Integration with MLflow/W&B**: Link data versions to experiment runs for full reproducibility

---

## Q160: Design a data mesh architecture for AI where different domains own their data but expose it for AI applications through standardized contracts. Include data quality SLAs and discovery.

### Answer

**Architecture:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Data Mesh for AI Platform                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Customer    │  │  Product     │  │  Support     │               │
│  │  Domain      │  │  Domain      │  │  Domain      │               │
│  │              │  │              │  │              │               │
│  │ ┌──────────┐│  │ ┌──────────┐│  │ ┌──────────┐│               │
│  │ │Data      ││  │ │Data      ││  │ │Data      ││               │
│  │ │Product   ││  │ │Product   ││  │ │Product   ││               │
│  │ │(API+SLA) ││  │ │(API+SLA) ││  │ │(API+SLA) ││               │
│  │ └────┬─────┘│  │ └────┬─────┘│  │ └────┬─────┘│               │
│  └──────┼───────┘  └──────┼───────┘  └──────┼───────┘               │
│          └─────────────────┼─────────────────┘                        │
│                            │                                          │
│  ┌─────────────────────────▼──────────────────────────────────────┐  │
│  │              Federated AI Platform Layer                         │  │
│  │                                                                  │  │
│  │  ┌────────────┐  ┌────────────────┐  ┌───────────────────┐    │  │
│  │  │ Data       │  │ Quality        │  │ Self-Serve        │    │  │
│  │  │ Catalog    │  │ Monitor        │  │ AI Infrastructure │    │  │
│  │  │ (Discovery)│  │ (SLA Enforce)  │  │ (Templates)       │    │  │
│  │  └────────────┘  └────────────────┘  └───────────────────┘    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

class QualityTier(Enum):
    GOLD = "gold"       # 99.9% freshness, 99.99% accuracy
    SILVER = "silver"   # 99% freshness, 99.9% accuracy  
    BRONZE = "bronze"   # Best-effort

@dataclass
class DataContract:
    """Standardized contract between data domain and AI consumers."""
    domain: str
    product_name: str
    version: str
    schema: dict                    # JSON Schema or Avro
    quality_sla: "QualitySLA"
    access_pattern: str             # "batch", "streaming", "request-response"
    freshness_guarantee: timedelta
    retention: timedelta
    owner_team: str
    
    # AI-specific contract fields
    embedding_ready: bool = False    # Pre-embedded available?
    chunking_hints: dict = field(default_factory=dict)  # Suggested chunking
    entity_annotations: bool = False  # Entities pre-extracted?
    pii_classification: dict = field(default_factory=dict)

@dataclass
class QualitySLA:
    completeness: float   # % of required fields non-null
    accuracy: float       # % of values validated correct
    freshness: timedelta  # Max age of data
    availability: float   # % uptime of data product API
    
    # Penalties
    breach_notification: timedelta = timedelta(minutes=5)
    auto_fallback: bool = True  # Use cached version on breach

class DataProductRegistry:
    """Central catalog for discovering domain data products."""
    
    def __init__(self, catalog_db, quality_monitor):
        self.catalog = catalog_db
        self.quality = quality_monitor
    
    def register_data_product(self, contract: DataContract):
        """Domain team registers their data product."""
        # Validate contract completeness
        self.validate_contract(contract)
        
        # Register in catalog
        self.catalog.upsert(contract)
        
        # Set up quality monitoring
        self.quality.create_monitors(contract)
        
        # Auto-generate consumer SDK
        self.generate_client_sdk(contract)
    
    def discover_for_ai(self, query: str, use_case: str) -> List[DataContract]:
        """AI teams discover relevant data products."""
        results = self.catalog.semantic_search(
            query=query,
            filters={
                "embedding_ready": True,
                "quality_tier": ["gold", "silver"]
            }
        )
        
        # Rank by relevance to use case
        ranked = self.rank_for_use_case(results, use_case)
        return ranked
    
    def check_sla_compliance(self, domain: str, product: str) -> dict:
        """Real-time SLA compliance check."""
        contract = self.catalog.get(domain, product)
        metrics = self.quality.get_metrics(domain, product)
        
        return {
            "completeness": {
                "sla": contract.quality_sla.completeness,
                "actual": metrics.completeness,
                "compliant": metrics.completeness >= contract.quality_sla.completeness
            },
            "freshness": {
                "sla": str(contract.quality_sla.freshness),
                "actual": str(metrics.max_lag),
                "compliant": metrics.max_lag <= contract.quality_sla.freshness
            },
            "availability": {
                "sla": contract.quality_sla.availability,
                "actual": metrics.availability_30d,
                "compliant": metrics.availability_30d >= contract.quality_sla.availability
            }
        }

class DomainDataProduct:
    """Template for domain teams to expose data for AI consumption."""
    
    def __init__(self, domain: str, product_name: str):
        self.domain = domain
        self.product_name = product_name
    
    def expose_for_rag(self, table_name: str, config: dict):
        """Expose domain data as RAG-ready data product."""
        
        # Define output port for AI consumption
        output_port = {
            "format": "parquet",
            "schema": self.generate_rag_schema(table_name),
            "partitioning": ["date", "category"],
            "update_frequency": config.get("frequency", "hourly"),
            
            # AI-specific enrichments the domain provides
            "enrichments": {
                "pre_chunked": True,
                "chunk_strategy": "semantic_paragraphs",
                "entities_extracted": True,
                "language_detected": True,
                "pii_redacted": True
            }
        }
        
        # Domain owns the transformation pipeline
        pipeline = self.create_transformation_pipeline(table_name, output_port)
        
        # Register contract
        contract = DataContract(
            domain=self.domain,
            product_name=self.product_name,
            version="1.0.0",
            schema=output_port["schema"],
            quality_sla=QualitySLA(
                completeness=0.99,
                accuracy=0.999,
                freshness=timedelta(hours=1),
                availability=0.999
            ),
            access_pattern="batch",
            freshness_guarantee=timedelta(hours=1),
            retention=timedelta(days=365),
            owner_team=f"{self.domain}-data-team",
            embedding_ready=True
        )
        
        return contract
```

**Data Mesh Principles Applied to AI:**

| Principle | Implementation |
|-----------|---------------|
| Domain Ownership | Each team owns their data-to-embedding pipeline |
| Data as Product | Standardized contracts with AI-specific fields |
| Self-Serve Platform | Templates for RAG-ready data products |
| Federated Governance | Central quality monitoring, decentralized execution |

**Production Considerations:**
- **Contract versioning**: Semantic versioning for schemas; consumers pin to major version
- **Quality gates**: Data products that breach SLA automatically fall back to last-known-good snapshot
- **Cross-domain joins**: AI platform provides federated query layer for joining across domains
- **Incentive alignment**: Domain teams see consumption metrics (who uses their data, for what)
- **Migration path**: Start with one domain, prove value, then expand; don't boil the ocean
# Multi-Tenancy and Data Isolation (Questions 161-165)

## Q161: Design a multi-tenant embedding and vector storage system that provides cryptographic isolation between tenants while sharing infrastructure. Compare namespace isolation vs collection isolation vs encryption-based isolation.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│            Multi-Tenant Vector Storage Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Tenant Routing Layer                         │    │
│  │  Request → Auth → Tenant ID → Isolation Strategy         │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                            │                                     │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │         Isolation Strategy (Per-Tier)                      │   │
│  │                                                            │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │   │
│  │  │  Namespace   │ │  Collection  │ │  Encryption-     │  │   │
│  │  │  Isolation   │ │  Isolation   │ │  Based Isolation │  │   │
│  │  │  (Standard)  │ │  (Premium)   │ │  (Enterprise)    │  │   │
│  │  │              │ │              │ │                   │  │   │
│  │  │ Shared index │ │ Separate     │ │ Shared infra +   │  │   │
│  │  │ + metadata   │ │ collections  │ │ per-tenant KEK   │  │   │
│  │  │ filter       │ │ per tenant   │ │ + envelope enc   │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘  │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Comparison Table:**

| Aspect | Namespace (Filter) | Collection Isolation | Encryption-Based |
|--------|-------------------|---------------------|-----------------|
| Isolation strength | Logical (software) | Physical (data) | Cryptographic |
| Performance | Slight overhead (filter) | Optimal per-tenant | 10-15% overhead |
| Cost efficiency | Highest (shared) | Medium (N collections) | High (shared + crypto) |
| Compliance | SOC2 | SOC2, HIPAA | FedRAMP, ITAR |
| Cross-tenant leak risk | Bug in filter logic | Misconfigured routing | Key compromise only |
| Scale limit | Millions of tenants | ~10K collections | Millions of tenants |
| Index optimization | Shared HNSW (larger=better) | Per-tenant HNSW (smaller) | Shared HNSW |

**Implementation:**

```python
from abc import ABC, abstractmethod
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class TenantIsolationStrategy(ABC):
    @abstractmethod
    async def store(self, tenant_id: str, vectors: list, metadata: list):
        pass
    
    @abstractmethod
    async def query(self, tenant_id: str, vector: list, top_k: int):
        pass

class NamespaceIsolation(TenantIsolationStrategy):
    """Shared index with tenant_id metadata filter."""
    
    def __init__(self, vector_store):
        self.store = vector_store  # Single shared collection
    
    async def store(self, tenant_id: str, vectors: list, metadata: list):
        # Inject tenant_id into every vector's metadata
        for m in metadata:
            m["_tenant_id"] = tenant_id
        await self.store.upsert(vectors=vectors, metadata=metadata)
    
    async def query(self, tenant_id: str, vector: list, top_k: int):
        # CRITICAL: Always filter by tenant_id
        return await self.store.query(
            vector=vector,
            top_k=top_k,
            filter={"_tenant_id": {"$eq": tenant_id}}  # Mandatory filter
        )

class CollectionIsolation(TenantIsolationStrategy):
    """Separate collection per tenant."""
    
    def __init__(self, vector_store_factory):
        self.factory = vector_store_factory
        self.collections = {}
    
    async def get_collection(self, tenant_id: str):
        if tenant_id not in self.collections:
            self.collections[tenant_id] = await self.factory.create(
                name=f"tenant_{tenant_id}",
                config=self.get_tenant_config(tenant_id)
            )
        return self.collections[tenant_id]
    
    async def store(self, tenant_id: str, vectors: list, metadata: list):
        collection = await self.get_collection(tenant_id)
        await collection.upsert(vectors=vectors, metadata=metadata)
    
    async def query(self, tenant_id: str, vector: list, top_k: int):
        collection = await self.get_collection(tenant_id)
        return await collection.query(vector=vector, top_k=top_k)

class EncryptionBasedIsolation(TenantIsolationStrategy):
    """Shared infra with per-tenant encryption keys (envelope encryption)."""
    
    def __init__(self, vector_store, kms_client):
        self.store = vector_store
        self.kms = kms_client
    
    async def get_tenant_key(self, tenant_id: str) -> bytes:
        """Retrieve or generate tenant-specific data encryption key."""
        # KMS manages key hierarchy: Master Key → Tenant KEK → DEK
        dek = await self.kms.get_data_key(
            key_id=f"tenant/{tenant_id}/vector-key",
            context={"tenant": tenant_id, "purpose": "vector-encryption"}
        )
        return dek
    
    async def store(self, tenant_id: str, vectors: list, metadata: list):
        key = await self.get_tenant_key(tenant_id)
        
        # Encrypt metadata (vectors stored plain for similarity search)
        encrypted_metadata = []
        for m in metadata:
            enc_m = self.encrypt_metadata(m, key)
            enc_m["_tenant_id"] = tenant_id  # Unencrypted for filtering
            encrypted_metadata.append(enc_m)
        
        await self.store.upsert(vectors=vectors, metadata=encrypted_metadata)
    
    async def query(self, tenant_id: str, vector: list, top_k: int):
        # Query with tenant filter
        results = await self.store.query(
            vector=vector, top_k=top_k,
            filter={"_tenant_id": {"$eq": tenant_id}}
        )
        
        # Decrypt metadata with tenant key
        key = await self.get_tenant_key(tenant_id)
        for r in results:
            r.metadata = self.decrypt_metadata(r.metadata, key)
        
        return results
    
    def encrypt_metadata(self, metadata: dict, key: bytes) -> dict:
        """Encrypt sensitive metadata fields."""
        fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
        sensitive_fields = {k: v for k, v in metadata.items() if k != "_tenant_id"}
        encrypted = fernet.encrypt(json.dumps(sensitive_fields).encode())
        return {"_encrypted_payload": encrypted.decode()}
```

**Production Considerations:**
- **Defense in depth**: Even with encryption, always apply tenant_id filter as secondary guard
- **Key rotation**: Support key rotation without re-encrypting all vectors (use envelope encryption with rotatable KEK)
- **Audit logging**: Log every cross-tenant access attempt (even failed ones) for security review
- **Testing**: Automated pen tests that attempt cross-tenant data access on every deployment
- **Performance**: Namespace isolation adds ~5% latency; encryption adds ~15%; benchmark per use case

---

## Q162: Design a noisy neighbor prevention system for a shared AI platform. One tenant's expensive queries shouldn't impact others' latency. Include resource quotas, fair scheduling, and quality of service enforcement.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Noisy Neighbor Prevention System                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Admission Control                           │  │
│  │  Request → Rate Limit → Quota Check → Priority Queue        │  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                                │                                  │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │              Fair Scheduler (Weighted Fair Queue)            │  │
│  │                                                              │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │  │
│  │  │Tenant A │  │Tenant B │  │Tenant C │  │Tenant D │      │  │
│  │  │Weight:4 │  │Weight:2 │  │Weight:1 │  │Weight:1 │      │  │
│  │  │(Prem)   │  │(Std)    │  │(Free)   │  │(Free)   │      │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘      │  │
│  │       └─────────────┴────────────┴─────────────┘            │  │
│  │                          │                                   │  │
│  └──────────────────────────┼───────────────────────────────────┘  │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │           Resource Pools (Isolated Compute)                │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐  │   │
│  │  │ Premium  │  │  Standard    │  │  Burst (Overflow)  │  │   │
│  │  │ Pool     │  │  Pool        │  │  Pool              │  │   │
│  │  │ (GPU×8)  │  │  (GPU×16)    │  │  (Auto-scale)     │  │   │
│  │  └──────────┘  └──────────────┘  └────────────────────┘  │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional
from collections import defaultdict

@dataclass
class TenantQuota:
    requests_per_second: float = 100.0
    tokens_per_minute: int = 100_000
    max_concurrent_requests: int = 50
    max_vector_results: int = 1000
    max_query_complexity: float = 1.0  # Normalized cost
    burst_allowance: float = 1.5       # 1.5x burst for short periods
    priority_weight: int = 1           # Higher = more share

class TokenBucket:
    """Token bucket rate limiter with burst support."""
    
    def __init__(self, rate: float, burst: float):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.monotonic()
    
    def try_acquire(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class NoisyNeighborPrevention:
    def __init__(self, quota_store, metrics):
        self.quotas: Dict[str, TenantQuota] = {}
        self.rate_limiters: Dict[str, TokenBucket] = {}
        self.concurrent: Dict[str, int] = defaultdict(int)
        self.metrics = metrics
    
    async def admit_request(self, tenant_id: str, request: "AIRequest") -> "AdmissionResult":
        quota = self.get_quota(tenant_id)
        
        # 1. Rate limit check
        limiter = self.get_rate_limiter(tenant_id, quota)
        if not limiter.try_acquire(request.estimated_cost):
            self.metrics.increment("rate_limited", tenant=tenant_id)
            return AdmissionResult(
                admitted=False,
                reason="rate_limit_exceeded",
                retry_after=1.0 / quota.requests_per_second
            )
        
        # 2. Concurrency limit
        if self.concurrent[tenant_id] >= quota.max_concurrent_requests:
            return AdmissionResult(
                admitted=False,
                reason="concurrency_limit",
                retry_after=0.1
            )
        
        # 3. Token budget (LLM tokens)
        if not await self.check_token_budget(tenant_id, request.estimated_tokens):
            return AdmissionResult(
                admitted=False,
                reason="token_budget_exhausted",
                retry_after=60.0
            )
        
        # 4. Complexity check (prevent expensive queries)
        complexity = self.estimate_complexity(request)
        if complexity > quota.max_query_complexity:
            return AdmissionResult(
                admitted=False,
                reason="query_too_complex",
                suggestion="Reduce top_k or simplify filters"
            )
        
        self.concurrent[tenant_id] += 1
        return AdmissionResult(admitted=True, priority=quota.priority_weight)
    
    def release_request(self, tenant_id: str):
        self.concurrent[tenant_id] -= 1

class WeightedFairScheduler:
    """Deficit round-robin scheduler for fair resource allocation."""
    
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.deficits: Dict[str, float] = defaultdict(float)
        self.weights: Dict[str, int] = {}
    
    async def schedule_next(self) -> Optional["AIRequest"]:
        """Pick next request using weighted fair queuing."""
        max_deficit = -float('inf')
        selected_tenant = None
        
        for tenant_id, queue in self.queues.items():
            if queue.empty():
                continue
            
            # Add weight to deficit (higher weight = chosen more often)
            self.deficits[tenant_id] += self.weights.get(tenant_id, 1)
            
            if self.deficits[tenant_id] > max_deficit:
                max_deficit = self.deficits[tenant_id]
                selected_tenant = tenant_id
        
        if selected_tenant:
            request = await self.queues[selected_tenant].get()
            self.deficits[selected_tenant] -= request.cost
            return request
        
        return None

class QoSEnforcer:
    """Runtime enforcement of quality of service during request processing."""
    
    async def execute_with_qos(self, tenant_id: str, request, executor):
        """Execute request with timeout and resource bounds."""
        quota = self.get_quota(tenant_id)
        
        # Compute timeout based on tier
        timeout = self.get_timeout(quota)
        
        try:
            result = await asyncio.wait_for(
                executor.execute(request, resource_limit={
                    "max_vectors_scanned": quota.max_vector_results * 10,
                    "max_memory_mb": 512,
                    "max_gpu_ms": 1000
                }),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            self.metrics.increment("qos_timeout", tenant=tenant_id)
            return self.graceful_partial_result(request)
```

**QoS Tiers:**

| Tier | Latency SLA | Rate Limit | Concurrency | Priority | Cost |
|------|------------|------------|-------------|----------|------|
| Enterprise | p99 < 200ms | 1000 RPS | 200 | Weight 8 | $$$$ |
| Premium | p99 < 500ms | 500 RPS | 100 | Weight 4 | $$$ |
| Standard | p99 < 2s | 100 RPS | 50 | Weight 2 | $$ |
| Free | p99 < 5s | 10 RPS | 5 | Weight 1 | $ |

**Production Considerations:**
- **Graceful degradation**: When overloaded, reduce result quality (fewer candidates, skip re-ranking) rather than failing
- **Burst handling**: Allow 1.5x burst for 30 seconds; smooth out spikes without hard rejection
- **Feedback loop**: If a tenant consistently hits limits, proactively reach out for tier upgrade
- **Circuit breaker**: If one tenant's queries cause backend errors, circuit-break that tenant without affecting others
- **Observability**: Per-tenant dashboards showing quota utilization, latency, and throttle events

---

## Q163: Design a tenant onboarding pipeline that automatically provisions isolated AI infrastructure (vector indices, embedding models, LLM endpoints) for new enterprise customers in under 5 minutes.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Tenant Onboarding Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │  Sales   │───▶│  Onboarding  │───▶│  Provisioning          │ │
│  │  Portal  │    │  Orchestrator│    │  Engine (Terraform +   │ │
│  └──────────┘    │  (Step Fn)   │    │  K8s Operators)        │ │
│                   └──────┬───────┘    └───────────┬────────────┘ │
│                          │                        │              │
│         ┌────────────────┼────────────────────────┘              │
│         │                │                                       │
│         ▼                ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Provisioned Resources (per tenant)                      │    │
│  │                                                           │    │
│  │  ✓ Vector namespace/collection                            │    │
│  │  ✓ Embedding model endpoint (or shared with quota)        │    │
│  │  ✓ LLM endpoint (or gateway config)                       │    │
│  │  ✓ Document storage bucket                                │    │
│  │  ✓ API keys + auth config                                 │    │
│  │  ✓ Monitoring dashboards                                  │    │
│  │  ✓ Ingestion pipeline config                              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime

class TenantTier(Enum):
    STARTER = "starter"       # Shared everything
    PROFESSIONAL = "pro"      # Dedicated namespace, shared compute
    ENTERPRISE = "enterprise" # Dedicated everything

@dataclass
class TenantConfig:
    tenant_id: str
    name: str
    tier: TenantTier
    region: str
    compliance: List[str] = field(default_factory=list)  # ["hipaa", "soc2"]
    custom_model: Optional[str] = None
    storage_quota_gb: int = 100
    embedding_model: str = "text-embedding-3-large"

@dataclass
class ProvisioningStatus:
    tenant_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    steps: Dict[str, str] = field(default_factory=dict)
    completed: bool = False
    error: Optional[str] = None

class TenantOnboardingOrchestrator:
    """Orchestrates tenant provisioning in < 5 minutes."""
    
    def __init__(self, infra_provisioner, config_manager, monitoring):
        self.infra = infra_provisioner
        self.config = config_manager
        self.monitoring = monitoring
    
    async def onboard_tenant(self, config: TenantConfig) -> ProvisioningStatus:
        status = ProvisioningStatus(tenant_id=config.tenant_id)
        
        try:
            # Parallel provisioning of independent resources
            results = await asyncio.gather(
                self.provision_vector_store(config, status),
                self.provision_storage(config, status),
                self.provision_auth(config, status),
                self.provision_monitoring(config, status),
                return_exceptions=True
            )
            
            # Check for failures
            for r in results:
                if isinstance(r, Exception):
                    raise r
            
            # Sequential steps that depend on above
            await self.configure_ingestion_pipeline(config, status)
            await self.configure_llm_gateway(config, status)
            await self.run_smoke_test(config, status)
            await self.send_welcome(config)
            
            status.completed = True
            
        except Exception as e:
            status.error = str(e)
            await self.rollback(config, status)
            raise
        
        return status
    
    async def provision_vector_store(self, config: TenantConfig, status):
        """Provision vector storage based on tier."""
        status.steps["vector_store"] = "in_progress"
        
        if config.tier == TenantTier.STARTER:
            # Shared collection with namespace
            await self.infra.create_namespace(
                collection="shared_multi_tenant",
                namespace=config.tenant_id
            )
        elif config.tier == TenantTier.PROFESSIONAL:
            # Dedicated collection, shared cluster
            await self.infra.create_collection(
                name=f"tenant_{config.tenant_id}",
                dimension=1536,
                metric="cosine",
                replicas=2
            )
        elif config.tier == TenantTier.ENTERPRISE:
            # Dedicated cluster
            await self.infra.create_dedicated_cluster(
                tenant_id=config.tenant_id,
                region=config.region,
                node_count=3,
                encryption_at_rest=True,
                compliance=config.compliance
            )
        
        status.steps["vector_store"] = "completed"
    
    async def configure_llm_gateway(self, config: TenantConfig, status):
        """Configure LLM access with tenant-specific settings."""
        status.steps["llm_gateway"] = "in_progress"
        
        gateway_config = {
            "tenant_id": config.tenant_id,
            "allowed_models": self.get_allowed_models(config.tier),
            "rate_limits": self.get_rate_limits(config.tier),
            "custom_system_prompt": config.custom_model,
            "safety_filters": self.get_safety_config(config.compliance),
            "logging": {
                "enabled": True,
                "pii_redaction": "hipaa" in config.compliance,
                "retention_days": 90
            }
        }
        
        await self.config.apply_gateway_config(gateway_config)
        status.steps["llm_gateway"] = "completed"
    
    async def run_smoke_test(self, config: TenantConfig, status):
        """Verify all provisioned resources work end-to-end."""
        status.steps["smoke_test"] = "in_progress"
        
        # Ingest a test document
        test_doc = "This is a smoke test document for tenant onboarding."
        await self.ingest_document(config.tenant_id, test_doc)
        
        # Query and verify isolation
        results = await self.query(config.tenant_id, "smoke test")
        assert len(results) > 0, "Smoke test query returned no results"
        
        # Verify isolation: query from different tenant should NOT return this
        other_results = await self.query("__isolation_test__", "smoke test")
        assert all(r.tenant_id != config.tenant_id for r in other_results)
        
        # Cleanup test data
        await self.delete_document(config.tenant_id, "smoke_test_doc")
        
        status.steps["smoke_test"] = "completed"
    
    async def rollback(self, config: TenantConfig, status):
        """Rollback provisioned resources on failure."""
        for step, step_status in status.steps.items():
            if step_status == "completed":
                await self.infra.deprovision(config.tenant_id, step)
```

**Onboarding Timeline (Target < 5 min):**

| Step | Duration | Parallelizable |
|------|----------|---------------|
| Auth/API keys | 5s | Yes |
| Vector store | 30-120s | Yes |
| Storage bucket | 10s | Yes |
| Monitoring setup | 15s | Yes |
| Ingestion pipeline | 30s | No (depends on above) |
| LLM gateway config | 10s | No (depends on auth) |
| Smoke test | 30s | No (depends on all) |
| **Total** | **~3 minutes** | |

**Production Considerations:**
- **Warm pools**: Pre-provision vector collections and keep a warm pool; assign to tenant instantly
- **Idempotency**: Onboarding can be retried safely; all steps are idempotent
- **Self-service**: Enterprise admin portal triggers onboarding; no human in the loop
- **Compliance routing**: HIPAA tenants auto-routed to compliant regions; FedRAMP to GovCloud
- **Tenant deletion**: Reverse pipeline with data purge verification and 30-day soft-delete grace period

---

## Q164: Design a tenant-aware caching system where cached results from one tenant can never be served to another tenant, while still maximizing cache efficiency within each tenant.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Tenant-Aware Caching System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Cache Key Structure                       │  │
│  │  key = hash(tenant_id + query + params + version)           │  │
│  │  Tenant ID is ALWAYS part of the cache key                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  L1: In-Process Cache         (per-instance, per-tenant)    │  │
│  │  L2: Distributed Cache        (Redis, tenant-prefixed)      │  │
│  │  L3: Semantic Cache           (similar query dedup)         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Isolation Enforcement                                      │  │
│  │  - Tenant ID in every cache key (mandatory)                 │  │
│  │  - Separate Redis DB/keyspace per tenant (defense in depth) │  │
│  │  - Cache poisoning detection                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import hashlib
import json
from typing import Optional, Any
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class CacheConfig:
    l1_max_size_per_tenant: int = 1000
    l2_ttl: timedelta = timedelta(hours=1)
    semantic_similarity_threshold: float = 0.95
    max_cache_memory_per_tenant_mb: int = 512

class TenantAwareCache:
    """Multi-level cache with strict tenant isolation."""
    
    def __init__(self, redis_client, embedding_service, config: CacheConfig):
        self.redis = redis_client
        self.embedder = embedding_service
        self.config = config
        self.l1_cache = {}  # {tenant_id: LRUCache}
    
    def _cache_key(self, tenant_id: str, query: str, params: dict) -> str:
        """Generate isolated cache key. Tenant ID is MANDATORY."""
        # Deterministic key that ALWAYS includes tenant
        payload = json.dumps({
            "tenant": tenant_id,  # Critical: prevents cross-tenant leaks
            "query": query,
            "params": sorted(params.items())
        }, sort_keys=True)
        return f"t:{tenant_id}:q:{hashlib.sha256(payload.encode()).hexdigest()}"
    
    async def get(self, tenant_id: str, query: str, params: dict) -> Optional[Any]:
        """Lookup with strict tenant isolation."""
        key = self._cache_key(tenant_id, query, params)
        
        # L1: In-process (fastest, per-instance)
        l1 = self.l1_cache.get(tenant_id)
        if l1 and key in l1:
            self.metrics.hit("l1", tenant_id)
            return l1[key]
        
        # L2: Distributed (shared across instances)
        l2_result = await self.redis.get(key)
        if l2_result:
            # Verify tenant ownership (defense in depth)
            cached = json.loads(l2_result)
            if cached.get("_tenant_id") != tenant_id:
                # SECURITY: This should never happen. Alert immediately.
                await self.alert_security_team(tenant_id, key, cached)
                await self.redis.delete(key)
                return None
            
            self.metrics.hit("l2", tenant_id)
            # Promote to L1
            self._l1_put(tenant_id, key, cached["data"])
            return cached["data"]
        
        # L3: Semantic cache (find similar queries)
        semantic_result = await self.semantic_lookup(tenant_id, query)
        if semantic_result:
            self.metrics.hit("l3", tenant_id)
            return semantic_result
        
        self.metrics.miss(tenant_id)
        return None
    
    async def put(self, tenant_id: str, query: str, params: dict, value: Any):
        """Store with tenant isolation metadata."""
        key = self._cache_key(tenant_id, query, params)
        
        # Enforce per-tenant memory limits
        if await self.get_tenant_cache_size(tenant_id) > self.config.max_cache_memory_per_tenant_mb:
            await self.evict_tenant_entries(tenant_id, evict_percent=0.2)
        
        # Store with tenant ownership metadata
        cached_value = {
            "_tenant_id": tenant_id,  # Ownership proof
            "data": value,
            "cached_at": time.time()
        }
        
        # L1
        self._l1_put(tenant_id, key, value)
        
        # L2
        await self.redis.set(
            key, json.dumps(cached_value),
            ex=int(self.config.l2_ttl.total_seconds())
        )
        
        # L3: Store query embedding for semantic matching
        await self.semantic_store(tenant_id, query, key)
    
    async def semantic_lookup(self, tenant_id: str, query: str) -> Optional[Any]:
        """Find semantically similar cached queries within same tenant."""
        query_embedding = await self.embedder.embed(query)
        
        # Search ONLY within tenant's semantic cache
        similar = await self.redis.ft_search(
            index=f"semantic_cache:{tenant_id}",
            vector=query_embedding,
            threshold=self.config.semantic_similarity_threshold,
            limit=1
        )
        
        if similar:
            return await self.get_by_key(similar[0].cache_key)
        return None
    
    async def invalidate_tenant(self, tenant_id: str):
        """Invalidate all cache entries for a tenant."""
        # L1
        self.l1_cache.pop(tenant_id, None)
        
        # L2: Delete all keys with tenant prefix
        pattern = f"t:{tenant_id}:*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
        
        # L3: Drop semantic index
        await self.redis.ft_dropindex(f"semantic_cache:{tenant_id}")
```

**Cache Efficiency Optimization:**

| Technique | Benefit | Isolation Impact |
|-----------|---------|-----------------|
| Semantic caching | 30-40% more hits | Safe (tenant-scoped similarity search) |
| Query normalization | Dedup reformulations | Safe (per-tenant) |
| Tiered TTL | Fresh for active tenants | Independent per tenant |
| Warm-up on config change | Reduce cold-start | Tenant-specific warm-up |
| Shared embedding cache | Reduce embed calls | Safe (embeddings are tenant-agnostic) |

**Production Considerations:**
- **Cache poisoning detection**: Background job verifies random cache entries have correct tenant_id
- **Memory fairness**: Per-tenant memory quota prevents one tenant from evicting others' cached data
- **Invalidation on data change**: When tenant's documents update, invalidate affected cache entries
- **Metrics**: Track hit rate per tenant; tenants with low hit rates may need different caching strategy
- **Encryption at rest**: Cache values encrypted with tenant key for Enterprise tier

---

## Q165: Design a compliance-aware multi-tenant architecture where different tenants have different regulatory requirements (HIPAA, SOC2, FedRAMP, GDPR) on the same platform.

### Answer

**Architecture:**

```
┌──────────────────────────────────────────────────────────────────────┐
│            Compliance-Aware Multi-Tenant Architecture                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                  Compliance Router                                │ │
│  │  Request → Tenant → Compliance Profile → Route to Compliant Infra│ │
│  └───────────────────────────────┬─────────────────────────────────┘ │
│                                   │                                    │
│  ┌────────────────────────────────┼────────────────────────────────┐ │
│  │                                ▼                                  │ │
│  │  ┌────────────┐  ┌────────────────┐  ┌───────────────────────┐ │ │
│  │  │ Standard   │  │  HIPAA Zone    │  │  FedRAMP Zone         │ │ │
│  │  │ Zone       │  │                │  │  (GovCloud)           │ │ │
│  │  │            │  │  - PHI encrypt │  │                       │ │ │
│  │  │ SOC2 base  │  │  - Audit log   │  │  - IL4/IL5 controls  │ │ │
│  │  │ controls   │  │  - BAA enforce │  │  - FIPS 140-2        │ │ │
│  │  │            │  │  - Min access  │  │  - US-only data       │ │ │
│  │  └────────────┘  └────────────────┘  └───────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              Cross-Cutting Compliance Controls                    │ │
│  │  - Encryption (at rest + in transit)                              │ │
│  │  - Audit logging (immutable)                                      │ │
│  │  - Data residency enforcement                                     │ │
│  │  - Access control (RBAC + ABAC)                                   │ │
│  │  - Retention policies                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
from enum import Enum

class ComplianceFramework(Enum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    FEDRAMP = "fedramp"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"

@dataclass
class ComplianceProfile:
    frameworks: Set[ComplianceFramework]
    data_residency: List[str]          # Allowed regions
    encryption_standard: str            # "AES-256", "FIPS-140-2"
    key_management: str                 # "aws-kms", "hsm", "byok"
    audit_level: str                    # "standard", "enhanced", "full"
    retention_days: int = 365
    pii_handling: str = "redact"        # "redact", "encrypt", "deny"
    model_restrictions: List[str] = field(default_factory=list)

class ComplianceRouter:
    """Route requests to compliant infrastructure based on tenant profile."""
    
    def __init__(self, tenant_store, zone_registry):
        self.tenants = tenant_store
        self.zones = zone_registry
    
    def get_compliant_zone(self, tenant_id: str) -> "InfraZone":
        profile = self.tenants.get_compliance_profile(tenant_id)
        
        # Find zone that satisfies ALL required frameworks
        for zone in self.zones.list():
            if profile.frameworks.issubset(zone.supported_frameworks):
                if self.check_residency(zone, profile):
                    return zone
        
        raise ComplianceError(f"No zone satisfies {profile.frameworks}")
    
    def check_residency(self, zone, profile: ComplianceProfile) -> bool:
        return zone.region in profile.data_residency

class ComplianceEnforcingProxy:
    """Middleware that enforces compliance controls on every request."""
    
    def __init__(self, compliance_profiles, audit_logger):
        self.profiles = compliance_profiles
        self.audit = audit_logger
    
    async def process_request(self, tenant_id: str, request: "AIRequest"):
        profile = self.profiles.get(tenant_id)
        
        # 1. Data residency check
        if request.target_region not in profile.data_residency:
            raise ComplianceViolation(
                f"Cannot process in {request.target_region}; "
                f"allowed: {profile.data_residency}"
            )
        
        # 2. PII handling
        if ComplianceFramework.HIPAA in profile.frameworks:
            request = await self.enforce_hipaa(request)
        
        if ComplianceFramework.GDPR in profile.frameworks:
            request = await self.enforce_gdpr(request)
        
        # 3. Model restrictions (some models not approved for certain data)
        if request.model not in self.get_approved_models(profile):
            raise ComplianceViolation(
                f"Model {request.model} not approved for {profile.frameworks}"
            )
        
        # 4. Audit logging (before processing)
        audit_entry = await self.audit.log(
            tenant_id=tenant_id,
            action="ai_request",
            request_hash=self.hash_request(request),
            compliance_context=profile.frameworks,
            timestamp=datetime.utcnow()
        )
        
        # 5. Process with compliance controls active
        result = await self.execute_with_controls(request, profile)
        
        # 6. Output validation
        if ComplianceFramework.HIPAA in profile.frameworks:
            result = await self.scan_output_for_phi(result)
        
        # 7. Audit response
        await self.audit.log_response(audit_entry.id, result_hash=self.hash_result(result))
        
        return result
    
    async def enforce_hipaa(self, request):
        """HIPAA-specific controls."""
        # Ensure PHI is encrypted in transit
        if not request.is_encrypted:
            raise ComplianceViolation("PHI must be encrypted in transit")
        
        # Minimum necessary access
        request.metadata["access_justification"] = request.purpose
        
        # Ensure BAA covers the model provider
        if not self.baa_exists(request.model_provider):
            raise ComplianceViolation(
                f"No BAA with {request.model_provider}"
            )
        
        return request
    
    async def enforce_gdpr(self, request):
        """GDPR-specific controls."""
        # Right to explanation: log all automated decisions
        request.metadata["automated_decision"] = True
        
        # Data minimization: strip unnecessary PII
        request.content = await self.minimize_pii(request.content)
        
        # Lawful basis check
        if not self.has_lawful_basis(request.tenant_id, request.data_subject):
            raise ComplianceViolation("No lawful basis for processing")
        
        return request
```

**Compliance Control Matrix:**

| Control | SOC2 | HIPAA | FedRAMP | GDPR |
|---------|------|-------|---------|------|
| Encryption at rest | AES-256 | AES-256 | FIPS 140-2 | AES-256 |
| Encryption in transit | TLS 1.2+ | TLS 1.2+ | TLS 1.2+ (FIPS) | TLS 1.2+ |
| Audit logging | Standard | Enhanced + PHI access | Full (6yr retention) | Standard |
| Data residency | Flexible | US (typically) | US only | EU (or adequacy) |
| Key management | AWS KMS | KMS + BYOK | HSM (FIPS) | KMS |
| Access control | RBAC | RBAC + MFA + min-necessary | RBAC + PIV/CAC | RBAC + consent |
| Model approval | Any | BAA-covered only | FedRAMP authorized | Any (with DPIA) |
| Data deletion | Reasonable | 6yr retention then delete | Per NARA schedule | On request (Art 17) |

**Production Considerations:**
- **Shared base, additive controls**: SOC2 is the baseline; other frameworks add controls on top
- **Compliance as code**: All controls defined in policy-as-code (OPA/Rego); changes go through PR review
- **Continuous compliance**: Automated compliance checks run hourly; violations trigger alerts
- **Audit trail immutability**: Write audit logs to append-only store (AWS CloudTrail, immutable S3)
- **Tenant migration**: If tenant adds HIPAA requirement, pipeline migrates data to compliant zone with zero downtime
# Data Engineering for AI (Questions 286-290)

## Q286: Streaming data platform for real-time AI features with <100ms latency

### Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         Real-Time AI Feature Platform (<100ms E2E)                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Event Sources ─────────────────────────────────────┐         │
│  │  User clicks │ API calls │ Search queries │ Purchases │         │
│  └──────────────────────────┬────────────────────────────┘         │
│                             │ <10ms                                  │
│  ┌──────────────────────────▼────────────────────────────┐         │
│  │           Kafka (Event Bus)                            │         │
│  │           Partitioned by user_id                       │         │
│  └──────────────────────────┬────────────────────────────┘         │
│                             │ <20ms                                  │
│  ┌──────────────────────────▼────────────────────────────┐         │
│  │           Flink (Stream Processing)                    │         │
│  │  ┌────────────────┐  ┌──────────────┐               │         │
│  │  │ Feature Compute│  │ Embedding    │               │         │
│  │  │ (aggregations, │  │ Computation  │               │         │
│  │  │  windowed stats)│  │ (real-time)  │               │         │
│  │  └───────┬────────┘  └──────┬───────┘               │         │
│  └──────────┼──────────────────┼─────────────────────────┘         │
│             │ <30ms            │ <40ms                               │
│  ┌──────────▼──────────────────▼─────────────────────────┐         │
│  │           Feature Store (Online)                       │         │
│  │  ┌─────────────┐  ┌────────────────┐                │         │
│  │  │ Redis       │  │ Vector Index   │                │         │
│  │  │ (Key-value  │  │ (Fresh         │                │         │
│  │  │  features)  │  │  embeddings)   │                │         │
│  │  └──────┬──────┘  └───────┬────────┘                │         │
│  └─────────┼─────────────────┼───────────────────────────┘         │
│            │ <5ms            │ <10ms                                │
│  ┌─────────▼─────────────────▼───────────────────────────┐         │
│  │           Serving Layer                                │         │
│  │  Retrieve features + vectors → Model inference         │         │
│  │  Total budget: <100ms end-to-end                       │         │
│  └────────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class RealTimeFeaturePipeline:
    """Stream processing for AI features with <100ms latency."""
    
    def __init__(self):
        self.flink_env = FlinkStreamEnv(
            checkpoint_interval_ms=5000,
            state_backend="rocksdb",  # For large state
            parallelism=64
        )
    
    def build_user_features(self):
        """Compute real-time user features from event stream."""
        events = self.flink_env.from_kafka("user_events")
        
        # Windowed aggregations (last 5 min, 1 hr, 24 hr)
        windowed_features = (events
            .key_by("user_id")
            .window(SlidingWindow(size="5min", slide="10sec"))
            .aggregate(UserFeatureAggregator())
            # Output: {user_id, click_count_5m, unique_categories_5m, 
            #          avg_dwell_time_5m, search_count_5m}
        )
        
        # Real-time embedding update
        embedding_updates = (events
            .filter(lambda e: e.type in ["search", "purchase", "view"])
            .key_by("user_id")
            .process(IncrementalEmbeddingUpdater())
            # Updates user embedding based on recent interactions
        )
        
        # Sink to online stores
        windowed_features.add_sink(RedisSink(ttl=3600))
        embedding_updates.add_sink(VectorIndexSink(index="user_embeddings"))
    
    def build_item_features(self):
        """Real-time item popularity and trending signals."""
        events = self.flink_env.from_kafka("item_events")
        
        trending = (events
            .key_by("item_id")
            .window(TumblingWindow(size="1min"))
            .aggregate(TrendingScoreAggregator())
            # Compute velocity: interactions/min vs. historical baseline
        )
        
        trending.add_sink(RedisSink(key_prefix="item:trending:", ttl=300))


class IncrementalEmbeddingUpdater(ProcessFunction):
    """Update user embedding incrementally without full recomputation."""
    
    def __init__(self):
        self.embedding_model = CachedEmbeddingModel()
        self.decay_factor = 0.95  # Exponential decay for old signals
    
    def process(self, event, state: UserEmbeddingState):
        # Get current user embedding from state
        current = state.get_embedding()
        
        # Compute embedding of new interaction
        interaction_embedding = self.embedding_model.encode(
            f"{event.type}: {event.item_title} in {event.category}")
        
        # Exponential moving average update
        # New = decay * old + (1 - decay) * new_signal
        updated = (self.decay_factor * current + 
                  (1 - self.decay_factor) * interaction_embedding)
        updated = updated / np.linalg.norm(updated)  # Normalize
        
        state.update_embedding(updated)
        
        return EmbeddingUpdate(user_id=event.user_id, embedding=updated)
```

### Latency Budget Breakdown

| Stage | Target | Technique |
|-------|--------|-----------|
| Event ingestion (Kafka) | <10ms | Linger.ms=5, batch.size=16K |
| Stream processing (Flink) | <30ms | Low checkpoint interval, no shuffle |
| Feature store write | <5ms | Redis pipeline, async write |
| Feature store read (serving) | <5ms | Redis cluster, local replica |
| Vector search | <10ms | HNSW with pre-warmed cache |
| Model inference | <30ms | Batched, quantized, cached |
| **Total** | **<100ms** | End-to-end monitored |

---

## Q287: Data labeling infrastructure with human + model-assisted + active learning

### Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         Intelligent Data Labeling Platform                           │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Unlabeled Data Pool ───────────────────────────────┐         │
│  │  Documents, images, conversations (millions)           │         │
│  └──────────────────────────┬────────────────────────────┘         │
│                             │                                       │
│  ┌──────────────────────────▼────────────────────────────┐         │
│  │           Active Learning Selector                     │         │
│  │  • Uncertainty sampling (model least confident)        │         │
│  │  • Diversity sampling (cover data distribution)        │         │
│  │  • Expected model change (most informative)            │         │
│  └──────────────────────────┬────────────────────────────┘         │
│                             │                                       │
│  ┌──────────────────────────▼────────────────────────────┐         │
│  │           Labeling Pipeline                            │         │
│  │                                                        │         │
│  │  ┌─────────────┐   ┌──────────────┐   ┌──────────┐  │         │
│  │  │ LLM Pre-    │   │ Human        │   │ Quality  │  │         │
│  │  │ annotation  │──▶│ Verification │──▶│ Control  │  │         │
│  │  │ (draft)     │   │ (correct/    │   │ (IAA,    │  │         │
│  │  │             │   │  confirm)    │   │  audit)  │  │         │
│  │  └─────────────┘   └──────────────┘   └──────────┘  │         │
│  └──────────────────────────┬────────────────────────────┘         │
│                             │                                       │
│  ┌──────────────────────────▼────────────────────────────┐         │
│  │           Labeled Dataset (versioned)                   │         │
│  └────────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class IntelligentLabelingPlatform:
    """Cost-optimized labeling with human + AI collaboration."""
    
    def __init__(self):
        self.active_learner = ActiveLearner()
        self.pre_annotator = LLMPreAnnotator(model="gpt-4-turbo")
        self.quality_controller = QualityController()
    
    def select_samples_for_labeling(self, pool_size: int = 1000) -> List:
        """Active learning: select most informative samples."""
        unlabeled = self.data_pool.get_unlabeled(limit=10000)
        
        # Score each sample by informativeness
        scores = []
        for sample in unlabeled:
            uncertainty = self.active_learner.uncertainty_score(sample)
            diversity = self.active_learner.diversity_score(sample, self.labeled_set)
            representativeness = self.active_learner.representativeness(sample)
            
            # Combined score (balance exploration vs exploitation)
            combined = (0.4 * uncertainty + 
                       0.3 * diversity + 
                       0.3 * representativeness)
            scores.append((sample, combined))
        
        # Select top-K most informative
        selected = sorted(scores, key=lambda x: x[1], reverse=True)[:pool_size]
        return [s[0] for s in selected]
    
    def model_assisted_labeling(self, samples: List) -> List[PreAnnotation]:
        """LLM generates draft labels for human verification."""
        pre_annotations = []
        
        for sample in samples:
            # LLM generates label + confidence + explanation
            result = self.pre_annotator.annotate(
                sample,
                guidelines=self.labeling_guidelines,
                examples=self.get_few_shot_examples(sample)
            )
            
            pre_annotations.append(PreAnnotation(
                sample=sample,
                suggested_label=result.label,
                confidence=result.confidence,
                explanation=result.explanation,
                # Route based on confidence
                routing=self.route_decision(result.confidence)
            ))
        
        return pre_annotations
    
    def route_decision(self, confidence: float) -> str:
        """Route based on model confidence to optimize human effort."""
        if confidence > 0.95:
            return "auto_accept"  # High confidence, spot-check only
        elif confidence > 0.7:
            return "human_verify"  # Show suggestion, human confirms/corrects
        else:
            return "human_label"  # Low confidence, human labels from scratch
    
    def quality_control(self, annotations: List) -> QualityReport:
        """Multi-layer quality assurance."""
        # 1. Inter-annotator agreement (10% overlap)
        overlap_samples = self.get_overlap_annotations()
        iaa = self.quality_controller.compute_agreement(
            overlap_samples, metric="cohen_kappa")
        
        # 2. Gold standard checks (hidden test questions)
        gold_results = self.quality_controller.check_gold_standards()
        
        # 3. Consistency checks (same annotator, similar samples)
        consistency = self.quality_controller.check_consistency()
        
        # 4. Flag problematic annotators
        annotator_quality = self.quality_controller.per_annotator_metrics()
        
        return QualityReport(
            iaa_score=iaa,  # Target: >0.8 Cohen's Kappa
            gold_accuracy=gold_results.accuracy,  # Target: >95%
            consistency_score=consistency,
            flagged_annotators=[a for a in annotator_quality if a.score < 0.7]
        )
```

### Cost Optimization

| Strategy | Cost Reduction | Quality Impact |
|----------|---------------|----------------|
| LLM pre-annotation + human verify | 60-70% cheaper | Slightly higher (guided) |
| Active learning selection | 50% fewer labels needed | Same accuracy (targeted) |
| Auto-accept high confidence | 30% fewer human tasks | <1% quality loss (spot-checked) |
| Tiered workforce (junior verify, senior label complex) | 40% cheaper | Same (difficulty-matched) |

---

## Q288: Synthetic data generation pipeline for AI evaluation and training

### Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         Synthetic Data Generation Pipeline                           │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Generation Strategies ─────────────────────────────┐         │
│  │                                                        │         │
│  │  1. LLM-Generated Test Cases                          │         │
│  │     • Seed examples → LLM generates variations        │         │
│  │     • Taxonomy-driven: cover all categories           │         │
│  │     • Edge case generation: adversarial examples      │         │
│  │                                                        │         │
│  │  2. Template-Based Augmentation                       │         │
│  │     • Entity swapping (names, dates, numbers)         │         │
│  │     • Paraphrase generation                           │         │
│  │     • Back-translation (EN→FR→EN)                     │         │
│  │                                                        │         │
│  │  3. Simulation-Based                                  │         │
│  │     • Multi-agent conversations (role-play)           │         │
│  │     • Tool-use traces (simulated API calls)           │         │
│  │     • Error injection (realistic failure modes)       │         │
│  └────────────────────────────┬───────────────────────────┘         │
│                               │                                      │
│  ┌────────────────────────────▼───────────────────────────┐         │
│  │           Validation Pipeline                           │         │
│  │  • Distribution match (KL divergence from real data)   │         │
│  │  • Diversity metrics (n-gram diversity, embedding spread│         │
│  │  • Quality filtering (coherence, correctness)          │         │
│  │  • Contamination check (not in test set)               │         │
│  └────────────────────────────┬───────────────────────────┘         │
│                               │                                      │
│  ┌────────────────────────────▼───────────────────────────┐         │
│  │           Synthetic Dataset (versioned, documented)     │         │
│  └────────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SyntheticDataGenerator:
    """Generate diverse, representative synthetic data for AI eval/training."""
    
    def __init__(self):
        self.llm = GPT4Client()
        self.validator = DataValidator()
        self.diversity_tracker = DiversityTracker()
    
    def generate_eval_dataset(self, taxonomy: Dict, 
                              target_size: int) -> SyntheticDataset:
        """Generate evaluation dataset covering full taxonomy."""
        samples = []
        
        for category, subcategories in taxonomy.items():
            samples_per_category = target_size // len(taxonomy)
            
            for subcategory in subcategories:
                # Generate diverse examples for this category
                batch = self.generate_category_batch(
                    category=category,
                    subcategory=subcategory,
                    count=samples_per_category // len(subcategories),
                    difficulty_distribution={"easy": 0.3, "medium": 0.5, "hard": 0.2}
                )
                samples.extend(batch)
        
        # Validate representativeness
        validation = self.validator.validate_dataset(samples)
        
        # Filter low-quality samples
        filtered = [s for s in samples if s.quality_score > 0.8]
        
        return SyntheticDataset(
            samples=filtered,
            validation_report=validation,
            diversity_metrics=self.diversity_tracker.compute(filtered)
        )
    
    def generate_category_batch(self, category: str, subcategory: str,
                                count: int, difficulty_distribution: Dict):
        """Generate batch with controlled diversity."""
        prompt = f"""Generate {count} diverse examples for:
        Category: {category}
        Subcategory: {subcategory}
        
        Requirements:
        - Each example must be unique (different entities, contexts, phrasings)
        - Vary difficulty: {difficulty_distribution}
        - Include edge cases and boundary conditions
        - Make examples realistic (could appear in production)
        
        For each example provide:
        - Input (user query/document)
        - Expected output (ground truth)
        - Difficulty level
        - What makes this example interesting/challenging
        """
        
        raw_samples = self.llm.generate(prompt, n=count)
        
        # Post-process and validate
        validated = []
        for sample in raw_samples:
            # Check it's not too similar to existing samples
            if self.diversity_tracker.is_diverse_enough(sample, validated):
                sample.quality_score = self.assess_quality(sample)
                validated.append(sample)
        
        return validated
    
    def validate_representativeness(self, synthetic: List, 
                                     real_sample: List) -> RepReport:
        """Ensure synthetic data distribution matches real data."""
        # Embedding distribution comparison
        synth_embeddings = self.embed(synthetic)
        real_embeddings = self.embed(real_sample)
        
        # KL divergence in embedding space
        kl_div = self.compute_kl_divergence(synth_embeddings, real_embeddings)
        
        # Length distribution comparison
        synth_lengths = [len(s.text.split()) for s in synthetic]
        real_lengths = [len(s.text.split()) for s in real_sample]
        length_ks = ks_test(synth_lengths, real_lengths)
        
        # Vocabulary overlap
        synth_vocab = set(word for s in synthetic for word in s.text.split())
        real_vocab = set(word for s in real_sample for word in s.text.split())
        vocab_overlap = len(synth_vocab & real_vocab) / len(real_vocab)
        
        return RepReport(
            embedding_kl_divergence=kl_div,  # Target: <0.1
            length_distribution_p_value=length_ks.pvalue,  # Target: >0.05
            vocabulary_overlap=vocab_overlap,  # Target: >0.7
            is_representative=kl_div < 0.1 and vocab_overlap > 0.7
        )
```

---

## Q289: Data deduplication pipeline for large document corpus

### Comparison of Approaches

```
┌────────────────────────────────────────────────────────────────────┐
│         Deduplication Methods Comparison                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Exact Dedup          Near-Duplicate         Semantic Dedup         │
│  ┌──────────┐        ┌──────────┐           ┌──────────┐          │
│  │ SHA-256  │        │ SimHash/ │           │ Embedding│          │
│  │ Hash     │        │ MinHash  │           │ Cosine   │          │
│  │          │        │          │           │ Similarity│          │
│  └──────────┘        └──────────┘           └──────────┘          │
│                                                                      │
│  Speed: O(n)          Speed: O(n)            Speed: O(n log n)     │
│  Catches: identical   Catches: near-copies   Catches: same meaning │
│  Misses: any change   Misses: rephrased      Misses: false pos     │
│  Cost: $              Cost: $$               Cost: $$$              │
└────────────────────────────────────────────────────────────────────┘
```

### Multi-Stage Pipeline

```python
class DocumentDeduplicationPipeline:
    """Multi-stage dedup: exact → near-duplicate → semantic."""
    
    def __init__(self, corpus_size: int):
        self.corpus_size = corpus_size
        # Stage 1: Exact
        self.hash_index = {}
        # Stage 2: Near-duplicate (MinHash + LSH)
        self.minhash_lsh = MinHashLSH(threshold=0.8, num_perm=128)
        # Stage 3: Semantic
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.vector_index = FaissIndex(dim=384)
    
    def deduplicate(self, documents: Iterator[Document]) -> DeduplicatedCorpus:
        """Three-stage deduplication pipeline."""
        unique_docs = []
        stats = DedupStats()
        
        for doc in documents:
            # Stage 1: Exact duplicate (hash comparison)
            doc_hash = hashlib.sha256(doc.text.encode()).hexdigest()
            if doc_hash in self.hash_index:
                stats.exact_duplicates += 1
                continue
            self.hash_index[doc_hash] = doc.id
            
            # Stage 2: Near-duplicate (MinHash)
            minhash = self.compute_minhash(doc.text)
            near_dupes = self.minhash_lsh.query(minhash)
            if near_dupes:
                # Keep the longer/higher-quality version
                stats.near_duplicates += 1
                if self.should_replace(doc, near_dupes[0]):
                    self.replace(near_dupes[0], doc)
                continue
            self.minhash_lsh.insert(doc.id, minhash)
            
            # Stage 3: Semantic dedup (embedding similarity)
            embedding = self.embedder.encode(doc.text)
            similar = self.vector_index.search(embedding, k=5, threshold=0.95)
            if similar:
                stats.semantic_duplicates += 1
                continue
            self.vector_index.add(doc.id, embedding)
            
            unique_docs.append(doc)
        
        return DeduplicatedCorpus(documents=unique_docs, stats=stats)
    
    def compute_minhash(self, text: str) -> MinHash:
        """Compute MinHash signature for near-duplicate detection."""
        # Shingle the text (5-gram character shingles)
        shingles = set()
        for i in range(len(text) - 4):
            shingles.add(text[i:i+5])
        
        m = MinHash(num_perm=128)
        for shingle in shingles:
            m.update(shingle.encode())
        return m
```

### Performance at Scale

| Method | 1M Docs | 100M Docs | 1B Docs |
|--------|---------|-----------|---------|
| Exact (SHA-256) | 30 sec | 50 min | 8 hr |
| MinHash LSH | 5 min | 8 hr | 80 hr |
| Semantic (FAISS) | 20 min | 30 hr | Sharded (days) |
| **Combined pipeline** | **25 min** | **35 hr** | **Distributed** |

---

## Q290: Data anonymization pipeline preserving utility for AI training

### Approach Comparison

| Method | Privacy Guarantee | Utility Preservation | Complexity |
|--------|-------------------|---------------------|-----------|
| k-Anonymity | Quasi-identifier groups ≥ k | Medium (generalization loses info) | Low |
| l-Diversity | Sensitive values diverse in each group | Medium-High | Medium |
| Differential Privacy | Mathematical bound on information leakage | Low-Medium (noise degrades) | High |
| Synthetic Data | No real records in output | High (if well-generated) | High |

### Implementation

```python
class AnonymizationPipeline:
    """Multi-technique anonymization preserving AI training utility."""
    
    def __init__(self, privacy_config: PrivacyConfig):
        self.config = privacy_config
        self.pii_detector = PIIDetector()  # NER + regex + context
        self.dp_mechanism = DifferentialPrivacy(epsilon=privacy_config.epsilon)
    
    def anonymize_for_training(self, dataset: Dataset) -> AnonymizedDataset:
        """Anonymize dataset while preserving ML utility."""
        
        # 1. PII Detection and Classification
        pii_annotations = self.pii_detector.detect_all(dataset)
        
        # 2. Apply appropriate technique per PII type
        anonymized = []
        for record in dataset:
            anon_record = record.copy()
            
            for pii in pii_annotations.get(record.id, []):
                if pii.type == "name":
                    # Replace with consistent fake (preserves relationships)
                    anon_record.text = self.replace_with_fake(
                        anon_record.text, pii, self.name_faker)
                elif pii.type == "email":
                    anon_record.text = self.replace_with_fake(
                        anon_record.text, pii, self.email_faker)
                elif pii.type == "phone":
                    anon_record.text = self.redact(anon_record.text, pii)
                elif pii.type == "address":
                    # Generalize (keep city, remove street)
                    anon_record.text = self.generalize(
                        anon_record.text, pii, level="city")
                elif pii.type == "medical_record":
                    # Most sensitive - full redaction
                    anon_record.text = self.redact(anon_record.text, pii)
            
            anonymized.append(anon_record)
        
        # 3. Validate anonymization
        validation = self.validate(anonymized)
        
        # 4. Utility measurement
        utility = self.measure_utility(dataset, anonymized)
        
        return AnonymizedDataset(
            records=anonymized,
            privacy_report=validation,
            utility_metrics=utility
        )
    
    def apply_differential_privacy(self, aggregates: Dict) -> Dict:
        """Add calibrated noise to aggregate statistics."""
        noisy_aggregates = {}
        for key, value in aggregates.items():
            sensitivity = self.compute_sensitivity(key)
            noise = np.random.laplace(0, sensitivity / self.config.epsilon)
            noisy_aggregates[key] = value + noise
        return noisy_aggregates
    
    def generate_synthetic_alternative(self, dataset: Dataset) -> Dataset:
        """Generate fully synthetic data matching distribution."""
        # Train generative model on real data with DP guarantees
        generator = DPSyntheticGenerator(
            epsilon=self.config.epsilon,
            delta=1e-5
        )
        generator.fit(dataset)
        
        # Generate synthetic records
        synthetic = generator.generate(n=len(dataset))
        
        # Validate: no real records in synthetic output
        assert self.no_memorization(synthetic, dataset)
        
        return synthetic
    
    def measure_utility(self, original: Dataset, 
                        anonymized: Dataset) -> UtilityMetrics:
        """Measure how much ML utility is preserved."""
        # Train same model on both, compare performance
        model_original = train_model(original)
        model_anonymized = train_model(anonymized)
        
        test_set = self.get_held_out_test()
        
        return UtilityMetrics(
            original_accuracy=evaluate(model_original, test_set),
            anonymized_accuracy=evaluate(model_anonymized, test_set),
            utility_ratio=evaluate(model_anonymized, test_set) / 
                         evaluate(model_original, test_set),
            # Target: utility_ratio > 0.95 (less than 5% degradation)
        )
```

### Privacy-Utility Trade-off Guidelines

| Use Case | Recommended Approach | Expected Utility Loss |
|----------|---------------------|----------------------|
| Text classification training | Entity replacement (consistent fakes) | <2% |
| Sentiment analysis | Redact names only | <1% |
| Medical NLP | Synthetic data generation | 5-10% |
| Financial modeling | k-Anonymity + DP aggregates | 3-8% |
| Conversational AI | Entity replacement + paraphrasing | 3-5% |
