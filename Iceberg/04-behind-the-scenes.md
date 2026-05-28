# Apache Iceberg — Behind the Scenes

## Write Path (How Data Gets Into Iceberg)

### Overview: The Immutable Write Protocol

Every write in Iceberg follows a strict protocol: create new immutable files, then atomically update a single pointer. Nothing is ever overwritten.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ICEBERG WRITE PATH                                 │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  WRITE   │    │  CREATE  │    │  CREATE  │    │  ATOMIC  │      │
│  │   DATA   │───▶│ MANIFEST │───▶│ METADATA │───▶│  COMMIT  │      │
│  │  FILES   │    │  FILES   │    │   FILE   │    │ (catalog)│      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │                │               │               │            │
│       ▼                ▼               ▼               ▼            │
│  s3://data/        s3://meta/      s3://meta/     Catalog DB        │
│  new parquet       manifest.avro   v4.json        pointer swap      │
│  (immutable)       (immutable)     (immutable)    (ONLY mutable)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Step-by-Step: INSERT Operation

**Example:** `INSERT INTO orders VALUES (1001, 'laptop', 999.99, '2024-01-15')`

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Write Data File(s) to S3                                │
│                                                                  │
│  Writer buffers rows in memory until target file size (128MB)    │
│  Then flushes to Parquet on S3:                                  │
│                                                                  │
│  PUT s3://warehouse/data/date=2024-01-15/                        │
│      00004-{uuid}-{attempt}.parquet                              │
│                                                                  │
│  File naming: {partition_id}-{uuid}-{attempt_id}.parquet         │
│  ─ UUID ensures no collisions between concurrent writers         │
│  ─ Attempt ID handles retries without duplicates                 │
│                                                                  │
│  At this point: file exists on S3, but NO reader can see it     │
│  (no manifest references it yet)                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Create Manifest File                                    │
│                                                                  │
│  Writer creates an Avro file listing the new data file(s):       │
│                                                                  │
│  PUT s3://warehouse/metadata/manifest-{uuid}.avro                │
│                                                                  │
│  Contents:                                                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ status: ADDED                                           │     │
│  │ file_path: s3://warehouse/data/.../00004-xyz.parquet    │     │
│  │ file_format: PARQUET                                    │     │
│  │ partition: {date: "2024-01-15"}                         │     │
│  │ record_count: 1                                         │     │
│  │ file_size_bytes: 4096                                   │     │
│  │ column_sizes: {1: 12, 2: 28, 3: 8, 4: 12}             │     │
│  │ value_counts: {1: 1, 2: 1, 3: 1, 4: 1}                │     │
│  │ null_counts: {1: 0, 2: 0, 3: 0, 4: 0}                 │     │
│  │ lower_bounds: {1: 1001, 2: "laptop", 3: 999.99}        │     │
│  │ upper_bounds: {1: 1001, 2: "laptop", 3: 999.99}        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Still invisible to readers — no snapshot references this yet    │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Create Manifest List (Snapshot)                         │
│                                                                  │
│  PUT s3://warehouse/metadata/snap-{snapshot-id}.avro              │
│                                                                  │
│  Contents: list of ALL manifests for this table version          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ manifest_path: manifest-abc.avro (existing, unchanged)  │     │
│  │   added_files: 0, deleted_files: 0                      │     │
│  │   partition_summary: date ∈ [2024-01-01, 2024-01-14]    │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │ manifest_path: manifest-{uuid}.avro (NEW)               │     │
│  │   added_files: 1, deleted_files: 0                      │     │
│  │   partition_summary: date ∈ [2024-01-15, 2024-01-15]    │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Create New Metadata File                                │
│                                                                  │
│  PUT s3://warehouse/metadata/v4.metadata.json                    │
│                                                                  │
│  Contents:                                                       │
│  {                                                               │
│    "format-version": 2,                                          │
│    "table-uuid": "abc-123",                                      │
│    "current-snapshot-id": 9999,                                  │
│    "snapshots": [                                                │
│      {"snapshot-id": 1234, "manifest-list": "snap-1234.avro"},   │
│      {"snapshot-id": 5678, "manifest-list": "snap-5678.avro"},   │
│      {"snapshot-id": 9999, "manifest-list": "snap-9999.avro"}    │
│    ],                                                            │
│    "current-schema-id": 0,                                       │
│    "schemas": [...],                                             │
│    "partition-specs": [...]                                       │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Atomic Commit (Catalog Update)                          │
│                                                                  │
│  This is the ONLY mutable operation in the entire flow:          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Catalog (e.g., AWS Glue):                          │        │
│  │                                                      │        │
│  │  Compare-And-Swap:                                   │        │
│  │    IF current_metadata == "v3.metadata.json"         │        │
│  │    THEN SET current_metadata = "v4.metadata.json"    │        │
│  │    ELSE → CONFLICT (retry from step 1)              │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  After this succeeds:                                            │
│  ─ All readers immediately see the new data                      │
│  ─ Previous snapshot (v3) is still valid for time travel         │
│  ─ The commit is atomic — readers see either all or nothing      │
└─────────────────────────────────────────────────────────────────┘
```

### Concurrent Writers: Optimistic Concurrency Control

```
Timeline:
─────────────────────────────────────────────────────────────────────

Writer A reads:   table → v3.metadata.json
Writer B reads:   table → v3.metadata.json

Writer A:  creates data files, manifests, v4.metadata.json
Writer B:  creates data files, manifests, v4b.metadata.json

Writer A commits: CAS(v3 → v4) ✓  SUCCESS
Writer B commits: CAS(v3 → v4b) ✗  CONFLICT!

Writer B retries:
  ─ Reads current state: v4.metadata.json (Writer A's version)
  ─ Checks: does my change conflict with A's?
    ─ If adding to different partitions: NO conflict → rebase + retry
    ─ If modifying same files: YES conflict → abort or merge logic
  ─ Creates v5.metadata.json (incorporating both A's and B's changes)
  ─ CAS(v4 → v5) ✓  SUCCESS

Final state: v5 contains both Writer A's and Writer B's data
```

**Conflict Resolution Rules:**
| Writer A | Writer B | Conflict? | Resolution |
|----------|----------|-----------|------------|
| INSERT (new partition) | INSERT (different partition) | No | Auto-rebase |
| INSERT (same partition) | INSERT (same partition) | No | Auto-rebase (different files) |
| DELETE file X | DELETE file X | Yes | One wins, one retries |
| DELETE file X | UPDATE file X | Yes | Depends on isolation level |
| COMPACT files [A,B,C] | INSERT into same partition | No | Compaction retries |

---

### Step-by-Step: UPDATE Operation (Copy-on-Write)

**Example:** `UPDATE orders SET amount = 1099.99 WHERE id = 1001`

```
┌─────────────────────────────────────────────────────────────────┐
│  COPY-ON-WRITE (CoW) UPDATE                                      │
│                                                                  │
│  Before: Snapshot S3                                             │
│  ├── file-A.parquet (rows 1-1000, includes id=1001)             │
│  ├── file-B.parquet (rows 1001-2000)                            │
│  └── file-C.parquet (rows 2001-3000)                            │
│                                                                  │
│  Step 1: Identify file(s) containing id=1001                    │
│          → Use manifest stats (min/max on id column)            │
│          → file-A.parquet has id range [1, 1000] wait...        │
│            Actually, id=1001 means row with order_id=1001       │
│          → Scan manifests: file-A has id ∈ [1, 1500]            │
│          → Read file-A, find row with id=1001                   │
│                                                                  │
│  Step 2: Create NEW file with the updated row                   │
│          → file-D.parquet = file-A minus row(1001)              │
│            + modified row(1001, amount=1099.99)                  │
│                                                                  │
│  Step 3: New manifest marks:                                    │
│          ─ file-A: status=DELETED                               │
│          ─ file-D: status=ADDED                                 │
│                                                                  │
│  After: Snapshot S4                                              │
│  ├── file-D.parquet (rows 1-1000, id=1001 updated) ← NEW       │
│  ├── file-B.parquet (unchanged, same reference)                 │
│  └── file-C.parquet (unchanged, same reference)                 │
│                                                                  │
│  file-A still exists on S3 (for time travel to S3)              │
└─────────────────────────────────────────────────────────────────┘
```

**Cost:** To update 1 row in a 128MB file, you rewrite the entire file. This is why CoW is good for batch updates but bad for row-level changes.

---

### Step-by-Step: UPDATE Operation (Merge-on-Read)

**Example:** Same update, but using Merge-on-Read (MoR) mode:

```
┌─────────────────────────────────────────────────────────────────┐
│  MERGE-ON-READ (MoR) UPDATE                                      │
│                                                                  │
│  Instead of rewriting file-A, we write TWO small files:          │
│                                                                  │
│  1. Position Delete File:                                        │
│     ┌────────────────────────────────┐                          │
│     │ delete-{uuid}.parquet          │                          │
│     │ file_path: file-A.parquet      │                          │
│     │ pos: 500  (row position 500)   │  ← "row 500 is deleted" │
│     └────────────────────────────────┘                          │
│                                                                  │
│  2. Data File (with new value):                                  │
│     ┌────────────────────────────────┐                          │
│     │ file-D.parquet                 │                          │
│     │ id=1001, amount=1099.99, ...   │  ← "replacement row"    │
│     └────────────────────────────────┘                          │
│                                                                  │
│  At READ time, the engine:                                       │
│  1. Reads file-A.parquet                                         │
│  2. Applies position deletes (skips row 500)                    │
│  3. Appends rows from file-D.parquet                            │
│  4. Returns merged result                                        │
│                                                                  │
│  Trade-off:                                                      │
│  ─ Write: FAST (tiny delete file + tiny data file)              │
│  ─ Read: SLOWER (must merge at query time)                       │
│  ─ Over time: Accumulates delete files → needs compaction        │
└─────────────────────────────────────────────────────────────────┘
```

### DELETE Variants

```
┌─────────────────────────────────────────────────────────────────┐
│  DELETE FILE TYPES IN ICEBERG V2                                  │
│                                                                  │
│  1. Position Delete Files:                                       │
│     ─ Records: (file_path, row_position) pairs                   │
│     ─ Fastest to apply (direct lookup by position)               │
│     ─ Used by: Flink, Spark in MoR mode                         │
│                                                                  │
│  2. Equality Delete Files:                                       │
│     ─ Records: column values that identify deleted rows          │
│     ─ Example: {id: 1001} means "delete all rows with id=1001"  │
│     ─ Slower to apply (must check every row against predicates) │
│     ─ Used by: streaming systems that don't know row positions  │
│                                                                  │
│  Both are Parquet files stored alongside data files.             │
│  Compaction later merges them into clean data files.             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Read Path (How Queries Find Data)

### Query Planning: Metadata-Driven File Selection

```
Query: SELECT * FROM orders 
       WHERE date = '2024-01-15' AND amount > 500

┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: Catalog Lookup (1 RPC)                                 │
│                                                                  │
│  Catalog.loadTable("db.orders")                                  │
│  → Returns: s3://warehouse/metadata/v4.metadata.json             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: Read Metadata File (1 S3 GET)                          │
│                                                                  │
│  Parse v4.metadata.json:                                         │
│  ─ Current snapshot: 9999                                        │
│  ─ Manifest list: snap-9999.avro                                 │
│  ─ Partition spec: days(date)                                    │
│  ─ Schema: {1:id INT, 2:item STRING, 3:amount DECIMAL, 4:date}  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: Read Manifest List (1 S3 GET) — MANIFEST PRUNING      │
│                                                                  │
│  snap-9999.avro contains:                                        │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ Manifest: manifest-001.avro                          │        │
│  │   partition_summary: date ∈ [2024-01-01, 2024-01-14] │        │
│  │   → SKIP (date=2024-01-15 not in range)             │        │
│  ├─────────────────────────────────────────────────────┤        │
│  │ Manifest: manifest-002.avro                          │        │
│  │   partition_summary: date ∈ [2024-01-15, 2024-01-31] │        │
│  │   → READ (might contain our data)                    │        │
│  ├─────────────────────────────────────────────────────┤        │
│  │ Manifest: manifest-003.avro                          │        │
│  │   partition_summary: date ∈ [2024-02-01, 2024-02-28] │        │
│  │   → SKIP (wrong month entirely)                      │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  Result: 2 of 3 manifests pruned (67% reduction)                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: Read Manifest File (1 S3 GET) — FILE PRUNING           │
│                                                                  │
│  manifest-002.avro contains:                                     │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ File: data/date=2024-01-15/00001.parquet             │        │
│  │   partition: date=2024-01-15    ✓ (matches filter)   │        │
│  │   amount: min=5.00, max=200.00                       │        │
│  │   → SKIP (max=200 < 500, filter is amount>500)      │        │
│  ├─────────────────────────────────────────────────────┤        │
│  │ File: data/date=2024-01-15/00002.parquet             │        │
│  │   partition: date=2024-01-15    ✓                    │        │
│  │   amount: min=100.00, max=5000.00                    │        │
│  │   → READ (range overlaps with amount>500)            │        │
│  ├─────────────────────────────────────────────────────┤        │
│  │ File: data/date=2024-01-16/00003.parquet             │        │
│  │   partition: date=2024-01-16                         │        │
│  │   → SKIP (wrong partition)                           │        │
│  ├─────────────────────────────────────────────────────┤        │
│  │ File: data/date=2024-01-15/00004.parquet             │        │
│  │   partition: date=2024-01-15    ✓                    │        │
│  │   amount: min=800.00, max=2000.00                    │        │
│  │   → READ (range overlaps)                            │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  Result: 2 of 4 files need reading (50% reduction)              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: Read Data Files (2 S3 GETs, parallel)                  │
│                                                                  │
│  For each selected Parquet file:                                 │
│  1. Read Parquet footer (column stats, row group offsets)        │
│  2. Apply row group pruning (skip row groups where max<500)     │
│  3. Read only needed columns (id, item, amount, date)           │
│  4. Apply remaining predicates on rows                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────┐            │
│  │  Parquet Internal Pruning:                       │            │
│  │                                                  │            │
│  │  00002.parquet has 4 row groups:                 │            │
│  │   RG1: amount ∈ [100, 300]  → SKIP              │            │
│  │   RG2: amount ∈ [250, 800]  → READ (partial)    │            │
│  │   RG3: amount ∈ [600, 2000] → READ              │            │
│  │   RG4: amount ∈ [3000, 5000]→ READ              │            │
│  └─────────────────────────────────────────────────┘            │
│                                                                  │
│  Total S3 operations: 1 (catalog) + 1 + 1 + 1 + 2 = 6 GETs    │
│  vs. Hive: potentially hundreds of LIST + GET operations        │
└─────────────────────────────────────────────────────────────────┘
```

### Read Path with Delete Files (MoR)

```
┌─────────────────────────────────────────────────────────────────┐
│  MERGE-ON-READ AT QUERY TIME                                     │
│                                                                  │
│  When manifest entry has associated delete files:                │
│                                                                  │
│  Manifest entry for 00002.parquet:                               │
│    data_file: 00002.parquet (50,000 rows)                        │
│    delete_files: [delete-001.parquet, delete-002.parquet]        │
│                                                                  │
│  Read process:                                                   │
│  1. Read 00002.parquet → 50,000 rows in memory                  │
│  2. Read delete-001.parquet → positions [500, 1200, 3400]       │
│  3. Read delete-002.parquet → positions [7800]                  │
│  4. Remove rows at positions 500, 1200, 3400, 7800             │
│  5. Return 49,996 rows                                           │
│                                                                  │
│  Performance impact:                                             │
│  ─ 1 delete file per data file: ~5% overhead                    │
│  ─ 10 delete files per data file: ~30% overhead                 │
│  ─ 50+ delete files: SEVERE degradation → needs compaction      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compaction (Rewriting for Performance)

### Why Compaction Is Necessary

Over time, Iceberg tables accumulate problems:

```
┌─────────────────────────────────────────────────────────────────┐
│  PROBLEMS THAT COMPACTION SOLVES                                  │
│                                                                  │
│  1. Small Files (from streaming inserts):                        │
│     ─ Flink writes every 1 minute → 1440 files/day/partition    │
│     ─ Each file: 1-5 MB instead of target 128-512 MB            │
│     ─ Impact: Too many S3 GETs, task scheduling overhead        │
│                                                                  │
│  2. Delete File Accumulation (from MoR updates):                 │
│     ─ Each UPDATE creates a delete file                          │
│     ─ 1000 updates → 1000 delete files to apply at read time   │
│     ─ Impact: Read performance degrades linearly                 │
│                                                                  │
│  3. Unoptimized Sort Order:                                      │
│     ─ Data written in arrival order, not query order             │
│     ─ Related rows scattered across many files                   │
│     ─ Impact: File pruning less effective, more files scanned    │
│                                                                  │
│  4. Skewed File Sizes:                                           │
│     ─ Mix of 1MB and 500MB files in same partition               │
│     ─ Impact: Uneven task parallelism, some tasks take 100x     │
└─────────────────────────────────────────────────────────────────┘
```

### Compaction Strategies

#### 1. Bin-Pack Compaction (Most Common)

```
┌─────────────────────────────────────────────────────────────────┐
│  BIN-PACK: Combine small files into target-size files            │
│                                                                  │
│  Before (partition date=2024-01-15):                             │
│  ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐                    │
│  │2M││3M││1M││4M││2M││1M││3M││2M││1M││2M│  = 10 files, 21MB   │
│  └──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘                    │
│                                                                  │
│  After bin-pack (target: 128MB, but data is only 21MB):          │
│  ┌─────────────────────────────────────────┐                    │
│  │              21 MB                       │  = 1 file          │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  Realistic scenario (1440 files from streaming, 2GB total):     │
│  Before: 1440 files × ~1.4MB each                               │
│  After:  16 files × ~128MB each                                  │
│                                                                  │
│  SQL:                                                            │
│  CALL system.rewrite_data_files(                                 │
│    table => 'db.orders',                                         │
│    strategy => 'binpack',                                        │
│    options => map(                                                │
│      'target-file-size-bytes', '134217728',   -- 128MB           │
│      'min-file-size-bytes', '104857600',      -- 100MB           │
│      'max-file-size-bytes', '180355072',      -- 172MB           │
│      'min-input-files', '5'                   -- don't compact   │
│    )                                                             │  -- if fewer than 5 small files
│  );                                                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. Sort Compaction (Optimizes Query Performance)

```
┌─────────────────────────────────────────────────────────────────┐
│  SORT: Rewrite files with data sorted by query-relevant columns  │
│                                                                  │
│  Before (arrival order — poor file pruning):                     │
│  ┌─────────────────────┐                                        │
│  │ file-1: customer_id ∈ [1, 99999]  (all customers mixed)     │
│  │ file-2: customer_id ∈ [1, 99999]  (all customers mixed)     │
│  │ file-3: customer_id ∈ [1, 99999]  (all customers mixed)     │
│  └─────────────────────┘                                        │
│  Query WHERE customer_id = 500 → must read ALL files            │
│                                                                  │
│  After sort by customer_id:                                      │
│  ┌─────────────────────┐                                        │
│  │ file-1: customer_id ∈ [1, 33333]      ← READ (500 is here) │
│  │ file-2: customer_id ∈ [33334, 66666]  ← SKIP               │
│  │ file-3: customer_id ∈ [66667, 99999]  ← SKIP               │
│  └─────────────────────┘                                        │
│  Query WHERE customer_id = 500 → reads ONLY file-1              │
│                                                                  │
│  SQL:                                                            │
│  CALL system.rewrite_data_files(                                 │
│    table => 'db.orders',                                         │
│    strategy => 'sort',                                           │
│    sort_order => 'customer_id ASC NULLS LAST, order_date DESC'  │
│  );                                                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Z-Order Compaction (Multi-Dimensional Clustering)

```
┌─────────────────────────────────────────────────────────────────┐
│  Z-ORDER: Optimize for queries on MULTIPLE columns               │
│                                                                  │
│  Problem: Sort by customer_id is great for customer queries,     │
│  but terrible for date range queries (dates scattered in files)  │
│                                                                  │
│  Z-order interleaves bits of multiple columns:                   │
│                                                                  │
│  Visual (2D space of customer_id × date):                        │
│                                                                  │
│  Sort by customer_id only:    Z-Order (customer_id, date):       │
│  ┌───┬───┬───┬───┐           ┌───┬───┬───┬───┐                 │
│  │ 1 │ 1 │ 1 │ 1 │           │ 1 │ 2 │ 5 │ 6 │                 │
│  ├───┼───┼───┼───┤           ├───┼───┼───┼───┤                 │
│  │ 2 │ 2 │ 2 │ 2 │  file#    │ 3 │ 4 │ 7 │ 8 │  file#          │
│  ├───┼───┼───┼───┤           ├───┼───┼───┼───┤                 │
│  │ 3 │ 3 │ 3 │ 3 │           │ 9 │ 10│ 13│ 14│                 │
│  ├───┼───┼───┼───┤           ├───┼───┼───┼───┤                 │
│  │ 4 │ 4 │ 4 │ 4 │           │ 11│ 12│ 15│ 16│                 │
│  └───┘───┘───┘───┘           └───┘───┘───┘───┘                 │
│   ↑ great for cust,           ↑ good for BOTH customer          │
│     bad for date                AND date queries                 │
│                                                                  │
│  SQL:                                                            │
│  CALL system.rewrite_data_files(                                 │
│    table => 'db.orders',                                         │
│    strategy => 'sort',                                           │
│    sort_order => 'zorder(customer_id, order_date)'              │
│  );                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Compaction: Behind the Scenes

```
┌─────────────────────────────────────────────────────────────────┐
│  WHAT HAPPENS DURING COMPACTION                                   │
│                                                                  │
│  1. Select files to compact:                                     │
│     ─ Files smaller than target size                             │
│     ─ Files with many associated delete files                    │
│     ─ Files in partitions matching a filter                      │
│                                                                  │
│  2. Read selected files (applying any delete files):             │
│     ─ Load rows from data files                                  │
│     ─ Apply position/equality deletes                            │
│     ─ Result: clean, merged row set                              │
│                                                                  │
│  3. Write new data files:                                        │
│     ─ Sorted (if sort/zorder strategy)                           │
│     ─ Target file size (128-512 MB)                              │
│     ─ Fresh column statistics                                    │
│                                                                  │
│  4. Commit atomically:                                           │
│     ─ New manifest: marks old files as DELETED, new as ADDED    │
│     ─ New snapshot references new manifest list                  │
│     ─ Catalog pointer: v4 → v5                                  │
│                                                                  │
│  5. Old files become eligible for cleanup:                       │
│     ─ Still referenced by old snapshots (time travel)           │
│     ─ Deleted from S3 only after snapshot expiration             │
│                                                                  │
│  IMPORTANT: Compaction is itself a write transaction!            │
│  ─ Uses optimistic concurrency                                   │
│  ─ Can conflict with concurrent writers                          │
│  ─ If a writer adds files to the same partition during           │
│    compaction, compaction retries (doesn't lose new data)        │
└─────────────────────────────────────────────────────────────────┘
```

### Production Compaction Schedule

```
┌─────────────────────────────────────────────────────────────────┐
│  TYPICAL COMPACTION STRATEGY                                      │
│                                                                  │
│  ┌─────────────────────────────────────────────┐                │
│  │  Streaming Table (Flink writes every minute) │                │
│  │                                              │                │
│  │  Every 1 hour:  Bin-pack recent partitions   │                │
│  │  Every 6 hours: Sort compaction on hot data  │                │
│  │  Every 24 hours: Full sort on yesterday's    │                │
│  │                  partition (final layout)     │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
│  ┌─────────────────────────────────────────────┐                │
│  │  Batch Table (Spark writes daily)            │                │
│  │                                              │                │
│  │  After each write: Check file count          │                │
│  │  If >20 files in partition: Bin-pack         │                │
│  │  Weekly: Z-order on analytical columns       │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
│  Trigger compaction when:                                        │
│  ─ avg_file_size < 50% of target (too many small files)         │
│  ─ delete_file_count > 10 per data file                         │
│  ─ After large batch ingestion completes                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Garbage Collection (Cleaning Up Old Data)

### What Accumulates Over Time

```
┌─────────────────────────────────────────────────────────────────┐
│  GARBAGE TYPES IN ICEBERG                                        │
│                                                                  │
│  1. Expired Snapshots:                                           │
│     ─ Every write creates a snapshot                             │
│     ─ 100 writes/day × 365 days = 36,500 snapshots             │
│     ─ Each snapshot = metadata files on S3 (manifest lists)     │
│                                                                  │
│  2. Orphan Files:                                                │
│     ─ Writer creates data file, then commit fails               │
│     ─ File exists on S3 but no snapshot references it           │
│     ─ Compaction replaces old files with new files              │
│       (old files become orphans after snapshot expiration)       │
│                                                                  │
│  3. Old Metadata Files:                                          │
│     ─ v1.metadata.json, v2.metadata.json, ...                   │
│     ─ Only latest is needed for current reads                    │
│     ─ Old ones needed for time travel to those versions         │
│                                                                  │
│  4. Old Manifest Files:                                          │
│     ─ Referenced only by expired snapshots                       │
│     ─ After expiration, no longer needed                         │
└─────────────────────────────────────────────────────────────────┘
```

### Snapshot Expiration

```
┌─────────────────────────────────────────────────────────────────┐
│  EXPIRE_SNAPSHOTS: Remove old snapshots + unreachable files      │
│                                                                  │
│  Before expiration (table with 5 snapshots):                     │
│                                                                  │
│  S1 ──→ [file-A, file-B, file-C]                                │
│  S2 ──→ [file-A, file-B, file-C, file-D]                        │
│  S3 ──→ [file-A, file-B, file-D, file-E]  (C deleted, E added) │
│  S4 ──→ [file-A, file-D, file-E, file-F]  (B deleted, F added) │
│  S5 ──→ [file-A, file-D, file-E, file-F, file-G]  (current)    │
│                                                                  │
│  Command: Expire snapshots older than 3 days                     │
│  (assume S1, S2, S3 are older than 3 days)                      │
│                                                                  │
│  After expiration:                                               │
│  ─ Snapshots S1, S2, S3 are removed from metadata               │
│  ─ file-C is DELETE-able (only referenced by S1, S2)            │
│  ─ file-B is DELETE-able (only referenced by S1, S2, S3)        │
│  ─ file-A is KEPT (still referenced by S4, S5)                  │
│  ─ file-D is KEPT (referenced by S4, S5)                        │
│                                                                  │
│  SQL:                                                            │
│  CALL system.expire_snapshots(                                   │
│    table => 'db.orders',                                         │
│    older_than => TIMESTAMP '2024-01-12 00:00:00',               │
│    retain_last => 5,    -- always keep at least 5 snapshots     │
│    max_concurrent_deletes => 100  -- parallel S3 delete limit   │
│  );                                                              │
│                                                                  │
│  What it does:                                                   │
│  1. Identifies snapshots to expire                               │
│  2. Finds data files ONLY referenced by expired snapshots       │
│  3. Deletes those data files from S3                             │
│  4. Removes expired snapshot entries from metadata               │
│  5. Removes now-unreferenced manifest files                      │
└─────────────────────────────────────────────────────────────────┘
```

### Orphan File Removal

```
┌─────────────────────────────────────────────────────────────────┐
│  REMOVE_ORPHAN_FILES: Find and delete unreferenced files         │
│                                                                  │
│  How orphans appear:                                             │
│                                                                  │
│  Scenario 1: Failed commit                                       │
│  ─ Writer creates file-X.parquet on S3                           │
│  ─ Catalog CAS fails (conflict)                                  │
│  ─ Writer doesn't retry or retries with different files         │
│  ─ file-X.parquet sits on S3 forever, never referenced          │
│                                                                  │
│  Scenario 2: Post-compaction + expiration                        │
│  ─ Compaction: file-A + file-B → file-C (new combined file)    │
│  ─ Commit succeeds: new snapshot uses file-C                    │
│  ─ OLD snapshot still references file-A, file-B (time travel)  │
│  ─ Expire old snapshot: file-A, file-B become orphans           │
│  ─ expire_snapshots SHOULD delete them, but sometimes misses   │
│                                                                  │
│  Algorithm:                                                      │
│  1. LIST all files in s3://warehouse/data/ and metadata/         │
│  2. Load ALL snapshots → collect set of referenced files        │
│  3. Orphans = files_on_s3 - referenced_files                    │
│  4. Delete orphans (with safety: only if older than threshold)  │
│                                                                  │
│  SQL:                                                            │
│  CALL system.remove_orphan_files(                                │
│    table => 'db.orders',                                         │
│    older_than => TIMESTAMP '2024-01-08 00:00:00',               │
│    dry_run => true  -- ALWAYS dry-run first!                    │
│  );                                                              │
│                                                                  │
│  ⚠️  WARNING: This is EXPENSIVE on large tables!                │
│  ─ Lists EVERY file on S3 (potentially millions)                 │
│  ─ Loads ALL metadata to build reference set                     │
│  ─ Run during off-peak hours only                                │
│  ─ Set older_than to at least 3 days (avoid racing with writes) │
└─────────────────────────────────────────────────────────────────┘
```

### Metadata Cleanup: Rewrite Manifests

```
┌─────────────────────────────────────────────────────────────────┐
│  REWRITE_MANIFESTS: Optimize manifest file organization          │
│                                                                  │
│  Problem: Over time, manifest files become fragmented            │
│  ─ Each small commit adds a new manifest                         │
│  ─ Some manifests reference just 1-2 files                       │
│  ─ Manifest list grows large → more S3 GETs at read time       │
│                                                                  │
│  Before: 500 manifest files (from 500 individual commits)        │
│  ┌─────┐┌─────┐┌─────┐    ┌─────┐                             │
│  │ m1  ││ m2  ││ m3  │....│m500 │  (1-3 files each)            │
│  │1file││2file││1file│    │2file│                               │
│  └─────┘└─────┘└─────┘    └─────┘                             │
│                                                                  │
│  After rewrite_manifests:                                        │
│  ┌──────────────────┐┌──────────────────┐┌────────────────┐    │
│  │    manifest-1     ││    manifest-2     ││   manifest-3   │    │
│  │   200 files       ││   200 files       ││   100 files    │    │
│  │ partition: Jan    ││ partition: Feb    ││ partition: Mar │    │
│  └──────────────────┘└──────────────────┘└────────────────┘    │
│                                                                  │
│  Benefits:                                                       │
│  ─ Fewer manifests → fewer S3 GETs during query planning       │
│  ─ Manifests organized by partition → better pruning             │
│  ─ Query planning: 500 GETs → 3 GETs                           │
│                                                                  │
│  SQL:                                                            │
│  CALL system.rewrite_manifests('db.orders');                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Maintenance Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION MAINTENANCE SCHEDULE                                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  HOURLY (for streaming tables):                             │ │
│  │  ─ Bin-pack compaction on partitions with >50 small files  │ │
│  │  ─ Target: reduce file count, not sort                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  DAILY:                                                     │ │
│  │  ─ Expire snapshots older than 7 days                      │ │
│  │    (retains at least 10 snapshots regardless of age)       │ │
│  │  ─ Sort compaction on yesterday's completed partition      │ │
│  │  ─ Rewrite manifests if manifest count > 100              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  WEEKLY:                                                    │ │
│  │  ─ Remove orphan files (older_than = 3 days)              │ │
│  │  ─ Z-order compaction on analytical tables                 │ │
│  │  ─ Review table metrics (file sizes, scan stats)          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  MONTHLY:                                                   │ │
│  │  ─ Full table statistics refresh                           │ │
│  │  ─ S3 storage class review (move cold data to Glacier)    │ │
│  │  ─ Audit snapshot retention policy                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Monitoring alerts:                                              │
│  ─ avg_file_size < 50MB → trigger immediate compaction         │
│  ─ manifest_count > 200 → trigger rewrite_manifests            │
│  ─ orphan_file_size > 1TB → investigate and clean              │
│  ─ snapshot_count > 1000 → aggressive expiration               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary: How It All Fits Together

```
┌─────────────────────────────────────────────────────────────────┐
│                     ICEBERG LIFECYCLE                             │
│                                                                  │
│  WRITE ─────────────────────────────────────────────────────▶   │
│  │ Data arrives (Spark batch / Flink streaming / API)           │
│  │ New immutable files written to S3                            │
│  │ Atomic commit via catalog CAS                                │
│  │                                                              │
│  READ ──────────────────────────────────────────────────────▶   │
│  │ Catalog → metadata → manifest list → manifest → files       │
│  │ Pruning at each level reduces I/O                            │
│  │ Delete files merged at read time (MoR) or pre-merged (CoW)  │
│  │                                                              │
│  COMPACT ───────────────────────────────────────────────────▶   │
│  │ Small files → large files (bin-pack)                         │
│  │ Unsorted → sorted (sort/z-order)                             │
│  │ Data + deletes → clean data (merge deletes)                  │
│  │ Compaction itself is a write transaction                     │
│  │                                                              │
│  CLEAN ─────────────────────────────────────────────────────▶   │
│  │ Expire old snapshots (free metadata)                         │
│  │ Remove orphan files (free storage)                           │
│  │ Rewrite manifests (optimize planning)                        │
│  │ Move cold data to Glacier (reduce cost)                      │
└─────────────────────────────────────────────────────────────────┘
```
