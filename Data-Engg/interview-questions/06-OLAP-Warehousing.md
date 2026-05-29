# Interview Questions Set 6: OLAP, Data Warehousing & Analytics (Q151-180)

---

## Q151: Compare ClickHouse, Apache Druid, and Apache Pinot for real-time OLAP. When would you choose each?

**Answer:**

| Feature | ClickHouse | Druid | Pinot |
|---------|-----------|-------|-------|
| Developed by | Yandex | Metamarkets → Apache | LinkedIn → Apache |
| Architecture | Shared-nothing MPP | Distributed, micro-services | Distributed, micro-services |
| Ingestion | Batch + Kafka engine | Real-time (Kafka) + batch | Real-time (Kafka) + batch |
| Query latency | 50ms - 10s | 100ms - 5s | 50ms - 2s |
| Concurrency | Medium (100 QPS) | High (1000+ QPS) | Very high (10K+ QPS) |
| SQL | Full SQL | SQL (limited joins) | SQL (limited joins) |
| Joins | Yes (distributed) | Limited (lookup joins) | Limited (lookup joins) |
| Pre-aggregation | Materialized views | Roll-up at ingestion | Star-tree index |
| Exactly-once | Idempotent inserts | At-least-once (dedup by ID) | Upsert support |
| UDF | Yes (C++, JS, SQL) | Limited | Limited |
| Tiered storage | Yes | Yes (deep storage) | Yes |
| Best for | Ad-hoc analytics, logs | Time-series OLAP, dashboards | User-facing analytics |
| Users | Cloudflare, Uber | Airbnb, Netflix | LinkedIn, Uber |

**Choose ClickHouse when:**
- Need full SQL including complex JOINs
- Ad-hoc analytical queries
- Log analytics, observability
- Team comfortable with SQL-first approach

**Choose Druid when:**
- Time-series focused analytics
- High ingestion rate with immediate queryability
- Dashboard queries (low-latency, high-concurrency)
- Pre-aggregation at ingestion (roll-up)

**Choose Pinot when:**
- User-facing analytics (10K+ QPS)
- Ultra-low latency required (<100ms p99)
- LinkedIn-style analytics (who viewed your profile)
- Star-tree index for pre-aggregated metrics

---

## Q152: Explain ClickHouse's MergeTree engine family. How does it achieve fast queries?

**Answer:**

```
MergeTree Storage Engine:
┌──────────────────────────────────────────────────────────────┐
│                                                               │
│  INSERT → Data Part (immutable, sorted by ORDER BY columns)  │
│                                                               │
│  Part structure on disk:                                     │
│  /data/orders/202401_1_1_0/                                  │
│  ├── primary.idx      (sparse index: every N-th row's key)  │
│  ├── column1.bin      (compressed column data)               │
│  ├── column1.mrk2     (marks: index → data position)         │
│  ├── column2.bin                                             │
│  ├── column2.mrk2                                            │
│  ├── count.txt        (row count in part)                    │
│  └── checksums.txt                                           │
│                                                               │
│  MERGE PROCESS (background):                                 │
│  Part_1 + Part_2 + Part_3 → Merged_Part (larger, still sorted)│
│  - Deduplication (ReplacingMergeTree)                        │
│  - Aggregation (AggregatingMergeTree)                        │
│  - TTL expiration (drop expired rows)                        │
│                                                               │
│  QUERY EXECUTION:                                            │
│  1. Primary index → identify granules (8192 rows each)       │
│  2. Skip non-matching granules (index condition)             │
│  3. Read only needed columns (columnar)                      │
│  4. Decompress + filter + aggregate in vectorized fashion    │
│                                                               │
│  WHY FAST:                                                   │
│  - Columnar: Only read needed columns                        │
│  - Sorted data: Range queries skip most data via sparse index│
│  - Vectorized: Process 8192 rows at a time (SIMD)           │
│  - Compression: LZ4/ZSTD per column (high ratio)            │
│  - Data skipping: minmax/bloom indexes per granule           │
└──────────────────────────────────────────────────────────────┘
```

**MergeTree variants:**
```sql
-- ReplacingMergeTree: Dedup by ORDER BY key on merge
CREATE TABLE orders (
    order_id String,
    amount Decimal(10,2),
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY order_id;
-- Keeps latest version (by updated_at) per order_id on merge

-- AggregatingMergeTree: Pre-aggregate on merge
CREATE TABLE hourly_stats (
    hour DateTime,
    category String,
    count_state AggregateFunction(count, UInt64),
    sum_state AggregateFunction(sum, Decimal(10,2))
) ENGINE = AggregatingMergeTree()
ORDER BY (hour, category);

-- SummingMergeTree: Sum numeric columns on merge
-- CollapsingMergeTree: Cancel rows with sign column (+1/-1)
-- VersionedCollapsingMergeTree: Collapsing with version ordering
```

---

## Q153: How do you design a Snowflake data warehouse for a large enterprise?

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│                SNOWFLAKE ENTERPRISE ARCHITECTURE                   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    ORGANIZATION                            │    │
│  │  Account: Production (us-east-1)                          │    │
│  │  Account: Development (us-east-1)                         │    │
│  │  Account: Analytics (eu-west-1) [data sharing]            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  DATABASES & SCHEMAS:                                            │
│  RAW (Bronze):    raw.salesforce, raw.postgres, raw.kafka         │
│  STAGING:         staging.orders, staging.customers               │
│  ANALYTICS (Gold):analytics.fct_orders, analytics.dim_customer    │
│  SEMANTIC:        semantic.revenue_metrics (views/secure views)    │
│                                                                    │
│  VIRTUAL WAREHOUSES (Compute):                                    │
│  ┌──────────────┬──────────┬──────────────────────────────────┐  │
│  │ Warehouse    │ Size     │ Use                              │  │
│  ├──────────────┼──────────┼──────────────────────────────────┤  │
│  │ ETL_WH       │ X-Large  │ dbt runs, heavy transforms       │  │
│  │ ANALYTICS_WH │ Medium   │ Analyst queries, dashboards       │  │
│  │ DS_WH        │ Large    │ Data science, ML training         │  │
│  │ API_WH       │ Small    │ Application queries (auto-scale)  │  │
│  │ LOADING_WH   │ Large    │ COPY INTO bulk loads              │  │
│  └──────────────┴──────────┴──────────────────────────────────┘  │
│                                                                    │
│  KEY CONFIGURATIONS:                                              │
│  - Auto-suspend: 60s (analytics), 300s (ETL)                     │
│  - Auto-resume: Yes (seamless user experience)                   │
│  - Multi-cluster: Min 1, Max 5 for ANALYTICS_WH (concurrency)   │
│  - Resource monitors: Budget alerts per warehouse                 │
│  - Query timeout: 3600s for ETL, 300s for analytics              │
│                                                                    │
│  COST OPTIMIZATION:                                              │
│  - Cluster keys on large tables (500GB+) for pruning             │
│  - Materialized views for expensive aggregations                 │
│  - Search optimization for point lookups                         │
│  - Result cache (24h) for repeated queries                       │
│  - Warehouse scheduling (suspend during off-hours)               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q154: Explain BigQuery's architecture. How is it different from traditional MPP warehouses?

**Answer:**

```
┌──────────────────────────────────────────────────────────────┐
│                    BIGQUERY ARCHITECTURE                       │
│                                                               │
│  KEY DIFFERENCE: Fully separated storage and compute          │
│  No provisioning, no clusters, no warehouse sizing            │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ DREMEL (Query Engine)                                 │    │
│  │                                                       │    │
│  │  Root Server (coordinator)                            │    │
│  │       │                                               │    │
│  │  Mixer nodes (intermediate aggregation)               │    │
│  │       │                                               │    │
│  │  Leaf nodes (scan + filter + local aggregation)       │    │
│  │       │                                               │    │
│  │  Thousands of leaf nodes scale up for large queries   │    │
│  │  Tree-structured execution (not shuffle-based!)       │    │
│  └──────────────────────────────────────────────────────┘    │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────┐     │
│  │ COLOSSUS (Distributed Storage)                       │     │
│  │                                                       │     │
│  │  Capacitor format (columnar, proprietary)             │     │
│  │  Compressed + encrypted at rest                       │     │
│  │  Replicated across zones                              │     │
│  │  Separation: Storage scales independently of compute  │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ JUPITER NETWORK (1 Petabit/s bisection bandwidth)     │    │
│  │ Enables disaggregated storage-compute                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  Pricing models:                                             │
│  On-demand: $5/TB scanned (pay per query)                    │
│  Flat-rate: Reserved slots (1 slot ≈ 1 vCPU-equivalent)     │
│  Autoscaler (Editions): Baseline + burst slots               │
│                                                               │
│  Key features:                                               │
│  - Slots: Unit of compute. 2000 slots for on-demand users   │
│  - BI Engine: In-memory cache for dashboards (sub-second)    │
│  - Materialized views: Auto-refreshed, query-transparent     │
│  - Clustering: Sort data by columns (like Z-order)           │
│  - Partitioning: Time-based or integer-range                 │
└──────────────────────────────────────────────────────────────┘

vs Traditional MPP (Redshift, Teradata):
  Traditional: Fixed cluster → buy nodes → scale is manual
  BigQuery: Serverless → submit query → infrastructure scales automatically
  
  Traditional: Storage + compute co-located
  BigQuery: Storage and compute independently scalable
```

---

## Q155: How do you optimize query performance in a columnar OLAP database?

**Answer:**

```
UNIVERSAL OPTIMIZATION STRATEGIES:

1. PARTITIONING (reduce data scanned):
   -- Snowflake: Automatic clustering
   ALTER TABLE orders CLUSTER BY (order_date);
   
   -- BigQuery: Partition + Cluster
   CREATE TABLE orders
   PARTITION BY DATE(order_date)
   CLUSTER BY customer_id, status;
   
   -- ClickHouse: PARTITION BY + ORDER BY
   PARTITION BY toYYYYMM(order_date)
   ORDER BY (customer_id, order_date)

2. MATERIALIZED VIEWS (precomputed results):
   CREATE MATERIALIZED VIEW daily_revenue AS
   SELECT order_date, SUM(amount) as revenue, COUNT(*) as orders
   FROM orders
   GROUP BY order_date;
   -- Query optimizer automatically uses MV when applicable

3. PROJECTION / COLUMN SELECTION:
   -- Only SELECT needed columns (huge impact in columnar!)
   -- BAD: SELECT * FROM orders WHERE ...
   -- GOOD: SELECT order_id, amount FROM orders WHERE ...

4. PREDICATE PUSHDOWN:
   -- Filter early, before joins
   -- Use partition columns in WHERE clause
   -- Avoid functions on filtered columns:
   -- BAD:  WHERE YEAR(order_date) = 2024
   -- GOOD: WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01'

5. JOIN OPTIMIZATION:
   -- Join smaller table to larger (reduce shuffle)
   -- Use broadcast join for small dimension tables
   -- Pre-aggregate before join when possible
   -- Avoid cross joins

6. DATA TYPES:
   -- Use smallest sufficient type (INT32 vs INT64)
   -- Use ENUM/LowCardinality for repeated strings (ClickHouse)
   -- Avoid String for numeric data
```

---

## Q156-180: [OLAP & Warehousing Questions - Condensed]

**Q156:** How does Snowflake's micro-partitioning work?
- Auto-partitions into ~16MB compressed micro-partitions
- Maintains min/max metadata per micro-partition per column
- Cluster keys control sort order → better pruning
- No explicit partition management needed

**Q157:** Explain Redshift's distribution styles.
- KEY: Hash by column → co-locate join keys
- ALL: Full copy on every node → small dimension tables
- EVEN: Round-robin → no skew, no co-location
- AUTO: Redshift chooses based on table size

**Q158:** How do you handle slowly changing dimensions in a cloud warehouse?
- MERGE statement (Snowflake/BigQuery/Redshift)
- Streams + Tasks (Snowflake) for automated SCD Type 2
- dbt snapshots for automated SCD Type 2

**Q159:** Compare materialized views across Snowflake, BigQuery, and Redshift.
- Snowflake: Auto-refresh, query rewrite, incremental maintenance
- BigQuery: Auto-refresh, smart tuning, up to 20 per table
- Redshift: Manual refresh or auto-refresh, used by optimizer

**Q160:** How do you implement real-time data in a warehouse?
- Snowflake: Snowpipe (continuous micro-batch from S3/Kafka)
- BigQuery: Streaming inserts API (row-level, seconds latency)
- Redshift: Streaming ingestion from Kinesis/MSK

**Q161:** Explain cost optimization strategies for BigQuery.
- Partition and cluster tables (reduce bytes scanned)
- Use `--dry-run` to estimate query cost
- Set per-user/project query byte limits
- Prefer flat-rate for predictable workloads (>$10K/month)
- Use BI Engine for repeated dashboard queries ($$$→$)

**Q162:** How do you handle semi-structured data (JSON) in OLAP systems?
- Snowflake VARIANT type: Parse on query, or flatten to columns
- BigQuery: STRUCT and ARRAY types (fully typed nesting)
- ClickHouse: JSON type, or extract to columns with Materialized columns

**Q163:** Design a multi-tenant analytics platform using Snowflake.
- Row-level security (RBAC + row access policies)
- Separate warehouses per tenant or shared with resource monitors
- Secure data sharing for external tenants
- Reader accounts for lightweight external access

**Q164:** How do you handle ELT vs ETL in modern warehouses?
- ELT: Load raw → transform IN warehouse (leverage MPP compute)
- ETL: Transform OUTSIDE → load clean (when warehouse compute is expensive)
- Modern preference: ELT with dbt (transformation as code, in-warehouse SQL)

**Q165:** Explain query result caching in Snowflake vs BigQuery.
- Snowflake: 24h cache, free, exact query match, invalidated on data change
- BigQuery: Free cache, invalidated on table modification, per-user
- Both: Critical for dashboards (repeat queries → zero cost)

**Q166:** How do you monitor and troubleshoot slow warehouse queries?
- Query profiling (Snowflake Query Profile, BigQuery INFORMATION_SCHEMA.JOBS)
- Check: Bytes scanned, spillage to disk, queue time, compilation time
- Common fixes: Add clustering, reduce data scanned, break complex CTEs

**Q167:** Explain ClickHouse's Kafka engine for real-time ingestion.
```sql
CREATE TABLE kafka_orders (order_id String, amount Float64)
ENGINE = Kafka()
SETTINGS kafka_broker_list = 'broker:9092',
         kafka_topic_list = 'orders',
         kafka_group_name = 'clickhouse_consumer',
         kafka_format = 'JSONEachRow';

CREATE MATERIALIZED VIEW orders_mv TO orders AS
SELECT * FROM kafka_orders;
-- Continuous ingestion from Kafka → ClickHouse MergeTree
```

**Q168:** How do you implement data sharing across organizations?
- Snowflake: Secure Data Sharing (zero-copy, no ETL, cross-account/region)
- BigQuery: Analytics Hub (publish/subscribe datasets)
- Databricks: Delta Sharing (open protocol, cross-platform)

**Q169:** Compare approximate vs exact aggregations. When use approximate?
- HyperLogLog (COUNT DISTINCT): 2% error, constant memory
- Approximate quantiles (t-digest, DDSketch): For percentiles
- Use when: Dashboards, large cardinality, speed > precision
- Never for: Financial reports, billing, compliance

**Q170:** How do you design a warehouse for real-time + historical analytics?
- Lambda: Stream → real-time layer (Druid) + Batch → historical (Snowflake)
- Kappa: Stream → Iceberg → serve both from lakehouse
- Unified: Snowflake Snowpipe (streaming) + historical in same tables

**Q171:** Explain Snowflake's zero-copy cloning.
- CREATE TABLE orders_clone CLONE orders;
- Points to same micro-partitions (no data copied)
- Diverges on write (copy-on-write semantics)
- Use: Dev/test environments, safe experimentation, backup

**Q172:** How do you handle data warehouse testing?
- dbt tests (unique, not_null, accepted_values, relationships)
- Record count validation (source vs warehouse)
- Schema tests (column types, new columns detection)
- Business logic tests (known-answer assertions)

**Q173:** Explain predicate pushdown in federated queries.
- External tables: Push filters to remote source
- Snowflake external tables on S3: Partition pruning on Parquet
- BigQuery BigLake: Push predicates to Iceberg/Delta metadata

**Q174:** How do you handle time-series data in OLAP systems?
- ClickHouse: toStartOfMinute(), moving aggregates, TTL for expiry
- Druid: Designed for time-series (roll-up, time dimension first)
- Snowflake: Window functions, MATCH_RECOGNIZE for pattern matching

**Q175:** Design a self-service analytics platform.
- Semantic layer (dbt metrics, Cube.js) for consistent definitions
- Governed access (column masking, row security)
- Catalog (DataHub) for discovery
- Sandboxed environments (clone for experimentation)

**Q176:** How do you handle large-scale aggregations efficiently?
- Pre-aggregate (materialized views, CUBE/ROLLUP)
- Approximate functions for dashboards (APPROX_COUNT_DISTINCT)
- Incremental aggregation (only process new data, merge with existing)
- Columnar + vectorized execution (process millions of rows/sec)

**Q177:** Explain Snowflake streams and tasks.
- Streams: CDC on Snowflake tables (track inserts, updates, deletes)
- Tasks: Scheduled SQL statements (cron or tree-based)
- Together: Continuous ELT pipeline within Snowflake

**Q178:** How do you handle cross-database queries?
- Snowflake: Fully qualified names (database.schema.table) across accounts
- BigQuery: Cross-project queries (fully supported, billed to requester)
- Trino/Presto: Federated queries across catalogs (iceberg, hive, mysql)

**Q179:** Compare columnar vs row-based storage for different workloads.
- Columnar (Parquet, ORC, OLAP): Best for analytics (few columns, many rows)
- Row-based (MySQL, Postgres, Avro): Best for OLTP (all columns, few rows)
- Hybrid (Hudi, some NewSQL): Both patterns supported

**Q180:** Design a real-time dashboard architecture with sub-second query latency.
```
Events → Kafka → Flink (pre-aggregate) → Redis/Druid → Dashboard
                                            │
                              Pre-aggregated metrics in memory
                              Dashboard queries hit cache first
                              Druid/Pinot for drill-down (100ms)
```
