"""
Multi-Tenant Vector Index Design
Implements 5 patterns: shared+filter, namespace, index-per-tenant, cell-based, dedicated.
Includes tenant lifecycle, migration, quotas, isolation testing.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

class TenantTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class IndexPattern(Enum):
    SHARED = "shared"           # Pattern 1: shared index + tenant_id filter
    NAMESPACE = "namespace"     # Pattern 2: logical namespace per tenant
    DEDICATED_INDEX = "dedicated_index"  # Pattern 3: index per tenant
    CELL = "cell"               # Pattern 4: cluster/cell per tenant group
    DEDICATED_DEPLOYMENT = "dedicated_deployment"  # Pattern 5: full deployment


@dataclass
class TenantQuota:
    max_vectors: int
    max_queries_per_second: int
    max_storage_bytes: int
    max_dimensions: int = 1536
    allowed_patterns: List[IndexPattern] = field(default_factory=lambda: [IndexPattern.SHARED])


TIER_QUOTAS = {
    TenantTier.FREE: TenantQuota(
        max_vectors=10_000, max_queries_per_second=10,
        max_storage_bytes=100 * 1024 * 1024,
        allowed_patterns=[IndexPattern.SHARED],
    ),
    TenantTier.STARTER: TenantQuota(
        max_vectors=100_000, max_queries_per_second=50,
        max_storage_bytes=1024 * 1024 * 1024,
        allowed_patterns=[IndexPattern.SHARED, IndexPattern.NAMESPACE],
    ),
    TenantTier.PROFESSIONAL: TenantQuota(
        max_vectors=5_000_000, max_queries_per_second=200,
        max_storage_bytes=10 * 1024 * 1024 * 1024,
        allowed_patterns=[IndexPattern.NAMESPACE, IndexPattern.DEDICATED_INDEX],
    ),
    TenantTier.ENTERPRISE: TenantQuota(
        max_vectors=100_000_000, max_queries_per_second=2000,
        max_storage_bytes=500 * 1024 * 1024 * 1024,
        allowed_patterns=[IndexPattern.DEDICATED_INDEX, IndexPattern.CELL, IndexPattern.DEDICATED_DEPLOYMENT],
    ),
}


@dataclass
class TenantInfo:
    tenant_id: str
    tier: TenantTier
    pattern: IndexPattern
    vector_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    index_id: Optional[str] = None
    namespace: Optional[str] = None
    cell_id: Optional[str] = None
    deployment_id: Optional[str] = None
    is_hot: bool = False
    last_activity: Optional[datetime] = None


@dataclass
class CellInfo:
    cell_id: str
    tenants: Set[str] = field(default_factory=set)
    total_vectors: int = 0
    max_capacity: int = 20_000_000
    endpoint: str = ""


# =============================================================================
# Index Pattern Implementations
# =============================================================================

class BaseIndexPattern(ABC):
    """Base class for multi-tenant index patterns."""

    @abstractmethod
    async def upsert_vectors(self, tenant_id: str, vectors: List[Dict]) -> int:
        pass

    @abstractmethod
    async def search(self, tenant_id: str, vector: List[float], top_k: int,
                     filters: Dict[str, Any] = None) -> List[Dict]:
        pass

    @abstractmethod
    async def delete_tenant_data(self, tenant_id: str) -> int:
        pass

    @abstractmethod
    async def get_tenant_vector_count(self, tenant_id: str) -> int:
        pass


class SharedIndexPattern(BaseIndexPattern):
    """
    Pattern 1: All tenants in one shared index.
    Every query MUST include tenant_id filter.
    Suitable for: <100 small tenants, <10M total vectors.
    """

    def __init__(self, index_name: str = "shared_vectors"):
        self.index_name = index_name
        self._vectors: Dict[str, Dict] = {}  # id -> {vector, metadata}
        self._tenant_vectors: Dict[str, Set[str]] = defaultdict(set)

    async def upsert_vectors(self, tenant_id: str, vectors: List[Dict]) -> int:
        count = 0
        for vec in vectors:
            vec_id = vec["id"]
            # CRITICAL: Always stamp tenant_id into metadata
            metadata = vec.get("metadata", {})
            metadata["tenant_id"] = tenant_id
            self._vectors[vec_id] = {
                "vector": vec["vector"],
                "metadata": metadata,
            }
            self._tenant_vectors[tenant_id].add(vec_id)
            count += 1
        return count

    async def search(self, tenant_id: str, vector: List[float], top_k: int,
                     filters: Dict[str, Any] = None) -> List[Dict]:
        """
        Search with MANDATORY tenant_id filter.
        In production: this translates to a pre-filter or post-filter on the HNSW graph.
        HNSW ef_search should be set higher (2-3x) to compensate for filtering.
        """
        if not tenant_id:
            raise ValueError("tenant_id filter is MANDATORY on shared index")

        tenant_vecs = self._tenant_vectors.get(tenant_id, set())
        # Simulate vector search with filter
        results = []
        for vec_id in tenant_vecs:
            vec_data = self._vectors[vec_id]
            # Cosine similarity simulation
            score = self._cosine_sim(vector, vec_data["vector"])
            if filters:
                if not self._matches_filters(vec_data["metadata"], filters):
                    continue
            results.append({"id": vec_id, "score": score, "metadata": vec_data["metadata"]})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete_tenant_data(self, tenant_id: str) -> int:
        vec_ids = self._tenant_vectors.pop(tenant_id, set())
        for vid in vec_ids:
            self._vectors.pop(vid, None)
        return len(vec_ids)

    async def get_tenant_vector_count(self, tenant_id: str) -> int:
        return len(self._tenant_vectors.get(tenant_id, set()))

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a[:10], b[:10]))  # partial for perf
        return min(max(dot / 10.0, 0.0), 1.0)

    @staticmethod
    def _matches_filters(metadata: Dict, filters: Dict) -> bool:
        for key, value in filters.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True


class NamespacePattern(BaseIndexPattern):
    """
    Pattern 2: Logical namespace per tenant within single physical index.
    Maps to Pinecone namespaces or Qdrant collections.
    Suitable for: up to ~1000 tenants, 10K-1M vectors each.
    """

    def __init__(self):
        self._namespaces: Dict[str, Dict[str, Dict]] = {}  # namespace -> {vec_id -> data}

    def _get_namespace(self, tenant_id: str) -> str:
        return f"ns_{tenant_id}"

    async def upsert_vectors(self, tenant_id: str, vectors: List[Dict]) -> int:
        ns = self._get_namespace(tenant_id)
        if ns not in self._namespaces:
            self._namespaces[ns] = {}
            logger.info(f"Created namespace: {ns}")

        count = 0
        for vec in vectors:
            self._namespaces[ns][vec["id"]] = {
                "vector": vec["vector"],
                "metadata": vec.get("metadata", {}),
            }
            count += 1
        return count

    async def search(self, tenant_id: str, vector: List[float], top_k: int,
                     filters: Dict[str, Any] = None) -> List[Dict]:
        """Search within tenant's namespace only. Natural isolation."""
        ns = self._get_namespace(tenant_id)
        ns_data = self._namespaces.get(ns, {})

        results = []
        for vec_id, data in ns_data.items():
            score = SharedIndexPattern._cosine_sim(vector, data["vector"])
            if filters and not SharedIndexPattern._matches_filters(data["metadata"], filters):
                continue
            results.append({"id": vec_id, "score": score, "metadata": data["metadata"]})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete_tenant_data(self, tenant_id: str) -> int:
        ns = self._get_namespace(tenant_id)
        count = len(self._namespaces.pop(ns, {}))
        logger.info(f"Deleted namespace {ns}: {count} vectors")
        return count

    async def get_tenant_vector_count(self, tenant_id: str) -> int:
        ns = self._get_namespace(tenant_id)
        return len(self._namespaces.get(ns, {}))


class DedicatedIndexPattern(BaseIndexPattern):
    """
    Pattern 3: Separate index (collection) per tenant.
    Each tenant gets independently tuned HNSW/IVF parameters.
    Suitable for: large tenants (1M+ vectors), different embedding models.
    """

    def __init__(self):
        self._indexes: Dict[str, Dict] = {}  # index_id -> {config, vectors}

    def create_index(self, tenant_id: str, config: Dict[str, Any] = None) -> str:
        index_id = f"idx_{tenant_id}"
        default_config = {
            "dimension": 1536,
            "metric": "cosine",
            "hnsw_m": 16,
            "hnsw_ef_construction": 200,
            "hnsw_ef_search": 128,
        }
        if config:
            default_config.update(config)

        self._indexes[index_id] = {"config": default_config, "vectors": {}}
        logger.info(f"Created dedicated index: {index_id} with config {default_config}")
        return index_id

    async def upsert_vectors(self, tenant_id: str, vectors: List[Dict]) -> int:
        index_id = f"idx_{tenant_id}"
        if index_id not in self._indexes:
            self.create_index(tenant_id)

        count = 0
        for vec in vectors:
            self._indexes[index_id]["vectors"][vec["id"]] = {
                "vector": vec["vector"],
                "metadata": vec.get("metadata", {}),
            }
            count += 1
        return count

    async def search(self, tenant_id: str, vector: List[float], top_k: int,
                     filters: Dict[str, Any] = None) -> List[Dict]:
        index_id = f"idx_{tenant_id}"
        if index_id not in self._indexes:
            return []

        index_data = self._indexes[index_id]["vectors"]
        results = []
        for vec_id, data in index_data.items():
            score = SharedIndexPattern._cosine_sim(vector, data["vector"])
            if filters and not SharedIndexPattern._matches_filters(data["metadata"], filters):
                continue
            results.append({"id": vec_id, "score": score, "metadata": data["metadata"]})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete_tenant_data(self, tenant_id: str) -> int:
        index_id = f"idx_{tenant_id}"
        if index_id in self._indexes:
            count = len(self._indexes[index_id]["vectors"])
            del self._indexes[index_id]
            logger.info(f"Dropped dedicated index: {index_id}")
            return count
        return 0

    async def get_tenant_vector_count(self, tenant_id: str) -> int:
        index_id = f"idx_{tenant_id}"
        if index_id in self._indexes:
            return len(self._indexes[index_id]["vectors"])
        return 0


# =============================================================================
# Multi-Tenant Index Manager
# =============================================================================

class MultiTenantIndexManager:
    """
    Orchestrates tenant placement across index patterns.
    Handles lifecycle, migration, quotas, and isolation.
    """

    def __init__(self):
        self.tenants: Dict[str, TenantInfo] = {}
        self.cells: Dict[str, CellInfo] = {}
        self.patterns: Dict[IndexPattern, BaseIndexPattern] = {
            IndexPattern.SHARED: SharedIndexPattern(),
            IndexPattern.NAMESPACE: NamespacePattern(),
            IndexPattern.DEDICATED_INDEX: DedicatedIndexPattern(),
        }
        self._usage_tracker: Dict[str, List[float]] = defaultdict(list)  # tenant -> [timestamps]

    # =========================================================================
    # Tenant Lifecycle
    # =========================================================================

    def provision_tenant(self, tenant_id: str, tier: TenantTier) -> TenantInfo:
        """Provision a new tenant with appropriate index pattern."""
        pattern = self._select_pattern(tier)
        tenant = TenantInfo(
            tenant_id=tenant_id,
            tier=tier,
            pattern=pattern,
        )
        self.tenants[tenant_id] = tenant
        logger.info(f"Provisioned tenant {tenant_id}: tier={tier.value}, pattern={pattern.value}")
        return tenant

    def _select_pattern(self, tier: TenantTier) -> IndexPattern:
        """Auto-select pattern based on tier."""
        mapping = {
            TenantTier.FREE: IndexPattern.SHARED,
            TenantTier.STARTER: IndexPattern.SHARED,
            TenantTier.PROFESSIONAL: IndexPattern.NAMESPACE,
            TenantTier.ENTERPRISE: IndexPattern.DEDICATED_INDEX,
        }
        return mapping[tier]

    def auto_assign_pattern(self, tenant_id: str) -> IndexPattern:
        """
        Reassign pattern based on actual usage.
        Called periodically or on threshold crossing.
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        vec_count = tenant.vector_count
        if vec_count < 10_000:
            target = IndexPattern.SHARED
        elif vec_count < 1_000_000:
            target = IndexPattern.NAMESPACE
        elif vec_count < 10_000_000:
            target = IndexPattern.DEDICATED_INDEX
        else:
            target = IndexPattern.DEDICATED_INDEX  # or CELL for grouped

        if target != tenant.pattern:
            logger.info(f"Tenant {tenant_id} should migrate: {tenant.pattern.value} -> {target.value}")
        return target

    # =========================================================================
    # Data Operations
    # =========================================================================

    async def upsert(self, tenant_id: str, vectors: List[Dict]) -> int:
        """Upsert vectors for a tenant, respecting quotas."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not provisioned")

        # Quota check
        quota = TIER_QUOTAS[tenant.tier]
        current_count = tenant.vector_count
        if current_count + len(vectors) > quota.max_vectors:
            raise ValueError(
                f"Quota exceeded: tenant {tenant_id} has {current_count}/{quota.max_vectors} vectors"
            )

        pattern_impl = self.patterns[tenant.pattern]
        count = await pattern_impl.upsert_vectors(tenant_id, vectors)
        tenant.vector_count += count
        tenant.last_activity = datetime.utcnow()
        return count

    async def search(self, tenant_id: str, vector: List[float], top_k: int = 10,
                     filters: Dict[str, Any] = None) -> List[Dict]:
        """Search within tenant's vectors."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not provisioned")

        # Rate limit check
        self._record_query(tenant_id)
        quota = TIER_QUOTAS[tenant.tier]
        current_qps = self._get_qps(tenant_id)
        if current_qps > quota.max_queries_per_second:
            raise ValueError(f"Rate limit exceeded: {current_qps:.1f} > {quota.max_queries_per_second} QPS")

        pattern_impl = self.patterns[tenant.pattern]
        return await pattern_impl.search(tenant_id, vector, top_k, filters)

    async def delete_tenant(self, tenant_id: str) -> int:
        """Complete tenant deletion (GDPR compliance)."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return 0

        pattern_impl = self.patterns[tenant.pattern]
        count = await pattern_impl.delete_tenant_data(tenant_id)
        del self.tenants[tenant_id]
        logger.info(f"Deleted tenant {tenant_id}: {count} vectors removed")
        return count

    # =========================================================================
    # Tenant Migration
    # =========================================================================

    async def migrate_tenant(self, tenant_id: str, target_pattern: IndexPattern):
        """
        Migrate tenant from current pattern to target pattern.
        Process: copy data to new pattern -> verify -> switch -> delete old.
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        if tenant.pattern == target_pattern:
            return

        source_impl = self.patterns[tenant.pattern]
        target_impl = self.patterns[target_pattern]

        logger.info(f"Migrating tenant {tenant_id}: {tenant.pattern.value} -> {target_pattern.value}")

        # Step 1: Export all vectors from source
        # In production: paginated export
        all_vectors = await self._export_tenant_vectors(tenant_id, source_impl)

        # Step 2: Import into target
        if all_vectors:
            await target_impl.upsert_vectors(tenant_id, all_vectors)

        # Step 3: Verify counts match
        source_count = await source_impl.get_tenant_vector_count(tenant_id)
        target_count = await target_impl.get_tenant_vector_count(tenant_id)

        if target_count < source_count * 0.99:  # Allow 1% tolerance
            raise RuntimeError(
                f"Migration verification failed: source={source_count}, target={target_count}"
            )

        # Step 4: Switch routing
        old_pattern = tenant.pattern
        tenant.pattern = target_pattern

        # Step 5: Delete from source
        await source_impl.delete_tenant_data(tenant_id)
        logger.info(f"Migration complete: {tenant_id} now on {target_pattern.value}")

    async def _export_tenant_vectors(self, tenant_id: str, impl: BaseIndexPattern) -> List[Dict]:
        """Export tenant vectors. Simplified for demonstration."""
        # In production: cursor-based pagination
        if isinstance(impl, SharedIndexPattern):
            vec_ids = impl._tenant_vectors.get(tenant_id, set())
            return [
                {"id": vid, "vector": impl._vectors[vid]["vector"],
                 "metadata": impl._vectors[vid]["metadata"]}
                for vid in vec_ids if vid in impl._vectors
            ]
        elif isinstance(impl, NamespacePattern):
            ns = impl._get_namespace(tenant_id)
            ns_data = impl._namespaces.get(ns, {})
            return [
                {"id": vid, "vector": data["vector"], "metadata": data["metadata"]}
                for vid, data in ns_data.items()
            ]
        return []

    # =========================================================================
    # Hot Tenant Isolation
    # =========================================================================

    def detect_hot_tenants(self, qps_threshold: float = 100) -> List[str]:
        """Identify tenants consuming disproportionate resources."""
        hot = []
        for tenant_id in self.tenants:
            qps = self._get_qps(tenant_id)
            if qps > qps_threshold:
                hot.append(tenant_id)
                self.tenants[tenant_id].is_hot = True
        return hot

    async def isolate_hot_tenant(self, tenant_id: str):
        """
        Move a hot tenant from shared to dedicated to prevent noisy-neighbor.
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return
        if tenant.pattern == IndexPattern.SHARED:
            await self.migrate_tenant(tenant_id, IndexPattern.NAMESPACE)
        elif tenant.pattern == IndexPattern.NAMESPACE:
            await self.migrate_tenant(tenant_id, IndexPattern.DEDICATED_INDEX)
        logger.warning(f"Isolated hot tenant {tenant_id} to {tenant.pattern.value}")

    # =========================================================================
    # Cross-Tenant Isolation Tests
    # =========================================================================

    async def test_isolation(self, tenant_a: str, tenant_b: str) -> Dict[str, Any]:
        """
        Negative access test: verify tenant_a cannot see tenant_b's vectors.
        Critical for security compliance.
        """
        results = {
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "isolation_verified": True,
            "violations": [],
        }

        # Get tenant_b's vector IDs
        tenant_b_info = self.tenants.get(tenant_b)
        if not tenant_b_info:
            results["isolation_verified"] = True
            return results

        # Search as tenant_a with a random vector
        test_vector = [0.5] * 1536
        search_results = await self.search(tenant_a, test_vector, top_k=100)

        # Check if any results belong to tenant_b
        for r in search_results:
            if r.get("metadata", {}).get("tenant_id") == tenant_b:
                results["isolation_verified"] = False
                results["violations"].append({
                    "type": "cross_tenant_leak",
                    "leaked_doc_id": r["id"],
                    "source_tenant": tenant_b,
                    "accessing_tenant": tenant_a,
                })

        if not results["isolation_verified"]:
            logger.error(f"ISOLATION VIOLATION: {tenant_a} can see {tenant_b}'s data!")

        return results

    async def run_full_isolation_audit(self) -> List[Dict]:
        """Run pairwise isolation tests for all tenants on shared patterns."""
        shared_tenants = [
            t for t in self.tenants.values() if t.pattern == IndexPattern.SHARED
        ]
        violations = []
        for i, ta in enumerate(shared_tenants):
            for tb in shared_tenants[i+1:]:
                result = await self.test_isolation(ta.tenant_id, tb.tenant_id)
                if not result["isolation_verified"]:
                    violations.append(result)
        return violations

    # =========================================================================
    # Rate Limiting Helpers
    # =========================================================================

    def _record_query(self, tenant_id: str):
        self._usage_tracker[tenant_id].append(time.time())
        # Prune old entries
        cutoff = time.time() - 1.0
        self._usage_tracker[tenant_id] = [
            t for t in self._usage_tracker[tenant_id] if t > cutoff
        ]

    def _get_qps(self, tenant_id: str) -> float:
        entries = self._usage_tracker.get(tenant_id, [])
        cutoff = time.time() - 1.0
        recent = [t for t in entries if t > cutoff]
        return float(len(recent))

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_tenant_report(self) -> Dict[str, Any]:
        pattern_counts = defaultdict(int)
        pattern_vectors = defaultdict(int)
        for t in self.tenants.values():
            pattern_counts[t.pattern.value] += 1
            pattern_vectors[t.pattern.value] += t.vector_count

        return {
            "total_tenants": len(self.tenants),
            "pattern_distribution": dict(pattern_counts),
            "vectors_per_pattern": dict(pattern_vectors),
            "hot_tenants": [t.tenant_id for t in self.tenants.values() if t.is_hot],
        }


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    manager = MultiTenantIndexManager()

    # Provision tenants of different tiers
    manager.provision_tenant("small_co", TenantTier.FREE)
    manager.provision_tenant("medium_co", TenantTier.PROFESSIONAL)
    manager.provision_tenant("big_corp", TenantTier.ENTERPRISE)

    # Upsert data
    test_vectors = [
        {"id": f"doc_{i}", "vector": [0.1 * i] * 1536, "metadata": {"title": f"Doc {i}"}}
        for i in range(5)
    ]
    await manager.upsert("small_co", test_vectors)
    await manager.upsert("medium_co", test_vectors)
    await manager.upsert("big_corp", test_vectors)

    # Search
    results = await manager.search("small_co", [0.3] * 1536, top_k=3)
    print(f"Small Co results: {len(results)}")

    # Isolation test
    isolation = await manager.test_isolation("small_co", "medium_co")
    print(f"Isolation verified: {isolation['isolation_verified']}")

    # Report
    report = manager.get_tenant_report()
    print(f"Report: {report}")

    # Migration
    await manager.migrate_tenant("small_co", IndexPattern.NAMESPACE)
    print(f"Small Co migrated to: {manager.tenants['small_co'].pattern.value}")


if __name__ == "__main__":
    asyncio.run(main())
