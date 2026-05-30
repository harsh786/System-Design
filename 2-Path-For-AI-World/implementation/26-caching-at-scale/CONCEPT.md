# Caching at Scale for Enterprise AI Systems

## Why AI Caching is Different

Traditional caching stores response = f(request). AI caching is fundamentally harder because:
- **Semantic equivalence**: "What's our revenue?" and "How much did we make?" are the same query
- **Permission-sensitive**: Same query, different user = potentially different answer
- **Freshness-sensitive**: Cached answer from yesterday may be dangerously stale
- **Safety-critical**: A cached response that leaks tenant A's data to tenant B is a security breach
- **Multi-layer**: A single user query touches 6+ cacheable operations

**The cardinal rule**: A cache hit that returns wrong/unauthorized data is infinitely worse than a cache miss.

---

## 1. Nine Cache Types in Enterprise AI

### 1.1 Prompt/Prefix Cache (KV-Cache)

**What**: Caches the Key-Value attention states for shared prompt prefixes in transformer inference.

**Why**: System prompts + few-shot examples can be 4000+ tokens. Re-computing attention for identical prefixes wastes GPU.

**Key design**:
- Cache at the token level, not semantic level
- Exact match required (single token difference = miss)
- Shared across requests with identical system prompt + prefix
- Typically lives on GPU memory (HBM) or host RAM close to inference

**TTL**: Long (hours to days) — system prompts change rarely.

**Invalidation**: On prompt template version change only.

**Scale insight**: At 10K+ RPS, prefix caching saves 30-60% of inference compute for structured enterprise prompts.

### 1.2 Semantic Response Cache

**What**: Caches the final LLM response keyed by the *semantic meaning* of the query (not exact string match).

**Why**: Users ask the same question in different ways. "What was Q3 revenue?" / "Show me revenue for Q3" / "Q3 earnings?" should all hit cache.

**Key design**:
```
cache_key = hash(
    tenant_id,
    embed(normalized_query),       # semantic embedding
    permission_fingerprint,         # user's effective permissions
    model_version,
    prompt_version,
    source_freshness_watermark,    # latest data timestamp
    safety_policy_version,
    risk_tier
)
```

**Similarity threshold**: Typically cosine similarity > 0.95 for cache hit.

**Danger zone**: Must NEVER return cached response if:
- User lacks permission to see the data referenced in response
- Source data has been updated since cache write
- Response was generated under different safety policy

### 1.3 Retrieval Result Cache

**What**: Caches the chunks/documents returned by vector search (RAG retrieval step).

**Why**: Vector search is expensive (ANN index scan + reranking). Same query over same index = same chunks.

**Key design**:
```
cache_key = hash(
    tenant_id,
    query_embedding,
    index_version,          # corpus version
    top_k,
    filter_predicates,      # metadata filters applied
    permission_scope        # what docs user can see
)
```

**TTL**: Until index_version changes (any document ingested/deleted/updated).

**Scale insight**: Retrieval cache has highest hit rate in enterprise (users ask similar questions about same docs).

### 1.4 Reranker Cache

**What**: Caches reranker scores for (query, document) pairs.

**Why**: Cross-encoder reranking is O(n) inference calls per query. Caching avoids redundant scoring.

**Key design**:
```
cache_key = hash(query_embedding, document_id, reranker_model_version)
```

**TTL**: Until document content changes or reranker model updates.

### 1.5 Embedding Cache

**What**: Caches computed embeddings for text chunks.

**Why**: Embedding computation is expensive at scale. Same text = same embedding (deterministic).

**Key design**:
```
cache_key = hash(text_content, embedding_model_version, chunking_strategy_version)
```

**TTL**: Indefinite (embeddings are deterministic for same input + model).

**Scale insight**: Most valuable during bulk ingestion where overlapping content is common.

### 1.6 Tool-Result Cache

**What**: Caches results of external tool/API calls (SQL queries, API responses, calculations).

**Why**: Tool calls are slow (database queries, API latency) and often return same result for same parameters.

**Key design**:
```
cache_key = hash(
    tool_name,
    tool_parameters,        # exact parameter values
    tenant_id,
    data_freshness_watermark,
    permission_fingerprint
)
```

**TTL**: Varies wildly by tool:
- SQL against static data: hours
- Real-time stock price: seconds
- Calculator: indefinite
- User profile lookup: minutes

**Critical rule**: Tool results that depend on user permissions MUST include permission_fingerprint in key.

### 1.7 Document Parse Cache

**What**: Caches parsed/extracted content from documents (PDF parsing, OCR, table extraction).

**Why**: Document parsing is CPU-intensive and deterministic for same input.

**Key design**:
```
cache_key = hash(document_content_hash, parser_version, extraction_config)
```

**TTL**: Indefinite (same document + same parser = same output).

**Scale insight**: Critical for re-ingestion scenarios. Parse once, cache forever (until parser upgrades).

### 1.8 Authorization Decision Cache

**What**: Caches access control decisions (can user X access resource Y?).

**Why**: Permission checks happen on every request. Policy evaluation can be complex (ABAC, hierarchy traversal).

**Key design**:
```
cache_key = hash(user_id, resource_id, action, policy_version)
```

**TTL**: SHORT (seconds to low minutes). Permission changes must propagate quickly.

**CRITICAL SAFETY RULES**:
- MUST invalidate immediately on permission revocation
- MUST invalidate on user role change
- MUST invalidate on resource access policy change
- Never cache "deny" decisions for long (user might get granted access)
- Never cache across tenant boundaries

### 1.9 Eval/Quality Cache

**What**: Caches evaluation scores for response quality (relevance, faithfulness, safety scores).

**Why**: Running eval models on every response is expensive. Same (query, response, context) = same eval score.

**Key design**:
```
cache_key = hash(query, response, context_docs, eval_model_version, eval_criteria_version)
```

**TTL**: Until eval model or criteria changes.

---

## 2. Cache Key Design — The Critical Foundation

### The Golden Rule: Never Cache by Query Alone

A cache key of just `hash(query)` is a **security vulnerability**. It means:
- Tenant A's response could be served to Tenant B
- A user who lost permissions could still get cached authorized responses
- Stale data could be served after source updates

### Complete Cache Key Dimensions

| Dimension | Why Required | Example |
|-----------|-------------|---------|
| `tenant_id` | Absolute isolation between customers | `tenant_acme_corp` |
| `permission_fingerprint` | Same query, different permissions = different accessible data | `hash(user_roles + resource_policies)` |
| `model_version` | Different model = different response quality/format | `gpt-4-0125` |
| `prompt_version` | Prompt template changes alter behavior | `v2.3.1` |
| `index_version` | New documents in corpus = potentially different retrieval | `idx_20240115_003` |
| `source_freshness_watermark` | Latest known data timestamp; stale cache if source updated | `2024-01-15T10:30:00Z` |
| `safety_policy_version` | Policy changes may make previously-safe responses unsafe | `safety_v4` |
| `risk_tier` | Different risk tiers have different staleness tolerances | `high/medium/low` |

### Permission Fingerprint Construction

```python
def build_permission_fingerprint(user_context):
    """
    Create a stable hash representing user's effective permissions.
    Changes when: roles change, group membership changes, resource policies change.
    """
    components = sorted([
        user_context.tenant_id,
        *user_context.effective_roles,
        *user_context.group_memberships,
        str(user_context.permission_policy_version),
        *user_context.resource_scope_ids,  # what resources user can access
    ])
    return hashlib.sha256("|".join(components).encode()).hexdigest()[:16]
```

### Source Freshness Watermark

The freshness watermark tracks the latest timestamp of source data that could affect the response:

```
watermark = max(
    latest_document_ingestion_time,
    latest_database_update_time,
    latest_tool_data_refresh_time
)
```

If `current_watermark > cached_watermark`, the cache entry is stale.

---

## 3. Cache Invalidation Rules

### Event-Driven Invalidation (Immediate)

| Event | What to Invalidate |
|-------|-------------------|
| Document ingested/updated/deleted | Retrieval cache, semantic response cache for affected tenant |
| User permission revoked | Auth decision cache, ALL response caches for that user |
| User added to/removed from group | Auth decision cache, response caches with that group's permissions |
| Prompt template updated | All response caches using that template |
| Model version changed | All response caches, reranker caches |
| Safety policy updated | All response caches (nuclear option, but necessary) |
| Tool schema changed | Tool result caches for that tool |
| Embedding model updated | ALL embedding caches, retrieval caches, reranker caches |

### Version-Based Invalidation (Lazy)

Instead of actively purging, include version in cache key. Old versions naturally expire:

```python
# Old cache key (will never be hit again after version bump)
key_v1 = f"{tenant}:{query_hash}:prompt_v2.2:model_gpt4_0125"

# New cache key (fresh start)
key_v2 = f"{tenant}:{query_hash}:prompt_v2.3:model_gpt4_0125"
```

**Advantage**: No coordination needed. Version bump = instant logical invalidation.
**Disadvantage**: Old entries consume memory until TTL expiry. Size monitoring needed.

### TTL-Based Expiration by Risk Tier

| Risk Tier | Max TTL | Use Case |
|-----------|---------|----------|
| Critical (financial, medical, legal) | 0 (no cache) or 60s max | Trading decisions, medical advice |
| High (PII-adjacent, compliance) | 5 minutes | HR queries, customer data |
| Medium (business analytics) | 1 hour | Revenue reports, dashboards |
| Low (general knowledge, static docs) | 24 hours | Policy documents, FAQs |
| Static (deterministic, no external data) | 7 days+ | Embeddings, parsed documents |

---

## 4. Billion-Request Cache Strategy

At 1B+ requests/day, cache architecture becomes a distributed systems problem:

### Tiered Storage

```
┌─────────────────────────────────────────┐
│  L1: GPU KV-Cache (prefix)              │  < 1ms, limited by HBM
├─────────────────────────────────────────┤
│  L2: Local Process Memory (LRU)         │  < 1ms, per-instance
├─────────────────────────────────────────┤
│  L3: Distributed Redis Cluster          │  1-5ms, shared across instances
├─────────────────────────────────────────┤
│  L4: Regional Cache (Redis/Memcached)   │  5-20ms, per-region
├─────────────────────────────────────────┤
│  L5: Global Cache (with replication)    │  20-100ms, cross-region
├─────────────────────────────────────────┤
│  L6: Cold Storage (S3/Blob)             │  100-500ms, archive
└─────────────────────────────────────────┘
```

### Capacity Planning

```
Daily requests:         1,000,000,000
Unique queries:         ~100,000,000 (90% are repeats with variations)
Semantic dedup:         ~10,000,000 unique intents
Cache hit rate target:  70-85%
Cache size estimate:    10M entries × 4KB avg = 40GB active cache
```

### Hot-Key Protection

Problem: Popular queries (e.g., "What's my balance?") create thundering herd on single cache key.

Solutions:
1. **Key replication**: Replicate hot keys across N shards with suffix `key:replica:{0..N}`
2. **Local caching**: Hot keys promoted to L2 (process memory) automatically
3. **Read-through coalescing**: Multiple readers wait on single backend fetch
4. **Probabilistic early refresh**: Refresh before TTL with probability increasing as expiry approaches

```python
def should_early_refresh(ttl_remaining, total_ttl, request_rate):
    """Probabilistic early refresh to prevent stampede at expiry."""
    staleness_ratio = 1 - (ttl_remaining / total_ttl)
    # Higher request rate = refresh earlier
    threshold = staleness_ratio * min(request_rate / 1000, 1.0)
    return random.random() < threshold
```

---

## 5. Regional Cache Hierarchy

### Architecture

```
Global Control Plane (invalidation coordination)
    │
    ├── US-East Region Cache
    │   ├── AZ-1 Local Cache
    │   ├── AZ-2 Local Cache
    │   └── AZ-3 Local Cache
    │
    ├── EU-West Region Cache
    │   ├── AZ-1 Local Cache
    │   └── AZ-2 Local Cache
    │
    └── APAC Region Cache
        ├── AZ-1 Local Cache
        └── AZ-2 Local Cache
```

### Data Residency Rules

- **Tenant data MUST NOT leave designated region** (GDPR, data sovereignty)
- Cache entries tagged with `data_residency_region`
- Cross-region cache ONLY for non-PII, non-tenant-specific data (e.g., embeddings of public docs)
- Invalidation events ARE cross-region (metadata only, no cached content)

### Consistency Model

- **Eventual consistency** between regions (invalidation propagation: < 5 seconds)
- **Strong consistency** within region for auth decisions
- **Read-your-writes** for same-user within session (sticky routing)

---

## 6. Cache Stampede Protection

### Problem

When a popular cache entry expires, 10,000 concurrent requests all miss and all hit the backend simultaneously.

### Solution 1: Request Coalescing (Single-Flight)

```python
class SingleFlight:
    """Only one request executes; others wait for same result."""
    
    def __init__(self):
        self._in_flight: Dict[str, asyncio.Future] = {}
    
    async def do(self, key: str, fn: Callable) -> Any:
        if key in self._in_flight:
            return await self._in_flight[key]  # Wait for existing
        
        future = asyncio.get_event_loop().create_future()
        self._in_flight[key] = future
        try:
            result = await fn()
            future.set_result(result)
            return result
        finally:
            del self._in_flight[key]
```

### Solution 2: TTL Jitter

Never set exact TTL. Add random jitter so entries don't expire simultaneously:

```python
def jittered_ttl(base_ttl: int, jitter_pct: float = 0.1) -> int:
    jitter = int(base_ttl * jitter_pct)
    return base_ttl + random.randint(-jitter, jitter)
```

### Solution 3: Stale-While-Revalidate

Serve stale data immediately while refreshing in background:

```python
async def get_with_swr(key, compute_fn, ttl, stale_ttl):
    entry = await cache.get(key)
    if entry and not entry.is_expired:
        return entry.value  # Fresh hit
    if entry and entry.age < stale_ttl:
        # Stale but within tolerance — serve stale, refresh async
        asyncio.create_task(refresh_cache(key, compute_fn, ttl))
        return entry.value
    # Fully expired — must compute synchronously
    return await compute_and_cache(key, compute_fn, ttl)
```

### Solution 4: Background Refresh (Proactive)

For known-hot keys, refresh BEFORE expiry:

```python
class ProactiveRefresher:
    """Monitors hot keys and refreshes them before TTL expiry."""
    
    async def monitor_loop(self):
        while True:
            for key in self.hot_keys:
                entry = await cache.get_metadata(key)
                if entry.ttl_remaining < entry.total_ttl * 0.2:
                    await self.refresh(key)
            await asyncio.sleep(1)
```

---

## 7. Stale-Answer Policy by Risk Tier

Not all stale answers are equally dangerous:

| Risk Tier | Stale Tolerance | Policy |
|-----------|----------------|--------|
| **Critical** | 0 seconds | NEVER serve stale. Cache bypass if any doubt. |
| **High** | 30 seconds | Serve stale only if actively refreshing (SWR with tight deadline) |
| **Medium** | 5 minutes | SWR acceptable. Background refresh within 5 min. |
| **Low** | 1 hour | SWR acceptable. Stale up to 1 hour for availability. |
| **Static** | Days | Content unlikely to change. Long TTL. |

### Risk Tier Classification

```python
RISK_TIER_RULES = {
    "critical": [
        "financial_transaction",
        "medical_recommendation",
        "legal_compliance",
        "security_decision",
    ],
    "high": [
        "pii_containing",
        "customer_facing_data",
        "compliance_report",
        "access_control",
    ],
    "medium": [
        "business_analytics",
        "internal_report",
        "aggregated_metrics",
    ],
    "low": [
        "general_knowledge",
        "documentation_lookup",
        "faq_response",
    ],
    "static": [
        "embedding_computation",
        "document_parsing",
        "deterministic_calculation",
    ],
}
```

---

## 8. Cache Safety for Auth and Permissions

### CRITICAL INVARIANTS (Violation = Security Breach)

1. **NEVER share cache entries across tenants** — even if queries are identical
2. **NEVER serve cached response after permission revocation** — even if TTL hasn't expired
3. **NEVER cache aggregated responses that span permission boundaries** — partial access ≠ full cache hit
4. **ALWAYS include permission fingerprint in cache key** — ensures permission-scoped isolation
5. **ALWAYS invalidate on permission change events** — subscribe to IAM event stream

### Permission Revocation Flow

```
1. Admin revokes User-X access to Dataset-Y
2. IAM system emits PermissionRevoked event
3. Cache invalidation service receives event
4. Service computes affected cache keys:
   - All keys where permission_fingerprint included Dataset-Y access
   - All auth decision cache entries for User-X + Dataset-Y
5. Invalidate ALL affected entries (eager, not lazy)
6. Log invalidation for audit trail
7. Verify: next request from User-X for Dataset-Y = cache MISS + fresh auth check
```

### Cross-Tenant Isolation Verification

```python
def verify_cache_isolation(cache_entry, requesting_user):
    """MUST be called before returning any cached response."""
    assert cache_entry.tenant_id == requesting_user.tenant_id, \
        "CRITICAL: Cross-tenant cache access attempted!"
    assert cache_entry.permission_fingerprint == \
        build_permission_fingerprint(requesting_user), \
        "Permission fingerprint mismatch — user permissions may have changed"
    assert cache_entry.freshness_watermark >= \
        get_minimum_freshness(requesting_user.risk_tier), \
        "Cache entry too stale for this risk tier"
```

### Negative Testing Requirements

Every cache implementation MUST pass:
- [ ] User A cannot receive User B's cached response (same tenant)
- [ ] Tenant A cannot receive Tenant B's cached response
- [ ] Revoked user cannot receive previously-cached authorized response
- [ ] Deleted document's content not served from cache
- [ ] Updated document triggers cache invalidation (not stale serve)
- [ ] Admin permission change propagates within SLA (< 5 seconds)

---

## 9. Routing, Batching, Queues, and Backpressure

### Request Routing for Cache Efficiency

**Consistent hashing**: Route same-tenant requests to same cache shard for better hit rates.

```
request → hash(tenant_id + query_category) → cache_shard_N
```

**Sticky sessions**: Same user's requests go to same instance (L1 cache benefits).

### Batch Cache Operations

For high-throughput ingestion:
```python
# BAD: Individual cache operations
for doc in documents:
    await cache.set(doc.key, doc.embedding)  # 10,000 round trips

# GOOD: Batch pipeline
pipeline = cache.pipeline()
for doc in documents:
    pipeline.set(doc.key, doc.embedding, ttl=86400)
await pipeline.execute()  # 1 round trip
```

### Backpressure on Cache Miss

When cache miss rate spikes (cold start, invalidation storm):

1. **Circuit breaker**: If backend error rate > threshold, serve stale (if available) or return graceful degradation
2. **Request shedding**: Drop low-priority cache-miss requests under load
3. **Queue with bounded concurrency**: Max N concurrent backend calls per tenant
4. **Adaptive TTL**: Extend TTLs during high-load periods to reduce miss rate

```python
class CacheBackpressure:
    def __init__(self, max_concurrent_misses=100):
        self.semaphore = asyncio.Semaphore(max_concurrent_misses)
        self.miss_rate = SlidingWindowCounter(window=60)
    
    async def handle_miss(self, key, compute_fn):
        self.miss_rate.increment()
        if self.miss_rate.value > 1000:  # Too many misses
            # Try stale, degrade gracefully
            stale = await self.get_stale(key)
            if stale:
                return stale
        async with self.semaphore:
            return await compute_fn()
```

---

## 10. Operational Considerations

### Metrics to Monitor

| Metric | Alert Threshold | Meaning |
|--------|----------------|---------|
| Hit rate | < 60% | Cache not effective; check key design |
| Latency p99 | > 50ms (Redis) | Cache infrastructure degraded |
| Eviction rate | > 10%/hour | Cache too small; scale up |
| Invalidation lag | > 5s | Stale data being served |
| Cross-tenant violation | > 0 | CRITICAL security incident |
| Memory usage | > 80% | Scale before OOM |
| Stampede events | > 0/min | Coalescing not working |

### Cache Warming Strategies

1. **Predictive warming**: Analyze query patterns, pre-compute popular queries at cache start
2. **Peer warming**: New instance copies hot keys from existing instance
3. **Lazy warming with SWR**: Accept misses initially, serve stale while building
4. **Scheduled warming**: Pre-compute known batch queries (daily reports)

### Cost Model

```
Cost_without_cache = N_requests × (inference_cost + retrieval_cost + tool_cost)
Cost_with_cache = N_requests × (1 - hit_rate) × (inference_cost + retrieval_cost + tool_cost)
                + cache_infrastructure_cost

ROI = (Cost_without_cache - Cost_with_cache) / cache_infrastructure_cost
```

At 80% hit rate with $0.01/request inference cost and 1B requests/day:
- Savings: 800M × $0.01 = $8M/day
- Cache infra cost: ~$50K/day (generous estimate)
- ROI: 160x

**Caching is the single highest-ROI optimization in enterprise AI.**
