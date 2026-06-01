# MLOps: Machine Learning Operations

## What is MLOps?

MLOps is the discipline of deploying, monitoring, and managing ML models in production reliably and efficiently. It combines ML, DevOps, and Data Engineering practices.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MLOps LIFECYCLE                              │
│                                                                     │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│    │  Data   │───▶│  Model  │───▶│  Model  │───▶│  Model  │      │
│    │ Mgmt    │    │   Dev   │    │  Deploy │    │  Monitor │      │
│    └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘      │
│         │              │              │              │             │
│         ▼              ▼              ▼              ▼             │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│    │  DVC    │    │Experiment│    │  CI/CD  │    │  Drift  │      │
│    │ Feature │    │ Tracking │    │  Model  │    │Detection│      │
│    │  Store  │    │ Registry │    │ Registry│    │ Alerting│      │
│    └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
│                                                                     │
│    ◀────────────── FEEDBACK LOOP ──────────────────────────▶       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MLOps Maturity Levels

### Level 0: No MLOps (Manual Process)

```
┌─────────────────────────────────────────────────────┐
│  LEVEL 0: MANUAL ML                                 │
│                                                     │
│  Data Scientist's Laptop                            │
│  ┌───────────────────────────────────────┐         │
│  │  Jupyter Notebook                      │         │
│  │  ┌──────┐  ┌──────┐  ┌──────────┐   │         │
│  │  │ Data │─▶│Train │─▶│ Evaluate │   │         │
│  │  │ Load │  │Model │  │  & Save  │   │         │
│  │  └──────┘  └──────┘  └──────────┘   │         │
│  └───────────────────────────────────────┘         │
│                      │                              │
│                      ▼ (manual handoff)             │
│  ┌───────────────────────────────────────┐         │
│  │  ML Engineer deploys manually          │         │
│  │  - Copy model file to server           │         │
│  │  - Update config                       │         │
│  │  - Restart service                     │         │
│  └───────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

**Characteristics:**
- Manual experiment tracking (spreadsheets)
- No versioning of data or models
- Manual deployment via scripts/SSH
- No monitoring beyond basic uptime
- Retraining triggered by humans noticing degradation

**Problems:**
- Weeks between model development and deployment
- No reproducibility
- "It works on my machine" syndrome
- No audit trail

---

### Level 1: DevOps but No MLOps

```
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 1: BASIC AUTOMATION                                      │
│                                                                  │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐       │
│  │   Git    │────▶│   CI/CD      │────▶│  Deployment  │       │
│  │  (code)  │     │  (Jenkins)   │     │  (K8s/Docker)│       │
│  └──────────┘     └──────────────┘     └──────────────┘       │
│                                                                  │
│  Training: Still manual/scripted                                │
│  Data: No versioning                                            │
│  Model: Stored as artifact in CI/CD                             │
│  Monitoring: Basic infra metrics only                           │
│                                                                  │
│  Improvement over Level 0:                                      │
│  ✓ Automated deployment of serving code                        │
│  ✓ Basic testing of serving endpoints                          │
│  ✗ Training still manual                                       │
│  ✗ No data/model versioning                                    │
│  ✗ No ML-specific monitoring                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### Level 2: Automated Training

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LEVEL 2: ML PIPELINE AUTOMATION                                        │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │              Orchestrated Training Pipeline                   │       │
│  │                                                               │       │
│  │  ┌──────┐  ┌────────┐  ┌───────┐  ┌────────┐  ┌────────┐  │       │
│  │  │ Data │─▶│Feature │─▶│ Train │─▶│Evaluate│─▶│Register│  │       │
│  │  │Ingest│  │  Eng   │  │       │  │        │  │ Model  │  │       │
│  │  └──────┘  └────────┘  └───────┘  └────────┘  └────────┘  │       │
│  └─────────────────────────────────────────────────────────────┘       │
│         │           │           │           │           │               │
│         ▼           ▼           ▼           ▼           ▼               │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  Metadata Store (experiment tracking, lineage)            │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                              │                          │
│                                              ▼                          │
│  ┌───────────────────────────────────────────────────────┐             │
│  │  Model Registry → CI/CD → Staging → Production        │             │
│  └───────────────────────────────────────────────────────┘             │
│                                              │                          │
│                                              ▼                          │
│  ┌───────────────────────────────────────────────────────┐             │
│  │  Monitoring: Model performance + Data quality          │             │
│  └───────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

**Characteristics:**
- Automated training pipelines (Airflow/Kubeflow)
- Experiment tracking (MLflow/W&B)
- Model registry with versioning
- Basic model validation gates
- Scheduled retraining

---

### Level 3: Full MLOps

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LEVEL 3: FULL MLOps                                                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Feature Store                                                    │      │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐    │      │
│  │  │  Offline    │  │   Online    │  │  Feature Registry    │    │      │
│  │  │  (Batch)    │  │(Low-latency)│  │  (Discovery/Docs)    │    │      │
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘    │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│         │                    │                                               │
│         ▼                    ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │  Training    │    │   Serving    │                                      │
│  │  Pipeline    │    │   Pipeline   │                                      │
│  └──────┬───────┘    └──────┬───────┘                                      │
│         │                    │                                               │
│         ▼                    ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Continuous Monitoring                                            │      │
│  │  ┌────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────────┐    │      │
│  │  │  Data  │ │  Model   │ │  Feature  │ │    Business     │    │      │
│  │  │  Drift │ │  Perf    │ │  Drift    │ │    KPIs         │    │      │
│  │  └────┬───┘ └────┬─────┘ └─────┬─────┘ └───────┬─────────┘    │      │
│  │       └───────────┴─────────────┴───────────────┘               │      │
│  │                          │                                        │      │
│  │                          ▼                                        │      │
│  │              ┌─────────────────────┐                             │      │
│  │              │  Auto-Retrain or    │                             │      │
│  │              │  Alert & Rollback   │                             │      │
│  │              └─────────────────────┘                             │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                              │
│  Additional:                                                                │
│  ✓ A/B testing infrastructure                                              │
│  ✓ Shadow deployments                                                      │
│  ✓ Automated rollback on degradation                                       │
│  ✓ Data validation gates                                                   │
│  ✓ Model fairness monitoring                                               │
│  ✓ Full lineage tracking                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Level 4: Autonomous ML (Self-Optimizing)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LEVEL 4: AUTONOMOUS ML PLATFORM                                            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Self-Service ML Platform                                         │      │
│  │                                                                    │      │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐    │      │
│  │  │  AutoML    │  │  Auto-Feature│  │  Neural Architecture │    │      │
│  │  │  Pipeline  │  │  Engineering │  │  Search (NAS)        │    │      │
│  │  └────────────┘  └──────────────┘  └──────────────────────┘    │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Intelligent Orchestration                                        │      │
│  │  - Auto-detects drift → triggers retraining                      │      │
│  │  - Auto-scales based on traffic patterns                         │      │
│  │  - Auto-selects best model via bandits                           │      │
│  │  - Auto-optimizes cost (spot instances, model compression)       │      │
│  │  - Self-healing (auto-rollback, failover)                        │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Governance & Compliance Layer                                    │      │
│  │  - Automated fairness checks before promotion                    │      │
│  │  - Explainability reports auto-generated                         │      │
│  │  - Audit trail for all model decisions                           │      │
│  │  - Automated regulatory reporting                                │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## CI/CD for ML

ML CI/CD is fundamentally more complex than traditional CI/CD because you version **three things**: code, data, and models.

### CI/CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ML CI/CD PIPELINE                                     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CONTINUOUS INTEGRATION                                      │       │
│  │                                                               │       │
│  │  Code Push ──▶ ┌──────────────────────────────────────┐     │       │
│  │                 │ 1. Unit Tests (code)                  │     │       │
│  │                 │ 2. Data Validation Tests              │     │       │
│  │                 │ 3. Feature Engineering Tests          │     │       │
│  │                 │ 4. Model Training (small dataset)     │     │       │
│  │                 │ 5. Model Quality Gates                │     │       │
│  │                 │    - Accuracy > threshold             │     │       │
│  │                 │    - Latency < SLA                    │     │       │
│  │                 │    - Fairness metrics pass            │     │       │
│  │                 │ 6. Integration Tests                  │     │       │
│  │                 └──────────────────────────────────────┘     │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                              │ Pass                                      │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CONTINUOUS DELIVERY                                         │       │
│  │                                                               │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │       │
│  │  │  Build   │─▶│  Deploy  │─▶│  Shadow  │─▶│  Canary  │  │       │
│  │  │ Container│  │ Staging  │  │  Mode    │  │  (5%)    │  │       │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │       │
│  │                                                    │        │       │
│  │                                          Metrics OK │        │       │
│  │                                                    ▼        │       │
│  │                                             ┌──────────┐   │       │
│  │                                             │Full Rollout│  │       │
│  │                                             │  (100%)   │   │       │
│  │                                             └──────────┘   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CONTINUOUS TRAINING (triggered by drift/schedule)           │       │
│  │                                                               │       │
│  │  Trigger ──▶ Fetch Data ──▶ Validate ──▶ Train ──▶ Evaluate │       │
│  │                                                    │          │       │
│  │                                          Pass?     │          │       │
│  │                                          Yes ──▶ Register     │       │
│  │                                          No  ──▶ Alert        │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### CI/CD Sequence Diagram

```
Developer        Git         CI Server      Model Registry    Staging       Production
    │              │              │              │              │              │
    │──push──────▶│              │              │              │              │
    │              │──webhook───▶│              │              │              │
    │              │              │──run tests──│              │              │
    │              │              │  unit tests  │              │              │
    │              │              │  data tests  │              │              │
    │              │              │  train(mini) │              │              │
    │              │              │              │              │              │
    │              │              │──evaluate───▶│              │              │
    │              │              │  quality gates│              │              │
    │              │              │              │              │              │
    │              │              │──register───▶│              │              │
    │              │              │              │──deploy─────▶│              │
    │              │              │              │              │──smoke test─│
    │              │              │              │              │              │
    │              │              │              │              │──shadow─────▶│
    │              │              │              │              │  compare     │
    │              │              │              │              │  metrics     │
    │              │              │              │              │              │
    │              │              │              │              │──canary─────▶│
    │              │              │              │              │  5% traffic  │
    │              │              │              │              │              │
    │              │              │              │              │──full roll──▶│
    │◀─────────────────────────notify─────────────────────────────────────────│
```

### What to Test in ML CI/CD

| Test Category | What to Test | Tools |
|--------------|-------------|-------|
| Data Tests | Schema, distributions, missing values, freshness | Great Expectations, Deequ |
| Feature Tests | Feature computation correctness, no leakage | pytest, custom validators |
| Model Tests | Accuracy, latency, fairness, robustness | pytest, Aequitas |
| Integration Tests | End-to-end prediction pipeline | pytest, locust |
| Infrastructure Tests | Container builds, scaling, failover | Terraform tests, chaos eng |

---

## Experiment Tracking

### Comparison of Tools

| Feature | MLflow | Weights & Biases | Neptune | ClearML |
|---------|--------|-------------------|---------|---------|
| Open Source | Yes | No (free tier) | No | Yes |
| Self-hosted | Yes | Yes (Enterprise) | No | Yes |
| UI Quality | Good | Excellent | Good | Good |
| Collaboration | Basic | Excellent | Good | Good |
| Artifact Storage | Basic | Good | Good | Good |
| GPU Monitoring | No | Yes | Yes | Yes |
| Pricing | Free | $$$ | $$ | Free/$ |
| Scale | Medium | Large | Medium | Medium |
| Integration | Broad | Broad | Medium | Broad |

### MLflow Architecture

```
┌─────────────────────────────────────────────────────────┐
│  MLflow Components                                       │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Tracking   │  │   Projects   │  │    Models    │ │
│  │              │  │              │  │   Registry   │ │
│  │ - Parameters │  │ - Packaging  │  │              │ │
│  │ - Metrics    │  │ - Reproducibility│ - Versioning│ │
│  │ - Artifacts  │  │ - Dependencies│  │ - Staging   │ │
│  │ - Tags       │  │              │  │ - Approvals  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         │                                     │         │
│         ▼                                     ▼         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Backend Store        │  Artifact Store           │  │
│  │  (PostgreSQL/MySQL)   │  (S3/GCS/Azure Blob)     │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Example: MLflow Tracking Code

```python
import mlflow

mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("fraud-detection-v2")

with mlflow.start_run(run_name="xgboost-tuned"):
    # Log parameters
    mlflow.log_params({
        "n_estimators": 500,
        "max_depth": 8,
        "learning_rate": 0.01,
        "dataset_version": "v2.3.1",
        "feature_store_version": "2024-01-15"
    })
    
    # Train model
    model = train_model(X_train, y_train, params)
    
    # Log metrics
    mlflow.log_metrics({
        "auc_roc": 0.943,
        "precision_at_1pct_fpr": 0.67,
        "latency_p99_ms": 12.3,
        "model_size_mb": 45.2
    })
    
    # Log model
    mlflow.sklearn.log_model(
        model, "model",
        registered_model_name="fraud-detection",
        signature=infer_signature(X_train, predictions)
    )
    
    # Log artifacts
    mlflow.log_artifact("feature_importance.png")
    mlflow.log_artifact("confusion_matrix.png")
```

---

## Model Registry

### Model Lifecycle

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
│  None   │───▶│Staging  │───▶│Production│───▶│ Archived │───▶│ Deleted  │
│(Logged) │    │(Testing)│    │(Serving) │    │(Retained)│    │(Purged)  │
└─────────┘    └─────────┘    └─────────┘    └──────────┘    └──────────┘
     │              │              │              │
     │         Validation     Monitoring     Compliance
     │         A/B Test       Drift Check    Audit Period
     │         Shadow Mode    Auto-rollback  (90 days)
```

### Model Registry Requirements

1. **Versioning**: Semantic versioning of models (major.minor.patch)
2. **Metadata**: Training data version, hyperparameters, metrics, lineage
3. **Approval Workflow**: Multi-stage approval (DS → ML Eng → SRE)
4. **Rollback**: One-click rollback to previous version
5. **Access Control**: RBAC for model promotion
6. **Audit Trail**: Who promoted what, when, why

---

## Feature Stores

### Why Feature Stores?

```
WITHOUT Feature Store:                 WITH Feature Store:
                                       
Team A: compute features               ┌──────────────┐
Team B: compute SAME features          │Feature Store │
Team C: compute SAME features          │              │
                                       │ Compute Once │
Problems:                              │ Serve Many   │
- Duplicated computation               │              │
- Training/serving skew                │ ┌──────────┐ │
- Inconsistent definitions             │ │ Offline  │ │  ← Training
- No reuse across teams                │ │  Store   │ │
                                       │ └──────────┘ │
                                       │ ┌──────────┐ │
                                       │ │  Online  │ │  ← Serving
                                       │ │  Store   │ │
                                       │ └──────────┘ │
                                       └──────────────┘
```

### Feature Store Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FEATURE STORE ARCHITECTURE                            │
│                                                                          │
│  DATA SOURCES                    FEATURE COMPUTATION                     │
│  ┌──────────┐                   ┌─────────────────┐                    │
│  │Databases │──┐                │  Batch Features  │                    │
│  └──────────┘  │                │  (Spark/Dask)    │                    │
│  ┌──────────┐  │  ┌─────────┐  │  - Daily agg     │  ┌─────────────┐  │
│  │  Logs    │──┼─▶│  Data   │─▶│  - Historical    │─▶│  Offline    │  │
│  └──────────┘  │  │  Layer  │  │                   │  │  Store      │  │
│  ┌──────────┐  │  └─────────┘  └─────────────────┘  │  (Parquet/  │  │
│  │  Events  │──┘       │                              │   Delta)    │  │
│  └──────────┘          │        ┌─────────────────┐  └─────────────┘  │
│                        └───────▶│Stream Features  │                    │
│                                 │  (Flink/Spark)  │  ┌─────────────┐  │
│                                 │  - Real-time    │─▶│  Online     │  │
│                                 │  - Windowed agg │  │  Store      │  │
│                                 └─────────────────┘  │  (Redis/    │  │
│                                                       │   DynamoDB) │  │
│  CONSUMERS                                           └─────────────┘  │
│  ┌──────────────┐                                         │            │
│  │  Training    │◀── get_historical_features() ───────────┘            │
│  │  Pipelines   │                                         │            │
│  └──────────────┘                                         │            │
│  ┌──────────────┐                                         │            │
│  │  Serving     │◀── get_online_features() ───────────────┘            │
│  │  (Real-time) │         (p99 < 10ms)                                 │
│  └──────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Feature Store Comparison

| Feature | Feast | Tecton | Hopsworks | Databricks FS |
|---------|-------|--------|-----------|---------------|
| Open Source | Yes | No | Partially | No |
| Real-time | Yes | Yes | Yes | Limited |
| Stream Processing | Basic | Advanced | Yes | Yes |
| Online Store | Redis, DynamoDB | Managed | MySQL, Redis | DynamoDB |
| Offline Store | BigQuery, Redshift | Managed | Hive, S3 | Delta Lake |
| Feature Monitoring | Basic | Advanced | Yes | Yes |
| Cost | Free + infra | $$$$ | $$ | $$ |

### Feast Example

```python
from feast import FeatureStore, Entity, FeatureView, Field
from feast.types import Float32, Int64

# Define entity
customer = Entity(name="customer_id", join_keys=["customer_id"])

# Define feature view
customer_features = FeatureView(
    name="customer_features",
    entities=[customer],
    schema=[
        Field(name="total_transactions_30d", dtype=Int64),
        Field(name="avg_transaction_amount_30d", dtype=Float32),
        Field(name="days_since_last_transaction", dtype=Int64),
    ],
    source=BigQuerySource(
        table="project.dataset.customer_features",
        timestamp_field="event_timestamp",
    ),
    online=True,
    ttl=timedelta(days=1),
)

# Retrieve for training (point-in-time correct)
training_df = store.get_historical_features(
    entity_df=entity_df,  # with customer_id and event_timestamp
    features=["customer_features:total_transactions_30d",
              "customer_features:avg_transaction_amount_30d"],
)

# Retrieve for serving (low-latency)
online_features = store.get_online_features(
    features=["customer_features:total_transactions_30d"],
    entity_rows=[{"customer_id": "C123"}],
).to_dict()
```

---

## Data Versioning

### DVC (Data Version Control)

```
┌─────────────────────────────────────────────────────────────┐
│  DVC Architecture                                            │
│                                                              │
│  ┌──────────┐         ┌──────────────┐                     │
│  │   Git    │         │  Remote      │                     │
│  │          │         │  Storage     │                     │
│  │ .dvc     │────────▶│  (S3/GCS)   │                     │
│  │ files    │         │              │                     │
│  │ (hashes) │         │  Actual data │                     │
│  └──────────┘         └──────────────┘                     │
│                                                              │
│  Workflow:                                                   │
│  1. dvc add data/training.csv  (creates .dvc file)         │
│  2. git add data/training.csv.dvc                          │
│  3. git commit -m "Add training data v1"                   │
│  4. dvc push  (uploads to remote)                          │
│                                                              │
│  Reproduce:                                                 │
│  git checkout v1.0                                          │
│  dvc checkout  (restores data for that version)            │
└─────────────────────────────────────────────────────────────┘
```

### LakeFS - Git for Data Lakes

```
┌─────────────────────────────────────────────────────────────┐
│  LakeFS Architecture                                         │
│                                                              │
│  ┌───────────────────────────────────┐                     │
│  │          LakeFS Server            │                     │
│  │  ┌───────┐  ┌───────┐  ┌──────┐ │                     │
│  │  │Branch │  │Branch │  │ main │ │                     │
│  │  │ dev   │  │ exp1  │  │      │ │                     │
│  │  └───┬───┘  └───┬───┘  └──┬───┘ │                     │
│  │      │          │         │      │                     │
│  │      └──────────┴─────────┘      │                     │
│  │           (merge/diff)            │                     │
│  └───────────────┬───────────────────┘                     │
│                  │                                           │
│                  ▼                                           │
│  ┌───────────────────────────────────┐                     │
│  │   Object Storage (S3/GCS/Azure)   │                     │
│  │   Zero-copy branching             │                     │
│  └───────────────────────────────────┘                     │
│                                                              │
│  Features:                                                  │
│  - Git-like branching for data                             │
│  - Atomic commits                                          │
│  - Pre-commit hooks (data validation)                      │
│  - Zero-copy branching (metadata only)                     │
│  - Compatible with Spark, Presto, etc.                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Orchestration

### Comparison

| Feature | Airflow | Kubeflow | Prefect | Dagster | Metaflow |
|---------|---------|----------|---------|---------|----------|
| ML-native | No | Yes | Partial | Yes | Yes |
| K8s Required | No | Yes | No | No | Optional |
| UI | Good | Basic | Good | Excellent | Basic |
| Scheduling | Excellent | Basic | Good | Good | Good |
| Scalability | High | High | High | Medium | High |
| Learning Curve | High | High | Low | Medium | Low |
| GPU Support | Via K8s | Native | Via K8s | Via K8s | Native |
| Data Lineage | Plugin | Basic | Basic | Native | Native |

### Kubeflow Pipelines Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Kubeflow Pipelines on Kubernetes                                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Pipeline Definition (Python SDK / YAML)                  │      │
│  │                                                            │      │
│  │  @component                                               │      │
│  │  def train_model(data: Input[Dataset]) -> Output[Model]:  │      │
│  │      ...                                                   │      │
│  │                                                            │      │
│  │  @pipeline                                                │      │
│  │  def ml_pipeline():                                       │      │
│  │      data = load_data()                                   │      │
│  │      features = feature_eng(data)                         │      │
│  │      model = train_model(features)                        │      │
│  │      evaluate(model)                                      │      │
│  └──────────────────────────────────────────────────────────┘      │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Kubernetes Cluster                                       │      │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐       │      │
│  │  │ Pod:   │─▶│ Pod:   │─▶│ Pod:   │─▶│ Pod:   │       │      │
│  │  │ Load   │  │Feature │  │ Train  │  │Evaluate│       │      │
│  │  │ Data   │  │  Eng   │  │(GPU)   │  │        │       │      │
│  │  └────────┘  └────────┘  └────────┘  └────────┘       │      │
│  │                                                          │      │
│  │  Each step: isolated container, tracked artifacts        │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ML Metadata Management

### What to Track

```
┌─────────────────────────────────────────────────────────────────┐
│  ML METADATA GRAPH                                               │
│                                                                   │
│  Dataset v2.1 ──────┐                                           │
│    - 1.2M rows       │                                           │
│    - schema: {...}   │                                           │
│    - quality: 99.2%  │      Pipeline Run #4521                  │
│                      ├─────▶  - Duration: 2h 15m                │
│  Features v3.0 ─────┘        - Compute: 4x V100                │
│    - 245 features    │        - Cost: $12.40                    │
│    - store: feast    │              │                            │
│                      │              ▼                            │
│  Code: git@abc123 ──┘       Model v2.1.0                        │
│                              - AUC: 0.943                       │
│  Config:                     - Latency: 8ms                     │
│    - lr: 0.001               - Size: 120MB                      │
│    - epochs: 50              - Promoted: 2024-01-20             │
│    - batch: 256              - Approved by: @jane               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Reproducibility Guarantees

### The Reproducibility Stack

| Layer | What to Pin | Tool |
|-------|-------------|------|
| Code | Git commit hash | Git |
| Dependencies | Package versions | pip freeze, conda env |
| Data | Dataset version/hash | DVC, LakeFS |
| Config | Hyperparameters | Config files in Git |
| Environment | Container image | Docker with digest |
| Hardware | GPU type, count | K8s node selectors |
| Randomness | Seeds | Set all random seeds |

### Reproducibility Checklist

```python
# reproducibility.py
import random
import numpy as np
import torch

def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)
```

---

## Team Collaboration Patterns

### Pattern 1: Centralized ML Platform

```
┌───────────────────────────────────────────────────────┐
│  ML Platform Team (owns infrastructure)               │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Feature Store │ Model Registry │ Serving Infra │ │
│  │  Orchestration │ Monitoring    │ Compute       │ │
│  └─────────────────────────────────────────────────┘ │
│         ▲              ▲              ▲               │
│         │              │              │               │
│  ┌──────┴──┐    ┌─────┴───┐    ┌────┴─────┐        │
│  │ Team A  │    │ Team B  │    │ Team C   │        │
│  │ (Fraud) │    │ (Recs)  │    │ (Search) │        │
│  └─────────┘    └─────────┘    └──────────┘        │
└───────────────────────────────────────────────────────┘
```

### Pattern 2: Embedded ML Engineers

```
Product Team A: PM + Engineers + Embedded ML Engineer
Product Team B: PM + Engineers + Embedded ML Engineer

Shared: ML Platform team provides tooling
```

---

## Real-World Case Studies

### Case Study: Uber Michelangelo
- **Scale**: 10,000+ models in production
- **Challenge**: Diverse ML use cases (ETA, pricing, fraud, matching)
- **Solution**: Unified ML platform with feature store, model management, deployment
- **Key Learning**: Feature store eliminated 80% of feature engineering duplication

### Case Study: Netflix ML Platform
- **Scale**: 100s of ML models for personalization
- **Challenge**: A/B testing at scale, rapid experimentation
- **Solution**: Metaflow + internal orchestration, heavy A/B testing infrastructure
- **Key Learning**: Invest heavily in experiment velocity; faster experiments > better models

### Production Incident: Training-Serving Skew at Stripe
- **Symptom**: Fraud model performance degraded 15% after deployment
- **Root Cause**: Feature computed differently in batch (training) vs real-time (serving) — timezone handling
- **Fix**: Feature store with guaranteed consistency between offline/online
- **Learning**: Always test feature parity between training and serving

---

## Interview Questions

1. **Design an MLOps platform for a team of 20 data scientists deploying 50 models**
   - Focus: Multi-tenancy, resource isolation, approval workflows

2. **How would you handle a model that silently degrades over 3 months?**
   - Focus: Monitoring strategy, drift detection, automated retraining triggers

3. **Design CI/CD for a model that takes 8 hours to train**
   - Focus: Incremental testing, cached artifacts, parallel validation

4. **How do you ensure reproducibility when training data changes daily?**
   - Focus: Data versioning, point-in-time snapshots, immutable datasets

5. **Compare feature store approaches for a company with 10ms latency SLA**
   - Focus: Online store selection, caching, pre-computation vs real-time

---

## Key Metrics for MLOps Success

| Metric | Target (Mature Org) |
|--------|-------------------|
| Time from experiment to production | < 1 week |
| Model deployment frequency | Daily |
| Failed deployment rate | < 5% |
| Mean time to rollback | < 5 minutes |
| Training pipeline reliability | > 99% |
| Feature computation freshness | < 1 hour (batch), < 1s (stream) |
| Experiment tracking coverage | 100% of runs |
| Model monitoring coverage | 100% of prod models |

---

## Production War Stories

Real-world incidents from production ML systems. These stories illustrate why MLOps practices exist — every best practice was born from a painful failure.

---

### War Story 1: The Silent Model Degradation

**Company:** Large e-commerce platform (~50M daily active users)

**What Happened:**
Over 3 months, the recommendation model's accuracy degraded by 30%. No alerts fired. No one noticed until a quarterly business review revealed a revenue dip in the "recommended for you" section. A data scientist manually investigated and found the model was essentially returning near-random recommendations.

**Root Cause Analysis:**
A data pipeline migration introduced a bug where a key user behavior feature (`last_category_viewed`) was silently being filled with `NULL` values for 40% of users. The model didn't crash — it gracefully degraded, falling back to popularity-based recommendations without any explicit error.

The pipeline had tests, but they only checked schema and row counts, not value distributions.

**How It Was Detected:**
- Revenue from recommendation-driven purchases dropped 15% over 3 months
- A product manager flagged it during quarterly review
- Manual investigation by a data scientist confirmed the issue

**How It Was Fixed:**
1. Immediate: Fixed the pipeline bug, backfilled the feature
2. Short-term: Added Great Expectations data quality checks on all features
3. Long-term: 
   - Feature distribution monitoring (KL divergence, PSI)
   - Automated alerts when any feature's null rate exceeds historical baseline by 2x
   - Model performance dashboard with daily accuracy tracking
   - Business metric correlation monitoring

**Key Takeaway:**
Models fail silently. You MUST monitor input features, not just output metrics. A model returning predictions with high confidence doesn't mean it's correct.

**Prevention Checklist:**
- [ ] Data quality checks on all input features (null rates, distribution shifts)
- [ ] Feature-level monitoring with automated alerts
- [ ] Business metric correlation with model metrics
- [ ] Regular model accuracy audits (weekly minimum)
- [ ] Alerting on prediction distribution changes (e.g., diversity of recommendations)

---

### War Story 2: The Training-Serving Skew

**Company:** Fintech company (credit scoring)

**What Happened:**
A new credit scoring model achieved AUC 0.95 in offline evaluation — significantly better than the existing model (AUC 0.82). After deploying to production, the model's actual AUC was measured at 0.65, worse than the model it replaced.

**Root Cause Analysis:**
Feature computation differed between training and serving:
- **Training:** Batch SQL pipeline computed features nightly. Dates were parsed using SQL's `DATE_PARSE` (which defaults to UTC).
- **Serving:** Real-time Python code computed features on-the-fly. Dates used `datetime.strptime()` which used local timezone (PST).
- **Null handling:** SQL `COALESCE(value, 0)` vs Python `value or -1`
- **String processing:** SQL `UPPER(TRIM(field))` vs Python `field.strip().upper()` (different whitespace handling)

These subtle differences meant 4 out of 15 features had different values at serving time compared to training time.

**How It Was Detected:**
- Online/offline metric mismatch flagged by an engineer during the first week
- Feature value comparison between training data and live serving logs confirmed the skew

**How It Was Fixed:**
1. Implemented Feast as a feature store
2. Single feature computation codebase used for both training and serving
3. Added automated skew detection: compute features both ways, alert if divergence > 1%
4. Training pipeline now validates features against serving infrastructure before model promotion

**Key Takeaway:**
Always use a feature store or shared feature computation layer. Never let training and serving compute features independently.

**Prevention Checklist:**
- [ ] Feature store (Feast, Tecton, etc.) for unified feature computation
- [ ] Automated training-serving skew detection
- [ ] Integration tests that compare training features vs serving features
- [ ] Feature computation code review as part of model review
- [ ] Log serving-time feature values for post-hoc comparison

---

### War Story 3: The Feedback Loop Disaster

**Company:** Content moderation platform

**What Happened:**
A toxicity detection model was retrained weekly on new data. Within 2 weeks of deployment, it started flagging nearly 80% of all content as toxic (up from 5%), causing massive user complaints and content removal.

**Root Cause Analysis:**
A positive feedback loop emerged:
1. Model flags content as toxic → content is removed
2. Removed content disappears from the "safe" training pool
3. Retraining data becomes skewed (fewer negative/safe examples)
4. New model has a lower threshold for "toxic" → flags more content
5. Cycle repeats, each iteration more aggressive

The model was literally training on a biased sample created by its own predictions.

**How It Was Detected:**
- User complaints spiked 400% in week 2
- Daily flagging rate metric showed exponential growth
- Manual review showed clearly safe content being flagged

**How It Was Fixed:**
1. Immediate: Rolled back to the pre-deployment model
2. Short-term:
   - Added counterfactual logging (log predictions but don't always act on them)
   - Human review sampling: 5% of "safe" predictions are manually verified
   - Temporal holdout evaluation: always test on data from BEFORE model deployment
3. Long-term:
   - Randomized holdback: 1% of content is never acted upon (for unbiased evaluation)
   - Prediction rate monitoring with alerts on significant shifts
   - Retraining data auditing: check label distribution before retraining

**Key Takeaway:**
Be extremely careful with models that influence their own training data. This includes recommendation systems, content moderation, fraud detection, and search ranking.

**Prevention Checklist:**
- [ ] Identify feedback loops BEFORE deployment (draw the data flow diagram)
- [ ] Counterfactual logging (record what would have happened without the model)
- [ ] Holdback groups for unbiased evaluation
- [ ] Monitor prediction distribution over time (flag rate, positive rate)
- [ ] Human-in-the-loop sampling for ground truth
- [ ] Temporal holdout validation (test on pre-deployment data)

---

### War Story 4: The Cascading Failure

**Company:** Ride-sharing platform

**What Happened:**
During a Sunday night traffic spike, the ML pricing service (surge pricing) became overwhelmed. Within 3 minutes, 6 dependent services (ETA estimation, driver matching, ride pricing, route optimization, demand forecasting, fare estimation) all went down. The entire platform was unavailable for 23 minutes.

**Root Cause Analysis:**
- The ML service had no circuit breaker — when it slowed down, callers kept retrying
- No timeout configuration — callers waited indefinitely for responses
- No fallback logic — services couldn't function without ML predictions
- Thread pool exhaustion in calling services → cascading failure
- The ML service was a single point of failure for the entire platform

**How It Was Detected:**
- PagerDuty alerts fired for all 6 services simultaneously
- Customer reports flooded in
- Monitoring dashboards showed cascade pattern

**How It Was Fixed:**
1. Immediate: Restarted all services, scaled ML service
2. Short-term:
   - Circuit breakers (Hystrix pattern) on all ML service calls
   - Timeouts: 100ms for ML predictions, fall back after that
   - Graceful degradation: rule-based pricing as fallback (1.5x base fare)
3. Long-term:
   - Bulkheading: separate thread pools per downstream service
   - Cached predictions: serve last-known-good predictions for up to 5 minutes
   - Load shedding: ML service drops low-priority requests under pressure
   - Chaos engineering: monthly failure injection tests

**Key Takeaway:**
ML services must have fallbacks. Always design for failure. An ML service going down should degrade the experience, not crash the platform.

**Prevention Checklist:**
- [ ] Circuit breakers on all ML service calls
- [ ] Timeouts (aggressive — 100ms for real-time predictions)
- [ ] Fallback logic (rule-based, cached predictions, or default values)
- [ ] Bulkheading (isolate failure domains)
- [ ] Load shedding under pressure
- [ ] Regular chaos engineering / failure injection tests
- [ ] Dependency mapping (know your blast radius)

---

### War Story 5: The Expensive GPU Incident

**Company:** AI startup (20 employees)

**What Happened:**
A machine learning engineer launched a hyperparameter sweep on a Friday afternoon — 200 GPU instances (V100s at $3.06/hr each) across multiple configurations. They planned to check results Monday. They got sick and didn't log in until the following Monday. By then, the sweep had finished on Saturday but the instances kept running. Total bill: $47,000.

**Root Cause Analysis:**
- No auto-shutdown policy for GPU instances
- No budget alerts configured
- No instance TTL (time-to-live) enforcement
- No team visibility into running resources
- The sweep framework didn't terminate instances after completion

**How It Was Detected:**
- Monday morning: engineer logged in and saw instances still running
- AWS bill alert came 3 days later (configured at $50K threshold, too high)

**How It Was Fixed:**
1. Immediate: Terminated all instances, negotiated partial credit with cloud provider
2. Short-term:
   - Budget alerts at $500/day, $2000/week, $5000/month
   - Auto-shutdown: all GPU instances auto-terminate after 4 hours unless explicitly extended
   - Spot instances for all training workloads (70% cost savings)
3. Long-term:
   - Scheduled scaling: training only during business hours
   - Resource tagging: every instance tagged with owner, purpose, TTL
   - Weekly cost review meeting
   - Terraform/IaC for all infrastructure (no manual instance launches)
   - Slack bot that posts daily cloud spend

**Key Takeaway:**
Always set budget alerts and instance TTLs for ML workloads. GPU instances are expensive and easy to forget.

**Prevention Checklist:**
- [ ] Budget alerts at multiple thresholds (daily, weekly, monthly)
- [ ] Auto-shutdown/TTL policies for all compute instances
- [ ] Spot/preemptible instances for training workloads
- [ ] Resource tagging (owner, purpose, expiry)
- [ ] No manual instance creation (use IaC only)
- [ ] Daily cost visibility (dashboard or Slack alerts)
- [ ] Instance audit: weekly review of running resources
