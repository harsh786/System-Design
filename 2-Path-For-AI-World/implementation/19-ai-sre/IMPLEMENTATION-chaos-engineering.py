"""
AI SRE - Chaos Engineering System
===================================
Chaos engineering framework for AI systems: experiment definition, chaos scenarios,
safety controls, results measurement, and automated chaos runs.
"""

import uuid
import json
import time
import logging
import random
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# EXPERIMENT DEFINITION
# =============================================================================

class ExperimentStatus(Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"  # Kill switch activated
    FAILED = "failed"


class BlastRadiusLevel(Enum):
    MINIMAL = "minimal"       # < 1% of traffic
    LOW = "low"               # 1-5% of traffic
    MEDIUM = "medium"         # 5-20% of traffic
    HIGH = "high"             # 20-50% of traffic
    FULL = "full"             # 100% of traffic (only for staging)


@dataclass
class SteadyStateHypothesis:
    """Defines what "normal" looks like - verified before and after experiment."""
    name: str
    description: str
    metric: str
    operator: str  # ">=", "<=", "<", ">", "=="
    threshold: float
    measurement_fn: Callable[[], float]
    tolerance_pct: float = 5.0  # Allowed deviation from threshold


@dataclass
class ChaosExperiment:
    """Complete chaos experiment definition."""
    id: str
    name: str
    description: str
    hypothesis: str  # What we believe will happen
    
    # Scope
    blast_radius: BlastRadiusLevel
    target_traffic_pct: float  # % of traffic affected
    target_environment: str  # "staging", "canary", "production"
    duration_seconds: int
    
    # Steady state
    steady_state_checks: list[SteadyStateHypothesis] = field(default_factory=list)
    
    # Actions
    chaos_actions: list[dict] = field(default_factory=list)
    
    # Safety
    abort_conditions: list[Callable[[], bool]] = field(default_factory=list)
    max_impact_threshold: dict = field(default_factory=dict)  # Metric -> max allowed deviation
    requires_approval: bool = True
    approved_by: Optional[str] = None
    
    # Results
    status: ExperimentStatus = ExperimentStatus.DRAFT
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pre_experiment_state: dict = field(default_factory=dict)
    post_experiment_state: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    
    # Metadata
    owner: str = ""
    team: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: list[str] = field(default_factory=list)


# =============================================================================
# CHAOS SCENARIOS FOR AI SYSTEMS
# =============================================================================

class AIChaosScenarios:
    """Pre-defined chaos scenarios for AI systems."""
    
    def __init__(self):
        self._injectors: dict[str, Callable] = {}
        self._active_injections: dict[str, dict] = {}
        self._original_behaviors: dict[str, Any] = {}
    
    def create_model_provider_failure(self, failure_type: str = "500",
                                       failure_rate: float = 1.0) -> ChaosExperiment:
        """
        Scenario: Model provider becomes unavailable.
        
        Tests: Fallback activation, graceful degradation, user experience during outage.
        """
        def inject_failure():
            self._active_injections["model_provider"] = {
                "type": failure_type,
                "rate": failure_rate,
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning(f"CHAOS: Model provider failure injected ({failure_type}, rate={failure_rate})")
            return "Model provider failure injection active"
        
        def remove_failure():
            if "model_provider" in self._active_injections:
                del self._active_injections["model_provider"]
            logger.info("CHAOS: Model provider failure removed")
        
        experiment = ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name="Model Provider Failure",
            description=f"Simulate model provider returning {failure_type} errors at {failure_rate*100}% rate",
            hypothesis="System should activate fallback model within 30s and maintain >95% availability",
            blast_radius=BlastRadiusLevel.LOW,
            target_traffic_pct=5.0,
            target_environment="canary",
            duration_seconds=300,
            chaos_actions=[
                {"action": "inject", "fn": inject_failure},
                {"action": "cleanup", "fn": remove_failure},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="availability",
                    description="System availability remains above 95%",
                    metric="availability_rate",
                    operator=">=",
                    threshold=0.95,
                    measurement_fn=lambda: random.uniform(0.93, 0.99),
                ),
                SteadyStateHypothesis(
                    name="latency",
                    description="P95 latency stays under 10s (relaxed during failover)",
                    metric="latency_p95_ms",
                    operator="<=",
                    threshold=10000,
                    measurement_fn=lambda: random.uniform(2000, 8000),
                ),
            ],
            max_impact_threshold={
                "error_rate": 0.10,  # Max 10% error rate
                "latency_p95_ms": 15000,  # Max 15s p95
            },
            tags=["provider", "failover", "availability"],
        )
        return experiment
    
    def create_vector_db_latency(self, added_latency_ms: int = 5000) -> ChaosExperiment:
        """
        Scenario: Vector DB becomes slow (but not down).
        
        Tests: Timeout handling, degraded mode activation, user experience with slow retrieval.
        """
        def inject_latency():
            self._active_injections["vector_db_latency"] = {
                "added_ms": added_latency_ms,
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning(f"CHAOS: Vector DB latency +{added_latency_ms}ms injected")
        
        def remove_latency():
            if "vector_db_latency" in self._active_injections:
                del self._active_injections["vector_db_latency"]
            logger.info("CHAOS: Vector DB latency removed")
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name="Vector DB Latency Injection",
            description=f"Add {added_latency_ms}ms latency to all vector DB queries",
            hypothesis="System should timeout gracefully and fall back to parametric knowledge within 5s",
            blast_radius=BlastRadiusLevel.LOW,
            target_traffic_pct=5.0,
            target_environment="canary",
            duration_seconds=600,
            chaos_actions=[
                {"action": "inject", "fn": inject_latency},
                {"action": "cleanup", "fn": remove_latency},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="end_to_end_latency",
                    description="End-to-end latency stays under 15s",
                    metric="e2e_latency_p95_ms",
                    operator="<=",
                    threshold=15000,
                    measurement_fn=lambda: random.uniform(3000, 12000),
                ),
                SteadyStateHypothesis(
                    name="response_quality",
                    description="Response quality doesn't drop below 60% (may be lower without RAG)",
                    metric="quality_score",
                    operator=">=",
                    threshold=0.60,
                    measurement_fn=lambda: random.uniform(0.55, 0.80),
                ),
            ],
            tags=["vector_db", "latency", "degradation"],
        )
    
    def create_tool_timeout(self, tool_name: str = "database_query",
                            timeout_rate: float = 0.8) -> ChaosExperiment:
        """
        Scenario: A specific tool becomes slow/unresponsive.
        
        Tests: Agent handles tool unavailability, doesn't loop, provides useful partial answer.
        """
        def inject_timeout():
            self._active_injections[f"tool_timeout_{tool_name}"] = {
                "tool": tool_name,
                "timeout_rate": timeout_rate,
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning(f"CHAOS: Tool '{tool_name}' timeout at {timeout_rate*100}% rate")
        
        def remove_timeout():
            key = f"tool_timeout_{tool_name}"
            if key in self._active_injections:
                del self._active_injections[key]
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name=f"Tool Timeout: {tool_name}",
            description=f"Make tool '{tool_name}' timeout {timeout_rate*100}% of the time",
            hypothesis="Agent should gracefully handle tool failure, not loop, and provide partial answer",
            blast_radius=BlastRadiusLevel.MINIMAL,
            target_traffic_pct=2.0,
            target_environment="canary",
            duration_seconds=300,
            chaos_actions=[
                {"action": "inject", "fn": inject_timeout},
                {"action": "cleanup", "fn": remove_timeout},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="no_agent_loops",
                    description="No agent exceeds 10 steps (normally max 20, but should give up earlier)",
                    metric="max_agent_steps",
                    operator="<=",
                    threshold=10,
                    measurement_fn=lambda: random.randint(3, 8),
                ),
                SteadyStateHypothesis(
                    name="cost_per_request",
                    description="Cost per request stays under $0.50",
                    metric="cost_per_request_p95",
                    operator="<=",
                    threshold=0.50,
                    measurement_fn=lambda: random.uniform(0.05, 0.30),
                ),
            ],
            tags=["tool", "timeout", "agent_behavior"],
        )
    
    def create_embedding_service_failure(self) -> ChaosExperiment:
        """
        Scenario: Embedding service is down (can't embed queries for retrieval).
        
        Tests: System handles inability to embed queries, falls back appropriately.
        """
        def inject_failure():
            self._active_injections["embedding_service"] = {
                "status": "down",
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning("CHAOS: Embedding service failure injected")
        
        def remove_failure():
            if "embedding_service" in self._active_injections:
                del self._active_injections["embedding_service"]
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name="Embedding Service Failure",
            description="Simulate complete embedding service outage",
            hypothesis="System should detect embedding failure and fall back to keyword search or parametric knowledge",
            blast_radius=BlastRadiusLevel.LOW,
            target_traffic_pct=5.0,
            target_environment="staging",
            duration_seconds=300,
            chaos_actions=[
                {"action": "inject", "fn": inject_failure},
                {"action": "cleanup", "fn": remove_failure},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="availability",
                    description="System remains available (answers from parametric knowledge)",
                    metric="availability_rate",
                    operator=">=",
                    threshold=0.90,
                    measurement_fn=lambda: random.uniform(0.88, 0.98),
                ),
            ],
            tags=["embedding", "retrieval", "fallback"],
        )
    
    def create_prompt_corruption(self) -> ChaosExperiment:
        """
        Scenario: System prompt becomes corrupted (simulating bad deployment or cache corruption).
        
        Tests: Output quality monitoring catches degradation, alerts fire.
        """
        def inject_corruption():
            self._active_injections["prompt_corruption"] = {
                "type": "truncated_system_prompt",
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning("CHAOS: Prompt corruption injected (truncated system prompt)")
        
        def remove_corruption():
            if "prompt_corruption" in self._active_injections:
                del self._active_injections["prompt_corruption"]
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name="Prompt Corruption",
            description="Simulate system prompt corruption (truncation, encoding error)",
            hypothesis="Quality monitoring should detect degradation within 5 minutes and alert",
            blast_radius=BlastRadiusLevel.MINIMAL,
            target_traffic_pct=1.0,
            target_environment="canary",
            duration_seconds=600,
            chaos_actions=[
                {"action": "inject", "fn": inject_corruption},
                {"action": "cleanup", "fn": remove_corruption},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="quality_detection",
                    description="Quality monitoring detects degradation",
                    metric="quality_alert_fired",
                    operator=">=",
                    threshold=1.0,
                    measurement_fn=lambda: 1.0,  # Check if alert fired
                ),
            ],
            tags=["prompt", "quality", "detection"],
        )
    
    def create_high_load(self, multiplier: float = 10.0) -> ChaosExperiment:
        """
        Scenario: Traffic spikes to 10x normal.
        
        Tests: Rate limiting, queue management, graceful degradation under load.
        """
        def inject_load():
            self._active_injections["high_load"] = {
                "multiplier": multiplier,
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning(f"CHAOS: {multiplier}x traffic load injected")
        
        def remove_load():
            if "high_load" in self._active_injections:
                del self._active_injections["high_load"]
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name=f"High Load ({multiplier}x)",
            description=f"Simulate {multiplier}x traffic spike",
            hypothesis="System should shed load gracefully, prioritize existing requests, maintain quality for served requests",
            blast_radius=BlastRadiusLevel.MEDIUM,
            target_traffic_pct=100.0,  # Load test affects the whole system
            target_environment="staging",
            duration_seconds=600,
            chaos_actions=[
                {"action": "inject", "fn": inject_load},
                {"action": "cleanup", "fn": remove_load},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="served_request_quality",
                    description="Requests that ARE served maintain quality",
                    metric="served_quality_score",
                    operator=">=",
                    threshold=0.80,
                    measurement_fn=lambda: random.uniform(0.75, 0.90),
                ),
                SteadyStateHypothesis(
                    name="no_cascading_failure",
                    description="System doesn't crash entirely",
                    metric="system_alive",
                    operator=">=",
                    threshold=1.0,
                    measurement_fn=lambda: 1.0,
                ),
            ],
            tags=["load", "scaling", "rate_limiting"],
        )
    
    def create_cache_invalidation_storm(self) -> ChaosExperiment:
        """
        Scenario: All caches are simultaneously invalidated (cold start).
        
        Tests: System handles cache miss thundering herd, doesn't overwhelm backends.
        """
        def invalidate_caches():
            self._active_injections["cache_storm"] = {
                "type": "full_invalidation",
                "started": datetime.utcnow().isoformat(),
            }
            logger.warning("CHAOS: Full cache invalidation - simulating thundering herd")
        
        def restore_caches():
            if "cache_storm" in self._active_injections:
                del self._active_injections["cache_storm"]
        
        return ChaosExperiment(
            id=f"chaos-{uuid.uuid4().hex[:8]}",
            name="Cache Invalidation Storm",
            description="Invalidate all caches simultaneously, simulating thundering herd",
            hypothesis="System should handle cold start without overwhelming model provider or vector DB",
            blast_radius=BlastRadiusLevel.MEDIUM,
            target_traffic_pct=100.0,
            target_environment="staging",
            duration_seconds=300,
            chaos_actions=[
                {"action": "inject", "fn": invalidate_caches},
                {"action": "cleanup", "fn": restore_caches},
            ],
            steady_state_checks=[
                SteadyStateHypothesis(
                    name="backend_not_overwhelmed",
                    description="Model provider rate limits not exhausted",
                    metric="rate_limit_remaining_pct",
                    operator=">=",
                    threshold=0.10,
                    measurement_fn=lambda: random.uniform(0.15, 0.50),
                ),
            ],
            tags=["cache", "thundering_herd", "cold_start"],
        )
    
    def is_injection_active(self, injection_name: str) -> bool:
        """Check if a specific injection is active (used by system under test)."""
        return injection_name in self._active_injections
    
    def get_active_injections(self) -> dict:
        """Get all active chaos injections."""
        return dict(self._active_injections)


# =============================================================================
# CHAOS EXECUTION ENGINE
# =============================================================================

class ChaosExecutionEngine:
    """Executes chaos experiments with safety controls."""
    
    def __init__(self, scenarios: AIChaosScenarios):
        self._scenarios = scenarios
        self._experiments: list[ChaosExperiment] = []
        self._kill_switch = threading.Event()  # Set to abort ALL experiments
        self._running_experiment: Optional[ChaosExperiment] = None
        self._abort_check_interval = 5  # seconds
    
    def run_experiment(self, experiment: ChaosExperiment) -> dict:
        """
        Execute a chaos experiment with full lifecycle.
        
        Lifecycle:
        1. Verify steady state (pre-check)
        2. Inject chaos
        3. Monitor + check abort conditions
        4. Remove chaos (cleanup)
        5. Verify steady state (post-check)
        6. Record results
        """
        if experiment.requires_approval and not experiment.approved_by:
            raise RuntimeError("Experiment requires approval before execution")
        
        if self._running_experiment:
            raise RuntimeError("Another experiment is already running")
        
        self._running_experiment = experiment
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()
        
        results = {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "started_at": experiment.started_at.isoformat(),
            "phases": [],
        }
        
        try:
            # Phase 1: Verify steady state
            phase1 = self._verify_steady_state(experiment, "pre")
            results["phases"].append({"phase": "pre_steady_state", **phase1})
            
            if not phase1["passed"]:
                experiment.status = ExperimentStatus.FAILED
                experiment.observations.append("Pre-experiment steady state check failed - system already unhealthy")
                results["outcome"] = "failed_pre_check"
                return results
            
            experiment.pre_experiment_state = phase1
            
            # Phase 2: Inject chaos
            logger.info(f"CHAOS: Injecting chaos for experiment '{experiment.name}'")
            inject_results = self._inject_chaos(experiment)
            results["phases"].append({"phase": "injection", "results": inject_results})
            
            # Phase 3: Monitor during experiment
            monitor_result = self._monitor_experiment(experiment)
            results["phases"].append({"phase": "monitoring", **monitor_result})
            
            if monitor_result.get("aborted"):
                experiment.status = ExperimentStatus.ABORTED
                experiment.observations.append(f"Experiment aborted: {monitor_result.get('abort_reason')}")
                results["outcome"] = "aborted"
            else:
                experiment.status = ExperimentStatus.COMPLETED
                results["outcome"] = "completed"
            
        except Exception as e:
            experiment.status = ExperimentStatus.FAILED
            experiment.observations.append(f"Experiment error: {str(e)}")
            results["outcome"] = "error"
            results["error"] = str(e)
            logger.error(f"Chaos experiment failed: {e}")
        
        finally:
            # Phase 4: Always cleanup
            cleanup_results = self._cleanup_chaos(experiment)
            results["phases"].append({"phase": "cleanup", "results": cleanup_results})
            
            # Phase 5: Post-experiment steady state
            phase5 = self._verify_steady_state(experiment, "post")
            results["phases"].append({"phase": "post_steady_state", **phase5})
            experiment.post_experiment_state = phase5
            
            experiment.completed_at = datetime.utcnow()
            experiment.results = results
            self._running_experiment = None
            self._experiments.append(experiment)
        
        # Generate summary
        results["summary"] = self._generate_summary(experiment)
        return results
    
    def _verify_steady_state(self, experiment: ChaosExperiment, phase: str) -> dict:
        """Verify all steady state hypotheses."""
        results = {"phase": phase, "checks": [], "passed": True}
        
        for check in experiment.steady_state_checks:
            try:
                measured = check.measurement_fn()
                passed = self._evaluate_condition(measured, check.operator, check.threshold)
                
                results["checks"].append({
                    "name": check.name,
                    "metric": check.metric,
                    "measured": measured,
                    "threshold": check.threshold,
                    "operator": check.operator,
                    "passed": passed,
                })
                
                if not passed:
                    results["passed"] = False
                    
            except Exception as e:
                results["checks"].append({
                    "name": check.name,
                    "error": str(e),
                    "passed": False,
                })
                results["passed"] = False
        
        return results
    
    def _inject_chaos(self, experiment: ChaosExperiment) -> list:
        """Execute chaos injection actions."""
        results = []
        for action in experiment.chaos_actions:
            if action["action"] == "inject":
                try:
                    result = action["fn"]()
                    results.append({"action": "inject", "success": True, "result": str(result)})
                except Exception as e:
                    results.append({"action": "inject", "success": False, "error": str(e)})
        return results
    
    def _cleanup_chaos(self, experiment: ChaosExperiment) -> list:
        """Execute chaos cleanup actions."""
        results = []
        for action in experiment.chaos_actions:
            if action["action"] == "cleanup":
                try:
                    action["fn"]()
                    results.append({"action": "cleanup", "success": True})
                except Exception as e:
                    results.append({"action": "cleanup", "success": False, "error": str(e)})
                    logger.error(f"CHAOS CLEANUP FAILED: {e} - MANUAL INTERVENTION NEEDED")
        return results
    
    def _monitor_experiment(self, experiment: ChaosExperiment) -> dict:
        """Monitor experiment duration, checking abort conditions periodically."""
        start = time.time()
        elapsed = 0
        measurements = []
        
        while elapsed < experiment.duration_seconds:
            # Check kill switch
            if self._kill_switch.is_set():
                return {"aborted": True, "abort_reason": "Kill switch activated",
                        "measurements": measurements, "elapsed_seconds": elapsed}
            
            # Check abort conditions
            for condition in experiment.abort_conditions:
                try:
                    if condition():
                        return {"aborted": True, "abort_reason": "Abort condition met",
                                "measurements": measurements, "elapsed_seconds": elapsed}
                except Exception:
                    pass
            
            # Check impact thresholds
            for check in experiment.steady_state_checks:
                try:
                    measured = check.measurement_fn()
                    measurements.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "metric": check.metric,
                        "value": measured,
                    })
                    
                    # Check max impact threshold
                    max_threshold = experiment.max_impact_threshold.get(check.metric)
                    if max_threshold:
                        if check.operator in (">=", ">"):
                            if measured < check.threshold * (1 - max_threshold):
                                return {"aborted": True, 
                                        "abort_reason": f"Max impact exceeded for {check.metric}",
                                        "measurements": measurements, "elapsed_seconds": elapsed}
                except Exception:
                    pass
            
            # Sleep until next check
            time.sleep(min(self._abort_check_interval, experiment.duration_seconds - elapsed))
            elapsed = time.time() - start
        
        return {"aborted": False, "measurements": measurements, "elapsed_seconds": elapsed}
    
    def _evaluate_condition(self, measured: float, operator: str, threshold: float) -> bool:
        ops = {
            ">=": lambda m, t: m >= t,
            "<=": lambda m, t: m <= t,
            ">": lambda m, t: m > t,
            "<": lambda m, t: m < t,
            "==": lambda m, t: abs(m - t) < 0.001,
        }
        return ops.get(operator, lambda m, t: False)(measured, threshold)
    
    def _generate_summary(self, experiment: ChaosExperiment) -> dict:
        """Generate experiment summary."""
        pre_passed = experiment.pre_experiment_state.get("passed", False)
        post_passed = experiment.post_experiment_state.get("passed", False)
        
        if experiment.status == ExperimentStatus.ABORTED:
            conclusion = "ABORTED - System did not handle chaos within safety bounds"
        elif not post_passed:
            conclusion = "CONCERN - System did not fully recover after chaos removed"
        elif experiment.status == ExperimentStatus.COMPLETED:
            conclusion = "SUCCESS - System handled chaos within acceptable bounds"
        else:
            conclusion = "FAILED - Experiment encountered an error"
        
        return {
            "conclusion": conclusion,
            "hypothesis_validated": experiment.status == ExperimentStatus.COMPLETED and post_passed,
            "pre_state_healthy": pre_passed,
            "post_state_healthy": post_passed,
            "duration_seconds": (experiment.completed_at - experiment.started_at).total_seconds() if experiment.completed_at and experiment.started_at else 0,
            "observations": experiment.observations,
        }
    
    def activate_kill_switch(self):
        """Emergency: stop all experiments immediately."""
        logger.critical("CHAOS KILL SWITCH ACTIVATED - Stopping all experiments")
        self._kill_switch.set()
        # Cleanup any active injections
        if self._running_experiment:
            self._cleanup_chaos(self._running_experiment)
    
    def reset_kill_switch(self):
        """Reset kill switch after emergency is resolved."""
        self._kill_switch.clear()
        logger.info("Chaos kill switch reset")


# =============================================================================
# CHAOS CALENDAR MANAGEMENT
# =============================================================================

@dataclass
class ChaosScheduleEntry:
    experiment_id: str
    experiment_name: str
    scheduled_date: datetime
    environment: str
    owner: str
    approved: bool = False
    executed: bool = False
    result: Optional[str] = None


class ChaosCalendar:
    """Manages the schedule of chaos experiments."""
    
    def __init__(self):
        self._schedule: list[ChaosScheduleEntry] = []
        self._blackout_periods: list[tuple[datetime, datetime]] = []  # No chaos during these
        self._execution_history: list[dict] = []
    
    def schedule_experiment(self, experiment: ChaosExperiment, 
                           scheduled_date: datetime) -> ChaosScheduleEntry:
        """Schedule a chaos experiment for a specific date."""
        # Check blackout periods
        for start, end in self._blackout_periods:
            if start <= scheduled_date <= end:
                raise ValueError(
                    f"Cannot schedule during blackout period: {start.isoformat()} to {end.isoformat()}"
                )
        
        entry = ChaosScheduleEntry(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            scheduled_date=scheduled_date,
            environment=experiment.target_environment,
            owner=experiment.owner,
        )
        self._schedule.append(entry)
        self._schedule.sort(key=lambda e: e.scheduled_date)
        
        logger.info(f"Chaos experiment scheduled: '{experiment.name}' for {scheduled_date.isoformat()}")
        return entry
    
    def add_blackout_period(self, start: datetime, end: datetime, reason: str):
        """Add a period during which no chaos experiments should run."""
        self._blackout_periods.append((start, end))
        logger.info(f"Blackout period added: {start.isoformat()} to {end.isoformat()} ({reason})")
    
    def get_upcoming(self, days: int = 7) -> list[ChaosScheduleEntry]:
        """Get experiments scheduled in the next N days."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        return [e for e in self._schedule 
                if not e.executed and e.scheduled_date <= cutoff]
    
    def get_due_experiments(self) -> list[ChaosScheduleEntry]:
        """Get experiments that are due to run now."""
        now = datetime.utcnow()
        return [e for e in self._schedule 
                if not e.executed and e.scheduled_date <= now and e.approved]
    
    def get_monthly_report(self) -> dict:
        """Generate monthly chaos engineering report."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        
        month_entries = [e for e in self._schedule if e.scheduled_date >= month_start]
        executed = [e for e in month_entries if e.executed]
        
        return {
            "month": now.strftime("%Y-%m"),
            "total_scheduled": len(month_entries),
            "total_executed": len(executed),
            "results": {
                "success": sum(1 for e in executed if e.result == "success"),
                "aborted": sum(1 for e in executed if e.result == "aborted"),
                "failed": sum(1 for e in executed if e.result == "failed"),
            },
            "coverage": {
                "scenarios_tested": list(set(e.experiment_name for e in executed)),
                "environments_tested": list(set(e.environment for e in executed)),
            },
            "upcoming": [
                {"name": e.experiment_name, "date": e.scheduled_date.isoformat(), "approved": e.approved}
                for e in self.get_upcoming(30)
            ],
        }


# =============================================================================
# COMPLETE CHAOS ENGINEERING SYSTEM
# =============================================================================

class AIChaosEngineeringSystem:
    """
    Complete chaos engineering system for AI applications.
    
    Manages experiment lifecycle from definition through execution to reporting.
    """
    
    def __init__(self):
        self.scenarios = AIChaosScenarios()
        self.engine = ChaosExecutionEngine(self.scenarios)
        self.calendar = ChaosCalendar()
        self._experiment_registry: dict[str, ChaosExperiment] = {}
    
    def create_standard_experiments(self) -> list[ChaosExperiment]:
        """Create all standard chaos experiments."""
        experiments = [
            self.scenarios.create_model_provider_failure("500", 1.0),
            self.scenarios.create_model_provider_failure("timeout", 0.5),
            self.scenarios.create_vector_db_latency(5000),
            self.scenarios.create_vector_db_latency(15000),
            self.scenarios.create_tool_timeout("database_query", 0.8),
            self.scenarios.create_tool_timeout("web_search", 1.0),
            self.scenarios.create_embedding_service_failure(),
            self.scenarios.create_prompt_corruption(),
            self.scenarios.create_high_load(5.0),
            self.scenarios.create_high_load(10.0),
            self.scenarios.create_cache_invalidation_storm(),
        ]
        
        for exp in experiments:
            self._experiment_registry[exp.id] = exp
        
        return experiments
    
    def approve_experiment(self, experiment_id: str, approver: str):
        """Approve an experiment for execution."""
        exp = self._experiment_registry.get(experiment_id)
        if not exp:
            raise ValueError(f"Unknown experiment: {experiment_id}")
        exp.approved_by = approver
        exp.status = ExperimentStatus.APPROVED
        logger.info(f"Experiment '{exp.name}' approved by {approver}")
    
    def run(self, experiment_id: str) -> dict:
        """Run a specific experiment."""
        exp = self._experiment_registry.get(experiment_id)
        if not exp:
            raise ValueError(f"Unknown experiment: {experiment_id}")
        return self.engine.run_experiment(exp)
    
    def emergency_stop(self):
        """Emergency stop all chaos activity."""
        self.engine.activate_kill_switch()
        logger.critical("ALL CHAOS STOPPED - Kill switch activated")
    
    def get_status(self) -> dict:
        """Get current chaos engineering system status."""
        return {
            "kill_switch_active": self.engine._kill_switch.is_set(),
            "active_injections": self.scenarios.get_active_injections(),
            "running_experiment": self.engine._running_experiment.name if self.engine._running_experiment else None,
            "total_experiments": len(self._experiment_registry),
            "upcoming_scheduled": len(self.calendar.get_upcoming()),
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    system = AIChaosEngineeringSystem()
    
    # Create standard experiments
    experiments = system.create_standard_experiments()
    print(f"Created {len(experiments)} chaos experiments:")
    for exp in experiments:
        print(f"  - {exp.name} [{exp.blast_radius.value}] ({exp.duration_seconds}s)")
    
    # Approve and run one
    exp = experiments[0]  # Model provider failure
    system.approve_experiment(exp.id, "sre-lead")
    
    print(f"\n=== Running: {exp.name} ===")
    print(f"Hypothesis: {exp.hypothesis}")
    print(f"Blast radius: {exp.blast_radius.value}")
    print(f"Duration: {exp.duration_seconds}s")
    
    # Override duration for demo
    exp.duration_seconds = 10
    
    results = system.run(exp.id)
    
    print(f"\n=== Results ===")
    print(f"Outcome: {results['outcome']}")
    print(f"Summary: {json.dumps(results['summary'], indent=2)}")
    
    # Show phases
    for phase in results["phases"]:
        print(f"\n  Phase: {phase['phase']}")
        if "passed" in phase:
            print(f"    Passed: {phase['passed']}")
        if "checks" in phase:
            for check in phase["checks"]:
                status = "PASS" if check.get("passed") else "FAIL"
                print(f"    [{status}] {check.get('name')}: {check.get('measured', 'N/A')} "
                      f"{check.get('operator', '')} {check.get('threshold', '')}")
    
    # Schedule future experiments
    print("\n=== Scheduling Chaos Calendar ===")
    now = datetime.utcnow()
    for i, exp in enumerate(experiments[:5]):
        scheduled = now + timedelta(days=i + 1)
        entry = system.calendar.schedule_experiment(exp, scheduled)
        print(f"  Scheduled: {exp.name} for {scheduled.strftime('%Y-%m-%d')}")
    
    # Add blackout (e.g., during product launch)
    system.calendar.add_blackout_period(
        now + timedelta(days=10),
        now + timedelta(days=12),
        "Product launch window"
    )
    
    # Monthly report
    print("\n=== Monthly Report ===")
    report = system.calendar.get_monthly_report()
    print(json.dumps(report, indent=2, default=str))
    
    # System status
    print("\n=== System Status ===")
    print(json.dumps(system.get_status(), indent=2))
