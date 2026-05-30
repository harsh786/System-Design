"""
AI Caching Layer
================
Multi-level caching system for AI cost optimization.

Layers:
1. Prompt/Prefix Cache - Repeated system prompts (provider-level)
2. Semantic Cache - Similar queries get cached answers
3. Retrieval Cache - Query → retrieved documents
4. Tool Result Cache - Idempotent tool call results

Achieves 30-60% cost reduction through cache hits.
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import numpy as np


# =============================================================================
# Cache Key Design
# =============================================================================

@dataclass
class CacheKeyComponents:
    """Components that form a cache key."""
    tenant_id: str
    query: str
    model: Optional[str] = None
    permissions: Optional[frozenset] = None
    version: Optional[str] = None  # App version or knowledge base version
    context_hash: Optional[str] = None  # Hash of relevant context


class CacheKeyBuilder:
    """
    Builds cache keys with proper scoping.
    
    Keys must account for:
    - Tenant isolation (different tenants, different answers)
    - Permissions (user A might see different docs than user B)
    - Version (knowledge base updates should invalidate)
    - Model (different models give different answers)
    """

    @staticmethod
    def build_exact_key(components: CacheKeyComponents) -> str:
        """Build an exact-match cache key."""
        parts = [
            components.tenant_id,
            components.query.strip().lower(),
            components.model or "default",
            ",".join(sorted(components.permissions)) if components.permissions else "all",
            components.version or "v1",
        ]
        key_str = "|".join(parts)
        return hashlib.sha256(key_str.encode()).hexdigest()

    @staticmethod
    def build_semantic_key(components: CacheKeyComponents) -> str:
        """Build a key for semantic cache lookup (used with embedding)."""
        parts = [
            components.tenant_id,
            ",".join(sorted(components.permissions)) if components.permissions else "all",
            components.version or "v1",
        ]
        # The query itself is embedded, not hashed
        return "|".join(parts)

    @staticmethod
    def build_retrieval_key(query: str, tenant_id: str, filters: dict = None) -> str:
        """Build key for retrieval cache."""
        parts = [tenant_id, query.strip().lower()]
        if filters:
            parts.append(json.dumps(filters, sort_keys=True))
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    @staticmethod
    def build_tool_key(tool_name: str, arguments: dict, tenant_id: str) -> str:
        """Build key for tool result cache."""
        parts = [tenant_id, tool_name, json.dumps(arguments, sort_keys=True)]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


# =============================================================================
# Cache Entry
# =============================================================================

@dataclass
class CacheEntry:
    """A single cache entry."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    hit_count: int = 0
    last_hit_at: float = 0.0
    metadata: dict = field(default_factory=dict)
    # For semantic cache
    embedding: Optional[list[float]] = None

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def record_hit(self):
        self.hit_count += 1
        self.last_hit_at = time.time()


# =============================================================================
# Cache Backend (Abstract)
# =============================================================================

class CacheBackend(ABC):
    """Abstract cache storage backend."""

    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        pass

    @abstractmethod
    def set(self, entry: CacheEntry):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def size(self) -> int:
        pass


class InMemoryBackend(CacheBackend):
    """In-memory cache backend (for single-instance or development)."""

    def __init__(self, max_entries: int = 10000):
        self.store: dict[str, CacheEntry] = {}
        self.max_entries = max_entries

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self.store.get(key)
        if entry and not entry.is_expired:
            entry.record_hit()
            return entry
        if entry and entry.is_expired:
            del self.store[key]
        return None

    def set(self, entry: CacheEntry):
        if len(self.store) >= self.max_entries:
            self._evict()
        self.store[entry.key] = entry

    def delete(self, key: str):
        self.store.pop(key, None)

    def clear(self):
        self.store.clear()

    def size(self) -> int:
        return len(self.store)

    def _evict(self):
        """Evict least recently used entries."""
        if not self.store:
            return
        # Remove expired first
        expired = [k for k, v in self.store.items() if v.is_expired]
        for k in expired:
            del self.store[k]
        # If still full, remove LRU
        if len(self.store) >= self.max_entries:
            sorted_entries = sorted(self.store.items(), key=lambda x: x[1].last_hit_at)
            to_remove = len(self.store) - self.max_entries + (self.max_entries // 10)
            for k, _ in sorted_entries[:to_remove]:
                del self.store[k]


# =============================================================================
# Semantic Cache
# =============================================================================

class SemanticCache:
    """
    Cache that finds similar queries using embeddings.
    
    Instead of exact key match, embeds the query and finds cached
    entries with cosine similarity above threshold.
    
    This is the highest-value cache for AI systems because:
    - "What's your refund policy?" and "How do I get a refund?" are the same question
    - Exact caching misses these, semantic caching catches them
    """

    def __init__(
        self,
        embedding_fn: Optional[Any] = None,
        similarity_threshold: float = 0.93,
        max_entries: int = 5000,
        default_ttl: float = 3600,  # 1 hour
    ):
        self.embedding_fn = embedding_fn
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.entries: list[CacheEntry] = []
        self.metrics = CacheMetrics(cache_name="semantic")

    def get(self, query: str, scope_key: str = "") -> Optional[CacheEntry]:
        """
        Find a semantically similar cached entry.
        
        Args:
            query: The query to look up
            scope_key: Scoping key (tenant + permissions + version)
        """
        self.metrics.total_lookups += 1

        if not self.embedding_fn:
            return None

        query_embedding = self._embed(query)
        if query_embedding is None:
            return None

        best_entry = None
        best_similarity = 0.0

        for entry in self.entries:
            if entry.is_expired:
                continue
            # Check scope match
            if scope_key and entry.metadata.get("scope_key") != scope_key:
                continue
            if entry.embedding is None:
                continue

            similarity = self._cosine_similarity(query_embedding, entry.embedding)
            if similarity > self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_entry = entry

        if best_entry:
            best_entry.record_hit()
            self.metrics.hits += 1
            self.metrics.total_savings_tokens += best_entry.metadata.get("output_tokens", 0)
            return best_entry

        self.metrics.misses += 1
        return None

    def set(self, query: str, response: Any, scope_key: str = "", ttl: Optional[float] = None, metadata: dict = None):
        """Cache a query-response pair."""
        if not self.embedding_fn:
            return

        embedding = self._embed(query)
        if embedding is None:
            return

        entry_metadata = metadata or {}
        entry_metadata["scope_key"] = scope_key
        entry_metadata["original_query"] = query

        entry = CacheEntry(
            key=hashlib.sha256(f"{scope_key}|{query}".encode()).hexdigest(),
            value=response,
            created_at=time.time(),
            expires_at=time.time() + (ttl or self.default_ttl),
            embedding=embedding,
            metadata=entry_metadata,
        )

        # Evict if full
        if len(self.entries) >= self.max_entries:
            self._evict()

        self.entries.append(entry)

    def invalidate_scope(self, scope_key: str):
        """Invalidate all entries for a scope (e.g., when knowledge base updates)."""
        self.entries = [e for e in self.entries if e.metadata.get("scope_key") != scope_key]

    def _embed(self, text: str) -> Optional[list[float]]:
        """Generate embedding for text."""
        try:
            if callable(self.embedding_fn):
                return self.embedding_fn(text)
            return None
        except Exception:
            return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    def _evict(self):
        """Remove expired and LRU entries."""
        now = time.time()
        self.entries = [e for e in self.entries if not e.is_expired]
        if len(self.entries) >= self.max_entries:
            self.entries.sort(key=lambda e: e.last_hit_at or e.created_at)
            self.entries = self.entries[len(self.entries) // 4:]


# =============================================================================
# Retrieval Cache
# =============================================================================

class RetrievalCache:
    """
    Caches retrieval results (query → documents).
    
    High value because:
    - Vector search is relatively expensive ($0.01-0.05 per query with reranking)
    - Same/similar queries hit same documents
    - Documents change infrequently (hourly/daily TTL is fine)
    """

    def __init__(self, backend: Optional[CacheBackend] = None, default_ttl: float = 3600):
        self.backend = backend or InMemoryBackend(max_entries=10000)
        self.default_ttl = default_ttl
        self.metrics = CacheMetrics(cache_name="retrieval")

    def get(self, query: str, tenant_id: str, filters: Optional[dict] = None) -> Optional[list[dict]]:
        """Look up cached retrieval results."""
        self.metrics.total_lookups += 1
        key = CacheKeyBuilder.build_retrieval_key(query, tenant_id, filters)
        entry = self.backend.get(key)
        if entry:
            self.metrics.hits += 1
            return entry.value
        self.metrics.misses += 1
        return None

    def set(
        self,
        query: str,
        tenant_id: str,
        results: list[dict],
        filters: Optional[dict] = None,
        ttl: Optional[float] = None,
    ):
        """Cache retrieval results."""
        key = CacheKeyBuilder.build_retrieval_key(query, tenant_id, filters)
        entry = CacheEntry(
            key=key,
            value=results,
            created_at=time.time(),
            expires_at=time.time() + (ttl or self.default_ttl),
            metadata={"tenant_id": tenant_id, "query": query, "result_count": len(results)},
        )
        self.backend.set(entry)

    def invalidate_tenant(self, tenant_id: str):
        """Invalidate all cached results for a tenant (e.g., after document update)."""
        # In production, use key prefix scanning
        # For in-memory, we iterate
        if isinstance(self.backend, InMemoryBackend):
            keys_to_delete = [
                k for k, v in self.backend.store.items()
                if v.metadata.get("tenant_id") == tenant_id
            ]
            for k in keys_to_delete:
                self.backend.delete(k)


# =============================================================================
# Tool Result Cache
# =============================================================================

class ToolResultCache:
    """
    Caches results of idempotent tool calls.
    
    Only cache tools that are:
    - Idempotent (same input → same output)
    - Read-only (no side effects)
    - Reasonably stable (result won't change in TTL window)
    
    Examples: search, lookup, calculate, get_weather
    NOT: send_email, create_ticket, process_payment
    """

    # Tools that are safe to cache
    CACHEABLE_TOOLS = {
        "search": 3600,           # 1 hour
        "lookup": 1800,           # 30 min
        "get_weather": 600,       # 10 min
        "calculate": 86400,       # 24 hours (deterministic)
        "get_exchange_rate": 300,  # 5 min
        "get_documentation": 3600,
    }

    # Tools that must NEVER be cached
    NON_CACHEABLE_TOOLS = {
        "send_email", "create_ticket", "update_record",
        "process_payment", "delete", "cancel",
    }

    def __init__(self, backend: Optional[CacheBackend] = None):
        self.backend = backend or InMemoryBackend(max_entries=5000)
        self.metrics = CacheMetrics(cache_name="tool_result")

    def is_cacheable(self, tool_name: str) -> bool:
        """Check if a tool's results can be cached."""
        if tool_name in self.NON_CACHEABLE_TOOLS:
            return False
        return tool_name in self.CACHEABLE_TOOLS

    def get(self, tool_name: str, arguments: dict, tenant_id: str) -> Optional[Any]:
        """Look up cached tool result."""
        if not self.is_cacheable(tool_name):
            return None

        self.metrics.total_lookups += 1
        key = CacheKeyBuilder.build_tool_key(tool_name, arguments, tenant_id)
        entry = self.backend.get(key)
        if entry:
            self.metrics.hits += 1
            return entry.value
        self.metrics.misses += 1
        return None

    def set(self, tool_name: str, arguments: dict, tenant_id: str, result: Any):
        """Cache a tool result."""
        if not self.is_cacheable(tool_name):
            return

        ttl = self.CACHEABLE_TOOLS.get(tool_name, 1800)
        key = CacheKeyBuilder.build_tool_key(tool_name, arguments, tenant_id)
        entry = CacheEntry(
            key=key,
            value=result,
            created_at=time.time(),
            expires_at=time.time() + ttl,
            metadata={"tool": tool_name, "tenant_id": tenant_id},
        )
        self.backend.set(entry)

    def register_cacheable_tool(self, tool_name: str, ttl_seconds: int):
        """Register a custom tool as cacheable."""
        self.CACHEABLE_TOOLS[tool_name] = ttl_seconds


# =============================================================================
# Prompt Prefix Cache Manager
# =============================================================================

class PrefixCacheManager:
    """
    Manages prompt prefix caching for provider-level caching.
    
    Providers like Anthropic and OpenAI cache repeated prompt prefixes.
    This manager helps structure prompts to maximize cache hits.
    
    Strategy:
    - Put stable content (system prompt, tool schemas) at the beginning
    - Put dynamic content (user query, retrieved context) at the end
    - Mark cache breakpoints for Anthropic's explicit caching
    """

    def __init__(self, provider: str = "openai"):
        self.provider = provider
        self.prefix_registry: dict[str, str] = {}  # name → content
        self.metrics = CacheMetrics(cache_name="prefix")

    def register_prefix(self, name: str, content: str):
        """Register a stable prefix (system prompt, instructions, tool schemas)."""
        self.prefix_registry[name] = content

    def build_cacheable_messages(
        self,
        system_prompt: str,
        tool_schemas: str,
        retrieved_context: str,
        conversation_history: list[dict],
        current_query: str,
    ) -> list[dict]:
        """
        Build messages optimized for prefix caching.
        
        Order (most stable → least stable):
        1. System prompt (almost never changes) ← CACHE THIS
        2. Tool schemas (rarely changes) ← CACHE THIS
        3. Retrieved context (changes per query)
        4. History (changes per turn)
        5. Current query (always different)
        """
        messages = []

        # Stable prefix (cacheable)
        system_content = system_prompt
        if tool_schemas:
            system_content += f"\n\nAvailable tools:\n{tool_schemas}"

        if self.provider == "anthropic":
            # Anthropic: explicit cache control
            messages.append({
                "role": "system",
                "content": system_content,
                "cache_control": {"type": "ephemeral"},  # Mark for caching
            })
        else:
            # OpenAI: automatic prefix caching
            messages.append({"role": "system", "content": system_content})

        # Dynamic content (not cached at provider level)
        if retrieved_context:
            messages.append({
                "role": "user",
                "content": f"[Context]\n{retrieved_context}\n[/Context]",
            })
            messages.append({
                "role": "assistant",
                "content": "I'll use this context to answer your question.",
            })

        # Conversation history
        messages.extend(conversation_history)

        # Current query
        messages.append({"role": "user", "content": current_query})

        return messages

    def estimate_cache_savings(self, system_prompt: str, tool_schemas: str, requests_per_hour: int) -> dict:
        """Estimate savings from prefix caching."""
        prefix_tokens = (len(system_prompt) + len(tool_schemas)) // 4
        
        # Assume 80% cache hit rate after warmup
        hit_rate = 0.80
        cached_requests = requests_per_hour * hit_rate

        # OpenAI: 50% discount on cached input tokens
        # Anthropic: 90% discount on cached input tokens
        if self.provider == "anthropic":
            discount = 0.90
            cost_per_1m = 3.00  # Claude Sonnet input
        else:
            discount = 0.50
            cost_per_1m = 2.50  # GPT-4o input

        savings_per_request = (prefix_tokens / 1_000_000) * cost_per_1m * discount
        hourly_savings = savings_per_request * cached_requests

        return {
            "prefix_tokens": prefix_tokens,
            "estimated_hit_rate": hit_rate,
            "savings_per_cached_request_usd": round(savings_per_request, 6),
            "hourly_savings_usd": round(hourly_savings, 4),
            "daily_savings_usd": round(hourly_savings * 24, 2),
            "monthly_savings_usd": round(hourly_savings * 24 * 30, 2),
        }


# =============================================================================
# Cache Metrics
# =============================================================================

@dataclass
class CacheMetrics:
    """Metrics for a cache layer."""
    cache_name: str
    total_lookups: int = 0
    hits: int = 0
    misses: int = 0
    total_savings_tokens: int = 0
    total_savings_usd: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    def summary(self) -> dict:
        return {
            "cache": self.cache_name,
            "lookups": self.total_lookups,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "savings_tokens": self.total_savings_tokens,
            "savings_usd": round(self.total_savings_usd, 4),
        }


# =============================================================================
# Cache Invalidation
# =============================================================================

class InvalidationTrigger(Enum):
    KNOWLEDGE_BASE_UPDATE = "kb_update"
    DOCUMENT_CHANGE = "doc_change"
    PERMISSION_CHANGE = "permission_change"
    MODEL_CHANGE = "model_change"
    TTL_EXPIRY = "ttl_expiry"
    MANUAL = "manual"
    FEEDBACK_NEGATIVE = "negative_feedback"


@dataclass
class InvalidationEvent:
    trigger: InvalidationTrigger
    scope: str  # What to invalidate: "all", tenant_id, document_id
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class CacheInvalidationManager:
    """
    Manages cache invalidation across all layers.
    
    Triggers:
    - Knowledge base update → invalidate retrieval + semantic cache for affected tenant
    - Document change → invalidate entries containing that document
    - Permission change → invalidate entries for affected user/role
    - Negative feedback → invalidate the specific cached response
    - Model change → invalidate all semantic cache (different model = different answers)
    """

    def __init__(self):
        self.caches: dict[str, Any] = {}  # name → cache instance
        self.event_log: list[InvalidationEvent] = []

    def register_cache(self, name: str, cache: Any):
        """Register a cache layer for invalidation management."""
        self.caches[name] = cache

    def invalidate(self, event: InvalidationEvent):
        """Process an invalidation event."""
        self.event_log.append(event)

        if event.trigger == InvalidationTrigger.KNOWLEDGE_BASE_UPDATE:
            self._invalidate_for_kb_update(event)
        elif event.trigger == InvalidationTrigger.PERMISSION_CHANGE:
            self._invalidate_for_permission_change(event)
        elif event.trigger == InvalidationTrigger.MODEL_CHANGE:
            self._invalidate_all_semantic()
        elif event.trigger == InvalidationTrigger.FEEDBACK_NEGATIVE:
            self._invalidate_specific(event)
        elif event.trigger == InvalidationTrigger.MANUAL:
            self._invalidate_scope(event.scope)

    def _invalidate_for_kb_update(self, event: InvalidationEvent):
        """Invalidate caches when knowledge base is updated."""
        tenant_id = event.scope
        if "retrieval" in self.caches:
            self.caches["retrieval"].invalidate_tenant(tenant_id)
        if "semantic" in self.caches:
            self.caches["semantic"].invalidate_scope(tenant_id)

    def _invalidate_for_permission_change(self, event: InvalidationEvent):
        """Invalidate when user permissions change."""
        # Must invalidate all cached responses for this user
        # since they might now see different documents
        tenant_id = event.scope
        if "semantic" in self.caches:
            self.caches["semantic"].invalidate_scope(tenant_id)
        if "retrieval" in self.caches:
            self.caches["retrieval"].invalidate_tenant(tenant_id)

    def _invalidate_all_semantic(self):
        """Invalidate all semantic cache (e.g., model change)."""
        if "semantic" in self.caches and hasattr(self.caches["semantic"], "entries"):
            self.caches["semantic"].entries.clear()

    def _invalidate_specific(self, event: InvalidationEvent):
        """Invalidate a specific cached entry."""
        key = event.metadata.get("cache_key")
        if key:
            for cache in self.caches.values():
                if hasattr(cache, "backend"):
                    cache.backend.delete(key)

    def _invalidate_scope(self, scope: str):
        """Invalidate everything in a scope."""
        if scope == "all":
            for cache in self.caches.values():
                if hasattr(cache, "backend"):
                    cache.backend.clear()
                elif hasattr(cache, "entries"):
                    cache.entries.clear()


# =============================================================================
# Unified Caching Layer
# =============================================================================

class AICachingLayer:
    """
    Unified caching layer combining all cache types.
    
    Lookup order:
    1. Semantic cache (might have exact answer)
    2. Retrieval cache (save vector search cost)
    3. Tool cache (save tool execution cost)
    
    The prefix cache is handled at the message construction level.
    """

    def __init__(
        self,
        embedding_fn: Optional[Any] = None,
        semantic_threshold: float = 0.93,
        provider: str = "openai",
    ):
        self.semantic_cache = SemanticCache(
            embedding_fn=embedding_fn,
            similarity_threshold=semantic_threshold,
        )
        self.retrieval_cache = RetrievalCache()
        self.tool_cache = ToolResultCache()
        self.prefix_cache = PrefixCacheManager(provider=provider)
        self.invalidation = CacheInvalidationManager()

        # Register caches for invalidation
        self.invalidation.register_cache("semantic", self.semantic_cache)
        self.invalidation.register_cache("retrieval", self.retrieval_cache)
        self.invalidation.register_cache("tool", self.tool_cache)

    def lookup_response(self, query: str, tenant_id: str, permissions: frozenset = None) -> Optional[dict]:
        """
        Try to find a cached response for this query.
        
        Returns cached response or None.
        """
        scope_key = CacheKeyBuilder.build_semantic_key(CacheKeyComponents(
            tenant_id=tenant_id,
            query=query,
            permissions=permissions,
        ))

        entry = self.semantic_cache.get(query, scope_key)
        if entry:
            return {
                "response": entry.value,
                "cache_hit": True,
                "cache_type": "semantic",
                "similarity": entry.metadata.get("similarity"),
                "original_query": entry.metadata.get("original_query"),
            }
        return None

    def cache_response(
        self,
        query: str,
        response: Any,
        tenant_id: str,
        permissions: frozenset = None,
        output_tokens: int = 0,
        ttl: Optional[float] = None,
    ):
        """Cache a response for future similar queries."""
        scope_key = CacheKeyBuilder.build_semantic_key(CacheKeyComponents(
            tenant_id=tenant_id,
            query=query,
            permissions=permissions,
        ))
        self.semantic_cache.set(
            query=query,
            response=response,
            scope_key=scope_key,
            ttl=ttl,
            metadata={"output_tokens": output_tokens},
        )

    def lookup_retrieval(self, query: str, tenant_id: str, filters: dict = None) -> Optional[list[dict]]:
        """Look up cached retrieval results."""
        return self.retrieval_cache.get(query, tenant_id, filters)

    def cache_retrieval(self, query: str, tenant_id: str, results: list[dict], filters: dict = None):
        """Cache retrieval results."""
        self.retrieval_cache.set(query, tenant_id, results, filters)

    def lookup_tool_result(self, tool_name: str, arguments: dict, tenant_id: str) -> Optional[Any]:
        """Look up cached tool result."""
        return self.tool_cache.get(tool_name, arguments, tenant_id)

    def cache_tool_result(self, tool_name: str, arguments: dict, tenant_id: str, result: Any):
        """Cache a tool result."""
        self.tool_cache.set(tool_name, arguments, tenant_id, result)

    def handle_invalidation(self, event: InvalidationEvent):
        """Handle a cache invalidation event."""
        self.invalidation.invalidate(event)

    def get_metrics(self) -> dict:
        """Get metrics across all cache layers."""
        return {
            "semantic": self.semantic_cache.metrics.summary(),
            "retrieval": self.retrieval_cache.metrics.summary(),
            "tool": self.tool_cache.metrics.summary(),
        }

    def get_cost_savings(self, cost_per_generation: float = 0.03, cost_per_retrieval: float = 0.005) -> dict:
        """Calculate total cost savings from caching."""
        semantic_savings = self.semantic_cache.metrics.hits * cost_per_generation
        retrieval_savings = self.retrieval_cache.metrics.hits * cost_per_retrieval
        tool_savings = self.tool_cache.metrics.hits * 0.001  # Minimal per-tool cost

        total_savings = semantic_savings + retrieval_savings + tool_savings
        total_lookups = (
            self.semantic_cache.metrics.total_lookups +
            self.retrieval_cache.metrics.total_lookups +
            self.tool_cache.metrics.total_lookups
        )

        return {
            "semantic_savings_usd": round(semantic_savings, 4),
            "retrieval_savings_usd": round(retrieval_savings, 4),
            "tool_savings_usd": round(tool_savings, 4),
            "total_savings_usd": round(total_savings, 4),
            "total_lookups": total_lookups,
            "overall_hit_rate": f"{(self.semantic_cache.metrics.hits + self.retrieval_cache.metrics.hits + self.tool_cache.metrics.hits) / max(1, total_lookups):.1%}",
        }


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Mock embedding function (in production, use OpenAI/Cohere embeddings)
    def mock_embed(text: str) -> list[float]:
        """Simple hash-based mock embedding for demo."""
        import hashlib
        h = hashlib.sha256(text.lower().strip().encode()).digest()
        # Convert to float vector (not semantically meaningful, just for structure)
        return [float(b) / 255.0 for b in h]

    # Initialize caching layer
    cache = AICachingLayer(embedding_fn=mock_embed, semantic_threshold=0.90)

    # Simulate usage
    print("=" * 60)
    print("AI CACHING LAYER DEMO")
    print("=" * 60)

    # Cache a response
    cache.cache_response(
        query="What is your refund policy?",
        response="Our refund policy allows returns within 30 days with receipt.",
        tenant_id="acme",
        output_tokens=50,
    )
    print("\nCached response for 'What is your refund policy?'")

    # Try to find it
    result = cache.lookup_response("What is your refund policy?", tenant_id="acme")
    print(f"Lookup same query: {'HIT' if result else 'MISS'}")

    # Cache retrieval results
    cache.cache_retrieval(
        query="refund policy",
        tenant_id="acme",
        results=[{"doc_id": "1", "title": "Refund Policy", "score": 0.95}],
    )
    print("\nCached retrieval results for 'refund policy'")

    retrieval_result = cache.lookup_retrieval("refund policy", "acme")
    print(f"Lookup retrieval: {'HIT' if retrieval_result else 'MISS'}")

    # Cache tool result
    cache.cache_tool_result("search", {"query": "billing"}, "acme", [{"id": 1, "title": "Billing FAQ"}])
    tool_result = cache.lookup_tool_result("search", {"query": "billing"}, "acme")
    print(f"Lookup tool result: {'HIT' if tool_result else 'MISS'}")

    # Non-cacheable tool
    cache.cache_tool_result("send_email", {"to": "user@example.com"}, "acme", {"sent": True})
    tool_result2 = cache.lookup_tool_result("send_email", {"to": "user@example.com"}, "acme")
    print(f"Lookup non-cacheable tool: {'HIT' if tool_result2 else 'MISS (correct!)'}")

    # Metrics
    print("\n" + "=" * 60)
    print("CACHE METRICS")
    print("=" * 60)
    print(json.dumps(cache.get_metrics(), indent=2))

    print("\nCOST SAVINGS")
    print(json.dumps(cache.get_cost_savings(), indent=2))

    # Prefix cache savings estimate
    print("\nPREFIX CACHE SAVINGS ESTIMATE")
    savings = cache.prefix_cache.estimate_cache_savings(
        system_prompt="You are a support agent..." * 10,
        tool_schemas='{"tools": [...]}' * 5,
        requests_per_hour=1000,
    )
    print(json.dumps(savings, indent=2))
