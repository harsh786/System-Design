# Redis Rate Limiting — Comprehensive Production Patterns

## Rate Limiting Strategy Comparison Matrix

| Algorithm | Accuracy | Memory | Burst Handling | Distributed | Complexity |
|-----------|----------|--------|----------------|-------------|------------|
| Fixed Window | Low (boundary burst) | O(1) | Poor | Easy | Low |
| Sliding Window Log | High | O(n) | Excellent | Medium | Medium |
| Sliding Window Counter | Good | O(1) | Good | Easy | Low |
| Token Bucket | High | O(1) | Configurable | Medium | Medium |
| Leaky Bucket | High | O(1) | Smoothing | Medium | Medium |
| GCRA (Generic Cell Rate) | High | O(1) | Configurable | Medium | High |

---

## 1. Fixed Window Rate Limiter

The simplest approach — counts requests in discrete time windows.

```python
import redis
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None


class FixedWindowRateLimiter:
    """
    Fixed window counter: divides time into discrete windows.
    
    Weakness: 2x burst at window boundaries.
    Example: 100 req/min limit. If 100 requests come at 0:59 and 100 at 1:00,
    200 requests pass in 2 seconds while respecting per-window limits.
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:fw"):
        self.r = redis_client
        self.prefix = prefix

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        window_start = int(now // window_seconds) * window_seconds
        window_key = f"{self.prefix}:{key}:{window_start}"

        pipe = self.r.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds + 1)  # +1 for clock skew safety
        results = pipe.execute()

        current_count = results[0]
        reset_at = window_start + window_seconds

        if current_count > limit:
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=reset_at - now,
            )

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=max(0, limit - current_count),
            reset_at=reset_at,
        )

    def check_multi_window(
        self, key: str, limits: list[tuple[int, int]]
    ) -> RateLimitResult:
        """
        Check multiple windows simultaneously.
        Example: [(100, 60), (1000, 3600)] = 100/min AND 1000/hour
        """
        results = []
        for limit, window in limits:
            result = self.check(f"{key}:{window}", limit, window)
            results.append(result)

        # If ANY window is exceeded, deny
        denied = [r for r in results if not r.allowed]
        if denied:
            # Return the most restrictive denial
            most_restrictive = max(denied, key=lambda r: r.retry_after or 0)
            return most_restrictive

        # Return the window with fewest remaining
        return min(results, key=lambda r: r.remaining)
```

### When to Use Fixed Window

- High-throughput systems where slight inaccuracy is acceptable
- Simple API quota tracking (daily/monthly limits)
- Background job scheduling with coarse granularity

---

## 2. Sliding Window Log

Stores timestamp of each request — most accurate but highest memory usage.

```python
import redis
import time
from typing import Optional


class SlidingWindowLogLimiter:
    """
    Stores timestamp of every request in a sorted set.
    Perfect accuracy but O(n) memory where n = number of requests in window.
    
    Best for: Low-volume, high-accuracy requirements (auth attempts, payments).
    Avoid for: High-volume endpoints (100k+ req/s).
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:swl"):
        self.r = redis_client
        self.prefix = prefix

    # Atomic check-and-record using Lua
    LUA_SLIDING_LOG = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local request_id = ARGV[4]
    
    local window_start = now - window
    
    -- Remove expired entries
    redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
    
    -- Count current entries
    local count = redis.call('ZCARD', key)
    
    if count < limit then
        -- Add this request
        redis.call('ZADD', key, now, request_id)
        redis.call('EXPIRE', key, window + 1)
        return {1, limit - count - 1, 0}  -- allowed, remaining, retry_after_ms
    else
        -- Get oldest entry to calculate retry time
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 0
        if #oldest > 0 then
            retry_after = math.ceil((tonumber(oldest[2]) + window - now) * 1000)
        end
        return {0, 0, retry_after}  -- denied, remaining, retry_after_ms
    end
    """

    def check(
        self, key: str, limit: int, window_seconds: int, request_id: Optional[str] = None
    ) -> RateLimitResult:
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        if request_id is None:
            request_id = f"{now}:{id(self)}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_SLIDING_LOG,
            1,
            full_key,
            str(now),
            str(window_seconds),
            str(limit),
            request_id,
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=now + window_seconds,
            retry_after=retry_after_ms / 1000.0 if not allowed else None,
        )

    def get_request_timestamps(self, key: str, window_seconds: int) -> list[float]:
        """Get all request timestamps in current window (for debugging)."""
        full_key = f"{self.prefix}:{key}"
        now = time.time()
        window_start = now - window_seconds
        entries = self.r.zrangebyscore(full_key, window_start, now, withscores=True)
        return [score for _, score in entries]
```

### Memory Estimation for Sliding Window Log

```
Memory per key = (avg_member_size + 16 bytes overhead) × requests_in_window
Example: 1000 req/min, member = 20 bytes
Memory = (20 + 16) × 1000 = 36 KB per key
For 100k users = 3.6 GB — often too expensive
```

---

## 3. Sliding Window Counter

Combines fixed window simplicity with sliding window accuracy using weighted counters.

```python
import redis
import time
import math


class SlidingWindowCounterLimiter:
    """
    Approximates sliding window using two fixed windows with weighted averaging.
    
    Accuracy: Within 0.003% of true sliding window for typical workloads.
    Memory: O(1) per key — just two counters.
    
    How it works:
    - Current window count: requests in current period
    - Previous window count: requests in previous period  
    - Weighted total = prev_count * (1 - elapsed_fraction) + current_count
    
    Example: 100 req/min limit, we're 30s into the current minute.
    prev_window had 80 requests, current has 40.
    weighted = 80 * (1 - 0.5) + 40 = 40 + 40 = 80 → allowed
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:swc"):
        self.r = redis_client
        self.prefix = prefix

    LUA_SLIDING_COUNTER = """
    local key_prefix = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    
    -- Calculate window boundaries
    local current_window = math.floor(now / window) * window
    local previous_window = current_window - window
    local elapsed = now - current_window
    local weight = 1 - (elapsed / window)
    
    local current_key = key_prefix .. ':' .. current_window
    local previous_key = key_prefix .. ':' .. previous_window
    
    -- Get counts
    local prev_count = tonumber(redis.call('GET', previous_key) or '0')
    local curr_count = tonumber(redis.call('GET', current_key) or '0')
    
    -- Calculate weighted count
    local weighted_count = math.floor(prev_count * weight) + curr_count
    
    if weighted_count >= limit then
        -- Calculate retry_after: when will enough old requests expire?
        local excess = weighted_count - limit + 1
        local retry_after = 0
        if prev_count > 0 then
            -- Time until weight reduces enough
            local needed_weight = (prev_count - excess) / prev_count
            retry_after = math.ceil((1 - needed_weight) * window - elapsed)
            if retry_after < 0 then retry_after = window - elapsed end
        else
            retry_after = math.ceil(window - elapsed)
        end
        return {0, 0, retry_after}
    end
    
    -- Increment current window
    redis.call('INCR', current_key)
    redis.call('EXPIRE', current_key, window * 2 + 1)
    
    local new_count = weighted_count + 1
    local remaining = limit - new_count
    
    return {1, remaining, 0}
    """

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_SLIDING_COUNTER,
            1,
            full_key,
            str(now),
            str(window_seconds),
            str(limit),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after = int(result[2])

        current_window = int(now // window_seconds) * window_seconds
        reset_at = current_window + window_seconds

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after if not allowed else None,
        )
```

### Accuracy Analysis

The sliding window counter has a maximum error of:
- Worst case: one full request over-count when `prev_count = limit` and weight ≈ 1
- Average error: < 0.003% in production workloads
- Error is always conservative (may reject slightly early, never allows over-limit)

---

## 4. Token Bucket Algorithm

Allows controlled bursts while maintaining a long-term average rate.

```python
import redis
import time


class TokenBucketLimiter:
    """
    Token Bucket: tokens are added at a fixed rate (refill_rate/second).
    Each request consumes one or more tokens. Bucket has a max capacity (burst limit).
    
    Key properties:
    - Allows bursts up to bucket capacity
    - Long-term rate is bounded by refill rate
    - Smooth rate limiting with configurable burst tolerance
    
    Parameters:
    - capacity: max tokens (burst size)
    - refill_rate: tokens added per second
    
    Example: capacity=10, refill_rate=2
    - Can burst 10 requests instantly
    - After burst, sustained rate = 2 req/s
    - Bucket refills to max 10 over 5 seconds of inactivity
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:tb"):
        self.r = redis_client
        self.prefix = prefix

    LUA_TOKEN_BUCKET = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])
    
    -- Get current state
    local data = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(data[1])
    local last_refill = tonumber(data[2])
    
    -- Initialize if first request
    if tokens == nil then
        tokens = capacity
        last_refill = now
    end
    
    -- Calculate token refill
    local elapsed = now - last_refill
    local new_tokens = elapsed * refill_rate
    tokens = math.min(capacity, tokens + new_tokens)
    
    -- Check if enough tokens
    local allowed = 0
    local retry_after = 0
    
    if tokens >= requested then
        tokens = tokens - requested
        allowed = 1
    else
        -- Calculate time until enough tokens are available
        local deficit = requested - tokens
        retry_after = math.ceil(deficit / refill_rate * 1000)  -- ms
    end
    
    -- Update state
    redis.call('HMSET', key, 'tokens', tostring(tokens), 'last_refill', tostring(now))
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 10)
    
    return {allowed, math.floor(tokens), retry_after}
    """

    def check(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        tokens_requested: int = 1,
    ) -> RateLimitResult:
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_TOKEN_BUCKET,
            1,
            full_key,
            str(capacity),
            str(refill_rate),
            str(now),
            str(tokens_requested),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])

        return RateLimitResult(
            allowed=allowed,
            limit=capacity,
            remaining=remaining,
            reset_at=now + (capacity - remaining) / refill_rate,
            retry_after=retry_after_ms / 1000.0 if not allowed else None,
        )

    def get_bucket_state(self, key: str) -> dict:
        """Inspect current bucket state (for monitoring)."""
        full_key = f"{self.prefix}:{key}"
        data = self.r.hgetall(full_key)
        if not data:
            return {"tokens": None, "last_refill": None}
        return {
            "tokens": float(data.get(b"tokens", 0)),
            "last_refill": float(data.get(b"last_refill", 0)),
        }
```

### Token Bucket Configuration Guide

| Use Case | Capacity | Refill Rate | Behavior |
|----------|----------|-------------|----------|
| API (100 req/min) | 10 | 1.67/s | Burst 10, then ~1.67/s sustained |
| Login attempts | 5 | 0.1/s | Burst 5, then 1 every 10s |
| File uploads | 3 | 0.05/s | Burst 3, then 1 every 20s |
| WebSocket msgs | 50 | 10/s | Burst 50, then 10/s sustained |

---

## 5. Leaky Bucket Algorithm

Processes requests at a fixed rate, queuing excess. Smoothest output rate.

```python
import redis
import time


class LeakyBucketLimiter:
    """
    Leaky Bucket: requests enter a queue (bucket) and drain at a fixed rate.
    If the bucket overflows, requests are rejected.
    
    Key properties:
    - Output rate is perfectly smooth (exactly drain_rate req/s)
    - No bursts in output (unlike token bucket)
    - Good for protecting downstream services that need consistent load
    
    Parameters:
    - capacity: queue size (max pending requests)
    - drain_rate: requests processed per second
    
    Difference from Token Bucket:
    - Token Bucket: controls INPUT rate with burst allowance
    - Leaky Bucket: controls OUTPUT rate, smoothing bursts
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:lb"):
        self.r = redis_client
        self.prefix = prefix

    LUA_LEAKY_BUCKET = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local drain_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    
    -- Get current state
    local data = redis.call('HMGET', key, 'water_level', 'last_drain')
    local water_level = tonumber(data[1]) or 0
    local last_drain = tonumber(data[2]) or now
    
    -- Drain water based on elapsed time
    local elapsed = now - last_drain
    local drained = elapsed * drain_rate
    water_level = math.max(0, water_level - drained)
    
    -- Try to add one unit of water
    local allowed = 0
    local retry_after = 0
    
    if water_level < capacity then
        water_level = water_level + 1
        allowed = 1
    else
        -- Calculate when one unit will drain
        retry_after = math.ceil((1 / drain_rate) * 1000)  -- ms until one drains
    end
    
    -- Save state
    redis.call('HMSET', key, 'water_level', tostring(water_level), 'last_drain', tostring(now))
    redis.call('EXPIRE', key, math.ceil(capacity / drain_rate) + 10)
    
    local remaining = math.floor(capacity - water_level)
    return {allowed, remaining, retry_after}
    """

    def check(self, key: str, capacity: int, drain_rate: float) -> RateLimitResult:
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_LEAKY_BUCKET,
            1,
            full_key,
            str(capacity),
            str(drain_rate),
            str(now),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])

        return RateLimitResult(
            allowed=allowed,
            limit=capacity,
            remaining=remaining,
            reset_at=now + capacity / drain_rate,
            retry_after=retry_after_ms / 1000.0 if not allowed else None,
        )
```

---

## 6. Generic Cell Rate Algorithm (GCRA)

The most theoretically sound algorithm — used in ATM networks, now adopted by modern API gateways.

```python
import redis
import time


class GCRALimiter:
    """
    Generic Cell Rate Algorithm (GCRA) — also called Virtual Scheduling.
    
    Concept: Each request has a "theoretical arrival time" (TAT).
    If a request arrives before its TAT, it's rate-limited.
    
    Parameters:
    - period: time window (e.g., 60 seconds)
    - limit: max requests in period
    - burst: additional burst allowance (default: limit)
    
    The emission_interval = period / limit
    The burst_offset = emission_interval * (burst - 1)
    
    Advantages over Token Bucket:
    - Single state variable (TAT) vs two (tokens + last_refill)
    - Mathematically equivalent but simpler implementation
    - Used by Cloudflare, Kong, Envoy
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:gcra"):
        self.r = redis_client
        self.prefix = prefix

    LUA_GCRA = """
    local key = KEYS[1]
    local emission_interval = tonumber(ARGV[1])  -- time between allowed requests
    local burst_offset = tonumber(ARGV[2])       -- max burst tolerance
    local now = tonumber(ARGV[3])
    
    -- TAT = Theoretical Arrival Time
    local tat = tonumber(redis.call('GET', key))
    
    if tat == nil then
        tat = now
    end
    
    -- Allow time = how far back TAT can be and still accept
    local allow_at = tat - burst_offset
    
    local diff = now - allow_at
    
    local allowed = 0
    local remaining = 0
    local retry_after = 0
    local new_tat = 0
    
    if diff >= 0 then
        -- Request allowed
        new_tat = math.max(tat, now) + emission_interval
        redis.call('SET', key, tostring(new_tat))
        
        -- TTL: time until bucket fully empties
        local ttl = math.ceil(new_tat - now + burst_offset)
        redis.call('EXPIRE', key, ttl)
        
        allowed = 1
        -- Remaining = how many more requests until TAT exceeds burst window
        remaining = math.floor(diff / emission_interval)
    else
        -- Request denied
        retry_after = math.ceil(-diff * 1000)  -- ms
        remaining = 0
    end
    
    return {allowed, remaining, retry_after, math.floor(new_tat * 1000)}
    """

    def check(
        self,
        key: str,
        limit: int,
        period_seconds: int,
        burst: int = 0,
    ) -> RateLimitResult:
        if burst == 0:
            burst = limit

        emission_interval = period_seconds / limit
        burst_offset = emission_interval * (burst - 1)
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_GCRA,
            1,
            full_key,
            str(emission_interval),
            str(burst_offset),
            str(now),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=now + period_seconds,
            retry_after=retry_after_ms / 1000.0 if not allowed else None,
        )
```

---

## 7. Hierarchical / Multi-Tier Rate Limiting

Real systems need multiple rate limit layers: per-user, per-IP, per-endpoint, global.

```python
import redis
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RateLimitTier(Enum):
    GLOBAL = "global"
    ORGANIZATION = "org"
    USER = "user"
    IP = "ip"
    ENDPOINT = "endpoint"


@dataclass
class RateLimitPolicy:
    tier: RateLimitTier
    identifier: str
    limit: int
    window_seconds: int
    priority: int = 0  # Higher = checked first


@dataclass
class HierarchicalResult:
    allowed: bool
    triggered_tier: Optional[RateLimitTier] = None
    results: dict = field(default_factory=dict)
    retry_after: Optional[float] = None
    headers: dict = field(default_factory=dict)


class HierarchicalRateLimiter:
    """
    Multi-tier rate limiting: checks multiple policies from most specific to least.
    
    Typical hierarchy:
    1. Global (protect infrastructure): 10000 req/s total
    2. Organization (fair usage): 1000 req/min per org
    3. User (individual limit): 100 req/min per user
    4. IP (abuse prevention): 60 req/min per IP
    5. Endpoint (protect expensive ops): 10 req/min per user+endpoint
    
    Design principle: Fail fast. Check cheapest/most-likely-to-fail tier first.
    In practice, that's usually the most specific tier (endpoint > user > org > global).
    """

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.counter = SlidingWindowCounterLimiter(redis_client, prefix="rl:hier")

    def check(self, policies: list[RateLimitPolicy]) -> HierarchicalResult:
        # Sort by priority (highest first) for fail-fast
        sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)

        results = {}
        for policy in sorted_policies:
            key = f"{policy.tier.value}:{policy.identifier}"
            result = self.counter.check(key, policy.limit, policy.window_seconds)
            results[policy.tier] = result

            if not result.allowed:
                return HierarchicalResult(
                    allowed=False,
                    triggered_tier=policy.tier,
                    results=results,
                    retry_after=result.retry_after,
                    headers=self._build_headers(results, policy),
                )

        # All tiers passed — return most restrictive remaining
        most_restrictive = min(results.values(), key=lambda r: r.remaining)
        return HierarchicalResult(
            allowed=True,
            results=results,
            headers=self._build_headers(results, sorted_policies[0]),
        )

    def _build_headers(
        self, results: dict, primary_policy: RateLimitPolicy
    ) -> dict:
        """Build standard rate limit response headers."""
        primary_result = results.get(primary_policy.tier)
        if not primary_result:
            return {}

        headers = {
            "X-RateLimit-Limit": str(primary_policy.limit),
            "X-RateLimit-Remaining": str(primary_result.remaining),
            "X-RateLimit-Reset": str(int(primary_result.reset_at)),
            "X-RateLimit-Policy": primary_policy.tier.value,
        }

        if not primary_result.allowed:
            headers["Retry-After"] = str(int(primary_result.retry_after or 1))

        return headers


# Usage example
def rate_limit_request(
    limiter: HierarchicalRateLimiter,
    user_id: str,
    org_id: str,
    ip_address: str,
    endpoint: str,
) -> HierarchicalResult:
    """Apply hierarchical rate limiting to an API request."""
    policies = [
        RateLimitPolicy(
            tier=RateLimitTier.ENDPOINT,
            identifier=f"{user_id}:{endpoint}",
            limit=10,
            window_seconds=60,
            priority=100,  # Check first (most specific)
        ),
        RateLimitPolicy(
            tier=RateLimitTier.USER,
            identifier=user_id,
            limit=100,
            window_seconds=60,
            priority=80,
        ),
        RateLimitPolicy(
            tier=RateLimitTier.IP,
            identifier=ip_address,
            limit=60,
            window_seconds=60,
            priority=70,
        ),
        RateLimitPolicy(
            tier=RateLimitTier.ORGANIZATION,
            identifier=org_id,
            limit=1000,
            window_seconds=60,
            priority=50,
        ),
        RateLimitPolicy(
            tier=RateLimitTier.GLOBAL,
            identifier="api",
            limit=10000,
            window_seconds=1,
            priority=10,  # Check last (least specific)
        ),
    ]

    return limiter.check(policies)
```

---

## 8. Distributed Rate Limiting with Penalty Box

Adds escalating penalties for repeated violations.

```python
import redis
import time
import math
from typing import Optional


class PenaltyBoxLimiter:
    """
    Rate limiter with escalating penalties for repeat offenders.
    
    After N violations within a window:
    - 1st violation: standard retry_after
    - 2nd violation: 2x penalty
    - 3rd violation: 4x penalty (exponential backoff)
    - Nth violation: min(base * 2^(n-1), max_penalty)
    
    Use cases:
    - Brute-force login prevention
    - Scraping detection
    - Abuse prevention with progressive enforcement
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:penalty"):
        self.r = redis_client
        self.prefix = prefix

    LUA_PENALTY_CHECK = """
    local rate_key = KEYS[1]
    local penalty_key = KEYS[2]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local base_penalty = tonumber(ARGV[4])
    local max_penalty = tonumber(ARGV[5])
    
    -- Check if currently in penalty box
    local penalty_until = tonumber(redis.call('GET', penalty_key))
    if penalty_until and now < penalty_until then
        local remaining_penalty = math.ceil(penalty_until - now)
        return {0, 0, remaining_penalty * 1000, 1}  -- denied, in_penalty=true
    end
    
    -- Standard sliding window counter check
    local current_window = math.floor(now / window) * window
    local current_key = rate_key .. ':' .. current_window
    local prev_key = rate_key .. ':' .. (current_window - window)
    
    local prev_count = tonumber(redis.call('GET', prev_key) or '0')
    local curr_count = tonumber(redis.call('GET', current_key) or '0')
    
    local elapsed = now - current_window
    local weight = 1 - (elapsed / window)
    local weighted_count = math.floor(prev_count * weight) + curr_count
    
    if weighted_count >= limit then
        -- Violation: calculate and apply penalty
        local violations_key = rate_key .. ':violations'
        local violations = redis.call('INCR', violations_key)
        redis.call('EXPIRE', violations_key, window * 10)
        
        -- Exponential penalty
        local penalty_duration = math.min(
            base_penalty * math.pow(2, violations - 1),
            max_penalty
        )
        
        -- Put in penalty box
        local penalty_expiry = now + penalty_duration
        redis.call('SET', penalty_key, tostring(penalty_expiry))
        redis.call('EXPIRE', penalty_key, math.ceil(penalty_duration) + 1)
        
        return {0, 0, math.ceil(penalty_duration * 1000), 0}  -- denied
    end
    
    -- Allow request
    redis.call('INCR', current_key)
    redis.call('EXPIRE', current_key, window * 2 + 1)
    
    local remaining = limit - weighted_count - 1
    return {1, remaining, 0, 0}  -- allowed
    """

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        base_penalty_seconds: float = 30,
        max_penalty_seconds: float = 3600,
    ) -> RateLimitResult:
        now = time.time()
        rate_key = f"{self.prefix}:{key}"
        penalty_key = f"{self.prefix}:{key}:penalty"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_PENALTY_CHECK,
            2,
            rate_key,
            penalty_key,
            str(now),
            str(window_seconds),
            str(limit),
            str(base_penalty_seconds),
            str(max_penalty_seconds),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])
        in_penalty = bool(result[3])

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=now + window_seconds,
            retry_after=retry_after_ms / 1000.0 if not allowed else None,
        )

    def clear_penalty(self, key: str) -> None:
        """Manually release from penalty box (admin action)."""
        penalty_key = f"{self.prefix}:{key}:penalty"
        violations_key = f"{self.prefix}:{key}:violations"
        self.r.delete(penalty_key, violations_key)

    def get_violation_count(self, key: str) -> int:
        """Get current violation count for monitoring."""
        violations_key = f"{self.prefix}:{key}:violations"
        count = self.r.get(violations_key)
        return int(count) if count else 0
```

---

## 9. Cost-Based Rate Limiting

Different endpoints have different costs — weight them accordingly.

```python
import redis
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class EndpointCost:
    cost: int  # Token cost per request
    description: str


class CostBasedRateLimiter:
    """
    Cost-aware rate limiting: different operations consume different amounts of quota.
    
    Instead of "100 requests per minute", it's "1000 tokens per minute" where:
    - GET /users → 1 token
    - POST /users → 5 tokens
    - GET /reports/generate → 50 tokens
    - POST /bulk-import → 100 tokens
    
    This prevents expensive operations from starving cheap ones,
    and lets users make more cheap calls without hitting limits on expensive ops.
    
    Used by: OpenAI (tokens), Stripe (API complexity), GitHub (GraphQL node count)
    """

    DEFAULT_COSTS: Dict[str, EndpointCost] = {
        "GET": EndpointCost(cost=1, description="Read operation"),
        "POST": EndpointCost(cost=5, description="Write operation"),
        "PUT": EndpointCost(cost=3, description="Update operation"),
        "DELETE": EndpointCost(cost=2, description="Delete operation"),
        "SEARCH": EndpointCost(cost=10, description="Search/query operation"),
        "EXPORT": EndpointCost(cost=50, description="Data export"),
        "BULK": EndpointCost(cost=100, description="Bulk operation"),
    }

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:cost"):
        self.r = redis_client
        self.prefix = prefix
        self.token_bucket = TokenBucketLimiter(redis_client, prefix=f"{prefix}:tb")

    def check(
        self,
        key: str,
        operation_cost: int,
        token_capacity: int,
        refill_rate: float,
    ) -> RateLimitResult:
        """
        Check if user has enough tokens for this operation.
        
        Args:
            key: Rate limit key (usually user_id or api_key)
            operation_cost: How many tokens this operation costs
            token_capacity: Max token bucket size (burst)
            refill_rate: Tokens refilled per second
        """
        return self.token_bucket.check(
            key=key,
            capacity=token_capacity,
            refill_rate=refill_rate,
            tokens_requested=operation_cost,
        )

    def get_remaining_budget(self, key: str, capacity: int, refill_rate: float) -> dict:
        """Show user what operations they can still afford."""
        state = self.token_bucket.get_bucket_state(key)
        tokens = state.get("tokens", capacity)

        affordable = {}
        for op_name, op_cost in self.DEFAULT_COSTS.items():
            if tokens >= op_cost.cost:
                affordable[op_name] = {
                    "cost": op_cost.cost,
                    "available_calls": int(tokens // op_cost.cost),
                }

        return {
            "tokens_remaining": tokens,
            "token_capacity": capacity,
            "refill_rate": refill_rate,
            "affordable_operations": affordable,
        }
```

---

## 10. API Rate Limiting Middleware (FastAPI)

Production-ready middleware with proper headers, logging, and bypass support.

```python
import redis
import time
import hashlib
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitBypass(Enum):
    """Reasons a request might bypass rate limiting."""
    INTERNAL_SERVICE = "internal_service"
    HEALTH_CHECK = "health_check"
    ADMIN_OVERRIDE = "admin_override"
    ALLOWLISTED_IP = "allowlisted_ip"


@dataclass
class RateLimitConfig:
    """Per-endpoint rate limit configuration."""
    endpoint_pattern: str
    limit: int
    window_seconds: int
    cost: int = 1
    key_func: Optional[Callable] = None  # Custom key extraction
    bypass_conditions: list = field(default_factory=list)


class RateLimitMiddleware:
    """
    Production rate limiting middleware.
    
    Features:
    - Per-endpoint configuration
    - Multiple key strategies (user_id, API key, IP, custom)
    - Bypass for internal services and health checks
    - Standard rate limit headers (RFC 6585 + draft-ietf-httpapi-ratelimit-headers)
    - Structured logging for monitoring
    - Graceful degradation if Redis is unavailable
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        configs: list[RateLimitConfig],
        fail_open: bool = True,
        allowlisted_ips: set = None,
        internal_service_header: str = "X-Internal-Service-Token",
        internal_service_token: str = "",
    ):
        self.r = redis_client
        self.configs = configs
        self.fail_open = fail_open
        self.allowlisted_ips = allowlisted_ips or set()
        self.internal_service_header = internal_service_header
        self.internal_service_token = internal_service_token
        self.limiter = SlidingWindowCounterLimiter(redis_client, prefix="rl:api")

    def get_config_for_endpoint(
        self, method: str, path: str
    ) -> Optional[RateLimitConfig]:
        """Match request to rate limit config."""
        for config in self.configs:
            if self._matches_pattern(config.endpoint_pattern, f"{method} {path}"):
                return config
        return None

    def _matches_pattern(self, pattern: str, request_path: str) -> bool:
        """Simple pattern matching. Production: use regex or path templates."""
        import fnmatch
        return fnmatch.fnmatch(request_path, pattern)

    def check_bypass(self, request_meta: dict) -> Optional[RateLimitBypass]:
        """Check if request should bypass rate limiting."""
        # Health checks
        if request_meta.get("path") in ("/health", "/ready", "/metrics"):
            return RateLimitBypass.HEALTH_CHECK

        # Internal service calls
        service_token = request_meta.get("headers", {}).get(
            self.internal_service_header
        )
        if service_token and service_token == self.internal_service_token:
            return RateLimitBypass.INTERNAL_SERVICE

        # Allowlisted IPs
        if request_meta.get("ip") in self.allowlisted_ips:
            return RateLimitBypass.ALLOWLISTED_IP

        return None

    def extract_key(self, request_meta: dict, config: RateLimitConfig) -> str:
        """Extract rate limit key from request."""
        if config.key_func:
            return config.key_func(request_meta)

        # Default hierarchy: API key > User ID > IP
        api_key = request_meta.get("api_key")
        if api_key:
            # Hash API key to avoid storing raw keys in Redis
            return f"apikey:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

        user_id = request_meta.get("user_id")
        if user_id:
            return f"user:{user_id}"

        ip = request_meta.get("ip", "unknown")
        return f"ip:{ip}"

    def process_request(self, request_meta: dict) -> dict:
        """
        Main entry point. Returns response dict with headers and status.
        
        Args:
            request_meta: {
                "method": "GET",
                "path": "/api/users",
                "ip": "1.2.3.4",
                "user_id": "user_123",  # optional
                "api_key": "sk_live_...",  # optional
                "headers": {...},
            }
        
        Returns:
            {
                "allowed": True/False,
                "status_code": 200/429,
                "headers": {...rate limit headers...},
                "body": {...error body if rejected...},
            }
        """
        # Check bypass
        bypass = self.check_bypass(request_meta)
        if bypass:
            logger.debug(f"Rate limit bypass: {bypass.value}")
            return {"allowed": True, "status_code": 200, "headers": {}}

        # Find config
        method = request_meta.get("method", "GET")
        path = request_meta.get("path", "/")
        config = self.get_config_for_endpoint(method, path)

        if not config:
            return {"allowed": True, "status_code": 200, "headers": {}}

        # Extract key
        key = self.extract_key(request_meta, config)
        full_key = f"{method}:{path}:{key}"

        # Check rate limit (with Redis failure handling)
        try:
            result = self.limiter.check(full_key, config.limit, config.window_seconds)
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            if self.fail_open:
                return {"allowed": True, "status_code": 200, "headers": {}}
            else:
                return {
                    "allowed": False,
                    "status_code": 503,
                    "headers": {"Retry-After": "5"},
                    "body": {"error": {"code": "SERVICE_UNAVAILABLE", "message": "Rate limiting service unavailable"}},
                }

        # Build response headers (draft-ietf-httpapi-ratelimit-headers)
        headers = {
            "RateLimit-Limit": str(config.limit),
            "RateLimit-Remaining": str(result.remaining),
            "RateLimit-Reset": str(int(result.reset_at - time.time())),
            "RateLimit-Policy": f"{config.limit};w={config.window_seconds}",
        }

        if not result.allowed:
            headers["Retry-After"] = str(int(result.retry_after or 1))

            logger.warning(
                "Rate limit exceeded",
                extra={
                    "key": key,
                    "endpoint": f"{method} {path}",
                    "limit": config.limit,
                    "window": config.window_seconds,
                    "retry_after": result.retry_after,
                },
            )

            return {
                "allowed": False,
                "status_code": 429,
                "headers": headers,
                "body": {
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Try again in {int(result.retry_after or 1)} seconds.",
                        "retry_after": result.retry_after,
                        "limit": config.limit,
                        "window": config.window_seconds,
                    }
                },
            }

        return {"allowed": True, "status_code": 200, "headers": headers}


# FastAPI integration example
def create_fastapi_middleware(limiter: RateLimitMiddleware):
    """
    FastAPI middleware integration.
    
    Usage:
        app = FastAPI()
        
        configs = [
            RateLimitConfig("GET /api/*", limit=100, window_seconds=60),
            RateLimitConfig("POST /api/*", limit=30, window_seconds=60),
            RateLimitConfig("* /api/auth/*", limit=5, window_seconds=300),
        ]
        
        middleware = RateLimitMiddleware(redis_client, configs)
        app.middleware("http")(create_fastapi_middleware(middleware))
    """
    async def middleware(request, call_next):
        request_meta = {
            "method": request.method,
            "path": request.url.path,
            "ip": request.client.host if request.client else "unknown",
            "user_id": getattr(request.state, "user_id", None),
            "api_key": request.headers.get("Authorization", "").replace("Bearer ", ""),
            "headers": dict(request.headers),
        }

        result = limiter.process_request(request_meta)

        if not result["allowed"]:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=result["status_code"],
                content=result.get("body", {}),
                headers=result["headers"],
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        for header, value in result.get("headers", {}).items():
            response.headers[header] = value

        return response

    return middleware
```

---

## 11. Adaptive Rate Limiting

Dynamically adjusts limits based on system health — backs off under load.

```python
import redis
import time
import math


class AdaptiveRateLimiter:
    """
    Adapts rate limits based on system health metrics.
    
    When system is healthy → use normal limits
    When system is degraded → reduce limits proportionally
    When system is critical → emergency limits (10% of normal)
    
    Health signals:
    - Response latency p99
    - Error rate percentage
    - Queue depth
    - CPU/memory utilization (if available)
    
    This prevents cascading failures by shedding load before the system falls over.
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:adaptive"):
        self.r = redis_client
        self.prefix = prefix
        self.limiter = TokenBucketLimiter(redis_client, prefix=f"{prefix}:tb")

    # System health thresholds
    HEALTH_KEY = "system:health:score"  # 0.0 (critical) to 1.0 (healthy)

    def update_health_score(
        self,
        error_rate: float,       # 0.0 to 1.0
        latency_p99_ms: float,   # milliseconds
        latency_target_ms: float = 500,
        error_threshold: float = 0.05,
    ) -> float:
        """
        Calculate and store system health score.
        Call this from a background health checker every 5-10 seconds.
        """
        # Score components (each 0.0 to 1.0, higher = healthier)
        error_score = max(0, 1.0 - (error_rate / error_threshold))
        latency_score = max(0, 1.0 - (latency_p99_ms / (latency_target_ms * 3)))

        # Weighted average
        health_score = (error_score * 0.6) + (latency_score * 0.4)
        health_score = max(0.1, min(1.0, health_score))  # Clamp to [0.1, 1.0]

        # Store with short TTL (stale health = assume degraded)
        self.r.set(self.HEALTH_KEY, str(health_score), ex=30)

        return health_score

    def get_health_multiplier(self) -> float:
        """Get current health multiplier (0.1 to 1.0)."""
        score = self.r.get(self.HEALTH_KEY)
        if score is None:
            return 0.5  # Unknown health → conservative
        return max(0.1, float(score))

    def check(
        self,
        key: str,
        base_capacity: int,
        base_refill_rate: float,
    ) -> RateLimitResult:
        """
        Check rate limit with adaptive adjustment.
        
        When health_score = 1.0 → full capacity (e.g., 100 tokens)
        When health_score = 0.5 → half capacity (50 tokens)
        When health_score = 0.1 → emergency mode (10 tokens)
        """
        multiplier = self.get_health_multiplier()

        adjusted_capacity = max(1, int(base_capacity * multiplier))
        adjusted_rate = max(0.1, base_refill_rate * multiplier)

        result = self.limiter.check(
            key=key,
            capacity=adjusted_capacity,
            refill_rate=adjusted_rate,
        )

        # Annotate result with health info
        result.limit = adjusted_capacity  # Reflect adjusted limit in headers
        return result


class ConcurrencyLimiter:
    """
    Limits concurrent in-flight requests (not rate, but concurrency).
    
    Difference from rate limiting:
    - Rate limiter: "max 100 requests per minute"
    - Concurrency limiter: "max 10 requests simultaneously in-flight"
    
    Use for: expensive operations, database-heavy endpoints, external API calls
    with limited connection pools.
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:conc"):
        self.r = redis_client
        self.prefix = prefix

    LUA_ACQUIRE = """
    local key = KEYS[1]
    local max_concurrent = tonumber(ARGV[1])
    local request_id = ARGV[2]
    local now = tonumber(ARGV[3])
    local timeout = tonumber(ARGV[4])
    
    -- Clean up expired entries (requests that never released)
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - timeout)
    
    -- Check current concurrency
    local current = redis.call('ZCARD', key)
    
    if current >= max_concurrent then
        return {0, current, max_concurrent - current}
    end
    
    -- Add this request
    redis.call('ZADD', key, now, request_id)
    redis.call('EXPIRE', key, timeout + 10)
    
    return {1, current + 1, max_concurrent - current - 1}
    """

    LUA_RELEASE = """
    local key = KEYS[1]
    local request_id = ARGV[1]
    redis.call('ZREM', key, request_id)
    return redis.call('ZCARD', key)
    """

    def acquire(
        self,
        key: str,
        max_concurrent: int,
        request_id: str,
        timeout_seconds: int = 30,
    ) -> tuple[bool, int]:
        """
        Try to acquire a concurrency slot.
        Returns (allowed, current_count).
        """
        now = time.time()
        full_key = f"{self.prefix}:{key}"

        result = self.r.execute_command(
            "EVAL",
            self.LUA_ACQUIRE,
            1,
            full_key,
            str(max_concurrent),
            request_id,
            str(now),
            str(timeout_seconds),
        )

        allowed = bool(result[0])
        current = int(result[1])
        return allowed, current

    def release(self, key: str, request_id: str) -> int:
        """Release a concurrency slot. Returns remaining count."""
        full_key = f"{self.prefix}:{key}"
        remaining = self.r.execute_command(
            "EVAL",
            self.LUA_RELEASE,
            1,
            full_key,
            request_id,
        )
        return int(remaining)
```

---

## 12. Rate Limit Quota Management

Pre-allocated quotas with usage tracking and billing integration.

```python
import redis
import time
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PlanTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class QuotaPlan:
    tier: PlanTier
    requests_per_minute: int
    requests_per_day: int
    requests_per_month: int
    burst_multiplier: float = 1.5  # Allow 1.5x burst
    overage_allowed: bool = False
    overage_cost_per_1000: float = 0.0  # $ per 1000 requests over quota


PLANS = {
    PlanTier.FREE: QuotaPlan(
        tier=PlanTier.FREE,
        requests_per_minute=20,
        requests_per_day=1000,
        requests_per_month=10000,
    ),
    PlanTier.STARTER: QuotaPlan(
        tier=PlanTier.STARTER,
        requests_per_minute=60,
        requests_per_day=10000,
        requests_per_month=100000,
        overage_allowed=True,
        overage_cost_per_1000=0.50,
    ),
    PlanTier.PRO: QuotaPlan(
        tier=PlanTier.PRO,
        requests_per_minute=200,
        requests_per_day=100000,
        requests_per_month=1000000,
        burst_multiplier=2.0,
        overage_allowed=True,
        overage_cost_per_1000=0.25,
    ),
    PlanTier.ENTERPRISE: QuotaPlan(
        tier=PlanTier.ENTERPRISE,
        requests_per_minute=1000,
        requests_per_day=1000000,
        requests_per_month=50000000,
        burst_multiplier=3.0,
        overage_allowed=True,
        overage_cost_per_1000=0.10,
    ),
}


class QuotaManager:
    """
    Manages API quotas with multiple time horizons and overage billing.
    
    Design:
    - Per-minute limit → rate limiting (prevent bursts)
    - Per-day limit → fair usage (prevent one bad day from burning monthly quota)
    - Per-month limit → billing quota (triggers overage charges or hard stop)
    
    Storage:
    - Minute counters: sliding window counter (auto-expiring)
    - Daily counters: INCR with midnight expiry
    - Monthly counters: INCR with month-end expiry
    - Usage events: Redis Stream for billing pipeline
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "quota"):
        self.r = redis_client
        self.prefix = prefix
        self.rate_limiter = SlidingWindowCounterLimiter(redis_client, prefix=f"{prefix}:rl")

    def check_and_consume(
        self, user_id: str, plan: QuotaPlan, cost: int = 1
    ) -> dict:
        """
        Check all quota tiers and consume if allowed.
        
        Returns:
            {
                "allowed": bool,
                "denied_reason": str or None,
                "usage": {"minute": x, "day": y, "month": z},
                "limits": {"minute": a, "day": b, "month": c},
                "overage": bool,
                "headers": {...},
            }
        """
        now = time.time()

        # Check per-minute rate limit
        minute_result = self.rate_limiter.check(
            f"{user_id}:minute",
            int(plan.requests_per_minute * plan.burst_multiplier),
            60,
        )
        if not minute_result.allowed:
            return self._denied_response(
                "RATE_LIMIT_EXCEEDED",
                "Per-minute rate limit exceeded",
                minute_result,
                plan,
                user_id,
            )

        # Check daily quota
        day_key = f"{self.prefix}:day:{user_id}:{self._day_key(now)}"
        daily_count = self.r.incr(day_key)
        if daily_count == 1:
            # Set expiry at end of day (UTC)
            seconds_until_midnight = self._seconds_until_midnight(now)
            self.r.expire(day_key, seconds_until_midnight)

        if daily_count > plan.requests_per_day:
            if not plan.overage_allowed:
                self.r.decr(day_key)  # Rollback
                return self._quota_exceeded_response("DAILY_QUOTA_EXCEEDED", plan, user_id)
            # Allow with overage flag
            self._record_overage(user_id, cost, "daily")

        # Check monthly quota
        month_key = f"{self.prefix}:month:{user_id}:{self._month_key(now)}"
        monthly_count = self.r.incr(month_key)
        if monthly_count == 1:
            seconds_until_month_end = self._seconds_until_month_end(now)
            self.r.expire(month_key, seconds_until_month_end)

        if monthly_count > plan.requests_per_month:
            if not plan.overage_allowed:
                self.r.decr(month_key)  # Rollback
                self.r.decr(day_key)    # Rollback
                return self._quota_exceeded_response("MONTHLY_QUOTA_EXCEEDED", plan, user_id)
            self._record_overage(user_id, cost, "monthly")

        # Success
        is_overage = (
            daily_count > plan.requests_per_day
            or monthly_count > plan.requests_per_month
        )

        return {
            "allowed": True,
            "denied_reason": None,
            "overage": is_overage,
            "usage": {
                "minute": plan.requests_per_minute - minute_result.remaining,
                "day": int(daily_count),
                "month": int(monthly_count),
            },
            "limits": {
                "minute": plan.requests_per_minute,
                "day": plan.requests_per_day,
                "month": plan.requests_per_month,
            },
            "headers": {
                "X-Quota-Remaining-Day": str(max(0, plan.requests_per_day - int(daily_count))),
                "X-Quota-Remaining-Month": str(max(0, plan.requests_per_month - int(monthly_count))),
                "X-Quota-Overage": str(is_overage).lower(),
            },
        }

    def _record_overage(self, user_id: str, cost: int, period: str) -> None:
        """Record overage event for billing pipeline."""
        event = json.dumps({
            "user_id": user_id,
            "cost": cost,
            "period": period,
            "timestamp": time.time(),
        })
        stream_key = f"{self.prefix}:overage_events"
        self.r.xadd(stream_key, {"event": event}, maxlen=100000)

    def get_usage_summary(self, user_id: str) -> dict:
        """Get current usage across all periods."""
        now = time.time()
        day_key = f"{self.prefix}:day:{user_id}:{self._day_key(now)}"
        month_key = f"{self.prefix}:month:{user_id}:{self._month_key(now)}"

        daily = self.r.get(day_key)
        monthly = self.r.get(month_key)

        return {
            "daily_usage": int(daily) if daily else 0,
            "monthly_usage": int(monthly) if monthly else 0,
        }

    def _denied_response(self, code, message, result, plan, user_id):
        return {
            "allowed": False,
            "denied_reason": code,
            "message": message,
            "retry_after": result.retry_after,
            "overage": False,
            "usage": {},
            "limits": {
                "minute": plan.requests_per_minute,
                "day": plan.requests_per_day,
                "month": plan.requests_per_month,
            },
            "headers": {"Retry-After": str(int(result.retry_after or 1))},
        }

    def _quota_exceeded_response(self, code, plan, user_id):
        return {
            "allowed": False,
            "denied_reason": code,
            "message": f"Quota exceeded. Upgrade plan or wait for reset.",
            "overage": False,
            "usage": self.get_usage_summary(user_id),
            "limits": {
                "minute": plan.requests_per_minute,
                "day": plan.requests_per_day,
                "month": plan.requests_per_month,
            },
            "headers": {},
        }

    @staticmethod
    def _day_key(now: float) -> str:
        return time.strftime("%Y%m%d", time.gmtime(now))

    @staticmethod
    def _month_key(now: float) -> str:
        return time.strftime("%Y%m", time.gmtime(now))

    @staticmethod
    def _seconds_until_midnight(now: float) -> int:
        t = time.gmtime(now)
        return 86400 - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec)

    @staticmethod
    def _seconds_until_month_end(now: float) -> int:
        import calendar
        t = time.gmtime(now)
        days_in_month = calendar.monthrange(t.tm_year, t.tm_mon)[1]
        remaining_days = days_in_month - t.tm_mday
        return remaining_days * 86400 + (86400 - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec))
```

---

## 13. DDoS Protection Patterns

Specialized rate limiting for attack mitigation.

```python
import redis
import time
import hashlib
from typing import Optional


class DDoSProtection:
    """
    Multi-layered DDoS protection using Redis.
    
    Layers:
    1. Connection rate: limit new connections per IP
    2. Request rate: limit requests per IP (tighter than user rate limits)
    3. Fingerprint rate: limit by device/browser fingerprint
    4. Behavioral: detect automated patterns (fixed intervals, no cookies, etc.)
    5. Global: circuit breaker when total traffic exceeds capacity
    
    Design principles:
    - Fast path: most checks are O(1) Redis operations
    - Fail-safe: if Redis is down, allow traffic (DoS protection isn't worth a self-DoS)
    - No false positives: prefer letting some attack traffic through over blocking legit users
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "ddos"):
        self.r = redis_client
        self.prefix = prefix

    LUA_RATE_AND_PATTERN = """
    local ip_key = KEYS[1]
    local pattern_key = KEYS[2]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local ip_limit = tonumber(ARGV[3])
    local interval_threshold = tonumber(ARGV[4])
    
    -- 1. IP rate check (sliding window counter)
    local current_window = math.floor(now / window) * window
    local curr_key = ip_key .. ':' .. current_window
    local prev_key = ip_key .. ':' .. (current_window - window)
    
    local prev = tonumber(redis.call('GET', prev_key) or '0')
    local curr = tonumber(redis.call('GET', curr_key) or '0')
    local elapsed = now - current_window
    local weight = 1 - (elapsed / window)
    local rate = math.floor(prev * weight) + curr
    
    if rate >= ip_limit then
        return {0, 1, rate}  -- blocked, reason=rate
    end
    
    redis.call('INCR', curr_key)
    redis.call('EXPIRE', curr_key, window * 2)
    
    -- 2. Pattern detection: check for fixed-interval requests (bot behavior)
    local last_request = tonumber(redis.call('GET', pattern_key .. ':last'))
    local is_suspicious = 0
    
    if last_request then
        local interval = now - last_request
        -- Track interval consistency
        local intervals_key = pattern_key .. ':intervals'
        redis.call('LPUSH', intervals_key, tostring(interval))
        redis.call('LTRIM', intervals_key, 0, 9)  -- Keep last 10 intervals
        redis.call('EXPIRE', intervals_key, 300)
        
        -- Check if intervals are suspiciously consistent
        local intervals = redis.call('LRANGE', intervals_key, 0, -1)
        if #intervals >= 5 then
            local sum = 0
            for _, v in ipairs(intervals) do sum = sum + tonumber(v) end
            local avg = sum / #intervals
            local variance = 0
            for _, v in ipairs(intervals) do
                variance = variance + (tonumber(v) - avg)^2
            end
            variance = variance / #intervals
            -- Low variance = fixed interval = likely bot
            if variance < interval_threshold then
                is_suspicious = 1
            end
        end
    end
    
    redis.call('SET', pattern_key .. ':last', tostring(now))
    redis.call('EXPIRE', pattern_key .. ':last', 300)
    
    return {1, is_suspicious, rate}  -- allowed, suspicious flag, current rate
    """

    def check_request(
        self,
        ip: str,
        fingerprint: Optional[str] = None,
        ip_limit: int = 120,  # per minute
        window: int = 60,
    ) -> dict:
        """
        Check if request should be allowed based on DDoS heuristics.
        
        Returns:
            {
                "allowed": bool,
                "blocked_reason": str or None,
                "suspicious": bool,
                "current_rate": int,
                "action": "allow" | "challenge" | "block",
            }
        """
        now = time.time()
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
        ip_key = f"{self.prefix}:ip:{ip_hash}"
        pattern_key = f"{self.prefix}:pattern:{ip_hash}"

        try:
            result = self.r.execute_command(
                "EVAL",
                self.LUA_RATE_AND_PATTERN,
                2,
                ip_key,
                pattern_key,
                str(now),
                str(window),
                str(ip_limit),
                str(0.01),  # interval variance threshold
            )

            allowed = bool(result[0])
            suspicious = bool(result[1])
            current_rate = int(result[2])

            if not allowed:
                return {
                    "allowed": False,
                    "blocked_reason": "IP_RATE_EXCEEDED",
                    "suspicious": True,
                    "current_rate": current_rate,
                    "action": "block",
                }

            if suspicious:
                return {
                    "allowed": True,  # Allow but flag
                    "blocked_reason": None,
                    "suspicious": True,
                    "current_rate": current_rate,
                    "action": "challenge",  # Serve CAPTCHA or JS challenge
                }

            return {
                "allowed": True,
                "blocked_reason": None,
                "suspicious": False,
                "current_rate": current_rate,
                "action": "allow",
            }

        except redis.RedisError:
            # Fail open: don't self-DoS
            return {
                "allowed": True,
                "blocked_reason": None,
                "suspicious": False,
                "current_rate": 0,
                "action": "allow",
            }

    def block_ip(self, ip: str, duration_seconds: int = 3600) -> None:
        """Manually block an IP (from admin action or automated detection)."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
        self.r.set(
            f"{self.prefix}:blocked:{ip_hash}",
            "1",
            ex=duration_seconds,
        )

    def is_blocked(self, ip: str) -> bool:
        """Check if IP is in block list."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
        return bool(self.r.exists(f"{self.prefix}:blocked:{ip_hash}"))

    def get_top_offenders(self, count: int = 10) -> list:
        """Get IPs with highest request rates (for dashboard)."""
        # This requires a separate tracking sorted set
        return self.r.zrevrange(f"{self.prefix}:top_ips", 0, count - 1, withscores=True)
```

---

## 14. Production Monitoring and Observability

```python
import redis
import time
import json
from dataclasses import dataclass
from typing import Optional


class RateLimitMonitor:
    """
    Tracks rate limiting metrics for observability.
    
    Key metrics:
    - Total requests checked
    - Total requests rejected (and by which tier)
    - Rejection rate over time
    - Top rate-limited keys
    - Average retry_after values
    - Health of the rate limiting system itself
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "rl:metrics"):
        self.r = redis_client
        self.prefix = prefix

    def record_decision(
        self,
        key: str,
        allowed: bool,
        tier: str,
        latency_ms: float,
    ) -> None:
        """Record a rate limit decision for monitoring."""
        now = time.time()
        minute_bucket = int(now // 60) * 60

        pipe = self.r.pipeline()

        # Total counters
        pipe.incr(f"{self.prefix}:total:{minute_bucket}")
        pipe.expire(f"{self.prefix}:total:{minute_bucket}", 3600)

        if not allowed:
            pipe.incr(f"{self.prefix}:rejected:{minute_bucket}")
            pipe.expire(f"{self.prefix}:rejected:{minute_bucket}", 3600)

            # Track rejection by tier
            pipe.incr(f"{self.prefix}:rejected:{tier}:{minute_bucket}")
            pipe.expire(f"{self.prefix}:rejected:{tier}:{minute_bucket}", 3600)

            # Top rejected keys (sorted set)
            pipe.zincrby(f"{self.prefix}:top_rejected", 1, key)
            pipe.expire(f"{self.prefix}:top_rejected", 3600)

        # Latency tracking
        pipe.lpush(f"{self.prefix}:latency", str(latency_ms))
        pipe.ltrim(f"{self.prefix}:latency", 0, 999)

        pipe.execute()

    def get_metrics(self, window_minutes: int = 5) -> dict:
        """Get rate limiting metrics for the last N minutes."""
        now = time.time()
        total = 0
        rejected = 0

        pipe = self.r.pipeline()
        for i in range(window_minutes):
            bucket = int((now - i * 60) // 60) * 60
            pipe.get(f"{self.prefix}:total:{bucket}")
            pipe.get(f"{self.prefix}:rejected:{bucket}")

        results = pipe.execute()

        for i in range(0, len(results), 2):
            total += int(results[i] or 0)
            rejected += int(results[i + 1] or 0)

        rejection_rate = (rejected / total * 100) if total > 0 else 0

        # Top rejected keys
        top_rejected = self.r.zrevrange(
            f"{self.prefix}:top_rejected", 0, 9, withscores=True
        )

        # Latency percentiles
        latencies = [float(x) for x in self.r.lrange(f"{self.prefix}:latency", 0, -1)]
        latencies.sort()

        p50 = latencies[len(latencies) // 2] if latencies else 0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

        return {
            "window_minutes": window_minutes,
            "total_requests": total,
            "rejected_requests": rejected,
            "rejection_rate_percent": round(rejection_rate, 2),
            "top_rejected_keys": [
                {"key": k.decode() if isinstance(k, bytes) else k, "count": int(s)}
                for k, s in top_rejected
            ],
            "latency_p50_ms": round(p50, 2),
            "latency_p99_ms": round(p99, 2),
        }


# Prometheus metrics export format
PROMETHEUS_METRICS_TEMPLATE = """
# HELP rate_limit_requests_total Total rate limit checks
# TYPE rate_limit_requests_total counter
rate_limit_requests_total{{status="allowed"}} {allowed}
rate_limit_requests_total{{status="rejected"}} {rejected}

# HELP rate_limit_rejection_rate Current rejection rate percentage
# TYPE rate_limit_rejection_rate gauge
rate_limit_rejection_rate {rejection_rate}

# HELP rate_limit_check_latency_seconds Rate limit check latency
# TYPE rate_limit_check_latency_seconds summary
rate_limit_check_latency_seconds{{quantile="0.5"}} {p50}
rate_limit_check_latency_seconds{{quantile="0.99"}} {p99}
"""
```

---

## 15. Redis Configuration for Rate Limiting

```python
# Optimal Redis configuration for rate limiting workloads

REDIS_RATE_LIMIT_CONFIG = {
    # Connection settings
    "host": "redis-ratelimit.internal",
    "port": 6379,
    "db": 2,  # Separate DB from application cache
    "decode_responses": False,  # Faster for numeric operations

    # Connection pool
    "max_connections": 50,
    "socket_timeout": 0.1,          # 100ms — rate limiting must be fast
    "socket_connect_timeout": 0.5,
    "retry_on_timeout": True,
    "health_check_interval": 30,

    # Cluster settings (if using Redis Cluster)
    # "startup_nodes": [
    #     {"host": "redis-rl-1", "port": 6379},
    #     {"host": "redis-rl-2", "port": 6379},
    #     {"host": "redis-rl-3", "port": 6379},
    # ],
}

# Redis server config (redis.conf) for rate limiting
REDIS_SERVER_CONFIG = """
# Memory
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence: disable for pure rate limiting (speed over durability)
save ""
appendonly no

# Performance
tcp-keepalive 60
timeout 0
hz 100  # Higher than default for faster key expiry processing

# Lua script timeout (rate limit scripts should be fast)
lua-time-limit 100

# Slow log: detect degraded rate limit checks
slowlog-log-slower-than 1000  # 1ms
slowlog-max-len 1000
"""
```

---

## 16. Testing Rate Limiters

```python
import redis
import time
import threading
from unittest.mock import patch


class RateLimiterTestHelper:
    """Utilities for testing rate limiters reliably."""

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client

    def flush_rate_limit_keys(self, prefix: str = "rl:*") -> int:
        """Clear all rate limit keys between tests."""
        keys = list(self.r.scan_iter(match=prefix))
        if keys:
            return self.r.delete(*keys)
        return 0

    def simulate_burst(
        self,
        limiter,
        key: str,
        count: int,
        **kwargs,
    ) -> list:
        """Send N requests as fast as possible, return results."""
        results = []
        for _ in range(count):
            result = limiter.check(key, **kwargs)
            results.append(result)
        return results

    def simulate_sustained_load(
        self,
        limiter,
        key: str,
        rate_per_second: float,
        duration_seconds: float,
        **kwargs,
    ) -> dict:
        """Simulate sustained traffic at a given rate."""
        interval = 1.0 / rate_per_second
        end_time = time.time() + duration_seconds
        allowed = 0
        denied = 0

        while time.time() < end_time:
            result = limiter.check(key, **kwargs)
            if result.allowed:
                allowed += 1
            else:
                denied += 1
            time.sleep(interval)

        return {
            "total": allowed + denied,
            "allowed": allowed,
            "denied": denied,
            "effective_rate": allowed / duration_seconds,
        }

    def simulate_concurrent_clients(
        self,
        limiter,
        key: str,
        num_clients: int,
        requests_per_client: int,
        **kwargs,
    ) -> dict:
        """Test thread safety with concurrent clients."""
        results = {"allowed": 0, "denied": 0}
        lock = threading.Lock()

        def client_worker():
            local_allowed = 0
            local_denied = 0
            for _ in range(requests_per_client):
                result = limiter.check(key, **kwargs)
                if result.allowed:
                    local_allowed += 1
                else:
                    local_denied += 1
            with lock:
                results["allowed"] += local_allowed
                results["denied"] += local_denied

        threads = [
            threading.Thread(target=client_worker) for _ in range(num_clients)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        results["total"] = results["allowed"] + results["denied"]
        return results


# Example test cases
def test_fixed_window_basic():
    """Verify basic fixed window behavior."""
    r = redis.Redis()
    helper = RateLimiterTestHelper(r)
    helper.flush_rate_limit_keys()

    limiter = FixedWindowRateLimiter(r)

    # Should allow up to limit
    results = helper.simulate_burst(limiter, "test_user", 10, limit=10, window_seconds=60)
    allowed = [r for r in results if r.allowed]
    assert len(allowed) == 10

    # 11th request should be denied
    result = limiter.check("test_user", limit=10, window_seconds=60)
    assert not result.allowed
    assert result.retry_after > 0


def test_token_bucket_refill():
    """Verify token bucket refills correctly."""
    r = redis.Redis()
    helper = RateLimiterTestHelper(r)
    helper.flush_rate_limit_keys()

    limiter = TokenBucketLimiter(r)

    # Consume all tokens
    results = helper.simulate_burst(
        limiter, "test_user", 10,
        capacity=10, refill_rate=2.0,
    )
    allowed = [r for r in results if r.allowed]
    assert len(allowed) == 10

    # Wait for refill (5 tokens in 2.5 seconds at rate=2)
    time.sleep(2.5)

    # Should have ~5 tokens available
    results = helper.simulate_burst(
        limiter, "test_user", 5,
        capacity=10, refill_rate=2.0,
    )
    allowed = [r for r in results if r.allowed]
    assert len(allowed) >= 4  # Allow slight timing variance


def test_concurrent_accuracy():
    """Verify rate limiter is accurate under concurrent load."""
    r = redis.Redis()
    helper = RateLimiterTestHelper(r)
    helper.flush_rate_limit_keys()

    limiter = SlidingWindowCounterLimiter(r)

    results = helper.simulate_concurrent_clients(
        limiter, "concurrent_test",
        num_clients=10,
        requests_per_client=20,
        limit=100,
        window_seconds=60,
    )

    # With limit=100, exactly 100 should be allowed regardless of concurrency
    assert results["allowed"] == 100
    assert results["denied"] == 100  # 200 total - 100 allowed
```

---

## 17. Algorithm Selection Decision Framework

```
START → What matters most?

├── Accuracy
│   ├── Must be exact → Sliding Window Log (O(n) memory)
│   ├── ~99.99% accuracy OK → GCRA or Sliding Window Counter
│   └── Approximate OK → Fixed Window (boundary burst issue)
│
├── Burst handling
│   ├── Allow controlled bursts → Token Bucket
│   ├── Smooth output (no bursts) → Leaky Bucket
│   ├── Configurable burst + sustained → GCRA
│   └── No burst control needed → Fixed or Sliding Counter
│
├── Memory constraint
│   ├── Minimal (O(1) per key) → Fixed Window, Sliding Counter, Token/Leaky Bucket, GCRA
│   └── Unlimited → Sliding Window Log
│
├── Implementation complexity
│   ├── Simplest possible → Fixed Window (2 Redis ops)
│   ├── Simple + accurate → Sliding Window Counter (1 Lua script)
│   └── Full-featured → Token Bucket or GCRA (1 Lua script)
│
└── Use case
    ├── API rate limiting → GCRA or Sliding Window Counter
    ├── Login protection → Token Bucket (burst=5, slow refill)
    ├── DDoS protection → Fixed Window (speed matters most)
    ├── Billing quota → Sliding Window Counter + daily/monthly counters
    ├── Smooth processing → Leaky Bucket
    └── Multi-tier → Hierarchical with Sliding Window Counter base
```

---

## 18. Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Rate limiting after auth only | Unauthenticated endpoints vulnerable to DDoS | Add IP-based limits pre-auth |
| Single Redis instance | SPOF for rate limiting | Use Redis Cluster or Sentinel |
| No fail-open mode | Redis outage = total service outage | Default to allowing if Redis unreachable |
| Client-side rate limiting only | Easily bypassed | Always enforce server-side |
| Same limits for all endpoints | Expensive ops under-protected | Per-endpoint cost-based limits |
| No retry-after header | Clients retry immediately in tight loop | Always return Retry-After |
| Blocking on rate limit check | Adds latency to every request | Use async/pipeline, set timeout |
| Rate limit key too broad | Shared IPs (offices, VPNs) affect all users | Use user_id > api_key > IP hierarchy |
| Rate limit key too narrow | Easy to bypass by rotating keys | Combine multiple signals |
| No monitoring | Can't detect misconfiguration or attack | Track rejection rate, alert on anomalies |
| Hard-coded limits | Can't adjust without deploy | Store in Redis/config service, allow dynamic updates |
| No grace period for new limits | Existing clients break instantly | Warn via headers before enforcement |

---

## 19. Rate Limit Headers Reference (RFC Draft)

```
# Standard headers (draft-ietf-httpapi-ratelimit-headers-07)
RateLimit-Limit: 100            # Max requests in window
RateLimit-Remaining: 47         # Remaining in current window  
RateLimit-Reset: 28             # Seconds until window resets
RateLimit-Policy: 100;w=60      # Policy: 100 requests per 60s window

# On rejection (429 response)
Retry-After: 28                 # Seconds to wait before retry

# Extended (non-standard but common)
X-RateLimit-Limit-Day: 10000
X-RateLimit-Remaining-Day: 8432
X-RateLimit-Limit-Month: 1000000
X-RateLimit-Remaining-Month: 876543
```

---

## 20. Performance Benchmarks

Approximate Redis operations per rate limit check:

| Algorithm | Redis Ops (pipeline) | Latency (p99) | Ops/sec (single node) |
|-----------|---------------------|---------------|----------------------|
| Fixed Window | 2 (INCR + EXPIRE) | 0.2ms | 500k+ |
| Sliding Counter | 1 Lua (4 internal ops) | 0.3ms | 300k+ |
| Token Bucket | 1 Lua (3 internal ops) | 0.3ms | 300k+ |
| GCRA | 1 Lua (2 internal ops) | 0.2ms | 400k+ |
| Leaky Bucket | 1 Lua (3 internal ops) | 0.3ms | 300k+ |
| Sliding Log | 1 Lua (3 internal ops) | 0.5-5ms* | 50k-200k* |

*Sliding Log performance degrades with high request volumes due to ZCARD on large sorted sets.

### Redis Cluster Considerations

- All rate limit keys for one entity should hash to the same slot: use `{user_123}:rate` pattern
- Lua scripts must operate on keys in the same hash slot (use KEYS[] properly)
- Cross-slot operations require application-level coordination
- For global rate limits, designate one node or use approximate distributed counting
