# Pattern 19: Compaction Strategies

## The Small File Problem

```
WHY SMALL FILES ARE TERRIBLE:
═════════════════════════════
• Each file = metadata entry in catalog (Iceberg manifest, Hive metastore)
• Each file = separate S3 GET request (S3 rate limits: 5500 GET/s per prefix)
• Each file = task scheduling overhead in Spark/Flink
• 1M small files = 1M metadata entries = 30+ second plan time
• 1M small files × 1 GET each = 3+ minutes to list them all

EXAMPLE:
  Streaming pipeline appends every 60 seconds for 30 days:
  30 × 24 × 60 = 43,200 files (if 1 file per commit)
  Each file: 5 MB (tiny!)
  
  Query "give me last 7 days": scans 10,080 files
  Overhead per file: 5ms (open, seek, close)
  = 50 seconds just in file overhead!

AFTER COMPACTION:
  Merge 43,200 files → 216 files (200MB each)
  Same query: reads 72 files
  = 360ms file overhead (140x faster!)
```

## Compaction Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPACTION STRATEGIES                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. SIZE-BASED COMPACTION (Most Common)                                      │
│  ──────────────────────────────────────                                      │
│  Target: Each file should be 128MB - 1GB                                     │
│  Trigger: When partition has > N files below target size                      │
│  Action: Read small files → merge → write as larger files                    │
│                                                                              │
│  -- Delta Lake                                                               │
│  OPTIMIZE table_name WHERE date = '2024-01-15';                              │
│                                                                              │
│  -- Iceberg                                                                  │
│  CALL system.rewrite_data_files('db.table',                                  │
│    map('target-file-size-bytes', '268435456'));  -- 256MB                     │
│                                                                              │
│  2. Z-ORDER COMPACTION (Multi-dimensional Clustering)                        │
│  ────────────────────────────────────────────────────                        │
│  Not just merge files, but SORT data across multiple columns.                │
│  Colocates related data for better data skipping.                            │
│                                                                              │
│  -- Delta Lake                                                               │
│  OPTIMIZE table_name ZORDER BY (user_id, product_id);                        │
│                                                                              │
│  Result: Queries filtering on user_id OR product_id both benefit.            │
│  Without Z-ORDER: random distribution → full scan                            │
│  With Z-ORDER: data clustered → skip 90%+ of files                          │
│                                                                              │
│  3. HILBERT CURVE COMPACTION (Better than Z-ORDER)                           │
│  ─────────────────────────────────────────────────                           │
│  Z-ORDER has "jumps" in space-filling curve.                                 │
│  Hilbert curve has better locality preservation.                             │
│  Available in Iceberg (Spark) since v1.0.                                    │
│                                                                              │
│  4. TIERED COMPACTION (LSM-Tree Style)                                       │
│  ─────────────────────────────────────                                       │
│  Used by: Kafka, RocksDB, Cassandra                                          │
│                                                                              │
│  Level 0: New writes (many small files)                                      │
│  Level 1: Compacted (fewer, larger files)                                    │
│  Level 2: Further compacted (few, very large files)                          │
│                                                                              │
│  Trigger: When level has too many files → compact to next level              │
│  Trade-off: Write amplification (data rewritten multiple times)              │
│                                                                              │
│  5. TIME-BASED COMPACTION (for streaming)                                    │
│  ────────────────────────────────────────                                    │
│  Schedule: Run compaction job every hour for previous hour's data            │
│  Rule: After 1 hour, partition is "settled" → compact                        │
│  Leave recent data (still being appended) alone                              │
│                                                                              │
│  Airflow DAG:                                                                │
│  0:00 - Compact partition from 22:00-23:00 (2 hour delay)                    │
│  1:00 - Compact partition from 23:00-00:00                                   │
│  ... (rolling)                                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Production Compaction Configuration

```
RECOMMENDED SETTINGS:
────────────────────

Target file size: 256 MB (good for both scan + point queries)
  Smaller (64 MB): Better for point queries, worse for scans
  Larger (1 GB): Better for scans, worse for point queries and concurrency

Compaction frequency:
  Streaming tables: Every 1-2 hours (automated)
  Batch tables: After each daily load (part of DAG)
  On-demand: Before expensive queries (manual OPTIMIZE)

Concurrent compaction:
  Don't compact while heavy queries run (resource contention)
  Schedule during off-peak (2 AM - 6 AM)
  Or use separate compaction cluster (isolation)

MONITORING:
  • Track: avg file size, file count per partition, compaction duration
  • Alert: If avg file size < 10 MB (small file accumulation)
  • Alert: If compaction takes > 2x normal (growing data or stuck job)
```

