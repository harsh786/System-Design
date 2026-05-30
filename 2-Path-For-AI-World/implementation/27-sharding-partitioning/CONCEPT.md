# Sharding & Partitioning for Vector Databases

## 1. Partitioning Strategies

Partitioning = logical separation of data within one deployment. Reduces search scope, enables isolation.

### 1.1 Tenant Partitioning
- **What**: Each customer's vectors in separate logical partition
- **Why**: Data isolation, per-tenant SLAs, deletion compliance (GDPR right-to-erasure = drop partition)
- **Implementation**: Collection per tenant OR metadata field `tenant_id` with mandatory filter
- **Trade-off**: Too many small tenants → thousands of tiny indexes with poor HNSW graph quality

### 1.2 Domain Partitioning
- **What**: Separate partitions by knowledge domain (legal, medical, engineering, HR)
- **Why**: Different embedding models per domain, domain-specific chunking, targeted reindexing
- **Implementation**: Classifier routes docs to domain partition at ingestion; queries route based on intent
- **Trade-off**: Cross-domain queries need fanout; misclassification → recall loss

### 1.3 Time Partitioning
- **What**: Partition by time window (daily, weekly, monthly)
- **Why**: Enables retention policies (drop old partitions), recency-biased search, predictable growth
- **Implementation**: Partition key = `YYYY-MM` or `YYYY-WW`; queries specify time range
- **Trade-off**: Time-agnostic queries need fanout across all partitions

### 1.4 Geography Partitioning
- **What**: Data partitioned by region (US, EU, APAC)
- **Why**: Data residency compliance (GDPR, sovereignty), latency optimization
- **Implementation**: Regional deployments with geo-routing at API gateway
- **Trade-off**: Cross-region queries add latency; user mobility creates edge cases

### 1.5 Risk/Sensitivity Partitioning
- **What**: Separate PII/confidential vectors from general content
- **Why**: Different access controls, encryption keys, audit requirements
- **Implementation**: Sensitivity classifier at ingestion → route to appropriate partition with different security posture
- **Trade-off**: Queries spanning sensitivity levels need careful access control merging

### 1.6 Embedding Version Partitioning
- **What**: Separate partitions per embedding model version
- **Why**: Can't mix embeddings from different models (cosine similarity meaningless across versions)
- **Implementation**: Partition key includes model version; blue-green reindexing creates new partition
- **Trade-off**: During migration, queries may need to hit both old and new partitions

### 1.7 Modality Partitioning
- **What**: Separate text embeddings from image embeddings from audio embeddings
- **Why**: Different dimensionality, different distance metrics, different index parameters
- **Implementation**: Modality field routes to appropriate collection with tuned parameters
- **Trade-off**: Multi-modal queries (find images matching this text) need cross-partition retrieval with score normalization

### 1.8 Hot/Cold Partitioning
- **What**: Frequently accessed vectors on fast storage (RAM/SSD), rarely accessed on cold storage (disk/object store)
- **Why**: Cost optimization — 80% of queries hit 20% of data
- **Implementation**: Access frequency tracking → migrate cold vectors to cheaper tier; warm on demand
- **Trade-off**: Cold queries have 10-100x latency; migration window causes brief inconsistency

---

## 2. Sharding Strategies

Sharding = physical distribution of data across nodes. Enables horizontal scaling beyond single-node limits.

### 2.1 Hash-Based Sharding
- **How**: `shard_id = hash(doc_id) % num_shards`
- **Pros**: Even distribution, simple routing, no hotspots for uniform access
- **Cons**: Resharding requires full data movement; no locality — every query fans out to all shards
- **Best for**: Uniform workloads where all queries are by doc_id lookup

### 2.2 Tenant-Based Sharding
- **How**: Each tenant (or tenant group) assigned to specific shard(s)
- **Pros**: Tenant isolation, no cross-tenant interference, simple routing (tenant→shard map)
- **Cons**: Uneven tenant sizes → hot shards; small tenants waste capacity
- **Best for**: B2B SaaS with clear tenant boundaries and varying sizes
- **Optimization**: Bin-packing small tenants onto shared shards; large tenants get dedicated shards

### 2.3 Range/Time-Based Sharding
- **How**: Shard by time range (shard_1 = Jan-Mar, shard_2 = Apr-Jun)
- **Pros**: Natural retention (drop old shards), append-only writes to latest shard, recency queries hit one shard
- **Cons**: Latest shard is always hot for writes; historical queries need fanout
- **Best for**: Log-like data, news, event streams, chat history

### 2.4 Semantic/Domain-Based Sharding
- **How**: Cluster vectors by semantic similarity; each cluster on its own shard
- **Pros**: Queries often hit only 1-2 shards (semantically similar queries route to same shard), better recall per shard
- **Cons**: Classification errors → wrong shard → recall loss; new domains need rebalancing
- **Best for**: Multi-domain knowledge bases where queries have clear domain intent
- **Implementation**: Train lightweight classifier on domain labels; route at query time

### 2.5 Hybrid Sharding
- **How**: Combine strategies — e.g., tenant sharding at top level, time sharding within each tenant
- **Pros**: Balances all concerns; practical for real systems
- **Cons**: Complex routing logic; more failure modes
- **Example**: `shard = tenant_shard_map[tenant_id][time_bucket(timestamp)]`

---

## 3. Query Routing Patterns

### 3.1 Single-Shard Lookup
- **When**: Query metadata deterministically identifies one shard (tenant_id, domain, time range)
- **Flow**: Parse query → extract routing key → route to single shard → return results
- **Latency**: Lowest (one network hop)
- **Recall**: Highest (all relevant data on that shard)
- **Example**: "Find similar docs for tenant_123" → route to tenant_123's shard

### 3.2 Fanout (Scatter-Gather)
- **When**: Cannot determine which shard has relevant vectors; must search all
- **Flow**: Parse query → broadcast to all N shards in parallel → each returns local top-k → merge → global top-k
- **Latency**: P99 of slowest shard (tail latency problem)
- **Recall**: Can lose recall if local top-k < global top-k (a vector ranked #11 locally might be #3 globally)
- **Mitigation**: Request `k * oversampling_factor` from each shard (typically 2-3x)
- **Example**: Semantic search with no metadata filters across hash-sharded data

### 3.3 Two-Stage Routing
- **When**: Can narrow down to subset of shards before vector search
- **Flow**: Stage 1: Lightweight classifier/router determines relevant shards (2-3 of N) → Stage 2: Vector search only on those shards
- **Latency**: Slightly higher than single-shard (classifier overhead) but much lower than full fanout
- **Recall**: Good if classifier is accurate; catastrophic if it misroutes
- **Example**: Query "HIPAA compliance for AWS" → classifier says [legal_shard, cloud_shard] → search both

### 3.4 Hierarchical Retrieval
- **When**: Large-scale systems where even fanout is too expensive
- **Flow**: Level 1: Coarse search on summary/centroid index (one per shard) → identifies top shards → Level 2: Fine search on selected shards only
- **Latency**: Two sequential searches but total work is reduced
- **Recall**: Depends on quality of coarse index; centroid representation matters
- **Example**: 1000 shards, coarse index selects top 10, then fine search on those 10

### 3.5 Federated Retrieval
- **When**: Need to combine results from heterogeneous sources
- **Flow**: Query → parallel to [vector DB, keyword search, SQL DB, knowledge graph] → normalize scores → reciprocal rank fusion → return merged results
- **Latency**: Slowest source determines latency
- **Recall**: Highest (complementary retrieval methods)
- **Example**: RAG system combining dense retrieval + BM25 + entity lookup + SQL facts

---

## 4. Sharding Risks

### 4.1 Hot Shards
- **Problem**: One shard receives disproportionate traffic (popular tenant, trending topic)
- **Impact**: That shard's latency degrades; affects all tenants on it
- **Detection**: Per-shard QPS monitoring, latency percentiles
- **Mitigation**: Read replicas for hot shards; split hot shard; rate limiting per tenant

### 4.2 Fanout Latency (Tail Latency Amplification)
- **Problem**: With N shards, P99 latency = worst of N independent P99s
- **Impact**: If single shard P99 = 50ms, with 20 shards: effective P99 ≈ 100-150ms
- **Formula**: P(all < t) = P(one < t)^N → need much tighter per-shard SLO
- **Mitigation**: Hedged requests, reduce shard count, better routing to avoid fanout

### 4.3 Local Top-K Recall Loss
- **Problem**: Each shard returns its local top-k; globally relevant results may be ranked below k on their shard
- **Impact**: Recall degrades as shards increase (for fanout queries)
- **Example**: True global top-10 might be spread as: shard_1 has 3, shard_2 has 4, shard_3 has 3. If each returns top-5, you get all 10. But if true top-10 is concentrated 7 on shard_1, requesting top-5 per shard loses 2.
- **Mitigation**: Over-request (each shard returns 3*k), smart routing to reduce fanout

### 4.4 Slow Metadata Filters Cross-Shard
- **Problem**: Post-filter after vector search can eliminate most results; pre-filter narrows the index
- **Impact**: With sharding, metadata indexes must be co-located; cross-shard filters need coordination
- **Mitigation**: Include filter fields in shard routing decision; co-locate metadata with vectors

### 4.5 Rebalancing Recall Issues
- **Problem**: Moving vectors between shards during rebalancing can temporarily split related vectors
- **Impact**: During rebalancing, recall may drop as semantically similar vectors are on different shards
- **Mitigation**: Atomic shard swaps (build new shard, switch routing); avoid live migration

### 4.6 Replica Cost Explosion
- **Problem**: Each shard needs N replicas for HA; total nodes = shards × replicas
- **Impact**: 20 shards × 3 replicas = 60 nodes; cost scales linearly
- **Mitigation**: Tiered replication (hot shards: 3 replicas, cold shards: 1 replica + backup)

### 4.7 Cross-Shard Consistency
- **Problem**: Updates to a document may need to update vectors on multiple shards (if duplicated)
- **Impact**: Stale vectors on some shards; inconsistent results depending on which shard is hit
- **Mitigation**: Single-writer per document; eventual consistency with version tracking

### 4.8 Backup and Restore Complexity
- **Problem**: Consistent backup across N shards requires coordination
- **Impact**: Point-in-time recovery is hard; individual shard restore may create inconsistency
- **Mitigation**: Snapshot coordination service; per-shard incremental backups with LSN tracking

---

## 5. Multi-Tenant Vector Index Design

### Pattern 1: Shared Index + Mandatory Tenant Filter
- **How**: All tenants in one index; every query includes `WHERE tenant_id = X`
- **Capacity**: Up to ~100 tenants or ~10M total vectors
- **Pros**: Simple ops, good resource utilization for small tenants
- **Cons**: Noisy neighbor risk; filter overhead; no tenant isolation; one bad tenant can degrade all
- **HNSW impact**: Graph connects vectors across tenants; filter is post-retrieval → over-fetch needed
- **Rule**: Must set `ef_search` higher (2-3x) to compensate for post-filtering

### Pattern 2: Namespace Per Tenant
- **How**: Single physical index with logical namespace isolation (Pinecone namespaces, Qdrant collections)
- **Capacity**: Up to ~1000 tenants
- **Pros**: Better isolation than shared; per-tenant metrics possible; independent deletion
- **Cons**: Still shared infrastructure; namespace overhead; may share HNSW graph
- **Best for**: Medium tenants (10K-1M vectors each)

### Pattern 3: Index Per Tenant
- **How**: Dedicated vector index (collection) per tenant
- **Capacity**: Up to ~100 tenants (operational overhead limit)
- **Pros**: Full isolation; independent tuning (dimension, metric, HNSW params); clean deletion
- **Cons**: Resource waste for small tenants; operational burden; cold-start for new tenants
- **Best for**: Large tenants (1M+ vectors) or tenants with different embedding models

### Pattern 4: Cluster/Cell Per Tenant Group
- **How**: Group similar-sized tenants into cells (dedicated cluster per cell)
- **Capacity**: Unlimited tenants (bin-packing into cells)
- **Pros**: Blast radius limited to cell; independent scaling per cell; cost allocation
- **Cons**: Complex placement logic; cell rebalancing needed
- **Best for**: SaaS at scale with mixed tenant sizes

### Pattern 5: Dedicated Deployment
- **How**: Entire vector DB deployment per tenant
- **Capacity**: Enterprise/whale tenants
- **Pros**: Complete isolation; custom SLAs; independent upgrades; compliance
- **Cons**: Highest cost; operational overhead; can't share learnings across tenants
- **Best for**: Enterprise customers paying premium for isolation

### Tenant-to-Pattern Assignment Logic
```
if tenant.vector_count < 10_000:
    assign → Pattern 1 (shared)
elif tenant.vector_count < 1_000_000:
    assign → Pattern 2 (namespace)
elif tenant.vector_count < 10_000_000:
    assign → Pattern 3 (dedicated index)
elif tenant.is_enterprise and tenant.pays_premium:
    assign → Pattern 5 (dedicated deployment)
else:
    assign → Pattern 4 (cell-based)
```

---

## 6. Vector Index Lifecycle

### Blue-Green Reindexing
1. **Trigger**: New embedding model, dimension change, parameter tuning, data migration
2. **Process**:
   - Create new index (green) alongside existing (blue)
   - Re-embed all documents with new model → write to green
   - Run shadow traffic: query both, compare recall
   - When green recall ≥ blue recall: switch routing to green
   - Keep blue alive for rollback window (24-72h)
   - Decommission blue
3. **Critical**: Never mix embeddings from different models in same index
4. **Duration**: For 10M vectors at 1000 embeddings/sec = ~2.8 hours for re-embedding

### Version Metadata Tracking
- Every vector stores: `embedding_model_version`, `chunk_strategy_version`, `indexed_at`
- Enables: partial reindexing (only re-embed vectors from old model version)
- Query-time: can filter to only search vectors from current model version during migration

---

## 7. HNSW at Scale

### Memory Requirements
- Per vector: `dimension × 4 bytes (float32)` + `M × 2 × 8 bytes (graph edges)` + metadata overhead
- Example: 1536-dim, M=16: ~6KB per vector raw + ~256B graph = ~6.3KB
- 10M vectors ≈ 63GB RAM (just for index, excluding overhead)
- **Rule**: HNSW requires all vectors in RAM for optimal performance

### Graph Per Shard
- Each shard maintains independent HNSW graph
- Smaller graphs = faster construction, lower memory, faster search
- But: splitting semantically similar vectors across shards hurts graph connectivity
- **Optimal shard size**: 1M-10M vectors per shard for HNSW

### ef_search Tuning
- Higher ef_search = better recall, higher latency
- Per-shard ef_search should account for post-filtering: `ef_search = target_k × (1 / selectivity) × 1.5`
- Example: want top-10, filter passes 10% of vectors: `ef_search = 10 × 10 × 1.5 = 150`
- Production ranges: ef_search 64-512 depending on recall requirements

### Key Parameters
| Parameter | Effect | Typical Range |
|-----------|--------|---------------|
| M | Graph connectivity (edges per node) | 16-64 |
| ef_construction | Build quality | 128-512 |
| ef_search | Search quality vs speed | 64-512 |

---

## 8. IVF at Scale

### nlist (Number of Clusters)
- Rule of thumb: `nlist = sqrt(N)` where N = total vectors
- 1M vectors → nlist ≈ 1000
- 100M vectors → nlist ≈ 10000
- Too few clusters → each cluster too large → slow search
- Too many clusters → poor cluster quality → recall loss

### nprobe (Clusters to Search)
- Higher nprobe = better recall, higher latency
- Typical: nprobe = 5-20% of nlist for 95%+ recall
- `nprobe = 1` is fastest but lowest recall (~50-70%)
- `nprobe = nlist` is exhaustive (100% recall, defeats purpose)

### Sharding Interaction
- Each shard has independent IVF clusters
- Cluster centroids may drift differently per shard after updates
- Periodic re-clustering needed (unlike HNSW which is more stable)

---

## 9. Quantization

### Product Quantization (PQ)
- Splits vector into M sub-vectors, quantizes each to 8-bit code
- Memory reduction: 1536-dim float32 (6KB) → PQ with 96 sub-quantizers (96 bytes) = 64x compression
- Recall trade-off: typically 5-15% recall loss depending on data distribution
- Best for: disk-based indexes where memory is constraint

### Scalar Quantization (SQ8)
- Float32 → Int8 per dimension
- Memory reduction: 4x
- Recall trade-off: 1-3% recall loss (much less than PQ)
- Best for: RAM-constrained but need high recall

### Binary Quantization
- Float32 → 1 bit per dimension
- Memory reduction: 32x
- Recall trade-off: 10-30% loss; only works well for high-dimensional embeddings (1536+)
- Best for: First-stage candidate retrieval with re-ranking

### Rescoring Strategy
- Quantized search → get top-100 candidates → rescore with full-precision vectors → return top-10
- Full vectors stored on SSD; only loaded for top candidates
- Recovers most recall loss from quantization

---

## 10. Ingestion Scaling

### Scalable Pipeline Design
```
Sources → Change Detection → Queue → Parse/Chunk → Embed → Index Write → Verify
                                  ↓ (failures)
                            Dead Letter Queue → Alert → Manual Review
```

### Key Principles
1. **Idempotency**: Every operation keyed by `(source_id, content_hash)` — re-processing same content is a no-op
2. **Ordering**: Per-document ordering guaranteed; cross-document ordering not required
3. **Batching**: Embedding calls batched (32-128 items); index writes batched (100-1000 items)
4. **Backpressure**: If index write is slow, slow down embedding; if embedding is slow, slow down parsing
5. **Exactly-once semantics**: Use transactional outbox pattern or idempotency keys

### Queue Design
- Partition queue by tenant (tenant isolation in pipeline too)
- Priority lanes: urgent (user upload) vs batch (scheduled crawl)
- Retry with exponential backoff: 1s, 5s, 30s, 5min, 30min, then DLQ

### Batching Strategy
- Embedding API: batch size 32-128 (API limit dependent)
- Index writes: batch 100-1000 vectors per upsert call
- Flush on: batch full OR timeout (5s) — whichever comes first

---

## 11. Metadata Partitioning and Filtering

### Important Metadata Fields
| Field | Purpose | Filter Type |
|-------|---------|-------------|
| tenant_id | Isolation | Exact match (mandatory) |
| source_type | Content origin | Exact match |
| created_at | Recency | Range |
| domain | Knowledge area | Exact match |
| access_level | Security | Set membership |
| language | Locale | Exact match |
| doc_id | Grouping | Exact match |
| chunk_index | Ordering | Range |
| embedding_model | Version | Exact match |

### Filter Design Rules
1. **Pre-filter vs Post-filter**: Pre-filter (narrow index before search) if filter eliminates >50% of data
2. **Mandatory filters**: tenant_id should ALWAYS be pre-filtered (never search across tenants)
3. **Index the filter fields**: Metadata fields used in filters need their own indexes (B-tree, bitmap)
4. **Compound filters**: `tenant_id + domain + time_range` as common compound filter — index accordingly
5. **Avoid high-cardinality post-filters**: Filtering by rare values after vector search wastes compute
6. **Filter selectivity estimation**: Track filter cardinalities to choose pre vs post at query time

---

## 12. Design Decision Guide

| # | Problem | Solution |
|---|---------|----------|
| 1 | Single index too large for RAM | Shard by tenant or domain; reduce per-shard size to fit memory |
| 2 | Need data isolation between customers | Tenant-based partitioning (shared→namespace→dedicated based on size) |
| 3 | Queries always within one time window | Time-based sharding; latest shard on fast storage |
| 4 | Cross-domain queries have poor recall | Domain-based sharding + two-stage routing with classifier |
| 5 | P99 latency too high | Reduce fanout via better routing; add read replicas for hot shards |
| 6 | Need to change embedding model | Blue-green reindexing with embedding version partitioning |
| 7 | GDPR deletion requests | Tenant partitioning → drop entire partition; or maintain deletion log |
| 8 | Mixed workload (real-time + batch) | Hot/cold partitioning; separate ingestion from serving path |
| 9 | Cost too high for full HNSW in RAM | Quantization (SQ8 for 4x, PQ for 64x) + disk-based index with rescoring |
| 10 | Ingestion falling behind | Horizontal scale workers; batch embeddings; async index writes with queue |
