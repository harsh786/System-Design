# Solution 127: Vector Database (like Pinecone/Milvus/Weaviate)

## 1. Requirements Clarification

### Functional Requirements
- Store high-dimensional vector embeddings with metadata
- Approximate nearest neighbor (ANN) search with configurable recall
- Hybrid search: vector similarity combined with metadata filtering
- CRUD operations on vectors (insert, update, delete, upsert)
- Multiple distance metrics (cosine, L2, inner product)
- Multi-tenancy with namespace isolation

### Non-Functional Requirements
- 1 billion+ vectors stored
- Query latency: <10ms at p99
- Query throughput: 100,000+ QPS
- Write throughput: 50,000+ vectors/second
- 99.99% availability
- Vector dimensions: 128 to 4096

### Out of Scope
- Embedding generation (assumed done externally)
- Full-text search (only metadata filtering)
- Graph queries
- Training ML models

## 2. Back-of-the-Envelope Estimation

### Storage
- 1B vectors × 768 dimensions × 4 bytes (FP32) = 3 TB raw vectors
- With PQ compression (32 bytes/vector): 32 GB
- Metadata (avg 200 bytes/vector): 200 GB
- HNSW index overhead (~1.5x): 4.5 TB for full precision
- Total with replication (RF=3): ~15 TB

### Memory
- Hot tier (frequently queried): fit index in RAM
- HNSW graph structure: ~500 bytes/vector × 1B = 500 GB
- With PQ vectors in RAM, full vectors on SSD: fits in ~600 GB RAM cluster

### Throughput
- 100K QPS, each query searches ~200 nodes in HNSW graph
- 100K × 200 × 768 dims × 4 bytes = 60 GB/s distance computation bandwidth
- Need ~50 query nodes with SIMD-accelerated distance computation

### Network
- Write: 50K vectors/sec × 768 dims × 4 bytes = 150 MB/s ingestion
- Query fan-out: scatter to 10 shards × 100K QPS = 1M internal queries

## 3. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        Vector Database                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐     ┌──────────────┐     ┌────────────────────┐  │
│  │   Client    │────▶│  Query Router │────▶│  Result Aggregator │  │
│  │   SDK       │     │  (Load Bal)   │     │  (Top-K Merge)     │  │
│  └─────────────┘     └──────┬───────┘     └────────────────────┘  │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐         │
│  │  Shard 1    │     │  Shard 2    │     │  Shard N    │         │
│  │ ┌─────────┐ │     │ ┌─────────┐ │     │ ┌─────────┐ │         │
│  │ │  HNSW   │ │     │ │  HNSW   │ │     │ │  HNSW   │ │         │
│  │ │  Index   │ │     │ │  Index   │ │     │ │  Index   │ │         │
│  │ ├─────────┤ │     │ ├─────────┤ │     │ ├─────────┤ │         │
│  │ │ Metadata│ │     │ │ Metadata│ │     │ │ Metadata│ │         │
│  │ │  Index   │ │     │ │  Index   │ │     │ │  Index   │ │         │
│  │ ├─────────┤ │     │ ├─────────┤ │     │ ├─────────┤ │         │
│  │ │ Vector  │ │     │ │ Vector  │ │     │ │ Vector  │ │         │
│  │ │ Storage │ │     │ │ Storage │ │     │ │ Storage │ │         │
│  │ └─────────┘ │     │ └─────────┘ │     │ └─────────┘ │         │
│  └─────────────┘     └─────────────┘     └─────────────┘         │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    Storage Engine                           │    │
│  │  ┌──────────┐  ┌────────────┐  ┌─────────────────────┐   │    │
│  │  │   WAL    │  │  Segment   │  │  Compaction Engine  │   │    │
│  │  │          │  │  Manager   │  │                     │   │    │
│  │  └──────────┘  └────────────┘  └─────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    Coordination                             │    │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐   │    │
│  │  │  etcd    │  │  Shard Mgr │  │  Rebalancer         │   │    │
│  │  └──────────┘  └────────────┘  └──────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
```

## 4. Data Model / Schema Design

### Collection Schema
```python
@dataclass
class Collection:
    collection_id: str
    name: str
    tenant_id: str
    dimension: int                  # Vector dimensionality (e.g., 768)
    distance_metric: DistanceMetric # COSINE, L2, DOT_PRODUCT
    index_config: IndexConfig
    schema: MetadataSchema          # Typed metadata fields
    num_vectors: int
    created_at: datetime
    
@dataclass
class IndexConfig:
    index_type: str                 # "hnsw", "ivf_pq", "flat"
    # HNSW params
    hnsw_m: int = 16               # Max connections per node
    hnsw_ef_construction: int = 200 # Build-time beam width
    hnsw_ef_search: int = 100      # Query-time beam width
    # IVF params
    ivf_nlist: int = 4096          # Number of clusters
    ivf_nprobe: int = 32           # Clusters to search
    # Quantization
    quantization: str = "none"     # "none", "scalar", "pq", "binary"
    pq_segments: int = 48          # PQ sub-vector count
    pq_bits: int = 8               # Bits per sub-quantizer

@dataclass
class MetadataSchema:
    fields: List[MetadataField]
    
@dataclass
class MetadataField:
    name: str
    dtype: str                     # "string", "int", "float", "bool", "string[]"
    indexed: bool                  # Whether to build inverted index
    
@dataclass
class VectorRecord:
    id: str                        # User-provided or auto-generated
    vector: List[float]            # Dense embedding
    sparse_vector: Optional[Dict[int, float]]  # For hybrid sparse+dense
    metadata: Dict[str, Any]       # Filterable attributes
    namespace: str                 # Logical partition within collection
    created_at: datetime
    updated_at: datetime
```

### Internal Storage Format
```python
@dataclass
class Segment:
    """Immutable unit of storage (like an LSM-tree SSTable)."""
    segment_id: str
    collection_id: str
    shard_id: int
    level: int                     # Compaction level
    num_vectors: int
    min_id: str
    max_id: str
    
    # Files within segment
    vector_file: str               # Raw vectors (memory-mapped)
    pq_codes_file: str             # Quantized vectors
    hnsw_graph_file: str           # HNSW neighbor lists
    metadata_file: str             # Column-stored metadata
    id_mapping_file: str           # ID → internal offset
    bitmap_index_file: str         # Bitmap indexes for metadata
    bloom_filter_file: str         # Bloom filter for ID existence
    
    created_at: datetime
    size_bytes: int

@dataclass
class WriteAheadLog:
    """WAL entry for durability before segment flush."""
    sequence_id: int
    operation: str                 # "insert", "update", "delete"
    collection_id: str
    vector_id: str
    vector: Optional[List[float]]
    metadata: Optional[Dict[str, Any]]
    timestamp: datetime
```

## 5. API Design

### Vector Operations
```python
# Upsert vectors
POST /v1/collections/{collection}/vectors/upsert
{
    "vectors": [
        {
            "id": "doc-001",
            "values": [0.1, 0.2, ..., 0.8],  // 768 floats
            "sparse_values": {"indices": [10, 50, 999], "values": [0.5, 0.3, 0.1]},
            "metadata": {
                "category": "technology",
                "year": 2024,
                "tags": ["ai", "ml"],
                "source": "arxiv"
            }
        },
        ...
    ],
    "namespace": "default"
}
Response: {"upserted_count": 100}

# Query (ANN search with filtering)
POST /v1/collections/{collection}/query
{
    "vector": [0.15, 0.22, ..., 0.78],
    "top_k": 10,
    "namespace": "default",
    "filter": {
        "and": [
            {"field": "category", "op": "eq", "value": "technology"},
            {"field": "year", "op": "gte", "value": 2023},
            {"field": "tags", "op": "contains", "value": "ai"}
        ]
    },
    "include_metadata": true,
    "include_vectors": false
}
Response:
{
    "matches": [
        {"id": "doc-042", "score": 0.95, "metadata": {"category": "technology", ...}},
        {"id": "doc-107", "score": 0.91, "metadata": {"category": "technology", ...}},
        ...
    ],
    "usage": {"read_units": 5}
}

# Hybrid search (dense + sparse)
POST /v1/collections/{collection}/query
{
    "vector": [0.15, 0.22, ..., 0.78],
    "sparse_vector": {"indices": [42, 100, 567], "values": [0.8, 0.5, 0.3]},
    "top_k": 10,
    "alpha": 0.7,  // Weight: 0.7 dense + 0.3 sparse
    "filter": {"field": "category", "op": "eq", "value": "technology"}
}

# Delete vectors
POST /v1/collections/{collection}/vectors/delete
{
    "ids": ["doc-001", "doc-002"],
    "namespace": "default"
}

# Fetch vectors by ID
POST /v1/collections/{collection}/vectors/fetch
{
    "ids": ["doc-001", "doc-002"],
    "include_vectors": true
}
```

## 6. Core Algorithm: HNSW (Hierarchical Navigable Small World)

### HNSW Construction
```python
class HNSWIndex:
    """
    HNSW: Multi-layer graph where each layer is a navigable small world.
    Top layers have few nodes (long-range connections).
    Bottom layer has all nodes (local connections).
    
    Search: start at top layer, greedily descend, refine at bottom.
    """
    
    def __init__(self, dim: int, M: int = 16, ef_construction: int = 200, 
                 ml: float = 1.0 / math.log(2.0)):
        self.dim = dim
        self.M = M                     # Max connections per node per layer
        self.M_max0 = 2 * M            # Max connections at layer 0
        self.ef_construction = ef_construction
        self.ml = ml                   # Level generation factor
        self.entry_point = None
        self.max_level = 0
        self.nodes = {}                # id -> vector
        self.graphs = defaultdict(lambda: defaultdict(list))  # level -> node -> neighbors
        
    def _random_level(self) -> int:
        """Assign a random level to new node (exponential distribution)."""
        return int(-math.log(random.random()) * self.ml)
    
    def insert(self, node_id: str, vector: np.ndarray):
        """Insert a vector into the HNSW graph."""
        self.nodes[node_id] = vector
        node_level = self._random_level()
        
        if self.entry_point is None:
            self.entry_point = node_id
            self.max_level = node_level
            return
        
        # Phase 1: Traverse from top to node's level (greedy, single nearest)
        current = self.entry_point
        for level in range(self.max_level, node_level, -1):
            current = self._search_layer_greedy(vector, current, level)
        
        # Phase 2: From node's level down to 0, find and connect neighbors
        for level in range(min(node_level, self.max_level), -1, -1):
            # Find ef_construction nearest neighbors at this level
            candidates = self._search_layer(vector, current, self.ef_construction, level)
            
            # Select M best neighbors using heuristic
            M_level = self.M if level > 0 else self.M_max0
            neighbors = self._select_neighbors_heuristic(vector, candidates, M_level)
            
            # Add bidirectional connections
            self.graphs[level][node_id] = neighbors
            for neighbor_id in neighbors:
                neighbor_connections = self.graphs[level][neighbor_id]
                neighbor_connections.append(node_id)
                
                # Prune if over capacity
                if len(neighbor_connections) > M_level:
                    neighbor_vec = self.nodes[neighbor_id]
                    self.graphs[level][neighbor_id] = self._select_neighbors_heuristic(
                        neighbor_vec, neighbor_connections, M_level
                    )
            
            current = candidates[0] if candidates else current
        
        # Update entry point if new node has higher level
        if node_level > self.max_level:
            self.max_level = node_level
            self.entry_point = node_id
    
    def _select_neighbors_heuristic(self, query: np.ndarray, 
                                     candidates: List[str], M: int) -> List[str]:
        """
        Heuristic neighbor selection (Algorithm 4 in HNSW paper).
        Prefers diverse neighbors over pure closest ones.
        Ensures good graph connectivity and search performance.
        """
        if len(candidates) <= M:
            return candidates
            
        # Sort candidates by distance to query
        candidates_with_dist = [
            (cid, np.linalg.norm(query - self.nodes[cid])) 
            for cid in candidates
        ]
        candidates_with_dist.sort(key=lambda x: x[1])
        
        selected = []
        for cid, dist_to_query in candidates_with_dist:
            if len(selected) >= M:
                break
                
            # Check if this candidate is closer to query than to any selected neighbor
            # This ensures diversity in the neighborhood
            good = True
            for sid in selected:
                dist_to_selected = np.linalg.norm(self.nodes[cid] - self.nodes[sid])
                if dist_to_selected < dist_to_query:
                    good = False
                    break
            
            if good:
                selected.append(cid)
        
        # Fill remaining slots with closest candidates
        if len(selected) < M:
            for cid, _ in candidates_with_dist:
                if cid not in selected:
                    selected.append(cid)
                    if len(selected) >= M:
                        break
                        
        return selected
    
    def search(self, query: np.ndarray, k: int, ef: int = None) -> List[Tuple[str, float]]:
        """
        Search for k nearest neighbors.
        ef: beam width (trade-off between recall and speed).
        """
        if ef is None:
            ef = max(k, self.ef_construction)
            
        # Traverse from top layer down to layer 1
        current = self.entry_point
        for level in range(self.max_level, 0, -1):
            current = self._search_layer_greedy(query, current, level)
        
        # Search layer 0 with beam width ef
        candidates = self._search_layer(query, current, ef, level=0)
        
        # Return top-k
        results = [(cid, np.linalg.norm(query - self.nodes[cid])) for cid in candidates]
        results.sort(key=lambda x: x[1])
        return results[:k]
    
    def _search_layer(self, query: np.ndarray, entry: str, ef: int, level: int) -> List[str]:
        """Beam search at a single layer. Returns up to ef nearest nodes."""
        visited = {entry}
        candidates = []  # Min-heap by distance (closest first)
        results = []     # Max-heap by distance (farthest first for pruning)
        
        dist = np.linalg.norm(query - self.nodes[entry])
        heapq.heappush(candidates, (dist, entry))
        heapq.heappush(results, (-dist, entry))
        
        while candidates:
            closest_dist, closest = heapq.heappop(candidates)
            farthest_dist = -results[0][0]
            
            if closest_dist > farthest_dist:
                break  # All remaining candidates are farther than worst result
            
            # Explore neighbors of closest candidate
            for neighbor in self.graphs[level].get(closest, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                
                ndist = np.linalg.norm(query - self.nodes[neighbor])
                
                if ndist < farthest_dist or len(results) < ef:
                    heapq.heappush(candidates, (ndist, neighbor))
                    heapq.heappush(results, (-ndist, neighbor))
                    
                    if len(results) > ef:
                        heapq.heappop(results)  # Remove farthest
        
        return [node_id for (_, node_id) in results]
```

### Hybrid Search: Integrated Filtering During Traversal
```python
class FilteredHNSWSearch:
    """
    Hybrid search: combine ANN with metadata filtering.
    Three strategies with automatic selection based on filter selectivity.
    """
    
    def __init__(self, hnsw_index: HNSWIndex, metadata_index: MetadataIndex):
        self.hnsw = hnsw_index
        self.metadata = metadata_index
        
    def search(self, query: np.ndarray, k: int, filter_expr: dict, ef: int = 100):
        """Auto-select strategy based on filter selectivity."""
        selectivity = self.metadata.estimate_selectivity(filter_expr)
        
        if selectivity > 0.5:
            # Most vectors match filter → post-filter (fastest ANN)
            return self._post_filter_search(query, k, filter_expr, ef)
        elif selectivity > 0.01:
            # Moderate selectivity → integrated filter during traversal
            return self._integrated_filter_search(query, k, filter_expr, ef * 3)
        else:
            # Very selective → pre-filter then brute-force/ANN on subset
            return self._pre_filter_search(query, k, filter_expr)
    
    def _integrated_filter_search(self, query, k, filter_expr, ef):
        """
        Modified HNSW search: skip non-matching nodes during traversal.
        Expand search beam to compensate for filtered-out nodes.
        """
        # Get bitmap of matching vector IDs
        matching_bitmap = self.metadata.evaluate_filter(filter_expr)
        
        visited = set()
        candidates = []
        results = []
        
        entry = self.hnsw.entry_point
        # Navigate to layer 0
        for level in range(self.hnsw.max_level, 0, -1):
            entry = self.hnsw._search_layer_greedy(query, entry, level)
        
        dist = np.linalg.norm(query - self.hnsw.nodes[entry])
        heapq.heappush(candidates, (dist, entry))
        visited.add(entry)
        
        if matching_bitmap.test(entry):
            heapq.heappush(results, (-dist, entry))
        
        while candidates:
            closest_dist, closest = heapq.heappop(candidates)
            
            if results and closest_dist > -results[0][0]:
                if len(results) >= k:
                    break
            
            for neighbor in self.hnsw.graphs[0].get(closest, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                
                ndist = np.linalg.norm(query - self.hnsw.nodes[neighbor])
                
                # Always add to candidates (for graph traversal continuity)
                if len(results) < ef or ndist < -results[0][0]:
                    heapq.heappush(candidates, (ndist, neighbor))
                
                # Only add to results if passes filter
                if matching_bitmap.test(neighbor):
                    heapq.heappush(results, (-ndist, neighbor))
                    if len(results) > ef:
                        heapq.heappop(results)
        
        final = [(nid, -d) for d, nid in sorted(results)]
        return final[:k]
    
    def _pre_filter_search(self, query, k, filter_expr):
        """For very selective filters: get matching IDs, then compute distances."""
        matching_ids = self.metadata.get_matching_ids(filter_expr)
        
        if len(matching_ids) < 10000:
            # Brute force on small set
            distances = []
            for vid in matching_ids:
                vec = self.hnsw.nodes[vid]
                dist = np.linalg.norm(query - vec)
                distances.append((vid, dist))
            distances.sort(key=lambda x: x[1])
            return distances[:k]
        else:
            # Build temporary small HNSW or use IVF on subset
            return self._ann_on_subset(query, k, matching_ids)
```

## 7. Deep Dive: Memory Optimization and Quantization

### Product Quantization
```python
class ProductQuantizer:
    """
    Product Quantization: divide vector into sub-vectors, quantize each independently.
    768-dim vector with 48 sub-vectors × 8 bits = 48 bytes (vs 3072 bytes FP32).
    ~64x compression with ~95% recall on typical workloads.
    """
    
    def __init__(self, dim: int, num_subvectors: int = 48, bits: int = 8):
        self.dim = dim
        self.m = num_subvectors
        self.bits = bits
        self.k = 2 ** bits            # Centroids per subspace (256 for 8-bit)
        self.sub_dim = dim // num_subvectors
        self.codebooks = None         # m × k × sub_dim
        
    def train(self, vectors: np.ndarray, iterations: int = 20):
        """Train codebooks using k-means on each sub-vector space."""
        n = vectors.shape[0]
        self.codebooks = np.zeros((self.m, self.k, self.sub_dim), dtype=np.float32)
        
        for i in range(self.m):
            # Extract sub-vectors for this subspace
            start = i * self.sub_dim
            end = start + self.sub_dim
            sub_vectors = vectors[:, start:end]
            
            # K-means clustering
            centroids = self._kmeans(sub_vectors, self.k, iterations)
            self.codebooks[i] = centroids
    
    def encode(self, vectors: np.ndarray) -> np.ndarray:
        """Encode vectors to PQ codes (uint8 array)."""
        n = vectors.shape[0]
        codes = np.zeros((n, self.m), dtype=np.uint8)
        
        for i in range(self.m):
            start = i * self.sub_dim
            end = start + self.sub_dim
            sub_vectors = vectors[:, start:end]
            
            # Assign each sub-vector to nearest centroid
            distances = self._pairwise_distances(sub_vectors, self.codebooks[i])
            codes[:, i] = np.argmin(distances, axis=1)
            
        return codes
    
    def search_with_adc(self, query: np.ndarray, codes: np.ndarray, k: int):
        """
        Asymmetric Distance Computation (ADC):
        Pre-compute distance from query sub-vectors to all centroids.
        Then sum up distances using lookup table.
        
        Complexity: O(m * k) precompute + O(n * m) scan (vs O(n * d) brute force)
        """
        # Precompute distance lookup table: m × k
        dist_table = np.zeros((self.m, self.k), dtype=np.float32)
        for i in range(self.m):
            start = i * self.sub_dim
            end = start + self.sub_dim
            query_sub = query[start:end]
            # Distance from query sub-vector to each centroid
            dist_table[i] = np.sum((self.codebooks[i] - query_sub) ** 2, axis=1)
        
        # Compute approximate distances using lookup
        n = codes.shape[0]
        distances = np.zeros(n, dtype=np.float32)
        for i in range(self.m):
            distances += dist_table[i, codes[:, i]]
        
        # Return top-k
        top_k_idx = np.argpartition(distances, k)[:k]
        top_k_idx = top_k_idx[np.argsort(distances[top_k_idx])]
        return top_k_idx, distances[top_k_idx]


class ScalarQuantizer:
    """
    Scalar quantization: FP32 → INT8 per dimension.
    4x compression with minimal quality loss (~99% recall).
    """
    
    def __init__(self, dim: int):
        self.dim = dim
        self.mins = None      # Per-dimension minimum
        self.maxs = None      # Per-dimension maximum
        self.scales = None    # (max - min) / 255
        
    def train(self, vectors: np.ndarray):
        self.mins = vectors.min(axis=0)
        self.maxs = vectors.max(axis=0)
        self.scales = (self.maxs - self.mins) / 255.0
        self.scales[self.scales == 0] = 1.0  # Avoid division by zero
        
    def encode(self, vectors: np.ndarray) -> np.ndarray:
        normalized = (vectors - self.mins) / self.scales
        return np.clip(normalized, 0, 255).astype(np.uint8)
    
    def decode(self, codes: np.ndarray) -> np.ndarray:
        return codes.astype(np.float32) * self.scales + self.mins
    
    def distance_int8(self, query_code: np.ndarray, codes: np.ndarray) -> np.ndarray:
        """SIMD-friendly INT8 distance computation."""
        # Use dot product approximation for cosine similarity
        # With AVX-512: process 64 dimensions per instruction
        diff = codes.astype(np.int16) - query_code.astype(np.int16)
        return np.sum(diff * diff, axis=1).astype(np.float32)
```

### Segment-based Storage Engine
```python
class SegmentManager:
    """
    LSM-tree inspired storage with segments.
    - Growing segment: in-memory, accepts writes
    - Sealed segments: immutable, on disk with HNSW index
    - Compaction merges small segments into larger ones
    """
    
    def __init__(self, collection_id: str, shard_id: int):
        self.collection_id = collection_id
        self.shard_id = shard_id
        self.growing_segment = GrowingSegment(max_size=100_000)
        self.sealed_segments: List[SealedSegment] = []
        self.wal = WriteAheadLog(f"{collection_id}/{shard_id}")
        
    def insert(self, vector_id: str, vector: np.ndarray, metadata: dict):
        # Write to WAL for durability
        self.wal.append(Operation.INSERT, vector_id, vector, metadata)
        
        # Insert into growing segment
        self.growing_segment.insert(vector_id, vector, metadata)
        
        # Seal and flush if full
        if self.growing_segment.is_full():
            self._seal_and_flush()
    
    def _seal_and_flush(self):
        """Convert growing segment to immutable sealed segment with index."""
        segment = self.growing_segment
        
        # Build HNSW index for the segment
        hnsw = HNSWIndex(dim=segment.dim, M=16, ef_construction=200)
        for vid, vec in segment.vectors.items():
            hnsw.insert(vid, vec)
        
        # Build metadata bitmap indexes
        bitmap_index = self._build_bitmap_indexes(segment.metadata)
        
        # Quantize vectors for memory efficiency
        pq = ProductQuantizer(dim=segment.dim, num_subvectors=48)
        pq.train(np.array(list(segment.vectors.values())))
        pq_codes = pq.encode(np.array(list(segment.vectors.values())))
        
        # Write to disk
        sealed = SealedSegment(
            segment_id=generate_id(),
            hnsw_index=hnsw,
            pq_index=pq,
            pq_codes=pq_codes,
            raw_vectors=segment.vectors,  # Memory-mapped file
            metadata=segment.metadata,
            bitmap_index=bitmap_index
        )
        self.sealed_segments.append(sealed)
        
        # Reset growing segment
        self.growing_segment = GrowingSegment(max_size=100_000)
        self.wal.truncate()
    
    def search(self, query: np.ndarray, k: int, filter_expr: dict = None) -> List:
        """Search across all segments, merge results."""
        all_results = []
        
        # Search growing segment (brute force, small)
        results = self.growing_segment.brute_force_search(query, k, filter_expr)
        all_results.extend(results)
        
        # Search each sealed segment
        for segment in self.sealed_segments:
            results = segment.search(query, k, filter_expr)
            all_results.extend(results)
        
        # Merge and return top-k across all segments
        all_results.sort(key=lambda x: x.distance)
        
        # Rescore top candidates with full precision vectors
        top_candidates = all_results[:k * 2]
        rescored = []
        for candidate in top_candidates:
            full_vec = self._get_full_vector(candidate.id)
            exact_dist = np.linalg.norm(query - full_vec)
            rescored.append((candidate.id, exact_dist))
        
        rescored.sort(key=lambda x: x[1])
        return rescored[:k]
```

## 8. Deep Dive: Distributed Architecture

### Sharding and Replication
```python
class ShardManager:
    """
    Shard vectors across nodes for horizontal scaling.
    Each shard is an independent search unit with its own index.
    """
    
    def __init__(self, num_shards: int, replication_factor: int = 3):
        self.num_shards = num_shards
        self.rf = replication_factor
        self.shard_map: Dict[int, List[str]] = {}  # shard_id -> [node_ids]
        
    def get_shard(self, vector_id: str) -> int:
        """Consistent hashing for shard assignment."""
        return mmh3.hash(vector_id) % self.num_shards
    
    def scatter_gather_search(self, query: np.ndarray, k: int, 
                               filter_expr: dict = None) -> List:
        """
        Query all shards in parallel, merge top-k results.
        Each shard returns its local top-k, coordinator merges.
        """
        # Fan out to all shards (pick one replica per shard)
        futures = []
        for shard_id in range(self.num_shards):
            node = self._select_replica(shard_id)  # Least-loaded replica
            future = self._async_query(node, shard_id, query, k, filter_expr)
            futures.append(future)
        
        # Gather results
        all_results = []
        for future in futures:
            shard_results = future.result(timeout=0.05)  # 50ms timeout
            all_results.extend(shard_results)
        
        # Global top-k merge
        all_results.sort(key=lambda x: x.distance)
        return all_results[:k]
    
    def rebalance(self, new_num_shards: int):
        """
        Online rebalancing: split shards that are too large.
        Uses virtual shards for minimal data movement.
        """
        # Identify oversized shards
        for shard_id in range(self.num_shards):
            shard_size = self._get_shard_size(shard_id)
            if shard_size > self.target_shard_size:
                self._split_shard(shard_id)


class ConsistencyManager:
    """
    Consistency for vector writes with index updates.
    Uses quorum writes with async index building.
    """
    
    def write_vector(self, collection_id: str, vector_id: str, 
                     vector: np.ndarray, metadata: dict):
        """
        Write path:
        1. Write to WAL on quorum of replicas (W=2 of RF=3)
        2. Apply to growing segment (searchable immediately)
        3. Ack to client
        4. Async: replicate to remaining replica
        """
        shard_id = self.shard_mgr.get_shard(vector_id)
        replicas = self.shard_mgr.shard_map[shard_id]
        
        # Quorum write
        write_quorum = (self.shard_mgr.rf // 2) + 1
        acks = 0
        
        for replica_node in replicas:
            try:
                self._write_to_replica(replica_node, vector_id, vector, metadata)
                acks += 1
                if acks >= write_quorum:
                    return True  # Success
            except Exception:
                continue
        
        raise WriteFailedException("Failed to achieve write quorum")
```

## 9. Production Configuration

### Deployment Configuration
```yaml
# Vector database cluster configuration
cluster:
  name: "vectordb-production"
  shards: 64
  replication_factor: 3
  
nodes:
  query_nodes:
    count: 50
    instance_type: "r6g.8xlarge"  # 256 GB RAM, ARM for efficiency
    storage: "io2"                # High IOPS EBS for segments
    storage_size_gb: 2000
  
  index_nodes:
    count: 10
    instance_type: "c6i.8xlarge"  # CPU-optimized for index building
    
  coordinator:
    count: 3
    instance_type: "m6i.2xlarge"

index_config:
  default_hnsw:
    M: 16
    ef_construction: 200
    ef_search: 128
  
  quantization:
    type: "scalar_int8"           # Default for balance of speed/quality
    rescore: true                 # Rescore top-100 with FP32
    rescore_multiplier: 10        # Fetch 10x candidates before rescoring

memory_management:
  mmap_enabled: true              # Memory-map sealed segments
  cache_size_gb: 200              # LRU cache for hot segments
  preload_collections: ["prod-embeddings", "search-index"]
  
compaction:
  strategy: "tiered"
  max_segment_size_mb: 1024
  min_segments_to_compact: 4
  compaction_threads: 4

wal:
  sync_mode: "fsync_per_batch"    # Batch fsync every 10ms
  max_wal_size_mb: 512
  retention_after_flush: "1h"

---
# Kubernetes deployment
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: vectordb-query
spec:
  replicas: 50
  template:
    spec:
      containers:
      - name: vectordb
        image: vectordb/query-node:3.2.1
        resources:
          requests:
            memory: "240Gi"
            cpu: "30"
          limits:
            memory: "256Gi"
            cpu: "32"
        env:
        - name: VECTORDB_CACHE_SIZE_GB
          value: "200"
        - name: VECTORDB_SEARCH_THREADS
          value: "28"
        - name: VECTORDB_SIMD
          value: "avx512"
        volumeMounts:
        - name: data
          mountPath: /data
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
      nodeSelector:
        node-type: "memory-optimized"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "io2-gp3"
      resources:
        requests:
          storage: 2000Gi
```

## 10. Failure Scenarios and Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Query node crash | Reduced QPS, some queries fail | Replica takes over queries for affected shards; client retries to different replica |
| Index corruption | Incorrect search results | Checksums on segments; rebuild index from raw vectors + WAL |
| Memory exhaustion | OOM kills query node | Mmap-based access (OS pages in/out), memory limits with backpressure |
| Network partition | Split-brain between replicas | Quorum reads/writes; partitioned minority stops serving reads |
| Slow disk I/O | Increased query latency | Prefetch segments, SSD with provisioned IOPS, circuit breaker |
| Compaction storm | CPU spike, latency increase | Rate-limit compaction threads, off-peak scheduling, I/O priority |
| Hot collection | Single tenant overwhelms shard | Auto-split hot shards, per-tenant rate limiting |
| WAL full | Writes rejected | Alert + auto-flush growing segment, increase WAL size |
| Stale replica | Inconsistent reads | Read repair on detection, anti-entropy background sync |
| Dimension mismatch | Query returns errors | Schema validation at ingestion, collection-level dimension lock |

## 11. Observability and Monitoring

### Key Metrics
```
┌─────────────────────────────────────────────────────────┐
│                   Observability Stack                     │
├──────────────┬────────────────┬─────────────────────────┤
│   Metrics    │    Traces      │      Dashboards         │
│              │                │                         │
│ - QPS        │ - Query path   │ - Recall vs latency    │
│ - p50/p99    │ - Shard fan-out│ - Index build progress │
│ - Recall     │ - Filter eval  │ - Memory usage/segment │
│ - Cache hit% │ - Rescore time │ - Write throughput     │
│ - Segment cnt│                │ - Compaction backlog   │
│ (Prometheus) │ (Jaeger)       │ (Grafana)              │
└──────────────┴────────────────┴─────────────────────────┘
```

### Performance Benchmarks
```
Index Type     | Recall@10 | Latency (p99) | Memory/Vector | Build Time
---------------|-----------|---------------|---------------|------------
HNSW (FP32)   | 0.99      | 2ms           | 4.5 KB        | Slow
HNSW (INT8)   | 0.97      | 1.5ms         | 1.2 KB        | Slow
IVF-PQ        | 0.92      | 3ms           | 64 B          | Fast
IVF-SQ        | 0.95      | 2.5ms         | 1 KB          | Medium
Binary         | 0.85      | 0.5ms         | 96 B          | Fast
Flat (brute)  | 1.00      | 50ms          | 3 KB          | None
```
