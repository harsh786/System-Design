# Problem 6: ML Model Training Pipeline (Netflix-Scale)

## The Problem

Netflix trains 1000+ ML models daily across multiple domains:
- **Recommendation models**: Personalized content ranking for 230M+ subscribers
- **Thumbnail selection**: Which artwork to show each user (trained per title)
- **Quality of Experience (QoE)**: Adaptive bitrate, buffering prediction
- **Content valuation**: Predicting show success before greenlight

Each model has wildly different resource requirements:
- Lightweight logistic regression: 2 CPU, 4GB RAM, 5 minutes
- Deep learning recommendation: 8 GPU, 128GB RAM, 12 hours
- Feature engineering: 64 CPU, 256GB RAM (memory-bound joins)

**Core challenges:**
1. GPU nodes cost $32/hour — cannot waste them waiting for data prep
2. Models have complex DAG dependencies (features → train → validate → deploy)
3. A/B testing means training 5-20 variants of the same model simultaneously
4. Failures in 12-hour training jobs are catastrophic without checkpointing
5. Teams share GPU infrastructure — need fair scheduling and isolation

## Scale Numbers

| Metric | Value |
|--------|-------|
| Models trained daily | 1,000+ |
| GPU node cost | $32/hour |
| Training duration range | 5 min – 12 hours |
| Daily feature engineering data | 50TB+ |
| Available GPU nodes | 100+ |
| Model variants per A/B experiment | 5–20 |
| Teams sharing infrastructure | 15+ |
| Daily GPU spend budget | ~$50,000 |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Airflow Scheduler                             │
│              (CeleryKubernetesExecutor - Hybrid)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
┌──────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│  Celery Workers  │ │  K8s Executor   │ │ KubernetesPodOperator│
│  (Fast Tasks)    │ │  (GPU Tasks)    │ │ (Custom Containers)  │
│                  │ │                 │ │                      │
│ • Feature eng    │ │ • Model train   │ │ • TensorFlow jobs    │
│ • Data validation│ │ • Hyperparameter│ │ • PyTorch distributed│
│ • Metric logging │ │ • Batch predict │ │ • Custom frameworks  │
└────────┬─────────┘ └────────┬────────┘ └──────────┬───────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                             │
│                                                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ CPU Pool    │  │ GPU Pool     │  │ High-Memory Pool        │ │
│  │ (spot)      │  │ (on-demand)  │  │ (on-demand)             │ │
│  │ n1-std-16   │  │ a2-highgpu-8 │  │ n1-highmem-96           │ │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              Shared Storage & Model Registry                       │
│  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  GCS   │  │ MLflow   │  │ Feature  │  │ Model Registry    │  │
│  │Buckets │  │ Tracking │  │  Store   │  │ (Deployment)      │  │
│  └────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. KubernetesExecutor Deep Dive

The KubernetesExecutor spawns a **new Pod for every task instance**. This gives complete isolation — one task's OOM cannot affect another.

```python
# airflow.cfg
[core]
executor = KubernetesExecutor

[kubernetes_executor]
namespace = airflow-ml
worker_container_repository = gcr.io/ml-platform/airflow-worker
worker_container_tag = 2.8.1-ml
delete_worker_pods = True
delete_worker_pods_on_failure = False  # Keep failed pods for debugging

# Pod template file for default configuration
pod_template_file = /opt/airflow/pod_templates/default.yaml
```

**Pod Template (default worker):**

```yaml
# /opt/airflow/pod_templates/default.yaml
apiVersion: v1
kind: Pod
metadata:
  labels:
    component: airflow-worker
    tier: ml-pipeline
spec:
  serviceAccountName: airflow-worker-sa
  initContainers:
    - name: wait-for-dependencies
      image: busybox:1.36
      command: ['sh', '-c', 'echo "Init complete"']
  containers:
    - name: base
      image: gcr.io/ml-platform/airflow-worker:2.8.1-ml
      env:
        - name: AIRFLOW__CORE__EXECUTOR
          value: "LocalExecutor"
      resources:
        requests:
          cpu: "1"
          memory: "2Gi"
        limits:
          cpu: "2"
          memory: "4Gi"
      volumeMounts:
        - name: model-artifacts
          mountPath: /mnt/artifacts
  volumes:
    - name: model-artifacts
      persistentVolumeClaim:
        claimName: model-artifacts-pvc
  tolerations:
    - key: "workload-type"
      operator: "Equal"
      value: "ml-training"
      effect: "NoSchedule"
```

### 2. executor_config and Pod Customization

The `executor_config` parameter lets you override Pod specs **per task**:

```python
from kubernetes.client import models as k8s

# GPU pod override — used for training tasks
GPU_POD_OVERRIDE = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        containers=[
            k8s.V1Container(
                name="base",
                resources=k8s.V1ResourceRequirements(
                    requests={
                        "cpu": "8",
                        "memory": "64Gi",
                        "nvidia.com/gpu": "4",
                    },
                    limits={
                        "cpu": "16",
                        "memory": "128Gi",
                        "nvidia.com/gpu": "4",
                    },
                ),
                volume_mounts=[
                    k8s.V1VolumeMount(
                        name="shm",
                        mount_path="/dev/shm",  # Shared memory for PyTorch DataLoader
                    )
                ],
            )
        ],
        volumes=[
            k8s.V1Volume(
                name="shm",
                empty_dir=k8s.V1EmptyDirVolumeSource(medium="Memory", size_limit="32Gi"),
            )
        ],
        node_selector={"cloud.google.com/gke-accelerator": "nvidia-tesla-a100"},
        tolerations=[
            k8s.V1Toleration(
                key="nvidia.com/gpu",
                operator="Exists",
                effect="NoSchedule",
            )
        ],
        priority_class_name="ml-training-high",
    )
)

# High-memory pod for feature engineering
HIGHMEM_POD_OVERRIDE = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        containers=[
            k8s.V1Container(
                name="base",
                resources=k8s.V1ResourceRequirements(
                    requests={"cpu": "32", "memory": "200Gi"},
                    limits={"cpu": "64", "memory": "256Gi"},
                ),
            )
        ],
        node_selector={"node-type": "highmem"},
    )
)
```

### 3. CeleryKubernetesExecutor (Hybrid)

Use Celery for fast, lightweight tasks and Kubernetes for resource-heavy GPU tasks:

```python
# airflow.cfg
[core]
executor = CeleryKubernetesExecutor

[celery_kubernetes_executor]
kubernetes_queue = kubernetes  # Tasks on this queue go to K8s executor
```

**Routing logic:** Any task with `queue="kubernetes"` runs on K8s. Everything else runs on Celery workers.

```python
# Fast task → Celery (sub-second scheduling overhead)
validate_data = PythonOperator(
    task_id="validate_data",
    python_callable=validate,
    queue="default",  # Celery
)

# GPU task → Kubernetes (30-60s pod startup, but isolated resources)
train_model = PythonOperator(
    task_id="train_model",
    python_callable=train,
    queue="kubernetes",  # K8s executor
    executor_config={"pod_override": GPU_POD_OVERRIDE},
)
```

### 4. Resource Management

**Pod Priority Classes** — ensure ML training gets resources over batch ETL:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: ml-training-critical
value: 1000000
globalDefault: false
description: "Critical model training (production models)"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: ml-training-experiment
value: 100000
description: "Experimental model training (can be preempted)"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: etl-batch
value: 10000
description: "Batch ETL jobs (lowest priority)"
```

**Spot instances for experimentation:**

```python
SPOT_GPU_OVERRIDE = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        containers=[k8s.V1Container(name="base", resources=GPU_RESOURCES)],
        node_selector={
            "cloud.google.com/gke-accelerator": "nvidia-tesla-a100",
            "cloud.google.com/gke-spot": "true",
        },
        tolerations=[
            k8s.V1Toleration(key="cloud.google.com/gke-spot", operator="Exists"),
            k8s.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule"),
        ],
        priority_class_name="ml-training-experiment",
    )
)
```

### 5. KubernetesPodOperator

For tasks requiring custom Docker images with specific ML frameworks:

```python
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

train_pytorch_model = KubernetesPodOperator(
    task_id="train_pytorch_distributed",
    name="pytorch-train-recommender",
    namespace="ml-training",
    image="gcr.io/ml-platform/pytorch-trainer:2.1.0-cuda12",
    cmds=["python"],
    arguments=[
        "/app/train.py",
        "--model=recommender_v3",
        "--epochs=50",
        "--batch-size=4096",
        "--checkpoint-dir=/mnt/checkpoints",
    ],
    env_vars={
        "MLFLOW_TRACKING_URI": "http://mlflow.internal:5000",
        "WANDB_PROJECT": "recommender-v3",
        "MODEL_VERSION": "{{ ds_nodash }}",
    },
    container_resources=k8s.V1ResourceRequirements(
        requests={"cpu": "8", "memory": "64Gi", "nvidia.com/gpu": "4"},
        limits={"cpu": "16", "memory": "128Gi", "nvidia.com/gpu": "4"},
    ),
    volumes=[
        k8s.V1Volume(name="checkpoints", persistent_volume_claim=
            k8s.V1PersistentVolumeClaimVolumeSource(claim_name="training-checkpoints")),
        k8s.V1Volume(name="shm", empty_dir=
            k8s.V1EmptyDirVolumeSource(medium="Memory", size_limit="32Gi")),
    ],
    volume_mounts=[
        k8s.V1VolumeMount(name="checkpoints", mount_path="/mnt/checkpoints"),
        k8s.V1VolumeMount(name="shm", mount_path="/dev/shm"),
    ],
    node_selector={"cloud.google.com/gke-accelerator": "nvidia-tesla-a100"},
    tolerations=[k8s.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule")],
    service_account_name="ml-trainer-sa",
    is_delete_operator_pod=False,  # Keep pod for debugging on failure
    get_logs=True,
    log_events_on_failure=True,
    startup_timeout_seconds=600,  # GPU nodes can take time to schedule
    # XCom sidecar for passing metrics back to Airflow
    do_xcom_push=True,
)
```

## Production Implementation

```python
"""
ML Model Training Pipeline — Netflix-Scale
Uses CeleryKubernetesExecutor: fast tasks on Celery, GPU tasks on Kubernetes.
"""
from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import BranchPythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.utils.trigger_rule import TriggerRule
from kubernetes.client import models as k8s

# ─── Resource Definitions ───────────────────────────────────────────────────

GPU_4x_A100 = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        containers=[k8s.V1Container(
            name="base",
            resources=k8s.V1ResourceRequirements(
                requests={"cpu": "8", "memory": "64Gi", "nvidia.com/gpu": "4"},
                limits={"cpu": "16", "memory": "128Gi", "nvidia.com/gpu": "4"},
            ),
            volume_mounts=[
                k8s.V1VolumeMount(name="shm", mount_path="/dev/shm"),
                k8s.V1VolumeMount(name="artifacts", mount_path="/mnt/artifacts"),
            ],
        )],
        volumes=[
            k8s.V1Volume(name="shm", empty_dir=k8s.V1EmptyDirVolumeSource(
                medium="Memory", size_limit="32Gi")),
            k8s.V1Volume(name="artifacts", persistent_volume_claim=
                k8s.V1PersistentVolumeClaimVolumeSource(claim_name="ml-artifacts")),
        ],
        node_selector={"cloud.google.com/gke-accelerator": "nvidia-tesla-a100"},
        tolerations=[k8s.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule")],
        priority_class_name="ml-training-high",
    )
)

HIGHMEM_256 = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        containers=[k8s.V1Container(
            name="base",
            resources=k8s.V1ResourceRequirements(
                requests={"cpu": "32", "memory": "200Gi"},
                limits={"cpu": "64", "memory": "256Gi"},
            ),
        )],
        node_selector={"node-type": "highmem"},
        priority_class_name="ml-training-high",
    )
)

# ─── DAG Definition ─────────────────────────────────────────────────────────

default_args = {
    "owner": "ml-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(hours=14),
    "on_failure_callback": notify_oncall,
}

with DAG(
    dag_id="ml_training_pipeline_recommender",
    default_args=default_args,
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ml", "recommender", "production"],
    doc_md="""
    ## Recommender Model Training Pipeline
    Trains the primary recommendation model daily.
    Feature eng (Celery) → Training (K8s GPU) → Validation → Conditional Deploy
    """,
) as dag:

    # ─── Phase 1: Feature Engineering (Celery — fast, CPU-bound) ────────────

    @task(queue="default")  # Celery worker
    def validate_source_data(**context) -> dict:
        """Quick validation that upstream data landed. Runs on Celery (fast startup)."""
        from data_quality import check_table_freshness, check_row_counts

        checks = {
            "user_interactions": check_table_freshness("user_interactions", max_hours=6),
            "content_metadata": check_table_freshness("content_metadata", max_hours=24),
            "row_count_ok": check_row_counts("user_interactions", min_rows=500_000_000),
        }
        if not all(checks.values()):
            raise ValueError(f"Data quality checks failed: {checks}")
        return {"validation_ts": datetime.utcnow().isoformat(), "checks": checks}

    @task(
        queue="default",
        executor_config={"pod_override": HIGHMEM_256},
    )
    def engineer_features(**context) -> str:
        """
        Heavy feature engineering — needs 256GB RAM for large joins.
        Runs on K8s via executor_config override even though queue is default.
        With CeleryKubernetesExecutor, executor_config with pod_override
        forces K8s execution regardless of queue.
        """
        from feature_store import FeatureEngineer

        engineer = FeatureEngineer(
            date=context["ds"],
            features=[
                "user_watch_history_90d",
                "content_embeddings_v3",
                "user_content_interactions",
                "temporal_features",
            ],
        )
        output_path = engineer.build_training_dataset(
            output_path=f"gs://ml-features/recommender/{context['ds_nodash']}/",
            partitions=256,
        )
        return output_path

    # ─── Phase 2: Model Training (Kubernetes — GPU-bound) ───────────────────

    @task(
        queue="kubernetes",
        executor_config={"pod_override": GPU_4x_A100},
        retries=1,  # GPU training is expensive; limit retries
        retry_delay=timedelta(minutes=15),
    )
    def train_model(feature_path: str, variant: str, **context) -> dict:
        """Train model variant on GPU nodes. Includes checkpointing for recovery."""
        import mlflow
        from model_trainer import RecommenderTrainer

        run_id = f"{context['dag_run'].run_id}_{variant}"

        with mlflow.start_run(run_name=run_id):
            trainer = RecommenderTrainer(
                feature_path=feature_path,
                model_variant=variant,
                checkpoint_dir=f"/mnt/artifacts/checkpoints/{run_id}",
                config={
                    "epochs": 50,
                    "batch_size": 4096,
                    "learning_rate": 0.001,
                    "early_stopping_patience": 5,
                },
            )
            # Resume from checkpoint if this is a retry
            metrics = trainer.train(resume_from_checkpoint=True)

            mlflow.log_metrics(metrics)
            model_uri = mlflow.pytorch.log_model(trainer.model, "model")

        return {
            "model_uri": model_uri.model_uri,
            "metrics": metrics,
            "variant": variant,
            "gpu_hours": trainer.elapsed_gpu_hours,
            "cost_usd": trainer.elapsed_gpu_hours * 32,
        }

    # ─── Phase 3: Validation & Comparison ───────────────────────────────────

    @task(queue="default")
    def validate_and_compare(training_results: list[dict], **context) -> dict:
        """Compare all variants, select champion. Lightweight — runs on Celery."""
        from model_registry import get_production_model_metrics

        production_metrics = get_production_model_metrics("recommender_v3")

        best_variant = max(training_results, key=lambda x: x["metrics"]["ndcg@10"])
        improvement = (
            best_variant["metrics"]["ndcg@10"] - production_metrics["ndcg@10"]
        ) / production_metrics["ndcg@10"]

        total_cost = sum(r["cost_usd"] for r in training_results)

        return {
            "best_variant": best_variant["variant"],
            "best_model_uri": best_variant["model_uri"],
            "improvement_pct": improvement * 100,
            "should_deploy": improvement > 0.001,  # >0.1% improvement threshold
            "total_training_cost_usd": total_cost,
            "all_results": training_results,
        }

    # ─── Phase 4: Conditional Deployment ────────────────────────────────────

    def decide_deployment(ti, **context) -> str:
        comparison = ti.xcom_pull(task_ids="validate_and_compare")
        if comparison["should_deploy"]:
            return "deploy_model"
        return "skip_deployment"

    branch = BranchPythonOperator(
        task_id="deployment_decision",
        python_callable=decide_deployment,
    )

    @task(queue="default")
    def deploy_model(ti, **context):
        """Register model and trigger canary deployment."""
        from model_registry import ModelRegistry

        comparison = ti.xcom_pull(task_ids="validate_and_compare")
        registry = ModelRegistry()
        registry.promote_to_canary(
            model_uri=comparison["best_model_uri"],
            model_name="recommender_v3",
            version=context["ds_nodash"],
            metadata={
                "improvement": comparison["improvement_pct"],
                "cost": comparison["total_training_cost_usd"],
            },
        )

    @task(queue="default", trigger_rule=TriggerRule.NONE_FAILED)
    def skip_deployment(ti, **context):
        comparison = ti.xcom_pull(task_ids="validate_and_compare")
        print(f"Skipping deployment. Improvement: {comparison['improvement_pct']:.3f}%")

    @task(queue="default", trigger_rule=TriggerRule.ALL_DONE)
    def log_cost_metrics(ti, **context):
        """Always log costs regardless of deployment decision."""
        comparison = ti.xcom_pull(task_ids="validate_and_compare")
        from monitoring import emit_metric

        emit_metric("ml.training.cost_usd", comparison["total_training_cost_usd"],
                    tags={"model": "recommender_v3", "date": context["ds"]})
        for result in comparison["all_results"]:
            emit_metric("ml.training.gpu_hours", result["gpu_hours"],
                        tags={"variant": result["variant"]})

    # ─── DAG Wiring ─────────────────────────────────────────────────────────

    validated = validate_source_data()
    features = engineer_features()
    validated >> features

    # Train multiple variants in parallel
    variants = ["baseline", "attention_v2", "transformer_small", "two_tower"]
    training_results = train_model.partial(feature_path=features).expand(variant=variants)

    comparison = validate_and_compare(training_results)
    comparison >> branch >> [deploy_model(), skip_deployment()]
    comparison >> log_cost_metrics()
```

## Production Handling

### GPU Node Unavailable

```python
# Configure generous startup timeout — GPU nodes may need to scale up
KubernetesPodOperator(
    task_id="train",
    startup_timeout_seconds=900,  # 15 min for node autoscaler
    # ...
)

# In executor_config, set pod priority to trigger preemption of lower-priority work
GPU_POD_OVERRIDE = k8s.V1Pod(
    spec=k8s.V1PodSpec(
        priority_class_name="ml-training-critical",  # Will preempt 'experiment' pods
        # ...
    )
)
```

### OOM Kill Recovery

```python
@task(
    queue="kubernetes",
    executor_config={"pod_override": GPU_4x_A100},
    retries=2,
    on_retry_callback=escalate_resources_on_retry,
)
def train_with_oom_handling(feature_path: str, **context):
    """Reduce batch size on retry if OOM detected."""
    attempt = context["ti"].try_number
    batch_size = 4096 // (2 ** (attempt - 1))  # Halve batch size each retry

    trainer = RecommenderTrainer(
        feature_path=feature_path,
        config={"batch_size": batch_size},
        checkpoint_dir="/mnt/artifacts/checkpoints/",
    )
    return trainer.train(resume_from_checkpoint=(attempt > 1))


def escalate_resources_on_retry(context):
    """Log OOM and alert — resource limits may need updating."""
    from monitoring import alert
    alert(
        severity="warning",
        message=f"Training task OOM on attempt {context['ti'].try_number}. "
                f"Retrying with reduced batch size.",
        channel="#ml-oncall",
    )
```

### Spot Instance Preemption Recovery

```python
@task(
    queue="kubernetes",
    executor_config={"pod_override": SPOT_GPU_OVERRIDE},
    retries=3,
    retry_delay=timedelta(minutes=10),
)
def train_on_spot(feature_path: str, **context):
    """
    Training on spot instances with checkpoint-based recovery.
    Spot instances save ~70% but can be preempted at any time.
    """
    trainer = RecommenderTrainer(
        feature_path=feature_path,
        checkpoint_dir="/mnt/artifacts/checkpoints/",
        config={
            "checkpoint_every_n_steps": 500,  # Frequent checkpoints on spot
            "epochs": 50,
        },
    )
    # Always try to resume — handles preemption transparently
    return trainer.train(resume_from_checkpoint=True)
```

### Cost Optimization: Progressive Resource Scaling

```python
@task(queue="default")  # Celery — quick feasibility check
def quick_feasibility_check(feature_path: str, **context) -> dict:
    """Train 1 epoch on CPU to validate data pipeline before burning GPU hours."""
    trainer = RecommenderTrainer(
        feature_path=feature_path,
        config={"epochs": 1, "batch_size": 256, "device": "cpu", "subset": 0.01},
    )
    result = trainer.train()
    if result["loss"] > 10.0:
        raise ValueError(f"Loss too high ({result['loss']}). Data issue likely — aborting GPU training.")
    return {"feasible": True, "initial_loss": result["loss"]}


# Pipeline: cheap check → expensive training
feasibility = quick_feasibility_check(features)
feasibility >> training_results  # Only burn GPU if feasibility passes
```

### Training Timeout with Early Stopping

```python
train_with_timeout = KubernetesPodOperator(
    task_id="train_with_timeout",
    image="gcr.io/ml-platform/pytorch-trainer:2.1.0",
    arguments=[
        "/app/train.py",
        "--max-wall-time=21600",   # 6 hour hard limit in training code
        "--early-stopping-patience=5",
        "--checkpoint-dir=/mnt/checkpoints",
    ],
    # Airflow-level timeout (slightly longer than training timeout)
    execution_timeout=timedelta(hours=7),
    # K8s-level: active deadline on the pod
    active_deadline_seconds=25200,  # 7 hours absolute maximum
    container_resources=k8s.V1ResourceRequirements(
        requests={"nvidia.com/gpu": "4"},
        limits={"nvidia.com/gpu": "4"},
    ),
    # ...
)
```

## Key Takeaways

| Concept | When to Use | Key Benefit |
|---------|------------|-------------|
| `KubernetesExecutor` | All tasks need isolation | Pod-per-task, no resource bleed |
| `CeleryKubernetesExecutor` | Mix of fast + heavy tasks | Fast scheduling for light work, isolation for heavy |
| `executor_config` + `pod_override` | Per-task resource customization | GPU for training, high-mem for features |
| `KubernetesPodOperator` | Custom Docker images needed | Run any container as a task |
| Priority Classes | Shared clusters | Production models preempt experiments |
| Spot + Checkpointing | Cost optimization | 70% savings with graceful recovery |
| Progressive scaling | Expensive resources | Validate cheaply before burning GPU |

**Critical production rules:**
1. Never schedule GPU pods without a `startup_timeout_seconds` of at least 600s
2. Always checkpoint training — spot preemption and OOM are inevitable at scale
3. Use `is_delete_operator_pod=False` on failure — you need those logs
4. Run a CPU feasibility check before committing to 12 hours of GPU time
5. Set both Airflow `execution_timeout` AND Kubernetes `active_deadline_seconds`
6. Use `/dev/shm` volume mounts for PyTorch DataLoader multi-worker performance
7. Track GPU cost per model per day — visibility drives optimization
