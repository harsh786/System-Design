# Pattern 13: Data Partitioning Strategies

## Why Partitioning Matters

```
WITHOUT PARTITIONING:
  Query: SELECT * FROM events WHERE date = '2024-01-15'
  Action: Scan ALL 1 PB of data
  Time: 30 minutes
  Cost: $5 (S3 reads)

WITH DATE PARTITIONING:
  Query: SELECT * FROM events WHERE date = '2024-01-15'
  Action: Read only 1 day's partition = 3 TB
  Time: 30 seconds
  Cost: $0.015

IMPROVEMENT: 1000x faster, 330x cheaper
```

## Partitioning Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PARTITIONING STRATEGIES FOR DATA LAKES                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. TIME-BASED (Most Common)                                                 │
│  ───────────────────────────                                                 │
│  s3://lake/events/year=2024/month=01/day=15/hour=10/                        │
│                                                                              │
│  When: Time-series data, queries always filter by time                       │
│  Granularity decision:                                                       │
│  • Year: Archival queries (rare)                                             │
│  • Month: Monthly reports                                                    │
│  • Day: Most analytical queries (DEFAULT CHOICE)                             │
│  • Hour: High-volume + need hourly freshness                                 │
│  • Minute: AVOID (too many partitions = small files = slow)                  │
│                                                                              │
│  Rule: Each partition should have 100MB-1GB of data                          │
│        If hourly partition < 100MB → use daily instead                       │
│                                                                              │
│  2. HASH-BASED                                                               │
│  ───────────────                                                             │
│  s3://lake/users/hash_bucket=0/                                              │
│  s3://lake/users/hash_bucket=1/                                              │
│  ...                                                                         │
│  s3://lake/users/hash_bucket=99/                                             │
│                                                                              │
│  When: Evenly distribute data, join optimization                             │
│  How: hash(user_id) % 100 = bucket number                                   │
│  Benefit: Bucket-pruning on joins (only join matching buckets)               │
│                                                                              │
│  3. RANGE-BASED                                                              │
│  ──────────────                                                              │
│  s3://lake/products/price_range=0-100/                                       │
│  s3://lake/products/price_range=100-500/                                     │
│  s3://lake/products/price_range=500+/                                        │
│                                                                              │
│  When: Queries filter by range (price, age, score)                           │
│  Challenge: Skew (most products might be $0-100)                             │
│                                                                              │
│  4. LIST-BASED                                                               │
│  ─────────────                                                               │
│  s3://lake/orders/country=US/                                                │
│  s3://lake/orders/country=UK/                                                │
│  s3://lake/orders/country=DE/                                                │
│                                                                              │
│  When: Categorical column with limited values                                │
│  Benefit: Perfect pruning for equality filters                               │
│  Risk: Cardinality too high → partition explosion                            │
│                                                                              │
│  5. COMPOSITE (Multi-level)                                                  │
│  ──────────────────────────                                                  │
│  s3://lake/events/date=2024-01-15/country=US/category=electronics/           │
│                                                                              │
│  When: Queries filter on multiple dimensions                                 │
│  Order matters: Put highest-cardinality LAST (fewer directories to list)     │
│  Rule of thumb: date first (always filtered), then next most common filter   │
│                                                                              │
│  6. HIDDEN PARTITIONING (Iceberg Innovation)                                 │
│  ────────────────────────────────────────────                                │
│  Table: partitioned by day(timestamp), bucket(user_id, 100)                  │
│  Users DON'T specify partition in queries:                                   │
│  SELECT * FROM events WHERE timestamp = '2024-01-15' AND user_id = 'abc'     │
│  → Engine automatically prunes to correct partition                          │
│  → No need for "WHERE year=2024 AND month=01 AND day=15" boilerplate        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Anti-Patterns

```
PARTITION EXPLOSION:
  Bad: PARTITION BY (user_id)  → 100M partitions, each 1 row
  Fix: PARTITION BY (date) or bucket(user_id, 256)

TOO FINE GRANULARITY:
  Bad: PARTITION BY (timestamp_minute) → 525,600 partitions/year × tiny files
  Fix: PARTITION BY (date) → 365 partitions/year, proper file sizes

PARTITION BY HIGH-CARDINALITY STRING:
  Bad: PARTITION BY (email) → millions of single-row partitions
  Fix: PARTITION BY (date) + CLUSTER BY (email) within partition

UNUSED PARTITION COLUMN:
  Bad: PARTITION BY (internal_batch_id) → queries never filter on it
  Fix: PARTITION BY (date) (matches actual query patterns)
```

## Partition Evolution (Iceberg)

```
SCENARIO: Your queries changed. You used to query by date, now also by region.

TRADITIONAL (Hive/Delta): Rewrite entire table with new partition scheme
  Cost: Scan + rewrite 1 PB = hours + $$$

ICEBERG: Partition evolution (metadata-only change!)
  ALTER TABLE events ADD PARTITION FIELD region;
  • Old data: still partitioned by date only
  • New data: partitioned by date + region
  • Query engine handles both transparently
  • No data rewrite needed!
  • Background optimize can reorganize old data gradually
```

