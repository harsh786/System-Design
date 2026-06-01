# Real-Time Fraud Detection Feature Store on Apache Iceberg

## The Production Problem

A Tier-1 bank processes **10 billion transaction events per day** across credit cards, wire transfers,
ACH, and P2P payments. Their fraud detection ML models require:

1. **Real-time features** — computed within seconds of a transaction (e.g., "number of transactions in last 5 minutes for this card")
2. **Historical behavioral features** — aggregated over days/weeks/months (e.g., "average weekend spend over 90 days")
3. **Feature history** — complete point-in-time feature values for model training (no data leakage)
4. **Regulatory explainability** — ability to reproduce exact features used for any past fraud decision (OCC/FFIEC audit requirement)

```
SCALE REQUIREMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ Metric                    │ Target                         │
├───────────────────────────┼────────────────────────────────┤
│ Events ingested/day       │ 10 billion                     │
│ Peak events/second        │ 200,000                        │
│ Entity profiles (cards)   │ 100 million                    │
│ Features per entity       │ 500+                           │
│ Feature serving latency   │ < 50ms p99                     │
│ Feature freshness (RT)    │ < 5 seconds                    │
│ Feature freshness (batch) │ < 1 hour                       │
│ Feature history retention │ 7 years (regulatory)           │
│ Training data generation  │ < 30 minutes for 1 year window │
│ Point-in-time correctness │ 100% (zero data leakage)       │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Why Traditional Approaches Fail

### Option 1: Redis/DynamoDB Only (Online Feature Store)

```
PROBLEM: No history, no training data, no explainability

- Features overwritten on every update → no point-in-time reconstruction
- No efficient way to generate training datasets (full table scan of 100M entities)
- Cost: 100M entities × 500 features × 8 bytes = 400GB in Redis = $50K+/month
- No time travel → regulatory audit impossible
- No schema evolution → new features require migration coordination
```

### Option 2: Data Warehouse (Snowflake/BigQuery)

```
PROBLEM: Too slow for real-time, too expensive at scale

- Feature serving at 50ms p99? Impossible. Minimum ~500ms for simple lookups
- 10B events/day streaming ingest → $200K+/month in warehouse costs
- Row-level upserts extremely expensive (full micro-partition rewrites)
- Concurrency limits hit quickly with 200K reads/sec for model serving
```

### Option 3: Traditional Feature Store (Feast/Tecton on Hive)

```
PROBLEM: Hive tables can't handle concurrent streaming + batch + serving

- No ACID → streaming writes corrupt batch reads
- No row-level upserts → full partition rewrites for entity updates
- Partition coupling → must know partition scheme in every query
- Small files from streaming → query performance degrades within hours
- No time travel → point-in-time joins require complex self-managed snapshots
```

---

## Why Iceberg Solves This

```
ICEBERG FEATURE STORE ADVANTAGES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. MERGE-ON-READ (MoR) for streaming upserts
   → Flink writes small delta files (delete + insert) without rewriting data files
   → Sub-second write latency for 200K events/sec
   → Background compaction merges deltas into base files asynchronously

2. EQUALITY DELETES for efficient upserts
   → "Delete where entity_id = X" as metadata, not physical rewrite
   → Combined with new insert → logical upsert without copy-on-write cost

3. HIDDEN PARTITIONING with bucket()
   → bucket(entity_id, 512) distributes 100M entities across 512 buckets
   → Point lookups read exactly 1 bucket, not full table scan
   → No partition column in queries; Iceberg resolves automatically

4. TIME TRAVEL for point-in-time correctness
   → Training queries: SELECT * FROM features FOR SYSTEM_TIME AS OF '2024-01-15'
   → Regulatory audit: exact features at any historical moment
   → Zero data leakage in training data generation

5. SNAPSHOT ISOLATION for concurrent access
   → Flink streaming writes don't block Spark batch reads
   → Trino serving reads don't conflict with compaction
   → Multiple ML training jobs can read different snapshots simultaneously

6. SCHEMA EVOLUTION for feature iteration
   → Data scientists add new features without migration
   → Old snapshots retain old schema; new snapshots have new columns
   → No coordination between feature producers and consumers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    FRAUD DETECTION FEATURE STORE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────────┐      │
│  │   Payment    │     │                   KAFKA CLUSTER                           │      │
│  │   Gateway    │────▶│  transactions (200K/s, 32 partitions)                    │      │
│  │              │     │  enriched-events (features attached)                      │      │
│  └──────────────┘     └────────────┬─────────────────────────────────────────────┘      │
│                                    │                                                     │
│                    ┌───────────────┼────────────────────┐                               │
│                    │               │                    │                                │
│                    ▼               ▼                    ▼                                │
│  ┌─────────────────────┐  ┌──────────────┐  ┌──────────────────────┐                   │
│  │   FLINK CLUSTER     │  │   FLINK      │  │   FRAUD SCORING      │                   │
│  │   (Streaming Path)  │  │   (Window    │  │   SERVICE             │                   │
│  │                     │  │   Aggregator)│  │                      │                   │
│  │ • Parse events      │  │              │  │ • Reads features     │                   │
│  │ • Compute RT feats  │  │ • 5m/15m/1h  │  │   from Redis         │                   │
│  │ • Upsert to Iceberg │  │   windows    │  │ • Calls ML model     │                   │
│  │ • Publish to Redis  │  │ • Upsert to  │  │ • Returns score      │                   │
│  │                     │  │   Iceberg    │  │                      │                   │
│  └──────────┬──────────┘  └──────┬───────┘  └──────────┬───────────┘                   │
│             │                    │                      │                                │
│             │                    │                      │  Feature Read                  │
│             ▼                    ▼                      ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐                │
│  │                         REDIS CLUSTER                                │                │
│  │           (Online Feature Serving - 100M entities)                   │                │
│  │           TTL: 24h │ Refresh: on every Flink upsert                  │                │
│  └─────────────────────────────────────────────────────────────────────┘                │
│             │                    │                                                       │
│             │ Async write-through│                                                       │
│             ▼                    ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐                │
│  │                     S3 (ICEBERG TABLES)                              │                │
│  │                                                                      │                │
│  │  ┌───────────────────────────┐  ┌────────────────────────────────┐  │                │
│  │  │ fraud.realtime_features   │  │ fraud.window_features          │  │                │
│  │  │ (MoR, bucket by entity)  │  │ (MoR, bucket by entity)       │  │                │
│  │  │ Flink streaming upserts  │  │ Flink window aggregations     │  │                │
│  │  └───────────────────────────┘  └────────────────────────────────┘  │                │
│  │                                                                      │                │
│  │  ┌───────────────────────────┐  ┌────────────────────────────────┐  │                │
│  │  │ fraud.batch_features      │  │ fraud.feature_snapshots        │  │                │
│  │  │ (CoW, daily Spark job)   │  │ (append-only, training data)  │  │                │
│  │  │ 90-day rolling aggs      │  │ point-in-time feature values  │  │                │
│  │  └───────────────────────────┘  └────────────────────────────────┘  │                │
│  │                                                                      │                │
│  └─────────────────────────────────────────────────────────────────────┘                │
│                                    │                                                     │
│                    ┌───────────────┼────────────────────┐                               │
│                    │               │                    │                                │
│                    ▼               ▼                    ▼                                │
│  ┌─────────────────────┐  ┌──────────────┐  ┌──────────────────────┐                   │
│  │   SPARK CLUSTER     │  │   TRINO      │  │   AIRFLOW            │                   │
│  │   (Batch Path)      │  │   (Serving)  │  │   (Orchestration)    │                   │
│  │                     │  │              │  │                      │                   │
│  │ • Daily aggregation │  │ • Low-lat    │  │ • Compaction trigger │                   │
│  │ • Training data gen │  │   feature    │  │ • Batch job schedule │                   │
│  │ • Backfill          │  │   reads      │  │ • Freshness alerts   │                   │
│  │ • Feature validation│  │ • Ad-hoc     │  │ • Snapshot mgmt      │                   │
│  │                     │  │   analysis   │  │                      │                   │
│  └─────────────────────┘  └──────────────┘  └──────────────────────┘                   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Table Design & DDL

### Table 1: Real-Time Features (MoR with Equality Deletes)

```sql
-- Real-time features: updated on every transaction
-- Merge-on-Read: writes are fast (delta files), reads merge at query time
-- Compaction runs every 10 minutes to keep read amplification bounded

CREATE TABLE fraud.realtime_features (
    entity_id           STRING      COMMENT 'Card number hash (SHA-256)',
    entity_type         STRING      COMMENT 'CARD|ACCOUNT|DEVICE|IP',
    
    -- Counters (updated in real-time)
    txn_count_1m        BIGINT      COMMENT 'Transactions in last 1 minute',
    txn_count_5m        BIGINT      COMMENT 'Transactions in last 5 minutes',
    txn_count_15m       BIGINT      COMMENT 'Transactions in last 15 minutes',
    txn_count_1h        BIGINT      COMMENT 'Transactions in last 1 hour',
    txn_amount_sum_5m   DECIMAL(18,2) COMMENT 'Total amount in last 5 minutes',
    txn_amount_sum_1h   DECIMAL(18,2) COMMENT 'Total amount in last 1 hour',
    txn_amount_max_1h   DECIMAL(18,2) COMMENT 'Max single transaction in last 1 hour',
    
    -- Velocity features
    distinct_merchants_1h    INT    COMMENT 'Unique merchants in last 1 hour',
    distinct_countries_1h    INT    COMMENT 'Unique countries in last 1 hour',
    distinct_mcc_codes_1h    INT    COMMENT 'Unique MCC codes in last 1 hour',
    
    -- Behavioral deviation
    amount_zscore_vs_30d     DOUBLE COMMENT 'Z-score of current txn vs 30-day mean',
    time_since_last_txn_sec  BIGINT COMMENT 'Seconds since previous transaction',
    geo_distance_from_last   DOUBLE COMMENT 'KM from last transaction location',
    
    -- Metadata
    last_updated_ts     TIMESTAMP   COMMENT 'Last feature update time',
    last_txn_id         STRING      COMMENT 'Transaction that triggered update',
    feature_version     INT         COMMENT 'Schema version for backward compat',
    
    -- Partition source (hidden)
    event_date          DATE        COMMENT 'Date for lifecycle management'
)
USING iceberg
PARTITIONED BY (
    bucket(512, entity_id),      -- High-cardinality: distribute across 512 buckets
    days(event_date)             -- Daily partitioning for lifecycle/compaction
)
TBLPROPERTIES (
    -- Merge-on-Read configuration
    'write.delete.mode'          = 'merge-on-read',
    'write.update.mode'          = 'merge-on-read',
    'write.merge.mode'           = 'merge-on-read',
    
    -- Format settings
    'write.format.default'       = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.parquet.row-group-size-bytes' = '134217728',  -- 128MB row groups
    
    -- Metadata management
    'write.metadata.delete-after-commit.enabled' = 'true',
    'write.metadata.previous-versions-max'       = '100',
    
    -- Delete file settings (critical for MoR performance)
    'write.delete.granularity'   = 'partition',
    
    -- Snapshot expiration
    'history.expire.max-snapshot-age-ms' = '604800000',  -- 7 days
    'history.expire.min-snapshots-to-keep' = '100',
    
    -- Compaction targets
    'write.target-file-size-bytes'       = '536870912',  -- 512MB target files
    'read.split.target-size'             = '134217728'   -- 128MB split size
);
```

### Table 2: Window Aggregation Features (MoR)

```sql
CREATE TABLE fraud.window_features (
    entity_id           STRING,
    entity_type         STRING,
    window_start        TIMESTAMP,
    window_end          TIMESTAMP,
    window_duration_min INT         COMMENT '5, 15, 60, 360, 1440',
    
    -- Aggregated features per window
    txn_count           BIGINT,
    txn_amount_sum      DECIMAL(18,2),
    txn_amount_avg      DECIMAL(18,2),
    txn_amount_stddev   DOUBLE,
    txn_amount_min      DECIMAL(18,2),
    txn_amount_max      DECIMAL(18,2),
    
    -- Category breakdowns (stored as maps for flexibility)
    amount_by_mcc       MAP<STRING, DECIMAL(18,2)>,
    count_by_country    MAP<STRING, BIGINT>,
    count_by_channel    MAP<STRING, BIGINT>,
    
    -- Derived features
    is_first_txn_in_window  BOOLEAN,
    pct_declined            DOUBLE,
    unique_merchants        INT,
    
    -- Metadata
    computed_at         TIMESTAMP,
    source_watermark    TIMESTAMP
)
USING iceberg
PARTITIONED BY (
    bucket(512, entity_id),
    window_duration_min,
    days(window_end)
)
TBLPROPERTIES (
    'write.delete.mode'     = 'merge-on-read',
    'write.update.mode'     = 'merge-on-read',
    'write.format.default'  = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.target-file-size-bytes'    = '268435456'  -- 256MB
);
```

### Table 3: Batch Features (Copy-on-Write, Daily)

```sql
CREATE TABLE fraud.batch_features (
    entity_id           STRING,
    entity_type         STRING,
    computation_date    DATE        COMMENT 'Date features were computed for',
    
    -- Long-horizon aggregates (not feasible in streaming)
    avg_daily_spend_30d      DECIMAL(18,2),
    avg_daily_spend_90d      DECIMAL(18,2),
    avg_txn_amount_30d       DECIMAL(18,2),
    stddev_txn_amount_30d    DOUBLE,
    max_single_txn_30d       DECIMAL(18,2),
    total_spend_30d          DECIMAL(18,2),
    total_spend_90d          DECIMAL(18,2),
    
    -- Behavioral patterns
    pct_weekend_spend_90d        DOUBLE,
    pct_international_90d        DOUBLE,
    pct_online_vs_pos_90d        DOUBLE,
    most_common_merchant_cat     STRING,
    typical_txn_hour_mode        INT,
    typical_txn_dow_mode         INT,
    
    -- Risk indicators
    days_since_last_dispute      INT,
    dispute_count_365d           INT,
    chargeback_count_365d        INT,
    account_age_days             INT,
    
    -- Model scores from previous runs
    prev_fraud_score             DOUBLE,
    prev_risk_tier               STRING,
    
    -- Metadata
    computed_at         TIMESTAMP,
    model_version       STRING,
    row_count_input     BIGINT      COMMENT 'Txns used in computation (data quality)'
)
USING iceberg
PARTITIONED BY (
    bucket(256, entity_id),
    computation_date
)
TBLPROPERTIES (
    'write.delete.mode'     = 'copy-on-write',   -- Batch: full rewrite is fine
    'write.update.mode'     = 'copy-on-write',
    'write.format.default'  = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.target-file-size-bytes'    = '536870912'
);
```

### Table 4: Feature Snapshots (Append-Only, Training Data)

```sql
CREATE TABLE fraud.feature_snapshots (
    -- Point-in-time feature snapshot taken at scoring time
    snapshot_ts         TIMESTAMP   COMMENT 'Exact time features were read for scoring',
    entity_id           STRING,
    txn_id              STRING      COMMENT 'Transaction being scored',
    
    -- All features flattened (denormalized for training efficiency)
    features            MAP<STRING, DOUBLE> COMMENT 'Feature name → value at scoring time',
    
    -- Labels (populated async after adjudication)
    is_fraud            BOOLEAN     COMMENT 'NULL until adjudicated',
    fraud_type          STRING      COMMENT 'first_party|third_party|friendly|NULL',
    adjudication_ts     TIMESTAMP,
    
    -- Lineage
    model_version       STRING,
    score_produced      DOUBLE,
    decision            STRING      COMMENT 'APPROVE|DECLINE|REVIEW'
)
USING iceberg
PARTITIONED BY (
    days(snapshot_ts),
    bucket(128, entity_id)
)
TBLPROPERTIES (
    'write.format.default'  = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.target-file-size-bytes'    = '536870912',
    -- Long retention for regulatory
    'history.expire.max-snapshot-age-ms' = '220752000000'  -- 7 years
);
```

---

## Flink Streaming Pipeline (Java)

### Streaming Upserts into Iceberg with Exactly-Once Semantics

```java
package com.bank.fraud.features;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.MapState;
import org.apache.flink.api.common.state.MapStateDescriptor;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.table.api.Schema;
import org.apache.flink.table.api.Table;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;
import org.apache.flink.util.Collector;
import org.apache.iceberg.flink.FlinkCatalog;
import org.apache.iceberg.flink.TableLoader;
import org.apache.iceberg.flink.sink.FlinkSink;

import java.time.Duration;
import java.time.Instant;
import java.util.*;

/**
 * Flink job that:
 * 1. Consumes transaction events from Kafka (200K/sec)
 * 2. Computes real-time features per entity using keyed state
 * 3. Upserts features into Iceberg MoR table (equality deletes)
 * 4. Publishes fresh features to Redis for online serving
 *
 * Exactly-once: Flink checkpointing + Iceberg's atomic commits
 * Late arrivals: Allowed up to 5 minutes, watermark-based
 */
public class RealtimeFeaturePipeline {

    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // ============================================================
        // Checkpoint configuration (critical for exactly-once)
        // ============================================================
        env.enableCheckpointing(60_000, CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000);
        env.getCheckpointConfig().setCheckpointTimeout(300_000);
        env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);
        env.getCheckpointConfig().setTolerableCheckpointFailureNumber(3);
        // Retain checkpoints on cancellation for manual recovery
        env.getCheckpointConfig().enableExternalizedCheckpoints(
            ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION
        );
        // Incremental checkpoints for RocksDB (100M keys)
        env.setStateBackend(new EmbeddedRocksDBStateBackend(true));
        env.getCheckpointConfig().setCheckpointStorage("s3://fraud-checkpoints/flink/");

        // Parallelism: match Kafka partitions
        env.setParallelism(32);

        StreamTableEnvironment tableEnv = StreamTableEnvironment.create(env);

        // ============================================================
        // Register Iceberg catalog
        // ============================================================
        Map<String, String> catalogProps = new HashMap<>();
        catalogProps.put("type", "iceberg");
        catalogProps.put("catalog-type", "rest");
        catalogProps.put("uri", "http://iceberg-rest-catalog:8181");
        catalogProps.put("warehouse", "s3://fraud-lakehouse/warehouse");
        catalogProps.put("io-impl", "org.apache.iceberg.aws.s3.S3FileIO");
        catalogProps.put("s3.endpoint", "https://s3.us-east-1.amazonaws.com");

        tableEnv.executeSql(
            "CREATE CATALOG iceberg_catalog WITH (" +
            "  'type' = 'iceberg'," +
            "  'catalog-type' = 'rest'," +
            "  'uri' = 'http://iceberg-rest-catalog:8181'," +
            "  'warehouse' = 's3://fraud-lakehouse/warehouse'" +
            ")"
        );

        // ============================================================
        // Kafka source with watermarks
        // ============================================================
        tableEnv.executeSql(
            "CREATE TEMPORARY TABLE kafka_transactions (" +
            "  txn_id STRING," +
            "  entity_id STRING," +
            "  entity_type STRING," +
            "  amount DECIMAL(18,2)," +
            "  currency STRING," +
            "  merchant_id STRING," +
            "  merchant_mcc STRING," +
            "  merchant_country STRING," +
            "  channel STRING," +
            "  pos_entry_mode STRING," +
            "  txn_timestamp TIMESTAMP(3)," +
            "  card_present BOOLEAN," +
            "  latitude DOUBLE," +
            "  longitude DOUBLE," +
            "  event_time TIMESTAMP(3) METADATA FROM 'timestamp'," +
            "  WATERMARK FOR txn_timestamp AS txn_timestamp - INTERVAL '5' MINUTE" +
            ") WITH (" +
            "  'connector' = 'kafka'," +
            "  'topic' = 'transactions'," +
            "  'properties.bootstrap.servers' = 'kafka-broker:9092'," +
            "  'properties.group.id' = 'fraud-feature-pipeline'," +
            "  'scan.startup.mode' = 'group-offsets'," +
            "  'format' = 'avro-confluent'," +
            "  'avro-confluent.url' = 'http://schema-registry:8081'" +
            ")"
        );

        // ============================================================
        // DataStream API for stateful feature computation
        // ============================================================
        DataStream<Transaction> txnStream = env
            .fromSource(kafkaSource(), watermarkStrategy(), "kafka-transactions")
            .name("kafka-source")
            .uid("kafka-source");

        DataStream<EntityFeatures> featureStream = txnStream
            .keyBy(Transaction::getEntityId)
            .process(new FeatureComputeFunction())
            .name("feature-computation")
            .uid("feature-computation");

        // ============================================================
        // Sink to Iceberg (equality delete + insert = upsert)
        // ============================================================
        TableLoader tableLoader = TableLoader.fromCatalog(
            catalogLoader(), org.apache.iceberg.catalog.TableIdentifier.of("fraud", "realtime_features")
        );

        FlinkSink.forRowData(featureStream.map(EntityFeatures::toRowData))
            .tableLoader(tableLoader)
            .overwrite(false)
            .equalityFieldColumns(Arrays.asList("entity_id", "entity_type"))
            .upsert(true)  // Enable upsert mode: equality delete + insert
            .distributionMode(DistributionMode.HASH)  // Match bucket partitioning
            .flinkConf(flinkConf())
            .append();

        // ============================================================
        // Side output to Redis for online serving
        // ============================================================
        featureStream
            .addSink(new RedisSinkFunction())
            .name("redis-sink")
            .uid("redis-sink");

        env.execute("fraud-realtime-feature-pipeline");
    }

    /**
     * Stateful feature computation using Flink keyed state.
     * Maintains sliding window counters per entity in RocksDB state.
     */
    static class FeatureComputeFunction
        extends KeyedProcessFunction<String, Transaction, EntityFeatures> {

        // Sliding window state: timestamp → transaction details
        private transient MapState<Long, TransactionSummary> txnWindowState;
        // Current aggregated features
        private transient ValueState<EntityFeatures> currentFeatures;
        // Last known location for geo-distance
        private transient ValueState<GeoPoint> lastLocation;

        @Override
        public void open(Configuration parameters) {
            txnWindowState = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("txn-window",
                    Long.class, TransactionSummary.class)
            );
            currentFeatures = getRuntimeContext().getState(
                new ValueStateDescriptor<>("current-features", EntityFeatures.class)
            );
            lastLocation = getRuntimeContext().getState(
                new ValueStateDescriptor<>("last-location", GeoPoint.class)
            );
        }

        @Override
        public void processElement(Transaction txn, Context ctx, Collector<EntityFeatures> out)
            throws Exception {

            long txnTs = txn.getTimestamp().toEpochMilli();

            // Store transaction in window state
            txnWindowState.put(txnTs, new TransactionSummary(
                txn.getAmount(), txn.getMerchantId(), txn.getMerchantCountry(),
                txn.getMerchantMcc(), txn.getChannel()
            ));

            // Register cleanup timer (evict transactions older than 1 hour)
            ctx.timerService().registerEventTimeTimer(txnTs + Duration.ofHours(1).toMillis());

            // Compute features from current window state
            EntityFeatures features = computeFeatures(txn, txnTs);

            // Compute geo-distance from last known location
            GeoPoint lastGeo = lastLocation.value();
            if (lastGeo != null && txn.getLatitude() != 0) {
                features.setGeoDistanceFromLast(
                    haversine(lastGeo.lat, lastGeo.lon, txn.getLatitude(), txn.getLongitude())
                );
            }
            if (txn.getLatitude() != 0) {
                lastLocation.update(new GeoPoint(txn.getLatitude(), txn.getLongitude()));
            }

            // Update and emit
            currentFeatures.update(features);
            out.collect(features);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<EntityFeatures> out)
            throws Exception {
            // Evict expired transactions from window state
            long cutoff = timestamp - Duration.ofHours(1).toMillis();
            List<Long> toRemove = new ArrayList<>();
            for (Map.Entry<Long, TransactionSummary> entry : txnWindowState.entries()) {
                if (entry.getKey() < cutoff) {
                    toRemove.add(entry.getKey());
                }
            }
            toRemove.forEach(ts -> {
                try { txnWindowState.remove(ts); } catch (Exception e) { /* log */ }
            });
        }

        private EntityFeatures computeFeatures(Transaction txn, long txnTs) throws Exception {
            long now = txnTs;
            long oneMin = now - 60_000;
            long fiveMin = now - 300_000;
            long fifteenMin = now - 900_000;
            long oneHour = now - 3_600_000;

            int count1m = 0, count5m = 0, count15m = 0, count1h = 0;
            double sum5m = 0, sum1h = 0, max1h = 0;
            Set<String> merchants1h = new HashSet<>();
            Set<String> countries1h = new HashSet<>();
            Set<String> mcc1h = new HashSet<>();
            long prevTxnTs = 0;

            for (Map.Entry<Long, TransactionSummary> entry : txnWindowState.entries()) {
                long ts = entry.getKey();
                TransactionSummary s = entry.getValue();

                if (ts >= oneHour) {
                    count1h++;
                    sum1h += s.amount;
                    max1h = Math.max(max1h, s.amount);
                    merchants1h.add(s.merchantId);
                    countries1h.add(s.country);
                    mcc1h.add(s.mcc);

                    if (ts >= fifteenMin) { count15m++; }
                    if (ts >= fiveMin) { count5m++; sum5m += s.amount; }
                    if (ts >= oneMin) { count1m++; }
                    if (ts < now && ts > prevTxnTs) { prevTxnTs = ts; }
                }
            }

            EntityFeatures f = new EntityFeatures();
            f.setEntityId(txn.getEntityId());
            f.setEntityType(txn.getEntityType());
            f.setTxnCount1m(count1m);
            f.setTxnCount5m(count5m);
            f.setTxnCount15m(count15m);
            f.setTxnCount1h(count1h);
            f.setTxnAmountSum5m(sum5m);
            f.setTxnAmountSum1h(sum1h);
            f.setTxnAmountMax1h(max1h);
            f.setDistinctMerchants1h(merchants1h.size());
            f.setDistinctCountries1h(countries1h.size());
            f.setDistinctMccCodes1h(mcc1h.size());
            f.setTimeSinceLastTxnSec(prevTxnTs > 0 ? (now - prevTxnTs) / 1000 : -1);
            f.setLastUpdatedTs(Instant.ofEpochMilli(now));
            f.setLastTxnId(txn.getTxnId());
            f.setFeatureVersion(3);
            f.setEventDate(LocalDate.ofInstant(Instant.ofEpochMilli(now), ZoneOffset.UTC));
            return f;
        }

        private double haversine(double lat1, double lon1, double lat2, double lon2) {
            double R = 6371.0; // Earth radius in km
            double dLat = Math.toRadians(lat2 - lat1);
            double dLon = Math.toRadians(lon2 - lon1);
            double a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                       Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                       Math.sin(dLon/2) * Math.sin(dLon/2);
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }
    }
}
```

### How Iceberg Equality Deletes Work (The Upsert Mechanism)

```
UPSERT FLOW (Merge-on-Read):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Flink checkpoint triggers Iceberg commit
         ┌─────────────────────────────────────────┐
         │  Commit contains:                        │
         │  • Equality Delete File (entity_id=X)   │  ← "Delete old version"
         │  • New Data File (entity_id=X, ...)     │  ← "Insert new version"
         └─────────────────────────────────────────┘

Step 2: Iceberg metadata updated atomically
         snap-003.avro
         ├── manifest-list-003.avro
         │   ├── manifest-new-data.avro     (new data files)
         │   └── manifest-new-deletes.avro  (equality delete files)
         └── (previous manifests unchanged)

Step 3: At read time, engine merges:
         Reader for bucket(entity_id) = 42:
         ┌─────────────┐     ┌──────────────────┐
         │  Data Files  │  -  │  Delete Files     │  =  Live Rows
         │  (all rows)  │     │  (entity_id=X)   │
         └─────────────┘     └──────────────────┘

         For entity_id=X: only the LATEST insert survives
         (older data files have matching equality delete)

Step 4: Compaction (background) physically merges:
         Before: 100 data files + 500 delete files (high read amplification)
         After:  20 data files + 0 delete files (fast reads)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Spark Batch Feature Computation

```python
"""
Daily batch feature computation job.
Runs at 02:00 UTC, computes 30/90-day rolling aggregates for all 100M entities.
Uses Iceberg time-travel to ensure point-in-time correctness.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import date, timedelta

spark = (SparkSession.builder
    .appName("fraud-batch-features")
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.iceberg.type", "rest")
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest-catalog:8181")
    .config("spark.sql.catalog.iceberg.warehouse", "s3://fraud-lakehouse/warehouse")
    .config("spark.sql.catalog.iceberg.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    # Performance tuning for 10B events
    .config("spark.sql.shuffle.partitions", "2048")
    .config("spark.sql.adaptive.enabled", "true")
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    .config("spark.sql.iceberg.planning.preserve-data-grouping", "true")
    .getOrCreate())

computation_date = date.today() - timedelta(days=1)  # Features for yesterday
lookback_90d = computation_date - timedelta(days=90)
lookback_30d = computation_date - timedelta(days=30)

# ============================================================
# Read raw transactions (partitioned by day, only scan 90 days)
# ============================================================
raw_txns = (spark.read
    .format("iceberg")
    .load("iceberg.fraud.raw_transactions")
    .filter(F.col("txn_date").between(lookback_90d, computation_date))
    .filter(F.col("status") == "COMPLETED")  # Only settled transactions
)

print(f"Processing {raw_txns.count():,} transactions for {computation_date}")

# ============================================================
# Compute 30-day and 90-day aggregates
# ============================================================
batch_features = (raw_txns
    .groupBy("entity_id", "entity_type")
    .agg(
        # 30-day aggregates
        F.avg(F.when(F.col("txn_date") >= lookback_30d, F.col("amount")))
            .alias("avg_txn_amount_30d"),
        F.stddev(F.when(F.col("txn_date") >= lookback_30d, F.col("amount")))
            .alias("stddev_txn_amount_30d"),
        F.max(F.when(F.col("txn_date") >= lookback_30d, F.col("amount")))
            .alias("max_single_txn_30d"),
        F.sum(F.when(F.col("txn_date") >= lookback_30d, F.col("amount")))
            .alias("total_spend_30d"),

        # 90-day aggregates
        F.sum(F.col("amount")).alias("total_spend_90d"),

        # Daily spend averages
        (F.sum(F.when(F.col("txn_date") >= lookback_30d, F.col("amount"))) / 30)
            .alias("avg_daily_spend_30d"),
        (F.sum(F.col("amount")) / 90).alias("avg_daily_spend_90d"),

        # Behavioral patterns (90-day window)
        (F.sum(F.when(F.dayofweek("txn_date").isin(1, 7), F.col("amount")))
         / F.sum(F.col("amount"))).alias("pct_weekend_spend_90d"),

        (F.sum(F.when(F.col("merchant_country") != "US", F.col("amount")))
         / F.sum(F.col("amount"))).alias("pct_international_90d"),

        (F.sum(F.when(F.col("channel") == "ONLINE", F.col("amount")))
         / F.sum(F.col("amount"))).alias("pct_online_vs_pos_90d"),

        # Mode calculations
        F.mode("merchant_mcc").alias("most_common_merchant_cat"),
        F.mode(F.hour("txn_timestamp")).alias("typical_txn_hour_mode"),
        F.mode(F.dayofweek("txn_date")).alias("typical_txn_dow_mode"),

        # Data quality
        F.count("*").alias("row_count_input"),
    )
    .withColumn("computation_date", F.lit(computation_date))
    .withColumn("computed_at", F.current_timestamp())
    .withColumn("model_version", F.lit("v3.2.1"))
)

# ============================================================
# Join with dispute/chargeback history
# ============================================================
disputes = (spark.read
    .format("iceberg")
    .load("iceberg.fraud.disputes")
    .filter(F.col("dispute_date") >= lookback_90d)
    .groupBy("entity_id")
    .agg(
        F.datediff(F.lit(computation_date), F.max("dispute_date")).alias("days_since_last_dispute"),
        F.count(F.when(F.col("dispute_date") >= computation_date - timedelta(days=365), True))
            .alias("dispute_count_365d"),
        F.count(F.when(
            (F.col("resolution") == "CHARGEBACK") &
            (F.col("dispute_date") >= computation_date - timedelta(days=365)), True))
            .alias("chargeback_count_365d"),
    )
)

batch_features = batch_features.join(disputes, "entity_id", "left")

# ============================================================
# Write to Iceberg (overwrite partition for this computation_date)
# ============================================================
(batch_features.writeTo("iceberg.fraud.batch_features")
    .overwritePartitions()  # Replace only this date's partition
    .option("fanout-enabled", "true")  # Write to multiple buckets in parallel
)

# ============================================================
# Generate training snapshots (point-in-time join)
# ============================================================
def generate_training_data(label_start: date, label_end: date):
    """
    Point-in-time correct training data:
    For each labeled transaction, get features AS THEY EXISTED at scoring time.
    Uses Iceberg time-travel to prevent data leakage.
    """
    labeled_txns = (spark.read
        .format("iceberg")
        .load("iceberg.fraud.feature_snapshots")
        .filter(F.col("snapshot_ts").between(label_start, label_end))
        .filter(F.col("is_fraud").isNotNull())  # Only adjudicated
    )

    # For batch features: use the computation_date BEFORE the transaction
    # This prevents leakage from same-day batch runs
    training_set = (labeled_txns
        .join(
            spark.read.format("iceberg").load("iceberg.fraud.batch_features"),
            (labeled_txns.entity_id == batch_features.entity_id) &
            (F.col("computation_date") == F.date_sub(F.to_date("snapshot_ts"), 1)),
            "left"
        )
    )

    (training_set.writeTo("iceberg.fraud.training_datasets")
        .partitionedBy(F.days("snapshot_ts"))
        .createOrReplace())

    return training_set

# Generate 6 months of training data
generate_training_data(
    computation_date - timedelta(days=180),
    computation_date
)

spark.stop()
```

---

## Trino Feature Serving Queries

```sql
-- ============================================================
-- QUERY 1: Real-time feature lookup for scoring (< 50ms target)
-- Uses bucket partition pruning: only reads 1 of 512 buckets
-- ============================================================

SELECT
    entity_id,
    txn_count_1m,
    txn_count_5m,
    txn_count_15m,
    txn_count_1h,
    txn_amount_sum_5m,
    txn_amount_sum_1h,
    txn_amount_max_1h,
    distinct_merchants_1h,
    distinct_countries_1h,
    geo_distance_from_last,
    time_since_last_txn_sec,
    last_updated_ts
FROM iceberg.fraud.realtime_features
WHERE entity_id = 'sha256_abc123def456'  -- Bucket pruning: reads 1/512 buckets
  AND entity_type = 'CARD'
  AND event_date = CURRENT_DATE;

-- Explain shows: Files scanned: ~2-5 (one bucket, one day)
-- vs full scan: 512 buckets × 365 days = 186,880 potential files


-- ============================================================
-- QUERY 2: Combined feature vector for ML scoring
-- Joins real-time + batch features for complete feature vector
-- ============================================================

SELECT
    rt.entity_id,
    -- Real-time features
    rt.txn_count_5m,
    rt.txn_count_1h,
    rt.txn_amount_sum_1h,
    rt.distinct_countries_1h,
    rt.geo_distance_from_last,
    -- Batch features (yesterday's computation)
    bf.avg_daily_spend_30d,
    bf.stddev_txn_amount_30d,
    bf.pct_international_90d,
    bf.pct_weekend_spend_90d,
    bf.days_since_last_dispute,
    -- Derived: z-score against historical baseline
    CASE
        WHEN bf.stddev_txn_amount_30d > 0
        THEN (rt.txn_amount_max_1h - bf.avg_txn_amount_30d) / bf.stddev_txn_amount_30d
        ELSE 0
    END AS amount_zscore
FROM iceberg.fraud.realtime_features rt
JOIN iceberg.fraud.batch_features bf
    ON rt.entity_id = bf.entity_id
    AND bf.computation_date = CURRENT_DATE - INTERVAL '1' DAY
WHERE rt.entity_id = 'sha256_abc123def456'
  AND rt.event_date = CURRENT_DATE;


-- ============================================================
-- QUERY 3: Regulatory explainability (time-travel)
-- "Show me exactly what features the model saw for txn X on date Y"
-- ============================================================

SELECT *
FROM iceberg.fraud.feature_snapshots
WHERE txn_id = 'TXN-2024-03-15-ABC123'
  AND snapshot_ts BETWEEN TIMESTAMP '2024-03-15 14:30:00' AND TIMESTAMP '2024-03-15 14:31:00';

-- Alternative: query features table as-of a specific snapshot
SELECT *
FROM iceberg.fraud.realtime_features
FOR TIMESTAMP AS OF TIMESTAMP '2024-03-15 14:30:22'
WHERE entity_id = 'sha256_abc123def456';


-- ============================================================
-- QUERY 4: Feature freshness monitoring
-- ============================================================

SELECT
    entity_type,
    COUNT(*) as entity_count,
    AVG(DATE_DIFF('second', last_updated_ts, CURRENT_TIMESTAMP)) as avg_staleness_sec,
    MAX(DATE_DIFF('second', last_updated_ts, CURRENT_TIMESTAMP)) as max_staleness_sec,
    COUNT(CASE WHEN DATE_DIFF('second', last_updated_ts, CURRENT_TIMESTAMP) > 30 THEN 1 END)
        as stale_entities_30s,
    COUNT(CASE WHEN DATE_DIFF('second', last_updated_ts, CURRENT_TIMESTAMP) > 300 THEN 1 END)
        as stale_entities_5m
FROM iceberg.fraud.realtime_features
WHERE event_date = CURRENT_DATE
GROUP BY entity_type;
```

---

## Compaction Strategy (Critical for MoR)

```
WHY COMPACTION IS CRITICAL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MoR trade-off:
  WRITES are fast (small delta files) → great for streaming at 200K/sec
  READS get slower over time (must merge N delete files with data files)

Read Amplification = (data files + delete files) read per query
                    vs
                    (actual live rows returned)

WITHOUT compaction (after 1 hour of streaming):
  - 60 checkpoints × 32 parallelism = 1,920 new data files
  - 60 checkpoints × 32 parallelism = 1,920 equality delete files
  - Point lookup for 1 entity must scan: ~4 data files + ~60 delete files
  - Latency: 200-500ms (UNACCEPTABLE for 50ms SLA)

WITH compaction (every 10 minutes):
  - Base: 1 compacted data file per bucket-day
  - Deltas: max 10 minutes of streaming files (~320 files)
  - Point lookup: 1 base file + ~5 delta files + ~5 delete files
  - Latency: 20-40ms (WITHIN SLA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Compaction Job (Spark-based, Airflow-triggered)

```python
"""
Compaction job for MoR tables.
Triggered every 10 minutes by Airflow.
Handles: partial compaction (per-bucket), conflict resolution, and metrics emission.
"""

from pyspark.sql import SparkSession
from pyiceberg.catalog import load_catalog
from pyiceberg.table import Table
import time
import json

catalog = load_catalog("rest", uri="http://iceberg-rest-catalog:8181",
                       warehouse="s3://fraud-lakehouse/warehouse")

table = catalog.load_table("fraud.realtime_features")

# ============================================================
# Identify buckets needing compaction
# ============================================================
def get_compaction_candidates(table: Table, max_delete_files_per_bucket: int = 20):
    """
    Scan manifests to find partitions (buckets) with high delete file count.
    Prioritize buckets with highest read amplification.
    """
    candidates = []
    current_snapshot = table.current_snapshot()

    for manifest in current_snapshot.manifests(table.io):
        if manifest.content == 1:  # DELETES manifest
            partition_spec = manifest.partition_spec_id
            # Count delete files per partition
            for entry in manifest.fetch_manifest_entry(table.io):
                partition_key = entry.data_file.partition
                candidates.append({
                    "partition": partition_key,
                    "delete_file_count": 1,
                    "delete_file_size": entry.data_file.file_size_in_bytes,
                })

    # Aggregate by partition
    from collections import defaultdict
    partition_stats = defaultdict(lambda: {"count": 0, "size": 0})
    for c in candidates:
        key = str(c["partition"])
        partition_stats[key]["count"] += c["delete_file_count"]
        partition_stats[key]["size"] += c["delete_file_size"]

    # Return partitions exceeding threshold, sorted by delete count desc
    return sorted(
        [{"partition": k, **v} for k, v in partition_stats.items()
         if v["count"] >= max_delete_files_per_bucket],
        key=lambda x: x["count"],
        reverse=True
    )


# ============================================================
# Execute compaction via Spark rewrite_data_files
# ============================================================
spark = (SparkSession.builder
    .appName("fraud-features-compaction")
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.iceberg.type", "rest")
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest-catalog:8181")
    .getOrCreate())

# Iceberg's built-in rewrite procedure
compaction_start = time.time()

result = spark.sql("""
    CALL iceberg.system.rewrite_data_files(
        table => 'fraud.realtime_features',
        strategy => 'sort',
        sort_order => 'entity_id ASC, last_updated_ts DESC',
        options => map(
            'target-file-size-bytes', '536870912',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '1073741824',
            'min-input-files', '5',
            'max-concurrent-file-group-rewrites', '16',
            'partial-progress.enabled', 'true',
            'partial-progress.max-commits', '10',
            'delete-file-threshold', '10'
        ),
        where => 'event_date = current_date()'
    )
""")

compaction_duration = time.time() - compaction_start
rewritten = result.collect()[0]

# ============================================================
# Also expire old delete files after compaction
# ============================================================
spark.sql("""
    CALL iceberg.system.rewrite_position_delete_files(
        table => 'fraud.realtime_features',
        options => map(
            'rewrite-all', 'true'
        )
    )
""")

# ============================================================
# Expire old snapshots (keep 7 days for time travel)
# ============================================================
spark.sql("""
    CALL iceberg.system.expire_snapshots(
        table => 'fraud.realtime_features',
        older_than => TIMESTAMP '{week_ago}',
        retain_last => 100,
        max_concurrent_deletes => 32
    )
""")

# Emit metrics
metrics = {
    "compaction_duration_sec": compaction_duration,
    "files_rewritten": rewritten["rewritten_data_files_count"],
    "delete_files_removed": rewritten["rewritten_delete_files_count"],
    "bytes_rewritten": rewritten["rewritten_bytes_count"],
}
print(json.dumps(metrics))
```

### Compaction Schedule & Priorities

```
COMPACTION TIERS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────┬─────────────┬─────────────────────────────────────┐
│ Tier             │ Frequency   │ Scope                               │
├──────────────────┼─────────────┼─────────────────────────────────────┤
│ Hot compaction   │ Every 10m   │ Today's partitions with >10 deletes │
│ Warm compaction  │ Every 1h    │ Yesterday's partitions              │
│ Cold compaction  │ Daily 04:00 │ Full table optimization + sort      │
│ Snapshot expiry  │ Daily 05:00 │ Remove snapshots older than 7d      │
│ Orphan cleanup   │ Weekly      │ Remove unreferenced data files      │
└──────────────────┴─────────────┴─────────────────────────────────────┘

CONFLICT HANDLING:
  If compaction conflicts with a Flink commit (optimistic concurrency):
  → Iceberg throws CommitConflictException
  → Compaction job retries with exponential backoff (max 3 retries)
  → If still failing: skip this bucket, alert ops, compact next cycle
  → Flink writes ALWAYS win (compaction is best-effort)
```

---

## Airflow Orchestration

```python
"""
Airflow DAG orchestrating the complete feature store pipeline.
"""

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    "owner": "fraud-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": alert_oncall,
}

# ============================================================
# DAG 1: Compaction (every 10 minutes)
# ============================================================
with DAG(
    "fraud_features_compaction",
    default_args=default_args,
    schedule_interval="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["fraud", "compaction", "iceberg"],
) as compaction_dag:

    compact_realtime = SparkSubmitOperator(
        task_id="compact_realtime_features",
        application="s3://fraud-jobs/compaction/compact_realtime.py",
        conf={
            "spark.executor.instances": "8",
            "spark.executor.memory": "8g",
            "spark.executor.cores": "4",
        },
    )

    check_read_amplification = PythonOperator(
        task_id="check_read_amplification",
        python_callable=check_and_alert_read_amplification,
    )

    compact_realtime >> check_read_amplification

# ============================================================
# DAG 2: Daily batch features (02:00 UTC)
# ============================================================
with DAG(
    "fraud_batch_features_daily",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    catchup=True,  # Backfill if missed
    max_active_runs=1,
    tags=["fraud", "batch", "features"],
) as batch_dag:

    validate_input = PythonOperator(
        task_id="validate_input_data",
        python_callable=validate_raw_txn_completeness,
    )

    compute_features = SparkSubmitOperator(
        task_id="compute_batch_features",
        application="s3://fraud-jobs/batch/compute_batch_features.py",
        conf={
            "spark.executor.instances": "64",
            "spark.executor.memory": "16g",
            "spark.executor.cores": "4",
            "spark.sql.shuffle.partitions": "2048",
        },
    )

    validate_output = PythonOperator(
        task_id="validate_feature_quality",
        python_callable=run_great_expectations_suite,
    )

    publish_to_redis = PythonOperator(
        task_id="publish_batch_features_to_redis",
        python_callable=bulk_load_redis_from_iceberg,
    )

    generate_training = SparkSubmitOperator(
        task_id="generate_training_snapshots",
        application="s3://fraud-jobs/training/generate_training_data.py",
        conf={"spark.executor.instances": "32", "spark.executor.memory": "16g"},
    )

    validate_input >> compute_features >> validate_output
    validate_output >> [publish_to_redis, generate_training]
```

---

## Production Handling

### Exactly-Once Semantics

```
END-TO-END EXACTLY-ONCE GUARANTEE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kafka → Flink → Iceberg:
  1. Kafka consumer offsets committed WITH Flink checkpoint
  2. Flink state (RocksDB) saved to S3 checkpoint atomically
  3. Iceberg commit happens ONLY after successful checkpoint
  4. If Flink crashes before checkpoint: replay from last committed offset
  5. If Flink crashes after checkpoint but before Iceberg commit:
     → Iceberg sees no commit → next checkpoint will produce correct state
  6. Iceberg atomic commit: either all files visible or none

Flink → Redis (at-least-once with idempotent writes):
  - Redis HSET is idempotent (same entity_id overwrites → safe)
  - Flink may replay events after recovery → Redis gets duplicate writes
  - Since features are full entity state (not deltas), replay is harmless
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Late Arrival Handling

```
LATE EVENT STRATEGY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Watermark: txn_timestamp - 5 minutes
  → Events arriving within 5 minutes of event time are processed normally
  → Events arriving AFTER watermark: handled by side output

┌──────────────────────────────────────────────────────────────────┐
│  Transaction Event (event_time = 14:30:00)                       │
│  Arrives at 14:35:30 (5.5 min late)                             │
│                                                                  │
│  Watermark at 14:35:30 = 14:30:30 (latest event - 5m)          │
│  Event time 14:30:00 < Watermark 14:30:30 → LATE               │
│                                                                  │
│  Action:                                                         │
│  1. Emit to late-events side output (Kafka: late-transactions)  │
│  2. Still process for feature update (features are latest-wins) │
│  3. Log metric: late_events_count++                             │
│  4. If >1% late rate: alert (indicates upstream delay)          │
└──────────────────────────────────────────────────────────────────┘

Why late arrivals are less critical for feature stores:
  - Features represent CURRENT state (latest value wins)
  - A late event for entity X still produces correct features
  - The only risk: a brief window where features were "stale"
  - For window aggregations: late events trigger window re-computation
```

### Feature Freshness SLAs

```
FRESHNESS MONITORING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────┬──────────┬──────────┬──────────────────────────┐
│ Feature Type     │ SLA      │ Alert    │ Escalation               │
├──────────────────┼──────────┼──────────┼──────────────────────────┤
│ Real-time (RT)   │ < 5s     │ > 10s    │ Page on-call if > 30s   │
│ Window (5m)      │ < 6m     │ > 8m     │ Page if > 15m            │
│ Window (1h)      │ < 65m    │ > 75m    │ Page if > 2h             │
│ Batch (daily)    │ < 1h     │ > 2h     │ Page if > 4h             │
│ Redis serving    │ < 50ms   │ > 100ms  │ Auto-failover to Trino   │
└──────────────────┴──────────┴──────────┴──────────────────────────┘

Measurement:
  freshness = NOW() - last_updated_ts (per entity)
  Sampled every 30s by monitoring job reading Iceberg metadata
```

---

## Failure Scenarios & Recovery

### Scenario 1: Flink Checkpoint Failure

```
SYMPTOM: Checkpoint timeout after 5 minutes
ROOT CAUSE: S3 latency spike during checkpoint upload (RocksDB incremental)

IMPACT:
  - No Iceberg commits during failure window (features freeze)
  - Redis still has last-good features (stale but available)
  - Fraud scoring continues with slightly stale features

RECOVERY:
  1. Flink auto-restores from last successful checkpoint
  2. Replays Kafka from last committed consumer offset
  3. Recomputes features for replayed window
  4. Features catch up within minutes (replay is fast)

MITIGATION:
  - checkpoint.timeout = 300s (tolerate S3 blips)
  - tolerable-checkpoint-failures = 3 (don't restart on transient)
  - Incremental checkpoints (upload only deltas)
  - S3 multi-part upload with retry
```

### Scenario 2: Compaction Conflicts

```
SYMPTOM: CommitConflictException during rewrite_data_files
ROOT CAUSE: Flink committed new snapshot between compaction's read and commit

IMPACT:
  - Compaction job fails for that partition
  - Delete files accumulate → read amplification grows
  - Feature serving latency increases (more files to merge)

RECOVERY:
  1. Compaction retries with exponential backoff
  2. On retry: re-reads current snapshot, replans file groups
  3. If still conflicting after 3 retries: skip, alert, next cycle

PREVENTION:
  - partial-progress.enabled = true
    → Compaction commits in batches, reducing conflict window
  - max-concurrent-file-group-rewrites = 16
    → Smaller commits, less likely to conflict
  - Time-based bucketing: compaction targets PREVIOUS day
    → Current day gets minimal compaction (Flink still writing)
```

### Scenario 3: Schema Evolution Mid-Stream

```
SYMPTOM: New feature column added while Flink is writing
ROOT CAUSE: Data scientist added feature via ALTER TABLE

IMPACT:
  - Flink writing old schema → Iceberg handles gracefully
  - New column filled with NULL until Flink job redeployed
  - Existing readers unaffected (schema evolution is additive)

PROCEDURE:
  1. ALTER TABLE fraud.realtime_features ADD COLUMN new_feature DOUBLE;
  2. Deploy new Flink version writing the new column (blue/green)
  3. Old Flink drains; new Flink starts from checkpoint
  4. Backfill: Spark job fills new_feature for historical partitions
```

---

## Monitoring & Observability

```
OPERATIONAL METRICS DASHBOARD:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────┐
│  FEATURE FRESHNESS (p50 / p99)                                          │
│  ═══════════════════════════════                                        │
│  Realtime features:    1.2s / 4.8s    ✅ (SLA: 5s)                     │
│  Window features (5m): 5.1m / 5.9m    ✅ (SLA: 6m)                     │
│  Batch features:       45m  / 58m     ✅ (SLA: 1h)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  READ AMPLIFICATION                                                     │
│  ═══════════════════                                                    │
│  realtime_features:  Files/query (p50): 3  │  (p99): 8   ✅ (<15)      │
│  window_features:    Files/query (p50): 2  │  (p99): 5   ✅ (<10)      │
│  Equality deletes pending: 1,240     │  Last compaction: 3m ago         │
├─────────────────────────────────────────────────────────────────────────┤
│  THROUGHPUT                                                             │
│  ══════════                                                             │
│  Kafka ingest:     185,000 events/sec                                   │
│  Flink processing: 183,000 events/sec (lag: 2,000 → healthy)           │
│  Iceberg commits:  62/hour (one per checkpoint)                         │
│  Redis writes:     185,000/sec                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  STORAGE                                                                │
│  ═══════                                                                │
│  realtime_features: 2.1 TB (S3)  │  Snapshots: 89  │  Files: 12,400   │
│  window_features:   8.4 TB (S3)  │  Snapshots: 156 │  Files: 48,200   │
│  batch_features:    1.8 TB (S3)  │  Snapshots: 365 │  Files: 94,000   │
│  feature_snapshots: 45 TB (S3)   │  Snapshots: 365 │  Files: 890,000  │
├─────────────────────────────────────────────────────────────────────────┤
│  COMPACTION HEALTH                                                      │
│  ═════════════════                                                      │
│  Last hot compaction:   2 min ago    Duration: 45s    Files merged: 320 │
│  Last warm compaction:  12 min ago   Duration: 180s   Files merged: 890 │
│  Compaction conflicts (24h): 3       (threshold: < 10/day)              │
│  Orphan files: 0                     (last cleanup: 2 days ago)         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Prometheus Metrics

```yaml
# Flink metrics (exposed via Flink metrics reporter)
flink_fraud_features_records_processed_total:
  type: counter
  labels: [entity_type, parallelism_index]

flink_fraud_features_checkpoint_duration_ms:
  type: histogram
  buckets: [1000, 5000, 10000, 30000, 60000, 300000]

flink_fraud_features_iceberg_commits_total:
  type: counter
  labels: [table, status]  # status: success|conflict|failure

# Iceberg table metrics (scraped from REST catalog)
iceberg_table_snapshot_count:
  type: gauge
  labels: [database, table]

iceberg_table_delete_files_count:
  type: gauge
  labels: [database, table, partition]

iceberg_table_data_files_count:
  type: gauge
  labels: [database, table]

# Feature freshness (custom exporter reading Iceberg metadata)
feature_store_freshness_seconds:
  type: histogram
  labels: [table, entity_type]
  buckets: [1, 2, 5, 10, 30, 60, 300, 3600]

# Redis serving metrics
feature_serving_latency_ms:
  type: histogram
  labels: [source]  # redis|trino_fallback
  buckets: [1, 5, 10, 25, 50, 100, 250, 500]

feature_serving_cache_hit_ratio:
  type: gauge
  # Target: > 99.5% (most entities accessed recently)
```

---

## Scale Considerations

```
SIZING FOR 10B EVENTS/DAY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FLINK CLUSTER:
  - TaskManagers: 16 × (8 cores, 32GB RAM, 500GB NVMe for RocksDB)
  - Parallelism: 32 (matches Kafka partitions)
  - State size: ~200GB (100M entities × 2KB average state per entity)
  - Checkpoint size: ~20GB incremental (delta since last checkpoint)
  - Checkpoint interval: 60s
  - Recovery time: ~90s (restore state + replay 60s of Kafka)

KAFKA:
  - Brokers: 12 × (16 cores, 64GB, 10TB NVMe)
  - Partitions: 32 for transactions topic
  - Retention: 7 days (for replay capability)
  - Throughput: 200K events/sec × 1KB avg = 200 MB/sec ingest

S3 (ICEBERG STORAGE):
  - realtime_features: ~2 TB (100M entities × 20KB compressed per entity)
  - window_features: ~8 TB (100M entities × 5 windows × 16KB)
  - batch_features: ~2 TB per daily snapshot × 365 days = ~700 TB total
  - feature_snapshots: ~10B records/day × 2KB × 365 days = ~7 PB/year
  - Total: ~8 PB growing at ~7 PB/year

  Cost: ~$170K/month (S3 Standard) → lifecycle to Glacier after 1 year
         reduces to ~$50K/month effective

REDIS (ONLINE SERVING):
  - Cluster: 20 shards × 3 replicas = 60 nodes
  - Memory: 100M entities × 4KB (hot features only) = 400 GB
  - Throughput: 200K reads/sec + 200K writes/sec
  - Latency: p50=2ms, p99=8ms

SPARK (BATCH):
  - Cluster: 64 executors × (4 cores, 16GB)
  - Daily job processes: ~10B transactions × 90-day lookback
  - Runtime: 45 minutes with adaptive query execution
  - Shuffle: ~2 TB (aggregation of 100M entity groups)

TRINO (SERVING FALLBACK + ANALYTICS):
  - Workers: 8 × (16 cores, 128GB, fast SSD for caching)
  - Concurrency: 200 concurrent queries
  - Point lookup latency: 30-50ms (bucket pruning + file caching)
```

---

## Summary: Iceberg Concepts Applied

| Iceberg Concept | How It's Used | Why It Matters |
|---|---|---|
| **Merge-on-Read** | Streaming upserts write small delta files | 200K/sec writes without rewriting existing data |
| **Equality Deletes** | `DELETE WHERE entity_id = X` as metadata | Logical upsert: delete old + insert new atomically |
| **Hidden Partitioning** | `bucket(512, entity_id)` | Point lookups read 1/512th of data, zero query changes |
| **Bucket Partitioning** | High-cardinality entity_id across 512 buckets | Even distribution, predictable file sizes |
| **Time Travel** | `FOR SYSTEM_TIME AS OF` for explainability | Regulatory audit: reproduce any historical decision |
| **Snapshot Isolation** | Flink writes don't block Trino reads | Concurrent streaming + serving without locks |
| **Schema Evolution** | Add features without migration | Data scientists iterate without pipeline coordination |
| **Optimistic Concurrency** | Compaction retries on conflict with Flink | Both writers coexist safely |
| **Compaction** | Background merge of delta + delete files | Keeps read amplification bounded for serving SLA |
| **Partition Evolution** | Change bucketing without rewrite | Scale from 256 → 512 buckets as entity count grows |

---

## Key Takeaways

1. **MoR is essential for streaming feature stores** — Copy-on-Write would require rewriting 512MB files on every transaction, making 200K/sec impossible.

2. **Bucket partitioning enables point lookups** — Without it, every feature read would scan the entire table. With 512 buckets, reads touch < 0.2% of data.

3. **Compaction is not optional** — It's a first-class operational concern. Without it, MoR tables degrade to unusable read latencies within hours.

4. **Time travel eliminates a class of ML bugs** — Point-in-time feature reconstruction (no data leakage) is trivial with Iceberg snapshots, but nearly impossible with mutable stores.

5. **Equality deletes + upsert mode** — The combination that makes streaming feature stores viable on object storage. Previously required a database.
