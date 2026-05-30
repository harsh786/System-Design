"""
Advanced Model Router - Intelligent routing engine for AI Gateway.

Supports multiple routing strategies:
- Rule-based routing (intent, risk, complexity, cost)
- Latency-aware routing
- Cost-optimized routing
- Quality-based routing
- A/B testing and canary routing
- Degraded mode routing
"""

import asyncio
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class RoutingStrategy(str, Enum):
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"
    BALANCED = "balanced"
    RULE_BASED = "rule_based"


class TaskComplexity(str, Enum):
    TRIVIAL = "trivial"      # Classification, extraction, simple QA
    SIMPLE = "simple"        # Summarization, translation, formatting
    MODERATE = "moderate"    # Multi-step reasoning, code generation
    COMPLEX = "complex"      # Advanced reasoning, creative writing, analysis
    CRITICAL = "critical"    # High-stakes decisions, regulated content


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RoutingContext:
    """All information available to the router for making decisions."""
    tenant_id: str = ""
    user_id: str = ""
    request_id: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    # Hints
    intent: Optional[str] = None
    task_complexity: Optional[TaskComplexity] = None
    risk_level: RiskLevel = RiskLevel.LOW
    max_latency_ms: Optional[float] = None
    max_cost: Optional[float] = None
    required_capabilities: List[str] = field(default_factory=list)
    preferred_provider: Optional[str] = None
    # Internal context
    estimated_input_tokens: int = 0
    is_streaming: bool = False
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """The output of the routing engine."""
    model_id: str
    provider: str
    strategy_used: str
    score: float  # Confidence/quality score of this routing decision
    reasoning: str
    fallback_models: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelMetrics:
    """Real-time performance metrics for a model."""
    model_id: str
    provider: str
    # Latency
    p50_latency_ms: float = 1000.0
    p95_latency_ms: float = 3000.0
    p99_latency_ms: float = 5000.0
    avg_ttft_ms: float = 200.0  # Time to first token
    # Reliability
    success_rate: float = 0.99
    error_rate_5m: float = 0.01
    # Quality
    quality_score: float = 0.85  # From evaluation sampling
    # Cost
    avg_cost_per_request: float = 0.01
    # Load
    current_rps: float = 0.0
    max_rps: float = 100.0
    # Health
    is_healthy: bool = True
    last_health_check: float = 0.0
    circuit_state: str = "closed"


@dataclass
class ModelCapability:
    """What a model can do."""
    model_id: str
    provider: str
    context_window: int = 128000
    max_output: int = 16384
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_function_calling: bool = False
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    quality_tier: str = "medium"


# ============================================================================
# Metrics Collector
# ============================================================================

class MetricsCollector:
    """Collects and maintains real-time model performance metrics."""

    def __init__(self, window_seconds: int = 300):
        self._window = window_seconds
        self._latencies: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self._successes: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
        self._costs: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def record_request(self, model_id: str, latency_ms: float, success: bool, cost: float):
        now = time.time()
        async with self._lock:
            self._latencies[model_id].append((now, latency_ms))
            self._successes[model_id].append((now, success))
            self._costs[model_id].append((now, cost))
            self._request_counts[model_id] += 1
            # Prune old data
            cutoff = now - self._window
            self._latencies[model_id] = [(t, v) for t, v in self._latencies[model_id] if t > cutoff]
            self._successes[model_id] = [(t, v) for t, v in self._successes[model_id] if t > cutoff]
            self._costs[model_id] = [(t, v) for t, v in self._costs[model_id] if t > cutoff]

    def get_metrics(self, model_id: str) -> ModelMetrics:
        now = time.time()
        cutoff = now - self._window

        latencies = [v for t, v in self._latencies[model_id] if t > cutoff]
        successes = [v for t, v in self._successes[model_id] if t > cutoff]
        costs = [v for t, v in self._costs[model_id] if t > cutoff]

        metrics = ModelMetrics(model_id=model_id, provider="")

        if latencies:
            sorted_lat = sorted(latencies)
            metrics.p50_latency_ms = sorted_lat[len(sorted_lat) // 2]
            metrics.p95_latency_ms = sorted_lat[int(len(sorted_lat) * 0.95)]
            metrics.p99_latency_ms = sorted_lat[int(len(sorted_lat) * 0.99)]

        if successes:
            metrics.success_rate = sum(1 for s in successes if s) / len(successes)
            metrics.error_rate_5m = 1 - metrics.success_rate

        if costs:
            metrics.avg_cost_per_request = sum(costs) / len(costs)

        metrics.current_rps = len(latencies) / self._window if latencies else 0
        metrics.is_healthy = metrics.success_rate > 0.9

        return metrics


# ============================================================================
# Complexity Estimator
# ============================================================================

class ComplexityEstimator:
    """Estimates task complexity from the request content."""

    # Keyword indicators for complexity
    COMPLEX_INDICATORS = [
        "analyze", "compare", "evaluate", "design", "architect",
        "prove", "derive", "optimize", "refactor", "debug",
        "multi-step", "trade-off", "comprehensive"
    ]
    SIMPLE_INDICATORS = [
        "translate", "summarize", "extract", "classify", "format",
        "list", "convert", "define", "what is"
    ]

    def estimate(self, context: RoutingContext) -> TaskComplexity:
        """Estimate complexity from messages and metadata."""
        if context.task_complexity:
            return context.task_complexity

        # Use the last user message
        last_message = ""
        for msg in reversed(context.messages):
            if msg.get("role") == "user":
                last_message = msg.get("content", "").lower()
                break

        if not last_message:
            return TaskComplexity.MODERATE

        # Token-length heuristic
        token_estimate = len(last_message) // 4
        if token_estimate > 2000:
            return TaskComplexity.COMPLEX

        # Keyword analysis
        complex_score = sum(1 for ind in self.COMPLEX_INDICATORS if ind in last_message)
        simple_score = sum(1 for ind in self.SIMPLE_INDICATORS if ind in last_message)

        # Number of questions/tasks
        question_count = last_message.count("?") + last_message.count("\n-") + last_message.count("\n*")

        if complex_score >= 3 or question_count > 3:
            return TaskComplexity.COMPLEX
        elif complex_score >= 1 or question_count > 1:
            return TaskComplexity.MODERATE
        elif simple_score >= 2:
            return TaskComplexity.SIMPLE
        elif token_estimate < 50 and simple_score >= 1:
            return TaskComplexity.TRIVIAL

        return TaskComplexity.MODERATE


# ============================================================================
# Routing Strategies
# ============================================================================

class RoutingStrategyBase(ABC):
    """Base class for routing strategies."""

    @abstractmethod
    async def route(
        self,
        context: RoutingContext,
        candidates: List[ModelCapability],
        metrics: Dict[str, ModelMetrics]
    ) -> Optional[RoutingDecision]:
        pass


class CostOptimizedStrategy(RoutingStrategyBase):
    """Route to the cheapest model that meets quality requirements."""

    async def route(
        self, context: RoutingContext,
        candidates: List[ModelCapability],
        metrics: Dict[str, ModelMetrics]
    ) -> Optional[RoutingDecision]:
        # Filter by capabilities
        viable = self._filter_capable(context, candidates)
        if not viable:
            return None

        # Sort by cost (input + expected output)
        estimated_output = min(context.estimated_input_tokens, 1000)  # Rough estimate
        viable.sort(key=lambda m: (
            m.input_cost_per_1k * context.estimated_input_tokens / 1000 +
            m.output_cost_per_1k * estimated_output / 1000
        ))

        best = viable[0]
        estimated_cost = (
            best.input_cost_per_1k * context.estimated_input_tokens / 1000 +
            best.output_cost_per_1k * estimated_output / 1000
        )

        # Check max cost constraint
        if context.max_cost and estimated_cost > context.max_cost:
            return None

        return RoutingDecision(
            model_id=best.model_id,
            provider=best.provider,
            strategy_used="cost_optimized",
            score=1.0 - (estimated_cost / 0.1),  # Normalize
            reasoning=f"Cheapest viable model: est. cost ${estimated_cost:.5f}",
            fallback_models=[m.model_id for m in viable[1:3]],
        )

    def _filter_capable(self, context: RoutingContext, candidates: List[ModelCapability]) -> List[ModelCapability]:
        viable = []
        for model in candidates:
            if "vision" in context.required_capabilities and not model.supports_vision:
                continue
            if "tools" in context.required_capabilities and not model.supports_tools:
                continue
            if context.estimated_input_tokens > model.context_window * 0.9:
                continue
            viable.append(model)
        return viable


class LatencyOptimizedStrategy(RoutingStrategyBase):
    """Route to the fastest model based on real-time latency metrics."""

    async def route(
        self, context: RoutingContext,
        candidates: List[ModelCapability],
        metrics: Dict[str, ModelMetrics]
    ) -> Optional[RoutingDecision]:
        # Score each model by latency
        scored = []
        for model in candidates:
            model_metrics = metrics.get(model.model_id)
            if not model_metrics or not model_metrics.is_healthy:
                continue
            # Use TTFT for streaming, p50 for non-streaming
            latency = model_metrics.avg_ttft_ms if context.is_streaming else model_metrics.p50_latency_ms
            if context.max_latency_ms and latency > context.max_latency_ms:
                continue
            scored.append((model, latency))

        if not scored:
            return None

        scored.sort(key=lambda x: x[1])
        best_model, best_latency = scored[0]

        return RoutingDecision(
            model_id=best_model.model_id,
            provider=best_model.provider,
            strategy_used="latency_optimized",
            score=1.0 - (best_latency / 5000),
            reasoning=f"Fastest model: p50={best_latency:.0f}ms",
            fallback_models=[m.model_id for m, _ in scored[1:3]],
        )


class QualityOptimizedStrategy(RoutingStrategyBase):
    """Route to the highest quality model for the given task."""

    # Quality tier ordering
    TIER_SCORES = {"high": 1.0, "medium": 0.7, "low": 0.4}

    async def route(
        self, context: RoutingContext,
        candidates: List[ModelCapability],
        metrics: Dict[str, ModelMetrics]
    ) -> Optional[RoutingDecision]:
        scored = []
        for model in candidates:
            model_metrics = metrics.get(model.model_id)
            if model_metrics and not model_metrics.is_healthy:
                continue
            quality = model_metrics.quality_score if model_metrics else self.TIER_SCORES.get(model.quality_tier, 0.5)
            scored.append((model, quality))

        if not scored:
            return None

        scored.sort(key=lambda x: x[1], reverse=True)
        best_model, best_quality = scored[0]

        return RoutingDecision(
            model_id=best_model.model_id,
            provider=best_model.provider,
            strategy_used="quality_optimized",
            score=best_quality,
            reasoning=f"Highest quality model: score={best_quality:.2f}",
            fallback_models=[m.model_id for m, _ in scored[1:3]],
        )


class BalancedStrategy(RoutingStrategyBase):
    """Balance cost, latency, and quality with configurable weights."""

    def __init__(self, cost_weight: float = 0.3, latency_weight: float = 0.3, quality_weight: float = 0.4):
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight
        self.quality_weight = quality_weight

    async def route(
        self, context: RoutingContext,
        candidates: List[ModelCapability],
        metrics: Dict[str, ModelMetrics]
    ) -> Optional[RoutingDecision]:
        scored = []

        for model in candidates:
            model_metrics = metrics.get(model.model_id)
            if model_metrics and not model_metrics.is_healthy:
                continue

            # Normalize cost score (lower is better, invert)
            cost = model.input_cost_per_1k * context.estimated_input_tokens / 1000
            cost_score = max(0, 1 - cost / 0.05)  # $0.05 as reference max

            # Normalize latency score (lower is better, invert)
            latency = model_metrics.p50_latency_ms if model_metrics else 2000
            latency_score = max(0, 1 - latency / 5000)  # 5s as reference max

            # Quality score
            quality = model_metrics.quality_score if model_metrics else 0.7

            # Weighted combination
            total_score = (
                self.cost_weight * cost_score +
                self.latency_weight * latency_score +
                self.quality_weight * quality
            )
            scored.append((model, total_score))

        if not scored:
            return None

        scored.sort(key=lambda x: x[1], reverse=True)
        best_model, best_score = scored[0]

        return RoutingDecision(
            model_id=best_model.model_id,
            provider=best_model.provider,
            strategy_used="balanced",
            score=best_score,
            reasoning=f"Balanced score: {best_score:.3f} (c={self.cost_weight}, l={self.latency_weight}, q={self.quality_weight})",
            fallback_models=[m.model_id for m, _ in scored[1:3]],
        )


# ============================================================================
# Rule-Based Router
# ============================================================================

@dataclass
class RoutingRule:
    """A single routing rule with conditions and target."""
    name: str
    conditions: Dict[str, Any]  # Field -> expected value(s)
    target_model: str
    priority: int = 0  # Higher = checked first
    enabled: bool = True


class RuleBasedRouter:
    """Evaluate routing rules in priority order."""

    def __init__(self):
        self._rules: List[RoutingRule] = []

    def add_rule(self, rule: RoutingRule):
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: RoutingContext) -> Optional[str]:
        """Evaluate rules and return first matching model_id."""
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._matches(rule, context):
                logger.info(f"Rule matched: {rule.name} -> {rule.target_model}")
                return rule.target_model
        return None

    def _matches(self, rule: RoutingRule, context: RoutingContext) -> bool:
        for field, expected in rule.conditions.items():
            actual = self._get_field(context, field)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def _get_field(self, context: RoutingContext, field: str) -> Any:
        field_map = {
            "intent": context.intent,
            "complexity": context.task_complexity.value if context.task_complexity else None,
            "risk_level": context.risk_level.value,
            "tenant_id": context.tenant_id,
            "priority": context.priority,
            "is_streaming": context.is_streaming,
        }
        return field_map.get(field)


# ============================================================================
# A/B Testing Router
# ============================================================================

@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""
    test_id: str
    name: str
    control_model: str
    variant_model: str
    traffic_split: float = 0.5  # % going to variant
    enabled: bool = True
    start_time: float = 0.0
    end_time: float = float("inf")
    # Targeting
    target_tenants: Optional[List[str]] = None
    target_complexity: Optional[List[str]] = None


class ABTestRouter:
    """Route traffic for A/B testing between models."""

    def __init__(self):
        self._tests: Dict[str, ABTestConfig] = {}
        self._assignments: Dict[str, str] = {}  # user_id -> variant

    def create_test(self, config: ABTestConfig):
        self._tests[config.test_id] = config

    def route(self, context: RoutingContext) -> Optional[Tuple[str, str]]:
        """Returns (model_id, test_id) or None if no test applies."""
        now = time.time()

        for test in self._tests.values():
            if not test.enabled or now < test.start_time or now > test.end_time:
                continue
            if test.target_tenants and context.tenant_id not in test.target_tenants:
                continue
            if test.target_complexity:
                ctx_complexity = context.task_complexity.value if context.task_complexity else "moderate"
                if ctx_complexity not in test.target_complexity:
                    continue

            # Deterministic assignment based on user_id
            assignment_key = f"{test.test_id}:{context.user_id}"
            if assignment_key not in self._assignments:
                # Use hash for deterministic but random-looking assignment
                hash_val = int(hashlib.md5(assignment_key.encode()).hexdigest(), 16)
                is_variant = (hash_val % 100) < (test.traffic_split * 100)
                self._assignments[assignment_key] = "variant" if is_variant else "control"

            if self._assignments[assignment_key] == "variant":
                return test.variant_model, test.test_id
            else:
                return test.control_model, test.test_id

        return None


# ============================================================================
# Canary Router
# ============================================================================

@dataclass
class CanaryConfig:
    """Canary deployment configuration."""
    canary_id: str
    stable_model: str
    canary_model: str
    canary_percentage: float = 5.0  # Start at 5%
    max_percentage: float = 100.0
    ramp_step: float = 5.0  # Increase by 5% each step
    error_threshold: float = 0.05  # Rollback if error rate > 5%
    min_requests_for_decision: int = 100
    auto_promote: bool = True


class CanaryRouter:
    """Gradual traffic shifting for new model deployments."""

    def __init__(self):
        self._canaries: Dict[str, CanaryConfig] = {}
        self._canary_metrics: Dict[str, Dict[str, List]] = defaultdict(lambda: {"success": [], "failure": []})

    def deploy_canary(self, config: CanaryConfig):
        self._canaries[config.canary_id] = config

    def route(self, context: RoutingContext) -> Optional[str]:
        """Route request to canary or stable based on percentage."""
        for canary in self._canaries.values():
            # Random routing based on percentage
            if random.random() * 100 < canary.canary_percentage:
                return canary.canary_model
            return canary.stable_model
        return None

    async def record_result(self, canary_id: str, success: bool):
        """Record canary result and auto-promote/rollback."""
        if canary_id not in self._canaries:
            return

        canary = self._canaries[canary_id]
        key = "success" if success else "failure"
        self._canary_metrics[canary_id][key].append(time.time())

        # Check if we have enough data
        total = len(self._canary_metrics[canary_id]["success"]) + len(self._canary_metrics[canary_id]["failure"])
        if total < canary.min_requests_for_decision:
            return

        # Calculate error rate
        failures = len(self._canary_metrics[canary_id]["failure"])
        error_rate = failures / total

        if error_rate > canary.error_threshold:
            # Rollback
            logger.warning(f"Canary {canary_id} rollback: error_rate={error_rate:.2%}")
            canary.canary_percentage = 0
        elif canary.auto_promote and error_rate < canary.error_threshold / 2:
            # Promote: increase traffic
            canary.canary_percentage = min(
                canary.canary_percentage + canary.ramp_step,
                canary.max_percentage
            )
            logger.info(f"Canary {canary_id} promoted to {canary.canary_percentage}%")
            # Reset metrics for next evaluation window
            self._canary_metrics[canary_id] = {"success": [], "failure": []}


# ============================================================================
# Degraded Mode Router
# ============================================================================

class DegradedModeLevel(int, Enum):
    FULL_SERVICE = 0
    DEGRADED_QUALITY = 1
    ESSENTIAL_ONLY = 2
    CACHE_ONLY = 3
    GRACEFUL_FAILURE = 4


class DegradedModeRouter:
    """Handle routing when providers are degraded or down."""

    def __init__(self):
        self._current_level = DegradedModeLevel.FULL_SERVICE
        self._provider_health: Dict[str, bool] = {}
        self._degraded_model_map: Dict[int, Dict[str, str]] = {
            # Level -> {original_model -> degraded_model}
            DegradedModeLevel.DEGRADED_QUALITY: {
                "gpt-4o": "gpt-4o-mini",
                "claude-3-5-sonnet": "claude-3-5-haiku",
            },
            DegradedModeLevel.ESSENTIAL_ONLY: {
                "gpt-4o": "llama-3-70b",
                "claude-3-5-sonnet": "llama-3-70b",
                "gpt-4o-mini": "llama-3-70b",
            },
        }

    def update_provider_health(self, provider: str, is_healthy: bool):
        self._provider_health[provider] = is_healthy
        # Auto-determine degradation level
        healthy_count = sum(1 for h in self._provider_health.values() if h)
        total = len(self._provider_health)
        if total == 0:
            return
        health_ratio = healthy_count / total
        if health_ratio >= 0.8:
            self._current_level = DegradedModeLevel.FULL_SERVICE
        elif health_ratio >= 0.5:
            self._current_level = DegradedModeLevel.DEGRADED_QUALITY
        elif health_ratio >= 0.2:
            self._current_level = DegradedModeLevel.ESSENTIAL_ONLY
        else:
            self._current_level = DegradedModeLevel.CACHE_ONLY

    def route(self, original_model: str, context: RoutingContext) -> Tuple[Optional[str], DegradedModeLevel]:
        """Get degraded model replacement if needed."""
        if self._current_level == DegradedModeLevel.FULL_SERVICE:
            return original_model, self._current_level

        if self._current_level == DegradedModeLevel.CACHE_ONLY:
            return None, self._current_level  # Signal to use cache only

        if self._current_level == DegradedModeLevel.GRACEFUL_FAILURE:
            return None, self._current_level  # Signal to return error

        # Get degraded replacement
        level_map = self._degraded_model_map.get(self._current_level, {})
        replacement = level_map.get(original_model, original_model)
        return replacement, self._current_level


# ============================================================================
# Load Balancer
# ============================================================================

class LoadBalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"


class ProviderLoadBalancer:
    """Load balance across multiple instances/keys of the same provider."""

    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.WEIGHTED):
        self.strategy = strategy
        self._endpoints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._connections: Dict[str, int] = defaultdict(int)

    def add_endpoint(self, provider: str, endpoint: str, weight: float = 1.0):
        self._endpoints[provider].append({
            "endpoint": endpoint,
            "weight": weight,
            "healthy": True,
        })

    def get_endpoint(self, provider: str) -> Optional[str]:
        endpoints = [e for e in self._endpoints[provider] if e["healthy"]]
        if not endpoints:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            idx = self._counters[provider] % len(endpoints)
            self._counters[provider] += 1
            return endpoints[idx]["endpoint"]

        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            weights = [e["weight"] for e in endpoints]
            total = sum(weights)
            r = random.random() * total
            cumulative = 0
            for e in endpoints:
                cumulative += e["weight"]
                if r <= cumulative:
                    return e["endpoint"]
            return endpoints[-1]["endpoint"]

        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(endpoints)["endpoint"]

        return endpoints[0]["endpoint"]


# ============================================================================
# Main Model Router
# ============================================================================

class ModelRouter:
    """
    Main model router that orchestrates all routing strategies.

    Routing priority:
    1. Explicit model selection (bypass routing)
    2. Rule-based routing (deterministic rules)
    3. A/B test routing (if user is in a test)
    4. Canary routing (if canary is active)
    5. Strategy-based routing (cost/latency/quality/balanced)
    6. Degraded mode routing (if providers are unhealthy)
    """

    def __init__(self, default_strategy: RoutingStrategy = RoutingStrategy.BALANCED):
        self.default_strategy = default_strategy
        self.complexity_estimator = ComplexityEstimator()
        self.metrics_collector = MetricsCollector()
        self.rule_router = RuleBasedRouter()
        self.ab_test_router = ABTestRouter()
        self.canary_router = CanaryRouter()
        self.degraded_router = DegradedModeRouter()
        self.load_balancer = ProviderLoadBalancer()

        # Strategy implementations
        self._strategies: Dict[RoutingStrategy, RoutingStrategyBase] = {
            RoutingStrategy.COST_OPTIMIZED: CostOptimizedStrategy(),
            RoutingStrategy.LATENCY_OPTIMIZED: LatencyOptimizedStrategy(),
            RoutingStrategy.QUALITY_OPTIMIZED: QualityOptimizedStrategy(),
            RoutingStrategy.BALANCED: BalancedStrategy(),
        }

        # Model capabilities registry
        self._capabilities: List[ModelCapability] = []

        # Tenant-specific strategy overrides
        self._tenant_strategies: Dict[str, RoutingStrategy] = {}

        # Routing metrics
        self._routing_decisions: List[Dict] = []

    def register_model(self, capability: ModelCapability):
        self._capabilities.append(capability)

    def set_tenant_strategy(self, tenant_id: str, strategy: RoutingStrategy):
        self._tenant_strategies[tenant_id] = strategy

    async def route(self, context: RoutingContext) -> RoutingDecision:
        """
        Main routing method. Returns the best model for the given context.
        """
        # Estimate complexity if not provided
        if not context.task_complexity:
            context.task_complexity = self.complexity_estimator.estimate(context)

        # 1. Rule-based routing (highest priority)
        rule_result = self.rule_router.evaluate(context)
        if rule_result:
            return RoutingDecision(
                model_id=rule_result,
                provider=self._get_provider(rule_result),
                strategy_used="rule_based",
                score=1.0,
                reasoning="Matched routing rule",
            )

        # 2. A/B test routing
        ab_result = self.ab_test_router.route(context)
        if ab_result:
            model_id, test_id = ab_result
            return RoutingDecision(
                model_id=model_id,
                provider=self._get_provider(model_id),
                strategy_used="ab_test",
                score=0.9,
                reasoning=f"A/B test: {test_id}",
                metadata={"ab_test_id": test_id},
            )

        # 3. Canary routing
        canary_result = self.canary_router.route(context)
        if canary_result:
            return RoutingDecision(
                model_id=canary_result,
                provider=self._get_provider(canary_result),
                strategy_used="canary",
                score=0.85,
                reasoning="Canary deployment routing",
            )

        # 4. Strategy-based routing
        strategy = self._tenant_strategies.get(context.tenant_id, self.default_strategy)

        # Override strategy based on context
        if context.risk_level == RiskLevel.CRITICAL:
            strategy = RoutingStrategy.QUALITY_OPTIMIZED
        elif context.max_cost is not None and context.max_cost < 0.01:
            strategy = RoutingStrategy.COST_OPTIMIZED
        elif context.max_latency_ms is not None and context.max_latency_ms < 1000:
            strategy = RoutingStrategy.LATENCY_OPTIMIZED

        # Get metrics for all models
        metrics = {cap.model_id: self.metrics_collector.get_metrics(cap.model_id) for cap in self._capabilities}

        # Execute strategy
        strategy_impl = self._strategies.get(strategy)
        if strategy_impl:
            decision = await strategy_impl.route(context, self._capabilities, metrics)
            if decision:
                # 5. Check degraded mode
                degraded_model, level = self.degraded_router.route(decision.model_id, context)
                if degraded_model and degraded_model != decision.model_id:
                    decision.model_id = degraded_model
                    decision.provider = self._get_provider(degraded_model)
                    decision.reasoning += f" [degraded: level={level.name}]"

                self._record_decision(context, decision)
                return decision

        # Fallback to default model
        return RoutingDecision(
            model_id="gpt-4o-mini",
            provider="openai",
            strategy_used="fallback_default",
            score=0.5,
            reasoning="No strategy matched, using default",
        )

    def _get_provider(self, model_id: str) -> str:
        for cap in self._capabilities:
            if cap.model_id == model_id:
                return cap.provider
        return "unknown"

    def _record_decision(self, context: RoutingContext, decision: RoutingDecision):
        self._routing_decisions.append({
            "timestamp": time.time(),
            "request_id": context.request_id,
            "tenant_id": context.tenant_id,
            "complexity": context.task_complexity.value if context.task_complexity else "unknown",
            "model": decision.model_id,
            "strategy": decision.strategy_used,
            "score": decision.score,
        })
        # Keep last 10000 decisions for analysis
        if len(self._routing_decisions) > 10000:
            self._routing_decisions = self._routing_decisions[-10000:]

    # ========================================================================
    # Analytics
    # ========================================================================

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing decision statistics."""
        if not self._routing_decisions:
            return {}

        strategy_counts = defaultdict(int)
        model_counts = defaultdict(int)
        for d in self._routing_decisions:
            strategy_counts[d["strategy"]] += 1
            model_counts[d["model"]] += 1

        total = len(self._routing_decisions)
        return {
            "total_decisions": total,
            "strategy_distribution": {k: v / total for k, v in strategy_counts.items()},
            "model_distribution": {k: v / total for k, v in model_counts.items()},
        }


# ============================================================================
# Example Usage
# ============================================================================

async def main():
    # Initialize router
    router = ModelRouter(default_strategy=RoutingStrategy.BALANCED)

    # Register models
    router.register_model(ModelCapability(
        model_id="gpt-4o", provider="openai",
        context_window=128000, max_output=16384,
        supports_vision=True, supports_tools=True,
        input_cost_per_1k=0.0025, output_cost_per_1k=0.01,
        quality_tier="high"
    ))
    router.register_model(ModelCapability(
        model_id="gpt-4o-mini", provider="openai",
        context_window=128000, max_output=16384,
        supports_vision=True, supports_tools=True,
        input_cost_per_1k=0.00015, output_cost_per_1k=0.0006,
        quality_tier="medium"
    ))
    router.register_model(ModelCapability(
        model_id="claude-3-5-sonnet", provider="anthropic",
        context_window=200000, max_output=8192,
        supports_vision=True, supports_tools=True,
        input_cost_per_1k=0.003, output_cost_per_1k=0.015,
        quality_tier="high"
    ))
    router.register_model(ModelCapability(
        model_id="llama-3-70b", provider="self_hosted",
        context_window=8192, max_output=4096,
        input_cost_per_1k=0.0, output_cost_per_1k=0.0,
        quality_tier="medium"
    ))

    # Add rules
    router.rule_router.add_rule(RoutingRule(
        name="critical_to_best",
        conditions={"risk_level": "critical"},
        target_model="gpt-4o",
        priority=100
    ))
    router.rule_router.add_rule(RoutingRule(
        name="batch_to_cheap",
        conditions={"priority": "batch"},
        target_model="llama-3-70b",
        priority=90
    ))

    # Route a request
    context = RoutingContext(
        tenant_id="tenant-123",
        user_id="user-456",
        messages=[{"role": "user", "content": "Summarize this article in 3 bullet points"}],
        estimated_input_tokens=500,
        risk_level=RiskLevel.LOW,
    )

    decision = await router.route(context)
    print(f"Routed to: {decision.model_id} ({decision.provider})")
    print(f"Strategy: {decision.strategy_used}")
    print(f"Reasoning: {decision.reasoning}")
    print(f"Fallbacks: {decision.fallback_models}")


if __name__ == "__main__":
    asyncio.run(main())
