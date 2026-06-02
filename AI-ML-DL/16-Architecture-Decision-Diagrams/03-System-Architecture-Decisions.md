# System Architecture Decisions for Production ML Systems

> Decisions a staff architect makes when designing production ML systems — with reasoning for each choice.

---

## Diagram 1: Batch vs Real-Time Serving Decision

```mermaid
flowchart TD
    Start[How often do predictions change?] --> Same[Same prediction for hours/days]
    Start --> Each[Must respond to each request]
    Start --> Mix[Mix of both]

    Same --> BATCH[✅ BATCH SERVING]
    BATCH --> BEx[Examples: Recommendations refresh nightly<br/>Risk scores daily, churn predictions weekly]
    BATCH --> BArch[Architecture: Precompute → Store in Cache/DB → Serve from Cache]
    BATCH --> BWhy[WHY batch: Cheaper - no GPU serving infra<br/>Simpler ops, tolerates slow models]
    BATCH --> BTrade[TRADEOFF: Stale predictions<br/>Cannot react to real-time signals]

    Each --> RT[✅ REAL-TIME SERVING]
    RT --> REx[Examples: Fraud detection, search ranking<br/>Chatbot, dynamic pricing]
    RT --> RArch[Architecture: Model Server - Triton/TF Serving<br/>→ Load Balancer → Autoscale]
    RT --> RWhy[WHY real-time: Fresh predictions<br/>Context-dependent, per-request features]
    RT --> RTrade[TRADEOFF: Expensive - always-on GPUs<br/>Latency constraints, complex infra]

    Mix --> NRT[✅ NEAR REAL-TIME / HYBRID]
    NRT --> NEx[Examples: News feed - batch candidates + real-time reranking<br/>E-commerce - batch product embeddings + real-time user context]
    NRT --> NArch[Architecture: Batch candidate generation<br/>+ Real-time scoring/reranking layer]
    NRT --> NWhy[WHY: Best of both worlds<br/>Cheap candidate gen, fresh final ranking]

    style BATCH fill:#2d5a2d,color:#fff
    style RT fill:#5a2d2d,color:#fff
    style NRT fill:#2d2d5a,color:#fff
```

### Decision Heuristic

| Signal | Batch | Real-Time |
|--------|-------|-----------|
| Prediction changes | Hourly/daily | Per-request |
| Latency requirement | Seconds OK | < 100ms |
| Cost sensitivity | High | Lower (revenue justifies) |
| Model complexity | Can be huge | Must be fast |
| Data freshness need | Low | High |

---

## Diagram 2: Model Serving Patterns

```mermaid
flowchart TD
    Root[Model Serving Patterns] --> Sync[Synchronous<br/>REST/gRPC]
    Root --> Async[Asynchronous<br/>Queue-based]
    Root --> Stream[Streaming<br/>WebSocket/SSE]
    Root --> Edge[Embedded<br/>Edge/On-device]
    Root --> Sidecar[Sidecar<br/>Service Mesh]

    Sync --> SFlow[Client → Request → Model → Response]
    Sync --> SWhy[WHY: Simple, immediate response<br/>Easy to reason about]
    Sync --> SWhen[WHEN: Latency < 100ms required<br/>User-facing, simple models]
    Sync --> SRisk[RISK: Timeout if model slow<br/>Blocks caller, no backpressure]

    Async --> AFlow[Client → Queue → Worker → Result Store → Client polls]
    Async --> AWhy[WHY: Decouple caller from model<br/>Handle traffic spikes, backpressure]
    Async --> AWhen[WHEN: Can tolerate seconds delay<br/>Heavy models like LLMs, batch jobs]
    Async --> ARisk[RISK: Complexity, eventual consistency<br/>Harder debugging, queue management]

    Stream --> StFlow[Client → Stream connection → Tokens arrive progressively]
    Stream --> StWhy[WHY: Better UX for generative models<br/>User sees progress, faster perceived latency]
    Stream --> StWhen[WHEN: LLM responses, real-time transcription<br/>Live translation, progressive rendering]
    Stream --> StRisk[RISK: Connection management<br/>Partial failures, reconnection logic]

    Edge --> EFlow[Model runs on client device<br/>Mobile, IoT, browser WASM]
    Edge --> EWhy[WHY: No network latency, works offline<br/>Privacy - data never leaves device]
    Edge --> EWhen[WHEN: Mobile apps, IoT sensors<br/>Privacy-sensitive, low-connectivity]
    Edge --> ERisk[RISK: Model size limits 50-200MB<br/>Hard to update, device heterogeneity]

    Sidecar --> ScFlow[Model runs alongside app container<br/>Shared pod in Kubernetes]
    Sidecar --> ScWhy[WHY: Language-agnostic inference<br/>Separate scaling, clear boundaries]
    Sidecar --> ScWhen[WHEN: Microservices architecture<br/>Polyglot teams, multiple models per service]

    style Sync fill:#1a5276,color:#fff
    style Async fill:#1a5276,color:#fff
    style Stream fill:#1a5276,color:#fff
    style Edge fill:#1a5276,color:#fff
    style Sidecar fill:#1a5276,color:#fff
```

---

## Diagram 3: Scaling ML Systems Decision Tree

```mermaid
flowchart TD
    Problem[Your ML model is too slow/expensive] --> Latency[Latency too high<br/>p99 > 100ms]
    Problem --> Throughput[Throughput too low<br/>Cannot handle QPS]
    Problem --> Cost[Cost too high<br/>GPU bill exploding]

    Latency --> LModel[Model too large?]
    Latency --> LPrep[Preprocessing slow?]
    Latency --> LNet[Network overhead?]
    Latency --> LGPU[Single request too slow?]

    LModel --> LMFix[Quantization INT8/FP16<br/>Distillation, Pruning]
    LMFix --> LMWhy[WHY: 2-4x speedup with less than 1% accuracy loss<br/>INT8 halves memory, doubles throughput]

    LPrep --> LPFix[Precompute features<br/>Cache embeddings]
    LPFix --> LPWhy[WHY: Feature computation often 3-5x slower<br/>than model inference itself]

    LNet --> LNFix[Batch requests together<br/>gRPC instead of REST]
    LNFix --> LNWhy[WHY: gRPC is 5-10x faster for small payloads<br/>Batching amortizes network overhead]

    LGPU --> LGFix[GPU serving with TensorRT<br/>Operator fusion, kernel optimization]
    LGFix --> LGWhy[WHY: GPU parallel compute for matrix ops<br/>TensorRT can give 3-6x over naive PyTorch]

    Throughput --> TRep[Add replicas - horizontal scaling]
    Throughput --> TBatch[Dynamic batching]
    Throughput --> TShard[Model sharding - tensor parallelism]
    Throughput --> TQueue[Async processing + queue]

    TRep --> TRWhy[WHY: Linear scaling for stateless model servers<br/>K8s HPA makes this simple]
    TBatch --> TBWhy[WHY: GPU utilization jumps from 10% to 80%<br/>Wait a few ms, batch 8-32 requests together]
    TShard --> TSWhy[WHY: Single model across multiple GPUs<br/>For models too large for one GPU]
    TQueue --> TQWhy[WHY: Smooth out traffic spikes<br/>Degrade gracefully under load]

    Cost --> CDistill[Smaller model via distillation]
    Cost --> CSpot[Spot/preemptible instances]
    Cost --> CCascade[Cascade: cheap model first<br/>expensive only if uncertain]
    Cost --> CCache[Cache frequent predictions]

    CDistill --> CDWhy[WHY: 90% quality at 10% cost<br/>DistilBERT = 40% smaller, 60% faster]
    CSpot --> CSWhy[WHY: 60-70% savings<br/>Use for batch, stateless serving]
    CCascade --> CCWhy[WHY: 80% of requests handled by fast model<br/>Only 20% need expensive model]
    CCache --> CKWhy[WHY: Many requests are duplicates<br/>Search queries follow power law]

    style Latency fill:#8b0000,color:#fff
    style Throughput fill:#8b4500,color:#fff
    style Cost fill:#006400,color:#fff
```

---

## Diagram 4: Feature Store Architecture

```mermaid
sequenceDiagram
    participant App as Application
    participant Online as Online Store<br/>Redis/DynamoDB
    participant Offline as Offline Store<br/>Parquet/Hive/BigQuery
    participant Compute as Feature Compute<br/>Spark/Flink
    participant Stream as Event Stream<br/>Kafka
    participant Train as Training Pipeline

    Note over App,Train: === WHY Feature Store? ===
    Note over App,Train: 1. Solves training-serving skew - same features everywhere
    Note over App,Train: 2. Feature reuse across teams - compute once, use many times
    Note over App,Train: 3. Point-in-time correctness - prevents future data leakage

    Note over Stream,Compute: ═══ STREAMING FEATURES (low latency) ═══
    Stream->>Compute: Raw events (clicks, purchases, page views)
    Compute->>Compute: Aggregate: count_last_5min<br/>avg_last_1hr, max_last_24hr
    Compute->>Online: Write to Redis<br/>key: user_id, TTL: 1 hour
    Note over Compute,Online: WHY streaming: Features that change per-minute<br/>Click counts, session features, recent activity

    Note over Offline,Compute: ═══ BATCH FEATURES (complex, historical) ═══
    Compute->>Offline: Daily Spark job: user profiles<br/>embeddings, lifetime stats
    Offline->>Online: Sync hot features to Redis<br/>on schedule or model deploy
    Note over Offline,Online: WHY batch: Expensive aggregations over TB of data<br/>User lifetime value, 90-day averages

    Note over App,Online: ═══ SERVING (real-time inference) ═══
    App->>Online: Get features for user_123
    Online-->>App: {click_count_5min: 3, avg_purchase: 45.0<br/>lifetime_orders: 142, embedding: [...]}
    Note over App,Online: WHY online store: Single-digit ms latency<br/>Pre-joined, denormalized for speed

    Note over Train,Offline: ═══ TRAINING (point-in-time correct) ═══
    Train->>Offline: Get features AS OF timestamp T<br/>for each training example
    Offline-->>Train: Features as they existed at time T
    Note over Train: WHY point-in-time: Prevents future data leakage!
    Note over Train: Without this: model sees future info during training<br/>performs great offline, terrible in production
```

### Feature Store Decision Matrix

| Feature Type | Compute | Store | Freshness | Example |
|-------------|---------|-------|-----------|---------|
| Streaming | Flink/Spark Streaming | Redis | Seconds | Click count last 5 min |
| Batch | Spark/SQL | Parquet + Redis | Hours | User lifetime value |
| On-demand | Real-time transform | None (computed) | Instant | Text length, IP geolocation |

---

## Diagram 5: A/B Testing for ML Models

```mermaid
sequenceDiagram
    participant User
    participant Router as Traffic Router
    participant ModelA as Model A<br/>Control/Champion
    participant ModelB as Model B<br/>Challenger
    participant Logger as Event Logger
    participant Analyzer as Statistical Analyzer

    User->>Router: Request (user_id=abc123)
    Router->>Router: Hash(user_id) % 100<br/>Deterministic assignment

    alt bucket < 50 → Control Group
        Router->>ModelA: Predict
        ModelA-->>User: Result A
        ModelA->>Logger: Log(model=A, pred, user_id, timestamp)
    else bucket >= 50 → Treatment Group
        Router->>ModelB: Predict
        ModelB-->>User: Result B
        ModelB->>Logger: Log(model=B, pred, user_id, timestamp)
    end

    Note over User,Router: User always sees same model<br/>WHY: Consistent experience, valid measurement

    Note over Logger,Analyzer: ═══ After sufficient data collected ═══
    Logger->>Analyzer: Aggregate metrics per model<br/>CTR, revenue, latency, errors
    Analyzer->>Analyzer: Statistical significance test<br/>Two-sample t-test or Mann-Whitney U

    Note over Analyzer: WHY statistical test:<br/>Random variation WILL make B look better/worse by chance!
    Note over Analyzer: Need BOTH:<br/>1. p-value < 0.05 (unlikely due to chance)<br/>2. Practical significance (effect size matters)

    Note over Analyzer: SAMPLE SIZE CALCULATION:<br/>Effect size 1% lift, baseline CTR 5%<br/>→ Need ~380K samples per group<br/>Smaller effect = exponentially more data

    Analyzer->>Analyzer: Check GUARDRAIL metrics:<br/>- Latency p99 not degraded?<br/>- Error rate stable?<br/>- User retention unchanged?
    Note over Analyzer: WHY guardrails: Optimizing clicks can destroy retention!<br/>Clickbait wins clicks, loses trust

    alt B wins on primary + guardrails pass
        Analyzer->>Router: Promote B to 100% traffic
    else No significant difference
        Analyzer->>Router: Keep A<br/>WHY: Simpler/cheaper model wins ties
    else B wins primary but fails guardrail
        Analyzer->>Router: REJECT B despite metric win
    end
```

### A/B Testing Key Decisions

**WHY you need statistical significance (not just "B has higher metric"):**
- With 1000 users, random chance alone creates ~3% metric swings
- A model that's actually identical can "win" 50% of the time without significance testing
- Type I error (false positive): Shipping a worse model thinking it's better

**Sample size calculation rule of thumb:**
- Minimum Detectable Effect (MDE) of 1% relative lift → ~400K samples per variant
- MDE of 5% → ~16K samples per variant
- Smaller effects need exponentially more data to detect

**Multi-Armed Bandit as alternative:**
- WHY: Faster convergence, less wasted traffic on losing variant
- HOW: Dynamically shift traffic toward winner (Thompson Sampling, UCB)
- TRADEOFF: Harder to get clean statistical significance, non-stationary
- WHEN: High cost of showing bad variant (revenue loss), many variants to test

---

## Diagram 6: Microservices vs Monolith for ML

```mermaid
flowchart TD
    Q[Should you split your ML system<br/>into microservices?] --> Small[Team < 5 AND models < 3]
    Q --> Large[Team > 5 OR models > 5<br/>OR different scaling needs]
    Q --> Platform[ML Platform team<br/>serving many teams]

    Small --> Mono[✅ MONOLITH]
    Mono --> MonoWhy[WHY: Less complexity, faster iteration<br/>Shared resources, one deploy pipeline<br/>Network calls = zero]
    Mono --> MonoArch[Architecture:<br/>Single service with multiple model endpoints<br/>Flask/FastAPI + model registry in-process]
    Mono --> MonoWarn[EVOLVE when: Deploy conflicts arise<br/>Scaling needs diverge, team grows]

    Large --> Micro[✅ MICROSERVICES]
    Micro --> MicroWhy[WHY: Independent deployment & scaling<br/>Team ownership, fault isolation<br/>Different GPU needs per model]
    Micro --> MicroArch[Architecture:]
    MicroArch --> FS[Feature Service<br/>Scales with data volume]
    MicroArch --> MSA[Model Service A<br/>Scales with traffic, CPU]
    MicroArch --> MSB[Model Service B<br/>Scales differently, needs GPU]
    MicroArch --> Orch[Orchestrator<br/>Routes requests, handles fallback]

    Platform --> Plat[✅ ML PLATFORM]
    Plat --> PlatWhy[WHY: Serve many teams with shared infra<br/>Standardize patterns, reduce duplication<br/>Central governance and monitoring]
    Plat --> PlatArch[Architecture:]
    PlatArch --> Reg[Model Registry - MLflow/Weights&Biases]
    PlatArch --> Serve[Serving Framework - Seldon/KServe/Triton]
    PlatArch --> Feat[Feature Platform - Feast/Tecton]
    PlatArch --> Mon[Monitoring - Prometheus + custom drift detection]

    style Mono fill:#2d5a2d,color:#fff
    style Micro fill:#5a4a2d,color:#fff
    style Plat fill:#2d2d5a,color:#fff
```

### When to Split: Concrete Signals

| Signal | Stay Monolith | Split |
|--------|--------------|-------|
| Deploy frequency | Same cadence | Model A daily, Model B weekly |
| Resource needs | All similar | One needs GPU, others CPU |
| Team structure | Same team owns all | Different teams, different models |
| Failure blast radius | Acceptable | One model crash kills everything |
| Shared state | Heavy sharing | Minimal coupling |

---

## Diagram 7: Caching Strategies for ML Systems

```mermaid
flowchart LR
    subgraph Request Path
        Req[Request] --> FC[Feature Cache]
        FC --> EC[Embedding Cache]
        EC --> PC[Prediction Cache]
        PC --> Resp[Response]
    end

    subgraph FC_Detail[Feature Cache]
        FC1[WHY: Expensive feature computation<br/>Same user = same features for seconds]
        FC2[HIT RATE: 40-60% typical<br/>Users make multiple requests quickly]
        FC3[TTL: 5-60 seconds<br/>Features change slowly]
    end

    subgraph EC_Detail[Embedding Cache]
        EC1[WHY: Embedding lookup is expensive<br/>Embeddings change only on retrain]
        EC2[HIT RATE: 80-95%<br/>Popular items requested repeatedly]
        EC3[TTL: Hours to days<br/>Until model retrain]
    end

    subgraph PC_Detail[Prediction Cache]
        PC1[WHY: Same input = same output<br/>Many queries are repeated]
        PC2[HIT RATE: 20-70% depends on domain<br/>Search queries follow power law]
        PC3[TTL: Minutes to hours<br/>Balance freshness vs cost]
    end

    subgraph MW[Model Weight Cache]
        MW1[WHY: Loading from disk/S3 is slow<br/>Keep hot models in GPU memory]
        MW2[Strategy: LRU eviction<br/>Pin frequently-used models]
    end

    FC --> FC_Detail
    EC --> EC_Detail
    PC --> PC_Detail
```

### Cache Invalidation Strategies

```mermaid
flowchart TD
    Invalidation[Cache Invalidation Strategy] --> TTL[TTL-based]
    Invalidation --> Event[Event-based]
    Invalidation --> Version[Version-based]

    TTL --> TTLWhy[WHY: Simple, good enough for most cases<br/>Features that change hourly → TTL 1hr]
    TTL --> TTLWhen[WHEN: Features with predictable staleness<br/>Aggregate stats, slowly-changing dimensions]
    TTL --> TTLRisk[RISK: May serve stale data up to TTL<br/>Thundering herd on expiry]

    Event --> EventWhy[WHY: Freshness matters for UX<br/>User did action → invalidate immediately]
    Event --> EventWhen[WHEN: User profile changes, new purchase<br/>Real-time personalization]
    Event --> EventRisk[RISK: Complexity, need event pipeline<br/>Partial invalidation bugs]

    Version --> VersionWhy[WHY: New model = all cached predictions stale<br/>Model deploy triggers full cache flush]
    Version --> VersionWhen[WHEN: Model retraining, feature schema change<br/>A/B test traffic shift]
    Version --> VersionRisk[RISK: Cache stampede on deploy<br/>Mitigate: warm cache before cutover]

    style TTL fill:#2d5a2d,color:#fff
    style Event fill:#5a4a2d,color:#fff
    style Version fill:#2d2d5a,color:#fff
```

### Caching Decision Quick Reference

| Cache Layer | Typical Store | TTL | Hit Rate | Savings |
|-------------|--------------|-----|----------|---------|
| Feature cache | Local/Redis | 5-60s | 40-60% | Skip feature DB call |
| Embedding cache | Redis/Memcached | Hours | 80-95% | Skip vector lookup |
| Prediction cache | Redis/CDN | Minutes | 20-70% | Skip entire inference |
| Model weights | GPU memory/RAM | Until eviction | 99%+ | Skip model load |

---

## Diagram 8: Error Handling & Fallback Patterns

```mermaid
flowchart TD
    Req[Request Arrives] --> Health{Model Healthy?}
    
    Health -->|Yes| Infer[Normal Inference]
    Health -->|No| Fallback[Fallback Strategy]
    
    Infer --> LatCheck{Latency within SLA?}
    LatCheck -->|Yes| ConfCheck{Confidence above threshold?}
    LatCheck -->|No| Timeout[Timeout Handler]
    
    ConfCheck -->|Yes| Return[Return Prediction ✅]
    ConfCheck -->|No| LowConf[Low Confidence Handler]
    
    Fallback --> F1[Cached Prediction<br/>Last known good result]
    Fallback --> F2[Simpler Model<br/>Rule-based/heuristic]
    Fallback --> F3[Default Value<br/>Most popular/average]
    Fallback --> F4[Graceful Degradation<br/>Partial features only]

    F1 --> F1Why[WHY: Better stale prediction than no prediction<br/>User still gets personalized experience]
    F2 --> F2Why[WHY: Always available, no GPU needed<br/>Rules catch 60-70% of cases correctly]
    F3 --> F3Why[WHY: Last resort, better than error<br/>Show popular items, average price]
    F4 --> F4Why[WHY: Some features unavailable ≠ complete failure<br/>Model trained to handle missing features]

    Timeout --> Circuit{Consecutive failures > N?}
    Circuit -->|Yes| CB[Circuit Breaker OPEN<br/>Stop calling model, use fallback]
    Circuit -->|No| Retry[Retry once with shorter timeout]
    CB --> CBWhy[WHY: Prevent cascade failure<br/>Model overload → all services slow → total outage]

    LowConf --> Human[Flag for Human Review]
    LowConf --> IDK[Return 'I dont know'<br/>Better than wrong answer]
    
    Human --> HWhy[WHY: Humans handle edge cases<br/>Model uncertainty = learning opportunity]
    IDK --> IDKWhy[WHY: Wrong confident prediction erodes trust<br/>Especially in high-stakes: medical, financial]

    style Return fill:#2d5a2d,color:#fff
    style CB fill:#8b0000,color:#fff
    style Fallback fill:#5a4a2d,color:#fff
```

### Fallback Priority Order

```mermaid
flowchart LR
    A[1. Cached prediction<br/>Freshest available] --> B[2. Simpler model<br/>Rules/heuristics]
    B --> C[3. Graceful degradation<br/>Partial prediction]
    C --> D[4. Default value<br/>Last resort]
    D --> E[5. Error response<br/>Only if nothing works]

    style A fill:#2d5a2d,color:#fff
    style B fill:#3d6a3d,color:#fff
    style C fill:#5a5a2d,color:#fff
    style D fill:#5a3d2d,color:#fff
    style E fill:#5a2d2d,color:#fff
```

### Error Budget Philosophy

| Failure Mode | Acceptable Rate | Response | WHY |
|-------------|----------------|----------|-----|
| Model timeout | < 1% of requests | Serve cached | Users tolerate slightly stale |
| Low confidence | < 5% of predictions | Flag + default | Reduces error rate at cost of coverage |
| Complete outage | < 0.1% uptime loss | Full fallback stack | SLA commitment |
| Data pipeline delay | < 1 hour | Serve with stale features | Features change slowly enough |

---

## Summary: Architecture Decision Cheat Sheet

| Decision | Default Choice | Switch When |
|----------|---------------|-------------|
| Batch vs Real-time | Batch (cheaper) | Predictions must reflect last-second data |
| Sync vs Async serving | Sync (simpler) | Model > 1s latency, need backpressure |
| Monolith vs Micro | Monolith (start here) | Teams/models/scaling needs diverge |
| Cache strategy | TTL-based (simple) | Need sub-second freshness |
| Fallback pattern | Cached + rules | High-stakes = "I don't know" is better |
| A/B vs Bandit | A/B (cleaner stats) | Many variants, high cost of losing variant |
| Feature store | None (start simple) | Training-serving skew bugs appear |
| GPU vs CPU serving | CPU (cheaper) | Latency requirement forces GPU |
