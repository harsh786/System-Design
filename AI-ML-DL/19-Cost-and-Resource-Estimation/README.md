# Cost & Resource Estimation for ML Systems

> What architects MUST know before starting any ML project.
> Get this wrong and you'll blow your budget or stall for weeks waiting on hardware.

---

## 1. GPU Memory Estimation Calculator

### Training Memory Formula

```
TOTAL GPU MEMORY (training) =
    Parameters + Gradients + Optimizer States + Activations + Overhead

┌─────────────────────────────────────────────────────────────────┐
│ Component          │ Formula                                     │
├────────────────────┼─────────────────────────────────────────────┤
│ Parameters         │ num_params × bytes_per_param                │
│   FP32             │ num_params × 4 bytes                        │
│   FP16/BF16        │ num_params × 2 bytes                        │
│   INT8             │ num_params × 1 byte                         │
├────────────────────┼─────────────────────────────────────────────┤
│ Gradients          │ Same size as parameters                     │
├────────────────────┼─────────────────────────────────────────────┤
│ Optimizer (Adam)   │ 2 × parameter size (momentum + variance)    │
│                    │ = num_params × 8 bytes (stored in FP32)     │
├────────────────────┼─────────────────────────────────────────────┤
│ Activations        │ batch × seq_len × hidden × num_layers × 2B │
│                    │ THIS IS THE DOMINANT FACTOR for large       │
│                    │ batches/sequences!                          │
├────────────────────┼─────────────────────────────────────────────┤
│ Overhead           │ ~10-20% of total (CUDA context, buffers)    │
└─────────────────────────────────────────────────────────────────┘
```

### Worked Examples

```
EXAMPLE 1: GPT-2 (124M params), batch=16, seq=1024
──────────────────────────────────────────────────
  Parameters:   124M × 4 bytes       = 496 MB
  Gradients:    124M × 4 bytes       = 496 MB
  Adam states:  124M × 8 bytes       = 992 MB
  Activations:  16 × 1024 × 768 × 12 × 2 ≈ 300 MB
  Overhead:     ~230 MB
  ─────────────────────────────────────────────
  TOTAL: ~2.5 GB  ✅ Fits on any modern GPU

EXAMPLE 2: LLaMA-7B, batch=1, seq=2048
──────────────────────────────────────────────────
  Parameters:   7B × 2 bytes (FP16)  = 14 GB
  Gradients:    7B × 2 bytes         = 14 GB
  Adam states:  7B × 8 bytes         = 56 GB  ← THIS kills you!
  Activations:  1 × 2048 × 4096 × 32 × 2 ≈ 500 MB
  Overhead:     ~8 GB
  ─────────────────────────────────────────────
  TOTAL: ~84 GB  ⚠️ Needs A100 80GB OR use FSDP/DeepSpeed

EXAMPLE 3: LLaMA-7B with LoRA (r=16)
──────────────────────────────────────────────────
  Base model (frozen): 7B × 2 bytes  = 14 GB
  LoRA trainable:      ~4M params
  Gradients:           4M × 4 bytes  = 16 MB
  Adam states:         4M × 8 bytes  = 32 MB
  Activations:         ~500 MB
  ─────────────────────────────────────────────
  TOTAL: ~16 GB  ✅ Fits on RTX 4090!

EXAMPLE 4: Inference Only (LLaMA-7B, INT8)
──────────────────────────────────────────────────
  Parameters:   7B × 1 byte          = 7 GB
  KV Cache:     batch × seq × heads × dim × layers × 2
                1 × 2048 × 32 × 128 × 32 × 2 ≈ 500 MB
  Overhead:     ~1 GB
  ─────────────────────────────────────────────
  TOTAL: ~8.5 GB  ✅ Fits on RTX 3080/4070!
```

### Quick Memory Estimation Rules

```
RULE OF THUMB:
- Full fine-tuning memory ≈ 16-20× model size (FP16 params)
- LoRA fine-tuning memory ≈ 1.2× model size
- Inference memory ≈ 1.2× model size (same precision)
- INT8 inference ≈ 0.6× FP16 model size
- INT4 inference ≈ 0.3× FP16 model size
```

---

## 2. Training Time Estimation

### Core Formula

```
Training Time = (dataset_size × epochs) / (throughput × num_gpus × efficiency)

Where:
  throughput = samples processed per second per GPU
  efficiency = multi-GPU scaling factor (0.85-0.95 for 2-8 GPUs)
```

### GPU Compute Capacity

```
| GPU      | FP32 TFLOPS | FP16 TFLOPS | Memory | Generation |
|----------|-------------|-------------|--------|------------|
| T4       | 8.1         | 65          | 16 GB  | Turing     |
| V100     | 15.7        | 125         | 16/32  | Volta      |
| A10G     | 31.2        | 125         | 24 GB  | Ampere     |
| A100     | 19.5        | 312         | 40/80  | Ampere     |
| H100     | 67          | 990         | 80 GB  | Hopper     |
```

### Benchmark Throughput Table

```
| Model              | GPU  | Batch | Throughput     | Time for 1M samples |
|--------------------|------|-------|----------------|---------------------|
| ResNet-50          | A100 | 256   | 3000 img/s     | 5.5 minutes         |
| ResNet-50          | V100 | 128   | 1200 img/s     | 14 minutes          |
| ResNet-50          | T4   | 64    | 450 img/s      | 37 minutes          |
| BERT-base finetune | A100 | 32    | 150 seq/s      | 1.8 hours           |
| BERT-base finetune | V100 | 16    | 60 seq/s       | 4.6 hours           |
| GPT-2 (124M)      | A100 | 8     | 25 seq/s       | 11 hours            |
| GPT-2 (124M)      | V100 | 4     | 10 seq/s       | 28 hours            |
| LLaMA-7B (LoRA)   | A100 | 4     | 3 seq/s        | 92 hours            |
| LLaMA-7B (LoRA)   | A10G | 2     | 1.5 seq/s      | 185 hours           |
| LLaMA-7B (full)   | 8×A100| 32   | 8 seq/s        | 35 hours            |
```

### Rules of Thumb

```
TRAINING TIME ESTIMATES:
─────────────────────────────────────────────────────
Task                          │ Hardware    │ Time
──────────────────────────────┼─────────────┼──────────
Fine-tune BERT on 100K        │ 1× A100    │ 1-3 hours
Fine-tune BERT on 1M          │ 1× A100    │ 6-12 hours
Train CNN from scratch (1M)   │ 1× A100    │ 1-3 days
Fine-tune 7B LoRA (100K)     │ 1× A100    │ 3-5 days
Train 7B from scratch         │ 8× A100    │ 2-4 weeks
Train 70B from scratch        │ 64× A100   │ 2-3 months
Train GPT-4 scale             │ 1000s GPUs │ months
─────────────────────────────────────────────────────

SPEEDUP TECHNIQUES:
- Mixed precision (FP16/BF16): 1.5-2× speedup
- Larger batch size: up to 2× (diminishing returns)
- Gradient accumulation: same as larger batch, no extra memory
- Data parallel (N GPUs): ~N× speedup (with 85-95% efficiency)
- Compiled model (torch.compile): 10-30% speedup
```

---

## 3. Cloud Cost Estimation

### AWS GPU Instances (us-east-1, approximate 2024 pricing)

```
| Instance          | GPU      | GPU Mem | vCPUs | $/hour | Spot $/hr |
|-------------------|----------|---------|-------|--------|-----------|
| g4dn.xlarge       | 1× T4   | 16 GB   | 4     | $0.53  | $0.16     |
| g5.xlarge         | 1× A10G | 24 GB   | 4     | $1.01  | $0.30     |
| g5.2xlarge        | 1× A10G | 24 GB   | 8     | $1.21  | $0.36     |
| p3.2xlarge        | 1× V100 | 16 GB   | 8     | $3.06  | $0.92     |
| p3.8xlarge        | 4× V100 | 64 GB   | 32    | $12.24 | $3.67     |
| p4d.24xlarge      | 8× A100 | 640 GB  | 96    | $32.77 | $9.83     |
| p5.48xlarge       | 8× H100 | 640 GB  | 192   | $98.32 | $29.50    |

SageMaker instances (add ~25-40% premium over EC2):
| ml.g4dn.xlarge    | 1× T4   | 16 GB   | 4     | $0.74  | $0.22     |
| ml.g5.xlarge      | 1× A10G | 24 GB   | 4     | $1.41  | $0.42     |
| ml.p3.2xlarge     | 1× V100 | 16 GB   | 8     | $3.83  | $1.15     |
| ml.p4d.24xlarge   | 8× A100 | 640 GB  | 96    | $40.97 | $12.29    |
```

### Real Project Cost Examples

```
EXAMPLE 1: Fine-tune BERT (3 hours on A10G)
  On-demand: 3 × $1.41 = $4.23
  Spot:      3 × $0.42 = $1.26

EXAMPLE 2: Train ResNet-50 (1 day on V100)
  On-demand: 24 × $3.83 = $92
  Spot:      24 × $1.15 = $28

EXAMPLE 3: Fine-tune 7B with LoRA (4 days on A100 80GB)
  On-demand: 96 × $32.77 = $3,146  (p4d has 8 GPUs but you need the memory)
  Spot:      96 × $9.83  = $944
  Better:    Use single A100 instance if available

EXAMPLE 4: Serve model 24/7 (T4, single instance)
  On-demand: 730 × $0.53 = $387/month
  With autoscaling (avg 12h/day): ~$194/month

EXAMPLE 5: Serve model serverless (1K requests/day)
  SageMaker Serverless: ~$5-15/month
  Lambda + small model:  ~$3-10/month

EXAMPLE 6: Full ML platform (team of 5)
  Training (sporadic):     ~$2,000/month
  Dev endpoints:           ~$800/month
  Production inference:    ~$1,500/month
  Storage (S3, models):    ~$200/month
  Other (monitoring, etc): ~$300/month
  ──────────────────────────────────────
  TOTAL:                   ~$4,800/month
```

### Cost Saving Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────┐
│ COST SAVING STRATEGIES (ordered by impact)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. USE SPOT INSTANCES FOR TRAINING              (70% savings)   │
│    - Checkpoint every 30 min                                    │
│    - Use SageMaker managed spot (handles interrupts)            │
│    - Accept 2-5% longer training due to interrupts              │
│                                                                 │
│ 2. RIGHT-SIZE YOUR GPU                          (50% savings)   │
│    - Don't use A100 when A10G works                             │
│    - Profile memory first, then pick GPU                        │
│    - Quantize model → use smaller GPU                           │
│                                                                 │
│ 3. SERVERLESS FOR LOW TRAFFIC                   (80% savings)   │
│    - <10K requests/day → serverless inference                   │
│    - Cold start OK? Use Lambda + ONNX                           │
│    - Scale-to-zero for dev/staging                              │
│                                                                 │
│ 4. AUTOSCALING + SCHEDULING                     (40% savings)   │
│    - Turn off dev/staging at night and weekends                 │
│    - Scale to 0 when no traffic                                 │
│    - Use scheduled scaling for predictable patterns             │
│                                                                 │
│ 5. MODEL OPTIMIZATION                          (30-60% savings) │
│    - Quantize (INT8): 2× cheaper inference GPU                  │
│    - Distillation: smaller model, same quality                  │
│    - TensorRT/ONNX: 2-3× throughput on same hardware            │
│    - Prune: remove unneeded weights                             │
│                                                                 │
│ 6. MULTI-MODEL ENDPOINTS                        (50% savings)   │
│    - Many low-traffic models on one GPU                         │
│    - SageMaker multi-model endpoint                             │
│    - Triton Inference Server with model switching               │
│                                                                 │
│ 7. RESERVED INSTANCES / SAVINGS PLANS           (30% savings)   │
│    - 1-year commitment for stable inference workloads           │
│    - Only for production endpoints you'll keep running          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Choosing the Right GPU

### Decision Tree

```
What are you doing?
│
├── INFERENCE ONLY
│   ├── Model < 500M params
│   │   ├── Latency critical (<50ms) → T4 with TensorRT
│   │   ├── Throughput critical → T4 or A10G with batching
│   │   └── Cost critical → CPU (ONNX Runtime)
│   ├── Model 1-7B params
│   │   ├── FP16 → A10G (24GB fits 7B)
│   │   ├── INT8 → T4 (16GB fits 7B quantized)
│   │   └── INT4 → T4 (fits 13B quantized!)
│   └── Model 13B+ params
│       ├── Single GPU → A100 40/80GB
│       └── Multi-GPU → Multiple A10G or A100s
│
├── FINE-TUNING
│   ├── Small model (BERT, ResNet) → A10G or V100
│   ├── Medium model (1-7B) with LoRA → A10G (24GB) or A100 (40GB)
│   ├── Medium model (1-7B) full fine-tune → A100 80GB or multi-GPU
│   ├── Large model (13-70B) with LoRA → A100 80GB
│   └── Large model (13-70B) full → Multiple A100s with FSDP
│
├── TRAINING FROM SCRATCH
│   ├── Small model (<1B) → A100 (fastest) or V100 (cheaper)
│   ├── Medium model (1-7B) → 4-8× A100
│   └── Large model (7B+) → 8-64× A100 or H100
│
└── NOT SURE → Start with A10G
    (Best price/performance, 24GB handles most tasks)
```

### GPU Selection Quick Reference

```
BUDGET TIERS:
─────────────────────────────────────────────
Budget Tier   │ GPU    │ Best For
──────────────┼────────┼─────────────────────
$0.50/hr      │ T4     │ Inference, small training
$1.00/hr      │ A10G   │ Fine-tuning, medium inference
$3.00/hr      │ V100   │ Training, multi-purpose
$30.00/hr     │ 8×A100 │ Large model training
$100.00/hr    │ 8×H100 │ Frontier model training
─────────────────────────────────────────────
```

---

## 5. Inference Sizing

### Latency-Based Selection

```
Latency Budget → Instance Selection:
─────────────────────────────────────────────────────────────────
p99 Target   │ Hardware          │ Notes
─────────────┼───────────────────┼───────────────────────────────
< 5ms        │ CPU + ONNX/tiny   │ Only for tiny models/lookups
< 10ms       │ CPU optimized     │ sklearn, small NNs, embeddings
< 50ms       │ T4/A10G + TensorRT│ Most production DL models
< 200ms      │ Any GPU           │ Even without optimization
< 500ms      │ CPU for medium    │ BERT on CPU with ONNX
< 1000ms     │ Serverless GPU    │ Cold-start acceptable
> 1000ms     │ Batch inference   │ Cheapest option
─────────────────────────────────────────────────────────────────
```

### Throughput-Based Scaling

```
QPS (Queries Per Second) → Architecture:
─────────────────────────────────────────────────────────────────
QPS Range    │ Architecture              │ Approximate Cost
─────────────┼───────────────────────────┼─────────────────────
< 1          │ Serverless / on-demand    │ $5-50/month
1-10         │ Single instance (GPU/CPU) │ $50-400/month
10-100       │ Single GPU + batching     │ $400-1000/month
100-1000     │ Multi-instance + LB       │ $1K-10K/month
1K-10K       │ + Caching layer           │ $5K-30K/month
10K+         │ Pre-compute + CDN + cache │ Custom architecture
─────────────────────────────────────────────────────────────────

HIGH-QPS STRATEGIES:
1. Cache predictions for repeated inputs (Redis)
2. Batch requests (dynamic batching in Triton)
3. Model distillation (smaller model, faster inference)
4. Pre-compute for known inputs (offline scoring)
5. Edge deployment (reduce network latency)
6. Request deduplication
```

### Autoscaling Configuration

```
RECOMMENDED AUTOSCALING SETTINGS:
─────────────────────────────────────────────────────
Metric                │ Target    │ Cooldown
──────────────────────┼───────────┼─────────────────
GPU Utilization       │ 60-70%    │ 300s scale-in
CPU Utilization       │ 70%       │ 300s scale-in
Invocations/instance  │ Model-dep │ 60s scale-out
Custom (queue depth)  │ < 10      │ 60s scale-out
─────────────────────────────────────────────────────

Min instances: 1 (production), 0 (dev/staging)
Max instances: Based on budget cap
Scale-out: Aggressive (1 min cooldown)
Scale-in: Conservative (5 min cooldown, avoid flapping)
```

---

## 6. Project Planning Template

```
┌─────────────────────────────────────────────────────────────────┐
│                    ML PROJECT COST ESTIMATE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ PROJECT: _____________________________________________           │
│ DATE: ____________  ESTIMATED BY: ___________________           │
│                                                                  │
│ ─── MODEL ───                                                    │
│ Architecture: ____________________  Params: _________           │
│ Precision: FP32 / FP16 / INT8 / INT4                            │
│ Model memory (inference): _______ GB                            │
│                                                                  │
│ ─── DATASET ───                                                  │
│ Training samples: _____________  Size on disk: _______          │
│ Validation samples: ___________                                  │
│ Features/preprocessing time: __________                          │
│                                                                  │
│ ─── TRAINING ───                                                 │
│ GPU type: ___________  Quantity: ___  Batch size: ____          │
│ Estimated epochs: ____  Est. time per epoch: _________          │
│ Total training time: ___________                                 │
│ Training cost (on-demand): $_________                           │
│ Training cost (spot):      $_________  ← USE THIS               │
│ Experiment budget (10× first run): $__________                  │
│                                                                  │
│ ─── INFERENCE ───                                                │
│ Expected QPS: ________  Latency target: _______ms               │
│ GPU type: ___________  Min instances: ___  Max: ___             │
│ Monthly inference cost: $_________                              │
│                                                                  │
│ ─── STORAGE & DATA ───                                           │
│ Model artifacts (S3): $________/month                           │
│ Training data storage: $________/month                          │
│ Feature store: $________/month                                  │
│                                                                  │
│ ─── TOTAL ───                                                    │
│ One-time training cost: $_________                              │
│ Monthly operational cost: $_________                            │
│ Annual estimate: $_________                                     │
│                                                                  │
│ ─── ASSUMPTIONS & RISKS ───                                      │
│ 1. ________________________________________________             │
│ 2. ________________________________________________             │
│ 3. ________________________________________________             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Common Mistakes in Cost Estimation

```
MISTAKE 1: Forgetting experiment costs
  Reality: You won't get it right first try.
  Budget: 5-10× your single training run cost for experiments.

MISTAKE 2: Ignoring data processing costs
  Reality: ETL, feature engineering, data validation take compute too.
  Budget: Add 20-30% for data pipeline compute.

MISTAKE 3: Underestimating inference costs
  Reality: Inference runs 24/7; training is one-time.
  A model that costs $100 to train might cost $500/month to serve.

MISTAKE 4: Not accounting for retraining
  Reality: Models need retraining (weekly/monthly).
  Budget: Monthly training cost = single run × retraining frequency.

MISTAKE 5: Forgetting monitoring and logging
  Reality: CloudWatch, experiment tracking, model registry cost money.
  Budget: Add $100-500/month for ML operations tooling.

MISTAKE 6: Optimistic GPU utilization
  Reality: You won't get 100% GPU utilization.
  Budget: Assume 60-70% effective utilization.
```

---

## 8. Cost Optimization Checklist

```
BEFORE TRAINING:
□ Profiled memory requirements (don't guess!)
□ Selected smallest GPU that fits
□ Configured spot instances with checkpointing
□ Set up early stopping
□ Using mixed precision (FP16/BF16)
□ Using gradient accumulation instead of larger GPU

BEFORE DEPLOYING INFERENCE:
□ Quantized model (INT8 minimum for production)
□ Benchmarked with TensorRT/ONNX
□ Configured autoscaling with scale-to-zero for non-prod
□ Set budget alerts (50%, 80%, 100% thresholds)
□ Evaluated serverless option for low traffic
□ Considered multi-model endpoint

ONGOING:
□ Monthly cost review
□ GPU utilization check (if <50%, downsize)
□ Spot interrupt rate acceptable?
□ Any endpoints running with zero traffic?
□ Can we distill/compress the model further?
```
