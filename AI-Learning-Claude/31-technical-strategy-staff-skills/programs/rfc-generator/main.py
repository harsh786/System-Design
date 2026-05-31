"""
RFC Generator for AI Systems
=============================
Interactive RFC generator that demonstrates good RFC writing principles.
Asks structured questions about a proposed change and generates a properly
formatted RFC document with AI-specific sections.

Usage: python3 main.py

No external dependencies required.
"""

import textwrap
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class RFCInput:
    """Captures all input needed to generate an RFC."""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    summary: str = ""
    problem_statement: str = ""
    current_metrics: Dict[str, str] = field(default_factory=dict)
    why_now: str = ""
    proposed_solution: str = ""
    key_components: List[str] = field(default_factory=list)
    alternatives: List[Dict[str, str]] = field(default_factory=list)
    ai_concerns: Dict[str, str] = field(default_factory=dict)
    migration_phases: List[str] = field(default_factory=list)
    risks: List[Dict[str, str]] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    success_metrics: List[str] = field(default_factory=list)


def simulate_rfc_input() -> RFCInput:
    """
    Simulates interactive input for demonstration purposes.
    In a real tool, these would come from user prompts.
    
    TEACHING POINT: A good RFC generator doesn't just format text - it guides
    the author to think about things they might skip. Notice how we force
    consideration of alternatives, AI-specific concerns, and migration.
    """
    print("=" * 70)
    print("  RFC GENERATOR FOR AI SYSTEMS")
    print("  Generating a well-structured RFC with AI-specific sections")
    print("=" * 70)
    print()
    print("This tool demonstrates how to write an RFC that will be taken")
    print("seriously at Staff+ level. Let's walk through the sections.\n")
    
    rfc = RFCInput()
    
    # Simulate the interview process
    print("─" * 70)
    print("STEP 1: BASIC INFORMATION")
    print("─" * 70)
    print()
    print("  [Simulating input for demonstration]")
    print()
    
    rfc.title = "Migrate from Single-Model to Multi-Model Gateway"
    rfc.authors = ["Alex Chen (Staff AI Architect)", "Jordan Kim (Senior ML Engineer)"]
    rfc.reviewers = [
        "Platform Team Lead",
        "ML Infrastructure Manager",
        "Product Engineering Leads (3)",
        "SRE Lead",
    ]
    
    print(f"  Title: {rfc.title}")
    print(f"  Authors: {', '.join(rfc.authors)}")
    print(f"  Reviewers: {', '.join(rfc.reviewers)}")
    print()
    
    # Teaching point about reviewers
    print("  💡 TEACHING POINT: Notice the reviewer list includes:")
    print("     - Technical peers (Platform, ML Infra)")
    print("     - Stakeholders affected by the change (Product Eng)")
    print("     - Operational owners (SRE)")
    print("     A good RFC has reviewers who might DISAGREE with you.")
    print()
    
    print("─" * 70)
    print("STEP 2: MOTIVATION (Why does this matter?)")
    print("─" * 70)
    print()
    
    rfc.problem_statement = (
        "Our AI platform currently makes direct API calls to a single model "
        "provider (OpenAI). This creates single-point-of-failure risk, prevents "
        "cost optimization through model routing, and couples application logic "
        "to provider-specific APIs."
    )
    
    rfc.current_metrics = {
        "Daily requests": "10M inference requests/day",
        "Monthly cost": "$2.1M/month (growing 40% QoQ)",
        "Availability": "99.5% (target: 99.9%)",
        "Provider outages (last quarter)": "3 incidents, 12 hours total downtime",
        "Revenue impact per hour of downtime": "~$50K",
        "Teams affected": "12 product teams",
    }
    
    rfc.why_now = (
        "Two factors make this urgent: (1) Our contract renewal with OpenAI is "
        "in 4 months - we need multi-provider capability for negotiation leverage. "
        "(2) We've had 3 provider outages in the last quarter costing ~$200K in "
        "lost revenue. Competitor launched multi-model support last month."
    )
    
    print("  Problem Statement:")
    print(f"  {rfc.problem_statement}")
    print()
    print("  Current Metrics:")
    for k, v in rfc.current_metrics.items():
        print(f"    • {k}: {v}")
    print()
    print("  Why Now:")
    print(f"  {rfc.why_now}")
    print()
    
    print("  💡 TEACHING POINT: The motivation section must have NUMBERS.")
    print("     'Things are bad' is not motivation. '$200K lost revenue from")
    print("     3 outages last quarter' is motivation. Quantify the pain.")
    print()
    
    print("─" * 70)
    print("STEP 3: PROPOSED SOLUTION")
    print("─" * 70)
    print()
    
    rfc.proposed_solution = (
        "Build a unified model gateway service that abstracts model provider "
        "APIs behind an intent-based interface. Applications declare quality, "
        "latency, and cost requirements; the gateway routes to the optimal model "
        "and handles failover automatically."
    )
    
    rfc.key_components = [
        "Intent-Based Router: Maps (quality, latency, cost) requirements to model selection",
        "Provider Abstraction Layer: Unified API across OpenAI, Anthropic, Google, open-source",
        "Automatic Failover: Detects provider degradation and reroutes within 30 seconds",
        "Semantic Cache: Deduplicates semantically similar requests (target 30% hit rate)",
        "Cost Attribution: Per-team, per-feature cost tracking and budgeting",
        "Observability: Unified metrics, traces, and quality monitoring across all providers",
    ]
    
    print(f"  Solution: {rfc.proposed_solution}")
    print()
    print("  Key Components:")
    for comp in rfc.key_components:
        print(f"    • {comp}")
    print()
    
    print("─" * 70)
    print("STEP 4: ALTERNATIVES CONSIDERED (Minimum 3!)")
    print("─" * 70)
    print()
    
    rfc.alternatives = [
        {
            "name": "Thin Proxy with Manual Failover",
            "description": "Simple reverse proxy that routes to configured provider. Teams manually switch providers during outages.",
            "pros": "Simple to build (2 weeks). No behavior change for teams. Low risk.",
            "cons": "Doesn't solve cost optimization. Manual failover means 15+ min downtime. No intelligent routing.",
            "why_not": "Solves only 1 of 3 problems (API abstraction) and doesn't address the most expensive one (cost optimization).",
        },
        {
            "name": "Client-Side SDK with Configuration",
            "description": "Distribute an SDK that teams import. Routing logic lives client-side, configured via remote config.",
            "pros": "No new infrastructure to operate. Teams retain full control. Can be adopted incrementally.",
            "cons": "Routing logic duplicated across 12 services. Can't do org-wide optimization. SDK updates require all teams to redeploy.",
            "why_not": "Org-wide cost optimization requires centralized routing decisions that client-side can't make (e.g., shifting load based on rate limits across all teams).",
        },
        {
            "name": "Adopt Third-Party Gateway (e.g., Portkey, LiteLLM hosted)",
            "description": "Use an existing managed gateway service instead of building our own.",
            "pros": "Immediate availability. No engineering investment. Maintained by vendor.",
            "cons": "Data passes through third party (compliance concern). Limited customization for our routing needs. Vendor lock-in. $8K/month at our scale.",
            "why_not": "Our compliance team requires that inference data doesn't leave our VPC. Also, our routing requirements (intent-based with team-specific budgets) aren't supported by any current vendor.",
        },
        {
            "name": "Do Nothing",
            "description": "Accept current state. Handle outages reactively. Don't optimize costs.",
            "pros": "Zero investment. No migration risk. Teams continue as-is.",
            "cons": "~$200K/quarter in outage costs. Costs grow 40% QoQ unchecked. Weak negotiating position with providers.",
            "why_not": "Projected cost in 12 months: $4.2M/month for inference alone. Doing nothing costs more than doing something.",
        },
    ]
    
    for alt in rfc.alternatives:
        print(f"  Alternative: {alt['name']}")
        print(f"    Description: {alt['description']}")
        print(f"    Pros: {alt['pros']}")
        print(f"    Cons: {alt['cons']}")
        print(f"    Why Not: {alt['why_not']}")
        print()
    
    print("  💡 TEACHING POINT: Notice each alternative is STEEL-MANNED.")
    print("     The pros are genuine. A reasonable person could choose any of these.")
    print("     The 'Why Not' explains the DECISIVE factor, not 'it's obviously worse.'")
    print("     Always include 'Do Nothing' - it forces you to justify action.")
    print()
    
    print("─" * 70)
    print("STEP 5: AI-SPECIFIC CONCERNS")
    print("─" * 70)
    print()
    
    rfc.ai_concerns = {
        "non_determinism": (
            "The gateway introduces a new source of non-determinism: model routing. "
            "The same query might go to different models on retry. Mitigation: "
            "Sticky routing for same user/session within 5-minute window. "
            "Document that cross-model consistency is NOT guaranteed."
        ),
        "evaluation": (
            "How do we know routing decisions are good? Implement A/B framework "
            "at gateway level. Measure: task completion rate, user satisfaction, "
            "cost per successful completion. Run shadow traffic to new models for "
            "2 weeks before enabling live routing."
        ),
        "cost_projection": (
            "Gateway infrastructure cost: ~$15K/month (compute + storage for cache). "
            "Expected savings from intelligent routing: $300K-500K/month at steady state. "
            "Break-even: Month 2 after full rollout. Worst case (routing suboptimal): "
            "Still save $100K/month from caching alone."
        ),
        "model_lifecycle": (
            "When providers deprecate models or release new versions: gateway handles "
            "transparently. Teams don't need to update code. Migration testing happens "
            "in gateway (shadow traffic) before switching live traffic."
        ),
    }
    
    for concern, detail in rfc.ai_concerns.items():
        print(f"  {concern.replace('_', ' ').title()}:")
        print(f"    {detail}")
        print()
    
    print("─" * 70)
    print("STEP 6: MIGRATION & RISKS")
    print("─" * 70)
    print()
    
    rfc.migration_phases = [
        "Phase 1 (Week 1-4): Build gateway with OpenAI-only support. Shadow mode - mirror all traffic, compare responses.",
        "Phase 2 (Week 5-8): Migrate 2 volunteer teams. Gateway handles their traffic. Monitor for regressions.",
        "Phase 3 (Week 9-16): Add Anthropic and Google providers. Migrate 5 more teams. Enable basic routing.",
        "Phase 4 (Week 17-24): Remaining teams migrate. Enable intelligent routing. Decommission direct API calls.",
    ]
    
    rfc.risks = [
        {"risk": "Gateway becomes single point of failure", "likelihood": "Medium", "impact": "High",
         "mitigation": "Multi-region deployment. Fallback: teams can bypass gateway temporarily via feature flag."},
        {"risk": "Routing decisions degrade quality", "likelihood": "Medium", "impact": "Medium",
         "mitigation": "Conservative routing initially (prefer current model). A/B test all routing changes. Auto-rollback on quality regression."},
        {"risk": "Migration takes longer than planned", "likelihood": "High", "impact": "Low",
         "mitigation": "Old and new paths coexist. No hard deadline. Teams migrate when ready."},
        {"risk": "Cache serves stale/wrong responses", "likelihood": "Low", "impact": "High",
         "mitigation": "Cache only for exact semantic matches (0.99 threshold). TTL of 5 minutes. Teams can disable caching per-request."},
    ]
    
    rfc.open_questions = [
        "[BLOCKING] How do we handle streaming responses through the cache layer?",
        "[BLOCKING] What's the latency budget for the gateway itself? (Proposal: <50ms p99 overhead)",
        "[NON-BLOCKING] Should we build rate limiting into the gateway or keep it separate?",
        "[NON-BLOCKING] How do we handle fine-tuned models that only exist on one provider?",
    ]
    
    rfc.success_metrics = [
        "Provider outage impact: 0 product-visible outages from provider failures (currently: 3/quarter)",
        "Cost efficiency: 20% reduction in cost-per-query within 6 months of full rollout",
        "Migration velocity: All 12 teams migrated within 6 months",
        "Latency overhead: <50ms p99 added latency from gateway",
        "Cache hit rate: >30% within 3 months (saves ~$300K/month)",
    ]
    
    for phase in rfc.migration_phases:
        print(f"    • {phase}")
    print()
    
    return rfc


def generate_rfc_document(rfc: RFCInput) -> str:
    """
    Generates a properly formatted RFC document from the collected input.
    
    TEACHING POINT: The output format matters. A well-structured document
    is easier to review, easier to reference later, and demonstrates that
    you've thought carefully about the proposal.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    deadline = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    
    doc = f"""# RFC: {rfc.title}

**Authors:** {', '.join(rfc.authors)}
**Status:** Draft
**Created:** {today}
**Last Updated:** {today}
**Reviewers:** {', '.join(rfc.reviewers)}
**Decision Deadline:** {deadline}

---

## Summary

{rfc.proposed_solution}

## Motivation

### What's Broken

{rfc.problem_statement}

### Current Metrics

| Metric | Value |
|--------|-------|
"""
    for k, v in rfc.current_metrics.items():
        doc += f"| {k} | {v} |\n"
    
    doc += f"""
### Why Now

{rfc.why_now}

## Detailed Design

### Architecture Overview

{rfc.proposed_solution}

### Key Components

"""
    for i, comp in enumerate(rfc.key_components, 1):
        doc += f"{i}. **{comp.split(':')[0]}**: {comp.split(':')[1].strip()}\n"
    
    doc += """
### AI-Specific Concerns

"""
    for concern, detail in rfc.ai_concerns.items():
        doc += f"#### {concern.replace('_', ' ').title()}\n\n{detail}\n\n"
    
    doc += "## Alternatives Considered\n\n"
    for i, alt in enumerate(rfc.alternatives, 1):
        doc += f"""### Alternative {i}: {alt['name']}

**Description:** {alt['description']}

**Pros:** {alt['pros']}

**Cons:** {alt['cons']}

**Why Not:** {alt['why_not']}

"""
    
    doc += "## Migration Plan\n\n"
    for phase in rfc.migration_phases:
        doc += f"- {phase}\n"
    
    doc += "\n## Risks and Mitigations\n\n"
    doc += "| Risk | Likelihood | Impact | Mitigation |\n"
    doc += "|------|-----------|--------|------------|\n"
    for risk in rfc.risks:
        doc += f"| {risk['risk']} | {risk['likelihood']} | {risk['impact']} | {risk['mitigation']} |\n"
    
    doc += "\n## Open Questions\n\n"
    for q in rfc.open_questions:
        doc += f"- {q}\n"
    
    doc += "\n## Success Metrics\n\n"
    for m in rfc.success_metrics:
        doc += f"- {m}\n"
    
    return doc


def analyze_rfc_quality(rfc: RFCInput) -> None:
    """
    Analyzes the generated RFC for common quality issues.
    
    TEACHING POINT: A good RFC tool doesn't just format - it catches
    common mistakes that would weaken your proposal.
    """
    print("\n")
    print("=" * 70)
    print("  RFC QUALITY ANALYSIS")
    print("=" * 70)
    print()
    
    issues = []
    strengths = []
    
    # Check alternatives
    if len(rfc.alternatives) < 3:
        issues.append("CRITICAL: Fewer than 3 alternatives. Reviewers will question rigor.")
    else:
        strengths.append(f"Good: {len(rfc.alternatives)} alternatives considered (including Do Nothing)")
    
    # Check for Do Nothing
    has_do_nothing = any("nothing" in alt["name"].lower() for alt in rfc.alternatives)
    if has_do_nothing:
        strengths.append("Good: 'Do Nothing' alternative included (forces justification)")
    else:
        issues.append("WARNING: No 'Do Nothing' alternative. Always include this.")
    
    # Check metrics
    if len(rfc.current_metrics) < 3:
        issues.append("WARNING: Few metrics in motivation. Add more quantitative evidence.")
    else:
        strengths.append(f"Good: {len(rfc.current_metrics)} metrics quantifying the problem")
    
    # Check AI concerns
    required_ai_sections = ["non_determinism", "evaluation", "cost_projection"]
    for section in required_ai_sections:
        if section in rfc.ai_concerns:
            strengths.append(f"Good: AI concern addressed - {section}")
        else:
            issues.append(f"CRITICAL: Missing AI-specific section: {section}")
    
    # Check migration
    if len(rfc.migration_phases) < 2:
        issues.append("WARNING: Migration plan too vague. Need phased approach.")
    else:
        strengths.append(f"Good: {len(rfc.migration_phases)}-phase migration plan")
    
    # Check open questions
    blocking = [q for q in rfc.open_questions if "BLOCKING" in q]
    if blocking:
        strengths.append(f"Good: {len(blocking)} blocking questions identified (honest about unknowns)")
    
    # Check risks
    if len(rfc.risks) < 3:
        issues.append("WARNING: Too few risks identified. Real proposals have many risks.")
    else:
        strengths.append(f"Good: {len(rfc.risks)} risks with mitigations")
    
    print("  STRENGTHS:")
    for s in strengths:
        print(f"    ✓ {s}")
    
    print()
    print("  ISSUES:")
    if issues:
        for i in issues:
            print(f"    ✗ {i}")
    else:
        print("    None found - RFC is well-structured!")
    
    print()
    print("  OVERALL ASSESSMENT:")
    if not issues:
        print("    This RFC is ready for pre-socialization with key stakeholders.")
    elif any("CRITICAL" in i for i in issues):
        print("    Address critical issues before sharing with reviewers.")
    else:
        print("    Minor improvements recommended but RFC is reviewable.")


def print_rfc_writing_tips():
    """Print key tips for RFC writing."""
    print()
    print("=" * 70)
    print("  KEY LESSONS FOR RFC WRITING")
    print("=" * 70)
    print()
    
    tips = [
        ("Start with WHY, not WHAT",
         "Reviewers need to agree the problem exists before they'll consider your solution."),
        ("Steel-man your alternatives",
         "If a reviewer thinks an alternative was unfairly dismissed, they'll distrust your judgment."),
        ("Quantify everything",
         "'It's slow' vs 'p99 latency is 8.1s against a 3s SLA' - only one of these is actionable."),
        ("Include AI-specific sections",
         "Non-determinism, evaluation, and cost are unique to AI systems and often overlooked."),
        ("Be honest about unknowns",
         "Open questions show intellectual honesty. Pretending you know everything loses trust."),
        ("Set a decision deadline",
         "Without one, RFCs languish in review forever. 2 weeks is usually right."),
        ("Pre-socialize before formal review",
         "The review meeting should be ratification, not the first time people see your proposal."),
    ]
    
    for i, (title, detail) in enumerate(tips, 1):
        print(f"  {i}. {title}")
        print(f"     {detail}")
        print()


def main():
    """Main execution flow."""
    # Step 1: Collect input (simulated)
    rfc = simulate_rfc_input()
    
    # Step 2: Generate the document
    print("\n")
    print("=" * 70)
    print("  GENERATED RFC DOCUMENT")
    print("=" * 70)
    print()
    
    document = generate_rfc_document(rfc)
    
    # Print first ~50 lines to show format without overwhelming output
    lines = document.split('\n')
    for line in lines[:60]:
        print(f"  {line}")
    print(f"\n  ... [{len(lines) - 60} more lines in full document] ...")
    
    # Step 3: Quality analysis
    analyze_rfc_quality(rfc)
    
    # Step 4: Teaching summary
    print_rfc_writing_tips()
    
    print("=" * 70)
    print("  RFC generation complete!")
    print(f"  Full document: {len(lines)} lines, {len(document)} characters")
    print("  In production, this would be saved as a markdown file for review.")
    print("=" * 70)


if __name__ == "__main__":
    main()
