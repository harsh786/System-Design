"""
Shard Simulator: Demonstrates sharding strategies for vector databases.
Distributes 100K simulated vectors across 5 shards and shows query routing.
"""

import hashlib
import time
import random
import numpy as np
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Vector:
    id: str
    tenant_id: str
    topic: str
    embedding: np.ndarray
    created_at: float


@dataclass
class Shard:
    id: int
    vectors: list = field(default_factory=list)
    query_count: int = 0

    @property
    def size(self):
        return len(self.vectors)

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list:
        """Brute-force search within this shard."""
        self.query_count += 1
        if not self.vectors:
            return []
        # Compute cosine similarities
        embeddings = np.array([v.embedding for v in self.vectors])
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        similarities = (embeddings / norms) @ query_norm
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [(self.vectors[i].id, float(similarities[i])) for i in top_indices]


class ShardSimulator:
    TENANTS = ["acme", "beta", "corp", "delta", "echo"]
    TOPICS = ["engineering", "sales", "legal", "marketing", "product"]

    def __init__(self, num_shards: int = 5, num_vectors: int = 100_000, dims: int = 64):
        self.num_shards = num_shards
        self.dims = dims
        self.vectors = self._generate_vectors(num_vectors)
        print(f"Generated {num_vectors:,} vectors ({dims} dims) for {num_shards} shards\n")

    def _generate_vectors(self, n: int) -> list:
        vectors = []
        for i in range(n):
            tenant = random.choice(self.TENANTS)
            topic = random.choice(self.TOPICS)
            # Bias embeddings slightly by topic for realistic clustering
            topic_offset = np.zeros(self.dims)
            topic_offset[self.TOPICS.index(topic) * (self.dims // 5)] = 1.0
            embedding = np.random.randn(self.dims).astype(np.float32) + topic_offset
            vectors.append(Vector(
                id=f"doc_{i:06d}",
                tenant_id=tenant,
                topic=topic,
                embedding=embedding,
                created_at=time.time() - random.uniform(0, 365 * 86400),
            ))
        return vectors

    def _create_shards(self) -> list:
        return [Shard(id=i) for i in range(self.num_shards)]

    # --- Sharding Strategies ---

    def shard_by_hash(self) -> list:
        """Hash-based: uniform distribution, no routing optimization."""
        shards = self._create_shards()
        for v in self.vectors:
            h = int(hashlib.md5(v.id.encode()).hexdigest(), 16)
            shards[h % self.num_shards].vectors.append(v)
        return shards

    def shard_by_tenant(self) -> list:
        """Tenant-based: each tenant gets a shard."""
        shards = self._create_shards()
        tenant_map = {t: i for i, t in enumerate(self.TENANTS)}
        for v in self.vectors:
            shards[tenant_map[v.tenant_id]].vectors.append(v)
        return shards

    def shard_by_topic(self) -> list:
        """Topic-based: each topic gets a shard."""
        shards = self._create_shards()
        topic_map = {t: i for i, t in enumerate(self.TOPICS)}
        for v in self.vectors:
            shards[topic_map[v.topic]].vectors.append(v)
        return shards

    # --- Query Simulation ---

    def simulate_queries(self, shards: list, strategy_name: str, num_queries: int = 50):
        """Run queries and measure performance."""
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name}")
        print(f"{'='*60}")

        # Print shard distribution
        print("\nShard Distribution:")
        for shard in shards:
            bar = "█" * (shard.size // 2000)
            print(f"  Shard {shard.id}: {shard.size:>6,} vectors {bar}")

        # Simulate queries
        latencies = []
        shards_hit_per_query = []

        for _ in range(num_queries):
            query_tenant = random.choice(self.TENANTS)
            query_topic = random.choice(self.TOPICS)
            query_embedding = np.random.randn(self.dims).astype(np.float32)
            # Add topic bias to query
            query_embedding[self.TOPICS.index(query_topic) * (self.dims // 5)] += 1.0

            start = time.time()

            if strategy_name == "Hash (scatter-all)":
                # Must query ALL shards
                all_results = []
                for shard in shards:
                    all_results.extend(shard.search(query_embedding, top_k=10))
                all_results.sort(key=lambda x: x[1], reverse=True)
                results = all_results[:10]
                shards_hit = self.num_shards

            elif strategy_name == "Tenant (single-shard)":
                # Route to tenant's shard
                tenant_map = {t: i for i, t in enumerate(self.TENANTS)}
                target = shards[tenant_map[query_tenant]]
                results = target.search(query_embedding, top_k=10)
                shards_hit = 1

            elif strategy_name == "Topic (1-2 shards)":
                # Route to topic shard + maybe one neighbor
                topic_map = {t: i for i, t in enumerate(self.TOPICS)}
                primary = shards[topic_map[query_topic]]
                results = primary.search(query_embedding, top_k=10)
                shards_hit = 1
                # Check if results are good enough
                if results and results[-1][1] < 0.3:
                    # Also check neighbor shard
                    neighbor = shards[(topic_map[query_topic] + 1) % self.num_shards]
                    results.extend(neighbor.search(query_embedding, top_k=10))
                    results.sort(key=lambda x: x[1], reverse=True)
                    results = results[:10]
                    shards_hit = 2

            elapsed = (time.time() - start) * 1000
            latencies.append(elapsed)
            shards_hit_per_query.append(shards_hit)

        # Print results
        print(f"\nQuery Performance ({num_queries} queries):")
        print(f"  Avg latency:       {np.mean(latencies):.2f} ms")
        print(f"  P95 latency:       {np.percentile(latencies, 95):.2f} ms")
        print(f"  Avg shards/query:  {np.mean(shards_hit_per_query):.1f}")
        print(f"  Total shard hits:  {sum(s.query_count for s in shards)}")

        # Show query distribution across shards
        print(f"\n  Queries per shard:")
        for shard in shards:
            bar = "█" * (shard.query_count // 2)
            print(f"    Shard {shard.id}: {shard.query_count:>4} queries {bar}")

        return np.mean(latencies)


def main():
    print("=" * 60)
    print("  SHARD SIMULATOR: Vector Database Sharding Demo")
    print("=" * 60)

    sim = ShardSimulator(num_shards=5, num_vectors=100_000, dims=64)

    # Strategy 1: Hash-based (scatter-all)
    shards_hash = sim.shard_by_hash()
    lat_hash = sim.simulate_queries(shards_hash, "Hash (scatter-all)")

    # Strategy 2: Tenant-based (single-shard routing)
    shards_tenant = sim.shard_by_tenant()
    lat_tenant = sim.simulate_queries(shards_tenant, "Tenant (single-shard)")

    # Strategy 3: Topic-based (1-2 shard routing)
    shards_topic = sim.shard_by_topic()
    lat_topic = sim.simulate_queries(shards_topic, "Topic (1-2 shards)")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY: Latency Comparison")
    print(f"{'='*60}")
    print(f"  Hash (scatter-all):    {lat_hash:.2f} ms  (queries ALL {sim.num_shards} shards)")
    print(f"  Tenant (single-shard): {lat_tenant:.2f} ms  (queries 1 shard)")
    print(f"  Topic (1-2 shards):    {lat_topic:.2f} ms  (queries 1-2 shards)")
    print(f"\n  Speedup (tenant vs hash): {lat_hash/lat_tenant:.1f}x")
    print(f"  Speedup (topic vs hash):  {lat_hash/lat_topic:.1f}x")
    print(f"\n  Key insight: Choosing the right shard key eliminates scatter-gather")
    print(f"  and provides {sim.num_shards}x latency improvement!")


if __name__ == "__main__":
    main()
