# Architecture 03: Real-Time Analytics Platform

## Design Goals

```
WHAT WE'RE BUILDING:
════════════════════
A real-time analytics platform that:
  • Ingests 500K-2M events/sec from multiple sources
  • Provides SUB-SECOND query latency on fresh data (< 5 sec freshness)
  • Supports concurrent dashboard users (1000+ simultaneous)
  • Handles both time-series aggregations and dimensional queries
  • Scales horizontally without downtime

USE CASES:
  • Real-time dashboard: "Revenue in last 5 minutes by region"
  • Operational monitoring: "Error rate by service in last 60 seconds"
  • User-facing analytics: "Your campaign performance right now"
  • Anomaly detection: "Alert when metric deviates 3 sigma from baseline"

WHY NOT BATCH?
  Batch (Spark → Warehouse): 15-60 min freshness, fine for historical
  Real-time: < 5 sec freshness, needed for operational decisions

  "Should we pause this ad campaign?" → Can't wait 30 min for batch.
  "Is this deploy causing errors?" → Need seconds, not hours.
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME ANALYTICS PLATFORM                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INGESTION                                                                   │
│  ═════════                                                                   │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ App Events   │  │ Clickstream  │  │ Server Logs  │                      │
│  │ (Protobuf)   │  │ (JSON)       │  │ (Structured) │                      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
│         │                  │                  │                               │
│         ▼                  ▼                  ▼                               │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  KAFKA (Event Bus)                                               │        │
│  │  • 12 brokers, 3 AZs                                            │        │
│  │  • Topics: events.app, events.click, events.logs                 │        │
│  │  • Partitions: 48-96 per topic (matched to downstream consumers) │        │
│  │  • Retention: 7 days (replay buffer)                             │        │
│  │  • Throughput: 2M msgs/sec sustained, 5M burst                   │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  STREAM PROCESSING               │                                           │
│  ═════════════════               │                                           │
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  FLINK (Stream Processor)                                        │        │
│  │                                                                  │        │
│  │  Job 1: Event Enrichment                                         │        │
│  │    • Join events with dimension data (user, product, geo)        │        │
│  │    • Lookup from Redis/RocksDB state backend                     │        │
│  │    • Output: enriched events (Kafka → OLAP)                      │        │
│  │                                                                  │        │
│  │  Job 2: Real-Time Aggregations                                   │        │
│  │    • Tumbling windows: 1 min, 5 min, 1 hour                     │        │
│  │    • Revenue, orders, errors by dimension                        │        │
│  │    • Output: pre-aggregated rows → OLAP                          │        │
│  │                                                                  │        │
│  │  Job 3: Anomaly Detection                                        │        │
│  │    • Rolling stats (mean, stddev) per metric                     │        │
│  │    • Alert when value > mean + 3*stddev                          │        │
│  │    • Output: alerts → PagerDuty/Slack                            │        │
│  │                                                                  │        │
│  │  Config: 32 TaskManagers × 8 slots = 256 parallel tasks          │        │
│  │  State backend: RocksDB (for large state, e.g., joins)           │        │
│  │  Checkpointing: Every 30 sec, exactly-once                       │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  OLAP SERVING                    │                                           │
│  ════════════                    ▼                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  OPTION A: Apache Pinot (Preferred for user-facing)              │        │
│  │  ─────────────────────────────────────────────────               │        │
│  │  • Real-time ingestion from Kafka (< 1 sec latency)             │        │
│  │  • Star-tree index for pre-aggregation                           │        │
│  │  • Handles 10,000+ QPS at P99 < 100ms                           │        │
│  │  • Multi-tenant isolation                                        │        │
│  │  • Segments: Real-time (mutable) + Offline (immutable, compact)  │        │
│  │                                                                  │        │
│  │  Cluster: 6 servers, 3 brokers, 3 controllers                   │        │
│  │  Storage: 500 GB SSD per server (recent data)                    │        │
│  │           + S3 deep storage (historical)                         │        │
│  │                                                                  │        │
│  ├─────────────────────────────────────────────────────────────────┤        │
│  │  OPTION B: ClickHouse (Preferred for internal analytics)         │        │
│  │  ───────────────────────────────────────────────────             │        │
│  │  • MergeTree engine with ORDER BY for fast scans                 │        │
│  │  • Materialized views for pre-aggregation                        │        │
│  │  • Kafka table engine (direct ingestion)                         │        │
│  │  • Handles complex SQL (JOINs, subqueries, window functions)     │        │
│  │  • Compression: 10-20x (columnar + LZ4/ZSTD)                    │        │
│  │                                                                  │        │
│  │  Cluster: 3 shards × 2 replicas = 6 nodes                       │        │
│  │  Storage: 2 TB NVMe per node                                     │        │
│  │                                                                  │        │
│  ├─────────────────────────────────────────────────────────────────┤        │
│  │  OPTION C: Apache Druid (Balanced)                               │        │
│  │  ─────────────────────────────────                               │        │
│  │  • Real-time + batch ingestion                                   │        │
│  │  • Bitmap indexes on dimensions                                  │        │
│  │  • Good for time-series + dimensional queries                    │        │
│  │  • More complex to operate than Pinot/ClickHouse                 │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  QUERY LAYER                                                                 │
│  ═══════════                                                                 │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ Grafana      │  │ Custom UI    │  │ REST API     │                      │
│  │ (Internal)   │  │ (User-facing)│  │ (Programmatic│                      │
│  │              │  │              │  │  access)     │                      │
│  │ Ops metrics  │  │ Campaign     │  │ ML pipeline  │                      │
│  │ dashboards   │  │ analytics    │  │ integration  │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## OLAP Engine Decision Matrix

```
┌────────────────────┬───────────────────┬───────────────────┬────────────────┐
│                    │ Apache Pinot       │ ClickHouse         │ Apache Druid   │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Best for           │ User-facing        │ Internal analytics │ Time-series    │
│                    │ high-concurrency   │ complex SQL        │ + dimensions   │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Ingestion latency  │ < 1 sec           │ 1-5 sec           │ 1-10 sec       │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Query latency P99  │ < 100ms           │ < 500ms           │ < 200ms        │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Concurrency        │ 10,000+ QPS       │ 100-500 QPS       │ 1,000+ QPS    │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ SQL support        │ Limited (no JOINs)│ Full ANSI SQL     │ Limited SQL    │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ JOINs             │ No (pre-join)     │ Yes (distributed) │ Limited        │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Mutable data       │ Yes (upserts)     │ ReplacingMergeTree│ No             │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Operational cost   │ Medium            │ Low-Medium        │ High           │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Used by            │ LinkedIn, Uber,   │ Cloudflare, Uber, │ Airbnb, Netflix│
│                    │ Stripe, Doordash  │ eBay, Lyft        │ Walmart        │
├────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Cloud managed      │ StarTree          │ ClickHouse Cloud  │ Imply          │
└────────────────────┴───────────────────┴───────────────────┴────────────────┘

DECISION RULE:
  User-facing analytics (10K+ QPS, simple queries) → Pinot
  Internal analytics (complex SQL, ad-hoc, JOINs)  → ClickHouse
  Time-series primary + some dimensions             → Druid

  If unsure → ClickHouse (most versatile, easiest to start)
```

## Scalability Deep Dive

```
BOTTLENECK ANALYSIS AT 2M EVENTS/SEC:
═════════════════════════════════════

1. KAFKA THROUGHPUT:
   2M msgs/sec × 500 bytes avg = 1 GB/sec
   Per broker: 1 GB / 12 brokers = 83 MB/sec (well within limits)
   Network: 10 Gbps NIC → 1.25 GB/sec per broker (fine)
   Disk: 3 × NVMe → 6 GB/sec write throughput (fine)
   
   SCALING TRIGGER: When broker CPU > 70% or disk utilization > 60%
   ACTION: Add brokers + rebalance partitions

2. FLINK THROUGHPUT:
   2M events/sec ÷ 256 tasks = ~8,000 events/task/sec
   Per event processing: ~0.1ms (lookup + transform)
   Utilization: 8000 × 0.1ms = 800ms / 1000ms = 80% (at limit!)
   
   SCALING TRIGGER: Backpressure > 0.5 on any operator
   ACTION: Increase parallelism (add TaskManagers or slots)
   
   STATE SIZE (for enrichment joins):
   10M users × 500 bytes = 5 GB in RocksDB state
   RocksDB: SSD-backed, handles 50+ GB without issue
   Checkpoint: 5 GB state → ~10 sec checkpoint (acceptable)

3. PINOT/CLICKHOUSE INGESTION:
   2M events/sec × 500 bytes = 1 GB/sec into OLAP
   Pinot: 6 servers → 166 MB/sec each (within capacity)
   Segment creation: Every 1 min (micro-batch within Pinot)
   
   SCALING TRIGGER: Segment build time > 80% of interval
   ACTION: Add Pinot servers (linear scaling)

4. QUERY SERVING:
   10,000 QPS on Pinot cluster
   Per query: Scan 1-5 segments, aggregate, return
   Avg query time: 20ms
   Capacity: 6 servers × (1000ms / 20ms) × 8 threads = 2,400 QPS/server
   Total: 14,400 QPS capacity (headroom: 44%)
   
   SCALING TRIGGER: P99 latency > 100ms
   ACTION: Add brokers/servers, or pre-aggregate (star-tree)

COST AT SCALE (2M events/sec):
  Kafka (12 i3.xlarge): 12 × $0.312/hr × 24 × 365 = $32,800/yr
  Flink (32 m5.2xlarge): 32 × $0.384/hr × 24 × 365 = $107,700/yr
  Pinot (6 r5.4xlarge): 6 × $1.008/hr × 24 × 365 = $52,900/yr
  Total: ~$195,000/year for 2M events/sec real-time analytics
```

## Data Freshness Guarantees

```
END-TO-END LATENCY BREAKDOWN:
═════════════════════════════

Event occurs           t=0
Producer batches       t=0 to t=100ms (linger.ms=100)
Kafka write + ack      t=100ms to t=110ms
Flink reads from Kafka t=110ms to t=200ms (poll interval)
Flink processing       t=200ms to t=250ms
Flink writes to Kafka  t=250ms to t=350ms (output topic)
Pinot ingests          t=350ms to t=1,350ms (real-time segment)
Query sees data        t=1,350ms to t=1,500ms

TOTAL: ~1.5 seconds end-to-end (event to queryable)

GUARANTEE: 95th percentile < 3 seconds, 99th < 5 seconds

MONITORING:
  Metric: "ingestion_lag_seconds" = now() - max(event_time) in OLAP
  Alert: If lag > 10 seconds for 2 minutes → P2 incident
  Alert: If lag > 60 seconds → P1 (pipeline broken)
```

## High Availability

```
FAILURE SCENARIOS:
═════════════════

Kafka broker dies:
  → Replicas in other AZs take over (ISR)
  → Producer retries to new leader
  → Consumer rebalances to healthy brokers
  → Downtime: 0 (if ISR > 1)

Flink TaskManager dies:
  → Job restarts from last checkpoint (30 sec old)
  → Reprocesses 30 sec of Kafka data (exactly-once via 2PC)
  → Downtime: 30-60 sec (checkpoint restore + catch up)

Pinot server dies:
  → Replica takes over (if replication factor > 1)
  → Queries route to healthy servers
  → Downtime: 0 for queries, ingestion catches up in minutes

Full AZ outage:
  → Kafka: 2/3 AZs still have data (min.insync.replicas=2)
  → Flink: Reschedules on remaining AZ nodes
  → Pinot: Replicas serve from other AZs
  → Impact: Reduced capacity (~33%), no data loss
```
