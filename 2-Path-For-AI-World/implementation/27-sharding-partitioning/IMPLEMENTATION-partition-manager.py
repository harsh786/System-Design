"""
Partition Manager for Vector Databases
Manages logical partitioning of vector data across multiple strategies.
"""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Core Data Models
# =============================================================================

class PartitionStrategy(Enum):
    TENANT = "tenant"
    DOMAIN = "domain"
    TIME = "time"
    GEOGRAPHY = "geography"
    SENSITIVITY = "sensitivity"
    EMBEDDING_VERSION = "embedding_version"
    MODALITY = "modality"
    HOT_COLD = "hot_cold"


class PartitionStatus(Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    FROZEN = "frozen"
    ARCHIVED = "archived"
    DELETING = "deleting"


class StorageTier(Enum):
    HOT = "hot"       # RAM-backed, fastest
    WARM = "warm"     # SSD-backed
    COLD = "cold"     # Disk/object store
    ARCHIVE = "archive"  # Glacier-like, retrieval takes minutes


@dataclass
class PartitionConfig:
    strategy: PartitionStrategy
    max_vectors_per_partition: int = 5_000_000
    max_partitions: int = 1000
    retention_days: Optional[int] = None
    auto_rebalance: bool = True
    rebalance_threshold_ratio: float = 3.0  # max/min size ratio before rebalance


@dataclass
class PartitionMetadata:
    partition_id: str
    strategy: PartitionStrategy
    status: PartitionStatus
    created_at: datetime
    vector_count: int = 0
    storage_bytes: int = 0
    storage_tier: StorageTier = StorageTier.HOT
    last_write_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None
    read_qps_avg: float = 0.0
    write_qps_avg: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    routing_keys: Set[str] = field(default_factory=set)


@dataclass
class PartitionHealthReport:
    partition_id: str
    is_healthy: bool
    vector_count: int
    storage_tier: StorageTier
    avg_query_latency_ms: float
    error_rate: float
    last_write_lag_seconds: float
    issues: List[str] = field(default_factory=list)


@dataclass
class VectorRecord:
    id: str
    vector: List[float]
    metadata: Dict[str, Any]
    tenant_id: Optional[str] = None
    domain: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class QueryRequest:
    vector: List[float]
    top_k: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[str] = None
    domain: Optional[str] = None
    time_range: Optional[Tuple[datetime, datetime]] = None


@dataclass
class QueryResult:
    id: str
    score: float
    metadata: Dict[str, Any]
    partition_id: str


# =============================================================================
# Partition Strategy Implementations
# =============================================================================

class BasePartitioner(ABC):
    """Base class for partition routing logic."""

    def __init__(self, config: PartitionConfig):
        self.config = config
        self.partitions: Dict[str, PartitionMetadata] = {}

    @abstractmethod
    def resolve_partition(self, record: VectorRecord) -> str:
        """Determine which partition a record belongs to."""
        pass

    @abstractmethod
    def resolve_query_partitions(self, query: QueryRequest) -> List[str]:
        """Determine which partitions to search for a query."""
        pass

    def create_partition(self, partition_id: str, **kwargs) -> PartitionMetadata:
        metadata = PartitionMetadata(
            partition_id=partition_id,
            strategy=self.config.strategy,
            status=PartitionStatus.ACTIVE,
            created_at=datetime.utcnow(),
            **kwargs,
        )
        self.partitions[partition_id] = metadata
        logger.info(f"Created partition: {partition_id}")
        return metadata

    def get_active_partitions(self) -> List[PartitionMetadata]:
        return [p for p in self.partitions.values() if p.status == PartitionStatus.ACTIVE]


class TenantPartitioner(BasePartitioner):
    """Routes vectors by tenant_id. Each tenant gets its own partition."""

    def __init__(self, config: PartitionConfig):
        super().__init__(config)
        self.tenant_partition_map: Dict[str, str] = {}

    def resolve_partition(self, record: VectorRecord) -> str:
        if not record.tenant_id:
            raise ValueError("tenant_id required for tenant partitioning")

        if record.tenant_id not in self.tenant_partition_map:
            partition_id = f"tenant_{record.tenant_id}"
            self.create_partition(
                partition_id,
                labels={"tenant_id": record.tenant_id},
                routing_keys={record.tenant_id},
            )
            self.tenant_partition_map[record.tenant_id] = partition_id

        return self.tenant_partition_map[record.tenant_id]

    def resolve_query_partitions(self, query: QueryRequest) -> List[str]:
        if query.tenant_id and query.tenant_id in self.tenant_partition_map:
            return [self.tenant_partition_map[query.tenant_id]]
        # No tenant specified — this should be rejected or fanned out
        raise ValueError("tenant_id is mandatory for tenant-partitioned queries")

    def get_tenant_partition(self, tenant_id: str) -> Optional[str]:
        return self.tenant_partition_map.get(tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        """GDPR right-to-erasure: drop entire tenant partition."""
        partition_id = self.tenant_partition_map.get(tenant_id)
        if not partition_id:
            return False
        self.partitions[partition_id].status = PartitionStatus.DELETING
        del self.tenant_partition_map[tenant_id]
        logger.info(f"Marked tenant {tenant_id} partition for deletion")
        return True


class DomainPartitioner(BasePartitioner):
    """Routes vectors by knowledge domain using a classifier."""

    KNOWN_DOMAINS = ["legal", "medical", "engineering", "finance", "hr", "general"]

    def __init__(self, config: PartitionConfig, classifier=None):
        super().__init__(config)
        self.classifier = classifier or self._default_classifier
        self.domain_partition_map: Dict[str, str] = {}
        self._init_domain_partitions()

    def _init_domain_partitions(self):
        for domain in self.KNOWN_DOMAINS:
            partition_id = f"domain_{domain}"
            self.create_partition(
                partition_id,
                labels={"domain": domain},
                routing_keys={domain},
            )
            self.domain_partition_map[domain] = partition_id

    def _default_classifier(self, text: str) -> str:
        """Simple keyword-based classifier. Replace with ML model in production."""
        text_lower = text.lower()
        domain_keywords = {
            "legal": ["contract", "clause", "liability", "court", "statute", "regulation"],
            "medical": ["patient", "diagnosis", "treatment", "clinical", "symptom"],
            "engineering": ["api", "database", "architecture", "code", "deploy", "kubernetes"],
            "finance": ["revenue", "investment", "portfolio", "trading", "compliance"],
            "hr": ["employee", "hiring", "compensation", "benefits", "onboarding"],
        }
        scores = {}
        for domain, keywords in domain_keywords.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def resolve_partition(self, record: VectorRecord) -> str:
        domain = record.domain
        if not domain:
            # Classify based on metadata content
            text = record.metadata.get("text", "") or record.metadata.get("title", "")
            domain = self.classifier(text)

        if domain not in self.domain_partition_map:
            domain = "general"

        return self.domain_partition_map[domain]

    def resolve_query_partitions(self, query: QueryRequest) -> List[str]:
        if query.domain:
            domain = query.domain
            if domain in self.domain_partition_map:
                return [self.domain_partition_map[domain]]
        # If no domain specified, classify from query filters or fan out
        query_text = query.filters.get("query_text", "")
        if query_text:
            domain = self.classifier(query_text)
            if domain != "general":
                return [self.domain_partition_map[domain]]
        # Fanout to all domains
        return list(self.domain_partition_map.values())


class TimePartitioner(BasePartitioner):
    """Routes vectors by time bucket (monthly by default)."""

    def __init__(self, config: PartitionConfig, bucket_format: str = "%Y-%m"):
        super().__init__(config)
        self.bucket_format = bucket_format
        self.time_partitions: Dict[str, str] = {}  # bucket_key -> partition_id

    def _get_bucket_key(self, dt: datetime) -> str:
        return dt.strftime(self.bucket_format)

    def resolve_partition(self, record: VectorRecord) -> str:
        ts = record.created_at or datetime.utcnow()
        bucket = self._get_bucket_key(ts)

        if bucket not in self.time_partitions:
            partition_id = f"time_{bucket}"
            self.create_partition(
                partition_id,
                labels={"time_bucket": bucket},
                routing_keys={bucket},
            )
            self.time_partitions[bucket] = partition_id

        return self.time_partitions[bucket]

    def resolve_query_partitions(self, query: QueryRequest) -> List[str]:
        if query.time_range:
            start, end = query.time_range
            relevant = []
            for bucket, partition_id in self.time_partitions.items():
                bucket_start = datetime.strptime(bucket, self.bucket_format)
                if self.bucket_format == "%Y-%m":
                    if bucket_start.year == 12:
                        bucket_end = bucket_start.replace(year=bucket_start.year + 1, month=1)
                    else:
                        bucket_end = bucket_start.replace(month=bucket_start.month + 1)
                else:
                    bucket_end = bucket_start + timedelta(days=7)
                if bucket_start <= end and bucket_end >= start:
                    relevant.append(partition_id)
            return relevant if relevant else list(self.time_partitions.values())[-3:]
        # Default: search last 3 partitions
        sorted_keys = sorted(self.time_partitions.keys(), reverse=True)
        return [self.time_partitions[k] for k in sorted_keys[:3]]

    def apply_retention(self) -> List[str]:
        """Delete partitions older than retention period."""
        if not self.config.retention_days:
            return []

        cutoff = datetime.utcnow() - timedelta(days=self.config.retention_days)
        expired = []
        for bucket, partition_id in list(self.time_partitions.items()):
            bucket_dt = datetime.strptime(bucket, self.bucket_format)
            if bucket_dt < cutoff:
                self.partitions[partition_id].status = PartitionStatus.DELETING
                expired.append(partition_id)
                del self.time_partitions[bucket]
                logger.info(f"Retention: marked {partition_id} for deletion (older than {self.config.retention_days}d)")
        return expired


class HotColdPartitioner(BasePartitioner):
    """Manages hot/cold tiering based on access patterns."""

    def __init__(self, config: PartitionConfig,
                 cold_threshold_days: int = 30,
                 archive_threshold_days: int = 180):
        super().__init__(config)
        self.cold_threshold_days = cold_threshold_days
        self.archive_threshold_days = archive_threshold_days
        self.access_log: Dict[str, List[datetime]] = defaultdict(list)
        self.vector_partition_map: Dict[str, str] = {}

    def resolve_partition(self, record: VectorRecord) -> str:
        # New records always go to hot tier
        partition_id = "hot_tier"
        if partition_id not in self.partitions:
            self.create_partition(partition_id, storage_tier=StorageTier.HOT)
        return partition_id

    def resolve_query_partitions(self, query: QueryRequest) -> List[str]:
        # Search hot first, optionally extend to warm/cold
        include_cold = query.filters.get("include_cold", False)
        partitions = [pid for pid, p in self.partitions.items()
                      if p.storage_tier == StorageTier.HOT and p.status == PartitionStatus.ACTIVE]
        if include_cold:
            partitions.extend(
                pid for pid, p in self.partitions.items()
                if p.storage_tier in (StorageTier.WARM, StorageTier.COLD)
                and p.status == PartitionStatus.ACTIVE
            )
        return partitions

    def record_access(self, vector_id: str):
        self.access_log[vector_id].append(datetime.utcnow())

    def evaluate_migrations(self) -> Dict[str, StorageTier]:
        """Determine which vectors should move tiers."""
        now = datetime.utcnow()
        migrations = {}

        for vector_id, accesses in self.access_log.items():
            recent = [a for a in accesses if (now - a).days < self.cold_threshold_days]
            if not recent:
                very_old = all((now - a).days > self.archive_threshold_days for a in accesses)
                migrations[vector_id] = StorageTier.ARCHIVE if very_old else StorageTier.COLD
        return migrations

    def execute_migration(self, migrations: Dict[str, StorageTier]):
        """Move vectors between tiers."""
        tier_counts = defaultdict(int)
        for vector_id, target_tier in migrations.items():
            tier_counts[target_tier] += 1
            # In production: actually move vector data between storage backends
        for tier, count in tier_counts.items():
            logger.info(f"Migrated {count} vectors to {tier.value} tier")


# =============================================================================
# Partition Manager (Orchestrator)
# =============================================================================

class PartitionManager:
    """
    Central orchestrator for partition management.
    Coordinates multiple partitioning strategies and handles cross-partition operations.
    """

    def __init__(self):
        self.partitioners: Dict[PartitionStrategy, BasePartitioner] = {}
        self.primary_strategy: Optional[PartitionStrategy] = None
        self.metrics = PartitionMetrics()
        self._health_check_interval = 60  # seconds

    def register_strategy(self, strategy: PartitionStrategy, partitioner: BasePartitioner,
                          primary: bool = False):
        self.partitioners[strategy] = partitioner
        if primary:
            self.primary_strategy = strategy
        logger.info(f"Registered {'primary ' if primary else ''}strategy: {strategy.value}")

    def route_record(self, record: VectorRecord) -> Dict[PartitionStrategy, str]:
        """Route a record to partitions across all active strategies."""
        assignments = {}
        for strategy, partitioner in self.partitioners.items():
            try:
                partition_id = partitioner.resolve_partition(record)
                assignments[strategy] = partition_id
            except Exception as e:
                logger.error(f"Routing failed for strategy {strategy.value}: {e}")
        return assignments

    def route_query(self, query: QueryRequest) -> Dict[PartitionStrategy, List[str]]:
        """Determine target partitions for a query."""
        targets = {}
        for strategy, partitioner in self.partitioners.items():
            try:
                partitions = partitioner.resolve_query_partitions(query)
                targets[strategy] = partitions
            except Exception as e:
                logger.warning(f"Query routing failed for {strategy.value}: {e}")
        return targets

    def get_effective_partitions(self, query: QueryRequest) -> List[str]:
        """
        Intersect partition targets across strategies to get minimal set.
        Primary strategy determines base set; others narrow it down.
        """
        if not self.primary_strategy:
            # Use first available
            for partitioner in self.partitioners.values():
                return partitioner.resolve_query_partitions(query)
            return []

        primary = self.partitioners[self.primary_strategy]
        return primary.resolve_query_partitions(query)

    async def execute_cross_partition_query(
        self, query: QueryRequest, partitions: List[str],
        search_fn, oversampling_factor: int = 3
    ) -> List[QueryResult]:
        """
        Execute query across multiple partitions with result merging.
        Uses oversampling to mitigate local top-k recall loss.
        """
        local_k = query.top_k * oversampling_factor

        async def search_partition(partition_id: str) -> List[QueryResult]:
            start = time.time()
            try:
                results = await search_fn(partition_id, query.vector, local_k, query.filters)
                latency = (time.time() - start) * 1000
                self.metrics.record_query(partition_id, latency)
                return [QueryResult(
                    id=r["id"], score=r["score"],
                    metadata=r["metadata"], partition_id=partition_id
                ) for r in results]
            except Exception as e:
                latency = (time.time() - start) * 1000
                self.metrics.record_error(partition_id, latency)
                logger.error(f"Search failed on partition {partition_id}: {e}")
                return []

        # Execute in parallel
        tasks = [search_partition(pid) for pid in partitions]
        all_results = await asyncio.gather(*tasks)

        # Merge and deduplicate
        merged = []
        seen_ids = set()
        for partition_results in all_results:
            for result in partition_results:
                if result.id not in seen_ids:
                    seen_ids.add(result.id)
                    merged.append(result)

        # Sort by score (descending) and return top-k
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:query.top_k]

    def get_health_report(self) -> List[PartitionHealthReport]:
        """Generate health report for all partitions."""
        reports = []
        for strategy, partitioner in self.partitioners.items():
            for pid, pmeta in partitioner.partitions.items():
                issues = []
                avg_latency = self.metrics.get_avg_latency(pid)
                error_rate = self.metrics.get_error_rate(pid)

                if avg_latency > 200:
                    issues.append(f"High latency: {avg_latency:.1f}ms")
                if error_rate > 0.05:
                    issues.append(f"High error rate: {error_rate:.2%}")
                if pmeta.vector_count > self.partitioners[strategy].config.max_vectors_per_partition * 0.9:
                    issues.append("Near capacity limit")
                if pmeta.storage_tier == StorageTier.HOT and pmeta.vector_count > 10_000_000:
                    issues.append("Hot partition exceeds recommended size")

                write_lag = 0.0
                if pmeta.last_write_at:
                    write_lag = (datetime.utcnow() - pmeta.last_write_at).total_seconds()

                reports.append(PartitionHealthReport(
                    partition_id=pid,
                    is_healthy=len(issues) == 0,
                    vector_count=pmeta.vector_count,
                    storage_tier=pmeta.storage_tier,
                    avg_query_latency_ms=avg_latency,
                    error_rate=error_rate,
                    last_write_lag_seconds=write_lag,
                    issues=issues,
                ))
        return reports

    def check_rebalance_needed(self, strategy: PartitionStrategy) -> bool:
        """Check if partitions need rebalancing based on size skew."""
        partitioner = self.partitioners.get(strategy)
        if not partitioner:
            return False

        active = partitioner.get_active_partitions()
        if len(active) < 2:
            return False

        sizes = [p.vector_count for p in active if p.vector_count > 0]
        if not sizes:
            return False

        ratio = max(sizes) / max(min(sizes), 1)
        return ratio > partitioner.config.rebalance_threshold_ratio

    def plan_rebalance(self, strategy: PartitionStrategy) -> Dict[str, Any]:
        """
        Plan partition rebalancing. Returns migration plan without executing.
        """
        partitioner = self.partitioners.get(strategy)
        if not partitioner:
            return {"action": "none", "reason": "strategy not found"}

        active = partitioner.get_active_partitions()
        total_vectors = sum(p.vector_count for p in active)
        target_per_partition = total_vectors // len(active)

        over_limit = [p for p in active if p.vector_count > target_per_partition * 1.5]
        under_limit = [p for p in active if p.vector_count < target_per_partition * 0.5]

        return {
            "action": "rebalance" if over_limit else "none",
            "total_vectors": total_vectors,
            "target_per_partition": target_per_partition,
            "over_provisioned": [p.partition_id for p in over_limit],
            "under_provisioned": [p.partition_id for p in under_limit],
            "estimated_vectors_to_move": sum(
                p.vector_count - target_per_partition for p in over_limit
            ),
        }


# =============================================================================
# Metrics Tracking
# =============================================================================

class PartitionMetrics:
    """Tracks per-partition performance metrics."""

    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self._latencies: Dict[str, List[Tuple[float, float]]] = defaultdict(list)  # pid -> [(timestamp, latency_ms)]
        self._errors: Dict[str, List[float]] = defaultdict(list)  # pid -> [timestamps]
        self._queries: Dict[str, List[float]] = defaultdict(list)  # pid -> [timestamps]

    def record_query(self, partition_id: str, latency_ms: float):
        now = time.time()
        self._latencies[partition_id].append((now, latency_ms))
        self._queries[partition_id].append(now)
        self._prune(partition_id)

    def record_error(self, partition_id: str, latency_ms: float):
        now = time.time()
        self._errors[partition_id].append(now)
        self._latencies[partition_id].append((now, latency_ms))
        self._queries[partition_id].append(now)
        self._prune(partition_id)

    def _prune(self, partition_id: str):
        cutoff = time.time() - self.window
        self._latencies[partition_id] = [
            (t, l) for t, l in self._latencies[partition_id] if t > cutoff
        ]
        self._errors[partition_id] = [t for t in self._errors[partition_id] if t > cutoff]
        self._queries[partition_id] = [t for t in self._queries[partition_id] if t > cutoff]

    def get_avg_latency(self, partition_id: str) -> float:
        entries = self._latencies.get(partition_id, [])
        if not entries:
            return 0.0
        return sum(l for _, l in entries) / len(entries)

    def get_error_rate(self, partition_id: str) -> float:
        queries = len(self._queries.get(partition_id, []))
        errors = len(self._errors.get(partition_id, []))
        if queries == 0:
            return 0.0
        return errors / queries

    def get_qps(self, partition_id: str) -> float:
        queries = self._queries.get(partition_id, [])
        if not queries:
            return 0.0
        return len(queries) / self.window

    def get_hot_partitions(self, threshold_qps: float = 100.0) -> List[str]:
        """Identify partitions with QPS above threshold."""
        return [pid for pid in self._queries if self.get_qps(pid) > threshold_qps]


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    """Demonstrate partition manager usage."""

    # Configure strategies
    tenant_config = PartitionConfig(
        strategy=PartitionStrategy.TENANT,
        max_vectors_per_partition=1_000_000,
    )
    time_config = PartitionConfig(
        strategy=PartitionStrategy.TIME,
        retention_days=365,
    )
    hot_cold_config = PartitionConfig(
        strategy=PartitionStrategy.HOT_COLD,
    )

    # Create manager
    manager = PartitionManager()
    manager.register_strategy(PartitionStrategy.TENANT, TenantPartitioner(tenant_config), primary=True)
    manager.register_strategy(PartitionStrategy.TIME, TimePartitioner(time_config))
    manager.register_strategy(PartitionStrategy.HOT_COLD, HotColdPartitioner(hot_cold_config))

    # Route a record
    record = VectorRecord(
        id="doc_001",
        vector=[0.1] * 1536,
        metadata={"text": "Contract clause about liability", "source": "legal_db"},
        tenant_id="acme_corp",
        created_at=datetime.utcnow(),
    )
    assignments = manager.route_record(record)
    print(f"Record routed to: {assignments}")

    # Route a query
    query = QueryRequest(
        vector=[0.1] * 1536,
        top_k=10,
        tenant_id="acme_corp",
        time_range=(datetime.utcnow() - timedelta(days=30), datetime.utcnow()),
    )
    partitions = manager.get_effective_partitions(query)
    print(f"Query targets partitions: {partitions}")

    # Health check
    reports = manager.get_health_report()
    for r in reports:
        status = "HEALTHY" if r.is_healthy else "UNHEALTHY"
        print(f"  [{status}] {r.partition_id}: {r.vector_count} vectors, {r.avg_query_latency_ms:.1f}ms")

    # Rebalance check
    needs_rebalance = manager.check_rebalance_needed(PartitionStrategy.TENANT)
    if needs_rebalance:
        plan = manager.plan_rebalance(PartitionStrategy.TENANT)
        print(f"Rebalance plan: {json.dumps(plan, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
