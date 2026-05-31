"""
Strangler Fig Migration Simulator

Simulates migrating from a legacy rule-based system to an LLM-based system
using the strangler fig pattern. Demonstrates gradual traffic shifting,
quality comparison, and rollback scenarios.
"""

import random
import time
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class QueryCategory(Enum):
    FACTUAL = "factual"
    REASONING = "reasoning"
    CREATIVE = "creative"
    CLASSIFICATION = "classification"


@dataclass
class Query:
    id: str
    text: str
    category: QueryCategory
    expected_quality: float  # 0-1 baseline quality expectation
    timestamp: float = field(default_factory=time.time)


@dataclass
class Response:
    query_id: str
    system: str  # "legacy" or "new"
    content: str
    quality_score: float  # 0-1
    latency_ms: float
    cost: float


@dataclass
class QualityGate:
    min_quality: float
    max_error_rate: float
    max_latency_p95_ms: float
    min_sample_size: int
    evaluation_window_seconds: float


@dataclass
class MigrationPhase:
    name: str
    new_system_percentage: float
    quality_gate: QualityGate
    duration_seconds: float


class LegacySystem:
    """Rule-based system with predictable but limited capabilities."""

    def __init__(self):
        self.rules: Dict[QueryCategory, float] = {
            QueryCategory.FACTUAL: 0.75,
            QueryCategory.REASONING: 0.50,
            QueryCategory.CREATIVE: 0.30,
            QueryCategory.CLASSIFICATION: 0.80,
        }
        self.base_latency_ms = 20.0
        self.cost_per_query = 0.001

    def process(self, query: Query) -> Response:
        base_quality = self.rules.get(query.category, 0.5)
        quality = max(0, min(1, base_quality + random.gauss(0, 0.05)))
        latency = self.base_latency_ms + random.expovariate(1 / 5.0)
        content = f"[LEGACY] Rule-based response for: {query.text[:50]}"
        return Response(
            query_id=query.id,
            system="legacy",
            content=content,
            quality_score=quality,
            latency_ms=latency,
            cost=self.cost_per_query,
        )


class NewSystem:
    """LLM-based system with higher quality but variable performance."""

    def __init__(self, reliability: float = 0.95):
        self.quality_boost: Dict[QueryCategory, float] = {
            QueryCategory.FACTUAL: 0.85,
            QueryCategory.REASONING: 0.80,
            QueryCategory.CREATIVE: 0.85,
            QueryCategory.CLASSIFICATION: 0.82,
        }
        self.base_latency_ms = 150.0
        self.cost_per_query = 0.02
        self.reliability = reliability
        self.error_rate = 1 - reliability
        self._degraded = False

    def set_degraded(self, degraded: bool):
        self._degraded = degraded

    def process(self, query: Query) -> Optional[Response]:
        if random.random() < self.error_rate or self._degraded:
            return None  # Simulates failure

        base_quality = self.quality_boost.get(query.category, 0.7)
        if self._degraded:
            base_quality *= 0.5
        quality = max(0, min(1, base_quality + random.gauss(0, 0.08)))
        latency = self.base_latency_ms + random.expovariate(1 / 50.0)
        content = f"[LLM] AI-generated response for: {query.text[:50]}"
        return Response(
            query_id=query.id,
            system="new",
            content=content,
            quality_score=quality,
            latency_ms=latency,
            cost=self.cost_per_query,
        )


class MigrationProxy:
    """Routes traffic between legacy and new systems based on migration phase."""

    def __init__(self, legacy: LegacySystem, new: NewSystem):
        self.legacy = legacy
        self.new = new
        self.new_system_percentage = 0.0
        self.fallback_to_legacy = True
        self.metrics: List[Response] = []
        self.errors: List[str] = []
        self.routing_decisions: Dict[str, str] = {}

    def route(self, query: Query) -> Response:
        use_new = random.random() < self.new_system_percentage

        if use_new:
            response = self.new.process(query)
            if response is None:
                self.errors.append(query.id)
                if self.fallback_to_legacy:
                    response = self.legacy.process(query)
                    self.routing_decisions[query.id] = "new->fallback"
                else:
                    response = Response(
                        query_id=query.id,
                        system="new",
                        content="[ERROR] System unavailable",
                        quality_score=0.0,
                        latency_ms=5000.0,
                        cost=self.new.cost_per_query,
                    )
                    self.routing_decisions[query.id] = "new->error"
            else:
                self.routing_decisions[query.id] = "new"
        else:
            response = self.legacy.process(query)
            self.routing_decisions[query.id] = "legacy"

        self.metrics.append(response)
        return response

    def get_phase_metrics(self, window_size: int = 100) -> Dict:
        recent = self.metrics[-window_size:] if self.metrics else []
        if not recent:
            return {"quality": 0, "error_rate": 0, "latency_p95": 0, "count": 0}

        new_responses = [r for r in recent if r.system == "new"]
        all_qualities = [r.quality_score for r in recent]
        all_latencies = [r.latency_ms for r in recent]

        error_count = len([q for q in list(self.routing_decisions.values())[-window_size:]
                         if "error" in q or "fallback" in q])

        sorted_latencies = sorted(all_latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        latency_p95 = sorted_latencies[p95_idx] if sorted_latencies else 0

        return {
            "avg_quality": sum(all_qualities) / len(all_qualities) if all_qualities else 0,
            "error_rate": error_count / len(recent) if recent else 0,
            "latency_p95_ms": latency_p95,
            "count": len(recent),
            "new_system_count": len(new_responses),
            "total_cost": sum(r.cost for r in recent),
        }


class QualityComparator:
    """Compares quality between legacy and new system responses."""

    def __init__(self):
        self.comparisons: List[Dict] = []

    def compare(self, legacy_response: Response, new_response: Optional[Response]) -> Dict:
        if new_response is None:
            result = {
                "query_id": legacy_response.query_id,
                "legacy_quality": legacy_response.quality_score,
                "new_quality": 0.0,
                "quality_delta": -legacy_response.quality_score,
                "new_system_failed": True,
            }
        else:
            delta = new_response.quality_score - legacy_response.quality_score
            result = {
                "query_id": legacy_response.query_id,
                "legacy_quality": legacy_response.quality_score,
                "new_quality": new_response.quality_score,
                "quality_delta": delta,
                "latency_delta_ms": new_response.latency_ms - legacy_response.latency_ms,
                "cost_delta": new_response.cost - legacy_response.cost,
                "new_system_failed": False,
            }
        self.comparisons.append(result)
        return result

    def summary(self) -> Dict:
        if not self.comparisons:
            return {}
        successful = [c for c in self.comparisons if not c["new_system_failed"]]
        failed = [c for c in self.comparisons if c["new_system_failed"]]
        avg_delta = (sum(c["quality_delta"] for c in successful) / len(successful)
                     if successful else 0)
        return {
            "total_comparisons": len(self.comparisons),
            "successful_comparisons": len(successful),
            "failed_comparisons": len(failed),
            "avg_quality_improvement": avg_delta,
            "improvement_rate": len([c for c in successful if c["quality_delta"] > 0]) / len(successful) if successful else 0,
        }


def generate_queries(count: int) -> List[Query]:
    """Generate synthetic queries for simulation."""
    categories = list(QueryCategory)
    queries = []
    for i in range(count):
        category = random.choice(categories)
        query_id = hashlib.md5(f"query-{i}-{time.time()}".encode()).hexdigest()[:8]
        queries.append(Query(
            id=query_id,
            text=f"Sample {category.value} query number {i}",
            category=category,
            expected_quality=0.7,
        ))
    return queries


def run_migration_simulation():
    """Run the full strangler fig migration simulation."""
    print("=" * 70)
    print("STRANGLER FIG MIGRATION SIMULATOR")
    print("Legacy (rule-based) → New (LLM-based) gradual migration")
    print("=" * 70)

    random.seed(42)

    legacy = LegacySystem()
    new_system = NewSystem(reliability=0.95)
    proxy = MigrationProxy(legacy, new_system)
    comparator = QualityComparator()

    # Define migration phases
    phases = [
        MigrationPhase(
            name="Shadow Mode",
            new_system_percentage=0.0,
            quality_gate=QualityGate(
                min_quality=0.0, max_error_rate=1.0,
                max_latency_p95_ms=10000, min_sample_size=50,
                evaluation_window_seconds=60,
            ),
            duration_seconds=1.0,
        ),
        MigrationPhase(
            name="Canary (5%)",
            new_system_percentage=0.05,
            quality_gate=QualityGate(
                min_quality=0.65, max_error_rate=0.10,
                max_latency_p95_ms=500, min_sample_size=50,
                evaluation_window_seconds=60,
            ),
            duration_seconds=1.0,
        ),
        MigrationPhase(
            name="Early Adoption (25%)",
            new_system_percentage=0.25,
            quality_gate=QualityGate(
                min_quality=0.70, max_error_rate=0.08,
                max_latency_p95_ms=400, min_sample_size=100,
                evaluation_window_seconds=60,
            ),
            duration_seconds=1.0,
        ),
        MigrationPhase(
            name="Majority (50%)",
            new_system_percentage=0.50,
            quality_gate=QualityGate(
                min_quality=0.72, max_error_rate=0.06,
                max_latency_p95_ms=350, min_sample_size=100,
                evaluation_window_seconds=60,
            ),
            duration_seconds=1.0,
        ),
        MigrationPhase(
            name="Full Migration (90%)",
            new_system_percentage=0.90,
            quality_gate=QualityGate(
                min_quality=0.75, max_error_rate=0.05,
                max_latency_p95_ms=300, min_sample_size=100,
                evaluation_window_seconds=60,
            ),
            duration_seconds=1.0,
        ),
    ]

    # Phase 1: Shadow mode - compare without routing
    print("\n--- Phase: Shadow Mode (comparison only) ---")
    shadow_queries = generate_queries(100)
    for query in shadow_queries:
        legacy_resp = legacy.process(query)
        new_resp = new_system.process(query)
        comparator.compare(legacy_resp, new_resp)

    shadow_summary = comparator.summary()
    print(f"  Shadow comparisons: {shadow_summary['total_comparisons']}")
    print(f"  Avg quality improvement: {shadow_summary['avg_quality_improvement']:+.3f}")
    print(f"  New system success rate: {shadow_summary['successful_comparisons']}/{shadow_summary['total_comparisons']}")
    print(f"  Improvement rate: {shadow_summary['improvement_rate']:.1%}")

    # Phase 2-5: Gradual traffic shift
    rollback_triggered = False
    final_phase = None

    for phase in phases[1:]:
        print(f"\n--- Phase: {phase.name} ---")
        proxy.new_system_percentage = phase.new_system_percentage
        print(f"  Traffic to new system: {phase.new_system_percentage:.0%}")

        queries = generate_queries(200)
        for query in queries:
            proxy.route(query)

        metrics = proxy.get_phase_metrics(window_size=200)
        gate = phase.quality_gate

        print(f"  Avg Quality: {metrics['avg_quality']:.3f} (gate: >={gate.min_quality})")
        print(f"  Error Rate: {metrics['error_rate']:.3f} (gate: <={gate.max_error_rate})")
        print(f"  Latency P95: {metrics['latency_p95_ms']:.0f}ms (gate: <={gate.max_latency_p95_ms}ms)")
        print(f"  Cost: ${metrics['total_cost']:.3f}")

        # Check quality gate
        gate_passed = (
            metrics['avg_quality'] >= gate.min_quality
            and metrics['error_rate'] <= gate.max_error_rate
            and metrics['latency_p95_ms'] <= gate.max_latency_p95_ms
            and metrics['count'] >= gate.min_sample_size
        )

        if gate_passed:
            print(f"  ✓ Quality gate PASSED - proceeding to next phase")
            final_phase = phase
        else:
            print(f"  ✗ Quality gate FAILED - triggering rollback")
            rollback_triggered = True
            break

    # Simulate a degradation + rollback scenario
    if not rollback_triggered:
        print("\n--- Simulating Degradation Scenario ---")
        new_system.set_degraded(True)
        proxy.new_system_percentage = 0.90

        degraded_queries = generate_queries(100)
        for query in degraded_queries:
            proxy.route(query)

        degraded_metrics = proxy.get_phase_metrics(window_size=100)
        print(f"  Degraded Quality: {degraded_metrics['avg_quality']:.3f}")
        print(f"  Degraded Error Rate: {degraded_metrics['error_rate']:.3f}")

        if degraded_metrics['avg_quality'] < 0.70 or degraded_metrics['error_rate'] > 0.10:
            print("  ⚠ Degradation detected! Initiating rollback...")
            rollback_triggered = True

    # Rollback
    if rollback_triggered:
        print("\n--- ROLLBACK INITIATED ---")
        proxy.new_system_percentage = 0.0
        new_system.set_degraded(False)

        rollback_queries = generate_queries(50)
        for query in rollback_queries:
            proxy.route(query)

        rollback_metrics = proxy.get_phase_metrics(window_size=50)
        print(f"  Post-rollback Quality: {rollback_metrics['avg_quality']:.3f}")
        print(f"  Post-rollback Error Rate: {rollback_metrics['error_rate']:.3f}")
        print(f"  System stabilized on legacy")

    # Final summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    total_metrics = proxy.get_phase_metrics(window_size=len(proxy.metrics))
    routing_counts = defaultdict(int)
    for decision in proxy.routing_decisions.values():
        routing_counts[decision] += 1

    print(f"  Total queries processed: {len(proxy.metrics)}")
    print(f"  Routing breakdown:")
    for route, count in sorted(routing_counts.items()):
        print(f"    {route}: {count} ({count/len(proxy.metrics):.1%})")
    print(f"  Overall avg quality: {total_metrics['avg_quality']:.3f}")
    print(f"  Overall error rate: {total_metrics['error_rate']:.3f}")
    print(f"  Total cost: ${total_metrics['total_cost']:.3f}")
    print(f"  Rollback triggered: {'Yes' if rollback_triggered else 'No'}")

    comparison_summary = comparator.summary()
    print(f"\n  Quality Comparison (shadow mode):")
    print(f"    New system improvement: {comparison_summary['avg_quality_improvement']:+.3f}")
    print(f"    Win rate: {comparison_summary['improvement_rate']:.1%}")


if __name__ == "__main__":
    run_migration_simulation()
