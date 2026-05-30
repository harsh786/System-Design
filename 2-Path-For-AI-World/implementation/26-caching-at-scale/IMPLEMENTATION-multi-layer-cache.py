"""
Multi-Layer Cache System for Enterprise AI
============================================
Orchestrates 9 cache layers with unified key building, invalidation bus,
and metrics aggregation. Each layer operates independently but shares
invalidation events and security enforcement.

Architecture:
    Request → CacheOrchestrator → [Layer1, Layer2, ...LayerN] → Backend
    
    Each layer:
    - Has its own TTL policy
    - Shares tenant isolation enforcement
    - Publishes/subscribes to invalidation events
    - Reports metrics to central aggregator
"""

import asyncio
import hashlib
import json
import time
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Core Types
# =============================================================================

class CacheLayer(Enum):
    PROMPT_PREFIX = "prompt_prefix"
    SEMANTIC_RESPONSE = "semantic_response"
    RETRIEVAL_RESULT = "retrieval_result"
    EMBEDDING = "embedding"
    TOOL_RESULT = "tool_result"
    RERANKER = "reranker"
    AUTH_DECISION = "auth_decision"
    DOCUMENT_PARSE = "document_parse"
    EVAL_QUALITY = "eval_quality"


class RiskTier(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    STATIC = "static"


class InvalidationReason(Enum):
    DOCUMENT_CHANGE = "document_change"
    PERMISSION_CHANGE = "permission_change"
    POLICY_CHANGE = "policy_change"
    MODEL_VERSION_CHANGE = "model_version_change"
    PROMPT_VERSION_CHANGE = "prompt_version_change"
    INDEX_VERSION_CHANGE = "index_version_change"
    TOOL_SCHEMA_CHANGE = "tool_schema_change"
    TTL_EXPIRED = "ttl_expired"
    MANUAL = "manual"
    SECURITY_INCIDENT = "security_incident"


@dataclass
class InvalidationEvent:
    reason: InvalidationReason
    tenant_id: str
    affected_layers: List[CacheLayer]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    propagate_cross_region: bool = False

    @property
    def event_id(self) -> str:
        return hashlib.md5(
            f"{self.reason.value}:{self.tenant_id}:{self.timestamp}".encode()
        ).hexdigest()[:12]


@dataclass
class CacheKeyContext:
    """All dimensions needed to build a secure cache key."""
    tenant_id: str
    user_id: str
    permission_fingerprint: str
    model_version: str
    prompt_version: str
    index_version: str
    source_freshness_watermark: float
    safety_policy_version: str
    risk_tier: RiskTier
    # Optional per-layer dimensions
    tool_name: Optional[str] = None
    tool_parameters: Optional[Dict] = None
    document_hash: Optional[str] = None
    parser_version: Optional[str] = None
    embedding_model_version: Optional[str] = None
    reranker_model_version: Optional[str] = None
    eval_criteria_version: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None


# =============================================================================
# Cache Key Builder
# =============================================================================

class CacheKeyBuilder:
    """
    Builds secure, multi-dimensional cache keys for each layer.
    
    SECURITY INVARIANT: Every key MUST include tenant_id at minimum.
    Most keys also include permission_fingerprint.
    """

    @staticmethod
    def build(layer: CacheLayer, context: CacheKeyContext, content_hash: str = "") -> str:
        """Build a cache key for the specified layer with all required security dimensions."""
        
        # Base dimensions (always included)
        base = f"{layer.value}:{context.tenant_id}"

        if layer == CacheLayer.PROMPT_PREFIX:
            # Exact token match — no permission needed (system prompt is same for all)
            raw = f"{base}:{context.prompt_version}:{context.model_version}:{content_hash}"

        elif layer == CacheLayer.SEMANTIC_RESPONSE:
            # Full security dimensions
            raw = (
                f"{base}:{content_hash}:"
                f"{context.permission_fingerprint}:"
                f"{context.model_version}:{context.prompt_version}:"
                f"{context.index_version}:"
                f"{context.source_freshness_watermark}:"
                f"{context.safety_policy_version}:"
                f"{context.risk_tier.value}"
            )

        elif layer == CacheLayer.RETRIEVAL_RESULT:
            raw = (
                f"{base}:{content_hash}:"
                f"{context.index_version}:"
                f"{context.permission_fingerprint}"
            )

        elif layer == CacheLayer.EMBEDDING:
            # Embeddings are deterministic — no permission needed
            raw = (
                f"{base}:{content_hash}:"
                f"{context.embedding_model_version or context.model_version}"
            )

        elif layer == CacheLayer.TOOL_RESULT:
            tool_params_hash = hashlib.md5(
                json.dumps(context.tool_parameters or {}, sort_keys=True).encode()
            ).hexdigest()[:12]
            raw = (
                f"{base}:{context.tool_name}:{tool_params_hash}:"
                f"{context.permission_fingerprint}:"
                f"{context.source_freshness_watermark}"
            )

        elif layer == CacheLayer.RERANKER:
            raw = (
                f"{base}:{content_hash}:"
                f"{context.reranker_model_version or 'default'}"
            )

        elif layer == CacheLayer.AUTH_DECISION:
            raw = (
                f"{base}:{context.user_id}:"
                f"{context.resource_id}:{context.action}:"
                f"{context.permission_fingerprint}"
            )

        elif layer == CacheLayer.DOCUMENT_PARSE:
            raw = (
                f"{base}:{context.document_hash}:"
                f"{context.parser_version or 'default'}"
            )

        elif layer == CacheLayer.EVAL_QUALITY:
            raw = (
                f"{base}:{content_hash}:"
                f"{context.eval_criteria_version or 'default'}"
            )

        else:
            raw = f"{base}:{content_hash}"

        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def get_ttl(layer: CacheLayer, risk_tier: RiskTier) -> int:
        """Get TTL in seconds for layer + risk tier combination."""
        ttl_matrix = {
            CacheLayer.PROMPT_PREFIX: {
                RiskTier.CRITICAL: 3600, RiskTier.HIGH: 7200,
                RiskTier.MEDIUM: 14400, RiskTier.LOW: 86400, RiskTier.STATIC: 604800,
            },
            CacheLayer.SEMANTIC_RESPONSE: {
                RiskTier.CRITICAL: 60, RiskTier.HIGH: 300,
                RiskTier.MEDIUM: 3600, RiskTier.LOW: 86400, RiskTier.STATIC: 604800,
            },
            CacheLayer.RETRIEVAL_RESULT: {
                RiskTier.CRITICAL: 120, RiskTier.HIGH: 600,
                RiskTier.MEDIUM: 3600, RiskTier.LOW: 43200, RiskTier.STATIC: 604800,
            },
            CacheLayer.EMBEDDING: {
                RiskTier.CRITICAL: 604800, RiskTier.HIGH: 604800,
                RiskTier.MEDIUM: 604800, RiskTier.LOW: 604800, RiskTier.STATIC: 2592000,
            },
            CacheLayer.TOOL_RESULT: {
                RiskTier.CRITICAL: 10, RiskTier.HIGH: 60,
                RiskTier.MEDIUM: 600, RiskTier.LOW: 3600, RiskTier.STATIC: 86400,
            },
            CacheLayer.RERANKER: {
                RiskTier.CRITICAL: 300, RiskTier.HIGH: 600,
                RiskTier.MEDIUM: 3600, RiskTier.LOW: 43200, RiskTier.STATIC: 604800,
            },
            CacheLayer.AUTH_DECISION: {
                RiskTier.CRITICAL: 10, RiskTier.HIGH: 30,
                RiskTier.MEDIUM: 60, RiskTier.LOW: 300, RiskTier.STATIC: 300,
            },
            CacheLayer.DOCUMENT_PARSE: {
                RiskTier.CRITICAL: 604800, RiskTier.HIGH: 604800,
                RiskTier.MEDIUM: 604800, RiskTier.LOW: 2592000, RiskTier.STATIC: 2592000,
            },
            CacheLayer.EVAL_QUALITY: {
                RiskTier.CRITICAL: 3600, RiskTier.HIGH: 7200,
                RiskTier.MEDIUM: 86400, RiskTier.LOW: 604800, RiskTier.STATIC: 2592000,
            },
        }
        base_ttl = ttl_matrix.get(layer, {}).get(risk_tier, 3600)
        # Add jitter
        jitter = int(base_ttl * 0.1)
        return base_ttl + random.randint(-jitter, max(jitter, 1))


# =============================================================================
# Invalidation Event Bus
# =============================================================================

class InvalidationEventBus:
    """
    Pub/Sub bus for cache invalidation events.
    All cache layers subscribe to relevant events.
    Supports cross-region propagation.
    """

    def __init__(self):
        self._subscribers: Dict[CacheLayer, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []
        self._event_log: List[InvalidationEvent] = []
        self._cross_region_queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, layer: CacheLayer, handler: Callable):
        """Subscribe a cache layer to invalidation events."""
        if layer not in self._subscribers:
            self._subscribers[layer] = []
        self._subscribers[layer].append(handler)

    def subscribe_global(self, handler: Callable):
        """Subscribe to ALL invalidation events (for monitoring)."""
        self._global_subscribers.append(handler)

    async def publish(self, event: InvalidationEvent):
        """Publish invalidation event to affected layers."""
        self._event_log.append(event)
        logger.info(
            f"Invalidation event: reason={event.reason.value}, "
            f"tenant={event.tenant_id}, layers={[l.value for l in event.affected_layers]}"
        )

        # Notify affected layers
        tasks = []
        for layer in event.affected_layers:
            handlers = self._subscribers.get(layer, [])
            for handler in handlers:
                tasks.append(asyncio.create_task(handler(event)))

        # Notify global subscribers
        for handler in self._global_subscribers:
            tasks.append(asyncio.create_task(handler(event)))

        # Cross-region propagation
        if event.propagate_cross_region:
            await self._cross_region_queue.put(event)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_document_change(self, tenant_id: str, document_id: str):
        """Convenience: document ingested/updated/deleted."""
        await self.publish(InvalidationEvent(
            reason=InvalidationReason.DOCUMENT_CHANGE,
            tenant_id=tenant_id,
            affected_layers=[
                CacheLayer.RETRIEVAL_RESULT,
                CacheLayer.SEMANTIC_RESPONSE,
                CacheLayer.RERANKER,
                CacheLayer.DOCUMENT_PARSE,
            ],
            metadata={"document_id": document_id},
            propagate_cross_region=True,
        ))

    async def publish_permission_change(
        self, tenant_id: str, user_id: str, old_fingerprint: str
    ):
        """Convenience: user permission revoked/changed."""
        await self.publish(InvalidationEvent(
            reason=InvalidationReason.PERMISSION_CHANGE,
            tenant_id=tenant_id,
            affected_layers=[
                CacheLayer.AUTH_DECISION,
                CacheLayer.SEMANTIC_RESPONSE,
                CacheLayer.RETRIEVAL_RESULT,
                CacheLayer.TOOL_RESULT,
            ],
            metadata={"user_id": user_id, "old_fingerprint": old_fingerprint},
            propagate_cross_region=True,
        ))

    async def publish_policy_change(self, tenant_id: str, policy_version: str):
        """Convenience: safety/governance policy updated."""
        await self.publish(InvalidationEvent(
            reason=InvalidationReason.POLICY_CHANGE,
            tenant_id=tenant_id,
            affected_layers=[
                CacheLayer.SEMANTIC_RESPONSE,
                CacheLayer.AUTH_DECISION,
                CacheLayer.EVAL_QUALITY,
            ],
            metadata={"policy_version": policy_version},
            propagate_cross_region=True,
        ))

    async def publish_model_change(self, model_version: str):
        """Convenience: model version updated (affects all tenants)."""
        await self.publish(InvalidationEvent(
            reason=InvalidationReason.MODEL_VERSION_CHANGE,
            tenant_id="*",  # All tenants
            affected_layers=[
                CacheLayer.SEMANTIC_RESPONSE,
                CacheLayer.EMBEDDING,
                CacheLayer.RERANKER,
                CacheLayer.EVAL_QUALITY,
            ],
            metadata={"model_version": model_version},
            propagate_cross_region=True,
        ))

    def get_event_log(self, limit: int = 100) -> List[Dict]:
        """Return recent invalidation events for monitoring."""
        return [
            {
                "event_id": e.event_id,
                "reason": e.reason.value,
                "tenant_id": e.tenant_id,
                "layers": [l.value for l in e.affected_layers],
                "timestamp": e.timestamp,
            }
            for e in self._event_log[-limit:]
        ]


# =============================================================================
# Abstract Cache Layer
# =============================================================================

class BaseCacheLayer(ABC):
    """Base class for all cache layers with shared security enforcement."""

    def __init__(self, layer: CacheLayer, event_bus: InvalidationEventBus):
        self.layer = layer
        self.event_bus = event_bus
        self._store: Dict[str, Dict[str, Any]] = {}
        self._metrics = LayerMetrics(layer_name=layer.value)

        # Subscribe to invalidation events
        event_bus.subscribe(layer, self._handle_invalidation)

    async def get(self, key: str, context: CacheKeyContext) -> Optional[Any]:
        """Get from cache with security validation."""
        entry = self._store.get(key)
        if entry is None:
            self._metrics.misses += 1
            return None

        # Security validation
        if entry["tenant_id"] != context.tenant_id:
            self._metrics.security_blocks += 1
            logger.error(f"SECURITY: Cross-tenant access blocked in {self.layer.value}")
            return None

        # TTL check
        if time.time() > entry["expires_at"]:
            self._metrics.expirations += 1
            del self._store[key]
            return None

        self._metrics.hits += 1
        entry["last_accessed"] = time.time()
        entry["access_count"] = entry.get("access_count", 0) + 1
        return entry["value"]

    async def put(
        self, key: str, value: Any, context: CacheKeyContext, ttl: Optional[int] = None
    ):
        """Store in cache."""
        if ttl is None:
            ttl = CacheKeyBuilder.get_ttl(self.layer, context.risk_tier)

        self._store[key] = {
            "value": value,
            "tenant_id": context.tenant_id,
            "permission_fingerprint": context.permission_fingerprint,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "last_accessed": time.time(),
            "access_count": 0,
            "risk_tier": context.risk_tier.value,
        }
        self._metrics.writes += 1

    async def _handle_invalidation(self, event: InvalidationEvent):
        """Handle invalidation event for this layer."""
        if event.tenant_id == "*":
            # Global invalidation
            count = len(self._store)
            self._store.clear()
            self._metrics.invalidations += count
        else:
            # Tenant-scoped invalidation
            keys_to_remove = [
                k for k, v in self._store.items()
                if v["tenant_id"] == event.tenant_id
            ]
            # For permission changes, only invalidate matching fingerprint
            if event.reason == InvalidationReason.PERMISSION_CHANGE:
                old_fp = event.metadata.get("old_fingerprint")
                if old_fp:
                    keys_to_remove = [
                        k for k in keys_to_remove
                        if self._store[k].get("permission_fingerprint") == old_fp
                    ]

            for key in keys_to_remove:
                del self._store[key]
            self._metrics.invalidations += len(keys_to_remove)

    @property
    def metrics(self) -> "LayerMetrics":
        return self._metrics


@dataclass
class LayerMetrics:
    layer_name: str
    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidations: int = 0
    expirations: int = 0
    security_blocks: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "layer": self.layer_name,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "hit_rate": f"{self.hit_rate:.2%}",
            "invalidations": self.invalidations,
            "expirations": self.expirations,
            "security_blocks": self.security_blocks,
        }


# =============================================================================
# Concrete Cache Layers
# =============================================================================

class PromptPrefixCache(BaseCacheLayer):
    """L1: GPU KV-cache prefix sharing. Exact token match."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.PROMPT_PREFIX, event_bus)


class SemanticResponseCacheLayer(BaseCacheLayer):
    """L2: Semantic similarity-based response cache."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.SEMANTIC_RESPONSE, event_bus)
        # In production, this would use a vector index (FAISS, ScaNN)
        self._embeddings: Dict[str, np.ndarray] = {}

    async def semantic_get(
        self, query_embedding: np.ndarray, context: CacheKeyContext, threshold: float = 0.95
    ) -> Optional[Any]:
        """Search by semantic similarity within tenant scope."""
        best_match = None
        best_score = 0.0

        for key, emb in self._embeddings.items():
            entry = self._store.get(key)
            if entry is None or entry["tenant_id"] != context.tenant_id:
                continue
            if entry["permission_fingerprint"] != context.permission_fingerprint:
                continue

            score = float(np.dot(query_embedding, emb))
            if score > threshold and score > best_score:
                best_match = key
                best_score = score

        if best_match:
            return await self.get(best_match, context)
        self._metrics.misses += 1
        return None

    async def semantic_put(
        self, key: str, value: Any, embedding: np.ndarray, context: CacheKeyContext
    ):
        """Store with embedding for semantic search."""
        await self.put(key, value, context)
        self._embeddings[key] = embedding


class RetrievalResultCache(BaseCacheLayer):
    """L3: Caches RAG retrieval results (chunks from vector search)."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.RETRIEVAL_RESULT, event_bus)


class EmbeddingCache(BaseCacheLayer):
    """L4: Caches computed embeddings (deterministic, long TTL)."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.EMBEDDING, event_bus)


class ToolResultCache(BaseCacheLayer):
    """L5: Caches tool/API call results."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.TOOL_RESULT, event_bus)

    # Tool-specific TTL overrides
    TOOL_TTL_OVERRIDES = {
        "calculator": 2592000,       # 30 days (deterministic)
        "sql_query": 300,            # 5 min (data changes)
        "web_search": 3600,          # 1 hour
        "stock_price": 10,           # 10 seconds (real-time)
        "weather": 600,              # 10 minutes
        "user_profile": 120,         # 2 minutes
    }

    async def put_tool_result(
        self, key: str, value: Any, tool_name: str, context: CacheKeyContext
    ):
        ttl = self.TOOL_TTL_OVERRIDES.get(
            tool_name, CacheKeyBuilder.get_ttl(self.layer, context.risk_tier)
        )
        await self.put(key, value, context, ttl=ttl)


class RerankerCache(BaseCacheLayer):
    """L6: Caches reranker scores for (query, doc) pairs."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.RERANKER, event_bus)


class AuthDecisionCache(BaseCacheLayer):
    """
    L7: Caches authorization decisions.
    SHORT TTL. Invalidates IMMEDIATELY on permission change.
    """
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.AUTH_DECISION, event_bus)

    async def _handle_invalidation(self, event: InvalidationEvent):
        """Override: auth decisions get aggressive invalidation."""
        if event.reason in (
            InvalidationReason.PERMISSION_CHANGE,
            InvalidationReason.POLICY_CHANGE,
            InvalidationReason.SECURITY_INCIDENT,
        ):
            # Nuclear: clear ALL auth decisions for this tenant
            keys_to_remove = [
                k for k, v in self._store.items()
                if v["tenant_id"] == event.tenant_id or event.tenant_id == "*"
            ]
            for key in keys_to_remove:
                del self._store[key]
            self._metrics.invalidations += len(keys_to_remove)
            logger.warning(
                f"Auth cache nuclear invalidation: {len(keys_to_remove)} entries "
                f"(reason={event.reason.value})"
            )
        else:
            await super()._handle_invalidation(event)


class DocumentParseCache(BaseCacheLayer):
    """L8: Caches parsed document content (long-lived, deterministic)."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.DOCUMENT_PARSE, event_bus)


class EvalQualityCache(BaseCacheLayer):
    """L9: Caches evaluation/quality scores."""
    def __init__(self, event_bus: InvalidationEventBus):
        super().__init__(CacheLayer.EVAL_QUALITY, event_bus)


# =============================================================================
# Cache Metrics Aggregator
# =============================================================================

class CacheMetricsAggregator:
    """Aggregates metrics across all cache layers for monitoring."""

    def __init__(self, layers: List[BaseCacheLayer]):
        self.layers = layers

    def get_summary(self) -> Dict[str, Any]:
        total_hits = sum(l.metrics.hits for l in self.layers)
        total_misses = sum(l.metrics.misses for l in self.layers)
        total_requests = total_hits + total_misses

        return {
            "overall_hit_rate": f"{total_hits / total_requests:.2%}" if total_requests > 0 else "N/A",
            "total_hits": total_hits,
            "total_misses": total_misses,
            "total_security_blocks": sum(l.metrics.security_blocks for l in self.layers),
            "total_invalidations": sum(l.metrics.invalidations for l in self.layers),
            "per_layer": [l.metrics.to_dict() for l in self.layers],
        }

    def get_alerts(self) -> List[Dict[str, str]]:
        """Generate alerts for anomalous conditions."""
        alerts = []
        for layer in self.layers:
            if layer.metrics.security_blocks > 0:
                alerts.append({
                    "severity": "CRITICAL",
                    "layer": layer.layer.value,
                    "message": f"{layer.metrics.security_blocks} cross-tenant access attempts blocked",
                })
            if layer.metrics.hit_rate < 0.3 and (layer.metrics.hits + layer.metrics.misses) > 100:
                alerts.append({
                    "severity": "WARNING",
                    "layer": layer.layer.value,
                    "message": f"Low hit rate: {layer.metrics.hit_rate:.2%}",
                })
        return alerts


# =============================================================================
# Cache Orchestrator
# =============================================================================

class MultiLayerCacheOrchestrator:
    """
    Orchestrates all cache layers, providing unified interface for
    the AI pipeline to cache/retrieve at each stage.
    """

    def __init__(self):
        self.event_bus = InvalidationEventBus()

        # Initialize all layers
        self.prompt_prefix = PromptPrefixCache(self.event_bus)
        self.semantic_response = SemanticResponseCacheLayer(self.event_bus)
        self.retrieval_result = RetrievalResultCache(self.event_bus)
        self.embedding = EmbeddingCache(self.event_bus)
        self.tool_result = ToolResultCache(self.event_bus)
        self.reranker = RerankerCache(self.event_bus)
        self.auth_decision = AuthDecisionCache(self.event_bus)
        self.document_parse = DocumentParseCache(self.event_bus)
        self.eval_quality = EvalQualityCache(self.event_bus)

        self._all_layers: List[BaseCacheLayer] = [
            self.prompt_prefix,
            self.semantic_response,
            self.retrieval_result,
            self.embedding,
            self.tool_result,
            self.reranker,
            self.auth_decision,
            self.document_parse,
            self.eval_quality,
        ]

        self.metrics_aggregator = CacheMetricsAggregator(self._all_layers)

    def build_key(self, layer: CacheLayer, context: CacheKeyContext, content_hash: str = "") -> str:
        """Build a secure cache key."""
        return CacheKeyBuilder.build(layer, context, content_hash)

    async def get_from_layer(
        self, layer: CacheLayer, key: str, context: CacheKeyContext
    ) -> Optional[Any]:
        """Get from a specific cache layer."""
        cache = self._get_layer_instance(layer)
        return await cache.get(key, context)

    async def put_to_layer(
        self, layer: CacheLayer, key: str, value: Any, context: CacheKeyContext
    ):
        """Put to a specific cache layer."""
        cache = self._get_layer_instance(layer)
        await cache.put(key, value, context)

    async def invalidate_tenant(self, tenant_id: str, reason: InvalidationReason):
        """Invalidate all caches for a tenant."""
        await self.event_bus.publish(InvalidationEvent(
            reason=reason,
            tenant_id=tenant_id,
            affected_layers=[l.layer for l in self._all_layers],
            propagate_cross_region=True,
        ))

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics_aggregator.get_summary()

    def get_alerts(self) -> List[Dict]:
        return self.metrics_aggregator.get_alerts()

    def _get_layer_instance(self, layer: CacheLayer) -> BaseCacheLayer:
        mapping = {
            CacheLayer.PROMPT_PREFIX: self.prompt_prefix,
            CacheLayer.SEMANTIC_RESPONSE: self.semantic_response,
            CacheLayer.RETRIEVAL_RESULT: self.retrieval_result,
            CacheLayer.EMBEDDING: self.embedding,
            CacheLayer.TOOL_RESULT: self.tool_result,
            CacheLayer.RERANKER: self.reranker,
            CacheLayer.AUTH_DECISION: self.auth_decision,
            CacheLayer.DOCUMENT_PARSE: self.document_parse,
            CacheLayer.EVAL_QUALITY: self.eval_quality,
        }
        return mapping[layer]


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    """Demonstrate multi-layer cache orchestration."""

    orchestrator = MultiLayerCacheOrchestrator()

    # Build context
    context = CacheKeyContext(
        tenant_id="acme_corp",
        user_id="user_123",
        permission_fingerprint="fp_abc123def456",
        model_version="gpt-4-0125",
        prompt_version="v2.3",
        index_version="idx_20240115",
        source_freshness_watermark=time.time() - 3600,
        safety_policy_version="safety_v4",
        risk_tier=RiskTier.MEDIUM,
        tool_name="sql_query",
        tool_parameters={"query": "SELECT SUM(revenue) FROM sales WHERE quarter='Q3'"},
    )

    # --- Simulate a full RAG pipeline with caching ---

    # 1. Check auth decision cache
    auth_key = orchestrator.build_key(
        CacheLayer.AUTH_DECISION, context, content_hash="dataset_sales"
    )
    auth_result = await orchestrator.get_from_layer(CacheLayer.AUTH_DECISION, auth_key, context)
    if auth_result is None:
        auth_result = {"allowed": True, "scopes": ["read"]}
        await orchestrator.put_to_layer(CacheLayer.AUTH_DECISION, auth_key, auth_result, context)
        print("Auth decision: MISS → computed and cached")
    else:
        print("Auth decision: HIT")

    # 2. Check retrieval cache
    retrieval_key = orchestrator.build_key(
        CacheLayer.RETRIEVAL_RESULT, context, content_hash="query_revenue_q3"
    )
    chunks = await orchestrator.get_from_layer(CacheLayer.RETRIEVAL_RESULT, retrieval_key, context)
    if chunks is None:
        chunks = [{"text": "Q3 revenue was $4.2M", "score": 0.95}]
        await orchestrator.put_to_layer(CacheLayer.RETRIEVAL_RESULT, retrieval_key, chunks, context)
        print("Retrieval: MISS → computed and cached")
    else:
        print("Retrieval: HIT")

    # 3. Check tool result cache
    tool_key = orchestrator.build_key(CacheLayer.TOOL_RESULT, context, content_hash="")
    tool_result = await orchestrator.get_from_layer(CacheLayer.TOOL_RESULT, tool_key, context)
    if tool_result is None:
        tool_result = {"result": 4200000, "currency": "USD"}
        await orchestrator.tool_result.put_tool_result(tool_key, tool_result, "sql_query", context)
        print("Tool result: MISS → computed and cached")
    else:
        print("Tool result: HIT")

    # 4. Check semantic response cache
    response_key = orchestrator.build_key(
        CacheLayer.SEMANTIC_RESPONSE, context, content_hash="revenue_q3_semantic"
    )
    response = await orchestrator.get_from_layer(CacheLayer.SEMANTIC_RESPONSE, response_key, context)
    if response is None:
        response = "Based on our data, Q3 revenue was $4.2M, representing 15% growth."
        await orchestrator.put_to_layer(CacheLayer.SEMANTIC_RESPONSE, response_key, response, context)
        print("Semantic response: MISS → computed and cached")
    else:
        print("Semantic response: HIT")

    # --- Simulate invalidation ---
    print("\n--- Simulating document change invalidation ---")
    await orchestrator.event_bus.publish_document_change("acme_corp", "doc_sales_2024")

    # Verify invalidation worked
    chunks_after = await orchestrator.get_from_layer(CacheLayer.RETRIEVAL_RESULT, retrieval_key, context)
    print(f"Retrieval after invalidation: {'HIT' if chunks_after else 'MISS (correctly invalidated)'}")

    # --- Print metrics ---
    print(f"\nMetrics: {json.dumps(orchestrator.get_metrics(), indent=2)}")
    alerts = orchestrator.get_alerts()
    if alerts:
        print(f"Alerts: {json.dumps(alerts, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
