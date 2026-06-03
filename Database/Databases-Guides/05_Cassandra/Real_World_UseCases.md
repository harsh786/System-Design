# Apache Cassandra - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: Netflix Viewing History](#use-case-1-netflix-viewing-history)
2. [Use Case 2: Discord Message Storage](#use-case-2-discord-message-storage)
3. [Use Case 3: Apple iCloud](#use-case-3-apple-icloud)
4. [Use Case 4: Instagram Direct Messages](#use-case-4-instagram-direct-messages)
5. [Use Case 5: Uber Driver Location](#use-case-5-uber-driver-location)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: Netflix Viewing History

### Why Cassandra?
- Write-heavy workload (every play/pause/stop event)
- Time-series pattern (viewing history is append-only)
- Multi-region (serve globally with low latency)
- No single point of failure (always available for writes)
- Linear scalability (add nodes as subscribers grow)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│          Netflix Viewing History Architecture                        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  Netflix │───▶│  Zuul Gateway│───▶│ Viewing Svc  │───▶│  Cassandra  │
│  Client  │    │              │    │ (microservice)│   │  Cluster    │
│  (TV/    │    └──────────────┘    └──────────────┘    │             │
│  Phone)  │                               │            │  US-East    │
└──────────┘                               │            │  US-West    │
                                           │            │  EU-West    │
                                           ▼            └─────────────┘
                                    ┌──────────────┐
                                    │   Kafka      │  (async for analytics)
                                    │  (event bus) │
                                    └──────────────┘

Multi-DC Topology:
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     US-EAST-1       │    │     US-WEST-2       │    │     EU-WEST-1       │
│                     │    │                     │    │                     │
│  ┌───┐ ┌───┐ ┌───┐ │    │  ┌───┐ ┌───┐ ┌───┐ │    │  ┌───┐ ┌───┐ ┌───┐ │
│  │ N1│ │ N2│ │ N3│ │◀──▶│  │ N4│ │ N5│ │ N6│ │◀──▶│  │ N7│ │ N8│ │ N9│ │
│  └───┘ └───┘ └───┘ │    │  └───┘ └───┘ └───┘ │    │  └───┘ └───┘ └───┘ │
│  ┌───┐ ┌───┐ ┌───┐ │    │  ┌───┐ ┌───┐ ┌───┐ │    │  ┌───┐ ┌───┐ ┌───┐ │
│  │N10│ │N11│ │N12│ │    │  │N13│ │N14│ │N15│ │    │  │N16│ │N17│ │N18│ │
│  └───┘ └───┘ └───┘ │    │  └───┘ └───┘ └───┘ │    │  └───┘ └───┘ └───┘ │
│                     │    │                     │    │                     │
│  RF=3               │    │  RF=3               │    │  RF=3               │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘

Write: LOCAL_QUORUM (2/3 in local DC)
Read:  LOCAL_ONE (fast, eventually consistent for viewing history)
```

### Data Model

```sql
-- Viewing history (partition per user, clustered by time DESC)
CREATE TABLE viewing_history (
    user_id       UUID,
    viewed_at     TIMESTAMP,
    video_id      UUID,
    title         TEXT,
    duration_sec  INT,
    progress_pct  FLOAT,
    device_type   TEXT,
    PRIMARY KEY (user_id, viewed_at)
) WITH CLUSTERING ORDER BY (viewed_at DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7}
  AND default_time_to_live = 31536000  -- 1 year TTL
  AND gc_grace_seconds = 864000;       -- 10 days

-- Currently watching (for "Continue Watching" row)
CREATE TABLE currently_watching (
    user_id       UUID,
    video_id      UUID,
    progress_pct  FLOAT,
    last_watched  TIMESTAMP,
    PRIMARY KEY (user_id, last_watched)
) WITH CLUSTERING ORDER BY (last_watched DESC);

-- Viewing history by video (for analytics: "who watched this?")
CREATE TABLE views_by_video (
    video_id      UUID,
    view_date     DATE,
    user_id       UUID,
    watched_pct   FLOAT,
    PRIMARY KEY ((video_id, view_date), user_id)
) WITH default_time_to_live = 7776000;  -- 90 days
```

### Query Patterns

```sql
-- Get user's recent viewing history (fast: single partition scan)
SELECT * FROM viewing_history 
WHERE user_id = ? 
LIMIT 50;

-- Get "Continue Watching" list
SELECT * FROM currently_watching
WHERE user_id = ?
AND progress_pct > 0.05 AND progress_pct < 0.95
LIMIT 20;

-- Record a viewing event (fast: single partition write)
INSERT INTO viewing_history (user_id, viewed_at, video_id, title, duration_sec, progress_pct, device_type)
VALUES (?, ?, ?, ?, ?, ?, ?);
```

### Scale Numbers
- **200M+ subscribers** globally
- **~2M writes/sec** across cluster (viewing events)
- **Cluster size**: 500+ nodes across 3 regions
- **Data volume**: Petabytes total
- **Partition size target**: < 100MB per user (years of history)

---

## Use Case 2: Discord Message Storage

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│          Discord Message Storage (Before ScyllaDB Migration)        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  Discord │───▶│  Gateway     │───▶│  Message Svc │───▶│  Cassandra  │
│  Client  │    │  (WebSocket) │    │  (Elixir)    │    │  (177 nodes)│
└──────────┘    └──────────────┘    └──────────────┘    └─────────────┘
      ▲                                    │
      │                                    ▼
      │                             ┌──────────────┐
      └─────────────────────────────│  Pub/Sub     │
             (real-time delivery)   │  (messages)  │
                                    └──────────────┘

Problem at Scale:
┌─────────────────────────────────────────────────────────────────────┐
│  Partition: (channel_id, bucket)                                     │
│  Bucket = timestamp / 10 days                                       │
│                                                                      │
│  Busy channels (e.g., 1M member server):                            │
│  - Partition grows to 100s of MBs                                   │
│  - Compaction creates massive temp disk usage                       │
│  - GC pauses from large heap (JVM-based)                            │
│  - Read latency spikes during compaction                            │
│  - Tombstone buildup from message deletes                           │
│                                                                      │
│  Solution: Migrated to ScyllaDB (C++, no GC, better performance)   │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Model

```sql
-- Messages partitioned by channel + time bucket
CREATE TABLE messages (
    channel_id  BIGINT,
    bucket      INT,           -- epoch_days / 10 (10-day buckets)
    message_id  BIGINT,        -- Snowflake ID (contains timestamp)
    author_id   BIGINT,
    content     TEXT,
    attachments FROZEN<LIST<FROZEN<attachment>>>,
    embeds      FROZEN<LIST<FROZEN<embed>>>,
    reactions   MAP<TEXT, FROZEN<SET<BIGINT>>>,
    edited_at   TIMESTAMP,
    deleted     BOOLEAN,
    PRIMARY KEY ((channel_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND compaction = {'class': 'LeveledCompactionStrategy'};

-- Message search index (for pin/search features)
CREATE TABLE messages_by_author (
    channel_id  BIGINT,
    author_id   BIGINT,
    bucket      INT,
    message_id  BIGINT,
    PRIMARY KEY ((channel_id, author_id), bucket, message_id)
) WITH CLUSTERING ORDER BY (bucket DESC, message_id DESC);
```

### Lessons Learned (Why They Left)
1. **JVM GC pauses**: 10-second STW pauses under heavy compaction
2. **Tombstone accumulation**: Message deletes created tombstones faster than GC grace
3. **Compaction I/O storms**: LCS required 10x temporary disk space
4. **Latency variance**: P99 latency could spike 100x during maintenance
5. **Operational complexity**: JVM tuning was a constant battle

---

## Use Case 3: Apple iCloud

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│       Apple iCloud - World's Largest Cassandra Deployment           │
└─────────────────────────────────────────────────────────────────────┘

Scale:
┌─────────────────────────────────────────────────────────────────┐
│  - 75,000+ Cassandra nodes (reported)                            │
│  - 10+ petabytes of data                                         │
│  - Hundreds of clusters for different services                   │
│  - Multi-datacenter across Apple's global infrastructure        │
│                                                                  │
│  Services using Cassandra:                                       │
│  - iCloud Key-Value Store                                        │
│  - CloudKit (developer backend)                                  │
│  - iMessage delivery metadata                                    │
│  - Maps data                                                     │
│  - Siri suggestions                                             │
└─────────────────────────────────────────────────────────────────┘

Architecture Pattern (per service cluster):
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌──────────┐         ┌──────────────────────────────────┐      │
│  │  iCloud  │────────▶│    CloudKit API Layer            │      │
│  │  Device  │         │    (authentication, routing)     │      │
│  └──────────┘         └─────────────┬────────────────────┘      │
│                                     │                            │
│                        ┌────────────┼────────────┐              │
│                        │            │            │              │
│                        ▼            ▼            ▼              │
│                 ┌───────────┐ ┌───────────┐ ┌───────────┐      │
│                 │ Cassandra │ │ Cassandra │ │ Cassandra │      │
│                 │ Cluster A │ │ Cluster B │ │ Cluster C │      │
│                 │ (user     │ │ (device   │ │ (zone     │      │
│                 │  records) │ │  tokens)  │ │  records) │      │
│                 └───────────┘ └───────────┘ └───────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Use Case 4: Instagram Direct Messages

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│            Instagram DM - Cassandra Message Storage                  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  Mobile  │◀══▶│  Real-time   │───▶│   DM Service │───▶│  Cassandra  │
│  Client  │    │  Gateway     │    │              │    │             │
└──────────┘    │  (MQTT)      │    └──────────────┘    └─────────────┘
                └──────────────┘           │
                                           ▼
                                    ┌──────────────┐
                                    │  Notification│
                                    │  Service     │
                                    └──────────────┘

Data Model:
┌──────────────────────────────────────────────────────────────────┐
│  Inbox (conversations per user):                                  │
│  Partition Key: user_id                                           │
│  Clustering: last_message_time DESC                              │
│                                                                  │
│  Messages (per conversation):                                    │
│  Partition Key: (thread_id, bucket)                              │
│  Clustering: message_id DESC                                     │
│                                                                  │
│  Read receipts:                                                  │
│  Partition Key: thread_id                                        │
│  Clustering: user_id                                             │
└──────────────────────────────────────────────────────────────────┘
```

### Data Model

```sql
-- User's inbox (list of conversations)
CREATE TABLE inbox (
    user_id           BIGINT,
    thread_id         BIGINT,
    last_message_time TIMESTAMP,
    last_message_text TEXT,
    other_user_id     BIGINT,
    unread_count      INT,
    muted             BOOLEAN,
    PRIMARY KEY (user_id, last_message_time, thread_id)
) WITH CLUSTERING ORDER BY (last_message_time DESC, thread_id DESC);

-- Messages in a thread
CREATE TABLE thread_messages (
    thread_id   BIGINT,
    bucket      INT,            -- monthly bucket
    message_id  BIGINT,         -- Snowflake-like ID
    sender_id   BIGINT,
    content     TEXT,
    media_url   TEXT,
    msg_type    TEXT,           -- 'text', 'image', 'reel_share', 'story_reply'
    reactions   MAP<BIGINT, TEXT>,
    seen_by     SET<BIGINT>,
    created_at  TIMESTAMP,
    PRIMARY KEY ((thread_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};
```

---

## Use Case 5: Uber Driver Location

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│          Uber - Real-time Driver Location Tracking                  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐   GPS every   ┌──────────────┐    ┌──────────────────────┐
│  Driver  │───4 seconds──▶│   Location   │───▶│   Cassandra          │
│  App     │               │   Service    │    │   (location store)   │
└──────────┘               └──────────────┘    └──────────────────────┘
                                  │                      │
                                  ▼                      │
                           ┌──────────────┐             │
                           │ Geospatial   │◀────────────┘
                           │ Index (in-   │   (read latest locations)
                           │ memory/Redis)│
                           └──────────────┘
                                  │
                                  ▼
                           ┌──────────────┐
                           │  Matching    │  (find nearby drivers)
                           │  Service     │
                           └──────────────┘

Data Model:
┌──────────────────────────────────────────────────────────────────┐
│  Write: ~1M location updates/sec (all active drivers)            │
│  Read: ~500K reads/sec (rider requesting rides, ETA calc)        │
│                                                                  │
│  Partition: (city_id, date)                                      │
│  Clustering: (driver_id, timestamp)                              │
│                                                                  │
│  Consistency: ONE for writes (speed > accuracy for GPS)          │
│  Consistency: ONE for reads (latest location, okay if stale)    │
└──────────────────────────────────────────────────────────────────┘
```

### Data Model

```sql
-- Driver location history (high-write throughput)
CREATE TABLE driver_locations (
    city_id       INT,
    date          DATE,
    driver_id     UUID,
    timestamp     TIMESTAMP,
    latitude      DOUBLE,
    longitude     DOUBLE,
    heading       FLOAT,
    speed_mph     FLOAT,
    accuracy_m    FLOAT,
    trip_id       UUID,
    status        TEXT,         -- 'available', 'on_trip', 'offline'
    PRIMARY KEY ((city_id, date), driver_id, timestamp)
) WITH CLUSTERING ORDER BY (driver_id ASC, timestamp DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'HOURS',
                    'compaction_window_size': 1}
  AND default_time_to_live = 86400;  -- 24 hour TTL

-- Latest driver location (for real-time matching)
CREATE TABLE driver_latest_location (
    city_id       INT,
    driver_id     UUID,
    latitude      DOUBLE,
    longitude     DOUBLE,
    status        TEXT,
    updated_at    TIMESTAMP,
    PRIMARY KEY (city_id, driver_id)
);
```

---

## Replication Deep Dive

### Ring Topology & Consistent Hashing

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cassandra Ring & Data Distribution                      │
└─────────────────────────────────────────────────────────────────────┘

Token Ring (with vnodes):
                        0
                        │
              ┌─────────┼─────────┐
         Token Range    │    Token Range
         ┌──────┐      │      ┌──────┐
    ─────│Node A│──────┼──────│Node B│─────
         │(-2^63│      │      │(0 to │
         │to 0) │      │      │2^62) │
         └──────┘      │      └──────┘
              │        │        │
              │   ┌────┴────┐   │
              │   │         │   │
              └───│ Node C  │───┘
                  │(2^62 to │
                  │ 2^63)   │
                  └─────────┘

With Vnodes (256 tokens per node):
┌─────────────────────────────────────────────────────────────────┐
│  Node A: tokens [5, 47, 102, 189, 234, 567, 890, ...]         │
│  Node B: tokens [12, 56, 145, 201, 345, 612, 901, ...]        │
│  Node C: tokens [23, 78, 156, 278, 456, 678, 945, ...]        │
│                                                                  │
│  Benefits of vnodes:                                             │
│  - Even data distribution (more token ranges = smoother)        │
│  - Faster rebalancing when adding/removing nodes                │
│  - Better streaming (many sources instead of one neighbor)      │
└─────────────────────────────────────────────────────────────────┘

Partition Key → Token Mapping:
  partition_key → Murmur3Hash → token (-2^63 to 2^63-1) → responsible node
```

### Consistency Levels

```
┌─────────────────────────────────────────────────────────────────────┐
│              Consistency Level Flow (RF=3)                           │
└─────────────────────────────────────────────────────────────────────┘

Write with QUORUM (need 2/3 ACKs):
┌────────┐    ┌──────────────┐         ┌─────────┐
│ Client │───▶│ Coordinator  │────────▶│ Node 1  │ ✓ ACK
└────────┘    │ (any node)   │────────▶│ Node 2  │ ✓ ACK  → SUCCESS
              │              │────────▶│ Node 3  │ (still writing, async)
              └──────────────┘         └─────────┘

Read with QUORUM (need 2/3 responses):
┌────────┐    ┌──────────────┐         ┌─────────┐
│ Client │◀──│ Coordinator  │◀────────│ Node 1  │ data v2
└────────┘    │ (compares    │◀────────│ Node 2  │ data v2  → return v2
              │  timestamps) │◀────────│ Node 3  │ data v1  → read repair!
              └──────────────┘         └─────────┘

┌───────────────────┬────────┬─────────────────────────────────────────┐
│ Consistency Level │ Nodes  │ Use Case                                 │
├───────────────────┼────────┼─────────────────────────────────────────┤
│ ONE               │ 1      │ Logs, metrics, IoT (fast, low latency) │
│ TWO               │ 2      │ Rarely used                             │
│ QUORUM            │ ⌈N/2⌉+1│ Default for strong consistency         │
│ LOCAL_QUORUM      │ ⌈Nlocal│ Multi-DC: strong in local DC           │
│                   │ /2⌉+1  │                                         │
│ EACH_QUORUM      │ quorum  │ Strong across ALL DCs (slow, safe)     │
│                   │ per DC  │                                         │
│ ALL               │ N      │ Never in production (one node down =   │
│                   │        │ unavailable)                            │
│ LOCAL_ONE         │ 1 local│ Analytics reads, non-critical           │
└───────────────────┴────────┴─────────────────────────────────────────┘

Strong Consistency Formula:
  W + R > N  (write CL + read CL > replication factor)
  
  QUORUM write + QUORUM read:  2 + 2 > 3 ✓ (strongly consistent)
  ONE write + ONE read:        1 + 1 > 3 ✗ (eventually consistent)
  ALL write + ONE read:        3 + 1 > 3 ✓ (strongly consistent)
```

### Multi-Datacenter Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│              Multi-DC Replication (NetworkTopologyStrategy)          │
└─────────────────────────────────────────────────────────────────────┘

CREATE KEYSPACE myapp WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'us-east': 3,
  'us-west': 3,
  'eu-west': 3
};

Write Flow (LOCAL_QUORUM):
┌───────────────────────────────────────────────────────────────────┐
│                                                                    │
│  US-EAST (local DC)              US-WEST           EU-WEST        │
│  ┌───────────────────┐          ┌─────────┐      ┌─────────┐    │
│  │ Coordinator       │          │ Node 4  │      │ Node 7  │    │
│  │   │               │          │ Node 5  │      │ Node 8  │    │
│  │   ├──▶ Node 1 ✓   │──async──▶│ Node 6  │─────▶│ Node 9  │    │
│  │   ├──▶ Node 2 ✓   │          └─────────┘      └─────────┘    │
│  │   └──▶ Node 3     │                                           │
│  │                    │                                           │
│  │  2/3 ACK = SUCCESS │          (replicate async to other DCs)  │
│  └───────────────────┘                                           │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘

- LOCAL_QUORUM: Only waits for local DC quorum (fast)
- Cross-DC replication happens asynchronously (no latency penalty)
- Each DC has full copy of data (RF per DC)
- Survives entire DC failure without data loss
```

### Hinted Handoff

```
┌─────────────────────────────────────────────────────────────────────┐
│              Hinted Handoff (temporary node failure)                 │
└─────────────────────────────────────────────────────────────────────┘

Normal write (RF=3):
  Client → Coordinator → [Node A ✓, Node B ✓, Node C ✓]

Node C is down:
  Client → Coordinator → [Node A ✓, Node B ✓, Node C ✗]
                                                │
                                    Coordinator stores HINT:
                                    ┌─────────────────────────────┐
                                    │ Hint for Node C:             │
                                    │   mutation data              │
                                    │   target: Node C             │
                                    │   timestamp: ...             │
                                    │   TTL: max_hint_window (3hr) │
                                    └─────────────────────────────┘

When Node C comes back:
  Coordinator → delivers stored hints → Node C applies them

Limitations:
- Hints stored for max_hint_window_in_ms (default: 3 hours)
- If node is down longer than hint window → data loss until repair
- Hints consume disk space on coordinator
- NOT a substitute for repair (hints can be lost if coordinator also fails)
```

---

## Scalability Patterns

### Linear Scalability

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cassandra Linear Scaling                                │
└─────────────────────────────────────────────────────────────────────┘

Throughput scales linearly with nodes:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Throughput (K ops/sec)                                          │
│  │                                                              │
│  │                                              ● 900K          │
│  │                                        ●                     │
│  │                                  ●                           │
│  │                            ●  600K                           │
│  │                      ●                                       │
│  │                ●  400K                                       │
│  │          ●                                                   │
│  │    ●  200K                                                   │
│  │ ●                                                            │
│  │ 100K                                                         │
│  └──────────────────────────────────────────────────────────────│
│     3     6     9    12    15    18    21    24    27  Nodes     │
│                                                                  │
│  Why linear:                                                     │
│  - No master/coordinator bottleneck                             │
│  - Each node handles its own partition range                    │
│  - Adding nodes = splitting token ranges = more capacity        │
│  - No cross-node coordination for writes                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Partition Sizing Guidelines

```
┌─────────────────────────────────────────────────────────────────────┐
│              Partition Design Rules                                  │
└─────────────────────────────────────────────────────────────────────┘

Hard Limits:
- Max partition size: 2 billion cells (columns * rows in partition)
- Recommended max: 100MB per partition
- Recommended max: 100,000 rows per partition

Design Patterns:
┌──────────────────────────────────────────────────────────────────┐
│ Wide Partition (time series):                                     │
│   PK: (sensor_id, day)                                           │
│   Cluster: timestamp                                             │
│   → Max rows per day ≈ 86,400 (1 per second) ✓                 │
│                                                                  │
│ Bucketing (for fast-growing partitions):                         │
│   PK: (channel_id, bucket)  where bucket = timestamp / 86400    │
│   → Caps partition growth to 1 day of data                      │
│                                                                  │
│ Skinny Partition (lookup):                                       │
│   PK: (user_id)                                                  │
│   → One row per partition (fastest reads, most partitions)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Production Setup

### Compaction Strategies

```
┌─────────────────────────────────────────────────────────────────────┐
│              Compaction Strategy Selection                           │
└─────────────────────────────────────────────────────────────────────┘

STCS (Size-Tiered Compaction Strategy):
┌──────────────────────────────────────────────────────────────┐
│  Merges SSTables of similar size together                     │
│                                                              │
│  [1MB][1MB][1MB][1MB] → compact → [4MB]                     │
│  [4MB][4MB][4MB][4MB] → compact → [16MB]                    │
│                                                              │
│  Pros: Good write throughput, low I/O amplification          │
│  Cons: Needs 50% free disk (temp space), space amplification │
│  Use for: Write-heavy, time-series, rarely updated data      │
└──────────────────────────────────────────────────────────────┘

LCS (Leveled Compaction Strategy):
┌──────────────────────────────────────────────────────────────┐
│  Fixed-size SSTables (160MB), organized in levels            │
│                                                              │
│  L0: [SST][SST][SST]  (from memtable flush)                │
│  L1: [SST][SST][SST][SST]  (10x size of L0)                │
│  L2: [SST][SST]...[SST]    (10x size of L1)                │
│                                                              │
│  Each level has non-overlapping key ranges                   │
│  Read: check at most 1 SSTable per level                    │
│                                                              │
│  Pros: Predictable read latency, low space amplification    │
│  Cons: Higher write amplification (10-30x)                  │
│  Use for: Read-heavy, frequently updated, point lookups     │
└──────────────────────────────────────────────────────────────┘

TWCS (Time Window Compaction Strategy):
┌──────────────────────────────────────────────────────────────┐
│  Groups SSTables by time window, compacts within window       │
│                                                              │
│  Window 1 (Jan 1-7):  [compacted SSTable]                   │
│  Window 2 (Jan 8-14): [compacted SSTable]                   │
│  Window 3 (Jan 15+):  [SST][SST][SST] (still accumulating) │
│                                                              │
│  Older windows never re-compacted (immutable past)           │
│  TTL data drops entire SSTables when window expires          │
│                                                              │
│  Pros: Perfect for time-series + TTL, efficient deletes     │
│  Cons: Only for time-ordered data, no updates/deletes       │
│  Use for: Logs, metrics, IoT, viewing history               │
└──────────────────────────────────────────────────────────────┘
```

### cassandra.yaml Critical Settings

```yaml
# Cluster
cluster_name: 'production-cluster'
num_tokens: 16          # vnodes (16 for new clusters, simpler than 256)
endpoint_snitch: GossipingPropertyFileSnitch  # multi-DC awareness

# Memory
memtable_heap_space: 2048  # MB, default is 1/4 of heap
memtable_offheap_space: 2048

# Disk
data_file_directories:
  - /data1/cassandra
  - /data2/cassandra     # multiple disks for parallelism
commitlog_directory: /commitlog/cassandra  # SEPARATE disk from data!

# Compaction
compaction_throughput: 64  # MB/s (don't starve foreground I/O)
concurrent_compactors: 4   # usually = number of disks

# Networking
native_transport_port: 9042
rpc_address: 0.0.0.0
broadcast_rpc_address: <node_ip>

# Timeouts
read_request_timeout: 5000    # ms
write_request_timeout: 2000   # ms
counter_write_request_timeout: 5000

# Repair & Consistency
hinted_handoff_enabled: true
max_hint_window: 3h
gc_grace_seconds: 864000      # 10 days (must repair within this!)

# JVM (in jvm.options)
# -Xms16G -Xmx16G (min = max, always)
# -XX:+UseG1GC
# -XX:MaxGCPauseMillis=500
```

---

## Core Concepts

### Write Path

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cassandra Write Path                                    │
└─────────────────────────────────────────────────────────────────────┘

┌────────┐    ┌──────────────┐    ┌─────────────────────────────────────┐
│ Client │───▶│ Coordinator  │───▶│          Target Node                 │
└────────┘    └──────────────┘    │                                     │
                                  │  1. ┌────────────────┐              │
                                  │     │  Commit Log    │ (append-only)│
                                  │     │  (sequential   │              │
                                  │     │   write, fast) │              │
                                  │     └────────────────┘              │
                                  │              │                       │
                                  │  2.          ▼                       │
                                  │     ┌────────────────┐              │
                                  │     │   Memtable     │ (in-memory)  │
                                  │     │  (sorted by    │              │
                                  │     │   clustering   │              │
                                  │     │   key)         │              │
                                  │     └────────┬───────┘              │
                                  │              │ flush (when full)    │
                                  │  3.          ▼                       │
                                  │     ┌────────────────┐              │
                                  │     │   SSTable      │ (immutable)  │
                                  │     │  (on disk)     │              │
                                  │     └────────────────┘              │
                                  │                                     │
                                  │  4. ACK to coordinator              │
                                  └─────────────────────────────────────┘

Write is acknowledged after step 1 + 2 (commit log + memtable)
Extremely fast: 2 sequential I/Os (commit log) + memory write
No read-before-write needed (unlike B-tree databases)
```

### Read Path

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cassandra Read Path                                     │
└─────────────────────────────────────────────────────────────────────┘

┌────────┐    ┌──────────────┐    ┌─────────────────────────────────────┐
│ Client │───▶│ Coordinator  │───▶│          Target Node                 │
└────────┘    └──────────────┘    │                                     │
                                  │  ┌─────────────────────────────────┐│
                                  │  │ 1. Check Memtable (in memory)   ││
                                  │  └──────────────┬──────────────────┘│
                                  │                 │ not found?         │
                                  │  ┌──────────────▼──────────────────┐│
                                  │  │ 2. Check Row Cache (if enabled) ││
                                  │  └──────────────┬──────────────────┘│
                                  │                 │ not found?         │
                                  │  ┌──────────────▼──────────────────┐│
                                  │  │ 3. Bloom Filter (per SSTable)   ││
                                  │  │    "Is key possibly here?"      ││
                                  │  │    NO → skip this SSTable       ││
                                  │  │    YES → continue               ││
                                  │  └──────────────┬──────────────────┘│
                                  │                 │ might be here      │
                                  │  ┌──────────────▼──────────────────┐│
                                  │  │ 4. Partition Index (binary srch)││
                                  │  │    → offset in SSTable          ││
                                  │  └──────────────┬──────────────────┘│
                                  │                 │                    │
                                  │  ┌──────────────▼──────────────────┐│
                                  │  │ 5. Compression Offset Map       ││
                                  │  │    → exact disk location        ││
                                  │  └──────────────┬──────────────────┘│
                                  │                 │                    │
                                  │  ┌──────────────▼──────────────────┐│
                                  │  │ 6. Read data from SSTable       ││
                                  │  │    (disk I/O - one seek)        ││
                                  │  └─────────────────────────────────┘│
                                  │                                     │
                                  │  7. Merge results from all sources  │
                                  │     (latest timestamp wins)         │
                                  └─────────────────────────────────────┘
```

### LSM Tree Storage

```
┌─────────────────────────────────────────────────────────────────────┐
│              LSM Tree in Cassandra                                   │
└─────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
    Writes ────────▶│    Memtable       │ (Red-Black Tree, in memory)
                    │    (sorted)       │
                    └─────────┬─────────┘
                              │ flush (when memtable_heap_space full)
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                     SSTables on Disk                          │
    │                                                              │
    │  SSTable = immutable, sorted file:                           │
    │  ┌────────────────────────────────────────────────────────┐ │
    │  │ Data.db        │ sorted key-value pairs                │ │
    │  │ Index.db       │ partition key → offset in Data.db     │ │
    │  │ Filter.db      │ Bloom filter (false positive ~1%)     │ │
    │  │ Summary.db     │ sampled index for faster seeking      │ │
    │  │ Statistics.db  │ min/max timestamps, count, size       │ │
    │  │ CompressionInfo│ compression chunk offsets              │ │
    │  │ TOC.txt        │ list of all component files           │ │
    │  └────────────────────────────────────────────────────────┘ │
    │                                                              │
    │  Compaction merges SSTables:                                 │
    │  [SST1] + [SST2] + [SST3] ──merge──▶ [New SST]            │
    │  (removes tombstones, resolves conflicts by timestamp)      │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
```

### Tombstones & TTL

```
┌─────────────────────────────────────────────────────────────────────┐
│              Tombstones (Distributed Deletes)                        │
└─────────────────────────────────────────────────────────────────────┘

Why tombstones exist:
- Cassandra is distributed → can't ensure all replicas got the DELETE
- Tombstone = "death certificate" → tells replicas "this was deleted"
- Without tombstones: deleted data would "resurrect" from stale replicas

DELETE lifecycle:
┌─────────┐    ┌──────────────────┐    ┌────────────────────────────┐
│ DELETE  │───▶│ Write Tombstone  │───▶│ After gc_grace_seconds     │
│ command │    │ (marked deleted  │    │ (default 10 days):         │
└─────────┘    │  at timestamp T) │    │ compaction removes         │
               └──────────────────┘    │ tombstone permanently      │
                                       └────────────────────────────┘

CRITICAL: Must run repair within gc_grace_seconds!
  If not: tombstone removed on one node, but stale data exists on another
  → stale data "resurrects" (zombie data)

Tombstone problems:
- Range scans read through tombstones (slow reads)
- Many tombstones = increased heap pressure
- tombstone_warn_threshold: 1000 (log warning)
- tombstone_failure_threshold: 100000 (query fails)

Best practices:
- Use TTL instead of DELETE where possible (cleaner expiration)
- Design data model to minimize deletes
- Run repair regularly (within gc_grace_seconds)
- Monitor tombstone counts per read
```
