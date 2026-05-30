# Embeddings - Architecture Diagrams

## 1. Embedding Model Selection Flowchart

```mermaid
flowchart TD
    Start([Need Embeddings]) --> Q1{What modality?}

    Q1 -->|Text only| Q2{Language?}
    Q1 -->|Text + Images| MM[Multimodal: CLIP/SigLIP]
    Q1 -->|Code| CODE[Voyage Code-2 / CodeBERT]

    Q2 -->|English only| Q3{Domain?}
    Q2 -->|Multilingual| MULTI[Cohere Multilingual v3 / mE5]

    Q3 -->|General| Q4{Budget?}
    Q3 -->|Medical/Legal/Finance| DOMAIN[Domain-specific model or Fine-tune]

    Q4 -->|API OK, quality priority| Q5{Corpus size?}
    Q4 -->|Self-hosted required| SELF[BGE-large / GTE-large / Nomic]
    Q4 -->|Minimum cost| CHEAP[all-MiniLM-L6-v2]

    Q5 -->|< 1M docs| LARGE[OpenAI 3-large / Voyage large-2]
    Q5 -->|> 10M docs| Q6{Need exact matching?}

    Q6 -->|Yes| HYBRID[Dense + SPLADE hybrid]
    Q6 -->|No| BALANCED[OpenAI 3-small / Cohere v3]

    MM --> EVAL[Evaluate on YOUR data]
    CODE --> EVAL
    MULTI --> EVAL
    DOMAIN --> EVAL
    SELF --> EVAL
    CHEAP --> EVAL
    LARGE --> EVAL
    HYBRID --> EVAL
    BALANCED --> EVAL

    EVAL --> GOOD{Recall@10 > 85%?}
    GOOD -->|Yes| DEPLOY[Deploy to Production]
    GOOD -->|No| FINETUNE[Fine-tune or try different model]
    FINETUNE --> EVAL
```

## 2. Embedding Service Architecture

```mermaid
flowchart TB
    subgraph Clients
        APP[Application]
        BATCH[Batch Processor]
        SEARCH[Search Service]
    end

    subgraph EmbeddingService["Embedding Service"]
        API[API Gateway]
        ROUTER[Model Router]
        CACHE_L1[LRU Cache - Memory]
        CACHE_L2[Redis Cache]

        subgraph Providers
            OAI[OpenAI Provider]
            COH[Cohere Provider]
            VOY[Voyage Provider]
            LOCAL[Local ST Provider]
        end

        RL[Rate Limiter]
        NORM[Normalizer + Truncator]
        COST[Cost Tracker]
        FB[Fallback Handler]
    end

    subgraph Storage
        REDIS[(Redis)]
        METRICS[(Metrics DB)]
    end

    APP --> API
    BATCH --> API
    SEARCH --> API

    API --> ROUTER
    ROUTER --> CACHE_L1
    CACHE_L1 -->|miss| CACHE_L2
    CACHE_L2 -->|miss| RL

    RL --> OAI
    RL --> COH
    RL --> VOY
    RL --> LOCAL

    OAI -->|failure| FB
    COH -->|failure| FB
    VOY -->|failure| FB
    FB --> LOCAL

    OAI --> NORM
    COH --> NORM
    VOY --> NORM
    LOCAL --> NORM

    NORM --> CACHE_L1
    NORM --> CACHE_L2

    CACHE_L2 --- REDIS
    COST --- METRICS
```

## 3. Embedding Evaluation Pipeline

```mermaid
flowchart LR
    subgraph DataPrep["1. Data Preparation"]
        QD[Query-Doc Pairs]
        CAT[Categorize: exact/paraphrase/adversarial/...]
        SPLIT[Train/Eval Split]
    end

    subgraph Embedding["2. Embed"]
        M1[Model A]
        M2[Model B]
        M3[Model C]
        DOCS[Embed All Documents]
        QUERIES[Embed All Queries]
    end

    subgraph Retrieval["3. Retrieve"]
        SIM[Cosine Similarity]
        RANK[Rank Documents]
        TOPK[Get Top-K per Query]
    end

    subgraph Metrics["4. Measure"]
        R1[Recall@1,5,10,20]
        MRR[MRR]
        NDCG[nDCG@10]
        CAT_M[Per-Category Metrics]
    end

    subgraph Analysis["5. Analyze"]
        STAT[Statistical Significance]
        COMP[Comparison Table]
        REPORT[Generate Report]
        REC[Recommendation]
    end

    QD --> CAT --> SPLIT
    SPLIT --> M1 & M2 & M3
    M1 & M2 & M3 --> DOCS & QUERIES
    DOCS & QUERIES --> SIM --> RANK --> TOPK
    TOPK --> R1 & MRR & NDCG & CAT_M
    R1 & MRR & NDCG & CAT_M --> STAT --> COMP --> REPORT --> REC
```

## 4. Blue-Green Migration Workflow

```mermaid
stateDiagram-v2
    [*] --> Planned: Create migration plan

    Planned --> EmbeddingGeneration: Start migration
    note right of Planned
        - Cost estimation
        - Capacity check
        - Create target collection
    end note

    EmbeddingGeneration --> Evaluation: All docs embedded
    note right of EmbeddingGeneration
        - Batch embed with new model
        - Rate limit aware
        - Progress tracking
        - Checkpoint/resume
    end note

    Evaluation --> GradualRollout: New model passes quality gate
    Evaluation --> RolledBack: New model fails quality gate

    note right of Evaluation
        - Run eval queries on both
        - Compare recall@10
        - Regression threshold: -5%
    end note

    GradualRollout --> Active: 100% traffic, monitoring stable
    GradualRollout --> RolledBack: Anomaly detected

    note right of GradualRollout
        - 10% → 25% → 50% → 75% → 100%
        - Monitor latency, errors, scores
        - Wait period between steps
    end note

    Active --> Completed: Rollback window expires (14 days)
    note right of Active
        - Old index kept as backup
        - Daily quality checks
        - Alert on score degradation
    end note

    RolledBack --> [*]: Cleanup new collection

    Completed --> [*]: Delete old collection
```

## 5. Embedding Fine-Tuning Pipeline

```mermaid
flowchart TD
    subgraph DataCollection["1. Collect Training Data"]
        CLICKS[Click Logs]
        QA[QA Pairs]
        SYNTH[LLM-Generated Queries]
        ANNO[Manual Annotations]
    end

    subgraph NegativeMining["2. Hard Negative Mining"]
        BASE[Embed with Base Model]
        SEARCH_N[Find near-miss documents]
        FILTER[Filter out true positives]
        PAIRS[Query + Positive + Hard Negatives]
    end

    subgraph Training["3. Training"]
        LOSS[Multiple Negatives Ranking Loss]
        MATRY[Matryoshka Loss Wrapper]
        TRAIN[Fine-tune All Layers]
        EVAL_T[Evaluate Every N Steps]
        SAVE[Save Best Checkpoint]
    end

    subgraph Evaluation["4. Before/After"]
        BASE_EVAL[Evaluate Base Model]
        TUNE_EVAL[Evaluate Fine-tuned Model]
        COMPARE[Compare Metrics]
        DECIDE{Improvement > 5%?}
    end

    subgraph Deploy["5. Deploy"]
        EXPORT[Export Model]
        SERVE[Model Serving]
        MIGRATE[Trigger Migration]
    end

    CLICKS & QA & SYNTH & ANNO --> BASE
    BASE --> SEARCH_N --> FILTER --> PAIRS
    PAIRS --> LOSS --> MATRY --> TRAIN
    TRAIN --> EVAL_T --> SAVE
    SAVE --> BASE_EVAL & TUNE_EVAL
    BASE_EVAL & TUNE_EVAL --> COMPARE --> DECIDE
    DECIDE -->|Yes| EXPORT --> SERVE --> MIGRATE
    DECIDE -->|No| PAIRS
```

## 6. Dense vs Sparse vs Late-Interaction Comparison

```mermaid
flowchart LR
    subgraph Dense["Dense (Bi-Encoder)"]
        direction TB
        D_DOC[Document] --> D_ENC[Encoder]
        D_ENC --> D_VEC["Single Vector [0.02, -0.15, ...]<br/>768-3072 dims"]
        D_Q[Query] --> D_QENC[Encoder]
        D_QENC --> D_QVEC["Single Vector"]
        D_VEC -.->|"dot product"| D_SCORE[Score: 0.85]
        D_QVEC -.-> D_SCORE
    end

    subgraph Sparse["Sparse (SPLADE)"]
        direction TB
        S_DOC[Document] --> S_ENC[Sparse Encoder]
        S_ENC --> S_VEC["Sparse Vector<br/>{neural: 2.1, network: 1.8, ...}<br/>~200 non-zero of 30k"]
        S_Q[Query] --> S_QENC[Sparse Encoder]
        S_QENC --> S_QVEC["Sparse Vector"]
        S_VEC -.->|"sparse dot product"| S_SCORE[Score: 12.4]
        S_QVEC -.-> S_SCORE
    end

    subgraph Late["Late Interaction (ColBERT)"]
        direction TB
        L_DOC[Document] --> L_ENC[Token Encoder]
        L_ENC --> L_VEC["Per-Token Vectors<br/>[v1, v2, ..., vN]<br/>N vectors × 128 dims"]
        L_Q[Query] --> L_QENC[Token Encoder]
        L_QENC --> L_QVEC["Per-Token Vectors<br/>[q1, q2, ..., qM]"]
        L_VEC -.->|"MaxSim"| L_SCORE[Score: 0.92]
        L_QVEC -.-> L_SCORE
    end
```

## 7. Embedding Versioning Strategy

```mermaid
flowchart TD
    subgraph VersionRegistry["Version Registry"]
        V1["v1: ada-002<br/>dims: 1536<br/>status: deleted"]
        V2["v2: text-embedding-3-small<br/>dims: 1536<br/>status: deprecated"]
        V3["v3: text-embedding-3-large<br/>dims: 1024 (truncated)<br/>status: ACTIVE"]
        V4["v4: fine-tuned-bge<br/>dims: 1024<br/>status: shadow testing"]
    end

    subgraph Collections["Vector Store Collections"]
        C2[("search_v2_3small<br/>10M vectors<br/>⚠️ rollback backup")]
        C3[("search_v3_3large<br/>10M vectors<br/>✅ serving traffic")]
        C4[("search_v4_bge_ft<br/>10M vectors<br/>🔄 building")]
    end

    subgraph Metadata["Per-Document Metadata"]
        META["doc_id: abc123<br/>embedding_model: text-embedding-3-large<br/>embedding_version: 3<br/>embedded_at: 2024-03-15<br/>source_text_hash: sha256:...<br/>dimensions: 1024"]
    end

    V2 --> C2
    V3 --> C3
    V4 --> C4
    C3 --> META

    subgraph Lifecycle["Version Lifecycle"]
        NEW[New] -->|embed all docs| SHADOW[Shadow]
        SHADOW -->|eval passes| CANARY[Canary 10%]
        CANARY -->|no regression| ACTIVE[Active 100%]
        ACTIVE -->|new version deployed| DEPRECATED[Deprecated]
        DEPRECATED -->|rollback window passes| DELETED[Deleted]
    end
```

## 8. Embedding Cost Optimization

```mermaid
flowchart TD
    subgraph Problem["Cost Drivers"]
        RE_EMBED[Re-embedding unchanged docs]
        DUPLICATE[Duplicate query embeddings]
        OVER_DIM[Over-dimensioned vectors]
        WRONG_MODEL[Using expensive model for simple tasks]
    end

    subgraph Solutions["Optimization Strategies"]
        subgraph Caching["Layer 1: Caching"]
            MEM_CACHE[In-Memory LRU<br/>10K entries, <1ms]
            REDIS_CACHE[Redis<br/>1M entries, 1-5ms]
            HASH_CHECK[Source text hash check<br/>Skip if unchanged]
        end

        subgraph Dimension["Layer 2: Dimension Optimization"]
            MATRY[Matryoshka truncation<br/>3072 → 1024 or 256]
            PQ[Product Quantization<br/>4x compression]
            BINARY[Binary quantization<br/>32x compression + rerank]
        end

        subgraph Routing["Layer 3: Model Routing"]
            SIMPLE_Q[Simple queries → Small model<br/>$0.02/1M tokens]
            COMPLEX_Q[Complex queries → Large model<br/>$0.13/1M tokens]
            BATCH_Q[Batch jobs → Self-hosted<br/>$0/token, GPU cost only]
        end

        subgraph Architecture["Layer 4: Architecture"]
            HYBRID_S[Hybrid: BM25 + Dense<br/>Fewer dense lookups needed]
            RERANK[Retrieve 100 → Rerank 10<br/>Cheaper than more dims]
            INCREMENTAL[Incremental indexing<br/>Only embed new/changed docs]
        end
    end

    subgraph Impact["Cost Reduction"]
        I1["Caching: 40-70% savings"]
        I2["Dimensions: 50-75% storage savings"]
        I3["Routing: 30-50% API cost savings"]
        I4["Architecture: 20-40% overall savings"]
    end

    RE_EMBED --> HASH_CHECK & INCREMENTAL
    DUPLICATE --> MEM_CACHE & REDIS_CACHE
    OVER_DIM --> MATRY & PQ & BINARY
    WRONG_MODEL --> SIMPLE_Q & COMPLEX_Q & BATCH_Q

    Caching --> I1
    Dimension --> I2
    Routing --> I3
    Architecture --> I4
```
