# Vector Database Internals - Staff Architect Interview

## Question 26: HNSW Index Deep Dive
**Difficulty: Staff Level | Topic: Vector Index Algorithms | Asked at: Pinecone, Weaviate, Google**

Explain the HNSW (Hierarchical Navigable Small World) algorithm in detail. How does it achieve logarithmic search complexity? What are the trade-offs between build time, search quality, and memory? How would you tune it for a 1B vector dataset?

### Expected Answer:

**HNSW Algorithm Architecture:**

1. **Core Data Structure:**
   ```
   Layer 3 (sparse):    [A] -------- [D]
                          |
   Layer 2:         [A] -- [B] -- [D] -- [F]
                      |     |      |
   Layer 1:     [A]-[B]-[C]-[D]-[E]-[F]-[G]
                  |   |   |   |   |   |   |
   Layer 0:   [A][B][C][D][E][F][G][H][I][J][K]...  (all nodes)
   ```
   
   - Multi-layer graph where higher layers have exponentially fewer nodes
   - Each node appears in layer 0, and with probability 1/ln(M) in each higher layer
   - Navigation: Start at top layer, greedily traverse to closest node, then descend

2. **Search Algorithm:**
   ```python
   def search_hnsw(query, entry_point, max_layer, ef_search):
       current_node = entry_point
       
       # Phase 1: Greedy search through upper layers
       for layer in range(max_layer, 0, -1):
           current_node = greedy_search(query, current_node, layer, ef=1)
       
       # Phase 2: Broader search at layer 0
       candidates = beam_search(query, current_node, layer=0, ef=ef_search)
       
       return candidates[:top_k]
   
   def greedy_search(query, entry, layer, ef):
       """Navigate graph greedily toward query vector."""
       visited = set()
       candidates = MinHeap()  # by distance to query
       candidates.push(entry)
       
       while candidates:
           closest = candidates.pop()
           if closest.distance > furthest_result.distance:
               break  # No improvement possible
           
           for neighbor in closest.get_neighbors(layer):
               if neighbor not in visited:
                   visited.add(neighbor)
                   distance = compute_distance(query, neighbor)
                   candidates.push((distance, neighbor))
       
       return top_ef_results
   ```

3. **Parameter Tuning for 1B Vectors:**
   | Parameter | Small (<1M) | Medium (1M-100M) | Large (1B) |
   |-----------|-------------|-----------------|------------|
   | M (connections) | 16 | 32 | 48-64 |
   | efConstruction | 200 | 400 | 500 |
   | efSearch | 64 | 128 | 256 |
   | Memory/vector | 1.2KB | 2.5KB | 4KB |
   | Build time | 1hr | 24hr | 7-14 days |
   | Recall@10 | 0.99 | 0.97 | 0.95 |

4. **Memory Optimization for 1B Vectors (1024-dim, float32):**
   - Raw vectors: 1B × 1024 × 4 bytes = 4 TB
   - HNSW graph: ~200GB (connections metadata)
   - **Solutions:**
     - Product Quantization (PQ): 4TB → 128GB (32x compression)
     - Scalar Quantization (SQ8): 4TB → 1TB (4x compression)
     - Disk-based HNSW: Graph in memory, vectors on SSD (DiskANN approach)
     - Sharding: Split across 100 nodes, each handles 10M vectors

5. **Trade-offs:**
   - Higher M → Better recall, more memory, slower build
   - Higher efConstruction → Better graph quality, much slower build
   - Higher efSearch → Better recall, higher latency
   - **Key insight:** efSearch is the runtime knob; M and efConstruction are build-time decisions
   - **Production tip:** Build with high efConstruction (can't change later), tune efSearch at runtime

---

## Question 27: Vector Database Sharding Strategies
**Difficulty: Staff Level | Topic: Distributed Systems | Asked at: Pinecone, Milvus, Qdrant**

You need to serve 10B vectors with sub-50ms latency. Design a sharding strategy for a distributed vector database. Consider data distribution, query routing, and consistency guarantees.

### Expected Answer:

**Distributed Vector Database Architecture:**

1. **Sharding Approaches:**

   **Option A: Hash-Based Sharding**
   ```
   Vector ID → Hash → Shard Assignment
   - Pros: Uniform distribution, simple routing
   - Cons: Range queries impossible, re-sharding is expensive
   - Best for: Flat namespaces, ID-based lookups
   ```

   **Option B: Partition-Based Sharding (Recommended)**
   ```
   Vectors clustered by IVF centroids → Each cluster = one shard
   - Pros: Locality-aware, queries hit fewer shards
   - Cons: Imbalanced shards, hot spots possible
   - Best for: Large-scale similarity search
   ```

   **Option C: Tenant-Based Sharding**
   ```
   Tenant ID → Dedicated shard(s)
   - Pros: Perfect isolation, simple compliance
   - Cons: Uneven sizes, underutilized shards
   - Best for: Multi-tenant SaaS
   ```

2. **Hybrid Sharding Architecture (10B vectors):**
   ```
   10B vectors across 500 shards (20M vectors each)
   
   ┌─────────────────────────────────────────┐
   │           Query Router                    │
   │  (Determines which shards to query)       │
   └─────────────────┬────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
   ┌────▼───┐  ┌────▼───┐      ┌────▼───┐
   │Shard 1 │  │Shard 2 │ ...  │Shard 500│
   │20M vecs│  │20M vecs│      │20M vecs │
   │HNSW idx│  │HNSW idx│      │HNSW idx │
   │3 replicas│ │3 replicas│   │3 replicas│
   └─────────┘  └─────────┘    └─────────┘
   ```

3. **Query Routing (Critical for Latency):**
   ```python
   class SmartQueryRouter:
       def __init__(self):
           # Coarse quantizer: learns which shards are relevant
           self.coarse_centroids = self.train_centroids(n_shards=500)
       
       def route_query(self, query_vector, top_k=10, n_probe=20):
           """Only query the most relevant shards."""
           # Find closest centroids (cheap operation)
           shard_distances = cosine_similarity(query_vector, self.coarse_centroids)
           target_shards = top_n(shard_distances, n=n_probe)
           
           # Scatter query to selected shards
           results = parallel_query(target_shards, query_vector, top_k)
           
           # Gather and merge results
           return merge_and_rerank(results, top_k)
   ```

4. **Consistency & Replication:**
   - Write path: Synchronous write to primary + 1 replica, async to 3rd
   - Read path: Read from any replica (eventual consistency OK for search)
   - Index consistency: New vectors searchable within 1-5 seconds (near-real-time)
   - Rebalancing: When shard exceeds 25M vectors, split into 2 (background operation)

5. **Latency Budget (sub-50ms target):**
   | Operation | Time |
   |-----------|------|
   | Query routing (centroid comparison) | 2ms |
   | Network to shard nodes | 5ms |
   | HNSW search per shard | 15ms |
   | Parallel execution (20 shards) | 15ms (parallel) |
   | Merge + re-rank | 5ms |
   | Network response | 5ms |
   | **Total** | **~32ms** ✓ |

---

## Question 28: Vector Quantization Techniques
**Difficulty: Staff Level | Topic: Compression & Efficiency | Asked at: Google, Meta, Pinecone**

Compare Product Quantization (PQ), Scalar Quantization (SQ), and Binary Quantization for vector compression. When would you use each? Design a tiered storage system using multiple quantization levels.

### Expected Answer:

**Vector Quantization Comparison:**

1. **Techniques Overview:**

   | Technique | Compression | Recall Loss | Speed | Use Case |
   |-----------|-------------|-------------|-------|----------|
   | None (FP32) | 1x | 0% | Baseline | <10M vectors |
   | Scalar (SQ8) | 4x | 1-2% | 2-3x faster | 10M-100M vectors |
   | Product (PQ) | 32-64x | 3-5% | 5-10x faster | 100M-1B vectors |
   | Binary | 32x | 5-10% | 50x faster | Pre-filtering, 1B+ |
   | Matryoshka | Variable | Variable | Variable | Adaptive precision |

2. **Product Quantization Deep Dive:**
   ```python
   class ProductQuantizer:
       """
       Split 1024-dim vector into 128 sub-vectors of 8 dims each.
       Each sub-vector quantized to nearest centroid (256 centroids = 1 byte).
       Original: 1024 * 4 bytes = 4096 bytes
       Quantized: 128 * 1 byte = 128 bytes (32x compression!)
       """
       def __init__(self, n_subvectors=128, n_centroids=256):
           self.n_subvectors = n_subvectors
           self.n_centroids = n_centroids
           self.codebooks = None  # Trained centroids per subvector
       
       def train(self, vectors):
           subvector_dim = vectors.shape[1] // self.n_subvectors
           self.codebooks = []
           for i in range(self.n_subvectors):
               sub_vectors = vectors[:, i*subvector_dim:(i+1)*subvector_dim]
               centroids = kmeans(sub_vectors, self.n_centroids)
               self.codebooks.append(centroids)
       
       def encode(self, vector):
           codes = []
           for i, codebook in enumerate(self.codebooks):
               sub_vec = vector[i*self.subdim:(i+1)*self.subdim]
               code = nearest_centroid(sub_vec, codebook)
               codes.append(code)
           return np.array(codes, dtype=np.uint8)
       
       def distance(self, query, codes):
           """Asymmetric distance computation (ADC) - no decompression needed."""
           # Pre-compute query-to-centroid distances
           distance_tables = []
           for i, codebook in enumerate(self.codebooks):
               sub_query = query[i*self.subdim:(i+1)*self.subdim]
               distances = cdist(sub_query.reshape(1,-1), codebook)
               distance_tables.append(distances[0])
           
           # Lookup distances using codes
           total_distance = sum(
               distance_tables[i][codes[i]] 
               for i in range(self.n_subvectors)
           )
           return total_distance
   ```

3. **Tiered Storage Architecture:**
   ```
   ┌─────────────────────────────────────────────┐
   │ Hot Tier (RAM): Full precision FP32          │
   │ - Most queried vectors (top 1%)              │
   │ - Sub-5ms search                             │
   │ - Cost: $$$$ per GB                          │
   ├─────────────────────────────────────────────┤
   │ Warm Tier (RAM): SQ8 quantized               │
   │ - Active vectors (top 20%)                   │
   │ - Sub-10ms search                            │
   │ - Cost: $$ per GB (4x less than hot)         │
   ├─────────────────────────────────────────────┤
   │ Cool Tier (SSD): PQ compressed               │
   │ - Standard vectors (70%)                     │
   │ - Sub-30ms search                            │
   │ - Cost: $ per GB                             │
   ├─────────────────────────────────────────────┤
   │ Cold Tier (Object Storage): Binary + PQ      │
   │ - Rarely accessed vectors (9%)               │
   │ - Sub-100ms search (with pre-filtering)      │
   │ - Cost: ¢ per GB                             │
   └─────────────────────────────────────────────┘
   ```

4. **Tier Promotion/Demotion Logic:**
   ```python
   class TierManager:
       def promote(self, vector_id):
           """Move vector to hotter tier based on access frequency."""
           access_count = self.get_access_count(vector_id, window='7d')
           current_tier = self.get_tier(vector_id)
           
           if access_count > 1000 and current_tier != 'hot':
               self.move_to_tier(vector_id, 'hot', precision='fp32')
           elif access_count > 100 and current_tier not in ['hot', 'warm']:
               self.move_to_tier(vector_id, 'warm', precision='sq8')
       
       def demote_cold_vectors(self):
           """Nightly job to demote inactive vectors."""
           for vector in self.get_inactive_vectors(days=30):
               self.move_to_tier(vector.id, 'cold', precision='binary_pq')
   ```

5. **Rescoring Strategy:**
   - Search with quantized vectors (fast, approximate)
   - Fetch full-precision vectors for top-100 results only
   - Re-score with exact distance computation
   - Return top-10 with exact scores
   - This gives PQ speed with near-FP32 accuracy

---

## Question 29: Vector Database Consistency & Durability
**Difficulty: Staff Level | Topic: Data Engineering | Asked at: MongoDB, Elastic, Pinecone**

How do you ensure data durability and consistency in a vector database that handles 100K writes/second? Design the write path, WAL (Write-Ahead Log), and recovery mechanisms.

### Expected Answer:

**Vector Database Write Path & Durability:**

1. **Write Path Architecture:**
   ```
   Client Write Request
         │
         ▼
   ┌─────────────┐
   │  API Server  │  (Validate, assign vector ID)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │     WAL      │  (Append-only, fsync)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  Memtable   │  (In-memory buffer, sorted)
   └──────┬──────┘
          │ (When full: flush)
          ▼
   ┌─────────────┐
   │  Segment    │  (Immutable on-disk segment with mini-index)
   └──────┬──────┘
          │ (Background)
          ▼
   ┌─────────────┐
   │  Compaction  │  (Merge segments, rebuild HNSW)
   └─────────────┘
   ```

2. **WAL Implementation:**
   ```python
   class VectorWAL:
       def __init__(self, path, sync_mode='group'):
           self.log_file = open(path, 'ab')
           self.sync_mode = sync_mode  # 'every', 'group', 'periodic'
           self.buffer = []
           self.buffer_size = 0
       
       def append(self, operation: WriteOp) -> int:
           """Append operation to WAL. Returns LSN (Log Sequence Number)."""
           entry = WALEntry(
               lsn=self.next_lsn(),
               timestamp=time.time(),
               op_type=operation.type,  # INSERT, UPDATE, DELETE
               vector_id=operation.id,
               vector_data=operation.vector,
               metadata=operation.metadata
           )
           
           serialized = self.serialize(entry)
           self.buffer.append(serialized)
           self.buffer_size += len(serialized)
           
           if self.sync_mode == 'every':
               self.flush_and_sync()
           elif self.sync_mode == 'group' and self.buffer_size > 4096:
               self.flush_and_sync()  # Group commit for throughput
           
           return entry.lsn
       
       def flush_and_sync(self):
           self.log_file.write(b''.join(self.buffer))
           self.log_file.flush()
           os.fsync(self.log_file.fileno())
           self.buffer.clear()
           self.buffer_size = 0
   ```

3. **Consistency Guarantees:**
   | Level | Guarantee | Throughput | Use Case |
   |-------|-----------|------------|----------|
   | Strong | Read-after-write | 10K writes/s | Financial, compliance |
   | Session | Read-your-writes | 50K writes/s | User-facing apps |
   | Eventual | May read stale | 100K writes/s | Analytics, batch |
   
   ```python
   class ConsistencyManager:
       def write_with_consistency(self, vector, level='session'):
           if level == 'strong':
               # Synchronous replication to all replicas
               wal_lsn = self.primary.write(vector)
               await self.replicate_sync(vector, all_replicas)
               self.make_searchable(vector)
               return wal_lsn
           elif level == 'session':
               # Write to primary, async replicate, immediate searchability
               wal_lsn = self.primary.write(vector)
               self.make_searchable_async(vector)
               self.replicate_async(vector)
               return wal_lsn  # Client can read with this LSN
   ```

4. **Recovery Process:**
   ```python
   class RecoveryManager:
       def recover(self):
           """Recover from crash using WAL replay."""
           # 1. Find last checkpoint
           checkpoint = self.find_latest_checkpoint()
           
           # 2. Load checkpoint state (HNSW graph + vectors)
           self.load_checkpoint(checkpoint)
           
           # 3. Replay WAL entries after checkpoint
           for entry in self.wal.replay_from(checkpoint.lsn):
               if entry.op_type == 'INSERT':
                   self.memtable.insert(entry.vector_id, entry.vector_data)
               elif entry.op_type == 'DELETE':
                   self.memtable.delete(entry.vector_id)
           
           # 4. Rebuild in-memory index for memtable entries
           self.rebuild_memtable_index()
           
           # 5. Mark recovery complete
           self.set_status('ready')
   ```

5. **Compaction Strategy (LSM-tree inspired):**
   - Level 0: Flushed memtables (small segments, many)
   - Level 1: Merged segments (medium, fewer)
   - Level 2: Large consolidated segments (big, optimized HNSW)
   - Compaction trigger: When level N has >10 segments
   - During compaction: Old segments remain readable until new segment is complete
   - After compaction: Atomic switch + old segment deletion

---

## Question 30: Approximate vs Exact Nearest Neighbor Trade-offs
**Difficulty: Staff Level | Topic: Algorithm Design | Asked at: Google, Apple, Spotify**

In what scenarios would you choose exact nearest neighbor search over approximate methods? Design a system that dynamically switches between exact and approximate search based on query requirements and system load.

### Expected Answer:

**Adaptive Search Strategy:**

1. **When to Use Exact vs Approximate:**
   | Scenario | Exact (Brute Force) | Approximate (ANN) |
   |----------|--------------------|--------------------|
   | Dataset size < 100K | ✓ | Overkill |
   | Recall requirement = 100% | ✓ | Cannot guarantee |
   | Legal/financial decisions | ✓ | Risk of missing relevant |
   | Dataset > 1M | Too slow | ✓ |
   | Real-time serving (< 50ms) | Only if small | ✓ |
   | Filtered search (small subset) | ✓ (on subset) | May miss in filter |
   | Initial development/testing | ✓ (baseline) | After validation |

2. **Adaptive Search Controller:**
   ```python
   class AdaptiveSearchController:
       def search(self, query_vector, filters=None, recall_requirement=0.95):
           # Estimate result set size after filtering
           if filters:
               estimated_size = self.estimate_filtered_size(filters)
           else:
               estimated_size = self.total_vectors
           
           # Decision logic
           if estimated_size < 50_000:
               # Small enough for exact search
               return self.exact_search(query_vector, filters)
           
           elif recall_requirement >= 0.99:
               # High recall needed: use ANN with over-retrieval + re-ranking
               return self.high_recall_ann(query_vector, filters, 
                                          over_retrieve_factor=10)
           
           elif self.system_load > 0.8:
               # High load: use aggressive approximation
               return self.fast_ann(query_vector, filters, ef_search=32)
           
           else:
               # Standard ANN
               return self.standard_ann(query_vector, filters, ef_search=128)
       
       def high_recall_ann(self, query, filters, over_retrieve_factor):
           """ANN with exactness guarantee via verification."""
           # Over-retrieve with ANN
           candidates = self.ann_search(query, top_k=100 * over_retrieve_factor)
           
           # Exact re-ranking of candidates
           exact_scores = self.exact_distance(query, candidates)
           
           # This gives exact results within the candidate set
           return sorted(exact_scores)[:self.top_k]
   ```

3. **Pre-filtering vs Post-filtering:**
   ```python
   class FilterAwareSearch:
       def search_with_filter(self, query, filter_condition, top_k=10):
           # Estimate selectivity
           selectivity = self.estimate_selectivity(filter_condition)
           
           if selectivity < 0.01:  # Very selective (< 1% of data matches)
               # Pre-filter then exact search on small subset
               candidate_ids = self.metadata_index.filter(filter_condition)
               vectors = self.load_vectors(candidate_ids)
               return self.brute_force(query, vectors, top_k)
           
           elif selectivity < 0.1:
               # ANN with post-filtering and over-retrieval
               ann_results = self.ann_search(query, top_k=top_k * 20)
               filtered = [r for r in ann_results if self.matches_filter(r, filter_condition)]
               return filtered[:top_k]
           
           else:
               # Standard ANN with inline filtering (vector DB native)
               return self.ann_search(query, top_k=top_k, filter=filter_condition)
   ```

4. **Dynamic ef_search Tuning:**
   ```python
   class DynamicEfTuner:
       """Adjust ef_search based on real-time system metrics."""
       
       def get_ef_search(self) -> int:
           latency_budget_remaining = self.sla_target - self.current_overhead
           system_load = self.get_cpu_utilization()
           queue_depth = self.get_queue_depth()
           
           if system_load > 0.9 or queue_depth > 1000:
               return 32   # Fast, lower recall
           elif system_load > 0.7:
               return 64   # Balanced
           elif latency_budget_remaining > 50:
               return 256  # High quality, plenty of time
           else:
               return 128  # Standard
   ```

5. **Hybrid Approach: Candidate Generation + Exact Re-ranking**
   - Step 1: ANN search with low ef (fast) → 1000 candidates
   - Step 2: Load full vectors for 1000 candidates
   - Step 3: Exact distance computation → top 10
   - Result: Speed of ANN + accuracy of exact
   - Trade-off: More memory bandwidth (loading 1000 full vectors)
   - When: Need >0.99 recall but dataset too large for full exact search
# Embeddings Scalability - Staff Architect Interview

## Question 51: Embedding Model Selection and Trade-offs
**Difficulty: Staff Level | Topic: Embedding Architecture | Asked at: Google, OpenAI, Cohere**

You're building a semantic search system for a company with 500M documents in 15 languages. Compare embedding models (OpenAI ada-002, E5-large, BGE, Cohere embed-v3, Sentence-T5) across dimensions of quality, latency, cost, and multilingual support. How do you make the selection?

### Expected Answer:

**Embedding Model Comparison Matrix:**

| Model | Dims | Languages | Quality (MTEB) | Latency/1K docs | Cost/1M embeddings | Self-hosted? |
|-------|------|-----------|----------------|-----------------|-------------------|--------------|
| OpenAI text-embedding-3-large | 3072 | 100+ | 0.644 | 2s | $0.13 | No |
| E5-large-v2 | 1024 | English | 0.632 | 0.5s (GPU) | Self-hosted | Yes |
| BGE-M3 | 1024 | 100+ | 0.640 | 0.8s (GPU) | Self-hosted | Yes |
| Cohere embed-v3 | 1024 | 100+ | 0.638 | 1.5s | $0.10 | No |
| multilingual-e5-large | 1024 | 100+ | 0.625 | 0.6s (GPU) | Self-hosted | Yes |

**Decision Framework:**

1. **Cost Analysis at Scale (500M documents):**
   ```
   API-based (OpenAI/Cohere):
   - Initial embedding: 500M × $0.10/1M = $50,000 (one-time)
   - Re-embedding on model update: $50,000 (each time)
   - Ongoing (new docs, 1M/day): $100/day = $3,000/month
   
   Self-hosted (E5/BGE):
   - GPU infrastructure: 8x A100 GPUs for 2 weeks = $15,000 (one-time)
   - Ongoing (1M/day): 8x A10G = $2,000/month
   - Engineering overhead: $5,000/month (maintenance)
   
   Break-even: Self-hosted wins after 3 months at this scale
   ```

2. **Architecture Decision:**
   ```python
   class EmbeddingStrategy:
       def select_model(self, requirements):
           if requirements.languages > 1:
               if requirements.budget == 'unlimited':
                   return 'openai-text-embedding-3-large'  # Best quality
               elif requirements.data_sovereignty:
                   return 'bge-m3'  # Self-hosted multilingual
               else:
                   return 'cohere-embed-v3'  # Good balance
           else:  # English only
               if requirements.latency_critical:
                   return 'e5-small-v2'  # Fast, good enough
               else:
                   return 'e5-large-v2'  # Best English quality
   ```

3. **Matryoshka Embeddings for Adaptive Dimensionality:**
   - Store full 1024-dim embeddings
   - Use first 256 dims for fast pre-filtering (4x less memory)
   - Use full 1024 dims for final re-ranking
   - Dynamic: Use 128 dims on mobile, 512 on web, 1024 for batch

4. **Embedding Serving Infrastructure:**
   ```
   ┌─────────────────────────────────────────┐
   │  Embedding Service (gRPC)                │
   ├─────────────────────────────────────────┤
   │  Load Balancer (round-robin)             │
   ├────────┬────────┬────────┬──────────────┤
   │GPU Pod 1│GPU Pod 2│GPU Pod 3│ ... Pod N  │
   │(A100)   │(A100)   │(A100)   │            │
   │Batch:256│Batch:256│Batch:256│            │
   └────────┴────────┴────────┴──────────────┘
   
   Features:
   - Dynamic batching (accumulate requests for 10ms, then batch)
   - Model warmup on pod start
   - Health checks with embedding quality verification
   - Auto-scaling based on queue depth
   ```

5. **Quality Monitoring:**
   - Weekly evaluation against domain-specific benchmark
   - Monitor embedding drift over time (centroid shift)
   - A/B test new models against production
   - Alerting if retrieval precision drops (proxy for embedding quality)

---

## Question 52: Embedding Drift and Model Versioning
**Difficulty: Staff Level | Topic: MLOps for Embeddings | Asked at: Spotify, Netflix, LinkedIn**

Your production system has 2B embeddings generated with model v1. You want to upgrade to model v2 which has 15% better retrieval quality. Design a zero-downtime migration strategy that handles the dual-model transition period.

### Expected Answer:

**Embedding Migration Strategy:**

1. **The Problem:**
   - Model v1 embeddings are NOT compatible with model v2
   - Can't mix: v1 query embedding vs v2 document embeddings = garbage results
   - Re-embedding 2B documents takes days/weeks
   - Can't have downtime during migration

2. **Shadow Index Approach (Recommended):**
   ```
   Phase 1: Build Shadow Index (Days 1-14)
   ┌─────────────────┐     ┌─────────────────┐
   │  Primary Index   │     │  Shadow Index    │
   │  (Model v1)      │     │  (Model v2)      │
   │  2B vectors      │     │  Building...     │
   │  Serving traffic │     │  0% traffic      │
   └─────────────────┘     └─────────────────┘
   
   Phase 2: Validation (Days 14-17)
   - Shadow receives copy of all queries
   - Compare results quality (offline evaluation)
   - Verify latency, recall, precision
   
   Phase 3: Canary (Days 17-19)
   - Route 5% of traffic to shadow index
   - Monitor user metrics (click-through, satisfaction)
   
   Phase 4: Ramp (Days 19-21)
   - 25% → 50% → 75% → 100% to new index
   
   Phase 5: Cleanup (Day 21+)
   - Decommission v1 index after 7-day rollback window
   ```

3. **Dual-Write During Migration:**
   ```python
   class DualWriteEmbedder:
       def __init__(self):
           self.model_v1 = load_model('v1')
           self.model_v2 = load_model('v2')
           self.migration_progress = MigrationTracker()
       
       async def embed_and_index(self, document):
           # Always write to both during migration
           embedding_v1 = self.model_v1.encode(document)
           embedding_v2 = self.model_v2.encode(document)
           
           await asyncio.gather(
               self.index_v1.upsert(document.id, embedding_v1),
               self.index_v2.upsert(document.id, embedding_v2)
           )
       
       async def search(self, query, user_in_canary=False):
           if user_in_canary:
               query_embedding = self.model_v2.encode(query)
               return await self.index_v2.search(query_embedding)
           else:
               query_embedding = self.model_v1.encode(query)
               return await self.index_v1.search(query_embedding)
   ```

4. **Backfill Strategy for 2B Documents:**
   - Parallel processing: 100 GPU workers, each handling 20M docs
   - Priority queue: Embed frequently-accessed docs first (from access logs)
   - Incremental: Process in batches of 10M, checkpoint progress
   - Cost estimate: 2B docs ÷ 10K docs/min/GPU × 100 GPUs = ~33 hours
   - Idempotent: Can restart from any checkpoint without duplication

5. **Rollback Plan:**
   - Keep v1 index intact for 7 days after full migration
   - Feature flag to instantly switch back to v1
   - Monitor quality metrics continuously during and after migration
   - Automated rollback trigger: If precision drops >3% or latency >2x

---

## Question 53: Real-Time Embedding Generation at Scale
**Difficulty: Staff Level | Topic: Inference Infrastructure | Asked at: Google, Amazon, Microsoft**

Design an embedding inference service that processes 50,000 embedding requests per second with p99 latency under 20ms. Consider batching, GPU utilization, and failure handling.

### Expected Answer:

**High-Throughput Embedding Service:**

1. **Architecture:**
   ```
   Clients (50K RPS)
        │
        ▼
   ┌─────────────────────────────────────┐
   │  Load Balancer (L4, least-connections) │
   └─────────────────┬───────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
   ┌────▼────┐  ┌────▼────┐    ┌────▼────┐
   │Batcher 1│  │Batcher 2│... │Batcher N│   (CPU pods)
   │(10ms win)│  │(10ms win)│   │(10ms win)│
   └────┬────┘  └────┬────┘    └────┬────┘
        │            │                │
        ▼            ▼                ▼
   ┌─────────────────────────────────────┐
   │  GPU Worker Pool (Triton/TensorRT)   │
   │  32x A100 GPUs, batch_size=512       │
   │  Model: E5-large quantized (INT8)    │
   └─────────────────────────────────────┘
   ```

2. **Dynamic Batching:**
   ```python
   class DynamicBatcher:
       """Accumulate requests and batch for GPU efficiency."""
       
       def __init__(self, max_batch=512, max_wait_ms=5):
           self.max_batch = max_batch
           self.max_wait = max_wait_ms / 1000
           self.queue = asyncio.Queue()
           self.gpu_workers = GPUWorkerPool(n_gpus=32)
       
       async def embed(self, text: str) -> np.ndarray:
           """Single request interface with batching under the hood."""
           future = asyncio.Future()
           await self.queue.put((text, future))
           return await future
       
       async def batch_loop(self):
           """Background loop that forms and dispatches batches."""
           while True:
               batch = []
               deadline = time.time() + self.max_wait
               
               # Collect up to max_batch items or until timeout
               while len(batch) < self.max_batch and time.time() < deadline:
                   try:
                       item = await asyncio.wait_for(
                           self.queue.get(), 
                           timeout=max(0, deadline - time.time())
                       )
                       batch.append(item)
                   except asyncio.TimeoutError:
                       break
               
               if batch:
                   # Dispatch batch to GPU
                   texts = [item[0] for item in batch]
                   futures = [item[1] for item in batch]
                   
                   embeddings = await self.gpu_workers.infer(texts)
                   
                   for future, embedding in zip(futures, embeddings):
                       future.set_result(embedding)
   ```

3. **GPU Optimization:**
   - **Model quantization:** INT8 inference (2x throughput, <1% quality loss)
   - **TensorRT optimization:** Fused kernels, optimized memory layout
   - **Continuous batching:** Don't wait for full batch if GPU is idle
   - **Token padding optimization:** Group similar-length texts to minimize padding
   - **Multi-stream:** Run multiple CUDA streams per GPU for better utilization

4. **Latency Budget (20ms p99):**
   | Component | p99 Latency |
   |-----------|-------------|
   | Network (client → LB) | 2ms |
   | Queuing in batcher | 5ms (max wait) |
   | Tokenization (CPU) | 1ms |
   | GPU inference (batch=512) | 8ms |
   | Network (response) | 2ms |
   | **Total** | **18ms** ✓ |

5. **Failure Handling:**
   - GPU OOM: Reduce batch size dynamically, alert on repeated OOMs
   - GPU hardware failure: Health check every 5s, remove unhealthy GPUs from pool
   - Request timeout: Return error after 20ms, client retries to different pod
   - Overload protection: Adaptive admission control (reject with 429 when queue > 10K)
   - Graceful degradation: If all GPUs busy, route to CPU fallback (slower but available)

---

## Question 54: Cross-Encoder vs Bi-Encoder Trade-offs
**Difficulty: Staff Level | Topic: Retrieval Models | Asked at: Google, Microsoft, Cohere**

Explain the architectural differences between cross-encoders and bi-encoders for semantic search. Design a production system that uses both optimally. When would you use a cross-encoder, and what are the latency implications at scale?

### Expected Answer:

**Cross-Encoder vs Bi-Encoder Architecture:**

1. **Fundamental Difference:**
   ```
   Bi-Encoder (Embedding model):
   Query  → Encoder → Query Embedding  ─┐
                                          ├── Cosine Similarity
   Doc    → Encoder → Doc Embedding    ─┘
   
   Advantage: Doc embeddings pre-computed, search is just similarity
   Speed: O(1) per comparison (with ANN index)
   Quality: Good but limited (no cross-attention between query and doc)
   
   Cross-Encoder (Reranker):
   [Query, Doc] → Joint Encoder → Relevance Score
   
   Advantage: Full attention between query and document tokens
   Speed: O(n) - must process each pair sequentially  
   Quality: Significantly better (cross-attention captures nuances)
   ```

2. **Production Two-Stage Architecture:**
   ```python
   class TwoStageRetriever:
       def __init__(self):
           self.bi_encoder = BiEncoder('e5-large-v2')  # Stage 1: Fast recall
           self.cross_encoder = CrossEncoder('ms-marco-MiniLM-L-12')  # Stage 2: Precision
       
       async def search(self, query: str, top_k: int = 5) -> List[Result]:
           # Stage 1: Bi-encoder retrieval (fast, high recall)
           query_embedding = self.bi_encoder.encode(query)
           candidates = await self.vector_db.search(
               query_embedding, top_k=100  # Over-retrieve
           )
           
           # Stage 2: Cross-encoder re-ranking (slow, high precision)
           pairs = [(query, doc.text) for doc in candidates]
           scores = self.cross_encoder.predict(pairs)
           
           # Re-rank by cross-encoder score
           reranked = sorted(
               zip(candidates, scores), 
               key=lambda x: x[1], reverse=True
           )
           return [doc for doc, score in reranked[:top_k]]
   ```

3. **Latency Analysis:**
   | Stage | Documents | Latency | Notes |
   |-------|-----------|---------|-------|
   | Bi-encoder (query) | 1 | 5ms | Encode query only |
   | ANN search | 100M index | 10ms | HNSW lookup |
   | Cross-encoder | 100 docs | 50ms | Batch inference |
   | Cross-encoder | 1000 docs | 400ms | Too slow for real-time |
   
   **Key insight:** Cross-encoder on 100 candidates is the sweet spot.

4. **Optimizing Cross-Encoder for Production:**
   ```python
   class OptimizedCrossEncoder:
       def __init__(self):
           # Use distilled/quantized model for speed
           self.model = load_model('cross-encoder-MiniLM-L-6', quantized=True)
           
       def predict_batch(self, pairs: List[Tuple[str, str]]) -> List[float]:
           # Optimization 1: Sort by length for minimal padding
           sorted_pairs = sorted(pairs, key=lambda p: len(p[0]) + len(p[1]))
           
           # Optimization 2: Batch on GPU with dynamic batching
           scores = self.model.predict(sorted_pairs, batch_size=64)
           
           # Optimization 3: Early termination
           # If top score is much higher than remaining, stop early
           return scores
   ```

5. **When NOT to use Cross-Encoder:**
   - Real-time autocomplete (latency too high even for 10 docs)
   - First-stage retrieval (can't pre-compute, too slow for full corpus)
   - Mobile/edge deployment (model too large)
   - When bi-encoder quality is sufficient (simple factual lookups)
   - When cost constraints are tight (GPU compute for every query)

---

## Question 55: Embedding Fine-tuning for Domain Adaptation
**Difficulty: Staff Level | Topic: Model Training | Asked at: Cohere, OpenAI, Anthropic**

Your general-purpose embedding model performs poorly on domain-specific retrieval (medical, legal, financial). Design a fine-tuning pipeline that improves domain performance without catastrophic forgetting of general capabilities.

### Expected Answer:

**Domain-Adaptive Embedding Fine-tuning:**

1. **Training Data Generation:**
   ```python
   class DomainTrainingDataGenerator:
       def generate_pairs(self, domain_documents):
           training_data = []
           
           # Method 1: Synthetic query generation
           for doc in domain_documents:
               queries = self.llm.generate(
                   f"Generate 5 diverse questions that this document answers:\n{doc}"
               )
               for query in queries:
                   training_data.append({
                       'query': query,
                       'positive': doc,
                       'negatives': self.mine_hard_negatives(query, doc)
                   })
           
           # Method 2: Click-through data (if available)
           for log in self.search_logs:
               if log.clicked:
                   training_data.append({
                       'query': log.query,
                       'positive': log.clicked_doc,
                       'negatives': log.shown_but_not_clicked
                   })
           
           # Method 3: Document structure exploitation
           # Heading → paragraph pairs as positive pairs
           for doc in domain_documents:
               for heading, paragraph in doc.heading_paragraph_pairs():
                   training_data.append({
                       'query': heading,
                       'positive': paragraph,
                       'negatives': self.random_paragraphs(exclude=paragraph)
                   })
           
           return training_data
   ```

2. **Training Strategy (Avoid Catastrophic Forgetting):**
   ```python
   class DomainFinetuner:
       def fine_tune(self, base_model, domain_data, general_data):
           # Strategy 1: Mixed training (70% domain, 30% general)
           mixed_data = self.mix_datasets(
               domain_data, weight=0.7,
               general_data, weight=0.3
           )
           
           # Strategy 2: Learning rate scheduling
           optimizer = AdamW(
               model.parameters(),
               lr=2e-5,  # Small LR to preserve general knowledge
               weight_decay=0.01
           )
           scheduler = WarmupCosineSchedule(
               warmup_steps=500,
               total_steps=10000
           )
           
           # Strategy 3: Selective layer freezing
           # Freeze bottom 6 layers (general knowledge), fine-tune top 6
           for i, layer in enumerate(model.layers):
               if i < 6:
                   layer.requires_grad_(False)
           
           # Strategy 4: Contrastive loss with hard negatives
           loss_fn = MultipleNegativesRankingLoss(
               with_in_batch_negatives=True
           )
           
           # Train
           for batch in DataLoader(mixed_data, batch_size=128):
               loss = loss_fn(
                   model(batch.queries),
                   model(batch.positives),
                   model(batch.negatives)
               )
               loss.backward()
               optimizer.step()
   ```

3. **Hard Negative Mining:**
   ```python
   def mine_hard_negatives(self, query, positive_doc, n_negatives=7):
       """Find documents that are similar but NOT relevant (hard negatives)."""
       # Embed query with current model
       query_emb = self.model.encode(query)
       
       # Find top-50 similar documents
       candidates = self.index.search(query_emb, top_k=50)
       
       # Filter out the positive
       candidates = [c for c in candidates if c.id != positive_doc.id]
       
       # Select hard negatives (similar but not relevant)
       # Use cross-encoder to verify they're NOT relevant
       hard_negatives = []
       for candidate in candidates:
           relevance = self.cross_encoder.predict(query, candidate.text)
           if relevance < 0.3:  # Not relevant despite high similarity
               hard_negatives.append(candidate)
           if len(hard_negatives) >= n_negatives:
               break
       
       return hard_negatives
   ```

4. **Evaluation Protocol:**
   - **Domain metrics:** Retrieval precision@5 on domain test set (target: +15% over base)
   - **General metrics:** MTEB benchmark subset (target: <2% regression)
   - **A/B test:** Compare fine-tuned vs base model on production traffic
   - **Per-query analysis:** Identify query types where fine-tuning helps most
   
5. **Production Deployment:**
   - Train on 100K domain pairs (2-4 hours on 8x A100)
   - Evaluate against holdout test set + MTEB general benchmark
   - If both pass: Deploy with shadow traffic first
   - Re-embed all domain documents with new model (batch job)
   - Keep general model as fallback for out-of-domain queries
   - Re-train monthly with new domain data (continuous improvement)
# Embeddings Advanced Topics - Staff Architect Interview

## Question 56: Multi-Vector Representations (ColBERT)
**Difficulty: Staff Level | Topic: Advanced Retrieval | Asked at: Google Research, Microsoft**

Explain the ColBERT late interaction paradigm and compare it with single-vector representations. When does multi-vector representation justify its additional storage and computation costs?

### Expected Answer:

**ColBERT Late Interaction Architecture:**

1. **Single-Vector vs Multi-Vector:**
   ```
   Single-Vector (Bi-Encoder):
   "machine learning algorithms" → [0.1, 0.3, ..., 0.8]  (1 vector, 768-dim)
   
   Multi-Vector (ColBERT):
   "machine learning algorithms" → [
       [0.1, 0.2, ...],  # "machine" token embedding (128-dim)
       [0.3, 0.1, ...],  # "learning" token embedding
       [0.5, 0.4, ...]   # "algorithms" token embedding
   ]
   (N vectors, 128-dim each, where N = token count)
   ```

2. **Late Interaction Mechanism:**
   ```python
   class ColBERTScorer:
       def score(self, query_vectors, doc_vectors):
           """
           MaxSim: For each query token, find max similarity with any doc token.
           Final score = sum of MaxSims across query tokens.
           """
           # query_vectors: [Q, 128] (Q query tokens)
           # doc_vectors: [D, 128] (D document tokens)
           
           # Compute all pairwise similarities
           similarity_matrix = query_vectors @ doc_vectors.T  # [Q, D]
           
           # For each query token, take max similarity with any doc token
           max_sims = similarity_matrix.max(dim=1).values  # [Q]
           
           # Final relevance score
           return max_sims.sum()
   ```

3. **Storage & Computation Trade-offs:**
   | Aspect | Single-Vector | ColBERT | Impact |
   |--------|--------------|---------|--------|
   | Storage/doc | 768 * 4 = 3KB | 128 * 128 * 4 = 65KB | ~20x more |
   | Index size (1B docs) | 3TB | 60TB | Significant |
   | Search (Stage 1) | ANN: 10ms | ANN on centroids: 15ms | Similar |
   | Scoring | Dot product: 0.001ms | MaxSim: 0.5ms/doc | 500x more |
   | Quality (BEIR) | 0.44 nDCG | 0.49 nDCG | +11% |

4. **When ColBERT is Worth It:**
   - Long documents where different sections are relevant to different queries
   - Queries with multiple distinct aspects (multi-faceted information needs)
   - When retrieval quality directly impacts revenue (e-commerce, legal)
   - When you can afford the storage (SSD is cheap, RAM is not)
   - NOT worth it for: Simple factual lookups, very large corpora with tight budgets

5. **Production Optimization:**
   ```python
   class OptimizedColBERT:
       def __init__(self):
           # Compression: Reduce per-token dims
           self.dim = 128  # Instead of 768
           # Residual compression: Store only residuals from centroid
           self.centroids = self.train_centroids(n=65536)
       
       def index_document(self, doc_tokens):
           """Compressed storage with centroid residuals."""
           embeddings = self.encode(doc_tokens)  # [N, 128]
           
           # Assign each token to nearest centroid
           centroid_ids = self.assign_centroids(embeddings)  # [N] uint16
           
           # Store residuals (much smaller magnitude)
           residuals = embeddings - self.centroids[centroid_ids]
           quantized_residuals = self.quantize(residuals)  # int8
           
           # Storage: centroid_id (2 bytes) + residual (128 bytes) = 130 bytes/token
           # vs original: 512 bytes/token (float32)
           return centroid_ids, quantized_residuals
   ```

---

## Question 57: Embedding Spaces and Alignment
**Difficulty: Staff Level | Topic: Representation Learning | Asked at: Meta AI, Google DeepMind**

How do you ensure that embeddings from different models, different modalities (text, image, audio), or different time periods are aligned in the same vector space? Design a system that maintains a unified embedding space as models evolve.

### Expected Answer:

**Embedding Space Alignment Architecture:**

1. **The Alignment Problem:**
   - Model v1 and v2 produce embeddings in DIFFERENT spaces
   - Text and image embeddings are in DIFFERENT spaces (unless specifically trained together)
   - Same model trained on different data → slightly different spaces (drift)
   - Need: Query in one space must find relevant items in any space

2. **Alignment Techniques:**
   ```python
   class EmbeddingAligner:
       # Technique 1: Linear Projection (Fast, approximate)
       def train_linear_alignment(self, source_embeds, target_embeds):
           """Learn W such that source_embeds @ W ≈ target_embeds."""
           # Procrustes alignment (orthogonal mapping)
           U, _, Vt = np.linalg.svd(target_embeds.T @ source_embeds)
           self.W = U @ Vt
           return self.W
       
       # Technique 2: Contrastive Alignment (Better quality)
       def train_contrastive_alignment(self, paired_data):
           """Train a projection network with contrastive loss."""
           projector = nn.Linear(source_dim, shared_dim)
           
           for (source_emb, target_emb) in paired_data:
               projected = projector(source_emb)
               loss = contrastive_loss(projected, target_emb)
               loss.backward()
       
       # Technique 3: Adapter Networks (Most flexible)
       def train_adapter(self, source_model, target_space_examples):
           """Add small adapter layer on top of source model."""
           adapter = nn.Sequential(
               nn.Linear(source_dim, hidden_dim),
               nn.GELU(),
               nn.Linear(hidden_dim, target_dim),
               nn.LayerNorm(target_dim)
           )
           # Train adapter while keeping source model frozen
   ```

3. **Multi-Modal Unified Space:**
   ```
   Text  → Text Encoder  → Projection → ┐
   Image → Vision Encoder → Projection → ├→ Shared Space (1024-dim)
   Audio → Audio Encoder  → Projection → ┘
   
   Training: CLIP-style contrastive learning on paired data
   - (text, image) pairs from web
   - (audio, text) pairs from transcripts
   - (image, audio) pairs from video
   ```

4. **Temporal Alignment (Model Evolution):**
   ```python
   class TemporalAligner:
       """Keep embeddings aligned as models are updated."""
       
       def __init__(self):
           self.anchor_set = self.select_anchor_documents(n=10000)
           # Fixed set of documents that represent the space well
       
       def align_new_model(self, new_model):
           # Embed anchors with both old and new model
           old_embeds = self.old_model.encode(self.anchor_set)
           new_embeds = new_model.encode(self.anchor_set)
           
           # Learn alignment transform
           transform = self.learn_alignment(new_embeds, old_embeds)
           
           # Validate alignment quality
           if self.alignment_quality(transform) > 0.95:
               # Apply transform to new model outputs
               return AlignedModel(new_model, transform)
           else:
               # Alignment too poor, need full re-indexing
               raise AlignmentFailure("Re-indexing required")
   ```

5. **Production Considerations:**
   - Maintain alignment validation suite (1000 query-document pairs)
   - Track alignment quality metric (mean reciprocal rank on cross-space retrieval)
   - Fallback: If alignment degrades, force queries to correct space
   - Cost: Alignment adds 1-2ms latency (matrix multiply) - negligible

---

## Question 58: Sparse vs Dense vs Learned Sparse Embeddings
**Difficulty: Staff Level | Topic: Retrieval Methods | Asked at: Elastic, Vespa, Google**

Compare traditional sparse representations (TF-IDF, BM25), dense embeddings, and learned sparse embeddings (SPLADE, DeepImpact). Design a system that optimally combines all three for maximum retrieval quality.

### Expected Answer:

**Three Paradigms of Text Representation:**

1. **Comparison:**
   | Aspect | BM25 (Sparse) | Dense Embedding | SPLADE (Learned Sparse) |
   |--------|---------------|-----------------|------------------------|
   | Representation | Term frequencies | Dense vector | Sparse activated terms |
   | Dimensions | Vocab size (~30K) | 768-1024 | Vocab size (~30K) |
   | Non-zero elements | 100-300 per doc | All | 200-500 per doc |
   | Storage/doc | ~500 bytes | 3-4KB | ~1KB |
   | Interpretable | Yes (terms visible) | No (abstract dims) | Yes (expanded terms) |
   | Exact match | Excellent | Poor | Good |
   | Semantic match | Poor | Excellent | Good |
   | Out-of-vocabulary | Fails | Handles | Partially handles |
   | Zero-shot | Good (no training) | Needs training | Needs training |

2. **SPLADE (Learned Sparse) Explanation:**
   ```python
   class SPLADE:
       """
       Produces sparse vectors where dimensions = vocabulary terms.
       Key insight: BERT predicts term importance including EXPANSION terms.
       
       "deep learning" → {
           "deep": 2.3, "learning": 2.1,
           "neural": 1.5, "network": 1.2,  # Expanded terms!
           "machine": 0.8, "AI": 0.7,
           "training": 0.5, ...
       }
       """
       def encode(self, text):
           # Get BERT token logits (vocabulary-sized)
           token_logits = self.bert(text).logits  # [seq_len, vocab_size]
           
           # ReLU + log to get importance weights
           weights = torch.log1p(torch.relu(token_logits))
           
           # Max-pool over sequence to get document representation
           sparse_repr = weights.max(dim=0).values  # [vocab_size]
           
           # Sparsify: keep only top-K terms
           topk_indices = sparse_repr.topk(200).indices
           sparse_vector = {idx: sparse_repr[idx] for idx in topk_indices}
           
           return sparse_vector
   ```

3. **Triple Combination Architecture:**
   ```python
   class TripleHybridRetriever:
       async def retrieve(self, query: str, top_k: int = 10):
           # Parallel retrieval from all three
           dense_task = self.dense_search(query, top_k=50)
           sparse_task = self.bm25_search(query, top_k=50)
           learned_sparse_task = self.splade_search(query, top_k=50)
           
           dense_results, sparse_results, splade_results = await asyncio.gather(
               dense_task, sparse_task, learned_sparse_task
           )
           
           # Adaptive fusion based on query characteristics
           weights = self.get_weights(query)
           # e.g., exact term query → boost BM25
           # conceptual query → boost dense
           # domain-specific → boost SPLADE (term expansion helps)
           
           fused = self.weighted_rrf(
               [dense_results, sparse_results, splade_results],
               weights=[weights['dense'], weights['bm25'], weights['splade']]
           )
           return fused[:top_k]
   ```

4. **When Each Shines:**
   - **BM25 wins:** Error codes ("ERR-4012"), product SKUs, exact phrases, rare terms
   - **Dense wins:** "How to fix slow database queries" (conceptual, no exact match needed)
   - **SPLADE wins:** Domain jargon with expansion ("MI" → expands to "myocardial infarction")

5. **Practical Deployment:**
   - BM25: Elasticsearch/Lucene (virtually free, already deployed)
   - Dense: Vector DB (Pinecone/Weaviate/Milvus)
   - SPLADE: Can use same inverted index as BM25! (Just different weights)
   - Cost: Dense is most expensive (GPU embedding + vector DB), BM25 cheapest
   - Recommendation: Start with BM25 + Dense, add SPLADE for domains with jargon

---

## Question 59: Embedding Compression for Edge Deployment
**Difficulty: Staff Level | Topic: Edge/Mobile AI | Asked at: Apple, Google, Qualcomm**

Design an embedding system that runs on mobile devices (iPhone, Android) with constraints of 100MB model size, 50ms latency, and no network connectivity. How do you compress embeddings while maintaining quality?

### Expected Answer:

**Edge Embedding Architecture:**

1. **Model Compression Pipeline:**
   ```
   Full Model (400MB, 768-dim, FP32)
        ↓ Knowledge Distillation
   Small Model (100MB, 384-dim, FP32)
        ↓ Quantization (INT8)
   Quantized (25MB, 384-dim, INT8)
        ↓ Pruning (50% sparsity)
   Final Edge Model (15MB, 384-dim, INT8, sparse)
   ```

2. **Knowledge Distillation:**
   ```python
   class EmbeddingDistiller:
       def distill(self, teacher_model, student_model, data):
           """Train small student to mimic large teacher."""
           for batch in data:
               # Teacher generates target embeddings
               with torch.no_grad():
                   teacher_embeds = teacher_model(batch)  # 768-dim
               
               # Student learns to match (with projection)
               student_embeds = student_model(batch)  # 384-dim
               projected = self.projection(student_embeds)  # 384 → 768
               
               # MSE loss + cosine similarity loss
               loss = (
                   0.5 * mse_loss(projected, teacher_embeds) +
                   0.5 * (1 - cosine_similarity(projected, teacher_embeds).mean())
               )
               loss.backward()
   ```

3. **On-Device Index Design:**
   ```python
   class OnDeviceVectorSearch:
       """Optimized for mobile constraints."""
       
       def __init__(self, max_vectors=100_000):
           # Use product quantization for storage
           self.pq = ProductQuantizer(n_subvectors=48, n_bits=8)
           # IVF for search speed (no HNSW - too much memory)
           self.n_clusters = 256
           self.ivf_index = IVFIndex(self.n_clusters, self.pq)
           
       def search(self, query_embedding, top_k=10):
           """Search ~100K vectors in <50ms on mobile CPU."""
           # Step 1: Find nearest clusters (2ms)
           nearest_clusters = self.find_clusters(query_embedding, n_probe=8)
           
           # Step 2: PQ distance computation within clusters (30ms)
           # Pre-compute distance table (query vs codebook centroids)
           distance_table = self.pq.compute_distance_table(query_embedding)
           
           # Step 3: Scan candidates using lookup table (fast!)
           candidates = self.scan_clusters(nearest_clusters, distance_table)
           
           return candidates[:top_k]
   ```

4. **Offline-First Architecture:**
   ```
   ┌─────────────────────────────────────┐
   │  On-Device                           │
   │  ┌─────────────┐ ┌──────────────┐   │
   │  │ Small Model  │ │ Local Index  │   │
   │  │ (15MB, INT8) │ │ (PQ, 50MB)  │   │
   │  └──────┬──────┘ └──────┬───────┘   │
   │         │               │            │
   │         └───────┬───────┘            │
   │                 │                    │
   │         Local Search (50ms)          │
   └─────────────────┬───────────────────┘
                     │ (When online)
                     ▼
   ┌─────────────────────────────────────┐
   │  Cloud (Optional Enhancement)        │
   │  - Full model re-ranking             │
   │  - Larger index search               │
   │  - Sync new embeddings to device     │
   └─────────────────────────────────────┘
   ```

5. **Quality Preservation Metrics:**
   | Metric | Full Model | Edge Model | Acceptable? |
   |--------|-----------|------------|-------------|
   | Recall@10 | 0.95 | 0.88 | Yes (>0.85) |
   | nDCG@10 | 0.82 | 0.74 | Yes (>0.70) |
   | Model size | 400MB | 15MB | Yes (<100MB) |
   | Latency | 5ms (GPU) | 45ms (CPU) | Yes (<50ms) |
   | Power draw | N/A | 50mW | Yes (< 100mW) |

---

## Question 60: Embedding Space Analysis and Debugging
**Difficulty: Staff Level | Topic: MLOps | Asked at: Google, Spotify, Pinterest**

Your retrieval quality has dropped 15% over the past month but no code changes were made. How do you diagnose issues in the embedding space? Design a monitoring and debugging toolkit for production embeddings.

### Expected Answer:

**Embedding Space Monitoring & Debugging:**

1. **Diagnostic Framework:**
   ```
   Quality Degradation Detected (Retrieval precision down 15%)
        │
        ▼
   ┌─────────────────────────────────────┐
   │  Step 1: Data Distribution Shift?    │
   │  - Compare document distribution     │
   │  - New vocabulary/topics?            │
   │  - Language distribution changed?    │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 2: Embedding Quality Metrics   │
   │  - Intrinsic: uniformity, alignment  │
   │  - Extrinsic: retrieval benchmarks   │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 3: Index Health                │
   │  - Fragmentation? Stale vectors?     │
   │  - Capacity issues? Hot spots?       │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 4: Query Pattern Changes       │
   │  - Query distribution shifted?       │
   │  - New query types not seen before?  │
   └─────────────────────────────────────┘
   ```

2. **Embedding Health Metrics:**
   ```python
   class EmbeddingMonitor:
       def compute_health_metrics(self, embeddings_sample):
           metrics = {}
           
           # 1. Uniformity: Are embeddings well-distributed?
           # Low uniformity = collapse (all embeddings similar)
           metrics['uniformity'] = self.compute_uniformity(embeddings_sample)
           # Target: -2.0 to -1.0 (lower is more uniform)
           
           # 2. Alignment: Are similar items close?
           metrics['alignment'] = self.compute_alignment(
               embeddings_sample, self.known_similar_pairs
           )
           # Target: < 0.5 (lower is better aligned)
           
           # 3. Isotropy: Is the space used efficiently?
           # Anisotropic = most variance in few directions
           eigenvalues = np.linalg.eigvalsh(np.cov(embeddings_sample.T))
           metrics['isotropy'] = self.compute_isotropy(eigenvalues)
           # Target: > 0.5 (higher is more isotropic)
           
           # 4. Cluster quality: Are semantic clusters still well-separated?
           metrics['silhouette_score'] = silhouette_score(
               embeddings_sample, self.known_labels
           )
           
           # 5. Dimensional collapse: Are any dimensions "dead"?
           dim_variance = np.var(embeddings_sample, axis=0)
           metrics['dead_dimensions'] = (dim_variance < 1e-6).sum()
           
           return metrics
   ```

3. **Root Cause Analysis:**
   ```python
   class EmbeddingDebugger:
       def diagnose_quality_drop(self):
           # Compare current vs baseline (30 days ago)
           current_embeddings = self.sample_recent_embeddings(n=10000)
           baseline_embeddings = self.load_baseline_snapshot()
           
           # Distribution shift detection
           shift = self.maximum_mean_discrepancy(current_embeddings, baseline_embeddings)
           if shift > threshold:
               # Embeddings have drifted! Why?
               
               # Check 1: New document types being indexed?
               new_doc_types = self.compare_document_distributions()
               
               # Check 2: Embedding model serving issues?
               model_health = self.validate_model_outputs(self.test_inputs)
               
               # Check 3: Tokenization issues? (library update?)
               tokenization_diff = self.compare_tokenizations(self.test_inputs)
               
               return DiagnosticReport(
                   shift_detected=True,
                   probable_causes=[new_doc_types, model_health, tokenization_diff]
               )
   ```

4. **Visualization Toolkit:**
   - UMAP/t-SNE projections of embedding space (before vs after)
   - Nearest neighbor consistency plots
   - Query-document similarity distribution histograms
   - Per-topic retrieval quality heatmaps
   - Dimensional contribution analysis

5. **Alerting Rules:**
   | Metric | Warning | Critical | Action |
   |--------|---------|----------|--------|
   | Uniformity increase > 20% | Warn | Alert | Check for collapse |
   | Dead dimensions > 5% | Warn | Alert | Model issue |
   | Distribution shift (MMD) > 0.1 | Warn | Alert | Data drift |
   | Retrieval precision drop > 5% | Warn | Alert | Full investigation |
   | Embedding latency p99 > 2x | Warn | Alert | Infra issue |
