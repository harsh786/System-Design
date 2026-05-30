# Caching at Scale — Architecture Diagrams

## 1. Multi-Layer Cache Architecture

```mermaid
graph TB
    subgraph "Client Request"
        REQ[User Query]
    end

    subgraph "Cache Orchestrator"
        CO[Cache Orchestrator]
        KB[Key Builder<br/>tenant + perm + version + freshness]
        BP[Bypass Policy<br/>risk-tier check]
    end

    subgraph "Cache Layers"
        L1[L1: Prompt/Prefix Cache<br/>GPU KV-Cache, exact match]
        L2[L2: Semantic Response Cache<br/>Embedding similarity > 0.95]
        L3[L3: Retrieval Result Cache<br/>Vector search results]
        L4[L4: Embedding Cache<br/>Deterministic, long TTL]
        L5[L5: Tool Result Cache<br/>API/DB call results]
        L6[L6: Reranker Cache<br/>Cross-encoder scores]
        L7[L7: Auth Decision Cache<br/>Short TTL, immediate invalidation]
        L8[L8: Document Parse Cache<br/>PDF/OCR extraction]
        L9[L9: Eval/Quality Cache<br/>Response quality scores]
    end

    subgraph "Backend Systems"
        LLM[LLM Inference]
        VS[Vector Store]
        TOOLS[Tool APIs]
        AUTH[Auth Service]
    end

    subgraph "Invalidation"
        EB[Event Bus]
        INV[Invalidation Service]
    end

    REQ --> CO
    CO --> KB
    CO --> BP
    BP -->|bypass| LLM
    KB --> L1 & L2 & L3 & L4 & L5 & L6 & L7 & L8 & L9
    L1 -->|miss| LLM
    L2 -->|miss| LLM
    L3 -->|miss| VS
    L5 -->|miss| TOOLS
    L7 -->|miss| AUTH
    EB --> INV --> L1 & L2 & L3 & L4 & L5 & L6 & L7 & L8 & L9
```

## 2. Cache Key Composition

```mermaid
graph LR
    subgraph "Cache Key Dimensions"
        T[tenant_id<br/><i>REQUIRED: isolation</i>]
        PF[permission_fingerprint<br/><i>hash of user roles+groups</i>]
        MV[model_version<br/><i>gpt-4-0125</i>]
        PV[prompt_version<br/><i>v2.3.1</i>]
        IV[index_version<br/><i>idx_20240115_003</i>]
        FW[source_freshness_watermark<br/><i>latest data timestamp</i>]
        SP[safety_policy_version<br/><i>safety_v4</i>]
        RT[risk_tier<br/><i>critical/high/medium/low</i>]
        QH[query_hash / content_hash<br/><i>semantic or exact</i>]
    end

    subgraph "Key Builder"
        KB[SHA-256 Hash]
    end

    subgraph "Output"
        CK[Cache Key<br/><code>a3f2b1c9...</code>]
    end

    T & PF & MV & PV & IV & FW & SP & RT & QH --> KB --> CK
```

## 3. Semantic Cache Flow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant E as Embedding Service
    participant SI as Semantic Index
    participant V as Validator
    participant C as Cache Store
    participant LLM as LLM

    U->>O: Query: "What was Q3 revenue?"
    O->>E: Embed query
    E-->>O: query_vector [1536d]
    O->>SI: ANN search (tenant-scoped, top-5)
    SI-->>O: Candidates [(key1, 0.97), (key2, 0.93)]

    loop For each candidate
        O->>C: Get entry by key
        C-->>O: CacheEntry
        O->>V: Validate security dimensions
        Note over V: Check: tenant_id match<br/>Check: permission_fingerprint<br/>Check: freshness watermark<br/>Check: TTL / staleness
        V-->>O: Valid ✓ or Rejected ✗
    end

    alt Cache HIT (valid entry found)
        O-->>U: Cached response (< 5ms)
    else Cache MISS
        O->>LLM: Generate response
        LLM-->>O: Response
        O->>C: Store with full key dimensions
        O->>SI: Index embedding (tenant-scoped)
        O-->>U: Fresh response
    end
```

## 4. Invalidation Event Flow

```mermaid
sequenceDiagram
    participant SRC as Source System<br/>(IAM, CMS, DB)
    participant IS as Invalidation Service
    participant RE as Rule Engine
    participant EB as Event Bus
    participant L2 as Semantic Cache
    participant L3 as Retrieval Cache
    participant L7 as Auth Cache
    participant XR as Cross-Region Propagator
    participant R2 as Remote Region

    SRC->>IS: Permission revoked (user_123, dataset_finance)
    IS->>RE: Get invalidation command
    RE-->>IS: Command: {layers: [auth, response, retrieval], scope: user, priority: IMMEDIATE}

    IS->>EB: Publish invalidation event

    par Parallel invalidation
        EB->>L7: Invalidate auth decisions for user_123
        L7-->>EB: 15 keys removed
        EB->>L2: Invalidate responses with user_123 fingerprint
        L2-->>EB: 42 keys removed
        EB->>L3: Invalidate retrieval results for user_123
        L3-->>EB: 8 keys removed
    end

    IS->>XR: Propagate cross-region
    XR->>R2: Invalidation command (async)
    R2-->>XR: ACK

    IS->>IS: Audit log: 65 keys invalidated in 3ms
```

## 5. Regional Cache Hierarchy

```mermaid
graph TB
    subgraph "Global Control Plane"
        GCP[Global Invalidation<br/>Coordinator]
        GCR[Global Cache Registry<br/>metadata only]
    end

    subgraph "US-East Region"
        direction TB
        USR[Regional Cache<br/>Redis Cluster]
        subgraph "US-East AZs"
            US1[AZ-1 Local<br/>Process Memory]
            US2[AZ-2 Local<br/>Process Memory]
            US3[AZ-3 Local<br/>Process Memory]
        end
        USR --- US1 & US2 & US3
    end

    subgraph "EU-West Region"
        direction TB
        EUR[Regional Cache<br/>Redis Cluster]
        subgraph "EU-West AZs"
            EU1[AZ-1 Local]
            EU2[AZ-2 Local]
        end
        EUR --- EU1 & EU2
    end

    subgraph "APAC Region"
        direction TB
        APR[Regional Cache<br/>Redis Cluster]
        subgraph "APAC AZs"
            AP1[AZ-1 Local]
            AP2[AZ-2 Local]
        end
        APR --- AP1 & AP2
    end

    GCP -->|invalidation events| USR & EUR & APR
    GCR -.->|metadata sync| USR & EUR & APR

    style GCP fill:#f55,stroke:#333,color:#fff
    style USR fill:#4af,stroke:#333
    style EUR fill:#4af,stroke:#333
    style APR fill:#4af,stroke:#333
```

**Data Residency Rule**: Tenant cache data NEVER leaves designated region. Only invalidation metadata crosses boundaries.

## 6. Cache Stampede Protection

```mermaid
sequenceDiagram
    participant R1 as Request 1
    participant R2 as Request 2
    participant R3 as Request 3
    participant SF as Single-Flight<br/>Controller
    participant C as Cache
    participant B as Backend (LLM)

    Note over C: Cache entry for "Q3 revenue" just expired

    R1->>C: GET "Q3 revenue"
    C-->>R1: MISS (expired)
    R1->>SF: do("Q3_revenue_key", compute_fn)
    SF->>SF: Register in-flight for key

    R2->>C: GET "Q3 revenue"
    C-->>R2: MISS (expired)
    R2->>SF: do("Q3_revenue_key", compute_fn)
    SF-->>R2: Wait (already in-flight)

    R3->>C: GET "Q3 revenue"
    C-->>R3: MISS (expired)
    R3->>SF: do("Q3_revenue_key", compute_fn)
    SF-->>R3: Wait (already in-flight)

    SF->>B: Single backend call
    B-->>SF: Response

    SF->>C: SET (with jittered TTL)
    SF-->>R1: Response
    SF-->>R2: Response (coalesced)
    SF-->>R3: Response (coalesced)

    Note over SF: Only 1 backend call instead of 3!
```

## 7. Hot-Key Protection

```mermaid
graph TB
    subgraph "Detection"
        HKD[Hot-Key Detector<br/>access_count > threshold/sec]
    end

    subgraph "Protection Strategies"
        direction TB
        S1[Strategy 1: Key Replication<br/>key:replica:0, key:replica:1, ..N]
        S2[Strategy 2: L1 Promotion<br/>Copy to process-local memory]
        S3[Strategy 3: Probabilistic Early Refresh<br/>Refresh before TTL based on access rate]
        S4[Strategy 4: Read-Through Coalescing<br/>Single-flight for concurrent reads]
    end

    subgraph "Cache Infrastructure"
        direction LR
        SHARD1[Shard 1]
        SHARD2[Shard 2]
        SHARD3[Shard 3]
        LOCAL[Process Memory<br/>per-instance]
    end

    HKD -->|hot key detected| S1 & S2 & S3 & S4
    S1 -->|replicate| SHARD1 & SHARD2 & SHARD3
    S2 -->|promote| LOCAL
    S3 -->|refresh before expiry| SHARD1
    S4 -->|coalesce| SHARD1

    style HKD fill:#f90,stroke:#333
```

## 8. Cache Safety Verification Flow

```mermaid
flowchart TD
    START[Cache Read Request] --> ISO{Tenant<br/>Isolation<br/>Check}
    ISO -->|entry.tenant ≠ request.tenant| BLOCK[BLOCK + Alert Security]
    ISO -->|tenant match| PERM{Permission<br/>Fingerprint<br/>Match?}
    PERM -->|mismatch| MISS1[Cache MISS<br/>permissions changed]
    PERM -->|match| FRESH{Freshness<br/>Watermark<br/>Valid?}
    FRESH -->|source updated since cache| MISS2[Cache MISS<br/>data stale]
    FRESH -->|within freshness| TTL{TTL<br/>Expired?}
    TTL -->|expired| STALE{Risk Tier<br/>Allows Stale?}
    STALE -->|critical: NEVER| MISS3[Cache MISS<br/>must recompute]
    STALE -->|within tolerance| SWR[Serve Stale +<br/>Background Refresh]
    STALE -->|beyond tolerance| MISS3
    TTL -->|valid| VERSION{Version<br/>Checks OK?}
    VERSION -->|model/prompt/policy changed| MISS4[Cache MISS<br/>version mismatch]
    VERSION -->|all versions match| HIT[Cache HIT ✓]

    style BLOCK fill:#f00,stroke:#333,color:#fff
    style HIT fill:#0a0,stroke:#333,color:#fff
    style MISS1 fill:#fa0,stroke:#333
    style MISS2 fill:#fa0,stroke:#333
    style MISS3 fill:#fa0,stroke:#333
    style MISS4 fill:#fa0,stroke:#333
```

## 9. Billion-Request Cache Path

```mermaid
graph TB
    subgraph "Ingress (1B req/day = ~12K RPS)"
        LB[Load Balancer<br/>Consistent Hash by tenant]
    end

    subgraph "L1: Process Memory (< 1ms)"
        PM1[Instance 1<br/>Hot keys + recent]
        PM2[Instance 2]
        PM3[Instance N]
    end

    subgraph "L2: Distributed Cache (1-5ms)"
        RC[Redis Cluster<br/>32 shards, 256GB<br/>~10M entries]
    end

    subgraph "L3: Regional Store (5-20ms)"
        RS[Regional Redis<br/>Read replicas]
    end

    subgraph "Compute (100-2000ms)"
        LLM[LLM Inference Pool]
        RAG[RAG Pipeline]
        TOOLS[Tool Execution]
    end

    subgraph "Metrics"
        M[Hit Rate Target: 75-85%<br/>Savings: ~$8M/day at scale]
    end

    LB --> PM1 & PM2 & PM3
    PM1 & PM2 & PM3 -->|L1 miss ~40%| RC
    RC -->|L2 miss ~15%| RS
    RS -->|L3 miss ~5%| LLM & RAG & TOOLS
    LLM & RAG & TOOLS -->|write-back| RC

    style LB fill:#36f,stroke:#333,color:#fff
    style RC fill:#e44,stroke:#333,color:#fff
    style LLM fill:#f90,stroke:#333
```

**Path probability at 1B requests/day:**
- L1 hit: 60% → 600M requests served in < 1ms
- L2 hit: 25% → 250M requests served in 1-5ms  
- L3 hit: 10% → 100M requests served in 5-20ms
- Full compute: 5% → 50M requests hit backend (still 50M inference calls/day)

**Cost impact:**
- Without cache: 1B × $0.01 = $10M/day
- With cache (95% hit): 50M × $0.01 + infra = $550K/day
- **Net savings: ~$9.5M/day**
