"""
Comprehensive Cost Model for LLM Inference
============================================
Covers:
- Per-request cost breakdown calculator
- Provider cost comparison (OpenAI, Anthropic, Azure, self-hosted)
- Self-hosted GPU TCO calculator
- Managed vs self-hosted breakeven analysis
- Cost optimization simulator
- Cost per successful task calculation
- Token efficiency metrics
- Cost forecasting based on growth
- ROI calculation for AI systems
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import math


# =============================================================================
# 1. PROVIDER PRICING DATABASE
# =============================================================================

@dataclass
class ModelPricing:
    """Pricing for a specific model from a provider."""
    provider: str
    model_name: str
    input_cost_per_1k_tokens: float  # USD
    output_cost_per_1k_tokens: float  # USD
    # Optional pricing dimensions
    embedding_cost_per_1k_tokens: float = 0.0
    image_cost_per_image: float = 0.0
    # Rate limits
    requests_per_minute: int = 500
    tokens_per_minute: int = 200_000
    # Performance characteristics
    avg_ttft_ms: float = 500.0  # Time to first token
    avg_tps: float = 50.0  # Tokens per second output
    context_window: int = 128_000
    max_output_tokens: int = 4096


# Current pricing as of late 2024 (update as needed)
PROVIDER_PRICING = {
    # OpenAI
    "gpt-4-turbo": ModelPricing("openai", "gpt-4-turbo", 0.01, 0.03, context_window=128000),
    "gpt-4o": ModelPricing("openai", "gpt-4o", 0.005, 0.015, context_window=128000),
    "gpt-4o-mini": ModelPricing("openai", "gpt-4o-mini", 0.00015, 0.0006, context_window=128000),
    "gpt-3.5-turbo": ModelPricing("openai", "gpt-3.5-turbo", 0.0005, 0.0015, context_window=16385),
    "text-embedding-3-small": ModelPricing("openai", "text-embedding-3-small", 0.00002, 0.0, embedding_cost_per_1k_tokens=0.00002),
    "text-embedding-3-large": ModelPricing("openai", "text-embedding-3-large", 0.00013, 0.0, embedding_cost_per_1k_tokens=0.00013),
    
    # Anthropic
    "claude-3.5-sonnet": ModelPricing("anthropic", "claude-3.5-sonnet", 0.003, 0.015, context_window=200000),
    "claude-3-opus": ModelPricing("anthropic", "claude-3-opus", 0.015, 0.075, context_window=200000),
    "claude-3-haiku": ModelPricing("anthropic", "claude-3-haiku", 0.00025, 0.00125, context_window=200000),
    
    # Google
    "gemini-1.5-pro": ModelPricing("google", "gemini-1.5-pro", 0.00125, 0.005, context_window=2000000),
    "gemini-1.5-flash": ModelPricing("google", "gemini-1.5-flash", 0.000075, 0.0003, context_window=1000000),
    
    # Self-hosted (cost per token based on TCO calculation)
    "llama-70b-self-hosted": ModelPricing("self-hosted", "llama-70b", 0.0009, 0.0009, context_window=8192),
    "llama-8b-self-hosted": ModelPricing("self-hosted", "llama-8b", 0.0002, 0.0002, context_window=8192),
    "mixtral-8x7b-self-hosted": ModelPricing("self-hosted", "mixtral-8x7b", 0.0005, 0.0005, context_window=32768),
}


# =============================================================================
# 2. PER-REQUEST COST BREAKDOWN CALCULATOR
# =============================================================================

@dataclass
class RequestCostBreakdown:
    """Detailed cost breakdown for a single request."""
    # Token costs
    llm_input_cost: float = 0.0
    llm_output_cost: float = 0.0
    embedding_cost: float = 0.0
    reranker_cost: float = 0.0
    
    # Infrastructure costs (amortized per request)
    vector_db_cost: float = 0.0
    cache_infra_cost: float = 0.0
    network_cost: float = 0.0
    
    # External costs
    tool_api_costs: float = 0.0
    
    # Operational costs (amortized)
    observability_cost: float = 0.0
    guardrail_cost: float = 0.0
    human_review_cost: float = 0.0  # For escalation/review
    
    @property
    def total_cost(self) -> float:
        return (self.llm_input_cost + self.llm_output_cost + self.embedding_cost +
                self.reranker_cost + self.vector_db_cost + self.cache_infra_cost +
                self.network_cost + self.tool_api_costs + self.observability_cost +
                self.guardrail_cost + self.human_review_cost)
    
    @property
    def llm_cost(self) -> float:
        return self.llm_input_cost + self.llm_output_cost
    
    @property
    def retrieval_cost(self) -> float:
        return self.embedding_cost + self.reranker_cost + self.vector_db_cost
    
    def summary(self) -> str:
        lines = [
            f"{'Component':<25} {'Cost':>10} {'%':>6}",
            f"{'-'*43}",
            f"{'LLM Input':<25} ${self.llm_input_cost:>8.6f} {self.llm_input_cost/self.total_cost*100:>5.1f}%",
            f"{'LLM Output':<25} ${self.llm_output_cost:>8.6f} {self.llm_output_cost/self.total_cost*100:>5.1f}%",
            f"{'Embedding':<25} ${self.embedding_cost:>8.6f} {self.embedding_cost/self.total_cost*100:>5.1f}%",
            f"{'Reranker':<25} ${self.reranker_cost:>8.6f} {self.reranker_cost/self.total_cost*100:>5.1f}%",
            f"{'Vector DB':<25} ${self.vector_db_cost:>8.6f} {self.vector_db_cost/self.total_cost*100:>5.1f}%",
            f"{'Tool/API Calls':<25} ${self.tool_api_costs:>8.6f} {self.tool_api_costs/self.total_cost*100:>5.1f}%",
            f"{'Observability':<25} ${self.observability_cost:>8.6f} {self.observability_cost/self.total_cost*100:>5.1f}%",
            f"{'Guardrails':<25} ${self.guardrail_cost:>8.6f} {self.guardrail_cost/self.total_cost*100:>5.1f}%",
            f"{'Human Review':<25} ${self.human_review_cost:>8.6f} {self.human_review_cost/self.total_cost*100:>5.1f}%",
            f"{'Cache Infra':<25} ${self.cache_infra_cost:>8.6f} {self.cache_infra_cost/self.total_cost*100:>5.1f}%",
            f"{'Network':<25} ${self.network_cost:>8.6f} {self.network_cost/self.total_cost*100:>5.1f}%",
            f"{'-'*43}",
            f"{'TOTAL':<25} ${self.total_cost:>8.6f} {'100.0%':>6}",
        ]
        return "\n".join(lines)


class RequestCostCalculator:
    """Calculate per-request cost for various pipeline configurations."""
    
    def __init__(self, 
                 llm_model: str = "gpt-4o",
                 embedding_model: str = "text-embedding-3-small",
                 monthly_request_volume: int = 100_000):
        self.llm_pricing = PROVIDER_PRICING[llm_model]
        self.embedding_pricing = PROVIDER_PRICING.get(embedding_model)
        self.monthly_volume = monthly_request_volume
        
        # Infrastructure costs (monthly, amortized per request)
        self.monthly_vector_db_cost = 500.0  # e.g., Pinecone/Weaviate
        self.monthly_cache_cost = 200.0  # Redis/Memcached
        self.monthly_observability_cost = 300.0  # Datadog/Grafana
        self.monthly_network_cost = 100.0
    
    def calculate(self,
                  input_tokens: int = 2000,
                  output_tokens: int = 500,
                  embedding_tokens: int = 50,
                  num_retrieved_docs: int = 10,
                  reranker_tokens: int = 5000,
                  num_tool_calls: int = 0,
                  tool_cost_per_call: float = 0.001,
                  uses_guardrails: bool = True,
                  human_review_rate: float = 0.05,
                  human_review_cost: float = 2.0) -> RequestCostBreakdown:
        """Calculate complete cost breakdown for a request."""
        
        breakdown = RequestCostBreakdown()
        
        # LLM costs
        breakdown.llm_input_cost = (input_tokens / 1000) * self.llm_pricing.input_cost_per_1k_tokens
        breakdown.llm_output_cost = (output_tokens / 1000) * self.llm_pricing.output_cost_per_1k_tokens
        
        # Embedding cost
        if self.embedding_pricing:
            breakdown.embedding_cost = (embedding_tokens / 1000) * self.embedding_pricing.embedding_cost_per_1k_tokens
        
        # Reranker cost (using a cross-encoder, often priced per token pair)
        reranker_cost_per_1k = 0.002  # Cohere reranker pricing
        breakdown.reranker_cost = (reranker_tokens / 1000) * reranker_cost_per_1k
        
        # Amortized infrastructure costs
        breakdown.vector_db_cost = self.monthly_vector_db_cost / self.monthly_volume
        breakdown.cache_infra_cost = self.monthly_cache_cost / self.monthly_volume
        breakdown.network_cost = self.monthly_network_cost / self.monthly_volume
        breakdown.observability_cost = self.monthly_observability_cost / self.monthly_volume
        
        # Tool/API calls
        breakdown.tool_api_costs = num_tool_calls * tool_cost_per_call
        
        # Guardrails (input + output moderation)
        if uses_guardrails:
            # Approximate: run input and output through a small classifier
            guardrail_tokens = input_tokens + output_tokens
            breakdown.guardrail_cost = (guardrail_tokens / 1000) * 0.0002  # Cheap model
        
        # Human review (amortized across all requests)
        breakdown.human_review_cost = human_review_rate * human_review_cost
        
        return breakdown
    
    def calculate_with_caching(self, cache_hit_rate: float = 0.3, **kwargs) -> RequestCostBreakdown:
        """Calculate cost accounting for semantic/response caching."""
        full_cost = self.calculate(**kwargs)
        
        # If cache hit, only pay for cache lookup, not LLM
        effective_llm_input = full_cost.llm_input_cost * (1 - cache_hit_rate)
        effective_llm_output = full_cost.llm_output_cost * (1 - cache_hit_rate)
        
        cached = RequestCostBreakdown(
            llm_input_cost=effective_llm_input,
            llm_output_cost=effective_llm_output,
            embedding_cost=full_cost.embedding_cost,  # Still need to embed for cache lookup
            reranker_cost=full_cost.reranker_cost * (1 - cache_hit_rate),
            vector_db_cost=full_cost.vector_db_cost,
            cache_infra_cost=full_cost.cache_infra_cost * 1.5,  # Higher cache infra cost
            network_cost=full_cost.network_cost,
            tool_api_costs=full_cost.tool_api_costs * (1 - cache_hit_rate),
            observability_cost=full_cost.observability_cost,
            guardrail_cost=full_cost.guardrail_cost * (1 - cache_hit_rate * 0.5),
            human_review_cost=full_cost.human_review_cost,
        )
        return cached


# =============================================================================
# 3. SELF-HOSTED GPU TCO CALCULATOR
# =============================================================================

@dataclass
class GPUSpec:
    name: str
    vram_gb: float
    bf16_tflops: float
    memory_bandwidth_tb_s: float
    tdp_watts: float
    purchase_price: float  # USD
    cloud_hourly_price: float  # USD/hr (for comparison)


GPU_SPECS = {
    "A100_40GB": GPUSpec("A100 40GB", 40, 312, 1.6, 300, 12000, 3.5),
    "A100_80GB": GPUSpec("A100 80GB", 80, 312, 2.0, 300, 18000, 4.5),
    "H100_SXM": GPUSpec("H100 SXM", 80, 990, 3.35, 700, 35000, 10.0),
    "H200": GPUSpec("H200", 141, 990, 4.8, 700, 45000, 13.0),
    "L40S": GPUSpec("L40S", 48, 366, 0.864, 350, 8000, 2.5),
    "A10G": GPUSpec("A10G", 24, 125, 0.6, 150, 3500, 1.2),
    "MI300X": GPUSpec("MI300X", 192, 1300, 5.3, 750, 15000, 8.0),
}


@dataclass
class TCOConfig:
    """Configuration for TCO calculation."""
    num_gpus: int = 8
    gpu_type: str = "H100_SXM"
    amortization_years: int = 3
    
    # Power and cooling
    power_cost_per_kwh: float = 0.10  # USD
    pue: float = 1.3  # Power Usage Effectiveness (cooling overhead)
    
    # Networking
    network_cost_per_gpu_monthly: float = 200.0  # InfiniBand/RoCE
    
    # Rack and facility
    rack_cost_monthly: float = 1500.0  # Colocation
    gpus_per_rack: int = 8
    
    # Operations
    ops_fte_per_100_gpus: float = 1.0
    ops_salary_annual: float = 200000.0
    
    # Software
    software_licenses_monthly: float = 500.0  # Per cluster
    
    # Redundancy
    spare_ratio: float = 0.1  # 10% spare GPUs
    
    # Utilization target
    target_utilization: float = 0.75


class TCOCalculator:
    """Calculate Total Cost of Ownership for self-hosted GPU inference."""
    
    def __init__(self, config: TCOConfig):
        self.config = config
        self.gpu_spec = GPU_SPECS[config.gpu_type]
    
    def calculate_annual_tco(self) -> dict:
        """Calculate full annual TCO breakdown."""
        c = self.config
        gpu = self.gpu_spec
        
        # Hardware amortization
        total_gpus = int(c.num_gpus * (1 + c.spare_ratio))
        hardware_cost = total_gpus * gpu.purchase_price
        # Server/chassis (roughly 30% of GPU cost for networking, CPU, RAM, NVMe)
        server_cost = hardware_cost * 0.3
        annual_hardware = (hardware_cost + server_cost) / c.amortization_years
        
        # Power
        gpu_power_kw = (gpu.tdp_watts * total_gpus) / 1000
        total_power_kw = gpu_power_kw * c.pue  # Include cooling
        # Add server overhead (~20% more)
        total_power_kw *= 1.2
        annual_power = total_power_kw * 8760 * c.power_cost_per_kwh
        
        # Networking
        annual_network = c.network_cost_per_gpu_monthly * total_gpus * 12
        
        # Facility
        num_racks = math.ceil(total_gpus / c.gpus_per_rack)
        annual_facility = num_racks * c.rack_cost_monthly * 12
        
        # Operations
        ops_headcount = (total_gpus / 100) * c.ops_fte_per_100_gpus
        annual_ops = ops_headcount * c.ops_salary_annual
        
        # Software
        annual_software = c.software_licenses_monthly * 12
        
        # Total
        annual_total = (annual_hardware + annual_power + annual_network + 
                       annual_facility + annual_ops + annual_software)
        
        # Per-GPU metrics
        per_gpu_annual = annual_total / c.num_gpus  # Divide by usable GPUs
        per_gpu_hourly = per_gpu_annual / 8760
        
        return {
            "annual_total": annual_total,
            "breakdown": {
                "hardware_amortized": annual_hardware,
                "power_and_cooling": annual_power,
                "networking": annual_network,
                "facility": annual_facility,
                "operations": annual_ops,
                "software": annual_software,
            },
            "per_gpu": {
                "annual": per_gpu_annual,
                "monthly": per_gpu_annual / 12,
                "hourly": per_gpu_hourly,
            },
            "comparison": {
                "cloud_hourly_per_gpu": gpu.cloud_hourly_price,
                "self_hosted_hourly_per_gpu": per_gpu_hourly,
                "savings_pct": (1 - per_gpu_hourly / gpu.cloud_hourly_price) * 100,
            },
            "specs": {
                "total_gpus": total_gpus,
                "usable_gpus": c.num_gpus,
                "total_vram_tb": total_gpus * gpu.vram_gb / 1024,
                "total_power_kw": total_power_kw,
            }
        }
    
    def cost_per_token(self, model_throughput_tokens_per_sec_per_gpu: float) -> dict:
        """Calculate cost per token given throughput."""
        tco = self.calculate_annual_tco()
        c = self.config
        
        # Effective throughput considering utilization
        effective_tps = (model_throughput_tokens_per_sec_per_gpu * 
                        c.num_gpus * c.target_utilization)
        
        # Tokens per year
        tokens_per_year = effective_tps * 3600 * 24 * 365
        
        # Cost per token
        cost_per_token = tco["annual_total"] / tokens_per_year
        cost_per_1k_tokens = cost_per_token * 1000
        
        return {
            "cost_per_token": cost_per_token,
            "cost_per_1k_tokens": cost_per_1k_tokens,
            "effective_throughput_tps": effective_tps,
            "tokens_per_year": tokens_per_year,
            "annual_tco": tco["annual_total"],
        }
    
    def print_report(self):
        """Print formatted TCO report."""
        tco = self.calculate_annual_tco()
        
        print(f"\n{'='*60}")
        print(f"GPU TCO Report: {self.config.num_gpus}× {self.gpu_spec.name}")
        print(f"{'='*60}")
        
        print(f"\n  Annual Total: ${tco['annual_total']:,.0f}")
        print(f"\n  Breakdown:")
        for component, cost in tco["breakdown"].items():
            pct = cost / tco["annual_total"] * 100
            print(f"    {component:<25} ${cost:>12,.0f}  ({pct:>5.1f}%)")
        
        print(f"\n  Per GPU:")
        print(f"    Annual:  ${tco['per_gpu']['annual']:>10,.0f}")
        print(f"    Monthly: ${tco['per_gpu']['monthly']:>10,.0f}")
        print(f"    Hourly:  ${tco['per_gpu']['hourly']:>10.2f}")
        
        print(f"\n  vs Cloud ({self.gpu_spec.name} @ ${self.gpu_spec.cloud_hourly_price}/hr):")
        print(f"    Self-hosted: ${tco['comparison']['self_hosted_hourly_per_gpu']:.2f}/hr")
        print(f"    Cloud:       ${tco['comparison']['cloud_hourly_per_gpu']:.2f}/hr")
        print(f"    Savings:     {tco['comparison']['savings_pct']:.1f}%")
        
        # Token cost at various throughputs
        print(f"\n  Cost per 1K tokens at various throughputs:")
        for tps in [500, 1000, 2000, 4000]:
            token_cost = self.cost_per_token(tps)
            print(f"    {tps} tok/s/GPU → ${token_cost['cost_per_1k_tokens']:.5f}/1K tokens")


# =============================================================================
# 4. MANAGED vs SELF-HOSTED BREAKEVEN ANALYSIS
# =============================================================================

class BreakevenAnalyzer:
    """Determine when self-hosting becomes cheaper than managed APIs."""
    
    def __init__(self, managed_model: str = "gpt-4o", gpu_type: str = "H100_SXM"):
        self.managed_pricing = PROVIDER_PRICING[managed_model]
        self.gpu_type = gpu_type
        self.gpu_spec = GPU_SPECS[gpu_type]
    
    def find_breakeven(self,
                       avg_input_tokens: int = 2000,
                       avg_output_tokens: int = 500,
                       self_hosted_throughput_per_gpu: float = 2000,
                       num_gpus: int = 8) -> dict:
        """Find the monthly request volume where self-hosting breaks even."""
        
        # Managed cost per request
        managed_cost_per_req = (
            (avg_input_tokens / 1000) * self.managed_pricing.input_cost_per_1k_tokens +
            (avg_output_tokens / 1000) * self.managed_pricing.output_cost_per_1k_tokens
        )
        
        # Self-hosted monthly cost (fixed)
        tco_config = TCOConfig(num_gpus=num_gpus, gpu_type=self.gpu_type)
        tco_calc = TCOCalculator(tco_config)
        tco = tco_calc.calculate_annual_tco()
        monthly_fixed_cost = tco["annual_total"] / 12
        
        # Self-hosted capacity (requests per month)
        tokens_per_request = avg_input_tokens + avg_output_tokens
        effective_tps = self_hosted_throughput_per_gpu * num_gpus * 0.75  # 75% util
        max_requests_per_month = (effective_tps / tokens_per_request) * 3600 * 24 * 30
        
        # Self-hosted variable cost per request (basically 0, all fixed)
        self_hosted_var_cost = 0.001  # Tiny marginal cost (power)
        
        # Breakeven: managed_cost * N = monthly_fixed + self_hosted_var * N
        # N = monthly_fixed / (managed_cost - self_hosted_var)
        if managed_cost_per_req <= self_hosted_var_cost:
            breakeven_requests = float('inf')  # Never breaks even
        else:
            breakeven_requests = monthly_fixed_cost / (managed_cost_per_req - self_hosted_var_cost)
        
        # Cost comparison at various volumes
        volumes = [10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000]
        comparison = []
        for vol in volumes:
            managed_total = vol * managed_cost_per_req
            self_hosted_total = monthly_fixed_cost + (vol * self_hosted_var_cost)
            # Cap self-hosted at capacity
            if vol > max_requests_per_month:
                self_hosted_total = float('inf')  # Need more GPUs
            
            comparison.append({
                "monthly_requests": vol,
                "managed_cost": managed_total,
                "self_hosted_cost": self_hosted_total,
                "cheaper": "self-hosted" if self_hosted_total < managed_total else "managed",
                "savings": managed_total - self_hosted_total,
            })
        
        return {
            "breakeven_monthly_requests": int(breakeven_requests),
            "managed_cost_per_request": managed_cost_per_req,
            "self_hosted_monthly_fixed": monthly_fixed_cost,
            "self_hosted_max_capacity": int(max_requests_per_month),
            "comparison": comparison,
        }
    
    def print_analysis(self, **kwargs):
        """Print formatted breakeven analysis."""
        result = self.find_breakeven(**kwargs)
        
        print(f"\n{'='*60}")
        print(f"Breakeven Analysis: {self.managed_pricing.model_name} vs Self-Hosted ({self.gpu_type})")
        print(f"{'='*60}")
        
        print(f"\n  Managed cost/request: ${result['managed_cost_per_request']:.4f}")
        print(f"  Self-hosted monthly fixed: ${result['self_hosted_monthly_fixed']:,.0f}")
        print(f"  Self-hosted max capacity: {result['self_hosted_max_capacity']:,} req/month")
        print(f"  Breakeven at: {result['breakeven_monthly_requests']:,} requests/month")
        
        print(f"\n  {'Volume':>12} {'Managed':>12} {'Self-Host':>12} {'Winner':>12} {'Savings':>12}")
        print(f"  {'-'*62}")
        for row in result["comparison"]:
            managed = f"${row['managed_cost']:>10,.0f}"
            self_h = f"${row['self_hosted_cost']:>10,.0f}" if row['self_hosted_cost'] != float('inf') else "  OVER CAP"
            savings = f"${row['savings']:>10,.0f}" if row['savings'] != float('inf') else "       N/A"
            print(f"  {row['monthly_requests']:>12,} {managed:>12} {self_h:>12} {row['cheaper']:>12} {savings:>12}")


# =============================================================================
# 5. COST OPTIMIZATION SIMULATOR
# =============================================================================

class CostOptimizer:
    """Simulate various cost optimization strategies and their impact."""
    
    def __init__(self, base_calculator: RequestCostCalculator):
        self.base = base_calculator
    
    def simulate_optimizations(self,
                               input_tokens: int = 2000,
                               output_tokens: int = 500,
                               monthly_requests: int = 100_000) -> dict:
        """Compare cost under various optimization strategies."""
        
        # Baseline
        baseline = self.base.calculate(input_tokens=input_tokens, output_tokens=output_tokens)
        baseline_monthly = baseline.total_cost * monthly_requests
        
        optimizations = {}
        
        # 1. Semantic Caching (30% hit rate)
        cached = self.base.calculate_with_caching(cache_hit_rate=0.3,
                                                   input_tokens=input_tokens,
                                                   output_tokens=output_tokens)
        optimizations["semantic_caching_30pct"] = {
            "cost_per_request": cached.total_cost,
            "monthly_cost": cached.total_cost * monthly_requests,
            "savings_pct": (1 - cached.total_cost / baseline.total_cost) * 100,
        }
        
        # 2. Prompt Compression (reduce input by 40%)
        compressed = self.base.calculate(input_tokens=int(input_tokens * 0.6),
                                         output_tokens=output_tokens)
        optimizations["prompt_compression_40pct"] = {
            "cost_per_request": compressed.total_cost,
            "monthly_cost": compressed.total_cost * monthly_requests,
            "savings_pct": (1 - compressed.total_cost / baseline.total_cost) * 100,
        }
        
        # 3. Model Routing (70% to small model, 30% to large)
        small_calc = RequestCostCalculator(llm_model="gpt-4o-mini", monthly_request_volume=monthly_requests)
        small_cost = small_calc.calculate(input_tokens=input_tokens, output_tokens=output_tokens)
        routed_cost = 0.7 * small_cost.total_cost + 0.3 * baseline.total_cost
        optimizations["model_routing_70_30"] = {
            "cost_per_request": routed_cost,
            "monthly_cost": routed_cost * monthly_requests,
            "savings_pct": (1 - routed_cost / baseline.total_cost) * 100,
        }
        
        # 4. Shorter outputs (constrain to 300 tokens)
        shorter = self.base.calculate(input_tokens=input_tokens, output_tokens=300)
        optimizations["shorter_outputs_300"] = {
            "cost_per_request": shorter.total_cost,
            "monthly_cost": shorter.total_cost * monthly_requests,
            "savings_pct": (1 - shorter.total_cost / baseline.total_cost) * 100,
        }
        
        # 5. All optimizations combined
        combined_cost = routed_cost * 0.7  # Caching + routing + compression
        optimizations["all_combined"] = {
            "cost_per_request": combined_cost,
            "monthly_cost": combined_cost * monthly_requests,
            "savings_pct": (1 - combined_cost / baseline.total_cost) * 100,
        }
        
        return {
            "baseline": {
                "cost_per_request": baseline.total_cost,
                "monthly_cost": baseline_monthly,
            },
            "optimizations": optimizations,
        }
    
    def print_optimization_report(self, **kwargs):
        """Print formatted optimization comparison."""
        result = self.simulate_optimizations(**kwargs)
        
        print(f"\n{'='*60}")
        print(f"Cost Optimization Comparison")
        print(f"{'='*60}")
        
        print(f"\n  Baseline: ${result['baseline']['cost_per_request']:.5f}/req "
              f"= ${result['baseline']['monthly_cost']:,.0f}/month")
        
        print(f"\n  {'Strategy':<30} {'$/Request':>10} {'$/Month':>12} {'Savings':>8}")
        print(f"  {'-'*64}")
        
        for name, opt in result["optimizations"].items():
            print(f"  {name:<30} ${opt['cost_per_request']:>8.5f} "
                  f"${opt['monthly_cost']:>10,.0f} {opt['savings_pct']:>6.1f}%")


# =============================================================================
# 6. COST PER SUCCESSFUL TASK
# =============================================================================

class TaskCostCalculator:
    """
    Calculate cost per SUCCESSFUL task outcome.
    Accounts for retries, failures, and multi-step workflows.
    """
    
    def __init__(self, request_calculator: RequestCostCalculator):
        self.calc = request_calculator
    
    def cost_per_successful_task(self,
                                  steps_per_task: int = 3,
                                  input_tokens_per_step: int = 2000,
                                  output_tokens_per_step: int = 500,
                                  success_rate_per_step: float = 0.95,
                                  max_retries: int = 2,
                                  retry_has_different_tokens: bool = True) -> dict:
        """
        Calculate cost for a multi-step task with retries.
        
        A "task" might be: classify + retrieve + generate + validate
        Each step can fail and be retried.
        """
        
        # Cost per single step attempt
        step_cost = self.calc.calculate(
            input_tokens=input_tokens_per_step,
            output_tokens=output_tokens_per_step,
        ).total_cost
        
        # Expected attempts per step (geometric series with retries)
        # P(success in k attempts) = (1-p)^(k-1) * p
        # E[attempts] = 1/p (but capped at max_retries+1)
        expected_attempts_per_step = 0
        cumulative_success = 0
        for attempt in range(max_retries + 1):
            p_this_attempt = (1 - success_rate_per_step) ** attempt * success_rate_per_step
            expected_attempts_per_step += (attempt + 1) * p_this_attempt
            cumulative_success += p_this_attempt
        # Account for final failure case
        p_all_fail = (1 - success_rate_per_step) ** (max_retries + 1)
        expected_attempts_per_step += (max_retries + 1) * p_all_fail
        
        # Overall task success probability
        step_success_with_retries = 1 - (1 - success_rate_per_step) ** (max_retries + 1)
        task_success_rate = step_success_with_retries ** steps_per_task
        
        # Total expected cost per task attempt
        cost_per_task_attempt = step_cost * expected_attempts_per_step * steps_per_task
        
        # Cost per SUCCESSFUL task
        cost_per_success = cost_per_task_attempt / task_success_rate if task_success_rate > 0 else float('inf')
        
        return {
            "cost_per_step": step_cost,
            "expected_attempts_per_step": expected_attempts_per_step,
            "step_success_with_retries": step_success_with_retries,
            "task_success_rate": task_success_rate,
            "cost_per_task_attempt": cost_per_task_attempt,
            "cost_per_successful_task": cost_per_success,
            "waste_from_failures": cost_per_success - cost_per_task_attempt,
            "effective_overhead_pct": ((cost_per_success / (step_cost * steps_per_task)) - 1) * 100,
        }


# =============================================================================
# 7. TOKEN EFFICIENCY METRICS
# =============================================================================

class TokenEfficiencyTracker:
    """Track how efficiently tokens are being used."""
    
    def __init__(self):
        self.requests: list[dict] = []
    
    def record_request(self, input_tokens: int, output_tokens: int,
                       useful_output_tokens: int, cache_hit: bool = False,
                       was_retry: bool = False):
        """Record a request for efficiency analysis."""
        self.requests.append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "useful_output_tokens": useful_output_tokens,
            "cache_hit": cache_hit,
            "was_retry": was_retry,
            "total_tokens": input_tokens + output_tokens,
        })
    
    def get_metrics(self) -> dict:
        if not self.requests:
            return {}
        
        total_input = sum(r["input_tokens"] for r in self.requests)
        total_output = sum(r["output_tokens"] for r in self.requests)
        total_useful = sum(r["useful_output_tokens"] for r in self.requests)
        total_all = total_input + total_output
        cache_hits = sum(1 for r in self.requests if r["cache_hit"])
        retries = sum(1 for r in self.requests if r["was_retry"])
        
        return {
            "total_requests": len(self.requests),
            "total_tokens": total_all,
            "input_output_ratio": total_input / total_output if total_output else 0,
            "output_efficiency": total_useful / total_output if total_output else 0,
            "cache_hit_rate": cache_hits / len(self.requests),
            "retry_rate": retries / len(self.requests),
            "tokens_wasted_on_retries": sum(
                r["total_tokens"] for r in self.requests if r["was_retry"]
            ),
            "avg_tokens_per_request": total_all / len(self.requests),
            "useful_token_ratio": total_useful / total_all if total_all else 0,
        }


# =============================================================================
# 8. COST FORECASTING
# =============================================================================

class CostForecaster:
    """Forecast future costs based on growth projections."""
    
    def __init__(self, current_monthly_requests: int, current_monthly_cost: float):
        self.current_requests = current_monthly_requests
        self.current_cost = current_monthly_cost
        self.cost_per_request = current_monthly_cost / current_monthly_requests
    
    def forecast(self, months_ahead: int = 12,
                 monthly_growth_rate: float = 0.15,  # 15% month-over-month
                 cost_reduction_rate: float = 0.03,  # 3% monthly cost reduction (optimization + price drops)
                 ) -> list[dict]:
        """Project costs over time."""
        projections = []
        
        for month in range(1, months_ahead + 1):
            # Growth in volume
            projected_requests = self.current_requests * (1 + monthly_growth_rate) ** month
            
            # Cost per request decreases over time (optimizations + API price drops)
            projected_cost_per_req = self.cost_per_request * (1 - cost_reduction_rate) ** month
            
            # Total monthly cost
            monthly_cost = projected_requests * projected_cost_per_req
            
            # Breakeven check (when should we switch to self-hosted?)
            projections.append({
                "month": month,
                "requests": int(projected_requests),
                "cost_per_request": projected_cost_per_req,
                "monthly_cost": monthly_cost,
                "annual_run_rate": monthly_cost * 12,
            })
        
        return projections
    
    def print_forecast(self, **kwargs):
        projections = self.forecast(**kwargs)
        
        print(f"\n{'='*60}")
        print(f"Cost Forecast ({len(projections)} months)")
        print(f"{'='*60}")
        print(f"\n  Current: {self.current_requests:,} req/mo @ ${self.cost_per_request:.5f}/req = ${self.current_cost:,.0f}/mo")
        
        print(f"\n  {'Month':>5} {'Requests':>12} {'$/Request':>10} {'Monthly':>12} {'Annual Rate':>14}")
        print(f"  {'-'*57}")
        for p in projections:
            print(f"  {p['month']:>5} {p['requests']:>12,} ${p['cost_per_request']:>8.5f} "
                  f"${p['monthly_cost']:>10,.0f} ${p['annual_run_rate']:>12,.0f}")


# =============================================================================
# 9. ROI CALCULATOR
# =============================================================================

class ROICalculator:
    """Calculate Return on Investment for AI systems."""
    
    def calculate_roi(self,
                      # Investment
                      development_cost: float = 500_000,  # One-time
                      monthly_infrastructure: float = 50_000,
                      monthly_api_costs: float = 30_000,
                      monthly_ops_cost: float = 20_000,
                      
                      # Returns
                      monthly_revenue_generated: float = 200_000,  # Or cost savings
                      monthly_cost_avoided: float = 100_000,  # Humans replaced/augmented
                      
                      # Timeline
                      months: int = 24,
                      ramp_up_months: int = 3,  # Months to reach full value
                      ) -> dict:
        """Calculate ROI over a time period."""
        
        monthly_cost = monthly_infrastructure + monthly_api_costs + monthly_ops_cost
        monthly_value = monthly_revenue_generated + monthly_cost_avoided
        
        cumulative_investment = development_cost
        cumulative_returns = 0.0
        monthly_data = []
        payback_month = None
        
        for month in range(1, months + 1):
            # Ramp-up: value increases linearly during ramp-up period
            if month <= ramp_up_months:
                value_multiplier = month / ramp_up_months
            else:
                value_multiplier = 1.0
            
            month_cost = monthly_cost
            month_value = monthly_value * value_multiplier
            
            cumulative_investment += month_cost
            cumulative_returns += month_value
            
            net_position = cumulative_returns - cumulative_investment
            
            if payback_month is None and net_position > 0:
                payback_month = month
            
            monthly_data.append({
                "month": month,
                "monthly_cost": month_cost,
                "monthly_value": month_value,
                "cumulative_investment": cumulative_investment,
                "cumulative_returns": cumulative_returns,
                "net_position": net_position,
                "roi_pct": (cumulative_returns / cumulative_investment - 1) * 100,
            })
        
        final = monthly_data[-1]
        
        return {
            "total_investment": final["cumulative_investment"],
            "total_returns": final["cumulative_returns"],
            "net_value": final["net_position"],
            "roi_pct": final["roi_pct"],
            "payback_month": payback_month,
            "monthly_data": monthly_data,
        }
    
    def print_roi_report(self, **kwargs):
        result = self.calculate_roi(**kwargs)
        
        print(f"\n{'='*60}")
        print(f"AI System ROI Analysis ({len(result['monthly_data'])} months)")
        print(f"{'='*60}")
        
        print(f"\n  Total Investment: ${result['total_investment']:,.0f}")
        print(f"  Total Returns:    ${result['total_returns']:,.0f}")
        print(f"  Net Value:        ${result['net_value']:,.0f}")
        print(f"  ROI:              {result['roi_pct']:.1f}%")
        print(f"  Payback Period:   {result['payback_month']} months" if result['payback_month'] else "  Payback: Never")
        
        # Print quarterly
        print(f"\n  {'Month':>5} {'Invest':>12} {'Returns':>12} {'Net':>12} {'ROI%':>8}")
        print(f"  {'-'*50}")
        for data in result["monthly_data"]:
            if data["month"] % 3 == 0 or data["month"] == 1:
                print(f"  {data['month']:>5} ${data['cumulative_investment']:>10,.0f} "
                      f"${data['cumulative_returns']:>10,.0f} ${data['net_position']:>10,.0f} "
                      f"{data['roi_pct']:>6.1f}%")


# =============================================================================
# DEMO
# =============================================================================

def main():
    print("=" * 70)
    print("  COMPREHENSIVE LLM COST MODEL")
    print("=" * 70)
    
    # --- 1. Per-Request Cost Breakdown ---
    print("\n\n" + "=" * 70)
    print("  1. PER-REQUEST COST BREAKDOWN (RAG Pipeline with GPT-4o)")
    print("=" * 70)
    
    calc = RequestCostCalculator(llm_model="gpt-4o", monthly_request_volume=100_000)
    breakdown = calc.calculate(
        input_tokens=3000,
        output_tokens=500,
        embedding_tokens=50,
        num_retrieved_docs=10,
        reranker_tokens=5000,
        num_tool_calls=2,
    )
    print(f"\n{breakdown.summary()}")
    
    # With caching
    cached = calc.calculate_with_caching(cache_hit_rate=0.3, input_tokens=3000, output_tokens=500)
    print(f"\n  With 30% cache hit rate: ${cached.total_cost:.6f}/req "
          f"(vs ${breakdown.total_cost:.6f} baseline, "
          f"{(1-cached.total_cost/breakdown.total_cost)*100:.1f}% savings)")
    
    # --- 2. Provider Comparison ---
    print("\n\n" + "=" * 70)
    print("  2. PROVIDER COST COMPARISON (2000 input + 500 output tokens)")
    print("=" * 70)
    
    models_to_compare = ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet", "claude-3-haiku", 
                         "gemini-1.5-pro", "gemini-1.5-flash"]
    
    print(f"\n  {'Model':<25} {'Input $/1K':>10} {'Output $/1K':>12} {'Cost/Req':>10} {'Monthly (100K)':>15}")
    print(f"  {'-'*75}")
    for model_name in models_to_compare:
        pricing = PROVIDER_PRICING[model_name]
        cost_per_req = (2000/1000 * pricing.input_cost_per_1k_tokens + 
                       500/1000 * pricing.output_cost_per_1k_tokens)
        monthly = cost_per_req * 100_000
        print(f"  {model_name:<25} ${pricing.input_cost_per_1k_tokens:>8.5f} "
              f"${pricing.output_cost_per_1k_tokens:>10.5f} ${cost_per_req:>8.5f} ${monthly:>13,.0f}")
    
    # --- 3. GPU TCO ---
    print("\n\n" + "=" * 70)
    print("  3. GPU TCO CALCULATION")
    print("=" * 70)
    
    for gpu_type in ["A100_80GB", "H100_SXM", "H200"]:
        config = TCOConfig(num_gpus=8, gpu_type=gpu_type)
        tco_calc = TCOCalculator(config)
        tco_calc.print_report()
    
    # --- 4. Breakeven Analysis ---
    print("\n\n" + "=" * 70)
    print("  4. MANAGED vs SELF-HOSTED BREAKEVEN")
    print("=" * 70)
    
    analyzer = BreakevenAnalyzer(managed_model="gpt-4o", gpu_type="H100_SXM")
    analyzer.print_analysis(avg_input_tokens=2000, avg_output_tokens=500, num_gpus=8)
    
    # --- 5. Cost Optimization ---
    print("\n\n" + "=" * 70)
    print("  5. COST OPTIMIZATION STRATEGIES")
    print("=" * 70)
    
    optimizer = CostOptimizer(calc)
    optimizer.print_optimization_report(
        input_tokens=2000,
        output_tokens=500,
        monthly_requests=100_000,
    )
    
    # --- 6. Cost Per Successful Task ---
    print("\n\n" + "=" * 70)
    print("  6. COST PER SUCCESSFUL TASK")
    print("=" * 70)
    
    task_calc = TaskCostCalculator(calc)
    result = task_calc.cost_per_successful_task(
        steps_per_task=3,
        success_rate_per_step=0.92,
        max_retries=2,
    )
    print(f"\n  3-step task (92% step success, 2 retries allowed):")
    print(f"    Cost per step:           ${result['cost_per_step']:.5f}")
    print(f"    Expected attempts/step:  {result['expected_attempts_per_step']:.2f}")
    print(f"    Task success rate:       {result['task_success_rate']:.1%}")
    print(f"    Cost per attempt:        ${result['cost_per_task_attempt']:.5f}")
    print(f"    Cost per SUCCESS:        ${result['cost_per_successful_task']:.5f}")
    print(f"    Overhead from failures:  {result['effective_overhead_pct']:.1f}%")
    
    # --- 7. Cost Forecast ---
    print("\n\n" + "=" * 70)
    print("  7. 12-MONTH COST FORECAST")
    print("=" * 70)
    
    forecaster = CostForecaster(
        current_monthly_requests=100_000,
        current_monthly_cost=3000,
    )
    forecaster.print_forecast(months_ahead=12, monthly_growth_rate=0.20)
    
    # --- 8. ROI Analysis ---
    print("\n\n" + "=" * 70)
    print("  8. ROI ANALYSIS")
    print("=" * 70)
    
    roi = ROICalculator()
    roi.print_roi_report(
        development_cost=400_000,
        monthly_infrastructure=30_000,
        monthly_api_costs=20_000,
        monthly_ops_cost=15_000,
        monthly_revenue_generated=150_000,
        monthly_cost_avoided=80_000,
        months=24,
        ramp_up_months=3,
    )


if __name__ == "__main__":
    main()
