# Solution 124: API Management Platform & Developer Portal

## 1. Requirements Clarification

### Functional Requirements
- **API Gateway**: Route, transform, and proxy API requests with plugin architecture
- **Rate Limiting**: Per-key, per-plan throttling with distributed enforcement
- **Authentication**: OAuth2, API keys, JWT validation, mTLS
- **Developer Portal**: Self-service key provisioning, interactive docs, SDKs
- **API Lifecycle**: Versioning, deprecation, traffic migration
- **Analytics & Billing**: Usage metering, per-call billing, plan management

### Non-Functional Requirements
- **Latency**: <5ms added by gateway (p99)
- **Throughput**: 1M+ requests/second
- **Availability**: 99.99% (gateway is on critical path)
- **Scale**: 100K+ developer keys, 10K+ APIs registered
- **Global**: Edge deployment for low-latency worldwide

### Out of Scope
- Service mesh (internal service-to-service)
- Full identity provider (use external IdP)
- CDN/static content delivery

## 2. Capacity Estimation

### Traffic
- 1M requests/second aggregate
- Average request size: 2KB, response: 10KB
- Bandwidth: 2GB/s inbound, 10GB/s outbound
- 100K developer keys, average 10 req/sec per key

### Storage
- API configurations: 10K APIs × 50KB = 500MB
- Developer keys + metadata: 100K × 2KB = 200MB
- Rate limit counters: 100K keys × 100 bytes = 10MB (Redis)
- Analytics events: 1M/sec × 200 bytes × 86400 = 17TB/day
- Billing records: 100K keys × daily aggregate = 100K rows/day

### Compute
- Gateway nodes: 1M RPS ÷ 50K RPS/node = 20 gateway nodes
- Redis (rate limiting): 3 nodes with 32GB RAM each
- Analytics pipeline: 50 Flink task slots
- Portal backend: 5 nodes

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     API MANAGEMENT PLATFORM                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                     EDGE / CDN LAYER                              │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │        │
│  │  │  Edge    │  │  Edge    │  │  Edge    │  │  Edge    │       │        │
│  │  │ US-East  │  │ EU-West  │  │ AP-South │  │ US-West  │       │        │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                              │                                                 │
│                              ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │              API GATEWAY (DATA PLANE)                              │        │
│  │                                                                    │        │
│  │  Request → [Auth] → [Rate Limit] → [Transform] → [Route] →      │        │
│  │           → [Backend] → [Response Transform] → [Log] → Response  │        │
│  │                                                                    │        │
│  │  ┌────────────────────────────────────────────────────────┐      │        │
│  │  │              Plugin Chain (per-route)                    │      │        │
│  │  └────────────────────────────────────────────────────────┘      │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                              │                                                 │
│              ┌───────────────┼───────────────────┐                            │
│              ▼               ▼                   ▼                            │
│  ┌──────────────┐  ┌──────────────┐    ┌──────────────┐                     │
│  │   Control    │  │    Redis     │    │   Backend    │                     │
│  │    Plane     │  │ (Rate Limit  │    │   Services   │                     │
│  │  (Config)    │  │  + Cache)    │    │              │                     │
│  └──────┬───────┘  └──────────────┘    └──────────────┘                     │
│         │                                                                     │
│         ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                    CONTROL PLANE                                    │        │
│  │  ┌───────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐     │        │
│  │  │ API Config│ │Developer │ │  Analytics  │ │   Billing    │     │        │
│  │  │  Manager  │ │  Portal  │ │  Pipeline   │ │   Engine     │     │        │
│  │  └───────────┘ └──────────┘ └────────────┘ └──────────────┘     │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 4. Detailed Design

### 4.1 Gateway Plugin Architecture

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import time
import asyncio

@dataclass
class GatewayRequest:
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: bytes
    client_ip: str
    timestamp: float
    
    # Set by plugins
    api_key: Optional[str] = None
    developer_id: Optional[str] = None
    plan_id: Optional[str] = None
    authenticated: bool = False
    route: Optional['RouteConfig'] = None

@dataclass 
class GatewayResponse:
    status_code: int
    headers: Dict[str, str]
    body: bytes
    
    # Metadata
    backend_latency_ms: float = 0
    total_latency_ms: float = 0

class Plugin(ABC):
    """Base class for gateway plugins."""
    
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def phase(self) -> str:
        """Which phase: 'access', 'request', 'response', 'log'"""
        pass
    
    @abstractmethod
    async def execute(self, request: GatewayRequest, 
                      response: Optional[GatewayResponse] = None) -> Optional[GatewayResponse]:
        """
        Execute plugin logic.
        Return GatewayResponse to short-circuit (e.g., 429 rate limit).
        Return None to continue chain.
        """
        pass


class PluginChain:
    """Executes plugins in order for each request phase."""
    
    def __init__(self, plugins: List[Plugin]):
        self.access_plugins = [p for p in plugins if p.phase() == "access"]
        self.request_plugins = [p for p in plugins if p.phase() == "request"]
        self.response_plugins = [p for p in plugins if p.phase() == "response"]
        self.log_plugins = [p for p in plugins if p.phase() == "log"]
    
    async def execute_request(self, request: GatewayRequest) -> GatewayResponse:
        """Full request lifecycle through plugin chain."""
        start = time.monotonic()
        
        # Phase 1: Access (auth, rate limit)
        for plugin in self.access_plugins:
            result = await plugin.execute(request)
            if result:  # Short-circuit
                return result
        
        # Phase 2: Request transform
        for plugin in self.request_plugins:
            await plugin.execute(request)
        
        # Phase 3: Proxy to backend
        response = await self._proxy_to_backend(request)
        
        # Phase 4: Response transform
        for plugin in self.response_plugins:
            await plugin.execute(request, response)
        
        # Phase 5: Logging (non-blocking)
        response.total_latency_ms = (time.monotonic() - start) * 1000
        asyncio.create_task(self._run_log_plugins(request, response))
        
        return response
    
    async def _proxy_to_backend(self, request: GatewayRequest) -> GatewayResponse:
        """Route request to appropriate backend service."""
        backend = request.route.backend
        
        backend_start = time.monotonic()
        # Use connection pool for backend
        async with self.connection_pool.get(backend.host) as conn:
            resp = await conn.request(
                method=request.method,
                path=request.route.rewrite_path(request.path),
                headers=request.headers,
                body=request.body,
                timeout=request.route.timeout_ms / 1000
            )
        
        backend_latency = (time.monotonic() - backend_start) * 1000
        
        return GatewayResponse(
            status_code=resp.status,
            headers=dict(resp.headers),
            body=await resp.read(),
            backend_latency_ms=backend_latency
        )


class AuthPlugin(Plugin):
    """Authentication plugin supporting multiple auth methods."""
    
    def name(self) -> str:
        return "authentication"
    
    def phase(self) -> str:
        return "access"
    
    def __init__(self, key_store, jwt_validator):
        self.key_store = key_store
        self.jwt_validator = jwt_validator
    
    async def execute(self, request: GatewayRequest, 
                      response=None) -> Optional[GatewayResponse]:
        route = request.route
        
        if not route.auth_required:
            return None
        
        auth_method = route.auth_method
        
        if auth_method == "api_key":
            return await self._validate_api_key(request)
        elif auth_method == "jwt":
            return await self._validate_jwt(request)
        elif auth_method == "oauth2":
            return await self._validate_oauth2(request)
        
        return self._unauthorized("No auth method configured")
    
    async def _validate_api_key(self, request: GatewayRequest):
        # Check header, query param, or body
        api_key = (
            request.headers.get("X-API-Key") or
            request.query_params.get("api_key")
        )
        
        if not api_key:
            return self._unauthorized("Missing API key")
        
        # Lookup key (Redis cache + DB fallback)
        key_data = await self.key_store.get(api_key)
        
        if not key_data:
            return self._unauthorized("Invalid API key")
        
        if key_data.revoked:
            return self._unauthorized("API key revoked")
        
        if key_data.expires_at and key_data.expires_at < time.time():
            return self._unauthorized("API key expired")
        
        # Enrich request with key metadata
        request.api_key = api_key
        request.developer_id = key_data.developer_id
        request.plan_id = key_data.plan_id
        request.authenticated = True
        
        return None  # Continue chain
    
    async def _validate_jwt(self, request: GatewayRequest):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return self._unauthorized("Missing Bearer token")
        
        token = auth_header[7:]
        claims = self.jwt_validator.validate(token)
        
        if not claims:
            return self._unauthorized("Invalid token")
        
        request.developer_id = claims.get("sub")
        request.authenticated = True
        return None
    
    def _unauthorized(self, message: str) -> GatewayResponse:
        return GatewayResponse(
            status_code=401,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "unauthorized", "message": message}).encode()
        )
```

### 4.2 Rate Limiting Implementation

```python
import redis.asyncio as redis
import time
import math

class RateLimitPlugin(Plugin):
    """
    Distributed rate limiting using Redis.
    
    Supports:
    - Token bucket (smooth rate with burst)
    - Sliding window (precise counting)
    - Quota (daily/monthly limits with reset)
    """
    
    def name(self) -> str:
        return "rate_limit"
    
    def phase(self) -> str:
        return "access"
    
    def __init__(self, redis_client: redis.Redis, config_store):
        self.redis = redis_client
        self.config_store = config_store
    
    async def execute(self, request: GatewayRequest, 
                      response=None) -> Optional[GatewayResponse]:
        
        if not request.authenticated:
            return None  # Auth plugin handles unauthenticated
        
        # Get rate limit config for this key's plan
        plan = await self.config_store.get_plan(request.plan_id)
        
        # Check per-second rate limit (token bucket)
        allowed, remaining, reset_at = await self._token_bucket_check(
            key=f"rl:{request.api_key}:sec",
            rate=plan.requests_per_second,
            burst=plan.burst_size
        )
        
        if not allowed:
            return self._rate_limited(remaining, reset_at)
        
        # Check daily quota
        quota_allowed, quota_remaining = await self._quota_check(
            key=f"quota:{request.api_key}:daily",
            limit=plan.daily_quota,
            window="day"
        )
        
        if not quota_allowed:
            return self._quota_exceeded(quota_remaining)
        
        # Set rate limit headers on response (handled in response phase)
        request.headers["X-RateLimit-Remaining"] = str(remaining)
        request.headers["X-RateLimit-Reset"] = str(reset_at)
        
        return None
    
    async def _token_bucket_check(self, key: str, rate: int, burst: int) -> tuple:
        """
        Token bucket algorithm in Redis (atomic via Lua script).
        
        - Tokens replenish at `rate` per second
        - Bucket holds max `burst` tokens
        - Each request consumes 1 token
        """
        now = time.time()
        
        # Lua script for atomic token bucket
        lua_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local burst = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])
        
        local data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1])
        local last_refill = tonumber(data[2])
        
        if tokens == nil then
            tokens = burst
            last_refill = now
        end
        
        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        local new_tokens = elapsed * rate
        tokens = math.min(burst, tokens + new_tokens)
        
        local allowed = 0
        local remaining = tokens
        
        if tokens >= cost then
            tokens = tokens - cost
            allowed = 1
            remaining = tokens
        end
        
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, math.ceil(burst / rate) + 1)
        
        return {allowed, math.floor(remaining), math.ceil((burst - remaining) / rate)}
        """
        
        result = await self.redis.eval(lua_script, 1, key, rate, burst, now, 1)
        allowed = result[0] == 1
        remaining = result[1]
        reset_at = int(now) + result[2]
        
        return allowed, remaining, reset_at
    
    async def _quota_check(self, key: str, limit: int, window: str) -> tuple:
        """Daily/monthly quota check using Redis INCR with expiry."""
        
        if window == "day":
            # Key expires at end of day UTC
            ttl = self._seconds_until_midnight()
        elif window == "month":
            ttl = self._seconds_until_month_end()
        
        current = await self.redis.incr(key)
        
        if current == 1:
            await self.redis.expire(key, ttl)
        
        remaining = max(0, limit - current)
        allowed = current <= limit
        
        return allowed, remaining
    
    def _rate_limited(self, remaining: int, reset_at: int) -> GatewayResponse:
        return GatewayResponse(
            status_code=429,
            headers={
                "Content-Type": "application/json",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(reset_at - int(time.time()))
            },
            body=json.dumps({
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after": reset_at - int(time.time())
            }).encode()
        )
    
    def _quota_exceeded(self, remaining: int) -> GatewayResponse:
        return GatewayResponse(
            status_code=429,
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "error": "quota_exceeded",
                "message": "Daily API quota exceeded. Upgrade your plan for higher limits."
            }).encode()
        )


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter for more precise counting.
    Uses Redis sorted sets with timestamps as scores.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check(self, key: str, limit: int, window_seconds: int) -> tuple:
        now = time.time()
        window_start = now - window_seconds
        
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {f"{now}:{id(object())}": now})
        
        # Set expiry
        pipe.expire(key, window_seconds + 1)
        
        results = await pipe.execute()
        current_count = results[1]
        
        allowed = current_count < limit
        remaining = max(0, limit - current_count - 1)
        
        if not allowed:
            # Remove the entry we just added
            await self.redis.zremrangebyscore(key, now, now)
        
        return allowed, remaining
```

### 4.3 API Lifecycle Management

```python
from enum import Enum
from datetime import datetime, timedelta

class APIVersionState(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    RETIRED = "retired"

class APILifecycleManager:
    """
    Manages API versions through their lifecycle.
    Handles versioning, deprecation, and traffic migration.
    """
    
    def __init__(self, config_store, notification_service):
        self.config_store = config_store
        self.notifications = notification_service
    
    async def publish_version(self, api_id: str, version: str, spec: dict):
        """Publish a new API version."""
        api = await self.config_store.get_api(api_id)
        
        # Validate backward compatibility with previous version
        if api.current_version:
            compatibility = self._check_backward_compatibility(
                old_spec=api.versions[api.current_version].spec,
                new_spec=spec
            )
            if not compatibility.is_compatible:
                raise IncompatibleVersionError(compatibility.breaking_changes)
        
        # Create version
        version_config = APIVersion(
            version=version,
            spec=spec,
            state=APIVersionState.PUBLISHED,
            published_at=datetime.utcnow()
        )
        
        api.versions[version] = version_config
        api.current_version = version
        await self.config_store.save_api(api)
        
        # Notify consumers
        await self.notifications.notify_api_consumers(
            api_id=api_id,
            event="new_version",
            version=version
        )
    
    async def deprecate_version(self, api_id: str, version: str, 
                                sunset_date: datetime, migration_guide: str):
        """Mark version as deprecated with sunset date."""
        api = await self.config_store.get_api(api_id)
        ver = api.versions[version]
        
        ver.state = APIVersionState.DEPRECATED
        ver.sunset_date = sunset_date
        ver.migration_guide = migration_guide
        ver.deprecated_at = datetime.utcnow()
        
        await self.config_store.save_api(api)
        
        # Notify all developers using this version
        consumers = await self.config_store.get_version_consumers(api_id, version)
        await self.notifications.notify_deprecation(
            consumers=consumers,
            api_id=api_id,
            version=version,
            sunset_date=sunset_date,
            migration_guide=migration_guide
        )
    
    async def retire_version(self, api_id: str, version: str):
        """Fully retire a version (returns 410 Gone)."""
        api = await self.config_store.get_api(api_id)
        ver = api.versions[version]
        
        if ver.state != APIVersionState.DEPRECATED:
            raise InvalidTransitionError("Must deprecate before retiring")
        
        if datetime.utcnow() < ver.sunset_date:
            raise PrematureRetirementError(f"Sunset date {ver.sunset_date} not reached")
        
        ver.state = APIVersionState.RETIRED
        ver.retired_at = datetime.utcnow()
        await self.config_store.save_api(api)
    
    def _check_backward_compatibility(self, old_spec: dict, new_spec: dict) -> 'CompatibilityResult':
        """Check OpenAPI specs for breaking changes."""
        breaking_changes = []
        
        old_paths = old_spec.get("paths", {})
        new_paths = new_spec.get("paths", {})
        
        # Check for removed endpoints
        for path in old_paths:
            if path not in new_paths:
                breaking_changes.append(f"Removed endpoint: {path}")
            else:
                for method in old_paths[path]:
                    if method not in new_paths[path]:
                        breaking_changes.append(f"Removed method: {method} {path}")
        
        # Check for removed/required fields
        # ... (detailed schema comparison)
        
        return CompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes
        )


class VersionRouter:
    """
    Routes requests to appropriate API version based on:
    - URL path (/v1/resource, /v2/resource)
    - Header (Accept-Version: 2)
    - Query param (?version=2)
    """
    
    def __init__(self, config_store):
        self.config_store = config_store
    
    async def resolve_version(self, request: GatewayRequest, api_config) -> str:
        """Determine which version to route to."""
        
        versioning = api_config.versioning_strategy
        
        if versioning == "url":
            # Extract from path: /v2/users → version "2"
            match = re.match(r'/v(\d+)/', request.path)
            if match:
                return match.group(1)
        
        elif versioning == "header":
            return request.headers.get("Accept-Version", api_config.default_version)
        
        elif versioning == "query":
            return request.query_params.get("version", api_config.default_version)
        
        return api_config.default_version
    
    def add_deprecation_headers(self, response: GatewayResponse, version_config):
        """Add sunset/deprecation headers to response."""
        if version_config.state == APIVersionState.DEPRECATED:
            response.headers["Deprecation"] = version_config.deprecated_at.isoformat()
            response.headers["Sunset"] = version_config.sunset_date.isoformat()
            response.headers["Link"] = f'<{version_config.migration_guide}>; rel="successor-version"'
```

### 4.4 Developer Portal Backend

```python
class DeveloperPortalService:
    """
    Self-service portal for API consumers.
    Handles: key management, docs, sandbox, usage dashboards.
    """
    
    def __init__(self, db, redis_client, billing_service):
        self.db = db
        self.redis = redis_client
        self.billing = billing_service
    
    async def create_api_key(self, developer_id: str, plan_id: str, 
                             name: str, scopes: list) -> dict:
        """Generate new API key for developer."""
        import secrets
        
        # Generate secure key
        key_prefix = "sk_live_"  # or "sk_test_" for sandbox
        key_value = key_prefix + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        
        # Store (we only store hash, developer sees key once)
        api_key = APIKey(
            id=str(uuid.uuid4()),
            developer_id=developer_id,
            plan_id=plan_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_value[:12],  # For identification
            scopes=scopes,
            created_at=datetime.utcnow()
        )
        
        await self.db.save(api_key)
        
        # Cache in Redis for fast gateway lookups
        await self.redis.hset(f"apikey:{key_hash}", mapping={
            "developer_id": developer_id,
            "plan_id": plan_id,
            "scopes": json.dumps(scopes),
            "created_at": api_key.created_at.isoformat()
        })
        await self.redis.expire(f"apikey:{key_hash}", 3600)
        
        return {
            "key_id": api_key.id,
            "api_key": key_value,  # Only shown once!
            "prefix": key_value[:12],
            "name": name,
            "plan": plan_id,
            "message": "Store this key securely. It won't be shown again."
        }
    
    async def rotate_api_key(self, developer_id: str, key_id: str, 
                             grace_period_hours: int = 24) -> dict:
        """
        Rotate API key with grace period.
        Old key works during grace period for zero-downtime migration.
        """
        old_key = await self.db.get_key(key_id)
        if old_key.developer_id != developer_id:
            raise PermissionError()
        
        # Create new key
        new_key_result = await self.create_api_key(
            developer_id=developer_id,
            plan_id=old_key.plan_id,
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes
        )
        
        # Mark old key as expiring
        old_key.expires_at = datetime.utcnow() + timedelta(hours=grace_period_hours)
        await self.db.save(old_key)
        
        return {
            "new_key": new_key_result,
            "old_key_expires_at": old_key.expires_at.isoformat(),
            "grace_period_hours": grace_period_hours
        }
    
    async def get_usage_dashboard(self, developer_id: str, 
                                   period: str = "7d") -> dict:
        """Get usage statistics for developer dashboard."""
        
        # Query ClickHouse for aggregated usage
        usage = await self.analytics.query(f"""
            SELECT
                toStartOfHour(timestamp) as hour,
                api_name,
                count() as requests,
                countIf(status_code >= 400) as errors,
                avg(latency_ms) as avg_latency,
                quantile(0.99)(latency_ms) as p99_latency
            FROM api_usage
            WHERE developer_id = '{developer_id}'
                AND timestamp > now() - interval {period}
            GROUP BY hour, api_name
            ORDER BY hour DESC
        """)
        
        # Get quota status
        keys = await self.db.get_developer_keys(developer_id)
        quota_status = []
        for key in keys:
            used = await self.redis.get(f"quota:{key.key_hash}:daily")
            plan = await self.db.get_plan(key.plan_id)
            quota_status.append({
                "key_prefix": key.key_prefix,
                "daily_used": int(used or 0),
                "daily_limit": plan.daily_quota,
                "percentage": int(used or 0) / plan.daily_quota * 100
            })
        
        return {
            "usage_by_hour": usage,
            "quota_status": quota_status,
            "total_requests_period": sum(u["requests"] for u in usage),
            "error_rate": sum(u["errors"] for u in usage) / max(1, sum(u["requests"] for u in usage))
        }
```

### 4.5 Usage Metering & Billing

```python
class UsageMeteringService:
    """
    Tracks API usage for billing purposes.
    
    Architecture:
    - Gateway emits usage events to Kafka
    - Flink aggregates per (developer, api, hour)
    - Billing engine generates invoices from aggregates
    """
    
    def __init__(self, kafka_producer, billing_db):
        self.kafka = kafka_producer
        self.billing_db = billing_db
    
    async def record_usage(self, request: GatewayRequest, 
                           response: GatewayResponse):
        """Emit usage event (called from gateway log plugin)."""
        event = {
            "developer_id": request.developer_id,
            "api_key": request.api_key[:12],  # prefix only
            "api_name": request.route.api_name,
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "request_bytes": len(request.body),
            "response_bytes": len(response.body),
            "latency_ms": response.total_latency_ms,
            "timestamp": time.time()
        }
        
        await self.kafka.send("api-usage-events", 
                             key=request.developer_id.encode(),
                             value=json.dumps(event).encode())
    
    async def generate_invoice(self, developer_id: str, period: str) -> dict:
        """Generate monthly invoice from usage aggregates."""
        
        # Get developer's plan
        developer = await self.billing_db.get_developer(developer_id)
        plan = await self.billing_db.get_plan(developer.plan_id)
        
        # Get usage aggregates for period
        usage = await self.billing_db.get_usage_aggregates(developer_id, period)
        
        line_items = []
        total = plan.base_price  # Monthly base fee
        
        line_items.append({
            "description": f"{plan.name} Plan - Monthly Base",
            "amount": plan.base_price
        })
        
        # Overage charges
        total_calls = sum(u.request_count for u in usage)
        included_calls = plan.included_requests
        
        if total_calls > included_calls:
            overage = total_calls - included_calls
            overage_cost = overage * plan.overage_rate_per_call
            total += overage_cost
            line_items.append({
                "description": f"Overage: {overage:,} calls × ${plan.overage_rate_per_call}",
                "amount": overage_cost
            })
        
        # Data transfer charges
        total_data_gb = sum(u.response_bytes for u in usage) / (1024**3)
        if total_data_gb > plan.included_data_gb:
            data_overage = total_data_gb - plan.included_data_gb
            data_cost = data_overage * plan.data_rate_per_gb
            total += data_cost
            line_items.append({
                "description": f"Data transfer: {data_overage:.2f} GB × ${plan.data_rate_per_gb}",
                "amount": data_cost
            })
        
        return {
            "developer_id": developer_id,
            "period": period,
            "plan": plan.name,
            "line_items": line_items,
            "total": total,
            "usage_summary": {
                "total_requests": total_calls,
                "total_data_gb": total_data_gb,
                "unique_apis": len(set(u.api_name for u in usage))
            }
        }
```

## 5. Data Model

### Entity-Relationship Diagram

```mermaid
erDiagram
    TEAMS {
        uuid id PK
        string name
    }
    APIS {
        uuid id PK
        uuid owner_team_id FK
        string name
        string base_path
        string state
    }
    API_VERSIONS {
        uuid id PK
        uuid api_id FK
        string version
        string state
        jsonb openapi_spec
    }
    API_ROUTES {
        uuid id PK
        uuid api_id FK
        string method
        string path_pattern
        string backend_service
    }
    DEVELOPERS {
        uuid id PK
        string email
        uuid plan_id FK
        string state
    }
    API_KEYS {
        uuid id PK
        uuid developer_id FK
        uuid plan_id FK
        string key_hash
        boolean revoked
    }
    PLANS {
        uuid id PK
        string name
        int requests_per_second
        int daily_quota
        decimal base_price
    }
    USAGE_AGGREGATES {
        bigint id PK
        uuid developer_id FK
        string api_name
        bigint request_count
        timestamp period_start
    }

    TEAMS ||--o{ APIS : owns
    APIS ||--o{ API_VERSIONS : has
    APIS ||--o{ API_ROUTES : defines
    DEVELOPERS ||--o{ API_KEYS : creates
    PLANS ||--o{ API_KEYS : governs
    PLANS ||--o{ DEVELOPERS : subscribed_to
    DEVELOPERS ||--o{ USAGE_AGGREGATES : tracked_in
```

### Database Schema (PostgreSQL)

```sql
-- APIs
CREATE TABLE apis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    description TEXT,
    owner_team_id UUID NOT NULL REFERENCES teams(id),
    
    -- Versioning
    versioning_strategy VARCHAR(20) DEFAULT 'url',  -- 'url', 'header', 'query'
    current_version VARCHAR(20),
    
    -- Configuration
    base_path VARCHAR(255) NOT NULL,
    backend_url VARCHAR(500) NOT NULL,
    timeout_ms INT DEFAULT 30000,
    
    -- Status
    state VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_apis_name ON apis(name);
CREATE INDEX idx_apis_state ON apis(state);

-- API Versions
CREATE TABLE api_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_id UUID NOT NULL REFERENCES apis(id),
    version VARCHAR(20) NOT NULL,
    
    state VARCHAR(20) NOT NULL DEFAULT 'draft',
    openapi_spec JSONB NOT NULL,
    
    published_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    sunset_date TIMESTAMP,
    retired_at TIMESTAMP,
    migration_guide TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(api_id, version)
);

CREATE INDEX idx_versions_api ON api_versions(api_id, state);

-- Route configurations
CREATE TABLE api_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_id UUID NOT NULL REFERENCES apis(id),
    version VARCHAR(20),
    
    method VARCHAR(10) NOT NULL,
    path_pattern VARCHAR(500) NOT NULL,
    
    -- Backend routing
    backend_service VARCHAR(255) NOT NULL,
    backend_path VARCHAR(500),
    
    -- Plugin configuration for this route
    plugins JSONB DEFAULT '[]',
    
    -- Auth
    auth_required BOOLEAN DEFAULT TRUE,
    auth_method VARCHAR(20) DEFAULT 'api_key',
    required_scopes TEXT[] DEFAULT '{}',
    
    -- Rate limiting override
    rate_limit_override JSONB,
    
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_routes_api ON api_routes(api_id, enabled);
CREATE INDEX idx_routes_path ON api_routes(method, path_pattern);

-- Developers
CREATE TABLE developers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    company VARCHAR(255),
    
    -- Plan
    plan_id UUID REFERENCES plans(id),
    
    -- Status
    state VARCHAR(20) DEFAULT 'active',
    verified BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id UUID NOT NULL REFERENCES developers(id),
    plan_id UUID NOT NULL REFERENCES plans(id),
    
    name VARCHAR(255),
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(12) NOT NULL,
    
    scopes TEXT[] DEFAULT '{}',
    
    -- Status
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP,
    expires_at TIMESTAMP,
    
    -- Rate limit overrides
    custom_rate_limit JSONB,
    
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_keys_developer ON api_keys(developer_id);
CREATE INDEX idx_keys_prefix ON api_keys(key_prefix);

-- Plans (pricing tiers)
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    
    -- Rate limits
    requests_per_second INT NOT NULL,
    burst_size INT NOT NULL,
    daily_quota INT NOT NULL,
    monthly_quota INT,
    
    -- Pricing
    base_price DECIMAL(10,2) DEFAULT 0,
    included_requests INT DEFAULT 0,
    overage_rate_per_call DECIMAL(10,6) DEFAULT 0,
    included_data_gb DECIMAL(10,2) DEFAULT 0,
    data_rate_per_gb DECIMAL(10,4) DEFAULT 0,
    
    -- Features
    features JSONB DEFAULT '{}',
    
    sort_order INT DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Usage aggregates (for billing)
CREATE TABLE usage_aggregates (
    id BIGSERIAL PRIMARY KEY,
    developer_id UUID NOT NULL,
    api_key_prefix VARCHAR(12) NOT NULL,
    api_name VARCHAR(255) NOT NULL,
    
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    
    request_count BIGINT DEFAULT 0,
    error_count BIGINT DEFAULT 0,
    request_bytes BIGINT DEFAULT 0,
    response_bytes BIGINT DEFAULT 0,
    avg_latency_ms DECIMAL(10,2),
    
    UNIQUE(developer_id, api_name, period_start)
) PARTITION BY RANGE (period_start);

CREATE INDEX idx_usage_developer ON usage_aggregates(developer_id, period_start DESC);
```

### ClickHouse Schema (Real-time Analytics)

```sql
CREATE TABLE api_usage (
    developer_id String,
    api_key_prefix String,
    api_name String,
    method String,
    path String,
    status_code UInt16,
    request_bytes UInt32,
    response_bytes UInt32,
    latency_ms Float32,
    timestamp DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (developer_id, api_name, timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

## 6. API Design

### Key Management

```
POST /v1/portal/keys
Authorization: Bearer <developer_token>

Request:
{
    "name": "Production Key",
    "scopes": ["read:users", "write:orders"],
    "plan_id": "plan_pro"
}

Response (201 Created):
{
    "key_id": "key_abc123",
    "api_key": "sk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "prefix": "sk_live_a1b2",
    "name": "Production Key",
    "plan": "Pro",
    "rate_limit": "100 req/sec",
    "daily_quota": 100000,
    "created_at": "2024-01-15T10:00:00Z",
    "warning": "Store this key securely. It cannot be retrieved again."
}
```

### Gateway Request Flow

```
# Client request
GET /v2/users/123
Host: api.platform.com
X-API-Key: sk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Gateway response
HTTP/1.1 200 OK
Content-Type: application/json
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705312800
X-Request-ID: req_xyz789
X-Response-Time: 45ms

{
    "id": "123",
    "name": "John Doe",
    "email": "john@example.com"
}
```

### Analytics API

```
GET /v1/portal/analytics?period=7d&granularity=hour
Authorization: Bearer <developer_token>

Response (200 OK):
{
    "period": "2024-01-08 to 2024-01-15",
    "summary": {
        "total_requests": 2847293,
        "total_errors": 1423,
        "error_rate": 0.0005,
        "avg_latency_ms": 45.2,
        "p99_latency_ms": 210.5,
        "unique_apis": 8
    },
    "time_series": [
        {
            "timestamp": "2024-01-15T10:00:00Z",
            "requests": 42150,
            "errors": 21,
            "avg_latency_ms": 43.1
        }
    ],
    "by_api": [
        {
            "api": "users-api",
            "requests": 1200000,
            "error_rate": 0.001,
            "avg_latency_ms": 38.5
        }
    ],
    "quota_usage": {
        "daily_used": 85000,
        "daily_limit": 100000,
        "percentage": 85
    }
}
```

## 7. Scalability & Performance

### Gateway Performance
- **Zero-copy proxying**: Stream request/response without full buffering
- **Connection pooling**: Persistent connections to backends (HTTP/2 multiplexing)
- **Plugin caching**: Auth results cached for 60s, rate limit state in Redis
- **Config hot-reload**: Route config changes applied without restart (shared memory)

### Horizontal Scaling
- Gateway nodes are stateless → scale horizontally behind load balancer
- Redis cluster for distributed rate limiting (6 nodes, 3 masters + 3 replicas)
- ClickHouse cluster for analytics (sharded by developer_id)

### Edge Deployment
- Gateway deployed at CDN edge locations for lowest latency
- Config pushed to edge via CDC (control plane → edge cache)
- Rate limiting: local token bucket + async sync to Redis (slightly overshoot allowed)

## 8. Reliability & Fault Tolerance

### Gateway HA
- Active-active deployment across AZs
- Health check from load balancer (unhealthy nodes removed in <10s)
- Graceful degradation: if Redis unavailable, allow requests (log for later billing)
- Circuit breaker per backend service

### Rate Limiting During Failures
- **Redis down**: Fall back to in-memory per-node rate limiting (less precise but safe)
- **Gateway restart**: Rate limit state in Redis survives gateway restarts
- **Split brain**: Slight overshoot acceptable (better than blocking legitimate traffic)

### Data Durability
- Usage events: Kafka with replication factor 3
- Billing aggregates: PostgreSQL with streaming replication
- API keys: Encrypted at rest, hash-only storage

## 9. Monitoring & Observability

### Key Metrics
| Metric | Target | Alert |
|--------|--------|-------|
| Gateway latency (added) p99 | <5ms | >15ms |
| Gateway error rate (5xx) | <0.01% | >0.1% |
| Rate limit accuracy | ±5% | ±20% |
| Config propagation time | <5s | >30s |
| Key validation latency | <1ms | >5ms |
| Analytics pipeline lag | <5min | >30min |

### Kafka Configuration

```properties
# API usage events
api.usage.topic=api-usage-events
api.usage.partitions=24
api.usage.replication.factor=3
api.usage.retention.ms=604800000  # 7 days
api.usage.compression.type=lz4

# Config changes
api.config.topic=api-config-changes
api.config.partitions=6
api.config.replication.factor=3
api.config.cleanup.policy=compact
```

### Redis Configuration

```
# Rate limiting cluster
cluster-enabled yes
cluster-node-timeout 5000
maxmemory 16gb
maxmemory-policy allkeys-lru

# Key patterns:
# rl:{key_hash}:sec - token bucket state (HASH: tokens, last_refill)
# quota:{key_hash}:daily - daily counter (STRING with TTL)
# apikey:{key_hash} - key metadata cache (HASH)
```

## 10. Trade-offs & Alternatives

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Rate limit algorithm | Token bucket | Sliding window | Better burst handling, simpler Redis ops |
| Rate limit storage | Redis | In-memory only | Distributed enforcement across gateway nodes |
| Auth cache | Redis + local cache | DB per request | Sub-ms validation on hot path |
| Analytics | Kafka → ClickHouse | Direct DB writes | Handles 1M events/sec without gateway impact |
| API spec format | OpenAPI 3.x | Custom format | Industry standard, tooling ecosystem |
| Versioning | URL-based default | Header only | Most intuitive for developers |
| Key format | Random token | JWT-based keys | Simpler, revocable without crypto overhead |

### Key Trade-offs
1. **Latency vs Accuracy (Rate Limiting)**: Local token bucket is fast but slightly imprecise vs fully synchronized but adds latency
2. **Security vs Performance**: Validating JWT signatures adds ~1ms vs pre-hashed API key lookup
3. **Developer UX vs Security**: Showing key once (secure) vs allowing retrieval (convenient)
4. **Flexibility vs Complexity**: Plugin architecture is powerful but harder to debug

## 11. Unique Considerations

### OpenAPI Spec Integration
- Auto-generate route configs from OpenAPI specs
- Validate incoming requests against schema (optional plugin)
- Generate client SDKs from specs (Node.js, Python, Go, Java)
- Keep docs always in sync with actual API behavior

### Sandbox Environment
- Separate sandbox keys (prefix: `sk_test_`)
- Sandbox backends return mock data
- No rate limits in sandbox (but track usage for testing)
- Sandbox → Production promotion workflow

### API Marketplace
- Third-party APIs can be published (with revenue sharing)
- Subscription management per API
- API quality scoring (uptime, latency, documentation quality)
- Developer reviews and ratings

### DDoS Protection
- Layer 7 DDoS detection at gateway level
- Automatic rate limiting escalation during attacks
- IP reputation scoring integrated with rate limiting
- Challenge-response for suspicious traffic patterns (not for API clients)

---

## Sequence Diagrams

### 1. API Call Through Gateway

```mermaid
sequenceDiagram
    participant Dev as Developer App
    participant GW as API Gateway
    participant Cache as Response Cache
    participant RL as Rate Limiter
    participant Auth as Auth/Key Validation
    participant Transform as Request Transform
    participant Backend as Backend API
    participant Analytics as Analytics Pipeline

    Dev->>GW: GET /v2/products/123 (x-api-key: ak_prod_xxx)

    GW->>Auth: Validate API key
    Auth->>Auth: Lookup key → {app_id, plan: gold, scopes: [products.read]}
    Auth-->>GW: Valid {app_id: A1, plan: gold, rate: 1000/min}

    GW->>RL: Check rate limit {app_id: A1, plan: gold}
    RL-->>GW: Allowed (remaining: 847/1000)

    GW->>Cache: Check response cache {key: GET:/v2/products/123}
    alt Cache hit (< max-age)
        Cache-->>GW: Cached response (age: 45s)
        GW-->>Dev: 200 OK (X-Cache: HIT, X-RateLimit-Remaining: 847)
    else Cache miss
        GW->>Transform: Apply request policies (add internal headers, strip sensitive params)
        Transform->>Backend: GET /internal/products/123 (X-App-Id: A1, X-Request-Id: uuid)
        Backend-->>Transform: 200 {product data}
        Transform->>Transform: Response transform (filter fields per plan tier)
        Transform->>Cache: Store response (TTL from Cache-Control)
        Transform-->>GW: Transformed response
        GW-->>Dev: 200 OK (X-Cache: MISS, X-RateLimit-Remaining: 847)
    end

    GW--)Analytics: Async log {app_id, endpoint, latency, status, bytes}
```

### 2. Developer API Key Provisioning

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Portal as Developer Portal
    participant Auth as Auth Service (OAuth)
    participant KMS as Key Management
    participant DB as Portal DB
    participant GW as Gateway Config
    participant Email as Notification Service

    Dev->>Portal: Sign up / Login (OAuth2 with GitHub/Google)
    Portal->>Auth: OAuth2 authorization code flow
    Auth-->>Portal: {access_token, user_info}
    Portal->>DB: Create developer account

    Dev->>Portal: Create App {name: "My App", description, callback_urls}
    Portal->>DB: Store app metadata

    Dev->>Portal: Subscribe to API Product {product: "Products API", plan: "Gold"}
    Portal->>Portal: Check plan eligibility (auto-approve for free/gold; manual for enterprise)

    alt Auto-approved plan
        Portal->>KMS: Generate API key pair
        KMS->>KMS: Generate: ak_prod_xxx (public) + sk_prod_xxx (secret)
        KMS-->>Portal: {api_key, secret_key, key_id}

        Portal->>DB: Store key metadata {key_id, app_id, plan, scopes, created_at}
        Portal->>GW: Sync key to gateway (push via config API)
        GW-->>Portal: Key active

        Portal->>Email: Send welcome email with getting-started guide
        Portal-->>Dev: {api_key: ak_prod_xxx, secret: sk_prod_xxx (shown once)}
    else Manual approval required (Enterprise plan)
        Portal->>DB: Create pending subscription
        Portal->>Email: Notify admin for approval
        Portal-->>Dev: Subscription pending approval (ETA: 24h)
    end

    Note over Dev: Developer can now:<br/>- View usage dashboard<br/>- Rotate keys<br/>- Set webhook URLs<br/>- Access sandbox environment
```
