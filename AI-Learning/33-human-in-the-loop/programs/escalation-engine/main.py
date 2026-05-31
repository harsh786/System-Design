"""
Escalation Engine Simulator
============================
Simulates a multi-tier escalation system where AI processes queries,
routes to human review based on confidence thresholds, manages queues
with SLA tracking, and demonstrates feedback loops.

Run: python3 main.py
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from typing import Optional
import statistics


class Tier(Enum):
    AUTO = "auto"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Query:
    id: int
    content: str
    category: str
    true_label: str
    ai_confidence: float = 0.0
    ai_prediction: str = ""
    priority: Priority = Priority.MEDIUM
    tier_routed: Tier = Tier.AUTO
    resolution: str = ""
    resolved_by: str = ""
    created_at: float = 0.0
    resolved_at: float = 0.0
    sla_seconds: float = 0.0
    feedback: str = ""


@dataclass
class Reviewer:
    name: str
    tier: Tier
    skills: list
    queue: list = field(default_factory=list)
    items_reviewed: int = 0
    correct_decisions: int = 0
    avg_review_time: float = 0.0


@dataclass
class EscalationMetrics:
    total_processed: int = 0
    auto_approved: int = 0
    l1_reviewed: int = 0
    l2_reviewed: int = 0
    l3_reviewed: int = 0
    sla_breaches: int = 0
    human_agreed_with_ai: int = 0
    human_disagreed_with_ai: int = 0
    total_resolution_time: float = 0.0
    errors_caught_by_humans: int = 0
    feedback_collected: int = 0


class EscalationEngine:
    """Multi-tier escalation system with confidence-based routing."""

    def __init__(self):
        # Thresholds for routing
        self.thresholds = {
            "auto_approve": 0.92,
            "l1_review": 0.70,
            "l2_review": 0.50,
            # Below 0.50 or flagged → L3
        }
        self.sla_by_priority = {
            Priority.CRITICAL: 300,    # 5 minutes
            Priority.HIGH: 1800,       # 30 minutes
            Priority.MEDIUM: 14400,    # 4 hours
            Priority.LOW: 86400,       # 24 hours
        }
        self.metrics = EscalationMetrics()
        self.reviewers = self._create_reviewers()
        self.feedback_store = []
        self.model_accuracy = 0.85  # Simulated initial AI accuracy
        self.simulation_time = 0.0

    def _create_reviewers(self):
        """Create a team of reviewers across tiers."""
        return [
            Reviewer("Alice", Tier.L1, ["general", "spam"], [], 0, 0, 30.0),
            Reviewer("Bob", Tier.L1, ["general", "content"], [], 0, 0, 45.0),
            Reviewer("Carol", Tier.L2, ["medical", "legal", "content"], [], 0, 0, 120.0),
            Reviewer("Dave", Tier.L2, ["financial", "safety"], [], 0, 0, 150.0),
            Reviewer("Eve", Tier.L3, ["policy", "complex", "safety"], [], 0, 0, 300.0),
        ]

    def generate_queries(self, n=100):
        """Generate simulated queries with various categories and difficulties."""
        categories = ["spam", "content", "medical", "financial", "safety", "general"]
        queries = []
        for i in range(n):
            category = random.choice(categories)
            true_label = random.choice(["approve", "reject"])
            # Simulate AI confidence - bimodal distribution
            if random.random() < 0.6:
                confidence = random.uniform(0.85, 0.99)  # High confidence cluster
            elif random.random() < 0.7:
                confidence = random.uniform(0.55, 0.85)  # Medium confidence
            else:
                confidence = random.uniform(0.30, 0.55)  # Low confidence

            # AI prediction: correct based on model accuracy + confidence
            correct_prob = self.model_accuracy * (confidence / 0.9)
            correct_prob = min(correct_prob, 0.99)
            ai_prediction = true_label if random.random() < correct_prob else (
                "reject" if true_label == "approve" else "approve"
            )

            # Priority based on category
            priority_map = {
                "safety": Priority.CRITICAL,
                "medical": Priority.HIGH,
                "financial": Priority.HIGH,
                "content": Priority.MEDIUM,
                "spam": Priority.LOW,
                "general": Priority.MEDIUM,
            }

            queries.append(Query(
                id=i,
                content=f"Query #{i} [{category}]",
                category=category,
                true_label=true_label,
                ai_confidence=confidence,
                ai_prediction=ai_prediction,
                priority=priority_map[category],
                created_at=self.simulation_time,
                sla_seconds=self.sla_by_priority[priority_map[category]],
            ))
        return queries

    def route_query(self, query: Query) -> Tier:
        """Route query to appropriate tier based on confidence and category."""
        # Safety always goes to L3 regardless of confidence
        if query.category == "safety" and query.ai_confidence < 0.98:
            return Tier.L3

        # High confidence → auto-approve
        if query.ai_confidence >= self.thresholds["auto_approve"]:
            return Tier.AUTO

        # Medium confidence → L1
        if query.ai_confidence >= self.thresholds["l1_review"]:
            return Tier.L1

        # Lower confidence → L2
        if query.ai_confidence >= self.thresholds["l2_review"]:
            return Tier.L2

        # Very low confidence → L3
        return Tier.L3

    def assign_to_reviewer(self, query: Query, tier: Tier) -> Optional[Reviewer]:
        """Assign query to best available reviewer in tier."""
        eligible = [r for r in self.reviewers if r.tier == tier]
        if not eligible:
            # Escalate to next tier
            tier_order = [Tier.L1, Tier.L2, Tier.L3]
            current_idx = tier_order.index(tier) if tier in tier_order else -1
            for next_tier in tier_order[current_idx + 1:]:
                eligible = [r for r in self.reviewers if r.tier == next_tier]
                if eligible:
                    break
        if not eligible:
            return None

        # Route to reviewer with smallest queue (load balancing)
        eligible.sort(key=lambda r: len(r.queue))
        return eligible[0]

    def simulate_human_review(self, query: Query, reviewer: Reviewer):
        """Simulate human reviewing a query."""
        # Simulate review time based on tier
        review_time = reviewer.avg_review_time * random.uniform(0.5, 1.5)

        # Human accuracy: L1=90%, L2=95%, L3=98%
        human_accuracy = {"L1": 0.90, "L2": 0.95, "L3": 0.98}
        accuracy = human_accuracy.get(reviewer.tier.value, 0.95)

        # Human decision
        if random.random() < accuracy:
            human_decision = query.true_label  # Human gets it right
        else:
            human_decision = "reject" if query.true_label == "approve" else "approve"

        # Check if human agrees with AI
        agreed = (human_decision == query.ai_prediction)

        # Generate feedback
        feedback = ""
        if not agreed:
            feedback = f"AI said '{query.ai_prediction}' but correct is '{human_decision}'"
            self.metrics.human_disagreed_with_ai += 1
            self.metrics.errors_caught_by_humans += 1
        else:
            self.metrics.human_agreed_with_ai += 1

        # Update query
        query.resolution = human_decision
        query.resolved_by = reviewer.name
        query.resolved_at = query.created_at + review_time
        query.feedback = feedback

        # Update reviewer stats
        reviewer.items_reviewed += 1
        if human_decision == query.true_label:
            reviewer.correct_decisions += 1

        # Check SLA
        if review_time > query.sla_seconds:
            self.metrics.sla_breaches += 1

        # Store feedback for model improvement
        if feedback:
            self.feedback_store.append({
                "query_id": query.id,
                "category": query.category,
                "ai_prediction": query.ai_prediction,
                "ai_confidence": query.ai_confidence,
                "human_decision": human_decision,
                "true_label": query.true_label,
            })
            self.metrics.feedback_collected += 1

        return review_time

    def process_queries(self, queries):
        """Process a batch of queries through the escalation system."""
        results = {"auto": [], "l1": [], "l2": [], "l3": []}

        for query in queries:
            tier = self.route_query(query)
            query.tier_routed = tier
            self.metrics.total_processed += 1

            if tier == Tier.AUTO:
                query.resolution = query.ai_prediction
                query.resolved_by = "AI"
                query.resolved_at = query.created_at + 0.1
                self.metrics.auto_approved += 1
                results["auto"].append(query)
            else:
                reviewer = self.assign_to_reviewer(query, tier)
                if reviewer:
                    review_time = self.simulate_human_review(query, reviewer)
                    self.metrics.total_resolution_time += review_time

                    if tier == Tier.L1:
                        self.metrics.l1_reviewed += 1
                        results["l1"].append(query)
                    elif tier == Tier.L2:
                        self.metrics.l2_reviewed += 1
                        results["l2"].append(query)
                    else:
                        self.metrics.l3_reviewed += 1
                        results["l3"].append(query)

        return results

    def simulate_model_improvement(self):
        """Simulate model improving from human feedback."""
        if len(self.feedback_store) > 20:
            # Each batch of feedback slightly improves the model
            improvement = len(self.feedback_store) * 0.0005
            old_accuracy = self.model_accuracy
            self.model_accuracy = min(0.98, self.model_accuracy + improvement)
            return old_accuracy, self.model_accuracy
        return self.model_accuracy, self.model_accuracy

    def print_metrics(self):
        """Print escalation metrics dashboard."""
        m = self.metrics
        total = m.total_processed or 1

        print("\n" + "=" * 65)
        print("           ESCALATION ENGINE - METRICS DASHBOARD")
        print("=" * 65)

        print(f"\n{'ROUTING DISTRIBUTION':^65}")
        print("-" * 65)
        print(f"  Total Processed:     {m.total_processed}")
        print(f"  Auto-approved:       {m.auto_approved:>6} ({m.auto_approved/total*100:.1f}%)")
        print(f"  L1 Reviewed:         {m.l1_reviewed:>6} ({m.l1_reviewed/total*100:.1f}%)")
        print(f"  L2 Reviewed:         {m.l2_reviewed:>6} ({m.l2_reviewed/total*100:.1f}%)")
        print(f"  L3 Reviewed:         {m.l3_reviewed:>6} ({m.l3_reviewed/total*100:.1f}%)")

        human_total = m.l1_reviewed + m.l2_reviewed + m.l3_reviewed
        print(f"\n{'QUALITY METRICS':^65}")
        print("-" * 65)
        if human_total > 0:
            agreement_rate = m.human_agreed_with_ai / human_total * 100
            print(f"  Human-AI Agreement:  {agreement_rate:.1f}%")
            print(f"  Errors Caught:       {m.errors_caught_by_humans}")
            print(f"  Feedback Collected:  {m.feedback_collected}")
            avg_time = m.total_resolution_time / human_total
            print(f"  Avg Resolution Time: {avg_time:.0f} seconds")

        print(f"  SLA Breaches:        {m.sla_breaches}")

        print(f"\n{'REVIEWER PERFORMANCE':^65}")
        print("-" * 65)
        print(f"  {'Name':<10} {'Tier':<5} {'Reviewed':<10} {'Accuracy':<10}")
        print(f"  {'-'*10} {'-'*5} {'-'*10} {'-'*10}")
        for r in self.reviewers:
            if r.items_reviewed > 0:
                acc = r.correct_decisions / r.items_reviewed * 100
                print(f"  {r.name:<10} {r.tier.value:<5} {r.items_reviewed:<10} {acc:.1f}%")

        print(f"\n{'MODEL IMPROVEMENT':^65}")
        print("-" * 65)
        print(f"  Current Model Accuracy: {self.model_accuracy:.3f}")
        print(f"  Feedback Items:         {len(self.feedback_store)}")


def simulate_progressive_automation():
    """Simulate how escalation rate decreases over time as model improves."""
    print("\n" + "=" * 65)
    print("      PROGRESSIVE AUTOMATION SIMULATION")
    print("=" * 65)
    print("\n  Simulating 6 months of model improvement from human feedback...")
    print(f"\n  {'Month':<8} {'Model Acc':<12} {'Auto Rate':<12} {'Escalation':<12} {'Est. Cost/day'}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*13}")

    engine = EscalationEngine()
    monthly_costs = []

    for month in range(1, 7):
        engine.metrics = EscalationMetrics()
        queries = engine.generate_queries(n=1000)
        engine.process_queries(queries)

        auto_rate = engine.metrics.auto_approved / engine.metrics.total_processed
        escalation_rate = 1 - auto_rate
        # Cost: $2 per human review, $0.001 per auto
        human_reviews = engine.metrics.total_processed * escalation_rate
        daily_cost = human_reviews * 2 + engine.metrics.auto_approved * 0.001
        # Scale to 100K items/day
        daily_cost_scaled = daily_cost * 100
        monthly_costs.append(daily_cost_scaled)

        print(f"  {month:<8} {engine.model_accuracy:<12.3f} {auto_rate*100:<12.1f}% {escalation_rate*100:<12.1f}% ${daily_cost_scaled:,.0f}")

        # Model improves from feedback
        engine.simulate_model_improvement()
        # Slightly adjust thresholds as model improves
        if engine.model_accuracy > 0.90:
            engine.thresholds["auto_approve"] = max(0.88, engine.thresholds["auto_approve"] - 0.005)

    print(f"\n  Cost reduction over 6 months: ${monthly_costs[0]:,.0f}/day → ${monthly_costs[-1]:,.0f}/day")
    savings = (monthly_costs[0] - monthly_costs[-1]) * 30
    print(f"  Monthly savings by month 6: ${savings:,.0f}")


def demonstrate_confidence_routing():
    """Show how different confidence levels route to different tiers."""
    print("\n" + "=" * 65)
    print("      CONFIDENCE-BASED ROUTING DEMONSTRATION")
    print("=" * 65)

    engine = EscalationEngine()

    # Create queries with specific confidence levels
    test_cases = [
        (0.98, "spam", "High confidence spam → Auto"),
        (0.95, "content", "High confidence content → Auto"),
        (0.85, "general", "Medium confidence → L1"),
        (0.72, "medical", "Lower confidence medical → L1"),
        (0.60, "financial", "Low confidence financial → L2"),
        (0.45, "content", "Very low confidence → L3"),
        (0.90, "safety", "Safety below 0.98 → L3 (always escalate safety)"),
    ]

    print(f"\n  Thresholds: Auto>{engine.thresholds['auto_approve']:.2f}, "
          f"L1>{engine.thresholds['l1_review']:.2f}, "
          f"L2>{engine.thresholds['l2_review']:.2f}, below→L3")
    print(f"\n  {'Confidence':<12} {'Category':<12} {'Routed To':<10} {'Explanation'}")
    print(f"  {'-'*12} {'-'*12} {'-'*10} {'-'*40}")

    for conf, category, explanation in test_cases:
        query = Query(
            id=0, content="test", category=category,
            true_label="approve", ai_confidence=conf,
            ai_prediction="approve", created_at=0.0
        )
        tier = engine.route_query(query)
        print(f"  {conf:<12.2f} {category:<12} {tier.value:<10} {explanation}")


def main():
    print("=" * 65)
    print("        HUMAN-IN-THE-LOOP ESCALATION ENGINE")
    print("        Multi-Tier Routing with SLA & Feedback")
    print("=" * 65)

    random.seed(42)

    # 1. Demonstrate confidence routing
    demonstrate_confidence_routing()

    # 2. Process a batch of queries
    print("\n" + "=" * 65)
    print("      BATCH PROCESSING SIMULATION (500 queries)")
    print("=" * 65)

    engine = EscalationEngine()
    queries = engine.generate_queries(n=500)
    results = engine.process_queries(queries)

    # Show sample escalations
    print("\n  Sample Escalated Items:")
    print(f"  {'ID':<5} {'Category':<12} {'Confidence':<12} {'Tier':<6} {'AI Said':<10} {'Human Said':<10} {'Correct?'}")
    print(f"  {'-'*5} {'-'*12} {'-'*12} {'-'*6} {'-'*10} {'-'*10} {'-'*8}")

    escalated = [q for q in queries if q.tier_routed != Tier.AUTO][:10]
    for q in escalated:
        correct = "Yes" if q.resolution == q.true_label else "No"
        print(f"  {q.id:<5} {q.category:<12} {q.ai_confidence:<12.3f} {q.tier_routed.value:<6} "
              f"{q.ai_prediction:<10} {q.resolution:<10} {correct}")

    engine.print_metrics()

    # 3. Auto-approved accuracy check
    auto_queries = results["auto"]
    if auto_queries:
        auto_correct = sum(1 for q in auto_queries if q.ai_prediction == q.true_label)
        auto_accuracy = auto_correct / len(auto_queries) * 100
        print(f"\n  Auto-approved accuracy: {auto_accuracy:.1f}% ({auto_correct}/{len(auto_queries)})")
        print(f"  (High confidence items that bypassed human review)")

    # 4. Progressive automation
    simulate_progressive_automation()

    # 5. Summary
    print("\n" + "=" * 65)
    print("      KEY TAKEAWAYS")
    print("=" * 65)
    print("""
  1. Confidence-based routing sends only uncertain items to humans
  2. Multi-tier escalation matches complexity to reviewer expertise
  3. Human feedback improves the model over time (self-improving)
  4. Progressive automation: escalation rate decreases as model improves
  5. SLA tracking ensures timely resolution of escalated items
  6. Cost optimization: only pay for human review where it matters
    """)


if __name__ == "__main__":
    main()
