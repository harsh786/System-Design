"""
AI Risk Register Tool
Interactive tool for managing AI system risks with scoring, controls, and reporting.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


LIKELIHOOD_LABELS = ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]
IMPACT_LABELS = ["Negligible", "Minor", "Moderate", "Major", "Catastrophic"]


def risk_level(score: int) -> str:
    if score >= 15:
        return "CRITICAL"
    elif score >= 10:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    return "LOW"


def risk_color(level: str) -> str:
    colors = {"CRITICAL": "\033[91m", "HIGH": "\033[93m", "MEDIUM": "\033[33m", "LOW": "\033[92m"}
    return colors.get(level, "") + level + "\033[0m"


@dataclass
class Risk:
    risk_id: str
    title: str
    category: str
    ai_system: str
    description: str
    likelihood: int  # 1-5
    impact: int  # 1-5
    controls: list = field(default_factory=list)
    owner: str = "Unassigned"
    status: str = "Active"
    treatment: str = "Mitigate"
    review_date: Optional[str] = None

    @property
    def score(self) -> int:
        return self.likelihood * self.impact

    @property
    def level(self) -> str:
        return risk_level(self.score)


# Pre-populated risks
DEFAULT_RISKS = [
    Risk("RISK-001", "Hallucination in customer chatbot", "output_quality", "CustomerBot",
         "Model generates false information presented as fact", 4, 3,
         ["RAG grounding", "Confidence threshold", "Disclaimer"], "AI Safety Team"),
    Risk("RISK-002", "Bias in hiring recommendations", "fairness", "TalentMatch AI",
         "Model shows demographic bias in candidate ranking", 3, 4,
         ["Demographic parity testing", "Blind processing", "Human review"], "HR Tech Team"),
    Risk("RISK-003", "Prompt injection attack", "security", "All LLM features",
         "Attacker manipulates model via crafted input", 5, 2,
         ["Input sanitization", "Output filtering"], "Security Team"),
    Risk("RISK-004", "PII leakage in outputs", "privacy", "SupportBot",
         "Model reveals personal information from training/context", 3, 4,
         ["PII detection filter", "Data masking"], "Privacy Team"),
    Risk("RISK-005", "Cost overrun from agent loops", "financial", "AutoAgent",
         "Recursive agent behavior causes unexpected API costs", 3, 3,
         ["Budget caps", "Iteration limits", "Cost alerts"], "Platform Team"),
    Risk("RISK-006", "Model drift degradation", "reliability", "RecommendationEngine",
         "Model quality degrades as data distribution shifts", 4, 2,
         ["Weekly eval pipeline", "Drift monitoring"], "ML Ops Team"),
    Risk("RISK-007", "Vendor API outage", "reliability", "All AI features",
         "Third-party model API becomes unavailable", 3, 3,
         ["Fallback model", "Cached responses", "Circuit breaker"], "Platform Team"),
    Risk("RISK-008", "Copyright infringement in outputs", "compliance", "ContentGen",
         "Model reproduces copyrighted content verbatim", 2, 4,
         ["Plagiarism detection", "Attribution system"], "Legal Team"),
    Risk("RISK-009", "Data residency violation", "compliance", "EU CustomerBot",
         "EU customer data processed outside EU region", 2, 5,
         ["Region-locked endpoints", "Data residency checks"], "Compliance Team"),
    Risk("RISK-010", "Reputational damage from AI failure", "reputational", "Public-facing AI",
         "Viral incident of AI producing offensive/incorrect content", 2, 4,
         ["Content safety filter", "Human escalation", "Kill switch"], "Comms Team"),
]


class RiskRegister:
    def __init__(self):
        self.risks: list[Risk] = list(DEFAULT_RISKS)
        self.next_id = 11

    def add_risk(self, title: str, category: str, ai_system: str, description: str,
                 likelihood: int, impact: int, owner: str = "Unassigned") -> Risk:
        risk = Risk(
            risk_id=f"RISK-{self.next_id:03d}",
            title=title, category=category, ai_system=ai_system,
            description=description, likelihood=likelihood, impact=impact,
            owner=owner
        )
        self.risks.append(risk)
        self.next_id += 1
        return risk

    def get_risk(self, risk_id: str) -> Optional[Risk]:
        for r in self.risks:
            if r.risk_id == risk_id:
                return r
        return None

    def sorted_risks(self) -> list[Risk]:
        return sorted(self.risks, key=lambda r: r.score, reverse=True)

    def print_matrix(self):
        """Print text-based risk matrix."""
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print("║                    RISK SCORING MATRIX                       ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print("║ Impact →     Negl(1) Minor(2) Mod(3) Major(4) Cata(5)       ║")
        print("║ Likelihood ↓                                                 ║")
        print("╠══════════════════════════════════════════════════════════════╣")

        # Build matrix with risk counts
        matrix = {}
        for r in self.risks:
            key = (r.likelihood, r.impact)
            matrix[key] = matrix.get(key, 0) + 1

        for lik in range(5, 0, -1):
            label = LIKELIHOOD_LABELS[lik - 1][:8].ljust(8)
            row = f"║ {label}({lik})  "
            for imp in range(1, 6):
                count = matrix.get((lik, imp), 0)
                score = lik * imp
                level = risk_level(score)
                if count > 0:
                    cell = f"[{count}]"
                else:
                    cell = " . "
                row += f"  {cell}  "
            row += "║"
            print(row)

        print("╚══════════════════════════════════════════════════════════════╝")
        print("  [ ] = number of risks at that position")
        print()

    def print_report(self):
        """Generate full risk report."""
        print("\n" + "=" * 70)
        print("              AI RISK REGISTER REPORT")
        print(f"              Generated: {date.today()}")
        print("=" * 70)

        # Summary
        levels = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in self.risks:
            levels[r.level] += 1

        print(f"\n  Total Risks: {len(self.risks)}")
        print(f"  CRITICAL: {levels['CRITICAL']}  |  HIGH: {levels['HIGH']}  |  MEDIUM: {levels['MEDIUM']}  |  LOW: {levels['LOW']}")
        print("-" * 70)

        # Sorted risks
        for r in self.sorted_risks():
            print(f"\n  {r.risk_id} [{risk_color(r.level)}] Score: {r.score}")
            print(f"  Title: {r.title}")
            print(f"  System: {r.ai_system} | Category: {r.category}")
            print(f"  Likelihood: {LIKELIHOOD_LABELS[r.likelihood-1]} ({r.likelihood}) | Impact: {IMPACT_LABELS[r.impact-1]} ({r.impact})")
            print(f"  Owner: {r.owner} | Treatment: {r.treatment}")
            if r.controls:
                print(f"  Controls: {', '.join(r.controls)}")
            print(f"  Status: {r.status}")

        # Recommendations
        print("\n" + "=" * 70)
        print("  RECOMMENDATIONS")
        print("=" * 70)
        critical = [r for r in self.risks if r.level == "CRITICAL"]
        if critical:
            print("\n  ⚠ CRITICAL risks requiring immediate attention:")
            for r in critical:
                print(f"    - {r.risk_id}: {r.title} (Owner: {r.owner})")

        uncontrolled = [r for r in self.risks if not r.controls and r.level in ("HIGH", "CRITICAL")]
        if uncontrolled:
            print("\n  ⚠ HIGH/CRITICAL risks with no controls:")
            for r in uncontrolled:
                print(f"    - {r.risk_id}: {r.title}")

        print("\n" + "=" * 70)

    def list_risks(self):
        print(f"\n{'ID':<10} {'Score':<7} {'Level':<10} {'Title':<35} {'Owner':<15}")
        print("-" * 80)
        for r in self.sorted_risks():
            print(f"{r.risk_id:<10} {r.score:<7} {risk_color(r.level):<20} {r.title[:35]:<35} {r.owner:<15}")


def interactive_add(register: RiskRegister):
    print("\n--- Add New Risk ---")
    title = input("  Title: ").strip()
    if not title:
        print("  Cancelled.")
        return
    categories = ["output_quality", "security", "privacy", "fairness",
                  "reliability", "compliance", "reputational", "financial"]
    print(f"  Categories: {', '.join(categories)}")
    category = input("  Category: ").strip() or "output_quality"
    ai_system = input("  AI System: ").strip() or "Unspecified"
    description = input("  Description: ").strip() or title
    print(f"  Likelihood (1-5): {', '.join(f'{i+1}={l}' for i, l in enumerate(LIKELIHOOD_LABELS))}")
    likelihood = int(input("  Likelihood [3]: ").strip() or "3")
    print(f"  Impact (1-5): {', '.join(f'{i+1}={l}' for i, l in enumerate(IMPACT_LABELS))}")
    impact = int(input("  Impact [3]: ").strip() or "3")
    owner = input("  Owner [Unassigned]: ").strip() or "Unassigned"

    risk = register.add_risk(title, category, ai_system, description, likelihood, impact, owner)
    print(f"\n  ✓ Added {risk.risk_id}: {risk.title} (Score: {risk.score}, Level: {risk.level})")


def interactive_control(register: RiskRegister):
    risk_id = input("  Risk ID (e.g., RISK-001): ").strip().upper()
    risk = register.get_risk(risk_id)
    if not risk:
        print(f"  Risk {risk_id} not found.")
        return
    print(f"  Current controls for {risk.title}:")
    for c in risk.controls:
        print(f"    - {c}")
    new_control = input("  Add control: ").strip()
    if new_control:
        risk.controls.append(new_control)
        print(f"  ✓ Control added. Total controls: {len(risk.controls)}")


def interactive_score(register: RiskRegister):
    risk_id = input("  Risk ID (e.g., RISK-001): ").strip().upper()
    risk = register.get_risk(risk_id)
    if not risk:
        print(f"  Risk {risk_id} not found.")
        return
    print(f"  Re-scoring: {risk.title}")
    print(f"  Current: Likelihood={risk.likelihood}, Impact={risk.impact}, Score={risk.score}")
    likelihood = input(f"  New Likelihood (1-5) [{risk.likelihood}]: ").strip()
    impact = input(f"  New Impact (1-5) [{risk.impact}]: ").strip()
    if likelihood:
        risk.likelihood = int(likelihood)
    if impact:
        risk.impact = int(impact)
    print(f"  ✓ Updated: Score={risk.score}, Level={risk.level}")


def main():
    register = RiskRegister()

    print("╔══════════════════════════════════════════════════╗")
    print("║          AI RISK REGISTER TOOL                   ║")
    print("║  Manage and track risks for AI systems           ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Commands: list, add, score, control,            ║")
    print("║            matrix, report, help, quit            ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"\n  Loaded {len(register.risks)} pre-populated risks.\n")

    while True:
        cmd = input("\nrisk-register> ").strip().lower()

        if cmd == "quit" or cmd == "exit":
            print("  Goodbye!")
            break
        elif cmd == "list":
            register.list_risks()
        elif cmd == "add":
            interactive_add(register)
        elif cmd.startswith("score"):
            interactive_score(register)
        elif cmd.startswith("control"):
            interactive_control(register)
        elif cmd == "matrix":
            register.print_matrix()
        elif cmd == "report":
            register.print_report()
        elif cmd == "help":
            print("  list    — Show all risks sorted by score")
            print("  add     — Add a new risk interactively")
            print("  score   — Re-score a risk")
            print("  control — Add controls to a risk")
            print("  matrix  — Show risk matrix visualization")
            print("  report  — Generate full risk report")
            print("  quit    — Exit")
        else:
            print("  Unknown command. Type 'help' for options.")


if __name__ == "__main__":
    main()
