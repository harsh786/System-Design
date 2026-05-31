# Aerospike Database Deep Dive

**Purpose:** Practical system-design notes for understanding Aerospike as a production database for very high read/write workloads.

**Focus:** data model, why Aerospike is fast, partitioning, replication, consistency, hotspots, session-store design, cache-store design, and production readiness.

**Docs checked:** Context7 was used for current Aerospike documentation. Official references are listed at the end.

## 1. What Aerospike Is

Aerospike is a distributed NoSQL database optimized for high-throughput, low-latency operational workloads. It is usually used when the application knows the key it wants to read or write.

Good fit:

- Session store.
- Durable cache store.
- User profile store.
- Device state store.
- Fraud/risk feature store.
- Ad-tech frequency capping.
- Real-time counters with careful key design.
- Personalization and recommendation feature lookup.
- Rate limiting and quota counters.
- Shopping cart/session-like state.

Poor fit:

- Arbitrary joins.
- Heavy analytical queries.
- Global sorting over large datasets.
- Unbounded scans in the user-facing path.
- Frequently changing ad hoc query patterns.
- Large multi-record transactions as the core workload.

Aerospike is strongest when the hot path looks like this:

```text
service receives request
  -> derive exact key
  -> read/update one record or a small batch of records
  -> respond within a tight latency budget
```

## 2. Data Model

Aerospike data is organized as:

```text
namespace -> set -> record -> bins
```

| Concept | Meaning |
|---|---|
| Namespace | Top-level data container. Holds policies such as storage engine, replication, consistency, TTL, and memory settings. |
| Set | Optional logical collection inside a namespace. Similar to a table name, but schema-free. |
| Record | A single object identified by a key. |
| Bin | A named field inside a record. |
| Key | Application-defined identifier for a record. |
| Digest | Internal hash derived from namespace, set, and key. Used for lookup/distribution. |
| Primary index | Always-present index for locating records quickly. |
| Secondary index | Optional index on bin values. Use only for selective bounded queries. |

Example record:

```text
namespace: auth
set: session
key: sess_9a8f7c

bins:
  user_id = "u123"
  device_id = "ios_abc"
  scopes = ["checkout", "profile"]
  created_at = 2026-05-27T10:00:00Z
  last_seen_at = 2026-05-27T10:05:00Z
  risk_level = "low"
```

The best access path is direct key lookup:

```text
get(namespace, set, key)
```

Aerospike does not require a fixed schema for bins. Different records in the same set can have different bins, though production systems should still define conventions for maintainability.

## 3. Why Aerospike Is Fast

Aerospike is fast because it reduces the amount of coordination and disk work needed for the common key-value path.

### 3.1 Cluster-Aware Clients

Aerospike clients maintain cluster metadata and a partition map. The client can usually route a request directly to the node responsible for the key.

Read path:

```text
application key
  -> client computes digest/partition
  -> client sends request to owning node
  -> node finds record through primary index
  -> node returns bins
```

Why this matters:

- No central routing service required.
- Fewer network hops.
- Less coordinator overhead.
- Better latency at high QPS.

### 3.2 Primary Index

Aerospike maintains a primary index for records. The primary index maps record digests to storage locations.

This makes point lookups efficient:

```text
record key -> digest -> primary index entry -> record location
```

Production impact:

- Index memory must be capacity planned.
- More records means more primary-index memory.
- Small records with huge record counts can become index-memory dominated.

### 3.3 Hybrid Memory And Flash Storage

Aerospike can store indexes and data using DRAM, persistent memory, SSD, or NVMe depending on namespace configuration and edition/features.

Common production pattern:

```text
primary index: memory
record data:   NVMe/SSD
```

Why this is useful:

- Memory gives fast record location.
- NVMe/SSD gives larger capacity than all-RAM.
- Costs less than storing everything in memory.
- Works well for operational workloads with random point reads/writes.

### 3.4 Fixed Logical Partitions

Aerospike distributes records across fixed logical partitions. A namespace has 4096 logical partitions. Records are assigned by hashing the key digest.

Mental model:

```text
key -> digest -> partition id -> master node + replica node(s)
```

Benefits:

- High-cardinality keys spread naturally.
- Nodes own many partitions, not one huge shard.
- Adding/removing nodes rebalances partition ownership.
- Application code does not need to manually pick database shards.

### 3.5 Record-Level Operations

Aerospike is optimized for single-record operations:

- `get`
- `put`
- `add` / counter increment
- `operate`
- compare-and-set through generation checks
- list/map operations inside a record
- TTL update

This is important because many real-time systems do not need large transactions. They need extremely fast, correct updates to one user/session/counter/profile record.

## 4. Partitioning In Aerospike

Aerospike partitioning is based on the record key.

```text
namespace + set + user key -> digest -> partition
```

Good keys:

- High cardinality.
- Stable.
- Naturally distributed.
- Derived from the access pattern.
- Avoid putting all traffic on one key.

Bad keys:

- `global_counter`
- `today_all_sessions`
- `campaign_123_total`
- `product_999_stock` if every write hits this one key during a flash sale.

There is no separate clustering-key concept in Aerospike. If the application needs ordering or grouping, model it explicitly with:

- Composite record keys.
- Time buckets.
- Hash buckets.
- Bounded lists/maps inside one record.
- Lookup records.
- Secondary indexes only for selective, bounded queries.

Composite key examples:

```text
session:
  key = session_id

daily user feature:
  key = user:u123|day:2026-05-27

ad frequency cap:
  key = tenant:t1|campaign:c99|user:u123|day:2026-05-27

cache record:
  key = cache:v1|product:p555|locale:en-IN|currency:INR

rate limit counter:
  key = tenant:t1|api:checkout|user:u123|minute:2026-05-27T10:42
```

## 5. Replication And Consistency

Aerospike replicates partitions across nodes according to namespace replication settings.

With replication factor 2:

```text
partition P
  master copy: node A
  replica copy: node B
```

With replication factor 3:

```text
partition P
  master copy: node A
  replica copy: node B
  replica copy: node C
```

### 5.1 AP Mode

AP mode prioritizes availability during failures and partitions.

Use AP mode for:

- Session data where availability matters more than strict global consistency.
- Cache-like data.
- User preferences.
- Feature store values that can tolerate last-write-wins behavior.
- High-QPS serving systems where occasional stale reads are acceptable.

Tradeoff:

- During failure scenarios, the system may accept availability over strict consistency.
- Application design should tolerate retries, duplicate writes, and stale values where appropriate.

### 5.2 Strong Consistency Mode

Strong consistency mode prioritizes consistency over availability during certain partition/failure cases.

Use strong consistency for:

- Entitlements.
- Inventory reservations.
- Account state where stale reads cause real damage.
- Critical authorization state.
- Workloads that need stronger read-after-write guarantees.

Tradeoff:

- Some operations may be unavailable during cluster partition or replica unavailability.
- Latency and operational requirements can be stricter.

### 5.3 CAP Framing

During a network partition, a distributed database must choose between serving every request and preserving strict consistency.

Aerospike gives namespace-level choices:

```text
AP mode: preserve availability, accept consistency tradeoffs
SC mode: preserve consistency, accept availability tradeoffs
```

Pick the mode from business correctness, not from preference.

## 6. TTL, Expiration, And Eviction

Aerospike supports record TTL. TTL is central to session-store and cache-store designs.

Common TTL usage:

```text
session record: 30 minutes sliding TTL
password reset token: 10 minutes
idempotency key: 24 hours
product cache: 5 minutes
rate limit counter: 60 seconds
daily frequency cap: expire after 2-7 days
```

Expiration:

- Record becomes logically expired after TTL.
- Expired data is cleaned by background expiration/eviction processes.
- The app should not depend on exact physical deletion time.

Production note:

TTL reduces manual cleanup, but high expiration volume is still database work. Capacity plan for expiry churn.

## 7. Hotspot Problems

A hotspot happens when a small number of records, partitions, tenants, or nodes receive too much traffic.

Aerospike distributes many keys very well. It cannot automatically split one hot record into many independently writable records. Key design must handle that.

### 7.1 Hotspot Type 1: Single Hot Counter

Problem:

```text
key = video:v123|likes_total
```

Every like update hits the same record.

Traffic:

```text
1 viral video
500,000 likes/minute
all writes -> one record -> one partition owner -> one node bottleneck
```

Bad write path:

```text
increment video:v123|likes_total
increment video:v123|likes_total
increment video:v123|likes_total
...
```

Fix: sharded counter.

```text
key = video:v123|likes_total|bucket:000
key = video:v123|likes_total|bucket:001
key = video:v123|likes_total|bucket:002
...
key = video:v123|likes_total|bucket:255
```

Write:

```text
bucket = hash(user_id or request_id) % 256
increment video:v123|likes_total|bucket:{bucket}
```

Read:

```text
batch read 256 buckets
sum counts
cache total for 1-5 seconds
```

Tradeoff:

- Writes spread across many records and partitions.
- Reads need aggregation.
- A short aggregate cache makes reads cheap.

### 7.2 Hotspot Type 2: Flash-Sale Product Inventory

Problem:

```text
key = product:p999|stock
```

During a flash sale, every buyer tries to decrement the same stock record.

Traffic:

```text
100,000 checkout attempts in 30 seconds
all writes -> product:p999|stock
```

If strict inventory correctness is required, do not blindly shard stock without a reservation design, because oversell can happen.

Option A: reservation buckets.

```text
key = product:p999|stock_bucket:00
key = product:p999|stock_bucket:01
...
key = product:p999|stock_bucket:63
```

Each bucket has a fixed allocated quantity:

```text
bucket 00 = 100 units
bucket 01 = 100 units
...
```

Buyer chooses:

```text
bucket = hash(user_id) % 64
attempt decrement on that bucket
if bucket empty, try limited fallback buckets
```

Option B: queue-based serialization.

```text
checkout request -> queue -> inventory worker -> Aerospike reservation record
```

Use when correctness matters more than immediate synchronous throughput.

Option C: front-door admission control.

```text
only allow N checkout attempts/sec for product p999
reject/waitlist overflow
```

Best production design often combines:

- Aerospike for fast reservation state.
- Queue for fairness and smoothing.
- Rate limiter for overload protection.
- Final source-of-truth reconciliation in order/payment system.

### 7.3 Hotspot Type 3: Hot Cache Key

Problem:

```text
key = cache:homepage:IN
```

One homepage cache key receives 1M reads/minute.

Read hotspots are easier than write hotspots, but still dangerous because one partition owner may receive too many reads.

Fix options:

1. Put CDN/app-local cache in front.

```text
browser/CDN -> app memory cache -> Aerospike
```

2. Use short-lived replicated application cache.

```text
app instance caches cache:homepage:IN for 1-5 seconds
```

3. Create read replicas at the application level only when data is immutable for the TTL window.

```text
cache:homepage:IN|copy:00
cache:homepage:IN|copy:01
...
cache:homepage:IN|copy:15
```

Write all copies when regenerating cache, then read one copy by hashing request ID.

Use this carefully. It improves read spreading but makes invalidation/update more complex.

### 7.4 Hotspot Type 4: Hot Tenant

Problem:

```text
tenant:t1 produces 80% of total traffic
```

If keys are still high-cardinality:

```text
tenant:t1|session:s1
tenant:t1|session:s2
tenant:t1|session:s3
```

the load can still spread well. The problem appears when tenant-level aggregate keys are hot:

```text
tenant:t1|requests_current_minute
tenant:t1|billing_total_today
```

Fix:

```text
tenant:t1|requests_current_minute|bucket:00
tenant:t1|requests_current_minute|bucket:01
...
tenant:t1|requests_current_minute|bucket:127
```

Also add:

- Tenant-level rate limits.
- Per-tenant dashboards.
- Dedicated namespace/cluster for very large tenants if needed.
- Async aggregation for billing/reporting counters.

### 7.5 Hotspot Debugging Checklist

When latency rises, identify the hotspot type:

```text
Is it one key?
Is it one set?
Is it one namespace?
Is it one tenant?
Is it one node?
Is it one device?
Is it one client service?
Is it retries multiplying traffic?
```

Mitigation table:

| Symptom | Likely cause | Fix |
|---|---|---|
| One key has huge write QPS | Hot counter/state record | Shard the record, use buckets, aggregate async. |
| One key has huge read QPS | Hot cache/config/profile | Add app/CDN cache, use copy keys if safe. |
| One tenant dominates traffic | Noisy tenant | Rate limit, split tenant aggregates, isolate tenant. |
| One node has high latency | Partition/device imbalance or hot partition | Check partition stats, device latency, migrations, client routing. |
| Secondary-index query is slow | Low-selectivity query | Replace with direct lookup/materialized keys. |
| Latency spikes after node change | Migration/rebalance load | Throttle operations, add headroom, avoid peak windows. |

## 8. Use Case: Aerospike As A Session Store

### 8.1 Problem

An e-commerce application needs to store login sessions for web and mobile users.

Requirements:

- Read session on every request.
- Update `last_seen_at` frequently.
- Expire idle sessions automatically.
- Support logout.
- Survive node failure.
- Keep latency low at high QPS.

Traffic example:

```text
active sessions: 80 million
average read QPS: 150,000
peak read QPS: 600,000
write/update QPS: 80,000
session TTL: 30 minutes idle / 30 days refresh
```

### 8.2 Data Model

```text
namespace: auth
set: session
key: session_id
```

Bins:

```text
user_id
device_id
created_at
last_seen_at
scopes
risk_score
ip_country
status
refresh_token_hash
```

Example:

```text
key = sess:01HX9W4R8Z7E1S

bins:
  user_id = u123
  device_id = ios_a71
  status = ACTIVE
  scopes = ["cart", "checkout", "profile"]
  created_at = 2026-05-27T10:00:00Z
  last_seen_at = 2026-05-27T10:28:00Z
```

### 8.3 Read Flow

```text
request comes with session cookie
  -> app extracts session_id
  -> Aerospike get(auth, session, session_id)
  -> if missing/expired: reject or refresh
  -> if ACTIVE: authorize request
```

### 8.4 Write Flow

Login:

```text
create random session_id
put session record with TTL
return secure cookie/token
```

Activity update:

```text
operate session record:
  set last_seen_at
  touch/extend TTL if using sliding session
```

Logout:

```text
delete session_id
or set status = REVOKED with short TTL for audit/propagation
```

### 8.5 Why Aerospike Fits

- Session ID is a perfect high-cardinality key.
- Reads are direct key lookups.
- TTL handles expiration.
- Replication handles node failure.
- Updates are single-record operations.
- Data size per session is bounded.

### 8.6 Session Store Pitfalls

Do not model all sessions for a user in one giant record:

```text
bad key = user:u123|all_sessions
```

That record can grow and become hot.

Better:

```text
primary record:
  key = session_id

optional lookup record:
  key = user:u123|sessions
  bins/list = bounded recent session IDs
```

If users can have many sessions/devices, keep the lookup bounded or maintain it asynchronously.

### 8.7 Consistency Choice

For normal web sessions:

```text
AP mode + replication + TTL
```

is often acceptable because availability is important and stale session state for a short window may be tolerable.

For critical authorization or entitlement sessions:

```text
strong consistency namespace
```

may be better if stale authorization is dangerous.

## 9. Use Case: Aerospike As A Cache Store

### 9.1 Problem

A product catalog service calls many expensive downstream systems. It needs a durable low-latency cache so applications do not overload source systems.

Requirements:

- Key-value access.
- TTL per cached object.
- Very high read QPS.
- Cache survives app restarts.
- Cache can be regenerated on miss.
- Avoid thundering herd on popular keys.

Traffic example:

```text
catalog cache records: 500 million
average read QPS: 300,000
peak read QPS: 1 million
write QPS: 20,000
TTL: 5 minutes for price, 1 hour for static metadata
```

### 9.2 Data Model

```text
namespace: cache
set: product_view
key: cache:v3|product:p555|locale:en-IN|currency:INR
```

Bins:

```text
payload_json
etag
source_version
created_at
expires_policy
compressed_payload
```

Example:

```text
key = cache:v3|product:p555|locale:en-IN|currency:INR

bins:
  payload_json = "{...}"
  source_version = "catalog_2026_05_27_1040"
  etag = "e98a..."
```

### 9.3 Read-Through Cache Flow

```text
app receives product request
  -> build cache key
  -> Aerospike get
  -> hit: return payload
  -> miss: fetch source systems
  -> write cache record with TTL
  -> return payload
```

### 9.4 Write-Through Cache Flow

```text
source update happens
  -> update source of truth
  -> update Aerospike cache record
  -> publish invalidation event
```

### 9.5 Cache-Aside With Request Coalescing

Problem:

When a hot key expires, thousands of requests can miss at the same time.

Bad:

```text
10,000 requests miss cache
  -> 10,000 requests call source systems
  -> source system overload
```

Fix:

```text
first request obtains refresh lock
other requests serve stale value for short grace window or wait
first request refreshes Aerospike
lock releases
```

Aerospike records:

```text
cache data key:
  cache:v3|product:p555|locale:en-IN|currency:INR

refresh lock key:
  lock:cache:v3|product:p555|locale:en-IN|currency:INR
```

Use a short TTL on lock records:

```text
lock TTL = 5-15 seconds
```

### 9.6 Why Aerospike Fits Cache Store

- Direct key lookup.
- TTL is built into the record lifecycle.
- Data can be larger than memory when using flash-backed storage.
- Cache survives application restarts.
- Replication reduces cache loss during node failure.
- Strong operational metrics help detect cache churn and hot keys.

### 9.7 Cache Store Pitfalls

- Do not run broad filter queries on cache records.
- Do not store huge payloads if network transfer dominates latency.
- Avoid one global cache key for all users/products.
- Avoid synchronized TTLs that expire millions of keys at the same second.
- Add TTL jitter:

```text
ttl = base_ttl + random(0, jitter_seconds)
```

Example:

```text
price cache TTL = 300 seconds + random(0..60 seconds)
```

This spreads expirations and reduces thundering herd.

## 10. Use Case: Rate Limiting

Problem:

An API platform needs to enforce:

```text
100 requests per user per minute
10,000 requests per tenant per minute
```

User-level key:

```text
namespace: limits
set: request_counter
key: tenant:t1|user:u123|api:checkout|minute:2026-05-27T10:42
```

Operation:

```text
increment count
set TTL = 2 minutes
if count > limit -> reject
```

Tenant-level aggregate can become hot. Use buckets:

```text
key = tenant:t1|api:checkout|minute:2026-05-27T10:42|bucket:00
...
key = tenant:t1|api:checkout|minute:2026-05-27T10:42|bucket:63
```

Write:

```text
bucket = hash(request_id) % 64
increment bucket
```

Read/enforce:

- For exact enforcement, sum buckets before accepting expensive operations.
- For approximate fast enforcement, use local app counters and Aerospike as shared backing.
- For hard global limits, combine queue/admission control with bucketed counters.

## 11. Use Case: Ad Frequency Capping

Problem:

During ad bidding, decide whether a user has already seen a campaign too many times.

Key:

```text
namespace: ads
set: freq_cap
key: tenant:t1|campaign:c777|user:u123|day:2026-05-27
```

Bins:

```text
impressions
clicks
last_seen_at
```

Read/update:

```text
get key
if impressions < cap:
  allow bid
  increment impressions
else:
  reject bid
```

Why this key works:

- Includes user ID, so a popular campaign spreads across many users.
- Day bucket bounds record lifetime and reset behavior.
- TTL removes old cap records.
- The user-campaign-day record is updated atomically.

Bad key:

```text
key = campaign:c777|impressions_total
```

That puts all writes for a popular campaign into one record.

Fix campaign totals with sharded counters or asynchronous analytics:

```text
campaign:c777|impressions_total|bucket:000
...
campaign:c777|impressions_total|bucket:255
```

### 11.1 Why Add Buckets To Campaign Totals?

The bucket is added because `campaign:c777|impressions_total` is one physical record. If every impression for a popular campaign increments that one record, all writes go to the partition owner for that one key.

Bad design:

```text
1 campaign receives 2 million impressions/minute
all writes increment:
  campaign:c777|impressions_total
```

Result:

```text
one record is hot
one partition owner gets overloaded
latency rises
timeouts and retries make load worse
```

Bucketed design:

```text
campaign:c777|impressions_total|bucket:000
campaign:c777|impressions_total|bucket:001
campaign:c777|impressions_total|bucket:002
...
campaign:c777|impressions_total|bucket:255
```

Now the campaign total is split across 256 independent records. Each bucket key hashes independently, so writes are spread across many partitions and nodes.

Write flow:

```text
on impression event:
  bucket = hash(user_id or impression_id) % 256
  key = campaign:c777|impressions_total|bucket:{bucket}
  increment impressions_count for that bucket
```

Example:

```text
user u101 -> hash(u101) % 256 = 13
  increment campaign:c777|impressions_total|bucket:013

user u222 -> hash(u222) % 256 = 91
  increment campaign:c777|impressions_total|bucket:091

user u333 -> hash(u333) % 256 = 13
  increment campaign:c777|impressions_total|bucket:013
```

This does not make writes disappear. It spreads them across 256 records instead of forcing all writes into one record.

### 11.2 How Reads Work From Multiple Buckets

To read the exact total, the service reads all bucket records and sums them.

Read flow:

```text
keys = [
  campaign:c777|impressions_total|bucket:000,
  campaign:c777|impressions_total|bucket:001,
  ...
  campaign:c777|impressions_total|bucket:255
]

records = batch_get(keys)
total = sum(record.impressions_count for record in records)
```

Example:

```text
bucket:000 = 10,500
bucket:001 = 8,200
bucket:002 = 12,100
...
bucket:255 = 9,900

campaign_total = sum(all 256 bucket counts)
```

Read tradeoff:

- Write path becomes scalable because each impression updates only one bucket.
- Exact read path becomes more expensive because it reads many buckets.
- This is usually acceptable because aggregate campaign totals are read much less frequently than they are written.

Production optimization:

```text
write path:
  increment one bucket synchronously

read path:
  batch read all buckets only when exact total is needed
  cache the summed total for 1-5 seconds
  or compute totals asynchronously through stream processing
```

For dashboards, exact real-time totals are often unnecessary. A common production design is:

```text
impression event
  -> increment Aerospike bucket for fast serving/control
  -> publish event to Kafka
  -> stream processor aggregates campaign totals
  -> dashboard reads precomputed total
```

### 11.3 When Not To Use Bucketed Counters

Do not use bucketed counters if every request needs a strongly consistent exact total before proceeding.

Example:

```text
campaign has hard budget of exactly 1,000,000 impressions
every impression must check global total before allowing the ad
```

In that case, bucketed counters can overshoot unless paired with reservation blocks, admission control, or a centralized budget allocator.

Better strict-budget design:

```text
campaign budget allocator
  -> grants each bucket/worker a reservation block
  -> workers spend from local reservation
  -> allocator stops granting when campaign budget is exhausted
```

## 12. Use Case: Fraud Feature Store

Problem:

A payment service needs real-time risk features before approving payment.

Keys:

```text
account features:
  key = account:u123

device features:
  key = device:d789

ip features:
  key = ip:203.0.113.10

card features:
  key = card_hash:abc123
```

Payment flow:

```text
payment request
  -> batch get account/device/ip/card feature records
  -> score risk
  -> approve/decline/challenge
  -> asynchronously update counters/events
```

Why Aerospike fits:

- Batch get of known keys.
- Low latency.
- Atomic counters for velocity features.
- TTL for rolling-window features.
- Data model is naturally key-value.

## 13. Secondary Indexes

Aerospike supports secondary indexes, but they should not be treated as free relational indexes.

Good secondary-index use:

```text
admin query:
  find sessions by status = SUSPICIOUS for a small tenant and time window

support query:
  find records with exact order_id
```

Risky secondary-index use:

```text
status = ACTIVE
country = IN
plan = FREE
```

Low-cardinality values can match huge portions of a set and create expensive distributed queries.

Better production patterns:

- Direct key lookup.
- Lookup records.
- Precomputed query-specific records.
- Event stream into analytics/search store for broad queries.

Example lookup record:

```text
email lookup:
  key = email_hash:89ab...
  bin user_id = u123

profile:
  key = user:u123
```

## 14. Production Design Checklist

Before using Aerospike for a workload, answer:

```text
What exact key does each request use?
Is the key high-cardinality?
Can one key become hot?
What is the p99 record size?
What is the record count?
What is the primary-index memory requirement?
What is the read/write QPS?
What is peak multiplier?
What TTL is required?
What happens on cache miss?
What happens on duplicate retry?
What consistency mode is needed?
What replication factor is needed?
What is the backup/restore plan?
What is the failover plan?
Which metrics prove the design is healthy?
```

### 14.1 Capacity Planning

Plan for:

- Record count.
- Average and p99 record size.
- Primary-index memory.
- Secondary-index memory if used.
- Replication factor.
- TTL churn.
- Write amplification from replicas.
- Defragmentation headroom.
- Migration/rebalance headroom.
- Peak traffic, not only average traffic.

Simple sizing:

```text
logical_data = record_count * average_record_size
replicated_data = logical_data * replication_factor
index_memory = record_count * index_bytes_per_record
peak_ops = average_ops * peak_multiplier
```

Keep headroom:

```text
do not run storage close to full
do not run memory close to full
reserve capacity for node failure and migrations
```

### 14.2 Client Configuration

Important client settings:

- Timeouts.
- Retry count.
- Retry backoff.
- Connection pool size.
- Batch concurrency.
- Read mode.
- Replica policy.
- Write commit policy.
- Circuit breaker behavior.

Bad retries can create an outage multiplier:

```text
service timeout
  -> every request retries 3 times immediately
  -> database load triples
  -> latency gets worse
```

Use bounded retries with jitter and backoff.

### 14.3 Observability

Monitor:

- Client p50/p95/p99/p999 latency.
- Server read/write latency.
- Timeouts.
- Retry count.
- Error count.
- Record count.
- Memory used by indexes.
- Device utilization and latency.
- Network throughput.
- Migrations.
- Evictions/expirations.
- Defragmentation.
- Namespace free space.
- Hot keys from application metrics.
- Per-tenant QPS.

Application metrics should include:

```text
top keys by QPS
top tenants by QPS
cache hit ratio
cache miss ratio
session read/write QPS
TTL expiration rate
retry rate
timeout rate
```

### 14.4 Backup And Restore

Replication is not backup.

Backups protect against:

- Bad deploys.
- Accidental deletes.
- Corrupt writes.
- Operator mistakes.
- Disaster recovery.

Production needs:

- Backup schedule.
- Restore drills.
- Retention policy.
- Encrypted backups.
- Cross-region copy if needed.
- Clear RPO/RTO.

### 14.5 Security

Cover:

- TLS for client traffic.
- TLS for inter-node/cross-site traffic when required.
- Authentication.
- Role-based access control.
- Least-privilege users.
- Encryption at rest if required.
- Audit logging for admin actions.
- Network isolation.
- Secrets management.

## 15. Common Mistakes

- Using Aerospike for arbitrary analytical queries.
- Creating low-selectivity secondary indexes on hot paths.
- Designing one global counter record.
- Storing all user events in one record.
- Using the same TTL for millions of cache records, causing synchronized expiry.
- Forgetting index memory in capacity planning.
- Ignoring p99 and p999 latency.
- Retrying too aggressively.
- Running migrations/rebalances without headroom.
- Treating replication as backup.
- Not instrumenting hot keys and hot tenants.

## 16. Interview-Ready Answers

### Why is Aerospike fast?

Because the client routes directly to the right node, the primary index locates records quickly, data is partitioned across nodes, storage is optimized for memory plus flash, and the system is built around efficient record-level operations.

### How does Aerospike solve high read and write load?

It spreads high-cardinality keys across partitions and nodes. Reads use direct key lookup. Writes are single-record operations replicated according to namespace policy. Horizontal scale comes from adding nodes, but hot records still require application-level sharding or caching.

### How does partitioning work?

Aerospike hashes the record key into a digest and maps it to one of the namespace partitions. Partition ownership tells the client which node should receive the request.

### Does Aerospike have clustering keys?

No. Aerospike uses record keys for placement and lookup. If you need time ordering, grouping, or range access, model it explicitly using composite keys, buckets, bounded lists/maps, lookup records, or a separate query/analytics system.

### How do you solve hotspots?

First identify the hotspot type. Then:

- Shard hot counters into buckets.
- Add TTL jitter for cache keys.
- Put app/CDN cache in front of hot read keys.
- Use request coalescing for cache misses.
- Split tenant-level aggregates.
- Use queues/admission control for strict hot inventory.
- Avoid low-cardinality secondary-index queries.

### When should Aerospike be used as a session store?

When sessions are read by `session_id`, have bounded record size, need TTL-based expiry, and require high availability with low latency.

### When should Aerospike be used as a cache store?

When the cache must be distributed, durable across app restarts, larger than app memory, TTL-driven, and accessed by exact keys.

## 17. Official References Used

- Context7 library resolution used: `/websites/aerospike`.
- Aerospike data model: https://aerospike.com/docs/database/learn/architecture/data-storage/data-model.md
- Aerospike architecture overview: https://aerospike.com/docs/database/learn/architecture/
- Aerospike clustering and data distribution: https://aerospike.com/docs/database/learn/architecture/clustering/data-distribution/
- Aerospike flexible storage: https://aerospike.com/docs/database/learn/architecture/hybrid-storage/
- Aerospike consistency modes: https://aerospike.com/docs/server/architecture/consistency
- Aerospike primary and secondary indexes: https://aerospike.com/docs/develop/data-modeling/indexes/
- Aerospike transactions and record operations: https://aerospike.com/docs/database/learn/transactions/
- Aerospike security: https://aerospike.com/docs/database/manage/security/
- Aerospike TLS: https://aerospike.com/docs/database/manage/network/tls/
