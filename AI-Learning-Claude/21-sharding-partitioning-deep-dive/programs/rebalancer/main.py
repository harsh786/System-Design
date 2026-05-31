"""
Shard Rebalancer: Simulates zero-downtime shard rebalancing.
Creates imbalanced shards and demonstrates rebalancing operations.
"""

import time
import random
import numpy as np
from dataclasses import dataclass, field
from enum import Enum


class RebalancePhase(Enum):
    PREPARE = "prepare"
    DUAL_WRITE = "dual_write"
    COPY = "background_copy"
    VERIFY = "verify"
    SWITCH = "switch_routing"
    DRAIN = "drain"
    CLEANUP = "cleanup"


@dataclass
class ShardMetrics:
    vector_count: int = 0
    memory_percent: float = 0.0
    p95_latency_ms: float = 0.0
    qps: float = 0.0


@dataclass
class Shard:
    id: str
    vectors: list = field(default_factory=list)
    is_primary: bool = True

    @property
    def size(self):
        return len(self.vectors)

    @property
    def metrics(self) -> ShardMetrics:
        count = self.size
        return ShardMetrics(
            vector_count=count,
            memory_percent=min(100, count / 10_000 * 100),  # 10K = 100%
            p95_latency_ms=5 + (count / 1000) * 2,  # Latency grows with size
            qps=max(10, 500 - count / 50),
        )

    def insert(self, vector):
        self.vectors.append(vector)

    def remove_batch(self, ids_to_remove: set):
        self.vectors = [v for v in self.vectors if v["id"] not in ids_to_remove]


class Rebalancer:
    def __init__(self):
        self.shards: dict[str, Shard] = {}
        self.routing_table: dict[str, str] = {}  # vector_id → shard_id
        self.phase_log: list = []

    def create_imbalanced_shards(self, total_vectors: int = 30_000):
        """Create 3 shards with 60%/30%/10% distribution."""
        distributions = {"shard_1": 0.60, "shard_2": 0.30, "shard_3": 0.10}

        for shard_id in distributions:
            self.shards[shard_id] = Shard(id=shard_id)

        for i in range(total_vectors):
            r = random.random()
            if r < 0.60:
                target = "shard_1"
            elif r < 0.90:
                target = "shard_2"
            else:
                target = "shard_3"

            vector = {"id": f"vec_{i:06d}", "data": np.random.randn(32).astype(np.float32)}
            self.shards[target].insert(vector)
            self.routing_table[vector["id"]] = target

    def print_distribution(self, title: str):
        """Print current shard distribution."""
        total = sum(s.size for s in self.shards.values())
        print(f"\n  {title}")
        print(f"  {'─'*50}")
        for shard_id, shard in sorted(self.shards.items()):
            pct = shard.size / total * 100
            bar = "█" * int(pct / 2)
            m = shard.metrics
            print(f"  {shard_id}: {shard.size:>6,} vectors ({pct:>5.1f}%) {bar}")
            print(f"           mem={m.memory_percent:.0f}%, p95={m.p95_latency_ms:.0f}ms")

    def check_imbalance(self) -> dict:
        """Detect imbalance and recommend action."""
        sizes = {sid: s.size for sid, s in self.shards.items()}
        avg = sum(sizes.values()) / len(sizes)
        max_shard = max(sizes, key=sizes.get)
        min_shard = min(sizes, key=sizes.get)
        ratio = sizes[max_shard] / max(sizes[min_shard], 1)

        recommendations = []
        if ratio > 2.0:
            recommendations.append(f"SPLIT {max_shard} (ratio={ratio:.1f}x)")
        if sizes[min_shard] < avg * 0.3:
            recommendations.append(f"MERGE {min_shard} into another shard")

        return {
            "imbalance_ratio": ratio,
            "max_shard": max_shard,
            "min_shard": min_shard,
            "recommendations": recommendations,
        }

    def split_shard(self, shard_id: str) -> str:
        """Split a shard into two with zero downtime."""
        source = self.shards[shard_id]
        new_shard_id = f"{shard_id}_b"
        total_steps = 7
        latencies_during = []

        print(f"\n  SPLITTING: {shard_id} ({source.size:,} vectors) → {shard_id} + {new_shard_id}")
        print(f"  {'─'*50}")

        # Phase 1: Create new shard
        self._log_phase(RebalancePhase.PREPARE, "Creating new shard")
        self.shards[new_shard_id] = Shard(id=new_shard_id)
        time.sleep(0.05)
        print(f"  [1/{total_steps}] ✓ Created {new_shard_id}")

        # Phase 2: Enable dual-write
        self._log_phase(RebalancePhase.DUAL_WRITE, "Enabling dual-write")
        time.sleep(0.05)
        print(f"  [2/{total_steps}] ✓ Dual-write enabled (new writes go to both)")

        # Phase 3: Background copy (move half the vectors)
        self._log_phase(RebalancePhase.COPY, "Copying vectors")
        vectors_to_move = source.vectors[source.size // 2:]
        moved_count = 0
        batch_size = 1000

        for i in range(0, len(vectors_to_move), batch_size):
            batch = vectors_to_move[i:i + batch_size]
            for v in batch:
                self.shards[new_shard_id].insert(v)
                moved_count += 1
            # Simulate latency measurement during copy
            latencies_during.append(source.metrics.p95_latency_ms * random.uniform(0.9, 1.3))
            time.sleep(0.01)

        pct_done = moved_count / len(vectors_to_move) * 100
        print(f"  [3/{total_steps}] ✓ Copied {moved_count:,} vectors ({pct_done:.0f}%)")

        # Phase 4: Verify
        self._log_phase(RebalancePhase.VERIFY, "Verifying data integrity")
        expected = len(vectors_to_move)
        actual = self.shards[new_shard_id].size
        verified = expected == actual
        time.sleep(0.05)
        print(f"  [4/{total_steps}] ✓ Verified: {actual:,} vectors (match={verified})")

        # Phase 5: Switch routing
        self._log_phase(RebalancePhase.SWITCH, "Switching routing table")
        moved_ids = {v["id"] for v in vectors_to_move}
        for vid in moved_ids:
            self.routing_table[vid] = new_shard_id
        time.sleep(0.05)
        print(f"  [5/{total_steps}] ✓ Routing switched ({len(moved_ids):,} entries updated)")

        # Phase 6: Drain
        self._log_phase(RebalancePhase.DRAIN, "Stopping dual-write, draining")
        time.sleep(0.05)
        print(f"  [6/{total_steps}] ✓ Dual-write stopped, old shard drained")

        # Phase 7: Cleanup
        self._log_phase(RebalancePhase.CLEANUP, "Removing moved vectors from source")
        source.remove_batch(moved_ids)
        time.sleep(0.05)
        print(f"  [7/{total_steps}] ✓ Cleanup complete")

        # Report latency during rebalancing
        print(f"\n  Latency during rebalancing:")
        print(f"    Avg P95: {np.mean(latencies_during):.1f}ms (normal: {source.metrics.p95_latency_ms:.1f}ms)")
        print(f"    Max P95: {max(latencies_during):.1f}ms")
        print(f"    Service disruption: NONE (zero-downtime)")

        return new_shard_id

    def merge_shards(self, source_id: str, target_id: str):
        """Merge source shard into target shard."""
        source = self.shards[source_id]
        target = self.shards[target_id]

        print(f"\n  MERGING: {source_id} ({source.size:,}) → {target_id} ({target.size:,})")
        print(f"  {'─'*50}")

        # Copy all vectors from source to target
        for v in source.vectors:
            target.insert(v)
            self.routing_table[v["id"]] = target_id

        # Remove source shard
        del self.shards[source_id]
        print(f"  ✓ Merged {source.size:,} vectors into {target_id}")
        print(f"  ✓ Deleted {source_id}")

    def _log_phase(self, phase: RebalancePhase, description: str):
        self.phase_log.append({
            "phase": phase.value,
            "description": description,
            "timestamp": time.time(),
        })


def main():
    print("=" * 60)
    print("  SHARD REBALANCER: Zero-Downtime Rebalancing Demo")
    print("=" * 60)

    rebalancer = Rebalancer()

    # Step 1: Create imbalanced shards
    print("\n[STEP 1] Creating imbalanced shards (60%/30%/10%)...")
    rebalancer.create_imbalanced_shards(total_vectors=30_000)
    rebalancer.print_distribution("BEFORE Rebalancing")

    # Step 2: Detect imbalance
    print("\n[STEP 2] Checking for imbalance...")
    analysis = rebalancer.check_imbalance()
    print(f"  Imbalance ratio: {analysis['imbalance_ratio']:.1f}x")
    print(f"  Heaviest shard: {analysis['max_shard']}")
    print(f"  Lightest shard: {analysis['min_shard']}")
    for rec in analysis["recommendations"]:
        print(f"  → Recommendation: {rec}")

    # Step 3: Execute split on heaviest shard
    print(f"\n[STEP 3] Executing rebalancing...")
    new_shard = rebalancer.split_shard(analysis["max_shard"])

    # Step 4: Show result
    rebalancer.print_distribution("AFTER Rebalancing")

    # Step 5: Verify final state
    print(f"\n[STEP 4] Final verification:")
    total_vectors = sum(s.size for s in rebalancer.shards.values())
    print(f"  Total vectors: {total_vectors:,} (should be 30,000)")
    print(f"  Shards: {len(rebalancer.shards)}")

    new_analysis = rebalancer.check_imbalance()
    print(f"  New imbalance ratio: {new_analysis['imbalance_ratio']:.1f}x (was {analysis['imbalance_ratio']:.1f}x)")
    print(f"  Improvement: {(1 - new_analysis['imbalance_ratio']/analysis['imbalance_ratio'])*100:.0f}% more balanced")

    print(f"\n  Rebalancing phases executed:")
    for entry in rebalancer.phase_log:
        print(f"    [{entry['phase']:>15}] {entry['description']}")


if __name__ == "__main__":
    main()
