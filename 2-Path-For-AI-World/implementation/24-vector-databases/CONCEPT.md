# Vector Databases - Deep Concepts

## 1. Vector DB Categories

### Managed Cloud-Native
| DB | Key Traits |
|---|---|
| **Pinecone** | Serverless, zero-ops, pod/serverless tiers, metadata filtering, namespaces for multi-tenancy, proprietary index |
| **Zilliz Cloud** | Managed Milvus, GPU-accelerated, segment-sealed architecture |
| **Weaviate Cloud** | GraphQL API, modules for vectorization, hybrid search built-in |

### Open-Source Self-Hosted
| DB | Key Traits |
|---|---|
| **Qdrant** | Rust, gRPC+REST, payload indexes, segment architecture, quantization (scalar/PQ/binary), HNSW per segment, multi-vector |
| **Weaviate** | Go, modular vectorizers, hybrid BM25+vector, multi-tenancy via classes, HNSW with PQ |
| **Milvus** | Distributed, segment-sealed design, multiple index types (HNSW/IVF/DiskANN/GPU), time-travel queries |
| **Chroma** | Python-native, embedded-first, simple API, good for prototyping |

### Relational Extensions
| DB | Key Traits |
|---|---|
| **pgvector** | PostgreSQL extension, ivfflat + HNSW indexes, ACID transactions, familiar SQL, joins with relational data |
| **AlloyDB AI** | Google's PostgreSQL-compatible, ScaNN index, 100x faster than pgvector on large datasets |
| **Azure Cosmos DB** | DiskANN-based vector index, global distribution, multi-model |

### Search Engine Extensions
| DB | Key Traits |
|---|---|
| **Elasticsearch** | kNN via HNSW, hybrid with BM25, mature ecosystem, dense/sparse vectors |
| **Azure AI Search** | Integrated vectorization, semantic ranker, hybrid (RRF fusion), enterprise security |
| **OpenSearch** | AWS-managed option, k-NN plugin, Lucene/NMSLIB/Faiss engines |

### Local/Embedded
| DB | Key Traits |
|---|---|
| **FAISS** | Meta's library, not a DB, fastest brute-force and IVF/PQ, GPU support, no CRUD—rebuild required |
| **Chroma** | Embedded + client/server modes, Python/JS, DuckDB+Parquet backend |
| **LanceDB** | Embedded, columnar (Lance format), zero-copy, disk-based ANN, versioned datasets, serverless-friendly |

### Lakehouse Pattern
| DB | Key Traits |
|---|---|
| **LanceDB** | Lance columnar format on object storage, IVF-PQ on disk, automatic versioning, works with Delta/Iceberg pipelines |
| **Databricks Vector Search** | Delta Lake integration, auto-sync from Delta tables, managed Faiss |

---

## 2. Vector DB Capability Matrix (12 Capabilities)

| Capability | Pinecone | Qdrant | Weaviate | Milvus | pgvector | Elasticsearch | FAISS | LanceDB |
|---|---|---|---|---|---|---|---|---|
| **ANN Index Support** | Proprietary | HNSW | HNSW+PQ | HNSW/IVF/DiskANN/GPU | HNSW/IVFFlat | HNSW (Lucene) | IVF/PQ/HNSW/Flat | IVF-PQ (disk) |
| **Hybrid Search** | Sparse+Dense | Sparse vectors + payload filter | BM25+Vector (RRF) | Sparse+Dense | Full-text + vector (tsvector) | BM25+kNN (RRF) | No | Full-text + vector |
| **Metadata Filtering** | Up to 40 fields | Payload indexes (keyword, integer, geo, datetime, full-text) | Inverted filters on properties | Scalar filtering | SQL WHERE clauses | Full query DSL | No (pre-filter externally) | SQL-like filters on Lance columns |
| **Payload Indexing** | Auto | Explicit create_payload_index | Auto on filterable fields | Auto + manual | B-tree/GIN/GiST | Inverted index | N/A | Columnar (inherent) |
| **Multi-Tenancy** | Namespaces | Payload-based or collection-per-tenant | Class-based tenancy | Partitions | Row-level security + schemas | Index-per-tenant or filtered | N/A | Table-per-tenant or filtered |
| **Update/Delete** | Upsert, delete by ID/filter | Upsert, delete by ID/filter, batch | Update properties, delete | Upsert, delete, compaction reclaims | Standard SQL UPDATE/DELETE | Update/delete doc | Rebuild index | Append-only with delete tombstones, compaction |
| **Consistency Model** | Eventual (seconds) | Strong (single-node) / Eventual (distributed) | Eventual | Strong (bounded staleness configurable) | Strong (ACID) | Near-real-time (refresh interval) | N/A (in-memory) | Strong (append-only + versioned) |
| **Backup/Restore** | Collections API | Snapshots (full + incremental) | Backup API | Backup to S3/GCS | pg_dump / pg_basebackup | Snapshot/restore | serialize_index / write_index | Lance versioning (zero-cost snapshots) |
| **Replication** | Managed (3 replicas) | Raft-based (distributed mode) | Raft consensus | etcd + message queue based | Streaming replication | Primary/replica shards | N/A | Object storage replication |
| **Sharding/Rebalancing** | Auto (serverless) | Manual shard config, auto-balance planned | Auto-sharding | Shard by partition key, auto-balance via query coord | Citus for distributed, table partitioning | Auto shard allocation | Manual sharding | Partitioned by IVF centroids |
| **Observability** | Dashboard, Prometheus metrics | Prometheus/Grafana, telemetry API | Prometheus, Go metrics | Grafana dashboards, Prometheus, Jaeger tracing | pg_stat_statements, explain analyze | Kibana, _cat APIs, _nodes/stats | Manual timing | Metrics via Lance stats |
| **Security** | API key, RBAC (orgs), SOC2 | API key, TLS, RBAC (cloud) | OIDC, API key, RBAC | TLS, RBAC, encryption at rest | PostgreSQL auth (SCRAM, certs, RLS) | TLS, RBAC, field-level security, SAML | N/A (library) | Inherits storage auth (S3 IAM) |

---

## 3. Selection Criteria (13 Criteria)

| # | Criterion | Architect Questions |
|---|---|---|
| 1 | **Scale** | How many vectors? 1M, 100M, 1B+? Growth rate? |
| 2 | **Latency** | What p99 latency is acceptable? <10ms, <50ms, <200ms? |
| 3 | **Throughput** | Peak QPS? Bursty or sustained? Read/write ratio? |
| 4 | **Freshness** | How quickly must new vectors be searchable? Real-time, seconds, minutes? |
| 5 | **Filtering Complexity** | Simple equality? Range? Geo? Nested? How selective are filters? |
| 6 | **Hybrid Requirements** | Need keyword search too? What fusion strategy? |
| 7 | **Multi-Tenancy** | Hundreds of tenants or millions? Isolation requirements? |
| 8 | **Operational Maturity** | Team skill set? Can you run distributed systems? |
| 9 | **Cost Model** | Pay-per-query vs provisioned? Storage-dominant or compute-dominant? |
| 10 | **Consistency** | Can you tolerate stale reads? How stale? |
| 11 | **Data Lifecycle** | TTL needed? Archival? Versioning? |
| 12 | **Integration** | Existing stack? Need SQL joins? Part of search platform? |
| 13 | **Compliance** | Data residency? Encryption? Audit logs? Certifications? |

---

## 4. Index Concepts

### HNSW (Hierarchical Navigable Small World)

**How it works:**
- Multi-layer graph where each layer is a navigable small-world network
- Top layers: sparse (long-range connections for fast navigation)
- Bottom layer: dense (short-range connections for precision)
- Search: enter at top layer, greedily descend to bottom layer

**Parameters:**
| Parameter | Description | Tradeoff |
|---|---|---|
| `M` | Max edges per node | Higher M = better recall, more memory (16-64 typical) |
| `ef_construction` | Beam width during build | Higher = better graph quality, slower build (100-500) |
| `ef_search` | Beam width during query | Higher = better recall, higher latency (50-500) |

**Characteristics:**
- Build time: O(N * log(N) * M)
- Query time: O(log(N) * ef_search)
- Memory: O(N * M * dim_size) — entire graph in RAM
- Recall: 95-99.5% achievable with proper tuning
- Dynamic: supports insert/delete without full rebuild

### IVFFlat (Inverted File with Flat Quantization)

**How it works:**
1. Cluster vectors into `nlist` centroids using k-means
2. Assign each vector to nearest centroid (inverted list)
3. At query time, find `nprobe` nearest centroids, then brute-force search within those lists

**Parameters:**
| Parameter | Description | Tradeoff |
|---|---|---|
| `nlist` | Number of clusters | More clusters = faster search, longer build, risk of empty clusters. Rule: sqrt(N) to 4*sqrt(N) |
| `nprobe` | Clusters to search | More probes = better recall, higher latency. Start at nlist/10 |

**Characteristics:**
- Build time: O(N * nlist * iterations) for k-means
- Query time: O(nprobe * N/nlist * dim)
- Memory: O(N * dim) — stores full vectors
- Recall: 90-99% depending on nprobe
- Static: adding vectors degrades cluster balance over time

### Product Quantization (PQ)

**How it works:**
1. Split each vector into `m` sub-vectors
2. Cluster each sub-space independently into 256 centroids
3. Represent each vector as `m` bytes (centroid IDs)
4. Compute approximate distances using lookup tables

**Compression:** 768-dim float32 (3072 bytes) → 96 sub-vectors × 1 byte = 96 bytes (32x compression)

**Variants:**
- **OPQ (Optimized PQ):** Rotate vectors before quantization for better sub-space independence
- **SQ (Scalar Quantization):** Quantize each dimension independently (float32→int8 = 4x compression, higher recall than PQ)
- **Binary Quantization:** 1-bit per dimension (32x compression, good for re-ranking with original vectors)

### Distance Metrics

| Metric | Formula | Use Case | Notes |
|---|---|---|---|
| **Cosine Similarity** | 1 - (A·B)/(‖A‖·‖B‖) | Text embeddings, normalized vectors | Most common for NLP |
| **Dot Product** | -(A·B) | When magnitude matters (MRL embeddings) | Faster than cosine if pre-normalized |
| **L2 (Euclidean)** | √(Σ(ai-bi)²) | Image embeddings, spatial data | Sensitive to magnitude |
| **Manhattan (L1)** | Σ|ai-bi| | High-dimensional sparse vectors | More robust to outliers |

### Recall vs Latency Tradeoffs

```
Recall
99.5% |          * HNSW(ef=500)
99%   |      * HNSW(ef=200)
98%   |   * HNSW(ef=100)         * IVF(nprobe=50)
95%   | * HNSW(ef=50)       * IVF(nprobe=20)
90%   |                 * IVF(nprobe=5)
      |_________________________________________
         1ms    5ms    10ms    50ms    Latency
```

---

## 5. Additional Concepts

### Disk-Based ANN
- **DiskANN (Microsoft):** Graph-based index on SSD, keeps compressed vectors in RAM, full vectors on disk. Handles billion-scale on single machine.
- **LanceDB approach:** IVF-PQ with centroids in memory, posting lists on disk (Lance columnar format).
- **Use case:** When dataset >> RAM. Trade ~2-5x latency for 10-100x cost reduction.

### Payload Indexes
Indexes on metadata fields that enable efficient pre/post-filtering:
- **Keyword index:** Exact match on strings (tenant_id, category)
- **Integer/Float index:** Range queries (price > 100)
- **Geo index:** Radius/bounding box queries
- **Datetime index:** Time range queries
- **Full-text index:** BM25 on text payloads

### Filter Pushdown
- **Pre-filtering:** Filter first, then ANN on subset. Accurate but slow if filter is non-selective.
- **Post-filtering:** ANN first, then filter results. Fast but may return < k results.
- **Integrated filtering (ACORN):** Modify graph traversal to respect filters. Best of both worlds.
- **Qdrant approach:** Estimates filter cardinality, chooses pre/post automatically.

### Segment Compaction
- Vectors stored in segments (immutable once sealed)
- Deletes create tombstones (soft delete)
- Compaction merges segments, removes tombstoned vectors, rebuilds indexes
- Critical for write-heavy workloads (prevents segment explosion)

### Tombstones
- Deleted vectors marked but not removed until compaction
- Impact: inflated memory, degraded recall (dead neighbors in graph), slower scans
- Monitor: tombstone ratio. Compact when > 10-20%.

### Snapshotting
- Point-in-time backup of index + data
- Full snapshot: entire collection state
- Incremental: only changed segments since last snapshot
- Use for: disaster recovery, blue-green migration source, compliance

### Hot/Warm/Cold Tiering
```
Hot:   In-memory HNSW, <5ms latency, $$$ 
Warm:  Disk-based (DiskANN/mmap), 10-50ms, $$ 
Cold:  Object storage (re-index on demand), seconds, $
```

### Namespaces vs Collections vs Partitions
| Concept | Scope | Isolation | Use Case |
|---|---|---|---|
| **Namespace** (Pinecone) | Logical partition within index | Soft (same index resources) | Per-user data separation |
| **Collection** (Qdrant/Weaviate) | Independent index + config | Hard (separate resources) | Different embedding models |
| **Partition** (Milvus) | Physical data partition | Medium (same collection, separate segments) | Time-based partitioning |

### Blue-Green Indexes
1. Build new index (green) alongside current (blue)
2. Populate green with same data + any new config/embeddings
3. Run shadow traffic to validate recall/latency
4. Atomic switch: route queries to green
5. Keep blue for rollback window, then decommission

### Read Replicas
- Scale read throughput by replicating index to multiple nodes
- Consistency: eventual (replication lag)
- Use case: high QPS with tolerance for slightly stale results
- Pattern: write to primary, read from replicas with load balancer

### Shard Rebalancing
- When shards become uneven (hot spots, growth)
- Strategies: split large shards, merge small shards, move shards between nodes
- Challenge: rebalancing while serving queries (online rebalancing)
- Milvus: automatic via query coordinator
- Qdrant: manual resharding (automatic planned)

### Freshness Watermarks
- Track: "queries are guaranteed to include vectors inserted before timestamp T"
- Important for consistency guarantees in distributed systems
- Implementation: write-ahead log position or timestamp
- Use: application can retry if watermark hasn't advanced past their write

---

## 6. Benchmark Slices (10 Query Types)

| # | Query Type | What It Tests | Example |
|---|---|---|---|
| 1 | **Pure ANN (no filter)** | Raw index performance | Find 10 nearest neighbors |
| 2 | **ANN + selective filter** | Filter that eliminates >90% of data | Vectors where tenant_id = "abc" |
| 3 | **ANN + broad filter** | Filter that keeps >50% of data | Vectors where created_at > last_week |
| 4 | **High-dimensional** | Curse of dimensionality | 1536-dim or 3072-dim embeddings |
| 5 | **Low-dimensional** | Where brute force might win | 64-128 dim embeddings |
| 6 | **Hybrid (vector + BM25)** | Fusion quality and latency | Keyword "error" + semantic similarity |
| 7 | **Batch query** | Throughput under concurrent load | 100 queries simultaneously |
| 8 | **Filtered count** | Metadata query without vector | Count documents matching filter |
| 9 | **Insert while querying** | Write impact on read performance | Sustained writes + reads |
| 10 | **Delete + query** | Tombstone impact | Delete 20% of vectors, measure recall |

---

## 7. Selection Decision Framework

### Decision 1: Managed vs Self-Hosted
```
IF (team < 5 engineers) AND (no Kubernetes expertise) → Managed
IF (data sovereignty required) AND (no cloud option in region) → Self-hosted
IF (cost at scale is primary concern) → Self-hosted (but factor ops cost)
IF (rapid iteration, MVP) → Managed
```

### Decision 2: Dedicated Vector DB vs Extension
```
IF (vectors are the primary workload) → Dedicated vector DB
IF (need ACID joins between vectors and relational data) → pgvector
IF (already have Elasticsearch for search) → ES vector features
IF (vectors are part of a larger data platform) → Lakehouse pattern
```

### Decision 3: Which Dedicated Vector DB
```
IF (zero-ops, just works) → Pinecone
IF (need full control, self-host, best filtering) → Qdrant  
IF (need GPU acceleration, billion scale) → Milvus
IF (need built-in vectorization, GraphQL) → Weaviate
IF (embedded, versioned, cost-optimized) → LanceDB
```

### Decision 4: Index Type
```
IF (dataset fits in RAM) AND (need dynamic inserts) → HNSW
IF (dataset fits in RAM) AND (batch-only) → IVF-PQ (better compression)
IF (dataset >> RAM) AND (single node) → DiskANN or IVF-PQ on disk
IF (exact results required) → Flat/brute-force (only viable < 100K vectors)
IF (extreme compression needed) → Binary quantization + re-rank
```
