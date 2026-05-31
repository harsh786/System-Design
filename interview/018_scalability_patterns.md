# Scalability Patterns for AI Systems (Questions 86-90)

## Q86: Horizontally scalable RAG system from 1M to 10B documents

### Problem
Design a RAG system that scales 10,000x without architecture changes. At 1M docs you need fast iteration; at 10B docs you need distributed indexing, cost-effective storage, and sub-100ms retrieval.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scalable RAG Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Ingestion Pipeline (scales horizontally)                    │ │
│  │  Kafka → Chunker → Embedder → Indexer                      │ │
│  │  Throughput: 100K docs/hour per worker                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Storage Layer (tiered by access pattern)                    │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │ │
│  │  │ Hot Tier    │  │ Warm Tier   │  │ Cold Tier        │   │ │
│  │  │ <100M docs  │  │ 100M-1B    │  │ 1B-10B docs      │   │ │
│  │  │ In-memory   │  │ SSD-backed  │  │ Object store +   │   │ │
│  │  │ HNSW index  │  │ DiskANN     │  │ quantized index  │   │ │
│  │  │ p99: 5ms    │  │ p99: 20ms   │  │ p99: 50ms        │   │ │
│  │  │ $50/M docs  │  │ $5/M docs   │  │ $0.50/M docs     │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Query Layer                                                 │ │
│  │  Query → Embed → Route to shards → Scatter-Gather → Rerank│ │
│  │                                                             │ │
│  │  Sharding: hash(tenant_id) for multi-tenant                │ │
│  │            hash(doc_id % N) for single-tenant               │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import hashlib
import numpy as np

class StorageTier(Enum):
    HOT = "hot"      # In-memory HNSW
    WARM = "warm"    # SSD-based DiskANN
    COLD = "cold"    # Object store + PQ-compressed

@dataclass
class ScaleConfig:
    """Configuration that adapts to current scale."""
    total_docs: int
    num_shards: int
    replication_factor: int
    index_type: str
    quantization: str
    
    @classmethod
    def for_scale(cls, doc_count: int) -> 'ScaleConfig':
        """Auto-configure based on document count."""
        if doc_count < 10_000_000:  # <10M
            return cls(
                total_docs=doc_count,
                num_shards=max(1, doc_count // 1_000_000),
                replication_factor=2,
                index_type="HNSW",
                quantization="none"  # Full FP32 embeddings
            )
        elif doc_count < 1_000_000_000:  # <1B
            return cls(
                total_docs=doc_count,
                num_shards=doc_count // 5_000_000,  # 5M per shard
                replication_factor=2,
                index_type="DiskANN",
                quantization="SQ8"  # Scalar quantization
            )
        else:  # 1B+
            return cls(
                total_docs=doc_count,
                num_shards=doc_count // 10_000_000,  # 10M per shard
                replication_factor=3,
                index_type="IVF_PQ",
                quantization="PQ64"  # Product quantization to 64 bytes
            )


class ShardRouter:
    """Routes queries to appropriate shards using scatter-gather."""
    
    def __init__(self, config: ScaleConfig):
        self.config = config
        self.shard_map: Dict[int, List[str]] = {}  # shard_id → [node_addresses]
    
    def get_target_shards(self, query_embedding: np.ndarray, 
                          tenant_id: Optional[str] = None,
                          top_k: int = 10) -> List[int]:
        """Determine which shards to query."""
        if tenant_id:
            # Tenant-scoped: only query tenant's shards
            shard_id = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16) % self.config.num_shards
            return [shard_id]
        
        if self.config.num_shards <= 10:
            # Small scale: query all shards
            return list(range(self.config.num_shards))
        
        # Large scale: use coarse quantizer to identify promising shards
        # Each shard has a centroid; find nearest centroids
        num_shards_to_query = min(
            max(3, self.config.num_shards // 10),  # Query ~10% of shards
            20  # Cap at 20 shards
        )
        return self._find_nearest_shards(query_embedding, num_shards_to_query)
    
    def _find_nearest_shards(self, query: np.ndarray, k: int) -> List[int]:
        """Find shards most likely to contain relevant docs."""
        # Pre-computed shard centroids (updated hourly)
        # This is essentially IVF's coarse quantizer at shard level
        return list(range(k))  # Placeholder


class ScalableRAGEngine:
    """RAG engine that works from 1M to 10B documents."""
    
    def __init__(self, doc_count: int):
        self.config = ScaleConfig.for_scale(doc_count)
        self.router = ShardRouter(self.config)
        self.merger = ResultMerger()
    
    async def retrieve(self, query: str, top_k: int = 10, 
                       tenant_id: Optional[str] = None) -> List[dict]:
        """Scatter-gather retrieval across shards."""
        # 1. Embed query
        query_embedding = await self._embed_query(query)
        
        # 2. Determine target shards
        target_shards = self.router.get_target_shards(
            query_embedding, tenant_id, top_k
        )
        
        # 3. Scatter: query all target shards in parallel
        shard_results = await asyncio.gather(*[
            self._query_shard(shard_id, query_embedding, top_k * 2)
            for shard_id in target_shards
        ])
        
        # 4. Gather: merge and re-rank results
        merged = self.merger.merge(shard_results, top_k)
        
        # 5. Optional: cross-encoder reranking on top candidates
        if len(merged) > top_k:
            merged = await self._rerank(query, merged, top_k)
        
        return merged
    
    async def _query_shard(self, shard_id: int, query_embedding: np.ndarray, 
                           top_k: int) -> List[dict]:
        """Query a single shard. Implementation depends on tier."""
        # The shard handles its own index type (HNSW/DiskANN/IVF_PQ)
        pass
    
    async def _rerank(self, query: str, candidates: List[dict], 
                      top_k: int) -> List[dict]:
        """Cross-encoder reranking for precision."""
        # Only rerank top 2*k candidates (expensive)
        scores = await cross_encoder_score(query, [c["text"] for c in candidates[:top_k*2]])
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:top_k]]


class IndexManager:
    """Manages index lifecycle: build, compact, migrate between tiers."""
    
    def __init__(self):
        self.tier_thresholds = {
            StorageTier.HOT: 100_000_000,    # Up to 100M in memory
            StorageTier.WARM: 1_000_000_000,  # Up to 1B on SSD
            StorageTier.COLD: float('inf'),   # Everything else
        }
    
    async def rebalance(self, shard_stats: Dict[int, dict]):
        """Move data between tiers based on access patterns."""
        for shard_id, stats in shard_stats.items():
            # Hot → Warm: if shard not queried in 1 hour
            if stats["last_query_age"] > 3600 and stats["current_tier"] == StorageTier.HOT:
                await self._migrate_shard(shard_id, StorageTier.HOT, StorageTier.WARM)
            
            # Warm → Hot: if query rate > 10/min
            if stats["query_rate_per_min"] > 10 and stats["current_tier"] == StorageTier.WARM:
                await self._migrate_shard(shard_id, StorageTier.WARM, StorageTier.HOT)
    
    async def _migrate_shard(self, shard_id: int, from_tier: StorageTier, to_tier: StorageTier):
        """Migrate shard between tiers with zero downtime."""
        # 1. Build new index in target tier
        # 2. Dual-read from both during migration
        # 3. Switch reads to new tier
        # 4. Delete old tier data
        pass
```

### Cost Model by Scale

| Scale | Shards | Storage Cost/mo | Compute Cost/mo | p99 Retrieval | Index Type |
|-------|--------|----------------|-----------------|---------------|------------|
| 1M | 1 | $50 | $200 | 5ms | HNSW (RAM) |
| 10M | 4 | $500 | $800 | 8ms | HNSW (RAM) |
| 100M | 20 | $2,000 | $4,000 | 15ms | HNSW + DiskANN |
| 1B | 200 | $8,000 | $15,000 | 30ms | DiskANN |
| 10B | 1000 | $25,000 | $50,000 | 60ms | IVF_PQ + DiskANN |

### Production Considerations

- **Shard splitting**: When a shard exceeds 10M docs, split it. Use consistent hashing to minimize data movement.
- **Compaction**: Dead/deleted documents accumulate. Compact indexes weekly (rebuild without deleted docs).
- **Embedding versioning**: When you upgrade embedding model, you need to re-embed everything. Do rolling migration: new docs get new embeddings, old docs re-embedded in background over days.
- **Query fan-out budget**: At 1000 shards, querying all is impossible. Coarse routing must be accurate or recall drops.
- **Monitoring**: Track recall@10 with golden queries. If recall drops below 0.9 after scaling changes, investigate.

---

## Q87: Multi-model serving platform for 50+ models on shared GPU infrastructure

### Problem
Your platform serves 50+ models: 5 LLMs (7B-70B), 10 embedding models, 20 classifiers, 15 specialized models. All share a GPU cluster. Design efficient multiplexing with per-model SLAs.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Multi-Model Serving Platform                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Model Registry & Scheduler                                  │  │
│  │  - 50+ model definitions (size, SLA, priority)              │  │
│  │  - Placement decisions: which model on which GPU            │  │
│  │  - Auto-scaling per model                                   │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ GPU Cluster (32x A100 80GB)                                 │  │
│  │                                                              │  │
│  │  Strategy: Model Packing                                    │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ GPU 0-3: Llama-70B (4-GPU tensor parallel)          │   │  │
│  │  │ GPU 4-5: Llama-7B (2 replicas, 1 GPU each)         │   │  │
│  │  │ GPU 6: Embedding-large + Classifier-A + Classifier-B│   │  │
│  │  │ GPU 7: Embedding-small × 3 (multi-instance)         │   │  │
│  │  │ GPU 8-11: Reserved for burst / overflow             │   │  │
│  │  │ ...                                                  │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Request Router                                              │  │
│  │  model_name → active endpoints → load-balanced selection    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
import heapq

@dataclass
class ModelSpec:
    model_id: str
    name: str
    size_gb: float           # GPU memory required
    min_replicas: int        # Minimum always-loaded replicas
    max_replicas: int
    sla_latency_ms: float    # p99 target
    sla_availability: float  # e.g., 0.999
    priority: int            # 0=highest
    can_share_gpu: bool      # Can co-locate with other models
    load_time_seconds: float # Time to load into GPU memory
    requests_per_second: float  # Current traffic

@dataclass
class GPUNode:
    gpu_id: str
    total_memory_gb: float = 80.0
    used_memory_gb: float = 0.0
    loaded_models: List[str] = field(default_factory=list)
    
    @property
    def free_memory_gb(self) -> float:
        return self.total_memory_gb - self.used_memory_gb

class ModelPlacementScheduler:
    """Bin-packing scheduler for multi-model GPU placement."""
    
    def __init__(self, gpus: List[GPUNode], models: List[ModelSpec]):
        self.gpus = {g.gpu_id: g for g in gpus}
        self.models = {m.model_id: m for m in models}
        self.placements: Dict[str, List[str]] = {}  # model_id → [gpu_ids]
    
    def compute_placement(self) -> Dict[str, List[str]]:
        """Solve model placement using priority-aware bin packing."""
        placements = {}
        
        # Sort models: large models first (harder to place), then by priority
        sorted_models = sorted(
            self.models.values(),
            key=lambda m: (-m.size_gb, m.priority)
        )
        
        for model in sorted_models:
            placed_gpus = self._place_model(model)
            if placed_gpus:
                placements[model.model_id] = placed_gpus
            else:
                # Can't place: need to evict or alert
                self._handle_placement_failure(model)
        
        return placements
    
    def _place_model(self, model: ModelSpec) -> List[str]:
        """Place model replicas on GPUs."""
        placed = []
        
        for _ in range(model.min_replicas):
            gpu = self._find_best_gpu(model)
            if gpu:
                gpu.used_memory_gb += model.size_gb
                gpu.loaded_models.append(model.model_id)
                placed.append(gpu.gpu_id)
            else:
                break
        
        return placed
    
    def _find_best_gpu(self, model: ModelSpec) -> Optional[GPUNode]:
        """Find optimal GPU for this model."""
        candidates = []
        
        for gpu in self.gpus.values():
            if gpu.free_memory_gb < model.size_gb:
                continue
            
            if not model.can_share_gpu and gpu.loaded_models:
                continue
            
            # Score: prefer GPUs that minimize wasted memory (bin packing)
            waste = gpu.free_memory_gb - model.size_gb
            # Prefer co-locating small models together
            affinity_bonus = 0
            if model.can_share_gpu and gpu.loaded_models:
                affinity_bonus = 10  # Prefer consolidation
            
            score = -waste + affinity_bonus
            candidates.append((score, gpu))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def _handle_placement_failure(self, model: ModelSpec):
        """When we can't place a model, evict lower priority."""
        # Find lowest priority model that frees enough memory
        pass


class ModelAutoScaler:
    """Per-model auto-scaling within shared GPU pool."""
    
    def __init__(self, scheduler: ModelPlacementScheduler):
        self.scheduler = scheduler
        self.metrics: Dict[str, dict] = {}  # model_id → metrics
    
    def evaluate_scaling(self) -> List[dict]:
        """Determine which models need more/fewer replicas."""
        actions = []
        
        for model_id, model in self.scheduler.models.items():
            metrics = self.metrics.get(model_id, {})
            current_replicas = len(self.scheduler.placements.get(model_id, []))
            
            # Scale up if latency SLA is being violated
            p99_latency = metrics.get("p99_latency_ms", 0)
            if p99_latency > model.sla_latency_ms * 0.8:
                if current_replicas < model.max_replicas:
                    actions.append({
                        "action": "scale_up",
                        "model_id": model_id,
                        "reason": f"p99={p99_latency}ms > {model.sla_latency_ms*0.8}ms threshold"
                    })
            
            # Scale down if heavily underutilized
            utilization = metrics.get("gpu_utilization", 0)
            if utilization < 0.2 and current_replicas > model.min_replicas:
                actions.append({
                    "action": "scale_down",
                    "model_id": model_id,
                    "reason": f"utilization={utilization:.0%} < 20%"
                })
        
        return actions


class ModelSwapper:
    """Handles model loading/unloading for dynamic scheduling."""
    
    def __init__(self):
        self.swap_history: List[dict] = []
    
    async def swap_model(self, gpu_id: str, unload_model: str, load_model: str):
        """Swap models on a GPU with minimal disruption."""
        # 1. Drain traffic from model being unloaded
        await self._drain_traffic(gpu_id, unload_model, timeout_s=30)
        
        # 2. Unload from GPU memory
        await self._unload_model(gpu_id, unload_model)
        
        # 3. Load new model (from local NVMe cache if available)
        await self._load_model(gpu_id, load_model)
        
        # 4. Warm up with test request
        await self._warmup(gpu_id, load_model)
        
        # 5. Route traffic to new model
        await self._enable_traffic(gpu_id, load_model)
    
    async def _drain_traffic(self, gpu_id: str, model_id: str, timeout_s: float):
        """Stop new requests, wait for in-flight to complete."""
        pass
    
    async def _unload_model(self, gpu_id: str, model_id: str):
        """Free GPU memory."""
        pass
    
    async def _load_model(self, gpu_id: str, model_id: str):
        """Load model weights into GPU memory."""
        pass
    
    async def _warmup(self, gpu_id: str, model_id: str):
        """Run test inference to warm caches."""
        pass
    
    async def _enable_traffic(self, gpu_id: str, model_id: str):
        """Register endpoint for traffic routing."""
        pass
```

### GPU Memory Budget Example (32x A100 80GB = 2560GB total)

| Model Category | Models | Per-Model Size | Replicas | Total GPU Memory |
|---------------|--------|---------------|----------|-----------------|
| Large LLMs (70B) | 2 | 140GB (4-GPU TP) | 2 each | 1120GB |
| Medium LLMs (7B) | 3 | 14GB | 3 each | 126GB |
| Embedding models | 10 | 2GB | 2 each | 40GB |
| Classifiers | 20 | 1GB | 2 each | 40GB |
| Specialized | 15 | 4GB | 2 each | 120GB |
| **Total** | **50** | | | **1446GB** |
| **Buffer (burst)** | | | | **1114GB** |

### Production Considerations

- **Interference**: Co-located models on same GPU compete for memory bandwidth. Benchmark co-location pairs and avoid bad combinations.
- **Model preloading**: Keep top-20 models by traffic always loaded. Swap bottom-30 based on time-of-day patterns.
- **Graceful degradation**: If a model can't be placed, route to API fallback (OpenAI/Anthropic) rather than failing.
- **Resource quotas**: Teams requesting new models must specify expected QPS. Platform validates GPU capacity before approval.
- **Version management**: Support multiple versions simultaneously during canary deployments. Each version is a separate "model" for placement purposes.

---

## Q88: Scalable feature store for real-time AI with 1M lookups/sec at <5ms

### Problem
Your AI applications need features computed from user behavior, item properties, and real-time signals. Design a feature store handling 1M point lookups per second with <5ms p99 latency, supporting both batch (training) and online (inference) access.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Scalable Feature Store                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Feature Computation Layer                                   │ │
│  │                                                             │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │ │
│  │  │ Batch Features│  │ Streaming     │  │ On-Demand    │  │ │
│  │  │ (Spark, daily)│  │ (Flink, <1min)│  │ (at request) │  │ │
│  │  │ user_history  │  │ session_count │  │ embedding    │  │ │
│  │  │ aggregations  │  │ real_time_ctr │  │ similarity   │  │ │
│  │  └───────┬───────┘  └───────┬───────┘  └──────┬───────┘  │ │
│  │          │                   │                  │           │ │
│  └──────────┼───────────────────┼──────────────────┼───────────┘ │
│             ▼                   ▼                  ▼              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Online Store (Redis Cluster, 1M reads/sec)                  │ │
│  │  - 100 nodes, 6.4TB RAM total                               │ │
│  │  - Key: entity_id | Value: feature_vector (protobuf)        │ │
│  │  - TTL-based expiration per feature group                   │ │
│  │  - Read replicas for throughput                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│             │                                                     │
│             ▼                                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Offline Store (Delta Lake / Parquet on S3)                  │ │
│  │  - Point-in-time correct feature snapshots                  │ │
│  │  - Used for training data generation                        │ │
│  │  - Partitioned by date + entity_type                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import hashlib
import struct
import numpy as np

@dataclass
class FeatureDefinition:
    name: str
    entity_type: str        # "user", "item", "session"
    value_type: str         # "float", "vector", "string"
    computation: str        # "batch", "streaming", "on_demand"
    ttl_seconds: int        # Freshness requirement
    default_value: Any      # Returned on cache miss
    sla_latency_ms: float = 5.0

@dataclass
class FeatureVector:
    entity_id: str
    features: Dict[str, Any]
    computed_at: float
    version: int

class OnlineFeatureStore:
    """High-throughput feature serving layer."""
    
    def __init__(self, redis_cluster, feature_registry: Dict[str, FeatureDefinition]):
        self.redis = redis_cluster
        self.registry = feature_registry
        self.local_cache = LRUCache(max_size=100_000)  # L1: process-local
        self.batch_buffer = BatchBuffer(max_size=64, max_wait_ms=2)
    
    async def get_features(self, entity_id: str, 
                           feature_names: List[str]) -> Dict[str, Any]:
        """Get features for a single entity. Target: <5ms p99."""
        # L1: Local LRU cache (sub-ms)
        cache_key = f"{entity_id}:{','.join(sorted(feature_names))}"
        cached = self.local_cache.get(cache_key)
        if cached:
            return cached
        
        # L2: Redis cluster (1-3ms)
        result = await self._redis_multiget(entity_id, feature_names)
        
        # Fill defaults for missing features
        for fname in feature_names:
            if fname not in result:
                defn = self.registry[fname]
                result[fname] = defn.default_value
        
        # Populate L1 cache
        self.local_cache.set(cache_key, result, ttl=1.0)  # 1s local TTL
        
        return result
    
    async def get_features_batch(self, entity_ids: List[str],
                                  feature_names: List[str]) -> List[Dict[str, Any]]:
        """Batch get for multiple entities. Uses pipelining."""
        # Redis pipeline: single round-trip for all entities
        pipeline = self.redis.pipeline()
        
        keys = []
        for entity_id in entity_ids:
            for fname in feature_names:
                key = f"feat:{self.registry[fname].entity_type}:{entity_id}:{fname}"
                pipeline.get(key)
                keys.append((entity_id, fname))
        
        results_raw = await pipeline.execute()
        
        # Reconstruct per-entity feature dicts
        results = [{} for _ in entity_ids]
        for idx, (entity_id, fname) in enumerate(keys):
            entity_idx = entity_ids.index(entity_id)
            value = self._deserialize(results_raw[idx], self.registry[fname].value_type)
            if value is not None:
                results[entity_idx][fname] = value
            else:
                results[entity_idx][fname] = self.registry[fname].default_value
        
        return results
    
    async def _redis_multiget(self, entity_id: str, 
                               feature_names: List[str]) -> Dict[str, Any]:
        """Multi-key get from Redis."""
        keys = [
            f"feat:{self.registry[fn].entity_type}:{entity_id}:{fn}"
            for fn in feature_names
        ]
        values = await self.redis.mget(keys)
        
        result = {}
        for fname, value in zip(feature_names, values):
            if value is not None:
                result[fname] = self._deserialize(value, self.registry[fname].value_type)
        return result
    
    def _deserialize(self, raw: Optional[bytes], value_type: str) -> Any:
        if raw is None:
            return None
        if value_type == "float":
            return struct.unpack('f', raw)[0]
        elif value_type == "vector":
            return np.frombuffer(raw, dtype=np.float32)
        elif value_type == "string":
            return raw.decode('utf-8')
        return raw


class StreamingFeatureComputer:
    """Computes real-time features from event streams."""
    
    def __init__(self, online_store: OnlineFeatureStore):
        self.store = online_store
        self.windows: Dict[str, dict] = {}  # Sliding window state
    
    async def process_event(self, event: dict):
        """Process real-time event, update features."""
        entity_id = event["user_id"]
        event_type = event["type"]
        
        # Update sliding window aggregations
        window_key = f"{entity_id}:{event_type}"
        if window_key not in self.windows:
            self.windows[window_key] = {
                "count_1min": 0, "count_5min": 0, "count_1hr": 0,
                "last_event_time": 0
            }
        
        window = self.windows[window_key]
        window["count_1min"] += 1
        window["count_5min"] += 1
        window["count_1hr"] += 1
        window["last_event_time"] = event["timestamp"]
        
        # Write computed features to online store
        features = {
            f"{event_type}_count_1min": window["count_1min"],
            f"{event_type}_count_5min": window["count_5min"],
            f"last_{event_type}_seconds_ago": time.time() - event["timestamp"],
        }
        
        await self._write_features(entity_id, features)
    
    async def _write_features(self, entity_id: str, features: Dict[str, Any]):
        """Write features to Redis with appropriate TTLs."""
        pipeline = self.store.redis.pipeline()
        for fname, value in features.items():
            key = f"feat:user:{entity_id}:{fname}"
            serialized = struct.pack('f', float(value))
            defn = self.store.registry.get(fname)
            ttl = defn.ttl_seconds if defn else 300
            pipeline.setex(key, ttl, serialized)
        await pipeline.execute()


class FeatureConsistencyChecker:
    """Ensures online/offline feature parity (training-serving skew detection)."""
    
    async def check_skew(self, entity_id: str, feature_name: str) -> dict:
        """Compare online value with offline computation."""
        online_value = await online_store.get_features(entity_id, [feature_name])
        offline_value = await offline_store.get_feature(entity_id, feature_name, 
                                                        timestamp=time.time())
        
        skew = abs(online_value.get(feature_name, 0) - offline_value)
        return {
            "feature": feature_name,
            "online": online_value.get(feature_name),
            "offline": offline_value,
            "skew": skew,
            "alert": skew > 0.1  # >10% skew is concerning
        }
```

### Scaling Numbers

| Metric | Value | How Achieved |
|--------|-------|--------------|
| Read throughput | 1M/sec | 100-node Redis cluster, 10K/sec per node |
| p50 latency | 1.2ms | Local cache hits + Redis single-hop |
| p99 latency | 4.5ms | Pipeline batching, read replicas |
| Feature freshness | <60s | Flink streaming computation |
| Storage | 6.4TB | 100 nodes × 64GB RAM |
| Entities | 500M users + 100M items | Sharded by entity_id |

### Production Considerations

- **Training-serving skew**: The #1 ML production bug. Feature store must guarantee same computation logic offline and online. Use shared feature definitions.
- **Point-in-time correctness**: When generating training data, features must reflect what was available at prediction time, not current values. Offline store maintains temporal snapshots.
- **Feature freshness SLAs**: Some features (user_last_click) must be <10s fresh. Others (user_lifetime_value) can be 24h stale. TTL enforcement prevents serving stale data.
- **Graceful degradation**: If Redis is slow, serve defaults. A model with some default features is better than a timeout.
- **Cost optimization**: Move cold entities (inactive users) from Redis to DynamoDB. Lazy-load back on first access.

---

## Q89: Scalable evaluation pipeline for 10M AI responses/day

### Problem
You need to assess quality of AI-generated content across accuracy, safety, helpfulness, and more. Volume: 10M responses/day. Each needs multi-dimensional scoring. Design for throughput, consistency, and actionability.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Scalable Evaluation Pipeline                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Ingestion (Kafka, 10M events/day ≈ 115/sec)                │  │
│  │  {request, response, context, metadata}                     │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                        │
│                           ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Sampling & Routing Layer                                    │  │
│  │  - 100% → Fast evaluators (heuristic, classifier)           │  │
│  │  - 10% → LLM-as-judge evaluation                           │  │
│  │  - 1% → Human evaluation queue                              │  │
│  └──────────┬──────────────────┬───────────────┬──────────────┘  │
│             │                  │               │                   │
│             ▼                  ▼               ▼                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Fast Evals   │  │ LLM Judge    │  │ Human Eval Queue     │   │
│  │ (all 10M)    │  │ (1M/day)     │  │ (100K/day)           │   │
│  │              │  │              │  │                       │   │
│  │ - Toxicity   │  │ - Accuracy   │  │ - Calibration        │   │
│  │ - Length     │  │ - Helpfulness│  │ - Edge cases         │   │
│  │ - Format     │  │ - Coherence  │  │ - Policy violations  │   │
│  │ - Regex      │  │ - Reasoning  │  │                       │   │
│  │              │  │              │  │                       │   │
│  │ Latency: 5ms│  │ Latency: 2s  │  │ Latency: hours       │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                  │                      │                │
│         ▼                  ▼                      ▼                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Score Aggregation & Storage (ClickHouse)                    │  │
│  │  - Per-response scores across dimensions                    │  │
│  │  - Real-time dashboards                                     │  │
│  │  - Alerting on quality drops                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import time
import random

class EvalDimension(Enum):
    ACCURACY = "accuracy"
    SAFETY = "safety"
    HELPFULNESS = "helpfulness"
    COHERENCE = "coherence"
    FORMAT_COMPLIANCE = "format"
    GROUNDEDNESS = "groundedness"

@dataclass
class EvalResult:
    dimension: EvalDimension
    score: float          # 0.0 - 1.0
    confidence: float     # How confident is this eval
    evaluator: str        # Which evaluator produced this
    reasoning: Optional[str] = None
    latency_ms: float = 0.0

@dataclass
class ResponseToEval:
    response_id: str
    query: str
    response: str
    context: Optional[str]    # RAG context provided
    model: str
    timestamp: float
    metadata: dict = field(default_factory=dict)

class EvaluationPipeline:
    """Orchestrates multi-tier evaluation at scale."""
    
    def __init__(self):
        self.fast_evaluators = [
            ToxicityClassifier(),
            FormatChecker(),
            LengthChecker(),
            GroundednessHeuristic(),
        ]
        self.llm_judge = LLMJudge()
        self.human_queue = HumanEvalQueue()
        self.storage = EvalStorage()
        
        # Sampling rates
        self.llm_sample_rate = 0.10   # 10% get LLM judging
        self.human_sample_rate = 0.01  # 1% get human review
    
    async def evaluate(self, response: ResponseToEval):
        """Full evaluation pipeline for one response."""
        results: List[EvalResult] = []
        
        # Tier 1: Fast evaluators (ALL responses, <10ms)
        fast_results = await asyncio.gather(*[
            evaluator.evaluate(response) 
            for evaluator in self.fast_evaluators
        ])
        results.extend(fast_results)
        
        # Check if fast evals flagged anything critical
        critical_flag = any(r.score < 0.3 for r in fast_results if r.dimension == EvalDimension.SAFETY)
        
        # Tier 2: LLM Judge (sampled OR flagged)
        if critical_flag or random.random() < self.llm_sample_rate:
            llm_results = await self.llm_judge.evaluate(response)
            results.extend(llm_results)
        
        # Tier 3: Human eval (sampled from interesting cases)
        if self._should_human_eval(response, results):
            await self.human_queue.enqueue(response, results)
        
        # Store all results
        await self.storage.store(response.response_id, results)
        
        # Real-time alerting
        await self._check_alerts(response, results)
    
    def _should_human_eval(self, response: ResponseToEval, 
                           results: List[EvalResult]) -> bool:
        """Smart sampling for human eval - focus on uncertain/borderline cases."""
        # Always: critical safety flags
        if any(r.score < 0.3 and r.dimension == EvalDimension.SAFETY for r in results):
            return True
        
        # Borderline cases (evaluators disagree or low confidence)
        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 1.0
        if avg_confidence < 0.6:
            return True
        
        # Random sample for calibration
        return random.random() < self.human_sample_rate
    
    async def _check_alerts(self, response: ResponseToEval, results: List[EvalResult]):
        """Real-time quality alerting."""
        for result in results:
            if result.score < 0.2:  # Critical quality failure
                await alert_oncall(
                    severity="high",
                    message=f"Quality alert: {result.dimension.value} score={result.score:.2f}",
                    response_id=response.response_id,
                    model=response.model
                )


class LLMJudge:
    """Uses LLM to evaluate response quality across dimensions."""
    
    JUDGE_PROMPT = """Evaluate this AI response on a scale of 1-5 for each dimension.

Query: {query}
Context provided: {context}
Response: {response}

Rate each dimension (1=terrible, 5=excellent):
1. Accuracy: Is the information factually correct?
2. Helpfulness: Does it answer what was asked?
3. Coherence: Is it well-structured and clear?
4. Groundedness: Is it supported by the provided context?

Output JSON: {{"accuracy": N, "helpfulness": N, "coherence": N, "groundedness": N, "reasoning": "..."}}"""
    
    def __init__(self):
        self.judge_model = "gpt-4"  # Use strong model as judge
        self.batch_size = 16  # Batch judge calls for efficiency
    
    async def evaluate(self, response: ResponseToEval) -> List[EvalResult]:
        prompt = self.JUDGE_PROMPT.format(
            query=response.query,
            context=response.context or "None provided",
            response=response.response
        )
        
        start = time.time()
        judgment = await call_llm(self.judge_model, prompt, max_tokens=200)
        latency = (time.time() - start) * 1000
        
        # Parse JSON response
        scores = parse_json(judgment)
        
        results = []
        for dimension, score in scores.items():
            if dimension == "reasoning":
                continue
            results.append(EvalResult(
                dimension=EvalDimension(dimension),
                score=score / 5.0,  # Normalize to 0-1
                confidence=0.8,  # LLM judge confidence
                evaluator="gpt-4-judge",
                reasoning=scores.get("reasoning"),
                latency_ms=latency
            ))
        
        return results


class QualityDashboard:
    """Aggregates eval results into actionable metrics."""
    
    async def get_model_quality_report(self, model: str, 
                                        time_range_hours: int = 24) -> dict:
        """Quality report for a specific model."""
        # Query ClickHouse for aggregated scores
        query = f"""
        SELECT 
            dimension,
            avg(score) as avg_score,
            quantile(0.05)(score) as p5_score,
            count() as eval_count,
            countIf(score < 0.3) as critical_count
        FROM eval_results
        WHERE model = '{model}' 
            AND timestamp > now() - INTERVAL {time_range_hours} HOUR
        GROUP BY dimension
        """
        return await self.storage.query(query)
    
    async def detect_quality_regression(self, model: str) -> Optional[dict]:
        """Compare last hour vs last 24h average."""
        recent = await self.get_model_quality_report(model, time_range_hours=1)
        baseline = await self.get_model_quality_report(model, time_range_hours=24)
        
        regressions = []
        for dim in EvalDimension:
            recent_score = recent.get(dim.value, {}).get("avg_score", 0)
            baseline_score = baseline.get(dim.value, {}).get("avg_score", 0)
            
            if baseline_score > 0 and (baseline_score - recent_score) / baseline_score > 0.05:
                regressions.append({
                    "dimension": dim.value,
                    "drop": f"{(baseline_score - recent_score)*100:.1f}%",
                    "current": recent_score,
                    "baseline": baseline_score
                })
        
        return {"regressions": regressions} if regressions else None
```

### Throughput Design

| Eval Tier | Volume | Compute | Latency | Cost/day |
|-----------|--------|---------|---------|----------|
| Fast classifiers | 10M/day | 20 CPU cores | 5ms | $50 |
| LLM Judge | 1M/day | GPT-4 API | 2s | $5,000 |
| Human eval | 100K/day | Crowd workers | 2-24h | $10,000 |
| **Total** | **10M/day** | | | **~$15,000/day** |

### Production Considerations

- **Judge calibration**: LLM judges have biases (verbosity bias, position bias). Calibrate against human judgments monthly. Adjust prompts if drift detected.
- **Cost management**: LLM judging at 10% sampling costs $5K/day. If budget-constrained, reduce to 5% but maintain stratified sampling (more samples from new models/prompts).
- **Feedback loop**: Evaluation results should feed back into model fine-tuning. Low-scoring responses are negative examples; high-scoring are positive examples.
- **Consistency**: Same response evaluated twice should get similar scores. Track inter-rater reliability for LLM judge (should be >0.8 Cohen's kappa).
- **Latency for blocking evals**: Safety evaluation must be synchronous (block response delivery). Quality evals can be async.

---

## Q90: Scalable prompt management for 500 teams

### Problem
500 teams each have 10-50 prompt templates with versions, A/B tests, and approval workflows. Design a system that prevents prompt chaos while enabling rapid iteration.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Enterprise Prompt Management System                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Prompt Registry (Git-backed, versioned)                     │  │
│  │                                                              │  │
│  │  /org/team-a/prompts/                                       │  │
│  │    ├── summarizer/                                          │  │
│  │    │   ├── v1.yaml (production)                             │  │
│  │    │   ├── v2.yaml (canary: 10%)                            │  │
│  │    │   └── v3.yaml (draft)                                  │  │
│  │    ├── classifier/                                          │  │
│  │    │   └── v1.yaml                                          │  │
│  │    └── ...                                                  │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Prompt Serving Layer (low-latency, cached)                  │  │
│  │  - Redis cache of active prompts (< 1ms lookup)             │  │
│  │  - A/B test traffic splitting                               │  │
│  │  - Variable interpolation                                   │  │
│  │  - Guardrail enforcement                                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Governance Layer                                            │  │
│  │  - Approval workflows (safety review for prompts)           │  │
│  │  - Audit trail (who changed what, when)                     │  │
│  │  - Policy enforcement (no PII in prompts, length limits)    │  │
│  │  - Cross-team prompt sharing & discovery                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import yaml
import random

class PromptStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    CANARY = "canary"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"

@dataclass
class PromptVersion:
    prompt_id: str
    version: int
    team_id: str
    template: str            # The actual prompt template with {variables}
    model: str               # Target model
    parameters: dict         # temperature, max_tokens, etc.
    status: PromptStatus
    traffic_percentage: float  # 0-100, for A/B testing
    created_by: str
    created_at: float
    approved_by: Optional[str] = None
    metrics: dict = field(default_factory=dict)  # Quality scores
    
    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]

@dataclass
class PromptExperiment:
    experiment_id: str
    prompt_id: str
    variants: List[PromptVersion]  # Each with traffic_percentage
    start_time: float
    end_time: Optional[float]
    success_metric: str  # "user_satisfaction", "task_completion", etc.
    min_sample_size: int = 1000

class PromptRegistry:
    """Central registry for all prompts across 500 teams."""
    
    def __init__(self):
        self.prompts: Dict[str, Dict[int, PromptVersion]] = {}  # prompt_id → {version → prompt}
        self.experiments: Dict[str, PromptExperiment] = {}
        self.serving_cache = {}  # prompt_id → resolved active version(s)
    
    def register_prompt(self, prompt: PromptVersion) -> str:
        """Register a new prompt version."""
        # Validate
        self._validate_prompt(prompt)
        
        if prompt.prompt_id not in self.prompts:
            self.prompts[prompt.prompt_id] = {}
        
        self.prompts[prompt.prompt_id][prompt.version] = prompt
        return prompt.prompt_id
    
    def _validate_prompt(self, prompt: PromptVersion):
        """Enforce organizational policies."""
        # No PII patterns in template
        pii_patterns = [r'\b\d{3}-\d{2}-\d{4}\b', r'password', r'api_key']
        for pattern in pii_patterns:
            if pattern in prompt.template.lower():
                raise PolicyViolation(f"Prompt contains PII pattern: {pattern}")
        
        # Length limits
        if len(prompt.template) > 10000:
            raise PolicyViolation("Prompt exceeds 10K character limit")
        
        # Must have at least one variable (prevents hardcoded prompts)
        if '{' not in prompt.template:
            pass  # Warning, not blocking
    
    def promote_to_production(self, prompt_id: str, version: int, 
                              approved_by: str) -> bool:
        """Promote a prompt to production (requires approval)."""
        prompt = self.prompts[prompt_id][version]
        
        if prompt.status not in [PromptStatus.APPROVED, PromptStatus.CANARY]:
            raise WorkflowError("Prompt must be approved before production")
        
        # Demote current production version
        for v, p in self.prompts[prompt_id].items():
            if p.status == PromptStatus.PRODUCTION:
                p.status = PromptStatus.DEPRECATED
        
        prompt.status = PromptStatus.PRODUCTION
        prompt.traffic_percentage = 100.0
        prompt.approved_by = approved_by
        
        # Update serving cache
        self._update_serving_cache(prompt_id)
        return True
    
    def start_experiment(self, prompt_id: str, 
                         variant_versions: List[int],
                         traffic_split: List[float],
                         success_metric: str) -> str:
        """Start A/B test between prompt versions."""
        assert sum(traffic_split) == 100.0
        
        variants = []
        for version, traffic in zip(variant_versions, traffic_split):
            prompt = self.prompts[prompt_id][version]
            prompt.traffic_percentage = traffic
            prompt.status = PromptStatus.CANARY
            variants.append(prompt)
        
        experiment = PromptExperiment(
            experiment_id=f"exp_{prompt_id}_{int(time.time())}",
            prompt_id=prompt_id,
            variants=variants,
            start_time=time.time(),
            end_time=None,
            success_metric=success_metric
        )
        
        self.experiments[experiment.experiment_id] = experiment
        self._update_serving_cache(prompt_id)
        return experiment.experiment_id
    
    def _update_serving_cache(self, prompt_id: str):
        """Update the fast-lookup cache for serving."""
        active_versions = [
            p for p in self.prompts[prompt_id].values()
            if p.status in [PromptStatus.PRODUCTION, PromptStatus.CANARY]
            and p.traffic_percentage > 0
        ]
        self.serving_cache[prompt_id] = active_versions


class PromptServingLayer:
    """Low-latency prompt resolution with A/B testing."""
    
    def __init__(self, registry: PromptRegistry):
        self.registry = registry
        self.redis_cache = None  # Redis for distributed cache
    
    def resolve_prompt(self, prompt_id: str, variables: Dict[str, str],
                       user_id: str = None) -> str:
        """Resolve prompt template with variables and A/B routing."""
        # Get active versions
        active = self.registry.serving_cache.get(prompt_id, [])
        
        if not active:
            raise PromptNotFound(f"No active version for {prompt_id}")
        
        # A/B test routing (deterministic by user_id for consistency)
        selected = self._select_variant(active, user_id)
        
        # Interpolate variables
        rendered = self._render_template(selected.template, variables)
        
        # Apply guardrails
        rendered = self._apply_guardrails(rendered, selected)
        
        return rendered
    
    def _select_variant(self, variants: List[PromptVersion], 
                        user_id: Optional[str]) -> PromptVersion:
        """Deterministic variant selection for A/B consistency."""
        if len(variants) == 1:
            return variants[0]
        
        # Deterministic hash for user consistency
        if user_id:
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
        else:
            hash_val = random.randint(0, 99)
        
        cumulative = 0
        for variant in variants:
            cumulative += variant.traffic_percentage
            if hash_val < cumulative:
                return variant
        
        return variants[-1]  # Fallback
    
    def _render_template(self, template: str, variables: Dict[str, str]) -> str:
        """Safe template rendering with variable validation."""
        try:
            # Only allow whitelisted variables
            rendered = template.format(**variables)
            return rendered
        except KeyError as e:
            raise MissingVariable(f"Required variable not provided: {e}")
    
    def _apply_guardrails(self, rendered: str, prompt: PromptVersion) -> str:
        """Apply safety guardrails to rendered prompt."""
        # Inject system-level safety prefix if not present
        safety_prefix = "You must not generate harmful, illegal, or discriminatory content."
        if safety_prefix not in rendered:
            rendered = f"{safety_prefix}\n\n{rendered}"
        
        # Truncate if exceeds model context
        max_chars = 50000  # ~12K tokens
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars]
        
        return rendered


class PromptAnalytics:
    """Track prompt performance for optimization."""
    
    async def get_experiment_results(self, experiment_id: str) -> dict:
        """Get A/B test results with statistical significance."""
        experiment = self.registry.experiments[experiment_id]
        
        results = {}
        for variant in experiment.variants:
            metrics = await self._get_variant_metrics(
                variant, experiment.success_metric
            )
            results[f"v{variant.version}"] = metrics
        
        # Statistical significance test
        if len(results) == 2:
            variants = list(results.values())
            significant = self._chi_squared_test(variants[0], variants[1])
            results["statistically_significant"] = significant
        
        return results
    
    async def _get_variant_metrics(self, variant: PromptVersion, 
                                    metric_name: str) -> dict:
        """Get aggregated metrics for a prompt variant."""
        return {
            "sample_size": 5000,
            "metric_value": 0.82,
            "confidence_interval": (0.79, 0.85),
        }
    
    def _chi_squared_test(self, control: dict, treatment: dict) -> bool:
        """Test if difference is statistically significant (p<0.05)."""
        # Simplified
        return True
```

### Scale Considerations

| Dimension | Scale | Solution |
|-----------|-------|----------|
| Teams | 500 | Namespace isolation, RBAC per team |
| Prompts | 25,000 (50 per team) | Git-backed registry, indexed search |
| Versions | 250,000 (10 per prompt) | Efficient storage, prune old versions |
| Lookups/sec | 100K | Redis cache, <1ms resolution |
| A/B tests | 200 concurrent | Deterministic hashing, shared nothing |

### Production Considerations

- **Rollback**: One-click rollback to previous production version. Automated rollback if quality scores drop >10% within 1 hour of promotion.
- **Cross-team discovery**: Searchable catalog of all prompts. Teams can fork/reuse prompts from other teams (with attribution).
- **Cost tracking**: Each prompt version has an associated cost profile (model × avg tokens × volume). Dashboard shows cost impact of prompt changes.
- **Compliance**: Audit log of all prompt changes for SOC2/HIPAA. Prompts handling sensitive data require security review.
- **Testing**: CI/CD pipeline runs prompt against golden test set before approval. Must pass quality threshold to be promotable.
