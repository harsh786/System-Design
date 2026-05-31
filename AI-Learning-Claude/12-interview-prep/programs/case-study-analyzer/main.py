#!/usr/bin/env python3
"""
Case Study Interview Simulator for AI Architects
Presents complex scenarios with multiple issues and walks through
structured analysis at different seniority levels.
"""

import random
import time
import textwrap

# ============================================================================
# CASE STUDIES
# ============================================================================

CASE_STUDIES = [
    {
        "title": "The Hallucinating Medical Chatbot Crisis",
        "scenario": textwrap.dedent("""
            Your company's AI health chatbot has:
            - 40% user satisfaction (down from 72% at launch 6 months ago)
            - Costs $500K/month in API calls (3x over budget)
            - Was just featured in a news article: "AI Chatbot Tells User to
              Mix Bleach and Ammonia for Cleaning" (hallucinated dangerous advice)
            - CEO is in damage control mode, board meeting in 2 weeks
            - The original architect left 3 months ago, documentation is sparse
            - Team of 4 engineers maintaining it, none were on the original build
        """),
        "immediate_actions": {
            "title": "IMMEDIATE ACTIONS (Today/This Week)",
            "staff_response": [
                "Kill switch: Disable medical/health advice category immediately",
                "Add disclaimer banner to all responses: 'AI-generated, not medical advice'",
                "Implement output filter: block responses containing dangerous keywords/patterns",
                "Draft public response (work with PR team) acknowledging the issue",
                "Set up war room: daily standup on this crisis until resolved",
                "Audit last 7 days of logs for similar dangerous outputs",
            ],
            "senior_response": [
                "Fix the prompt to say 'don't give dangerous advice'",
                "Add a content filter",
                "Tell PR to handle it",
            ],
            "difference": "Staff thinks about blast radius and stakeholder management. "
                         "Senior thinks about the technical fix only.",
        },
        "root_cause": {
            "title": "ROOT CAUSE ANALYSIS",
            "analysis": [
                "1. No guardrails architecture: Single LLM call with no output validation",
                "2. No domain-specific safety layer for medical/health content",
                "3. Knowledge drift: Training data and retrieval corpus haven't been updated",
                "4. No monitoring: Quality degradation went undetected for months",
                "5. Bus factor: Original architect left with all context",
                "6. Cost spiral: No budget alerts, no per-feature cost tracking",
            ],
            "systemic_issues": [
                "No evaluation framework (how did satisfaction drop 32% without alerts?)",
                "No safety classification of query types (medical vs. general)",
                "No operational runbook for AI failures",
                "No content review process for high-risk domains",
            ],
        },
        "short_term": {
            "title": "SHORT-TERM FIXES (1-2 Weeks)",
            "actions": [
                "Deploy topic classifier: Route medical queries to restricted handler",
                "Add output safety validator: LLM-as-judge checking for harmful content",
                "Implement confidence scoring: Low-confidence -> 'I cannot help with this'",
                "Set up basic monitoring: Response quality sampling, daily reports",
                "Create incident playbook for future AI safety issues",
                "Implement cost alerts with automatic throttling at budget thresholds",
            ],
        },
        "medium_term": {
            "title": "MEDIUM-TERM ARCHITECTURE CHANGES (1-3 Months)",
            "actions": [
                "Redesign as multi-layer system: Intent -> Safety Check -> Generation -> Validation",
                "Build domain-specific guardrails (medical, financial, legal = high-risk)",
                "Implement RAG with curated, reviewed health content (not raw LLM generation)",
                "Create evaluation pipeline: automated + human review on production samples",
                "Migrate to cost-efficient architecture: caching, model tiering, query routing",
                "Document architecture decisions and create operational runbook",
                "Hire/assign AI safety engineer role",
            ],
        },
        "long_term": {
            "title": "LONG-TERM STRATEGY (6-12 Months)",
            "actions": [
                "Build AI governance framework: risk classification, review processes, audit trails",
                "Implement continuous evaluation: detect quality degradation before users do",
                "Create responsible AI review board for high-risk feature launches",
                "Develop cost model: unit economics per feature, ROI tracking",
                "Build institutional knowledge: architecture docs, decision records, runbooks",
                "Establish AI safety testing as part of CI/CD (red-teaming, adversarial tests)",
            ],
        },
    },
    {
        "title": "The Scaling Wall: RAG System at Breaking Point",
        "scenario": textwrap.dedent("""
            Your enterprise RAG system for internal knowledge management:
            - Serves 10,000 employees, growing to 50,000 after acquisition
            - Response latency has crept from 2s to 12s over 6 months
            - Relevance scores dropping (users report 'it never finds what I need')
            - Vector database is at 95% capacity (200M vectors)
            - Monthly cost has grown from $50K to $200K (linear with usage)
            - New requirement: must support 5 acquired companies' document formats
            - Security audit found: users can sometimes see other departments' confidential docs
            - Team is 3 engineers, burned out from firefighting
        """),
        "immediate_actions": {
            "title": "IMMEDIATE ACTIONS (Today/This Week)",
            "staff_response": [
                "Fix the security issue FIRST: Add strict tenant/department filtering to ALL queries",
                "Audit access logs: identify scope of unauthorized document access",
                "Notify security team and legal of the data access incident",
                "Add query timeout + graceful degradation for latency (fail fast at 5s)",
                "Communicate to users: known performance issues, being addressed",
                "Stop the bleeding on cost: identify top-cost queries, add basic caching",
            ],
            "senior_response": [
                "Add more vector DB capacity",
                "Optimize the slow queries",
                "Fix the permission bug",
            ],
            "difference": "Staff recognizes the security issue as highest priority (legal/compliance risk), "
                         "communicates with stakeholders, and triages systematically. Senior jumps to "
                         "technical fixes without assessing risk priority.",
        },
        "root_cause": {
            "title": "ROOT CAUSE ANALYSIS",
            "analysis": [
                "1. No access control in retrieval layer (security-by-obscurity failed)",
                "2. Flat vector index with no partitioning strategy (doesn't scale)",
                "3. Embedding model not updated as corpus grew (relevance degradation)",
                "4. No query optimization: every query searches entire index",
                "5. Monolithic architecture: can't scale components independently",
                "6. No capacity planning: growth surprised the team",
            ],
            "systemic_issues": [
                "No architecture review for scale milestones",
                "Team too small for the system's complexity",
                "No SLOs defined (so degradation was 'acceptable' until crisis)",
                "Security wasn't designed in from the start",
            ],
        },
        "short_term": {
            "title": "SHORT-TERM FIXES (1-2 Weeks)",
            "actions": [
                "Implement pre-retrieval access control filter (reduce search space + fix security)",
                "Add semantic cache for repeated queries (20-30% of queries are similar)",
                "Partition hot vs cold data: recent 6 months in primary index, rest in archive",
                "Define SLOs: latency P95 < 3s, relevance score > 0.7",
                "Add monitoring dashboards: latency percentiles, cache hit rate, cost per query",
            ],
        },
        "medium_term": {
            "title": "MEDIUM-TERM ARCHITECTURE CHANGES (1-3 Months)",
            "actions": [
                "Re-architect to namespace-partitioned vector indices (per-department + shared)",
                "Implement hybrid retrieval: sparse (BM25) + dense (vector) for better relevance",
                "Add a re-ranking layer (cross-encoder) for top-K results quality",
                "Design multi-tenant architecture for 5 acquired companies",
                "Build document ingestion pipeline that handles multiple formats",
                "Implement tiered storage: hot/warm/cold based on access patterns",
                "Make the case for team expansion (target: 6-8 engineers for this system)",
            ],
        },
        "long_term": {
            "title": "LONG-TERM STRATEGY (6-12 Months)",
            "actions": [
                "Platform architecture: self-service RAG-as-a-service for business units",
                "Federated search: each acquired company maintains their own index, unified query layer",
                "ML-driven query routing: classify query intent and route to optimal retrieval strategy",
                "Continuous relevance evaluation with user feedback loops",
                "Cost optimization through intelligent tiering and lifecycle management",
                "Build internal expertise: training programs, hiring plan, vendor relationships",
            ],
        },
    },
    {
        "title": "The Agent Gone Rogue: Autonomous AI Causing Damage",
        "scenario": textwrap.dedent("""
            Your company deployed an AI agent for automated customer refunds:
            - Agent was supposed to handle refunds < $50 autonomously
            - Over the weekend, it processed $2.3M in refunds (10x normal)
            - Root cause: agent misinterpreted a promotional email as refund policy
            - 40% of refunds were to customers who didn't request them
            - Some customers already spent the unexpected refund
            - Finance team discovered it Monday morning
            - System has been running for 3 months without incident until now
            - No human review was in the loop for 'standard' refunds
            - Logging exists but no alerting on aggregate behavior
        """),
        "immediate_actions": {
            "title": "IMMEDIATE ACTIONS (Today/This Week)",
            "staff_response": [
                "HALT all autonomous refund processing immediately",
                "Switch to human-in-the-loop for ALL refunds until further notice",
                "Quantify the damage: exactly how many erroneous refunds, total amount",
                "Coordinate with Finance on recovery strategy (can we reverse charges?)",
                "Coordinate with Legal on customer communication (can't just claw back)",
                "Preserve all logs and agent decision traces for forensic analysis",
                "Brief leadership: what happened, current exposure, recovery plan timeline",
            ],
            "senior_response": [
                "Fix the bug that let it read the promo email as policy",
                "Add a daily spending cap",
                "Turn it back on after fixing",
            ],
            "difference": "Staff sees this as a business crisis requiring cross-functional response. "
                         "Senior sees it as a bug to fix. The $2.3M and customer impact require "
                         "Finance, Legal, and Leadership involvement.",
        },
        "root_cause": {
            "title": "ROOT CAUSE ANALYSIS",
            "analysis": [
                "1. Agent had unrestricted access to refund API (no aggregate limits)",
                "2. Agent's context included ALL company emails (not scoped to relevant docs)",
                "3. No anomaly detection on agent behavior (volume, velocity, patterns)",
                "4. Policy was defined in natural language, not as code constraints",
                "5. No human oversight for aggregate impact (individual refunds < $50, but total uncapped)",
                "6. Weekend operation with no on-call monitoring",
            ],
            "systemic_issues": [
                "Trust model was binary: agent either has access or doesn't",
                "No separation between 'understanding policy' and 'executing actions'",
                "Monitoring designed for individual actions, not emergent behavior",
                "No 'blast radius' containment for autonomous systems",
                "Success for 3 months created false confidence (survivorship bias)",
            ],
        },
        "short_term": {
            "title": "SHORT-TERM FIXES (1-2 Weeks)",
            "actions": [
                "Implement hard spending caps: per-hour, per-day, per-week aggregate limits",
                "Add anomaly detection: alert if refund volume/amount deviates >2x from baseline",
                "Scope agent's knowledge: curated policy documents only (not all company emails)",
                "Add policy-as-code layer: business rules that cannot be overridden by agent reasoning",
                "Implement graduated re-enablement: start with human-confirms-all, then relax",
                "Create on-call rotation with weekend coverage for autonomous systems",
            ],
        },
        "medium_term": {
            "title": "MEDIUM-TERM ARCHITECTURE CHANGES (1-3 Months)",
            "actions": [
                "Redesign agent architecture: separate reasoning from action execution",
                "Implement 'proposal and approval' pattern: agent proposes, system validates against rules",
                "Build behavioral monitoring: track agent decisions over time, detect drift",
                "Create action simulation mode: test agent decisions against historical data before deploy",
                "Design graduated autonomy framework: more trust = more autonomy, earned over time",
                "Implement financial controls: real-time budget tracking integrated with agent",
            ],
        },
        "long_term": {
            "title": "LONG-TERM STRATEGY (6-12 Months)",
            "actions": [
                "Build autonomous AI governance framework for the company",
                "Define autonomy levels (1-5) with clear criteria for each level",
                "Implement continuous monitoring and trust scoring for all AI agents",
                "Create AI incident response playbook (like security incident response)",
                "Establish AI risk committee for reviewing new autonomous deployments",
                "Build internal tooling for safe agent development and testing",
            ],
        },
    },
]

# ============================================================================
# ANALYSIS FRAMEWORK
# ============================================================================

FRAMEWORK = {
    "Senior vs Staff Thinking": {
        "Senior (Fix the Bug)": [
            "Identifies the immediate technical cause",
            "Proposes a code fix",
            "Tests and deploys",
            "Moves on to next task",
        ],
        "Staff (Fix the System)": [
            "Assesses blast radius and business impact",
            "Coordinates cross-functional response",
            "Fixes immediate issue AND identifies systemic gaps",
            "Designs architectural changes to prevent recurrence",
            "Updates processes, monitoring, and documentation",
            "Presents to leadership with timeline and resource needs",
        ],
    },
    "Structured Response Framework": [
        "1. ASSESS: What's the blast radius? Who's impacted? What's the urgency?",
        "2. TRIAGE: What's the highest priority? (Usually: safety > security > revenue > UX)",
        "3. CONTAIN: Stop the bleeding before fixing the root cause",
        "4. COMMUNICATE: Keep stakeholders informed (engineering, product, leadership, customers)",
        "5. FIX: Short-term mitigation, then medium-term architecture fix",
        "6. PREVENT: Long-term systemic changes to prevent recurrence",
        "7. LEARN: Post-mortem, update runbooks, share learnings",
    ],
}

# ============================================================================
# DISPLAY HELPERS
# ============================================================================

def print_header(text, char="="):
    width = 78
    print(f"\n{char * width}")
    print(f" {text}")
    print(f"{char * width}")


def print_section(title, items, indent=4):
    print(f"\n  {title}:")
    for item in items:
        wrapped = textwrap.wrap(item, width=74 - indent)
        print(f"{' ' * indent}- {wrapped[0]}")
        for line in wrapped[1:]:
            print(f"{' ' * indent}  {line}")


def print_comparison(staff, senior, difference):
    print(f"\n  {'STAFF RESPONSE':^37}{'SENIOR RESPONSE':^37}")
    print(f"  {'─' * 37}{'─' * 37}")
    max_lines = max(len(staff), len(senior))
    for i in range(max_lines):
        s = textwrap.shorten(staff[i], 35) if i < len(staff) else ""
        r = textwrap.shorten(senior[i], 35) if i < len(senior) else ""
        print(f"  {s:<37}{r:<37}")
    print(f"\n  KEY DIFFERENCE: {difference}")


# ============================================================================
# MAIN
# ============================================================================

def run_case_study():
    print_header("CASE STUDY INTERVIEW SIMULATOR")
    print("""
    This simulator presents a complex AI system failure scenario and walks
    through how a Staff+ architect would analyze and respond.

    Key skill tested: Can you think SYSTEMICALLY, not just technically?
    """)

    # Select case study
    case = random.choice(CASE_STUDIES)

    print_header(f"CASE: {case['title']}", "~")
    print(case["scenario"])
    time.sleep(1)

    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ Before reading the analysis below, think:                       │")
    print("  │ 1. What would you do FIRST?                                     │")
    print("  │ 2. Who needs to be involved?                                    │")
    print("  │ 3. What's the 1-week vs 1-month vs 6-month plan?               │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    time.sleep(1)

    # Immediate actions with comparison
    print_header(case["immediate_actions"]["title"], "-")
    print_comparison(
        case["immediate_actions"]["staff_response"],
        case["immediate_actions"]["senior_response"],
        case["immediate_actions"]["difference"],
    )
    time.sleep(0.5)

    # Root cause
    print_header(case["root_cause"]["title"], "-")
    print_section("Direct Causes", case["root_cause"]["analysis"])
    print_section("Systemic Issues (what Staff identifies that Senior misses)",
                  case["root_cause"]["systemic_issues"])
    time.sleep(0.5)

    # Timeline
    for phase in ["short_term", "medium_term", "long_term"]:
        data = case[phase]
        print_header(data["title"], "-")
        print_section("Actions", data["actions"])
        time.sleep(0.5)

    # Framework
    print_header("RESPONSE FRAMEWORK (Use in Any Case Study)", "=")

    for title, content in FRAMEWORK.items():
        if isinstance(content, dict):
            print(f"\n  {title}:")
            for level, points in content.items():
                print(f"\n    {level}:")
                for p in points:
                    print(f"      - {p}")
        else:
            print(f"\n  {title}:")
            for item in content:
                print(f"    {item}")

    # Scoring
    print_header("SELF-ASSESSMENT CHECKLIST")
    checklist = [
        "Did you address the highest-priority issue FIRST? (safety/security/legal)",
        "Did you think about stakeholders beyond engineering?",
        "Did you separate immediate triage from root cause fixing?",
        "Did you identify systemic issues (not just the proximate bug)?",
        "Did you propose monitoring/alerting to detect this class of issue?",
        "Did you think about the team/org changes needed (not just technical)?",
        "Did you structure your response with a clear timeline?",
        "Did you consider what could go wrong with your proposed fixes?",
    ]
    for i, item in enumerate(checklist, 1):
        print(f"  [{' '}] {i}. {item}")

    print(f"\n  SCORING:")
    print(f"    6-8 checked: Staff-level response")
    print(f"    4-5 checked: Strong Senior response")
    print(f"    1-3 checked: Need more practice on systemic thinking")

    print(f"\n  Run again for a different case study ({len(CASE_STUDIES)} total).\n")


if __name__ == "__main__":
    run_case_study()
