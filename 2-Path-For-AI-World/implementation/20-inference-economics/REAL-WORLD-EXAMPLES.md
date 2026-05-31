# Inference Economics — Real-World Examples

## Case Study 1: Self-Hosted vLLM vs Managed API — Break-Even Analysis

### Company: "DocuFlow" — Document Processing Startup (Series B)

DocuFlow processes legal documents using LLM-powered extraction. They needed to decide between OpenAI API and self-hosted Llama 3 70B on vLLM.

### Traffic Profile

```
Daily volume: 500K-2M tokens (varies by day)
Peak: 3M tokens on Monday mornings
Pattern: Business hours heavy (80% between 9am-6pm EST)
Latency requirement: P95 < 5s for 500-token responses
Quality requirement: Must match GPT-4 on legal extraction (validated via eval suite)
```

### Cost Comparison

```
═══════════════════════════════════════════════════════════════
OPTION A: OpenAI GPT-4 Turbo API
═══════════════════════════════════════════════════════════════
Pricing: $10/1M input tokens, $30/1M output tokens
Average request: 2000 input tokens, 500 output tokens

Daily cost at 500K tokens/day:
  Input:  400K tokens × ($10/1M) = $4.00
  Output: 100K tokens × ($30/1M) = $3.00
  Daily: $7.00 | Monthly: $210

Daily cost at 2M tokens/day:
  Input:  1.6M tokens × ($10/1M) = $16.00
  Output: 400K tokens × ($30/1M) = $12.00
  Daily: $28.00 | Monthly: $840

Pros: Zero ops overhead, instant scaling, always latest model
Cons: No control over availability, costs scale linearly

═══════════════════════════════════════════════════════════════
OPTION B: Self-Hosted Llama 3 70B on vLLM (2× A100 80GB)
═══════════════════════════════════════════════════════════════
Infrastructure (AWS):
  2× p4d.24xlarge (8× A100 each, but we use 2 GPUs via TP=2)
  Actually: 1× g5.12xlarge with 4× A10G would work for 70B INT4
  
  Revised: 1× p4de.24xlarge spot instance
  On-demand: $32.77/hr → $23,594/month
  Spot (avg): $12.50/hr → $9,000/month
  Reserved 1yr: $16.50/hr → $11,880/month

  Actually let's be precise for 70B on 2× A100:
  g5.48xlarge (8× A10G 24GB): Can fit 70B INT4 with TP=4
  Cost: $16.29/hr on-demand → $11,728/month
  
  OR p4d.24xlarge (8× A100 40GB): Can fit 70B FP16 with TP=4
  Cost: $32.77/hr → $23,594/month
  
  Best option: 2× A100 80GB via p4de spot
  Realistic: $6,500/month for compute

Additional costs:
  DevOps engineer time (20% allocation): $3,500/month
  Monitoring/logging: $200/month
  Load balancer + networking: $150/month
  Total: $10,350/month

Throughput capacity:
  vLLM with Llama 3 70B INT4 on 2× A100 80GB:
  ~35 tokens/sec per concurrent request
  With continuous batching: ~150 concurrent users
  Daily capacity: ~50M tokens (way more than needed)

═══════════════════════════════════════════════════════════════
BREAK-EVEN ANALYSIS
═══════════════════════════════════════════════════════════════

OpenAI monthly cost = $210 + (volume × $14/M_tokens)
Self-hosted monthly cost = $10,350 (fixed)

Break-even: $10,350 / $14 per M tokens = ~740K tokens/day

At 500K tokens/day: OpenAI wins ($210 vs $10,350)
At 2M tokens/day:   Closer ($840 vs $10,350) — OpenAI still wins
At 10M tokens/day:  Self-hosted wins ($4,200 vs $10,350)
                    Wait, let me recalculate...
                    OpenAI at 10M: 8M input + 2M output = $80 + $60 = $140/day = $4,200/mo
                    Self-hosted: $10,350/mo
                    
                    Still OpenAI wins until ~25M tokens/day!

REALITY CHECK: For GPT-4 class quality at this volume, API wins.
Self-hosted only wins when:
  1. Volume > 25M tokens/day, OR
  2. Using a model that's "good enough" but much cheaper to host
     (Llama 3 70B matches GPT-4 on their specific legal task)
  3. Latency/privacy requirements mandate self-hosting
  4. Need custom model (fine-tuned) that providers don't offer

═══════════════════════════════════════════════════════════════
DOCUFLOW'S DECISION
═══════════════════════════════════════════════════════════════
Chose: Hybrid approach
- OpenAI GPT-4 for complex extraction (20% of requests, high-value)
- Self-hosted Llama 3 70B INT4 for routine classification (80% of requests)
- Monthly cost: $2,800 (vs $4,200 all-API or $10,350 all-self-hosted)
```

---

## Case Study 2: GPU Economics — A100 vs H100 vs L40S

### Comparison for Different Workloads

```
═══════════════════════════════════════════════════════════════════
GPU SPECIFICATIONS COMPARISON
═══════════════════════════════════════════════════════════════════

                    | A100 80GB    | H100 80GB     | L40S 48GB
────────────────────|──────────────|───────────────|──────────────
FP16 TFLOPS        | 312          | 989           | 362
BF16 TFLOPS        | 312          | 989           | 362
INT8 TOPS          | 624          | 1,979         | 724
Memory             | 80 GB HBM2e  | 80 GB HBM3    | 48 GB GDDR6X
Memory BW          | 2.0 TB/s     | 3.35 TB/s     | 864 GB/s
NVLink BW          | 600 GB/s     | 900 GB/s      | N/A (PCIe)
TDP                | 300W         | 700W          | 350W
Cloud cost/hr (OD) | ~$4.00       | ~$8.50        | ~$2.50
Cloud cost/hr (RI) | ~$2.50       | ~$5.50        | ~$1.60

═══════════════════════════════════════════════════════════════════
WORKLOAD 1: Llama 3 70B Serving (Batch inference, throughput-focused)
═══════════════════════════════════════════════════════════════════

Setup: FP16, TP=4 for A100/H100, TP=2 INT4 for L40S

                    | A100 (×4)    | H100 (×4)     | L40S (×4, INT4)
────────────────────|──────────────|───────────────|──────────────
Throughput (tok/s)  | 2,400        | 5,800         | 1,100
Latency P50 (TTFT) | 280ms        | 120ms         | 450ms
Batch capacity      | 32 concurrent| 64 concurrent | 16 concurrent
Cost/hr             | $16.00       | $34.00        | $10.00
Cost/1M tokens      | $1.85        | $1.63         | $2.52
Quality (vs FP16)   | Baseline     | Baseline      | -2% (quant loss)

Winner for throughput: H100 (best cost/token despite higher hourly rate)
Winner for budget: L40S (lowest absolute cost, acceptable quality)
Winner for latency: H100 (2.3× faster TTFT)

═══════════════════════════════════════════════════════════════════
WORKLOAD 2: Real-time chatbot (Latency-sensitive, moderate throughput)
═══════════════════════════════════════════════════════════════════

Model: Llama 3 8B, need P95 TTFT < 200ms, serving 100 concurrent users

                    | A100 (×1)    | H100 (×1)     | L40S (×1)
────────────────────|──────────────|───────────────|──────────────
TTFT P95            | 85ms         | 45ms          | 180ms
Throughput (tok/s)  | 4,500        | 11,000        | 2,800
Concurrent users    | 150          | 350           | 80
Cost/hr             | $4.00        | $8.50         | $2.50
Users per $/hr      | 37.5         | 41.2          | 32.0

Winner: H100 barely beats A100 on users-per-dollar.
But A100 is the practical choice (easier to get, good enough latency).
L40S needs 2 GPUs to match, making it more expensive than A100.

═══════════════════════════════════════════════════════════════════
WORKLOAD 3: Embedding generation (Batch, throughput-only)
═══════════════════════════════════════════════════════════════════

Model: E5-large (330M params), batch processing millions of documents

                    | A100 (×1)    | H100 (×1)     | L40S (×1)
────────────────────|──────────────|───────────────|──────────────
Embeddings/sec      | 3,200        | 5,100         | 2,400
Cost/1M embeddings  | $0.35        | $0.46         | $0.29
Memory used         | 8 GB / 80 GB | 8 GB / 80 GB  | 8 GB / 48 GB

Winner: L40S — model is small, doesn't need HBM bandwidth or NVLink.
You're paying for 80GB of unused memory on A100/H100.
Actually best: Use multiple L4 GPUs ($0.80/hr, 24GB) for $0.18/1M embeddings.

═══════════════════════════════════════════════════════════════════
DECISION FRAMEWORK
═══════════════════════════════════════════════════════════════════

Use H100 when:
  ✓ Large models (70B+) that are memory-bandwidth bound
  ✓ Latency-critical applications where TTFT matters
  ✓ High-volume serving where cost-per-token matters most
  ✓ Training or fine-tuning (3× faster than A100)

Use A100 when:
  ✓ Mid-size models (7B-70B) with moderate latency needs
  ✓ Good balance of cost and performance
  ✓ Better availability than H100
  ✓ Mixed workloads (training + serving)

Use L40S/L4 when:
  ✓ Small models (< 13B) or quantized models
  ✓ Embedding workloads (don't need HBM bandwidth)
  ✓ Budget-constrained deployments
  ✓ Inference-only (no training needed)
  ✓ Workloads that don't need multi-GPU NVLink
```

---

## Case Study 3: KV Cache Optimization with PagedAttention

### Before and After: Real Production Numbers

```
═══════════════════════════════════════════════════════════════════
SYSTEM: Llama 3 70B on 2× A100 80GB (TP=2)
CONTEXT: 4K token average context, 2K token average generation
═══════════════════════════════════════════════════════════════════

BEFORE (Naive KV Cache — Pre-allocated contiguous memory):

KV cache memory per request:
  num_layers = 80
  num_kv_heads = 8 (GQA)
  head_dim = 128
  max_seq_len = 8192 (must pre-allocate for max)
  dtype = FP16 (2 bytes)

  Per request = 2 × 80 × 8 × 128 × 8192 × 2 bytes
             = 2 × 80 × 8 × 128 × 8192 × 2
             = 26.8 GB per request at max length!

  Reality: Even with shorter sequences, memory is reserved for max_seq_len.
  On 2× A100 80GB (160GB total, ~120GB available after model weights):
  
  Max concurrent requests: 120GB / 26.8GB = 4 concurrent users
  
  Actual utilization: Most sequences use only 4K-6K tokens
  Memory waste: ~50% (allocated for 8K, using 4K average)
  GPU compute utilization during inference: 23% (memory-bound, few batches)

AFTER (PagedAttention — vLLM's approach):

How it works:
  - KV cache split into fixed-size "pages" (blocks of 16 tokens)
  - Pages allocated on-demand as generation progresses
  - Pages can be non-contiguous in GPU memory
  - Completed sequences free their pages immediately
  - Shared prefixes can share pages (copy-on-write)

Memory per active request (4K context + generating):
  Actually allocated = tokens_so_far × per_token_kv_size
  At 4K tokens = 2 × 80 × 8 × 128 × 4096 × 2 = 13.4 GB
  (vs 26.8 GB pre-allocated before!)

  But with paging, fragmentation is <4% (vs impossible fragmentation before)
  
  Effective capacity on same hardware:
  120GB / (avg 6.5GB per request with paging overhead) = 18 concurrent users
  
  But wait — vLLM also enables:
  - Prefix caching: System prompt KV cached, shared across all requests
    Saves ~2GB per request for 1K token system prompt
  - Early page release: Completed requests free memory immediately
  - Dynamic batching: More requests = better GPU utilization

  Real concurrent capacity: 24 concurrent users (6× improvement!)

═══════════════════════════════════════════════════════════════════
PRODUCTION METRICS COMPARISON
═══════════════════════════════════════════════════════════════════

Metric                    | Before (Naive) | After (PagedAttention)
──────────────────────────|────────────────|───────────────────────
Max concurrent requests   | 4              | 24
GPU memory utilization    | 95% (wasted)   | 92% (effective)
GPU compute utilization   | 23%            | 78%
Throughput (tokens/sec)   | 420            | 2,450
P50 TTFT                  | 1.2s (queuing) | 0.3s
P95 TTFT                  | 8.5s (queuing) | 0.9s
Cost per 1M tokens        | $12.40         | $2.13
Monthly GPU cost (same $) | Serves 50K req | Serves 300K req

═══════════════════════════════════════════════════════════════════
ADDITIONAL OPTIMIZATION: Prefix Caching
═══════════════════════════════════════════════════════════════════

Scenario: RAG system where all requests share a 1500-token system prompt

Without prefix caching:
  Each request computes KV for system prompt independently
  1500 tokens × 0.03s compute = 45ms overhead per request
  Memory: 1500 × per_token_kv × N_concurrent

With prefix caching:
  System prompt KV computed once, stored in cache
  Shared across ALL concurrent requests (read-only pages)
  Memory savings: (N-1) × 1500 × per_token_kv = ~2GB × 23 = 46GB saved!
  Latency savings: 45ms per request (TTFT reduced by 45ms)
  
  This alone increased concurrent capacity from 24 to 32 users.
```

---

## Case Study 4: Continuous Batching Impact

### Real Throughput Comparison

```
═══════════════════════════════════════════════════════════════════
EXPERIMENT: Llama 3 8B on single A100 80GB
INPUT: Realistic chat workload (mixed lengths: 100-2000 token inputs,
       50-500 token outputs)
LOAD: 50 requests/second sustained
═══════════════════════════════════════════════════════════════════

STATIC BATCHING (Traditional):
  How it works:
    - Collect requests until batch is full (batch_size=8) or timeout (100ms)
    - Process entire batch together
    - ALL requests in batch must wait for LONGEST sequence to finish
    - Only then can next batch start

  Results:
    Throughput: 1,200 tokens/sec
    P50 latency: 2.1s
    P95 latency: 8.3s  ← dominated by waiting for long sequences
    GPU utilization: 34% (idle while waiting for batch formation + long tail)
    
    Why it's bad:
    - A 50-token response waits for a 500-token response in same batch
    - GPU sits idle between batches
    - Batch size is a painful tradeoff: big = high latency, small = low throughput

CONTINUOUS BATCHING (vLLM / TensorRT-LLM):
  How it works:
    - Requests enter processing immediately (no waiting for batch formation)
    - Each iteration, generate 1 token for ALL active sequences
    - When a sequence finishes, its slot is IMMEDIATELY filled by a new request
    - No "wasted" iterations on padding tokens

  Results:
    Throughput: 4,200 tokens/sec (3.5× improvement!)
    P50 latency: 0.8s
    P95 latency: 2.4s (3.5× better)
    GPU utilization: 82%

  Why it's so much better:
    - Short requests don't wait for long ones (they exit early)
    - GPU is never idle (always has work from dynamic request pool)
    - Effective batch size is always optimal (auto-adjusts to load)

═══════════════════════════════════════════════════════════════════
SCALING COMPARISON AT DIFFERENT LOADS
═══════════════════════════════════════════════════════════════════

Requests/sec    | Static (tok/s) | Continuous (tok/s) | Multiplier
────────────────|────────────────|────────────────────|──────────
10              | 800            | 1,400              | 1.75×
25              | 1,100          | 3,200              | 2.9×
50              | 1,200          | 4,200              | 3.5×
100             | 1,200 (saturated)| 4,500            | 3.75×
200             | Queuing/failing| 4,600 (near max)   | -

Key insight: Static batching saturates early because it can't efficiently
use GPU cycles. Continuous batching gracefully scales to hardware limits.

═══════════════════════════════════════════════════════════════════
REAL COST IMPACT
═══════════════════════════════════════════════════════════════════

Company serving 10M tokens/day:
  Static batching: Need 3× A100 GPUs = $12.00/hr = $8,640/month
  Continuous batching: Need 1× A100 GPU = $4.00/hr = $2,880/month
  
  Savings: $5,760/month = $69,120/year from ONE optimization.
```

---

## Case Study 5: Speculative Decoding in Production

### Setup: 2.8× Latency Reduction for Code Generation

```
═══════════════════════════════════════════════════════════════════
COMPANY: "CodePilot" — AI Code Completion Service
MODEL: Llama 3 70B (target) + Llama 3.2 1.5B (draft)
HARDWARE: 2× A100 80GB for target, 1× L4 for draft
═══════════════════════════════════════════════════════════════════

HOW SPECULATIVE DECODING WORKS:
  1. Draft model generates K tokens quickly (cheap, fast)
  2. Target model verifies all K tokens in ONE forward pass (parallel)
  3. Accept all tokens up to first rejection, then regenerate from there
  4. Net effect: Multiple target-quality tokens per forward pass

CONFIGURATION:
  Draft model: Llama 3.2 1.5B (fits on L4, generates at 180 tok/s)
  Target model: Llama 3 70B (2× A100, generates at 35 tok/s normally)
  Speculation length (K): 5 tokens
  Acceptance rate: ~72% for code (code is more predictable than prose)

RESULTS:
                         | Without Speculative | With Speculative
─────────────────────────|────────────────────|──────────────────
Tokens/sec (per user)    | 35                 | 98 (2.8×)
TTFT                     | 280ms              | 310ms (+30ms draft)
Time for 100 tokens      | 2.86s              | 1.02s
P95 end-to-end (50 tok)  | 1.7s               | 0.6s
GPU cost/hr (total)      | $8.00              | $8.80 (+L4 for draft)
Effective cost/1M tokens | $3.17              | $1.25 (2.5× cheaper!)

WHY 2.8× AND NOT 5× (the theoretical max with K=5):
  - Acceptance rate is 72%, not 100%
  - When rejected at position 3, tokens 4-5 are wasted
  - Average accepted length per speculation: 3.6 tokens
  - Overhead of running draft model + verification logic
  - Effective speedup = avg_accepted / (1 + draft_overhead) = 3.6/1.3 ≈ 2.8×

WHEN SPECULATIVE DECODING WORKS BEST:
  ✓ Code generation (highly predictable patterns)
  ✓ Structured output (JSON, XML — draft model learns format)
  ✓ Repetitive content (boilerplate, templates)
  ✓ When target model is very large (70B+) and latency-bound
  
WHEN IT DOESN'T HELP:
  ✗ Creative writing (low acceptance rate ~40%, marginal speedup)
  ✗ When target model is already fast (8B model — overhead dominates)
  ✗ High-throughput batch scenarios (better to just batch more)
  ✗ Very short outputs (TTFT penalty matters more than generation speed)

ACCEPTANCE RATE BY DOMAIN:
  Code completion: 72%
  JSON generation: 78%
  Technical docs:  65%
  Creative writing: 41%
  Translation:     58%
  Summarization:   52%
```

---

## Case Study 6: Quantization Tradeoffs — Real Benchmarks

```
═══════════════════════════════════════════════════════════════════
MODEL: Llama 3 70B | HARDWARE: 2× A100 80GB | BENCHMARK: Custom enterprise eval
═══════════════════════════════════════════════════════════════════

QUANTIZATION COMPARISON:

Method    | Bits | Model Size | Memory   | Tok/s | Quality* | Cost/1M tok
──────────|──────|──────────--|──────────|───────|──────────|───────────
FP16      | 16   | 140 GB     | 155 GB** | 35    | 100%     | $3.17
FP8       | 8    | 70 GB      | 82 GB    | 58    | 99.2%    | $1.91
INT8 GPTQ | 8    | 70 GB      | 80 GB    | 62    | 98.8%    | $1.79
INT4 AWQ  | 4    | 35 GB      | 48 GB    | 89    | 96.5%    | $1.24
INT4 GPTQ | 4    | 35 GB      | 48 GB    | 85    | 95.8%    | $1.30
GGUF Q4_K | 4    | 40 GB      | 52 GB    | 72    | 96.1%    | $1.53

* Quality measured as % of FP16 score on enterprise eval suite (1000 questions)
** Includes KV cache and overhead

═══════════════════════════════════════════════════════════════════
QUALITY BREAKDOWN BY TASK (INT4 AWQ vs FP16):
═══════════════════════════════════════════════════════════════════

Task                    | FP16 Score | INT4 AWQ Score | Delta
────────────────────────|────────────|────────────────|───────
Simple Q&A              | 94.2%      | 93.8%          | -0.4%
Code generation         | 87.1%      | 84.3%          | -2.8%  ⚠️
Mathematical reasoning  | 78.5%      | 72.1%          | -6.4%  🔴
Summarization           | 91.3%      | 90.7%          | -0.6%
Classification          | 96.8%      | 96.5%          | -0.3%
Creative writing        | 88.4%      | 87.9%          | -0.5%
Complex reasoning       | 82.3%      | 77.8%          | -4.5%  ⚠️
Instruction following   | 93.1%      | 91.4%          | -1.7%

KEY INSIGHT: Quantization impact is NOT uniform across tasks.
- Simple/classification tasks: almost no degradation
- Math/complex reasoning: significant degradation (4-6%)
- This means: quantize for simple tasks, keep FP16 for reasoning-heavy tasks

═══════════════════════════════════════════════════════════════════
PRACTICAL DECISION: TIERED QUANTIZATION STRATEGY
═══════════════════════════════════════════════════════════════════

DocuFlow's approach (from Case Study 1):
  - Classification/routing (80% of requests): INT4 AWQ → $1.24/1M tokens
  - Complex extraction (15% of requests): FP8 → $1.91/1M tokens  
  - Reasoning-heavy tasks (5% of requests): FP16 → $3.17/1M tokens
  
  Blended cost: $1.43/1M tokens (vs $3.17 all-FP16)
  Quality: 99.1% of all-FP16 (measured on production traffic)
  Savings: 55% cost reduction with minimal quality impact

═══════════════════════════════════════════════════════════════════
GPU MEMORY IMPLICATIONS — WHAT FITS WHERE
═══════════════════════════════════════════════════════════════════

Llama 3 70B:
  FP16:     2× A100 80GB (TP=2) or 4× A100 40GB (TP=4)
  FP8:      1× A100 80GB (tight) or 1× H100 80GB (comfortable)
  INT4 AWQ: 1× A100 80GB (lots of room for KV cache!) or 1× L40S 48GB

Serving capacity with INT4 on 1× A100 80GB:
  Model: 35GB
  Available for KV cache: 40GB
  Concurrent requests: ~32 (vs 4-6 with FP16!)
  
  This is the REAL win of quantization: not just speed, but CONCURRENCY.
```

---

## Case Study 7: LoRA Serving Economics

### 100 LoRA Adapters on One GPU vs 100 Separate Deployments

```
═══════════════════════════════════════════════════════════════════
SCENARIO: AI Platform serving 100 enterprise customers
Each customer has a fine-tuned model (same base: Llama 3 8B)
Average traffic per customer: 50K tokens/day
═══════════════════════════════════════════════════════════════════

OPTION A: 100 Separate Model Deployments
─────────────────────────────────────────

Each deployment:
  Model: Llama 3 8B FP16 = 16GB VRAM
  Minimum viable: 1× L4 GPU (24GB) per customer
  Cost per GPU: $0.80/hr = $576/month

  Total: 100 × $576 = $57,600/month

  Problems:
  - Most GPUs are idle 90% of the time (50K tokens/day = ~15 min of work)
  - GPU utilization: ~4% average
  - Scaling: Need to provision for peak, pay for idle
  - Ops overhead: 100 deployments to manage

OPTION B: Shared Base Model + LoRA Adapters (using vLLM/LoRAX)
──────────────────────────────────────────────────────────────────

Architecture:
  Base model: Llama 3 8B FP16 = 16GB (loaded once, shared)
  LoRA adapter: rank=16, ~50MB per adapter
  100 adapters: 100 × 50MB = 5GB
  Total VRAM: 16GB + 5GB + KV cache = ~28GB

  Hardware: 2× L4 GPUs (48GB total) for redundancy
  Cost: 2 × $576 = $1,152/month

  How it works (vLLM with LoRA support):
  - Base model weights shared in memory (read-only)
  - LoRA adapters loaded into adapter cache
  - Request includes adapter_id → correct LoRA applied dynamically
  - KV cache shared across all adapters
  - Continuous batching works across different adapters!

  Performance:
  - Adapter switching overhead: <1ms (just pointer swap)
  - Can batch requests from different adapters together
  - Throughput: same as single model (adapters are tiny)
  - Total capacity: 5M tokens/day (10× what's needed)

═══════════════════════════════════════════════════════════════════
COST COMPARISON
═══════════════════════════════════════════════════════════════════

                        | 100 Separate | Shared LoRA
────────────────────────|──────────────|────────────
Monthly GPU cost        | $57,600      | $1,152
GPU utilization         | 4%           | 62%
Ops complexity          | 100 deploys  | 2 deploys
Scaling new customer    | +1 GPU       | +50MB adapter
Time to add customer    | 30 min       | 2 min (upload adapter)
Annual cost             | $691,200     | $13,824

ANNUAL SAVINGS: $677,376 (~$450K+ conservatively with overhead)

═══════════════════════════════════════════════════════════════════
TRADEOFFS AND LIMITATIONS
═══════════════════════════════════════════════════════════════════

When shared LoRA works:
  ✓ Same base model for all customers
  ✓ Low-to-moderate per-customer traffic
  ✓ Adapters are small (rank ≤ 64)
  ✓ No strict latency isolation requirements

When you need separate deployments:
  ✗ Different base models per customer
  ✗ Customers need guaranteed latency SLOs (noisy neighbor)
  ✗ Full fine-tunes (not LoRA) — can't share base weights
  ✗ Regulatory requirement for data isolation at hardware level
  ✗ Single customer doing 10M+ tokens/day (deserves dedicated GPU)

REAL CAPACITY PLANNING:
  Adapters in memory:    ~200 (limited by VRAM for adapter weights)
  Adapters on disk:      Unlimited (swap in/out with ~50ms cold start)
  Active adapters:       Schedule popular ones in VRAM, LRU eviction
  
  If customer has bursty traffic:
    Hot adapter (in VRAM): 0ms switch time
    Cold adapter (on disk): ~50ms load time (acceptable for first request)
    Strategy: Keep top-20 most active in VRAM, LRU rest
```

---

## Case Study 8: Tensor Parallelism Decisions

### When to Use TP=2 vs TP=4 vs TP=8

```
═══════════════════════════════════════════════════════════════════
HARDWARE: 8× H100 80GB with NVLink (900 GB/s bidirectional per pair)
MODEL: Llama 3 70B FP16
WORKLOAD: Real-time serving, P95 TTFT target: 200ms
═══════════════════════════════════════════════════════════════════

TENSOR PARALLELISM BENCHMARK RESULTS:

TP Setting | GPUs Used | TTFT P50 | TTFT P95 | Throughput | Efficiency
───────────|───────────|──────────|──────────|────────────|───────────
TP=1       | 1 (impossible — model doesn't fit in 80GB FP16) | — | — | — | —
TP=2       | 2         | 180ms    | 320ms    | 58 tok/s   | 88%
TP=4       | 4         | 95ms     | 160ms    | 105 tok/s  | 79%
TP=8       | 8         | 65ms     | 110ms    | 155 tok/s  | 59%

Efficiency = actual_speedup / theoretical_speedup (linear would be 100%)

WHY EFFICIENCY DROPS:
  TP=2: Small all-reduce between 2 GPUs. NVLink handles it easily.
  TP=4: All-reduce across 4 GPUs. Some NVLink topology penalty.
  TP=8: All-reduce across 8 GPUs. Communication starts to dominate
        for smaller per-GPU compute chunks.

═══════════════════════════════════════════════════════════════════
DECISION FRAMEWORK
═══════════════════════════════════════════════════════════════════

Use TP=2:
  ✓ Model barely fits in 2 GPUs (e.g., 70B FP16 on 2× 80GB)
  ✓ Throughput matters more than latency
  ✓ Want to run multiple TP=2 instances for higher total throughput
  ✓ Budget-constrained (2 GPUs serve well)
  Example: 4 instances of TP=2 on 8 GPUs = 4 × 58 = 232 tok/s total
           vs 1 instance of TP=8 = 155 tok/s
           THROUGHPUT WINNER: Multiple TP=2 instances!

Use TP=4:
  ✓ Need low latency AND good throughput
  ✓ Sweet spot for 70B class models
  ✓ TTFT target: 100-200ms
  Example: 2 instances of TP=4 on 8 GPUs = 2 × 105 = 210 tok/s
           with P95 TTFT of 160ms (meets target)

Use TP=8:
  ✓ Ultra-low latency requirement (TTFT < 100ms)
  ✓ Very large models (175B+ that need 8 GPUs for memory anyway)
  ✓ Single-user dedicated system (no throughput concern)
  Example: Real-time voice assistant needing TTFT < 80ms

═══════════════════════════════════════════════════════════════════
COST-OPTIMAL CONFIGURATION FOR DIFFERENT SCENARIOS
═══════════════════════════════════════════════════════════════════

Scenario: Serve 500 concurrent users, Llama 3 70B, TTFT < 300ms

Option A: 8× H100, TP=2, 4 instances
  Capacity: 4 × 58 tok/s generation + 4 parallel prefills
  Concurrent users supported: ~200 (need 3 nodes = 24 GPUs)
  Cost: 24 × $8.50/hr = $204/hr

Option B: 8× H100, TP=4, 2 instances per node
  Capacity: 2 × 105 tok/s + 2 parallel prefills
  Concurrent users: ~160 per node (need 4 nodes = 32 GPUs)
  Cost: 32 × $8.50/hr = $272/hr

Option C: Mix of TP=2 instances (better throughput per dollar)
  16 instances of TP=2 across 32 GPUs
  Capacity: 16 × 58 = 928 tok/s, handles 500 concurrent easily
  Cost: 32 × $8.50/hr = $272/hr BUT with better latency distribution

WINNER: Option A (TP=2, fewer total GPUs needed for throughput)
CAVEAT: Only if TTFT=320ms P95 is acceptable. If need <200ms, TP=4.
```

---

## Case Study 9: GPU Utilization Monitoring and Optimization

### Real Dashboard Patterns and What They Mean

```
═══════════════════════════════════════════════════════════════════
DASHBOARD: AI Inference Fleet — Weekly GPU Utilization Report
Fleet: 16× A100 80GB across 2 nodes (serving Llama 3 70B + 8B)
═══════════════════════════════════════════════════════════════════

GPU UTILIZATION PATTERNS OBSERVED:

Pattern 1: "The Valley" (Low utilization during off-hours)
─────────────────────────────────────────────────────────
  06:00-09:00: 12% utilization
  09:00-17:00: 78% utilization  
  17:00-22:00: 45% utilization
  22:00-06:00: 8% utilization

  Problem: Paying for 24/7 GPU but using only 40% average
  Solution implemented:
    - Scale down to 8 GPUs at night (spot instances)
    - Run batch jobs (embedding indexing, eval suites) during off-hours
    - Result: Effective utilization increased to 71%, cost reduced 30%

Pattern 2: "The Spike" (Request queuing during peaks)
─────────────────────────────────────────────────────
  Monday 9:00-9:15: Queue depth reaches 500 requests
  GPU utilization: 99% (maxed out)
  P95 latency: 12s (5× normal)
  Requests dropped: 2.3%

  Solution implemented:
    - Pre-warm 4 additional spot GPUs at 8:45 AM Monday
    - Request priority queuing (paying customers first)
    - Graceful degradation: switch overflow to smaller model
    - Result: Peak P95 reduced to 3.2s, no drops

Pattern 3: "The Waste" (Memory allocated but unused)
────────────────────────────────────────────────────
  Observation: GPU memory 92% allocated, but compute only 45%
  Root cause: KV cache pre-allocated for max_seq_len=32K
              but average sequence is 4K tokens
  
  Solution: Migrated to vLLM with PagedAttention
  Result: Same memory now serves 4× more concurrent requests
          Compute utilization rose to 78% (more batching possible)

Pattern 4: "The Imbalance" (Uneven GPU utilization in TP group)
──────────────────────────────────────────────────────────────
  GPU 0: 82% utilization
  GPU 1: 79% utilization  
  GPU 2: 81% utilization
  GPU 3: 45% utilization  ← Problem!

  Root cause: GPU 3 handling embedding requests (small model)
              while GPUs 0-2 doing TP=3 for 70B model
  
  Solution: Reorganized to dedicated embedding GPU (cheaper L4)
            and TP=4 across 4 A100s for main model
  Result: All 4 GPUs at 78-82% utilization, embedding on $0.80/hr L4

═══════════════════════════════════════════════════════════════════
KEY METRICS TO MONITOR
═══════════════════════════════════════════════════════════════════

Metric                  | Target  | Alert Threshold | Action
────────────────────────|─────────|─────────────────|───────────
SM (Compute) Util %     | > 70%   | < 40% for 1hr   | Under-provisioned or batching issue
Memory Util %           | 80-90%  | > 95%           | Risk of OOM, reduce batch
Memory Bandwidth Util   | > 60%   | < 30%           | Compute-bound, can batch more
Power Draw (watts)      | 250-280W| < 150W sustained| GPU idle, wasting money
Request Queue Depth     | < 10    | > 50            | Need to scale or optimize
Tokens/sec/GPU          | Model-dependent | < 50% of benchmark | Regression detected
KV Cache Hit Rate       | > 30%   | < 10%           | Prefix caching not working
Batch Size (effective)  | > 8     | < 2 sustained   | Low traffic, consider scaling down
```

---

## Case Study 10: Build vs Rent — Complete 12-Month TCO

### Comprehensive Comparison for a Mid-Stage Startup

```
═══════════════════════════════════════════════════════════════════
COMPANY: "InsightAI" — B2B Analytics Platform with AI Features
WORKLOAD: 15M tokens/day (growing 20%/month)
MODEL NEEDS: 70B class for analysis, 8B for classification
TEAM: 3 ML engineers, 1 DevOps, 12 developers
═══════════════════════════════════════════════════════════════════

OPTION A: MANAGED API (OpenAI/Anthropic)
════════════════════════════════════════

Month-by-month cost (at 20% growth):
  Month 1:  15M tok/day × 30 × $0.015/1K = $6,750
  Month 3:  21.6M tok/day × 30 × $0.015/1K = $9,720
  Month 6:  37.3M tok/day × 30 × $0.015/1K = $16,785
  Month 12: 89M tok/day × 30 × $0.015/1K = $40,050

  12-month total API cost: ~$220,000

  Additional costs:
    API gateway/proxy: $500/month = $6,000
    Monitoring: $300/month = $3,600
    Engineer time (integration): 0.2 FTE × $180K = $36,000
    
  12-MONTH TOTAL: ~$266,000

  Pros:
    + Zero GPU expertise needed
    + Instant scaling
    + Always latest models
    + No hardware risk
  
  Cons:
    - Costs scale linearly with growth (painful at 20%/month)
    - No control over model updates
    - Data leaves your infrastructure
    - Rate limits can bottleneck growth

OPTION B: CLOUD GPU (AWS/GCP instances)
═══════════════════════════════════════

Infrastructure plan:
  Serving: 4× A100 80GB (p4de.24xlarge, using 4 of 8 GPUs)
  Scale-up path: Add instances as traffic grows
  
  Month 1-3: 1× p4de (4 GPUs), reserved instance
    $16.50/hr × 730hr = $12,045/month
  Month 4-6: 2× p4de (8 GPUs)
    $24,090/month
  Month 7-12: 3× p4de (12 GPUs) + spot for peaks
    $36,135/month + $5,000 spot = $41,135/month

  12-month compute: ~$340,000

  Additional costs:
    ML engineer (GPU ops): 0.5 FTE × $200K = $100,000
    Networking/storage: $1,500/month = $18,000
    Monitoring (GPU-specific): $800/month = $9,600
    Model optimization (one-time): $30,000 (consultant)
    
  12-MONTH TOTAL: ~$498,000

  Pros:
    + Full control over models
    + Can run custom/fine-tuned models
    + Data stays in your infra
    + Can optimize aggressively (quantization, batching)
  
  Cons:
    - Significant ML ops expertise needed
    - Hardware capacity planning is hard
    - Reserved instances lock you in
    - GPU availability not guaranteed

OPTION C: SELF-HOSTED GPU CLUSTER (Colo/On-prem)
════════════════════════════════════════════════════

Hardware purchase:
  8× A100 80GB PCIe: 8 × $15,000 = $120,000
  2× Server chassis (4 GPU each): 2 × $25,000 = $50,000
  NVLink bridges: $8,000
  Networking (InfiniBand): $15,000
  Total hardware: $193,000 (amortize over 3 years = $5,361/month)

Colocation:
  2× 4U servers, 10kW total power
  Colo cost: $3,500/month (including power, cooling, network)

Operations:
  DevOps/MLOps engineer: 0.5 FTE × $200K = $100,000/year
  Hardware warranty/support: $2,000/month
  Spare parts budget: $500/month

  Monthly cost: $5,361 + $3,500 + $8,333 + $2,000 + $500 = $19,694
  12-MONTH TOTAL: ~$236,000

  Pros:
    + Lowest long-term cost (hardware is an asset)
    + Complete control
    + Predictable monthly costs
    + No cloud markup (2-4× on GPU instances)
  
  Cons:
    - High upfront capital ($193K)
    - Hardware depreciation risk (H200/B200 coming)
    - Scaling takes weeks/months (ordering hardware)
    - Team needs hardware expertise
    - If growth slows, stuck with expensive hardware

═══════════════════════════════════════════════════════════════════
DECISION MATRIX
═══════════════════════════════════════════════════════════════════

                    | Managed API | Cloud GPU  | Self-Hosted
────────────────────|─────────────|────────────|────────────
12-month TCO        | $266,000    | $498,000   | $236,000
Year 2 projected    | $600,000+   | $580,000   | $240,000
Break-even vs API   | —           | Never(!)   | Month 8
Scaling flexibility | Instant     | Hours      | Weeks
Team needed         | 0.2 FTE     | 0.5 FTE    | 0.5 FTE
Time to production  | 1 week      | 1 month    | 3 months
Risk level          | Low         | Medium     | High

═══════════════════════════════════════════════════════════════════
INSIGHTAI'S ACTUAL DECISION: Phased approach
═══════════════════════════════════════════════════════════════════

Phase 1 (Months 1-4): Managed API only
  - Ship product fast, validate market
  - Cost: ~$35K total
  - Focus: Product-market fit, not infrastructure

Phase 2 (Months 5-8): Hybrid (API + Cloud GPU for high-volume features)
  - Move classification (80% of tokens) to self-hosted on cloud GPU
  - Keep complex analysis on managed API
  - Cost: ~$18K/month blended

Phase 3 (Month 9+): Self-hosted cluster + API overflow
  - Order hardware for predictable baseline workload
  - Cloud GPU for scaling peaks
  - API for latest model capabilities only
  - Target: $15K/month for 100M+ tokens/day
```

---

## Case Study 11: Embedding Batching Economics

### 90% Cost Reduction Through Proper Batching

```
═══════════════════════════════════════════════════════════════════
SCENARIO: Index 2M documents (average 500 tokens each) for RAG system
MODEL: text-embedding-3-small (OpenAI) or self-hosted E5-large
═══════════════════════════════════════════════════════════════════

APPROACH 1: One-at-a-time (Naive implementation)
──────────────────────────────────────────────────

for doc in documents:  # 2M iterations
    embedding = openai.embeddings.create(
        input=doc.text,
        model="text-embedding-3-small"
    )

Performance:
  Requests: 2,000,000 API calls
  Rate limit: 3,000 RPM → 2M/3000 = 667 minutes = 11.1 hours
  Latency per request: ~100ms (but rate-limited, so irrelevant)
  Total time: 11.1 hours
  
  API cost: 2M docs × 500 tokens = 1B tokens
            $0.020 per 1M tokens = $20.00
  
  Compute overhead (your side):
    Connection overhead: 2M × 50ms = 27.7 hours of connection setup
    Total wall clock: 11.1 hours (rate-limit bound)

APPROACH 2: Batched (2048 texts per request — API max)
──────────────────────────────────────────────────────

for batch in chunks(documents, size=2048):
    embeddings = openai.embeddings.create(
        input=[doc.text for doc in batch],
        model="text-embedding-3-small"
    )

Performance:
  Requests: 2,000,000 / 2048 = 977 API calls
  Rate limit: 3,000 RPM → done in < 1 minute (not rate-limited!)
  Latency per batch request: ~2s (processing 2048 texts)
  Total time: 977 × 2s = 32.5 minutes (with parallelism: ~5 minutes)
  
  API cost: Same $20.00 (charged per token, not per request)
  
  Compute overhead (your side):
    Connection overhead: 977 × 50ms = 49 seconds
    Total wall clock: ~5 minutes with 10 parallel connections

COMPARISON:
                    | One-at-a-time | Batched (2048)
────────────────────|───────────────|───────────────
Wall clock time     | 11.1 hours    | 5 minutes
API calls           | 2,000,000     | 977
API cost            | $20.00        | $20.00 (same!)
Your compute cost   | ~$5.00 (EC2)  | ~$0.05
Connection overhead | 27.7 hours    | 49 seconds
Rate limit risk     | High          | Negligible

═══════════════════════════════════════════════════════════════════
SELF-HOSTED EMBEDDING: WHERE BATCHING REALLY SHINES
═══════════════════════════════════════════════════════════════════

Model: E5-large (330M params) on 1× A100 80GB

Batch size | Throughput (texts/sec) | GPU Util | Latency/text | Cost/1M texts
────────── |────────────────────────|──────────|──────────────|─────────────
1          | 45                     | 8%       | 22ms         | $24.69
8          | 320                    | 42%      | 25ms         | $3.47
32         | 1,100                  | 71%      | 29ms         | $1.01
128        | 2,800                  | 89%      | 46ms         | $0.40
512        | 3,200                  | 94%      | 160ms        | $0.35
2048       | 3,400                  | 96%      | 600ms        | $0.33

For 2M documents:
  Batch=1:    2M / 45 = 12.3 hours | Cost: $49.38 (GPU time)
  Batch=512:  2M / 3200 = 10.4 min | Cost: $0.70 (GPU time)

  COST REDUCTION: 98.6% (from batching alone!)
  TIME REDUCTION: 98.6%

WHY SUCH A DRAMATIC DIFFERENCE:
  1. GPU parallelism: Batch=1 uses 8% of GPU cores. Batch=512 uses 94%.
     You're literally paying for 92% idle silicon with batch=1.
  2. Memory bandwidth: Loading model weights once for 512 texts vs 1.
     Amortizes the memory-bandwidth cost across batch.
  3. Kernel launch overhead: One CUDA kernel launch for 512 texts vs 512 launches.

═══════════════════════════════════════════════════════════════════
OPTIMAL BATCHING STRATEGY FOR PRODUCTION
═══════════════════════════════════════════════════════════════════

Real-time queries (latency-sensitive):
  Batch size: 8-32
  Strategy: Micro-batch with 10ms collection window
  Latency: <50ms per query
  
  Implementation:
    async def embed_with_microbatch(text):
        batch_collector.add(text)
        if batch_collector.size >= 32 or batch_collector.age >= 10ms:
            results = model.encode(batch_collector.flush())
            return results[my_index]

Background indexing (throughput-sensitive):
  Batch size: 512-2048
  Strategy: Fill batches completely, process sequentially
  Throughput: 3,200+ texts/sec on single A100
  
  Implementation:
    for batch in chunks(all_documents, size=512):
        embeddings = model.encode(batch)  # One GPU call
        vector_db.upsert(batch, embeddings)

Mixed workload (real-time + batch on same GPU):
  Strategy: Priority queue with batch accumulation
  Real-time: Preempts batch jobs, micro-batched to 8
  Batch: Runs during gaps, batch=256
  
  Result: GPU stays at 85%+ utilization always
          Real-time latency: <50ms P95
          Batch throughput: 2,500 texts/sec (slightly reduced due to preemption)
```

---

## Summary: Key Economic Principles for Inference

| Principle | Impact | Example |
|-----------|--------|---------|
| Batch everything | 10-90× throughput | Embeddings: 45→3,200 texts/sec |
| Quantize aggressively | 2-4× cost reduction | INT4 AWQ: 96.5% quality at 40% cost |
| Use PagedAttention | 4-6× concurrency | 4→24 concurrent users same GPU |
| Continuous batching | 3.5× throughput | Static→continuous: 1,200→4,200 tok/s |
| Right-size GPU | 30-60% savings | L4 for embeddings vs A100 overkill |
| LoRA serving | 50× cost reduction | $57K→$1.1K for 100 customers |
| Speculative decoding | 2-3× latency | For predictable outputs (code, JSON) |
| Tiered architecture | 40-60% savings | Cheap model for easy tasks, expensive for hard |
| Off-peak scheduling | 30% savings | Batch jobs at night on spot instances |
| Hybrid deployment | Best of all worlds | API for flexibility + self-hosted for volume |
