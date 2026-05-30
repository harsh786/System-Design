"""
Capacity Planning System for AI Infrastructure.

Computes per-component capacity requirements, cost projections,
provider limit checks, and scaling recommendations from input parameters.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Input Parameters
# ---------------------------------------------------------------------------

@dataclass
class WorkloadProfile:
    """Describes the expected workload characteristics."""

    daily_active_users: int = 1_000_000
    requests_per_user_per_day: float = 10.0
    avg_agent_steps: float = 4.0
    model_calls_per_step: float = 1.5
    avg_input_tokens: int = 1500
    avg_output_tokens: int = 500
    retrieval_queries_per_step: float = 1.2
    rerank_ratio: float = 0.8  # fraction of retrieval queries that trigger reranking
    embedding_calls_per_request: float = 1.5
    tool_probability_per_step: float = 0.5
    tools_per_step_when_used: float = 2.0
    safety_checks_per_step: float = 2.0
    spans_per_request: float = 25.0
    eval_sample_rate: float = 0.05
    eval_complexity_multiplier: float = 10.0
    memory_writes_per_request: float = 2.0
    cache_reads_per_request: float = 12.0
    cache_writes_per_request: float = 3.0
    budget_checks_per_request: float = 2.0

    # Peak multiplier (peak hour traffic / average hour traffic)
    peak_multiplier: float = 3.0
    # Headroom factor (provision above peak)
    headroom_factor: float = 1.3


@dataclass
class ProviderLimits:
    """Known limits for external providers."""

    model_rpm: int = 10_000  # requests per minute
    model_tpm: int = 2_000_000  # tokens per minute
    embedding_rpm: int = 50_000
    vector_db_qps: int = 10_000
    reranker_qps: int = 5_000


@dataclass
class CostRates:
    """Cost per unit for projections."""

    model_input_per_1k_tokens: float = 0.005
    model_output_per_1k_tokens: float = 0.015
    embedding_per_1k_tokens: float = 0.0001
    reranker_per_1k_queries: float = 0.10
    vector_db_per_million_queries: float = 5.0
    tool_call_avg_cost: float = 0.001
    trace_per_million_spans: float = 2.0
    cache_per_gb_hour: float = 0.05
    queue_per_million_messages: float = 0.40


# ---------------------------------------------------------------------------
# Capacity Estimation Engine
# ---------------------------------------------------------------------------

@dataclass
class CapacityEstimate:
    """Computed capacity requirements per component."""

    # Raw numbers
    total_daily_requests: float = 0.0
    peak_hour_requests: float = 0.0
    peak_rps: float = 0.0

    # Per-component QPS/throughput
    model_qps: float = 0.0
    model_tokens_per_sec_input: float = 0.0
    model_tokens_per_sec_output: float = 0.0
    retrieval_qps: float = 0.0
    reranker_qps: float = 0.0
    embedding_qps: float = 0.0
    tool_qps: float = 0.0
    safety_qps: float = 0.0
    trace_spans_per_sec: float = 0.0
    eval_ops_per_sec: float = 0.0
    memory_ops_per_sec: float = 0.0
    cache_ops_per_sec: float = 0.0
    budget_checks_per_sec: float = 0.0
    queue_depth_peak: float = 0.0

    # With headroom
    provisioned_model_qps: float = 0.0
    provisioned_retrieval_qps: float = 0.0
    provisioned_tool_qps: float = 0.0


class CapacityPlanner:
    """Computes capacity requirements from workload profile."""

    def __init__(
        self,
        profile: WorkloadProfile,
        provider_limits: ProviderLimits | None = None,
        cost_rates: CostRates | None = None,
    ):
        self.profile = profile
        self.limits = provider_limits or ProviderLimits()
        self.costs = cost_rates or CostRates()
        self.estimate = CapacityEstimate()
        self._compute()

    def _compute(self) -> None:
        p = self.profile
        e = self.estimate

        # --- Basic throughput ---
        e.total_daily_requests = p.daily_active_users * p.requests_per_user_per_day
        avg_hour_requests = e.total_daily_requests / 24.0
        e.peak_hour_requests = avg_hour_requests * p.peak_multiplier
        e.peak_rps = e.peak_hour_requests / 3600.0

        # --- Per-component ---
        e.model_qps = e.peak_rps * p.avg_agent_steps * p.model_calls_per_step
        e.model_tokens_per_sec_input = e.model_qps * p.avg_input_tokens
        e.model_tokens_per_sec_output = e.model_qps * p.avg_output_tokens
        e.retrieval_qps = e.peak_rps * p.avg_agent_steps * p.retrieval_queries_per_step
        e.reranker_qps = e.retrieval_qps * p.rerank_ratio
        e.embedding_qps = e.peak_rps * p.embedding_calls_per_request
        e.tool_qps = (
            e.peak_rps
            * p.avg_agent_steps
            * p.tool_probability_per_step
            * p.tools_per_step_when_used
        )
        e.safety_qps = e.peak_rps * p.avg_agent_steps * p.safety_checks_per_step
        e.trace_spans_per_sec = e.peak_rps * p.spans_per_request
        e.eval_ops_per_sec = e.peak_rps * p.eval_sample_rate * p.eval_complexity_multiplier
        e.memory_ops_per_sec = e.peak_rps * p.memory_writes_per_request
        e.cache_ops_per_sec = e.peak_rps * (p.cache_reads_per_request + p.cache_writes_per_request)
        e.budget_checks_per_sec = e.peak_rps * p.budget_checks_per_request

        # Queue depth estimate (assuming 2s avg processing time)
        avg_processing_sec = 2.0
        e.queue_depth_peak = e.peak_rps * avg_processing_sec

        # Provisioned (with headroom)
        h = p.headroom_factor
        e.provisioned_model_qps = e.model_qps * h
        e.provisioned_retrieval_qps = e.retrieval_qps * h
        e.provisioned_tool_qps = e.tool_qps * h

    # ---------------------------------------------------------------------------
    # Provider Limit Checks
    # ---------------------------------------------------------------------------

    def check_provider_limits(self) -> list[dict[str, Any]]:
        """Return warnings where projected usage exceeds provider limits."""
        warnings: list[dict[str, Any]] = []
        e = self.estimate
        l = self.limits

        model_rpm_needed = e.provisioned_model_qps * 60
        if model_rpm_needed > l.model_rpm:
            warnings.append({
                "component": "model",
                "metric": "RPM",
                "needed": model_rpm_needed,
                "limit": l.model_rpm,
                "ratio": model_rpm_needed / l.model_rpm,
                "recommendation": f"Need {math.ceil(model_rpm_needed / l.model_rpm)} provider accounts or rate-limit tier upgrade",
            })

        total_tpm = (e.model_tokens_per_sec_input + e.model_tokens_per_sec_output) * 60
        if total_tpm > l.model_tpm:
            warnings.append({
                "component": "model",
                "metric": "TPM",
                "needed": total_tpm,
                "limit": l.model_tpm,
                "ratio": total_tpm / l.model_tpm,
                "recommendation": f"Need {math.ceil(total_tpm / l.model_tpm)}x TPM quota or model routing to spread load",
            })

        embedding_rpm_needed = e.embedding_qps * 60
        if embedding_rpm_needed > l.embedding_rpm:
            warnings.append({
                "component": "embedding",
                "metric": "RPM",
                "needed": embedding_rpm_needed,
                "limit": l.embedding_rpm,
                "recommendation": "Increase embedding batching or add provider accounts",
            })

        if e.provisioned_retrieval_qps > l.vector_db_qps:
            warnings.append({
                "component": "vector_db",
                "metric": "QPS",
                "needed": e.provisioned_retrieval_qps,
                "limit": l.vector_db_qps,
                "recommendation": "Add read replicas or shard vector index",
            })

        if e.reranker_qps > l.reranker_qps:
            warnings.append({
                "component": "reranker",
                "metric": "QPS",
                "needed": e.reranker_qps,
                "limit": l.reranker_qps,
                "recommendation": "Deploy self-hosted reranker or reduce rerank ratio",
            })

        return warnings

    # ---------------------------------------------------------------------------
    # Cost Projection
    # ---------------------------------------------------------------------------

    def project_daily_cost(self) -> dict[str, float]:
        """Estimate daily cost by component."""
        e = self.estimate
        c = self.costs
        seconds_per_day = 86400
        # Use average (not peak) for cost — peak is ~peak_mult/24 of daily
        avg_rps = e.total_daily_requests / seconds_per_day

        # For cost, compute total daily volume
        daily_model_calls = e.total_daily_requests * self.profile.avg_agent_steps * self.profile.model_calls_per_step
        daily_input_tokens = daily_model_calls * self.profile.avg_input_tokens
        daily_output_tokens = daily_model_calls * self.profile.avg_output_tokens
        daily_retrieval = e.total_daily_requests * self.profile.avg_agent_steps * self.profile.retrieval_queries_per_step
        daily_reranker = daily_retrieval * self.profile.rerank_ratio
        daily_embeddings = e.total_daily_requests * self.profile.embedding_calls_per_request
        daily_tools = (
            e.total_daily_requests
            * self.profile.avg_agent_steps
            * self.profile.tool_probability_per_step
            * self.profile.tools_per_step_when_used
        )
        daily_spans = e.total_daily_requests * self.profile.spans_per_request

        costs = {
            "model_input": (daily_input_tokens / 1000) * c.model_input_per_1k_tokens,
            "model_output": (daily_output_tokens / 1000) * c.model_output_per_1k_tokens,
            "embedding": (daily_embeddings * 500 / 1000) * c.embedding_per_1k_tokens,  # assume 500 tokens avg
            "reranker": (daily_reranker / 1000) * c.reranker_per_1k_queries,
            "vector_db": (daily_retrieval / 1_000_000) * c.vector_db_per_million_queries,
            "tool_calls": daily_tools * c.tool_call_avg_cost,
            "traces": (daily_spans / 1_000_000) * c.trace_per_million_spans,
            "cache": 50 * 24 * c.cache_per_gb_hour,  # assume 50GB cache
            "queue": (e.total_daily_requests / 1_000_000) * c.queue_per_million_messages,
        }
        costs["total"] = sum(costs.values())
        costs["monthly_estimate"] = costs["total"] * 30
        return costs

    # ---------------------------------------------------------------------------
    # Scaling Trigger Recommendations
    # ---------------------------------------------------------------------------

    def scaling_triggers(self) -> list[dict[str, Any]]:
        """Recommend auto-scaling triggers per component."""
        e = self.estimate
        return [
            {
                "component": "agent_workers",
                "scale_up": "queue_depth > 100 OR p95_latency > 5s",
                "scale_down": "queue_depth < 10 AND p95_latency < 1s for 5min",
                "min_instances": max(4, int(e.peak_rps / 50)),
                "max_instances": max(20, int(e.peak_rps / 10)),
            },
            {
                "component": "vector_db_replicas",
                "scale_up": "read_latency_p99 > 200ms OR qps > 80% capacity",
                "scale_down": "read_latency_p99 < 50ms AND qps < 40% capacity for 10min",
                "min_replicas": max(2, int(e.provisioned_retrieval_qps / 3000)),
                "max_replicas": max(6, int(e.provisioned_retrieval_qps / 1000)),
            },
            {
                "component": "cache_cluster",
                "scale_up": "memory_usage > 80% OR eviction_rate > 5%",
                "scale_down": "memory_usage < 40% for 30min",
                "min_nodes": max(3, int(e.cache_ops_per_sec / 50000)),
                "max_nodes": max(9, int(e.cache_ops_per_sec / 10000)),
            },
            {
                "component": "queue_consumers",
                "scale_up": "queue_lag > 1000 messages OR oldest_message > 10s",
                "scale_down": "queue_lag < 100 AND oldest_message < 1s for 5min",
                "min_consumers": max(4, int(e.peak_rps / 30)),
                "max_consumers": max(50, int(e.peak_rps / 5)),
            },
            {
                "component": "trace_ingestion",
                "scale_up": "ingest_lag > 5s OR drop_rate > 0.1%",
                "scale_down": "ingest_lag < 500ms for 10min",
                "min_instances": max(2, int(e.trace_spans_per_sec / 5000)),
                "max_instances": max(10, int(e.trace_spans_per_sec / 1000)),
            },
        ]

    # ---------------------------------------------------------------------------
    # Report Generation
    # ---------------------------------------------------------------------------

    def generate_report(self) -> str:
        """Generate a human-readable capacity planning report."""
        e = self.estimate
        p = self.profile
        warnings = self.check_provider_limits()
        costs = self.project_daily_cost()
        triggers = self.scaling_triggers()

        lines = [
            "=" * 70,
            "          AI INFRASTRUCTURE CAPACITY PLANNING REPORT",
            "=" * 70,
            "",
            "INPUT PARAMETERS",
            "-" * 40,
            f"  Daily Active Users:       {p.daily_active_users:>12,}",
            f"  Requests/User/Day:        {p.requests_per_user_per_day:>12.1f}",
            f"  Avg Agent Steps:          {p.avg_agent_steps:>12.1f}",
            f"  Model Calls/Step:         {p.model_calls_per_step:>12.1f}",
            f"  Avg Input Tokens:         {p.avg_input_tokens:>12,}",
            f"  Avg Output Tokens:        {p.avg_output_tokens:>12,}",
            f"  Peak Multiplier:          {p.peak_multiplier:>12.1f}x",
            f"  Headroom Factor:          {p.headroom_factor:>12.1f}x",
            "",
            "THROUGHPUT ESTIMATES (at peak)",
            "-" * 40,
            f"  Total Daily Requests:     {e.total_daily_requests:>12,.0f}",
            f"  Peak Hour Requests:       {e.peak_hour_requests:>12,.0f}",
            f"  Peak RPS:                 {e.peak_rps:>12,.1f}",
            "",
            "PER-COMPONENT CAPACITY (peak)",
            "-" * 40,
            f"  Model QPS:                {e.model_qps:>12,.1f}",
            f"  Model Input Tokens/sec:   {e.model_tokens_per_sec_input:>12,.0f}",
            f"  Model Output Tokens/sec:  {e.model_tokens_per_sec_output:>12,.0f}",
            f"  Retrieval QPS:            {e.retrieval_qps:>12,.1f}",
            f"  Reranker QPS:             {e.reranker_qps:>12,.1f}",
            f"  Embedding QPS:            {e.embedding_qps:>12,.1f}",
            f"  Tool QPS:                 {e.tool_qps:>12,.1f}",
            f"  Safety QPS:               {e.safety_qps:>12,.1f}",
            f"  Trace Spans/sec:          {e.trace_spans_per_sec:>12,.1f}",
            f"  Eval Ops/sec:             {e.eval_ops_per_sec:>12,.1f}",
            f"  Memory Ops/sec:           {e.memory_ops_per_sec:>12,.1f}",
            f"  Cache Ops/sec:            {e.cache_ops_per_sec:>12,.1f}",
            f"  Budget Checks/sec:        {e.budget_checks_per_sec:>12,.1f}",
            f"  Queue Depth (peak):       {e.queue_depth_peak:>12,.0f}",
            "",
            "PROVISIONED CAPACITY (with {:.0f}% headroom)".format((p.headroom_factor - 1) * 100),
            "-" * 40,
            f"  Model QPS:                {e.provisioned_model_qps:>12,.1f}",
            f"  Retrieval QPS:            {e.provisioned_retrieval_qps:>12,.1f}",
            f"  Tool QPS:                 {e.provisioned_tool_qps:>12,.1f}",
            "",
        ]

        # Provider limit warnings
        lines.append("PROVIDER LIMIT CHECKS")
        lines.append("-" * 40)
        if warnings:
            for w in warnings:
                lines.append(f"  WARNING [{w['component']}] {w['metric']}:")
                lines.append(f"    Needed: {w['needed']:,.0f} | Limit: {w['limit']:,.0f} | Ratio: {w['ratio']:.1f}x")
                lines.append(f"    -> {w['recommendation']}")
        else:
            lines.append("  All within provider limits.")
        lines.append("")

        # Cost projection
        lines.append("DAILY COST PROJECTION")
        lines.append("-" * 40)
        for k, v in costs.items():
            if k in ("total", "monthly_estimate"):
                lines.append(f"  {'─' * 30}")
            lines.append(f"  {k:<25} ${v:>12,.2f}")
        lines.append("")

        # Scaling triggers
        lines.append("SCALING TRIGGER RECOMMENDATIONS")
        lines.append("-" * 40)
        for t in triggers:
            lines.append(f"  [{t['component']}]")
            lines.append(f"    Scale up:   {t['scale_up']}")
            lines.append(f"    Scale down: {t['scale_down']}")
            lines.append(f"    Range:      {t.get('min_instances', t.get('min_replicas', t.get('min_nodes', t.get('min_consumers', '?'))))} - {t.get('max_instances', t.get('max_replicas', t.get('max_nodes', t.get('max_consumers', '?'))))}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Infrastructure Capacity Planner")
    parser.add_argument("--dau", type=int, default=1_000_000, help="Daily active users")
    parser.add_argument("--requests-per-user", type=float, default=10.0)
    parser.add_argument("--agent-steps", type=float, default=4.0)
    parser.add_argument("--model-calls-per-step", type=float, default=1.5)
    parser.add_argument("--input-tokens", type=int, default=1500)
    parser.add_argument("--output-tokens", type=int, default=500)
    parser.add_argument("--peak-multiplier", type=float, default=3.0)
    parser.add_argument("--headroom", type=float, default=1.3)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    profile = WorkloadProfile(
        daily_active_users=args.dau,
        requests_per_user_per_day=args.requests_per_user,
        avg_agent_steps=args.agent_steps,
        model_calls_per_step=args.model_calls_per_step,
        avg_input_tokens=args.input_tokens,
        avg_output_tokens=args.output_tokens,
        peak_multiplier=args.peak_multiplier,
        headroom_factor=args.headroom,
    )

    planner = CapacityPlanner(profile)

    if args.json:
        output = {
            "estimate": planner.estimate.__dict__,
            "warnings": planner.check_provider_limits(),
            "costs": planner.project_daily_cost(),
            "scaling_triggers": planner.scaling_triggers(),
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(planner.generate_report())


if __name__ == "__main__":
    main()
