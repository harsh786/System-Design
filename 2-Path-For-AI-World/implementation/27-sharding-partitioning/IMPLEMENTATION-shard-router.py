"""
Shard Router for Vector Databases
Implements query routing patterns: single-shard, fanout, two-stage, hierarchical, federated.
"""

import asyncio
import hashlib
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import logging
import heapq

logger = logging.getLogger(__name__)


# =============================================================================
# Core Models
# =============================================================================

class RoutingStrategy(Enum):
    SINGLE_SHARD = "single_shard"
    FANOUT = "fanout"
    TWO_STAGE = "two_stage"
    HIERARCHICAL = "hierarchical"
    FEDERATED = "federated"


class ShardStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ISOLATED = "isolated"  # hot shard pulled from rotation
    OFFLINE = "offline"


@dataclass
class ShardInfo:
    shard_id: str
    status: ShardStatus
    endpoint: str
    vector_count: int = 0
    replica_count: int = 1
    labels: Dict[str, str] = field(default_factory=dict)
    tenants: Set[str] = field(default_factory=set)
    domains: Set[str] = field(default_factory=set)


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: Dict[str, Any]
    shard_id: str


@dataclass
class RoutingDecision:
    strategy: RoutingStrategy
    target_shards: List[str]
    reason: str
    estimated_latency_ms: float


@dataclass
class ShardMetrics:
    shard_id: str
    avg_latency_ms: float
    p99_latency_ms: float
    qps: float
    error_rate: float
    last_updated: datetime


@dataclass
class FanoutConfig:
    oversampling_factor: int = 3
    timeout_ms: int = 500
    max_parallel_shards: int = 50
    hedged_request_threshold_ms: int = 200  # send hedge after this delay


# =============================================================================
# Shard Registry
# =============================================================================

class ShardRegistry:
    """Maintains shard topology and routing maps."""

    def __init__(self):
        self.shards: Dict[str, ShardInfo] = {}
        self.tenant_shard_map: Dict[str, List[str]] = {}
        self.domain_shard_map: Dict[str, List[str]] = {}
        self._metrics: Dict[str, ShardMetrics] = {}
        self._latency_window: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    def register_shard(self, shard: ShardInfo):
        self.shards[shard.shard_id] = shard
        for tenant in shard.tenants:
            self.tenant_shard_map.setdefault(tenant, []).append(shard.shard_id)
        for domain in shard.domains:
            self.domain_shard_map.setdefault(domain, []).append(shard.shard_id)

    def get_healthy_shards(self) -> List[ShardInfo]:
        return [s for s in self.shards.values() if s.status == ShardStatus.HEALTHY]

    def get_shards_for_tenant(self, tenant_id: str) -> List[str]:
        return self.tenant_shard_map.get(tenant_id, [])

    def get_shards_for_domain(self, domain: str) -> List[str]:
        return self.domain_shard_map.get(domain, [])

    def record_latency(self, shard_id: str, latency_ms: float, is_error: bool = False):
        now = time.time()
        self._latency_window[shard_id].append((now, latency_ms))
        # Prune old entries (keep last 5 minutes)
        cutoff = now - 300
        self._latency_window[shard_id] = [
            (t, l) for t, l in self._latency_window[shard_id] if t > cutoff
        ]

    def get_shard_metrics(self, shard_id: str) -> ShardMetrics:
        entries = self._latency_window.get(shard_id, [])
        if not entries:
            return ShardMetrics(shard_id=shard_id, avg_latency_ms=0, p99_latency_ms=0,
                                qps=0, error_rate=0, last_updated=datetime.utcnow())
        latencies = [l for _, l in entries]
        latencies.sort()
        return ShardMetrics(
            shard_id=shard_id,
            avg_latency_ms=sum(latencies) / len(latencies),
            p99_latency_ms=latencies[int(len(latencies) * 0.99)] if len(latencies) > 10 else latencies[-1],
            qps=len(entries) / 300.0,
            error_rate=0.0,
            last_updated=datetime.utcnow(),
        )

    def detect_hot_shards(self, qps_threshold: float = 500, latency_threshold_ms: float = 200) -> List[str]:
        """Identify shards that are overloaded."""
        hot = []
        for shard_id in self.shards:
            metrics = self.get_shard_metrics(shard_id)
            if metrics.qps > qps_threshold or metrics.p99_latency_ms > latency_threshold_ms:
                hot.append(shard_id)
        return hot

    def isolate_shard(self, shard_id: str):
        """Pull a hot shard from normal rotation; serve from replicas only."""
        if shard_id in self.shards:
            self.shards[shard_id].status = ShardStatus.ISOLATED
            logger.warning(f"Isolated hot shard: {shard_id}")


# =============================================================================
# Query Router
# =============================================================================

@dataclass
class QueryContext:
    vector: List[float]
    top_k: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[str] = None
    domain: Optional[str] = None
    query_text: Optional[str] = None
    routing_hint: Optional[RoutingStrategy] = None
    timeout_ms: int = 1000


class ShardRouter:
    """
    Main router that selects routing strategy and executes queries across shards.
    """

    def __init__(self, registry: ShardRegistry, fanout_config: FanoutConfig = None):
        self.registry = registry
        self.fanout_config = fanout_config or FanoutConfig()
        self.domain_classifier: Optional[Callable[[str], str]] = None
        self._search_backends: Dict[str, Callable] = {}  # shard_id -> search function

    def register_search_backend(self, shard_id: str, search_fn: Callable):
        """Register the actual search function for a shard."""
        self._search_backends[shard_id] = search_fn

    def set_domain_classifier(self, classifier: Callable[[str], str]):
        self.domain_classifier = classifier

    # =========================================================================
    # Strategy Selection
    # =========================================================================

    def select_strategy(self, ctx: QueryContext) -> RoutingDecision:
        """Automatically select the best routing strategy for a query."""
        if ctx.routing_hint:
            strategy = ctx.routing_hint
        elif ctx.tenant_id and self.registry.get_shards_for_tenant(ctx.tenant_id):
            strategy = RoutingStrategy.SINGLE_SHARD
        elif ctx.domain and self.registry.get_shards_for_domain(ctx.domain):
            strategy = RoutingStrategy.SINGLE_SHARD
        elif ctx.query_text and self.domain_classifier:
            strategy = RoutingStrategy.TWO_STAGE
        else:
            strategy = RoutingStrategy.FANOUT

        target_shards = self._resolve_targets(strategy, ctx)
        estimated_latency = self._estimate_latency(strategy, target_shards)

        return RoutingDecision(
            strategy=strategy,
            target_shards=target_shards,
            reason=f"Auto-selected {strategy.value} based on query context",
            estimated_latency_ms=estimated_latency,
        )

    def _resolve_targets(self, strategy: RoutingStrategy, ctx: QueryContext) -> List[str]:
        if strategy == RoutingStrategy.SINGLE_SHARD:
            if ctx.tenant_id:
                shards = self.registry.get_shards_for_tenant(ctx.tenant_id)
                return shards[:1] if shards else []
            if ctx.domain:
                shards = self.registry.get_shards_for_domain(ctx.domain)
                return shards[:1] if shards else []
        elif strategy == RoutingStrategy.TWO_STAGE:
            if ctx.query_text and self.domain_classifier:
                domain = self.domain_classifier(ctx.query_text)
                shards = self.registry.get_shards_for_domain(domain)
                return shards if shards else [s.shard_id for s in self.registry.get_healthy_shards()]
        elif strategy == RoutingStrategy.FANOUT:
            return [s.shard_id for s in self.registry.get_healthy_shards()]
        elif strategy == RoutingStrategy.HIERARCHICAL:
            return [s.shard_id for s in self.registry.get_healthy_shards()]

        return [s.shard_id for s in self.registry.get_healthy_shards()]

    def _estimate_latency(self, strategy: RoutingStrategy, target_shards: List[str]) -> float:
        if not target_shards:
            return 0.0
        per_shard_latencies = []
        for sid in target_shards:
            m = self.registry.get_shard_metrics(sid)
            per_shard_latencies.append(m.p99_latency_ms if m.p99_latency_ms > 0 else 50.0)

        if strategy == RoutingStrategy.SINGLE_SHARD:
            return per_shard_latencies[0] if per_shard_latencies else 50.0
        elif strategy == RoutingStrategy.FANOUT:
            return max(per_shard_latencies)  # tail latency
        elif strategy == RoutingStrategy.TWO_STAGE:
            return 20.0 + max(per_shard_latencies)  # classifier + search
        elif strategy == RoutingStrategy.HIERARCHICAL:
            return 30.0 + max(per_shard_latencies[:3])  # coarse + fine on top shards
        return max(per_shard_latencies)

    # =========================================================================
    # Query Execution
    # =========================================================================

    async def execute(self, ctx: QueryContext) -> List[SearchResult]:
        """Route and execute a query."""
        decision = self.select_strategy(ctx)
        logger.info(f"Routing: {decision.strategy.value} -> {len(decision.target_shards)} shards")

        if decision.strategy == RoutingStrategy.SINGLE_SHARD:
            return await self._execute_single_shard(ctx, decision.target_shards)
        elif decision.strategy == RoutingStrategy.FANOUT:
            return await self._execute_fanout(ctx, decision.target_shards)
        elif decision.strategy == RoutingStrategy.TWO_STAGE:
            return await self._execute_two_stage(ctx, decision.target_shards)
        elif decision.strategy == RoutingStrategy.HIERARCHICAL:
            return await self._execute_hierarchical(ctx, decision.target_shards)
        elif decision.strategy == RoutingStrategy.FEDERATED:
            return await self._execute_federated(ctx, decision.target_shards)
        else:
            return await self._execute_fanout(ctx, decision.target_shards)

    async def _execute_single_shard(self, ctx: QueryContext, shards: List[str]) -> List[SearchResult]:
        """Direct query to a single shard."""
        if not shards:
            return []
        shard_id = shards[0]
        return await self._search_shard(shard_id, ctx.vector, ctx.top_k, ctx.filters)

    async def _execute_fanout(self, ctx: QueryContext, shards: List[str]) -> List[SearchResult]:
        """
        Scatter-gather: query all shards in parallel, merge results.
        Uses oversampling to compensate for local top-k recall loss.
        """
        local_k = ctx.top_k * self.fanout_config.oversampling_factor

        async def search_with_timeout(shard_id: str) -> List[SearchResult]:
            try:
                return await asyncio.wait_for(
                    self._search_shard(shard_id, ctx.vector, local_k, ctx.filters),
                    timeout=self.fanout_config.timeout_ms / 1000.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Shard {shard_id} timed out after {self.fanout_config.timeout_ms}ms")
                return []
            except Exception as e:
                logger.error(f"Shard {shard_id} error: {e}")
                return []

        # Limit parallelism
        semaphore = asyncio.Semaphore(self.fanout_config.max_parallel_shards)

        async def bounded_search(shard_id: str):
            async with semaphore:
                return await search_with_timeout(shard_id)

        tasks = [bounded_search(sid) for sid in shards]
        all_results = await asyncio.gather(*tasks)

        return self._merge_results(all_results, ctx.top_k)

    async def _execute_two_stage(self, ctx: QueryContext, shards: List[str]) -> List[SearchResult]:
        """
        Stage 1: Classify query to determine relevant shards.
        Stage 2: Search only those shards.
        """
        # Stage 1: Already done in _resolve_targets via domain_classifier
        # Stage 2: Search the selected shards (subset of all)
        if len(shards) == 1:
            return await self._execute_single_shard(ctx, shards)
        else:
            return await self._execute_fanout(ctx, shards)

    async def _execute_hierarchical(self, ctx: QueryContext, shards: List[str]) -> List[SearchResult]:
        """
        Level 1: Search coarse index (centroid/summary per shard) to identify top shards.
        Level 2: Full search on selected shards only.
        """
        # Level 1: Score each shard by centroid similarity (simulated)
        shard_scores = []
        for shard_id in shards:
            # In production: compare query vector to shard centroid
            # Simulated with random scores
            score = await self._get_shard_centroid_score(shard_id, ctx.vector)
            shard_scores.append((score, shard_id))

        # Select top-N shards (e.g., top 20%)
        shard_scores.sort(reverse=True)
        num_selected = max(1, len(shards) // 5)
        selected_shards = [sid for _, sid in shard_scores[:num_selected]]

        logger.info(f"Hierarchical: selected {num_selected}/{len(shards)} shards after coarse search")

        # Level 2: Fine search on selected shards
        return await self._execute_fanout(ctx, selected_shards)

    async def _execute_federated(self, ctx: QueryContext, shards: List[str]) -> List[SearchResult]:
        """
        Query multiple heterogeneous backends and merge with reciprocal rank fusion.
        """
        # Vector search
        vector_results = await self._execute_fanout(ctx, shards)

        # Keyword search (simulated)
        keyword_results = await self._keyword_search(ctx.query_text or "", ctx.top_k, ctx.filters)

        # Merge via Reciprocal Rank Fusion
        return self._reciprocal_rank_fusion(
            [vector_results, keyword_results],
            k=60,
            final_top_k=ctx.top_k,
        )

    # =========================================================================
    # Search Backend & Merging
    # =========================================================================

    async def _search_shard(self, shard_id: str, vector: List[float],
                            top_k: int, filters: Dict[str, Any]) -> List[SearchResult]:
        """Execute search on a single shard."""
        start = time.time()
        search_fn = self._search_backends.get(shard_id)
        if not search_fn:
            # Simulated search for demonstration
            await asyncio.sleep(random.uniform(0.01, 0.05))
            results = [
                SearchResult(
                    id=f"{shard_id}_doc_{i}",
                    score=random.uniform(0.5, 0.99),
                    metadata={"shard": shard_id},
                    shard_id=shard_id,
                )
                for i in range(min(top_k, 5))
            ]
        else:
            raw = await search_fn(vector, top_k, filters)
            results = [
                SearchResult(id=r["id"], score=r["score"], metadata=r.get("metadata", {}), shard_id=shard_id)
                for r in raw
            ]

        latency = (time.time() - start) * 1000
        self.registry.record_latency(shard_id, latency)
        return results

    async def _get_shard_centroid_score(self, shard_id: str, vector: List[float]) -> float:
        """Get similarity between query and shard centroid. Simulated."""
        # In production: maintain per-shard centroid vectors and compute cosine sim
        return random.uniform(0.3, 0.95)

    async def _keyword_search(self, query_text: str, top_k: int,
                              filters: Dict[str, Any]) -> List[SearchResult]:
        """Keyword/BM25 search backend. Simulated."""
        await asyncio.sleep(0.02)
        return [
            SearchResult(
                id=f"kw_doc_{i}", score=random.uniform(0.4, 0.9),
                metadata={"source": "keyword"}, shard_id="keyword_index",
            )
            for i in range(min(top_k, 5))
        ]

    def _merge_results(self, shard_results: List[List[SearchResult]], top_k: int) -> List[SearchResult]:
        """Merge results from multiple shards, deduplicate, return global top-k."""
        seen_ids = set()
        merged = []
        for results in shard_results:
            for r in results:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    merged.append(r)
        merged.sort(key=lambda x: x.score, reverse=True)
        return merged[:top_k]

    def _reciprocal_rank_fusion(
        self, result_lists: List[List[SearchResult]], k: int = 60, final_top_k: int = 10
    ) -> List[SearchResult]:
        """
        Reciprocal Rank Fusion: merges multiple ranked lists.
        RRF score = sum(1 / (k + rank_i)) for each list where doc appears.
        """
        rrf_scores: Dict[str, float] = defaultdict(float)
        result_map: Dict[str, SearchResult] = {}

        for result_list in result_lists:
            for rank, result in enumerate(result_list):
                rrf_scores[result.id] += 1.0 / (k + rank + 1)
                if result.id not in result_map:
                    result_map[result.id] = result

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        final_results = []
        for doc_id in sorted_ids[:final_top_k]:
            r = result_map[doc_id]
            final_results.append(SearchResult(
                id=r.id,
                score=rrf_scores[doc_id],
                metadata={**r.metadata, "rrf_score": rrf_scores[doc_id]},
                shard_id=r.shard_id,
            ))
        return final_results

    # =========================================================================
    # Hot Shard Management
    # =========================================================================

    def detect_and_isolate_hot_shards(self, qps_threshold: float = 500,
                                       latency_threshold_ms: float = 300) -> List[str]:
        """Detect overloaded shards and isolate them."""
        hot = self.registry.detect_hot_shards(qps_threshold, latency_threshold_ms)
        for shard_id in hot:
            self.registry.isolate_shard(shard_id)
        return hot

    def get_routing_metrics(self) -> Dict[str, Any]:
        """Get per-shard routing metrics for observability."""
        metrics = {}
        for shard_id in self.registry.shards:
            m = self.registry.get_shard_metrics(shard_id)
            metrics[shard_id] = {
                "avg_latency_ms": m.avg_latency_ms,
                "p99_latency_ms": m.p99_latency_ms,
                "qps": m.qps,
                "status": self.registry.shards[shard_id].status.value,
            }
        return metrics


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    # Setup registry
    registry = ShardRegistry()
    for i in range(5):
        shard = ShardInfo(
            shard_id=f"shard_{i}",
            status=ShardStatus.HEALTHY,
            endpoint=f"http://vectordb-{i}:6333",
            vector_count=1_000_000,
            tenants={f"tenant_{i}", f"tenant_{i+5}"},
            domains={"engineering" if i < 2 else "legal" if i < 4 else "medical"},
        )
        registry.register_shard(shard)

    # Create router
    router = ShardRouter(registry, FanoutConfig(oversampling_factor=3, timeout_ms=500))
    router.set_domain_classifier(lambda text: "engineering" if "api" in text.lower() else "legal")

    # Single-shard query (tenant-routed)
    ctx = QueryContext(
        vector=[0.1] * 1536,
        top_k=10,
        tenant_id="tenant_0",
    )
    results = await router.execute(ctx)
    print(f"Single-shard results: {len(results)}")

    # Fanout query (no routing key)
    ctx = QueryContext(vector=[0.1] * 1536, top_k=10)
    results = await router.execute(ctx)
    print(f"Fanout results: {len(results)}")

    # Two-stage query (domain classification)
    ctx = QueryContext(
        vector=[0.1] * 1536,
        top_k=10,
        query_text="How to design an API gateway?",
    )
    results = await router.execute(ctx)
    print(f"Two-stage results: {len(results)}")

    # Metrics
    metrics = router.get_routing_metrics()
    for shard_id, m in metrics.items():
        print(f"  {shard_id}: avg={m['avg_latency_ms']:.1f}ms, qps={m['qps']:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
