# Financial Transaction History & Audit Trail at Stripe/Banking Scale

## The Problem: 2 Billion Transactions/Day with Complete Audit History

### Business Context

A fintech company (Stripe-scale payment processor or tier-1 bank) must:

1. **Store every transaction immutably** — regulators demand complete history
2. **Prove any historical state** — "Show me the exact ledger at 2024-03-15T14:30:00Z"
3. **Never lose or corrupt data** — a single lost transaction = regulatory violation
4. **Support concurrent writes** — thousands of microservices writing simultaneously
5. **Enable fast auditor queries** — SOX auditors query years of history interactively
6. **Comply with SOX, PCI-DSS, Basel III** — data retention, access controls, lineage

### Scale Parameters

```
┌────────────────────────────────────────────────────────────┐
│              PRODUCTION SCALE PARAMETERS                     │
├────────────────────────────────┬───────────────────────────┤
│ Daily transactions             │ 2,000,000,000 (2B)        │
│ Peak write rate                │ 45,000 txns/sec           │
│ Average transaction size       │ ~800 bytes (raw JSON)     │
│ Daily raw ingestion            │ ~1.6 TB/day               │
│ Columnar (Parquet) storage     │ ~400 GB/day (4:1 ratio)   │
│ Retention period               │ 7 years (regulatory)      │
│ Total stored data              │ ~1 PB (compressed)        │
│ Concurrent writers             │ 200+ microservices        │
│ Auditor query latency SLA      │ < 30 seconds              │
│ Data availability SLA          │ 99.999%                   │
│ Recovery Point Objective (RPO) │ 0 (zero data loss)        │
│ Recovery Time Objective (RTO)  │ < 5 minutes               │
└────────────────────────────────┴───────────────────────────┘
```

---

## Why Traditional Approaches Fail

### Approach 1: RDBMS (PostgreSQL/Oracle)

```
Problem: 2B rows/day × 7 years = 5+ trillion rows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Single table cannot hold 5 trillion rows (index maintenance alone kills writes)
- Sharding across 1000s of nodes = operational nightmare
- Storage cost: $0.10/GB/month × 1PB = $100,000/month just for storage
- Backup/restore of PB-scale RDBMS: days, not minutes
- Historical queries across all shards: impossible at interactive speeds
- Verdict: FAILS at scale
```

### Approach 2: Hive Tables on S3

```
Problem: No ACID, no time travel, corruption risk
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Concurrent writers corrupt partitions (no isolation)
- No time travel: can't prove historical state to auditors
- Partition scheme locked at creation: changing requires full rewrite
- Small files from streaming: query performance degrades over time
- No row-level operations: corrections require full partition rewrite
- Verdict: FAILS on compliance requirements
```

### Approach 3: Data Warehouse (Snowflake/BigQuery)

```
Problem: Cost-prohibitive at this scale
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Snowflake storage: ~$23/TB/month × 1PB = $23,000/month
- Compute for ingestion: $50,000+/month at this write rate
- Time travel limited to 90 days (not 7 years)
- Vendor lock-in: data not portable
- Total cost: $80,000-150,000/month
- Verdict: FAILS on cost and retention
```

### Why Iceberg Wins

```
┌────────────────────────────────────────────────────────────────────────┐
│                    WHY ICEBERG SOLVES THIS                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ✓ ACID Transactions     → No corruption from concurrent writers       │
│  ✓ Time Travel           → Query ANY historical snapshot (7 years)     │
│  ✓ Append-Only Design    → Immutable data files = perfect audit trail  │
│  ✓ S3 Storage            → $0.023/GB/month = $23,000/month for 1PB    │
│  ✓ Snapshot Metadata     → Prove exact state at any point in time      │
│  ✓ Schema Evolution      → Add columns without rewriting history       │
│  ✓ Hidden Partitioning   → Optimal query performance, no user burden   │
│  ✓ Open Format           → No vendor lock-in, multiple query engines   │
│  ✓ Concurrent Writers    → Optimistic concurrency with retry           │
│  ✓ Compaction            → Solve small files from streaming ingestion  │
│                                                                        │
│  Total monthly cost: ~$30,000-40,000 (vs $100K+ alternatives)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    FINANCIAL TRANSACTION AUDIT PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │ Payment SVC  │    │ Transfer SVC │    │ Fraud Detection / Settlement / ...   │   │
│  └──────┬───────┘    └──────┬───────┘    └──────────────────┬───────────────────┘   │
│         │                   │                                │                       │
│         ▼                   ▼                                ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Apache Kafka (MSK)                                   │    │
│  │  transactions.payments  │  transactions.transfers  │  transactions.all       │    │
│  │  (partitioned by merchant_id, 256 partitions)                                │    │
│  └─────────────────────────────────────────────┬───────────────────────────────┘    │
│                                                 │                                    │
│                    ┌────────────────────────────┼────────────────────┐               │
│                    │                            │                    │               │
│                    ▼                            ▼                    ▼               │
│  ┌─────────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐     │
│  │  Spark Structured       │  │  Spark Batch (EMR)   │  │  Data Quality      │     │
│  │  Streaming (K8s)        │  │  Hourly Compaction   │  │  Validator (K8s)   │     │
│  │                         │  │  + Snapshot Mgmt     │  │                    │     │
│  │  - Micro-batch (30s)    │  │                      │  │  - Schema checks   │     │
│  │  - Exactly-once via     │  │  - Merge small files │  │  - Null checks     │     │
│  │    checkpoint + Iceberg │  │  - Expire snapshots  │  │  - Range checks    │     │
│  │    commit               │  │  - Orphan cleanup    │  │  - Referential     │     │
│  └────────────┬────────────┘  └──────────┬───────────┘  └─────────┬──────────┘     │
│               │                          │                         │                │
│               ▼                          ▼                         ▼                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                          AWS Glue Data Catalog                                │    │
│  │                     (Iceberg metadata, schema registry)                       │    │
│  └─────────────────────────────────────────────┬───────────────────────────────┘    │
│                                                 │                                    │
│                                                 ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                              Amazon S3                                        │    │
│  │                                                                               │    │
│  │  s3://fintech-datalake-prod/                                                  │    │
│  │  └── iceberg/                                                                 │    │
│  │      └── transactions/                                                        │    │
│  │          └── audit_ledger/                                                    │    │
│  │              ├── metadata/          ← Iceberg metadata (snapshots, manifests) │    │
│  │              │   ├── v1.metadata.json                                         │    │
│  │              │   ├── v2.metadata.json                                         │    │
│  │              │   ├── snap-<id>.avro  (manifest lists)                         │    │
│  │              │   └── <hash>.avro     (manifest files)                         │    │
│  │              └── data/              ← Parquet data files                       │    │
│  │                  ├── event_date=2024-03-15/                                   │    │
│  │                  │   ├── hour=14/                                              │    │
│  │                  │   │   ├── 00000-0-<uuid>.parquet  (256MB target)           │    │
│  │                  │   │   └── ...                                               │    │
│  │                  │   └── ...                                                   │    │
│  │                  └── ...                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                          QUERY LAYER                                           │   │
│  │                                                                                │   │
│  │  ┌─────────────┐   ┌─────────────────┐   ┌──────────────────────────────┐    │   │
│  │  │   Athena    │   │  Trino/Starburst│   │  Spark SQL (ad-hoc)          │    │   │
│  │  │  (Auditors) │   │  (Analytics)    │   │  (Data Engineering)          │    │   │
│  │  └─────────────┘   └─────────────────┘   └──────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                          ORCHESTRATION & MONITORING                            │   │
│  │                                                                                │   │
│  │  Airflow (MWAA)          │  CloudWatch + Datadog     │  PagerDuty Alerts     │   │
│  │  - Compaction DAGs       │  - Lag monitoring         │  - Ingestion delay    │   │
│  │  - Snapshot expiry       │  - File count/size        │  - Data quality fail  │   │
│  │  - Data quality checks   │  - Query latency          │  - Commit failures    │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Iceberg Table DDL (Production Settings)

```sql
-- Create the Iceberg namespace
CREATE DATABASE IF NOT EXISTS fintech_audit
LOCATION 's3://fintech-datalake-prod/iceberg/';

-- Main audit ledger table
CREATE TABLE fintech_audit.transaction_ledger (
    -- Primary identifiers
    transaction_id          STRING      NOT NULL,
    idempotency_key         STRING      NOT NULL,
    
    -- Transaction details
    transaction_type        STRING      NOT NULL,  -- payment, refund, transfer, chargeback
    status                  STRING      NOT NULL,  -- initiated, processing, completed, failed, reversed
    amount_cents            BIGINT      NOT NULL,  -- Store in cents to avoid floating point
    currency                STRING      NOT NULL,  -- ISO 4217
    
    -- Parties
    source_account_id       STRING      NOT NULL,
    destination_account_id  STRING,
    merchant_id             STRING,
    customer_id             STRING      NOT NULL,
    
    -- Metadata
    payment_method          STRING,      -- card, ach, wire, crypto
    card_last_four          STRING,      -- PCI: only last 4 digits
    card_brand              STRING,
    
    -- Risk & compliance
    risk_score              DOUBLE,
    fraud_flags             ARRAY<STRING>,
    aml_check_status        STRING,
    sanctions_check_status  STRING,
    
    -- Audit fields
    created_at              TIMESTAMP   NOT NULL,
    updated_at              TIMESTAMP   NOT NULL,
    event_time              TIMESTAMP   NOT NULL,  -- When the event actually occurred
    ingestion_time          TIMESTAMP   NOT NULL,  -- When we received it
    source_system           STRING      NOT NULL,
    correlation_id          STRING      NOT NULL,
    
    -- Lineage
    upstream_transaction_id STRING,      -- For refunds/chargebacks pointing to original
    batch_id                STRING       -- Ingestion batch identifier
)
USING iceberg
PARTITIONED BY (
    days(event_time),           -- Partition by day (hidden partitioning)
    bucket(16, merchant_id)     -- Sub-partition by merchant bucket
)
TBLPROPERTIES (
    -- Write settings
    'write.format.default'                    = 'parquet',
    'write.parquet.compression-codec'         = 'zstd',
    'write.parquet.compression-level'         = '3',
    'write.target-file-size-bytes'            = '268435456',   -- 256 MB target files
    'write.distribution-mode'                 = 'hash',        -- Distribute by partition
    'write.metadata.compression-codec'        = 'gzip',
    
    -- Snapshot management (CRITICAL for audit)
    'history.expire.max-snapshot-age-ms'      = '220752000000', -- 7 years (regulatory)
    'history.expire.min-snapshots-to-keep'    = '1000',
    
    -- Commit settings for concurrent writers
    'commit.retry.num-retries'                = '10',
    'commit.retry.min-wait-ms'                = '100',
    'commit.retry.max-wait-ms'                = '60000',
    'commit.manifest-merge.enabled'           = 'true',
    'commit.manifest.target-size-bytes'       = '8388608',  -- 8 MB manifests
    'commit.manifest.min-count-to-merge'      = '100',
    
    -- Read optimization
    'read.split.target-size'                  = '134217728',   -- 128 MB splits
    'read.parquet.vectorization.enabled'      = 'true',
    
    -- Table metadata
    'table.owner'                             = 'data-platform-team',
    'table.classification'                    = 'PCI-DSS-LEVEL-1',
    'table.retention-policy'                  = '7-years-regulatory',
    'table.data-sensitivity'                  = 'HIGHLY_CONFIDENTIAL'
);
```

---

## Production Spark Pipeline (PySpark)

### Streaming Ingestion: Kafka → Iceberg

```python
"""
Financial Transaction Streaming Ingestion Pipeline
===================================================
Reads from Kafka, validates, deduplicates, and writes to Iceberg.
Runs on Kubernetes (Spark on K8s operator) with exactly-once semantics.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    DoubleType, TimestampType, ArrayType
)
from pyspark.sql.avro.functions import from_avro
import json
import sys


def create_spark_session() -> SparkSession:
    """Create production Spark session with Iceberg configuration."""
    return (
        SparkSession.builder
        .appName("financial-txn-audit-ingestion")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
        .config("spark.sql.catalog.glue_catalog.warehouse", "s3://fintech-datalake-prod/iceberg/")
        .config("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        # S3 optimizations
        .config("spark.sql.catalog.glue_catalog.s3.multipart-upload.part-size-bytes", "67108864")
        .config("spark.hadoop.fs.s3a.connection.maximum", "200")
        .config("spark.hadoop.fs.s3a.threads.max", "64")
        # Iceberg write settings
        .config("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
        # Checkpoint for exactly-once
        .config("spark.sql.streaming.checkpointLocation", 
                "s3://fintech-datalake-prod/checkpoints/txn-audit-ingestion/")
        # Memory and execution
        .config("spark.executor.memory", "8g")
        .config("spark.executor.cores", "4")
        .config("spark.executor.instances", "20")
        .config("spark.sql.shuffle.partitions", "256")
        .getOrCreate()
    )


# Schema for transaction events from Kafka
TRANSACTION_SCHEMA = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("idempotency_key", StringType(), False),
    StructField("transaction_type", StringType(), False),
    StructField("status", StringType(), False),
    StructField("amount_cents", LongType(), False),
    StructField("currency", StringType(), False),
    StructField("source_account_id", StringType(), False),
    StructField("destination_account_id", StringType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("customer_id", StringType(), False),
    StructField("payment_method", StringType(), True),
    StructField("card_last_four", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("risk_score", DoubleType(), True),
    StructField("fraud_flags", ArrayType(StringType()), True),
    StructField("aml_check_status", StringType(), True),
    StructField("sanctions_check_status", StringType(), True),
    StructField("created_at", StringType(), False),
    StructField("updated_at", StringType(), False),
    StructField("event_time", StringType(), False),
    StructField("source_system", StringType(), False),
    StructField("correlation_id", StringType(), False),
    StructField("upstream_transaction_id", StringType(), True),
])


def validate_transactions(df):
    """
    Apply data quality rules. Invalid records go to dead-letter queue.
    Returns (valid_df, invalid_df).
    """
    # Critical field null checks
    critical_fields = [
        "transaction_id", "idempotency_key", "transaction_type",
        "status", "amount_cents", "currency", "source_account_id",
        "customer_id", "event_time"
    ]
    
    null_check = F.lit(True)
    for field in critical_fields:
        null_check = null_check & F.col(field).isNotNull()
    
    # Business rule validations
    valid_types = ["payment", "refund", "transfer", "chargeback", "settlement"]
    valid_statuses = ["initiated", "processing", "completed", "failed", "reversed"]
    valid_currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]
    
    business_rules = (
        null_check
        & F.col("transaction_type").isin(valid_types)
        & F.col("status").isin(valid_statuses)
        & F.col("currency").isin(valid_currencies)
        & (F.col("amount_cents") > 0)
        & (F.col("amount_cents") < 100000000000)  # Max $1B per txn
        & (F.length("transaction_id") == 36)        # UUID format
    )
    
    valid_df = df.filter(business_rules)
    invalid_df = df.filter(~business_rules)
    
    return valid_df, invalid_df


def deduplicate_within_batch(df):
    """
    Deduplicate using idempotency_key within a micro-batch.
    Cross-batch dedup handled by Iceberg's merge-on-read at query time
    and periodic compaction with dedup.
    """
    from pyspark.sql.window import Window
    
    window = Window.partitionBy("idempotency_key").orderBy(F.col("event_time").desc())
    
    return (
        df
        .withColumn("_row_num", F.row_number().over(window))
        .filter(F.col("_row_num") == 1)
        .drop("_row_num")
    )


def run_streaming_ingestion():
    """Main entry point for streaming pipeline."""
    
    spark = create_spark_session()
    
    # Read from Kafka
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "b-1.msk-prod.xxxxx.kafka.us-east-1.amazonaws.com:9096")
        .option("kafka.security.protocol", "SASL_SSL")
        .option("kafka.sasl.mechanism", "AWS_MSK_IAM")
        .option("kafka.sasl.jaas.config",
                "software.amazon.msk.auth.iam.IAMLoginModule required;")
        .option("kafka.sasl.client.callback.handler.class",
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler")
        .option("subscribe", "transactions.all")
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", "5000000")  # ~5M records per micro-batch
        .option("failOnDataLoss", "true")           # CRITICAL: never silently skip data
        .load()
    )
    
    # Parse and transform
    parsed_df = (
        kafka_df
        .select(
            F.col("key").cast("string").alias("kafka_key"),
            F.from_json(F.col("value").cast("string"), TRANSACTION_SCHEMA).alias("data"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset")
        )
        .select("data.*", "kafka_timestamp")
        .withColumn("ingestion_time", F.current_timestamp())
        .withColumn("event_time", F.to_timestamp("event_time"))
        .withColumn("created_at", F.to_timestamp("created_at"))
        .withColumn("updated_at", F.to_timestamp("updated_at"))
        .withColumn("batch_id", F.lit(None).cast("string"))  # Set in foreachBatch
    )
    
    # Write using foreachBatch for exactly-once with validation
    def process_batch(batch_df, batch_id):
        """Process each micro-batch with validation and exactly-once write."""
        if batch_df.isEmpty():
            return
        
        import uuid
        current_batch_id = f"stream-{batch_id}-{uuid.uuid4().hex[:8]}"
        
        # Add batch identifier
        batch_df = batch_df.withColumn("batch_id", F.lit(current_batch_id))
        
        # Validate
        valid_df, invalid_df = validate_transactions(batch_df)
        
        # Send invalid records to dead-letter topic
        if not invalid_df.isEmpty():
            (
                invalid_df
                .select(
                    F.col("transaction_id").alias("key"),
                    F.to_json(F.struct("*")).alias("value")
                )
                .write
                .format("kafka")
                .option("kafka.bootstrap.servers", 
                        "b-1.msk-prod.xxxxx.kafka.us-east-1.amazonaws.com:9096")
                .option("topic", "transactions.dead-letter")
                .save()
            )
            
            # Emit metric for alerting
            print(f"METRIC|dead_letter_count|{invalid_df.count()}|batch_id={current_batch_id}")
        
        # Deduplicate valid records
        deduped_df = deduplicate_within_batch(valid_df)
        
        # Write to Iceberg (append-only for audit trail)
        (
            deduped_df
            .writeTo("glue_catalog.fintech_audit.transaction_ledger")
            .option("fanout-enabled", "true")  # Write to multiple partitions efficiently
            .append()
        )
        
        # Emit success metrics
        count = deduped_df.count()
        print(f"METRIC|records_written|{count}|batch_id={current_batch_id}")
    
    # Start streaming query
    query = (
        parsed_df.writeStream
        .foreachBatch(process_batch)
        .trigger(processingTime="30 seconds")
        .option("checkpointLocation",
                "s3://fintech-datalake-prod/checkpoints/txn-audit-ingestion/")
        .start()
    )
    
    query.awaitTermination()


if __name__ == "__main__":
    run_streaming_ingestion()
```

### Batch Compaction & Maintenance Pipeline

```python
"""
Iceberg Table Maintenance Pipeline
====================================
Runs hourly via Airflow. Handles:
- Small file compaction
- Snapshot management (expire old, keep regulatory minimum)
- Orphan file cleanup
- Sort order optimization
"""

from pyspark.sql import SparkSession
from datetime import datetime, timedelta
import sys


def create_maintenance_session() -> SparkSession:
    """Spark session for maintenance operations."""
    return (
        SparkSession.builder
        .appName("iceberg-txn-ledger-maintenance")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
        .config("spark.sql.catalog.glue_catalog.warehouse", "s3://fintech-datalake-prod/iceberg/")
        .config("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.executor.memory", "16g")
        .config("spark.executor.cores", "4")
        .config("spark.executor.instances", "10")
        .getOrCreate()
    )


def compact_small_files(spark, table_name: str, target_date: str):
    """
    Compact small files from streaming ingestion into optimally-sized files.
    
    Streaming writes 30-second micro-batches → many small files (~5-20MB each).
    Compaction merges them into 256MB target files for query performance.
    """
    print(f"Starting compaction for {table_name}, date={target_date}")
    
    spark.sql(f"""
        CALL glue_catalog.system.rewrite_data_files(
            table => '{table_name}',
            strategy => 'sort',
            sort_order => 'event_time ASC, merchant_id ASC',
            options => map(
                'target-file-size-bytes', '268435456',
                'min-file-size-bytes',    '67108864',
                'max-file-size-bytes',    '536870912',
                'min-input-files',        '5',
                'max-concurrent-file-group-rewrites', '10',
                'partial-progress.enabled', 'true',
                'partial-progress.max-commits', '10'
            ),
            where => "event_time >= timestamp '{target_date} 00:00:00' 
                      AND event_time < timestamp '{target_date} 23:59:59'"
        )
    """)
    
    print(f"Compaction completed for {target_date}")


def expire_snapshots(spark, table_name: str):
    """
    Expire snapshots older than 7 years.
    
    CRITICAL: For audit compliance, we keep ALL snapshots for 7 years.
    Only expire beyond the regulatory retention window.
    We also keep a minimum of 1000 snapshots regardless of age.
    """
    retention_cutoff = datetime.now() - timedelta(days=2557)  # 7 years
    cutoff_ts = retention_cutoff.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Expiring snapshots older than {cutoff_ts}")
    
    spark.sql(f"""
        CALL glue_catalog.system.expire_snapshots(
            table => '{table_name}',
            older_than => TIMESTAMP '{cutoff_ts}',
            retain_last => 1000,
            max_concurrent_deletes => 20,
            stream_results => true
        )
    """)


def remove_orphan_files(spark, table_name: str):
    """
    Remove data files not referenced by any snapshot.
    
    These accumulate from failed writes or expired snapshots.
    Use a 3-day grace period to avoid deleting files from in-progress commits.
    """
    cutoff = datetime.now() - timedelta(days=3)
    cutoff_ts = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    
    spark.sql(f"""
        CALL glue_catalog.system.remove_orphan_files(
            table => '{table_name}',
            older_than => TIMESTAMP '{cutoff_ts}',
            dry_run => false
        )
    """)


def rewrite_manifests(spark, table_name: str):
    """
    Merge small manifest files for faster query planning.
    Many streaming commits = many small manifests → slow query planning.
    """
    spark.sql(f"""
        CALL glue_catalog.system.rewrite_manifests(
            table => '{table_name}',
            use_caching => true
        )
    """)


def run_maintenance(target_date: str = None):
    """Full maintenance run."""
    spark = create_maintenance_session()
    table = "fintech_audit.transaction_ledger"
    
    if target_date is None:
        # Compact yesterday's data (today's is still being written)
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        compact_small_files(spark, table, target_date)
        rewrite_manifests(spark, table)
        expire_snapshots(spark, table)
        remove_orphan_files(spark, table)
        print(f"Maintenance completed successfully for {target_date}")
    except Exception as e:
        print(f"ERROR|maintenance_failed|{str(e)}")
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_maintenance(date_arg)
```

---

## Exactly-Once Ingestion Guarantees

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXACTLY-ONCE SEMANTICS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: Kafka Consumer                                                     │
│  ────────────────────────                                                    │
│  - Spark Structured Streaming tracks offsets in checkpoint                    │
│  - On failure: resumes from last committed offset                            │
│  - failOnDataLoss=true → alerts if offsets are no longer available           │
│                                                                              │
│  Layer 2: Idempotency Key                                                    │
│  ────────────────────────                                                    │
│  - Every transaction has a unique idempotency_key from source                │
│  - Within-batch dedup via window function                                    │
│  - Cross-batch dedup at query time (auditors always get correct view)        │
│                                                                              │
│  Layer 3: Iceberg Atomic Commits                                             │
│  ────────────────────────────                                                │
│  - Each micro-batch is a single Iceberg commit                               │
│  - Commit either fully succeeds or fully fails                               │
│  - On failure: Spark retries from checkpoint → re-processes same offsets     │
│  - Iceberg's optimistic concurrency prevents partial writes                  │
│                                                                              │
│  Layer 4: Checkpoint Coordination                                            │
│  ────────────────────────────────                                            │
│  - Checkpoint updated AFTER Iceberg commit succeeds                          │
│  - If crash between Iceberg commit and checkpoint update:                    │
│    → Duplicate write on restart (handled by idempotency_key dedup)           │
│                                                                              │
│  Result: At-least-once delivery + idempotency = exactly-once semantics       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Airflow Orchestration

```python
"""
Airflow DAG for Iceberg Table Maintenance
==========================================
Runs on Amazon MWAA (Managed Workflows for Apache Airflow).
"""

from airflow import DAG
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator
from airflow.providers.amazon.aws.sensors.emr import EmrServerlessSensor
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import boto3


default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["data-platform-oncall@company.com"],
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

dag = DAG(
    dag_id="iceberg_txn_ledger_maintenance",
    default_args=default_args,
    description="Hourly compaction + daily snapshot management for transaction ledger",
    schedule_interval="0 * * * *",  # Every hour
    start_date=days_ago(1),
    catchup=False,
    tags=["iceberg", "maintenance", "critical"],
    max_active_runs=1,
)


# Compaction job (hourly)
compaction_job = EmrServerlessStartJobOperator(
    task_id="compact_small_files",
    application_id="{{ var.value.emr_serverless_app_id }}",
    execution_role_arn="{{ var.value.emr_execution_role_arn }}",
    job_driver={
        "sparkSubmit": {
            "entryPoint": "s3://fintech-datalake-prod/jobs/iceberg_maintenance.py",
            "entryPointArguments": ["{{ ds }}"],
            "sparkSubmitParameters": (
                "--conf spark.executor.memory=16g "
                "--conf spark.executor.cores=4 "
                "--conf spark.executor.instances=10 "
                "--conf spark.jars.packages=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,"
                "org.apache.iceberg:iceberg-aws-bundle:1.5.0"
            ),
        }
    },
    configuration_overrides={
        "monitoringConfiguration": {
            "cloudWatchLoggingConfiguration": {
                "enabled": True,
                "logGroupName": "/emr-serverless/iceberg-maintenance",
            }
        }
    },
    dag=dag,
)


# Data quality check after compaction
def check_data_quality(**context):
    """Verify compaction didn't corrupt data."""
    import boto3
    
    client = boto3.client("athena")
    ds = context["ds"]
    
    # Count records for the day should match pre-compaction count
    query = f"""
        SELECT COUNT(*) as cnt
        FROM fintech_audit.transaction_ledger
        WHERE event_time >= TIMESTAMP '{ds} 00:00:00'
          AND event_time < TIMESTAMP '{ds} 23:59:59'
    """
    
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": "fintech_audit"},
        ResultConfiguration={
            "OutputLocation": "s3://fintech-datalake-prod/athena-results/"
        },
    )
    # In production: wait for query, compare with expected count from metrics


quality_check = PythonOperator(
    task_id="data_quality_check",
    python_callable=check_data_quality,
    dag=dag,
)

compaction_job >> quality_check
```

---

## Audit Query Examples (Time Travel)

### Query 1: Exact State at a Point in Time (SOX Audit)

```sql
-- "Show me all transactions for merchant_id='m_abc123' as of March 15, 2024 at 2:30 PM"
-- This is THE killer feature for regulatory compliance

SELECT 
    transaction_id,
    transaction_type,
    status,
    amount_cents / 100.0 AS amount_dollars,
    currency,
    source_account_id,
    destination_account_id,
    event_time,
    risk_score
FROM glue_catalog.fintech_audit.transaction_ledger
FOR TIMESTAMP AS OF TIMESTAMP '2024-03-15 14:30:00'
WHERE merchant_id = 'm_abc123'
  AND event_time >= TIMESTAMP '2024-03-01 00:00:00'
  AND event_time < TIMESTAMP '2024-03-16 00:00:00'
ORDER BY event_time DESC;
```

### Query 2: Compare Two Points in Time (Detect Unauthorized Changes)

```sql
-- Compliance requirement: prove no records were modified between two audit checkpoints

WITH checkpoint_a AS (
    SELECT transaction_id, amount_cents, status
    FROM glue_catalog.fintech_audit.transaction_ledger
    FOR TIMESTAMP AS OF TIMESTAMP '2024-03-15 00:00:00'
    WHERE event_time >= TIMESTAMP '2024-03-14 00:00:00'
      AND event_time < TIMESTAMP '2024-03-15 00:00:00'
),
checkpoint_b AS (
    SELECT transaction_id, amount_cents, status
    FROM glue_catalog.fintech_audit.transaction_ledger
    FOR TIMESTAMP AS OF TIMESTAMP '2024-03-20 00:00:00'
    WHERE event_time >= TIMESTAMP '2024-03-14 00:00:00'
      AND event_time < TIMESTAMP '2024-03-15 00:00:00'
)
SELECT 
    a.transaction_id,
    a.amount_cents AS amount_at_checkpoint_a,
    b.amount_cents AS amount_at_checkpoint_b,
    a.status AS status_at_checkpoint_a,
    b.status AS status_at_checkpoint_b
FROM checkpoint_a a
FULL OUTER JOIN checkpoint_b b ON a.transaction_id = b.transaction_id
WHERE a.amount_cents != b.amount_cents
   OR a.status != b.status
   OR a.transaction_id IS NULL
   OR b.transaction_id IS NULL;
-- Result should be EMPTY for append-only audit table
```

### Query 3: Snapshot History (Prove Data Lineage)

```sql
-- Show all snapshots (commits) that modified the table
-- Each snapshot = one atomic write operation

SELECT 
    committed_at,
    snapshot_id,
    parent_id,
    operation,
    summary
FROM glue_catalog.fintech_audit.transaction_ledger.snapshots
ORDER BY committed_at DESC
LIMIT 100;

-- Query specific snapshot by ID
SELECT COUNT(*) as total_records, 
       SUM(amount_cents) / 100.0 as total_dollars
FROM glue_catalog.fintech_audit.transaction_ledger
FOR VERSION AS OF 7345918274651923847  -- specific snapshot ID
WHERE event_time >= TIMESTAMP '2024-03-14 00:00:00'
  AND event_time < TIMESTAMP '2024-03-15 00:00:00';
```

### Query 4: Daily Reconciliation (Basel III)

```sql
-- Daily aggregate for regulatory reporting
-- Must match settlement system within $0.01

SELECT 
    DATE(event_time) AS txn_date,
    currency,
    transaction_type,
    COUNT(*) AS txn_count,
    SUM(amount_cents) / 100.0 AS total_amount,
    SUM(CASE WHEN status = 'completed' THEN amount_cents ELSE 0 END) / 100.0 AS settled_amount,
    SUM(CASE WHEN status = 'failed' THEN amount_cents ELSE 0 END) / 100.0 AS failed_amount
FROM glue_catalog.fintech_audit.transaction_ledger
WHERE event_time >= TIMESTAMP '2024-03-14 00:00:00'
  AND event_time < TIMESTAMP '2024-03-15 00:00:00'
GROUP BY DATE(event_time), currency, transaction_type
ORDER BY currency, transaction_type;
```

### Query 5: Fraud Investigation (Full Transaction History)

```sql
-- Trace all activity for a flagged customer across all time
SELECT 
    transaction_id,
    transaction_type,
    status,
    amount_cents / 100.0 AS amount,
    currency,
    merchant_id,
    payment_method,
    risk_score,
    fraud_flags,
    event_time,
    source_system
FROM glue_catalog.fintech_audit.transaction_ledger
WHERE customer_id = 'cust_xyz789'
ORDER BY event_time ASC;
```

---

## Partitioning & File Sizing Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARTITIONING STRATEGY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Partition scheme: days(event_time), bucket(16, merchant_id)                 │
│                                                                              │
│  WHY THIS WORKS:                                                             │
│  ─────────────────                                                           │
│  • days(event_time):                                                         │
│    - Most queries filter by date range                                       │
│    - 2B txns/day ÷ 16 buckets = 125M txns per partition                     │
│    - At 256MB target file size: ~490 files per partition per day             │
│    - After compaction: predictable, scannable                                │
│                                                                              │
│  • bucket(16, merchant_id):                                                  │
│    - Prevents hot partitions (top merchants = 80% traffic)                   │
│    - 16 buckets provides good parallelism without too many files             │
│    - Merchant-scoped queries read only 1/16th of day's data                  │
│                                                                              │
│  WHY NOT more granular?                                                      │
│  ─────────────────────                                                       │
│  • hours(event_time) → 24 × 16 = 384 partitions/day → too many small files │
│  • bucket(256, merchant_id) → explosion of small files                       │
│                                                                              │
│  FILE SIZING:                                                                │
│  ────────────                                                                │
│  • Streaming writes: 5-20MB files (30-sec micro-batches)                     │
│  • After compaction: 256MB files (optimal for S3 + Parquet)                  │
│  • Daily data: ~400GB ÷ 256MB = ~1,562 files after compaction               │
│  • 7 years: ~1,562 × 2,557 days = ~4M data files total                      │
│                                                                              │
│  MANIFEST MANAGEMENT:                                                        │
│  ────────────────────                                                        │
│  • Each manifest tracks ~1000 data files                                     │
│  • ~4,000 manifest files total                                               │
│  • Manifest list per snapshot: references ~50-100 manifests                  │
│  • Query planning: read manifest list → filter manifests → filter files      │
│  • Typical query (1 day, 1 merchant): reads 1-2 manifests → 30-50 files     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Failure Scenarios & Recovery

### Scenario 1: Streaming Job Crash

```
Problem: Spark driver OOM during micro-batch processing
─────────────────────────────────────────────────────────

Impact: Ingestion pauses (data buffered in Kafka, retention=7 days)

Recovery:
1. Kubernetes restarts pod automatically (restart policy: Always)
2. Spark resumes from checkpoint (last committed Kafka offsets)
3. Reprocesses uncommitted micro-batch
4. No data loss, possible duplicates (handled by idempotency_key)

Detection: 
- CloudWatch alarm: Kafka consumer lag > 5 minutes
- PagerDuty: P2 alert after 10 minutes

Prevention:
- Right-size executors (monitor GC time)
- Set maxOffsetsPerTrigger to limit batch size
- Enable adaptive query execution
```

### Scenario 2: Iceberg Commit Conflict

```
Problem: Two streaming instances attempt concurrent commit to same partition
───────────────────────────────────────────────────────────────────────────────

Impact: One commit fails with CommitFailedException

Recovery:
1. Iceberg retries automatically (commit.retry.num-retries=10)
2. Reads latest metadata, rebases the commit
3. If all retries fail: micro-batch fails → Spark retries from checkpoint

Prevention:
- Only one streaming job writes to table (HA via K8s leader election)
- Compaction runs on non-overlapping partitions (yesterday only)
```

### Scenario 3: Corrupt Data Ingested

```
Problem: Upstream service sends malformed transactions
───────────────────────────────────────────────────────

Impact: Bad records could pollute audit table

Recovery:
1. Validation layer catches → routes to dead-letter queue
2. If validation missed (logic bug): 
   - Iceberg time travel to last known-good snapshot
   - Cherry-pick good data from bad snapshot window
   - Never delete from audit table (regulatory); add correction records instead

Procedure for correction:
  -- Identify the bad snapshot range
  SELECT snapshot_id, committed_at, summary['added-records']
  FROM fintech_audit.transaction_ledger.snapshots
  WHERE committed_at BETWEEN '2024-03-15 14:00:00' AND '2024-03-15 15:00:00';
  
  -- Rollback to last good snapshot (creates new snapshot pointing to old state)
  CALL glue_catalog.system.rollback_to_snapshot(
      'fintech_audit.transaction_ledger', 
      <good_snapshot_id>
  );
  
  -- Re-ingest corrected data from Kafka (replay offsets)
```

### Scenario 4: S3 Availability Issue

```
Problem: S3 returns 503 SlowDown errors during peak writes
──────────────────────────────────────────────────────────────

Impact: Write latency increases, possible timeouts

Recovery:
1. S3FileIO has built-in retry with exponential backoff
2. Spark task retries (spark.task.maxFailures=4)
3. If sustained: micro-batch exceeds timeout → retry from checkpoint

Prevention:
- Use random prefixes in S3 paths (Iceberg does this by default with UUIDs)
- Distribute writes across multiple S3 prefixes
- Monitor S3 request metrics via CloudTrail
```

---

## Monitoring & Alerting

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONITORING DASHBOARD                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INGESTION METRICS (Datadog/CloudWatch):                                     │
│  ───────────────────────────────────────                                     │
│  • kafka.consumer.lag              → Alert if > 5M records (P2)              │
│  • iceberg.commits.per.hour        → Alert if < 100 (ingestion stuck)       │
│  • iceberg.records.per.commit      → Track batch sizes                       │
│  • dead.letter.count.per.hour      → Alert if > 1000 (data quality issue)   │
│  • streaming.batch.duration.p99    → Alert if > 60s (falling behind)        │
│                                                                              │
│  TABLE HEALTH METRICS:                                                       │
│  ────────────────────                                                        │
│  • iceberg.files.count             → Alert if > 100K (compaction failing)   │
│  • iceberg.files.avg.size.bytes    → Alert if < 64MB (small file problem)   │
│  • iceberg.manifests.count         → Track growth, alert if > 10K           │
│  • iceberg.snapshots.count         → Monitor, expect ~2500/day              │
│  • iceberg.table.size.bytes        → Track growth rate                       │
│                                                                              │
│  QUERY PERFORMANCE:                                                          │
│  ─────────────────                                                           │
│  • athena.query.p50.latency        → Target < 10s for standard queries      │
│  • athena.query.p99.latency        → Alert if > 60s                         │
│  • athena.data.scanned.bytes       → Cost optimization signal               │
│                                                                              │
│  COMPLIANCE METRICS:                                                         │
│  ──────────────────                                                          │
│  • oldest.snapshot.age.days        → Must be >= 2555 (7 years)              │
│  • time.travel.query.success.rate  → Alert if < 100%                        │
│  • data.completeness.daily         → Compare Kafka offsets vs table count   │
│                                                                              │
│  ALERTS:                                                                     │
│  ───────                                                                     │
│  P1 (PagerDuty, immediate):                                                 │
│    - Ingestion stopped > 15 minutes                                          │
│    - Data loss detected (Kafka offsets skipped)                              │
│    - Snapshot expiry running on data < 7 years old                           │
│                                                                              │
│  P2 (Slack, 30 min response):                                                │
│    - Consumer lag > 5 minutes                                                │
│    - Dead letter rate > 0.1%                                                 │
│    - Compaction job failed                                                   │
│                                                                              │
│  P3 (Ticket, next business day):                                             │
│    - File count growing faster than expected                                 │
│    - Query latency degradation trend                                         │
│    - Storage cost exceeding budget                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment: Kubernetes & Infrastructure

### Streaming Job (Spark on K8s)

```yaml
# spark-streaming-job.yaml (SparkApplication CRD via spark-on-k8s-operator)
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: txn-audit-ingestion
  namespace: data-platform
  labels:
    team: data-platform
    criticality: tier-1
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: "123456789.dkr.ecr.us-east-1.amazonaws.com/spark-iceberg:3.5.1-v42"
  imagePullPolicy: Always
  mainApplicationFile: "s3://fintech-datalake-prod/jobs/streaming_ingestion.py"
  sparkVersion: "3.5.1"
  
  sparkConf:
    spark.sql.extensions: "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
    spark.sql.catalog.glue_catalog: "org.apache.iceberg.spark.SparkCatalog"
    spark.sql.catalog.glue_catalog.catalog-impl: "org.apache.iceberg.aws.glue.GlueCatalog"
    spark.sql.catalog.glue_catalog.warehouse: "s3://fintech-datalake-prod/iceberg/"
    spark.kubernetes.authenticate.driver.serviceAccountName: "spark-driver"
    spark.sql.streaming.metricsEnabled: "true"
    
  restartPolicy:
    type: Always
    onFailureRetries: 2147483647  # Effectively infinite restarts
    onFailureRetryInterval: 30
    onSubmissionFailureRetries: 10
    onSubmissionFailureRetryInterval: 60
    
  driver:
    cores: 2
    memory: "4g"
    serviceAccount: spark-driver
    nodeSelector:
      node-type: compute-optimized
    tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "spark-driver"
        effect: "NoSchedule"
        
  executor:
    cores: 4
    instances: 20
    memory: "8g"
    nodeSelector:
      node-type: compute-optimized
    tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "spark-executor"
        effect: "NoSchedule"
        
  monitoring:
    exposeDriverMetrics: true
    exposeExecutorMetrics: true
    prometheus:
      jmxExporterJar: "/prometheus/jmx_prometheus_javaagent.jar"
      port: 8090
```

### IAM & Security

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IcebergS3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::fintech-datalake-prod/iceberg/transactions/*",
        "arn:aws:s3:::fintech-datalake-prod/checkpoints/*",
        "arn:aws:s3:::fintech-datalake-prod"
      ]
    },
    {
      "Sid": "GlueCatalogAccess",
      "Effect": "Allow",
      "Action": [
        "glue:GetTable",
        "glue:GetTables",
        "glue:UpdateTable",
        "glue:GetDatabase",
        "glue:CreateTable"
      ],
      "Resource": [
        "arn:aws:glue:us-east-1:123456789:catalog",
        "arn:aws:glue:us-east-1:123456789:database/fintech_audit",
        "arn:aws:glue:us-east-1:123456789:table/fintech_audit/*"
      ]
    },
    {
      "Sid": "KafkaAccess",
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:Connect",
        "kafka-cluster:ReadData",
        "kafka-cluster:DescribeGroup",
        "kafka-cluster:AlterGroup"
      ],
      "Resource": "arn:aws:kafka:us-east-1:123456789:cluster/msk-prod/*"
    }
  ]
}
```

---

## Cost Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONTHLY COST BREAKDOWN                                     │
├──────────────────────────────────────┬──────────────────────────────────────┤
│  Component                           │  Monthly Cost                         │
├──────────────────────────────────────┼──────────────────────────────────────┤
│  S3 Storage (1 PB, Standard)         │  $23,552  ($0.023/GB)                │
│  S3 Requests (writes, ~50M PUT/mo)   │  $250                                │
│  S3 Requests (reads, ~200M GET/mo)   │  $80                                 │
│  Kafka (MSK, 256 partitions, 3 AZ)   │  $4,500                              │
│  Spark Streaming (20 executors 24/7) │  $6,200  (spot instances)            │
│  EMR Serverless (compaction, 2h/day) │  $1,800                              │
│  Athena Queries (auditors, ~50TB/mo) │  $250    ($5/TB scanned)             │
│  Glue Data Catalog                   │  $50                                 │
│  CloudWatch/Monitoring               │  $200                                │
│  Data Transfer                       │  $0      (same region)               │
├──────────────────────────────────────┼──────────────────────────────────────┤
│  TOTAL                               │  ~$36,882/month                      │
├──────────────────────────────────────┼──────────────────────────────────────┤
│                                      │                                       │
│  vs. Snowflake equivalent            │  ~$120,000/month                     │
│  vs. Oracle Exadata                  │  ~$300,000/month                     │
│  vs. Aurora PostgreSQL (sharded)     │  ~$180,000/month                     │
│                                      │                                       │
│  SAVINGS: 60-88% vs alternatives                                            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  COST OPTIMIZATION TIPS:                                                     │
│                                                                              │
│  1. S3 Intelligent-Tiering for data > 90 days: saves ~40% on storage        │
│  2. S3 Glacier for data > 1 year (still queryable via Athena):              │
│     reduces 1PB storage to ~$5,000/month                                     │
│  3. Spot instances for Spark executors: 60-70% savings on compute           │
│  4. Athena partition pruning: reduces scan cost by 90%+                      │
│  5. Parquet + ZSTD compression: 4:1 ratio reduces storage                   │
│                                                                              │
│  With all optimizations: ~$22,000/month                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Iceberg Concepts Applied

### 1. Snapshots (Immutable Audit History)

Every write creates a new snapshot. The old snapshot remains forever (within retention).
This is the foundation of the audit trail — you can always prove what data existed at any time.

```
Snapshot Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

snap-001 ──→ snap-002 ──→ snap-003 ──→ snap-004 ──→ ... ──→ snap-N
(t=0)        (t=30s)      (t=60s)      (t=90s)              (current)

Each snapshot references a complete, consistent view of the table.
Query AS OF any snapshot = perfect reproducibility for auditors.
```

### 2. Append-Only Pattern

For audit tables, we NEVER update or delete. Every record is immutable once written.
Even corrections are added as new records with `upstream_transaction_id` pointing to the original.

### 3. Snapshot Expiry (Regulatory Retention)

```
Standard table:     expire snapshots > 7 days (save metadata space)
Audit table:        expire snapshots > 7 YEARS (regulatory requirement)

This means:
- 7 years × 365 days × 24 hours × 120 commits/hour = ~7.3M snapshots
- Each snapshot metadata: ~2KB → ~14.6 GB of snapshot metadata
- Manifest files grow but are compacted by rewrite_manifests
- Cost of keeping this metadata: negligible vs. compliance value
```

### 4. Table Properties for Compliance

```
'table.classification'       = 'PCI-DSS-LEVEL-1'    → Drives access controls
'table.retention-policy'     = '7-years-regulatory'  → Automation respects this
'table.data-sensitivity'     = 'HIGHLY_CONFIDENTIAL' → Tagging for governance
'history.expire.max-snapshot-age-ms' = 220752000000  → 7 years in ms
```

---

## Production Checklist

```
PRE-LAUNCH:
━━━━━━━━━━━━
[ ] Iceberg table created with correct partitioning and properties
[ ] IAM roles configured (least privilege)
[ ] S3 bucket versioning enabled (belt + suspenders)
[ ] S3 bucket lifecycle rules configured (Intelligent-Tiering after 90d)
[ ] Kafka topic created with correct partition count and retention
[ ] Streaming job deployed to K8s with proper resource limits
[ ] Checkpoint location initialized
[ ] Dead-letter topic configured
[ ] Airflow DAGs deployed and tested
[ ] Monitoring dashboards created
[ ] Alert rules configured (P1/P2/P3)
[ ] Runbooks written for each failure scenario
[ ] Load test completed (simulate 2B txns/day for 24 hours)
[ ] Audit query performance validated (< 30s SLA)
[ ] Time travel queries tested across snapshot boundaries
[ ] Disaster recovery drill completed
[ ] Compliance team sign-off on retention configuration

POST-LAUNCH (ongoing):
━━━━━━━━━━━━━━━━━━━━━━
[ ] Weekly: review compaction effectiveness (file sizes)
[ ] Monthly: cost review vs. budget
[ ] Quarterly: audit query performance regression test
[ ] Annually: retention policy review with legal
[ ] Annually: disaster recovery drill
```

---

## Summary

| Aspect | Solution |
|--------|----------|
| Storage | S3 + Iceberg (open format, $0.023/GB) |
| Ingestion | Spark Structured Streaming, 30s micro-batches |
| Exactly-once | Checkpoints + idempotency keys + atomic commits |
| Audit trail | Append-only table, 7-year snapshot retention |
| Time travel | `FOR TIMESTAMP AS OF` / `FOR VERSION AS OF` |
| Compliance | Table properties, access controls, snapshot immutability |
| Performance | Hidden partitioning, compaction, 256MB target files |
| Query layer | Athena (auditors), Trino (analytics), Spark SQL (engineering) |
| Orchestration | Airflow (MWAA) for maintenance, K8s for streaming |
| Cost | ~$37K/month (60-88% less than alternatives) |
| Recovery | Automatic restart, Kafka replay, snapshot rollback |
