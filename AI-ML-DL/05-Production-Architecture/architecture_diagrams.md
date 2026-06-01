# ML Production Architecture Diagrams

Visual references for ML system architectures using Mermaid diagrams.

---

## 1. ML Training Pipeline

End-to-end flow from raw data to a validated model in the model registry.

```mermaid
flowchart LR
    subgraph Data
        A[Raw Data Sources] --> B[Data Ingestion]
        B --> C[Data Lake / S3]
        C --> D[Data Validation]
        D --> E[Feature Engineering]
    end

    subgraph Training
        E --> F[Training Dataset]
        F --> G[Model Training]
        G --> H[Hyperparameter Tuning]
        H --> I[Model Evaluation]
    end

    subgraph Registry
        I -->|Pass| J[Model Registry]
        I -->|Fail| G
        J --> K[Model Versioning]
        K --> L[Approval Gate]
    end

    style A fill:#e1f5fe
    style J fill:#c8e6c9
    style L fill:#fff9c4
```

**Key points:**
- Data validation (Great Expectations, Deequ) catches schema drift and data quality issues before they corrupt training
- Hyperparameter tuning (Optuna, Ray Tune) runs in parallel across GPU cluster
- Model registry (MLflow, Weights & Biases) stores artifacts, metrics, lineage
- Approval gate can be automated (metric thresholds) or manual (for high-risk models)

---

## 2. Model Serving Architecture (Inference)

Real-time and batch serving with graceful fallback.

```mermaid
flowchart TB
    subgraph Clients
        A[Web App] 
        B[Mobile App]
        C[Internal Services]
    end

    subgraph Gateway
        D[API Gateway / Load Balancer]
    end

    subgraph Serving
        E[Model Server A - GPU]
        F[Model Server B - GPU]
        G[Model Server C - CPU fallback]
    end

    subgraph Support
        H[Feature Store - Redis]
        I[Model Store - S3]
        J[Prediction Cache]
        K[Shadow Model - Canary]
    end

    A --> D
    B --> D
    C --> D
    D --> J
    J -->|Cache Miss| E
    J -->|Cache Miss| F
    D -->|Fallback| G
    E --> H
    F --> H
    I -->|Load model| E
    I -->|Load model| F
    D -.->|Mirror traffic| K
```

**Key points:**
- Prediction cache (Redis, TTL-based) reduces GPU compute for repeated/similar queries
- Shadow model receives mirrored traffic for evaluation without impacting users
- CPU fallback ensures availability if GPU servers are overloaded
- Model servers use Triton, TF Serving, or TorchServe with dynamic batching

---

## 3. Feature Store Architecture

Unified feature management for training and serving consistency.

```mermaid
flowchart LR
    subgraph Sources
        A[Event Stream - Kafka]
        B[Databases]
        C[APIs]
    end

    subgraph Processing
        D[Stream Processing - Flink]
        E[Batch Processing - Spark]
    end

    subgraph Feature Store
        F[Online Store - Redis/DynamoDB]
        G[Offline Store - Delta Lake/S3]
        H[Feature Registry & Catalog]
    end

    subgraph Consumers
        I[Training Pipelines]
        J[Serving - Real-time]
        K[Analytics / Exploration]
    end

    A --> D
    B --> E
    C --> E
    D --> F
    D --> G
    E --> G
    E --> F
    G --> I
    F --> J
    G --> K
    H -.->|Schema, lineage| F
    H -.->|Schema, lineage| G
```

**Key points:**
- **Online store:** Low-latency reads (<5ms p99) for serving; keyed by entity ID
- **Offline store:** Point-in-time correct joins for training; prevents label leakage
- **Feature registry:** Centralized catalog with ownership, schema, freshness SLA, documentation
- **Training-serving consistency:** Same transformation code generates both online and offline features (avoids skew)
- Tools: Feast, Tecton, Databricks Feature Store, Vertex AI Feature Store

---

## 4. A/B Testing Flow

From experiment creation to statistical decision.

```mermaid
flowchart TB
    subgraph Setup
        A[Define Hypothesis] --> B[Configure Experiment]
        B --> C[Set Traffic Split]
        C --> D[Define Metrics & Guardrails]
    end

    subgraph Execution
        E[Traffic Router]
        E -->|Control 95%| F[Model A - Current]
        E -->|Treatment 5%| G[Model B - Candidate]
        F --> H[Log Predictions + Outcomes]
        G --> H
    end

    subgraph Analysis
        H --> I[Metric Aggregation]
        I --> J{Statistical Significance?}
        J -->|Yes, positive| K[Roll out Model B]
        J -->|Yes, negative| L[Revert to Model A]
        J -->|No| M[Continue / Increase Traffic]
    end

    D --> E

    style K fill:#c8e6c9
    style L fill:#ffcdd2
```

**Key points:**
- Traffic split by user_id hash (consistent assignment across sessions)
- Guardrail metrics (latency, error rate, revenue) must not regress even if primary metric improves
- Minimum 1-2 weeks to capture weekly seasonality
- Use sequential testing (always-valid p-values) for early stopping
- Beware: novelty effects, interference between variants, Simpson's paradox in segments

---

## 5. Monitoring and Alerting Flow

Comprehensive observability for ML systems in production.

```mermaid
flowchart LR
    subgraph ML System
        A[Model Server]
        B[Feature Pipeline]
        C[Training Pipeline]
    end

    subgraph Metrics Collection
        D[Prediction Logs]
        E[Feature Values]
        F[System Metrics]
    end

    subgraph Detection
        G[Data Drift Detection]
        H[Model Performance Monitor]
        I[System Health Monitor]
    end

    subgraph Action
        J[Alert - PagerDuty/Slack]
        K[Auto-rollback]
        L[Trigger Retrain]
        M[Dashboard - Grafana]
    end

    A --> D
    A --> F
    B --> E
    C --> F
    D --> H
    E --> G
    F --> I
    G -->|Drift detected| J
    G -->|Severe| L
    H -->|Degradation| J
    H -->|Below threshold| K
    I -->|Unhealthy| J
    D --> M
    E --> M
    F --> M
```

**What to monitor:**

| Category | Metrics | Alert Threshold |
|----------|---------|-----------------|
| Data quality | Null rate, schema violations, volume | >5% nulls, schema change |
| Feature drift | PSI, KL divergence, Jensen-Shannon | PSI > 0.2 |
| Prediction drift | Output distribution shift, confidence calibration | KS test p<0.01 |
| Model performance | Accuracy, AUC (when labels available) | Drop >2% from baseline |
| System | Latency p99, error rate, throughput | p99 >200ms, errors >1% |
| Business | CTR, conversion, revenue per session | Drop >5% WoW |

---

## 6. CI/CD for ML (MLOps Pipeline)

Continuous integration, training, and deployment for ML.

```mermaid
flowchart TB
    subgraph Trigger
        A[Code Push] 
        B[Schedule - Daily/Weekly]
        C[Data Drift Alert]
    end

    subgraph CI - Validate
        D[Unit Tests - Feature Logic]
        E[Integration Tests - Pipeline]
        F[Data Validation]
        G[Model Quality Gate]
    end

    subgraph CT - Train
        H[Feature Computation]
        I[Model Training]
        J[Evaluation vs. Baseline]
    end

    subgraph CD - Deploy
        K{Better than Production?}
        L[Shadow Deployment]
        M[Canary - 1% Traffic]
        N[Gradual Rollout]
        O[Full Production]
    end

    A --> D
    B --> H
    C --> H
    D --> E --> F --> G
    G -->|Pass| H
    H --> I --> J
    J --> K
    K -->|Yes| L --> M --> N --> O
    K -->|No| P[Log & Archive]

    style O fill:#c8e6c9
    style P fill:#ffcdd2
```

**Key differences from traditional CI/CD:**
- **CT (Continuous Training):** Models retrain automatically on new data
- **Data validation is a first-class gate** — bad data is the #1 cause of ML failures
- **Model quality gate:** Compare against baseline on held-out set AND production metrics
- **Shadow deployment:** New model serves alongside production, predictions logged but not used
- **Canary:** Small traffic slice; automated rollback if metrics degrade
- **Immutable artifacts:** Model + features + config versioned together for reproducibility

---

## 7. Data Lake Architecture for ML

Layered data architecture supporting both analytics and ML workloads.

```mermaid
flowchart TB
    subgraph Ingestion
        A[Transactional DBs - CDC]
        B[Event Streams - Kafka]
        C[External APIs]
        D[File Uploads]
    end

    subgraph Storage Layers
        E[Bronze - Raw Layer]
        F[Silver - Cleaned & Conformed]
        G[Gold - Aggregated & Feature-Ready]
    end

    subgraph Compute
        H[Spark / Databricks]
        I[Flink - Streaming]
    end

    subgraph Consumers
        J[ML Training Pipelines]
        K[Feature Store]
        L[BI / Analytics]
        M[Ad-hoc Exploration]
    end

    A --> E
    B --> E
    C --> E
    D --> E
    E -->|Validate & clean| F
    F -->|Aggregate & join| G
    H --> F
    H --> G
    I --> F
    G --> J
    G --> K
    G --> L
    F --> M

    style E fill:#fff3e0
    style F fill:#e3f2fd
    style G fill:#e8f5e9
```

**Layer descriptions:**

| Layer | Purpose | Format | Retention |
|-------|---------|--------|-----------|
| Bronze | Raw, immutable ingestion | Parquet/JSON, partitioned by date | Forever |
| Silver | Cleaned, deduplicated, schema-enforced | Delta Lake / Iceberg | 2+ years |
| Gold | Business-level aggregations, ML-ready features | Delta Lake, optimized | As needed |

**Key principles:**
- **Immutability:** Bronze layer never modified — enables reprocessing and auditing
- **Schema evolution:** Delta Lake / Iceberg handle schema changes gracefully
- **Time travel:** Query data as-of any point in time (critical for reproducible training)
- **Partitioning:** By date + entity for efficient ML data loading (avoid full scans)
- **Governance:** Data catalog (Unity Catalog, Glue) with lineage, access control, PII tagging
