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
