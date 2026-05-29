# Stream Processing Architectures - Staff Architect Deep Dive

## Table of Contents
1. [Fundamentals](#1-fundamentals)
2. [Lambda Architecture](#2-lambda-architecture)
3. [Kappa Architecture](#3-kappa-architecture)
4. [Streaming Guarantees](#4-streaming-guarantees)
5. [Event Time Processing](#5-event-time-processing)
6. [Windowing](#6-windowing)
7. [State Management](#7-state-management)
8. [Stream-Table Duality](#8-stream-table-duality)
9. [Backpressure](#9-backpressure)
10. [Streaming Joins](#10-streaming-joins)
11. [Framework Comparison](#11-kafka-streams-vs-flink-vs-spark-streaming)
12. [Real-time Analytics](#12-real-time-analytics)
13. [Event Sourcing and CQRS](#13-event-sourcing-and-cqrs)
14. [Deployment Patterns](#14-deployment-patterns)

---

## 1. Fundamentals

### Bounded vs Unbounded Data

```
BOUNDED (Batch):
  Known start and end, complete dataset
  ┌────────────────────────────────────┐
  │ ████████████████████████████████████│  ← All data available
  └────────────────────────────────────┘
  Process once, get final result

UNBOUNDED (Streaming):
  Continuous, potentially infinite
  ──────████████████████████████████████───────────▶ (never ends)
  Process continuously, results evolve
```

### Time Domains

```
EVENT TIME:        When the event actually occurred
INGESTION TIME:    When the event entered the processing system
PROCESSING TIME:   When the event is being processed

Timeline example:
  Event created:   10:00:00 (event time)
  Event produced:  10:00:05 (network delay)
  Kafka received:  10:00:06 (ingestion time)
  Flink processes: 10:00:15 (processing time)
  
  Event time is most meaningful but hardest to work with
  (requires handling out-of-order events)
```

### Out-of-Order Events

```
Ideal world (perfectly ordered):
  E1(10:00) → E2(10:01) → E3(10:02) → E4(10:03) → E5(10:04)

Real world (out of order):
  E1(10:00) → E3(10:02) → E2(10:01) → E5(10:04) → E4(10:03)
                            ▲                        ▲
                         Late!                    Late!

Causes:
  - Network delays (different paths)
  - Multi-producer with clock skew
  - Mobile devices with connectivity gaps
  - Micro-service fan-out/fan-in
  - Retry/redelivery
```

---

## 2. Lambda Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    LAMBDA ARCHITECTURE                             │
│                                                                    │
│                    ┌──────────────────────┐                       │
│  ┌──────────┐     │    BATCH LAYER        │                       │
│  │          │────▶│    (Hadoop/Spark)      │                       │
│  │  Data    │     │                        │                       │
│  │  Source  │     │  Master Dataset        │──── Batch Views ────┐│
│  │ (Events) │     │  (immutable, append)   │                     ││
│  │          │     └──────────────────────┘                     ││
│  │          │                                                    ││
│  │          │     ┌──────────────────────┐    ┌────────────────┐││
│  │          │────▶│    SPEED LAYER        │───▶│ SERVING LAYER  │││
│  │          │     │    (Storm/Flink)      │    │                │││
│  └──────────┘     │                        │    │ Merge batch + │││
│                    │  Real-time views      │    │ speed results  │││
│                    │  (approximate, fast)  │    │                │││
│                    └──────────────────────┘    │ Query interface│││
│                                                │                ││┘
│                                                └────────────────┘│
└──────────────────────────────────────────────────────────────────┘

Pros:
  ✓ Fault tolerant (batch can recompute everything)
  ✓ Simple correctness model (batch is source of truth)
  ✓ Handles late data (batch reprocesses)

Cons:
  ✗ Two codepaths (batch + streaming) → operational complexity
  ✗ Logic duplication (same computation in two frameworks)
  ✗ Serving layer merge complexity
  ✗ High latency for batch layer (hours)
  ✗ High infrastructure cost (run both systems)
```

---

## 3. Kappa Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    KAPPA ARCHITECTURE                              │
│                                                                    │
│  ┌──────────┐     ┌──────────────────────────────────┐           │
│  │  Data    │     │         EVENT LOG                  │           │
│  │  Source  │────▶│    (Kafka - long retention)        │           │
│  │          │     │    Immutable, append-only           │           │
│  └──────────┘     │    Source of truth                  │           │
│                    └──────────────┬───────────────────┘           │
│                                   │                                │
│                    ┌──────────────▼───────────────────┐           │
│                    │      STREAM PROCESSING            │           │
│                    │      (Flink / Kafka Streams)      │           │
│                    │                                    │           │
│                    │  Single processing pipeline        │           │
│                    │  Handles batch via replay           │           │
│                    └──────────────┬───────────────────┘           │
│                                   │                                │
│                    ┌──────────────▼───────────────────┐           │
│                    │      SERVING LAYER                │           │
│                    │      (Druid / Pinot / ClickHouse) │           │
│                    └──────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘

Reprocessing strategy:
  1. Deploy new version of streaming job (Job v2)
  2. Job v2 reads from beginning of Kafka topic
  3. Job v2 writes to new output (serving table v2)
  4. When caught up, switch queries to v2
  5. Shut down Job v1, drop v1 output

Pros:
  ✓ Single codebase (one processing pipeline)
  ✓ Simpler operations
  ✓ Lower latency
  ✓ Reprocessing via replay

Cons:
  ✗ Requires long Kafka retention (cost)
  ✗ Replay can be slow for large datasets
  ✗ Streaming logic must handle both real-time and historical
  ✗ Harder to do complex analytics (ad-hoc batch queries)
```

---

## 4. Streaming Guarantees

### At-Most-Once

```
Producer ──── message ────▶ Processor ──── result ────▶ Sink
                                │
                            Process once
                            If failure → message lost
                            No retry

Implementation:
  - Fire and forget (acks=0 in Kafka)
  - No checkpointing
  - No offset commit before processing

Use cases: Metrics, logs (acceptable to lose some)
```

### At-Least-Once

```
Producer ──── message ────▶ Processor ──── result ────▶ Sink
                                │              │
                            Process ────── Commit offset
                            If failure before commit → reprocess
                            If failure after commit → move on
                            Possible DUPLICATES

Implementation:
  - Kafka acks=all, retries enabled
  - Checkpoint after processing
  - Offset committed after processing
  - But: crash between sink write and checkpoint → duplicate

Use cases: Most applications (with idempotent sinks)
```

### Exactly-Once

```
Producer ──── message ────▶ Processor ──── result ────▶ Sink
                                │              │            │
                            Process ─── Write ─── Commit offset
                            ALL in single atomic transaction
                            If failure → rollback ALL
                            No duplicates, no loss

Implementation approaches:
  1. Transactional writes (Kafka transactions)
  2. Idempotent writes (dedup at sink)
  3. Two-phase commit (Flink checkpointing + 2PC sinks)

Requirements:
  - Replayable source (Kafka with offset tracking)
  - Transactional or idempotent sink
  - Atomic checkpoint/commit mechanism
```

---

## 5. Event Time Processing

### Watermark Strategies

```
PERFECT WATERMARK (deterministic):
  W(t) = max event time seen across ALL sources
  Guarantees: No late data (all events before W have arrived)
  Possible when: Bounded source with global ordering (rare)

HEURISTIC WATERMARK (practical):
  W(t) = max event time seen - tolerance
  Example: W = max_event_time - 5 seconds
  Trade-off: 
    Small tolerance → more "on-time" but more late data
    Large tolerance → more complete windows but higher latency

WATERMARK PROPAGATION:
  Source A: W=10:05
  Source B: W=10:03
  Merged:   W=min(10:05, 10:03) = 10:03
  
  Slowest source determines overall progress!
  If Source B stops → watermark stuck (use idle timeout)
```

### Late Data Handling Strategies

```
Strategy 1: DROP late data
  Simple, but loses accuracy
  
  watermark = 10:05
  Event arrives with time 10:02 → DROPPED (before watermark)

Strategy 2: ALLOWED LATENESS (Flink/Spark)
  Keep window state open for additional time
  Late events update the window result
  
  window [10:00-10:05] closes at watermark 10:05
  allowed lateness = 10 minutes
  window state kept until watermark 10:15
  Late event at 10:02 arriving at 10:12 → ACCEPTED (updates window)
  Late event at 10:02 arriving at 10:20 → DROPPED (past allowed lateness)

Strategy 3: SIDE OUTPUT (Flink)
  Route late data to separate stream for reconciliation
  
  Main output: On-time window results
  Side output: Late events → write to DLQ/separate table
               → periodic batch reconciliation job

Strategy 4: RETRACTION/UPDATE (streaming SQL)
  Emit updated results when late data arrives
  -D[old_result]  +I[new_result]
  Downstream systems must handle retractions
```

---

## 6. Windowing

### Window Types with Diagrams

```
TUMBLING WINDOWS (fixed-size, non-overlapping):
Events: ─E1──E2──E3──E4──E5──E6──E7──E8──E9──
Windows: |====W1====|====W2====|====W3====|
         [E1,E2,E3]  [E4,E5,E6]  [E7,E8,E9]

Use: Regular periodic aggregations
Example: Hourly revenue, daily user counts


SLIDING/HOPPING WINDOWS (fixed-size, overlapping):
Events: ─E1──E2──E3──E4──E5──E6──E7──
Windows: |======W1======|
            |======W2======|
               |======W3======|
         Size=6, Slide=2
         W1=[E1-E6], W2=[E3-E8], W3=[E5-E10]

Use: Moving averages, trend detection
Example: 5-minute avg over 1-minute slides


SESSION WINDOWS (dynamic, activity-based):
Events: E1─E2─E3─────────────E4─E5──────────E6─
Windows: |===W1===|           |==W2==|        |W3|
         Gap > threshold       Gap > threshold

Use: User session analysis, clickstream
Example: User activity sessions with 30-min inactivity gap


GLOBAL WINDOW (single window per key):
Events: ─E1──E2──E3──E4──E5──E6──E7──E8──
Window: |════════════ forever ═══════════|

Use: With custom triggers (count-based, time-based)
Example: Fire every 1000 events or every 5 minutes
```

---

## 7. State Management

### State Backend Architectures

```
IN-MEMORY (Flink HashMapStateBackend):
┌─────────────────────────────────┐
│  JVM Heap                       │
│  ┌───────────────────────────┐  │
│  │  HashMap<Key, Value>       │  │
│  │  Fast access               │  │
│  │  Limited by heap size      │  │
│  │  GC pressure at scale      │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
Best for: Small state (< few GB)

EMBEDDED KV STORE (Flink EmbeddedRocksDB):
┌─────────────────────────────────┐
│  TaskManager Process            │
│  ┌───────────────────────────┐  │
│  │  RocksDB (embedded)        │  │
│  │  ┌─────────────────────┐  │  │
│  │  │  MemTable (write buf)│  │  │
│  │  ├─────────────────────┤  │  │
│  │  │  Block Cache (read) │  │  │
│  │  ├─────────────────────┤  │  │
│  │  │  SST Files (disk)   │  │  │
│  │  └─────────────────────┘  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
Best for: Large state (TB scale), incremental checkpoints

EXTERNAL STATE STORE (Kafka Streams):
┌─────────────────────────────────┐
│  Application Process            │
│  ┌────────┐    ┌─────────────┐  │
│  │RocksDB │◀──▶│  Changelog  │  │
│  │(local) │    │  Topic      │  │
│  │        │    │  (Kafka)    │  │
│  └────────┘    └─────────────┘  │
└─────────────────────────────────┘
State changes written to changelog topic for recovery
```

---

## 8. Stream-Table Duality

### Concept

```
STREAM → TABLE (materialization):
  Stream of changes → Current state of the world

  INSERT(A=1) → INSERT(B=2) → UPDATE(A=3)
  
  Table at any point:
  After INSERT(A=1):   {A:1}
  After INSERT(B=2):   {A:1, B:2}
  After UPDATE(A=3):   {A:3, B:2}

TABLE → STREAM (changelog):
  Every table change emitted as event
  
  Table: {A:3, B:2}
  Change B to 5:
  Stream: ... → UPDATE(B, old=2, new=5) → ...
```

### ksqlDB Example

```sql
-- Create stream from Kafka topic
CREATE STREAM orders_stream (
    order_id VARCHAR KEY,
    customer_id VARCHAR,
    amount DOUBLE,
    status VARCHAR,
    order_time TIMESTAMP
) WITH (
    kafka_topic = 'orders',
    value_format = 'JSON',
    timestamp = 'order_time'
);

-- Create materialized table (continuously updated)
CREATE TABLE customer_order_count AS
    SELECT customer_id,
           COUNT(*) AS total_orders,
           SUM(amount) AS total_spent
    FROM orders_stream
    WINDOW TUMBLING (SIZE 1 HOUR)
    GROUP BY customer_id
    EMIT CHANGES;

-- Query the materialized view (pull query)
SELECT * FROM customer_order_count WHERE customer_id = 'C001';

-- Subscribe to changes (push query)
SELECT * FROM customer_order_count EMIT CHANGES;

-- Stream-Table join (enrich stream with table)
CREATE TABLE customers (
    customer_id VARCHAR PRIMARY KEY,
    name VARCHAR,
    tier VARCHAR
) WITH (
    kafka_topic = 'customers',
    value_format = 'JSON'
);

CREATE STREAM enriched_orders AS
    SELECT o.order_id, o.amount, c.name, c.tier
    FROM orders_stream o
    LEFT JOIN customers c ON o.customer_id = c.customer_id
    EMIT CHANGES;
```

---

## 9. Backpressure

### Mechanisms by Framework

```
FLINK - Credit-based flow control:
  Downstream sends credits (available buffers) to upstream
  Upstream only sends if credits available
  Granular per-channel backpressure
  
  Upstream ──[data]──▶ Network Buffer ──[data]──▶ Downstream
            ◀─[credits]─              ◀─[credits]─
  
  Metrics: 
    backPressuredTimeMsPerSecond (>0 = backpressure)
    idleTimeMsPerSecond
    busyTimeMsPerSecond

KAFKA STREAMS - Inherent (single thread per task):
  Consumer.poll() → process → commit
  If processing slow → poll() called less frequently
  Consumer lag increases naturally
  No explicit backpressure mechanism needed
  
  Metrics:
    consumer-lag (increasing = slow processing)
    process-rate
    poll-rate

SPARK STREAMING - Rate limiting:
  Micro-batch: Naturally bounded (process batch, then next)
  spark.streaming.kafka.maxRatePerPartition = 1000  (records/sec)
  spark.streaming.backpressure.enabled = true (Spark Streaming)
  maxOffsetsPerTrigger = 100000 (Structured Streaming)
  
  If batch takes longer than trigger interval:
    Batches queue up → increasing delay → potential OOM
```

---

## 10. Streaming Joins

### Join Types

```
STREAM-STREAM JOIN (windowed):
  Both sides are unbounded streams
  MUST have time constraint (window or interval)
  
  Orders Stream × Shipments Stream
  ON orders.id = shipments.order_id
  AND shipments.time BETWEEN orders.time AND orders.time + 7 DAYS
  
  State: Both streams buffered in state for window duration

STREAM-TABLE JOIN (lookup):
  Stream enriched with latest table state
  
  Orders Stream × Customers Table
  ON orders.customer_id = customers.id
  
  No time constraint needed (table has "latest" value)
  State: Table materialized in local state store

TEMPORAL JOIN (time-versioned):
  Stream joined with table AS OF event time
  
  Orders Stream × Exchange Rates Table (time-versioned)
  ON orders.currency = rates.currency
  AS OF orders.order_time
  
  Gets the rate that was valid at order time (not current rate)
  State: Versioned table state (multiple versions per key)

INTERVAL JOIN (time range):
  Two streams within time range of each other
  
  Clicks × Impressions
  ON clicks.ad_id = impressions.ad_id
  AND clicks.time BETWEEN impressions.time
                  AND impressions.time + 1 HOUR
  
  State: Both streams buffered for interval duration
```

### SQL Examples

```sql
-- Flink SQL: Stream-Stream Join
SELECT 
    o.order_id,
    o.amount,
    p.payment_method,
    p.payment_time
FROM orders o
JOIN payments p
    ON o.order_id = p.order_id
    AND p.payment_time BETWEEN o.order_time 
    AND o.order_time + INTERVAL '1' HOUR;

-- Flink SQL: Temporal Join
SELECT 
    o.order_id,
    o.amount,
    o.amount * r.rate AS amount_usd
FROM orders o
JOIN currency_rates FOR SYSTEM_TIME AS OF o.order_time AS r
    ON o.currency = r.currency;

-- Flink SQL: Lookup Join (external table)
SELECT 
    o.order_id,
    o.customer_id,
    c.customer_name,
    c.tier
FROM orders o
JOIN customer_dim FOR SYSTEM_TIME AS OF o.proc_time AS c
    ON o.customer_id = c.customer_id;
```

---

## 11. Kafka Streams vs Flink vs Spark Streaming

```
┌──────────────────┬────────────────┬────────────────┬────────────────┐
│ Feature          │ Kafka Streams  │ Apache Flink   │ Spark Streaming│
├──────────────────┼────────────────┼────────────────┼────────────────┤
│ Processing model │ Event-at-a-time│ Event-at-a-time│ Micro-batch    │
│ Deployment       │ Library (embed)│ Cluster        │ Cluster        │
│ Latency          │ ms             │ ms             │ seconds-minutes│
│ State backend    │ RocksDB        │ RocksDB/HashMap│ HDFS/S3        │
│ State size       │ TB (local disk)│ TB (checkpoint)│ Limited        │
│ Exactly-once     │ Yes            │ Yes (2PC)      │ Yes (idempotent│
│ Checkpointing    │ Changelog topic│ Chandy-Lamport │ WAL/checkpoint │
│ Windowing        │ Time, Session  │ All types      │ Time-based     │
│ SQL support      │ ksqlDB         │ Full SQL       │ Full SQL       │
│ CEP              │ No             │ Yes            │ No             │
│ Source/Sink      │ Kafka only     │ Any            │ Any            │
│ Scaling          │ Add instances  │ Change parallel│ Change executors│
│ Ordering         │ Per partition  │ Per key        │ Per partition  │
│ Backpressure     │ Implicit       │ Credit-based   │ Rate limiting  │
│ Resource mgmt    │ App-managed    │ YARN/K8s/Stand │ YARN/K8s/Stand │
│ Complexity       │ Low            │ High           │ Medium         │
│ Best for         │ Kafka-centric  │ Complex event  │ Unified batch+ │
│                  │ microservices  │ processing     │ stream         │
│ Fault tolerance  │ Changelog      │ Distributed    │ Micro-batch    │
│                  │ replay         │ snapshots      │ replay         │
│ Testing          │ TopologyTest   │ MiniCluster    │ StreamingQuery │
│ Community        │ Confluent      │ Apache/Alibaba │ Databricks     │
└──────────────────┴────────────────┴────────────────┴────────────────┘

Decision guide:
  Kafka-only, microservices, embedded → Kafka Streams
  Complex stateful processing, CEP, SQL → Flink
  Unified batch+streaming, existing Spark → Spark Structured Streaming
  Simple transformations, serverless → AWS Lambda / Cloud Functions
```

---

## 12. Real-time Analytics

### Approximate Algorithms

```
HYPERLOGLOG (Cardinality Estimation):
  Problem: COUNT(DISTINCT user_id) on billions of events
  Exact: Requires storing ALL unique values (memory intensive)
  HLL: Uses hash function + register tracking
  
  Accuracy: ~2% error with 12KB memory
  Memory:   O(1) vs O(n) for exact
  
  Use: Unique visitors, distinct counts
  Support: Redis, Druid, Flink, Spark, ClickHouse

COUNT-MIN SKETCH (Frequency Estimation):
  Problem: Frequency of each item in stream
  Exact: Hash map of all items
  CMS: Matrix of counters with multiple hash functions
  
  Accuracy: Over-estimates (never under-estimates)
  Memory:   O(1) vs O(n) for exact
  
  Use: Top-K items, heavy hitters, spam detection

T-DIGEST (Percentile Estimation):
  Problem: p99 latency across billions of requests
  Exact: Sort all values (impossible in streaming)
  T-Digest: Adaptive cluster-based estimation
  
  Accuracy: Very accurate at tails (p99, p999)
  Memory:   ~10KB for accurate percentiles
  
  Use: Latency percentiles, SLA monitoring

BLOOM FILTER (Membership Test):
  Problem: Has this event been seen before?
  Exact: Store all event IDs (memory intensive)
  Bloom: Bit array with multiple hash functions
  
  False positive: Possible (says "yes" when "no")
  False negative: Never (if says "no", definitely "no")
  
  Use: Deduplication, cache miss reduction
```

---

## 13. Event Sourcing and CQRS

### Event Sourcing Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    EVENT SOURCING                                  │
│                                                                    │
│  Commands:                                                        │
│  ┌──────────────┐                                                │
│  │ PlaceOrder   │─┐                                              │
│  │ CancelOrder  │─┤                                              │
│  │ UpdateItem   │─┤                                              │
│  └──────────────┘ │                                              │
│                    ▼                                              │
│  ┌──────────────────────────────────────────────────┐            │
│  │              EVENT STORE (Kafka)                   │            │
│  │                                                    │            │
│  │  OrderPlaced(id=1, items=[A,B], total=100)         │            │
│  │  OrderItemUpdated(id=1, item=A, qty=2)             │            │
│  │  OrderShipped(id=1, tracking=ABC)                  │            │
│  │  OrderDelivered(id=1, time=...)                    │            │
│  │                                                    │            │
│  │  IMMUTABLE, APPEND-ONLY                            │            │
│  └─────────────┬────────────────────────────────────┘            │
│                 │                                                  │
│        ┌────────┼────────┐                                       │
│        ▼        ▼        ▼                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │Projection│ │Projection│ │Projection│                        │
│  │  Orders  │ │ Analytics│ │  Search  │                        │
│  │ (RDBMS)  │ │ (OLAP)   │ │ (Elastic)│                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
│                                                                    │
│  Current state = replay(all events for entity)                    │
│  or use snapshots + events since snapshot                         │
└──────────────────────────────────────────────────────────────────┘
```

### CQRS (Command Query Responsibility Segregation)

```
┌──────────────────────────────────────────────────────────────────┐
│                         CQRS                                      │
│                                                                    │
│  WRITE SIDE:                    READ SIDE:                        │
│  ┌──────────────┐              ┌──────────────┐                  │
│  │  Command API  │              │   Query API   │                  │
│  │  (validate,   │              │   (fast reads) │                  │
│  │   process)    │              │               │                  │
│  └──────┬───────┘              └──────┬───────┘                  │
│         │                              ▲                          │
│         ▼                              │                          │
│  ┌──────────────┐    ┌──────────┐    ┌──────────────┐           │
│  │ Write DB     │───▶│  Event   │───▶│ Read DB      │           │
│  │ (normalized) │    │  Stream  │    │ (denormalized)│           │
│  │ PostgreSQL   │    │  (Kafka) │    │ Redis/Elastic │           │
│  └──────────────┘    └──────────┘    └──────────────┘           │
│                                                                    │
│  Benefits:                                                        │
│  - Independent scaling of reads and writes                        │
│  - Optimized read models for each query pattern                  │
│  - Event stream enables multiple projections                      │
│  - Audit trail via event log                                     │
│                                                                    │
│  Challenges:                                                      │
│  - Eventual consistency between write and read sides              │
│  - Increased complexity                                           │
│  - Event schema evolution                                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 14. Deployment Patterns

### Pattern Comparison

```
EMBEDDED (Kafka Streams):
  App instance = stream processor
  ┌──────────────┐  ┌──────────────┐
  │  App Pod 1   │  │  App Pod 2   │
  │  ┌────────┐  │  │  ┌────────┐  │
  │  │ KStreams│  │  │  │ KStreams│  │
  │  │ P0, P1 │  │  │  │ P2, P3 │  │
  │  └────────┘  │  │  └────────┘  │
  └──────────────┘  └──────────────┘
  Scale: Kubernetes HPA / ECS autoscaling
  Pros: Simple deployment, no cluster management
  Cons: Kafka-only, state recovery on pod restart

CLUSTER-BASED (Flink, Spark):
  Dedicated compute cluster
  ┌──────────────────────────────────┐
  │  Flink Cluster                    │
  │  ┌────────┐  ┌──────┐  ┌──────┐│
  │  │ JobMgr │  │ TM 1 │  │ TM N ││
  │  └────────┘  └──────┘  └──────┘│
  └──────────────────────────────────┘
  Scale: Add TaskManagers, change parallelism
  Pros: Rich features, any source/sink, large state
  Cons: Operational complexity, cluster management

SERVERLESS (AWS Lambda, Cloud Functions):
  Event-triggered, auto-scaled
  ┌──────┐  ┌──────┐  ┌──────┐
  │ λ    │  │ λ    │  │ λ    │
  │ func │  │ func │  │ func │
  └──────┘  └──────┘  └──────┘
  Scale: Automatic (per event)
  Pros: Zero ops, pay-per-use
  Cons: No state, 15min timeout, cold starts, limited

CONTAINER-NATIVE (K8s-based):
  ┌──────────────────────────────────┐
  │  Kubernetes                       │
  │  ┌──────────────────────────┐    │
  │  │ Flink Kubernetes Operator │    │
  │  │ Auto-manages Flink jobs   │    │
  │  │ Savepoint on upgrade      │    │
  │  │ Auto-scaling              │    │
  │  └──────────────────────────┘    │
  └──────────────────────────────────┘
  Best of cluster + container: managed lifecycle, native scaling
```

---

## Production Checklist

```
[ ] Choose architecture: Lambda vs Kappa (prefer Kappa for new systems)
[ ] Define time semantics: Event time with watermarks (not processing time)
[ ] Set watermark strategy: BoundedOutOfOrderness with appropriate tolerance
[ ] Handle late data: Allowed lateness + side output for very late events
[ ] Exactly-once: Idempotent sinks OR transactional processing
[ ] State management: RocksDB for large state, incremental checkpoints
[ ] Backpressure monitoring: Track backpressure metrics per operator
[ ] Window selection: Match business requirements (tumbling vs session)
[ ] Join strategy: Use temporal joins for time-versioned lookups
[ ] Schema evolution: Schema registry with compatibility checks
[ ] Dead letter queue: Route unparseable/bad records to DLQ
[ ] Monitoring: Consumer lag, processing latency, checkpoint duration
[ ] Scaling: Auto-scale based on lag/throughput metrics
[ ] DR: Multi-DC replication (MirrorMaker 2 / Cluster Linking)
```
