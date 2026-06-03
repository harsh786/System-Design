# Apache HBase - Real World Use Cases & Production Guide

## Core Concepts

### Column-Family Storage Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        HBase Table                               │
├─────────────────────────────────────────────────────────────────┤
│  Row Key  │  Column Family: cf1       │  Column Family: cf2     │
│           │  col1  │  col2  │  col3   │  col1  │  col2         │
├───────────┼────────┼────────┼─────────┼────────┼───────────────┤
│  row-001  │  v1    │  v2    │  v3     │  v1    │  v2           │
│  row-002  │  v1    │        │  v3     │        │  v2           │
│  row-003  │  v1    │  v2    │         │  v1    │               │
└───────────┴────────┴────────┴─────────┴────────┴───────────────┘

Key Properties:
- Each column family stored in separate HFiles on HDFS
- Sparse: missing cells cost nothing
- Each cell has: row_key + column_family:qualifier + timestamp → value
- Cells versioned by timestamp (configurable VERSIONS per family)
```

### Region Lifecycle: MemStore → HFile → HDFS

```
┌─────────────────────────────────────────────────────────┐
│                      Region                              │
│                                                         │
│  ┌─────────────────┐    ┌─────────────────┐           │
│  │  Store (CF1)    │    │  Store (CF2)    │           │
│  │                 │    │                 │           │
│  │  ┌───────────┐  │    │  ┌───────────┐  │           │
│  │  │ MemStore  │  │    │  │ MemStore  │  │           │
│  │  │ (in-heap) │  │    │  │ (in-heap) │  │           │
│  │  └─────┬─────┘  │    │  └─────┬─────┘  │           │
│  │        │ flush   │    │        │ flush   │           │
│  │        ▼         │    │        ▼         │           │
│  │  ┌───────────┐  │    │  ┌───────────┐  │           │
│  │  │  HFile 1  │  │    │  │  HFile 1  │  │           │
│  │  │  HFile 2  │  │    │  │  HFile 2  │  │           │
│  │  │  HFile 3  │  │    │  │  HFile 3  │  │           │
│  │  └─────┬─────┘  │    │  └─────┬─────┘  │           │
│  └────────┼─────────┘    └────────┼─────────┘           │
│           │                       │                     │
└───────────┼───────────────────────┼─────────────────────┘
            ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│                    HDFS DataNodes                        │
│         (3x replication, 128MB block size)              │
└─────────────────────────────────────────────────────────┘
```

### Write Path

```
Client Write Request
        │
        ▼
┌──────────────────┐
│  RegionServer    │
│                  │
│  1. Write WAL ───────────► HDFS (Write-Ahead Log)
│     (sequential) │          - Sequential append
│                  │          - Synced to disk
│  2. Write MemStore         - Guarantees durability
│     (in-memory   │
│      sorted map) │
│                  │
│  3. Acknowledge  │
│     to client    │
└──────────────────┘
        │
        │ When MemStore reaches threshold (128MB default)
        ▼
┌──────────────────┐
│  Flush to HFile  │
│  (sorted on disk)│
│  - Immutable     │
│  - Block indexed │
│  - Bloom filter  │
└──────────────────┘

Write Throughput:
- Single RegionServer: 10,000-30,000 writes/sec
- With batching (Put list): 50,000-100,000 writes/sec
- Cluster (20 nodes): 500K-1M writes/sec
```

### Read Path

```
Client Read (Get/Scan)
        │
        ▼
┌─────────────────────────────────────────────┐
│              RegionServer                     │
│                                              │
│  ┌─────────┐   ┌──────────────┐            │
│  │MemStore │   │  BlockCache  │            │
│  │(current │   │  (LRU/Bucket)│            │
│  │ writes) │   │              │            │
│  └────┬────┘   └──────┬───────┘            │
│       │                │                    │
│       ▼                ▼                    │
│  ┌─────────────────────────────────┐       │
│  │     Merge/Priority Queue        │       │
│  │  (merge sorted results from     │       │
│  │   MemStore + BlockCache + HFiles)│       │
│  └─────────────────────┬───────────┘       │
│                        │                    │
│                        │ cache miss         │
│                        ▼                    │
│  ┌─────────────────────────────────┐       │
│  │  HFiles on HDFS                 │       │
│  │  - Check Bloom filter first     │       │
│  │  - Block index lookup           │       │
│  │  - Read data block              │       │
│  │  - Populate BlockCache          │       │
│  └─────────────────────────────────┘       │
└─────────────────────────────────────────────┘

Read Throughput:
- Random Get (cache hit): 1-3ms, 20,000-50,000 ops/sec per RS
- Random Get (cache miss): 5-20ms, 5,000-10,000 ops/sec per RS
- Sequential Scan: 50,000-200,000 rows/sec per RS
- Short Scan (10 rows): 3-10ms
```

### Row Key Design Patterns

```
┌─────────────────────────────────────────────────────────────┐
│ Problem: Sequential keys → hotspotting on single region     │
│                                                             │
│ Pattern 1: SALTING                                          │
│   Original:  2024-01-15-user123                             │
│   Salted:    bucket_hash(user123) + 2024-01-15-user123      │
│   Example:   03_2024-01-15-user123  (bucket 0-N)            │
│   Buckets:   Typically N = number of regions                │
│                                                             │
│ Pattern 2: HASHING                                          │
│   Original:  user123                                        │
│   Hashed:    md5(user123)[0:8] + user123                    │
│   Example:   a1b2c3d4_user123                               │
│   Trade-off: Loses ordering, enables uniform distribution   │
│                                                             │
│ Pattern 3: REVERSING                                        │
│   Original:  com.facebook.www                               │
│   Reversed:  www.facebook.com                               │
│   Benefit:   Groups related domains together                │
│                                                             │
│ Pattern 4: COMPOSITE KEY                                    │
│   Format:    <shard>|<entity_id>|<reverse_timestamp>        │
│   Example:   05|user123|9999999999-1705312000               │
│   Benefit:   Latest data first within entity scan           │
│                                                             │
│ Anti-patterns:                                              │
│   ✗ Monotonically increasing (timestamps, sequence IDs)     │
│   ✗ Purely random (no scan locality)                        │
│   ✗ Very short keys (poor distribution)                     │
│   ✗ Very long keys (memory/storage overhead)                │
└─────────────────────────────────────────────────────────────┘
```

### Bloom Filters

```
Per HFile Bloom Filter:
┌──────────────────────────────────────────────┐
│  HFile                                        │
│  ┌────────────────────────────────────────┐  │
│  │  Bloom Filter (ROW or ROW+COL)         │  │
│  │  - Bit array + hash functions          │  │
│  │  - Loaded into memory on region open   │  │
│  │  - False positive rate: ~1%            │  │
│  │                                        │  │
│  │  Before reading any block:             │  │
│  │  "Is row X possibly in this HFile?"    │  │
│  │    YES → read block index → read block │  │
│  │    NO  → skip entire HFile            │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  Impact: Reduces disk reads by 10-50x        │
│  for random Get operations                   │
└──────────────────────────────────────────────┘

Types:
- ROW bloom: check if row exists in HFile
- ROWCOL bloom: check if row+column exists (higher memory)
- NONE: no bloom filter (scan-heavy workloads)
```

### Versioning & TTL

```
Cell Structure:
  (RowKey, ColumnFamily:Qualifier, Timestamp) → Value

┌─────────────────────────────────────────────────┐
│ Row: user123, CF:info, Qualifier:email          │
│                                                 │
│ Timestamp 1705312000 → "new@email.com"  (latest)│
│ Timestamp 1704000000 → "old@email.com"          │
│ Timestamp 1702000000 → "first@email.com"        │
│                                                 │
│ VERSIONS=3: keeps last 3 versions               │
│ TTL=86400: cells older than 1 day auto-deleted  │
│            (cleaned during major compaction)     │
└─────────────────────────────────────────────────┘

Configuration per Column Family:
  create 'table', {NAME=>'cf', VERSIONS=>5, TTL=>604800}
```

### Filters & Coprocessors

```
Filters (server-side, reduces network transfer):
- SingleColumnValueFilter: WHERE col = value
- PrefixFilter: row key prefix scan
- PageFilter: limit rows returned
- ColumnPaginationFilter: limit columns
- FuzzyRowFilter: pattern matching on row keys
- FilterList: AND/OR composition

Coprocessors (stored procedures for HBase):
┌────────────────────────────────────────────┐
│ Observer (triggers):                       │
│   prePut, postPut, preGet, postGet         │
│   preFlush, postFlush                      │
│   Use: secondary indexing, validation      │
│                                            │
│ Endpoint (custom RPC):                     │
│   Server-side aggregation                  │
│   Use: SUM, COUNT, AVG without full scan   │
│   Runs on each RegionServer in parallel    │
└────────────────────────────────────────────┘
```

---

## Real-World Use Cases

### 1. Facebook Messages

Facebook migrated from Cassandra to HBase (2010) for their messaging platform handling billions of messages.

```
Architecture:
┌──────────┐     ┌──────────────────────────────────────────┐
│  Client  │────▶│           Load Balancer                   │
└──────────┘     └────────────────┬─────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │      Application Tier       │
                    │   (Message Service Layer)   │
                    └─────────────┬──────────────┘
                                  │
              ┌───────────────────▼───────────────────┐
              │              ZooKeeper                 │
              │  (cluster coordination, meta location) │
              └──┬────────────────────────────────┬───┘
                 │                                │
    ┌────────────▼────────┐          ┌────────────▼────────┐
    │      HMaster        │          │      HMaster        │
    │  (active)           │          │  (standby)          │
    └─────────────────────┘          └─────────────────────┘
                 │
    ┌────────────┼─────────────────────────┐
    │            │                         │
    ▼            ▼                         ▼
┌────────┐  ┌────────┐              ┌────────┐
│Region  │  │Region  │    ...       │Region  │
│Server 1│  │Server 2│              │Server N│
│        │  │        │              │        │
│Regions:│  │Regions:│              │Regions:│
│ msg_01 │  │ msg_05 │              │ msg_98 │
│ msg_02 │  │ msg_06 │              │ msg_99 │
└───┬────┘  └───┬────┘              └───┬────┘
    │            │                      │
    ▼            ▼                      ▼
┌─────────────────────────────────────────────┐
│                HDFS Cluster                   │
│  (DataNodes co-located with RegionServers)   │
│  3x replication, 128MB blocks               │
└─────────────────────────────────────────────┘
```

**Table Design:**

```
Table: messages
Row Key: <user_id_hash(2bytes)><user_id><reverse_timestamp>

Column Families:
  meta:   {from, to, subject, thread_id, read_status}
  body:   {content, content_type}
  attach: {attachment_id, mime_type, storage_ref}

Example Row:
  RowKey: a3|user456|9999999999-1705312000
  meta:from        → "user789"
  meta:to          → "user456"
  meta:subject     → "Hello"
  meta:read_status → "false"
  body:content     → "Hey, how are you?"
  body:content_type→ "text/plain"

Access Patterns:
  - Get latest N messages for user: Scan with PrefixFilter + limit
  - Get single message: Direct Get by full row key
  - Mark as read: Put on meta:read_status
  - Search: External index (not HBase)
```

**Scale:**
- 100+ billion messages stored
- 6+ billion messages/day ingested
- 1000+ RegionServers
- 70+ TB data per cluster (compressed)
- Read latency: p50 < 5ms, p99 < 50ms

---

### 2. Airbnb Online Storage (ML Feature Serving)

Airbnb uses HBase as their online feature store for real-time ML model serving.

```
Architecture:
┌─────────────────┐    ┌──────────────────────────────┐
│  ML Training    │    │  Online Serving              │
│  (Spark/Flink)  │    │  (Feature Lookup)            │
└───────┬─────────┘    └──────────────┬───────────────┘
        │                             │
        │ batch write                 │ real-time get
        ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                   ZooKeeper Quorum                    │
│               (3 or 5 nodes, ensemble)               │
└────────────────────────┬────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Region  │    │ Region  │    │ Region  │
    │Server 1 │    │Server 2 │    │Server 3 │
    │         │    │         │    │         │
    │ BucketC │    │ BucketC │    │ BucketC │
    │ (off-   │    │ (off-   │    │ (off-   │
    │  heap)  │    │  heap)  │    │  heap)  │
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
         ▼              ▼              ▼
    ┌─────────────────────────────────────────┐
    │          HDFS (feature data)            │
    └─────────────────────────────────────────┘

    ┌─────────────────────────────────────────┐
    │  HMaster (DDL, region assignment,       │
    │           load balancing)               │
    └─────────────────────────────────────────┘
```

**Table Design:**

```
Table: ml_features
Row Key: <feature_group>|<entity_type>|<entity_id>

Column Families:
  rt:     {real-time features, TTL=1h, VERSIONS=1}
  batch:  {batch-computed features, VERSIONS=3}
  meta:   {feature metadata, schema version}

Example Row:
  RowKey: pricing|listing|listing_12345
  rt:demand_score        → 0.87
  rt:last_booking_mins   → 23
  rt:search_impressions  → 450
  batch:avg_price_30d    → 125.50
  batch:occupancy_rate   → 0.72
  batch:review_sentiment → 0.91
  meta:schema_version    → "v3"

Access Patterns:
  - Model serving: MultiGet for entity features (< 5ms required)
  - Batch update: BulkLoad HFiles from Spark (daily)
  - Real-time update: Single Puts from Flink (streaming)
  - Feature backfill: Scan by feature_group prefix
```

**Scale:**
- 200+ feature groups
- 500M+ entities with features
- 50,000+ feature lookups/sec at p99 < 10ms
- 30TB feature data
- Batch updates: 100M+ rows/hour via BulkLoad
- BucketCache: 100GB+ off-heap per RegionServer

---

### 3. Pinterest Object Storage

Pinterest uses HBase to store core objects: users, boards, pins, and their relationships.

```
Architecture:
┌──────────┐     ┌──────────────────────────────────┐
│Pinterest │────▶│  API Service Layer               │
│  Apps    │     │  (Thrift/gRPC)                   │
└──────────┘     └──────────────┬───────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │  ZooKeeper  │  │  ZooKeeper  │  │  ZooKeeper  │
     │   Node 1    │  │   Node 2    │  │   Node 3    │
     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
            └────────────────┼────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
       ┌─────────┐    ┌─────────┐     ┌─────────┐
       │  RS 1   │    │  RS 2   │     │  RS N   │
       │         │    │         │     │         │
       │ users_  │    │ pins_   │     │ boards_ │
       │ 00-0F   │    │ 00-0F   │     │ 00-0F   │
       └────┬────┘    └────┬────┘     └────┬────┘
            │              │               │
            ▼              ▼               ▼
       ┌─────────────────────────────────────────┐
       │            HDFS Cluster                  │
       │   (co-located DataNodes on RS hosts)     │
       └─────────────────────────────────────────┘

       ┌──────────┐    ┌──────────┐
       │ HMaster  │    │ HMaster  │
       │ (active) │    │(standby) │
       └──────────┘    └──────────┘
```

**Table Design:**

```
Table: pins
Row Key: md5(pin_id)[0:2] + pin_id  (2-byte salt + ID)

Column Families:
  d: (data) {image_url, description, link, source_domain}
  s: (social) {repin_count, like_count, comment_count}
  m: (metadata) {created_at, board_id, user_id, category}

Table: user_pins (relationship/index table)
Row Key: <user_id>|<reverse_timestamp>|<pin_id>

Column Families:
  p: {pin_id, board_id, action_type}

Table: board_pins
Row Key: <board_id>|<position>|<pin_id>

Column Families:
  p: {pin_id, added_at}

Access Patterns:
  - Get pin by ID: Direct Get (< 3ms)
  - User's latest pins: Scan user_pins with prefix (< 10ms)
  - Board contents: Scan board_pins with prefix
  - Increment social counts: Increment on s: family
  - Write new pin: Batch Put across pins + user_pins + board_pins
```

**Scale:**
- 100+ billion pins stored
- 500M+ active users
- 1M+ writes/sec across cluster
- 2M+ reads/sec
- 200+ RegionServers
- Read latency: p50=2ms, p99=15ms

---

### 4. Spotify User Activity

Spotify stores user listening history and activity events in HBase for personalization.

```
Architecture:
┌──────────────┐     ┌─────────────────────┐
│Spotify Client│────▶│  Event Ingestion    │
│(play events) │     │  (Kafka)            │
└──────────────┘     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │  Stream Processing  │
                     │  (Flink/Storm)      │
                     └──────────┬──────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
    ┌─────────┐           ┌──────────┐          ┌──────────┐
    │   RS 1  │           │   RS 2   │          │   RS N   │
    │         │           │          │          │          │
    │activity │           │activity  │          │activity  │
    │_00-33   │           │_34-66    │          │_67-FF    │
    └────┬────┘           └────┬─────┘          └────┬─────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │    HDFS Cluster     │
                    └─────────────────────┘

    ZooKeeper Quorum (3-5 nodes)
    HMaster (active + standby)
```

**Table Design:**

```
Table: user_activity
Row Key: <salt(1byte)>|<user_id>|<reverse_timestamp>

Column Families:
  e: (event) {track_id, artist_id, album_id, context_uri}
  p: (playback) {duration_ms, percent_played, skip, shuffle}
  d: (device) {device_type, os, country, offline}

Table: user_aggregates
Row Key: <user_id>|<time_bucket>  (bucket = day/week/month)

Column Families:
  c: (counts) {total_plays, unique_tracks, unique_artists}
  t: (top) {top_artist_1..10, top_track_1..10, top_genre_1..5}

Access Patterns:
  - Recent listening history: Scan user_activity prefix (last 50)
  - Write play event: Put (append-heavy, write-optimized)
  - User taste profile: Get user_aggregates for current period
  - "On This Day": Scan with timestamp filter for past years
  - Batch analytics: MapReduce/Spark over full table

Configuration:
  - TTL on user_activity: 2 years (auto-expire old events)
  - VERSIONS=1 (events are immutable)
  - Bloom filter: ROW (heavy random access by user)
  - Compression: SNAPPY (balance speed/ratio)
```

**Scale:**
- 400M+ active users
- 1B+ play events/day ingested
- 10M+ writes/sec peak
- 50TB+ activity data (compressed)
- Read latency for recent history: p50=3ms, p99=20ms
- 500+ RegionServers across clusters

---

### 5. Adobe Analytics (Real-Time Data Collection)

Adobe uses HBase for real-time analytics data collection and serving.

```
Architecture:
┌───────────┐    ┌─────────────────────────────────────┐
│ Websites/ │───▶│  Data Collection Servers (Edge)     │
│ Apps      │    │  (100K+ hits/sec ingest)            │
└───────────┘    └──────────────┬──────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Processing Pipeline  │
                    │  (enrichment, rules)  │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
         ┌─────────┐     ┌─────────┐      ┌─────────┐
         │  RS 1   │     │  RS 2   │      │  RS N   │
         │ 64GB    │     │ 64GB    │      │ 64GB    │
         │ heap    │     │ heap    │      │ heap    │
         │         │     │         │      │         │
         │ realtime│     │ realtime│      │ realtime│
         │ _00-1F  │     │ _20-3F  │      │ _E0-FF  │
         └────┬────┘     └────┬────┘      └────┬────┘
              │               │                │
              ▼               ▼                ▼
         ┌─────────────────────────────────────────┐
         │             HDFS Cluster                 │
         │  (1000+ DataNode, PB-scale storage)     │
         └─────────────────────────────────────────┘

    ┌───────────────┐  ┌───────────────┐
    │  ZooKeeper    │  │   HMaster     │
    │  (5 nodes)    │  │  (HA pair)    │
    └───────────────┘  └───────────────┘
```

**Table Design:**

```
Table: realtime_hits
Row Key: <report_suite_id>|<salt>|<visitor_id>|<reverse_ts>

Column Families:
  h: (hit data) {page_url, referrer, event_list, product_list}
  v: (visitor) {visitor_id, visit_num, new_visitor, geo_*}
  t: (technology) {browser, os, device_type, screen_res}
  c: (custom) {evar1..evar250, prop1..prop75}

Table: realtime_aggregates
Row Key: <report_suite_id>|<metric>|<dimension_value>|<minute_bucket>

Column Families:
  m: {count, sum, min, max, instances}

Access Patterns:
  - Ingest hit: Put to realtime_hits (fire-and-forget, async WAL)
  - Real-time dashboard: Scan aggregates for last 15 minutes
  - Visitor profile: Scan realtime_hits by visitor prefix
  - Segment evaluation: Coprocessor-based server-side filtering
  - Data export: Snapshot + MapReduce for batch processing

Configuration:
  - WAL: ASYNC_WAL for hits (speed over guaranteed durability)
  - Compression: LZ4 (fastest decompression)
  - Block size: 64KB (more granular for random reads)
  - TTL on realtime tables: 48 hours
  - Long-term: moved to cold storage via snapshots
```

**Scale:**
- 200,000+ hits/sec sustained ingestion
- 500K+ hits/sec peak
- 10+ PB total data under management
- 1000+ RegionServers
- Real-time query latency: p50=5ms, p99=30ms
- 200+ report suites (multi-tenant)

---

## Replication

### Cluster-to-Cluster WAL-Based Replication

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│       Source Cluster         │     │    Destination Cluster       │
│                             │     │                             │
│  ┌───────────────────────┐  │     │  ┌───────────────────────┐  │
│  │    RegionServer       │  │     │  │    RegionServer       │  │
│  │                       │  │     │  │                       │  │
│  │  Write → WAL ─────────┼──┼─────┼──▶  ReplicationSink     │  │
│  │         │             │  │     │  │    │                  │  │
│  │         │             │  │     │  │    ▼                  │  │
│  │  ReplicationSource    │  │     │  │  Apply edits to       │  │
│  │  (reads WAL entries,  │  │     │  │  local regions        │  │
│  │   ships to peer)      │  │     │  │                       │  │
│  └───────────────────────┘  │     │  └───────────────────────┘  │
│                             │     │                             │
│  ZooKeeper tracks:         │     │                             │
│  - Replication position    │     │                             │
│  - Peer cluster config     │     │                             │
│  - WAL queue assignment    │     │                             │
└─────────────────────────────┘     └─────────────────────────────┘

Replication Flow:
1. Client writes to source cluster
2. WAL entry marked with cluster IDs (avoids loops)
3. ReplicationSource thread reads new WAL entries
4. Entries batched and shipped via RPC to destination
5. Destination RegionServer applies edits locally
6. Position updated in ZooKeeper
```

### Sync vs Async Replication

```
┌─────────────────────────────────────────────────────────────┐
│ ASYNC REPLICATION (default)                                  │
│                                                             │
│  Client → Source WAL → ACK to client                        │
│                    └──── async ship ────▶ Destination        │
│                                                             │
│  Lag: seconds to minutes                                    │
│  Throughput: High (no cross-cluster wait)                   │
│  Consistency: Eventual                                      │
│  Data loss window: up to replication lag                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ SYNC REPLICATION (HBase 2.1+)                               │
│                                                             │
│  Client → Source WAL ──┬──▶ Local WAL                       │
│                        └──▶ Remote WAL (on peer HDFS)       │
│                             │                               │
│                             ▼                               │
│                        ACK to client (after both)           │
│                                                             │
│  States: ACTIVE / DOWNGRADE_ACTIVE / STANDBY               │
│  Lag: 0 (synchronous)                                       │
│  Throughput: Lower (cross-DC latency on write path)         │
│  Consistency: Strong                                        │
│  Data loss: Zero (RPO=0)                                    │
│                                                             │
│  Failover: STANDBY cluster promoted to ACTIVE              │
│  Recovery: old ACTIVE demoted, replays remote WAL          │
└─────────────────────────────────────────────────────────────┘
```

### Serial Replication

```
┌─────────────────────────────────────────────────────────────┐
│ SERIAL REPLICATION (HBase 2.1+)                             │
│                                                             │
│ Problem: Default async replication doesn't guarantee order  │
│ across region moves/splits                                  │
│                                                             │
│ Solution: Barrier mechanism                                 │
│                                                             │
│  Region A on RS1:  WAL entries [1,2,3] → ship in order     │
│                    │                                        │
│  Region A moves to RS2:                                     │
│                    barrier: wait for [1,2,3] to replicate   │
│                    │                                        │
│  Region A on RS2:  WAL entries [4,5,6] → ship after barrier│
│                                                             │
│ Guarantees:                                                 │
│ - Edits replicated in WAL write order per region            │
│ - No out-of-order application at destination                │
│ - Handles region moves, splits, merges                      │
│                                                             │
│ Config: SERIAL flag on peer                                 │
│   add_peer '1', CLUSTER_KEY=>'...', SERIAL=>true            │
└─────────────────────────────────────────────────────────────┘
```

### RegionServer Failover + WAL Replay

```
Normal Operation:
  RS1 owns regions [A, B, C], writes WAL to HDFS

RS1 Failure Detected:
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. ZooKeeper session timeout (default 90s)                 │
│     - RS1's ephemeral znode disappears                      │
│     - HMaster notified via ZK watch                         │
│                                                             │
│  2. HMaster starts ServerCrashProcedure:                    │
│     a. Split RS1's WAL files by region                      │
│        /hbase/WALs/rs1/  →  /hbase/WALs/rs1-splitting/     │
│        Creates: region_A.recovered, region_B.recovered      │
│                                                             │
│     b. Reassign regions to surviving RegionServers          │
│        Region A → RS2                                       │
│        Region B → RS3                                       │
│        Region C → RS2                                       │
│                                                             │
│  3. New RegionServer opens region:                          │
│     a. Reads recovered WAL edits for that region            │
│     b. Replays edits into MemStore                          │
│     c. Region becomes available                             │
│                                                             │
│  Recovery Time:                                             │
│  - Detection: 30-90s (ZK session timeout)                   │
│  - WAL split: 1-30s (depends on WAL size)                   │
│  - Region open + replay: 5-60s per region                   │
│  - Total: 1-3 minutes typical                               │
│                                                             │
│  Optimization: WAL splitting can be distributed             │
│  (hbase.master.distributed.log.splitting=true)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Scalability

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HBase Cluster                                │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │ ZooKeeper 1 │  │ ZooKeeper 2 │  │ ZooKeeper 3 │               │
│  │ (leader)    │  │ (follower)  │  │ (follower)  │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         └────────────────┬┘────────────────┘                       │
│                          │                                          │
│  Responsibilities:       │   ┌──────────────────────────────────┐  │
│  - Master election       │   │         HMaster (Active)         │  │
│  - Region assignment     │   │  - DDL operations                │  │
│  - RS liveness           │   │  - Region assignment             │  │
│  - Meta table location   │   │  - Load balancing                │  │
│                          │   │  - Compaction scheduling          │  │
│                          │   └──────────────────────────────────┘  │
│                          │   ┌──────────────────────────────────┐  │
│                          │   │       HMaster (Standby)          │  │
│                          │   └──────────────────────────────────┘  │
│                          │                                          │
│  ┌───────────────────────┼───────────────────────────────────────┐ │
│  │                       │         RegionServers                  │ │
│  │  ┌─────────┐  ┌──────┴──┐  ┌─────────┐  ┌─────────┐        │ │
│  │  │  RS 1   │  │  RS 2   │  │  RS 3   │  │  RS N   │        │ │
│  │  │         │  │         │  │         │  │         │        │ │
│  │  │MemStore │  │MemStore │  │MemStore │  │MemStore │        │ │
│  │  │BlockCach│  │BlockCach│  │BlockCach│  │BlockCach│        │ │
│  │  │WAL      │  │WAL      │  │WAL      │  │WAL      │        │ │
│  │  │Regions: │  │Regions: │  │Regions: │  │Regions: │        │ │
│  │  │ [A,B,C] │  │ [D,E,F] │  │ [G,H,I] │  │ [X,Y,Z] │        │ │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │ │
│  └───────┼─────────────┼───────────┼────────────┼──────────────┘ │
│          │             │           │            │                 │
│          ▼             ▼           ▼            ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    HDFS Cluster                              │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │  │
│  │  │  DN 1  │  │  DN 2  │  │  DN 3  │  │  DN N  │           │  │
│  │  │(co-loc │  │(co-loc │  │(co-loc │  │(co-loc │           │  │
│  │  │ w/ RS) │  │ w/ RS) │  │ w/ RS) │  │ w/ RS) │           │  │
│  │  └────────┘  └────────┘  └────────┘  └────────┘           │  │
│  │                                                             │  │
│  │  NameNode (Active) + NameNode (Standby)                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Region Splitting & Balancing

```
Region Splitting (auto):
┌──────────────────────────────┐
│  Region A: [row_000, row_999]│   Size > threshold
│  Size: 10GB (threshold)      │   (hbase.hregion.max.filesize)
└──────────────┬───────────────┘
               │ split
               ▼
┌──────────────────┐  ┌───────────────────┐
│  Region A1       │  │  Region A2        │
│ [row_000,row_500]│  │ [row_500,row_999] │
│  Size: ~5GB      │  │  Size: ~5GB       │
└──────────────────┘  └───────────────────┘

Split Policies:
- ConstantSizeRegionSplitPolicy: split at fixed size (10GB default)
- IncreasingToUpperBoundRegionSplitPolicy: 
    min(R^2 * memstore_flush_size, max_filesize)
    where R = number of regions on RS for this table
- SteppingSplitPolicy (HBase 2.0+): 
    first split at 2x flush size, then max_filesize

Region Balancing:
┌───────────────────────────────────────────────────┐
│  HMaster Load Balancer (runs periodically)        │
│                                                   │
│  Before:  RS1: 50 regions  RS2: 10 regions       │
│  After:   RS1: 30 regions  RS2: 30 regions       │
│                                                   │
│  Balancer strategies:                             │
│  - SimpleLoadBalancer: even region count          │
│  - StochasticLoadBalancer (default):              │
│    considers: region count, table locality,       │
│    read/write load, memstore size                 │
│                                                   │
│  Cost functions:                                  │
│  - RegionCountSkewCostFunction                    │
│  - TableSkewCostFunction                          │
│  - LocalityCostFunction                           │
│  - ReadRequestCostFunction                        │
│  - WriteRequestCostFunction                       │
│  - MemStoreSizeCostFunction                       │
└───────────────────────────────────────────────────┘
```

### Pre-Splitting Strategies

```
# Pre-split at table creation to avoid initial hotspot

# Uniform split (hex-based row keys):
create 'table', 'cf', {NUMREGIONS => 64, SPLITALGO => 'HexStringSplit'}

# Uniform split (byte-based):
create 'table', 'cf', {NUMREGIONS => 64, SPLITALGO => 'UniformSplit'}

# Custom split points:
create 'table', 'cf', SPLITS => ['10','20','30','40','50','60','70','80','90']

# Programmatic (Java):
byte[][] splits = new byte[numRegions-1][];
for (int i = 1; i < numRegions; i++) {
    splits[i-1] = Bytes.toBytes(String.format("%02x", (256/numRegions)*i));
}
admin.createTable(tableDescriptor, splits);

Guidelines:
- Start with: numRegions = numRegionServers * 3-5
- Monitor region sizes, let auto-split handle growth
- Re-split if regions become uneven (> 3:1 ratio)
```

### Compaction

```
MINOR COMPACTION:
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ HFile 1 │ │ HFile 2 │ │ HFile 3 │ │ HFile 4 │
│ (small) │ │ (small) │ │ (small) │ │ (large) │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └─────────┘
     │            │            │         (not selected)
     └────────────┼────────────┘
                  ▼
          ┌──────────────┐
          │  New HFile   │  (merged, but keeps deletes/versions)
          └──────────────┘

- Triggered: when file count > hbase.hstore.compactionThreshold (3)
- Selects: subset of HFiles (ratio-based algorithm)
- Fast: doesn't rewrite all data
- Frequency: minutes to hours

MAJOR COMPACTION:
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ HFile 1 │ │ HFile 2 │ │ HFile 3 │ │ HFile 4 │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     └────────────┼────────────┼────────────┘
                  ▼
          ┌──────────────┐
          │  Single      │  (removes deletes, expired versions,
          │  HFile       │   expired TTL cells)
          └──────────────┘

- Triggered: every 7 days (default) or manual
- Rewrites: ALL HFiles for a store into one
- Heavy I/O: schedule during off-peak
- Required: to actually reclaim space from deletes
- Config: hbase.hregion.majorcompaction = 604800000 (ms)
  Set to 0 to disable auto, run manually via cron
```

### Block Cache & Bucket Cache

```
┌─────────────────────────────────────────────────────────────┐
│                   RegionServer Memory Layout                  │
│                                                             │
│  JVM Heap (e.g., 32GB)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  MemStore (40% = 12.8GB)                              │  │
│  │  - Writes buffered here before flush                  │  │
│  │  - hbase.regionserver.global.memstore.size=0.4        │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  LRU BlockCache (40% = 12.8GB)  OR                    │  │
│  │  On-heap portion of BucketCache index                 │  │
│  │  - hbase.regionserver.global.memstore.size +          │  │
│  │    hfile.block.cache.size <= 0.8                       │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  Other (20%): RPC handlers, leases, misc              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Off-Heap BucketCache (e.g., 64-128GB)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Direct memory or file-backed                         │  │
│  │  - No GC pressure                                     │  │
│  │  - Much larger cache possible                         │  │
│  │  - hbase.bucketcache.size=65536 (MB)                  │  │
│  │  - hbase.bucketcache.ioengine=offheap                 │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Cache Priority Levels:                                      │
│  - SINGLE: first access (25% of cache)                      │
│  - MULTI: multiple accesses (50% of cache)                  │
│  - MEMORY: in-memory CF / meta blocks (25% of cache)        │
└─────────────────────────────────────────────────────────────┘
```

### MOB (Medium Object) Storage

```
Problem: Values 100KB-10MB cause write amplification during compaction

Without MOB:
  Write 1MB value → stored in HFile → rewritten on every compaction
  10 compactions = 10MB I/O for 1MB of data

With MOB (HBase 2.0+):
┌─────────────────────────────────────────────────────────┐
│  Regular HFile:                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │  Row Key → MOB reference (pointer to MOB file)│       │
│  │  (small, compacts normally)                   │       │
│  └──────────────────────────────────────────────┘       │
│                                                         │
│  MOB Files (separate path on HDFS):                     │
│  ┌──────────────────────────────────────────────┐       │
│  │  /hbase/mobdir/table/region/cf/mob_file       │       │
│  │  - Actual large values stored here            │       │
│  │  - Compacted separately, less frequently      │       │
│  │  - MOB compaction: merge small MOB files      │       │
│  └──────────────────────────────────────────────┘       │
│                                                         │
│  Config per Column Family:                              │
│    IS_MOB => true, MOB_THRESHOLD => 102400 (100KB)      │
│                                                         │
│  Benefit: 5-10x reduction in write amplification        │
└─────────────────────────────────────────────────────────┘
```

### Coprocessors for Scalability

```
Endpoint Coprocessor (distributed aggregation):
┌──────────┐
│  Client  │
└─────┬────┘
      │ coprocessorService() call
      │
      ├──────────────▶ RS1: compute partial SUM for regions [A,B]
      ├──────────────▶ RS2: compute partial SUM for regions [C,D]
      ├──────────────▶ RS3: compute partial SUM for regions [E,F]
      │
      │ collect results
      ▼
┌──────────────────┐
│ Client merges:   │
│ total = p1+p2+p3 │
└──────────────────┘

Without coprocessor: full table scan → transfer all data to client
With coprocessor: server-side compute → transfer only aggregates

Use cases:
- COUNT/SUM/AVG without full scan
- Secondary index maintenance (Observer)
- Custom access control
- Server-side filtering beyond standard filters
```

---

## Production Setup

### HDFS Configuration

```xml
<!-- hdfs-site.xml for HBase workloads -->

<!-- Short-circuit reads (critical for HBase performance) -->
<property>
  <name>dfs.client.read.shortcircuit</name>
  <value>true</value>
</property>
<property>
  <name>dfs.domain.socket.path</name>
  <value>/var/run/hdfs-sockets/dn</value>
</property>

<!-- DataNode settings -->
<property>
  <name>dfs.datanode.max.transfer.threads</name>
  <value>4096</value>  <!-- default 4096, increase for heavy load -->
</property>
<property>
  <name>dfs.datanode.handler.count</name>
  <value>10</value>
</property>

<!-- Replication for WAL vs data -->
<!-- WAL: dfs.replication = 3 (default, critical for durability) -->
<!-- Data: table-level, typically 3 -->

<!-- Block size -->
<property>
  <name>dfs.blocksize</name>
  <value>134217728</value>  <!-- 128MB -->
</property>

<!-- NameNode handlers (high for HBase file operations) -->
<property>
  <name>dfs.namenode.handler.count</name>
  <value>200</value>
</property>
```

### RegionServer Heap & GC

```bash
# hbase-env.sh

# Heap sizing (typically 16-32GB, avoid > 32GB for CMS)
export HBASE_HEAPSIZE=31g

# G1GC (recommended for HBase 2.x, heaps > 16GB)
export HBASE_OPTS="-XX:+UseG1GC \
  -XX:MaxGCPauseMillis=50 \
  -XX:+ParallelRefProcEnabled \
  -XX:G1HeapRegionSize=16m \
  -XX:InitiatingHeapOccupancyPercent=65 \
  -XX:-ResizePLAB \
  -XX:MaxDirectMemorySize=128g"
  # MaxDirectMemorySize for off-heap BucketCache

# For smaller heaps (< 16GB), CMS still viable:
# -XX:+UseConcMarkSweepGC
# -XX:+UseParNewGC
# -XX:CMSInitiatingOccupancyFraction=70
# -XX:+UseCMSInitiatingOccupancyOnly

# GC logging
export HBASE_OPTS="$HBASE_OPTS \
  -Xlog:gc*:file=/var/log/hbase/gc.log:time,uptime,level,tags:filecount=10,filesize=50m"
```

### MemStore & Block Cache Sizing

```xml
<!-- hbase-site.xml -->

<!-- MemStore: total across all regions on this RS -->
<property>
  <name>hbase.regionserver.global.memstore.size</name>
  <value>0.4</value>  <!-- 40% of heap -->
</property>
<property>
  <name>hbase.regionserver.global.memstore.size.lower.limit</name>
  <value>0.95</value>  <!-- flush starts at 95% of upper limit -->
</property>

<!-- Block Cache (LRU on-heap) -->
<property>
  <name>hfile.block.cache.size</name>
  <value>0.4</value>  <!-- 40% of heap -->
</property>

<!-- BucketCache (off-heap, recommended for production) -->
<property>
  <name>hbase.bucketcache.ioengine</name>
  <value>offheap</value>  <!-- or file:/path/to/cache -->
</property>
<property>
  <name>hbase.bucketcache.size</name>
  <value>65536</value>  <!-- 64GB in MB -->
</property>
<property>
  <name>hbase.bucketcache.combinedcache.enabled</name>
  <value>true</value>
</property>

<!-- Rule of thumb:
     Read-heavy: increase block cache, decrease memstore
     Write-heavy: increase memstore, decrease block cache
     Balanced: 0.4 / 0.4 split -->
```

### Compaction Tuning

```xml
<!-- hbase-site.xml -->

<!-- Minor compaction triggers -->
<property>
  <name>hbase.hstore.compactionThreshold</name>
  <value>3</value>  <!-- min files to trigger -->
</property>
<property>
  <name>hbase.hstore.compaction.max</name>
  <value>10</value>  <!-- max files per minor compaction -->
</property>
<property>
  <name>hbase.hstore.compaction.ratio</name>
  <value>1.2</value>  <!-- file selection ratio -->
</property>

<!-- Major compaction -->
<property>
  <name>hbase.hregion.majorcompaction</name>
  <value>0</value>  <!-- DISABLE auto major compaction in prod -->
</property>
<!-- Run major compaction via cron during off-peak:
     hbase shell: major_compact 'table_name' -->

<!-- Compaction throttle -->
<property>
  <name>hbase.regionserver.throughput.controller</name>
  <value>org.apache.hadoop.hbase.regionserver.compactions.PressureAwareCompactionThroughputController</value>
</property>
<property>
  <name>hbase.hstore.compaction.throughput.lower.bound</name>
  <value>52428800</value>  <!-- 50MB/s floor -->
</property>
<property>
  <name>hbase.hstore.compaction.throughput.higher.bound</name>
  <value>104857600</value>  <!-- 100MB/s ceiling -->
</property>

<!-- Flush settings -->
<property>
  <name>hbase.hregion.memstore.flush.size</name>
  <value>134217728</value>  <!-- 128MB per region -->
</property>
<property>
  <name>hbase.hregion.memstore.block.multiplier</name>
  <value>4</value>  <!-- block writes at 4x flush size -->
</property>
```

### ZooKeeper Configuration

```properties
# zoo.cfg

tickTime=2000
initLimit=10
syncLimit=5
dataDir=/data/zookeeper
clientPort=2181

# Dedicated ZK nodes (don't co-locate with RS in production)
server.1=zk1.example.com:2888:3888
server.2=zk2.example.com:2888:3888
server.3=zk3.example.com:2888:3888

# Performance tuning
maxClientCnxns=300
autopurge.snapRetainCount=5
autopurge.purgeInterval=24
```

```xml
<!-- hbase-site.xml ZooKeeper settings -->
<property>
  <name>hbase.zookeeper.quorum</name>
  <value>zk1.example.com,zk2.example.com,zk3.example.com</value>
</property>
<property>
  <name>zookeeper.session.timeout</name>
  <value>90000</value>  <!-- 90s: balance detection speed vs false positives -->
</property>
<property>
  <name>hbase.zookeeper.property.maxClientCnxns</name>
  <value>300</value>
</property>
```

### Monitoring

```
Web UI:
  HMaster:       http://master:16010  (cluster status, tables, regions)
  RegionServer:  http://rs:16030     (per-RS metrics, regions, compactions)

JMX Metrics (key ones to monitor):
┌────────────────────────────────────────────────────────────┐
│ Metric                              │ Alert Threshold      │
├─────────────────────────────────────┼──────────────────────┤
│ regionserver.Server.readRequestCount│ baseline + 50%       │
│ regionserver.Server.writeRequestCount│ baseline + 50%      │
│ regionserver.Server.totalRequestCount│ > 50K/s per RS      │
│ regionserver.Server.blockCacheHitPercent│ < 85%            │
│ regionserver.Server.memStoreSize    │ > 90% of limit       │
│ regionserver.Server.compactionQueueLength│ > 20            │
│ regionserver.Server.flushQueueLength│ > 5                  │
│ regionserver.Server.regionCount     │ > 200 per RS         │
│ regionserver.WAL.slowAppendCount    │ > 0                  │
│ regionserver.Server.percentFilesLocal│ < 80%              │
│ GC pause time                       │ > 500ms              │
└────────────────────────────────────────────────────────────┘

Prometheus Integration:
  # Use hbase-metrics2-prometheus reporter
  # hbase-site.xml:
  <property>
    <name>hbase.metrics2.sink.prometheus.class</name>
    <value>org.apache.hadoop.metrics2.sink.PrometheusMetricsSink</value>
  </property>

  # Or use JMX exporter:
  -javaagent:/opt/jmx_exporter/jmx_prometheus_javaagent.jar=9100:/opt/jmx_exporter/hbase.yml

Grafana Dashboards:
  - Request rates (read/write/total)
  - Latency percentiles (p50, p95, p99)
  - Cache hit rates
  - Compaction queue depth
  - MemStore usage
  - Region count distribution
  - GC pause frequency and duration
  - HDFS locality percentage
```

### Backup & Recovery

```bash
# SNAPSHOTS (fastest, recommended)

# Create snapshot (instant, no data copy)
hbase shell> snapshot 'my_table', 'my_table_snapshot_20240115'

# List snapshots
hbase shell> list_snapshots

# Restore snapshot (table must be disabled)
hbase shell> disable 'my_table'
hbase shell> restore_snapshot 'my_table_snapshot_20240115'
hbase shell> enable 'my_table'

# Clone snapshot to new table (no data copy, CoW)
hbase shell> clone_snapshot 'my_table_snapshot_20240115', 'my_table_clone'

# Export snapshot to another cluster/S3
hbase org.apache.hadoop.hbase.snapshot.ExportSnapshot \
  -snapshot my_table_snapshot_20240115 \
  -copy-to hdfs://backup-cluster/hbase \
  -mappers 16 \
  -bandwidth 200  # MB/s per mapper

# Export to S3
hbase org.apache.hadoop.hbase.snapshot.ExportSnapshot \
  -snapshot my_table_snapshot_20240115 \
  -copy-to s3a://my-bucket/hbase-backup/ \
  -mappers 16

# EXPORT/IMPORT (for cross-version migration)
hbase org.apache.hadoop.hbase.mapreduce.Export \
  'my_table' /backup/my_table_export

hbase org.apache.hadoop.hbase.mapreduce.Import \
  'my_table' /backup/my_table_export

# BACKUP (HBase 2.0+ built-in backup/restore)
hbase backup create full hdfs://backup/hbase-backups my_table
hbase backup create incremental hdfs://backup/hbase-backups my_table

# Strategy:
# - Daily: incremental snapshots
# - Weekly: full snapshot export to remote cluster/S3
# - Monthly: validate restore from backup
# - Retention: keep 7 daily, 4 weekly, 3 monthly
```

---

## Throughput Summary by Access Pattern

```
┌──────────────────────────────────────────────────────────────────────┐
│ Access Pattern          │ Throughput/RS    │ Latency      │ Notes    │
├─────────────────────────┼─────────────────┼──────────────┼──────────┤
│ Random Get (cache hit)  │ 20-50K ops/s    │ 1-3ms        │ Best case│
│ Random Get (cache miss) │ 5-10K ops/s     │ 5-20ms       │ Disk I/O │
│ Batch Get (100 rows)    │ 2-5K batches/s  │ 10-30ms      │ Parallel │
│ Sequential Scan         │ 50-200K rows/s  │ varies       │ No seeks │
│ Short Scan (10-100 rows)│ 5-20K scans/s   │ 3-15ms       │ Common   │
│ Single Put              │ 10-30K ops/s    │ 1-5ms        │ WAL sync │
│ Batch Put (100 rows)    │ 50-100K rows/s  │ 10-50ms      │ Amortized│
│ Put (ASYNC_WAL)         │ 30-80K ops/s    │ <1ms         │ Risk loss│
│ Increment               │ 5-15K ops/s     │ 5-10ms       │ Read+Writ│
│ BulkLoad                │ 500K-1M rows/s  │ N/A (batch)  │ Bypass RS│
│ Full Table Scan         │ 100-500K rows/s │ minutes-hours│ MapReduce│
├─────────────────────────┼─────────────────┼──────────────┼──────────┤
│ Cluster (20 RS)         │                 │              │          │
│ - Reads                 │ 200K-1M ops/s   │ similar      │ Linear   │
│ - Writes                │ 400K-2M ops/s   │ similar      │ scale    │
│ - BulkLoad              │ 10-20M rows/s   │ N/A          │          │
└──────────────────────────────────────────────────────────────────────┘

Factors affecting throughput:
- Row/value size (smaller = higher ops/s)
- Cache hit ratio (target > 90% for read-heavy)
- Disk type (SSD vs HDD: 3-5x improvement for random reads)
- Network bandwidth (10Gbps minimum for production)
- Number of column families (1-3 recommended)
- Compaction pressure (back-pressure reduces write throughput)
- Region count per RS (optimal: 20-200 regions)
```
