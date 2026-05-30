"""
Backpressure and Degraded Modes for AI Systems.

Implements load detection, backpressure signal propagation, graceful degradation
levels, circuit breakers, rate limiting, and automatic recovery.
"""

from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Degradation Levels
# ---------------------------------------------------------------------------

class DegradationLevel(IntEnum):
    FULL = 0        # All features active
    REDUCED = 1     # Disable non-essential features
    MINIMAL = 2     # Single model call, cached only
    ERROR = 3       # Return errors or cached fallbacks


@dataclass
class LevelBehavior:
    """Defines system behavior at each degradation level."""

    level: DegradationLevel
    max_agent_steps: int
    enable_retrieval: bool
    enable_reranking: bool
    enable_tools: bool
    enable_eval_sampling: bool
    enable_memory_writes: bool
    model_tier: str  # fast, standard, premium
    cache_only_retrieval: bool
    max_concurrent_requests: int
    description: str


LEVEL_BEHAVIORS: dict[DegradationLevel, LevelBehavior] = {
    DegradationLevel.FULL: LevelBehavior(
        level=DegradationLevel.FULL,
        max_agent_steps=10,
        enable_retrieval=True,
        enable_reranking=True,
        enable_tools=True,
        enable_eval_sampling=True,
        enable_memory_writes=True,
        model_tier="premium",
        cache_only_retrieval=False,
        max_concurrent_requests=1000,
        description="All features active, full quality",
    ),
    DegradationLevel.REDUCED: LevelBehavior(
        level=DegradationLevel.REDUCED,
        max_agent_steps=3,
        enable_retrieval=True,
        enable_reranking=False,
        enable_tools=True,
        enable_eval_sampling=False,
        enable_memory_writes=True,
        model_tier="standard",
        cache_only_retrieval=False,
        max_concurrent_requests=500,
        description="Reduced steps, no reranking/eval, standard model",
    ),
    DegradationLevel.MINIMAL: LevelBehavior(
        level=DegradationLevel.MINIMAL,
        max_agent_steps=1,
        enable_retrieval=True,
        enable_reranking=False,
        enable_tools=False,
        enable_eval_sampling=False,
        enable_memory_writes=False,
        model_tier="fast",
        cache_only_retrieval=True,
        max_concurrent_requests=200,
        description="Single call, cache-only retrieval, no tools",
    ),
    DegradationLevel.ERROR: LevelBehavior(
        level=DegradationLevel.ERROR,
        max_agent_steps=0,
        enable_retrieval=False,
        enable_reranking=False,
        enable_tools=False,
        enable_eval_sampling=False,
        enable_memory_writes=False,
        model_tier="none",
        cache_only_retrieval=True,
        max_concurrent_requests=50,
        description="Return cached responses or error messages only",
    ),
}


# ---------------------------------------------------------------------------
# Backpressure Signal Detection
# ---------------------------------------------------------------------------

@dataclass
class ComponentHealth:
    """Health metrics for a single component."""

    name: str
    queue_depth: int = 0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    error_rate: float = 0.0  # 0.0 to 1.0
    saturation: float = 0.0  # 0.0 to 1.0 (utilization)

    # Thresholds
    queue_depth_warn: int = 100
    queue_depth_critical: int = 1000
    latency_p99_warn_ms: float = 1000.0
    latency_p99_critical_ms: float = 5000.0
    error_rate_warn: float = 0.05
    error_rate_critical: float = 0.20
    saturation_warn: float = 0.70
    saturation_critical: float = 0.90

    def pressure_score(self) -> float:
        """Compute pressure score 0.0 (healthy) to 1.0 (critical)."""
        scores = []

        # Queue depth
        if self.queue_depth >= self.queue_depth_critical:
            scores.append(1.0)
        elif self.queue_depth >= self.queue_depth_warn:
            scores.append(0.5 + 0.5 * (self.queue_depth - self.queue_depth_warn) / (self.queue_depth_critical - self.queue_depth_warn))
        else:
            scores.append(self.queue_depth / max(self.queue_depth_warn, 1))

        # Latency
        if self.latency_p99_ms >= self.latency_p99_critical_ms:
            scores.append(1.0)
        elif self.latency_p99_ms >= self.latency_p99_warn_ms:
            scores.append(0.5 + 0.5 * (self.latency_p99_ms - self.latency_p99_warn_ms) / (self.latency_p99_critical_ms - self.latency_p99_warn_ms))
        else:
            scores.append(self.latency_p99_ms / max(self.latency_p99_warn_ms, 1))

        # Error rate
        if self.error_rate >= self.error_rate_critical:
            scores.append(1.0)
        elif self.error_rate >= self.error_rate_warn:
            scores.append(0.5 + 0.5 * (self.error_rate - self.error_rate_warn) / (self.error_rate_critical - self.error_rate_warn))
        else:
            scores.append(self.error_rate / max(self.error_rate_warn, 0.01))

        # Saturation
        if self.saturation >= self.saturation_critical:
            scores.append(1.0)
        elif self.saturation >= self.saturation_warn:
            scores.append(0.5 + 0.5 * (self.saturation - self.saturation_warn) / (self.saturation_critical - self.saturation_warn))
        else:
            scores.append(self.saturation / max(self.saturation_warn, 0.1))

        return max(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject calls
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreaker:
    """Circuit breaker for a dependency."""

    name: str
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False  # OPEN

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate  # tokens per second
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        return self._tokens


# ---------------------------------------------------------------------------
# Backpressure Controller
# ---------------------------------------------------------------------------

class BackpressureController:
    """
    Central controller that monitors component health, manages degradation
    levels, circuit breakers, and rate limiting.
    """

    def __init__(self):
        self._components: dict[str, ComponentHealth] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._rate_limiters: dict[str, TokenBucketRateLimiter] = {}
        self._current_level: DegradationLevel = DegradationLevel.FULL
        self._level_change_time: float = time.time()
        self._recovery_hold_seconds: float = 300.0  # 5 min stable before recovery
        self._history: deque[tuple[float, DegradationLevel]] = deque(maxlen=100)
        self._listeners: list[Callable[[DegradationLevel, DegradationLevel], None]] = []

    # --- Setup ---

    def register_component(self, health: ComponentHealth) -> None:
        self._components[health.name] = health
        self._circuit_breakers[health.name] = CircuitBreaker(
            name=health.name,
            failure_threshold=5,
            recovery_timeout_seconds=30.0,
        )

    def register_rate_limiter(self, name: str, rate: float, burst: int) -> None:
        self._rate_limiters[name] = TokenBucketRateLimiter(rate, burst)

    def on_level_change(self, callback: Callable[[DegradationLevel, DegradationLevel], None]) -> None:
        self._listeners.append(callback)

    # --- Health Updates ---

    def update_component(self, name: str, **kwargs) -> None:
        """Update component health metrics."""
        if name in self._components:
            for k, v in kwargs.items():
                if hasattr(self._components[name], k):
                    setattr(self._components[name], k, v)
            self._evaluate()

    # --- Core Logic ---

    def _evaluate(self) -> None:
        """Evaluate all components and determine degradation level."""
        if not self._components:
            return

        max_pressure = max(c.pressure_score() for c in self._components.values())

        # Determine target level
        if max_pressure >= 0.9:
            target = DegradationLevel.ERROR
        elif max_pressure >= 0.7:
            target = DegradationLevel.MINIMAL
        elif max_pressure >= 0.5:
            target = DegradationLevel.REDUCED
        else:
            target = DegradationLevel.FULL

        # Only degrade immediately; recover requires stability
        if target > self._current_level:
            self._set_level(target)
        elif target < self._current_level:
            # Only recover if stable for recovery_hold_seconds
            elapsed = time.time() - self._level_change_time
            if elapsed >= self._recovery_hold_seconds:
                # Step down one level at a time
                new_level = DegradationLevel(self._current_level.value - 1)
                self._set_level(new_level)

    def _set_level(self, level: DegradationLevel) -> None:
        if level != self._current_level:
            old = self._current_level
            self._current_level = level
            self._level_change_time = time.time()
            self._history.append((time.time(), level))
            for cb in self._listeners:
                cb(old, level)

    # --- Public API ---

    @property
    def current_level(self) -> DegradationLevel:
        return self._current_level

    @property
    def current_behavior(self) -> LevelBehavior:
        return LEVEL_BEHAVIORS[self._current_level]

    def should_allow_request(self, tenant_id: str, priority: int = 2) -> tuple[bool, str]:
        """Check if request should be allowed given current state."""
        behavior = self.current_behavior

        # Check rate limiter
        limiter_key = f"tenant:{tenant_id}"
        if limiter_key in self._rate_limiters:
            if not self._rate_limiters[limiter_key].allow():
                return False, "rate_limited"

        # In ERROR mode, only allow critical priority
        if self._current_level == DegradationLevel.ERROR and priority > 0:
            return False, "system_overloaded"

        # In MINIMAL, shed bulk/low priority
        if self._current_level == DegradationLevel.MINIMAL and priority >= 3:
            return False, "load_shedding"

        # In REDUCED, shed bulk
        if self._current_level == DegradationLevel.REDUCED and priority >= 4:
            return False, "load_shedding"

        return True, "allowed"

    def check_circuit(self, component: str) -> bool:
        """Check if circuit breaker allows a call to component."""
        cb = self._circuit_breakers.get(component)
        if not cb:
            return True
        return cb.allow_request()

    def record_call(self, component: str, success: bool) -> None:
        """Record a call result for circuit breaker."""
        cb = self._circuit_breakers.get(component)
        if cb:
            if success:
                cb.record_success()
            else:
                cb.record_failure()

    def get_status(self) -> dict[str, Any]:
        """Get full system status."""
        return {
            "degradation_level": self._current_level.name,
            "behavior": self.current_behavior.description,
            "level_since": self._level_change_time,
            "components": {
                name: {
                    "pressure_score": comp.pressure_score(),
                    "queue_depth": comp.queue_depth,
                    "latency_p99_ms": comp.latency_p99_ms,
                    "error_rate": comp.error_rate,
                    "saturation": comp.saturation,
                    "circuit_state": self._circuit_breakers[name].state.value,
                }
                for name, comp in self._components.items()
            },
            "recent_transitions": [
                {"time": t, "level": l.name} for t, l in list(self._history)[-10:]
            ],
        }


# ---------------------------------------------------------------------------
# Request Shedding Strategy
# ---------------------------------------------------------------------------

class RequestShedder:
    """Implements load shedding when system is overloaded."""

    def __init__(self, controller: BackpressureController):
        self.controller = controller
        self._shed_count = 0
        self._total_count = 0

    def should_shed(self, priority: int, estimated_cost: float = 1.0) -> tuple[bool, str]:
        """
        Determine if a request should be shed.
        
        Args:
            priority: 0 (critical) to 4 (bulk)
            estimated_cost: relative cost of this request
        """
        self._total_count += 1
        level = self.controller.current_level

        shed = False
        reason = ""

        if level == DegradationLevel.ERROR:
            # Only allow priority 0
            if priority > 0:
                shed = True
                reason = "error_mode_non_critical"

        elif level == DegradationLevel.MINIMAL:
            # Shed priority 3+ and expensive requests
            if priority >= 3:
                shed = True
                reason = "minimal_mode_low_priority"
            elif estimated_cost > 5.0 and priority >= 2:
                shed = True
                reason = "minimal_mode_expensive"

        elif level == DegradationLevel.REDUCED:
            # Only shed bulk and very expensive
            if priority >= 4:
                shed = True
                reason = "reduced_mode_bulk"
            elif estimated_cost > 10.0 and priority >= 3:
                shed = True
                reason = "reduced_mode_expensive"

        if shed:
            self._shed_count += 1

        return shed, reason

    @property
    def shed_rate(self) -> float:
        if self._total_count == 0:
            return 0.0
        return self._shed_count / self._total_count


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main():
    controller = BackpressureController()

    # Register components
    components = [
        ComponentHealth(name="model_provider", latency_p99_warn_ms=2000, latency_p99_critical_ms=8000),
        ComponentHealth(name="vector_db", latency_p99_warn_ms=200, latency_p99_critical_ms=1000),
        ComponentHealth(name="tool_service", error_rate_warn=0.05, error_rate_critical=0.15),
        ComponentHealth(name="queue", queue_depth_warn=500, queue_depth_critical=5000),
    ]
    for c in components:
        controller.register_component(c)

    # Register rate limiter
    controller.register_rate_limiter("tenant:acme", rate=10.0, burst=50)

    # Listener
    def on_change(old: DegradationLevel, new: DegradationLevel):
        print(f"  ** LEVEL CHANGE: {old.name} -> {new.name} **")

    controller.on_level_change(on_change)

    shedder = RequestShedder(controller)

    print("=" * 60)
    print("BACKPRESSURE AND DEGRADATION DEMO")
    print("=" * 60)

    # Simulate increasing load
    scenarios = [
        ("Normal operation", {"model_provider": {"latency_p99_ms": 500, "error_rate": 0.01}}),
        ("Model getting slow", {"model_provider": {"latency_p99_ms": 3000, "error_rate": 0.03}}),
        ("Model degraded", {"model_provider": {"latency_p99_ms": 6000, "error_rate": 0.10}}),
        ("Multiple failures", {"model_provider": {"latency_p99_ms": 9000, "error_rate": 0.25}, "vector_db": {"latency_p99_ms": 800}}),
    ]

    for scenario_name, updates in scenarios:
        print(f"\n--- Scenario: {scenario_name} ---")
        for component, metrics in updates.items():
            controller.update_component(component, **metrics)

        status = controller.get_status()
        print(f"  Level: {status['degradation_level']}")
        print(f"  Behavior: {status['behavior']}")

        # Test request shedding
        for priority in [0, 1, 2, 3, 4]:
            shed, reason = shedder.should_shed(priority)
            allowed, allow_reason = controller.should_allow_request("acme", priority)
            if shed or not allowed:
                print(f"  Priority {priority}: SHED ({reason or allow_reason})")

    print(f"\n  Total shed rate: {shedder.shed_rate:.1%}")


if __name__ == "__main__":
    main()
