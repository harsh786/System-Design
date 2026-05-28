# ClickHouse Performance Internals — Deep Dive

> How ClickHouse achieves sub-second queries over billions of rows

---

## Table of Contents

1. [Columnar Storage](#1-columnar-storage)
2. [Compression](#2-compression)
3. [Sparse Indexing & Granules](#3-sparse-indexing--granules)
4. [Partition Pruning](#4-partition-pruning)
5. [Data Skipping Indexes](#5-data-skipping-indexes)
6. [PREWHERE Optimization](#6-prewhere-optimization)
7. [Vectorized Execution](#7-vectorized-execution)
8. [Parallelization](#8-parallelization)
9. [MergeTree Smart Engine](#9-mergetree-smart-engine)
10. [Materialized Views](#10-materialized-views)

---

## 1. Columnar Storage

### Core Idea

In a **row-oriented** database (PostgreSQL, MySQL), data is stored row-by-row:

```
Row 1: [user_id=1, name="Alice", age=30, city="NYC", salary=90000]
Row 2: [user_id=2, name="Bob",   age=25, city="LA",  salary=75000]
Row 3: [user_id=3, name="Carol", age=35, city="NYC", salary=95000]
```

In a **column-oriented** database (ClickHouse), data is stored column-by-column:

```
user_id column: [1, 2, 3, 4, 5, ...]
name column:    ["Alice", "Bob", "Carol", ...]
age column:     [30, 25, 35, ...]
city column:    ["NYC", "LA", "NYC", ...]
salary column:  [90000, 75000, 95000, ...]
```

### Why This Matters for Analytics

```sql
-- "What's the average salary by city?"
SELECT city, avg(salary)
FROM employees
GROUP BY city;
```

**Row store reads:** ALL columns for ALL rows → reads `user_id`, `name`, `age` (unused!)
**Column store reads:** ONLY `city` + `salary` columns → skips 60% of data

### Physical Layout on Disk

```
/var/lib/clickhouse/data/mydb/employees/
├── all_1_1_0/
│   ├── user_id.bin        ← compressed column data
│   ├── user_id.mrk2       ← marks (offsets into .bin)
│   ├── name.bin
│   ├── name.mrk2
│   ├── age.bin
│   ├── age.mrk2
│   ├── city.bin
│   ├── city.mrk2
│   ├── salary.bin
│   ├── salary.mrk2
│   ├── primary.idx        ← sparse primary index
│   └── checksums.txt
```

### Performance Impact

| Scenario | Row Store | Column Store | Speedup |
|----------|-----------|--------------|---------|
| SELECT 2 of 50 columns | Reads 100% | Reads 4% | **25x** |
| SELECT 5 of 100 columns | Reads 100% | Reads 5% | **20x** |
| Aggregation on 1 column | Full table scan | Single column scan | **50-100x** |

### Example: Measuring I/O Savings

```sql
CREATE TABLE events (
    event_id    UInt64,
    user_id     UInt32,
    event_type  LowCardinality(String),
    properties  String,          -- large JSON blob, ~500 bytes avg
    timestamp   DateTime,
    amount      Float64
) ENGINE = MergeTree()
ORDER BY (event_type, timestamp);

-- This query only reads event_type + amount columns
-- Skips the heavy 'properties' column entirely
SELECT event_type, sum(amount)
FROM events
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY event_type;
```

Check actual bytes read:

```sql
SELECT
    query,
    read_bytes,
    read_rows,
    formatReadableSize(read_bytes) as data_read
FROM system.query_log
WHERE query LIKE '%sum(amount)%'
ORDER BY event_time DESC
LIMIT 1;
```

---

## 2. Compression

### How ClickHouse Achieves 10-100x Compression

Columnar storage enables extraordinary compression because **similar values are stored together**:

```
-- A "status" column with 10M rows might contain:
["active", "active", "active", "inactive", "active", "active", ...]

-- After compression: stored as essentially a bitmap + dictionary
-- Original: 10M × 8 bytes = 80 MB
-- Compressed: ~800 KB (100x reduction)
```

### Compression Pipeline

```
Raw Column Data
    │
    ▼
┌─────────────────────────┐
│  1. Delta Encoding       │  (for sorted numeric columns)
│     [100, 101, 103, 105] │  → [100, 1, 2, 2]
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  2. LZ4 / ZSTD          │  (general-purpose compression)
│     Default: LZ4         │  (fast decompression)
│     Optional: ZSTD       │  (better ratio, slower)
└─────────────────────────┘
    │
    ▼
  Compressed Block on Disk (64KB - 1MB)
```

### Compression Codecs

```sql
CREATE TABLE metrics (
    timestamp    DateTime     CODEC(DoubleDelta, LZ4),  -- timestamps: ~20x
    metric_id    UInt32       CODEC(Delta, LZ4),        -- sequential IDs: ~50x
    value        Float64      CODEC(Gorilla, LZ4),      -- float values: ~10x
    host         LowCardinality(String),                -- low cardinality: ~100x
    raw_json     String       CODEC(ZSTD(3))            -- large text: ~5-10x
) ENGINE = MergeTree()
ORDER BY (metric_id, timestamp);
```

### Codec Selection Guide

| Data Pattern | Best Codec | Typical Ratio | Example |
|-------------|------------|---------------|---------|
| Timestamps (sorted) | DoubleDelta + LZ4 | 20-40x | `event_time DateTime` |
| Sequential integers | Delta + LZ4 | 30-100x | `auto_increment_id UInt64` |
| Float metrics | Gorilla + LZ4 | 5-15x | `cpu_usage Float64` |
| Low cardinality strings | LowCardinality + LZ4 | 50-200x | `country String` |
| High cardinality strings | ZSTD(3) | 3-8x | `url String` |
| Boolean/enum-like | T64 + LZ4 | 50-100x | `is_active UInt8` |

### Measuring Compression

```sql
SELECT
    column,
    formatReadableSize(data_compressed_bytes) AS compressed,
    formatReadableSize(data_uncompressed_bytes) AS uncompressed,
    round(data_uncompressed_bytes / data_compressed_bytes, 2) AS ratio
FROM system.columns
WHERE table = 'events' AND database = 'mydb'
ORDER BY data_uncompressed_bytes DESC;
```

Example output:

```
┌─column──────┬─compressed─┬─uncompressed─┬──ratio─┐
│ properties  │ 2.31 GiB   │ 18.50 GiB    │   8.01 │
│ timestamp   │ 45.12 MiB  │ 1.86 GiB     │  42.27 │
│ user_id     │ 89.33 MiB  │ 3.73 GiB     │  42.76 │
│ event_type  │ 12.44 MiB  │ 1.86 GiB     │ 153.22 │
│ amount      │ 156.78 MiB │ 1.86 GiB     │  12.15 │
└─────────────┴────────────┴──────────────┴────────┘
```

### Why Compression = Speed

```
Traditional thinking: Compression = slower (CPU overhead)
ClickHouse reality:   Compression = FASTER

Why? Disk I/O is the bottleneck, not CPU.

Without compression: Read 100 GB from disk → 100 seconds (1 GB/s SSD)
With 10x compression: Read 10 GB from disk + decompress → 12 seconds

LZ4 decompresses at ~4 GB/s — faster than any SSD can deliver data.
```

---

## 3. Sparse Indexing & Granules

### What is a Granule?

A **granule** is the minimum unit of data that ClickHouse reads. Default size: **8192 rows**.

```
Data Part (millions of rows)
├── Granule 0: rows 0 - 8191
├── Granule 1: rows 8192 - 16383
├── Granule 2: rows 16384 - 24575
├── Granule 3: rows 24576 - 32767
│   ...
└── Granule N: rows (N×8192) - ((N+1)×8192 - 1)
```

### Sparse Index Structure

Unlike B-Tree indexes (which store a pointer for EVERY row), ClickHouse stores **one index entry per granule**:

```sql
CREATE TABLE hits (
    date      Date,
    user_id   UInt64,
    url       String,
    duration  UInt32
) ENGINE = MergeTree()
ORDER BY (date, user_id);  -- This defines the sparse index
```

**Primary index (primary.idx):**

```
┌─────────────────────────────────────────────────────┐
│ Granule │  date       │  user_id                     │
├─────────┼─────────────┼──────────────────────────────┤
│    0    │ 2024-01-01  │  1000                        │
│    1    │ 2024-01-01  │  5420                        │
│    2    │ 2024-01-01  │  12800                       │
│    3    │ 2024-01-02  │  100                         │
│    4    │ 2024-01-02  │  3300                        │
│   ...   │    ...      │  ...                         │
└─────────┴─────────────┴──────────────────────────────┘
```

### How Index Lookup Works

```sql
SELECT * FROM hits WHERE date = '2024-01-02' AND user_id = 5000;
```

**Step-by-step:**

```
1. Binary search primary.idx for date = '2024-01-02'
   → Found: Granule 3 starts with (2024-01-02, 100)
   → Found: Granule 5 starts with (2024-01-03, ...)

2. Within date = '2024-01-02' range (Granules 3-4):
   Binary search for user_id = 5000
   → Granule 3: starts at user_id=100
   → Granule 4: starts at user_id=3300
   → Granule 5: starts at 2024-01-03 (past our date)
   → Must read Granules 3 and 4

3. Read ONLY granules 3 and 4 (16384 rows)
   Skip ALL other granules (potentially millions of rows)
```

### Index Size Advantage

```
Table: 1 billion rows
Granule size: 8192 rows
Number of granules: ~122,000

B-Tree index: 1 billion entries × ~20 bytes = 20 GB (doesn't fit in RAM!)
Sparse index: 122,000 entries × ~20 bytes = ~2.4 MB (easily fits in RAM!)
```

### Granule Settings

```sql
CREATE TABLE large_events (
    timestamp DateTime,
    data      String
) ENGINE = MergeTree()
ORDER BY timestamp
SETTINGS
    index_granularity = 8192,           -- rows per granule (default)
    index_granularity_bytes = 10485760; -- 10MB max per granule (adaptive)
```

### Visualizing Granule Skipping

```sql
-- Force ClickHouse to show which granules it reads
SET send_logs_level = 'trace';

SELECT count() FROM hits WHERE user_id = 12345;

-- In logs you'll see:
-- "Selected 3 parts by partition key"
-- "Selected 12 marks by primary key out of 45000 total marks"
-- ↑ This means: read 12 granules, skipped 44,988 granules!
```

### Mark Files (.mrk2)

Mark files map granule numbers → physical byte offsets in compressed column files:

```
┌──────────┬────────────────────────┬──────────────────────┐
│ Granule  │ Compressed Block Offset│ Offset Within Block  │
├──────────┼────────────────────────┼──────────────────────┤
│    0     │         0              │        0             │
│    1     │         0              │     65536            │
│    2     │      131072            │        0             │
│    3     │      131072            │     65536            │
└──────────┴────────────────────────┴──────────────────────┘
```

This allows ClickHouse to seek directly to the compressed block containing a granule.

---

## 4. Partition Pruning

### What is Partitioning?

Partitioning splits a table into **independent physical parts** based on a partition expression:

```sql
CREATE TABLE events (
    event_time  DateTime,
    user_id     UInt32,
    event_type  String,
    payload     String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)  -- One partition per month
ORDER BY (event_type, user_id);
```

### Physical Layout

```
/var/lib/clickhouse/data/mydb/events/
├── 202401_1_5_2/       ← January 2024 partition (merged)
│   ├── event_time.bin
│   ├── user_id.bin
│   ├── ...
├── 202402_6_10_1/      ← February 2024 partition
│   ├── ...
├── 202403_11_15_3/     ← March 2024 partition
│   ├── ...
└── 202404_16_20_1/     ← April 2024 partition
    └── ...
```

### How Partition Pruning Works

```sql
SELECT count(*)
FROM events
WHERE event_time >= '2024-03-01' AND event_time < '2024-04-01';
```

**Without partitioning:** Scan ALL data, use sparse index to skip granules
**With partitioning:** Immediately eliminate Jan, Feb, Apr partitions → read ONLY March

```
Query planner:
  1. Evaluate: toYYYYMM('2024-03-01') = 202403
  2. Evaluate: toYYYYMM('2024-03-31') = 202403
  3. Prune: Keep only partition 202403
  4. Skip: 202401, 202402, 202404 (never touched!)
  5. Within 202403: use sparse index for further filtering
```

### Partition Pruning + Granule Skipping (Combined)

```sql
SELECT avg(payload_size)
FROM events
WHERE event_time BETWEEN '2024-03-15' AND '2024-03-16'
  AND event_type = 'purchase';
```

```
Step 1: Partition pruning
  └── Skip Jan, Feb, Apr → Keep only March partition

Step 2: Sparse index scan (within March partition)
  └── ORDER BY (event_type, user_id)
  └── Binary search for event_type = 'purchase'
  └── Select relevant granules only

Step 3: Read those granules, apply event_time filter
  └── Final result from minimal I/O
```

### Partition Strategy Recommendations

| Use Case | Partition Expression | Reason |
|----------|---------------------|--------|
| Time-series (high volume) | `toYYYYMM(timestamp)` | Monthly partitions, good for TTL |
| Time-series (moderate) | `toYYYYMMDD(timestamp)` | Daily partitions, fast recent queries |
| Multi-tenant | `tenant_id` | Isolate per customer |
| Combined | `(toYYYYMM(ts), region)` | Time + geography |

### Anti-Patterns

```sql
-- TOO MANY partitions (causes "too many parts" error)
PARTITION BY toDateTime(event_time)  -- One partition per SECOND!

-- TOO FEW partitions (no pruning benefit)
PARTITION BY toYear(event_time)      -- Only 1 partition per year

-- IDEAL: 100-1000 partitions total
PARTITION BY toYYYYMM(event_time)    -- ~12 per year
```

### Checking Partition Pruning

```sql
EXPLAIN indexes = 1
SELECT count() FROM events
WHERE event_time >= '2024-03-01' AND event_time < '2024-04-01';

-- Output shows:
-- Parts: 3/12 (read 3 parts, total 12 exist)
-- Granules: 150/5000 (read 150 granules of 5000 total)
```

---

## 5. Data Skipping Indexes

### Problem: Sparse Index Limitations

The sparse (primary) index only helps queries that filter on the **ORDER BY columns** (or a prefix of them). What about other columns?

```sql
CREATE TABLE logs (
    timestamp   DateTime,
    level       String,
    service     String,
    message     String,
    request_id  String
) ENGINE = MergeTree()
ORDER BY timestamp;

-- This is FAST (uses primary index):
SELECT * FROM logs WHERE timestamp > '2024-03-01';

-- This is SLOW (full scan, primary index doesn't help):
SELECT * FROM logs WHERE request_id = 'abc-123-def';
```

### Solution: Data Skipping Indexes (Secondary Indexes)

Data skipping indexes store **summary statistics per granule** to skip irrelevant granules:

```sql
ALTER TABLE logs ADD INDEX idx_request_id request_id
    TYPE set(1000) GRANULARITY 4;

-- GRANULARITY 4 means: one index entry covers 4 granules (4 × 8192 = 32768 rows)
```

### Index Types

#### 1. minmax — Stores min/max per granule group

```sql
ALTER TABLE logs ADD INDEX idx_response_time response_time
    TYPE minmax GRANULARITY 3;

-- For each group of 3 granules, stores: [min_value, max_value]
-- Query: WHERE response_time > 5000
-- Skip granule groups where max_value < 5000
```

**Best for:** Numeric ranges, timestamps, sorted-ish data

#### 2. set(N) — Stores unique values (up to N)

```sql
ALTER TABLE logs ADD INDEX idx_service service
    TYPE set(100) GRANULARITY 4;

-- For each group of 4 granules, stores the set of distinct values
-- Query: WHERE service = 'payment-api'
-- Skip granule groups that don't contain 'payment-api' in their set
```

**Best for:** Low-cardinality columns (status codes, service names, countries)

#### 3. bloom_filter — Probabilistic membership test

```sql
ALTER TABLE logs ADD INDEX idx_request_id request_id
    TYPE bloom_filter(0.01) GRANULARITY 4;

-- Bloom filter with 1% false positive rate
-- Query: WHERE request_id = 'abc-123-def'
-- Skip granule groups where bloom filter says "definitely not here"
-- May read some extra granules (false positives), but never misses data
```

**Best for:** High-cardinality columns (UUIDs, request IDs, emails)

#### 4. tokenbf_v1 — Tokenized bloom filter for text search

```sql
ALTER TABLE logs ADD INDEX idx_message message
    TYPE tokenbf_v1(10240, 3, 0)  GRANULARITY 2;
    -- (bloom_size, hash_functions, seed)

-- Tokenizes the string, builds bloom filter on tokens
-- Query: WHERE message LIKE '%timeout%'
-- Skip granule groups where 'timeout' token is definitely absent
```

**Best for:** Text search, log messages, URL paths

#### 5. ngrambf_v1 — N-gram bloom filter

```sql
ALTER TABLE logs ADD INDEX idx_url url
    TYPE ngrambf_v1(4, 10240, 3, 0) GRANULARITY 2;
    -- (ngram_size, bloom_size, hash_functions, seed)

-- Builds bloom filter on 4-character n-grams
-- Better for substring matching than tokenbf_v1
-- Query: WHERE url LIKE '%user%profile%'
```

**Best for:** Substring search, partial matches

### Complete Example

```sql
CREATE TABLE application_logs (
    timestamp    DateTime,
    date         Date DEFAULT toDate(timestamp),
    level        Enum8('DEBUG'=0, 'INFO'=1, 'WARN'=2, 'ERROR'=3),
    service      LowCardinality(String),
    host         LowCardinality(String),
    request_id   String,
    user_id      UInt64,
    message      String,
    response_ms  UInt32,

    -- Data Skipping Indexes
    INDEX idx_request_id request_id TYPE bloom_filter(0.001) GRANULARITY 4,
    INDEX idx_user_id user_id TYPE set(10000) GRANULARITY 2,
    INDEX idx_service service TYPE set(50) GRANULARITY 1,
    INDEX idx_response_ms response_ms TYPE minmax GRANULARITY 3,
    INDEX idx_message message TYPE tokenbf_v1(30720, 3, 0) GRANULARITY 2

) ENGINE = MergeTree()
PARTITION BY date
ORDER BY (level, timestamp);
```

### Verifying Index Effectiveness

```sql
-- Check how many granules are skipped
SELECT *
FROM system.query_log
WHERE query LIKE '%request_id%'
  AND type = 'QueryFinish'
ORDER BY event_time DESC
LIMIT 1
FORMAT Vertical;

-- Key fields:
-- ProfileEvents['SelectedMarks']      = granules read
-- ProfileEvents['SelectedParts']      = parts read
-- ProfileEvents['SkippedMarks']       = granules SKIPPED by indexes!
```

---

## 6. PREWHERE Optimization

### The Problem

```sql
SELECT user_id, name, huge_json_blob
FROM users
WHERE status = 'active' AND country = 'US';
```

Without PREWHERE: ClickHouse reads ALL columns (including `huge_json_blob`) for matching granules, THEN filters.

### How PREWHERE Works

PREWHERE splits query execution into two phases:

```
Phase 1 (PREWHERE): Read ONLY lightweight filter columns
  └── Read 'status' column (tiny, fast)
  └── Read 'country' column (tiny, fast)
  └── Build row bitmap: which rows pass the filter?
  └── Result: [row 0: ✓, row 1: ✗, row 2: ✓, row 3: ✗, ...]

Phase 2 (WHERE): Read heavy columns ONLY for matching rows
  └── Read 'user_id' only for rows marked ✓
  └── Read 'name' only for rows marked ✓
  └── Read 'huge_json_blob' only for rows marked ✓
```

### Automatic PREWHERE

ClickHouse **automatically** moves conditions to PREWHERE when beneficial:

```sql
-- You write:
SELECT * FROM events WHERE event_type = 'click' AND timestamp > now() - 1;

-- ClickHouse internally rewrites to:
SELECT * FROM events
PREWHERE event_type = 'click'   -- small column, checked first
WHERE timestamp > now() - 1;    -- remaining filter
```

### Explicit PREWHERE

```sql
-- Force specific PREWHERE behavior:
SELECT user_id, properties
FROM events
PREWHERE event_type = 'purchase'  -- 5% selectivity, tiny column
WHERE JSONExtractFloat(properties, 'amount') > 100;  -- expensive extraction

-- Phase 1: Read only 'event_type' → eliminate 95% of rows
-- Phase 2: Read 'properties' + parse JSON for remaining 5%
```

### When PREWHERE Helps Most

```
Savings = (1 - selectivity) × size_of_heavy_columns

Example:
- Table: 1B rows, 10 columns, 500 bytes avg per row = 500 GB
- Filter column (event_type): 10 bytes per row = 10 GB
- Heavy columns: 490 bytes per row = 490 GB
- Filter selectivity: 2% (only 2% of rows match)

Without PREWHERE: Read 500 GB, return 2% = 10 GB useful data
With PREWHERE:    Read 10 GB (filter) + 2% × 490 GB ≈ 20 GB total

Savings: 500 GB → 20 GB = 25x less I/O!
```

### PREWHERE Settings

```sql
-- Disable automatic PREWHERE (rarely needed)
SET optimize_move_to_prewhere = 0;

-- Control which columns are eligible
SET optimize_move_to_prewhere_if_final = 1;

-- Move multiple conditions to PREWHERE
SET move_all_conditions_to_prewhere = 1;
```

### PREWHERE vs WHERE: Decision Matrix

| Condition | Use PREWHERE | Use WHERE |
|-----------|:---:|:---:|
| High selectivity filter (< 10% rows pass) | ✓ | |
| Filter on small column, SELECT has large columns | ✓ | |
| Filter is cheap to evaluate | ✓ | |
| Filter involves expensive functions (JSON parsing) | | ✓ |
| Most rows pass the filter (> 50%) | | ✓ |
| All selected columns are small | | ✓ |

---

## 7. Vectorized Execution

### What is Vectorization?

Instead of processing one row at a time, ClickHouse processes **blocks of rows** using SIMD (Single Instruction, Multiple Data) CPU instructions:

```
Traditional (row-at-a-time):
  for each row:
    result[i] = column_a[i] + column_b[i]
  → 1 addition per CPU cycle

Vectorized (block-at-a-time):
  for each block of 8-32 values:
    result[i:i+8] = column_a[i:i+8] + column_b[i:i+8]
  → 8-32 additions per CPU cycle (using AVX2/AVX-512)
```

### SIMD in Action

```
CPU Register (AVX2 = 256 bits wide):

┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
│ val[0] │ val[1] │ val[2] │ val[3] │ val[4] │ val[5] │ val[6] │ val[7] │
│ 32-bit │ 32-bit │ 32-bit │ 32-bit │ 32-bit │ 32-bit │ 32-bit │ 32-bit │
└────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┘

Single instruction: ADD all 8 values simultaneously
  → 8x throughput for UInt32 operations
  → 4x throughput for UInt64 operations
  → 32x throughput for UInt8 operations (AVX-512)
```

### Operations That Benefit

```sql
-- Filtering: compare 8-32 values per instruction
SELECT * FROM events WHERE amount > 100;
-- SIMD: compare 8 Float64 values simultaneously

-- Aggregation: accumulate 8-32 values per instruction
SELECT sum(amount) FROM events;
-- SIMD: add 8 Float64 values per cycle

-- String operations: process 32 bytes at a time
SELECT * FROM logs WHERE message LIKE '%error%';
-- SIMD: scan 32 characters per cycle using SSE4.2 string instructions
```

### How ClickHouse Maximizes Vectorization

```
1. Columnar format ensures data is contiguous in memory
   → CPU prefetcher works perfectly
   → No cache misses jumping between row fields

2. Fixed-size types (UInt32, Float64) enable perfect alignment
   → SIMD instructions require aligned memory
   → No padding or indirection

3. Block processing (65536 rows per block by default)
   → Amortize function call overhead
   → Keep data in CPU L1/L2 cache

4. Specialized kernels for common operations
   → Hand-written assembly for hot paths
   → Different code paths for different CPU capabilities
```

### Checking Vectorization Support

```sql
SELECT *
FROM system.build_options
WHERE name LIKE '%SSE%' OR name LIKE '%AVX%';

-- Shows which SIMD instruction sets your ClickHouse build supports:
-- SSE 4.2, AVX, AVX2, AVX-512 (if available)
```

### Performance Impact Example

```sql
-- Simple aggregation on 1 billion UInt32 values:
SELECT sum(value) FROM billion_rows;

-- Without SIMD: ~1.2 seconds (sequential addition)
-- With AVX2:    ~0.15 seconds (8 additions per cycle)
-- Speedup:      8x (matches theoretical 256-bit / 32-bit = 8)
```

### Block Size Tuning

```sql
-- Default block size for reading
SET max_block_size = 65536;

-- For queries reading many columns, smaller blocks may be better (cache)
SET max_block_size = 8192;

-- For simple aggregations on few columns, larger blocks are better
SET max_block_size = 131072;
```

---

## 8. Parallelization

### Multi-Core Query Execution

ClickHouse automatically distributes work across **all available CPU cores**:

```
Query: SELECT count(*) FROM events WHERE event_type = 'click'

Table has 100 data parts:

┌─────────────────────────────────────────────────────────┐
│                    Query Coordinator                      │
└──────────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
     ┌─────▼────┐┌───▼────┐┌───▼────┐┌───▼────┐
     │ Thread 1 ││Thread 2││Thread 3││Thread 4│  ... (N threads)
     │Parts 1-12││Parts   ││Parts   ││Parts   │
     │          ││ 13-25  ││ 26-38  ││ 39-50  │
     └─────┬────┘└───┬────┘└───┬────┘└───┬────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
     count=15234  count=14892  count=15567  count=14201
           │          │          │          │
           └──────────┴──────────┴──────────┘
                          │
                          ▼
                   Total: 59,894 (merged)
```

### Parallelization Levels

```
Level 1: Inter-Part Parallelism
  └── Different data parts processed by different threads
  └── Each thread works independently on its parts

Level 2: Intra-Part Parallelism
  └── Large parts split into ranges of granules
  └── Multiple threads process different granule ranges

Level 3: Pipeline Parallelism
  └── Different query stages run concurrently
  └── While thread A reads data, thread B compresses results

Level 4: Distributed Parallelism (multi-node)
  └── Shards process their local data in parallel
  └── Results merged at the coordinator node
```

### Thread Pool Settings

```sql
-- Maximum threads for a single query (default = number of CPU cores)
SET max_threads = 16;

-- For I/O bound queries, allow more threads than cores
SET max_threads = 32;

-- Minimum bytes per thread (avoids overhead for small queries)
-- Won't create threads if data per thread < this threshold
SET min_bytes_to_use_direct_io = 10485760;  -- 10 MB
```

### Parallel Aggregation

```sql
SELECT
    event_type,
    count() AS cnt,
    avg(duration) AS avg_dur
FROM events
GROUP BY event_type;
```

```
Execution with 8 threads:

Phase 1: Parallel Scan + Local Aggregation
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Thread 1 │  │ Thread 2 │  │ Thread 8 │
│ Local HT │  │ Local HT │  │ Local HT │
│click: 500│  │click: 480│  │click: 510│
│view: 1200│  │view: 1190│  │view: 1205│
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
Phase 2: Merge Hash Tables
                    ▼
          ┌─────────────────┐
          │  Final Result   │
          │ click: 3940     │
          │ view:  9595     │
          └─────────────────┘
```

### Observing Parallelization

```sql
-- See thread usage for a query
SELECT
    query,
    read_rows,
    ProfileEvents['OSCPUVirtualTimeMicroseconds'] / 1000000 AS cpu_seconds,
    query_duration_ms / 1000 AS wall_seconds,
    round(cpu_seconds / wall_seconds, 1) AS parallelism_factor
FROM system.query_log
WHERE type = 'QueryFinish'
ORDER BY event_time DESC
LIMIT 5;

-- parallelism_factor ≈ number of cores actually used
-- If wall_time = 1s and cpu_time = 8s → 8 cores were used
```

### Distributed Query Parallelism

```sql
-- On a 4-shard cluster:
SELECT uniq(user_id) FROM events_distributed WHERE date = today();

-- Execution:
-- 1. Coordinator sends subquery to all 4 shards
-- 2. Each shard uses all its local cores (e.g., 16 each)
-- 3. Each shard returns partial uniq state
-- 4. Coordinator merges partial states into final result

-- Total parallelism: 4 shards × 16 cores = 64-way parallel
```

---

## 9. MergeTree Smart Engine

### What Makes MergeTree "Smart"

The MergeTree engine family continuously **optimizes data in the background**:

```
INSERT (fast, append-only)
  │
  ▼
┌────────────────────────────┐
│  New "Part" on disk        │
│  (unsorted within insert)  │
│  (sorted by ORDER BY)      │
└────────────────────────────┘
  │
  ▼ (background merge)
┌────────────────────────────┐
│  Merged larger Part        │
│  - More compressible       │
│  - Better sorted           │
│  - Fewer parts to scan     │
└────────────────────────────┘
```

### The Merge Process

```
Time T1: After many inserts
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Part_1 │ │Part_2 │ │Part_3 │ │Part_4 │ │Part_5 │
│100 MB │ │ 50 MB │ │ 80 MB │ │ 20 MB │ │ 40 MB │
└───────┘ └───────┘ └───────┘ └───────┘ └───────┘

Time T2: After background merge
┌─────────────────┐ ┌───────────────────┐
│   Part_1_3      │ │    Part_4_5       │
│   230 MB        │ │    60 MB          │
│ (better sorted) │ │ (better compressed)│
└─────────────────┘ └───────────────────┘

Time T3: After more merges
┌─────────────────────────────────────┐
│          Part_1_5                    │
│          290 MB (maximally merged)  │
│  - Perfect sort order               │
│  - Optimal compression              │
│  - Single part to scan              │
└─────────────────────────────────────┘
```

### MergeTree Variants

```sql
-- Standard MergeTree: basic sorted storage
ENGINE = MergeTree()

-- ReplacingMergeTree: deduplicates by ORDER BY key (keeps latest version)
ENGINE = ReplacingMergeTree(version_column)

-- AggregatingMergeTree: merges rows by aggregating (for materialized views)
ENGINE = AggregatingMergeTree()

-- CollapsingMergeTree: handles updates via +1/-1 sign rows
ENGINE = CollapsingMergeTree(sign)

-- VersionedCollapsingMergeTree: like Collapsing but with version tracking
ENGINE = VersionedCollapsingMergeTree(sign, version)

-- SummingMergeTree: automatically sums numeric columns during merge
ENGINE = SummingMergeTree((column1, column2))
```

### ReplacingMergeTree Example (Handling Updates)

```sql
CREATE TABLE user_profiles (
    user_id     UInt64,
    name        String,
    email       String,
    updated_at  DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY user_id;

-- Insert original
INSERT INTO user_profiles VALUES (1, 'Alice', 'alice@old.com', '2024-01-01 00:00:00');

-- "Update" by inserting new version
INSERT INTO user_profiles VALUES (1, 'Alice', 'alice@new.com', '2024-03-15 10:30:00');

-- Before merge: both rows exist
-- After merge: only the row with latest updated_at survives

-- Force merge for testing:
OPTIMIZE TABLE user_profiles FINAL;

-- Query with guaranteed deduplication (without waiting for merge):
SELECT * FROM user_profiles FINAL WHERE user_id = 1;
```

### SummingMergeTree Example (Real-Time Aggregation)

```sql
CREATE TABLE daily_metrics (
    date        Date,
    metric_name LowCardinality(String),
    host        LowCardinality(String),
    value       Float64,
    count       UInt64
) ENGINE = SummingMergeTree((value, count))
ORDER BY (date, metric_name, host);

-- Multiple inserts for same key:
INSERT INTO daily_metrics VALUES ('2024-03-15', 'requests', 'web-1', 150, 1);
INSERT INTO daily_metrics VALUES ('2024-03-15', 'requests', 'web-1', 200, 1);
INSERT INTO daily_metrics VALUES ('2024-03-15', 'requests', 'web-1', 180, 1);

-- After merge: automatically summed!
-- ('2024-03-15', 'requests', 'web-1', 530, 3)
```

### Monitoring Merge Activity

```sql
-- Current merge activity
SELECT
    database,
    table,
    elapsed,
    progress,
    num_parts,
    formatReadableSize(total_size_bytes_compressed) AS size
FROM system.merges;

-- Part statistics
SELECT
    partition,
    count() AS parts,
    sum(rows) AS total_rows,
    formatReadableSize(sum(bytes_on_disk)) AS disk_size
FROM system.parts
WHERE table = 'events' AND active
GROUP BY partition
ORDER BY partition;
```

### TTL (Time-To-Live): Automatic Data Lifecycle

```sql
CREATE TABLE events (
    timestamp DateTime,
    data      String
) ENGINE = MergeTree()
ORDER BY timestamp
TTL timestamp + INTERVAL 90 DAY DELETE,          -- delete after 90 days
    timestamp + INTERVAL 30 DAY TO DISK 'cold',  -- move to cold storage after 30 days
    timestamp + INTERVAL 7 DAY TO VOLUME 'ssd';  -- keep recent on SSD
```

---

## 10. Materialized Views

### The Problem: Expensive Repeated Aggregations

```sql
-- Dashboard query executed every 5 seconds by 50 users:
SELECT
    toStartOfMinute(timestamp) AS minute,
    service,
    count() AS requests,
    avg(response_ms) AS avg_latency,
    quantile(0.99)(response_ms) AS p99_latency
FROM request_logs                    -- 10 billion rows!
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY minute, service;

-- Without materialized view: scans ~500M rows every 5 seconds
-- With materialized view: reads pre-computed result (~1000 rows)
```

### How Materialized Views Work

```
                 INSERT into source table
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│              Source Table (request_logs)           │
│              10 billion rows, raw data            │
└───────────────────────┬──────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          │ Trigger MV  │ Trigger MV  │
          ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ MV: per-min │ │ MV: per-hr  │ │ MV: top URLs│
│ aggregation │ │ aggregation │ │ aggregation │
│ ~1K rows/min│ │ ~100 rows/hr│ │ ~500 rows   │
└─────────────┘ └─────────────┘ └─────────────┘
```

### Complete Example: Dashboard Acceleration

```sql
-- Step 1: Source table (raw events)
CREATE TABLE request_logs (
    timestamp    DateTime,
    service      LowCardinality(String),
    endpoint     String,
    method       LowCardinality(String),
    status_code  UInt16,
    response_ms  UInt32,
    user_id      UInt64
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service, timestamp);

-- Step 2: Target table for materialized view
CREATE TABLE request_metrics_1m (
    minute       DateTime,
    service      LowCardinality(String),
    requests     UInt64,
    errors       UInt64,
    sum_ms       UInt64,
    max_ms       UInt32,
    p99_state    AggregateFunction(quantile(0.99), UInt32)
) ENGINE = AggregatingMergeTree()
ORDER BY (service, minute);

-- Step 3: Materialized view (transforms on INSERT)
CREATE MATERIALIZED VIEW request_metrics_1m_mv
TO request_metrics_1m
AS SELECT
    toStartOfMinute(timestamp) AS minute,
    service,
    count() AS requests,
    countIf(status_code >= 500) AS errors,
    sum(response_ms) AS sum_ms,
    max(response_ms) AS max_ms,
    quantileState(0.99)(response_ms) AS p99_state
FROM request_logs
GROUP BY minute, service;
```

### Querying the Materialized View

```sql
-- Dashboard query: instant response from pre-aggregated data
SELECT
    minute,
    service,
    requests,
    errors,
    round(sum_ms / requests) AS avg_ms,
    max_ms,
    quantileMerge(0.99)(p99_state) AS p99_ms
FROM request_metrics_1m
WHERE minute > now() - INTERVAL 1 HOUR
GROUP BY minute, service, requests, errors, sum_ms, max_ms
ORDER BY minute DESC;

-- Scans ~60 rows per service (1 per minute × 60 minutes)
-- Instead of millions of raw rows!
```

### Multi-Level Aggregation (Roll-Up Pattern)

```sql
-- Level 1: Per-minute (from raw data)
CREATE MATERIALIZED VIEW metrics_1m_mv TO metrics_1m AS
SELECT toStartOfMinute(ts) AS period, service, count() AS cnt, sum(val) AS total
FROM raw_events GROUP BY period, service;

-- Level 2: Per-hour (from per-minute)
CREATE MATERIALIZED VIEW metrics_1h_mv TO metrics_1h AS
SELECT toStartOfHour(period) AS period, service, sum(cnt) AS cnt, sum(total) AS total
FROM metrics_1m GROUP BY period, service;

-- Level 3: Per-day (from per-hour)
CREATE MATERIALIZED VIEW metrics_1d_mv TO metrics_1d AS
SELECT toStartOfDay(period) AS period, service, sum(cnt) AS cnt, sum(total) AS total
FROM metrics_1h GROUP BY period, service;
```

```
Dashboard timeframe → Query source:
  Last 1 hour     → metrics_1m  (60 rows per service)
  Last 24 hours   → metrics_1h  (24 rows per service)
  Last 30 days    → metrics_1d  (30 rows per service)
  Last 1 year     → metrics_1d  (365 rows per service)
```

### Important: Materialized View Gotchas

```sql
-- 1. MVs only process NEW inserts (not existing data!)
--    Backfill manually:
INSERT INTO request_metrics_1m
SELECT toStartOfMinute(timestamp) AS minute, service, count(), ...
FROM request_logs
WHERE timestamp < '2024-03-01'  -- existing data
GROUP BY minute, service;

-- 2. MVs see only the INSERT block, not the full table
--    This means JOINs in MVs join against the INSERT block, not all data

-- 3. If MV target table is AggregatingMergeTree,
--    you MUST use -State/-Merge function pairs:
--    quantileState() in the MV → quantileMerge() when querying

-- 4. Dropping a MV doesn't drop its target table (and vice versa)
DROP VIEW request_metrics_1m_mv;     -- drops the trigger only
DROP TABLE request_metrics_1m;        -- drops the stored data
```

---

## Performance Comparison Summary

| Technique | What It Skips | Typical Speedup | When to Use |
|-----------|--------------|-----------------|-------------|
| Columnar Storage | Unused columns | 5-50x | Always (it's the storage engine) |
| Compression | Redundant bytes | 2-5x I/O speed | Always (automatic) |
| Sparse Index | Irrelevant granules | 10-1000x | Queries on ORDER BY columns |
| Partition Pruning | Entire partitions | 2-12x | Time-range or tenant queries |
| Data Skipping | Granule groups | 5-100x | Queries on non-ORDER BY columns |
| PREWHERE | Heavy column reads | 2-25x | Selective filters + large columns |
| Vectorization | CPU cycles | 4-32x | All operations (automatic) |
| Parallelization | Wall clock time | Nx (N=cores) | All queries (automatic) |
| MergeTree Merge | Fragmentation | 2-5x over time | Background (automatic) |
| Materialized Views | Redundant computation | 100-10000x | Repeated dashboard queries |

---

## Query Optimization Checklist

```sql
-- 1. Check which optimizations fired
EXPLAIN indexes = 1
SELECT ... FROM table WHERE ...;

-- 2. Check actual I/O
SELECT
    query,
    read_rows,
    read_bytes,
    result_rows,
    query_duration_ms
FROM system.query_log
WHERE type = 'QueryFinish'
ORDER BY event_time DESC LIMIT 10;

-- 3. Check if PREWHERE was used
EXPLAIN SYNTAX SELECT ... FROM table WHERE ...;
-- Shows rewritten query with PREWHERE

-- 4. Check partition pruning
EXPLAIN PLAN SELECT ... FROM table WHERE date = today();
-- Shows "Parts: X/Y" where X < Y means pruning worked

-- 5. Check index usage
SET send_logs_level = 'debug';
SELECT ... FROM table WHERE ...;
-- Logs show: "Selected N marks by primary key out of M marks"
```
