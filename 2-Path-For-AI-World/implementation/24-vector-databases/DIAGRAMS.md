# Vector Databases - Architecture Diagrams

## 1. Vector DB Architecture

```mermaid
graph TB
    subgraph Client Layer
        APP[Application]
        SDK[SDK / Client Library]
    end

    subgraph API Layer
        REST[REST API]
        GRPC[gRPC API]
        LB[Load Balancer]
    end

    subgraph Query Engine
        QP[Query Planner]
        FE[Filter Engine]
        ANN[ANN Search]
        RANK[Re-Ranker / Scorer]
        FUSION[Score Fusion<br/>RRF / Linear]
    end

    subgraph Index Layer
        HNSW[HNSW Graph Index]
        IVF[IVF Inverted Index]
        PL[Payload Indexes<br/>keyword, int, geo]
        FT[Full-Text Index<br/>BM25]
    end

    subgraph Storage Layer
        VEC[Vector Storage<br/>mmap / disk]
        META[Metadata Store]
        WAL[Write-Ahead Log]
        SEG[Segment Manager]
    end

    subgraph Infrastructure
        REP[Replication<br/>Raft / Primary-Replica]
        SHARD[Shard Manager]
        SNAP[Snapshot Engine]
        MON[Metrics / Observability]
    end

    APP --> SDK --> LB
    LB --> REST & GRPC
    REST & GRPC --> QP
    QP --> FE --> PL
    QP --> ANN --> HNSW & IVF
    QP --> FT
    ANN --> RANK
    FT --> FUSION
    RANK --> FUSION

    HNSW & IVF --> VEC
    PL --> META
    VEC --> SEG
    SEG --> WAL
    SEG --> REP
    REP --> SHARD
```

## 2. HNSW Graph Structure

```mermaid
graph TB
    subgraph "Layer 2 (Sparse - Long Range)"
        L2A((A)) --- L2D((D))
        L2D --- L2G((G))
        L2A --- L2G
    end

    subgraph "Layer 1 (Medium Density)"
        L1A((A)) --- L1B((B))
        L1A --- L1D((D))
        L1B --- L1C((C))
        L1D --- L1E((E))
        L1D --- L1G((G))
        L1E --- L1F((F))
        L1G --- L1F
    end

    subgraph "Layer 0 (Dense - All Vectors)"
        L0A((A)) --- L0B((B))
        L0A --- L0C((C))
        L0B --- L0C
        L0B --- L0D((D))
        L0C --- L0E((E))
        L0D --- L0E
        L0D --- L0F((F))
        L0E --- L0F
        L0F --- L0G((G))
        L0D --- L0G
        L0E --- L0H((H))
        L0F --- L0H
        L0G --- L0H
    end

    L2A -.->|"enter"| L1A
    L2D -.-> L1D
    L2G -.-> L1G
    L1A -.-> L0A
    L1B -.-> L0B
    L1D -.-> L0D
    L1E -.-> L0E
    L1F -.-> L0F
    L1G -.-> L0G

    Q[/"Query Vector"/] ==>|"1. Enter top layer"| L2A
    L2A ==>|"2. Greedy descent"| L1D
    L1D ==>|"3. Navigate to neighborhood"| L0E
    L0E ==>|"4. Return nearest"| RES[/"Results: E, F, H"/]

    style Q fill:#ff9,stroke:#333
    style RES fill:#9f9,stroke:#333
```

## 3. IVF Clustering Approach

```mermaid
graph TB
    subgraph "Training Phase"
        DATA[All Vectors<br/>N = 1,000,000] --> KMEANS[K-Means Clustering<br/>nlist = 1024]
        KMEANS --> C1[Centroid 1]
        KMEANS --> C2[Centroid 2]
        KMEANS --> C3[Centroid ...]
        KMEANS --> CK[Centroid 1024]
    end

    subgraph "Index Structure (Inverted Lists)"
        C1 --> IL1["List 1<br/>~976 vectors"]
        C2 --> IL2["List 2<br/>~1001 vectors"]
        C3 --> IL3["List 3<br/>~989 vectors"]
        CK --> ILK["List 1024<br/>~1034 vectors"]
    end

    subgraph "Query Phase"
        QV[/"Query Vector"/] --> DIST[Compute distance<br/>to all centroids]
        DIST --> TOP["Select top nprobe=32<br/>nearest centroids"]
        TOP --> SCAN["Brute-force scan<br/>~32,000 vectors"]
        SCAN --> RES[/"Top-K Results"/]
    end

    style QV fill:#ff9,stroke:#333
    style RES fill:#9f9,stroke:#333
    style SCAN fill:#fdd,stroke:#333
```

## 4. Hybrid Search Merging

```mermaid
graph LR
    subgraph Input
        Q["User Query:<br/>'python async error handling'"]
    end

    subgraph "Vector Search Path"
        EMB[Embed Query<br/>→ 1536-dim vector]
        ANN[ANN Search<br/>HNSW]
        VR["Vector Results<br/>doc_7: 0.89<br/>doc_3: 0.85<br/>doc_12: 0.82<br/>doc_1: 0.80<br/>doc_9: 0.78"]
    end

    subgraph "Keyword Search Path"
        TOK[Tokenize + BM25]
        BM25[Inverted Index<br/>Search]
        KR["BM25 Results<br/>doc_3: 12.4<br/>doc_5: 11.8<br/>doc_7: 10.2<br/>doc_15: 9.1<br/>doc_1: 8.7"]
    end

    subgraph "Score Fusion"
        RRF["RRF Fusion<br/>score = Σ 1/(k + rank_i)<br/>k = 60"]
        NORM["Normalized Scores<br/>doc_3: 0.033<br/>doc_7: 0.031<br/>doc_1: 0.024<br/>doc_5: 0.016<br/>doc_12: 0.015"]
    end

    subgraph Output
        FINAL[/"Final Ranked Results<br/>1. doc_3<br/>2. doc_7<br/>3. doc_1<br/>4. doc_5<br/>5. doc_12"/]
    end

    Q --> EMB --> ANN --> VR --> RRF
    Q --> TOK --> BM25 --> KR --> RRF
    RRF --> NORM --> FINAL

    style Q fill:#ff9
    style FINAL fill:#9f9
```

## 5. Blue-Green Index Migration

```mermaid
stateDiagram-v2
    [*] --> Blue_Active: Initial deployment

    state "Blue Index (Active)" as Blue_Active {
        [*] --> Serving_Traffic_Blue
        Serving_Traffic_Blue: Handles all queries
    }

    state "Green Index (Building)" as Green_Building {
        [*] --> Create_Green
        Create_Green --> Populate_Data
        Populate_Data --> Build_Index
        Build_Index --> Validate
    }

    state "Validation" as Validate_State {
        [*] --> Shadow_Traffic
        Shadow_Traffic --> Compare_Recall
        Compare_Recall --> Compare_Latency
        Compare_Latency --> Pass_Fail
    }

    state "Traffic Switch" as Switch {
        [*] --> Route_to_Green
        Route_to_Green --> Monitor_Errors
        Monitor_Errors --> Stable
    }

    state "Rollback Window" as Rollback {
        [*] --> Keep_Blue_48h
        Keep_Blue_48h --> Decommission_Blue
    }

    Blue_Active --> Green_Building: Trigger migration
    Green_Building --> Validate_State: Index ready
    Validate_State --> Switch: Validation passed
    Validate_State --> Blue_Active: Validation failed\n(abort)
    Switch --> Rollback: Switch complete
    Rollback --> [*]: Blue decommissioned

    Switch --> Blue_Active: Errors detected\n(rollback)
```

## 6. Vector DB Selection Decision Tree

```mermaid
graph TD
    START{{"How many vectors?"}}

    START -->|"< 100K"| SMALL["Small Scale"]
    START -->|"100K - 10M"| MEDIUM["Medium Scale"]
    START -->|"10M - 1B"| LARGE["Large Scale"]
    START -->|"> 1B"| MASSIVE["Massive Scale"]

    SMALL --> S1{"Need persistence?"}
    S1 -->|No| FAISS["FAISS<br/>(in-memory)"]
    S1 -->|Yes| S2{"Need relational joins?"}
    S2 -->|Yes| PGVEC1["pgvector"]
    S2 -->|No| CHROMA["Chroma / LanceDB"]

    MEDIUM --> M1{"Ops team available?"}
    M1 -->|No| M2{"Budget?"}
    M2 -->|"$$"| PINECONE["Pinecone Serverless"]
    M2 -->|"$"| QDRANT_C["Qdrant Cloud"]
    M1 -->|Yes| M3{"Primary need?"}
    M3 -->|"Best filtering"| QDRANT["Qdrant"]
    M3 -->|"Hybrid search"| WEAVIATE["Weaviate"]
    M3 -->|"SQL + vectors"| PGVEC2["pgvector"]
    M3 -->|"Existing ES"| ES["Elasticsearch"]

    LARGE --> L1{"Single node OK?"}
    L1 -->|Yes| L2{"RAM budget?"}
    L2 -->|"High (>64GB)"| QDRANT2["Qdrant + Quantization"]
    L2 -->|"Low"| LANCE["LanceDB (disk-based)"]
    L1 -->|No| L3{"GPU available?"}
    L3 -->|Yes| MILVUS["Milvus (GPU)"]
    L3 -->|No| MILVUS2["Milvus (distributed)"]

    MASSIVE --> MILVUS3["Milvus Distributed<br/>+ DiskANN"]

    style FAISS fill:#e8f5e9
    style CHROMA fill:#e8f5e9
    style PGVEC1 fill:#e3f2fd
    style PGVEC2 fill:#e3f2fd
    style PINECONE fill:#fff3e0
    style QDRANT fill:#fce4ec
    style QDRANT_C fill:#fce4ec
    style QDRANT2 fill:#fce4ec
    style WEAVIATE fill:#f3e5f5
    style ES fill:#fff8e1
    style MILVUS fill:#e0f7fa
    style MILVUS2 fill:#e0f7fa
    style MILVUS3 fill:#e0f7fa
    style LANCE fill:#f1f8e9
```

## 7. Multi-Tenant Index Patterns

```mermaid
graph TB
    subgraph "Pattern 1: Shared Index + Filter"
        SI[Single HNSW Index<br/>All tenants' vectors]
        SI --> F1["Query: vector + filter<br/>tenant_id = 'acme'"]
        F1 --> R1["Results: only Acme vectors"]

        PRO1["✓ Simple ops<br/>✓ Low cost<br/>✓ Easy scaling"]
        CON1["✗ Noisy neighbors<br/>✗ Filter overhead<br/>✗ No isolation"]
    end

    subgraph "Pattern 2: Namespace/Partition"
        NS[Logical Partitions]
        NS --> NS1["Namespace: acme<br/>50K vectors"]
        NS --> NS2["Namespace: globex<br/>200K vectors"]
        NS --> NS3["Namespace: initech<br/>10K vectors"]

        PRO2["✓ Logical isolation<br/>✓ Per-tenant stats<br/>✓ Moderate cost"]
        CON2["✗ Shared resources<br/>✗ Hot tenants affect others"]
    end

    subgraph "Pattern 3: Collection per Tenant"
        CT1["Collection: acme<br/>HNSW M=16"]
        CT2["Collection: globex<br/>HNSW M=32"]
        CT3["Collection: initech<br/>IVF (small)"]

        PRO3["✓ Full isolation<br/>✓ Custom config<br/>✓ Independent scaling"]
        CON3["✗ High overhead<br/>✗ Complex ops<br/>✗ Connection limits"]
    end

    subgraph "Pattern 4: Hybrid (Tiered)"
        TIER["Tenant Tier Router"]
        TIER -->|"Free tier<br/>(1000s of tenants)"| SHARED["Shared Index<br/>+ filter"]
        TIER -->|"Pro tier<br/>(100s of tenants)"| PART["Dedicated Partition"]
        TIER -->|"Enterprise<br/>(10s of tenants)"| DEDICATED["Dedicated Collection<br/>+ Read Replicas"]

        PRO4["✓ Cost-efficient<br/>✓ Performance where needed<br/>✓ Scalable"]
        CON4["✗ Complex routing<br/>✗ Migration between tiers"]
    end
```

## 8. Index Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Planned: Create request

    Planned --> Creating: Resources allocated
    Creating --> Building: Schema created

    state Building {
        [*] --> Inserting_Data
        Inserting_Data --> Training: Batch complete (IVF)
        Training --> Indexing: Training done
        Inserting_Data --> Indexing: No training needed (HNSW)
        Indexing --> Optimizing: Initial index built
        Optimizing --> [*]: Segments merged
    }

    Building --> Validating: Build complete
    Validating --> Active: Recall/latency OK
    Validating --> Failed: Below thresholds

    Failed --> Building: Retry with new params
    Failed --> [*]: Abandoned

    Active --> Degraded: Tombstones > 20%\nor latency spike
    Degraded --> Active: Compaction complete
    Degraded --> Rebuilding: Cannot recover

    Active --> Migrating: Blue-green triggered
    Migrating --> Deprecated: New index activated
    Migrating --> Active: Migration failed\n(rollback)

    Deprecated --> Archived: Retention period passed
    Archived --> [*]: Deleted

    Rebuilding --> Building: New version created

    Active --> Active: Maintenance\n(backup, metrics)

    note right of Active
        Healthy state:
        - Serving queries
        - Accepting writes
        - Metrics collected
    end note

    note right of Degraded
        Triggers:
        - Tombstone ratio > 20%
        - P99 latency > 2x baseline
        - Recall estimate < target
        - Segment count > threshold
    end note
```
