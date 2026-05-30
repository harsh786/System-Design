"""
Scalable Ingestion Pipeline for Vector Databases
Handles: source connectors, change detection, parsing, embedding, indexing,
dead-letter queues, freshness monitoring, retrieval regression, backpressure.
"""

import asyncio
import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class SourceType(Enum):
    S3 = "s3"
    GCS = "gcs"
    DATABASE = "database"
    API = "api"
    FILESYSTEM = "filesystem"
    CONFLUENCE = "confluence"
    SHAREPOINT = "sharepoint"


class Priority(Enum):
    URGENT = 0      # User upload, needs immediate processing
    HIGH = 1        # Real-time sync
    NORMAL = 2      # Scheduled crawl
    LOW = 3         # Backfill, reindex


@dataclass
class Document:
    doc_id: str
    source_type: SourceType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    tenant_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class EmbeddedChunk:
    chunk_id: str
    doc_id: str
    vector: List[float]
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_model: str = "text-embedding-3-small"
    embedded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IngestionJob:
    job_id: str
    doc_id: str
    source_id: str
    content_hash: str
    tenant_id: str
    priority: Priority
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: str = ""

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = f"{self.source_id}:{self.content_hash}"


@dataclass
class PipelineMetrics:
    docs_ingested: int = 0
    docs_failed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    vectors_indexed: int = 0
    avg_latency_ms: float = 0.0
    queue_depth: int = 0
    dlq_depth: int = 0
    last_ingestion_at: Optional[datetime] = None
    freshness_lag_seconds: float = 0.0


# =============================================================================
# Source Connectors
# =============================================================================

class BaseSourceConnector(ABC):
    """Base class for source connectors with change detection."""

    def __init__(self, source_id: str, config: Dict[str, Any]):
        self.source_id = source_id
        self.config = config
        self._last_sync: Optional[datetime] = None
        self._known_hashes: Dict[str, str] = {}  # doc_id -> content_hash

    @abstractmethod
    async def list_documents(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """List documents, optionally only those changed since timestamp."""
        pass

    @abstractmethod
    async def fetch_document(self, doc_ref: Dict[str, Any]) -> Document:
        """Fetch full document content."""
        pass

    async def detect_changes(self) -> Tuple[List[str], List[str], List[str]]:
        """
        Detect added, modified, and deleted documents since last sync.
        Returns: (added_ids, modified_ids, deleted_ids)
        """
        current_docs = await self.list_documents(since=self._last_sync)
        current_map = {d["doc_id"]: d.get("content_hash", "") for d in current_docs}

        added = [did for did in current_map if did not in self._known_hashes]
        modified = [
            did for did in current_map
            if did in self._known_hashes and current_map[did] != self._known_hashes[did]
        ]
        deleted = [did for did in self._known_hashes if did not in current_map]

        self._known_hashes = current_map
        self._last_sync = datetime.utcnow()
        return added, modified, deleted


class S3SourceConnector(BaseSourceConnector):
    """S3/GCS bucket connector with change detection via ETags."""

    async def list_documents(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        # In production: boto3.list_objects_v2 with LastModified filter
        # Simulated
        return [
            {"doc_id": f"s3://{self.config['bucket']}/doc_{i}.pdf",
             "content_hash": f"hash_{i}",
             "last_modified": datetime.utcnow()}
            for i in range(10)
        ]

    async def fetch_document(self, doc_ref: Dict[str, Any]) -> Document:
        # In production: boto3.get_object
        return Document(
            doc_id=doc_ref["doc_id"],
            source_type=SourceType.S3,
            content=f"Content of {doc_ref['doc_id']}",
            metadata={"source": "s3", "bucket": self.config.get("bucket", "")},
        )


class DatabaseSourceConnector(BaseSourceConnector):
    """Database connector using CDC (Change Data Capture) or polling."""

    async def list_documents(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        # In production: SELECT id, content_hash, updated_at FROM docs WHERE updated_at > since
        return [
            {"doc_id": f"db_doc_{i}", "content_hash": f"dbhash_{i}"}
            for i in range(5)
        ]

    async def fetch_document(self, doc_ref: Dict[str, Any]) -> Document:
        return Document(
            doc_id=doc_ref["doc_id"],
            source_type=SourceType.DATABASE,
            content=f"DB content of {doc_ref['doc_id']}",
            metadata={"source": "database"},
        )


# =============================================================================
# Processing Pipeline Stages
# =============================================================================

class ChunkingService:
    """Document chunking with configurable strategies."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: Document) -> List[Chunk]:
        """Split document into overlapping chunks."""
        content = doc.content
        chunks = []
        start = 0
        idx = 0

        while start < len(content):
            end = start + self.chunk_size
            chunk_content = content[start:end]

            chunk = Chunk(
                chunk_id=f"{doc.doc_id}__chunk_{idx}",
                doc_id=doc.doc_id,
                content=chunk_content,
                chunk_index=idx,
                metadata={
                    **doc.metadata,
                    "tenant_id": doc.tenant_id,
                    "doc_id": doc.doc_id,
                    "chunk_index": idx,
                    "source_type": doc.source_type.value,
                },
            )
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
            idx += 1

        return chunks


class EmbeddingService:
    """Batch embedding service with rate limiting and retry."""

    def __init__(self, model: str = "text-embedding-3-small",
                 batch_size: int = 64, max_concurrent: int = 4):
        self.model = model
        self.batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._total_embedded = 0

    async def embed_batch(self, chunks: List[Chunk]) -> List[EmbeddedChunk]:
        """Embed a batch of chunks. Handles batching and concurrency."""
        results = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            embedded = await self._call_embedding_api(batch)
            results.extend(embedded)
        return results

    async def _call_embedding_api(self, chunks: List[Chunk]) -> List[EmbeddedChunk]:
        """Call embedding API with retry and rate limiting."""
        async with self._semaphore:
            # In production: call OpenAI/Cohere/local model
            await asyncio.sleep(0.05)  # Simulate API call
            results = []
            for chunk in chunks:
                # Simulated embedding (in production: actual API response)
                vector = [hash(chunk.content[i:i+4]) % 1000 / 1000.0
                          for i in range(0, min(len(chunk.content), 1536 * 4), 4)]
                vector = vector[:1536] + [0.0] * max(0, 1536 - len(vector))

                results.append(EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    vector=vector,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    embedding_model=self.model,
                ))
            self._total_embedded += len(results)
            return results


class VectorIndexWriter:
    """Writes embedded vectors to partitioned vector index."""

    def __init__(self, batch_size: int = 100, flush_interval_seconds: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: Dict[str, List[EmbeddedChunk]] = defaultdict(list)  # partition -> chunks
        self._total_written = 0
        self._last_flush = time.time()

    async def write(self, chunks: List[EmbeddedChunk], partition_id: str):
        """Buffer chunks and flush when batch is full or timeout."""
        self._buffer[partition_id].extend(chunks)

        # Flush if batch full or timeout
        if (len(self._buffer[partition_id]) >= self.batch_size or
                time.time() - self._last_flush > self.flush_interval):
            await self._flush(partition_id)

    async def _flush(self, partition_id: str):
        """Write buffered vectors to index."""
        chunks = self._buffer.pop(partition_id, [])
        if not chunks:
            return

        # In production: vector_db.upsert(collection=partition_id, vectors=[...])
        logger.info(f"Flushing {len(chunks)} vectors to partition {partition_id}")
        await asyncio.sleep(0.01)  # Simulate write
        self._total_written += len(chunks)
        self._last_flush = time.time()

    async def flush_all(self):
        """Flush all buffered partitions."""
        for partition_id in list(self._buffer.keys()):
            await self._flush(partition_id)


class KeywordIndexWriter:
    """Writes chunks to keyword/BM25 index (Elasticsearch/OpenSearch)."""

    def __init__(self):
        self._total_indexed = 0

    async def index_chunks(self, chunks: List[Chunk], index_name: str):
        """Index chunks for keyword search."""
        # In production: elasticsearch.helpers.async_bulk(...)
        await asyncio.sleep(0.01)
        self._total_indexed += len(chunks)
        logger.debug(f"Indexed {len(chunks)} chunks to keyword index {index_name}")


# =============================================================================
# Queue and Job Management
# =============================================================================

class IngestionQueue:
    """Priority queue with per-tenant isolation and backpressure."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queues: Dict[Priority, deque] = {p: deque() for p in Priority}
        self._tenant_counts: Dict[str, int] = defaultdict(int)
        self._total_enqueued = 0
        self._total_dequeued = 0

    @property
    def depth(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def enqueue(self, job: IngestionJob) -> bool:
        """Enqueue job with backpressure check."""
        if self.depth >= self.max_size:
            logger.warning(f"Queue full ({self.depth}/{self.max_size}), applying backpressure")
            return False

        self._queues[job.priority].append(job)
        self._tenant_counts[job.tenant_id] += 1
        self._total_enqueued += 1
        return True

    def dequeue(self) -> Optional[IngestionJob]:
        """Dequeue highest priority job."""
        for priority in Priority:
            if self._queues[priority]:
                job = self._queues[priority].popleft()
                self._tenant_counts[job.tenant_id] -= 1
                self._total_dequeued += 1
                return job
        return None

    def get_tenant_queue_depth(self, tenant_id: str) -> int:
        return self._tenant_counts.get(tenant_id, 0)


class DeadLetterQueue:
    """Stores permanently failed jobs for manual review."""

    def __init__(self):
        self._items: List[IngestionJob] = []

    def add(self, job: IngestionJob):
        job.status = JobStatus.DEAD_LETTER
        self._items.append(job)
        logger.error(f"Job {job.job_id} sent to DLQ: {job.error}")

    @property
    def depth(self) -> int:
        return len(self._items)

    def get_all(self) -> List[IngestionJob]:
        return list(self._items)

    def retry_job(self, job_id: str) -> Optional[IngestionJob]:
        """Pull job from DLQ for retry."""
        for i, job in enumerate(self._items):
            if job.job_id == job_id:
                job.status = JobStatus.PENDING
                job.retry_count = 0
                return self._items.pop(i)
        return None


# =============================================================================
# Idempotency Store
# =============================================================================

class IdempotencyStore:
    """Tracks processed jobs to ensure exactly-once semantics."""

    def __init__(self):
        self._processed: Dict[str, datetime] = {}  # idempotency_key -> processed_at

    def is_processed(self, key: str) -> bool:
        return key in self._processed

    def mark_processed(self, key: str):
        self._processed[key] = datetime.utcnow()

    def cleanup(self, older_than: timedelta = timedelta(days=7)):
        """Remove old entries to prevent unbounded growth."""
        cutoff = datetime.utcnow() - older_than
        self._processed = {
            k: v for k, v in self._processed.items() if v > cutoff
        }


# =============================================================================
# Freshness & Regression Monitoring
# =============================================================================

class FreshnessMonitor:
    """Monitors ingestion freshness — time between source update and index availability."""

    def __init__(self, max_lag_seconds: float = 300):
        self.max_lag_seconds = max_lag_seconds
        self._ingestion_times: deque = deque(maxlen=1000)  # (source_time, index_time)

    def record_ingestion(self, source_updated_at: datetime, indexed_at: datetime):
        lag = (indexed_at - source_updated_at).total_seconds()
        self._ingestion_times.append((source_updated_at, indexed_at, lag))
        if lag > self.max_lag_seconds:
            logger.warning(f"Freshness SLO breach: {lag:.1f}s > {self.max_lag_seconds}s")

    def get_current_lag(self) -> float:
        if not self._ingestion_times:
            return 0.0
        return self._ingestion_times[-1][2]

    def get_avg_lag(self) -> float:
        if not self._ingestion_times:
            return 0.0
        return sum(t[2] for t in self._ingestion_times) / len(self._ingestion_times)

    def is_healthy(self) -> bool:
        return self.get_avg_lag() <= self.max_lag_seconds


class RetrievalRegressionMonitor:
    """
    Monitors recall quality after index updates.
    Uses golden queries with known expected results.
    """

    def __init__(self, golden_queries: List[Dict[str, Any]] = None):
        self.golden_queries = golden_queries or []
        self._results_history: List[Dict] = []

    def add_golden_query(self, query_vector: List[float], expected_doc_ids: List[str],
                         description: str = ""):
        self.golden_queries.append({
            "vector": query_vector,
            "expected_ids": set(expected_doc_ids),
            "description": description,
        })

    async def run_regression(self, search_fn: Callable) -> Dict[str, Any]:
        """
        Run golden queries against current index and measure recall.
        Should be called after every significant index update.
        """
        if not self.golden_queries:
            return {"status": "no_golden_queries", "recall": None}

        total_recall = 0.0
        failures = []

        for gq in self.golden_queries:
            results = await search_fn(gq["vector"], top_k=10)
            result_ids = {r["id"] for r in results}
            expected = gq["expected_ids"]

            recall = len(result_ids & expected) / len(expected) if expected else 1.0
            total_recall += recall

            if recall < 0.8:
                failures.append({
                    "description": gq.get("description", ""),
                    "recall": recall,
                    "missing": list(expected - result_ids),
                })

        avg_recall = total_recall / len(self.golden_queries)
        result = {
            "status": "pass" if avg_recall >= 0.9 else "fail",
            "avg_recall": avg_recall,
            "num_queries": len(self.golden_queries),
            "failures": failures,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._results_history.append(result)

        if avg_recall < 0.9:
            logger.error(f"RETRIEVAL REGRESSION: avg_recall={avg_recall:.3f} < 0.9")

        return result


# =============================================================================
# Ingestion Pipeline Orchestrator
# =============================================================================

class IngestionPipeline:
    """
    Main pipeline orchestrator. Coordinates all stages with backpressure.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.queue = IngestionQueue(max_size=self.config.get("queue_max_size", 10000))
        self.dlq = DeadLetterQueue()
        self.idempotency = IdempotencyStore()
        self.chunker = ChunkingService(
            chunk_size=self.config.get("chunk_size", 512),
            chunk_overlap=self.config.get("chunk_overlap", 50),
        )
        self.embedder = EmbeddingService(
            model=self.config.get("embedding_model", "text-embedding-3-small"),
            batch_size=self.config.get("embedding_batch_size", 64),
        )
        self.vector_writer = VectorIndexWriter(
            batch_size=self.config.get("index_batch_size", 100),
        )
        self.keyword_writer = KeywordIndexWriter()
        self.freshness = FreshnessMonitor(
            max_lag_seconds=self.config.get("max_freshness_lag_seconds", 300),
        )
        self.regression = RetrievalRegressionMonitor()
        self.sources: Dict[str, BaseSourceConnector] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._metrics = PipelineMetrics()

    # =========================================================================
    # Source Registration
    # =========================================================================

    def register_source(self, source_id: str, connector: BaseSourceConnector):
        self.sources[source_id] = connector
        logger.info(f"Registered source: {source_id}")

    # =========================================================================
    # Ingestion Submission
    # =========================================================================

    async def submit_document(self, doc: Document, priority: Priority = Priority.NORMAL) -> str:
        """Submit a document for ingestion. Returns job_id."""
        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            doc_id=doc.doc_id,
            source_id=doc.metadata.get("source", "unknown"),
            content_hash=doc.content_hash,
            tenant_id=doc.tenant_id,
            priority=priority,
        )

        # Idempotency check
        if self.idempotency.is_processed(job.idempotency_key):
            logger.debug(f"Skipping duplicate: {job.idempotency_key}")
            return job.job_id

        # Enqueue with backpressure
        if not self.queue.enqueue(job):
            raise RuntimeError("Pipeline backpressure: queue full, slow down submission")

        return job.job_id

    # =========================================================================
    # Processing Workers
    # =========================================================================

    async def start(self, num_workers: int = 4):
        """Start pipeline workers."""
        self._running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(f"worker_{i}"))
            self._workers.append(task)
        logger.info(f"Started {num_workers} pipeline workers")

    async def stop(self):
        """Gracefully stop pipeline."""
        self._running = False
        await self.vector_writer.flush_all()
        for task in self._workers:
            task.cancel()
        logger.info("Pipeline stopped")

    async def _worker_loop(self, worker_id: str):
        """Main worker loop: dequeue and process jobs."""
        while self._running:
            job = self.queue.dequeue()
            if not job:
                await asyncio.sleep(0.1)
                continue

            try:
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                await self._process_job(job)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                self.idempotency.mark_processed(job.idempotency_key)
                self._metrics.docs_ingested += 1
                self._metrics.last_ingestion_at = job.completed_at
            except Exception as e:
                job.error = str(e)
                job.retry_count += 1
                if job.retry_count >= job.max_retries:
                    self.dlq.add(job)
                    self._metrics.docs_failed += 1
                else:
                    # Re-enqueue with backoff
                    await asyncio.sleep(min(2 ** job.retry_count, 30))
                    self.queue.enqueue(job)
                    logger.warning(f"Retrying job {job.job_id} (attempt {job.retry_count})")

    async def _process_job(self, job: IngestionJob):
        """Full processing pipeline for a single document."""
        # Step 1: Fetch document (if needed)
        doc = Document(
            doc_id=job.doc_id,
            source_type=SourceType.API,
            content=f"Content for {job.doc_id}",  # In production: fetch from source
            tenant_id=job.tenant_id,
            metadata={"source_id": job.source_id},
        )

        # Step 2: Chunk
        chunks = self.chunker.chunk_document(doc)
        self._metrics.chunks_created += len(chunks)

        # Step 3: Embed
        embedded = await self.embedder.embed_batch(chunks)
        self._metrics.embeddings_generated += len(embedded)

        # Step 4: Write to vector index (partitioned by tenant)
        partition_id = f"tenant_{job.tenant_id}"
        await self.vector_writer.write(embedded, partition_id)
        self._metrics.vectors_indexed += len(embedded)

        # Step 5: Write to keyword index
        await self.keyword_writer.index_chunks(chunks, index_name=f"keywords_{job.tenant_id}")

        # Step 6: Record freshness
        self.freshness.record_ingestion(doc.updated_at, datetime.utcnow())

    # =========================================================================
    # Change Detection Sync
    # =========================================================================

    async def sync_source(self, source_id: str, tenant_id: str):
        """Sync a source: detect changes and submit jobs."""
        connector = self.sources.get(source_id)
        if not connector:
            raise ValueError(f"Source {source_id} not registered")

        added, modified, deleted = await connector.detect_changes()
        logger.info(f"Source {source_id}: +{len(added)}, ~{len(modified)}, -{len(deleted)}")

        # Submit new/modified for processing
        for doc_id in added + modified:
            doc_ref = {"doc_id": doc_id}
            doc = await connector.fetch_document(doc_ref)
            doc.tenant_id = tenant_id
            await self.submit_document(doc, Priority.NORMAL)

        # Handle deletions
        for doc_id in deleted:
            # In production: delete vectors with doc_id from index
            logger.info(f"Deleting vectors for removed doc: {doc_id}")

    # =========================================================================
    # Monitoring
    # =========================================================================

    def get_metrics(self) -> PipelineMetrics:
        self._metrics.queue_depth = self.queue.depth
        self._metrics.dlq_depth = self.dlq.depth
        self._metrics.freshness_lag_seconds = self.freshness.get_avg_lag()
        return self._metrics

    async def run_regression_check(self, search_fn: Callable) -> Dict[str, Any]:
        """Run retrieval regression after index update."""
        return await self.regression.run_regression(search_fn)


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    # Configure pipeline
    pipeline = IngestionPipeline({
        "chunk_size": 512,
        "chunk_overlap": 50,
        "embedding_model": "text-embedding-3-small",
        "embedding_batch_size": 32,
        "index_batch_size": 100,
        "queue_max_size": 5000,
        "max_freshness_lag_seconds": 60,
    })

    # Register sources
    s3_source = S3SourceConnector("s3_docs", {"bucket": "my-docs-bucket"})
    db_source = DatabaseSourceConnector("pg_docs", {"connection": "postgresql://..."})
    pipeline.register_source("s3_docs", s3_source)
    pipeline.register_source("pg_docs", db_source)

    # Start workers
    await pipeline.start(num_workers=4)

    # Submit documents
    for i in range(20):
        doc = Document(
            doc_id=f"doc_{i:04d}",
            source_type=SourceType.API,
            content=f"This is document {i} with content about vector databases and sharding strategies.",
            tenant_id="acme_corp",
            metadata={"title": f"Document {i}", "department": "engineering"},
        )
        await pipeline.submit_document(doc, Priority.NORMAL)

    # Let workers process
    await asyncio.sleep(2)

    # Check metrics
    metrics = pipeline.get_metrics()
    print(f"Ingested: {metrics.docs_ingested}")
    print(f"Failed: {metrics.docs_failed}")
    print(f"Queue depth: {metrics.queue_depth}")
    print(f"DLQ depth: {metrics.dlq_depth}")
    print(f"Freshness lag: {metrics.freshness_lag_seconds:.1f}s")

    # Sync from source
    await pipeline.sync_source("s3_docs", "acme_corp")

    # Stop
    await pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
