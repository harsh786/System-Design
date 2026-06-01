# Streaming, CDC & Real-Time Issues (#73-86)

Issues related to streaming writes (Flink/Spark Streaming), CDC pipelines (Debezium),
real-time data freshness, and exactly-once guarantees with Iceberg.

---

## Issue #73: Flink Checkpoint Timeout Causes Data Loss

**Severity:** P0 - Critical
**Frequency:** Under backpressure or during GC pauses
**Affected Components:** Streaming ingestion, exactly-once guarantee
**First seen at:** Flink jobs under sustained high load

### Symptoms
```
- Flink checkpoint fails: "Checkpoint expired before completing"
- Job restarts from last successful checkpoint (gap in data)
- Iceberg table missing events for 5-10 minute windows
- Flink UI shows increasing checkpoint duration trend
- Eventually: checkpoint barrier alignment timeout
```

### Root Cause
```
Flink exactly-once with Iceberg:
  Checkpoint = Iceberg commit (atomic)
  
  If checkpoint fails:
    - Data written to S3 (Parquet files created)
    - But Iceberg commit NOT made (no snapshot)
    - Orphan files created on S3
    - Flink rolls back to last successful checkpoint
    - Re-processes events from Kafka (at-least-once for that window)
    
  Checkpoint fails when:
    - Total checkpoint time > timeout (default 10 min)
    - Barrier alignment takes too long (backpressure)
    - S3 write is slow (throttling)
    - GC pause during checkpoint
    - Iceberg commit conflicts (retry exhausts timeout)
    
  Data "loss" (actually never committed):
    Events between failed checkpoint and next successful one
    are reprocessed → no actual loss, but DELAY of 10-20 minutes
    
  True data loss scenario:
    Kafka retention < checkpoint interval + recovery time
    → Messages expire from Kafka before re-read → REAL loss
```

### Immediate Fix
```yaml
# Increase checkpoint timeout
execution.checkpointing.timeout: 30min
execution.checkpointing.min-pause: 30s
execution.checkpointing.max-concurrent-checkpoints: 1

# Enable unaligned checkpoints (don't wait for barrier alignment)
execution.checkpointing.unaligned.enabled: true
execution.checkpointing.aligned-checkpoint-timeout: 60s
```

### Permanent Fix
```java
// Flink job configuration for reliable Iceberg writes
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

// Checkpoint configuration
env.enableCheckpointing(300_000); // 5 minutes
env.getCheckpointConfig().setCheckpointTimeout(1_800_000); // 30 min timeout
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(60_000); // 1 min between
env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);
env.getCheckpointConfig().enableUnalignedCheckpoints();
env.getCheckpointConfig().setExternalizedCheckpointCleanup(
    CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);

// State backend (for large state)
env.setStateBackend(new EmbeddedRocksDBStateBackend());
env.getCheckpointConfig().setCheckpointStorage("s3://checkpoints/flink/");
```

```
Prevention:
1. Kafka retention >> checkpoint interval (retain 7 days minimum)
2. Use unaligned checkpoints (faster completion under backpressure)
3. Monitor checkpoint duration trend (alert if increasing)
4. Size Flink cluster for 2x expected load (headroom)
5. Increase checkpoint interval if too frequent (reduce commit overhead)
```

---

## Issue #74: CDC Event Ordering Violation (Out-of-Order Updates)

**Severity:** P1 - High
**Frequency:** When CDC topic has multiple partitions
**Affected Components:** Data correctness (stale updates applied last)
**First seen at:** Debezium CDC with Kafka partitioning

### Symptoms
```
- Iceberg table shows stale values for some records
- Example: user status should be "active" but shows "pending" (old state)
- Ordering correct within Kafka partition but wrong across partitions
- Rebalancing causes ordering violations
- Final state depends on processing order (non-deterministic)
```

### Root Cause
```
Kafka guarantees ordering only within a SINGLE partition:

  Debezium captures changes:
    T1: user_123 → status = 'pending' (INSERT)
    T2: user_123 → status = 'active' (UPDATE)
    T3: user_123 → status = 'suspended' (UPDATE)
    
  If Kafka topic has partitions by key hash:
    All user_123 events → same partition → ORDERED correctly
    
  But if Kafka rebalances or key changes:
    T1: user_123 → partition 0 → status = 'pending'
    T2: user_123 → partition 1 → status = 'active' (different partition!)
    
    Consumer reads partition 1 first → applies 'active'
    Consumer reads partition 0 → applies 'pending' (STALE, overwrite!)
    Final state: 'pending' ← WRONG (should be 'active')
    
  Also: Flink parallelism > Kafka partitions → event interleaving
```

### Permanent Fix
```java
// Strategy 1: Key-based partitioning in Kafka (ensures ordering)
// Debezium config:
// transforms.route.type=io.debezium.transforms.ByLogicalTableRouter
// key.converter.schemas.enable=true
// → Events for same primary key always in same partition

// Strategy 2: Event-time ordering in Flink
DataStream<RowData> orderedStream = cdcStream
    .keyBy(row -> row.getString(0))  // Key by primary key
    .process(new OrderedCDCProcessor());

// OrderedCDCProcessor:
// - Buffers events per key
// - Orders by event timestamp (from Debezium)
// - Emits in correct order
// - Handles late arrivals (watermark-based)

public class OrderedCDCProcessor extends KeyedProcessFunction<String, CdcEvent, RowData> {
    private ValueState<Long> lastEventTimestamp;
    
    @Override
    public void processElement(CdcEvent event, Context ctx, Collector<RowData> out) {
        long eventTs = event.getTimestamp();
        Long lastTs = lastEventTimestamp.value();
        
        if (lastTs == null || eventTs >= lastTs) {
            // Normal order: apply event
            lastEventTimestamp.update(eventTs);
            out.collect(event.toRowData());
        } else {
            // Out of order: log and skip (or buffer and reorder)
            LOG.warn("Out-of-order event for key={}, eventTs={}, lastTs={}",
                ctx.getCurrentKey(), eventTs, lastTs);
            // Option A: Skip stale event
            // Option B: Re-apply with full state reconstruction
        }
    }
}
```

### Prevention
```
1. ALWAYS partition Kafka CDC topic by primary key
2. Set Debezium transforms.unwrap.type for clean event ordering
3. Use Flink keyBy(primary_key) before Iceberg sink
4. Add event_timestamp to CDC events and use for ordering
5. Monitor ordering violations (alert on out-of-order events)
```

---

## Issue #75: Streaming Data Freshness SLA Breach (Commit Latency)

**Severity:** P1 - High
**Frequency:** When commit interval > freshness SLA
**Affected Components:** Real-time dashboards, downstream consumers
**First seen at:** When business requires <5 min data freshness

### Symptoms
```
- Data in Iceberg table is 15 minutes stale (SLA: 5 minutes)
- Dashboard shows data from 10-15 minutes ago
- Commit interval: 5 min + planning: 2 min + S3 write: 3 min = 10 min total latency
- Reducing checkpoint interval causes small file explosion
- Cannot achieve both freshness AND file size goals simultaneously
```

### Root Cause
```
Latency components in streaming → Iceberg pipeline:

  1. Kafka → Flink source latency: ~1 second
  2. Processing latency (transformations): ~2 seconds
  3. Buffer until checkpoint: checkpoint_interval / 2 average
     With 5 min interval: average 2.5 min waiting for checkpoint
  4. Checkpoint execution: 30-120 seconds
  5. Iceberg commit (S3 write + catalog update): 5-30 seconds
  6. Query engine metadata refresh: 0-60 seconds (cache TTL)
  
  Total: 1s + 2s + 150s + 60s + 15s + 30s = ~4.3 minutes minimum
  With 5 min checkpoint: ~5-7 minutes typical
  With issues: 10-15 minutes
  
  Tradeoff: shorter checkpoint = fresher data BUT more small files
    1 min checkpoint: 1.5 min freshness, 6000 files/hour (terrible for queries)
    5 min checkpoint: 5 min freshness, 1200 files/hour (manageable)
    15 min checkpoint: 12 min freshness, 400 files/hour (good file sizes)
```

### Permanent Fix
```
1. Hybrid approach: fast commits + async compaction
   - Commit every 1 minute (fresh data, small files)
   - Compaction runs every 5 minutes (merges small files)
   - Result: 1.5 min freshness + reasonable file sizes
   
2. Two-tier serving:
   - Tier 1 (real-time): Redis/Kafka Streams for <1 min freshness
   - Tier 2 (batch): Iceberg for analytical queries (5 min freshness OK)
   
3. Optimize commit latency:
   - Pre-create manifest files during processing
   - Fast catalog (low-latency Nessie/REST vs Glue)
   - S3 Express for metadata writes (lower latency)
```

```properties
# Aggressive freshness configuration
execution.checkpointing.interval = 60000  # 1 minute
write.target-file-size-bytes = 33554432   # 32MB (smaller target for speed)
write.distribution-mode = none            # Skip redistribution (faster)
```

---

## Issue #76: Debezium Schema Change Crashes Flink Job

**Severity:** P0 - Critical
**Frequency:** Whenever source database schema changes
**Affected Components:** Entire streaming pipeline
**First seen at:** After any DDL on source database

### Symptoms
```
- Flink job crashes: "Schema incompatible" or "Unknown field"
- Source DB ALTER TABLE → downstream pipeline dies within seconds
- Kafka messages switch from schema v1 to v2 mid-stream
- Iceberg MERGE fails: "Column 'new_column' not found in target"
- Pipeline down until manual intervention (schema alignment)
```

### Root Cause
```
Debezium captures schema changes from database:
  T0: Source has schema {id, name, email}
  T1: DBA runs: ALTER TABLE ADD COLUMN phone VARCHAR(20)
  T2: Debezium emits events with NEW schema {id, name, email, phone}
  T3: Flink deserializer expects OLD schema → CRASH
  
  Or: Schema Registry rejects new schema (compatibility violation)
  
  Or: Iceberg table doesn't have 'phone' column → MERGE fails
  
  Chain of failures:
    Source DDL → Debezium schema change event → Kafka schema registry 
    → Flink deserialization error → Job crash → Pipeline down
```

### Permanent Fix
```java
// Strategy 1: Schema-agnostic processing (handle any schema)
// Use GenericRecord / Map instead of typed POJO
FlinkKafkaConsumer<GenericRecord> consumer = new FlinkKafkaConsumer<>(
    "cdc.source.table",
    new AvroDeserializationSchema<>(GenericRecord.class),
    properties
);

// Dynamic schema handling in processor
public class SchemaEvolvingProcessor extends ProcessFunction<GenericRecord, RowData> {
    @Override
    public void processElement(GenericRecord record, Context ctx, Collector<RowData> out) {
        Schema currentSchema = record.getSchema();
        // Dynamically map fields that exist
        // Ignore new unknown fields (or add them dynamically)
        // Handle removed fields (use NULL)
    }
}
```

```python
# Strategy 2: Pre-evolve Iceberg schema before source DDL
# Coordination workflow:
# 1. Add column to Iceberg FIRST (accepts NULL)
# 2. Then ALTER source database
# 3. Debezium picks up new schema
# 4. Flink writes new column to Iceberg (column already exists)

def pre_evolve_iceberg_schema(table_name, new_column, data_type):
    """Add column to Iceberg before source database change."""
    spark.sql(f"ALTER TABLE {table_name} ADD COLUMN {new_column} {data_type}")
    # Now safe to ALTER source database
```

### Prevention
```
1. Schema evolution coordination:
   - Iceberg schema evolves FIRST (new column added, nullable)
   - Source database changes SECOND
   - Pipeline handles both old and new schema during transition
   
2. Schema Registry with FORWARD compatibility:
   - New schema must be forward-compatible
   - Old consumers can read new schema (extra fields ignored)
   
3. Graceful degradation:
   - On schema error: pause processing, alert, don't crash
   - Buffer messages to Kafka (don't lose data)
   - Manual resolution: evolve schema → resume
```

---

## Issue #77: Kafka Consumer Lag Growing (Iceberg Sink Backpressure)

**Severity:** P1 - High
**Frequency:** When write throughput exceeds Iceberg commit capacity
**Affected Components:** Data freshness, Kafka retention pressure
**First seen at:** During traffic spikes (2-3x normal load)

### Symptoms
```
- Kafka consumer group lag: 500K messages (growing)
- Flink backpressure: 100% on Iceberg sink operator
- Write throughput: 50K events/sec (capacity: 30K events/sec to Iceberg)
- Events backing up in Kafka (approaching retention limit)
- Dashboard freshness: degrading from 5 min to 30 min to 2 hours
```

### Root Cause
```
Iceberg write path bottlenecks:

  1. S3 PUT latency (50-100ms per file write)
  2. Commit serialization (one commit at a time per table)
  3. Parquet encoding (CPU-bound for compression)
  4. Memory pressure (buffering events until checkpoint)
  5. Manifest file creation (sequential metadata writes)
  
  Maximum throughput per Flink job to single Iceberg table:
    ~100K events/sec with good tuning
    ~30-50K events/sec with default config
    
  During spike: 200K events/sec incoming vs 50K write capacity
    → 150K/sec surplus → accumulates in Kafka → lag grows
    → 1 hour spike: 540M messages of lag
    → At 50K/sec drain rate: 3 hours to catch up
```

### Immediate Fix
```bash
# Scale Flink job horizontally
flink modify job_id --parallelism 200  # Increase from 100

# Or: temporarily increase Kafka partition count
kafka-topics.sh --alter --topic events --partitions 200
```

### Permanent Fix
```
1. Auto-scaling Flink (reactive scaling):
   - Monitor consumer lag
   - Scale up parallelism when lag > threshold
   - Scale down when caught up
   
2. Tune Iceberg sink for throughput:
   - write.distribution-mode=none (skip redistribution)
   - Larger target file size (fewer files per commit)
   - Fewer but larger checkpoints
   
3. Backpressure handling:
   - Size for peak load (not average)
   - Kafka retention: 7 days (buffer for extended outages)
   - Overflow routing: if lag > threshold, write to staging (fast), compact later
   
4. Multiple tables for parallelism:
   - Shard writes across 10 tables (10x commit throughput)
   - Downstream: union or federated query across shards
```

---

## Issue #78: Duplicate Events After Flink Job Restart

**Severity:** P1 - High
**Frequency:** Every Flink job restart/redeploy
**Affected Components:** Data quality (duplicates)
**First seen at:** Every streaming-to-Iceberg deployment

### Symptoms
```
- After Flink restart: 5 minutes of duplicate events in Iceberg
- Row count spike at restart time
- Downstream aggregations over-count during restart window
- Dedup query shows 0.1% duplicates (significant at billion-event scale)
```

### Root Cause
```
Flink exactly-once guarantee has a gap during restart:

  Checkpoint N: committed to Iceberg (snapshot v100)
  Processing events after checkpoint N...
  Job crashes (before checkpoint N+1)
  
  Restart: resume from checkpoint N
  Re-reads events from Kafka (from checkpoint N offset)
  Re-processes and writes to Iceberg again
  
  Scenario A: Events between N and crash were NOT committed to Iceberg
    → Re-processing is correct (no duplicates) ✓
    
  Scenario B: Events were written to S3 but commit failed (orphan files)
    → Re-processing writes new files + commits → correct ✓
    
  Scenario C: Events were committed (checkpoint N+1 partially succeeded)
    → Re-processing writes again → DUPLICATES ✗
    
  Scenario C happens when:
    - Flink commits to Iceberg (success)
    - Flink tries to complete checkpoint (fails)
    - From Flink's perspective: checkpoint failed
    - From Iceberg's perspective: data committed
    → Restart re-processes already-committed events
```

### Permanent Fix
```python
# Post-restart deduplication job (runs automatically after restart)
def deduplicate_after_restart(table_name, event_id_col, window_hours=1):
    """Remove duplicates created during Flink restart."""
    spark.sql(f"""
        MERGE INTO prod.{table_name} t
        USING (
            SELECT {event_id_col}, 
                   ROW_NUMBER() OVER (PARTITION BY {event_id_col} ORDER BY _commit_timestamp DESC) as rn
            FROM prod.{table_name}
            WHERE _commit_timestamp > current_timestamp() - INTERVAL {window_hours} HOURS
        ) dedup
        ON t.{event_id_col} = dedup.{event_id_col}
        WHEN MATCHED AND dedup.rn > 1 THEN DELETE
    """)
```

```java
// Flink: Use upsert mode with equality fields (built-in dedup)
FlinkSink.forRowData(stream)
    .tableLoader(tableLoader)
    .equalityFieldColumns(Arrays.asList("event_id"))  // Primary key
    .upsert(true)  // Upsert semantics (handles duplicates)
    .build();
```

---

## Issue #79: CDC Delete Events Not Propagating to Iceberg

**Severity:** P1 - High
**Frequency:** When pipeline only handles INSERT/UPDATE but not DELETE
**Affected Components:** Data correctness (deleted records persist)
**First seen at:** Initial CDC pipeline implementations

### Symptoms
```
- Source DB: record deleted
- Iceberg table: record still exists
- Row count in Iceberg > row count in source (grows over time)
- Stale/deleted records appearing in reports
- GDPR deletion not propagating from source to lake
```

### Root Cause
```
Debezium emits delete events as:
  {
    "op": "d",
    "before": {"id": 123, "name": "John", "email": "john@test.com"},
    "after": null
  }

Common pipeline mistakes:
  1. Filter condition only processes op='c' (create) and op='u' (update)
     → Drops op='d' (delete) events
     
  2. Append-only pipeline: doesn't know how to "delete" from Iceberg
     → All events appended, including "delete" events (as new rows!)
     
  3. Tombstone records in Kafka (key present, value NULL):
     → Deserializer crashes on NULL value → event lost
     
  4. MERGE INTO without WHEN MATCHED AND ... THEN DELETE clause:
     → Only handles updates, not deletes
```

### Permanent Fix
```python
# Complete CDC MERGE handling all operations
def apply_cdc_changes(spark, table_name, cdc_batch_df):
    """Apply CDC changes including deletes."""
    
    cdc_batch_df.createOrReplaceTempView("cdc_changes")
    
    spark.sql(f"""
        MERGE INTO prod.{table_name} target
        USING (
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY id ORDER BY event_timestamp DESC
                ) as rn
                FROM cdc_changes
            ) WHERE rn = 1
        ) source
        ON target.id = source.id
        WHEN MATCHED AND source.op = 'd' THEN DELETE
        WHEN MATCHED AND source.op = 'u' THEN UPDATE SET *
        WHEN NOT MATCHED AND source.op != 'd' THEN INSERT *
    """)
```

---

## Issue #80: Watermark Drift Causing Late Events to Be Dropped

**Severity:** P1 - High
**Frequency:** With event-time processing and late-arriving data
**Affected Components:** Data completeness
**First seen at:** Event-time partitioned tables with global sources

### Symptoms
```
- 0.5-2% of events never appear in Iceberg table
- Missing events are always "late" (event_time << processing_time)
- Flink watermark advances past event → event dropped
- Events from mobile devices with clock skew consistently lost
- Events from offline-first apps (batch uploaded) always dropped
```

### Root Cause
```
Flink watermarks define "event time has progressed to X":
  
  Watermark at T=10:05:00
  → All events with event_time < 10:05:00 are considered "late"
  → Late events: dropped by windowed operations
  
  Sources of late events:
  - Mobile apps: 5-60 minute delay in sending events
  - Offline devices: hours/days of delay
  - Cross-timezone: events appear "late" due to clock differences
  - Network outages: batch of events arrives late
  - Retry queues: failed events reprocessed hours later
  
  With allowed lateness = 5 minutes:
    Events arriving 5+ minutes late → DROPPED
    At 10B events/day with 0.5% late: 50M events lost daily
```

### Permanent Fix
```java
// Strategy 1: Side output for late events (never drop)
SingleOutputStreamTag<Event> lateEventsTag = new OutputTag<>("late-events");

DataStream<Event> mainStream = inputStream
    .assignTimestampsAndWatermarks(
        WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofMinutes(5))
            .withTimestampAssigner((event, timestamp) -> event.getEventTime())
    )
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.hours(1))  // Allow 1 hour late
    .sideOutputLateData(lateEventsTag)  // Don't drop, side-output
    .process(new MyWindowFunction());

// Late events go to separate Iceberg table (processed in batch later)
DataStream<Event> lateEvents = mainStream.getSideOutput(lateEventsTag);
lateEvents.sinkTo(lateEventsIcebergSink);
```

```
Strategy 2: Append-only with downstream dedup/merge:
  - Never drop events regardless of lateness
  - Append ALL events to Iceberg (including very late ones)
  - Downstream batch job handles ordering/dedup
  - Trade-off: more complex downstream but zero data loss

Strategy 3: Large watermark delay + aggressive compaction:
  - Set watermark delay to 1 hour (accept ALL events within 1 hour)
  - Accept small file problem (events trickle in late)
  - Compact hourly to fix file sizes
```

---

## Issue #81: Schema Registry Incompatibility with Iceberg Schema Evolution

**Severity:** P2 - Medium
**Frequency:** When Kafka schema evolves independently of Iceberg
**Affected Components:** Pipeline reliability, schema alignment
**First seen at:** Decoupled teams (producer team evolves schema without telling consumers)

### Symptoms
```
- Schema Registry shows schema v15
- Iceberg table has schema v8
- 7 columns exist in Kafka messages but not in Iceberg table
- Silent data loss: new fields in events dropped during write
- No error: pipeline happily ignores extra fields
```

### Root Cause
```
Two independent schema evolution paths:

  Producer → Schema Registry: evolves freely (adding fields, etc.)
  Iceberg table: evolves separately (manual ALTER TABLE)
  
  Gap grows over time:
  Kafka event: {id, name, email, phone, address, preferences, ...}
  Iceberg table: {id, name, email}  (6 columns behind!)
  
  Flink/Spark writer: maps available columns, ignores extras
  → Data silently lost (phone, address, preferences never stored)
  
  Nobody notices until downstream consumer needs phone number:
    "Why is phone NULL for all 2024 data?!"
    "Oh, we never evolved the Iceberg schema..."
```

### Permanent Fix
```python
# Automated schema sync: Registry → Iceberg
from confluent_kafka.schema_registry import SchemaRegistryClient
from pyiceberg.catalog import load_catalog

def sync_schema(topic, table_name):
    """Sync Kafka schema to Iceberg table (add new columns)."""
    
    # Get latest Kafka schema
    sr = SchemaRegistryClient({"url": "http://schema-registry:8081"})
    kafka_schema = sr.get_latest_version(f"{topic}-value")
    kafka_fields = parse_avro_fields(kafka_schema.schema)
    
    # Get current Iceberg schema
    catalog = load_catalog("prod")
    table = catalog.load_table(table_name)
    iceberg_fields = {f.name for f in table.schema().fields}
    
    # Find new fields (in Kafka but not Iceberg)
    new_fields = kafka_fields - iceberg_fields
    
    for field in new_fields:
        field_type = kafka_to_iceberg_type(kafka_schema, field)
        spark.sql(f"ALTER TABLE {table_name} ADD COLUMN {field} {field_type}")
        logger.info(f"Added column {field} ({field_type}) to {table_name}")
```

---

## Issue #82: Flink Iceberg Sink Parallelism Mismatch

**Severity:** P2 - Medium
**Frequency:** Misconfigured Flink job topology
**Affected Components:** Write throughput, commit conflicts
**First seen at:** Flink jobs with incorrect parallelism settings

### Symptoms
```
- Write throughput limited despite available resources
- Commit conflicts even with single table writer
- Each checkpoint creates parallelism × partitions number of files
- Too many small files from Flink (1 per task per partition per checkpoint)
- Reducing parallelism improves file quality but reduces throughput
```

### Root Cause
```
Flink Iceberg sink file creation:

  Files per checkpoint = parallelism × active_partitions
  
  Example:
    Parallelism: 100
    Active partitions: 24 (hourly partitions for 1 day)
    Checkpoint interval: 1 minute
    
    Files per checkpoint: 100 × 24 = 2,400 files
    Files per hour: 2,400 × 60 = 144,000 files!
    Average file size: total_data_per_minute / 2400 = tiny
    
  With write.distribution-mode=hash:
    Data shuffled to specific tasks per partition
    Parallelism: 100, but only 24 active partitions
    → 24 tasks write (others idle)
    → Files per checkpoint: 24 (much better!)
    → But 76 tasks wasted (under-utilized)
```

### Permanent Fix
```properties
# Balance parallelism and file count
# Rule: parallelism ≈ number of expected active partitions

# For 24 hourly partitions:
flink.parallelism.default = 24  # Match partition count

# Or use distribution mode:
write.distribution-mode = hash  # Concentrate writes per partition
# This lets you use higher parallelism (100) but still get good files

# File size tuning:
write.target-file-size-bytes = 134217728  # 128MB target
write.parquet.row-group-size-bytes = 67108864  # 64MB row groups
```

---

## Issue #83: Streaming MERGE Performance Cliff

**Severity:** P1 - High
**Frequency:** When streaming merge target table grows large
**Affected Components:** Streaming latency, freshness
**First seen at:** After table grows past 100M rows

### Symptoms
```
- Micro-batch MERGE: 5 seconds at 1M rows → 5 minutes at 100M rows
- Linear degradation: each doubling of table size = 2x merge time
- Eventually MERGE takes longer than batch interval → falling behind
- Streaming pipeline cannot keep up with data rate
- Only affects MERGE (appends still fast)
```

### Root Cause
```
MERGE INTO must scan target to find matching rows:

  MERGE INTO target USING source ON target.id = source.id
  
  Execution:
    1. Read source batch (1000 rows, fast)
    2. Scan target for matching IDs (100M rows!)
    3. Apply changes (fast)
    4. Commit (fast)
    
  Step 2 is the bottleneck:
    Without optimization: full table scan every micro-batch
    With file pruning: scan files where min(id) <= source_max AND max(id) >= source_min
    
    But with random IDs (UUIDs): almost no pruning possible
    → Every micro-batch scans nearly all 100M rows
    
  As table grows: scan time grows linearly
  Eventually: merge_time > batch_interval → pipeline stalls
```

### Permanent Fix
```
1. Use MoR upsert instead of MERGE (for streaming):
   - Equality delete + insert (no target scan needed!)
   - Write: O(source_size) not O(target_size)
   - Requires compaction but writes are fast
   
2. Partition alignment:
   - Partition target by same key used in MERGE ON clause
   - bucket(256, id) → MERGE only scans matching bucket
   - Reduces scan from 100M to 100M/256 = 400K rows
   
3. Bucketed MERGE optimization:
   - Iceberg can push down join predicate to file pruning
   - Requires: partition by bucket(id) + filter on id in MERGE
   
4. Micro-batch size vs frequency trade-off:
   - Larger batches: better amortization of scan cost
   - Fewer merges per hour: less total scan time
```

```python
# Optimized: Use equality delete + insert instead of MERGE
# (Much faster for streaming - no target scan needed)
def streaming_upsert(spark, source_df, table_name, key_col):
    """Fast upsert using delete+insert (no MERGE scan)."""
    
    # Create equality delete for matching keys
    keys = source_df.select(key_col).distinct()
    
    # Write equality deletes
    spark.sql(f"""
        DELETE FROM prod.{table_name} 
        WHERE {key_col} IN (SELECT {key_col} FROM incoming_keys)
    """)
    
    # Append new versions
    source_df.writeTo(f"prod.{table_name}").append()
```

---

## Issue #84: Kafka Offset Tracking Drift from Iceberg Snapshots

**Severity:** P1 - High
**Frequency:** After infrastructure changes or prolonged outages
**Affected Components:** Exactly-once tracking, data gaps/duplicates
**First seen at:** After Kafka cluster maintenance or topic recreation

### Symptoms
```
- After Kafka maintenance: pipeline resumes from wrong offset
- Gap in Iceberg data (missing events from specific time window)
- Iceberg snapshot committed but Kafka offset not advanced
- Consumer group offsets reset during Kafka upgrade
- No way to correlate Iceberg snapshots to Kafka offsets
```

### Root Cause
```
Two separate state systems:
  1. Kafka: consumer group offsets (topic, partition, offset)
  2. Iceberg: snapshots (table state at point in time)
  
  Flink bridges them via checkpoint:
    Checkpoint = (kafka offsets, iceberg pending files)
    On commit: advance Kafka offsets + commit Iceberg snapshot
    
  Drift occurs when:
    - Kafka offsets reset (topic recreation, cluster migration)
    - Flink checkpoint lost (state backend failure)
    - Manual Kafka offset manipulation
    - Iceberg committed but Kafka offset commit failed
    
  Without correlation: can't determine "which Kafka data is in which snapshot"
```

### Permanent Fix
```python
# Store Kafka offset metadata in Iceberg snapshot properties
# Custom Flink sink that records offsets in commit:

# After commit, record mapping:
snapshot_properties = {
    "kafka.topic": "events",
    "kafka.partition.0.offset": "1234567",
    "kafka.partition.1.offset": "2345678",
    "kafka.partition.2.offset": "3456789",
    "kafka.commit.timestamp": "2024-01-15T10:30:00Z"
}

# Store in separate tracking table:
spark.sql("""
    INSERT INTO prod.iceberg_kafka_offsets 
    VALUES (
        'events_table', -- iceberg table
        1234567890,     -- snapshot_id
        '2024-01-15 10:30:00', -- commit_time
        MAP('0', 1234567, '1', 2345678, '2', 3456789) -- offsets per partition
    )
""")

# Recovery: lookup last committed offsets for table
def get_recovery_offsets(table_name):
    return spark.sql(f"""
        SELECT kafka_offsets FROM prod.iceberg_kafka_offsets
        WHERE iceberg_table = '{table_name}'
        ORDER BY commit_time DESC LIMIT 1
    """).first().kafka_offsets
```

---

## Issue #85: Flink Job Upgrade Causes Incompatible State

**Severity:** P1 - High
**Frequency:** Every Flink job upgrade/redeploy
**Affected Components:** Pipeline continuity
**First seen at:** First code change after initial deployment

### Symptoms
```
- After code change + redeploy: "Incompatible state found"
- Cannot resume from savepoint (serialization changed)
- Must restart from scratch (lose progress)
- Flink state migration fails for complex operators
- Every deploy = fresh start = data gap or reprocess
```

### Root Cause
```
Flink state is Java-serialized. Code changes can break compatibility:

  - Rename operator → state can't be mapped to new operator
  - Change parallelism → state redistribution may fail
  - Modify state schema (add field to POJO) → deserialization fails
  - Upgrade Flink version → internal state format changed
  - Change Iceberg sink config → sink state incompatible
```

### Permanent Fix
```java
// Use UID for all operators (stable across code changes)
stream
    .keyBy(Event::getKey)
    .process(new MyProcessor())
    .uid("my-processor-v1")  // ALWAYS set UID
    .name("My Processor")
    .sinkTo(icebergSink)
    .uid("iceberg-sink-v1"); // ALWAYS set UID

// For schema evolution in state:
// Use Avro/Protobuf state serializer (supports evolution)
env.getConfig().registerTypeWithKryoSerializer(MyState.class, AvroSerializer.class);
```

```
Deployment strategy:
1. Always take savepoint before upgrade
2. Use operator UIDs (never change)
3. Test state compatibility in staging
4. If incompatible: stop-with-savepoint → start fresh with replay from Kafka
5. Maintain upgrade compatibility matrix
```

---

## Issue #86: CDC Backfill Conflicts with Streaming Pipeline

**Severity:** P1 - High
**Frequency:** During initial CDC setup or historical backfill
**Affected Components:** Data consistency, pipeline reliability
**First seen at:** When running full-load + CDC simultaneously

### Symptoms
```
- Backfill job and streaming CDC both writing to same table
- Duplicate rows (backfill writes row, CDC writes same row)
- Lost updates (backfill overwrites CDC-applied change)
- Inconsistent state during backfill window
- Cannot determine which source is "truth" during overlap
```

### Root Cause
```
Two data sources writing same table simultaneously:

  Backfill (batch): reads full table snapshot at T0, writes to Iceberg
  CDC (streaming): captures changes from T0 onward, writes to Iceberg
  
  Race conditions:
  T0: Backfill reads source (user_123: name="John")
  T1: Source update: user_123 → name="Jane"  
  T2: CDC captures T1 change → writes to Iceberg (name="Jane")
  T3: Backfill writes user_123 → name="John" (STALE! Overwrites CDC!)
  
  Result: user_123 shows "John" (should be "Jane")
```

### Permanent Fix
```
Strategy: Sequential backfill with CDC catch-up:

1. Start CDC but DON'T write to final table yet (buffer in staging)
2. Run backfill from source snapshot at T0
3. After backfill: apply buffered CDC events (T0 → now) using MERGE
4. Switch to live CDC writing to final table
5. No overlap period → no conflicts

Alternative: CDC-first approach:
1. Start CDC from current position (captures all changes from now)
2. Run backfill as separate table (backfill_table)
3. MERGE backfill_table INTO final_table (CDC has priority for conflicts)
4. Done: historical data from backfill + real-time from CDC
```

```python
# Safe backfill with CDC coordination
def coordinated_backfill(source_table, target_table, cdc_topic):
    # Step 1: Record current Kafka offset (CDC start point)
    start_offsets = get_current_kafka_offsets(cdc_topic)
    
    # Step 2: Full backfill from source snapshot
    backfill_df = spark.read.jdbc(source_connection, source_table)
    backfill_df.writeTo(f"prod.{target_table}").overwritePartitions()
    
    # Step 3: Apply CDC events from start_offsets to now
    cdc_df = read_kafka_range(cdc_topic, start_offsets, current_offsets())
    apply_cdc_merge(cdc_df, target_table)  # CDC wins conflicts
    
    # Step 4: Switch streaming CDC to write directly
    start_streaming_cdc(cdc_topic, target_table)
```

---

## Summary: Streaming, CDC & Real-Time Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 73 | Flink checkpoint timeout | P0 | Unaligned checkpoints + longer timeout |
| 74 | CDC event ordering violation | P1 | Partition by primary key + event-time ordering |
| 75 | Data freshness SLA breach | P1 | Short commits + async compaction |
| 76 | Schema change crashes pipeline | P0 | Schema-agnostic processing + pre-evolution |
| 77 | Kafka consumer lag growing | P1 | Auto-scaling + write distribution tuning |
| 78 | Duplicates after Flink restart | P1 | Upsert mode + post-restart dedup |
| 79 | CDC deletes not propagating | P1 | Full MERGE with DELETE handling |
| 80 | Late events dropped by watermark | P1 | Side-output + append-only pattern |
| 81 | Schema Registry vs Iceberg drift | P2 | Automated schema sync |
| 82 | Flink parallelism mismatch | P2 | Match parallelism to partition count |
| 83 | Streaming MERGE performance cliff | P1 | MoR upsert + bucket partitioning |
| 84 | Kafka offset drift from snapshots | P1 | Offset tracking table + recovery |
| 85 | Flink job upgrade breaks state | P1 | Operator UIDs + state evolution |
| 86 | Backfill conflicts with streaming | P1 | Sequential coordination + MERGE priority |
