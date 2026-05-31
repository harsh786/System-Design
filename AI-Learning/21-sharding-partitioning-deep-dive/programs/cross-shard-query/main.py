"""
Cross-Shard Query Simulator: Demonstrates scatter-gather and smart routing.
Creates 5 topic-based shards and compares query strategies.
"""

import time
import random
import numpy as np
from dataclasses import dataclass, field
from collections import defaultdict


TOPICS = ["ml_engineering", "web_development", "data_science", "devops", "security"]


@dataclass
class SearchResult:
    doc_id: str
    score: float
    shard_id: str
    topic: str


@dataclass
class Shard:
    id: str
    topic: str
    vectors: list = field(default_factory=list)
    centroid: np.ndarray = None

    def insert(self, doc_id: str, embedding: np.ndarray):
        self.vectors.append({"id": doc_id, "embedding": embedding})

    def compute_centroid(self):
        if self.vectors:
            embeddings = np.array([v["embedding"] for v in self.vectors])
            self.centroid = embeddings.mean(axis=0)

    def search(self, query: np.ndarray, top_k: int = 10) -> tuple:
        """Search shard, return results and simulated latency."""
        start = time.time()

        if not self.vectors:
            return [], 0

        embeddings = np.array([v["embedding"] for v in self.vectors])
        # Cosine similarity
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        similarities = (embeddings / norms) @ query_norm

        top_idx = np.argsort(similarities)[-top_k:][::-1]
        results = [
            SearchResult(
                doc_id=self.vectors[i]["id"],
                score=float(similarities[i]),
                shard_id=self.id,
                topic=self.topic,
            )
            for i in top_idx
        ]

        # Add realistic latency simulation (base + size-dependent)
        base_latency = 5 + len(self.vectors) / 2000  # ms
        jitter = random.uniform(0.8, 1.5)
        simulated_latency = base_latency * jitter

        actual_compute = (time.time() - start) * 1000
        total_latency = simulated_latency + actual_compute

        return results, total_latency


class CrossShardQueryEngine:
    def __init__(self, dims: int = 64):
        self.dims = dims
        self.shards: dict[str, Shard] = {}
        self._build_shards()

    def _build_shards(self):
        """Create 5 topic-based shards with 10K vectors each."""
        for i, topic in enumerate(TOPICS):
            shard = Shard(id=f"shard_{i}", topic=topic)

            # Create topic-specific bias vector
            topic_bias = np.zeros(self.dims)
            topic_bias[i * (self.dims // 5):(i + 1) * (self.dims // 5)] = 1.0

            for j in range(10_000):
                embedding = np.random.randn(self.dims).astype(np.float32) * 0.5 + topic_bias
                shard.insert(f"{topic}_doc_{j:05d}", embedding)

            shard.compute_centroid()
            self.shards[shard.id] = shard

        print(f"Created {len(self.shards)} shards × 10,000 vectors = 50,000 total\n")

    def _make_query(self, target_topic: str) -> np.ndarray:
        """Create a query embedding biased toward a topic."""
        topic_idx = TOPICS.index(target_topic)
        query = np.random.randn(self.dims).astype(np.float32) * 0.3
        query[topic_idx * (self.dims // 5):(topic_idx + 1) * (self.dims // 5)] += 2.0
        return query

    # --- Query Strategies ---

    def scatter_all(self, query: np.ndarray, top_k: int = 10) -> dict:
        """Query ALL shards (worst case: no routing)."""
        all_results = []
        shard_latencies = {}

        for shard in self.shards.values():
            results, latency = shard.search(query, top_k=top_k * 2)
            all_results.extend(results)
            shard_latencies[shard.id] = latency

        # Merge: take global top-K
        all_results.sort(key=lambda r: r.score, reverse=True)
        final = all_results[:top_k]

        # Total latency = max (parallel execution)
        total_latency = max(shard_latencies.values())

        return {
            "results": final,
            "shards_queried": len(self.shards),
            "total_latency_ms": total_latency,
            "shard_latencies": shard_latencies,
            "strategy": "scatter-all",
        }

    def smart_route(self, query: np.ndarray, top_k: int = 10, max_shards: int = 2) -> dict:
        """Route to most relevant shards based on centroid similarity."""
        # Compute similarity to each shard's centroid
        shard_scores = {}
        for shard in self.shards.values():
            sim = np.dot(query, shard.centroid) / (
                np.linalg.norm(query) * np.linalg.norm(shard.centroid) + 1e-10
            )
            shard_scores[shard.id] = sim

        # Pick top-N most relevant shards
        sorted_shards = sorted(shard_scores.items(), key=lambda x: x[1], reverse=True)
        target_shards = [self.shards[sid] for sid, _ in sorted_shards[:max_shards]]

        all_results = []
        shard_latencies = {}

        for shard in target_shards:
            results, latency = shard.search(query, top_k=top_k * 2)
            all_results.extend(results)
            shard_latencies[shard.id] = latency

        all_results.sort(key=lambda r: r.score, reverse=True)
        final = all_results[:top_k]

        total_latency = max(shard_latencies.values()) if shard_latencies else 0

        return {
            "results": final,
            "shards_queried": len(target_shards),
            "total_latency_ms": total_latency,
            "shard_latencies": shard_latencies,
            "pruned_shards": [sid for sid, _ in sorted_shards[max_shards:]],
            "strategy": "smart-route",
        }

    def single_shard(self, query: np.ndarray, shard_id: str, top_k: int = 10) -> dict:
        """Query exactly one shard (best case: perfect routing)."""
        shard = self.shards[shard_id]
        results, latency = shard.search(query, top_k=top_k)

        return {
            "results": results,
            "shards_queried": 1,
            "total_latency_ms": latency,
            "shard_latencies": {shard_id: latency},
            "strategy": "single-shard",
        }


def print_query_plan(result: dict, label: str):
    """Print query execution plan."""
    print(f"\n  Strategy: {label}")
    print(f"  {'─'*55}")
    print(f"  Shards queried: {result['shards_queried']}/{5}")
    print(f"  Total latency:  {result['total_latency_ms']:.1f} ms")

    if result["shard_latencies"]:
        print(f"  Per-shard latency:")
        for sid, lat in sorted(result["shard_latencies"].items()):
            bar = "█" * int(lat / 2)
            print(f"    {sid}: {lat:.1f}ms {bar}")

    if "pruned_shards" in result:
        print(f"  Pruned (skipped): {result['pruned_shards']}")

    print(f"  Top-3 results:")
    for r in result["results"][:3]:
        print(f"    {r.doc_id} (score={r.score:.3f}, shard={r.shard_id})")


def main():
    print("=" * 60)
    print("  CROSS-SHARD QUERY: Scatter-Gather vs Smart Routing")
    print("=" * 60)

    engine = CrossShardQueryEngine(dims=64)

    # Scenario 1: Query about ML engineering
    print("\n" + "=" * 60)
    print("  SCENARIO: Query about 'ML model deployment'")
    print("=" * 60)

    query = engine._make_query("ml_engineering")

    # Strategy A: Scatter-all (5 shards)
    result_all = engine.scatter_all(query, top_k=10)
    print_query_plan(result_all, "Scatter-All (query 5 shards)")

    # Strategy B: Smart routing (2 shards)
    result_smart = engine.smart_route(query, top_k=10, max_shards=2)
    print_query_plan(result_smart, "Smart Route (top-2 shards)")

    # Strategy C: Single shard (perfect routing)
    result_single = engine.single_shard(query, "shard_0", top_k=10)
    print_query_plan(result_single, "Single Shard (perfect routing)")

    # Comparison
    print(f"\n  {'─'*55}")
    print(f"  LATENCY COMPARISON:")
    print(f"    Scatter-all:    {result_all['total_latency_ms']:>6.1f} ms (5 shards)")
    print(f"    Smart route:    {result_smart['total_latency_ms']:>6.1f} ms (2 shards)")
    print(f"    Single shard:   {result_single['total_latency_ms']:>6.1f} ms (1 shard)")
    speedup = result_all['total_latency_ms'] / max(result_single['total_latency_ms'], 0.1)
    print(f"    Speedup (single vs scatter): {speedup:.1f}x")

    # Result quality comparison
    print(f"\n  RESULT QUALITY:")
    scores_all = [r.score for r in result_all["results"][:10]]
    scores_smart = [r.score for r in result_smart["results"][:10]]
    scores_single = [r.score for r in result_single["results"][:10]]
    print(f"    Scatter-all avg score:  {np.mean(scores_all):.4f}")
    print(f"    Smart route avg score:  {np.mean(scores_smart):.4f}")
    print(f"    Single shard avg score: {np.mean(scores_single):.4f}")

    # Scenario 2: Batch of queries showing statistics
    print(f"\n\n{'='*60}")
    print("  BATCH TEST: 100 queries with different topics")
    print(f"{'='*60}")

    strategies = {"scatter-all": [], "smart-route": [], "single-shard": []}

    for _ in range(100):
        topic = random.choice(TOPICS)
        q = engine._make_query(topic)
        topic_shard = f"shard_{TOPICS.index(topic)}"

        r1 = engine.scatter_all(q, top_k=10)
        r2 = engine.smart_route(q, top_k=10, max_shards=2)
        r3 = engine.single_shard(q, topic_shard, top_k=10)

        strategies["scatter-all"].append(r1["total_latency_ms"])
        strategies["smart-route"].append(r2["total_latency_ms"])
        strategies["single-shard"].append(r3["total_latency_ms"])

    print(f"\n  {'Strategy':<15} {'P50 (ms)':<10} {'P95 (ms)':<10} {'Shards/query':<13}")
    print(f"  {'─'*50}")
    for name, latencies in strategies.items():
        shards = {"scatter-all": 5, "smart-route": 2, "single-shard": 1}[name]
        print(f"  {name:<15} {np.percentile(latencies, 50):<10.1f} "
              f"{np.percentile(latencies, 95):<10.1f} {shards}")

    print(f"\n  Key Takeaways:")
    print(f"  • Smart routing (2 shards) gives ~{np.percentile(strategies['smart-route'], 95)/np.percentile(strategies['scatter-all'], 95)*100:.0f}% of scatter-all latency")
    print(f"  • Single-shard routing is fastest but requires perfect shard key")
    print(f"  • Tail latency (P95) grows with more shards due to straggler effect")


if __name__ == "__main__":
    main()
