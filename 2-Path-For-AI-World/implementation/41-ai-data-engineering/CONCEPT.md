# AI Data Engineering: Keeping RAG Systems Current in Production

## Why This Matters

Building a RAG demo takes a weekend. Keeping it accurate, fresh, and reliable in production
takes an entire engineering discipline. This is AI Data Engineering — the operational pipeline
work that ensures your AI system reflects reality, not a stale snapshot from 3 months ago.

Most RAG failures in production aren't retrieval failures or LLM hallucinations. They're
**data freshness failures**: the system confidently answers based on outdated information
because the pipeline that keeps it current is broken, slow, or nonexistent.

---

## 1. Change Data Capture (CDC) for AI

### The Problem

Your knowledge lives in Confluence, Google Drive, Slack, databases, GitHub repos. These sources
change constantly. Your vector store needs to reflect those changes in near-real-time.

### How CDC Works for AI Systems

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOURCE SYSTEMS                                 │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│Confluence│  Slack   │  GitHub  │ Database │  Google Drive        │
│ Webhooks │ Events   │ Webhooks │  WAL/CDC │  Push Notifications  │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────┬──────────────┘
     │          │          │          │            │
     ▼          ▼          ▼          ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│              CDC EVENT BUS (Kafka / EventBridge)                  │
│                                                                   │
│  Event Schema:                                                    │
│  {                                                                │
│    "source": "confluence",                                        │
│    "operation": "UPDATE",    // CREATE | UPDATE | DELETE           │
│    "document_id": "page-12345",                                   │
│    "timestamp": "2024-01-15T10:30:00Z",                          │
│    "version": 47,                                                 │
│    "changed_by": "user@company.com",                             │
│    "change_summary": "Updated pricing section",                   │
│    "content_hash": "sha256:abc123..."                            │
│  }                                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              INGESTION PIPELINE                                    │
│                                                                   │
│  1. Fetch full document content                                   │
│  2. Diff against previous version (if UPDATE)                     │
│  3. Determine affected chunks                                     │
│  4. Re-chunk affected sections only                               │
│  5. Generate embeddings for new/changed chunks                    │
│  6. Upsert to vector store                                        │
│  7. Invalidate caches                                             │
│  8. Update lineage metadata                                       │
└─────────────────────────────────────────────────────────────────┘
```

### CDC Strategies by Source Type

| Source | CDC Mechanism | Latency | Reliability |
|--------|--------------|---------|-------------|
| Confluence | Webhooks + polling fallback | 1-5 min | Medium (webhooks can be lost) |
| Slack | Events API (socket mode) | Seconds | High |
| GitHub | Webhooks + GitHub Apps | Seconds | High |
| PostgreSQL | Logical replication / Debezium | Seconds | Very High |
| Google Drive | Push notifications + polling | 1-10 min | Medium |
| SharePoint | Microsoft Graph subscriptions | 1-5 min | Medium |
| S3 | Event notifications → SQS | Seconds | Very High |

### Handling Webhook Unreliability

Webhooks are fire-and-forget. They can be lost due to network issues, service outages, or
misconfiguration. You need a reconciliation strategy:

```python
class CDCReconciler:
    """
    Hybrid approach: webhooks for low-latency + periodic full scan for consistency.
    """
    
    def __init__(self, source_client, vector_store, reconcile_interval_hours=6):
        self.source_client = source_client
        self.vector_store = vector_store
        self.reconcile_interval = reconcile_interval_hours
    
    async def handle_webhook(self, event: CDCEvent):
        """Real-time path: process individual changes as they arrive."""
        if event.operation == "DELETE":
            await self.propagate_deletion(event.document_id)
        elif event.operation in ("CREATE", "UPDATE"):
            await self.process_document_change(event.document_id, event.version)
        
        # Record that we processed this event
        await self.mark_processed(event)
    
    async def periodic_reconciliation(self):
        """
        Batch path: scan all documents and compare against what's indexed.
        Catches any missed webhooks, handles drift.
        """
        source_manifest = await self.source_client.list_all_documents()
        indexed_manifest = await self.vector_store.list_all_document_ids()
        
        # Find documents in source but not in index (missed CREATE)
        missing = source_manifest.keys() - indexed_manifest.keys()
        for doc_id in missing:
            await self.process_document_change(doc_id, source_manifest[doc_id].version)
        
        # Find documents in index but not in source (missed DELETE)
        orphaned = indexed_manifest.keys() - source_manifest.keys()
        for doc_id in orphaned:
            await self.propagate_deletion(doc_id)
        
        # Find documents with version mismatch (missed UPDATE)
        for doc_id in source_manifest.keys() & indexed_manifest.keys():
            if source_manifest[doc_id].version != indexed_manifest[doc_id].version:
                await self.process_document_change(doc_id, source_manifest[doc_id].version)
```

### Ordering Guarantees

CDC events can arrive out of order. If you receive UPDATE v5 before UPDATE v4, you must:

1. **Use version numbers**: Always store the version you indexed. Reject older versions.
2. **Idempotent processing**: Processing the same event twice must produce the same result.
3. **Partition by document**: Route events for the same document to the same consumer to ensure ordering per-document.

---

## 2. Incremental Indexing

### The Problem

Re-embedding your entire corpus on every change is prohibitively expensive. With 1M documents
at $0.0001 per 1K tokens, a full re-index costs ~$500-2000 and takes hours. You need to
re-embed only what changed.

### Document-Level vs Chunk-Level Tracking

```
Document: "Engineering Handbook v47" (50 pages)
├── Chunk 1: "Introduction" (unchanged since v45)
├── Chunk 2: "Setup Guide" (unchanged since v46)  
├── Chunk 3: "API Reference" (CHANGED in v47)     ← only re-embed this
├── Chunk 4: "Troubleshooting" (unchanged since v43)
└── Chunk 5: "FAQ" (unchanged since v44)
```

### Content-Hash Based Change Detection

```python
import hashlib
from dataclasses import dataclass

@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    content_hash: str
    embedding_model: str
    embedding_vector: list[float]
    chunk_index: int
    created_at: datetime
    updated_at: datetime

class IncrementalIndexer:
    def __init__(self, chunk_store, embedding_service, vector_store):
        self.chunk_store = chunk_store
        self.embedding_service = embedding_service
        self.vector_store = vector_store
    
    async def process_document_update(self, doc_id: str, new_content: str):
        # 1. Chunk the new content
        new_chunks = self.chunker.chunk(new_content)
        
        # 2. Compute hashes for new chunks
        new_hashes = {
            i: hashlib.sha256(chunk.encode()).hexdigest()
            for i, chunk in enumerate(new_chunks)
        }
        
        # 3. Get existing chunk records for this document
        existing_records = await self.chunk_store.get_by_document(doc_id)
        existing_hashes = {r.chunk_index: r.content_hash for r in existing_records}
        
        # 4. Determine what changed
        to_embed = []  # New or modified chunks
        to_delete = [] # Chunks that no longer exist
        unchanged = [] # Chunks that haven't changed
        
        for i, chunk in enumerate(new_chunks):
            if i not in existing_hashes:
                to_embed.append((i, chunk))  # New chunk
            elif new_hashes[i] != existing_hashes[i]:
                to_embed.append((i, chunk))  # Modified chunk
            else:
                unchanged.append(i)
        
        # Chunks beyond the new document length are deleted
        for i in existing_hashes:
            if i >= len(new_chunks):
                to_delete.append(i)
        
        # 5. Only embed changed chunks
        if to_embed:
            texts = [chunk for _, chunk in to_embed]
            embeddings = await self.embedding_service.embed_batch(texts)
            
            for (i, chunk), embedding in zip(to_embed, embeddings):
                await self.vector_store.upsert(
                    id=f"{doc_id}_chunk_{i}",
                    vector=embedding,
                    metadata={"document_id": doc_id, "chunk_index": i, "content": chunk}
                )
                await self.chunk_store.upsert(ChunkRecord(
                    chunk_id=f"{doc_id}_chunk_{i}",
                    document_id=doc_id,
                    content_hash=new_hashes[i],
                    embedding_model=self.embedding_service.model_name,
                    embedding_vector=embedding,
                    chunk_index=i,
                    updated_at=datetime.utcnow()
                ))
        
        # 6. Delete removed chunks
        for i in to_delete:
            await self.vector_store.delete(f"{doc_id}_chunk_{i}")
            await self.chunk_store.delete(f"{doc_id}_chunk_{i}")
        
        return IncrementalResult(
            embedded=len(to_embed),
            deleted=len(to_delete),
            unchanged=len(unchanged),
            cost_saved_pct=len(unchanged) / max(len(new_chunks), 1) * 100
        )
```

### Chunking Boundary Stability

A critical subtlety: if your chunking strategy uses overlapping windows or semantic boundaries,
a small change in one section can cascade into different chunk boundaries for the entire document.
This defeats incremental indexing.

**Solution: Anchor-based chunking**

```python
class StableChunker:
    """
    Chunks documents using stable anchors (headings, paragraph breaks) so that
    changes in one section don't shift chunk boundaries elsewhere.
    """
    
    def chunk(self, content: str) -> list[Chunk]:
        # Split on structural boundaries (headings, HR, double newlines)
        sections = self.split_on_structure(content)
        
        chunks = []
        for section in sections:
            if len(section) <= self.max_chunk_size:
                chunks.append(section)
            else:
                # Sub-split large sections, but only within this section
                sub_chunks = self.split_large_section(section)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def split_on_structure(self, content: str) -> list[str]:
        """Split on headings and major structural elements."""
        import re
        # Markdown headings, HTML headings, or double newlines
        pattern = r'(?=^#{1,3}\s|\n\n\n)'
        return [s.strip() for s in re.split(pattern, content, flags=re.MULTILINE) if s.strip()]
```

---

## 3. Document Deletion Propagation

### The Problem

When a document is deleted from the source system, you must remove all traces from:
- Vector store (all chunks)
- Semantic cache (any cached queries that referenced this document)
- Conversation memory (historical references)
- Evaluation datasets (test cases built from this document)
- Search indices (BM25/keyword search)
- Knowledge graph nodes and edges

### Cascade Delete Architecture

```
DELETE event for document "policy-123"
         │
         ▼
┌─────────────────────────────┐
│   DELETION ORCHESTRATOR      │
│                              │
│   1. Record deletion intent  │
│   2. Fan out to all stores   │
│   3. Verify completion       │
│   4. Audit log               │
└──────┬──────────────────────┘
       │
       ├──► Vector Store: DELETE WHERE document_id = "policy-123"
       │    (deletes all chunks: policy-123_chunk_0 through policy-123_chunk_N)
       │
       ├──► Semantic Cache: INVALIDATE WHERE source_docs CONTAINS "policy-123"
       │    (removes cached Q&A pairs that cited this document)
       │
       ├──► BM25 Index: DELETE WHERE document_id = "policy-123"
       │
       ├──► Knowledge Graph: DELETE node AND edges WHERE source = "policy-123"
       │
       ├──► Eval Dataset: FLAG WHERE ground_truth_source = "policy-123"
       │    (don't auto-delete; flag for human review)
       │
       └──► Audit Log: APPEND {deleted: "policy-123", timestamp, reason, actor}
```

### Soft Delete vs Hard Delete

```python
class DeletionManager:
    """
    Implements soft-delete with configurable retention for compliance.
    Hard-deletes after retention period or on explicit purge request.
    """
    
    async def soft_delete(self, doc_id: str, reason: str, actor: str):
        """Mark as deleted but retain for recovery/audit."""
        # Remove from active index (invisible to queries)
        await self.vector_store.update_metadata(
            filter={"document_id": doc_id},
            metadata={"_deleted": True, "_deleted_at": datetime.utcnow().isoformat()}
        )
        
        # Remove from cache immediately
        await self.cache.invalidate_by_source(doc_id)
        
        # Schedule hard delete after retention period
        await self.scheduler.schedule(
            task=self.hard_delete,
            args=(doc_id,),
            run_at=datetime.utcnow() + timedelta(days=self.retention_days)
        )
    
    async def hard_delete(self, doc_id: str):
        """Permanently remove all traces. Irreversible."""
        await self.vector_store.delete(filter={"document_id": doc_id})
        await self.chunk_store.delete(filter={"document_id": doc_id})
        await self.lineage_store.delete(filter={"document_id": doc_id})
        await self.audit_log.append({
            "action": "HARD_DELETE",
            "document_id": doc_id,
            "timestamp": datetime.utcnow().isoformat()
        })
```

### The "Ghost Reference" Problem

Even after deleting a document, historical conversations may reference it. Users might ask
"What did that deleted policy say?" You need a strategy:

1. **Tombstone approach**: Replace content with "This document has been deleted on [date]"
2. **Reference invalidation**: Mark historical citations as "[source no longer available]"
3. **Compliance purge**: For GDPR/legal, actively scrub from conversation logs too

---

## 4. Schema Evolution

### The Problem

Your chunking strategy will change. Your embedding model will be upgraded. Your metadata
schema will evolve. How do you migrate without rebuilding everything from scratch?

### Types of Schema Changes

| Change Type | Impact | Migration Strategy |
|-------------|--------|-------------------|
| New metadata field | Low | Backfill existing records |
| Chunk size change | High | Re-chunk + re-embed affected docs |
| Embedding model upgrade | Critical | Full re-embedding (see Section 9) |
| Vector dimensions change | Critical | New collection + migration |
| Scoring/ranking change | Medium | No data change; update query logic |
| Adding hybrid search (BM25) | Medium | Build keyword index alongside |

### Version-Aware Schema

```python
SCHEMA_VERSIONS = {
    "v1": {
        "chunker": "recursive_text_splitter",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "embedding_model": "text-embedding-ada-002",
        "embedding_dimensions": 1536,
        "metadata_fields": ["source", "title", "created_at"]
    },
    "v2": {
        "chunker": "semantic_chunker",
        "chunk_size": 1024,
        "chunk_overlap": 100,
        "embedding_model": "text-embedding-3-large",
        "embedding_dimensions": 3072,
        "metadata_fields": ["source", "title", "created_at", "author", "department", "access_level"]
    }
}

class SchemaManager:
    def __init__(self, current_version: str = "v2"):
        self.current = SCHEMA_VERSIONS[current_version]
        self.version = current_version
    
    def needs_reprocessing(self, chunk_record: ChunkRecord) -> bool:
        """Determine if a chunk needs reprocessing under current schema."""
        if chunk_record.schema_version == self.version:
            return False
        
        old_schema = SCHEMA_VERSIONS[chunk_record.schema_version]
        
        # Embedding model changed → must re-embed
        if old_schema["embedding_model"] != self.current["embedding_model"]:
            return True
        
        # Chunk strategy changed → must re-chunk and re-embed
        if (old_schema["chunker"] != self.current["chunker"] or
            old_schema["chunk_size"] != self.current["chunk_size"]):
            return True
        
        # Only metadata changed → backfill, don't re-embed
        return False
    
    def needs_metadata_backfill(self, chunk_record: ChunkRecord) -> bool:
        """Check if chunk just needs metadata updates (cheaper than re-embedding)."""
        old_schema = SCHEMA_VERSIONS[chunk_record.schema_version]
        new_fields = set(self.current["metadata_fields"]) - set(old_schema["metadata_fields"])
        return len(new_fields) > 0 and not self.needs_reprocessing(chunk_record)
```

### Migration Execution Pattern

```
Phase 1: Deploy new schema alongside old (dual-write)
    - New documents use v2 schema
    - Old documents remain on v1
    - Queries search both collections

Phase 2: Background migration
    - Worker pool re-processes v1 documents into v2
    - Progress tracking: 0/1,000,000 → ... → 1,000,000/1,000,000
    - Rate-limited to avoid API throttling

Phase 3: Validation
    - Compare query results between v1-only and v2-only
    - Ensure quality hasn't degraded
    - Run eval suite against v2 collection

Phase 4: Cutover
    - Switch queries to v2-only
    - Keep v1 as read-only backup for 7 days
    - Drop v1 collection
```

---

## 5. Data Contracts

### The Problem

Your AI system depends on data from Confluence, Slack, databases, and other sources. Without
explicit contracts, you discover problems only when users complain about wrong answers.

### Contract Definition

```yaml
# data_contracts/confluence_to_rag.yaml
contract:
  name: "Confluence → RAG Pipeline"
  version: "2.1"
  owner: "ai-platform-team"
  
  producer:
    system: "Confluence Cloud"
    team: "knowledge-management"
    contact: "km-team@company.com"
  
  consumer:
    system: "RAG Knowledge Base"
    team: "ai-platform"
    contact: "ai-platform@company.com"
  
  sla:
    freshness:
      target: "5 minutes"
      degraded: "30 minutes"
      critical: "2 hours"
      measurement: "time from source update to searchable in RAG"
    
    availability:
      target: "99.9%"
      measurement: "webhook delivery success rate"
    
    completeness:
      target: "100% of public space pages"
      exclusions: ["archived spaces", "draft pages", "personal spaces"]
    
    quality:
      min_content_length: 50  # characters; reject shorter
      max_content_length: 500000  # characters; split larger
      required_fields: ["title", "body", "space_key", "last_modified", "author"]
      encoding: "UTF-8"
      format: "HTML (Confluence storage format)"
  
  schema:
    fields:
      - name: "page_id"
        type: "string"
        required: true
        description: "Unique Confluence page identifier"
      - name: "title"
        type: "string"
        required: true
        max_length: 500
      - name: "body"
        type: "html"
        required: true
        description: "Page content in Confluence storage format"
      - name: "space_key"
        type: "string"
        required: true
      - name: "last_modified"
        type: "ISO8601 datetime"
        required: true
      - name: "author"
        type: "string"
        required: true
      - name: "labels"
        type: "array[string]"
        required: false
      - name: "restrictions"
        type: "object"
        required: true
        description: "Page-level access restrictions"
  
  alerting:
    freshness_breach:
      channel: "#ai-platform-alerts"
      severity: "P2"
      escalation: "page ai-platform on-call after 1 hour"
    
    quality_breach:
      channel: "#ai-platform-alerts"  
      severity: "P3"
      threshold: "error rate > 5% over 15 minutes"
  
  monitoring:
    dashboard: "https://grafana.internal/d/confluence-rag-pipeline"
    metrics:
      - "pipeline.confluence.events_received"
      - "pipeline.confluence.events_processed"
      - "pipeline.confluence.processing_latency_p99"
      - "pipeline.confluence.error_rate"
      - "pipeline.confluence.freshness_lag_seconds"
```

### Contract Enforcement

```python
class DataContractValidator:
    def __init__(self, contract: DataContract):
        self.contract = contract
    
    def validate_document(self, doc: dict) -> ValidationResult:
        errors = []
        warnings = []
        
        # Required fields
        for field in self.contract.schema.required_fields:
            if field not in doc or doc[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Content length
        if "body" in doc:
            if len(doc["body"]) < self.contract.sla.quality.min_content_length:
                errors.append(f"Content too short: {len(doc['body'])} chars")
            if len(doc["body"]) > self.contract.sla.quality.max_content_length:
                warnings.append(f"Content exceeds max length, will be split")
        
        # Encoding
        if "body" in doc:
            try:
                doc["body"].encode("utf-8")
            except UnicodeEncodeError:
                errors.append("Content contains invalid UTF-8 characters")
        
        # Freshness (for updates)
        if "last_modified" in doc:
            age = datetime.utcnow() - parse_datetime(doc["last_modified"])
            if age > timedelta(hours=2):
                warnings.append(f"Document age {age} exceeds critical freshness threshold")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

---

## 6. Data Quality Checks

### The Problem

Garbage in, garbage out. If corrupted documents enter your vector store, users get nonsensical
answers and lose trust in the system.

### Quality Gate Pipeline

```
Document arrives
      │
      ▼
┌──────────────┐     REJECT      ┌──────────────┐
│ Format Check │────────────────► │ Dead Letter  │
│              │                   │    Queue     │
└──────┬───────┘                   └──────────────┘
       │ PASS
       ▼
┌──────────────┐     REJECT      ┌──────────────┐
│Content Check │────────────────► │ Dead Letter  │
│              │                   │    Queue     │
└──────┬───────┘                   └──────────────┘
       │ PASS
       ▼
┌──────────────┐     WARN        ┌──────────────┐
│Quality Score │────────────────► │  Low Quality │
│              │                   │    Index     │
└──────┬───────┘                   └──────────────┘
       │ HIGH QUALITY
       ▼
┌──────────────┐
│  Embed &     │
│  Index       │
└──────────────┘
```

### Specific Quality Checks

```python
class DocumentQualityGate:
    
    def check_format(self, doc: RawDocument) -> QualityResult:
        """Validate document can be parsed and is not corrupt."""
        checks = []
        
        # PDF corruption
        if doc.mime_type == "application/pdf":
            try:
                pages = extract_pdf_text(doc.content)
                if not pages:
                    return QualityResult.reject("PDF has no extractable text")
                # Check for garbled text (common with scanned PDFs without OCR)
                garble_ratio = self._compute_garble_ratio(pages)
                if garble_ratio > 0.3:
                    return QualityResult.reject(f"PDF appears garbled ({garble_ratio:.0%} non-ASCII)")
            except Exception as e:
                return QualityResult.reject(f"PDF parsing failed: {e}")
        
        # HTML validity
        if doc.mime_type == "text/html":
            text = strip_html(doc.content)
            if len(text.strip()) < 20:
                return QualityResult.reject("HTML contains no meaningful text after stripping tags")
        
        # Encoding detection
        if isinstance(doc.content, bytes):
            detected = chardet.detect(doc.content)
            if detected["confidence"] < 0.7:
                return QualityResult.reject(f"Uncertain encoding: {detected}")
        
        return QualityResult.pass_()
    
    def check_content(self, doc: ParsedDocument) -> QualityResult:
        """Validate content is meaningful and appropriate for indexing."""
        
        # Empty or near-empty after extraction
        if len(doc.text.strip()) < 50:
            return QualityResult.reject("Content too short after extraction")
        
        # Repeated content (copy-paste artifacts)
        lines = doc.text.split("\n")
        unique_lines = set(lines)
        if len(unique_lines) < len(lines) * 0.5:
            return QualityResult.warn("High repetition ratio — possible template/boilerplate")
        
        # Language detection (reject if not in expected languages)
        detected_lang = detect_language(doc.text[:1000])
        if detected_lang not in self.expected_languages:
            return QualityResult.warn(f"Unexpected language: {detected_lang}")
        
        # Binary/encoded content leaked into text
        if re.search(r'[^\x00-\x7F]{100,}', doc.text):
            return QualityResult.reject("Contains long sequences of non-ASCII (possible binary leak)")
        
        return QualityResult.pass_()
    
    def check_chunk_quality(self, chunk: str) -> QualityResult:
        """Validate individual chunks before embedding."""
        
        # Too short to be meaningful
        if len(chunk.split()) < 10:
            return QualityResult.reject("Chunk has fewer than 10 words")
        
        # Table-only chunks (low semantic value for embedding)
        if chunk.count("|") > chunk.count(" ") * 0.3:
            return QualityResult.warn("Chunk appears to be mostly tabular data")
        
        # Code-only chunks (might want separate handling)
        code_indicators = chunk.count("{") + chunk.count("}") + chunk.count(";")
        if code_indicators > len(chunk) * 0.1:
            return QualityResult.warn("Chunk appears to be mostly code")
        
        return QualityResult.pass_()
    
    def _compute_garble_ratio(self, text: str) -> float:
        """Ratio of characters that are likely garbled (control chars, weird symbols)."""
        garbled = sum(1 for c in text if ord(c) > 0xFFFF or (ord(c) < 32 and c not in '\n\r\t'))
        return garbled / max(len(text), 1)
```

---

## 7. Duplicate Detection

### The Problem

The same content often exists in multiple places: a Slack message that quotes a Confluence page,
a GitHub README that's also in the docs site, an email that's also a Jira ticket. Indexing all
copies means retrieval returns redundant results and wastes vector store capacity.

### Duplicate Detection Strategies

**Exact duplicates**: Content hash comparison (fast, simple)

```python
def detect_exact_duplicates(chunks: list[Chunk]) -> list[set[str]]:
    """Group chunks by content hash. O(n) time."""
    hash_to_chunks = defaultdict(set)
    for chunk in chunks:
        h = hashlib.sha256(chunk.content.encode()).hexdigest()
        hash_to_chunks[h].add(chunk.id)
    return [group for group in hash_to_chunks.values() if len(group) > 1]
```

**Near-duplicates**: MinHash/LSH for similarity detection

```python
from datasketch import MinHash, MinHashLSH

class NearDuplicateDetector:
    def __init__(self, threshold=0.8, num_perm=128):
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.num_perm = num_perm
    
    def compute_minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=self.num_perm)
        # Shingle the text (3-word sliding window)
        words = text.lower().split()
        for i in range(len(words) - 2):
            shingle = " ".join(words[i:i+3])
            m.update(shingle.encode("utf-8"))
        return m
    
    def add_document(self, doc_id: str, text: str):
        mh = self.compute_minhash(text)
        self.lsh.insert(doc_id, mh)
    
    def find_duplicates(self, doc_id: str, text: str) -> list[str]:
        mh = self.compute_minhash(text)
        return self.lsh.query(mh)
```

### Deduplication Strategy: Canonical Source

When duplicates are found, keep the **canonical** version:

1. Prefer the **authoritative source** (Confluence > Slack, Docs > Email)
2. Prefer the **most recent** version
3. Store cross-references as metadata: `{"canonical_id": "...", "also_found_in": [...]}`

---

## 8. Source Freshness SLAs

### Defining Freshness

```
Freshness = now() - max(source_last_modified, indexed_at)

Tiers:
  Real-time:  < 1 minute  (Slack messages, live docs)
  Near-real:  < 5 minutes (Confluence, GitHub)
  Periodic:   < 1 hour    (Email archives, old wikis)
  Batch:      < 24 hours  (Quarterly reports, legal docs)
```

### Freshness Monitoring

```python
class FreshnessMonitor:
    def __init__(self, sources: list[DataSource], alerting: AlertingService):
        self.sources = sources
        self.alerting = alerting
    
    async def check_freshness(self):
        """Run every minute. Check each source against its SLA."""
        for source in self.sources:
            last_event_time = await self.get_last_event_time(source)
            lag = datetime.utcnow() - last_event_time
            
            # Emit metric
            metrics.gauge(
                "pipeline.freshness_lag_seconds",
                lag.total_seconds(),
                tags={"source": source.name}
            )
            
            # Check against SLA tiers
            if lag > source.sla.critical:
                await self.alerting.page(
                    severity="P1",
                    message=f"CRITICAL: {source.name} freshness lag is {lag} (SLA: {source.sla.critical})"
                )
            elif lag > source.sla.degraded:
                await self.alerting.alert(
                    severity="P2",
                    message=f"DEGRADED: {source.name} freshness lag is {lag} (SLA: {source.sla.degraded})"
                )
    
    async def get_last_event_time(self, source: DataSource) -> datetime:
        """Get the timestamp of the most recently processed event from this source."""
        return await self.event_store.get_latest_processed_timestamp(source.name)
```

### Freshness Dashboard Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `freshness_lag_seconds` | Time since last successful sync per source | > SLA target |
| `events_pending` | Number of unprocessed CDC events in queue | > 1000 |
| `processing_rate` | Events processed per second | < 50% of normal |
| `last_full_reconciliation` | Time since last full consistency check | > 24 hours |
| `stale_document_count` | Documents not updated despite source changes | > 0 |

---

## 9. Embedding Regeneration Strategy

### The Problem

You need to upgrade from `text-embedding-ada-002` to `text-embedding-3-large`. You have 10M
chunks. At $0.13 per 1M tokens and ~200 tokens per chunk, that's ~$260 in API costs but
potentially days of processing time. You cannot have downtime.

### Migration Architecture

```
┌──────────────────────────────────────────────────────┐
│                  DUAL-INDEX PERIOD                      │
│                                                        │
│  Collection A (ada-002, 1536 dims)  ← existing queries│
│  Collection B (3-large, 3072 dims)  ← being populated │
│                                                        │
│  Query Router:                                         │
│    - 100% traffic → Collection A (default)             │
│    - Shadow queries → Collection B (for comparison)    │
│    - Gradual shift: 90/10 → 70/30 → 50/50 → 0/100   │
└──────────────────────────────────────────────────────┘
```

### Batch Re-embedding Pipeline

```python
class EmbeddingMigrationPipeline:
    def __init__(self, old_collection, new_collection, new_model, batch_size=100):
        self.old_collection = old_collection
        self.new_collection = new_collection
        self.new_model = new_model
        self.batch_size = batch_size
    
    async def migrate(self, concurrency=10, rate_limit_rpm=3000):
        """
        Re-embed all documents from old collection into new collection.
        Rate-limited to stay within API limits.
        """
        total = await self.old_collection.count()
        processed = 0
        semaphore = asyncio.Semaphore(concurrency)
        rate_limiter = RateLimiter(max_per_minute=rate_limit_rpm)
        
        async def process_batch(batch):
            nonlocal processed
            async with semaphore:
                await rate_limiter.acquire(len(batch))
                
                texts = [doc["content"] for doc in batch]
                new_embeddings = await self.new_model.embed_batch(texts)
                
                # Upsert to new collection with same IDs and metadata
                records = [
                    {
                        "id": doc["id"],
                        "vector": emb,
                        "metadata": doc["metadata"]
                    }
                    for doc, emb in zip(batch, new_embeddings)
                ]
                await self.new_collection.upsert_batch(records)
                
                processed += len(batch)
                if processed % 10000 == 0:
                    logger.info(f"Migration progress: {processed}/{total} ({processed/total*100:.1f}%)")
        
        # Stream through old collection in batches
        async for batch in self.old_collection.scroll(batch_size=self.batch_size):
            await process_batch(batch)
        
        logger.info(f"Migration complete: {processed} documents re-embedded")
```

### Quality Validation During Migration

```python
class MigrationValidator:
    """Compare retrieval quality between old and new embeddings."""
    
    def __init__(self, test_queries: list[str], ground_truth: dict[str, list[str]]):
        self.test_queries = test_queries
        self.ground_truth = ground_truth
    
    async def validate(self, old_collection, new_collection) -> ValidationReport:
        results = []
        
        for query in self.test_queries:
            old_results = await old_collection.search(query, top_k=10)
            new_results = await new_collection.search(query, top_k=10)
            
            # Compare recall against ground truth
            expected = set(self.ground_truth.get(query, []))
            old_recall = len(set(r.id for r in old_results) & expected) / max(len(expected), 1)
            new_recall = len(set(r.id for r in new_results) & expected) / max(len(expected), 1)
            
            results.append({
                "query": query,
                "old_recall": old_recall,
                "new_recall": new_recall,
                "improvement": new_recall - old_recall
            })
        
        avg_old = sum(r["old_recall"] for r in results) / len(results)
        avg_new = sum(r["new_recall"] for r in results) / len(results)
        
        return ValidationReport(
            avg_old_recall=avg_old,
            avg_new_recall=avg_new,
            improvement=avg_new - avg_old,
            regression_queries=[r for r in results if r["improvement"] < -0.1],
            safe_to_cutover=avg_new >= avg_old * 0.95  # Allow 5% tolerance
        )
```

---

## 10. Index Migration (Vector DB to Vector DB)

### The Problem

You need to move from Pinecone to Qdrant, or from one Qdrant collection to another with a
different schema. Zero downtime required.

### Migration Pattern: Blue-Green

```
Phase 1: Set up new store (Green)
    - Create new collection with target schema
    - Verify connectivity and configuration

Phase 2: Dual-write
    - All writes go to both Old (Blue) and New (Green)
    - Reads still from Blue only
    - Duration: until Green is fully populated

Phase 3: Backfill
    - Copy all existing data from Blue → Green
    - Reconcile: verify counts match, spot-check random records

Phase 4: Shadow reads
    - Query both Blue and Green
    - Compare results (log discrepancies, don't serve Green results yet)
    - Fix any issues found

Phase 5: Cutover
    - Switch reads to Green
    - Keep dual-write for safety (24-48 hours)
    - Monitor error rates and latency

Phase 6: Decommission
    - Stop writes to Blue
    - Keep Blue read-only for 7 days (rollback safety)
    - Delete Blue
```

### Implementation

```python
class DualWriteProxy:
    """Proxy that writes to both old and new vector stores during migration."""
    
    def __init__(self, primary, secondary, mode="dual_write"):
        self.primary = primary      # Currently serving reads
        self.secondary = secondary  # Being populated
        self.mode = mode            # dual_write | shadow_read | cutover
    
    async def upsert(self, id, vector, metadata):
        # Always write to primary
        await self.primary.upsert(id, vector, metadata)
        
        # Write to secondary (best-effort during migration)
        try:
            await self.secondary.upsert(id, vector, metadata)
        except Exception as e:
            logger.warning(f"Secondary write failed for {id}: {e}")
            await self.retry_queue.enqueue(("upsert", id, vector, metadata))
    
    async def search(self, query_vector, top_k=10, filter=None):
        if self.mode == "dual_write":
            return await self.primary.search(query_vector, top_k, filter)
        
        elif self.mode == "shadow_read":
            # Query both, serve primary, log differences
            primary_results, secondary_results = await asyncio.gather(
                self.primary.search(query_vector, top_k, filter),
                self.secondary.search(query_vector, top_k, filter)
            )
            self._log_comparison(primary_results, secondary_results)
            return primary_results
        
        elif self.mode == "cutover":
            return await self.secondary.search(query_vector, top_k, filter)
```

---

## 11. Metadata Backfill

### The Problem

You've added a `department` field to your metadata schema. 500K existing chunks don't have
this field. You need to backfill without re-embedding.

### Backfill Pipeline

```python
class MetadataBackfiller:
    """Add or update metadata fields on existing vector store records without re-embedding."""
    
    async def backfill_department(self, batch_size=500):
        """Example: Add department field by looking up source document's author."""
        
        cursor = None
        updated = 0
        
        while True:
            # Scroll through all records missing the field
            batch, cursor = await self.vector_store.scroll(
                filter={"department": {"$exists": False}},
                limit=batch_size,
                cursor=cursor
            )
            
            if not batch:
                break
            
            # Look up department for each document's author
            updates = []
            for record in batch:
                author = record.metadata.get("author")
                if author:
                    department = await self.directory_service.get_department(author)
                    updates.append((record.id, {"department": department}))
            
            # Batch update metadata (no re-embedding needed)
            await self.vector_store.update_metadata_batch(updates)
            updated += len(updates)
            
            logger.info(f"Backfilled {updated} records")
        
        return updated
```

---

## 12. Multi-Region Replication

### The Problem

Your users are global. Vector search latency from US-East when your user is in Singapore is
200-400ms. You need replicas.

### Replication Topologies

```
Option A: Single-writer, multi-reader
    US-East (PRIMARY) ──replicate──► EU-West (REPLICA)
                       ──replicate──► AP-Southeast (REPLICA)
    
    Writes: Only to primary
    Reads: Routed to nearest region
    Consistency: Eventually consistent (seconds to minutes lag)

Option B: Multi-writer with conflict resolution
    US-East ◄──sync──► EU-West ◄──sync──► AP-Southeast
    
    Writes: To nearest region
    Conflicts: Last-writer-wins by timestamp
    Consistency: Eventual with conflict resolution
```

### Consistency Considerations for AI

For most RAG use cases, **eventual consistency is acceptable**. A user in Singapore seeing a
document indexed 30 seconds after a user in New York is fine. However:

- **Access control changes** must propagate quickly (security requirement)
- **Deletions** must propagate quickly (compliance requirement)
- **New content** can tolerate seconds-to-minutes of lag

---

## 13. Data Lineage Tracking

### The Problem

A user asks "Where did this answer come from?" and you cite "Engineering Handbook, section 3.2."
But which version? When was it indexed? What chunking produced that specific text? You need
full traceability.

### Lineage Record Schema

```python
@dataclass
class LineageRecord:
    # What was produced
    chunk_id: str
    embedding_id: str
    
    # Source provenance
    source_system: str          # "confluence"
    source_document_id: str     # "page-12345"
    source_version: int         # 47
    source_url: str             # "https://wiki.company.com/page/12345"
    source_fetched_at: datetime # When we fetched the content
    
    # Processing details
    pipeline_version: str       # "v2.3.1"
    chunker_config: dict        # {"strategy": "semantic", "max_tokens": 512}
    embedding_model: str        # "text-embedding-3-large"
    embedding_dimensions: int   # 3072
    
    # Chunk position
    chunk_index: int            # 3 (4th chunk of document)
    char_start: int             # 4521 (character offset in source)
    char_end: int               # 5102
    
    # Timestamps
    indexed_at: datetime
    last_verified_at: datetime  # Last time we confirmed source still exists
```

### Query-Time Lineage

When a RAG system returns an answer, attach lineage:

```json
{
  "answer": "The deployment process requires approval from two senior engineers...",
  "citations": [
    {
      "chunk_id": "eng-handbook_chunk_14",
      "source": "Engineering Handbook v47",
      "source_url": "https://wiki.company.com/page/12345#section-deployments",
      "indexed_at": "2024-01-15T10:30:00Z",
      "source_version": 47,
      "freshness": "2 hours ago"
    }
  ]
}
```

---

## 14. Access-Control Sync

### The Problem

A document in Confluence is restricted to the "Engineering" group. When it enters your vector
store, those same restrictions must be enforced. When someone is removed from the group, they
must immediately lose access to that content in RAG responses.

### ACL Propagation Architecture

```
Source System (Confluence)         Vector Store
┌─────────────────────┐           ┌─────────────────────────┐
│ Page: "Secret Plan" │           │ Chunks from "Secret Plan"│
│ Allowed:            │   sync    │ Metadata:                │
│   - group:eng       │ ────────► │   allowed_groups: [eng]  │
│   - user:alice      │           │   allowed_users: [alice] │
└─────────────────────┘           └─────────────────────────┘

Query Time:
  User "bob" (groups: [sales, marketing]) queries RAG
  → Filter: allowed_groups INTERSECT user_groups != empty
            OR allowed_users CONTAINS user_id
  → "Secret Plan" chunks are EXCLUDED from bob's results
```

### Permission Change Propagation

```python
class ACLSyncService:
    """Sync access control changes from source systems to vector store filters."""
    
    async def handle_permission_change(self, event: PermissionChangeEvent):
        """
        Triggered when:
        - Document permissions change
        - User is added/removed from a group
        - User leaves the company
        """
        if event.type == "DOCUMENT_PERMISSION_CHANGED":
            # Update metadata on all chunks from this document
            new_acl = await self.source.get_permissions(event.document_id)
            await self.vector_store.update_metadata(
                filter={"document_id": event.document_id},
                metadata={
                    "allowed_groups": new_acl.groups,
                    "allowed_users": new_acl.users,
                    "acl_updated_at": datetime.utcnow().isoformat()
                }
            )
        
        elif event.type == "USER_REMOVED_FROM_GROUP":
            # No vector store change needed — query-time filter handles this
            # Just ensure the user directory is updated
            await self.user_directory.refresh(event.user_id)
        
        elif event.type == "USER_DEACTIVATED":
            # Remove user from all allowed_users lists
            affected_docs = await self.vector_store.search_metadata(
                filter={"allowed_users": {"$contains": event.user_id}}
            )
            for doc in affected_docs:
                new_users = [u for u in doc.metadata["allowed_users"] if u != event.user_id]
                await self.vector_store.update_metadata(
                    filter={"id": doc.id},
                    metadata={"allowed_users": new_users}
                )
```

---

## 15. Ingestion Pipeline Architecture

### Queue-Based Event-Driven Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │     │  Event Bus  │     │  Workers    │     │   Stores    │
│             │     │             │     │             │     │             │
│ Confluence  │────►│             │────►│  Fetcher    │────►│ Vector DB   │
│ Slack       │     │   Kafka /   │     │  Chunker    │     │ BM25 Index  │
│ GitHub      │     │   SQS /     │     │  Embedder   │     │ Graph DB    │
│ Database    │     │  EventBridge│     │  Indexer    │     │ Cache       │
│ S3          │     │             │     │  Validator  │     │ Audit Log   │
└─────────────┘     └──────┬──────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Dead Letter │
                    │   Queue     │
                    └─────────────┘
```

### Worker Pipeline Stages

```python
class IngestionPipeline:
    """
    Multi-stage pipeline with independent scaling per stage.
    Each stage reads from a queue and writes to the next.
    """
    
    stages = [
        "fetch",      # Download content from source
        "parse",      # Extract text from HTML/PDF/DOCX
        "validate",   # Quality checks
        "chunk",      # Split into chunks
        "embed",      # Generate embeddings (most expensive — scale separately)
        "index",      # Write to vector store
        "post_index", # Update caches, lineage, metrics
    ]
    
    async def process_event(self, event: CDCEvent):
        context = PipelineContext(event=event, start_time=datetime.utcnow())
        
        try:
            # Fetch
            raw_doc = await self.fetcher.fetch(event.source, event.document_id)
            context.raw_doc = raw_doc
            
            # Parse
            parsed = await self.parser.parse(raw_doc)
            context.parsed_doc = parsed
            
            # Validate
            quality_result = await self.validator.validate(parsed)
            if not quality_result.valid:
                await self.dead_letter.send(event, reason=quality_result.errors)
                return
            
            # Chunk
            chunks = await self.chunker.chunk(parsed, config=self.chunk_config)
            
            # Embed (batch for efficiency)
            embeddings = await self.embedder.embed_batch([c.text for c in chunks])
            
            # Index
            await self.indexer.upsert_chunks(chunks, embeddings, metadata=context.metadata)
            
            # Post-index
            await self.post_processor.run(context)
            
            # Metrics
            metrics.histogram("pipeline.latency_ms", context.elapsed_ms)
            metrics.counter("pipeline.documents_processed", 1, tags={"source": event.source})
            
        except Exception as e:
            metrics.counter("pipeline.errors", 1, tags={"source": event.source, "stage": context.current_stage})
            await self.dead_letter.send(event, reason=str(e), stage=context.current_stage)
            raise
```

---

## 16. Dead Letter Queues

### Purpose

Documents that fail processing shouldn't block the pipeline or be silently lost. They go to a
dead letter queue (DLQ) for investigation and retry.

### DLQ Design

```python
@dataclass
class DeadLetterRecord:
    original_event: CDCEvent
    failure_reason: str
    failed_stage: str          # Which pipeline stage failed
    failure_timestamp: datetime
    retry_count: int
    last_retry_at: Optional[datetime]
    status: str                # "pending" | "retrying" | "resolved" | "abandoned"

class DeadLetterQueue:
    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 3600]  # 1 min, 5 min, 1 hour
    
    async def send(self, event: CDCEvent, reason: str, stage: str):
        record = DeadLetterRecord(
            original_event=event,
            failure_reason=reason,
            failed_stage=stage,
            failure_timestamp=datetime.utcnow(),
            retry_count=0,
            status="pending"
        )
        await self.store.insert(record)
        
        # Alert if DLQ depth exceeds threshold
        depth = await self.store.count(status="pending")
        if depth > 100:
            await self.alerting.alert(f"DLQ depth is {depth} — investigate failures")
    
    async def retry_pending(self):
        """Periodic job that retries failed documents with backoff."""
        pending = await self.store.query(status="pending", retry_count__lt=self.MAX_RETRIES)
        
        for record in pending:
            delay = self.RETRY_DELAYS[min(record.retry_count, len(self.RETRY_DELAYS) - 1)]
            if datetime.utcnow() - record.failure_timestamp < timedelta(seconds=delay):
                continue  # Not ready for retry yet
            
            record.status = "retrying"
            record.retry_count += 1
            record.last_retry_at = datetime.utcnow()
            await self.store.update(record)
            
            # Re-submit to pipeline
            await self.pipeline.process_event(record.original_event)
```

---

## 17. Idempotency

### The Problem

Network failures, retries, and at-least-once delivery semantics mean the same document may be
processed multiple times. Processing must be idempotent — the result should be the same whether
you process a document once or five times.

### Idempotency Strategies

```python
class IdempotentIndexer:
    """Ensures duplicate processing doesn't create duplicate chunks."""
    
    async def upsert_chunks(self, doc_id: str, chunks: list[Chunk], embeddings: list[list[float]]):
        """
        Uses deterministic chunk IDs based on document_id + chunk_index.
        Upsert (not insert) ensures re-processing overwrites, not duplicates.
        """
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}__chunk_{i}"  # Deterministic ID
            
            await self.vector_store.upsert(
                id=chunk_id,  # Same ID = overwrite, not duplicate
                vector=embedding,
                metadata={
                    "document_id": doc_id,
                    "chunk_index": i,
                    "content": chunk.text,
                    "processed_at": datetime.utcnow().isoformat()
                }
            )
        
        # Delete any chunks beyond the current count (document may have shrunk)
        await self.vector_store.delete(
            filter={
                "document_id": doc_id,
                "chunk_index": {"$gte": len(chunks)}
            }
        )
    
    async def with_dedup_lock(self, event: CDCEvent, process_fn):
        """
        Prevent concurrent processing of the same document.
        Uses distributed lock with event version as fence token.
        """
        lock_key = f"processing:{event.source}:{event.document_id}"
        
        async with self.lock_manager.acquire(lock_key, ttl=300) as lock:
            # Check if we already processed this version
            last_processed = await self.state_store.get(f"last_version:{event.document_id}")
            if last_processed and last_processed >= event.version:
                logger.info(f"Skipping {event.document_id} v{event.version} (already at v{last_processed})")
                return
            
            await process_fn(event)
            await self.state_store.set(f"last_version:{event.document_id}", event.version)
```

---

## 18. Monitoring

### Key Metrics

```python
# Pipeline health metrics
METRICS = {
    # Throughput
    "pipeline.events_received_total": Counter,       # Total CDC events received
    "pipeline.events_processed_total": Counter,      # Successfully processed
    "pipeline.events_failed_total": Counter,         # Failed (sent to DLQ)
    
    # Latency
    "pipeline.processing_latency_seconds": Histogram, # End-to-end per document
    "pipeline.stage_latency_seconds": Histogram,      # Per stage (fetch, parse, embed, index)
    "pipeline.queue_wait_seconds": Histogram,         # Time in queue before processing
    
    # Freshness
    "pipeline.freshness_lag_seconds": Gauge,          # Per source: time since last sync
    "pipeline.stale_documents": Gauge,                # Documents older than SLA
    
    # Quality
    "pipeline.quality_rejections_total": Counter,     # Documents rejected by quality gate
    "pipeline.dlq_depth": Gauge,                      # Dead letter queue size
    "pipeline.duplicate_detections": Counter,         # Near-duplicates found
    
    # Cost
    "pipeline.embedding_tokens_total": Counter,       # Tokens sent to embedding API
    "pipeline.embedding_cost_dollars": Counter,       # Estimated cost
    "pipeline.api_calls_total": Counter,              # Calls to external APIs
    
    # Capacity
    "pipeline.vector_store_size": Gauge,              # Total vectors stored
    "pipeline.vector_store_capacity_pct": Gauge,      # % of capacity used
    "pipeline.worker_utilization_pct": Gauge,         # Worker pool utilization
}
```

### Alerting Rules

```yaml
alerts:
  - name: "Pipeline Stalled"
    condition: "rate(pipeline.events_processed_total[5m]) == 0 AND pipeline.events_received_total > 0"
    severity: P1
    action: "Page on-call"
  
  - name: "High Error Rate"
    condition: "rate(pipeline.events_failed_total[5m]) / rate(pipeline.events_received_total[5m]) > 0.05"
    severity: P2
    action: "Alert channel"
  
  - name: "Freshness SLA Breach"
    condition: "pipeline.freshness_lag_seconds > source_sla_seconds"
    severity: P2
    action: "Alert channel + auto-trigger reconciliation"
  
  - name: "DLQ Growing"
    condition: "pipeline.dlq_depth > 100 AND rate(pipeline.dlq_depth[1h]) > 0"
    severity: P3
    action: "Alert channel"
  
  - name: "Embedding Cost Spike"
    condition: "rate(pipeline.embedding_cost_dollars[1h]) > 2x daily_average"
    severity: P3
    action: "Alert channel (possible re-indexing loop)"
```

### Operational Runbooks

| Scenario | Detection | Response |
|----------|-----------|----------|
| Pipeline stalled | Zero throughput, growing queue | Check worker health, restart consumers |
| Embedding API down | Spike in embed-stage failures | Switch to backup model, queue for retry |
| Vector DB full | Capacity > 90% | Scale storage, or prune low-quality chunks |
| Freshness breach | Lag > SLA | Trigger immediate reconciliation for affected source |
| Duplicate storm | Sudden spike in duplicate detections | Check if source is sending duplicate events |
| Cost runaway | Embedding cost > 3x normal | Check for infinite re-processing loops |

---

## Summary: The AI Data Engineering Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MONITORING & ALERTING                             │
│  Freshness SLA │ Error Rate │ Pipeline Lag │ Cost │ Quality Score        │
├─────────────────────────────────────────────────────────────────────────┤
│                         DATA CONTRACTS                                    │
│  Schema │ SLA │ Quality Gates │ Ownership │ Alerting                     │
├─────────────────────────────────────────────────────────────────────────┤
│                      INGESTION PIPELINE                                   │
│  CDC → Queue → Fetch → Parse → Validate → Chunk → Embed → Index         │
│                                    │                                      │
│                              Dead Letter Queue                            │
├─────────────────────────────────────────────────────────────────────────┤
│                      OPERATIONAL PROCESSES                                │
│  Incremental Indexing │ Deletion Propagation │ ACL Sync │ Dedup          │
│  Schema Migration │ Embedding Upgrade │ Metadata Backfill │ Lineage      │
├─────────────────────────────────────────────────────────────────────────┤
│                         STORAGE LAYER                                     │
│  Vector DB │ BM25 Index │ Knowledge Graph │ Cache │ Audit Log            │
└─────────────────────────────────────────────────────────────────────────┘
```

This is the work that separates a RAG demo from a production RAG system. It's not glamorous,
but it's where reliability lives.
