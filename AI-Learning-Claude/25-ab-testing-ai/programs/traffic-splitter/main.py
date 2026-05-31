"""
Traffic Splitting for AI A/B Tests
===================================
Implements random, user-based, and session-based traffic splitting.
Verifies distribution and consistency.
"""

import hashlib
import random
from collections import Counter
from dataclasses import dataclass


@dataclass
class Variant:
    name: str
    weight: int  # percentage


class RandomSplitter:
    """Randomly assign each request to a variant."""

    def __init__(self, variants: list):
        self.variants = variants

    def assign(self, **kwargs) -> str:
        roll = random.random() * 100
        cumulative = 0
        for v in self.variants:
            cumulative += v.weight
            if roll < cumulative:
                return v.name
        return self.variants[-1].name


class UserBasedSplitter:
    """Deterministically assign based on user ID hash."""

    def __init__(self, variants: list, experiment_id: str = "exp_default"):
        self.variants = variants
        self.experiment_id = experiment_id

    def assign(self, user_id: str, **kwargs) -> str:
        hash_input = f"{user_id}:{self.experiment_id}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        cumulative = 0
        for v in self.variants:
            cumulative += v.weight
            if bucket < cumulative:
                return v.name
        return self.variants[-1].name


class SessionBasedSplitter:
    """Assign based on session ID — consistent within a session."""

    def __init__(self, variants: list, experiment_id: str = "exp_default"):
        self.variants = variants
        self.experiment_id = experiment_id

    def assign(self, session_id: str, **kwargs) -> str:
        hash_input = f"{session_id}:{self.experiment_id}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        cumulative = 0
        for v in self.variants:
            cumulative += v.weight
            if bucket < cumulative:
                return v.name
        return self.variants[-1].name


def test_distribution(splitter, assign_kwargs_list, expected_weights):
    """Test that actual distribution matches expected weights."""
    counts = Counter()
    for kwargs in assign_kwargs_list:
        variant = splitter.assign(**kwargs)
        counts[variant] += 1

    total = sum(counts.values())
    print(f"    Total requests: {total}")
    print(f"    Distribution:")
    for v_name, weight in expected_weights.items():
        actual_count = counts.get(v_name, 0)
        actual_pct = actual_count / total * 100
        diff = abs(actual_pct - weight)
        status = "✅" if diff < 3 else "⚠️"
        print(f"      {v_name}: {actual_count} ({actual_pct:.1f}%) — expected {weight}% {status}")
    return counts


def test_consistency(splitter, test_id, id_field, num_checks=10):
    """Verify same ID always gets same variant."""
    assignments = set()
    for _ in range(num_checks):
        result = splitter.assign(**{id_field: test_id})
        assignments.add(result)

    consistent = len(assignments) == 1
    variant = list(assignments)[0]
    return consistent, variant


def print_separator(title=""):
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}")
    else:
        print("-" * 60)


def main():
    print_separator("TRAFFIC SPLITTING FOR AI A/B TESTS")

    # Define variants
    variants_50_50 = [Variant("control", 50), Variant("treatment", 50)]
    variants_90_10 = [Variant("control", 90), Variant("treatment", 10)]
    variants_multi = [Variant("control", 34), Variant("treatment_a", 33), Variant("treatment_b", 33)]

    # ==========================================
    # Test 1: Random Splitting
    # ==========================================
    print_separator("TEST 1: Random Splitting (50/50)")

    splitter = RandomSplitter(variants_50_50)
    random.seed(42)

    # Generate 10000 random requests
    kwargs_list = [{} for _ in range(10000)]
    test_distribution(splitter, kwargs_list, {"control": 50, "treatment": 50})

    print("\n    Note: Each request is independently random.")
    print("    Same user may see different variants across requests!")
    print("    Use for: high-traffic, single-turn interactions")

    # ==========================================
    # Test 2: User-Based Splitting (50/50)
    # ==========================================
    print_separator("TEST 2: User-Based Splitting (50/50)")

    splitter = UserBasedSplitter(variants_50_50, "exp_prompt_v4")

    # Generate requests from 1000 users
    kwargs_list = [{"user_id": f"user_{i}"} for i in range(1000)]
    test_distribution(splitter, kwargs_list, {"control": 50, "treatment": 50})

    # Consistency check
    print("\n    Consistency check (same user → same variant):")
    for uid in ["user_42", "user_100", "user_777"]:
        consistent, variant = test_consistency(splitter, uid, "user_id")
        status = "✅ CONSISTENT" if consistent else "❌ INCONSISTENT"
        print(f"      {uid} → always '{variant}' {status}")

    print("\n    User-based splitting guarantees consistency:")
    print("    - user_42 will ALWAYS see the same variant")
    print("    - Even across different sessions/days")
    print("    - No database needed (purely hash-based)")

    # ==========================================
    # Test 3: User-Based Splitting (90/10 cautious)
    # ==========================================
    print_separator("TEST 3: User-Based Splitting (90/10 — Cautious Rollout)")

    splitter = UserBasedSplitter(variants_90_10, "exp_risky_model_change")

    kwargs_list = [{"user_id": f"user_{i}"} for i in range(1000)]
    test_distribution(splitter, kwargs_list, {"control": 90, "treatment": 10})

    print("\n    Use 90/10 for risky changes (model swaps, architecture changes)")
    print("    Limits blast radius: only 10% of users affected if treatment is bad")
    print("    Tradeoff: takes 9x longer to reach significance for treatment group")

    # ==========================================
    # Test 4: Session-Based Splitting
    # ==========================================
    print_separator("TEST 4: Session-Based Splitting (50/50)")

    splitter = SessionBasedSplitter(variants_50_50, "exp_agent_arch")

    # Simulate: user has multiple sessions
    print("\n    Same user, different sessions:")
    user_sessions = {
        "user_42": ["sess_42_001", "sess_42_002", "sess_42_003"],
        "user_99": ["sess_99_001", "sess_99_002", "sess_99_003"],
    }

    for user, sessions in user_sessions.items():
        print(f"\n      {user}:")
        for sess in sessions:
            variant = splitter.assign(session_id=sess)
            print(f"        {sess} → {variant}")

    print("\n    Session-based: consistent within a session, may vary across sessions")
    print("    Use for: multi-turn conversations, agent tasks")
    print("    Benefit: entire conversation uses same variant (no mid-chat switches)")

    # ==========================================
    # Test 5: Multi-Variant (A/B/C Test)
    # ==========================================
    print_separator("TEST 5: Multi-Variant Test (3 variants: 34/33/33)")

    splitter = UserBasedSplitter(variants_multi, "exp_model_comparison")

    kwargs_list = [{"user_id": f"user_{i}"} for i in range(3000)]
    test_distribution(
        splitter, kwargs_list,
        {"control": 34, "treatment_a": 33, "treatment_b": 33}
    )

    print("\n    Multi-variant tests compare 3+ options simultaneously")
    print("    Example: GPT-4 vs Claude vs GPT-4o")
    print("    Note: requires more samples (Bonferroni correction for pairwise tests)")

    # ==========================================
    # Test 6: Experiment Isolation (Layers)
    # ==========================================
    print_separator("TEST 6: Experiment Isolation (Independent Layers)")

    # Two experiments running simultaneously on different layers
    splitter_layer1 = UserBasedSplitter(variants_50_50, "layer1_retrieval")
    splitter_layer2 = UserBasedSplitter(variants_50_50, "layer2_prompting")

    print("\n    Two simultaneous experiments on different components:")
    print("    Layer 1: Retrieval experiment (hybrid vs semantic)")
    print("    Layer 2: Prompting experiment (v3 vs v4)")
    print("\n    User assignments (independent due to different hash salts):\n")

    print(f"    {'User':<12} {'Layer1 (Retrieval)':<22} {'Layer2 (Prompting)':<22}")
    print(f"    {'-'*56}")

    for i in range(10):
        uid = f"user_{i}"
        l1 = splitter_layer1.assign(user_id=uid)
        l2 = splitter_layer2.assign(user_id=uid)
        print(f"    {uid:<12} {l1:<22} {l2:<22}")

    print("\n    Assignments are INDEPENDENT across layers.")
    print("    Being in 'control' for Layer 1 says nothing about Layer 2.")
    print("    This allows running multiple experiments safely.")

    # ==========================================
    # Summary
    # ==========================================
    print_separator("TRAFFIC SPLITTING STRATEGY GUIDE")
    print("""
    ┌──────────────────┬────────────────────────────────────────────────┐
    │ Strategy         │ Best For                                       │
    ├──────────────────┼────────────────────────────────────────────────┤
    │ Random           │ High-traffic, single-turn, no consistency need │
    │ User-based       │ Most AI experiments (consistent experience)    │
    │ Session-based    │ Multi-turn conversations, agent workflows      │
    │ 90/10 split      │ Risky changes, new models, major rewrites      │
    │ Multi-variant    │ Comparing 3+ options (model selection)          │
    │ Layered          │ Running multiple experiments simultaneously     │
    └──────────────────┴────────────────────────────────────────────────┘
    """)


if __name__ == "__main__":
    main()
