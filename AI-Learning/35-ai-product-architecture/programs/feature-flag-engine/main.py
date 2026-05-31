"""
Feature Flag Engine for AI Systems - Simulates feature flags, rollouts, and A/B testing.

Supports:
- Multiple flag types (model version, prompt template, threshold)
- User targeting and percentage rollout
- A/B test assignment with consistent hashing
- Kill-switch activation
- Ring deployment simulation

Standard library only. No API keys required.
"""

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class FlagType(Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    NUMERIC = "numeric"
    JSON = "json"


class RolloutRing(Enum):
    CANARY = "canary"        # 1% - internal testers
    EARLY_ADOPTER = "early"  # 10% - opted-in users
    GENERAL = "general"      # 50% - gradual rollout
    FULL = "full"            # 100% - everyone


@dataclass
class TargetingRule:
    """Rule for targeting specific users or segments."""
    attribute: str
    operator: str  # "in", "not_in", "equals", "gt", "lt"
    value: Any

    def evaluate(self, user_context: Dict[str, Any]) -> bool:
        user_val = user_context.get(self.attribute)
        if user_val is None:
            return False
        if self.operator == "in":
            return user_val in self.value
        elif self.operator == "not_in":
            return user_val not in self.value
        elif self.operator == "equals":
            return user_val == self.value
        elif self.operator == "gt":
            return user_val > self.value
        elif self.operator == "lt":
            return user_val < self.value
        return False


@dataclass
class FeatureFlag:
    """A feature flag with rollout configuration."""
    name: str
    flag_type: FlagType
    default_value: Any
    enabled: bool = True
    rollout_percentage: float = 0.0  # 0-100
    targeting_rules: List[TargetingRule] = field(default_factory=list)
    variants: Dict[str, Any] = field(default_factory=dict)
    kill_switch: bool = False
    ring: RolloutRing = RolloutRing.FULL
    description: str = ""


@dataclass
class ABTestAssignment:
    """Records a user's assignment to an A/B test variant."""
    user_id: str
    flag_name: str
    variant: str
    timestamp: str


@dataclass
class FlagEvaluation:
    """Result of evaluating a flag for a user."""
    flag_name: str
    user_id: str
    value: Any
    reason: str  # "kill_switch", "targeting", "rollout", "default", "ring"


class FeatureFlagEngine:
    """Feature flag engine with AI-specific capabilities."""

    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.assignments: List[ABTestAssignment] = []
        self.evaluation_log: List[FlagEvaluation] = []
        self._setup_default_flags()

    def _setup_default_flags(self):
        """Set up AI-specific feature flags."""
        # Model version flag
        self.register_flag(FeatureFlag(
            name="model_version",
            flag_type=FlagType.STRING,
            default_value="gpt-4o-stable",
            enabled=True,
            rollout_percentage=100.0,
            variants={"control": "gpt-4o-stable", "treatment": "gpt-4o-latest"},
            description="Controls which model version serves requests",
        ))

        # Prompt template flag
        self.register_flag(FeatureFlag(
            name="prompt_template",
            flag_type=FlagType.STRING,
            default_value="v2_concise",
            enabled=True,
            rollout_percentage=30.0,
            variants={"control": "v2_concise", "treatment": "v3_detailed"},
            description="A/B test between concise and detailed prompt templates",
        ))

        # Quality threshold flag
        self.register_flag(FeatureFlag(
            name="quality_threshold",
            flag_type=FlagType.NUMERIC,
            default_value=0.7,
            enabled=True,
            rollout_percentage=50.0,
            variants={"control": 0.7, "treatment": 0.85},
            description="Minimum quality score before showing response to user",
        ))

        # RAG retrieval flag
        self.register_flag(FeatureFlag(
            name="rag_enabled",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            enabled=True,
            rollout_percentage=20.0,
            ring=RolloutRing.EARLY_ADOPTER,
            description="Enable RAG-augmented responses",
        ))

        # Safety filter version
        self.register_flag(FeatureFlag(
            name="safety_filter_v2",
            flag_type=FlagType.BOOLEAN,
            default_value=False,
            enabled=True,
            rollout_percentage=10.0,
            ring=RolloutRing.CANARY,
            targeting_rules=[
                TargetingRule(attribute="tier", operator="in", value=["enterprise", "pro"]),
            ],
            description="New safety filter with reduced false positives",
        ))

        # Streaming response flag
        self.register_flag(FeatureFlag(
            name="streaming_enabled",
            flag_type=FlagType.BOOLEAN,
            default_value=True,
            enabled=True,
            rollout_percentage=100.0,
            description="Enable streaming responses (kill-switch candidate)",
        ))

    def register_flag(self, flag: FeatureFlag):
        """Register a new feature flag."""
        self.flags[flag.name] = flag

    def evaluate(self, flag_name: str, user_context: Dict[str, Any]) -> FlagEvaluation:
        """Evaluate a feature flag for a given user context."""
        flag = self.flags.get(flag_name)
        if flag is None:
            eval_result = FlagEvaluation(flag_name, user_context.get("user_id", "unknown"),
                                         None, "flag_not_found")
            self.evaluation_log.append(eval_result)
            return eval_result

        user_id = user_context.get("user_id", "anonymous")

        # Kill switch overrides everything
        if flag.kill_switch:
            eval_result = FlagEvaluation(flag_name, user_id, flag.default_value, "kill_switch")
            self.evaluation_log.append(eval_result)
            return eval_result

        # Disabled flag returns default
        if not flag.enabled:
            eval_result = FlagEvaluation(flag_name, user_id, flag.default_value, "disabled")
            self.evaluation_log.append(eval_result)
            return eval_result

        # Ring-based deployment check
        user_ring = self._get_user_ring(user_id, user_context)
        if not self._ring_allows(user_ring, flag.ring):
            eval_result = FlagEvaluation(flag_name, user_id, flag.default_value, "ring_excluded")
            self.evaluation_log.append(eval_result)
            return eval_result

        # Targeting rules (if any match, user gets the treatment)
        if flag.targeting_rules:
            all_match = all(rule.evaluate(user_context) for rule in flag.targeting_rules)
            if all_match and flag.variants:
                value = flag.variants.get("treatment", flag.default_value)
                eval_result = FlagEvaluation(flag_name, user_id, value, "targeting")
                self.evaluation_log.append(eval_result)
                self._record_assignment(user_id, flag_name, "treatment")
                return eval_result

        # Percentage rollout with consistent hashing
        if self._is_in_rollout(user_id, flag_name, flag.rollout_percentage):
            if flag.variants:
                variant = self._assign_variant(user_id, flag_name, flag.variants)
                value = flag.variants[variant]
            elif flag.flag_type == FlagType.BOOLEAN:
                value = True
                variant = "enabled"
            else:
                value = flag.default_value
                variant = "default"
            eval_result = FlagEvaluation(flag_name, user_id, value, "rollout")
            self.evaluation_log.append(eval_result)
            self._record_assignment(user_id, flag_name, variant)
            return eval_result

        # Default
        eval_result = FlagEvaluation(flag_name, user_id, flag.default_value, "default")
        self.evaluation_log.append(eval_result)
        return eval_result

    def _is_in_rollout(self, user_id: str, flag_name: str, percentage: float) -> bool:
        """Consistent hash-based rollout assignment."""
        hash_input = f"{user_id}:{flag_name}".encode()
        hash_value = int(hashlib.sha256(hash_input).hexdigest()[:8], 16)
        bucket = (hash_value % 10000) / 100.0  # 0-100 with 0.01 precision
        return bucket < percentage

    def _assign_variant(self, user_id: str, flag_name: str, variants: Dict[str, Any]) -> str:
        """Consistently assign user to a variant."""
        hash_input = f"{user_id}:{flag_name}:variant".encode()
        hash_value = int(hashlib.sha256(hash_input).hexdigest()[:8], 16)
        variant_names = sorted(variants.keys())
        idx = hash_value % len(variant_names)
        return variant_names[idx]

    def _get_user_ring(self, user_id: str, context: Dict[str, Any]) -> RolloutRing:
        """Determine user's deployment ring."""
        if context.get("is_internal", False):
            return RolloutRing.CANARY
        if context.get("early_adopter", False):
            return RolloutRing.EARLY_ADOPTER
        # Hash-based general ring assignment
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:4], 16)
        if hash_val % 100 < 50:
            return RolloutRing.GENERAL
        return RolloutRing.FULL

    def _ring_allows(self, user_ring: RolloutRing, flag_ring: RolloutRing) -> bool:
        """Check if user's ring has access to the flag."""
        ring_order = [RolloutRing.CANARY, RolloutRing.EARLY_ADOPTER,
                      RolloutRing.GENERAL, RolloutRing.FULL]
        user_idx = ring_order.index(user_ring)
        flag_idx = ring_order.index(flag_ring)
        return user_idx <= flag_idx

    def _record_assignment(self, user_id: str, flag_name: str, variant: str):
        self.assignments.append(ABTestAssignment(
            user_id=user_id,
            flag_name=flag_name,
            variant=variant,
            timestamp=datetime.now().isoformat(),
        ))

    def activate_kill_switch(self, flag_name: str) -> bool:
        """Activate kill switch for a flag."""
        if flag_name in self.flags:
            self.flags[flag_name].kill_switch = True
            return True
        return False

    def deactivate_kill_switch(self, flag_name: str) -> bool:
        if flag_name in self.flags:
            self.flags[flag_name].kill_switch = False
            return True
        return False

    def update_rollout_percentage(self, flag_name: str, percentage: float):
        """Update rollout percentage for gradual rollout."""
        if flag_name in self.flags:
            self.flags[flag_name].rollout_percentage = max(0, min(100, percentage))


def run_simulation():
    """Run the feature flag engine simulation."""
    print("=" * 60)
    print("AI FEATURE FLAG ENGINE - Simulation")
    print("=" * 60)

    engine = FeatureFlagEngine()
    random.seed(42)

    # Simulate users
    users = []
    for i in range(20):
        users.append({
            "user_id": f"user_{i:04d}",
            "tier": random.choice(["free", "pro", "enterprise"]),
            "is_internal": i < 2,
            "early_adopter": i < 5,
            "region": random.choice(["us-east", "us-west", "eu-west"]),
        })

    # === Phase 1: Normal evaluation ===
    print(f"\n{'─' * 60}")
    print("Phase 1: Evaluating flags for all users")
    print(f"{'─' * 60}")

    flag_names = ["model_version", "prompt_template", "quality_threshold",
                  "rag_enabled", "safety_filter_v2", "streaming_enabled"]

    for flag_name in flag_names:
        results = {"control": 0, "treatment": 0, "default": 0, "other": 0}
        for user in users:
            eval_result = engine.evaluate(flag_name, user)
            flag = engine.flags[flag_name]
            if flag.variants:
                if eval_result.value == flag.variants.get("treatment"):
                    results["treatment"] += 1
                elif eval_result.value == flag.variants.get("control"):
                    results["control"] += 1
                else:
                    results["default"] += 1
            elif eval_result.value == flag.default_value:
                results["default"] += 1
            else:
                results["other"] += 1

        print(f"\n  {flag_name}:")
        print(f"    Rollout: {engine.flags[flag_name].rollout_percentage}% | "
              f"Ring: {engine.flags[flag_name].ring.value}")
        non_zero = {k: v for k, v in results.items() if v > 0}
        print(f"    Distribution: {non_zero}")

    # === Phase 2: A/B test consistency check ===
    print(f"\n{'─' * 60}")
    print("Phase 2: A/B Test Consistency Verification")
    print(f"{'─' * 60}")

    test_user = {"user_id": "user_0007", "tier": "pro", "is_internal": False,
                 "early_adopter": False}
    print(f"\n  Testing consistency for {test_user['user_id']}:")
    evaluations = []
    for _ in range(5):
        result = engine.evaluate("prompt_template", test_user)
        evaluations.append(result.value)
    consistent = len(set(evaluations)) == 1
    print(f"    5 evaluations: {evaluations}")
    print(f"    Consistent: {'✓ YES' if consistent else '✗ NO'}")

    # === Phase 3: Kill-switch activation ===
    print(f"\n{'─' * 60}")
    print("Phase 3: Kill-Switch Activation Demo")
    print(f"{'─' * 60}")

    print(f"\n  Before kill-switch (streaming_enabled):")
    result = engine.evaluate("streaming_enabled", users[5])
    print(f"    User user_0005: value={result.value}, reason={result.reason}")

    engine.activate_kill_switch("streaming_enabled")
    print(f"\n  ⚠ KILL-SWITCH ACTIVATED for 'streaming_enabled'")

    print(f"\n  After kill-switch:")
    for user in users[:5]:
        result = engine.evaluate("streaming_enabled", user)
        print(f"    {user['user_id']}: value={result.value}, reason={result.reason}")

    engine.deactivate_kill_switch("streaming_enabled")
    print(f"\n  ✓ Kill-switch deactivated")

    # === Phase 4: Ring deployment simulation ===
    print(f"\n{'─' * 60}")
    print("Phase 4: Ring Deployment Simulation")
    print(f"{'─' * 60}")

    print(f"\n  Simulating gradual rollout of 'rag_enabled':")
    ring_stages = [
        (RolloutRing.CANARY, 10.0),
        (RolloutRing.EARLY_ADOPTER, 20.0),
        (RolloutRing.GENERAL, 50.0),
        (RolloutRing.FULL, 100.0),
    ]

    for ring, pct in ring_stages:
        engine.flags["rag_enabled"].ring = ring
        engine.flags["rag_enabled"].rollout_percentage = pct

        enabled_count = 0
        for user in users:
            result = engine.evaluate("rag_enabled", user)
            if result.value is True:
                enabled_count += 1

        print(f"    Ring: {ring.value:<15} | Rollout: {pct:>5.0f}% | "
              f"Users enabled: {enabled_count}/{len(users)}")

    # === Phase 5: Targeting demo ===
    print(f"\n{'─' * 60}")
    print("Phase 5: User Targeting Demo")
    print(f"{'─' * 60}")

    print(f"\n  Flag 'safety_filter_v2' targets: tier in [enterprise, pro]")
    for user in users[:8]:
        result = engine.evaluate("safety_filter_v2", user)
        print(f"    {user['user_id']} (tier={user['tier']:<12}): "
              f"value={result.value}, reason={result.reason}")

    # === Summary ===
    print(f"\n{'=' * 60}")
    print("SIMULATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total flag evaluations: {len(engine.evaluation_log)}")
    print(f"  Total A/B assignments: {len(engine.assignments)}")
    print(f"  Flags registered: {len(engine.flags)}")

    reason_counts: Dict[str, int] = {}
    for ev in engine.evaluation_log:
        reason_counts[ev.reason] = reason_counts.get(ev.reason, 0) + 1
    print(f"\n  Evaluation reasons:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"    {reason:<20}: {count}")

    print(f"\n{'=' * 60}")
    print("Simulation complete.")


if __name__ == "__main__":
    run_simulation()
