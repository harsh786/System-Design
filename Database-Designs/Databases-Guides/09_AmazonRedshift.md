# Amazon Redshift - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage & Columnar Design](#storage--columnar-design)
3. [Distribution Styles](#distribution-styles)
4. [Sort Keys & Zone Maps](#sort-keys--zone-maps)
5. [Query Processing (MPP)](#query-processing-mpp)
6. [Concurrency Scaling & Serverless](#concurrency-scaling--serverless)
7. [Data Loading & COPY](#data-loading--copy)
8. [Performance Optimization](#performance-optimization)
9. [Staff Architect Interview Questions](#staff-architect-interview-questions)
10. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Redshift Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Redshift Cluster                       │
│                                                           │
│  ┌──────────────────┐                                    │
│  │   Leader Node    │ ← SQL parsing, planning, coordination│
│  │                  │ ← Client connections                 │
│  │  Query Optimizer │ ← Result aggregation                │
│  └────────┬─────────┘                                    │
│           │ Distribute to compute nodes                   │
│    ┌──────┼──────┬──────────┐                            │
│    ▼      ▼      ▼          ▼                            │
│ ┌──────┐┌──────┐┌──────┐┌──────┐                        │
│ │Compute││Compute││Compute││Compute│  (Massively Parallel)│
│ │Node 1 ││Node 2 ││Node 3 ││Node N │                     │
│ │       ││       ││       ││       │                      │
│ │Slices:││Slices:││Slices:││Slices:│                      │
│ │[1][2] ││[3][4] ││[5][6] ││[N][N+1]                     │
│ └──────┘└──────┘└──────┘└──────┘                        │
│                                                           │
│  Each slice: Own CPU, memory, disk partition             │
│  Parallel processing within and across nodes            │
└─────────────────────────────────────────────────────────┘

Node types:
- RA3 (managed storage, scale compute/storage independently)
  - ra3.xlplus: 4 vCPU, 32GB, 32TB managed storage
  - ra3.4xlarge: 12 vCPU, 96GB, 128TB managed storage
  - ra3.16xlarge: 48 vCPU, 384GB, 128TB managed storage

- DC2 (dense compute, local SSD)
  - dc2.large: 2 vCPU, 15GB, 160GB SSD
  - dc2.8xlarge: 32 vCPU, 244GB, 2.56TB SSD
```

### Redshift Serverless
```
No cluster management:
- Auto-scales compute (RPU: Redshift Processing Units)
- Pay per query (based on compute used)
- Base capacity: 32-512 RPUs
- Auto-scales up for concurrent/complex queries
- Scales to zero when idle

Use cases:
- Variable workloads (spiky analytics)
- Development/testing
- Ad-hoc analytics (data exploration)
- Cost optimization for intermittent use
```

---

## Storage & Columnar Design

### Columnar Storage
```
Table: orders (id, customer_id, amount, status, order_date)

Storage on disk (per 1MB block):
Block 1: [id: 1,2,3,...,N]           ← Compressed column block
Block 2: [customer_id: C1,C2,C3,...] ← Compressed column block  
Block 3: [amount: 99.99, 149.50,...] ← Compressed column block
Block 4: [status: 'active','active',...]
Block 5: [order_date: 2024-01-01,...]

Each 1MB block:
- Contains values from a single column
- Independently compressed
- Zone map: min/max values stored in metadata
- Enables column-level I/O (read only needed columns)
```

### Compression Encodings
```sql
CREATE TABLE events (
    event_id BIGINT ENCODE az64,          -- AZ64 (Amazon's encoding for numeric)
    event_date DATE ENCODE delta32k,       -- Delta for sequential dates
    user_id BIGINT ENCODE az64,
    event_type VARCHAR(50) ENCODE bytedict, -- Dictionary for low-cardinality
    description VARCHAR(500) ENCODE lzo,    -- LZO for long strings
    amount DECIMAL(10,2) ENCODE az64,
    country CHAR(2) ENCODE raw,            -- Too small to compress
    is_active BOOLEAN ENCODE runlength     -- Run-length for repeated values
);

-- ANALYZE COMPRESSION (recommend encodings):
ANALYZE COMPRESSION events;

Encoding types:
- RAW: No compression
- AZ64: Amazon's adaptive encoding (best for most numerics)
- LZO: Good for long strings
- ZSTD: Better ratio than LZO, slower
- BYTEDICT: Dictionary encoding (256 unique values max)
- DELTA/DELTA32K: For sequential/slowly changing values
- RUNLENGTH: Repeated values
- MOSTLY8/16/32: Small range values stored in fewer bytes
- TEXT255/TEXT32K: Dictionary for text
```

---

## Distribution Styles

### Distribution Strategies
```sql
-- KEY distribution: Rows with same key on same slice
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    amount DECIMAL(10,2)
) DISTSTYLE KEY DISTKEY(customer_id);
-- Use when: JOIN on this column is frequent
-- Co-located JOINs avoid network shuffle

-- EVEN distribution: Round-robin across slices
CREATE TABLE events (
    event_id BIGINT,
    event_data VARCHAR(1000)
) DISTSTYLE EVEN;
-- Use when: No clear join key, or table not joined

-- ALL distribution: Full copy on every node
CREATE TABLE countries (
    code CHAR(2),
    name VARCHAR(100)
) DISTSTYLE ALL;
-- Use when: Small dimension tables (<= few million rows)
-- JOINs are always local (no network)

-- AUTO distribution (default in Redshift):
-- Redshift chooses based on table size:
-- Small tables → ALL
-- Large tables → EVEN or KEY (based on query patterns)
```

### Distribution Key Selection
```
Rules for choosing DISTKEY:
1. Column most frequently used in JOIN conditions
2. High cardinality (avoid skew)
3. Even distribution of values

Bad DISTKEY:
- status (low cardinality: 3-5 values → skew)
- boolean columns (only 2 values)
- nullable columns with many NULLs

Good DISTKEY:
- customer_id (high cardinality, used in JOINs)
- order_id (if joining orders with order_items)

Verify distribution:
SELECT slice, count(*) FROM stv_blocklist 
WHERE tbl = (SELECT oid FROM stv_tbl_perm WHERE name = 'orders')
GROUP BY slice ORDER BY slice;
-- Should be roughly equal across slices
```

---

## Sort Keys & Zone Maps

### Sort Key Types
```sql
-- Compound Sort Key (default): Multi-column, prefix-based
CREATE TABLE events (
    event_date DATE,
    event_type VARCHAR(50),
    user_id BIGINT,
    amount DECIMAL(10,2)
) COMPOUND SORTKEY(event_date, event_type);
-- Benefits: WHERE event_date = '2024-01-15' (uses sort)
-- Benefits: WHERE event_date = '2024-01-15' AND event_type = 'click'
-- NO benefit: WHERE event_type = 'click' (skips first column)

-- Interleaved Sort Key: Equal weight to all key columns
CREATE TABLE events (...)
INTERLEAVED SORTKEY(event_date, event_type, user_id);
-- Benefits: ANY combination of sort key columns
-- Cost: Slower VACUUM REINDEX, higher maintenance
-- Use when: Queries filter on different columns unpredictably

-- Auto Sort Key (default now):
-- Redshift automatically picks sort key based on query patterns
```

### Zone Maps (Block Metadata)
```
Every 1MB block stores min/max per column:
Block 1: event_date [2024-01-01, 2024-01-05]
Block 2: event_date [2024-01-05, 2024-01-10]
Block 3: event_date [2024-01-10, 2024-01-15]

Query: WHERE event_date = '2024-01-08'
→ Skip Block 1 (max=01-05 < 01-08)
→ Read Block 2 (min=01-05 ≤ 01-08 ≤ max=01-10)
→ Skip Block 3 (min=01-10 > 01-08)

This is why SORT KEY matters:
- Sorted data → tight zone maps → maximum block skipping
- Unsorted data → wide zone maps → minimal skipping
```

---

## Query Processing (MPP)

### Query Execution Flow
```
1. Client sends SQL to Leader Node
2. Leader parses, optimizes, creates execution plan
3. Leader distributes plan to compute nodes
4. Each slice executes plan on its data partition
5. Intermediate results shuffled between nodes (redistribution)
6. Leader aggregates final results
7. Leader returns results to client

Parallel execution:
- Each slice processes independently
- Joins may require data redistribution (expensive!)
- Aggregations computed locally, then merged
- Sort operations done locally, then merge-sorted
```

### Query Plan Analysis
```sql
EXPLAIN SELECT customer_id, SUM(amount)
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.order_date >= '2024-01-01'
GROUP BY customer_id;

-- Key operators to look for:
-- DS_DIST_NONE: No redistribution needed (co-located data)
-- DS_DIST_ALL_NONE: Replicated table, no redistribution
-- DS_BCAST_INNER: Inner table broadcast to all nodes (small table)
-- DS_DIST_BOTH: Both tables redistributed (EXPENSIVE!)
-- DS_DIST_INNER: Only inner table redistributed

-- STL_EXPLAIN, STL_QUERYTEXT for historical analysis
-- SVL_QUERY_SUMMARY for execution details
```

---

## Concurrency Scaling & Workload Management

### WLM (Workload Management)
```
Queues with priorities:
┌─────────────────────────────────────────────┐
│ Queue 1: "Dashboard" (priority: high)        │
│   Concurrency: 10, Memory: 30%              │
│   Users: bi_dashboard_role                   │
├─────────────────────────────────────────────┤
│ Queue 2: "Analytics" (priority: medium)      │
│   Concurrency: 5, Memory: 50%               │
│   Users: analyst_role                        │
├─────────────────────────────────────────────┤
│ Queue 3: "ETL" (priority: low)               │
│   Concurrency: 2, Memory: 20%               │
│   Users: etl_role                            │
├─────────────────────────────────────────────┤
│ Queue 4: "Default" (catch-all)               │
│   Concurrency: 5, Memory: auto              │
└─────────────────────────────────────────────┘

-- Automatic WLM (recommended):
-- Redshift auto-manages concurrency and memory
-- Set priority per queue only
```

### Concurrency Scaling
```
Automatic burst capacity:
- When queries queue up → auto-provisions transient clusters
- Burst cluster runs queued queries
- Scales back when demand drops
- Free tier: 1 hour of concurrency scaling per 24 hours
- Beyond: Pay per second of burst cluster time

Materialized Views (reduce query load):
CREATE MATERIALIZED VIEW daily_sales AS
SELECT order_date, SUM(amount) total, COUNT(*) orders
FROM orders
GROUP BY order_date;

-- Auto-refresh:
ALTER MATERIALIZED VIEW daily_sales AUTO REFRESH YES;
```

---

## Data Loading & COPY

### COPY Command (Best Practice)
```sql
-- Load from S3 (parallel by file count matching slice count)
COPY events FROM 's3://bucket/events/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
FORMAT AS PARQUET;  -- Parquet preserves types and compresses

-- Optimal: Number of files = multiple of slice count
-- 8 slices → 8, 16, 24 files for maximum parallelism

-- CSV with options:
COPY events FROM 's3://bucket/events/2024-01/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
CSV
DELIMITER ','
IGNOREHEADER 1
GZIP
MAXERROR 100
TIMEFORMAT 'auto'
REGION 'us-east-1';

-- Manifest file (explicit file list):
COPY events FROM 's3://bucket/manifest.json'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
MANIFEST;
```

### Loading Best Practices
```
1. File splitting: Split large files into multiple parts
   - Each slice loads one file in parallel
   - File count = N × slice count (e.g., 16, 32, 64 files)
   - Each file: 1MB - 1GB compressed

2. Use columnar formats: Parquet or ORC
   - Type preservation (no parsing overhead)
   - Column pruning (read only needed columns)
   - Better compression

3. Sort data before loading (if possible):
   - Pre-sorted by sort key = no VACUUM needed
   - Tight zone maps from the start

4. VACUUM after loads:
   VACUUM SORT ONLY events;  -- Re-sort unsorted rows
   VACUUM DELETE ONLY events; -- Reclaim deleted row space
   VACUUM FULL events;        -- Both sort + delete

5. ANALYZE after loads:
   ANALYZE events;  -- Update query planner statistics
```

---

## Performance Optimization

### Query Design Patterns
```sql
-- 1. Avoid SELECT * (columnar DB penalty):
SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id;

-- 2. Use approximate functions for large datasets:
SELECT APPROXIMATE COUNT(DISTINCT user_id) FROM events;
-- ±2% accuracy, 10-100x faster

-- 3. Use window functions instead of self-joins:
SELECT customer_id, amount,
       SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date 
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
FROM orders;

-- 4. Filter early with WHERE:
-- Zone maps eliminate blocks before scanning

-- 5. Use EXPLAIN to check distribution:
-- Avoid DS_DIST_BOTH (both tables redistributed)

-- 6. Avoid cross-database queries (federated):
-- External schemas (Spectrum) are slower than local tables
```

### Redshift Spectrum (Query S3 Directly)
```sql
-- Create external schema pointing to S3
CREATE EXTERNAL SCHEMA spectrum
FROM DATA CATALOG
DATABASE 'my_glue_db'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftSpectrumRole';

-- Query S3 data directly (no loading needed):
SELECT date_trunc('hour', event_time), COUNT(*)
FROM spectrum.raw_events
WHERE event_date = '2024-01-15'
GROUP BY 1;

-- Benefits:
-- - Query petabytes without loading
-- - Columnar formats (Parquet) for performance
-- - Partition pruning on S3 prefix structure
-- - Combine with local Redshift tables in same query

-- Best for: Historical/cold data, ad-hoc exploration
-- Not for: Low-latency production queries
```

---

## Staff Architect Interview Questions

**Q1: How do you choose between Redshift, BigQuery, and Snowflake?**
**A:**
| Aspect | Redshift | BigQuery | Snowflake |
|--------|----------|----------|-----------|
| Pricing | Per-node (provisioned) or serverless | Per-query (scan) | Per-credit (compute time) |
| Best for | Consistent workloads, AWS ecosystem | Variable workloads, zero-ops | Multi-cloud, easy scaling |
| Storage | Managed (RA3) or local (DC2) | Separated (Capacitor) | Separated (micro-partitions) |
| Concurrency | WLM + concurrency scaling | Auto-scaling slots | Virtual warehouses |
| Ecosystem | AWS native (S3, Glue, SageMaker) | GCP native (GCS, Dataflow) | Multi-cloud |
| Semi-structured | JSON functions, Spectrum | Native (STRUCT, ARRAY) | VARIANT type |

**Q2: A Redshift query that was fast is now slow. How do you diagnose?**
**A:**
1. Check STL_ALERT_EVENT_LOG for alerts (missing stats, nested loops, large distribution)
2. Check distribution skew: `SELECT slice, rows FROM svv_diskusage WHERE name='table'`
3. Check unsorted rows: `SELECT "table", unsorted FROM svv_table_info`
4. Check if VACUUM/ANALYZE needed
5. Review WLM queues: Is query waiting? Memory pressure?
6. Check query plan: DS_DIST_BOTH means redistribution (expensive)
7. Check for concurrent query competition (concurrency scaling?)

**Q3: Design a data warehouse for an e-commerce company processing 1TB/day.**
**A:**
```
Architecture:
- Redshift RA3 cluster: 6 × ra3.4xlarge nodes
- Sort key: order_date (compound) for most tables
- Distribution: customer_id (KEY) for orders/customers
- Small tables (products, categories): DISTSTYLE ALL
- Hot data (30 days) in Redshift, cold data in S3 (Spectrum)
- Materialized views for common dashboard queries
- WLM: 3 queues (dashboard/analytics/ETL)

Loading pipeline:
S3 (raw) → Glue ETL → S3 (Parquet, partitioned) → COPY into Redshift
- Files split into 48 parts (6 nodes × 8 slices = 48)
- Incremental loads every 15 minutes
- Full refresh monthly (historical adjustments)

Retention:
- Redshift: 2 years (frequently queried)
- S3 + Spectrum: 7 years (compliance, ad-hoc)
```

---

## Scenario-Based Questions

### Scenario 1: Query Taking 30 Minutes Instead of 30 Seconds

**Diagnosis:**
```sql
-- 1. Check execution details
SELECT * FROM stl_query WHERE query = :query_id;
SELECT * FROM svl_query_summary WHERE query = :query_id;

-- 2. Check for distribution issues
SELECT segment, step, label, rows, bytes
FROM svl_query_report WHERE query = :query_id
ORDER BY segment, step;
-- Look for: Large "bcast" or "dist" steps (data shuffling)

-- 3. Check disk-based operations (spilling to disk)
SELECT * FROM svl_query_metrics WHERE query = :query_id;
-- query_temp_blocks_to_disk > 0 means memory spill

-- 4. Check queue wait time
SELECT * FROM stl_wlm_query WHERE query = :query_id;
-- total_queue_time >> 0 means WLM contention

-- 5. Solutions:
-- a. Add/change DISTKEY to match JOIN column
-- b. Add SORTKEY for WHERE clause columns
-- c. Increase WLM memory allocation
-- d. VACUUM SORT to re-sort data
-- e. Break into smaller queries (UNLOAD intermediate results)
```

### Scenario 2: Real-Time Dashboard on Top of Redshift

**Problem:** Dashboard needs sub-second refresh, Redshift queries take 5-10s.

**Solution architecture:**
```
Option 1: Materialized Views + Auto-Refresh
- Pre-compute dashboard aggregations
- Auto-refresh every 1 minute
- Dashboard queries read from MV (fast)

Option 2: Redshift Streaming Ingestion (from Kinesis/Kafka)
- Near real-time data availability (seconds)
- Combined with materialized views for speed
- No COPY batch latency

Option 3: Hybrid architecture
- Redshift for historical analytics (5s+ latency OK)
- Redis/Druid/Pinot for real-time metrics (sub-second)
- Application layer combines both

Recommendation: For true sub-second with >100 concurrent users,
Redshift alone is insufficient. Use Pinot/Druid for real-time,
Redshift for deep analytics and ad-hoc queries.
```

