# 🔴 Pinot Real-Time Segments & Kafka Consumption - Complete Production Guide

## 📌 What is a Real-Time Segment?

A **real-time segment** is a data container in Apache Pinot that holds records actively being ingested from a streaming source (Kafka, Kinesis, Pulsar). It exists in two phases:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REAL-TIME SEGMENT LIFECYCLE                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase 1: CONSUMING Segment                                      │
│  ┌──────────────────────────────────────────────────┐            │
│  │ • Lives in SERVER MEMORY (heap/off-heap)         │            │
│  │ • MUTABLE — appends new records continuously     │            │
│  │ • Partial indexing (basic forward index only)    │            │
│  │ • NOT compressed                                 │            │
│  │ • NOT in deep store                              │            │
│  │ • Query-able but slower than sealed segments     │            │
│  └──────────────────┬───────────────────────────────┘            │
│                     │ Seal trigger (size/time/rows)               │
│                     ▼                                             │
│  Phase 2: COMPLETED/ONLINE Segment                               │
│  ┌──────────────────────────────────────────────────┐            │
│  │ • Flushed to DISK (local + deep store)           │            │
│  │ • IMMUTABLE — zero writes allowed                │            │
│  │ • Full indexing (inverted, range, star-tree)     │            │
│  │ • Columnar compressed (LZ4/Snappy/ZSTD)         │            │
│  │ • Uploaded to deep store (S3/HDFS/GCS)           │            │
│  │ • Blazing fast queries                           │            │
│  └──────────────────────────────────────────────────┘            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Properties of a CONSUMING Segment

| Property | Value |
|----------|-------|
| **Location** | Server heap or off-heap memory |
| **Mutability** | Append-only (no updates/deletes) |
| **Indexing** | Forward index only (minimal) |
| **Compression** | None |
| **Durability** | NOT durable — lost if server crashes |
| **Recovery** | Replay from Kafka using stored offsets |
| **Query Performance** | Slower than sealed segments |
| **Naming Convention** | `tableName__partitionId__sequenceId__timestamp` |

### Why "Real-Time" and Not Just "Online"?

```
Terminology Clarification:

REAL-TIME TABLE = Table configured to ingest from streaming source
REAL-TIME SEGMENT = Segment belonging to a real-time table

CONSUMING = Actively ingesting (in-memory, mutable)
ONLINE/COMPLETED = Sealed real-time segment (on disk, immutable)

OFFLINE TABLE = Table that ingests batch data only
OFFLINE SEGMENT = Pre-built segment pushed to Pinot

HYBRID TABLE = Both real-time + offline together
```

---

## 🏗️ Architecture: How Pinot Consumes from Kafka

### High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Kafka Cluster                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │Partition 0│  │Partition 1│  │Partition 2│  │Partition 3│           │
│  └────┬─────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘           │
│       │               │             │              │                 │
└───────┼───────────────┼─────────────┼──────────────┼─────────────────┘
        │               │             │              │
        ▼               ▼             ▼              ▼
┌───────────────────────────────────────────────────────────────────────┐
│  Pinot Controller (Orchestrator)                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ • Partition Assignment: Which server consumes which partition    │ │
│  │ • Ideal State Management: Tracks segment states in ZooKeeper    │ │
│  │ • Segment Completion Protocol: Coordinates seal + upload        │ │
│  │ • Rebalancing: Handles server additions/removals                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
        │               │             │              │
        ▼               ▼             ▼              ▼
┌───────────────────────────────────────────────────────────────────────┐
│  Pinot Servers                                                        │
│                                                                       │
│  Server-1                    Server-2                                  │
│  ┌────────────────────┐     ┌────────────────────┐                   │
│  │ Partition 0 Consumer│     │ Partition 2 Consumer│                   │
│  │ ┌────────────────┐ │     │ ┌────────────────┐ │                   │
│  │ │CONSUMING Seg   │ │     │ │CONSUMING Seg   │ │                   │
│  │ │ offset: 50000  │ │     │ │ offset: 72000  │ │                   │
│  │ │ rows: 12K      │ │     │ │ rows: 18K      │ │                   │
│  │ └────────────────┘ │     │ └────────────────┘ │                   │
│  │                     │     │                     │                   │
│  │ Partition 1 Consumer│     │ Partition 3 Consumer│                   │
│  │ ┌────────────────┐ │     │ ┌────────────────┐ │                   │
│  │ │CONSUMING Seg   │ │     │ │CONSUMING Seg   │ │                   │
│  │ │ offset: 63000  │ │     │ │ offset: 41000  │ │                   │
│  │ │ rows: 15K      │ │     │ │ rows: 9K       │ │                   │
│  │ └────────────────┘ │     │ └────────────────┘ │                   │
│  └────────────────────┘     └────────────────────┘                   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

### Consumer Types in Pinot

Pinot supports two consumer types for Kafka:

#### LowLevel Consumer (RECOMMENDED for Production)

```
┌─────────────────────────────────────────────────────────────────┐
│  LowLevel Consumer (LLC) — Default & Recommended                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • 1:1 mapping between Kafka partition and Pinot server         │
│  • Each Pinot server directly consumes assigned partitions      │
│  • No Kafka consumer group coordination overhead                │
│  • Controller manages partition-to-server assignment            │
│  • Offsets stored in ZooKeeper (Pinot-managed, not Kafka)       │
│  • Supports exactly-once consumption semantics                  │
│  • Automatic failover: another server picks up partition        │
│                                                                 │
│  Kafka P0 ──────────→ Pinot Server 1                           │
│  Kafka P1 ──────────→ Pinot Server 2                           │
│  Kafka P2 ──────────→ Pinot Server 3                           │
│  Kafka P3 ──────────→ Pinot Server 1 (wraps around)            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### HighLevel Consumer (DEPRECATED)

```
┌─────────────────────────────────────────────────────────────────┐
│  HighLevel Consumer (HLC) — DEPRECATED, Do Not Use              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • Uses Kafka consumer group for coordination                   │
│  • Kafka decides partition assignment (less control)            │
│  • All servers in same consumer group                           │
│  • Rebalancing triggers Kafka group rebalance                   │
│  • Less predictable behavior under failures                    │
│  • No longer recommended for any use case                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Detailed Consumption Flow (LowLevel Consumer)

```
Step-by-Step: What happens when Pinot consumes from Kafka

═══════════════════════════════════════════════════════════════════

STEP 1: Table Creation
─────────────────────
Controller receives CREATE REALTIME TABLE request
  → Reads Kafka topic metadata (partition count, broker list)
  → Computes partition-to-server assignment
  → Creates IdealState in ZooKeeper:
      Segment "table__0__0__20260528T0000Z" → Server1 (CONSUMING)
      Segment "table__1__0__20260528T0000Z" → Server2 (CONSUMING)
      Segment "table__2__0__20260528T0000Z" → Server3 (CONSUMING)

═══════════════════════════════════════════════════════════════════

STEP 2: Server Starts Consuming
────────────────────────────────
Each assigned server:
  → Creates a Kafka SimpleConsumer (not consumer group)
  → Seeks to the start offset (from ZK or configured reset strategy)
  → Begins polling Kafka in a tight loop

  while (segment not sealed):
      records = kafkaConsumer.poll(timeout=100ms)
      for record in records:
          decodedRow = decoder.decode(record)     // Avro/JSON/Protobuf
          transformedRow = transformer.transform(decodedRow)
          mutableIndex.addRow(transformedRow)     // In-memory forward index
          currentOffset = record.offset
          rowCount++

═══════════════════════════════════════════════════════════════════

STEP 3: Seal Condition Check (Every Poll Cycle)
───────────────────────────────────────────────
After each batch of records:
  if (rowCount >= maxRowsPerSegment          // Default: 5,000,000
      OR timeSinceCreation >= maxTimePerSegment  // Default: 24h
      OR memoryUsage >= maxSegmentSize):     // Configurable bytes
      
      → TRIGGER SEGMENT COMPLETION PROTOCOL

═══════════════════════════════════════════════════════════════════

STEP 4: Segment Completion Protocol
────────────────────────────────────
Server → Controller: "I want to commit segment X at offset Y"

Controller checks:
  • Is this the latest segment for this partition? YES → proceed
  • Is the offset valid? (no gaps, no duplicates) YES → proceed

Controller → Server: "OK, build and upload the segment"

Server:
  1. Stops consuming from Kafka
  2. Builds columnar segment from in-memory data:
     - Creates forward indexes (sorted/unsorted)
     - Builds inverted indexes
     - Builds range indexes
     - Builds star-tree (if configured)
     - Compresses columns (LZ4/Snappy/ZSTD)
     - Writes metadata (min/max, cardinality, row count)
  3. Writes segment to local disk as .tar.gz
  4. Uploads to deep store (S3/HDFS/GCS/ADLS)
  5. Notifies controller: "Upload complete"

Controller:
  1. Updates ZooKeeper IdealState:
     Old: Segment "table__0__0__ts" → Server1 (CONSUMING)
     New: Segment "table__0__0__ts" → Server1 (ONLINE)
  2. Creates NEW CONSUMING segment:
     Segment "table__0__1__ts" → Server1 (CONSUMING)
     Start offset = previous segment end offset + 1

Server:
  1. Transitions old segment state: CONSUMING → ONLINE
  2. Creates new CONSUMING segment
  3. Resumes consuming from Kafka at new offset

═══════════════════════════════════════════════════════════════════

STEP 5: Query During Consumption
────────────────────────────────
Broker receives query:
  → Routes to servers hosting relevant segments
  → Server queries BOTH:
      • ONLINE segments (fast, indexed, compressed)
      • CONSUMING segments (slower, in-memory, partial index)
  → Merges results and returns to broker
  → Broker aggregates across all servers and returns to client
```

---

## ⚙️ Configuration Deep Dive

### Real-Time Table Configuration

```json
{
  "tableName": "user_events_REALTIME",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "schemaName": "user_events",
    "replication": "3",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "30",
    "completionConfig": {
      "completionMode": "DOWNLOAD"
    }
  },
  "tableIndexConfig": {
    "loadMode": "MMAP",
    "streamConfigs": {
      "streamType": "kafka",
      "stream.kafka.topic.name": "user-events",
      "stream.kafka.broker.list": "kafka-1:9092,kafka-2:9092,kafka-3:9092",
      "stream.kafka.consumer.type": "lowlevel",
      "stream.kafka.consumer.factory.class.name": "org.apache.pinot.plugin.stream.kafka20.KafkaConsumerFactory",
      "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaJSONMessageDecoder",
      "stream.kafka.consumer.prop.auto.offset.reset": "smallest",
      
      "realtime.segment.flush.threshold.rows": "500000",
      "realtime.segment.flush.threshold.time": "6h",
      "realtime.segment.flush.threshold.segment.size": "200M",
      
      "stream.kafka.consumer.prop.security.protocol": "SASL_SSL",
      "stream.kafka.consumer.prop.sasl.mechanism": "PLAIN",
      "stream.kafka.consumer.prop.sasl.jaas.config": "..."
    }
  },
  "tenants": {
    "broker": "DefaultTenant",
    "server": "DefaultTenant"
  },
  "metadata": {
    "customConfigs": {}
  }
}
```

### Critical StreamConfig Parameters

| Parameter | Default | Production Recommendation | Purpose |
|-----------|---------|--------------------------|---------|
| `realtime.segment.flush.threshold.rows` | 5,000,000 | 100K–500K | Rows before seal |
| `realtime.segment.flush.threshold.time` | 24h | 1h–6h | Time before seal |
| `realtime.segment.flush.threshold.segment.size` | 200MB | 100MB–500MB | Size before seal |
| `stream.kafka.consumer.prop.auto.offset.reset` | largest | `smallest` for new tables | Where to start |
| `realtime.segment.flush.autotune.initialRows` | 100000 | Tune per use case | Autotuning seed |
| `stream.kafka.fetch.timeout.millis` | 5000 | 5000–10000 | Kafka poll timeout |

---

## 🔄 Segment Completion Modes

### Mode 1: DOWNLOAD (Default, Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│  DOWNLOAD Completion Mode                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Server-1 (leader) builds + uploads segment to deep store    │
│  2. Controller notifies Server-2, Server-3 (replicas)           │
│  3. Replicas DOWNLOAD the segment from deep store               │
│  4. All replicas have identical segment (byte-for-byte same)    │
│                                                                 │
│  Pros:                                                          │
│  • Segments are byte-identical across replicas                  │
│  • Deep store is always consistent                              │
│  • One server does the expensive build work                     │
│                                                                 │
│  Cons:                                                          │
│  • Network bandwidth for download from deep store               │
│  • Slight delay before replicas have the segment                │
│                                                                 │
│  Server-1 (Leader):                                             │
│  [CONSUMING] → Build → Upload to S3 → [ONLINE]                 │
│                                                                 │
│  Server-2 (Replica):                                            │
│  [CONSUMING] → Wait → Download from S3 → [ONLINE]              │
│                                                                 │
│  Server-3 (Replica):                                            │
│  [CONSUMING] → Wait → Download from S3 → [ONLINE]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Mode 2: DEFAULT (Each server builds independently)

```
┌─────────────────────────────────────────────────────────────────┐
│  DEFAULT Completion Mode                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Each server independently seals its CONSUMING segment       │
│  2. Each server builds its own segment from its local data      │
│  3. Leader uploads to deep store                                │
│                                                                 │
│  Pros:                                                          │
│  • No download step — faster segment availability               │
│                                                                 │
│  Cons:                                                          │
│  • Segments MAY differ across replicas (timing differences)     │
│  • More CPU usage (N builds instead of 1)                       │
│  • Harder to debug inconsistencies                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Offset Management

### How Pinot Tracks Kafka Offsets

```
┌─────────────────────────────────────────────────────────────────┐
│  Offset Storage: ZooKeeper (NOT Kafka __consumer_offsets)        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ZooKeeper Path:                                                │
│  /PinotCluster/SEGMENTS/tableName_REALTIME/                     │
│    segment_name → {                                             │
│      "startOffset": 50000,                                      │
│      "endOffset": 100000,                                       │
│      "status": "DONE",                                          │
│      "downloadUrl": "s3://bucket/segments/..."                  │
│    }                                                            │
│                                                                 │
│  For CONSUMING segments:                                        │
│  /PinotCluster/SEGMENTS/tableName_REALTIME/                     │
│    consuming_segment → {                                        │
│      "startOffset": 100001,                                     │
│      "currentOffset": 125000,    ← Updated periodically        │
│      "status": "IN_PROGRESS"                                    │
│    }                                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Offset Reset Strategies

| Strategy | When Used | Behavior |
|----------|-----------|----------|
| `smallest` | New table, first consumption | Start from beginning of topic |
| `largest` | Skip historical data | Start from latest offset |
| Stored offset | Normal operation | Resume from last committed offset |
| Specific offset | Manual recovery | Force start from specific offset |

### What Happens on Server Crash?

```
SCENARIO: Server-1 crashes while consuming partition 0

Timeline:
─────────────────────────────────────────────────────────────

T=0:  Server-1 consuming P0, offset at 75,000
      Last committed segment ended at offset 50,000
      (CONSUMING segment has rows from 50,001 → 75,000)

T=1:  Server-1 CRASHES
      • CONSUMING segment (50,001→75,000) is LOST (was in memory)
      • Last committed offset in ZK: 50,000

T=2:  Controller detects Server-1 is down (via ZK session timeout)
      • Reassigns P0 to Server-2

T=3:  Server-2 picks up P0
      • Reads last committed offset from ZK: 50,000
      • Creates new CONSUMING segment starting at offset 50,001
      • RE-CONSUMES records 50,001 → 75,000 from Kafka
      • Continues consuming from 75,001 onward

T=4:  NO DATA LOSS — Kafka retained the messages
      • Kafka retention must be > time to recover

─────────────────────────────────────────────────────────────

CRITICAL REQUIREMENT:
  Kafka retention period MUST be longer than:
  - Maximum time between segment commits
  - Time to detect failure + reassign + replay

  If Kafka retention = 7 days and segment flush time = 6h:
  → Safe: Can recover up to 7 days of uncommitted data
  
  If Kafka retention = 1 hour and segment flush time = 6h:
  → DANGEROUS: Data loss if crash happens after 1h of consuming
```

---

## 📊 Memory Model of a CONSUMING Segment

```
┌─────────────────────────────────────────────────────────────────┐
│  In-Memory Structure of a CONSUMING Segment                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  MutableSegmentImpl                                      │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Forward Index (per column)                       │   │    │
│  │  │  ┌────────────┐  ┌────────────┐  ┌───────────┐  │   │    │
│  │  │  │FixedByte   │  │VarByte     │  │Dictionary │  │   │    │
│  │  │  │SingleValue │  │MultiValue  │  │(optional) │  │   │    │
│  │  │  │Buffer      │  │Buffer      │  │           │  │   │    │
│  │  │  └────────────┘  └────────────┘  └───────────┘  │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  RealtimeInvertedIndex (per indexed column)       │   │    │
│  │  │  • Built on-the-fly as records arrive             │   │    │
│  │  │  • ConcurrentHashMap<Value, RoaringBitmap>        │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Metadata                                         │   │    │
│  │  │  • numDocs (current row count)                    │   │    │
│  │  │  • startOffset / currentOffset                    │   │    │
│  │  │  • creationTime                                   │   │    │
│  │  │  • minValues / maxValues per column               │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Memory Allocation:                                             │
│  • Off-heap: Column data buffers (configurable)                 │
│  • On-heap: Inverted indexes, metadata, dictionary              │
│  • Typical size: 50MB – 500MB per consuming segment             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏭 Production Real-World Use Cases

### Use Case 1: Real-Time User Analytics Dashboard (LinkedIn-Scale)

```
SCENARIO: 800M+ users, showing "Who viewed your profile" in real-time

Architecture:
─────────────────────────────────────────────────────────────────

Producers:
  • LinkedIn app servers emit profile_view events
  • Event: {viewer_id, profile_id, timestamp, device, geo, session_id}
  • Volume: ~2M events/second peak

Kafka:
  • Topic: profile-views
  • Partitions: 128 (based on profile_id hash)
  • Retention: 7 days
  • Replication: 3

Pinot Real-Time Table:
  • 32 Pinot servers, each consuming 4 partitions
  • Segment flush: 500K rows OR 1 hour
  • Replication: 2 (for HA)
  • Retention: 90 days

Query Pattern:
  SELECT viewer_id, timestamp, device, geo
  FROM profile_views
  WHERE profile_id = '12345'
    AND timestamp > NOW() - 7 DAYS
  ORDER BY timestamp DESC
  LIMIT 50

  → Response time: P99 < 50ms
  → Serves directly to user-facing product

Production Considerations:
  • Star-tree index on (profile_id, device, geo) for aggregation queries
  • Inverted index on profile_id for point lookups
  • Sorted index on timestamp for range scans
  • Tiered storage: hot (7 days SSD) → warm (90 days HDD/S3)
```

---

### Use Case 2: Real-Time Anomaly Detection (Uber-Scale)

```
SCENARIO: Detecting ride pricing anomalies across 10K+ cities

Architecture:
─────────────────────────────────────────────────────────────────

Producers:
  • Trip completion events from ride services
  • Event: {trip_id, city, fare, distance, duration, surge_mult, ts}
  • Volume: ~500K events/second

Kafka:
  • Topic: trip-completed
  • Partitions: 64 (based on city hash)
  • Retention: 3 days

Pinot Real-Time Table:
  • 16 servers, 4 partitions each
  • Segment flush: 200K rows OR 30 minutes (fast seal for freshness)
  • Star-tree: pre-aggregated on (city, hour) for AVG/P95 fare

Anomaly Detection Query (runs every minute):
  SELECT city,
         AVG(fare) as avg_fare,
         PERCENTILE(fare, 95) as p95_fare,
         COUNT(*) as trip_count
  FROM trip_completed
  WHERE ts > NOW() - 1 HOUR
  GROUP BY city
  HAVING AVG(fare) > 2 * historical_avg  -- anomaly threshold

  → Feeds into alerting system
  → Triggers investigation if city fare pattern deviates

Production Considerations:
  • Low flush threshold (30 min) for data freshness
  • Star-tree critical for pre-aggregated city-level metrics
  • Upsert NOT used — pure append model
  • Separate OFFLINE table for historical baselines (30-day windows)
```

---

### Use Case 3: Ad-Tech Real-Time Bidding Analytics (Stripe/Pinterest-Scale)

```
SCENARIO: Real-time campaign performance for advertisers

Architecture:
─────────────────────────────────────────────────────────────────

Producers:
  • Ad impression, click, conversion events
  • Events: {campaign_id, ad_id, user_segment, bid_price, 
             impression_ts, click_ts, conversion_ts, revenue}
  • Volume: ~5M impressions/second, ~100K clicks/second

Kafka Topics:
  • ad-impressions (256 partitions)
  • ad-clicks (64 partitions)  
  • ad-conversions (32 partitions)

Pinot Tables:
  • impressions_REALTIME (64 servers)
  • clicks_REALTIME (16 servers)
  • conversions_REALTIME (8 servers)

Advertiser Dashboard Query:
  SELECT ad_id,
         COUNT(*) as impressions,
         SUM(CASE WHEN click_ts IS NOT NULL THEN 1 ELSE 0 END) as clicks,
         SUM(revenue) as total_revenue,
         SUM(revenue) / COUNT(*) as eCPM
  FROM impressions
  WHERE campaign_id = 'camp_123'
    AND impression_ts > NOW() - 24 HOURS
  GROUP BY ad_id
  ORDER BY total_revenue DESC

  → P99 < 100ms for advertiser-facing dashboards
  → Refreshes every 30 seconds in UI

Production Considerations:
  • Very high partition count for impressions (high volume)
  • Different retention per table (impressions: 7d, clicks: 30d, conversions: 90d)
  • Multi-value columns for user_segment (array of segment IDs)
  • Bloom filter on campaign_id for fast filtering
  • Range index on impression_ts for time-range queries
```

---

### Use Case 4: Real-Time Infrastructure Monitoring (Datadog-Scale)

```
SCENARIO: Metrics ingestion and querying across 100K+ hosts

Architecture:
─────────────────────────────────────────────────────────────────

Producers:
  • Agents on customer infrastructure emit metric data points
  • Event: {host, metric_name, value, tags[], timestamp}
  • Volume: ~10M data points/second
  • Cardinality: 500K unique metric names, 100K hosts

Kafka:
  • Topic: metrics-ingest
  • Partitions: 512 (based on host hash for locality)
  • Retention: 48 hours (Pinot catches up within hours)

Pinot Real-Time Table:
  • 128 servers, 4 partitions each
  • Segment flush: 1M rows OR 15 minutes (aggressive for freshness)
  • Off-heap memory for column buffers (high volume = big segments)

Dashboard Query:
  SELECT DATETIMECONVERT(timestamp, '1:MILLISECONDS:EPOCH', 
                         '1:MINUTES:EPOCH', '1:MINUTES') as minute_bucket,
         AVG(value) as avg_value,
         MAX(value) as max_value,
         PERCENTILE(value, 99) as p99_value
  FROM metrics
  WHERE metric_name = 'cpu.usage'
    AND host IN ('host-001', 'host-002', 'host-003')
    AND timestamp > NOW() - 6 HOURS
  GROUP BY minute_bucket
  ORDER BY minute_bucket

Production Considerations:
  • Star-tree on (metric_name, host) → 100x faster aggregations
  • TEXT index on tags[] for tag-based filtering
  • Very aggressive segment flush (15 min) for monitoring freshness
  • Tiered storage: 6h hot (memory), 7d warm (SSD), 30d cold (S3)
  • Sorted column on timestamp for optimal time-range queries
```

---

## 🚨 Production Considerations (Complete Checklist)

### 1. Memory Sizing

```
FORMULA: Memory per server for consuming segments

memory_per_server = 
  num_partitions_per_server 
  × avg_rows_per_segment 
  × avg_row_size_bytes 
  × 1.3 (overhead factor for indexes)

EXAMPLE:
  4 partitions × 500K rows × 200 bytes × 1.3 = ~520MB per server

CRITICAL RULES:
  • Reserve 30-40% of heap for consuming segments
  • Use off-heap (DirectByteBuffer) for column data if heap pressure is high
  • Monitor GC pauses — large consuming segments cause long GC
  • If OOM occurs, CONSUMING segments are lost (recovered from Kafka)

CONFIGURATION:
  -Xmx16g -Xms16g                          # Fixed heap
  -XX:MaxDirectMemorySize=32g               # Off-heap for mmap + consuming
  pinot.server.instance.realtime.alloc.offheap=true  # Off-heap columns
```

---

### 2. Consumer Lag Monitoring

```
CRITICAL METRIC: Kafka consumer lag per partition

What is consumer lag?
  lag = Kafka latest offset - Pinot current consuming offset

Why it matters:
  • High lag = Pinot is falling behind Kafka
  • Data freshness degrades (queries return stale results)
  • If lag > Kafka retention, DATA LOSS occurs!

Monitoring Setup:
  ┌──────────────────────────────────────────────────────┐
  │  Metrics to track:                                    │
  │                                                      │
  │  pinot.server.realtimeConsumptionCatchupTimeMs       │
  │  pinot.server.kafkaPartitionOffset.lag               │
  │  pinot.server.currentOffset.tableName.partition      │
  │  pinot.server.highWaterMarkOffset.tableName.partition │
  └──────────────────────────────────────────────────────┘

Alert Thresholds:
  • WARN:  lag > 10,000 records (configurable)
  • CRITICAL: lag > 100,000 records
  • EMERGENCY: lag approaching Kafka retention limit

Common Causes of Lag:
  1. Slow deserialization (complex Avro schemas, large messages)
  2. Insufficient server resources (CPU/memory)
  3. Too few servers for partition count
  4. GC pauses during segment building
  5. Slow deep store uploads blocking new consumption
  6. Kafka broker issues (slow fetch responses)

Remediation:
  • Add more Pinot servers → spread partitions
  • Increase Kafka partitions → more parallelism
  • Reduce segment flush threshold → smaller segments, faster builds
  • Use off-heap memory → reduce GC pressure
  • Tune Kafka fetch size → larger batches
```

---

### 3. Segment Flush Tuning

```
THE TRADEOFF:

  Small segments (flush quickly):
    ✅ Better data freshness (queries see recent data sooner)
    ✅ Less memory usage per consuming segment
    ✅ Faster crash recovery (less to replay from Kafka)
    ❌ More segments on disk (query planning overhead)
    ❌ More segment builds/uploads (CPU + network)
    ❌ More ZooKeeper metadata

  Large segments (flush slowly):
    ✅ Fewer segments (better query performance)
    ✅ Better compression ratios
    ✅ Less segment management overhead
    ❌ Higher memory usage
    ❌ Longer crash recovery time
    ❌ Less fresh data for queries

RECOMMENDED PRODUCTION SETTINGS:

  Use case                    | Rows    | Time  | Notes
  ─────────────────────────────────────────────────────────
  User-facing dashboards      | 100K    | 1h    | Freshness critical
  Monitoring/alerting         | 200K    | 15min | Very fresh data needed
  Analytics (non-real-time)   | 500K    | 6h    | Balance size/freshness
  Batch-like streaming        | 1M      | 24h   | Throughput priority
  High-cardinality metrics    | 50K     | 30min | Small for memory safety

AUTOTUNING:
  Pinot 0.12+ supports automatic segment size tuning:
  "realtime.segment.flush.threshold.segment.size": "200M"
  → Pinot adjusts row count to hit target segment size
  → Recommended for variable-size records
```

---

### 4. Replication and High Availability

```
REPLICATION CONFIGURATION:

  "segmentsConfig": {
    "replication": "3"    // Number of replicas per segment
  }

HOW REPLICATION WORKS FOR REAL-TIME:

  With replication=3 and completionMode=DOWNLOAD:

  1. ALL 3 replicas independently consume from Kafka
     (Each maintains its own CONSUMING segment)

  2. When seal is triggered:
     • Leader (first in ideal state) builds and uploads segment
     • Other replicas stop consuming
     • Other replicas download built segment from deep store

  3. Result: All 3 servers have identical ONLINE segment

  ┌─────────┐     ┌─────────┐     ┌─────────┐
  │Server-1 │     │Server-2 │     │Server-3 │
  │(Leader) │     │(Replica)│     │(Replica)│
  ├─────────┤     ├─────────┤     ├─────────┤
  │CONSUMING│     │CONSUMING│     │CONSUMING│
  │(active) │     │(active) │     │(active) │
  │offset:5K│     │offset:5K│     │offset:5K│
  └────┬────┘     └────┬────┘     └────┬────┘
       │ SEAL          │               │
       ▼               ▼               ▼
  ┌─────────┐     ┌─────────┐     ┌─────────┐
  │ BUILD   │     │  WAIT   │     │  WAIT   │
  │ UPLOAD  │     │         │     │         │
  │ to S3   │     │         │     │         │
  └────┬────┘     └────┬────┘     └────┬────┘
       │               │DOWNLOAD       │DOWNLOAD
       ▼               ▼               ▼
  ┌─────────┐     ┌─────────┐     ┌─────────┐
  │ ONLINE  │     │ ONLINE  │     │ ONLINE  │
  │(identical segments on all 3)                │
  └─────────┘     └─────────┘     └─────────┘

FAILURE SCENARIOS:

  Server-1 dies while CONSUMING:
  → Controller reassigns partition to Server-4
  → Server-4 replays from last committed offset
  → No data loss (Kafka has the records)

  Server-1 dies during segment BUILD:
  → Controller times out waiting for commit
  → Picks another replica as leader
  → New leader builds from its CONSUMING data

  Deep store upload fails:
  → Server retries with exponential backoff
  → If persistent failure, segment stays ONLINE locally
  → Alert fires for deep store health check
```

---

### 5. Exactly-Once Semantics

```
PINOT'S GUARANTEE: At-least-once delivery (not exactly-once)

WHY:
  • Pinot re-reads from Kafka on crash recovery
  • Records between last commit and crash are replayed
  • Some records may appear in BOTH the committed segment AND replayed data

HOW DUPLICATES HAPPEN:

  Time 0: Consuming at offset 5000
  Time 1: Segment sealed at offset 10000, but upload in progress
  Time 2: Server CRASHES before upload completes
  Time 3: New server replays from offset 5001 (last committed: 5000)
  
  Records 5001-10000 are now in BOTH:
  • The partially-committed segment (if it was uploaded)
  • The new consuming segment (re-consumed from Kafka)

SOLUTIONS:

  1. Upsert Mode (Best for mutable data):
     • Deduplicates by primary key
     • Latest record wins (by comparison column)
     • Additional memory overhead for primary key index
     
  2. Dedup at Query Time:
     • Use GROUP BY primary_key with MAX(timestamp)
     • Higher query cost but no ingestion overhead
     
  3. Idempotent Producers + Dedup:
     • Kafka exactly-once (idempotent producer + transactions)
     • Pinot still re-reads, but Kafka guarantees no source duplicates
     
  4. Accept Duplicates:
     • For metrics/aggregations, minor over-counting is acceptable
     • SUM of impressions off by 0.01% is usually fine
     • Simplest operationally
```

---

### 6. Schema Evolution

```
SCENARIO: Adding a new column to a table already consuming from Kafka

SAFE OPERATIONS (No downtime):
  ✅ Add new nullable column
  ✅ Add column with default value
  ✅ Add new index on existing column (reload required)
  
UNSAFE OPERATIONS (Requires careful migration):
  ❌ Remove a column (existing segments still have it)
  ❌ Change column type (incompatible formats)
  ❌ Rename a column (new name won't match existing segments)

PROCEDURE TO ADD COLUMN:

  Step 1: Update Pinot schema (add column with default)
    POST /schemas → adds "new_field" with defaultNullValue

  Step 2: Update Avro/JSON schema in producers
    → New events include "new_field"
    → Pinot decoder handles missing field with default

  Step 3: New CONSUMING segments have the new column
    → Old ONLINE segments return default for missing column
    → Queries work transparently across old and new segments

  Step 4 (Optional): Reload old segments to add column physically
    POST /segments/{table}/{segment}/reload
```

---

### 7. Backpressure Handling

```
WHAT HAPPENS WHEN PINOT CAN'T KEEP UP WITH KAFKA?

Scenario: Kafka produces 1M msgs/sec but Pinot can only consume 500K/sec

Symptoms:
  • Consumer lag grows continuously
  • Memory usage increases (larger consuming segments)
  • Query latency increases (scanning bigger in-memory segments)
  • Eventually: OOM kills or forced segment flush

BACKPRESSURE STRATEGIES:

  1. Horizontal Scaling (Preferred):
     • Add more Pinot servers
     • Rebalance partitions across more servers
     • Each server handles less data
     
  2. Kafka Partition Increase:
     • More partitions = more parallelism
     • CAUTION: Requires Pinot table config update + rebalance
     • Can't decrease partitions later
     
  3. Reduce Processing Per Record:
     • Simplify transformation logic
     • Remove unnecessary ingestion-time transformations
     • Use simpler decoder (JSON → Avro for faster parsing)
     
  4. Rate Limiting at Source:
     • Throttle producers during peak
     • Use Kafka quotas per producer
     • Not always possible (traffic is traffic)
     
  5. Segment Size Reduction:
     • Flush smaller segments more frequently
     • Reduces memory pressure
     • Trades query performance for stability

MONITORING QUERY:
  -- Check consumption rate vs production rate
  SELECT partition,
         (latestOffset - currentOffset) as lag,
         consumptionRate as msgs_per_sec
  FROM realtimeConsumptionStatus
  WHERE tableName = 'my_table_REALTIME'
```

---

### 8. Kafka Topic Design for Pinot

```
BEST PRACTICES:

  Partition Key Selection:
  ─────────────────────────
  • CHOOSE: Partition by the most common filter/group-by column
  • WHY: Same key always goes to same Pinot server → local queries
  • EXAMPLE: If you always query by user_id, partition Kafka by user_id
  
  • AVOID: Partition by timestamp (skewed — all traffic to one partition)
  • AVOID: Random partitioning (queries hit all servers every time)
  • AVOID: Very high cardinality key with hot keys (one partition gets 50% traffic)

  Partition Count:
  ─────────────────────────
  • Rule of thumb: num_partitions = 2 × num_pinot_servers
  • Why 2x? Allows adding servers without repartitioning
  • Minimum: num_pinot_servers (so each server has work)
  • Maximum: Don't exceed 1000 (ZK overhead per partition)

  Message Format:
  ─────────────────────────
  • Avro (RECOMMENDED): Schema registry, fast decode, backward compatible
  • JSON: Simple but slow to decode, no schema enforcement
  • Protobuf: Fast decode but less tooling in Pinot ecosystem
  
  Message Size:
  ─────────────────────────
  • Ideal: < 1KB per message (Pinot is optimized for this)
  • Acceptable: 1KB – 10KB
  • Problematic: > 10KB (slow decode, memory pressure)
  • If large: Flatten/denormalize before sending to Kafka

  Compaction:
  ─────────────────────────
  • Log compaction is fine — Pinot reads sequentially
  • Compacted topics work with Pinot upsert mode
  • Don't rely on Kafka compaction for Pinot dedup (race conditions)
```

---

### 9. Monitoring Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION MONITORING: Real-Time Pinot Tables                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TIER 1 — Page immediately (P1):                                │
│  ───────────────────────────────────                            │
│  □ Consumer lag > Kafka retention threshold                     │
│  □ Server OOM / crash                                           │
│  □ Segment build failure (upload to deep store failed)          │
│  □ Zero consumption rate (consumer stalled)                     │
│  □ Query error rate > 1%                                        │
│                                                                 │
│  TIER 2 — Alert team (P2):                                      │
│  ──────────────────────────                                     │
│  □ Consumer lag growing steadily                                │
│  □ Segment build time > 5 minutes                               │
│  □ Memory usage > 80% on Pinot servers                          │
│  □ GC pauses > 2 seconds                                        │
│  □ Query P99 latency > SLA threshold                            │
│  □ Replication factor below target                              │
│                                                                 │
│  TIER 3 — Track in dashboard (P3):                              │
│  ─────────────────────────────────                              │
│  □ Records consumed per second (throughput)                     │
│  □ Active consuming segment count per server                    │
│  □ Consuming segment size (rows and bytes)                      │
│  □ Segment seal frequency                                       │
│  □ Deep store upload latency                                    │
│  □ Kafka fetch latency                                          │
│  □ Schema decode errors (malformed messages)                    │
│                                                                 │
│  PINOT METRICS TO EXPORT:                                       │
│  ─────────────────────────                                      │
│  pinot.server.consumptionLagMs                                  │
│  pinot.server.lastConsumedOffset                                │
│  pinot.server.currentOffsetsLag                                 │
│  pinot.server.realtimeRowsConsumedCount                         │
│  pinot.server.realtimeSegmentBuildTimeMs                        │
│  pinot.server.segmentUploadTimeMs                               │
│  pinot.server.numConsumingSegments                              │
│  pinot.server.realtimeConsumptionExceptions                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 10. Common Production Failures & Runbooks

```
═══════════════════════════════════════════════════════════════════
FAILURE 1: Consumer Lag Growing Unbounded
═══════════════════════════════════════════════════════════════════

Symptoms:
  • Consumer lag increasing over time
  • Data freshness degrading
  • No server crashes

Diagnosis:
  1. Check consumption rate: Is it dropping?
  2. Check Kafka produce rate: Is it spiking?
  3. Check server CPU/memory: Is it saturated?
  4. Check GC logs: Are there long pauses?
  5. Check segment build times: Are builds slow?

Fix:
  • Short-term: Reduce segment flush threshold (smaller, faster segments)
  • Medium-term: Add more servers, rebalance partitions
  • Long-term: Increase Kafka partitions + Pinot servers together

═══════════════════════════════════════════════════════════════════
FAILURE 2: Server OOM During Consumption
═══════════════════════════════════════════════════════════════════

Symptoms:
  • JVM OOM error in server logs
  • Server process dies
  • Consuming segments lost

Diagnosis:
  1. Check consuming segment size (rows × avg_row_bytes)
  2. Check number of consuming segments per server
  3. Check if off-heap is enabled
  4. Check for memory leaks (heap dump analysis)

Fix:
  • Immediate: Reduce flush threshold rows (smaller segments)
  • Enable off-heap: pinot.server.instance.realtime.alloc.offheap=true
  • Increase heap: Rarely the right answer (just delays OOM)
  • Reduce partitions per server: Add more servers

═══════════════════════════════════════════════════════════════════
FAILURE 3: Segment Build Timeout
═══════════════════════════════════════════════════════════════════

Symptoms:
  • Segment stuck in CONSUMING state past expected time
  • Controller logs show "segment commit timeout"
  • New consuming segment not created

Diagnosis:
  1. Check if build is still in progress (CPU usage high)
  2. Check deep store connectivity (S3/HDFS reachable?)
  3. Check disk space on server (temp build space)
  4. Check if star-tree build is taking too long

Fix:
  • Increase commit timeout: realtime.segment.commit.timeoutMs
  • Reduce segment size (fewer rows = faster build)
  • Disable complex indexes during build if not needed
  • Check and fix deep store connectivity
  • Restart the stuck server (last resort — triggers replay)

═══════════════════════════════════════════════════════════════════
FAILURE 4: Kafka Connection Lost
═══════════════════════════════════════════════════════════════════

Symptoms:
  • "Failed to fetch from Kafka" in server logs
  • Consumer offset not advancing
  • No new records being consumed

Diagnosis:
  1. Check Kafka broker health (are brokers alive?)
  2. Check network connectivity (firewall, DNS)
  3. Check Kafka ACLs (permissions revoked?)
  4. Check SSL certificate expiry
  5. Check if topic still exists (accidental deletion?)

Fix:
  • Fix network/DNS issue
  • Renew SSL certificates
  • Restore Kafka ACLs
  • If topic deleted: recreate topic, reset offsets, reload table
  • Pinot will auto-reconnect once Kafka is reachable

═══════════════════════════════════════════════════════════════════
FAILURE 5: Duplicate Records After Recovery
═══════════════════════════════════════════════════════════════════

Symptoms:
  • COUNT(*) higher than expected after server recovery
  • SUM values slightly inflated
  • Duplicate primary keys visible in queries

Diagnosis:
  1. Check if a server crashed during segment commit
  2. Look for overlapping offset ranges in segment metadata
  3. Verify if upsert mode is enabled

Fix:
  • If upsert is enabled: Records auto-deduplicated on query
  • If not: Accept minor duplicates OR
  • Run minion RealtimeToOfflineTask to compact and deduplicate
  • For critical accuracy: Enable upsert mode on the table
```

---

## 📐 Sizing Guide

```
INPUT PARAMETERS:
  • Messages per second from Kafka: 100,000
  • Average message size: 500 bytes
  • Kafka partitions: 32
  • Desired query freshness: < 5 minutes
  • Retention: 30 days
  • Replication: 3

CALCULATIONS:

  Data rate:
  100K msg/s × 500 bytes = 50 MB/s raw ingestion

  Per partition:
  100K / 32 = 3,125 msg/s per partition
  3,125 × 500 = 1.5 MB/s per partition

  Segment flush at 5 minutes:
  3,125 msg/s × 300s = 937,500 rows per segment
  1.5 MB/s × 300s = 450 MB per consuming segment (uncompressed)

  Servers needed (consumption):
  32 partitions / 4 partitions per server = 8 servers minimum
  × 3 replication = 24 total server instances

  Memory per server (consuming segments):
  4 partitions × 450 MB = 1.8 GB for consuming segments
  + 30% overhead = 2.34 GB
  → Need at least 8 GB heap per server (30% for consuming)

  Storage (completed segments, compressed ~4:1):
  50 MB/s × 86400 s/day × 30 days / 4 compression = ~32 TB
  × 3 replication = ~97 TB total storage

FINAL RECOMMENDATION:
  • 24 Pinot servers (8 per replication group)
  • 16 GB heap + 32 GB off-heap per server
  • 4 TB SSD per server for local segment cache
  • S3 deep store: ~100 TB provisioned
  • Kafka: 32 partitions, 7-day retention minimum
```

---

## 🎯 Summary: Key Takeaways

```
┌─────────────────────────────────────────────────────────────────┐
│  REAL-TIME SEGMENTS IN PINOT: EXECUTIVE SUMMARY                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. A real-time segment = a chunk of data being actively        │
│     ingested from Kafka (CONSUMING state) or already sealed     │
│     (ONLINE state) from a real-time table                       │
│                                                                 │
│  2. CONSUMING is the ONLY mutable state in all of Pinot         │
│     (append-only, lives in memory, not durable)                 │
│                                                                 │
│  3. LowLevel Consumer = 1:1 Kafka partition to Pinot server     │
│     (no Kafka consumer group, offsets in ZooKeeper)             │
│                                                                 │
│  4. Crash recovery = replay from Kafka using stored offsets     │
│     (Kafka retention MUST exceed max segment lifetime)          │
│                                                                 │
│  5. Segment completion = seal + build indexes + compress +      │
│     upload to deep store + notify controller + create new       │
│     consuming segment                                           │
│                                                                 │
│  6. Production must monitor: consumer lag, memory usage,        │
│     segment build time, deep store upload health, query         │
│     latency on consuming vs completed segments                  │
│                                                                 │
│  7. Tune flush thresholds based on use case:                    │
│     Fresh data needed → small, frequent segments                │
│     Query perf priority → larger, fewer segments                │
│                                                                 │
│  8. Exactly-once is NOT guaranteed out of the box.              │
│     Use upsert mode or accept at-least-once semantics.          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 References

- [Pinot Real-Time Ingestion Docs](https://docs.pinot.apache.org/basics/data-import/pinot-stream-ingestion)
- [Stream Ingestion Configuration](https://docs.pinot.apache.org/configuration-reference/table#stream-config)
- [Segment Completion Protocol](https://docs.pinot.apache.org/operators/operating-pinot/tuning/realtime)
- [Upsert Documentation](https://docs.pinot.apache.org/basics/data-import/upsert)
- [Pinot Memory Tuning](https://docs.pinot.apache.org/operators/operating-pinot/tuning/memory)
