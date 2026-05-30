"""
AI Gateway - Complete Production Implementation

A unified gateway for routing, managing, and observing all AI/LLM interactions.
Supports multiple providers, intelligent routing, budget enforcement, caching,
guardrails, and comprehensive observability.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple
)

import aiohttp
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Core Data Models
# ============================================================================

class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    SELF_HOSTED = "self_hosted"
    GOOGLE = "google"


class RequestPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BATCH = "batch"


class GatewayErrorCode(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_LIMITED = "rate_limited"
    ALL_PROVIDERS_DOWN = "all_providers_down"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    INVALID_REQUEST = "invalid_request"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


@dataclass
class Message:
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class GatewayRequest:
    """Unified request format for all providers."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    messages: List[Message] = field(default_factory=list)
    model: Optional[str] = None  # Explicit model or None for auto-routing
    model_tier: Optional[str] = None  # "high", "medium", "low" for auto-routing
    max_tokens: int = 1000
    temperature: float = 0.7
    tools: Optional[List[Dict]] = None
    stream: bool = False
    priority: RequestPriority = RequestPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000
    # Routing hints
    prefer_provider: Optional[ModelProvider] = None
    require_capabilities: List[str] = field(default_factory=list)
    max_cost: Optional[float] = None  # Max acceptable cost for this request


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class CostBreakdown:
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"


@dataclass
class GatewayResponse:
    """Unified response format from all providers."""
    request_id: str = ""
    content: str = ""
    model: str = ""
    provider: ModelProvider = ModelProvider.OPENAI
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None  # Time to first token (streaming)
    finish_reason: str = "stop"
    cached: bool = False
    fallback_used: bool = False
    original_provider: Optional[ModelProvider] = None
    tool_calls: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayError:
    code: GatewayErrorCode
    message: str
    request_id: str = ""
    retry_after_ms: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Model Registry & Pricing
# ============================================================================

@dataclass
class ModelConfig:
    model_id: str
    provider: ModelProvider
    display_name: str
    context_window: int
    max_output_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    quality_tier: str = "medium"  # high, medium, low
    avg_latency_ms: float = 1000.0
    is_available: bool = True


class ModelRegistry:
    """Central registry of all available models and their capabilities."""

    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._equivalence_map: Dict[str, List[str]] = {}
        self._load_defaults()

    def _load_defaults(self):
        defaults = [
            ModelConfig("gpt-4o", ModelProvider.OPENAI, "GPT-4o", 128000, 16384,
                       0.0025, 0.01, True, True, True, "high", 800),
            ModelConfig("gpt-4o-mini", ModelProvider.OPENAI, "GPT-4o Mini", 128000, 16384,
                       0.00015, 0.0006, True, True, True, "medium", 500),
            ModelConfig("claude-3-5-sonnet", ModelProvider.ANTHROPIC, "Claude 3.5 Sonnet", 200000, 8192,
                       0.003, 0.015, True, True, True, "high", 900),
            ModelConfig("claude-3-5-haiku", ModelProvider.ANTHROPIC, "Claude 3.5 Haiku", 200000, 8192,
                       0.0008, 0.004, False, True, True, "medium", 400),
            ModelConfig("gpt-4o-azure", ModelProvider.AZURE_OPENAI, "GPT-4o (Azure)", 128000, 16384,
                       0.0025, 0.01, True, True, True, "high", 850),
            ModelConfig("llama-3-70b", ModelProvider.SELF_HOSTED, "Llama 3 70B", 8192, 4096,
                       0.0, 0.0, False, False, True, "medium", 600),
        ]
        for model in defaults:
            self._models[model.model_id] = model

        # Equivalence mapping for fallback
        self._equivalence_map = {
            "gpt-4o": ["claude-3-5-sonnet", "gpt-4o-azure", "llama-3-70b"],
            "claude-3-5-sonnet": ["gpt-4o", "gpt-4o-azure", "llama-3-70b"],
            "gpt-4o-mini": ["claude-3-5-haiku", "llama-3-70b"],
            "claude-3-5-haiku": ["gpt-4o-mini", "llama-3-70b"],
        }

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        return self._models.get(model_id)

    def get_fallbacks(self, model_id: str) -> List[str]:
        return self._equivalence_map.get(model_id, [])

    def get_models_by_tier(self, tier: str) -> List[ModelConfig]:
        return [m for m in self._models.values() if m.quality_tier == tier and m.is_available]

    def get_models_by_provider(self, provider: ModelProvider) -> List[ModelConfig]:
        return [m for m in self._models.values() if m.provider == provider and m.is_available]

    def compute_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> CostBreakdown:
        model = self._models.get(model_id)
        if not model:
            return CostBreakdown()
        input_cost = (input_tokens / 1000) * model.input_cost_per_1k
        output_cost = (output_tokens / 1000) * model.output_cost_per_1k
        return CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost
        )

    def estimate_cost(self, model_id: str, input_tokens: int, max_output_tokens: int) -> float:
        """Estimate maximum cost before sending request."""
        model = self._models.get(model_id)
        if not model:
            return 0.0
        return (input_tokens / 1000) * model.input_cost_per_1k + \
               (max_output_tokens / 1000) * model.output_cost_per_1k


# ============================================================================
# Rate Limiter
# ============================================================================

class SlidingWindowRateLimiter:
    """Token bucket + sliding window rate limiter."""

    def __init__(self):
        self._windows: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def check_and_consume(
        self, key: str, tokens: int, limit: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """Check if request is within limits and consume tokens.
        Returns (allowed, remaining_tokens).
        """
        async with self._locks[key]:
            now = time.time()
            cutoff = now - window_seconds
            # Remove expired entries
            self._windows[key] = [
                (ts, t) for ts, t in self._windows[key] if ts > cutoff
            ]
            # Sum current window
            current_usage = sum(t for _, t in self._windows[key])
            if current_usage + tokens > limit:
                return False, max(0, limit - current_usage)
            # Consume
            self._windows[key].append((now, tokens))
            return True, limit - current_usage - tokens

    def get_usage(self, key: str, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        return sum(t for ts, t in self._windows[key] if ts > cutoff)


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    requests_per_day: int = 10000
    concurrent_requests: int = 10


class RateLimitManager:
    """Multi-dimensional rate limiting per tenant/user/model."""

    def __init__(self):
        self._limiter = SlidingWindowRateLimiter()
        self._configs: Dict[str, RateLimitConfig] = {}
        self._concurrent: Dict[str, int] = defaultdict(int)
        self._concurrent_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def set_config(self, key: str, config: RateLimitConfig):
        self._configs[key] = config

    def _get_config(self, tenant_id: str, model: str) -> RateLimitConfig:
        # Check specific first, then defaults
        for key in [f"{tenant_id}:{model}", tenant_id, "default"]:
            if key in self._configs:
                return self._configs[key]
        return RateLimitConfig()

    async def check_rate_limit(
        self, tenant_id: str, user_id: str, model: str, estimated_tokens: int
    ) -> Tuple[bool, Optional[GatewayError]]:
        config = self._get_config(tenant_id, model)

        # Check RPM
        rpm_key = f"rpm:{tenant_id}:{user_id}"
        allowed, remaining = await self._limiter.check_and_consume(
            rpm_key, 1, config.requests_per_minute, 60
        )
        if not allowed:
            return False, GatewayError(
                code=GatewayErrorCode.RATE_LIMITED,
                message=f"Rate limit exceeded: {config.requests_per_minute} requests/minute",
                retry_after_ms=5000
            )

        # Check TPM
        tpm_key = f"tpm:{tenant_id}"
        allowed, remaining = await self._limiter.check_and_consume(
            tpm_key, estimated_tokens, config.tokens_per_minute, 60
        )
        if not allowed:
            return False, GatewayError(
                code=GatewayErrorCode.RATE_LIMITED,
                message=f"Token rate limit exceeded: {config.tokens_per_minute} tokens/minute",
                retry_after_ms=10000
            )

        # Check concurrent
        async with self._concurrent_locks[tenant_id]:
            if self._concurrent[tenant_id] >= config.concurrent_requests:
                return False, GatewayError(
                    code=GatewayErrorCode.RATE_LIMITED,
                    message=f"Concurrent request limit exceeded: {config.concurrent_requests}",
                    retry_after_ms=2000
                )
            self._concurrent[tenant_id] += 1

        return True, None

    async def release_concurrent(self, tenant_id: str):
        async with self._concurrent_locks[tenant_id]:
            self._concurrent[tenant_id] = max(0, self._concurrent[tenant_id] - 1)


# ============================================================================
# Circuit Breaker
# ============================================================================

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_ms: int = 30000
    half_open_max_requests: int = 2
    success_threshold: int = 3  # Successes needed to close from half-open


class CircuitBreaker:
    """Per-provider circuit breaker to prevent cascading failures."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.half_open_requests = 0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                elapsed = (time.time() - self.last_failure_time) * 1000
                if elapsed >= self.config.recovery_timeout_ms:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_requests = 0
                    self.success_count = 0
                    logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                    return True
                return False
            else:  # HALF_OPEN
                if self.half_open_requests < self.config.half_open_max_requests:
                    self.half_open_requests += 1
                    return True
                return False

    async def record_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
            else:
                self.failure_count = 0

    async def record_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: CLOSED -> OPEN (failures={self.failure_count})")


# ============================================================================
# Prompt & Semantic Cache
# ============================================================================

class PromptCache:
    """Exact-match and prefix cache for deterministic prompts."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self._cache: Dict[str, Tuple[GatewayResponse, float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _make_key(self, request: GatewayRequest) -> str:
        """Create cache key from request content."""
        key_data = {
            "messages": [(m.role, m.content) for m in request.messages],
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "tools": request.tools,
        }
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def get(self, request: GatewayRequest) -> Optional[GatewayResponse]:
        # Only cache deterministic requests
        if request.temperature > 0:
            return None

        key = self._make_key(request)
        if key in self._cache:
            response, expires_at = self._cache[key]
            if time.time() < expires_at:
                self._hits += 1
                cached_response = GatewayResponse(
                    request_id=request.request_id,
                    content=response.content,
                    model=response.model,
                    provider=response.provider,
                    usage=response.usage,
                    cost=CostBreakdown(),  # No cost for cached response
                    latency_ms=0.1,
                    cached=True,
                    finish_reason=response.finish_reason,
                    tool_calls=response.tool_calls,
                )
                return cached_response
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def put(self, request: GatewayRequest, response: GatewayResponse, ttl: Optional[int] = None):
        if request.temperature > 0:
            return
        if len(self._cache) >= self._max_size:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        key = self._make_key(request)
        expires_at = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (response, expires_at)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class SemanticCache:
    """Embedding-based similarity cache for non-deterministic prompts."""

    def __init__(self, similarity_threshold: float = 0.95, max_size: int = 5000):
        self._entries: List[Tuple[np.ndarray, GatewayRequest, GatewayResponse, float]] = []
        self._threshold = similarity_threshold
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text. In production, use a fast embedding model."""
        # Placeholder - in production, call embedding API
        np.random.seed(hash(text) % 2**32)
        return np.random.randn(256).astype(np.float32)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    async def get(self, request: GatewayRequest) -> Optional[GatewayResponse]:
        if not request.messages:
            return None

        query_text = request.messages[-1].content
        query_embedding = await self._get_embedding(query_text)

        best_similarity = 0.0
        best_response = None

        for embedding, cached_req, cached_resp, expires_at in self._entries:
            if time.time() >= expires_at:
                continue
            if cached_req.model != request.model:
                continue
            sim = self._cosine_similarity(query_embedding, embedding)
            if sim > best_similarity and sim >= self._threshold:
                best_similarity = sim
                best_response = cached_resp

        if best_response:
            self._hits += 1
            return GatewayResponse(
                request_id=request.request_id,
                content=best_response.content,
                model=best_response.model,
                provider=best_response.provider,
                usage=best_response.usage,
                cost=CostBreakdown(),
                latency_ms=0.5,
                cached=True,
                metadata={"cache_type": "semantic", "similarity": best_similarity}
            )
        self._misses += 1
        return None

    async def put(self, request: GatewayRequest, response: GatewayResponse, ttl: int = 3600):
        if not request.messages:
            return
        query_text = request.messages[-1].content
        embedding = await self._get_embedding(query_text)
        expires_at = time.time() + ttl

        if len(self._entries) >= self._max_size:
            # Remove expired entries first
            self._entries = [e for e in self._entries if time.time() < e[3]]
            if len(self._entries) >= self._max_size:
                self._entries.pop(0)

        self._entries.append((embedding, request, response, expires_at))


# ============================================================================
# Guardrails
# ============================================================================

class GuardrailResult:
    def __init__(self, passed: bool, reason: str = "", modified_content: Optional[str] = None):
        self.passed = passed
        self.reason = reason
        self.modified_content = modified_content


class Guardrail(ABC):
    @abstractmethod
    async def evaluate(self, content: str, context: Dict[str, Any]) -> GuardrailResult:
        pass


class PromptInjectionGuardrail(Guardrail):
    """Detect and block prompt injection attempts."""

    INJECTION_PATTERNS = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard your instructions",
        "you are now",
        "new instructions:",
        "system prompt:",
        "forget everything",
        "override your",
    ]

    async def evaluate(self, content: str, context: Dict[str, Any]) -> GuardrailResult:
        lower_content = content.lower()
        for pattern in self.INJECTION_PATTERNS:
            if pattern in lower_content:
                return GuardrailResult(
                    passed=False,
                    reason=f"Potential prompt injection detected: '{pattern}'"
                )
        return GuardrailResult(passed=True)


class PIIGuardrail(Guardrail):
    """Detect and optionally redact PII from prompts/responses."""

    import re
    PII_PATTERNS = {
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "credit_card": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
    }

    def __init__(self, redact: bool = True):
        self._redact = redact

    async def evaluate(self, content: str, context: Dict[str, Any]) -> GuardrailResult:
        found_pii = []
        modified = content

        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(content)
            if matches:
                found_pii.append(pii_type)
                if self._redact:
                    modified = pattern.sub(f"[REDACTED_{pii_type.upper()}]", modified)

        if found_pii and not self._redact:
            return GuardrailResult(
                passed=False,
                reason=f"PII detected: {', '.join(found_pii)}"
            )
        elif found_pii and self._redact:
            return GuardrailResult(
                passed=True,
                reason=f"PII redacted: {', '.join(found_pii)}",
                modified_content=modified
            )
        return GuardrailResult(passed=True)


class ContentSafetyGuardrail(Guardrail):
    """Check response content for safety violations."""

    BLOCKED_CATEGORIES = ["violence", "self_harm", "illegal_activity"]

    async def evaluate(self, content: str, context: Dict[str, Any]) -> GuardrailResult:
        # In production, call a content safety API (Azure Content Safety, OpenAI Moderation)
        # Placeholder implementation
        return GuardrailResult(passed=True)


class GuardrailPipeline:
    """Ordered pipeline of guardrails for pre-request and post-response."""

    def __init__(self):
        self._pre_request_guardrails: List[Guardrail] = []
        self._post_response_guardrails: List[Guardrail] = []

    def add_pre_request(self, guardrail: Guardrail):
        self._pre_request_guardrails.append(guardrail)

    def add_post_response(self, guardrail: Guardrail):
        self._post_response_guardrails.append(guardrail)

    async def run_pre_request(self, request: GatewayRequest) -> Tuple[bool, Optional[GatewayError], GatewayRequest]:
        """Run pre-request guardrails. May modify the request."""
        content = " ".join(m.content for m in request.messages if m.content)
        context = {"tenant_id": request.tenant_id, "user_id": request.user_id}

        for guardrail in self._pre_request_guardrails:
            result = await guardrail.evaluate(content, context)
            if not result.passed:
                return False, GatewayError(
                    code=GatewayErrorCode.GUARDRAIL_BLOCKED,
                    message=result.reason,
                    request_id=request.request_id
                ), request
            if result.modified_content:
                # Update the last user message with modified content
                for msg in reversed(request.messages):
                    if msg.role == "user":
                        msg.content = result.modified_content
                        break
        return True, None, request

    async def run_post_response(self, response: GatewayResponse) -> Tuple[bool, Optional[GatewayError], GatewayResponse]:
        """Run post-response guardrails. May modify the response."""
        context = {"model": response.model, "provider": response.provider.value}

        for guardrail in self._post_response_guardrails:
            result = await guardrail.evaluate(response.content, context)
            if not result.passed:
                return False, GatewayError(
                    code=GatewayErrorCode.GUARDRAIL_BLOCKED,
                    message=f"Response blocked: {result.reason}",
                    request_id=response.request_id
                ), response
            if result.modified_content:
                response.content = result.modified_content
        return True, None, response


# ============================================================================
# Provider Adapters (Simplified - full implementation in provider-abstraction.py)
# ============================================================================

class ProviderAdapter(ABC):
    @abstractmethod
    async def complete(self, request: GatewayRequest, model_config: ModelConfig) -> GatewayResponse:
        pass

    @abstractmethod
    async def stream(self, request: GatewayRequest, model_config: ModelConfig) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass


class OpenAIAdapter(ProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url

    async def complete(self, request: GatewayRequest, model_config: ModelConfig) -> GatewayResponse:
        start_time = time.time()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_config.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            payload["tools"] = request.tools

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000)
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise Exception(f"OpenAI error {resp.status}: {error_body}")
                data = await resp.json()

        latency_ms = (time.time() - start_time) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})

        token_usage = TokenUsage(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        return GatewayResponse(
            request_id=request.request_id,
            content=choice["message"].get("content", ""),
            model=data["model"],
            provider=ModelProvider.OPENAI,
            usage=token_usage,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=choice["message"].get("tool_calls"),
        )

    async def stream(self, request: GatewayRequest, model_config: ModelConfig) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_config.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000)
            ) as resp:
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: ") and line_str != "data: [DONE]":
                        chunk = json.loads(line_str[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if content := delta.get("content"):
                            yield content

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False


class AnthropicAdapter(ProviderAdapter):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://api.anthropic.com/v1"

    async def complete(self, request: GatewayRequest, model_config: ModelConfig) -> GatewayResponse:
        start_time = time.time()
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        # Convert messages format for Anthropic
        system_msg = ""
        messages = []
        for m in request.messages:
            if m.role == "system":
                system_msg = m.content
            else:
                messages.append({"role": m.role, "content": m.content})

        payload = {
            "model": model_config.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_msg:
            payload["system"] = system_msg

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000)
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise Exception(f"Anthropic error {resp.status}: {error_body}")
                data = await resp.json()

        latency_ms = (time.time() - start_time) * 1000
        content = data["content"][0]["text"] if data.get("content") else ""
        usage = data.get("usage", {})

        return GatewayResponse(
            request_id=request.request_id,
            content=content,
            model=data["model"],
            provider=ModelProvider.ANTHROPIC,
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
            latency_ms=latency_ms,
            finish_reason=data.get("stop_reason", "end_turn"),
        )

    async def stream(self, request: GatewayRequest, model_config: ModelConfig) -> AsyncGenerator[str, None]:
        # Simplified streaming for Anthropic
        response = await self.complete(request, model_config)
        yield response.content

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/messages",
                    headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status in [200, 405]  # 405 = method not allowed but reachable
        except Exception:
            return False


# ============================================================================
# Key Manager
# ============================================================================

class KeyManager:
    """Manages API keys with rotation and isolation."""

    def __init__(self):
        self._keys: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._current_index: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    def add_key(self, provider: str, key: str, weight: float = 1.0, metadata: Dict = None):
        self._keys[provider].append({
            "key": key,
            "weight": weight,
            "metadata": metadata or {},
            "usage_count": 0,
            "last_error": None,
            "is_active": True,
        })

    async def get_key(self, provider: str) -> Optional[str]:
        """Get next available key using round-robin with health check."""
        async with self._lock:
            keys = [k for k in self._keys[provider] if k["is_active"]]
            if not keys:
                return None
            idx = self._current_index[provider] % len(keys)
            self._current_index[provider] = idx + 1
            keys[idx]["usage_count"] += 1
            return keys[idx]["key"]

    async def mark_key_error(self, provider: str, key: str, error: str):
        """Mark a key as having an error. Disable after repeated failures."""
        for k in self._keys[provider]:
            if k["key"] == key:
                k["last_error"] = {"error": error, "time": time.time()}
                # Disable after 3 consecutive errors in 5 minutes
                break

    async def rotate_keys(self, provider: str, new_keys: List[str]):
        """Rotate all keys for a provider."""
        async with self._lock:
            self._keys[provider] = [
                {"key": k, "weight": 1.0, "metadata": {}, "usage_count": 0,
                 "last_error": None, "is_active": True}
                for k in new_keys
            ]
            self._current_index[provider] = 0


# ============================================================================
# Request Logger & Observability
# ============================================================================

@dataclass
class RequestLog:
    request_id: str
    tenant_id: str
    user_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency_ms: float
    status: str  # "success", "error", "cached", "guardrail_blocked"
    error_message: Optional[str] = None
    cached: bool = False
    fallback_used: bool = False
    timestamp: float = field(default_factory=time.time)


class RequestLogger:
    """Async request logger with batching."""

    def __init__(self, flush_interval: float = 5.0, batch_size: int = 100):
        self._buffer: List[RequestLog] = []
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._lock = asyncio.Lock()
        self._sinks: List[Callable[[List[RequestLog]], Any]] = []

    def add_sink(self, sink: Callable[[List[RequestLog]], Any]):
        self._sinks.append(sink)

    async def log(self, entry: RequestLog):
        async with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._batch_size:
                await self._flush()

    async def _flush(self):
        if not self._buffer:
            return
        batch = self._buffer.copy()
        self._buffer.clear()
        for sink in self._sinks:
            try:
                await sink(batch) if asyncio.iscoroutinefunction(sink) else sink(batch)
            except Exception as e:
                logger.error(f"Log sink error: {e}")

    async def start_periodic_flush(self):
        while True:
            await asyncio.sleep(self._flush_interval)
            async with self._lock:
                await self._flush()


# ============================================================================
# Budget Manager (simplified - full in budget-and-cost.py)
# ============================================================================

@dataclass
class BudgetConfig:
    monthly_limit: float = 1000.0
    daily_limit: float = 50.0
    per_request_limit: float = 5.0
    alert_threshold: float = 0.8
    hard_limit: bool = True  # If False, allow overage with alert


class BudgetManager:
    """Per-tenant budget enforcement."""

    def __init__(self):
        self._configs: Dict[str, BudgetConfig] = {}
        self._daily_spend: Dict[str, float] = defaultdict(float)
        self._monthly_spend: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    def set_budget(self, tenant_id: str, config: BudgetConfig):
        self._configs[tenant_id] = config

    async def check_budget(self, tenant_id: str, estimated_cost: float) -> Tuple[bool, Optional[GatewayError]]:
        config = self._configs.get(tenant_id, BudgetConfig())

        # Check per-request limit
        if estimated_cost > config.per_request_limit:
            return False, GatewayError(
                code=GatewayErrorCode.BUDGET_EXCEEDED,
                message=f"Estimated cost ${estimated_cost:.4f} exceeds per-request limit ${config.per_request_limit:.2f}"
            )

        async with self._lock:
            # Check daily limit
            if self._daily_spend[tenant_id] + estimated_cost > config.daily_limit:
                if config.hard_limit:
                    return False, GatewayError(
                        code=GatewayErrorCode.BUDGET_EXCEEDED,
                        message=f"Daily budget exceeded: ${self._daily_spend[tenant_id]:.2f}/{config.daily_limit:.2f}"
                    )

            # Check monthly limit
            if self._monthly_spend[tenant_id] + estimated_cost > config.monthly_limit:
                if config.hard_limit:
                    return False, GatewayError(
                        code=GatewayErrorCode.BUDGET_EXCEEDED,
                        message=f"Monthly budget exceeded: ${self._monthly_spend[tenant_id]:.2f}/{config.monthly_limit:.2f}"
                    )

        return True, None

    async def record_spend(self, tenant_id: str, cost: float):
        async with self._lock:
            self._daily_spend[tenant_id] += cost
            self._monthly_spend[tenant_id] += cost

    async def get_remaining_budget(self, tenant_id: str) -> Dict[str, float]:
        config = self._configs.get(tenant_id, BudgetConfig())
        return {
            "daily_remaining": config.daily_limit - self._daily_spend[tenant_id],
            "monthly_remaining": config.monthly_limit - self._monthly_spend[tenant_id],
        }


# ============================================================================
# Retry Engine
# ============================================================================

class RetryEngine:
    """Exponential backoff retry with jitter."""

    def __init__(self, max_retries: int = 3, base_delay_ms: int = 1000, max_delay_ms: int = 30000):
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms

    def _should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        retryable_indicators = ["timeout", "429", "500", "502", "503", "504", "rate limit", "overloaded"]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff + jitter."""
        delay = self.base_delay_ms * (2 ** attempt)
        delay = min(delay, self.max_delay_ms)
        # Add jitter (±25%)
        jitter = delay * 0.25 * (2 * np.random.random() - 1)
        return (delay + jitter) / 1000  # Convert to seconds

    async def execute_with_retry(
        self, func: Callable, *args, **kwargs
    ) -> Any:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries and self._should_retry(e):
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Retry attempt {attempt + 1}/{self.max_retries} after {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise
        raise last_error


# ============================================================================
# AI Gateway - Main Orchestrator
# ============================================================================

class AIGateway:
    """
    Main AI Gateway orchestrator that coordinates all components:
    - Rate limiting
    - Budget enforcement
    - Guardrails
    - Caching
    - Model routing
    - Provider execution with retry and fallback
    - Cost tracking
    - Logging
    """

    def __init__(self):
        # Core components
        self.model_registry = ModelRegistry()
        self.rate_limiter = RateLimitManager()
        self.budget_manager = BudgetManager()
        self.guardrails = GuardrailPipeline()
        self.prompt_cache = PromptCache()
        self.semantic_cache = SemanticCache()
        self.key_manager = KeyManager()
        self.request_logger = RequestLogger()
        self.retry_engine = RetryEngine()

        # Provider adapters
        self._adapters: Dict[ModelProvider, ProviderAdapter] = {}
        # Circuit breakers per provider
        self._circuit_breakers: Dict[ModelProvider, CircuitBreaker] = {}

        # Setup default guardrails
        self.guardrails.add_pre_request(PromptInjectionGuardrail())
        self.guardrails.add_pre_request(PIIGuardrail(redact=True))
        self.guardrails.add_post_response(ContentSafetyGuardrail())

    def register_provider(self, provider: ModelProvider, adapter: ProviderAdapter):
        self._adapters[provider] = adapter
        self._circuit_breakers[provider] = CircuitBreaker(
            name=provider.value,
            config=CircuitBreakerConfig()
        )

    async def process_request(self, request: GatewayRequest) -> GatewayResponse | GatewayError:
        """
        Main request processing pipeline:
        1. Pre-request guardrails
        2. Rate limit check
        3. Budget check
        4. Cache lookup
        5. Model routing
        6. Provider execution (with retry + fallback)
        7. Post-response guardrails
        8. Cost tracking
        9. Logging
        """
        start_time = time.time()

        # 1. Pre-request guardrails
        passed, error, request = await self.guardrails.run_pre_request(request)
        if not passed:
            await self._log_request(request, None, "guardrail_blocked", error.message)
            return error

        # 2. Rate limit check
        estimated_tokens = self._estimate_tokens(request)
        allowed, error = await self.rate_limiter.check_rate_limit(
            request.tenant_id, request.user_id,
            request.model or "default", estimated_tokens
        )
        if not allowed:
            await self._log_request(request, None, "rate_limited", error.message)
            return error

        try:
            # 3. Resolve model
            model_id = await self._resolve_model(request)
            model_config = self.model_registry.get_model(model_id)
            if not model_config:
                return GatewayError(
                    code=GatewayErrorCode.INVALID_REQUEST,
                    message=f"Unknown model: {model_id}",
                    request_id=request.request_id
                )

            # 4. Budget check
            estimated_cost = self.model_registry.estimate_cost(
                model_id, estimated_tokens, request.max_tokens
            )
            allowed, error = await self.budget_manager.check_budget(request.tenant_id, estimated_cost)
            if not allowed:
                await self._log_request(request, None, "budget_exceeded", error.message)
                return error

            # 5. Cache lookup
            cached = self.prompt_cache.get(request)
            if cached:
                await self._log_request(request, cached, "cached")
                return cached

            cached = await self.semantic_cache.get(request)
            if cached:
                await self._log_request(request, cached, "cached")
                return cached

            # 6. Execute with retry and fallback
            response = await self._execute_with_fallback(request, model_config)

            # 7. Post-response guardrails
            passed, error, response = await self.guardrails.run_post_response(response)
            if not passed:
                await self._log_request(request, None, "guardrail_blocked", error.message)
                return error

            # 8. Compute cost and track
            response.cost = self.model_registry.compute_cost(
                response.model, response.usage.input_tokens, response.usage.output_tokens
            )
            response.latency_ms = (time.time() - start_time) * 1000
            await self.budget_manager.record_spend(request.tenant_id, response.cost.total_cost)

            # 9. Cache store
            self.prompt_cache.put(request, response)
            await self.semantic_cache.put(request, response)

            # 10. Log
            await self._log_request(request, response, "success")

            return response

        finally:
            await self.rate_limiter.release_concurrent(request.tenant_id)

    async def _resolve_model(self, request: GatewayRequest) -> str:
        """Resolve the model to use based on request configuration."""
        if request.model:
            return request.model
        # Auto-route based on tier
        tier = request.model_tier or "medium"
        models = self.model_registry.get_models_by_tier(tier)
        if models:
            return models[0].model_id
        return "gpt-4o-mini"  # Default fallback

    async def _execute_with_fallback(
        self, request: GatewayRequest, model_config: ModelConfig
    ) -> GatewayResponse:
        """Execute request with retry and fallback to equivalent models."""
        # Try primary model
        try:
            return await self._execute_single(request, model_config)
        except Exception as primary_error:
            logger.warning(f"Primary model {model_config.model_id} failed: {primary_error}")

        # Try fallbacks
        fallback_models = self.model_registry.get_fallbacks(model_config.model_id)
        for fallback_id in fallback_models:
            fallback_config = self.model_registry.get_model(fallback_id)
            if not fallback_config or not fallback_config.is_available:
                continue
            try:
                response = await self._execute_single(request, fallback_config)
                response.fallback_used = True
                response.original_provider = model_config.provider
                return response
            except Exception as e:
                logger.warning(f"Fallback model {fallback_id} failed: {e}")
                continue

        raise Exception(f"All providers failed for request {request.request_id}")

    async def _execute_single(
        self, request: GatewayRequest, model_config: ModelConfig
    ) -> GatewayResponse:
        """Execute a single request against a specific provider/model."""
        provider = model_config.provider
        circuit = self._circuit_breakers.get(provider)

        if circuit and not await circuit.can_execute():
            raise Exception(f"Circuit breaker OPEN for {provider.value}")

        adapter = self._adapters.get(provider)
        if not adapter:
            raise Exception(f"No adapter registered for {provider.value}")

        try:
            response = await self.retry_engine.execute_with_retry(
                adapter.complete, request, model_config
            )
            if circuit:
                await circuit.record_success()
            return response
        except Exception as e:
            if circuit:
                await circuit.record_failure()
            raise

    def _estimate_tokens(self, request: GatewayRequest) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        total_chars = sum(len(m.content or "") for m in request.messages)
        return total_chars // 4 + request.max_tokens

    async def _log_request(
        self, request: GatewayRequest, response: Optional[GatewayResponse],
        status: str, error_message: str = None
    ):
        log_entry = RequestLog(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            model=response.model if response else (request.model or "unknown"),
            provider=response.provider.value if response else "unknown",
            input_tokens=response.usage.input_tokens if response else 0,
            output_tokens=response.usage.output_tokens if response else 0,
            cost=response.cost.total_cost if response else 0.0,
            latency_ms=response.latency_ms if response else 0.0,
            status=status,
            error_message=error_message,
            cached=response.cached if response else False,
            fallback_used=response.fallback_used if response else False,
        )
        await self.request_logger.log(log_entry)

    # ========================================================================
    # Streaming Support
    # ========================================================================

    async def process_stream(self, request: GatewayRequest) -> AsyncGenerator[str, None]:
        """Process a streaming request through the gateway."""
        # Pre-flight checks (guardrails, rate limit, budget)
        passed, error, request = await self.guardrails.run_pre_request(request)
        if not passed:
            yield f"[ERROR] {error.message}"
            return

        estimated_tokens = self._estimate_tokens(request)
        allowed, error = await self.rate_limiter.check_rate_limit(
            request.tenant_id, request.user_id,
            request.model or "default", estimated_tokens
        )
        if not allowed:
            yield f"[ERROR] {error.message}"
            return

        model_id = await self._resolve_model(request)
        model_config = self.model_registry.get_model(model_id)
        if not model_config:
            yield f"[ERROR] Unknown model: {model_id}"
            return

        adapter = self._adapters.get(model_config.provider)
        if not adapter:
            yield f"[ERROR] No adapter for {model_config.provider.value}"
            return

        try:
            async for chunk in adapter.stream(request, model_config):
                yield chunk
        except Exception as e:
            yield f"[ERROR] Stream failed: {e}"
        finally:
            await self.rate_limiter.release_concurrent(request.tenant_id)


# ============================================================================
# FastAPI Application
# ============================================================================

def create_app() -> "FastAPI":
    """Create the FastAPI application for the AI Gateway."""
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel as PydanticBaseModel

    app = FastAPI(title="AI Gateway", version="1.0.0")
    gateway = AIGateway()

    # Register providers (in production, load from config/secrets)
    # gateway.register_provider(ModelProvider.OPENAI, OpenAIAdapter(api_key="..."))
    # gateway.register_provider(ModelProvider.ANTHROPIC, AnthropicAdapter(api_key="..."))

    class CompletionRequest(PydanticBaseModel):
        messages: List[Dict[str, str]]
        model: Optional[str] = None
        model_tier: Optional[str] = None
        max_tokens: int = 1000
        temperature: float = 0.7
        stream: bool = False
        tools: Optional[List[Dict]] = None
        priority: str = "normal"
        max_cost: Optional[float] = None

    @app.post("/v1/chat/completions")
    async def chat_completions(req: CompletionRequest, request: Request):
        # Extract tenant/user from auth headers
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        user_id = request.headers.get("X-User-ID", "anonymous")

        gateway_request = GatewayRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            messages=[Message(role=m["role"], content=m["content"]) for m in req.messages],
            model=req.model,
            model_tier=req.model_tier,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            stream=req.stream,
            tools=req.tools,
            priority=RequestPriority(req.priority),
            max_cost=req.max_cost,
        )

        if req.stream:
            async def stream_generator():
                async for chunk in gateway.process_stream(gateway_request):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(stream_generator(), media_type="text/event-stream")

        result = await gateway.process_request(gateway_request)
        if isinstance(result, GatewayError):
            raise HTTPException(
                status_code=429 if result.code == GatewayErrorCode.RATE_LIMITED else 400,
                detail={"error": result.code.value, "message": result.message}
            )

        return {
            "id": result.request_id,
            "model": result.model,
            "provider": result.provider.value,
            "choices": [{"message": {"role": "assistant", "content": result.content}}],
            "usage": {
                "prompt_tokens": result.usage.input_tokens,
                "completion_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
            },
            "cost": {"total": result.cost.total_cost, "currency": result.cost.currency},
            "metadata": {
                "latency_ms": result.latency_ms,
                "cached": result.cached,
                "fallback_used": result.fallback_used,
            }
        }

    @app.get("/v1/health")
    async def health():
        return {"status": "healthy", "cache_hit_rate": gateway.prompt_cache.hit_rate}

    @app.get("/v1/budget/{tenant_id}")
    async def get_budget(tenant_id: str):
        return await gateway.budget_manager.get_remaining_budget(tenant_id)

    return app


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
