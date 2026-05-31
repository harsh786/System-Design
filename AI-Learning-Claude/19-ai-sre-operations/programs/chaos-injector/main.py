"""
Chaos Injector for AI Systems
Simulates chaos experiments to test AI system resilience.
"""

import time
import random
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExperimentResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


@dataclass
class ChaosExperiment:
    name: str
    description: str
    blast_radius: float  # 0.0 - 1.0
    duration_sec: int
    auto_stop_threshold: float
    result: Optional[ExperimentResult] = None
    measurements: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)


class AISystem:
    """Simulated AI system with resilience features."""

    def __init__(self):
        self.primary_provider = "openai"
        self.secondary_provider = "azure-openai"
        self.active_provider = self.primary_provider
        self.cache = {"query_1": "cached_response_1", "query_2": "cached_response_2"}
        self.cache_enabled = True
        self.rate_limit_remaining = 1000
        self.failover_enabled = True
        self.circuit_breaker_open = False
        self.quality_threshold = 0.7
        self.request_queue = []
        self.max_queue_size = 500
        self.metrics = {
            "requests_served": 0,
            "errors": 0,
            "failovers": 0,
            "cache_hits": 0,
            "queue_overflow": 0,
            "quality_blocks": 0,
        }

    def handle_request(self, query: str) -> dict:
        """Process a request through the AI system."""
        # Check cache first
        if self.cache_enabled and query in self.cache:
            self.metrics["cache_hits"] += 1
            return {"status": "success", "source": "cache", "latency_ms": 5}

        # Check circuit breaker
        if self.circuit_breaker_open:
            if len(self.request_queue) < self.max_queue_size:
                self.request_queue.append(query)
                return {"status": "queued", "queue_position": len(self.request_queue)}
            else:
                self.metrics["queue_overflow"] += 1
                return {"status": "rejected", "reason": "queue_full"}

        # Call model provider
        response = self._call_provider(query)
        if response["status"] == "error" and self.failover_enabled:
            self.metrics["failovers"] += 1
            self.active_provider = self.secondary_provider
            response = self._call_provider(query)

        self.metrics["requests_served"] += 1
        return response

    def _call_provider(self, query: str) -> dict:
        """Simulate calling the model provider."""
        if self.rate_limit_remaining <= 0:
            return {"status": "error", "code": 429, "reason": "rate_limited"}
        self.rate_limit_remaining -= 1
        # Normal response
        latency = random.gauss(200, 50)
        quality = random.gauss(0.92, 0.03)
        return {
            "status": "success",
            "provider": self.active_provider,
            "latency_ms": max(50, latency),
            "quality_score": min(1.0, max(0.0, quality)),
        }


class ChaosInjector:
    """Runs chaos experiments against the AI system."""

    def __init__(self):
        self.experiments: list[ChaosExperiment] = []
        self.system = AISystem()

    def run_all_experiments(self):
        """Run all chaos experiments and generate report."""
        print("=" * 70)
        print("  CHAOS ENGINEERING REPORT - AI SYSTEM RESILIENCE")
        print("=" * 70)
        print()

        experiments = [
            self._experiment_provider_outage,
            self._experiment_latency_injection,
            self._experiment_quality_degradation,
            self._experiment_cache_stampede,
            self._experiment_token_exhaustion,
        ]

        for experiment_fn in experiments:
            self.system = AISystem()  # Fresh system for each experiment
            experiment_fn()
            print()

        self._print_summary()

    def _experiment_provider_outage(self):
        """Experiment 1: Simulate provider returning 500 errors."""
        exp = ChaosExperiment(
            name="Provider Outage",
            description="Primary provider returns 500 errors for all requests",
            blast_radius=1.0,
            duration_sec=60,
            auto_stop_threshold=0.1,
        )

        print(f"{'─' * 70}")
        print(f"  EXPERIMENT: {exp.name}")
        print(f"  {exp.description}")
        print(f"  Blast radius: {exp.blast_radius * 100}% | Duration: {exp.duration_sec}s")
        print(f"{'─' * 70}")

        # Inject fault: make primary provider fail
        original_call = self.system._call_provider

        def failing_provider(query):
            if self.system.active_provider == "openai":
                return {"status": "error", "code": 500, "reason": "provider_outage"}
            return original_call(query)

        self.system._call_provider = failing_provider

        # Send requests and measure
        results = []
        failover_detected_at = None

        for i in range(100):
            response = self.system.handle_request(f"query_{i}")
            results.append(response)
            if response.get("provider") == "azure-openai" and failover_detected_at is None:
                failover_detected_at = i

        # Measure results
        successes = sum(1 for r in results if r["status"] == "success")
        errors = sum(1 for r in results if r["status"] == "error")

        exp.measurements = {
            "total_requests": 100,
            "successful": successes,
            "failed": errors,
            "failover_triggered": failover_detected_at is not None,
            "failover_at_request": failover_detected_at or "N/A",
            "success_rate": successes / 100,
        }

        # Evaluate
        if successes >= 99 and failover_detected_at is not None and failover_detected_at <= 2:
            exp.result = ExperimentResult.PASS
        elif successes >= 90:
            exp.result = ExperimentResult.PARTIAL
            exp.recommendations.append("Failover works but too slow - some requests failed")
        else:
            exp.result = ExperimentResult.FAIL
            exp.recommendations.append("Failover not working - significant request loss during outage")

        self.experiments.append(exp)
        self._print_experiment_result(exp)

    def _experiment_latency_injection(self):
        """Experiment 2: Add 5s delay to model responses."""
        exp = ChaosExperiment(
            name="Latency Injection",
            description="Add 5000ms delay to all model responses",
            blast_radius=0.5,
            duration_sec=120,
            auto_stop_threshold=0.3,
        )

        print(f"{'─' * 70}")
        print(f"  EXPERIMENT: {exp.name}")
        print(f"  {exp.description}")
        print(f"  Blast radius: {exp.blast_radius * 100}% | Duration: {exp.duration_sec}s")
        print(f"{'─' * 70}")

        # Inject latency
        original_call = self.system._call_provider
        injected_delay = 5000  # ms

        def slow_provider(query):
            result = original_call(query)
            if random.random() < 0.5:  # 50% blast radius
                result["latency_ms"] = result.get("latency_ms", 200) + injected_delay
            return result

        self.system._call_provider = slow_provider

        # Send requests and measure
        latencies = []
        timeout_count = 0
        timeout_threshold = 8000  # 8s timeout

        for i in range(100):
            response = self.system.handle_request(f"query_{i}")
            if response["status"] == "success":
                latency = response.get("latency_ms", 0)
                latencies.append(latency)
                if latency > timeout_threshold:
                    timeout_count += 1

        # Check if circuit breaker should have opened
        high_latency_count = sum(1 for l in latencies if l > 3000)
        circuit_breaker_should_open = high_latency_count > 30

        exp.measurements = {
            "total_requests": 100,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "timeouts": timeout_count,
            "high_latency_requests": high_latency_count,
            "circuit_breaker_activated": self.system.circuit_breaker_open,
        }

        # Evaluate
        if timeout_count == 0 and self.system.circuit_breaker_open:
            exp.result = ExperimentResult.PASS
        elif timeout_count < 5:
            exp.result = ExperimentResult.PARTIAL
            exp.recommendations.append("Timeout handling exists but circuit breaker didn't activate")
            if not self.system.circuit_breaker_open and circuit_breaker_should_open:
                exp.recommendations.append("Circuit breaker should have opened after sustained high latency")
        else:
            exp.result = ExperimentResult.FAIL
            exp.recommendations.append("No timeout protection - users experiencing unacceptable delays")
            exp.recommendations.append("Implement circuit breaker with 3s latency threshold")

        self.experiments.append(exp)
        self._print_experiment_result(exp)

    def _experiment_quality_degradation(self):
        """Experiment 3: Inject low-quality responses."""
        exp = ChaosExperiment(
            name="Quality Degradation",
            description="30% of responses replaced with low-quality generic answers",
            blast_radius=0.3,
            duration_sec=300,
            auto_stop_threshold=0.2,
        )

        print(f"{'─' * 70}")
        print(f"  EXPERIMENT: {exp.name}")
        print(f"  {exp.description}")
        print(f"  Blast radius: {exp.blast_radius * 100}% | Duration: {exp.duration_sec}s")
        print(f"{'─' * 70}")

        # Inject quality degradation
        original_call = self.system._call_provider

        def degraded_provider(query):
            result = original_call(query)
            if random.random() < 0.3:  # 30% degraded
                result["quality_score"] = random.uniform(0.3, 0.5)  # Low quality
            return result

        self.system._call_provider = degraded_provider

        # Send requests and track quality
        quality_scores = []
        detected_low_quality = 0

        for i in range(200):
            response = self.system.handle_request(f"query_{i}")
            if response["status"] == "success":
                score = response.get("quality_score", 0.9)
                quality_scores.append(score)
                if score < self.system.quality_threshold:
                    detected_low_quality += 1

        # Analysis
        low_quality_count = sum(1 for s in quality_scores if s < 0.6)
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        detection_rate = detected_low_quality / low_quality_count if low_quality_count > 0 else 0

        exp.measurements = {
            "total_responses": len(quality_scores),
            "low_quality_injected": low_quality_count,
            "low_quality_detected": detected_low_quality,
            "detection_rate": f"{detection_rate:.1%}",
            "avg_quality_score": f"{avg_quality:.3f}",
            "quality_below_threshold": f"{low_quality_count / len(quality_scores):.1%}",
        }

        # Evaluate
        if detection_rate > 0.8:
            exp.result = ExperimentResult.PASS
        elif detection_rate > 0.5:
            exp.result = ExperimentResult.PARTIAL
            exp.recommendations.append("Quality monitoring detects some issues but misses too many")
            exp.recommendations.append("Lower quality detection threshold or add secondary checks")
        else:
            exp.result = ExperimentResult.FAIL
            exp.recommendations.append("Quality monitoring not catching degraded responses")
            exp.recommendations.append("Implement output quality scoring on all responses")
            exp.recommendations.append("Add confidence thresholds that block low-quality outputs")

        self.experiments.append(exp)
        self._print_experiment_result(exp)

    def _experiment_cache_stampede(self):
        """Experiment 4: Invalidate all caches simultaneously."""
        exp = ChaosExperiment(
            name="Cache Stampede",
            description="All caches flushed simultaneously - thundering herd scenario",
            blast_radius=1.0,
            duration_sec=60,
            auto_stop_threshold=0.5,
        )

        print(f"{'─' * 70}")
        print(f"  EXPERIMENT: {exp.name}")
        print(f"  {exp.description}")
        print(f"  Blast radius: {exp.blast_radius * 100}% | Duration: {exp.duration_sec}s")
        print(f"{'─' * 70}")

        # First, warm the cache
        for i in range(50):
            self.system.cache[f"popular_query_{i}"] = f"cached_response_{i}"

        # Measure baseline (with cache)
        baseline_hits = 0
        for i in range(100):
            query = f"popular_query_{random.randint(0, 49)}"
            response = self.system.handle_request(query)
            if response.get("source") == "cache":
                baseline_hits += 1

        # FLUSH ALL CACHES
        self.system.cache = {}
        self.system.metrics["cache_hits"] = 0

        # Now send same traffic pattern - all will hit the model
        post_flush_results = []
        backend_load = 0
        errors = 0

        for i in range(200):
            query = f"popular_query_{random.randint(0, 49)}"
            response = self.system.handle_request(query)
            post_flush_results.append(response)
            if response["status"] == "success":
                backend_load += 1
            elif response["status"] in ("error", "rejected"):
                errors += 1

        # Check: did thundering herd protection work?
        # (In this simulation, we check if request coalescing happened)
        has_coalescing = False  # Simulated system doesn't have it yet
        backend_load_ratio = backend_load / 200

        exp.measurements = {
            "baseline_cache_hit_rate": f"{baseline_hits}%",
            "post_flush_backend_requests": backend_load,
            "post_flush_errors": errors,
            "backend_load_ratio": f"{backend_load_ratio:.1%}",
            "request_coalescing_active": has_coalescing,
            "cache_recovery_started": len(self.system.cache) > 0,
        }

        # Evaluate
        if errors == 0 and has_coalescing:
            exp.result = ExperimentResult.PASS
        elif errors == 0:
            exp.result = ExperimentResult.PARTIAL
            exp.recommendations.append("No errors but no thundering herd protection")
            exp.recommendations.append("Implement request coalescing for duplicate queries")
            exp.recommendations.append("Add cache warming strategy for post-flush recovery")
        else:
            exp.result = ExperimentResult.FAIL
            exp.recommendations.append("Cache flush causes errors - backend overloaded")
            exp.recommendations.append("Implement request coalescing immediately")
            exp.recommendations.append("Add circuit breaker to prevent cascade")

        self.experiments.append(exp)
        self._print_experiment_result(exp)

    def _experiment_token_exhaustion(self):
        """Experiment 5: Simulate hitting rate limits."""
        exp = ChaosExperiment(
            name="Token/Rate Limit Exhaustion",
            description="Provider returns 429 (rate limited) for all requests",
            blast_radius=1.0,
            duration_sec=60,
            auto_stop_threshold=0.3,
        )

        print(f"{'─' * 70}")
        print(f"  EXPERIMENT: {exp.name}")
        print(f"  {exp.description}")
        print(f"  Blast radius: {exp.blast_radius * 100}% | Duration: {exp.duration_sec}s")
        print(f"{'─' * 70}")

        # Exhaust rate limit
        self.system.rate_limit_remaining = 0

        # Send requests
        results = []
        queued = 0
        rejected = 0
        served_from_cache = 0

        for i in range(150):
            # Mix of cached and new queries
            if random.random() < 0.3:
                query = f"query_{random.randint(0, 1)}"  # Might hit cache
            else:
                query = f"new_query_{i}"
            response = self.system.handle_request(query)
            results.append(response)

            if response["status"] == "queued":
                queued += 1
            elif response["status"] == "rejected":
                rejected += 1
            elif response.get("source") == "cache":
                served_from_cache += 1

        exp.measurements = {
            "total_requests": 150,
            "served_from_cache": served_from_cache,
            "queued": queued,
            "rejected": rejected,
            "requests_lost": rejected,
            "queue_utilized": queued > 0,
            "graceful_degradation": rejected == 0,
        }

        # Evaluate
        if rejected == 0 and queued > 0:
            exp.result = ExperimentResult.PASS
        elif rejected < 10:
            exp.result = ExperimentResult.PARTIAL
            exp.recommendations.append("Queue handles most requests but some are dropped")
            exp.recommendations.append("Increase queue size or implement priority ordering")
        else:
            exp.result = ExperimentResult.FAIL
            exp.recommendations.append("Too many requests rejected - no graceful degradation")
            exp.recommendations.append("Implement request queue with priority levels")
            exp.recommendations.append("Add user-facing 'busy' message instead of errors")
            exp.recommendations.append("Consider secondary provider failover for rate limits")

        self.experiments.append(exp)
        self._print_experiment_result(exp)

    def _print_experiment_result(self, exp: ChaosExperiment):
        """Print formatted experiment result."""
        result_icon = {
            ExperimentResult.PASS: "✓ PASS",
            ExperimentResult.FAIL: "✗ FAIL",
            ExperimentResult.PARTIAL: "~ PARTIAL",
        }

        print(f"\n  Result: {result_icon[exp.result]}")
        print(f"\n  Measurements:")
        for key, value in exp.measurements.items():
            print(f"    {key}: {value}")

        if exp.recommendations:
            print(f"\n  Recommendations:")
            for rec in exp.recommendations:
                print(f"    → {rec}")

    def _print_summary(self):
        """Print final summary report."""
        print("=" * 70)
        print("  CHAOS EXPERIMENT SUMMARY")
        print("=" * 70)
        print()

        passed = sum(1 for e in self.experiments if e.result == ExperimentResult.PASS)
        partial = sum(1 for e in self.experiments if e.result == ExperimentResult.PARTIAL)
        failed = sum(1 for e in self.experiments if e.result == ExperimentResult.FAIL)

        print(f"  Total experiments: {len(self.experiments)}")
        print(f"  Passed:  {passed}")
        print(f"  Partial: {partial}")
        print(f"  Failed:  {failed}")
        print()

        # Resilience score
        score = (passed * 1.0 + partial * 0.5) / len(self.experiments)
        print(f"  RESILIENCE SCORE: {score:.0%}")
        print()

        if score >= 0.8:
            print("  Assessment: System is well-prepared for common AI failure modes.")
        elif score >= 0.5:
            print("  Assessment: System handles some failures but has gaps. Address recommendations.")
        else:
            print("  Assessment: System is fragile. Prioritize resilience engineering.")

        print()
        print("  Experiment Details:")
        print(f"  {'─' * 60}")
        for exp in self.experiments:
            icon = {"PASS": "✓", "FAIL": "✗", "PARTIAL": "~"}[exp.result.value]
            print(f"  {icon} {exp.name:<30} {exp.result.value}")

        # All recommendations
        all_recs = []
        for exp in self.experiments:
            for rec in exp.recommendations:
                all_recs.append((exp.name, rec))

        if all_recs:
            print()
            print(f"  {'─' * 60}")
            print("  Priority Recommendations:")
            for exp_name, rec in all_recs:
                print(f"    [{exp_name}] {rec}")

        print()
        print("=" * 70)


if __name__ == "__main__":
    injector = ChaosInjector()
    injector.run_all_experiments()
