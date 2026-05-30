# Inference Economics and GPU Serving

## 1. KV Cache

### What Is It?

In transformer models, every token generated requires attending to ALL previous tokens. The Key and Value matrices from previous tokens don't change once computed—they're deterministic given the same prefix. The **KV Cache** stores these pre-computed K and V tensors so we don't recompute them at every generation step.

### Memory Implications

For a model with:
- `L` layers, `H` attention heads, `D` head dimension, sequence length `S`, batch size `B`
- KV Cache size = `2 × L × H × D × S × B × bytes_per_element`

**Example: LLaMA-70B (FP16)**
- 80 layers, 64 KV heads (GQA), 128 dim, 4096 seq len
- Per request: 2 × 80 × 64 × 128 × 4096 × 2 bytes = ~10.7 GB per sequence
- With GQA (8 KV heads): 2 × 80 × 8 × 128 × 4096 × 2 bytes = ~1.34 GB per sequence

This means **KV cache often dominates GPU memory**, not model weights. A 70B model in FP16 is ~140GB for weights, but serving 32 concurrent 4K-context requests needs ~43GB just for KV cache.

### PagedAttention (vLLM)

Traditional KV cache allocates contiguous memory per sequence upfront (worst case = max_seq_len). This wastes memory for short sequences.

**PagedAttention** treats KV cache like virtual memory:
- Divides KV cache into fixed-size **blocks** (e.g., 16 tokens per block)
- Blocks are allocated on demand as the sequence grows
- Blocks can be non-contiguous in physical memory
- A block table maps logical positions → physical blocks
- Enables **memory sharing** between sequences with common prefixes (copy-on-write)

Benefits:
- Near-zero memory waste (only last block may be partially filled)
- 2-4x more concurrent sequences vs naive allocation
- Enables prefix sharing for prompt caching

---

## 2. Continuous Batching

### Static Batching (Naive)

In static batching, you collect N requests, process them together, and wait until ALL finish before accepting new requests. If one request generates 500 tokens and another generates 10, the short one wastes GPU cycles waiting.

### Continuous Batching (Iteration-Level Scheduling)

At each decode step:
1. Check if any sequences have finished (hit EOS or max_tokens)
2. Remove finished sequences from the batch
3. Add waiting sequences into the freed slots
4. Run one forward pass for the entire active batch

**Impact:**
- Static batching: GPU idle 50-70% of the time
- Continuous batching: GPU utilization 85-95%
- Throughput improvement: 2-10x depending on output length variance

### Prefill vs Decode Phases

- **Prefill**: Process all input tokens in parallel (compute-bound, high FLOPS)
- **Decode**: Generate one token at a time per sequence (memory-bound, limited by memory bandwidth)

These have different GPU characteristics. Advanced schedulers (like Sarathi-Serve) **chunk prefill** to avoid starving decode requests.

---

## 3. Prefix Caching

When many requests share the same system prompt or few-shot examples, the KV cache for those prefix tokens is identical across requests.

### How It Works

1. Hash the prefix tokens (system prompt + common instructions)
2. Check if KV cache blocks for that hash exist in a cache (GPU memory or host memory)
3. If hit: skip prefill for those tokens, load cached KV blocks
4. If miss: compute normally, store result

### Savings

- System prompt of 2000 tokens at ~0.5ms/token prefill = 1 second saved per request
- For high-volume systems (1000 req/s), this is massive
- Also saves compute (FLOPS) not just latency

### Implementations

- **vLLM**: Automatic prefix caching via hash-based block matching
- **SGLang**: RadixAttention—maintains a radix tree of all cached prefixes
- **TensorRT-LLM**: KV cache reuse across requests

---

## 4. Speculative Decoding

### The Problem

Autoregressive decoding is sequential—one token per forward pass of the full model. For a 70B model, each forward pass takes ~30ms. Generating 100 tokens = 3 seconds minimum.

### The Solution

Use a **small draft model** (e.g., 1B params) to speculatively generate K tokens ahead, then **verify** all K tokens in a single forward pass of the large model.

### Algorithm

```
1. Draft model generates K tokens: [t1, t2, ..., tK]
2. Large model runs ONE forward pass on all K tokens
3. Compare probabilities: for each position i,
   - If P_large(ti) / P_draft(ti) >= random threshold: ACCEPT
   - Else: REJECT ti and all subsequent tokens
4. Keep accepted tokens, resample from large model at rejection point
```

### Economics

- Draft model: ~1/70th the compute per token
- If acceptance rate is α ≈ 0.7-0.85:
  - Expected tokens per large-model forward pass: K×α + 1
  - With K=5, α=0.8: ~5 tokens per forward pass instead of 1
  - **3-5x latency reduction** for similar quality

### When It Works Well

- Draft model closely matches large model's distribution
- Tasks with predictable/formulaic outputs (code, structured data)
- Low-entropy continuations

---

## 5. Quantization

### What Is Quantization?

Reducing the precision of model weights (and optionally activations) from FP16/BF16 (16-bit) to INT8 (8-bit) or INT4 (4-bit).

### Techniques

| Method | Bits | How | Quality Impact |
|--------|------|-----|----------------|
| **FP16/BF16** | 16 | Baseline | None |
| **INT8 (W8A8)** | 8 | Weights + activations quantized | Minimal (<1% degradation) |
| **INT8 (W8A16)** | 8/16 | Only weights quantized | Negligible |
| **GPTQ** | 4 | Post-training, layer-wise optimal rounding | 1-3% quality loss |
| **AWQ** | 4 | Activation-aware, protects salient weights | <1% quality loss |
| **GGUF/GGML** | 2-8 | Mixed quantization per tensor | Varies |
| **FP8** | 8 | Native on H100, maintains dynamic range | Minimal |
| **SqueezeLLM** | 3-4 | Non-uniform quantization | Competitive |

### Memory and Speed Impact

- **INT8**: 2x memory reduction, 1.5-2x throughput increase
- **INT4**: 4x memory reduction, 2-3x throughput increase
- **GPTQ-INT4**: 70B model fits on single 80GB A100 (vs 2x A100 for FP16)

### Quality Considerations

- Larger models are MORE robust to quantization (70B INT4 ≈ 70B FP16 on most benchmarks)
- Smaller models (7B) show noticeable degradation at INT4
- AWQ generally outperforms GPTQ at same bit width
- Perplexity increase: INT8 < 0.1, GPTQ-4bit ≈ 0.2-0.5, aggressive 3-bit ≈ 1.0+

---

## 6. Tensor Parallelism vs Pipeline Parallelism

### Tensor Parallelism (TP)

Split individual layers ACROSS GPUs. Each GPU holds a slice of every layer.

```
GPU 0: First half of attention heads + first half of FFN
GPU 1: Second half of attention heads + second half of FFN
```

- **Requires**: High-bandwidth interconnect (NVLink: 600-900 GB/s)
- **Latency**: Same as single GPU (all GPUs compute simultaneously)
- **Communication**: AllReduce after each layer (~microseconds on NVLink)
- **Best for**: Latency-sensitive serving within a single node

### Pipeline Parallelism (PP)

Split layers sequentially across GPUs. Each GPU holds a subset of consecutive layers.

```
GPU 0: Layers 0-19
GPU 1: Layers 20-39
GPU 2: Layers 40-59
GPU 3: Layers 60-79
```

- **Requires**: Any interconnect (works across nodes)
- **Latency**: Slightly higher (pipeline bubbles)
- **Communication**: Point-to-point between stages (activation tensors only)
- **Best for**: Throughput optimization, cross-node serving

### Combined (TP + PP)

For very large models across multiple nodes:
- TP within a node (fast NVLink)
- PP across nodes (slower network)

Example: 8-node H100 cluster for 405B model
- 4-way TP within each node
- 2-way PP across node pairs

---

## 7. LoRA Adapter Serving

### Concept

LoRA (Low-Rank Adaptation) adds small trainable matrices to attention layers:
- Original weight W (d×d), frozen
- LoRA: W + A×B where A is (d×r), B is (r×d), rank r << d

### Multi-LoRA Serving

One base model + multiple LoRA adapters loaded simultaneously:
- Base model weights: shared across all requests (e.g., 140GB for 70B FP16)
- Each LoRA adapter: ~50-500MB (rank 16-64)
- Can serve 100+ different fine-tuned variants on the same GPU

### Implementation Pattern

```
Request → Route to adapter → Base model forward pass + LoRA computation
```

- **S-LoRA**: Unified paging for LoRA weights, batch requests to different adapters
- **Punica**: Custom CUDA kernels for batched LoRA computation
- **vLLM**: Native multi-LoRA support

### Economics

- Without LoRA: Need separate GPU allocation per fine-tuned model
- With LoRA: 1 GPU serves 50+ "models" simultaneously
- Cost reduction: 10-50x for multi-tenant fine-tuned serving

---

## 8. GPU Utilization Optimization

### Utilization Metrics

| Metric | Target | Meaning |
|--------|--------|---------|
| SM Occupancy | >80% | Streaming multiprocessors active |
| Memory Bandwidth Util | >70% | HBM bandwidth utilized |
| Compute Util (TFLOPS) | >60% | Theoretical FLOPS achieved |
| GPU Memory Used | 85-95% | VRAM allocated (not too much, not wasted) |

### Common Waste Sources

1. **Bubble time**: Waiting between prefill and decode batches
2. **Memory fragmentation**: KV cache not fully utilized
3. **Small batches**: Not enough concurrent requests
4. **Padding**: Sequences padded to same length in static batching
5. **Data transfer**: CPU↔GPU data movement

### Optimization Strategies

- **Continuous batching**: Eliminate decode bubbles
- **PagedAttention**: Eliminate memory fragmentation
- **Dynamic batching**: Accumulate requests for 5-50ms before processing
- **Chunked prefill**: Interleave prefill chunks with decode steps
- **CUDA graphs**: Eliminate kernel launch overhead for decode
- **FlashAttention**: Fused attention kernel, memory-efficient

---

## 9. Throughput vs Latency Tradeoffs

### The Fundamental Tradeoff

```
Higher batch size → Higher throughput BUT higher per-request latency
Lower batch size → Lower latency BUT lower throughput (GPU underutilized)
```

### Quantified Example (LLaMA-70B on 4×A100)

| Batch Size | Throughput (tok/s) | P50 Latency (ms/tok) | P99 Latency |
|------------|-------------------|----------------------|-------------|
| 1 | 35 | 28 | 32 |
| 8 | 240 | 33 | 45 |
| 32 | 750 | 42 | 80 |
| 128 | 1800 | 71 | 200 |
| 256 | 2200 | 116 | 500 |

### SLO-Based Serving

Define latency SLOs per tier:
- **Streaming chat**: TTFT < 500ms, inter-token < 50ms
- **Batch processing**: TTFT < 5s, throughput maximized
- **Real-time API**: E2E < 2s

Configure serving parameters to meet SLOs:
- Max batch size limited by P99 latency target
- Priority queuing for latency-sensitive requests
- Separate pools for interactive vs batch workloads

---

## 10. Cold Starts and Autoscaling

### Cold Start Components

| Phase | Duration | What Happens |
|-------|----------|--------------|
| Instance provisioning | 30-120s | VM/container starts |
| Model download | 30-300s | Pull weights from storage (70B ≈ 140GB) |
| Model loading to GPU | 15-60s | CPU→GPU memory transfer |
| CUDA compilation | 5-30s | JIT compile kernels |
| Warmup inference | 2-10s | First inference is slow |
| **Total** | **80-520s** | **Unusable during this time** |

### Mitigation Strategies

1. **Pre-warmed pools**: Keep N idle replicas ready
2. **Model caching on local NVMe**: Skip download (30s → 0s)
3. **Tensor-parallel fast loading**: Load shards in parallel
4. **Speculative autoscaling**: Scale based on queue growth rate, not just length
5. **Graceful degradation**: Serve smaller model while large model loads

### Autoscaling Signals

```
Primary: tokens_per_second_capacity vs tokens_per_second_demand
Secondary: queue_depth, p99_latency, gpu_memory_utilization
Scale-up threshold: utilization > 75% for 60s OR queue > 100 requests
Scale-down threshold: utilization < 30% for 300s AND queue == 0
```

### Scaling by Tokens/Sec

```
demand_tokens_per_sec = request_rate × avg_total_tokens_per_request
capacity_per_replica = throughput_tokens_per_sec (measured)
required_replicas = ceil(demand / (capacity × target_utilization))
```

---

## 11. Multi-Model Serving

### Why?

Different tasks need different models:
- Simple classification: 7B model (fast, cheap)
- Complex reasoning: 70B model (slow, expensive)
- Embeddings: Dedicated embedding model
- Code: Code-specialized model

### Serving Patterns

**Pattern 1: Model per GPU**
- Dedicate GPUs to specific models
- Simple but potentially wasteful

**Pattern 2: Time-multiplexing**
- Swap models on/off GPU based on demand
- Swap overhead: 15-60s (unacceptable for real-time)

**Pattern 3: Memory-sharing with Paging**
- Multiple small models fit on one GPU simultaneously
- E.g., 2× 7B models + 1× embedding model on 80GB A100

**Pattern 4: Cascading/Routing**
- Route easy requests to small model
- Route hard requests to large model
- Use a cheap classifier to decide

### Economics of Routing

If 70% of requests can be handled by 7B ($0.001/req) and 30% need 70B ($0.01/req):
- Without routing: $0.01 × 100% = $0.01/req
- With routing: $0.001 × 70% + $0.01 × 30% = $0.0037/req
- **63% cost reduction**

---

## 12. Fallback Serving

### Failure Modes

1. GPU OOM (out of memory)
2. Model crash / CUDA error
3. Latency spike beyond SLO
4. Provider API rate limit
5. Region outage

### Fallback Architecture

```
Primary: Self-hosted 70B on A100 cluster
  ↓ (timeout/error)
Secondary: Azure OpenAI GPT-4 (different region)
  ↓ (rate limited)
Tertiary: Anthropic Claude (different provider)
  ↓ (all failed)
Degraded: Cached response or smaller local model
```

### Implementation Considerations

- **Semantic equivalence**: Fallback model may produce different outputs
- **Cost spikes**: Fallback to API can be 10x more expensive
- **Prompt compatibility**: Different models need different prompts
- **Circuit breakers**: Don't hammer a failing backend
- **Budget caps**: Limit fallback spend per hour

---

## 13. Cost Per Request Breakdown

### Full Stack Cost Components

```
Total Cost Per Request = 
    LLM Input Tokens Cost
  + LLM Output Tokens Cost
  + Embedding Cost
  + Reranker Cost
  + Vector DB Query Cost
  + Tool/API Call Costs
  + Observability/Logging Cost
  + Human Review Cost (amortized)
  + Infrastructure Overhead
  + Network/Egress Cost
```

### Detailed Breakdown Example (RAG Pipeline)

| Component | Unit Cost | Usage | Cost/Request |
|-----------|-----------|-------|-------------|
| Embedding (query) | $0.0001/1K tok | 50 tokens | $0.000005 |
| Vector DB query | $0.000004/query | 1 query | $0.000004 |
| Reranker | $0.002/1K tok | 5000 tokens (20 docs) | $0.01 |
| LLM Input | $0.003/1K tok | 3000 tokens | $0.009 |
| LLM Output | $0.015/1K tok | 500 tokens | $0.0075 |
| Tool calls | $0.001/call | 2 calls | $0.002 |
| Observability | $0.0001/request | 1 | $0.0001 |
| Infrastructure | Amortized | — | $0.002 |
| **Total** | | | **$0.031** |

### Hidden Costs

- **Retries**: Failed requests still cost money (2-10% of requests)
- **Evaluation**: Running eval suites costs real tokens
- **Prompt iteration**: Development cost of prompt engineering
- **Guardrails**: Input/output moderation adds latency and cost
- **Caching infrastructure**: Redis/CDN costs to enable savings
- **Monitoring**: Logging every request for debugging

---

## 14. Financial Architecture and Unit Economics

### Revenue Models for AI Features

1. **Per-seat subscription**: User pays flat rate, you eat variable AI costs
2. **Per-request pricing**: Pass-through with margin (Cursor, GitHub Copilot)
3. **Per-outcome pricing**: Charge per successful task (higher margin, harder to measure)
4. **Token credits**: Sell credit packs (OpenAI model)
5. **Freemium with limits**: Free tier with token caps

### Unit Economics Framework

```
Gross Margin = (Revenue per Request - Variable Cost per Request) / Revenue per Request

Variable costs: LLM tokens, embedding, vector DB, API calls
Fixed costs: GPUs (reserved), engineering, model training, infrastructure

Break-even volume = Fixed Costs / Gross Margin per Request
```

### Example: AI Customer Support Bot

```
Revenue: $0.50 per resolved ticket
Costs:
  - LLM (3 turns avg): 3 × $0.03 = $0.09
  - RAG retrieval: 3 × $0.005 = $0.015
  - Embedding: $0.001
  - Infra amortized: $0.01
  - Total: $0.116
  
Gross margin: ($0.50 - $0.116) / $0.50 = 76.8%

Monthly fixed costs: $50K (GPU cluster + engineering)
Break-even: $50K / $0.384 = 130,208 tickets/month
```

### Cost Optimization Levers

1. **Caching**: 30-60% hit rate on repeated queries → proportional cost reduction
2. **Model routing**: Small model for easy tasks → 50-70% cheaper
3. **Prompt optimization**: Shorter prompts → proportional savings
4. **Batch processing**: Non-real-time tasks → higher throughput, lower cost/token
5. **Self-hosting**: At >$50K/month API spend, self-hosting usually wins
6. **Quantization**: INT4 serving → 2-3x more requests per GPU

---

## 15. GPU Economics

### Hardware Comparison

| GPU | VRAM | BF16 TFLOPS | Memory BW | Price (cloud/hr) | TCO (3yr) |
|-----|------|-------------|-----------|-------------------|-----------|
| A100 40GB | 40GB | 312 | 1.6 TB/s | $3-4/hr | ~$90K |
| A100 80GB | 80GB | 312 | 2.0 TB/s | $4-5/hr | ~$110K |
| H100 SXM | 80GB | 990 | 3.35 TB/s | $8-12/hr | ~$250K |
| H200 | 141GB | 990 | 4.8 TB/s | $12-15/hr | ~$350K |
| L40S | 48GB | 366 | 864 GB/s | $2-3/hr | ~$60K |
| A10G | 24GB | 125 | 600 GB/s | $1-1.5/hr | ~$25K |

### Performance Per Dollar (Inference)

For LLaMA-70B INT4 serving:

| GPU | Throughput (tok/s) | $/hr | tok/$ |
|-----|-------------------|------|-------|
| 4×A100 80GB | 2000 | $20 | 360K |
| 2×H100 | 3500 | $20 | 630K |
| 2×H200 | 5000 | $28 | 643K |
| 8×L40S | 2400 | $20 | 432K |

### Total Cost of Ownership (Self-Hosted)

```
Annual TCO per GPU = 
    Hardware amortized (3 year) 
  + Power (GPU: 300-700W × 8760hr × $0.10/kWh)
  + Cooling (1.3x power)
  + Network (InfiniBand/RoCE)
  + Rack space ($500-2000/month/rack)
  + Operations (0.5-1 FTE per 100 GPUs)
  + Redundancy (N+1 sparing)
  + Software licenses (CUDA, monitoring)

Example H100 SXM:
  Hardware: $250K / 3 = $83K/yr
  Power: 700W × 8760 × $0.10 × 1.3 = $7,970/yr
  Network: ~$5K/yr
  Ops: ~$10K/yr (amortized)
  Total: ~$106K/yr = ~$12/hr

Cloud H100: $10-12/hr (comparable but includes ops)
Self-hosted advantage: At >80% utilization, self-hosted wins by 30-50%
```

### Decision Framework: Build vs Buy

| Factor | Self-Host | Managed API |
|--------|-----------|-------------|
| Monthly spend < $10K | ❌ | ✅ |
| Monthly spend > $50K | ✅ | Consider |
| Need custom models | ✅ | ❌ |
| Need data privacy | ✅ | ❌ (mostly) |
| Variable load (10x peaks) | ❌ | ✅ |
| Steady high load | ✅ | ❌ |
| Team has GPU expertise | ✅ | N/A |
| Time to market critical | ❌ | ✅ |
| Need latest models immediately | ❌ | ✅ |

### Utilization Is Everything

```
Self-hosted cost per token = Fixed Cost / (Capacity × Utilization)

At 90% utilization: $0.002/1K tokens
At 50% utilization: $0.0036/1K tokens  (1.8x more expensive)
At 20% utilization: $0.009/1K tokens   (4.5x more expensive)

OpenAI GPT-4 Turbo: $0.01/1K input tokens

Break-even utilization (self-hosted H100 cluster vs GPT-4 API):
  ~35-45% utilization for comparable models
```

---

## Summary: Key Principles

1. **KV cache is the bottleneck**, not model weights—optimize memory management first
2. **Continuous batching is table stakes**—never use static batching in production
3. **Quantize aggressively for large models**—70B+ models lose minimal quality at INT4
4. **Route by complexity**—don't use expensive models for easy tasks
5. **Cache everything**—prefix caching, semantic caching, response caching
6. **Measure cost per successful outcome**, not cost per token
7. **Utilization determines self-hosted economics**—below 50% util, use managed APIs
8. **Plan for cold starts**—they're the #1 complaint in autoscaled GPU serving
9. **Fallbacks are not optional**—GPU serving is less reliable than traditional backends
10. **The cheapest inference is the one you don't do**—cache and filter aggressively
