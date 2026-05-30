# Scaling Architecture Diagrams

## Million-User Architecture

```mermaid
graph TB
    subgraph Clients
        C1[Web Client]
        C2[Mobile Client]
        C3[API Client]
    end

    subgraph Global Layer
        DNS[DNS / Anycast]
        GLB[Global Load Balancer]
        WAF[WAF + DDoS Protection]
    end

    subgraph Regional Gateway
        GW[API Gateway]
        AUTH[Auth Service]
        RL[Rate Limiter]
        RC[Request Classifier]
        BUD[Budget Checker]
    end

    subgraph Queue Layer
        Q0[Priority-0 Queue]
        Q1[Priority-1 Queue]
        QD[Default Queue]
        QA[Async Jobs Queue]
    end

    subgraph Worker Pools
        WP[Premium Workers]
        WS[Standard Workers]
        WL[Long-Running Workers]
        WE[Eval Workers]
    end

    subgraph AI Services
        MR[Model Router]
        M1[Fast Models]
        M2[Standard Models]
        M3[Premium Models]
    end

    subgraph Data Layer
        VDB[(Vector DB Cluster)]
        RR[Reranker Service]
        CACHE[Cache Hierarchy<br/>L1/L2/L3]
        MEM[(Memory Store)]
        CONV[(Conversation Store)]
    end

    subgraph Tools
        TS[Tool Service Mesh]
        T1[Tool A]
        T2[Tool B]
        T3[Tool C]
    end

    subgraph Observability
        TR[Trace Collector]
        EVAL[Eval Pipeline]
        MON[Monitoring]
        ALERT[Alerting]
    end

    C1 & C2 & C3 --> DNS --> GLB --> WAF
    WAF --> GW --> AUTH --> RL --> RC --> BUD
    BUD --> Q0 & Q1 & QD & QA
    Q0 --> WP
    Q1 --> WP & WS
    QD --> WS
    QA --> WL & WE
    WP & WS --> MR --> M1 & M2 & M3
    WP & WS --> VDB --> RR
    WP & WS --> CACHE
    WP & WS --> MEM & CONV
    WS --> TS --> T1 & T2 & T3
    WP & WS & WL --> TR --> EVAL
    TR --> MON --> ALERT
```

## Billion-Request Flow Path

```mermaid
sequenceDiagram
    participant C as Client
    participant DNS as DNS/Anycast
    participant RGW as Regional Gateway
    participant CGW as Cell Gateway
    participant Q as Queue
    participant W as Worker
    participant MC as Model Cache
    participant M as Model Provider
    participant VDB as Vector DB
    participant T as Tools
    participant TR as Traces

    C->>DNS: Request
    DNS->>RGW: Route to nearest region
    RGW->>RGW: Auth + Rate Limit + Classify
    RGW->>CGW: Route to tenant's cell
    CGW->>Q: Enqueue by priority

    Q->>W: Dequeue
    
    loop Agent Steps (1-N)
        W->>MC: Check semantic cache
        alt Cache Hit
            MC-->>W: Cached response
        else Cache Miss
            W->>VDB: Retrieve context
            VDB-->>W: Documents
            W->>M: LLM call (streamed)
            M-->>W: Token stream
            W->>MC: Store in cache
        end
        
        opt Tool Needed
            W->>T: Execute tool
            T-->>W: Result
        end
        
        W->>TR: Write spans (batched)
    end

    W-->>CGW: Stream response
    CGW-->>RGW: Forward stream
    RGW-->>C: SSE/WebSocket stream

    Note over W,TR: Async: memory update, eval sampling, budget update
```

## Cell-Based Architecture

```mermaid
graph TB
    subgraph Global
        GR[Global Router]
        CONFIG[Config Store]
        REP[Replication Coordinator]
    end

    subgraph Region_US_East[Region: us-east-1]
        RGW1[Regional Gateway]
        
        subgraph Cell_1[Cell 1 - Tenants A-D]
            CG1[Cell Gateway]
            CW1[Workers x10]
            CV1[(Vector Shard)]
            CC1[Cache]
            CQ1[Queue Partition]
        end

        subgraph Cell_2[Cell 2 - Tenants E-H]
            CG2[Cell Gateway]
            CW2[Workers x10]
            CV2[(Vector Shard)]
            CC2[Cache]
            CQ2[Queue Partition]
        end

        subgraph Cell_3[Cell 3 - Hot Tenant I]
            CG3[Cell Gateway]
            CW3[Workers x20]
            CV3[(Vector Shard)]
            CC3[Cache]
            CQ3[Queue Partition]
        end
    end

    subgraph Region_US_West[Region: us-west-2 - Standby]
        RGW2[Regional Gateway]
        BC1[Backup Cells]
    end

    GR --> RGW1 & RGW2
    CONFIG --> RGW1 & RGW2
    RGW1 --> CG1 & CG2 & CG3
    REP --> CV1 & CV2 & CV3 & BC1
```

## Backpressure Cascading

```mermaid
graph LR
    subgraph Detection
        ML[Model Latency ↑]
        VL[Vector DB Latency ↑]
        QD[Queue Depth ↑]
        ER[Error Rate ↑]
    end

    subgraph Signals
        BP1[Backpressure Score]
        DL[Degradation Level]
    end

    subgraph Actions
        SH[Request Shedding]
        CB[Circuit Breaking]
        DG[Degrade Features]
        RL[Rate Limiting]
        SC[Scale Up Workers]
    end

    subgraph Recovery
        MON[Monitor Stability]
        REC[Recover One Level]
        FULL[Full Restoration]
    end

    ML & VL & QD & ER --> BP1
    BP1 --> DL
    DL -->|Level 1| DG
    DL -->|Level 2| DG & RL
    DL -->|Level 3| SH & CB & DG & RL
    DL -->|Recovery| MON --> REC --> FULL
    SC -.->|Auto-scale| MON
```

## Request Classification Routing

```mermaid
graph TD
    REQ[Incoming Request] --> CLASS[Classifier]
    
    CLASS -->|Simple Chat| S1[Fast Model Pool<br/>1 step, streaming]
    CLASS -->|Complex Chat| S2[Premium Workers<br/>4+ steps, full pipeline]
    CLASS -->|Retrieval| S3[Retrieval Workers<br/>Heavy vector load]
    CLASS -->|Tool Action| S4[Tool Workers<br/>Circuit breakers]
    CLASS -->|Eval Job| S5[Eval Queue<br/>Background, batch]
    CLASS -->|Long Running| S6[Job Queue<br/>Checkpointing, hours]

    S1 --> P0[Priority Queue 0<br/>< 100ms wait]
    S2 --> P1[Priority Queue 1<br/>< 1s wait]
    S3 --> P1
    S4 --> P1
    S5 --> P3[Batch Queue<br/>< 5min wait]
    S6 --> P3

    P0 --> FAST[Fast Workers<br/>Dedicated]
    P1 --> STD[Standard Workers<br/>Shared]
    P3 --> BATCH[Batch Workers<br/>Spot/Preemptible]
```

## Cache Hierarchy

```mermaid
graph TD
    REQ[Request] --> L1{L1: In-Process}
    
    L1 -->|HIT 30%| RES[Response]
    L1 -->|MISS| L2{L2: Distributed Cache<br/>Redis/Memcached}
    
    L2 -->|HIT 40%| RES
    L2 -->|MISS| L3{L3: Persistent Cache<br/>DB/Object Store}
    
    L3 -->|HIT 15%| RES
    L3 -->|MISS 15%| ORIGIN[Origin Services]
    
    ORIGIN --> RES
    ORIGIN -->|Write back| L3
    L3 -->|Promote| L2
    L2 -->|Promote| L1

    subgraph L1 Contents
        L1A[Conversation Context]
        L1B[Prompt Templates]
        L1C[Hot Embeddings]
    end

    subgraph L2 Contents
        L2A[Semantic Cache]
        L2B[Embedding Cache]
        L2C[Tool Result Cache]
    end

    subgraph L3 Contents
        L3A[RAG Index Results]
        L3B[Model Response Cache]
        L3C[Computed Summaries]
    end
```

## Queue Architecture

```mermaid
graph TB
    subgraph Ingress
        GW[Gateway]
    end

    subgraph Priority Queues
        PQ0[P0: Critical<br/>TTL: 5s<br/>Workers: 20]
        PQ1[P1: High<br/>TTL: 30s<br/>Workers: 15]
        PQD[Default<br/>TTL: 5min<br/>Workers: 10]
        PQA[Async<br/>TTL: 1hr<br/>Workers: 5]
    end

    subgraph Dead Letter
        DLQ[Dead Letter Queue<br/>Failed after 3 retries]
    end

    subgraph Workers
        W0[Premium Pool]
        W1[Standard Pool]
        W2[Background Pool]
    end

    subgraph Backpressure
        MON[Queue Monitor]
        SHED[Shedder]
    end

    GW --> PQ0 & PQ1 & PQD & PQA
    PQ0 --> W0
    PQ1 --> W0 & W1
    PQD --> W1
    PQA --> W2
    W0 & W1 & W2 -->|Failed| DLQ
    MON --> PQ0 & PQ1 & PQD & PQA
    MON -->|Overloaded| SHED --> GW
```

## Capacity Planning Model

```mermaid
graph LR
    subgraph Inputs
        DAU[DAU: 1M]
        RPU[Req/User: 10]
        STEPS[Avg Steps: 4]
        CALLS[Calls/Step: 1.5]
    end

    subgraph Calculation
        DAILY[Daily: 10M requests]
        PEAK[Peak RPS: 347]
        MULT[× Steps × Calls]
    end

    subgraph Component Capacity
        MQPS[Model: 2,083 QPS]
        RQPS[Retrieval: 1,665 QPS]
        TQPS[Tools: 1,388 QPS]
        CQPS[Cache: 5,205 ops/s]
        TRQPS[Traces: 8,675 spans/s]
    end

    subgraph Provisioning
        HEAD[+ 30% Headroom]
        PROV[Provisioned Capacity]
        COST[Cost: $X/day]
    end

    DAU & RPU --> DAILY --> PEAK
    STEPS & CALLS --> MULT
    PEAK --> MULT --> MQPS & RQPS & TQPS & CQPS & TRQPS
    MQPS & RQPS & TQPS --> HEAD --> PROV --> COST
```

## Degraded Mode Levels

```mermaid
stateDiagram-v2
    [*] --> FULL

    FULL --> REDUCED: pressure > 0.5
    REDUCED --> MINIMAL: pressure > 0.7
    MINIMAL --> ERROR: pressure > 0.9

    ERROR --> MINIMAL: stable 5min + pressure < 0.7
    MINIMAL --> REDUCED: stable 5min + pressure < 0.5
    REDUCED --> FULL: stable 5min + pressure < 0.3

    state FULL {
        [*] --> AllFeatures
        AllFeatures: All features active
        AllFeatures: 10 max agent steps
        AllFeatures: Premium models
        AllFeatures: Full retrieval + reranking
        AllFeatures: Tools + Eval + Memory
    }

    state REDUCED {
        [*] --> LimitedFeatures
        LimitedFeatures: 3 max agent steps
        LimitedFeatures: Standard models
        LimitedFeatures: No reranking, no eval
        LimitedFeatures: Tools + Memory active
    }

    state MINIMAL {
        [*] --> BasicOnly
        BasicOnly: 1 model call only
        BasicOnly: Fast model
        BasicOnly: Cache-only retrieval
        BasicOnly: No tools, no memory writes
    }

    state ERROR {
        [*] --> Fallback
        Fallback: Cached responses only
        Fallback: Error pages
        Fallback: Queue for later processing
        Fallback: Only P0 requests served
    }
```
