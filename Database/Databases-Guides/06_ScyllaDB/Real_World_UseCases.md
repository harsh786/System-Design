# ScyllaDB - Real World Use Cases & Production Guide

## Overview

ScyllaDB is a drop-in replacement for Apache Cassandra, rewritten in C++ using the Seastar framework. It eliminates the JVM and its garbage collection pauses, delivering consistent low-latency at scale through a shard-per-core architecture.

```
┌─────────────────────────────────────────────────────────┐
│                  ScyllaDB vs Cassandra                   │
├─────────────────────────────────────────────────────────┤
│  Cassandra (Java/JVM)      │  ScyllaDB (C++/Seastar)   │
│  - GC pauses               │  - No GC, no JVM          │
│  - Thread-per-request      │  - Shard-per-core          │
│  - Shared memory + locks   │  - No locks, no sharing   │
│  - ~10x nodes needed       │  - 3-10x fewer nodes      │
│  - P99 spikes under load   │  - Consistent P99          │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Real-World Use Cases

### 1.1 Discord - Message Storage

**Scale:** Trillions of messages, billions of reads/day

**Problem:** Cassandra's JVM GC pauses caused P99 latency spikes (40-125ms) during compaction and garbage collection. Hot partitions (large servers) caused cascading issues.

**Result:**
- 177 Cassandra nodes → 72 ScyllaDB nodes
- P99 latency: 40-125ms → 15ms
- Consistent performance under compaction

```
┌──────────────────────────────────────────────────────────────┐
│                  Discord Message Architecture                  │
│                                                              │
│  ┌─────────┐     ┌──────────────┐     ┌─────────────────┐  │
│  │ Gateway │────▶│ Message Svc  │────▶│  ScyllaDB       │  │
│  │ (Elixir)│     │  (Rust)      │     │  Cluster        │  │
│  └─────────┘     └──────────────┘     │                 │  │
│                         │              │  72 nodes       │  │
│                         ▼              │  RF=3           │  │
│                  ┌──────────────┐     │  CL=LOCAL_QUORUM│  │
│                  │ Channel Cache│     └─────────────────┘  │
│                  │  (Hot data)  │                           │
│                  └──────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

**CQL Data Model:**

```sql
CREATE KEYSPACE discord_messages WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'us-east': 3,
  'us-west': 3
};

CREATE TABLE discord_messages.messages (
    channel_id   bigint,
    bucket       int,          -- Time bucket (e.g., 10-day windows)
    message_id   bigint,       -- Snowflake ID (time-ordered)
    author_id    bigint,
    content      text,
    attachments  frozen<list<frozen<attachment>>>,
    embeds       frozen<list<frozen<embed>>>,
    edited_at    timestamp,
    PRIMARY KEY ((channel_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND compaction = {'class': 'IncrementalCompactionStrategy'}
  AND gc_grace_seconds = 864000;

-- Bucketing prevents unbounded partition growth
-- Snowflake IDs give time-ordering without secondary index
```

**Why ScyllaDB Won:**
- No GC pauses → stable P99
- Shard-per-core → hot partitions handled by dedicated core
- ICS compaction → no read amplification spikes

---

### 1.2 Comcast - Video Delivery Platform

**Scale:** 30M+ concurrent viewers, millions of metadata lookups/sec

**Problem:** Video metadata (titles, thumbnails, playback URLs) must be served in <10ms for responsive UI. CDN edge caches need a fast origin.

```
┌──────────────────────────────────────────────────────────────────┐
│              Comcast Video Delivery Architecture                   │
│                                                                  │
│  ┌────────┐    ┌─────────┐    ┌──────────┐    ┌─────────────┐  │
│  │ STB /  │───▶│  CDN    │───▶│ API      │───▶│  ScyllaDB   │  │
│  │ App    │    │  Edge   │    │ Gateway  │    │  (metadata) │  │
│  └────────┘    └─────────┘    └──────────┘    └─────────────┘  │
│                                     │                            │
│                                     ▼                            │
│                              ┌──────────────┐                    │
│                              │ Kafka Stream │                    │
│                              │ (events)     │                    │
│                              └──────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

**CQL Data Model:**

```sql
CREATE TABLE video.catalog_metadata (
    content_id    uuid,
    region        text,
    title         text,
    description   text,
    thumbnail_url text,
    playback_urls map<text, text>,  -- {quality: url}
    genres        set<text>,
    rating        text,
    duration_sec  int,
    updated_at    timestamp,
    PRIMARY KEY ((content_id, region))
) WITH compaction = {'class': 'SizeTieredCompactionStrategy'};

CREATE TABLE video.user_watch_history (
    user_id       uuid,
    watched_at    timestamp,
    content_id    uuid,
    progress_sec  int,
    PRIMARY KEY ((user_id), watched_at)
) WITH CLUSTERING ORDER BY (watched_at DESC);
```

**Scale Numbers:**
- 30M+ concurrent viewers during peak
- 2M+ reads/sec for metadata
- Sub-5ms P99 reads
- 3 DCs for geo-redundancy

---

### 1.3 Zillow - Real Estate Listings

**Scale:** 135M+ property records, 200M+ monthly unique visitors

**Problem:** Property data changes frequently (price, status), needs fast reads for search results with geographic partitioning.

```
┌────────────────────────────────────────────────────────────┐
│              Zillow Property Data Architecture              │
│                                                            │
│  ┌──────────┐    ┌───────────────┐    ┌───────────────┐  │
│  │ Web/App  │───▶│ Search Svc    │───▶│ Elasticsearch │  │
│  │ Client   │    │               │    │ (full-text)   │  │
│  └──────────┘    └───────────────┘    └───────────────┘  │
│                         │                                  │
│                         ▼                                  │
│                  ┌───────────────┐    ┌───────────────┐   │
│                  │ Property Svc  │───▶│  ScyllaDB     │   │
│                  │               │    │  (source of   │   │
│                  └───────────────┘    │   truth)      │   │
│                         │             └───────────────┘   │
│                         ▼                                  │
│                  ┌───────────────┐                         │
│                  │ Kafka         │ (CDC for ES sync)       │
│                  └───────────────┘                         │
└────────────────────────────────────────────────────────────┘
```

**CQL Data Model:**

```sql
CREATE TABLE zillow.properties (
    zip_code      text,
    property_id   uuid,
    address       text,
    city          text,
    state         text,
    price         decimal,
    bedrooms      int,
    bathrooms     float,
    sqft          int,
    listing_type  text,    -- 'sale', 'rent', 'sold'
    listed_at     timestamp,
    photos        list<text>,
    features      map<text, text>,
    PRIMARY KEY ((zip_code), property_id)
);

CREATE TABLE zillow.property_history (
    property_id   uuid,
    event_time    timestamp,
    event_type    text,    -- 'price_change', 'status_change'
    old_value     text,
    new_value     text,
    PRIMARY KEY ((property_id), event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
```

---

### 1.4 ShareChat - Social Feed

**Scale:** 180M+ monthly active users, India's largest social media platform

**Problem:** Feed generation and storage for hundreds of millions of users with diverse content types (text, images, video, audio). High write throughput for user actions.

```
┌──────────────────────────────────────────────────────────────┐
│              ShareChat Feed Architecture                       │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Mobile   │───▶│ Feed Service │───▶│  ScyllaDB       │   │
│  │ App      │    │              │    │  (feed store)   │   │
│  └──────────┘    └──────────────┘    └─────────────────┘   │
│       │                │                                     │
│       │                ▼                                     │
│       │         ┌──────────────┐    ┌─────────────────┐    │
│       └────────▶│ Action Svc   │───▶│  ScyllaDB       │    │
│                 │ (like/share) │    │  (counters)     │    │
│                 └──────────────┘    └─────────────────┘    │
│                        │                                    │
│                        ▼                                    │
│                 ┌──────────────┐                            │
│                 │ ML Ranking   │                            │
│                 │ Service      │                            │
│                 └──────────────┘                            │
└──────────────────────────────────────────────────────────────┘
```

**CQL Data Model:**

```sql
CREATE TABLE sharechat.user_feed (
    user_id       bigint,
    feed_bucket   int,           -- Daily/hourly bucket
    post_score    double,        -- ML ranking score
    post_id       bigint,
    author_id     bigint,
    content_type  text,
    content_url   text,
    caption       text,
    PRIMARY KEY ((user_id, feed_bucket), post_score, post_id)
) WITH CLUSTERING ORDER BY (post_score DESC, post_id DESC);

CREATE TABLE sharechat.post_counters (
    post_id       bigint,
    likes         counter,
    shares        counter,
    comments      counter,
    views         counter,
    PRIMARY KEY ((post_id))
);
```

**Scale Numbers:**
- 180M+ MAU
- 500K+ writes/sec
- 2M+ reads/sec for feed
- 15 nodes (vs 100+ if on Cassandra)

---

### 1.5 Grab - Ride-hailing & Delivery

**Scale:** Millions of rides/day across 8 countries in Southeast Asia

**Problem:** Real-time location tracking, order state management, and driver matching require low-latency writes and reads with geographic distribution.

```
┌──────────────────────────────────────────────────────────────────┐
│                 Grab Location & Order Architecture                 │
│                                                                  │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────────────┐  │
│  │ Driver   │───▶│ Location Svc  │───▶│ ScyllaDB (Singapore) │  │
│  │ App      │    │ (GPS stream)  │    │   - driver_locations │  │
│  └──────────┘    └───────────────┘    │   - order_state      │  │
│                                        └──────────────────────┘  │
│  ┌──────────┐    ┌───────────────┐              │                │
│  │ Rider    │───▶│ Matching Svc  │◀─────────────┘                │
│  │ App      │    │               │                               │
│  └──────────┘    └───────────────┘    ┌──────────────────────┐  │
│                         │             │ ScyllaDB (Jakarta)    │  │
│                         └────────────▶│   - replica           │  │
│                                       └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**CQL Data Model:**

```sql
CREATE TABLE grab.driver_locations (
    geohash_prefix text,       -- Geohash prefix for spatial queries
    driver_id      uuid,
    latitude       double,
    longitude      double,
    heading        float,
    speed          float,
    updated_at     timestamp,
    status         text,       -- 'available', 'on_trip', 'offline'
    PRIMARY KEY ((geohash_prefix), updated_at, driver_id)
) WITH CLUSTERING ORDER BY (updated_at DESC, driver_id ASC)
  AND default_time_to_live = 30;  -- TTL: only recent locations matter

CREATE TABLE grab.orders (
    order_id       uuid,
    rider_id       uuid,
    driver_id      uuid,
    status         text,
    pickup_lat     double,
    pickup_lng     double,
    dropoff_lat    double,
    dropoff_lng    double,
    created_at     timestamp,
    updated_at     timestamp,
    fare_estimate  decimal,
    PRIMARY KEY ((order_id))
);
```

**Scale Numbers:**
- Millions of location updates/sec
- Sub-10ms reads for driver matching
- Multi-DC across Singapore, Jakarta, Ho Chi Minh City
- TTL-based auto-cleanup of stale locations

---

## 2. Replication

### Ring-based Replication (Same as Cassandra)

ScyllaDB uses the same replication model as Cassandra - consistent hashing with a token ring.

```
┌─────────────────────────────────────────────────────────┐
│              Token Ring (RF=3)                           │
│                                                         │
│                    Node A                                │
│                   (0-255)                                │
│                  ╱       ╲                               │
│            Node F         Node B                        │
│          (1280-1535)    (256-511)                        │
│              │               │                          │
│            Node E         Node C                        │
│          (1024-1279)    (512-767)                        │
│                  ╲       ╱                               │
│                   Node D                                │
│                 (768-1023)                               │
│                                                         │
│  Write to key hash=300 → B (primary), C, D (replicas)  │
└─────────────────────────────────────────────────────────┘
```

### Consistency Levels

| Level | Reads/Writes | Use Case |
|-------|-------------|----------|
| ONE | 1 replica | Highest throughput, eventual consistency |
| QUORUM | ⌊RF/2⌋+1 | Strong consistency within DC |
| LOCAL_QUORUM | Quorum in local DC | Most common production choice |
| EACH_QUORUM | Quorum in each DC | Strongest multi-DC guarantee |
| ALL | All replicas | Highest consistency, lowest availability |

### Cross-DC Replication

```
┌────────────────────────────────────────────────────────────────┐
│           Multi-DC Replication (NetworkTopologyStrategy)        │
│                                                                │
│  ┌─────────────────────┐         ┌─────────────────────┐     │
│  │     DC: us-east     │         │     DC: eu-west     │     │
│  │                     │◀───────▶│                     │     │
│  │  ┌───┐ ┌───┐ ┌───┐│  Async  │┌───┐ ┌───┐ ┌───┐  │     │
│  │  │ 1 │ │ 2 │ │ 3 ││ Replic. ││ 4 │ │ 5 │ │ 6 │  │     │
│  │  └───┘ └───┘ └───┘│         │└───┘ └───┘ └───┘  │     │
│  │     RF=3           │         │     RF=3           │     │
│  └─────────────────────┘         └─────────────────────┘     │
│                                                                │
│  CREATE KEYSPACE ks WITH replication = {                       │
│    'class': 'NetworkTopologyStrategy',                         │
│    'us-east': 3, 'eu-west': 3                                 │
│  };                                                            │
└────────────────────────────────────────────────────────────────┘
```

### Raft-based Tablets (Replacing Vnodes)

ScyllaDB is migrating from vnodes to **tablets** - Raft-based range ownership.

```
Traditional Vnodes:              Tablets (New):
┌─────────────────────┐         ┌─────────────────────┐
│ Node has 256 vnodes │         │ Table split into    │
│ scattered on ring   │         │ tablets, each with  │
│                     │         │ Raft group          │
│ Problem:            │         │                     │
│ - Streaming is slow │         │ Benefits:           │
│ - Repair is complex │         │ - Fast streaming    │
│ - Topology changes  │         │ - Raft consensus    │
│   are heavyweight   │         │ - Granular moves    │
│                     │         │ - No anti-entropy   │
└─────────────────────┘         │   repair needed     │
                                └─────────────────────┘

Tablet Raft Group:
┌─────────────────────────────────────┐
│  Tablet T1 (range: 0-1000)         │
│                                     │
│  Leader: Node A, Shard 3            │
│  Follower: Node B, Shard 1          │
│  Follower: Node C, Shard 5          │
│                                     │
│  Raft log → consistent replication  │
└─────────────────────────────────────┘
```

---

## 3. Scalability

### Shard-per-Core Architecture

The defining feature of ScyllaDB. Each CPU core operates as an independent shard with its own:
- Memory allocation
- Disk I/O queue
- Network connections
- Data partition ownership

```
┌──────────────────────────────────────────────────────────────────┐
│          Cassandra: Thread Pool Model                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Shared Heap (JVM)                      │    │
│  │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │    │
│  │   │Thread│ │Thread│ │Thread│ │Thread│ │Thread│  ...    │    │
│  │   │  1   │ │  2   │ │  3   │ │  4   │ │  5   │       │    │
│  │   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘       │    │
│  │      │        │        │        │        │             │    │
│  │      ▼        ▼        ▼        ▼        ▼             │    │
│  │   ┌─────────────────────────────────────────────┐      │    │
│  │   │     Locks / Contention / Context Switches    │      │    │
│  │   └─────────────────────────────────────────────┘      │    │
│  │                        │                                │    │
│  │              ┌─────────▼──────────┐                     │    │
│  │              │   GC PAUSE (STW)   │ ← 50-500ms          │    │
│  │              └────────────────────┘                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│          ScyllaDB: Shard-per-Core Model (Seastar)                │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Core 0  │  │  Core 1  │  │  Core 2  │  │  Core 3  │  ...  │
│  │          │  │          │  │          │  │          │       │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │       │
│  │ │Memory│ │  │ │Memory│ │  │ │Memory│ │  │ │Memory│ │       │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │       │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │       │
│  │ │ I/O  │ │  │ │ I/O  │ │  │ │ I/O  │ │  │ │ I/O  │ │       │
│  │ │Queue │ │  │ │Queue │ │  │ │Queue │ │  │ │Queue │ │       │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │       │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │       │
│  │ │ Net  │ │  │ │ Net  │ │  │ │ Net  │ │  │ │ Net  │ │       │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │       │
│  │          │  │          │  │          │  │          │       │
│  │ NO LOCKS │  │ NO LOCKS │  │ NO LOCKS │  │ NO LOCKS │       │
│  │ NO GC    │  │ NO GC    │  │ NO GC    │  │ NO GC    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  Cross-shard communication: explicit message passing only        │
└──────────────────────────────────────────────────────────────────┘
```

### Linear Scaling

```
Throughput vs Nodes (ScyllaDB):

Ops/sec │
  1.2M  │                                          ●
  1.0M  │                                ●
  800K  │                       ●
  600K  │              ●
  400K  │     ●
  200K  │ ●
        └──────────────────────────────────────────
          3     6     9     12    15    18   Nodes

Each node added = proportional throughput increase
(No coordination overhead eating into gains)
```

### Workload Prioritization

ScyllaDB can isolate workloads at the scheduler level:

```sql
-- Create service levels
CREATE SERVICE LEVEL realtime WITH timeout = '5ms' AND workload_type = 'interactive';
CREATE SERVICE LEVEL analytics WITH timeout = '60s' AND workload_type = 'batch';

-- Assign to roles
ATTACH SERVICE LEVEL realtime TO prod_app;
ATTACH SERVICE LEVEL analytics TO spark_etl;
```

```
┌─────────────────────────────────────────────┐
│         Per-Core Scheduler                   │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │ Shares:  realtime=1000  analytics=100 │  │
│  │                                       │  │
│  │  realtime ████████████████████  90%   │  │
│  │  analytics ██                   10%   │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Analytics never starves realtime traffic   │
└─────────────────────────────────────────────┘
```

---

## 4. Production Setup

### Hardware Recommendations

| Component | Recommendation | Notes |
|-----------|---------------|-------|
| CPU | Many cores (16-64+) | Each core = independent shard |
| RAM | 32-256 GB | More RAM = larger cache |
| Storage | NVMe SSDs | MUST be NVMe; no SATA/spinning |
| Network | 10 Gbps+ | Inter-node replication |
| Instance | i3/i3en (AWS), L-series (Azure) | Local NVMe storage |

### Initial Setup

```bash
# Install ScyllaDB (Ubuntu/Debian)
curl -sSf get.scylladb.com/server | sudo bash
sudo apt-get install scylla

# Run setup scripts
sudo scylla_setup                # Interactive setup wizard
sudo scylla_io_setup             # Benchmarks disks, configures I/O scheduler
sudo scylla_cpuset_setup         # Pin IRQs and cores

# Key configs in /etc/scylla/scylla.yaml
cluster_name: 'production'
seeds: '10.0.1.1,10.0.1.2'
endpoint_snitch: GossipingPropertyFileSnitch
authenticator: PasswordAuthenticator
authorizer: CassandraAuthorizer

# Start
sudo systemctl start scylla-server
```

### Scylla Monitoring Stack

```
┌──────────────────────────────────────────────────────────┐
│              Monitoring Architecture                       │
│                                                          │
│  ┌──────────┐    ┌────────────┐    ┌──────────────┐    │
│  │ ScyllaDB │───▶│ Prometheus │───▶│   Grafana    │    │
│  │ (metrics)│    │            │    │ (dashboards) │    │
│  └──────────┘    └────────────┘    └──────────────┘    │
│                                                          │
│  Pre-built dashboards:                                   │
│  - Cluster overview (throughput, latency)                │
│  - Per-node / per-shard metrics                          │
│  - Compaction progress                                   │
│  - Cache hit rates                                       │
│  - Repair status                                         │
└──────────────────────────────────────────────────────────┘

# Deploy monitoring stack
docker-compose -f docker-compose-monitoring.yml up -d
```

### Scylla Manager (Repair & Backup)

```bash
# Install Scylla Manager
sudo apt-get install scylla-manager

# Register cluster
sctool cluster add --host 10.0.1.1 --name production

# Schedule weekly repair
sctool repair schedule --cluster production \
  --interval 7d \
  --intensity 1     # Parallel repair streams per shard

# Schedule daily backup to S3
sctool backup schedule --cluster production \
  --interval 1d \
  --location s3:scylla-backups \
  --retention 7
```

---

## 5. Core Concepts

### Seastar Reactor Pattern

```
┌──────────────────────────────────────────────────────────┐
│            Seastar Event Loop (per core)                   │
│                                                          │
│    ┌──────────────────────────────────────────────────┐  │
│    │              Event Loop (never blocks)            │  │
│    │                                                  │  │
│    │   ┌─────────┐  ┌──────────┐  ┌────────────┐   │  │
│    │   │  Poll   │─▶│  Run     │─▶│  Complete  │   │  │
│    │   │  I/O    │  │  Tasks   │  │  Futures   │   │  │
│    │   └─────────┘  └──────────┘  └────────────┘   │  │
│    │        ▲                            │           │  │
│    │        └────────────────────────────┘           │  │
│    │                                                  │  │
│    │   - Uses Linux AIO / io_uring                   │  │
│    │   - Futures & continuations (no callbacks)      │  │
│    │   - userspace task scheduler                    │  │
│    │   - Zero-copy networking                        │  │
│    └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### CQL Compatibility

ScyllaDB is wire-protocol compatible with Cassandra (CQL native protocol v4). Existing Cassandra drivers work unchanged:

```python
# Same driver, same code, just point to ScyllaDB
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy

cluster = Cluster(
    ['scylla-node1', 'scylla-node2'],
    load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='us-east'),
    protocol_version=4
)
session = cluster.connect('my_keyspace')

# Shard-aware driver (ScyllaDB-optimized)
# pip install scylla-driver
from cassandra.cluster import Cluster  # scylla-driver is a drop-in
```

### Raft-based Consensus (vs Paxos)

```
┌──────────────────────────────────────────────────────────┐
│  Cassandra LWT (Paxos):     │  ScyllaDB (Raft):         │
│                              │                            │
│  4 round-trips per LWT:     │  1 round-trip (leader):    │
│  1. Prepare                  │  1. Leader appends to log  │
│  2. Promise                  │  2. Replicates to majority │
│  3. Propose                  │  3. Commits                │
│  4. Commit                   │                            │
│                              │  Stable leader = fast path │
│  No leader = contention      │  Schema changes via Raft   │
│  under concurrent LWTs       │  Topology changes via Raft │
└──────────────────────────────────────────────────────────┘
```

Used for:
- Schema changes (no more schema disagreements)
- Topology changes
- Tablet ownership
- Future: strongly consistent tables

### Alternator (DynamoDB-Compatible API)

ScyllaDB exposes a DynamoDB-compatible API, allowing migration from DynamoDB without code changes:

```python
import boto3

# Point DynamoDB client at ScyllaDB Alternator
dynamodb = boto3.resource('dynamodb',
    endpoint_url='http://scylla-node:8000',
    region_name='us-east-1',
    aws_access_key_id='none',
    aws_secret_access_key='none'
)

table = dynamodb.Table('users')
table.put_item(Item={'user_id': '123', 'name': 'Alice'})
response = table.get_item(Key={'user_id': '123'})
```

### Incremental Compaction Strategy (ICS)

```
┌──────────────────────────────────────────────────────────┐
│  Size-Tiered (STCS):          │  ICS (ScyllaDB):         │
│                                │                          │
│  ┌────┐┌────┐┌────┐┌────┐    │  ┌──┐┌──┐┌──┐           │
│  │ L0 ││ L0 ││ L0 ││ L0 │    │  │  ││  ││  │  Sorted   │
│  └──┬─┘└──┬─┘└──┬─┘└──┬─┘    │  └─┬┘└─┬┘└─┬┘  runs     │
│     └──┬───┘     └──┬───┘     │    │   │   │             │
│        ▼             ▼         │    ▼   ▼   ▼             │
│     ┌────────┐  ┌────────┐    │  Incremental merge:      │
│     │   L1   │  │   L1   │    │  - Pick 2 adjacent runs  │
│     └───┬────┘  └───┬────┘    │  - Merge into 1          │
│         └─────┬──────┘        │  - Bounded temp space     │
│               ▼               │  - No space amplification │
│        ┌────────────┐         │  - Predictable latency    │
│        │     L2     │         │                          │
│        └────────────┘         │                          │
│                                │                          │
│  50-100% space overhead        │  ~20% space overhead     │
│  Latency spikes during merge   │  Smooth, continuous      │
└──────────────────────────────────────────────────────────┘
```

### Workload Conditioning

ScyllaDB automatically detects and adapts to workload patterns:

- **Cache management:** Promotes/evicts based on actual access patterns per shard
- **I/O scheduling:** Prioritizes reads vs writes vs compaction based on service levels
- **Backpressure:** If a shard is overloaded, it signals the client to slow down (no queuing)

---

## 6. Performance Comparison Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              ScyllaDB vs Cassandra (typical production)           │
│                                                                 │
│  Metric              │ Cassandra        │ ScyllaDB              │
│  ────────────────────┼──────────────────┼────────────────────── │
│  P99 Read Latency    │ 10-50ms          │ 1-5ms                 │
│  P99 Write Latency   │ 5-20ms           │ 1-3ms                 │
│  P99 under compact.  │ 50-200ms (GC)    │ 5-10ms                │
│  Nodes needed (1M    │ 30-50 nodes      │ 5-10 nodes            │
│    ops/sec)          │                  │                       │
│  Ops/core            │ ~3K-12K          │ ~50K-150K             │
│  Tail latency        │ Unpredictable    │ Bounded               │
│  Tuning complexity   │ JVM + heap +     │ Mostly auto-tuned     │
│                      │ GC tuning        │                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. When to Use ScyllaDB

**Good fit:**
- High throughput, low latency (IoT, gaming, messaging, ad-tech)
- Cassandra replacement (drop-in, same CQL)
- DynamoDB cost reduction (Alternator API)
- Time-series with TTL
- Large datasets with predictable access patterns

**Not ideal for:**
- Complex joins / ad-hoc analytics (use ClickHouse, Snowflake)
- Small datasets (<100GB) where PostgreSQL suffices
- Strong multi-row transactions (use CockroachDB, Spanner)
- Full-text search (use Elasticsearch alongside)

---

## Quick Reference

```bash
# Connect
cqlsh scylla-node 9042

# Check cluster status
nodetool status

# Per-shard metrics
curl http://localhost:9180/metrics

# Tracing a slow query
TRACING ON;
SELECT * FROM ks.table WHERE pk = 'value';
TRACING OFF;
```
