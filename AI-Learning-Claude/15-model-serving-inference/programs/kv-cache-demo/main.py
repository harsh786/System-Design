"""
KV Cache Demo
=============
Simulates KV cache memory usage and demonstrates PagedAttention savings.
"""

import random
from dataclasses import dataclass
from tabulate import tabulate


@dataclass
class ModelConfig:
    name: str
    num_layers: int
    num_kv_heads: int
    head_dim: int
    max_context: int


MODELS = [
    ModelConfig("Llama-3 8B", 32, 8, 128, 8192),
    ModelConfig("Llama-3 70B", 80, 8, 128, 8192),
    ModelConfig("Llama-2 13B", 40, 40, 128, 4096),
    ModelConfig("Mistral 7B", 32, 8, 128, 32768),
    ModelConfig("GPT-4 (estimated 200B)", 120, 16, 128, 128000),
]


def kv_cache_memory_bytes(model: ModelConfig, seq_len: int, batch_size: int, bytes_per_elem: int = 2) -> int:
    """Calculate KV cache memory in bytes."""
    return 2 * model.num_layers * model.num_kv_heads * model.head_dim * seq_len * batch_size * bytes_per_elem


def format_bytes(b: int) -> str:
    if b >= 1024**3:
        return f"{b / 1024**3:.2f} GB"
    elif b >= 1024**2:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024:.1f} KB"


def demo_kv_cache_scaling():
    """Show how KV cache scales with model, context, and batch size."""
    print("=" * 80)
    print("KV CACHE MEMORY CALCULATOR")
    print("=" * 80)
    print("\nFormula: 2 × layers × kv_heads × head_dim × seq_len × batch × bytes_per_elem\n")

    rows = []
    for model in MODELS:
        for ctx in [1024, 4096, 8192, 32768]:
            if ctx > model.max_context:
                continue
            for batch in [1, 8, 32]:
                mem = kv_cache_memory_bytes(model, ctx, batch)
                rows.append([model.name, ctx, batch, format_bytes(mem)])

    print(tabulate(rows, headers=["Model", "Context", "Batch", "KV Cache Memory"], tablefmt="grid"))


def demo_static_vs_paged():
    """Compare static allocation waste vs PagedAttention."""
    print("\n" + "=" * 80)
    print("STATIC ALLOCATION vs PAGEDATTENTION")
    print("=" * 80)

    model = MODELS[1]  # Llama-3 70B
    max_context = 4096
    num_requests = 32

    # Simulate requests with varying actual lengths
    random.seed(42)
    actual_lengths = [random.randint(50, 2000) for _ in range(num_requests)]

    # Static allocation: allocate max_context for every request
    static_allocated = kv_cache_memory_bytes(model, max_context, num_requests)
    static_used = sum(kv_cache_memory_bytes(model, length, 1) for length in actual_lengths)
    static_waste = static_allocated - static_used
    waste_pct = (static_waste / static_allocated) * 100

    # PagedAttention: allocate only what's needed (+ minor block overhead)
    block_size = 16  # tokens per block
    paged_blocks = sum((length + block_size - 1) // block_size for length in actual_lengths)
    paged_allocated = kv_cache_memory_bytes(model, block_size * paged_blocks // num_requests, num_requests)
    # Internal fragmentation: last block per request
    paged_waste_tokens = num_requests * (block_size // 2)  # average half-block waste
    paged_waste = kv_cache_memory_bytes(model, paged_waste_tokens, 1)
    paged_waste_pct = (paged_waste / static_used) * 100

    print(f"\nModel: {model.name}")
    print(f"Requests: {num_requests}")
    print(f"Max context: {max_context}")
    print(f"Actual lengths: min={min(actual_lengths)}, max={max(actual_lengths)}, avg={sum(actual_lengths)//num_requests}")
    print(f"\n{'Strategy':<20} {'Allocated':<15} {'Used':<15} {'Wasted':<15} {'Waste %':<10}")
    print("-" * 75)
    print(f"{'Static':<20} {format_bytes(static_allocated):<15} {format_bytes(static_used):<15} {format_bytes(static_waste):<15} {waste_pct:.1f}%")
    print(f"{'PagedAttention':<20} {format_bytes(static_used + paged_waste):<15} {format_bytes(static_used):<15} {format_bytes(paged_waste):<15} {paged_waste_pct:.1f}%")
    print(f"\nPagedAttention saves: {format_bytes(static_waste - paged_waste)} ({waste_pct - paged_waste_pct:.1f}% less waste)")


def demo_concurrency_limits():
    """Show how KV cache limits concurrent requests."""
    print("\n" + "=" * 80)
    print("CONCURRENCY LIMITS (Llama-3 70B on 2× A100-80GB)")
    print("=" * 80)

    model = MODELS[1]  # Llama-3 70B
    total_gpu_memory = 160 * 1024**3  # 160 GB
    model_weights = 140 * 1024**3  # 140 GB FP16
    overhead = 5 * 1024**3  # 5 GB
    available_for_kv = total_gpu_memory - model_weights - overhead

    print(f"\nTotal GPU memory: 160 GB (2× A100-80GB)")
    print(f"Model weights (FP16): 140 GB")
    print(f"Overhead: 5 GB")
    print(f"Available for KV cache: {format_bytes(available_for_kv)}")

    rows = []
    for ctx in [1024, 2048, 4096, 8192, 16384, 32768]:
        if ctx > model.max_context:
            continue
        kv_per_request = kv_cache_memory_bytes(model, ctx, 1)
        max_concurrent = available_for_kv // kv_per_request
        rows.append([ctx, format_bytes(kv_per_request), max_concurrent])

    print(f"\n{tabulate(rows, headers=['Context Length', 'KV/Request', 'Max Concurrent'], tablefmt='grid')}")

    # With INT8 KV cache
    print("\n--- With INT8 KV Cache (50% less memory) ---")
    rows_int8 = []
    for ctx in [1024, 2048, 4096, 8192, 16384, 32768]:
        if ctx > model.max_context:
            continue
        kv_per_request = kv_cache_memory_bytes(model, ctx, 1, bytes_per_elem=1)
        max_concurrent = available_for_kv // kv_per_request
        rows_int8.append([ctx, format_bytes(kv_per_request), max_concurrent])

    print(f"\n{tabulate(rows_int8, headers=['Context Length', 'KV/Request (INT8)', 'Max Concurrent'], tablefmt='grid')}")


def demo_prefix_caching_savings():
    """Show savings from prefix caching."""
    print("\n" + "=" * 80)
    print("PREFIX CACHING SAVINGS")
    print("=" * 80)

    model = MODELS[1]  # Llama-3 70B
    system_prompt_tokens = 500
    num_requests = 100
    avg_user_tokens = 200

    without_prefix = kv_cache_memory_bytes(model, (system_prompt_tokens + avg_user_tokens), num_requests)
    with_prefix = (
        kv_cache_memory_bytes(model, system_prompt_tokens, 1)  # shared prefix (1 copy)
        + kv_cache_memory_bytes(model, avg_user_tokens, num_requests)  # per-request
    )
    savings = without_prefix - with_prefix

    print(f"\nScenario: {num_requests} requests, {system_prompt_tokens}-token shared system prompt")
    print(f"Average user message: {avg_user_tokens} tokens")
    print(f"\nWithout prefix caching: {format_bytes(without_prefix)}")
    print(f"With prefix caching:    {format_bytes(with_prefix)}")
    print(f"Memory saved:           {format_bytes(savings)} ({savings/without_prefix*100:.1f}%)")


if __name__ == "__main__":
    demo_kv_cache_scaling()
    demo_static_vs_paged()
    demo_concurrency_limits()
    demo_prefix_caching_savings()
