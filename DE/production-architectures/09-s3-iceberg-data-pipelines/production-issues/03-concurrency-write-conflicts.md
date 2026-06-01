# Concurrency & Write Conflict Issues (#31-45)

Issues related to concurrent writers, optimistic concurrency control, commit conflicts,
and data consistency at scale.

---

## Issue #31: Commit Conflict Storm (Multiple Writers to Same Table)

**Severity:** P0 - Critical
**Frequency:** Daily on tables with >5 concurrent writers
**Affected Components:** All write operations, pipeline SLAs
**First seen at:** Streaming + batch writers to same table

### Symptoms
```
- CommitFailedException across multiple jobs simultaneously
- Retry storms: all writers retry at same time → more conflicts
- Pipeline latency spikes from 5 min to 2 hours
- Cascading failures: upstream Kafka consumer lag grows
- Alert fatigue: hundreds of "commit failed" alerts per hour
```

### Root Cause
```
Optimistic concurrency with multiple writers:

  Writer A: Read metadata v5 → Process → Try commit → SUCCESS (v6)
  Writer B: Read metadata v5 → Process → Try commit → FAIL (v5 is stale, now v6)
  Writer C: Read metadata v5 → Process → Try commit → FAIL (v5 is stale, now v6)
  
  B retries: Read v6 → Process → Try commit → FAIL (C committed v7)
  C retries: Read v7 → Process → Try commit → FAIL (B committed v8)
  
  → Livelock: Writers keep invalidating each other
  → With 10 writers: probability of clean commit = 1/10 per attempt
  → Average attempts before success grows exponentially
  
  Thundering herd: All retries happen simultaneously
  → All fail again → retry again → spiral
```

### Immediate Fix
```python
# Add jitter to retry intervals (break thundering herd)
spark.conf.set("spark.sql.catalog.prod.commit.retry.num-retries", "20")
spark.conf.set("spark.sql.catalog.prod.commit.retry.min-wait-ms", "100")
spark.conf.set("spark.sql.catalog.prod.commit.retry.max-wait-ms", "60000")

# Add random jitter to job start times
import random, time
time.sleep(random.uniform(0, 60))  # 0-60 second random delay
```

### Permanent Fix
```
1. Reduce number of concurrent writers:
   - Use single writer per table (fan-in pattern)
   - Partition ownership: Writer A owns partition 1-100, B owns 101-200
   
2. Write to separate tables, merge periodically:
   - streaming_raw_1, streaming_raw_2 → merged into final_table
   
3. Use write-ahead pattern:
   - Writers write to staging S3 path
   - Single coordinator commits to Iceberg (serialized)
   
4. Optimistic concurrency tuning:
```

```properties
# Aggressive retry with exponential backoff + jitter
commit.retry.num-retries = 30
commit.retry.min-wait-ms = 200
commit.retry.max-wait-ms = 120000
commit.retry.total-timeout-ms = 600000

# Enable commit conflict resolution for compatible operations
commit.retry.enable-conflict-resolution = true
```

```python
# Fan-in writer pattern
class FanInWriter:
    """Single writer that consumes from multiple input streams."""
    
    def __init__(self, table_name, input_topics):
        self.table_name = table_name
        self.buffer = []
        self.commit_interval_seconds = 60
        
    def run(self):
        while True:
            # Consume from all input topics into single buffer
            for topic in self.input_topics:
                messages = kafka_consumer.poll(topic, timeout=1000)
                self.buffer.extend(messages)
            
            if time.time() - last_commit > self.commit_interval_seconds:
                # Single atomic commit (no conflicts possible)
                self.commit_buffer()
                last_commit = time.time()
```

### Prevention
```
- Design for single-writer-per-table where possible
- If multi-writer needed: partition ownership (no overlap)
- Monitor commit conflict rate: >10% is a design problem
- Use Flink with single-writer topology (coordinator pattern)
- Consider Nessie branches for parallel work → merge
```

---

## Issue #32: Lost Updates (Last Writer Wins Semantics)

**Severity:** P0 - Critical
**Frequency:** When using append without proper concurrency control
**Affected Components:** Data correctness, silent data loss
**First seen at:** Multiple batch jobs writing overlapping data

### Symptoms
```
- Row counts don't match expected (data silently lost)
- No errors in any job - all report success
- Audit shows: Job A wrote 1M rows, Job B wrote 1M rows, table has 1M (not 2M)
- Happens only when jobs overlap in time
- Difficult to detect (no error, just wrong count)
```

### Root Cause
```
Overwrite mode without proper conflict detection:

  Job A: df.writeTo("table").overwritePartitions()  -- partition = 2024-01-15
  Job B: df.writeTo("table").overwritePartitions()  -- partition = 2024-01-15
  
  If A and B run concurrently and both overwrite the same partition:
  
  T1: A reads partition (empty) → processes 1M rows
  T2: B reads partition (empty) → processes 1M rows  
  T3: A commits → partition has A's 1M rows
  T4: B commits → partition OVERWRITTEN with B's 1M rows (A's data LOST!)
  
  With Iceberg, B should get CommitFailedException, BUT:
  - If using dynamic overwrite and partitions don't overlap → no conflict detected
  - If using replace with mismatched conflict detection rules → silent overwrite
  - If overwrite is "full table" scope → last writer wins by design
```

### Immediate Fix
```python
# Use append mode (never lose data via append)
df.writeTo("db.table").append()

# If overwrite needed, use explicit conflict detection:
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

# Verify after write:
expected_count = df.count()
actual_count = spark.sql("SELECT COUNT(*) FROM db.table WHERE partition = '2024-01-15'").first()[0]
assert actual_count >= expected_count, "Data loss detected!"
```

### Permanent Fix
```
1. Prefer MERGE INTO over overwrite (handles conflicts explicitly)
2. Use append + dedup downstream (safer than overwrite)
3. Partition ownership: only one job can write to a given partition
4. Post-write validation: compare expected vs actual row counts
5. Use Iceberg's write-audit-publish pattern:
   - Write to hidden branch
   - Validate counts
   - Fast-forward merge to main
```

---

## Issue #33: Deadlock Between Compaction and Schema Evolution

**Severity:** P1 - High
**Frequency:** During schema changes on actively compacted tables
**Affected Components:** Both compaction and schema evolution blocked
**First seen at:** Teams evolving schema on streaming tables

### Symptoms
```
- ALTER TABLE hangs indefinitely
- Compaction fails: "Table metadata has changed since operation started"
- Both operations retry infinitely, neither succeeds
- Table schema stuck in inconsistent state
- Manual intervention required to break deadlock
```

### Root Cause
```
Schema evolution and compaction both need to update metadata:

  Compaction: Reads metadata v5 → rewrites files → commits metadata v6
  ALTER TABLE: Reads metadata v5 → changes schema → commits metadata v6
  
  If concurrent:
    Compaction commits v6 (file changes)
    ALTER retries: reads v6 → changes schema → commits v7
    → This usually works because changes don't conflict
    
  BUT: Some schema changes invalidate compaction:
    - Compaction wrote files with schema v5 (3 columns)
    - ALTER TABLE drops column 3
    - Compaction commits files that reference column 3
    → Conflict: new files have column that no longer exists in schema
    
  Or: Compaction takes so long that metadata expires:
    - Compaction started 2 hours ago (based on v5)
    - 100 schema changes happened (now v105)
    - Compaction cannot resolve conflict with 100 intermediate changes
    → Always fails
```

### Immediate Fix
```bash
# Pause compaction, do schema change, resume
# Step 1: Kill compaction job
kubectl delete job iceberg-compaction-job

# Step 2: Do schema change
spark-sql -e "ALTER TABLE db.table ADD COLUMN new_col STRING"

# Step 3: Restart compaction
kubectl apply -f compaction-cronjob.yaml
```

### Permanent Fix
```
1. Serialize schema changes and compaction:
   - Maintenance window: pause writes → schema change → compact → resume
   
2. Use locking mechanism:
   - Before schema change: acquire table-level advisory lock
   - Compaction checks lock before starting
   
3. Short-lived compaction (less likely to conflict):
   - partial-progress with small commits
   - Each sub-commit takes <1 minute (unlikely to conflict with schema change)
   
4. Schema change notification:
   - Schema change publishes event
   - Compaction service resets and re-reads metadata
```

---

## Issue #34: Concurrent MERGE INTO Corrupts Data

**Severity:** P0 - Critical
**Frequency:** When multiple MERGE jobs target same table
**Affected Components:** Data integrity
**First seen at:** Multiple CDC streams merging into same dimension table

### Symptoms
```
- Duplicate rows appear after concurrent MERGE operations
- Some updates missing (applied by one MERGE but lost by another)
- Row count grows unexpectedly (inserts duplicated)
- MERGE job A's changes overwritten by MERGE job B
- Inconsistent state: some keys updated, others not
```

### Root Cause
```
MERGE INTO reads target, computes changes, then commits atomically.
With concurrent MERGEs on overlapping keys:

  MERGE A: reads target (user 1: status=active)
  MERGE B: reads target (user 1: status=active)  
  MERGE A: user 1 changed to status=suspended → commits
  MERGE B: user 1 changed to status=premium → commits
  
  Both see "active" as starting state.
  Both generate delete + insert for user 1.
  
  Final state depends on which commits last:
  - If Iceberg detects conflict: one fails, retries, correct result
  - If operations target different FILE SETS: both succeed → DUPLICATE user 1
  
  Iceberg conflict detection is FILE-based:
  - If MERGE A touched file X and MERGE B touched file Y:
    → No conflict detected (different file sets)
    → Both changes committed → user 1 exists in BOTH files = DUPLICATE
    
  This happens when user 1's data is in file X (read by A)
  and user 1 has a new row inserted by B into file Y.
```

### Permanent Fix
```
1. NEVER run concurrent MERGE on overlapping key spaces:
   - MERGE A: WHERE region = 'US'
   - MERGE B: WHERE region = 'EU'
   - Non-overlapping → safe concurrent execution
   
2. Single MERGE writer per table (fan-in pattern):
   - All change events → single Kafka topic → single MERGE job
   
3. Use deterministic partitioning for MERGE isolation:
   - Partition by hash(merge_key) 
   - Each MERGE job owns specific hash partitions
   
4. Post-MERGE deduplication check:
```

```python
# Validate no duplicates after MERGE
def validate_merge(table_name, key_column):
    dupes = spark.sql(f"""
        SELECT {key_column}, COUNT(*) as cnt 
        FROM prod.{table_name} 
        GROUP BY {key_column} 
        HAVING COUNT(*) > 1
    """).count()
    
    if dupes > 0:
        raise DataIntegrityError(f"Found {dupes} duplicate keys after MERGE!")
```

---

## Issue #35: Write-Write Conflict on Partition-Level Overwrite

**Severity:** P1 - High  
**Frequency:** During parallel batch job execution
**Affected Components:** Batch pipeline reliability
**First seen at:** Airflow DAGs with parallel partition processing

### Symptoms
```
- Airflow task fails: "Cannot commit: conflict in partition X"
- Retry succeeds but adds 5 min latency to pipeline
- Some days: 0 conflicts. Other days: 50+ conflicts.
- Conflicts correlate with number of parallel tasks
- Pipeline SLA breach on high-conflict days
```

### Root Cause
```
Dynamic partition overwrite with overlapping partition scopes:

  Spark dynamic overwrite: replaces ONLY partitions present in the write DataFrame.
  
  Job A writes: partitions [2024-01-15, 2024-01-16]
  Job B writes: partitions [2024-01-16, 2024-01-17]
  
  Overlap on 2024-01-16 → conflict!
  
  Even with static partition overwrite:
  If both jobs compute data for the same date (e.g., late-arriving data handling)
  → Both try to overwrite same partition → conflict
  
  Common pattern in Airflow:
    Task 1: Process events for 2024-01-15 (includes late events for 01-14)
    Task 2: Process events for 2024-01-14 (backfill)
    Both write to partition 2024-01-14 → conflict
```

### Permanent Fix
```python
# Strategy 1: Strict partition ownership
# Each job ONLY writes to its assigned partition (no spillover)
def strict_partition_write(df, table_name, partition_date):
    # Filter to ONLY the owned partition
    df_filtered = df.filter(f"event_date = '{partition_date}'")
    df_filtered.writeTo(f"prod.{table_name}") \
        .overwritePartitions()

# Strategy 2: Append + downstream dedup (no overwrites)
def append_with_dedup(df, table_name):
    df.writeTo(f"prod.{table_name}").append()
    # Downstream MERGE handles dedup

# Strategy 3: Serial execution for overlapping partitions
# In Airflow, set dependencies correctly:
# task_jan_14 >> task_jan_15 (not parallel if they overlap)
```

---

## Issue #36: Optimistic Concurrency Retry Exhaustion

**Severity:** P1 - High
**Frequency:** On hot tables with 10+ concurrent commits/second
**Affected Components:** Write reliability, data loss risk
**First seen at:** High-frequency trading data pipelines

### Symptoms
```
- "CommitFailedException: Exceeded maximum retry attempts (10)"
- Data batch dropped (not committed) without recovery
- Monitoring shows 50%+ commit failure rate
- Increasing retries makes problem worse (longer conflicts)
- Only happens during peak hours (9 AM - 4 PM)
```

### Root Cause
```
With N concurrent writers and commit duration D:

  Probability of conflict per attempt ≈ 1 - (1/N)
  Expected attempts to succeed: N (on average)
  
  With 10 concurrent writers, default 10 retries:
    P(success in 10 attempts) = 1 - (9/10)^10 = 65%
    → 35% of commits FAIL after exhausting retries!
    
  With 20 concurrent writers, 10 retries:
    P(success in 10 attempts) = 1 - (19/20)^10 = 40%
    → 60% failure rate!
    
  Increasing retries helps but with diminishing returns:
    20 writers, 50 retries: P(success) = 92%
    20 writers, 100 retries: P(success) = 99.4%
    → Still losing 0.6% of commits = millions of rows at scale

  Also: longer retry = longer commit duration = MORE conflicts (positive feedback loop)
```

### Permanent Fix
```
1. Reduce concurrent writers (best solution):
   - Fan-in: 20 writers → 1 coordinator
   - Partition ownership: 20 writers on 20 non-overlapping partitions
   
2. Micro-batch aggregation before commit:
   - Buffer 60 seconds of writes → single commit
   - Fewer commits/second = fewer conflicts
   
3. Conflict-free write patterns:
   - APPEND ONLY (appends never conflict with each other!)
   - Partition-scoped writes (different partitions = no conflict)
   
4. If must have many writers: very aggressive retry:
```

```properties
commit.retry.num-retries = 100
commit.retry.min-wait-ms = 50
commit.retry.max-wait-ms = 30000
commit.retry.total-timeout-ms = 300000
```

---

## Issue #37: Snapshot Isolation Violation (Read-Your-Own-Write Failure)

**Severity:** P1 - High
**Frequency:** In multi-stage pipelines within single Spark session
**Affected Components:** Pipeline correctness
**First seen at:** ETL pipelines that write then immediately read

### Symptoms
```
- Write 1M rows → immediately query → 0 rows returned
- Pipeline logic assumes previous stage's data is visible
- Counts don't match between write confirmation and read
- Only happens in same Spark session (works fine across sessions)
- Adding sleep(30) between write and read "fixes" it
```

### Root Cause
```
Spark catalog caching:

  # Same SparkSession:
  df.writeTo("db.table").append()  # Commits snapshot v5
  result = spark.sql("SELECT COUNT(*) FROM db.table")  # Still sees snapshot v4!
  
  Why: Spark caches table metadata per session.
  The write committed v5 to the catalog, but the reader side
  still has v4 cached in the SparkSession's catalog cache.
  
  Different SparkSessions or different engines (Trino) would see v5
  because they load metadata fresh.
  
  This is NOT a bug - it's by design (snapshot isolation).
  But it surprises developers who expect read-your-own-write semantics.
```

### Immediate Fix
```python
# Force refresh after write
df.writeTo("db.table").append()
spark.sql("REFRESH TABLE db.table")  # Invalidate cache
result = spark.sql("SELECT COUNT(*) FROM db.table")  # Now sees latest
```

### Permanent Fix
```python
# Wrapper that auto-refreshes after write
class IcebergWriter:
    def __init__(self, spark):
        self.spark = spark
    
    def write_and_refresh(self, df, table_name, mode='append'):
        if mode == 'append':
            df.writeTo(table_name).append()
        elif mode == 'overwrite':
            df.writeTo(table_name).overwritePartitions()
        
        # Always refresh to see own writes
        self.spark.sql(f"REFRESH TABLE {table_name}")
        return self
```

---

## Issue #38: Partition-Level Lock Escalation (Whole-Table Lock)

**Severity:** P1 - High
**Frequency:** With HMS catalog under concurrent writes
**Affected Components:** Write parallelism completely lost
**First seen at:** On-prem Hive Metastore with MySQL backend

### Symptoms
```
- Writing to different partitions still conflicts
- Sequential commits (one at a time) despite targeting different partitions
- Commit throughput: 1 per second regardless of partition
- "Lock escalation" in MySQL slow query log
- Adding more writers doesn't increase throughput
```

### Root Cause
```
HMS locks at TABLE level, not PARTITION level:

  Iceberg commit with HMS:
    1. Lock table row in metastore DB
    2. Read current metadata location
    3. Write new metadata file
    4. Update table row with new location
    5. Release lock
    
  Even if Writer A writes to partition 1 and Writer B writes to partition 2:
    BOTH need to update the SAME table row in HMS
    → Sequential, even though changes are logically independent
    
  This is a catalog limitation, not an Iceberg limitation.
  Glue and Nessie handle this differently (optimistic, not pessimistic locking).
```

### Permanent Fix
```
1. Migrate to catalog with optimistic concurrency:
   - AWS Glue: CAS (Compare-And-Swap) on metadata location
   - Nessie: Git-like multi-table atomic commits
   - REST Catalog: Implementation-specific (can be optimistic)
   
2. If stuck with HMS: use Iceberg's HadoopCatalog instead
   - Uses rename-based atomic commit on HDFS/S3
   - No metastore lock required
   - Limitation: no external catalog features
   
3. Write buffering: single writer per table, buffer incoming
```

---

## Issue #39: Cross-Table Atomic Commit Not Supported

**Severity:** P2 - Medium
**Frequency:** When pipelines need multi-table consistency
**Affected Components:** Data consistency across tables
**First seen at:** ETL that writes to fact + dimension tables

### Symptoms
```
- Fact table updated but dimension table commit fails → inconsistent state
- Queries joining updated fact with stale dimension get wrong results
- Partial pipeline failures leave tables at different snapshots
- No rollback mechanism across tables
```

### Root Cause
```
Iceberg commits are per-table atomic, NOT cross-table:

  Pipeline writes to:
    1. dim_customers (updates)
    2. fact_orders (appends)
    3. agg_daily_revenue (rebuilds)
    
  Each is independent commit. If step 2 fails after step 1 committed:
    → dim_customers updated, fact_orders stale
    → Queries joining them get incorrect results
    
  No multi-table transaction support in standard catalogs (Glue, HMS).
  Exception: Nessie supports multi-table atomic commits.
```

### Permanent Fix
```
1. Use Nessie catalog for multi-table atomicity:
   - Branch: creates isolated multi-table workspace
   - Commit: atomic across all tables in branch
   - Merge: promotes all changes to main atomically
   
2. Design for eventual consistency:
   - Write fact first (append-only, safe)
   - Write dimensions (MERGE, idempotent)
   - Design queries to tolerate lag between tables
   
3. Staging pattern:
   - Write all tables to staging (branch/hidden snapshots)
   - Validation pass
   - Promote all (fast-forward branch references)
   
4. Compensation pattern:
   - If step 2 fails: rollback step 1 to previous snapshot
```

```python
# Nessie multi-table atomic commit
from pynessie import NessieClient

client = NessieClient(endpoint="http://nessie:19120/api/v2")

# Create branch for atomic work
branch = client.create_branch("etl-run-20240115", ref="main")

# All writes happen on branch (isolated)
spark.conf.set("spark.sql.catalog.prod.ref", "etl-run-20240115")
df_dim.writeTo("prod.dim_customers").overwritePartitions()
df_fact.writeTo("prod.fact_orders").append()
df_agg.writeTo("prod.agg_daily").overwritePartitions()

# Atomic merge (all or nothing)
client.merge_branch("etl-run-20240115", into="main")
```

---

## Issue #40: WAL (Write-Ahead Log) Conflict in Flink Exactly-Once

**Severity:** P1 - High
**Frequency:** After Flink job restart or failover
**Affected Components:** Exactly-once guarantee broken
**First seen at:** Flink jobs recovering from checkpoint failures

### Symptoms
```
- After Flink restart: duplicate data in Iceberg table
- Commit IDs don't match between Flink checkpoint and Iceberg snapshots
- Flink job fails: "Snapshot already committed by another job instance"
- Two Flink job instances running simultaneously (zombie + new)
- Exactly-once violated: some events written twice
```

### Root Cause
```
Flink exactly-once with Iceberg relies on:
  1. Flink checkpoint ID → maps to → Iceberg commit
  2. On recovery, Flink replays from last successful checkpoint
  3. If previous instance committed to Iceberg but Flink checkpoint failed:
     → Iceberg has the data (committed)
     → Flink doesn't know (checkpoint lost)
     → Flink replays and commits AGAIN = duplicates!
     
  Zombie instance scenario:
    - Instance A: checkpoint 100 → commits to Iceberg → crashes before ack
    - Flink restarts Instance B: resumes from checkpoint 99
    - Instance B: replays 99→100 → commits to Iceberg AGAIN
    - Iceberg has data from both commits = duplicates
    
  Root: Flink and Iceberg are separate systems without distributed transaction
```

### Permanent Fix
```java
// Flink IcebergSink with proper exactly-once configuration
FlinkSink.forRowData(inputStream)
    .tableLoader(tableLoader)
    .overwrite(false)
    .equalityFieldColumns(Arrays.asList("event_id"))  // Dedup key
    .upsert(true)  // Use upsert mode (handles duplicates via MERGE)
    .build();

// Alternative: Use commit ID tracking
// Store last committed Flink checkpoint ID in Iceberg table properties
// On restart: check if checkpoint already committed → skip replay
```

```python
# Deduplication layer after Flink writes (safety net)
def deduplicate_recent(table_name, key_col, window_hours=2):
    """Remove duplicates from recent commits (post-recovery safety net)."""
    spark.sql(f"""
        MERGE INTO prod.{table_name} t
        USING (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY {key_col} ORDER BY event_timestamp DESC
            ) as rn
            FROM prod.{table_name}
            WHERE ingestion_time > current_timestamp() - INTERVAL {window_hours} HOURS
        ) s
        ON t.{key_col} = s.{key_col}
        WHEN MATCHED AND s.rn > 1 THEN DELETE
    """)
```

---

## Issue #41: Concurrent expire_snapshots Corrupts Metadata

**Severity:** P0 - Critical
**Frequency:** When multiple maintenance jobs run simultaneously
**Affected Components:** Table integrity
**First seen at:** Teams with overlapping Airflow maintenance DAGs

### Symptoms
```
- Table becomes unreadable after two expire_snapshots ran concurrently
- "FileNotFoundException" for manifests that should exist
- Snapshot chain has gaps (parent snapshot missing)
- Some queries work, others fail (depending on which manifests exist)
```

### Root Cause
```
expire_snapshots is NOT safe to run concurrently on same table:

  Expire A: reads snapshots, decides to remove snap-5, snap-6, snap-7
  Expire B: reads snapshots, decides to remove snap-5, snap-6, snap-7 (same!)
  
  Expire A: removes manifests only referenced by snap-5 (manifest-X)
  Expire B: removes manifests only referenced by snap-6 (manifest-Y)
  
  But: snap-7 referenced manifest-X AND manifest-Y!
  Expire A thought "manifest-X is only in snap-5" (didn't account for B removing snap-6)
  
  Result: manifest-X deleted but still needed by remaining snapshots
  → Table corrupted: FileNotFoundException on reads
```

### Permanent Fix
```python
# Use distributed lock for maintenance operations
import redis

class IcebergMaintenanceLock:
    def __init__(self):
        self.redis = redis.Redis(host='redis-cluster')
    
    def run_with_lock(self, table_name, operation):
        lock_key = f"iceberg:maintenance:{table_name}"
        lock = self.redis.lock(lock_key, timeout=3600)  # 1 hour max
        
        if lock.acquire(blocking=True, blocking_timeout=60):
            try:
                operation()
            finally:
                lock.release()
        else:
            raise TimeoutError(f"Could not acquire lock for {table_name}")
```

```
Rules for maintenance operations:
  1. NEVER run concurrent expire_snapshots on same table
  2. NEVER run concurrent remove_orphan_files on same table
  3. Compaction CAN run concurrently (uses optimistic concurrency)
  4. Use distributed lock (Redis/DynamoDB) for expire + orphan cleanup
  5. Order: expire_snapshots → remove_orphan_files (never reverse)
```

---

## Issue #42: Branch Merge Conflicts in Nessie

**Severity:** P2 - Medium
**Frequency:** When multiple teams work on same tables via branches
**Affected Components:** Team workflow, deployment delays
**First seen at:** Data mesh implementations with Nessie

### Symptoms
```
- Branch merge fails: "Conflict: table modified on both branches"
- Feature branches diverge significantly (merge becomes complex)
- Team blocked on merging their branch to main
- No automatic conflict resolution for overlapping changes
```

### Root Cause
```
Nessie Git-like model:

  main:     ────A────B────C────D
                 \              ↑ merge conflict!
  feature:   ────A────E────F──↗
  
  If main:B modified table T and feature:E also modified table T:
    → Conflict on merge (can't auto-resolve)
    
  Unlike Git (text merge), Iceberg table changes aren't "mergeable":
    - main added files [X, Y] to table T
    - feature added files [Z] and deleted files [X] from table T
    → Conflict: main depends on X, feature deleted X
    
  Resolution requires manual decision (which version to keep)
```

### Permanent Fix
```
1. Short-lived branches (merge frequently):
   - Feature branches: max 1 day before merge
   - Longer divergence = more conflicts
   
2. Table-level ownership:
   - Team A owns tables [T1, T2] → only modifies these on their branch
   - Team B owns tables [T3, T4] → no overlap → no conflict
   
3. Read-only access to shared tables on branches:
   - Branch only modifies team-owned tables
   - Reads shared tables from main (live reference)
   
4. Conflict resolution workflow:
   - Detect conflict early (CI check on every commit)
   - Rebase frequently (like git rebase)
   - When conflict: review + manual resolution
```

---

## Issue #43: DynamoDB Lock Table Throttling (Glue + DynamoDB Lock)

**Severity:** P1 - High
**Frequency:** At 100+ concurrent commits/minute
**Affected Components:** All Iceberg commits via Glue catalog
**First seen at:** Large Glue catalog deployments with DynamoDB locking

### Symptoms
```
- ProvisionedThroughputExceededException from DynamoDB
- Commits randomly timeout (5-10 seconds instead of <1 second)
- "Unable to acquire lock" errors intermittently
- DynamoDB throttling metrics spike during pipeline hours
- Lock table read/write capacity consumed by Iceberg operations
```

### Root Cause
```
Iceberg uses DynamoDB as distributed lock for Glue catalog:

  Each commit:
    1. PUT item to lock table (acquire lock)
    2. GET current metadata from Glue
    3. PUT new metadata to S3
    4. UPDATE Glue table entry
    5. DELETE item from lock table (release lock)
    
  = 2 DynamoDB operations per commit minimum
  
  With 1000 commits/minute across all tables:
    = 2000 DynamoDB operations/minute
    
  DynamoDB provisioned capacity: often set low (50 WCU)
  = 50 writes/second = 3000/minute (barely enough)
  
  Add retries: each conflict = 2 more DynamoDB ops
  Add lock expiry checks: periodic scans
  
  Result: easily exceeds provisioned capacity → throttled
```

### Permanent Fix
```
1. Use DynamoDB on-demand pricing (no capacity limits):
   - aws dynamodb update-table --table-name iceberg-lock-table --billing-mode PAY_PER_REQUEST
   
2. Or increase provisioned capacity:
   - aws dynamodb update-table --table-name iceberg-lock-table \
       --provisioned-throughput ReadCapacityUnits=500,WriteCapacityUnits=500

3. Use lock table per high-traffic table (isolate hot tables)

4. Consider removing DynamoDB lock (use S3 conditional writes instead):
   - Iceberg 1.4+ supports S3 conditional PUT for atomic commits
   - No external lock table needed
   - Lower latency, no throttling
```

```properties
# Use S3 atomic rename (if available) instead of DynamoDB lock
spark.sql.catalog.prod.io-impl = org.apache.iceberg.aws.s3.S3FileIO
spark.sql.catalog.prod.lock.table = my-lock-table  # DynamoDB
# OR for newer Iceberg:
spark.sql.catalog.prod.s3.use-conditional-writes = true  # No lock needed
```

---

## Issue #44: Split-Brain After Network Partition (Multi-Region)

**Severity:** P0 - Critical
**Frequency:** During network partition between regions
**Affected Components:** Data consistency, potential data loss
**First seen at:** Multi-region active-active deployments

### Symptoms
```
- Region A and Region B both successfully commit to "same" table
- After partition heals: two divergent metadata chains
- Catalog shows different metadata locations in different regions
- Queries return different results depending on which region serves them
- Cannot determine which region has "correct" data
```

### Root Cause
```
Multi-region active-active with S3 Cross-Region Replication:

  Region A: Catalog A → metadata in s3://bucket-us/
  Region B: Catalog B → metadata in s3://bucket-eu/ (replica)
  
  Normal: All writes go to Region A, replicate to B (active-passive)
  
  During network partition:
    Region A: commits v10 to s3://bucket-us/
    Region B: doesn't see v10 (replication delayed/broken)
    Region B: commits v10 to s3://bucket-eu/ (DIFFERENT v10!)
    
  After partition heals:
    s3://bucket-us/ has v10(A)
    s3://bucket-eu/ has v10(B)
    CRR tries to replicate but conflicts (same key, different content)
    
  Result: split-brain with two divergent table histories
```

### Permanent Fix
```
1. Active-PASSIVE pattern (recommended):
   - All writes go to primary region
   - Secondary is read-only (for DR/low-latency reads)
   - No split-brain possible
   
2. If active-active needed: partition table by region
   - Region A owns partitions for US data
   - Region B owns partitions for EU data
   - No overlapping writes → no conflict
   
3. Single catalog (Nessie/REST Catalog) as source of truth:
   - Catalog deployed in one region
   - All commits go through single catalog
   - Data can be in multiple regions (catalog is metadata-only)
   
4. Conflict resolution protocol:
   - On partition heal: compare snapshots
   - Latest timestamp wins (or: primary region wins)
   - Merge divergent changes (append-only tables can be unioned)
```

---

## Issue #45: Idempotency Failure on Retry (Duplicate Data After Job Restart)

**Severity:** P1 - High
**Frequency:** After any job restart/retry
**Affected Components:** Data quality (duplicates)
**First seen at:** Every team at scale eventually hits this

### Symptoms
```
- Row counts higher than expected after pipeline retry
- Duplicates detectable by primary key (same event_id, multiple rows)
- Only happens on days with pipeline failures + retries
- Batch overwrite is safe (idempotent), but append is not
- Streaming exactly-once breaks on checkpoint restore
```

### Root Cause
```
Append operations are NOT idempotent:

  Run 1: Process batch → Append 1M rows → Commit succeeds
  Run 2 (retry): Process SAME batch → Append 1M rows → Commit succeeds
  Result: 2M rows (1M duplicates)
  
  Why retries happen:
    - Airflow retries on timeout (commit succeeded but task timed out)
    - Spark job OOM (some tasks committed, others didn't)
    - Network blip after S3 write but before catalog update
    - Manual re-run by operator (didn't know previous run succeeded)
    
  Overwrite is idempotent (same result regardless of how many times):
    Run 1: Overwrite partition = [row set A]
    Run 2: Overwrite partition = [row set A]
    Result: [row set A] (correct)
    
  But overwrite has its own problems (Issue #32)
```

### Permanent Fix
```python
# Strategy 1: Write-audit-publish pattern
def idempotent_write(spark, df, table_name, batch_id):
    """Write only if batch_id not already committed."""
    
    # Check if this batch already committed
    existing = spark.sql(f"""
        SELECT COUNT(*) as cnt FROM prod.{table_name} 
        WHERE _batch_id = '{batch_id}'
    """).first().cnt
    
    if existing > 0:
        logger.info(f"Batch {batch_id} already committed, skipping")
        return
    
    # Add batch_id to data for dedup tracking
    df_with_batch = df.withColumn("_batch_id", lit(batch_id))
    df_with_batch.writeTo(f"prod.{table_name}").append()

# Strategy 2: MERGE instead of append (dedup on write)
def idempotent_merge(spark, df, table_name, key_column):
    """MERGE handles duplicates automatically."""
    df.createOrReplaceTempView("incoming")
    spark.sql(f"""
        MERGE INTO prod.{table_name} t
        USING incoming s
        ON t.{key_column} = s.{key_column}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

# Strategy 3: Overwrite partition (inherently idempotent)
def idempotent_overwrite(spark, df, table_name):
    df.writeTo(f"prod.{table_name}").overwritePartitions()
```

---

## Summary: Concurrency & Write Conflict Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 31 | Commit conflict storm | P0 | Single writer + partition ownership |
| 32 | Lost updates (last writer wins) | P0 | MERGE instead of overwrite |
| 33 | Deadlock: compaction vs schema evolution | P1 | Serialize operations + lock |
| 34 | Concurrent MERGE corrupts data | P0 | Non-overlapping key partitioning |
| 35 | Partition-level overwrite conflicts | P1 | Strict partition ownership |
| 36 | Retry exhaustion | P1 | Reduce concurrent writers |
| 37 | Read-your-own-write failure | P1 | REFRESH TABLE after write |
| 38 | Table-level lock escalation (HMS) | P1 | Migrate to optimistic catalog |
| 39 | Cross-table atomicity missing | P2 | Nessie branches or compensation |
| 40 | Flink exactly-once WAL conflict | P1 | Dedup key + upsert mode |
| 41 | Concurrent expire corrupts metadata | P0 | Distributed lock for maintenance |
| 42 | Nessie branch merge conflicts | P2 | Short-lived branches + ownership |
| 43 | DynamoDB lock throttling | P1 | On-demand + conditional S3 writes |
| 44 | Split-brain after network partition | P0 | Active-passive + single catalog |
| 45 | Idempotency failure on retry | P1 | MERGE/overwrite + batch_id tracking |
