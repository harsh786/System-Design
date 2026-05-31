"""
Model Version Manager Simulator

Simulates model version management including registry, deployment lifecycle,
consumer pinning, deprecation, and backward compatibility checking.
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from collections import defaultdict


class VersionState(Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    CANARY = "canary"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    REMOVED = "removed"


class CompatibilityLevel(Enum):
    FULL = "full"  # Completely backward compatible
    PARTIAL = "partial"  # Some breaking changes
    BREAKING = "breaking"  # Major breaking changes


@dataclass
class ModelCharacteristics:
    quality_score: float  # 0-1
    latency_ms: float
    cost_per_query: float
    supported_features: Set[str]
    output_schema_version: str
    max_context_tokens: int


@dataclass
class ModelVersion:
    version_id: str
    name: str
    state: VersionState
    characteristics: ModelCharacteristics
    created_at: float
    promoted_at: Optional[float] = None
    deprecated_at: Optional[float] = None
    sunset_at: Optional[float] = None
    predecessor: Optional[str] = None
    config_hash: str = ""
    changelog: List[str] = field(default_factory=list)
    eval_results: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.config_hash:
            content = f"{self.version_id}-{self.characteristics.quality_score}"
            self.config_hash = hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class Consumer:
    consumer_id: str
    name: str
    pinned_version: Optional[str]
    min_version: Optional[str]
    max_version: Optional[str]
    required_features: Set[str]
    registered_at: float = field(default_factory=time.time)


@dataclass
class DeploymentEvent:
    timestamp: float
    version_id: str
    from_state: VersionState
    to_state: VersionState
    reason: str
    traffic_percentage: float = 0.0


class VersionRegistry:
    """Central registry for model versions."""

    def __init__(self):
        self.versions: Dict[str, ModelVersion] = {}
        self.consumers: Dict[str, Consumer] = {}
        self.events: List[DeploymentEvent] = []
        self.traffic_allocation: Dict[str, float] = {}

    def register_version(self, version: ModelVersion) -> None:
        self.versions[version.version_id] = version
        print(f"  [Registry] Registered version: {version.version_id} ({version.state.value})")

    def register_consumer(self, consumer: Consumer) -> None:
        self.consumers[consumer.consumer_id] = consumer
        print(f"  [Registry] Registered consumer: {consumer.name} (pinned={consumer.pinned_version})")

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        return self.versions.get(version_id)

    def get_active_versions(self) -> List[ModelVersion]:
        active_states = {VersionState.CANARY, VersionState.PRODUCTION}
        return [v for v in self.versions.values() if v.state in active_states]

    def get_production_version(self) -> Optional[ModelVersion]:
        for v in self.versions.values():
            if v.state == VersionState.PRODUCTION and self.traffic_allocation.get(v.version_id, 0) > 0.5:
                return v
        return None

    def transition_version(self, version_id: str, new_state: VersionState,
                          reason: str, traffic_pct: float = 0.0) -> bool:
        version = self.versions.get(version_id)
        if not version:
            print(f"  [Error] Version {version_id} not found")
            return False

        valid_transitions = {
            VersionState.DEVELOPMENT: {VersionState.TESTING},
            VersionState.TESTING: {VersionState.CANARY, VersionState.DEVELOPMENT},
            VersionState.CANARY: {VersionState.PRODUCTION, VersionState.DEVELOPMENT},
            VersionState.PRODUCTION: {VersionState.DEPRECATED},
            VersionState.DEPRECATED: {VersionState.SUNSET},
            VersionState.SUNSET: {VersionState.REMOVED},
        }

        allowed = valid_transitions.get(version.state, set())
        if new_state not in allowed:
            print(f"  [Error] Invalid transition: {version.state.value} -> {new_state.value}")
            return False

        event = DeploymentEvent(
            timestamp=time.time(),
            version_id=version_id,
            from_state=version.state,
            to_state=new_state,
            reason=reason,
            traffic_percentage=traffic_pct,
        )
        self.events.append(event)

        old_state = version.state
        version.state = new_state
        if new_state == VersionState.PRODUCTION:
            version.promoted_at = time.time()
        elif new_state == VersionState.DEPRECATED:
            version.deprecated_at = time.time()
        elif new_state == VersionState.SUNSET:
            version.sunset_at = time.time()

        self.traffic_allocation[version_id] = traffic_pct
        print(f"  [Lifecycle] {version_id}: {old_state.value} -> {new_state.value} "
              f"(traffic: {traffic_pct:.0%}, reason: {reason})")
        return True


class CompatibilityChecker:
    """Checks backward compatibility between model versions."""

    def check(self, old: ModelVersion, new: ModelVersion) -> Dict:
        issues = []
        level = CompatibilityLevel.FULL

        # Check output schema
        if old.characteristics.output_schema_version != new.characteristics.output_schema_version:
            issues.append(f"Output schema changed: {old.characteristics.output_schema_version} -> {new.characteristics.output_schema_version}")
            level = CompatibilityLevel.BREAKING

        # Check removed features
        removed = old.characteristics.supported_features - new.characteristics.supported_features
        if removed:
            issues.append(f"Features removed: {removed}")
            level = CompatibilityLevel.BREAKING

        # Check quality regression
        quality_delta = new.characteristics.quality_score - old.characteristics.quality_score
        if quality_delta < -0.1:
            issues.append(f"Quality regression: {quality_delta:+.2f}")
            if level == CompatibilityLevel.FULL:
                level = CompatibilityLevel.PARTIAL

        # Check latency increase
        latency_ratio = new.characteristics.latency_ms / max(old.characteristics.latency_ms, 1)
        if latency_ratio > 2.0:
            issues.append(f"Latency increased {latency_ratio:.1f}x")
            if level == CompatibilityLevel.FULL:
                level = CompatibilityLevel.PARTIAL

        # Check context reduction
        if new.characteristics.max_context_tokens < old.characteristics.max_context_tokens:
            issues.append(f"Context window reduced: {old.characteristics.max_context_tokens} -> {new.characteristics.max_context_tokens}")
            if level == CompatibilityLevel.FULL:
                level = CompatibilityLevel.PARTIAL

        # Check new features (non-breaking)
        added = new.characteristics.supported_features - old.characteristics.supported_features
        if added:
            issues.append(f"Features added (non-breaking): {added}")

        return {
            "compatibility_level": level,
            "issues": issues,
            "old_version": old.version_id,
            "new_version": new.version_id,
            "safe_to_upgrade": level != CompatibilityLevel.BREAKING,
        }


class ConsumerImpactAnalyzer:
    """Analyzes impact of version changes on consumers."""

    def __init__(self, registry: VersionRegistry):
        self.registry = registry

    def analyze_deprecation_impact(self, version_id: str) -> Dict:
        affected = []
        for consumer in self.registry.consumers.values():
            if consumer.pinned_version == version_id:
                affected.append({
                    "consumer": consumer.name,
                    "impact": "DIRECT - pinned to deprecated version",
                    "action_required": "Must update pinned version",
                })
            elif consumer.min_version and consumer.min_version <= version_id <= (consumer.max_version or "z"):
                affected.append({
                    "consumer": consumer.name,
                    "impact": "INDIRECT - version in allowed range",
                    "action_required": "Should update range bounds",
                })
        return {
            "version": version_id,
            "affected_consumers": len(affected),
            "details": affected,
        }

    def check_consumer_compatibility(self, consumer: Consumer, version: ModelVersion) -> Dict:
        missing_features = consumer.required_features - version.characteristics.supported_features
        compatible = len(missing_features) == 0
        return {
            "consumer": consumer.name,
            "version": version.version_id,
            "compatible": compatible,
            "missing_features": missing_features,
        }


def run_simulation():
    """Run the model version management simulation."""
    print("=" * 70)
    print("MODEL VERSION MANAGER SIMULATOR")
    print("=" * 70)

    registry = VersionRegistry()
    checker = CompatibilityChecker()
    analyzer = ConsumerImpactAnalyzer(registry)

    # Create model versions with different characteristics
    print("\n--- Registering Model Versions ---")

    v1 = ModelVersion(
        version_id="assistant-v1.0",
        name="Assistant V1",
        state=VersionState.PRODUCTION,
        characteristics=ModelCharacteristics(
            quality_score=0.72,
            latency_ms=100,
            cost_per_query=0.01,
            supported_features={"chat", "summarization", "classification"},
            output_schema_version="schema-v1",
            max_context_tokens=4096,
        ),
        created_at=time.time() - 86400 * 60,
        changelog=["Initial release"],
    )

    v2 = ModelVersion(
        version_id="assistant-v2.0",
        name="Assistant V2",
        state=VersionState.DEVELOPMENT,
        characteristics=ModelCharacteristics(
            quality_score=0.82,
            latency_ms=150,
            cost_per_query=0.02,
            supported_features={"chat", "summarization", "classification", "tool_use", "reasoning"},
            output_schema_version="schema-v1",
            max_context_tokens=8192,
        ),
        created_at=time.time() - 86400 * 30,
        predecessor="assistant-v1.0",
        changelog=["Added tool use", "Added reasoning", "Improved quality", "Extended context"],
    )

    v3 = ModelVersion(
        version_id="assistant-v3.0",
        name="Assistant V3",
        state=VersionState.DEVELOPMENT,
        characteristics=ModelCharacteristics(
            quality_score=0.90,
            latency_ms=200,
            cost_per_query=0.03,
            supported_features={"chat", "summarization", "tool_use", "reasoning", "vision"},
            output_schema_version="schema-v2",
            max_context_tokens=16384,
        ),
        created_at=time.time() - 86400 * 7,
        predecessor="assistant-v2.0",
        changelog=["Added vision", "Breaking: schema-v2", "Removed classification (use tool_use)"],
    )

    for v in [v1, v2, v3]:
        registry.register_version(v)

    registry.traffic_allocation["assistant-v1.0"] = 1.0

    # Register consumers
    print("\n--- Registering Consumers ---")

    consumers = [
        Consumer(
            consumer_id="frontend-app",
            name="Frontend Chat App",
            pinned_version="assistant-v1.0",
            min_version="assistant-v1.0",
            max_version=None,
            required_features={"chat", "summarization"},
        ),
        Consumer(
            consumer_id="analytics-svc",
            name="Analytics Service",
            pinned_version="assistant-v1.0",
            min_version="assistant-v1.0",
            max_version="assistant-v2.0",
            required_features={"classification"},
        ),
        Consumer(
            consumer_id="agent-platform",
            name="Agent Platform",
            pinned_version=None,
            min_version="assistant-v2.0",
            max_version=None,
            required_features={"chat", "tool_use", "reasoning"},
        ),
    ]

    for c in consumers:
        registry.register_consumer(c)

    # Simulate deployment lifecycle: v2 through canary to production
    print("\n--- Deployment Lifecycle: assistant-v2.0 ---")

    registry.transition_version("assistant-v2.0", VersionState.TESTING,
                               "Passed unit evals (quality=0.82)")

    # Simulate eval results
    v2.eval_results = {"accuracy": 0.85, "relevance": 0.80, "safety": 0.95}
    print(f"  [Eval] Results: {json.dumps(v2.eval_results)}")

    registry.transition_version("assistant-v2.0", VersionState.CANARY,
                               "Passed integration evals", traffic_pct=0.05)

    # Compatibility check
    print("\n--- Compatibility Check: v1.0 -> v2.0 ---")
    compat = checker.check(v1, v2)
    print(f"  Level: {compat['compatibility_level'].value}")
    print(f"  Safe to upgrade: {compat['safe_to_upgrade']}")
    for issue in compat['issues']:
        print(f"    - {issue}")

    # Canary metrics pass, promote to production
    print("\n--- Canary Results (simulated) ---")
    print("  Quality gate: PASSED (0.82 >= 0.75)")
    print("  Error rate: PASSED (0.02 <= 0.05)")
    print("  Latency P95: PASSED (180ms <= 300ms)")

    registry.transition_version("assistant-v2.0", VersionState.PRODUCTION,
                               "Canary quality gates passed", traffic_pct=1.0)

    # Deprecate v1
    print("\n--- Deprecating assistant-v1.0 ---")
    registry.transition_version("assistant-v1.0", VersionState.DEPRECATED,
                               "Successor v2.0 promoted to production")

    # Analyze deprecation impact
    print("\n--- Deprecation Impact Analysis ---")
    impact = analyzer.analyze_deprecation_impact("assistant-v1.0")
    print(f"  Affected consumers: {impact['affected_consumers']}")
    for detail in impact['details']:
        print(f"    {detail['consumer']}: {detail['impact']}")
        print(f"      Action: {detail['action_required']}")

    # Check v3 compatibility (breaking changes)
    print("\n--- Compatibility Check: v2.0 -> v3.0 ---")
    compat_v3 = checker.check(v2, v3)
    print(f"  Level: {compat_v3['compatibility_level'].value}")
    print(f"  Safe to upgrade: {compat_v3['safe_to_upgrade']}")
    for issue in compat_v3['issues']:
        print(f"    - {issue}")

    # Check consumer compatibility with v3
    print("\n--- Consumer Compatibility with v3.0 ---")
    for consumer in consumers:
        result = analyzer.check_consumer_compatibility(consumer, v3)
        status = "COMPATIBLE" if result['compatible'] else "INCOMPATIBLE"
        print(f"  {consumer.name}: {status}")
        if result['missing_features']:
            print(f"    Missing: {result['missing_features']}")

    # Sunset v1
    print("\n--- Sunset and Removal ---")
    registry.transition_version("assistant-v1.0", VersionState.SUNSET,
                               "Deprecation grace period elapsed (30 days)")

    registry.transition_version("assistant-v1.0", VersionState.REMOVED,
                               "Sunset period elapsed, no remaining traffic")

    # Final state
    print("\n" + "=" * 70)
    print("FINAL REGISTRY STATE")
    print("=" * 70)
    for vid, version in registry.versions.items():
        traffic = registry.traffic_allocation.get(vid, 0)
        print(f"  {vid}: state={version.state.value}, traffic={traffic:.0%}, "
              f"quality={version.characteristics.quality_score}, hash={version.config_hash}")

    print(f"\n  Total lifecycle events: {len(registry.events)}")
    print("  Event log:")
    for event in registry.events:
        print(f"    {event.version_id}: {event.from_state.value} -> {event.to_state.value} "
              f"({event.reason})")


if __name__ == "__main__":
    run_simulation()
