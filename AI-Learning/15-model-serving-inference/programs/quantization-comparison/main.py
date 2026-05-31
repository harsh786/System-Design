"""
Quantization Comparison
=======================
Simulates quantization effects on memory, speed, quality, and cost.
"""

from dataclasses import dataclass
from tabulate import tabulate


@dataclass
class QuantConfig:
    name: str
    bits: float
    bytes_per_weight: float
    quality_loss_pct: float  # approximate benchmark degradation
    speed_multiplier: float  # relative to FP16
    method: str


QUANT_LEVELS = [
    QuantConfig("FP16", 16, 2.0, 0.0, 1.0, "baseline"),
    QuantConfig("INT8 (per-channel)", 8, 1.0, 0.1, 1.7, "PTQ"),
    QuantConfig("INT4 (GPTQ-128g)", 4, 0.5, 0.8, 2.2, "PTQ + calibration"),
    QuantConfig("INT4 (AWQ)", 4, 0.5, 0.5, 2.3, "PTQ + activation-aware"),
    QuantConfig("INT4 (RTN)", 4, 0.5, 2.5, 2.2, "PTQ + round-to-nearest"),
    QuantConfig("INT3 (GPTQ)", 3, 0.375, 4.7, 2.5, "PTQ + calibration"),
    QuantConfig("INT2 (GPTQ)", 2, 0.25, 13.8, 2.8, "PTQ + calibration"),
]

MODEL_SIZES = [7, 13, 34, 70, 180, 405]  # billions of parameters

GPU_CONFIGS = [
    {"name": "T4", "vram_gb": 16, "cost_hr": 0.35, "bw_tbs": 0.32},
    {"name": "A10G", "vram_gb": 24, "cost_hr": 1.0, "bw_tbs": 0.6},
    {"name": "L40S", "vram_gb": 48, "cost_hr": 1.5, "bw_tbs": 0.864},
    {"name": "A100-40GB", "vram_gb": 40, "cost_hr": 2.5, "bw_tbs": 1.5},
    {"name": "A100-80GB", "vram_gb": 80, "cost_hr": 3.5, "bw_tbs": 2.0},
    {"name": "H100-80GB", "vram_gb": 80, "cost_hr": 5.0, "bw_tbs": 3.35},
]


def model_memory_gb(params_b: float, bytes_per_weight: float) -> float:
    """Calculate model memory in GB."""
    return params_b * bytes_per_weight


def min_gpus_needed(memory_gb: float, gpu_vram: float, overhead_factor: float = 1.2) -> int:
    """Calculate minimum GPUs needed (with overhead for KV cache)."""
    needed = memory_gb * overhead_factor
    return max(1, int((needed + gpu_vram - 1) // gpu_vram))


def demo_memory_comparison():
    """Show memory requirements across models and quantization levels."""
    print("=" * 80)
    print("MEMORY REQUIREMENTS BY MODEL SIZE AND QUANTIZATION")
    print("=" * 80)
    print()

    headers = ["Model Size"] + [q.name for q in QUANT_LEVELS[:5]]
    rows = []
    for size in MODEL_SIZES:
        row = [f"{size}B"]
        for q in QUANT_LEVELS[:5]:
            mem = model_memory_gb(size, q.bytes_per_weight)
            row.append(f"{mem:.0f} GB")
        rows.append(row)

    print(tabulate(rows, headers=headers, tablefmt="grid"))


def demo_gpu_fitting():
    """Show which GPU configs can fit each model at different quantizations."""
    print("\n" + "=" * 80)
    print("GPU REQUIREMENTS (minimum GPUs needed)")
    print("=" * 80)
    print()

    target_model = 70  # 70B
    print(f"Model: {target_model}B parameters\n")

    headers = ["Quantization", "Memory", "T4", "A10G", "A100-40", "A100-80", "H100-80", "Monthly Cost (A100-80)"]
    rows = []
    for q in QUANT_LEVELS[:5]:
        mem = model_memory_gb(target_model, q.bytes_per_weight)
        gpu_counts = []
        for gpu in GPU_CONFIGS:
            count = min_gpus_needed(mem, gpu["vram_gb"])
            gpu_counts.append(str(count))

        # Monthly cost for A100-80GB
        a100_count = min_gpus_needed(mem, 80)
        monthly = a100_count * 3.5 * 24 * 30
        rows.append([q.name, f"{mem:.0f} GB"] + gpu_counts + [f"${monthly:,.0f}"])

    print(tabulate(rows, headers=headers, tablefmt="grid"))


def demo_quality_impact():
    """Show quality degradation at each quantization level."""
    print("\n" + "=" * 80)
    print("QUALITY IMPACT (simulated benchmark scores)")
    print("=" * 80)
    print()

    baseline_score = 68.9  # MMLU baseline for 70B

    headers = ["Quantization", "Method", "MMLU Score", "Δ from FP16", "Verdict"]
    rows = []
    for q in QUANT_LEVELS:
        score = baseline_score * (1 - q.quality_loss_pct / 100)
        delta = score - baseline_score

        if q.quality_loss_pct == 0:
            verdict = "Baseline"
        elif q.quality_loss_pct <= 0.2:
            verdict = "✓ Imperceptible"
        elif q.quality_loss_pct <= 1.0:
            verdict = "✓ Acceptable"
        elif q.quality_loss_pct <= 3.0:
            verdict = "~ Noticeable"
        elif q.quality_loss_pct <= 5.0:
            verdict = "⚠ Significant"
        else:
            verdict = "✗ Severe"

        rows.append([q.name, q.method, f"{score:.1f}%", f"{delta:+.1f}%", verdict])

    print(tabulate(rows, headers=headers, tablefmt="grid"))


def demo_speed_comparison():
    """Show inference speed at different quantization levels."""
    print("\n" + "=" * 80)
    print("INFERENCE SPEED (tokens/sec for single request decode)")
    print("=" * 80)
    print()

    # Base decode speed on H100 for 70B FP16
    base_tps = 15.0  # tokens/sec

    headers = ["Quantization", "Speed Multiplier", "Tokens/sec", "Relative"]
    rows = []
    for q in QUANT_LEVELS[:5]:
        tps = base_tps * q.speed_multiplier
        bar = "█" * int(q.speed_multiplier * 10)
        rows.append([q.name, f"{q.speed_multiplier:.1f}x", f"{tps:.0f}", bar])

    print(f"Model: 70B on H100-80GB (single request, no batching)\n")
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def demo_cost_savings():
    """Calculate total cost savings from quantization."""
    print("\n" + "=" * 80)
    print("COST SAVINGS ANALYSIS")
    print("=" * 80)
    print()

    model_size = 70
    daily_tokens = 50_000_000  # 50M tokens/day
    hours_per_day = 24

    print(f"Scenario: {model_size}B model, {daily_tokens/1e6:.0f}M tokens/day\n")

    headers = ["Quantization", "GPUs (A100-80)", "Cost/Month", "Tokens/sec", "Savings vs FP16"]
    rows = []
    fp16_cost = None

    for q in QUANT_LEVELS[:5]:
        mem = model_memory_gb(model_size, q.bytes_per_weight)
        num_gpus = min_gpus_needed(mem, 80)
        monthly_cost = num_gpus * 3.5 * hours_per_day * 30

        # Throughput with batching
        base_throughput = 1500  # tokens/sec FP16 with continuous batching
        throughput = base_throughput * q.speed_multiplier

        if fp16_cost is None:
            fp16_cost = monthly_cost
            savings = "-"
        else:
            saved = fp16_cost - monthly_cost
            savings = f"${saved:,.0f}/mo ({saved/fp16_cost*100:.0f}%)"

        rows.append([q.name, num_gpus, f"${monthly_cost:,.0f}", f"{throughput:.0f}", savings])

    print(tabulate(rows, headers=headers, tablefmt="grid"))


def demo_recommendation():
    """Provide recommendation based on use case."""
    print("\n" + "=" * 80)
    print("RECOMMENDATION ENGINE")
    print("=" * 80)

    scenarios = [
        {"name": "Medical AI (high stakes)", "quality_tolerance": 0.1, "budget": "high"},
        {"name": "Customer chatbot", "quality_tolerance": 1.0, "budget": "medium"},
        {"name": "Internal search/RAG", "quality_tolerance": 2.0, "budget": "low"},
        {"name": "Development/testing", "quality_tolerance": 3.0, "budget": "minimal"},
        {"name": "Batch processing", "quality_tolerance": 1.5, "budget": "low"},
    ]

    print()
    for scenario in scenarios:
        # Find best quantization within quality tolerance
        best = None
        for q in QUANT_LEVELS:
            if q.quality_loss_pct <= scenario["quality_tolerance"]:
                best = q  # Last one that fits = most aggressive within tolerance

        print(f"  {scenario['name']:<30} → {best.name} ({best.method})")
        print(f"    Quality loss: {best.quality_loss_pct}%, Speed: {best.speed_multiplier}x, Memory: {best.bytes_per_weight}B/param")
        print()


def main():
    demo_memory_comparison()
    demo_gpu_fitting()
    demo_quality_impact()
    demo_speed_comparison()
    demo_cost_savings()
    demo_recommendation()

    print("=" * 80)
    print("SUMMARY: INT4 (AWQ) is the best cost/quality tradeoff for most production use cases.")
    print("INT8 is the safe choice when quality is paramount. FP16 only if budget is unlimited.")
    print("=" * 80)


if __name__ == "__main__":
    main()
