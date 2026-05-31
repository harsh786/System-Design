"""
GPU Cluster Capacity Planner
=============================
Simulates GPU cluster capacity planning for AI inference workloads.

Given a model size, target throughput, and latency SLA, this tool:
1. Calculates GPU memory requirements
2. Determines parallelism strategy
3. Computes number of GPUs needed
4. Compares cloud provider costs
5. Outputs a recommendation with rationale

Usage: python3 main.py

Staff Architect Tool: Use this to quickly estimate infrastructure requirements
before writing a formal capacity plan or cost proposal.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import math
import json


# =============================================================================
# GPU Specifications Database
# Real specs from NVIDIA datasheets
# =============================================================================

@dataclass
class GPUSpec:
    """Hardware specifications for a GPU model."""
    name: str
    memory_gb: float
    memory_bandwidth_tb_s: float  # TB/s
    fp16_tflops: float
    nvlink_bandwidth_gb_s: float  # 0 if no NVLink
    tdp_watts: int
    cost_per_hour_spot: float
    cost_per_hour_ondemand: float
    cost_per_hour_reserved_1yr: float


GPU_DATABASE = {
    "H100_SXM": GPUSpec(
        name="NVIDIA H100 SXM",
        memory_gb=80,
        memory_bandwidth_tb_s=3.35,
        fp16_tflops=1979,
        nvlink_bandwidth_gb_s=900,
        tdp_watts=700,
        cost_per_hour_spot=3.50,
        cost_per_hour_ondemand=12.26,
        cost_per_hour_reserved_1yr=7.50,
    ),
    "A100_80GB": GPUSpec(
        name="NVIDIA A100 80GB",
        memory_gb=80,
        memory_bandwidth_tb_s=2.0,
        fp16_tflops=624,
        nvlink_bandwidth_gb_s=600,
        tdp_watts=400,
        cost_per_hour_spot=1.80,
        cost_per_hour_ondemand=5.12,
        cost_per_hour_reserved_1yr=3.30,
    ),
    "A100_40GB": GPUSpec(
        name="NVIDIA A100 40GB",
        memory_gb=40,
        memory_bandwidth_tb_s=2.0,
        fp16_tflops=624,
        nvlink_bandwidth_gb_s=600,
        tdp_watts=400,
        cost_per_hour_spot=1.50,
        cost_per_hour_ondemand=4.10,
        cost_per_hour_reserved_1yr=2.70,
    ),
    "L40S": GPUSpec(
        name="NVIDIA L40S",
        memory_gb=48,
        memory_bandwidth_tb_s=0.864,
        fp16_tflops=733,
        nvlink_bandwidth_gb_s=0,  # No NVLink
        tdp_watts=350,
        cost_per_hour_spot=0.80,
        cost_per_hour_ondemand=2.35,
        cost_per_hour_reserved_1yr=1.50,
    ),
    "T4": GPUSpec(
        name="NVIDIA T4",
        memory_gb=16,
        memory_bandwidth_tb_s=0.320,
        fp16_tflops=130,
        nvlink_bandwidth_gb_s=0,
        tdp_watts=70,
        cost_per_hour_spot=0.15,
        cost_per_hour_ondemand=0.53,
        cost_per_hour_reserved_1yr=0.35,
    ),
}


# =============================================================================
# Model Specifications
# =============================================================================

@dataclass
class ModelSpec:
    """Specification of an AI model for serving."""
    name: str
    parameters_billions: float
    num_layers: int
    hidden_dim: int
    num_heads: int
    head_dim: int
    precision: str  # "fp16", "fp8", "int4"

    @property
    def bytes_per_param(self) -> float:
        return {"fp32": 4, "fp16": 2, "fp8": 1, "int4": 0.5}[self.precision]

    @property
    def model_size_gb(self) -> float:
        return self.parameters_billions * 1e9 * self.bytes_per_param / (1024**3)

    def kv_cache_per_token_bytes(self) -> float:
        """KV cache memory per token per layer."""
        # 2 (K and V) × num_heads × head_dim × bytes_per_param
        return 2 * self.num_heads * self.head_dim * 2  # KV cache always in FP16

    def kv_cache_per_sequence_gb(self, seq_len: int) -> float:
        """Total KV cache for one sequence."""
        bytes_total = seq_len * self.kv_cache_per_token_bytes() * self.num_layers
        return bytes_total / (1024**3)


MODELS = {
    "llama-7b-fp16": ModelSpec("LLaMA 7B (FP16)", 7, 32, 4096, 32, 128, "fp16"),
    "llama-7b-int4": ModelSpec("LLaMA 7B (INT4)", 7, 32, 4096, 32, 128, "int4"),
    "llama-13b-fp16": ModelSpec("LLaMA 13B (FP16)", 13, 40, 5120, 40, 128, "fp16"),
    "llama-70b-fp16": ModelSpec("LLaMA 70B (FP16)", 70, 80, 8192, 64, 128, "fp16"),
    "llama-70b-fp8": ModelSpec("LLaMA 70B (FP8)", 70, 80, 8192, 64, 128, "fp8"),
    "llama-405b-fp8": ModelSpec("LLaMA 405B (FP8)", 405, 126, 16384, 128, 128, "fp8"),
}


# =============================================================================
# Capacity Planner
# =============================================================================

@dataclass
class InferenceRequirements:
    """User-specified requirements for inference serving."""
    model_key: str
    target_throughput_tokens_per_sec: float
    latency_sla_ms: float  # p99 time-to-first-token
    max_concurrent_sequences: int
    avg_input_length: int = 1000
    avg_output_length: int = 200
    max_sequence_length: int = 4096


@dataclass
class ParallelismStrategy:
    """Chosen parallelism configuration."""
    tensor_parallel: int
    pipeline_parallel: int
    data_parallel: int  # number of replicas

    @property
    def total_gpus(self) -> int:
        return self.tensor_parallel * self.pipeline_parallel * self.data_parallel


@dataclass
class ClusterRecommendation:
    """Final recommendation output."""
    gpu_type: str
    gpu_spec: GPUSpec
    strategy: ParallelismStrategy
    total_gpus: int
    estimated_throughput: float
    estimated_latency_ms: float
    monthly_cost_spot: float
    monthly_cost_ondemand: float
    monthly_cost_reserved: float
    rationale: List[str] = field(default_factory=list)


def calculate_memory_requirements(model: ModelSpec, batch_size: int, seq_len: int) -> dict:
    """Calculate total GPU memory needed for inference."""
    model_memory_gb = model.model_size_gb
    kv_cache_gb = model.kv_cache_per_sequence_gb(seq_len) * batch_size
    # Activation memory (rough estimate: ~10% of model size for inference)
    activation_gb = model_memory_gb * 0.1
    overhead_gb = 2.0  # CUDA context, framework overhead
    total_gb = model_memory_gb + kv_cache_gb + activation_gb + overhead_gb
    return {
        "model_gb": model_memory_gb,
        "kv_cache_gb": kv_cache_gb,
        "activation_gb": activation_gb,
        "overhead_gb": overhead_gb,
        "total_gb": total_gb,
    }


def determine_parallelism(model: ModelSpec, gpu: GPUSpec, memory_needed: float) -> Optional[ParallelismStrategy]:
    """Determine minimum tensor parallelism to fit model in GPU memory."""
    # Can't use tensor parallelism without NVLink (too slow)
    max_tp = 8 if gpu.nvlink_bandwidth_gb_s > 0 else 1

    for tp in [1, 2, 4, 8]:
        if tp > max_tp:
            break
        per_gpu_memory = memory_needed / tp
        if per_gpu_memory <= gpu.memory_gb * 0.85:  # 85% usable
            return ParallelismStrategy(tensor_parallel=tp, pipeline_parallel=1, data_parallel=1)

    # If TP=8 not enough, need pipeline parallelism (multi-node)
    if gpu.nvlink_bandwidth_gb_s > 0:
        for pp in [2, 4, 8]:
            per_gpu_memory = memory_needed / (8 * pp)
            if per_gpu_memory <= gpu.memory_gb * 0.85:
                return ParallelismStrategy(tensor_parallel=8, pipeline_parallel=pp, data_parallel=1)

    return None  # Can't fit


def estimate_decode_throughput(model: ModelSpec, gpu: GPUSpec, tp: int) -> float:
    """
    Estimate tokens/second for decode phase.
    Decode is memory-bandwidth-bound: must read all weights per token.
    """
    # Effective model size per GPU
    model_bytes = model.model_size_gb * (1024**3) / tp
    # Time to read all weights = model_bytes / bandwidth
    bandwidth_bytes_per_sec = gpu.memory_bandwidth_tb_s * (1024**4)
    time_per_token_sec = model_bytes / bandwidth_bytes_per_sec
    # With batching, we amortize overhead (not weights, but attention)
    # Rough: batch of 32 gives ~80% efficiency
    base_tokens_per_sec = 1.0 / time_per_token_sec
    # Batched throughput (batch=32, ~20x improvement due to better GPU utilization)
    batched_throughput = base_tokens_per_sec * 20
    return batched_throughput


def estimate_prefill_latency(model: ModelSpec, gpu: GPUSpec, tp: int, input_len: int) -> float:
    """Estimate prefill latency in milliseconds (compute-bound)."""
    # Prefill is compute-bound: 2 * params * input_len FLOPs
    flops_needed = 2 * model.parameters_billions * 1e9 * input_len
    # Available FLOPS across TP GPUs
    available_flops = gpu.fp16_tflops * 1e12 * tp * 0.4  # 40% utilization typical
    time_sec = flops_needed / available_flops
    return time_sec * 1000  # Convert to ms


def plan_cluster(requirements: InferenceRequirements) -> List[ClusterRecommendation]:
    """Generate cluster recommendations for all viable GPU types."""
    model = MODELS[requirements.model_key]
    recommendations = []

    for gpu_key, gpu in GPU_DATABASE.items():
        # Calculate memory needs
        mem = calculate_memory_requirements(
            model,
            batch_size=min(32, requirements.max_concurrent_sequences),
            seq_len=requirements.max_sequence_length,
        )

        # Determine parallelism
        strategy = determine_parallelism(model, gpu, mem["total_gb"])
        if strategy is None:
            continue  # Can't fit on this GPU type

        # Estimate throughput per replica
        throughput_per_replica = estimate_decode_throughput(model, gpu, strategy.tensor_parallel)

        # Estimate latency
        prefill_latency = estimate_prefill_latency(
            model, gpu, strategy.tensor_parallel, requirements.avg_input_length
        )

        # Check latency SLA
        if prefill_latency > requirements.latency_sla_ms:
            # Need more TP or skip
            continue

        # Determine data parallelism (replicas) for throughput
        replicas_needed = math.ceil(
            requirements.target_throughput_tokens_per_sec / throughput_per_replica
        )
        # Add headroom (20%)
        replicas_needed = math.ceil(replicas_needed * 1.2)
        strategy.data_parallel = max(1, replicas_needed)

        total_gpus = strategy.total_gpus
        hours_per_month = 730

        rationale = []
        rationale.append(f"Model size: {model.model_size_gb:.1f} GB")
        rationale.append(f"Memory needed (with KV cache): {mem['total_gb']:.1f} GB")
        rationale.append(f"TP={strategy.tensor_parallel} fits in {gpu.memory_gb}GB × {strategy.tensor_parallel} GPUs")
        rationale.append(f"Throughput per replica: {throughput_per_replica:.0f} tok/s")
        rationale.append(f"Replicas for {requirements.target_throughput_tokens_per_sec} tok/s: {replicas_needed}")
        rationale.append(f"Prefill latency: {prefill_latency:.1f}ms (SLA: {requirements.latency_sla_ms}ms)")

        rec = ClusterRecommendation(
            gpu_type=gpu_key,
            gpu_spec=gpu,
            strategy=strategy,
            total_gpus=total_gpus,
            estimated_throughput=throughput_per_replica * replicas_needed,
            estimated_latency_ms=prefill_latency,
            monthly_cost_spot=total_gpus * gpu.cost_per_hour_spot * hours_per_month,
            monthly_cost_ondemand=total_gpus * gpu.cost_per_hour_ondemand * hours_per_month,
            monthly_cost_reserved=total_gpus * gpu.cost_per_hour_reserved_1yr * hours_per_month,
            rationale=rationale,
        )
        recommendations.append(rec)

    # Sort by reserved cost (best value)
    recommendations.sort(key=lambda r: r.monthly_cost_reserved)
    return recommendations


# =============================================================================
# Output Formatting
# =============================================================================

def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_recommendation(rec: ClusterRecommendation, rank: int):
    print(f"\n{'─'*70}")
    print(f"  Option {rank}: {rec.gpu_spec.name}")
    print(f"{'─'*70}")
    print(f"  GPU Type:          {rec.gpu_spec.name}")
    print(f"  Total GPUs:        {rec.total_gpus}")
    print(f"  Parallelism:       TP={rec.strategy.tensor_parallel}, "
          f"PP={rec.strategy.pipeline_parallel}, "
          f"DP={rec.strategy.data_parallel} replicas")
    print(f"  Est. Throughput:   {rec.estimated_throughput:.0f} tokens/sec")
    print(f"  Est. TTFT Latency: {rec.estimated_latency_ms:.1f} ms")
    print(f"\n  Monthly Cost:")
    print(f"    Spot:            ${rec.monthly_cost_spot:,.0f}")
    print(f"    On-Demand:       ${rec.monthly_cost_ondemand:,.0f}")
    print(f"    Reserved (1yr):  ${rec.monthly_cost_reserved:,.0f}")
    print(f"\n  Rationale:")
    for r in rec.rationale:
        print(f"    • {r}")


def run_scenario(name: str, requirements: InferenceRequirements):
    """Run a complete planning scenario."""
    model = MODELS[requirements.model_key]
    print_header(f"SCENARIO: {name}")
    print(f"\n  Model: {model.name} ({model.parameters_billions}B params)")
    print(f"  Model Size: {model.model_size_gb:.1f} GB")
    print(f"  Target Throughput: {requirements.target_throughput_tokens_per_sec} tokens/sec")
    print(f"  Latency SLA (TTFT): {requirements.latency_sla_ms} ms")
    print(f"  Max Concurrent Sequences: {requirements.max_concurrent_sequences}")

    recommendations = plan_cluster(requirements)

    if not recommendations:
        print("\n  ⚠ No viable GPU configuration found for these requirements.")
        return

    print(f"\n  Found {len(recommendations)} viable configurations:")

    for i, rec in enumerate(recommendations[:3], 1):  # Top 3
        print_recommendation(rec, i)

    # Final recommendation
    best = recommendations[0]
    print(f"\n{'─'*70}")
    print(f"  ★ RECOMMENDED: {best.gpu_spec.name} × {best.total_gpus}")
    print(f"    Monthly cost (reserved): ${best.monthly_cost_reserved:,.0f}")
    print(f"{'─'*70}")


# =============================================================================
# Main: Run Example Scenarios
# =============================================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    GPU CLUSTER CAPACITY PLANNER                      ║
║                                                                      ║
║  Calculates GPU requirements for AI inference workloads.             ║
║  Compares GPU types, parallelism strategies, and costs.              ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # Scenario 1: Small model, cost-sensitive
    run_scenario(
        "Startup serving 7B model (cost-optimized)",
        InferenceRequirements(
            model_key="llama-7b-fp16",
            target_throughput_tokens_per_sec=100,
            latency_sla_ms=500,
            max_concurrent_sequences=32,
        ),
    )

    # Scenario 2: Large model, production SLA
    run_scenario(
        "Enterprise serving 70B model (production SLA)",
        InferenceRequirements(
            model_key="llama-70b-fp16",
            target_throughput_tokens_per_sec=500,
            latency_sla_ms=200,
            max_concurrent_sequences=64,
        ),
    )

    # Scenario 3: Very large model
    run_scenario(
        "Frontier 405B model (research/premium tier)",
        InferenceRequirements(
            model_key="llama-405b-fp8",
            target_throughput_tokens_per_sec=100,
            latency_sla_ms=1000,
            max_concurrent_sequences=16,
            avg_input_length=2000,
        ),
    )

    # Scenario 4: Quantized for cost savings
    run_scenario(
        "7B INT4 quantized (maximum cost savings)",
        InferenceRequirements(
            model_key="llama-7b-int4",
            target_throughput_tokens_per_sec=200,
            latency_sla_ms=500,
            max_concurrent_sequences=64,
        ),
    )

    # Summary
    print_header("KEY INSIGHTS FOR STAFF ARCHITECTS")
    print("""
  1. Memory bandwidth determines decode throughput — not TFLOPS.
  2. Tensor parallelism requires NVLink — never split across PCIe-only GPUs.
  3. Quantization (INT4/FP8) can reduce GPU count by 50%+ with minimal quality loss.
  4. Reserved pricing (1yr) saves 35-40% vs on-demand — use for stable workloads.
  5. Right-sizing (matching GPU to model) is the biggest cost lever.
  6. Always add 20% headroom for traffic spikes and operational overhead.
    """)


if __name__ == "__main__":
    main()
