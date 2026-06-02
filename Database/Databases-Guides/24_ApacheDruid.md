# Apache Druid - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Node Types & Cluster Architecture](#node-types--cluster-architecture)
3. [Storage Engine & Segments](#storage-engine--segments)
4. [Data Ingestion](#data-ingestion)
5. [Query Engine & SQL](#query-engine--sql)
6. [Deep Storage & Metadata](#deep-storage--metadata)
7. [Real-Time Ingestion Deep Dive](#real-time-ingestion-deep-dive)
8. [Data Retention & Tiering](#data-retention--tiering)
9. [High Availability & Scaling](#high-availability--scaling)
10. [Performance Optimization](#performance-optimization)
11. [Production Deployment Patterns](#production-deployment-patterns)
12. [Security & Multi-tenancy](#security--multi-tenancy)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is Apache Druid?
```
Apache Druid is a real-time analytics database designed for sub-second
OLAP queries on event-driven data. It combines ideas from data warehouses,
timeseries databases, and search systems.

Key characteristics:
- Sub-second queries on billions of rows
- Real-time ingestion (seconds latency from event to query)
- Column-oriented storage with bitmap indexes
- Automatic rollup (pre-aggregation at ingest time)
- Time-based partitioning with segment architecture
- Designed for slice-and-dice analytics (filter, group by, aggregate)
- High concurrency (1000s of simultaneous queries)
- Independent scaling of ingestion, storage, and query

NOT designed for:
- Point lookups by primary key (use KV store)
- Full-text search (use Elasticsearch)
- Joins across large tables (use Spark/Presto)
- OLTP workloads (updates, transactions)
- Small datasets (< 1M rows - overkill)

Comparison:
┌────────────────────┬────────────┬──────────────┬──────────────┬────────────┐
│                    │ Druid      │ ClickHouse   │ Apache Pinot │ Redshift   │
├────────────────────┼────────────┼──────────────┼──────────────┼────────────┤
│ Query Latency      │ <1s (p99)  │ <1s          │ <1s          │ Seconds    │
│ Realtime Ingest    │ Yes (secs) │ Yes (secs)   │ Yes (secs)   │ Minutes    │
│ Concurrency        │ 1000+      │ 100-200      │ 1000+        │ 50-500     │
│ Exactly-once       │ Yes (Kafka)│ At-least-once│ Yes (Kafka)  │ N/A        │
│ Pre-aggregation    │ Rollup     │ No           │ Star-tree    │ No         │
│ Joins              │ Limited    │ Full SQL     │ Limited      │ Full SQL   │
│ Storage Format     │ Segments   │ Parts/Cols   │ Segments     │ Columnar   │
│ Operational        │ Complex    │ Moderate     │ Complex      │ Managed    │
│ Best For           │ Ad-tech,   │ Log analysis,│ User-facing  │ BI/Report  │
│                    │ monitoring │ analytics    │ analytics    │            │
└────────────────────┴────────────┴──────────────┴──────────────┴────────────┘
```

### Full Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        APACHE DRUID CLUSTER ARCHITECTURE                          │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         MASTER TIER                                         │ │
│  │                                                                            │ │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐               │ │
│  │  │      COORDINATOR        │    │       OVERLORD           │               │ │
│  │  │                         │    │                          │               │ │
│  │  │ - Manages data topology │    │ - Manages ingestion     │               │ │
│  │  │ - Assigns segments to   │    │ - Submits tasks to      │               │ │
│  │  │   Historical nodes      │    │   MiddleManagers        │               │ │
│  │  │ - Balances segment load │    │ - Task lifecycle mgmt   │               │ │
│  │  │ - Enforces retention    │    │ - Supervisor management │               │ │
│  │  │   rules (load/drop)     │    │   (Kafka consumers)     │               │ │
│  │  │ - Compaction scheduling │    │ - Parallel indexing      │               │ │
│  │  └─────────────────────────┘    └─────────────────────────┘               │ │
│  │                                                                            │ │
│  │  Often co-located on same JVM (druid.service=coordinator+overlord)        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         QUERY TIER                                          │ │
│  │                                                                            │ │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐               │ │
│  │  │        BROKER            │    │        ROUTER            │               │ │
│  │  │                         │    │                          │               │ │
│  │  │ - Receives queries      │    │ - Routes queries to     │               │ │
│  │  │ - Identifies segments   │    │   appropriate Broker    │               │ │
│  │  │   from timeline         │    │ - Load balancing         │               │ │
│  │  │ - Fan-out to Historicals│    │ - Optional (for multi-  │               │ │
│  │  │   & MiddleManagers      │    │   tier routing)         │               │ │
│  │  │ - Merges partial results│    │                          │               │ │
│  │  │ - Query caching (LRU)   │    │                          │               │ │
│  │  │ - Subquery execution    │    │                          │               │ │
│  │  └─────────────────────────┘    └─────────────────────────┘               │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         DATA TIER                                           │ │
│  │                                                                            │ │
│  │  ┌──────────────────────────────────┐  ┌────────────────────────────────┐ │ │
│  │  │          HISTORICAL              │  │       MIDDLEMANAGER            │ │ │
│  │  │                                  │  │                                │ │ │
│  │  │ - Serves immutable segments      │  │ - Runs ingestion tasks (Peons)│ │ │
│  │  │ - Loads segments from deep store │  │ - Real-time indexing          │ │ │
│  │  │ - Memory-maps segment data       │  │ - Serves real-time segments   │ │ │
│  │  │ - Tiered: hot (SSD) / cold (HDD)│  │ - Publishes to deep storage   │ │ │
│  │  │ - Caches: segment + result       │  │ - Each task = 1 Peon JVM      │ │ │
│  │  │                                  │  │                                │ │ │
│  │  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐   │  │  ┌──────┐ ┌──────┐ ┌──────┐ │ │ │
│  │  │  │Seg1│ │Seg2│ │Seg3│ │SegN│   │  │  │Peon1 │ │Peon2 │ │Peon3 │ │ │ │
│  │  │  └────┘ └────┘ └────┘ └────┘   │  │  │(Kafka│ │(Kafka│ │(Batch│ │ │ │
│  │  │                                  │  │  │ task)│ │ task)│ │ task)│ │ │ │
│  │  │  Segments mmap'd into memory     │  │  └──────┘ └──────┘ └──────┘ │ │ │
│  │  │  (OS page cache manages hot data)│  │                                │ │ │
│  │  └──────────────────────────────────┘  └────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                      EXTERNAL DEPENDENCIES                                  │ │
│  │                                                                            │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐ │ │
│  │  │  ZooKeeper   │  │  Metadata Store  │  │  Deep Storage               │ │ │
│  │  │              │  │  (MySQL/PG)      │  │  (S3/HDFS/GCS)             │ │ │
│  │  │ - Cluster    │  │                  │  │                             │ │ │
│  │  │   discovery  │  │ - Segment        │  │ - Immutable segments        │ │ │
│  │  │ - Leader     │  │   metadata       │  │ - Source of truth           │ │ │
│  │  │   election   │  │ - Rules          │  │ - Historicals pull from     │ │ │
│  │  │ - Segment    │  │ - Task info      │  │   here when loading         │ │ │
│  │  │   publishing │  │ - Audit log      │  │ - Cheap, infinite storage   │ │ │
│  │  └──────────────┘  └──────────────────┘  └─────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Storage Engine & Segments

### Segment Structure
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DRUID SEGMENT STRUCTURE                               │
│                                                                              │
│  Segment = fundamental unit of storage and distribution                      │
│  Named: datasource_intervalStart_intervalEnd_version_partitionNum            │
│  Example: "clicks_2024-01-01T00:00:00.000Z_2024-01-02T00:00:00.000Z_v1_0" │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    SEGMENT FILE (compressed, immutable)                │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  version.bin - segment format version                            │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  TIMESTAMP COLUMN                                                │ │   │
│  │  │  - Delta encoded + LZ4 compressed                                │ │   │
│  │  │  - Millisecond granularity                                       │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  DIMENSION COLUMNS (string/numeric)                              │ │   │
│  │  │                                                                   │ │   │
│  │  │  For each STRING dimension:                                       │ │   │
│  │  │  ┌──────────────────────────────────────────────────────────┐    │ │   │
│  │  │  │ Dictionary: sorted unique values → integer IDs            │    │ │   │
│  │  │  │ Encoded column: array of dictionary IDs                  │    │ │   │
│  │  │  │ Bitmap index: value → roaring bitmap of row positions    │    │ │   │
│  │  │  └──────────────────────────────────────────────────────────┘    │ │   │
│  │  │                                                                   │ │   │
│  │  │  Example "country" dimension:                                     │ │   │
│  │  │  Dictionary: {"BR"→0, "IN"→1, "US"→2}                           │ │   │
│  │  │  Column: [2, 1, 2, 0, 1, 2, ...]  (encoded as ints)            │ │   │
│  │  │  Bitmaps:                                                         │ │   │
│  │  │    "BR" → 0001000010...  (rows where country=BR)                 │ │   │
│  │  │    "IN" → 0100010000...  (rows where country=IN)                 │ │   │
│  │  │    "US" → 1010100101...  (rows where country=US)                 │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  METRIC COLUMNS (aggregated values)                              │ │   │
│  │  │                                                                   │ │   │
│  │  │  - LZ4 or LZF compressed                                        │ │   │
│  │  │  - Types: long, float, double, complex (hyperLogLog, sketch)    │ │   │
│  │  │  - If rollup enabled: pre-aggregated (sum, count, etc.)         │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  metadata.drd - column metadata, intervals, schema               │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  index.drd - bitmap indexes metadata                             │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  Typical segment: 5-10 million rows, 300MB-700MB                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rollup (Pre-Aggregation)
```
Rollup collapses rows with same dimensions + time granularity:

Before rollup (raw events):
┌───────────────────┬─────────┬────────┬───────────┬───────┐
│ timestamp         │ country │ device │ impressions│ clicks│
├───────────────────┼─────────┼────────┼───────────┼───────┤
│ 2024-01-01 10:01  │ US      │ mobile │ 1         │ 0     │
│ 2024-01-01 10:01  │ US      │ mobile │ 1         │ 1     │
│ 2024-01-01 10:01  │ US      │ mobile │ 1         │ 0     │
│ 2024-01-01 10:02  │ US      │ desktop│ 1         │ 1     │
└───────────────────┴─────────┴────────┴───────────┴───────┘

After rollup (queryGranularity: MINUTE):
┌───────────────────┬─────────┬────────┬───────────┬───────┬───────┐
│ timestamp         │ country │ device │ impressions│ clicks│ count │
├───────────────────┼─────────┼────────┼───────────┼───────┼───────┤
│ 2024-01-01 10:01  │ US      │ mobile │ 3         │ 1     │ 3     │
│ 2024-01-01 10:02  │ US      │ desktop│ 1         │ 1     │ 1     │
└───────────────────┴─────────┴────────┴───────────┴───────┴───────┘

Benefits:
- 10-100x fewer rows stored
- Much faster queries (fewer rows to scan)
- Less storage space

Trade-offs:
- Cannot query individual raw events
- Cannot add new aggregations after ingest
- Cannot drill down below chosen granularity

Best practice: Keep raw data in data lake, rollup in Druid
```

---

## Data Ingestion

### Ingestion Methods
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DRUID INGESTION METHODS                                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STREAMING INGESTION (real-time)                                      │   │
│  │                                                                       │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                   │   │
│  │  │ Kafka Indexing       │  │ Kinesis Indexing     │                   │   │
│  │  │ Service              │  │ Service              │                   │   │
│  │  │                      │  │                      │                   │   │
│  │  │ - Exactly-once       │  │ - Exactly-once       │                   │   │
│  │  │ - Auto-scaling tasks │  │ - Checkpoint-based   │                   │   │
│  │  │ - Supervisor managed │  │ - Supervisor managed │                   │   │
│  │  │ - Offset tracking    │  │ - Shard discovery    │                   │   │
│  │  └─────────────────────┘  └─────────────────────┘                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  BATCH INGESTION                                                      │   │
│  │                                                                       │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                   │   │
│  │  │ Native Batch         │  │ Hadoop-based         │                   │   │
│  │  │ (parallel indexing)  │  │ (MapReduce)          │                   │   │
│  │  │                      │  │                      │                   │   │
│  │  │ - No external deps   │  │ - For very large     │                   │   │
│  │  │ - S3/GCS/HDFS input │  │   datasets (100s TB) │                   │   │
│  │  │ - Parallel tasks     │  │ - Existing Hadoop    │                   │   │
│  │  │ - Automatic splitting│  │   cluster            │                   │   │
│  │  └─────────────────────┘  └─────────────────────┘                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Segment lifecycle:                                                          │
│  ┌──────┐    ┌──────┐    ┌───────────┐    ┌──────────────┐                 │
│  │Ingest│───▶│Build │───▶│Publish to │───▶│Load on       │                 │
│  │data  │    │segment│    │deep storage│    │Historical    │                 │
│  └──────┘    └──────┘    └───────────┘    └──────────────┘                 │
│                                              ▲                               │
│                              Coordinator assigns segment to Historical       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Query Engine & SQL

### Query Execution Flow
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      QUERY EXECUTION FLOW                                     │
│                                                                              │
│  Client (SQL query)                                                          │
│    │                                                                         │
│    │  SELECT country, SUM(impressions), COUNT(*)                             │
│    │  FROM clicks                                                            │
│    │  WHERE __time >= '2024-01-01' AND __time < '2024-01-02'                │
│    │  AND device = 'mobile'                                                  │
│    │  GROUP BY country                                                       │
│    │  ORDER BY SUM(impressions) DESC                                         │
│    │  LIMIT 10                                                               │
│    │                                                                         │
│    ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ BROKER                                                               │    │
│  │                                                                       │    │
│  │ 1. Parse SQL → Druid native query (or execute directly via Calcite) │    │
│  │ 2. Identify segments for time range [Jan 1 - Jan 2]                 │    │
│  │ 3. Determine which nodes hold those segments                         │    │
│  │ 4. Check result cache (segment-level caching)                       │    │
│  │ 5. Fan-out subqueries to data nodes                                  │    │
│  └───────────┬─────────────────────────────┬───────────────────────────┘    │
│              │                              │                                │
│              ▼                              ▼                                │
│  ┌───────────────────────┐    ┌───────────────────────┐                     │
│  │ HISTORICAL NODE 1     │    │ HISTORICAL NODE 2     │                     │
│  │                        │    │                        │                     │
│  │ Segments: Jan1 0:00-6h│    │ Segments: Jan1 6h-12h │                     │
│  │                        │    │                        │                     │
│  │ For each segment:     │    │ For each segment:     │                     │
│  │ 1. Apply time filter  │    │ 1. Apply time filter  │                     │
│  │ 2. Use bitmap index   │    │ 2. Use bitmap index   │                     │
│  │    for device='mobile'│    │    for device='mobile'│                     │
│  │ 3. AND bitmaps → rows │    │ 3. AND bitmaps → rows │                     │
│  │ 4. Read metric columns│    │ 4. Read metric columns│                     │
│  │    for matched rows   │    │    for matched rows   │                     │
│  │ 5. Aggregate locally  │    │ 5. Aggregate locally  │                     │
│  │ 6. Return partial     │    │ 6. Return partial     │                     │
│  └───────────┬───────────┘    └───────────┬───────────┘                     │
│              │                              │                                │
│              └──────────────┬───────────────┘                                │
│                             ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ BROKER (merge)                                                       │    │
│  │                                                                       │    │
│  │ 1. Merge partial results from all nodes                              │    │
│  │ 2. Final aggregation (sum partial sums)                              │    │
│  │ 3. Apply ORDER BY and LIMIT                                          │    │
│  │ 4. Cache results per segment (for future queries)                    │    │
│  │ 5. Return final result to client                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Why it's fast:                                                              │
│  - Bitmap indexes: Filter by dimension = simple bitmap AND operations       │
│  - Columnar: Only read needed columns (country, impressions)                │
│  - Pre-aggregation: Rollup reduces rows before they're even stored          │
│  - Parallel: Each node processes its segments independently                 │
│  - Caching: Segment-level cache avoids re-reading immutable data            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Native Query Types
```
Druid native JSON queries (used internally even when SQL submitted):

1. Timeseries: aggregate over time intervals
   - Fastest query type
   - No grouping dimensions, just time + aggregations
   
2. TopN: approximate top-K by single dimension
   - Much faster than groupBy for single dimension
   - Approximate (exact with threshold parameter)

3. GroupBy: multi-dimensional aggregation
   - Most flexible, most expensive
   - Like SQL GROUP BY with multiple columns
   - v2 engine: streaming merge + spill to disk

4. Scan: raw row retrieval (no aggregation)
   - For exploring raw data
   - Supports ordering and limits

5. Search: find dimension values matching pattern
   - Like SHOW TAG VALUES in InfluxDB
   - Fast due to dictionary encoding

Query type selection (automatic from SQL):
  SQL with GROUP BY time only → Timeseries
  SQL with GROUP BY 1 dimension + LIMIT → TopN
  SQL with GROUP BY multiple dimensions → GroupBy
  SQL with no aggregation → Scan
```

---

## Real-Time Ingestion Deep Dive

### Kafka Indexing Service
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KAFKA INGESTION PIPELINE                                   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  KAFKA CLUSTER                                                        │   │
│  │  Topic: "ad_events" (partitions: 0,1,2,3,4,5)                       │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
│                                      │ Consume                               │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  SUPERVISOR (managed by Overlord)                                     │   │
│  │                                                                       │   │
│  │  Configuration:                                                       │   │
│  │  - ioConfig.topic: "ad_events"                                       │   │
│  │  - ioConfig.taskCount: 3 (parallel consumers)                        │   │
│  │  - ioConfig.replicas: 2 (for HA)                                     │   │
│  │  - tuningConfig.maxRowsPerSegment: 5,000,000                        │   │
│  │  - tuningConfig.taskDuration: PT1H (1 hour)                         │   │
│  │                                                                       │   │
│  │  Creates reading tasks:                                               │   │
│  │  ┌─────────────────────┬─────────────────────┬──────────────────┐   │   │
│  │  │ Task 0 (replica 0)  │ Task 1 (replica 0)  │ Task 2 (rep 0)  │   │   │
│  │  │ Partitions: 0,1     │ Partitions: 2,3     │ Partitions: 4,5 │   │   │
│  │  ├─────────────────────┼─────────────────────┼──────────────────┤   │   │
│  │  │ Task 0 (replica 1)  │ Task 1 (replica 1)  │ Task 2 (rep 1)  │   │   │
│  │  │ Partitions: 0,1     │ Partitions: 2,3     │ Partitions: 4,5 │   │   │
│  │  └─────────────────────┴─────────────────────┴──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Task Lifecycle:                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Task starts, seeks to last committed Kafka offset                   │  │
│  │ 2. Consumes messages, builds in-memory segment (incremental index)    │  │
│  │ 3. Queryable immediately (served from MiddleManager)                   │  │
│  │ 4. At taskDuration or maxRows: begin handoff                          │  │
│  │ 5. Build final segment, push to deep storage                           │  │
│  │ 6. Publish segment metadata to metadata store                         │  │
│  │ 7. Wait for Historical to load segment                                 │  │
│  │ 8. New task starts from last committed offset                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Exactly-once guarantees:                                                    │
│  - Offsets committed AFTER segment published to deep storage                │
│  - If task fails: new task replays from last committed offset               │
│  - Segment publication is atomic (metadata store transaction)               │
│  - No duplicate data (idempotent segment publishing)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Retention & Tiering

### Tiered Historicals
```
┌─────────────────────────────────────────────────────────────────┐
│                    TIERED STORAGE                                 │
│                                                                   │
│  Coordinator rules determine segment placement:                  │
│                                                                   │
│  Rule 1: IF period < P7D → tier = "hot"                         │
│  Rule 2: IF period < P30D → tier = "warm"                       │
│  Rule 3: IF period < P365D → tier = "cold"                      │
│  Rule 4: Drop (forever rule to delete old data)                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ HOT TIER (last 7 days)                                       ││
│  │ - NVMe SSD storage                                           ││
│  │ - High RAM (segments in page cache)                          ││
│  │ - Highest query performance                                  ││
│  │ - 3 nodes, 32 cores, 128GB RAM, 2TB NVMe each              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ WARM TIER (7-30 days)                                        ││
│  │ - SATA SSD storage                                           ││
│  │ - Moderate RAM                                               ││
│  │ - Good query performance                                     ││
│  │ - 3 nodes, 16 cores, 64GB RAM, 4TB SSD each                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ COLD TIER (30 days - 1 year)                                 ││
│  │ - HDD storage or deep storage only                           ││
│  │ - Minimal RAM (load on demand)                               ││
│  │ - Acceptable query latency (seconds)                         ││
│  │ - 2 nodes, 8 cores, 32GB RAM, 20TB HDD each                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  Cost optimization:                                              │
│  - Hot tier: $$$  (fast queries for recent data)                │
│  - Warm tier: $$  (good enough for dashboards)                  │
│  - Cold tier: $   (ad-hoc historical queries)                   │
│  - Deep storage only: ¢ (archive, reload when needed)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## High Availability & Scaling

### Replication & Segment Balancing
```
HA mechanisms:

1. Segment replication:
   - Coordinator replicates segments across Historicals
   - druid.coordinator.replicant.period = PT1H
   - Configurable replication factor per datasource/tier
   - If a Historical dies, segments available on replicas

2. Query HA:
   - Multiple Brokers behind load balancer
   - Broker has no state (any can serve any query)
   - If one Broker dies, others continue serving

3. Ingestion HA:
   - Kafka supervisor replicas (multiple tasks per partition set)
   - If a MiddleManager dies, Overlord reassigns tasks
   - Kafka offsets ensure no data loss

4. Master HA:
   - Coordinator + Overlord: leader election via ZooKeeper
   - Standby instances ready to take over
   - Short failover time (~30 seconds)

Segment balancing:
  Coordinator continuously optimizes placement:
  - Cost function: query latency + disk usage + balance
  - Moves segments between Historicals for even load
  - Respects tier assignments
  - Rate-limited to avoid thrashing
```

### Scaling Each Tier Independently
```
┌────────────────────────────────────────────────────────────────┐
│ Component       │ Scale Trigger            │ How to Scale       │
├─────────────────┼──────────────────────────┼────────────────────┤
│ Broker          │ Query concurrency        │ Add Brokers        │
│ Historical      │ Segment count/size       │ Add Historicals    │
│ MiddleManager   │ Ingestion throughput     │ Add MiddleManagers │
│ Coordinator     │ Segment count (metadata) │ Upgrade (vertical) │
│ Overlord        │ Task count               │ Upgrade (vertical) │
└─────────────────┴──────────────────────────┴────────────────────┘

Scaling is independent:
- More queries? → Add Brokers + Historicals
- More ingestion? → Add MiddleManagers
- More data volume? → Add Historicals + deep storage
- This is Druid's key architectural advantage
```

---

## Performance Optimization

### Segment Sizing & Partitioning
```
Optimal segment configuration:

Segment size: 300MB - 700MB (compressed)
Rows per segment: 5 million (ideal target)
Segment granularity: Choose based on data volume
  - < 10M rows/day → DAY granularity
  - 10M-100M rows/day → HOUR granularity  
  - > 100M rows/day → HOUR + secondary partitioning

Secondary partitioning strategies:
1. Hash partitioning: Even distribution by dimension hash
2. Range partitioning: By specific dimension value ranges
3. Single-dim partitioning: Partition by one high-cardinality dimension

Impact on queries:
  Query: WHERE country = 'US' AND time = '2024-01-01'
  
  Without partitioning: Must scan all segments for that hour
  With hash on country: Only scan 1 segment (where US hashes to)
  
  Segment pruning = fewer segments to read = faster queries

Compaction (post-ingest optimization):
  - Merges small segments into optimal-size segments
  - Adds partitioning to streaming-ingested data
  - Adds rollup to raw data
  - Scheduled by Coordinator (autoCompaction)
```

### Query Context Parameters
```
Key tuning parameters per query:

{
  "queryContext": {
    "timeout": 60000,                    // Query timeout ms
    "priority": 0,                       // -1 (low) to 10 (high)
    "useCache": true,                    // Use segment cache
    "populateCache": true,               // Store in segment cache
    "useResultLevelCache": true,         // Use result cache
    "maxQueuedBytes": 100000000,         // Memory limit for buffering
    "vectorize": "force",                // Vectorized query engine
    "vectorSize": 1024,                  // Batch size for vectorization
    "maxSubqueryRows": 100000,           // Limit subquery intermediate rows
    "maxScatterGatherBytes": 1073741824  // Max scatter-gather memory
  }
}

Vectorized query engine (Druid 0.17+):
- Processes data in batches (vector of 512/1024 values)
- SIMD-like processing on columnar data
- 2-5x faster than row-by-row for most queries
- Enabled by default for supported query types
```

---

## Production Deployment Patterns

### Production Topology
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              PRODUCTION DRUID DEPLOYMENT (Large Scale)                        │
│                                                                              │
│  Master Tier (3 nodes):                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │ Coordinator(L)   │ │ Coordinator(S)   │ │ Coordinator(S)   │            │
│  │ + Overlord(L)    │ │ + Overlord(S)    │ │ + Overlord(S)    │            │
│  │ 8 CPU, 32GB RAM │ │ 8 CPU, 32GB RAM │ │ 8 CPU, 32GB RAM │            │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘            │
│                                                                              │
│  Query Tier (4+ nodes):                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌────┐    │
│  │ Broker 1         │ │ Broker 2         │ │ Broker 3         │ │ .. │    │
│  │ 16 CPU, 64GB RAM│ │ 16 CPU, 64GB RAM│ │ 16 CPU, 64GB RAM│ │    │    │
│  │ (heap: 12GB)    │ │ (heap: 12GB)    │ │ (heap: 12GB)    │ │    │    │
│  │ (direct: 48GB)  │ │ (direct: 48GB)  │ │ (direct: 48GB)  │ │    │    │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └────┘    │
│                                                                              │
│  Data Tier - Hot (6+ nodes):                                                │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌────┐    │
│  │ Historical 1     │ │ Historical 2     │ │ Historical 3     │ │ .. │    │
│  │ 32 CPU, 128GB   │ │ 32 CPU, 128GB   │ │ 32 CPU, 128GB   │ │    │    │
│  │ 2TB NVMe SSD    │ │ 2TB NVMe SSD    │ │ 2TB NVMe SSD    │ │    │    │
│  │ (heap: 12GB)    │ │ (heap: 12GB)    │ │ (heap: 12GB)    │ │    │    │
│  │ (direct: 100GB) │ │ (direct: 100GB) │ │ (direct: 100GB) │ │    │    │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └────┘    │
│                                                                              │
│  Ingestion Tier (4+ nodes):                                                 │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌────┐    │
│  │ MiddleManager 1  │ │ MiddleManager 2  │ │ MiddleManager 3  │ │ .. │    │
│  │ 16 CPU, 64GB RAM│ │ 16 CPU, 64GB RAM│ │ 16 CPU, 64GB RAM│ │    │    │
│  │ 500GB SSD (tmp) │ │ 500GB SSD (tmp) │ │ 500GB SSD (tmp) │ │    │    │
│  │ 4 task slots    │ │ 4 task slots    │ │ 4 task slots    │ │    │    │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └────┘    │
│                                                                              │
│  External:                                                                   │
│  ┌───────────────┐  ┌───────────────────┐  ┌──────────────────────┐        │
│  │ ZooKeeper (3) │  │ MySQL/PG (HA)     │  │ S3 / HDFS            │        │
│  │ (metadata)    │  │ (metadata store)  │  │ (deep storage)       │        │
│  └───────────────┘  └───────────────────┘  └──────────────────────┘        │
│                                                                              │
│  Monitoring: Druid emits metrics → Prometheus → Grafana                     │
└─────────────────────────────────────────────────────────────────────────────┘

JVM tuning (Historical example):
  -Xms12g -Xmx12g (heap for metadata, merging)
  -XX:MaxDirectMemorySize=100g (for mmap'd segments)
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=100
  
  Most segment data accessed via mmap (off-heap/direct memory)
  OS page cache is critical for performance
```

---

## Security & Multi-tenancy

### Security Model
```
Authentication options:
- Basic auth (username/password)
- LDAP integration
- Kerberos (Hadoop environments)
- Custom authenticator (plugin)

Authorization:
- Resource-based permissions:
  - DATASOURCE: read, write
  - CONFIG: read, write
  - STATE: read, write (cluster state)
  - SYSTEM_TABLE: read
- Role-based: map users to roles to permissions

Multi-tenancy approaches:
1. Datasource-per-tenant:
   - tenant_a_clicks, tenant_b_clicks
   - Simple isolation via permissions
   - Downside: Many datasources to manage

2. Shared datasource with tenant dimension:
   - Filter: WHERE tenant_id = 'A'
   - Less isolation (query bugs could leak)
   - Better resource utilization

3. Separate clusters:
   - Complete isolation
   - Highest cost
   - For compliance-sensitive environments
```

---

## Use Case Architectures

### Ad-Tech Analytics
```
┌─────────────────────────────────────────────────────────────────┐
│              AD-TECH REAL-TIME ANALYTICS                          │
│                                                                   │
│  Ad Servers (100K+ events/sec)                                   │
│  ┌────────┐ ┌────────┐ ┌────────┐                              │
│  │ Server │ │ Server │ │ Server │ → impression/click events     │
│  └───┬────┘ └───┬────┘ └───┬────┘                              │
│      └──────────┴──────────┘                                     │
│              │                                                    │
│              ▼                                                    │
│  ┌────────────────────┐                                         │
│  │ Kafka              │  Topics: impressions, clicks, conversions│
│  │ (100 partitions)   │                                         │
│  └─────────┬──────────┘                                         │
│            │                                                     │
│            ▼                                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DRUID CLUSTER                                               │ │
│  │                                                             │ │
│  │ Datasource: ad_events                                       │ │
│  │ Dimensions: campaign_id, advertiser, publisher, country,    │ │
│  │             device_type, browser, os, ad_size               │ │
│  │ Metrics: impressions(count), clicks(count), spend(sum),     │ │
│  │          revenue(sum)                                        │ │
│  │ Rollup: MINUTE granularity                                  │ │
│  │ Retention: 90 days (hot: 7d, warm: 30d, cold: 90d)        │ │
│  └────────────────────────────────────────────────────────────┘ │
│            │                                                     │
│            ▼                                                     │
│  Queries (sub-second):                                          │
│  - "Show CTR by campaign for last hour"                         │
│  - "Top 10 publishers by revenue today"                         │
│  - "Impressions by country, device for campaign X"              │
│  - Serving 10K+ concurrent dashboard queries                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: How does Druid achieve sub-second query latency on billions of rows?
```
Answer:
Multiple techniques combine:

1. Segment pruning: Time-based partitioning eliminates irrelevant segments
2. Bitmap indexes: Filter conditions → bitmap AND operations (no row scan)
3. Dictionary encoding: Strings stored as integers (smaller, faster comparison)
4. Columnar storage: Only read needed columns (10% of row-oriented I/O)
5. Rollup: Pre-aggregation reduces row count 10-100x at ingest time
6. Scatter-gather: Parallel processing across Historical nodes
7. Vectorized engine: Process 1024 values per batch (CPU cache friendly)
8. mmap: Segments memory-mapped (OS page cache = fast repeated access)
9. Result caching: Segment-level cache (immutable segments = perfect cache)
10. TopN approximation: Top-K queries avoid full sort

Example: 10 billion rows, 30 days, query last 24h:
- Segment pruning: 10B → 330M (1/30 of data)
- Bitmap filter: 330M → 3.3M (1% match rate)
- Columnar: Read 2 columns of 3.3M rows (fast sequential I/O)
- Scatter-gather: Split across 6 Historicals (550K each)
- Result: <500ms
```

### Q2: Compare Druid's bitmap indexes vs ClickHouse's approach
```
Answer:
Druid: Bitmap (Roaring Bitmap) indexes
- Pre-built at ingest time for every dimension value
- O(1) filter application (bitmap AND/OR)
- Space-efficient for low-medium cardinality
- Less effective for high cardinality (>1M unique values)
- Best for: equality filters, IN clauses

ClickHouse: Sparse primary index + data skipping indexes
- Primary index: sparse (every Nth row) → finds granules
- Secondary: minmax, set, bloom_filter, ngrambf
- No pre-built bitmap per value
- Better for range queries and high cardinality
- Best for: range filters, prefix matches

Trade-off:
- Druid faster for exact equality on low-cardinality dimensions
- ClickHouse faster for range queries and high-cardinality columns
- Druid: more storage overhead (bitmap per value)
- ClickHouse: more flexible indexing options
```

### Q3: How would you handle late-arriving data in Druid?
```
Answer:
Late data = events arriving after the segment for their time window is published.

Strategies:
1. Append (taskDuration overlap):
   - Set task early-offset to cover expected lateness
   - Example: ioConfig.lateMessageRejectionPeriod: PT1H
   - Late data within 1 hour will be included

2. Separate datasource:
   - Route late data to "datasource_late"
   - Periodically compact/merge with main datasource
   
3. Reindexing:
   - Batch re-index affected time ranges
   - Replaces existing segments with corrected data
   - Can be automated via compaction

4. Delta architecture:
   - Real-time: streaming ingest (may miss late data)
   - Batch: nightly batch job catches all late arrivals
   - Union query across both datasources at query time

Best practice for ad-tech (where revenue accuracy matters):
- Real-time ingest with 1h late buffer
- Nightly batch compaction/reindex of previous day
- Weekly full reindex for compliance reports
```

### Q4-Q10: Additional Questions
```
Q4: Explain exactly-once semantics in Kafka ingestion
- Each task tracks Kafka offsets in memory
- Offsets committed to Kafka ONLY after segment published to deep storage
- If task crashes: new task starts from last committed offset
- Segment publishing is idempotent (same segment ID = no duplicate)
- Result: Each event appears exactly once in Druid

Q5: How does compaction work and when to use it?
- Compaction = re-ingest existing segments with different settings
- Use cases: Add rollup, change partitioning, merge small segments
- Scheduler: Coordinator auto-compaction (configurable)
- Impact: Temporary double storage (old + new segments)
- Best practice: Run during off-peak, rate-limit I/O

Q6: How to handle high-cardinality dimensions?
- High cardinality → large dictionaries + many bitmaps → more memory
- Solutions: 
  - Move to metric (field) if not filtered/grouped on
  - Use multi-value dimensions
  - Hash to bounded cardinality
  - Use LONG type instead of STRING for numeric IDs
  - Consider sketch aggregators (theta/HLL for approximation)

Q7: Druid vs Pinot - when to choose each?
- Druid: Stronger rollup, better for aggregation-heavy workloads
- Pinot: Better upsert support, star-tree index, LinkedIn backing
- Druid: More mature ecosystem, better documentation
- Pinot: Better for user-facing analytics with high QPS
- Both: Sub-second, real-time, segment-based, Kafka integration

Q8: How to monitor Druid cluster health?
- Coordinator: segment loading lag, replication factor
- Broker: query/time, query/failed, query/count
- Historical: segment/scan/pending, segment/count
- MiddleManager: task/success, task/failed, task/running
- Query latency percentiles: p50, p95, p99 per datasource
- Ingestion lag: Kafka consumer lag per supervisor

Q9: Disaster recovery strategy for Druid
- Deep storage is source of truth (replicated S3/GCS)
- Metadata store: MySQL/PG with replication + backups
- ZooKeeper: 3-node ensemble with snapshots
- Recovery: Redeploy cluster, Historicals reload from deep storage
- RPO: 0 (deep storage is durable)
- RTO: Time to reload segments (depends on data volume)

Q10: How to optimize Druid for high query concurrency?
- Increase Broker count (stateless, easy to scale)
- Enable query caching (segment-level + result-level)
- Increase Historical count (more parallel segment serving)
- Use query priority queuing (important queries first)
- Set query timeout (kill runaway queries)
- Sub-query result size limits (prevent memory explosion)
```

---

## Scenario-Based Questions

### Scenario 1: Query latency spikes during ingestion
```
Diagnosis:
1. MiddleManager competing for CPU with Historical queries?
   - Separate into different node pools
2. Compaction running during peak query time?
   - Schedule compaction off-peak
3. New segments being loaded (cache cold)?
   - Pre-warm segments, increase page cache
4. GC pauses on Historical nodes?
   - Reduce heap, increase direct memory for mmap

Solution architecture:
- Dedicate nodes: ingestion-only MiddleManagers, query-only Historicals
- Tiered Historicals: hot tier with excess RAM for full page cache
- Rate-limit compaction during business hours
- Query priority: Dashboard queries > ad-hoc queries
```

### Scenario 2: Design real-time analytics for 1M events/sec
```
Architecture:
- Kafka: 100 partitions, 3 brokers
- Druid ingestion: 10 MiddleManagers, 4 tasks each
- taskCount: 25 (Kafka supervisor)
- Rollup: MINUTE granularity, reduce 1M/s to ~100K/s stored
- Historicals: 12 nodes (hot tier), 2TB NVMe each
- Brokers: 4 nodes, 64GB RAM each
- Segment granularity: HOUR
- Retention: 30 days hot, 90 days warm, 1 year cold

Estimated resources:
- Storage: 1M × 86400 × 100 bytes / rollup(10x) / compression(5x) 
         ≈ 170 GB/day raw → 3.4 GB/day after rollup + compression
- 30 day hot: ~100 GB on NVMe
- Query concurrency: 1000+ simultaneous with 4 Brokers
```

### Scenario 3: Segment loading falling behind after cluster restart
```
Problem: After restart, Historicals must reload all segments from deep storage.

Immediate:
- Increase coordinator replication throttle
- Prioritize recent segments (hot data first)

Architecture improvements:
- Use local SSD cache (druid.segmentCache): segments persist on disk
  across restarts → instant reload from local cache
- Increase segmentCache.locations size
- Pre-fetch: Load segments before marking node as available
- Rolling restarts: Never restart all Historicals simultaneously
- Kubernetes: Use StatefulSets with PVC (segment cache survives pod restart)
```

### Scenario 4: Cost optimization for a 500TB Druid cluster
```
Analysis:
- 500TB = deep storage cost + compute cost
- Most data is cold (>30 days old, rarely queried)

Optimization:
1. Tiered storage:
   - Hot (7d): 50TB on NVMe, fast queries
   - Warm (30d): 100TB on SATA SSD
   - Cold (365d): 200TB on HDD or deep-storage-only
   - Archive: Drop from Historicals, keep in S3 (reload on demand)

2. Rollup improvements:
   - Increase rollup granularity for older data (1min → 1hour)
   - Reduces storage 60x for historical data

3. Column pruning:
   - Drop unused dimensions during compaction
   - Reduce segment size significantly

4. Spot instances:
   - MiddleManagers on spot (tasks are retryable)
   - Cold-tier Historicals on spot (segments reloadable)

Cost reduction: 500TB × $0.023/GB → tiered: 60-70% savings
```

### Scenario 5: Data accuracy discrepancy between Druid and data warehouse
```
Root causes:
1. Late-arriving data not captured in Druid
2. Rollup precision loss (pre-aggregation)
3. Kafka consumer lag during peak (data not yet ingested)
4. Approximate algorithms (HyperLogLog, theta sketches)
5. Clock skew between event sources

Resolution:
- Audit: Compare specific time ranges, specific dimensions
- Late data: Implement nightly batch reindex from data lake
- Rollup: Document precision expectations (Druid = operational analytics)
- Lag: Monitor supervisor lag, alert if > threshold
- Approximation: Use exact algorithms for billing-critical metrics
- Reconciliation: Daily job comparing Druid totals vs warehouse
- Accept: Druid = 99.9% accuracy, warehouse = source of truth
```
