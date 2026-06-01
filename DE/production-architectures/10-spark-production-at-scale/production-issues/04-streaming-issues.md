# Category 4: Streaming Issues (Issues 31-40)

> Structured Streaming failures are insidious - they may not crash immediately but silently fall behind, lose data, or corrupt state.

---

## Issue #31: Streaming Query Falling Behind (Processing Time > Trigger Interval)

**Frequency**: Very High  
**Severity**: Critical - growing latency, eventual OOM/data loss  
**Spark Component**: MicroBatchExecution, StreamExecution

### Symptoms
```
# StreamingQueryProgress shows:
"inputRowsPerSecond": 500000,
"processedRowsPerSecond": 200000,  ← Processing < Input!
# Batch duration growing: 30s → 60s → 120s → 300s
# Kafka consumer lag growing monotonically
# Eventually: OOM from accumulated state or Kafka offset expiry
```

### Root Cause
- Insufficient cluster resources for data volume
- Query too complex for micro-batch latency requirements
- State store growing (more lookups per batch)
- Source spike (Black Friday, viral event)
- Upstream producer suddenly sends backlog

### Solution
```python
# 1. Scale horizontally (more executors)
spark.conf.set("spark.dynamicAllocation.enabled", "true")
spark.conf.set("spark.dynamicAllocation.maxExecutors", "200")

# 2. Rate limiting to prevent overwhelming during spikes
spark.conf.set("spark.streaming.kafka.maxRatePerPartition", "50000")
# For Structured Streaming:
df = spark.readStream.format("kafka") \
    .option("maxOffsetsPerTrigger", "10000000")  # Cap per batch
    .option("minOffsetsPerTrigger", "1000000")   # Minimum to process

# 3. Optimize query - push filters early, reduce state
# BAD: filter after stateful operation
stream.groupBy("key").count().filter("count > 100")

# GOOD: filter before stateful operation
stream.filter(F.col("value") > 0).groupBy("key").count()

# 4. Use trigger.availableNow() for catch-up batches
query = df.writeStream \
    .trigger(availableNow=True) \  # Process all available, then stop
    .start()
# Run this as a catch-up job, then switch back to continuous

# 5. Increase trigger interval to process larger batches (more efficient)
query = df.writeStream \
    .trigger(processingTime="30 seconds") \  # Instead of 10s
    .start()
# Larger batches amortize overhead better

# 6. Monitor and alert
# Alert: processedRowsPerSecond < inputRowsPerSecond for > 10 minutes
```

---

## Issue #32: State Store Growing Unbounded (Memory Leak)

**Frequency**: High  
**Severity**: Critical - slow degradation → OOM  
**Spark Component**: StateStore, HDFSBackedStateStore, RocksDBStateStore

### Symptoms
```
# From streaming progress:
"stateOperators": [{
    "numRowsTotal": 500000000,  ← Growing every batch!
    "numRowsUpdated": 100000,
    "memoryUsedBytes": 85899345920  ← 80GB state!
}]
# Batch duration increasing linearly with time
# Eventually: executor OOM or checkpoint takes longer than trigger interval
```

### Root Cause
- No watermark set → Spark keeps ALL state forever
- Watermark set but too generous (e.g., "7 days")
- Stream-stream join state never expires (waiting for match that won't come)
- flatMapGroupsWithState not implementing timeout/cleanup

### Solution
```python
# 1. ALWAYS set watermark for stateful operations
df_with_wm = df.withWatermark("event_time", "1 hour")
# Spark drops state older than watermark automatically

# 2. For stream-stream joins, set watermarks on BOTH sides
left_wm = left.withWatermark("left_time", "2 hours")
right_wm = right.withWatermark("right_time", "3 hours")

# Time-bounded join (state cleaned after window)
result = left_wm.join(right_wm, 
    (left_wm.key == right_wm.key) &
    (left_wm.left_time.between(
        right_wm.right_time - F.expr("INTERVAL 1 HOUR"),
        right_wm.right_time + F.expr("INTERVAL 1 HOUR")
    )),
    "inner"
)

# 3. For mapGroupsWithState, implement timeout
from pyspark.sql.streaming import GroupStateTimeout

def update_state(key, values, state):
    if state.hasTimedOut:
        # Emit final result and remove state
        old_state = state.get
        state.remove()
        return [old_state]
    
    # Set timeout - state auto-expires after inactivity
    state.setTimeoutDuration("30 minutes")
    # Update state...
    return []

# 4. Use RocksDB state backend (handles larger state than heap)
spark.conf.set("spark.sql.streaming.stateStore.providerClass",
    "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider")
# RocksDB uses disk-backed storage, only active keys in memory

# 5. Monitor state growth rate
# Alert if: numRowsTotal grows > 5% per hour without matching input growth
```

---

## Issue #33: Checkpoint Corruption After Schema Change

**Frequency**: Medium  
**Severity**: Critical - query cannot restart  
**Spark Component**: OffsetLog, CommitLog, StateStore

### Symptoms
```
org.apache.spark.sql.AnalysisException: 
  Detected schema change in streaming query from checkpoint:
  Expected: struct<id:string, value:int, ts:timestamp>
  Actual: struct<id:string, value:long, ts:timestamp, new_col:string>

# OR
java.lang.IllegalStateException: 
  Cannot recover operator state after changing number of stateful operators
```

### Root Cause
- Source schema evolved (new column, type change)
- Query logic changed (added/removed groupBy, join)
- State schema incompatible with new query plan
- Upstream Kafka topic had schema change

### Solution
```python
# 1. For additive schema changes (new nullable columns): use schema merge
df = spark.readStream.format("kafka") \
    .option("failOnDataLoss", "false") \
    .option("kafka.schema.registry.url", schema_registry_url) \
    .load()
# Schema Registry handles forward-compatible changes

# 2. For breaking changes: start fresh with new checkpoint
# Option A: New checkpoint location (loses state but safe)
query = df.writeStream \
    .option("checkpointLocation", "s3://checkpoints/query_v2/") \  # New path
    .start()

# Option B: Controlled migration
# 1. Stop old query gracefully
# 2. Read final committed offsets from old checkpoint
# 3. Start new query from those offsets with new checkpoint
new_query = df.writeStream \
    .option("checkpointLocation", "s3://checkpoints/query_v2/") \
    .option("startingOffsets", '{"topic":{"0":12345,"1":12346}}') \
    .start()

# 3. Schema evolution strategy for streaming:
# - Use Avro/Protobuf with schema registry (forward + backward compatible)
# - Add columns as NULLABLE only
# - Never remove or rename columns
# - Version your checkpoint paths: /checkpoints/pipeline_v3/
# - Keep old checkpoints for rollback window (7 days)

# 4. For state schema changes, there's NO in-place migration
# You MUST start with a fresh checkpoint
# Design state to be forward-compatible:
# - Store state as serialized bytes (JSON/Avro), decode in application logic
# - Version state format: {"version": 2, "data": {...}}
```

---

## Issue #34: Exactly-Once Semantics Broken (Duplicates in Sink)

**Frequency**: Medium-High  
**Severity**: Critical - data correctness  
**Spark Component**: StreamExecution, Sink, OffsetLog

### Symptoms
```
# Downstream table has duplicate records after streaming restart
# Same event processed twice: once before crash, once after recovery
# Counts don't match between source and sink
# Financial amounts doubled for some transactions
```

### Root Cause
- Non-idempotent sink (append-only without dedup key)
- Crash between writing output and committing offset
- Sink doesn't support transactional writes
- Kafka rebalance causing duplicate consumption
- foreachBatch not implementing idempotent writes

### Solution
```python
# 1. Use Iceberg/Delta sinks (built-in exactly-once with transactions)
query = df.writeStream \
    .format("iceberg") \
    .outputMode("append") \
    .option("checkpointLocation", "s3://cp/") \
    .toTable("catalog.db.events")
# Iceberg: write is atomic, committed only when Spark commits offset

# 2. For foreachBatch: implement idempotent writes
def idempotent_write(batch_df, batch_id):
    # Use batch_id as deduplication key
    batch_df.createOrReplaceTempView("batch")
    
    spark.sql(f"""
        MERGE INTO target t
        USING batch b
        ON t.event_id = b.event_id
        WHEN NOT MATCHED THEN INSERT *
    """)
    # MERGE is idempotent: re-processing same batch_id won't create duplicates

query = df.writeStream.foreachBatch(idempotent_write).start()

# 3. For Kafka sink: use idempotent producer
df.writeStream \
    .format("kafka") \
    .option("kafka.enable.idempotence", "true") \
    .option("kafka.acks", "all") \
    .start()

# 4. For JDBC sink: use upsert (INSERT ON CONFLICT)
def upsert_to_postgres(batch_df, batch_id):
    batch_df.write \
        .format("jdbc") \
        .option("dbtable", "target_table") \
        .option("isolationLevel", "READ_COMMITTED") \
        .mode("append") \  # Use custom upsert logic
        .save()
    # Better: use raw JDBC with ON CONFLICT DO UPDATE

# 5. Add event-level deduplication key
df_deduped = df.dropDuplicatesWithinWatermark("event_id", "10 minutes")
```

---

## Issue #35: Kafka Offset Out of Range (Data Loss)

**Frequency**: Medium  
**Severity**: Critical - permanent data loss  
**Spark Component**: KafkaSource, KafkaOffsetReader

### Symptoms
```
org.apache.kafka.clients.consumer.OffsetOutOfRangeException:
  Offsets out of range with no configured reset policy for partitions: 
  {topic-0=145000000}
# OR
org.apache.spark.sql.AnalysisException:
  Some offsets are behind the earliest available offset
# Streaming job was stopped for too long, Kafka deleted old data
```

### Root Cause
- Streaming job was down longer than Kafka retention period
- Kafka topic retention reduced unexpectedly
- Consumer group offsets expired
- Checkpoint points to offsets that no longer exist

### Solution
```python
# 1. Set fail-safe policy (production: "earliest" to avoid data loss)
df = spark.readStream.format("kafka") \
    .option("failOnDataLoss", "false") \  # Don't crash, skip missing
    .option("startingOffsets", "earliest") \  # Fall back to earliest available
    .load()

# 2. BETTER: Alert and require manual decision
df = spark.readStream.format("kafka") \
    .option("failOnDataLoss", "true") \   # Crash so we know about it
    .load()
# Then: decide to skip or replay from external source

# 3. Prevention: increase Kafka retention
# Kafka topic config:
# retention.ms=604800000  (7 days)
# retention.bytes=-1  (unlimited by size)
# Ensure: max_expected_downtime < retention_period

# 4. Prevention: monitor consumer lag
# Alert if lag > 50% of retention
# lag_seconds > retention_seconds * 0.5 → CRITICAL

# 5. Recovery: start from latest (accept gap) or replay from data lake
# Option A: Accept data loss, start from latest
df = spark.readStream.format("kafka") \
    .option("startingOffsets", "latest") \
    .option("checkpointLocation", "s3://cp/new_checkpoint/") \
    .load()

# Option B: Replay gap from data lake backup
# 1. Find gap: checkpoint offset vs earliest available Kafka offset
# 2. Read gap from S3 (if you have a parallel batch pipeline)
# 3. Write gap to sink, then resume streaming
```

---

## Issue #36: Watermark Dropping Valid Data (Late Data Loss)

**Frequency**: Medium  
**Severity**: High - silent data loss  
**Spark Component**: WatermarkTracker, EventTimeWatermarkExec

### Symptoms
```
# Events arriving 2 hours late are silently dropped
# No error, no warning - data just disappears
# Aggregation results undercount during network delays/retries
# Reconciliation shows: streaming result < batch result by 2-5%
```

### Root Cause
- Watermark too aggressive (e.g., "10 minutes" but data arrives 2 hours late)
- Mobile/IoT devices buffer events offline, send in bulk later
- Retry storms after outage create burst of late data
- Clock skew between producers and event timestamps

### Solution
```python
# 1. Set watermark based on ACTUAL late arrival distribution
# Analyze: what % of data arrives how late?
df.groupBy(
    F.floor((F.current_timestamp().cast("long") - F.col("event_time").cast("long")) / 3600)
    .alias("hours_late")
).count().orderBy("hours_late").show(50)
# If 99.9% arrives within 4 hours, set watermark to 4 hours

df_wm = df.withWatermark("event_time", "4 hours")

# 2. Accept the tradeoff: more watermark = more state = more memory
# Watermark: 10 min → keeps 10 min of state (fast, might lose data)
# Watermark: 24 hours → keeps 24 hours of state (safe, uses more memory)

# 3. Late data routing: capture dropped events
# Spark doesn't natively route dropped events, but you can:
# Option A: Run TWO queries
# Query 1: Streaming with tight watermark (real-time, approximate)
# Query 2: Batch hourly reconciliation (complete, authoritative)

# Option B: Use Append mode with window
windowed = df_wm.groupBy(
    F.window("event_time", "1 hour"),
    "key"
).agg(F.sum("value"))
# In append mode: emits result ONLY after watermark passes window end
# This guarantees completeness within watermark threshold

# 4. For critical data: use outputMode("update") + idempotent sink
# Update mode re-emits updated aggregations (handles late data until watermark)
query = windowed.writeStream \
    .outputMode("update") \
    .foreachBatch(upsert_to_sink) \
    .start()

# 5. Monitor late data ratio
# Track: (events_beyond_watermark / total_events) per batch
# Alert if late_ratio > 1% (watermark too aggressive)
```

---

## Issue #37: Stream-Stream Join Never Emitting Results

**Frequency**: Medium  
**Severity**: High - query appears stuck  
**Spark Component**: StreamingSymmetricHashJoinExec

### Symptoms
```
# Two streams joined, but output is always empty
# Both streams have data flowing, but join produces nothing
# Progress shows rows read on both sides but 0 rows output
# Works in batch mode but not streaming
```

### Root Cause
- Watermarks not aligned (one stream's watermark is far ahead)
- Time range condition too narrow for event arrival patterns
- Inner join: one side's events arrive much later than the other
- Event time fields have different timezone interpretations
- Left stream events arrive AFTER right stream's watermark passes

### Solution
```python
# 1. Set watermarks on BOTH streams (required for stream-stream joins)
orders = orders_stream.withWatermark("order_time", "2 hours")
payments = payments_stream.withWatermark("payment_time", "3 hours")

# 2. Use time range condition that accounts for real-world delays
result = orders.join(
    payments,
    (orders.order_id == payments.order_id) &
    # Payment can arrive up to 4 hours after order
    (payments.payment_time.between(
        orders.order_time,
        orders.order_time + F.expr("INTERVAL 4 HOURS")
    )),
    "inner"
)

# 3. Debug: check watermark advancement
# If one stream has no data, its watermark doesn't advance
# This blocks the other stream from emitting!
# Solution: ensure both streams always have data (even heartbeats)

# 4. Use left outer join to see unmatched events
result = orders.join(payments, ..., "leftOuter")
# Now you can see orders without matching payments
# After watermark passes, unmatched orders emit with null payment columns

# 5. Verify timestamps are comparable
# BAD: orders use UTC, payments use local time → never match time condition!
# GOOD: Normalize all to UTC:
orders = orders.withColumn("order_time_utc", F.to_utc_timestamp("order_time", "US/Pacific"))
payments = payments.withColumn("payment_time_utc", F.to_utc_timestamp("payment_time", "US/Eastern"))
```

---

## Issue #38: Streaming Job Restart Takes Too Long (State Reload)

**Frequency**: Medium  
**Severity**: Medium-High - extended downtime during restart  
**Spark Component**: StateStore, RocksDBStateStore, Checkpoint Recovery

### Symptoms
```
# After restart:
"Restoring state from checkpoint..." → takes 45 minutes!
# 100GB state being reloaded from S3 checkpoint
# First batch doesn't process until state fully loaded
# During reload: no data processing, lag growing
```

### Root Cause
- Large state stored in HDFS/S3 checkpoint (slow I/O)
- HDFSBackedStateStore reloads full state on restart
- State accumulated over weeks/months
- Checkpoint on slow storage (S3 vs local NVMe)

### Solution
```python
# 1. Use RocksDB state store (incremental checkpointing)
spark.conf.set("spark.sql.streaming.stateStore.providerClass",
    "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider")
# RocksDB: only sends DELTA to checkpoint (incremental)
# Recovery: loads last full snapshot + recent deltas

# 2. Configure RocksDB for fast recovery
spark.conf.set("spark.sql.streaming.stateStore.rocksdb.formatVersion", "5")
spark.conf.set("spark.sql.streaming.stateStore.rocksdb.trackTotalNumberOfRows", "true")
spark.conf.set("spark.sql.streaming.stateStore.rocksdb.compactOnCommit", "false")  # Faster commits

# 3. Reduce state size (faster checkpoint, faster recovery)
# Use shorter watermarks (less state to persist)
# Expire old state aggressively (TTL)
# Use approximate data structures (HyperLogLog vs exact distinct)

# 4. Use local SSD for state store (faster than S3)
spark.conf.set("spark.sql.streaming.stateStore.localDir", "/mnt/nvme/state")
# Combined with S3 checkpoints for durability

# 5. Graceful shutdown (enables faster restart)
# Stop with: query.stop()  (NOT kill -9)
# This commits final checkpoint cleanly
# Next restart doesn't need to redo last batch

# 6. Parallel state restore (Spark 3.5+)
spark.conf.set("spark.sql.streaming.stateStore.restore.parallelism", "8")
```

---

## Issue #39: Trigger.Once() / AvailableNow Doesn't Complete

**Frequency**: Medium  
**Severity**: Medium - job runs forever instead of stopping  
**Spark Component**: StreamExecution, ProcessingTimeTrigger

### Symptoms
```
# trigger(once=True) supposed to process all available data and stop
# But job runs indefinitely
# OR processes only first batch and stops (missing data)
# OR keeps finding "new" data every micro-batch
```

### Root Cause
- Source continuously produces data (job never "catches up")
- File source: new files arriving during processing
- Kafka: `maxOffsetsPerTrigger` limits per-batch, trigger.once processes one batch
- Rate source for testing: infinite by design

### Solution
```python
# 1. Use trigger.availableNow (Spark 3.3+) - processes all CURRENTLY available
query = df.writeStream \
    .trigger(availableNow=True) \  # Process what's there NOW, then stop
    .option("checkpointLocation", "s3://cp/") \
    .start()
query.awaitTermination()
# Unlike once=True, this processes MULTIPLE batches until caught up

# 2. For trigger.once with Kafka, remove maxOffsetsPerTrigger
# BAD: trigger.once + maxOffsetsPerTrigger → processes only one limited batch!
# GOOD:
query = df.readStream.format("kafka") \
    .option("subscribe", "topic") \
    .load() \
    .writeStream \
    .trigger(once=True) \  # Process ALL available offsets in one batch
    .start()

# 3. For file source: snapshot available files at start
# trigger.once/availableNow snapshots the file list at query start
# New files arriving during processing are picked up on NEXT run

# 4. Set timeout as safety net
query.awaitTermination(timeout=3600000)  # 1 hour max
if query.isActive:
    query.stop()  # Force stop if still running
    raise TimeoutError("Streaming job didn't complete in 1 hour")

# 5. For scheduled micro-batch (e.g., every 5 min via Airflow):
# Use trigger(availableNow=True) in a scheduled job
# This gives exactly-once batch semantics with streaming simplicity
```

---

## Issue #40: Streaming Metrics Reporting Incorrect Values

**Frequency**: Medium  
**Severity**: Medium - misleading dashboards  
**Spark Component**: StreamingQueryListener, ProgressReporter

### Symptoms
```
# Dashboard shows processedRowsPerSecond = 1M/s
# But actual throughput is 100K/s
# inputRowsPerSecond fluctuates wildly between batches
# numInputRows doesn't match Kafka consumer lag reduction
```

### Root Cause
- `processedRowsPerSecond` = numInputRows / triggerExecution time
- If trigger interval > processing time, rate looks artificially low
- If batch has backlog, rate looks artificially high (one big batch)
- Metrics report per-batch, not smoothed averages
- Multiple sources: metrics summed incorrectly

### Solution
```python
# 1. Use smoothed metrics (rolling average over N batches)
class MetricsTracker:
    def __init__(self, window=10):
        self.history = []
        self.window = window
    
    def add_progress(self, progress):
        self.history.append({
            "input_rate": progress.inputRowsPerSecond,
            "process_rate": progress.processedRowsPerSecond,
            "batch_duration": progress.batchDuration,
            "num_rows": progress.numInputRows,
            "timestamp": progress.timestamp,
        })
        if len(self.history) > self.window:
            self.history.pop(0)
    
    def smoothed_rate(self):
        if not self.history:
            return 0
        total_rows = sum(h["num_rows"] for h in self.history)
        total_time_s = sum(h["batch_duration"] / 1000 for h in self.history)
        return total_rows / total_time_s if total_time_s > 0 else 0

# 2. Use custom StreamingQueryListener for accurate metrics
class AccurateMetricsListener(StreamingQueryListener):
    def onQueryProgress(self, event):
        p = event.progress
        # True throughput = rows / wall_clock_time (not just processing)
        # Include trigger interval idle time
        actual_throughput = p.numInputRows / (p.triggerExecution / 1000)
        publish_metric("spark_streaming_actual_throughput", actual_throughput)
        
        # Lag = distance from latest offset
        for source in p.sources:
            if hasattr(source, 'endOffset') and hasattr(source, 'latestOffset'):
                lag = source.latestOffset - source.endOffset  # Simplified
                publish_metric("spark_streaming_lag", lag)

# 3. Monitor the RIGHT metrics for alerting
# DON'T alert on: processedRowsPerSecond (noisy)
# DO alert on:
#   - Kafka consumer lag (monotonically increasing = falling behind)
#   - batch_duration > trigger_interval (can't keep up)
#   - numInputRows = 0 for > 5 minutes (source problem)
#   - state store size (growing = leak)
```

---

## Summary: Streaming Issue Decision Tree

```
Streaming problem
├── Query falling behind?
│   ├── Processing < Input rate → Issue #31 (scale up or rate limit)
│   ├── State growing unbounded → Issue #32 (add watermark/TTL)
│   └── Restart takes too long → Issue #38 (use RocksDB, reduce state)
├── Data correctness issue?
│   ├── Duplicates in sink → Issue #34 (idempotent writes)
│   ├── Missing data (gap) → Issue #35 (Kafka offset expired)
│   ├── Undercounting events → Issue #36 (watermark too aggressive)
│   └── Join produces nothing → Issue #37 (time condition/watermark alignment)
├── Query won't start/stop?
│   ├── Schema change → Issue #33 (new checkpoint needed)
│   └── trigger.once won't complete → Issue #39 (availableNow)
└── Monitoring inaccurate?
    └── Metrics misleading → Issue #40 (use smoothed/custom metrics)
```
