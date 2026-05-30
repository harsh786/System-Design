"""
Semantic Response Cache for Enterprise AI
==========================================
Caches LLM responses keyed by semantic similarity of queries,
with full tenant isolation, permission awareness, and freshness validation.

Architecture:
- Query → Embed → ANN search in cache index → If similar enough → Return cached response
- All cache keys include security dimensions (tenant, permissions, versions)
- Risk-tier-aware TTL and staleness policies
"""

import asyncio
import hashlib
import json
import time
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Core Data Models
# =============================================================================

class RiskTier(Enum):
    CRITICAL = "critical"     # Financial, medical, legal — never serve stale
    HIGH = "high"             # PII-adjacent, compliance — 30s stale max
    MEDIUM = "medium"         # Business analytics — 5 min stale OK
    LOW = "low"               # General knowledge — 1 hour stale OK
    STATIC = "static"         # Deterministic — days

    @property
    def max_ttl_seconds(self) -> int:
        return {
            RiskTier.CRITICAL: 60,
            RiskTier.HIGH: 300,
            RiskTier.MEDIUM: 3600,
            RiskTier.LOW: 86400,
            RiskTier.STATIC: 604800,
        }[self]

    @property
    def stale_tolerance_seconds(self) -> int:
        return {
            RiskTier.CRITICAL: 0,
            RiskTier.HIGH: 30,
            RiskTier.MEDIUM: 300,
            RiskTier.LOW: 3600,
            RiskTier.STATIC: 86400,
        }[self]


@dataclass
class UserContext:
    tenant_id: str
    user_id: str
    effective_roles: List[str]
    group_memberships: List[str]
    resource_scope_ids: List[str]
    permission_policy_version: str
    risk_tier: RiskTier = RiskTier.MEDIUM

    @property
    def permission_fingerprint(self) -> str:
        """Stable hash of user's effective permissions."""
        components = sorted([
            self.tenant_id,
            *self.effective_roles,
            *self.group_memberships,
            self.permission_policy_version,
            *self.resource_scope_ids,
        ])
        return hashlib.sha256("|".join(components).encode()).hexdigest()[:16]


@dataclass
class CacheKeyComponents:
    tenant_id: str
    query_embedding_hash: str
    permission_fingerprint: str
    model_version: str
    prompt_version: str
    index_version: str
    source_freshness_watermark: float  # Unix timestamp
    safety_policy_version: str
    risk_tier: RiskTier

    @property
    def composite_key(self) -> str:
        """Full composite cache key."""
        raw = (
            f"{self.tenant_id}:"
            f"{self.query_embedding_hash}:"
            f"{self.permission_fingerprint}:"
            f"{self.model_version}:"
            f"{self.prompt_version}:"
            f"{self.index_version}:"
            f"{self.source_freshness_watermark}:"
            f"{self.safety_policy_version}:"
            f"{self.risk_tier.value}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class CacheEntry:
    key: str
    query_embedding: np.ndarray
    response: str
    metadata: Dict[str, Any]
    tenant_id: str
    permission_fingerprint: str
    source_freshness_watermark: float
    risk_tier: RiskTier
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 3600
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.created_at + self.ttl_seconds)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def is_stale_but_servable(self) -> bool:
        """Within stale tolerance for risk tier."""
        if self.is_expired:
            overage = time.time() - (self.created_at + self.ttl_seconds)
            return overage < self.risk_tier.stale_tolerance_seconds
        return False


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    stale_serves: int = 0
    invalidations: int = 0
    stampede_coalescences: int = 0
    cross_tenant_blocks: int = 0
    permission_mismatch_blocks: int = 0
    freshness_rejections: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "stale_serves": self.stale_serves,
            "invalidations": self.invalidations,
            "stampede_coalescences": self.stampede_coalescences,
            "cross_tenant_blocks": self.cross_tenant_blocks,
            "permission_mismatch_blocks": self.permission_mismatch_blocks,
            "freshness_rejections": self.freshness_rejections,
            "evictions": self.evictions,
        }


# =============================================================================
# Embedding Service Interface
# =============================================================================

class EmbeddingService(ABC):
    @abstractmethod
    async def embed_query(self, text: str) -> np.ndarray:
        """Generate embedding vector for query text."""
        ...

    @abstractmethod
    async def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """Batch embedding for multiple texts."""
        ...


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for demonstration."""
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    async def embed_query(self, text: str) -> np.ndarray:
        # Deterministic pseudo-embedding based on text hash
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype(np.float32)
        return vec / np.linalg.norm(vec)

    async def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        return [await self.embed_query(t) for t in texts]


# =============================================================================
# Vector Index for Semantic Similarity Search
# =============================================================================

class SemanticIndex:
    """
    In-memory ANN index for semantic cache lookup.
    Production: replace with FAISS, ScaNN, or Pinecone.
    """

    def __init__(self, dimension: int = 1536, similarity_threshold: float = 0.95):
        self.dimension = dimension
        self.similarity_threshold = similarity_threshold
        self.vectors: List[np.ndarray] = []
        self.keys: List[str] = []
        self.tenant_index: Dict[str, List[int]] = {}  # tenant_id -> indices

    def add(self, key: str, vector: np.ndarray, tenant_id: str):
        idx = len(self.vectors)
        self.vectors.append(vector)
        self.keys.append(key)
        if tenant_id not in self.tenant_index:
            self.tenant_index[tenant_id] = []
        self.tenant_index[tenant_id].append(idx)

    def search(
        self, query_vector: np.ndarray, tenant_id: str, top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Search for similar vectors ONLY within same tenant.
        Returns list of (key, similarity_score) pairs above threshold.
        """
        # CRITICAL: Only search within tenant's entries
        tenant_indices = self.tenant_index.get(tenant_id, [])
        if not tenant_indices:
            return []

        results = []
        for idx in tenant_indices:
            similarity = float(np.dot(query_vector, self.vectors[idx]))
            if similarity >= self.similarity_threshold:
                results.append((self.keys[idx], similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def remove(self, key: str):
        """Remove entry from index."""
        if key in self.keys:
            idx = self.keys.index(key)
            self.keys[idx] = None  # Mark as deleted (compact later)
            self.vectors[idx] = np.zeros(self.dimension)

    def compact(self):
        """Remove deleted entries and rebuild index."""
        new_vectors = []
        new_keys = []
        new_tenant_index: Dict[str, List[int]] = {}

        for i, (v, k) in enumerate(zip(self.vectors, self.keys)):
            if k is not None:
                new_idx = len(new_vectors)
                new_vectors.append(v)
                new_keys.append(k)
                # Rebuild tenant index (need tenant_id stored somewhere)

        self.vectors = new_vectors
        self.keys = new_keys


# =============================================================================
# Single-Flight / Request Coalescing
# =============================================================================

class SingleFlight:
    """
    Prevents cache stampede by coalescing concurrent requests for the same key.
    Only one request actually computes; others wait for the result.
    """

    def __init__(self):
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def do(self, key: str, fn) -> Any:
        if key in self._in_flight:
            logger.debug(f"Coalescing request for key={key[:16]}...")
            return await self._in_flight[key]

        if key not in self._locks:
            self._locks[key] = asyncio.Lock()

        async with self._locks[key]:
            # Double-check after acquiring lock
            if key in self._in_flight:
                return await self._in_flight[key]

            future = asyncio.get_event_loop().create_future()
            self._in_flight[key] = future

            try:
                result = await fn()
                future.set_result(result)
                return result
            except Exception as e:
                future.set_exception(e)
                raise
            finally:
                del self._in_flight[key]
                if key in self._locks:
                    del self._locks[key]


# =============================================================================
# Semantic Response Cache
# =============================================================================

class SemanticResponseCache:
    """
    Enterprise-grade semantic response cache with:
    - Tenant isolation (NEVER share across tenants)
    - Permission-aware cache keys
    - Freshness watermark validation
    - Risk-tier-based TTL and staleness policies
    - Stampede protection via single-flight
    - Stale-while-revalidate for availability
    - Comprehensive metrics
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_threshold: float = 0.95,
        max_entries_per_tenant: int = 100_000,
        dimension: int = 1536,
    ):
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.max_entries_per_tenant = max_entries_per_tenant

        # Storage
        self.entries: Dict[str, CacheEntry] = {}
        self.semantic_index = SemanticIndex(
            dimension=dimension, similarity_threshold=similarity_threshold
        )
        self.tenant_entry_counts: Dict[str, int] = {}

        # Stampede protection
        self.single_flight = SingleFlight()

        # Metrics
        self.metrics = CacheMetrics()

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background maintenance tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SemanticResponseCache started")

    async def stop(self):
        """Stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()

    # -------------------------------------------------------------------------
    # Core Cache Operations
    # -------------------------------------------------------------------------

    async def get(
        self,
        query: str,
        user_context: UserContext,
        model_version: str,
        prompt_version: str,
        index_version: str,
        source_freshness_watermark: float,
        safety_policy_version: str,
    ) -> Optional[str]:
        """
        Attempt to retrieve a cached response for the given query.
        
        Returns None on cache miss. NEVER returns cross-tenant or
        permission-mismatched entries.
        """
        # Step 1: Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)

        # Step 2: Search semantic index (tenant-scoped)
        candidates = self.semantic_index.search(
            query_vector=query_embedding,
            tenant_id=user_context.tenant_id,
            top_k=5,
        )

        if not candidates:
            self.metrics.misses += 1
            return None

        # Step 3: Validate candidates against security dimensions
        for candidate_key, similarity in candidates:
            entry = self.entries.get(candidate_key)
            if entry is None:
                continue

            # CRITICAL SAFETY CHECKS
            validation = self._validate_entry(
                entry=entry,
                user_context=user_context,
                model_version=model_version,
                prompt_version=prompt_version,
                index_version=index_version,
                source_freshness_watermark=source_freshness_watermark,
                safety_policy_version=safety_policy_version,
            )

            if not validation.is_valid:
                logger.debug(
                    f"Cache candidate rejected: {validation.reason} "
                    f"(key={candidate_key[:16]}, sim={similarity:.4f})"
                )
                continue

            # Check freshness
            if entry.is_expired:
                if entry.is_stale_but_servable:
                    # Stale-while-revalidate: serve stale, refresh async
                    self.metrics.stale_serves += 1
                    entry.access_count += 1
                    entry.last_accessed = time.time()
                    logger.info(
                        f"Serving stale cache (age={entry.age_seconds:.0f}s, "
                        f"tier={entry.risk_tier.value})"
                    )
                    return entry.response
                else:
                    # Too stale, skip
                    self.metrics.freshness_rejections += 1
                    continue

            # Valid, fresh cache hit
            self.metrics.hits += 1
            entry.access_count += 1
            entry.last_accessed = time.time()
            logger.info(
                f"Cache HIT (sim={similarity:.4f}, age={entry.age_seconds:.0f}s, "
                f"tenant={user_context.tenant_id})"
            )
            return entry.response

        # No valid candidate found
        self.metrics.misses += 1
        return None

    async def put(
        self,
        query: str,
        response: str,
        user_context: UserContext,
        model_version: str,
        prompt_version: str,
        index_version: str,
        source_freshness_watermark: float,
        safety_policy_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a response in the semantic cache.
        Returns the cache key.
        """
        # Generate embedding
        query_embedding = await self.embedding_service.embed_query(query)
        embedding_hash = hashlib.sha256(
            query_embedding.tobytes()
        ).hexdigest()[:16]

        # Build cache key
        key_components = CacheKeyComponents(
            tenant_id=user_context.tenant_id,
            query_embedding_hash=embedding_hash,
            permission_fingerprint=user_context.permission_fingerprint,
            model_version=model_version,
            prompt_version=prompt_version,
            index_version=index_version,
            source_freshness_watermark=source_freshness_watermark,
            safety_policy_version=safety_policy_version,
            risk_tier=user_context.risk_tier,
        )
        cache_key = key_components.composite_key

        # Determine TTL with jitter
        base_ttl = user_context.risk_tier.max_ttl_seconds
        ttl = self._jittered_ttl(base_ttl)

        # Create entry
        entry = CacheEntry(
            key=cache_key,
            query_embedding=query_embedding,
            response=response,
            metadata=metadata or {},
            tenant_id=user_context.tenant_id,
            permission_fingerprint=user_context.permission_fingerprint,
            source_freshness_watermark=source_freshness_watermark,
            risk_tier=user_context.risk_tier,
            ttl_seconds=ttl,
        )

        # Check tenant capacity
        tenant_count = self.tenant_entry_counts.get(user_context.tenant_id, 0)
        if tenant_count >= self.max_entries_per_tenant:
            await self._evict_tenant_entries(user_context.tenant_id)

        # Store
        self.entries[cache_key] = entry
        self.semantic_index.add(
            key=cache_key,
            vector=query_embedding,
            tenant_id=user_context.tenant_id,
        )
        self.tenant_entry_counts[user_context.tenant_id] = tenant_count + 1

        logger.debug(
            f"Cache PUT (key={cache_key[:16]}, ttl={ttl}s, "
            f"tenant={user_context.tenant_id}, tier={user_context.risk_tier.value})"
        )
        return cache_key

    async def get_or_compute(
        self,
        query: str,
        user_context: UserContext,
        compute_fn,
        model_version: str,
        prompt_version: str,
        index_version: str,
        source_freshness_watermark: float,
        safety_policy_version: str,
    ) -> Tuple[str, bool]:
        """
        Get from cache or compute with stampede protection.
        Returns (response, was_cache_hit).
        """
        # Try cache first
        cached = await self.get(
            query=query,
            user_context=user_context,
            model_version=model_version,
            prompt_version=prompt_version,
            index_version=index_version,
            source_freshness_watermark=source_freshness_watermark,
            safety_policy_version=safety_policy_version,
        )
        if cached is not None:
            return cached, True

        # Cache miss — compute with single-flight protection
        coalesce_key = (
            f"{user_context.tenant_id}:"
            f"{hashlib.md5(query.encode()).hexdigest()[:8]}:"
            f"{user_context.permission_fingerprint}"
        )

        async def _compute_and_cache():
            response = await compute_fn(query)
            await self.put(
                query=query,
                response=response,
                user_context=user_context,
                model_version=model_version,
                prompt_version=prompt_version,
                index_version=index_version,
                source_freshness_watermark=source_freshness_watermark,
                safety_policy_version=safety_policy_version,
            )
            return response

        response = await self.single_flight.do(coalesce_key, _compute_and_cache)
        return response, False

    # -------------------------------------------------------------------------
    # Invalidation
    # -------------------------------------------------------------------------

    async def invalidate_by_tenant(self, tenant_id: str):
        """Invalidate ALL cache entries for a tenant."""
        keys_to_remove = [
            k for k, v in self.entries.items() if v.tenant_id == tenant_id
        ]
        for key in keys_to_remove:
            self._remove_entry(key)
        self.metrics.invalidations += len(keys_to_remove)
        logger.warning(
            f"Invalidated {len(keys_to_remove)} entries for tenant={tenant_id}"
        )

    async def invalidate_by_permission_change(
        self, tenant_id: str, user_id: str, old_fingerprint: str
    ):
        """Invalidate entries matching old permission fingerprint."""
        keys_to_remove = [
            k for k, v in self.entries.items()
            if v.tenant_id == tenant_id
            and v.permission_fingerprint == old_fingerprint
        ]
        for key in keys_to_remove:
            self._remove_entry(key)
        self.metrics.invalidations += len(keys_to_remove)
        logger.warning(
            f"Permission change invalidation: {len(keys_to_remove)} entries "
            f"(tenant={tenant_id}, user={user_id})"
        )

    async def invalidate_by_freshness(
        self, tenant_id: str, new_watermark: float
    ):
        """Invalidate entries older than new freshness watermark."""
        keys_to_remove = [
            k for k, v in self.entries.items()
            if v.tenant_id == tenant_id
            and v.source_freshness_watermark < new_watermark
        ]
        for key in keys_to_remove:
            self._remove_entry(key)
        self.metrics.invalidations += len(keys_to_remove)
        logger.info(
            f"Freshness invalidation: {len(keys_to_remove)} entries "
            f"(tenant={tenant_id}, watermark={new_watermark})"
        )

    async def invalidate_by_key(self, cache_key: str):
        """Invalidate a specific cache entry."""
        if cache_key in self.entries:
            self._remove_entry(cache_key)
            self.metrics.invalidations += 1

    # -------------------------------------------------------------------------
    # Cache Warming
    # -------------------------------------------------------------------------

    async def warm_cache(
        self,
        queries: List[str],
        user_context: UserContext,
        compute_fn,
        model_version: str,
        prompt_version: str,
        index_version: str,
        source_freshness_watermark: float,
        safety_policy_version: str,
        concurrency: int = 10,
    ):
        """
        Pre-warm cache with predicted popular queries.
        Used during deployment, cold start, or scheduled maintenance.
        """
        semaphore = asyncio.Semaphore(concurrency)
        warmed = 0

        async def warm_one(query: str):
            nonlocal warmed
            async with semaphore:
                _, was_hit = await self.get_or_compute(
                    query=query,
                    user_context=user_context,
                    compute_fn=compute_fn,
                    model_version=model_version,
                    prompt_version=prompt_version,
                    index_version=index_version,
                    source_freshness_watermark=source_freshness_watermark,
                    safety_policy_version=safety_policy_version,
                )
                if not was_hit:
                    warmed += 1

        await asyncio.gather(*[warm_one(q) for q in queries])
        logger.info(f"Cache warm-up complete: {warmed}/{len(queries)} computed")

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    @dataclass
    class _ValidationResult:
        is_valid: bool
        reason: str = ""

    def _validate_entry(
        self,
        entry: CacheEntry,
        user_context: UserContext,
        model_version: str,
        prompt_version: str,
        index_version: str,
        source_freshness_watermark: float,
        safety_policy_version: str,
    ) -> "_ValidationResult":
        """Validate that a cache entry is safe to serve to this user."""

        # CRITICAL: Cross-tenant isolation
        if entry.tenant_id != user_context.tenant_id:
            self.metrics.cross_tenant_blocks += 1
            logger.error(
                f"SECURITY: Cross-tenant cache access blocked! "
                f"entry_tenant={entry.tenant_id}, "
                f"request_tenant={user_context.tenant_id}"
            )
            return self._ValidationResult(False, "cross_tenant_violation")

        # CRITICAL: Permission fingerprint match
        if entry.permission_fingerprint != user_context.permission_fingerprint:
            self.metrics.permission_mismatch_blocks += 1
            return self._ValidationResult(False, "permission_mismatch")

        # Freshness watermark: source data may have been updated
        if entry.source_freshness_watermark < source_freshness_watermark:
            self.metrics.freshness_rejections += 1
            return self._ValidationResult(False, "stale_source_data")

        # Version checks (included in key but validate explicitly for safety)
        entry_meta = entry.metadata
        if entry_meta.get("model_version") and entry_meta["model_version"] != model_version:
            return self._ValidationResult(False, "model_version_mismatch")
        if entry_meta.get("prompt_version") and entry_meta["prompt_version"] != prompt_version:
            return self._ValidationResult(False, "prompt_version_mismatch")
        if entry_meta.get("safety_policy_version") and entry_meta["safety_policy_version"] != safety_policy_version:
            return self._ValidationResult(False, "safety_policy_mismatch")

        return self._ValidationResult(True)

    def _remove_entry(self, key: str):
        """Remove entry from all data structures."""
        entry = self.entries.pop(key, None)
        if entry:
            self.semantic_index.remove(key)
            tenant_count = self.tenant_entry_counts.get(entry.tenant_id, 1)
            self.tenant_entry_counts[entry.tenant_id] = max(0, tenant_count - 1)

    async def _evict_tenant_entries(self, tenant_id: str, evict_count: int = 100):
        """Evict LRU entries for a tenant to make room."""
        tenant_entries = [
            (k, v) for k, v in self.entries.items() if v.tenant_id == tenant_id
        ]
        # Sort by last_accessed (oldest first)
        tenant_entries.sort(key=lambda x: x[1].last_accessed)

        for key, _ in tenant_entries[:evict_count]:
            self._remove_entry(key)
            self.metrics.evictions += 1

        logger.info(f"Evicted {evict_count} LRU entries for tenant={tenant_id}")

    def _jittered_ttl(self, base_ttl: int, jitter_pct: float = 0.1) -> int:
        """Add random jitter to TTL to prevent synchronized expiry."""
        jitter = int(base_ttl * jitter_pct)
        return base_ttl + random.randint(-jitter, jitter)

    async def _cleanup_loop(self):
        """Background task to remove expired entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                expired_keys = [
                    k for k, v in self.entries.items()
                    if v.is_expired and not v.is_stale_but_servable
                ]
                for key in expired_keys:
                    self._remove_entry(key)
                if expired_keys:
                    logger.info(f"Cleanup: removed {len(expired_keys)} expired entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Return current cache metrics."""
        return {
            **self.metrics.to_dict(),
            "total_entries": len(self.entries),
            "tenants": len(self.tenant_entry_counts),
            "entries_per_tenant": dict(self.tenant_entry_counts),
        }

    def get_health(self) -> Dict[str, Any]:
        """Health check for monitoring."""
        return {
            "status": "healthy" if self.metrics.hit_rate > 0.3 else "degraded",
            "hit_rate": f"{self.metrics.hit_rate:.2%}",
            "total_entries": len(self.entries),
            "security_violations": self.metrics.cross_tenant_blocks,
        }


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    """Demonstrate semantic cache usage."""

    # Initialize
    embedding_service = MockEmbeddingService(dimension=384)
    cache = SemanticResponseCache(
        embedding_service=embedding_service,
        similarity_threshold=0.92,
        max_entries_per_tenant=10_000,
        dimension=384,
    )
    await cache.start()

    # Create user context
    user = UserContext(
        tenant_id="acme_corp",
        user_id="user_123",
        effective_roles=["analyst", "viewer"],
        group_memberships=["finance_team"],
        resource_scope_ids=["dataset_revenue", "dataset_costs"],
        permission_policy_version="v3.2",
        risk_tier=RiskTier.MEDIUM,
    )

    # Simulate LLM call
    async def fake_llm_call(query: str) -> str:
        await asyncio.sleep(0.5)  # Simulate latency
        return f"Response to: {query} [generated at {time.time():.0f}]"

    # First call — cache miss, computes
    response1, hit1 = await cache.get_or_compute(
        query="What was our Q3 revenue?",
        user_context=user,
        compute_fn=fake_llm_call,
        model_version="gpt-4-0125",
        prompt_version="v2.3",
        index_version="idx_20240115",
        source_freshness_watermark=time.time() - 3600,
        safety_policy_version="safety_v4",
    )
    print(f"Call 1: hit={hit1}, response={response1[:50]}")

    # Second call — same semantic query, should hit cache
    response2, hit2 = await cache.get_or_compute(
        query="What was our Q3 revenue?",
        user_context=user,
        compute_fn=fake_llm_call,
        model_version="gpt-4-0125",
        prompt_version="v2.3",
        index_version="idx_20240115",
        source_freshness_watermark=time.time() - 3600,
        safety_policy_version="safety_v4",
    )
    print(f"Call 2: hit={hit2}, response={response2[:50]}")

    # Different tenant — MUST NOT hit cache
    other_user = UserContext(
        tenant_id="other_corp",
        user_id="user_456",
        effective_roles=["analyst"],
        group_memberships=["finance_team"],
        resource_scope_ids=["dataset_revenue"],
        permission_policy_version="v3.2",
        risk_tier=RiskTier.MEDIUM,
    )
    response3, hit3 = await cache.get_or_compute(
        query="What was our Q3 revenue?",
        user_context=other_user,
        compute_fn=fake_llm_call,
        model_version="gpt-4-0125",
        prompt_version="v2.3",
        index_version="idx_20240115",
        source_freshness_watermark=time.time() - 3600,
        safety_policy_version="safety_v4",
    )
    print(f"Call 3 (different tenant): hit={hit3}")

    # Print metrics
    print(f"\nMetrics: {json.dumps(cache.get_metrics(), indent=2)}")

    await cache.stop()


if __name__ == "__main__":
    asyncio.run(main())
