# Redis Increment Operations & Atomic Counters

## Core Commands

### INCR / DECR — Single-Step Atomic Operations

```
INCR key          → increments by 1, returns new value
DECR key          → decrements by 1, returns new value
INCRBY key delta  → increments by integer delta
DECRBY key delta  → decrements by integer delta
INCRBYFLOAT key delta → increments by float delta (use sparingly — precision issues)
```

**Atomicity guarantee**: Redis is single-threaded for command execution. INCR is a single operation — no read-modify-write race condition is possible. Two clients calling INCR simultaneously will ALWAYS produce correct sequential increments.

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Basic counter
r.set("page_views:homepage", 0)
new_count = r.incr("page_views:homepage")  # Returns 1
new_count = r.incrby("page_views:homepage", 10)  # Returns 11

# INCR on non-existent key initializes to 0, then increments
r.delete("new_counter")
val = r.incr("new_counter")  # Returns 1 (0 + 1)

# INCR on non-integer value raises error
r.set("name", "hello")
# r.incr("name")  # raises redis.ResponseError: value is not an integer
```

### Why INCR is O(1) and Lock-Free

Redis processes commands sequentially in its event loop. When INCR arrives:
1. Redis reads the value from the key's dict entry (pointer dereference)
2. Parses as int64 (already stored as integer encoding for small values)
3. Adds 1
4. Writes back to same memory location
5. Returns result

No mutex, no CAS loop, no retry — it's a single-threaded sequential execution.

---

## Pattern 1: Real-Time Page View / Event Counters

### Simple Per-Page Counter

```python
import redis
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def track_page_view(page_id: str, user_id: str = None):
    """Track page view with multiple granularities."""
    pipe = r.pipeline()
    
    now = datetime.utcnow()
    date_key = now.strftime("%Y-%m-%d")
    hour_key = now.strftime("%Y-%m-%d:%H")
    minute_key = now.strftime("%Y-%m-%d:%H:%M")
    
    # Total views (all time)
    pipe.incr(f"views:total:{page_id}")
    
    # Daily views
    pipe.incr(f"views:daily:{page_id}:{date_key}")
    
    # Hourly views (for real-time dashboard)
    pipe.incr(f"views:hourly:{page_id}:{hour_key}")
    
    # Per-minute views (for spike detection)
    pipe.incr(f"views:minute:{page_id}:{minute_key}")
    pipe.expire(f"views:minute:{page_id}:{minute_key}", 3600)  # 1 hour retention
    
    # Unique viewers using HyperLogLog
    if user_id:
        pipe.pfadd(f"views:unique:{page_id}:{date_key}", user_id)
    
    results = pipe.execute()
    
    return {
        "total": results[0],
        "daily": results[1],
        "hourly": results[2],
        "minute": results[3],
    }


def get_page_stats(page_id: str):
    """Get current page statistics."""
    now = datetime.utcnow()
    date_key = now.strftime("%Y-%m-%d")
    hour_key = now.strftime("%Y-%m-%d:%H")
    
    pipe = r.pipeline()
    pipe.get(f"views:total:{page_id}")
    pipe.get(f"views:daily:{page_id}:{date_key}")
    pipe.get(f"views:hourly:{page_id}:{hour_key}")
    pipe.pfcount(f"views:unique:{page_id}:{date_key}")
    
    results = pipe.execute()
    
    return {
        "total_views": int(results[0] or 0),
        "today_views": int(results[1] or 0),
        "this_hour_views": int(results[2] or 0),
        "unique_visitors_today": results[3],
    }
```

### High-Throughput Counter with Local Buffering

When you have 100K+ increments/second, even Redis pipeline overhead matters. Buffer locally and flush periodically:

```python
import redis
import threading
import time
from collections import defaultdict

class BufferedCounter:
    """
    Buffers increments locally and flushes to Redis periodically.
    
    Trade-off: Slight staleness (up to flush_interval_ms) in exchange for
    dramatically reduced Redis round-trips. If the process crashes between
    flushes, buffered counts are lost.
    
    Use when:
    - Exact real-time accuracy is not critical
    - Throughput > 10K increments/sec per key
    - Acceptable to lose up to flush_interval worth of counts on crash
    """
    
    def __init__(self, redis_client, flush_interval_ms=1000, max_buffer_size=10000):
        self.r = redis_client
        self.flush_interval = flush_interval_ms / 1000.0
        self.max_buffer_size = max_buffer_size
        self.buffer = defaultdict(int)
        self.lock = threading.Lock()
        self._start_flush_thread()
    
    def incr(self, key: str, amount: int = 1):
        with self.lock:
            self.buffer[key] += amount
            if len(self.buffer) >= self.max_buffer_size:
                self._flush()
    
    def _flush(self):
        if not self.buffer:
            return
        
        with self.lock:
            to_flush = dict(self.buffer)
            self.buffer.clear()
        
        pipe = self.r.pipeline(transaction=False)  # Non-transactional for speed
        for key, delta in to_flush.items():
            pipe.incrby(key, delta)
        pipe.execute()
    
    def _start_flush_thread(self):
        def flush_loop():
            while True:
                time.sleep(self.flush_interval)
                self._flush()
        
        t = threading.Thread(target=flush_loop, daemon=True)
        t.start()


# Usage
r = redis.Redis(host='localhost', port=6379)
counter = BufferedCounter(r, flush_interval_ms=500)

# These buffer locally — only one Redis call every 500ms
for i in range(100000):
    counter.incr("high_throughput:events")
```

---

## Pattern 2: API Quota / Rate Counters

### Fixed Window Counter

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def check_rate_limit_fixed_window(user_id: str, limit: int = 100, window_seconds: int = 60) -> dict:
    """
    Fixed window rate limiter using INCR + EXPIRE.
    
    Limitation: Boundary problem — a user can make 100 requests at 0:59
    and another 100 at 1:01, effectively 200 in 2 seconds spanning the window boundary.
    """
    window_key = int(time.time() // window_seconds)
    key = f"ratelimit:{user_id}:{window_key}"
    
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds + 1)  # +1 for safety margin
    results = pipe.execute()
    
    current_count = results[0]
    
    return {
        "allowed": current_count <= limit,
        "current": current_count,
        "limit": limit,
        "remaining": max(0, limit - current_count),
        "reset_at": (window_key + 1) * window_seconds,
    }
```

### Sliding Window Counter (Lua-based)

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Remove entries outside the window
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

-- Count current entries
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add current request
    redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
    redis.call('EXPIRE', key, window)
    return {1, count + 1, limit - count - 1}  -- allowed, current, remaining
else
    return {0, count, 0}  -- denied, current, remaining
end
"""

def check_rate_limit_sliding_window(user_id: str, limit: int = 100, window_seconds: int = 60) -> dict:
    """
    Sliding window rate limiter using sorted sets.
    
    Each request is stored as a member with its timestamp as score.
    Old entries are pruned on each check. More memory-intensive than
    fixed window but eliminates the boundary problem.
    """
    key = f"ratelimit:sliding:{user_id}"
    now = time.time()
    
    result = r.execute_command(
        "EVAL", SLIDING_WINDOW_LUA, 1, key,
        str(window_seconds), str(limit), str(now)
    )
    
    return {
        "allowed": bool(result[0]),
        "current": result[1],
        "remaining": result[2],
    }
```

### Token Bucket with INCR

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per second
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    -- Initialize bucket
    tokens = max_tokens
    last_refill = now
end

-- Calculate tokens to add based on elapsed time
local elapsed = now - last_refill
local new_tokens = elapsed * refill_rate
tokens = math.min(max_tokens, tokens + new_tokens)

local allowed = 0
local wait_time = 0

if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
else
    -- How long until enough tokens are available
    wait_time = (requested - tokens) / refill_rate
end

-- Update bucket state
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 10)

return {allowed, math.floor(tokens), math.ceil(wait_time * 1000)}
"""

def token_bucket_check(user_id: str, max_tokens: int = 100, refill_rate: float = 10, cost: int = 1) -> dict:
    """
    Token bucket rate limiter.
    
    - max_tokens: Maximum burst capacity
    - refill_rate: Tokens added per second
    - cost: Tokens consumed per request (use higher cost for expensive operations)
    
    Advantage over fixed/sliding window: Allows bursts up to max_tokens
    while maintaining a steady-state rate of refill_rate requests/second.
    """
    key = f"tokenbucket:{user_id}"
    now = time.time()
    
    result = r.execute_command(
        "EVAL", TOKEN_BUCKET_LUA, 1, key,
        str(max_tokens), str(refill_rate), str(now), str(cost)
    )
    
    return {
        "allowed": bool(result[0]),
        "tokens_remaining": result[1],
        "retry_after_ms": result[2],
    }
```

---

## Pattern 3: Distributed Counters (Sharded)

When a single key becomes a hotspot (>100K ops/sec on one key), shard the counter:

```python
import redis
import random
import hashlib

class ShardedCounter:
    """
    Shards a single logical counter across N Redis keys.
    
    Write: Randomly pick a shard and INCRBY on it → O(1)
    Read: Sum all shards → O(num_shards)
    
    Use when:
    - Single key throughput > 100K ops/sec
    - Write-heavy workload (reads can tolerate O(N) sum)
    - Exact real-time reads are not critical (eventual consistency across shards)
    
    Trade-offs:
    - Reads are more expensive (must sum all shards)
    - DECR below zero requires coordination (use Lua)
    - Atomic "read current value" is not possible without MULTI
    """
    
    def __init__(self, redis_client, key_prefix: str, num_shards: int = 16):
        self.r = redis_client
        self.key_prefix = key_prefix
        self.num_shards = num_shards
    
    def incr(self, amount: int = 1):
        """Increment a random shard."""
        shard = random.randint(0, self.num_shards - 1)
        return self.r.incrby(f"{self.key_prefix}:shard:{shard}", amount)
    
    def get(self) -> int:
        """Sum all shards to get total count."""
        pipe = self.r.pipeline()
        for i in range(self.num_shards):
            pipe.get(f"{self.key_prefix}:shard:{i}")
        results = pipe.execute()
        return sum(int(v or 0) for v in results)
    
    def reset(self):
        """Reset all shards to zero."""
        pipe = self.r.pipeline()
        for i in range(self.num_shards):
            pipe.set(f"{self.key_prefix}:shard:{i}", 0)
        pipe.execute()


# Usage
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
like_counter = ShardedCounter(r, "likes:post:12345", num_shards=16)

# High-throughput writes
like_counter.incr()       # Fast — hits one random shard
like_counter.incr(5)      # Bulk increment

# Read (aggregates all shards)
total_likes = like_counter.get()
```

### Consistent Sharding for Decrement Safety

```python
SAFE_DECR_LUA = """
-- Decrement across shards, ensuring total doesn't go below zero
local prefix = ARGV[1]
local num_shards = tonumber(ARGV[2])
local amount = tonumber(ARGV[3])

-- First, compute the total
local total = 0
for i = 0, num_shards - 1 do
    local val = redis.call('GET', prefix .. ':shard:' .. i)
    total = total + tonumber(val or '0')
end

if total < amount then
    return {0, total}  -- insufficient balance
end

-- Decrement from a shard that has enough
for i = 0, num_shards - 1 do
    local key = prefix .. ':shard:' .. i
    local val = tonumber(redis.call('GET', key) or '0')
    if val >= amount then
        redis.call('DECRBY', key, amount)
        return {1, total - amount}
    end
end

-- Spread across shards if no single shard has enough
local remaining = amount
for i = 0, num_shards - 1 do
    local key = prefix .. ':shard:' .. i
    local val = tonumber(redis.call('GET', key) or '0')
    if val > 0 then
        local to_deduct = math.min(val, remaining)
        redis.call('DECRBY', key, to_deduct)
        remaining = remaining - to_deduct
        if remaining <= 0 then
            return {1, total - amount}
        end
    end
end

return {0, total}  -- shouldn't reach here given total >= amount check above
"""
```

---

## Pattern 4: Unique Event Counting (HyperLogLog)

When you need approximate unique counts with minimal memory:

```python
import redis
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

class UniqueEventCounter:
    """
    Uses HyperLogLog for approximate unique counting.
    
    Memory: 12KB per counter regardless of cardinality
    Accuracy: ±0.81% standard error
    
    Use when:
    - Counting unique users, IPs, sessions
    - Exact count is not required (marketing analytics, dashboards)
    - Memory efficiency matters (millions of counters)
    
    Do NOT use when:
    - Exact count required (billing, compliance)
    - Need to know WHICH elements are in the set (use SET or Bloom filter)
    """
    
    def __init__(self, redis_client, prefix: str):
        self.r = redis_client
        self.prefix = prefix
    
    def add(self, event_type: str, identifier: str, granularity: str = "daily"):
        """Add an identifier to the unique counter."""
        now = datetime.utcnow()
        
        if granularity == "daily":
            time_key = now.strftime("%Y-%m-%d")
        elif granularity == "hourly":
            time_key = now.strftime("%Y-%m-%d:%H")
        elif granularity == "monthly":
            time_key = now.strftime("%Y-%m")
        else:
            time_key = "all"
        
        key = f"{self.prefix}:{event_type}:{time_key}"
        return self.r.pfadd(key, identifier)
    
    def count(self, event_type: str, time_key: str) -> int:
        """Get approximate unique count for a time period."""
        key = f"{self.prefix}:{event_type}:{time_key}"
        return self.r.pfcount(key)
    
    def count_range(self, event_type: str, time_keys: list) -> int:
        """
        Get approximate unique count across multiple time periods.
        PFCOUNT with multiple keys returns the union count.
        """
        keys = [f"{self.prefix}:{event_type}:{tk}" for tk in time_keys]
        return self.r.pfcount(*keys)
    
    def merge(self, dest_key: str, source_keys: list):
        """Merge multiple HLL counters into one (union of unique elements)."""
        self.r.pfmerge(dest_key, *source_keys)


# Usage
counter = UniqueEventCounter(r, "analytics")

# Track unique visitors
counter.add("page_view", user_id="user_123")
counter.add("page_view", user_id="user_456")
counter.add("page_view", user_id="user_123")  # Duplicate — not counted twice

# Get counts
daily_uniques = counter.count("page_view", "2026-05-28")  # ~2
weekly_uniques = counter.count_range("page_view", [
    "2026-05-22", "2026-05-23", "2026-05-24",
    "2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28"
])
```

---

## Pattern 5: Inventory / Stock Counters (Atomic Conditional Decrement)

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

RESERVE_STOCK_LUA = """
local stock_key = KEYS[1]
local reservation_key = KEYS[2]
local quantity = tonumber(ARGV[1])
local reservation_id = ARGV[2]
local ttl = tonumber(ARGV[3])

local current_stock = tonumber(redis.call('GET', stock_key) or '0')

if current_stock < quantity then
    return {0, current_stock}  -- insufficient stock
end

-- Atomically decrement stock and create reservation
redis.call('DECRBY', stock_key, quantity)
redis.call('HSET', reservation_key, reservation_id, quantity)
redis.call('EXPIRE', reservation_key, ttl)

return {1, current_stock - quantity}
"""

RELEASE_STOCK_LUA = """
local stock_key = KEYS[1]
local reservation_key = KEYS[2]
local reservation_id = ARGV[1]

local quantity = tonumber(redis.call('HGET', reservation_key, reservation_id) or '0')
if quantity == 0 then
    return {0, 0}  -- reservation not found or already released
end

-- Return stock and remove reservation
redis.call('INCRBY', stock_key, quantity)
redis.call('HDEL', reservation_key, reservation_id)

return {1, quantity}
"""

class InventoryManager:
    """
    Atomic inventory management with reservation pattern.
    
    Flow:
    1. reserve_stock() — atomically checks and decrements
    2. confirm_order() — removes reservation (stock already decremented)
    3. cancel_order() — returns stock to pool
    
    TTL on reservations prevents stock being locked forever if the
    checkout process crashes. A background job processes expired reservations.
    """
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def set_stock(self, product_id: str, quantity: int):
        """Initialize or reset stock for a product."""
        self.r.set(f"stock:{product_id}", quantity)
    
    def reserve_stock(self, product_id: str, quantity: int, reservation_id: str, ttl: int = 600) -> dict:
        """
        Atomically reserve stock for a pending order.
        TTL ensures reservations expire if not confirmed.
        """
        result = self.r.execute_command(
            "EVAL", RESERVE_STOCK_LUA, 2,
            f"stock:{product_id}", f"reservations:{product_id}",
            str(quantity), reservation_id, str(ttl)
        )
        return {
            "success": bool(result[0]),
            "remaining_stock": result[1],
        }
    
    def confirm_order(self, product_id: str, reservation_id: str):
        """Confirm reservation — just removes the reservation record."""
        self.r.hdel(f"reservations:{product_id}", reservation_id)
    
    def cancel_order(self, product_id: str, reservation_id: str) -> dict:
        """Cancel reservation — returns stock to pool."""
        result = self.r.execute_command(
            "EVAL", RELEASE_STOCK_LUA, 2,
            f"stock:{product_id}", f"reservations:{product_id}",
            reservation_id
        )
        return {
            "success": bool(result[0]),
            "returned_quantity": result[1],
        }
    
    def get_stock(self, product_id: str) -> int:
        """Get available stock (already accounts for reservations)."""
        return int(self.r.get(f"stock:{product_id}") or 0)


# Usage
inventory = InventoryManager(r)
inventory.set_stock("SKU-001", 100)

# User starts checkout
result = inventory.reserve_stock("SKU-001", 2, "order-abc-123", ttl=600)
# {"success": True, "remaining_stock": 98}

# Payment succeeds
inventory.confirm_order("SKU-001", "order-abc-123")

# Or payment fails
inventory.cancel_order("SKU-001", "order-abc-123")
# Stock returns to 100
```

---

## Pattern 6: Atomic Multi-Key Operations

### Transfer Between Counters (Debit/Credit)

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

TRANSFER_LUA = """
local from_key = KEYS[1]
local to_key = KEYS[2]
local amount = tonumber(ARGV[1])

local from_balance = tonumber(redis.call('GET', from_key) or '0')

if from_balance < amount then
    return {0, from_balance, -1}  -- insufficient funds
end

local new_from = redis.call('DECRBY', from_key, amount)
local new_to = redis.call('INCRBY', to_key, amount)

return {1, new_from, new_to}
"""

def transfer(from_account: str, to_account: str, amount: int) -> dict:
    """
    Atomic transfer between two counters.
    
    Uses Lua to ensure:
    1. Balance check and debit happen atomically
    2. No partial state (debit without credit)
    3. No overdraft possible
    """
    result = r.execute_command(
        "EVAL", TRANSFER_LUA, 2,
        f"balance:{from_account}", f"balance:{to_account}",
        str(amount)
    )
    
    return {
        "success": bool(result[0]),
        "from_balance": result[1],
        "to_balance": result[2],
    }


# Usage
r.set("balance:alice", 1000)
r.set("balance:bob", 500)

result = transfer("alice", "bob", 200)
# {"success": True, "from_balance": 800, "to_balance": 700}

result = transfer("alice", "bob", 900)
# {"success": False, "from_balance": 800, "to_balance": -1}
```

---

## Pattern 7: Time-Series Counters with Automatic Rollup

```python
import redis
import time
from datetime import datetime, timedelta

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

class TimeSeriesCounter:
    """
    Multi-granularity time-series counter with automatic TTL-based cleanup.
    
    Stores counts at second, minute, hour, and day granularities.
    Each granularity has its own TTL so older fine-grained data expires
    while coarser aggregates remain.
    
    Granularity → TTL:
    - Second → 1 hour
    - Minute → 24 hours
    - Hour → 30 days
    - Day → 1 year
    """
    
    GRANULARITIES = {
        "second": {"format": "%Y-%m-%d:%H:%M:%S", "ttl": 3600},
        "minute": {"format": "%Y-%m-%d:%H:%M", "ttl": 86400},
        "hour": {"format": "%Y-%m-%d:%H", "ttl": 2592000},
        "day": {"format": "%Y-%m-%d", "ttl": 31536000},
    }
    
    def __init__(self, redis_client, prefix: str):
        self.r = redis_client
        self.prefix = prefix
    
    def record(self, event_type: str, count: int = 1):
        """Record an event at all granularities."""
        now = datetime.utcnow()
        pipe = self.r.pipeline()
        
        for granularity, config in self.GRANULARITIES.items():
            time_bucket = now.strftime(config["format"])
            key = f"{self.prefix}:{event_type}:{granularity}:{time_bucket}"
            pipe.incrby(key, count)
            pipe.expire(key, config["ttl"])
        
        pipe.execute()
    
    def get_range(self, event_type: str, granularity: str, start: datetime, end: datetime) -> list:
        """Get counts for a time range at the specified granularity."""
        config = self.GRANULARITIES[granularity]
        
        # Generate all time buckets in range
        buckets = []
        current = start
        
        if granularity == "second":
            delta = timedelta(seconds=1)
        elif granularity == "minute":
            delta = timedelta(minutes=1)
        elif granularity == "hour":
            delta = timedelta(hours=1)
        else:
            delta = timedelta(days=1)
        
        while current <= end:
            buckets.append(current.strftime(config["format"]))
            current += delta
        
        # Fetch all in one pipeline
        pipe = self.r.pipeline()
        for bucket in buckets:
            pipe.get(f"{self.prefix}:{event_type}:{granularity}:{bucket}")
        results = pipe.execute()
        
        return [
            {"time": bucket, "count": int(val or 0)}
            for bucket, val in zip(buckets, results)
        ]
    
    def get_total(self, event_type: str, granularity: str, time_key: str) -> int:
        """Get count for a single time bucket."""
        key = f"{self.prefix}:{event_type}:{granularity}:{time_key}"
        return int(self.r.get(key) or 0)


# Usage
ts = TimeSeriesCounter(r, "metrics")

# Record events
ts.record("api_requests")
ts.record("api_errors")
ts.record("api_requests", count=5)  # Batch increment

# Query last hour at minute granularity
now = datetime.utcnow()
hour_ago = now - timedelta(hours=1)
data = ts.get_range("api_requests", "minute", hour_ago, now)
```

---

## Pattern 8: Overflow and Boundary Handling

### INCR Limits

Redis integers are 64-bit signed: range is -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807.

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Overflow protection — Redis will return an error, NOT wrap around
r.set("big_counter", "9223372036854775806")
r.incr("big_counter")  # Returns 9223372036854775807 (max int64)
# r.incr("big_counter")  # raises: increment or decrement would overflow

# INCRBYFLOAT precision issues
r.set("float_counter", "0")
r.incrbyfloat("float_counter", 0.1)
r.incrbyfloat("float_counter", 0.1)
r.incrbyfloat("float_counter", 0.1)
val = r.get("float_counter")  # "0.3" — BUT internal representation may drift over millions of ops
```

### Safe Counter with Floor

```python
SAFE_DECR_LUA = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local floor = tonumber(ARGV[2])

local current = tonumber(redis.call('GET', key) or '0')
local new_val = current - amount

if new_val < floor then
    return {0, current}  -- would go below floor
end

redis.call('SET', key, new_val)
return {1, new_val}
"""

def safe_decrement(key: str, amount: int = 1, floor: int = 0) -> dict:
    """Decrement but never go below floor value."""
    result = r.execute_command(
        "EVAL", SAFE_DECR_LUA, 1, key,
        str(amount), str(floor)
    )
    return {
        "success": bool(result[0]),
        "value": result[1],
    }
```

---

## Production Considerations

### Memory Usage

| Pattern | Memory per counter |
|---------|-------------------|
| Simple INCR key | ~72 bytes (key overhead + int encoding) |
| Hash field counter | ~64 bytes per field (amortized in ziplist) |
| HyperLogLog | 12,304 bytes fixed (regardless of cardinality) |
| Sorted set (sliding window) | ~80 bytes per entry |
| Sharded counter (16 shards) | ~1,152 bytes (16 × 72) |

### Key Expiration Strategy

```python
# DON'T: Set expiry on every INCR call (unnecessary overhead)
r.incr("counter")
r.expire("counter", 86400)  # Extra round-trip

# DO: Set expiry only on first creation (INCR returns 1)
val = r.incr("counter:2026-05-28")
if val == 1:
    r.expire("counter:2026-05-28", 172800)  # 2 days retention

# BEST: Use pipeline for atomic incr + conditional expire
pipe = r.pipeline()
pipe.incr("counter:2026-05-28")
pipe.expire("counter:2026-05-28", 172800)
pipe.execute()
# Note: This sets expire on every call, but pipeline makes it one round-trip
```

### Monitoring Counters

```python
# Key metrics to track
COUNTER_METRICS = {
    "redis_counter_incr_total": "Total INCR operations",
    "redis_counter_overflow_total": "Counter overflow attempts",
    "redis_counter_miss_total": "GET on non-existent counters",
    "redis_counter_flush_duration_seconds": "Buffered counter flush time",
    "redis_counter_buffer_size": "Current buffer size (for BufferedCounter)",
}
```

### Common Pitfalls

1. **Key explosion**: Don't create per-second keys without TTL. You'll run out of memory.
2. **INCRBYFLOAT drift**: Floating point accumulates errors. Use integer cents/milliunits instead.
3. **Pipeline vs MULTI**: Use pipeline (non-transactional) for independent counters. Use MULTI only when atomicity between multiple keys is required.
4. **Missing EXPIRE**: Every temporal counter key MUST have a TTL. No exceptions.
5. **Reading stale data**: If you buffer locally, the Redis value is stale until flush. Document this trade-off.

---

## Anti-Patterns

```python
# BAD: Read-modify-write race condition
current = int(r.get("counter"))  # Another client can INCR between these two lines
r.set("counter", current + 1)

# GOOD: Atomic INCR
r.incr("counter")

# BAD: Using WATCH/MULTI for simple increment (overcomplicated)
with r.pipeline() as pipe:
    while True:
        try:
            pipe.watch("counter")
            current = int(pipe.get("counter"))
            pipe.multi()
            pipe.set("counter", current + 1)
            pipe.execute()
            break
        except redis.WatchError:
            continue

# GOOD: Just use INCR
r.incr("counter")

# BAD: String concatenation for unique tracking
r.append("visitors:today", f",{user_id}")  # O(N) to check membership, unbounded growth

# GOOD: Use SET or HyperLogLog
r.sadd("visitors:today", user_id)  # O(1) membership check
r.pfadd("visitors:approx:today", user_id)  # Constant 12KB memory
```
