"""
AI System Capacity Planner
Calculates capacity requirements and projects future needs.
"""

import math
from dataclasses import dataclass


@dataclass
class CurrentUsage:
    """Current system usage metrics."""
    requests_per_day: int
    avg_tokens_per_request: int
    peak_qps: float
    concurrent_users: int
    total_vectors: int
    vector_dimensions: int
    new_docs_per_day: int
    chunks_per_doc: int
    active_sessions: int
    avg_session_size_kb: float
    monthly_growth_rate: float  # e.g., 0.20 for 20%


@dataclass
class InfraConfig:
    """Infrastructure configuration and pricing."""
    # Model API pricing
    input_cost_per_1m_tokens: float  # e.g., $2.50
    output_cost_per_1m_tokens: float  # e.g., $10.00
    input_output_ratio: float  # e.g., 0.7 means 70% input tokens

    # GPU (if self-hosted)
    gpu_cost_per_hour: float
    tokens_per_gpu_per_sec: int

    # Vector DB
    vector_node_memory_gb: int
    vector_node_cost_per_month: float

    # Redis
    redis_cost_per_gb_month: float

    # Storage
    storage_cost_per_gb_month: float

    # Other infra
    base_infra_cost_per_month: float  # App servers, networking, monitoring


@dataclass
class SLORequirements:
    """SLO targets that constrain capacity."""
    availability_target: float  # e.g., 0.999
    latency_p95_ms: int
    min_redundancy_factor: float  # e.g., 1.5 for N+1


class CapacityPlanner:
    """Calculates and projects AI system capacity needs."""

    def __init__(self, usage: CurrentUsage, infra: InfraConfig, slos: SLORequirements):
        self.usage = usage
        self.infra = infra
        self.slos = slos

    def calculate_current_capacity(self) -> dict:
        """Calculate current capacity requirements."""
        results = {}

        # Token throughput
        tokens_per_sec = (self.usage.requests_per_day * self.usage.avg_tokens_per_request) / 86400
        results["tokens_per_sec_avg"] = tokens_per_sec
        results["tokens_per_sec_peak"] = self.usage.peak_qps * self.usage.avg_tokens_per_request

        # GPU requirements (if self-hosted)
        gpus_needed = math.ceil(
            results["tokens_per_sec_peak"] / self.infra.tokens_per_gpu_per_sec
        ) * self.slos.min_redundancy_factor
        results["gpus_required"] = int(gpus_needed)

        # Vector DB nodes
        bytes_per_vector = self.usage.vector_dimensions * 4 * 2  # float32 + overhead
        vectors_per_node = (self.infra.vector_node_memory_gb * 1e9) / bytes_per_vector
        nodes_needed = math.ceil(self.usage.total_vectors / vectors_per_node) * 1.3  # 30% headroom
        results["vector_db_nodes"] = max(3, int(math.ceil(nodes_needed)))  # min 3 for HA
        results["vector_db_utilization"] = self.usage.total_vectors / (results["vector_db_nodes"] * vectors_per_node)

        # Redis memory
        redis_gb = (self.usage.active_sessions * self.usage.avg_session_size_kb * 2) / (1024 * 1024)
        results["redis_memory_gb"] = math.ceil(redis_gb * 10) / 10  # round to 0.1

        # Storage growth
        vector_growth_per_month = (
            self.usage.new_docs_per_day * self.usage.chunks_per_doc *
            self.usage.vector_dimensions * 4 * 30
        ) / (1024**3)  # GB
        results["storage_growth_gb_per_month"] = round(vector_growth_per_month, 1)

        return results

    def project_capacity(self, months: int) -> dict:
        """Project capacity needs N months in the future."""
        growth = (1 + self.usage.monthly_growth_rate) ** months
        current = self.calculate_current_capacity()

        projected = {
            "months_out": months,
            "growth_factor": round(growth, 2),
            "projected_requests_per_day": int(self.usage.requests_per_day * growth),
            "projected_peak_qps": round(self.usage.peak_qps * growth, 1),
            "projected_tokens_per_sec_peak": round(current["tokens_per_sec_peak"] * growth, 0),
            "projected_gpus": int(math.ceil(current["gpus_required"] * growth)),
            "projected_vectors": int(self.usage.total_vectors + (
                self.usage.new_docs_per_day * self.usage.chunks_per_doc * 30 * months
            )),
            "projected_redis_gb": round(current["redis_memory_gb"] * growth, 1),
            "projected_storage_total_gb": round(
                current["storage_growth_gb_per_month"] * months + 50, 1  # 50GB existing
            ),
        }

        # Recalculate vector DB nodes for projected vectors
        bytes_per_vector = self.usage.vector_dimensions * 4 * 2
        vectors_per_node = (self.infra.vector_node_memory_gb * 1e9) / bytes_per_vector
        projected["projected_vector_db_nodes"] = max(
            3, int(math.ceil(projected["projected_vectors"] / vectors_per_node * 1.3))
        )

        return projected

    def calculate_monthly_cost(self, months_out: int = 0) -> dict:
        """Calculate monthly cost, optionally projected forward."""
        growth = (1 + self.usage.monthly_growth_rate) ** months_out
        daily_requests = self.usage.requests_per_day * growth
        tokens_per_request = self.usage.avg_tokens_per_request

        # API costs
        input_tokens = daily_requests * tokens_per_request * self.infra.input_output_ratio * 30
        output_tokens = daily_requests * tokens_per_request * (1 - self.infra.input_output_ratio) * 30

        api_cost = (
            (input_tokens / 1e6) * self.infra.input_cost_per_1m_tokens +
            (output_tokens / 1e6) * self.infra.output_cost_per_1m_tokens
        )

        # Infrastructure costs
        current = self.calculate_current_capacity()
        projected = self.project_capacity(months_out) if months_out > 0 else None

        vector_nodes = projected["projected_vector_db_nodes"] if projected else current["vector_db_nodes"]
        redis_gb = projected["projected_redis_gb"] if projected else current["redis_memory_gb"]
        storage_gb = projected["projected_storage_total_gb"] if projected else 50

        vector_cost = vector_nodes * self.infra.vector_node_cost_per_month
        redis_cost = redis_gb * self.infra.redis_cost_per_gb_month
        storage_cost = storage_gb * self.infra.storage_cost_per_gb_month
        gpu_cost = current["gpus_required"] * growth * self.infra.gpu_cost_per_hour * 720

        total = api_cost + vector_cost + redis_cost + storage_cost + self.infra.base_infra_cost_per_month + gpu_cost

        return {
            "months_out": months_out,
            "api_cost": round(api_cost, 2),
            "gpu_cost": round(gpu_cost, 2),
            "vector_db_cost": round(vector_cost, 2),
            "redis_cost": round(redis_cost, 2),
            "storage_cost": round(storage_cost, 2),
            "base_infra_cost": self.infra.base_infra_cost_per_month,
            "total_monthly": round(total, 2),
            "cost_per_request": round(total / (daily_requests * 30), 4),
        }

    def generate_report(self):
        """Generate full capacity planning report."""
        current = self.calculate_current_capacity()
        cost_now = self.calculate_monthly_cost(0)
        cost_3m = self.calculate_monthly_cost(3)
        cost_6m = self.calculate_monthly_cost(6)
        cost_12m = self.calculate_monthly_cost(12)

        proj_3 = self.project_capacity(3)
        proj_6 = self.project_capacity(6)
        proj_12 = self.project_capacity(12)

        print("=" * 70)
        print("  AI SYSTEM CAPACITY PLAN")
        print("=" * 70)
        print()

        # Current state
        print("  CURRENT STATE")
        print(f"  {'─' * 60}")
        print(f"    Requests/day:         {self.usage.requests_per_day:,}")
        print(f"    Peak QPS:             {self.usage.peak_qps}")
        print(f"    Avg tokens/request:   {self.usage.avg_tokens_per_request:,}")
        print(f"    Tokens/sec (avg):     {current['tokens_per_sec_avg']:,.0f}")
        print(f"    Tokens/sec (peak):    {current['tokens_per_sec_peak']:,.0f}")
        print(f"    Total vectors:        {self.usage.total_vectors:,}")
        print(f"    Monthly growth rate:  {self.usage.monthly_growth_rate:.0%}")
        print()

        # Current capacity
        print("  CURRENT CAPACITY REQUIREMENTS")
        print(f"  {'─' * 60}")
        print(f"    GPUs required:          {current['gpus_required']}")
        print(f"    Vector DB nodes:        {current['vector_db_nodes']} (utilization: {current['vector_db_utilization']:.0%})")
        print(f"    Redis memory:           {current['redis_memory_gb']} GB")
        print(f"    Storage growth:         {current['storage_growth_gb_per_month']} GB/month")
        print()

        # Projections
        print("  CAPACITY PROJECTIONS")
        print(f"  {'─' * 60}")
        print(f"    {'Metric':<30} {'Now':>10} {'3 months':>10} {'6 months':>10} {'12 months':>10}")
        print(f"    {'─' * 58}")
        print(f"    {'Requests/day':<30} {self.usage.requests_per_day:>10,} {proj_3['projected_requests_per_day']:>10,} {proj_6['projected_requests_per_day']:>10,} {proj_12['projected_requests_per_day']:>10,}")
        print(f"    {'Peak QPS':<30} {self.usage.peak_qps:>10.0f} {proj_3['projected_peak_qps']:>10.0f} {proj_6['projected_peak_qps']:>10.0f} {proj_12['projected_peak_qps']:>10.0f}")
        print(f"    {'GPUs':<30} {current['gpus_required']:>10} {proj_3['projected_gpus']:>10} {proj_6['projected_gpus']:>10} {proj_12['projected_gpus']:>10}")
        print(f"    {'Vector DB nodes':<30} {current['vector_db_nodes']:>10} {proj_3['projected_vector_db_nodes']:>10} {proj_6['projected_vector_db_nodes']:>10} {proj_12['projected_vector_db_nodes']:>10}")
        print(f"    {'Redis (GB)':<30} {current['redis_memory_gb']:>10} {proj_3['projected_redis_gb']:>10} {proj_6['projected_redis_gb']:>10} {proj_12['projected_redis_gb']:>10}")
        print(f"    {'Vectors (millions)':<30} {self.usage.total_vectors/1e6:>10.1f} {proj_3['projected_vectors']/1e6:>10.1f} {proj_6['projected_vectors']/1e6:>10.1f} {proj_12['projected_vectors']/1e6:>10.1f}")
        print()

        # Cost projections
        print("  COST PROJECTIONS (Monthly)")
        print(f"  {'─' * 60}")
        print(f"    {'Component':<25} {'Now':>12} {'3 months':>12} {'6 months':>12} {'12 months':>12}")
        print(f"    {'─' * 58}")
        print(f"    {'API (tokens)':<25} ${cost_now['api_cost']:>10,.0f} ${cost_3m['api_cost']:>10,.0f} ${cost_6m['api_cost']:>10,.0f} ${cost_12m['api_cost']:>10,.0f}")
        print(f"    {'GPU compute':<25} ${cost_now['gpu_cost']:>10,.0f} ${cost_3m['gpu_cost']:>10,.0f} ${cost_6m['gpu_cost']:>10,.0f} ${cost_12m['gpu_cost']:>10,.0f}")
        print(f"    {'Vector DB':<25} ${cost_now['vector_db_cost']:>10,.0f} ${cost_3m['vector_db_cost']:>10,.0f} ${cost_6m['vector_db_cost']:>10,.0f} ${cost_12m['vector_db_cost']:>10,.0f}")
        print(f"    {'Redis':<25} ${cost_now['redis_cost']:>10,.0f} ${cost_3m['redis_cost']:>10,.0f} ${cost_6m['redis_cost']:>10,.0f} ${cost_12m['redis_cost']:>10,.0f}")
        print(f"    {'Storage':<25} ${cost_now['storage_cost']:>10,.0f} ${cost_3m['storage_cost']:>10,.0f} ${cost_6m['storage_cost']:>10,.0f} ${cost_12m['storage_cost']:>10,.0f}")
        print(f"    {'Base infra':<25} ${cost_now['base_infra_cost']:>10,.0f} ${cost_3m['base_infra_cost']:>10,.0f} ${cost_6m['base_infra_cost']:>10,.0f} ${cost_12m['base_infra_cost']:>10,.0f}")
        print(f"    {'─' * 58}")
        print(f"    {'TOTAL':<25} ${cost_now['total_monthly']:>10,.0f} ${cost_3m['total_monthly']:>10,.0f} ${cost_6m['total_monthly']:>10,.0f} ${cost_12m['total_monthly']:>10,.0f}")
        print(f"    {'Cost/request':<25} ${cost_now['cost_per_request']:>10.4f} ${cost_3m['cost_per_request']:>10.4f} ${cost_6m['cost_per_request']:>10.4f} ${cost_12m['cost_per_request']:>10.4f}")
        print()

        # Recommendations
        print("  RECOMMENDATIONS")
        print(f"  {'─' * 60}")
        recommendations = self._generate_recommendations(current, proj_3, proj_6, proj_12, cost_now, cost_12m)
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. [{rec['priority']}] {rec['action']}")
            print(f"       Reason: {rec['reason']}")
            print(f"       When: {rec['when']}")
            print()

        # Break-even analysis
        print("  SELF-HOSTING BREAK-EVEN ANALYSIS")
        print(f"  {'─' * 60}")
        if cost_now['api_cost'] > 30000:
            savings = cost_now['api_cost'] - cost_now['gpu_cost']
            print(f"    Current API spend: ${cost_now['api_cost']:,.0f}/month")
            print(f"    Self-hosted GPU cost: ${cost_now['gpu_cost']:,.0f}/month")
            print(f"    Potential savings: ${savings:,.0f}/month")
            print(f"    Recommendation: EVALUATE self-hosting (spending > $30K/month on API)")
        else:
            print(f"    Current API spend: ${cost_now['api_cost']:,.0f}/month")
            print(f"    Self-hosting threshold: $30,000/month")
            print(f"    Recommendation: Continue using API providers (not at break-even yet)")
            months_to_breakeven = 0
            for m in range(1, 25):
                projected_api = self.calculate_monthly_cost(m)['api_cost']
                if projected_api > 30000:
                    months_to_breakeven = m
                    break
            if months_to_breakeven > 0:
                print(f"    Projected break-even: ~{months_to_breakeven} months from now")

        print()
        print("=" * 70)

    def _generate_recommendations(self, current, proj_3, proj_6, proj_12, cost_now, cost_12m) -> list:
        recommendations = []

        # Vector DB scaling
        if current["vector_db_utilization"] > 0.7:
            recommendations.append({
                "priority": "HIGH",
                "action": "Scale Vector DB cluster",
                "reason": f"Current utilization at {current['vector_db_utilization']:.0%}, above 70% threshold",
                "when": "Within 2 weeks",
            })

        # Cost optimization
        if cost_now["cost_per_request"] > 0.05:
            recommendations.append({
                "priority": "MEDIUM",
                "action": "Implement aggressive caching strategy",
                "reason": f"Cost per request (${cost_now['cost_per_request']:.4f}) exceeds $0.05 target",
                "when": "This quarter",
            })

        # Growth planning
        if proj_6["projected_peak_qps"] > self.usage.peak_qps * 2.5:
            recommendations.append({
                "priority": "HIGH",
                "action": "Negotiate higher rate limits with provider",
                "reason": f"Peak QPS projected to reach {proj_6['projected_peak_qps']:.0f} in 6 months",
                "when": "Within 1 month",
            })

        # Multi-provider
        recommendations.append({
            "priority": "MEDIUM",
            "action": "Establish secondary provider relationship",
            "reason": "Redundancy for availability SLO and rate limit headroom",
            "when": "This quarter",
        })

        # Storage
        if current["storage_growth_gb_per_month"] > 20:
            recommendations.append({
                "priority": "LOW",
                "action": "Implement data lifecycle policy (archive old vectors)",
                "reason": f"Growing at {current['storage_growth_gb_per_month']:.0f} GB/month",
                "when": "Next quarter",
            })

        return recommendations


def main():
    """Run capacity planning with example configuration."""
    # Example: Mid-size AI SaaS product
    usage = CurrentUsage(
        requests_per_day=75_000,
        avg_tokens_per_request=3_500,
        peak_qps=15.0,
        concurrent_users=200,
        total_vectors=8_000_000,
        vector_dimensions=1536,
        new_docs_per_day=500,
        chunks_per_doc=12,
        active_sessions=2_000,
        avg_session_size_kb=45.0,
        monthly_growth_rate=0.20,  # 20% month-over-month
    )

    infra = InfraConfig(
        input_cost_per_1m_tokens=2.50,
        output_cost_per_1m_tokens=10.00,
        input_output_ratio=0.70,
        gpu_cost_per_hour=3.50,  # H100
        tokens_per_gpu_per_sec=8_000,
        vector_node_memory_gb=64,
        vector_node_cost_per_month=450.0,
        redis_cost_per_gb_month=50.0,
        storage_cost_per_gb_month=0.10,
        base_infra_cost_per_month=2_500.0,
    )

    slos = SLORequirements(
        availability_target=0.999,
        latency_p95_ms=5000,
        min_redundancy_factor=1.5,
    )

    planner = CapacityPlanner(usage, infra, slos)
    planner.generate_report()


if __name__ == "__main__":
    main()
