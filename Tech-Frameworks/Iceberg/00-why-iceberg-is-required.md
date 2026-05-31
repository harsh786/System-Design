# Why Apache Iceberg Is Required

## The Promise of Object Storage as a Data Lake

S3 (and similar object stores) offers unlimited scale, low cost, and durability. Companies moved
their data lakes to S3 hoping to unify analytics. But raw S3 is a **file system**, not a **table
format**. The gap between "bucket of files" and "queryable analytical table" is enormous.

---

## What Happens Without Iceberg (Raw S3 Problems)

### Problem 1: No ACID Transactions

```
Writer A: uploads part-00001.parquet → SUCCESS
Writer B: uploads part-00002.parquet → SUCCESS
Writer A: updates manifest file      → SUCCESS
Writer B: updates manifest file      → OVERWRITES A's entry

Result: part-00001.parquet is orphaned, data is LOST silently
```

S3 has no multi-object atomic operations. You cannot atomically add 5 files to a "table."
If a writer crashes mid-operation, you get partial writes with no rollback.

**Real-world impact**: ETL jobs that run concurrently corrupt the table. Teams resort to
time-based "windows" where only one writer runs at a time — killing throughput.

---

### Problem 2: No Schema Enforcement

```
Day 1:  team writes {user_id: INT, name: STRING, age: INT}
Day 30: team writes {user_id: STRING, full_name: STRING, birth_year: INT}

Both land in the same S3 prefix. No error. No warning.
```

S3 stores bytes. It does not know or care about column types. When schemas drift:
- Downstream queries fail with cryptic deserialization errors
- Data scientists waste days debugging "why did my model break?"
- Nobody knows which version of the schema is "correct"

---

### Problem 3: No Efficient Query Filtering

```
Query: SELECT * FROM events WHERE event_date = '2026-01-15'

Without Iceberg:
  → List ALL objects in s3://bucket/events/ (could be 500,000 files)
  → Open each Parquet file footer to check date range
  → Read matching files
  Cost: $$$, Time: minutes

With Iceberg:
  → Read metadata (tiny JSON file)
  → Manifest files say exactly which data files contain 2026-01-15
  → Read only those 3 files
  Cost: $, Time: seconds
```

The S3 `ListObjects` API is paginated (1000 objects/call), slow, and expensive at scale.
Without metadata-level pruning, every query does a full directory scan.

---

### Problem 4: The Small File Problem

```
Streaming pipeline writes every 30 seconds:
  → 2 files/minute × 60 minutes × 24 hours = 2,880 files/day
  → After 1 year: 1,051,200 tiny files

Each file: 5 MB
Optimal file for analytics: 256 MB - 512 MB
```

Small files destroy query performance because:
- Each file requires a separate S3 GET request (network overhead)
- Parquet/ORC metadata is per-file (redundant headers)
- Query engines spend more time opening files than reading data

Without Iceberg, you must build custom compaction jobs with fragile coordination logic.

---

### Problem 5: No UPDATE or DELETE

```sql
-- GDPR request: "Delete user 12345's data"
-- In raw S3:

-- Step 1: Find which files contain user 12345 (scan everything?)
-- Step 2: Read those files entirely into memory
-- Step 3: Filter out user 12345's rows
-- Step 4: Write new files without that user
-- Step 5: Delete old files
-- Step 6: Hope no reader was using the old files

-- If anything fails midway? Inconsistent state.
```

Object storage is append-only. You cannot edit a byte range inside a Parquet file.
Every "update" requires a full rewrite of affected files, with no transactional safety.

---

### Problem 6: No Time Travel or Audit Trail

```
Analyst: "Our revenue numbers changed between Monday and today. What happened?"
Engineer: "Someone overwrote the files. The old data is gone."
Analyst: "Can we see what it looked like before?"
Engineer: "No."
```

Once you overwrite files in S3, the old version is gone (unless you enable S3 versioning,
which is unmanaged and expensive). There's no concept of table-level snapshots.

---

### Problem 7: No Partition Evolution

```
Original partitioning: year/month/day
New requirement: need hourly partitions for recent data

Without Iceberg:
  → Rewrite entire table with new partition layout
  → 50 TB of data to reprocess
  → 3 days of compute, $$$$ cost
  → Downstream jobs all break because paths changed

With Iceberg:
  → ALTER TABLE events SET PARTITION SPEC (hour(event_time))
  → Old data stays where it is
  → New data uses hourly partitions
  → Queries transparently span both layouts
```

---

### Problem 8: No Concurrent Reader/Writer Safety

```
Timeline:
  T0: Reader starts query, lists files [A, B, C]
  T1: Writer starts compaction, merges A+B → D, deletes A and B
  T2: Reader tries to read file B → 404 NOT FOUND → Query fails

This is called a "phantom read" or "read instability" problem.
```

Without snapshot isolation, readers see a moving target. There's no way to guarantee
a consistent view of the data while writers are active.

---

## The Netflix Origin Story

Netflix hit these problems at scale around 2017:

```
Scale:
  - Petabytes of data in S3
  - Thousands of Hive tables
  - Hundreds of concurrent writers (Spark jobs)
  - Partition listings taking 10+ minutes

Pain points:
  1. Hive metastore was the bottleneck (single MySQL DB tracking all partitions)
  2. Adding a partition required an exclusive lock on the table
  3. S3 listing was eventually consistent (before Dec 2020)
  4. No way to safely compact files while readers were active
  5. Schema changes required rewriting entire tables
```

Netflix built Iceberg to solve ALL of these problems with a single design:
**Track table state in immutable metadata files, not a central database.**

---

## What Iceberg Solves

### 1. ACID Transactions via Optimistic Concurrency

```
How it works:
  ┌─────────────────────────────────────────────────┐
  │ Writer reads current metadata pointer: v5       │
  │ Writer does its work (creates new data files)   │
  │ Writer creates new metadata: v6                 │
  │ Writer atomically swaps pointer: v5 → v6       │
  │   (uses S3 conditional PUT or catalog lock)     │
  │ If pointer was already changed → RETRY          │
  └─────────────────────────────────────────────────┘

Guarantees:
  - All-or-nothing commits (no partial writes visible)
  - Serializable isolation between writers
  - Readers always see a complete, consistent snapshot
```

---

### 2. Schema Evolution Without Rewriting Data

```sql
-- Add a column
ALTER TABLE events ADD COLUMN country STRING;
-- Old files don't have 'country' → Iceberg returns NULL for them
-- New files include 'country'
-- No data rewrite needed

-- Rename a column
ALTER TABLE events RENAME COLUMN user_name TO full_name;
-- Iceberg tracks columns by ID, not name
-- Old Parquet files still work (mapped by column ID 7 → "full_name")

-- Widen a type
ALTER TABLE events ALTER COLUMN age TYPE BIGINT;
-- INT → BIGINT is safe (every INT is a valid BIGINT)
-- No rewrite needed
```

---

### 3. Hidden Partitioning

```sql
-- Raw S3/Hive approach (user must know partition layout):
SELECT * FROM events
WHERE year = 2026 AND month = 1 AND day = 15;  -- user manages partition columns

-- Iceberg approach (partition is derived automatically):
CREATE TABLE events (..., event_time TIMESTAMP)
PARTITIONED BY (days(event_time));

SELECT * FROM events
WHERE event_time = '2026-01-15 10:30:00';
-- Iceberg automatically prunes to the correct partition
-- User never thinks about partition columns
```

---

### 4. Time Travel and Rollback

```sql
-- Query data as it existed yesterday
SELECT * FROM events TIMESTAMP AS OF '2026-01-14 00:00:00';

-- Query a specific snapshot
SELECT * FROM events VERSION AS OF 923748172;

-- Rollback a bad write
CALL system.rollback_to_snapshot('events', 923748171);
-- Instantly restores previous state (just swaps a metadata pointer)
-- No data copying
```

---

### 5. Metadata-Driven Query Planning

```
Query: WHERE country = 'US' AND event_date > '2026-01-01'

Iceberg's planning:
  1. Read manifest list (1 file, ~10 KB)
  2. Check each manifest's partition summary
     → Skip manifests where max(event_date) < '2026-01-01'
  3. For remaining manifests, check column-level stats
     → Skip data files where min(country) > 'US' or max(country) < 'US'
  4. Result: read 12 files out of 50,000

Traditional S3 scan: open all 50,000 files to check
Iceberg metadata pruning: read 12 files

Speedup: 4000x fewer file reads
```

---

### 6. Safe Compaction and Maintenance

```
Without Iceberg:
  Compact files A, B, C → D
  Delete A, B, C
  (Readers using A, B, C get 404 errors)

With Iceberg:
  Compact files A, B, C → D
  Commit new snapshot: {remove: [A,B,C], add: [D]}
  Old snapshots still reference A, B, C
  Readers on old snapshots still work
  After snapshot expiry (e.g., 7 days): safely delete A, B, C
```

---

### 7. Multi-Engine Access

```
Same table, multiple engines, no conflicts:

  Flink (streaming) → writes every 30 seconds  ─┐
  Spark (batch)     → runs daily compaction     ─┤→ Same Iceberg table
  Trino (ad-hoc)   → analysts run queries      ─┤   in S3
  PyTorch (ML)     → reads training features   ─┘

All engines see consistent snapshots.
All engines respect the same schema.
No custom integration code needed.
```

---

## Before vs After: Summary

| Concern | Raw S3 | S3 + Iceberg |
|---------|--------|--------------|
| Concurrent writes | Data corruption | ACID commits |
| Schema changes | Rewrite everything | Metadata-only update |
| Query a subset | Scan all files | Prune via manifest stats |
| Delete a row | Rewrite + pray | Transactional delete |
| See yesterday's data | Gone forever | Time travel query |
| Change partition layout | Rewrite entire table | `ALTER TABLE`, zero rewrite |
| Small files | Manual compaction scripts | Built-in safe compaction |
| Reader/writer conflicts | 404 errors, inconsistency | Snapshot isolation |
| Multi-engine access | Custom glue code per engine | Standard table format |
| Compliance (GDPR delete) | Weeks of engineering | `DELETE WHERE user_id = X` |

---

## When You DON'T Need Iceberg

Iceberg adds complexity. Skip it when:

- **Single writer, append-only**: Just dump Parquet files with a naming convention
- **Small data (< 100 GB)**: A single Parquet file with partitions is fine
- **No concurrent readers/writers**: No transaction conflicts to worry about
- **No schema evolution needed**: Fixed schema, batch-load-and-query pattern
- **Operational databases**: Use PostgreSQL/DynamoDB — Iceberg is for analytics

---

## The Core Insight

```
S3 gives you: durable, cheap, unlimited STORAGE

Iceberg gives you: TABLE SEMANTICS on top of that storage
  - Transactions (atomic commits)
  - Schema (evolution without rewrites)
  - Performance (metadata-driven pruning)
  - Time travel (snapshot history)
  - Isolation (readers never see partial writes)

Without Iceberg, S3 is a bucket of files.
With Iceberg, S3 is a lakehouse database.
```

The magic is that Iceberg achieves all of this using **only files in S3** — no external
database, no running service, no single point of failure. The metadata IS the table format,
stored as immutable files alongside your data.
