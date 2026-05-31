# AI Data Engineering: Real-World Examples

## Case Study 1: Confluence → RAG Sync with 5-Minute Freshness SLA

### Company Context

A 2,000-person SaaS company with 45,000 Confluence pages. Their internal AI assistant answers
employee questions about engineering processes, HR policies, product specs, and customer playbooks.

### The Problem

Initial implementation used a nightly batch job. Employees would update a policy at 9 AM, but
the AI assistant would give the old answer until the next morning. Trust eroded rapidly.

### Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                     CONFLUENCE → RAG PIPELINE                            │
│                                                                          │
│  Confluence Cloud                                                        │
│       │                                                                  │
│       ├── Webhook (page_updated, page_created, page_deleted)            │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   API Gateway (webhook receiver)                                 │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   SQS Queue (buffering + retry)                                 │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   Lambda: Fetch Full Page Content                                │
│       │        │ (Confluence REST API - expand=body.storage)            │
│       │        ▼                                                         │
│       │   Lambda: Parse & Clean HTML                                     │
│       │        │ (strip macros, resolve @mentions, expand includes)      │
│       │        ▼                                                         │
│       │   Lambda: Quality Gate                                           │
│       │        │ (reject empty, too short, or corrupt pages)            │
│       │        ▼                                                         │
│       │   Lambda: Chunk (semantic chunker, ~500 tokens/chunk)           │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   Lambda: Embed (OpenAI text-embedding-3-small, batch)          │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   Lambda: Upsert to Pinecone                                    │
│       │        │ (namespace per Confluence space)                        │
│       │        ▼                                                         │
│       │   Lambda: Invalidate semantic cache                              │
│       │        │                                                         │
│       │        ▼                                                         │
│       │   CloudWatch: Emit freshness metric                              │
│       │                                                                  │
│       │                                                                  │
│       └── Polling Reconciler (every 6 hours)                            │
│            Catches missed webhooks by comparing Confluence page list     │
│            against Pinecone document_id list                            │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Implementation Details

**Webhook receiver with deduplication:**

```python
# Confluence sends duplicate webhooks frequently (known issue)
# Use page_id + version as dedup key

async def handle_webhook(event):
    page_id = event["page"]["id"]
    version = event["page"]["version"]["number"]
    
    dedup_key = f"{page_id}:v{version}"
    if await redis.exists(dedup_key):
        return {"status": "duplicate, skipped"}
    
    await redis.setex(dedup_key, 3600, "processed")  # 1-hour dedup window
    await sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(event))
    return {"status": "queued"}
```

**Handling Confluence-specific quirks:**

```python
def clean_confluence_html(storage_format_html: str) -> str:
    """
    Confluence storage format has many non-standard elements:
    - <ac:structured-macro> (expand macros, code blocks, etc.)
    - <ac:link> (internal links with page IDs)
    - <ri:attachment> (embedded files — extract filename only)
    - <ac:parameter> (macro parameters)
    """
    soup = BeautifulSoup(storage_format_html, "html.parser")
    
    # Remove macros that don't contain useful text
    for macro in soup.find_all("ac:structured-macro"):
        macro_name = macro.get("ac:name", "")
        if macro_name in ["toc", "pagetree", "children", "recently-updated"]:
            macro.decompose()  # Navigation macros — no content value
        elif macro_name == "code":
            # Keep code blocks but mark them
            code_text = macro.get_text()
            macro.replace_with(f"\n```\n{code_text}\n```\n")
        elif macro_name == "expand":
            # Expand sections — keep the content
            pass  # Let inner content remain
    
    # Convert to plain text, preserving structure
    text = soup.get_text(separator="\n")
    
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
```

### Results

| Metric | Before (Nightly Batch) | After (CDC Pipeline) |
|--------|----------------------|---------------------|
| Freshness | 12-24 hours | 2-4 minutes (p95) |
| User trust score | 3.2/5 | 4.6/5 |
| Stale answer complaints/week | 15-20 | 0-2 |
| Monthly cost | $120 (full re-index nightly) | $45 (incremental only) |
| Docs processed/day | 45,000 (all, nightly) | ~800 (only changed) |

---

## Case Study 2: Re-embedding 8M Documents (ada-002 → text-embedding-3-large)

### Company Context

A legal tech firm with 8 million document chunks (contracts, case law, regulations, memos).
Moving from `text-embedding-ada-002` (1536 dims) to `text-embedding-3-large` (3072 dims) for
better retrieval accuracy on legal queries.

### Constraints

- Zero downtime — lawyers use the system 24/7 for case research
- Budget: $2,500 max for embedding costs
- Timeline: Complete within 5 business days
- Quality: New embeddings must match or exceed current retrieval accuracy

### Cost Estimation

```
8M chunks × ~250 tokens average = 2B tokens
text-embedding-3-large: $0.13 per 1M tokens
Cost: 2000 × $0.13 = $260 (well within budget)

But API rate limits are the constraint:
- 10,000 RPM (requests per minute) on their tier
- Batch endpoint: 50,000 embeddings per batch file
- Batch processing: ~24 hours turnaround per batch file
```

### Migration Plan (Executed Over 3 Days)

**Day 1: Preparation & Dual-Write Setup**

```python
# 1. Create new Qdrant collection with 3072 dimensions
new_collection = qdrant.create_collection(
    collection_name="legal_docs_v2",
    vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
    # Same shard configuration as production
    shard_number=6,
    replication_factor=2
)

# 2. Enable dual-write: all new documents go to both collections
pipeline_config.update({
    "embedding_model": "text-embedding-3-large",
    "write_collections": ["legal_docs_v1", "legal_docs_v2"],
    "read_collection": "legal_docs_v1"  # Still reading from old
})

# 3. Start batch export of existing chunks
# Export all chunk texts to JSONL for batch embedding API
exported = 0
with open("chunks_for_reembedding.jsonl", "w") as f:
    for batch in qdrant.scroll("legal_docs_v1", batch_size=1000):
        for point in batch:
            f.write(json.dumps({
                "custom_id": point.id,
                "body": {
                    "model": "text-embedding-3-large",
                    "input": point.payload["content"]
                }
            }) + "\n")
            exported += 1

# Split into batch files of 50K each
# 8M / 50K = 160 batch files
```

**Day 2-3: Batch Re-embedding**

```python
# Used OpenAI Batch API for cost efficiency (50% discount)
# Submitted 160 batch files across Day 2 and Day 3

import openai

batch_files = glob.glob("batch_chunks_*.jsonl")
batch_jobs = []

for batch_file in batch_files:
    # Upload file
    uploaded = openai.files.create(file=open(batch_file, "rb"), purpose="batch")
    
    # Create batch job
    batch = openai.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/embeddings",
        completion_window="24h"
    )
    batch_jobs.append(batch.id)
    
    # Rate limit: max 100 batch jobs in flight
    if len([j for j in batch_jobs if not is_complete(j)]) >= 100:
        await wait_for_any_completion(batch_jobs)

# Monitor progress
while incomplete := [j for j in batch_jobs if not is_complete(j)]:
    print(f"Progress: {len(batch_jobs) - len(incomplete)}/{len(batch_jobs)} batches complete")
    await asyncio.sleep(300)
```

**Day 3: Backfill Results into New Collection**

```python
# Process completed batch results
for batch_id in batch_jobs:
    result_file = openai.batches.retrieve(batch_id).output_file_id
    content = openai.files.content(result_file)
    
    upsert_batch = []
    for line in content.iter_lines():
        result = json.loads(line)
        chunk_id = result["custom_id"]
        embedding = result["response"]["body"]["data"][0]["embedding"]
        
        # Get original metadata from v1 collection
        original = qdrant.retrieve("legal_docs_v1", ids=[chunk_id])[0]
        
        upsert_batch.append(PointStruct(
            id=chunk_id,
            vector=embedding,
            payload=original.payload
        ))
        
        if len(upsert_batch) >= 500:
            qdrant.upsert("legal_docs_v2", points=upsert_batch)
            upsert_batch = []
    
    if upsert_batch:
        qdrant.upsert("legal_docs_v2", points=upsert_batch)
```

**Day 3 (Evening): Quality Validation**

```python
# Ran 500 test queries from their eval suite
eval_results = []
for query, expected_doc_ids in eval_suite.items():
    v1_results = search("legal_docs_v1", query, model="ada-002", top_k=20)
    v2_results = search("legal_docs_v2", query, model="3-large", top_k=20)
    
    v1_recall = recall_at_k(v1_results, expected_doc_ids, k=10)
    v2_recall = recall_at_k(v2_results, expected_doc_ids, k=10)
    
    eval_results.append({"query": query, "v1": v1_recall, "v2": v2_recall})

# Results:
# v1 average recall@10: 0.72
# v2 average recall@10: 0.81  (+12.5% improvement!)
# Zero regressions > 0.1 on any query
# ✅ Safe to cutover
```

**Day 4: Traffic Cutover**

```python
# Gradual shift over 4 hours
for pct in [10, 25, 50, 75, 100]:
    pipeline_config.update({"read_collection_v2_pct": pct})
    await asyncio.sleep(3600)  # 1 hour between steps
    
    # Monitor error rates and latency
    error_rate = metrics.query("search_error_rate_5m")
    p99_latency = metrics.query("search_latency_p99")
    
    if error_rate > 0.01 or p99_latency > 500:
        # Rollback
        pipeline_config.update({"read_collection_v2_pct": 0})
        alert("Cutover rolled back due to degradation")
        break

# After 100% for 24 hours with no issues:
pipeline_config.update({
    "write_collections": ["legal_docs_v2"],  # Stop writing to v1
    "read_collection": "legal_docs_v2"
})
```

### Final Results

| Metric | Value |
|--------|-------|
| Total re-embedding cost | $135 (batch API 50% discount) |
| Migration duration | 3 days (mostly waiting for batch API) |
| Downtime | 0 seconds |
| Retrieval accuracy improvement | +12.5% recall@10 |
| Lawyer satisfaction (post-survey) | "Noticeably better at finding relevant precedents" |

---

## Case Study 3: Deletion Propagation — Employee Departure

### Scenario

An engineering director leaves the company. Their private Confluence space (847 pages),
Slack DMs referenced in the knowledge base, personal Google Drive documents, and GitHub
comments must be removed from all AI systems within 4 hours (company policy).

### Deletion Cascade Execution

```python
# Triggered by HR system webhook: employee_terminated event

async def handle_employee_departure(event: EmployeeTerminatedEvent):
    user_id = event.user_id
    user_email = event.email
    
    deletion_job = DeletionJob(
        triggered_by="hr_system",
        reason=f"Employee departure: {user_email}",
        timestamp=datetime.utcnow()
    )
    
    # 1. Find all documents authored by or restricted to this user
    affected_documents = []
    
    # Confluence: pages in their personal space + pages only they can access
    confluence_pages = await confluence.get_pages(
        creator=user_email,
        space_type="personal"
    )
    affected_documents.extend([
        {"source": "confluence", "id": p.id, "title": p.title}
        for p in confluence_pages
    ])
    
    # Also: pages where they're the sole viewer (restricted pages)
    restricted_pages = await confluence.get_pages(
        restrictions_include_user=user_email,
        restrictions_sole_user=True  # Only remove if they're the ONLY allowed user
    )
    affected_documents.extend([
        {"source": "confluence", "id": p.id, "title": p.title}
        for p in restricted_pages
    ])
    
    # Google Drive: files in their personal drive
    drive_files = await google_drive.list_files(owner=user_email, shared=False)
    affected_documents.extend([
        {"source": "gdrive", "id": f.id, "title": f.name}
        for f in drive_files
    ])
    
    # 2. Delete from all stores
    total_chunks_deleted = 0
    
    for doc in affected_documents:
        source_key = f"{doc['source']}:{doc['id']}"
        
        # Vector store (all chunks)
        deleted = await vector_store.delete(filter={"source_document_id": source_key})
        total_chunks_deleted += deleted
        
        # BM25 index
        await bm25_index.delete(filter={"source_document_id": source_key})
        
        # Semantic cache (invalidate any cached answers citing this doc)
        await semantic_cache.invalidate(filter={"cited_sources": {"$contains": source_key}})
        
        # Knowledge graph
        await knowledge_graph.delete_node(source_key)
        
        deletion_job.add_record(doc, chunks_deleted=deleted)
    
    # 3. Remove user from ACL lists (they were a viewer on shared docs)
    await acl_service.remove_user_from_all_acls(user_email)
    
    # 4. Audit log
    deletion_job.complete(
        total_documents=len(affected_documents),
        total_chunks=total_chunks_deleted,
        duration=deletion_job.elapsed
    )
    await audit_log.record(deletion_job)
    
    # 5. Verification
    verification = await verify_deletion(user_email, affected_documents)
    if not verification.clean:
        await alert(f"INCOMPLETE DELETION for {user_email}: {verification.remaining}")
    
    return deletion_job

# Results for this case:
# Documents removed: 847 Confluence + 234 Drive files = 1,081 documents
# Chunks deleted: 14,392
# ACL entries removed: 2,847
# Cache entries invalidated: 891
# Total duration: 47 minutes
# Verification: CLEAN ✓
```

---

## Case Study 4: Ingestion Pipeline at Scale — 50K Documents/Day

### Company Context

A financial services firm processing 50,000 documents daily: regulatory filings, market reports,
client communications, research notes, and news articles.

### Pipeline Architecture

```
Sources (50K docs/day):
├── Reuters/Bloomberg feeds: 30K articles/day (streaming)
├── SEC EDGAR filings: 5K/day (batch, 4x daily)
├── Internal research: 2K/day (Confluence webhooks)
├── Client emails (anonymized): 10K/day (batch, hourly)
└── Regulatory updates: 3K/day (RSS + scraping)

Processing Pipeline:
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Kafka Topics│───►│ Workers  │───►│ Quality  │───►│ Embedding│
│ (partitioned│    │ (fetch + │    │ Gate     │    │ Workers  │
│  by source) │    │  parse)  │    │          │    │ (GPU)    │
│             │    │ 20 pods  │    │ 5 pods   │    │ 8 pods   │
└─────────────┘    └──────────┘    └──────────┘    └──────────┘
                                        │                │
                                        ▼                ▼
                                   ┌──────────┐    ┌──────────┐
                                   │   DLQ    │    │ Qdrant   │
                                   │          │    │ (6 nodes)│
                                   └──────────┘    └──────────┘
```

### Quality Gate Results (30-Day Average)

```
Documents received:     1,500,000 (50K/day × 30 days)
├── Passed quality gate:  1,387,500 (92.5%)
├── Rejected - format:       45,000 (3.0%) — corrupt PDFs, invalid encoding
├── Rejected - content:      37,500 (2.5%) — too short, garbled, non-English
├── Rejected - duplicate:    22,500 (1.5%) — exact or near-duplicate
└── Sent to DLQ (errors):    7,500 (0.5%) — API timeouts, parsing crashes

DLQ resolution:
├── Auto-retried successfully: 6,750 (90% of DLQ)
├── Manually resolved:           500 (6.7%)
└── Abandoned (unfixable):       250 (3.3%)
```

### Alerting Incidents (Sample Month)

| Date | Alert | Cause | Resolution | Duration |
|------|-------|-------|------------|----------|
| Mar 3 | Error rate > 5% | OpenAI embedding API returned 429s | Enabled exponential backoff, scaled down concurrent requests | 12 min |
| Mar 8 | Freshness breach (Reuters) | Kafka consumer lag spike due to pod eviction | K8s rescheduled pod, consumer caught up | 8 min |
| Mar 15 | DLQ depth > 100 | New PDF format from SEC caused parser crash | Deployed parser fix, re-processed DLQ | 2 hours |
| Mar 22 | Cost spike alert | Duplicate event storm from Reuters (known issue) | Dedup filter caught most; some double-processed | 30 min |

### Cost Breakdown (Monthly)

```
Embedding API:           $3,400  (1.5B tokens/month at batch pricing)
Compute (EKS):           $2,800  (workers, quality gate, indexer pods)
Qdrant (managed):        $4,200  (6-node cluster, 3TB storage)
Kafka (MSK):             $1,100  (3 brokers, 2TB retention)
Monitoring (Datadog):      $600  (custom metrics, APM)
S3 (raw document archive): $200  (compliance requirement)
────────────────────────────────────────────────────────────────
Total:                  $12,300/month
```

---

## Case Study 5: Data Quality Incident — The Corrupted PDF Disaster

### What Happened

A government procurement portal changed their PDF generation software. The new PDFs looked
normal to humans but contained corrupted Unicode sequences in the extracted text. Over 3 days
(a weekend), 10,247 garbled chunks entered the vector store undetected.

### How It Was Discovered

Monday morning: users reported the AI assistant returning responses like:

> "The compliance requirement states: 'Th\ufffd r\ufffd\ufffdqui\ufffdrem\ufffdnt f\ufffdr
> s\ufffdcti\ufffdn 4.2 is th\ufffd\ufffd the v\ufffdnd\ufffd\ufffdr must...'"

### Impact

- 10,247 chunks with garbled text in the vector store
- These chunks were being retrieved because their embeddings still had *some* semantic signal
- 156 user queries between Friday and Monday returned partially garbled answers
- Trust score dropped from 4.5 to 3.1 that week

### Root Cause Analysis

```
PDF extraction pipeline:
1. Raw PDF bytes → PyPDF2 text extraction
2. PyPDF2 returned text with replacement characters (U+FFFD)
3. Quality gate checked for "non-empty" but NOT for Unicode replacement chars
4. Chunks passed validation because they were technically non-empty UTF-8
5. Embeddings were generated (garbage in → garbage embedding)
6. Garbled chunks indexed alongside good content
```

### Cleanup Process

```python
# Step 1: Identify affected chunks
affected_chunks = await vector_store.query(
    filter={"source": "gov-procurement-portal"},
    # All chunks from this source in the affected date range
    metadata_filter={
        "indexed_at": {"$gte": "2024-03-15", "$lte": "2024-03-18"}
    }
)

# Step 2: Detect garbled content
garbled_chunk_ids = []
for chunk in affected_chunks:
    content = chunk.payload["content"]
    replacement_char_count = content.count("\ufffd")
    total_chars = len(content)
    
    if replacement_char_count / total_chars > 0.05:  # >5% replacement chars
        garbled_chunk_ids.append(chunk.id)

print(f"Found {len(garbled_chunk_ids)} garbled chunks")  # 10,247

# Step 3: Delete garbled chunks
await vector_store.delete(ids=garbled_chunk_ids)

# Step 4: Invalidate cache entries that cited these chunks
await semantic_cache.invalidate(
    filter={"cited_chunk_ids": {"$overlap": garbled_chunk_ids}}
)

# Step 5: Re-process source documents with fixed parser
for doc_id in affected_source_documents:
    await pipeline.reprocess(doc_id, force=True)
```

### Prevention: Enhanced Quality Gate

```python
# Added to quality gate after this incident:

def check_unicode_integrity(text: str) -> QualityResult:
    """Detect text with excessive Unicode replacement characters."""
    replacement_count = text.count("\ufffd")
    
    if replacement_count > 0:
        ratio = replacement_count / len(text)
        if ratio > 0.02:  # More than 2% replacement characters
            return QualityResult.reject(
                f"Unicode integrity check failed: {replacement_count} replacement chars "
                f"({ratio:.1%} of content). Likely corrupted extraction."
            )
        elif ratio > 0.005:
            return QualityResult.warn(
                f"Minor Unicode issues: {replacement_count} replacement chars"
            )
    
    # Also check for other corruption patterns
    control_chars = sum(1 for c in text if unicodedata.category(c).startswith('C') 
                       and c not in '\n\r\t')
    if control_chars > len(text) * 0.01:
        return QualityResult.reject(f"Excessive control characters: {control_chars}")
    
    return QualityResult.pass_()
```

---

## Case Study 6: CDC with Debezium/Kafka for Database → AI Pipeline

### Architecture

A SaaS product stores customer-facing knowledge base articles in PostgreSQL. When articles
are created/updated/deleted, the AI search system must reflect changes within 60 seconds.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│  PostgreSQL  │───►│   Debezium   │───►│    Kafka     │───►│  AI      │
│  (articles   │    │  (CDC via    │    │  (topic:     │    │  Pipeline│
│   table)     │    │   WAL)       │    │   articles.  │    │  Workers │
│              │    │              │    │   changes)   │    │          │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────┘
```

### Debezium Configuration

```json
{
  "name": "articles-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "prod-db.internal",
    "database.port": "5432",
    "database.user": "debezium_replication",
    "database.dbname": "app_production",
    "database.server.name": "prod",
    "table.include.list": "public.articles,public.article_sections",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_articles",
    "publication.name": "articles_publication",
    "transforms": "route",
    "transforms.route.type": "io.debezium.transforms.ByLogicalTableRouter",
    "transforms.route.topic.regex": "prod.public.(.*)",
    "transforms.route.topic.replacement": "ai-pipeline.$1-changes",
    "tombstones.on.delete": true,
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter"
  }
}
```

### Kafka Consumer (AI Pipeline Side)

```python
class ArticleCDCConsumer:
    def __init__(self, kafka_config, pipeline):
        self.consumer = KafkaConsumer(
            "ai-pipeline.articles-changes",
            bootstrap_servers=kafka_config["brokers"],
            group_id="ai-indexing-pipeline",
            auto_offset_reset="earliest",
            enable_auto_commit=False
        )
        self.pipeline = pipeline
    
    async def consume(self):
        for message in self.consumer:
            event = json.loads(message.value)
            
            operation = event["payload"]["op"]  # c=create, u=update, d=delete
            
            if operation in ("c", "u"):
                # Create or Update: extract article content and re-index
                after = event["payload"]["after"]
                await self.pipeline.process_article(
                    article_id=after["id"],
                    title=after["title"],
                    body=after["body_html"],
                    metadata={
                        "category": after["category"],
                        "author_id": after["author_id"],
                        "published": after["published"],
                        "updated_at": after["updated_at"]
                    }
                )
            
            elif operation == "d":
                # Delete: remove from vector store
                before = event["payload"]["before"]
                await self.pipeline.delete_article(article_id=before["id"])
            
            # Commit offset after successful processing
            self.consumer.commit()
            
            # Emit latency metric
            event_time = datetime.fromtimestamp(event["payload"]["ts_ms"] / 1000)
            lag = (datetime.utcnow() - event_time).total_seconds()
            metrics.histogram("cdc.processing_lag_seconds", lag)
```

### Results

- **Average end-to-end latency**: 4.2 seconds (from DB write to searchable in AI)
- **p99 latency**: 18 seconds
- **Missed events**: 0 (WAL-based CDC doesn't lose events)
- **Daily volume**: ~2,000 article changes/day

---

## Case Study 7: Multi-Source Fusion with Deduplication

### The Problem

A consulting firm indexes content from Confluence (internal wiki), Slack (discussions), and
GitHub (code + docs). The same information often appears across sources:

- A Slack thread discussing a design that's also documented in Confluence
- A GitHub README that's copy-pasted into Confluence
- Meeting notes in Confluence that summarize Slack discussions

### Deduplication Pipeline

```python
class MultiSourceFusionPipeline:
    def __init__(self):
        self.dedup_detector = NearDuplicateDetector(threshold=0.85)
        self.source_priority = {
            "confluence": 3,  # Highest priority (canonical documentation)
            "github": 2,      # Code is authoritative for technical details
            "slack": 1        # Lowest priority (conversational, often partial)
        }
    
    async def process_document(self, doc: Document):
        # Check for near-duplicates across all sources
        duplicates = self.dedup_detector.find_duplicates(doc.id, doc.text)
        
        if not duplicates:
            # No duplicates — index normally
            await self.index(doc)
            self.dedup_detector.add_document(doc.id, doc.text)
            return
        
        # Found duplicates — determine canonical version
        all_versions = [doc] + [await self.fetch_doc(d) for d in duplicates]
        canonical = self.select_canonical(all_versions)
        
        if canonical.id == doc.id:
            # This new document IS the canonical version
            # Index it and add cross-references
            await self.index(doc, metadata={
                "also_found_in": [d.id for d in all_versions if d.id != doc.id],
                "is_canonical": True
            })
            # Mark others as non-canonical
            for other in all_versions:
                if other.id != doc.id:
                    await self.update_metadata(other.id, {"is_canonical": False, "canonical_id": doc.id})
        else:
            # An existing document is canonical — just record the cross-reference
            await self.update_metadata(canonical.id, {
                "also_found_in": [doc.source + ":" + doc.id]
            })
            # Don't index this duplicate (or index with lower boost)
            metrics.counter("dedup.duplicates_skipped", 1, tags={"source": doc.source})
    
    def select_canonical(self, versions: list[Document]) -> Document:
        """Select the canonical version based on source priority and recency."""
        return max(versions, key=lambda d: (
            self.source_priority.get(d.source, 0),
            d.updated_at
        ))
```

### Conflict Resolution

When the same information differs across sources:

```python
class ConflictResolver:
    async def resolve(self, canonical: Document, conflicting: Document) -> Resolution:
        """
        When Confluence says "deploy on Tuesdays" but Slack says "we moved deploys to Thursdays"
        """
        # Strategy 1: Most recent wins
        if conflicting.updated_at > canonical.updated_at + timedelta(days=7):
            return Resolution(
                action="flag_for_review",
                reason=f"Conflicting info: {canonical.source} says X, {conflicting.source} says Y (newer)",
                suggested="Update Confluence to match recent Slack discussion"
            )
        
        # Strategy 2: Higher-authority source wins
        # Confluence > Slack for policy docs
        # GitHub > Confluence for code docs
        return Resolution(
            action="keep_canonical",
            reason=f"{canonical.source} is authoritative for this content type"
        )
```

### Monthly Stats

```
Documents processed: 45,000
Exact duplicates found: 3,200 (7.1%)
Near-duplicates found: 1,800 (4.0%)
Conflicts flagged for review: 89
Storage saved by dedup: ~22%
```

---

## Case Study 8: Embedding Migration — Side-by-Side Strategy

### Approach: Shadow Indexing

Rather than a big-bang migration, this company ran both embedding models simultaneously for
2 weeks, comparing quality in production.

```python
class ShadowEmbeddingComparator:
    """
    Runs every query against both old and new embeddings.
    Serves old results to users. Logs comparison for analysis.
    """
    
    async def search(self, query: str, user_id: str):
        # Embed query with both models
        old_query_vec = await embed(query, model="ada-002")
        new_query_vec = await embed(query, model="text-embedding-3-large")
        
        # Search both collections
        old_results = await self.old_collection.search(old_query_vec, top_k=10)
        new_results = await self.new_collection.search(new_query_vec, top_k=10)
        
        # Log comparison (async, non-blocking)
        asyncio.create_task(self.log_comparison(query, old_results, new_results, user_id))
        
        # Serve old results (stable experience during evaluation)
        return old_results
    
    async def log_comparison(self, query, old_results, new_results, user_id):
        old_ids = [r.id for r in old_results]
        new_ids = [r.id for r in new_results]
        
        overlap = len(set(old_ids) & set(new_ids))
        
        await self.comparison_store.insert({
            "query": query,
            "timestamp": datetime.utcnow(),
            "old_top_10_ids": old_ids,
            "new_top_10_ids": new_ids,
            "overlap_count": overlap,
            "overlap_pct": overlap / 10,
            "new_only": [id for id in new_ids if id not in old_ids],
            "old_only": [id for id in old_ids if id not in new_ids]
        })
```

### Analysis After 2 Weeks

```
Total queries compared: 28,450
Average overlap (top 10): 6.2/10 (62%)
Cases where new model found clearly better results: 4,200 (14.8%)
Cases where old model was clearly better: 890 (3.1%)
Net improvement: +11.7% of queries improved
```

Decision: **Proceed with migration** — net positive with minimal regressions.

---

## Case Study 9: Freshness Monitoring Dashboard

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI PIPELINE FRESHNESS DASHBOARD                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Source Health         Last Sync    Lag      SLA    Status            │
│  ─────────────────────────────────────────────────────────           │
│  Confluence            2 min ago    2m       5m     ✅ OK             │
│  Slack                 30 sec ago   30s      1m     ✅ OK             │
│  GitHub                4 min ago    4m       10m    ✅ OK             │
│  Google Drive          47 min ago   47m      30m    🔴 BREACH        │
│  SharePoint            12 min ago   12m      15m    🟡 DEGRADED      │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Pipeline Throughput (last hour)                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │     ▄▄                                                       │    │
│  │    ████  ▄▄                                                  │    │
│  │   ██████████  ▄▄    ▄▄                                      │    │
│  │  ████████████████  ████  ▄▄  ▄▄  ▄▄  ▄▄  ▄▄  ▄▄           │    │
│  │  ████████████████████████████████████████████████            │    │
│  │  0  5  10 15 20 25 30 35 40 45 50 55 60 (minutes ago)       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  Current rate: 142 docs/min    Average: 128 docs/min                 │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Error Rates (last 24h)                                              │
│  Total processed: 184,320                                            │
│  Failed: 847 (0.46%)                                                 │
│  DLQ depth: 23 (all < 2 hours old)                                   │
│                                                                       │
│  Top failure reasons:                                                │
│  1. PDF parse error (312) — gov-portal source                        │
│  2. Embedding API timeout (201) — spike at 14:00                     │
│  3. Content too short (189) — Slack messages < 10 words              │
│  4. Encoding error (145) — legacy SharePoint docs                    │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Cost Today: $127.40                                                 │
│  ├── Embedding API: $98.20 (77%)                                     │
│  ├── Compute: $22.30 (18%)                                           │
│  └── Vector DB writes: $6.90 (5%)                                    │
│  Budget remaining this month: $2,847                                 │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Alerting Configuration (PagerDuty + Slack)

```yaml
# Alert when Google Drive sync is stale
- name: "google_drive_freshness_breach"
  query: "pipeline_freshness_lag_seconds{source='google_drive'} > 1800"
  for: "5m"
  labels:
    severity: "P2"
  annotations:
    summary: "Google Drive sync is {{ $value | humanizeDuration }} behind"
    runbook: "https://runbooks.internal/ai-pipeline/freshness-breach"
    action: |
      1. Check Google Drive push notification subscription status
      2. Verify OAuth token hasn't expired
      3. Check if reconciler last ran successfully
      4. If subscription expired, re-subscribe and trigger full reconciliation
```

---

## Case Study 10: The True Cost of AI Data Engineering

### Real Budget Breakdown (Series B startup, 200 employees, RAG-based product)

```
ANNUAL AI SYSTEM BUDGET: $840,000

Data Engineering (pipeline work):     $504,000  (60%)
├── Personnel:                        $380,000
│   ├── 1 Senior Data Engineer:       $195,000
│   └── 1 ML Platform Engineer:       $185,000
├── Infrastructure:                   $98,000/year
│   ├── Kafka (managed):              $24,000
│   ├── Vector DB (Pinecone):         $36,000
│   ├── Compute (workers):            $26,000
│   └── Monitoring/observability:     $12,000
└── Embedding API costs:              $26,000/year

LLM/Inference (the "AI" part):        $168,000  (20%)
├── OpenAI GPT-4 API:                 $120,000
├── Fine-tuning experiments:          $18,000
└── Eval/testing:                     $30,000

Product/Application layer:            $126,000  (15%)
├── Frontend engineering (0.5 FTE):   $95,000
└── Infrastructure (hosting, CDN):    $31,000

Research/Experimentation:             $42,000   (5%)
├── New model evaluations:            $22,000
└── Architecture experiments:         $20,000
```

### Why 60% Goes to Data Engineering

1. **It's continuous work, not a one-time build.** The LLM integration is built once and
   tweaked occasionally. The pipeline runs 24/7 and breaks in new ways every week.

2. **Every new source multiplies complexity.** Adding Confluence took 2 weeks. Adding Slack
   took another 2 weeks. Each source has unique APIs, auth, rate limits, data formats,
   and failure modes.

3. **Quality is expensive to maintain.** You need monitoring, alerting, quality gates,
   DLQ processing, reconciliation, and on-call rotations. This is operational overhead
   that never goes away.

4. **Migrations happen more often than expected.** In one year: upgraded embedding model
   once, changed chunking strategy twice, migrated vector DB once, added 3 new metadata
   fields. Each migration requires careful planning and execution.

5. **Incidents require immediate response.** When the pipeline breaks, the AI gives wrong
   answers. Unlike a traditional data warehouse where stale data is tolerable, stale AI
   data erodes user trust immediately.

### The Counterintuitive Insight

Companies that under-invest in data engineering and over-invest in model sophistication end
up with:
- The most advanced LLM (GPT-4 Turbo with perfect prompts)
- Fed with stale, inconsistent, duplicate-ridden data
- Producing confident but wrong answers

The firms that succeed invest heavily in boring pipeline work:
- Reliable CDC with <5 minute freshness
- Quality gates that reject garbage before it enters the index
- Monitoring that catches staleness before users notice
- Clean, deduplicated, well-structured data

**A mediocre model with great data beats a great model with mediocre data. Every time.**
