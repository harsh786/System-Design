"""
Vector DB Evaluation Framework - Production Implementation
Comprehensive benchmarking: recall, latency, throughput, filtering, cost modeling
"""

import time
import json
import asyncio
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class RecallMetrics:
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    recall_at_50: float
    recall_at_100: float
    mrr: float  # Mean Reciprocal Rank
    ndcg_at_10: float  # Normalized Discounted Cumulative Gain


@dataclass
class LatencyMetrics:
    avg_ms: float
    p50_ms: float
    p75_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_ms: float


@dataclass
class ThroughputMetrics:
    qps_single_thread: float
    qps_concurrent: float
    concurrency_level: int
    total_queries: int
    total_time_seconds: float
    errors: int


@dataclass
class FilterPerformanceMetrics:
    filter_type: str
    selectivity: float  # Fraction of data matching filter
    latency: LatencyMetrics
    recall: float
    result_count_avg: float


@dataclass
class UpdateDeleteMetrics:
    insert_qps: float
    update_qps: float
    delete_qps: float
    insert_latency: LatencyMetrics
    compaction_time_seconds: float
    recall_after_deletes: float
    recall_degradation: float


@dataclass
class MultiTenancyMetrics:
    tenant_count: int
    vectors_per_tenant: int
    cross_tenant_isolation: bool  # True if results never leak across tenants
    latency_by_tenant_size: dict[str, LatencyMetrics]  # "small"/"medium"/"large" -> latency
    overhead_per_tenant_mb: float


@dataclass
class MemoryMetrics:
    total_memory_mb: float
    index_memory_mb: float
    vector_storage_mb: float
    metadata_memory_mb: float
    overhead_mb: float
    bytes_per_vector: float


@dataclass
class CostModel:
    provider: str
    monthly_cost_usd: float
    cost_per_million_vectors: float
    cost_per_million_queries: float
    storage_cost_per_gb: float
    compute_cost_per_hour: float
    assumptions: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    db_name: str
    timestamp: datetime
    dataset_info: dict[str, Any]
    recall: Optional[RecallMetrics] = None
    latency: Optional[LatencyMetrics] = None
    throughput: Optional[ThroughputMetrics] = None
    filter_performance: list[FilterPerformanceMetrics] = field(default_factory=list)
    update_delete: Optional[UpdateDeleteMetrics] = None
    multi_tenancy: Optional[MultiTenancyMetrics] = None
    memory: Optional[MemoryMetrics] = None
    cost: Optional[CostModel] = None


# ─── Ground Truth Generator ────────────────────────────────────────────────────

class GroundTruthGenerator:
    """Generate ground truth using brute-force search for recall measurement."""

    @staticmethod
    def compute_ground_truth(
        data_vectors: np.ndarray,
        query_vectors: np.ndarray,
        k: int = 100,
        metric: str = "cosine",
    ) -> list[list[int]]:
        """Compute exact nearest neighbors via brute force."""
        if metric == "cosine":
            # Normalize for cosine
            data_norm = data_vectors / np.linalg.norm(data_vectors, axis=1, keepdims=True)
            query_norm = query_vectors / np.linalg.norm(query_vectors, axis=1, keepdims=True)
            # Similarity = dot product of normalized vectors
            similarities = query_norm @ data_norm.T
            # Sort descending (higher similarity = closer)
            indices = np.argsort(-similarities, axis=1)[:, :k]
        elif metric == "euclidean":
            # Use faiss for efficient brute force
            import faiss
            index = faiss.IndexFlatL2(data_vectors.shape[1])
            index.add(data_vectors.astype(np.float32))
            _, indices = index.search(query_vectors.astype(np.float32), k)
        elif metric == "dot_product":
            similarities = query_vectors @ data_vectors.T
            indices = np.argsort(-similarities, axis=1)[:, :k]
        else:
            raise ValueError(f"Unknown metric: {metric}")

        return indices.tolist()


# ─── Recall Evaluator ──────────────────────────────────────────────────────────

class RecallEvaluator:
    """Measure recall@k against ground truth."""

    @staticmethod
    def compute_recall_at_k(
        predicted: list[list[str]], ground_truth: list[list[str]], k: int
    ) -> float:
        """Compute recall@k: fraction of true nearest neighbors found."""
        recalls = []
        for pred, truth in zip(predicted, ground_truth):
            pred_set = set(pred[:k])
            truth_set = set(truth[:k])
            if len(truth_set) == 0:
                continue
            recalls.append(len(pred_set & truth_set) / len(truth_set))
        return statistics.mean(recalls) if recalls else 0.0

    @staticmethod
    def compute_mrr(predicted: list[list[str]], ground_truth: list[list[str]]) -> float:
        """Mean Reciprocal Rank: average of 1/rank_of_first_relevant."""
        rrs = []
        for pred, truth in zip(predicted, ground_truth):
            truth_set = set(truth)
            rr = 0.0
            for rank, item in enumerate(pred, 1):
                if item in truth_set:
                    rr = 1.0 / rank
                    break
            rrs.append(rr)
        return statistics.mean(rrs) if rrs else 0.0

    @staticmethod
    def compute_ndcg_at_k(
        predicted: list[list[str]], ground_truth: list[list[str]], k: int
    ) -> float:
        """Normalized DCG@k."""
        ndcgs = []
        for pred, truth in zip(predicted, ground_truth):
            truth_set = set(truth[:k])
            dcg = sum(
                1.0 / np.log2(rank + 2)
                for rank, item in enumerate(pred[:k])
                if item in truth_set
            )
            ideal_dcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(truth_set))))
            ndcgs.append(dcg / ideal_dcg if ideal_dcg > 0 else 0.0)
        return statistics.mean(ndcgs) if ndcgs else 0.0

    @classmethod
    def full_recall_report(
        cls, predicted: list[list[str]], ground_truth: list[list[str]]
    ) -> RecallMetrics:
        return RecallMetrics(
            recall_at_1=cls.compute_recall_at_k(predicted, ground_truth, 1),
            recall_at_5=cls.compute_recall_at_k(predicted, ground_truth, 5),
            recall_at_10=cls.compute_recall_at_k(predicted, ground_truth, 10),
            recall_at_50=cls.compute_recall_at_k(predicted, ground_truth, 50),
            recall_at_100=cls.compute_recall_at_k(predicted, ground_truth, 100),
            mrr=cls.compute_mrr(predicted, ground_truth),
            ndcg_at_10=cls.compute_ndcg_at_k(predicted, ground_truth, 10),
        )


# ─── Latency Benchmarker ──────────────────────────────────────────────────────

class LatencyBenchmarker:
    """Measure query latency distribution."""

    def __init__(self, vector_db_client, collection: str):
        self._client = vector_db_client
        self._collection = collection

    async def measure_latency(
        self,
        queries: list[list[float]],
        top_k: int = 10,
        filter_: Optional[dict] = None,
        warmup: int = 10,
    ) -> LatencyMetrics:
        """Measure latency across queries with warmup."""
        from IMPLEMENTATION_vector_db_client import SearchRequest

        # Warmup (don't count these)
        for q in queries[:warmup]:
            await self._client.search(
                self._collection, SearchRequest(vector=q, top_k=top_k, filter=filter_)
            )

        # Actual measurement
        latencies = []
        for q in queries:
            start = time.perf_counter()
            await self._client.search(
                self._collection, SearchRequest(vector=q, top_k=top_k, filter=filter_)
            )
            latencies.append((time.perf_counter() - start) * 1000)

        return LatencyMetrics(
            avg_ms=statistics.mean(latencies),
            p50_ms=float(np.percentile(latencies, 50)),
            p75_ms=float(np.percentile(latencies, 75)),
            p90_ms=float(np.percentile(latencies, 90)),
            p95_ms=float(np.percentile(latencies, 95)),
            p99_ms=float(np.percentile(latencies, 99)),
            min_ms=min(latencies),
            max_ms=max(latencies),
            std_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        )


# ─── Throughput Benchmarker ────────────────────────────────────────────────────

class ThroughputBenchmarker:
    """Measure sustained QPS under concurrent load."""

    def __init__(self, vector_db_client, collection: str):
        self._client = vector_db_client
        self._collection = collection

    async def measure_throughput(
        self,
        queries: list[list[float]],
        top_k: int = 10,
        concurrency: int = 10,
        duration_seconds: float = 30.0,
    ) -> ThroughputMetrics:
        """Measure QPS under sustained concurrent load."""
        from IMPLEMENTATION_vector_db_client import SearchRequest

        completed = 0
        errors = 0
        start_time = time.time()
        query_idx = 0

        semaphore = asyncio.Semaphore(concurrency)

        async def run_query():
            nonlocal completed, errors, query_idx
            async with semaphore:
                q = queries[query_idx % len(queries)]
                query_idx += 1
                try:
                    await self._client.search(
                        self._collection, SearchRequest(vector=q, top_k=top_k)
                    )
                    completed += 1
                except Exception:
                    errors += 1

        tasks = []
        while time.time() - start_time < duration_seconds:
            tasks.append(asyncio.create_task(run_query()))
            # Small sleep to avoid overwhelming the event loop
            if len(tasks) % concurrency == 0:
                await asyncio.sleep(0.001)

        # Wait for remaining tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Single-thread baseline
        single_start = time.time()
        single_count = 0
        while time.time() - single_start < 5.0:
            q = queries[single_count % len(queries)]
            await self._client.search(self._collection, SearchRequest(vector=q, top_k=top_k))
            single_count += 1
        single_qps = single_count / (time.time() - single_start)

        return ThroughputMetrics(
            qps_single_thread=single_qps,
            qps_concurrent=completed / total_time,
            concurrency_level=concurrency,
            total_queries=completed,
            total_time_seconds=total_time,
            errors=errors,
        )


# ─── Filter Performance Evaluator ─────────────────────────────────────────────

class FilterPerformanceEvaluator:
    """Evaluate impact of metadata filtering on performance."""

    def __init__(self, vector_db_client, collection: str):
        self._client = vector_db_client
        self._collection = collection
        self._latency_benchmarker = LatencyBenchmarker(vector_db_client, collection)

    async def evaluate_filter_scenarios(
        self,
        queries: list[list[float]],
        filter_scenarios: list[dict[str, Any]],
    ) -> list[FilterPerformanceMetrics]:
        """Test different filter selectivities."""
        results = []

        for scenario in filter_scenarios:
            filter_config = scenario["filter"]
            selectivity = scenario.get("selectivity", 0.5)
            filter_type = scenario.get("type", "equality")

            latency = await self._latency_benchmarker.measure_latency(
                queries=queries[:50], top_k=10, filter_=filter_config
            )

            results.append(FilterPerformanceMetrics(
                filter_type=filter_type,
                selectivity=selectivity,
                latency=latency,
                recall=0.0,  # Would need ground truth with filter
                result_count_avg=0.0,
            ))

        return results


# ─── Update/Delete Performance ─────────────────────────────────────────────────

class UpdateDeleteEvaluator:
    """Evaluate write performance and its impact on reads."""

    def __init__(self, vector_db_client, collection: str):
        self._client = vector_db_client
        self._collection = collection

    async def evaluate(
        self,
        dimension: int,
        num_inserts: int = 1000,
        num_updates: int = 500,
        num_deletes: int = 200,
        query_vectors: Optional[list[list[float]]] = None,
    ) -> UpdateDeleteMetrics:
        """Benchmark insert/update/delete operations."""
        from IMPLEMENTATION_vector_db_client import VectorRecord, SearchRequest

        # Measure insert throughput
        insert_latencies = []
        inserted_ids = []
        for i in range(num_inserts):
            record = VectorRecord(
                id=f"bench_insert_{i}",
                vector=np.random.randn(dimension).tolist(),
                metadata={"batch": "insert_bench", "idx": i},
            )
            start = time.perf_counter()
            await self._client.insert(self._collection, [record])
            insert_latencies.append((time.perf_counter() - start) * 1000)
            inserted_ids.append(record.id)

        insert_qps = 1000 / statistics.mean(insert_latencies) if insert_latencies else 0

        # Measure update throughput (upsert existing IDs with new vectors)
        update_latencies = []
        for i in range(min(num_updates, len(inserted_ids))):
            record = VectorRecord(
                id=inserted_ids[i],
                vector=np.random.randn(dimension).tolist(),
                metadata={"batch": "update_bench", "idx": i},
            )
            start = time.perf_counter()
            await self._client.insert(self._collection, [record])
            update_latencies.append((time.perf_counter() - start) * 1000)

        update_qps = 1000 / statistics.mean(update_latencies) if update_latencies else 0

        # Measure delete throughput
        delete_latencies = []
        ids_to_delete = inserted_ids[:num_deletes]
        for batch_start in range(0, len(ids_to_delete), 10):
            batch = ids_to_delete[batch_start : batch_start + 10]
            start = time.perf_counter()
            await self._client.delete(self._collection, batch)
            delete_latencies.append((time.perf_counter() - start) * 1000)

        delete_qps = (num_deletes / (sum(delete_latencies) / 1000)) if delete_latencies else 0

        # Measure recall degradation after deletes
        recall_after = 0.0
        if query_vectors:
            # Simple check: search shouldn't return deleted IDs
            deleted_set = set(ids_to_delete)
            leaked = 0
            total_results = 0
            for q in query_vectors[:20]:
                results = await self._client.search(
                    self._collection, SearchRequest(vector=q, top_k=10)
                )
                for r in results:
                    total_results += 1
                    if r.id in deleted_set:
                        leaked += 1
            recall_after = 1.0 - (leaked / total_results if total_results > 0 else 0)

        return UpdateDeleteMetrics(
            insert_qps=insert_qps,
            update_qps=update_qps,
            delete_qps=delete_qps,
            insert_latency=LatencyMetrics(
                avg_ms=statistics.mean(insert_latencies),
                p50_ms=float(np.percentile(insert_latencies, 50)),
                p75_ms=float(np.percentile(insert_latencies, 75)),
                p90_ms=float(np.percentile(insert_latencies, 90)),
                p95_ms=float(np.percentile(insert_latencies, 95)),
                p99_ms=float(np.percentile(insert_latencies, 99)),
                min_ms=min(insert_latencies),
                max_ms=max(insert_latencies),
                std_ms=statistics.stdev(insert_latencies) if len(insert_latencies) > 1 else 0,
            ),
            compaction_time_seconds=0.0,
            recall_after_deletes=recall_after,
            recall_degradation=1.0 - recall_after,
        )


# ─── Multi-Tenancy Evaluator ──────────────────────────────────────────────────

class MultiTenancyEvaluator:
    """Evaluate performance in multi-tenant scenarios."""

    def __init__(self, vector_db_client, collection: str):
        self._client = vector_db_client
        self._collection = collection

    async def evaluate(
        self,
        dimension: int,
        tenant_configs: list[dict[str, int]],  # [{"id": "t1", "vectors": 1000}, ...]
        queries_per_tenant: int = 20,
    ) -> MultiTenancyMetrics:
        """Benchmark multi-tenant performance."""
        from IMPLEMENTATION_vector_db_client import VectorRecord, SearchRequest

        # Insert vectors for each tenant
        for tenant in tenant_configs:
            records = [
                VectorRecord(
                    id=f"{tenant['id']}_vec_{i}",
                    vector=np.random.randn(dimension).tolist(),
                    metadata={"tenant_id": tenant["id"], "idx": i},
                )
                for i in range(tenant["vectors"])
            ]
            await self._client.batch_insert(self._collection, records, batch_size=100)

        # Query each tenant and measure isolation + latency
        latency_by_size = {}
        isolation_violations = 0
        total_results = 0

        for tenant in tenant_configs:
            latencies = []
            for _ in range(queries_per_tenant):
                q = np.random.randn(dimension).tolist()
                start = time.perf_counter()
                results = await self._client.search(
                    self._collection,
                    SearchRequest(vector=q, top_k=10, filter={"tenant_id": tenant["id"]}),
                )
                latencies.append((time.perf_counter() - start) * 1000)

                # Check isolation
                for r in results:
                    total_results += 1
                    if r.metadata.get("tenant_id") != tenant["id"]:
                        isolation_violations += 1

            # Categorize by size
            size_category = "small" if tenant["vectors"] < 1000 else "medium" if tenant["vectors"] < 10000 else "large"
            latency_by_size[size_category] = LatencyMetrics(
                avg_ms=statistics.mean(latencies),
                p50_ms=float(np.percentile(latencies, 50)),
                p75_ms=float(np.percentile(latencies, 75)),
                p90_ms=float(np.percentile(latencies, 90)),
                p95_ms=float(np.percentile(latencies, 95)),
                p99_ms=float(np.percentile(latencies, 99)),
                min_ms=min(latencies),
                max_ms=max(latencies),
                std_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            )

        return MultiTenancyMetrics(
            tenant_count=len(tenant_configs),
            vectors_per_tenant=statistics.mean([t["vectors"] for t in tenant_configs]),
            cross_tenant_isolation=isolation_violations == 0,
            latency_by_tenant_size=latency_by_size,
            overhead_per_tenant_mb=0.0,  # Would measure memory diff
        )


# ─── Cost Modeler ──────────────────────────────────────────────────────────────

class CostModeler:
    """Model costs for different vector DB deployments."""

    PRICING = {
        "pinecone_serverless": {
            "read_per_million": 8.25,  # $8.25 per million read units
            "write_per_million": 2.00,
            "storage_per_gb": 0.33,
        },
        "pinecone_pod": {
            "p1_per_hour": 0.096,  # p1.x1 pod
            "s1_per_hour": 0.096,
        },
        "qdrant_cloud": {
            "per_hour_1gb": 0.044,
            "per_hour_4gb": 0.175,
            "per_hour_16gb": 0.700,
        },
        "pgvector_rds": {
            "db_r6g_large_per_hour": 0.26,  # 2 vCPU, 16 GB
            "db_r6g_xlarge_per_hour": 0.52,
            "storage_per_gb_month": 0.115,
        },
        "elasticsearch_cloud": {
            "per_hour_4gb": 0.36,
            "storage_per_gb": 0.24,
        },
    }

    @classmethod
    def estimate_cost(
        cls,
        provider: str,
        num_vectors: int,
        dimension: int,
        queries_per_day: int,
        writes_per_day: int = 0,
    ) -> CostModel:
        """Estimate monthly cost for a vector DB deployment."""

        storage_gb = (num_vectors * dimension * 4) / (1024**3)  # Raw vector storage
        # Index overhead ~2-3x for HNSW
        total_storage_gb = storage_gb * 2.5

        if provider == "pinecone_serverless":
            pricing = cls.PRICING["pinecone_serverless"]
            monthly_reads = (queries_per_day * 30) / 1_000_000
            monthly_writes = (writes_per_day * 30) / 1_000_000
            monthly_cost = (
                monthly_reads * pricing["read_per_million"]
                + monthly_writes * pricing["write_per_million"]
                + total_storage_gb * pricing["storage_per_gb"]
            )
            return CostModel(
                provider=provider,
                monthly_cost_usd=round(monthly_cost, 2),
                cost_per_million_vectors=round(monthly_cost / (num_vectors / 1_000_000), 2),
                cost_per_million_queries=pricing["read_per_million"],
                storage_cost_per_gb=pricing["storage_per_gb"],
                compute_cost_per_hour=0,  # Serverless
                assumptions={"storage_gb": round(total_storage_gb, 2)},
            )

        elif provider == "qdrant_cloud":
            # Pick instance size based on memory need
            memory_needed_gb = total_storage_gb * 1.3  # Buffer
            if memory_needed_gb <= 1:
                hourly = cls.PRICING["qdrant_cloud"]["per_hour_1gb"]
            elif memory_needed_gb <= 4:
                hourly = cls.PRICING["qdrant_cloud"]["per_hour_4gb"]
            else:
                nodes = int(np.ceil(memory_needed_gb / 16))
                hourly = cls.PRICING["qdrant_cloud"]["per_hour_16gb"] * nodes

            monthly_cost = hourly * 24 * 30
            return CostModel(
                provider=provider,
                monthly_cost_usd=round(monthly_cost, 2),
                cost_per_million_vectors=round(monthly_cost / (num_vectors / 1_000_000), 2),
                cost_per_million_queries=0,  # Included in compute
                storage_cost_per_gb=0,  # Included in instance
                compute_cost_per_hour=hourly,
                assumptions={"memory_needed_gb": round(memory_needed_gb, 2), "hourly_rate": hourly},
            )

        elif provider == "pgvector_rds":
            memory_needed_gb = total_storage_gb * 1.5
            if memory_needed_gb <= 16:
                hourly = cls.PRICING["pgvector_rds"]["db_r6g_large_per_hour"]
            else:
                instances = int(np.ceil(memory_needed_gb / 32))
                hourly = cls.PRICING["pgvector_rds"]["db_r6g_xlarge_per_hour"] * instances

            storage_monthly = total_storage_gb * cls.PRICING["pgvector_rds"]["storage_per_gb_month"]
            monthly_cost = hourly * 24 * 30 + storage_monthly
            return CostModel(
                provider=provider,
                monthly_cost_usd=round(monthly_cost, 2),
                cost_per_million_vectors=round(monthly_cost / (num_vectors / 1_000_000), 2),
                cost_per_million_queries=0,
                storage_cost_per_gb=cls.PRICING["pgvector_rds"]["storage_per_gb_month"],
                compute_cost_per_hour=hourly,
                assumptions={"storage_gb": round(total_storage_gb, 2)},
            )

        else:
            return CostModel(
                provider=provider,
                monthly_cost_usd=0,
                cost_per_million_vectors=0,
                cost_per_million_queries=0,
                storage_cost_per_gb=0,
                compute_cost_per_hour=0,
                assumptions={"error": f"Unknown provider: {provider}"},
            )


# ─── Comparative Evaluation Framework ─────────────────────────────────────────

class ComparativeEvaluator:
    """Run the same evaluation across multiple vector DBs for comparison."""

    def __init__(self):
        self._results: list[EvaluationReport] = []

    async def evaluate_all(
        self,
        clients: dict[str, Any],  # name -> VectorDBClient
        collection_configs: dict[str, Any],  # name -> CollectionConfig
        data_vectors: np.ndarray,
        query_vectors: np.ndarray,
        metadata: list[dict[str, Any]],
        ground_truth: Optional[list[list[str]]] = None,
    ) -> list[EvaluationReport]:
        """Run full evaluation suite on all provided DBs."""
        from IMPLEMENTATION_vector_db_client import VectorRecord, SearchRequest, CollectionConfig

        dimension = data_vectors.shape[1]
        num_vectors = data_vectors.shape[0]

        # Generate ground truth if not provided
        if ground_truth is None:
            gt_indices = GroundTruthGenerator.compute_ground_truth(
                data_vectors, query_vectors, k=100, metric="cosine"
            )
            ground_truth = [[f"vec_{idx}" for idx in row] for row in gt_indices]

        reports = []

        for db_name, client in clients.items():
            logger.info(f"Evaluating: {db_name}")
            report = EvaluationReport(
                db_name=db_name,
                timestamp=datetime.now(timezone.utc),
                dataset_info={
                    "num_vectors": num_vectors,
                    "dimension": dimension,
                    "num_queries": len(query_vectors),
                },
            )

            try:
                # Setup: create collection and insert data
                config = collection_configs.get(db_name)
                if config:
                    await client.create_collection(config)

                records = [
                    VectorRecord(
                        id=f"vec_{i}",
                        vector=data_vectors[i].tolist(),
                        metadata=metadata[i] if i < len(metadata) else {},
                    )
                    for i in range(num_vectors)
                ]
                await client.batch_insert(config.name if config else "benchmark", records, batch_size=500)

                # Wait for indexing
                await asyncio.sleep(2)

                collection_name = config.name if config else "benchmark"

                # 1. Recall evaluation
                predicted = []
                for q in query_vectors:
                    results = await client.search(
                        collection_name, SearchRequest(vector=q.tolist(), top_k=100)
                    )
                    predicted.append([r.id for r in results])

                report.recall = RecallEvaluator.full_recall_report(predicted, ground_truth)

                # 2. Latency evaluation
                benchmarker = LatencyBenchmarker(client, collection_name)
                report.latency = await benchmarker.measure_latency(
                    [q.tolist() for q in query_vectors], top_k=10, warmup=10
                )

                # 3. Throughput evaluation
                tp_benchmarker = ThroughputBenchmarker(client, collection_name)
                report.throughput = await tp_benchmarker.measure_throughput(
                    [q.tolist() for q in query_vectors[:100]],
                    concurrency=10,
                    duration_seconds=10,
                )

                # 4. Filter performance
                filter_eval = FilterPerformanceEvaluator(client, collection_name)
                report.filter_performance = await filter_eval.evaluate_filter_scenarios(
                    [q.tolist() for q in query_vectors[:20]],
                    [
                        {"filter": {"batch": "insert_bench"}, "selectivity": 0.1, "type": "equality"},
                    ],
                )

                # 5. Cost modeling
                report.cost = CostModeler.estimate_cost(
                    provider=db_name,
                    num_vectors=num_vectors,
                    dimension=dimension,
                    queries_per_day=100_000,
                )

            except Exception as e:
                logger.error(f"Error evaluating {db_name}: {e}")
                report.dataset_info["error"] = str(e)

            reports.append(report)

        self._results = reports
        return reports

    def print_comparison_table(self):
        """Print side-by-side comparison."""
        if not self._results:
            print("No results to compare.")
            return

        header = f"{'Metric':<30}"
        for r in self._results:
            header += f" | {r.db_name:<15}"
        print(header)
        print("-" * len(header))

        # Recall
        for k_label, k_attr in [("Recall@1", "recall_at_1"), ("Recall@10", "recall_at_10"), ("MRR", "mrr")]:
            row = f"{k_label:<30}"
            for r in self._results:
                val = getattr(r.recall, k_attr, 0) if r.recall else 0
                row += f" | {val:<15.4f}"
            print(row)

        # Latency
        for l_label, l_attr in [("Avg Latency (ms)", "avg_ms"), ("P95 Latency (ms)", "p95_ms"), ("P99 Latency (ms)", "p99_ms")]:
            row = f"{l_label:<30}"
            for r in self._results:
                val = getattr(r.latency, l_attr, 0) if r.latency else 0
                row += f" | {val:<15.2f}"
            print(row)

        # Throughput
        row = f"{'QPS (concurrent)':<30}"
        for r in self._results:
            val = r.throughput.qps_concurrent if r.throughput else 0
            row += f" | {val:<15.1f}"
        print(row)

        # Cost
        row = f"{'Monthly Cost ($)':<30}"
        for r in self._results:
            val = r.cost.monthly_cost_usd if r.cost else 0
            row += f" | {val:<15.2f}"
        print(row)


# ─── Usage Example ─────────────────────────────────────────────────────────────

async def example():
    """Example evaluation run."""
    # Generate synthetic data
    dimension = 1536
    num_vectors = 10_000
    num_queries = 100

    data = np.random.randn(num_vectors, dimension).astype(np.float32)
    queries = np.random.randn(num_queries, dimension).astype(np.float32)
    metadata = [{"category": f"cat_{i % 10}", "idx": i} for i in range(num_vectors)]

    # Compute ground truth
    gt = GroundTruthGenerator.compute_ground_truth(data, queries, k=100, metric="cosine")
    ground_truth = [[f"vec_{idx}" for idx in row] for row in gt]

    # Cost comparison
    print("\n=== Cost Comparison (1M vectors, 1536-dim, 100K queries/day) ===")
    for provider in ["pinecone_serverless", "qdrant_cloud", "pgvector_rds"]:
        cost = CostModeler.estimate_cost(
            provider=provider,
            num_vectors=1_000_000,
            dimension=1536,
            queries_per_day=100_000,
        )
        print(f"  {provider}: ${cost.monthly_cost_usd}/month")

    # Single DB recall evaluation
    print("\n=== Recall Evaluation (synthetic data) ===")
    # Simulate ANN results (add noise to ground truth)
    predicted = []
    for gt_row in ground_truth:
        # Simulate 95% recall by randomly dropping some results
        noisy = list(gt_row[:100])
        for i in range(len(noisy)):
            if np.random.random() < 0.05:
                noisy[i] = f"vec_{np.random.randint(num_vectors)}"
        predicted.append(noisy)

    recall_report = RecallEvaluator.full_recall_report(predicted, ground_truth)
    print(f"  Recall@1:  {recall_report.recall_at_1:.4f}")
    print(f"  Recall@10: {recall_report.recall_at_10:.4f}")
    print(f"  MRR:       {recall_report.mrr:.4f}")
    print(f"  nDCG@10:   {recall_report.ndcg_at_10:.4f}")


if __name__ == "__main__":
    asyncio.run(example())
