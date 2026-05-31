# Apache Pinot - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Model & Segments](#data-model--segments)
3. [Indexing Strategies](#indexing-strategies)
4. [Real-Time Ingestion](#real-time-ingestion)
5. [Query Processing](#query-processing)
6. [Scalability & Performance](#scalability--performance)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Pinot Components
```
┌────────────────────────────────────────────────────────────┐
│                     Apache Pinot Cluster                     │
│                                                              │
│  ┌────────────────┐         ┌────────────────┐             │
│  │   Controller   │         │   Controller   │ (HA pair)    │
│  │  - Schema mgmt │         │  - Segment mgmt│             │
│  │  - Routing     │         │  - Tenant mgmt │             │
│  └───────┬────────┘         └───────┬────────┘             │
│          │                           │                       │
│          └───────────┬───────────────┘                       │
│                      │                                       │
│  ┌───────────────────┼───────────────────┐                  │
│  │                   │                    │                   │
│  ▼                   ▼                    ▼                   │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│ │  Broker  │  │  Broker  │  │  Broker  │  (Query routing)   │
│ └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│      │              │              │                          │
│      └──────────────┼──────────────┘                         │
│                     │                                        │
│  ┌──────────────────┼──────────────────┐                    │
│  ▼                  ▼                   ▼                    │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│ │  Server  │  │  Server  │  │  Server  │  (Data serving)    │
│ │(Offline) │  │(Realtime)│  │(Offline) │                    │
│ │Segments  │  │Segments  │  │Segments  │                    │
│ └──────────┘  └──────────┘  └──────────┘                    │
│                     ▲                                        │
│                     │                                        │
│ ┌──────────┐  ┌────┴─────┐                                  │
│ │  Minion  │  │  Kafka/  │  (Ingestion)                     │
│ │(Tasks)   │  │  Kinesis │                                   │
│ └──────────┘  └──────────┘                                   │
│                                                              │
│  ZooKeeper (coordination, metadata)                          │
└────────────────────────────────────────────────────────────┘
```

### Key Design Principles
```
1. Immutable segments (no in-place updates)
2. Columnar storage with rich indexing
3. Scatter-gather query execution
4. Lambda architecture (offline + real-time)
5. Sub-second query latency at high concurrency
6. Designed for user-facing analytics (not batch ETL)

Use cases:
- Real-time dashboards (LinkedIn, Uber, Stripe)
- User-facing analytics (embedded analytics)
- Anomaly detection
- Ad-hoc OLAP queries with low latency
- Site-facing metrics (showing users their data)
```

### Table Types
```
OFFLINE table:
- Data ingested from batch sources (Hadoop, Spark, S3)
- Immutable segments pushed to deep store
- Servers pull segments from deep store
- Use for: Historical data, large backfills

REALTIME table:
- Data ingested from streaming sources (Kafka, Kinesis)
- Consuming segments → completed segments
- Servers consume directly from stream
- Use for: Real-time data, low latency requirements

HYBRID table:
- Combines OFFLINE + REALTIME
- Offline for historical, realtime for recent
- Query spans both (time-based routing)
```

---

## Data Model & Segments

### Schema Definition
```json
{
  "schemaName": "events",
  "dimensionFieldSpecs": [
    { "name": "user_id", "dataType": "LONG" },
    { "name": "event_type", "dataType": "STRING" },
    { "name": "country", "dataType": "STRING" },
    { "name": "device", "dataType": "STRING" },
    { "name": "tags", "dataType": "STRING", "singleValueField": false }
  ],
  "metricFieldSpecs": [
    { "name": "amount", "dataType": "DOUBLE" },
    { "name": "duration_ms", "dataType": "LONG" }
  ],
  "dateTimeFieldSpecs": [
    {
      "name": "event_time",
      "dataType": "TIMESTAMP",
      "format": "1:MILLISECONDS:EPOCH",
      "granularity": "1:MILLISECONDS"
    }
  ]
}
```

### Segment Structure
```
Segment (immutable columnar unit):
├── Metadata (creation time, row count, CRC)
├── Forward Index (column values by docId)
│   ├── Dictionary-encoded (default for strings)
│   │   Dictionary: [0→"click", 1→"view", 2→"purchase"]
│   │   Forward:    [0, 1, 0, 2, 1, 0, ...]  (dictIds per row)
│   ├── Raw (no dictionary, for high-cardinality)
│   └── Sorted (for sorted columns, run-length encoded)
├── Inverted Index (docIds by value)
│   "click"    → [0, 2, 5, 8, ...]
│   "view"     → [1, 4, 7, ...]
│   "purchase" → [3, 6, 9, ...]
├── Range Index (for numeric range queries)
├── Star-Tree Index (pre-aggregated)
├── Bloom Filter (membership test)
└── Text Index (Lucene-based full-text)
```

---

## Indexing Strategies

### Available Index Types
```
1. Forward Index (always present):
   - Dictionary-encoded: Column → DictId → DocIds
   - Raw: Directly stores values
   - Sorted: Run-length encoded sorted column

2. Inverted Index:
   - Bitmap-based inverted index
   - Perfect for: Low-medium cardinality filtering (country, status)
   - CREATE INDEX: "invertedIndexColumns": ["country", "event_type"]

3. Range Index:
   - For numeric/time range queries
   - "rangeIndexColumns": ["amount", "event_time"]
   
4. Star-Tree Index (unique to Pinot):
   - Pre-aggregated index for common query patterns
   - Answers aggregation queries in O(1) time!
   - Configurable dimensions and metrics

5. Text Index (Lucene):
   - Full-text search within Pinot
   - "textIndexColumns": ["description"]
   
6. JSON Index:
   - Index nested JSON fields
   - "jsonIndexColumns": ["properties"]

7. Bloom Filter:
   - Fast negative lookup (not exists)
   - "bloomFilterColumns": ["user_id"]

8. Geospatial Index:
   - H3-based spatial indexing
   - "h3IndexColumns": [{"name": "location", "resolution": 7}]
```

### Star-Tree Index (Pinot's Secret Weapon)
```
Star-Tree pre-computes aggregations at various granularities:

Configuration:
"starTreeIndexConfigs": [{
    "dimensionsSplitOrder": ["country", "device", "event_type"],
    "skipStarNodeCreationForDimensions": [],
    "functionColumnPairs": ["SUM__amount", "COUNT__*"],
    "maxLeafRecords": 10000
}]

Structure (conceptual):
                         [* , * , *]  → sum=1000000, count=50000
                        /     |      \
               [US, *, *]  [UK, *, *]  [IN, *, *]
              /    |    \
    [US,Mobile,*] [US,Desktop,*] [US,Tablet,*]
    /    |    \
[US,Mobile,Click] [US,Mobile,View] [US,Mobile,Purchase]

Query: SELECT SUM(amount) WHERE country='US' AND device='Mobile'
→ Directly reads pre-aggregated node: O(1) !
→ No scanning of raw rows needed

When Star-Tree helps:
- Aggregation queries with GROUP BY on indexed dimensions
- High-cardinality tables where full scan is expensive
- Dashboard queries with known dimension combinations
```

---

## Real-Time Ingestion

### Kafka Integration
```json
{
  "tableName": "events_REALTIME",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "replication": "3",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "30",
    "completionConfig": {
      "completionMode": "DOWNLOAD"
    }
  },
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "events",
    "stream.kafka.broker.list": "kafka:9092",
    "stream.kafka.consumer.type": "lowLevel",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaJSONMessageDecoder",
    "realtime.segment.flush.threshold.rows": "500000",
    "realtime.segment.flush.threshold.time": "3600000"
  }
}
```

### Segment Lifecycle (Real-Time)
```
Kafka Partition → Pinot Server

1. CONSUMING segment: 
   - Actively consuming from Kafka
   - In-memory (mutable)
   - Queryable immediately (real-time!)
   
2. Segment completion (flush threshold reached):
   - Convert to immutable segment
   - Build indexes (inverted, star-tree, etc.)
   - Upload to deep store (S3/HDFS)
   
3. COMPLETED segment:
   - Immutable, optimized for queries
   - Loaded from deep store by assigned servers

Consumer assignment:
- Low-level consumer: Each server consumes specific Kafka partitions
- Pinot maps: Kafka partition → Pinot server (via ZooKeeper)
- Replication: Multiple servers consume same partition for redundancy
```

---

## Query Processing

### Broker Query Flow
```
Client Query
     │
     ▼
┌──────────┐
│  Broker  │
│  1. Parse SQL
│  2. Route to servers (scatter)
│  3. Merge results (gather)
│  4. Apply post-aggregation
│  5. Return to client
└────┬─────┘
     │ Scatter to relevant servers
     ├─────────────────────┐
     ▼                     ▼
┌──────────┐         ┌──────────┐
│ Server A │         │ Server B │
│ Process  │         │ Process  │
│ segments │         │ segments │
│ 1-5      │         │ 6-10     │
└──────────┘         └──────────┘
     │                     │
     └──────────┬──────────┘
                │ Gather
                ▼
          Final result

Query routing:
- Broker knows which servers have which segments
- Prunes segments based on time/partition
- Fan-out only to relevant servers
```

### SQL Support (Pinot SQL)
```sql
-- Aggregation
SELECT country, COUNT(*), SUM(amount), AVG(duration_ms)
FROM events
WHERE event_time > ago('7d')
  AND event_type = 'purchase'
GROUP BY country
ORDER BY COUNT(*) DESC
LIMIT 10;

-- DISTINCT count (approximate)
SELECT DISTINCTCOUNTHLL(user_id) AS unique_users
FROM events
WHERE event_time BETWEEN 1706000000000 AND 1706100000000;

-- Multi-value columns
SELECT tags, COUNT(*)
FROM events
WHERE tags IN ('premium', 'returning')
GROUP BY tags;

-- JSON extraction
SELECT JSON_EXTRACT_SCALAR(properties, '$.referrer', 'STRING') AS referrer,
       COUNT(*)
FROM events
GROUP BY referrer;

-- Percentiles
SELECT PERCENTILEEST(duration_ms, 95) AS p95,
       PERCENTILEEST(duration_ms, 99) AS p99
FROM events;
```

---

## Scalability & Performance

### Performance Characteristics
```
Typical benchmarks (user-facing analytics):
- Query latency: 10-100ms (P95) for aggregation queries
- Concurrency: 1000+ QPS per broker
- Ingestion: 100K-1M events/sec per server
- Scan rate: 1M-10M rows/sec per segment per core

Scaling dimensions:
- More brokers: Handle more concurrent queries
- More servers: Handle more data / more segments
- More replicas: Handle more read throughput
- Star-tree: Reduce scan to O(1) for specific patterns
```

---

## Staff Architect Interview Questions

**Q1: When would you choose Pinot over ClickHouse or Druid?**
**A:**
- **Pinot**: User-facing analytics needing sub-100ms at 1000+ QPS, real-time from Kafka, LinkedIn/Uber scale
- **ClickHouse**: Internal analytics, fewer concurrent queries but complex SQL, better SQL support
- **Druid**: Similar to Pinot but older; Pinot has better Kafka integration and star-tree
- Pinot wins when you need: High concurrency + low latency + real-time streaming

**Q2: Explain the Star-Tree index and when it helps/hurts.**
**A:** Star-Tree pre-computes aggregations across dimension combinations at indexing time. Helps: Known aggregation patterns, high-cardinality data where scanning is expensive. Hurts: High-cardinality dimensions (tree explodes), many metrics (storage overhead), queries not matching configured dimensions. Trade-off: Storage space + ingestion time vs. query latency.

**Q3: How does Pinot handle late-arriving data in real-time tables?**
**A:** Options:
1. Upsert tables: Newer records with same primary key replace older
2. HYBRID table: Realtime for recent + offline batch corrections for historical
3. Segment replacement: Re-push corrected offline segments
4. Dedup: Configure deduplication at ingestion level

---

## Scenario-Based Questions

### Scenario 1: User-Facing Analytics for 100M Users

**Problem:** Show each user their activity metrics (last 30 days) with <100ms latency.

**Design:**
```
Schema:
- Partition by user_id (ensures data locality)
- Sort by event_time within partition
- Star-tree on common aggregation dimensions

Table config:
- HYBRID: Realtime (last 24h from Kafka) + Offline (historical)
- Replication: 3 (for read throughput)
- Retention: 30 days

Query pattern:
SELECT event_type, COUNT(*), SUM(amount)
FROM user_events
WHERE user_id = :id AND event_time > ago('30d')
GROUP BY event_type;

Expected: <50ms per query, 10K QPS supported

Cluster sizing:
- 6 brokers (query routing, 2K QPS each)
- 12 servers (3 replicas of 4 shards)
- Deep store: S3
- Kafka: 32 partitions for ingestion parallelism
```

