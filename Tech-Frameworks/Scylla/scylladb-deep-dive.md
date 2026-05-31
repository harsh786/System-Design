# ScyllaDB Deep Dive - Architecture, Data Modeling, Performance, and Production Playbook

**Purpose:** A practical learning note for understanding ScyllaDB from system-design, production, and real-world problem-solving angles.

**Primary focus:** why ScyllaDB is fast, how it handles high read/write workloads, data modeling with partition and clustering keys, hotspot prevention, compaction strategies, internals, replication, CAP tradeoffs, and production readiness.

**Docs checked:** Context7 was used for current ScyllaDB docs, and official ScyllaDB docs were also referenced. Links are listed at the end.

## 1. Mental Model

ScyllaDB is a distributed, wide-column, NoSQL database designed for very high throughput and low latency. It is API-compatible with Apache Cassandra through CQL and also supports a DynamoDB-compatible API through Alternator.

The most important mental model:

- ScyllaDB is not a relational database.
- It is not optimized for ad hoc joins or arbitrary filters.
- It is optimized for known access patterns at very high scale.
- You model tables by query, not by entity normalization.
- The partition key decides where data lives.
- The clustering key decides how data is sorted inside one partition.
- High performance comes from combining data distribution, shard-per-core execution, LSM storage, caching, and careful compaction.

Good ScyllaDB design starts with this question:

> For each request, can I answer it by reading one known partition or a small bounded set of partitions?

If yes, ScyllaDB can be extremely fast. If no, the design probably needs a different table, a derived view, a search engine, or another database.

## 2. When To Use ScyllaDB

Use ScyllaDB when the workload has:

- Very high write throughput.
- Very high read throughput.
- Low-latency point lookups.
- Large data volume.
- Horizontal scale requirements.
- Multi-node fault tolerance.
- Predictable access patterns.
- Append-heavy or time-series data.
- High-cardinality keys.
- Event, message, timeline, session, profile, device, metrics, feed, or cache-like access patterns.

Common real-world examples:

- URL shortener redirect lookups.
- User session store.
- IoT sensor ingestion.
- Clickstream and event ingestion.
- Chat messages.
- Notification inboxes.
- User timelines.
- Fraud feature store.
- Ad-tech counters and impressions.
- Gaming player state.
- Large-scale metadata lookups.

Avoid ScyllaDB as the primary store when the workload requires:

- Complex joins.
- Multi-row, multi-table ACID transactions.
- Frequent arbitrary filtering.
- Unbounded scans.
- Global sorting across the whole dataset.
- Strong serializable consistency for many records.
- OLAP-style analytics over large historical ranges.

For those, use Postgres, MySQL, Snowflake, ClickHouse, Elasticsearch/OpenSearch, or a lakehouse alongside ScyllaDB.

## 3. Why ScyllaDB Is Fast

ScyllaDB is fast because several design choices compound together.

### 3.1 Shard-Per-Core Architecture

ScyllaDB uses a shard-per-core model. A node is divided into shards, usually one shard per CPU core. Each shard owns its own portion of data and handles its own CPU, memory, and I/O work.

This reduces:

- Lock contention.
- Cross-core coordination.
- Context switching.
- Shared mutable state.
- Scheduler overhead.

Instead of one database process with many threads constantly fighting over shared data structures, ScyllaDB keeps ownership local to each shard.

Practical impact:

- Adding CPU cores can increase throughput more linearly.
- Tail latency is more predictable.
- A hot shard is easier to identify than a vague overloaded process.
- Shard-aware drivers can send requests directly to the right CPU shard.

### 3.2 Shared-Nothing Scale-Out

ScyllaDB nodes are peers. There is no single primary node for all writes. Data is distributed across the cluster by hashing the partition key into a token range, then mapping that token to replicas.

Practical impact:

- No single write leader bottleneck.
- Writes can be accepted by multiple nodes.
- Cluster capacity grows by adding nodes.
- Failure of one node does not bring down the whole cluster if the consistency level can still be satisfied.

### 3.3 LSM Write Path

ScyllaDB uses a Log Structured Merge Tree style storage engine.

On write:

1. The write reaches a coordinator node.
2. The coordinator sends the mutation to the correct replicas.
3. Each replica appends the mutation to the commitlog.
4. Each replica updates an in-memory memtable.
5. The write is acknowledged when the requested consistency level is satisfied.
6. Later, memtables flush to immutable SSTables on disk.
7. Background compaction merges SSTables and removes overwritten or expired data.

This is fast because random writes are converted into:

- Sequential commitlog appends.
- Memory updates.
- Later sequential disk writes during flush.

The cost is that reads may need to merge data from memtables and multiple SSTables. Bloom filters, indexes, cache, and compaction reduce this read amplification.

### 3.4 Caching And Bloom Filters

ScyllaDB avoids unnecessary disk reads using:

- Row cache.
- Key cache/index metadata.
- Bloom filters.
- Partition summaries and indexes.
- OS-independent memory management.

Bloom filters answer this question cheaply:

> Could this SSTable contain this partition key?

If the answer is no, ScyllaDB skips that SSTable. If the answer is maybe, it checks indexes and may read from disk.

Bloom filters can have false positives, but not false negatives.

### 3.5 Query-First Data Modeling

ScyllaDB becomes fast when the query maps directly to the primary key:

- Partition key is known.
- Clustering range is bounded.
- No filtering across many partitions.
- Result set is limited.
- Query touches a small number of replicas.

Bad schema design can make ScyllaDB slow even on strong hardware. Good schema design is the main performance feature.

### 3.6 Shard-Aware Drivers

Shard-aware drivers know ScyllaDB's shard topology and can route requests to the right node and shard. This avoids extra internal forwarding and reduces latency.

Use official or compatible drivers that support:

- Token-aware routing.
- Shard-aware routing.
- Prepared statements.
- Connection pooling.
- Correct retry/idempotency behavior.
- Local datacenter awareness.

## 4. Core Terms

| Term | Meaning |
|---|---|
| Cluster | Group of ScyllaDB nodes. |
| Node | One ScyllaDB server/instance. |
| Shard | Per-core execution unit inside a node. |
| Keyspace | Similar to a database namespace; stores replication settings. |
| Table | Wide-column table modeled for specific queries. |
| Partition | Rows sharing the same partition key. |
| Partition key | Hash key used to distribute data across the cluster. |
| Clustering key | Sort key inside a partition. |
| Replica | Node/shard copy of a partition's data. |
| Coordinator | Node that receives a client request and coordinates replicas. |
| Consistency level | Number/location of replica responses required for success. |
| Memtable | In-memory write structure. |
| Commitlog | Durable append-only log for crash recovery. |
| SSTable | Immutable sorted on-disk table file. |
| Compaction | Background merging of SSTables. |
| Tombstone | Marker for deleted or expired data. |

## 5. Partition Key And Clustering Key

ScyllaDB primary keys have two parts:

```text
PRIMARY KEY ((partition_key_columns...), clustering_key_columns...)
```

The partition key is mandatory. Clustering columns are optional.

### 5.1 Partition Key

The partition key decides:

- Which token the row maps to.
- Which nodes store the row.
- Which shard handles the row.
- Which rows live together in one partition.

Example:

```cql
CREATE TABLE users_by_id (
  user_id uuid PRIMARY KEY,
  email text,
  name text,
  created_at timestamp
);
```

Here `user_id` is the partition key.

Good partition keys are:

- High cardinality.
- Evenly distributed.
- Present in the query.
- Stable.
- Not too large.
- Not too low-cardinality, such as `status`, `country`, or `type`.

Bad partition key examples:

- `status`, because there may be only a few statuses.
- `country`, because some countries can dominate traffic.
- `tenant_id` alone, if one tenant is huge.
- `date` alone, because all writes for today hit one partition.
- `celebrity_user_id`, if one user receives extreme traffic.

### 5.2 Clustering Key

The clustering key decides:

- How rows are ordered inside a partition.
- Which range queries are efficient inside that partition.
- Whether you can read newest-first, oldest-first, or by a compound order.

Example:

```cql
CREATE TABLE messages_by_conversation (
  conversation_id uuid,
  message_ts timestamp,
  message_id timeuuid,
  sender_id uuid,
  body text,
  PRIMARY KEY ((conversation_id), message_ts, message_id)
) WITH CLUSTERING ORDER BY (message_ts DESC, message_id DESC);
```

Here:

- `conversation_id` is the partition key.
- `message_ts, message_id` are clustering keys.
- Messages for one conversation are stored together.
- The newest messages can be read efficiently.

Efficient query:

```cql
SELECT *
FROM messages_by_conversation
WHERE conversation_id = ?
LIMIT 50;
```

Also efficient:

```cql
SELECT *
FROM messages_by_conversation
WHERE conversation_id = ?
  AND message_ts >= ?
  AND message_ts < ?
LIMIT 100;
```

Inefficient:

```cql
SELECT *
FROM messages_by_conversation
WHERE sender_id = ?;
```

That query needs a different table, for example `messages_by_sender`.

## 6. Primary Key Forms

### 6.1 Simple Partition Key

```cql
PRIMARY KEY (user_id)
```

Same as:

```cql
PRIMARY KEY ((user_id))
```

Use for point lookups.

### 6.2 Partition Key Plus Clustering Key

```cql
PRIMARY KEY ((conversation_id), message_ts)
```

Rows with the same `conversation_id` live in the same partition and are sorted by `message_ts`.

### 6.3 Composite Partition Key

```cql
PRIMARY KEY ((tenant_id, bucket_day), event_id)
```

Here the partition key is the tuple `(tenant_id, bucket_day)`.

This means:

- All events for one tenant on one day live together.
- Different tenants and days distribute independently.
- `event_id` sorts or uniquely identifies rows inside that partition.

### 6.4 Composite Partition Key With Multiple Clustering Columns

```cql
CREATE TABLE page_views_by_tenant_day (
  tenant_id uuid,
  bucket_day date,
  shard smallint,
  event_ts timestamp,
  event_id timeuuid,
  user_id uuid,
  url text,
  country text,
  PRIMARY KEY ((tenant_id, bucket_day, shard), event_ts, event_id)
) WITH CLUSTERING ORDER BY (event_ts DESC, event_id DESC);
```

Here:

- Partition key: `(tenant_id, bucket_day, shard)`.
- Clustering key: `(event_ts, event_id)`.
- The extra `shard` spreads a hot tenant-day across multiple partitions.
- Reads for a tenant/day fan out across `N` shards, then merge results in the application.

Good query:

```cql
SELECT *
FROM page_views_by_tenant_day
WHERE tenant_id = ?
  AND bucket_day = ?
  AND shard = ?
LIMIT 100;
```

For a full tenant/day read, the service queries all shard values:

```text
for shard in 0..31:
  query partition (tenant_id, bucket_day, shard)
merge by event_ts desc
return top K
```

## 7. Query-First Data Modeling

In ScyllaDB, a table is not an entity model. A table is a query-serving model.

Start with access patterns:

| Access Pattern | Table Shape |
|---|---|
| Get user by id | `users_by_id`, `PRIMARY KEY (user_id)` |
| Get user by email | `users_by_email`, `PRIMARY KEY (email)` |
| Get latest messages in conversation | `messages_by_conversation`, `PRIMARY KEY ((conversation_id), message_ts, message_id)` |
| Get events by tenant and day | `events_by_tenant_day`, `PRIMARY KEY ((tenant_id, day, shard), event_ts, event_id)` |
| Get URL by short code | `links_by_code`, `PRIMARY KEY (code)` |
| Get links by owner | `links_by_owner`, `PRIMARY KEY ((owner_id), created_at, code)` |

This means controlled duplication is normal.

Example: URL shortener.

```cql
CREATE TABLE links_by_code (
  code text PRIMARY KEY,
  long_url text,
  owner_id uuid,
  status text,
  created_at timestamp,
  expires_at timestamp
);

CREATE TABLE links_by_owner (
  owner_id uuid,
  created_at timestamp,
  code text,
  long_url text,
  status text,
  expires_at timestamp,
  PRIMARY KEY ((owner_id), created_at, code)
) WITH CLUSTERING ORDER BY (created_at DESC, code ASC);
```

Why two tables?

- Redirect path needs `code -> long_url`.
- Owner dashboard needs `owner_id -> recent links`.
- A single normalized table would not serve both efficiently.

Application responsibility:

- Write both tables.
- Use idempotency keys.
- Repair inconsistencies asynchronously if needed.
- Use batch only when rows share a partition or when atomicity semantics are understood. Do not use batches as a bulk-loading performance trick.

## 8. Solving High Read And High Write Workloads

### 8.1 High Write Workload

ScyllaDB handles high writes well when:

- Writes are distributed across many partitions.
- Partition keys have high cardinality.
- The workload avoids large hot partitions.
- The compaction strategy matches the workload.
- Tombstones are controlled.
- Write consistency level is chosen intentionally.
- Hardware has enough disk bandwidth, CPU, memory, and network.

Write path advantages:

- Commitlog append is sequential.
- Memtable update is in memory.
- SSTable flush is sequential.
- No global secondary index maintenance unless configured.
- No cross-table joins.
- No single primary node for the entire cluster.

Write bottlenecks usually come from:

- One hot partition.
- Too many tombstones.
- Expensive LWT use.
- Large batches.
- Slow disks.
- Compaction falling behind.
- Oversized partitions.
- Too much cross-DC replication.
- Client retry storms.

### 8.2 High Read Workload

ScyllaDB handles high reads well when:

- Reads are point lookups by partition key.
- Reads return bounded rows.
- Partitions are not too large.
- Data is cached or has good locality.
- Compaction keeps read amplification low.
- Queries avoid `ALLOW FILTERING`.
- Driver uses token-aware and shard-aware routing.

Read bottlenecks usually come from:

- Querying without partition key.
- Reading huge partitions.
- Scanning many SSTables due to poor compaction.
- Tombstone-heavy reads.
- Large result pages.
- Low cache hit ratio.
- Cross-DC reads.
- Hot key read amplification.

## 9. Hotspot Problems

A hotspot occurs when too much traffic targets the same node, shard, partition, or small set of partitions.

### 9.1 Common Hotspot Causes

| Cause | Example | Problem |
|---|---|---|
| Low-cardinality partition key | `status = ACTIVE` | Huge fraction of traffic hits one partition. |
| Time-only partition key | `day = 2026-05-27` | All today's writes hit one/few partitions. |
| Tenant-only partition key | `tenant_id` | One big tenant overloads one partition. |
| Celebrity object | `post_id` for viral post | Likes/views/comments hit one partition. |
| Counter row | One global counter | All updates serialize around one key. |
| Unbounded partition growth | One chat room forever | Reads and compaction get expensive. |

### 9.2 Detecting Hotspots

Look for:

- High p99 latency on specific queries.
- One node or shard with high CPU.
- One node with high disk/network.
- Large partition warnings.
- Uneven token/tablet load.
- Read/write timeout patterns tied to a key.
- Top partition metrics.
- Slow queries concentrated around one tenant/object.

### 9.3 Fix Pattern 1 - Add A Bucket Or Shard To The Partition Key

Bad design for viral post likes:

```cql
CREATE TABLE likes_by_post_bad (
  post_id uuid,
  user_id uuid,
  liked_at timestamp,
  PRIMARY KEY ((post_id), user_id)
);
```

If one post becomes viral, all likes hit one partition.

Better:

```cql
CREATE TABLE likes_by_post_bucketed (
  post_id uuid,
  bucket smallint,
  user_id uuid,
  liked_at timestamp,
  PRIMARY KEY ((post_id, bucket), user_id)
);
```

Bucket selection:

```text
bucket = hash(user_id) % 64
```

Write:

- Compute bucket.
- Write to `(post_id, bucket)`.

Read:

- Query 64 partitions.
- Merge results or aggregate counts.

Tradeoff:

- Writes scale better.
- Reads become fan-out.
- Use this when write hotspot risk is worse than read fan-out cost.

### 9.4 Fix Pattern 2 - Time Bucketing

Bad design for all metrics for one device:

```cql
CREATE TABLE metrics_by_device_bad (
  device_id uuid,
  ts timestamp,
  value double,
  PRIMARY KEY ((device_id), ts)
);
```

If a device writes every millisecond forever, the partition grows without bound.

Better:

```cql
CREATE TABLE metrics_by_device_hour (
  device_id uuid,
  bucket_hour timestamp,
  ts timestamp,
  metric_id text,
  value double,
  PRIMARY KEY ((device_id, bucket_hour), ts, metric_id)
) WITH CLUSTERING ORDER BY (ts DESC, metric_id ASC);
```

Now each partition is bounded by one device-hour.

### 9.5 Fix Pattern 3 - Tenant Plus Bucket

Bad for SaaS events:

```cql
PRIMARY KEY ((tenant_id), event_ts)
```

Better:

```cql
PRIMARY KEY ((tenant_id, bucket_day, shard), event_ts, event_id)
```

This handles:

- Large tenants.
- Time-bounded reads.
- Controlled partition size.
- Parallel ingestion.

### 9.6 Fix Pattern 4 - Cache Hot Reads

For hot read keys, use:

- Application cache.
- CDN/edge cache if content is public.
- Redis for ultra-hot small values.
- ScyllaDB row cache.
- Read-through cache.

Example: URL shortener redirect.

Flow:

```text
GET /abc123
  -> edge cache
  -> service local cache
  -> ScyllaDB links_by_code
  -> redirect
```

Cache reduces read pressure on ScyllaDB, but ScyllaDB remains the source of truth.

### 9.7 Fix Pattern 5 - Avoid Single Global Counters

Bad:

```cql
post_id -> total_views counter
```

Better:

```cql
CREATE TABLE view_counts_by_post_bucket (
  post_id uuid,
  bucket smallint,
  count counter,
  PRIMARY KEY ((post_id, bucket))
);
```

Or use event ingestion:

```text
write raw events -> stream processor -> aggregate table
```

Counters are useful, but they need careful modeling under high contention.

## 10. Real-World Problem Solving

### 10.1 URL Shortener

Requirements:

- Redirect by short code at very low latency.
- Create links.
- Track clicks.
- Support owner dashboard.
- Expire links.
- Handle viral links.

Tables:

```cql
CREATE TABLE links_by_code (
  code text PRIMARY KEY,
  long_url text,
  owner_id uuid,
  status text,
  created_at timestamp,
  expires_at timestamp
);

CREATE TABLE links_by_owner (
  owner_id uuid,
  created_at timestamp,
  code text,
  long_url text,
  status text,
  PRIMARY KEY ((owner_id), created_at, code)
) WITH CLUSTERING ORDER BY (created_at DESC, code ASC);

CREATE TABLE click_events_by_code_day (
  code text,
  bucket_day date,
  shard smallint,
  event_ts timestamp,
  event_id timeuuid,
  ip_hash text,
  country text,
  user_agent text,
  PRIMARY KEY ((code, bucket_day, shard), event_ts, event_id)
) WITH CLUSTERING ORDER BY (event_ts DESC, event_id DESC);
```

Why this works:

- Redirect is a single partition lookup by `code`.
- Owner dashboard is a bounded partition by `owner_id`.
- Click events are bucketed by day and shard to avoid viral-code hotspots.
- Expiration can use TTL or application status checks depending on audit needs.
- Analytics should be asynchronous, not on the redirect critical path.

Operational notes:

- Cache `links_by_code` aggressively.
- Use idempotency for create requests.
- Use async queue for click events if redirect p99 matters.
- Use rate limits and abuse detection.
- For extremely viral codes, increase `shard` count or sample click events.

### 10.2 Chat Messages

Requirements:

- Fetch latest messages in a conversation.
- Append new messages.
- Fetch user's conversation list.

Tables:

```cql
CREATE TABLE messages_by_conversation_day (
  conversation_id uuid,
  bucket_day date,
  message_ts timestamp,
  message_id timeuuid,
  sender_id uuid,
  body text,
  PRIMARY KEY ((conversation_id, bucket_day), message_ts, message_id)
) WITH CLUSTERING ORDER BY (message_ts DESC, message_id DESC);

CREATE TABLE conversations_by_user (
  user_id uuid,
  last_message_ts timestamp,
  conversation_id uuid,
  title text,
  last_message_preview text,
  PRIMARY KEY ((user_id), last_message_ts, conversation_id)
) WITH CLUSTERING ORDER BY (last_message_ts DESC, conversation_id ASC);
```

Why bucket by day?

- A very active group chat should not create one unbounded partition forever.
- Reads for recent messages usually touch today's partition and maybe yesterday's.

Problem:

- A celebrity livestream chat may still overload today's partition.

Fix:

```cql
PRIMARY KEY ((conversation_id, bucket_day, shard), message_ts, message_id)
```

Use `shard = hash(message_id) % N`.

### 10.3 IoT Metrics

Requirements:

- Millions of devices.
- High write rate.
- Query last hour/day for a device.
- Expire old data.

Table:

```cql
CREATE TABLE metrics_by_device_hour (
  device_id uuid,
  bucket_hour timestamp,
  ts timestamp,
  metric_name text,
  value double,
  PRIMARY KEY ((device_id, bucket_hour), ts, metric_name)
) WITH CLUSTERING ORDER BY (ts DESC, metric_name ASC)
  AND default_time_to_live = 2592000
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': '1'
  };
```

Why TWCS?

- Time-series data expires by time.
- Data is usually appended and rarely updated.
- Whole windows can expire efficiently when TTL aligns with windows.

Avoid:

- Multiple TTL values in the same TWCS table.
- Explicit deletes in hot time-series tables.
- Unbounded device partitions.

### 10.4 Feature Store

Requirements:

- Read latest features for a user in single-digit milliseconds.
- Write feature updates continuously.
- Keep history for debugging.

Tables:

```cql
CREATE TABLE user_features_current (
  user_id uuid PRIMARY KEY,
  features map<text, double>,
  updated_at timestamp
);

CREATE TABLE user_features_history (
  user_id uuid,
  bucket_day date,
  updated_at timestamp,
  feature_name text,
  value double,
  PRIMARY KEY ((user_id, bucket_day), updated_at, feature_name)
) WITH CLUSTERING ORDER BY (updated_at DESC, feature_name ASC);
```

Current state is optimized for serving. History is optimized for audit and debugging.

## 11. Internal Write Path

Detailed write path:

```text
client
  -> driver chooses coordinator
  -> coordinator hashes partition key
  -> coordinator finds replica nodes/shards
  -> replicas append to commitlog
  -> replicas update memtable
  -> replicas respond
  -> coordinator returns success once consistency level is satisfied
```

Important details:

- The commitlog gives durability before memtable data is flushed to SSTables.
- The memtable makes new writes immediately readable.
- The coordinator does not need every replica unless consistency level requires it.
- Failed replicas can be repaired later through hinted handoff, read repair, and repair.
- Last-write-wins conflict resolution is timestamp-based for normal writes.

Write latency depends on:

- Chosen consistency level.
- Replica health.
- Coordinator/replica network latency.
- Commitlog latency.
- Memtable pressure.
- Compaction pressure.
- Client-side timeout and retry behavior.

## 12. Internal Read Path

Detailed read path:

```text
client
  -> coordinator
  -> coordinator hashes partition key
  -> coordinator contacts replicas required by consistency level
  -> replica checks cache/memtable
  -> replica uses bloom filters to skip irrelevant SSTables
  -> replica reads index/summary/data from relevant SSTables
  -> replica merges memtable + SSTable versions
  -> coordinator reconciles replica responses
  -> coordinator returns result
```

Read latency depends on:

- Whether partition key is known.
- Number of SSTables touched.
- Bloom filter effectiveness.
- Cache hit ratio.
- Tombstones scanned.
- Result size and paging.
- Consistency level.
- Cross-DC routing.
- Compaction quality.

### Read Repair

If replicas disagree during a read, ScyllaDB can repair inconsistent data. This helps convergence for hot data, but it should not replace scheduled repair.

Flow:

```text
client reads partition K
  -> coordinator contacts replicas required by the consistency level
  -> replicas return data or digests
  -> coordinator detects mismatch
  -> coordinator returns the correct/latest result to the client
  -> stale replicas are repaired in the background or as part of the read path
```

Good for:

- Frequently read data.
- Fixing inconsistencies that are naturally discovered by application traffic.
- Reducing stale reads for hot partitions over time.

Limitations:

- Cold data is never repaired if it is never read.
- Repairing during reads can add latency.
- It does not guarantee full cluster convergence.
- Scheduled repair is still required for production clusters, especially with deletes and TTLs.

## 13. SSTables, Memtables, Commitlog, Bloom Filter

### 13.1 Commitlog

The commitlog is an append-only durability log.

Purpose:

- Protect acknowledged writes if the node crashes before memtable flush.
- Replay mutations during restart.

Production concerns:

- Commitlog disk latency affects writes.
- Commitlog space pressure can force memtable flushes.
- On HDD, separating commitlog and data disks can help.
- On SSD/NVMe, local fast disks are preferred.

### 13.2 Memtable

The memtable is an in-memory sorted structure holding recent writes.

Purpose:

- Fast writes.
- Recent data reads before disk flush.
- Buffer writes before creating SSTables.

When a memtable grows too large or commitlog pressure requires it, it is flushed to disk as an SSTable.

### 13.3 SSTable

An SSTable is immutable and sorted.

Purpose:

- Durable storage.
- Efficient sequential writes.
- Efficient range reads within a partition.
- Compatible with compaction.

SSTable components include:

- Data file.
- Index.
- Summary.
- Bloom filter.
- Compression metadata.
- Statistics/checksum metadata.

Because SSTables are immutable, updates do not overwrite old values in place. Newer values are written elsewhere and compaction later merges old and new versions.

### 13.4 Bloom Filter

Bloom filters reduce disk reads by telling ScyllaDB whether an SSTable definitely does not contain a partition.

Result meanings:

- `no`: skip the SSTable.
- `maybe`: check the SSTable metadata/index.

Bloom filters improve reads when many SSTables exist.

### 13.5 Tombstones

A tombstone is a delete marker.

Tombstones are created by:

- `DELETE`.
- TTL expiration.
- Some collection updates.
- Range deletes.

Tombstone problems:

- Reads must scan tombstones to know data is deleted.
- Too many tombstones increase read latency.
- Tombstones cannot be purged until it is safe with respect to repair and `gc_grace_seconds`.

Best practices:

- Prefer TTL for time-series retention.
- Avoid explicit deletes in high-volume time-series tables.
- Run repair on schedule.
- Keep queries bounded.
- Monitor tombstone warnings.
- Do not set `gc_grace_seconds = 0` unless you fully understand the resurrection risk and repair model.

## 14. Compaction Strategies

The user wording mentioned "network topology like time window based, tier, level based." Time-window, size-tiered, leveled, and incremental are compaction strategies, not network topologies.

Compaction solves three problems:

- Remove obsolete overwritten values.
- Remove expired/deleted data when safe.
- Reduce the number of SSTables a read must check.

The tradeoff is amplification:

- Read amplification: extra files/data read.
- Write amplification: data rewritten during compaction.
- Space amplification: extra disk needed while old and new files coexist.

### 14.1 Size-Tiered Compaction Strategy

Class:

```cql
SizeTieredCompactionStrategy
```

How it works:

- Groups similarly sized SSTables into tiers.
- When enough SSTables exist in a tier, merges them into a larger SSTable.

Example shape:

```text
Tier 1:  100 MB, 110 MB, 95 MB, 105 MB  -> compact -> 410 MB
Tier 2:  400 MB, 420 MB, 390 MB, 410 MB -> compact -> 1.6 GB
Tier 3:  1.5 GB, 1.7 GB, 1.6 GB        -> compact -> larger SSTable
```

Good for:

- Write-heavy workloads.
- Append-heavy data.
- Lower write amplification than leveled compaction.

Why it is write-friendly:

- It does not constantly rewrite data into strict levels.
- New SSTables can accumulate before compaction is triggered.
- Compaction work is less aggressive than LCS.
- Sequential flushes from memtables remain cheap.
- It usually spends less disk I/O per write than LCS.

Weaknesses:

- Can have higher read amplification.
- Obsolete data may remain longer.
- Needs temporary disk space during compaction.

Why reads can be slower:

- Many SSTables may overlap the same partition key range.
- A point read may have to check memtable plus several SSTables.
- Bloom filters skip SSTables that definitely do not contain the key, but false positives and overlapping files still create work.
- Read latency becomes less predictable when the table has many overlapping SSTables.

### 14.2 Leveled Compaction Strategy

Class:

```cql
LeveledCompactionStrategy
```

How it works:

- Organizes SSTables into levels.
- SSTables in a level generally have non-overlapping token ranges.
- Keeps reads more predictable because fewer SSTables overlap.

Example shape:

```text
L0: new SSTables, may overlap
L1: non-overlapping ranges, small total size
L2: non-overlapping ranges, larger total size
L3: non-overlapping ranges, even larger total size
```

Good for:

- Read-heavy workloads.
- Workloads with updates/overwrites where read latency matters.

Why it is read-friendly:

- SSTables within a level usually do not overlap.
- For a given partition key, ScyllaDB checks a small bounded number of files per level.
- Lower read amplification improves point reads.
- Read latency is more predictable under update-heavy workloads.
- Old overwritten values are compacted away more aggressively.

Weaknesses:

- Higher write amplification.
- More compaction I/O.
- Can be costly for write-heavy workloads.

Why writes are more expensive:

- Data may be rewritten repeatedly as it moves from L0 to L1 to L2 and beyond.
- More compaction means more disk bandwidth and CPU usage.
- Write-heavy workloads can build compaction backlog if hardware headroom is not enough.
- During sustained ingest, LCS can spend significant I/O rewriting already-written data.

Example:

```cql
ALTER TABLE user_features_current
WITH compaction = {
  'class': 'LeveledCompactionStrategy',
  'sstable_size_in_mb': '160'
};
```

### 14.3 Time-Window Compaction Strategy

Class:

```cql
TimeWindowCompactionStrategy
```

How it works:

- Groups SSTables by time windows.
- Compacts data inside each window.
- Avoids compacting old windows with new windows.
- Works well when data expires by TTL.

Good for:

- Time-series data.
- Append-only event data.
- TTL-based retention.

Weaknesses:

- Poor fit for frequent updates to old data.
- Poor fit for mixed TTL values.
- Explicit deletes can prevent efficient whole-SSTable expiration.

Example:

```cql
ALTER TABLE metrics_by_device_hour
WITH compaction = {
  'class': 'TimeWindowCompactionStrategy',
  'compaction_window_unit': 'HOURS',
  'compaction_window_size': '1'
};
```

### 14.4 Incremental Compaction Strategy

Class:

```cql
IncrementalCompactionStrategy
```

How it works:

- Similar workload philosophy to size-tiered compaction.
- Breaks very large SSTables into sorted runs/fragments.
- Reduces temporary disk space pressure versus classic size-tiered compaction.

Good for:

- General-purpose write-heavy workloads.
- Cases where STCS would need too much temporary disk.
- Default-like production choice when no workload-specific reason exists for LCS or TWCS.

### 14.5 Choosing A Compaction Strategy

| Workload | Usually Consider |
|---|---|
| Write-heavy append-only | ICS or STCS |
| Read-heavy point lookups with updates | LCS |
| Time-series with TTL | TWCS |
| Mixed workload, not sure | Start with ICS/default, test with production-like load |
| Frequent overwrites and strict read latency | LCS, but account for write amplification |

Compaction choice must be tested with:

- Real data size.
- Real write/read ratio.
- Real TTL/delete behavior.
- Real partition distribution.
- Real disk hardware.

## 15. Replication And Network Topology

Replication is configured at the keyspace level.

Production keyspace example:

```cql
CREATE KEYSPACE app
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'replication_factor': 3
};
```

Traditional multi-DC form:

```cql
CREATE KEYSPACE app
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'us-east': 3,
  'us-west': 3
};
```

Use `NetworkTopologyStrategy` for production because it is datacenter and rack aware when paired with a DC-aware snitch.

### 15.1 Replication Factor

Replication factor is the number of copies of each partition.

Common choice:

```text
RF = 3
```

With RF=3, ScyllaDB stores three replicas of each partition.

Benefits:

- Can tolerate node failure.
- Reads can be served from multiple replicas.
- Quorum consistency is possible.

Cost:

- 3x storage before compression/overhead.
- More network and disk work per write.
- Repair and streaming need more resources.

### 15.2 Tablets And Vnodes

Modern ScyllaDB uses tablets by default for data distribution in new keyspaces where supported.

Conceptually:

- A table is split into tablets.
- Each tablet has replicas based on RF.
- Tablets can move between nodes and shards for balancing.
- Tablets can split as data grows.

This improves:

- Elastic scaling.
- Load balancing.
- Data movement during topology changes.

Older or explicitly configured keyspaces may use vnode-based distribution.

### 15.3 Snitches And Racks

A snitch tells ScyllaDB about topology:

- Datacenter.
- Rack.
- Node placement.

Production deployments should use a DC-aware snitch so replicas are distributed safely across failure domains.

Goal:

- Do not place all replicas on the same rack.
- Keep local reads/writes local when possible.
- Survive node/rack failure depending on RF and topology.

## 16. Consistency Levels And CAP

ScyllaDB provides tunable consistency. The client chooses how many replicas must respond.

Common consistency levels:

| Consistency Level | Meaning |
|---|---|
| `ONE` | One replica must respond. Lowest latency, weaker consistency. |
| `LOCAL_ONE` | One replica in local DC. Good for low-latency local reads where staleness is acceptable. |
| `QUORUM` | Majority of replicas across relevant replicas. |
| `LOCAL_QUORUM` | Majority in local DC. Common production choice. |
| `EACH_QUORUM` | Quorum in each DC. Higher latency, stronger cross-DC requirement. |
| `ALL` | Every replica must respond. Stronger, but fragile and slow. |

Quorum rule:

```text
quorum = floor(RF / 2) + 1
```

For RF=3:

```text
quorum = 2
```

If writes use `LOCAL_QUORUM` and reads use `LOCAL_QUORUM` in the same DC, read and write replica sets overlap, which gives strong read-after-write behavior for successful acknowledged writes under normal conditions.

However, ScyllaDB is still a distributed, eventually consistent database:

- Timeouts can leave ambiguous write outcomes.
- Client retries must be idempotent.
- Conflicting writes use timestamp conflict resolution.
- Repairs are still needed.
- Cross-DC consistency has latency and availability tradeoffs.

### 16.1 CAP Theorem

During a network partition, a distributed database cannot simultaneously guarantee perfect consistency and perfect availability.

ScyllaDB is generally AP-oriented with tunable consistency:

- It prioritizes availability and partition tolerance by design.
- You can increase consistency by using stronger consistency levels.
- Stronger consistency can reduce availability during failures.

Example:

With RF=3 and `LOCAL_QUORUM`, if one replica is down, reads/writes can still succeed with two replicas. If two replicas are unavailable, quorum cannot be satisfied and requests fail. That failure is the system preserving the requested consistency level.

With `ONE`, the request may succeed with only one reachable replica, improving availability but increasing stale-read risk.

### 16.2 Anti-Entropy And Repair

Replicas can diverge because of:

- Node failures.
- Network partitions.
- Timeouts.
- Dropped mutations.
- Restarts.
- Disk or resource pressure.

ScyllaDB converges replicas through:

- Hinted handoff.
- Read repair.
- Scheduled repair.
- Repair-based node operations.
- Incremental repair in supported deployments.

### 16.3 Hinted Handoff

Hinted handoff is a short-outage recovery mechanism.

If a replica is temporarily unavailable during a write, another node can store a hint saying that the unavailable replica missed a mutation. When the failed replica comes back, the hint is replayed.

Flow:

```text
write arrives
  -> replica A succeeds
  -> replica B succeeds
  -> replica C is down
  -> coordinator stores hint for C
  -> client receives success if the requested consistency level is satisfied
  -> C comes back
  -> hints are replayed to C
```

Good for:

- Short node outages.
- Restart windows.
- Temporary network blips.
- Reducing the amount of data later repaired by full repair.

Limitations:

- It is not a replacement for repair.
- Hints are kept only for a configured window.
- If the node is down longer than the hint window, newer hints stop being created for that node.
- If the coordinator storing hints fails before replay, repair is still needed.
- It only helps writes that happened while hints could be recorded.

Production implication:

> Hinted handoff is a fast catch-up path for short failures. Scheduled repair is the correctness safety net.

### 16.4 Read Repair

Read repair fixes inconsistencies discovered while serving reads.

Flow:

```text
client reads key K
  -> coordinator asks replicas according to consistency level
  -> replicas return data or digest responses
  -> coordinator compares versions
  -> if replicas disagree, coordinator reconciles using timestamps/tombstones
  -> correct result is returned
  -> stale replicas are updated
```

Good for:

- Hot data that is frequently read.
- Repairing naturally discovered divergence.
- Improving convergence without scanning the whole dataset.

Limitations:

- Cold data does not get repaired if nobody reads it.
- It can increase tail latency for reads that discover mismatches.
- It cannot replace scheduled anti-entropy repair.

### 16.5 Scheduled Repair

Scheduled repair is background anti-entropy. It compares replica ranges and synchronizes differences.

Flow:

```text
for each token range:
  pick replicas responsible for the range
  compare data for that range
  identify missing/stale rows
  stream the needed mutations
  make replicas converge
```

Why it matters:

- Repairs cold data.
- Handles nodes that were down longer than the hinted handoff window.
- Prevents deleted data from reappearing after tombstone garbage collection.
- Keeps replicas healthy before topology changes.
- Reduces surprise inconsistency during failover.

Production rule:

> Run repair regularly. If deletes/TTL are common, repair must run more often than `gc_grace_seconds` unless the table is intentionally configured otherwise.

Example issue if repair is missed:

```text
T1: row X is deleted on replicas A and B
T2: replica C is down and misses the tombstone
T3: gc_grace_seconds passes and A/B purge the tombstone
T4: C comes back with old row X
T5: without proper repair, old row X can be treated as live data again
```

This is called deleted data resurrection.

### 16.6 Repair-Based Node Operations

Repair-based node operations use repair logic for topology changes instead of relying only on streaming whole data ranges.

Examples:

- `bootstrap`
- `replace`
- `rebuild`
- `removenode`
- `decommission`

Why this exists:

- Node operations need the joining/replacing/leaving node to get the correct replica data.
- Repair can compare ranges and transfer only data that is needed.
- A compacting reader can reduce transferred data by removing dead data before streaming or repair, at the cost of extra CPU.

Mental model:

```text
old replica set
  -> compare token/tablet/range ownership
  -> repair/synchronize the affected ranges
  -> new node state becomes correct
  -> cluster ownership changes safely
```

Production implications:

- Keep repair and streaming bandwidth controlled.
- Do topology operations during low-traffic windows when possible.
- Watch disk, network, CPU, and compaction backlog.
- Do not start multiple heavy node operations casually.

### 16.7 Incremental Repair

Incremental repair tries to avoid repairing the entire dataset every time. Instead, it repairs changed/unrepaired data since a previous successful repair, in deployments where this mode is supported.

Mental model:

```text
full repair:
  compare and repair the whole selected dataset

incremental repair:
  compare and repair data that changed since the last successful repair boundary
```

Benefits:

- Less network transfer.
- Less disk I/O.
- Shorter repair windows.
- Better fit for large clusters when supported and configured correctly.

Cautions:

- Confirm support and behavior for the ScyllaDB version, topology, and table mode in use.
- Monitor completion, failures, and skipped ranges.
- Keep periodic validation/full repair procedures for high-criticality data if required.
- Do not assume incremental repair eliminates the need for operational repair planning.

### 16.8 How These Mechanisms Work Together

Use this layered view:

| Mechanism | When it runs | What it fixes | What it does not fix |
|---|---|---|---|
| Hinted handoff | After a short replica outage | Missed writes while hints were recorded | Long outages, lost hints, cold historical divergence |
| Read repair | During reads | Divergence found on hot/read data | Cold data nobody reads |
| Scheduled repair | Background schedule | Full replica divergence over ranges | Bad schema or permanent overload |
| Repair-based node operations | During topology changes | Correctness for node replace/bootstrap/decommission | Routine anti-entropy by itself |
| Incremental repair | Scheduled/managed repair mode | Changed/unrepaired data since prior repair | Unsupported topologies or missed operational validation |

Production mental model:

```text
hinted handoff = quick catch-up
read repair = opportunistic healing
scheduled repair = complete anti-entropy safety net
repair-based node ops = safe topology change machinery
incremental repair = lower-cost repair when supported
```

Production rule:

> Run repair regularly. If deletes/TTL are common, repair must run more often than `gc_grace_seconds` unless the table is intentionally configured otherwise.

## 17. Production Database Aspects

### 17.1 Schema Checklist

Before creating a table, answer:

- What exact query does this table serve?
- What is the full partition key?
- What are the clustering columns?
- What is the expected rows per partition?
- What is the expected bytes per partition?
- What is the p99 partition size?
- Can a single tenant/user/object become hot?
- Does the table need a bucket/shard key?
- Is the result set bounded?
- What is the TTL/delete behavior?
- Which compaction strategy fits?
- Which consistency level will the service use?
- What is the repair requirement?

### 17.2 Partition Sizing

Avoid:

- Millions of rows in one partition.
- Very wide partitions.
- Partitions that grow forever.
- High write rate into one partition.

Prefer:

- Time buckets.
- Hash buckets.
- Tenant/object plus bucket.
- Bounded result windows.
- Derived tables per query.

A rough target is to keep partitions small and predictable. The exact limit depends on workload, hardware, row size, and query pattern, but huge partitions are a common source of latency and operational pain.

### 17.3 Capacity Planning

Estimate:

```text
write_qps_peak
read_qps_peak
average_row_size
daily_storage = writes_per_day * average_row_size
replicated_storage = daily_storage * replication_factor
retention_storage = replicated_storage * retention_days
compaction_headroom = depends on compaction strategy
```

Plan for:

- RF overhead.
- Compression ratio.
- Compaction temporary space.
- Tombstones.
- Repair traffic.
- Backups/snapshots.
- Growth and failover.
- Hot partitions, not just average QPS.

### 17.4 Hardware

Production recommendations:

- Use modern CPUs.
- Use enough cores to match desired throughput.
- Use NVMe/SSD local disks where possible.
- Keep enough RAM for cache and memtables.
- Use fast networking, commonly 10 Gbps or higher for large nodes.
- Avoid noisy neighbors.
- Keep nodes homogeneous when possible.

ScyllaDB benefits from balanced hardware. A node with many cores but weak disk or network will bottleneck.

### 17.5 Driver And Client Configuration

Use:

- Prepared statements.
- Token-aware routing.
- Shard-aware routing.
- Local datacenter policy.
- Bounded retries.
- Idempotency flags only when operations are actually idempotent.
- Connection pool sizing tested under load.
- Request timeouts aligned with service SLOs.
- Backpressure when ScyllaDB is overloaded.

Avoid:

- Unlimited client concurrency.
- Retry storms.
- Blind retry of non-idempotent writes.
- Large unpaged reads.
- `ALLOW FILTERING`.
- Per-request schema changes.

### 17.6 Consistency Policy

Common production defaults:

- Single DC: `LOCAL_QUORUM` for important reads/writes.
- Multi-DC: `LOCAL_QUORUM` for local user-facing traffic, async cross-DC convergence.
- Low-value telemetry: `LOCAL_ONE` or `ONE` may be acceptable.
- Critical uniqueness: use LWT carefully, or external allocation/design.

Choose per operation:

| Operation | Possible CL |
|---|---|
| Login/session read | `LOCAL_QUORUM` |
| Analytics event write | `LOCAL_ONE` or `LOCAL_QUORUM` depending on loss tolerance |
| URL redirect lookup | `LOCAL_QUORUM` for correctness, cache in front |
| Click event ingest | `LOCAL_ONE` plus durable queue, or `LOCAL_QUORUM` if direct write must be durable |
| Admin update | `LOCAL_QUORUM` |

### 17.7 LWT And Uniqueness

Lightweight Transactions support conditional updates such as:

```cql
INSERT INTO links_by_code (code, long_url)
VALUES (?, ?)
IF NOT EXISTS;
```

Use LWT for:

- Unique alias creation.
- Compare-and-set state changes.
- Rare coordination paths.

Avoid LWT for:

- High-volume hot paths.
- Counters.
- Every event write.

LWT is more expensive because it requires consensus-style coordination.

### 17.8 Secondary Indexes And Materialized Views

Use cautiously.

Questions before using:

- Is the indexed value high cardinality?
- Is the query selective?
- Can I create a query-specific table instead?
- What is the write amplification?
- What happens under tenant hotspots?
- Can I tolerate eventual consistency of derived views?

Often better:

- Maintain your own denormalized table.
- Use CDC/stream processor for derived views.
- Use a search engine for arbitrary search.

### 17.9 Deletes, TTL, And Retention

TTL is good for:

- Expiring metrics/events.
- Short-lived sessions.
- Cache-like data.

Be careful with:

- Mixed TTL values in TWCS tables.
- Frequent explicit deletes.
- Range deletes.
- Large collections with deletes.
- Setting `gc_grace_seconds` too low.

Retention design example:

```cql
CREATE TABLE click_events_by_code_day (
  code text,
  bucket_day date,
  shard smallint,
  event_ts timestamp,
  event_id timeuuid,
  country text,
  PRIMARY KEY ((code, bucket_day, shard), event_ts, event_id)
) WITH default_time_to_live = 7776000
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': '1'
  };
```

### 17.10 Backup And Restore

Production needs:

- Regular snapshots/backups.
- Restore drills.
- Point-in-time recovery strategy if required.
- Backup encryption.
- Backup retention policy.
- Cross-region storage for disaster recovery.
- Clear RPO/RTO.

Do not assume replication is backup. Replication protects against node failure, not accidental deletes, bad deploys, or data corruption.

### 17.11 Monitoring

Monitor:

- Read/write latency p50/p95/p99.
- Timeouts and unavailable errors.
- Per-node and per-shard CPU.
- Disk utilization.
- Disk I/O latency.
- Network throughput/errors.
- Compaction backlog.
- Pending flushes.
- Cache hit ratio.
- Tombstone warnings.
- Large partition warnings.
- Repair status.
- Node status.
- Dropped messages.
- Client retry rate.
- Query-specific latency.

Alert on:

- Disk filling.
- Sustained compaction backlog.
- Repair not running.
- p99 latency regression.
- Node down.
- High timeout rate.
- Hot partition warnings.
- Uneven load.

### 17.12 Security

Production checklist:

- Enable authentication.
- Enable authorization/RBAC.
- Use TLS client-to-node.
- Use TLS node-to-node.
- Encrypt backups.
- Consider encryption at rest.
- Rotate credentials.
- Restrict CQL and admin ports.
- Audit privileged operations.
- Use least privilege application roles.

### 17.13 Operations

Operational practices:

- Use rolling upgrades.
- Test upgrades in staging with production-like data.
- Avoid schema changes during incidents unless needed.
- Do not add/remove many nodes blindly without understanding streaming load.
- Run repairs.
- Test node replacement.
- Test restore.
- Load test before major traffic events.
- Keep capacity headroom.
- Keep compaction headroom.
- Keep clear runbooks.

## 18. Anti-Patterns

Avoid:

- Using ScyllaDB like a relational database.
- Designing one table for all queries.
- Querying without partition key.
- Using `ALLOW FILTERING` in production paths.
- Huge partitions.
- Low-cardinality partition keys.
- Single global counters.
- Monotonic hot buckets without sharding.
- Large logged batches for bulk writes.
- Blind retries without idempotency.
- Frequent deletes in high-volume tables.
- Mixed TTL values in TWCS tables.
- Secondary indexes as a default query strategy.
- Cross-DC reads in latency-sensitive paths.
- Ignoring repair.
- Treating replication as backup.

## 19. Decision Cheatsheet

| Problem | ScyllaDB Pattern |
|---|---|
| Exact lookup by id | Partition key = id |
| Latest N rows for object | Partition key = object + time bucket, clustering = time desc |
| Hot object writes | Add hash shard/bucket to partition key |
| Time-series retention | Time buckets + TTL + TWCS |
| Read-heavy current state | Point lookup table + possibly LCS |
| Write-heavy events | Append table + ICS/STCS/TWCS depending on TTL |
| Multiple query shapes | One table per query |
| Unique alias | LWT on alias table |
| Analytics over large range | Stream to OLAP store |
| Arbitrary search | Search engine |
| Strong multi-record transaction | Use another database or redesign workflow |

## 20. Interview Discussion Session

### Q1. What is ScyllaDB?

ScyllaDB is a distributed, wide-column NoSQL database compatible with Cassandra APIs. It is designed for low-latency, high-throughput workloads with horizontal scaling.

### Q2. Why is ScyllaDB fast?

Because it combines shard-per-core execution, shared-nothing cluster design, LSM writes, efficient caching, bloom filters, compaction, and query-first data modeling. It avoids global locks and avoids a single write leader.

### Q3. How does ScyllaDB solve high write throughput?

Writes are appended to commitlog, applied to memtables, acknowledged after the requested consistency level, and flushed later to SSTables. This turns random writes into memory writes and sequential disk writes. Horizontal partition distribution spreads writes across nodes and shards.

### Q4. How does ScyllaDB solve high read throughput?

Reads are efficient when the partition key is known. ScyllaDB uses cache, memtables, bloom filters, indexes, and compaction to avoid unnecessary disk work. Shard-aware drivers route requests directly to the right shard.

### Q5. What is a partition key?

The partition key is the hash-distribution key. It decides which node and shard own the data. All rows with the same partition key live in the same logical partition.

### Q6. What is a clustering key?

The clustering key sorts rows inside a partition. It supports efficient ordered reads and range scans inside that partition.

### Q7. What is a composite partition key?

A composite partition key uses multiple columns as the partition identity, for example:

```cql
PRIMARY KEY ((tenant_id, bucket_day, shard), event_ts, event_id)
```

Here `(tenant_id, bucket_day, shard)` decides data placement, while `(event_ts, event_id)` sorts rows inside the partition.

### Q8. How do you solve a hotspot?

First identify whether the hotspot is a node, shard, partition, tenant, or object. Then use one or more of:

- Better high-cardinality partition key.
- Time bucketing.
- Hash bucketing.
- Read caching.
- Write fan-out.
- Async aggregation.
- Avoiding global counters.
- Splitting large tenants or viral objects.

### Q9. What is the tradeoff of adding a bucket?

Writes spread across many partitions, but reads may need to query multiple buckets and merge results. This is usually worth it for write-heavy hotspots.

### Q10. What is an SSTable?

An SSTable is an immutable sorted file on disk. Memtables flush to SSTables. Reads may merge data from multiple SSTables, and compaction later merges SSTables to reduce read, write, and space amplification.

### Q11. What is a bloom filter?

A bloom filter is a probabilistic structure used to skip SSTables that definitely do not contain the requested partition. It can say "maybe", but if it says "no", the SSTable can be skipped.

### Q12. What is compaction?

Compaction merges SSTables, removes obsolete versions and expired data when safe, and reduces read amplification. It consumes I/O and disk headroom, so choosing the right strategy matters.

### Q13. Difference between STCS, LCS, TWCS, and ICS?

- STCS groups similarly sized SSTables; good for write-heavy workloads but can increase read amplification.
- LCS organizes SSTables into levels; good for read-heavy workloads but has higher write amplification.
- TWCS groups data by time windows; good for time-series data with TTL.
- ICS reduces temporary disk pressure compared with classic STCS while preserving similar workload behavior.

### Q14. What replication strategy should production use?

Use `NetworkTopologyStrategy` with a DC-aware snitch. It lets you control replication per datacenter/rack topology and is the production-oriented strategy.

### Q15. How does ScyllaDB fit CAP theorem?

ScyllaDB is generally AP-oriented with tunable consistency. During a partition, stronger consistency levels may reject requests to preserve consistency, while weaker levels may accept more requests with higher stale-read risk.

### Q16. What consistency level should I use?

Use `LOCAL_QUORUM` for important user-facing reads/writes in one DC. Use `LOCAL_ONE` or `ONE` only when lower latency or higher availability is more important than reading the latest data. Use `ALL` rarely because it reduces availability.

### Q17. Is ScyllaDB strongly consistent?

It is tunably consistent, not generally serializable like a relational database. Quorum reads and writes can provide strong read-after-write behavior for many single-partition flows, but applications must still handle retries, timeouts, conflicts, and repair.

### Q18. Does replication replace backup?

No. Replication protects availability during node failure. Backup protects against accidental deletes, bad deploys, corruption, and disaster recovery scenarios.

### Q19. What is the biggest ScyllaDB design mistake?

Using the wrong partition key. Most severe production issues come from hot partitions, huge partitions, or queries that do not include the partition key.

### Q20. How should I design a ScyllaDB table?

Start from the query. Pick a partition key that distributes traffic and bounds data size. Pick clustering columns that support the required order/range. Add buckets for hotspots. Choose compaction and TTL based on lifecycle. Test with production-like load.

## 21. Quick Production Review Template

Use this before approving a ScyllaDB schema:

```text
Table:
Access pattern:
Read QPS:
Write QPS:
Peak multiplier:
Partition key:
Clustering key:
Rows per partition p50/p99:
Bytes per partition p50/p99:
Hot key risk:
Bucket/shard needed:
TTL/delete behavior:
Compaction strategy:
Consistency level:
Repair schedule:
Backup/restore:
Monitoring:
Failure mode:
```

## 22. Sources

- Context7 library resolution used: `/websites/scylladb`.
- ScyllaDB schema and key examples: https://docs.scylladb.com/stable/get-started/query-data/schema/
- ScyllaDB CQL data definition and primary key examples: https://docs.scylladb.com/manual/stable/cql/ddl/
- ScyllaDB compaction overview: https://docs.scylladb.com/manual/master/kb/compaction.html
- ScyllaDB compaction strategy guide: https://docs.scylladb.com/manual/stable/architecture/compaction/compaction-strategies.html
- ScyllaDB compaction CQL reference: https://docs.scylladb.com/manual/stable/cql/compaction.html
- ScyllaDB data distribution with tablets: https://docs.scylladb.com/manual/stable/architecture/tablets.html
- ScyllaDB replication/schema basics: https://docs.scylladb.com/stable/get-started/query-data/schema.html
- ScyllaDB consistency guide: https://docs.scylladb.com/manual/stable/kb/consistency.html
- ScyllaDB fault tolerance and CAP discussion: https://docs.scylladb.com/manual/master/architecture/architecture-fault-tolerance.html
- ScyllaDB repair: https://docs.scylladb.com/manual/stable/operating-scylla/procedures/maintenance/repair.html
- ScyllaDB system requirements: https://docs.scylladb.com/manual/stable/getting-started/system-requirements.html
- ScyllaDB configuration parameters: https://docs.scylladb.com/manual/stable/reference/configuration-parameters.html
