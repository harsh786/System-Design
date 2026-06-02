# Data Pipeline & Feature Engineering Decision Workflows

> Staff architect guide: How to choose data pipeline patterns, engineer features systematically, and ensure data quality for ML systems.

---

## Diagram 1: ETL vs ELT vs Streaming Decision

```mermaid
flowchart TD
    A[Data Pipeline Needed] --> B{What's your data like?}
    
    B -->|Structured + Known Schema| C[ETL: Transform Before Load]
    B -->|Semi-structured + Evolving Schema| D[ELT: Load Then Transform]
    B -->|Real-time Action Needed| E[STREAMING]
    
    %% ETL Path
    C --> C1[WHY: Clean data enters warehouse]
    C1 --> C2[Cheaper storage - only store transformed]
    C2 --> C3[Tools: Airflow + dbt + Postgres/Redshift]
    C3 --> C4{Use When?}
    C4 --> C4a[Traditional BI dashboards]
    C4 --> C4b[Known query patterns upfront]
    C4 --> C4c[OLTP source systems]
    C4 --> C4d[Compliance: must not store raw PII]
    
    %% ELT Path
    D --> D1[WHY: Keep raw data intact]
    D1 --> D2[Transform differently per use case]
    D2 --> D3[Tools: Spark + Delta Lake + dbt]
    D3 --> D4{Use When?}
    D4 --> D4a[ML features need different transforms than dashboards]
    D4 --> D4b[Schema evolves frequently]
    D4 --> D4c[Multiple teams consume same raw data]
    D4 --> D4d[Need to reprocess historical data with new logic]
    
    %% Streaming Path
    E --> E1[WHY: Cannot wait for batch]
    E1 --> E2[Sub-second latency required]
    E2 --> E3[Tools: Kafka + Flink/Spark Streaming]
    E3 --> E4{Use When?}
    E4 --> E4a[Fraud detection - block transaction NOW]
    E4 --> E4b[Real-time recommendations]
    E4 --> E4c[Monitoring & alerting]
    E4 --> E4d[Session-based features]
    
    %% Cost annotations
    C3 -.->|Cost: $| COST[Cost Comparison]
    D3 -.->|Cost: $$| COST
    E3 -.->|Cost: $$$$| COST

    style C fill:#2d5,color:#fff
    style D fill:#25d,color:#fff
    style E fill:#d52,color:#fff
```

### Decision Rationale

| Factor | ETL | ELT | Streaming |
|--------|-----|-----|-----------|
| Latency tolerance | Hours | Minutes-Hours | Sub-second |
| Schema stability | Fixed | Evolving | Event-driven |
| Storage cost priority | High | Medium | Low (speed matters more) |
| Reprocessing need | Rare | Frequent | N/A |
| Team maturity needed | Low | Medium | High |
| Debugging difficulty | Easy | Medium | Hard |

---

## Diagram 2: Feature Engineering Pipeline

```mermaid
sequenceDiagram
    participant Raw as Raw Data Sources
    participant Val as Validation Layer
    participant Clean as Cleaning Stage
    participant Eng as Feature Engineering
    participant Sel as Feature Selection
    participant Store as Feature Store
    participant Model as Model Training/Serving

    Raw->>Val: Schema validation (Great Expectations)
    Note over Val: WHY: Catch data quality issues BEFORE<br/>they poison model training
    Note over Val: CHECK: columns present, types correct,<br/>no unexpected nulls in required fields
    
    Val-->>Val: FAIL? → Alert + block pipeline
    Val->>Clean: Pass validated data
    
    Clean->>Clean: Handle missing values
    Note over Clean: Strategy depends on WHY missing:<br/>MCAR → impute mean/median<br/>MAR → model-based imputation<br/>MNAR → indicator variable + impute
    
    Clean->>Clean: Remove duplicates
    Note over Clean: WHY: Duplicates bias model toward<br/>repeated examples (overfitting to dupes)
    
    Clean->>Clean: Handle outliers
    Note over Clean: WHY: Models amplify noise in dirty data<br/>CAUTION: Don't remove real rare events!
    
    Clean->>Eng: Clean data ready
    
    Note over Eng: === NUMERIC FEATURES ===
    Eng->>Eng: Log transform (skewed distributions)
    Eng->>Eng: Binning (non-linear relationships)
    Eng->>Eng: Interactions (feature1 × feature2)
    Eng->>Eng: Polynomial features (quadratic effects)
    
    Note over Eng: === CATEGORICAL FEATURES ===
    Eng->>Eng: One-hot encoding (low cardinality)
    Eng->>Eng: Target encoding (high cardinality)
    Eng->>Eng: Embedding lookup (very high cardinality)
    
    Note over Eng: === TEMPORAL FEATURES ===
    Eng->>Eng: Lag features (value N steps ago)
    Eng->>Eng: Rolling windows (mean/std last 7 days)
    Eng->>Eng: Cyclical encoding (hour→sin/cos)
    Eng->>Eng: Time since event (recency)
    
    Note over Eng: === TEXT FEATURES ===
    Eng->>Eng: TF-IDF (sparse, interpretable)
    Eng->>Eng: Sentence embeddings (dense, semantic)
    Eng->>Eng: Entity extraction (structured from unstructured)
    
    Eng->>Sel: Candidate features (potentially 100s)
    
    Note over Sel: WHY SELECT: Fewer features =<br/>faster training + less overfit +<br/>cheaper serving + easier debugging
    
    Sel->>Sel: Filter: Remove low-variance, high-correlation
    Sel->>Sel: Mutual information: Keep high MI with target
    Sel->>Sel: L1 regularization: Let model pick
    Sel->>Sel: SHAP importance: Post-hoc validation
    
    Sel->>Store: Selected features (versioned)
    Note over Store: WHY STORE: Reuse across models,<br/>ensure train/serve consistency,<br/>audit trail for compliance
    
    Store->>Model: Serve features (online or offline)
    Note over Model: Online: Redis/DynamoDB (p99 < 10ms)<br/>Offline: Parquet/Delta Lake (batch)
```

---

## Diagram 3: Data Quality Decision Framework

```mermaid
flowchart TD
    A[Data Arrives] --> B[Schema Check]
    A --> C[Volume Check]
    A --> D[Freshness Check]
    A --> E[Distribution Check]
    A --> F[Null Rate Check]
    A --> G[Cross-table Consistency]
    
    %% Schema
    B --> B1{Columns present?<br/>Types correct?}
    B1 -->|FAIL| B2[BLOCK pipeline + alert on-call]
    B1 -->|PASS| B3[Continue]
    B2 --> B2a[WHY: Wrong schema = model crashes<br/>or produces silent garbage predictions]
    
    %% Volume
    C --> C1{Row count in<br/>expected range?}
    C1 -->|TOO FEW| C2[Investigate: source down? filter bug?]
    C1 -->|TOO MANY| C3[Investigate: duplicate events? replay?]
    C1 -->|NORMAL| C4[Continue]
    C2 --> C2a[WHY: Empty dataset = stale model<br/>Tiny dataset = unreliable retraining]
    C3 --> C3a[WHY: Huge spike = duplicates<br/>bias model toward repeated events]
    
    %% Freshness
    D --> D1{Latest timestamp<br/>within SLA?}
    D1 -->|STALE| D2[Alert: source pipeline broken]
    D1 -->|FRESH| D3[Continue]
    D2 --> D2a[WHY: Stale features = model makes<br/>decisions on old information]
    
    %% Distribution
    E --> E1{Feature stats within<br/>3σ of historical?}
    E1 -->|DRIFT| E2[WARN: drift detected]
    E1 -->|STABLE| E3[Continue]
    E2 --> E2a[WHY: Input drift → predictions<br/>become unreliable over time]
    E2 --> E2b[Action: Log drift score,<br/>trigger retrain if sustained]
    
    %% Nulls
    F --> F1{Null % below<br/>threshold per column?}
    F1 -->|CRITICAL NULL| F2[BLOCK: core feature missing]
    F1 -->|OPTIONAL NULL| F3[WARN: impute and continue]
    F1 -->|OK| F4[Continue]
    F2 --> F2a[WHY: Model NEEDS this feature.<br/>Imputing critical features = garbage]
    
    %% Consistency
    G --> G1{FK relationships hold?<br/>Aggregates match?}
    G1 -->|INCONSISTENT| G2[BLOCK: data corruption detected]
    G1 -->|CONSISTENT| G3[Continue]
    G2 --> G2a[WHY: Inconsistent data =<br/>conflicting signals to model]

    style B2 fill:#d33,color:#fff
    style C2 fill:#d93,color:#fff
    style C3 fill:#d93,color:#fff
    style D2 fill:#d33,color:#fff
    style E2 fill:#da3,color:#000
    style F2 fill:#d33,color:#fff
    style G2 fill:#d33,color:#fff
```

### Quality Check Priority Matrix

| Check | Severity | Block Pipeline? | Automation |
|-------|----------|----------------|------------|
| Schema | Critical | Yes, always | Great Expectations / Pandera |
| Volume | High | Yes if zero rows | Custom threshold alerts |
| Freshness | High | Yes if > 2x SLA | Timestamp monitoring |
| Distribution | Medium | No, warn + log | PSI / KS test automated |
| Null rate | Depends | Critical cols only | Per-column thresholds |
| Consistency | Critical | Yes | Cross-table assertions |

---

## Diagram 4: Streaming vs Batch Features Decision

```mermaid
flowchart LR
    A[Feature Need] --> B{How fast does<br/>this change?}
    
    B -->|Days/Weeks| C[STATIC - Batch Daily]
    B -->|Hours| D[SLOW-MOVING - Micro-batch]
    B -->|Seconds| E[REAL-TIME - Streaming]
    
    C --> C1[Examples:<br/>User demographics<br/>Product catalog<br/>Historical aggregates]
    C1 --> C2[Compute: Daily Spark job]
    C2 --> C3[Storage: Offline store - Parquet/Hive]
    C3 --> C4[Latency: Hours OK]
    C4 --> C5[Cost: $]
    
    D --> D1[Examples:<br/>30-day purchase history<br/>Weekly engagement score<br/>Rolling conversion rate]
    D1 --> D2[Compute: Hourly micro-batch Spark]
    D2 --> D3[Storage: Sync to online store]
    D3 --> D4[Latency: Minutes OK]
    D4 --> D5[Cost: $$]
    
    E --> E1[Examples:<br/>Clicks in last 5 min<br/>Current session behavior<br/>Real-time fraud signals]
    E1 --> E2[Compute: Kafka → Flink]
    E2 --> E3[Storage: Redis / DynamoDB]
    E3 --> E4[Latency: Sub-second required]
    E4 --> E5[Cost: $$$$]
    
    %% Decision guidance
    F[DECISION RULE] --> F1[Only make features real-time<br/>if they MEASURABLY improve model]
    F1 --> F2[Run A/B test:<br/>batch features vs batch+realtime]
    F2 --> F3{Lift > cost of<br/>streaming infra?}
    F3 -->|Yes| E
    F3 -->|No| C

    style C5 fill:#2d5,color:#fff
    style D5 fill:#da3,color:#000
    style E5 fill:#d33,color:#fff
```

### Cost Reality Check

```
Real-time pipeline (Kafka + Flink + Redis):
  Infrastructure: ~$5,000-20,000/month
  Engineering: 2-3 engineers to maintain
  Debugging: Hard (distributed, async, exactly-once semantics)

Batch pipeline (Daily Spark):
  Infrastructure: ~$200-1,000/month
  Engineering: 0.5 engineer to maintain
  Debugging: Easy (rerun, inspect intermediate outputs)

RULE OF THUMB: Start batch. Add real-time only when you can prove
the latency improvement drives measurable business value.
```

---

## Diagram 5: Data Partitioning & Storage Strategy

```mermaid
flowchart TD
    A[How much data?] --> B{Size?}
    
    B -->|< 1GB| C[Plain Parquet Files]
    B -->|1-100GB| D[Partitioned Parquet]
    B -->|100GB-10TB| E[Delta Lake / Iceberg]
    B -->|> 10TB| F[Data Lakehouse<br/>Databricks/Snowflake]
    
    C --> C1[WHY: Simple, fast, columnar compression<br/>No infrastructure overhead<br/>Fits in memory for training]
    
    D --> D1[WHY: Only read partitions you need<br/>10-100x faster queries<br/>Partition by: date, category, region]
    
    E --> E1[WHY: ACID transactions<br/>Time travel - reproduce any point in time<br/>Schema evolution without breaking readers<br/>Concurrent read/write safely]
    
    F --> F1[WHY: Distributed compute + storage<br/>Managed infrastructure<br/>SQL + ML in same platform<br/>Cost optimization via auto-scaling]
    
    %% ML-specific partitioning
    G[ML Data Organization] --> H[Training Data]
    G --> I[Features]
    G --> J[Predictions]
    G --> K[Labels]
    
    H --> H1[Partition by: training_date<br/>WHY: Reproducibility -<br/>recreate exact training set]
    
    I --> I1[Partition by: entity_id + timestamp<br/>WHY: Point-in-time joins -<br/>get features AS OF specific time]
    
    J --> J1[Partition by: model_version + date<br/>WHY: Compare model versions,<br/>monitor drift per cohort]
    
    K --> K1[Partition by: labeling_date<br/>WHY: Track label quality over time,<br/>identify labeler disagreement periods]

    style C fill:#2d5,color:#fff
    style D fill:#25d,color:#fff
    style E fill:#d5a,color:#000
    style F fill:#d52,color:#fff
```

### Storage Format Comparison for ML

| Format | Compression | Schema Evolution | Time Travel | Best For |
|--------|-------------|-----------------|-------------|----------|
| CSV | None | No | No | Never use for ML |
| Parquet | Excellent | Limited | No | Small-medium datasets |
| Delta Lake | Excellent | Yes | Yes | Production ML pipelines |
| Iceberg | Excellent | Yes | Yes | Multi-engine (Spark+Trino) |
| ORC | Good | Limited | No | Hive-heavy ecosystems |

### Point-in-Time Correctness (Critical for ML)

```
WRONG: Join features using latest values
  → Training uses "future" information → Data leakage → Overly optimistic metrics

RIGHT: Join features AS OF the label timestamp
  → Feature values reflect what model would have seen at prediction time
  
Example:
  Label: "User churned on March 15"
  Features must be: values as of March 14 (day before)
  NOT: current values (includes post-churn behavior)
```

---

## Summary: Data Pipeline Decision Checklist

1. **ETL vs ELT vs Streaming** → Based on latency needs and schema stability
2. **Feature engineering** → Systematic pipeline with validation at each stage
3. **Data quality** → Automated checks that block bad data before it reaches models
4. **Batch vs real-time features** → Start batch, prove value before going real-time
5. **Storage strategy** → Size-appropriate, with ML-specific partitioning for reproducibility
