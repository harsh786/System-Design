# 062 - ML Experiment Tracking and Reproducibility

## Problem Statement

ML teams running thousands of experiments lose track of which data, code, hyperparameters, and environment produced which results. Without systematic tracking, reproducing a successful experiment becomes impossible, comparing approaches is ad-hoc, and promoting models to production is risky. At scale (100+ data scientists, 10K+ experiments/month), this requires a platform that versions everything and enables distributed hyperparameter search.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Experiment Execution"
        Notebook[Jupyter Notebooks]
        Scripts[Training Scripts]
        HPOJobs[HPO Jobs<br/>Distributed Search]
    end

    subgraph "Tracking Layer"
        MLflow[MLflow Tracking Server<br/>Metrics + Params]
        WandB[Weights & Biases<br/>Visualizations]
        TrackingDB[Tracking DB<br/>PostgreSQL/MySQL]
    end

    subgraph "Artifact Storage"
        S3Artifacts[S3 Artifact Store<br/>Models + Data]
        ModelArtifacts[Model Checkpoints<br/>Versioned]
        DataArtifacts[Dataset Snapshots<br/>DVC tracked]
    end

    subgraph "Versioning"
        GitCode[Git<br/>Code Versioning]
        DVCData[DVC<br/>Data Versioning]
        DockerEnv[Docker<br/>Environment Versioning]
        CondaEnv[Conda/Poetry<br/>Dependency Lock]
    end

    subgraph "Hyperparameter Optimization"
        Optuna[Optuna<br/>Bayesian + Pruning]
        RayTune[Ray Tune<br/>Distributed HPO]
        SageMakerHPO[SageMaker HPO<br/>Managed Bayesian]
    end

    subgraph "Comparison & Analysis"
        Dashboard[Experiment Dashboard<br/>Compare runs]
        ParallelCoord[Parallel Coordinates<br/>Param importance]
        StatTests[Statistical Tests<br/>Significance]
    end

    subgraph "Model Registry"
        Registry[Model Registry<br/>Stage management]
        Staging[Staging<br/>Validation]
        Production[Production<br/>Serving]
        Archived[Archived<br/>Historical]
    end

    Notebook --> MLflow
    Scripts --> MLflow
    HPOJobs --> MLflow
    Notebook --> WandB

    MLflow --> TrackingDB
    MLflow --> S3Artifacts
    S3Artifacts --> ModelArtifacts
    S3Artifacts --> DataArtifacts

    GitCode --> MLflow
    DVCData --> MLflow
    DockerEnv --> MLflow
    CondaEnv --> MLflow

    Optuna --> HPOJobs
    RayTune --> HPOJobs
    SageMakerHPO --> HPOJobs

    MLflow --> Dashboard
    Dashboard --> ParallelCoord
    Dashboard --> StatTests

    MLflow --> Registry
    Registry --> Staging
    Staging --> Production
    Production --> Archived
```

## Component Breakdown

### 1. MLflow Tracking Integration

```python
import mlflow
from mlflow.tracking import MlflowClient

# Configure tracking server
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("recommendation-model-v3")

# Full experiment tracking
with mlflow.start_run(run_name="xgboost-tuned-v3.2") as run:
    # Log parameters
    mlflow.log_params({
        "model_type": "xgboost",
        "learning_rate": 0.01,
        "max_depth": 8,
        "n_estimators": 1000,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
    })
    
    # Log data version
    mlflow.log_params({
        "data_version": "v2.3",
        "dvc_commit": "abc123",
        "train_samples": 50_000_000,
        "val_samples": 5_000_000,
        "feature_count": 256,
    })
    
    # Log environment
    mlflow.log_params({
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode(),
        "docker_image": "ml-training:v2.3.1",
        "instance_type": "ml.p4d.24xlarge",
        "gpu_count": 8,
    })
    
    # Train with metric logging
    model = xgb.XGBClassifier(**params)
    eval_set = [(X_val, y_val)]
    model.fit(
        X_train, y_train,
        eval_set=eval_set,
        callbacks=[
            XGBMLflowCallback(log_model=False),  # Log metrics per iteration
        ]
    )
    
    # Log final metrics
    y_pred = model.predict_proba(X_val)[:, 1]
    mlflow.log_metrics({
        "val_auc": roc_auc_score(y_val, y_pred),
        "val_precision_at_10": precision_at_k(y_val, y_pred, k=10),
        "val_recall_at_50": recall_at_k(y_val, y_pred, k=50),
        "val_ndcg": ndcg_score(y_val, y_pred),
        "val_log_loss": log_loss(y_val, y_pred),
        "training_time_seconds": training_time,
        "model_size_mb": model_size / 1e6,
    })
    
    # Log artifacts
    mlflow.log_artifact("feature_importance.png")
    mlflow.log_artifact("confusion_matrix.png")
    mlflow.log_artifact("calibration_curve.png")
    
    # Log model with signature
    from mlflow.models.signature import infer_signature
    signature = infer_signature(X_val[:5], model.predict(X_val[:5]))
    mlflow.xgboost.log_model(model, "model", signature=signature)
    
    # Log dataset info
    mlflow.log_input(
        mlflow.data.from_pandas(X_train.head(100), source="s3://data/train/"),
        context="training"
    )
```

### 2. Distributed Hyperparameter Optimization

```python
import optuna
from optuna.integration import MLflowCallback
from optuna.pruners import HyperbandPruner
from optuna.samplers import TPESampler
import ray
from ray import tune
from ray.tune.search.optuna import OptunaSearch

# Optuna with MLflow tracking
def objective(trial):
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 1e-5, 1e-1, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }
    
    model = xgb.XGBClassifier(**params, use_label_encoder=False, eval_metric="auc")
    
    # Pruning callback - stop unpromising trials early
    pruning_callback = optuna.integration.XGBoostPruningCallback(trial, "validation-auc")
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[pruning_callback],
        verbose=False,
    )
    
    y_pred = model.predict_proba(X_val)[:, 1]
    return roc_auc_score(y_val, y_pred)

# Distributed study with RDB storage
study = optuna.create_study(
    study_name="recommendation-hpo-v3",
    direction="maximize",
    storage="postgresql://optuna:password@db:5432/optuna",
    sampler=TPESampler(n_startup_trials=20, multivariate=True),
    pruner=HyperbandPruner(min_resource=50, max_resource=2000, reduction_factor=3),
    load_if_exists=True,
)

# Run distributed across 10 workers
study.optimize(
    objective,
    n_trials=500,
    n_jobs=10,  # Parallel trials
    callbacks=[MLflowCallback(tracking_uri="http://mlflow:5000", metric_name="val_auc")],
    show_progress_bar=True,
)

# Ray Tune for GPU-distributed HPO
ray.init(address="auto")  # Connect to Ray cluster

search_space = {
    "lr": tune.loguniform(1e-5, 1e-1),
    "batch_size": tune.choice([32, 64, 128, 256]),
    "hidden_dim": tune.choice([128, 256, 512, 1024]),
    "num_layers": tune.randint(2, 8),
    "dropout": tune.uniform(0.0, 0.5),
}

tuner = tune.Tuner(
    tune.with_resources(train_function, {"gpu": 1, "cpu": 4}),
    param_space=search_space,
    tune_config=tune.TuneConfig(
        metric="val_auc",
        mode="max",
        num_samples=200,
        scheduler=tune.schedulers.ASHAScheduler(
            max_t=100, grace_period=10, reduction_factor=3
        ),
        search_alg=OptunaSearch(),
    ),
    run_config=ray.train.RunConfig(
        storage_path="s3://ray-results/",
        name="recommendation-hpo",
    ),
)

results = tuner.fit()
best_result = results.get_best_result("val_auc", "max")
```

### 3. Model Registry and Promotion

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Register best model
model_uri = f"runs:/{best_run_id}/model"
mv = client.create_model_version(
    name="recommendation-model",
    source=model_uri,
    run_id=best_run_id,
    description=f"AUC: {best_auc:.4f}, trained on data v2.3",
    tags={
        "data_version": "v2.3",
        "training_time": "4h",
        "gpu_type": "A100",
    }
)

# Transition through stages with validation
# Stage 1: None → Staging (automated)
client.transition_model_version_stage(
    name="recommendation-model",
    version=mv.version,
    stage="Staging",
)

# Run validation in staging
validation_passed = run_staging_validation(model_uri)

if validation_passed:
    # Stage 2: Staging → Production (manual approval or automated)
    client.transition_model_version_stage(
        name="recommendation-model",
        version=mv.version,
        stage="Production",
        archive_existing_versions=True,  # Auto-archive previous production
    )

# Query production model
prod_model = client.get_latest_versions("recommendation-model", stages=["Production"])[0]
```

### 4. Reproducibility Configuration

```yaml
# reproducibility.yaml - Full experiment specification
experiment:
  name: "recommendation-model-v3"
  description: "XGBoost recommendation model with new user features"
  
code:
  git_repo: "https://github.com/company/ml-models.git"
  git_commit: "abc123def456"
  entry_point: "src/train.py"
  
data:
  dvc_remote: "s3://dvc-storage/"
  dvc_commit: "xyz789"
  train_path: "data/processed/train.parquet"
  val_path: "data/processed/val.parquet"
  test_path: "data/processed/test.parquet"
  
environment:
  docker_image: "123456789.dkr.ecr.us-east-1.amazonaws.com/ml-training:v2.3.1"
  conda_env: "environment.yml"
  python_version: "3.10.12"
  cuda_version: "12.1"
  
infrastructure:
  instance_type: "ml.p4d.24xlarge"
  instance_count: 4
  spot: true
  
hyperparameters:
  learning_rate: 0.01
  max_depth: 8
  n_estimators: 1500
  
random_seeds:
  numpy: 42
  torch: 42
  python: 42
```

### 5. MLflow Server Deployment

```yaml
# docker-compose.yml for MLflow server
version: '3.8'
services:
  mlflow-server:
    image: ghcr.io/mlflow/mlflow:2.9.0
    command: >
      mlflow server
      --backend-store-uri postgresql://mlflow:password@postgres:5432/mlflow
      --default-artifact-root s3://mlflow-artifacts/
      --host 0.0.0.0
      --port 5000
      --workers 8
      --gunicorn-opts "--timeout 300"
    environment:
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '4'
          memory: 8G

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: mlflow
      POSTGRES_USER: mlflow
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 32G
```

## Scaling Strategies

| Component | Strategy | Scale |
|-----------|----------|-------|
| MLflow Server | Multi-replica behind LB | 10K concurrent experiments |
| PostgreSQL Backend | RDS Multi-AZ, read replicas | 100M metric entries |
| Artifact Store (S3) | Unlimited | PB of model artifacts |
| HPO | Ray cluster (100+ GPUs) | 1000 parallel trials |
| Optuna Storage | PostgreSQL with partitioning | 1M+ trials |

## Failure Handling

| Failure | Impact | Recovery |
|---------|--------|----------|
| MLflow server down | Can't log metrics | Local buffering → retry; async logging |
| S3 artifact upload fails | Model not persisted | Retry with exponential backoff |
| HPO worker crash | Trial lost | Ray auto-restart; checkpoint resume |
| DB corruption | Experiment history lost | Daily RDS snapshots; point-in-time recovery |
| Docker image missing | Can't reproduce | ECR lifecycle policies; immutable tags |

## Cost Optimization

| Technique | Savings | Notes |
|-----------|---------|-------|
| Pruning bad HPO trials early | 60% compute | ASHA/Hyperband stops unpromising |
| Spot instances for HPO | 70% | Trials are restartable |
| S3 lifecycle (archive old artifacts) | 50% storage | Glacier for experiments >6 months |
| Shared MLflow server | 80% infra | One server for all teams |
| Incremental training | 40% compute | Resume from checkpoints |

## Real-World Companies

| Company | Platform | Scale |
|---------|----------|-------|
| Netflix | Metaflow + internal tracking | 1000s of experiments/week |
| Uber | Michelangelo | 10K+ models in production |
| Spotify | MLflow + custom extensions | 100+ ML teams |
| Airbnb | Bighead platform | Full experiment lifecycle |
| LinkedIn | ProML | Thousands of experiments/day |
| Meta | FBLearner Flow | Millions of experiments/year |

## Key Design Decisions

1. **MLflow vs W&B vs Neptune**: MLflow for self-hosted/OSS; W&B for best visualization/collaboration; Neptune for lightweight teams
2. **Artifact storage**: Always S3/GCS — never store large artifacts in tracking DB
3. **HPO strategy**: Bayesian (TPE) for <100 trials; ASHA for large search spaces needing early stopping
4. **Reproducibility level**: At minimum: code commit + data version + parameters. Ideal: + Docker image + hardware spec + random seeds
5. **Registry stages**: Minimum 3 (Staging → Production → Archived). Add "Canary" for gradual rollouts
