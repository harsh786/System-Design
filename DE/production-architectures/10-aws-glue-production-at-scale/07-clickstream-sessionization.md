# Clickstream Analytics & Sessionization Pipeline at Google Analytics/Amplitude Scale

## 1. The Problem: 20B Page Views/Day → Sessionized, Attributed User Journeys

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

An analytics platform (think Google Analytics 4, Amplitude, Mixpanel) ingests raw clickstream
events from thousands of customer websites and apps. The raw events are meaningless individually—
value comes from stitching them into **sessions**, computing **attribution**, building **funnels**,
and scoring **engagement**.

### Scale Numbers

| Metric                    | Value                          |
|---------------------------|--------------------------------|
| Raw events/day            | 20 billion                     |
| Unique users/day          | 500 million                    |
| Sessions/day              | 2 billion                      |
| Avg events/session        | 10                             |
| Event types               | 100+ (page_view, click, scroll, purchase, etc.) |
| Avg session duration      | 4.2 minutes                    |
| Cross-device users        | 35% have 2+ devices            |
| Late-arriving events      | 3% arrive after 1+ hours       |
| Customer accounts         | 50,000 websites/apps           |
| Retention (raw)           | 90 days                        |
| Retention (aggregated)    | 2 years                        |

### Core Requirements

1. **Session Boundary Detection** — 30-minute inactivity timeout, configurable per customer
2. **Cross-Device Identity Stitching** — deterministic (login) + probabilistic (fingerprint)
3. **Multi-Touch Attribution** — last-touch, linear, time-decay, position-based, Shapley
4. **Funnel Analysis** — ordered step completion with configurable time windows
5. **Engagement Scoring** — frequency, recency, depth, breadth composite score
6. **A/B Test Datasets** — consistent user assignment with metric computation per variant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

### Real-Time Session Detection (Flink/Spark Streaming)

```
Problem: Maintaining session state for 500M concurrent users
- State per user: ~2KB (last event time, session_id, device info)
- Total state: 500M × 2KB = 1TB in-memory state
- Checkpoint overhead: 1TB every 60 seconds = unsustainable
- Recovery time after failure: 10+ minutes (unacceptable)
```

### RDBMS Window Functions

```
Problem: SELECT with WINDOW on 20B rows
- Even columnar (Redshift): 20B row sort + window = 4+ hours
- Partition by user_id: 500M partitions, huge shuffle
- Cost: $50K+ cluster running continuously
```

### Lambda Per Event

```
Problem: No session context
- Each Lambda sees one event in isolation
- Session requires ordered sequence of events per user
- DynamoDB for state: 20B reads + writes/day = $200K/month
- Race conditions on concurrent events from same user
```

### Simple Time Partitioning

```
Problem: Sessions span partition boundaries
- User starts session at 23:55, continues at 00:05
- Hourly partitions split this session into two
- Naive approach: double-count or lose session continuity
```

### Why Glue Batch + Micro-Batch Works

```
- Process hourly micro-batches (manageable 833M events/batch)
- Sort within partition: Spark handles 833M rows efficiently
- Look-back window: check last event from previous hour for boundary users
- State: zero persistent state (recomputed from sorted data)
- Cost: pay only for processing time, not 24/7 state maintenance
- Late arrivals: reprocess affected hour with updated data
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA COLLECTION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────────┐    │
│  │ Web SDK  │   │ Mobile SDK   │   │ Server Events │   │ Third-Party      │    │
│  │ (JS tag) │   │ (iOS/Android)│   │ (webhooks)    │   │ Integrations     │    │
│  └────┬─────┘   └──────┬───────┘   └───────┬───────┘   └────────┬─────────┘    │
│       │                 │                    │                     │              │
│       ▼                 ▼                    ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │                    API Gateway (Edge Locations)                       │        │
│  │              Validate, enrich with geo/device, forward               │        │
│  └──────────────────────────────┬───────────────────────────────────────┘        │
│                                  │                                                │
└──────────────────────────────────┼────────────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │              Kinesis Data Streams (64 shards)                         │        │
│  │              Partition Key: customer_id + device_id                   │        │
│  │              Retention: 24 hours                                      │        │
│  └──────────────────────────────┬───────────────────────────────────────┘        │
│                                  │                                                │
│                                  ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │              Kinesis Firehose → S3 (hourly partitions)               │        │
│  │              s3://clickstream-raw/{customer}/{yyyy}/{mm}/{dd}/{hh}/   │        │
│  │              Format: Parquet, Snappy compressed                       │        │
│  └──────────────────────────────┬───────────────────────────────────────┘        │
│                                  │                                                │
└──────────────────────────────────┼────────────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        GLUE PROCESSING PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │  JOB 1: Event Dedup + Bot Filter + Normalization                   │          │
│  │  Trigger: Hourly (T+10 min)                                        │          │
│  │  Workers: 80 × G.2X    DPU-hours: 160                             │          │
│  │  Input: Raw Parquet    Output: Clean events (Iceberg)              │          │
│  └────────────────────────────────┬───────────────────────────────────┘          │
│                                    ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │  JOB 2: Identity Resolution (Cross-Device Stitching)               │          │
│  │  Trigger: After Job 1 completes                                    │          │
│  │  Workers: 40 × G.2X    DPU-hours: 80                              │          │
│  │  Input: Clean events + Identity Graph    Output: Stitched events   │          │
│  └────────────────────────────────┬───────────────────────────────────┘          │
│                                    ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │  JOB 3: Sessionization                                             │          │
│  │  Trigger: After Job 2 completes                                    │          │
│  │  Workers: 120 × G.2X   DPU-hours: 360                             │          │
│  │  Input: Stitched events (current hour + boundary lookback)         │          │
│  │  Output: Session table (Iceberg, partitioned by customer/date)     │          │
│  └────────────────────────────────┬───────────────────────────────────┘          │
│                                    ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │  JOB 4: Attribution Computation                                    │          │
│  │  Trigger: After Job 3 completes                                    │          │
│  │  Workers: 60 × G.2X    DPU-hours: 120                             │          │
│  │  Input: Sessions + Conversions    Output: Attribution table        │          │
│  └────────────────────────────────┬───────────────────────────────────┘          │
│                                    ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │  JOB 5: Funnel + Engagement Metrics                                │          │
│  │  Trigger: After Job 4 completes                                    │          │
│  │  Workers: 40 × G.2X    DPU-hours: 80                              │          │
│  │  Input: Sessions    Output: Funnel metrics, Engagement scores      │          │
│  └────────────────────────────────┬───────────────────────────────────┘          │
│                                    │                                              │
└────────────────────────────────────┼──────────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT / SERVING LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐                  │
│  │ Sessions Table │  │ Attribution     │  │ Funnel Metrics   │                  │
│  │ (Iceberg)      │  │ Table (Iceberg) │  │ (Iceberg)        │                  │
│  └───────┬────────┘  └────────┬────────┘  └────────┬─────────┘                  │
│          │                     │                     │                            │
│          ▼                     ▼                     ▼                            │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │  Athena / Trino — Ad-hoc analytics queries                          │        │
│  │  Redshift Spectrum — Dashboard backing store                         │        │
│  │  DynamoDB — Real-time session lookup (last 24h)                     │        │
│  └──────────────────────────────────────────────────────────────────────┘        │
│                                                                                   │
│  CONSUMERS:                                                                       │
│  • Product Analytics Dashboards (session metrics, page flows)                    │
│  • Marketing ROI Reports (attribution by channel)                                │
│  • Growth Team (funnel drop-off analysis)                                        │
│  • Data Science (engagement models, churn prediction)                            │
│  • A/B Test Platform (metric computation per variant)                            │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used

| Concept                          | Application                                           |
|----------------------------------|-------------------------------------------------------|
| **Glue Streaming ETL**           | Near-real-time micro-batch mode for <15 min latency   |
| **DynamicFrame → DataFrame**     | Convert for Spark window functions in sessionization   |
| **Job Bookmarks**                | Track processed hourly partitions, avoid reprocessing  |
| **Pushdown Predicates**          | Read only target customer/date from catalog            |
| **G.2X Workers**                 | 16GB RAM per executor for sort-heavy sessionization    |
| **Glue Workflows**               | Chain Jobs 1→2→3→4→5 with conditional triggers        |
| **Glue Data Catalog**            | Register Iceberg tables, track schema evolution        |
| **Custom Connectors**            | Read identity graph from Neptune/DynamoDB              |
| **Spark UI via Glue**            | Monitor shuffle, skew during sessionization sorts      |
| **Auto Scaling**                 | Scale workers based on partition size variability       |

### Workflow Trigger Configuration

```
Workflow: clickstream_hourly_pipeline
├── Trigger: Schedule (every hour at :10)
│   └── Job 1: event_dedup_normalize
├── Trigger: Job 1 SUCCEEDED
│   └── Job 2: identity_resolution
├── Trigger: Job 2 SUCCEEDED
│   └── Job 3: sessionization
├── Trigger: Job 3 SUCCEEDED
│   ├── Job 4: attribution_compute (parallel)
│   └── Job 5: funnel_engagement   (parallel)
└── Trigger: Jobs 4 AND 5 SUCCEEDED
    └── Crawler: update_catalog_partitions
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code

### Job 1: Event Dedup, Bot Filtering, Normalization

```python
# job1_event_dedup_normalize.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_hour', 'raw_path', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# ─── Configuration ───────────────────────────────────────────────────────────
PROCESSING_HOUR = args['processing_hour']  # e.g., "2024-01-15T14"
RAW_PATH = args['raw_path']
OUTPUT_PATH = args['output_path']

# Known bot user-agent patterns
BOT_PATTERNS = [
    "googlebot", "bingbot", "slurp", "duckduckbot", "baiduspider",
    "yandexbot", "sogou", "facebot", "ia_archiver", "semrushbot",
    "ahrefsbot", "dotbot", "rogerbot", "screaming frog"
]
BOT_REGEX = "|".join(BOT_PATTERNS)

# ─── Read raw hourly partition ───────────────────────────────────────────────
raw_df = spark.read.parquet(f"{RAW_PATH}/{PROCESSING_HOUR}/")

print(f"Raw events loaded: {raw_df.count()}")

# ─── Bot Detection ───────────────────────────────────────────────────────────
def detect_bots(df):
    """Multi-signal bot detection."""
    return df.withColumn(
        "is_bot",
        F.when(
            # User-agent based detection
            F.lower(F.col("user_agent")).rlike(BOT_REGEX), True
        ).when(
            # Superhuman click speed (< 100ms between events)
            F.col("time_since_last_event_ms") < 100, True
        ).when(
            # No JS execution (headless indicator)
            (F.col("has_js") == False) & (F.col("event_type") == "page_view"), True
        ).when(
            # Known datacenter IP ranges
            F.col("ip_is_datacenter") == True, True
        ).when(
            # Abnormal event rate (>500 events/minute from single device)
            F.col("events_per_minute") > 500, True
        ).otherwise(False)
    )

# Compute events per minute per device for bot detection
event_rate_window = Window.partitionBy("device_id").orderBy("event_timestamp") \
    .rangeBetween(-60000, 0)  # 60 second lookback in milliseconds

raw_df = raw_df.withColumn(
    "events_per_minute",
    F.count("*").over(event_rate_window)
)

raw_df = raw_df.withColumn(
    "time_since_last_event_ms",
    F.col("event_timestamp").cast("long") -
    F.lag("event_timestamp").over(
        Window.partitionBy("device_id").orderBy("event_timestamp")
    ).cast("long")
)

raw_df = detect_bots(raw_df)
clean_df = raw_df.filter(F.col("is_bot") == False)

# ─── Deduplication ───────────────────────────────────────────────────────────
# Events may be sent multiple times (retries, SDK bugs)
# Dedup on (event_id) keeping earliest received
dedup_window = Window.partitionBy("event_id").orderBy("received_at")

deduped_df = clean_df.withColumn(
    "row_num", F.row_number().over(dedup_window)
).filter(F.col("row_num") == 1).drop("row_num")

# ─── Normalization ───────────────────────────────────────────────────────────
normalized_df = deduped_df.select(
    F.col("event_id"),
    F.col("customer_id"),          # Analytics customer (website owner)
    F.col("anonymous_id"),         # Pre-login device identifier
    F.col("user_id"),              # Post-login user identifier (nullable)
    F.col("device_id"),            # Fingerprint-based device ID
    F.col("event_type"),           # page_view, click, purchase, etc.
    F.col("event_timestamp").cast("timestamp"),
    F.col("received_at").cast("timestamp"),
    F.col("page_url"),
    F.col("page_title"),
    F.col("referrer_url"),
    F.col("utm_source"),
    F.col("utm_medium"),
    F.col("utm_campaign"),
    F.col("utm_content"),
    F.col("utm_term"),
    F.col("device_type"),          # desktop, mobile, tablet
    F.col("browser"),
    F.col("os"),
    F.col("country"),
    F.col("region"),
    F.col("city"),
    F.col("properties").cast("string"),  # Event-specific JSON properties
    F.col("revenue").cast("double"),     # For purchase events
    F.lit(PROCESSING_HOUR).alias("processing_hour")
)

# ─── Write to Iceberg ────────────────────────────────────────────────────────
normalized_df.writeTo("glue_catalog.clickstream.events_clean") \
    .partitionedBy("customer_id", "processing_hour") \
    .append()

bot_count = raw_df.filter(F.col("is_bot") == True).count()
dedup_removed = clean_df.count() - deduped_df.count()
print(f"Bots filtered: {bot_count}, Duplicates removed: {dedup_removed}")
print(f"Clean events written: {normalized_df.count()}")

job.commit()
```

### Job 2: Identity Resolution (Cross-Device Stitching)

```python
# job2_identity_resolution.py
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_hour', 'identity_graph_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

PROCESSING_HOUR = args['processing_hour']

# ─── Load clean events ───────────────────────────────────────────────────────
events_df = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.events_clean") \
    .filter(F.col("processing_hour") == PROCESSING_HOUR)

# ─── Load Identity Graph ─────────────────────────────────────────────────────
# The identity graph maps device_id / anonymous_id → canonical_user_id
# Built incrementally from login events (deterministic) and
# fingerprint clustering (probabilistic)

identity_graph = spark.read.parquet(args['identity_graph_path'])
# Schema: anonymous_id, device_id, canonical_user_id, confidence, method

# ─── Update Identity Graph with new login signals ────────────────────────────
# When a user logs in, we get a definitive link: anonymous_id ↔ user_id
login_events = events_df.filter(
    (F.col("user_id").isNotNull()) & (F.col("anonymous_id").isNotNull())
).select(
    "customer_id", "anonymous_id", "device_id", "user_id"
).distinct()

# Deterministic links: highest confidence
new_links = login_events.select(
    F.col("anonymous_id"),
    F.col("device_id"),
    F.col("user_id").alias("canonical_user_id"),
    F.lit(1.0).alias("confidence"),
    F.lit("deterministic_login").alias("method")
)

# Merge new links into identity graph (upsert logic)
updated_graph = identity_graph.union(new_links) \
    .withColumn(
        "rank",
        F.row_number().over(
            Window.partitionBy("anonymous_id", "device_id")
            .orderBy(F.desc("confidence"))
        )
    ).filter(F.col("rank") == 1).drop("rank")

# ─── Stitch events to canonical user ────────────────────────────────────────
# Priority: explicit user_id > graph by anonymous_id > graph by device_id > anonymous_id as-is

stitched_df = events_df.join(
    updated_graph.select(
        F.col("anonymous_id"),
        F.col("canonical_user_id").alias("graph_user_id_by_anon")
    ),
    on="anonymous_id",
    how="left"
).join(
    updated_graph.select(
        F.col("device_id"),
        F.col("canonical_user_id").alias("graph_user_id_by_device")
    ).distinct(),
    on="device_id",
    how="left"
)

stitched_df = stitched_df.withColumn(
    "resolved_user_id",
    F.coalesce(
        F.col("user_id"),                    # Explicit login in this event
        F.col("graph_user_id_by_anon"),      # Graph match on anonymous_id
        F.col("graph_user_id_by_device"),    # Graph match on device_id
        F.col("anonymous_id")               # Fallback: use anonymous_id
    )
).withColumn(
    "identity_confidence",
    F.when(F.col("user_id").isNotNull(), 1.0)
     .when(F.col("graph_user_id_by_anon").isNotNull(), 0.95)
     .when(F.col("graph_user_id_by_device").isNotNull(), 0.7)
     .otherwise(0.5)
)

# ─── Write stitched events ──────────────────────────────────────────────────
output_df = stitched_df.select(
    "event_id", "customer_id", "resolved_user_id", "anonymous_id",
    "device_id", "event_type", "event_timestamp", "page_url",
    "page_title", "referrer_url", "utm_source", "utm_medium",
    "utm_campaign", "utm_content", "utm_term", "device_type",
    "browser", "os", "country", "region", "city",
    "properties", "revenue", "identity_confidence", "processing_hour"
)

output_df.writeTo("glue_catalog.clickstream.events_stitched") \
    .partitionedBy("customer_id", "processing_hour") \
    .append()

# Save updated identity graph
updated_graph.write.mode("overwrite").parquet(args['identity_graph_path'])

job.commit()
```

### Job 3: Sessionization (Core Algorithm)

```python
# job3_sessionization.py
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StringType
import hashlib

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_hour', 'session_timeout_minutes'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

PROCESSING_HOUR = args['processing_hour']
SESSION_TIMEOUT_MS = int(args['session_timeout_minutes']) * 60 * 1000  # Default: 30 min

# ─── Load stitched events for current hour + lookback ────────────────────────
# We need events from the previous hour to handle boundary sessions
current_hour_events = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.events_stitched") \
    .filter(F.col("processing_hour") == PROCESSING_HOUR)

# Lookback: last 35 minutes of previous hour (to cover timeout boundary)
from datetime import datetime, timedelta
current_dt = datetime.strptime(PROCESSING_HOUR, "%Y-%m-%dT%H")
prev_hour = (current_dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H")

prev_hour_events = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.events_stitched") \
    .filter(F.col("processing_hour") == prev_hour) \
    .filter(F.col("event_timestamp") >= F.lit(
        (current_dt - timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
    ))

# Combine for boundary handling
all_events = current_hour_events.union(prev_hour_events)

# ─── Session Boundary Detection Algorithm ────────────────────────────────────
#
# Algorithm: Gap-based sessionization
# 1. Sort events by (resolved_user_id, customer_id, event_timestamp)
# 2. Compute time gap from previous event for same user+customer
# 3. Mark new session boundary where gap > SESSION_TIMEOUT
# 4. Assign session_id using cumulative sum of boundary flags
#

user_time_window = Window.partitionBy(
    "customer_id", "resolved_user_id"
).orderBy("event_timestamp")

sessionized_df = all_events.withColumn(
    "prev_event_time",
    F.lag("event_timestamp").over(user_time_window)
).withColumn(
    "time_gap_ms",
    (F.col("event_timestamp").cast("long") - F.col("prev_event_time").cast("long")) * 1000
).withColumn(
    "is_new_session",
    F.when(
        F.col("prev_event_time").isNull(), 1  # First event ever
    ).when(
        F.col("time_gap_ms") > SESSION_TIMEOUT_MS, 1  # Timeout exceeded
    ).when(
        # New session on UTM change (campaign-based session split)
        (F.col("utm_source").isNotNull()) &
        (F.col("utm_source") != F.lag("utm_source").over(user_time_window)),
        1
    ).otherwise(0)
).withColumn(
    "session_seq",
    F.sum("is_new_session").over(user_time_window)
)

# Generate deterministic session_id from components
sessionized_df = sessionized_df.withColumn(
    "session_id",
    F.sha2(
        F.concat_ws("||",
            F.col("customer_id"),
            F.col("resolved_user_id"),
            F.col("session_seq").cast("string"),
            # Include date to avoid collisions across days
            F.date_format(F.col("event_timestamp"), "yyyy-MM-dd")
        ), 256
    )
)

# ─── Compute Session-Level Metrics ──────────────────────────────────────────
session_window = Window.partitionBy("session_id")
session_ordered = Window.partitionBy("session_id").orderBy("event_timestamp")

sessionized_df = sessionized_df.withColumn(
    "event_order_in_session", F.row_number().over(session_ordered)
).withColumn(
    "session_event_count", F.count("*").over(session_window)
).withColumn(
    "session_start_time", F.min("event_timestamp").over(session_window)
).withColumn(
    "session_end_time", F.max("event_timestamp").over(session_window)
).withColumn(
    "session_duration_seconds",
    (F.max("event_timestamp").over(session_window).cast("long") -
     F.min("event_timestamp").over(session_window).cast("long"))
)

# ─── Session Summary Table ───────────────────────────────────────────────────
session_summary = sessionized_df.groupBy(
    "session_id", "customer_id", "resolved_user_id"
).agg(
    F.min("event_timestamp").alias("session_start"),
    F.max("event_timestamp").alias("session_end"),
    F.count("*").alias("event_count"),
    F.countDistinct("page_url").alias("unique_pages"),
    F.first("referrer_url").alias("entry_referrer"),
    F.first("page_url").alias("landing_page"),
    F.last("page_url").alias("exit_page"),
    F.first("utm_source").alias("utm_source"),
    F.first("utm_medium").alias("utm_medium"),
    F.first("utm_campaign").alias("utm_campaign"),
    F.first("device_type").alias("device_type"),
    F.first("browser").alias("browser"),
    F.first("country").alias("country"),
    F.sum("revenue").alias("session_revenue"),
    F.max(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("has_conversion"),
    F.collect_list(
        F.struct("event_order_in_session", "event_type", "page_url", "event_timestamp")
    ).alias("event_sequence")
).withColumn(
    "session_duration_seconds",
    F.col("session_end").cast("long") - F.col("session_start").cast("long")
).withColumn(
    "is_bounce",
    F.when(F.col("event_count") == 1, True).otherwise(False)
).withColumn(
    "session_date",
    F.to_date("session_start")
)

# ─── Filter to only sessions that START in current processing hour ───────────
# (Boundary sessions from previous hour were needed for context only)
hour_start = current_dt.strftime("%Y-%m-%d %H:%M:%S")
hour_end = (current_dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

current_hour_sessions = session_summary.filter(
    (F.col("session_start") >= hour_start) & (F.col("session_start") < hour_end)
)

# Also update sessions that SPAN the boundary (started last hour, continued this hour)
boundary_sessions = session_summary.filter(
    (F.col("session_start") < hour_start) & (F.col("session_end") >= hour_start)
)

# Write session events (detailed)
sessionized_df.filter(
    F.col("processing_hour") == PROCESSING_HOUR
).writeTo("glue_catalog.clickstream.session_events") \
    .partitionedBy("customer_id", "processing_hour") \
    .append()

# Write/update session summaries
current_hour_sessions.writeTo("glue_catalog.clickstream.sessions") \
    .partitionedBy("customer_id", "session_date") \
    .append()

# Merge boundary sessions (update existing records)
boundary_sessions.createOrReplaceTempView("boundary_updates")
spark.sql("""
    MERGE INTO glue_catalog.clickstream.sessions t
    USING boundary_updates s
    ON t.session_id = s.session_id
    WHEN MATCHED THEN UPDATE SET
        session_end = s.session_end,
        event_count = s.event_count,
        unique_pages = s.unique_pages,
        exit_page = s.exit_page,
        session_revenue = s.session_revenue,
        has_conversion = s.has_conversion,
        session_duration_seconds = s.session_duration_seconds,
        is_bounce = s.is_bounce,
        event_sequence = s.event_sequence
""")

job.commit()
```

### Job 4: Multi-Touch Attribution

```python
# job4_attribution.py
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import ArrayType, StructType, StructField, StringType, DoubleType

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'processing_date'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

PROCESSING_DATE = args['processing_date']
ATTRIBUTION_WINDOW_DAYS = 30  # Look back 30 days for touchpoints

# ─── Load sessions with conversions ─────────────────────────────────────────
sessions = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.sessions") \
    .filter(F.col("session_date") == PROCESSING_DATE)

# Get converting sessions
conversions = sessions.filter(F.col("has_conversion") == True) \
    .select("customer_id", "resolved_user_id", "session_id",
            "session_start", "session_revenue")

# Get all touchpoints in attribution window for converting users
from datetime import datetime, timedelta
proc_date = datetime.strptime(PROCESSING_DATE, "%Y-%m-%d")
window_start = (proc_date - timedelta(days=ATTRIBUTION_WINDOW_DAYS)).strftime("%Y-%m-%d")

all_touchpoints = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.sessions") \
    .filter(
        (F.col("session_date") >= window_start) &
        (F.col("session_date") <= PROCESSING_DATE) &
        (F.col("utm_source").isNotNull())  # Only sessions with attribution data
    ).select(
        "customer_id", "resolved_user_id", "session_id",
        "session_start", "utm_source", "utm_medium", "utm_campaign"
    )

# ─── Build touchpoint sequences per conversion ──────────────────────────────
# Join conversions with their preceding touchpoints
conversion_touchpoints = conversions.alias("c").join(
    all_touchpoints.alias("t"),
    (F.col("c.customer_id") == F.col("t.customer_id")) &
    (F.col("c.resolved_user_id") == F.col("t.resolved_user_id")) &
    (F.col("t.session_start") <= F.col("c.session_start")),
    how="inner"
).select(
    F.col("c.session_id").alias("conversion_session_id"),
    F.col("c.session_revenue").alias("revenue"),
    F.col("c.session_start").alias("conversion_time"),
    F.col("t.session_id").alias("touchpoint_session_id"),
    F.col("t.session_start").alias("touchpoint_time"),
    F.col("t.utm_source").alias("channel"),
    F.col("t.utm_medium").alias("medium"),
    F.col("t.utm_campaign").alias("campaign"),
    F.col("c.customer_id")
)

# Order touchpoints per conversion
tp_window = Window.partitionBy("conversion_session_id").orderBy("touchpoint_time")
tp_count_window = Window.partitionBy("conversion_session_id")

conversion_touchpoints = conversion_touchpoints.withColumn(
    "touchpoint_position", F.row_number().over(tp_window)
).withColumn(
    "total_touchpoints", F.count("*").over(tp_count_window)
).withColumn(
    "days_before_conversion",
    F.datediff(F.col("conversion_time"), F.col("touchpoint_time"))
)

# ─── Attribution Model 1: Last Touch ────────────────────────────────────────
last_touch = conversion_touchpoints.filter(
    F.col("touchpoint_position") == F.col("total_touchpoints")
).withColumn(
    "attribution_credit", F.lit(1.0)
).withColumn(
    "attribution_revenue", F.col("revenue")
).withColumn(
    "model", F.lit("last_touch")
)

# ─── Attribution Model 2: First Touch ───────────────────────────────────────
first_touch = conversion_touchpoints.filter(
    F.col("touchpoint_position") == 1
).withColumn(
    "attribution_credit", F.lit(1.0)
).withColumn(
    "attribution_revenue", F.col("revenue")
).withColumn(
    "model", F.lit("first_touch")
)

# ─── Attribution Model 3: Linear ────────────────────────────────────────────
linear = conversion_touchpoints.withColumn(
    "attribution_credit", 1.0 / F.col("total_touchpoints")
).withColumn(
    "attribution_revenue", F.col("revenue") / F.col("total_touchpoints")
).withColumn(
    "model", F.lit("linear")
)

# ─── Attribution Model 4: Time Decay ────────────────────────────────────────
# Half-life of 7 days: credit halves every 7 days before conversion
HALF_LIFE_DAYS = 7.0

time_decay = conversion_touchpoints.withColumn(
    "raw_weight",
    F.pow(F.lit(0.5), F.col("days_before_conversion") / F.lit(HALF_LIFE_DAYS))
).withColumn(
    "weight_sum",
    F.sum("raw_weight").over(tp_count_window)
).withColumn(
    "attribution_credit", F.col("raw_weight") / F.col("weight_sum")
).withColumn(
    "attribution_revenue", F.col("revenue") * F.col("attribution_credit")
).withColumn(
    "model", F.lit("time_decay")
)

# ─── Attribution Model 5: Position-Based (U-Shaped) ─────────────────────────
# 40% first, 40% last, 20% distributed among middle
position_based = conversion_touchpoints.withColumn(
    "attribution_credit",
    F.when(
        F.col("total_touchpoints") == 1, 1.0
    ).when(
        F.col("total_touchpoints") == 2,
        F.lit(0.5)
    ).when(
        F.col("touchpoint_position") == 1, 0.4
    ).when(
        F.col("touchpoint_position") == F.col("total_touchpoints"), 0.4
    ).otherwise(
        0.2 / (F.col("total_touchpoints") - 2)
    )
).withColumn(
    "attribution_revenue", F.col("revenue") * F.col("attribution_credit")
).withColumn(
    "model", F.lit("position_based")
)

# ─── Combine all models ─────────────────────────────────────────────────────
all_attributions = last_touch.union(first_touch).union(linear) \
    .union(time_decay).union(position_based)

attribution_output = all_attributions.select(
    "customer_id", "conversion_session_id", "touchpoint_session_id",
    "channel", "medium", "campaign", "touchpoint_position",
    "total_touchpoints", "attribution_credit", "attribution_revenue",
    "model", "days_before_conversion"
).withColumn("attribution_date", F.lit(PROCESSING_DATE))

# ─── Aggregate by channel × model ───────────────────────────────────────────
channel_attribution = attribution_output.groupBy(
    "customer_id", "model", "channel", "medium", "campaign"
).agg(
    F.sum("attribution_revenue").alias("attributed_revenue"),
    F.sum("attribution_credit").alias("attributed_conversions"),
    F.countDistinct("conversion_session_id").alias("conversion_count")
).withColumn("attribution_date", F.lit(PROCESSING_DATE))

# Write results
attribution_output.writeTo("glue_catalog.clickstream.attribution_touchpoints") \
    .partitionedBy("customer_id", "attribution_date") \
    .append()

channel_attribution.writeTo("glue_catalog.clickstream.attribution_summary") \
    .partitionedBy("customer_id", "attribution_date") \
    .append()

job.commit()
```

### Job 5: Funnel Analysis & Engagement Scoring

```python
# job5_funnel_engagement.py
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'processing_date'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

PROCESSING_DATE = args['processing_date']

# ─── Load session events ─────────────────────────────────────────────────────
session_events = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.session_events") \
    .filter(F.col("processing_hour").startswith(PROCESSING_DATE))

sessions = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.sessions") \
    .filter(F.col("session_date") == PROCESSING_DATE)

# ═══════════════════════════════════════════════════════════════════════════════
# FUNNEL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

# Define standard e-commerce funnel steps
FUNNEL_STEPS = {
    "view_product": 1,
    "add_to_cart": 2,
    "begin_checkout": 3,
    "add_payment": 4,
    "purchase": 5
}

# Tag each event with its funnel step
funnel_events = session_events.filter(
    F.col("event_type").isin(list(FUNNEL_STEPS.keys()))
).withColumn(
    "funnel_step",
    F.when(F.col("event_type") == "view_product", 1)
     .when(F.col("event_type") == "add_to_cart", 2)
     .when(F.col("event_type") == "begin_checkout", 3)
     .when(F.col("event_type") == "add_payment", 4)
     .when(F.col("event_type") == "purchase", 5)
)

# Compute ordered funnel progression per user per session
# A user "reaches" step N only if they completed steps 1..N-1 in order
user_session_window = Window.partitionBy(
    "customer_id", "resolved_user_id", "session_id"
).orderBy("event_timestamp")

funnel_progress = funnel_events.withColumn(
    "max_prior_step",
    F.max("funnel_step").over(
        user_session_window.rowsBetween(Window.unboundedPreceding, -1)
    )
).withColumn(
    # Valid funnel step: either step 1 or step N where max prior >= N-1
    "is_valid_funnel_step",
    F.when(F.col("funnel_step") == 1, True)
     .when(F.col("max_prior_step") >= (F.col("funnel_step") - 1), True)
     .otherwise(False)
)

# Compute funnel metrics per customer
funnel_metrics = funnel_progress.filter(F.col("is_valid_funnel_step") == True) \
    .groupBy("customer_id") \
    .agg(
        F.countDistinct(
            F.when(F.col("funnel_step") >= 1, F.col("resolved_user_id"))
        ).alias("step1_users"),
        F.countDistinct(
            F.when(F.col("funnel_step") >= 2, F.col("resolved_user_id"))
        ).alias("step2_users"),
        F.countDistinct(
            F.when(F.col("funnel_step") >= 3, F.col("resolved_user_id"))
        ).alias("step3_users"),
        F.countDistinct(
            F.when(F.col("funnel_step") >= 4, F.col("resolved_user_id"))
        ).alias("step4_users"),
        F.countDistinct(
            F.when(F.col("funnel_step") >= 5, F.col("resolved_user_id"))
        ).alias("step5_users"),
    ).withColumn("funnel_date", F.lit(PROCESSING_DATE))

# Conversion rates
funnel_metrics = funnel_metrics.withColumn(
    "step1_to_2_rate", F.col("step2_users") / F.col("step1_users")
).withColumn(
    "step2_to_3_rate", F.col("step3_users") / F.col("step2_users")
).withColumn(
    "step3_to_4_rate", F.col("step4_users") / F.col("step3_users")
).withColumn(
    "step4_to_5_rate", F.col("step5_users") / F.col("step4_users")
).withColumn(
    "overall_conversion_rate", F.col("step5_users") / F.col("step1_users")
)

# ═══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT SCORING
# ═══════════════════════════════════════════════════════════════════════════════

# Engagement score = weighted composite of:
# - Frequency (sessions per week): 25%
# - Recency (days since last session): 25%
# - Depth (avg pages per session): 25%
# - Breadth (distinct features/sections used): 25%

# Compute per-user engagement metrics (rolling 7-day window)
from datetime import datetime, timedelta
proc_date = datetime.strptime(PROCESSING_DATE, "%Y-%m-%d")
week_ago = (proc_date - timedelta(days=7)).strftime("%Y-%m-%d")

weekly_sessions = spark.read.format("iceberg") \
    .load("glue_catalog.clickstream.sessions") \
    .filter(
        (F.col("session_date") >= week_ago) &
        (F.col("session_date") <= PROCESSING_DATE)
    )

user_engagement = weekly_sessions.groupBy("customer_id", "resolved_user_id").agg(
    F.count("*").alias("sessions_7d"),
    F.datediff(
        F.lit(PROCESSING_DATE),
        F.max("session_start")
    ).alias("days_since_last_session"),
    F.avg("unique_pages").alias("avg_pages_per_session"),
    F.avg("session_duration_seconds").alias("avg_session_duration"),
    F.sum("session_revenue").alias("revenue_7d"),
    F.sum(F.when(F.col("has_conversion") == True, 1).otherwise(0)).alias("conversions_7d")
)

# Normalize each dimension to 0-100 using percentile ranks
w = Window.partitionBy("customer_id")

user_engagement = user_engagement.withColumn(
    "frequency_score",
    F.percent_rank().over(w.orderBy("sessions_7d")) * 100
).withColumn(
    "recency_score",
    (1 - F.percent_rank().over(w.orderBy("days_since_last_session"))) * 100
).withColumn(
    "depth_score",
    F.percent_rank().over(w.orderBy("avg_pages_per_session")) * 100
).withColumn(
    "duration_score",
    F.percent_rank().over(w.orderBy("avg_session_duration")) * 100
).withColumn(
    "engagement_score",
    (F.col("frequency_score") * 0.25 +
     F.col("recency_score") * 0.25 +
     F.col("depth_score") * 0.25 +
     F.col("duration_score") * 0.25)
).withColumn(
    "engagement_tier",
    F.when(F.col("engagement_score") >= 80, "power_user")
     .when(F.col("engagement_score") >= 50, "active")
     .when(F.col("engagement_score") >= 20, "casual")
     .otherwise("dormant")
).withColumn("score_date", F.lit(PROCESSING_DATE))

# ─── Write outputs ───────────────────────────────────────────────────────────
funnel_metrics.writeTo("glue_catalog.clickstream.funnel_metrics") \
    .partitionedBy("customer_id", "funnel_date") \
    .append()

user_engagement.writeTo("glue_catalog.clickstream.engagement_scores") \
    .partitionedBy("customer_id", "score_date") \
    .append()

job.commit()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

### Late-Arriving Events

```
Problem: 3% of events arrive 1-6 hours late (network issues, offline mobile, SDK retries)

Solution: Session Reopening Logic

┌────────────────────────────────────────────────────────────────────────┐
│  Late Event Handler (runs every hour for T-6h through T-1h)           │
│                                                                        │
│  1. Identify new events that arrived for already-processed hours       │
│  2. For each late event:                                               │
│     a. Find the session it belongs to (user + timestamp within 30min)  │
│     b. If session exists → MERGE (update session end, event count)     │
│     c. If no matching session → create new single-event session        │
│  3. Recompute attribution only if late event is a conversion           │
│  4. Track late-arrival rate per customer for SLA monitoring            │
└────────────────────────────────────────────────────────────────────────┘

Implementation:
- Glue job runs with 6-hour lookback window
- Uses Iceberg MERGE INTO for idempotent session updates
- Late events >6 hours trigger async backfill job
```

### Cross-Midnight Session Handling

```
Problem: Session starts at 23:45, continues past midnight
- Session belongs to which day? (start date)
- Hourly processing at 00:10 might split it

Solution:
- Sessions are dated by their START time
- The 00:00 processing hour always looks back 35 minutes into previous day
- Session summary uses MERGE to update if session extends into new hour
- Daily aggregation runs at 06:00 (after all late arrivals for previous day)
```

### Identity Graph Updates & Re-Stitching

```
Problem: User logs in at 14:00, revealing that anonymous sessions from 09:00-13:00
         were the same person. Those sessions were already processed with anonymous_id.

Solution: Periodic re-stitching job (daily)
- Compare identity graph snapshots (yesterday vs today)
- Find newly resolved identities (anonymous_id → user_id links)
- Re-process affected sessions:
  1. Update resolved_user_id in session_events table
  2. Merge sessions that were split across devices but are now same user
  3. Recompute attribution for affected conversions
- Cost mitigation: only reprocess users with NEW identity links (typically <5%)
```

### Session Boundary Consistency

```
Guarantee: Same event always produces same session_id (deterministic)

session_id = SHA256(customer_id || resolved_user_id || session_seq || date)

This means:
- Reprocessing same data = same session_ids (idempotent)
- Late events may change session_seq for subsequent sessions → those get new IDs
- Downstream consumers must handle session_id changes (use MERGE, not INSERT)
```

### Backfill After Identity Resolution Changes

```
Scenario: Customer changes session timeout from 30min to 15min

Backfill Strategy:
1. Create new Glue workflow: backfill_sessionization
2. Process date range (configurable, typically 30 days)
3. Use separate output path to avoid disrupting live data
4. Run validation: compare session counts, duration distributions
5. Atomic swap: rename tables in Glue Catalog
6. Cost: ~$2,000 for 30-day backfill at full scale
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Query Patterns (Athena)

### Funnel Drop-Off Analysis

```sql
-- Where are users dropping off in the purchase funnel?
SELECT
    funnel_date,
    step1_users AS viewed_product,
    step2_users AS added_to_cart,
    step3_users AS began_checkout,
    step4_users AS added_payment,
    step5_users AS purchased,
    ROUND(step1_to_2_rate * 100, 1) AS view_to_cart_pct,
    ROUND(step2_to_3_rate * 100, 1) AS cart_to_checkout_pct,
    ROUND(step3_to_4_rate * 100, 1) AS checkout_to_payment_pct,
    ROUND(step4_to_5_rate * 100, 1) AS payment_to_purchase_pct,
    ROUND(overall_conversion_rate * 100, 2) AS overall_cvr_pct
FROM clickstream.funnel_metrics
WHERE customer_id = 'acme_corp'
  AND funnel_date BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY funnel_date;
```

### Channel Attribution Comparison

```sql
-- Compare attribution models for budget allocation decisions
SELECT
    channel,
    model,
    SUM(attributed_revenue) AS total_revenue,
    SUM(attributed_conversions) AS total_conversions,
    SUM(attributed_revenue) / SUM(attributed_conversions) AS revenue_per_conversion
FROM clickstream.attribution_summary
WHERE customer_id = 'acme_corp'
  AND attribution_date BETWEEN '2024-01-01' AND '2024-01-31'
GROUP BY channel, model
ORDER BY model, total_revenue DESC;
```

### Session Quality by Source

```sql
-- Which traffic sources drive highest quality sessions?
SELECT
    utm_source,
    utm_medium,
    COUNT(*) AS sessions,
    AVG(session_duration_seconds) AS avg_duration,
    AVG(unique_pages) AS avg_pages,
    SUM(CASE WHEN is_bounce THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS bounce_rate,
    SUM(CASE WHEN has_conversion THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS conversion_rate,
    SUM(session_revenue) AS total_revenue
FROM clickstream.sessions
WHERE customer_id = 'acme_corp'
  AND session_date = '2024-01-15'
  AND utm_source IS NOT NULL
GROUP BY utm_source, utm_medium
HAVING COUNT(*) > 100
ORDER BY conversion_rate DESC;
```

### User Journey Path Analysis

```sql
-- Most common paths to purchase (top 20)
WITH purchase_sessions AS (
    SELECT session_id, event_sequence
    FROM clickstream.sessions
    WHERE customer_id = 'acme_corp'
      AND session_date = '2024-01-15'
      AND has_conversion = true
),
paths AS (
    SELECT
        array_join(
            transform(
                filter(event_sequence, x -> x.event_type IN ('page_view', 'purchase')),
                x -> x.page_url
            ),
            ' → '
        ) AS journey_path
    FROM purchase_sessions
)
SELECT journey_path, COUNT(*) AS occurrences
FROM paths
GROUP BY journey_path
ORDER BY occurrences DESC
LIMIT 20;
```

### Engagement Tier Distribution

```sql
-- How is our user base distributed across engagement tiers?
SELECT
    engagement_tier,
    COUNT(*) AS user_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct,
    AVG(sessions_7d) AS avg_sessions,
    AVG(revenue_7d) AS avg_revenue,
    AVG(engagement_score) AS avg_score
FROM clickstream.engagement_scores
WHERE customer_id = 'acme_corp'
  AND score_date = '2024-01-15'
GROUP BY engagement_tier
ORDER BY avg_score DESC;
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling: 20B Events/Day Strategy

### Partitioning Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│  S3 Partitioning (Raw → Clean → Sessions)                       │
│                                                                  │
│  Raw:      s3://raw/{customer_id}/{yyyy}/{mm}/{dd}/{hh}/        │
│  Clean:    Iceberg, partitioned by (customer_id, processing_hour)│
│  Sessions: Iceberg, partitioned by (customer_id, session_date)  │
│                                                                  │
│  Why customer_id first:                                          │
│  - Each customer's data is independent                          │
│  - Enables per-customer query isolation                          │
│  - Allows customer-level backfill without touching others       │
│  - Largest customers: 500M events/day (need sub-partitioning)   │
│  - Smallest customers: 10K events/day (fits single file)        │
└─────────────────────────────────────────────────────────────────┘
```

### Processing Parallelism

```
20B events/day ÷ 24 hours = 833M events/hour

Per hourly run:
- 833M events across 50,000 customers
- Top 100 customers: 60% of traffic (500M events)
- Remaining 49,900 customers: 40% (333M events)

Strategy:
- Large customers (>10M events/hour): dedicated Glue job per customer
- Medium customers (100K-10M): batched in groups of 100
- Small customers (<100K): batched in groups of 1000

Total parallel Glue jobs per hour: ~50
Each job: 80-120 G.2X workers
```

### Shuffle Optimization for Sessionization

```
The sessionization sort (partition by user_id, order by timestamp) is the
most expensive operation. Key optimizations:

1. Pre-sort within partitions during ingestion (Firehose sorting)
2. Use Iceberg's sort-order metadata to avoid redundant sorts
3. Bucket by user_id hash (256 buckets) to minimize shuffle
4. G.2X workers: 32GB RAM, 8 vCPU — handles 10M user sort in memory
5. spark.sql.shuffle.partitions = 2000 (tuned for data volume)
6. Broadcast join for identity graph (<2GB per customer)
```

### Iceberg Table Maintenance

```
Daily maintenance job (off-peak):
- Expire snapshots older than 7 days
- Compact small files (target: 256MB per file)
- Rewrite manifests for optimal query planning
- Orphan file cleanup

Monthly:
- Full compaction (merge 30 days of hourly appends)
- Sort-order optimization for sessions table
- Partition evolution if access patterns change
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

### Monthly Cost Breakdown (20B events/day)

| Component                        | Specification                    | Monthly Cost  |
|----------------------------------|----------------------------------|---------------|
| **Kinesis Data Streams**         | 64 shards, 24h retention         | $4,800        |
| **Kinesis Firehose**             | 20B events → S3                  | $6,000        |
| **S3 Storage (raw)**             | 60TB (90 day retention, Parquet) | $1,380        |
| **S3 Storage (processed)**       | 40TB (Iceberg, 2yr retention)    | $920          |
| **Glue Job 1** (dedup/filter)    | 160 DPU-hr × 24 × 30            | $50,688       |
| **Glue Job 2** (identity)        | 80 DPU-hr × 24 × 30             | $25,344       |
| **Glue Job 3** (sessionization)  | 360 DPU-hr × 24 × 30            | $114,048      |
| **Glue Job 4** (attribution)     | 120 DPU-hr × 24 × 30            | $38,016       |
| **Glue Job 5** (funnel/engage)   | 80 DPU-hr × 24 × 30             | $25,344       |
| **Glue Data Catalog**            | 500K objects                     | $500          |
| **Athena queries**               | 50TB scanned/month               | $250          |
| **DynamoDB (identity graph)**    | 50M items, on-demand             | $3,000        |
| **CloudWatch & monitoring**      | Logs, metrics, alarms            | $800          |
| **Data transfer**                | Internal S3→Glue                 | $0 (same region) |
| **TOTAL**                        |                                  | **~$271,000** |

### Cost Optimization Levers

```
1. Spot instances for Glue (Flex execution): -60% on compute → saves $152K
2. Iceberg file compaction: reduces Athena scan costs by 40%
3. Customer-tier processing:
   - Free tier customers: process every 6 hours (not hourly)
   - Saves 75% of their compute cost
4. Skip unchanged partitions via Iceberg metadata
5. Reserved capacity for predictable base load

Optimized total: ~$140,000/month ($0.007 per 1000 events)
```

### Cost vs. Alternatives

```
This pipeline at $140K/month vs:
- Google Analytics 360: $150K/month (capped at 2B events)
- Amplitude Enterprise: $200K+/month at this scale
- Self-managed Flink cluster: $180K/month (+ ops team)
- Snowflake continuous processing: $300K+/month

Glue advantage: pay-per-use, no cluster management, native AWS integration
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Running Similar Architectures

| Company        | Scale              | Approach                                    |
|----------------|--------------------|---------------------------------------------|
| **Google Analytics** | 100B+ events/day | Custom Colossus + Dremel, session via Flume |
| **Amplitude**  | 1T+ events/month   | Custom Lambda architecture on AWS           |
| **Mixpanel**   | 20B+ events/month  | Custom ingestion → GCS → BigQuery batch     |
| **Heap**       | Auto-capture all   | Kafka → S3 → Spark/Glue batch              |
| **Snowplow**   | Open-source        | Kinesis → S3 → Spark EMR (or Glue)         |
| **Segment**    | 1T+ API calls/month| Centrifuge (custom) + S3 + Spark            |
| **PostHog**    | Self-hosted scale  | Kafka → ClickHouse (real-time sessions)     |
| **Plausible**  | Privacy-focused    | ClickHouse real-time, no sessionization     |

### Key Pattern: All Large-Scale Analytics Use Batch Sessionization

```
Real-time sessionization (per-event) does NOT scale beyond ~100M events/day.
Every company at 1B+ events/day uses batch/micro-batch:

1. Ingest raw events to durable store (S3/GCS)
2. Hourly (or more frequent) batch job to compute sessions
3. Incremental updates for late arrivals
4. Separate serving layer for low-latency queries

This is exactly what the Glue pipeline above implements.
```

### Snowplow Open-Source Reference Architecture (AWS)

```
Snowplow's production-proven architecture closely mirrors ours:

Collector (Kinesis) → Enrichment (Kinesis) → S3 Loader → Glue/EMR →
  Sessions Table → Redshift/Athena

Key differences in our approach:
- Iceberg instead of plain Parquet (time-travel, MERGE support)
- Identity resolution as explicit pipeline stage
- Multi-model attribution in same pipeline
- Customer-level isolation for multi-tenant SaaS
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Summary

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Clickstream Sessionization Pipeline — Key Metrics                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Input:          20B events/day from 50K customer websites                │
│  Processing:     5-stage Glue pipeline, hourly micro-batch                │
│  Latency:        Event → queryable session: <75 minutes                   │
│  Output:         2B sessions/day + attribution + funnels + scores         │
│  Cost:           $0.007 per 1000 events (optimized)                       │
│  Accuracy:       99.7% session boundary correctness                       │
│  Availability:   99.9% (Glue managed, auto-retry on failure)             │
│                                                                            │
│  Core Insight:   Sessionization is a SORT problem, not a streaming        │
│                  problem. Batch wins at scale.                             │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```
