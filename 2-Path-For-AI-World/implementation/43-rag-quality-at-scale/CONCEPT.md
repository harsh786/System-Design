# RAG Quality at Scale: Eliminating Hallucination While Serving Millions

## The Core Tension

RAG systems face an inverse relationship between scale and quality. As your corpus grows from thousands to millions of documents, hallucination rates increase unless you actively engineer against it. This module addresses the hardest production problem in AI architecture: maintaining factual accuracy at scale.

The fundamental challenge:
- **Small corpus (10K docs):** Retrieval is precise, context is clean, hallucination is rare
- **Large corpus (10M docs):** Retrieval returns noise, context conflicts, hallucination spikes
- **Massive corpus (100M+ docs):** Without architectural intervention, RAG becomes unreliable

---

## Part 1: Scaling RAG to Millions of Records

### Vector DB Scaling Architecture

#### Memory Math: Capacity Planning

Every vector consumes: `dimensions × bytes_per_float + metadata_overhead`

For OpenAI's text-embedding-3-large (3072 dimensions, float32):

| Scale | Raw Vectors | HNSW Overhead (M=16) | Total RAM | With 3x Replication |
|-------|-------------|---------------------|-----------|---------------------|
| 1M vectors | 12.3 GB | ~17.2 GB | 17.2 GB | 51.6 GB |
| 10M vectors | 123 GB | ~172 GB | 172 GB | 516 GB |
| 100M vectors | 1.23 TB | ~1.72 TB | 1.72 TB | 5.16 TB |
| 1B vectors | 12.3 TB | ~17.2 TB | 17.2 TB | 51.6 TB |

For text-embedding-3-small (1536 dimensions, float32):

| Scale | Raw Vectors | HNSW Overhead (M=16) | Total RAM | With 3x Replication |
|-------|-------------|---------------------|-----------|---------------------|
| 1M vectors | 6.1 GB | ~8.6 GB | 8.6 GB | 25.8 GB |
| 10M vectors | 61.4 GB | ~86 GB | 86 GB | 258 GB |
| 100M vectors | 614 GB | ~860 GB | 860 GB | 2.58 TB |
| 1B vectors | 6.14 TB | ~8.6 TB | 8.6 TB | 25.8 TB |

**Key insight:** Quantization changes everything. With scalar quantization (float32 → int8):
- 4x reduction in storage
- 10M vectors at 1536d: 86 GB → ~22 GB (fits a single machine)
- Trade-off: ~2-5% recall loss (usually acceptable with reranking)

With binary quantization (float32 → 1 bit):
- 32x reduction in storage
- 10M vectors at 1536d: 86 GB → ~3 GB
- Trade-off: ~10-15% recall loss (requires oversampling + reranking)

#### Index Selection at Scale

**HNSW (Hierarchical Navigable Small World)**
- Memory: Entire index must fit in RAM
- Query latency: 1-5ms for top-10
- Insert latency: 10-50ms (rebuilds graph connections)
- Sweet spot: Up to 10M vectors per node with sufficient RAM
- Weakness: Memory-hungry, slow initial build, no native disk support
- Use when: Latency is king, budget allows RAM, corpus < 50M vectors

**IVF (Inverted File Index)**
- Memory: Centroids in RAM, vectors on disk possible
- Query latency: 5-20ms (depends on nprobe)
- Insert latency: Fast (just assign to nearest centroid)
- Sweet spot: 1M-100M vectors with disk-backed storage
- Weakness: Recall depends heavily on nprobe tuning
- Use when: Need disk-friendly option, moderate latency acceptable

**DiskANN (Microsoft)**
- Memory: Compressed graph in RAM, full vectors on disk (SSD)
- Query latency: 3-10ms even at billion scale
- Insert latency: Moderate (graph update + disk write)
- Sweet spot: 100M-10B vectors
- Weakness: Requires NVMe SSDs, complex deployment
- Use when: Billion-scale, want HNSW-like quality without all-RAM cost

**SPANN (Space Partition Tree and Graph)**
- Memory: Partition structure in RAM, data on disk
- Query latency: 5-15ms
- Sweet spot: Similar to DiskANN, research-grade
- Use when: Evaluating alternatives to DiskANN

**Decision matrix:**
```
Budget prioritized → IVF with quantization
Latency prioritized → HNSW with enough RAM
Scale prioritized → DiskANN on NVMe
Balanced → HNSW up to 10M, DiskANN beyond
```

#### When to Shard: Warning Signs

You need sharding when:
1. **Query latency degradation:** p99 latency exceeds SLA (e.g., >50ms for retrieval)
2. **Memory pressure:** Node memory utilization >80% sustained
3. **Ingestion lag:** Write queue depth growing, fresh documents delayed >15 minutes
4. **Single-node limits:** Vector count exceeds what one node can serve at target latency
5. **Availability requirements:** Single node = single point of failure
6. **Geographic requirements:** Users in multiple regions need low-latency access

**Rule of thumb:** Shard before you need to. A planned shard migration is 10x less painful than an emergency one.

#### Sharding Strategies for RAG

**Strategy 1: By Tenant (Multi-tenant SaaS)**
```
Tenant A → Shard 1 (vectors: 2M)
Tenant B → Shard 2 (vectors: 500K)
Tenant C → Shard 3 (vectors: 8M)
```
- Advantages: Perfect isolation, simple routing, per-tenant scaling
- Disadvantages: Uneven shard sizes, many small tenants waste resources
- Solution: Small tenants share shards with namespace isolation; large tenants get dedicated shards
- Routing: Tenant ID → shard lookup table (fast, deterministic)

**Strategy 2: By Topic/Domain**
```
Query: "What is our refund policy?" → Route to Policy shard
Query: "Show me Q3 revenue" → Route to Finance shard
Query: "How do I reset my password?" → Route to IT Support shard
```
- Advantages: Smaller search space = better precision, domain-specific tuning
- Disadvantages: Requires query classifier, cross-domain queries need fan-out
- Routing: Lightweight classifier (fine-tuned small model) or keyword rules
- Critical insight: This directly reduces hallucination by limiting noise

**Strategy 3: By Time**
```
Last 30 days → Hot shard (in-memory HNSW, fast)
30-365 days → Warm shard (DiskANN, moderate)
>1 year → Cold shard (IVF on object storage, slow)
```
- Advantages: Most queries hit recent data, cost-efficient for historical
- Disadvantages: Time-spanning queries need fan-out
- Implementation: Time-based routing with fallback to older shards if hot returns insufficient results

**Strategy 4: By Document Type**
```
Policies & procedures → Shard A (high authority, strict verification)
Chat transcripts → Shard B (lower authority, lighter verification)
Code documentation → Shard C (technical, code-aware retrieval)
Email archives → Shard D (conversational, context-heavy)
```
- Advantages: Type-specific retrieval tuning, type-specific quality levels
- Disadvantages: Documents that span types need duplication or routing logic

**Hybrid sharding (recommended for enterprise):**
```
Primary: By tenant (isolation guarantee)
Secondary: Within tenant, by domain (precision boost)
Tertiary: Within domain, by time (cost optimization)
```

#### Replication for Availability

**3-replica pattern:**
```
Primary (writes) ─── Replica 1 (reads, same region)
                 └── Replica 2 (reads, different AZ)
                 └── Replica 3 (reads, different region)
```

- Writes go to primary, replicated async to replicas
- Reads served from nearest replica (latency optimization)
- If primary fails: Promote replica 1, create new replica 3
- Replication lag SLA: <5 seconds for consistency
- Consistency model: Eventual consistency for reads, strong for writes

**Read-your-writes consistency:**
- After document ingestion, route that user's queries to primary for 30s
- After 30s, replicas have caught up, resume normal routing
- Critical for: Document update → immediate query scenarios

#### Ingestion at Scale: 100K Documents/Day

Processing pipeline:
```
Documents → Chunking → Embedding → Indexing → Available for Query
   │            │           │           │              │
   │         10ms/doc    50ms/doc   5ms/vector      Ready
   │                                                   
   └── Parallel: 100 workers = 10K docs/hour = 240K docs/day capacity
```

**Architecture for concurrent read/write:**
```
┌─────────────────────────────────────────────────┐
│                    Load Balancer                  │
├─────────────────────────────────────────────────┤
│  Query Path (reads)         │  Ingest Path       │
│  ┌─────────────────┐       │  ┌──────────────┐  │
│  │ Read Replicas   │       │  │ Write Primary │  │
│  │ (serve queries) │       │  │ (accept new)  │  │
│  └─────────────────┘       │  └──────────────┘  │
│                             │        │           │
│          ←── Replication ───┘        │           │
│                                      ▼           │
│                              ┌──────────────┐    │
│                              │ Ingest Queue │    │
│                              │ (backpressure)│   │
│                              └──────────────┘    │
└─────────────────────────────────────────────────┘
```

Key patterns:
- **Backpressure:** If indexing falls behind, queue grows, producers slow down
- **Batch indexing:** Accumulate 1000 vectors, bulk insert (more efficient than one-by-one)
- **Off-peak indexing:** Heavy reindexing jobs run during low-traffic hours
- **Shadow indexing:** Build new index in parallel, swap atomically when ready

#### Hot/Warm/Cold Tiering

```
┌──────────────────────────────────────────────────────┐
│ HOT (RAM): Last 7 days, high-frequency documents     │
│ - HNSW in-memory                                      │
│ - Latency: 2-5ms                                      │
│ - Cost: $$$                                           │
│ - Capacity: 1-5M vectors                              │
├──────────────────────────────────────────────────────┤
│ WARM (SSD): Last 90 days, moderate frequency          │
│ - DiskANN on NVMe                                     │
│ - Latency: 5-15ms                                     │
│ - Cost: $$                                            │
│ - Capacity: 10-100M vectors                           │
├──────────────────────────────────────────────────────┤
│ COLD (Object Storage): Archive, rare access           │
│ - IVF with on-demand loading                          │
│ - Latency: 50-200ms                                   │
│ - Cost: $                                             │
│ - Capacity: Unlimited                                 │
└──────────────────────────────────────────────────────┘
```

Promotion/demotion logic:
- Document accessed 3+ times in 7 days → promote to HOT
- Document not accessed in 30 days → demote to WARM
- Document not accessed in 90 days → demote to COLD
- Query hits COLD → serve from COLD, async promote to WARM

---

### Retrieval Architecture at Scale

#### Two-Stage Retrieval

```
Query → Embed → ANN Search (top-100) → Cross-Encoder Rerank (top-5) → LLM
         │              │                        │
      ~20ms         ~10ms                    ~100ms
         │              │                        │
    Single model   Bi-encoder            Cross-encoder
    (cached OK)    (fast, approximate)   (slow, precise)
```

**Why two stages matter at scale:**
- ANN with 10M vectors returns "approximately relevant" top-100
- At scale, the difference between rank 1 and rank 50 is small in embedding space
- Cross-encoder compares query-document pairs jointly (much more accurate)
- Result: Top-5 after reranking is dramatically better than top-5 from ANN alone

**Reranking models:**
- Cross-encoder (ms-marco-MiniLM-L-12): Fast, moderate quality
- BGE-reranker-large: Better quality, moderate speed
- Cohere Rerank: API-based, excellent quality
- GPT-4 as reranker: Highest quality, expensive, slow (useful for verification)

#### Pre-filtering Strategies

At 10M documents, searching all vectors wastes compute. Pre-filter to reduce search space:

```python
# Instead of searching 10M vectors:
results = vector_db.search(query_embedding, top_k=100)

# Search only relevant subset (maybe 100K vectors):
results = vector_db.search(
    query_embedding, 
    top_k=100,
    filter={
        "tenant_id": "customer_123",
        "document_type": "policy",
        "created_after": "2024-01-01",
        "department": ["legal", "compliance"]
    }
)
```

**Filter types by effectiveness:**
1. **Tenant filter** (mandatory for multi-tenant): Reduces space by 100-10000x
2. **Time filter:** Recent documents usually more relevant, reduces by 2-10x
3. **Type filter:** Document category, reduces by 3-20x
4. **Access control filter:** User's permitted documents only
5. **Language filter:** If multilingual corpus

**Implementation options:**
- Pre-filter then search (Qdrant, Weaviate): Filter first, search within filtered set
- Post-filter (some Milvus modes): Search all, then filter results (wasteful at scale)
- Hybrid (Pinecone): Combines metadata index with vector index

**Critical insight:** Pre-filtering is the single biggest lever for both performance AND quality at scale. Narrower search space = more relevant results = less hallucination.

#### Parallel Retrieval (Fan-out)

When data is sharded, queries fan out:
```
Query → Router → ┌─ Shard 1 (top-20) ─┐
                 ├─ Shard 2 (top-20) ─┤── Merge → Rerank → Top-5
                 └─ Shard 3 (top-20) ─┘
```

**Merge strategies:**
- Score-based merge: Normalize scores across shards, take global top-K
- Round-robin merge: Take top-N from each shard, rerank combined
- Weighted merge: Shards have relevance weights based on query routing confidence

**Timeout handling:**
- Set per-shard timeout (e.g., 50ms)
- If shard doesn't respond, proceed with available results
- Log degraded responses for monitoring
- Circuit breaker: If shard fails 50%+, remove from fan-out temporarily

#### Query Routing

Instead of querying all shards, classify the query first:
```
Query: "What is the vacation policy?"
  → Classifier: category=HR, confidence=0.92
  → Route to: HR shard only
  → Search space: 50K instead of 10M
  → Better results, faster, cheaper
```

**Router implementation:**
- Zero-shot classifier (small model): Fast but less accurate
- Fine-tuned classifier on historical queries: More accurate, needs training data
- Embedding similarity to shard centroids: Compare query embedding to centroid of each shard
- Keyword rules + ML fallback: Fast path for obvious cases

**Fallback:** If router confidence < 0.7, fan-out to top-3 candidate shards.

#### Caching at the Retrieval Layer

```
┌─────────────────────────────────────────┐
│          Query Cache (L1)               │
│  Key: hash(query_embedding + filters)    │
│  Value: retrieved chunk IDs + scores     │
│  TTL: 5 minutes                          │
│  Hit rate: 15-30% (repeated queries)     │
├─────────────────────────────────────────┤
│      Embedding Cache (L2)               │
│  Key: hash(query_text)                   │
│  Value: query embedding vector           │
│  TTL: 1 hour                             │
│  Hit rate: 20-40%                        │
├─────────────────────────────────────────┤
│      Response Cache (L3)                │
│  Key: hash(query + top_chunks)           │
│  Value: final generated response         │
│  TTL: 10 minutes (invalidated on update)│
│  Hit rate: 5-15%                         │
└─────────────────────────────────────────┘
```

**Cache invalidation:**
- Document updated → invalidate all response caches containing that document's chunks
- Use inverted index: document_id → list of cache keys that reference it
- Time-based expiry as safety net

#### Embedding Computation at Scale

At 100K documents/day ingestion:
- Average 10 chunks per document = 1M chunks/day to embed
- At 50ms per embedding call: 50,000 seconds = 13.9 hours sequential
- Need: Batch embedding (100 texts per call) + parallel workers

**Optimization strategies:**
- Batch API calls: 100 texts per request (most APIs support this)
- Pre-compute on ingest: Never compute embeddings at query time for documents
- Cache query embeddings: Same query text → same embedding (deterministic)
- GPU inference server: Self-hosted model for high-volume (NVIDIA Triton)
- Async embedding: Embed in background, document available after embedding completes

---

### Infrastructure Patterns

#### Kubernetes Architecture for Vector DB at Scale

```yaml
# StatefulSet for vector DB (e.g., Qdrant cluster)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: vectordb
spec:
  replicas: 3
  serviceName: vectordb
  template:
    spec:
      containers:
      - name: qdrant
        resources:
          requests:
            memory: "64Gi"
            cpu: "8"
          limits:
            memory: "96Gi"
        volumeMounts:
        - name: data
          mountPath: /qdrant/storage
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 500Gi
```

**Key infrastructure decisions:**
- **StatefulSets** (not Deployments): Stable network identity, persistent storage
- **Local NVMe** preferred over network storage for DiskANN workloads
- **Anti-affinity rules:** Replicas on different nodes/AZs
- **PodDisruptionBudget:** At least 2/3 replicas available during maintenance

#### GPU Nodes for Reranking

At 1000 QPS with cross-encoder reranking:
- Each rerank: 100 query-document pairs scored
- Cross-encoder throughput on A10G: ~500 pairs/second
- Need: 1000 × 100 / 500 = 200 GPU-seconds/second = need multiple GPUs

```
Reranker Service:
  - 4x A10G GPUs (24GB each)
  - Batch incoming rerank requests (wait up to 10ms to fill batch)
  - Process batch of 64-128 pairs simultaneously
  - Throughput: ~2000 pairs/second per GPU = 8000 total
  - Handles: 80 QPS with top-100 reranking per query
  - Scale: Add GPUs linearly with QPS
```

#### Queue-Based Ingestion with Backpressure

```
Source → Kafka/SQS → Chunker → Embedding Queue → Embedder → Index Queue → Indexer
                        │                             │                        │
                    Workers: 10              Workers: 20 (batch)        Workers: 5
                    Rate: 1K/min             Rate: 50K embeddings/min   Rate: 50K/min
```

Backpressure signals:
- Embedding queue depth > 10K: Slow down chunker
- Index queue depth > 50K: Slow down embedder
- Memory pressure > 85%: Pause indexing, serve reads only
- Alert at queue depth > 100K: Scaling event needed

#### Circuit Breakers Between Retrieval and Generation

```
Retrieval → Circuit Breaker → Generation
                  │
          States: CLOSED (normal)
                  OPEN (retrieval failing, use fallback)
                  HALF-OPEN (testing recovery)
```

Fallback behaviors when retrieval is down:
- Return cached response if available
- Return "I don't have access to current information" (honest abstention)
- Route to a smaller, always-available knowledge base
- Never: Hallucinate an answer without retrieval context

---

## Part 2: Eliminating Hallucination at Scale

### Why Hallucination Gets WORSE at Scale

**1. More documents = more noise in retrieval results**
- At 10K docs: Top-5 retrieved are usually highly relevant (>0.85 similarity)
- At 10M docs: Top-5 might include tangentially relevant docs (0.65-0.75 similarity)
- These "sort-of relevant" documents are hallucination fuel — they give the LLM enough context to sound confident while being wrong

**2. Larger corpus = higher chance of conflicting information**
- Policy document v1 says "30-day return policy"
- Policy document v2 (updated) says "14-day return policy"
- Both exist in the corpus. Which one gets retrieved? Whichever is closer in embedding space to the query — not necessarily the current one.

**3. More topics = model confuses related concepts**
- "Employee benefits" and "contractor benefits" are semantically close
- At scale, retrieval may mix chunks from both
- LLM generates a confident-sounding answer that blends both (wrong for either)

**4. Stale documents = outdated information presented as truth**
- 6-hour ingestion lag means queries during that window get old answers
- Users don't know the answer is outdated — it looks authoritative

**5. Cross-tenant contamination (multi-tenant)**
- Metadata filter bug → Tenant A's query retrieves Tenant B's document
- Model incorporates it seamlessly — hallucination that's also a security breach

### The Hallucination Defense Stack

#### Layer 1: Retrieval Quality (Prevents Hallucination at Source)

**Principle: Precision > Recall.** Better to retrieve 3 highly relevant documents than 10 somewhat relevant ones.

**1. Aggressive relevance thresholds:**
```python
results = search(query, top_k=20)
# Don't just take top-5. Filter by minimum relevance:
filtered = [r for r in results if r.score > 0.75]
# If fewer than 3 pass threshold, consider abstaining
if len(filtered) < 3:
    return "I don't have enough information to answer this confidently."
```

**2. Cross-encoder reranking:**
- Bi-encoder (embedding similarity) is fast but imprecise
- Cross-encoder jointly processes query + document, catches semantic traps
- Example: Query "What is Apple's revenue?" — bi-encoder might retrieve docs about apple farming (high word overlap). Cross-encoder understands the distinction.

**3. Freshness decay scoring:**
```python
def freshness_score(doc_timestamp, half_life_days=90):
    age_days = (now() - doc_timestamp).days
    return 0.5 ** (age_days / half_life_days)

# Final score = relevance_score * freshness_score
# 6-month-old doc: 0.25x relevance penalty
# 1-year-old doc: 0.0625x relevance penalty
```

**4. Authority scoring:**
- Official documentation: authority=1.0
- Approved internal docs: authority=0.9
- Team wikis: authority=0.7
- Slack messages/emails: authority=0.4
- Draft documents: authority=0.2

Final ranking: `relevance × freshness × authority`

**5. Diversity in top-K (MMR — Maximal Marginal Relevance):**
- Problem: Top-5 might be 5 paraphrases of the same paragraph
- If that paragraph is wrong, you have 5 "sources" all confirming the wrong answer
- MMR: Balance relevance with diversity, ensure top-5 cover different aspects
- Implementation: After selecting top-1, penalize remaining candidates by similarity to already-selected

**6. Access control at retrieval (not post-hoc):**
- Filter documents by user's permissions BEFORE vector search
- Never retrieve unauthorized documents and hope to filter them out later
- Defense in depth: Namespace isolation + metadata filter + post-retrieval ACL check

#### Layer 2: Context Engineering (Prevents Hallucination in Prompt)

**1. Context deduplication:**
```python
# After retrieval, before prompting:
chunks = retrieve(query, top_k=10)
deduplicated = remove_near_duplicates(chunks, similarity_threshold=0.9)
# Typically reduces 10 chunks to 5-7 unique ones
```
Why it matters: Duplicate context gives false confidence to the model.

**2. Contradiction detection:**
```python
# Check retrieved chunks against each other
for i, chunk_a in enumerate(chunks):
    for chunk_b in chunks[i+1:]:
        if nli_model.predict(chunk_a, chunk_b) == "CONTRADICTION":
            flag_contradiction(chunk_a, chunk_b)
            # Option A: Present both with sources
            # Option B: Use more recent/authoritative one
            # Option C: Abstain and flag for human review
```

**3. Context ordering (exploit primacy bias):**
- Most relevant chunk first
- Most authoritative chunk first
- Most recent chunk first (if freshness matters)
- LLMs pay more attention to content at the beginning of the context window

**4. Context budget management:**
```
Too little context:   Model lacks information → refuses or guesses
Optimal context:      Enough to answer accurately, not so much that it gets confused
Too much context:     Model gets confused by noise, starts hallucinating

Rule of thumb: 3-7 highly relevant chunks (1500-3500 tokens of context)
Never: Stuff 20 chunks hoping "more is better" — it's not
```

**5. Source attribution markers in context:**
```
[Source: HR Policy v3.2, updated 2024-03-15, authority: official]
Employees are entitled to 20 days of paid vacation per year.

[Source: Team Wiki, updated 2023-08-01, authority: informal]  
Most people take their vacation in blocks of 5 days.
```
This helps the model attribute claims AND helps verification later.

#### Layer 3: Generation Controls (Prevents Hallucination During Generation)

**1. Grounding instructions (system prompt):**
```
You are a helpful assistant that answers questions ONLY based on the provided context.

Rules:
- If the answer is not found in the context, say "I don't have information about this."
- Never use your general knowledge. Only use the provided documents.
- For each claim you make, cite the specific source document.
- If sources conflict, present both viewpoints with citations.
- Express uncertainty when the context is ambiguous.
```

**2. Citation requirements (structured output):**
```json
{
  "answer": "Employees receive 20 days of paid vacation per year.",
  "citations": [
    {
      "claim": "20 days of paid vacation",
      "source": "HR Policy v3.2",
      "quote": "All full-time employees are entitled to 20 days..."
    }
  ],
  "confidence": 0.92,
  "caveats": []
}
```

**3. Temperature = 0 for factual tasks:**
- Temperature > 0 = sampling from probability distribution = randomness = creative = hallucination risk
- Temperature = 0 = greedy decoding = most likely token = deterministic = factual
- Exception: Use temperature 0.3-0.5 for conversational tone, but verify output

**4. Token limit as guardrail:**
- Shorter responses have less room to hallucinate
- A 50-word factual answer is less likely to contain hallucination than a 500-word one
- Set max_tokens appropriate to the query type
- Encourage concise, citation-heavy answers

#### Layer 4: Post-Generation Verification (Catches Hallucination After Generation)

**1. Claim decomposition:**
```
Generated answer: "The company was founded in 2015 in San Francisco 
and has 500 employees across 3 offices."

Decomposed claims:
- Claim 1: "The company was founded in 2015"
- Claim 2: "The company was founded in San Francisco"  
- Claim 3: "The company has 500 employees"
- Claim 4: "The company has 3 offices"
```

**2. NLI (Natural Language Inference) verification:**
For each claim, check against the retrieved context:
```
Claim: "The company was founded in 2015"
Context: "Established in 2015, the company began operations..."
NLI result: ENTAILED ✓

Claim: "The company has 500 employees"
Context: "With a team of over 450 people..."
NLI result: NEUTRAL (not directly supported) ⚠️

Claim: "The company has 3 offices"
Context: (no mention of number of offices)
NLI result: NOT ENTAILED ✗ → This is hallucination
```

**3. Citation verification:**
```python
def verify_citation(claim, cited_quote, source_document):
    # Check 1: Does the cited quote actually exist in the source?
    if cited_quote not in source_document.text:
        return "FABRICATED_CITATION"  # Model made up the quote
    
    # Check 2: Does the quote actually support the claim?
    nli_result = nli_model.predict(premise=cited_quote, hypothesis=claim)
    if nli_result != "ENTAILMENT":
        return "MISATTRIBUTED"  # Quote doesn't support claim
    
    return "VERIFIED"
```

**4. Consistency check (self-consistency):**
- Generate the answer 3 times (temperature=0.3)
- If all 3 agree: High confidence in factual correctness
- If they disagree: Flag the inconsistent claims
- Cost: 3x generation, but very effective at catching hallucination
- Use for: High-risk queries only (medical, legal, financial)

**5. Groundedness score:**
```
Groundedness = (claims_supported / total_claims) × 100%

Example:
- 5 claims in response
- 4 supported by context (ENTAILED)
- 1 not supported (NEUTRAL or CONTRADICTED)
- Groundedness = 80%

Threshold: If groundedness < 90%, regenerate or flag
```

#### Layer 5: System-Level Guarantees

**1. Confidence-driven behavior:**
```python
confidence = calculate_confidence(retrieval_scores, groundedness, nli_results)

if confidence > 0.9:
    return answer  # Serve directly
elif confidence > 0.7:
    return answer + caveat  # "Based on available information..."
elif confidence > 0.5:
    return partial_answer + "I'm not fully certain about this. Please verify."
else:
    return "I don't have enough information to answer this reliably."
```

**2. Hallucination rate monitoring:**
```
Dashboard metrics (real-time):
- Groundedness score (rolling 1-hour average)
- Citation accuracy rate
- Abstention rate (are we refusing too much? too little?)
- Confidence distribution
- Per-domain hallucination rates

Alerts:
- Groundedness drops below 92%: Warning
- Groundedness drops below 88%: Critical, investigate immediately
- Abstention rate > 25%: Check if retrieval is degraded
- Abstention rate < 3%: Check if system is too permissive
```

**3. Feedback loop:**
```
User reports inaccuracy → Log query + response + context
                       → Add to evaluation dataset
                       → Re-evaluate against current system
                       → If systemic: Fix retrieval/prompt/verification
                       → Track resolution rate
```

**4. Canary queries:**
- 50-100 known-answer questions run every 10 minutes
- Expected answers are pre-verified
- If canary accuracy drops: Alert (something changed)
- Categories: Factual recall, temporal accuracy, boundary testing (should-refuse queries)

---

### Making Verification Scale

#### The Latency-Quality Trade-off

| Verification Step | Latency Added | Quality Impact | Cost per Query |
|-------------------|---------------|----------------|----------------|
| Reranking | +100ms | -3% hallucination | $0.001 |
| Claim decomposition | +200ms | Enables verification | $0.005 |
| NLI per claim | +50ms/claim | -4% hallucination | $0.003 |
| Citation verification | +150ms | -2% hallucination | $0.004 |
| Consistency check (3x) | +2000ms | -2% hallucination | $0.03 |
| Full pipeline | +3000ms | -11% hallucination | $0.043 |

At 1000 QPS with full verification:
- 1000 claim decompositions/second: Need ~5 GPT-4 equivalent LLM instances
- 5000 NLI inferences/second: Need 4x A10G with optimized model
- Total additional infrastructure: $15-25K/month

#### Scaling Strategies

**1. Tiered verification (most impactful):**
```python
def determine_verification_tier(query, context):
    risk = classify_risk(query)  # medical, financial, legal = high
    confidence = retrieval_confidence(context)  # How relevant is context?
    
    if risk == "critical":
        return FULL_VERIFICATION  # All layers, no shortcuts
    elif risk == "high" or confidence < 0.8:
        return STANDARD_VERIFICATION  # NLI + citation check
    elif risk == "medium":
        return LIGHTWEIGHT_VERIFICATION  # Groundedness score only
    else:
        return NO_VERIFICATION  # Fast path, monitoring only
```

Distribution at typical enterprise:
- Critical: 5% of queries → Full verification (3s)
- High: 15% of queries → Standard verification (1.5s)
- Medium: 30% of queries → Lightweight verification (0.5s)
- Low: 50% of queries → No verification (0s overhead)

Weighted average latency overhead: 0.4s (instead of 3s for all)

**2. Cached verification:**
```python
cache_key = hash(context_chunks + query_embedding + response)
if cache_key in verification_cache:
    return verification_cache[cache_key]  # Skip verification entirely
```
- Same query + same retrieved documents + same response → same verification result
- Hit rate: 15-35% depending on query diversity
- TTL: Until any source document is updated

**3. Async verification:**
```
Request → Generate Response → Return to User (fast)
                                    │
                                    └─── Async: Verify in background
                                              │
                                              ├─ PASS: Log, done
                                              └─ FAIL: Flag response, notify user,
                                                       update response if UI supports it
```
- User gets fast response (500ms)
- Verification happens in background (2-3s)
- If verification fails: Show warning, offer corrected answer
- Use for: Non-critical queries where speed matters more than guaranteed accuracy

**4. Distilled verifiers:**
- Train DeBERTa-large (350M params) on NLI → 50ms per inference on GPU
- vs GPT-4 for NLI: 500ms per inference + API cost
- 10x faster, 7x cheaper, 90% as accurate
- At scale: Distilled model for all, GPT-4 as fallback for edge cases

**5. Batch verification:**
```python
# Instead of 5 separate NLI calls (one per claim):
claims = decompose(response)
# Batch all claims + context into one prompt:
results = nli_model.batch_predict(
    premises=[context] * len(claims),
    hypotheses=claims
)  # Single GPU forward pass for all claims
```

**6. Statistical sampling at very high traffic:**
```python
# At 100K QPS, verify 5% = 5000 verifications/second
if random.random() < 0.05:  # 5% sample
    verify_async(query, response, context)
    
# Statistical guarantee: With 5% sampling at 100K QPS:
# 5000 verified/second = 432K verified/day
# Can detect 1% quality drift with 99% confidence within 10 minutes
```

---

### Architecture for Zero-Hallucination at Different Scales

#### 100 QPS (Startup)

```
Query → Retrieve (top-20) → Rerank (top-5) → Generate → Verify All → Respond
                                                              │
                                                   Full claim decomposition
                                                   NLI on every claim
                                                   Citation verification
```

- Infrastructure: 1 vector DB node, 1 GPU for reranking/NLI, LLM API
- Latency: 3-5 seconds (acceptable for enterprise internal tools)
- Cost: ~$0.05/response for verification
- Hallucination rate: <1.5%
- Monthly cost: ~$15K total

#### 1,000 QPS (Growth)

```
Query → Risk Classify → Route:
  High-risk (20%):  Full verification path (3s)
  Standard (80%):   Rerank + groundedness score only (1.5s)
```

- Infrastructure: 3-node vector DB cluster, 4x GPU for reranking/NLI, LLM API
- Latency: 1.5-3s average
- Cost: ~$0.02/response average
- Hallucination rate: <2%
- Monthly cost: ~$80K total

#### 10,000 QPS (Scale)

```
Query → Cache Check → [hit: return cached] / [miss: continue]
      → Risk Classify → Route:
          Critical (5%):   Full verification (3s)
          High (15%):      Standard verification (1.5s)  
          Medium (30%):    Lightweight (async verify) (0.8s)
          Low (50%):       No verification (0.5s)
      → Statistical monitoring on 5% sample of all responses
```

- Infrastructure: Multi-shard vector DB, 16x GPU cluster, multiple LLM endpoints
- Latency: 800ms-2s average
- Cost: ~$0.005/response average
- Hallucination rate: <2.5% (with 5% sampling detection)
- Monthly cost: ~$350K total

#### 100,000 QPS (Massive Scale)

```
Query → Response Cache (40% hit) → [hit: return]
      → Embedding Cache → Retrieval (sharded, routed)
      → Generation Cache (15% hit) → [hit: return + async verify]
      → Generate → Risk-based verification
      → Background: 2% continuous sampling with statistical alerting
      → Circuit breaker: If quality drops, route to safer slow path
```

- Infrastructure: Cell-based architecture, dedicated GPU verification cluster
- Latency: 500ms (cached) to 2s (full path)
- Cost: ~$0.002/response average
- Hallucination rate: <3% (monitored, circuit-breaker enforced)
- Monthly cost: ~$2M total

---

### Hallucination Metrics to Track

| Metric | Target | How to Measure | Frequency |
|--------|--------|----------------|-----------|
| Groundedness rate | >95% | NLI on sampled responses | Continuous |
| Citation accuracy | >90% | Automated citation verification | Continuous |
| Abstention recall | >80% | Should-refuse queries test set | Hourly canary |
| Hallucination rate | <3% | Human evaluation on sample | Weekly batch |
| False confidence rate | <2% | High-confidence + wrong answers | Weekly batch |
| User-reported inaccuracy | <1% | Feedback thumbs-down for accuracy | Daily rollup |
| Retrieval precision@5 | >70% | Relevance judgments on top-5 | Daily sample |
| Stale document rate | <5% | Documents past freshness SLA | Continuous |
| Cross-tenant leakage | 0% | Audit log analysis | Continuous |

### The Hallucination Budget Framework

Modeled after SRE error budgets:

```
Monthly hallucination budget: 2.0%

Current month: 
  Week 1: 1.8% → Budget remaining: healthy
  Week 2: 2.3% → Budget exceeded, alert triggered
  
Actions when budget exceeded:
  1. Freeze model/prompt changes
  2. Increase verification coverage (from 20% to 50%)
  3. Tighten confidence thresholds
  4. Root cause analysis on recent hallucinations
  5. Regression test before resuming changes

Actions when well under budget:
  1. Can experiment with faster paths
  2. Can try lower-cost models
  3. Can reduce verification sampling rate
  4. Can relax confidence thresholds slightly
```

**Budget allocation by domain:**
```
Medical/Legal queries:  0.5% budget (very strict)
Financial queries:      1.0% budget
General knowledge:      3.0% budget
Casual/conversational:  5.0% budget (relaxed)
```

---

## Part 3: Architecture Patterns for Quality at Scale

### Pattern 1: Tiered Quality Architecture

```
                    ┌─────────────────────────┐
                    │     Query Classifier     │
                    │  (risk level + domain)   │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                     │
            ▼                    ▼                     ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────────┐
    │   Fast Path   │   │ Standard Path │   │    Safe Path      │
    │               │   │               │   │                   │
    │ Cache lookup  │   │ Full RAG      │   │ Full RAG          │
    │ No verification│  │ + Reranking   │   │ + Full verification│
    │ 200ms         │   │ + Groundedness│   │ + Consistency check│
    │               │   │ 1.5s          │   │ + Human review     │
    │ Low risk only │   │ Medium risk   │   │ 5-30s             │
    └───────────────┘   └───────────────┘   │ Critical risk     │
                                             └───────────────────┘
```

**Risk classification signals:**
- Query contains medical/legal/financial terms → High risk
- User is in regulated industry → Higher risk
- Query asks for specific numbers/dates → Higher risk (easy to verify, important to get right)
- Query is conversational/general → Lower risk
- Query has been asked before with verified answer → Cache hit, low risk

### Pattern 2: Read-Your-Writes Consistency for RAG

Problem: Document updated at T=0, but cached/indexed version persists until T=X.

```
Document Update Event
    │
    ├──→ Invalidate response cache (immediate)
    │
    ├──→ Re-embed document chunks (async, <5min)
    │
    ├──→ Update vector index (async, <5min)
    │
    └──→ During transition window:
         Route queries about this document to primary (fresh data)
         Flag responses that might reference stale version
```

Implementation:
```python
# CDC (Change Data Capture) pipeline
def on_document_update(doc_id, new_content):
    # 1. Immediate: Invalidate caches
    cache.invalidate_by_document(doc_id)
    
    # 2. Fast: Mark old vectors as stale
    vector_db.update_metadata(doc_id, {"stale": True, "stale_since": now()})
    
    # 3. Async: Re-process document
    queue.enqueue("reindex", doc_id, new_content)
    
    # 4. Until reindex complete: Queries matching this doc get caveat
    # "Note: This information may have been recently updated. 
    #  Please verify with the latest version."
```

### Pattern 3: Bloom Filter for "Known Unknowns"

```
┌─────────────────────────────────────────────────────────┐
│                  Query Processing                         │
│                                                          │
│  Query → Topic Extraction → Bloom Filter Check           │
│                                    │                     │
│                          ┌─────────┴──────────┐          │
│                          │                    │          │
│                     IN SCOPE            OUT OF SCOPE     │
│                     (probably)           (definitely)    │
│                          │                    │          │
│                     Full RAG          Fast abstention    │
│                     pipeline          "I don't have      │
│                                        information       │
│                                        about X"          │
└─────────────────────────────────────────────────────────┘
```

- Bloom filter: O(1) lookup, no false negatives
- If bloom filter says "not in corpus" → Definitely not in corpus → Fast abstention
- If bloom filter says "might be in corpus" → Proceed with retrieval
- Saves: Retrieval cost (compute + latency) + prevents hallucination on out-of-scope
- Update: Rebuild bloom filter on ingestion (cheap, fast)

### Pattern 4: Evidence Strength Scoring

```python
def score_evidence_strength(claim, source_chunk):
    """Score how strongly a source supports a claim."""
    
    nli_result = nli_model.predict(
        premise=source_chunk, 
        hypothesis=claim
    )
    
    if nli_result == "ENTAILMENT":
        # Check if it's a direct statement or inference
        if exact_match(claim, source_chunk):
            return 1.0  # Direct quote
        elif paraphrase_match(claim, source_chunk):
            return 0.9  # Clear paraphrase
        else:
            return 0.7  # Logically entailed but not directly stated
    
    elif nli_result == "NEUTRAL":
        return 0.3  # Tangentially related, not direct evidence
    
    elif nli_result == "CONTRADICTION":
        return -1.0  # Source actively contradicts this claim

# Generation rule: Only use evidence with strength > 0.7
# If best evidence is 0.3-0.7: Add caveat "This is implied but not directly stated"
# If best evidence is < 0.3: Abstain
```

### Pattern 5: Contradiction-Aware Generation

```python
def handle_contradictions(query, retrieved_chunks):
    # Step 1: Detect contradictions among retrieved chunks
    contradictions = []
    for i, chunk_a in enumerate(retrieved_chunks):
        for j, chunk_b in enumerate(retrieved_chunks[i+1:], i+1):
            if nli_model.predict(chunk_a.text, chunk_b.text) == "CONTRADICTION":
                contradictions.append((chunk_a, chunk_b))
    
    if not contradictions:
        return generate_normal(query, retrieved_chunks)
    
    # Step 2: Determine which source to trust
    for chunk_a, chunk_b in contradictions:
        if chunk_a.freshness > chunk_b.freshness:
            winner, loser = chunk_a, chunk_b
        elif chunk_a.authority > chunk_b.authority:
            winner, loser = chunk_a, chunk_b
        else:
            # Can't determine winner — present both
            return generate_with_both_viewpoints(query, chunk_a, chunk_b)
    
    # Step 3: Generate with winner, acknowledge contradiction
    return generate_with_caveat(
        query, winner,
        caveat=f"Note: An older source ({loser.source}) states differently. "
               f"This answer is based on the most recent version ({winner.source})."
    )
```

---

## Part 4: Production Playbook

### Step-by-Step: Scaling from 1K to 10M Documents

#### Phase 1: 1K-50K Documents (Single Node)

**Infrastructure:**
- Single Qdrant/pgvector instance (8-16 GB RAM)
- HNSW index fits entirely in RAM
- Single API for embedding (OpenAI / Cohere)
- Application server handles retrieval + generation

**Quality measures:**
- Full claim verification on every response (acceptable latency at low QPS)
- GPT-4 as NLI judge (expensive but low volume)
- Manual review of 100% of thumbs-down feedback
- Baseline hallucination rate with evaluation dataset

**What to measure:**
- Retrieval precision@5 (weekly evaluation, 100 queries)
- Groundedness rate (every response)
- User satisfaction (thumbs up/down)
- Latency distribution

**Expected performance:**
- Latency: 2-4 seconds end-to-end
- Hallucination rate: 2-5% (establish baseline)
- Monthly cost: $2-5K

#### Phase 2: 50K-500K Documents (Optimize)

**What changes:**
- Retrieval precision starts to degrade (more noise in top-5)
- Some queries return tangentially relevant results
- First instances of contradicting documents appear

**Actions:**
1. Add cross-encoder reranking (biggest single quality improvement)
2. Implement freshness decay scoring (prevents stale answer hallucination)
3. Add authority-based ranking (official > informal)
4. Start caching common query-response pairs
5. Implement basic query routing (if multiple domains exist)

**Infrastructure additions:**
- Dedicated reranker service (CPU or single GPU)
- Redis for response/embedding caching
- Monitoring dashboard (groundedness trend)

**Expected improvement:**
- Hallucination rate: 2-5% → 1.5-3% (reranking alone gives 30-40% reduction)
- Latency: +100-200ms from reranking (still under 4s total)

#### Phase 3: 500K-5M Documents (Scale Out)

**What changes:**
- Single node approaches memory limits
- Query latency increases (larger index)
- Ingestion starts competing with query serving
- Cross-domain confusion increases

**Actions:**
1. Shard by domain/topic (reduces per-shard search space)
2. Implement query routing (classifier routes to relevant shard)
3. Deploy tiered verification (full for high-risk, lightweight for rest)
4. Add hallucination monitoring per shard (identify problem domains)
5. Separate read path from write path (read replicas)
6. Deploy dedicated reranker service with GPU

**Infrastructure:**
- 3-5 node vector DB cluster (sharded)
- 2x GPU for reranking service
- Kafka for ingestion pipeline with backpressure
- Separate monitoring service

**Expected performance:**
- Latency: 1.5-3s (faster per-shard searches despite more infrastructure)
- Hallucination rate: 1.5-2.5%
- Monthly cost: $20-50K

#### Phase 4: 5M-50M Documents (Enterprise)

**What changes:**
- Multi-region requirements (global users)
- Strict SLAs (99.9% availability, <2s p99 latency)
- Regulatory compliance requirements
- Scale demands async/batch verification
- Need distilled models (can't afford GPT-4 for all verification)

**Actions:**
1. Multi-region replication (read from nearest)
2. Hot/warm/cold storage tiers
3. Train/deploy distilled NLI verifier on GPU (DeBERTa-large fine-tuned)
4. Statistical quality monitoring (sample verification, alert on drift)
5. Async verification pipeline (verify in background, retract if failed)
6. Contradiction detection across sources (pre-generation check)
7. Implement hallucination budget framework
8. Response cache with TTL tied to source document freshness

**Infrastructure:**
- Multi-region vector DB deployment (3+ regions)
- 8-16x GPU cluster for reranking + NLI verification
- Dedicated monitoring and evaluation service
- Human review queue for critical queries

**Expected performance:**
- Latency: 800ms-2s (heavy caching, regional proximity)
- Hallucination rate: <2% (monitored, budgeted)
- Monthly cost: $100-300K

#### Phase 5: 50M+ Documents (Massive Scale)

**What changes:**
- Cell-based architecture needed (blast radius control)
- Can't verify everything — statistical guarantees required
- Need automated quality response (circuit breakers)
- Caching becomes primary serving path

**Actions:**
1. Cell-based architecture (independent quality guarantees per cell)
2. Dedicated verification GPU cluster (separate from serving)
3. Response caching with verification pre-computation
4. Real-time hallucination dashboard per domain/cell
5. Automated quality degradation response:
   - Hallucination rate > 3% in a cell → Route traffic to slower but safer path
   - Hallucination rate > 5% → Circuit break, serve cached only, page on-call
6. Continuous evaluation on 2-5% of traffic
7. Automated root cause detection (which shard/domain is degrading?)

**Infrastructure:**
- Cell-based deployment (10-50 independent cells)
- Dedicated GPU verification cluster (32+ GPUs)
- Real-time quality monitoring pipeline (Flink/Spark Streaming)
- Automated incident response system
- Human evaluation team for weekly calibration

**Expected performance:**
- Latency: 500ms (cached, 40%+ hit rate) to 2s (full path)
- Hallucination rate: <3% (statistically monitored, circuit-breaker enforced)
- Monthly cost: $1-3M

---

## Summary: The Quality-at-Scale Hierarchy

```
Level 1: Retrieval Quality       → Prevents 40% of hallucinations (cheapest)
Level 2: Context Engineering     → Prevents 20% of hallucinations
Level 3: Generation Controls     → Prevents 15% of hallucinations
Level 4: Post-Generation Verify  → Catches 20% of remaining hallucinations
Level 5: System Guarantees       → Ensures sustained quality over time

Combined: 95%+ reduction in hallucination vs naive RAG at scale
```

The key insight: Each level is cheaper and faster than the next. Invest heavily in Level 1 (retrieval quality) before reaching for expensive verification. A system with excellent retrieval and no verification will outperform one with poor retrieval and full verification — and cost less.

---

## Key Takeaways

1. **Hallucination is a retrieval problem first.** Fix retrieval precision before adding expensive verification.
2. **Scale and quality are inversely correlated by default.** You must actively engineer against quality degradation as corpus grows.
3. **Tiered verification is the scaling key.** Not all queries need the same level of assurance.
4. **The hallucination budget framework** brings SRE discipline to AI quality.
5. **Pre-filtering is the highest-leverage intervention.** Narrower search space = better results = less hallucination = lower cost.
6. **Measure everything.** You can't improve what you can't measure. Instrument from day one.
7. **Plan for contradictions.** At scale, your corpus WILL contain conflicting information. Handle it explicitly.
8. **Cache aggressively.** The fastest and most accurate response is one that's already been verified.
9. **Defense in depth.** No single layer prevents all hallucination. Stack your defenses.
10. **The cost of NOT preventing hallucination exceeds the cost of prevention** — always, in production.
