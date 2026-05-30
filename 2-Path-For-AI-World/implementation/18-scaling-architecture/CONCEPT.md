# Scaling Architecture for AI Systems

## Why AI Scaling Is Different

Traditional web scaling: `Request → DB query → Response`
AI system scaling: `Request → Auth → Classification → Queue → Agent Loop (N steps) → Per-step: [Retrieval → Reranking → LLM call → Tool calls → Safety check → Memory update → Trace write → Eval sampling] → Streaming response`

**Every single user request triggers a cascade:**

| Component | Multiplier per request |
|-----------|----------------------|
| LLM calls | 3-15 (agent steps, retries, routing) |
| Retrieval queries | 2-8 (per step, multi-index) |
| Reranker calls | 1-5 (per retrieval) |
| Tool invocations | 1-10 (per agent step) |
| Safety checks | 2-4 (input + output + tool args) |
| Trace writes | 10-50 spans per request |
| Embedding calls | 1-3 (query + memory) |
| Eval sampling | 5-10% of requests get full eval |
| Memory updates | 1-3 (conversation + entity + summary) |
| Cache operations | 5-20 reads + 2-5 writes |

A single "simple" chat message at scale becomes 50-100+ downstream operations.

---

## Capacity Formula

### Basic Model

```
Daily Load = DAU × requests_per_user × avg_agent_steps × calls_per_step

Where calls_per_step includes:
  - model_calls (1-3)
  - retrieval_queries (1-2)
  - reranker_calls (1)
  - tool_calls (0-3)
  - safety_checks (2)
  - trace_writes (5-10 spans)
  - eval_sample_probability (0.05-0.10)
  - memory_operations (1-2)
```

### Expanded Capacity Model

```
Total System Load = {
  model_qps:      peak_rps × avg_agent_steps × model_calls_per_step,
  token_throughput: model_qps × avg_tokens_per_call,
  retrieval_qps:  peak_rps × avg_agent_steps × retrieval_per_step,
  reranker_qps:   retrieval_qps × rerank_ratio,
  embedding_qps:  peak_rps × embedding_per_request,
  tool_qps:       peak_rps × avg_agent_steps × tool_probability × tools_per_step,
  safety_qps:     peak_rps × avg_agent_steps × safety_checks_per_step,
  trace_writes:   peak_rps × avg_spans_per_request,
  eval_load:      peak_rps × eval_sample_rate × eval_complexity_multiplier,
  memory_ops:     peak_rps × memory_writes_per_request,
  cache_ops:      peak_rps × (cache_reads + cache_writes),
  queue_depth:    peak_rps × avg_processing_time,
  budget_checks:  peak_rps × budget_check_frequency
}
```

### Example: 1M DAU

```
DAU:                 1,000,000
Requests/user/day:   10
Total daily:         10,000,000
Peak multiplier:     3x (peak hour = 3x average)
Peak hour requests:  10M / 24 * 3 = 1,250,000
Peak RPS:            1,250,000 / 3600 ≈ 347 RPS

Per request (avg 4 agent steps):
  Model calls:       347 × 4 × 1.5 = 2,083 model QPS
  Tokens:            2,083 × 2,000 = 4.2M tokens/sec
  Retrieval:         347 × 4 × 1.2 = 1,665 retrieval QPS
  Reranker:          1,665 × 0.8 = 1,332 reranker QPS
  Tools:             347 × 4 × 0.5 × 2 = 1,388 tool QPS
  Traces:            347 × 25 = 8,675 span writes/sec
  Eval:              347 × 0.05 × 10 = 174 eval operations/sec
  Memory:            347 × 2 = 694 memory ops/sec
  Cache:             347 × 15 = 5,205 cache ops/sec
```

---

## Million-User Architecture Patterns

### Pattern 1: Request Classes

Separate infrastructure by request type:

| Class | Characteristics | Infrastructure |
|-------|----------------|---------------|
| Chat (sync) | Low latency, 1-3 steps | Fast model pool, streaming |
| Retrieval (sync) | Medium latency, heavy vector load | Dedicated vector cluster |
| Tool Action (sync) | Variable latency, external deps | Circuit-breaker pool |
| Eval (async) | High latency, batch-friendly | Batch workers, lower priority |
| Long-running Job (async) | Minutes to hours | Job queue, checkpointing |

### Pattern 2: Cell-Based Tenancy

Divide system into isolated cells:

```
Cell = {
  capacity: 10,000 tenants OR 50 RPS,
  components: [gateway, agent-workers, vector-db-shard, cache, queue],
  isolation: full (no cross-cell traffic for normal ops),
  scaling: add new cells, never grow existing cells beyond limit
}
```

Benefits:
- Blast radius limited to one cell
- Hot tenants isolated
- Cells can be in different regions
- Independent deployment and scaling

### Pattern 3: Queues and Workers

```
Ingress → Priority Queue → Worker Pool → Downstream Services

Queue tiers:
  P0 (real-time):  < 100ms queue time, dedicated workers
  P1 (interactive): < 1s queue time, shared workers
  P2 (background):  < 30s queue time, elastic workers
  P3 (batch):       < 5min queue time, spot/preemptible workers
```

### Pattern 4: Backpressure

When downstream saturates, propagate pressure upstream:

```
Model Provider Slow → Agent worker backs up → Queue grows →
Gateway returns 429 → Client backs off → Load reduces →
System recovers → Resume normal operation
```

Key metrics for backpressure signals:
- Queue depth > threshold
- P99 latency > SLO × 2
- Error rate > 5%
- Concurrent requests > worker capacity × 0.8

### Pattern 5: Model Routing

Route to different models based on context:

```
Simple query     → Small/fast model (GPT-4o-mini, Claude Haiku)
Complex reasoning → Large model (GPT-4o, Claude Opus)
Code generation  → Specialized model (Codex, DeepSeek)
Embedding        → Embedding model pool
Eval/judge       → Judge model (may differ from serving model)
```

Routing criteria: query complexity, token budget remaining, latency SLO, cost tier.

### Pattern 6: Streaming Architecture

```
Client ←SSE/WS← Gateway ←gRPC stream← Agent Worker ←stream← Model Provider

Benefits at scale:
- Time-to-first-token matters more than total latency
- Streaming reduces perceived latency by 5-10x
- Enables progressive rendering
- Allows early termination (user navigates away)
- Reduces memory pressure (don't buffer full response)
```

### Pattern 7: Cache Hierarchy

```
L1: In-process cache (agent worker memory)
    - Recent conversation context
    - Frequently used prompts
    - TTL: request duration

L2: Distributed cache (Redis/Memcached)
    - Semantic cache (similar queries → cached responses)
    - Embedding cache (document → vector)
    - Tool result cache (deterministic tools)
    - TTL: minutes to hours

L3: Persistent cache (DB/Object store)
    - RAG index results (query → doc set)
    - Model response cache (exact match)
    - Computed summaries
    - TTL: hours to days

Hit rates target: L1 30%, L2 40%, L3 15% → Only 15% go to origin
```

### Pattern 8: Hot/Cold Indexes

```
Hot index (in-memory, fast replicas):
  - Active users' documents (accessed in last 7 days)
  - Frequently queried knowledge base sections
  - Recent conversation embeddings

Warm index (SSD, fewer replicas):
  - Documents accessed in last 30 days
  - Full knowledge base
  - Historical conversations

Cold index (object store, on-demand load):
  - Archived documents
  - Old conversation history
  - Compliance/audit data

Promotion/demotion based on access patterns.
```

### Pattern 9: Read Replicas

```
Writes → Primary (single region)
  ↓ async replication
Reads → Replicas (multi-region, near users)

Components with read replicas:
- Vector database (retrieval reads from nearest replica)
- Conversation store (read recent context from local)
- Configuration store (feature flags, model routing rules)
- Knowledge base metadata
```

### Pattern 10: Budget Enforcement

```
Per-tenant budget tracking:
  - Token consumption (input + output)
  - Model tier usage (premium vs standard)
  - Tool call volume
  - Storage consumption

Enforcement points:
  - Gateway: reject if budget exhausted
  - Agent loop: switch to cheaper model if nearing limit
  - Async jobs: pause if budget low
  - Alerts: notify at 80%, 90%, 100%

Architecture:
  - Budget ledger: strongly consistent (no overspend)
  - Usage tracking: eventually consistent (batch updates)
  - Limit checking: cached with short TTL (< 1 min)
```

### Pattern 11: Degraded Modes

```
Level 0 - FULL: All features active
Level 1 - REDUCED: Disable eval sampling, reduce agent steps to 3, skip reranking
Level 2 - MINIMAL: Single model call (no agent loop), cached retrieval only, no tools
Level 3 - ERROR: Return cached responses or error page, queue requests for later

Triggers:
  - Model provider degraded → Level 1-2
  - Vector DB overloaded → Skip retrieval, use cached
  - Multiple components failing → Level 3
  - Cost spike detected → Level 1

Recovery: automatic when metrics return to normal for 5+ minutes
```

### Pattern 12: Regional Failover

```
Primary region: us-east-1
  - All writes, primary indexes
  - Active-active for reads

Secondary region: us-west-2
  - Read replicas, warm standby
  - Async replication (< 30s lag)
  - Can promote to primary in < 5 min

Failover triggers:
  - Region health check failures (3 consecutive)
  - Latency spike > 10x normal for > 2 minutes
  - Error rate > 50% for > 1 minute
  - Manual operator trigger

DNS-based routing with health checks.
```

---

## Billion-Request Architecture

Full strategy for 1B+ requests/day:

### Regional Cells

```
Global:
  - DNS/Anycast routing
  - Global config store
  - Cross-region replication coordinator

Per Region (3-5 regions):
  - Regional gateway cluster
  - Regional queue system
  - Regional cache layer

Per Cell (50-200 cells per region):
  - Cell gateway
  - Agent worker pool (auto-scaling)
  - Vector DB shard
  - Local cache
  - Queue partition
  - Trace collector
```

### Request Flow

```
1. Client → DNS → Nearest regional gateway
2. Gateway: auth, rate limit, classify request, check budget
3. Route to tenant's assigned cell
4. Cell gateway: queue request by priority
5. Worker picks up: execute agent loop
6. Per step: check backpressure, call services, write traces
7. Stream response back through gateway
8. Async: update memory, sample for eval, update budget
```

### Batching Strategy

```
Model calls: batch similar-length requests (up to 50ms wait)
Embeddings: batch documents (up to 100 items)
Trace writes: batch spans (flush every 1s or 100 spans)
Memory updates: batch per-user (flush every 5s)
Eval sampling: batch evaluations (process in background)
Budget updates: batch per-tenant (flush every 10s)
```

### Sharding

```
Vector DB: shard by tenant_id (consistent hashing)
Conversation store: shard by user_id
Queue: partition by cell_id
Cache: shard by key hash
Trace store: shard by time + tenant_id
Budget ledger: shard by tenant_id
```

### Caching Strategy

```
Semantic cache: similar queries (cosine > 0.95) → return cached
Exact cache: identical prompt + context → return cached
Embedding cache: document_hash → vector (avoid re-embedding)
Tool cache: deterministic tool + args → cached result
Config cache: routing rules, feature flags (short TTL)

Expected savings: 30-50% reduction in model calls
```

### Rate Limiting

```
Layers:
  1. Global: total system capacity protection
  2. Per-region: regional capacity protection  
  3. Per-tenant: fair usage enforcement
  4. Per-user: abuse prevention
  5. Per-model: provider limit protection

Algorithm: Token bucket with sliding window
Enforcement: At gateway (fast reject) + at worker (precise)
```

### Backpressure Propagation

```
Detection → Signal → Action → Recovery

Per component:
  Model provider: latency > 5s → reduce batch, shed low-priority
  Vector DB: latency > 500ms → serve from cache, skip rerank
  Tool service: error > 10% → circuit break, return fallback
  Queue: depth > 10K → reject P3, then P2
  Memory store: latency > 1s → defer writes, serve stale
```

### Budget Controls

```
Hard limits: never exceed (enforced at gateway)
Soft limits: alert and degrade (enforced at worker)
Burst allowance: 2x sustained rate for 5 minutes
Overage handling: queue requests, notify, auto-upgrade or reject
```

### Degraded Modes at Scale

```
Component failure isolation:
  - Single cell fails → route tenants to backup cell
  - Model provider degraded → route to alternative, reduce quality
  - Vector DB shard down → serve from cache + replica
  - Queue backing up → shed low priority, increase workers
  - Region down → failover to secondary region
```

---

## Scale Testing Checklist

What MUST be load tested before claiming scale-readiness:

### Component Tests
- [ ] Model provider at 2x expected QPS (with realistic token lengths)
- [ ] Vector DB at 3x expected QPS (with realistic query complexity)
- [ ] Reranker at 2x expected QPS
- [ ] Tool services at 2x expected QPS (with realistic payloads)
- [ ] Queue system at 5x expected throughput
- [ ] Cache at 10x expected ops/sec
- [ ] Trace ingestion at 3x expected span rate
- [ ] Memory store at 2x expected write rate

### Integration Tests
- [ ] Full request path end-to-end at peak load
- [ ] Multi-step agent loop under sustained load
- [ ] Streaming performance with 1000+ concurrent streams
- [ ] Cross-cell communication under load
- [ ] Failover during load (kill a cell, verify redistribution)

### Degradation Tests
- [ ] Model provider returns 429 → backpressure works
- [ ] Vector DB goes slow → cache serves, quality degrades gracefully
- [ ] Tool service circuit breaks → fallback activates
- [ ] Queue saturates → shedding works correctly
- [ ] Cache fails → system still works (slower)
- [ ] One region fails → traffic reroutes

### Isolation Tests
- [ ] Hot tenant doesn't affect cold tenants
- [ ] Large request doesn't block small requests
- [ ] Eval jobs don't compete with serving
- [ ] Background memory updates don't impact latency

### Budget Tests
- [ ] Budget enforcement under concurrent requests (no overspend)
- [ ] Rate limiting fairness across tenants
- [ ] Burst handling within allowance

---

## The Architect Rule

> **"Scaling an agent is not only scaling model calls. Scale state, retrieval, tools, queues, evals, observability, memory, approvals, caches, budgets, and incident controls."**

Every component in the AI system has its own scaling curve, failure mode, and cost profile. The system is only as scalable as its weakest link.

### What This Means in Practice

1. **Model calls** scale with provider limits and cost
2. **State (conversation/memory)** scales with storage and read latency
3. **Retrieval** scales with index size, query complexity, and replica count
4. **Tools** scale with external API limits and timeout handling
5. **Queues** scale with partition count and consumer throughput
6. **Evals** scale independently (async, can be deferred)
7. **Observability** scales with span volume and retention policy
8. **Memory** scales with write throughput and consistency requirements
9. **Approvals** scale with human response time (bottleneck!)
10. **Caches** scale with memory/storage and invalidation complexity
11. **Budgets** scale with ledger consistency requirements
12. **Incident controls** scale with detection speed and automation

Miss any one of these, and you have a scaling bottleneck that brings down the entire system under load.
