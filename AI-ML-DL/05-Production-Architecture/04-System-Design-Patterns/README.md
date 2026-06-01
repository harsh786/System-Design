# System Design Patterns for ML

## Overview

ML system design patterns solve recurring architectural challenges in production ML. These patterns address the unique complexities of ML systems: non-determinism, data dependencies, model lifecycle management, and the need for both batch and real-time computation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML SYSTEM DESIGN PATTERN CATEGORIES                                        │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Serving Patterns│  │  Data Patterns   │  │ Reliability      │        │
│  │  - Microservices │  │  - Lambda/Kappa  │  │ - Circuit Breaker│        │
│  │  - Ensemble      │  │  - Feature comp  │  │ - Fallback       │        │
│  │  - Multi-model   │  │  - Event-driven  │  │ - Rate limiting  │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Scale Patterns  │  │  Domain Patterns │  │  Update Patterns │        │
│  │  - Embedding     │  │  - Search/Rec    │  │  - Online learning│       │
│  │  - Caching       │  │  - Fraud/Risk    │  │  - Continual      │       │
│  │  - Sharding      │  │  - NLP serving   │  │  - Incremental    │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Microservices for ML

### ML Microservice Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML MICROSERVICES ARCHITECTURE                                              │
│                                                                              │
│  ┌──────────┐                                                              │
│  │  Client  │                                                              │
│  └────┬─────┘                                                              │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────┐                                                          │
│  │  API Gateway │  (auth, rate limit, routing)                            │
│  └──────┬───────┘                                                          │
│         │                                                                   │
│    ┌────┼────────────────────────────┐                                    │
│    │    │                            │                                    │
│    ▼    ▼                            ▼                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                         │
│  │  Feature   │  │  Prediction│  │  Feedback  │                         │
│  │  Service   │  │  Service   │  │  Service   │                         │
│  │            │  │            │  │            │                         │
│  │ - Compute  │  │ - Load     │  │ - Collect  │                         │
│  │   features │  │   model    │  │   labels   │                         │
│  │ - Cache    │  │ - Inference│  │ - Store    │                         │
│  │ - Serve    │  │ - Post-proc│  │ - Trigger  │                         │
│  └─────┬──────┘  └─────┬──────┘  └────────────┘                         │
│        │                │                                                  │
│        ▼                ▼                                                  │
│  ┌──────────┐    ┌──────────┐                                            │
│  │  Feature │    │  Model   │                                            │
│  │  Store   │    │  Store   │                                            │
│  └──────────┘    └──────────┘                                            │
│                                                                              │
│  Service Boundaries:                                                       │
│  - Feature Service: Owns feature computation logic                        │
│  - Prediction Service: Owns model loading and inference                   │
│  - Feedback Service: Owns label collection and storage                    │
│  - Training Service: Owns model training pipeline                         │
│  - Monitoring Service: Owns drift detection and alerting                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### When to Use Microservices vs Monolith for ML

| Factor | Microservices | Monolith |
|--------|--------------|----------|
| Team size | >5 ML engineers | 1-3 ML engineers |
| Models in production | >5 models | 1-3 models |
| Deploy frequency | Daily per service | Weekly for whole system |
| Scaling needs | Different per component | Uniform |
| Feature reuse | Multiple teams share features | Single team |
| Latency budget | Can afford network hops | Every ms counts |

---

## Event-Driven ML Architectures

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EVENT-DRIVEN ML ARCHITECTURE                                               │
│                                                                              │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐         │
│  │  Events  │───▶│  Event Bus (Kafka)                           │         │
│  │  Source  │    │                                               │         │
│  └──────────┘    │  Topics:                                     │         │
│                   │  ├── user.actions                            │         │
│                   │  ├── transactions                            │         │
│                   │  ├── model.predictions                      │         │
│                   │  ├── model.feedback                         │         │
│                   │  └── drift.alerts                           │         │
│                   └──────────────────────────────────────────────┘         │
│                        │         │         │         │                      │
│                        ▼         ▼         ▼         ▼                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐             │
│  │  Feature │  │  Model   │  │ Monitoring│  │  Retraining  │             │
│  │  Compute │  │  Serving │  │  Service  │  │  Trigger     │             │
│  │  (Flink) │  │          │  │           │  │              │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘             │
│                                                                              │
│  Benefits:                                                                 │
│  - Loose coupling between components                                      │
│  - Easy to add new consumers (new models, monitors)                      │
│  - Natural audit trail (event log)                                       │
│  - Replay capability (retrain on historical events)                      │
│  - Back-pressure handling                                                 │
│                                                                              │
│  Challenges:                                                               │
│  - Eventual consistency                                                   │
│  - Event ordering guarantees                                              │
│  - Debugging distributed flows                                            │
│  - Schema evolution                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Lambda Architecture for ML

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAMBDA ARCHITECTURE FOR ML                                                 │
│                                                                              │
│                    ┌────────────────────────────────────┐                   │
│                    │         DATA SOURCES                │                   │
│                    └──────────────┬─────────────────────┘                   │
│                                   │                                          │
│                    ┌──────────────┼──────────────┐                          │
│                    │              │              │                           │
│                    ▼              │              ▼                           │
│  ┌─────────────────────┐        │  ┌─────────────────────┐               │
│  │  BATCH LAYER         │        │  │  SPEED LAYER         │               │
│  │                      │        │  │                      │               │
│  │  - Full recompute    │        │  │  - Incremental       │               │
│  │  - High accuracy     │        │  │  - Approximate       │               │
│  │  - Hours latency     │        │  │  - Real-time         │               │
│  │                      │        │  │                      │               │
│  │  Batch Features:     │        │  │  Stream Features:    │               │
│  │  - User lifetime     │        │  │  - Last 5 min count  │               │
│  │    aggregates        │        │  │  - Session features   │               │
│  │  - Daily models      │        │  │  - Real-time score   │               │
│  │  - Historical        │        │  │                      │               │
│  └──────────┬───────────┘        │  └──────────┬───────────┘               │
│             │                     │             │                           │
│             ▼                     │             ▼                           │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  SERVING LAYER                                           │               │
│  │                                                           │               │
│  │  Merge batch + speed layer results                       │               │
│  │  Final prediction = f(batch_features, stream_features)   │               │
│  └─────────────────────────────────────────────────────────┘               │
│                                                                              │
│  Example: Fraud Detection                                                  │
│  Batch: user_avg_transaction_30d (computed nightly)                        │
│  Speed: transaction_count_last_5min (real-time)                            │
│  Serving: Combine both → fraud score                                       │
│                                                                              │
│  Trade-offs:                                                               │
│  + Best of both: accuracy + freshness                                     │
│  - Complexity: maintain two codepaths                                     │
│  - Risk: batch/speed logic divergence (training-serving skew)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Kappa Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  KAPPA ARCHITECTURE (Stream-only)                                           │
│                                                                              │
│  ┌──────────┐    ┌─────────────────────────────────────────────┐          │
│  │  Events  │───▶│  Immutable Event Log (Kafka)                │          │
│  └──────────┘    │  (retained indefinitely)                    │          │
│                   └─────────────────────┬───────────────────────┘          │
│                                          │                                  │
│                                          ▼                                  │
│                   ┌─────────────────────────────────────────────┐          │
│                   │  Stream Processor (Flink/Spark Streaming)   │          │
│                   │                                              │          │
│                   │  Single processing logic for ALL data       │          │
│                   │  - Real-time: process current events        │          │
│                   │  - Historical: replay from beginning        │          │
│                   └─────────────────────────────────────────────┘          │
│                                          │                                  │
│                                          ▼                                  │
│                   ┌─────────────────────────────────────────────┐          │
│                   │  Serving Store (feature values, predictions)│          │
│                   └─────────────────────────────────────────────┘          │
│                                                                              │
│  vs Lambda:                                                                │
│  + Single codebase (no batch/speed divergence)                            │
│  + Simpler operations                                                     │
│  + Reprocess by replaying events                                          │
│  - Requires mature streaming infrastructure                               │
│  - Historical reprocessing can be slow                                    │
│  - Not all computations fit streaming (e.g., global sorts)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Lambda vs Kappa Decision

| Criterion | Lambda | Kappa |
|-----------|--------|-------|
| Team streaming expertise | Low | High |
| Computation type | Global aggregations needed | Mostly event-level |
| Reprocessing time tolerance | Low (batch is fast) | Hours OK (replay) |
| Code complexity tolerance | Can maintain 2 paths | Prefer single path |
| Data volume for replay | Very large (>PB) | Manageable (<100TB) |

---

## Feature Computation Patterns

### Online vs Offline Feature Computation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FEATURE COMPUTATION PATTERNS                                               │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  OFFLINE (Batch) Features                                          │    │
│  │                                                                     │    │
│  │  Computed: Daily/hourly batch jobs                                 │    │
│  │  Stored: Data warehouse → materialized to online store            │    │
│  │  Examples:                                                         │    │
│  │  - user_total_purchases_30d                                       │    │
│  │  - item_avg_rating                                                │    │
│  │  - user_embedding (updated daily)                                 │    │
│  │                                                                     │    │
│  │  Latency: Stale by hours (acceptable for slow-changing features)  │    │
│  │  Cost: $$ (batch compute + storage)                                │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  NEAR-REAL-TIME (Streaming) Features                               │    │
│  │                                                                     │    │
│  │  Computed: Flink/Spark Streaming on event arrival                 │    │
│  │  Stored: Online store (Redis/DynamoDB)                            │    │
│  │  Examples:                                                         │    │
│  │  - user_actions_last_5min                                         │    │
│  │  - rolling_avg_transaction_amount_1h                              │    │
│  │  - session_page_views                                             │    │
│  │                                                                     │    │
│  │  Latency: Seconds to minutes                                      │    │
│  │  Cost: $$$ (always-on streaming infra)                            │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  REAL-TIME (On-Request) Features                                   │    │
│  │                                                                     │    │
│  │  Computed: At prediction time, from request context                │    │
│  │  Not stored (ephemeral)                                           │    │
│  │  Examples:                                                         │    │
│  │  - request_time_of_day                                            │    │
│  │  - input_text_length                                              │    │
│  │  - device_type (from request headers)                             │    │
│  │  - distance_to_merchant (from current GPS)                        │    │
│  │                                                                     │    │
│  │  Latency: Must be <5ms (computed inline)                          │    │
│  │  Cost: $ (compute only, no storage)                               │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Model Ensemble in Production

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ENSEMBLE PATTERNS IN PRODUCTION                                            │
│                                                                              │
│  Pattern 1: Weighted Average (simplest)                                    │
│  ┌────────┐                                                                │
│  │Request │──┬──▶ Model A (weight=0.4) ──┐                               │
│  └────────┘  ├──▶ Model B (weight=0.35)──┼──▶ Weighted Avg ──▶ Response  │
│              └──▶ Model C (weight=0.25)──┘                               │
│                                                                              │
│  Pattern 2: Stacking (meta-learner)                                       │
│  ┌────────┐                                                                │
│  │Request │──┬──▶ Model A ──┐                                             │
│  └────────┘  ├──▶ Model B ──┼──▶ Meta-Model ──▶ Response                 │
│              └──▶ Model C ──┘    (learns to combine)                      │
│                                                                              │
│  Pattern 3: Cascade (sequential, cost-saving)                             │
│  ┌────────┐    ┌─────────┐  Confident?   ┌─────────┐                    │
│  │Request │──▶│ Simple  │──Yes──▶ Return │ Complex │                    │
│  └────────┘    │ Model   │       │         │ Model   │                    │
│                └─────────┘  No───▶────────▶│ (GPU)   │──▶ Response       │
│                                             └─────────┘                    │
│                                                                              │
│  Cascade Economics:                                                        │
│  - 70% of requests handled by simple model ($0.001/req)                  │
│  - 30% escalated to complex model ($0.01/req)                            │
│  - Blended cost: $0.004/req (vs $0.01 for complex only)                  │
│  - 60% cost reduction with <1% accuracy loss                             │
│                                                                              │
│  Pattern 4: Mixture of Experts (routing)                                  │
│  ┌────────┐    ┌──────────┐    ┌──────────────────┐                     │
│  │Request │──▶│  Router  │──▶ │ Expert A (images) │                     │
│  └────────┘    │  (gating │    │ Expert B (text)   │                     │
│                │  network)│    │ Expert C (tabular)│                     │
│                └──────────┘    └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Fallback Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FALLBACK HIERARCHY                                                         │
│                                                                              │
│  Level 0: Primary Model (full accuracy)                                    │
│     │ Fails? (timeout, error, drift detected)                              │
│     ▼                                                                       │
│  Level 1: Secondary Model (simpler, faster, less accurate)                 │
│     │ Fails?                                                                │
│     ▼                                                                       │
│  Level 2: Cached Predictions (stale but available)                         │
│     │ No cache hit?                                                         │
│     ▼                                                                       │
│  Level 3: Business Rules / Heuristics (handcrafted)                        │
│     │ Rules don't apply?                                                    │
│     ▼                                                                       │
│  Level 4: Default Value (safe default, e.g., "not fraud")                  │
│                                                                              │
│  Example: Product Recommendations                                          │
│  L0: Personalized model (user features + context) — 85% CTR lift          │
│  L1: Collaborative filtering (user history only) — 50% CTR lift           │
│  L2: User's last recommendations (cached 1h) — 30% CTR lift              │
│  L3: Popularity-based (trending items) — 10% CTR lift                     │
│  L4: Editorial picks (manually curated) — baseline                        │
│                                                                              │
│  Implementation:                                                           │
│  ```python                                                                  │
│  async def get_recommendations(user_id, context):                          │
│      try:                                                                   │
│          return await primary_model.predict(user_id, context, timeout=50)  │
│      except (TimeoutError, ModelError):                                    │
│          metrics.increment("fallback.l1")                                  │
│          try:                                                               │
│              return await simple_model.predict(user_id, timeout=20)        │
│          except:                                                            │
│              cached = await cache.get(f"recs:{user_id}")                   │
│              if cached:                                                      │
│                  metrics.increment("fallback.l2")                           │
│                  return cached                                              │
│              metrics.increment("fallback.l3")                               │
│              return get_popular_items()                                     │
│  ```                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Circuit Breaker for ML Services

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML CIRCUIT BREAKER                                                         │
│                                                                              │
│  States:                                                                    │
│                                                                              │
│  ┌──────────┐   failure_rate > 50%   ┌──────────┐   after timeout  ┌────┐│
│  │  CLOSED  │ ─────────────────────▶ │   OPEN   │ ───────────────▶│HALF││
│  │(normal)  │                        │(fallback)│                  │OPEN││
│  └──────────┘ ◀───────────────────── └──────────┘ ◀─────────────── └────┘│
│                   success in half-open              failure in half-open   │
│                                                                              │
│  ML-Specific Triggers (beyond errors):                                     │
│  - Latency > SLA for 5+ minutes                                          │
│  - Prediction confidence < threshold (model uncertain)                    │
│  - Drift score above critical threshold                                   │
│  - GPU memory warnings                                                    │
│                                                                              │
│  When circuit is OPEN:                                                     │
│  - Route to fallback model / cached predictions                          │
│  - Log all requests for replay when circuit closes                       │
│  - Alert on-call team                                                     │
│  - Auto-attempt recovery every 30s (half-open)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Model Serving

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MULTI-MODEL SERVING PATTERNS                                               │
│                                                                              │
│  Pattern 1: Model-per-Container (isolated)                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐              │
│  │  Container A   │  │  Container B   │  │  Container C   │              │
│  │  Model: Fraud  │  │  Model: Recs   │  │  Model: Search │              │
│  │  GPU: T4       │  │  GPU: A10      │  │  CPU only      │              │
│  └────────────────┘  └────────────────┘  └────────────────┘              │
│  Pros: Isolation, independent scaling                                     │
│  Cons: Resource waste (each needs own GPU)                                │
│                                                                              │
│  Pattern 2: Multi-Model-per-GPU (shared, Triton)                          │
│  ┌────────────────────────────────────────────────────┐                   │
│  │  Single GPU Instance (A100 80GB)                    │                   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │                   │
│  │  │ Model A  │  │ Model B  │  │ Model C  │        │                   │
│  │  │ (10GB)   │  │ (20GB)   │  │ (5GB)    │        │                   │
│  │  └──────────┘  └──────────┘  └──────────┘        │                   │
│  │  Triton handles scheduling & memory management     │                   │
│  └────────────────────────────────────────────────────┘                   │
│  Pros: Better GPU utilization (70%+ vs 20%)                               │
│  Cons: Noisy neighbor, complex memory management                          │
│                                                                              │
│  Pattern 3: Model Multiplexing (swap models on demand)                    │
│  ┌────────────────────────────────────────────────────┐                   │
│  │  GPU Instance                                       │                   │
│  │  Active: Model A (loaded)                          │                   │
│  │  Standby: Model B, C (on disk, load on request)   │                   │
│  │  Swap time: 2-10 seconds                           │                   │
│  └────────────────────────────────────────────────────┘                   │
│  Pros: Handle 1000s of models with few GPUs                               │
│  Cons: Cold start latency for inactive models                             │
│  Use for: Multi-tenant SaaS, per-customer models                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Embedding Serving at Scale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EMBEDDING SERVING ARCHITECTURE                                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Embedding Generation Pipeline                                    │     │
│  │                                                                    │     │
│  │  Items/Users → Embedding Model → Vector Store                    │     │
│  │  (batch job, daily/hourly)                                       │     │
│  │                                                                    │     │
│  │  New items → Real-time embedding → Update index                  │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Serving Architecture                                             │     │
│  │                                                                    │     │
│  │  Query ──▶ Encode Query ──▶ ANN Search ──▶ Top-K Results        │     │
│  │              (5ms)            (10ms)          (rank/filter)       │     │
│  │                                                                    │     │
│  │  Vector Index Options:                                            │     │
│  │  ┌────────────────────────────────────────────────────────────┐ │     │
│  │  │ Engine    │ Scale      │ Latency │ Cost    │ Managed?     │ │     │
│  │  │───────────┼────────────┼─────────┼─────────┼──────────────│ │     │
│  │  │ FAISS     │ 1B vectors │ <5ms    │ $       │ No (self)    │ │     │
│  │  │ Pinecone  │ 1B vectors │ <20ms   │ $$$$    │ Yes          │ │     │
│  │  │ Milvus    │ 10B vectors│ <10ms   │ $$      │ Optional     │ │     │
│  │  │ Weaviate  │ 1B vectors │ <15ms   │ $$$     │ Yes          │ │     │
│  │  │ Qdrant    │ 1B vectors │ <10ms   │ $$      │ Optional     │ │     │
│  │  │ pgvector  │ 10M vectors│ <50ms   │ $       │ Yes (RDS)    │ │     │
│  │  └────────────────────────────────────────────────────────────┘ │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Scaling Strategy:                                                         │
│  - <10M vectors: Single node (FAISS/pgvector) — simplest                  │
│  - 10M-1B vectors: Distributed index (Milvus/Qdrant) — sharded           │
│  - >1B vectors: Tiered (hot in memory, warm on SSD, cold in S3)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Search & Recommendation System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RECOMMENDATION SYSTEM ARCHITECTURE (Two-Stage)                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Stage 1: CANDIDATE GENERATION (retrieve ~1000 from millions)    │     │
│  │                                                                    │     │
│  │  Sources (parallel):                                              │     │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │     │
│  │  │ ANN        │  │Collaborative│  │ Content-   │  │ Popular/ │ │     │
│  │  │ (embedding │  │ Filtering  │  │ Based      │  │ Trending │ │     │
│  │  │  similarity)│  │(user-item) │  │ (features) │  │          │ │     │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └────┬─────┘ │     │
│  │        └────────────────┴───────────────┴───────────────┘       │     │
│  │                              │                                    │     │
│  │                              ▼ (~1000 candidates)                │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                 │                                           │
│  ┌──────────────────────────────┼───────────────────────────────────┐     │
│  │  Stage 2: RANKING (score & order ~1000 → top 25)                 │     │
│  │                              │                                    │     │
│  │  ┌──────────────────────────────────────────────────────┐       │     │
│  │  │  Feature Assembly                                     │       │     │
│  │  │  User features + Item features + Context features    │       │     │
│  │  └──────────────────────────────────────────────────────┘       │     │
│  │                              │                                    │     │
│  │  ┌──────────────────────────────────────────────────────┐       │     │
│  │  │  Ranking Model (Deep learning, typically GPU)        │       │     │
│  │  │  Score each candidate                                │       │     │
│  │  └──────────────────────────────────────────────────────┘       │     │
│  │                              │                                    │     │
│  │  ┌──────────────────────────────────────────────────────┐       │     │
│  │  │  Post-Processing                                      │       │     │
│  │  │  - Diversity (MMR)                                   │       │     │
│  │  │  - Business rules (boost new items, filter NSFW)     │       │     │
│  │  │  - Position bias correction                          │       │     │
│  │  └──────────────────────────────────────────────────────┘       │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Latency Budget (total <200ms):                                           │
│  - Candidate gen: 30ms (parallel retrieval)                               │
│  - Feature assembly: 20ms (online store lookup)                           │
│  - Ranking: 50ms (GPU inference, batch of 1000)                           │
│  - Post-processing: 10ms                                                  │
│  - Network/overhead: 20ms                                                 │
│                                                                              │
│  Scale Numbers (Netflix-class):                                           │
│  - 200M users, 50K items                                                  │
│  - 50K QPS peak                                                           │
│  - Model refresh: hourly (embeddings), daily (ranker)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Rate Limiting and Throttling for ML

```
┌─────────────────────────────────────────────────────────────────┐
│  ML-SPECIFIC RATE LIMITING                                       │
│                                                                   │
│  Standard rate limiting is insufficient for ML because:         │
│  - GPU resources are expensive and limited                      │
│  - Large batch requests can starve other users                 │
│  - Model inference time varies by input size                   │
│                                                                   │
│  Strategies:                                                    │
│  1. Token-based (like LLM APIs):                               │
│     - Budget per request = f(input_size, model_complexity)     │
│     - 1000 tokens/min per user                                 │
│                                                                   │
│  2. GPU-time-based:                                            │
│     - Track actual GPU ms consumed per user                    │
│     - Limit: 10,000 GPU-ms per minute                         │
│                                                                   │
│  3. Priority queuing:                                          │
│     - Premium: guaranteed low latency, no throttling          │
│     - Standard: best-effort, throttled under load             │
│     - Batch: lowest priority, process when idle               │
│                                                                   │
│  4. Adaptive throttling:                                       │
│     - Monitor GPU utilization                                  │
│     - If >80%: start rejecting low-priority requests          │
│     - If >90%: only serve premium tier                        │
│     - If >95%: circuit break, serve cached/fallback           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Trade-Off Analysis Tables

### Serving Pattern Trade-offs

| Pattern | Latency | Cost | Freshness | Complexity | Best For |
|---------|---------|------|-----------|------------|----------|
| Batch + Lookup | <5ms | $ | Hours | Low | Stable predictions |
| Real-time | 10-100ms | $$$ | Instant | Medium | Personalization |
| Streaming | 1-10s | $$ | Near-RT | High | Fraud, anomaly |
| Hybrid (Lambda) | <50ms | $$ | Minutes | High | Most production |
| Edge | <10ms | $ per device | Days (model) | High | IoT, mobile |

### Architecture Pattern Selection

| Requirement | Recommended Pattern |
|-------------|-------------------|
| <10ms latency, simple model | Pre-computed batch + cache lookup |
| <50ms, personalized | Real-time serving + feature store |
| Millions of models (per-user) | Model multiplexing |
| Cost-sensitive, variable complexity | Cascade ensemble |
| High availability required | Multi-model fallback + circuit breaker |
| Event-driven domain | Kappa + streaming features |

---

## Real-World Case Studies

### Case Study: YouTube Recommendations
- **Architecture**: Two-tower retrieval → deep ranking → re-ranking
- **Scale**: 500M+ users, 500+ hours video/min uploaded
- **Key Pattern**: Candidate generation uses ANN on user/video embeddings; ranker uses 100s of features
- **Learning**: Freshness matters — re-rank with latest user actions in session

### Case Study: Uber Eats Delivery Time Prediction
- **Architecture**: Ensemble of specialized models (restaurant prep, driver travel, handoff)
- **Key Pattern**: Each sub-model serves a different phase; combined for total ETA
- **Fallback**: If GPS fails → historical average for route; if restaurant model fails → category average
- **Learning**: Decompose complex predictions into interpretable sub-problems

### Production Incident: Embedding Index Corruption
- **Symptom**: Recommendations became random (diversity metric spiked)
- **Root Cause**: Index rebuild failed silently, served stale index missing 30% of items
- **Fix**: Added embedding coverage monitoring (% of catalog in index), blue-green index swaps
- **Learning**: Monitor what's NOT in the index, not just what is

---

## Interview Questions

1. **Design a real-time recommendation system for 100M users, 10M items, <100ms latency**
   - Focus: Two-stage retrieval+ranking, feature store, embedding serving, caching

2. **How would you implement fallback for an ML service with 99.99% availability SLA?**
   - Focus: Graceful degradation hierarchy, circuit breaker, cached predictions

3. **Design an architecture that serves 50 different ML models cost-efficiently**
   - Focus: Multi-model serving, GPU sharing, model multiplexing, priority queuing

4. **Compare Lambda vs Kappa architecture for a fraud detection system**
   - Focus: Feature freshness requirements, operational complexity, replay needs

5. **Design a cascade model system that reduces GPU costs by 70% with <1% accuracy loss**
   - Focus: Confidence thresholds, routing logic, monitoring escalation rates
