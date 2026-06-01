# 034 - Advanced Partitioning Strategies at Scale

## Architecture Diagram

```mermaid
graph TB
    subgraph Data Characteristics
        TIME[Time-Series Data<br/>Events, Logs, Metrics]
        ENTITY[Entity Data<br/>Users, Products]
        GEO[Geospatial Data<br/>Locations, Regions]
        MIXED[Mixed Access Patterns<br/>Ad-hoc + Scheduled]
    end

    subgraph Partitioning Strategies
        TIME_PART[Time-Based<br/>year/month/day/hour]
        HASH_PART[Hash-Based<br/>bucket(N, col)]
        COMPOSITE[Composite<br/>time + hash]
        RANGE[Range-Based<br/>value ranges]
        HIDDEN[Iceberg Hidden<br/>Transform-based]
    end

    subgraph Storage Engines
        HIVE[Hive-Style<br/>col=value/ directories]
        ICE_PART[Iceberg Partitioning<br/>Metadata-driven]
        DELTA_PART[Delta Lake<br/>Partition columns]
    end

    subgraph Optimization
        PRUNE[Partition Pruning<br/>Skip irrelevant data]
        DYNAMIC[Dynamic Partition<br/>Overwrite]
        EVOLVE[Partition Evolution<br/>Change without rewrite]
        ZORDER[Z-Order / Hilbert<br/>Multi-dimensional]
    end

    subgraph Query Patterns
        POINT[Point Lookups<br/>WHERE id = X]
        RANGE_Q[Range Scans<br/>WHERE date BETWEEN]
        FULL[Full Scans<br/>Aggregations]
        MULTI[Multi-dimensional<br/>WHERE col1 AND col2]
    end

    TIME --> TIME_PART
    ENTITY --> HASH_PART
    GEO --> COMPOSITE
    MIXED --> HIDDEN

    TIME_PART --> HIVE
    TIME_PART --> ICE_PART
    HASH_PART --> ICE_PART
    COMPOSITE --> ICE_PART
    HIDDEN --> ICE_PART

    HIVE --> PRUNE
    ICE_PART --> PRUNE
    ICE_PART --> DYNAMIC
    ICE_PART --> EVOLVE
    ICE_PART --> ZORDER

    PRUNE --> POINT
    PRUNE --> RANGE_Q
    ZORDER --> MULTI
    DYNAMIC --> FULL
```

## Problem Statement at Petabyte Scale

Partitioning is the single most impactful performance decision for petabyte-scale data:

- **Wrong partitioning** → queries scan 100% of data instead of 0.1%
- **Over-partitioning** → millions of tiny files, metadata overhead, slow planning
- **Under-partitioning** → partitions too large (100GB+), no pruning benefit
- **Static partitioning** → can't adapt to changing query patterns without full rewrite
- **Multi-tenant** → one partition scheme can't serve all access patterns efficiently

### Impact at Scale

| Dataset Size | Bad Partitioning Cost | Good Partitioning Cost | Savings |
|-------------|----------------------|----------------------|---------|
| 1 PB (Athena) | $5.00/query (full scan) | $0.05/query (1% scan) | 99% |
| 100 TB (Spark) | 2 hours (full shuffle) | 5 min (partition pruning) | 96% |
| 10 PB (S3 listing) | 30 min (millions of prefixes) | 10 sec (metadata) | 99.4% |

## Partitioning Strategy Deep Dive

### 1. Time-Based Partitioning

```python
# Most common for event/log data
# Key decision: granularity (year/month/day/hour)

# Rule of thumb for partition size targets:
# - Athena/Presto: 128MB - 1GB per partition per file
# - Spark: 128MB - 512MB per partition
# - Too small (<1MB): "small files problem"
# - Too large (>10GB): no pruning benefit

# Example: 5TB/day of events
# Daily partitions: 5TB each → too large for most queries
# Hourly partitions: ~210GB each → good for Spark, large for Athena
# Hourly + bucketed: 210GB / 64 buckets = 3.3GB → still large
# Recommended: hourly partition + target 128MB files within

spark.sql("""
    CREATE TABLE events (
        event_id STRING,
        user_id STRING,
        event_type STRING,
        properties MAP<STRING, STRING>,
        event_timestamp TIMESTAMP
    )
    USING iceberg
    PARTITIONED BY (hours(event_timestamp), event_type)
    TBLPROPERTIES (
        'write.target-file-size-bytes' = '134217728',  -- 128MB
        'write.distribution-mode' = 'hash'
    )
""")
```

### 2. Hash-Based Partitioning (Bucketing)

```python
# Best for: high-cardinality join keys, point lookups
# Eliminates shuffle for bucket-aligned joins

spark.sql("""
    CREATE TABLE dim_customer (
        customer_id STRING,
        customer_name STRING,
        segment STRING,
        region STRING
    )
    USING iceberg
    PARTITIONED BY (bucket(256, customer_id))
""")

# Join without shuffle (both tables bucketed on same key, same count)
spark.sql("""
    CREATE TABLE fact_orders (
        order_id STRING,
        customer_id STRING,
        amount DECIMAL(18,2),
        order_date DATE
    )
    USING iceberg
    PARTITIONED BY (days(order_date), bucket(256, customer_id))
""")

# This join is now bucket-to-bucket (no shuffle!)
spark.sql("""
    SELECT c.customer_name, SUM(o.amount)
    FROM fact_orders o
    JOIN dim_customer c ON o.customer_id = c.customer_id
    WHERE o.order_date = '2024-01-15'
    GROUP BY c.customer_name
""")
```

### 3. Composite Partitioning

```python
# Combine time + hash for balanced read/write patterns
# Use case: 10B events/day, queries filter by both time and user

spark.sql("""
    CREATE TABLE user_events (
        event_id STRING,
        user_id STRING,
        event_type STRING,
        payload STRING,
        event_ts TIMESTAMP
    )
    USING iceberg
    PARTITIONED BY (
        days(event_ts),        -- Time-based pruning for range queries
        bucket(64, user_id)    -- Hash-based for user lookups
    )
""")

# Query 1: "All events for user X last week" → prunes to 7 days * 1 bucket = 7 partitions
# Query 2: "All events yesterday" → prunes to 1 day * 64 buckets = 64 partitions
# Query 3: "User X yesterday" → prunes to 1 partition exactly
```

### 4. Iceberg Hidden Partitioning

```python
# Iceberg transforms: users write raw values, engine handles partition mapping
# No partition columns in data! Clean schema.

# Available transforms:
# - years(ts), months(ts), days(ts), hours(ts)
# - bucket(N, col)
# - truncate(L, col)  -- first L characters

spark.sql("""
    CREATE TABLE web_logs (
        request_id STRING,
        url STRING,
        status_code INT,
        response_time_ms INT,
        request_ts TIMESTAMP,
        user_agent STRING
    )
    USING iceberg
    PARTITIONED BY (
        days(request_ts),
        truncate(2, url)  -- First 2 chars of URL path
    )
""")

# Queries naturally prune without knowing partition structure:
# WHERE request_ts > '2024-01-15' → Iceberg prunes at day level
# WHERE url LIKE '/api/%' → Iceberg prunes by truncated prefix
```

### 5. Partition Evolution (Iceberg-only)

```python
# Change partitioning WITHOUT rewriting data!
# Old data keeps old scheme, new data uses new scheme

# Started with monthly partitions (early days, low volume)
spark.sql("""
    ALTER TABLE events 
    SET PARTITION SPEC (months(event_ts))
""")

# Volume grew → switch to daily (no rewrite!)
spark.sql("""
    ALTER TABLE events 
    SET PARTITION SPEC (days(event_ts))
""")

# Added user-based access pattern → add bucketing
spark.sql("""
    ALTER TABLE events 
    SET PARTITION SPEC (days(event_ts), bucket(128, user_id))
""")

# Iceberg handles mixed partition specs transparently
# Old data: monthly partitions (still readable, less pruning)
# New data: daily + bucketed (optimal pruning)
```

## Hive-Style vs Iceberg-Style Partitioning

| Aspect | Hive-Style | Iceberg-Style |
|--------|-----------|---------------|
| **Storage layout** | `col=value/` directories | Any layout, metadata-tracked |
| **Partition discovery** | File system listing (slow at scale) | Manifest files (O(1) lookup) |
| **Schema** | Partition cols in data AND path | Partition derived from data cols |
| **Evolution** | Requires full rewrite | In-place evolution |
| **Hidden partitions** | No (user must know scheme) | Yes (transparent pruning) |
| **Planning time (1M partitions)** | 10+ minutes | <1 second |
| **Dynamic overwrite** | Unreliable (race conditions) | ACID guaranteed |
| **Predicate pushdown** | String-based path matching | Stats-based (min/max/count) |

### Planning Performance Comparison

```
Dataset: 3 years of hourly data = 26,280 partitions

Hive (file listing):
├── LIST s3://bucket/table/ → 26,280 prefixes
├── For each: LIST files → 26,280 API calls
├── Total: ~52,000 S3 API calls
└── Time: 3-5 minutes just for planning

Iceberg (manifest scan):
├── Read metadata.json → 1 file
├── Read manifest-list → 1 file
├── Read relevant manifests → 10-20 files
├── Total: ~25 S3 API calls
└── Time: <2 seconds
```

## Dynamic Partition Overwrite

```python
# Problem: Reprocessing one day shouldn't affect other days
# Hive behavior: INSERT OVERWRITE can delete unintended partitions

# Iceberg: Overwrite only partitions present in the DataFrame
df_jan15 = spark.read.parquet("s3://reprocessed/2024-01-15/")

# Only overwrites partition for 2024-01-15, leaves others untouched
df_jan15.writeTo("catalog.db.events") \
    .overwritePartitions()

# Spark dynamic partition overwrite (for Hive-style tables)
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
df_jan15.write \
    .format("parquet") \
    .mode("overwrite") \
    .partitionBy("event_date") \
    .save("s3://lake/events/")  # Only overwrites event_date=2024-01-15
```

## Partition Pruning Deep Dive

```python
# Partition pruning eliminates reading irrelevant partitions
# Critical for query performance at petabyte scale

# Example: 1 PB table, 365 daily partitions
# Query: WHERE event_date = '2024-01-15'
# Without pruning: scan 1 PB → $5,000 on Athena
# With pruning: scan 2.7 TB (1/365) → $13.70 on Athena

# Pruning requirements:
# 1. Filter must reference partition column directly
# 2. Expression must be evaluable at planning time (no UDFs)
# 3. For Iceberg: predicate must be pushable to manifest scan

# GOOD (pruning works):
spark.sql("SELECT * FROM events WHERE event_date = '2024-01-15'")
spark.sql("SELECT * FROM events WHERE event_date BETWEEN '2024-01-01' AND '2024-01-31'")
spark.sql("SELECT * FROM events WHERE year(event_ts) = 2024 AND month(event_ts) = 1")

# BAD (pruning fails - full scan):
spark.sql("SELECT * FROM events WHERE date_format(event_ts, 'yyyy-MM-dd') = '2024-01-15'")
spark.sql("SELECT * FROM events WHERE event_date = (SELECT max(event_date) FROM events)")
spark.sql("SELECT * FROM events WHERE custom_udf(event_ts) = 'Jan'")

# Verify pruning with EXPLAIN
spark.sql("EXPLAIN EXTENDED SELECT * FROM events WHERE event_date = '2024-01-15'").show(truncate=False)
# Look for: "PartitionFilters: [event_date = 2024-01-15]"
# NOT: "PushedFilters" (that's predicate pushdown within partition, different thing)
```

## Partition Size Guidelines

```python
# Optimal partition sizing formulas

def calculate_optimal_partitions(
    daily_data_size_gb: float,
    target_file_size_mb: int = 128,
    files_per_partition: int = 4,
    query_engine: str = "spark"
) -> dict:
    """
    Calculate optimal partition count and granularity.
    """
    target_partition_size_mb = target_file_size_mb * files_per_partition  # 512MB
    
    partitions_needed = (daily_data_size_gb * 1024) / target_partition_size_mb
    
    # Recommendations
    recommendations = {}
    
    if daily_data_size_gb < 1:
        recommendations["time_granularity"] = "daily"
        recommendations["additional_partitioning"] = "none"
    elif daily_data_size_gb < 50:
        recommendations["time_granularity"] = "daily"
        recommendations["additional_partitioning"] = "bucket(16, key)"
    elif daily_data_size_gb < 500:
        recommendations["time_granularity"] = "hourly"
        recommendations["additional_partitioning"] = "bucket(64, key)"
    else:  # 500GB+ per day
        recommendations["time_granularity"] = "hourly"
        recommendations["additional_partitioning"] = "bucket(256, key)"
    
    recommendations["estimated_partitions_per_day"] = int(partitions_needed)
    recommendations["target_files_per_partition"] = files_per_partition
    recommendations["target_file_size_mb"] = target_file_size_mb
    
    return recommendations

# Examples:
# 5 TB/day → hourly + bucket(256) = 24 * 256 = 6,144 partitions/day, ~830MB each
# 100 GB/day → daily + bucket(16) = 16 partitions/day, ~6.4GB each → maybe hourly better
# 10 GB/day → daily, no bucketing = 1 partition/day, target 128MB files (78 files)
```

## Anti-Patterns

### 1. Over-Partitioning

```python
# BAD: Partitioning by high-cardinality column
# 100M users → 100M directories → S3 listing takes hours
df.write.partitionBy("user_id").parquet("s3://bad-idea/")

# GOOD: Bucket instead
# 256 buckets, evenly distributed
spark.sql("""
    CREATE TABLE good_idea USING iceberg
    PARTITIONED BY (bucket(256, user_id))
""")
```

### 2. Partition Column in Predicates but Wrong Type

```python
# BAD: Partition column is STRING but compared as DATE
# Spark can't prune because it can't evaluate the cast at planning time
spark.sql("""
    SELECT * FROM events 
    WHERE CAST(event_date_str AS DATE) = '2024-01-15'
""")

# GOOD: Partition column matches predicate type
spark.sql("""
    SELECT * FROM events 
    WHERE event_date = DATE '2024-01-15'
""")
```

### 3. Calendar Partitioning Misalignment

```python
# BAD: Daily partitions but queries always filter by week
# Every query touches 7 partitions minimum

# GOOD: If business queries are weekly, partition by ISO week
spark.sql("""
    CREATE TABLE weekly_metrics USING iceberg
    PARTITIONED BY (truncate(1, iso_week))  -- e.g., '2024-W03'
""")
```

## Scaling Strategies

### 1. Partition Coalescing for Small Files

```python
# After streaming writes create many small files per partition
# Coalesce to target file size

spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        strategy => 'binpack',
        options => map(
            'target-file-size-bytes', '134217728',  -- 128MB
            'min-file-size-bytes', '67108864',       -- 64MB (don't rewrite if close enough)
            'max-file-size-bytes', '201326592',      -- 192MB
            'min-input-files', '5'                   -- Only compact if 5+ small files
        ),
        where => 'event_date >= current_date() - interval 1 day'
    )
""")
```

### 2. Sort Within Partitions

```python
# Sort within partitions for better compression and predicate pushdown
# Parquet row groups with sorted data have tight min/max stats

spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        strategy => 'sort',
        sort_order => 'event_type ASC, user_id ASC'
    )
""")

# Result: Queries filtering on event_type skip entire row groups
# Compression improves 20-40% due to data locality
```

### 3. Adaptive Partition Granularity

```python
# Different tables need different strategies based on their growth

def auto_tune_partitioning(spark, table_name):
    """Analyze table and recommend partition changes."""
    
    # Get partition stats
    stats = spark.sql(f"""
        SELECT 
            partition,
            COUNT(*) as file_count,
            SUM(file_size_in_bytes) as partition_size_bytes,
            AVG(file_size_in_bytes) as avg_file_size
        FROM {table_name}.files
        GROUP BY partition
    """)
    
    avg_partition_size = stats.agg(F.avg("partition_size_bytes")).collect()[0][0]
    avg_file_count = stats.agg(F.avg("file_count")).collect()[0][0]
    
    if avg_partition_size > 10 * 1024**3:  # >10GB per partition
        return "SPLIT: Add sub-partitioning (bucket or finer time granularity)"
    elif avg_partition_size < 10 * 1024**2:  # <10MB per partition
        return "MERGE: Reduce partition granularity or remove a partition level"
    elif avg_file_count > 100:
        return "COMPACT: Too many small files, run compaction"
    else:
        return "OPTIMAL: Current partitioning is well-balanced"
```

## Failure Handling

### Partition Corruption Recovery

```python
# Iceberg: rollback corrupted partition to previous snapshot
spark.sql("""
    CALL catalog.system.rollback_to_snapshot('db.events', 12345678)
""")

# Rewrite specific partitions
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        where => "event_date = '2024-01-15'"
    )
""")
```

### Handling Partition Skew

```python
# Problem: One partition has 100x more data than others (hot key)
# Solution: Salt the hot partition

def handle_partition_skew(df, partition_col, hot_values, num_salts=10):
    """Add salt to hot partition values to spread load."""
    
    is_hot = F.col(partition_col).isin(hot_values)
    
    return df.withColumn(
        "_salted_partition",
        F.when(is_hot, 
               F.concat(F.col(partition_col), F.lit("_"), 
                       (F.rand() * num_salts).cast("int").cast("string")))
        .otherwise(F.col(partition_col))
    )
```

## Cost Optimization

### Query Cost by Partition Strategy (1 PB table, Athena)

| Strategy | Typical Query Scan | Cost/Query | Annual (1000 queries/day) |
|----------|-------------------|-----------|--------------------------|
| No partitioning | 1 PB | $5,000 | $1.8B (impossible) |
| Year partition | 333 TB | $1,665 | $608M (still bad) |
| Month partition | 28 TB | $140 | $51M |
| Day partition | 2.7 TB | $13.50 | $4.9M |
| Day + bucket(64) | 43 GB | $0.21 | $77K |
| Day + bucket(64) + Z-order | 5 GB | $0.025 | $9K |

### Storage Cost Optimization

```python
# Partition-aware lifecycle policies
lifecycle_rules:
  - prefix: "events/event_date=2023"  # Old year
    transitions:
      - days: 0
        storage_class: GLACIER_IR
    
  - prefix: "events/event_date=2024-01"  # Older months
    transitions:
      - days: 90
        storage_class: STANDARD_IA
```

## Real-World Companies

| Company | Dataset | Strategy |
|---------|---------|----------|
| **Netflix** | 100PB+ viewing data | Iceberg hidden partitioning (time + bucket) |
| **Uber** | Trips (10B records) | Hudi + composite (city + day) |
| **LinkedIn** | Activity feed (1PB/day) | Iceberg bucket(512, member_id) + days(ts) |
| **Apple** | iCloud analytics | Iceberg partition evolution (monthly→daily) |
| **Databricks** | Internal telemetry | Delta Lake + Z-order on multiple columns |
| **Stripe** | Payment events | Day partition + bucket(128, merchant_id) |

## Key Design Decisions

1. **Partition column count**: Maximum 2-3 partition dimensions. More creates too many small partitions.

2. **Bucket count**: Choose power of 2 (64, 128, 256). Must be same across tables for shuffle-free joins. Changing bucket count requires full rewrite.

3. **Time granularity**: Match your most common query filter granularity. Daily for business queries, hourly for operational monitoring.

4. **Iceberg vs Hive-style**: Always Iceberg for new tables. Hive-style only for legacy compatibility.

5. **Sort order within partitions**: Sort by most selective filter column first. This gives Parquet min/max stats maximum pruning power.
