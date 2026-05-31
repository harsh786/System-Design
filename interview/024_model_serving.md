# Model Serving and Inference Optimization (Questions 116-120)

## Q116: Design model serving infrastructure with vLLM/TensorRT-LLM

### Problem
Maximize GPU utilization through continuous batching, PagedAttention, and KV-cache optimization for production LLM serving.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            High-Performance Model Serving Infrastructure      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 Load Balancer                          │   │
│  │  (request routing by estimated tokens, priority)      │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Inference Engine (vLLM)                   │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         Continuous Batching Scheduler            │  │   │
│  │  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐    │  │   │
│  │  │  │ Waiting │ │ Running  │ │ Preempted    │    │  │   │
│  │  │  │ Queue   │ │ Batch    │ │ Queue        │    │  │   │
│  │  │  └─────────┘ └──────────┘ └──────────────┘    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         PagedAttention KV-Cache Manager         │  │   │
│  │  │  ┌──────┐┌──────┐┌──────┐┌──────┐            │  │   │
│  │  │  │Page 0││Page 1││Page 2││ ...  │ (4KB each)  │  │   │
│  │  │  └──────┘└──────┘└──────┘└──────┘            │  │   │
│  │  │  Block Table: seq_id -> [page_ids]             │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │         GPU Memory Layout                       │  │   │
│  │  │  [Model Weights 60%] [KV-Cache 35%] [Act. 5%] │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import asyncio

class RequestState(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    PREEMPTED = "preempted"
    FINISHED = "finished"

@dataclass
class InferenceRequest:
    request_id: str
    prompt_tokens: List[int]
    max_new_tokens: int
    priority: int = 0
    arrival_time: float = 0
    state: RequestState = RequestState.WAITING
    generated_tokens: List[int] = field(default_factory=list)
    kv_cache_pages: List[int] = field(default_factory=list)

class ContinuousBatchingScheduler:
    """Iteration-level scheduling: add/remove requests every decode step."""
    
    def __init__(self, max_batch_size: int = 256, max_tokens_per_batch: int = 8192,
                 gpu_memory_gb: float = 80):
        self.max_batch_size = max_batch_size
        self.max_tokens = max_tokens_per_batch
        self.waiting_queue = []  # priority queue
        self.running_batch = []
        self.kv_cache_manager = PagedKVCacheManager(gpu_memory_gb)

    def schedule_step(self) -> List[InferenceRequest]:
        """Called every decode iteration to determine batch composition."""
        # 1. Remove finished sequences
        self.running_batch = [r for r in self.running_batch 
                             if r.state == RequestState.RUNNING]
        
        # 2. Try to add new requests from waiting queue
        while self.waiting_queue and self._can_add_request(self.waiting_queue[0]):
            request = self.waiting_queue.pop(0)
            # Allocate KV-cache pages
            pages = self.kv_cache_manager.allocate(request.prompt_tokens)
            if pages is None:
                # No memory: preempt lowest priority running request
                preempted = self._preempt_lowest_priority()
                if preempted:
                    pages = self.kv_cache_manager.allocate(request.prompt_tokens)
                else:
                    self.waiting_queue.insert(0, request)
                    break
            
            request.kv_cache_pages = pages
            request.state = RequestState.RUNNING
            self.running_batch.append(request)
        
        return self.running_batch

    def _can_add_request(self, request: InferenceRequest) -> bool:
        """Check if we can fit another request in the batch."""
        if len(self.running_batch) >= self.max_batch_size:
            return False
        current_tokens = sum(len(r.prompt_tokens) + len(r.generated_tokens) 
                           for r in self.running_batch)
        if current_tokens + len(request.prompt_tokens) > self.max_tokens:
            return False
        return self.kv_cache_manager.has_capacity(len(request.prompt_tokens))

    def _preempt_lowest_priority(self) -> Optional[InferenceRequest]:
        """Preempt request with lowest priority (swap KV-cache to CPU)."""
        if not self.running_batch:
            return None
        lowest = min(self.running_batch, key=lambda r: r.priority)
        self.kv_cache_manager.swap_out(lowest.kv_cache_pages)  # GPU -> CPU
        lowest.state = RequestState.PREEMPTED
        self.running_batch.remove(lowest)
        return lowest

class PagedKVCacheManager:
    """Manages KV-cache using paging (like OS virtual memory)."""
    
    def __init__(self, gpu_memory_gb: float, page_size: int = 16):
        # page_size = number of tokens per page
        self.page_size = page_size
        # Calculate available pages (assume 35% of GPU for KV-cache)
        kv_memory_bytes = int(gpu_memory_gb * 0.35 * 1e9)
        # Per-page memory: 2 (K+V) * num_layers * hidden_dim * 2 (bf16) * page_size
        self.bytes_per_page = 2 * 80 * 8192 * 2 * page_size  # ~40MB for 70B model
        self.total_pages = kv_memory_bytes // self.bytes_per_page
        self.free_pages = list(range(self.total_pages))
        self.page_table: Dict[str, List[int]] = {}  # seq_id -> page_ids

    def allocate(self, tokens: List[int]) -> Optional[List[int]]:
        """Allocate pages for a sequence."""
        pages_needed = (len(tokens) + self.page_size - 1) // self.page_size
        if len(self.free_pages) < pages_needed:
            return None
        allocated = [self.free_pages.pop() for _ in range(pages_needed)]
        return allocated

    def has_capacity(self, num_tokens: int) -> bool:
        pages_needed = (num_tokens + self.page_size - 1) // self.page_size
        return len(self.free_pages) >= pages_needed

    def free(self, pages: List[int]):
        """Return pages to free list."""
        self.free_pages.extend(pages)

    def swap_out(self, pages: List[int]):
        """Swap KV-cache pages from GPU to CPU (for preemption)."""
        # In practice: async cudaMemcpyAsync GPU->CPU
        pass

    def copy_on_write(self, pages: List[int]) -> List[int]:
        """For beam search / parallel sampling: share pages until write."""
        # Increment reference count; only copy page on modification
        return pages  # logical sharing, physical copy deferred
```

### Performance Metrics

| Metric | Without Optimization | With vLLM | Improvement |
|--------|---------------------|-----------|-------------|
| Throughput (tokens/s) | 500 | 2000+ | 4x |
| GPU utilization | 30-40% | 85-95% | 2.5x |
| Memory waste | 60-80% | <5% | 15x reduction |
| P50 latency (TTFT) | 2s | 200ms | 10x |
| Max concurrent requests | 8 | 256 | 32x |

### Production Considerations
- **Prefix caching**: Cache KV-cache for common system prompts; share across requests
- **Chunked prefill**: Process long prompts in chunks to avoid blocking decode steps
- **Priority queues**: Premium users get higher priority; preempt free-tier requests
- **Auto-scaling**: Scale GPU instances based on queue depth, not CPU utilization
- **Health checks**: Monitor KV-cache fragmentation; periodic compaction

---

## Q117: Design a speculative decoding system

### Problem
Use a small draft model to speed up a large target model by 2-3x while maintaining exact output distribution.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│              Speculative Decoding System                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Draft Phase (fast, small model)                     │   │
│  │                                                      │   │
│  │  Token 1 ──▶ Token 2 ──▶ Token 3 ──▶ ... Token K   │   │
│  │  (7B model, ~5ms per token)                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼ (K draft tokens)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Verification Phase (target model, single forward)   │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │ Parallel verification of all K draft tokens   │   │   │
│  │  │ P_target(token_i | prefix + tokens_1..i-1)    │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Acceptance/Rejection (token by token)               │   │
│  │                                                      │   │
│  │  Token 1: ✓ Accept  (P_target >= P_draft)           │   │
│  │  Token 2: ✓ Accept                                  │   │
│  │  Token 3: ✗ Reject  → Resample from adjusted dist  │   │
│  │  Token 4+: Discard                                  │   │
│  │                                                      │   │
│  │  Result: 3 tokens from 1 target forward pass!       │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
import torch.nn.functional as F
from typing import Tuple, List

class SpeculativeDecoder:
    def __init__(self, target_model, draft_model, 
                 speculation_length: int = 5, temperature: float = 1.0):
        self.target = target_model  # 70B
        self.draft = draft_model    # 7B (same tokenizer)
        self.K = speculation_length
        self.temperature = temperature

    @torch.no_grad()
    def generate(self, input_ids: torch.Tensor, max_tokens: int) -> torch.Tensor:
        """Generate tokens using speculative decoding."""
        generated = input_ids.clone()
        tokens_generated = 0
        
        while tokens_generated < max_tokens:
            # Phase 1: Draft K tokens with small model
            draft_tokens, draft_probs = self._draft_phase(generated)
            
            # Phase 2: Verify all K tokens with target model in one forward pass
            target_probs = self._verify_phase(generated, draft_tokens)
            
            # Phase 3: Accept/reject using modified rejection sampling
            accepted, bonus_token = self._acceptance_phase(
                draft_tokens, draft_probs, target_probs
            )
            
            # Append accepted tokens + bonus token
            generated = torch.cat([generated, accepted, bonus_token.unsqueeze(0)], dim=-1)
            tokens_generated += len(accepted) + 1
            
            # Adaptive K: increase if acceptance rate high, decrease if low
            acceptance_rate = len(accepted) / self.K
            self.K = self._adapt_k(acceptance_rate)
        
        return generated[:, input_ids.shape[-1]:]  # return only new tokens

    def _draft_phase(self, prefix: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Generate K tokens with draft model."""
        draft_tokens = []
        draft_probs = []
        current = prefix
        
        for _ in range(self.K):
            logits = self.draft(current)[:, -1, :]
            probs = F.softmax(logits / self.temperature, dim=-1)
            token = torch.multinomial(probs, 1)
            draft_tokens.append(token.item())
            draft_probs.append(probs[0])
            current = torch.cat([current, token], dim=-1)
        
        return torch.tensor(draft_tokens), torch.stack(draft_probs)

    def _verify_phase(self, prefix: torch.Tensor, 
                      draft_tokens: torch.Tensor) -> torch.Tensor:
        """Single forward pass of target model on prefix + all draft tokens."""
        # Concatenate prefix with draft tokens
        full_sequence = torch.cat([prefix, draft_tokens.unsqueeze(0)], dim=-1)
        
        # One forward pass gives logits for all positions
        logits = self.target(full_sequence)
        
        # Extract probabilities for positions where we need to verify
        # Position i gives P(token at i+1 | tokens 0..i)
        start_pos = prefix.shape[-1] - 1
        target_logits = logits[:, start_pos:start_pos + self.K + 1, :]
        target_probs = F.softmax(target_logits / self.temperature, dim=-1)
        
        return target_probs[0]  # [K+1, vocab_size]

    def _acceptance_phase(self, draft_tokens: torch.Tensor,
                          draft_probs: torch.Tensor,
                          target_probs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Modified rejection sampling preserving target distribution."""
        accepted = []
        
        for i in range(self.K):
            token = draft_tokens[i]
            p_draft = draft_probs[i, token]
            p_target = target_probs[i, token]
            
            # Accept with probability min(1, p_target / p_draft)
            acceptance_prob = min(1.0, (p_target / p_draft).item())
            
            if torch.rand(1).item() < acceptance_prob:
                accepted.append(token)
            else:
                # Reject: sample from adjusted distribution
                # P_adjusted = normalize(max(0, P_target - P_draft))
                adjusted = torch.clamp(target_probs[i] - draft_probs[i], min=0)
                adjusted = adjusted / adjusted.sum()
                bonus = torch.multinomial(adjusted, 1)
                return torch.tensor(accepted), bonus.squeeze()
        
        # All K tokens accepted! Sample bonus token from target at position K
        bonus = torch.multinomial(target_probs[self.K], 1)
        return torch.tensor(accepted), bonus.squeeze()

    def _adapt_k(self, acceptance_rate: float) -> int:
        """Dynamically adjust speculation length."""
        if acceptance_rate > 0.8:
            return min(self.K + 1, 10)  # speculate more
        elif acceptance_rate < 0.4:
            return max(self.K - 1, 2)  # speculate less
        return self.K
```

### When to Use / Not Use

| Scenario | Use Speculative Decoding? | Rationale |
|----------|--------------------------|-----------|
| High acceptance rate (>70%) | Yes | 2-3x speedup |
| Creative/high-temp generation | No | Low acceptance rate, wasted compute |
| Batch size > 1 | Depends | Less benefit (GPU already utilized) |
| Draft model unavailable | No | Need aligned draft model |
| Latency-critical (single user) | Yes | Best for reducing per-user latency |
| Throughput-critical (many users) | Maybe | Continuous batching might be better |

### Speedup Analysis

| Draft Model | Target Model | Acceptance Rate | Speedup | Overhead |
|-------------|-------------|-----------------|---------|----------|
| Llama-7B | Llama-70B | 75% | 2.5x | Draft GPU cost |
| 2-layer model | GPT-4 | 60% | 1.8x | Minimal |
| Medusa heads | Same model | 80% | 2.8x | +5% params |
| N-gram cache | Any | 40-90% (varies) | 1.5-3x | CPU only |

### Production Considerations
- **Draft model alignment**: Draft must share tokenizer; fine-tune on target's outputs for higher acceptance
- **Memory**: Need both models in GPU memory (or draft on CPU if small enough)
- **Adaptive K**: Monitor acceptance rate per-request; adjust dynamically
- **Batched verification**: Batch multiple sequences' verifications together
- **Fallback**: If acceptance rate drops below 30%, disable speculative decoding for that request

---

## Q118: Design a quantization strategy for production LLM deployment

### Problem
Select and deploy optimal quantization (GPTQ, AWQ, GGUF) based on hardware and quality requirements.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│              Quantization Strategy Framework                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                Quantization Selector                     │    │
│  │                                                         │    │
│  │  Input: model_size, hardware, quality_req, latency_req  │    │
│  │  Output: quantization_method + config                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                      │
│          ┌───────────────┼───────────────┐                     │
│          ▼               ▼               ▼                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │    GPTQ      │ │    AWQ       │ │    GGUF      │           │
│  │  (GPU, 4bit) │ │ (GPU, 4bit) │ │ (CPU/GPU,    │           │
│  │  Post-train  │ │ Activation-  │ │  mixed quant)│           │
│  │  per-column  │ │ aware        │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                          │                                      │
│                          ▼                                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Quality Validation Pipeline                 │    │
│  │  [Perplexity Check] [Task Accuracy] [Edge Cases]       │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class QuantMethod(Enum):
    FP16 = "fp16"
    GPTQ_4BIT = "gptq_4bit"
    GPTQ_8BIT = "gptq_8bit"
    AWQ_4BIT = "awq_4bit"
    GGUF_Q4_K_M = "gguf_q4_k_m"
    GGUF_Q5_K_M = "gguf_q5_k_m"
    GGUF_Q8_0 = "gguf_q8_0"

@dataclass
class HardwareProfile:
    gpu_type: Optional[str]  # "A100", "T4", "RTX4090", None (CPU only)
    gpu_memory_gb: float = 0
    cpu_memory_gb: float = 64
    has_tensor_cores: bool = False

@dataclass
class QualityRequirement:
    max_perplexity_increase: float = 0.5  # % increase over fp16
    min_task_accuracy: float = 0.95  # relative to fp16 baseline
    critical_domains: list = None  # domains where quality matters most

class QuantizationSelector:
    def __init__(self):
        self.benchmarks = self._load_benchmarks()

    def select(self, model_size_b: float, hardware: HardwareProfile,
               quality_req: QualityRequirement, target_latency_ms: float) -> dict:
        """Select optimal quantization strategy."""
        
        # Calculate memory requirements for each method
        candidates = []
        for method in QuantMethod:
            memory_gb = self._estimate_memory(model_size_b, method)
            fits_gpu = memory_gb <= hardware.gpu_memory_gb * 0.85  # 85% headroom
            
            if method.name.startswith("GGUF") and not hardware.gpu_type:
                fits_hardware = memory_gb <= hardware.cpu_memory_gb * 0.7
            elif hardware.gpu_type:
                fits_hardware = fits_gpu
            else:
                continue
            
            if not fits_hardware:
                continue
            
            # Check quality constraints
            quality_loss = self._get_quality_loss(model_size_b, method)
            if quality_loss > quality_req.max_perplexity_increase:
                continue
            
            # Estimate latency
            latency = self._estimate_latency(model_size_b, method, hardware)
            if latency > target_latency_ms:
                continue
            
            candidates.append({
                "method": method,
                "memory_gb": memory_gb,
                "quality_loss_pct": quality_loss,
                "estimated_latency_ms": latency,
                "throughput_tokens_per_sec": self._estimate_throughput(model_size_b, method, hardware)
            })
        
        if not candidates:
            raise ValueError("No quantization method meets all constraints")
        
        # Rank by: quality first, then throughput
        candidates.sort(key=lambda c: (c["quality_loss_pct"], -c["throughput_tokens_per_sec"]))
        return candidates[0]

    def _estimate_memory(self, model_size_b: float, method: QuantMethod) -> float:
        """Estimate GPU/CPU memory in GB."""
        bits_per_param = {
            QuantMethod.FP16: 16,
            QuantMethod.GPTQ_4BIT: 4.5,  # 4-bit + overhead
            QuantMethod.GPTQ_8BIT: 8.5,
            QuantMethod.AWQ_4BIT: 4.2,   # slightly less overhead
            QuantMethod.GGUF_Q4_K_M: 4.8,
            QuantMethod.GGUF_Q5_K_M: 5.5,
            QuantMethod.GGUF_Q8_0: 8.5,
        }
        return model_size_b * bits_per_param[method] / 8  # bytes -> GB

    def _get_quality_loss(self, model_size_b: float, method: QuantMethod) -> float:
        """Perplexity increase % based on benchmarks."""
        # Larger models lose less quality from quantization
        base_loss = {
            QuantMethod.FP16: 0,
            QuantMethod.GPTQ_4BIT: 1.5,
            QuantMethod.GPTQ_8BIT: 0.3,
            QuantMethod.AWQ_4BIT: 1.0,  # AWQ typically better than GPTQ
            QuantMethod.GGUF_Q4_K_M: 1.8,
            QuantMethod.GGUF_Q5_K_M: 0.8,
            QuantMethod.GGUF_Q8_0: 0.2,
        }
        # Larger models are more robust to quantization
        size_factor = max(0.5, 1.0 - (model_size_b - 7) * 0.02)
        return base_loss[method] * size_factor

    async def quantize_model(self, model_path: str, method: QuantMethod) -> str:
        """Quantize model using selected method."""
        if method in (QuantMethod.GPTQ_4BIT, QuantMethod.GPTQ_8BIT):
            from auto_gptq import AutoGPTQForCausalLM
            bits = 4 if "4BIT" in method.name else 8
            
            model = AutoGPTQForCausalLM.from_pretrained(model_path)
            model.quantize(
                calibration_data=self._load_calibration_data(),
                bits=bits,
                group_size=128,
                desc_act=True,  # better quality, slightly slower
            )
            output_path = f"{model_path}-gptq-{bits}bit"
            model.save_quantized(output_path)
            
        elif method == QuantMethod.AWQ_4BIT:
            from awq import AutoAWQForCausalLM
            model = AutoAWQForCausalLM.from_pretrained(model_path)
            model.quantize(
                calibration_data=self._load_calibration_data(),
                quant_config={"w_bit": 4, "q_group_size": 128, "version": "gemm"}
            )
            output_path = f"{model_path}-awq-4bit"
            model.save_quantized(output_path)
        
        return output_path
```

### Quantization Comparison Table

| Method | Bits | Memory (70B) | Quality Loss | Speed (A100) | Speed (T4) | Best For |
|--------|------|-------------|-------------|-------------|-----------|----------|
| FP16 | 16 | 140 GB | 0% | 1x (baseline) | N/A | Training |
| GPTQ-4bit | 4 | 35 GB | 1-2% | 1.8x | 1x | GPU inference |
| AWQ-4bit | 4 | 33 GB | 0.5-1.5% | 2.0x | 1.1x | GPU (best quality/speed) |
| GGUF Q4_K_M | ~4.8 | 40 GB | 1-2% | 1.5x | N/A | CPU + GPU offload |
| GGUF Q5_K_M | ~5.5 | 45 GB | 0.5-1% | 1.3x | N/A | CPU (quality focus) |
| GGUF Q8_0 | 8 | 70 GB | <0.5% | 1.1x | N/A | Near-lossless CPU |

### Production Considerations
- **Calibration data**: Use 128-512 representative samples from production traffic
- **Per-layer quantization**: Keep first/last layers in higher precision (they're most sensitive)
- **Validation pipeline**: Run full eval suite on quantized model before deployment
- **A/B test**: Serve quantized model to 10% traffic; compare quality metrics vs fp16
- **Hardware matching**: AWQ optimized for NVIDIA tensor cores; GGUF for Apple Silicon/CPU

---

## Q119: Design model sharding for a 180B parameter model

### Problem
Serve 180B parameter model across multiple GPUs using tensor, pipeline, and expert parallelism.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│          180B Model Sharding Strategy                            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Option A: Tensor Parallelism (TP=8, within one node)          │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Layer N:                                             │      │
│  │  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐  │      │
│  │  │GPU0││GPU1││GPU2││GPU3││GPU4││GPU5││GPU6││GPU7│  │      │
│  │  │ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8││ 1/8│  │      │
│  │  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘  │      │
│  │  All-reduce after each layer (NVLink: 600 GB/s)      │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  Option B: Pipeline Parallelism (PP=4, across nodes)           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Node 0  │ │  Node 1  │ │  Node 2  │ │  Node 3  │         │
│  │Layer 0-23│▶│Layer24-47│▶│Layer48-71│▶│Layer72-95│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│  Micro-batching to hide pipeline bubbles                       │
│                                                                 │
│  Option C: Hybrid (TP=8 intra-node × PP=2 inter-node)         │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │   Node 0 (TP=8)      │  │   Node 1 (TP=8)      │           │
│  │   Layers 0-47        │─▶│   Layers 48-95       │           │
│  │   8 GPUs, NVLink     │  │   8 GPUs, NVLink     │           │
│  └──────────────────────┘  └──────────────────────┘           │
│  Inter-node: InfiniBand (400 Gb/s)                             │
│                                                                 │
│  Option D: Expert Parallelism (MoE models)                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Router → Expert 0 (GPU0) | Expert 1 (GPU1) | ...      │    │
│  │  Each expert: subset of FFN weights                     │    │
│  │  Only top-K experts activated per token                 │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ModelSpec:
    total_params_b: float  # 180B
    num_layers: int  # 96
    hidden_dim: int  # 12288
    num_heads: int  # 96
    is_moe: bool = False
    num_experts: int = 1
    experts_per_token: int = 1

@dataclass
class ClusterSpec:
    num_nodes: int
    gpus_per_node: int
    gpu_memory_gb: float
    intra_node_bandwidth_gbps: float  # NVLink
    inter_node_bandwidth_gbps: float  # InfiniBand

class ShardingPlanner:
    def __init__(self, model: ModelSpec, cluster: ClusterSpec):
        self.model = model
        self.cluster = cluster
        self.total_gpus = cluster.num_nodes * cluster.gpus_per_node

    def plan(self) -> dict:
        """Determine optimal sharding strategy."""
        model_memory_gb = self.model.total_params_b * 2  # bf16
        per_gpu_memory = self.cluster.gpu_memory_gb * 0.80  # leave headroom
        
        # Minimum GPUs needed just for weights
        min_gpus = int(model_memory_gb / per_gpu_memory) + 1
        
        # Strategy selection
        if min_gpus <= self.cluster.gpus_per_node:
            # Fits in one node: use tensor parallelism only
            tp = min_gpus
            pp = 1
            strategy = "tensor_parallel_only"
        elif min_gpus <= self.total_gpus:
            # Multi-node: hybrid TP + PP
            tp = self.cluster.gpus_per_node  # max TP within node (fast NVLink)
            pp = (min_gpus + tp - 1) // tp  # pipeline stages across nodes
            strategy = "hybrid_tp_pp"
        else:
            raise ValueError(f"Model requires {min_gpus} GPUs, cluster has {self.total_gpus}")

        # For MoE models: expert parallelism
        if self.model.is_moe:
            ep = min(self.model.num_experts, self.total_gpus)
            strategy = "expert_parallel"
        else:
            ep = 1

        return {
            "strategy": strategy,
            "tensor_parallel": tp,
            "pipeline_parallel": pp,
            "expert_parallel": ep,
            "data_parallel": self.total_gpus // (tp * pp),
            "memory_per_gpu_gb": model_memory_gb / (tp * pp),
            "communication_overhead": self._estimate_comm_overhead(tp, pp),
            "pipeline_bubble_fraction": (pp - 1) / (pp - 1 + self._num_microbatches()),
        }

    def _estimate_comm_overhead(self, tp: int, pp: int) -> dict:
        """Estimate communication costs."""
        # TP: 2 all-reduces per layer (forward + backward)
        # Each all-reduce: 2 * (tp-1)/tp * hidden_dim * seq_len * 2 bytes
        tp_volume_per_layer = 2 * (tp - 1) / tp * self.model.hidden_dim * 4096 * 2
        tp_time_per_layer_us = tp_volume_per_layer / (self.cluster.intra_node_bandwidth_gbps * 1e9 / 8) * 1e6
        
        # PP: send activation between stages
        pp_volume = self.model.hidden_dim * 4096 * 2  # one activation tensor
        pp_time_us = pp_volume / (self.cluster.inter_node_bandwidth_gbps * 1e9 / 8) * 1e6
        
        return {
            "tp_overhead_per_layer_us": tp_time_per_layer_us,
            "pp_overhead_per_stage_us": pp_time_us,
            "total_comm_fraction": "~15-25% for TP=8, PP=2"
        }

    def _num_microbatches(self) -> int:
        """More microbatches = less pipeline bubble."""
        return 16  # typical: 4x pipeline stages
```

### Parallelism Trade-offs

| Strategy | Latency | Throughput | Communication | Complexity |
|----------|---------|-----------|---------------|-----------|
| TP only (8 GPU) | Lowest | Good | High (all-reduce every layer) | Low |
| PP only (4 stages) | Higher (bubbles) | Good | Low (point-to-point) | Medium |
| Hybrid TP+PP | Medium | Best | Medium | High |
| Expert Parallel (MoE) | Low (sparse) | Very High | Medium (all-to-all) | High |

### Production Considerations
- **Intra-node TP**: Always max out NVLink before going inter-node (10x faster than IB)
- **Pipeline bubbles**: Use 4x microbatches per pipeline stage to keep bubble <20%
- **Failure handling**: If one GPU fails in TP group, entire group must restart; PP can isolate failures
- **Load balancing (MoE)**: Monitor expert utilization; add auxiliary loss for balanced routing
- **Scaling inference**: For more throughput, add data parallelism replicas (each replica = full TP+PP group)

---

## Q120: Design KV-cache management for long-context applications (100K+ tokens)

### Problem
Manage KV-cache for 100K+ token contexts with eviction, compression, and multi-turn optimization.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│           KV-Cache Management System (100K+ tokens)             │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                 Tiered KV-Cache                          │    │
│  │                                                         │    │
│  │  ┌──────────────────────┐  Hot: Recent tokens           │    │
│  │  │   GPU HBM (fast)     │  (last 4K tokens)            │    │
│  │  │   ~20 GB             │  Full precision, instant      │    │
│  │  └──────────────────────┘                               │    │
│  │            │ evict                                       │    │
│  │            ▼                                             │    │
│  │  ┌──────────────────────┐  Warm: Important tokens       │    │
│  │  │   GPU HBM (compress) │  (attention-scored subset)    │    │
│  │  │   ~10 GB             │  Quantized (FP8/INT4)        │    │
│  │  └──────────────────────┘                               │    │
│  │            │ evict                                       │    │
│  │            ▼                                             │    │
│  │  ┌──────────────────────┐  Cold: Bulk context           │    │
│  │  │   CPU DRAM (swap)    │  (older context)             │    │
│  │  │   ~64 GB             │  Can reload on demand         │    │
│  │  └──────────────────────┘                               │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │          Multi-Turn Optimization                        │    │
│  │  Turn 1 KV ──┐                                         │    │
│  │  Turn 2 KV ──┼──▶ Shared prefix cache                  │    │
│  │  Turn 3 KV ──┘    (reuse across turns)                  │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np

@dataclass
class KVCacheConfig:
    max_seq_len: int = 131072  # 128K tokens
    num_layers: int = 80
    num_kv_heads: int = 8  # GQA
    head_dim: int = 128
    gpu_budget_gb: float = 30  # max GPU memory for KV-cache
    page_size: int = 256  # tokens per page

class TieredKVCacheManager:
    def __init__(self, config: KVCacheConfig):
        self.config = config
        self.hot_cache = {}      # GPU: recent tokens (full precision)
        self.warm_cache = {}     # GPU: important tokens (quantized)
        self.cold_cache = {}     # CPU: swapped out tokens
        
        # Calculate capacity per tier
        bytes_per_token = (2 * config.num_layers * config.num_kv_heads * 
                          config.head_dim * 2)  # K+V, bf16
        self.hot_capacity = int(config.gpu_budget_gb * 0.6 * 1e9 / bytes_per_token)
        self.warm_capacity = int(config.gpu_budget_gb * 0.3 * 1e9 / (bytes_per_token / 4))  # 4x compression
        
    def get_kv(self, seq_id: str, position: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Retrieve KV for a position, loading from appropriate tier."""
        if position in self.hot_cache.get(seq_id, {}):
            return self.hot_cache[seq_id][position]
        elif position in self.warm_cache.get(seq_id, {}):
            # Dequantize from warm cache
            return self._dequantize(self.warm_cache[seq_id][position])
        elif position in self.cold_cache.get(seq_id, {}):
            # Load from CPU to GPU
            kv = self.cold_cache[seq_id][position].cuda(non_blocking=True)
            return kv
        return None

    def append_kv(self, seq_id: str, position: int, k: torch.Tensor, v: torch.Tensor):
        """Add new KV entry, managing eviction."""
        if seq_id not in self.hot_cache:
            self.hot_cache[seq_id] = {}
        
        self.hot_cache[seq_id][position] = (k, v)
        
        # Eviction: if hot cache full, move old tokens based on policy
        if self._hot_cache_size(seq_id) > self.hot_capacity:
            self._evict(seq_id)

    def _evict(self, seq_id: str):
        """Eviction policy: keep recent + high-attention tokens."""
        cache = self.hot_cache[seq_id]
        positions = sorted(cache.keys())
        
        # Always keep last N tokens (recent window)
        recent_window = 2048
        protected = set(positions[-recent_window:])
        
        # Score remaining by attention importance (computed during forward pass)
        eviction_candidates = [p for p in positions if p not in protected]
        
        # Move bottom 50% to warm (quantized) or cold (CPU)
        to_evict = eviction_candidates[:len(eviction_candidates) // 2]
        
        for pos in to_evict:
            k, v = cache.pop(pos)
            if self._warm_has_capacity():
                # Quantize and store in warm tier
                self.warm_cache.setdefault(seq_id, {})[pos] = self._quantize(k, v)
            else:
                # Swap to CPU
                self.cold_cache.setdefault(seq_id, {})[pos] = (k.cpu(), v.cpu())

    def _quantize(self, k: torch.Tensor, v: torch.Tensor) -> dict:
        """Quantize KV to INT4 with per-channel scaling."""
        def quantize_tensor(t):
            scale = t.abs().max(dim=-1, keepdim=True).values / 7.0  # INT4 range
            quantized = torch.clamp(torch.round(t / scale), -8, 7).to(torch.int8)
            return {"data": quantized, "scale": scale.half()}
        return {"k": quantize_tensor(k), "v": quantize_tensor(v)}

    def _dequantize(self, quantized: dict) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize from INT4 back to bf16."""
        def dequant(q):
            return (q["data"].float() * q["scale"].float()).bfloat16()
        return dequant(quantized["k"]), dequant(quantized["v"])

class MultiTurnCacheOptimizer:
    """Optimize KV-cache for multi-turn conversations."""
    
    def __init__(self, kv_manager: TieredKVCacheManager):
        self.kv_manager = kv_manager
        self.prefix_cache = {}  # system_prompt_hash -> KV-cache

    def get_or_compute_prefix(self, system_prompt: str, model) -> dict:
        """Cache KV for system prompt; shared across all conversations."""
        prompt_hash = hash(system_prompt)
        if prompt_hash in self.prefix_cache:
            return self.prefix_cache[prompt_hash]
        
        # Compute KV for system prompt once
        kv = model.prefill(system_prompt)
        self.prefix_cache[prompt_hash] = kv
        return kv

    def new_turn(self, seq_id: str, turn_input: str, model):
        """Add new turn; reuse existing KV-cache for prior turns."""
        # KV-cache from previous turns is already stored
        # Just append new turn's tokens
        existing_len = self.kv_manager.get_seq_length(seq_id)
        new_kv = model.prefill(turn_input, kv_cache=self.kv_manager.get_all(seq_id))
        
        # Append new KV entries
        for pos, (k, v) in enumerate(new_kv, start=existing_len):
            self.kv_manager.append_kv(seq_id, pos, k, v)

    def summarize_and_compress(self, seq_id: str, model):
        """For very long conversations: summarize old turns, free KV-cache."""
        seq_len = self.kv_manager.get_seq_length(seq_id)
        if seq_len > 80000:  # compress when approaching limit
            # Keep last 20K tokens as-is
            # Summarize first 60K tokens into ~2K token summary
            old_text = model.decode_from_kv(self.kv_manager, seq_id, 0, 60000)
            summary = model.summarize(old_text, max_tokens=2000)
            
            # Replace old KV-cache with summary's KV-cache
            self.kv_manager.evict_range(seq_id, 0, 60000)
            summary_kv = model.prefill(summary)
            self.kv_manager.insert_at(seq_id, 0, summary_kv)
```

### KV-Cache Memory Calculator (per sequence)

| Model | Context | Precision | Memory/Sequence | 100 Concurrent |
|-------|---------|-----------|----------------|---------------|
| Llama 70B | 4K | bf16 | 2.5 GB | 250 GB |
| Llama 70B | 128K | bf16 | 80 GB | Impossible |
| Llama 70B | 128K | INT4 (warm) | 20 GB | 2 TB (distributed) |
| Llama 70B (GQA) | 128K | bf16 | 10 GB | 1 TB |

### Eviction Policy Comparison

| Policy | Quality Impact | Memory Savings | Complexity |
|--------|---------------|---------------|-----------|
| FIFO (oldest first) | Medium (loses important early context) | High | Low |
| Attention-scored | Low (keeps what model attends to) | High | Medium |
| Sliding window + sink | Low-Medium | Very High | Low |
| H2O (Heavy Hitter Oracle) | Very Low | High | Medium |
| Learned eviction | Lowest | High | High |

### Production Considerations
- **Prefix caching**: System prompts shared across users; cache once, reuse 1000x
- **Async prefetch**: Predict which cold pages will be needed; prefetch before decode step
- **GQA/MQA**: Use models with grouped-query attention (8 KV heads vs 64); 8x memory savings
- **Session affinity**: Route same user to same GPU to reuse their KV-cache
- **TTL**: Expire KV-cache after 30min idle; recompute on next message (cheaper than storing)
