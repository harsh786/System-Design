# Apache Iceberg on S3 — Storage Layer Deep Dive

## Why S3 is the Default Choice for Iceberg

S3 (and S3-compatible stores like MinIO, GCS, Azure Blob) is the dominant storage backend for Iceberg because:

1. **Infinite scale**: No capacity planning. Store petabytes without provisioning.
2. **Durability**: 99.999999999% (11 nines) — data is replicated across AZs.
3. **Cost**: $0.023/GB/month for Standard. Cold data on Glacier at $0.004/GB.
4. **Decoupled compute**: Any engine (Spark, Flink, Trino) reads the same files.
5. **Immutable objects**: Iceberg writes immutable files — perfect fit for object stores.

```
┌─────────────────────────────────────────────────────────────┐
│                    ICEBERG TABLE ON S3                        │
│                                                              │
│  s3://warehouse/db/orders/                                   │
│  ├── metadata/                                               │
│  │   ├── v1.metadata.json          ← Metadata files         │
│  │   ├── v2.metadata.json                                    │
│  │   ├── snap-1234.avro            ← Manifest lists          │
│  │   ├── snap-5678.avro                                      │
│  │   ├── manifest-abc.avro         ← Manifest files          │
│  │   └── manifest-def.avro                                   │
│  └── data/                                                   │
│      ├── date=2024-01-15/                                    │
│      │   ├── 00001-abc.parquet     ← Data files              │
│      │   └── 00002-def.parquet                               │
│      └── date=2024-01-16/                                    │
│          └── 00003-ghi.parquet                               │
└─────────────────────────────────────────────────────────────┘
```

---

## S3 Consistency Model & Iceberg

### S3 Strong Consistency (Since Dec 2020)

AWS S3 now provides **strong read-after-write consistency** for all operations:
- PUT new object → immediately readable
- DELETE object → immediately reflects
- LIST after write → immediately includes new object

**Before 2020**, S3 had eventual consistency for overwrites and deletes. This was a MAJOR problem for table formats because:
- A writer could overwrite a metadata file, but readers might see the old version
- Iceberg was designed to work around this by using **immutable files + atomic pointer swap**

### How Iceberg Leverages S3 Consistency

```
┌───────────────────────────────────────────────────────────┐
│  WRITE PATH (Commit Protocol on S3)                        │
│                                                            │
│  1. Writer creates new data files (immutable)              │
│     PUT s3://warehouse/data/00004-xyz.parquet              │
│                                                            │
│  2. Writer creates new manifest file (immutable)           │
│     PUT s3://warehouse/metadata/manifest-ghi.avro          │
│                                                            │
│  3. Writer creates new manifest list (immutable)           │
│     PUT s3://warehouse/metadata/snap-9999.avro             │
│                                                            │
│  4. Writer creates new metadata file (immutable)           │
│     PUT s3://warehouse/metadata/v3.metadata.json           │
│                                                            │
│  5. ATOMIC COMMIT: Update catalog pointer                  │
│     Catalog: "orders" → v3.metadata.json                   │
│     (This is the ONLY mutable operation)                   │
└───────────────────────────────────────────────────────────┘
```

**Key insight**: Iceberg never overwrites files on S3. Every write creates NEW files. The only "mutable" part is the catalog pointer (stored in Glue/Hive/Nessie, NOT on S3).

---

## S3 Performance Optimization for Iceberg

### Problem: S3 Latency

| Operation | Latency | Cost |
|-----------|---------|------|
| GET (single file) | 50-100ms | $0.0004 per 1000 requests |
| PUT (single file) | 100-200ms | $0.005 per 1000 requests |
| LIST (per 1000 objects) | 200-500ms | $0.005 per 1000 requests |
| HEAD (metadata check) | 50-100ms | $0.0004 per 1000 requests |

### How Iceberg Optimizes S3 Access

#### 1. Eliminate LIST Operations

**Hive approach** (bad):
```
# To read table "orders" partitioned by date:
LIST s3://warehouse/orders/                        → 365 directories
LIST s3://warehouse/orders/date=2024-01-01/        → 50 files
LIST s3://warehouse/orders/date=2024-01-02/        → 48 files
... (365 more LIST calls)
# Total: 366 LIST operations just to find the files!
```

**Iceberg approach** (good):
```
# To read table "orders":
GET s3://warehouse/metadata/v3.metadata.json       → 1 file (has snapshot pointer)
GET s3://warehouse/metadata/snap-9999.avro         → 1 file (manifest list)
GET s3://warehouse/metadata/manifest-abc.avro      → 1 file (file list with stats)
# Total: 3 GET operations to know ALL files in the table!
```

#### 2. File-Level Pruning (Skip Irrelevant Files)

```
Query: SELECT * FROM orders WHERE amount > 1000 AND date = '2024-01-15'

Manifest file contains per-file stats:
┌──────────────────────────────────────────────────────┐
│ File: 00001-abc.parquet                               │
│   partition: date=2024-01-15                          │
│   record_count: 50000                                 │
│   amount: min=5.00, max=950.00     ← SKIP (max<1000)│
├──────────────────────────────────────────────────────┤
│ File: 00002-def.parquet                               │
│   partition: date=2024-01-15                          │
│   record_count: 48000                                 │
│   amount: min=100.00, max=5000.00  ← READ            │
├──────────────────────────────────────────────────────┤
│ File: 00003-ghi.parquet                               │
│   partition: date=2024-01-16       ← SKIP (wrong dt) │
│   record_count: 52000                                 │
│   amount: min=1.00, max=2000.00                       │
└──────────────────────────────────────────────────────┘

Result: Read only 1 of 3 files → 67% reduction in S3 GETs
```

#### 3. S3 Request Parallelism

Iceberg engines read multiple data files in parallel:

```
┌─────────────────────────────────────────────────┐
│  Spark Executor (or Trino Worker)                │
│                                                  │
│  Thread 1 ──→ GET 00002-def.parquet (part 1)    │
│  Thread 2 ──→ GET 00002-def.parquet (part 2)    │
│  Thread 3 ──→ GET 00005-jkl.parquet (part 1)    │
│  Thread 4 ──→ GET 00005-jkl.parquet (part 2)    │
│                                                  │
│  S3 prefix: each partition gets unique prefix    │
│  → avoids S3 throttling (3500 GET/s per prefix) │
└─────────────────────────────────────────────────┘
```

#### 4. S3 Request Throttling & Partitioning

S3 limits: **3,500 PUT/COPY/POST/DELETE** and **5,500 GET/HEAD** requests per second **per prefix**.

Iceberg handles this by:
- Distributing data files across multiple prefixes
- Using hash-based file naming to spread load
- Manifest files reference files across many prefixes

```
# Good: Files spread across prefixes
s3://warehouse/data/a1/00001.parquet
s3://warehouse/data/b2/00002.parquet
s3://warehouse/data/c3/00003.parquet

# Bad: All files in same prefix
s3://warehouse/data/00001.parquet
s3://warehouse/data/00002.parquet   ← Will hit throttle at scale
s3://warehouse/data/00003.parquet
```

---

## S3 Cost Analysis for Iceberg

### Storage Costs

| Tier | $/GB/month | Use Case |
|------|-----------|----------|
| S3 Standard | $0.023 | Hot data (recent partitions, active queries) |
| S3 Infrequent Access | $0.0125 | Warm data (30-90 day old partitions) |
| S3 Glacier Instant | $0.004 | Cold data (regulatory archive, time travel) |
| S3 Glacier Deep | $0.00099 | Frozen data (compliance, rarely accessed) |

### Request Costs (Often Dominates!)

**Example: Analytic query scanning 10TB table**

| Approach | Requests | Cost per Query |
|----------|----------|---------------|
| Hive (LIST all) | 100,000 LISTs + 50,000 GETs | ~$0.75 |
| Iceberg (targeted) | 3 metadata GETs + 500 data GETs | ~$0.002 |

**Annual savings at 1000 queries/day**: $0.75 × 1000 × 365 = **$273,750** vs $0.002 × 1000 × 365 = **$730**

### Data Transfer Costs

- Same region (compute → S3): **FREE**
- Cross region: $0.02/GB — avoid this!
- Internet egress: $0.09/GB — use VPC endpoints

**Best Practice**: Keep compute cluster and S3 bucket in the **same region**.

---

## S3 Storage Lifecycle for Iceberg

### Tiered Storage Strategy

```
┌─────────────────────────────────────────────────────────┐
│                  DATA LIFECYCLE                           │
│                                                          │
│  Day 0-7:     S3 Standard (hot queries, recent data)    │
│  Day 7-30:    S3 Standard-IA (less frequent queries)    │
│  Day 30-90:   S3 Glacier Instant (time travel archive)  │
│  Day 90-365:  S3 Glacier Flexible (compliance)          │
│  Day 365+:    S3 Glacier Deep Archive (legal hold)      │
│                                                          │
│  ★ IMPORTANT: Only move DATA files to cold tiers        │
│  ★ Keep METADATA files in Standard (needed for queries) │
└─────────────────────────────────────────────────────────┘
```

### S3 Lifecycle Policy Example

```json
{
  "Rules": [
    {
      "ID": "IcebergDataTiering",
      "Filter": { "Prefix": "warehouse/db/orders/data/" },
      "Transitions": [
        { "Days": 30, "StorageClass": "STANDARD_IA" },
        { "Days": 90, "StorageClass": "GLACIER_IR" },
        { "Days": 365, "StorageClass": "DEEP_ARCHIVE" }
      ]
    },
    {
      "ID": "KeepMetadataHot",
      "Filter": { "Prefix": "warehouse/db/orders/metadata/" },
      "Transitions": []
    }
  ]
}
```

### Iceberg Snapshot Expiration

Old snapshots accumulate metadata and prevent file deletion:

```sql
-- Expire snapshots older than 7 days (keeps recent time travel)
CALL system.expire_snapshots('db.orders', TIMESTAMP '2024-01-08 00:00:00');

-- Remove orphan files (data files not referenced by any snapshot)
CALL system.remove_orphan_files('db.orders');
```

**Warning**: After expiring snapshots, old data files become orphans. Run `remove_orphan_files` to actually delete them from S3 and save storage costs.

---

## S3 Security for Iceberg

### Access Control Layers

```
┌─────────────────────────────────────────────────┐
│  Layer 1: IAM Policies                           │
│  ─ Who can access which S3 paths                 │
│  ─ Fine-grained: read-only on data/,             │
│    read-write on metadata/ for writers           │
│                                                  │
│  Layer 2: S3 Bucket Policies                     │
│  ─ Cross-account access                          │
│  ─ VPC endpoint restrictions                     │
│                                                  │
│  Layer 3: Encryption                             │
│  ─ SSE-S3 (default, no cost)                     │
│  ─ SSE-KMS (audit trail via CloudTrail)          │
│  ─ CSE (client-side, max security)              │
│                                                  │
│  Layer 4: Catalog-Level Auth                     │
│  ─ AWS Lake Formation                            │
│  ─ Apache Ranger                                 │
│  ─ Column/row-level security                     │
└─────────────────────────────────────────────────┘
```

### IAM Policy Example (Least Privilege)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IcebergReadOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-warehouse",
        "arn:aws:s3:::my-warehouse/db/orders/*"
      ]
    },
    {
      "Sid": "IcebergWriter",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::my-warehouse/db/orders/*",
      "Condition": {
        "StringEquals": { "aws:PrincipalTag/team": "data-engineering" }
      }
    }
  ]
}
```

---

## S3 Failure Modes & Iceberg Resilience

### What Happens When S3 Fails?

| Failure | Impact | Iceberg Handling |
|---------|--------|-----------------|
| S3 GET timeout | Query fails for that file | Retry with exponential backoff |
| S3 PUT fails mid-write | Partial file on S3 | Commit never happens → orphan file (cleaned later) |
| S3 throttled (429) | Slow queries | Engines retry; spread prefixes |
| S3 eventual consistency (pre-2020) | Stale reads | N/A (fixed by S3 since Dec 2020) |
| Catalog unavailable | Can't resolve table | No reads or writes until catalog recovers |

### Iceberg's Immutability Guarantee

Because Iceberg never modifies existing files:
- A reader that started before a write completes will see the old snapshot
- A writer that fails leaves orphan files (no corruption)
- Recovery = expire old snapshots + clean orphans (no data loss)

```
Writer 1: PUT file-A.parquet ✓
Writer 1: PUT manifest-new.avro ✓
Writer 1: PUT v4.metadata.json ✓
Writer 1: Update catalog → FAILS (network error)

Result:
- file-A.parquet exists on S3 (orphan)
- Table still points to v3.metadata.json (safe)
- No reader ever sees partial state
- Next cleanup removes file-A.parquet
```

---

## Real-World S3 Configuration for Iceberg

### Spark Configuration

```python
spark = SparkSession.builder \
    .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.my_catalog.type", "glue") \
    .config("spark.sql.catalog.my_catalog.warehouse", "s3://my-warehouse/") \
    .config("spark.sql.catalog.my_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.sql.catalog.my_catalog.s3.endpoint", "https://s3.us-east-1.amazonaws.com") \
    .config("spark.hadoop.fs.s3a.connection.maximum", "200") \
    .config("spark.hadoop.fs.s3a.fast.upload", "true") \
    .config("spark.hadoop.fs.s3a.path.style.access", "false") \
    .getOrCreate()
```

### Key S3 Tuning Parameters

| Parameter | Default | Recommended | Why |
|-----------|---------|-------------|-----|
| `s3.multipart.size` | 32MB | 64MB | Fewer requests for large files |
| `s3.multipart.threshold` | 128MB | 128MB | Use multipart for files >128MB |
| `fs.s3a.connection.maximum` | 96 | 200 | More parallel downloads |
| `fs.s3a.threads.max` | 10 | 64 | Parallel file operations |
| `fs.s3a.connection.timeout` | 200000ms | 60000ms | Fail fast on issues |
| `fs.s3a.attempts.maximum` | 20 | 5 | Don't retry too long |

---

## Summary: Iceberg + S3 Design Principles

1. **Never overwrite**: All files are immutable objects on S3. Mutations happen via new files + metadata pointer swap.
2. **Minimize requests**: Metadata-driven file pruning reduces S3 GETs from thousands to dozens.
3. **Same region**: Keep compute and storage co-located to avoid transfer costs.
4. **Lifecycle tiers**: Move old data files to Glacier. Keep metadata in Standard.
5. **Parallel reads**: Spread files across prefixes to avoid S3 throttling.
6. **Clean regularly**: Expire snapshots + remove orphans to control storage costs.
7. **Encrypt everything**: SSE-KMS for audit trail, bucket policies for access control.
