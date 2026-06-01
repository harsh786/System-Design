# Streaming Upserts - Unified Batch + Real-Time Pipeline

## The Production Problem

A ride-sharing company (Uber/Lyft scale) operates a `ride_events` table that serves as the **single source of truth** for all ride lifecycle data. This table must simultaneously handle:

1. **Real-time streaming** (1M events/sec): ride status changes, driver GPS pings, surge pricing updates, ETA recalculations
2. **Batch corrections** (hourly): fare adjustments, fraud flags, retroactive pricing corrections
3. **Late-arriving data** (up to 72h): partner integrations, payment settlements, insurance claims

The core challenge: these three write paths target the **same rows**. A ride created at 2:00 PM gets 50+ updates over its lifecycle — streaming status changes, batch fare corrections, late payment confirmations — and every reader must see a consistent, up-to-date view.

### Why This Is Hard Without Iceberg

**Before Iceberg (the Lambda Architecture nightmare):**

```
┌─────────────────────────────────────────────────────────────┐
│  BEFORE: Separate Systems = Consistency Hell                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Kafka ──► Flink ──► HBase (real-time view)                │
│                           │                                 │
│                           ▼                                 │
│  S3/HDFS ──► Spark ──► Hive (batch view)                   │
│                           │                                 │
│                           ▼                                 │
│  Reconciliation Job (runs at 3 AM, breaks every Tuesday)   │
│                           │                                 │
│                           ▼                                 │
│  "Which one is correct?" ── Nobody knows                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Problems:
- Two copies of truth that constantly diverge
- HBase operational cost: $2M/year for this one table
- Reconciliation job takes 6 hours, delays downstream
- Analysts query Hive (stale), ops query HBase (incomplete)
- Schema changes require coordinated deploys across 4 systems
```

**With Iceberg (unified):**

```
┌─────────────────────────────────────────────────────────────┐
│  AFTER: Single Iceberg Table = One Truth                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Kafka ──► Flink ──► ┐                                     │
│                      ├──► Iceberg Table (S3) ──► All readers│
│  Corrections ──► Spark ──►┘        │                        │
│                                    │                        │
│                          Compaction (async)                  │
│                                                             │
│  One schema, one table, one truth, ACID guarantees          │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Savings:
- Eliminated HBase: -$2M/year
- Eliminated reconciliation: -1 FTE
- Query latency: seconds (not hours stale)
- Schema evolution: one ALTER TABLE
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED STREAMING UPSERT PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────────────────────────────────┐                   │
│  │  Kafka   │    │  Flink Cluster (K8s)                 │                   │
│  │  Cluster │    │                                      │                   │
│  │          │───►│  ┌────────┐  ┌────────┐  ┌───────┐  │                   │
│  │ 256 parts│    │  │Source  │─►│Dedup + │─►│Iceberg│  │                   │
│  │ 1M evt/s │    │  │Operator│  │Process │  │ Sink  │  │                   │
│  └──────────┘    │  └────────┘  └────────┘  └───┬───┘  │                   │
│                  │                               │      │                   │
│                  │  Checkpoints every 60s ────────┘      │                   │
│                  └──────────────────────────────────────┘                   │
│                                         │                                   │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────────────┐                   │
│  │              Apache Iceberg Table (S3)                │                   │
│  │                                                      │                   │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────────┐     │                   │
│  │  │ Data    │  │Equality │  │  Position Delete  │     │                   │
│  │  │ Files   │  │ Delete  │  │  Files (from      │     │                   │
│  │  │ (Parquet)│  │ Files   │  │  compaction)      │     │                   │
│  │  └─────────┘  └─────────┘  └──────────────────┘     │                   │
│  │                                                      │                   │
│  │  Metadata: Snapshots, Manifests, Schema              │                   │
│  └──────────────────────────────────────────────────────┘                   │
│                        │                    ▲                                │
│                        ▼                    │                                │
│  ┌──────────────────────────┐   ┌───────────────────────┐                   │
│  │  Readers (1000+)         │   │  Spark Compaction      │                   │
│  │                          │   │  Service               │                   │
│  │  • Trino (analytics)     │   │                        │                   │
│  │  • Spark (ML pipelines)  │   │  • Rewrites data files │                   │
│  │  • Presto (dashboards)   │   │  • Removes deletes     │                   │
│  │  • Flink (streaming read)│   │  • Runs every 15 min   │                   │
│  └──────────────────────────┘   └───────────────────────┘                   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │  Batch Corrections (Spark, hourly)                        │               │
│  │  • Fare recalculations, fraud flags, payment settlements │               │
│  │  • MERGE INTO with deduplication                         │               │
│  └──────────────────────────────────────────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Table DDL: Merge-on-Read Optimized for Streaming

```sql
CREATE TABLE ride_sharing.events.ride_events (
    -- Primary key (used for equality deletes)
    ride_id         STRING      NOT NULL,
    event_id        STRING      NOT NULL,
    
    -- Event metadata
    event_type      STRING,         -- 'created','accepted','started','completed','cancelled'
    event_timestamp TIMESTAMP,
    ingestion_time  TIMESTAMP,
    
    -- Ride details (mutable via upserts)
    rider_id        STRING,
    driver_id       STRING,
    status          STRING,
    
    -- Location
    pickup_lat      DOUBLE,
    pickup_lng      DOUBLE,
    dropoff_lat     DOUBLE,
    dropoff_lng     DOUBLE,
    current_lat     DOUBLE,
    current_lng     DOUBLE,
    
    -- Pricing (frequently updated)
    estimated_fare  DECIMAL(10,2),
    actual_fare     DECIMAL(10,2),
    surge_multiplier DECIMAL(4,2),
    
    -- Batch-correction fields
    fare_adjustment DECIMAL(10,2),
    fraud_flag      BOOLEAN,
    correction_timestamp TIMESTAMP,
    
    -- Partitioning column
    event_date      DATE
)
USING iceberg
PARTITIONED BY (event_date, bucket(64, ride_id))
TBLPROPERTIES (
    -- Merge-on-Read: critical for streaming upserts
    'write.delete.mode'             = 'merge-on-read',
    'write.update.mode'             = 'merge-on-read',
    'write.merge.mode'              = 'merge-on-read',
    
    -- Equality delete field (streaming upserts use this)
    'write.delete.equality-field-ids' = '1,2',  -- ride_id, event_id
    
    -- File sizing for streaming (smaller files, faster commits)
    'write.target-file-size-bytes'  = '134217728',   -- 128MB (smaller for streaming)
    'write.parquet.row-group-size-bytes' = '67108864', -- 64MB row groups
    
    -- Commit configuration
    'commit.retry.num-retries'      = '10',
    'commit.retry.min-wait-ms'      = '100',
    'commit.retry.max-wait-ms'      = '60000',
    'commit.manifest.min-count-to-merge' = '100',
    'commit.manifest-merge.enabled' = 'true',
    
    -- Compaction hints
    'write.distribution-mode'       = 'hash',  -- co-locate by ride_id
    'read.split.target-size'        = '268435456',  -- 256MB splits for readers
    
    -- History and snapshot management
    'history.expire.max-snapshot-age-ms' = '259200000',  -- 3 days
    'history.expire.min-snapshots-to-keep' = '100'
);
```

---

## Flink Streaming Upsert Writer (Java)

### Main Pipeline Job

```java
package com.rideshare.pipeline.streaming;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.restartstrategy.RestartStrategies;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.CheckpointConfig;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.iceberg.flink.FlinkSchemaUtil;
import org.apache.iceberg.flink.TableLoader;
import org.apache.iceberg.flink.sink.FlinkSink;
import org.apache.iceberg.catalog.TableIdentifier;
import org.apache.iceberg.flink.CatalogLoader;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Flink job that consumes ride events from Kafka and writes upserts
 * to Iceberg with exactly-once semantics.
 * 
 * Scale: 1M events/sec across 256 Kafka partitions
 * Checkpoint interval: 60s (balances latency vs commit overhead)
 * Parallelism: 512 (2x Kafka partitions for headroom)
 */
public class RideEventStreamingUpsertJob {

    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        // ═══════════════════════════════════════════════════════════════
        // EXACTLY-ONCE CHECKPOINTING CONFIGURATION
        // ═══════════════════════════════════════════════════════════════
        
        // Checkpoint every 60 seconds - this is the commit interval to Iceberg
        // Tradeoff: shorter = fresher data but more small files and catalog pressure
        //           longer  = fewer commits but higher data loss window on failure
        env.enableCheckpointing(60_000, CheckpointingMode.EXACTLY_ONCE);
        
        CheckpointConfig checkpointConfig = env.getCheckpointConfig();
        
        // Minimum 30s between checkpoints (prevents checkpoint storms under backpressure)
        checkpointConfig.setMinPauseBetweenCheckpoints(30_000);
        
        // Checkpoint must complete within 5 minutes or it's failed
        checkpointConfig.setCheckpointTimeout(300_000);
        
        // Allow 3 concurrent checkpoints (overlapping for large state)
        checkpointConfig.setMaxConcurrentCheckpoints(1);
        
        // Keep checkpoints on cancellation for manual recovery
        checkpointConfig.setExternalizedCheckpointCleanup(
            CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION
        );
        
        // Unaligned checkpoints: critical for high-throughput to avoid backpressure
        // during checkpoint barriers
        checkpointConfig.enableUnalignedCheckpoints();
        checkpointConfig.setAlignedCheckpointTimeout(Duration.ofSeconds(30));
        
        // Checkpoint storage on S3 for durability
        env.getCheckpointConfig().setCheckpointStorage(
            "s3://rideshare-checkpoints/flink/ride-events-upsert/");
        
        // ═══════════════════════════════════════════════════════════════
        // RESTART STRATEGY
        // ═══════════════════════════════════════════════════════════════
        
        // Exponential backoff: avoids thundering herd on transient failures
        env.setRestartStrategy(RestartStrategies.exponentialDelayRestart(
            Time.of(1, TimeUnit.SECONDS),     // initial delay
            Time.of(60, TimeUnit.SECONDS),    // max delay
            2.0,                               // backoff multiplier
            Time.of(300, TimeUnit.SECONDS),   // reset backoff after stable period
            0.1                                // jitter
        ));
        
        // Parallelism: 512 operators for 256 Kafka partitions
        env.setParallelism(512);
        
        // ═══════════════════════════════════════════════════════════════
        // KAFKA SOURCE
        // ═══════════════════════════════════════════════════════════════
        
        KafkaSource<RideEvent> kafkaSource = KafkaSource.<RideEvent>builder()
            .setBootstrapServers("kafka-broker-1:9092,kafka-broker-2:9092,kafka-broker-3:9092")
            .setTopics("ride-events-v2")
            .setGroupId("iceberg-upsert-writer-prod")
            .setStartingOffsets(OffsetsInitializer.committedOffsets())
            .setDeserializer(new RideEventDeserializationSchema())
            // Kafka consumer tuning for high throughput
            .setProperty("fetch.min.bytes", "1048576")           // 1MB min fetch
            .setProperty("fetch.max.wait.ms", "500")             // 500ms max wait
            .setProperty("max.partition.fetch.bytes", "10485760") // 10MB per partition
            .setProperty("max.poll.records", "10000")
            .build();
        
        DataStream<RideEvent> eventStream = env.fromSource(
            kafkaSource,
            WatermarkStrategy.<RideEvent>forBoundedOutOfOrderness(Duration.ofMinutes(5))
                .withTimestampAssigner((event, ts) -> event.getEventTimestamp()),
            "Kafka-RideEvents"
        );
        
        // ═══════════════════════════════════════════════════════════════
        // DEDUPLICATION + PROCESSING
        // ═══════════════════════════════════════════════════════════════
        
        DataStream<RideEvent> deduplicated = eventStream
            // Key by ride_id for deduplication state
            .keyBy(RideEvent::getRideId)
            // Deduplicate within 10-minute window using event_id
            .process(new DeduplicationFunction(Duration.ofMinutes(10)))
            .name("Deduplication")
            .uid("dedup-operator");
        
        DataStream<RideEvent> processed = deduplicated
            .keyBy(RideEvent::getRideId)
            .process(new RideEventEnrichmentFunction())
            .name("Enrichment")
            .uid("enrichment-operator");
        
        // ═══════════════════════════════════════════════════════════════
        // ICEBERG SINK WITH UPSERT (EQUALITY DELETES)
        // ═══════════════════════════════════════════════════════════════
        
        Map<String, String> catalogProperties = new HashMap<>();
        catalogProperties.put("type", "glue");  // AWS Glue Catalog
        catalogProperties.put("warehouse", "s3://rideshare-lakehouse/warehouse");
        catalogProperties.put("io-impl", "org.apache.iceberg.aws.s3.S3FileIO");
        catalogProperties.put("s3.endpoint", "https://s3.us-east-1.amazonaws.com");
        // S3 write optimization
        catalogProperties.put("s3.multipart.size", "67108864");  // 64MB multipart
        catalogProperties.put("s3.multipart.threshold", "67108864");
        
        CatalogLoader catalogLoader = CatalogLoader.custom(
            "glue_catalog", catalogProperties, new org.apache.hadoop.conf.Configuration());
        
        TableLoader tableLoader = TableLoader.fromCatalog(
            catalogLoader, TableIdentifier.of("ride_sharing", "events", "ride_events"));
        
        FlinkSink.forRowData(processed.map(new RideEventToRowDataMapper()))
            .tableLoader(tableLoader)
            // UPSERT MODE: generates equality delete + new data file per checkpoint
            .upsert(true)
            // Equality fields: determines which existing rows to delete before inserting
            .equalityFieldColumns(java.util.Arrays.asList("ride_id", "event_id"))
            // Distribution: hash by ride_id ensures co-located deletes
            .distributionMode(org.apache.iceberg.DistributionMode.HASH)
            // Parallelism for writers (fewer than source for file consolidation)
            .writeParallelism(256)
            // Target file size in the writer
            .set("write.target-file-size-bytes", "134217728")
            // Manifest merge on each commit
            .set("commit.manifest.min-count-to-merge", "50")
            .append();
        
        env.execute("RideEvents-Streaming-Upsert-to-Iceberg");
    }
}
```

### Deduplication Function

```java
package com.rideshare.pipeline.streaming;

import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

import java.time.Duration;

/**
 * Deduplicates events by event_id within a configurable window.
 * 
 * Uses Flink state with TTL to automatically expire dedup entries,
 * preventing unbounded state growth. At 1M events/sec with 10-min TTL,
 * state size is ~600M entries × 40 bytes ≈ 24GB across all operators.
 * 
 * Why deduplicate before Iceberg:
 * - Each duplicate would generate an unnecessary equality delete + data file
 * - Deduplication here prevents file proliferation in the table
 * - Kafka consumer retries on rebalance can produce duplicates
 */
public class DeduplicationFunction 
    extends KeyedProcessFunction<String, RideEvent, RideEvent> {
    
    private final Duration deduplicationWindow;
    private transient ValueState<Long> lastSeenTimestamp;
    
    // Bloom filter state for memory-efficient dedup of event_ids
    private transient ValueState<BloomFilterState> bloomState;
    
    public DeduplicationFunction(Duration deduplicationWindow) {
        this.deduplicationWindow = deduplicationWindow;
    }
    
    @Override
    public void open(Configuration parameters) {
        // TTL-based state expiration prevents unbounded growth
        var ttlConfig = org.apache.flink.api.common.state.StateTtlConfig.newBuilder(
                org.apache.flink.api.common.time.Time.milliseconds(
                    deduplicationWindow.toMillis()))
            .setUpdateType(org.apache.flink.api.common.state.StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(
                org.apache.flink.api.common.state.StateTtlConfig.StateVisibility.NeverReturnExpired)
            .cleanupInRocksdbCompactFilter(5000)
            .build();
        
        var bloomDescriptor = new ValueStateDescriptor<>("bloom", BloomFilterState.class);
        bloomDescriptor.enableTimeToLive(ttlConfig);
        bloomState = getRuntimeContext().getState(bloomDescriptor);
        
        var tsDescriptor = new ValueStateDescriptor<>("last-ts", Types.LONG);
        tsDescriptor.enableTimeToLive(ttlConfig);
        lastSeenTimestamp = getRuntimeContext().getState(tsDescriptor);
    }
    
    @Override
    public void processElement(RideEvent event, Context ctx, Collector<RideEvent> out) 
            throws Exception {
        
        BloomFilterState bloom = bloomState.value();
        if (bloom == null) {
            // Expected false positive rate: 0.01 (1%)
            // Capacity: 1000 events per ride within the dedup window
            bloom = new BloomFilterState(1000, 0.01);
        }
        
        String eventId = event.getEventId();
        
        if (bloom.mightContain(eventId)) {
            // Possible duplicate - emit metric and drop
            getRuntimeContext().getMetricGroup()
                .counter("duplicates_dropped").inc();
            return;
        }
        
        // Not a duplicate: record and emit
        bloom.put(eventId);
        bloomState.update(bloom);
        lastSeenTimestamp.update(event.getEventTimestamp());
        
        // Ordering guarantee: if this event is older than last seen for this key,
        // still emit it (Iceberg merge-on-read will resolve at query time)
        // but flag it for monitoring
        Long lastTs = lastSeenTimestamp.value();
        if (lastTs != null && event.getEventTimestamp() < lastTs) {
            getRuntimeContext().getMetricGroup()
                .counter("out_of_order_events").inc();
        }
        
        out.collect(event);
    }
}
```

### Exactly-Once Semantics: How It Works

```
┌───────────────────────────────────────────────────────────────────────┐
│  EXACTLY-ONCE COMMIT FLOW (per checkpoint)                            │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Checkpoint Triggered (every 60s)                                  │
│     │                                                                 │
│     ▼                                                                 │
│  2. Flink Writer flushes current data files to S3                     │
│     • Data files are written but NOT yet committed to Iceberg         │
│     • Each writer produces: data files + equality delete files        │
│     │                                                                 │
│     ▼                                                                 │
│  3. Checkpoint barrier passes through all operators                   │
│     • Kafka offsets saved to checkpoint                               │
│     • Writer records pending file paths in checkpoint state           │
│     │                                                                 │
│     ▼                                                                 │
│  4. Checkpoint completes → IcebergFilesCommitter triggered            │
│     • Single committer operator (parallelism=1) collects all files    │
│     • Performs atomic Iceberg commit (single snapshot)                 │
│     │                                                                 │
│     ▼                                                                 │
│  5. Commit success → Kafka offsets committed                          │
│     • If commit fails: retry with exponential backoff                 │
│     • If retries exhausted: Flink job fails, restarts from           │
│       last successful checkpoint (exactly-once preserved)             │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  FAILURE RECOVERY SCENARIO                                   │     │
│  │                                                              │     │
│  │  Checkpoint N: committed (files A,B,C in snapshot 100)       │     │
│  │  Checkpoint N+1: data written to S3 but commit failed        │     │
│  │                                                              │     │
│  │  Recovery:                                                   │     │
│  │  • Flink restarts from Checkpoint N                          │     │
│  │  • Kafka offsets reset to Checkpoint N positions             │     │
│  │  • Orphaned files from N+1 on S3 are garbage (cleaned later)│     │
│  │  • Re-processes events, writes NEW files, commits            │     │
│  │  • Result: exactly-once — no duplicates in table             │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Equality Deletes vs Position Deletes

Understanding this distinction is critical for operating a streaming upsert pipeline:

| Aspect | Equality Deletes (Streaming) | Position Deletes (Compaction) |
|--------|------------------------------|-------------------------------|
| Written by | Flink streaming writer | Spark compaction job |
| Contains | Field values to match (ride_id, event_id) | Exact file path + row position |
| Applied at | Read time (merge-on-read) | Read time (faster than equality) |
| Cost | Expensive reads (scan all files) | Cheap reads (direct lookup) |
| Why used | No way to know position during streaming | Compaction knows exact positions |
| Accumulation | Grows every checkpoint (60s) | Created during compaction, replaces equality deletes |

**Read amplification formula:**

```
Read Cost = (Data Files) + (Equality Delete Files × Data Files)  [join required]
           vs
Read Cost = (Data Files) + (Position Delete Files)               [direct lookup]
```

This is why compaction is not optional — it's **critical infrastructure**.

---

## Spark Compaction Service

### Compaction Job (Runs Every 15 Minutes)

```scala
package com.rideshare.pipeline.compaction

import org.apache.spark.sql.SparkSession
import org.apache.iceberg.spark.actions.SparkActions
import org.apache.iceberg.actions.RewriteDataFilesAction
import org.apache.iceberg.expressions.Expressions
import org.apache.iceberg.Table
import org.apache.iceberg.catalog.TableIdentifier
import org.apache.iceberg.spark.SparkCatalog
import io.prometheus.client.{Counter, Gauge, Histogram}

import java.time.LocalDate
import java.time.format.DateTimeFormatter

/**
 * Production compaction service for the ride_events table.
 * 
 * Strategy:
 * - Runs every 15 minutes (cron on K8s)
 * - Only compacts partitions with delete file accumulation above threshold
 * - Partial compaction: targets worst partitions first (budget: 10 minutes)
 * - Converts equality deletes → position deletes → merged data files
 * 
 * Scale considerations:
 * - 100TB table, ~2M files total
 * - Each 15-min run compacts ~500GB across affected partitions
 * - Avoids full-table rewrite (would take 8+ hours)
 */
object CompactionService {

  // Prometheus metrics
  val compactionDuration = Histogram.build()
    .name("compaction_duration_seconds")
    .help("Time taken for compaction run")
    .register()

  val filesRewritten = Counter.build()
    .name("compaction_files_rewritten_total")
    .help("Total data files rewritten by compaction")
    .register()

  val deleteFilesRemoved = Counter.build()
    .name("compaction_delete_files_removed_total")
    .help("Delete files eliminated by compaction")
    .register()

  val readAmplification = Gauge.build()
    .name("table_read_amplification_ratio")
    .help("Current read amplification (delete files / data files)")
    .register()

  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder()
      .appName("RideEvents-Compaction")
      .config("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkCatalog")
      .config("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
      .config("spark.sql.catalog.glue.warehouse", "s3://rideshare-lakehouse/warehouse")
      .config("spark.sql.catalog.glue.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
      // Compaction-specific Spark tuning
      .config("spark.executor.memory", "16g")
      .config("spark.executor.cores", "4")
      .config("spark.dynamicAllocation.enabled", "true")
      .config("spark.dynamicAllocation.maxExecutors", "200")
      .config("spark.sql.shuffle.partitions", "1024")
      .getOrCreate()

    val timer = compactionDuration.startTimer()

    try {
      val table = loadTable(spark)
      
      // Step 1: Identify partitions needing compaction
      val partitionsToCompact = findPartitionsNeedingCompaction(table)
      
      // Step 2: Partial compaction (budget-aware)
      compactPartitions(spark, table, partitionsToCompact)
      
      // Step 3: Expire old snapshots
      expireSnapshots(table)
      
      // Step 4: Remove orphan files (S3 garbage from failed commits)
      removeOrphanFiles(spark, table)
      
      // Step 5: Update read amplification metric
      updateMetrics(table)
      
    } finally {
      timer.observeDuration()
      spark.stop()
    }
  }

  private def findPartitionsNeedingCompaction(table: Table): Seq[PartitionCompactionTarget] = {
    import scala.collection.JavaConverters._
    
    val snapshot = table.currentSnapshot()
    val manifests = snapshot.dataManifests(table.io())
    val deleteManifests = snapshot.deleteManifests(table.io())
    
    // Count delete files per partition
    val deleteFilesByPartition = deleteManifests.asScala.flatMap { manifest =>
      val reader = org.apache.iceberg.ManifestFiles.readDeleteManifest(manifest, table.io(), null)
      reader.asScala.map(entry => (entry.partition().toString, 1))
    }.groupBy(_._1).mapValues(_.size)
    
    // Compact partitions where delete_files > 10 per data file (read amplification > 10x)
    // Priority: most delete files first
    deleteFilesByPartition
      .filter { case (_, deleteCount) => deleteCount > 50 }  // threshold
      .toSeq
      .sortBy(-_._2)  // worst first
      .take(20)        // budget: max 20 partitions per run
      .map { case (partition, deleteCount) =>
        PartitionCompactionTarget(partition, deleteCount)
      }
  }

  private def compactPartitions(
      spark: SparkSession, 
      table: Table, 
      targets: Seq[PartitionCompactionTarget]): Unit = {
    
    val today = LocalDate.now()
    val yesterday = today.minusDays(1)
    
    // Rewrite data files: merges data + applies deletes
    val result = SparkActions.get(spark)
      .rewriteDataFiles(table)
      // Only compact recent partitions (last 3 days most active)
      .filter(Expressions.greaterThanOrEqual("event_date", yesterday.toString))
      // Target output file size: 512MB (larger than streaming writes)
      .option("target-file-size-bytes", "536870912")
      // Partial compaction: stop after rewriting 5000 files
      .option("max-file-group-size-bytes", "10737418240")  // 10GB per group
      .option("partial-progress.enabled", "true")
      .option("partial-progress.max-commits", "10")
      // Use zOrder for query performance on common filter columns
      .sort(
        org.apache.iceberg.actions.SortOrder.builderFor(table.schema())
          .asc("ride_id")
          .asc("event_timestamp")
          .build()
      )
      .execute()
    
    filesRewritten.inc(result.rewrittenDataFilesCount())
    deleteFilesRemoved.inc(result.rewrittenBytesCount() / (128 * 1024 * 1024))  // approx
    
    println(s"Compaction complete: rewrote ${result.rewrittenDataFilesCount()} files, " +
      s"${result.rewrittenBytesCount() / (1024*1024*1024)}GB")
  }

  private def expireSnapshots(table: Table): Unit = {
    // Keep 3 days of snapshots for time-travel queries
    table.expireSnapshots()
      .expireOlderThan(System.currentTimeMillis() - (3L * 24 * 60 * 60 * 1000))
      .retainLast(100)
      .commit()
  }

  private def removeOrphanFiles(spark: SparkSession, table: Table): Unit = {
    // Remove files on S3 not referenced by any snapshot
    // These accumulate from failed Flink commits
    SparkActions.get(spark)
      .deleteOrphanFiles(table)
      .olderThan(System.currentTimeMillis() - (2L * 24 * 60 * 60 * 1000))  // 2 days old
      .execute()
  }

  private def updateMetrics(table: Table): Unit = {
    val snapshot = table.currentSnapshot()
    val summary = snapshot.summary()
    
    val totalDataFiles = summary.getOrDefault("total-data-files", "0").toLong
    val totalDeleteFiles = summary.getOrDefault("total-delete-files", "0").toLong
    
    val ratio = if (totalDataFiles > 0) totalDeleteFiles.toDouble / totalDataFiles else 0.0
    readAmplification.set(ratio)
  }

  case class PartitionCompactionTarget(partition: String, deleteFileCount: Int)
}
```

### Batch Corrections Job (Hourly)

```scala
package com.rideshare.pipeline.batch

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

/**
 * Hourly batch corrections: applies fare adjustments, fraud flags,
 * and late-arriving payment settlements.
 * 
 * Uses MERGE INTO which generates position deletes (more efficient
 * than equality deletes for bulk corrections).
 */
object BatchCorrectionsJob {

  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder()
      .appName("RideEvents-BatchCorrections")
      .config("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkCatalog")
      .config("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
      .config("spark.sql.catalog.glue.warehouse", "s3://rideshare-lakehouse/warehouse")
      .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
      .getOrCreate()

    // Load corrections from the corrections queue (populated by billing service)
    val corrections = spark.read
      .format("parquet")
      .load("s3://rideshare-corrections/pending/")
      .filter(col("processed") === false)

    // Late-arriving data: payment settlements from payment processor
    val settlements = spark.read
      .format("json")
      .load("s3://rideshare-settlements/hourly/")

    // ═══════════════════════════════════════════════════════════════
    // MERGE INTO: Fare Corrections
    // ═══════════════════════════════════════════════════════════════
    
    corrections.createOrReplaceTempView("fare_corrections")

    spark.sql("""
      MERGE INTO glue.ride_sharing.events.ride_events AS target
      USING fare_corrections AS source
      ON target.ride_id = source.ride_id 
         AND target.event_type = 'completed'
         AND target.event_date = source.ride_date
      WHEN MATCHED THEN UPDATE SET
        target.fare_adjustment = source.adjustment_amount,
        target.actual_fare = target.actual_fare + source.adjustment_amount,
        target.correction_timestamp = current_timestamp()
      WHEN NOT MATCHED THEN INSERT (
        ride_id, event_id, event_type, event_timestamp, ingestion_time,
        rider_id, driver_id, status, actual_fare, fare_adjustment,
        correction_timestamp, event_date
      ) VALUES (
        source.ride_id, source.correction_id, 'fare_correction', 
        current_timestamp(), current_timestamp(),
        source.rider_id, source.driver_id, 'corrected',
        source.adjustment_amount, source.adjustment_amount,
        current_timestamp(), source.ride_date
      )
    """)

    // ═══════════════════════════════════════════════════════════════
    // MERGE INTO: Fraud Flags
    // ═══════════════════════════════════════════════════════════════
    
    spark.sql("""
      MERGE INTO glue.ride_sharing.events.ride_events AS target
      USING (
        SELECT ride_id, ride_date 
        FROM glue.ride_sharing.fraud.flagged_rides
        WHERE flagged_at > current_timestamp() - INTERVAL 1 HOUR
      ) AS fraud
      ON target.ride_id = fraud.ride_id AND target.event_date = fraud.ride_date
      WHEN MATCHED THEN UPDATE SET
        target.fraud_flag = true
    """)

    // ═══════════════════════════════════════════════════════════════
    // Late-Arriving Data Reconciliation
    // ═══════════════════════════════════════════════════════════════
    
    settlements.createOrReplaceTempView("payment_settlements")
    
    // Insert late-arriving settlement events (these rides may be days old)
    spark.sql("""
      INSERT INTO glue.ride_sharing.events.ride_events
      SELECT
        s.ride_id,
        concat('settlement-', s.settlement_id) as event_id,
        'payment_settled' as event_type,
        s.settlement_timestamp as event_timestamp,
        current_timestamp() as ingestion_time,
        r.rider_id,
        r.driver_id,
        'settled' as status,
        r.pickup_lat, r.pickup_lng, r.dropoff_lat, r.dropoff_lng,
        null as current_lat, null as current_lng,
        r.estimated_fare,
        s.final_amount as actual_fare,
        r.surge_multiplier,
        null as fare_adjustment,
        false as fraud_flag,
        null as correction_timestamp,
        CAST(s.settlement_timestamp AS DATE) as event_date
      FROM payment_settlements s
      JOIN glue.ride_sharing.events.ride_events r
        ON s.ride_id = r.ride_id AND r.event_type = 'completed'
      WHERE NOT EXISTS (
        SELECT 1 FROM glue.ride_sharing.events.ride_events e
        WHERE e.ride_id = s.ride_id AND e.event_type = 'payment_settled'
      )
    """)

    spark.stop()
  }
}
```

---

## Production Operations

### Backpressure Handling

```
┌───────────────────────────────────────────────────────────────────┐
│  BACKPRESSURE CASCADE AND MITIGATION                              │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Root cause: S3 latency spike → Writer buffers fill →             │
│              Checkpoint takes too long → Barrier stalls →         │
│              Kafka consumer lag increases                          │
│                                                                   │
│  Mitigation layers:                                               │
│                                                                   │
│  1. Unaligned checkpoints (barriers don't wait for processing)    │
│  2. S3 write retry with circuit breaker (fail fast)               │
│  3. Writer buffer limits (spill to local disk, not OOM)           │
│  4. Kafka consumer lag alert → auto-scale Flink TaskManagers      │
│  5. Rate limiter on source if lag > 10 minutes                    │
│                                                                   │
│  Monitoring:                                                      │
│  • flink_taskmanager_job_task_backPressuredTimeMsPerSecond        │
│  • kafka_consumer_lag_records (by partition)                       │
│  • iceberg_commit_duration_ms                                     │
│  • s3_put_latency_p99                                             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Ordering Guarantees

The pipeline provides **per-key eventual consistency** with the following guarantees:

1. **Within a checkpoint**: All events for the same `ride_id` in one checkpoint window are written atomically
2. **Across checkpoints**: Snapshots are strictly ordered; readers see consistent state
3. **Out-of-order events**: Handled at read time via `event_timestamp` ordering in queries
4. **Cross-key ordering**: Not guaranteed (unnecessary for this use case)

```sql
-- Reader query pattern: always get latest state per ride
SELECT * FROM ride_events
WHERE ride_id = 'ride-123'
  AND event_date = '2024-01-15'
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY ride_id, event_type 
  ORDER BY event_timestamp DESC
) = 1;
```

---

## Monitoring Dashboard

### Key Metrics and Alerts

```yaml
# Prometheus alerting rules
groups:
  - name: iceberg_streaming_upserts
    rules:
      # Write path health
      - alert: FlinkCheckpointDurationHigh
        expr: flink_job_lastCheckpointDuration > 120000  # >2 min
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Checkpoint taking too long - risk of timeout"

      - alert: IcebergCommitFailures
        expr: rate(iceberg_commit_failures_total[5m]) > 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Iceberg commits failing - data freshness degrading"

      - alert: KafkaConsumerLagCritical
        expr: kafka_consumer_lag_records > 5000000  # 5M records behind
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Consumer lag critical - streaming freshness >5 min"

      # Read amplification (compaction health)
      - alert: ReadAmplificationHigh
        expr: table_read_amplification_ratio > 15
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Delete file accumulation high - compaction may be failing"

      - alert: ReadAmplificationCritical
        expr: table_read_amplification_ratio > 50
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Read amplification critical - queries will timeout"

      # File management
      - alert: SmallFilesAccumulating
        expr: iceberg_table_data_files_count > 500000
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Too many small files - plan metadata overhead"

      - alert: CompactionJobFailed
        expr: time() - compaction_last_success_timestamp > 3600  # 1 hour
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Compaction hasn't run in 1 hour - urgent"

      # S3 health
      - alert: S3WriteLatencyHigh
        expr: histogram_quantile(0.99, s3_put_duration_seconds) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "S3 write latency elevated - checkpoint risk"
```

### Grafana Dashboard Panels

```
┌─────────────────────────────────────────────────────────────────────┐
│  STREAMING UPSERTS - OPERATIONAL DASHBOARD                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Row 1: Throughput                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │Events/sec    │ │Bytes Written │ │Commits/min   │ │Consumer   │  │
│  │  1,023,456   │ │  2.1 GB/min  │ │     1.0      │ │Lag: 12s   │  │
│  │  ████████▓   │ │  ████████    │ │  ██          │ │ █         │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
│                                                                     │
│  Row 2: Data Quality                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │Duplicates    │ │Out-of-Order  │ │Late Arrivals │ │Dedup Hit  │  │
│  │Dropped: 0.1% │ │Events: 2.3%  │ │   450/min    │ │Rate: 0.1% │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
│                                                                     │
│  Row 3: Table Health                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │Data Files    │ │Delete Files  │ │Read Amp.     │ │Table Size │  │
│  │  142,000     │ │   8,500      │ │    5.2x      │ │  98.7 TB  │  │
│  │  (target<200k)│ │  (target<10k)│ │ (target<10x) │ │           │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
│                                                                     │
│  Row 4: Compaction                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │Last Run      │ │Files Merged  │ │Duration      │ │Next Run   │  │
│  │  8 min ago   │ │   2,340      │ │  7m 23s      │ │  in 7 min │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Kubernetes Deployment

### Flink Job Deployment

```yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: ride-events-upsert
  namespace: data-streaming
spec:
  image: rideshare/flink-iceberg:1.18.1-v42
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.backend: rocksdb
    state.backend.rocksdb.memory.managed: "true"
    state.checkpoints.dir: s3://rideshare-checkpoints/flink/ride-events-upsert/
    state.savepoints.dir: s3://rideshare-savepoints/flink/ride-events-upsert/
    execution.checkpointing.interval: "60000"
    execution.checkpointing.mode: EXACTLY_ONCE
    execution.checkpointing.unaligned.enabled: "true"
    restart-strategy: exponential-delay
    restart-strategy.exponential-delay.initial-backoff: 1s
    restart-strategy.exponential-delay.max-backoff: 60s
    # Memory tuning for high-throughput state
    taskmanager.memory.managed.fraction: "0.7"
    taskmanager.memory.network.fraction: "0.15"
    # S3 filesystem
    s3.access-key: "${AWS_ACCESS_KEY}"
    s3.secret-key: "${AWS_SECRET_KEY}"
    s3.endpoint: "https://s3.us-east-1.amazonaws.com"
  serviceAccount: flink-operator
  jobManager:
    resource:
      memory: "8Gi"
      cpu: 4
    replicas: 2  # HA
  taskManager:
    resource:
      memory: "32Gi"
      cpu: 8
    replicas: 128  # 128 TMs × 4 slots = 512 parallelism
    podTemplate:
      spec:
        tolerations:
          - key: "dedicated"
            operator: "Equal"
            value: "flink"
            effect: "NoSchedule"
        nodeSelector:
          node-type: flink-compute
        containers:
          - name: flink-main-container
            volumeMounts:
              - name: rocksdb-storage
                mountPath: /opt/flink/rocksdb
        volumes:
          - name: rocksdb-storage
            ephemeral:
              volumeClaimTemplate:
                spec:
                  accessModes: ["ReadWriteOnce"]
                  storageClassName: gp3-iops
                  resources:
                    requests:
                      storage: 200Gi
  job:
    jarURI: s3://rideshare-artifacts/flink-jobs/ride-events-upsert-v42.jar
    entryClass: com.rideshare.pipeline.streaming.RideEventStreamingUpsertJob
    parallelism: 512
    upgradeMode: savepoint
    state: running
```

### Compaction CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ride-events-compaction
  namespace: data-batch
spec:
  schedule: "*/15 * * * *"  # Every 15 minutes
  concurrencyPolicy: Forbid  # Never overlap
  successfulJobsHistoryLimit: 5
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      activeDeadlineSeconds: 900  # Kill if running > 15 min
      template:
        spec:
          serviceAccountName: spark-compaction
          nodeSelector:
            node-type: spark-compute
          containers:
            - name: compaction
              image: rideshare/spark-iceberg:3.5.0-v18
              command: ["spark-submit"]
              args:
                - "--master=k8s://https://kubernetes.default:443"
                - "--deploy-mode=cluster"
                - "--conf=spark.executor.instances=50"
                - "--conf=spark.executor.memory=16g"
                - "--conf=spark.executor.cores=4"
                - "--conf=spark.driver.memory=8g"
                - "--conf=spark.kubernetes.namespace=data-batch"
                - "--class=com.rideshare.pipeline.compaction.CompactionService"
                - "s3://rideshare-artifacts/spark-jobs/compaction-v18.jar"
              resources:
                requests:
                  memory: "10Gi"
                  cpu: "2"
                limits:
                  memory: "12Gi"
                  cpu: "4"
          restartPolicy: OnFailure
```

---

## Failure Recovery Playbook

### Scenario 1: Flink Job Crash

```
Symptom: Job restarts, consumer lag spikes
Recovery: Automatic — restarts from last checkpoint
Duration: 30-90 seconds
Data loss: Zero (exactly-once)
Action needed: None (monitor that lag recovers within 5 min)
```

### Scenario 2: Checkpoint Timeout (S3 Slow)

```
Symptom: Checkpoint duration > 5 min, then failure
Recovery: 
  1. Automatic restart from previous checkpoint
  2. If repeated: increase checkpoint timeout
  3. If S3 degraded: check AWS status, consider regional failover
Mitigation: Unaligned checkpoints reduce sensitivity to S3 latency
```

### Scenario 3: Iceberg Commit Conflict

```
Symptom: CommitFailedException in logs
Cause: Compaction and streaming commit racing on same snapshot
Recovery: Built-in retry (10 attempts with backoff)
If persistent: 
  1. Check if compaction is running too aggressively
  2. Increase commit.retry.num-retries
  3. Stagger compaction to avoid hot partitions
```

### Scenario 4: Compaction Falling Behind

```
Symptom: read_amplification_ratio climbing over hours
Cause: Write rate exceeds compaction throughput
Recovery:
  1. Scale compaction executors (50 → 150)
  2. Reduce compaction interval (15min → 5min)
  3. Increase partial-progress.max-commits
  4. Emergency: run full compaction during low-traffic period
Alert threshold: ratio > 20 = page on-call
```

### Scenario 5: Corrupt Snapshot (Catalog Issue)

```
Symptom: Readers get FileNotFoundException
Cause: Snapshot references deleted/moved files
Recovery:
  1. Roll back to previous snapshot:
     CALL glue.system.rollback_to_snapshot('ride_sharing.events.ride_events', <snapshot_id>)
  2. Identify and fix root cause (usually premature orphan cleanup)
  3. Re-run streaming from that point (Flink savepoint)
```

---

## Scale Numbers: Production Reality

| Metric | Value | Notes |
|--------|-------|-------|
| Events ingested | 1M/sec | 256 Kafka partitions |
| Bytes written | 2.1 GB/min | After compression (Zstd) |
| Commit frequency | 1/min | One snapshot per checkpoint |
| Files per commit | ~250 data + ~250 equality deletes | 512 writers, some co-locate |
| Table size | 98.7 TB | 14 days hot, 90 days warm |
| Total data files | 142,000 | After compaction |
| Total delete files | 8,500 | Between compaction runs |
| Read amplification | 5.2x | Target: < 10x |
| Concurrent readers | 1,000+ | Trino + Spark + Flink |
| Query latency (point) | 2-5 sec | Single ride lookup |
| Query latency (scan) | 30-120 sec | Day-level aggregation |
| Compaction throughput | 500 GB / 15 min | 50 Spark executors |
| Flink state size | 24 GB | Dedup bloom filters |
| Recovery time | 30-90 sec | Checkpoint restore |
| End-to-end latency | 60-120 sec | Event → queryable |

---

## Key Design Decisions and Tradeoffs

### Why 60-Second Checkpoint Interval?

| Interval | Pros | Cons |
|----------|------|------|
| 10s | Fresher data (10s latency) | 6 commits/min, massive small file problem, catalog pressure |
| 60s | Good balance (60s latency) | Acceptable freshness for analytics |
| 300s | Fewer files, less catalog load | 5-min data staleness, larger loss window |

**Decision**: 60s. Analytics users tolerate 1-minute staleness. Operational dashboards use Kafka directly for sub-second needs.

### Why Merge-on-Read (Not Copy-on-Write)?

Copy-on-Write rewrites entire data files on every update. At 1M events/sec, this would mean rewriting terabytes every minute. MoR writes small delete files and defers merging to read time or compaction.

**Cost**: Readers do more work (merging). **Mitigation**: Aggressive compaction keeps read amplification < 10x.

### Why Equality Deletes (Not Position Deletes) for Streaming?

Streaming writers don't know the physical position of existing rows. They only know "delete all rows where ride_id=X and event_id=Y." This is an equality delete. Position deletes require a full scan to find row positions — impossible at streaming speeds.

### Why Separate Compaction (Not Inline)?

Inline compaction during streaming writes would cause unpredictable latency spikes and checkpoint timeouts. Decoupling compaction to an async Spark job provides:
- Predictable streaming latency
- Independent scaling
- Budget-aware partial compaction
- No risk of blocking the write path
