# Apache Iceberg — Fundamentals & Architecture

## What is Apache Iceberg?

Apache Iceberg is an **open table format** for huge analytic datasets. It was created at Netflix (2017) and donated to Apache (2018). It defines how data files, metadata, and schema are organized on storage (S3, HDFS, GCS, Azure Blob).

**Key Insight:** Iceberg is NOT a storage engine, NOT a query engine, NOT a database. It is a **specification** that tells any engine how to read and write a table correctly with ACID semantics.

```
┌─────────────────────────────────────────────────────────────┐
│              COMPUTE ENGINES (Read/Write)                     │
│   Spark │ Flink │ Presto/Trino │ Hive │ Dremio │ Snowflake  │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  ICEBERG TABLE  │  ← Table Format Layer
                    │    FORMAT       │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│              STORAGE (Immutable Files)                        │
│         S3 │ HDFS │ GCS │ Azure Blob │ MinIO                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Why Was Iceberg Created?

### Problems with Hive Table Format

| Problem | Hive Behavior | Iceberg Solution |
|---------|--------------|-----------------|
| **Partition Discovery** | LIST all directories on every query | Metadata tracks exact file list |
| **Schema Evolution** | Breaks readers on column add/rename | Full schema evolution with column IDs |
| **Hidden Partitioning** | Users must know partition layout | Partition spec is abstracted away |
| **No ACID** | Partial writes visible to readers | Snapshot isolation via atomic commits |
| **No Time Travel** | Only current state visible | Full snapshot history |
| **Slow Queries** | Scans all files in partition | Fine-grained file-level filtering |

### Real Problem at Netflix

Netflix had 10,000+ Hive tables on S3. A single `SELECT COUNT(*)` on a large table would issue **millions** of S3 LIST requests (each costing money and taking time). Partition pruning required users to know the exact layout (`year=2024/month=01/day=15`). Schema changes broke downstream pipelines.

---

## Core Architecture

### Three Layers of Metadata

```
┌─────────────────────────────────────────────┐
│  CATALOG (Pointer to current metadata)       │
│  ─ Stores: table name → metadata file path   │
│  ─ Examples: Hive Metastore, AWS Glue,       │
│    Nessie, REST catalog                      │
└────────────────────┬────────────────────────┘
                     │ points to
                     ▼
┌─────────────────────────────────────────────┐
│  METADATA FILE (JSON)                        │
│  ─ Current schema (with column IDs)          │
│  ─ Partition spec                            │
│  ─ List of snapshots                         │
│  ─ Current snapshot pointer                  │
│  ─ Table properties                          │
└────────────────────┬────────────────────────┘
                     │ each snapshot points to
                     ▼
┌─────────────────────────────────────────────┐
│  MANIFEST LIST (Avro file)                   │
│  ─ List of manifest files for this snapshot  │
│  ─ Partition range summaries per manifest    │
│  ─ Added/deleted file counts                 │
└────────────────────┬────────────────────────┘
                     │ each entry points to
                     ▼
┌─────────────────────────────────────────────┐
│  MANIFEST FILE (Avro file)                   │
│  ─ List of data files                        │
│  ─ Per-file: path, format, record count      │
│  ─ Per-file: column-level min/max/null stats │
│  ─ Per-file: partition values                │
└────────────────────┬────────────────────────┘
                     │ points to
                     ▼
┌─────────────────────────────────────────────┐
│  DATA FILES (Parquet / ORC / Avro)           │
│  ─ Actual rows of data                       │
│  ─ Column-oriented, compressed               │
│  ─ Immutable once written                    │
└─────────────────────────────────────────────┘
```

### Why This Layered Approach?

1. **Catalog Layer**: Atomic pointer swap = atomic commit. Changing one pointer atomically publishes a new table version.
2. **Metadata File**: Contains ALL schema versions, partition specs, and snapshot history. Self-describing.
3. **Manifest List**: Enables pruning at the manifest level. If a manifest only contains data for `date=2024-01-15`, skip it entirely for queries on other dates.
4. **Manifest File**: Column-level stats enable data skipping. If `max(amount) = 100` in a file and your filter is `amount > 500`, skip that file.
5. **Data Files**: Immutable. Never modified in place. New data = new files. Deletes = delete files or position delete files.

---

## Key Concepts

### Snapshots & Time Travel

Every write operation creates a new **snapshot**. A snapshot is an immutable, complete view of the table at a point in time.

```
Snapshot 1 (t=10:00) ──→ files: [f1, f2, f3]
Snapshot 2 (t=10:30) ──→ files: [f1, f2, f3, f4]     ← INSERT added f4
Snapshot 3 (t=11:00) ──→ files: [f1, f2, f4, f5]     ← UPDATE: deleted f3, added f5
```

**Time Travel Queries:**
```sql
-- Read current state
SELECT * FROM orders;

-- Read as of a specific snapshot
SELECT * FROM orders FOR SYSTEM_TIME AS OF '2024-01-15 10:00:00';

-- Read a specific snapshot ID
SELECT * FROM orders FOR SYSTEM_VERSION AS OF 123456789;
```

### Schema Evolution

Iceberg uses **column IDs** (not column names or positions) to track columns:

```
Schema v1: {1: "id" INT, 2: "name" STRING, 3: "amount" DECIMAL}
Schema v2: {1: "id" INT, 2: "name" STRING, 3: "amount" DECIMAL, 4: "status" STRING}  ← ADD
Schema v3: {1: "id" INT, 2: "full_name" STRING, 3: "amount" DECIMAL, 4: "status" STRING}  ← RENAME
```

Old Parquet files written with Schema v1 still work because:
- Column ID 1 is always "id" regardless of position
- Column ID 4 ("status") returns NULL for old files (it didn't exist)
- Column ID 2 was renamed but same data — no rewrite needed

### Hidden Partitioning

Users write queries without knowing the partition layout:

```sql
-- User writes:
SELECT * FROM events WHERE event_time > '2024-01-15 10:00:00'

-- Iceberg internally knows partition spec:
-- partition by: days(event_time)
-- It automatically prunes partitions without user specifying year=/month=/day=
```

Partition evolution (changing the partition scheme) doesn't require rewriting data:
```sql
-- Originally partitioned by month
ALTER TABLE events SET PARTITION SPEC (months(event_time));

-- Later changed to daily (only new data uses new spec, old data keeps old spec)
ALTER TABLE events SET PARTITION SPEC (days(event_time));
```

### ACID Transactions

Iceberg achieves ACID through **optimistic concurrency control**:

1. Writer reads current table state (snapshot S1)
2. Writer creates new data files
3. Writer creates new manifest files
4. Writer attempts to commit: atomically swap metadata pointer from S1 → S2
5. If another writer committed between steps 1 and 4, **retry** from step 1

The atomic swap depends on the catalog implementation:
- **Hive Metastore**: uses database transactions
- **AWS Glue**: uses conditional updates (compare-and-swap)
- **Nessie**: uses git-like branching and merging
- **REST Catalog**: uses ETags for conditional updates

---

## Data File Formats

### Parquet (Most Common)

```
┌──────────────────────────────────────┐
│  Parquet File                         │
│  ┌──────────────────────────────┐    │
│  │ Row Group 1 (128MB default)   │    │
│  │  ├─ Column Chunk: id         │    │
│  │  ├─ Column Chunk: name       │    │
│  │  └─ Column Chunk: amount     │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │ Row Group 2                   │    │
│  │  ├─ Column Chunk: id         │    │
│  │  └─ ...                      │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │ Footer (schema + statistics)  │    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

### Why Parquet + Iceberg?

- **Column pruning**: Read only columns needed
- **Predicate pushdown**: Skip row groups based on min/max stats
- **Compression**: Snappy, ZSTD, LZ4 — columnar data compresses 5-10x
- **Encoding**: Dictionary, RLE, Delta — further reduces size

---

## Comparison with Other Table Formats

| Feature | Iceberg | Delta Lake | Hudi |
|---------|---------|------------|------|
| **Creator** | Netflix/Apache | Databricks | Uber |
| **Lock-in** | None (open spec) | Spark-first | Spark-first |
| **Multi-engine** | Excellent | Improving | Moderate |
| **Time Travel** | ✓ | ✓ | ✓ |
| **Schema Evolution** | Full (column IDs) | Limited | Limited |
| **Partition Evolution** | ✓ (no rewrite) | ✗ | ✗ |
| **Hidden Partitioning** | ✓ | ✗ | ✗ |
| **Row-level Deletes** | Copy-on-write + MOR | Copy-on-write + MOR | MOR native |
| **Catalog** | Pluggable (REST, Glue, Nessie) | Unity Catalog | Timeline |
| **Governance** | Via catalog (Nessie) | Unity Catalog | Limited |

---

## Summary

Iceberg solves:
1. **Correctness**: ACID guarantees across multiple concurrent writers
2. **Performance**: File-level pruning via metadata stats (no directory listing)
3. **Evolution**: Schema + partition changes without rewriting data
4. **Portability**: Any engine can read/write — no vendor lock-in
5. **History**: Full time travel and audit trail via snapshots
