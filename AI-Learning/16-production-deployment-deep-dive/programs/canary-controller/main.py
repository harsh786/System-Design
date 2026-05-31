"""
Canary Deployment Controller for AI Models
===========================================

Simulates canary deployment: gradually shift traffic from the old model version
to the new one while monitoring quality metrics. If degradation is detected,
automatically roll back before most users are affected.

Unlike blue-green (all-or-nothing switch), canary gives you:
- Gradual risk exposure (1% -> 5% -> 25% -> 50% -> 100%)
- Real production traffic validation (not synthetic)
- Statistical confidence before proceeding
- Automatic rollback on metric degradation
"""

import time
import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class CanaryPhase(Enum):
    NOT_STARTED = "not_started"
    RAMPING = "ramping"
    BAKING = "baking"  # Holding at a stage to gather confidence
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"


@dataclass
class ModelEndpoint:
    name: str
    version: str
    accuracy: float  # True accuracy (simulated)
    p50_latency_ms: float
    p99_latency_ms: float

    def serve(self) -> Tuple[bool, float]:
        """Serve a request. Returns (success, latency_ms)."""
        success = random.random() < self.accuracy
        # Log-normal latency distribution (realistic)
        latency = random.lognormvariate(
            math.log(self.p50_latency_ms), 0.3
        )
        latency = min(latency, self.p99_latency_ms * 1.5)  # Cap outliers
        return success, latency


@dataclass
class MetricsWindow:
    """Sliding window of metrics for a model version."""
    successes: int = 0
    failures: int = 0
    latencies: List[float] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.successes / self.total

    @property
    def p50_latency(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        return sorted_lat[len(sorted_lat) // 2]

    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def record(self, success: bool, latency: float):
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.latencies.append(latency)

    def reset(self):
        self.successes = 0
        self.failures = 0
        self.latencies = []


@dataclass
class CanaryConfig:
    """Configuration for a canary rollout."""
    # Traffic percentage stages
    stages: List[int] = field(default_factory=lambda: [1, 5, 25, 50, 100])
    # Minimum requests per stage before evaluation
    min_requests_per_stage: int = 100
    # Maximum acceptable degradation vs baseline
    max_error_rate_increase: float = 0.02  # 2% absolute increase
    max_latency_increase_pct: float = 0.20  # 20% relative increase
    # Bake time at each stage (simulated seconds)
    bake_time_per_stage: float = 0.5


class CanaryController:
    """
    Controls the canary rollout of a new AI model version.
    
    In production, this would integrate with:
    - Service mesh (Istio, Linkerd) for traffic splitting
    - Metrics systems (Prometheus) for real-time quality signals
    - Feature flags (LaunchDarkly) for user-level targeting
    - Alerting (PagerDuty) for degradation notifications
    """

    def __init__(self, config: CanaryConfig):
        self.config = config
        self.phase = CanaryPhase.NOT_STARTED
        self.current_stage_idx = 0
        self.baseline_metrics = MetricsWindow()
        self.canary_metrics = MetricsWindow()
        self.rollout_log: List[str] = []

    def _log(self, msg: str):
        self.rollout_log.append(msg)
        print(f"    {msg}")

    def route_request(self, canary_pct: int) -> str:
        """Decide whether a request goes to baseline or canary."""
        if random.randint(1, 100) <= canary_pct:
            return "canary"
        return "baseline"

    def evaluate_canary(self) -> Tuple[bool, str]:
        """
        Compare canary metrics against baseline.
        Returns (is_healthy, reason).
        
        This is the CRITICAL decision function. In production you'd want:
        - Statistical significance tests (chi-squared, t-test)
        - Multiple metrics (accuracy, latency, error rate, business KPIs)
        - Minimum sample size requirements
        """
        if self.canary_metrics.total < 20:
            return True, "insufficient data"

        # Check error rate
        baseline_error = 1 - self.baseline_metrics.success_rate
        canary_error = 1 - self.canary_metrics.success_rate
        error_increase = canary_error - baseline_error

        if error_increase > self.config.max_error_rate_increase:
            return False, (
                f"Error rate increase: {error_increase:.3f} "
                f"(baseline={baseline_error:.3f}, canary={canary_error:.3f})"
            )

        # Check latency
        if self.baseline_metrics.p50_latency > 0:
            latency_increase = (
                (self.canary_metrics.p50_latency - self.baseline_metrics.p50_latency)
                / self.baseline_metrics.p50_latency
            )
            if latency_increase > self.config.max_latency_increase_pct:
                return False, (
                    f"Latency increase: {latency_increase:.1%} "
                    f"(baseline={self.baseline_metrics.p50_latency:.1f}ms, "
                    f"canary={self.canary_metrics.p50_latency:.1f}ms)"
                )

        return True, "all metrics within bounds"

    def run_rollout(self, baseline: ModelEndpoint, canary: ModelEndpoint) -> bool:
        """
        Execute the full canary rollout.
        Returns True if canary was promoted, False if rolled back.
        """
        print(f"\n  Starting canary rollout:")
        print(f"    Baseline: {baseline.name} v{baseline.version}")
        print(f"    Canary:   {canary.name} v{canary.version}")
        print(f"    Stages:   {self.config.stages}%")
        print()

        self.phase = CanaryPhase.RAMPING

        for stage_idx, pct in enumerate(self.config.stages):
            self.current_stage_idx = stage_idx
            self.canary_metrics.reset()
            self.baseline_metrics.reset()

            print(f"  ┌─ Stage {stage_idx + 1}/{len(self.config.stages)}: "
                  f"Canary at {pct}% traffic")
            print(f"  │")

            # Simulate requests at this traffic split
            num_requests = self.config.min_requests_per_stage
            for i in range(num_requests):
                target = self.route_request(pct)
                if target == "canary":
                    success, latency = canary.serve()
                    self.canary_metrics.record(success, latency)
                else:
                    success, latency = baseline.serve()
                    self.baseline_metrics.record(success, latency)

            # Report metrics
            print(f"  │  Baseline: {self.baseline_metrics.total} reqs, "
                  f"success={self.baseline_metrics.success_rate:.3f}, "
                  f"p50={self.baseline_metrics.p50_latency:.1f}ms")
            print(f"  │  Canary:   {self.canary_metrics.total} reqs, "
                  f"success={self.canary_metrics.success_rate:.3f}, "
                  f"p50={self.canary_metrics.p50_latency:.1f}ms")

            # Evaluate
            is_healthy, reason = self.evaluate_canary()

            if not is_healthy:
                print(f"  │")
                print(f"  │  ✗ DEGRADATION DETECTED: {reason}")
                print(f"  │  ✗ AUTO-ROLLBACK triggered at {pct}% traffic")
                print(f"  └─ Canary ROLLED BACK")
                self.phase = CanaryPhase.ROLLED_BACK
                self._log(f"Rolled back at stage {stage_idx+1} ({pct}%): {reason}")
                return False

            print(f"  │  ✓ Healthy: {reason}")

            # Bake time
            if pct < 100:
                self.phase = CanaryPhase.BAKING
                print(f"  │  Baking at {pct}%...")
                time.sleep(self.config.bake_time_per_stage)
                print(f"  │  Bake complete, advancing to next stage")

            print(f"  └─ Stage passed\n")

        # Full promotion
        self.phase = CanaryPhase.PROMOTED
        self._log(f"Canary promoted to 100%: {canary.name} v{canary.version}")
        print(f"  ✓ CANARY PROMOTED: {canary.name} v{canary.version} is now serving 100%")
        return True


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          CANARY DEPLOYMENT CONTROLLER                        ║
║          Gradual Traffic Shifting with Auto-Rollback         ║
╠══════════════════════════════════════════════════════════════╣
║  Pattern: Shift traffic gradually (1%->5%->25%->50%->100%)  ║
║  Monitor quality metrics at each stage.                      ║
║  Auto-rollback if degradation exceeds thresholds.            ║
╚══════════════════════════════════════════════════════════════╝
""")

    config = CanaryConfig(
        stages=[1, 5, 25, 50, 100],
        min_requests_per_stage=200,
        max_error_rate_increase=0.03,
        max_latency_increase_pct=0.25,
        bake_time_per_stage=0.3,
    )

    # --- Scenario 1: Successful canary (better model) ---
    print("━" * 60)
    print("  SCENARIO 1: Good canary - improved model version")
    print("━" * 60)

    baseline_v1 = ModelEndpoint("fraud-detector", "2.3.0", accuracy=0.93, p50_latency_ms=30, p99_latency_ms=120)
    canary_v1 = ModelEndpoint("fraud-detector", "2.4.0", accuracy=0.95, p50_latency_ms=28, p99_latency_ms=110)

    controller1 = CanaryController(config)
    controller1.run_rollout(baseline_v1, canary_v1)

    # --- Scenario 2: Bad canary (accuracy regression) ---
    print("\n" + "━" * 60)
    print("  SCENARIO 2: Bad canary - accuracy regression")
    print("━" * 60)
    print("  (Model was trained on stale data, accuracy dropped)")

    baseline_v2 = ModelEndpoint("fraud-detector", "2.4.0", accuracy=0.95, p50_latency_ms=28, p99_latency_ms=110)
    canary_v2 = ModelEndpoint("fraud-detector", "2.5.0", accuracy=0.82, p50_latency_ms=35, p99_latency_ms=150)

    controller2 = CanaryController(config)
    controller2.run_rollout(baseline_v2, canary_v2)

    # --- Scenario 3: Latency regression ---
    print("\n" + "━" * 60)
    print("  SCENARIO 3: Bad canary - latency regression")
    print("━" * 60)
    print("  (Larger model, accuracy same but too slow)")

    baseline_v3 = ModelEndpoint("fraud-detector", "2.4.0", accuracy=0.95, p50_latency_ms=28, p99_latency_ms=110)
    canary_v3 = ModelEndpoint("fraud-detector", "2.5.1", accuracy=0.95, p50_latency_ms=50, p99_latency_ms=200)

    controller3 = CanaryController(config)
    controller3.run_rollout(baseline_v3, canary_v3)

    # --- Summary ---
    print(f"""
{'━'*60}
  KEY TAKEAWAYS
{'━'*60}
  1. Canary limits blast radius - only X% of users see the new version
  2. Real production traffic validates the model (not synthetic tests)
  3. Multiple metrics matter: accuracy AND latency AND error rates
  4. Statistical significance requires minimum sample sizes
  5. Bake time catches issues that appear only under sustained load
  6. Auto-rollback prevents human reaction time from causing outages
  
  Canary vs Blue-Green:
  ┌──────────────┬──────────────────────┬─────────────────────┐
  │              │ Blue-Green           │ Canary              │
  ├──────────────┼──────────────────────┼─────────────────────┤
  │ Risk         │ All-or-nothing       │ Gradual exposure    │
  │ Validation   │ Synthetic/shadow     │ Real traffic        │
  │ Rollback     │ Instant (LB switch)  │ Instant (route 0%)  │
  │ Complexity   │ Lower                │ Higher              │
  │ Duration     │ Minutes              │ Hours to days       │
  │ Best for     │ Infra changes        │ Model quality       │
  └──────────────┴──────────────────────┴─────────────────────┘
  
  In production, use tools like:
  - Istio VirtualService for traffic splitting
  - Flagger for automated canary analysis
  - Argo Rollouts for Kubernetes-native canary
  - Custom metrics from model serving (accuracy, drift scores)
{'━'*60}
""")


if __name__ == "__main__":
    main()
