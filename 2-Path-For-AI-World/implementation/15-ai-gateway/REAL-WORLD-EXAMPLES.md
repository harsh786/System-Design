# AI Gateway — Real-World Examples

## Case Study 1: Multi-Provider Abstraction with LiteLLM

### Context

A Series-B fintech company (120 engineers, 8 AI-powered features) was locked into OpenAI. When GPT-4 had a 3-hour outage during market hours, their trading analysis feature went completely dark. They decided to build provider abstraction using LiteLLM as the core routing engine behind a custom gateway.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Gateway (K8s)                         │
│                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────┐   │
│  │  Ingress │──▶│  Auth/Rate   │──▶│   LiteLLM Router  │   │
│  │  (Envoy) │   │  Limiter     │   │                   │   │
│  └──────────┘   └──────────────┘   │  ┌─────────────┐  │   │
│                                     │  │ OpenAI      │  │   │
│  ┌──────────────────────────────┐   │  │ Anthropic   │  │   │
│  │  Semantic Cache (Redis +     │   │  │ Azure OAI   │  │   │
│  │  pgvector for embeddings)    │◀──│  │ Google AI   │  │   │
│  └──────────────────────────────┘   │  └─────────────┘  │   │
│                                     └───────────────────┘   │
│  ┌──────────────────────────────┐                           │
│  │  Observability (OTel → Prom) │                           │
│  └──────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### LiteLLM Configuration (Actual Production Config)

```yaml
# litellm_config.yaml
model_list:
  - model_name: "gpt-4-turbo"
    litellm_params:
      model: "openai/gpt-4-turbo"
      api_key: "os.environ/OPENAI_API_KEY"
      max_retries: 2
      timeout: 30
    model_info:
      id: "openai-gpt4t-primary"

  - model_name: "gpt-4-turbo"  # Same model_name = fallback
    litellm_params:
      model: "azure/gpt-4-turbo-2024-04-09"
      api_base: "https://eastus2.openai.azure.com"
      api_key: "os.environ/AZURE_EASTUS2_KEY"
      max_retries: 1
      timeout: 25
    model_info:
      id: "azure-gpt4t-fallback"

  - model_name: "gpt-4-turbo"  # Third fallback
    litellm_params:
      model: "anthropic/claude-sonnet-4-20250514"
      api_key: "os.environ/ANTHROPIC_API_KEY"
      max_retries: 1
      timeout: 30
    model_info:
      id: "anthropic-sonnet-fallback"

  - model_name: "fast-completion"
    litellm_params:
      model: "openai/gpt-4o-mini"
      api_key: "os.environ/OPENAI_API_KEY"
    model_info:
      id: "gpt4o-mini-fast"

  - model_name: "fast-completion"
    litellm_params:
      model: "anthropic/claude-3-5-haiku-20241022"
      api_key: "os.environ/ANTHROPIC_API_KEY"
    model_info:
      id: "haiku-fast-fallback"

  - model_name: "embedding"
    litellm_params:
      model: "openai/text-embedding-3-small"
      api_key: "os.environ/OPENAI_API_KEY"

  - model_name: "embedding"
    litellm_params:
      model: "google/text-embedding-004"
      api_key: "os.environ/GOOGLE_API_KEY"

router_settings:
  routing_strategy: "latency-based-routing"
  num_retries: 3
  retry_after: 5
  timeout: 60
  fallbacks:
    - gpt-4-turbo: ["gpt-4-turbo"]  # cycles through providers
    - fast-completion: ["fast-completion"]
  allowed_fails: 2
  cooldown_time: 120  # seconds before retrying failed provider

litellm_settings:
  drop_params: true  # drop unsupported params when falling back
  set_verbose: false
  cache: true
  cache_params:
    type: "redis"
    host: "redis-gateway.internal"
    port: 6379
    ttl: 3600
```

### Gateway Application Layer

```python
# gateway/main.py — Custom logic wrapping LiteLLM
from fastapi import FastAPI, Request, HTTPException
from litellm import Router
import yaml
import time

app = FastAPI()

with open("litellm_config.yaml") as f:
    config = yaml.safe_load(f)

router = Router(
    model_list=config["model_list"],
    **config["router_settings"]
)

@app.post("/v1/chat/completions")
async def chat_completion(request: Request):
    body = await request.json()
    team_id = request.headers.get("X-Team-ID")
    
    # Map internal model aliases to gateway models
    model_mapping = {
        "default": "gpt-4-turbo",
        "fast": "fast-completion",
        "premium": "gpt-4-turbo",
    }
    
    requested_model = body.get("model", "default")
    gateway_model = model_mapping.get(requested_model, requested_model)
    
    # Inject team-specific system prompts if configured
    team_config = get_team_config(team_id)
    if team_config.get("system_prompt_prefix"):
        messages = body.get("messages", [])
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = (
                team_config["system_prompt_prefix"] + "\n" + messages[0]["content"]
            )
    
    start = time.time()
    response = await router.acompletion(
        model=gateway_model,
        messages=body["messages"],
        temperature=body.get("temperature", 0.7),
        max_tokens=body.get("max_tokens", 4096),
        metadata={
            "team_id": team_id,
            "trace_id": request.headers.get("X-Trace-ID"),
        }
    )
    latency = time.time() - start
    
    # Emit metrics
    REQUEST_LATENCY.labels(
        model=gateway_model,
        provider=response._hidden_params.get("model_id", "unknown"),
        team=team_id
    ).observe(latency)
    
    return response
```

### Results After 6 Months

| Metric | Before Gateway | After Gateway |
|--------|---------------|---------------|
| Provider outage impact | Full feature failure | <2s failover, no user impact |
| Monthly LLM spend | $47K | $38K (semantic cache + routing) |
| P99 latency | 12.4s | 8.1s (latency-based routing) |
| Provider lock-in | 100% OpenAI | 55% OpenAI, 30% Azure, 15% Anthropic |
| Time to add new model | 2 weeks (code changes) | 15 minutes (config change) |

---

## Case Study 2: Netflix-Style Model Routing with Fallback Chains

### Context

A large streaming platform (not Netflix, but similar scale — 200M+ users) built an AI recommendation and content understanding system. They needed:
- Different models for different content types (video understanding vs. text generation)
- Automatic failover with quality degradation awareness
- A/B testing of model versions without code deployments
- Cost optimization by routing simpler queries to cheaper models

### Routing Decision Tree

```
Incoming Request
      │
      ▼
┌─────────────────┐
│  Classify Query  │ ← Uses a lightweight classifier (fine-tuned distilbert)
│  Complexity      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Simple    Complex
    │         │
    ▼         ▼
┌────────┐ ┌──────────────────────────────────────────┐
│GPT-4o  │ │ Route by capability requirement:         │
│Mini    │ │                                          │
│$0.15/M │ │  reasoning → Claude Opus / o1            │
│        │ │  creative  → GPT-4 Turbo                 │
│        │ │  code      → Claude Sonnet               │
│        │ │  vision    → GPT-4 Vision / Gemini Pro   │
└────────┘ └──────────────────────────────────────────┘
```

### Fallback Chain Configuration

```python
# Actual production fallback configuration
FALLBACK_CHAINS = {
    "content-summarization": {
        "primary": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "timeout": 15,
            "max_retries": 2,
        },
        "fallbacks": [
            {
                "provider": "openai",
                "model": "gpt-4o",
                "timeout": 20,
                "max_retries": 1,
                "quality_degradation": 0.02,  # 2% quality drop expected
            },
            {
                "provider": "google",
                "model": "gemini-1.5-pro",
                "timeout": 25,
                "max_retries": 1,
                "quality_degradation": 0.05,
            },
            {
                "provider": "local",
                "model": "llama-3-70b",  # Self-hosted fallback
                "timeout": 10,
                "max_retries": 0,
                "quality_degradation": 0.15,
                "note": "Last resort — lower quality but always available"
            },
        ],
        "circuit_breaker": {
            "failure_threshold": 5,
            "recovery_timeout": 60,
            "half_open_requests": 3,
        }
    },
    "real-time-chat": {
        "primary": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "timeout": 5,  # Strict timeout for real-time
            "max_retries": 0,  # No retries — latency critical
        },
        "fallbacks": [
            {
                "provider": "anthropic",
                "model": "claude-3-5-haiku-20241022",
                "timeout": 5,
                "max_retries": 0,
            },
            {
                "provider": "local",
                "model": "llama-3-8b",
                "timeout": 3,
                "max_retries": 0,
                "note": "Ultra-fast local inference for degraded mode"
            },
        ],
        "circuit_breaker": {
            "failure_threshold": 3,
            "recovery_timeout": 30,
            "half_open_requests": 2,
        }
    }
}
```

### Automatic Failover Implementation

```python
class FallbackRouter:
    def __init__(self):
        self.circuit_breakers = {}  # provider -> CircuitBreaker
        self.provider_health = {}   # provider -> HealthStats
    
    async def route_with_fallback(self, chain_name: str, request: dict):
        chain = FALLBACK_CHAINS[chain_name]
        providers = [chain["primary"]] + chain["fallbacks"]
        
        last_error = None
        for i, provider_config in enumerate(providers):
            provider_key = f"{provider_config['provider']}/{provider_config['model']}"
            
            # Check circuit breaker
            cb = self.circuit_breakers.get(provider_key)
            if cb and cb.is_open():
                FAILOVER_COUNTER.labels(
                    chain=chain_name,
                    from_provider=provider_key,
                    reason="circuit_open"
                ).inc()
                continue
            
            try:
                response = await self._call_provider(provider_config, request)
                
                # Record success for circuit breaker
                if cb:
                    cb.record_success()
                
                # Log if we used a fallback
                if i > 0:
                    FALLBACK_USED.labels(
                        chain=chain_name,
                        fallback_level=i,
                        provider=provider_key
                    ).inc()
                    logger.warning(
                        f"Used fallback level {i} for {chain_name}",
                        extra={"provider": provider_key, "primary_error": str(last_error)}
                    )
                
                return response
                
            except (TimeoutError, ProviderError, RateLimitError) as e:
                last_error = e
                if cb:
                    cb.record_failure()
                else:
                    self.circuit_breakers[provider_key] = CircuitBreaker(
                        **chain["circuit_breaker"]
                    )
                    self.circuit_breakers[provider_key].record_failure()
        
        # All providers failed — return cached response or error
        cached = await self.get_stale_cache(chain_name, request)
        if cached:
            STALE_CACHE_SERVED.labels(chain=chain_name).inc()
            return cached
        
        raise AllProvidersFailedError(chain_name, last_error)
```

---

## Case Study 3: Budget Enforcement That Saved $80K

### The Incident

A machine learning team at an e-commerce company deployed a new "product description enhancer" feature. A bug in the retry logic caused infinite loops — each failed request spawned 3 more requests, exponentially. Without the gateway's budget controls, this would have cost approximately $80K in a single weekend.

### What Happened (Timeline)

```
Friday 6:14 PM — Deploy goes out (feature flag enabled for 5% of traffic)
Friday 6:15 PM — Bug triggers: timeout → retry → timeout → retry (exponential)
Friday 6:16 PM — Request rate: 50 req/s → 450 req/s → 4,000 req/s
Friday 6:17 PM — Gateway budget alert fires (team hourly budget 80% consumed)
Friday 6:18 PM — Gateway HARD STOPS the team's requests (budget exhausted)
Friday 6:18 PM — PagerDuty alert → on-call engineer notified
Friday 6:34 PM — Engineer identifies bug, rolls back feature flag
Friday 6:35 PM — Budget manually reset after root cause confirmed

Total cost incurred: $847 (2 minutes of runaway before gateway killed it)
Estimated cost without gateway: $80,000+ (entire weekend of exponential retries)
```

### Budget Enforcement Configuration

```python
# gateway/budget_enforcer.py
from dataclasses import dataclass
from enum import Enum
import redis
import time

class BudgetAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    THROTTLE = "throttle"
    BLOCK = "block"

@dataclass
class BudgetConfig:
    team_id: str
    hourly_limit_usd: float
    daily_limit_usd: float
    monthly_limit_usd: float
    warn_threshold: float = 0.7    # 70% → warning
    throttle_threshold: float = 0.9  # 90% → reduce to 10% of traffic
    hard_limit: float = 1.0        # 100% → full block

# Actual production budget table
TEAM_BUDGETS = {
    "product-team": BudgetConfig(
        team_id="product-team",
        hourly_limit_usd=50.0,
        daily_limit_usd=800.0,
        monthly_limit_usd=15000.0,
    ),
    "search-team": BudgetConfig(
        team_id="search-team",
        hourly_limit_usd=200.0,
        daily_limit_usd=3000.0,
        monthly_limit_usd=50000.0,
    ),
    "customer-support": BudgetConfig(
        team_id="customer-support",
        hourly_limit_usd=100.0,
        daily_limit_usd=1500.0,
        monthly_limit_usd=25000.0,
    ),
}

class BudgetEnforcer:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.cost_per_token = {
            "gpt-4-turbo": {"input": 0.01/1000, "output": 0.03/1000},
            "gpt-4o": {"input": 0.005/1000, "output": 0.015/1000},
            "gpt-4o-mini": {"input": 0.00015/1000, "output": 0.0006/1000},
            "claude-sonnet-4-20250514": {"input": 0.003/1000, "output": 0.015/1000},
            "claude-3-5-haiku-20241022": {"input": 0.001/1000, "output": 0.005/1000},
        }
    
    def check_budget(self, team_id: str, model: str, estimated_tokens: int) -> BudgetAction:
        config = TEAM_BUDGETS.get(team_id)
        if not config:
            return BudgetAction.BLOCK  # Unknown team = block
        
        # Estimate cost of this request
        cost_rates = self.cost_per_token.get(model, {"input": 0.01/1000, "output": 0.03/1000})
        estimated_cost = estimated_tokens * cost_rates["output"]  # Conservative estimate
        
        # Check all time windows
        for window, limit in [
            ("hour", config.hourly_limit_usd),
            ("day", config.daily_limit_usd),
            ("month", config.monthly_limit_usd),
        ]:
            spent = self._get_spend(team_id, window)
            ratio = (spent + estimated_cost) / limit
            
            if ratio >= config.hard_limit:
                self._alert_budget_exhausted(team_id, window, spent, limit)
                return BudgetAction.BLOCK
            elif ratio >= config.throttle_threshold:
                return BudgetAction.THROTTLE
            elif ratio >= config.warn_threshold:
                self._alert_budget_warning(team_id, window, spent, limit)
                return BudgetAction.WARN
        
        return BudgetAction.ALLOW
    
    def record_spend(self, team_id: str, model: str, input_tokens: int, output_tokens: int):
        cost_rates = self.cost_per_token[model]
        cost = (input_tokens * cost_rates["input"]) + (output_tokens * cost_rates["output"])
        
        now = time.time()
        hour_key = f"budget:{team_id}:hour:{int(now // 3600)}"
        day_key = f"budget:{team_id}:day:{int(now // 86400)}"
        month_key = f"budget:{team_id}:month:{time.strftime('%Y-%m')}"
        
        pipe = self.redis.pipeline()
        pipe.incrbyfloat(hour_key, cost)
        pipe.expire(hour_key, 7200)
        pipe.incrbyfloat(day_key, cost)
        pipe.expire(day_key, 172800)
        pipe.incrbyfloat(month_key, cost)
        pipe.expire(month_key, 2764800)
        pipe.execute()
```

### Post-Incident Improvements

After this incident, the team added:
1. **Per-request cost ceiling**: No single request can cost more than $2
2. **Anomaly detection**: Alert if request rate exceeds 3σ of normal pattern
3. **Retry budget**: Max 3 retries per original request (gateway-enforced, overriding client behavior)
4. **Exponential backoff enforcement**: Gateway adds Retry-After headers, rejects requests that don't respect them

---

## Case Study 4: Semantic Caching Architecture

### Problem

A customer support AI answered ~15,000 queries per day. Analysis showed that 40% of questions were semantically identical ("How do I reset my password?" / "password reset help" / "I forgot my password, what do I do?"). Each redundant call cost $0.03-0.08.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Semantic Cache Layer                            │
│                                                                    │
│  Request → Embed(query) → Search pgvector (cosine > 0.92)        │
│                │                        │                          │
│                │                   ┌────┴────┐                     │
│                │                   │  HIT    │  MISS               │
│                │                   ▼         ▼                     │
│                │            Return cached   Forward to LLM         │
│                │            response        Store response          │
│                │            (avg 45ms)      + embedding in cache    │
│                │                            (avg 2.1s)              │
│                ▼                                                    │
│  Cache Key Factors:                                                │
│  - Query embedding (semantic similarity)                          │
│  - System prompt hash (different contexts = different cache)      │
│  - Model version (cache invalidated on model change)              │
│  - Temperature (only cache temp=0 requests)                       │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# gateway/semantic_cache.py
import numpy as np
from pgvector.asyncpg import register_vector
import asyncpg
import hashlib
import json

class SemanticCache:
    def __init__(self, pool: asyncpg.Pool, embedding_client):
        self.pool = pool
        self.embedding_client = embedding_client
        self.similarity_threshold = 0.92
        self.max_cache_age_seconds = 86400  # 24 hours
    
    async def get(self, messages: list, model: str, temperature: float) -> dict | None:
        # Only cache deterministic requests
        if temperature > 0.1:
            return None
        
        # Create cache context key from system prompt + model
        context_hash = self._context_hash(messages, model)
        
        # Get embedding of the user's query (last user message)
        user_query = self._extract_user_query(messages)
        query_embedding = await self._embed(user_query)
        
        # Search for semantically similar cached queries
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT response, created_at,
                       1 - (embedding <=> $1::vector) as similarity
                FROM semantic_cache
                WHERE context_hash = $2
                  AND created_at > NOW() - INTERVAL '24 hours'
                  AND 1 - (embedding <=> $1::vector) > $3
                ORDER BY similarity DESC
                LIMIT 1
            """, query_embedding, context_hash, self.similarity_threshold)
        
        if row:
            CACHE_HIT.labels(model=model).inc()
            return json.loads(row["response"])
        
        CACHE_MISS.labels(model=model).inc()
        return None
    
    async def put(self, messages: list, model: str, temperature: float, response: dict):
        if temperature > 0.1:
            return
        
        context_hash = self._context_hash(messages, model)
        user_query = self._extract_user_query(messages)
        query_embedding = await self._embed(user_query)
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO semantic_cache (embedding, context_hash, query_text, response, model)
                VALUES ($1::vector, $2, $3, $4, $5)
                ON CONFLICT (context_hash, query_text) DO UPDATE
                SET response = $4, created_at = NOW()
            """, query_embedding, context_hash, user_query,
                json.dumps(response), model)
    
    def _context_hash(self, messages: list, model: str) -> str:
        # Hash system prompt + model to partition cache
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        context = f"{model}:{'|'.join(system_msgs)}"
        return hashlib.sha256(context.encode()).hexdigest()[:16]
    
    def _extract_user_query(self, messages: list) -> str:
        user_msgs = [m for m in messages if m["role"] == "user"]
        return user_msgs[-1]["content"] if user_msgs else ""
    
    async def _embed(self, text: str) -> list[float]:
        response = await self.embedding_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
```

### Results

| Metric | Value |
|--------|-------|
| Cache hit rate | 35.2% |
| Monthly cost before cache | $18,400 |
| Monthly cost after cache | $11,960 |
| Monthly savings | $6,440 (35%) |
| Cache response latency | 45ms avg |
| LLM response latency | 2,100ms avg |
| User-perceived improvement | 35% of queries return 47x faster |

---

## Case Study 5: Rate Limiting Strategy

### Multi-Dimensional Rate Limiting

```python
# gateway/rate_limiter.py
from dataclasses import dataclass

@dataclass
class RateLimitPolicy:
    """Hierarchical rate limits — most restrictive wins"""
    
    # Per-user limits (prevent single user abuse)
    user_rpm: int = 20          # requests per minute
    user_rpd: int = 500         # requests per day
    user_tpm: int = 40_000      # tokens per minute
    
    # Per-team limits (organizational budget control)
    team_rpm: int = 200
    team_rpd: int = 10_000
    team_tpm: int = 500_000
    
    # Per-model limits (protect expensive models)
    model_rpm: int = 1000       # global limit per model
    model_concurrent: int = 50  # max concurrent requests to a model
    
    # Burst handling
    burst_multiplier: float = 2.0  # Allow 2x burst for 10 seconds
    burst_window_seconds: int = 10

RATE_LIMIT_TIERS = {
    "free": RateLimitPolicy(
        user_rpm=5, user_rpd=50, user_tpm=10_000,
        team_rpm=20, team_rpd=200, team_tpm=50_000,
    ),
    "standard": RateLimitPolicy(
        user_rpm=20, user_rpd=500, user_tpm=40_000,
        team_rpm=200, team_rpd=10_000, team_tpm=500_000,
    ),
    "premium": RateLimitPolicy(
        user_rpm=60, user_rpd=2000, user_tpm=150_000,
        team_rpm=600, team_rpd=50_000, team_tpm=2_000_000,
    ),
    "internal": RateLimitPolicy(
        user_rpm=100, user_rpd=10_000, user_tpm=500_000,
        team_rpm=2000, team_rpd=100_000, team_tpm=10_000_000,
    ),
}

class GracefulDegradation:
    """When rate limited, don't just reject — degrade gracefully"""
    
    STRATEGIES = {
        "downgrade_model": {
            "description": "Route to cheaper/faster model instead of rejecting",
            "mapping": {
                "gpt-4-turbo": "gpt-4o-mini",
                "claude-sonnet-4-20250514": "claude-3-5-haiku-20241022",
            }
        },
        "reduce_tokens": {
            "description": "Cap max_tokens to reduce cost",
            "max_tokens_override": 500,
        },
        "queue_request": {
            "description": "Queue for processing when capacity available",
            "max_queue_time_seconds": 30,
        },
        "return_cached": {
            "description": "Return semantically similar cached response",
            "similarity_threshold": 0.88,  # Lower threshold in degraded mode
        },
    }
    
    def apply(self, request: dict, strategy: str) -> dict:
        if strategy == "downgrade_model":
            original = request["model"]
            downgraded = self.STRATEGIES["downgrade_model"]["mapping"].get(original)
            if downgraded:
                request["model"] = downgraded
                request["_metadata"] = {"degraded": True, "original_model": original}
        elif strategy == "reduce_tokens":
            request["max_tokens"] = min(
                request.get("max_tokens", 4096),
                self.STRATEGIES["reduce_tokens"]["max_tokens_override"]
            )
        return request
```

### Rate Limit Response Headers (Actual Production)

```http
HTTP/1.1 200 OK
X-RateLimit-Limit-Requests: 20
X-RateLimit-Remaining-Requests: 14
X-RateLimit-Limit-Tokens: 40000
X-RateLimit-Remaining-Tokens: 32450
X-RateLimit-Reset: 2024-03-15T14:30:00Z
X-Request-Cost-USD: 0.0234
X-Budget-Remaining-USD: 142.87
X-Model-Used: gpt-4-turbo
X-Cache-Status: MISS
```

---

## Case Study 6: Shadow Mode Provider Comparison

### Architecture

A company used shadow mode to evaluate whether switching from GPT-4 to Claude Sonnet would maintain quality. The gateway sent every request to both providers simultaneously, used the primary for the user response, and logged both for offline comparison.

```python
# gateway/shadow_mode.py
import asyncio
from dataclasses import dataclass

@dataclass
class ShadowConfig:
    primary_provider: str
    shadow_provider: str
    sample_rate: float = 0.1  # Shadow 10% of traffic
    compare_dimensions: list = None
    
    def __post_init__(self):
        self.compare_dimensions = self.compare_dimensions or [
            "response_quality",
            "latency",
            "cost",
            "token_count",
        ]

SHADOW_EXPERIMENTS = {
    "claude-vs-gpt4-summarization": ShadowConfig(
        primary_provider="openai/gpt-4-turbo",
        shadow_provider="anthropic/claude-sonnet-4-20250514",
        sample_rate=0.15,
    ),
    "gemini-cost-test": ShadowConfig(
        primary_provider="openai/gpt-4o",
        shadow_provider="google/gemini-1.5-pro",
        sample_rate=0.05,
    ),
}

class ShadowModeRouter:
    async def route(self, experiment: str, request: dict) -> dict:
        config = SHADOW_EXPERIMENTS[experiment]
        
        # Always call primary
        primary_task = asyncio.create_task(
            self._call_provider(config.primary_provider, request)
        )
        
        # Conditionally call shadow (sampled)
        shadow_task = None
        if random.random() < config.sample_rate:
            shadow_task = asyncio.create_task(
                self._call_provider(config.shadow_provider, request)
            )
        
        # Wait for primary (user-facing)
        primary_response = await primary_task
        
        # Don't wait for shadow — fire and forget comparison
        if shadow_task:
            asyncio.create_task(
                self._compare_and_log(experiment, request, primary_task, shadow_task)
            )
        
        return primary_response
    
    async def _compare_and_log(self, experiment, request, primary_task, shadow_task):
        try:
            shadow_response = await asyncio.wait_for(shadow_task, timeout=60)
            primary_response = primary_task.result()
            
            comparison = {
                "experiment": experiment,
                "timestamp": datetime.utcnow().isoformat(),
                "request_hash": hashlib.md5(json.dumps(request).encode()).hexdigest(),
                "primary": {
                    "latency_ms": primary_response.response_ms,
                    "tokens": primary_response.usage.total_tokens,
                    "cost_usd": self._calculate_cost(primary_response),
                },
                "shadow": {
                    "latency_ms": shadow_response.response_ms,
                    "tokens": shadow_response.usage.total_tokens,
                    "cost_usd": self._calculate_cost(shadow_response),
                },
                "primary_response_text": primary_response.choices[0].message.content[:500],
                "shadow_response_text": shadow_response.choices[0].message.content[:500],
            }
            
            # Store for offline quality evaluation
            await self.comparison_store.insert(comparison)
            
        except Exception as e:
            logger.warning(f"Shadow comparison failed: {e}")
```

### Shadow Mode Results After 2 Weeks

```
Experiment: claude-vs-gpt4-summarization
Samples collected: 2,847

Quality (human eval on 200 samples):
  GPT-4 Turbo: 4.2/5.0 average
  Claude Sonnet: 4.4/5.0 average  ← Winner

Latency:
  GPT-4 Turbo: P50=1.8s, P99=8.2s
  Claude Sonnet: P50=1.4s, P99=5.1s  ← Winner

Cost per request:
  GPT-4 Turbo: $0.042 avg
  Claude Sonnet: $0.031 avg  ← Winner (26% cheaper)

Decision: Migrate primary to Claude Sonnet for summarization use case.
```

---

## Case Study 7: Model Version Management

### Version Pinning Strategy

```yaml
# gateway/model_versions.yaml
# Never use "latest" — always pin to specific versions

model_versions:
  production:
    summarization:
      model: "gpt-4-turbo-2024-04-09"
      pinned_since: "2024-04-15"
      eval_score: 0.87
      next_eval_date: "2024-05-15"
    
    classification:
      model: "claude-sonnet-4-20250514"
      pinned_since: "2024-03-01"
      eval_score: 0.92
    
    embeddings:
      model: "text-embedding-3-small"
      pinned_since: "2024-02-01"
      note: "DO NOT change without reindexing 4.2M vectors"

  canary:  # 5% of traffic
    summarization:
      model: "gpt-4o-2024-05-13"
      eval_score: 0.89  # Slightly better — monitoring for 2 weeks
      rollout_start: "2024-05-20"
      auto_promote_if:
        min_requests: 10000
        max_error_rate: 0.001
        min_eval_score: 0.86
        max_latency_p99: 10000

  rollback:
    summarization:
      model: "gpt-4-turbo-2024-01-25"
      note: "Previous stable version"
```

### Canary Deployment Logic

```python
class ModelVersionRouter:
    def get_model_version(self, use_case: str, request_id: str) -> str:
        versions = load_model_versions()
        
        # Deterministic canary assignment based on request_id
        canary_hash = int(hashlib.md5(request_id.encode()).hexdigest()[:8], 16)
        is_canary = (canary_hash % 100) < 5  # 5% canary
        
        if is_canary and use_case in versions["canary"]:
            canary_config = versions["canary"][use_case]
            
            # Check if canary should be auto-promoted
            if self._should_promote(use_case, canary_config):
                self._promote_canary(use_case)
                return versions["production"][use_case]["model"]
            
            # Check if canary should be rolled back
            if self._should_rollback(use_case, canary_config):
                self._rollback_canary(use_case)
                return versions["production"][use_case]["model"]
            
            return canary_config["model"]
        
        return versions["production"][use_case]["model"]
    
    def _should_rollback(self, use_case: str, config: dict) -> bool:
        metrics = self._get_canary_metrics(use_case)
        return (
            metrics.error_rate > 0.005 or  # >0.5% errors
            metrics.latency_p99 > 15000 or  # >15s P99
            metrics.eval_score < 0.80       # Quality dropped
        )
```

---

## Case Study 8: Gateway Observability

### Prometheus Metrics

```python
# gateway/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_TOTAL = Counter(
    "ai_gateway_requests_total",
    "Total requests",
    ["model", "provider", "team", "status", "cache_status"]
)

REQUEST_LATENCY = Histogram(
    "ai_gateway_request_duration_seconds",
    "Request latency",
    ["model", "provider", "team"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

TOKENS_USED = Counter(
    "ai_gateway_tokens_total",
    "Tokens consumed",
    ["model", "provider", "team", "token_type"]  # input/output
)

COST_USD = Counter(
    "ai_gateway_cost_usd_total",
    "Cost in USD",
    ["model", "provider", "team"]
)

# Reliability metrics
FAILOVER_TOTAL = Counter(
    "ai_gateway_failover_total",
    "Failover events",
    ["from_provider", "to_provider", "reason"]
)

CIRCUIT_BREAKER_STATE = Gauge(
    "ai_gateway_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["provider"]
)

# Cache metrics
CACHE_HIT_RATE = Gauge(
    "ai_gateway_cache_hit_rate",
    "Cache hit rate (rolling 5min)",
    ["model"]
)

# Budget metrics
BUDGET_UTILIZATION = Gauge(
    "ai_gateway_budget_utilization_ratio",
    "Budget utilization (0-1)",
    ["team", "window"]  # hour/day/month
)
```

### Grafana Dashboard JSON (Key Panels)

```json
{
  "panels": [
    {
      "title": "Request Rate by Provider",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(rate(ai_gateway_requests_total[5m])) by (provider)",
        "legendFormat": "{{provider}}"
      }]
    },
    {
      "title": "P99 Latency by Model",
      "type": "timeseries",
      "targets": [{
        "expr": "histogram_quantile(0.99, rate(ai_gateway_request_duration_seconds_bucket[5m]))",
        "legendFormat": "{{model}}"
      }]
    },
    {
      "title": "Hourly Cost by Team",
      "type": "barchart",
      "targets": [{
        "expr": "sum(increase(ai_gateway_cost_usd_total[1h])) by (team)",
        "legendFormat": "{{team}}"
      }]
    },
    {
      "title": "Cache Hit Rate",
      "type": "stat",
      "targets": [{
        "expr": "ai_gateway_cache_hit_rate"
      }],
      "thresholds": [
        {"value": 0, "color": "red"},
        {"value": 0.2, "color": "yellow"},
        {"value": 0.3, "color": "green"}
      ]
    },
    {
      "title": "Budget Burn Rate (will budget last the month?)",
      "type": "gauge",
      "targets": [{
        "expr": "ai_gateway_budget_utilization_ratio{window='month'}"
      }]
    }
  ]
}
```

### Alerting Rules

```yaml
# prometheus/alerts/ai_gateway.yml
groups:
  - name: ai_gateway_alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(ai_gateway_requests_total{status="error"}[5m]))
          / sum(rate(ai_gateway_requests_total[5m])) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "AI Gateway error rate >5% for 2 minutes"
          
      - alert: ProviderDown
        expr: ai_gateway_circuit_breaker_state == 2
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker OPEN for {{ $labels.provider }}"
          
      - alert: BudgetExhaustion
        expr: ai_gateway_budget_utilization_ratio{window="month"} > 0.8
        labels:
          severity: warning
        annotations:
          summary: "Team {{ $labels.team }} at 80% monthly budget"
          
      - alert: LatencySpike
        expr: |
          histogram_quantile(0.99, rate(ai_gateway_request_duration_seconds_bucket[5m])) > 15
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency >15s for {{ $labels.model }}"
          
      - alert: CacheHitRateDrop
        expr: ai_gateway_cache_hit_rate < 0.15
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Cache hit rate dropped below 15% — check cache health"
```

---

## Case Study 9: Multi-Region Gateway

### Architecture (Global Financial Services Company)

```
                    ┌─────────────┐
                    │  Cloudflare  │
                    │  Global LB   │
                    └──────┬──────┘
                           │ (latency-based routing)
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  US-East    │  │  EU-West    │  │  APAC       │
   │  Gateway    │  │  Gateway    │  │  Gateway    │
   │             │  │             │  │             │
   │ Azure EUS2  │  │ Azure WEU   │  │ Azure EJAP  │
   │ OpenAI US   │  │ OpenAI EU   │  │ Google APAC │
   └─────────────┘  └─────────────┘  └─────────────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                   ┌──────▼──────┐
                   │ Cross-Region │
                   │ Failover DB  │
                   │ (CockroachDB)│
                   └─────────────┘
```

### Data Residency Routing

```python
# Key requirement: EU user data must NOT leave EU region

class RegionalRouter:
    REGION_PROVIDERS = {
        "eu": {
            "primary": "azure/westeurope/gpt-4-turbo",
            "fallback": "azure/swedencentral/gpt-4-turbo",
            "last_resort": "anthropic/claude-sonnet-4-20250514",  # Anthropic EU endpoint
            # NEVER route to US providers for EU users (GDPR)
        },
        "us": {
            "primary": "openai/gpt-4-turbo",
            "fallback": "azure/eastus2/gpt-4-turbo",
            "last_resort": "azure/westus3/gpt-4-turbo",
        },
        "apac": {
            "primary": "azure/japaneast/gpt-4-turbo",
            "fallback": "google/gemini-1.5-pro",  # Low latency in APAC
            "last_resort": "openai/gpt-4-turbo",  # Accept latency hit
        },
    }
    
    def route(self, user_region: str, request: dict) -> str:
        providers = self.REGION_PROVIDERS[user_region]
        
        for level in ["primary", "fallback", "last_resort"]:
            provider = providers[level]
            if self.is_healthy(provider):
                return provider
        
        # If all regional providers down, check compliance
        if user_region == "eu":
            # Cannot failover to non-EU — return error
            raise RegionalComplianceError("No EU providers available")
        else:
            # Can failover cross-region for non-EU
            return self._find_any_healthy_provider()
```

---

## Case Study 10: Build vs Buy Decision

### Decision Matrix (Actual Evaluation)

| Factor | LiteLLM (OSS) | Portkey (SaaS) | Custom Build |
|--------|---------------|----------------|--------------|
| **Setup time** | 2 days | 30 minutes | 4-8 weeks |
| **Monthly cost (at 1M req/mo)** | $0 (self-hosted) + infra ~$500 | $2,000-5,000 | $0 + eng time |
| **Provider support** | 100+ providers | 30+ providers | Only what you build |
| **Customization** | Moderate (Python) | Limited (config) | Unlimited |
| **Semantic caching** | Basic (Redis) | Built-in | Build yourself |
| **Rate limiting** | Basic | Advanced | Build yourself |
| **Compliance (SOC2)** | Your responsibility | They handle it | Your responsibility |
| **Data residency** | Full control | Check their regions | Full control |
| **Vendor lock-in risk** | Low (OSS) | Medium | None |
| **Maintenance burden** | Medium | Low | High |
| **Observability** | Good (OTel) | Good (dashboard) | Whatever you build |

### When to Choose What

**Choose LiteLLM (or similar OSS) when:**
- You have platform engineering capacity
- Data residency/compliance requirements mean you can't use SaaS
- You need deep customization (custom routing logic, special caching)
- Budget is constrained but you have engineering time
- You're already running Kubernetes

**Choose Portkey/Helicone/etc (SaaS) when:**
- Small team (<5 engineers using AI)
- Speed to market matters more than customization
- You don't want to maintain infrastructure
- Standard rate limiting and caching features are sufficient
- Compliance requirements allow third-party data processing

**Choose Custom Build when:**
- You're at massive scale (>100M requests/month)
- You have unique routing requirements (ML-based routing, custom quality scoring)
- The gateway IS your product (you're building an AI platform)
- You need tight integration with internal systems (auth, billing, compliance)
- You have 2+ dedicated platform engineers for ongoing maintenance

### Real Decision Example

A 50-person startup chose LiteLLM with custom wrappers because:
1. They needed HIPAA compliance (couldn't send PHI through SaaS gateway)
2. They had a platform engineer who could maintain it
3. They needed custom logic: patient context injection before every LLM call
4. Cost: ~$400/month in infrastructure vs $3,000/month for SaaS

They wrapped LiteLLM in a FastAPI service, added their HIPAA-compliant logging (no PHI in logs, audit trail in encrypted DB), and deployed on their existing EKS cluster. Total implementation: 3 weeks.
