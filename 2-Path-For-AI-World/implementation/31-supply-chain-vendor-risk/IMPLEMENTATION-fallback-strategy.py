"""
Provider Fallback Strategy System
====================================
Multi-provider failover, health checking, degraded mode management,
and automatic recovery for AI system resilience.
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FailoverReason(Enum):
    HEALTH_CHECK_FAILED = "health_check_failed"
    LATENCY_EXCEEDED = "latency_exceeded"
    ERROR_RATE_EXCEEDED = "error_rate_exceeded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    SCHEDULED_DRILL = "scheduled_drill"


class DegradedModeLevel(Enum):
    NONE = "none"                # Full capability
    MINOR = "minor"              # Slightly reduced quality
    MODERATE = "moderate"        # Noticeable quality reduction
    SEVERE = "severe"            # Major feature loss
    EMERGENCY = "emergency"      # Minimal viable service only


class Capability(Enum):
    CHAT_COMPLETION = "chat_completion"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    RERANKING = "reranking"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    LONG_CONTEXT = "long_context"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class HealthCheckResult:
    provider_id: str
    timestamp: datetime
    status: ProviderStatus
    latency_ms: float
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class ProviderConfig:
    id: str
    name: str
    priority: int  # Lower = higher priority (1 = primary)
    capabilities: set[Capability]
    max_latency_ms: float
    max_error_rate: float
    rate_limit_rpm: int
    cost_per_1k_tokens: float
    health_check_endpoint: str
    health_check_interval_seconds: int = 30
    max_consecutive_failures: int = 3
    cooldown_seconds: int = 60  # Time before retrying after failure
    weight: float = 1.0  # For weighted load balancing
    region: str = "us-east-1"
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderState:
    config: ProviderConfig
    status: ProviderStatus = ProviderStatus.UNKNOWN
    consecutive_failures: int = 0
    last_health_check: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    is_primary: bool = False
    in_cooldown: bool = False
    cooldown_until: Optional[datetime] = None


@dataclass
class FailoverEvent:
    id: str
    timestamp: datetime
    from_provider: str
    to_provider: str
    reason: FailoverReason
    automatic: bool
    degraded_mode: DegradedModeLevel
    capabilities_lost: list[Capability] = field(default_factory=list)
    recovery_time: Optional[datetime] = None


@dataclass
class FallbackDrillResult:
    id: str
    timestamp: datetime
    provider_disabled: str
    fallback_provider: str
    success: bool
    latency_impact_pct: float
    cost_impact_pct: float
    capabilities_verified: list[Capability]
    capabilities_failed: list[Capability]
    notes: str = ""


@dataclass
class DegradedModeConfig:
    level: DegradedModeLevel
    description: str
    disabled_features: list[str]
    quality_impact: str
    user_notification: str
    max_duration_minutes: int


# =============================================================================
# Health Checker
# =============================================================================

class HealthChecker:
    """Performs health checks against providers."""

    def __init__(self):
        self._check_functions: dict[str, Callable] = {}

    def register_check(self, provider_id: str, check_fn: Callable) -> None:
        """Register a health check function for a provider."""
        self._check_functions[provider_id] = check_fn

    async def check_health(self, provider: ProviderConfig) -> HealthCheckResult:
        """Execute health check for a provider."""
        start_time = time.time()
        try:
            check_fn = self._check_functions.get(provider.id)
            if check_fn:
                result = await check_fn()
                latency = (time.time() - start_time) * 1000

                if latency > provider.max_latency_ms:
                    status = ProviderStatus.DEGRADED
                else:
                    status = ProviderStatus.HEALTHY

                return HealthCheckResult(
                    provider_id=provider.id,
                    timestamp=datetime.utcnow(),
                    status=status,
                    latency_ms=latency,
                    details=result if isinstance(result, dict) else {},
                )
            else:
                # Simulate health check
                latency = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    provider_id=provider.id,
                    timestamp=datetime.utcnow(),
                    status=ProviderStatus.HEALTHY,
                    latency_ms=latency,
                )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheckResult(
                provider_id=provider.id,
                timestamp=datetime.utcnow(),
                status=ProviderStatus.UNHEALTHY,
                latency_ms=latency,
                error=str(e),
            )


# =============================================================================
# Fallback Strategy Engine
# =============================================================================

class FallbackStrategy(ABC):
    """Base class for fallback selection strategies."""

    @abstractmethod
    def select_provider(self, providers: list[ProviderState], required_capabilities: set[Capability]) -> Optional[ProviderState]:
        ...


class PriorityFallback(FallbackStrategy):
    """Select the highest-priority healthy provider."""

    def select_provider(self, providers: list[ProviderState], required_capabilities: set[Capability]) -> Optional[ProviderState]:
        eligible = [
            p for p in providers
            if p.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
            and not p.in_cooldown
            and required_capabilities.issubset(p.config.capabilities)
        ]
        if not eligible:
            # Try without capability filter for degraded mode
            eligible = [
                p for p in providers
                if p.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
                and not p.in_cooldown
            ]
        return min(eligible, key=lambda p: p.config.priority) if eligible else None


class WeightedFallback(FallbackStrategy):
    """Select provider based on weighted random selection among healthy providers."""

    def select_provider(self, providers: list[ProviderState], required_capabilities: set[Capability]) -> Optional[ProviderState]:
        eligible = [
            p for p in providers
            if p.status == ProviderStatus.HEALTHY
            and not p.in_cooldown
            and required_capabilities.issubset(p.config.capabilities)
        ]
        if not eligible:
            return PriorityFallback().select_provider(providers, required_capabilities)

        weights = [p.config.weight for p in eligible]
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0
        for p, w in zip(eligible, weights):
            cumulative += w
            if r <= cumulative:
                return p
        return eligible[-1]


class LowestCostFallback(FallbackStrategy):
    """Select the cheapest healthy provider that meets capability requirements."""

    def select_provider(self, providers: list[ProviderState], required_capabilities: set[Capability]) -> Optional[ProviderState]:
        eligible = [
            p for p in providers
            if p.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
            and not p.in_cooldown
            and required_capabilities.issubset(p.config.capabilities)
        ]
        return min(eligible, key=lambda p: p.config.cost_per_1k_tokens) if eligible else None


class LowestLatencyFallback(FallbackStrategy):
    """Select provider with lowest observed latency."""

    def select_provider(self, providers: list[ProviderState], required_capabilities: set[Capability]) -> Optional[ProviderState]:
        eligible = [
            p for p in providers
            if p.status == ProviderStatus.HEALTHY
            and not p.in_cooldown
            and required_capabilities.issubset(p.config.capabilities)
        ]
        return min(eligible, key=lambda p: p.avg_latency_ms) if eligible else None


# =============================================================================
# Provider Fallback Manager
# =============================================================================

class ProviderFallbackManager:
    """
    Manages multi-provider failover with health checking,
    automatic failover, degraded modes, and recovery.
    """

    def __init__(self, strategy: FallbackStrategy = None):
        self._providers: dict[str, ProviderState] = {}
        self._strategy = strategy or PriorityFallback()
        self._health_checker = HealthChecker()
        self._failover_history: list[FailoverEvent] = []
        self._drill_history: list[FallbackDrillResult] = []
        self._current_degraded_mode = DegradedModeLevel.NONE
        self._degraded_mode_configs: dict[DegradedModeLevel, DegradedModeConfig] = {}
        self._active_provider_id: Optional[str] = None
        self._recovery_callbacks: list[Callable] = []
        self._failover_callbacks: list[Callable] = []

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def add_provider(self, config: ProviderConfig) -> None:
        """Add a provider to the fallback pool."""
        state = ProviderState(config=config, is_primary=(config.priority == 1))
        self._providers[config.id] = state
        if state.is_primary:
            self._active_provider_id = config.id
        logger.info(f"Added provider: {config.name} (priority={config.priority})")

    def configure_degraded_mode(self, config: DegradedModeConfig) -> None:
        """Configure a degraded mode level."""
        self._degraded_mode_configs[config.level] = config

    def on_failover(self, callback: Callable) -> None:
        self._failover_callbacks.append(callback)

    def on_recovery(self, callback: Callable) -> None:
        self._recovery_callbacks.append(callback)

    # -------------------------------------------------------------------------
    # Health Checking
    # -------------------------------------------------------------------------

    async def run_health_checks(self) -> dict[str, HealthCheckResult]:
        """Run health checks on all providers."""
        results = {}
        for provider_id, state in self._providers.items():
            result = await self._health_checker.check_health(state.config)
            results[provider_id] = result
            self._update_provider_state(state, result)
        return results

    def _update_provider_state(self, state: ProviderState, result: HealthCheckResult) -> None:
        state.last_health_check = result.timestamp
        previous_status = state.status

        if result.status == ProviderStatus.HEALTHY:
            state.consecutive_failures = 0
            state.last_success = result.timestamp
            state.status = ProviderStatus.HEALTHY
            state.in_cooldown = False
            # Update rolling average latency
            if state.total_requests > 0:
                state.avg_latency_ms = (state.avg_latency_ms * 0.9) + (result.latency_ms * 0.1)
            else:
                state.avg_latency_ms = result.latency_ms
            state.total_requests += 1
        elif result.status == ProviderStatus.DEGRADED:
            state.status = ProviderStatus.DEGRADED
            state.avg_latency_ms = (state.avg_latency_ms * 0.9) + (result.latency_ms * 0.1)
        else:
            state.consecutive_failures += 1
            state.last_failure = result.timestamp
            state.total_errors += 1

            if state.consecutive_failures >= state.config.max_consecutive_failures:
                state.status = ProviderStatus.UNHEALTHY
                state.in_cooldown = True
                state.cooldown_until = datetime.utcnow() + timedelta(seconds=state.config.cooldown_seconds)
                logger.error(f"Provider {state.config.name} marked UNHEALTHY after "
                           f"{state.consecutive_failures} consecutive failures")

        # Trigger failover if active provider went unhealthy
        if (state.config.id == self._active_provider_id
                and state.status == ProviderStatus.UNHEALTHY
                and previous_status != ProviderStatus.UNHEALTHY):
            self._trigger_failover(state, FailoverReason.HEALTH_CHECK_FAILED)

        # Trigger recovery if primary came back healthy
        if (state.is_primary
                and state.status == ProviderStatus.HEALTHY
                and previous_status == ProviderStatus.UNHEALTHY
                and self._active_provider_id != state.config.id):
            self._trigger_recovery(state)

    # -------------------------------------------------------------------------
    # Failover Logic
    # -------------------------------------------------------------------------

    def _trigger_failover(self, failed_provider: ProviderState, reason: FailoverReason) -> None:
        """Execute automatic failover."""
        required_caps = failed_provider.config.capabilities
        available = [s for s in self._providers.values() if s.config.id != failed_provider.config.id]
        selected = self._strategy.select_provider(available, required_caps)

        if not selected:
            logger.critical(f"NO FALLBACK AVAILABLE! All providers are unhealthy.")
            self._current_degraded_mode = DegradedModeLevel.EMERGENCY
            return

        # Determine capability loss
        lost_capabilities = required_caps - selected.config.capabilities
        degraded_level = DegradedModeLevel.NONE
        if lost_capabilities:
            if len(lost_capabilities) > 3:
                degraded_level = DegradedModeLevel.SEVERE
            elif len(lost_capabilities) > 1:
                degraded_level = DegradedModeLevel.MODERATE
            else:
                degraded_level = DegradedModeLevel.MINOR

        event = FailoverEvent(
            id=f"FO-{uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            from_provider=failed_provider.config.id,
            to_provider=selected.config.id,
            reason=reason,
            automatic=True,
            degraded_mode=degraded_level,
            capabilities_lost=list(lost_capabilities),
        )
        self._failover_history.append(event)
        self._active_provider_id = selected.config.id
        self._current_degraded_mode = degraded_level

        logger.warning(
            f"FAILOVER: {failed_provider.config.name} -> {selected.config.name} "
            f"(reason={reason.value}, degraded={degraded_level.value})"
        )

        for cb in self._failover_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Failover callback error: {e}")

    def _trigger_recovery(self, recovered_provider: ProviderState) -> None:
        """Recover to primary provider."""
        previous_active = self._active_provider_id
        self._active_provider_id = recovered_provider.config.id
        self._current_degraded_mode = DegradedModeLevel.NONE

        # Update last failover event with recovery time
        if self._failover_history:
            last_event = self._failover_history[-1]
            if last_event.from_provider == recovered_provider.config.id:
                last_event.recovery_time = datetime.utcnow()

        logger.info(f"RECOVERY: Restored to primary provider {recovered_provider.config.name}")

        for cb in self._recovery_callbacks:
            try:
                cb(recovered_provider.config.id, previous_active)
            except Exception as e:
                logger.error(f"Recovery callback error: {e}")

    # -------------------------------------------------------------------------
    # Request Routing
    # -------------------------------------------------------------------------

    def get_active_provider(self, required_capabilities: Optional[set[Capability]] = None) -> Optional[ProviderConfig]:
        """Get the current active provider for routing requests."""
        # Check cooldowns
        now = datetime.utcnow()
        for state in self._providers.values():
            if state.in_cooldown and state.cooldown_until and now > state.cooldown_until:
                state.in_cooldown = False

        if self._active_provider_id:
            active_state = self._providers.get(self._active_provider_id)
            if active_state and active_state.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED):
                if not required_capabilities or required_capabilities.issubset(active_state.config.capabilities):
                    return active_state.config

        # Need to select a new provider
        states = list(self._providers.values())
        caps = required_capabilities or set()
        selected = self._strategy.select_provider(states, caps)
        if selected:
            self._active_provider_id = selected.config.id
            return selected.config
        return None

    def report_request_result(self, provider_id: str, success: bool, latency_ms: float) -> None:
        """Report the result of a request to update provider state."""
        state = self._providers.get(provider_id)
        if not state:
            return

        state.total_requests += 1
        state.avg_latency_ms = (state.avg_latency_ms * 0.95) + (latency_ms * 0.05)

        if not success:
            state.total_errors += 1
            state.consecutive_failures += 1
            error_rate = state.total_errors / state.total_requests if state.total_requests > 0 else 0

            if error_rate > state.config.max_error_rate:
                self._trigger_failover(state, FailoverReason.ERROR_RATE_EXCEEDED)
            elif state.consecutive_failures >= state.config.max_consecutive_failures:
                self._trigger_failover(state, FailoverReason.HEALTH_CHECK_FAILED)
        else:
            state.consecutive_failures = 0
            state.last_success = datetime.utcnow()

        if success and latency_ms > state.config.max_latency_ms:
            logger.warning(f"Provider {state.config.name} latency {latency_ms:.0f}ms exceeds target")

    # -------------------------------------------------------------------------
    # Fallback Drills
    # -------------------------------------------------------------------------

    async def run_fallback_drill(self, provider_to_disable: str, test_requests: list[dict] = None) -> FallbackDrillResult:
        """Simulate a provider outage to test fallback behavior."""
        state = self._providers.get(provider_to_disable)
        if not state:
            raise ValueError(f"Provider {provider_to_disable} not found")

        logger.info(f"DRILL: Simulating outage for {state.config.name}")

        # Save original state
        original_status = state.status
        original_active = self._active_provider_id

        # Simulate failure
        state.status = ProviderStatus.UNHEALTHY
        state.in_cooldown = True
        self._trigger_failover(state, FailoverReason.SCHEDULED_DRILL)

        # Get fallback provider
        fallback_state = self._providers.get(self._active_provider_id)
        if not fallback_state:
            state.status = original_status
            state.in_cooldown = False
            self._active_provider_id = original_active
            return FallbackDrillResult(
                id=f"DRILL-{uuid4().hex[:8]}",
                timestamp=datetime.utcnow(),
                provider_disabled=provider_to_disable,
                fallback_provider="NONE",
                success=False,
                latency_impact_pct=0,
                cost_impact_pct=0,
                capabilities_verified=[],
                capabilities_failed=list(state.config.capabilities),
                notes="No fallback provider available!",
            )

        # Verify capabilities
        verified = list(state.config.capabilities & fallback_state.config.capabilities)
        failed = list(state.config.capabilities - fallback_state.config.capabilities)

        # Calculate cost impact
        cost_impact = (
            (fallback_state.config.cost_per_1k_tokens - state.config.cost_per_1k_tokens)
            / state.config.cost_per_1k_tokens * 100
            if state.config.cost_per_1k_tokens > 0 else 0
        )

        # Calculate latency impact
        latency_impact = (
            (fallback_state.avg_latency_ms - state.avg_latency_ms)
            / state.avg_latency_ms * 100
            if state.avg_latency_ms > 0 else 0
        )

        # Restore
        state.status = original_status
        state.in_cooldown = False
        self._active_provider_id = original_active
        self._current_degraded_mode = DegradedModeLevel.NONE

        result = FallbackDrillResult(
            id=f"DRILL-{uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            provider_disabled=provider_to_disable,
            fallback_provider=fallback_state.config.id,
            success=len(failed) == 0,
            latency_impact_pct=latency_impact,
            cost_impact_pct=cost_impact,
            capabilities_verified=verified,
            capabilities_failed=failed,
            notes=f"Fallback to {fallback_state.config.name} {'successful' if not failed else 'with capability loss'}",
        )
        self._drill_history.append(result)
        logger.info(f"DRILL COMPLETE: success={result.success}, latency_impact={latency_impact:.1f}%")
        return result

    # -------------------------------------------------------------------------
    # Status and Reporting
    # -------------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get current system status."""
        return {
            "active_provider": self._active_provider_id,
            "degraded_mode": self._current_degraded_mode.value,
            "providers": {
                pid: {
                    "name": state.config.name,
                    "status": state.status.value,
                    "priority": state.config.priority,
                    "is_primary": state.is_primary,
                    "is_active": pid == self._active_provider_id,
                    "avg_latency_ms": state.avg_latency_ms,
                    "error_rate": state.total_errors / state.total_requests if state.total_requests > 0 else 0,
                    "in_cooldown": state.in_cooldown,
                    "consecutive_failures": state.consecutive_failures,
                }
                for pid, state in self._providers.items()
            },
            "total_failovers": len(self._failover_history),
            "total_drills": len(self._drill_history),
            "last_failover": self._failover_history[-1].timestamp.isoformat() if self._failover_history else None,
        }

    def get_failover_history(self) -> list[dict]:
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "from": e.from_provider,
                "to": e.to_provider,
                "reason": e.reason.value,
                "automatic": e.automatic,
                "degraded_mode": e.degraded_mode.value,
                "capabilities_lost": [c.value for c in e.capabilities_lost],
                "recovered": e.recovery_time.isoformat() if e.recovery_time else None,
            }
            for e in self._failover_history
        ]

    def get_cost_during_fallback(self) -> dict:
        """Calculate additional cost incurred during fallback periods."""
        total_extra_cost_factor = 0.0
        total_fallback_duration_minutes = 0

        for event in self._failover_history:
            if event.recovery_time:
                duration = (event.recovery_time - event.timestamp).total_seconds() / 60
                total_fallback_duration_minutes += duration

                from_state = self._providers.get(event.from_provider)
                to_state = self._providers.get(event.to_provider)
                if from_state and to_state:
                    cost_ratio = to_state.config.cost_per_1k_tokens / from_state.config.cost_per_1k_tokens
                    total_extra_cost_factor += (cost_ratio - 1.0) * duration

        return {
            "total_fallback_minutes": total_fallback_duration_minutes,
            "total_failover_events": len(self._failover_history),
            "avg_extra_cost_factor": total_extra_cost_factor / len(self._failover_history) if self._failover_history else 0,
        }


# =============================================================================
# Demo
# =============================================================================

def demo():
    print("=" * 60)
    print("Provider Fallback Strategy - Demo")
    print("=" * 60)

    manager = ProviderFallbackManager(strategy=PriorityFallback())

    # Configure providers
    manager.add_provider(ProviderConfig(
        id="openai-primary",
        name="OpenAI GPT-4",
        priority=1,
        capabilities={Capability.CHAT_COMPLETION, Capability.FUNCTION_CALLING,
                     Capability.VISION, Capability.STREAMING, Capability.JSON_MODE},
        max_latency_ms=2000,
        max_error_rate=0.05,
        rate_limit_rpm=500,
        cost_per_1k_tokens=0.03,
        health_check_endpoint="https://api.openai.com/v1/models",
    ))

    manager.add_provider(ProviderConfig(
        id="anthropic-fallback",
        name="Anthropic Claude",
        priority=2,
        capabilities={Capability.CHAT_COMPLETION, Capability.FUNCTION_CALLING,
                     Capability.VISION, Capability.STREAMING},
        max_latency_ms=3000,
        max_error_rate=0.05,
        rate_limit_rpm=300,
        cost_per_1k_tokens=0.015,
        health_check_endpoint="https://api.anthropic.com/v1/messages",
    ))

    manager.add_provider(ProviderConfig(
        id="local-llama",
        name="Local Llama 3",
        priority=3,
        capabilities={Capability.CHAT_COMPLETION, Capability.STREAMING},
        max_latency_ms=5000,
        max_error_rate=0.1,
        rate_limit_rpm=100,
        cost_per_1k_tokens=0.001,
        health_check_endpoint="http://localhost:8080/health",
    ))

    # Configure degraded modes
    manager.configure_degraded_mode(DegradedModeConfig(
        level=DegradedModeLevel.MINOR,
        description="Function calling via prompt engineering instead of native",
        disabled_features=["native_function_calling"],
        quality_impact="Slightly less reliable function calling",
        user_notification="Some features may respond slower than usual",
        max_duration_minutes=60,
    ))

    manager.configure_degraded_mode(DegradedModeConfig(
        level=DegradedModeLevel.SEVERE,
        description="Basic completion only, no vision or function calling",
        disabled_features=["function_calling", "vision", "json_mode"],
        quality_impact="Major reduction in capabilities",
        user_notification="We are experiencing issues. Some features are temporarily unavailable.",
        max_duration_minutes=30,
    ))

    # Register callbacks
    manager.on_failover(lambda e: print(f"  [FAILOVER] {e.from_provider} -> {e.to_provider}"))
    manager.on_recovery(lambda new, old: print(f"  [RECOVERY] Restored to {new}"))

    # Simulate normal operation
    print("\n--- Normal Operation ---")
    provider = manager.get_active_provider()
    print(f"Active provider: {provider.name}")

    # Simulate requests
    for i in range(10):
        manager.report_request_result("openai-primary", True, random.uniform(200, 800))

    # Simulate failures triggering failover
    print("\n--- Simulating Failures ---")
    for i in range(4):
        manager.report_request_result("openai-primary", False, 5000)

    # Check status after failover
    print("\n--- Status After Failover ---")
    status = manager.get_status()
    print(f"Active: {status['active_provider']}")
    print(f"Degraded Mode: {status['degraded_mode']}")
    for pid, pinfo in status["providers"].items():
        print(f"  {pinfo['name']}: {pinfo['status']} (active={pinfo['is_active']})")

    # Run a drill
    print("\n--- Running Fallback Drill ---")
    loop = asyncio.new_event_loop()
    drill_result = loop.run_until_complete(manager.run_fallback_drill("openai-primary"))
    print(f"Drill success: {drill_result.success}")
    print(f"Fallback to: {drill_result.fallback_provider}")
    print(f"Latency impact: {drill_result.latency_impact_pct:.1f}%")
    print(f"Cost impact: {drill_result.cost_impact_pct:.1f}%")
    print(f"Capabilities lost: {[c.value for c in drill_result.capabilities_failed]}")

    # Failover history
    print("\n--- Failover History ---")
    for event in manager.get_failover_history():
        print(f"  {event['timestamp']}: {event['from']} -> {event['to']} ({event['reason']})")

    loop.close()
    print("\n[Done]")


if __name__ == "__main__":
    demo()
