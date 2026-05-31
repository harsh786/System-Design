# Sharding & Partitioning for AI Systems: Real-World Examples

## Case Study 1: Multi-Tenant SaaS Sharding Vector Data Across 500+ Tenants

### Context

DataVault AI is a B2B SaaS platform providing semantic search over enterprise documents. They serve 500+ tenants ranging from 10-person startups (5K documents) to Fortune 500 companies (2M+ documents). Their vector database (Qdrant) stores 1536-dimensional OpenAI embeddings.

### The Problem

Initially, all tenants shared a single Qdrant collection with a `tenant_id` metadata filter. At 50 tenants, p99 latency was 80ms. At 200 tenants, it degraded to 450ms. At 350 tenants, some queries timed out at 2 seconds.

### Strategy Selection Process

The engineering team evaluated three approaches:

```
Option A: One collection per tenant
  - Pros: Perfect isolation, simple routing, easy deletion
  - Cons: 500+ collections = massive memory overhead for small tenants
  - Memory cost: ~50MB base per collection × 500 = 25GB just for metadata

Option B: Tiered sharding (small tenants pooled, large tenants isolated)
  - Pros: Efficient resource use, isolation where it matters
  - Cons: Complex routing logic, migration needed when tenants grow
  - Memory cost: ~8GB total (20 shared pools + 30 dedicated collections)

Option C: Hash-based sharding with tenant-aware routing
  - Pros: Even distribution, predictable scaling
  - Cons: Cross-shard queries for analytics, complex rebalancing
  - Memory cost: ~10GB total across 32 shards
```

They chose **Option B** with the following tier definitions:

```python
class TenantTier:
    SMALL = "small"       # < 50K vectors → shared pool
    MEDIUM = "medium"     # 50K-500K vectors → dedicated shard in shared cluster
    LARGE = "large"       # 500K-5M vectors → dedicated collection
    ENTERPRISE = "enterprise"  # > 5M vectors → dedicated cluster

class ShardRouter:
    def __init__(self, tenant_registry: TenantRegistry):
        self.registry = tenant_registry
        self.pool_assignments = {}  # tenant_id → pool_id for SMALL tenants
        self.shard_map = {}         # tenant_id → shard_endpoint for MEDIUM+

    def route(self, tenant_id: str) -> ShardTarget:
        tenant = self.registry.get(tenant_id)

        if tenant.tier == TenantTier.SMALL:
            pool_id = self._get_pool_assignment(tenant_id)
            return ShardTarget(
                collection=f"shared_pool_{pool_id}",
                filter={"tenant_id": tenant_id},
                endpoint=self._get_pool_endpoint(pool_id)
            )
        elif tenant.tier == TenantTier.MEDIUM:
            return ShardTarget(
                collection=f"tenant_{tenant_id}",
                filter=None,  # dedicated collection, no filter needed
                endpoint=self.shard_map[tenant_id]
            )
        elif tenant.tier == TenantTier.LARGE:
            return ShardTarget(
                collection=f"tenant_{tenant_id}",
                filter=None,
                endpoint=tenant.dedicated_endpoint
            )
        elif tenant.tier == TenantTier.ENTERPRISE:
            return ShardTarget(
                collection=f"tenant_{tenant_id}",
                filter=None,
                endpoint=tenant.cluster_endpoint
            )

    def _get_pool_assignment(self, tenant_id: str) -> int:
        if tenant_id not in self.pool_assignments:
            # Assign to least-loaded pool using consistent hashing
            pool_id = self._consistent_hash(tenant_id, num_pools=20)
            self.pool_assignments[tenant_id] = pool_id
        return self.pool_assignments[tenant_id]
```

### Rebalancing: The Tier Promotion Pipeline

When a tenant grows beyond their tier threshold, an automated pipeline handles promotion:

```python
class TierPromotionPipeline:
    """
    Runs every 6 hours. Checks tenant vector counts against thresholds.
    Promotes/demotes tenants between tiers with zero downtime.
    """

    def promote_small_to_medium(self, tenant_id: str):
        """Move tenant from shared pool to dedicated collection."""
        # Step 1: Create new dedicated collection
        new_collection = f"tenant_{tenant_id}"
        self.qdrant.create_collection(new_collection, vectors_config={
            "size": 1536, "distance": "Cosine"
        })

        # Step 2: Copy vectors (background, ~15 minutes for 500K vectors)
        pool_id = self.router.pool_assignments[tenant_id]
        vectors = self.qdrant.scroll(
            collection=f"shared_pool_{pool_id}",
            filter={"tenant_id": tenant_id},
            limit=1000  # paginated
        )
        for batch in chunked(vectors, 500):
            self.qdrant.upsert(new_collection, batch)

        # Step 3: Atomic routing switch (Redis-based)
        self.redis.set(f"route:{tenant_id}", json.dumps({
            "collection": new_collection,
            "tier": "medium"
        }))

        # Step 4: Delete from shared pool (after 24h grace period)
        self.scheduler.schedule_deletion(
            collection=f"shared_pool_{pool_id}",
            filter={"tenant_id": tenant_id},
            delay_hours=24
        )

        # Step 5: Update registry
        self.registry.update_tier(tenant_id, TenantTier.MEDIUM)
```

### Results After Migration

| Metric | Before (single collection) | After (tiered sharding) |
|--------|---------------------------|------------------------|
| p50 latency | 120ms | 25ms |
| p99 latency | 2100ms | 95ms |
| Query timeout rate | 3.2% | 0.01% |
| Memory efficiency | 40% utilized | 78% utilized |
| Tenant onboarding time | 0s (just insert) | 2s (pool assignment) |

---

## Case Study 2: Partitioning 50M Documents for Fast Retrieval

### Context

ResearchHub is an internal knowledge platform at a pharmaceutical company. They index 50M documents spanning:
- 12M research papers (2000-2024)
- 8M clinical trial reports
- 15M patent filings
- 10M internal memos/emails
- 5M regulatory submissions

Users need sub-200ms semantic search with filters on department, date range, and document type.

### Partition Design

They implemented a **composite partitioning strategy** with three dimensions:

```
Level 1: Department (List Partition)
  ├── R&D (18M docs)
  ├── Clinical (12M docs)
  ├── Legal/IP (15M docs)
  ├── Regulatory (5M docs)
  └── Corporate (mixed, pointer-based)

Level 2: Time (Range Partition within each department)
  ├── Current (last 2 years) — hot storage, in-memory HNSW
  ├── Recent (2-5 years) — warm storage, disk-backed HNSW
  ├── Archive (5-15 years) — cold storage, flat index with PQ compression
  └── Legacy (15+ years) — frozen, loaded on-demand

Level 3: Topic Cluster (Hash Partition within time ranges)
  ├── 64 topic clusters per time partition
  └── Assigned via k-means on document embeddings during ingestion
```

### Implementation Architecture

```python
class CompositePartitionRouter:
    def __init__(self):
        self.department_map = {
            "R&D": ["rd_current", "rd_recent", "rd_archive", "rd_legacy"],
            "Clinical": ["clin_current", "clin_recent", "clin_archive"],
            "Legal/IP": ["legal_current", "legal_recent", "legal_archive"],
            "Regulatory": ["reg_current", "reg_recent"],
            "Corporate": ["corp_current", "corp_recent"]
        }
        self.topic_classifier = TopicClassifier(num_clusters=64)

    def route_query(self, query: SearchQuery) -> list[PartitionTarget]:
        targets = []

        # Level 1: Department filter
        departments = query.departments or list(self.department_map.keys())

        for dept in departments:
            partitions = self.department_map[dept]

            # Level 2: Time filter
            relevant_partitions = self._filter_by_time(
                partitions, query.date_range
            )

            # Level 3: Topic routing (optional optimization)
            if query.enable_topic_routing:
                topic_ids = self.topic_classifier.predict_topics(
                    query.embedding, top_k=8
                )
                for partition in relevant_partitions:
                    targets.append(PartitionTarget(
                        partition=partition,
                        topic_filter=topic_ids,
                        max_results=query.top_k
                    ))
            else:
                for partition in relevant_partitions:
                    targets.append(PartitionTarget(
                        partition=partition,
                        topic_filter=None,
                        max_results=query.top_k
                    ))

        return targets

    def _filter_by_time(self, partitions: list, date_range: DateRange) -> list:
        """Only search partitions that overlap with the query's date range."""
        result = []
        now = datetime.now()

        for p in partitions:
            if "current" in p and date_range.overlaps(now - timedelta(days=730), now):
                result.append(p)
            elif "recent" in p and date_range.overlaps(now - timedelta(days=1825), now - timedelta(days=730)):
                result.append(p)
            elif "archive" in p and date_range.overlaps(now - timedelta(days=5475), now - timedelta(days=1825)):
                result.append(p)
            elif "legacy" in p:
                if date_range.start and date_range.start < now - timedelta(days=5475):
                    result.append(p)

        return result
```

### Storage Optimization by Tier

```yaml
# Current tier (last 2 years): Optimized for speed
current_tier:
  index_type: HNSW
  storage: in-memory
  ef_construction: 256
  m: 32
  quantization: none  # full float32 for accuracy
  replicas: 3
  expected_vectors: 8M
  memory_per_node: 48GB

# Recent tier (2-5 years): Balance of speed and cost
recent_tier:
  index_type: HNSW
  storage: mmap (disk-backed)
  ef_construction: 128
  m: 16
  quantization: scalar (int8)  # 4x memory reduction
  replicas: 2
  expected_vectors: 15M
  memory_per_node: 16GB + 200GB SSD

# Archive tier (5-15 years): Optimized for cost
archive_tier:
  index_type: IVF-PQ
  storage: disk
  nlist: 4096
  pq_segments: 48  # 32x compression
  replicas: 1
  expected_vectors: 20M
  memory_per_node: 8GB + 500GB HDD

# Legacy tier (15+ years): Cold storage, loaded on demand
legacy_tier:
  index_type: flat (brute force on load)
  storage: object_storage (S3)
  loaded_on_demand: true
  ttl_in_memory: 30_minutes
  expected_vectors: 7M
```

### Query Performance by Partition Combination

| Query Scope | Partitions Searched | p50 Latency | p99 Latency |
|-------------|-------------------|-------------|-------------|
| Single dept + current | 1 | 12ms | 35ms |
| Single dept + all time | 4 | 45ms | 120ms |
| All depts + current | 5 | 28ms | 85ms |
| All depts + all time | 20 | 180ms | 450ms |
| Single dept + topic-routed | 1 (partial) | 8ms | 22ms |

---

## Shard Routing: Real Implementation

### The Complete Query Flow

```python
class ShardAwareQueryEngine:
    """
    Production shard routing for a multi-tenant vector search system.
    Handles routing, fan-out, result merging, and fallback.
    """

    def __init__(self, config: ShardConfig):
        self.shard_registry = ShardRegistry(config.registry_url)
        self.connection_pool = ConnectionPool(max_per_shard=10)
        self.circuit_breakers = {}  # shard_id → CircuitBreaker

    async def search(self, request: SearchRequest) -> SearchResponse:
        # Step 1: Determine target shards
        targets = self._resolve_shards(request)

        # Step 2: Fan-out queries in parallel
        tasks = []
        for target in targets:
            if self._is_shard_healthy(target.shard_id):
                tasks.append(self._query_shard(target, request))
            else:
                # Use replica or skip with degraded flag
                replica = self.shard_registry.get_replica(target.shard_id)
                if replica:
                    tasks.append(self._query_shard(replica, request))

        # Step 3: Gather results with timeout
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4: Merge and rank
        merged = self._merge_results(results, request.top_k)

        # Step 5: Track metrics
        self._emit_metrics(targets, results)

        return merged

    def _resolve_shards(self, request: SearchRequest) -> list[ShardTarget]:
        """
        Routing logic based on request characteristics.
        """
        # Tenant-based routing (most common)
        if request.tenant_id:
            shard_info = self.shard_registry.lookup_tenant(request.tenant_id)
            return [ShardTarget(
                shard_id=shard_info.shard_id,
                endpoint=shard_info.endpoint,
                collection=shard_info.collection
            )]

        # Time-based routing
        if request.time_range:
            return self.shard_registry.lookup_time_range(
                request.time_range.start,
                request.time_range.end
            )

        # Topic-based routing (uses embedding similarity to shard centroids)
        if request.embedding and request.enable_smart_routing:
            shard_scores = self.shard_registry.score_shards_by_centroid(
                request.embedding, top_k=3
            )
            return [s for s in shard_scores if s.score > 0.3]

        # Fallback: broadcast to all relevant shards
        return self.shard_registry.get_all_active_shards()

    def _merge_results(self, results: list, top_k: int) -> SearchResponse:
        """
        Merge results from multiple shards using a priority queue.
        Handles duplicates (documents replicated across shards) and
        normalizes scores across different shard index configurations.
        """
        heap = []
        seen_ids = set()
        failed_shards = []

        for result in results:
            if isinstance(result, Exception):
                failed_shards.append(result)
                continue
            for hit in result.hits:
                if hit.id not in seen_ids:
                    seen_ids.add(hit.id)
                    heapq.heappush(heap, (-hit.score, hit))

        top_results = []
        for _ in range(min(top_k, len(heap))):
            score, hit = heapq.heappop(heap)
            top_results.append(hit)

        return SearchResponse(
            hits=top_results,
            total_shards_queried=len(results),
            failed_shards=len(failed_shards),
            degraded=len(failed_shards) > 0
        )
```

---

## Partition Strategies: Range vs Hash vs List for Vector Stores

### When Range Partitioning Wins

**Use case: Time-series document embeddings (news, social media, logs)**

```python
# Range partition by ingestion timestamp
# Each partition covers a fixed time window

class TimeRangePartitioner:
    """
    Optimal when:
    - Queries almost always include a time filter
    - Recent data is queried 10x more than old data
    - Old partitions can be compressed/archived independently
    - Growth is predictable (X docs per day)
    """

    def __init__(self, partition_duration_days: int = 30):
        self.duration = timedelta(days=partition_duration_days)

    def get_partition_key(self, document: Document) -> str:
        # Partition name: vectors_2024_03
        return f"vectors_{document.created_at.strftime('%Y_%m')}"

    def get_query_partitions(self, time_range: TimeRange) -> list[str]:
        partitions = []
        current = time_range.start.replace(day=1)
        while current <= time_range.end:
            partitions.append(f"vectors_{current.strftime('%Y_%m')}")
            current += timedelta(days=32)
            current = current.replace(day=1)
        return partitions

# Result: News aggregator with 200M articles
# Query "latest AI news" only hits 1-2 partitions (current month + last month)
# Instead of scanning all 200M vectors, scans ~3M (60x reduction)
```

### When Hash Partitioning Wins

**Use case: Multi-tenant with uniform access patterns**

```python
class ConsistentHashPartitioner:
    """
    Optimal when:
    - No natural range key exists
    - Need even distribution across shards
    - Tenant/user access is unpredictable
    - Want to add/remove shards with minimal data movement
    """

    def __init__(self, num_shards: int = 32, virtual_nodes: int = 150):
        self.ring = ConsistentHashRing(num_shards, virtual_nodes)

    def get_partition(self, tenant_id: str) -> int:
        return self.ring.get_node(tenant_id)

    def rebalance_after_adding_shard(self, new_shard_id: int):
        """
        With consistent hashing, adding 1 shard to 32 existing shards
        only moves ~3% of data (1/33), not 50% like naive hash.
        """
        affected_keys = self.ring.add_node(new_shard_id)
        return affected_keys  # Only keys that need migration

# Performance comparison at 500 tenants, 32 shards:
# - Naive modulo hash: Adding 1 shard moves 48% of data
# - Consistent hash: Adding 1 shard moves 3.1% of data
# - Consistent hash with 150 vnodes: Variance in shard size < 5%
```

### When List Partitioning Wins

**Use case: Domain-specific knowledge bases with clear categorical boundaries**

```python
class ListPartitioner:
    """
    Optimal when:
    - Clear categorical boundaries exist (department, product line, region)
    - Categories have very different access patterns
    - Categories need different index configurations
    - Compliance requires data isolation (GDPR per-region)
    """

    PARTITION_MAP = {
        # Category → (partition_name, index_config)
        "medical": ("medical_vectors", {"ef": 256, "m": 48}),  # High accuracy needed
        "legal": ("legal_vectors", {"ef": 128, "m": 32}),
        "financial": ("financial_vectors", {"ef": 128, "m": 32}),
        "engineering": ("engineering_vectors", {"ef": 64, "m": 16}),  # Speed over accuracy
        "marketing": ("marketing_vectors", {"ef": 64, "m": 16}),
    }

    def route(self, document: Document) -> str:
        category = document.metadata.get("department", "general")
        if category in self.PARTITION_MAP:
            return self.PARTITION_MAP[category][0]
        return "general_vectors"

# Real result: Medical queries get 99.2% recall (high ef),
# while engineering queries get 94% recall but 3x faster (lower ef).
# Each department's SLA is met independently.
```

---

## Hot-Spot Detection and Rebalancing

### The Discovery

A fintech AI platform running semantic search for customer support noticed:

```
Shard Distribution Report (Week 42, 2024):
------------------------------------------
Total queries: 2.4M/day
Total shards: 40

Top 5 shards by query volume:
  shard_07: 312K queries/day (13.0%) ← Tenant: MegaBank
  shard_14: 289K queries/day (12.0%) ← Tenant: InsureCorp
  shard_23: 201K queries/day  (8.4%) ← Tenant: TradeFirm
  shard_31: 178K queries/day  (7.4%) ← Shared pool (has 3 active tenants)
  shard_02: 156K queries/day  (6.5%) ← Tenant: CryptoExchange

Top 5 shards handle: 1,136K queries = 47.3% of total traffic
Bottom 20 shards handle: 312K queries = 13.0% of total traffic

CPU utilization:
  shard_07: 89% (critical)
  shard_14: 82% (warning)
  shard_23: 71% (elevated)
  Average of remaining: 28%
```

### Detection System

```python
class HotSpotDetector:
    """
    Runs every 5 minutes. Detects imbalanced shards using coefficient of variation.
    """

    IMBALANCE_THRESHOLD = 0.4  # CV > 0.4 means significant imbalance
    HOT_SHARD_THRESHOLD = 3.0  # 3x average = hot shard

    def detect(self, metrics: ShardMetrics) -> HotSpotReport:
        query_counts = [m.query_count_5min for m in metrics.shards]
        avg = statistics.mean(query_counts)
        std = statistics.stdev(query_counts)
        cv = std / avg if avg > 0 else 0

        hot_shards = [
            m for m in metrics.shards
            if m.query_count_5min > avg * self.HOT_SHARD_THRESHOLD
        ]

        cold_shards = [
            m for m in metrics.shards
            if m.query_count_5min < avg * 0.2
        ]

        return HotSpotReport(
            coefficient_of_variation=cv,
            is_imbalanced=cv > self.IMBALANCE_THRESHOLD,
            hot_shards=hot_shards,
            cold_shards=cold_shards,
            recommendation=self._recommend(hot_shards, cold_shards)
        )

    def _recommend(self, hot: list, cold: list) -> str:
        if len(hot) == 1 and hot[0].is_single_tenant:
            return f"SPLIT: Shard {hot[0].id} has single large tenant. Split into 4 sub-shards."
        elif len(hot) > 2:
            return "REBALANCE: Multiple hot shards detected. Redistribute tenants."
        elif len(cold) > len(hot) * 3:
            return "MERGE: Many underutilized cold shards. Consider consolidation."
        return "MONITOR: Imbalance detected but within recovery bounds."
```

### Rebalancing Strategy Executed

```python
class ShardRebalancer:
    """
    Executed for MegaBank (shard_07) which had 4M vectors on a single shard.
    Strategy: Split into 4 sub-shards by document category.
    """

    async def split_tenant_shard(self, tenant_id: str, num_splits: int = 4):
        source_shard = self.registry.get_shard(tenant_id)

        # Step 1: Create target shards
        target_shards = []
        for i in range(num_splits):
            shard = await self.create_shard(f"{source_shard.id}_split_{i}")
            target_shards.append(shard)

        # Step 2: Assign split strategy (by topic cluster)
        cluster_assignments = self._compute_cluster_splits(
            tenant_id, num_splits
        )
        # Result: {cluster_0-15: shard_0, cluster_16-31: shard_1, ...}

        # Step 3: Background migration (took 4 hours for 4M vectors)
        migration_job = await self.start_migration(
            source=source_shard,
            targets=target_shards,
            assignment_fn=cluster_assignments,
            batch_size=10000,
            rate_limit=5000  # vectors/second to avoid overloading source
        )

        # Step 4: Dual-write phase (new writes go to both old and new)
        await self.enable_dual_write(tenant_id, source_shard, target_shards)

        # Step 5: Wait for migration completion
        await migration_job.wait()

        # Step 6: Switch routing atomically
        await self.registry.update_routing(tenant_id, {
            "type": "fan_out",
            "shards": [s.id for s in target_shards],
            "merge_strategy": "top_k_merge"
        })

        # Step 7: Disable dual-write, decommission source
        await self.disable_dual_write(tenant_id)
        await self.schedule_decommission(source_shard, grace_period_hours=48)

# Results after rebalancing:
# shard_07 CPU: 89% → decommissioned
# 4 new shards CPU: 22%, 25%, 19%, 24% (balanced)
# MegaBank p99 latency: 180ms → 65ms (fan-out with merge is faster than single overloaded shard)
```

---

## Cross-Shard Queries

### When Cross-Shard is Unavoidable

```python
class CrossShardQueryEngine:
    """
    Scenario: User asks "Find all documents about GDPR compliance across all departments"
    This requires searching Legal, Regulatory, Engineering, and Corporate partitions.
    """

    async def cross_shard_search(
        self, query: str, embedding: list[float], top_k: int = 20
    ) -> CrossShardResult:
        # Determine all relevant shards
        target_shards = self.router.resolve_all_relevant(query)
        # Returns: [legal_current, legal_recent, reg_current, eng_current, corp_current]

        start_time = time.monotonic()

        # Fan-out with per-shard timeout
        shard_tasks = [
            self._query_with_timeout(
                shard=shard,
                embedding=embedding,
                top_k=top_k * 2,  # Over-fetch for better merge quality
                timeout_ms=200    # Per-shard timeout
            )
            for shard in target_shards
        ]

        # Gather with global timeout
        results = await asyncio.wait_for(
            asyncio.gather(*shard_tasks, return_exceptions=True),
            timeout=0.5  # 500ms global timeout
        )

        # Merge with score normalization
        merged = self._normalized_merge(results, top_k)

        elapsed = time.monotonic() - start_time

        return CrossShardResult(
            hits=merged,
            latency_ms=elapsed * 1000,
            shards_queried=len(target_shards),
            shards_responded=sum(1 for r in results if not isinstance(r, Exception)),
            shards_timed_out=sum(1 for r in results if isinstance(r, asyncio.TimeoutError))
        )

    def _normalized_merge(self, results: list, top_k: int) -> list[Hit]:
        """
        Different shards may use different index configs, so raw scores
        aren't directly comparable. Normalize per-shard before merging.
        """
        all_hits = []
        for result in results:
            if isinstance(result, Exception):
                continue
            if not result.hits:
                continue
            # Per-shard min-max normalization
            scores = [h.score for h in result.hits]
            min_s, max_s = min(scores), max(scores)
            range_s = max_s - min_s if max_s != min_s else 1.0

            for hit in result.hits:
                normalized_score = (hit.score - min_s) / range_s
                all_hits.append((normalized_score, hit))

        # Sort by normalized score, return top_k
        all_hits.sort(key=lambda x: x[0], reverse=True)
        return [hit for _, hit in all_hits[:top_k]]
```

### Latency Analysis for Cross-Shard

```
Query: "GDPR compliance" across 5 shards
├── Shard 1 (legal_current): 18ms
├── Shard 2 (legal_recent): 45ms (disk-backed, slower)
├── Shard 3 (reg_current): 22ms
├── Shard 4 (eng_current): 15ms
└── Shard 5 (corp_current): 20ms

Total latency = max(individual) + merge_overhead
             = 45ms + 3ms (merge)
             = 48ms

Compare to single-shard query: 15-22ms
Cross-shard overhead: ~2-3x (acceptable)

Worst case (one slow shard):
If legal_recent takes 180ms but others take 20ms:
  - With 200ms per-shard timeout: Total = 183ms
  - Without timeout: Could block indefinitely
  - With partial results: Return results from 4/5 shards in 23ms, mark degraded
```

---

## Ingestion Pipeline: 100K Documents/Hour Distributed Across Shards

### Architecture

```python
class DistributedIngestionPipeline:
    """
    Handles 100K documents/hour = ~28 docs/second sustained.
    Peak: 500 docs/second during bulk uploads.

    Architecture:
    [Upload API] → [Kafka] → [Embedding Workers] → [Shard Writers] → [Vector DB]
                                    (8 workers)        (per-shard)
    """

    def __init__(self):
        self.kafka_producer = KafkaProducer(
            bootstrap_servers="kafka:9092",
            topic="documents.raw"
        )
        self.embedding_pool = EmbeddingWorkerPool(
            num_workers=8,
            model="text-embedding-3-large",
            batch_size=64,
            max_concurrent_batches=4
        )
        self.shard_writers = ShardWriterPool(
            buffer_size=500,       # Buffer per shard before flush
            flush_interval_ms=1000  # Flush at least every second
        )

    async def ingest_document(self, doc: RawDocument):
        # Step 1: Produce to Kafka for durability
        await self.kafka_producer.send(
            key=doc.tenant_id,  # Ensures ordering per tenant
            value=doc.serialize()
        )

    async def process_batch(self, docs: list[RawDocument]):
        """Called by Kafka consumer. Processes a batch of documents."""

        # Step 2: Chunk documents
        chunks = []
        for doc in docs:
            doc_chunks = self.chunker.chunk(
                doc.content,
                chunk_size=512,
                overlap=64,
                metadata=doc.metadata
            )
            chunks.extend(doc_chunks)

        # Step 3: Generate embeddings (batched for efficiency)
        embeddings = await self.embedding_pool.embed_batch(
            texts=[c.text for c in chunks]
        )

        # Step 4: Route to correct shards
        shard_batches = defaultdict(list)
        for chunk, embedding in zip(chunks, embeddings):
            shard_id = self.router.get_write_shard(chunk.metadata)
            shard_batches[shard_id].append(
                VectorPoint(
                    id=chunk.id,
                    vector=embedding,
                    payload=chunk.metadata
                )
            )

        # Step 5: Write to shards (parallel, with backpressure)
        write_tasks = [
            self.shard_writers.write(shard_id, points)
            for shard_id, points in shard_batches.items()
        ]
        await asyncio.gather(*write_tasks)

    # Throughput metrics:
    # - Embedding generation: 64 texts × 8 workers = 512 embeddings/batch
    # - At ~100ms per batch: 5,120 embeddings/second capacity
    # - Each document → ~8 chunks avg: 640 documents/second capacity
    # - Actual sustained: 28 docs/second (well within capacity)
    # - Peak handling: 500 docs/second = 4,000 chunks/second (78% capacity)
```

### Backpressure and Rate Limiting

```python
class ShardWriter:
    """Per-shard writer with backpressure to prevent overwhelming the vector DB."""

    def __init__(self, shard_id: str, max_pending: int = 5000):
        self.shard_id = shard_id
        self.buffer = []
        self.pending_count = 0
        self.max_pending = max_pending
        self.semaphore = asyncio.Semaphore(4)  # Max 4 concurrent writes

    async def write(self, points: list[VectorPoint]):
        # Backpressure: if too many pending writes, slow down
        while self.pending_count > self.max_pending:
            await asyncio.sleep(0.1)
            # This naturally slows Kafka consumption, creating backpressure

        self.buffer.extend(points)

        if len(self.buffer) >= 500:  # Flush at 500 points
            await self._flush()

    async def _flush(self):
        async with self.semaphore:
            batch = self.buffer[:500]
            self.buffer = self.buffer[500:]
            self.pending_count += len(batch)

            try:
                await self.qdrant_client.upsert(
                    collection=self.shard_id,
                    points=batch,
                    wait=False  # Async write for throughput
                )
            finally:
                self.pending_count -= len(batch)
```

---

## Shard Lifecycle Management

### Creating a New Shard (Zero-Downtime)

```python
class ShardLifecycleManager:
    async def create_shard(self, config: ShardConfig) -> Shard:
        """
        Create a new shard and register it for traffic.
        Used when: tenant grows beyond threshold, time partition rolls over,
                   or capacity planning predicts need.
        """
        # 1. Provision infrastructure
        shard = await self.infrastructure.provision(
            cpu=config.cpu_cores,
            memory_gb=config.memory_gb,
            storage_gb=config.storage_gb,
            region=config.region
        )

        # 2. Create collection with config
        await shard.client.create_collection(
            name=config.collection_name,
            vectors_config=config.vector_config,
            hnsw_config=config.hnsw_config,
            optimizers_config=config.optimizer_config
        )

        # 3. Register in shard registry (not yet receiving traffic)
        await self.registry.register(shard, status="provisioning")

        # 4. If splitting from existing shard, start data migration
        if config.source_shard:
            await self._migrate_data(config.source_shard, shard, config.filter)

        # 5. Health check
        await self._verify_shard_health(shard)

        # 6. Enable traffic
        await self.registry.update_status(shard.id, "active")
        await self.router.add_shard(shard.id, config.routing_rules)

        return shard

    async def split_shard(self, shard_id: str, split_key: str):
        """Split one shard into two at a given key boundary."""
        source = self.registry.get(shard_id)

        # Create two new shards
        left = await self.create_shard(ShardConfig(
            collection_name=f"{shard_id}_left",
            vector_config=source.vector_config
        ))
        right = await self.create_shard(ShardConfig(
            collection_name=f"{shard_id}_right",
            vector_config=source.vector_config
        ))

        # Migrate data (left gets keys < split_key, right gets keys >= split_key)
        await asyncio.gather(
            self._migrate_data(source, left, filter=f"key < {split_key}"),
            self._migrate_data(source, right, filter=f"key >= {split_key}")
        )

        # Atomic routing switch
        await self.router.replace_shard(shard_id, [left.id, right.id], split_key)

        # Decommission source after grace period
        await self.schedule_decommission(shard_id, grace_hours=24)

    async def merge_shards(self, shard_ids: list[str]):
        """Merge multiple underutilized shards into one."""
        # Only safe if combined size < single shard capacity
        total_vectors = sum(
            self.registry.get(s).vector_count for s in shard_ids
        )
        if total_vectors > self.MAX_SHARD_SIZE:
            raise ValueError(f"Combined size {total_vectors} exceeds max {self.MAX_SHARD_SIZE}")

        target = await self.create_shard(ShardConfig(
            collection_name=f"merged_{int(time.time())}",
            vector_config=self.registry.get(shard_ids[0]).vector_config
        ))

        for shard_id in shard_ids:
            await self._migrate_data(self.registry.get(shard_id), target)

        # Update routing for all merged shards
        await self.router.replace_shards(shard_ids, target.id)

        for shard_id in shard_ids:
            await self.schedule_decommission(shard_id, grace_hours=24)
```

---

## Multi-Tenant Index Isolation: Performance Comparison

### Test Setup

Benchmarked two approaches at varying tenant counts:

```
Approach A: Shared collection with metadata filter
  - Single Qdrant collection
  - Each vector has payload: {"tenant_id": "abc123"}
  - Queries use filter: {"must": [{"key": "tenant_id", "match": {"value": "abc123"}}]}
  - Payload index on tenant_id field

Approach B: Per-tenant collections
  - One collection per tenant
  - No filter needed on queries
  - Router determines which collection to query
```

### Results at Scale

| Tenants | Vectors/Tenant | Approach A p50 | Approach A p99 | Approach B p50 | Approach B p99 |
|---------|---------------|----------------|----------------|----------------|----------------|
| 100 | 10K | 8ms | 22ms | 5ms | 15ms |
| 100 | 100K | 15ms | 45ms | 12ms | 35ms |
| 1,000 | 10K | 12ms | 55ms | 5ms | 16ms |
| 1,000 | 100K | 28ms | 120ms | 13ms | 38ms |
| 10,000 | 10K | 35ms | 180ms | 6ms | 18ms |
| 10,000 | 100K | 85ms | 450ms | 14ms | 42ms |

### Why Shared Collections Degrade

```
At 10,000 tenants × 100K vectors = 1B total vectors in one collection:

1. HNSW graph becomes massive (1B nodes, each with 16-32 edges)
2. Filter must be applied AFTER graph traversal in many implementations
3. Payload index for tenant_id adds memory overhead
4. Lock contention on single collection during concurrent writes
5. Index optimization (vacuum, compaction) affects ALL tenants

At 10,000 tenants with per-tenant collections:
1. Each collection has only 100K vectors (small, fast HNSW)
2. No filter overhead
3. Independent compaction/optimization
4. BUT: 10,000 collections × ~50MB overhead = 500GB metadata memory
5. Connection management becomes complex
```

### Hybrid Solution (What Production Systems Actually Use)

```python
class HybridTenantIsolation:
    """
    Tenants < 50K vectors: Shared pools (100 tenants per pool)
    Tenants 50K-1M vectors: Dedicated collection, shared cluster
    Tenants > 1M vectors: Dedicated cluster

    This gives:
    - 9,500 small tenants across 95 pools (95 collections)
    - 400 medium tenants (400 collections)
    - 100 large tenants (100 dedicated clusters)
    Total: 495 collections on shared infra + 100 dedicated clusters
    """
    pass
```

---

## Time-Based Partitioning: News Aggregator

### Design for Time-Weighted Retrieval

```python
class TimeWeightedNewsSearch:
    """
    News aggregator indexing 500K articles/day across 36 partitions (one per month for 3 years).
    Search applies time decay: recent articles get score boost.
    """

    # Partition layout:
    # news_2024_11 (current month) — 15M vectors, in-memory HNSW
    # news_2024_10 (last month) — 15M vectors, in-memory HNSW
    # news_2024_09 — 15M vectors, mmap HNSW
    # ...
    # news_2022_01 — 12M vectors, IVF-PQ on disk

    TIME_DECAY_FACTOR = 0.95  # Score multiplier per month of age

    async def search(self, query_embedding: list[float], top_k: int = 20) -> list[Article]:
        # Only search recent partitions unless user specifies otherwise
        partitions = self._get_partitions(months_back=6)

        tasks = []
        for i, partition in enumerate(partitions):
            decay = self.TIME_DECAY_FACTOR ** i
            tasks.append(self._search_partition(
                partition, query_embedding,
                top_k=top_k,
                score_multiplier=decay
            ))

        results = await asyncio.gather(*tasks)

        # Merge with time-adjusted scores
        all_hits = []
        for partition_results, (_, decay) in zip(results, enumerate(partitions)):
            for hit in partition_results:
                hit.adjusted_score = hit.raw_score * (self.TIME_DECAY_FACTOR ** _)
                all_hits.append(hit)

        all_hits.sort(key=lambda h: h.adjusted_score, reverse=True)
        return all_hits[:top_k]

    def _get_partitions(self, months_back: int) -> list[str]:
        """Generate partition names for last N months."""
        partitions = []
        now = datetime.now()
        for i in range(months_back):
            dt = now - timedelta(days=30 * i)
            partitions.append(f"news_{dt.strftime('%Y_%m')}")
        return partitions
```

### Partition Rotation (Monthly Cron Job)

```python
class PartitionRotator:
    """
    Monthly job that:
    1. Creates next month's partition (ready for writes)
    2. Demotes 2-month-old partition from in-memory to mmap
    3. Compresses 12-month-old partition with PQ
    4. Archives 36-month-old partition to cold storage
    """

    async def rotate(self):
        now = datetime.now()
        next_month = now + timedelta(days=32)

        # Create next month (pre-provision)
        await self.create_partition(
            name=f"news_{next_month.strftime('%Y_%m')}",
            config="hot"  # in-memory HNSW
        )

        # Demote: 2 months ago → warm
        two_months_ago = now - timedelta(days=60)
        await self.change_storage_tier(
            f"news_{two_months_ago.strftime('%Y_%m')}",
            from_tier="hot", to_tier="warm"  # Switch to mmap
        )

        # Compress: 12 months ago → cold
        twelve_months_ago = now - timedelta(days=365)
        await self.compress_partition(
            f"news_{twelve_months_ago.strftime('%Y_%m')}",
            method="product_quantization",
            segments=48
        )

        # Archive: 36 months ago → frozen
        thirty_six_months_ago = now - timedelta(days=1095)
        await self.archive_partition(
            f"news_{thirty_six_months_ago.strftime('%Y_%m')}",
            destination="s3://news-archive/"
        )
```

---

## Capacity Planning for Shards

### Growth Prediction Model

```python
class ShardCapacityPlanner:
    """
    Monitors shard growth and predicts when splitting is needed.
    Uses linear regression on last 30 days of data to project future size.
    """

    SPLIT_THRESHOLD = 5_000_000  # Split when shard reaches 5M vectors
    WARNING_THRESHOLD = 0.8      # Alert at 80% of split threshold

    def predict_split_date(self, shard_id: str) -> Optional[datetime]:
        # Get daily vector counts for last 30 days
        history = self.metrics.get_daily_counts(shard_id, days=30)

        if len(history) < 7:
            return None  # Not enough data

        # Linear regression
        days = np.arange(len(history))
        slope, intercept = np.polyfit(days, history, 1)

        current_count = history[-1]
        remaining_capacity = self.SPLIT_THRESHOLD - current_count

        if slope <= 0:
            return None  # Not growing

        days_until_split = remaining_capacity / slope
        split_date = datetime.now() + timedelta(days=days_until_split)

        return split_date

    def generate_capacity_report(self) -> CapacityReport:
        report = []
        for shard in self.registry.get_all_shards():
            split_date = self.predict_split_date(shard.id)
            utilization = shard.vector_count / self.SPLIT_THRESHOLD

            report.append(ShardCapacity(
                shard_id=shard.id,
                current_vectors=shard.vector_count,
                utilization_pct=utilization * 100,
                growth_rate_per_day=self._get_growth_rate(shard.id),
                predicted_split_date=split_date,
                action_needed="SPLIT_NOW" if utilization > 0.95
                    else "PLAN_SPLIT" if utilization > 0.8
                    else "MONITOR" if utilization > 0.6
                    else "OK"
            ))

        return CapacityReport(shards=report)

# Example output:
# ┌───────────┬──────────┬───────┬────────────┬─────────────┬────────────┐
# │ Shard     │ Vectors  │ Util% │ Growth/Day │ Split Date  │ Action     │
# ├───────────┼──────────┼───────┼────────────┼─────────────┼────────────┤
# │ shard_01  │ 4.2M     │ 84%   │ 15K        │ 2024-12-20  │ PLAN_SPLIT │
# │ shard_02  │ 4.8M     │ 96%   │ 22K        │ 2024-11-15  │ SPLIT_NOW  │
# │ shard_03  │ 2.1M     │ 42%   │ 8K         │ 2025-06-01  │ OK         │
# │ shard_04  │ 3.5M     │ 70%   │ 12K        │ 2025-02-28  │ MONITOR    │
# └───────────┴──────────┴───────┴────────────┴─────────────┴────────────┘
```

---

## Key Takeaways

1. **Start with tiered sharding** for multi-tenant — don't over-engineer for small tenants
2. **Composite partitioning** (department × time × topic) dramatically reduces search space
3. **Cross-shard queries** add 2-3x latency; design routing to minimize fan-out
4. **Hot-spot detection** should run continuously; coefficient of variation > 0.4 means trouble
5. **Time-based partitioning** enables tiered storage (hot/warm/cold) with massive cost savings
6. **Capacity planning** with growth prediction prevents emergency splits at 3am
7. **Hybrid tenant isolation** (pooled small + dedicated large) is the production standard
8. **Ingestion backpressure** is critical — without it, a bulk upload can crash your vector DB
9. **Shard lifecycle automation** (create, split, merge, retire) should be fully automated
10. **Score normalization** is essential when merging results across shards with different configurations
