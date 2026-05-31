"""
Distributed Inference Simulator
================================
Simulates distributed inference for large language models across multiple GPUs.

Demonstrates:
1. Tensor parallel vs pipeline parallel placement
2. Request flow through distributed system
3. Throughput and latency measurement
4. GPU utilization analysis
5. Prefill/decode disaggregation (Splitwise pattern)

Usage: python3 main.py

Staff Architect Tool: Understand how parallelism choices affect latency,
throughput, and GPU efficiency for large model serving.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import random
import math
import time


# =============================================================================
# Model and Hardware Configuration
# =============================================================================

@dataclass
class ModelConfig:
    """LLM model architecture parameters."""
    name: str
    parameters_b: float  # Billions
    num_layers: int
    hidden_dim: int
    num_heads: int
    head_dim: int
    vocab_size: int = 32000
    precision_bytes: int = 2  # FP16

    @property
    def model_size_gb(self) -> float:
        return self.parameters_b * 1e9 * self.precision_bytes / (1024**3)

    @property
    def bytes_per_layer(self) -> float:
        """Approximate bytes per transformer layer."""
        return self.model_size_gb * (1024**3) / self.num_layers


@dataclass
class GPUConfig:
    """GPU hardware configuration."""
    name: str
    memory_gb: float
    bandwidth_tb_s: float  # Memory bandwidth
    nvlink_gb_s: float  # Inter-GPU bandwidth within node
    fp16_tflops: float


LLAMA_70B = ModelConfig("LLaMA-70B", 70, 80, 8192, 64, 128)
LLAMA_405B = ModelConfig("LLaMA-405B", 405, 126, 16384, 128, 128)
H100 = GPUConfig("H100 SXM", 80, 3.35, 900, 1979)


# =============================================================================
# Parallelism Configuration
# =============================================================================

class ParallelismMode(Enum):
    TENSOR_PARALLEL = "tensor_parallel"
    PIPELINE_PARALLEL = "pipeline_parallel"
    TENSOR_PLUS_PIPELINE = "tensor_plus_pipeline"


@dataclass
class ParallelConfig:
    """Parallelism configuration for distributed inference."""
    tensor_parallel: int = 1  # GPUs within a layer
    pipeline_parallel: int = 1  # Stages (layer groups)
    mode: ParallelismMode = ParallelismMode.TENSOR_PARALLEL

    @property
    def total_gpus(self) -> int:
        return self.tensor_parallel * self.pipeline_parallel


@dataclass
class InferenceStage:
    """One pipeline stage (group of layers on one TP group)."""
    stage_id: int
    layers: List[int]  # Layer indices in this stage
    gpu_ids: List[int]  # GPUs assigned (TP group)
    tp_degree: int


# =============================================================================
# Request Modeling
# =============================================================================

@dataclass
class InferenceRequest:
    """A single inference request."""
    request_id: int
    input_tokens: int
    output_tokens: int
    arrival_time_ms: float = 0
    prefill_start_ms: float = 0
    prefill_end_ms: float = 0
    decode_start_ms: float = 0
    decode_end_ms: float = 0
    tokens_generated: int = 0

    @property
    def ttft_ms(self) -> float:
        """Time to first token."""
        return self.prefill_end_ms - self.arrival_time_ms

    @property
    def total_latency_ms(self) -> float:
        return self.decode_end_ms - self.arrival_time_ms

    @property
    def tokens_per_sec(self) -> float:
        decode_time = (self.decode_end_ms - self.decode_start_ms) / 1000
        return self.output_tokens / decode_time if decode_time > 0 else 0


# =============================================================================
# Distributed Inference Engine
# =============================================================================

class DistributedInferenceEngine:
    """Simulates distributed inference with configurable parallelism."""

    def __init__(self, model: ModelConfig, gpu: GPUConfig, config: ParallelConfig):
        self.model = model
        self.gpu = gpu
        self.config = config
        self.stages = self._build_stages()
        self.completed_requests: List[InferenceRequest] = []
        self.current_time_ms = 0.0

    def _build_stages(self) -> List[InferenceStage]:
        """Divide model layers into pipeline stages."""
        layers_per_stage = self.model.num_layers // self.config.pipeline_parallel
        stages = []
        gpu_id = 0
        for s in range(self.config.pipeline_parallel):
            start_layer = s * layers_per_stage
            end_layer = start_layer + layers_per_stage
            if s == self.config.pipeline_parallel - 1:
                end_layer = self.model.num_layers  # Last stage gets remainder
            gpu_ids = list(range(gpu_id, gpu_id + self.config.tensor_parallel))
            gpu_id += self.config.tensor_parallel
            stages.append(InferenceStage(
                stage_id=s,
                layers=list(range(start_layer, end_layer)),
                gpu_ids=gpu_ids,
                tp_degree=self.config.tensor_parallel,
            ))
        return stages

    def estimate_prefill_time_ms(self, input_tokens: int) -> float:
        """
        Prefill is compute-bound: processes all input tokens in parallel.
        Time = 2 * params * tokens / (FLOPS * TP * utilization)
        """
        flops_needed = 2 * self.model.parameters_b * 1e9 * input_tokens
        available_flops = self.gpu.fp16_tflops * 1e12 * self.config.tensor_parallel * 0.4
        compute_time_ms = (flops_needed / available_flops) * 1000

        # Pipeline overhead: stages execute sequentially for prefill
        # (each stage processes all tokens, then passes activations)
        pipeline_overhead = 1.0 + (self.config.pipeline_parallel - 1) * 0.1  # 10% overhead per extra stage

        # Communication overhead (all-reduce per layer for TP)
        if self.config.tensor_parallel > 1:
            allreduce_size_bytes = input_tokens * self.model.hidden_dim * 2  # FP16
            allreduce_time_per_layer = allreduce_size_bytes / (self.gpu.nvlink_gb_s * 1e9) * 1000
            comm_time = allreduce_time_per_layer * self.model.num_layers
        else:
            comm_time = 0

        return compute_time_ms * pipeline_overhead + comm_time

    def estimate_decode_time_per_token_ms(self) -> float:
        """
        Decode is memory-bandwidth-bound: must read all weights per token.
        Time = model_size / (bandwidth * TP)
        """
        model_bytes = self.model.model_size_gb * (1024**3)
        per_gpu_bytes = model_bytes / self.config.tensor_parallel
        bandwidth_bytes_s = self.gpu.bandwidth_tb_s * (1024**4)
        time_per_token_ms = (per_gpu_bytes / bandwidth_bytes_s) * 1000

        # Pipeline adds latency (sequential stages)
        pipeline_factor = 1.0 + (self.config.pipeline_parallel - 1) * 0.3

        # All-reduce overhead for TP (small for single token)
        if self.config.tensor_parallel > 1:
            allreduce_bytes = self.model.hidden_dim * 2  # Single token
            comm_ms = (allreduce_bytes / (self.gpu.nvlink_gb_s * 1e9) * 1000) * self.model.num_layers
        else:
            comm_ms = 0

        return time_per_token_ms * pipeline_factor + comm_ms

    def process_request(self, request: InferenceRequest) -> InferenceRequest:
        """Simulate processing a single request."""
        request.arrival_time_ms = self.current_time_ms
        request.prefill_start_ms = self.current_time_ms

        # Prefill phase
        prefill_time = self.estimate_prefill_time_ms(request.input_tokens)
        request.prefill_end_ms = request.prefill_start_ms + prefill_time
        request.decode_start_ms = request.prefill_end_ms

        # Decode phase (one token at a time)
        decode_per_token = self.estimate_decode_time_per_token_ms()
        total_decode_time = decode_per_token * request.output_tokens
        request.decode_end_ms = request.decode_start_ms + total_decode_time
        request.tokens_generated = request.output_tokens

        self.current_time_ms = request.decode_end_ms
        self.completed_requests.append(request)
        return request

    def process_batch(self, requests: List[InferenceRequest], batch_size: int = 32) -> List[InferenceRequest]:
        """Simulate batch processing with continuous batching."""
        results = []
        # Simplified: process in batches
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            # With batching, decode time is amortized
            for req in batch:
                req.arrival_time_ms = self.current_time_ms
                req.prefill_start_ms = self.current_time_ms

                prefill_time = self.estimate_prefill_time_ms(req.input_tokens)
                req.prefill_end_ms = req.prefill_start_ms + prefill_time
                req.decode_start_ms = req.prefill_end_ms

                # Batched decode: amortize weight reads across batch
                decode_per_token = self.estimate_decode_time_per_token_ms()
                # Batching efficiency: weight reads shared across batch
                batch_efficiency = min(len(batch), batch_size) * 0.8
                effective_decode_time = decode_per_token * req.output_tokens / batch_efficiency
                req.decode_end_ms = req.decode_start_ms + effective_decode_time
                req.tokens_generated = req.output_tokens
                results.append(req)

            # Advance time by longest request in batch
            if batch:
                max_end = max(r.decode_end_ms for r in batch)
                self.current_time_ms = max_end

        self.completed_requests.extend(results)
        return results

    def get_throughput_tokens_per_sec(self) -> float:
        """Calculate observed throughput."""
        if not self.completed_requests:
            return 0
        total_tokens = sum(r.output_tokens for r in self.completed_requests)
        total_time_sec = (self.current_time_ms - self.completed_requests[0].arrival_time_ms) / 1000
        return total_tokens / total_time_sec if total_time_sec > 0 else 0

    def get_gpu_utilization(self) -> Dict:
        """Estimate GPU utilization breakdown."""
        decode_time_per_token = self.estimate_decode_time_per_token_ms()
        # Decode is bandwidth-bound → compute utilization is low
        model_bytes = self.model.model_size_gb * (1024**3) / self.config.tensor_parallel
        flops_per_token = 2 * self.model.parameters_b * 1e9 / self.config.tensor_parallel
        time_for_compute = flops_per_token / (self.gpu.fp16_tflops * 1e12) * 1000
        compute_util_decode = time_for_compute / decode_time_per_token if decode_time_per_token > 0 else 0

        return {
            "compute_utilization_prefill": 0.40,  # Typical
            "compute_utilization_decode": min(compute_util_decode, 1.0),
            "memory_bandwidth_utilization_decode": 0.85,  # Near max
            "nvlink_utilization": 0.3 if self.config.tensor_parallel > 1 else 0,
        }


# =============================================================================
# Prefill/Decode Disaggregation
# =============================================================================

@dataclass
class DisaggregatedConfig:
    """Configuration for prefill/decode disaggregation."""
    prefill_gpus: int
    prefill_tp: int
    decode_gpus: int
    decode_tp: int
    kv_transfer_bandwidth_gb_s: float = 50  # InfiniBand or NVMe-oF


class DisaggregatedEngine:
    """Simulates Splitwise-style prefill/decode disaggregation."""

    def __init__(self, model: ModelConfig, gpu: GPUConfig, config: DisaggregatedConfig):
        self.model = model
        self.gpu = gpu
        self.config = config

        # Separate engines for prefill and decode
        self.prefill_engine = DistributedInferenceEngine(
            model, gpu, ParallelConfig(tensor_parallel=config.prefill_tp)
        )
        self.decode_engine = DistributedInferenceEngine(
            model, gpu, ParallelConfig(tensor_parallel=config.decode_tp)
        )

    def estimate_kv_transfer_time_ms(self, seq_len: int) -> float:
        """Time to transfer KV cache from prefill to decode workers."""
        # KV cache size: 2 * layers * heads * head_dim * seq_len * 2 bytes
        kv_bytes = 2 * self.model.num_layers * self.model.num_heads * self.model.head_dim * seq_len * 2
        transfer_time = kv_bytes / (self.config.kv_transfer_bandwidth_gb_s * 1e9) * 1000
        return transfer_time

    def process_request(self, request: InferenceRequest) -> Dict:
        """Process with disaggregated prefill/decode."""
        # Prefill on prefill workers
        prefill_time = self.prefill_engine.estimate_prefill_time_ms(request.input_tokens)

        # KV cache transfer
        kv_transfer_time = self.estimate_kv_transfer_time_ms(request.input_tokens)

        # Decode on decode workers
        decode_per_token = self.decode_engine.estimate_decode_time_per_token_ms()
        total_decode_time = decode_per_token * request.output_tokens

        ttft = prefill_time + kv_transfer_time
        total_time = ttft + total_decode_time

        return {
            "prefill_ms": prefill_time,
            "kv_transfer_ms": kv_transfer_time,
            "ttft_ms": ttft,
            "decode_ms": total_decode_time,
            "total_ms": total_time,
            "decode_tokens_per_sec": request.output_tokens / (total_decode_time / 1000),
        }


# =============================================================================
# Simulation Scenarios
# =============================================================================

def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def scenario_parallelism_comparison():
    """Compare TP vs PP vs TP+PP for 70B model."""
    print_header("SCENARIO 1: Parallelism Strategy Comparison (70B Model)")

    configs = [
        ("TP=4 (single node)", ParallelConfig(tensor_parallel=4, pipeline_parallel=1, mode=ParallelismMode.TENSOR_PARALLEL)),
        ("TP=8 (single node)", ParallelConfig(tensor_parallel=8, pipeline_parallel=1, mode=ParallelismMode.TENSOR_PARALLEL)),
        ("PP=2, TP=4 (2 nodes)", ParallelConfig(tensor_parallel=4, pipeline_parallel=2, mode=ParallelismMode.TENSOR_PLUS_PIPELINE)),
        ("PP=4, TP=2 (4 nodes)", ParallelConfig(tensor_parallel=2, pipeline_parallel=4, mode=ParallelismMode.TENSOR_PLUS_PIPELINE)),
    ]

    request = InferenceRequest(request_id=1, input_tokens=1000, output_tokens=200)

    print(f"\n  Model: {LLAMA_70B.name} ({LLAMA_70B.model_size_gb:.0f} GB)")
    print(f"  GPU: {H100.name}")
    print(f"  Request: {request.input_tokens} input tokens → {request.output_tokens} output tokens")
    print(f"\n  {'Config':<25} {'GPUs':<6} {'Prefill':<12} {'Decode/tok':<12} {'Total':<12} {'Tok/s':<8}")
    print(f"  {'─'*75}")

    for name, config in configs:
        engine = DistributedInferenceEngine(LLAMA_70B, H100, config)
        prefill = engine.estimate_prefill_time_ms(request.input_tokens)
        decode_per_tok = engine.estimate_decode_time_per_token_ms()
        total = prefill + decode_per_tok * request.output_tokens
        tps = request.output_tokens / (decode_per_tok * request.output_tokens / 1000)

        print(f"  {name:<25} {config.total_gpus:<6} {prefill:<12.1f} {decode_per_tok:<12.2f} {total:<12.0f} {tps:<8.1f}")

    print(f"""
  Analysis:
  • TP=4: Best balance of latency and GPU count for 70B model
  • TP=8: Lower latency but diminishing returns (communication overhead)
  • PP=2,TP=4: Allows scaling across nodes but adds pipeline latency
  • PP=4,TP=2: High pipeline latency, only use when memory-constrained
  
  Rule: TP within NVLink node, PP only when model doesn't fit in one node.
    """)


def scenario_throughput_analysis():
    """Analyze throughput with batching."""
    print_header("SCENARIO 2: Batching Impact on Throughput")

    config = ParallelConfig(tensor_parallel=4)
    engine = DistributedInferenceEngine(LLAMA_70B, H100, config)

    batch_sizes = [1, 4, 8, 16, 32, 64]

    print(f"\n  Model: {LLAMA_70B.name}, TP=4 on H100")
    print(f"  Measuring throughput at different batch sizes")
    print(f"\n  {'Batch':<8} {'Tok/s (output)':<18} {'Latency/req (ms)':<18} {'GPU BW Util':<12}")
    print(f"  {'─'*56}")

    for bs in batch_sizes:
        # With batching, weight reads are amortized across batch
        decode_per_token_unbatched = engine.estimate_decode_time_per_token_ms()
        # Batched: time per token stays same (bandwidth-bound) but total throughput = batch × single
        # In reality, up to a point where KV cache fills GPU memory
        throughput = bs / (decode_per_token_unbatched / 1000)  # tokens/s across batch
        latency_per_req = decode_per_token_unbatched * 200  # 200 output tokens
        bw_util = min(0.95, 0.5 + bs * 0.015)  # Utilization improves with batch

        print(f"  {bs:<8} {throughput:<18.0f} {latency_per_req:<18.0f} {bw_util:<12.0%}")

    print(f"""
  Key Insight: Batching increases THROUGHPUT (tokens/s) without increasing
  per-request LATENCY (for decode). This is because decode is bandwidth-bound:
  reading weights once serves the entire batch.
  
  Limit: KV cache memory. Batch=64 with 4K context on 70B model needs ~170GB KV cache.
  With TP=4 (320GB total), max practical batch ≈ 32-48 before OOM.
    """)


def scenario_disaggregation():
    """Compare unified vs disaggregated prefill/decode."""
    print_header("SCENARIO 3: Prefill/Decode Disaggregation (Splitwise)")

    print(f"""
  Problem: Prefill (compute-bound) and decode (bandwidth-bound) compete
  for GPU resources. Long prefills block decode for all concurrent users.
  
  Solution: Separate prefill and decode onto different GPU pools.
    """)

    request = InferenceRequest(request_id=1, input_tokens=2000, output_tokens=200)

    # Unified (standard)
    unified_engine = DistributedInferenceEngine(LLAMA_70B, H100, ParallelConfig(tensor_parallel=4))
    unified_prefill = unified_engine.estimate_prefill_time_ms(request.input_tokens)
    unified_decode_per_tok = unified_engine.estimate_decode_time_per_token_ms()
    unified_total = unified_prefill + unified_decode_per_tok * request.output_tokens

    # Disaggregated
    disagg_config = DisaggregatedConfig(
        prefill_gpus=4, prefill_tp=4,
        decode_gpus=4, decode_tp=4,
        kv_transfer_bandwidth_gb_s=50,  # InfiniBand NDR
    )
    disagg_engine = DisaggregatedEngine(LLAMA_70B, H100, disagg_config)
    disagg_result = disagg_engine.process_request(request)

    print(f"\n  Request: {request.input_tokens} input → {request.output_tokens} output tokens")
    print(f"\n  {'Metric':<30} {'Unified (TP=4)':<20} {'Disaggregated':<20}")
    print(f"  {'─'*70}")
    print(f"  {'Prefill time (ms)':<30} {unified_prefill:<20.1f} {disagg_result['prefill_ms']:<20.1f}")
    print(f"  {'KV transfer (ms)':<30} {'N/A':<20} {disagg_result['kv_transfer_ms']:<20.1f}")
    print(f"  {'TTFT (ms)':<30} {unified_prefill:<20.1f} {disagg_result['ttft_ms']:<20.1f}")
    print(f"  {'Decode time (ms)':<30} {unified_decode_per_tok * request.output_tokens:<20.0f} {disagg_result['decode_ms']:<20.0f}")
    print(f"  {'Total (ms)':<30} {unified_total:<20.0f} {disagg_result['total_ms']:<20.0f}")
    print(f"  {'Total GPUs':<30} {'4':<20} {'8 (4+4)':<20}")

    print(f"""
  Trade-offs:
  • Disaggregation adds KV transfer latency ({disagg_result['kv_transfer_ms']:.1f}ms)
  • But prefill workers are free immediately after transfer → higher prefill throughput
  • Decode workers not blocked by long prefills → stable decode latency
  • Cost: 2× GPUs but each specialized for its workload phase
  
  When to use disaggregation:
  • Long prompts (>2000 tokens) with strict TTFT SLA
  • High concurrency (>100 concurrent requests)
  • Mixed prompt lengths causing head-of-line blocking
  
  When NOT to use:
  • Low concurrency (<10 requests)
  • Short prompts where prefill is <50ms
  • KV transfer overhead exceeds the benefit
    """)


def scenario_utilization_analysis():
    """Show GPU utilization breakdown."""
    print_header("SCENARIO 4: GPU Utilization Analysis")

    configs = [
        ("TP=1 (single GPU)", ParallelConfig(tensor_parallel=1)),
        ("TP=4", ParallelConfig(tensor_parallel=4)),
        ("TP=8", ParallelConfig(tensor_parallel=8)),
    ]

    # Use smaller model for single GPU
    models = [
        (LLAMA_70B, "70B"),
    ]

    print(f"\n  GPU: {H100.name}")
    print(f"  Model: {LLAMA_70B.name}")
    print(f"\n  {'Config':<20} {'Compute (Prefill)':<20} {'Compute (Decode)':<20} {'BW Util (Decode)':<18}")
    print(f"  {'─'*78}")

    for name, config in configs:
        if config.tensor_parallel == 1 and LLAMA_70B.model_size_gb > H100.memory_gb:
            print(f"  {name:<20} {'N/A (OOM)':<20} {'N/A (OOM)':<20} {'N/A':<18}")
            continue
        engine = DistributedInferenceEngine(LLAMA_70B, H100, config)
        util = engine.get_gpu_utilization()
        print(f"  {name:<20} {util['compute_utilization_prefill']:<20.0%} "
              f"{util['compute_utilization_decode']:<20.1%} "
              f"{util['memory_bandwidth_utilization_decode']:<18.0%}")

    print(f"""
  Key Insight:
  • Prefill: ~40% compute utilization (limited by memory access patterns)
  • Decode: <10% compute utilization (bandwidth-bound, GPU cores mostly idle!)
  • Memory bandwidth: ~85% utilized during decode (the real bottleneck)
  
  This is why:
  1. More TFLOPS doesn't help decode → bandwidth is the bottleneck
  2. Batching helps → amortize weight reads across sequences
  3. Quantization helps → fewer bytes to read per token
  4. Speculative decoding helps → verify multiple tokens per weight read
    """)


# =============================================================================
# Main
# =============================================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              DISTRIBUTED INFERENCE SIMULATOR                         ║
║                                                                      ║
║  Models tensor parallelism, pipeline parallelism, batching,          ║
║  and prefill/decode disaggregation for large LLM serving.            ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    scenario_parallelism_comparison()
    scenario_throughput_analysis()
    scenario_disaggregation()
    scenario_utilization_analysis()

    print_header("KEY INSIGHTS FOR STAFF ARCHITECTS")
    print("""
  1. TENSOR PARALLELISM within NVLink node is optimal for latency.
     Never TP across slow interconnects (Ethernet/PCIe).

  2. PIPELINE PARALLELISM adds latency but enables multi-node serving.
     Only use when model doesn't fit in one node's GPU memory.

  3. DECODE IS MEMORY-BANDWIDTH-BOUND, not compute-bound.
     GPU compute utilization during decode is typically <10%.
     This means: quantization and batching are the key optimizations.

  4. BATCHING increases throughput linearly (up to memory limit)
     without increasing per-request latency for decode.

  5. DISAGGREGATION (Splitwise) eliminates prefill/decode interference
     at the cost of KV transfer latency and 2× GPUs.
     Worth it at scale (>16 GPUs, >100 concurrent users).

  6. RIGHT-SIZE PARALLELISM: TP=4 for 70B is optimal.
     TP=8 has diminishing returns due to communication overhead.
    """)


if __name__ == "__main__":
    main()
