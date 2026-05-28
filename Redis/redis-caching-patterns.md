# Redis Caching Patterns — Production Deep Dive

## Strategy Comparison Matrix

| Strategy | Consistency | Latency | Write Complexity | Best For |
|----------|------------|---------|-----------------|----------|
| Cache-Aside | Eventual | Low reads | Low | General purpose, read-heavy |
| Read-Through | Eventual | Low reads | Medium | Uniform cache access |
| Write-Through | Strong | Higher writes | Medium | Data that must not be lost |
| Write-Behind | Eventual | Low writes | High | Write-heavy, batch-friendly |
| Refresh-Ahead | Eventual | Lowest reads | High | Predictable hot keys |

---

## 1. Cache-Aside (Lazy Loading)

The most common pattern. Application manages the cache explicitly.

```
READ:  App → Cache? → HIT → return
                    → MISS → DB → write to Cache → return

WRITE: App → DB → invalidate Cache
```

### Why Invalidate, Not Update on Write?

```
Timeline showing race condition with "update cache on write":

Thread A: Read user from DB (version 1)
Thread B: Write user to DB (version 2)  
Thread B: Update cache (version 2)       ← correct momentarily
Thread A: Update cache (version 1)       ← STALE! A's slower write overwrites B

With invalidation:
Thread B: Write user to DB (version 2)
Thread B: Delete cache key
Thread A: Cache miss → reads DB → gets version 2 ← always correct
```

```python
import redis
import json
import hashlib
import time
import threading
from typing import Optional, Any, Callable

class CacheAside:
    """
    Cache-Aside with jittered TTL to prevent synchronized expiration.
    """
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        self.r = redis_client
        self.default_ttl = default_ttl
    
    def get(self, key: str, loader: Callable, ttl: Optional[int] = None) -> Any:
        """Read-through with cache-aside semantics."""
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        
        # Cache miss — load from source
        value = loader()
        if value is not None:
            effective_ttl = ttl or self.default_ttl
            # Add jitter: ±10% to prevent thundering herd on expiration
            jitter = int(effective_ttl * 0.1)
            import random
            actual_ttl = effective_ttl + random.randint(-jitter, jitter)
            self.r.setex(key, actual_ttl, json.dumps(value))
        
        return value
    
    def invalidate(self, key: str) -> None:
        """Delete on write — safer than update."""
        self.r.delete(key)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern. Use sparingly."""
        count = 0
        cursor = 0
        while True:
            cursor, keys = self.r.scan(cursor, match=pattern, count=100)
            if keys:
                self.r.delete(*keys)
                count += len(keys)
            if cursor == 0:
                break
        return count


# Usage
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
cache = CacheAside(r)

def get_user(user_id: int) -> dict:
    return cache.get(
        f"user:{user_id}",
        loader=lambda: db.query("SELECT * FROM users WHERE id = %s", user_id),
        ttl=600
    )

def update_user(user_id: int, data: dict) -> None:
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)
    cache.invalidate(f"user:{user_id}")
```

---

## 2. Read-Through Cache

Cache itself is responsible for loading data on miss. Application only talks to cache.

```python
class ReadThroughCache:
    """
    Cache manages its own data loading via registered loaders.
    Application never talks to DB directly for reads.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self._loaders: dict[str, Callable] = {}
    
    def register_loader(self, prefix: str, loader: Callable, ttl: int = 300):
        """Register a data source for a key prefix."""
        self._loaders[prefix] = {"loader": loader, "ttl": ttl}
    
    def get(self, key: str) -> Optional[Any]:
        """Transparently loads from source on miss."""
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        
        # Find the loader for this key prefix
        prefix = key.split(":")[0]
        config = self._loaders.get(prefix)
        if not config:
            raise ValueError(f"No loader registered for prefix: {prefix}")
        
        # Extract identifier from key
        identifier = key[len(prefix) + 1:]
        value = config["loader"](identifier)
        
        if value is not None:
            self.r.setex(key, config["ttl"], json.dumps(value))
        
        return value
    
    def multi_get(self, keys: list[str]) -> dict[str, Any]:
        """Batch get with automatic loading for misses."""
        results = {}
        values = self.r.mget(keys)
        
        misses = []
        for key, val in zip(keys, values):
            if val is not None:
                results[key] = json.loads(val)
            else:
                misses.append(key)
        
        # Load misses in batch
        for key in misses:
            results[key] = self.get(key)
        
        return results


# Usage
cache = ReadThroughCache(r)
cache.register_loader("user", lambda id: db.get_user(int(id)), ttl=600)
cache.register_loader("product", lambda id: db.get_product(int(id)), ttl=1800)

# Application only knows about cache
user = cache.get("user:42")
product = cache.get("product:100")
```

---

## 3. Write-Through Cache

Every write goes to both cache and DB atomically. Strong consistency at the cost of write latency.

```python
class WriteThroughCache:
    """
    Writes go to DB first, then cache. Guarantees cache freshness.
    Higher write latency but strong consistency.
    """
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.r = redis_client
        self.default_ttl = default_ttl
    
    def write(self, key: str, value: Any, db_writer: Callable, ttl: Optional[int] = None) -> None:
        """Write to DB first, then update cache. DB is source of truth."""
        # DB first — if this fails, cache stays stale (acceptable)
        db_writer(value)
        
        # Update cache
        effective_ttl = ttl or self.default_ttl
        self.r.setex(key, effective_ttl, json.dumps(value))
    
    def read(self, key: str, db_reader: Callable) -> Optional[Any]:
        """Read from cache, fallback to DB."""
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        
        value = db_reader()
        if value is not None:
            self.r.setex(key, self.default_ttl, json.dumps(value))
        return value


# Usage
wt_cache = WriteThroughCache(r)

def save_user_profile(user_id: int, profile: dict):
    wt_cache.write(
        key=f"user:{user_id}:profile",
        value=profile,
        db_writer=lambda v: db.execute(
            "UPDATE users SET profile = %s WHERE id = %s", 
            json.dumps(v), user_id
        ),
        ttl=3600
    )
```

---

## 4. Write-Behind (Write-Back) Cache

Writes go to cache immediately, then asynchronously flushed to DB. Lowest write latency but risk of data loss.

```python
class WriteBehindCache:
    """
    Writes buffered in Redis, flushed to DB in batches.
    Extremely low write latency. Risk: data loss if Redis crashes before flush.
    
    Mitigation: Use Redis AOF with fsync=always for critical data,
    or accept eventual consistency for non-critical writes.
    """
    
    PENDING_QUEUE = "writebehind:pending"
    
    def __init__(self, redis_client: redis.Redis, flush_interval: float = 5.0, 
                 batch_size: int = 100):
        self.r = redis_client
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self._running = False
        self._flush_thread = None
    
    def write(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Write to cache immediately, queue for DB flush."""
        pipe = self.r.pipeline()
        pipe.setex(key, ttl, json.dumps(value))
        pipe.rpush(self.PENDING_QUEUE, json.dumps({
            "key": key,
            "value": value,
            "timestamp": time.time()
        }))
        pipe.execute()
    
    def start_flush_worker(self, db_batch_writer: Callable):
        """Start background thread that flushes to DB."""
        self._running = True
        
        def flush_loop():
            while self._running:
                self._flush_batch(db_batch_writer)
                time.sleep(self.flush_interval)
        
        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _flush_batch(self, db_batch_writer: Callable) -> int:
        """Flush a batch of pending writes to DB."""
        # Atomically pop up to batch_size items
        pipe = self.r.pipeline()
        for _ in range(self.batch_size):
            pipe.lpop(self.PENDING_QUEUE)
        results = pipe.execute()
        
        writes = []
        for item in results:
            if item is not None:
                writes.append(json.loads(item))
        
        if writes:
            try:
                db_batch_writer(writes)
                return len(writes)
            except Exception as e:
                # Re-queue failed writes
                pipe = self.r.pipeline()
                for w in writes:
                    pipe.rpush(self.PENDING_QUEUE, json.dumps(w))
                pipe.execute()
                raise
        return 0
    
    def stop(self):
        self._running = False
        if self._flush_thread:
            self._flush_thread.join()
    
    def pending_count(self) -> int:
        return self.r.llen(self.PENDING_QUEUE)


# Usage
wb_cache = WriteBehindCache(r, flush_interval=2.0, batch_size=50)

def batch_insert_views(writes: list[dict]):
    """Batch insert page views into analytics DB."""
    values = [(w["key"], w["value"]["count"], w["timestamp"]) for w in writes]
    db.executemany("INSERT INTO page_views (page, count, ts) VALUES (%s,%s,%s)", values)

wb_cache.start_flush_worker(batch_insert_views)

# These return instantly — DB write happens later
wb_cache.write("pageview:home", {"count": 1, "user": "abc"})
wb_cache.write("pageview:product:42", {"count": 1, "user": "xyz"})
```

---

## 5. Refresh-Ahead (Predictive Refresh)

Proactively refresh cache entries before they expire, based on recent access patterns.

```python
class RefreshAheadCache:
    """
    Refreshes entries before expiry if they're being actively accessed.
    Near-zero cache miss rate for hot keys.
    
    refresh_threshold: fraction of TTL remaining that triggers refresh.
    e.g., 0.2 means refresh when 20% of TTL remains.
    """
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 600, 
                 refresh_threshold: float = 0.2):
        self.r = redis_client
        self.default_ttl = default_ttl
        self.refresh_threshold = refresh_threshold
        self._refresh_executor = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_queue = "refresh_ahead:queue"
    
    def get(self, key: str, loader: Callable, ttl: Optional[int] = None) -> Optional[Any]:
        """Get with proactive refresh scheduling."""
        cached = self.r.get(key)
        
        if cached is not None:
            # Check if TTL is low enough to trigger refresh
            remaining_ttl = self.r.ttl(key)
            effective_ttl = ttl or self.default_ttl
            
            if remaining_ttl > 0 and remaining_ttl < effective_ttl * self.refresh_threshold:
                # Schedule async refresh — don't block the read
                self._schedule_refresh(key, effective_ttl)
            
            return json.loads(cached)
        
        # Cache miss — synchronous load
        value = loader()
        if value is not None:
            effective_ttl = ttl or self.default_ttl
            self.r.setex(key, effective_ttl, json.dumps(value))
        return value
    
    def _schedule_refresh(self, key: str, ttl: int):
        """Queue key for background refresh. Deduplicated via set."""
        # Use a set to prevent duplicate refresh requests
        self.r.sadd("refresh_ahead:pending", json.dumps({
            "key": key, "ttl": ttl, "scheduled_at": time.time()
        }))
    
    def _refresh_loop(self):
        """Background worker that processes refresh requests."""
        while True:
            item = self.r.spop("refresh_ahead:pending")
            if item:
                data = json.loads(item)
                # Subclass must implement actual refresh logic
                self._do_refresh(data["key"], data["ttl"])
            else:
                time.sleep(0.1)
    
    def _do_refresh(self, key: str, ttl: int):
        """Override in subclass to implement actual data loading."""
        pass
```

---

## 6. Cache Stampede Prevention

### Problem

When a hot key expires, hundreds of concurrent requests all miss simultaneously and hit the database.

### Solution 1: Mutex Lock (Simple)

```python
class MutexCache:
    """
    Only one request loads from DB on cache miss.
    Others wait briefly, then retry from cache.
    """
    
    LOCK_TTL = 5  # seconds
    WAIT_MS = 50  # poll interval
    MAX_WAIT = 3000  # max total wait
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        self.r = redis_client
        self.default_ttl = default_ttl
    
    def get(self, key: str, loader: Callable, ttl: Optional[int] = None) -> Optional[Any]:
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        
        # Try to acquire lock
        lock_key = f"lock:{key}"
        acquired = self.r.set(lock_key, "1", nx=True, ex=self.LOCK_TTL)
        
        if acquired:
            try:
                # Winner loads from DB
                value = loader()
                if value is not None:
                    effective_ttl = ttl or self.default_ttl
                    self.r.setex(key, effective_ttl, json.dumps(value))
                return value
            finally:
                self.r.delete(lock_key)
        else:
            # Losers wait for winner to populate cache
            waited = 0
            while waited < self.MAX_WAIT:
                time.sleep(self.WAIT_MS / 1000)
                waited += self.WAIT_MS
                cached = self.r.get(key)
                if cached is not None:
                    return json.loads(cached)
            
            # Timeout — fall through to DB as last resort
            return loader()
```

### Solution 2: Probabilistic Early Expiration (XFetch)

```python
class ProbabilisticCache:
    """
    XFetch algorithm: probabilistically refresh BEFORE expiration.
    As TTL gets lower, probability of refresh increases.
    Eliminates stampede without locks.
    
    Formula: current_time - (ttl_remaining * beta * ln(random()))  > expiry_time
    beta controls eagerness (higher = earlier refresh). Default: 1.0
    """
    
    def __init__(self, redis_client: redis.Redis, beta: float = 1.0):
        self.r = redis_client
        self.beta = beta
    
    def get(self, key: str, loader: Callable, ttl: int = 300) -> Optional[Any]:
        import random
        import math
        
        cached = self.r.get(key)
        if cached is not None:
            remaining = self.r.ttl(key)
            
            if remaining > 0:
                # XFetch probabilistic check
                delta = ttl - remaining  # time since last set
                random_val = random.random()
                
                if random_val == 0:
                    random_val = 0.0001  # avoid log(0)
                
                threshold = delta - (self.beta * remaining * math.log(random_val))
                
                if threshold < ttl:
                    # Not yet time to refresh
                    return json.loads(cached)
            
            # Probabilistically chosen to refresh (or TTL expired)
            # Fall through to reload
            
            # But first, return stale while refreshing in background
            old_value = json.loads(cached)
            threading.Thread(
                target=self._refresh, args=(key, loader, ttl), daemon=True
            ).start()
            return old_value
        
        # Hard miss
        value = loader()
        if value is not None:
            self.r.setex(key, ttl, json.dumps(value))
        return value
    
    def _refresh(self, key: str, loader: Callable, ttl: int):
        value = loader()
        if value is not None:
            self.r.setex(key, ttl, json.dumps(value))
```

### Solution 3: Stale-While-Revalidate

```python
class StaleWhileRevalidateCache:
    """
    Serve stale data immediately while refreshing in background.
    Uses two TTLs: fresh (serve as-is) and stale (serve but refresh).
    
    Key structure:
      key → serialized value
      key:meta → {"set_at": timestamp, "fresh_until": timestamp, "stale_until": timestamp}
    """
    
    def __init__(self, redis_client: redis.Redis, fresh_ttl: int = 60, stale_ttl: int = 300):
        self.r = redis_client
        self.fresh_ttl = fresh_ttl
        self.stale_ttl = stale_ttl
    
    def get(self, key: str, loader: Callable) -> Optional[Any]:
        pipe = self.r.pipeline()
        pipe.get(key)
        pipe.hgetall(f"{key}:meta")
        value, meta = pipe.execute()
        
        if value is None:
            # Hard miss
            return self._load_and_cache(key, loader)
        
        now = time.time()
        fresh_until = float(meta.get("fresh_until", 0))
        stale_until = float(meta.get("stale_until", 0))
        
        if now < fresh_until:
            # Fresh — serve directly
            return json.loads(value)
        elif now < stale_until:
            # Stale but usable — serve and refresh in background
            threading.Thread(
                target=self._load_and_cache, args=(key, loader), daemon=True
            ).start()
            return json.loads(value)
        else:
            # Expired — synchronous reload
            return self._load_and_cache(key, loader)
    
    def _load_and_cache(self, key: str, loader: Callable) -> Optional[Any]:
        value = loader()
        if value is None:
            return None
        
        now = time.time()
        pipe = self.r.pipeline()
        pipe.setex(key, self.stale_ttl, json.dumps(value))
        pipe.hset(f"{key}:meta", mapping={
            "set_at": str(now),
            "fresh_until": str(now + self.fresh_ttl),
            "stale_until": str(now + self.stale_ttl)
        })
        pipe.expire(f"{key}:meta", self.stale_ttl)
        pipe.execute()
        
        return value
```

---

## 7. Cache Invalidation Strategies

### Event-Driven Invalidation (Pub/Sub)

```python
class EventDrivenInvalidation:
    """
    Services publish invalidation events. Cache listeners react.
    Decouples write path from cache management.
    """
    
    CHANNEL = "cache:invalidate"
    
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self._local_cache = {}  # L1 in-process cache
    
    def publish_invalidation(self, entity: str, entity_id: str, 
                             reason: str = "update"):
        """Called by write path after DB mutation."""
        message = json.dumps({
            "entity": entity,
            "id": entity_id,
            "reason": reason,
            "timestamp": time.time()
        })
        self.r.publish(self.CHANNEL, message)
        # Also delete from Redis directly
        self.r.delete(f"{entity}:{entity_id}")
    
    def start_listener(self, on_invalidate: Callable):
        """Subscribe and react to invalidation events."""
        pubsub = self.r.pubsub()
        pubsub.subscribe(self.CHANNEL)
        
        def listen():
            for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    on_invalidate(data)
                    # Clear local cache
                    local_key = f"{data['entity']}:{data['id']}"
                    self._local_cache.pop(local_key, None)
        
        thread = threading.Thread(target=listen, daemon=True)
        thread.start()


# Usage in write service
invalidator = EventDrivenInvalidation(r)

def update_product(product_id: int, data: dict):
    db.execute("UPDATE products SET ... WHERE id = %s", product_id)
    invalidator.publish_invalidation("product", str(product_id), reason="price_change")
```

### Version-Based Invalidation

```python
class VersionedCache:
    """
    Each entity has a version counter. Cache keys include version.
    Incrementing version makes all old cache entries irrelevant.
    No explicit deletion needed — old versions just expire naturally.
    """
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.r = redis_client
        self.default_ttl = default_ttl
    
    def get(self, entity: str, entity_id: str, loader: Callable) -> Optional[Any]:
        version = self._get_version(entity, entity_id)
        key = f"{entity}:{entity_id}:v{version}"
        
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        
        value = loader()
        if value is not None:
            self.r.setex(key, self.default_ttl, json.dumps(value))
        return value
    
    def invalidate(self, entity: str, entity_id: str) -> int:
        """Increment version — old cached value becomes orphaned."""
        version_key = f"{entity}:{entity_id}:version"
        return self.r.incr(version_key)
    
    def _get_version(self, entity: str, entity_id: str) -> int:
        version_key = f"{entity}:{entity_id}:version"
        version = self.r.get(version_key)
        return int(version) if version else 0


# Usage
vcache = VersionedCache(r)

user = vcache.get("user", "42", loader=lambda: db.get_user(42))

# On update — just bump version
def update_user(user_id, data):
    db.update_user(user_id, data)
    vcache.invalidate("user", str(user_id))
    # Old "user:42:v3" naturally expires, new reads create "user:42:v4"
```

### Tag-Based Invalidation

```python
class TaggedCache:
    """
    Associate cache entries with tags. Invalidate all entries with a given tag.
    Useful for: "invalidate everything related to user 42" across multiple entity types.
    
    Implementation: tags are Redis Sets containing member keys.
    """
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.r = redis_client
        self.default_ttl = default_ttl
    
    def set_with_tags(self, key: str, value: Any, tags: list[str], 
                      ttl: Optional[int] = None):
        """Cache a value and associate it with tags."""
        effective_ttl = ttl or self.default_ttl
        pipe = self.r.pipeline()
        pipe.setex(key, effective_ttl, json.dumps(value))
        
        for tag in tags:
            tag_key = f"tag:{tag}"
            pipe.sadd(tag_key, key)
            pipe.expire(tag_key, effective_ttl + 60)  # tag lives slightly longer
        
        pipe.execute()
    
    def invalidate_tag(self, tag: str) -> int:
        """Delete all cache entries associated with a tag."""
        tag_key = f"tag:{tag}"
        members = self.r.smembers(tag_key)
        
        if members:
            pipe = self.r.pipeline()
            pipe.delete(*members)
            pipe.delete(tag_key)
            pipe.execute()
        
        return len(members)
    
    def get(self, key: str) -> Optional[Any]:
        cached = self.r.get(key)
        return json.loads(cached) if cached else None


# Usage
tc = TaggedCache(r)

# Cache user's profile, orders, and preferences — all tagged with user:42
tc.set_with_tags("user:42:profile", profile_data, tags=["user:42", "profiles"])
tc.set_with_tags("user:42:orders", order_data, tags=["user:42", "orders"])
tc.set_with_tags("user:42:prefs", pref_data, tags=["user:42", "preferences"])

# User changes their account — invalidate EVERYTHING related to them
tc.invalidate_tag("user:42")  # Deletes profile, orders, prefs in one shot
```

---

## 8. Multi-Tier Caching

```python
from functools import lru_cache

class MultiTierCache:
    """
    L1: In-process memory (fastest, smallest, per-instance)
    L2: Redis (fast, shared across instances)
    L3: Database (slow, source of truth)
    
    Read path: L1 → L2 → L3 (populate on miss)
    Write path: DB → invalidate L2 → broadcast invalidation to all L1s
    """
    
    def __init__(self, redis_client: redis.Redis, l1_max_size: int = 1000,
                 l1_ttl: int = 30, l2_ttl: int = 300):
        self.r = redis_client
        self.l1_max_size = l1_max_size
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self._l1: dict[str, dict] = {}  # {key: {"value": ..., "expires_at": ...}}
    
    def get(self, key: str, loader: Callable) -> Optional[Any]:
        # L1 check
        l1_entry = self._l1.get(key)
        if l1_entry and time.time() < l1_entry["expires_at"]:
            return l1_entry["value"]
        
        # L2 check (Redis)
        cached = self.r.get(key)
        if cached is not None:
            value = json.loads(cached)
            self._set_l1(key, value)
            return value
        
        # L3 (database)
        value = loader()
        if value is not None:
            # Populate L2
            self.r.setex(key, self.l2_ttl, json.dumps(value))
            # Populate L1
            self._set_l1(key, value)
        
        return value
    
    def invalidate(self, key: str):
        """Invalidate across all tiers."""
        self._l1.pop(key, None)
        self.r.delete(key)
        # Broadcast to other instances
        self.r.publish("cache:invalidate:l1", key)
    
    def _set_l1(self, key: str, value: Any):
        """Add to L1 with eviction if full."""
        if len(self._l1) >= self.l1_max_size:
            # Evict oldest entry
            oldest_key = min(self._l1, key=lambda k: self._l1[k]["expires_at"])
            del self._l1[oldest_key]
        
        self._l1[key] = {
            "value": value,
            "expires_at": time.time() + self.l1_ttl
        }
    
    def stats(self) -> dict:
        return {
            "l1_size": len(self._l1),
            "l1_max": self.l1_max_size,
        }
```

---

## 9. Cache Warming

```python
class CacheWarmer:
    """
    Pre-populate cache before traffic hits.
    Use cases:
      - After deployment (caches are cold)
      - After Redis restart
      - Before peak traffic window
    """
    
    def __init__(self, redis_client: redis.Redis, batch_size: int = 100):
        self.r = redis_client
        self.batch_size = batch_size
    
    def warm_from_queries(self, queries: list[dict]):
        """
        Warm cache from a list of query specifications.
        Each query: {"key_pattern": "user:{id}", "loader": callable, "ids": [...], "ttl": int}
        """
        for query in queries:
            pattern = query["key_pattern"]
            loader = query["loader"]
            ids = query["ids"]
            ttl = query.get("ttl", 3600)
            
            for i in range(0, len(ids), self.batch_size):
                batch = ids[i:i + self.batch_size]
                pipe = self.r.pipeline()
                
                for entity_id in batch:
                    key = pattern.format(id=entity_id)
                    value = loader(entity_id)
                    if value is not None:
                        pipe.setex(key, ttl, json.dumps(value))
                
                pipe.execute()
    
    def warm_hot_keys(self, hot_keys_source: Callable, loader: Callable, 
                      ttl: int = 3600):
        """
        Warm the most frequently accessed keys.
        hot_keys_source returns list of keys sorted by access frequency.
        """
        hot_keys = hot_keys_source()
        
        pipe = self.r.pipeline()
        count = 0
        
        for key in hot_keys:
            value = loader(key)
            if value is not None:
                pipe.setex(key, ttl, json.dumps(value))
                count += 1
            
            if count % self.batch_size == 0:
                pipe.execute()
                pipe = self.r.pipeline()
        
        if count % self.batch_size != 0:
            pipe.execute()
        
        return count
    
    def warm_from_access_log(self, log_path: str, loader: Callable,
                             ttl: int = 3600, top_n: int = 10000):
        """
        Parse access logs to find hot keys and pre-populate.
        """
        from collections import Counter
        
        key_counts = Counter()
        
        with open(log_path, 'r') as f:
            for line in f:
                # Assumes log format: timestamp key action
                parts = line.strip().split()
                if len(parts) >= 2:
                    key_counts[parts[1]] += 1
        
        # Warm top N keys
        hot_keys = [key for key, _ in key_counts.most_common(top_n)]
        
        pipe = self.r.pipeline()
        for i, key in enumerate(hot_keys):
            value = loader(key)
            if value is not None:
                pipe.setex(key, ttl, json.dumps(value))
            
            if (i + 1) % self.batch_size == 0:
                pipe.execute()
                pipe = self.r.pipeline()
        
        pipe.execute()
        return len(hot_keys)
```

---

## 10. Eviction Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| `noeviction` | Return errors when memory full | Critical data that must not be lost |
| `allkeys-lru` | Evict least recently used | General-purpose caching |
| `allkeys-lfu` | Evict least frequently used | Access patterns with hot/cold keys |
| `volatile-lru` | Evict LRU among keys with TTL | Mix of persistent + cache data |
| `volatile-lfu` | Evict LFU among keys with TTL | Same as above, frequency-based |
| `volatile-ttl` | Evict shortest TTL first | When TTL indicates priority |
| `allkeys-random` | Evict random key | When all keys equal importance |
| `volatile-random` | Evict random key with TTL | Random among expirable keys |

### Configuration Recommendations

```
# redis.conf for a caching workload
maxmemory 4gb
maxmemory-policy allkeys-lfu

# LFU tuning
lfu-log-factor 10       # Higher = slower frequency counter growth
lfu-decay-time 1        # Minutes before frequency counter halves

# For mixed workloads (some persistent, some cache):
# maxmemory-policy volatile-lfu
# Set TTL on cache keys, no TTL on persistent keys
```

---

## 11. Serialization Strategies

```python
import msgpack
import zlib

class JsonSerializer:
    """Human-readable, moderate size. Best for debugging and mixed-type data."""
    
    def serialize(self, value: Any) -> bytes:
        return json.dumps(value).encode('utf-8')
    
    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode('utf-8'))


class MsgpackSerializer:
    """Binary format, 20-30% smaller than JSON, 2-3x faster."""
    
    def serialize(self, value: Any) -> bytes:
        return msgpack.packb(value, use_bin_type=True)
    
    def deserialize(self, data: bytes) -> Any:
        return msgpack.unpackb(data, raw=False)


class CompressedSerializer:
    """For large values. Adds CPU cost but saves memory/network."""
    
    def __init__(self, level: int = 6):
        self.level = level
        self._inner = MsgpackSerializer()
    
    def serialize(self, value: Any) -> bytes:
        raw = self._inner.serialize(value)
        return zlib.compress(raw, self.level)
    
    def deserialize(self, data: bytes) -> Any:
        raw = zlib.decompress(data)
        return self._inner.deserialize(raw)


# Benchmark comparison (1000 user objects):
# | Serializer     | Size (bytes) | Serialize (ms) | Deserialize (ms) |
# |----------------|-------------|----------------|------------------|
# | JSON           | 152,000     | 12.3           | 8.7              |
# | msgpack        | 108,000     | 4.1            | 3.2              |
# | compressed     | 42,000      | 18.5           | 9.1              |
#
# Rule of thumb:
# - Small values (<1KB): JSON (readability wins)
# - Medium values (1-100KB): msgpack (speed + size)
# - Large values (>100KB): compressed msgpack (memory savings)
```

---

## 12. TTL Strategy Patterns

```python
import random
import math

class TTLStrategy:
    """Collection of TTL strategies for different scenarios."""
    
    @staticmethod
    def fixed(seconds: int) -> int:
        """Simple fixed TTL. Use when expiry time is a business rule."""
        return seconds
    
    @staticmethod
    def jittered(base_seconds: int, jitter_pct: float = 0.1) -> int:
        """
        Prevent thundering herd from synchronized expiration.
        100 keys all set at once with TTL=300 all expire at same second.
        With 10% jitter: they expire between 270-330, spreading the load.
        """
        jitter = int(base_seconds * jitter_pct)
        return base_seconds + random.randint(-jitter, jitter)
    
    @staticmethod
    def adaptive(base_seconds: int, access_frequency: float) -> int:
        """
        Hot keys get longer TTL (they'll be accessed again soon anyway).
        Cold keys get shorter TTL (free up memory faster).
        
        access_frequency: accesses per minute
        """
        if access_frequency > 100:
            return base_seconds * 4  # Very hot
        elif access_frequency > 10:
            return base_seconds * 2  # Warm
        elif access_frequency > 1:
            return base_seconds      # Normal
        else:
            return base_seconds // 2  # Cold
    
    @staticmethod
    def time_aware(base_seconds: int) -> int:
        """
        Shorter TTL during business hours (data changes often).
        Longer TTL during off-hours (data is stable).
        """
        import datetime
        hour = datetime.datetime.now().hour
        
        if 9 <= hour <= 18:  # Business hours
            return base_seconds
        else:  # Off hours
            return base_seconds * 3
    
    @staticmethod
    def cascade(entity_type: str) -> int:
        """
        Different entities have different staleness tolerance.
        Configuration: how stale can this data be?
        """
        ttl_map = {
            "user_session": 1800,      # 30 min — security sensitive
            "user_profile": 3600,       # 1 hour — changes occasionally
            "product_listing": 300,     # 5 min — prices change
            "product_catalog": 86400,   # 24 hours — rarely changes
            "feature_flags": 60,        # 1 min — must propagate quickly
            "static_content": 604800,   # 7 days — almost never changes
        }
        return ttl_map.get(entity_type, 3600)
```

---

## 13. Production Monitoring

```python
class CacheMonitor:
    """
    Track cache effectiveness metrics.
    Export to Prometheus/Datadog for alerting.
    """
    
    def __init__(self, redis_client: redis.Redis, namespace: str = "app"):
        self.r = redis_client
        self.namespace = namespace
        self._hits = 0
        self._misses = 0
    
    def record_hit(self, key_prefix: str):
        self._hits += 1
        self.r.hincrby(f"metrics:{self.namespace}:cache", f"hits:{key_prefix}", 1)
    
    def record_miss(self, key_prefix: str):
        self._misses += 1
        self.r.hincrby(f"metrics:{self.namespace}:cache", f"misses:{key_prefix}", 1)
    
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def get_stats(self) -> dict:
        """Get comprehensive cache statistics."""
        info = self.r.info("stats")
        memory = self.r.info("memory")
        
        return {
            "hit_rate": self.hit_rate(),
            "total_hits": self._hits,
            "total_misses": self._misses,
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "evicted_keys": info.get("evicted_keys", 0),
            "used_memory_mb": memory.get("used_memory", 0) / 1024 / 1024,
            "max_memory_mb": memory.get("maxmemory", 0) / 1024 / 1024,
            "memory_fragmentation_ratio": memory.get("mem_fragmentation_ratio", 0),
            "connected_clients": self.r.info("clients").get("connected_clients", 0),
        }
    
    def detect_slow_keys(self, threshold_ms: float = 10.0) -> list[dict]:
        """Find keys with high access latency using SLOWLOG."""
        slow_logs = self.r.slowlog_get(50)
        slow_keys = []
        
        for entry in slow_logs:
            duration_ms = entry.get("duration", 0) / 1000
            if duration_ms > threshold_ms:
                slow_keys.append({
                    "command": entry.get("command", b"").decode() if isinstance(entry.get("command"), bytes) else str(entry.get("command", "")),
                    "duration_ms": duration_ms,
                    "timestamp": entry.get("start_time", 0),
                })
        
        return slow_keys


# Prometheus alert rules for cache health:
#
# - alert: CacheHitRateLow
#   expr: cache_hit_rate < 0.8
#   for: 5m
#   labels:
#     severity: warning
#   annotations:
#     summary: "Cache hit rate below 80%"
#
# - alert: CacheEvictionHigh
#   expr: rate(redis_evicted_keys_total[5m]) > 100
#   for: 5m
#   labels:
#     severity: critical
#   annotations:
#     summary: "Redis evicting >100 keys/sec — increase maxmemory"
#
# - alert: CacheMemoryHigh
#   expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
#   for: 5m
#   labels:
#     severity: warning
#   annotations:
#     summary: "Redis memory usage above 90%"
```

---

## 14. Anti-Patterns

| Anti-Pattern | Problem | Solution |
|-------------|---------|----------|
| Cache everything | Memory exhaustion, eviction of hot keys | Cache only repeated reads with measurable latency savings |
| No TTL | Stale data forever, memory never freed | Always set TTL, even if long (7 days) |
| Same TTL everywhere | Thundering herd on mass expiration | Use jittered TTL |
| Updating cache on write | Race condition between readers and writers | Invalidate (delete) on write |
| Fat cache keys | Wasted memory, slow serialization | Store only what's needed, not full objects |
| No monitoring | Blind to cache degradation | Track hit rate, evictions, memory |
| Caching errors | Serving errors to all users | Never cache null/error responses (or very short TTL) |
| Complex invalidation | Bugs from inconsistent invalidation logic | Use simple patterns: delete on write, version bump |

---

## 15. Production Configuration

```
# redis.conf — optimized for caching workload

# Memory
maxmemory 8gb
maxmemory-policy allkeys-lfu

# Persistence (for caching: disable or use lightweight)
save ""
appendonly no
# If you need crash recovery:
# appendonly yes
# appendfsync everysec

# Performance
tcp-keepalive 300
timeout 300
tcp-backlog 511

# Clients
maxclients 10000

# Slow log
slowlog-log-slower-than 10000  # 10ms
slowlog-max-len 128

# Key expiration
hz 10  # Higher = more accurate expiration, more CPU
# For heavy expiration workloads:
# hz 100
# dynamic-hz yes

# Snapshotting disabled for pure cache
rdbcompression no
rdbchecksum no
```

---

## 16. Key Naming Conventions

```
Pattern: {service}:{entity}:{identifier}:{field}

Examples:
  user-svc:user:42:profile          → User profile
  user-svc:user:42:orders           → User's order list
  product-svc:product:100:detail    → Product detail
  product-svc:catalog:electronics   → Category listing
  auth-svc:session:abc123           → Session data
  auth-svc:rate:login:10.0.1.5     → Rate limit counter
  cache:user:42:v3                  → Versioned cache entry
  lock:user:42                      → Distributed lock
  tag:user:42                       → Tag membership set

Rules:
  - Use colons as separators (Redis convention, enables keyspace notifications)
  - Include service prefix in multi-service environments
  - Keep keys short but readable (memory overhead per key is real)
  - Use consistent patterns team-wide (document in team wiki)
  - Avoid spaces, newlines, or very long keys (>512 bytes wastes memory)
```

---

## 17. Sizing and Capacity Planning

```
Formula:
  Required Memory = (avg_value_size + avg_key_size + 80 bytes overhead) × num_keys × overhead_factor

Overhead factor: ~1.5x (accounts for fragmentation, hash table, pointers)

Example:
  - 10M user profiles, avg 500 bytes each
  - Key size: ~20 bytes ("user:12345678:profile")
  - Per-key overhead: ~80 bytes (Redis object headers + dict entry)
  
  Raw: (500 + 20 + 80) × 10,000,000 = 6 GB
  With overhead: 6 GB × 1.5 = 9 GB
  Recommendation: 12 GB maxmemory (headroom for spikes)

Monitoring thresholds:
  - 70% memory: scale alert — plan capacity increase
  - 85% memory: warning — evictions starting
  - 95% memory: critical — degraded performance, high eviction rate
```

---

## 18. Decision Framework

```
Should I cache this?

                    ┌─────────────────────────────────┐
                    │ Is the data read more than once? │
                    └───────────────┬─────────────────┘
                                    │
                            Yes     │     No
                            ┌───────┴───────┐
                            │               │
                    ┌───────▼──────┐   Don't cache
                    │ Is latency   │
                    │ a problem?   │
                    └───────┬──────┘
                            │
                    Yes     │     No
                    ┌───────┴───────┐
                    │               │
            ┌───────▼──────┐   Probably don't cache
            │ Can you       │   (measure first)
            │ tolerate      │
            │ staleness?    │
            └───────┬──────┘
                    │
            Yes     │     No
            ┌───────┴───────┐
            │               │
    ┌───────▼──────┐  ┌─────▼──────────┐
    │ Cache-Aside  │  │ Write-Through   │
    │ (most cases) │  │ (consistency    │
    │              │  │  critical)      │
    └──────────────┘  └────────────────┘
    
Which pattern?
  - Read-heavy, tolerant of staleness → Cache-Aside + jittered TTL
  - Read-heavy, consistency critical → Write-Through + short TTL
  - Write-heavy, batch-friendly → Write-Behind
  - Predictable hot keys → Refresh-Ahead
  - Unpredictable access → Cache-Aside + LFU eviction
```
