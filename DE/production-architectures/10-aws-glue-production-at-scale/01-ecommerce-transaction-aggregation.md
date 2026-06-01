# E-Commerce Transaction Aggregation Pipeline at Amazon/Shopify Scale

## Real Production Use Case: Processing 5 Billion Order Events Daily

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 5 Billion Order Events/Day with Multi-dimensional Aggregation

### Business Context

Large-scale e-commerce marketplaces (Amazon, Shopify, Walmart Marketplace) process
enormous volumes of transactional data every second. Each customer interaction
generates a cascade of events:

- **Order placement** → order_created, payment_authorized, inventory_reserved
- **Fulfillment** → order_shipped, tracking_updated, delivery_confirmed
- **Post-purchase** → return_initiated, refund_processed, review_submitted
- **Seller payouts** → commission_calculated, payout_scheduled, payout_completed

The business needs near-real-time aggregated views across dozens of dimensions for:
- Executive dashboards (GMV by region, category, seller tier)
- Seller analytics (revenue, return rates, fulfillment SLA compliance)
- Finance reconciliation (daily revenue recognition, tax rollups)
- Product intelligence (top movers, declining SKUs, margin analysis)
- Fraud detection aggregates (velocity checks, anomaly baselines)

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCALE PARAMETERS                                      │
├──────────────────────────────┬──────────────────────────────────────────────┤
│ Parameter                    │ Value                                        │
├──────────────────────────────┼──────────────────────────────────────────────┤
│ Raw events per day           │ 5 Billion                                    │
│ Peak throughput              │ 500,000 orders/minute (Black Friday)         │
│ Average event size           │ 2-4 KB (JSON/Avro)                          │
│ Raw data volume per day      │ 50 TB (uncompressed), ~8 TB (Snappy)        │
│ Unique dimensions            │ 200+ (category, geo, seller, brand, etc.)   │
│ Aggregation grains           │ Hourly, Daily, Weekly, Monthly               │
│ Output tables                │ 45 Iceberg tables                           │
│ Historical depth             │ 3 years rolling (for YoY comparisons)       │
│ SLA: hourly aggs available   │ T+20 minutes                                │
│ SLA: daily aggs available    │ T+2 hours                                   │
│ Sellers/Merchants            │ 2.5 Million active                          │
│ Product SKUs                 │ 350 Million active                          │
│ Geographic markets           │ 22 countries, 500+ metro areas              │
│ Concurrent downstream users  │ 50,000+ (dashboards, APIs, ML pipelines)    │
└──────────────────────────────┴──────────────────────────────────────────────┘
```

### Event Schema (Simplified)

```json
{
  "event_id": "evt_8f3a2b1c-...",
  "event_type": "order_created",
  "timestamp": "2024-11-29T14:23:01.445Z",
  "order_id": "ord_9x7k2m...",
  "marketplace_id": "US",
  "seller_id": "sel_abc123",
  "buyer_id": "buy_xyz789",
  "items": [
    {
      "sku": "SKU-001",
      "category_l1": "Electronics",
      "category_l2": "Smartphones",
      "category_l3": "Android",
      "brand": "Samsung",
      "quantity": 1,
      "unit_price": 899.99,
      "discount": 100.00,
      "tax": 63.99,
      "total": 863.98
    }
  ],
  "shipping": {"method": "PRIME_2DAY", "cost": 0.00, "zip": "98101"},
  "payment": {"method": "CREDIT_CARD", "currency": "USD"},
  "metadata": {"device": "MOBILE_APP", "session_id": "..."}
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

```
┌──────────────────────────┬──────────────────────────────────────────────────┐
│ Approach                 │ Why It Fails at This Scale                       │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ RDBMS (PostgreSQL/MySQL) │ GROUP BY on 5B rows = hours-long queries.        │
│                          │ Single-node disk I/O bottleneck. No horizontal   │
│                          │ scaling for writes. Lock contention on           │
│                          │ aggregation tables during concurrent updates.    │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Redshift Direct Load     │ COPY command ingestion: 50TB/day exceeds         │
│                          │ cluster I/O capacity. Need 64+ ra3.16xl nodes    │
│                          │ ($500K+/month) just for ingestion. Vacuum/sort   │
│                          │ operations block queries during loading.         │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Lambda Per-Event         │ 5B invocations/day = $5,000+/day in Lambda       │
│                          │ costs alone. State management across events      │
│                          │ requires DynamoDB (another $10K+/day).           │
│                          │ Cold starts + retries = unpredictable latency.   │
│                          │ Cannot do window aggregations without external   │
│                          │ state store. Exactly-once is nearly impossible.  │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Real-time Only (Flink)   │ Works for current-state but cannot handle        │
│                          │ historical corrections (refund applied to last   │
│                          │ month's order). Late-arriving data requires      │
│                          │ recomputing entire windows. State size for 200+  │
│                          │ dimension combos exceeds memory. No native       │
│                          │ time-travel for audit.                           │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Spark on EMR (manual)    │ Works technically but: cluster management        │
│                          │ overhead, manual scaling, spot instance           │
│                          │ handling, Hive metastore maintenance, no         │
│                          │ built-in job bookmarks, monitoring requires      │
│                          │ custom tooling. 3-5 engineers just for infra.    │
└──────────────────────────┴──────────────────────────────────────────────────┘
```

### Why AWS Glue Is the Right Fit

- **Serverless**: No cluster management, auto-provisions resources
- **Job Bookmarks**: Native incremental processing without custom state
- **DynamicFrame**: Handles schema inconsistencies across marketplace events
- **Auto-scaling**: Scales DPUs based on data volume (10 → 200 workers)
- **Iceberg Integration**: Native support for merge-on-read and time-travel
- **Cost**: Pay only for compute time, not idle clusters
- **Glue Workflows**: Built-in orchestration with dependency management

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           E-COMMERCE AGGREGATION PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────────┐    ┌──────────────┐    ┌───────────────────────────────────────────┐
 │ Order Service│    │Payment Service│   │ Fulfillment Service                        │
 │  (500K/min)  │    │  (300K/min)  │    │  (200K/min)                               │
 └──────┬───────┘    └──────┬───────┘    └─────────────────┬─────────────────────────┘
        │                    │                              │
        ▼                    ▼                              ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │                        Amazon MSK (Kafka) - 128 Partitions                          │
 │                   Topics: orders.events, payments.events, fulfillment.events         │
 └──────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │                    Kafka Connect / Firehose → S3 Raw Landing                         │
 │         s3://data-lake-raw/events/year=2024/month=11/day=29/hour=14/                │
 │                    Format: Avro (Snappy compressed)                                  │
 │                    Partitioning: year/month/day/hour                                 │
 └──────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │                         AWS GLUE DATA CATALOG                                        │
 │  ┌─────────────────┐                                                                │
 │  │  Glue Crawler   │ ← Runs every 15 min, detects new partitions                   │
 │  │  (Incremental)  │   Updates table schema if new fields detected                  │
 │  └─────────────────┘                                                                │
 │  Tables: raw_order_events, raw_payment_events, raw_fulfillment_events               │
 └──────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┬┴──────────────────────┐
                    ▼                   ▼                        ▼
┌────────────────────────┐ ┌────────────────────────┐ ┌────────────────────────────┐
│   GLUE JOB 1           │ │   GLUE JOB 2           │ │   GLUE JOB 3               │
│   Cleanse & Dedupe     │ │   Multi-Grain Agg      │ │   Iceberg Merge & Output   │
│                        │ │                        │ │                            │
│ • Job Bookmarks        │ │ • Spark SQL            │ │ • MERGE INTO hourly_aggs   │
│ • DynamicFrame         │ │ • Window functions     │ │ • MERGE INTO daily_aggs    │
│ • resolveChoice()      │ │ • Cube/Rollup          │ │ • MERGE INTO monthly_aggs  │
│ • Dedup on event_id    │ │ • 200+ dimensions      │ │ • Partition evolution       │
│ • Schema validation    │ │ • Multiple time grains │ │ • Compaction trigger        │
│ • Dead letter queue    │ │                        │ │                            │
│                        │ │ Workers: G.2X (80 DPU) │ │ Workers: G.2X (40 DPU)    │
│ Workers: G.1X (40 DPU)│ │ Timeout: 120 min       │ │ Timeout: 60 min           │
│ Timeout: 60 min       │ │                        │ │                            │
└───────────┬────────────┘ └───────────┬────────────┘ └──────────────┬─────────────┘
            │                          │                              │
            ▼                          ▼                              ▼
┌────────────────────────┐ ┌────────────────────────┐ ┌────────────────────────────┐
│ s3://data-lake-clean/  │ │ s3://data-lake-agg/    │ │ s3://data-lake-serving/    │
│ events/cleaned/        │ │ staging/               │ │ iceberg/                   │
│ (Parquet, Zstd)        │ │ (Parquet, temp)        │ │ ├── hourly_sales/          │
│                        │ │                        │ │ ├── daily_sales/           │
│                        │ │                        │ │ ├── seller_metrics/        │
│                        │ │                        │ │ ├── category_analytics/    │
│                        │ │                        │ │ └── geo_revenue/           │
└────────────────────────┘ └────────────────────────┘ └──────────────┬─────────────┘
                                                                     │
                          ┌──────────────────────────────────────────┼────────────┐
                          │                                          │            │
                          ▼                                          ▼            ▼
              ┌────────────────────┐                    ┌──────────────┐  ┌──────────────┐
              │    Amazon Athena   │                    │   Redshift   │  │  QuickSight  │
              │   (Ad-hoc queries) │                    │   Spectrum   │  │  (Executive  │
              │                    │                    │  (BI tools)  │  │  Dashboards) │
              └────────────────────┘                    └──────────────┘  └──────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used (Deep Explanation)

### 4.1 Job Bookmarks for Incremental Processing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        JOB BOOKMARKS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Run N:   Processes partitions hour=10, hour=11, hour=12                    │
│           Bookmark saved: {"last_partition": "hour=12"}                      │
│                                                                             │
│  Run N+1: Starts from hour=13 (skips already-processed data)               │
│           Bookmark saved: {"last_partition": "hour=15"}                      │
│                                                                             │
│  CRITICAL: Bookmark only advances on job.commit()                           │
│            If job fails mid-way, next run reprocesses from last commit      │
│            This gives us exactly-once semantics for successful runs          │
│                                                                             │
│  For S3 sources:                                                            │
│  - Tracks by file modification timestamp                                    │
│  - New files in old partitions ARE picked up                                │
│  - Deleted files are NOT reprocessed                                        │
│                                                                             │
│  Limitation: Cannot bookmark within a single large file                     │
│  Solution: Kafka→S3 writes small files (128MB target)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 DynamicFrame resolveChoice for Schema Inconsistencies

In a marketplace with 2.5M sellers, event schemas drift:
- Some sellers send `price` as string "29.99", others as float 29.99
- Legacy events have `shipping_address` as flat string, new ones as struct
- Optional fields appear/disappear across marketplace versions

```python
# resolveChoice handles type ambiguity without failing the job
dyf = dyf.resolveChoice(
    choice="cast:double",          # Cast ambiguous price to double
    specs=[
        ("items.unit_price", "cast:double"),
        ("items.quantity", "cast:int"),
        ("shipping.cost", "cast:double"),
    ]
)
```

### 4.3 Pushdown Predicates for Partition Pruning

```python
# Without pushdown: Reads ALL partitions then filters (50TB scan)
# With pushdown: Only reads relevant partitions from S3 (500GB scan)
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="ecommerce_raw",
    table_name="order_events",
    push_down_predicate="year='2024' AND month='11' AND day='29' AND hour>='14'",
    additional_options={
        "jobBookmarkKeys": ["timestamp"],
        "jobBookmarkKeysSortOrder": "asc"
    }
)
```

### 4.4 Worker Type Selection

```
┌────────────────┬──────────┬────────┬───────────────────────────────────────┐
│ Worker Type    │ vCPU     │ Memory │ Use Case in This Pipeline             │
├────────────────┼──────────┼────────┼───────────────────────────────────────┤
│ Standard       │ 4        │ 16 GB  │ NOT USED - insufficient for aggs     │
│ G.1X           │ 4        │ 16 GB  │ Job 1: Cleansing (I/O bound)         │
│ G.2X           │ 8        │ 32 GB  │ Job 2: Aggregation (compute bound)   │
│ G.4X           │ 16       │ 64 GB  │ Backfill jobs (massive shuffles)     │
│ G.8X           │ 32       │ 128 GB │ NOT USED (cost prohibitive)          │
│ Z.2X           │ 8        │ 64 GB  │ ML feature engineering (high memory) │
└────────────────┴──────────┴────────┴───────────────────────────────────────┘

Why G.2X for aggregation:
- 200+ dimension GROUP BY creates massive shuffle
- Window functions require partition data in memory
- 32GB/worker prevents OOM during skewed seller aggregations
  (top 100 sellers have 40% of all transactions)
```

### 4.5 Auto-scaling Configuration

```python
# Glue Job parameters for auto-scaling
{
    "--enable-auto-scaling": "true",
    "NumberOfWorkers": 200,          # Maximum workers (scales DOWN from this)
    "WorkerType": "G.2X",
    # Glue monitors executor utilization and adjusts:
    # - Low utilization (<40%) → removes executors
    # - High utilization (>70%) → adds executors up to max
    # - Typical: 10-30 DPUs off-peak, 150-200 DPUs during Black Friday
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation

### 5.1 Glue Job 1: Cleansing & Deduplication

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ─────────────────────────────────────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_database',
    'source_table',
    'target_path',
    'dlq_path',
    'enable_metrics'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger = glueContext.get_logger()
logger.info(f"Starting cleansing job: {args['JOB_NAME']}")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
SOURCE_DATABASE = args['source_database']      # "ecommerce_raw"
SOURCE_TABLE = args['source_table']            # "order_events"
TARGET_PATH = args['target_path']              # "s3://data-lake-clean/events/"
DLQ_PATH = args['dlq_path']                    # "s3://data-lake-dlq/cleansing/"

# Spark tuning for this workload
spark.conf.set("spark.sql.shuffle.partitions", "400")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")

# ─────────────────────────────────────────────────────────────────────────────
# READ WITH JOB BOOKMARK (INCREMENTAL)
# ─────────────────────────────────────────────────────────────────────────────
dyf_raw = glueContext.create_dynamic_frame.from_catalog(
    database=SOURCE_DATABASE,
    table_name=SOURCE_TABLE,
    transformation_ctx="dyf_raw",              # CRITICAL: enables bookmarks
    additional_options={
        "jobBookmarkKeys": ["timestamp"],
        "jobBookmarkKeysSortOrder": "asc",
        "boundedFiles": 5000                   # Process max 5000 files per run
    }
)

record_count = dyf_raw.count()
logger.info(f"Read {record_count} records from bookmark position")

if record_count == 0:
    logger.info("No new data to process. Committing bookmark and exiting.")
    job.commit()
    sys.exit(0)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA RESOLUTION (DynamicFrame-specific)
# ─────────────────────────────────────────────────────────────────────────────
# Resolve type ambiguities from heterogeneous producers
dyf_resolved = dyf_raw.resolveChoice(
    specs=[
        ("items.unit_price", "cast:double"),
        ("items.quantity", "cast:int"),
        ("items.discount", "cast:double"),
        ("items.tax", "cast:double"),
        ("shipping.cost", "cast:double"),
    ]
)

# Flatten nested structs for easier aggregation downstream
dyf_flat = dyf_resolved.relationalize(
    root_table_name="order_events",
    staging_path=f"s3://glue-temp-{args['JOB_NAME']}/relationalize/"
)

# Convert to DataFrame for complex transformations
df = dyf_resolved.toDF()

# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
# Separate valid records from invalid ones (DLQ pattern)
df_valid = df.filter(
    (F.col("event_id").isNotNull()) &
    (F.col("order_id").isNotNull()) &
    (F.col("timestamp").isNotNull()) &
    (F.col("event_type").isin([
        "order_created", "order_updated", "order_cancelled",
        "payment_captured", "payment_refunded",
        "shipment_created", "delivery_confirmed",
        "return_initiated", "return_completed"
    ])) &
    (F.col("marketplace_id").isNotNull())
)

df_invalid = df.subtract(df_valid)
invalid_count = df_invalid.count()

if invalid_count > 0:
    logger.warn(f"Routing {invalid_count} invalid records to DLQ")
    df_invalid.write.mode("append").partquet(
        f"{DLQ_PATH}/dt={F.current_date()}"
    )

# Alert if invalid rate exceeds threshold
invalid_rate = invalid_count / record_count if record_count > 0 else 0
if invalid_rate > 0.05:  # >5% invalid = alert
    # Push metric to CloudWatch
    logger.error(f"HIGH INVALID RATE: {invalid_rate:.2%} - triggering alert")

# ─────────────────────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────────────
# Deduplicate on event_id, keeping latest version (for event corrections)
window_dedup = Window.partitionBy("event_id").orderBy(F.col("timestamp").desc())

df_deduped = (
    df_valid
    .withColumn("row_num", F.row_number().over(window_dedup))
    .filter(F.col("row_num") == 1)
    .drop("row_num")
)

dupes_removed = df_valid.count() - df_deduped.count()
logger.info(f"Removed {dupes_removed} duplicate events")

# ─────────────────────────────────────────────────────────────────────────────
# ENRICHMENT & NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────
df_enriched = (
    df_deduped
    # Parse timestamp into time dimensions
    .withColumn("event_ts", F.to_timestamp("timestamp"))
    .withColumn("event_date", F.to_date("event_ts"))
    .withColumn("event_hour", F.hour("event_ts"))
    .withColumn("event_day_of_week", F.dayofweek("event_ts"))
    # Normalize currency to USD (simplified - production uses lookup table)
    .withColumn("amount_usd",
        F.when(F.col("payment.currency") == "USD", F.col("items.total"))
         .when(F.col("payment.currency") == "EUR", F.col("items.total") * 1.08)
         .when(F.col("payment.currency") == "GBP", F.col("items.total") * 1.27)
         .otherwise(F.col("items.total"))  # Default to face value
    )
    # Extract geo dimensions
    .withColumn("country_code", F.col("marketplace_id"))
    .withColumn("postal_prefix", F.substring("shipping.zip", 1, 3))
)

# ─────────────────────────────────────────────────────────────────────────────
# WRITE CLEANED DATA (Partitioned Parquet)
# ─────────────────────────────────────────────────────────────────────────────
df_enriched.write \
    .mode("append") \
    .partitionBy("event_date", "event_hour", "marketplace_id") \
    .option("compression", "zstd") \
    .parquet(TARGET_PATH)

logger.info(f"Wrote {df_enriched.count()} cleaned records to {TARGET_PATH}")

# ─────────────────────────────────────────────────────────────────────────────
# COMMIT BOOKMARK (marks this data as processed)
# ─────────────────────────────────────────────────────────────────────────────
job.commit()
logger.info("Job bookmark committed successfully")
```

### 5.2 Glue Job 2: Multi-Grain Aggregation

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_path',
    'staging_path',
    'processing_date',
    'processing_hour'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger = glueContext.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# SPARK TUNING FOR HEAVY AGGREGATION
# ─────────────────────────────────────────────────────────────────────────────
spark.conf.set("spark.sql.shuffle.partitions", "800")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")

PROCESSING_DATE = args['processing_date']     # "2024-11-29"
PROCESSING_HOUR = args['processing_hour']     # "14"
SOURCE_PATH = args['source_path']
STAGING_PATH = args['staging_path']

# ─────────────────────────────────────────────────────────────────────────────
# READ CLEANED DATA WITH PARTITION PRUNING
# ─────────────────────────────────────────────────────────────────────────────
df = spark.read.parquet(SOURCE_PATH) \
    .filter(
        (F.col("event_date") == PROCESSING_DATE) &
        (F.col("event_hour") == int(PROCESSING_HOUR))
    )

df.cache()  # Reused across multiple aggregation passes
logger.info(f"Processing {df.count()} records for {PROCESSING_DATE} hour {PROCESSING_HOUR}")

# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION 1: HOURLY SALES BY MULTI-DIMENSION
# ─────────────────────────────────────────────────────────────────────────────
df_orders = df.filter(F.col("event_type") == "order_created")

# Explode items array for per-item aggregation
df_items = df_orders.select(
    F.col("order_id"),
    F.col("marketplace_id"),
    F.col("seller_id"),
    F.col("event_date"),
    F.col("event_hour"),
    F.col("country_code"),
    F.col("postal_prefix"),
    F.explode("items").alias("item")
).select(
    "*",
    F.col("item.sku").alias("sku"),
    F.col("item.category_l1").alias("category_l1"),
    F.col("item.category_l2").alias("category_l2"),
    F.col("item.category_l3").alias("category_l3"),
    F.col("item.brand").alias("brand"),
    F.col("item.quantity").alias("quantity"),
    F.col("item.unit_price").alias("unit_price"),
    F.col("item.discount").alias("discount"),
    F.col("item.tax").alias("tax"),
    F.col("item.total").alias("item_total"),
)

# Multi-dimensional hourly aggregation using CUBE
hourly_agg = df_items.cube(
    "event_date",
    "event_hour",
    "marketplace_id",
    "category_l1",
    "category_l2",
    "seller_id",
    "brand",
    "country_code"
).agg(
    F.count("order_id").alias("order_count"),
    F.sum("quantity").alias("units_sold"),
    F.sum("item_total").alias("gmv"),
    F.sum("discount").alias("total_discount"),
    F.sum("tax").alias("total_tax"),
    F.avg("unit_price").alias("avg_selling_price"),
    F.countDistinct("order_id").alias("unique_orders"),
    F.countDistinct("seller_id").alias("active_sellers"),
    F.countDistinct("sku").alias("unique_skus"),
).filter(
    # Remove the "all nulls" row from CUBE and keep meaningful combos
    F.col("event_date").isNotNull()
)

# Add aggregation metadata
hourly_agg = hourly_agg.withColumn(
    "agg_grain", F.lit("hourly")
).withColumn(
    "agg_timestamp", F.current_timestamp()
).withColumn(
    "agg_version", F.lit(1)
)

# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION 2: SELLER PERFORMANCE METRICS
# ─────────────────────────────────────────────────────────────────────────────
df_refunds = df.filter(F.col("event_type") == "payment_refunded")
df_returns = df.filter(F.col("event_type") == "return_completed")

seller_metrics = df_orders.groupBy(
    "event_date", "event_hour", "seller_id", "marketplace_id"
).agg(
    F.count("order_id").alias("orders_placed"),
    F.sum("amount_usd").alias("revenue_usd"),
    F.avg("amount_usd").alias("avg_order_value"),
    F.countDistinct("buyer_id").alias("unique_buyers"),
)

# Join with refund data for return rate
seller_refunds = df_refunds.groupBy("seller_id").agg(
    F.count("order_id").alias("refund_count"),
    F.sum("amount_usd").alias("refund_amount"),
)

seller_metrics = seller_metrics.join(
    F.broadcast(seller_refunds),   # Broadcast small refund DF
    on="seller_id",
    how="left"
).fillna(0, subset=["refund_count", "refund_amount"])

seller_metrics = seller_metrics.withColumn(
    "refund_rate", F.col("refund_count") / F.col("orders_placed")
)

# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION 3: GEO-BASED REVENUE BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
geo_revenue = df_items.groupBy(
    "event_date", "event_hour", "country_code", "postal_prefix", "category_l1"
).agg(
    F.sum("item_total").alias("revenue"),
    F.count("order_id").alias("order_count"),
    F.sum("quantity").alias("units"),
    F.avg("item_total").alias("avg_basket_size"),
)

# ─────────────────────────────────────────────────────────────────────────────
# WRITE STAGING OUTPUTS
# ─────────────────────────────────────────────────────────────────────────────
hourly_agg.write.mode("overwrite").parquet(
    f"{STAGING_PATH}/hourly_sales/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)
seller_metrics.write.mode("overwrite").parquet(
    f"{STAGING_PATH}/seller_metrics/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)
geo_revenue.write.mode("overwrite").parquet(
    f"{STAGING_PATH}/geo_revenue/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)

df.unpersist()
job.commit()
logger.info("Aggregation job completed successfully")
```

### 5.3 Glue Job 3: Iceberg Merge & Output

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'staging_path',
    'iceberg_warehouse',
    'processing_date',
    'processing_hour'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger = glueContext.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# ICEBERG CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
ICEBERG_WAREHOUSE = args['iceberg_warehouse']  # "s3://data-lake-serving/iceberg/"
PROCESSING_DATE = args['processing_date']
PROCESSING_HOUR = args['processing_hour']

spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", ICEBERG_WAREHOUSE)
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl",
               "org.apache.iceberg.aws.s3.S3FileIO")
spark.conf.set("spark.sql.extensions",
               "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

# ─────────────────────────────────────────────────────────────────────────────
# READ STAGING AGGREGATIONS
# ─────────────────────────────────────────────────────────────────────────────
staging_path = args['staging_path']

df_hourly = spark.read.parquet(
    f"{staging_path}/hourly_sales/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)
df_seller = spark.read.parquet(
    f"{staging_path}/seller_metrics/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)
df_geo = spark.read.parquet(
    f"{staging_path}/geo_revenue/dt={PROCESSING_DATE}/hr={PROCESSING_HOUR}/"
)

# ─────────────────────────────────────────────────────────────────────────────
# MERGE INTO ICEBERG: HOURLY SALES (Upsert for late-arriving corrections)
# ─────────────────────────────────────────────────────────────────────────────
df_hourly.createOrReplaceTempView("hourly_updates")

spark.sql("""
    MERGE INTO glue_catalog.ecommerce.hourly_sales_agg AS target
    USING hourly_updates AS source
    ON target.event_date = source.event_date
       AND target.event_hour = source.event_hour
       AND target.marketplace_id = source.marketplace_id
       AND target.category_l1 <=> source.category_l1
       AND target.category_l2 <=> source.category_l2
       AND target.seller_id <=> source.seller_id
       AND target.brand <=> source.brand
       AND target.country_code <=> source.country_code
    WHEN MATCHED AND source.agg_version > target.agg_version THEN
        UPDATE SET
            order_count = source.order_count,
            units_sold = source.units_sold,
            gmv = source.gmv,
            total_discount = source.total_discount,
            total_tax = source.total_tax,
            avg_selling_price = source.avg_selling_price,
            unique_orders = source.unique_orders,
            active_sellers = source.active_sellers,
            unique_skus = source.unique_skus,
            agg_timestamp = source.agg_timestamp,
            agg_version = source.agg_version
    WHEN NOT MATCHED THEN
        INSERT *
""")

logger.info("Merged hourly sales aggregations into Iceberg")

# ─────────────────────────────────────────────────────────────────────────────
# MERGE INTO ICEBERG: SELLER METRICS
# ─────────────────────────────────────────────────────────────────────────────
df_seller.createOrReplaceTempView("seller_updates")

spark.sql("""
    MERGE INTO glue_catalog.ecommerce.seller_metrics AS target
    USING seller_updates AS source
    ON target.event_date = source.event_date
       AND target.event_hour = source.event_hour
       AND target.seller_id = source.seller_id
       AND target.marketplace_id = source.marketplace_id
    WHEN MATCHED THEN
        UPDATE SET *
    WHEN NOT MATCHED THEN
        INSERT *
""")

# ─────────────────────────────────────────────────────────────────────────────
# MERGE INTO ICEBERG: GEO REVENUE
# ─────────────────────────────────────────────────────────────────────────────
df_geo.createOrReplaceTempView("geo_updates")

spark.sql("""
    MERGE INTO glue_catalog.ecommerce.geo_revenue AS target
    USING geo_updates AS source
    ON target.event_date = source.event_date
       AND target.event_hour = source.event_hour
       AND target.country_code = source.country_code
       AND target.postal_prefix = source.postal_prefix
       AND target.category_l1 = source.category_l1
    WHEN MATCHED THEN
        UPDATE SET *
    WHEN NOT MATCHED THEN
        INSERT *
""")

# ─────────────────────────────────────────────────────────────────────────────
# ICEBERG TABLE MAINTENANCE
# ─────────────────────────────────────────────────────────────────────────────
# Expire old snapshots (keep 7 days for time-travel)
spark.sql("""
    CALL glue_catalog.system.expire_snapshots(
        table => 'ecommerce.hourly_sales_agg',
        older_than => TIMESTAMP '{PROCESSING_DATE} 00:00:00' - INTERVAL 7 DAYS,
        retain_last => 168
    )
""")

# Compact small files (from frequent MERGE operations)
spark.sql("""
    CALL glue_catalog.system.rewrite_data_files(
        table => 'ecommerce.hourly_sales_agg',
        options => map('target-file-size-bytes', '536870912')
    )
""")

job.commit()
logger.info("Iceberg merge and maintenance completed")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

### 6.1 Late-Arriving Data

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LATE-ARRIVING DATA STRATEGY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Problem: Order placed at 14:58 but payment confirmation arrives at 15:03   │
│           Refund for Nov 15 order processed on Nov 29                       │
│           Seller correction applied retroactively                           │
│                                                                             │
│  Solution: Reprocessing Windows                                             │
│                                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                       │
│  │ Hour H  │  │ Hour H-1│  │ Hour H-2│  │ Hour H-3│  ← Always reprocess   │
│  │ (current│  │ (catch  │  │ (catch  │  │ (catch  │     last 3 hours       │
│  │  batch) │  │  late)  │  │  late)  │  │  late)  │                        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘                        │
│                                                                             │
│  For daily aggregations:                                                    │
│  - Recompute D-1 and D-2 on every daily run                                │
│  - Use Iceberg MERGE to update only changed rows                           │
│  - Time-travel allows auditors to see "what we reported at time T"         │
│                                                                             │
│  For monthly close:                                                         │
│  - Full recompute of current month on day M+3                              │
│  - "Preliminary" vs "Final" flag on aggregation records                    │
│  - Finance sign-off triggers version bump (agg_version)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Duplicate Detection (Idempotent Writes)

```python
# Iceberg MERGE provides natural idempotency:
# - Same aggregation key → UPDATE (no duplicates)
# - Rerunning the same hour produces identical output → no data corruption
#
# Additional safeguards:
# 1. event_id deduplication in Job 1 (window + row_number)
# 2. Idempotent aggregation keys include ALL grain dimensions
# 3. agg_version monotonically increases (stale writes rejected)
# 4. Iceberg snapshot isolation prevents read-write conflicts
```

### 6.3 Schema Evolution

```python
# Scenario: Product team adds "subscription_type" dimension in March 2024
#
# Glue handles this gracefully:
# 1. DynamicFrame automatically detects new field (no schema registry needed)
# 2. Iceberg schema evolution adds nullable column:
spark.sql("""
    ALTER TABLE glue_catalog.ecommerce.hourly_sales_agg
    ADD COLUMNS (subscription_type STRING)
""")
# 3. Old records have NULL for subscription_type
# 4. Aggregation code updated to include new dimension (backward compatible)
# 5. No backfill needed unless historical analysis requires it
```

### 6.4 Backfill Strategy

```python
# Backfill job: Reprocess historical data (e.g., after logic fix)
# Uses G.4X workers for maximum throughput, NO job bookmarks

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'start_date', 'end_date'
])

# Disable bookmarks for backfill
# Job parameter: --job-bookmark-option job-bookmark-disable

date_range = pd.date_range(args['start_date'], args['end_date'])
for dt in date_range:
    for hr in range(24):
        # Reprocess each hour partition
        df = spark.read.parquet(f"{SOURCE}/event_date={dt}/event_hour={hr}/")
        # ... run aggregation logic ...
        # Write with overwrite mode (not append) for backfill
        result.write.mode("overwrite").parquet(
            f"{STAGING}/hourly_sales/dt={dt}/hr={hr}/"
        )
```

### 6.5 Data Quality Checks (DQDL Rules)

```python
# AWS Glue Data Quality (built-in DQDL)
from awsglue.data_quality import EvaluateDataQuality

# Define rules
dqdl_ruleset = """
    Rules = [
        RowCount between 1000000 and 500000000,
        Completeness "event_id" = 1.0,
        Completeness "order_id" >= 0.99,
        Completeness "marketplace_id" = 1.0,
        ColumnValues "amount_usd" >= 0,
        ColumnValues "amount_usd" <= 1000000,
        Uniqueness "event_id" >= 0.999,
        CustomSql "SELECT COUNT(*) FROM primary WHERE event_date > current_date" = 0,
        DataFreshness "timestamp" <= 4 hours
    ]
"""

# Evaluate after cleansing
dq_results = EvaluateDataQuality.apply(
    frame=dyf_resolved,
    ruleset=dqdl_ruleset,
    publishing_options={
        "dataQualityEvaluationContext": "cleansing_job",
        "enableDataQualityCloudWatchMetrics": "true",
        "enableDataQualityResultsPublishing": "true",
    }
)

# Route failures
if dq_results.filter(F.col("outcome") == "FAIL").count() > 0:
    logger.error("Data quality check FAILED - halting pipeline")
    # Write failed data to quarantine
    # Trigger SNS alert
    raise Exception("DQ_CHECK_FAILED")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Workflow Orchestration

### Glue Workflow Definition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE WORKFLOW: ecommerce_hourly_aggregation               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐         ┌──────────────────┐         ┌───────────────┐  │
│  │  TRIGGER:    │────────▶│  JOB 1:          │────────▶│  TRIGGER:     │  │
│  │  Schedule    │         │  Cleanse &       │         │  On Success   │  │
│  │  (every 1hr) │         │  Deduplicate     │         │  of Job 1     │  │
│  └──────────────┘         └──────────────────┘         └───────┬───────┘  │
│                                                                 │          │
│                                                                 ▼          │
│                                                        ┌───────────────┐   │
│                                                        │  JOB 2:       │   │
│                                                        │  Multi-Grain  │   │
│                                                        │  Aggregation  │   │
│                                                        └───────┬───────┘   │
│                                                                 │          │
│                                                                 ▼          │
│                                                        ┌───────────────┐   │
│                                                        │  TRIGGER:     │   │
│                                                        │  On Success   │   │
│                                                        │  of Job 2     │   │
│                                                        └───────┬───────┘   │
│                                                                 │          │
│                                                                 ▼          │
│                                                        ┌───────────────┐   │
│                                                        │  JOB 3:       │   │
│                                                        │  Iceberg      │   │
│                                                        │  Merge        │   │
│                                                        └───────┬───────┘   │
│                                                                 │          │
│                                                                 ▼          │
│                                                        ┌───────────────┐   │
│                                                        │  CRAWLER:     │   │
│                                                        │  Update       │   │
│                                                        │  Catalog      │   │
│                                                        └───────────────┘   │
│                                                                            │
│  ON FAILURE (any job):                                                     │
│  ┌───────────────────────────────────────────┐                             │
│  │ → SNS Notification to #data-platform-alerts                             │
│  │ → CloudWatch Alarm (CRITICAL severity)     │                            │
│  │ → PagerDuty incident for on-call engineer  │                            │
│  │ → Workflow marked FAILED (blocks next run)  │                           │
│  └───────────────────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Workflow via Boto3 (Infrastructure-as-Code)

```python
import boto3

glue = boto3.client('glue')

# Create workflow
glue.create_workflow(
    Name='ecommerce_hourly_aggregation',
    Description='Hourly e-commerce transaction aggregation pipeline',
    DefaultRunProperties={
        'source_database': 'ecommerce_raw',
        'source_table': 'order_events',
        'processing_date': '${CURRENT_DATE}',
        'processing_hour': '${CURRENT_HOUR}',
    }
)

# Schedule trigger (start of workflow)
glue.create_trigger(
    Name='trigger_hourly_start',
    WorkflowName='ecommerce_hourly_aggregation',
    Type='SCHEDULED',
    Schedule='cron(5 * * * ? *)',  # 5 minutes past every hour
    Actions=[{
        'JobName': 'ecommerce_cleanse_dedupe',
        'Arguments': {
            '--source_database': 'ecommerce_raw',
            '--source_table': 'order_events',
            '--target_path': 's3://data-lake-clean/events/',
            '--dlq_path': 's3://data-lake-dlq/cleansing/',
        }
    }],
    StartOnCreation=True
)

# Conditional trigger: Job 1 → Job 2
glue.create_trigger(
    Name='trigger_after_cleansing',
    WorkflowName='ecommerce_hourly_aggregation',
    Type='CONDITIONAL',
    Predicate={
        'Conditions': [{
            'LogicalOperator': 'EQUALS',
            'JobName': 'ecommerce_cleanse_dedupe',
            'State': 'SUCCEEDED'
        }]
    },
    Actions=[{
        'JobName': 'ecommerce_multi_grain_agg',
        'Arguments': {
            '--source_path': 's3://data-lake-clean/events/',
            '--staging_path': 's3://data-lake-agg/staging/',
        }
    }]
)

# Conditional trigger: Job 2 → Job 3
glue.create_trigger(
    Name='trigger_after_aggregation',
    WorkflowName='ecommerce_hourly_aggregation',
    Type='CONDITIONAL',
    Predicate={
        'Conditions': [{
            'LogicalOperator': 'EQUALS',
            'JobName': 'ecommerce_multi_grain_agg',
            'State': 'SUCCEEDED'
        }]
    },
    Actions=[{
        'JobName': 'ecommerce_iceberg_merge',
        'Arguments': {
            '--staging_path': 's3://data-lake-agg/staging/',
            '--iceberg_warehouse': 's3://data-lake-serving/iceberg/',
        }
    }]
)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling Strategy

### Auto-scaling Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTO-SCALING: 10 → 200 DPUs                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Normal Day (Monday):                                                       │
│  ┌─────┐                                                                    │
│  │10DPU│ ← Off-peak hours (midnight-6am): 10 DPUs sufficient               │
│  └─────┘                                                                    │
│       ┌──────────┐                                                          │
│       │  40 DPU  │ ← Daytime (6am-10pm): scales to 40 DPUs                 │
│       └──────────┘                                                          │
│                                                                             │
│  Black Friday / Prime Day:                                                  │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                    200 DPU (MAX)                                │ ← Peak │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  Scaling signals:                                                           │
│  • Input file count per partition > 10,000 → scale up                       │
│  • Executor memory utilization > 70% → scale up                            │
│  • Task completion rate declining → scale up                                │
│  • Executor idle time > 30% → scale down                                   │
│                                                                             │
│  Cost implications:                                                         │
│  • 1 DPU = $0.44/hour (standard), $0.29/hour (flex)                        │
│  • 10 DPU × 24hr = $105.60/day (off-peak baseline)                         │
│  • 200 DPU × 4hr = $352/day (Black Friday peak burst)                      │
│  • Average daily: $600-800 in compute                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Job Parameters for Scaling

```python
# Job definition with auto-scaling
job_config = {
    "Name": "ecommerce_multi_grain_agg",
    "Role": "arn:aws:iam::123456789:role/GlueServiceRole",
    "Command": {
        "Name": "glueetl",
        "ScriptLocation": "s3://glue-scripts/ecommerce/multi_grain_agg.py",
        "PythonVersion": "3"
    },
    "GlueVersion": "4.0",
    "WorkerType": "G.2X",
    "NumberOfWorkers": 200,               # MAX workers (auto-scaling starts here)
    "DefaultArguments": {
        "--enable-auto-scaling": "true",   # Key flag
        "--enable-continuous-cloudwatch-log": "true",
        "--enable-metrics": "true",
        "--enable-spark-ui": "true",
        "--spark-event-logs-path": "s3://glue-spark-logs/ecommerce/",
        "--conf": "spark.sql.adaptive.enabled=true",
        "--TempDir": "s3://glue-temp/ecommerce/",
        "--enable-glue-datacatalog": "true",
        "--additional-python-modules": "pyiceberg==0.5.0",
    },
    "ExecutionProperty": {"MaxConcurrentRuns": 2},
    "Timeout": 120,  # minutes
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

### Monthly Cost Breakdown at Scale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              MONTHLY COST BREAKDOWN (Steady State)                            │
├────────────────────────────────────┬────────────────────────────────────────┤
│ Component                          │ Monthly Cost (USD)                     │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Job 1 (Cleansing)            │                                        │
│   40 G.1X DPUs × 0.8hr × 24/day  │ $10,137                                │
│   × 30 days × $0.44/DPU-hr       │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Job 2 (Aggregation)          │                                        │
│   80 G.2X DPUs × 1.5hr × 24/day  │ $38,016                                │
│   × 30 days × $0.44/DPU-hr       │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Job 3 (Iceberg Merge)        │                                        │
│   40 G.2X DPUs × 0.5hr × 24/day  │ $6,336                                 │
│   × 30 days × $0.44/DPU-hr       │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Crawlers                      │ $800                                  │
│   (15-min intervals, partition    │                                        │
│    detection only)                 │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Data Catalog                  │ $1,200                                │
│   (45 tables, 10M+ partitions)    │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ S3 Storage (raw + clean + serving)│ $18,000                                │
│   ~600TB total (compressed)       │                                        │
│   + request costs ($0.005/1K PUT) │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ S3 Data Transfer                   │ $2,500                                │
│   (cross-region replication)       │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│ CloudWatch Logs & Metrics          │ $1,500                                │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Backfill/Reprocessing Buffer       │ $5,000                                │
│   (estimated ad-hoc runs)          │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│ TOTAL MONTHLY                      │ ~$83,500                              │
│                                    │                                        │
│ PEAK MONTH (Black Friday/Dec)      │ ~$120,000                             │
│ (2x volume, max DPU utilization)  │                                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│ COMPARISON: Equivalent on EMR      │ ~$150,000-200,000/month               │
│ (always-on cluster + ops team)    │                                        │
│                                    │                                        │
│ COMPARISON: Redshift direct        │ ~$400,000-500,000/month               │
│ (64× ra3.16xl for ingestion)      │                                        │
│                                    │                                        │
└────────────────────────────────────┴────────────────────────────────────────┘
```

### Cost Optimization Levers

```
┌────────────────────────────────────┬────────────────────────────────────────┐
│ Optimization                       │ Savings                                │
├────────────────────────────────────┼────────────────────────────────────────┤
│ Glue Flex execution (non-urgent)   │ 34% on DPU costs (~$18K/month)        │
│ S3 Intelligent Tiering             │ 20-30% on storage (~$4K/month)        │
│ Partition pruning (pushdown preds) │ 60-80% reduction in data scanned      │
│ Iceberg compaction (fewer files)   │ 30% faster reads, less S3 requests    │
│ Spot instances (Glue Flex)         │ Built into Flex pricing               │
│ Right-sizing DPUs per job          │ 15-20% on over-provisioned jobs       │
└────────────────────────────────────┴────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Using This Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPANIES USING THIS PATTERN                               │
├─────────────────┬───────────────────────────────────────────────────────────┤
│ Company         │ Scale & Details                                           │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Amazon          │ Internal retail analytics. Processes order, inventory,    │
│                 │ and fulfillment events across all marketplaces. Uses      │
│                 │ Glue for ETL between S3 data lake and Redshift. Reported  │
│                 │ 100K+ Glue jobs running daily across the organization.    │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Shopify         │ Merchant analytics platform. Aggregates transaction data  │
│                 │ from 2M+ merchants into analytics dashboards. Uses Glue   │
│                 │ for daily/hourly rollups powering Shop app insights and   │
│                 │ Shopify Capital lending decisions.                        │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Walmart         │ Marketplace seller analytics and inventory optimization.  │
│                 │ Processes POS + e-commerce data together. Glue pipelines  │
│                 │ feed real-time pricing and demand forecasting models.     │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ eBay            │ Seller performance metrics, GMV reporting, search         │
│                 │ relevance signal generation. Migrated from on-prem Hadoop │
│                 │ to Glue + S3 + Iceberg for cost and operational benefits. │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Instacart       │ Order fulfillment analytics, shopper performance metrics, │
│                 │ delivery time prediction features. Heavy use of Glue for  │
│                 │ ML feature engineering pipelines.                         │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ DoorDash        │ Real-time and batch order analytics. Uses Glue for        │
│                 │ merchant payout calculations and delivery optimization    │
│                 │ model training data preparation.                          │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Zalando         │ European fashion marketplace. Uses Glue for              │
│                 │ cross-border transaction aggregation, returns analytics,  │
│                 │ and personalization data pipelines across 25 markets.     │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Takeaways

1. **Glue excels at batch aggregation at scale** - serverless, auto-scaling, pay-per-use
2. **Job Bookmarks are critical** - enable incremental processing without custom state
3. **DynamicFrame handles marketplace chaos** - schema inconsistencies are the norm
4. **Iceberg MERGE provides idempotency** - safe for reprocessing and late data
5. **Multi-job workflow separation** - cleanse → aggregate → merge keeps logic clean
6. **G.2X workers for aggregation** - memory-intensive shuffles need 32GB/executor
7. **Cost is 40-60% less than alternatives** - vs. always-on EMR or Redshift direct
8. **Pushdown predicates are mandatory** - without them, you scan 50TB instead of 500GB
9. **Data quality gates prevent bad data propagation** - fail fast, route to DLQ
10. **Backfill is a first-class concern** - design for re-computation from day one
