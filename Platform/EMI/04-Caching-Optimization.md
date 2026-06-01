# Affordability Platform - Caching & Performance Optimization

## 1. Multi-Layer Cache Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST PATH                                             │
│                                                                                      │
│  [Client Request]                                                                    │
│       │                                                                              │
│       ▼                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 1: Gateway-Level Cache (Offer Adapter / Gateway Adapter)              │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ • Product details: 30-day TTL (Redis)                                   │ │   │
│  │  │ • Issuer details: 1-hour TTL (Redis)                                    │ │   │
│  │  │ • Feature toggles: In-memory (ConcurrentHashMap)                        │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│       │ MISS                                                                         │
│       ▼                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 2: Service-Level Redis Cache (ReadServ - EmiCalculationCacheService)  │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ • Full EMI response cache: SHA-256(request) → GZIP(response)            │ │   │
│  │  │ • Client entity cache: 15-min TTL                                       │ │   │
│  │  │ • Issuer EMI config: 120-min TTL                                        │ │   │
│  │  │ • Offer codes: 120-min TTL                                              │ │   │
│  │  │ • Product mappings: Redis Hash (HMGET batch)                            │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│       │ MISS                                                                         │
│       ▼                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 3: In-Memory Application Cache (ReadServ - CacheDataService)          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ • Issuer master data: ConcurrentHashMap, 6-hour refresh                 │ │   │
│  │  │ • Tenure cache: ConcurrentHashMap, 6-hour refresh                       │ │   │
│  │  │ • Interest rate subvention charts: In-memory, 6-hour refresh            │ │   │
│  │  │ • Issuer program offer code criteria: In-memory                         │ │   │
│  │  │ • Issuer EMI config overrides: In-memory                                │ │   │
│  │  │ • Downpayment milestone rules: In-memory                                │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│       │ MISS                                                                         │
│       ▼                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 4: Offer Data Cache (CacheManagementServ → Redis)                     │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ • Issuer offers per client: 2-hour TTL + jitter                         │ │   │
│  │  │ • Product offers per client+product: 2-hour TTL + jitter                │ │   │
│  │  │ • Bundle offers: 2-hour TTL + jitter                                    │ │   │
│  │  │ • Offer breakups: 2-hour TTL + jitter                                   │ │   │
│  │  │ • Client product details: 2-hour TTL + jitter                           │ │   │
│  │  │ • Product bundles: 2-hour TTL + jitter                                  │ │   │
│  │  │ • BIN ranges: Sorted set (ZRANGEBYSCORE)                                │ │   │
│  │  │ • Offer codes: 24-hour TTL                                              │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│       │ MISS                                                                         │
│       ▼                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 5: PostgreSQL (Read Replicas with Round-Robin Routing)                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ • AtomicInteger counter for round-robin replica selection                │ │   │
│  │  │ • LazyConnectionDataSourceProxy (defer connection until first query)     │ │   │
│  │  │ • Native SQL with projections (avoid full entity loading)                │ │   │
│  │  │ • HikariCP: max-pool-size=100, connection-timeout=10s                   │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Redis Cache Key Design

### 2.1 EMI Response Cache (ReadServ)

| Cache Type | Key Pattern | TTL | Size |
|-----------|-------------|-----|------|
| Full EMI Response | `AFFORDABILITY_READ_OFFER:{clientId}:{version}:{SHA256(request)}` | 60min (configurable per client) | ~2-50KB compressed |
| Empty Response | `AFFORDABILITY_READ_OFFER:{clientId}:{version}:{SHA256(request)}` | 5min | ~100B |
| Client Entity | `AFFORDABILITY_READ_CLIENT:{clientType}:{channel}:{clientId}:{tenant}` | 15min | ~1KB |
| Issuer EMI Config | `AFFORDABILITY_READ_MASTER_ISSUER_EMI_CONFIG:{channel}` | 120min | ~50-500KB |
| Issuer Offer Codes | `AFFORDABILITY_READ_ISSUER_EMI_OFFER_CODE_CONFIG:{SHA256(issuerIds)}` | 120min | ~5-50KB |
| Brand Offer Codes | `AFFORDABILITY_READ_BRAND_EMI_OFFER_CODE_CONFIG:{SHA256(issuerIds)}` | 120min | ~5-50KB |
| Product Mapping | `AFFORDABILITY_READ_PRODUCT_MAPPING:{clientId}` (Hash) | External | ~1-10KB |

**Cache Eligibility Rule**: Requests containing `cardData` or `customerDetails` are NEVER cached (personalized results require fresh computation).

### 2.2 Offer Data Cache (CacheManagementServ)

| Cache Type | Key Pattern | TTL | Compression |
|-----------|-------------|-----|-------------|
| Issuer Offers | `issuer_offers:tenant:{t}:channel:{ch}:client:{c}[:issuer_type:{it}][:issuer:{i}][:tenure:{t}][:program:{p}]` | 7200s + 0-30s jitter | GZIP |
| Product Offers | `product_offers:tenant:{t}:channel:{ch}:client:{c}:product:{p}[:issuer_type:{it}][:issuer:{i}][:tenure:{t}][:program:{p}]` | 7200s + jitter | GZIP |
| Bundle Offers | `bundle_offers:tenant:{t}:channel:{ch}:client:{c}:bundle:{b}` | 7200s + jitter | GZIP |
| Offer Breakup | `offer_breakup:tenant:{t}:offer_parameter_id:{id}` | 7200s + jitter | GZIP |
| Client Product | `client_product:client:{c}:product:{p}` | 7200s + jitter | GZIP |
| Product Bundles | `product_bundles:product:{p}` | 7200s + jitter | GZIP |
| BIN Range | `bin_range` (Sorted Set, score=BIN number) | 7200s + jitter | None |
| Issuer EMI Codes | `issuer_emi_offer_codes:{hash}` | 86400s (24h) | GZIP |
| Brand EMI Codes | `brand_emi_offer_codes:{hash}` | 86400s (24h) | GZIP |

### 2.3 Gateway Layer Cache

| Cache Type | Key Pattern | TTL | Storage |
|-----------|-------------|-----|---------|
| Product Details | `product:{externalProductId}` | 2,592,000s (30 days) | Redis |
| Issuer Details | `AFF:ISSUER_{id}` | 3600s (1h) | Redis |
| Rate Limiter | `rate-limiter:{env}.{uri}.{clientKey}` | Configurable | Redis |
| Hot Keys | `HOT_KEYS_SORTED_SET` | No expiry | Redis Sorted Set |
| Distributed Locks | `lock:cache:clear:{request}` | 600s | Redis |
| Refresh Locks | `lock:cache:refresh:{request}` | 1800s | Redis |

---

## 3. Cache Invalidation Strategy

### 3.1 Event-Driven Invalidation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CACHE INVALIDATION PIPELINE                               │
│                                                                              │
│  ┌──────────────────┐     ┌────────────────────────────────────────────┐    │
│  │ OfferMgmtServ    │     │          offer_update_events TABLE         │    │
│  │                   │     │                                            │    │
│  │ • Create offer    │────>│  id | offer_id | event       | status     │    │
│  │ • Update offer    │     │  1  | 100      | CREATE      | PENDING    │    │
│  │ • Delete offer    │     │  2  | 100      | STATE_CHANGE| PENDING    │    │
│  │ • State change    │     │  3  | 101      | UPDATE      | PENDING    │    │
│  │ • Param update    │     │                                            │    │
│  └──────────────────┘     └──────────────────┬─────────────────────────┘    │
│                                               │                              │
│                                    Poll every 120 seconds                    │
│                                               │                              │
│                                               ▼                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                    CacheManagementServ (Scheduled Job)                 │   │
│  │                                                                       │   │
│  │  1. Acquire distributed lock: lock:cache:clear:{request}             │   │
│  │                                                                       │   │
│  │  2. Deduplication check (10-min window):                             │   │
│  │     - Skip if same event processed in last 10 minutes                │   │
│  │                                                                       │   │
│  │  3. Route to appropriate processor:                                   │   │
│  │     ┌──────────────────────────────────────────────────────────┐     │   │
│  │     │ OfferCacheRefreshProcessorFactory                        │     │   │
│  │     │  • IssuerOfferCacheProcessor                             │     │   │
│  │     │  • ProductOfferCacheProcessor                            │     │   │
│  │     │  • BundleOfferCacheProcessor                             │     │   │
│  │     │  • OfferCodeCacheProcessor                               │     │   │
│  │     │  • ClientProductCacheProcessor                           │     │   │
│  │     └──────────────────────────────────────────────────────────┘     │   │
│  │                                                                       │   │
│  │  4. Pattern-based deletion:                                           │   │
│  │     - SCAN with pattern match (e.g., issuer_offers:tenant:PL.IN:*)   │   │
│  │     - Batch DELETE (1000 keys per batch, 100 concurrent threads)      │   │
│  │                                                                       │   │
│  │  5. Hot key refresh:                                                  │   │
│  │     - Read top-1000 from HOT_KEYS_SORTED_SET                         │   │
│  │     - Pre-warm affected hot keys immediately                          │   │
│  │                                                                       │   │
│  │  6. Mark events as PROCESSED                                          │   │
│  │                                                                       │   │
│  │  7. Release distributed lock                                          │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Invalidation Triggers

| Trigger Event | Affected Cache Keys | Strategy |
|---------------|-------------------|----------|
| Offer created/updated | `issuer_offers:*`, `product_offers:*` | Pattern-based clear + hot key refresh |
| Offer state change | `issuer_offers:*`, `product_offers:*` | Pattern-based clear |
| Offer parameter change | `offer_breakup:*`, `issuer_offers:*` | Targeted + pattern clear |
| Client configuration change | `CLIENT:*` | Targeted key deletion |
| Issuer EMI config change | `MASTER_ISSUER_EMI_CONFIG:*` | Full config cache clear |
| BIN range change | `bin_range` sorted set | Full rebuild |
| Manual trigger (API) | Specified pattern | On-demand clear |

---

## 4. Performance Optimization Techniques

### 4.1 Response Compression (GZIP)

```java
// CompressionUtil.java - All Redis values are compressed
public class CompressionUtil {
    public static byte[] compress(String data) {
        // GZIP compression before Redis SET
        // Reduces ~80% network + memory overhead
    }
    
    public static String decompress(byte[] compressed) {
        // GZIP decompression after Redis GET
    }
}

// Typical compression ratios:
// EMI response JSON: 10KB → 2KB (80% reduction)
// Issuer config JSON: 500KB → 60KB (88% reduction)
```

### 4.2 SHA-256 Request Hashing (Deterministic Cache Keys)

```java
// Cache key generation for EMI responses
String cacheKey = String.format("OFFER:%s:%s:%s", 
    clientId, 
    apiVersion,
    DigestUtils.sha256Hex(objectMapper.writeValueAsString(normalizedRequest))
);

// Normalization ensures identical logical requests produce same hash
// regardless of JSON field ordering
```

### 4.3 Read Replica Round-Robin Routing

```java
// ReplicaRoutingDataSource.java
public class ReplicaRoutingDataSource extends AbstractRoutingDataSource {
    private final AtomicInteger counter = new AtomicInteger(0);
    private List<Object> replicaKeys;
    
    @Override
    protected Object determineCurrentLookupKey() {
        int index = Math.abs(counter.getAndIncrement() % replicaKeys.size());
        return replicaKeys.get(index);
    }
}

// Wrapped with LazyConnectionDataSourceProxy
// → Connection only acquired when first query executes
// → Avoids connection waste for cached responses
```

### 4.4 Async Parallel Execution

```java
// EmiOfferServiceHelper.java - Parallel DB + cache lookups
CompletableFuture<Map<Long, IssuerEmiConfigDTO>> configFuture = 
    CompletableFuture.supplyAsync(() -> fetchIssuerEmiConfigs(issuerIds), executorService);

CompletableFuture<Map<Long, List<OfferCode>>> offerCodeFuture = 
    CompletableFuture.supplyAsync(() -> fetchOfferCodes(issuerIds), executorService);

CompletableFuture<List<OfferDetails>> offerDetailsFuture = 
    CompletableFuture.supplyAsync(() -> fetchOfferDetails(clientId, productId), executorService);

// Wait for all and merge results
CompletableFuture.allOf(configFuture, offerCodeFuture, offerDetailsFuture).join();

// Thread pool config:
// async.executor.threadpool.min=25
// async.executor.threadpool.max=25
// async.executor.thread.wait.timeout=5000ms
```

### 4.5 Native SQL with Projections (Avoid N+1)

```java
// OfferParametersRepository.java - Native queries for complex joins
@Query(value = """
    SELECT op.id, op.offer_id, op.min_amount, op.max_amount,
           sp.merchant_offered_percentage, sp.brand_offered_percentage,
           dp.merchant_offered_percentage as disc_merchant_pct
    FROM offer_parameters op
    LEFT JOIN subvention_parameters sp ON sp.offer_parameter_id = op.id
    LEFT JOIN discount_parameters dp ON dp.offer_parameter_id = op.id
    WHERE op.offer_id IN (:offerIds)
    AND op.status = 'A'
    """, nativeQuery = true)
List<OfferParameterProjections> findByOfferIds(@Param("offerIds") List<Long> offerIds);
```

### 4.6 Redis Hash for Batch Lookups

```java
// Product mapping uses Redis HMGET for batch retrieval
// Key: PRODUCT_MAPPING:{clientId} (Redis Hash)
// Field: externalProductId
// Value: internalProductId

List<String> internalIds = redisTemplate.opsForHash()
    .multiGet("PRODUCT_MAPPING:" + clientId, externalProductIds);
// Single round-trip for N product lookups
```

### 4.7 TTL Jitter (Thundering Herd Prevention)

```java
// RedisCacheService.java
private long addJitter(long baseTtl) {
    // Add random 0-30 seconds to prevent cache stampede
    return baseTtl + ThreadLocalRandom.current().nextLong(0, 30);
}

// Without jitter: 1000 keys expire simultaneously → DB overload
// With jitter: Keys expire over 30-second window → gradual DB load
```

### 4.8 Hot Key Tracking & Pre-warming

```java
// HotKeyTracker.java
public class HotKeyTracker {
    // In-memory counter (high-performance, no Redis round-trip on every access)
    private final ConcurrentHashMap<String, LongAdder> localCounters = new ConcurrentHashMap<>();
    
    public void trackAccess(String key) {
        localCounters.computeIfAbsent(key, k -> new LongAdder()).increment();
    }
    
    @Scheduled(fixedRate = 60000) // Flush every 60 seconds
    public void flushToRedis() {
        localCounters.forEach((key, counter) -> {
            long count = counter.sumThenReset();
            if (count > 0) {
                redis.zincrby("HOT_KEYS_SORTED_SET", count, key);
            }
        });
    }
    
    public List<String> getTopHotKeys(int limit) {
        return redis.zrevrange("HOT_KEYS_SORTED_SET", 0, limit - 1);
    }
}

// After cache invalidation, hot keys are immediately re-warmed:
// 1. Get top-1000 hot keys matching invalidated pattern
// 2. Reconstruct cache entries from DB
// 3. SET with normal TTL
```

### 4.9 BIN Range Lookup with Sorted Sets

```java
// BIN ranges stored as Redis Sorted Set
// Score = BIN number (numeric), Value = JSON(issuer_id, bin_group_id, card_type)

// Lookup: Find which issuer owns a given BIN
Set<String> result = redis.zrangeByScore("bin_range", binNumber, binNumber);
// O(log N) lookup instead of full-table scan

// Alternatively: ZRANGEBYSCORE for range queries
// Find all BINs in range [411111, 411199]
```

### 4.10 Rate Limiting (Token Bucket via Redis Lua)

```lua
-- Redis Lua script for atomic token bucket rate limiting
local key = KEYS[1]
local rate = tonumber(ARGV[1])          -- tokens per second
local capacity = tonumber(ARGV[2])       -- max burst capacity
local now = tonumber(ARGV[3])            -- current timestamp (ms)
local requested = tonumber(ARGV[4])      -- tokens requested (usually 1)

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Calculate refill
local elapsed = (now - last_refill) / 1000.0
local new_tokens = math.min(capacity, tokens + (elapsed * rate))

if new_tokens >= requested then
    new_tokens = new_tokens - requested
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
    return 1  -- allowed
else
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
    return 0  -- rejected
end
```

---

## 5. Redis Configuration

### 5.1 Connection Pool Settings
```properties
# ReadServ Redis Config
cache.poolMaxActive=16
cache.poolMaxIdle=8
cache.poolMinIdle=4
cache.poolMaxWaitMs=2000
spring.data.redis.connect-timeout=120000
spring.data.redis.ssl.enabled=true

# Gateway Adapter Redis Config
redis.host=localhost
redis.port=6379
redis.minIdle=100
redis.maxIdle=500
redis.maxTotal=500
```

### 5.2 TTL Configuration Summary
```properties
# ReadServ
cache.default-ttl=7200                    # 2 hours (generic)
cache.ttlOfferCodes=86400                 # 24 hours (offer codes - slow changing)
cache.ttlOfferDetails=3600                # 1 hour (offer details)
calculate-emi.offer.cache.default.ttl=60  # 60 minutes (EMI response)
caching.spring.refreshConfigTTL=21600000  # 6 hours (in-memory master data)

# CacheManagementServ
cache.default-ttl=7200                    # 2 hours + 0-30s jitter
cache.dedup.window.minutes=10             # Event dedup window

# Gateway Adapter
redis.ttl=3600                            # 1 hour (issuer data)
product.cache.ttl=2592000                 # 30 days (product details)
```

---

## 6. Performance Metrics & Monitoring

### Key Performance Indicators

| Metric | Target | Measurement |
|--------|--------|-------------|
| EMI Discovery P95 Latency | < 200ms | Cache hit path |
| EMI Discovery P95 Latency | < 800ms | Cache miss path |
| Cache Hit Rate (ReadServ) | > 85% | Redis GET success / total requests |
| Cache Hit Rate (Offer Data) | > 90% | CacheMgmt cache / total lookups |
| Redis Command Latency | < 5ms (P99) | Redis MONITOR / Prometheus |
| DB Query Latency (Read Replica) | < 50ms (P95) | HikariCP metrics |
| Compression Ratio | > 75% | Compressed size / original size |

### Monitoring Points
```
@LogTime annotation on all service methods → method-level timing
Prometheus metrics via Micrometer → /metrics endpoint
Custom gauges: cache_hit_count, cache_miss_count, cache_size_bytes
Rate limiter metrics: requests_allowed, requests_rejected
```

---

## 7. Capacity Planning

### Redis Memory Estimation
```
Per-client EMI response cache:
  - Average compressed size: 3KB
  - Unique request variations per client: ~500/day
  - Active clients: 5,000
  - TTL: 60 min → ~1,500 active keys per client at peak
  - Total: 5,000 × 1,500 × 3KB = ~22GB

Offer data cache:
  - ~50,000 active offers × 5 cache entries × 2KB avg = ~500MB

BIN range sorted set:
  - ~100,000 BIN ranges × 200B = ~20MB

Total estimated Redis footprint: ~25GB (recommend 32GB ElastiCache cluster)
```

### Connection Pool Sizing
```
ReadServ:
  - HikariCP max-pool-size: 100 (per replica)
  - 3 read replicas → 300 total DB connections
  - Async executor: 25 threads
  - Concurrent request capacity: ~500 RPS

TransactionServ:
  - HikariCP max-pool-size: 50
  - Single writer node
  - Write capacity: ~200 TPS
```
