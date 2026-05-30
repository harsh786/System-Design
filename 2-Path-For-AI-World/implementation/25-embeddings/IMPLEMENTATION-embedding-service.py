"""
Embedding Service - Production-grade multi-provider embedding client.

Features:
- Multi-provider support (OpenAI, Cohere, HuggingFace local, sentence-transformers)
- Batch embedding with rate limiting
- Embedding caching (Redis + in-memory LRU)
- Dimension handling and Matryoshka truncation
- L2 normalization
- Async embedding generation
- Cost tracking per call
- Provider fallback
- Model selection by use case
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration & Types
# =============================================================================

class EmbeddingUseCase(Enum):
    SEARCH_DOCUMENT = "search_document"
    SEARCH_QUERY = "search_query"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"
    CODE_SEARCH = "code_search"


class EmbeddingProvider(Enum):
    OPENAI = "openai"
    COHERE = "cohere"
    HUGGINGFACE_LOCAL = "huggingface_local"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    VOYAGE = "voyage"


@dataclass
class EmbeddingConfig:
    provider: EmbeddingProvider
    model_name: str
    dimensions: int
    max_tokens: int
    normalize: bool = True
    truncate_dim: Optional[int] = None  # Matryoshka truncation
    batch_size: int = 100
    max_retries: int = 3
    rate_limit_rpm: int = 3000
    rate_limit_tpm: int = 1_000_000
    cost_per_million_tokens: float = 0.0
    input_type: Optional[str] = None  # For Cohere-style input types


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    model: str
    dimensions: int
    tokens_used: int
    cost_usd: float
    latency_ms: float
    cache_hits: int
    cache_misses: int


@dataclass
class CostTracker:
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_requests: int = 0
    total_cache_hits: int = 0

    def record(self, tokens: int, cost: float, cache_hits: int = 0):
        self.total_tokens += tokens
        self.total_cost_usd += cost
        self.total_requests += 1
        self.total_cache_hits += cache_hits

    def summary(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_requests": self.total_requests,
            "total_cache_hits": self.total_cache_hits,
            "avg_cost_per_request": round(self.total_cost_usd / max(self.total_requests, 1), 6),
        }


# =============================================================================
# Model Registry - Predefined configurations
# =============================================================================

MODEL_REGISTRY: dict[str, EmbeddingConfig] = {
    "openai-3-large": EmbeddingConfig(
        provider=EmbeddingProvider.OPENAI,
        model_name="text-embedding-3-large",
        dimensions=3072,
        max_tokens=8191,
        cost_per_million_tokens=0.13,
        batch_size=2048,
        rate_limit_rpm=5000,
        rate_limit_tpm=5_000_000,
    ),
    "openai-3-small": EmbeddingConfig(
        provider=EmbeddingProvider.OPENAI,
        model_name="text-embedding-3-small",
        dimensions=1536,
        max_tokens=8191,
        cost_per_million_tokens=0.02,
        batch_size=2048,
        rate_limit_rpm=5000,
        rate_limit_tpm=5_000_000,
    ),
    "cohere-english-v3": EmbeddingConfig(
        provider=EmbeddingProvider.COHERE,
        model_name="embed-english-v3.0",
        dimensions=1024,
        max_tokens=512,
        cost_per_million_tokens=0.10,
        batch_size=96,
        rate_limit_rpm=10000,
    ),
    "cohere-multilingual-v3": EmbeddingConfig(
        provider=EmbeddingProvider.COHERE,
        model_name="embed-multilingual-v3.0",
        dimensions=1024,
        max_tokens=512,
        cost_per_million_tokens=0.10,
        batch_size=96,
        rate_limit_rpm=10000,
    ),
    "voyage-large-2": EmbeddingConfig(
        provider=EmbeddingProvider.VOYAGE,
        model_name="voyage-large-2",
        dimensions=1536,
        max_tokens=16000,
        cost_per_million_tokens=0.12,
        batch_size=128,
        rate_limit_rpm=3000,
    ),
    "voyage-code-2": EmbeddingConfig(
        provider=EmbeddingProvider.VOYAGE,
        model_name="voyage-code-2",
        dimensions=1536,
        max_tokens=16000,
        cost_per_million_tokens=0.12,
        batch_size=128,
        rate_limit_rpm=3000,
    ),
    "bge-large-en": EmbeddingConfig(
        provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
        model_name="BAAI/bge-large-en-v1.5",
        dimensions=1024,
        max_tokens=512,
        cost_per_million_tokens=0.0,  # Self-hosted
        batch_size=64,
    ),
    "minilm-l6": EmbeddingConfig(
        provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
        model_name="all-MiniLM-L6-v2",
        dimensions=384,
        max_tokens=256,
        cost_per_million_tokens=0.0,
        batch_size=256,
    ),
}


# =============================================================================
# Caching Layer
# =============================================================================

class EmbeddingCache:
    """Two-layer cache: in-memory LRU + Redis."""

    def __init__(self, redis_client=None, ttl_seconds: int = 86400 * 30):
        self._memory_cache: dict[str, list[float]] = {}
        self._memory_max_size = 10_000
        self._memory_access_order: list[str] = []
        self._redis = redis_client
        self._ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _make_key(self, text: str, model: str, dimensions: int) -> str:
        content = f"{model}:{dimensions}:{text}"
        return f"emb:{hashlib.sha256(content.encode()).hexdigest()}"

    def get(self, text: str, model: str, dimensions: int) -> Optional[list[float]]:
        key = self._make_key(text, model, dimensions)

        # Check memory cache
        if key in self._memory_cache:
            self.hits += 1
            return self._memory_cache[key]

        # Check Redis
        if self._redis:
            try:
                cached = self._redis.get(key)
                if cached:
                    embedding = json.loads(cached)
                    self._put_memory(key, embedding)
                    self.hits += 1
                    return embedding
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}")

        self.misses += 1
        return None

    def put(self, text: str, model: str, dimensions: int, embedding: list[float]):
        key = self._make_key(text, model, dimensions)
        self._put_memory(key, embedding)

        if self._redis:
            try:
                self._redis.setex(key, self._ttl, json.dumps(embedding))
            except Exception as e:
                logger.warning(f"Redis cache put failed: {e}")

    def _put_memory(self, key: str, embedding: list[float]):
        if len(self._memory_cache) >= self._memory_max_size:
            # Evict oldest
            oldest = self._memory_access_order.pop(0)
            self._memory_cache.pop(oldest, None)
        self._memory_cache[key] = embedding
        self._memory_access_order.append(key)

    def reset_stats(self):
        self.hits = 0
        self.misses = 0


# =============================================================================
# Rate Limiter
# =============================================================================

class TokenBucketRateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute
        self._request_tokens = requests_per_minute
        self._token_tokens = tokens_per_minute
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, num_tokens: int = 0):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            # Refill buckets
            self._request_tokens = min(
                self._rpm, self._request_tokens + elapsed * (self._rpm / 60.0)
            )
            self._token_tokens = min(
                self._tpm, self._token_tokens + elapsed * (self._tpm / 60.0)
            )
            self._last_refill = now

            # Wait if necessary
            while self._request_tokens < 1 or self._token_tokens < num_tokens:
                wait_time = max(
                    (1 - self._request_tokens) / (self._rpm / 60.0),
                    (num_tokens - self._token_tokens) / (self._tpm / 60.0),
                )
                await asyncio.sleep(max(wait_time, 0.01))
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._request_tokens = min(
                    self._rpm, self._request_tokens + elapsed * (self._rpm / 60.0)
                )
                self._token_tokens = min(
                    self._tpm, self._token_tokens + elapsed * (self._tpm / 60.0)
                )
                self._last_refill = now

            self._request_tokens -= 1
            self._token_tokens -= num_tokens


# =============================================================================
# Provider Implementations
# =============================================================================

class BaseEmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    async def embed_batch(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        """Returns (embeddings, total_tokens_used)."""
        ...


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed_batch(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        kwargs = {"model": config.model_name, "input": texts}
        if config.truncate_dim:
            kwargs["dimensions"] = config.truncate_dim

        response = await self._client.embeddings.create(**kwargs)
        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens
        return embeddings, tokens_used


class CohereEmbeddingProvider(BaseEmbeddingProvider):
    """Cohere embedding provider."""

    def __init__(self, api_key: str):
        import cohere
        self._client = cohere.AsyncClient(api_key=api_key)

    def _get_input_type(self, use_case: EmbeddingUseCase) -> str:
        mapping = {
            EmbeddingUseCase.SEARCH_DOCUMENT: "search_document",
            EmbeddingUseCase.SEARCH_QUERY: "search_query",
            EmbeddingUseCase.CLASSIFICATION: "classification",
            EmbeddingUseCase.CLUSTERING: "clustering",
        }
        return mapping.get(use_case, "search_document")

    async def embed_batch(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        response = await self._client.embed(
            texts=texts,
            model=config.model_name,
            input_type=self._get_input_type(use_case),
            truncate="END",
        )
        # Cohere doesn't return token count directly, estimate
        estimated_tokens = sum(len(t.split()) * 1.3 for t in texts)
        return response.embeddings, int(estimated_tokens)


class VoyageEmbeddingProvider(BaseEmbeddingProvider):
    """Voyage AI embedding provider."""

    def __init__(self, api_key: str):
        import voyageai
        self._client = voyageai.AsyncClient(api_key=api_key)

    async def embed_batch(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        input_type = "document" if use_case == EmbeddingUseCase.SEARCH_DOCUMENT else "query"
        result = await self._client.embed(
            texts, model=config.model_name, input_type=input_type
        )
        return result.embeddings, result.total_tokens


class SentenceTransformersProvider(BaseEmbeddingProvider):
    """Local sentence-transformers provider."""

    def __init__(self, device: str = "cpu"):
        self._device = device
        self._models: dict = {}

    def _get_model(self, model_name: str):
        if model_name not in self._models:
            from sentence_transformers import SentenceTransformer
            self._models[model_name] = SentenceTransformer(model_name, device=self._device)
        return self._models[model_name]

    async def embed_batch(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        model = self._get_model(config.model_name)
        # Run in executor to not block event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=config.normalize).tolist()
        )
        # Estimate tokens for local models
        estimated_tokens = sum(len(t.split()) * 1.3 for t in texts)
        return embeddings, int(estimated_tokens)


# =============================================================================
# Main Embedding Service
# =============================================================================

class EmbeddingService:
    """
    Production embedding service with caching, rate limiting, fallback, and cost tracking.

    Usage:
        service = EmbeddingService(
            primary_model="openai-3-large",
            fallback_model="bge-large-en",
            openai_api_key="sk-...",
        )
        result = await service.embed(
            texts=["Hello world", "How are you?"],
            use_case=EmbeddingUseCase.SEARCH_DOCUMENT,
        )
    """

    def __init__(
        self,
        primary_model: str,
        fallback_model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        cohere_api_key: Optional[str] = None,
        voyage_api_key: Optional[str] = None,
        redis_client=None,
        local_device: str = "cpu",
    ):
        self._primary_config = MODEL_REGISTRY[primary_model]
        self._fallback_config = MODEL_REGISTRY[fallback_model] if fallback_model else None
        self._cache = EmbeddingCache(redis_client=redis_client)
        self._cost_tracker = CostTracker()

        # Initialize providers
        self._providers: dict[EmbeddingProvider, BaseEmbeddingProvider] = {}
        if openai_api_key:
            self._providers[EmbeddingProvider.OPENAI] = OpenAIEmbeddingProvider(openai_api_key)
        if cohere_api_key:
            self._providers[EmbeddingProvider.COHERE] = CohereEmbeddingProvider(cohere_api_key)
        if voyage_api_key:
            self._providers[EmbeddingProvider.VOYAGE] = VoyageEmbeddingProvider(voyage_api_key)
        self._providers[EmbeddingProvider.SENTENCE_TRANSFORMERS] = SentenceTransformersProvider(local_device)
        self._providers[EmbeddingProvider.HUGGINGFACE_LOCAL] = SentenceTransformersProvider(local_device)

        # Rate limiters per provider
        self._rate_limiters: dict[EmbeddingProvider, TokenBucketRateLimiter] = {}
        for config in [self._primary_config, self._fallback_config]:
            if config and config.provider not in self._rate_limiters:
                self._rate_limiters[config.provider] = TokenBucketRateLimiter(
                    config.rate_limit_rpm, config.rate_limit_tpm
                )

    async def embed(
        self,
        texts: list[str],
        use_case: EmbeddingUseCase = EmbeddingUseCase.SEARCH_DOCUMENT,
        config_override: Optional[EmbeddingConfig] = None,
    ) -> EmbeddingResult:
        """
        Embed texts with caching, rate limiting, and fallback.

        Args:
            texts: List of strings to embed.
            use_case: Embedding use case (affects input_type for some providers).
            config_override: Override the default model config.

        Returns:
            EmbeddingResult with embeddings, cost, and metadata.
        """
        config = config_override or self._primary_config
        start_time = time.monotonic()

        # Check cache for each text
        results: list[Optional[list[float]]] = []
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        target_dim = config.truncate_dim or config.dimensions

        for i, text in enumerate(texts):
            cached = self._cache.get(text, config.model_name, target_dim)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None)
                uncached_indices.append(i)
                uncached_texts.append(text)

        cache_hits = len(texts) - len(uncached_texts)
        cache_misses = len(uncached_texts)

        # Embed uncached texts in batches
        total_tokens = 0
        if uncached_texts:
            try:
                embeddings, tokens = await self._embed_with_retry(
                    uncached_texts, config, use_case
                )
                total_tokens = tokens
            except Exception as e:
                logger.error(f"Primary provider failed: {e}")
                if self._fallback_config:
                    logger.info(f"Falling back to {self._fallback_config.model_name}")
                    config = self._fallback_config
                    target_dim = config.truncate_dim or config.dimensions
                    embeddings, tokens = await self._embed_with_retry(
                        uncached_texts, config, use_case
                    )
                    total_tokens = tokens
                else:
                    raise

            # Apply normalization and dimension truncation
            for idx, embedding in zip(uncached_indices, embeddings):
                processed = self._post_process(embedding, config)
                results[idx] = processed
                self._cache.put(texts[idx], config.model_name, target_dim, processed)

        # Calculate cost
        cost = (total_tokens / 1_000_000) * config.cost_per_million_tokens
        latency_ms = (time.monotonic() - start_time) * 1000

        # Track costs
        self._cost_tracker.record(total_tokens, cost, cache_hits)

        return EmbeddingResult(
            embeddings=results,
            model=config.model_name,
            dimensions=target_dim,
            tokens_used=total_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

    async def _embed_with_retry(
        self, texts: list[str], config: EmbeddingConfig, use_case: EmbeddingUseCase
    ) -> tuple[list[list[float]], int]:
        """Embed with batching, rate limiting, and retries."""
        provider = self._providers.get(config.provider)
        if not provider:
            raise ValueError(f"Provider {config.provider} not initialized")

        rate_limiter = self._rate_limiters.get(config.provider)
        all_embeddings = []
        total_tokens = 0

        # Process in batches
        for i in range(0, len(texts), config.batch_size):
            batch = texts[i : i + config.batch_size]
            estimated_tokens = sum(len(t.split()) * 1.3 for t in batch)

            if rate_limiter:
                await rate_limiter.acquire(int(estimated_tokens))

            # Retry logic
            last_error = None
            for attempt in range(config.max_retries):
                try:
                    embeddings, tokens = await provider.embed_batch(batch, config, use_case)
                    all_embeddings.extend(embeddings)
                    total_tokens += tokens
                    break
                except Exception as e:
                    last_error = e
                    wait = 2**attempt
                    logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {wait}s")
                    await asyncio.sleep(wait)
            else:
                raise last_error

        return all_embeddings, total_tokens

    def _post_process(self, embedding: list[float], config: EmbeddingConfig) -> list[float]:
        """Normalize and truncate embedding."""
        vec = np.array(embedding, dtype=np.float32)

        # Matryoshka dimension truncation
        if config.truncate_dim and len(vec) > config.truncate_dim:
            vec = vec[: config.truncate_dim]

        # L2 normalization
        if config.normalize:
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

        return vec.tolist()

    @property
    def cost_summary(self) -> dict:
        return self._cost_tracker.summary()

    @property
    def cache_stats(self) -> dict:
        return {"hits": self._cache.hits, "misses": self._cache.misses}


# =============================================================================
# Use-Case Based Model Selector
# =============================================================================

class ModelSelector:
    """Select the best model based on use case constraints."""

    @staticmethod
    def recommend(
        use_case: str,
        languages: list[str] = None,
        max_cost_per_million: float = 1.0,
        max_dimensions: int = 4096,
        self_hosted_only: bool = False,
        max_latency_ms: float = 500,
    ) -> list[str]:
        """
        Recommend models based on constraints.

        Returns list of model registry keys, ordered by recommendation.
        """
        candidates = []

        for key, config in MODEL_REGISTRY.items():
            # Filter by cost
            if config.cost_per_million_tokens > max_cost_per_million:
                continue
            # Filter by self-hosted
            if self_hosted_only and config.cost_per_million_tokens > 0:
                continue
            # Filter by dimensions
            if config.dimensions > max_dimensions:
                continue

            score = 0
            # Score by use case match
            if use_case == "code" and "code" in key:
                score += 10
            elif use_case == "multilingual" and "multilingual" in key:
                score += 10
            elif use_case == "general":
                if "large" in key:
                    score += 5
                score += 3

            # Prefer larger dimensions (usually better quality)
            score += config.dimensions / 1000

            candidates.append((key, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:5]]


# =============================================================================
# Example Usage
# =============================================================================

async def main():
    """Example usage of the embedding service."""

    # Initialize service
    service = EmbeddingService(
        primary_model="openai-3-large",
        fallback_model="minilm-l6",
        openai_api_key="sk-your-key-here",
    )

    # Embed documents
    documents = [
        "Machine learning is a subset of artificial intelligence.",
        "Neural networks are inspired by biological neurons.",
        "Transformers revolutionized natural language processing.",
        "Embeddings represent text as dense vectors.",
    ]

    result = await service.embed(
        texts=documents,
        use_case=EmbeddingUseCase.SEARCH_DOCUMENT,
    )

    print(f"Model: {result.model}")
    print(f"Dimensions: {result.dimensions}")
    print(f"Tokens used: {result.tokens_used}")
    print(f"Cost: ${result.cost_usd:.6f}")
    print(f"Latency: {result.latency_ms:.1f}ms")
    print(f"Cache hits/misses: {result.cache_hits}/{result.cache_misses}")

    # Embed a query
    query_result = await service.embed(
        texts=["What is deep learning?"],
        use_case=EmbeddingUseCase.SEARCH_QUERY,
    )

    # Compute similarities
    query_vec = np.array(query_result.embeddings[0])
    for i, doc in enumerate(documents):
        doc_vec = np.array(result.embeddings[i])
        similarity = np.dot(query_vec, doc_vec)
        print(f"  Similarity to '{doc[:50]}...': {similarity:.4f}")

    # Re-embed same texts (should hit cache)
    result2 = await service.embed(texts=documents, use_case=EmbeddingUseCase.SEARCH_DOCUMENT)
    print(f"\nSecond call - Cache hits: {result2.cache_hits}, Cost: ${result2.cost_usd:.6f}")

    # Cost summary
    print(f"\nCost summary: {service.cost_summary}")

    # Model recommendation
    recommendations = ModelSelector.recommend(
        use_case="general", self_hosted_only=False, max_cost_per_million=0.15
    )
    print(f"\nRecommended models: {recommendations}")


if __name__ == "__main__":
    asyncio.run(main())
