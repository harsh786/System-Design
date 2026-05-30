"""
Inference Optimization Techniques
===================================
Simulates and demonstrates key optimization strategies:
- Quantization impact simulation
- Batching strategies comparison
- Prefix caching implementation
- Speculative decoding simulation
- Context length optimization
- Prompt compression for cost savings
- Model selection by task complexity
- Warm-up strategies for cold starts
- GPU memory management patterns
"""

import time
import random
import math
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from collections import OrderedDict


# =============================================================================
# 1. QUANTIZATION IMPACT SIMULATION
# =============================================================================

@dataclass
class QuantizationProfile:
    """Model performance profile at a given quantization level."""
    name: str
    bits: int
    memory_gb: float  # Model weight memory
    relative_throughput: float  # Multiplier vs FP16 baseline
    quality_retention: float  # 1.0 = no loss, 0.95 = 5% quality drop
    perplexity_increase: float  # Absolute increase over FP16
    supported_hardware: list[str] = field(default_factory=list)


class QuantizationSimulator:
    """Simulate the impact of different quantization levels."""
    
    # Profiles for a 70B parameter model
    PROFILES_70B = {
        "fp16": QuantizationProfile("FP16", 16, 140.0, 1.0, 1.0, 0.0, ["A100", "H100", "H200"]),
        "bf16": QuantizationProfile("BF16", 16, 140.0, 1.0, 1.0, 0.0, ["A100", "H100", "H200"]),
        "fp8": QuantizationProfile("FP8 (E4M3)", 8, 70.0, 1.8, 0.998, 0.05, ["H100", "H200"]),
        "int8_w8a8": QuantizationProfile("INT8 W8A8", 8, 70.0, 1.7, 0.995, 0.08, ["A100", "H100"]),
        "int8_w8a16": QuantizationProfile("INT8 W8A16", 8, 70.0, 1.5, 0.999, 0.02, ["A100", "H100"]),
        "gptq_4bit": QuantizationProfile("GPTQ 4-bit", 4, 35.0, 2.5, 0.985, 0.3, ["A100", "H100", "L40S"]),
        "awq_4bit": QuantizationProfile("AWQ 4-bit", 4, 35.0, 2.5, 0.992, 0.15, ["A100", "H100", "L40S"]),
        "gguf_q4_k_m": QuantizationProfile("GGUF Q4_K_M", 4, 38.0, 2.2, 0.990, 0.2, ["Any"]),
        "gptq_3bit": QuantizationProfile("GPTQ 3-bit", 3, 26.0, 3.0, 0.965, 0.8, ["A100", "H100"]),
        "gguf_q2_k": QuantizationProfile("GGUF Q2_K", 2, 20.0, 3.5, 0.920, 2.0, ["Any"]),
    }
    
    def __init__(self, model_size_b: float = 70.0, base_throughput_tps: float = 35.0):
        self.model_size_b = model_size_b
        self.base_throughput = base_throughput_tps
    
    def compare_all(self, gpu_vram_gb: float = 80.0) -> list[dict]:
        """Compare all quantization levels for given GPU."""
        results = []
        
        for name, profile in self.PROFILES_70B.items():
            fits_in_memory = profile.memory_gb <= gpu_vram_gb
            kv_cache_budget = gpu_vram_gb - profile.memory_gb if fits_in_memory else 0
            
            # Estimate max concurrent sequences (assuming 1GB per 4K context sequence)
            gb_per_sequence = 1.0  # Approximate for 70B with GQA
            max_sequences = int(kv_cache_budget / gb_per_sequence) if fits_in_memory else 0
            
            throughput = self.base_throughput * profile.relative_throughput
            
            # Effective throughput with batching
            effective_throughput = throughput * min(max_sequences, 32)  # Cap at batch 32
            
            results.append({
                "quantization": profile.name,
                "bits": profile.bits,
                "memory_gb": profile.memory_gb,
                "fits_single_gpu": fits_in_memory,
                "kv_cache_budget_gb": kv_cache_budget,
                "max_concurrent_sequences": max_sequences,
                "single_stream_tps": throughput,
                "batched_throughput_tps": effective_throughput,
                "quality_retention": profile.quality_retention,
                "perplexity_increase": profile.perplexity_increase,
            })
        
        return results
    
    def print_comparison(self, gpu_vram_gb: float = 80.0):
        results = self.compare_all(gpu_vram_gb)
        
        print(f"\n{'='*80}")
        print(f"Quantization Comparison: {self.model_size_b:.0f}B Model on {gpu_vram_gb:.0f}GB GPU")
        print(f"{'='*80}")
        
        print(f"\n  {'Quant':<15} {'Bits':>4} {'Mem':>6} {'Fits':>5} {'KV$':>5} "
              f"{'MaxSeq':>6} {'TPS':>6} {'BatchTPS':>9} {'Quality':>7} {'PPL+':>5}")
        print(f"  {'-'*82}")
        
        for r in results:
            fits = "Yes" if r["fits_single_gpu"] else "No"
            print(f"  {r['quantization']:<15} {r['bits']:>4} {r['memory_gb']:>5.0f}G {fits:>5} "
                  f"{r['kv_cache_budget_gb']:>4.0f}G {r['max_concurrent_sequences']:>6} "
                  f"{r['single_stream_tps']:>5.0f} {r['batched_throughput_tps']:>8.0f} "
                  f"{r['quality_retention']:>6.1%} {r['perplexity_increase']:>5.2f}")
    
    def recommend(self, gpu_vram_gb: float = 80.0, 
                  min_quality: float = 0.99,
                  optimize_for: str = "throughput") -> dict:
        """Recommend best quantization for given constraints."""
        results = self.compare_all(gpu_vram_gb)
        
        # Filter by constraints
        valid = [r for r in results if r["fits_single_gpu"] and r["quality_retention"] >= min_quality]
        
        if not valid:
            # Relax quality constraint
            valid = [r for r in results if r["fits_single_gpu"]]
        
        if not valid:
            return {"error": "Model doesn't fit in GPU at any quantization"}
        
        if optimize_for == "throughput":
            best = max(valid, key=lambda r: r["batched_throughput_tps"])
        elif optimize_for == "quality":
            best = max(valid, key=lambda r: r["quality_retention"])
        else:  # balance
            best = max(valid, key=lambda r: r["batched_throughput_tps"] * r["quality_retention"])
        
        return {"recommendation": best["quantization"], "details": best}


# =============================================================================
# 2. BATCHING STRATEGIES COMPARISON
# =============================================================================

@dataclass
class BatchingResult:
    strategy: str
    total_requests: int
    total_time_sec: float
    throughput_rps: float
    throughput_tps: float
    avg_latency_ms: float
    p99_latency_ms: float
    gpu_utilization: float


class BatchingSimulator:
    """Compare different batching strategies."""
    
    def __init__(self, 
                 forward_pass_time_ms: float = 30.0,
                 max_batch_size: int = 64,
                 prefill_time_per_token_ms: float = 0.5):
        self.forward_pass_ms = forward_pass_time_ms
        self.max_batch = max_batch_size
        self.prefill_ms_per_token = prefill_time_per_token_ms
    
    def simulate_static_batching(self, requests: list[dict]) -> BatchingResult:
        """
        Static batching: collect batch, process all, wait for longest, repeat.
        """
        total_time = 0
        latencies = []
        batch_start = 0
        
        while batch_start < len(requests):
            batch_end = min(batch_start + self.max_batch, len(requests))
            batch = requests[batch_start:batch_end]
            
            # Time = prefill all + decode for LONGEST sequence
            max_output = max(r["output_tokens"] for r in batch)
            prefill_time = max(r["input_tokens"] for r in batch) * self.prefill_ms_per_token
            decode_time = max_output * self.forward_pass_ms
            batch_time = prefill_time + decode_time
            
            total_time += batch_time
            
            # All requests in batch have same latency (waiting for longest)
            for r in batch:
                actual_time = r["input_tokens"] * self.prefill_ms_per_token + r["output_tokens"] * self.forward_pass_ms
                latencies.append(batch_time)  # Everyone waits for longest
            
            batch_start = batch_end
        
        total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in requests)
        sorted_lat = sorted(latencies)
        
        # GPU utilization: actual compute / total time
        actual_compute_time = sum(
            r["input_tokens"] * self.prefill_ms_per_token + r["output_tokens"] * self.forward_pass_ms 
            for r in requests
        )
        
        return BatchingResult(
            strategy="Static Batching",
            total_requests=len(requests),
            total_time_sec=total_time / 1000,
            throughput_rps=len(requests) / (total_time / 1000),
            throughput_tps=total_tokens / (total_time / 1000),
            avg_latency_ms=sum(latencies) / len(latencies),
            p99_latency_ms=sorted_lat[int(len(sorted_lat) * 0.99)],
            gpu_utilization=actual_compute_time / (total_time * self.max_batch) if total_time else 0,
        )
    
    def simulate_continuous_batching(self, requests: list[dict]) -> BatchingResult:
        """
        Continuous batching: fill slots as sequences complete.
        """
        # Simulation: process requests with iteration-level scheduling
        active: list[dict] = []
        pending = list(requests)
        completed = 0
        total_time_ms = 0
        latencies = []
        total_tokens = 0
        
        for req in pending:
            req["_remaining"] = req["output_tokens"]
            req["_start_time"] = None
            req["_prefill_done"] = False
        
        step = 0
        while active or pending:
            step += 1
            
            # Fill batch
            while len(active) < self.max_batch and pending:
                req = pending.pop(0)
                req["_start_time"] = total_time_ms
                # Prefill (simplified: assume chunked, adds 1 step)
                req["_prefill_done"] = True
                active.append(req)
            
            if not active:
                break
            
            # One decode step for all active
            total_time_ms += self.forward_pass_ms
            
            # Generate one token per active request
            still_active = []
            for req in active:
                req["_remaining"] -= 1
                if req["_remaining"] <= 0:
                    latency = total_time_ms - req["_start_time"]
                    latencies.append(latency)
                    total_tokens += req["input_tokens"] + req["output_tokens"]
                    completed += 1
                else:
                    still_active.append(req)
            
            active = still_active
        
        sorted_lat = sorted(latencies) if latencies else [0]
        
        return BatchingResult(
            strategy="Continuous Batching",
            total_requests=len(requests),
            total_time_sec=total_time_ms / 1000,
            throughput_rps=len(requests) / (total_time_ms / 1000) if total_time_ms else 0,
            throughput_tps=total_tokens / (total_time_ms / 1000) if total_time_ms else 0,
            avg_latency_ms=sum(sorted_lat) / len(sorted_lat),
            p99_latency_ms=sorted_lat[int(len(sorted_lat) * 0.99)],
            gpu_utilization=0.85,  # Typically much higher with continuous batching
        )
    
    def compare(self, num_requests: int = 200):
        """Run comparison between strategies."""
        # Generate requests with varying output lengths
        requests = [
            {"input_tokens": random.randint(100, 2000), 
             "output_tokens": random.randint(10, 500)}
            for _ in range(num_requests)
        ]
        
        static = self.simulate_static_batching([dict(r) for r in requests])
        continuous = self.simulate_continuous_batching([dict(r) for r in requests])
        
        print(f"\n{'='*60}")
        print(f"Batching Strategy Comparison ({num_requests} requests)")
        print(f"{'='*60}")
        
        print(f"\n  {'Metric':<25} {'Static':>15} {'Continuous':>15} {'Improvement':>12}")
        print(f"  {'-'*70}")
        
        metrics = [
            ("Total time (sec)", static.total_time_sec, continuous.total_time_sec),
            ("Throughput (req/s)", static.throughput_rps, continuous.throughput_rps),
            ("Throughput (tok/s)", static.throughput_tps, continuous.throughput_tps),
            ("Avg Latency (ms)", static.avg_latency_ms, continuous.avg_latency_ms),
            ("P99 Latency (ms)", static.p99_latency_ms, continuous.p99_latency_ms),
            ("GPU Utilization", static.gpu_utilization, continuous.gpu_utilization),
        ]
        
        for name, s_val, c_val in metrics:
            if "Latency" in name or "time" in name:
                improvement = f"{(1 - c_val/s_val)*100:.1f}% lower" if s_val > 0 else "N/A"
            else:
                improvement = f"{(c_val/s_val - 1)*100:.1f}% higher" if s_val > 0 else "N/A"
            print(f"  {name:<25} {s_val:>13.1f} {c_val:>13.1f} {improvement:>12}")
        
        return static, continuous


# =============================================================================
# 3. PREFIX CACHING IMPLEMENTATION
# =============================================================================

class PrefixCache:
    """
    LRU cache for KV cache blocks keyed by token prefix hash.
    
    How it works:
    1. Hash the prefix tokens (system prompt + context)
    2. If hash exists in cache, reuse cached KV blocks (skip prefill)
    3. If miss, compute prefill and store result
    """
    
    def __init__(self, max_entries: int = 1000, max_memory_gb: float = 20.0):
        self.max_entries = max_entries
        self.max_memory_gb = max_memory_gb
        self.current_memory_gb = 0.0
        
        # LRU cache: hash -> (kv_blocks_placeholder, num_tokens, memory_gb)
        self.cache: OrderedDict[str, dict] = OrderedDict()
        
        # Stats
        self.hits = 0
        self.misses = 0
        self.total_tokens_saved = 0
    
    def _hash_prefix(self, tokens: list[int]) -> str:
        """Hash a token prefix for cache lookup."""
        token_bytes = bytes(str(tokens), 'utf-8')
        return hashlib.sha256(token_bytes).hexdigest()[:16]
    
    def lookup(self, prefix_tokens: list[int]) -> Optional[dict]:
        """Look up cached KV blocks for a prefix."""
        key = self._hash_prefix(prefix_tokens)
        
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            self.total_tokens_saved += len(prefix_tokens)
            return self.cache[key]
        
        self.misses += 1
        return None
    
    def store(self, prefix_tokens: list[int], kv_data: dict = None):
        """Store KV cache blocks for a prefix."""
        key = self._hash_prefix(prefix_tokens)
        
        # Estimate memory for this entry
        # ~2KB per token for 70B model KV cache (with GQA)
        entry_memory_gb = len(prefix_tokens) * 2 / (1024 * 1024)  # KB to GB
        
        # Evict if necessary
        while (len(self.cache) >= self.max_entries or 
               self.current_memory_gb + entry_memory_gb > self.max_memory_gb):
            if not self.cache:
                break
            # Evict LRU
            _, evicted = self.cache.popitem(last=False)
            self.current_memory_gb -= evicted["memory_gb"]
        
        self.cache[key] = {
            "num_tokens": len(prefix_tokens),
            "memory_gb": entry_memory_gb,
            "kv_data": kv_data,  # Placeholder for actual GPU tensors
            "created_at": time.time(),
        }
        self.current_memory_gb += entry_memory_gb
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def get_stats(self) -> dict:
        return {
            "entries": len(self.cache),
            "memory_gb": self.current_memory_gb,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "tokens_saved": self.total_tokens_saved,
            "estimated_time_saved_sec": self.total_tokens_saved * 0.5 / 1000,  # 0.5ms per token
        }


def demo_prefix_caching():
    """Demonstrate prefix caching with shared system prompts."""
    cache = PrefixCache(max_entries=100, max_memory_gb=10.0)
    
    # Common system prompts (shared across many requests)
    system_prompts = {
        "customer_support": list(range(500)),  # 500 tokens
        "code_assistant": list(range(500, 1200)),  # 700 tokens
        "medical_qa": list(range(1200, 2200)),  # 1000 tokens
    }
    
    # Simulate 1000 requests
    num_requests = 1000
    total_prefill_saved_ms = 0
    
    for i in range(num_requests):
        # 80% of requests use one of 3 system prompts
        if random.random() < 0.8:
            prompt_type = random.choice(list(system_prompts.keys()))
            prefix = system_prompts[prompt_type]
        else:
            prefix = list(range(random.randint(100, 500)))  # Unique prefix
        
        result = cache.lookup(prefix)
        if result:
            # Cache hit - skip prefill for these tokens
            tokens_saved = result["num_tokens"]
            total_prefill_saved_ms += tokens_saved * 0.5  # 0.5ms per token
        else:
            # Cache miss - compute and store
            cache.store(prefix)
    
    stats = cache.get_stats()
    
    print(f"\n{'='*60}")
    print(f"Prefix Caching Demo ({num_requests} requests)")
    print(f"{'='*60}")
    print(f"  Cache entries: {stats['entries']}")
    print(f"  Memory used: {stats['memory_gb']:.2f} GB")
    print(f"  Hit rate: {stats['hit_rate']:.1%}")
    print(f"  Tokens saved from recomputation: {stats['tokens_saved']:,}")
    print(f"  Estimated time saved: {total_prefill_saved_ms/1000:.1f} seconds")
    print(f"  Avg time saved per request: {total_prefill_saved_ms/num_requests:.1f} ms")


# =============================================================================
# 4. SPECULATIVE DECODING SIMULATION
# =============================================================================

class SpeculativeDecoder:
    """
    Simulate speculative decoding with draft + verify.
    
    Draft model: Fast, small (e.g., 1B params) - generates K candidates
    Target model: Slow, large (e.g., 70B params) - verifies in one pass
    """
    
    def __init__(self,
                 draft_model_time_ms: float = 2.0,   # Time per token for draft model
                 target_model_time_ms: float = 30.0,  # Time per forward pass for target
                 speculation_length: int = 5,          # Number of tokens to speculate
                 acceptance_rate: float = 0.78):       # Average acceptance rate
        self.draft_time = draft_model_time_ms
        self.target_time = target_model_time_ms
        self.k = speculation_length
        self.acceptance_rate = acceptance_rate
    
    def simulate_standard_decoding(self, num_tokens: int) -> dict:
        """Standard autoregressive decoding (baseline)."""
        total_time = num_tokens * self.target_time
        return {
            "method": "Standard Autoregressive",
            "tokens": num_tokens,
            "total_time_ms": total_time,
            "time_per_token_ms": self.target_time,
            "target_model_calls": num_tokens,
        }
    
    def simulate_speculative(self, num_tokens: int) -> dict:
        """Speculative decoding simulation."""
        generated = 0
        total_time = 0
        target_calls = 0
        draft_calls = 0
        
        while generated < num_tokens:
            # Draft model generates K tokens
            draft_calls += self.k
            draft_time = self.k * self.draft_time
            
            # Target model verifies all K in one pass
            target_calls += 1
            verify_time = self.target_time
            
            # How many tokens accepted?
            # Geometric distribution: first rejection at position i
            accepted = 0
            for i in range(self.k):
                if random.random() < self.acceptance_rate:
                    accepted += 1
                else:
                    break
            
            # We always get at least 1 token (resampled at rejection point)
            tokens_this_round = accepted + 1
            generated += tokens_this_round
            total_time += draft_time + verify_time
        
        effective_tpt = total_time / num_tokens
        speedup = self.target_time / effective_tpt
        
        return {
            "method": "Speculative Decoding",
            "tokens": num_tokens,
            "total_time_ms": total_time,
            "time_per_token_ms": effective_tpt,
            "target_model_calls": target_calls,
            "draft_model_calls": draft_calls,
            "avg_accepted_per_round": num_tokens / target_calls if target_calls else 0,
            "speedup_vs_standard": speedup,
        }
    
    def compare(self, num_tokens: int = 200, num_trials: int = 10):
        """Run comparison with multiple trials."""
        print(f"\n{'='*60}")
        print(f"Speculative Decoding Comparison")
        print(f"  Draft model: {self.draft_time}ms/tok, Target: {self.target_time}ms/pass")
        print(f"  Speculation length K={self.k}, Acceptance rate={self.acceptance_rate:.0%}")
        print(f"{'='*60}")
        
        standard = self.simulate_standard_decoding(num_tokens)
        
        # Average over trials
        spec_results = [self.simulate_speculative(num_tokens) for _ in range(num_trials)]
        avg_time = sum(r["total_time_ms"] for r in spec_results) / num_trials
        avg_speedup = sum(r["speedup_vs_standard"] for r in spec_results) / num_trials
        avg_accepted = sum(r["avg_accepted_per_round"] for r in spec_results) / num_trials
        avg_target_calls = sum(r["target_model_calls"] for r in spec_results) / num_trials
        
        print(f"\n  Generating {num_tokens} tokens:")
        print(f"\n  {'Metric':<30} {'Standard':>12} {'Speculative':>12}")
        print(f"  {'-'*56}")
        print(f"  {'Total time (ms)':<30} {standard['total_time_ms']:>10.0f} {avg_time:>10.0f}")
        print(f"  {'Time per token (ms)':<30} {standard['time_per_token_ms']:>10.1f} {avg_time/num_tokens:>10.1f}")
        print(f"  {'Target model calls':<30} {standard['target_model_calls']:>10} {avg_target_calls:>10.0f}")
        print(f"  {'Tokens/target call':<30} {'1.0':>12} {avg_accepted:>10.1f}")
        print(f"  {'Speedup':<30} {'1.0x':>12} {avg_speedup:>10.1f}x")
        print(f"  {'Latency reduction':<30} {'—':>12} {(1-1/avg_speedup)*100:>9.0f}%")
        
        # Show how acceptance rate affects speedup
        print(f"\n  Speedup vs Acceptance Rate (K={self.k}):")
        for rate in [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]:
            # Expected tokens per target call: sum of geometric series
            expected_accepted = sum(rate**i for i in range(self.k)) 
            # +1 for the resampled token
            expected_tokens = min(expected_accepted + 1, self.k + 1)
            time_per_round = self.k * self.draft_time + self.target_time
            effective_tpt = time_per_round / expected_tokens
            speedup = self.target_time / effective_tpt
            print(f"    α={rate:.2f}: {speedup:.2f}x speedup ({expected_tokens:.1f} tokens/round)")


# =============================================================================
# 5. CONTEXT LENGTH OPTIMIZATION
# =============================================================================

class ContextOptimizer:
    """
    Optimize context window usage to balance quality and cost.
    
    Key insight: Longer contexts don't always improve quality.
    There's a sweet spot between "too little context" and "lost in the middle."
    """
    
    def __init__(self, cost_per_1k_input_tokens: float = 0.005):
        self.cost_per_1k = cost_per_1k_input_tokens
    
    def analyze_context_efficiency(self, 
                                    max_context: int = 128000,
                                    relevant_info_tokens: int = 2000,
                                    quality_curve: str = "diminishing") -> list[dict]:
        """
        Analyze how context length affects quality and cost.
        
        Quality curves:
        - "diminishing": More context helps but with diminishing returns
        - "lost_in_middle": Quality dips for info in the middle of long contexts
        - "linear": Quality scales linearly with relevant info included
        """
        
        results = []
        context_lengths = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 128000]
        
        for ctx_len in context_lengths:
            if ctx_len > max_context:
                break
            
            # Cost
            cost = (ctx_len / 1000) * self.cost_per_1k
            
            # Quality model (normalized 0-1)
            if quality_curve == "diminishing":
                # Log curve - rapid improvement then plateau
                quality = min(1.0, 0.5 + 0.5 * math.log(1 + ctx_len / relevant_info_tokens) / math.log(10))
            elif quality_curve == "lost_in_middle":
                # Good at short, slightly worse at medium, recovers at long
                if ctx_len <= 4096:
                    quality = min(1.0, ctx_len / 4096)
                elif ctx_len <= 32768:
                    quality = 0.95 - 0.1 * (ctx_len - 4096) / 28672  # Slight dip
                else:
                    quality = 0.88 + 0.05 * (ctx_len - 32768) / 95232
            else:  # linear
                quality = min(1.0, ctx_len / (relevant_info_tokens * 4))
            
            # Quality per dollar
            quality_per_dollar = quality / cost if cost > 0 else 0
            
            results.append({
                "context_length": ctx_len,
                "cost_per_request": cost,
                "quality_score": quality,
                "quality_per_dollar": quality_per_dollar,
                "marginal_quality": 0,  # Filled below
            })
        
        # Calculate marginal quality
        for i in range(1, len(results)):
            delta_quality = results[i]["quality_score"] - results[i-1]["quality_score"]
            delta_cost = results[i]["cost_per_request"] - results[i-1]["cost_per_request"]
            results[i]["marginal_quality"] = delta_quality / delta_cost if delta_cost > 0 else 0
        
        return results
    
    def find_optimal_context(self, **kwargs) -> dict:
        """Find the context length with best quality/cost ratio."""
        results = self.analyze_context_efficiency(**kwargs)
        best = max(results, key=lambda r: r["quality_per_dollar"])
        return best
    
    def print_analysis(self, **kwargs):
        results = self.analyze_context_efficiency(**kwargs)
        best = max(results, key=lambda r: r["quality_per_dollar"])
        
        print(f"\n{'='*60}")
        print(f"Context Length Optimization")
        print(f"{'='*60}")
        
        print(f"\n  {'Context':>8} {'Cost':>8} {'Quality':>8} {'Q/$':>10} {'Marginal Q/$':>12}")
        print(f"  {'-'*50}")
        for r in results:
            marker = " ← BEST" if r["context_length"] == best["context_length"] else ""
            print(f"  {r['context_length']:>8,} ${r['cost_per_request']:>6.4f} "
                  f"{r['quality_score']:>7.3f} {r['quality_per_dollar']:>9.1f} "
                  f"{r['marginal_quality']:>11.1f}{marker}")
        
        print(f"\n  Optimal context length: {best['context_length']:,} tokens")
        print(f"  At this length: quality={best['quality_score']:.3f}, cost=${best['cost_per_request']:.4f}")


# =============================================================================
# 6. PROMPT COMPRESSION
# =============================================================================

class PromptCompressor:
    """
    Simulate prompt compression techniques for cost reduction.
    
    Techniques:
    - Remove redundant whitespace and formatting
    - Abbreviate common patterns
    - Use structured format instead of natural language
    - Prune low-relevance context
    - Token-aware truncation
    """
    
    COMPRESSION_TECHNIQUES = {
        "whitespace_cleanup": {
            "description": "Remove extra whitespace, newlines, formatting",
            "compression_ratio": 0.85,
            "quality_impact": 0.99,
        },
        "abbreviation": {
            "description": "Use shorter phrases, abbreviations",
            "compression_ratio": 0.70,
            "quality_impact": 0.97,
        },
        "structured_format": {
            "description": "Convert prose to JSON/YAML structure",
            "compression_ratio": 0.60,
            "quality_impact": 0.95,
        },
        "context_pruning": {
            "description": "Remove low-relevance retrieved documents",
            "compression_ratio": 0.50,
            "quality_impact": 0.92,
        },
        "llmlingua": {
            "description": "Model-based compression (LLMLingua/LongLLMLingua)",
            "compression_ratio": 0.35,
            "quality_impact": 0.93,
        },
    }
    
    def analyze_savings(self, original_tokens: int = 4000,
                        cost_per_1k_tokens: float = 0.005,
                        monthly_requests: int = 100_000) -> list[dict]:
        """Analyze cost savings from various compression techniques."""
        results = []
        
        for name, technique in self.COMPRESSION_TECHNIQUES.items():
            compressed_tokens = int(original_tokens * technique["compression_ratio"])
            tokens_saved = original_tokens - compressed_tokens
            
            cost_original = (original_tokens / 1000) * cost_per_1k_tokens
            cost_compressed = (compressed_tokens / 1000) * cost_per_1k_tokens
            savings_per_request = cost_original - cost_compressed
            monthly_savings = savings_per_request * monthly_requests
            
            results.append({
                "technique": name,
                "description": technique["description"],
                "compressed_tokens": compressed_tokens,
                "tokens_saved": tokens_saved,
                "compression_ratio": technique["compression_ratio"],
                "quality_retention": technique["quality_impact"],
                "savings_per_request": savings_per_request,
                "monthly_savings": monthly_savings,
                "annual_savings": monthly_savings * 12,
            })
        
        return results
    
    def print_analysis(self, **kwargs):
        results = self.analyze_savings(**kwargs)
        original = kwargs.get("original_tokens", 4000)
        
        print(f"\n{'='*60}")
        print(f"Prompt Compression Analysis (Original: {original} tokens)")
        print(f"{'='*60}")
        
        print(f"\n  {'Technique':<20} {'Tokens':>7} {'Ratio':>6} {'Quality':>7} {'$/req saved':>11} {'$/month':>10}")
        print(f"  {'-'*65}")
        for r in results:
            print(f"  {r['technique']:<20} {r['compressed_tokens']:>7,} {r['compression_ratio']:>5.0%} "
                  f"{r['quality_retention']:>6.0%} ${r['savings_per_request']:>9.5f} "
                  f"${r['monthly_savings']:>8,.0f}")


# =============================================================================
# 7. MODEL SELECTION BY TASK COMPLEXITY
# =============================================================================

class ModelRouter:
    """
    Route requests to appropriate model based on task complexity.
    
    Strategy: Use cheap models for easy tasks, expensive for hard ones.
    A lightweight classifier determines complexity.
    """
    
    def __init__(self):
        self.models = {
            "small": {
                "name": "GPT-4o-mini / LLaMA-8B",
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
                "quality_simple": 0.95,
                "quality_complex": 0.60,
                "latency_ms_per_token": 5,
            },
            "medium": {
                "name": "Claude-3.5-Sonnet / LLaMA-70B",
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "quality_simple": 0.98,
                "quality_complex": 0.85,
                "latency_ms_per_token": 15,
            },
            "large": {
                "name": "GPT-4 / Claude-3-Opus",
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03,
                "quality_simple": 0.99,
                "quality_complex": 0.95,
                "latency_ms_per_token": 25,
            },
        }
        
        # Classifier cost (tiny model or rules)
        self.classifier_cost_per_request = 0.0001
    
    def classify_complexity(self, task_features: dict) -> str:
        """
        Classify task complexity. In production, this would be a trained model.
        Features: token_count, requires_reasoning, domain_specificity, etc.
        """
        score = 0
        
        if task_features.get("requires_reasoning", False):
            score += 3
        if task_features.get("requires_creativity", False):
            score += 2
        if task_features.get("domain_specific", False):
            score += 2
        if task_features.get("multi_step", False):
            score += 3
        if task_features.get("input_tokens", 0) > 5000:
            score += 1
        
        if score <= 2:
            return "small"
        elif score <= 5:
            return "medium"
        else:
            return "large"
    
    def simulate_routing(self, tasks: list[dict]) -> dict:
        """Simulate routing a batch of tasks."""
        results = {"small": 0, "medium": 0, "large": 0}
        total_cost_routed = 0
        total_cost_always_large = 0
        total_quality_routed = 0
        total_quality_large = 0
        
        for task in tasks:
            model_tier = self.classify_complexity(task)
            results[model_tier] += 1
            
            model = self.models[model_tier]
            large_model = self.models["large"]
            
            input_tokens = task.get("input_tokens", 1000)
            output_tokens = task.get("output_tokens", 300)
            is_complex = task.get("requires_reasoning", False) or task.get("multi_step", False)
            
            # Cost
            cost = ((input_tokens / 1000) * model["cost_per_1k_input"] +
                   (output_tokens / 1000) * model["cost_per_1k_output"] +
                   self.classifier_cost_per_request)
            total_cost_routed += cost
            
            cost_large = ((input_tokens / 1000) * large_model["cost_per_1k_input"] +
                         (output_tokens / 1000) * large_model["cost_per_1k_output"])
            total_cost_always_large += cost_large
            
            # Quality
            quality = model["quality_complex"] if is_complex else model["quality_simple"]
            total_quality_routed += quality
            quality_large = large_model["quality_complex"] if is_complex else large_model["quality_simple"]
            total_quality_large += quality_large
        
        n = len(tasks)
        return {
            "routing_distribution": results,
            "total_cost_routed": total_cost_routed,
            "total_cost_always_large": total_cost_always_large,
            "cost_savings_pct": (1 - total_cost_routed / total_cost_always_large) * 100,
            "avg_quality_routed": total_quality_routed / n,
            "avg_quality_always_large": total_quality_large / n,
            "quality_gap_pct": (1 - (total_quality_routed/n) / (total_quality_large/n)) * 100,
        }
    
    def demo(self, num_tasks: int = 1000):
        """Run routing demo."""
        tasks = []
        for _ in range(num_tasks):
            task = {
                "input_tokens": random.randint(200, 5000),
                "output_tokens": random.randint(100, 1000),
                "requires_reasoning": random.random() < 0.25,
                "requires_creativity": random.random() < 0.15,
                "domain_specific": random.random() < 0.20,
                "multi_step": random.random() < 0.15,
            }
            tasks.append(task)
        
        result = self.simulate_routing(tasks)
        
        print(f"\n{'='*60}")
        print(f"Model Routing Simulation ({num_tasks} tasks)")
        print(f"{'='*60}")
        
        print(f"\n  Routing distribution:")
        for tier, count in result["routing_distribution"].items():
            model_name = self.models[tier]["name"]
            print(f"    {tier:>6}: {count:>5} ({count/num_tasks*100:.1f}%) → {model_name}")
        
        print(f"\n  Cost comparison:")
        print(f"    Always large model: ${result['total_cost_always_large']:.2f}")
        print(f"    With routing:       ${result['total_cost_routed']:.2f}")
        print(f"    Savings:            {result['cost_savings_pct']:.1f}%")
        
        print(f"\n  Quality comparison:")
        print(f"    Always large model: {result['avg_quality_always_large']:.3f}")
        print(f"    With routing:       {result['avg_quality_routed']:.3f}")
        print(f"    Quality gap:        {result['quality_gap_pct']:.1f}%")
        
        print(f"\n  Conclusion: {result['cost_savings_pct']:.0f}% cost reduction with "
              f"only {result['quality_gap_pct']:.1f}% quality reduction")


# =============================================================================
# 8. COLD START MITIGATION
# =============================================================================

class ColdStartManager:
    """
    Strategies to minimize cold start impact for GPU inference.
    """
    
    @dataclass
    class ColdStartProfile:
        strategy: str
        instance_provision_sec: float
        model_download_sec: float
        model_load_sec: float
        cuda_compile_sec: float
        warmup_sec: float
        
        @property
        def total_sec(self) -> float:
            return (self.instance_provision_sec + self.model_download_sec +
                    self.model_load_sec + self.cuda_compile_sec + self.warmup_sec)
    
    def compare_strategies(self, model_size_gb: float = 140.0) -> list:
        """Compare cold start mitigation strategies."""
        
        strategies = [
            self.ColdStartProfile(
                strategy="Naive (no optimization)",
                instance_provision_sec=90,
                model_download_sec=model_size_gb / 1.0,  # 1 GB/s from S3
                model_load_sec=model_size_gb / 5.0,  # 5 GB/s PCIe
                cuda_compile_sec=20,
                warmup_sec=5,
            ),
            self.ColdStartProfile(
                strategy="Local NVMe cache",
                instance_provision_sec=90,
                model_download_sec=0,  # Already on disk
                model_load_sec=model_size_gb / 5.0,
                cuda_compile_sec=20,
                warmup_sec=5,
            ),
            self.ColdStartProfile(
                strategy="NVMe + CUDA graphs cached",
                instance_provision_sec=90,
                model_download_sec=0,
                model_load_sec=model_size_gb / 5.0,
                cuda_compile_sec=2,  # Pre-compiled
                warmup_sec=2,
            ),
            self.ColdStartProfile(
                strategy="Pre-warmed pool (standby)",
                instance_provision_sec=0,  # Already running
                model_download_sec=0,
                model_load_sec=0,
                cuda_compile_sec=0,
                warmup_sec=0,
            ),
            self.ColdStartProfile(
                strategy="Hibernated (GPU state saved)",
                instance_provision_sec=10,
                model_download_sec=0,
                model_load_sec=model_size_gb / 20.0,  # Resume from GPU checkpoint
                cuda_compile_sec=0,
                warmup_sec=1,
            ),
            self.ColdStartProfile(
                strategy="Tensor-parallel fast load (8 GPU)",
                instance_provision_sec=90,
                model_download_sec=model_size_gb / 8.0,  # Parallel shards
                model_load_sec=model_size_gb / 40.0,  # 8 GPUs in parallel
                cuda_compile_sec=15,
                warmup_sec=3,
            ),
        ]
        
        return strategies
    
    def print_comparison(self, model_size_gb: float = 140.0):
        strategies = self.compare_strategies(model_size_gb)
        
        print(f"\n{'='*60}")
        print(f"Cold Start Strategies ({model_size_gb:.0f}GB model)")
        print(f"{'='*60}")
        
        print(f"\n  {'Strategy':<35} {'Provision':>9} {'Download':>9} {'Load':>6} {'CUDA':>5} {'Warm':>5} {'TOTAL':>7}")
        print(f"  {'-'*80}")
        
        for s in strategies:
            print(f"  {s.strategy:<35} {s.instance_provision_sec:>7.0f}s "
                  f"{s.model_download_sec:>7.0f}s {s.model_load_sec:>4.0f}s "
                  f"{s.cuda_compile_sec:>3.0f}s {s.warmup_sec:>3.0f}s {s.total_sec:>5.0f}s")
        
        # Cost of pre-warmed pool
        gpu_hourly = 10.0  # H100
        standby_cost_per_hour = gpu_hourly
        print(f"\n  Pre-warmed pool cost: ${standby_cost_per_hour:.0f}/hr per standby replica")
        print(f"  Break-even: if you'd lose >{standby_cost_per_hour:.0f}/hr in revenue during cold starts")


# =============================================================================
# 9. GPU MEMORY MANAGEMENT PATTERNS
# =============================================================================

class GPUMemoryPlanner:
    """
    Plan GPU memory allocation for inference serving.
    
    Memory consumers:
    1. Model weights
    2. KV cache
    3. Activation memory (temporary, during forward pass)
    4. CUDA overhead
    5. LoRA adapters
    """
    
    def plan_allocation(self,
                        gpu_vram_gb: float = 80.0,
                        model_size_gb: float = 35.0,  # After quantization
                        num_lora_adapters: int = 5,
                        lora_size_mb: float = 100.0,
                        target_batch_size: int = 32,
                        avg_sequence_length: int = 4096,
                        num_kv_heads: int = 8,
                        head_dim: int = 128,
                        num_layers: int = 80) -> dict:
        """Plan memory allocation and determine max batch size."""
        
        # 1. Model weights (fixed)
        model_memory = model_size_gb
        
        # 2. LoRA adapters (fixed once loaded)
        lora_memory = (num_lora_adapters * lora_size_mb) / 1024  # GB
        
        # 3. CUDA/framework overhead (fixed)
        cuda_overhead = 1.5  # GB
        
        # 4. Activation memory (per batch, temporary)
        # Rough estimate: ~2-4 MB per sequence during forward pass
        activation_per_seq_mb = 3.0
        activation_memory = (target_batch_size * activation_per_seq_mb) / 1024  # GB
        
        # 5. KV cache (per sequence)
        # 2 (K+V) × num_layers × num_kv_heads × head_dim × seq_len × 2 (fp16)
        kv_per_seq_bytes = 2 * num_layers * num_kv_heads * head_dim * avg_sequence_length * 2
        kv_per_seq_gb = kv_per_seq_bytes / (1024**3)
        kv_total = kv_per_seq_gb * target_batch_size
        
        # Total
        total_needed = model_memory + lora_memory + cuda_overhead + activation_memory + kv_total
        available_for_kv = gpu_vram_gb - model_memory - lora_memory - cuda_overhead - activation_memory
        
        # Max batch size (limited by KV cache memory)
        max_batch_by_memory = int(available_for_kv / kv_per_seq_gb) if kv_per_seq_gb > 0 else 0
        
        # Effective batch size
        effective_batch = min(target_batch_size, max_batch_by_memory)
        
        fits = total_needed <= gpu_vram_gb
        
        return {
            "gpu_vram_gb": gpu_vram_gb,
            "allocation": {
                "model_weights": model_memory,
                "lora_adapters": lora_memory,
                "cuda_overhead": cuda_overhead,
                "activations": activation_memory,
                "kv_cache": kv_total,
                "total_needed": total_needed,
                "free": gpu_vram_gb - total_needed if fits else 0,
            },
            "fits_in_memory": fits,
            "kv_per_sequence_gb": kv_per_seq_gb,
            "max_batch_size": max_batch_by_memory,
            "effective_batch_size": effective_batch,
            "utilization": total_needed / gpu_vram_gb,
            "kv_cache_pct": kv_total / gpu_vram_gb * 100,
        }
    
    def print_plan(self, **kwargs):
        plan = self.plan_allocation(**kwargs)
        
        print(f"\n{'='*60}")
        print(f"GPU Memory Allocation Plan ({plan['gpu_vram_gb']:.0f}GB VRAM)")
        print(f"{'='*60}")
        
        alloc = plan["allocation"]
        print(f"\n  {'Component':<20} {'Memory (GB)':>12} {'%':>6}")
        print(f"  {'-'*40}")
        for key, val in alloc.items():
            if key in ("total_needed", "free"):
                continue
            pct = val / plan["gpu_vram_gb"] * 100
            bar = "█" * int(pct / 2)
            print(f"  {key:<20} {val:>10.2f}  {pct:>5.1f}% {bar}")
        
        print(f"  {'-'*40}")
        print(f"  {'TOTAL USED':<20} {alloc['total_needed']:>10.2f}  {plan['utilization']*100:>5.1f}%")
        print(f"  {'FREE':<20} {alloc['free']:>10.2f}")
        
        status = "✓ FITS" if plan["fits_in_memory"] else "✗ OOM"
        print(f"\n  Status: {status}")
        print(f"  KV cache per sequence: {plan['kv_per_sequence_gb']*1024:.0f} MB")
        print(f"  Max batch size (memory-limited): {plan['max_batch_size']}")
        print(f"  Effective batch size: {plan['effective_batch_size']}")


# =============================================================================
# DEMO
# =============================================================================

def main():
    print("=" * 70)
    print("  INFERENCE OPTIMIZATION TECHNIQUES")
    print("=" * 70)
    
    # 1. Quantization
    quant_sim = QuantizationSimulator(model_size_b=70.0, base_throughput_tps=35.0)
    quant_sim.print_comparison(gpu_vram_gb=80.0)
    
    rec = quant_sim.recommend(gpu_vram_gb=80.0, min_quality=0.99)
    print(f"\n  Recommendation (≥99% quality, max throughput): {rec['recommendation']}")
    
    # 2. Batching comparison
    batch_sim = BatchingSimulator(forward_pass_time_ms=30.0, max_batch_size=32)
    batch_sim.compare(num_requests=100)
    
    # 3. Prefix caching
    demo_prefix_caching()
    
    # 4. Speculative decoding
    spec = SpeculativeDecoder(
        draft_model_time_ms=2.0,
        target_model_time_ms=30.0,
        speculation_length=5,
        acceptance_rate=0.78,
    )
    spec.compare(num_tokens=200, num_trials=20)
    
    # 5. Context length optimization
    ctx_opt = ContextOptimizer(cost_per_1k_input_tokens=0.005)
    ctx_opt.print_analysis(max_context=128000, relevant_info_tokens=2000)
    
    # 6. Prompt compression
    compressor = PromptCompressor()
    compressor.print_analysis(original_tokens=4000, cost_per_1k_tokens=0.005, monthly_requests=100_000)
    
    # 7. Model routing
    router = ModelRouter()
    router.demo(num_tasks=1000)
    
    # 8. Cold start strategies
    cold_start = ColdStartManager()
    cold_start.print_comparison(model_size_gb=140.0)
    
    # 9. GPU memory planning
    planner = GPUMemoryPlanner()
    
    print(f"\n\n{'='*70}")
    print("  GPU Memory Plans for Different Configurations")
    print(f"{'='*70}")
    
    # Scenario A: 70B INT4 on single 80GB GPU
    print("\n  --- Scenario A: LLaMA-70B INT4 on A100 80GB ---")
    planner.print_plan(gpu_vram_gb=80, model_size_gb=35, target_batch_size=32,
                       avg_sequence_length=4096, num_lora_adapters=3)
    
    # Scenario B: 70B FP16 on single 80GB (won't fit)
    print("\n  --- Scenario B: LLaMA-70B FP16 on A100 80GB (won't fit!) ---")
    planner.print_plan(gpu_vram_gb=80, model_size_gb=140, target_batch_size=8,
                       avg_sequence_length=2048, num_lora_adapters=0)
    
    # Scenario C: 8B model on A10G 24GB
    print("\n  --- Scenario C: LLaMA-8B INT4 on A10G 24GB ---")
    planner.print_plan(gpu_vram_gb=24, model_size_gb=4.5, target_batch_size=16,
                       avg_sequence_length=4096, num_kv_heads=8, num_layers=32,
                       num_lora_adapters=10, lora_size_mb=50)


if __name__ == "__main__":
    main()
