# Fraud Detection Feature Engineering Pipeline at Capital One/Stripe Scale

## 1. The Problem: 100M+ Transactions/Day Needing 500+ Features for Real-time Fraud Scoring

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

A payment processor or issuing bank runs ML models that score every transaction in
real-time (<50ms). The models need two categories of features:

- **Real-time features** — computed at inference time (transaction amount, time of day,
  merchant category). These are cheap: just parse the incoming request.
- **Batch/historical features** — computed from days/weeks of history (how many times has
  this card transacted in the last 24h? What's the standard deviation of this cardholder's
  spend? Is this merchant connected to known fraud rings?). These are expensive.

The batch features are what separate a 70% accurate model from a 99.5% accurate model.
The feature engineering pipeline computes these offline and stores them where the real-time
scoring service can look them up in <5ms.

### Scale Parameters

```
┌─────────────────────────────────────────────────────────┐
│  Parameter                 │  Value                      │
├─────────────────────────────────────────────────────────┤
│  Daily transactions        │  100M–300M                  │
│  Unique cards active/day   │  50M                        │
│  Unique merchants          │  2M                         │
│  Features per entity       │  500+ (card) + 200 (merch) │
│  Feature freshness SLA     │  < 4 hours                  │
│  Feature store reads/sec   │  500K (at peak)             │
│  Historical lookback       │  90 days                    │
│  Total records in window   │  ~9 billion                 │
└─────────────────────────────────────────────────────────┘
```

### Why Batch Features Matter

```
┌───────────────────────────────────────────────────────────────────────┐
│                     ML SCORING AT INFERENCE TIME                       │
│                                                                       │
│   Transaction Request ──┐                                             │
│                         ▼                                             │
│   ┌─────────────────────────────┐    ┌──────────────────────────┐    │
│   │  Real-time Features (10)    │    │  Batch Features (500+)   │    │
│   │  - amount                   │    │  - velocity_1h/6h/24h/7d │    │
│   │  - merchant_category        │    │  - spending_zscore        │    │
│   │  - time_of_day              │    │  - graph_fraud_proximity  │    │
│   │  - card_present_flag        │    │  - device_reputation      │    │
│   │  - geo_distance             │    │  - merchant_risk_score    │    │
│   └──────────────┬──────────────┘    └────────────┬─────────────┘    │
│                  │                                 │                   │
│                  └──────────┬──────────────────────┘                   │
│                             ▼                                          │
│                  ┌─────────────────────┐                              │
│                  │  XGBoost / Neural   │──▶ Fraud Score (0.0 - 1.0)   │
│                  │  Network Model      │                              │
│                  └─────────────────────┘                              │
└───────────────────────────────────────────────────────────────────────┘
```

The batch features are pre-computed by the **Glue pipeline** every 4 hours and written to
DynamoDB. At inference time, the scoring service does a single DynamoDB GetItem by card_id
to retrieve all 500+ features in <5ms.

---

## 2. Why Traditional Approaches Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Computing Features in Real-time Database (PostgreSQL/Aurora)

```
Problem: SELECT COUNT(*) FROM transactions
         WHERE card_id = ? AND txn_time > NOW() - INTERVAL '24 hours'

- At 500K reads/sec, this query runs for EVERY transaction
- Each query scans millions of rows (90-day window)
- Database CPU saturates at ~5K concurrent feature queries
- Cost: Would need 100+ Aurora replicas = $500K+/month
- Latency: 200-500ms per feature set (too slow for real-time scoring)
```

### Single Persistent EMR Cluster

```
- 50-node cluster sitting idle 18-20 hours/day
- Cost: ~$80K/month for r5.4xlarge × 50
- Cluster management overhead (patching, scaling, failures)
- No built-in job orchestration or data catalog integration
- Underutilized GPU/memory during off-peak
```

### Lambda-Based Feature Computation

```
- 15-minute execution limit: cannot compute 90-day rolling features
- No shared state between invocations
- Cold start latency compounds across 500+ features
- Cannot efficiently do window functions across billions of rows
- Memory limit (10GB) insufficient for graph computation
```

### Application-Layer Feature Computation

```
- Each microservice computes its own features → inconsistency
- Training/serving skew: features computed differently offline vs online
- No versioning, no monitoring, no drift detection
- Debugging fraud model becomes impossible
```

---

## 3. Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    FRAUD DETECTION FEATURE ENGINEERING PIPELINE                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Transaction  │  │  Card Master │  │  Merchant    │  │ Device/IP    │        │
│  │ DB (Aurora)  │  │  (DynamoDB)  │  │  Master (S3) │  │ Logs (Kinesis│        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │ CDC/DMS          │                  │                  │                │
│         ▼                  ▼                  ▼                  ▼                │
│  ┌─────────────────────────────────────────────────────────────────────┐        │
│  │                     S3 LANDING ZONE                                  │        │
│  │   s3://fraud-features/landing/{source}/{date}/{hour}/               │        │
│  └─────────────────────────────────┬───────────────────────────────────┘        │
│                                    │                                             │
│                                    ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐        │
│  │  GLUE JOB 1: Raw Ingestion & Deduplication                          │        │
│  │  Workers: G.1X × 20 | Runtime: ~30 min | Trigger: Every 4 hours     │        │
│  │  - Deduplicate by (txn_id, timestamp)                               │        │
│  │  - Schema validation & type casting                                  │        │
│  │  - Partition: card_id_prefix / date                                  │        │
│  └─────────────────────────────────┬───────────────────────────────────┘        │
│                                    │                                             │
│                                    ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐        │
│  │  S3 CURATED ZONE (Iceberg tables)                                    │        │
│  │  s3://fraud-features/curated/transactions/                           │        │
│  └────┬───────────────┬───────────────┬───────────────┬────────────────┘        │
│       │               │               │               │                          │
│       ▼               ▼               ▼               ▼                          │
│  ┌─────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐                   │
│  │ GLUE    │   │ GLUE      │   │ GLUE      │   │ GLUE      │                   │
│  │ JOB 2   │   │ JOB 3     │   │ JOB 4     │   │ JOB 5     │                   │
│  │Velocity │   │ Graph     │   │Statistical│   │ Device/IP │                   │
│  │Features │   │ Features  │   │ Features  │   │ Features  │                   │
│  │G.2X×40  │   │ G.4X×20   │   │ G.2X×30  │   │ G.1X×10   │                   │
│  │~45 min  │   │ ~60 min   │   │ ~40 min   │   │ ~20 min   │                   │
│  └────┬────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘                   │
│       │               │               │               │                          │
│       └───────────────┴───────┬───────┴───────────────┘                          │
│                               ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐        │
│  │  GLUE JOB 6: Feature Assembly & Validation                           │        │
│  │  Workers: G.2X × 30 | Runtime: ~25 min                              │        │
│  │  - Join all feature sets on card_id                                  │        │
│  │  - Null imputation & outlier capping                                 │        │
│  │  - Feature distribution validation (Glue Data Quality)              │        │
│  │  - Write to dual stores                                              │        │
│  └──────────────────┬─────────────────────┬────────────────────────────┘        │
│                     │                     │                                       │
│                     ▼                     ▼                                       │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐                 │
│  │  S3 Feature Store        │  │  DynamoDB Online Store        │                 │
│  │  (Training/Batch)        │  │  (Real-time Serving)          │                 │
│  │  Parquet, partitioned    │  │  Key: card_id                 │                 │
│  │  by date                 │  │  500+ attrs per item          │                 │
│  └───────────┬──────────────┘  └──────────────┬───────────────┘                 │
│              │                                 │                                  │
│              ▼                                 ▼                                  │
│  ┌───────────────────────┐      ┌──────────────────────────────┐                │
│  │  SageMaker Training   │      │  Real-time Scoring Lambda    │                │
│  │  (Daily retraining)   │      │  DynamoDB GetItem < 5ms      │                │
│  └───────────────────────┘      └──────────────────────────────┘                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Glue Concepts Used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Glue Streaming ETL for Near-Real-Time Features

For critical velocity features (transactions in last 1 hour), a Glue Streaming job
processes from Kinesis with a 5-minute micro-batch window, updating DynamoDB counters
incrementally rather than recomputing from scratch.

### Custom Transforms (UDFs)

Complex feature logic that cannot be expressed as SQL window functions:
- Benford's Law digit distribution analysis
- Haversine distance from cardholder home
- Time-series anomaly scoring (Isolation Forest embedded in UDF)

### Worker Auto-Scaling with G.4X for Graph Computation

Graph feature computation (Job 3) requires massive memory for building adjacency matrices
across merchant-customer networks. G.4X workers provide 256GB RAM and 64 vCPUs each.
Auto-scaling adjusts from 10→40 workers based on input partition count.

### Job Bookmarks with Partitioned Incremental Reads

Each run only processes new/changed partitions since the last successful run. Combined
with Iceberg's time-travel, this ensures exactly-once feature computation without
reprocessing the full 90-day window.

### Glue Data Quality for Feature Drift Detection

Rules validate that feature distributions haven't shifted beyond acceptable thresholds:
- `ColumnValues "velocity_24h" between 0 and 5000`
- `StandardDeviation "amount_zscore" between 0.8 and 1.2`
- `Completeness "card_id" = 1.0`

### DynamoDB Connection for Online Feature Store

Glue writes directly to DynamoDB using a custom DynamicFrame sink with batch writes
(25 items per BatchWriteItem), adaptive capacity, and exponential backoff.

---

## 5. Feature Engineering Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job 1: Raw Ingestion & Deduplication

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

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'source_path', 'output_path', 'run_date'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configure for large-scale shuffle
spark.conf.set("spark.sql.shuffle.partitions", "2000")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

# Read from landing zone using job bookmarks for incremental processing
raw_dyf = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    format="json",
    connection_options={
        "paths": [f"{args['source_path']}/transactions/"],
        "recurse": True,
        "jobBookmarkKeys": ["txn_id", "txn_timestamp"],
        "jobBookmarkKeysSortOrder": "asc"
    },
    transformation_ctx="raw_transactions"
)

raw_df = raw_dyf.toDF()

# Schema enforcement
transactions = raw_df.select(
    F.col("txn_id").cast("string"),
    F.col("card_id").cast("string"),
    F.col("merchant_id").cast("string"),
    F.col("amount").cast("double"),
    F.col("currency").cast("string"),
    F.col("txn_timestamp").cast("timestamp"),
    F.col("merchant_category_code").cast("integer"),
    F.col("card_present").cast("boolean"),
    F.col("device_id").cast("string"),
    F.col("ip_address").cast("string"),
    F.col("geo_lat").cast("double"),
    F.col("geo_lon").cast("double"),
    F.col("response_code").cast("string"),
    F.col("is_fraud").cast("integer")  # label, populated after investigation
)

# Deduplication: keep latest version of each transaction
dedup_window = Window.partitionBy("txn_id").orderBy(F.col("txn_timestamp").desc())
deduped = transactions.withColumn("row_num", F.row_number().over(dedup_window)) \
    .filter(F.col("row_num") == 1) \
    .drop("row_num")

# Add processing metadata
deduped = deduped.withColumn("processing_time", F.current_timestamp()) \
    .withColumn("card_id_prefix", F.substring("card_id", 1, 4)) \
    .withColumn("txn_date", F.to_date("txn_timestamp"))

# Validate: reject records with null card_id or amount
valid = deduped.filter(
    F.col("card_id").isNotNull() & F.col("amount").isNotNull()
)
rejected = deduped.filter(
    F.col("card_id").isNull() | F.col("amount").isNull()
)

# Write rejected to dead-letter path
if rejected.count() > 0:
    rejected.write.mode("append").parquet(
        f"{args['output_path']}/dead_letter/txn_date={args['run_date']}/"
    )

# Write valid to Iceberg curated table
valid.writeTo("glue_catalog.fraud_features.transactions_curated") \
    .partitionedBy("txn_date", "card_id_prefix") \
    .append()

job.commit()
```

### Job 2: Velocity Feature Computation

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import DoubleType, IntegerType
from datetime import datetime, timedelta

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'output_path', 'run_date', 'lookback_days'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.shuffle.partitions", "4000")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")

run_date = datetime.strptime(args['run_date'], '%Y-%m-%d')
lookback_start = (run_date - timedelta(days=int(args['lookback_days']))).strftime('%Y-%m-%d')

# Read 90 days of curated transactions
transactions = spark.read.table("glue_catalog.fraud_features.transactions_curated") \
    .filter(
        (F.col("txn_date") >= lookback_start) &
        (F.col("txn_date") <= args['run_date'])
    )

# Convert timestamp to seconds for range-based windows
transactions = transactions.withColumn(
    "txn_epoch", F.unix_timestamp("txn_timestamp")
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VELOCITY FEATURES: Transaction counts & amounts in time windows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Define range-based windows for each time period
def time_window(seconds):
    return Window.partitionBy("card_id") \
        .orderBy("txn_epoch") \
        .rangeBetween(-seconds, 0)

window_1h = time_window(3600)
window_6h = time_window(21600)
window_24h = time_window(86400)
window_7d = time_window(604800)
window_30d = time_window(2592000)

velocity_features = transactions \
    .withColumn("txn_count_1h", F.count("txn_id").over(window_1h)) \
    .withColumn("txn_count_6h", F.count("txn_id").over(window_6h)) \
    .withColumn("txn_count_24h", F.count("txn_id").over(window_24h)) \
    .withColumn("txn_count_7d", F.count("txn_id").over(window_7d)) \
    .withColumn("txn_count_30d", F.count("txn_id").over(window_30d)) \
    .withColumn("txn_amount_sum_1h", F.sum("amount").over(window_1h)) \
    .withColumn("txn_amount_sum_6h", F.sum("amount").over(window_6h)) \
    .withColumn("txn_amount_sum_24h", F.sum("amount").over(window_24h)) \
    .withColumn("txn_amount_sum_7d", F.sum("amount").over(window_7d)) \
    .withColumn("txn_amount_max_24h", F.max("amount").over(window_24h)) \
    .withColumn("txn_amount_avg_7d", F.avg("amount").over(window_7d)) \
    .withColumn("txn_amount_stddev_30d", F.stddev("amount").over(window_30d))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DISTINCT MERCHANT VELOCITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Approximate distinct merchants (exact distinct not supported in range windows)
# Use collect_set + size as workaround
merchant_window_24h = Window.partitionBy("card_id") \
    .orderBy("txn_epoch") \
    .rangeBetween(-86400, 0)

velocity_features = velocity_features \
    .withColumn(
        "distinct_merchants_24h",
        F.size(F.collect_set("merchant_id").over(merchant_window_24h))
    ) \
    .withColumn(
        "distinct_mcc_24h",
        F.size(F.collect_set("merchant_category_code").over(merchant_window_24h))
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIME-BETWEEN-TRANSACTIONS FEATURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

prev_txn_window = Window.partitionBy("card_id").orderBy("txn_epoch")

velocity_features = velocity_features \
    .withColumn(
        "seconds_since_last_txn",
        F.col("txn_epoch") - F.lag("txn_epoch", 1).over(prev_txn_window)
    ) \
    .withColumn(
        "seconds_since_last_txn_same_merchant",
        F.col("txn_epoch") - F.lag("txn_epoch", 1).over(
            Window.partitionBy("card_id", "merchant_id").orderBy("txn_epoch")
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KEEP ONLY LATEST ROW PER CARD (current feature values)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

latest_window = Window.partitionBy("card_id").orderBy(F.col("txn_epoch").desc())
latest_velocity = velocity_features \
    .withColumn("rn", F.row_number().over(latest_window)) \
    .filter(F.col("rn") == 1) \
    .drop("rn")

# Select only feature columns
velocity_output = latest_velocity.select(
    "card_id",
    "txn_count_1h", "txn_count_6h", "txn_count_24h", "txn_count_7d", "txn_count_30d",
    "txn_amount_sum_1h", "txn_amount_sum_6h", "txn_amount_sum_24h", "txn_amount_sum_7d",
    "txn_amount_max_24h", "txn_amount_avg_7d", "txn_amount_stddev_30d",
    "distinct_merchants_24h", "distinct_mcc_24h",
    "seconds_since_last_txn", "seconds_since_last_txn_same_merchant"
)

velocity_output.write.mode("overwrite").parquet(
    f"{args['output_path']}/features/velocity/run_date={args['run_date']}/"
)

job.commit()
```

### Job 3: Graph Feature Computation

```python
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from graphframes import GraphFrame

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'output_path', 'run_date'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Graph computation needs large memory - using G.4X workers
spark.conf.set("spark.sql.shuffle.partitions", "2000")

transactions = spark.read.table("glue_catalog.fraud_features.transactions_curated") \
    .filter(F.col("txn_date") >= F.date_sub(F.lit(args['run_date']), 30))

# Known fraud labels (from investigations)
known_fraud = spark.read.table("glue_catalog.fraud_features.confirmed_fraud") \
    .select("card_id", "merchant_id", "fraud_confirmed_date")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BUILD BIPARTITE GRAPH: Cards ↔ Merchants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Vertices: all cards and merchants
card_vertices = transactions.select(
    F.col("card_id").alias("id"),
    F.lit("card").alias("type")
).distinct()

merchant_vertices = transactions.select(
    F.col("merchant_id").alias("id"),
    F.lit("merchant").alias("type")
).distinct()

vertices = card_vertices.union(merchant_vertices)

# Edges: card → merchant with weight = transaction count
edges = transactions.groupBy(
    F.col("card_id").alias("src"),
    F.col("merchant_id").alias("dst")
).agg(
    F.count("*").alias("txn_count"),
    F.sum("amount").alias("total_amount"),
    F.max(F.when(F.col("is_fraud") == 1, 1).otherwise(0)).alias("has_fraud")
)

graph = GraphFrame(vertices, edges)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEATURE: Fraud proximity (hops to nearest known fraud)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Label propagation to find connected components with fraud
fraud_cards = known_fraud.select("card_id").distinct() \
    .withColumnRenamed("card_id", "id")

# Connected components
components = graph.connectedComponents()

# Count fraud nodes per component
fraud_components = components.join(fraud_cards, "id", "inner") \
    .groupBy("component") \
    .agg(F.count("*").alias("fraud_nodes_in_component"))

card_graph_features = components.filter(F.col("type") == "card") \
    .join(fraud_components, "component", "left") \
    .select(
        F.col("id").alias("card_id"),
        F.col("component").alias("graph_component_id"),
        F.coalesce(F.col("fraud_nodes_in_component"), F.lit(0)).alias("fraud_nodes_in_network")
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEATURE: PageRank (high-risk nodes have high centrality in fraud networks)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pagerank = graph.pageRank(resetProbability=0.15, maxIter=10)
card_pagerank = pagerank.vertices.filter(F.col("type") == "card") \
    .select(
        F.col("id").alias("card_id"),
        F.col("pagerank").alias("graph_pagerank")
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEATURE: Shared merchant overlap with fraud cards
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

card_merchants = transactions.groupBy("card_id") \
    .agg(F.collect_set("merchant_id").alias("merchant_set"))

fraud_merchant_sets = card_merchants.join(
    known_fraud.select("card_id").distinct(), "card_id", "inner"
).select("merchant_set")

# Explode fraud merchants into a single set
all_fraud_merchants = fraud_merchant_sets \
    .select(F.explode("merchant_set").alias("merchant_id")) \
    .distinct()

# For each card, count how many of their merchants are in fraud merchant set
card_fraud_merchant_overlap = transactions \
    .join(all_fraud_merchants, "merchant_id", "inner") \
    .groupBy("card_id") \
    .agg(
        F.countDistinct("merchant_id").alias("shared_merchants_with_fraud"),
        F.sum("amount").alias("amount_at_fraud_merchants")
    )

# Assemble graph features
graph_features = card_graph_features \
    .join(card_pagerank, "card_id", "left") \
    .join(card_fraud_merchant_overlap, "card_id", "left") \
    .fillna(0, subset=[
        "fraud_nodes_in_network", "graph_pagerank",
        "shared_merchants_with_fraud", "amount_at_fraud_merchants"
    ])

graph_features.write.mode("overwrite").parquet(
    f"{args['output_path']}/features/graph/run_date={args['run_date']}/"
)

job.commit()
```

### Job 4: Statistical Features

```python
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import DoubleType
import numpy as np

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'output_path', 'run_date'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

transactions = spark.read.table("glue_catalog.fraud_features.transactions_curated") \
    .filter(F.col("txn_date") >= F.date_sub(F.lit(args['run_date']), 90))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PER-CARD SPENDING STATISTICS (baseline behavior)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

card_stats = transactions.groupBy("card_id").agg(
    F.mean("amount").alias("card_avg_amount"),
    F.stddev("amount").alias("card_stddev_amount"),
    F.expr("percentile_approx(amount, 0.5)").alias("card_median_amount"),
    F.expr("percentile_approx(amount, 0.95)").alias("card_p95_amount"),
    F.expr("percentile_approx(amount, 0.99)").alias("card_p99_amount"),
    F.count("*").alias("card_total_txn_count"),
    F.countDistinct("merchant_id").alias("card_distinct_merchants"),
    F.countDistinct("merchant_category_code").alias("card_distinct_mcc"),
    F.min("amount").alias("card_min_amount"),
    F.max("amount").alias("card_max_amount"),
    F.skewness("amount").alias("card_amount_skewness"),
    F.kurtosis("amount").alias("card_amount_kurtosis")
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Z-SCORE OF LATEST TRANSACTION vs CARDHOLDER BASELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

latest_txn_window = Window.partitionBy("card_id").orderBy(F.col("txn_timestamp").desc())
latest_txns = transactions \
    .withColumn("rn", F.row_number().over(latest_txn_window)) \
    .filter(F.col("rn") == 1) \
    .select("card_id", "amount", "merchant_category_code", "txn_timestamp")

zscore_features = latest_txns.join(card_stats, "card_id") \
    .withColumn(
        "amount_zscore",
        F.when(F.col("card_stddev_amount") > 0,
               (F.col("amount") - F.col("card_avg_amount")) / F.col("card_stddev_amount")
        ).otherwise(0.0)
    ) \
    .withColumn(
        "amount_percentile_rank",
        F.when(F.col("card_max_amount") > F.col("card_min_amount"),
               (F.col("amount") - F.col("card_min_amount")) /
               (F.col("card_max_amount") - F.col("card_min_amount"))
        ).otherwise(0.5)
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIME-OF-DAY DEVIATION (is this transaction at an unusual hour?)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

hourly_patterns = transactions \
    .withColumn("hour", F.hour("txn_timestamp")) \
    .groupBy("card_id", "hour") \
    .agg(F.count("*").alias("txn_at_hour"))

card_total = hourly_patterns.groupBy("card_id") \
    .agg(F.sum("txn_at_hour").alias("total"))

hour_probs = hourly_patterns.join(card_total, "card_id") \
    .withColumn("hour_prob", F.col("txn_at_hour") / F.col("total")) \
    .select("card_id", "hour", "hour_prob")

# Join latest transaction hour to get probability
latest_with_hour = latest_txns.withColumn("hour", F.hour("txn_timestamp"))
time_deviation = latest_with_hour.join(hour_probs, ["card_id", "hour"], "left") \
    .withColumn("hour_unusualness", 1.0 - F.coalesce(F.col("hour_prob"), F.lit(0.0))) \
    .select("card_id", "hour_unusualness")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCC DEVIATION (is this merchant category unusual for this card?)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

mcc_patterns = transactions \
    .groupBy("card_id", "merchant_category_code") \
    .agg(F.count("*").alias("txn_at_mcc"))

mcc_total = mcc_patterns.groupBy("card_id") \
    .agg(F.sum("txn_at_mcc").alias("total"))

mcc_probs = mcc_patterns.join(mcc_total, "card_id") \
    .withColumn("mcc_prob", F.col("txn_at_mcc") / F.col("total")) \
    .select("card_id", "merchant_category_code", "mcc_prob")

mcc_deviation = latest_txns.join(
    mcc_probs, ["card_id", "merchant_category_code"], "left"
).withColumn(
    "mcc_unusualness", 1.0 - F.coalesce(F.col("mcc_prob"), F.lit(0.0))
).select("card_id", "mcc_unusualness")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ASSEMBLE STATISTICAL FEATURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

stat_features = zscore_features.select(
    "card_id", "card_avg_amount", "card_stddev_amount",
    "card_median_amount", "card_p95_amount", "card_p99_amount",
    "card_total_txn_count", "card_distinct_merchants", "card_distinct_mcc",
    "card_amount_skewness", "card_amount_kurtosis",
    "amount_zscore", "amount_percentile_rank"
).join(time_deviation, "card_id", "left") \
 .join(mcc_deviation, "card_id", "left")

stat_features.write.mode("overwrite").parquet(
    f"{args['output_path']}/features/statistical/run_date={args['run_date']}/"
)

job.commit()
```

### Job 5: Device/IP Reputation Features

```python
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'output_path', 'run_date'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

transactions = spark.read.table("glue_catalog.fraud_features.transactions_curated") \
    .filter(F.col("txn_date") >= F.date_sub(F.lit(args['run_date']), 30))

known_fraud = spark.read.table("glue_catalog.fraud_features.confirmed_fraud")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DEVICE REPUTATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

device_stats = transactions.filter(F.col("device_id").isNotNull()) \
    .groupBy("device_id").agg(
        F.countDistinct("card_id").alias("cards_per_device"),
        F.count("*").alias("txns_per_device"),
        F.sum(F.col("is_fraud").cast("int")).alias("fraud_txns_on_device"),
        F.countDistinct("merchant_id").alias("merchants_per_device")
    ).withColumn(
        "device_fraud_rate",
        F.col("fraud_txns_on_device") / F.col("txns_per_device")
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IP REPUTATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ip_stats = transactions.filter(F.col("ip_address").isNotNull()) \
    .withColumn("ip_prefix", F.expr("substring(ip_address, 1, instr(ip_address, '.', 1, 3) - 1)")) \
    .groupBy("ip_prefix").agg(
        F.countDistinct("card_id").alias("cards_per_ip_block"),
        F.sum(F.col("is_fraud").cast("int")).alias("fraud_from_ip_block"),
        F.count("*").alias("txns_from_ip_block")
    ).withColumn(
        "ip_block_fraud_rate",
        F.col("fraud_from_ip_block") / F.col("txns_from_ip_block")
    )

# Join device/IP features back to cards (using latest transaction's device/IP)
from pyspark.sql.window import Window
latest_w = Window.partitionBy("card_id").orderBy(F.col("txn_timestamp").desc())

latest_card_context = transactions \
    .withColumn("rn", F.row_number().over(latest_w)) \
    .filter(F.col("rn") == 1) \
    .select("card_id", "device_id", "ip_address") \
    .withColumn("ip_prefix", F.expr("substring(ip_address, 1, instr(ip_address, '.', 1, 3) - 1)"))

device_ip_features = latest_card_context \
    .join(device_stats, "device_id", "left") \
    .join(ip_stats, "ip_prefix", "left") \
    .select(
        "card_id",
        F.coalesce("cards_per_device", F.lit(1)).alias("cards_per_device"),
        F.coalesce("device_fraud_rate", F.lit(0.0)).alias("device_fraud_rate"),
        F.coalesce("cards_per_ip_block", F.lit(1)).alias("cards_per_ip_block"),
        F.coalesce("ip_block_fraud_rate", F.lit(0.0)).alias("ip_block_fraud_rate")
    )

device_ip_features.write.mode("overwrite").parquet(
    f"{args['output_path']}/features/device_ip/run_date={args['run_date']}/"
)

job.commit()
```

### Job 6: Feature Assembly & DynamoDB Write

```python
import sys
import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'feature_path', 'run_date', 'dynamodb_table', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']
base = args['feature_path']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOAD ALL FEATURE SETS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

velocity = spark.read.parquet(f"{base}/features/velocity/run_date={run_date}/")
graph = spark.read.parquet(f"{base}/features/graph/run_date={run_date}/")
statistical = spark.read.parquet(f"{base}/features/statistical/run_date={run_date}/")
device_ip = spark.read.parquet(f"{base}/features/device_ip/run_date={run_date}/")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JOIN ON card_id
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

assembled = velocity \
    .join(graph, "card_id", "left") \
    .join(statistical, "card_id", "left") \
    .join(device_ip, "card_id", "left")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NULL IMPUTATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

numeric_cols = [c for c in assembled.columns if c != "card_id"]
assembled = assembled.fillna(0.0, subset=numeric_cols)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OUTLIER CAPPING (cap at 99.9th percentile)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cap_cols = ["txn_count_24h", "txn_amount_sum_24h", "amount_zscore", "graph_pagerank"]
for col_name in cap_cols:
    p999 = assembled.approxQuantile(col_name, [0.999], 0.01)[0]
    assembled = assembled.withColumn(
        col_name, F.when(F.col(col_name) > p999, p999).otherwise(F.col(col_name))
    )

# Add metadata
assembled = assembled.withColumn("feature_version", F.lit("v2.3")) \
    .withColumn("computed_at", F.lit(run_date))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WRITE TO S3 (offline/training store)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

assembled.write.mode("overwrite").parquet(
    f"{args['output_path']}/feature_store/assembled/run_date={run_date}/"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WRITE TO DYNAMODB (online serving store)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Convert to DynamicFrame for Glue DynamoDB sink
dyf = DynamicFrame.fromDF(assembled, glueContext, "assembled_features")

glueContext.write_dynamic_frame_from_options(
    frame=dyf,
    connection_type="dynamodb",
    connection_options={
        "dynamodb.output.tableName": args['dynamodb_table'],
        "dynamodb.throughput.write.percent": "0.8"
    }
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA QUALITY VALIDATION (post-write)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from awsglue.data_quality import EvaluateDataQuality

quality_rules = """
    Rules = [
        RowCount between 45000000 and 55000000,
        Completeness "card_id" = 1.0,
        Completeness "txn_count_24h" >= 0.99,
        ColumnValues "amount_zscore" between -10 and 50,
        StandardDeviation "txn_count_24h" between 1 and 500
    ]
"""

quality_result = EvaluateDataQuality.apply(
    frame=dyf,
    ruleset=quality_rules,
    publishing_options={
        "dataQualityEvaluationContext": "fraud_features_assembly",
        "enableDataQualityCloudWatchMetrics": "true"
    }
)

# Alert on quality failures
quality_df = quality_result.toDF()
failures = quality_df.filter(F.col("Outcome") == "Failed")
if failures.count() > 0:
    sns = boto3.client('sns')
    sns.publish(
        TopicArn='arn:aws:sns:us-east-1:123456789:fraud-feature-alerts',
        Subject='Feature Quality Alert',
        Message=f"Feature quality rules failed for run_date={run_date}"
    )

job.commit()
```

---

## 6. Production Handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Feature Freshness SLA Management

```
┌──────────────────────────────────────────────────────────────────┐
│  FRESHNESS SLA: All features updated within 4 hours of data      │
│                                                                   │
│  Schedule (Glue Triggers):                                        │
│    00:00 UTC - Run for 20:00-00:00 data                          │
│    04:00 UTC - Run for 00:00-04:00 data                          │
│    08:00 UTC - Run for 04:00-08:00 data                          │
│    12:00 UTC - Run for 08:00-12:00 data                          │
│    16:00 UTC - Run for 12:00-16:00 data                          │
│    20:00 UTC - Run for 16:00-20:00 data                          │
│                                                                   │
│  Each run: ~2.5 hours end-to-end                                 │
│  Buffer: 1.5 hours for retries before SLA breach                 │
│                                                                   │
│  Monitoring:                                                      │
│    - CloudWatch metric: feature_staleness_minutes                 │
│    - Alarm if > 240 minutes → PagerDuty escalation               │
│    - DynamoDB item metadata includes "computed_at" timestamp      │
└──────────────────────────────────────────────────────────────────┘
```

### Backfill Strategy for New Features

When a new feature is added (e.g., `txn_count_3h`):

1. Deploy new code to a **shadow job** that writes to a staging table
2. Backfill 90 days by running with historical date parameters
3. Validate distributions match expectations
4. Swap the shadow table into production via DynamoDB table pointer update
5. Update the scoring Lambda's feature schema config

### Feature Versioning

```
Feature Store Layout:
s3://fraud-features/feature_store/
├── assembled/
│   ├── run_date=2024-01-15/   (latest)
│   ├── run_date=2024-01-14/
│   └── ...
├── metadata/
│   ├── schema_v2.3.json       (current)
│   ├── schema_v2.2.json       (previous)
│   └── feature_importance.parquet
└── training_snapshots/
    ├── model_v45_training_set/  (point-in-time for model reproducibility)
    └── model_v44_training_set/
```

### A/B Testing New Features

- Shadow scoring: run new model with new features alongside production model
- Log both scores, compare fraud catch rate on confirmed fraud labels
- Feature importance validation: new feature should rank in top-50 by SHAP value
- Roll out via feature flag in scoring Lambda

### Monitoring Feature Distributions

```python
# CloudWatch custom metrics published by Job 6
metrics = {
    "velocity_24h_mean": velocity["txn_count_24h"].mean(),
    "velocity_24h_p99": velocity["txn_count_24h"].approxQuantile(0.99),
    "zscore_stddev": statistical["amount_zscore"].stddev(),
    "null_rate_graph": graph.filter(col("graph_pagerank").isNull()).count() / total,
    "feature_count": len(assembled.columns) - 1,  # minus card_id
    "total_cards_covered": assembled.count()
}
# Alarm if any metric deviates >3 stddev from 7-day rolling average
```

---

## 7. ML Integration: How Glue Output Feeds SageMaker

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  TRAINING PIPELINE (Daily)                                           │
│                                                                      │
│  S3 Feature Store ──▶ SageMaker Processing Job ──▶ Training Job     │
│  (assembled/)         (train/val/test split)       (XGBoost)        │
│                                                                      │
│  Point-in-time correctness:                                          │
│  - For each labeled fraud event at time T, use features              │
│    that were available BEFORE T (not future-leaked features)         │
│  - Glue writes snapshots with "computed_at" timestamps               │
│  - SageMaker Processing joins labels with correct feature snapshot   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INFERENCE PIPELINE (Real-time, <50ms)                               │
│                                                                      │
│  Transaction ──▶ API Gateway ──▶ Lambda ──┬──▶ DynamoDB GetItem     │
│  Request                                  │    (batch features)      │
│                                           │                          │
│                                           ├──▶ Compute real-time     │
│                                           │    features (in-Lambda)  │
│                                           │                          │
│                                           └──▶ SageMaker Endpoint   │
│                                                (model inference)     │
│                                                                      │
│  Latency budget:                                                     │
│    DynamoDB lookup:     3-5ms                                        │
│    Real-time features:  1-2ms                                        │
│    Model inference:    10-20ms                                        │
│    Total:             15-30ms                                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Scaling: 500+ Features x 100M Records

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Compute Optimization Strategies

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| Incremental computation | Only recompute features for cards with new txns | 60% compute reduction |
| Columnar partitioning | Partition by card_id_prefix (hash) | Even shuffle distribution |
| Broadcast joins | Broadcast merchant/device lookup tables (<2GB) | Eliminate shuffle |
| Adaptive query execution | `spark.sql.adaptive.enabled=true` | Auto-optimize skew |
| Column pruning | Only read columns needed per job | 70% less I/O |
| Z-order on card_id | Iceberg Z-order for data skipping | 5x read speedup |
| Checkpointing | Break lineage at expensive shuffles | Prevent recomputation on failure |

### Worker Configuration

```
Job 1 (Ingestion):    G.1X × 20  =  80 vCPU,  320 GB RAM
Job 2 (Velocity):     G.2X × 40  = 320 vCPU, 1280 GB RAM   ← shuffle-heavy
Job 3 (Graph):        G.4X × 20  = 640 vCPU, 2560 GB RAM   ← memory-heavy
Job 4 (Statistical):  G.2X × 30  = 240 vCPU,  960 GB RAM
Job 5 (Device/IP):    G.1X × 10  =  40 vCPU,  160 GB RAM   ← smallest dataset
Job 6 (Assembly):     G.2X × 30  = 240 vCPU,  960 GB RAM

Total per run: ~1560 vCPU, ~6240 GB RAM for ~2.5 hours
```

### Parallelism Strategy

Jobs 2-5 run in parallel (Glue Workflow with conditional triggers). Only Job 1
(ingestion) and Job 6 (assembly) are sequential gates.

```
Time:  0min         30min        90min        120min       150min
       │            │            │            │            │
       ├─ Job 1 ───┤            │            │            │
       │            ├─ Job 2 ───┼────────────┤            │
       │            ├─ Job 3 ───┼────────────┼────────────┤
       │            ├─ Job 4 ───┼────────────┤            │
       │            ├─ Job 5 ───┤            │            │
       │            │            │            ├─ Job 6 ───┤
       │            │            │            │            │
```

---

## 9. Cost Breakdown

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌───────────────────────────────────────────────────────────────────────┐
│  MONTHLY COST ESTIMATE (us-east-1)                                    │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Glue Jobs (6 runs/day × 30 days):                                    │
│    Job 1: 20 DPU × 0.5h × 6 × 30 × $0.44/DPU-hr    =   $  792      │
│    Job 2: 40 DPU × 0.75h × 6 × 30 × $0.44           =   $ 2,376     │
│    Job 3: 20 DPU × 1.0h × 6 × 30 × $0.44 (G.4X×2)  =   $ 3,168     │
│    Job 4: 30 DPU × 0.67h × 6 × 30 × $0.44           =   $ 1,584     │
│    Job 5: 10 DPU × 0.33h × 6 × 30 × $0.44           =   $   262     │
│    Job 6: 30 DPU × 0.42h × 6 × 30 × $0.44           =   $ 1,000     │
│  ────────────────────────────────────────────────────────────────      │
│  Glue Subtotal:                                          $ 9,182/mo   │
│                                                                        │
│  S3 Storage (90 days × 100M txns/day × ~1KB each):                    │
│    Raw + Curated + Features: ~30 TB                  =   $ 690/mo     │
│                                                                        │
│  DynamoDB (Online Feature Store):                                      │
│    50M items × 2KB avg × WCU for batch writes        =   $ 3,500/mo  │
│    500K reads/sec peak (on-demand)                   =   $ 4,200/mo   │
│  ────────────────────────────────────────────────────────────────      │
│  DynamoDB Subtotal:                                      $ 7,700/mo   │
│                                                                        │
│  DMS (CDC from Aurora):                              =   $   800/mo   │
│  Glue Data Catalog & Crawlers:                       =   $   150/mo   │
│  CloudWatch & SNS Alerting:                          =   $   100/mo   │
│                                                                        │
│  ════════════════════════════════════════════════════════════════       │
│  TOTAL:                                                 ~$18,600/mo   │
│  ════════════════════════════════════════════════════════════════       │
│                                                                        │
│  vs. Alternatives:                                                     │
│    Persistent EMR 50-node:          ~$80,000/mo                       │
│    Aurora replicas (real-time):     ~$500,000+/mo                     │
│    Databricks equivalent:           ~$25,000/mo                       │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 10. Companies Running This Pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Company | Scale | Key Detail |
|---------|-------|------------|
| **Capital One** | 200M+ txns/day | Pioneered batch+streaming feature store on AWS; 1000+ features per card |
| **Stripe** | 300M+ API calls/day | Radar fraud system uses batch-computed merchant risk scores + velocity |
| **PayPal** | 400M+ accounts | Graph-based features detect fraud rings spanning millions of accounts |
| **Square (Block)** | 100M+ txns/day | Seller risk scoring with merchant network features |
| **Visa** | 500M+ txns/day | VisaNet batch feature pipeline feeds real-time Decision Manager |
| **Nubank** | 80M+ customers | All-in on AWS; Glue + SageMaker for credit/fraud features |
| **Adyen** | 200M+ txns/day | RevenueProtect uses batch merchant behavior profiles |

### Common Patterns Across These Companies

1. **Dual-store architecture** — S3 for training, low-latency store for serving
2. **Feature versioning** — every model version pins to a feature schema version
3. **Incremental over full recompute** — only update features for active cards
4. **Graph features differentiate** — network/linkage features catch organized fraud that velocity alone misses
5. **4-6 hour freshness** is the industry standard for batch features (supplemented by streaming counters for 1h windows)

---

## Key Takeaways

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. Glue's serverless model eliminates 80% waste vs persistent EMR   │
│  2. Parallel job execution (Jobs 2-5) cuts wall-clock time by 60%    │
│  3. Graph features (Job 3) are the highest-value, highest-cost job   │
│  4. DynamoDB online store enables <5ms feature lookup at 500K RPS    │
│  5. Feature quality monitoring prevents silent model degradation     │
│  6. Point-in-time correctness in training prevents data leakage      │
│  7. Total cost ~$18K/mo to serve 500+ features for 50M cards         │
└──────────────────────────────────────────────────────────────────────┘
```
