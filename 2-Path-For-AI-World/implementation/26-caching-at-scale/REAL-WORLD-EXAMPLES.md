# Real-World Examples: Caching at Scale for AI Systems

## Case Study 1: High-Traffic AI Chatbot Achieving 42% Semantic Cache Hit Rate

### Background

A B2B SaaS company running an AI customer support chatbot handling 2.4M queries/day across 800 enterprise customers. Their GPT-4 costs were $180K/month. They needed to reduce costs without degrading response quality.

### Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  Cache Router                    │
│  1. Normalize query              │
│  2. Exact match check (Redis)    │
│  3. Semantic similarity check    │
│     (Qdrant, threshold=0.96)     │
│  4. On miss → LLM + cache write  │
└─────────────────────────────────┘
    │                    │
    ▼ (hit)              ▼ (miss)
Return cached        Generate response
response             Cache response + embedding
```

### Implementation Details

```python
class SemanticCache:
    def __init__(self):
        self.redis = Redis()  # Exact match layer
        self.qdrant = QdrantClient()  # Semantic layer
        self.similarity_threshold = 0.96  # Tuned via A/B test
        self.ttl_hours = 72  # Cache expiry
        self.embedding_model = "text-embedding-3-small"  # Fast, cheap
    
    async def get(self, query: str, tenant_id: str) -> Optional[CacheResult]:
        """Two-layer cache lookup."""
        normalized = self.normalize(query)
        
        # Layer 1: Exact match (sub-millisecond)
        exact_key = f"cache:exact:{tenant_id}:{hashlib.sha256(normalized.encode()).hexdigest()}"
        exact_hit = await self.redis.get(exact_key)
        if exact_hit:
            self.metrics.increment("cache_hit_exact")
            return CacheResult(response=json.loads(exact_hit), source="exact")
        
        # Layer 2: Semantic similarity
        query_embedding = await self.embed(normalized)
        results = await self.qdrant.search(
            collection_name=f"cache_{tenant_id}",
            query_vector=query_embedding,
            limit=1,
            score_threshold=self.similarity_threshold,
        )
        
        if results:
            self.metrics.increment("cache_hit_semantic")
            return CacheResult(
                response=results[0].payload["response"],
                source="semantic",
                similarity=results[0].score,
                original_query=results[0].payload["query"],
            )
        
        self.metrics.increment("cache_miss")
        return None
    
    async def put(self, query: str, response: str, tenant_id: str):
        """Store in both layers."""
        normalized = self.normalize(query)
        embedding = await self.embed(normalized)
        
        # Exact cache
        exact_key = f"cache:exact:{tenant_id}:{hashlib.sha256(normalized.encode()).hexdigest()}"
        await self.redis.setex(exact_key, self.ttl_hours * 3600, json.dumps(response))
        
        # Semantic cache
        await self.qdrant.upsert(
            collection_name=f"cache_{tenant_id}",
            points=[{
                "id": str(uuid4()),
                "vector": embedding,
                "payload": {
                    "query": query,
                    "response": response,
                    "created_at": datetime.utcnow().isoformat(),
                    "tenant_id": tenant_id,
                }
            }]
        )
    
    def normalize(self, query: str) -> str:
        """Normalize whitespace, casing, punctuation for better exact matching."""
        query = query.lower().strip()
        query = re.sub(r'\s+', ' ', query)
        query = re.sub(r'[?!.]+$', '', query)  # Remove trailing punctuation
        return query
```

### Similarity Threshold Tuning

The team ran an A/B test across 100K queries with human evaluators:

| Threshold | Hit Rate | False Positive Rate | User Satisfaction |
|-----------|----------|--------------------|--------------------|
| 0.90 | 58% | 12.3% | 3.2/5 (too many wrong answers) |
| 0.93 | 51% | 5.1% | 3.8/5 |
| 0.95 | 45% | 2.2% | 4.3/5 |
| 0.96 | 42% | 1.1% | 4.5/5 (production choice) |
| 0.98 | 28% | 0.3% | 4.6/5 (diminishing returns) |
| 0.99 | 12% | 0.05% | 4.6/5 |

**Key insight**: The jump from 0.96 to 0.98 lost 14 percentage points of hit rate but only reduced false positives by 0.8pp. The 0.96 threshold was the optimal tradeoff.

### Cache Warming Strategy

```python
class CacheWarmer:
    """Pre-populate cache with predicted high-traffic queries."""
    
    async def warm_from_history(self, tenant_id: str, days_back=7):
        """Replay last week's top queries."""
        top_queries = await self.analytics.get_top_queries(
            tenant_id, days=days_back, limit=500
        )
        
        for query_group in top_queries:
            # Only warm if query appeared 3+ times
            if query_group["count"] >= 3:
                response = await self.generate_response(query_group["query"], tenant_id)
                await self.cache.put(query_group["query"], response, tenant_id)
    
    async def warm_from_docs_update(self, tenant_id: str, updated_docs: list[str]):
        """When docs change, regenerate affected cached responses."""
        # Find cached entries that referenced the updated documents
        affected = await self.find_cache_entries_citing(tenant_id, updated_docs)
        
        for entry in affected:
            # Invalidate old entry
            await self.cache.invalidate(entry.id)
            # Re-generate with updated context
            new_response = await self.generate_response(entry.query, tenant_id)
            await self.cache.put(entry.query, new_response, tenant_id)
```

### Results

| Metric | Before Cache | After Cache | Improvement |
|--------|-------------|-------------|-------------|
| Monthly LLM cost | $180,000 | $104,000 | -42% |
| p50 response latency | 2.8s | 180ms (hits), 2.9s (misses) | Avg: -58% |
| p99 response latency | 8.2s | 340ms (hits), 8.5s (misses) | — |
| User satisfaction | 4.1/5 | 4.5/5 | +10% (faster = happier) |
| Cache infrastructure cost | $0 | $2,800/mo | — |
| Net savings | — | — | $73,200/mo |

---

## Case Study 2: Multi-Layer Caching for Enterprise RAG

### Architecture Overview

A financial services company built a three-layer cache for their RAG system serving 12,000 analysts:

```
Query Flow:
┌─────────────────────────────────────────────────────────────────┐
│ L1: Exact Match Cache (Redis)                                    │
│ Key: hash(normalized_query + user_role + date_bucket)            │
│ TTL: 1 hour | Hit rate: 15% | Latency: <1ms                     │
├─────────────────────────────────────────────────────────────────┤
│ L2: Semantic Cache (Qdrant + Redis metadata)                     │
│ Similarity threshold: 0.97 | Additional filter: same user_role   │
│ TTL: 4 hours | Hit rate: 22% | Latency: 8ms                     │
├─────────────────────────────────────────────────────────────────┤
│ L3: Retrieval Result Cache (Redis)                               │
│ Key: hash(query_embedding, top_k, filters)                       │
│ Stores: retrieved chunk IDs + scores (not full LLM response)     │
│ TTL: 24 hours | Hit rate: 35% | Latency: 2ms                    │
├─────────────────────────────────────────────────────────────────┤
│ Full Pipeline (on complete miss)                                  │
│ Embed → Retrieve → Rerank → Generate | Latency: 3.2s            │
└─────────────────────────────────────────────────────────────────┘
```

### Why Three Layers?

| Layer | What It Caches | Why It Exists |
|-------|---------------|---------------|
| L1 | Full response | Identical queries (common in enterprises with shared workflows) |
| L2 | Full response | Semantically equivalent queries ("Q3 revenue" ≈ "revenue in Q3") |
| L3 | Retrieval results only | Same documents relevant, but generation might differ (user context) |

L3 is the key innovation: even on a semantic cache miss, if the retrieval results are cached, you skip the most expensive step (embedding + vector search + reranking) and only pay for generation.

```python
class ThreeLayerCache:
    async def query(self, query: str, user: User) -> Response:
        # L1: Exact
        l1_key = self.l1_key(query, user.role)
        if hit := await self.redis.get(l1_key):
            return Response(json.loads(hit), cache_layer="L1")
        
        # L2: Semantic
        query_emb = await self.embed(query)
        semantic_hit = await self.semantic_search(
            query_emb, user.role, threshold=0.97
        )
        if semantic_hit:
            # Store as exact match too for next identical query
            await self.redis.setex(l1_key, 3600, semantic_hit.response)
            return Response(semantic_hit.response, cache_layer="L2")
        
        # L3: Retrieval cache
        retrieval_key = self.l3_key(query_emb, user.filters)
        cached_chunks = await self.redis.get(retrieval_key)
        
        if cached_chunks:
            # Skip retrieval, go straight to generation
            chunks = json.loads(cached_chunks)
            response = await self.generate(query, chunks, user)
            # Populate L1 and L2 with the generated response
            await self.populate_l1_l2(query, query_emb, response, user)
            return Response(response, cache_layer="L3")
        
        # Full miss: embed → retrieve → rerank → generate
        chunks = await self.retrieve_and_rerank(query_emb, user.filters)
        response = await self.generate(query, chunks, user)
        
        # Populate all layers
        await self.redis.setex(retrieval_key, 86400, json.dumps(chunks))
        await self.populate_l1_l2(query, query_emb, response, user)
        
        return Response(response, cache_layer="MISS")
```

### Performance Breakdown

| Scenario | Probability | Latency | LLM Cost |
|----------|------------|---------|----------|
| L1 hit | 15% | 1ms | $0 |
| L2 hit | 22% | 8ms | $0 |
| L3 hit (retrieval cached) | 23% | 850ms | Generation only |
| Full miss | 40% | 3,200ms | Full pipeline |

**Weighted average latency**: 0.15(1) + 0.22(8) + 0.23(850) + 0.40(3200) = **1,478ms** vs 3,200ms without caching.

---

## Semantic Cache Implementation: Redis + Vector Similarity

### Production Architecture

```python
import numpy as np
from redis import Redis
from redis.commands.search.field import VectorField, TextField, NumericField
from redis.commands.search.query import Query

class RedisSemanticCache:
    """
    Uses Redis Stack with vector similarity search.
    Single infrastructure dependency, simpler than Redis + separate vector DB.
    """
    
    def __init__(self, redis_url: str, dimension: int = 1536):
        self.redis = Redis.from_url(redis_url)
        self.dimension = dimension
        self.index_name = "idx:semantic_cache"
        self._ensure_index()
    
    def _ensure_index(self):
        """Create RediSearch index with vector field."""
        try:
            self.redis.ft(self.index_name).info()
        except:
            schema = (
                TextField("$.query", as_name="query"),
                TextField("$.response", as_name="response"),
                TextField("$.tenant_id", as_name="tenant_id"),
                NumericField("$.created_at", as_name="created_at"),
                VectorField(
                    "$.embedding",
                    "FLAT",  # FLAT for <100K vectors, HNSW for more
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.dimension,
                        "DISTANCE_METRIC": "COSINE",
                    },
                    as_name="embedding",
                ),
            )
            self.redis.ft(self.index_name).create_index(
                schema, definition=IndexDefinition(prefix=["cache:"], index_type=IndexType.JSON)
            )
    
    async def search(self, query_embedding: list[float], tenant_id: str, threshold: float = 0.96):
        """Find semantically similar cached query."""
        query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # Vector similarity search with tenant filter
        q = (
            Query(f"(@tenant_id:{{{tenant_id}}})=>[KNN 1 @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("query", "response", "score")
            .dialect(2)
        )
        
        results = self.redis.ft(self.index_name).search(
            q, query_params={"vec": query_bytes}
        )
        
        if results.docs:
            doc = results.docs[0]
            similarity = 1 - float(doc.score)  # Redis returns distance, not similarity
            if similarity >= threshold:
                return {
                    "response": doc.response,
                    "similarity": similarity,
                    "original_query": doc.query,
                }
        return None
```

### Why Redis Stack Over a Separate Vector DB?

| Factor | Redis Stack | Qdrant/Pinecone |
|--------|-------------|-----------------|
| Ops complexity | Single system | Two systems to manage |
| Latency | Sub-millisecond (in-memory) | 5-15ms (network hop) |
| Scale limit | ~1M vectors per node | Billions |
| Cost at 100K vectors | ~$50/mo (existing Redis) | $70-150/mo (managed vector DB) |
| TTL support | Native | Manual cleanup jobs |

**Recommendation**: Use Redis Stack for caches under 1M entries. Use a dedicated vector DB when your cache grows beyond that or you need advanced filtering.

---

## Cache Invalidation Challenges in AI Systems

### The Three Triggers for Staleness

**1. Source Document Updated**

```python
class DocumentUpdateHandler:
    """When a knowledge base document changes, invalidate affected cache entries."""
    
    async def on_document_update(self, doc_id: str, tenant_id: str):
        # Find all cache entries that cited this document
        affected_entries = await self.cache_metadata.find({
            "tenant_id": tenant_id,
            "cited_doc_ids": {"$contains": doc_id}
        })
        
        # Strategy: Invalidate immediately, optionally re-warm
        for entry in affected_entries:
            await self.cache.invalidate(entry.cache_id)
            
            # Re-warm if this was a high-traffic query
            if entry.hit_count > 10:
                asyncio.create_task(
                    self.rewarm(entry.query, tenant_id)
                )
        
        self.metrics.gauge("cache_invalidations_doc_update", len(affected_entries))
```

**2. Model Changed (upgraded LLM or embedding model)**

```python
class ModelChangeInvalidator:
    """Nuclear option: model change invalidates ALL semantic cache entries."""
    
    async def on_model_change(self, old_model: str, new_model: str, change_type: str):
        if change_type == "embedding_model":
            # ALL cache entries are invalid (embedding space changed)
            await self.cache.flush_all_semantic()
            # Exact match cache can stay (responses might still be valid)
            
        elif change_type == "generation_model":
            # Responses may differ, but retrieval results still valid
            # Strategy: Keep L3 (retrieval cache), flush L1+L2 (response caches)
            await self.cache.flush_layers(["L1", "L2"])
            
        elif change_type == "system_prompt":
            # Similar to model change — all generated responses are stale
            await self.cache.flush_layers(["L1", "L2"])
```

**3. Policy or Permission Change**

```python
class PolicyChangeHandler:
    """When access policies change, some cached responses become unauthorized."""
    
    async def on_role_change(self, user_id: str, old_role: str, new_role: str):
        # If user was DOWNGRADED, they might have cached responses
        # from when they had higher access
        if self.is_downgrade(old_role, new_role):
            await self.cache.invalidate_for_user(user_id)
    
    async def on_document_classification_change(self, doc_id: str, new_classification: str):
        # Document became more restricted
        # Invalidate any cache entries citing it for users who no longer have access
        affected = await self.find_unauthorized_cache_entries(doc_id, new_classification)
        for entry in affected:
            await self.cache.invalidate(entry.cache_id)
```

### The Metadata Problem

To invalidate correctly, you MUST store metadata about what went into each cached response:

```python
@dataclass
class CacheEntry:
    cache_id: str
    query: str
    query_embedding: list[float]
    response: str
    tenant_id: str
    user_role: str  # For permission-based invalidation
    cited_doc_ids: list[str]  # For document-update invalidation
    model_version: str  # For model-change invalidation
    system_prompt_hash: str  # For prompt-change invalidation
    created_at: datetime
    hit_count: int
    last_hit_at: datetime
```

Without this metadata, you're forced to flush the entire cache on any change — defeating the purpose.

---

## Cache Safety: Multi-Tenant Isolation

### The Risk

Tenant A asks: "What were our Q3 revenue numbers?"
The response (containing Tenant A's confidential data) gets cached.
Tenant B asks: "What were our Q3 revenue numbers?"
Without proper isolation, Tenant B could receive Tenant A's numbers from cache.

### Defense in Depth

```python
class TenantIsolatedCache:
    """Multiple layers of tenant isolation for cache safety."""
    
    # Defense 1: Separate collections per tenant
    def collection_name(self, tenant_id: str) -> str:
        return f"cache_tenant_{tenant_id}"  # Physical isolation
    
    # Defense 2: Tenant ID in every cache key
    def cache_key(self, query: str, tenant_id: str) -> str:
        return f"cache:{tenant_id}:{hashlib.sha256(query.encode()).hexdigest()}"
    
    # Defense 3: Filter on every query (belt + suspenders)
    async def semantic_search(self, embedding, tenant_id: str):
        results = await self.qdrant.search(
            collection_name=self.collection_name(tenant_id),
            query_vector=embedding,
            query_filter=Filter(
                must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
            ),
            limit=1,
        )
        
        # Defense 4: Verify tenant_id in result payload
        if results and results[0].payload["tenant_id"] != tenant_id:
            self.alert("CRITICAL: Cross-tenant cache leak detected!")
            return None
        
        return results
    
    # Defense 5: Audit logging
    async def log_cache_access(self, query, tenant_id, hit, result_tenant):
        await self.audit_log.write({
            "event": "cache_access",
            "query_tenant": tenant_id,
            "result_tenant": result_tenant,
            "hit": hit,
            "timestamp": datetime.utcnow(),
            "cross_tenant_violation": tenant_id != result_tenant,
        })
```

### Shared Cache for Public Knowledge

Some content is tenant-agnostic (product docs, public FAQs). A separate shared cache avoids redundant per-tenant caching:

```python
class HybridTenantCache:
    async def get(self, query: str, tenant_id: str, query_type: str):
        if query_type == "public_knowledge":
            # Shared cache — safe, no tenant-specific data
            return await self.shared_cache.get(query)
        else:
            # Tenant-isolated cache
            return await self.tenant_cache.get(query, tenant_id)
    
    def classify_query(self, query: str, retrieved_docs: list) -> str:
        """Determine if response will contain tenant-specific data."""
        for doc in retrieved_docs:
            if doc.metadata.get("visibility") == "tenant_private":
                return "private"
        return "public_knowledge"
```

---

## Prompt Caching Economics: OpenAI and Anthropic Features

### How Prompt Caching Works

Both OpenAI and Anthropic offer server-side prompt caching where repeated system prompts / prefixes are cached and charged at reduced rates:

**Anthropic (Claude):**
- Cache write: 25% premium on first request
- Cache read: 90% discount on subsequent requests
- Cache TTL: 5 minutes (extended on each hit)
- Minimum cacheable prefix: 1024 tokens (Sonnet), 2048 tokens (Haiku)

**OpenAI:**
- Automatic for prompts >1024 tokens
- Cached tokens: 50% discount
- No explicit TTL (managed automatically)

### When It Matters: Real Cost Analysis

**Scenario**: RAG system with 4,000 token system prompt + 3,000 token few-shot examples + variable retrieval context + user query.

```
Without prompt caching:
  System prompt (4,000 tokens) + few-shot (3,000) + context (2,000) + query (100)
  = 9,100 input tokens per request
  At $3/M tokens (Claude Sonnet): $0.0273 per request
  At 100K requests/day: $2,730/day = $81,900/month

With prompt caching (assuming 90% cache hit on 7,000 token prefix):
  First request: 7,000 × 1.25 + 2,100 × 1.0 = 10,850 "effective tokens"
  Subsequent: 7,000 × 0.10 + 2,100 × 1.0 = 2,800 "effective tokens"
  
  Blended rate per request: (0.10 × 10,850 + 0.90 × 2,800) × $3/M
  = (1,085 + 2,520) × $3/M = $0.01082 per request
  At 100K requests/day: $1,082/day = $32,445/month

Savings: $49,455/month (60% reduction)
```

### Implementation Pattern

```python
class PromptCacheOptimizer:
    """Structure prompts to maximize cache hit rate."""
    
    def build_messages(self, query: str, context: list[str], user: User):
        """
        KEY PRINCIPLE: Put stable content FIRST (cacheable prefix),
        variable content LAST.
        """
        return [
            {
                "role": "system",
                "content": self.system_prompt,  # 4,000 tokens — STABLE
                # Mark as cacheable (Anthropic-specific)
                "cache_control": {"type": "ephemeral"}
            },
            {
                "role": "user", 
                "content": self.few_shot_examples,  # 3,000 tokens — STABLE
                "cache_control": {"type": "ephemeral"}
            },
            {
                # Variable content comes after cached prefix
                "role": "user",
                "content": f"Context:\n{chr(10).join(context)}\n\nQuestion: {query}"
            }
        ]
```

### When Prompt Caching Doesn't Help

- Prompts under 1024 tokens (below minimum)
- Highly variable system prompts (per-user personalization in the prefix)
- Low traffic (<1 request per 5 minutes to same prefix)
- Very short conversations where the prompt is a small fraction of total tokens

---

## Cache Warming Strategies

### Monday Morning Problem

An enterprise analytics AI sees a spike every Monday at 9 AM as executives ask about weekend metrics. Without warming, the first 500 queries all hit cold cache → 500 expensive LLM calls in parallel → rate limits hit → degraded experience.

```python
class ScheduledCacheWarmer:
    """Pre-compute responses for predictable query patterns."""
    
    # Run Sunday 11 PM: warm cache for Monday morning
    @scheduler.cron("0 23 * * 0")
    async def warm_monday_queries(self):
        # Historical analysis: these queries appear every Monday
        monday_queries = [
            "What was our weekend revenue?",
            "How many new signups this week?",
            "Show me the conversion funnel for last 7 days",
            "What's our current MRR?",
            "Any critical incidents over the weekend?",
        ]
        
        for tenant in await self.get_active_tenants():
            for query in monday_queries:
                try:
                    response = await self.generate_response(query, tenant.id)
                    await self.cache.put(query, response, tenant.id)
                except Exception as e:
                    logger.warning(f"Warm failed for {tenant.id}: {e}")
                
                # Rate limit: don't overwhelm LLM provider
                await asyncio.sleep(0.5)
    
    # Event-driven warming: when a document is updated
    async def warm_on_doc_update(self, doc_id: str, tenant_id: str):
        """Find queries that typically reference this doc and re-cache them."""
        related_queries = await self.query_log.find_queries_citing(doc_id, limit=20)
        
        for query_record in related_queries:
            if query_record.frequency > 5:  # Only warm popular queries
                response = await self.generate_response(query_record.query, tenant_id)
                await self.cache.put(query_record.query, response, tenant_id)
```

### Predictive Warming Based on Query Patterns

```python
class PredictiveWarmer:
    """Learn query patterns and pre-cache likely next queries."""
    
    async def warm_follow_up_queries(self, query: str, tenant_id: str):
        """
        After answering "What was Q3 revenue?", users often ask:
        - "How does that compare to Q2?"
        - "Break that down by region"
        - "What's the growth rate?"
        """
        likely_followups = await self.predict_followups(query)
        
        # Warm top 3 predicted follow-ups in background
        for followup in likely_followups[:3]:
            if followup.confidence > 0.7:
                asyncio.create_task(
                    self.warm_single(followup.query, tenant_id)
                )
```

---

## KV-Cache Sharing in Inference Servers

### The Problem

When self-hosting LLMs (vLLM, TGI, TensorRT-LLM), each request computes KV-cache from scratch for the entire prompt. If 100 requests share the same 4,000-token system prompt, you compute those same 4,000 tokens 100 times.

### How vLLM Automatic Prefix Caching Works

```
Request 1: [System Prompt (4K tokens)] + [User Context A (2K)] + [Query A]
Request 2: [System Prompt (4K tokens)] + [User Context B (1K)] + [Query B]

Without prefix caching:
  Request 1: Process all 6K+ tokens from scratch
  Request 2: Process all 5K+ tokens from scratch

With prefix caching:
  Request 1: Compute KV-cache for system prompt (4K), store in GPU memory
  Request 2: Reuse cached KV for system prompt, only compute 1K+ new tokens
  
  Speedup: ~40% reduction in time-to-first-token for requests sharing prefix
```

### vLLM Configuration

```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3.1-70B-Instruct",
    enable_prefix_caching=True,  # Key flag
    gpu_memory_utilization=0.90,
    # Prefix cache uses available GPU memory as LRU cache
    # More GPU memory = more prefixes cached = higher hit rate
)

# All requests with the same system prompt prefix share KV-cache
system_prompt = "You are a helpful financial analyst..." * 500  # Long prompt

# These share the cached prefix
for user_query in user_queries:
    output = llm.generate(
        f"{system_prompt}\n\nUser: {user_query}\nAssistant:",
        SamplingParams(max_tokens=500)
    )
```

### Production Impact

Measurements from a company running Llama 3.1 70B on 8x H100:

| Metric | Without Prefix Caching | With Prefix Caching |
|--------|----------------------|-------------------|
| Time to first token (p50) | 1,200ms | 420ms |
| Throughput (requests/sec) | 12 | 19 |
| GPU memory for KV cache | 24 GB | 38 GB (more KV stored) |
| System prompt: 4K tokens shared | Recomputed every request | Computed once, cached |

---

## Cache Coherence in Distributed Systems

### The Challenge

An AI system deployed across 3 regions (US-East, EU-West, AP-Southeast). When a document is updated in US-East, cached responses in EU-West referencing that document become stale.

### Architecture: Event-Driven Invalidation

```python
class DistributedCacheCoordinator:
    """Cross-region cache invalidation via event bus."""
    
    def __init__(self, region: str):
        self.region = region
        self.event_bus = KafkaBus(topic="cache-invalidation")  # Global topic
        self.local_cache = LocalSemanticCache()
    
    async def invalidate_globally(self, invalidation: CacheInvalidation):
        """Publish invalidation event for all regions."""
        event = {
            "type": "invalidate",
            "pattern": invalidation.pattern,  # e.g., {"doc_ids": ["doc_123"]}
            "source_region": self.region,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": invalidation.reason,
        }
        await self.event_bus.publish(event)
        
        # Also invalidate locally immediately (don't wait for event roundtrip)
        await self.local_cache.invalidate(invalidation.pattern)
    
    async def handle_invalidation_event(self, event: dict):
        """Process invalidation events from other regions."""
        if event["source_region"] == self.region:
            return  # Already handled locally
        
        await self.local_cache.invalidate(event["pattern"])
        self.metrics.increment("cross_region_invalidation", 
                              tags={"source": event["source_region"]})
```

### Consistency Model Choices

| Model | Behavior | Use When |
|-------|----------|----------|
| Eventual (5-30s lag) | Invalidation propagates asynchronously | Most AI caches (stale for seconds is acceptable) |
| Best-effort immediate | Invalidation + short TTL as safety net | Sensitive data, compliance requirements |
| No cross-region sharing | Each region has independent cache | Simplest, highest cache miss rate |

**Most AI systems choose eventual consistency** because:
1. A 10-second stale response in a chatbot rarely matters
2. Strong consistency across regions adds 100-300ms to every cache write
3. The TTL provides a maximum staleness bound regardless

---

## Measuring Cache Effectiveness

### The Three Metrics That Matter

```python
class CacheMetricsDashboard:
    """Real-time monitoring of cache health."""
    
    def compute_metrics(self, window_minutes=60):
        hits = self.counter("cache_hit", window_minutes)
        misses = self.counter("cache_miss", window_minutes)
        false_positives = self.counter("cache_false_positive", window_minutes)
        
        return {
            # 1. Hit Rate — are we saving money?
            "hit_rate": hits / (hits + misses),
            # Target: 30-50% for semantic cache
            
            # 2. Cache Miss Latency — is cache overhead acceptable?
            "miss_latency_overhead_ms": (
                self.percentile("latency_on_miss", 50) - 
                self.percentile("latency_no_cache_baseline", 50)
            ),
            # Target: <50ms overhead (embedding + vector search on miss)
            
            # 3. Stale Response Rate — are we serving wrong answers?
            "stale_rate": false_positives / hits if hits > 0 else 0,
            # Target: <2%
            
            # Derived: Cost effectiveness
            "cost_per_cache_hit": self.cache_infrastructure_cost / hits,
            "cost_per_llm_call": self.llm_cost / misses,
            "roi": (self.llm_cost_saved - self.cache_infrastructure_cost) / self.cache_infrastructure_cost,
        }
```

### Dashboard Alerts

```yaml
# Prometheus alerting rules
groups:
  - name: cache_health
    rules:
      - alert: CacheHitRateDrop
        expr: cache_hit_rate < 0.25
        for: 15m
        annotations:
          summary: "Cache hit rate dropped below 25%"
          # Possible causes: TTL too short, threshold too high, 
          # query distribution shifted

      - alert: CacheStaleRateHigh
        expr: cache_false_positive_rate > 0.05
        for: 5m
        annotations:
          summary: "5%+ of cached responses are stale/incorrect"
          # Action: Increase similarity threshold or reduce TTL

      - alert: CacheMissLatencyHigh  
        expr: cache_miss_latency_p99 > 200
        for: 10m
        annotations:
          summary: "Cache miss adds >200ms overhead"
          # Possible: Vector DB overloaded, embedding service slow
```

### A/B Testing Cache Quality

```python
class CacheQualityABTest:
    """Continuously validate that cached responses match fresh responses."""
    
    async def shadow_validate(self, query: str, cached_response: str, tenant_id: str):
        """On 5% of cache hits, also generate fresh and compare."""
        if random.random() > 0.05:
            return
        
        fresh_response = await self.generate_fresh(query, tenant_id)
        
        # Semantic similarity between cached and fresh
        similarity = await self.compute_similarity(cached_response, fresh_response)
        
        self.metrics.histogram("cache_freshness_similarity", similarity)
        
        if similarity < 0.85:
            # Cached response has drifted significantly from fresh
            self.metrics.increment("cache_stale_detected")
            await self.cache.invalidate_query(query, tenant_id)
```

---

## When NOT to Cache

### 1. Personalized Responses

```python
def should_cache(self, query: str, context: QueryContext) -> bool:
    # DON'T cache if response depends on user-specific data
    if context.uses_personal_data:
        return False  # "Show my account balance" — unique per user
    
    # DON'T cache if response includes user's name or details
    if context.response_contains_pii:
        return False
```

**Why**: Personalized responses cached and served to another user = privacy violation + wrong answer.

### 2. Time-Sensitive Queries

```python
def is_time_sensitive(self, query: str) -> bool:
    time_indicators = [
        "right now", "current", "today", "this week", "latest",
        "live", "real-time", "as of now"
    ]
    return any(indicator in query.lower() for indicator in time_indicators)

# "What's the current stock price of AAPL?" — stale in seconds
# "What were the top stories today?" — stale in hours
```

### 3. High-Risk Answers Requiring Fresh Retrieval

```python
HIGH_RISK_CATEGORIES = [
    "medical_advice",
    "legal_compliance", 
    "financial_regulations",
    "safety_critical",
]

def should_bypass_cache(self, query: str, classification: str) -> bool:
    if classification in HIGH_RISK_CATEGORIES:
        # Always retrieve fresh documents — regulations may have changed
        return True
    
    # Also bypass for queries about recent events
    if self.references_recent_events(query):
        return True
    
    return False
```

### 4. Multi-Turn Conversations with State

```python
def cacheable_in_conversation(self, messages: list[dict]) -> bool:
    # First message in a conversation: potentially cacheable
    if len(messages) <= 2:  # system + user
        return True
    
    # Multi-turn: response depends on full conversation history
    # Caching would require matching entire conversation, not just last query
    # Hit rate drops to <2% — not worth the overhead
    return False
```

### 5. Exploratory/Creative Queries

```python
UNCACHEABLE_INTENTS = [
    "brainstorm",    # "Give me 10 ideas for..." — user wants variety
    "creative",      # "Write a poem about..." — uniqueness is the value
    "random",        # "Surprise me with..." — repetition defeats purpose
]
```

### Decision Matrix

| Query Type | Cache? | Reason |
|-----------|--------|--------|
| "How do I reset my password?" | Yes | Same answer for everyone |
| "What's my account balance?" | No | Per-user |
| "Summarize our company's Q3 report" | Yes (per-tenant) | Same within tenant |
| "What's the weather right now?" | No | Changes constantly |
| "Give me 5 creative names for my startup" | No | Users expect variety |
| "What does error code E-4012 mean?" | Yes | Factual, stable |
| "Should I take ibuprofen for my headache?" | No | Medical risk, needs fresh context |
| "Explain our refund policy" | Yes | Stable policy document |
| "What changed in the last deployment?" | Short TTL | Valid briefly, stale quickly |

---

## Summary: Cache Architecture Decision Framework

| Decision | Recommendation | Key Consideration |
|----------|---------------|-------------------|
| Cache type | Semantic (0.96 threshold) + Exact | Exact alone misses paraphrases |
| Storage backend | Redis Stack for <1M entries, dedicated vector DB for more | Operational simplicity vs scale |
| TTL | 1-4 hours for responses, 24h for retrieval results | Shorter = fresher, longer = higher hit rate |
| Tenant isolation | Separate collections + filter + verify | Never share private data |
| Invalidation | Event-driven + TTL safety net | Metadata on cited sources required |
| Warming | Schedule-based + event-driven | Focus on top 500 queries per tenant |
| Monitoring | Hit rate, stale rate, miss overhead | Alert on stale rate > 2% |
| Multi-region | Eventual consistency via event bus | 5-30s staleness acceptable for AI |
| When to skip | Personal, time-sensitive, high-risk, creative | Default to caching, whitelist exclusions |
