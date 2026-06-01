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
