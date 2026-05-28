# Compute Engine Integration with Iceberg

## The Iceberg Ecosystem

Iceberg is a **table format specification**, not a compute engine. It defines how data and metadata are organized. Any engine that implements the spec can read/write Iceberg tables — creating a true multi-engine data lakehouse.

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPUTE ENGINE LAYER                           │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│  Spark   │  Flink   │  Trino   │  Presto  │  Dremio / StarRocks│
│ (Batch + │(Stream + │ (Ad-hoc  │ (Ad-hoc  │  (Acceleration)    │
│  ETL)    │ Real-time)│ Analytics)│ Queries) │                    │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│                    ICEBERG TABLE FORMAT                           │
│         (Catalog → Metadata → Manifests → Data Files)           │
├─────────────────────────────────────────────────────────────────┤
│                    STORAGE LAYER (S3 / GCS / ADLS)              │
└─────────────────────────────────────────────────────────────────┘

Key Principle: Write with one engine, read with another.
              No vendor lock-in, no data duplication.
```

---

## Apache Flink + Iceberg (Streaming Ingestion)

### When to Use Flink with Iceberg
- **Real-time data ingestion** from Kafka/Kinesis into the lakehouse
- **Streaming ETL** with exactly-once semantics
- **CDC (Change Data Capture)** from operational databases
- **Low-latency updates** to dimension tables

### Architecture: Streaming Ingestion Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│             FLINK STREAMING INGESTION                            │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Kafka Topics            Flink Job             Iceberg Table    │
│  ┌──────────────┐       ┌──────────────┐      ┌────────────┐  │
│  │ user_events  │──────▶│ Deserialize  │      │            │  │
│  │ (JSON/Avro)  │       │ Validate     │      │ lakehouse  │  │
│  └──────────────┘       │ Transform    │─────▶│ .events    │  │
│  ┌──────────────┐       │ Partition    │      │            │  │
│  │ order_events │──────▶│              │      │ (Parquet   │  │
│  │ (Protobuf)   │       │ Checkpoint   │      │  on S3)    │  │
│  └──────────────┘       │ at interval  │      └────────────┘  │
│                          └──────────────┘                       │
│                                                                  │
│  Commit Cadence:                                                │
│    • Checkpoint every 1-5 minutes                               │
│    • Each checkpoint = one Iceberg commit (new snapshot)        │
│    • Exactly-once via Flink's two-phase commit protocol        │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Flink SQL Example: CDC to Iceberg

```sql
-- Source: MySQL CDC via Debezium connector
CREATE TABLE mysql_orders (
  order_id BIGINT,
  customer_id BIGINT,
  total_amount DECIMAL(10, 2),
  status STRING,
  updated_at TIMESTAMP(3),
  PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
  'connector' = 'mysql-cdc',
  'hostname' = 'mysql.prod.internal',
  'port' = '3306',
  'database-name' = 'ecommerce',
  'table-name' = 'orders',
  'server-time-zone' = 'UTC'
);

-- Sink: Iceberg table with upsert support
CREATE TABLE iceberg_orders (
  order_id BIGINT,
  customer_id BIGINT,
  total_amount DECIMAL(10, 2),
  status STRING,
  updated_at TIMESTAMP(3),
  PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
  'connector' = 'iceberg',
  'catalog-name' = 'lakehouse',
  'catalog-type' = 'hive',
  'warehouse' = 's3://data-lake/warehouse',
  'write.format.default' = 'parquet',
  'write.upsert.enabled' = 'true',
  'write.target-file-size-bytes' = '134217728'  -- 128MB
);

-- Streaming INSERT (runs continuously)
INSERT INTO iceberg_orders
SELECT * FROM mysql_orders;
```

### Flink Java API: Custom Streaming Sink

```java
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
env.enableCheckpointing(60000); // 1-minute checkpoints

// Kafka source
KafkaSource<Event> source = KafkaSource.<Event>builder()
    .setBootstrapServers("kafka:9092")
    .setTopics("clickstream")
    .setGroupId("iceberg-writer")
    .setValueOnlyDeserializer(new EventDeserializer())
    .build();

DataStream<Event> events = env.fromSource(source, WatermarkStrategy
    .forBoundedOutOfOrderness(Duration.ofSeconds(30))
    .withTimestampAssigner((event, ts) -> event.getTimestamp()),
    "Kafka Source");

// Transform and write to Iceberg
DataStream<RowData> rows = events
    .filter(e -> e.isValid())
    .map(new EventToRowDataMapper());

// Iceberg sink with exactly-once
FlinkSink.forRowData(rows)
    .tableLoader(TableLoader.fromHadoopTable("s3://lake/events"))
    .overwrite(false)
    .distributionMode(DistributionMode.HASH) // co-locate by partition
    .writeParallelism(16)
    .build();

env.execute("Iceberg Streaming Ingestion");
```

### Flink + Iceberg Operational Considerations

```
┌─────────────────────────────────────────────────────────────┐
│  CHECKPOINT INTERVAL vs FILE SIZE TRADE-OFF                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Short intervals (10s):                                     │
│    ✓ Lower data latency                                     │
│    ✗ Many small files (requires frequent compaction)        │
│    ✗ More S3 PUT requests (higher cost)                     │
│    ✗ More snapshots (metadata bloat)                        │
│                                                              │
│  Long intervals (5min):                                     │
│    ✓ Larger, optimally-sized files                          │
│    ✓ Fewer S3 requests                                      │
│    ✓ Less compaction needed                                 │
│    ✗ Higher end-to-end latency                              │
│                                                              │
│  Recommended: 1-2 minutes for most use cases                │
│  Use Flink's file rolling to target 128-256MB files         │
└─────────────────────────────────────────────────────────────┘
```

---

## Trino / Presto + Iceberg (Ad-Hoc Analytics)

### When to Use Trino/Presto with Iceberg
- **Interactive ad-hoc queries** by analysts and data scientists
- **Cross-table joins** across the lakehouse
- **Dashboard queries** with sub-second latency requirements
- **Data exploration** and profiling
- **Federated queries** joining Iceberg with other data sources

### Architecture: Query Federation

```
┌────────────────────────────────────────────────────────────────┐
│              TRINO FEDERATED QUERY ENGINE                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Analyst SQL                  Trino Coordinator                 │
│  ┌──────────────────┐        ┌──────────────────────────┐     │
│  │ SELECT *          │       │ • Parse query             │     │
│  │ FROM iceberg.     │──────▶│ • Plan with Iceberg meta  │     │
│  │   events e        │       │ • Prune partitions        │     │
│  │ JOIN postgres.    │       │ • Prune files (min/max)   │     │
│  │   users u         │       │ • Distribute to workers   │     │
│  │ ON e.user_id =   │       └──────────────────────────┘     │
│  │   u.id           │                    │                     │
│  └──────────────────┘                    ▼                     │
│                              ┌──────────────────────────┐      │
│                              │     Trino Workers         │      │
│  Data Sources:               │ • Read Parquet from S3    │      │
│  ┌────────────┐             │ • Column pruning          │      │
│  │ Iceberg/S3 │◀────────────│ • Predicate pushdown      │      │
│  └────────────┘             │ • Join execution          │      │
│  ┌────────────┐             │ • Aggregation             │      │
│  │ PostgreSQL │◀────────────│                           │      │
│  └────────────┘             └──────────────────────────┘      │
│  ┌────────────┐                                                │
│  │ Elasticsearch│                                              │
│  └────────────┘                                                │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Trino Connector Configuration

```properties
# etc/catalog/iceberg.properties
connector.name=iceberg
iceberg.catalog.type=glue            # AWS Glue as catalog
hive.metastore.uri=thrift://hive:9083  # Alternative: Hive Metastore
iceberg.file-format=PARQUET
iceberg.compression-codec=ZSTD

# Performance tuning
iceberg.max-partitions-per-writer=1000
iceberg.split-size=134217728         # 128MB split size
iceberg.target-max-file-size=536870912  # 512MB target file

# S3 access
hive.s3.endpoint=s3.amazonaws.com
hive.s3.aws-access-key=${ENV:AWS_ACCESS_KEY}
hive.s3.aws-secret-key=${ENV:AWS_SECRET_KEY}
```

### Trino Query Examples

```sql
-- Time travel query
SELECT * FROM iceberg.lakehouse.events
FOR TIMESTAMP AS OF TIMESTAMP '2024-06-15 00:00:00';

-- Snapshot metadata inspection
SELECT snapshot_id, committed_at, operation, summary
FROM iceberg.lakehouse."events$snapshots"
ORDER BY committed_at DESC
LIMIT 10;

-- Partition pruning + predicate pushdown (both happen automatically)
SELECT 
  event_type,
  COUNT(*) as event_count,
  AVG(response_time_ms) as avg_latency
FROM iceberg.lakehouse.events
WHERE event_date >= DATE '2024-06-01'       -- partition pruning
  AND event_type IN ('page_view', 'click')  -- pushed to Parquet reader
GROUP BY event_type;

-- Manifest file inspection
SELECT 
  path, 
  partition,
  record_count,
  file_size_in_bytes,
  lower_bounds,
  upper_bounds
FROM iceberg.lakehouse."events$files"
WHERE partition.event_date = DATE '2024-06-15';
```

### Why Trino Excels with Iceberg

```
Trino + Iceberg Performance Advantages:

1. METADATA-DRIVEN PLANNING
   Trino reads Iceberg metadata before touching data files.
   Manifest-level pruning eliminates entire file groups.
   Result: 10-100x fewer files scanned vs. full table scan.

2. PREDICATE PUSHDOWN TO PARQUET
   WHERE clauses pushed into Parquet column readers.
   Row groups skipped based on column statistics.
   Result: Only relevant rows decoded from disk.

3. DYNAMIC FILTERING
   JOIN predicates become runtime filters for the probe side.
   Example: JOIN on user_id = 12345 only reads Iceberg files
            that contain user_id 12345 (via manifest stats).

4. WORKER-LEVEL PARALLELISM
   Each Iceberg data file becomes one or more splits.
   Workers process splits in parallel across the cluster.
   No coordinator bottleneck on file listing (unlike Hive).
```

---

## Apache Spark + Iceberg (Batch ETL & ML)

### When to Use Spark with Iceberg
- **Large-scale batch ETL** (transform terabytes of data)
- **Data quality pipelines** (validation, deduplication)
- **ML feature engineering** (generate training features from raw data)
- **Compaction and maintenance** (rewrite files, expire snapshots)
- **Backfill operations** (reprocess historical data)

### Spark Configuration

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("IcebergETL") \
    .config("spark.sql.extensions", 
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.lakehouse", 
            "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.lakehouse.type", "hive") \
    .config("spark.sql.catalog.lakehouse.uri", 
            "thrift://hive-metastore:9083") \
    .config("spark.sql.catalog.lakehouse.warehouse", 
            "s3://data-lake/warehouse") \
    .config("spark.sql.catalog.lakehouse.io-impl", 
            "org.apache.iceberg.aws.s3.S3FileIO") \
    .getOrCreate()
```

### Spark ETL Pattern: Incremental Processing

```python
# Read only new data since last processing (incremental read)
df_new = spark.read \
    .format("iceberg") \
    .option("start-snapshot-id", last_processed_snapshot) \
    .option("end-snapshot-id", current_snapshot) \
    .load("lakehouse.raw.events")

# Transform
df_enriched = df_new \
    .filter(col("event_type").isNotNull()) \
    .withColumn("event_hour", hour(col("event_time"))) \
    .withColumn("is_mobile", col("user_agent").contains("Mobile")) \
    .join(dim_users, "user_id", "left")

# Write to curated table (append mode)
df_enriched.writeTo("lakehouse.curated.enriched_events") \
    .option("fanout-enabled", "true") \
    .append()
```

### Spark Maintenance Operations

```python
# Compact small files (critical for streaming-ingested tables)
spark.sql("""
  CALL lakehouse.system.rewrite_data_files(
    table => 'curated.enriched_events',
    strategy => 'bin-pack',
    options => map(
      'target-file-size-bytes', '268435456',
      'min-file-size-bytes', '67108864',
      'max-file-size-bytes', '536870912',
      'partial-progress.enabled', 'true',
      'partial-progress.max-commits', '10'
    )
  )
""")

# Expire old snapshots (keep last 5 days)
spark.sql("""
  CALL lakehouse.system.expire_snapshots(
    table => 'curated.enriched_events',
    older_than => TIMESTAMP '2024-06-20 00:00:00',
    retain_last => 50
  )
""")

# Remove orphan files
spark.sql("""
  CALL lakehouse.system.remove_orphan_files(
    table => 'curated.enriched_events',
    older_than => TIMESTAMP '2024-06-18 00:00:00'
  )
""")
```

---

## Machine Learning + Iceberg (Training Data)

### When to Use ML Frameworks with Iceberg
- **Training data versioning** — reproducible model training
- **Feature stores** — point-in-time correct feature retrieval
- **Dataset iteration** — efficient large-scale data loading
- **Experiment tracking** — link model to exact training data snapshot

### Architecture: ML Training Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│              ML TRAINING DATA PIPELINE                           │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Feature Engineering (Spark)         Training (PyTorch/TF)      │
│  ┌───────────────────────────┐      ┌──────────────────────┐  │
│  │ Raw Events → Features      │      │                      │  │
│  │ • Join user demographics   │      │  model.fit(          │  │
│  │ • Aggregate last 30 days   │      │    IcebergDataset(   │  │
│  │ • Compute rolling stats    │      │      table,          │  │
│  │ • Write to feature table   │      │      snapshot_id,    │  │
│  └─────────────┬─────────────┘      │      columns,        │  │
│                │                      │      filter          │  │
│                ▼                      │    )                 │  │
│  ┌───────────────────────────┐      │  )                   │  │
│  │ Iceberg Feature Table      │─────▶│                      │  │
│  │ (versioned, time-travel)   │      └──────────────────────┘  │
│  │                            │                │                │
│  │ snapshot-2847: training v1 │                ▼                │
│  │ snapshot-2903: training v2 │      ┌──────────────────────┐  │
│  │ snapshot-2991: training v3 │      │ Model Registry        │  │
│  └───────────────────────────┘      │ model_v3:             │  │
│                                      │   trained_on:         │  │
│                                      │     snapshot-2991     │  │
│                                      │   metrics: ...        │  │
│                                      └──────────────────────┘  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### PyTorch + Iceberg (via PyIceberg)

```python
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import GreaterThanOrEqual, And, EqualTo
import pyarrow.dataset as ds
import torch
from torch.utils.data import Dataset, DataLoader

# Load Iceberg table at specific snapshot (reproducibility)
catalog = load_catalog("lakehouse", **{
    "type": "glue",
    "s3.region": "us-east-1"
})
table = catalog.load_table("ml.training_features")

# Read at exact snapshot for reproducibility
scan = table.scan(
    snapshot_id=2991,  # Pin to exact data version
    row_filter=And(
        GreaterThanOrEqual("event_date", "2024-01-01"),
        EqualTo("label_available", True)
    ),
    selected=["user_id", "feature_vector", "label", "weight"]
)

# Convert to PyArrow for zero-copy access
arrow_table = scan.to_arrow()

class IcebergDataset(Dataset):
    def __init__(self, arrow_table):
        self.features = arrow_table.column("feature_vector").to_numpy()
        self.labels = arrow_table.column("label").to_numpy()
        self.weights = arrow_table.column("weight").to_numpy()
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        return {
            "features": torch.tensor(self.features[idx], dtype=torch.float32),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
            "weight": torch.tensor(self.weights[idx], dtype=torch.float32)
        }

# Create DataLoader for training
dataset = IcebergDataset(arrow_table)
loader = DataLoader(dataset, batch_size=1024, shuffle=True, num_workers=4)

# Training loop with exact data provenance
for epoch in range(num_epochs):
    for batch in loader:
        loss = model(batch["features"], batch["label"])
        loss.backward()
        optimizer.step()

# Log which snapshot was used for this training run
mlflow.log_param("iceberg_snapshot_id", 2991)
mlflow.log_param("iceberg_table", "ml.training_features")
```

### Feature Store Pattern with Point-in-Time Correctness

```python
# Problem: Training data must use features AS THEY EXISTED at prediction time
# (not current values, which would cause data leakage)

# Iceberg time travel provides point-in-time correct features:

def get_training_features(entity_ids, event_timestamps):
    """
    For each (entity_id, timestamp) pair, retrieve features
    as they existed at that timestamp — preventing data leakage.
    """
    features = []
    
    # Group by date for efficient batch queries
    for date, group in entity_ids.groupby(event_timestamps.dt.date):
        # Read feature table as it existed on that date
        snapshot = table.scan(
            row_filter=In("entity_id", group.entity_ids.tolist()),
            # Time travel to the state at prediction time
            snapshot_id=get_snapshot_at_timestamp(table, date)
        ).to_arrow()
        
        features.append(snapshot)
    
    return pa.concat_tables(features)

def get_snapshot_at_timestamp(table, target_date):
    """Find the latest snapshot before target_date."""
    snapshots = table.metadata.snapshots
    valid = [s for s in snapshots 
             if s.timestamp_ms <= target_date.timestamp() * 1000]
    return max(valid, key=lambda s: s.timestamp_ms).snapshot_id
```

---

## Engine Selection Decision Matrix

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WHEN TO USE WHICH ENGINE                            │
├──────────────┬────────────────────────────────────────────────────────┤
│ Use Case     │ Best Engine │ Why                                      │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Stream       │ Flink       │ Exactly-once, low latency, CDC native   │
│ ingestion    │             │                                          │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Batch ETL    │ Spark       │ Mature, handles TBs, rich transformations│
│ (>100GB)     │             │                                          │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Ad-hoc       │ Trino       │ Sub-second on indexed data, federated   │
│ analytics    │             │ queries across sources                   │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Dashboard    │ Trino/      │ Concurrency, caching, fast response     │
│ queries      │ StarRocks   │                                          │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ ML training  │ Spark +     │ Feature engineering at scale, then       │
│ data         │ PyTorch     │ efficient iteration in training loop     │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Table        │ Spark       │ Rewrite operations need distributed      │
│ maintenance  │             │ compute for large tables                 │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Data quality │ Spark /     │ Complex validation logic + reporting     │
│ checks       │ Great Expect│                                          │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ Real-time    │ Flink +     │ Stream processing with lakehouse         │
│ aggregation  │ Iceberg     │ checkpointing for recovery              │
├──────────────┼─────────────┼──────────────────────────────────────────┤
│ CDC replica  │ Flink /     │ Upsert support, schema evolution        │
│              │ Debezium    │                                          │
└──────────────┴─────────────┴──────────────────────────────────────────┘
```

---

## Multi-Engine Architecture (Production Pattern)

```
┌─────────────────────────────────────────────────────────────────────┐
│                PRODUCTION LAKEHOUSE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  INGESTION LAYER                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Flink (streaming CDC)  │  Spark (batch loads)  │  Airbyte  │   │
│  └─────────────┬───────────┴──────────┬────────────┴─────┬─────┘   │
│                │                       │                   │         │
│                ▼                       ▼                   ▼         │
│  RAW LAYER (Bronze)                                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Iceberg Tables: raw.events, raw.orders, raw.users          │   │
│  │  • Append-only, no transforms                               │   │
│  │  • Partitioned by ingestion date                            │   │
│  │  • Retains 90 days of snapshots                             │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
│                                 │                                     │
│                    Spark ETL (hourly/daily)                           │
│                                 │                                     │
│                                 ▼                                     │
│  CURATED LAYER (Silver)                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Iceberg Tables: curated.events, curated.orders             │   │
│  │  • Deduplicated, validated, enriched                        │   │
│  │  • Optimized partitioning + Z-order sorting                 │   │
│  │  • SCD Type 2 via time travel                               │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
│                                 │                                     │
│                    Spark/dbt (daily)                                  │
│                                 │                                     │
│                                 ▼                                     │
│  CONSUMPTION LAYER (Gold)                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Iceberg Tables: analytics.daily_metrics, ml.features       │   │
│  │  • Pre-aggregated for fast queries                          │   │
│  │  • Materialized views, summary tables                       │   │
│  │  • Read by: Trino, ML pipelines, BI tools                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                 │                                     │
│                                 ▼                                     │
│  QUERY LAYER                                                         │
│  ┌──────────┬──────────┬──────────┬──────────────────────────┐     │
│  │ Trino    │ Spark ML │ Jupyter  │ Tableau / Looker / Superset│    │
│  │(analysts)│(training)│(data sci)│ (dashboards)              │     │
│  └──────────┴──────────┴──────────┴──────────────────────────┘     │
│                                                                       │
│  MAINTENANCE (Spark, scheduled)                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Compaction: every 2 hours for streaming tables           │   │
│  │  • Snapshot expiration: daily                               │   │
│  │  • Orphan file removal: weekly                              │   │
│  │  • Analyze table (stats update): after large writes         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Catalog Integration

The catalog is the glue that enables multi-engine access:

```
┌────────────────────────────────────────────────────────────────┐
│                    CATALOG OPTIONS                               │
├───────────────┬────────────────────────────────────────────────┤
│ Catalog       │ Best For                                        │
├───────────────┼────────────────────────────────────────────────┤
│ AWS Glue      │ AWS-native, serverless, IAM integration        │
│ Hive          │ Self-managed, Hadoop ecosystem compatibility   │
│   Metastore   │                                                │
│ Nessie        │ Git-like branching, multi-table transactions   │
│ REST Catalog  │ Cloud-agnostic, vendor-neutral, Tabular/Polaris│
│ Unity Catalog │ Databricks ecosystem, fine-grained governance  │
└───────────────┴────────────────────────────────────────────────┘

All engines point to the SAME catalog:

  Flink  ──┐
  Spark  ──┤──→  AWS Glue Catalog  ──→  s3://lake/warehouse/
  Trino  ──┤         (single source of truth for table locations)
  PyIceberg┘
```

---

## Performance Comparison by Engine

```
Benchmark: 1TB TPC-DS, Iceberg on S3, Parquet + ZSTD

┌──────────────────────────────────────────────────────────────────┐
│ Query Type           │ Spark  │ Trino  │ Flink  │ Notes          │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Full table scan      │ 120s   │ 85s    │ N/A    │ Trino: better  │
│ (SELECT COUNT(*))    │        │        │        │ parallelism    │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Point lookup         │ 8s     │ 0.5s   │ N/A    │ Trino: query   │
│ (WHERE id = X)       │        │        │        │ planning speed │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Aggregation with     │ 45s    │ 30s    │ N/A    │ Both good,     │
│ partition filter     │        │        │        │ Trino slightly │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Complex JOIN         │ 180s   │ 150s   │ N/A    │ Similar for    │
│ (3+ tables)          │        │        │        │ large joins    │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Streaming write      │ N/A    │ N/A    │ 2s lat │ Flink: purpose │
│ (end-to-end latency) │        │        │        │ built          │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Batch write 100GB    │ 180s   │ 300s   │ N/A    │ Spark: shuffle │
│                      │        │        │        │ optimized      │
├──────────────────────┼────────┼────────┼────────┼────────────────┤
│ Compaction 500GB     │ 600s   │ N/A    │ N/A    │ Spark only     │
│                      │        │        │        │ (maintenance)  │
└──────────────────────┴────────┴────────┴────────┴────────────────┘

Rule of thumb:
  • WRITE: Flink (streaming), Spark (batch)
  • READ: Trino (interactive), Spark (heavy compute)
  • MAINTAIN: Spark (compaction, expiration)
```

---

## Common Integration Pitfalls

### 1. Concurrent Write Conflicts

```
Problem: Flink streaming + Spark compaction writing simultaneously.

Solution: Use Iceberg's conflict resolution rules.
  • Flink APPEND + Spark REWRITE = Compatible (no conflict)
  • Flink APPEND + Spark DELETE = May conflict (retry needed)
  • Two Flink jobs to same table = Conflict (use different partitions)

Best Practice:
  • Streaming jobs: APPEND to one set of partitions
  • Batch jobs: Operate on different partitions or use WAP (Write-Audit-Publish)
  • Compaction: Always compatible with APPEND operations
```

### 2. Small File Problem from Streaming

```
Problem: Flink checkpoints every 60s → many small files → slow reads.

Solution: Automated compaction pipeline.
  • Schedule Spark compaction every 2 hours for streaming tables
  • Target 256MB file size after compaction
  • Use partial-progress commits to avoid holding locks too long
```

### 3. Schema Mismatch Across Engines

```
Problem: Flink evolves schema; Trino uses cached schema.

Solution:
  • All schema changes via a single engine (preferably Spark SQL ALTER TABLE)
  • Trino: set iceberg.expire-snapshot-time to refresh metadata cache
  • Flink: restart job after schema changes to pick up new schema
```
