# Streaming ETL into Data Warehouse

## Problem Statement

Traditional batch ETL (nightly loads) creates 24-hour data freshness gaps unacceptable for modern analytics. Organizations need continuous loading from operational databases into warehouses (Redshift, Snowflake, BigQuery) with sub-5-minute freshness. The challenges: micro-batch efficiency vs latency tradeoff, deduplication of CDC events in append-only warehouses, merge operations for SCD Type 2, and managing warehouse compute costs that spike with frequent loading.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Source Systems"
        PG[(PostgreSQL)]
        MY[(MySQL)]
        MONGO[(MongoDB)]
        API[REST APIs<br/>SaaS Sources]
    end

    subgraph "CDC / Ingestion"
        DBZ[Debezium<br/>Connectors]
        FIVETRAN[Fivetran /<br/>Airbyte]
    end

    subgraph "Kafka"
        T1[cdc.orders]
        T2[cdc.users]
        T3[cdc.payments]
        T4[cdc.events]
    end

    subgraph "Stream Processing (Flink)"
        DEDUP[Deduplication<br/>Window]
        TRANSFORM[Transformations<br/>+ Business Logic]
        MICRO[Micro-batch<br/>Assembler]
        SCHEMA[Schema<br/>Evolution Handler]
    end

    subgraph "Staging (S3)"
        STAGE[s3://staging/<br/>micro-batches/]
        MANIFEST[Manifest Files]
    end

    subgraph "Data Warehouse"
        subgraph "Redshift"
            RS_STAGE[Staging Tables]
            RS_TARGET[Target Tables<br/>(SCD Type 2)]
            RS_COPY[COPY Command<br/>from S3]
        end
        
        subgraph "Snowflake"
            SF_PIPE[Snowpipe<br/>(auto-ingest)]
            SF_STREAM[Snowflake Streams]
            SF_TASK[Snowflake Tasks<br/>(MERGE)]
            SF_TARGET[Target Tables]
        end
        
        subgraph "BigQuery"
            BQ_STREAM[BigQuery<br/>Storage Write API]
            BQ_MERGE[Scheduled<br/>MERGE Query]
            BQ_TARGET[Target Tables]
        end
    end

    PG --> DBZ
    MY --> DBZ
    MONGO --> DBZ
    API --> FIVETRAN

    DBZ --> T1
    DBZ --> T2
    DBZ --> T3
    FIVETRAN --> T4

    T1 --> DEDUP
    T2 --> DEDUP
    T3 --> DEDUP
    T4 --> DEDUP

    DEDUP --> TRANSFORM
    TRANSFORM --> MICRO
    MICRO --> SCHEMA

    SCHEMA --> STAGE
    STAGE --> MANIFEST

    MANIFEST --> RS_COPY --> RS_STAGE --> RS_TARGET
    STAGE --> SF_PIPE --> SF_STREAM --> SF_TASK --> SF_TARGET
    TRANSFORM --> BQ_STREAM --> BQ_MERGE --> BQ_TARGET
```

## Component Breakdown

### Micro-batch Assembly (Flink)

```python
# Flink job that assembles CDC events into efficient micro-batches
# Balances latency (small batches = fast) vs efficiency (large batches = cheap)

class MicroBatchAssembler:
    """
    Assembles CDC events into Parquet micro-batches for warehouse loading.
    Triggers flush on: size threshold OR time threshold (whichever first).
    """
    
    CONFIG = {
        'max_batch_size_mb': 128,        # Flush at 128MB
        'max_batch_records': 500000,     # Or 500K records
        'max_batch_age_seconds': 60,     # Or 60 seconds (latency SLA)
        'output_format': 'parquet',
        'compression': 'zstd',
        'partition_by': ['table_name', 'batch_date_hour'],
    }
    
    def configure_flink_sink(self):
        return """
        CREATE TABLE s3_staging (
            table_name STRING,
            record_id STRING,
            op STRING,
            payload STRING,
            cdc_timestamp BIGINT,
            batch_date_hour STRING
        ) PARTITIONED BY (table_name, batch_date_hour)
        WITH (
            'connector' = 'filesystem',
            'path' = 's3://data-staging/micro-batches/',
            'format' = 'parquet',
            'parquet.compression' = 'ZSTD',
            'sink.rolling-policy.file-size' = '128MB',
            'sink.rolling-policy.rollover-interval' = '60s',
            'sink.rolling-policy.check-interval' = '10s'
        )
        """
```

### Deduplication Strategy

```sql
-- Problem: CDC can produce duplicates due to:
-- 1. Kafka consumer rebalance (re-processing)
-- 2. Flink checkpoint recovery (replay)
-- 3. Connector restart (overlap with previous batch)

-- Solution: Dedup at warehouse level using ROW_NUMBER

-- Redshift MERGE with deduplication
BEGIN TRANSACTION;

-- Load micro-batch into staging
COPY staging_orders FROM 's3://staging/micro-batches/orders/2024-01-15-10/'
IAM_ROLE 'arn:aws:iam::123:role/redshift-copy'
FORMAT PARQUET;

-- Dedup within batch (keep latest per record)
CREATE TEMP TABLE deduped_orders AS
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY order_id 
        ORDER BY cdc_timestamp DESC
    ) as rn
    FROM staging_orders
) WHERE rn = 1;

-- MERGE into target (handles insert + update + delete)
MERGE INTO orders_target t
USING deduped_orders s
ON t.order_id = s.order_id
WHEN MATCHED AND s.op = 'd' THEN DELETE
WHEN MATCHED THEN UPDATE SET
    customer_id = s.customer_id,
    status = s.status,
    amount = s.amount,
    updated_at = s.updated_at,
    _cdc_loaded_at = GETDATE()
WHEN NOT MATCHED AND s.op != 'd' THEN INSERT (
    order_id, customer_id, status, amount, created_at, updated_at, _cdc_loaded_at
) VALUES (
    s.order_id, s.customer_id, s.status, s.amount, s.created_at, s.updated_at, GETDATE()
);

-- Cleanup
DROP TABLE staging_orders;
TRUNCATE staging_orders;

END TRANSACTION;
```

### Snowflake Snowpipe Configuration

```sql
-- Snowflake: Auto-ingest with Snowpipe + Streams + Tasks

-- Stage pointing to S3
CREATE OR REPLACE STAGE cdc_stage
  URL = 's3://data-staging/micro-batches/'
  STORAGE_INTEGRATION = s3_integration
  FILE_FORMAT = (TYPE = PARQUET);

-- Raw landing table (append-only)
CREATE TABLE orders_raw (
    record_content VARIANT,
    filename STRING DEFAULT METADATA$FILENAME,
    load_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Snowpipe for auto-ingest
CREATE PIPE orders_pipe AUTO_INGEST = TRUE AS
  COPY INTO orders_raw (record_content)
  FROM @cdc_stage/orders/
  FILE_FORMAT = (TYPE = PARQUET);

-- Stream to capture changes to raw table
CREATE STREAM orders_raw_stream ON TABLE orders_raw;

-- Task to MERGE from raw to target (every 1 minute)
CREATE TASK orders_merge_task
  WAREHOUSE = 'ETL_XS'
  SCHEDULE = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('orders_raw_stream')
AS
MERGE INTO orders_target t
USING (
    SELECT 
        record_content:order_id::STRING as order_id,
        record_content:customer_id::STRING as customer_id,
        record_content:status::STRING as status,
        record_content:amount::DECIMAL(10,2) as amount,
        record_content:op::STRING as op,
        record_content:cdc_timestamp::BIGINT as cdc_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY record_content:order_id 
            ORDER BY record_content:cdc_timestamp DESC
        ) as rn
    FROM orders_raw_stream
    QUALIFY rn = 1
) s
ON t.order_id = s.order_id
WHEN MATCHED AND s.op = 'd' THEN DELETE
WHEN MATCHED AND s.cdc_timestamp > t._cdc_timestamp THEN UPDATE SET
    customer_id = s.customer_id,
    status = s.status,
    amount = s.amount,
    _cdc_timestamp = s.cdc_timestamp,
    _loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED AND s.op != 'd' THEN INSERT (
    order_id, customer_id, status, amount, _cdc_timestamp, _loaded_at
) VALUES (
    s.order_id, s.customer_id, s.status, s.amount, s.cdc_timestamp, CURRENT_TIMESTAMP()
);

ALTER TASK orders_merge_task RESUME;
```

### BigQuery Streaming Insert

```python
from google.cloud import bigquery_storage_v1
from google.protobuf import descriptor_pb2

class BigQueryStreamingLoader:
    """
    Uses BigQuery Storage Write API for high-throughput streaming.
    Committed mode for exactly-once, buffered mode for higher throughput.
    """
    
    def __init__(self, project_id: str, dataset: str):
        self.client = bigquery_storage_v1.BigQueryWriteClient()
        self.parent = f"projects/{project_id}/datasets/{dataset}/tables"
    
    async def stream_batch(self, table: str, records: list):
        """Stream micro-batch using committed mode (exactly-once)"""
        write_stream = self.client.create_write_stream(
            parent=f"{self.parent}/{table}",
            write_stream=bigquery_storage_v1.types.WriteStream(
                type_=bigquery_storage_v1.types.WriteStream.Type.COMMITTED
            )
        )
        
        # Serialize records to protocol buffers
        proto_rows = self._to_proto_rows(records)
        
        # Append rows
        request = bigquery_storage_v1.types.AppendRowsRequest(
            write_stream=write_stream.name,
            proto_rows=bigquery_storage_v1.types.AppendRowsRequest.ProtoData(
                rows=proto_rows
            )
        )
        
        response = self.client.append_rows(iter([request]))
        
        # Then run periodic MERGE from staging to final table
        # (BigQuery doesn't support streaming + DML on same table efficiently)
```

### SCD Type 2 Implementation

```sql
-- Slowly Changing Dimension Type 2 for historical tracking
-- Used for entities where history matters (customer status, pricing)

CREATE TABLE dim_customer_scd2 (
    surrogate_key BIGINT IDENTITY(1,1),
    customer_id VARCHAR(50) NOT NULL,
    
    -- Business fields
    name VARCHAR(200),
    email VARCHAR(255),
    tier VARCHAR(20),
    address_city VARCHAR(100),
    
    -- SCD2 metadata
    effective_from TIMESTAMP NOT NULL,
    effective_to TIMESTAMP DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    _cdc_op CHAR(1),
    _loaded_at TIMESTAMP DEFAULT GETDATE()
);

-- MERGE that maintains history
MERGE INTO dim_customer_scd2 t
USING staging_customers s
ON t.customer_id = s.customer_id AND t.is_current = TRUE
WHEN MATCHED AND (
    t.name != s.name OR t.email != s.email OR 
    t.tier != s.tier OR t.address_city != s.address_city
) THEN UPDATE SET
    effective_to = s.cdc_timestamp,
    is_current = FALSE
;

-- Insert new current records
INSERT INTO dim_customer_scd2 (
    customer_id, name, email, tier, address_city, 
    effective_from, is_current, _cdc_op
)
SELECT 
    s.customer_id, s.name, s.email, s.tier, s.address_city,
    s.cdc_timestamp, TRUE, s.op
FROM staging_customers s
WHERE s.op IN ('c', 'u')
AND NOT EXISTS (
    SELECT 1 FROM dim_customer_scd2 t 
    WHERE t.customer_id = s.customer_id 
    AND t.is_current = TRUE
    AND t.name = s.name AND t.email = s.email 
    AND t.tier = s.tier AND t.address_city = s.address_city
);
```

## Data Flow

```
End-to-end flow (target: < 5 minute latency):

1. Source DB write (t=0)
2. CDC capture (t=+200ms)
3. Kafka publish (t=+500ms)
4. Flink dedup + transform (t=+1s)
5. Micro-batch assembly (t=+1-60s, based on threshold)
6. Write to S3 staging (t=+2-62s)
7. Warehouse COPY/Snowpipe (t=+10-120s)
8. MERGE into target (t=+30-180s)
9. Available for query (t=+60-300s total)

Effective freshness: 1-5 minutes
```

## Scaling Strategies

### Warehouse-Specific Optimization

| Warehouse | Loading Method | Optimal Batch | Concurrency |
|-----------|---------------|---------------|-------------|
| Redshift | COPY from S3 | 128MB files | 4-8 parallel COPYs |
| Snowflake | Snowpipe | Any size (auto-scales) | Unlimited (serverless) |
| BigQuery | Storage Write API | 10MB-100MB | 100 concurrent streams |
| Databricks | Auto Loader | 128MB files | Auto-scales |

### Cost vs Freshness Tradeoff
```
Batch every 60s:  ~$2,000/month compute, 1-2 min freshness
Batch every 5min: ~$500/month compute, 5-6 min freshness  
Batch every 15min: ~$200/month compute, 15-16 min freshness
Batch every 1hr: ~$50/month compute, 1 hour freshness

Sweet spot for most: 1-5 minute batches
```

## Failure Handling

| Failure | Impact | Recovery |
|---------|--------|----------|
| Flink crash | Micro-batches delayed | Resume from Kafka checkpoint |
| S3 write fail | Batch lost | Retry from Kafka (still available) |
| COPY/Snowpipe fail | Target stale | Retry with same manifest |
| MERGE conflict | Duplicate processing | Dedup handles idempotently |
| Schema mismatch | Load rejected | Schema evolution handler adapts |
| Warehouse full | All loads fail | Alert, expand storage |

### Idempotent Loading
```sql
-- Track loaded batches to prevent double-loading
CREATE TABLE _load_tracking (
    batch_id VARCHAR(255) PRIMARY KEY,
    table_name VARCHAR(100),
    s3_path VARCHAR(500),
    record_count BIGINT,
    loaded_at TIMESTAMP DEFAULT GETDATE(),
    status VARCHAR(20)
);

-- Before loading, check if batch already processed
SELECT 1 FROM _load_tracking WHERE batch_id = :batch_id;
-- If exists: skip (idempotent)
-- If not: load + record in tracking table (same transaction)
```

## Cost Optimization

| Component | Monthly Cost | Optimization |
|-----------|-------------|--------------|
| Flink (micro-batch assembly) | ~$2,000 | Right-size, batch larger |
| S3 staging | ~$100 | Lifecycle delete after 7d |
| Redshift COPY compute | ~$1,500 | Schedule off-peak, RA3 |
| Snowflake Snowpipe | ~$800 | Auto-suspend warehouses |
| BigQuery streaming | ~$1,200 | Batch mode where possible |
| **Total (Snowflake path)** | **~$3,000/month** | For ~50 tables, 5-min freshness |

### Snowflake Cost Tips
```
1. Use XS warehouse for MERGE tasks (auto-suspend after 60s)
2. Snowpipe costs: $0.06 per 1000 files (batch larger files)
3. Cluster keys on MERGE target for faster lookups
4. Separate warehouse for loading vs querying
5. Use transient tables for staging (no fail-safe cost)
```

## Real-World Companies

| Company | Stack | Freshness |
|---------|-------|-----------|
| **Netflix** | Flink → Iceberg → Spark SQL | < 5 minutes |
| **Shopify** | Debezium → Kafka → Snowflake | < 5 minutes |
| **Uber** | Flink → Hudi → Presto | < 1 minute |
| **Stripe** | CDC → Flink → Redshift | < 5 minutes |
| **Airbnb** | Kafka → Spark Streaming → Hive | < 15 minutes |
| **DoorDash** | Debezium → Flink → Snowflake | < 5 minutes |
| **Instacart** | CDC → dbt + Snowpipe → Snowflake | < 10 minutes |
