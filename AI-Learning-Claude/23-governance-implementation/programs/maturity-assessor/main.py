"""
AI Platform Maturity Assessor
Evaluates organizational AI maturity across 4 dimensions with 20 questions.
"""

import sys

QUESTIONS = {
    "Governance": [
        "Do you have a standardized model selection process with documented criteria?",
        "Do you have an AI-specific risk register that's reviewed regularly?",
        "Are AI architecture decisions documented in ADRs?",
        "Do you have defined roles for AI governance (risk owner, ethics, security)?",
        "Does leadership receive regular AI risk and quality reports?",
    ],
    "Evaluation": [
        "Do you have automated evaluation in your CI/CD pipeline?",
        "Do you maintain golden datasets for each AI feature?",
        "Do you run A/B tests for AI feature changes?",
        "Do you have domain-expert evaluation (not just automated metrics)?",
        "Do you track evaluation quality over time (meta-evaluation)?",
    ],
    "Operations": [
        "Do you track cost per request and attribute it to features?",
        "Do you have SLOs for AI quality metrics (not just availability)?",
        "Do you have incident runbooks specific to AI failures?",
        "Do you have automated rollback for AI quality regressions?",
        "Do you have model versioning and reproducible deployments?",
    ],
    "Security": [
        "Do you have guardrails on all production AI outputs?",
        "Do you conduct regular red teaming / adversarial testing?",
        "Do you have data loss prevention (DLP) for AI interactions?",
        "Do you monitor for prompt injection attempts?",
        "Do you have an AI-specific incident response process?",
    ],
}

LEVELS = [
    (0, 15, "L0", "Ad Hoc", "Individual experiments, no standards, no governance"),
    (16, 35, "L1", "Managed", "Basic standards, some shared tools"),
    (36, 55, "L2", "Defined", "Formal processes, documented architecture"),
    (56, 75, "L3", "Measured", "Quantified quality, performance, cost"),
    (76, 90, "L4", "Optimized", "Continuous improvement, automated governance"),
    (91, 100, "L5", "Adaptive", "Self-healing, organization-wide AI governance"),
]

ROADMAP = {
    "L0": {
        "target": "L1",
        "timeline": "2-3 months",
        "actions": [
            "Centralize API key management (single secrets store)",
            "Write an acceptable use policy for AI tools (1 page)",
            "Create shared prompt templates for common patterns",
            "Set up monthly AI spend tracking (even a spreadsheet)",
            "Establish basic security review checklist for new AI features",
        ],
    },
    "L1": {
        "target": "L2",
        "timeline": "3-6 months",
        "actions": [
            "Deploy an AI gateway for centralized traffic management",
            "Establish architecture review board (monthly meetings)",
            "Build evaluation pipeline with golden datasets (50+ examples each)",
            "Implement prompt registry with versioning",
            "Require ADRs for all new AI architecture decisions",
            "Set up production monitoring (error rates, latency, cost)",
        ],
    },
    "L2": {
        "target": "L3",
        "timeline": "6 months",
        "actions": [
            "Define SLOs for every AI feature (quality + latency + cost)",
            "Build real-time quality dashboards accessible to all teams",
            "Implement cost optimization (response caching, model routing)",
            "Create and actively maintain an AI risk register",
            "Automate compliance checks in CI/CD pipeline",
            "Begin regular red teaming exercises (quarterly)",
            "Start A/B testing framework for AI changes",
        ],
    },
    "L3": {
        "target": "L4",
        "timeline": "12 months",
        "actions": [
            "Implement policy-as-code for AI governance",
            "Build self-service AI platform with built-in guardrails",
            "Deploy automatic model routing based on cost/quality optimization",
            "Implement predictive monitoring and auto-remediation",
            "Run continuous evaluation in production (not just CI/CD)",
            "Standardize platform across all teams",
        ],
    },
    "L4": {
        "target": "L5",
        "timeline": "18+ months",
        "actions": [
            "Implement cross-team learning (incidents in one team improve all)",
            "Build self-healing systems (auto-detect and fix quality drops)",
            "Deploy organization-wide AI governance metrics to board",
            "Create marketplace of reusable AI capabilities",
            "Implement meta-evaluation (evaluation that improves itself)",
            "Achieve full organizational adoption of unified AI platform",
        ],
    },
    "L5": {
        "target": "Maintain",
        "timeline": "Ongoing",
        "actions": [
            "Continue innovation and industry leadership",
            "Share learnings externally (conferences, papers)",
            "Mentor other organizations on AI governance",
        ],
    },
}


def get_level(total_score: int) -> tuple:
    for min_s, max_s, code, name, desc in LEVELS:
        if min_s <= total_score <= max_s:
            return code, name, desc
    return "L0", "Ad Hoc", ""


def category_level(score: int) -> str:
    """Get level for a single category (max 25)."""
    if score <= 4:
        return "L0"
    elif score <= 8:
        return "L1"
    elif score <= 13:
        return "L2"
    elif score <= 18:
        return "L3"
    elif score <= 22:
        return "L4"
    return "L5"


def run_assessment(mode: str = "interactive") -> dict:
    """Run the assessment and return scores."""
    scores = {}

    if mode == "quick":
        # Default scores simulating a typical L2 organization
        defaults = {
            "Governance": [3, 2, 3, 2, 2],
            "Evaluation": [3, 3, 1, 2, 1],
            "Operations": [2, 2, 3, 1, 3],
            "Security": [3, 1, 2, 2, 2],
        }
        scores = defaults
        print("\n  Using default scores (typical L2 organization)...\n")
    else:
        print("\n  Score each question 0-5:")
        print("  0=Not at all  1=Initial  2=Partial  3=Mostly  4=Fully  5=Exemplary\n")

        for category, questions in QUESTIONS.items():
            print(f"\n  === {category.upper()} ===")
            scores[category] = []
            for i, question in enumerate(questions, 1):
                print(f"\n  Q{i}: {question}")
                while True:
                    try:
                        val = input("  Score [0-5]: ").strip()
                        val = int(val)
                        if 0 <= val <= 5:
                            scores[category].append(val)
                            break
                        print("  Please enter 0-5.")
                    except (ValueError, EOFError):
                        scores[category].append(3)
                        break

    return scores


def print_results(scores: dict):
    """Print assessment results and recommendations."""
    total = sum(sum(v) for v in scores.values())
    level_code, level_name, level_desc = get_level(total)

    print("\n" + "=" * 60)
    print("         AI PLATFORM MATURITY ASSESSMENT RESULTS")
    print("=" * 60)

    # Overall score
    print(f"\n  Overall Score: {total}/100")
    print(f"  Maturity Level: {level_code} — {level_name}")
    print(f"  Description: {level_desc}")

    # Progress bar
    filled = int(total / 100 * 40)
    bar = "█" * filled + "░" * (40 - filled)
    print(f"\n  [{bar}] {total}%")

    # Category breakdown
    print("\n  ┌─────────────────────────────────────────────┐")
    print("  │           CATEGORY BREAKDOWN                 │")
    print("  ├──────────────┬───────┬───────┬──────────────┤")
    print("  │ Category     │ Score │ Max   │ Level        │")
    print("  ├──────────────┼───────┼───────┼──────────────┤")

    weakest_cat = None
    weakest_score = 26

    for category, cat_scores in scores.items():
        cat_total = sum(cat_scores)
        cat_lvl = category_level(cat_total)
        bar_len = int(cat_total / 25 * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        print(f"  │ {category:<12} │ {cat_total:>5} │   25  │ {cat_lvl:<5} {bar} │")
        if cat_total < weakest_score:
            weakest_score = cat_total
            weakest_cat = category

    print("  └──────────────┴───────┴───────┴──────────────┘")

    if weakest_cat:
        print(f"\n  ⚠ Weakest area: {weakest_cat} ({category_level(weakest_score)})")
        print(f"    Your overall maturity is limited by this dimension.")

    # Roadmap
    roadmap = ROADMAP.get(level_code, ROADMAP["L5"])
    print(f"\n  ┌─────────────────────────────────────────────┐")
    print(f"  │         IMPROVEMENT ROADMAP                   │")
    print(f"  │  Current: {level_code} → Target: {roadmap['target']:<23}│")
    print(f"  │  Timeline: {roadmap['timeline']:<30}│")
    print(f"  ├─────────────────────────────────────────────┤")
    print(f"  │  Recommended Next Steps:                      │")
    print(f"  ├─────────────────────────────────────────────┤")
    for i, action in enumerate(roadmap["actions"], 1):
        # Wrap long lines
        if len(action) > 50:
            print(f"  │  {i}. {action[:50]}")
            print(f"  │     {action[50:]:<40}│")
        else:
            print(f"  │  {i}. {action:<43}│")
    print(f"  └─────────────────────────────────────────────┘")

    # Quick wins
    print("\n  QUICK WINS (address in next 2 weeks):")
    for category, cat_scores in scores.items():
        for i, score in enumerate(cat_scores):
            if score <= 1:
                q = list(QUESTIONS[category])[i]
                print(f"    • [{category}] {q[:60]}")
                break  # One per category

    print("\n" + "=" * 60)


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║       AI PLATFORM MATURITY ASSESSOR              ║")
    print("║  Assess your organization's AI maturity (L0-L5)  ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Modes:                                          ║")
    print("║    1. Interactive (answer 20 questions)           ║")
    print("║    2. Quick demo (pre-filled scores)             ║")
    print("╚══════════════════════════════════════════════════╝")

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        mode = "quick"
    else:
        choice = input("\n  Select mode (1=interactive, 2=quick) [2]: ").strip()
        mode = "interactive" if choice == "1" else "quick"

    scores = run_assessment(mode)
    print_results(scores)


if __name__ == "__main__":
    main()
