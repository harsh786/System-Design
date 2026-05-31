"""
AI Infrastructure Cost Optimizer
==================================
Simulates infrastructure cost optimization for AI inference workloads.

Demonstrates:
1. Traffic pattern analysis (peak/off-peak)
2. Strategy comparison: reserved, on-demand, spot, auto-scaling
3. Multi-tier routing (expensive vs cheap model)
4. Monthly cost calculation per strategy
5. Optimization report with savings

Usage: python3 main.py

Staff Architect Tool: Model different cost strategies before committing
to infrastructure procurement decisions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from enum import Enum
import math
import random


# =============================================================================
# Pricing Models
# =============================================================================

@dataclass
class GPUPricing:
    """Pricing for a GPU type across procurement options."""
    gpu_type: str
    on_demand_per_hour: float
    reserved_1yr_per_hour: float
    reserved_3yr_per_hour: float
    spot_per_hour: float
    spot_availability: float  # Probability spot is available (0-1)


PRICING = {
    "H100": GPUPricing("H100 SXM", 12.26, 7.50, 5.00, 3.50, 0.70),
    "A100": GPUPricing("A100 80GB", 5.12, 3.30, 2.20, 1.80, 0.80),
    "L40S": GPUPricing("L40S", 2.35, 1.50, 1.00, 0.80, 0.85),
    "T4": GPUPricing("T4", 0.53, 0.35, 0.25, 0.15, 0.90),
}

HOURS_PER_MONTH = 730


# =============================================================================
# Traffic Patterns
# =============================================================================

@dataclass
class TrafficPattern:
    """Hourly traffic pattern over 24 hours."""
    name: str
    hourly_requests_per_sec: List[float]  # 24 values, one per hour
    avg_input_tokens: int = 500
    avg_output_tokens: int = 200

    @property
    def peak_rps(self) -> float:
        return max(self.hourly_requests_per_sec)

    @property
    def avg_rps(self) -> float:
        return sum(self.hourly_requests_per_sec) / 24

    @property
    def daily_requests(self) -> float:
        return sum(r * 3600 for r in self.hourly_requests_per_sec)


def create_business_hours_pattern(peak_rps: float) -> TrafficPattern:
    """Typical B2B SaaS: high during business hours, low at night."""
    pattern = [
        0.1, 0.05, 0.05, 0.05, 0.1, 0.2,   # 00-05: very low
        0.4, 0.7, 0.9, 1.0, 0.95, 1.0,      # 06-11: ramp to peak
        0.85, 0.95, 1.0, 0.9, 0.8, 0.6,     # 12-17: sustained
        0.4, 0.3, 0.2, 0.15, 0.1, 0.1,      # 18-23: ramp down
    ]
    return TrafficPattern(
        name="Business Hours (B2B SaaS)",
        hourly_requests_per_sec=[p * peak_rps for p in pattern],
    )


def create_consumer_pattern(peak_rps: float) -> TrafficPattern:
    """Consumer app: peaks in evening, moderate daytime."""
    pattern = [
        0.2, 0.1, 0.05, 0.05, 0.05, 0.1,   # 00-05: low
        0.2, 0.3, 0.4, 0.5, 0.5, 0.6,      # 06-11: morning ramp
        0.5, 0.5, 0.5, 0.6, 0.7, 0.8,      # 12-17: afternoon
        0.9, 1.0, 1.0, 0.9, 0.7, 0.4,      # 18-23: evening peak
    ]
    return TrafficPattern(
        name="Consumer App (Evening Peak)",
        hourly_requests_per_sec=[p * peak_rps for p in pattern],
    )


def create_steady_pattern(rps: float) -> TrafficPattern:
    """Steady traffic with minimal variation (API service)."""
    pattern = [0.8 + random.uniform(0, 0.2) for _ in range(24)]
    return TrafficPattern(
        name="Steady API Traffic",
        hourly_requests_per_sec=[p * rps for p in pattern],
    )


# =============================================================================
# Infrastructure Strategies
# =============================================================================

class Strategy(Enum):
    ALL_RESERVED = "all_reserved"
    ALL_ON_DEMAND = "all_on_demand"
    RESERVED_PLUS_SPOT = "reserved_plus_spot"
    AUTOSCALING = "autoscaling"
    MULTI_TIER = "multi_tier"


@dataclass
class InfraConfig:
    """Infrastructure configuration for a strategy."""
    strategy: Strategy
    gpu_type: str
    gpus_per_replica: int  # TP degree
    throughput_per_replica_tps: float  # Tokens/sec per replica
    reserved_replicas: int = 0
    max_replicas: int = 0
    spot_replicas: int = 0
    # For multi-tier
    cheap_gpu_type: str = "T4"
    cheap_gpus_per_replica: int = 1
    cheap_throughput_per_replica_tps: float = 0
    cheap_replicas: int = 0
    tier_routing_ratio: float = 0  # Fraction routed to cheap tier


@dataclass
class CostResult:
    """Monthly cost calculation result."""
    strategy_name: str
    monthly_cost: float
    gpu_hours: float
    avg_utilization: float
    max_replicas_used: int
    unserved_requests_pct: float
    details: Dict = field(default_factory=dict)


# =============================================================================
# Cost Calculator
# =============================================================================

class CostOptimizer:
    """Calculates and compares infrastructure costs."""

    def __init__(self, traffic: TrafficPattern):
        self.traffic = traffic

    def replicas_needed(self, rps: float, throughput_per_replica_tps: float,
                        avg_output_tokens: int) -> int:
        """Calculate replicas needed for given request rate."""
        tokens_per_sec_needed = rps * avg_output_tokens
        replicas = math.ceil(tokens_per_sec_needed / throughput_per_replica_tps)
        return max(1, replicas)

    def calculate_all_reserved(self, config: InfraConfig) -> CostResult:
        """All GPUs reserved at peak capacity."""
        pricing = PRICING[config.gpu_type]
        # Must provision for peak
        peak_replicas = self.replicas_needed(
            self.traffic.peak_rps,
            config.throughput_per_replica_tps,
            self.traffic.avg_output_tokens,
        )
        total_gpus = peak_replicas * config.gpus_per_replica
        monthly_cost = total_gpus * pricing.reserved_1yr_per_hour * HOURS_PER_MONTH

        # Calculate average utilization
        avg_replicas_needed = self.replicas_needed(
            self.traffic.avg_rps,
            config.throughput_per_replica_tps,
            self.traffic.avg_output_tokens,
        )
        utilization = avg_replicas_needed / peak_replicas

        return CostResult(
            strategy_name="All Reserved (1yr)",
            monthly_cost=monthly_cost,
            gpu_hours=total_gpus * HOURS_PER_MONTH,
            avg_utilization=utilization,
            max_replicas_used=peak_replicas,
            unserved_requests_pct=0,
            details={"total_gpus": total_gpus, "pricing": "reserved_1yr"},
        )

    def calculate_all_on_demand(self, config: InfraConfig) -> CostResult:
        """All GPUs on-demand, scale to traffic."""
        pricing = PRICING[config.gpu_type]
        total_cost = 0
        total_gpu_hours = 0
        max_replicas = 0

        for hour_rps in self.traffic.hourly_requests_per_sec:
            replicas = self.replicas_needed(
                hour_rps, config.throughput_per_replica_tps, self.traffic.avg_output_tokens
            )
            max_replicas = max(max_replicas, replicas)
            gpus = replicas * config.gpus_per_replica
            # Cost for this hour (× 30 days)
            total_cost += gpus * pricing.on_demand_per_hour * 30
            total_gpu_hours += gpus * 30

        return CostResult(
            strategy_name="All On-Demand (Auto-scaled)",
            monthly_cost=total_cost,
            gpu_hours=total_gpu_hours,
            avg_utilization=0.85,  # Auto-scaling targets ~85%
            max_replicas_used=max_replicas,
            unserved_requests_pct=0,
            details={"max_gpus": max_replicas * config.gpus_per_replica},
        )

    def calculate_reserved_plus_spot(self, config: InfraConfig) -> CostResult:
        """Reserved base + spot for peaks."""
        pricing = PRICING[config.gpu_type]

        # Reserve for ~60th percentile traffic
        sorted_rps = sorted(self.traffic.hourly_requests_per_sec)
        p60_rps = sorted_rps[int(len(sorted_rps) * 0.6)]
        base_replicas = self.replicas_needed(
            p60_rps, config.throughput_per_replica_tps, self.traffic.avg_output_tokens
        )

        # Reserved cost (always running)
        base_gpus = base_replicas * config.gpus_per_replica
        reserved_cost = base_gpus * pricing.reserved_1yr_per_hour * HOURS_PER_MONTH

        # Spot for overflow
        spot_cost = 0
        unserved_hours = 0
        max_total_replicas = base_replicas

        for hour_rps in self.traffic.hourly_requests_per_sec:
            needed = self.replicas_needed(
                hour_rps, config.throughput_per_replica_tps, self.traffic.avg_output_tokens
            )
            overflow = max(0, needed - base_replicas)
            if overflow > 0:
                # Spot may not be available
                actual_spot = math.ceil(overflow * pricing.spot_availability)
                unserved = overflow - actual_spot
                spot_gpus = actual_spot * config.gpus_per_replica
                spot_cost += spot_gpus * pricing.spot_per_hour * 30
                if unserved > 0:
                    unserved_hours += 1
                max_total_replicas = max(max_total_replicas, base_replicas + actual_spot)

        total_cost = reserved_cost + spot_cost
        unserved_pct = unserved_hours / 24 * 100

        return CostResult(
            strategy_name="Reserved Base + Spot Burst",
            monthly_cost=total_cost,
            gpu_hours=base_gpus * HOURS_PER_MONTH,
            avg_utilization=0.75,
            max_replicas_used=max_total_replicas,
            unserved_requests_pct=unserved_pct,
            details={
                "reserved_gpus": base_gpus,
                "reserved_cost": reserved_cost,
                "spot_cost": spot_cost,
            },
        )

    def calculate_multi_tier(self, config: InfraConfig) -> CostResult:
        """Route fraction of traffic to cheaper/smaller model."""
        pricing_expensive = PRICING[config.gpu_type]
        pricing_cheap = PRICING[config.cheap_gpu_type]

        total_cost = 0
        max_expensive = 0
        max_cheap = 0

        for hour_rps in self.traffic.hourly_requests_per_sec:
            # Route portion to cheap tier
            cheap_rps = hour_rps * config.tier_routing_ratio
            expensive_rps = hour_rps * (1 - config.tier_routing_ratio)

            # Expensive tier (reserved)
            exp_replicas = self.replicas_needed(
                expensive_rps, config.throughput_per_replica_tps, self.traffic.avg_output_tokens
            )
            max_expensive = max(max_expensive, exp_replicas)

            # Cheap tier (on-demand, auto-scaled)
            cheap_replicas = self.replicas_needed(
                cheap_rps, config.cheap_throughput_per_replica_tps, self.traffic.avg_output_tokens
            )
            max_cheap = max(max_cheap, cheap_replicas)

            # Costs per hour × 30 days
            exp_cost = exp_replicas * config.gpus_per_replica * pricing_expensive.reserved_1yr_per_hour * 30
            cheap_cost = cheap_replicas * config.cheap_gpus_per_replica * pricing_cheap.on_demand_per_hour * 30
            total_cost += exp_cost + cheap_cost

        return CostResult(
            strategy_name=f"Multi-Tier ({int(config.tier_routing_ratio*100)}% to cheap)",
            monthly_cost=total_cost,
            gpu_hours=0,
            avg_utilization=0.80,
            max_replicas_used=max_expensive + max_cheap,
            unserved_requests_pct=0,
            details={
                "expensive_replicas": max_expensive,
                "cheap_replicas": max_cheap,
                "expensive_gpu": config.gpu_type,
                "cheap_gpu": config.cheap_gpu_type,
            },
        )

    def calculate_autoscaling(self, config: InfraConfig) -> CostResult:
        """Auto-scaling with reserved base and on-demand burst."""
        pricing = PRICING[config.gpu_type]

        # Reserve minimum (always-on)
        min_replicas = max(1, config.reserved_replicas)
        reserved_gpus = min_replicas * config.gpus_per_replica
        reserved_cost = reserved_gpus * pricing.reserved_1yr_per_hour * HOURS_PER_MONTH

        # On-demand for scaling beyond reserved
        od_cost = 0
        max_replicas = min_replicas

        for hour_rps in self.traffic.hourly_requests_per_sec:
            needed = self.replicas_needed(
                hour_rps, config.throughput_per_replica_tps, self.traffic.avg_output_tokens
            )
            overflow = max(0, needed - min_replicas)
            if overflow > 0:
                od_gpus = overflow * config.gpus_per_replica
                od_cost += od_gpus * pricing.on_demand_per_hour * 30
                max_replicas = max(max_replicas, needed)

        total_cost = reserved_cost + od_cost

        return CostResult(
            strategy_name=f"Auto-scale (base={min_replicas} reserved)",
            monthly_cost=total_cost,
            gpu_hours=reserved_gpus * HOURS_PER_MONTH,
            avg_utilization=0.80,
            max_replicas_used=max_replicas,
            unserved_requests_pct=0,
            details={"reserved_cost": reserved_cost, "on_demand_cost": od_cost},
        )


# =============================================================================
# Report Generation
# =============================================================================

def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def generate_report(traffic: TrafficPattern, results: List[CostResult]):
    """Generate optimization report."""
    print(f"\n  Traffic Pattern: {traffic.name}")
    print(f"  Peak RPS: {traffic.peak_rps:.0f}")
    print(f"  Average RPS: {traffic.avg_rps:.0f}")
    print(f"  Peak/Avg Ratio: {traffic.peak_rps/traffic.avg_rps:.1f}×")
    print(f"  Daily Requests: {traffic.daily_requests:,.0f}")

    # Sort by cost
    results.sort(key=lambda r: r.monthly_cost)
    cheapest = results[0].monthly_cost
    most_expensive = results[-1].monthly_cost

    print(f"\n  {'Strategy':<35} {'Monthly Cost':<15} {'vs Best':<10} {'Util':<8} {'Risk':<8}")
    print(f"  {'─'*76}")

    for r in results:
        delta = ((r.monthly_cost - cheapest) / cheapest * 100) if cheapest > 0 else 0
        risk = "Low" if r.unserved_requests_pct == 0 else f"{r.unserved_requests_pct:.0f}% drop"
        print(f"  {r.strategy_name:<35} ${r.monthly_cost:>10,.0f}   +{delta:>4.0f}%   "
              f"{r.avg_utilization:>5.0%}   {risk}")

    savings = most_expensive - cheapest
    print(f"\n  Maximum savings opportunity: ${savings:,.0f}/month "
          f"({savings/most_expensive*100:.0f}% reduction)")
    print(f"  Recommended: {results[0].strategy_name}")


# =============================================================================
# Main Scenarios
# =============================================================================

def scenario_70b_model():
    """Cost optimization for 70B model serving."""
    print_header("SCENARIO 1: 70B Model Serving (100 peak RPS)")

    traffic = create_business_hours_pattern(peak_rps=100)
    optimizer = CostOptimizer(traffic)

    # Base config: 70B on 4× H100 (TP=4), ~500 tokens/s per replica
    base_config = InfraConfig(
        strategy=Strategy.ALL_RESERVED,
        gpu_type="H100",
        gpus_per_replica=4,
        throughput_per_replica_tps=500,
    )

    results = [
        optimizer.calculate_all_reserved(base_config),
        optimizer.calculate_all_on_demand(base_config),
        optimizer.calculate_reserved_plus_spot(base_config),
        optimizer.calculate_autoscaling(InfraConfig(
            strategy=Strategy.AUTOSCALING,
            gpu_type="H100",
            gpus_per_replica=4,
            throughput_per_replica_tps=500,
            reserved_replicas=5,  # Base for average traffic
        )),
        optimizer.calculate_multi_tier(InfraConfig(
            strategy=Strategy.MULTI_TIER,
            gpu_type="H100",
            gpus_per_replica=4,
            throughput_per_replica_tps=500,
            cheap_gpu_type="T4",
            cheap_gpus_per_replica=1,
            cheap_throughput_per_replica_tps=50,  # 7B quantized model on T4
            tier_routing_ratio=0.6,  # 60% to cheap model
        )),
    ]

    generate_report(traffic, results)


def scenario_7b_cost_sensitive():
    """Cost optimization for 7B model (startup/cost-sensitive)."""
    print_header("SCENARIO 2: 7B Model Serving - Startup (50 peak RPS)")

    traffic = create_consumer_pattern(peak_rps=50)
    optimizer = CostOptimizer(traffic)

    base_config = InfraConfig(
        strategy=Strategy.ALL_RESERVED,
        gpu_type="A100",
        gpus_per_replica=1,
        throughput_per_replica_tps=200,
    )

    results = [
        optimizer.calculate_all_reserved(base_config),
        optimizer.calculate_all_on_demand(base_config),
        optimizer.calculate_reserved_plus_spot(base_config),
        # Try with cheaper GPU (T4 + quantization)
        optimizer.calculate_all_reserved(InfraConfig(
            strategy=Strategy.ALL_RESERVED,
            gpu_type="T4",
            gpus_per_replica=1,
            throughput_per_replica_tps=80,  # INT4 quantized on T4
        )),
        optimizer.calculate_autoscaling(InfraConfig(
            strategy=Strategy.AUTOSCALING,
            gpu_type="T4",
            gpus_per_replica=1,
            throughput_per_replica_tps=80,
            reserved_replicas=3,
        )),
    ]

    # Fix strategy name for T4 reserved
    results[3].strategy_name = "All Reserved (T4 + INT4 quantized)"

    generate_report(traffic, results)


def scenario_high_scale():
    """Cost optimization at high scale (1000 RPS)."""
    print_header("SCENARIO 3: High Scale (1000 peak RPS) - Enterprise")

    traffic = create_steady_pattern(rps=800)  # Relatively steady
    optimizer = CostOptimizer(traffic)

    results = [
        optimizer.calculate_all_reserved(InfraConfig(
            strategy=Strategy.ALL_RESERVED,
            gpu_type="H100",
            gpus_per_replica=4,
            throughput_per_replica_tps=500,
        )),
        optimizer.calculate_all_reserved(InfraConfig(
            strategy=Strategy.ALL_RESERVED,
            gpu_type="A100",
            gpus_per_replica=8,  # TP=8 needed for 70B on A100
            throughput_per_replica_tps=300,
        )),
        optimizer.calculate_multi_tier(InfraConfig(
            strategy=Strategy.MULTI_TIER,
            gpu_type="H100",
            gpus_per_replica=4,
            throughput_per_replica_tps=500,
            cheap_gpu_type="A100",
            cheap_gpus_per_replica=1,
            cheap_throughput_per_replica_tps=200,  # 7B model on A100
            tier_routing_ratio=0.7,
        )),
    ]

    results[1].strategy_name = "All Reserved (A100 × 8, TP=8)"
    results[2].strategy_name = "Multi-Tier (70% → 7B on A100, 30% → 70B on H100)"

    generate_report(traffic, results)

    # Self-hosting comparison
    print(f"\n  Self-Hosting Comparison:")
    cloud_best = min(r.monthly_cost for r in results)
    # Self-hosted: ~$15/hr per 8-GPU node (amortized)
    needed_nodes = math.ceil(results[0].details.get("total_gpus", 40) / 8)
    self_hosted_monthly = needed_nodes * 15 * HOURS_PER_MONTH
    print(f"    Cloud (best strategy): ${cloud_best:,.0f}/month")
    print(f"    Self-hosted ({needed_nodes} nodes): ${self_hosted_monthly:,.0f}/month")
    print(f"    Savings: ${cloud_best - self_hosted_monthly:,.0f}/month ({(1-self_hosted_monthly/cloud_best)*100:.0f}%)")
    print(f"    Break-even: ~{needed_nodes * 300000 / (cloud_best - self_hosted_monthly):.0f} months")
    print(f"    Requires: Data center capacity, 3+ ML infra engineers, 3yr commitment")


def scenario_api_vs_self_host():
    """Compare API providers vs self-hosting."""
    print_header("SCENARIO 4: API vs Self-Hosting Break-Even")

    print(f"""
  Comparing: Using an API provider vs self-hosting the same quality model.
  Assumptions: GPT-4 class model, variable monthly token volume.
    """)

    # API pricing (per 1M output tokens)
    api_prices = {
        "OpenAI GPT-4o": 15.0,
        "Anthropic Claude Sonnet": 15.0,
        "OpenAI GPT-4o-mini": 0.60,
    }

    # Self-hosted equivalent costs
    self_hosted = {
        "70B on 4×H100 (reserved)": {
            "monthly_fixed": 4 * 7.50 * HOURS_PER_MONTH,  # ~$22K
            "capacity_tokens_per_month": 500 * 3600 * 24 * 30,  # 500 tok/s continuous
            "quality": "GPT-4 class",
        },
        "7B on 1×T4 (reserved)": {
            "monthly_fixed": 1 * 0.35 * HOURS_PER_MONTH,  # ~$255
            "capacity_tokens_per_month": 80 * 3600 * 24 * 30,
            "quality": "GPT-4o-mini class",
        },
    }

    # Calculate break-even
    volumes = [1e6, 10e6, 100e6, 500e6, 1e9, 5e9]  # Tokens per month

    print(f"  {'Volume (M tok/mo)':<20}", end="")
    for name in api_prices:
        print(f" {name:<15}", end="")
    print(f" {'Self-host 70B':<15} {'Self-host 7B':<15}")
    print(f"  {'─'*95}")

    for vol in volumes:
        print(f"  {vol/1e6:<20.0f}", end="")
        for name, price in api_prices.items():
            cost = vol / 1e6 * price
            print(f" ${cost:<13,.0f}", end="")

        # Self-hosted (fixed cost regardless of volume, up to capacity)
        for name, config in self_hosted.items():
            if vol <= config["capacity_tokens_per_month"]:
                print(f" ${config['monthly_fixed']:<13,.0f}", end="")
            else:
                # Need multiple replicas
                replicas = math.ceil(vol / config["capacity_tokens_per_month"])
                cost = config["monthly_fixed"] * replicas
                print(f" ${cost:<13,.0f}", end="")
        print()

    print(f"""
  Break-even Analysis:
  • 70B self-hosted ($22K/mo) vs GPT-4o API ($15/M tokens):
    Break-even at: {22000/15*1e6/1e9:.1f}B tokens/month
    (≈ {22000/15*1e6/500/3600/24:.0f} days at full 500 tok/s capacity)
    
  • 7B self-hosted ($255/mo) vs GPT-4o-mini API ($0.60/M tokens):
    Break-even at: {255/0.6:.0f}M tokens/month
    (≈ {255/0.6*1e6/80/3600/24:.0f} days at full 80 tok/s capacity)
    
  Conclusion:
  • At LOW volume: APIs win (no fixed cost, pay per token)
  • At HIGH volume: Self-hosting wins (fixed cost amortized across tokens)
  • Break-even typically at 50-70% GPU utilization sustained
    """)


# =============================================================================
# Main
# =============================================================================

def main():
    random.seed(42)  # Reproducible results

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              AI INFRASTRUCTURE COST OPTIMIZER                         ║
║                                                                      ║
║  Compares infrastructure strategies: reserved, on-demand, spot,      ║
║  auto-scaling, multi-tier routing, and self-hosting.                 ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    scenario_70b_model()
    scenario_7b_cost_sensitive()
    scenario_high_scale()
    scenario_api_vs_self_host()

    print_header("COST OPTIMIZATION PLAYBOOK FOR STAFF ARCHITECTS")
    print("""
  Priority 1 - Quick Wins (implement this week):
    • Kill idle GPU pods (scale-to-zero for dev/staging)
    • Right-size: move small models off H100 to T4/L40S
    • Enable response caching for repeated queries
    
  Priority 2 - Medium Effort (implement this month):
    • Reserved instances for stable base load (35-40% savings)
    • Spot instances for training/batch (60-90% savings)
    • Quantization: FP16 → FP8/INT4 (halve GPU count)
    
  Priority 3 - Strategic (implement this quarter):
    • Multi-tier routing (route simple queries to cheap models)
    • Auto-scaling with predictive warm-up
    • Evaluate self-hosting if spend > $200K/month sustained
    
  Key Metrics to Track:
    • Cost per 1M tokens (by model, by team)
    • GPU utilization (target: >70% for reserved)
    • Cost per user request (margin analysis)
    • Waste: allocated but idle GPU-hours
    """)


if __name__ == "__main__":
    main()
