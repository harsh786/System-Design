# Real-World Examples: RAG Quality at Scale

## Case Study 1: How Perplexity.ai Maintains Quality While Searching Billions of Web Pages

### The Scale Challenge

Perplexity processes 100M+ queries per month against an index of billions of web pages. Their core promise: accurate, cited answers with sub-3-second latency. This is RAG at internet scale.

### Architecture: Multi-Stage Quality Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1: Query Understanding (50ms)                 │
│  - Intent classification                             │
│  - Query expansion/reformulation                     │
│  - Determine freshness requirements                  │
│    (news = last hours, knowledge = any time)         │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Stage 2: Fast Retrieval from Index (100-200ms)      │
│  - Search pre-built web index (billions of pages)    │
│  - BM25 + dense retrieval hybrid                     │
│  - Return top-50 candidate pages                     │
│  - Parallel: Also hit live search API for freshness  │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Stage 3: Quality Reranking (200-400ms)              │
│  - Cross-encoder reranks top-50 → top-5-10          │
│  - Source authority weighting                        │
│  - Freshness boost for time-sensitive queries        │
│  - Diversity enforcement (not all same source)       │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Stage 4: Verified Generation (1-2s)                 │
│  - Custom LLM with inline citation training          │
│  - Generates answer with [1][2][3] citations         │
│  - Structured to reference specific passages         │
│  - Post-generation: Citation link verification       │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Stage 5: Quality Gates                              │
│  - Are all citations from retrieved sources?         │
│  - Does answer contain claims not in sources?        │
│  - Confidence score: Low → add hedging language      │
└─────────────────────────────────────────────────────┘
```

### Handling Conflicting Information

The web is full of contradictions. Perplexity's approach:

1. **Source credibility hierarchy:**
   - Tier 1: Official documentation, .gov, peer-reviewed
   - Tier 2: Established news outlets, Wikipedia
   - Tier 3: Forums, blogs, social media
   - When sources conflict: Prefer higher tier

2. **Temporal resolution:**
   - If sources from different dates disagree, prefer most recent
   - Explicitly state "As of [date]..." for time-sensitive information
   - Show timeline when information has changed

3. **Explicit disagreement acknowledgment:**
   - "According to [Source A]... However, [Source B] states..."
   - Never silently pick one side when credible sources disagree
   - Let the user see the conflict

### Citation Accuracy

Perplexity maintains >90% citation accuracy through:
- **Training the model specifically for inline citation generation** (not just appending sources)
- **Post-generation verification:** Each [N] citation is checked against retrieved content
- **Passage-level citations:** Not just page-level but specific paragraph matching
- **User feedback loop:** Incorrect citations are logged and used for model improvement

### Performance at Scale

- Query-to-first-token: ~800ms
- Full response: 2-3 seconds
- Citation accuracy: >90% (independently measured)
- Source diversity: Average 4-6 unique sources per answer
- Freshness: News queries answered with content <1 hour old

### Key Architectural Lessons

1. **Hybrid retrieval (sparse + dense) is essential at web scale** — neither alone is sufficient
2. **Reranking is non-negotiable** — top-50 from a billion-page index has significant noise
3. **The model must be trained/fine-tuned for citation** — prompt engineering alone doesn't achieve >90% citation accuracy
4. **Live search as a supplement** — pre-built index can't be fresh enough for breaking news
5. **Speed budget allocation matters:** 50ms query understanding + 200ms retrieval + 300ms reranking + 1500ms generation = 2050ms total

---

## Case Study 2: Banking RAG — 100K to 8M Compliance Documents with Zero-Hallucination Mandate

### The Regulatory Requirement

A major US bank needed to serve their compliance officers with a RAG system over regulatory documents. The constraint: **any incorrect answer about a regulation could result in millions in fines from SEC, FINRA, or OCC.** Zero-tolerance for hallucination on regulatory content.

### Starting Point (100K Documents)

Initial deployment:
- 100K regulatory documents (SEC filings, FINRA rules, OCC guidance)
- Single Qdrant instance (8GB RAM)
- Full claim verification on every response
- GPT-4 as generation + verification
- Hallucination rate: 1.2% (measured by compliance team weekly review)
- Latency: 5-7 seconds (acceptable for compliance officers)
- Cost: $8K/month

### Growth Trigger

Mandate to include:
- All historical regulations (back to 2000)
- Internal compliance memos
- Enforcement actions and penalties
- Cross-jurisdictional regulations (EU, UK)
- Client correspondence related to compliance

Total: 8M documents. 80x growth.

### The Scaling Journey

**Phase 1: Direct scale-up (failed)**
- Loaded 8M documents into larger vector DB cluster
- Hallucination rate spiked from 1.2% to 9.8%
- Root cause: Retrieval quality degraded — top-5 now contained tangentially relevant historical documents that confused the model
- Compliance team halted the system

**Phase 2: Architecture redesign**

```
Query → Regulatory Domain Classifier → Route to specific shard:
                                        ├── SEC regulations
                                        ├── FINRA rules
                                        ├── OCC guidance
                                        ├── EU regulations
                                        ├── Internal memos
                                        └── Enforcement actions
```

Sharding reduced per-shard search space by 6-10x.

**Phase 3: Three-layer verification**

```
Layer 1: Retrieval Quality Gate
  - Cross-encoder reranking (top-50 → top-5)
  - Minimum relevance threshold: 0.82 (if nothing passes, abstain)
  - Authority scoring: Current regulation > superseded regulation
  - Temporal filter: If regulation has been amended, only retrieve current version

Layer 2: NLI Verification
  - Every response decomposed into claims
  - Each claim verified against source via NLI (DeBERTa fine-tuned on legal NLI)
  - Any CONTRADICTED claim → response rejected, regenerated
  - Any NEUTRAL claim → flagged with caveat "This may not be directly stated in the regulation"

Layer 3: Human Review (risk-tiered)
  - Queries about penalties/enforcement: Mandatory human review before serving
  - Queries about specific dollar amounts: Mandatory human verification
  - General regulatory questions: Served immediately, async human audit on 20%
  - Clarification/summary requests: No human review needed
```

**Phase 4: Result**

| Metric | Before (100K) | Failed Scale (8M) | After Redesign (8M) |
|--------|---------------|-------------------|-----------------------|
| Documents | 100K | 8M | 8M |
| Hallucination rate | 1.2% | 9.8% | 0.3% |
| Groundedness | 97.5% | 88% | 99.7% |
| Latency | 5-7s | 4-6s | 3-8s (risk-dependent) |
| Abstention rate | 5% | 3% (too low!) | 12% (appropriate) |
| Monthly cost | $8K | $12K | $65K |

**Key insight:** The abstention rate of 3% at 8M documents was a red flag — the system was answering questions it shouldn't have been confident about. After redesign, the 12% abstention rate (with escalation to human) was actually the correct behavior.

### Lessons Learned

1. **Scaling a RAG system is not just adding compute — it requires architectural rethinking**
2. **Domain-specific sharding is the single most impactful quality lever at scale**
3. **Abstention is a feature, not a failure** — better to say "I'm not sure" than to hallucinate a regulation
4. **Fine-tuned NLI models for your domain (legal, medical) outperform general NLI** — the bank trained on 50K legal entailment pairs
5. **Human-in-the-loop is acceptable and often required for high-stakes domains**
6. **The cost increase (8x) is trivial compared to the cost of a wrong answer** — one compliance violation costs more than years of infrastructure

---

## Case Study 3: Enterprise Hallucination Spike — Root Cause Analysis

### The Scenario

A SaaS company providing AI-powered customer support scaled their knowledge base from 2M to 15M documents (adding historical tickets, product changelogs, community forums). Their hallucination rate went from 2.1% to 12.4% over 3 weeks.

### Detection

- Week 1 of expansion: Hallucination rate 3.8% (monitoring alert at 3%)
- Week 2: Rate climbed to 7.2% (P1 incident declared)
- Week 3: Rate reached 12.4% (system partially disabled for investigation)

### Root Cause Analysis

**Finding 1: Retrieval precision collapsed**
```
Before expansion (2M docs):
  Average cosine similarity of top-5 results: 0.87
  All 5 results typically from relevant product/topic
  
After expansion (15M docs):
  Average cosine similarity of top-5 results: 0.71
  Often 2-3 of top-5 were from different products or outdated
```

The embedding space became more crowded. Documents about similar topics from different products clustered together, and top-K retrieval pulled from multiple unrelated contexts.

**Finding 2: No metadata pre-filtering**
- Queries about Product A were retrieving documents about Product B (similar features, different products)
- Historical tickets (resolved years ago) were retrieved as if current
- Community forum posts (user-generated, sometimes incorrect) ranked alongside official docs

**Finding 3: Contradicting sources**
- 3% of queries had retrieved documents that directly contradicted each other
- Example: Old documentation said "Feature X supports 100 users" while current docs said "Feature X supports 10,000 users"
- The model was generating answers that averaged or conflated these

### The Fix (Applied in Order)

**Fix 1: Metadata pre-filtering (immediate, 2 days)**
```python
# Before: Search all 15M vectors
results = search(query_embedding, top_k=20)

# After: Filter to relevant product + time window
results = search(
    query_embedding, 
    top_k=20,
    filter={
        "product": detected_product,      # From query classification
        "source_type": ["official_docs", "internal_kb"],  # Exclude forums
        "status": "current",              # Exclude superseded docs
        "created_after": "2023-01-01"     # Exclude very old content
    }
)
```

Impact: Reduced effective search space from 15M to ~500K per query.
Hallucination rate: 12.4% → 5.8% (immediately)

**Fix 2: Cross-encoder reranking upgrade (1 week)**
```
Before: Top-5 from ANN directly fed to LLM
After: Top-20 from ANN → Cross-encoder reranks → Top-5 to LLM

Reranker: BGE-reranker-v2-m3 (fine-tuned on 10K query-document pairs from their domain)
```

Impact: Top-5 precision improved from 62% to 84%.
Hallucination rate: 5.8% → 3.2%

**Fix 3: Contradiction detection (2 weeks)**
```python
# After retrieval, before generation:
for i, doc_a in enumerate(top_5):
    for doc_b in top_5[i+1:]:
        contradiction_score = nli_model.predict(doc_a.text, doc_b.text)
        if contradiction_score > 0.8:
            # Remove the less authoritative / older document
            # Or: Present both with sources if can't determine
            resolve_contradiction(doc_a, doc_b)
```

Impact: 3% of queries had contradictions detected and resolved.
Hallucination rate: 3.2% → 1.8%

### Final Result

| Metric | Before Expansion | During Crisis | After Fix |
|--------|-----------------|---------------|-----------|
| Corpus size | 2M | 15M | 15M |
| Hallucination rate | 2.1% | 12.4% | 1.8% |
| Retrieval precision@5 | 81% | 52% | 84% |
| Average latency | 1.8s | 2.1s | 2.4s |
| Monthly cost | $35K | $38K | $52K |

**The 0.6s latency increase and $17K cost increase paid for 10x quality improvement.**

### Post-Mortem Recommendations

1. **Never scale corpus without testing retrieval quality first** — run eval suite at each 2x growth
2. **Metadata pre-filtering should be mandatory** — it's cheap and massively improves precision
3. **Set up automated hallucination monitoring before scaling** — they caught it at 3.8% because they had monitoring
4. **Community/user-generated content needs lower authority scores** — treat as supplementary, never primary
5. **Document versioning is critical** — superseded documents should be marked and de-prioritized

---

## Case Study 4: Scaling NLI Verification to 5000 QPS

### The Challenge

An AI company needed to verify every claim in their RAG responses against source documents. At 5000 QPS with an average of 4 claims per response, they needed 20,000 NLI inferences per second.

### Architecture

```
Response + Claims + Context
         │
         ▼
┌─────────────────────────────────────────────┐
│          Claim Cache (Redis)                 │
│  Key: hash(claim + context_chunk)           │
│  Hit rate: 35%                               │
│  Effective load: 20K → 13K inferences/sec   │
└───────────────────┬─────────────────────────┘
                    │ (cache misses)
                    ▼
┌─────────────────────────────────────────────┐
│          Batch Accumulator                   │
│  Waits up to 5ms to fill batch of 64        │
│  Maximizes GPU utilization                   │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│     GPU Inference Cluster                    │
│     4x NVIDIA A10G (24GB each)              │
│                                              │
│     Model: DeBERTa-large fine-tuned NLI     │
│     Batch size: 64 claim-context pairs       │
│     Throughput: 1200 inferences/sec/GPU      │
│     Total: 4800 inferences/sec               │
│                                              │
│     With cache (35% hit): Effective 7400/s   │
│     With tiering: Only 65% verified = 4800/s │
│     Comfortable headroom at 5000 QPS         │
└─────────────────────────────────────────────┘
```

### Model Selection

| Model | Accuracy (NLI) | Throughput (A10G) | Cost/1M inferences |
|-------|----------------|-------------------|---------------------|
| GPT-4 (API) | 94% | ~100/sec | $20.00 |
| GPT-3.5 (API) | 87% | ~500/sec | $2.00 |
| DeBERTa-large (self-hosted) | 91% | 1200/sec | $0.15 |
| DeBERTa-base (self-hosted) | 88% | 2400/sec | $0.08 |
| MiniLM-L6 (self-hosted) | 82% | 5000/sec | $0.04 |

**Decision:** DeBERTa-large fine-tuned on domain-specific NLI data.
- 91% accuracy (close to GPT-4's 94%, much better than smaller models)
- 1200/sec throughput (100x GPT-4 API)
- $0.15/M vs $20/M (133x cheaper than GPT-4)

### Fine-tuning for Domain-Specific NLI

Training data creation:
1. Took 10K RAG responses with known groundedness labels (from human eval)
2. Decomposed into 45K individual claims
3. Paired each claim with its source context
4. Human annotators labeled: ENTAILED / CONTRADICTED / NEUTRAL
5. Fine-tuned DeBERTa-large on this domain-specific dataset

Result: Domain-specific accuracy improved from 88% (base NLI) to 91% (fine-tuned).

### Cost Comparison at 5000 QPS

```
Monthly verification volume: 5000 QPS × 4 claims × 86400 sec × 30 days = 51.8B claims
With 35% cache hit: 33.7B actual inferences needed
With tiering (65% verified): 21.9B inferences needed

Option A: GPT-4 API
  21.9B × $0.00002 = $438,000/month
  
Option B: Self-hosted DeBERTa-large (4x A10G)
  Infrastructure: 4 × $1.50/hr × 730 hrs = $4,380/month
  Total: $4,380/month

Savings: 99% cost reduction with 3% accuracy trade-off
```

### Key Lessons

1. **Caching is the first optimization** — 35% of claims are repeated (same context + same claim pattern)
2. **Batching dramatically improves GPU utilization** — single inference wastes 80% of GPU capacity
3. **Domain fine-tuning is worth the investment** — 3% accuracy improvement on your specific data
4. **Tiered verification reduces load** — not all queries need verification (50% saved)
5. **Self-hosted models are 100x cheaper at scale** — API costs don't scale

---

## Case Study 5: Memory Math Walkthrough — Planning Infrastructure for 10M Vectors

### The Scenario

A company needs to serve 10M document chunks (1536-dimensional embeddings from text-embedding-3-small) with <20ms retrieval latency and 99.9% availability.

### Raw Storage Calculation

```
10,000,000 vectors × 1,536 dimensions × 4 bytes (float32) = 61.4 GB

Metadata per vector (average):
  - document_id: 16 bytes (UUID)
  - tenant_id: 16 bytes
  - timestamp: 8 bytes
  - source_type: 4 bytes (enum)
  - tags: ~50 bytes average
  Total metadata: ~94 bytes × 10M = 940 MB ≈ 1 GB

Total raw data: ~62.4 GB
```

### Index Overhead by Type

**HNSW (M=16, ef_construction=200):**
```
Graph structure overhead:
  - Per vector: M × 2 × sizeof(int) × avg_layers
  - M=16, avg 1.3 layers: 16 × 2 × 4 × 1.3 = 166 bytes/vector
  - Total graph: 166 bytes × 10M = 1.66 GB

Additional overhead:
  - Node metadata: ~20 bytes/vector = 200 MB
  - Memory allocator overhead: ~10% = 6.2 GB

Total HNSW: 62.4 + 1.66 + 0.2 + 6.2 ≈ 70.5 GB
With safety margin (20%): ~86 GB per node
```

**IVF (nlist=4096, nprobe=32):**
```
Centroid storage: 4096 × 1536 × 4 = 25 MB (negligible)
Inverted lists: ~62.4 GB (same as raw vectors, different layout)
Total: ~63 GB (can be partially disk-backed)
```

**DiskANN (R=64, L=100):**
```
In-memory: Compressed graph (~4 GB with PQ compression)
On-disk: Full vectors (62.4 GB on NVMe SSD)
RAM requirement: ~8-12 GB (dramatic reduction)
Disk requirement: ~70 GB NVMe
```

### Option A: All-RAM HNSW (3x Replication)

```
Per node: 86 GB RAM needed
Replication factor: 3 (for 99.9% availability)
Total RAM across cluster: 258 GB

Node sizing: 3 nodes × 96 GB RAM (c5.12xlarge or equivalent)
  - CPU: 48 vCPU per node (HNSW search is CPU-bound)
  - RAM: 96 GB per node
  - Network: 25 Gbps (replication traffic)
  - Storage: 500 GB NVMe (persistence, not primary serving)

Cloud cost estimate (AWS):
  - 3 × c5.12xlarge on-demand: 3 × $2.04/hr = $6.12/hr = $4,467/month
  - Reserved (1yr): ~$2,800/month
  - With monitoring, load balancer: ~$3,200/month total

Performance:
  - Query latency: 2-5ms (p99: 8ms)
  - Throughput: ~10,000 QPS per node
  - Total cluster: 30,000 QPS capacity
  - Failover: Any node fails, remaining 2 serve (degraded throughput)
```

### Option B: DiskANN on NVMe (3x Replication)

```
Per node: 12 GB RAM + 100 GB NVMe SSD
Replication factor: 3

Node sizing: 3 nodes × 32 GB RAM + NVMe (i3.xlarge or equivalent)
  - CPU: 4 vCPU per node
  - RAM: 32 GB (12 GB for index, rest for OS/cache)
  - Storage: 475 GB NVMe (local)
  - Network: 10 Gbps

Cloud cost estimate (AWS):
  - 3 × i3.xlarge on-demand: 3 × $0.312/hr = $0.94/hr = $682/month
  - Reserved (1yr): ~$430/month
  - With monitoring, load balancer: ~$700/month total

Performance:
  - Query latency: 5-12ms (p99: 20ms)
  - Throughput: ~3,000 QPS per node
  - Total cluster: 9,000 QPS capacity
  - Trade-off: Higher latency, lower throughput, 6x cheaper
```

### Option C: Hybrid (HNSW for Hot, DiskANN for Warm)

```
Hot tier (1M most-accessed vectors): 1 node × 16 GB RAM (HNSW)
Warm tier (9M remaining vectors): 2 nodes × 32 GB RAM (DiskANN)
Total: 3 nodes

Routing logic:
  - Check hot tier first (2ms)
  - If insufficient results: Also query warm tier (8ms)
  - Most queries (70%) answered from hot tier alone

Cost estimate: ~$1,500/month
Performance: 2-10ms depending on tier hit
```

### Decision Framework

```
┌────────────────────┬──────────────┬──────────────┬──────────────┐
│ Requirement        │ Choose HNSW  │ Choose DiskANN│ Choose Hybrid│
├────────────────────┼──────────────┼──────────────┼──────────────┤
│ Latency <5ms p99   │ ✓            │              │ ✓ (hot tier) │
│ Budget < $1K/month │              │ ✓            │ ✓            │
│ >50K QPS needed    │ ✓            │              │              │
│ Cost-sensitive     │              │ ✓            │ ✓            │
│ <20ms acceptable   │ ✓            │ ✓            │ ✓            │
│ Uneven access      │              │              │ ✓            │
└────────────────────┴──────────────┴──────────────┴──────────────┘
```

### Scaling Beyond 10M

At 100M vectors:
- All-RAM HNSW: 860 GB RAM cluster = $30K-50K/month (expensive)
- DiskANN: 12 nodes × 32 GB + NVMe = $5K-8K/month (viable)
- Sharded HNSW (10 shards × 10M each): $10K-15K/month (balanced)

**Recommendation for most cases:** DiskANN or sharded HNSW with quantization beyond 10M vectors.

---

## Case Study 6: The Stale Document Hallucination

### The Scenario

A company's HR policy document was updated at 2:00 PM:
- **Old version:** "Remote work requires manager approval and is limited to 2 days per week"
- **New version:** "Remote work is available to all employees up to 5 days per week"

The vector DB ingestion pipeline ran every 6 hours (next run at 6:00 PM).

### The Impact

Between 2:00 PM and 6:00 PM:
- 47 queries about remote work policy
- All 47 answered with the OLD policy (2 days, manager approval)
- 12 employees made decisions based on wrong information
- 3 escalated to HR when told different information in person
- Result: Trust in the AI system damaged, executive escalation

### Root Cause

```
Document Source (SharePoint)
    │ Updated at 2:00 PM
    │
    ▼ (no trigger)
    
Batch Ingestion Pipeline (runs every 6 hours)
    │ Next run at 6:00 PM
    │
    ▼
    
Vector DB (still has old embeddings until 6:00 PM)
    │
    ▼
    
RAG System (serves old information with high confidence)
```

The system had no mechanism to detect source changes between batch runs.

### The Fix: Event-Driven CDC Pipeline

```
Document Source (SharePoint/Confluence/etc)
    │ 
    ├──→ Change Event (webhook/CDC)
    │         │
    │         ▼ (immediate)
    │    ┌──────────────────────┐
    │    │ Change Processor      │
    │    │ 1. Detect what changed│
    │    │ 2. Invalidate caches  │
    │    │ 3. Re-chunk document  │
    │    │ 4. Re-embed chunks    │
    │    │ 5. Update vector DB   │
    │    └──────────────────────┘
    │              │
    │              ▼
    │    Vector DB updated within 5 minutes
    │
    └──→ Freshness Monitor
              │
              ▼
         Dashboard: "Staleness by source"
         Alert: Any source >30min stale
```

### Implementation Details

```python
# CDC listener (webhook from document management system)
@app.post("/document-updated")
async def handle_document_update(event: DocumentUpdateEvent):
    doc_id = event.document_id
    
    # Step 1: Immediately invalidate cached responses referencing this doc
    await cache.invalidate_by_source(doc_id)
    
    # Step 2: Mark old vectors as stale (queries will deprioritize them)
    await vector_db.update_metadata(
        filter={"document_id": doc_id},
        update={"stale": True, "stale_since": datetime.utcnow()}
    )
    
    # Step 3: Queue re-processing (typically completes in 2-5 minutes)
    await ingestion_queue.enqueue(
        priority="HIGH",  # Skip ahead of normal batch ingestion
        task="reindex_document",
        document_id=doc_id,
        source_url=event.source_url
    )
    
    # Step 4: Log freshness event
    metrics.record("document_update_detected", {
        "document_id": doc_id,
        "detection_latency_ms": event.change_time_to_now_ms
    })

# Query-time freshness check
def retrieve_with_freshness(query, filters):
    results = vector_db.search(query, filters)
    
    for result in results:
        if result.metadata.get("stale"):
            # Option A: Exclude stale results
            # Option B: Include but add caveat
            result.score *= 0.3  # Heavily penalize stale results
            result.caveat = "This information may have been recently updated."
    
    return results
```

### Monitoring Dashboard

```
┌─────────────────────────────────────────────────┐
│         Document Freshness Dashboard             │
├─────────────────────────────────────────────────┤
│                                                  │
│  Source: HR Policies      Freshness: 99.8%       │
│  Source: Product Docs     Freshness: 97.2%       │
│  Source: Engineering Wiki Freshness: 95.1%       │
│  Source: Customer FAQs    Freshness: 99.9%       │
│                                                  │
│  ⚠️  Alert: 3 documents >30min stale             │
│  - /hr/remote-work-policy (45min)               │
│  - /eng/api-limits (38min)                       │
│  - /product/pricing-2024 (32min)                │
│                                                  │
│  Average staleness: 4.2 minutes                  │
│  SLA: <5 minutes (✓ MET)                         │
│  p99 staleness: 12 minutes                       │
│  Max staleness: 45 minutes (⚠️ BREACH)           │
└─────────────────────────────────────────────────┘
```

### Result After Fix

- Average document freshness: 4.2 minutes (from 6 hours)
- Stale-document hallucinations: Reduced from ~2% of answers to <0.1%
- Cost increase: $200/month for CDC infrastructure
- Value: Prevented repeat of trust-damaging incidents

---

## Case Study 7: Cross-Tenant Hallucination — The Scariest Bug in Multi-Tenant RAG

### The Scenario

A B2B SaaS company provides an AI assistant that answers questions from each customer's uploaded knowledge base. Each customer (tenant) should ONLY see answers from their own documents.

### The Incident

**What happened:** A user from Company A asked "What is our parental leave policy?" The system returned an answer citing Company B's parental leave policy (16 weeks) instead of Company A's (12 weeks).

**How it was detected:** Company A's HR director noticed the answer didn't match their policy and reported it. Audit log investigation revealed the source document belonged to Company B.

### Root Cause

The metadata filter in the vector search had a bug:

```python
# BUGGY CODE (simplified)
def search_for_tenant(query_embedding, tenant_id, department=None):
    filters = []
    filters.append({"tenant_id": tenant_id})
    
    if department:
        filters.append({"department": department})
    
    # BUG: Using OR instead of AND
    # This meant: tenant_id = A OR department = "HR"
    # When department = "HR", it returned ALL HR documents across ALL tenants
    return vector_db.search(
        query_embedding, 
        filter={"$or": filters}  # Should be "$and"
    )
```

The bug was introduced in a refactoring 3 weeks prior. It only manifested when the optional `department` filter was present — making it hard to catch in testing.

### Impact Assessment

- Duration: 3 weeks (bug existed before detection)
- Affected queries: ~2,400 queries where department filter was active
- Cross-tenant data exposure: 847 queries returned results from wrong tenant
- Unique tenants affected: 23 tenants had data exposed to other tenants
- Severity: Critical (data breach, contractual violation, potential legal liability)

### Immediate Response

1. **System disabled** within 30 minutes of confirmed cross-tenant access
2. **Full audit:** Replay all queries from past 3 weeks, identify every cross-tenant access
3. **Customer notification:** All affected customers notified within 24 hours
4. **Legal review:** Contractual obligations assessed, incident reported per data processing agreements

### The Fix: Defense in Depth

```python
# Fix 1: Correct the filter logic (immediate)
def search_for_tenant(query_embedding, tenant_id, department=None):
    filters = {"tenant_id": tenant_id}  # Always required, always AND
    
    if department:
        filters["department"] = department
    
    return vector_db.search(
        query_embedding,
        filter=filters  # Implicit AND between all conditions
    )

# Fix 2: Namespace isolation (architectural)
# Each tenant gets a completely separate collection/namespace
# Even if filter fails, can't cross namespaces
def search_for_tenant_v2(query_embedding, tenant_id, **kwargs):
    # Tenant namespace is the collection itself — no filter needed for isolation
    collection = f"tenant_{tenant_id}"
    return vector_db.search(
        collection=collection,
        query=query_embedding,
        filter=kwargs  # Additional filters within tenant's namespace
    )

# Fix 3: Post-retrieval ACL check (belt and suspenders)
def search_with_acl_check(query_embedding, tenant_id, **kwargs):
    results = search_for_tenant_v2(query_embedding, tenant_id, **kwargs)
    
    # Even after namespace isolation, verify every returned document
    verified_results = []
    for result in results:
        doc_tenant = document_acl_service.get_tenant(result.document_id)
        if doc_tenant != tenant_id:
            # THIS SHOULD NEVER HAPPEN if namespace isolation works
            # But if it does, we catch it here
            alert_security_team(
                f"Cross-tenant access attempt: {tenant_id} saw {doc_tenant}'s doc"
            )
            continue  # Skip this result
        verified_results.append(result)
    
    return verified_results

# Fix 4: Continuous monitoring
def audit_cross_tenant_access():
    """Runs every 5 minutes, checks recent responses for cross-tenant leakage."""
    recent_responses = get_responses_last_5_minutes()
    for response in recent_responses:
        for source in response.cited_sources:
            if source.tenant_id != response.requesting_tenant_id:
                trigger_critical_alert(response)
```

### Architecture After Fix

```
┌────────────────────────────────────────────────────────────────┐
│                    Defense in Depth Layers                       │
│                                                                  │
│  Layer 1: Namespace Isolation                                    │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ Each tenant has separate vector DB collection         │       │
│  │ Physical isolation — impossible to query across        │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Layer 2: Metadata Filter (even within namespace)                │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ tenant_id filter always applied as AND condition      │       │
│  │ Filter logic reviewed in code review checklist        │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Layer 3: Post-Retrieval ACL Verification                        │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ Every returned document verified against ACL service  │       │
│  │ Any mismatch = immediate alert + result excluded      │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Layer 4: Response Audit                                         │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ Every response logged with source tenant IDs          │       │
│  │ Continuous monitoring for cross-tenant patterns       │       │
│  │ Weekly penetration testing with cross-tenant queries  │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Lessons Learned

1. **Never rely on a single layer for tenant isolation** — one bug bypasses everything
2. **Namespace isolation > metadata filtering** — physical separation is safer than logical filtering
3. **Post-retrieval ACL is cheap insurance** — one extra DB lookup per result saves you from data breaches
4. **Audit logging is non-negotiable** — without it, you can't assess the blast radius
5. **Regular penetration testing** — specifically craft cross-tenant test queries weekly
6. **OR vs AND in filters is a category of bug that kills** — add specific linting rules
7. **The cost of this bug exceeded the entire year's infrastructure budget** — legal fees, customer notification, contractual penalties, trust damage

---

## Case Study 8: Cost of Quality at Scale — Real Budget Breakdown

### System Profile

- Scale: 10,000 QPS average, 25,000 QPS peak
- Daily queries: 864 million
- Corpus: 25M documents (enterprise knowledge base)
- SLA: <2s p99 latency, >95% groundedness, <2% hallucination

### Monthly Cost Breakdown

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monthly Cost Breakdown                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  LLM Generation                                    $180,000      │
│  ├── GPT-4o for high-risk queries (20%)              $95,000     │
│  ├── GPT-4o-mini for standard queries (60%)          $65,000     │
│  └── Cached responses (20% — no LLM call)            $20,000*   │
│      (* cache infrastructure cost)                               │
│                                                                   │
│  Retrieval Infrastructure                           $45,000      │
│  ├── Vector DB cluster (5 shards, 3 replicas)        $22,000     │
│  ├── Reranker GPU cluster (8x A10G)                  $12,000     │
│  ├── Embedding computation (query-time)               $5,000     │
│  ├── Redis caching cluster                            $4,000     │
│  └── Load balancers + networking                      $2,000     │
│                                                                   │
│  Verification Pipeline                              $28,000      │
│  ├── NLI verification GPU cluster (4x A10G)          $6,000      │
│  ├── Claim decomposition (LLM calls)                $12,000      │
│  ├── Citation verification                           $5,000      │
│  ├── Consistency checks (3x generation, 5% sample)   $3,000      │
│  └── Verification caching                            $2,000      │
│                                                                   │
│  Monitoring & Evaluation                            $8,000       │
│  ├── Canary query system                             $1,500      │
│  ├── Human evaluation (weekly sample)                $4,000      │
│  ├── Dashboards + alerting infrastructure            $1,500      │
│  └── Logging + audit trail                           $1,000      │
│                                                                   │
│  Ingestion Pipeline                                 $12,000      │
│  ├── Document processing (chunking, parsing)         $3,000      │
│  ├── Embedding computation (batch)                   $5,000      │
│  ├── CDC infrastructure                              $2,000      │
│  └── Queue infrastructure (Kafka)                    $2,000      │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│  TOTAL                                             $273,000/mo   │
└─────────────────────────────────────────────────────────────────┘
```

### ROI Analysis: Is Verification Worth It?

**Without verification (save $28K/month):**
- Hallucination rate: ~8% (based on pre-verification measurements)
- At 864M queries/day × 30 days = 25.9B queries/month
- 8% hallucinated = 2.07B wrong answers/month
- Even if only 1% of wrong answers cause business impact: 20.7M impactful wrong answers

**Business cost of wrong answers:**
- Customer support escalation from wrong answer: $15 per incident
- Customer churn from repeated bad experience: $500 per churned customer
- Brand damage (social media complaint): $200 estimated impact
- Conservative estimate: 0.01% of wrong answers cause $15 impact = $3.1M/month in damage

**With verification ($28K/month):**
- Hallucination rate: 1.8%
- Wrong answers reduced by 77%
- Damage reduced from $3.1M to $700K/month
- Net savings: $2.4M/month from $28K investment
- **ROI: 85x return on verification investment**

### Cost Optimization Strategies

```
Strategy 1: Tiered LLM Selection (saves 40% on LLM costs)
  Before: GPT-4 for all queries = $350K/month
  After: GPT-4 for 20% high-risk, GPT-4o-mini for 60%, cached for 20% = $180K/month

Strategy 2: Response Caching (saves 20% on total cost)
  Cache hit rate: 20% (common queries answered without LLM/retrieval)
  Savings: $54K/month in avoided computation
  Cache infrastructure cost: $20K/month
  Net savings: $34K/month

Strategy 3: Distilled Verification (saves 70% vs GPT-4 verification)
  Before: GPT-4 for NLI verification = $95K/month
  After: Self-hosted DeBERTa on GPUs = $6K/month + $12K claim decomposition
  Accuracy trade-off: 94% → 91% (acceptable with monitoring)

Strategy 4: Query Routing to Reduce Retrieval (saves 30% on retrieval)
  Before: Query all shards for every query
  After: Route to specific shard(s) — average 1.5 shards queried instead of 5
  Retrieval cost reduction: $45K → $31K/month
```

---

## Case Study 9: A/B Test Results — Impact of Hallucination Defenses

### Test Setup

- Duration: 4 weeks
- Traffic: 50,000 QPS total, split across 7 variants
- Evaluation: 1000 queries per variant evaluated by human raters (binary: hallucinated or not)
- Additional metrics: Latency, user satisfaction (thumbs up/down), cost per query

### Results

| Variant | Hallucination Rate | p50 Latency | p99 Latency | User Satisfaction | Cost/Query |
|---------|-------------------|-------------|-------------|-------------------|------------|
| Control (basic RAG) | 8.2% | 0.9s | 1.5s | 72% | $0.008 |
| +Reranking | 5.1% | 1.1s | 1.8s | 78% | $0.010 |
| +Freshness decay | 4.3% | 1.1s | 1.8s | 80% | $0.010 |
| +Citation forcing | 3.1% | 1.3s | 2.1s | 83% | $0.012 |
| +NLI verification | 1.4% | 1.8s | 3.2s | 86% | $0.018 |
| +Consistency (3x) | 0.8% | 3.2s | 5.8s | 84%* | $0.042 |
| All defenses | 0.6% | 3.5s | 6.2s | 82%* | $0.048 |

*User satisfaction decreased for slowest variants due to latency frustration.

### Analysis

**Marginal benefit of each defense:**

```
Reranking:         -3.1% hallucination, +0.2s latency → 15.5 points per second
Freshness decay:   -0.8% hallucination, +0.0s latency → Free improvement
Citation forcing:  -1.2% hallucination, +0.2s latency → 6.0 points per second
NLI verification:  -1.7% hallucination, +0.5s latency → 3.4 points per second
Consistency check: -0.6% hallucination, +1.4s latency → 0.4 points per second
```

**Diminishing returns are real:** The first 3 defenses (reranking + freshness + citation) reduce hallucination by 5.1 percentage points with only 0.4s latency increase. The last 2 defenses reduce by only 2.3 more points but add 2.2s latency.

### Recommended Configuration by Use Case

**Low-latency requirement (<1.5s):**
- Reranking + freshness decay
- Hallucination: ~4.3%
- Good for: Chat assistants, real-time support

**Balanced (1.5-2.5s acceptable):**
- Reranking + freshness + citation forcing + lightweight NLI
- Hallucination: ~2%
- Good for: Enterprise knowledge bases, internal tools

**High-accuracy requirement (latency flexible):**
- All defenses
- Hallucination: <1%
- Good for: Medical, legal, financial, compliance

**Cost-sensitive:**
- Reranking + freshness + citation forcing (no GPU needed for NLI)
- Hallucination: ~3.1%
- Cost: $0.012/query (50% cheaper than full stack)
- Good for: High-volume, lower-stakes applications

### Surprising Finding

The consistency check (3x generation) **hurt user satisfaction** despite improving hallucination rate. Root cause: The 3.2s → 5.8s p99 latency increase frustrated users more than the 0.6% quality improvement pleased them. Users prefer a slightly-less-perfect fast answer over a near-perfect slow one — except in high-stakes domains.

**Lesson:** Measure user satisfaction holistically, not just accuracy. The "best" system isn't always the most accurate one.

---

## Case Study 10: Confidence Threshold Tuning

### The Problem

An AI assistant for a healthcare company was configured with aggressive abstention: refuse to answer if confidence < 0.8. This was meant to prevent hallucination in a high-stakes domain.

**Result:** The system was refusing 30% of all queries.

User feedback:
- "Why does the AI never know anything?"
- "I asked a simple question and it said it couldn't help"
- "I'm going back to Google, at least it gives me something"

### Investigation

Analysis of 5,000 refused queries:
- **20% truly unanswerable:** Question was out of scope or required information not in the knowledge base ✓ (correct refusal)
- **35% answerable with medium confidence:** Information existed but phrased differently, or required minor inference ✗ (over-refusal)
- **30% answerable with high confidence:** Information was clearly in the knowledge base, but retrieval scored below threshold due to paraphrasing ✗ (retrieval issue)
- **15% answerable from multiple partial sources:** No single document fully answered, but combination did ✗ (context assembly issue)

**Only 20% of refusals were correct.** The system was 80% wrong in its refusals.

### Root Cause

1. **Single global threshold (0.8) was too blunt** — what's "risky" varies enormously by domain
2. **Confidence was based solely on retrieval score** — didn't account for evidence completeness
3. **Paraphrase mismatch** — embeddings scored lower when question phrasing differed from document phrasing
4. **No partial-answer option** — either full answer or full refusal, nothing in between

### The Fix: Domain-Adaptive Confidence

```python
# Before: Single threshold
def should_answer(retrieval_score):
    return retrieval_score > 0.8  # Same for everything

# After: Domain-adaptive thresholds + multi-signal confidence
def should_answer(query, retrieval_results, domain):
    # Signal 1: Retrieval relevance
    retrieval_confidence = max(r.score for r in retrieval_results)
    
    # Signal 2: Coverage (does context cover the question?)
    coverage = estimate_coverage(query, retrieval_results)
    
    # Signal 3: Source authority
    authority = max(r.authority_score for r in retrieval_results)
    
    # Combined confidence
    confidence = (
        retrieval_confidence * 0.4 +
        coverage * 0.4 +
        authority * 0.2
    )
    
    # Domain-specific thresholds
    thresholds = {
        "medication_dosage": 0.85,   # Very strict — wrong dosage is dangerous
        "drug_interactions": 0.85,   # Very strict
        "side_effects": 0.75,        # Moderate — common question, lower risk
        "appointment_scheduling": 0.5, # Low risk — logistical
        "general_health_info": 0.6,  # Moderate — general wellness
        "insurance_coverage": 0.7,   # Moderate — financial impact
        "emergency_guidance": 0.9,   # Strictest — life-threatening
    }
    
    threshold = thresholds.get(domain, 0.7)  # Default moderate
    
    if confidence > threshold:
        return "answer"
    elif confidence > threshold - 0.15:
        return "answer_with_caveat"  # Answer but add uncertainty language
    else:
        return "refuse_with_suggestion"  # Refuse but suggest where to find answer
```

### Graduated Response Strategy

```
Instead of binary answer/refuse:

Level 1 (confidence > threshold): Full answer
  "Based on your records, your next appointment is March 15 at 2:00 PM."

Level 2 (confidence within 0.15 of threshold): Answer with caveat
  "Based on the information available, [answer]. However, I'd recommend 
   confirming this with your care team for the most up-to-date information."

Level 3 (confidence below threshold - 0.15): Partial answer + redirect
  "I found some related information but I'm not confident enough to give 
   you a definitive answer about drug interactions. I'd recommend:
   - Contacting your pharmacist at [number]
   - Checking with your prescribing physician
   Here's what I did find: [partial info with heavy caveats]"

Level 4 (no relevant information found): Clear refusal + help
  "I don't have information about this topic in my knowledge base. 
   For questions about [topic], please contact [specific resource]."
```

### Results After Tuning

| Metric | Before Tuning | After Tuning | Target |
|--------|---------------|--------------|--------|
| Refusal rate (total) | 30% | 8% | 5-12% |
| Correct refusals | 6% (of all queries) | 6% | — |
| Over-refusals | 24% | 2% | <3% |
| Hallucination rate | 0.8% | 1.6% | <2% |
| User satisfaction | 61% | 84% | >80% |
| Escalation to human | 28% | 10% | <15% |

**Key trade-off:** Hallucination increased from 0.8% to 1.6% (still within budget). But user satisfaction increased from 61% to 84%. The system went from "useless" to "helpful" while staying within acceptable quality bounds.

### Tuning Process (Repeatable)

```
Step 1: Collect 1000+ refused queries
Step 2: Have domain experts label each as:
        - Correct refusal (truly unanswerable)
        - Over-refusal (answerable, should have answered)
Step 3: For over-refusals, identify WHY confidence was low:
        - Retrieval issue (fix retrieval, add synonyms)
        - Threshold too high (lower for this domain)
        - Partial information (enable graduated response)
Step 4: Adjust thresholds by domain based on:
        - Risk level of wrong answer in this domain
        - Frequency of over-refusal in this domain
        - User feedback specific to this domain
Step 5: Re-evaluate on held-out set
Step 6: Deploy with monitoring, iterate monthly
```

### Key Insight

**The optimal threshold is NOT the one that minimizes hallucination.** It's the one that maximizes user value while keeping hallucination within an acceptable budget. A system that refuses everything has 0% hallucination but 0% utility. Finding the right balance is the art of production RAG.

The hallucination budget framework makes this explicit:
- Medical dosage queries: Budget 0.5% hallucination → strict threshold
- Appointment scheduling: Budget 5% hallucination → relaxed threshold
- Overall system: Budget 2% hallucination → weighted average across domains

This is how you build a system that's both safe AND useful.

---

## Summary: Patterns Across All Case Studies

| Case Study | Core Lesson |
|------------|-------------|
| Perplexity | Multi-stage retrieval + reranking is non-negotiable at web scale |
| Banking RAG | Domain-specific sharding + tiered verification for regulated industries |
| Enterprise Spike | Metadata pre-filtering is the #1 lever when scaling corpus |
| NLI at 5000 QPS | Distilled models + caching make verification economically viable |
| Memory Math | DiskANN/quantization changes the economics of billion-scale RAG |
| Stale Documents | CDC pipelines with 5-min SLA prevent temporal hallucination |
| Cross-Tenant | Defense in depth — never rely on one layer for security |
| Cost Breakdown | Verification ROI is 85x — the cost of NOT verifying exceeds verification |
| A/B Testing | Reranking + citation forcing = best quality/latency trade-off |
| Confidence Tuning | Domain-adaptive thresholds maximize utility within hallucination budget |

The unifying theme: **Quality at scale requires engineering discipline, not just model improvements.** The system architecture — sharding, caching, tiering, monitoring, circuit breakers — determines quality more than any single model choice.
