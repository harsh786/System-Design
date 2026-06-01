# Model Serving & Scaling

## Overview

Model serving is the infrastructure that takes a trained model and makes it available for predictions at scale. The choice of serving pattern depends on latency requirements, throughput needs, cost constraints, and model complexity.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL SERVING SPECTRUM                                    │
│                                                                              │
│  ◀── Higher Latency Tolerance          Lower Latency Requirement ──▶       │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │    BATCH     │    │  STREAMING   │    │  REAL-TIME   │                 │
│  │              │    │              │    │              │                 │
│  │ Minutes-Hours│    │ Seconds-Min  │    │ Milliseconds │                 │
│  │              │    │              │    │              │                 │
│  │ Spark/MapRed │    │ Flink/Kafka  │    │ REST/gRPC   │                 │
│  │              │    │  Streams     │    │              │                 │
│  │ Pre-compute  │    │ Near-real-   │    │ On-demand    │                 │
│  │ all results  │    │ time updates │    │ inference    │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                              │
│  Use cases:          Use cases:          Use cases:                         │
│  - Recommendations   - Fraud scoring     - Search ranking                  │
│  - Email targeting   - Session features  - Ad bidding                      │
│  - Report generation - Anomaly detection - Chatbots                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Serving Patterns Deep Dive

### Pattern 1: Batch Serving

```
┌─────────────────────────────────────────────────────────────────┐
│  BATCH SERVING ARCHITECTURE                                      │
│                                                                   │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │  Data   │───▶│  Batch Job   │───▶│  Results     │           │
│  │  Lake   │    │  (Spark)     │    │  Store       │           │
│  └─────────┘    │              │    │  (Redis/DB)  │           │
│                  │  Load Model  │    └──────┬───────┘           │
│                  │  Score All   │           │                    │
│                  │  Write Back  │           ▼                    │
│                  └──────────────┘    ┌──────────────┐           │
│                                      │  Application │           │
│                                      │  (Lookup)    │           │
│  Schedule: Every 1h / 6h / 24h      └──────────────┘           │
│                                                                   │
│  Pros: Simple, cost-efficient, handles large scale              │
│  Cons: Stale predictions, no personalization on new data        │
│                                                                   │
│  Scaling: Horizontal - more Spark executors                     │
│  Cost: ~$0.001 per 1000 predictions (amortized)                │
│  Latency: Lookup = <5ms; Freshness = hours                     │
└─────────────────────────────────────────────────────────────────┘
```

### Pattern 2: Real-Time Serving

```
┌─────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME SERVING ARCHITECTURE                                         │
│                                                                          │
│  Client ──▶ Load Balancer ──▶ Model Server Cluster                     │
│                                                                          │
│  ┌──────┐    ┌─────────┐    ┌─────────────────────────────────┐       │
│  │Client│───▶│   LB    │───▶│  Model Server (Replicas)        │       │
│  │      │    │(Nginx/  │    │  ┌─────────┐  ┌─────────┐      │       │
│  │      │    │ Envoy)  │    │  │ Pod 1   │  │ Pod 2   │      │       │
│  └──────┘    └─────────┘    │  │ GPU/CPU │  │ GPU/CPU │      │       │
│                              │  └─────────┘  └─────────┘      │       │
│                              │  ┌─────────┐  ┌─────────┐      │       │
│                              │  │ Pod 3   │  │ Pod N   │      │       │
│                              │  │ GPU/CPU │  │ GPU/CPU │      │       │
│                              │  └─────────┘  └─────────┘      │       │
│                              └─────────────────────────────────┘       │
│                                         │                               │
│                                         ▼                               │
│                              ┌─────────────────────┐                   │
│                              │  Feature Store      │                   │
│                              │  (Online - Redis)   │                   │
│                              └─────────────────────┘                   │
│                                                                          │
│  Latency Budget:                                                        │
│  ┌──────────────────────────────────────────────────┐                  │
│  │ Network: 2ms │ Feature: 3ms │ Inference: 10ms │ Total: ~15ms     │
│  └──────────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pattern 3: Streaming Serving

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STREAMING SERVING ARCHITECTURE                                         │
│                                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐    │
│  │  Events  │───▶│  Kafka   │───▶│  Flink Job   │───▶│  Output  │    │
│  │  Stream  │    │  Topic   │    │              │    │  Topic   │    │
│  └──────────┘    └──────────┘    │  - Aggregate │    └──────────┘    │
│                                   │    features   │         │          │
│                                   │  - Score model│         ▼          │
│                                   │  - Emit result│    ┌──────────┐   │
│                                   └──────────────┘    │ Consumer │   │
│                                                        │ (Action) │   │
│                                                        └──────────┘   │
│                                                                          │
│  Use case: Fraud detection on payment events                           │
│  Latency: 100ms - 5s (event to action)                                │
│  Throughput: 100K+ events/sec                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Model Servers

### Comparison

| Feature | TorchServe | TF Serving | Triton | BentoML | Ray Serve |
|---------|-----------|-----------|--------|---------|-----------|
| Framework | PyTorch | TensorFlow | Multi | Multi | Multi |
| Protocol | REST/gRPC | gRPC | REST/gRPC | REST/gRPC | REST |
| Batching | Yes | Yes | Yes (best) | Yes | Yes |
| GPU Sharing | Limited | No | Yes | No | Yes |
| Multi-model | Yes | Yes | Yes | Yes | Yes |
| Model Ensemble | No | No | Yes | No | Yes |
| A/B Testing | No | No | No | Yes | Yes |
| Scalability | Good | Good | Excellent | Good | Excellent |
| Complexity | Medium | Low | High | Low | Medium |

### NVIDIA Triton Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  NVIDIA TRITON INFERENCE SERVER                                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Client (HTTP/gRPC)                                        │        │
│  └────────────────────────────────────────┬───────────────────┘        │
│                                            │                             │
│  ┌────────────────────────────────────────┼───────────────────┐        │
│  │  Triton Server                         ▼                    │        │
│  │  ┌──────────────────────────────────────────────────┐     │        │
│  │  │  Request Scheduler                                │     │        │
│  │  │  - Dynamic Batching (batch requests together)     │     │        │
│  │  │  - Sequence Batching (stateful models)            │     │        │
│  │  │  - Priority Queuing                               │     │        │
│  │  └──────────────────────┬───────────────────────────┘     │        │
│  │                          │                                  │        │
│  │  ┌──────────┐  ┌───────┴──┐  ┌──────────┐  ┌─────────┐ │        │
│  │  │TensorRT  │  │ PyTorch  │  │ONNX      │  │ Python  │ │        │
│  │  │ Backend  │  │ Backend  │  │Runtime   │  │ Backend │ │        │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │        │
│  │                                                          │        │
│  │  ┌──────────────────────────────────────────────────┐   │        │
│  │  │  Model Repository                                 │   │        │
│  │  │  models/                                          │   │        │
│  │  │  ├── model_a/                                     │   │        │
│  │  │  │   ├── config.pbtxt                            │   │        │
│  │  │  │   └── 1/model.onnx                           │   │        │
│  │  │  ├── model_b/                                     │   │        │
│  │  │  │   ├── config.pbtxt                            │   │        │
│  │  │  │   └── 1/model.plan (TensorRT)                │   │        │
│  │  │  └── ensemble/                                    │   │        │
│  │  │      └── config.pbtxt (chains A → B)            │   │        │
│  │  └──────────────────────────────────────────────────┘   │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                          │
│  Key Features:                                                          │
│  - Dynamic batching: Wait up to N ms to batch requests → higher GPU util│
│  - Concurrent model execution: Multiple models share GPU                │
│  - Model ensemble: Chain models without network hops                    │
│  - Model versioning: Hot-swap models without downtime                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Triton Dynamic Batching Performance

```
Requests arriving individually:    GPU Utilization: ~15%
With dynamic batching (batch=32):  GPU Utilization: ~85%

Throughput improvement: 4-8x
Latency trade-off: +5-20ms (configurable max wait)
```

---

## Containerization & Kubernetes

### ML Model Deployment on K8s

```
┌─────────────────────────────────────────────────────────────────────────┐
│  KUBERNETES ML DEPLOYMENT                                               │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  Namespace: ml-serving                                        │      │
│  │                                                                │      │
│  │  ┌─────────────────────────────────────────────────────┐    │      │
│  │  │  Deployment: fraud-model-v2                          │    │      │
│  │  │  replicas: 3 (HPA: min=3, max=20)                  │    │      │
│  │  │                                                      │    │      │
│  │  │  ┌──────────────────────────────────────────────┐  │    │      │
│  │  │  │  Pod                                          │  │    │      │
│  │  │  │  ┌────────────┐  ┌────────────────────────┐ │  │    │      │
│  │  │  │  │ Init:      │  │ Main Container:        │ │  │    │      │
│  │  │  │  │ Download   │  │ Model Server           │ │  │    │      │
│  │  │  │  │ Model from │  │ - TorchServe/Triton   │ │  │    │      │
│  │  │  │  │ Registry   │  │ - GPU: nvidia/A10     │ │  │    │      │
│  │  │  │  └────────────┘  │ - Memory: 16Gi        │ │  │    │      │
│  │  │  │                   └────────────────────────┘ │  │    │      │
│  │  │  │  ┌────────────────────────────────────────┐ │  │    │      │
│  │  │  │  │ Sidecar: metrics-exporter (Prometheus) │ │  │    │      │
│  │  │  │  └────────────────────────────────────────┘ │  │    │      │
│  │  │  └──────────────────────────────────────────────┘  │    │      │
│  │  └─────────────────────────────────────────────────────┘    │      │
│  │                                                                │      │
│  │  ┌─────────────────────────────────────────────────────┐    │      │
│  │  │  HPA (Horizontal Pod Autoscaler)                     │    │      │
│  │  │  Metric: custom/gpu_utilization > 70%               │    │      │
│  │  │  Or: custom/request_queue_depth > 100               │    │      │
│  │  │  Scale-up: 30s    Scale-down: 300s                  │    │      │
│  │  └─────────────────────────────────────────────────────┘    │      │
│  │                                                                │      │
│  │  ┌─────────────────────────────────────────────────────┐    │      │
│  │  │  Service: fraud-model-svc (ClusterIP)                │    │      │
│  │  │  Ingress: fraud-model.ml.company.com                │    │      │
│  │  └─────────────────────────────────────────────────────┘    │      │
│  └──────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Auto-Scaling Strategies for ML

| Strategy | Metric | Pros | Cons |
|----------|--------|------|------|
| CPU-based | CPU utilization | Simple, built-in | Misleading for GPU workloads |
| GPU-based | GPU utilization | Accurate for inference | Requires custom metrics |
| Queue-based | Request queue depth | Predictive | Need queue infrastructure |
| Latency-based | p99 latency | User-experience driven | Reactive, not predictive |
| Predictive | Historical traffic | Proactive scaling | Complex to implement |
| Cost-based | $/prediction | Cost optimized | May sacrifice latency |

### Scaling Example: Predictive Autoscaler

```python
# Scale based on predicted traffic (e.g., lunch rush for food delivery)
schedule:
  - cron: "0 11 * * *"   # 11 AM: scale up for lunch
    replicas: 20
  - cron: "0 14 * * *"   # 2 PM: scale down
    replicas: 5
  - cron: "0 18 * * *"   # 6 PM: scale up for dinner
    replicas: 15
  - cron: "0 22 * * *"   # 10 PM: scale to minimum
    replicas: 3
```

---

## Deployment Strategies

### A/B Testing

```
┌─────────────────────────────────────────────────────────────────┐
│  A/B TESTING FOR MODELS                                          │
│                                                                   │
│  Traffic ──▶ Router (Feature flags / Traffic splitting)          │
│                 │                                                 │
│         ┌──────┼──────────────┐                                 │
│         │      │              │                                  │
│         ▼      ▼              ▼                                  │
│     ┌──────┐ ┌──────┐    ┌──────┐                              │
│     │Model │ │Model │    │Model │                              │
│     │ A    │ │ B    │    │ C    │                              │
│     │(50%) │ │(25%) │    │(25%) │                              │
│     └──┬───┘ └──┬───┘    └──┬───┘                              │
│        │        │           │                                    │
│        └────────┴───────────┘                                   │
│                 │                                                 │
│                 ▼                                                 │
│     ┌─────────────────────────┐                                 │
│     │  Metrics Collection     │                                 │
│     │  - Business KPIs        │                                 │
│     │  - Model metrics        │                                 │
│     │  - Statistical tests    │                                 │
│     └─────────────────────────┘                                 │
│                                                                   │
│  Decision after N samples / statistical significance:            │
│  - Promote winner to 100%                                       │
│  - Or: inconclusive → extend test                              │
│                                                                   │
│  Pitfalls:                                                       │
│  - Novelty effects (new model gets engagement boost)            │
│  - Interference between variants                                │
│  - Insufficient sample size                                     │
│  - Simpson's paradox (segment-level vs overall)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Canary Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│  CANARY DEPLOYMENT SEQUENCE                                      │
│                                                                   │
│  Time ──▶                                                        │
│                                                                   │
│  t=0:  [████████████████████████████████████] v1 (100%)         │
│                                                                   │
│  t=1:  [███████████████████████████████████░] v1 (95%)          │
│         [░]                                   v2 (5%)  ← Canary │
│                                                                   │
│  t=2:  [█████████████████████████░░░░░░░░░░] v1 (75%)           │
│         [░░░░░░░░░]                           v2 (25%)          │
│         (if metrics OK)                                          │
│                                                                   │
│  t=3:  [█████████████████░░░░░░░░░░░░░░░░░░] v1 (50%)          │
│         [░░░░░░░░░░░░░░░░░░]                  v2 (50%)          │
│                                                                   │
│  t=4:  [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] v2 (100%)         │
│         ← v1 decommissioned                                     │
│                                                                   │
│  Auto-rollback triggers:                                        │
│  - Error rate > 1%                                              │
│  - p99 latency > 2x baseline                                   │
│  - Model accuracy drops > 5%                                    │
│  - Business KPI degradation > threshold                         │
└─────────────────────────────────────────────────────────────────┘
```

### Shadow Mode Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│  SHADOW MODE                                                     │
│                                                                   │
│  Request ──▶ Production Model (v1) ──▶ Response to User         │
│       │                                                          │
│       └───▶ Shadow Model (v2) ──▶ Log (not served to user)     │
│                                                                   │
│  Compare offline:                                                │
│  - Prediction distribution                                      │
│  - Latency                                                      │
│  - Resource usage                                               │
│  - Accuracy (if labels available)                               │
│                                                                   │
│  Pros: Zero risk to users                                       │
│  Cons: 2x compute cost, no real user feedback                   │
│  Duration: Typically 1-2 weeks                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Armed Bandit for Model Selection

```
┌─────────────────────────────────────────────────────────────────┐
│  MULTI-ARMED BANDIT (Thompson Sampling)                          │
│                                                                   │
│  Instead of fixed traffic split:                                │
│  - Dynamically allocate more traffic to better-performing model │
│  - Balances exploration (try all) vs exploitation (use best)    │
│                                                                   │
│  Time   Model A   Model B   Model C                            │
│  t=0    33%       33%       33%      (uniform exploration)     │
│  t=100  40%       35%       25%      (A looking better)        │
│  t=500  60%       30%       10%      (A is best)              │
│  t=1000 85%       10%       5%       (exploit A)              │
│                                                                   │
│  Algorithms:                                                    │
│  - Epsilon-greedy: Simple, explore ε% randomly                 │
│  - UCB (Upper Confidence Bound): Explore uncertain options     │
│  - Thompson Sampling: Bayesian, best theoretical guarantees    │
│                                                                   │
│  Advantage over A/B:                                            │
│  - Less regret (fewer users see bad model)                     │
│  - Adapts to non-stationary rewards                            │
│  - No need to pre-define test duration                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Edge Deployment

### Framework Comparison

| Framework | Target | Model Size | Latency | Platforms |
|-----------|--------|-----------|---------|-----------|
| TFLite | Mobile/IoT | <100MB | <50ms | Android, iOS, Embedded |
| ONNX Runtime | Universal | Any | <20ms | All |
| CoreML | Apple | <500MB | <30ms | iOS, macOS |
| TensorRT | Server GPU | Any | <5ms | NVIDIA GPUs |
| OpenVINO | Intel | Any | <10ms | Intel CPU/GPU/VPU |

### Edge Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EDGE ML DEPLOYMENT                                                     │
│                                                                          │
│  Cloud                                                                  │
│  ┌──────────────────────────────────────────────────────┐              │
│  │  ┌─────────┐   ┌──────────┐   ┌────────────────┐   │              │
│  │  │ Train   │──▶│ Optimize │──▶│ Model Registry │   │              │
│  │  │ (GPU)   │   │ Quantize │   │ (versioned)    │   │              │
│  │  │         │   │ Prune    │   │                │   │              │
│  │  └─────────┘   └──────────┘   └───────┬────────┘   │              │
│  └────────────────────────────────────────┼────────────┘              │
│                                            │ OTA Update                 │
│                                            ▼                            │
│  Edge Devices                                                          │
│  ┌──────────────────────────────────────────────────────┐              │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │              │
│  │  │ Device 1 │  │ Device 2 │  │ Device N │          │              │
│  │  │ TFLite   │  │ CoreML   │  │ ONNX RT  │          │              │
│  │  │ INT8     │  │ FP16     │  │ INT8     │          │              │
│  │  └──────────┘  └──────────┘  └──────────┘          │              │
│  │       │              │              │                 │              │
│  │       └──────────────┴──────────────┘                │              │
│  │                      │                                │              │
│  │                      ▼                                │              │
│  │  ┌────────────────────────────────────────────┐     │              │
│  │  │ Telemetry: accuracy, latency, battery, etc │     │              │
│  │  └────────────────────────────────────────────┘     │              │
│  └──────────────────────────────────────────────────────┘              │
│                                                                          │
│  Model Optimization Techniques:                                        │
│  - Quantization: FP32 → INT8 (4x smaller, 2-3x faster)               │
│  - Pruning: Remove 50-90% of weights                                  │
│  - Knowledge Distillation: Large teacher → small student               │
│  - Architecture Search: Find efficient architectures (MobileNet)       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## GPU Optimization

### Dynamic Batching

```
┌─────────────────────────────────────────────────────────────────┐
│  DYNAMIC BATCHING                                                │
│                                                                   │
│  Without batching (sequential):                                 │
│  Request 1 ──▶ [GPU: 5% util] ──▶ Response 1  (10ms)          │
│  Request 2 ──▶ [GPU: 5% util] ──▶ Response 2  (10ms)          │
│  Request 3 ──▶ [GPU: 5% util] ──▶ Response 3  (10ms)          │
│  Total: 30ms for 3 requests, GPU idle 85% of time             │
│                                                                   │
│  With dynamic batching:                                         │
│  Request 1 ─┐                                                   │
│  Request 2 ─┼──▶ [GPU: 60% util] ──▶ Response 1,2,3  (12ms)  │
│  Request 3 ─┘    (batch of 3)                                   │
│  Total: 12ms for 3 requests, 3x throughput improvement         │
│                                                                   │
│  Configuration:                                                  │
│  - max_batch_size: 32 (depends on GPU memory)                  │
│  - max_queue_delay_ms: 10 (latency vs throughput tradeoff)     │
│  - preferred_batch_sizes: [8, 16, 32]                          │
└─────────────────────────────────────────────────────────────────┘
```

### Model Parallelism

```
┌─────────────────────────────────────────────────────────────────┐
│  MODEL PARALLELISM (for large models that don't fit on 1 GPU)   │
│                                                                   │
│  Tensor Parallelism (split layers across GPUs):                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │  GPU 0  │  │  GPU 1  │  │  GPU 2  │  │  GPU 3  │          │
│  │ Layer 1 │  │ Layer 1 │  │ Layer 1 │  │ Layer 1 │          │
│  │ (shard) │  │ (shard) │  │ (shard) │  │ (shard) │          │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘          │
│       └─────────────┴────AllReduce┴─────────────┘              │
│                                                                   │
│  Pipeline Parallelism (split model vertically):                 │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    │
│  │  GPU 0  │───▶│  GPU 1  │───▶│  GPU 2  │───▶│  GPU 3  │    │
│  │Layer 1-8│    │Layer 9-16│   │Layer17-24│   │Layer25-32│    │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    │
│                                                                   │
│  LLM Serving (e.g., LLaMA 70B):                                │
│  - 4x A100 80GB with tensor parallelism                        │
│  - KV-cache optimization: PagedAttention (vLLM)                │
│  - Continuous batching for different sequence lengths           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Caching Strategies

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ML INFERENCE CACHING                                                   │
│                                                                          │
│  Layer 1: Request Cache (exact match)                                  │
│  ┌──────────────────────────────────────────────────┐                  │
│  │  Input hash → Cached prediction                   │                  │
│  │  Hit rate: 20-60% (depends on input diversity)   │                  │
│  │  Storage: Redis/Memcached                         │                  │
│  │  TTL: Minutes to hours                            │                  │
│  └──────────────────────────────────────────────────┘                  │
│                                                                          │
│  Layer 2: Feature Cache                                                │
│  ┌──────────────────────────────────────────────────┐                  │
│  │  Entity → Pre-computed features                   │                  │
│  │  Reduces feature computation latency              │                  │
│  │  Storage: Redis (online feature store)            │                  │
│  └──────────────────────────────────────────────────┘                  │
│                                                                          │
│  Layer 3: Embedding Cache                                              │
│  ┌──────────────────────────────────────────────────┐                  │
│  │  Item/User → Pre-computed embedding               │                  │
│  │  Avoids re-running embedding model                │                  │
│  │  Storage: Redis/Milvus                            │                  │
│  │  Invalidation: On item/user update                │                  │
│  └──────────────────────────────────────────────────┘                  │
│                                                                          │
│  Layer 4: Approximate Results (semantic cache)                         │
│  ┌──────────────────────────────────────────────────┐                  │
│  │  Similar input → Similar output (cosine sim>0.95)│                  │
│  │  For LLM serving: cache similar prompts          │                  │
│  │  Hit rate: 5-15% additional                      │                  │
│  └──────────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Load Balancing for ML

```
┌─────────────────────────────────────────────────────────────────┐
│  ML-AWARE LOAD BALANCING                                         │
│                                                                   │
│  Standard LB (round-robin) → BAD for ML                        │
│  Why: ML requests have variable compute time                    │
│                                                                   │
│  Better strategies:                                              │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  1. Least-Outstanding-Requests                          │    │
│  │     Route to server with fewest in-flight requests     │    │
│  │                                                         │    │
│  │  2. Latency-Aware                                       │    │
│  │     Route to server with lowest recent p50 latency     │    │
│  │                                                         │    │
│  │  3. GPU-Utilization-Aware                              │    │
│  │     Route to server with lowest GPU utilization        │    │
│  │     (requires custom metrics export)                   │    │
│  │                                                         │    │
│  │  4. Model-Aware Routing                                │    │
│  │     Route based on model version/variant requested     │    │
│  │     (for A/B testing / multi-model serving)            │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cost Optimization

### Cost Comparison (per 1M inferences)

| Setup | Cost | Latency (p99) | Best For |
|-------|------|---------------|----------|
| CPU (c5.2xlarge) | $2-5 | 50-200ms | Simple models, low traffic |
| GPU (g4dn.xlarge, T4) | $5-15 | 10-30ms | Medium models, batch |
| GPU (p3.2xlarge, V100) | $20-50 | 5-15ms | Large models, low latency |
| GPU (p4d.24xlarge, A100) | $50-100 | 3-8ms | LLMs, huge models |
| Spot/Preemptible | 60-70% discount | Variable | Batch, fault-tolerant |
| Serverless (Lambda/Cloud Functions) | $1-3 | 100-500ms | Sporadic traffic |

### Cost Optimization Decision Tree

```
Is traffic predictable?
├── Yes: Use reserved instances (30-60% savings)
│   └── Are there off-peak hours?
│       ├── Yes: Scale to 0 at night (40% savings)
│       └── No: Steady reserved capacity
└── No: 
    ├── Spiky: Serverless or aggressive autoscaling
    └── Bursty: Spot instances + on-demand fallback

Is model latency-sensitive?
├── No (>1s OK): Batch with spot instances
└── Yes (<100ms):
    ├── Small model: CPU instances (cheapest)
    └── Large model: GPU with batching (best $/inference)
```

---

## Capacity Planning

### Example: E-commerce Recommendation System

```
Requirements:
- 50M daily active users
- 10 recommendations per page load
- Average 5 page loads per session
- Peak traffic: 3x average (holiday sales)
- Latency SLA: p99 < 100ms

Calculations:
- Average QPS: 50M × 5 / 86400 = ~2,900 QPS
- Peak QPS: 2,900 × 3 = ~8,700 QPS
- With safety margin (2x): ~17,400 QPS target capacity

- Single GPU (T4) throughput: ~500 QPS (batch=16, model-specific)
- Required GPUs at peak: 17,400 / 500 = 35 GPUs
- With redundancy (N+2): 37 GPUs across 3 AZs

Infrastructure:
- 12-13 g4dn.xlarge instances per AZ (3 AZs)
- Estimated cost: ~$25K/month
- With spot instances for non-peak: ~$15K/month
```

---

## Real-World Case Studies

### Case Study: Instagram Explore (Recommendation Serving)
- **Scale**: 1B+ users, 500K QPS
- **Architecture**: Two-stage (candidate generation → ranking)
- **Serving**: Custom C++ inference, GPU clusters
- **Key Insight**: Heavy caching of embeddings; model produces ~1000 candidates, ranker selects 25

### Case Study: Stripe Radar (Fraud Detection)
- **Scale**: Millions of transactions/day, <100ms latency
- **Architecture**: Streaming features (Kafka) + real-time serving
- **Key Insight**: Feature computation is 60% of latency budget; pre-compute where possible

### Production Incident: GPU OOM in Production
- **Symptom**: Intermittent 500 errors under load
- **Root Cause**: Dynamic batching accumulated too many long sequences, exceeding GPU memory
- **Fix**: Added max-sequence-length bucketing + per-request memory estimation
- **Learning**: Always set memory guards; test with adversarial input sizes

---

## Interview Questions

1. **Design a model serving system that handles 100K QPS with <20ms p99 latency**
   - Focus: Batching, caching, GPU selection, horizontal scaling

2. **How would you deploy a new model version with zero downtime and rollback capability?**
   - Focus: Canary, shadow mode, feature flags, metrics-based promotion

3. **Compare batch vs real-time serving for a recommendation system**
   - Focus: Freshness vs cost, hybrid approaches, cache warming

4. **Design edge deployment for a computer vision model on 1M IoT devices**
   - Focus: Model compression, OTA updates, A/B testing on edge, telemetry

5. **How do you handle a model that needs 40GB of GPU memory for inference?**
   - Focus: Model parallelism, quantization, distillation, KV-cache optimization

---

## Production War Stories

Real-world incidents from model serving infrastructure. These stories illustrate why serving architecture decisions matter.

---

### War Story 6: The Latency Spike from Model Size

**Company:** Search engine startup

**What Happened:**
The NLP team trained a new transformer-based ranking model that improved relevance by 12%. When deployed to production, P99 latency jumped from 50ms to 800ms. The SLA was 200ms. User engagement actually dropped because results took too long.

**Root Cause Analysis:**
- The new model was 3x larger (1.2GB vs 400MB)
- It didn't fit efficiently in GPU memory alongside the batching buffer
- Constant memory swapping between GPU and CPU memory
- The model also had dynamic shapes that prevented TensorRT optimization
- No latency benchmarking was done before deployment — only accuracy was evaluated

**How It Was Detected:**
- P99 latency alerts fired immediately after deployment
- Canary deployment caught it at 5% traffic (before full rollout)
- GPU memory utilization dashboard showed 98% usage with constant swapping

**How It Was Fixed:**
1. Immediate: Rolled back to previous model
2. Short-term:
   - Quantized model from FP32 → INT8 (3x smaller, minimal accuracy loss: -0.3%)
   - Optimized batching (dynamic batching with max wait time of 5ms)
   - Fixed input shapes with padding (enabled TensorRT optimization)
3. Long-term:
   - Model distillation: trained a smaller model to mimic the large one (90% of the gains, 30% of the size)
   - Latency benchmarking added to model promotion pipeline
   - Model size budget: any model >500MB requires architecture review
   - A/B test framework includes latency as a guardrail metric

**Key Takeaway:**
Always benchmark latency BEFORE deploying larger models. Accuracy improvements mean nothing if latency degrades the user experience.

**Prevention Checklist:**
- [ ] Latency benchmarking in model CI/CD (P50, P95, P99)
- [ ] Model size budgets per service
- [ ] Quantization as standard step in model optimization
- [ ] GPU memory profiling before deployment
- [ ] Latency as a guardrail metric in A/B tests
- [ ] Canary deployments with automatic rollback on latency regression

---

### War Story 7: The Cold Start Catastrophe

**Company:** Video streaming platform

**What Happened:**
The recommendation service used Kubernetes auto-scaling. During a promotional event, traffic spiked 10x in 2 minutes. The auto-scaler reacted correctly and spun up new pods. But each pod took 45 seconds to load the recommendation model (2GB embedding table). During those 45 seconds, requests to new pods timed out, causing a cascade of retries and a 3-minute partial outage.

**Root Cause Analysis:**
- Model file was 2GB, loaded from S3 on pod startup
- No model pre-loading or caching
- No warm-up period before receiving traffic
- Health check marked pods as "ready" before model was loaded
- Auto-scaler was reactive only (threshold-based), not predictive

**How It Was Detected:**
- Request timeout rate spiked to 40% during the event
- Auto-scaler metrics showed pods "ready" but not actually serving
- User reports of empty recommendation sections

**How It Was Fixed:**
1. Immediate: Manually pre-scaled before next event
2. Short-term:
   - Readiness probe now verifies model is loaded and can serve a test prediction
   - Model cached on node's local SSD (30s → 3s load time)
   - Keep-warm: minimum 3 replicas always running (never scale to zero)
3. Long-term:
   - Predictive auto-scaling: ML model predicts traffic 15 minutes ahead based on historical patterns
   - Model loading optimization: memory-mapped files, lazy loading of embedding shards
   - Pre-scaling triggers for known events (marketing campaigns, launches)
   - Graceful degradation: serve cached/popular recommendations during cold start

**Key Takeaway:**
ML model loading time must be factored into scaling strategy. Standard auto-scaling assumes sub-second pod readiness — ML services often need 10-60 seconds.

**Prevention Checklist:**
- [ ] Readiness probes that verify model serving capability (not just process running)
- [ ] Model caching on local storage (not loading from remote on every start)
- [ ] Minimum replica count (never scale to zero for critical services)
- [ ] Predictive auto-scaling for known traffic patterns
- [ ] Load test with scale-from-cold scenarios
- [ ] Pre-scaling runbooks for planned events
- [ ] Warm-up period: pod receives shadow traffic before live traffic

---

### War Story 8: The A/B Test That Wasn't

**Company:** E-commerce marketplace

**What Happened:**
A new product ranking model showed +5% conversion in A/B test over 2 weeks. The team rolled it out to 100% of traffic. Within a week, overall revenue dropped 3%. Leadership was furious.

**Root Cause Analysis:**
Simpson's Paradox. The A/B test had a bug in its randomization:
- Treatment group: 80% mobile users, 20% desktop users
- Control group: 50% mobile, 50% desktop
- Mobile users had inherently higher conversion rates (they were more purchase-intent)
- The model wasn't actually better — it just got a more favorable user mix
- Additionally, the model performed worse for desktop users (-8%) which wasn't caught because they were underrepresented in the treatment group

**How It Was Detected:**
- Revenue drop after full rollout (1 week)
- Post-hoc segment analysis revealed the imbalance
- A data scientist re-analyzed results stratified by platform → no significant improvement

**How It Was Fixed:**
1. Immediate: Rolled back to previous model
2. Short-term:
   - Fixed randomization: hash-based assignment ensuring demographic balance
   - Added Sample Ratio Mismatch (SRM) test — alerts if group compositions differ
   - Segment-level results required before any ship decision
3. Long-term:
   - Guardrail metrics: revenue, latency, and error rate must not degrade for ANY segment
   - Minimum test duration: 2 weeks + weekend coverage
   - Automated heterogeneous treatment effect analysis
   - Required statistical review before shipping any A/B test result

**Key Takeaway:**
A/B tests can lie. Always check segment-level results, verify randomization balance, and use guardrail metrics that must not degrade for any user segment.

**Prevention Checklist:**
- [ ] Sample Ratio Mismatch (SRM) checks on all A/B tests
- [ ] Stratified analysis by key segments (platform, region, user tenure)
- [ ] Guardrail metrics (must-not-degrade thresholds)
- [ ] Minimum test duration with weekend coverage
- [ ] Hash-based randomization (not session-based)
- [ ] Statistical review before shipping decisions
- [ ] Novelty effect check: compare week 1 vs week 2 results
