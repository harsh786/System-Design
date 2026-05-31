"""
Strategy Analyzer for AI Systems
=================================
Analyzes an AI system's metrics and generates technical strategy
recommendations using Richard Rumelt's Good Strategy framework.

Demonstrates how to connect system metrics to strategic decisions -
a core Staff Architect skill.

Usage: python3 main.py

No external dependencies required.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from enum import Enum
import json


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class SystemMetrics:
    """Simulated system metrics for an AI platform."""
    # Performance
    latency_p50_ms: float
    latency_p99_ms: float
    throughput_qps: float
    error_rate_percent: float
    
    # Cost
    monthly_cost_usd: float
    cost_per_query_usd: float
    cost_growth_rate_percent: float  # QoQ
    
    # Scale
    daily_requests: int
    total_documents: int  # for RAG systems
    num_models: int
    num_teams: int
    
    # Reliability
    availability_percent: float
    incidents_last_quarter: int
    mttr_minutes: float  # Mean time to recovery
    
    # Quality
    eval_coverage_percent: float
    quality_score: float  # 0-1 scale
    regression_incidents: int


@dataclass
class Diagnosis:
    """A diagnosed problem following Rumelt's framework."""
    title: str
    severity: Severity
    evidence: List[str]
    root_cause: str
    if_unaddressed: str


@dataclass
class GuidingPolicy:
    """A guiding policy that constrains solution space."""
    name: str
    statement: str
    rationale: str
    tradeoff: str
    addresses: List[str]  # Which diagnoses this addresses


@dataclass
class Action:
    """A specific coherent action."""
    quarter: str
    title: str
    description: str
    success_metric: str
    dependencies: List[str]


def create_sample_system() -> SystemMetrics:
    """Create a realistic AI system with several problems to diagnose."""
    return SystemMetrics(
        latency_p50_ms=2300,
        latency_p99_ms=8100,
        throughput_qps=115,
        error_rate_percent=2.1,
        monthly_cost_usd=2_100_000,
        cost_per_query_usd=0.007,
        cost_growth_rate_percent=40,
        daily_requests=10_000_000,
        total_documents=50_000_000,
        num_models=3,
        num_teams=12,
        availability_percent=99.5,
        incidents_last_quarter=3,
        mttr_minutes=240,
        eval_coverage_percent=35,
        quality_score=0.72,
        regression_incidents=5,
    )


def diagnose_system(metrics: SystemMetrics) -> List[Diagnosis]:
    """
    Analyze metrics to produce diagnoses.
    
    TEACHING POINT: Diagnosis is the hardest part of strategy. It's not
    just listing symptoms - it's identifying the UNDERLYING pattern that
    connects symptoms. A good diagnosis reframes the situation.
    """
    diagnoses = []
    
    # Diagnosis 1: Cost trajectory
    if metrics.cost_growth_rate_percent > 25:
        projected_12mo = metrics.monthly_cost_usd * (1 + metrics.cost_growth_rate_percent/100) ** 4
        diagnoses.append(Diagnosis(
            title="Unsustainable Cost Trajectory",
            severity=Severity.CRITICAL,
            evidence=[
                f"Monthly cost: ${metrics.monthly_cost_usd:,.0f} growing {metrics.cost_growth_rate_percent}% QoQ",
                f"Projected 12-month cost: ${projected_12mo:,.0f}/month",
                f"Cost per query: ${metrics.cost_per_query_usd:.4f} with no optimization layer",
                f"No caching, no model routing, no query classification",
            ],
            root_cause=(
                "Architecture treats all queries equally - a simple FAQ lookup "
                "uses the same expensive model as a complex reasoning task. No "
                "tiering, no caching, no cost-aware routing."
            ),
            if_unaddressed=(
                f"At {metrics.cost_growth_rate_percent}% QoQ growth, costs hit "
                f"${projected_12mo:,.0f}/month in 12 months. This is likely "
                f"unsustainable and will force reactive cost-cutting that harms quality."
            ),
        ))
    
    # Diagnosis 2: Reliability
    if metrics.availability_percent < 99.9 and metrics.incidents_last_quarter > 2:
        hourly_revenue_impact = metrics.monthly_cost_usd * 0.025  # rough estimate
        diagnoses.append(Diagnosis(
            title="Single-Provider Dependency Creates Cascading Failures",
            severity=Severity.HIGH,
            evidence=[
                f"Availability: {metrics.availability_percent}% (target: 99.9%)",
                f"Incidents last quarter: {metrics.incidents_last_quarter}",
                f"MTTR: {metrics.mttr_minutes} minutes (target: <30 min)",
                f"No automatic failover between providers",
            ],
            root_cause=(
                "Direct coupling to single model provider with no abstraction layer. "
                "When provider degrades, all products degrade simultaneously. No "
                "circuit breaking, no fallback models, no graceful degradation."
            ),
            if_unaddressed=(
                f"Each hour of downtime costs ~${hourly_revenue_impact:,.0f}. With "
                f"{metrics.incidents_last_quarter} incidents/quarter averaging "
                f"{metrics.mttr_minutes} min MTTR, annual impact is significant. "
                f"Risk increases as we scale to more teams."
            ),
        ))
    
    # Diagnosis 3: Quality blind spots
    if metrics.eval_coverage_percent < 50:
        diagnoses.append(Diagnosis(
            title="Quality Regression Goes Undetected",
            severity=Severity.HIGH,
            evidence=[
                f"Eval coverage: {metrics.eval_coverage_percent}% of use cases",
                f"Quality regressions last quarter: {metrics.regression_incidents}",
                f"Quality score: {metrics.quality_score:.2f} (no trend data available)",
                f"No automated quality monitoring in production",
            ],
            root_cause=(
                "Evaluation is treated as optional, not infrastructure. Each team "
                "builds (or doesn't build) their own eval. No shared framework, "
                "no continuous monitoring, no regression detection."
            ),
            if_unaddressed=(
                "Model updates, prompt changes, and data drift will cause quality "
                "regressions that reach users undetected. As we add more AI features, "
                "the probability of undetected regression approaches certainty."
            ),
        ))
    
    # Diagnosis 4: Latency
    if metrics.latency_p99_ms > 5000:
        diagnoses.append(Diagnosis(
            title="Tail Latency Degrades User Experience",
            severity=Severity.MEDIUM,
            evidence=[
                f"P50 latency: {metrics.latency_p50_ms}ms",
                f"P99 latency: {metrics.latency_p99_ms}ms ({metrics.latency_p99_ms/metrics.latency_p50_ms:.1f}x p50)",
                f"No request-level latency budgets",
                f"No caching layer for repeated queries",
            ],
            root_cause=(
                "All requests treated synchronously with no tiering. Long-tail "
                "latency caused by complex queries hitting model cold paths, "
                "RAG retrieval on large document sets, and lack of caching."
            ),
            if_unaddressed=(
                "User experience degrades for 1% of requests (at 10M/day = 100K "
                "bad experiences daily). As document corpus grows, retrieval latency "
                "will worsen without architectural intervention."
            ),
        ))
    
    # Diagnosis 5: Scaling bottleneck
    if metrics.total_documents > 30_000_000 and metrics.num_teams > 8:
        diagnoses.append(Diagnosis(
            title="RAG Architecture Can't Scale to Next Growth Phase",
            severity=Severity.MEDIUM,
            evidence=[
                f"Current documents: {metrics.total_documents:,}",
                f"Teams with independent RAG: {metrics.num_teams}",
                f"Duplicated RAG infrastructure across teams",
                f"No hierarchical retrieval for large corpora",
            ],
            root_cause=(
                "Each team runs independent RAG pipelines. This means N copies of "
                "similar infrastructure, N different chunking strategies, and no "
                "shared learning about retrieval quality. Doesn't scale past 100M docs."
            ),
            if_unaddressed=(
                "As document corpus grows toward 200M (projected in 12 months), "
                "retrieval quality will degrade and infrastructure costs will "
                "multiply. Teams will build increasingly divergent solutions."
            ),
        ))
    
    return diagnoses


def generate_policies(diagnoses: List[Diagnosis]) -> List[GuidingPolicy]:
    """
    Generate guiding policies that address diagnosed problems.
    
    TEACHING POINT: Policies are NOT actions. They're principles that
    constrain which actions are coherent. A good policy makes many
    individual decisions obvious.
    """
    policies = []
    
    diagnosis_titles = [d.title for d in diagnoses]
    
    # Policy based on cost diagnosis
    if any("Cost" in d for d in diagnosis_titles):
        policies.append(GuidingPolicy(
            name="Cost-Aware by Default",
            statement=(
                "Every AI request has an explicit cost budget. The platform optimizes "
                "within that budget automatically. Teams set budgets; platform meets them."
            ),
            rationale=(
                "Cost grows with traffic unless we build optimization into the architecture. "
                "Making cost explicit (not invisible) changes behavior at every level."
            ),
            tradeoff=(
                "Accepting: Slightly higher latency for cost-optimized routes. "
                "Accepting: Engineering investment in routing infrastructure. "
                "Rejecting: 'Use the best model for everything' approach."
            ),
            addresses=["Unsustainable Cost Trajectory"],
        ))
    
    # Policy based on reliability diagnosis
    if any("Failure" in d or "Provider" in d for d in diagnosis_titles):
        policies.append(GuidingPolicy(
            name="Graceful Degradation Over Hard Failure",
            statement=(
                "When a provider fails, serve degraded responses rather than errors. "
                "Quality can flex temporarily; availability cannot. Automatic failover "
                "within 30 seconds, no human intervention required."
            ),
            rationale=(
                "Users tolerate slightly lower quality answers. They don't tolerate "
                "no answer at all. Our SLA is availability, not perfection."
            ),
            tradeoff=(
                "Accepting: Sometimes serving responses from a less-preferred model. "
                "Accepting: Complexity of multi-provider abstraction layer. "
                "Rejecting: 'One provider is good enough' approach."
            ),
            addresses=["Single-Provider Dependency Creates Cascading Failures"],
        ))
    
    # Policy based on quality diagnosis
    if any("Quality" in d or "Regression" in d for d in diagnosis_titles):
        policies.append(GuidingPolicy(
            name="Evaluation as Infrastructure, Not Afterthought",
            statement=(
                "No AI feature ships without automated evaluation. The platform provides "
                "eval infrastructure; teams provide domain-specific test cases. Quality "
                "is monitored continuously, not tested once."
            ),
            rationale=(
                "AI systems degrade silently. Without continuous evaluation, quality "
                "regressions are discovered by users, not engineers. This is unacceptable "
                "at scale."
            ),
            tradeoff=(
                "Accepting: Slower initial feature delivery (eval setup required). "
                "Accepting: Platform team maintains eval infrastructure. "
                "Rejecting: 'Ship fast, evaluate later' approach."
            ),
            addresses=["Quality Regression Goes Undetected"],
        ))
    
    # Policy based on scale diagnosis
    if any("Scale" in d or "RAG" in d for d in diagnosis_titles):
        policies.append(GuidingPolicy(
            name="Shared Retrieval, Custom Ranking",
            statement=(
                "Retrieval infrastructure (indexing, embedding, storage) is centralized. "
                "Product-specific relevance (ranking, filtering, reranking) is configured "
                "per-team. Teams don't manage vector infrastructure."
            ),
            rationale=(
                "80% of RAG infrastructure is the same across teams. Only the last-mile "
                "relevance tuning is product-specific. Centralizing the 80% eliminates "
                "duplication and enables shared optimization."
            ),
            tradeoff=(
                "Accepting: Teams lose full control over retrieval internals. "
                "Accepting: Platform team takes on operational burden. "
                "Rejecting: 'Every team manages their own vector DB' approach."
            ),
            addresses=["RAG Architecture Can't Scale to Next Growth Phase"],
        ))
    
    return policies


def generate_actions(policies: List[GuidingPolicy], metrics: SystemMetrics) -> List[Action]:
    """Generate coherent, sequenced actions that implement the policies."""
    actions = []
    
    # Q1: Foundation - address most critical issues
    actions.extend([
        Action(
            quarter="Q1",
            title="Ship Model Gateway (Intent-Based Routing)",
            description=(
                "Build gateway service that abstracts provider APIs. Teams declare "
                "intent (quality/latency/cost requirements), gateway routes optimally. "
                "Start with simple routing rules, add intelligence over time."
            ),
            success_metric="Gateway serving 100% of traffic for 2 pilot teams",
            dependencies=[],
        ),
        Action(
            quarter="Q1",
            title="Implement Semantic Caching Layer",
            description=(
                "Cache responses for semantically similar queries. Target 30% hit rate "
                "based on analysis of query patterns. Immediate cost reduction without "
                "changing any team's code."
            ),
            success_metric="30% cache hit rate, $300K/month cost reduction",
            dependencies=["Ship Model Gateway"],
        ),
        Action(
            quarter="Q1",
            title="Launch Evaluation Framework v1",
            description=(
                "Shared evaluation infrastructure: dataset management, metric computation, "
                "regression detection. Teams provide test cases, platform provides tooling. "
                "Mandatory for new features, opt-in for existing."
            ),
            success_metric="Eval coverage from 35% to 50%",
            dependencies=[],
        ),
    ])
    
    # Q2: Migration and reliability
    actions.extend([
        Action(
            quarter="Q2",
            title="Multi-Provider Failover",
            description=(
                "Add Anthropic and Google as fallback providers in gateway. Automatic "
                "failover within 30 seconds of provider degradation detection. No team "
                "code changes required."
            ),
            success_metric="Zero product-visible outages from provider failures",
            dependencies=["Ship Model Gateway"],
        ),
        Action(
            quarter="Q2",
            title="Migrate Top 5 Teams to Gateway",
            description=(
                "Move highest-traffic teams to gateway. Provide migration support "
                "(dedicated engineer per team for 1 week). Document patterns for "
                "remaining teams to self-serve."
            ),
            success_metric="5 teams migrated, 60% of traffic through gateway",
            dependencies=["Ship Model Gateway", "Multi-Provider Failover"],
        ),
        Action(
            quarter="Q2",
            title="Centralized Retrieval Service v1",
            description=(
                "Shared vector search service replacing per-team infrastructure. "
                "Support for multiple index types, automatic embedding management. "
                "Start with 2 teams with highest document volumes."
            ),
            success_metric="2 teams on shared retrieval, latency parity with old system",
            dependencies=[],
        ),
    ])
    
    # Q3-Q4: Optimization and full migration
    actions.extend([
        Action(
            quarter="Q3",
            title="Intelligent Cost-Optimized Routing",
            description=(
                "ML-based router classifies query complexity and routes to "
                "appropriate model tier. Simple queries → cheaper models. Complex "
                "queries → premium models. Transparent to teams."
            ),
            success_metric="40% cost reduction vs Q1 baseline for migrated teams",
            dependencies=["Migrate Top 5 Teams to Gateway"],
        ),
        Action(
            quarter="Q4",
            title="Full Platform Migration",
            description=(
                "Remaining 7 teams migrate to gateway and shared retrieval. "
                "Self-serve migration path based on Q2 learnings. Platform team "
                "provides support but teams drive their own migration."
            ),
            success_metric="All 12 teams on platform, old infrastructure decommissioned",
            dependencies=["Intelligent Cost-Optimized Routing"],
        ),
    ])
    
    return actions


def generate_strategy_document(
    metrics: SystemMetrics,
    diagnoses: List[Diagnosis],
    policies: List[GuidingPolicy],
    actions: List[Action],
) -> None:
    """Print the complete strategy document."""
    print()
    print("=" * 70)
    print("  GENERATED TECHNICAL STRATEGY DOCUMENT")
    print("  AI Platform Technical Strategy 2025")
    print("=" * 70)
    
    # Context
    print()
    print("━" * 70)
    print("  1. CONTEXT")
    print("━" * 70)
    print(f"""
  Our AI platform serves {metrics.daily_requests:,} requests/day across
  {metrics.num_models} foundation models with {metrics.availability_percent}% availability.
  {metrics.num_teams} product teams consume the platform.

  Key Metrics:
    • Latency: {metrics.latency_p50_ms}ms p50, {metrics.latency_p99_ms}ms p99
    • Monthly cost: ${metrics.monthly_cost_usd:,.0f} (growing {metrics.cost_growth_rate_percent}% QoQ)
    • RAG corpus: {metrics.total_documents:,} documents
    • Eval coverage: {metrics.eval_coverage_percent}% of production use cases
    • Incidents: {metrics.incidents_last_quarter} provider-caused outages last quarter
""")
    
    # Diagnosis
    print("━" * 70)
    print("  2. DIAGNOSIS")
    print("━" * 70)
    print()
    for i, d in enumerate(diagnoses, 1):
        print(f"  [{d.severity.value}] {d.title}")
        print(f"  Root Cause: {d.root_cause[:100]}...")
        print(f"  If Unaddressed: {d.if_unaddressed[:100]}...")
        print()
    
    # Guiding Policies
    print("━" * 70)
    print("  3. GUIDING POLICIES")
    print("━" * 70)
    print()
    for i, p in enumerate(policies, 1):
        print(f"  Policy {i}: {p.name}")
        print(f"    \"{p.statement[:100]}...\"")
        print(f"    Tradeoff: {p.tradeoff[:80]}...")
        print()
    
    # Actions
    print("━" * 70)
    print("  4. COHERENT ACTIONS")
    print("━" * 70)
    print()
    current_q = ""
    for a in actions:
        if a.quarter != current_q:
            current_q = a.quarter
            print(f"  ── {current_q} ──")
        print(f"    • {a.title}")
        print(f"      Metric: {a.success_metric}")
        print()


def main():
    """Main execution flow demonstrating the strategy analysis process."""
    print("=" * 70)
    print("  STRATEGY ANALYZER FOR AI SYSTEMS")
    print("  Applying Rumelt's Good Strategy Framework")
    print("=" * 70)
    print()
    print("  This tool demonstrates how a Staff Architect connects system")
    print("  metrics to strategic decisions. The key insight: strategy is")
    print("  not 'what should we build?' but 'what's the actual problem")
    print("  and what approach addresses it coherently?'")
    print()
    
    # Step 1: Gather metrics
    print("─" * 70)
    print("  STEP 1: SYSTEM METRICS (Simulated)")
    print("─" * 70)
    metrics = create_sample_system()
    print(f"    Daily requests:    {metrics.daily_requests:>12,}")
    print(f"    Monthly cost:      ${metrics.monthly_cost_usd:>11,.0f}")
    print(f"    Latency p99:       {metrics.latency_p99_ms:>12,.0f} ms")
    print(f"    Availability:      {metrics.availability_percent:>12.1f}%")
    print(f"    Eval coverage:     {metrics.eval_coverage_percent:>12.0f}%")
    print()
    
    # Step 2: Diagnose
    print("─" * 70)
    print("  STEP 2: DIAGNOSIS (The hard part)")
    print("─" * 70)
    print()
    print("  💡 TEACHING POINT: Diagnosis is where most strategies fail.")
    print("     It's not just listing what's wrong - it's identifying the")
    print("     PATTERN that connects the symptoms. Watch how metrics")
    print("     combine into root cause insights:")
    print()
    
    diagnoses = diagnose_system(metrics)
    for d in diagnoses:
        print(f"  [{d.severity.value}] {d.title}")
        print(f"    Evidence: {d.evidence[0]}")
        print(f"    Root Cause: {d.root_cause[:80]}...")
        print()
    
    # Step 3: Generate policies
    print("─" * 70)
    print("  STEP 3: GUIDING POLICIES")
    print("─" * 70)
    print()
    print("  💡 TEACHING POINT: Policies are NOT actions. They're decisions")
    print("     about APPROACH that make specific actions obvious. A good")
    print("     policy says 'We will prioritize X over Y when forced to choose.'")
    print()
    
    policies = generate_policies(diagnoses)
    for p in policies:
        print(f"  Policy: {p.name}")
        print(f"    \"{p.statement}\"")
        print(f"    Tradeoff: {p.tradeoff[:70]}...")
        print(f"    Addresses: {', '.join(p.addresses)}")
        print()
    
    # Step 4: Generate actions
    print("─" * 70)
    print("  STEP 4: COHERENT ACTIONS")
    print("─" * 70)
    print()
    print("  💡 TEACHING POINT: 'Coherent' means actions reinforce each other.")
    print("     The gateway enables failover enables cost routing. They're not")
    print("     independent projects - they're a coordinated campaign.")
    print()
    
    actions = generate_actions(policies, metrics)
    current_q = ""
    for a in actions:
        if a.quarter != current_q:
            current_q = a.quarter
            print(f"  ── {current_q} ──")
        print(f"    {a.title}")
        print(f"      → {a.success_metric}")
        if a.dependencies:
            print(f"      Depends on: {', '.join(a.dependencies)}")
        print()
    
    # Generate full document
    generate_strategy_document(metrics, diagnoses, policies, actions)
    
    # Summary
    print()
    print("=" * 70)
    print("  KEY TAKEAWAYS")
    print("=" * 70)
    print("""
  1. METRICS → DIAGNOSIS: Don't jump to solutions. Understand the problem.
  2. DIAGNOSIS → POLICIES: Policies constrain the solution space.
  3. POLICIES → ACTIONS: Actions implement policies coherently.
  4. TRADEOFFS EXPLICIT: Every policy accepts something and rejects something.
  5. MEASURABLE: Every action has a success metric.
  
  The difference between a Senior and Staff engineer:
    Senior: "We should build a model gateway" (jumps to solution)
    Staff:  "Our coupling to single provider creates cascading failures
             AND prevents cost optimization. An abstraction layer 
             addresses both." (diagnosis → coherent solution)
""")


if __name__ == "__main__":
    main()
