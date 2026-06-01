# CDC-Based Slowly Changing Dimensions (SCD Type 2) on Apache Iceberg

## The Problem at Scale

Enterprise dimension tables — customers, products, pricing, contracts — change constantly.
Analytics requires **complete history** of every change for regulatory compliance, attribution,
and point-in-time reporting.

**Scale parameters:**
- 500M customer dimension records (current state)
- 50M change events per day from 12 source systems
- 2+ years of history retained (~18B total rows including history)
- Sub-second point-in-time lookups for operational analytics
- 15-minute maximum CDC lag requirement

### Why Traditional Approaches Fail

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Approach              │ Cost/Month │ Problem                            │
├───────────────────────┼────────────┼────────────────────────────────────┤
│ Snowflake SCD Type 2  │ $180K+     │ MERGE on 500M rows = massive       │
│                       │            │ warehouse credits, clustering $$   │
├───────────────────────┼────────────┼────────────────────────────────────┤
│ Redshift SCD Type 2   │ $150K+     │ No native MERGE, DELETE+INSERT     │
│                       │            │ causes massive vacuum overhead     │
├───────────────────────┼────────────┼────────────────────────────────────┤
│ Raw CDC in Data Lake  │ $5K        │ No MERGE capability, loses current │
│                       │            │ state, requires full rebuilds      │
├───────────────────────┼────────────┼────────────────────────────────────┤
│ Iceberg SCD Type 2    │ $12K       │ ← This solution                   │
│                       │            │ Native MERGE, partition pruning,   │
│                       │            │ cheap S3 storage for history       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Iceberg Solves This

1. **MERGE INTO** — Native upsert semantics: match existing records, close them, insert new versions
2. **Copy-on-Write mode** — Rewrites only affected data files, optimal for batch MERGE
3. **Partition evolution** — Start partitioned by `is_current`, evolve to add date partitions without rewrite
4. **Optimistic concurrency** — Multiple MERGE jobs targeting different partition ranges run concurrently
5. **Schema evolution** — Add new tracked columns without rewriting 18B rows of history
6. **Time travel** — Query any historical snapshot without SCD complexity for recent changes
7. **Hidden partitioning** — Partition by `effective_date` month without exposing it in queries

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        CDC → SCD Type 2 Pipeline                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────────┐    ┌──────────┐ │
│  │ Sources │    │ Debezium │    │  Kafka   │    │    Spark     │    │  Iceberg │ │
│  │         │───▶│  CDC     │───▶│  Topics  │───▶│  MERGE INTO  │───▶│  Tables  │ │
│  │ MySQL   │    │          │    │          │    │              │    │          │ │
│  │ Postgres│    │ Captures │    │ Partitnd │    │ SCD Type 2   │    │ S3 + HMS │ │
│  │ Oracle  │    │ Row-level│    │ by table │    │ Logic        │    │          │ │
│  └─────────┘    └──────────┘    └─────────┘    └──────────────┘    └──────────┘ │
│                                                        │                          │
│                                                        ▼                          │
│                                              ┌──────────────────┐                 │
│                                              │   Monitoring     │                 │
│                                              │   - CDC lag      │                 │
│                                              │   - Merge stats  │                 │
│                                              │   - Conflict rate│                 │
│                                              └──────────────────┘                 │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                         Query Layer                                       │    │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────────────────┐  │    │
│  │  │  Trino  │    │ Athena  │    │  dbt    │    │  BI Tools            │  │    │
│  │  │ Ad-hoc  │    │ Serverls│    │ Transfrm│    │  (Looker/Tableau)    │  │    │
│  │  └─────────┘    └─────────┘    └─────────┘    └──────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘

Detail: MERGE Execution Flow
─────────────────────────────
                                                                                    
  CDC Events (micro-batch)          Iceberg SCD Table                               
  ┌────────────────────┐           ┌──────────────────────────────────┐            
  │ customer_id: 1001  │           │ surr_key │ cust_id │ is_current │            
  │ op: UPDATE         │──MATCH───▶│ SK-9001  │ 1001    │ true       │            
  │ name: "New Name"   │           │          │         │            │            
  │ ts: 2024-01-15T... │           └──────────────────────────────────┘            
  └────────────────────┘                                                           
           │                                                                        
           ▼                                                                        
  ┌─────────────────────────────────────────────────────────┐                      
  │ MERGE Result:                                            │                      
  │  1. UPDATE matched row: is_current=false, eff_end=ts     │                      
  │  2. INSERT new row: is_current=true, eff_start=ts        │                      
  └─────────────────────────────────────────────────────────┘                      
```

---

## Table Design

### SCD Type 2 Table DDL

```sql
-- Iceberg table for Customer dimension with SCD Type 2
CREATE TABLE lakehouse.dimensions.customer_scd2 (
    -- Surrogate key (unique per version)
    surrogate_key       BIGINT,
    
    -- Natural/business key
    customer_id         BIGINT,
    
    -- Tracked attributes (changes to these create new versions)
    customer_name       STRING,
    email               STRING,
    phone               STRING,
    address_line1       STRING,
    address_line2       STRING,
    city                STRING,
    state               STRING,
    postal_code         STRING,
    country             STRING,
    customer_segment    STRING,
    credit_score        INT,
    account_status      STRING,
    preferred_channel   STRING,
    loyalty_tier        STRING,
    assigned_rep_id     BIGINT,
    
    -- Non-tracked attributes (updates in-place, no new version)
    last_login_ts       TIMESTAMP,
    session_count       INT,
    
    -- SCD metadata
    effective_start_ts  TIMESTAMP    COMMENT 'When this version became active',
    effective_end_ts    TIMESTAMP    COMMENT 'When this version was superseded (NULL if current)',
    is_current          BOOLEAN      COMMENT 'True if this is the active version',
    
    -- Audit columns
    source_system       STRING,
    cdc_operation       STRING       COMMENT 'INSERT/UPDATE/DELETE from source',
    cdc_event_ts        TIMESTAMP    COMMENT 'Original event timestamp from source',
    ingestion_ts        TIMESTAMP    COMMENT 'When this record was written to Iceberg',
    batch_id            STRING       COMMENT 'Processing batch identifier'
)
USING iceberg
PARTITIONED BY (is_current, months(effective_start_ts))
TBLPROPERTIES (
    'write.format.default'          = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.target-file-size-bytes'  = '268435456',  -- 256MB for large table
    'write.mode'                    = 'copy-on-write',
    'write.merge.mode'              = 'copy-on-write',
    'write.update.mode'             = 'copy-on-write',
    'write.delete.mode'             = 'copy-on-write',
    'commit.retry.num-retries'      = '10',
    'commit.retry.min-wait-ms'      = '100',
    'commit.retry.max-wait-ms'      = '60000',
    'read.split.target-size'        = '134217728',  -- 128MB splits
    'write.metadata.delete-after-commit.enabled' = 'true',
    'write.metadata.previous-versions-max'       = '100'
);

-- Sort order for optimal query performance
ALTER TABLE lakehouse.dimensions.customer_scd2
  WRITE ORDERED BY customer_id, effective_start_ts DESC;
```

### Why This Partition Strategy

```
Partition: (is_current, months(effective_start_ts))

Rationale:
─────────────────────────────────────────────────────────────────
1. is_current=true partition:
   - Contains only 500M "current" rows
   - 99% of analytical queries hit ONLY this partition
   - MERGE operations target this partition for closing records
   - Keeps "hot" data separate from "cold" history

2. months(effective_start_ts):
   - History partitioned by month of version creation
   - Point-in-time queries prune to specific month ranges
   - Old history rarely touched → stays in cold storage tier
   - ~800M rows/month of history at 50M changes/day

File layout on S3:
  s3://lakehouse/dimensions/customer_scd2/
    is_current=true/
      effective_start_ts_month=2024-01/
        00000-0-abc123.parquet (256MB)
        00001-0-def456.parquet (256MB)
        ...
    is_current=false/
      effective_start_ts_month=2024-01/
      effective_start_ts_month=2024-02/
      ...
```

---

## Debezium CDC Configuration

### Connector Configuration (MySQL Source)

```json
{
  "name": "customer-cdc-mysql",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "customer-db-primary.internal",
    "database.port": "3306",
    "database.user": "debezium_cdc",
    "database.password": "${vault:secret/debezium/mysql-password}",
    "database.server.id": "184054",
    "database.server.name": "customer_db",
    "database.include.list": "customers",
    "table.include.list": "customers.customer_profile,customers.customer_address,customers.customer_preferences",
    
    "database.history.kafka.bootstrap.servers": "kafka-broker-1:9092,kafka-broker-2:9092,kafka-broker-3:9092",
    "database.history.kafka.topic": "schema-changes.customer_db",
    
    "include.schema.changes": "true",
    "column.include.list": "customers.customer_profile.*,customers.customer_address.*",
    
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "key.converter.schemas.enable": "false",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "true",
    
    "transforms": "unwrap,route",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.add.fields": "op,source.ts_ms,source.server,source.db,source.table",
    "transforms.unwrap.delete.handling.mode": "rewrite",
    "transforms.unwrap.drop.tombstones": "true",
    
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "customer_db\\.customers\\.(.*)",
    "transforms.route.replacement": "cdc.customers.$1",
    
    "snapshot.mode": "initial",
    "snapshot.locking.mode": "minimal",
    "snapshot.fetch.size": "10000",
    
    "heartbeat.interval.ms": "10000",
    "heartbeat.action.query": "INSERT INTO debezium_heartbeat (ts) VALUES (NOW()) ON DUPLICATE KEY UPDATE ts=NOW()",
    
    "max.batch.size": "4096",
    "max.queue.size": "65536",
    "poll.interval.ms": "500",
    
    "signal.data.collection": "customers.debezium_signal",
    "incremental.snapshot.chunk.size": "10000",
    
    "topic.creation.default.replication.factor": "3",
    "topic.creation.default.partitions": "12",
    "topic.creation.default.cleanup.policy": "delete",
    "topic.creation.default.retention.ms": "604800000"
  }
}
```

### Kafka Topic Configuration

```properties
# Topic: cdc.customers.customer_profile
num.partitions=12
replication.factor=3
retention.ms=604800000          # 7 days retention
retention.bytes=-1
max.message.bytes=10485760      # 10MB max message
cleanup.policy=delete
compression.type=zstd
```

### CDC Event Schema (after Debezium unwrap)

```json
{
  "schema": { "...": "..." },
  "payload": {
    "customer_id": 1001,
    "customer_name": "Jane Smith",
    "email": "jane.smith@newdomain.com",
    "phone": "+1-555-0199",
    "address_line1": "456 Oak Avenue",
    "city": "San Francisco",
    "state": "CA",
    "postal_code": "94102",
    "country": "US",
    "customer_segment": "enterprise",
    "credit_score": 780,
    "account_status": "active",
    "__op": "u",
    "__source_ts_ms": 1705334400000,
    "__source_server": "customer_db",
    "__source_db": "customers",
    "__source_table": "customer_profile",
    "__deleted": "false"
  }
}
```

---

## Spark MERGE Implementation

### Complete SCD Type 2 MERGE Job

```python
"""
SCD Type 2 MERGE implementation for Customer dimension on Iceberg.

Production job processing 50M CDC events/day against 500M record dimension.
Runs as micro-batch every 15 minutes via Airflow.
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *
from datetime import datetime, timezone
import uuid
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scd2_merge")


def create_spark_session() -> SparkSession:
    """Configure Spark for Iceberg MERGE workload."""
    return (
        SparkSession.builder
        .appName("customer-scd2-merge")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.lakehouse.type", "hive")
        .config("spark.sql.catalog.lakehouse.uri", "thrift://hive-metastore:9083")
        .config("spark.sql.catalog.lakehouse.warehouse", "s3://lakehouse-prod/warehouse")
        # S3 configuration
        .config("spark.hadoop.fs.s3a.endpoint", "s3.us-east-1.amazonaws.com")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")
        # Iceberg MERGE optimization
        .config("spark.sql.iceberg.merge.cardinality-check.enabled", "false")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        .config("spark.sql.shuffle.partitions", "400")
        # Memory for large MERGE
        .config("spark.driver.memory", "16g")
        .config("spark.executor.memory", "32g")
        .config("spark.executor.cores", "8")
        .config("spark.executor.instances", "20")
        .config("spark.memory.fraction", "0.8")
        .config("spark.memory.storageFraction", "0.3")
        # Write optimization
        .config("spark.sql.iceberg.write.target-file-size-bytes", "268435456")
        .getOrCreate()
    )


def read_cdc_batch(spark: SparkSession, batch_start: str, batch_end: str) -> DataFrame:
    """
    Read CDC events from Kafka for the micro-batch window.
    
    In production, this reads from a staging table that Kafka Connect
    or a Spark Structured Streaming job lands CDC events into.
    """
    raw_cdc = (
        spark.read
        .format("iceberg")
        .load("lakehouse.staging.customer_cdc_raw")
        .filter(
            (F.col("ingestion_ts") >= batch_start) &
            (F.col("ingestion_ts") < batch_end)
        )
    )
    
    return raw_cdc


def deduplicate_cdc_events(cdc_df: DataFrame) -> DataFrame:
    """
    Handle duplicate and out-of-order CDC events.
    
    Debezium guarantees at-least-once delivery. Multiple events for the same
    customer_id may arrive. We keep only the LATEST event per customer_id
    within this batch, ordered by source timestamp.
    """
    # Window to pick latest event per customer within batch
    dedup_window = Window.partitionBy("customer_id").orderBy(
        F.col("__source_ts_ms").desc(),
        F.col("ingestion_ts").desc()  # tie-breaker
    )
    
    deduped = (
        cdc_df
        .withColumn("row_num", F.row_number().over(dedup_window))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )
    
    logger.info(f"CDC events: {cdc_df.count()} raw → {deduped.count()} after dedup")
    return deduped


def prepare_staging_records(cdc_df: DataFrame, batch_id: str) -> DataFrame:
    """
    Transform CDC events into records ready for MERGE.
    
    Maps CDC schema to SCD table schema, handles deletes,
    generates surrogate keys for new versions.
    """
    staged = (
        cdc_df
        .withColumn("cdc_operation", 
            F.when(F.col("__op") == "c", F.lit("INSERT"))
             .when(F.col("__op") == "u", F.lit("UPDATE"))
             .when(F.col("__op") == "d", F.lit("DELETE"))
             .otherwise(F.lit("UNKNOWN"))
        )
        .withColumn("cdc_event_ts",
            F.to_timestamp(F.col("__source_ts_ms") / 1000)
        )
        .withColumn("source_system", F.col("__source_server"))
        .withColumn("batch_id", F.lit(batch_id))
        .withColumn("ingestion_ts", F.current_timestamp())
        # Generate surrogate key for new version
        .withColumn("new_surrogate_key",
            F.monotonically_increasing_id() + F.lit(int(time.time() * 1000) << 20)
        )
        .select(
            "customer_id",
            "customer_name",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "customer_segment",
            "credit_score",
            "account_status",
            "preferred_channel",
            "loyalty_tier",
            "assigned_rep_id",
            "last_login_ts",
            "session_count",
            "cdc_operation",
            "cdc_event_ts",
            "source_system",
            "batch_id",
            "ingestion_ts",
            "new_surrogate_key"
        )
    )
    
    return staged


def detect_actual_changes(staged_df: DataFrame, spark: SparkSession) -> DataFrame:
    """
    Compare staged records against current dimension to detect ACTUAL changes.
    
    Filters out CDC events where tracked attributes haven't actually changed
    (e.g., non-tracked column updates that Debezium still captures).
    """
    # Read current records from dimension
    current_dim = (
        spark.read
        .format("iceberg")
        .load("lakehouse.dimensions.customer_scd2")
        .filter(F.col("is_current") == True)
        .select(
            F.col("customer_id").alias("dim_customer_id"),
            F.col("customer_name").alias("dim_customer_name"),
            F.col("email").alias("dim_email"),
            F.col("phone").alias("dim_phone"),
            F.col("address_line1").alias("dim_address_line1"),
            F.col("city").alias("dim_city"),
            F.col("state").alias("dim_state"),
            F.col("postal_code").alias("dim_postal_code"),
            F.col("country").alias("dim_country"),
            F.col("customer_segment").alias("dim_customer_segment"),
            F.col("credit_score").alias("dim_credit_score"),
            F.col("account_status").alias("dim_account_status"),
            F.col("preferred_channel").alias("dim_preferred_channel"),
            F.col("loyalty_tier").alias("dim_loyalty_tier"),
            F.col("assigned_rep_id").alias("dim_assigned_rep_id"),
        )
    )
    
    # Join staged with current to detect real changes
    joined = staged_df.join(
        current_dim,
        staged_df.customer_id == current_dim.dim_customer_id,
        "left"
    )
    
    # Tracked columns that trigger new SCD version
    tracked_columns = [
        ("customer_name", "dim_customer_name"),
        ("email", "dim_email"),
        ("phone", "dim_phone"),
        ("address_line1", "dim_address_line1"),
        ("city", "dim_city"),
        ("state", "dim_state"),
        ("postal_code", "dim_postal_code"),
        ("country", "dim_country"),
        ("customer_segment", "dim_customer_segment"),
        ("credit_score", "dim_credit_score"),
        ("account_status", "dim_account_status"),
        ("preferred_channel", "dim_preferred_channel"),
        ("loyalty_tier", "dim_loyalty_tier"),
        ("assigned_rep_id", "dim_assigned_rep_id"),
    ]
    
    # Build change detection condition
    change_condition = F.lit(False)
    for new_col, dim_col in tracked_columns:
        change_condition = change_condition | (
            ~F.col(new_col).eqNullSafe(F.col(dim_col))
        )
    
    # Keep: new inserts (no match) OR actual changes OR deletes
    actual_changes = joined.filter(
        (F.col("dim_customer_id").isNull()) |  # New customer (INSERT)
        (F.col("cdc_operation") == "DELETE") |  # Deletes always process
        change_condition                         # Actual tracked change
    ).drop(*[col for col in joined.columns if col.startswith("dim_")])
    
    logger.info(f"Staged: {staged_df.count()} → Actual changes: {actual_changes.count()}")
    return actual_changes


def execute_scd2_merge(spark: SparkSession, changes_df: DataFrame):
    """
    Execute the SCD Type 2 MERGE INTO operation.
    
    This is the core logic:
    - MATCHED + is_current=true → close the old record (set end date, is_current=false)
    - NOT MATCHED → insert as new current record
    - Additional INSERT for matched records (the new version)
    
    Iceberg's MERGE INTO supports multiple MATCHED/NOT MATCHED clauses.
    """
    # Register changes as temp view
    changes_df.createOrReplaceTempView("staged_changes")
    
    # The MERGE handles three cases:
    # 1. Existing current record that's changing → close it
    # 2. New version of changed record → insert it
    # 3. Brand new customer → insert first version
    
    # Because Iceberg MERGE doesn't support INSERT for MATCHED rows directly,
    # we split into two operations: UPDATE matched + INSERT all changes as new versions
    
    merge_sql = """
    MERGE INTO lakehouse.dimensions.customer_scd2 AS target
    USING staged_changes AS source
    ON target.customer_id = source.customer_id 
       AND target.is_current = true
    
    WHEN MATCHED AND source.cdc_operation IN ('UPDATE', 'DELETE') THEN
        UPDATE SET
            target.is_current = false,
            target.effective_end_ts = source.cdc_event_ts
    
    WHEN NOT MATCHED AND source.cdc_operation IN ('INSERT', 'UPDATE') THEN
        INSERT (
            surrogate_key,
            customer_id,
            customer_name,
            email,
            phone,
            address_line1,
            address_line2,
            city,
            state,
            postal_code,
            country,
            customer_segment,
            credit_score,
            account_status,
            preferred_channel,
            loyalty_tier,
            assigned_rep_id,
            last_login_ts,
            session_count,
            effective_start_ts,
            effective_end_ts,
            is_current,
            source_system,
            cdc_operation,
            cdc_event_ts,
            ingestion_ts,
            batch_id
        ) VALUES (
            source.new_surrogate_key,
            source.customer_id,
            source.customer_name,
            source.email,
            source.phone,
            source.address_line1,
            source.address_line2,
            source.city,
            source.state,
            source.postal_code,
            source.country,
            source.customer_segment,
            source.credit_score,
            source.account_status,
            source.preferred_channel,
            source.loyalty_tier,
            source.assigned_rep_id,
            source.last_login_ts,
            source.session_count,
            source.cdc_event_ts,
            CAST(NULL AS TIMESTAMP),
            true,
            source.source_system,
            source.cdc_operation,
            source.cdc_event_ts,
            source.ingestion_ts,
            source.batch_id
        )
    """
    
    logger.info("Executing MERGE: closing old records...")
    spark.sql(merge_sql)
    
    # Second pass: Insert new versions for MATCHED records (updates)
    # The MERGE above only closed old records for matched rows.
    # We need to insert the new active version.
    insert_new_versions_sql = """
    INSERT INTO lakehouse.dimensions.customer_scd2
    SELECT
        new_surrogate_key AS surrogate_key,
        customer_id,
        customer_name,
        email,
        phone,
        address_line1,
        address_line2,
        city,
        state,
        postal_code,
        country,
        customer_segment,
        credit_score,
        account_status,
        preferred_channel,
        loyalty_tier,
        assigned_rep_id,
        last_login_ts,
        session_count,
        cdc_event_ts AS effective_start_ts,
        CAST(NULL AS TIMESTAMP) AS effective_end_ts,
        true AS is_current,
        source_system,
        cdc_operation,
        cdc_event_ts,
        ingestion_ts,
        batch_id
    FROM staged_changes
    WHERE cdc_operation = 'UPDATE'
    """
    
    logger.info("Inserting new versions for updated records...")
    spark.sql(insert_new_versions_sql)


def execute_scd2_merge_single_pass(spark: SparkSession, changes_df: DataFrame):
    """
    Alternative: Single-pass SCD Type 2 using DataFrame API.
    
    More efficient for large batches because it avoids two separate writes.
    Reads current state, computes closed + new records, then overwrites
    the affected partitions.
    """
    target_table = "lakehouse.dimensions.customer_scd2"
    
    # Read current records that will be affected
    affected_current = (
        spark.read.format("iceberg").load(target_table)
        .filter(F.col("is_current") == True)
        .join(
            changes_df.select("customer_id").distinct(),
            "customer_id",
            "inner"
        )
    )
    
    # Close affected records
    closed_records = (
        affected_current
        .join(
            changes_df.select(
                F.col("customer_id"),
                F.col("cdc_event_ts").alias("close_ts")
            ),
            "customer_id",
            "inner"
        )
        .withColumn("is_current", F.lit(False))
        .withColumn("effective_end_ts", F.col("close_ts"))
        .drop("close_ts")
    )
    
    # New versions (for inserts and updates)
    new_records = (
        changes_df
        .filter(F.col("cdc_operation").isin("INSERT", "UPDATE"))
        .select(
            F.col("new_surrogate_key").alias("surrogate_key"),
            "customer_id", "customer_name", "email", "phone",
            "address_line1", "address_line2", "city", "state",
            "postal_code", "country", "customer_segment", "credit_score",
            "account_status", "preferred_channel", "loyalty_tier",
            "assigned_rep_id", "last_login_ts", "session_count",
            F.col("cdc_event_ts").alias("effective_start_ts"),
            F.lit(None).cast("timestamp").alias("effective_end_ts"),
            F.lit(True).alias("is_current"),
            "source_system", "cdc_operation", "cdc_event_ts",
            "ingestion_ts", "batch_id"
        )
    )
    
    # Write closed records (overwrite dynamic partition)
    closed_records.writeTo(target_table).overwritePartitions()
    
    # Append new records
    new_records.writeTo(target_table).append()
    
    logger.info(
        f"SCD2 complete: {closed_records.count()} closed, "
        f"{new_records.count()} new versions inserted"
    )


def handle_out_of_order_events(spark: SparkSession, changes_df: DataFrame) -> DataFrame:
    """
    Handle CDC events that arrive out of order.
    
    Example: An UPDATE with ts=T2 arrives BEFORE an earlier UPDATE with ts=T1.
    Without handling, we'd create incorrect version chains.
    
    Strategy: Compare event timestamp against current record's effective_start_ts.
    If the event is OLDER than the current record, it's a late-arriving event
    that needs special handling.
    """
    current_dim = (
        spark.read.format("iceberg")
        .load("lakehouse.dimensions.customer_scd2")
        .filter(F.col("is_current") == True)
        .select("customer_id", F.col("effective_start_ts").alias("current_start_ts"))
    )
    
    annotated = changes_df.join(current_dim, "customer_id", "left")
    
    # Normal events: event timestamp >= current record start (or new customer)
    normal_events = annotated.filter(
        (F.col("current_start_ts").isNull()) |
        (F.col("cdc_event_ts") >= F.col("current_start_ts"))
    ).drop("current_start_ts")
    
    # Late events: event timestamp < current record start
    late_events = annotated.filter(
        (F.col("current_start_ts").isNotNull()) &
        (F.col("cdc_event_ts") < F.col("current_start_ts"))
    ).drop("current_start_ts")
    
    late_count = late_events.count()
    if late_count > 0:
        logger.warning(f"Detected {late_count} out-of-order events, routing to dead letter")
        # Write late events to dead letter table for manual review
        (late_events.write
         .format("iceberg")
         .mode("append")
         .save("lakehouse.staging.customer_cdc_dead_letter"))
    
    return normal_events


def run_scd2_pipeline(batch_start: str, batch_end: str):
    """Main entry point for the SCD2 pipeline."""
    batch_id = f"scd2-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting SCD2 batch: {batch_id} [{batch_start} → {batch_end}]")
    
    spark = create_spark_session()
    
    try:
        # Step 1: Read CDC batch
        raw_cdc = read_cdc_batch(spark, batch_start, batch_end)
        raw_count = raw_cdc.count()
        logger.info(f"Read {raw_count} raw CDC events")
        
        if raw_count == 0:
            logger.info("No events to process, exiting")
            return
        
        # Step 2: Deduplicate
        deduped = deduplicate_cdc_events(raw_cdc)
        
        # Step 3: Prepare staging records
        staged = prepare_staging_records(deduped, batch_id)
        
        # Step 4: Handle out-of-order events
        valid_changes = handle_out_of_order_events(spark, staged)
        
        # Step 5: Detect actual changes (skip no-op updates)
        actual_changes = detect_actual_changes(valid_changes, spark)
        
        # Step 6: Cache changes for multi-use
        actual_changes.cache()
        change_count = actual_changes.count()
        logger.info(f"Processing {change_count} actual dimension changes")
        
        # Step 7: Execute MERGE
        execute_scd2_merge(spark, actual_changes)
        
        # Step 8: Emit metrics
        emit_metrics(spark, batch_id, raw_count, change_count)
        
        actual_changes.unpersist()
        logger.info(f"Batch {batch_id} complete")
        
    except Exception as e:
        logger.error(f"Batch {batch_id} failed: {e}")
        raise
    finally:
        spark.stop()


def emit_metrics(spark: SparkSession, batch_id: str, raw_count: int, change_count: int):
    """Emit pipeline metrics to monitoring."""
    metrics = {
        "batch_id": batch_id,
        "raw_cdc_events": raw_count,
        "actual_changes": change_count,
        "dedup_ratio": round(1 - change_count / max(raw_count, 1), 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Write to metrics table
    metrics_df = spark.createDataFrame([metrics])
    (metrics_df.write
     .format("iceberg")
     .mode("append")
     .save("lakehouse.monitoring.scd2_batch_metrics"))


if __name__ == "__main__":
    import sys
    batch_start = sys.argv[1]
    batch_end = sys.argv[2]
    run_scd2_pipeline(batch_start, batch_end)
```

---

## Airflow Orchestration

```python
"""
Airflow DAG for SCD Type 2 pipeline.
Runs every 15 minutes, processing CDC events in micro-batches.
"""
from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago
from datetime import timedelta
import pendulum

default_args = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": "slack_alert_critical",
}

with DAG(
    dag_id="customer_scd2_merge",
    default_args=default_args,
    schedule_interval="*/15 * * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,  # Prevent concurrent MERGE on same table
    tags=["scd2", "customer", "dimensions"],
) as dag:

    check_cdc_lag = PythonOperator(
        task_id="check_cdc_lag",
        python_callable=check_kafka_lag,
        op_kwargs={"topic": "cdc.customers.customer_profile", "max_lag_seconds": 900},
    )

    scd2_merge = SparkSubmitOperator(
        task_id="execute_scd2_merge",
        application="/opt/spark-jobs/customer_scd2_merge.py",
        application_args=[
            "{{ data_interval_start.isoformat() }}",
            "{{ data_interval_end.isoformat() }}",
        ],
        conf={
            "spark.executor.instances": "20",
            "spark.executor.memory": "32g",
            "spark.executor.cores": "8",
            "spark.driver.memory": "16g",
            "spark.sql.shuffle.partitions": "400",
        },
        packages="org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0",
    )

    compact_table = SparkSubmitOperator(
        task_id="compact_current_partition",
        application="/opt/spark-jobs/iceberg_maintenance.py",
        application_args=[
            "lakehouse.dimensions.customer_scd2",
            "--action", "compact",
            "--filter", "is_current=true",
            "--target-file-size", "268435456",
        ],
        trigger_rule="all_success",
    )

    check_cdc_lag >> scd2_merge >> compact_table
```

---

## Production Concerns

### Handling Schema Changes in Source

When source systems add/modify columns, the pipeline must handle this gracefully:

```python
def handle_schema_evolution(spark: SparkSession, cdc_df: DataFrame):
    """
    Detect new columns in CDC events and evolve Iceberg schema.
    
    Iceberg supports adding columns without rewriting existing data.
    Old rows will have NULL for newly added columns.
    """
    # Get current Iceberg table schema
    table = spark.table("lakehouse.dimensions.customer_scd2")
    existing_cols = set(table.schema.fieldNames())
    
    # Get columns from incoming CDC
    incoming_cols = set(cdc_df.columns) - {
        "__op", "__source_ts_ms", "__source_server",
        "__source_db", "__source_table", "__deleted"
    }
    
    # Detect new columns
    new_cols = incoming_cols - existing_cols
    
    if new_cols:
        logger.warning(f"Schema evolution detected! New columns: {new_cols}")
        for col_name in new_cols:
            col_type = cdc_df.schema[col_name].dataType.simpleString()
            spark.sql(f"""
                ALTER TABLE lakehouse.dimensions.customer_scd2
                ADD COLUMN {col_name} {col_type}
            """)
            logger.info(f"Added column: {col_name} ({col_type})")
```

### Optimistic Concurrency Handling

```python
def merge_with_retry(spark: SparkSession, changes_df: DataFrame, max_retries: int = 5):
    """
    Handle Iceberg optimistic concurrency conflicts.
    
    When multiple writers attempt concurrent commits, Iceberg uses optimistic
    concurrency. If a conflict occurs (another writer modified the same files),
    the commit is retried with refreshed metadata.
    
    Iceberg handles this automatically via table properties:
      commit.retry.num-retries = 10
      commit.retry.min-wait-ms = 100
    
    But for application-level conflicts (e.g., two batches updating same customer),
    we add explicit retry logic.
    """
    from py4j.protocol import Py4JJavaError
    
    for attempt in range(max_retries):
        try:
            execute_scd2_merge(spark, changes_df)
            return
        except Py4JJavaError as e:
            if "CommitFailedException" in str(e):
                logger.warning(
                    f"Commit conflict on attempt {attempt + 1}/{max_retries}, "
                    f"retrying in {2 ** attempt}s..."
                )
                time.sleep(2 ** attempt)
                # Refresh cached data
                changes_df.unpersist()
                changes_df.cache()
            else:
                raise
    
    raise RuntimeError(f"MERGE failed after {max_retries} retries due to conflicts")
```

### Copy-on-Write Performance Tuning

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Copy-on-Write Optimization for MERGE                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ How CoW MERGE works:                                                      │
│ 1. Identify data files containing matched rows                           │
│ 2. Read entire file, apply updates, write new file                       │
│ 3. Commit: delete old file reference, add new file reference             │
│                                                                           │
│ Optimization levers:                                                      │
│                                                                           │
│ 1. SORT ORDER (customer_id)                                              │
│    - Changes for same customer land in same file                         │
│    - Fewer files need rewriting per MERGE batch                          │
│    - 500M rows / 256MB files ≈ 2000 files for is_current=true           │
│    - With good sort: ~200 files touched per batch (10%)                  │
│    - Without sort: ~1800 files touched (90%)                             │
│                                                                           │
│ 2. FILE SIZE (256MB)                                                     │
│    - Larger files = fewer total files = faster planning                  │
│    - But larger files = more data rewritten per change                   │
│    - 256MB is sweet spot for 500M row table with 50M changes/day        │
│                                                                           │
│ 3. PARTITION PRUNING (is_current=true)                                   │
│    - MERGE only scans is_current=true partition                          │
│    - Skips entire history (18B rows) during match phase                  │
│    - Reduces scan from 18B rows to 500M rows                            │
│                                                                           │
│ 4. BATCH SIZE                                                            │
│    - 15-min micro-batch ≈ 520K changes                                  │
│    - Small enough for fast MERGE (<5 min)                                │
│    - Large enough to amortize commit overhead                            │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Query Patterns

### Point-in-Time Lookup

```sql
-- What was customer 1001's state on 2024-06-15?
SELECT *
FROM lakehouse.dimensions.customer_scd2
WHERE customer_id = 1001
  AND effective_start_ts <= TIMESTAMP '2024-06-15 00:00:00'
  AND (effective_end_ts > TIMESTAMP '2024-06-15 00:00:00' OR effective_end_ts IS NULL);
```

### Current State (Most Common Query)

```sql
-- Current state of all enterprise customers
-- Partition pruning on is_current=true makes this fast
SELECT *
FROM lakehouse.dimensions.customer_scd2
WHERE is_current = true
  AND customer_segment = 'enterprise';
```

### Change History for a Customer

```sql
-- Full version history for customer 1001
SELECT 
    surrogate_key,
    customer_name,
    email,
    customer_segment,
    effective_start_ts,
    effective_end_ts,
    cdc_operation
FROM lakehouse.dimensions.customer_scd2
WHERE customer_id = 1001
ORDER BY effective_start_ts;
```

### Bi-Temporal Query (Transaction Time + Valid Time)

```sql
-- What did we KNOW about customer 1001 as of our system state on Jan 20?
-- Uses Iceberg time travel (transaction time) + SCD dates (valid time)
SELECT *
FROM lakehouse.dimensions.customer_scd2
  FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-20 00:00:00'
WHERE customer_id = 1001
  AND is_current = true;
```

### Aggregate Change Analytics

```sql
-- Segment migration analysis: customers who changed segments in Q1 2024
WITH segment_changes AS (
    SELECT 
        customer_id,
        customer_segment AS new_segment,
        LAG(customer_segment) OVER (
            PARTITION BY customer_id ORDER BY effective_start_ts
        ) AS old_segment,
        effective_start_ts AS change_date
    FROM lakehouse.dimensions.customer_scd2
    WHERE customer_id IN (
        SELECT DISTINCT customer_id 
        FROM lakehouse.dimensions.customer_scd2
        WHERE effective_start_ts BETWEEN '2024-01-01' AND '2024-03-31'
          AND customer_segment IS NOT NULL
    )
)
SELECT 
    old_segment,
    new_segment,
    COUNT(*) AS migration_count,
    DATE_TRUNC('week', change_date) AS change_week
FROM segment_changes
WHERE old_segment != new_segment
  AND old_segment IS NOT NULL
  AND change_date BETWEEN '2024-01-01' AND '2024-03-31'
GROUP BY old_segment, new_segment, DATE_TRUNC('week', change_date)
ORDER BY migration_count DESC;
```

### dbt Downstream Model

```sql
-- models/marts/dim_customer_current.sql
-- Materialized as Iceberg table, refreshed after SCD2 MERGE completes

{{ config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by='customer_segment'
) }}

SELECT
    surrogate_key,
    customer_id,
    customer_name,
    email,
    city,
    state,
    country,
    customer_segment,
    loyalty_tier,
    account_status,
    effective_start_ts AS current_since,
    ingestion_ts AS last_updated
FROM {{ source('dimensions', 'customer_scd2') }}
WHERE is_current = true
```

---

## Monitoring & Alerting

### Key Metrics Dashboard

```python
# Monitoring queries for Grafana/Datadog dashboards

METRICS_QUERIES = {
    # CDC lag: time between source change and SCD table update
    "cdc_to_scd_lag_seconds": """
        SELECT 
            AVG(UNIX_TIMESTAMP(ingestion_ts) - UNIX_TIMESTAMP(cdc_event_ts)) AS avg_lag_sec,
            MAX(UNIX_TIMESTAMP(ingestion_ts) - UNIX_TIMESTAMP(cdc_event_ts)) AS max_lag_sec,
            PERCENTILE(UNIX_TIMESTAMP(ingestion_ts) - UNIX_TIMESTAMP(cdc_event_ts), 0.99) AS p99_lag_sec
        FROM lakehouse.dimensions.customer_scd2
        WHERE ingestion_ts > current_timestamp - INTERVAL 1 HOUR
    """,
    
    # MERGE batch performance
    "merge_batch_stats": """
        SELECT 
            batch_id,
            raw_cdc_events,
            actual_changes,
            dedup_ratio,
            timestamp
        FROM lakehouse.monitoring.scd2_batch_metrics
        WHERE timestamp > current_timestamp - INTERVAL 24 HOURS
        ORDER BY timestamp DESC
    """,
    
    # Table growth rate
    "history_growth": """
        SELECT 
            DATE_TRUNC('day', effective_start_ts) AS day,
            COUNT(*) AS new_versions_created
        FROM lakehouse.dimensions.customer_scd2
        WHERE effective_start_ts > current_date - INTERVAL 30 DAYS
        GROUP BY 1
        ORDER BY 1
    """,
    
    # Partition health
    "partition_file_counts": """
        SELECT 
            partition,
            file_count,
            total_size_bytes / 1024 / 1024 / 1024 AS size_gb,
            record_count
        FROM lakehouse.dimensions.customer_scd2.partitions
    """,
}

# Alert thresholds
ALERTS = {
    "cdc_lag_critical": {"threshold_seconds": 900, "severity": "P1"},
    "merge_duration_warning": {"threshold_minutes": 10, "severity": "P3"},
    "merge_duration_critical": {"threshold_minutes": 25, "severity": "P1"},
    "conflict_rate_warning": {"threshold_percent": 5, "severity": "P3"},
    "dead_letter_count": {"threshold_per_hour": 1000, "severity": "P2"},
    "history_growth_anomaly": {"threshold_stddev": 3, "severity": "P3"},
}
```

### Iceberg Table Maintenance

```python
# Scheduled maintenance tasks (daily)

def daily_maintenance(spark: SparkSession):
    table = "lakehouse.dimensions.customer_scd2"
    
    # 1. Compact small files in current partition (after many MERGEs)
    spark.sql(f"""
        CALL lakehouse.system.rewrite_data_files(
            table => '{table}',
            where => 'is_current = true',
            options => map(
                'target-file-size-bytes', '268435456',
                'min-file-size-bytes', '67108864',
                'max-file-size-bytes', '536870912',
                'partial-progress.enabled', 'true',
                'partial-progress.max-commits', '10'
            )
        )
    """)
    
    # 2. Expire old snapshots (keep 7 days for time travel)
    spark.sql(f"""
        CALL lakehouse.system.expire_snapshots(
            table => '{table}',
            older_than => TIMESTAMP '{(datetime.now() - timedelta(days=7)).isoformat()}',
            retain_last => 100
        )
    """)
    
    # 3. Remove orphan files
    spark.sql(f"""
        CALL lakehouse.system.remove_orphan_files(
            table => '{table}',
            older_than => TIMESTAMP '{(datetime.now() - timedelta(days=3)).isoformat()}'
        )
    """)
    
    # 4. Rewrite manifests for better query planning
    spark.sql(f"""
        CALL lakehouse.system.rewrite_manifests('{table}')
    """)
```

---

## Scale Characteristics

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Dimension                 │ Value                                         │
├───────────────────────────┼───────────────────────────────────────────────┤
│ Current records           │ 500M rows (~120GB in is_current=true)         │
│ Total with history        │ ~18B rows (~4.5TB across all partitions)      │
│ Daily CDC events          │ 50M events/day                                │
│ Actual dimension changes  │ ~35M/day (after dedup + change detection)     │
│ MERGE batch size          │ ~520K changes per 15-min batch                │
│ MERGE execution time      │ 3-5 minutes per batch                         │
│ Files in current partition│ ~470 files × 256MB                            │
│ Files rewritten per MERGE │ ~50-80 files (10-17% of current partition)    │
│ History retention         │ 2 years (older archived to separate table)    │
│ Storage cost (S3)         │ ~$105/month (4.5TB Standard + lifecycle)      │
│ Compute cost (Spark)      │ ~$8K/month (96 batches/day × 20 executors)   │
│ Query latency (current)   │ 2-5 seconds (Trino, partition pruned)         │
│ Query latency (PIT)       │ 5-15 seconds (depends on time range)          │
│ Compaction overhead       │ ~$200/month (daily maintenance)               │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Partition Evolution Example

As the table grows, evolve partitioning without rewriting data:

```sql
-- Original: partitioned by (is_current, months(effective_start_ts))
-- After 1 year, current partition has too many files.
-- Add customer_id bucket partitioning for better MERGE performance:

ALTER TABLE lakehouse.dimensions.customer_scd2
ADD PARTITION FIELD bucket(64, customer_id);

-- New data written with 3-level partitioning:
--   is_current / effective_start_ts_month / customer_id_bucket
-- Old data retains original 2-level partitioning (no rewrite needed)
-- MERGE now touches fewer files per batch (customer IDs cluster in buckets)
```

---

## Key Takeaways

1. **Iceberg MERGE INTO** makes SCD Type 2 viable at 500M+ scale on cheap object storage
2. **Copy-on-Write** is correct mode for batch MERGE (read-heavy workload, batch updates)
3. **Partition by is_current** is the single most important optimization — separates hot current state from cold history
4. **Sort by business key** minimizes files rewritten during MERGE
5. **Micro-batch every 15 minutes** balances latency vs. commit overhead
6. **Schema evolution** lets you add tracked columns without touching billions of historical rows
7. **Total cost ~$12K/month** vs. $150K+ for equivalent warehouse SCD — 10x cheaper at this scale
