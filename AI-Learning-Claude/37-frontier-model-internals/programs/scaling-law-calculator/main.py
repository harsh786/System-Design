"""
Scaling Law Calculator
======================
Predicts optimal training tokens, training cost, inference cost,
and emergent capabilities based on model size.

Uses Chinchilla scaling laws and empirical data from public models.

No external dependencies - standard library only.
"""

import math

# ============================================================
# SECTION 1: Scaling Law Constants
# ============================================================

# Chinchilla optimal: tokens = 20 * params
CHINCHILLA_RATIO = 20

# Modern over-training ratios (inference-optimal)
MODERN_RATIOS = {
    "chinchilla_optimal": 20,
    "moderate_overtrain": 100,
    "heavy_overtrain": 500,    # LLaMA-3 style
    "extreme_overtrain": 2000,  # LLaMA-3 8B style
}

# H100 specs
H100_BF16_TFLOPS = 989  # peak BF16 tensor TFLOPS
MODEL_FLOP_UTILIZATION = 0.40  # typical MFU
H100_COST_PER_HOUR = 2.50  # cloud rental $/hr

# Inference cost constants
TOKENS_PER_SECOND_PER_PARAM_B = 150  # rough: tokens/s ≈ 150/params_B for batch=1

# Known model data for calibration
KNOWN_MODELS = [
    {"name": "Phi-3 Mini", "params_B": 3.8, "tokens_T": 3.3, "cost_M": 1.0},
    {"name": "LLaMA-3 8B", "params_B": 8, "tokens_T": 15, "cost_M": 2.0},
    {"name": "Mistral 7B", "params_B": 7.3, "tokens_T": 2.0, "cost_M": 1.5},
    {"name": "LLaMA-2 13B", "params_B": 13, "tokens_T": 2.0, "cost_M": 3.0},
    {"name": "LLaMA-3 70B", "params_B": 70, "tokens_T": 15, "cost_M": 30.0},
    {"name": "LLaMA-2 70B", "params_B": 70, "tokens_T": 2.0, "cost_M": 10.0},
    {"name": "Mixtral 8x22B", "params_B": 141, "tokens_T": 4.0, "cost_M": 15.0},
    {"name": "LLaMA-3 405B", "params_B": 405, "tokens_T": 15, "cost_M": 50.0},
    {"name": "GPT-4 (est.)", "params_B": 1800, "tokens_T": 13, "cost_M": 100.0},
]

# Emergence thresholds (approximate effective compute scale)
EMERGENCE_THRESHOLDS = {
    "basic_language": 0.1,          # ~100M params
    "coherent_paragraphs": 1.0,     # ~1B
    "few_shot_learning": 10.0,      # ~10B
    "chain_of_thought": 60.0,       # ~60B
    "complex_code_gen": 100.0,      # ~100B
    "mathematical_reasoning": 100.0, # ~100B
    "theory_of_mind": 100.0,        # ~100B
    "multi_step_planning": 500.0,   # ~500B (or reasoning models)
}


# ============================================================
# SECTION 2: Core Calculations
# ============================================================

def compute_training_flops(params_B, tokens_T):
    """Estimate training FLOPs using the 6ND rule."""
    N = params_B * 1e9
    D = tokens_T * 1e12
    return 6 * N * D


def flops_to_gpu_hours(flops, gpu_tflops=H100_BF16_TFLOPS, mfu=MODEL_FLOP_UTILIZATION):
    """Convert FLOPs to GPU-hours."""
    effective_flops_per_second = gpu_tflops * 1e12 * mfu
    seconds = flops / effective_flops_per_second
    return seconds / 3600


def estimate_training_cost(gpu_hours, cost_per_hour=H100_COST_PER_HOUR):
    """Estimate training cost in USD."""
    return gpu_hours * cost_per_hour


def optimal_tokens_chinchilla(params_B):
    """Chinchilla-optimal training tokens."""
    return params_B * CHINCHILLA_RATIO  # in trillions? No, in billions
    # params_B billion * 20 = tokens in billions, convert to T
    return params_B * CHINCHILLA_RATIO / 1000  # T


def estimate_inference_throughput(params_B, batch_size=1):
    """Estimate tokens/second for inference."""
    # Rough model: throughput inversely proportional to params for batch=1
    # With batching, throughput scales sub-linearly
    base_throughput = 1000 / params_B  # very rough
    return base_throughput * math.sqrt(batch_size)


def estimate_inference_cost_per_million_tokens(params_B):
    """Estimate $/1M tokens for self-hosted inference."""
    # Based on: GPU cost / tokens generated per hour
    # Tokens/hour = throughput * 3600
    throughput = estimate_inference_throughput(params_B, batch_size=32)
    tokens_per_hour = throughput * 3600
    cost_per_hour = H100_COST_PER_HOUR * math.ceil(params_B * 2 / 80)  # GPUs needed
    cost_per_token = cost_per_hour / tokens_per_hour
    return cost_per_token * 1e6  # per million tokens


def predict_emergent_capabilities(params_B):
    """Predict which capabilities are likely present at a given scale."""
    capabilities = []
    for capability, threshold in EMERGENCE_THRESHOLDS.items():
        if params_B >= threshold:
            capabilities.append((capability, "LIKELY"))
        elif params_B >= threshold * 0.5:
            capabilities.append((capability, "POSSIBLE"))
        else:
            capabilities.append((capability, "UNLIKELY"))
    return capabilities


# ============================================================
# SECTION 3: Comparison Table
# ============================================================

def model_comparison_table():
    """Compare different model sizes across all metrics."""
    print("\n" + "=" * 90)
    print("  MODEL SIZE COMPARISON: Scaling Laws in Action")
    print("=" * 90)
    
    sizes = [1, 7, 13, 34, 70, 405]
    
    print(f"\n  {'Params':<8} {'Chinchilla':<12} {'Modern':<12} {'Train FLOPs':<14} "
          f"{'GPU-hrs':<10} {'Cost ($)':<12} {'Inf $/1M tok':<12}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*14} {'-'*10} {'-'*12} {'-'*12}")
    
    for params_B in sizes:
        chinchilla_T = params_B * CHINCHILLA_RATIO / 1000
        modern_T = params_B * 200 / 1000  # moderate over-training
        
        flops = compute_training_flops(params_B, modern_T)
        gpu_hrs = flops_to_gpu_hours(flops)
        cost = estimate_training_cost(gpu_hrs)
        inf_cost = estimate_inference_cost_per_million_tokens(params_B)
        
        def fmt_flops(f):
            exp = int(math.log10(f))
            mantissa = f / (10 ** exp)
            return f"{mantissa:.1f}e{exp}"
        
        def fmt_cost(c):
            if c >= 1e6:
                return f"${c/1e6:.1f}M"
            elif c >= 1e3:
                return f"${c/1e3:.0f}K"
            else:
                return f"${c:.0f}"
        
        print(f"  {params_B:<8} {chinchilla_T:<12.2f}T {modern_T:<12.2f}T "
              f"{fmt_flops(flops):<14} {gpu_hrs:<10.0f} {fmt_cost(cost):<12} "
              f"${inf_cost:<11.2f}")
    
    print("""
  Notes:
  - Chinchilla = compute-optimal tokens (minimizes training cost)
  - Modern = over-trained (minimizes inference cost)
  - Training cost assumes H100 @ $2.50/hr, 40% MFU
  - Inference cost assumes self-hosted, batch=32
  """)


# ============================================================
# SECTION 4: Compute-Optimal Frontier
# ============================================================

def compute_optimal_frontier():
    """Visualize the compute-optimal frontier."""
    print("\n" + "=" * 90)
    print("  COMPUTE-OPTIMAL FRONTIER")
    print("=" * 90)
    print("""
  Given a fixed compute budget, what's the optimal params/tokens split?
  
  Chinchilla law: For budget C FLOPs, optimal is:
    N_opt ∝ C^0.5  (parameters)
    D_opt ∝ C^0.5  (tokens)
  """)
    
    # Show frontier for different compute budgets
    print(f"  {'Compute Budget':<18} {'Optimal Params':<16} {'Optimal Tokens':<16} {'Like...'}")
    print(f"  {'-'*18} {'-'*16} {'-'*16} {'-'*30}")
    
    budgets = [
        (1e20, "Small experiment"),
        (1e21, "Startup training"),
        (1e22, "LLaMA-3 8B class"),
        (1e23, "LLaMA-3 70B class"),
        (1e24, "Frontier model"),
        (1e25, "GPT-4 class"),
        (1e26, "Next frontier"),
    ]
    
    for flops, description in budgets:
        # From C = 6ND and N ∝ D (Chinchilla): N = sqrt(C/120), D = sqrt(C/120)
        # More precisely: N_opt = (C / 120)^0.5 (rough)
        n_opt = math.sqrt(flops / 120)
        d_opt = flops / (6 * n_opt)
        
        def fmt_params(n):
            if n >= 1e12:
                return f"{n/1e12:.0f}T"
            elif n >= 1e9:
                return f"{n/1e9:.0f}B"
            elif n >= 1e6:
                return f"{n/1e6:.0f}M"
            else:
                return f"{n:.0f}"
        
        def fmt_tokens(d):
            if d >= 1e12:
                return f"{d/1e12:.1f}T"
            elif d >= 1e9:
                return f"{d/1e9:.0f}B"
            else:
                return f"{d/1e6:.0f}M"
        
        print(f"  {flops:.0e} FLOPs   {fmt_params(n_opt):<16} {fmt_tokens(d_opt):<16} {description}")
    
    print("""
  Important: Modern practice DEVIATES from Chinchilla-optimal!
  
  Why? Because inference cost matters more than training cost.
  A 8B model trained on 15T tokens (1875:1 ratio) costs more to train
  but saves enormously on inference vs a 70B Chinchilla-optimal model.
  """)


# ============================================================
# SECTION 5: Emergence Prediction
# ============================================================

def emergence_analysis():
    """Predict capabilities at different scales."""
    print("\n" + "=" * 90)
    print("  EMERGENT CAPABILITIES BY SCALE")
    print("=" * 90)
    
    print("""
  Which capabilities appear at which model sizes?
  (Based on empirical observations — these are APPROXIMATE)
  """)
    
    test_sizes = [0.5, 1, 3, 7, 13, 34, 70, 180, 405]
    
    capabilities_short = {
        "basic_language": "Basic language",
        "coherent_paragraphs": "Coherent text",
        "few_shot_learning": "Few-shot learning",
        "chain_of_thought": "Chain-of-thought",
        "complex_code_gen": "Complex code gen",
        "mathematical_reasoning": "Math reasoning",
        "theory_of_mind": "Theory of mind",
        "multi_step_planning": "Multi-step planning",
    }
    
    print(f"  {'Capability':<22}", end="")
    for size in test_sizes:
        print(f" {size:>5}B", end="")
    print()
    print(f"  {'-'*22}", end="")
    for _ in test_sizes:
        print(f" {'-'*5}-", end="")
    print()
    
    for cap_key, cap_name in capabilities_short.items():
        threshold = EMERGENCE_THRESHOLDS[cap_key]
        print(f"  {cap_name:<22}", end="")
        for size in test_sizes:
            if size >= threshold:
                symbol = "  ██ "
            elif size >= threshold * 0.5:
                symbol = "  ▒▒ "
            else:
                symbol = "  ·· "
            print(f"{symbol} ", end="")
        print()
    
    print(f"\n  Legend: ██ = LIKELY present  ▒▒ = POSSIBLE  ·· = UNLIKELY")
    print("""
  CAVEATS:
  1. These thresholds assume standard training — fine-tuning can lower them
  2. Reasoning models (o1) achieve some capabilities at smaller base sizes
  3. "Emergence" may be measurement artifact — always test YOUR specific task
  4. Architecture matters: MoE models may show capabilities at lower active params
  5. Distilled models (Phi-3) punch above their weight class
  """)


# ============================================================
# SECTION 6: Cost Comparison Tool
# ============================================================

def cost_comparison():
    """Compare total cost of ownership for different deployment strategies."""
    print("\n" + "=" * 90)
    print("  COST COMPARISON: Self-Hosted vs API")
    print("=" * 90)
    
    # Scenario: 100K queries/day, 1000 tokens avg per query, 12 months
    queries_per_day = 100_000
    tokens_per_query = 1000
    months = 12
    days = months * 30
    total_tokens = queries_per_day * tokens_per_query * days
    
    print(f"\n  Scenario: {queries_per_day:,} queries/day, {tokens_per_query} tokens/query, {months} months")
    print(f"  Total tokens: {total_tokens/1e9:.1f}B tokens over {months} months")
    
    print(f"\n  {'Option':<30} {'Monthly Cost':<15} {'12-Month Cost':<15} {'Latency':<12} {'Quality'}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*12} {'-'*10}")
    
    options = [
        {
            "name": "GPT-4o API",
            "cost_per_M_tokens": 7.50,  # avg input+output
            "latency": "200-500ms",
            "quality": "High",
        },
        {
            "name": "GPT-4o-mini API",
            "cost_per_M_tokens": 0.375,
            "latency": "100-300ms",
            "quality": "Good",
        },
        {
            "name": "Claude 3.5 Sonnet API",
            "cost_per_M_tokens": 9.00,
            "latency": "200-600ms",
            "quality": "High",
        },
        {
            "name": "Self-hosted 8B (1×H100)",
            "cost_per_M_tokens": 0.05,
            "latency": "50-100ms",
            "quality": "Medium",
            "fixed_monthly": 2500,
        },
        {
            "name": "Self-hosted 70B (2×H100)",
            "cost_per_M_tokens": 0.50,
            "latency": "100-300ms",
            "quality": "Good+",
            "fixed_monthly": 5000,
        },
        {
            "name": "Self-hosted 8B + RAG",
            "cost_per_M_tokens": 0.08,
            "latency": "200-400ms",
            "quality": "Good",
            "fixed_monthly": 3500,
        },
    ]
    
    for opt in options:
        monthly_tokens = queries_per_day * tokens_per_query * 30
        variable_cost = (monthly_tokens / 1e6) * opt["cost_per_M_tokens"]
        fixed = opt.get("fixed_monthly", 0)
        monthly_total = variable_cost + fixed
        yearly_total = monthly_total * 12
        
        def fmt_cost(c):
            if c >= 1e6:
                return f"${c/1e6:.1f}M"
            elif c >= 1e3:
                return f"${c/1e3:.0f}K"
            else:
                return f"${c:.0f}"
        
        print(f"  {opt['name']:<30} {fmt_cost(monthly_total):<15} {fmt_cost(yearly_total):<15} "
              f"{opt['latency']:<12} {opt['quality']}")
    
    print("""
  Key insight: At 100K queries/day, self-hosted 8B saves 95%+ vs GPT-4o API,
  but quality difference may matter. The optimal strategy is often:
    - Route simple queries → self-hosted 8B (cheap, fast)
    - Route complex queries → API frontier model (expensive, best quality)
    - Result: 80% cost savings with <5% quality loss
  """)


# ============================================================
# SECTION 7: ASCII Visualization of Scaling Curves
# ============================================================

def scaling_curve_visualization():
    """ASCII plot of loss vs compute."""
    print("\n" + "=" * 90)
    print("  SCALING CURVES: Loss vs Compute")
    print("=" * 90)
    
    print("""
  Loss (lower = better)
    │
  3.5│ *
    │  *
  3.0│   *
    │    **
  2.5│      **
    │        ***
  2.0│           ****
    │               *****
  1.5│                    ********
    │                            **********
  1.0│                                      ********************
    │
    └──────────────────────────────────────────────────────────── log(Compute)
     10^18    10^19    10^20    10^21    10^22    10^23    10^24

  The scaling law: L(C) = (C_0/C)^α + L_∞
  Where:
    L = loss (cross-entropy)
    C = compute (FLOPs)
    α ≈ 0.05 (diminishing returns)
    L_∞ ≈ 1.0 (irreducible loss / entropy of language)
  
  Key observations:
  1. Returns diminish — each 10× compute gives less improvement
  2. There's a floor (irreducible loss) you can never go below
  3. The curve is smooth — but TASK PERFORMANCE can be step-like
  4. Different tasks "unlock" at different points on this curve
  """)


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "╔" + "═" * 88 + "╗")
    print("║" + " SCALING LAW CALCULATOR ".center(88) + "║")
    print("║" + " Predicting Model Capabilities, Costs, and Optimal Configurations ".center(88) + "║")
    print("╚" + "═" * 88 + "╝")
    
    # Section 1: Model comparison table
    model_comparison_table()
    
    # Section 2: Compute-optimal frontier
    compute_optimal_frontier()
    
    # Section 3: Emergence analysis
    emergence_analysis()
    
    # Section 4: Cost comparison
    cost_comparison()
    
    # Section 5: Scaling curves
    scaling_curve_visualization()
    
    # Section 6: Summary
    print("\n" + "=" * 90)
    print("  PRACTICAL DECISION GUIDE")
    print("=" * 90)
    print("""
  Given your requirements, choose:
  
  ┌────────────────────────────────────────────────────────────────────────────────┐
  │ Need                          │ Recommended Model Size   │ Estimated Cost      │
  ├───────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ Classification/extraction     │ 1-3B fine-tuned          │ $10-100 to train    │
  │ Simple QA + RAG               │ 7-8B                     │ $0.05/1M tokens     │
  │ Code completion               │ 7-8B code-specific       │ $0.05/1M tokens     │
  │ General assistant             │ 30-70B                   │ $0.50/1M tokens     │
  │ Complex reasoning             │ API (o1/o3)              │ $15-60/1M tokens    │
  │ Maximum capability            │ API (GPT-4/Claude)       │ $3-15/1M tokens     │
  └───────────────────────────────┴──────────────────────────┴─────────────────────┘
  
  Rules of thumb:
  1. Start with the SMALLEST model that might work
  2. Fine-tuned small > general large (for specific tasks)
  3. Cost scales roughly linearly with params for inference
  4. Training cost scales as params × tokens (6ND rule)
  5. Re-evaluate every 6 months — the landscape shifts fast
  """)


if __name__ == "__main__":
    main()
