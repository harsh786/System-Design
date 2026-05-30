# Diagrams: Sharding & Partitioning for Vector Databases

## 1. Partition Strategy Comparison

```mermaid
graph TB
    subgraph "Partitioning Strategies"
        direction TB
        A[Incoming Document] --> B{Partition Router}
        B -->|tenant_id| C[Tenant Partition]
        B -->|classifier| D[Domain Partition]
        B -->|timestamp| E[Time Partition]
        B -->|geo_region| F[Geography Partition]
        B -->|sensitivity| G[Risk Partition]
        B -->|model_version| H[Embedding Version Partition]
        B -->|content_type| I[Modality Partition]
        B -->|access_freq| J[Hot/Cold Partition]
    end

    subgraph "Properties"
        C --> C1[Isolation: Strong<br/>Routing: Deterministic<br/>GDPR: Drop partition]
        D --> D1[Isolation: Medium<br/>Routing: Classifier<br/>Recall: Domain-specific]
        E --> E1[Isolation: Time-based<br/>Routing: Range<br/>Retention: Drop old]
        J --> J1[Isolation: Tier-based<br/>Routing: Frequency<br/>Cost: Optimized]
    end
```

## 2. Shard Routing Architecture

```mermaid
graph TB
    Client[Client Query] --> LB[Load Balancer]
    LB --> Router[Shard Router]

    Router --> Strategy{Strategy Selection}

    Strategy -->|"tenant_id present"| SS[Single Shard]
    Strategy -->|"no routing key"| FO[Fanout All Shards]
    Strategy -->|"query_text present"| TS[Two-Stage]
    Strategy -->|"large cluster"| HR[Hierarchical]
    Strategy -->|"hybrid search"| FR[Federated]

    SS --> S1[Shard 1]

    FO --> S1
    FO --> S2[Shard 2]
    FO --> S3[Shard 3]
    FO --> SN[Shard N]

    TS --> Classifier[Domain Classifier]
    Classifier --> S2
    Classifier --> S3

    HR --> Coarse[Coarse Index<br/>Centroids]
    Coarse --> S1
    Coarse --> S3

    FR --> VDB[(Vector DB)]
    FR --> ES[(Elasticsearch)]
    FR --> SQL[(SQL DB)]
    FR --> KG[(Knowledge Graph)]

    S1 --> Merge[Result Merger]
    S2 --> Merge
    S3 --> Merge
    SN --> Merge
    VDB --> RRF[Reciprocal Rank Fusion]
    ES --> RRF
    SQL --> RRF
    KG --> RRF

    Merge --> Response[Response]
    RRF --> Response
```

## 3. Fanout Query Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Router
    participant S1 as Shard 1
    participant S2 as Shard 2
    participant S3 as Shard 3
    participant M as Merger

    C->>R: search(vector, top_k=10)
    Note over R: No routing key → Fanout
    Note over R: local_k = 10 × 3 = 30 (oversampling)

    par Parallel Search
        R->>S1: search(vector, top_k=30)
        R->>S2: search(vector, top_k=30)
        R->>S3: search(vector, top_k=30)
    end

    S1-->>M: 30 results (local top-30)
    S2-->>M: 30 results (local top-30)
    S3-->>M: 28 results (fewer matches)

    Note over M: Deduplicate by doc_id
    Note over M: Sort by score descending
    Note over M: Take global top-10

    M-->>C: 10 results (global top-10)

    Note over C: Latency = max(S1, S2, S3) latency<br/>+ merge overhead
```

## 4. Multi-Tenant Index Patterns

```mermaid
graph TB
    subgraph "Pattern 1: Shared Index"
        SI[Single HNSW Index]
        T1A[Tenant A vectors] --> SI
        T1B[Tenant B vectors] --> SI
        T1C[Tenant C vectors] --> SI
        SI --> F1[Mandatory Filter:<br/>tenant_id = X]
        F1 --> R1[Results]
        style SI fill:#ffcccc
        note1[Risk: Noisy neighbor<br/>ef_search must be 2-3x higher]
    end

    subgraph "Pattern 2: Namespace"
        NS_A[Namespace A<br/>10K vectors]
        NS_B[Namespace B<br/>50K vectors]
        NS_C[Namespace C<br/>100K vectors]
        NS_A --> PHY[Shared Physical Infra]
        NS_B --> PHY
        NS_C --> PHY
        style PHY fill:#ffffcc
    end

    subgraph "Pattern 3: Dedicated Index"
        IDX_A[Index A<br/>HNSW M=16<br/>dim=1536]
        IDX_B[Index B<br/>HNSW M=32<br/>dim=768]
        IDX_C[Index C<br/>IVF<br/>dim=1536]
        style IDX_A fill:#ccffcc
        style IDX_B fill:#ccffcc
        style IDX_C fill:#ccffcc
    end

    subgraph "Pattern 4: Cell-Based"
        Cell1[Cell 1<br/>Small tenants A-F]
        Cell2[Cell 2<br/>Medium tenants G-J]
        Cell3[Cell 3<br/>Large tenant K]
        Cell1 --> Cluster1[K8s Cluster 1]
        Cell2 --> Cluster2[K8s Cluster 2]
        Cell3 --> Cluster3[K8s Cluster 3]
    end

    subgraph "Tenant Assignment Logic"
        TA{Vector Count?}
        TA -->|"< 10K"| P1[Pattern 1: Shared]
        TA -->|"10K - 1M"| P2[Pattern 2: Namespace]
        TA -->|"1M - 10M"| P3[Pattern 3: Dedicated]
        TA -->|"> 10M"| P4[Pattern 4: Cell]
    end
```

## 5. Blue-Green Reindexing

```mermaid
sequenceDiagram
    participant App as Application
    participant LB as Router
    participant Blue as Blue Index<br/>(v1 embeddings)
    participant Green as Green Index<br/>(v2 embeddings)
    participant Embed as Embedding Service v2

    Note over Blue: Currently serving all traffic

    rect rgb(200, 255, 200)
        Note over Green: Phase 1: Build Green Index
        loop For each document
            Embed->>Green: Re-embed with model v2
        end
    end

    rect rgb(255, 255, 200)
        Note over LB: Phase 2: Shadow Traffic
        App->>LB: Query
        par
            LB->>Blue: Search (serving)
            LB->>Green: Search (shadow, compare only)
        end
        Blue-->>App: Results (served to user)
        Note over LB: Compare recall: Green vs Blue
    end

    rect rgb(200, 200, 255)
        Note over LB: Phase 3: Switch (Green recall >= Blue)
        App->>LB: Query
        LB->>Green: Search (now serving)
        Green-->>App: Results
        Note over Blue: Keep alive 24-72h for rollback
    end

    rect rgb(255, 200, 200)
        Note over Blue: Phase 4: Decommission Blue
        Blue->>Blue: Delete index
    end
```

## 6. Ingestion Pipeline Architecture

```mermaid
graph TB
    subgraph "Sources"
        S3[S3/GCS Bucket]
        DB[(Database CDC)]
        API[REST API Upload]
        Confluence[Confluence]
    end

    subgraph "Change Detection"
        CDC[Change Detector<br/>ETags / CDC / Polling]
    end

    subgraph "Queue Layer"
        PQ[Priority Queue]
        UQ[Urgent Lane]
        NQ[Normal Lane]
        BQ[Batch Lane]
        PQ --> UQ
        PQ --> NQ
        PQ --> BQ
    end

    subgraph "Processing Workers"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker 3]
        W4[Worker 4]
    end

    subgraph "Pipeline Stages"
        Parse[Parse / OCR /<br/>Table Extract]
        Chunk[Chunking<br/>512 tokens, 50 overlap]
        Embed[Batch Embedding<br/>64 items/batch]
        Dedup[Idempotency Check<br/>source_id + content_hash]
    end

    subgraph "Index Writers"
        VW[Vector Index Writer<br/>Batched, Partitioned]
        KW[Keyword Index Writer<br/>Elasticsearch]
    end

    subgraph "Storage"
        VDB[(Vector DB<br/>Partitioned by Tenant)]
        ES[(Elasticsearch<br/>BM25 Index)]
    end

    subgraph "Monitoring"
        FM[Freshness Monitor<br/>Source→Index lag]
        RM[Regression Monitor<br/>Golden query recall]
        DLQ[Dead Letter Queue<br/>Failed jobs]
    end

    S3 --> CDC
    DB --> CDC
    API --> CDC
    Confluence --> CDC

    CDC --> PQ

    UQ --> W1
    NQ --> W2
    NQ --> W3
    BQ --> W4

    W1 --> Dedup
    W2 --> Dedup
    W3 --> Dedup
    W4 --> Dedup

    Dedup -->|new| Parse
    Dedup -->|duplicate| Skip[Skip]

    Parse --> Chunk
    Chunk --> Embed
    Embed --> VW
    Embed --> KW

    VW --> VDB
    KW --> ES

    VW --> FM
    Parse -.->|failure| DLQ
    Embed -.->|failure| DLQ
    VW --> RM
```

## 7. Hot/Cold Partitioning

```mermaid
graph TB
    subgraph "Query Path"
        Q[Query] --> QR{Include cold?}
        QR -->|No| HotSearch[Search Hot Only<br/>~20ms]
        QR -->|Yes| AllSearch[Search Hot + Cold<br/>~200ms]
    end

    subgraph "Hot Tier (RAM/SSD)"
        style HotTier fill:#ffcccc
        HotTier[Hot Tier<br/>20% of data<br/>80% of queries]
        HotTier --> H1[Recent docs < 30 days]
        HotTier --> H2[Frequently accessed]
        HotTier --> H3[High-priority tenants]
    end

    subgraph "Warm Tier (SSD)"
        style WarmTier fill:#ffffcc
        WarmTier[Warm Tier<br/>30% of data]
        WarmTier --> W1[30-90 days old]
        WarmTier --> W2[Occasional access]
    end

    subgraph "Cold Tier (Disk/Object Store)"
        style ColdTier fill:#ccccff
        ColdTier[Cold Tier<br/>50% of data<br/>5% of queries]
        ColdTier --> C1[> 90 days old]
        ColdTier --> C2[Rarely accessed]
        ColdTier --> C3[Compliance retention]
    end

    subgraph "Migration Engine"
        ME[Access Frequency Tracker]
        ME -->|"No access 30d"| MoveWarm[Move to Warm]
        ME -->|"No access 90d"| MoveCold[Move to Cold]
        ME -->|"Accessed again"| Promote[Promote to Hot]
    end

    HotSearch --> HotTier
    AllSearch --> HotTier
    AllSearch --> WarmTier
    AllSearch --> ColdTier
```

## 8. Metadata Filtering Architecture

```mermaid
graph TB
    subgraph "Query with Filters"
        Q["search(vector, top_k=10,<br/>filters={tenant_id: 'X',<br/>domain: 'legal',<br/>created_at > '2024-01'})"]
    end

    subgraph "Filter Strategy Selection"
        FS{Selectivity?}
        Q --> FS
        FS -->|"Eliminates > 50%"| PreFilter[Pre-Filter Strategy]
        FS -->|"Eliminates < 50%"| PostFilter[Post-Filter Strategy]
    end

    subgraph "Pre-Filter Path"
        PreFilter --> MI[Metadata Index<br/>B-tree on tenant_id<br/>Bitmap on domain]
        MI --> Narrow[Narrowed Vector Set<br/>Only matching IDs]
        Narrow --> VS1[Vector Search<br/>on subset]
        VS1 --> R1[Results<br/>High precision]
    end

    subgraph "Post-Filter Path"
        PostFilter --> VS2[Vector Search<br/>ef_search = k × 1/selectivity × 1.5]
        VS2 --> Candidates[Over-fetched Candidates]
        Candidates --> MF[Apply Metadata Filters]
        MF --> R2[Results<br/>May have fewer than k]
    end

    subgraph "Mandatory Filters (Always Pre-Filter)"
        MandatoryNote[tenant_id: ALWAYS pre-filter<br/>Never search across tenants<br/>Security boundary]
    end

    subgraph "Compound Index"
        CI[Compound Index:<br/>tenant_id + domain + created_at<br/>Covers 90% of queries]
    end
```

## 9. Hierarchical Retrieval Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Router
    participant CI as Coarse Index<br/>(1 centroid per shard)
    participant S1 as Shard 1
    participant S2 as Shard 2
    participant S3 as Shard 3
    participant S4 as Shard 4
    participant S5 as Shard 5
    participant M as Merger

    C->>R: search(vector, top_k=10)
    Note over R: 1000 shards total<br/>Full fanout too expensive

    rect rgb(255, 255, 200)
        Note over CI: Level 1: Coarse Search
        R->>CI: Find top shards (compare to centroids)
        CI-->>R: [Shard 2: 0.92, Shard 5: 0.88, Shard 1: 0.85]
        Note over R: Selected 3 of 1000 shards
    end

    rect rgb(200, 255, 200)
        Note over S1,S5: Level 2: Fine Search (only selected shards)
        par
            R->>S1: search(vector, top_k=30)
            R->>S2: search(vector, top_k=30)
            R->>S5: search(vector, top_k=30)
        end
        S1-->>M: 30 results
        S2-->>M: 30 results
        S5-->>M: 30 results
    end

    Note over M: Merge + deduplicate + top-10
    M-->>C: 10 results

    Note over C: Searched 3 shards instead of 1000<br/>Latency: ~70ms vs ~500ms<br/>Recall: ~95% (depends on centroid quality)
```
