# GPU Scheduling and Allocation for AI Systems

## The GPU Scheduling Challenge

### Why GPUs Are Different from CPUs

```
CPU workloads:
├── Elastic: scale from 1 to 100 instances in seconds
├── Cheap: $0.05-0.50/hr per vCPU
├── Fungible: any CPU can run any workload
└── Overcommit-friendly: 10 pods can share 1 CPU

GPU workloads:
├── Rigid: scale takes 2-5 minutes (model loading)
├── Expensive: $4-32/hr per GPU
├── Specialized: model X needs GPU type Y with Z GB VRAM
├── Exclusive: model occupies ALL GPU memory (usually)
└── Wasted when idle: paying $8/hr even with 0 requests
```

### The Core Scheduling Problem

```
You have:
├── 16 × A100-80GB GPUs ($128/hr total)
├── 4 × A10G-24GB GPUs ($16/hr total)
└── 2 × H100-80GB GPUs ($64/hr total)

You need to serve:
├── GPT-4 equivalent (70B params): needs 4× A100 (tensor parallel)
├── Llama-13B fine-tuned: needs 1× A100 or 1× A10G (quantized)
├── Embedding model: needs 1× A10G
├── Reranker model: needs 1× A10G
├── Whisper (speech): needs 1× A100
├── Image model: needs 1× H100
└── 5 LoRA adapters: share base model, need 1× A100

Question: How do you allocate GPUs to maximize utilization while meeting latency SLAs?
```

## Kubernetes GPU Scheduling

### NVIDIA Device Plugin

```yaml
# Node with GPUs exposes them as resources
apiVersion: v1
kind: Node
metadata:
  name: gpu-node-01
status:
  capacity:
    nvidia.com/gpu: 8        # 8 GPUs available
    nvidia.com/gpu.memory: 80Gi  # per GPU
  allocatable:
    nvidia.com/gpu: 8
```

### Pod GPU Requests

```yaml
# Pod requesting GPU resources
apiVersion: v1
kind: Pod
metadata:
  name: llm-serving-70b
spec:
  containers:
  - name: model-server
    image: vllm/vllm-openai:latest
    resources:
      requests:
        nvidia.com/gpu: 4           # Need 4 GPUs
        memory: "320Gi"             # CPU RAM for loading
      limits:
        nvidia.com/gpu: 4
    env:
    - name: TENSOR_PARALLEL_SIZE
      value: "4"
    - name: MODEL_NAME
      value: "meta-llama/Llama-2-70b-chat-hf"
  
  nodeSelector:
    gpu-type: a100-80gb             # Must be A100
    gpu-interconnect: nvlink        # Need NVLink for tensor parallel
  
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

### Multi-Instance GPU (MIG)

MIG splits one physical A100 into up to 7 isolated GPU instances:

```
A100-80GB with MIG enabled:
├── 7 × 1g.10gb (7 instances, 10GB each)  → 7 small models
├── 3 × 2g.20gb + 1 × 1g.10gb             → 3 medium + 1 small
├── 2 × 3g.40gb                             → 2 large models
├── 1 × 4g.40gb + 1 × 3g.40gb             → 1 large + 1 medium-large
└── 1 × 7g.80gb                             → 1 model uses full GPU

Each MIG slice has:
├── Guaranteed memory (isolated, can't be stolen)
├── Guaranteed compute (SM cores dedicated)
├── Own copy engines (memory bandwidth isolated)
└── Fault isolation (one slice crash doesn't affect others)
```

```yaml
# Kubernetes MIG configuration
apiVersion: v1
kind: Pod
metadata:
  name: embedding-model
spec:
  containers:
  - name: embedder
    image: embedding-server:latest
    resources:
      requests:
        nvidia.com/mig-1g.10gb: 1    # Request one 10GB MIG slice
      limits:
        nvidia.com/mig-1g.10gb: 1
```

### Time-Slicing (Alternative to MIG)

```yaml
# NVIDIA time-slicing config
apiVersion: v1
kind: ConfigMap
metadata:
  name: nvidia-device-plugin-config
data:
  config.yaml: |
    version: v1
    sharing:
      timeSlicing:
        resources:
        - name: nvidia.com/gpu
          replicas: 4    # Each physical GPU appears as 4 logical GPUs

# Pros: Simple, works on any GPU, no MIG hardware requirement
# Cons: No memory isolation (pods can OOM each other), no compute guarantee
# Use for: Dev/test, non-latency-critical batch jobs
```

## GPU Allocation Strategies

### Strategy 1: Dedicated GPU per Model

```
Layout:
├── GPU 0-3: 70B model (tensor parallel, 4 GPUs)
├── GPU 4: 13B model (single GPU)
├── GPU 5: Embedding model
├── GPU 6: Reranker model
├── GPU 7: Whisper model

Pros:
├── Guaranteed performance (no contention)
├── Simple (no scheduling complexity)
├── Predictable latency
└── Easy capacity planning

Cons:
├── Expensive (GPU 5-7 maybe 30% utilized)
├── Can't handle spikes (fixed capacity)
└── Wasted money on idle GPUs

Best for: Production with strict SLAs, high-traffic services
```

### Strategy 2: Shared GPU with MIG

```
One A100-80GB serves multiple models:
├── MIG slice 1 (10GB): Embedding model (text-embedding-3)
├── MIG slice 2 (10GB): Reranker model
├── MIG slice 3 (10GB): Classification model
├── MIG slice 4 (10GB): Sentiment model
├── MIG slice 5 (10GB): Toxicity detector
├── MIG slice 6 (10GB): PII detector
├── MIG slice 7 (10GB): Query router
└── Total: 7 models on 1 GPU! ($8/hr instead of $56/hr)

Pros:
├── 7x cost reduction for small models
├── Hardware-level isolation
├── Each model has guaranteed resources
└── No noisy neighbor (unlike time-slicing)

Cons:
├── Only works for models that fit in 10GB (< 7B params quantized)
├── Only available on A100/A30/H100
├── Fixed partitioning (can't resize without restart)
└── Limited to pre-defined MIG profiles

Best for: Multiple small models (embeddings, classifiers, guardrails)
```

### Strategy 3: Dynamic Scheduling

```
On-demand GPU allocation:
├── Requests arrive → check if model is loaded
├── If loaded: serve immediately (hot path)
├── If not loaded: schedule GPU, load model (cold path, 30-120s)
├── After idle timeout: unload model, release GPU
└── Scale to zero when no traffic

Implementation with KNative / Serverless GPUs:
├── Request → Queue → Scheduler → GPU allocation → Model load → Serve
├── Keep-alive: model stays loaded for 5 min after last request
├── Scale-to-zero: after 5 min idle, unload and release GPU
└── Cold start mitigation: pre-warm N instances based on schedule

Pros:
├── Pay only for actual usage
├── Infinite scale (cloud has many GPUs)
├── No wasted capacity
└── Good for batch/async workloads

Cons:
├── Cold start: 30-120s for first request
├── Complex scheduling logic
├── Model loading overhead
└── Not suitable for real-time SLAs without pre-warming

Best for: Dev/test, batch processing, low-traffic models
```

### Strategy 4: Spot/Preemptible Instances

```
Spot GPU instances (60-70% cheaper):
├── A100 on-demand: $8/hr
├── A100 spot: $2.50/hr (68% savings!)
├── BUT: can be reclaimed with 30-second warning
└── Need: graceful handling of preemption

Handling preemption:
├── Receive 30-second warning signal
├── Stop accepting new requests
├── Complete in-flight requests (or save state)
├── Checkpoint any batch processing
├── Release gracefully
└── Scheduler finds replacement instance

Where to use spot:
├── Batch processing (embeddings, evals)
├── Training / fine-tuning (with checkpointing)
├── Non-critical inference (can retry on another instance)
├── Development / testing
└── NOT for: latency-critical production serving

Architecture:
├── Base capacity: on-demand instances (guaranteed)
├── Burst capacity: spot instances (cost-effective)
├── Fallback: when spot reclaimed, on-demand handles overflow
└── Queue: requests wait during spot → on-demand transition
```

## GPU Topology Awareness

### Why Topology Matters

```
Tensor Parallelism (split model across GPUs):
├── Needs: high-bandwidth interconnect between GPUs
├── NVLink: 600 GB/s (A100) → USE THIS
├── PCIe Gen4: 32 GB/s → TOO SLOW for tensor parallel
└── Rule: tensor parallel GPUs MUST be on same NVLink domain

Pipeline Parallelism (split layers across GPUs):
├── Less bandwidth-sensitive (only activations between stages)
├── PCIe Gen4: acceptable
├── Cross-node: InfiniBand (200 Gb/s) acceptable
└── Rule: pipeline parallel can span nodes

Data Parallelism (full model copy on each GPU):
├── Only need to sync gradients (training) or not at all (inference)
├── Any interconnect works
├── Cross-region even works (for global serving)
└── Rule: no topology constraint
```

### Topology-Aware Scheduling

```yaml
# Schedule tensor-parallel workload on NVLink-connected GPUs
apiVersion: v1
kind: Pod
metadata:
  name: llm-70b-tp4
  annotations:
    nvidia.com/gpu-topology: "nvlink"  # Require NVLink between GPUs
spec:
  containers:
  - name: vllm
    resources:
      requests:
        nvidia.com/gpu: 4
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: nvidia.com/gpu.interconnect
            operator: In
            values: ["nvlink"]
          - key: nvidia.com/gpu.count
            operator: Gt
            values: ["4"]  # Node must have 4+ GPUs
```

### Multi-Node GPU Topology

```
Single server (DGX A100):
├── 8 × A100-80GB
├── NVLink mesh: all-to-all 600 GB/s
├── Best for: single large model up to 8 GPUs
└── Cost: ~$200K purchase, ~$50/hr cloud

Multi-server cluster:
├── 4 × DGX A100 (32 GPUs total)
├── Intra-node: NVLink (600 GB/s)
├── Inter-node: InfiniBand HDR (200 Gb/s)
├── Best for: very large models (175B+) or high throughput
└── Scheduling: keep tensor-parallel within node, pipeline across nodes

Cloud topology:
├── Instance placement groups (GPUs on same rack)
├── Cluster networking (enhanced bandwidth between instances)
├── Zone affinity (same availability zone = lower latency)
└── Scheduling: request placement group for multi-GPU workloads
```

## Capacity Planning

### Calculating GPU Requirements

```
Formula:
  GPUs_needed = (peak_QPS × avg_tokens_per_request) / tokens_per_GPU_per_second

Example - Llama 70B serving:
  Peak QPS: 100 requests/second
  Avg tokens per request: 500 (input) + 200 (output) = 700
  Throughput per 4-GPU set: ~2000 output tokens/second
  
  GPU sets needed = 100 × 200 / 2000 = 10 sets = 40 GPUs at peak

  Add 30% headroom: 40 × 1.3 = 52 GPUs
  Add redundancy (N+1): 52 + 4 = 56 GPUs (14 sets, 1 spare set)

Cost:
  56 × A100 at $8/hr = $448/hr = $10,752/day = $322,560/month
  With reserved instances (40% savings): ~$193,536/month
  With spot for batch (separate): additional savings
```

### Time-of-Day Scaling

```
Traffic pattern (typical SaaS AI product):
  00:00-06:00: 10% of peak (night)     → 6 GPUs
  06:00-09:00: 40% of peak (morning)   → 22 GPUs
  09:00-12:00: 80% of peak (working)   → 42 GPUs
  12:00-14:00: 100% of peak (midday)   → 52 GPUs
  14:00-18:00: 90% of peak (afternoon) → 47 GPUs
  18:00-22:00: 50% of peak (evening)   → 27 GPUs
  22:00-00:00: 20% of peak (night)     → 12 GPUs

Average utilization: ~55% of peak
If you provision for peak 24/7: paying 45% extra
With auto-scaling: save ~40% of GPU costs
```

## Auto-Scaling for GPU Workloads

### Scale Metrics (NOT CPU)

```yaml
# WRONG: scaling on CPU utilization
# GPUs are the bottleneck, not CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-serving-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-serving
  minReplicas: 2
  maxReplicas: 20
  metrics:
  # RIGHT: scale on queue depth
  - type: External
    external:
      metric:
        name: inference_queue_depth
      target:
        type: AverageValue
        averageValue: "5"    # Scale up if >5 requests queued per replica
  
  # ALSO RIGHT: scale on GPU utilization
  - type: Pods
    pods:
      metric:
        name: gpu_utilization_percent
      target:
        type: AverageValue
        averageValue: "75"   # Scale up if GPU >75% utilized
  
  # ALSO: scale on latency
  - type: External
    external:
      metric:
        name: inference_latency_p95_ms
      target:
        type: Value
        value: "2000"        # Scale up if P95 > 2 seconds
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60    # Wait 1 min before scaling up
      policies:
      - type: Pods
        value: 2                         # Add max 2 pods at a time
        periodSeconds: 120               # Every 2 min
    scaleDown:
      stabilizationWindowSeconds: 300   # Wait 5 min before scaling down
      policies:
      - type: Pods
        value: 1                         # Remove max 1 pod at a time
        periodSeconds: 300               # Every 5 min
```

### Scale-Up Time Problem

```
Traditional web app scale-up: ~30 seconds
  ├── Launch container: 5s
  ├── Start application: 10s
  ├── Health check passes: 15s
  └── Receiving traffic: 30s

GPU model serving scale-up: 2-5 MINUTES
  ├── Find GPU node: 30-60s (if available)
  ├── Launch container: 10s
  ├── Download model weights: 30-120s (70B model = 140GB)
  ├── Load into GPU memory: 30-60s
  ├── Warmup inference: 10s
  ├── Health check passes: 10s
  └── Receiving traffic: 2-5 min total

Mitigation strategies:
  ├── Pre-warmed pool: keep N idle instances ready (expensive but instant)
  ├── Model caching: store weights on local NVMe (skip download: save 60-120s)
  ├── Predictive scaling: scale up BEFORE traffic arrives (based on schedule)
  └── Request queuing: buffer requests during scale-up (degrades latency)
```

### Pre-Warming Strategy

```yaml
# Keep minimum instances warm for instant response
warm_pool:
  strategy: "minimum_ready"
  config:
    min_ready_instances: 3          # Always 3 instances loaded and ready
    max_instances: 20               # Scale up to 20 during peak
    scale_to_zero: false            # NEVER scale below 3 in production
    
    # For dev/staging: scale to zero is OK
    # scale_to_zero: true
    # idle_timeout: 300              # Unload after 5 min idle

# Predictive pre-warming based on schedule
predictive_scaling:
  enabled: true
  schedule:
    - cron: "0 8 * * 1-5"          # Mon-Fri 8 AM
      target_replicas: 10           # Pre-warm for morning traffic
    - cron: "0 12 * * 1-5"         # Mon-Fri noon
      target_replicas: 15           # Pre-warm for peak
    - cron: "0 22 * * *"           # Every day 10 PM
      target_replicas: 3            # Scale down for night
```

## Cost Optimization

### Strategy Summary

```
Optimization                    | Savings | Complexity | Risk
-------------------------------|---------|------------|------
Reserved instances (1yr)        | 30-40%  | Low        | Low (commit)
Reserved instances (3yr)        | 50-60%  | Low        | Medium (long commit)
Spot for batch workloads        | 60-70%  | Medium     | Medium (interruption)
Time-of-day scaling             | 30-40%  | Medium     | Low
MIG for small models            | 50-85%  | Medium     | Low
Model quantization (INT8/INT4)  | 50%     | Medium     | Low (quality check)
LoRA consolidation              | 60-80%  | High       | Low
Scale-to-zero (dev/test)        | 90%+    | Low        | None (dev only)
```

### LoRA Adapter Consolidation

```
WITHOUT consolidation:
├── Customer A fine-tuned model: 1 GPU ($8/hr)
├── Customer B fine-tuned model: 1 GPU ($8/hr)
├── Customer C fine-tuned model: 1 GPU ($8/hr)
├── Customer D fine-tuned model: 1 GPU ($8/hr)
├── Customer E fine-tuned model: 1 GPU ($8/hr)
└── Total: 5 GPUs = $40/hr

WITH LoRA consolidation:
├── 1 base model loaded on 1 GPU
├── 5 LoRA adapters loaded (tiny: 10-50MB each)
├── Route request to correct adapter based on tenant
├── Swap adapter per-request (< 1ms overhead)
└── Total: 1 GPU = $8/hr (80% savings!)

Serving framework support:
├── vLLM: native LoRA serving (multiple adapters, single base)
├── TGI: LoRA adapter support
├── Triton: custom LoRA routing
└── All: S-LoRA paper implementation for 1000+ adapters
```

### Model Quantization

```
Full precision (FP16): 70B model = 140GB = 4× A100-40GB
INT8 quantization:     70B model = 70GB  = 2× A100-40GB (50% savings)
INT4 quantization:     70B model = 35GB  = 1× A100-40GB (75% savings)

Quality impact:
├── FP16 → INT8: typically < 1% quality loss
├── FP16 → INT4: typically 1-3% quality loss
├── GPTQ/AWQ: better quality than naive quantization
└── Always validate: run eval suite on quantized model

Cost comparison (serving 70B model):
├── FP16: 4 GPUs × $8/hr = $32/hr = $23,040/month
├── INT8: 2 GPUs × $8/hr = $16/hr = $11,520/month
├── INT4: 1 GPU × $8/hr = $8/hr = $5,760/month
└── Savings: 50-75% with quantization
```

## Monitoring GPU Resources

### Key Metrics

```yaml
gpu_metrics:
  utilization:
    - gpu_utilization_percent       # SM (compute) utilization
    - gpu_memory_used_bytes         # VRAM usage
    - gpu_memory_total_bytes        # Total VRAM
    - gpu_memory_utilization_percent
  
  performance:
    - gpu_temperature_celsius       # Throttling if > 80°C
    - gpu_power_draw_watts          # Approaching TDP = thermal limit
    - gpu_clock_speed_mhz           # Reduced = throttling
    - pcie_bandwidth_utilization    # Data transfer bottleneck
  
  inference:
    - tokens_per_second             # Throughput
    - batch_size_avg                # Batching efficiency
    - queue_depth                   # Backpressure indicator
    - time_to_first_token_ms       # User-perceived latency
    - inter_token_latency_ms       # Streaming smoothness
  
  scheduling:
    - gpu_allocation_ratio          # Allocated / Total GPUs
    - pending_gpu_requests          # Pods waiting for GPU
    - scheduling_latency_seconds    # Time to find GPU for pod
    - preemption_count              # Spot instance reclaims
```

## Key Takeaways

1. **GPUs are the critical resource — schedule based on queue depth, not CPU**
2. **MIG slicing: 7 small models on 1 GPU (massive cost savings for utilities)**
3. **Scale-up takes 2-5 min — pre-warm instances for latency-sensitive workloads**
4. **Topology matters: tensor parallelism needs NVLink, pipeline parallelism doesn't**
5. **LoRA consolidation: serve 5-100 fine-tuned models on 1 base model GPU**
6. **Quantization: 50-75% cost reduction with minimal quality impact**
7. **Spot instances: 60-70% savings for batch, but handle preemption gracefully**
8. **Capacity formula: peak_QPS × tokens / throughput_per_GPU = GPUs needed + 30% headroom**
