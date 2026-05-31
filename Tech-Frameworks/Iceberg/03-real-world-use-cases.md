# Apache Iceberg — Real-World Use Cases & Industry Examples

## Netflix: The Origin Story

Netflix created Iceberg to solve critical problems with their 10,000+ Hive tables on S3.

### The Problem

```
┌───────────────────────────────────────────────────────────────┐
│  NETFLIX BEFORE ICEBERG (2016)                                 │
│                                                                │
│  Table: viewing_history (partitioned by date, region)          │
│  Size: 1.5 PB across 50,000+ partitions                       │
│                                                                │
│  Simple query: SELECT COUNT(*) FROM viewing_history            │
│                WHERE date = '2024-01-15'                       │
│                                                                │
│  Hive behavior:                                                │
│  1. LIST s3://warehouse/viewing_history/              (500ms)  │
│  2. LIST s3://warehouse/viewing_history/date=2024-01-15/       │
│  3. For each file found, HEAD to get size             (50ms×N) │
│  4. Total: 2000+ S3 requests just to PLAN the query           │
│                                                                │
│  Cost: $50K+/month in S3 LIST requests alone                  │
│  Latency: 30+ seconds for query planning                      │
└───────────────────────────────────────────────────────────────┘
```

### The Solution

```
┌───────────────────────────────────────────────────────────────┐
│  NETFLIX WITH ICEBERG                                          │
│                                                                │
│  Same query: SELECT COUNT(*) FROM viewing_history              │
│              WHERE date = '2024-01-15'                         │
│                                                                │
│  Iceberg behavior:                                             │
│  1. GET metadata/v1024.metadata.json            (100ms)       │
│  2. GET metadata/snap-latest.avro               (100ms)       │
│  3. GET metadata/manifest-xyz.avro              (100ms)       │
│     → manifest says: 47 files for date=2024-01-15             │
│     → total records: 2.1 billion (from manifest stats)        │
│  4. Answer: 2,100,000,000 ← NO data file reads needed!       │
│                                                                │
│  Cost: $0.001 per query (3 GET requests)                      │
│  Latency: 300ms for query planning                            │
└───────────────────────────────────────────────────────────────┘
```

### Netflix Use Cases

| Use Case | Table | Size | Why Iceberg? |
|----------|-------|------|-------------|
| Viewing analytics | `viewing_history` | 1.5 PB | Time travel for A/B test analysis |
| Content recommendations | `user_interactions` | 800 TB | Schema evolution as new features added |
| Encoding decisions | `encoding_metadata` | 200 TB | Partition evolution (monthly → daily) |
| QoE monitoring | `streaming_quality` | 500 TB | Real-time + batch on same table |
| Financial reporting | `revenue_events` | 100 TB | Audit trail with snapshot history |

---

## Apple: Privacy-Preserving Analytics at Scale

Apple uses Iceberg for privacy-focused analytics across billions of devices.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  APPLE ICEBERG ARCHITECTURE                                  │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ iPhone/Mac   │    │ Differential │    │ Aggregation  │  │
│  │ Telemetry    │───▶│ Privacy      │───▶│ Pipeline     │  │
│  │ (billions)   │    │ Layer        │    │ (Flink)      │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘  │
│                                                  │          │
│                                          ┌───────▼───────┐  │
│                                          │ Iceberg Table │  │
│                                          │ on S3         │  │
│                                          │               │  │
│                                          │ • 10+ PB      │  │
│                                          │ • 1M+ files   │  │
│                                          │ • Daily ingest│  │
│                                          └───────┬───────┘  │
│                                                  │          │
│                              ┌───────────────────┼──────┐   │
│                              │                   │      │   │
│                        ┌─────▼──┐  ┌─────────▼┐ ┌──▼──┐   │
│                        │ Spark  │  │ Presto   │ │ ML  │   │
│                        │ Batch  │  │ Ad-hoc   │ │     │   │
│                        └────────┘  └──────────┘ └─────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Why Iceberg for Apple?

1. **Schema Evolution**: New device types (Vision Pro) add new telemetry columns without rewriting PBs of historical data
2. **Partition Evolution**: Migrated from `month/device_type` to `day/device_type/os_version` without reprocessing
3. **Time Travel**: Reproduce any ML model's training data exactly as it was at training time
4. **Multi-engine**: Flink writes streaming data, Spark runs batch ML, Presto serves dashboards

---

## LinkedIn: Real-Time + Batch Unified Analytics

LinkedIn processes trillions of events through Iceberg tables.

### Event Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  LINKEDIN EVENT PROCESSING WITH ICEBERG                          │
│                                                                   │
│  ┌──────────────┐                                                │
│  │ User Actions │    ┌─────────────┐    ┌──────────────────┐    │
│  │ (clicks,     │───▶│ Kafka       │───▶│ Flink Streaming  │    │
│  │  views,      │    │ (50M msgs/s)│    │ Job              │    │
│  │  searches)   │    └─────────────┘    └────────┬─────────┘    │
│  └──────────────┘                                │              │
│                                                  │              │
│                                    ┌─────────────▼─────────────┐│
│                                    │  Iceberg Table:            ││
│                                    │  member_activity_events    ││
│                                    │                            ││
│                                    │  Partitioned by:           ││
│                                    │    hours(event_time),      ││
│                                    │    bucket(16, member_id)   ││
│                                    │                            ││
│                                    │  Size: 2 PB               ││
│                                    │  Daily ingest: 50 TB      ││
│                                    │  Files: 5M+               ││
│                                    └─────────────┬─────────────┘│
│                                                  │              │
│                    ┌─────────────┬───────────────┼──────┐       │
│                    │             │               │      │       │
│              ┌─────▼───┐  ┌─────▼───┐  ┌───────▼┐  ┌──▼───┐  │
│              │ Spark   │  │ Trino   │  │ Flink  │  │ ML   │  │
│              │ Batch   │  │ Ad-hoc  │  │ Stream │  │ Train│  │
│              │ (daily  │  │ (analyst│  │ (real- │  │      │  │
│              │  agg)   │  │  query) │  │  time) │  │      │  │
│              └─────────┘  └─────────┘  └────────┘  └──────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### LinkedIn's Key Patterns

| Pattern | Implementation | Benefit |
|---------|---------------|---------|
| **Streaming ingestion** | Flink writes micro-batches every 1 minute | Near-real-time data availability |
| **Bucketed partitioning** | `bucket(16, member_id)` | Even file sizes, no hot partitions |
| **Compaction** | Hourly compaction job merges small files | Better read performance |
| **Time travel** | 7-day snapshot retention | Debug data pipeline issues |
| **Schema evolution** | Add columns for new event types weekly | No downtime, no migration |

---

## Shopify: E-Commerce Analytics

### Order Analytics Platform

```
┌─────────────────────────────────────────────────────────────┐
│  SHOPIFY ORDER ANALYTICS                                     │
│                                                              │
│  Tables:                                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ orders_raw (Iceberg)                                 │    │
│  │ • Every order event (created, paid, shipped, etc.)  │    │
│  │ • Partitioned: days(event_time), bucket(merchant_id)│    │
│  │ • 500 TB, 90-day retention active, 7-year archive   │    │
│  └────────────────────────────┬────────────────────────┘    │
│                               │                              │
│  ┌────────────────────────────▼────────────────────────┐    │
│  │ orders_aggregated (Iceberg)                          │    │
│  │ • Daily merchant summaries                           │    │
│  │ • Partitioned: days(agg_date)                       │    │
│  │ • Computed by Spark from orders_raw                  │    │
│  │ • 50 TB                                             │    │
│  └────────────────────────────┬────────────────────────┘    │
│                               │                              │
│  ┌────────────────────────────▼────────────────────────┐    │
│  │ Merchant Dashboard (Trino/Presto queries)            │    │
│  │ • "How are my sales today vs last week?"            │    │
│  │ • Time travel: compare snapshot at midnight vs now  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Why Iceberg for E-Commerce?

1. **Late-arriving data**: Orders can be updated days later (refunds, chargebacks). Iceberg handles UPSERT via merge-on-read.
2. **Multi-tenant isolation**: Partition by merchant prevents noisy neighbor issues in queries.
3. **Regulatory compliance**: 7-year data retention with Glacier archival, accessible via time travel.
4. **Schema changes**: New payment methods, new order fields added without table rebuild.

---

## Uber: Geospatial & Pricing Analytics

### Ride Pricing Data Lake

```
┌─────────────────────────────────────────────────────────────────┐
│  UBER PRICING ANALYTICS                                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ trip_events (Iceberg on S3)                             │     │
│  │                                                         │     │
│  │ Schema:                                                 │     │
│  │   trip_id UUID                                          │     │
│  │   rider_id UUID                                         │     │
│  │   driver_id UUID                                        │     │
│  │   pickup_location STRUCT<lat: DOUBLE, lng: DOUBLE>      │     │
│  │   dropoff_location STRUCT<lat: DOUBLE, lng: DOUBLE>     │     │
│  │   surge_multiplier DECIMAL(4,2)                         │     │
│  │   base_fare DECIMAL(10,2)                               │     │
│  │   final_fare DECIMAL(10,2)                              │     │
│  │   event_time TIMESTAMP                                  │     │
│  │                                                         │     │
│  │ Partition: days(event_time), bucket(64, city_id)        │     │
│  │ Size: 3 PB                                              │     │
│  │ Daily ingest: 100 TB                                    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  Consumers:                                                       │
│  ├─ Pricing ML model training (Spark + PyTorch)                  │
│  ├─ Surge pricing analysis (Trino ad-hoc queries)                │
│  ├─ Real-time ETL (Flink streaming enrichment)                   │
│  ├─ Regulatory reporting (exact historical snapshots)            │
│  └─ Driver earnings analytics (Spark batch jobs)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Uber's Iceberg Benefits

| Requirement | How Iceberg Solves It |
|-------------|----------------------|
| Regulatory audit | Time travel to reproduce any historical fare calculation |
| Multi-city schema | Schema evolution adds city-specific fields without migration |
| Massive scale | 3 PB table with sub-second query planning |
| Fair pricing proof | Snapshot at any timestamp shows exact surge state |
| ML reproducibility | Pin training data to specific snapshot ID |

---

## Stripe: Financial Transaction Ledger

### Payment Event Store

```
┌─────────────────────────────────────────────────────────────┐
│  FINANCIAL LEDGER USE CASE                                   │
│                                                              │
│  Requirements:                                               │
│  • Immutable audit trail of every transaction                │
│  • Exact reproducibility of any financial report             │
│  • 7-year retention for compliance                           │
│  • Sub-second query for recent data, acceptable delay for    │
│    historical                                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ payment_events (Iceberg)                             │    │
│  │                                                      │    │
│  │ Properties:                                          │    │
│  │   write.format.default = parquet                     │    │
│  │   write.parquet.compression-codec = zstd             │    │
│  │   write.metadata.delete-after-commit.enabled = true  │    │
│  │   history.expire.max-snapshot-age-ms = 604800000     │    │
│  │                                                      │    │
│  │ Partition spec:                                      │    │
│  │   days(created_at), bucket(32, merchant_id)          │    │
│  │                                                      │    │
│  │ Storage tiering:                                     │    │
│  │   0-30 days:  S3 Standard    (hot queries)          │    │
│  │   30-90 days: S3 Standard-IA (monthly reports)      │    │
│  │   90+ days:   Glacier Instant (compliance/audit)    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Query patterns:                                             │
│  • Daily reconciliation (Spark batch, T+1)                  │
│  • Merchant dashboard (Trino, last 30 days)                 │
│  • Audit query (Spark, any point in history)                │
│  • Fraud ML training (Spark + snapshot pinning)             │
└─────────────────────────────────────────────────────────────┘
```

### Immutability for Financial Compliance

```sql
-- Reproduce exact financial report from Q3 2023
SELECT 
  merchant_id,
  SUM(amount) as total_volume,
  COUNT(*) as transaction_count
FROM payment_events
FOR SYSTEM_TIME AS OF TIMESTAMP '2023-09-30 23:59:59'
WHERE created_at BETWEEN '2023-07-01' AND '2023-09-30'
GROUP BY merchant_id;

-- This returns EXACTLY what the Q3 report showed,
-- even if data was corrected later in Q4
```

---

## Spotify: Music Streaming Analytics

### Listening Event Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  SPOTIFY STREAMING ANALYTICS                                     │
│                                                                   │
│  Scale:                                                           │
│  • 600M+ monthly active users                                    │
│  • 2B+ listening events per day                                  │
│  • 100+ TB daily ingestion                                       │
│                                                                   │
│  ┌─────────┐     ┌─────────┐     ┌────────────────────────┐    │
│  │ Mobile  │     │ Kafka   │     │ Flink                  │    │
│  │ Client  │────▶│ Streams │────▶│ (dedup, enrich,        │    │
│  │ Events  │     │         │     │  sessionize)           │    │
│  └─────────┘     └─────────┘     └───────────┬────────────┘    │
│                                               │                  │
│                                     ┌─────────▼─────────┐       │
│                                     │ listening_sessions │       │
│                                     │ (Iceberg on S3)    │       │
│                                     │                    │       │
│                                     │ Partitioned by:    │       │
│                                     │  days(session_end),│       │
│                                     │  country_code      │       │
│                                     └─────────┬──────────┘       │
│                                               │                  │
│          ┌────────────┬───────────────────────┼──────────┐       │
│          │            │                       │          │       │
│    ┌─────▼────┐ ┌─────▼────┐ ┌──────────────▼┐ ┌──────▼────┐  │
│    │ Royalty  │ │ Recommend│ │ Artist        │ │ Podcast  │  │
│    │ Calc     │ │ ML Model │ │ Dashboard     │ │ Analytics│  │
│    │ (Spark)  │ │ Training │ │ (Trino)       │ │ (Spark)  │  │
│    └──────────┘ └──────────┘ └───────────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Consumer Pattern

| Consumer | Engine | Access Pattern | Iceberg Feature Used |
|----------|--------|---------------|---------------------|
| Royalty calculation | Spark | Full table scan monthly | Snapshot pinning for reproducible payments |
| Recommendations | Spark + PyTorch | Last 30 days, sampled | Partition pruning + sampling |
| Artist dashboard | Trino | Last 7 days, filtered by artist | Column stats for file skipping |
| Podcast analytics | Spark | Streaming + batch join | Same table for both workloads |
| Wrapped (year-end) | Spark | Full year scan | Time travel to year boundary |

---

## Cross-Industry Pattern Summary

### When to Use Iceberg

| Signal | Example | Why Iceberg? |
|--------|---------|-------------|
| **Data > 1 TB** | Any analytical dataset at scale | Metadata-driven pruning saves time and money |
| **Multiple consumers** | ML + dashboards + reports | Engine-agnostic format |
| **Schema changes** | Adding new event types monthly | Column ID-based evolution |
| **Audit requirements** | Financial, healthcare, legal | Time travel = exact historical state |
| **Streaming + batch** | Real-time + daily aggregation | Same table for both |
| **Cost sensitivity** | Large S3 bills from LIST ops | 100-1000x fewer S3 requests |
| **Data corrections** | Late-arriving records, fixes | ACID updates without corruption |
| **Multi-year retention** | Compliance, historical analysis | Lifecycle tiering (Standard → Glacier) |

### When NOT to Use Iceberg

| Situation | Better Alternative | Why |
|-----------|-------------------|-----|
| Sub-millisecond lookups | Redis, DynamoDB | Iceberg is for analytics, not OLTP |
| Small datasets (<10 GB) | PostgreSQL, SQLite | Overhead not justified |
| Simple key-value access | DynamoDB, Cassandra | Iceberg is columnar, not key-value |
| Real-time streaming only | Kafka, Kinesis | Iceberg has commit latency (seconds) |
| Graph queries | Neo4j, Neptune | Wrong data model |
| Full-text search | Elasticsearch, OpenSearch | Wrong query model |

---

## Production Deployment Patterns

### Pattern 1: Lambda Architecture Replacement

```
BEFORE (Lambda):                    AFTER (Iceberg):
┌─────────────────────┐            ┌─────────────────────┐
│ Batch Layer (Spark)  │            │                     │
│   → batch_table     │            │ Single Iceberg Table │
├─────────────────────┤            │ • Flink writes      │
│ Speed Layer (Storm)  │    ──▶    │   streaming         │
│   → realtime_view   │            │ • Spark runs batch  │
├─────────────────────┤            │ • Trino queries     │
│ Serving Layer        │            │   both              │
│   → merge both      │            │                     │
└─────────────────────┘            └─────────────────────┘

Complexity: 3 systems, data reconciliation issues
vs
Simplicity: 1 table, consistent view, ACID guarantees
```

### Pattern 2: Data Mesh with Iceberg

```
┌─────────────────────────────────────────────────────────────┐
│  DATA MESH DOMAINS                                           │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │ Orders     │  │ Users      │  │ Payments           │    │
│  │ Domain     │  │ Domain     │  │ Domain             │    │
│  │            │  │            │  │                    │    │
│  │ Iceberg:   │  │ Iceberg:   │  │ Iceberg:           │    │
│  │ orders.    │  │ users.     │  │ payments.          │    │
│  │ events     │  │ profiles   │  │ transactions       │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────────────┘    │
│        │                │                │                   │
│        └────────────────┼────────────────┘                   │
│                         │                                    │
│              ┌──────────▼──────────┐                         │
│              │ Shared Catalog      │                         │
│              │ (Nessie / REST)     │                         │
│              │                     │                         │
│              │ Access control per  │                         │
│              │ domain table        │                         │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘

Each domain:
• Owns their Iceberg tables
• Publishes a "data product" (curated table with SLA)
• Controls schema evolution
• Sets retention policies
```

### Pattern 3: CDC (Change Data Capture) to Iceberg

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐
│ MySQL/   │    │ Debezium │    │ Kafka    │    │ Flink CDC    │
│ Postgres │───▶│ (CDC)    │───▶│ Topics   │───▶│ Connector    │
│ (OLTP)   │    │          │    │          │    │              │
└──────────┘    └──────────┘    └──────────┘    └──────┬───────┘
                                                       │
                                             ┌─────────▼─────────┐
                                             │ Iceberg Table      │
                                             │ (analytics copy)   │
                                             │                    │
                                             │ • Full history     │
                                             │ • ACID updates     │
                                             │ • No OLTP load     │
                                             └────────────────────┘

Benefits:
• OLTP database stays fast (no analytical queries)
• Full change history preserved in Iceberg
• Schema changes in source auto-propagate
• Multiple analytics engines can query independently
```
