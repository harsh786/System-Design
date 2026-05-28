# Redis Probabilistic Data Structures — Deep Dive

## Overview

Probabilistic data structures trade perfect accuracy for dramatic savings in memory and computation. Redis provides native HyperLogLog and supports Bloom filters, Count-Min Sketch, Top-K, and Cuckoo filters through the RedisBloom module. These structures are essential for high-scale systems where exact answers are impractical.

---

## 1. HyperLogLog (Native Redis)

### Concept

HyperLogLog estimates cardinality (count of unique elements) using only ~12KB of memory regardless of the number of elements. It achieves a standard error of 0.81%.

**Key insight:** Instead of storing every element, HLL observes the distribution of leading zeros in hashed values. The more leading zeros observed, the more unique elements likely exist.

```
Element → Hash → Binary → Count leading zeros
"user:1001" → 0x3A7F → 0011101001111111 → 2 leading zeros
"user:9999" → 0x007B → 0000000001111011 → 9 leading zeros (rare = many uniques)
```

### Core Operations

```python
import redis
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional


class HyperLogLogCounter:
    """
    Production HyperLogLog implementation for unique counting.
    
    Use cases:
    - Unique visitors per page/day
    - Unique search queries
    - Unique IP addresses
    - Unique events per user
    """

    def __init__(self, r: redis.Redis, namespace: str = "hll"):
        self.r = r
        self.ns = namespace

    def _key(self, metric: str, granularity: str, bucket: str) -> str:
        return f"{self.ns}:{metric}:{granularity}:{bucket}"

    # ─── Basic Counting ───────────────────────────────────────────

    def add(self, metric: str, *elements: str) -> int:
        """
        Add elements to a HyperLogLog counter.
        Returns 1 if the internal state was modified, 0 otherwise.
        """
        now = datetime.utcnow()
        pipe = self.r.pipeline()

        # Multi-granularity tracking
        keys = [
            self._key(metric, "minute", now.strftime("%Y%m%d%H%M")),
            self._key(metric, "hour", now.strftime("%Y%m%d%H")),
            self._key(metric, "day", now.strftime("%Y%m%d")),
            self._key(metric, "month", now.strftime("%Y%m")),
        ]

        for key in keys:
            pipe.pfadd(key, *elements)

        # Set TTLs: minute=2h, hour=3d, day=90d, month=2y
        ttls = [7200, 259200, 7776000, 63072000]
        for key, ttl in zip(keys, ttls):
            pipe.expire(key, ttl)

        results = pipe.execute()
        return results[0]  # Return first PFADD result

    def count(self, metric: str, granularity: str, bucket: str) -> int:
        """Get estimated unique count for a specific bucket."""
        key = self._key(metric, granularity, bucket)
        return self.r.pfcount(key)

    def count_range(self, metric: str, granularity: str, buckets: list) -> int:
        """
        Merge multiple HLLs and return combined unique count.
        
        Example: unique visitors across multiple days
        """
        keys = [self._key(metric, granularity, b) for b in buckets]
        existing = [k for k in keys if self.r.exists(k)]
        if not existing:
            return 0
        return self.r.pfcount(*existing)

    # ─── Time-Window Aggregation ──────────────────────────────────

    def unique_last_n_hours(self, metric: str, hours: int) -> int:
        """Count uniques over the last N hours by merging hourly HLLs."""
        now = datetime.utcnow()
        buckets = []
        for i in range(hours):
            t = now - timedelta(hours=i)
            buckets.append(t.strftime("%Y%m%d%H"))
        return self.count_range(metric, "hour", buckets)

    def unique_last_n_days(self, metric: str, days: int) -> int:
        """Count uniques over the last N days by merging daily HLLs."""
        now = datetime.utcnow()
        buckets = []
        for i in range(days):
            t = now - timedelta(days=i)
            buckets.append(t.strftime("%Y%m%d"))
        return self.count_range(metric, "day", buckets)

    # ─── Merge and Persist ────────────────────────────────────────

    def merge_into(self, dest_metric: str, dest_gran: str, dest_bucket: str,
                   source_keys: list) -> bool:
        """
        Merge multiple HLL keys into a destination.
        Useful for rollup jobs (e.g., hourly → daily).
        """
        dest_key = self._key(dest_metric, dest_gran, dest_bucket)
        existing = [k for k in source_keys if self.r.exists(k)]
        if not existing:
            return False
        self.r.pfmerge(dest_key, *existing)
        return True

    def rollup_hours_to_day(self, metric: str, date_str: str):
        """Roll up 24 hourly HLLs into one daily HLL."""
        source_keys = []
        for hour in range(24):
            key = self._key(metric, "hour", f"{date_str}{hour:02d}")
            source_keys.append(key)
        dest_key = self._key(metric, "day", date_str)
        existing = [k for k in source_keys if self.r.exists(k)]
        if existing:
            self.r.pfmerge(dest_key, *existing)
            self.r.expire(dest_key, 7776000)  # 90 days


class UniqueVisitorTracker:
    """
    Real-world unique visitor tracking with HyperLogLog.
    
    Tracks:
    - Per-page uniques
    - Per-section uniques
    - Site-wide uniques
    - Cross-device uniques (via user ID when authenticated)
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.hll = HyperLogLogCounter(r, "uv")

    def track_pageview(self, page_path: str, visitor_id: str,
                       user_id: Optional[str] = None):
        """Track a pageview from a visitor."""
        pipe = self.r.pipeline()
        today = datetime.utcnow().strftime("%Y%m%d")

        # Page-level uniques
        page_key = f"uv:page:{page_path}:day:{today}"
        pipe.pfadd(page_key, visitor_id)
        pipe.expire(page_key, 7776000)

        # Site-wide uniques
        site_key = f"uv:site:day:{today}"
        pipe.pfadd(site_key, visitor_id)
        pipe.expire(site_key, 7776000)

        # Section-level (first path segment)
        section = page_path.strip("/").split("/")[0] if "/" in page_path else page_path
        section_key = f"uv:section:{section}:day:{today}"
        pipe.pfadd(section_key, visitor_id)
        pipe.expire(section_key, 7776000)

        # Authenticated user tracking (cross-device)
        if user_id:
            auth_key = f"uv:auth:day:{today}"
            pipe.pfadd(auth_key, user_id)
            pipe.expire(auth_key, 7776000)

        pipe.execute()

    def get_page_uniques(self, page_path: str, date_str: str) -> int:
        return self.r.pfcount(f"uv:page:{page_path}:day:{date_str}")

    def get_site_uniques_range(self, days: int) -> int:
        """Get site-wide uniques over a date range (merged)."""
        now = datetime.utcnow()
        keys = []
        for i in range(days):
            d = (now - timedelta(days=i)).strftime("%Y%m%d")
            key = f"uv:site:day:{d}"
            keys.append(key)
        existing = [k for k in keys if self.r.exists(k)]
        if not existing:
            return 0
        return self.r.pfcount(*existing)


class ABTestUniqueTracker:
    """
    Track unique participants per A/B test variant using HLL.
    
    Memory: ~12KB per variant vs millions of user IDs in a set.
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def record_exposure(self, experiment_id: str, variant: str, user_id: str):
        key = f"ab:exposure:{experiment_id}:{variant}"
        self.r.pfadd(key, user_id)

    def record_conversion(self, experiment_id: str, variant: str, user_id: str):
        key = f"ab:conversion:{experiment_id}:{variant}"
        self.r.pfadd(key, user_id)

    def get_stats(self, experiment_id: str, variants: list) -> dict:
        results = {}
        pipe = self.r.pipeline()
        for v in variants:
            pipe.pfcount(f"ab:exposure:{experiment_id}:{v}")
            pipe.pfcount(f"ab:conversion:{experiment_id}:{v}")
        counts = pipe.execute()

        for i, v in enumerate(variants):
            exposures = counts[i * 2]
            conversions = counts[i * 2 + 1]
            rate = conversions / exposures if exposures > 0 else 0
            results[v] = {
                "exposures": exposures,
                "conversions": conversions,
                "conversion_rate": round(rate, 4),
            }
        return results
```

### HyperLogLog Internals

```
┌─────────────────────────────────────────────────────────┐
│                    HyperLogLog (12KB)                     │
├─────────────────────────────────────────────────────────┤
│  16384 registers (6 bits each) = 12288 bytes            │
│                                                          │
│  Element → Hash(64-bit) → Split into:                   │
│    ┌──────────┬─────────────────────────────────────┐   │
│    │ 14 bits  │         50 bits                      │   │
│    │ register │   count leading zeros + 1            │   │
│    │ index    │   (position of first 1)              │   │
│    └──────────┴─────────────────────────────────────┘   │
│                                                          │
│  register[index] = max(register[index], leading_zeros)  │
│                                                          │
│  Estimate = α * m² / Σ(2^(-register[j]))               │
│    where m = 16384, α = correction constant              │
├─────────────────────────────────────────────────────────┤
│  Properties:                                             │
│  • Standard error: 0.81% (1.04 / √m)                   │
│  • Memory: always 12KB (dense) or less (sparse)         │
│  • Mergeable: PFMERGE combines any number of HLLs       │
│  • No deletion: elements cannot be removed              │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Bloom Filters (RedisBloom Module)

### Concept

A Bloom filter answers "is X in the set?" with:
- **Definitely NOT in set** (no false negatives)
- **Probably in set** (configurable false positive rate)

Uses multiple hash functions to set bits in a bit array. Zero memory per element (just bits).

### Implementation

```python
import redis
import math
import struct
from typing import List, Tuple


class BloomFilterEngine:
    """
    Production Bloom filter using RedisBloom (BF.*) commands.
    
    Use cases:
    - Username/email existence check (avoid DB query)
    - URL deduplication in web crawlers
    - Spam detection (known spam fingerprints)
    - Cache penetration prevention
    - Recommendation filtering (already seen items)
    """

    def __init__(self, r: redis.Redis, namespace: str = "bf"):
        self.r = r
        self.ns = namespace

    # ─── Filter Lifecycle ─────────────────────────────────────────

    def create_filter(self, name: str, expected_items: int,
                      false_positive_rate: float = 0.01,
                      expansion: int = 2) -> bool:
        """
        Create a scalable Bloom filter.
        
        Args:
            expected_items: Expected number of unique items
            false_positive_rate: Acceptable false positive rate (0.01 = 1%)
            expansion: Growth factor when filter fills up
            
        Memory estimation:
            bits = -n * ln(p) / (ln(2))²
            bytes ≈ bits / 8
            
            1M items at 1% FPR ≈ 1.2MB
            10M items at 0.1% FPR ≈ 18MB
            100M items at 1% FPR ≈ 120MB
        """
        key = f"{self.ns}:{name}"
        try:
            self.r.execute_command(
                "BF.RESERVE", key,
                false_positive_rate,
                expected_items,
                "EXPANSION", expansion
            )
            return True
        except redis.ResponseError as e:
            if "item exists" in str(e):
                return False  # Filter already exists
            raise

    def add(self, name: str, item: str) -> bool:
        """Add item to filter. Returns True if item is new."""
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("BF.ADD", key, item))

    def add_multi(self, name: str, items: List[str]) -> List[bool]:
        """Add multiple items atomically."""
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("BF.MADD", key, *items)
        return [bool(r) for r in results]

    def exists(self, name: str, item: str) -> bool:
        """
        Check if item might exist.
        False = definitely not in set.
        True = probably in set (with FPR probability of false positive).
        """
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("BF.EXISTS", key, item))

    def exists_multi(self, name: str, items: List[str]) -> List[bool]:
        """Check multiple items at once."""
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("BF.MEXISTS", key, *items)
        return [bool(r) for r in results]

    def info(self, name: str) -> dict:
        """Get filter statistics."""
        key = f"{self.ns}:{name}"
        raw = self.r.execute_command("BF.INFO", key)
        # Parse flat list into dict
        it = iter(raw)
        return dict(zip(it, it))

    # ─── Scalable Bloom Pattern ───────────────────────────────────

    def add_with_auto_create(self, name: str, item: str,
                             expected: int = 1000000,
                             fpr: float = 0.01) -> bool:
        """
        Add with auto-creation if filter doesn't exist.
        BF.ADD auto-creates with defaults; this ensures custom params.
        """
        key = f"{self.ns}:{name}"
        # BF.INSERT creates if not exists with specified params
        result = self.r.execute_command(
            "BF.INSERT", key,
            "CAPACITY", expected,
            "ERROR", fpr,
            "EXPANSION", 2,
            "ITEMS", item
        )
        return bool(result[0])


class CachePenetrationGuard:
    """
    Prevent cache penetration attacks using Bloom filters.
    
    Problem: Attacker requests non-existent keys → every request hits DB.
    Solution: Bloom filter of all valid keys → reject definitely-invalid keys early.
    
    Architecture:
    Request → Bloom Filter → Cache → Database
                 ↓ NO
              Return 404 (no DB query)
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.bf = BloomFilterEngine(r, "guard")

    def initialize(self, valid_keys: List[str], name: str = "valid_keys"):
        """Bulk load all valid keys into the Bloom filter."""
        self.bf.create_filter(
            name,
            expected_items=len(valid_keys) * 2,  # 2x headroom
            false_positive_rate=0.001  # 0.1% FPR for security
        )
        # Batch insert
        batch_size = 1000
        for i in range(0, len(valid_keys), batch_size):
            batch = valid_keys[i:i + batch_size]
            self.bf.add_multi(name, batch)

    def should_query_db(self, key: str, name: str = "valid_keys") -> bool:
        """
        Check if we should bother querying the database.
        Returns False = definitely invalid → skip DB entirely.
        Returns True = might be valid → proceed to cache/DB.
        """
        return self.bf.exists(name, key)

    def on_new_key_created(self, key: str, name: str = "valid_keys"):
        """When a new valid key is created, add to filter."""
        self.bf.add(name, key)


class URLDeduplicator:
    """
    Web crawler URL deduplication using Bloom filter.
    
    At scale (billions of URLs), a Set would consume hundreds of GB.
    Bloom filter: 1B URLs at 0.1% FPR ≈ 1.8GB.
    """

    def __init__(self, r: redis.Redis, crawler_id: str):
        self.r = r
        self.bf = BloomFilterEngine(r, f"crawl:{crawler_id}")
        self.filter_name = "seen_urls"

    def initialize(self, expected_urls: int = 100_000_000):
        self.bf.create_filter(
            self.filter_name,
            expected_items=expected_urls,
            false_positive_rate=0.001,
            expansion=2
        )

    def should_crawl(self, url: str) -> bool:
        """
        Returns True if URL has NOT been seen before.
        False positive (skip a valid URL) is acceptable — we miss at most 0.1%.
        False negative (re-crawl a URL) never happens with Bloom.
        """
        already_seen = self.bf.exists(self.filter_name, url)
        if not already_seen:
            self.bf.add(self.filter_name, url)
            return True
        return False

    def mark_crawled_batch(self, urls: List[str]):
        """Mark a batch of URLs as crawled."""
        self.bf.add_multi(self.filter_name, urls)


class RecommendationFilter:
    """
    Filter already-seen recommendations per user.
    
    Problem: Don't recommend content the user has already interacted with.
    At scale: 100M users × 1000 interactions each = too much for Sets.
    Solution: Per-user Bloom filter (tiny memory footprint).
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.bf = BloomFilterEngine(r, "reco")

    def record_interaction(self, user_id: str, item_id: str):
        """Record that user has seen/interacted with this item."""
        filter_name = f"seen:{user_id}"
        self.r.execute_command(
            "BF.INSERT", f"reco:{filter_name}",
            "CAPACITY", 5000,
            "ERROR", 0.01,
            "EXPANSION", 2,
            "ITEMS", item_id
        )

    def filter_recommendations(self, user_id: str,
                               candidates: List[str]) -> List[str]:
        """
        Remove already-seen items from candidate recommendations.
        
        False positive: user hasn't seen it but we filter it out (acceptable loss).
        False negative: never happens — we never re-recommend seen items.
        """
        filter_name = f"seen:{user_id}"
        key = f"reco:{filter_name}"

        if not self.r.exists(key):
            return candidates  # New user, nothing filtered

        seen_flags = self.r.execute_command("BF.MEXISTS", key, *candidates)
        return [
            item for item, seen in zip(candidates, seen_flags)
            if not seen
        ]
```

### Bloom Filter Internals

```
┌──────────────────────────────────────────────────────────────┐
│                     Bloom Filter                              │
├──────────────────────────────────────────────────────────────┤
│  Bit Array: [0|1|0|0|1|0|1|0|0|1|0|0|0|1|0|0|1|0|1|0|...] │
│              ↑       ↑   ↑                                   │
│  Add "hello":                                                │
│    h1("hello") = 1  → set bit[1]                            │
│    h2("hello") = 4  → set bit[4]                            │
│    h3("hello") = 6  → set bit[6]                            │
│                                                              │
│  Check "hello": bits[1]=1, bits[4]=1, bits[6]=1 → MAYBE    │
│  Check "world": bits[2]=0 → DEFINITELY NOT                  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Parameters:                                                 │
│  • m (bits): -n·ln(p) / (ln2)²                             │
│  • k (hash functions): (m/n) · ln2                          │
│  • n = expected items, p = false positive rate               │
│                                                              │
│  Optimal k = 7 for 1% FPR                                   │
│  Optimal k = 10 for 0.1% FPR                                │
│                                                              │
│  NO DELETION possible (use Cuckoo filter if needed)         │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Count-Min Sketch

### Concept

Count-Min Sketch estimates the frequency of elements in a data stream. It answers "how many times has X appeared?" with bounded over-estimation (never under-counts).

```python
class CountMinSketchEngine:
    """
    Production Count-Min Sketch for frequency estimation.
    
    Use cases:
    - Heavy hitter detection (top queries, frequent IPs)
    - Network traffic analysis
    - Click fraud detection
    - Trending topic detection
    - Rate limiting with approximate counters
    """

    def __init__(self, r: redis.Redis, namespace: str = "cms"):
        self.r = r
        self.ns = namespace

    def create_sketch(self, name: str, width: int = 2000,
                      depth: int = 7) -> bool:
        """
        Create a Count-Min Sketch.
        
        Args:
            width: Number of counters per row (more = less error)
            depth: Number of hash functions/rows (more = less probability of error)
            
        Error bounds:
            ε (error) = e / width  (over-count by at most ε·N)
            δ (probability) = e^(-depth) (probability of exceeding ε·N)
            
        Practical settings:
            width=2000, depth=7 → error < 0.14% of total with 99.9% probability
            width=10000, depth=5 → error < 0.03% with 99.3% probability
            
        Memory: width × depth × 4 bytes (32-bit counters)
            2000 × 7 × 4 = 56KB
        """
        key = f"{self.ns}:{name}"
        try:
            self.r.execute_command("CMS.INITBYDIM", key, width, depth)
            return True
        except redis.ResponseError as e:
            if "item exists" in str(e):
                return False
            raise

    def create_by_error(self, name: str, error: float = 0.001,
                        probability: float = 0.01) -> bool:
        """
        Create sketch specifying desired error bounds.
        
        Args:
            error: Maximum over-estimation as fraction of total count
            probability: Probability of exceeding the error bound
        """
        key = f"{self.ns}:{name}"
        try:
            self.r.execute_command("CMS.INITBYPROB", key, error, probability)
            return True
        except redis.ResponseError as e:
            if "item exists" in str(e):
                return False
            raise

    def increment(self, name: str, item: str, count: int = 1) -> int:
        """Increment the count of an item. Returns estimated new count."""
        key = f"{self.ns}:{name}"
        result = self.r.execute_command("CMS.INCRBY", key, item, count)
        return result[0]

    def increment_multi(self, name: str,
                        items_counts: List[Tuple[str, int]]) -> List[int]:
        """Increment multiple items atomically."""
        key = f"{self.ns}:{name}"
        args = []
        for item, count in items_counts:
            args.extend([item, count])
        results = self.r.execute_command("CMS.INCRBY", key, *args)
        return list(results)

    def query(self, name: str, *items: str) -> List[int]:
        """Get estimated counts for one or more items."""
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("CMS.QUERY", key, *items)
        return list(results)

    def info(self, name: str) -> dict:
        """Get sketch parameters and statistics."""
        key = f"{self.ns}:{name}"
        raw = self.r.execute_command("CMS.INFO", key)
        it = iter(raw)
        return dict(zip(it, it))

    def merge(self, dest_name: str, source_names: List[str],
              weights: Optional[List[int]] = None):
        """
        Merge multiple sketches into one.
        Useful for combining per-node sketches into global view.
        """
        dest_key = f"{self.ns}:{dest_name}"
        source_keys = [f"{self.ns}:{s}" for s in source_names]
        num_sources = len(source_keys)

        if weights:
            self.r.execute_command(
                "CMS.MERGE", dest_key, num_sources,
                *source_keys, "WEIGHTS", *weights
            )
        else:
            self.r.execute_command(
                "CMS.MERGE", dest_key, num_sources, *source_keys
            )


class HeavyHitterDetector:
    """
    Detect heavy hitters (items that appear more than threshold% of the time).
    
    Architecture:
    - CMS for approximate counting
    - Sorted Set for top-K maintenance
    - Periodic cleanup of stale entries
    """

    def __init__(self, r: redis.Redis, name: str, threshold_pct: float = 0.01):
        self.r = r
        self.cms = CountMinSketchEngine(r)
        self.name = name
        self.threshold_pct = threshold_pct
        self.total_key = f"hh:{name}:total"
        self.topk_key = f"hh:{name}:top"

    def initialize(self, width: int = 5000, depth: int = 7):
        self.cms.create_sketch(self.name, width, depth)
        self.r.set(self.total_key, 0)

    def observe(self, item: str, count: int = 1) -> bool:
        """
        Observe an item. Returns True if it's a heavy hitter.
        """
        estimated_count = self.cms.increment(self.name, item, count)
        total = self.r.incrby(self.total_key, count)

        # Check if it exceeds threshold
        if total > 0 and (estimated_count / total) >= self.threshold_pct:
            # Add/update in top-K sorted set
            self.r.zadd(self.topk_key, {item: estimated_count})
            return True
        return False

    def get_heavy_hitters(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get current heavy hitters sorted by frequency."""
        results = self.r.zrevrange(self.topk_key, 0, limit - 1, withscores=True)
        return [(item.decode() if isinstance(item, bytes) else item, int(score))
                for item, score in results]

    def cleanup_stale(self):
        """Remove items that are no longer heavy hitters."""
        total = int(self.r.get(self.total_key) or 0)
        if total == 0:
            return

        threshold_count = total * self.threshold_pct
        # Remove items below threshold
        self.r.zremrangebyscore(self.topk_key, 0, threshold_count)


class ClickFraudDetector:
    """
    Detect click fraud using Count-Min Sketch for frequency tracking.
    
    Approach:
    - Track clicks per (IP, ad_id) pair in sliding windows
    - Flag IPs with abnormally high click rates
    - Use CMS because storing exact counts for all IP×Ad pairs is infeasible
    """

    DETECT_FRAUD_SCRIPT = """
    local cms_key = KEYS[1]
    local fraud_set_key = KEYS[2]
    local item = ARGV[1]
    local threshold = tonumber(ARGV[2])
    local window_total_key = KEYS[3]

    -- Increment in CMS
    local counts = redis.call('CMS.INCRBY', cms_key, item, 1)
    local count = counts[1]

    -- Increment window total
    redis.call('INCR', window_total_key)

    -- Check threshold
    if count >= threshold then
        redis.call('SADD', fraud_set_key, item)
        redis.call('EXPIRE', fraud_set_key, 3600)
        return 1
    end
    return 0
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.cms = CountMinSketchEngine(r, "fraud")

    def initialize(self):
        """Create sketches for different time windows."""
        # 1-minute window (tight)
        self.cms.create_sketch("clicks_1m", width=10000, depth=5)
        # 1-hour window (broader)
        self.cms.create_sketch("clicks_1h", width=50000, depth=7)

    def record_click(self, ip: str, ad_id: str) -> dict:
        """
        Record a click and check for fraud signals.
        Returns fraud assessment.
        """
        item = f"{ip}:{ad_id}"
        now_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
        now_hour = datetime.utcnow().strftime("%Y%m%d%H")

        # Use Lua for atomicity
        is_fraud = self.r.execute_command(
            "EVAL", self.DETECT_FRAUD_SCRIPT, 3,
            f"cms:clicks_1m", f"fraud:flagged:{now_minute}", f"fraud:total:{now_minute}",
            item, 10  # Threshold: 10 clicks per IP per ad per minute
        )

        # Also track hourly
        self.cms.increment("clicks_1h", item)

        return {
            "flagged": bool(is_fraud),
            "item": item,
            "window": now_minute,
        }

    def get_flagged_ips(self, window: str) -> set:
        """Get all IPs flagged as fraudulent in a given window."""
        members = self.r.smembers(f"fraud:flagged:{window}")
        return {m.decode() if isinstance(m, bytes) else m for m in members}
```

### Count-Min Sketch Internals

```
┌────────────────────────────────────────────────────────────────┐
│                    Count-Min Sketch                              │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  depth (d) hash functions × width (w) counters                  │
│                                                                  │
│  h1: [ 0 | 3 | 0 | 1 | 0 | 5 | 0 | 0 | 2 | 0 ]              │
│  h2: [ 1 | 0 | 0 | 4 | 0 | 0 | 3 | 0 | 0 | 1 ]              │
│  h3: [ 0 | 0 | 2 | 0 | 0 | 3 | 0 | 1 | 0 | 0 ]              │
│  h4: [ 0 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 4 | 0 ]              │
│  h5: [ 2 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 0 | 0 ]              │
│                                                                  │
│  Query("X"):                                                    │
│    count = min(h1[hash1(X)], h2[hash2(X)], ..., hd[hashd(X)]) │
│                                                                  │
│  Properties:                                                     │
│    • Never underestimates (may over-estimate due to collisions) │
│    • Point query: min across all rows                           │
│    • Mergeable: add corresponding counters                      │
│    • Deletable: subtract (but can go negative → use conserv.)   │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Top-K

### Concept

Top-K maintains an approximate list of the most frequent items in a stream without needing to know frequencies of all items. Uses a combination of Count-Min Sketch and a min-heap.

```python
class TopKEngine:
    """
    Production Top-K for streaming top-N element tracking.
    
    Use cases:
    - Trending hashtags/topics
    - Most popular products
    - Most active users
    - Most frequent search queries
    - Top error messages
    """

    def __init__(self, r: redis.Redis, namespace: str = "topk"):
        self.r = r
        self.ns = namespace

    def create(self, name: str, k: int = 100,
               width: int = 2000, depth: int = 7,
               decay: float = 0.9) -> bool:
        """
        Create a Top-K structure.
        
        Args:
            k: Number of top elements to track
            width/depth: CMS dimensions for frequency estimation
            decay: Probability of decrement (Heavy Keeper algorithm)
                   Lower decay = more aggressive eviction of old items
        """
        key = f"{self.ns}:{name}"
        try:
            self.r.execute_command(
                "TOPK.RESERVE", key, k, width, depth, decay
            )
            return True
        except redis.ResponseError as e:
            if "item exists" in str(e):
                return False
            raise

    def add(self, name: str, *items: str) -> List[Optional[str]]:
        """
        Add items to Top-K.
        Returns list of evicted items (or None if no eviction).
        Evicted items were previously in top-K but got replaced.
        """
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("TOPK.ADD", key, *items)
        return [
            r.decode() if isinstance(r, bytes) else r
            for r in results
        ]

    def add_with_increment(self, name: str,
                           items_increments: List[Tuple[str, int]]) -> List:
        """Add items with specific increment values."""
        key = f"{self.ns}:{name}"
        args = []
        for item, incr in items_increments:
            args.extend([item, incr])
        return self.r.execute_command("TOPK.INCRBY", key, *args)

    def query(self, name: str, *items: str) -> List[bool]:
        """Check if items are in the current Top-K."""
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("TOPK.QUERY", key, *items)
        return [bool(r) for r in results]

    def count(self, name: str, *items: str) -> List[int]:
        """Get estimated counts for items (only for those in Top-K)."""
        key = f"{self.ns}:{name}"
        results = self.r.execute_command("TOPK.COUNT", key, *items)
        return list(results)

    def list_top(self, name: str, with_count: bool = True) -> List[dict]:
        """List all items currently in the Top-K."""
        key = f"{self.ns}:{name}"
        if with_count:
            results = self.r.execute_command("TOPK.LIST", key, "WITHCOUNT")
            items = []
            for i in range(0, len(results), 2):
                item = results[i].decode() if isinstance(results[i], bytes) else results[i]
                items.append({"item": item, "count": results[i + 1]})
            return items
        else:
            results = self.r.execute_command("TOPK.LIST", key)
            return [r.decode() if isinstance(r, bytes) else r for r in results]

    def info(self, name: str) -> dict:
        key = f"{self.ns}:{name}"
        raw = self.r.execute_command("TOPK.INFO", key)
        it = iter(raw)
        return dict(zip(it, it))


class TrendingTopicsTracker:
    """
    Real-time trending topics using Top-K with time decay.
    
    Architecture:
    - Multiple Top-K structures for different time windows
    - Periodic rotation creates sliding windows
    - Velocity detection: compare current window vs previous
    """

    def __init__(self, r: redis.Redis, k: int = 50):
        self.r = r
        self.topk = TopKEngine(r, "trending")
        self.k = k

    def initialize(self):
        """Create Top-K structures for different windows."""
        # Current window (5-minute buckets)
        self.topk.create("current_5m", k=self.k, width=5000, depth=7, decay=0.9)
        # Current hour
        self.topk.create("current_1h", k=self.k, width=10000, depth=7, decay=0.9)
        # Previous hour (for velocity comparison)
        self.topk.create("previous_1h", k=self.k, width=10000, depth=7, decay=0.9)

    def record_topic(self, topic: str, weight: int = 1):
        """Record a topic mention."""
        pipe = self.r.pipeline()
        # Add to both current windows
        key_5m = f"trending:current_5m"
        key_1h = f"trending:current_1h"
        pipe.execute_command("TOPK.INCRBY", key_5m, topic, weight)
        pipe.execute_command("TOPK.INCRBY", key_1h, topic, weight)
        pipe.execute()

    def get_trending(self, window: str = "current_1h") -> List[dict]:
        """Get current trending topics with counts."""
        return self.topk.list_top(window, with_count=True)

    def get_velocity_trending(self) -> List[dict]:
        """
        Find topics with highest velocity (current vs previous hour).
        These are truly 'trending' — not just popular, but accelerating.
        """
        current = self.topk.list_top("current_1h", with_count=True)
        previous_counts = {}

        if current:
            prev_items = [item["item"] for item in current]
            prev_key = "trending:previous_1h"
            prev_results = self.r.execute_command(
                "TOPK.COUNT", prev_key, *prev_items
            )
            for item, count in zip(prev_items, prev_results):
                previous_counts[item] = count

        velocity_items = []
        for item in current:
            prev_count = previous_counts.get(item["item"], 0)
            curr_count = item["count"]
            velocity = curr_count - prev_count if prev_count > 0 else curr_count
            acceleration = (
                (curr_count / prev_count) if prev_count > 0 else float('inf')
            )
            velocity_items.append({
                "topic": item["item"],
                "current_count": curr_count,
                "previous_count": prev_count,
                "velocity": velocity,
                "acceleration": round(acceleration, 2),
            })

        velocity_items.sort(key=lambda x: x["velocity"], reverse=True)
        return velocity_items[:self.k]

    def rotate_windows(self):
        """
        Called periodically (every hour) to rotate windows.
        Current → Previous, then reset Current.
        """
        pipe = self.r.pipeline()
        # Copy current to previous (rename)
        pipe.rename("trending:current_1h", "trending:previous_1h")
        pipe.execute()
        # Create new current
        self.topk.create("current_1h", k=self.k, width=10000, depth=7, decay=0.9)
```

---

## 5. Cuckoo Filters

### Concept

Cuckoo filters are similar to Bloom filters but support **deletion** and typically have better space efficiency for low false positive rates. They use cuckoo hashing with fingerprints.

```python
class CuckooFilterEngine:
    """
    Production Cuckoo filter — like Bloom but with deletion support.
    
    Advantages over Bloom:
    - Supports deletion
    - Better space efficiency at low FPR (<3%)
    - Faster lookups (2 locations vs k hash functions)
    
    Disadvantages:
    - Cannot handle duplicates well (limited count)
    - Insertion can fail when filter is near capacity
    - Slightly higher FPR for same space at high FPR targets
    
    Use cases:
    - Session tracking (need to remove expired sessions)
    - Temporary bans/blocks (need to unblock)
    - Feature flag membership (users can be removed from groups)
    - Real-time blacklists with removal capability
    """

    def __init__(self, r: redis.Redis, namespace: str = "cf"):
        self.r = r
        self.ns = namespace

    def create(self, name: str, capacity: int = 1000000,
               bucket_size: int = 2, max_iterations: int = 20,
               expansion: int = 1) -> bool:
        """
        Create a Cuckoo filter.
        
        Args:
            capacity: Expected number of items
            bucket_size: Number of items per bucket (2-4, higher = more dense)
            max_iterations: Max cuckoo kicks before expansion
            expansion: Auto-expansion factor (1 = no expansion)
        """
        key = f"{self.ns}:{name}"
        try:
            self.r.execute_command(
                "CF.RESERVE", key, capacity,
                "BUCKETSIZE", bucket_size,
                "MAXITERATIONS", max_iterations,
                "EXPANSION", expansion
            )
            return True
        except redis.ResponseError as e:
            if "item exists" in str(e):
                return False
            raise

    def add(self, name: str, item: str) -> bool:
        """Add item. Returns True if added, False if might already exist."""
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("CF.ADD", key, item))

    def add_if_not_exists(self, name: str, item: str) -> bool:
        """Only add if item is definitely not present."""
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("CF.ADDNX", key, item))

    def exists(self, name: str, item: str) -> bool:
        """Check if item might exist. Same semantics as Bloom."""
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("CF.EXISTS", key, item))

    def delete(self, name: str, item: str) -> bool:
        """
        Delete an item from the filter.
        
        IMPORTANT: Only delete items you KNOW were inserted.
        Deleting a non-existent item can cause false negatives.
        """
        key = f"{self.ns}:{name}"
        return bool(self.r.execute_command("CF.DEL", key, item))

    def count(self, name: str, item: str) -> int:
        """Get approximate count of item (cuckoo supports limited counting)."""
        key = f"{self.ns}:{name}"
        return self.r.execute_command("CF.COUNT", key, item)

    def info(self, name: str) -> dict:
        key = f"{self.ns}:{name}"
        raw = self.r.execute_command("CF.INFO", key)
        it = iter(raw)
        return dict(zip(it, it))


class DynamicBlocklist:
    """
    IP/user blocklist that supports both adding and removing entries.
    
    Bloom filter can't do this — once an IP is added, it can never be removed.
    Cuckoo filter solves this with O(1) delete.
    """

    def __init__(self, r: redis.Redis, list_name: str = "blocklist"):
        self.r = r
        self.cf = CuckooFilterEngine(r)
        self.list_name = list_name

    def initialize(self, expected_entries: int = 100000):
        self.cf.create(self.list_name, capacity=expected_entries, bucket_size=4)

    def block(self, identifier: str, reason: str = ""):
        """Add to blocklist."""
        self.cf.add(self.list_name, identifier)
        # Also store metadata for admin reference
        if reason:
            self.r.hset(f"block:meta:{identifier}", mapping={
                "reason": reason,
                "blocked_at": str(int(time.time())),
            })

    def unblock(self, identifier: str):
        """Remove from blocklist."""
        self.cf.delete(self.list_name, identifier)
        self.r.delete(f"block:meta:{identifier}")

    def is_blocked(self, identifier: str) -> bool:
        """Check if identifier is in blocklist."""
        return self.cf.exists(self.list_name, identifier)

    def check_and_enforce(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """Check blocklist and return enforcement decision with reason."""
        if not self.is_blocked(identifier):
            return False, None

        meta = self.r.hgetall(f"block:meta:{identifier}")
        reason = meta.get(b"reason", b"unknown").decode()
        return True, reason


class SessionTracker:
    """
    Track active sessions using Cuckoo filter.
    
    Unlike Bloom: sessions can expire and be removed from the filter.
    Much more memory-efficient than maintaining a full Set of session IDs.
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.cf = CuckooFilterEngine(r)
        self.filter_name = "active_sessions"

    def initialize(self, max_concurrent_sessions: int = 1000000):
        self.cf.create(self.filter_name, capacity=max_concurrent_sessions)

    def create_session(self, session_id: str, user_id: str, ttl: int = 3600):
        """Register a new session."""
        # Add to Cuckoo filter for fast existence check
        self.cf.add(self.filter_name, session_id)
        # Store session data with TTL
        self.r.setex(
            f"session:{session_id}",
            ttl,
            user_id
        )
        # Track session in user's set for multi-session management
        self.r.sadd(f"user_sessions:{user_id}", session_id)
        self.r.expire(f"user_sessions:{user_id}", ttl * 2)

    def is_active(self, session_id: str) -> bool:
        """Fast check if session might be active."""
        # First: Cuckoo filter (O(1), sub-microsecond)
        if not self.cf.exists(self.filter_name, session_id):
            return False  # Definitely not active

        # If Cuckoo says yes, verify with actual session data
        return self.r.exists(f"session:{session_id}") == 1

    def destroy_session(self, session_id: str):
        """Terminate a session."""
        # Get user_id before deleting
        user_id = self.r.get(f"session:{session_id}")
        if user_id:
            user_id = user_id.decode()
            self.r.srem(f"user_sessions:{user_id}", session_id)

        # Remove from Cuckoo filter
        self.cf.delete(self.filter_name, session_id)
        # Delete session data
        self.r.delete(f"session:{session_id}")

    def cleanup_expired(self, session_ids: List[str]):
        """Remove expired sessions from the filter (called by background job)."""
        for sid in session_ids:
            if not self.r.exists(f"session:{sid}"):
                self.cf.delete(self.filter_name, sid)
```

### Cuckoo Filter Internals

```
┌──────────────────────────────────────────────────────────────────┐
│                      Cuckoo Filter                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Bucket Array (each bucket holds b fingerprints):                 │
│                                                                    │
│  [fp1|fp2|  ] [fp3|   |  ] [fp4|fp5|fp6] [   |   |  ] ...      │
│   bucket 0     bucket 1     bucket 2       bucket 3               │
│                                                                    │
│  Insert("hello"):                                                 │
│    fingerprint = hash("hello") → "A7"                            │
│    i1 = hash("hello") mod n_buckets = 2                          │
│    i2 = i1 XOR hash("A7") mod n_buckets = 5                     │
│    → Try bucket[2], if full try bucket[5]                        │
│    → If both full: kick random entry, relocate it to its alt     │
│                                                                    │
│  Lookup("hello"):                                                 │
│    Check bucket[2] and bucket[5] for fingerprint "A7"            │
│                                                                    │
│  Delete("hello"):                                                 │
│    Find "A7" in bucket[2] or bucket[5], remove it                │
│                                                                    │
│  Properties:                                                       │
│    • Supports deletion (unlike Bloom)                             │
│    • 2 lookups per query (vs k for Bloom)                        │
│    • ~95% load factor achievable                                  │
│    • FPR ≈ 2b/2^f where b=bucket_size, f=fingerprint_bits       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Composite Patterns

### Combining Structures for Production Systems

```python
class UniqueEventCounter:
    """
    Combines HyperLogLog + Count-Min Sketch for rich analytics.
    
    HLL answers: "How many unique users did X?"
    CMS answers: "How often did user Y do X?"
    Together: full event analytics with minimal memory.
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.hll = HyperLogLogCounter(r, "events")
        self.cms = CountMinSketchEngine(r, "events")

    def initialize(self, event_types: List[str]):
        """Create CMS structures for each event type."""
        for event_type in event_types:
            self.cms.create_sketch(
                f"freq:{event_type}",
                width=10000, depth=7
            )

    def track_event(self, event_type: str, user_id: str):
        """Track an event with both unique counting and frequency."""
        pipe = self.r.pipeline()

        # HLL: unique users per event per day
        today = datetime.utcnow().strftime("%Y%m%d")
        hll_key = f"events:{event_type}:day:{today}"
        pipe.pfadd(hll_key, user_id)
        pipe.expire(hll_key, 7776000)

        pipe.execute()

        # CMS: frequency per user (separate call for module command)
        self.cms.increment(f"freq:{event_type}", user_id)

    def get_analytics(self, event_type: str, date_str: str) -> dict:
        """Get combined analytics for an event type."""
        hll_key = f"events:{event_type}:day:{date_str}"
        unique_users = self.r.pfcount(hll_key)

        return {
            "event_type": event_type,
            "date": date_str,
            "unique_users": unique_users,
        }

    def get_user_frequency(self, event_type: str, user_id: str) -> int:
        """How many times has this user triggered this event?"""
        counts = self.cms.query(f"freq:{event_type}", user_id)
        return counts[0] if counts else 0

    def is_power_user(self, event_type: str, user_id: str,
                      threshold: int = 100) -> bool:
        """Detect power users based on event frequency."""
        return self.get_user_frequency(event_type, user_id) >= threshold


class MultiLayerDeduplication:
    """
    Multi-layer deduplication for high-throughput event processing.
    
    Layer 1: Bloom filter (fast reject of never-seen events)
    Layer 2: Cuckoo filter (recent events with TTL-based cleanup)
    Layer 3: Exact check in Redis Set (small hot window)
    
    Architecture:
    Event → Bloom (definitely new?) → Cuckoo (recent dup?) → Exact Set → Process
              ↓ NO                        ↓ YES
           Process                      Drop (duplicate)
    """

    def __init__(self, r: redis.Redis, stream_name: str):
        self.r = r
        self.bf = BloomFilterEngine(r, f"dedup:bf:{stream_name}")
        self.cf = CuckooFilterEngine(r, f"dedup:cf:{stream_name}")
        self.stream = stream_name
        self.exact_key = f"dedup:exact:{stream_name}"

    def initialize(self, expected_total: int = 10_000_000,
                   recent_window: int = 100_000):
        """Set up dedup layers."""
        # Bloom: all-time dedup (never miss a duplicate)
        self.bf.create_filter("alltime", expected_total, false_positive_rate=0.001)
        # Cuckoo: recent window (allows removal of old entries)
        self.cf.create("recent", capacity=recent_window, bucket_size=4)

    def is_duplicate(self, event_id: str) -> bool:
        """
        Multi-layer duplicate check.
        
        Returns True if event is (probably) a duplicate.
        False positives are possible but rare (0.1% from Bloom).
        False negatives (missing a dup) are impossible.
        """
        # Layer 1: Bloom filter (all-time)
        if not self.bf.exists("alltime", event_id):
            # Definitely new — fast path
            return False

        # Bloom says "maybe seen" — verify with Cuckoo (recent)
        if self.cf.exists("recent", event_id):
            return True  # Likely a recent duplicate

        # Bloom positive but not in Cuckoo = either old event or false positive
        # Check exact set for the hot window
        if self.r.sismember(self.exact_key, event_id):
            return True

        # False positive from Bloom — not actually a duplicate
        return False

    def mark_processed(self, event_id: str):
        """Mark event as processed across all layers."""
        pipe = self.r.pipeline()

        # Add to all layers
        pipe.execute()

        self.bf.add("alltime", event_id)
        self.cf.add("recent", event_id)
        self.r.sadd(self.exact_key, event_id)

        # Trim exact set to bounded size
        if self.r.scard(self.exact_key) > 10000:
            self.r.spop(self.exact_key, 1000)

    def cleanup_recent(self, old_event_ids: List[str]):
        """Remove old events from Cuckoo filter (called by cleanup job)."""
        for eid in old_event_ids:
            self.cf.delete("recent", eid)


class CardinalityEstimationPipeline:
    """
    Atomic cardinality tracking with Lua for high-throughput scenarios.
    
    Use case: Track unique visitors with atomic increment + cardinality
    check in a single round trip.
    """

    TRACK_AND_CHECK_THRESHOLD_SCRIPT = """
    local hll_key = KEYS[1]
    local alert_key = KEYS[2]
    local element = ARGV[1]
    local threshold = tonumber(ARGV[2])
    local alert_ttl = tonumber(ARGV[3])

    -- Add to HLL
    local modified = redis.call('PFADD', hll_key, element)

    -- Check current count
    local count = redis.call('PFCOUNT', hll_key)

    -- If threshold crossed and no recent alert
    if count >= threshold then
        local already_alerted = redis.call('EXISTS', alert_key)
        if already_alerted == 0 then
            redis.call('SETEX', alert_key, alert_ttl, count)
            return {count, 1}  -- {count, should_alert}
        end
    end

    return {count, 0}
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def track_with_threshold(self, metric: str, element: str,
                             threshold: int,
                             alert_cooldown: int = 300) -> Tuple[int, bool]:
        """
        Atomically track an element and check if threshold is crossed.
        
        Returns (estimated_count, should_alert).
        Alert fires at most once per cooldown period.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        hll_key = f"hll:{metric}:{today}"
        alert_key = f"alert:{metric}:{today}"

        result = self.r.execute_command(
            "EVAL", self.TRACK_AND_CHECK_THRESHOLD_SCRIPT, 2,
            hll_key, alert_key,
            element, threshold, alert_cooldown
        )
        return int(result[0]), bool(result[1])
```

---

## 7. Memory & Performance Reference

### Structure Comparison

| Structure | Memory (1M items) | False Positive | Deletion | Use Case |
|-----------|-------------------|----------------|----------|----------|
| **HyperLogLog** | 12KB (fixed) | N/A (cardinal) | No | Unique counting |
| **Bloom Filter** | 1.2MB (1% FPR) | Yes (tunable) | No | Membership test |
| **Cuckoo Filter** | 1MB (1% FPR) | Yes (tunable) | Yes | Membership + removal |
| **Count-Min Sketch** | 56KB (w=2000,d=7) | Over-estimates | Subtract | Frequency est. |
| **Top-K** | ~200KB (k=100) | Approximate | Eviction | Top elements |
| **Redis Set** | ~64MB | None (exact) | Yes | Exact membership |

### When to Use What

```
┌─────────────────────────────────────────────────────────────┐
│                Decision Matrix                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  "How many unique X?"        → HyperLogLog                  │
│  "Is X in the set?"          → Bloom filter (no delete)     │
│                              → Cuckoo filter (need delete)  │
│  "How often does X appear?"  → Count-Min Sketch             │
│  "What are the top N items?" → Top-K                        │
│  "Is X new or duplicate?"    → Bloom + exact fallback       │
│                                                              │
│  Need exact answers?         → Use Redis Set/Hash instead   │
│  Can tolerate ~1% error?     → Probabilistic = 100x savings │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  Memory Savings Examples:                                    │
│                                                              │
│  100M unique users/day:                                      │
│    Set: ~6.4GB          HLL: 12KB (530,000x smaller!)       │
│                                                              │
│  1B URL dedup:                                               │
│    Set: ~64GB           Bloom: 1.8GB (35x smaller)          │
│                                                              │
│  Frequency of 10M items:                                     │
│    Hash: ~640MB         CMS: 56KB (11,000x smaller)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Performance Characteristics

| Operation | Time Complexity | Latency (typical) |
|-----------|----------------|-------------------|
| PFADD | O(1) | < 1μs |
| PFCOUNT (single key) | O(1) | < 1μs |
| PFCOUNT (multiple) | O(N) keys | ~10μs per key |
| PFMERGE | O(N) keys | ~10μs per key |
| BF.ADD | O(k) hash functions | < 5μs |
| BF.EXISTS | O(k) hash functions | < 5μs |
| CF.ADD | O(1) amortized | < 5μs |
| CF.DEL | O(1) | < 5μs |
| CMS.INCRBY | O(d) depth | < 3μs |
| CMS.QUERY | O(d) depth | < 3μs |
| TOPK.ADD | O(k·d) | < 10μs |
| TOPK.LIST | O(k) | < 50μs |

### Production Considerations

| Concern | Mitigation |
|---------|-----------|
| **Bloom filter fills up** | Use scalable Bloom (EXPANSION > 1) or size for 2x expected |
| **CMS over-estimation in hot path** | Use conservative update or wider sketch |
| **HLL merge across clusters** | PFMERGE works; ship HLL bytes between clusters |
| **Cuckoo filter insertion failure** | Resize or use expansion; monitor load factor |
| **Top-K accuracy for low-frequency** | Increase width/depth of internal CMS |
| **Memory pressure** | Monitor with BF.INFO/CF.INFO; set alerts on capacity |
| **Persistence** | All structures persist with RDB/AOF — survive restarts |
| **Cluster mode** | Each key hashes to one slot; use hash tags for co-location |

### Module Installation

```bash
# Redis Stack (includes RedisBloom, RedisJSON, RediSearch, RedisTimeSeries)
docker run -p 6379:6379 redis/redis-stack:latest

# Or load module manually
redis-server --loadmodule /path/to/redisbloom.so

# Verify modules loaded
redis-cli MODULE LIST
```

---

## 8. Error Rate Calibration

### Choosing False Positive Rate

```python
class FPRCalculator:
    """Utility for sizing probabilistic structures."""

    @staticmethod
    def bloom_memory(n: int, fpr: float) -> dict:
        """
        Calculate Bloom filter memory for given parameters.
        
        Args:
            n: Expected number of items
            fpr: Desired false positive rate (e.g., 0.01 for 1%)
        """
        import math
        m = -n * math.log(fpr) / (math.log(2) ** 2)  # bits
        k = (m / n) * math.log(2)  # optimal hash functions
        return {
            "bits": int(m),
            "bytes": int(m / 8),
            "megabytes": round(m / 8 / 1024 / 1024, 2),
            "hash_functions": int(math.ceil(k)),
            "items": n,
            "fpr": fpr,
            "bits_per_item": round(m / n, 1),
        }

    @staticmethod
    def cms_memory(width: int, depth: int) -> dict:
        """Calculate Count-Min Sketch memory and error bounds."""
        import math
        memory_bytes = width * depth * 4  # 32-bit counters
        error = math.e / width
        probability = math.exp(-depth)
        return {
            "bytes": memory_bytes,
            "kilobytes": round(memory_bytes / 1024, 1),
            "width": width,
            "depth": depth,
            "error_fraction": round(error, 6),
            "error_probability": round(probability, 6),
        }

    @staticmethod
    def hll_error(registers: int = 16384) -> dict:
        """Calculate HyperLogLog error bounds."""
        import math
        std_error = 1.04 / math.sqrt(registers)
        return {
            "registers": registers,
            "memory_bytes": int(registers * 6 / 8),
            "standard_error": round(std_error, 4),
            "relative_error_pct": round(std_error * 100, 2),
            "at_1M_items": f"±{int(1_000_000 * std_error):,}",
            "at_100M_items": f"±{int(100_000_000 * std_error):,}",
        }


# Usage examples
if __name__ == "__main__":
    calc = FPRCalculator()

    # Bloom filter sizing
    print("=== Bloom Filter Sizing ===")
    for n in [100_000, 1_000_000, 10_000_000, 100_000_000]:
        for fpr in [0.01, 0.001, 0.0001]:
            info = calc.bloom_memory(n, fpr)
            print(f"  {n:>12,} items @ {fpr:.4f} FPR → "
                  f"{info['megabytes']:>8} MB, {info['hash_functions']} hashes, "
                  f"{info['bits_per_item']} bits/item")

    print("\n=== Count-Min Sketch Sizing ===")
    for w, d in [(2000, 7), (5000, 5), (10000, 7), (50000, 10)]:
        info = calc.cms_memory(w, d)
        print(f"  width={w:>6}, depth={d:>2} → "
              f"{info['kilobytes']:>8} KB, "
              f"ε={info['error_fraction']:.6f}, "
              f"δ={info['error_probability']:.6f}")

    print("\n=== HyperLogLog Error ===")
    info = calc.hll_error()
    print(f"  Standard HLL (16384 registers):")
    print(f"    Memory: {info['memory_bytes']:,} bytes")
    print(f"    Error: ±{info['relative_error_pct']}%")
    print(f"    At 1M items: {info['at_1M_items']}")
    print(f"    At 100M items: {info['at_100M_items']}")
```

---

## Summary

| Problem | Structure | Error Trade-off | Memory vs Exact |
|---------|-----------|-----------------|-----------------|
| Count uniques | HyperLogLog | ±0.81% | 12KB vs GBs |
| Set membership | Bloom filter | 1-0.01% false positive | 10-100x smaller |
| Membership + delete | Cuckoo filter | ~1% false positive | 10-100x smaller |
| Frequency counting | Count-Min Sketch | Over-estimates only | 1000-10000x smaller |
| Top-N items | Top-K | Approximate ranking | Fixed K memory |
| Combined analytics | HLL + CMS + TopK | Layered accuracy | Dramatic savings |

The fundamental insight: **when you don't need perfect accuracy, probabilistic structures provide 100-10000x memory savings** — enabling analytics at scales where exact answers would require terabytes of RAM.
