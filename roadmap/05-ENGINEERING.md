# Stage 5: Production Engineering & MLOps

> Duration: 3-4 months | Output: A system handling real traffic with monitoring and auto-scaling

---

## Why This Stage Exists

Here's the dirty secret of the ML industry:

```
Companies don't pay for models. They pay for SYSTEMS that use models.

What gets you hired as an ML engineer:      What gets you promoted to Senior/Staff:
─────────────────────────────────────       ─────────────────────────────────────
"I trained a model that gets 95%"           "I built a system that serves 50K
                                             requests/sec at p99 < 100ms, costs
                                             $X/month, retrains weekly, and
                                             hasn't had an incident in 6 months"
```

This stage transforms you from "person who trains models" into "person who
builds ML systems that run in production 24/7 without babysitting."

---

## The Production ML Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION ML SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 5: OBSERVABILITY & OPERATIONS                                  │  │
│  │  Prometheus │ Grafana │ PagerDuty │ Cost dashboards │ SLOs           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 4: SERVING & INFERENCE                                         │  │
│  │  Model serving │ Load balancing │ Caching │ A/B testing │ Canary     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 3: TRAINING & EXPERIMENT                                       │  │
│  │  Distributed training │ HPO │ Experiment tracking │ Model registry   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 2: DATA                                                        │  │
│  │  Feature store │ Data pipelines │ Validation │ Versioning │ Lakehouse│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 1: INFRASTRUCTURE                                              │  │
│  │  Docker │ Kubernetes │ Terraform │ Cloud (AWS/GCP/Azure) │ GPU mgmt  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Month 1: Infrastructure (Docker + K8s + Cloud)

### Week 1-2: Docker (Non-Negotiable Skill)

```
You must be fluent in Docker. No exceptions.

Learn:
├── Dockerfile writing (multi-stage builds for ML)
│   ├── Base image selection (slim vs full, CUDA images)
│   ├── Layer caching (order matters: deps first, code last)
│   ├── .dockerignore (don't copy data/ or .git/)
│   └── Multi-stage: build deps in big image, copy to slim runtime
├── docker-compose (multi-container applications)
│   ├── Services: API + model + database + cache + monitoring
│   ├── Volumes (persist data, mount models)
│   ├── Networks (service discovery)
│   └── Health checks
├── ML-specific Docker patterns
│   ├── GPU passthrough (nvidia-docker, --gpus all)
│   ├── Large model files (mount, don't COPY)
│   ├── Dependency management (pip freeze, conda-lock)
│   └── Reproducibility (pin EVERYTHING -- base image, deps, models)
└── Container registries (ECR, GCR, DockerHub)

Build:
├── Dockerfile for training (CUDA, PyTorch, your code)
├── Dockerfile for inference (lightweight, ONNX Runtime)
├── docker-compose with: API + Redis cache + Postgres + Prometheus + Grafana
└── CI pipeline that builds and pushes images on git push
```

### Week 3-4: Kubernetes Fundamentals

```
You don't need to be a K8s admin. You need to understand:
├── Pods, Deployments, Services, Ingress (core concepts)
├── ConfigMaps, Secrets (configuration management)
├── Resource requests/limits (CPU, memory, GPU)
├── Horizontal Pod Autoscaler (HPA) -- scale on CPU/custom metrics
├── Jobs and CronJobs (batch training, scheduled retraining)
├── Persistent Volumes (model storage)
├── GPU scheduling (node selectors, tolerations)
└── Helm charts (packaging K8s applications)

ML-specific K8s:
├── KServe / Seldon Core (model serving on K8s)
├── Kubeflow (ML pipelines on K8s)
├── Ray on K8s (distributed training)
├── Spot instances for training (cost savings)
└── Node pools (CPU for serving, GPU for training)

DON'T deep-dive K8s internals unless you're going into infra.
Know enough to:
- Write Deployment YAMLs
- Debug why a pod isn't starting
- Set up autoscaling
- Manage GPU resources
```

### Cloud Provider Knowledge (Pick ONE primary)

```
AWS (most ML jobs):                    GCP (best ML tools):
├── SageMaker (training, serving)      ├── Vertex AI (end-to-end)
├── EC2 (GPU instances: p4d, g5)       ├── GKE (K8s with GPU)
├── S3 (data + model storage)          ├── BigQuery (data warehouse)
├── ECR (container registry)           ├── Cloud Storage
├── Lambda (lightweight inference)      ├── TPU access (for JAX)
├── EKS (managed K8s)                  └── Artifact Registry
├── Step Functions (orchestration)
└── IAM (security)

Azure (enterprise):
├── Azure ML (training, serving)
├── AKS (managed K8s)
├── Blob Storage
├── Azure OpenAI Service (GPT-4 access)
└── Cosmos DB (for vector search)

Minimum cloud skills:
├── Spin up GPU instances for training
├── Store data and models in object storage
├── Deploy containers to managed K8s
├── Set up CI/CD that deploys to cloud
├── Understand pricing (THIS MATTERS AT ARCHITECT LEVEL)
└── Security basics (IAM, VPC, encryption)
```

**Resources:**

| Resource | Link |
|----------|------|
| Docker for ML (official guide) | https://docs.docker.com/guides/use-case/ml/ |
| Kubernetes The Hard Way | https://github.com/kelseyhightower/kubernetes-the-hard-way |
| AWS ML Specialty course (free tier) | https://aws.amazon.com/training/learn-about/machine-learning/ |
| "Designing ML Systems" - Chip Huyen | THE book for ML systems |
| Made With ML (MLOps course) | https://madewithml.com/ |

---

## Month 2: ML Pipelines & Model Serving

### Week 5-6: Training Pipelines & Experiment Management

```
Experiment Tracking (pick one, master it):
├── Weights & Biases (W&B) -- BEST for research teams
│   ├── Experiment logging (metrics, config, artifacts)
│   ├── Sweeps (hyperparameter search)
│   ├── Tables (data visualization)
│   ├── Artifacts (dataset/model versioning)
│   └── Reports (share results)
├── MLflow -- BEST for production teams
│   ├── Tracking (log params, metrics, artifacts)
│   ├── Projects (reproducible runs)
│   ├── Models (model registry, staging/production)
│   └── Model serving (REST API from registry)
└── Both are useful. W&B for experiments, MLflow for lifecycle.

Data Versioning & Feature Stores:
├── DVC (Data Version Control) -- git for data
├── Feature stores
│   ├── Feast (open-source, batch + online)
│   ├── Tecton (managed, real-time)
│   └── Why: consistent features between training and serving
├── Data validation
│   ├── Great Expectations (assertions on data)
│   ├── Pandera (pandas schema validation)
│   └── Detect: missing values, distribution shifts, schema changes
└── Pipeline orchestration
    ├── Prefect (Python-native, modern)
    ├── Airflow (industry standard, more complex)
    ├── Dagster (type-safe, testable)
    └── Metaflow (Netflix, great for ML)

Build a complete training pipeline:
├── Data ingestion → validation → feature engineering
├── Training with hyperparameter search
├── Model evaluation with multiple metrics
├── Model registration (promote to "staging")
├── Automated tests (data quality, model performance)
├── Triggered by: schedule, data arrival, or manual
└── Everything logged, reproducible, versioned
```

### Week 7-8: Model Serving & Inference Optimization

```
Serving Patterns:
├── Online (real-time, one request at a time)
│   ├── FastAPI + uvicorn (simple, works for most cases)
│   ├── Triton Inference Server (NVIDIA, high throughput)
│   ├── TorchServe (PyTorch-native)
│   ├── TF Serving (TensorFlow-native)
│   ├── vLLM (LLM serving, paged attention)
│   └── BentoML (framework-agnostic, batteries included)
├── Batch (process many inputs, latency doesn't matter)
│   ├── Spark ML / Ray (distributed batch inference)
│   ├── Scheduled jobs (process overnight)
│   └── When: recommendations, risk scoring, reports
├── Streaming (process events as they arrive)
│   ├── Kafka + model (real-time scoring)
│   ├── Flink + model
│   └── When: fraud detection, anomaly detection
└── Edge (on-device, no internet needed)
    ├── ONNX Runtime (cross-platform)
    ├── TensorRT (NVIDIA GPUs)
    ├── Core ML (Apple devices)
    ├── TFLite (mobile)
    └── When: latency-critical, privacy, offline

Optimization Techniques:
├── Quantization
│   ├── Post-training quantization (PTQ) -- fast, some accuracy loss
│   ├── Quantization-aware training (QAT) -- less loss, needs retraining
│   ├── INT8, INT4, FP16, BF16
│   └── For LLMs: GPTQ, AWQ, GGUF formats
├── Pruning
│   ├── Structured (remove entire channels/heads)
│   ├── Unstructured (zero out individual weights)
│   └── Effect: smaller model, faster inference
├── Knowledge Distillation
│   ├── Train small "student" model from large "teacher"
│   ├── Much smaller model with ~95% of accuracy
│   └── How DistilBERT was created
├── Batching
│   ├── Dynamic batching (collect requests, process together)
│   ├── Continuous batching (for LLMs -- don't wait)
│   └── Effect: 5-10x throughput improvement
├── Caching
│   ├── Embedding cache (Redis/Memcached)
│   ├── KV-cache for LLMs
│   ├── Prompt caching (identical prompts)
│   └── Semantic cache (similar queries → same answer)
└── Hardware Optimization
    ├── ONNX export (optimize graph)
    ├── TensorRT compilation (NVIDIA specific, fastest)
    ├── Flash Attention (memory-efficient attention)
    └── Speculative decoding (for LLMs)

Build:
├── Serve a model with FastAPI (baseline)
├── Optimize with ONNX Runtime (measure speedup)
├── Add dynamic batching (measure throughput gain)
├── Add Redis caching (measure cache hit rate)
├── Load test with locust (find breaking point)
└── Quantize model, compare: latency, throughput, accuracy
```

---

## Month 3: Monitoring, Testing, and Reliability

### Week 9-10: ML Monitoring (The Most Neglected Skill)

```
What to monitor:
├── System metrics (the basics)
│   ├── Latency (p50, p95, p99)
│   ├── Throughput (requests/sec)
│   ├── Error rate
│   ├── CPU/GPU/Memory utilization
│   └── Queue depth
├── Model metrics (ML-specific)
│   ├── Prediction distribution shift
│   ├── Feature drift (inputs changing over time)
│   ├── Concept drift (relationship between X and Y changes)
│   ├── Data quality (missing values, schema violations)
│   └── Model staleness (when was it last retrained?)
├── Business metrics (what actually matters)
│   ├── Conversion rate, click-through rate
│   ├── Revenue impact
│   ├── User feedback signals
│   └── A/B test results
└── Alert on
    ├── Latency spike (p99 > threshold)
    ├── Feature distribution shift (KS-test, PSI)
    ├── Prediction confidence drop
    ├── Error rate increase
    └── Model accuracy degradation (if ground truth available)

Tools:
├── Prometheus + Grafana (system + custom metrics)
├── Evidently AI (data drift, model monitoring, open source)
├── WhyLabs (managed monitoring)
├── Arize (model observability)
├── Custom dashboards (Streamlit or Grafana)
└── PagerDuty/OpsGenie (alerting)

Build:
├── Prometheus metrics in your serving API
├── Grafana dashboard (latency, throughput, GPU, predictions)
├── Data drift detector (Evidently or custom with KS-test)
├── Automated retraining trigger when drift detected
└── Alerting rules (Slack/PagerDuty when things break)
```

### Week 11-12: Testing ML Systems + CI/CD

```
ML Testing Pyramid:
                    ┌──────────┐
                    │  E2E /   │  Does the whole pipeline work?
                    │  System  │  (data in → prediction out)
                    ├──────────┤
                    │Integration│  Do components work together?
                    │  Tests   │  (feature eng + model + serving)
                    ├──────────┤
                    │   Unit   │  Do individual functions work?
                    │  Tests   │  (transforms, preprocessing)
                    └──────────┘

What to test in ML:
├── Data tests
│   ├── Schema validation (columns, types, ranges)
│   ├── Distribution tests (no sudden changes)
│   ├── Completeness (expected number of rows)
│   └── Referential integrity
├── Model tests
│   ├── Invariance tests (rotation shouldn't change label for text)
│   ├── Directional tests (increasing X should increase Y)
│   ├── Minimum performance thresholds
│   ├── Slice-based testing (performance per subgroup)
│   └── No regression vs previous model
├── Infrastructure tests
│   ├── Model loads correctly
│   ├── API returns expected schema
│   ├── Latency within SLA
│   └── Graceful degradation under load
└── Integration tests
    ├── Training pipeline produces valid model
    ├── Serving pipeline returns correct predictions
    └── Monitoring triggers correctly

CI/CD for ML:
├── On every PR:
│   ├── Linting, type checking, unit tests
│   ├── Data validation tests
│   ├── Train on small subset (smoke test)
│   └── Model quality gates (accuracy > threshold)
├── On merge to main:
│   ├── Full training run
│   ├── Evaluation on holdout set
│   ├── Comparison with current production model
│   └── If better: promote to staging
├── Deployment:
│   ├── Canary deployment (10% traffic → monitor → full rollout)
│   ├── Shadow deployment (run both, compare, don't serve new model yet)
│   ├── Blue-green (instant switch, easy rollback)
│   └── A/B testing (statistical comparison)
└── Rollback:
    ├── Automated if error rate spikes
    ├── One-click manual rollback
    └── All model versions preserved in registry
```

---

## Month 3-4: Cost Optimization & Scaling

### The Cost Conversation (Architects Must Know This)

```
GPU Cost Reality (2024 approximate):
├── A100 80GB: $2-4/hr (cloud)
├── H100 80GB: $4-8/hr (cloud)
├── Training a large model: $10K-$1M+ (one run)
├── Serving an LLM: $0.01-0.10 per request
└── Most ML teams overspend by 40-60%

Cost Optimization Strategies:
├── Training
│   ├── Spot/preemptible instances (60-80% savings, handle interruptions)
│   ├── Mixed precision (2x speed = half the cost)
│   ├── Gradient accumulation (use smaller GPU, simulate large batch)
│   ├── Early stopping (don't waste compute on diminishing returns)
│   ├── Efficient architectures (EfficientNet, MobileNet, DistilBERT)
│   └── Progressive training (start small, grow model/data)
├── Serving
│   ├── Quantization (INT8 = 4x less memory, 2x faster)
│   ├── Batching (amortize overhead across requests)
│   ├── Caching (don't recompute identical inputs)
│   ├── Model cascading (cheap model first, expensive only if needed)
│   ├── Auto-scaling (scale to zero when idle)
│   └── Right-sizing (don't use A100 for a logistic regression)
├── Data
│   ├── Parquet over CSV (compression + columnar = 10x less storage)
│   ├── Data lifecycle (archive old data to cold storage)
│   └── Compute pushdown (filter at storage layer)
└── Architecture
    ├── Serverless for bursty workloads
    ├── Reserved instances for steady workloads
    ├── Multi-region only when needed (latency vs cost)
    └── Edge inference for high-volume (save bandwidth)
```

---

## Stage 5 Capstone Project

```
PROJECT: Production ML Platform (Mini)
────────────────────────────────────────

Build a scaled-down version of an ML platform that handles:
- Automated training pipelines
- Model registry with promotion workflow
- Serving with auto-scaling and canary deployment
- Full monitoring stack
- Cost tracking

Architecture:
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Data   │────▶│  Training    │────▶│   Model     │────▶│  Serving     │
│  Source │     │  Pipeline    │     │  Registry   │     │  (API + LB)  │
└─────────┘     └──────────────┘     └─────────────┘     └──────┬───────┘
                       │                     │                     │
                       ▼                     ▼                     ▼
                ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
                │  Experiment  │     │  CI/CD      │     │  Monitoring  │
                │  Tracking    │     │  Pipeline   │     │  + Alerting  │
                │  (W&B/MLflow)│     │  (GH Actions)│    │  (Grafana)   │
                └──────────────┘     └─────────────┘     └──────────────┘

Tech choices (one possible stack):
├── Training: PyTorch + Lightning + Optuna
├── Orchestration: Prefect (or GitHub Actions for simple cases)
├── Tracking: MLflow (training) + W&B (experiments)
├── Registry: MLflow Model Registry
├── Serving: FastAPI + ONNX Runtime + Redis cache
├── Infra: Docker + docker-compose (locally) or K8s (cloud)
├── Monitoring: Prometheus + Grafana + Evidently
├── CI/CD: GitHub Actions
├── Load testing: Locust
└── Cost: track GPU hours, inference cost per request

Success criteria:
├── System handles 1000 req/sec with p99 < 200ms
├── Automated retraining when drift detected
├── Canary deployment with automatic rollback
├── <5 min to deploy a new model version
├── Full observability dashboard
├── Documented runbooks for common failures
└── Cost report showing optimization impact
```

---

## Stage 5 Completion Criteria

- [ ] Can containerize any ML application (training + serving)
- [ ] Can deploy to Kubernetes with auto-scaling and GPU support
- [ ] Can build a CI/CD pipeline for ML (training → evaluation → deployment)
- [ ] Can set up monitoring that catches model degradation before users notice
- [ ] Can optimize serving latency by 5-10x (quantization, batching, caching)
- [ ] Can estimate and optimize costs for ML workloads
- [ ] Can design a canary/shadow deployment strategy
- [ ] Can write proper ML tests (data, model, integration)
- [ ] Have a working production system on GitHub (docker-compose up and it works)
- [ ] Can explain tradeoffs between different serving architectures
