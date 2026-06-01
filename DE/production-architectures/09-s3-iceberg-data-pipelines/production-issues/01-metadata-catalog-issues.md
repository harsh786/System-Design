# Metadata & Catalog Issues (#1-15)

Issues related to Iceberg metadata management, catalog operations, and metadata file growth
that cause production outages at scale.

---

## Issue #1: Metadata File Explosion (Thousands of metadata.json files)

**Severity:** P1 - High
**Frequency:** Weekly at tables with >100 commits/day
**Affected Components:** Query planning, catalog operations, S3 costs
**First seen at:** Netflix (10K+ commits/day on hot tables)

### Symptoms
```
- Query planning takes 30+ seconds (was 2 seconds)
- S3 LIST requests spike on metadata/ prefix
- AWS bill shows unexpected S3 GET/LIST costs
- `ls s3://bucket/db/table/metadata/` returns 50,000+ files
- Spark jobs fail with: "java.lang.OutOfMemoryError: GC overhead limit exceeded"
  during table scan initialization
```

### Root Cause
```
Every Iceberg commit creates a NEW metadata.json file:
  v1.metadata.json → v2.metadata.json → ... → v50000.metadata.json

Each metadata.json contains the FULL snapshot list (all historical snapshots).
At 50K versions:
  - Each metadata file is 50MB+ (contains all snapshot references)
  - S3 stores 50K × 50MB = 2.5TB of metadata alone
  - Latest metadata.json must be fully parsed to plan any query

Root: No automatic metadata cleanup + high commit frequency (streaming)
```

### Impact
```
- Query latency: 2s → 45s (22x degradation)
- Planning OOM for tables with 100K+ snapshots in metadata
- S3 costs: $500/month just for metadata GETs on one table
- Catalog pointer update becomes slow (large JSON to write)
```

### Immediate Fix
```sql
-- Expire old snapshots (keeps only recent ones in metadata)
CALL system.expire_snapshots(
  table => 'production.db.hot_table',
  older_than => TIMESTAMP '2024-01-01 00:00:00',
  retain_last => 100,
  max_concurrent_deletes => 50
);

-- Remove old metadata files
CALL system.remove_orphan_files(
  table => 'production.db.hot_table',
  older_than => TIMESTAMP '2024-01-01 00:00:00',
  location => 's3://bucket/db/hot_table/metadata'
);
```

### Permanent Fix
```properties
# Table properties to auto-manage metadata
write.metadata.delete-after-commit.enabled = true
write.metadata.previous-versions-max = 50

# Limit snapshot retention
history.expire.max-snapshot-age-ms = 259200000   # 3 days
history.expire.min-snapshots-to-keep = 10
```

```python
# Automated maintenance job (runs every 6 hours)
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.catalog.prod", "org.apache.iceberg.spark.SparkCatalog") \
    .getOrCreate()

# Expire snapshots older than 3 days, keep minimum 5
spark.sql("""
    CALL prod.system.expire_snapshots(
        table => 'db.hot_table',
        older_than => current_timestamp() - INTERVAL 3 DAYS,
        retain_last => 5
    )
""")
```

### Prevention
```
1. ALWAYS set write.metadata.delete-after-commit.enabled=true on creation
2. Set history.expire.max-snapshot-age-ms based on workload
3. Schedule expire_snapshots as Airflow DAG (every 6 hours for hot tables)
4. Monitor metadata file count with Prometheus alert
5. For streaming tables: lower commit interval (fewer commits = fewer metadata files)
```

### Monitoring
```yaml
# Prometheus alert
- alert: IcebergMetadataExplosion
  expr: iceberg_table_metadata_file_count > 1000
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Table {{ $labels.table }} has {{ $value }} metadata files"
    runbook: "Run expire_snapshots and enable auto-cleanup"
```

---

## Issue #2: Catalog Pointer Corruption (Table becomes unreadable)

**Severity:** P0 - Critical
**Frequency:** Rare but catastrophic (1-2x per year at scale)
**Affected Components:** All reads/writes to affected table
**First seen at:** Large bank (Glue catalog concurrent update race)

### Symptoms
```
- All queries fail: "Table metadata file not found: s3://bucket/.../v999.metadata.json"
- Catalog shows table exists but points to non-existent metadata
- Cannot write to table: "Failed to load table metadata"
- Glue GetTable API returns stale/invalid location
```

### Root Cause
```
Race condition in catalog pointer update:

  Writer A: reads v5.metadata.json
  Writer B: reads v5.metadata.json
  Writer A: writes v6.metadata.json, updates catalog → v6
  Writer B: writes v6.metadata.json (OVERWRITES A's file!), updates catalog → v6
  
  Now v6.metadata.json has B's content, A's commit is LOST.
  
  OR: Catalog update succeeds but metadata file write to S3 fails
  (network issue) → catalog points to non-existent file.

  OR: S3 eventual consistency (rare with strong consistency, but 
  possible during region failover) → catalog reads stale location.
```

### Impact
```
- COMPLETE TABLE OUTAGE - no reads or writes possible
- Data loss if recent commits cannot be recovered
- Downstream pipelines fail (cascade failure)
- SLA breach for dependent services
```

### Immediate Fix
```python
# Step 1: Find the last valid metadata file
import boto3
s3 = boto3.client('s3')

# List all metadata files, find the latest valid one
response = s3.list_objects_v2(
    Bucket='my-bucket',
    Prefix='db/table/metadata/',
    Delimiter=''
)

metadata_files = sorted(
    [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.metadata.json')],
    key=lambda x: int(x.split('/')[-1].split('.')[0].replace('v', ''))
)

# Find latest readable metadata
for mf in reversed(metadata_files):
    try:
        obj = s3.get_object(Bucket='my-bucket', Key=mf)
        content = obj['Body'].read()
        import json
        metadata = json.loads(content)
        print(f"Last valid metadata: {mf}")
        print(f"  Snapshots: {len(metadata.get('snapshots', []))}")
        break
    except Exception as e:
        print(f"  Corrupt/missing: {mf} - {e}")

# Step 2: Update catalog to point to valid metadata
# For Glue:
glue = boto3.client('glue')
glue.update_table(
    DatabaseName='db',
    TableInput={
        'Name': 'table',
        'Parameters': {
            'metadata_location': f's3://my-bucket/{mf}'
        }
    }
)
```

### Permanent Fix
```
1. Use catalog-level locking (DynamoDB lock for Glue, DB lock for HMS)
2. Enable optimistic concurrency with retries:
   commit.retry.num-retries = 10
   commit.retry.min-wait-ms = 100
   commit.retry.max-wait-ms = 60000
3. Use Nessie catalog (has built-in conflict detection via Git model)
4. Implement metadata backup (copy every N-th metadata file to backup bucket)
```

### Prevention
```
- Use DynamoDB lock table with Glue catalog (prevents concurrent pointer updates)
- Configure proper retry settings on all writers
- Never run multiple Spark jobs writing to same table without coordination
- Implement pre-write health check (verify current metadata is readable)
- Daily metadata integrity verification job
```

### Monitoring
```yaml
- alert: IcebergCatalogPointerInvalid
  expr: iceberg_table_metadata_load_errors > 0
  for: 1m
  labels:
    severity: critical
    pager: "true"
  annotations:
    summary: "CRITICAL: Table {{ $labels.table }} metadata unreachable"
    runbook: "Follow catalog recovery runbook immediately"
```

---

## Issue #3: Snapshot List Grows Unbounded (OOM on Table Load)

**Severity:** P1 - High
**Frequency:** Monthly for tables without maintenance
**Affected Components:** Any operation that loads table metadata
**First seen at:** LinkedIn (tables with 500K+ snapshots)

### Symptoms
```
- Spark driver OOM when loading table: "java.lang.OutOfMemoryError: Java heap space"
- Query planning takes 5+ minutes
- DESCRIBE TABLE hangs indefinitely
- metadata.json file is 500MB+
- Athena query fails: "HIVE_METASTORE_ERROR: Failed to get table metadata"
```

### Root Cause
```
metadata.json structure:
{
  "snapshots": [
    {"snapshot-id": 1, "manifest-list": "...", ...},
    {"snapshot-id": 2, "manifest-list": "...", ...},
    ... // 500,000 entries × ~500 bytes each = 250MB JSON
  ],
  "snapshot-log": [...],  // Another 500K entries
  "metadata-log": [...]   // All metadata versions
}

Entire JSON must be parsed to load table → 250MB+ in memory just for metadata.
With JVM overhead: 250MB JSON → 1-2GB heap usage.
Default Spark driver: 1-4GB → OOM.
```

### Immediate Fix
```bash
# Increase driver memory temporarily
spark-submit \
  --driver-memory 16g \
  --conf spark.sql.catalog.prod=org.apache.iceberg.spark.SparkCatalog \
  maintenance_job.py

# Then expire snapshots aggressively
```

```python
# Emergency snapshot expiry (run with high memory)
spark.sql("""
    CALL prod.system.expire_snapshots(
        table => 'db.problem_table',
        older_than => current_timestamp() - INTERVAL 1 DAY,
        retain_last => 5,
        max_concurrent_deletes => 100
    )
""")
```

### Permanent Fix
```python
# Automated governance: enforce snapshot limits
SNAPSHOT_POLICIES = {
    'streaming_tables': {'max_age_hours': 24, 'min_keep': 5},
    'batch_daily': {'max_age_hours': 168, 'min_keep': 7},
    'audit_tables': {'max_age_hours': 8760, 'min_keep': 365},
}

def enforce_snapshot_policy(table_name, policy):
    spark.sql(f"""
        CALL prod.system.expire_snapshots(
            table => '{table_name}',
            older_than => current_timestamp() - INTERVAL {policy['max_age_hours']} HOURS,
            retain_last => {policy['min_keep']}
        )
    """)
```

### Prevention
```
1. Tag tables with retention policy at creation time
2. Automated maintenance runs every 6 hours for streaming tables
3. Set write.metadata.previous-versions-max = 50
4. Monitor snapshot count with hard alerting threshold
5. Gate new table creation: must include retention properties
```

---

## Issue #4: Glue Catalog Throttling (API Rate Limits)

**Severity:** P1 - High
**Frequency:** Daily during peak hours at 1000+ table deployments
**Affected Components:** All Iceberg operations (read/write/maintenance)
**First seen at:** Large fintech (5000+ Iceberg tables, 200+ concurrent jobs)

### Symptoms
```
- Intermittent failures: "Rate exceeded" from Glue API
- Spark jobs randomly fail during table loading
- Athena queries timeout with "HIVE_METASTORE_ERROR"
- Error: "com.amazonaws.services.glue.model.ThrottlingException"
- Burst of failures at top of hour (all cron jobs start simultaneously)
```

### Root Cause
```
AWS Glue Data Catalog API limits:
  - GetTable: 100 requests/second/account (shared across ALL services)
  - UpdateTable: 25 requests/second/account
  - GetPartitions: 50 requests/second/account

At scale:
  - 200 Spark jobs × 5 tables each = 1000 GetTable calls at startup
  - Each Iceberg commit = 1 GetTable + 1 UpdateTable
  - Streaming jobs commit every 60s × 100 tables = 100 UpdateTable/min
  - Query planning: GetTable → parse metadata → GetTable again for lock check
  
  Total: easily 500+ requests/second during peak → THROTTLED
```

### Immediate Fix
```python
# Add exponential backoff to catalog operations
spark.conf.set("spark.sql.catalog.prod.client.retry.max-retries", "10")
spark.conf.set("spark.sql.catalog.prod.client.retry.initial-backoff-ms", "200")
spark.conf.set("spark.sql.catalog.prod.client.retry.max-backoff-ms", "30000")

# Stagger job start times (jitter)
import random, time
time.sleep(random.uniform(0, 300))  # Random delay 0-5 minutes
```

### Permanent Fix
```
1. Use caching catalog wrapper:
   - Cache GetTable results for 30 seconds
   - Reduces calls by 80%+

2. Request Glue API limit increase from AWS Support

3. Separate accounts for different environments:
   - prod-streaming account (high write rate)
   - prod-batch account (high read rate)
   - analytics account (ad-hoc queries)

4. Consider Nessie or REST Catalog (no AWS rate limits)

5. Implement catalog connection pooling with rate limiting:
```

```python
from ratelimit import limits, sleep_and_retry

class RateLimitedGlueCatalog:
    @sleep_and_retry
    @limits(calls=80, period=1)  # Stay under 100/s limit
    def get_table(self, database, table):
        return self.glue_client.get_table(
            DatabaseName=database,
            Name=table
        )
```

### Prevention
```
- Implement catalog-level caching layer (Redis/ElastiCache)
- Spread job schedules with jitter (don't use @hourly for everything)
- Use Iceberg's metadata caching: spark.sql.catalog.prod.cache-enabled=true
- Monitor Glue API usage with CloudWatch ServiceQuotas dashboard
- Design for multi-account catalog isolation
```

---

## Issue #5: Manifest List Explosion (100K+ Manifests)

**Severity:** P1 - High
**Frequency:** Monthly for tables with frequent small commits
**Affected Components:** Query planning time, metadata reads
**First seen at:** Apple (tables with millions of daily appends)

### Symptoms
```
- Query planning: 2 minutes+ (should be <5 seconds)
- Spark shows "Planning query..." for ages before execution starts
- Large number of S3 GET requests during planning phase
- "Reading manifest files" stage takes 90% of total query time
- Trino coordinator OOM during planning
```

### Root Cause
```
Every commit adds new manifest files. Without rewrite:

  Commit 1: manifest-001.avro (tracks 5 data files)
  Commit 2: manifest-002.avro (tracks 3 data files)
  ...
  Commit 100000: manifest-100000.avro (tracks 2 data files)

  Query planning must READ ALL 100K manifests to determine which data files match.
  
  100K manifests × 10KB each = 1GB of manifest data to read
  100K S3 GET requests for manifests alone (at $0.0004/1000 = $0.04/query)
  Sequential reads: 100K × 50ms = 5000 seconds (clearly parallelized, but still slow)
```

### Immediate Fix
```sql
-- Rewrite manifests to merge small ones
CALL prod.system.rewrite_manifests('db.table');

-- With options for better grouping
CALL prod.system.rewrite_manifests(
  table => 'db.table',
  use_caching => true
);
```

### Permanent Fix
```python
# Automated manifest rewrite when count exceeds threshold
def check_and_rewrite_manifests(table_name, threshold=500):
    table = spark.catalog.loadTable(table_name)
    manifest_count = len(list(table.currentSnapshot().allManifests()))
    
    if manifest_count > threshold:
        spark.sql(f"CALL prod.system.rewrite_manifests('{table_name}')")
        logger.info(f"Rewrote {manifest_count} manifests for {table_name}")
```

```properties
# Table properties to limit manifest growth
commit.manifest.target-size-bytes = 8388608  # 8MB manifests
commit.manifest-merge.enabled = true
commit.manifest.min-count-to-merge = 100
```

### Prevention
```
1. Enable manifest merging on commit (commit.manifest-merge.enabled=true)
2. Schedule rewrite_manifests weekly for batch tables, daily for streaming
3. Increase commit interval for streaming (fewer commits = fewer manifests)
4. Monitor manifest count per table
5. Set target manifest size to 8MB (holds ~1000 data file entries)
```

---

## Issue #6: Orphan Metadata Files Consuming Storage

**Severity:** P2 - Medium
**Frequency:** Ongoing (grows over time)
**Affected Components:** S3 storage costs, confusion during debugging
**First seen at:** Common across all large deployments

### Symptoms
```
- S3 storage costs growing faster than data growth
- metadata/ directory has 100K+ files but table only has 50 snapshots
- Manifest files exist on S3 but aren't referenced by any snapshot
- Storage audit shows 40% of table storage is unreferenced files
- After expire_snapshots, storage doesn't decrease as expected
```

### Root Cause
```
Orphan files are created by:

1. Failed commits: Writer creates data/manifest files → commit fails → files remain
2. expire_snapshots: Removes snapshot references but NOT the manifest/data files
   (by design - expire is metadata-only, fast operation)
3. Compaction: Creates new files, old files dereferenced but not deleted
4. Aborted Spark stages: Speculative execution creates duplicate output files
5. Manual table drops without cleanup

Lifecycle:
  expire_snapshots → removes snapshot metadata (fast, safe)
  remove_orphan_files → actually deletes unreferenced S3 objects (slow, dangerous)
  
  Many teams run expire_snapshots but forget remove_orphan_files!
```

### Immediate Fix
```sql
-- Find and remove orphan files (CAREFUL: use dry_run first!)
-- Only remove files older than 3 days (safety margin for in-progress commits)
CALL prod.system.remove_orphan_files(
  table => 'db.table',
  older_than => TIMESTAMP '2024-06-01 00:00:00',
  dry_run => true  -- ALWAYS dry_run first!
);

-- If dry_run output looks safe, run for real:
CALL prod.system.remove_orphan_files(
  table => 'db.table',
  older_than => current_timestamp() - INTERVAL 3 DAYS
);
```

### Permanent Fix
```python
# Scheduled orphan cleanup (weekly, off-peak hours)
# IMPORTANT: older_than must be > max possible commit duration
SAFETY_MARGIN_DAYS = 3

def safe_orphan_cleanup(table_name):
    cutoff = datetime.now() - timedelta(days=SAFETY_MARGIN_DAYS)
    
    # Step 1: Expire snapshots first
    spark.sql(f"""
        CALL prod.system.expire_snapshots(
            table => '{table_name}',
            older_than => TIMESTAMP '{cutoff.isoformat()}',
            retain_last => 5
        )
    """)
    
    # Step 2: Remove orphan files (only files older than safety margin)
    spark.sql(f"""
        CALL prod.system.remove_orphan_files(
            table => '{table_name}',
            older_than => TIMESTAMP '{cutoff.isoformat()}'
        )
    """)
```

### Prevention
```
- ALWAYS pair expire_snapshots with remove_orphan_files (schedule together)
- Use safety margin of 3+ days for older_than (protects in-progress commits)
- Enable write.metadata.delete-after-commit.enabled=true (auto-deletes old metadata)
- Track orphan file count as a metric
- Budget for weekly cleanup windows
```

---

## Issue #7: Partition Metadata Explosion (10M+ Partition Specs)

**Severity:** P1 - High
**Frequency:** When partition cardinality is too high
**Affected Components:** Query planning, manifest scanning
**First seen at:** E-commerce (partitioned by user_id with 500M users)

### Symptoms
```
- SHOW PARTITIONS returns millions of entries (hangs)
- Query planning reads all partition metadata even for single-partition query
- Manifest files are huge (100MB+) because each tracks high-cardinality partitions
- S3 costs dominated by manifest reads
- "Partition stats" in manifest list is enormous
```

### Root Cause
```
Bad partitioning choice: identity(user_id) with 500M distinct users

Result:
  - 500M partition values tracked in manifests
  - Each manifest list entry stores min/max partition bounds
  - Partition summary in manifest list: 500M entries × 50 bytes = 25GB
  - Cannot effectively prune: most queries need multiple user_ids

Another cause: day-level partitioning on 10-year historical table
  = 3,650 partitions (manageable, but combined with other dimensions...)
  
  Partition by (day, region, product_type) = 3,650 × 50 × 200 = 36.5M partitions
```

### Immediate Fix
```sql
-- Evolve partition to lower cardinality
ALTER TABLE db.events 
SET PARTITION SPEC (
  bucket(256, user_id),   -- 256 buckets instead of 500M partitions
  days(event_timestamp)
);

-- Note: Old data keeps old partition spec, only new data uses new spec
-- To fix old data, must rewrite:
CALL prod.system.rewrite_data_files(
  table => 'db.events',
  strategy => 'sort',
  sort_order => 'bucket(256, user_id), event_timestamp'
);
```

### Permanent Fix
```
Partitioning rules of thumb:
  - identity(): ONLY for low-cardinality columns (< 10K distinct values)
  - bucket(N, col): For high-cardinality (users, IDs). N = 64-1024
  - days/hours(): For time-series data
  - NEVER: identity() on unbounded columns (user_id, order_id, etc.)

Ideal partition count per table: 100 - 10,000
Target files per partition: 10 - 1,000
```

### Prevention
```
- Code review all CREATE TABLE statements for partition spec
- Lint rule: reject identity() on columns with >100K distinct values
- Default to bucket() for entity IDs
- Document partitioning decision framework for team
- Monitor partition count growth rate
```

---

## Issue #8: Stale Catalog Cache Causing Reads of Old Data

**Severity:** P1 - High
**Frequency:** After enabling caching (common optimization)
**Affected Components:** Query correctness (SILENT DATA ISSUES)
**First seen at:** Data teams that added caching for performance

### Symptoms
```
- Queries return stale data (data written 5 min ago not visible)
- Dashboard shows yesterday's numbers despite pipeline completing
- Trino and Athena return different results for same query
- After table update, some queries see old data, others see new
- No errors - just wrong results (MOST DANGEROUS type of issue)
```

### Root Cause
```
Caching layers that serve stale metadata:

1. Spark catalog cache (default: caches table metadata indefinitely per session)
   spark.sql.catalog.prod.cache-enabled = true (default!)
   
2. Trino metadata cache (default: 5 minutes)
   iceberg.metadata.cache-ttl = 5m
   
3. Hive Metastore cache (HMS caches GetTable results)

4. Application-level caching (Redis caching catalog lookups)

5. S3 eventual consistency SOLVED in 2020, but CDN/proxy caches still exist

Flow:
  Writer commits snapshot v10 → Updates catalog → Done
  Reader (with cached catalog) → Still sees snapshot v8 → Returns OLD data
  Reader doesn't know v10 exists because catalog lookup is cached!
```

### Immediate Fix
```sql
-- Force Spark to refresh cached metadata
REFRESH TABLE db.table;

-- Trino: invalidate metadata cache
CALL system.flush_metadata_cache();

-- For critical queries: disable cache per-query
SET spark.sql.catalog.prod.cache-enabled = false;
SELECT * FROM db.table WHERE ...;
SET spark.sql.catalog.prod.cache-enabled = true;
```

### Permanent Fix
```properties
# Spark: set reasonable cache TTL (not unlimited)
spark.sql.catalog.prod.cache-enabled = true
spark.sql.catalog.prod.cache.expiration-interval-ms = 30000  # 30 seconds

# Trino: lower metadata cache for frequently updated tables
iceberg.metadata.cache-ttl = 30s

# For real-time serving: no cache
spark.sql.catalog.prod.cache-enabled = false
```

### Prevention
```
- DOCUMENT cache behavior for all query engines in your stack
- Use explicit REFRESH TABLE in pipelines that read after write
- For streaming consumers: disable metadata cache entirely
- Test with writes + immediate reads in integration tests
- Monitor "data freshness" metric (time between commit and query visibility)
```

---

## Issue #9: Table Schema ID Collision After Table Recreation

**Severity:** P0 - Critical
**Frequency:** After DROP + CREATE TABLE with same name
**Affected Components:** All queries return wrong data / corrupt results
**First seen at:** Teams that "recreate" tables to fix schema issues

### Symptoms
```
- After table recreation, queries return garbage data
- Column values appear in wrong columns
- Type errors: "Cannot cast BINARY to INT"
- Data files from old table being read with new schema
- Parquet files show different column ordering than expected
```

### Root Cause
```
Dangerous pattern:
  1. DROP TABLE db.transactions  (catalog pointer removed)
  2. CREATE TABLE db.transactions (new schema, new column IDs)
  
  But: Old data files still exist on S3!
  If new table uses same S3 location, old files get picked up
  with WRONG schema mapping (new column IDs don't match old file column IDs)

  Column ID mapping:
  Old table: {1: user_id (string), 2: amount (decimal), 3: status (string)}
  New table: {1: txn_id (string), 2: user_id (string), 3: amount (decimal)}
  
  Reading old file with new schema:
  → Column 1 (user_id data) mapped to txn_id → WRONG
  → Column 2 (amount data) mapped to user_id → TYPE ERROR
```

### Immediate Fix
```sql
-- NEVER reuse the same S3 location after DROP TABLE
-- Instead, use a new location:
CREATE TABLE db.transactions_v2 (...)
LOCATION 's3://bucket/db/transactions_v2/'  -- NEW location

-- Or: properly clean up old files before recreation:
-- Step 1: Note the old location
DESCRIBE EXTENDED db.transactions;  -- Get location

-- Step 2: Drop table
DROP TABLE db.transactions;

-- Step 3: Delete ALL files at old location
-- aws s3 rm s3://bucket/db/transactions/ --recursive

-- Step 4: Recreate
CREATE TABLE db.transactions (...) LOCATION 's3://bucket/db/transactions/';
```

### Permanent Fix
```
1. NEVER DROP + CREATE to fix schema issues. Use ALTER TABLE instead:
   ALTER TABLE db.transactions ADD COLUMN new_col STRING;
   ALTER TABLE db.transactions RENAME COLUMN old_name TO new_name;
   ALTER TABLE db.transactions ALTER COLUMN amount TYPE DECIMAL(18,4);

2. If must recreate: use unique location per table version
   Location pattern: s3://bucket/db/{table_name}/{uuid}/

3. Implement table lifecycle policy: 
   DROP TABLE → async cleanup job deletes S3 files after 7 days
```

### Prevention
```
- Block DROP TABLE in production (require approval process)
- Use schema evolution (ALTER TABLE) instead of recreation
- If drop needed: use PURGE option to delete files
  DROP TABLE db.transactions PURGE;
- Automated check: verify no orphan data files exist at location before CREATE
```

---

## Issue #10: Hive Metastore (HMS) Lock Contention

**Severity:** P1 - High
**Frequency:** Daily at high-concurrency deployments using HMS
**Affected Components:** All commits blocked, pipeline delays
**First seen at:** On-prem deployments with HMS + MySQL backend

### Symptoms
```
- Commits hang for 30+ seconds (normally <1s)
- Multiple Spark jobs waiting on "Acquiring lock for table"
- HMS backend DB shows many transactions in LOCK WAIT state
- Deadlock detected errors in HMS logs
- Commit timeout: "Failed to commit: lock wait timeout exceeded"
```

### Root Cause
```
HMS uses database-level locking for Iceberg commit:

  1. Writer acquires exclusive lock on table entry (MySQL row lock)
  2. Writer reads current metadata location
  3. Writer writes new metadata file
  4. Writer updates table entry with new metadata location
  5. Writer releases lock

  With 50 concurrent writers to same table:
  - 49 writers wait for lock (serialized commits)
  - MySQL lock timeout default: 50 seconds
  - If commit takes >50s → timeout → retry → more contention
  - Lock wait queue grows exponentially under load

  HMS MySQL backend limitations:
  - Single-row lock on table record
  - No optimistic concurrency (pessimistic locking)
  - Transaction isolation: SERIALIZABLE (highest overhead)
```

### Immediate Fix
```sql
-- Increase lock timeout (temporary relief)
SET innodb_lock_wait_timeout = 120;  -- MySQL

-- Reduce concurrent writers to same table
-- Route writes through single coordinator
```

### Permanent Fix
```
1. Migrate to Nessie catalog (optimistic concurrency, no locks)
2. Migrate to AWS Glue (uses DynamoDB, no row-level locking)
3. If must use HMS: upgrade to PostgreSQL backend (better concurrency)
4. Implement write coordinator pattern:
   - Single Spark job owns writes to hot table
   - Other jobs write to staging → coordinator merges
5. Tune HMS database:
   - Connection pool size: 100+
   - innodb_lock_wait_timeout: 120s
   - Read replicas for metadata reads
```

### Prevention
```
- Avoid HMS for high-concurrency streaming tables
- Use catalog that supports optimistic concurrency (Glue, Nessie, REST)
- Design write patterns to minimize concurrent commits to same table
- Monitor lock wait time and contention metrics
```

---

## Issue #11: Metadata Location Becomes Invalid After S3 Bucket Rename/Migration

**Severity:** P0 - Critical
**Frequency:** During infrastructure migrations
**Affected Components:** All tables in migrated bucket
**First seen at:** Companies migrating between AWS accounts or regions

### Symptoms
```
- All tables fail: "FileNotFoundException: s3://old-bucket/..."
- Catalog entries still point to old S3 paths
- Even after updating catalog, internal metadata references use absolute paths
- metadata.json contains hardcoded S3 paths to manifest lists
- Manifest files contain hardcoded paths to data files
```

### Root Cause
```
Iceberg metadata contains ABSOLUTE paths everywhere:

metadata.json:
  "manifest-list": "s3://old-bucket/db/table/metadata/snap-123-m0.avro"

manifest-list.avro:
  manifest_path: "s3://old-bucket/db/table/metadata/manifest-abc.avro"

manifest.avro:
  data_file.path: "s3://old-bucket/db/table/data/00001.parquet"

Simply renaming/copying the bucket doesn't update these internal references!
Every file in the metadata chain contains absolute paths.
```

### Immediate Fix
```python
# Use Iceberg's table migration API (rewrites metadata only, not data)
from pyiceberg.catalog import load_catalog

catalog = load_catalog("prod")

# Register table at new location (creates new metadata pointing to data)
# This only works if data files are accessible at the same paths
# If bucket changed, you need to use add_files or rewrite metadata

# For S3 bucket rename/copy:
# 1. Copy ALL files to new bucket (preserving directory structure)
# 2. Update catalog pointer to new metadata location
# 3. Rewrite metadata to update internal paths:

spark.sql("""
    CALL prod.system.migrate(
        table => 'db.table',
        properties => map(
            'location', 's3://new-bucket/db/table/'
        )
    )
""")
```

### Permanent Fix
```
1. Use relative paths where possible (Iceberg v2 supports this for some refs)
2. Implement proper migration tooling:
   - Script that rewrites ALL metadata files with updated paths
   - Verify integrity after migration (row count, checksum)
3. Use warehouse-relative paths:
   spark.sql.catalog.prod.warehouse = s3://bucket/warehouse/
   Tables use relative paths under warehouse root
4. For multi-account: use S3 access points instead of bucket names
```

### Prevention
```
- Plan S3 bucket naming strategy upfront (include account, region, environment)
- Use warehouse-relative paths from day 1
- Document and test migration procedures before you need them
- Keep old bucket accessible (read-only) during migration window
- Never rename production S3 buckets without Iceberg migration plan
```

---

## Issue #12: Timestamp Precision Mismatch (Microseconds vs Milliseconds)

**Severity:** P2 - Medium (but causes subtle data issues)
**Frequency:** When mixing Spark 3.x and Flink or Trino writers
**Affected Components:** Data correctness, join mismatches, deduplication failures
**First seen at:** Mixed engine environments (common)

### Symptoms
```
- JOINs on timestamp columns return no matches (off by factor of 1000)
- Deduplication fails: "same" event appears twice with different timestamps
- Partition pruning doesn't work (timestamp resolves to wrong partition)
- Trino reads Flink-written data with wrong timestamps
- Event ordering is incorrect after reading from different engine
```

### Root Cause
```
Different engines use different timestamp precision:

  Flink: TIMESTAMP(6) → microseconds (default Iceberg behavior)
  Spark 3.x: TIMESTAMP → microseconds (configurable)
  Spark 2.x: TIMESTAMP → milliseconds (legacy)
  Trino: TIMESTAMP(6) → microseconds
  Athena: TIMESTAMP → milliseconds (engine v2) or microseconds (engine v3)

  If table created with Spark 2.x (millis) and Flink writes micros:
  Event time: 2024-01-15 10:30:00.123456
  Stored by Flink: 1705312200123456 (microseconds)
  Read by Spark 2.x: interprets as 1705312200123456 milliseconds
                    → year 56,000 something → WRONG

  Partition mismatch:
  days(event_ts) with microseconds → day X
  Same value read as milliseconds → day Y
  → Query can't find the data (wrong partition pruning)
```

### Immediate Fix
```sql
-- Check table's timestamp type
DESCRIBE EXTENDED db.table;
-- Look for: event_ts TIMESTAMP (microseconds) vs TIMESTAMP_MS

-- Force consistent reading
SET spark.sql.iceberg.handle-timestamp-without-timezone = true;
SET spark.sql.session.timeZone = UTC;
```

### Permanent Fix
```sql
-- Use explicit precision in table definition
CREATE TABLE db.events (
    event_id STRING,
    event_ts TIMESTAMP,           -- Always microsecond precision in Iceberg v2
    event_ts_ms TIMESTAMP_MS,     -- Explicit millisecond if needed for compatibility
    ...
) USING iceberg
TBLPROPERTIES (
    'format-version' = '2'        -- v2 standardizes on microseconds
);
```

```properties
# Spark configuration for consistency
spark.sql.iceberg.handle-timestamp-without-timezone = true
spark.sql.session.timeZone = UTC
```

### Prevention
```
- Standardize on Iceberg format version 2 (microsecond precision)
- ALWAYS use UTC for all timestamp columns
- Document timestamp precision conventions for all teams
- Integration test: write with Engine A, read with Engine B, verify values
- Use TIMESTAMPTZ (timestamp with timezone) to avoid ambiguity
```

---

## Issue #13: Catalog Namespace Conflicts (Cross-Team Table Overwrite)

**Severity:** P0 - Critical
**Frequency:** In organizations without governance
**Affected Components:** Data integrity, team trust
**First seen at:** Fast-growing companies with multiple data teams

### Symptoms
```
- Team B's table suddenly has Team A's data
- "Table already exists" errors when team tries to create their table
- Schema changes appear that no one on the team made
- Production table silently replaced by development version
- Audit log shows unexpected ALTER TABLE from unknown principal
```

### Root Cause
```
Shared catalog without namespace governance:

  Team A: CREATE TABLE prod.transactions (...)  -- payments team
  Team B: CREATE TABLE prod.transactions (...)  -- fraud team
  
  Both think they own "prod.transactions" → whoever ran last wins
  
  Or: Developer accidentally runs against prod catalog:
  spark.sql.catalog.prod (points to production Glue)
  CREATE TABLE prod.db.my_test_table (...)  -- Creates in PRODUCTION
  
  No namespace isolation + no access control = disaster waiting to happen
```

### Immediate Fix
```python
# Audit: find who owns what
import boto3
glue = boto3.client('glue')

tables = glue.get_tables(DatabaseName='prod')
for table in tables['TableList']:
    print(f"{table['Name']}: created by {table.get('CreatedBy', 'unknown')}"
          f" at {table.get('CreateTime')}")
```

### Permanent Fix
```
1. Namespace convention enforced by policy:
   {environment}.{team}.{domain}.{table}
   Example: prod.payments.transactions.completed

2. IAM/Lake Formation policies:
   - Team A can only write to prod.payments.*
   - Team B can only write to prod.fraud.*
   - Cross-team read requires explicit grant

3. Catalog-level RBAC:
```

```json
// Lake Formation permission
{
  "Principal": {"DataLakePrincipalIdentifier": "arn:aws:iam::123:role/payments-team"},
  "Resource": {
    "Database": {"Name": "prod_payments"},
    "TableWildcard": {}
  },
  "Permissions": ["ALL"],
  "PermissionsWithGrantOption": []
}
```

### Prevention
```
- Enforce namespace naming convention via CI/CD validation
- Block direct catalog writes: all changes go through PR-reviewed Terraform
- Use separate catalogs per environment (dev/staging/prod)
- Enable AWS CloudTrail for Glue API (audit all catalog changes)
- Implement data ownership registry (who owns which namespace)
```

---

## Issue #14: Metadata JSON Parsing Failure After Iceberg Library Upgrade

**Severity:** P1 - High
**Frequency:** During Iceberg version upgrades
**Affected Components:** All operations on affected tables
**First seen at:** Teams upgrading from Iceberg 0.x to 1.x

### Symptoms
```
- After library upgrade: "Cannot parse metadata file: unknown field 'xyz'"
- Old tables unreadable with new library version
- New tables unreadable with old library version (other team hasn't upgraded)
- "Unsupported format version: 2" errors (older library)
- Mixed fleet: some jobs on Iceberg 1.3, others on 1.5 → incompatible
```

### Root Cause
```
Iceberg metadata format evolves across versions:

  Format v1 (Iceberg 0.x - 1.x):
    - No row-level deletes
    - Sequence numbers not tracked
    - Older metadata structure

  Format v2 (Iceberg 1.x+):
    - Row-level deletes (position + equality)
    - Sequence numbers for ordering
    - Additional fields in metadata

  Problem: Upgrading table to format v2 makes it UNREADABLE by format v1 libraries.
  
  Mixed environment:
    Job A (Iceberg 1.5): upgrades table to format v2
    Job B (Iceberg 1.1): cannot read format v2 → FAIL
    
  Library compatibility:
    Iceberg 1.5 can read: format v1, v2
    Iceberg 1.1 can read: format v1 only
    Iceberg 0.14 can read: format v1 only (partial)
```

### Immediate Fix
```sql
-- Do NOT upgrade format version until ALL consumers are updated
-- Check current format:
SELECT * FROM prod.db.table.metadata_log_entries;

-- If accidentally upgraded, you CANNOT downgrade format version
-- Must ensure all readers upgrade their library
```

### Permanent Fix
```
1. Coordinated upgrade process:
   Step 1: Upgrade ALL reader/writer libraries to version that supports v2
   Step 2: Wait 1 week (verify no issues)
   Step 3: Upgrade table format version:
   
   ALTER TABLE db.table SET TBLPROPERTIES ('format-version' = '2');
   
2. Pin Iceberg library version across all jobs:
   - Use single BOM (Bill of Materials) for Iceberg deps
   - All teams must use same minor version
   
3. Version compatibility matrix in docs:
   Table format v1: readable by Iceberg >= 0.12
   Table format v2: readable by Iceberg >= 1.0
```

### Prevention
```
- Maintain Iceberg version compatibility matrix for your organization
- NEVER upgrade format version without verifying ALL consumers
- Use single dependency management (Maven BOM / requirements.txt)
- Integration test: upgrade library → verify all tables readable
- Document format version per table in data catalog
```

---

## Issue #15: Snapshot Reference Leak (Branches/Tags Not Cleaned Up)

**Severity:** P2 - Medium
**Frequency:** Teams using branching (Nessie or Iceberg refs)
**Affected Components:** Storage costs, metadata bloat
**First seen at:** Teams using branches for testing/staging

### Symptoms
```
- Storage keeps growing despite expire_snapshots running
- Old branches reference ancient snapshots (prevent GC)
- S3 costs unexpectedly high (data files can't be deleted)
- expire_snapshots completes but storage unchanged
- "Referenced by branch 'test-2023-jan'" blocks file deletion
```

### Root Cause
```
Snapshot references (branches/tags) prevent garbage collection:

  main: snap-100 → snap-101 → snap-102 (current)
  branch "old-test": → snap-005 (created 6 months ago)
  tag "release-v1": → snap-020 (created 3 months ago)

  expire_snapshots(older_than = 7 days):
    - Cannot expire snap-005 (referenced by branch "old-test")
    - Cannot expire snap-020 (referenced by tag "release-v1")
    - All data files referenced by snap-005 and snap-020 are RETAINED
    
  If snap-005 references 10TB of data files that would otherwise be GC'd:
    → 10TB of storage waste because of forgotten branch

  Common cause: developers create branches for testing, never clean up
```

### Immediate Fix
```sql
-- List all references
SELECT * FROM prod.db.table.refs;

-- Drop stale branches
ALTER TABLE db.table DROP BRANCH `old-test`;
ALTER TABLE db.table DROP BRANCH `experiment-2023-q1`;

-- Drop old tags (keep last N releases)
ALTER TABLE db.table DROP TAG `release-v1`;
ALTER TABLE db.table DROP TAG `release-v2`;

-- Now expire_snapshots can clean up
CALL prod.system.expire_snapshots(
  table => 'db.table',
  older_than => current_timestamp() - INTERVAL 7 DAYS,
  retain_last => 5
);
```

### Permanent Fix
```python
# Automated ref cleanup policy
def cleanup_stale_refs(table_name, max_branch_age_days=30, max_tag_age_days=90):
    refs = spark.sql(f"SELECT * FROM prod.{table_name}.refs").collect()
    
    for ref in refs:
        if ref['type'] == 'branch' and ref['name'] != 'main':
            age_days = (datetime.now() - ref['max_snapshot_age']).days
            if age_days > max_branch_age_days:
                spark.sql(f"ALTER TABLE {table_name} DROP BRANCH `{ref['name']}`")
                
        elif ref['type'] == 'tag':
            age_days = (datetime.now() - ref['snapshot_age']).days
            if age_days > max_tag_age_days:
                spark.sql(f"ALTER TABLE {table_name} DROP TAG `{ref['name']}`")
```

### Prevention
```
- Set branch/tag retention policies at creation:
  ALTER TABLE db.table CREATE BRANCH test_branch 
    RETAIN 7 DAYS;  -- Auto-expires after 7 days
  
  ALTER TABLE db.table CREATE TAG release_v3 
    RETAIN 90 DAYS;  -- Auto-expires after 90 days

- Document: all branches must have RETAIN clause
- Weekly audit of refs across all tables
- Alert when ref count exceeds threshold
```

---

## Summary: Metadata & Catalog Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 1 | Metadata file explosion | P1 | Auto-delete + expire_snapshots |
| 2 | Catalog pointer corruption | P0 | Locking + retry + backup |
| 3 | Snapshot list unbounded growth | P1 | Aggressive expire + retention policy |
| 4 | Glue catalog throttling | P1 | Caching + multi-account + limits |
| 5 | Manifest list explosion | P1 | rewrite_manifests + merge on commit |
| 6 | Orphan metadata files | P2 | Paired expire + remove_orphan schedule |
| 7 | Partition metadata explosion | P1 | bucket() + partition evolution |
| 8 | Stale catalog cache | P1 | TTL config + REFRESH TABLE |
| 9 | Schema ID collision on recreate | P0 | ALTER TABLE (never drop+create) |
| 10 | HMS lock contention | P1 | Migrate to Nessie/Glue |
| 11 | Invalid metadata paths after migration | P0 | Proper migration tooling |
| 12 | Timestamp precision mismatch | P2 | Format v2 + explicit precision |
| 13 | Namespace conflicts | P0 | RBAC + naming convention |
| 14 | Library upgrade breaking metadata | P1 | Coordinated upgrade process |
| 15 | Snapshot reference leak | P2 | RETAIN clause + automated cleanup |
