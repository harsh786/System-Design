# ML Training Data Pipeline at Uber/DoorDash Scale

## The Problem: 50TB/Day of Raw Events → Versioned Training Datasets for 200+ Models

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Business Context**: A ride-sharing/delivery platform with millions of daily orders needs
to continuously prepare training data for hundreds of ML models. Each model requires
feature-label alignment, point-in-time correctness, and reproducible dataset versions.

**Scale Numbers**:
- 50TB raw events per day (GPS pings, order events, driver telemetry)
- 200+ ML models in production (ETA, demand, pricing, matching, search)
- 500M+ training examples per major model
- 100-500 features per example depending on model
- Labels arrive with 1-72 hour delay (ground truth)
- New dataset versions cut every 6 hours for critical models
- 18 months of historical data available for retraining

**Models Served**:
| Model Category | Examples | Training Frequency | Features |
|---|---|---|---|
| ETA Prediction | Delivery time, ride duration | Every 6h | 350+ |
| Demand Forecasting | Order volume per zone per hour | Daily | 200+ |
| Pricing/Surge | Dynamic pricing multiplier | Every 4h | 180+ |
| Driver Matching | Optimal driver-order assignment | Every 12h | 250+ |
| Search Ranking | Restaurant/item relevance | Daily | 400+ |
| Fraud Detection | Fake orders, GPS spoofing | Every 2h | 500+ |

**Requirements**:
- **Reproducibility**: Any historical dataset version can be recreated exactly
- **Point-in-time correctness**: No future information leaks into training features
- **Label accuracy**: Ground truth labels computed only from confirmed outcomes
- **Feature-label alignment**: Features computed at prediction time, labels from outcome time
- **Freshness**: Models retrain on data no older than 6 hours for critical paths
- **Versioning**: Full lineage from raw events to training examples

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Why Traditional Approaches Fail

### 1. Training on Live Feature Store Data
```
Problem: Data leakage + non-reproducibility

- Features in store reflect CURRENT state, not state at prediction time
- Model sees "driver was 2 min away" but at prediction time driver was 15 min away
- Cannot reproduce last week's training run (features have been overwritten)
- No way to generate labels (outcomes) from feature store alone
```

### 2. Ad-Hoc SQL Queries
```
Problem: Not versioned, not reproducible, not scalable

- Data scientist writes SELECT * FROM orders WHERE date > '2024-01-01'
- Query takes 8 hours on 50TB, blocks other workloads
- No version control on the query or resulting dataset
- Different team members get different results on different days
- Point-in-time correctness requires complex self-joins that time out
```

### 3. Single Monolithic Spark Job
```
Problem: Too complex, too long-running, single point of failure

- One job trying to do sessionization + features + labels + joining
- 12-hour runtime means any failure restarts everything
- Cannot independently update label logic vs feature logic
- Memory pressure from holding entire state in one job
- Team cannot work on different stages independently
```

### 4. Feature Store Alone
```
Problem: Solves serving, not training data preparation

- Feature stores (Feast, Tecton) handle online/offline serving
- They do NOT solve: label generation, event sessionization,
  feature-label temporal alignment, dataset versioning/splitting
- Still need a pipeline upstream of the feature store
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAW EVENT SOURCES (50TB/day)                         │
├─────────────┬──────────┬───────────┬──────────┬───────────┬─────────────────┤
│ GPS Traces  │  Order   │  Driver   │ Weather  │  Traffic  │   Map Tiles     │
│ (Kinesis)   │  Events  │  Events   │   API    │   Data    │   (S3 static)   │
│ 2B pts/day  │(Kafka→S3)│(Kafka→S3) │ (hourly) │ (5-min)   │   (weekly)      │
└──────┬──────┴────┬─────┴─────┬─────┴────┬─────┴─────┬─────┴────────┬────────┘
       │           │           │          │           │              │
       ▼           ▼           ▼          ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE DATA CATALOG (Schema Registry)                       │
│  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────────┐ │
│  │gps_events │ │order_events│ │driver_evt│ │weather  │ │traffic_segments │ │
│  │(Iceberg)  │ │(Iceberg)  │ │(Iceberg) │ │(Parquet)│ │(Parquet)        │ │
│  └───────────┘ └───────────┘ └──────────┘ └─────────┘ └─────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────────┐
       │                       │                           │
       ▼                       ▼                           ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐
│  GLUE JOB 1  │    │   GLUE JOB 2     │    │      GLUE JOB 3          │
│  Event       │    │   Label           │    │      Feature             │
│  Alignment & │───▶│   Generation      │    │      Computation         │
│  Sessionize  │    │                   │    │      (Ray Workers)       │
│              │    │ - Actual ETA      │    │                          │
│ - GPS+Order  │    │ - Actual demand   │    │ - Historical patterns    │
│   matching   │    │ - True price      │    │ - Spatial (H3 hexagons)  │
│ - Session    │    │ - Match outcome   │    │ - Temporal features      │
│   boundaries │    │ - Fraud labels    │    │ - Driver features        │
│              │    │                   │    │ - Context features       │
└──────┬───────┘    └────────┬──────────┘    └────────────┬────────────┘
       │                     │                            │
       │                     ▼                            │
       │            ┌──────────────────┐                  │
       │            │  Label Store     │                  │
       │            │  (Iceberg table) │                  │
       │            │  - order_id      │                  │
       │            │  - label_type    │                  │
       │            │  - label_value   │                  │
       │            │  - label_time    │                  │
       │            └────────┬─────────┘                  │
       │                     │                            │
       ▼                     ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GLUE JOB 4                                        │
│              Point-in-Time Feature-Label Join                                │
│                                                                             │
│  For each labeled example:                                                  │
│    - Find features computed BEFORE the prediction timestamp                 │
│    - Join label computed AFTER the outcome timestamp                        │
│    - Ensure no future information leakage                                   │
│    - Validate temporal ordering: feature_time < pred_time < outcome_time    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GLUE JOB 5                                        │
│              Dataset Assembly, Versioning & Splitting                        │
│                                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Sampling   │  │  Stratified  │  │   Version    │  │  Quality       │  │
│  │  & Balancing│─▶│  Train/Val/  │─▶│   Tagging    │─▶│  Validation    │  │
│  │             │  │  Test Split  │  │  (Iceberg)   │  │  (Glue DQ)     │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERSIONED DATASETS (Iceberg)                              │
│                                                                             │
│  s3://ml-datasets/eta_model/v2024.06.15.18/                                 │
│    ├── train/    (400M examples, 70%)                                       │
│    ├── val/      (85M examples, 15%)                                        │
│    ├── test/     (85M examples, 15%)                                        │
│    └── metadata/ (schema, stats, lineage, snapshot_id)                      │
│                                                                             │
│  Iceberg snapshot_id → exact point-in-time reproducibility                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
    │ SageMaker        │  │ Model        │  │ A/B Evaluation   │
    │ Training Jobs    │  │ Registry     │  │ Framework        │
    │                  │  │              │  │                  │
    │ - Distributed    │  │ - Model +    │  │ - Holdout eval   │
    │   training       │  │   dataset    │  │ - Shadow scoring │
    │ - Hyperparameter │  │   version    │  │ - Metric diffs   │
    │   tuning         │  │   linked     │  │                  │
    └──────────────────┘  └──────────────┘  └──────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Glue Concepts Used

### Job Bookmarks for Incremental Label Generation
Labels (ground truth) arrive with delays — an order placed at 2pm might complete at 3pm,
but the delivery confirmation event arrives at 3:05pm. Job bookmarks track which events
have been processed, enabling incremental label computation without reprocessing history.

### DynamicFrame for Heterogeneous Event Types
Raw events have different schemas: GPS has lat/lng/accuracy, orders have items/amounts,
driver events have status/location. DynamicFrame handles schema evolution and mixed types
without requiring upfront schema unification.

### Glue Ray Jobs for Embarrassingly Parallel Feature Computation
Spatial features (H3 hexagon aggregations), historical pattern lookups, and per-entity
feature computation are embarrassingly parallel. Glue Ray distributes computation across
workers without Spark shuffle overhead.

### Glue Data Quality for Training Data Validation
Before any dataset version is published, automated quality rules validate:
- No null labels, feature completeness > 99.5%
- Label distribution within expected bounds
- Feature value ranges within historical norms
- No temporal leakage (feature timestamps < prediction timestamp)

### Auto-Scaling for Variable Workload
Peak hours generate 3x more events than off-peak. Auto-scaling adjusts workers
from 20 (off-peak) to 100 (peak) based on input data volume.

### Connections to Multiple Data Sources
Glue connections manage credentials for: S3 (raw events), RDS (order metadata),
DynamoDB (driver state), Redshift (historical aggregates), external APIs (weather).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Implementation Code

### Job 1: Event Alignment & Sessionization

```python
# glue_job_1_event_alignment.py
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
    'JOB_NAME', 'processing_date', 'gps_database', 'orders_database',
    'output_path', 'session_gap_minutes'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

SESSION_GAP = int(args['session_gap_minutes'])  # 30 minutes default
PROCESSING_DATE = args['processing_date']

# ─── Read GPS traces (2B points/day) ───────────────────────────────────────
gps_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=args['gps_database'],
    table_name="gps_events",
    push_down_predicate=f"event_date = '{PROCESSING_DATE}'",
    transformation_ctx="gps_source"
)

# Resolve choice fields (accuracy can be int or double depending on device)
gps_dyf = ResolveChoice.apply(
    frame=gps_dyf,
    choice="cast:double",
    transformation_ctx="resolve_gps"
)

gps_df = gps_dyf.toDF()

# ─── Read order events ─────────────────────────────────────────────────────
orders_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=args['orders_database'],
    table_name="order_events",
    push_down_predicate=f"event_date = '{PROCESSING_DATE}'",
    transformation_ctx="orders_source"
)

orders_df = orders_dyf.toDF()

# ─── Sessionize GPS traces per driver ─────────────────────────────────────
# A session breaks when gap between consecutive GPS pings > SESSION_GAP minutes
gps_windowed = Window.partitionBy("driver_id").orderBy("event_timestamp")

gps_sessioned = gps_df.withColumn(
    "prev_timestamp",
    F.lag("event_timestamp").over(gps_windowed)
).withColumn(
    "gap_minutes",
    (F.col("event_timestamp").cast("long") - F.col("prev_timestamp").cast("long")) / 60
).withColumn(
    "new_session_flag",
    F.when(
        (F.col("gap_minutes") > SESSION_GAP) | F.col("prev_timestamp").isNull(), 1
    ).otherwise(0)
).withColumn(
    "session_id",
    F.concat(
        F.col("driver_id"),
        F.lit("_"),
        F.sum("new_session_flag").over(gps_windowed)
    )
)

# ─── Align GPS sessions with order events ──────────────────────────────────
# For each order, find the driver's GPS session that overlaps the order timeframe
order_with_session = orders_df.alias("o").join(
    gps_sessioned.alias("g"),
    on=[
        F.col("o.driver_id") == F.col("g.driver_id"),
        F.col("g.event_timestamp").between(
            F.col("o.driver_assigned_time"),
            F.col("o.delivery_completed_time")
        )
    ],
    how="inner"
).groupBy(
    "o.order_id", "o.driver_id", "g.session_id"
).agg(
    F.count("g.event_timestamp").alias("gps_point_count"),
    F.min("g.event_timestamp").alias("session_start"),
    F.max("g.event_timestamp").alias("session_end"),
    F.collect_list(
        F.struct("g.latitude", "g.longitude", "g.event_timestamp", "g.accuracy")
    ).alias("gps_trace")
)

# ─── Write aligned sessions ────────────────────────────────────────────────
aligned_dyf = DynamicFrame.fromDF(order_with_session, glueContext, "aligned")

glueContext.write_dynamic_frame.from_options(
    frame=aligned_dyf,
    connection_type="s3",
    format="iceberg",
    connection_options={
        "path": f"{args['output_path']}/aligned_sessions",
        "catalog": "glue_catalog",
        "database": "ml_training",
        "table": "aligned_sessions",
        "partition_by": ["event_date"],
    },
    transformation_ctx="write_aligned"
)

job.commit()
```

### Job 2: Label Generation

```python
# glue_job_2_label_generation.py
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
    'JOB_NAME', 'processing_date', 'label_delay_hours', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

LABEL_DELAY_HOURS = int(args['label_delay_hours'])  # Wait for ground truth
PROCESSING_DATE = args['processing_date']

# ─── Only process orders where ground truth has arrived ────────────────────
# An order placed at time T needs outcome by T + label_delay to be labeled
cutoff_time = F.date_sub(F.current_timestamp(), LABEL_DELAY_HOURS / 24)

orders_df = spark.read.format("iceberg").load(
    "glue_catalog.ml_training.order_events"
).filter(
    (F.col("event_date") == PROCESSING_DATE) &
    (F.col("order_placed_time") < cutoff_time)
)

# ─── ETA Labels: Actual delivery duration ──────────────────────────────────
eta_labels = orders_df.filter(
    F.col("delivery_completed_time").isNotNull()
).select(
    F.col("order_id"),
    F.lit("eta_seconds").alias("label_type"),
    (
        F.col("delivery_completed_time").cast("long") -
        F.col("order_placed_time").cast("long")
    ).alias("label_value"),
    F.col("order_placed_time").alias("prediction_timestamp"),
    F.col("delivery_completed_time").alias("outcome_timestamp"),
    F.col("event_date")
)

# ─── Demand Labels: Actual orders per H3 hexagon per hour ─────────────────
demand_labels = orders_df.select(
    F.concat(
        F.col("pickup_h3_hex_res8"),
        F.lit("_"),
        F.date_format("order_placed_time", "yyyy-MM-dd-HH")
    ).alias("order_id"),
    F.lit("demand_count").alias("label_type"),
    F.count("*").over(
        Window.partitionBy(
            "pickup_h3_hex_res8",
            F.date_trunc("hour", "order_placed_time")
        )
    ).alias("label_value"),
    F.date_trunc("hour", "order_placed_time").alias("prediction_timestamp"),
    F.date_add(
        F.date_trunc("hour", "order_placed_time"), 1
    ).alias("outcome_timestamp"),
    F.col("event_date")
)

# ─── Surge Labels: Actual supply-demand ratio ──────────────────────────────
driver_supply = spark.read.format("iceberg").load(
    "glue_catalog.ml_training.driver_events"
).filter(
    F.col("event_date") == PROCESSING_DATE
).groupBy(
    "h3_hex_res8",
    F.date_trunc("hour", "event_timestamp").alias("hour")
).agg(
    F.countDistinct("driver_id").alias("available_drivers")
)

demand_per_hex = orders_df.groupBy(
    "pickup_h3_hex_res8",
    F.date_trunc("hour", "order_placed_time").alias("hour")
).agg(
    F.count("*").alias("order_count")
)

surge_labels = demand_per_hex.join(
    driver_supply,
    on=[
        demand_per_hex.pickup_h3_hex_res8 == driver_supply.h3_hex_res8,
        demand_per_hex.hour == driver_supply.hour
    ],
    how="left"
).select(
    F.concat(
        F.col("pickup_h3_hex_res8"), F.lit("_"),
        F.date_format("demand_per_hex.hour", "yyyy-MM-dd-HH")
    ).alias("order_id"),
    F.lit("surge_ratio").alias("label_type"),
    (F.col("order_count") / F.coalesce(F.col("available_drivers"), F.lit(1))).alias("label_value"),
    F.col("demand_per_hex.hour").alias("prediction_timestamp"),
    F.col("demand_per_hex.hour").alias("outcome_timestamp"),
    F.lit(PROCESSING_DATE).alias("event_date")
)

# ─── Union all labels and write ────────────────────────────────────────────
all_labels = eta_labels.unionByName(demand_labels).unionByName(surge_labels)

all_labels.writeTo("glue_catalog.ml_training.labels").append()

job.commit()
```

### Job 3: Feature Computation (Glue Ray)

```python
# glue_job_3_feature_computation_ray.py
import sys
import ray
import h3
import numpy as np
from datetime import datetime, timedelta
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_date', 'output_path'
])

# Initialize Ray on Glue
ray.init()

# ─── Spatial Feature Computation (H3 Hexagons) ────────────────────────────

@ray.remote
def compute_spatial_features(order_batch: list) -> list:
    """Compute spatial features for a batch of orders using H3 hexagons."""
    results = []
    for order in order_batch:
        lat, lng = order['pickup_lat'], order['pickup_lng']
        dropoff_lat, dropoff_lng = order['dropoff_lat'], order['dropoff_lng']

        # Multi-resolution H3 hexagon IDs
        h3_res7 = h3.latlng_to_cell(lat, lng, 7)
        h3_res8 = h3.latlng_to_cell(lat, lng, 8)
        h3_res9 = h3.latlng_to_cell(lat, lng, 9)

        # Haversine distance
        R = 6371000  # Earth radius in meters
        dlat = np.radians(dropoff_lat - lat)
        dlng = np.radians(dropoff_lng - lng)
        a = (np.sin(dlat/2)**2 +
             np.cos(np.radians(lat)) * np.cos(np.radians(dropoff_lat)) *
             np.sin(dlng/2)**2)
        straight_line_distance = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

        # Neighboring hexagons (for context features)
        neighbors = h3.grid_ring(h3_res8, 1)

        # H3 grid distance between pickup and dropoff
        dropoff_h3 = h3.latlng_to_cell(dropoff_lat, dropoff_lng, 8)
        h3_grid_distance = h3.grid_distance(h3_res8, dropoff_h3)

        results.append({
            'order_id': order['order_id'],
            'pickup_h3_res7': h3_res7,
            'pickup_h3_res8': h3_res8,
            'pickup_h3_res9': h3_res9,
            'dropoff_h3_res8': dropoff_h3,
            'straight_line_distance_m': straight_line_distance,
            'h3_grid_distance': h3_grid_distance,
            'pickup_neighbor_hexes': list(neighbors),
            'bearing': np.degrees(np.arctan2(
                np.sin(np.radians(dropoff_lng - lng)) * np.cos(np.radians(dropoff_lat)),
                np.cos(np.radians(lat)) * np.sin(np.radians(dropoff_lat)) -
                np.sin(np.radians(lat)) * np.cos(np.radians(dropoff_lat)) *
                np.cos(np.radians(dropoff_lng - lng))
            ))
        })
    return results


@ray.remote
def compute_temporal_features(order_batch: list) -> list:
    """Compute time-based features for a batch of orders."""
    results = []
    for order in order_batch:
        ts = datetime.fromisoformat(order['order_placed_time'])

        # Basic temporal
        hour_of_day = ts.hour
        minute_of_hour = ts.minute
        day_of_week = ts.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0

        # Cyclical encoding (preserves continuity: 23:59 is close to 00:00)
        hour_sin = np.sin(2 * np.pi * hour_of_day / 24)
        hour_cos = np.cos(2 * np.pi * hour_of_day / 24)
        dow_sin = np.sin(2 * np.pi * day_of_week / 7)
        dow_cos = np.cos(2 * np.pi * day_of_week / 7)

        # Meal period flags
        is_breakfast = 1 if 6 <= hour_of_day <= 9 else 0
        is_lunch = 1 if 11 <= hour_of_day <= 14 else 0
        is_dinner = 1 if 17 <= hour_of_day <= 21 else 0
        is_late_night = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0

        # Holiday/special event (loaded from reference table)
        is_holiday = order.get('is_holiday', 0)
        is_major_event = order.get('is_major_event', 0)

        # Minutes since midnight (for linear time features)
        minutes_since_midnight = hour_of_day * 60 + minute_of_hour

        results.append({
            'order_id': order['order_id'],
            'hour_of_day': hour_of_day,
            'day_of_week': day_of_week,
            'is_weekend': is_weekend,
            'hour_sin': hour_sin,
            'hour_cos': hour_cos,
            'dow_sin': dow_sin,
            'dow_cos': dow_cos,
            'is_breakfast': is_breakfast,
            'is_lunch': is_lunch,
            'is_dinner': is_dinner,
            'is_late_night': is_late_night,
            'is_holiday': is_holiday,
            'is_major_event': is_major_event,
            'minutes_since_midnight': minutes_since_midnight,
        })
    return results


@ray.remote
def compute_historical_features(order_batch: list, historical_stats: dict) -> list:
    """Compute historical pattern features (lookback aggregations)."""
    results = []
    for order in order_batch:
        h3_hex = order['pickup_h3_res8']
        hour = datetime.fromisoformat(order['order_placed_time']).hour
        dow = datetime.fromisoformat(order['order_placed_time']).weekday()

        # Historical averages for this hexagon + time slot
        key = f"{h3_hex}_{hour}_{dow}"
        stats = historical_stats.get(key, {})

        results.append({
            'order_id': order['order_id'],
            # Demand history
            'hist_avg_orders_same_hour_dow': stats.get('avg_orders', 0),
            'hist_std_orders_same_hour_dow': stats.get('std_orders', 0),
            'hist_avg_orders_last_7_days': stats.get('avg_orders_7d', 0),
            'hist_avg_orders_last_28_days': stats.get('avg_orders_28d', 0),
            # ETA history
            'hist_avg_eta_same_hour': stats.get('avg_eta', 0),
            'hist_p50_eta_same_hour': stats.get('p50_eta', 0),
            'hist_p90_eta_same_hour': stats.get('p90_eta', 0),
            # Supply history
            'hist_avg_drivers_same_hour': stats.get('avg_drivers', 0),
            'hist_avg_surge_same_hour': stats.get('avg_surge', 1.0),
            # Trend features
            'demand_trend_7d': stats.get('demand_trend_7d', 0),
            'eta_trend_7d': stats.get('eta_trend_7d', 0),
        })
    return results


# ─── Orchestrate parallel feature computation ──────────────────────────────

def process_features_for_date(processing_date: str, output_path: str):
    """Main orchestration: read orders, compute features in parallel, write."""
    import pyarrow.parquet as pq
    import pyarrow as pa

    # Read order data for the date
    orders_table = pq.read_table(
        f"s3://raw-events/orders/event_date={processing_date}/"
    )
    orders = orders_table.to_pylist()

    # Load historical stats (pre-computed daily aggregate table)
    hist_stats_table = pq.read_table(
        f"s3://ml-features/historical_stats/latest/"
    )
    historical_stats = {
        row['key']: row for row in hist_stats_table.to_pylist()
    }
    hist_stats_ref = ray.put(historical_stats)

    # Batch orders for parallel processing
    BATCH_SIZE = 10000
    batches = [orders[i:i+BATCH_SIZE] for i in range(0, len(orders), BATCH_SIZE)]

    # Launch parallel computation
    spatial_futures = [compute_spatial_features.remote(batch) for batch in batches]
    temporal_futures = [compute_temporal_features.remote(batch) for batch in batches]
    historical_futures = [
        compute_historical_features.remote(batch, hist_stats_ref) for batch in batches
    ]

    # Gather results
    spatial_results = [item for batch in ray.get(spatial_futures) for item in batch]
    temporal_results = [item for batch in ray.get(temporal_futures) for item in batch]
    historical_results = [item for batch in ray.get(historical_futures) for item in batch]

    # Write feature tables
    for name, results in [
        ('spatial_features', spatial_results),
        ('temporal_features', temporal_results),
        ('historical_features', historical_results)
    ]:
        table = pa.Table.from_pylist(results)
        pq.write_table(
            table,
            f"{output_path}/{name}/event_date={processing_date}/data.parquet"
        )


process_features_for_date(args['processing_date'], args['output_path'])
```

### Job 4: Point-in-Time Feature-Label Join

```python
# glue_job_4_pit_join.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_date', 'model_name', 'lookback_days', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

MODEL_NAME = args['model_name']  # e.g., "eta_prediction"
LOOKBACK_DAYS = int(args['lookback_days'])
PROCESSING_DATE = args['processing_date']

# ─── Point-in-Time Correct Join ────────────────────────────────────────────
# CRITICAL: Features must be computed from data available BEFORE prediction time
# Labels must come from events AFTER the outcome occurs
# This prevents data leakage that inflates offline metrics

# Read labels for this model
labels_df = spark.read.format("iceberg").load(
    "glue_catalog.ml_training.labels"
).filter(
    (F.col("label_type") == MODEL_NAME) &
    (F.col("event_date").between(
        F.date_sub(F.lit(PROCESSING_DATE), LOOKBACK_DAYS),
        F.lit(PROCESSING_DATE)
    ))
)

# Read pre-computed features
spatial_features = spark.read.parquet(
    f"s3://ml-features/spatial_features/event_date={PROCESSING_DATE}/"
)
temporal_features = spark.read.parquet(
    f"s3://ml-features/temporal_features/event_date={PROCESSING_DATE}/"
)
historical_features = spark.read.parquet(
    f"s3://ml-features/historical_features/event_date={PROCESSING_DATE}/"
)

# ─── Join features ensuring point-in-time correctness ──────────────────────
# The key invariant: feature_computation_time <= prediction_timestamp < outcome_timestamp

# Join all feature sets on order_id
features_df = spatial_features.join(
    temporal_features, on="order_id", how="inner"
).join(
    historical_features, on="order_id", how="inner"
)

# Join with labels — only include examples where label exists (ground truth arrived)
pit_correct_dataset = features_df.join(
    labels_df.select("order_id", "label_value", "prediction_timestamp", "outcome_timestamp"),
    on="order_id",
    how="inner"
)

# ─── Validate temporal ordering (detect leakage) ──────────────────────────
# Add validation columns
validated = pit_correct_dataset.withColumn(
    "temporal_valid",
    F.col("prediction_timestamp") < F.col("outcome_timestamp")
).withColumn(
    "has_label",
    F.col("label_value").isNotNull()
)

# Filter out invalid examples and log stats
valid_count = validated.filter(F.col("temporal_valid")).count()
invalid_count = validated.filter(~F.col("temporal_valid")).count()

print(f"Valid examples: {valid_count}, Invalid (leakage): {invalid_count}")
print(f"Leakage rate: {invalid_count / (valid_count + invalid_count) * 100:.4f}%")

# Only keep temporally valid examples
clean_dataset = validated.filter(
    F.col("temporal_valid") & F.col("has_label")
).drop("temporal_valid", "has_label")

# ─── Write point-in-time correct training examples ─────────────────────────
clean_dataset.writeTo(
    f"glue_catalog.ml_training.pit_features_{MODEL_NAME}"
).append()

job.commit()
```

### Job 5: Dataset Assembly, Versioning & Splitting

```python
# glue_job_5_dataset_assembly.py
import sys
import json
from datetime import datetime
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'model_name', 'dataset_version', 'train_ratio',
    'val_ratio', 'test_ratio', 'max_examples', 'output_path',
    'enable_stratification', 'stratify_column', 'stratify_bins'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

MODEL_NAME = args['model_name']
VERSION = args['dataset_version']  # e.g., "v2024.06.15.18"
TRAIN_RATIO = float(args['train_ratio'])  # 0.70
VAL_RATIO = float(args['val_ratio'])      # 0.15
TEST_RATIO = float(args['test_ratio'])    # 0.15
MAX_EXAMPLES = int(args['max_examples'])  # 500_000_000
ENABLE_STRATIFICATION = args['enable_stratification'] == 'true'
STRATIFY_COL = args.get('stratify_column', 'label_value')
STRATIFY_BINS = int(args.get('stratify_bins', '10'))

# ─── Read PIT-correct features ─────────────────────────────────────────────
dataset = spark.read.format("iceberg").load(
    f"glue_catalog.ml_training.pit_features_{MODEL_NAME}"
)

total_count = dataset.count()
print(f"Total available examples: {total_count:,}")

# ─── Sampling ──────────────────────────────────────────────────────────────
if total_count > MAX_EXAMPLES:
    sample_fraction = MAX_EXAMPLES / total_count
    dataset = dataset.sample(fraction=sample_fraction, seed=42)
    print(f"Sampled down to ~{MAX_EXAMPLES:,} examples")

# ─── Stratified Splitting ──────────────────────────────────────────────────
if ENABLE_STRATIFICATION:
    # Bin the label into quantile-based strata for balanced representation
    dataset = dataset.withColumn(
        "stratum",
        F.ntile(STRATIFY_BINS).over(Window.orderBy(STRATIFY_COL))
    )

    # Within each stratum, assign to train/val/test
    dataset = dataset.withColumn(
        "rand",
        F.rand(seed=42)
    ).withColumn(
        "split",
        F.when(F.col("rand") < TRAIN_RATIO, "train")
         .when(F.col("rand") < TRAIN_RATIO + VAL_RATIO, "val")
         .otherwise("test")
    )
else:
    # Simple random split (time-based for temporal models)
    # Use temporal split: oldest 70% train, next 15% val, newest 15% test
    dataset = dataset.withColumn(
        "temporal_rank",
        F.percent_rank().over(Window.orderBy("prediction_timestamp"))
    ).withColumn(
        "split",
        F.when(F.col("temporal_rank") <= TRAIN_RATIO, "train")
         .when(F.col("temporal_rank") <= TRAIN_RATIO + VAL_RATIO, "val")
         .otherwise("test")
    )

# ─── Compute dataset statistics ────────────────────────────────────────────
split_counts = dataset.groupBy("split").count().collect()
split_stats = {row['split']: row['count'] for row in split_counts}

label_stats = dataset.agg(
    F.mean("label_value").alias("label_mean"),
    F.stddev("label_value").alias("label_std"),
    F.expr("percentile_approx(label_value, 0.5)").alias("label_p50"),
    F.expr("percentile_approx(label_value, 0.9)").alias("label_p90"),
    F.expr("percentile_approx(label_value, 0.99)").alias("label_p99"),
    F.min("label_value").alias("label_min"),
    F.max("label_value").alias("label_max"),
).collect()[0]

# ─── Write versioned dataset splits ───────────────────────────────────────
output_base = f"{args['output_path']}/{MODEL_NAME}/{VERSION}"

for split_name in ["train", "val", "test"]:
    split_data = dataset.filter(F.col("split") == split_name).drop(
        "split", "rand", "stratum", "temporal_rank"
    )

    split_data.write.format("iceberg").mode("overwrite").save(
        f"glue_catalog.ml_training.{MODEL_NAME}_{split_name}_{VERSION.replace('.', '_')}"
    )

    # Also write to S3 path for SageMaker direct access
    split_data.write.parquet(
        f"{output_base}/{split_name}/",
        mode="overwrite"
    )

# ─── Write metadata ───────────────────────────────────────────────────────
metadata = {
    "model_name": MODEL_NAME,
    "version": VERSION,
    "created_at": datetime.utcnow().isoformat(),
    "total_examples": sum(split_stats.values()),
    "split_counts": split_stats,
    "split_ratios": {
        "train": TRAIN_RATIO, "val": VAL_RATIO, "test": TEST_RATIO
    },
    "label_statistics": {
        "mean": float(label_stats['label_mean']),
        "std": float(label_stats['label_std']),
        "p50": float(label_stats['label_p50']),
        "p90": float(label_stats['label_p90']),
        "p99": float(label_stats['label_p99']),
        "min": float(label_stats['label_min']),
        "max": float(label_stats['label_max']),
    },
    "stratification": {
        "enabled": ENABLE_STRATIFICATION,
        "column": STRATIFY_COL,
        "bins": STRATIFY_BINS
    },
    "iceberg_snapshot_ids": {},  # populated below
    "source_tables": [
        f"glue_catalog.ml_training.pit_features_{MODEL_NAME}"
    ]
}

# Capture Iceberg snapshot IDs for reproducibility
for split_name in ["train", "val", "test"]:
    table_name = f"{MODEL_NAME}_{split_name}_{VERSION.replace('.', '_')}"
    snapshot_df = spark.sql(
        f"SELECT snapshot_id FROM glue_catalog.ml_training.{table_name}.snapshots "
        f"ORDER BY committed_at DESC LIMIT 1"
    )
    if snapshot_df.count() > 0:
        metadata["iceberg_snapshot_ids"][split_name] = snapshot_df.collect()[0][0]

# Write metadata JSON
spark.sparkContext.parallelize([json.dumps(metadata, indent=2)]).saveAsTextFile(
    f"{output_base}/metadata/"
)

print(f"Dataset {MODEL_NAME}/{VERSION} assembled successfully")
print(f"  Train: {split_stats.get('train', 0):,}")
print(f"  Val:   {split_stats.get('val', 0):,}")
print(f"  Test:  {split_stats.get('test', 0):,}")

job.commit()
```

### Glue Data Quality Rules for Training Data

```python
# glue_data_quality_rules.py
# Applied before dataset version is published

DATA_QUALITY_RULESET = """
Rules = [
    # No null labels allowed
    Completeness "label_value" = 1.0,

    # Feature completeness threshold
    Completeness "straight_line_distance_m" >= 0.995,
    Completeness "hour_of_day" = 1.0,
    Completeness "hist_avg_orders_same_hour_dow" >= 0.99,

    # Label value ranges (ETA model: 60 seconds to 7200 seconds)
    ColumnValues "label_value" between 60 and 7200,

    # Feature value ranges
    ColumnValues "straight_line_distance_m" between 0 and 100000,
    ColumnValues "hour_of_day" between 0 and 23,
    ColumnValues "day_of_week" between 0 and 6,

    # Dataset size minimum
    RowCount >= 100000000,

    # No duplicate order_ids
    Uniqueness "order_id" = 1.0,

    # Label distribution stability (mean within 20% of historical)
    StandardDeviation "label_value" between 200 and 2000,

    # Temporal ordering validation
    CustomSql "SELECT COUNT(*) FROM primary WHERE prediction_timestamp >= outcome_timestamp" = 0
]
"""
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Production Handling

### Label Delay Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    Label Delay by Model Type                     │
├─────────────────────┬───────────────────┬───────────────────────┤
│ Model               │ Label Delay       │ Strategy              │
├─────────────────────┼───────────────────┼───────────────────────┤
│ ETA Prediction      │ 30-90 min         │ Wait for completion   │
│ Demand Forecasting  │ 1 hour            │ Hourly batch          │
│ Surge Pricing       │ 1 hour            │ Hourly batch          │
│ Driver Matching     │ 2-4 hours         │ Wait for trip rating  │
│ Fraud Detection     │ 24-72 hours       │ Delayed labeling job  │
│ Search Ranking      │ 1-7 days          │ Weekly recomputation  │
└─────────────────────┴───────────────────┴───────────────────────┘
```

**Implementation**: Each model's label generation job has a configurable `label_delay_hours`
parameter. The job only processes events older than this threshold, ensuring ground truth
has arrived before attempting label computation.

### Feature Drift Detection

```python
# Runs after each dataset version is created
def detect_feature_drift(current_version_path, baseline_version_path, threshold=0.1):
    """Compare feature distributions between dataset versions."""
    current = spark.read.parquet(current_version_path)
    baseline = spark.read.parquet(baseline_version_path)

    drift_report = []
    numeric_features = [f.name for f in current.schema.fields
                       if f.dataType.typeName() in ('double', 'float', 'integer', 'long')]

    for feature in numeric_features:
        curr_stats = current.agg(
            F.mean(feature).alias("mean"),
            F.stddev(feature).alias("std")
        ).collect()[0]

        base_stats = baseline.agg(
            F.mean(feature).alias("mean"),
            F.stddev(feature).alias("std")
        ).collect()[0]

        # Population Stability Index (PSI)
        mean_shift = abs(curr_stats['mean'] - base_stats['mean']) / (base_stats['std'] + 1e-8)

        if mean_shift > threshold:
            drift_report.append({
                'feature': feature,
                'baseline_mean': base_stats['mean'],
                'current_mean': curr_stats['mean'],
                'normalized_shift': mean_shift,
                'status': 'DRIFT_DETECTED'
            })

    return drift_report
```

### Dataset Version Management

```
Dataset Retention Policy:
- Last 7 days: All versions kept (6-hourly = 28 versions)
- Last 30 days: Daily versions kept (30 versions)
- Last 6 months: Weekly versions kept (24 versions)
- Older: Monthly versions only

Iceberg table maintenance:
- expire_snapshots older than retention policy
- rewrite_data_files for compaction weekly
- remove_orphan_files monthly
```

### Reproducibility Guarantees

Every dataset version includes:
1. **Iceberg snapshot IDs** — exact data at creation time
2. **Glue job run IDs** — which pipeline execution created it
3. **Git commit hash** — which version of pipeline code was used
4. **Input data ranges** — exact date/time ranges of source data
5. **Random seeds** — for sampling and splitting operations
6. **Feature schema version** — which feature definitions were active

To reproduce a historical dataset:
```python
# Time-travel query using Iceberg snapshot
df = spark.read.format("iceberg") \
    .option("snapshot-id", metadata['iceberg_snapshot_ids']['train']) \
    .load("glue_catalog.ml_training.eta_prediction_train_v2024_06_15_18")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Training Integration: Glue → SageMaker Pipeline

```python
# sagemaker_pipeline_integration.py
import boto3
import sagemaker
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.parameters import ParameterString
from sagemaker.processing import ScriptProcessor

# ─── Pipeline Parameters ───────────────────────────────────────────────────
model_name = ParameterString(name="ModelName", default_value="eta_prediction")
dataset_version = ParameterString(name="DatasetVersion", default_value="latest")

# ─── Step 1: Trigger Glue Pipeline (via Lambda) ───────────────────────────
glue_trigger_processor = ScriptProcessor(
    role=sagemaker.get_execution_role(),
    image_uri="<account>.dkr.ecr.us-east-1.amazonaws.com/glue-trigger:latest",
    instance_type="ml.t3.medium",
    instance_count=1,
)

trigger_step = ProcessingStep(
    name="TriggerGluePipeline",
    processor=glue_trigger_processor,
    code="trigger_glue_workflow.py",
    job_arguments=[
        "--model-name", model_name,
        "--dataset-version", dataset_version,
    ]
)

# ─── Step 2: Training ─────────────────────────────────────────────────────
from sagemaker.estimator import Estimator

estimator = Estimator(
    image_uri="763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.0-gpu-py310",
    role=sagemaker.get_execution_role(),
    instance_count=4,
    instance_type="ml.p4d.24xlarge",
    hyperparameters={
        "epochs": 50,
        "batch_size": 4096,
        "learning_rate": 0.001,
    },
    output_path="s3://ml-models/output/",
)

training_step = TrainingStep(
    name="TrainModel",
    estimator=estimator,
    inputs={
        "train": sagemaker.inputs.TrainingInput(
            s3_data=f"s3://ml-datasets/{{model_name}}/{{dataset_version}}/train/",
            content_type="application/x-parquet"
        ),
        "validation": sagemaker.inputs.TrainingInput(
            s3_data=f"s3://ml-datasets/{{model_name}}/{{dataset_version}}/val/",
            content_type="application/x-parquet"
        ),
    }
)
training_step.add_depends_on([trigger_step])

# ─── Step 3: Evaluation on held-out test set ──────────────────────────────
eval_processor = ScriptProcessor(
    role=sagemaker.get_execution_role(),
    image_uri="<account>.dkr.ecr.us-east-1.amazonaws.com/model-eval:latest",
    instance_type="ml.m5.4xlarge",
    instance_count=1,
)

eval_step = ProcessingStep(
    name="EvaluateModel",
    processor=eval_processor,
    code="evaluate_model.py",
    job_arguments=[
        "--model-artifact", training_step.properties.ModelArtifacts.S3ModelArtifacts,
        "--test-data", f"s3://ml-datasets/{{model_name}}/{{dataset_version}}/test/",
    ]
)
eval_step.add_depends_on([training_step])

# ─── Assemble Pipeline ────────────────────────────────────────────────────
pipeline = Pipeline(
    name=f"MLTrainingPipeline-{model_name}",
    parameters=[model_name, dataset_version],
    steps=[trigger_step, training_step, eval_step],
)

pipeline.upsert(role_arn=sagemaker.get_execution_role())
```

### Glue Workflow Orchestration

```python
# glue_workflow_definition.py
import boto3

glue = boto3.client('glue')

# Create workflow that chains all 5 jobs
glue.create_workflow(Name='ml-training-data-pipeline')

# Trigger chain: Job1 → Job2 → Job3 → Job4 → Job5
for i, (job_name, next_job) in enumerate([
    ('event-alignment', 'label-generation'),
    ('label-generation', 'feature-computation-ray'),
    ('feature-computation-ray', 'pit-join'),
    ('pit-join', 'dataset-assembly'),
]):
    glue.create_trigger(
        Name=f'trigger-{next_job}',
        WorkflowName='ml-training-data-pipeline',
        Type='CONDITIONAL',
        Predicate={
            'Conditions': [{
                'LogicalOperator': 'EQUALS',
                'JobName': job_name,
                'State': 'SUCCEEDED'
            }]
        },
        Actions=[{'JobName': next_job}]
    )
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Scaling: 50TB/Day Processing Strategies

### Partitioning Strategy
```
Raw Events (50TB/day):
  Partition by: event_date / hour / city_id
  Result: 24 hours × 200 cities = 4,800 partitions
  Average partition size: ~10GB (manageable per worker)

Feature Tables:
  Partition by: event_date / model_name
  Allows model-specific queries to scan only relevant data

Label Tables:
  Partition by: event_date / label_type
  Different models read only their labels
```

### Worker Allocation
```
┌─────────────────────────────────────────────────────────┐
│              Worker Allocation per Job                    │
├──────────────────────────┬──────────────────────────────┤
│ Job 1: Event Alignment   │ G.2X workers: 50-80          │
│                          │ (shuffle-heavy join)          │
├──────────────────────────┼──────────────────────────────┤
│ Job 2: Label Generation  │ G.1X workers: 20-40          │
│                          │ (aggregation-heavy)           │
├──────────────────────────┼──────────────────────────────┤
│ Job 3: Feature Compute   │ Ray workers: 80-120          │
│ (Ray)                    │ (embarrassingly parallel)     │
├──────────────────────────┼──────────────────────────────┤
│ Job 4: PIT Join          │ G.2X workers: 40-60          │
│                          │ (large join, moderate shuffle)│
├──────────────────────────┼──────────────────────────────┤
│ Job 5: Assembly          │ G.1X workers: 20-30          │
│                          │ (mostly write-heavy)          │
└──────────────────────────┴──────────────────────────────┘
```

### Performance Optimizations
- **Bucketed joins**: Pre-bucket on `order_id` to eliminate shuffle in Job 4
- **Broadcast joins**: Small dimension tables (weather, holidays) broadcast to all workers
- **Z-ordering**: Iceberg tables z-ordered on (city_id, timestamp) for locality
- **Predicate pushdown**: Glue pushes date/city filters to Iceberg scan level
- **Caching**: Intermediate results cached in S3 between jobs (not recomputed on retry)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Cost: Monthly Breakdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Monthly Cost Estimate (50TB/day)                          │
├──────────────────────────────────┬──────────────────────────────────────────┤
│ Component                        │ Monthly Cost                             │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ Glue Job 1 (Event Alignment)     │ $18,000                                 │
│   60 G.2X DPUs × 2h × 30 days   │ (60 × $0.44/h × 2 × 30)                │
│                                  │                                          │
│ Glue Job 2 (Label Generation)    │ $5,280                                  │
│   30 G.1X DPUs × 1h × 30 days   │ (30 × $0.44/h × 1 × 30 × 4 runs/day)  │
│                                  │                                          │
│ Glue Job 3 (Feature Compute Ray) │ $22,000                                 │
│   100 Ray workers × 2.5h × 30d  │ (100 × $0.44/h × 2.5 × 30)            │
│                                  │                                          │
│ Glue Job 4 (PIT Join)            │ $10,560                                 │
│   50 G.2X DPUs × 1.5h × 30d     │ (50 × $0.44/h × 1.5 × 30 × 4/day)    │
│                                  │                                          │
│ Glue Job 5 (Assembly)            │ $3,960                                  │
│   25 G.1X DPUs × 0.5h × 30d     │ (25 × $0.44/h × 0.5 × 30 × 4×6/day)  │
│                                  │                                          │
│ S3 Storage (datasets + raw)      │ $35,000                                 │
│   1.5PB total stored             │                                          │
│                                  │                                          │
│ Glue Data Catalog                │ $500                                    │
│                                  │                                          │
│ Data Quality checks              │ $1,200                                  │
│                                  │                                          │
│ CloudWatch + monitoring          │ $800                                    │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ TOTAL                            │ ~$97,300/month                           │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ Cost per model per month         │ ~$486 (200 models)                      │
│ Cost per training example        │ ~$0.000006                              │
└──────────────────────────────────┴──────────────────────────────────────────┘
```

**Cost Optimization Levers**:
- Use Flex execution (non-urgent jobs): 35% discount → saves ~$20K/month
- Compact small files weekly: reduces S3 GET costs by 40%
- Share feature computation across models: spatial/temporal features reused by 50+ models
- Incremental processing via bookmarks: only process new data, not full recomputation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Companies Using This Pattern

| Company | Scale | ML Models | Key Innovation |
|---------|-------|-----------|----------------|
| **Uber** (Michelangelo) | 100TB/day events | 1000+ | Invented point-in-time joins at scale, DSL for feature pipelines |
| **DoorDash** | 50TB/day | 200+ | Label delay management for delivery ETA, spatial features via H3 |
| **Lyft** | 40TB/day | 300+ | Real-time feature computation with offline alignment for training |
| **Instacart** | 20TB/day | 150+ | Item availability prediction, substitution models with delayed labels |
| **Grab** (Southeast Asia) | 30TB/day | 250+ | Multi-modal transport, complex sessionization across ride types |
| **Rappi** (Latin America) | 10TB/day | 80+ | Multi-vertical (food, groceries, pharmacy) unified feature store |

**Common Patterns Across All**:
- Separate label generation from feature computation (different cadences)
- Iceberg/Delta Lake for dataset versioning and time-travel
- Stratified splitting to handle long-tail distributions
- Feature drift monitoring triggers automatic retraining
- Dataset versions linked to model versions in registry for full lineage

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Takeaways

1. **Point-in-time correctness is non-negotiable** — without it, models perform great
   offline but fail in production (the #1 cause of ML model degradation)

2. **Labels and features must be decoupled** — they have different latencies, different
   update cadences, and different ownership (ML engineers vs domain experts)

3. **Dataset versioning enables rollback** — when a model regresses, you need to know
   if it was bad data or bad model code. Versioned datasets isolate the variable.

4. **Glue's sweet spot** is the heavy ETL between raw events and ML-ready datasets —
   it handles the scale (50TB) with managed infrastructure while integrating with
   the AWS ML ecosystem (SageMaker, Feature Store, Model Registry)

5. **Cost per training example is trivial** ($0.000006) — the real cost is engineering
   time to build correct pipelines. Invest in correctness validation upfront.
