# Recommendation System Data Pipeline at Netflix/Spotify Scale

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 300M Users × 50M Items → Personalized Recommendations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

A streaming/e-commerce platform must deliver personalized recommendations to every
user on every surface (homepage, search, notifications, emails). The recommendation
engine requires structured training data derived from raw behavioral signals.

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PLATFORM SCALE                                    │
├─────────────────────────────────┬───────────────────────────────────┤
│  Active Users                   │  300 Million                      │
│  Content Items                  │  50 Million                       │
│  Interactions/Day               │  10 Billion                       │
│  Features per User-Item Pair    │  1,000+                           │
│  Models in Production           │  200+ (per surface/region)        │
│  Training Frequency             │  Daily (full) + Hourly (delta)    │
│  Serving Latency Requirement    │  < 50ms p99                       │
│  User Profile Size              │  ~2KB average                     │
│  Item Embedding Dimensions      │  256-512                          │
│  A/B Tests Running              │  50+ concurrent                   │
└─────────────────────────────────┴───────────────────────────────────┘
```

### Why Batch Data Preparation is Critical

Even real-time serving systems depend on batch-computed artifacts:

1. **User embeddings** - Computed from full interaction history (not just last session)
2. **Item popularity scores** - Require aggregation across all users over time windows
3. **Collaborative signals** - Matrix factorization needs the full interaction matrix
4. **Feature crosses** - User×Item affinity scores computed offline
5. **Training labels** - Positive/negative pairs assembled from historical data
6. **Evaluation sets** - Time-based splits for offline model evaluation

```
Real-time signals (last 5 min)  ──┐
                                   ├──→  Inference Engine  ──→  Recommendations
Batch-computed features (daily) ──┘
        ↑
        │
   AWS Glue Pipeline (this document)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Approach 1: Computing User Profiles in Application DB

```
Problem: SELECT user_id, array_agg(item_id) FROM interactions
         GROUP BY user_id  -- 300M groups × 10B rows = DB meltdown

- Locks production tables during aggregation
- No separation between OLTP and analytical workloads
- Cannot compute complex features (TF-IDF, decay functions)
- Query takes 48+ hours on RDS, blocks writes
```

### Approach 2: Single-Node Matrix Factorization

```
Problem: 300M × 50M interaction matrix = 15 petabytes dense (impossible)
         Even sparse: 10B non-zero entries × 16 bytes = 160GB in memory

- Exceeds single machine memory
- No fault tolerance (restart from scratch on failure)
- Cannot parallelize ALS iterations
- Feature engineering bottlenecked on one CPU
```

### Approach 3: Raw Interactions Without Aggregation

```
Problem: Training on 10B raw events/day directly

- Model training takes 72+ hours (too slow for daily refresh)
- Storage: 10B × 500 bytes = 5TB/day raw → 1.8PB/year
- No signal-to-noise improvement (duplicate clicks, bots, errors)
- Training instability from noisy labels
```

### Approach 4: No Dataset Versioning

```
Problem: "The model degraded—what changed in training data?"

- Cannot reproduce previous model results
- No rollback capability when data pipeline has bugs
- Impossible to debug model regressions
- Compliance issues (GDPR right to explanation)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                              │
├────────────────┬────────────────┬─────────────────┬────────────────────────────┤
│  Kafka         │  DynamoDB      │  RDS (CDC)      │  S3 Content                │
│  Click Events  │  Streams       │  Explicit       │  Catalog                   │
│  10B/day       │  Watch/Listen  │  Ratings        │  Metadata +                │
│  (implicit)    │  History       │  Reviews        │  Descriptions              │
└───────┬────────┴───────┬────────┴────────┬────────┴─────────────┬──────────────┘
        │                │                 │                      │
        ▼                ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AWS GLUE PIPELINE                                        │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Job 1: INTERACTION AGGREGATION                                          │   │
│  │  - Merge implicit (clicks, views, skips) + explicit (ratings, likes)     │   │
│  │  - Deduplicate and sessionize                                            │   │
│  │  - Compute implicit feedback scores (dwell time → relevance)             │   │
│  │  - Bot/fraud filtering                                                   │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────▼───────────────────────────────────────┐   │
│  │  Job 2: USER PROFILE FEATURE COMPUTATION                                 │   │
│  │  - Genre/category affinity vectors                                        │   │
│  │  - Temporal patterns (day-of-week, time-of-day preferences)              │   │
│  │  - Recency-weighted engagement scores                                     │   │
│  │  - User embedding from interaction history                                │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────▼───────────────────────────────────────┐   │
│  │  Job 3: ITEM FEATURE ENRICHMENT                                          │   │
│  │  - Content metadata join (genre, creator, duration, language)             │   │
│  │  - TF-IDF on descriptions/titles                                          │   │
│  │  - Popularity metrics (views, trending score, decay-weighted)            │   │
│  │  - Freshness score                                                        │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────▼───────────────────────────────────────┐   │
│  │  Job 4: TRAINING DATASET ASSEMBLY                                        │   │
│  │  - Positive pairs (user interacted with item)                            │   │
│  │  - Negative sampling (items user did NOT interact with)                  │   │
│  │  - Feature vector construction (user features ⊕ item features)           │   │
│  │  - Label assignment (click, complete, skip, rating)                      │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────▼───────────────────────────────────────┐   │
│  │  Job 5: EVALUATION DATASET PREPARATION                                   │   │
│  │  - Time-based train/validation/test splits                               │   │
│  │  - Per-user holdout sets                                                  │   │
│  │  - A/B test cohort segmentation                                          │   │
│  │  - Metric computation (NDCG, MAP, Hit Rate baselines)                    │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
└─────────────────────────────────────┼───────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT & DOWNSTREAM                                      │
│                                                                                 │
│  ┌───────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  S3 (Iceberg) │───▶│ SageMaker        │───▶│ Model Registry               │  │
│  │  Versioned    │    │ Training Jobs     │    │ (version, metrics, lineage)  │  │
│  │  Datasets     │    └──────────────────┘    └──────────────┬───────────────┘  │
│  └───────────────┘                                           │                  │
│                                                              ▼                  │
│  ┌───────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Feature Store │───▶│ Inference        │◀───│ Real-time Features           │  │
│  │  (offline)    │    │ Endpoint         │    │ (Kinesis → Lambda)           │  │
│  └───────────────┘    └────────┬─────────┘    └──────────────────────────────┘  │
│                                │                                                │
└────────────────────────────────┼────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FEEDBACK LOOP                                               │
│                                                                                 │
│  User interactions with recommendations → Kafka → Glue Job 1 (next cycle)      │
│  A/B test assignments + outcomes → Glue → Model comparison metrics              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### DynamicFrame for Semi-Structured Interaction Data

Interaction events have varying schemas (click events differ from watch events).
DynamicFrame handles schema inconsistency without upfront schema definition.

```
Click event:    {user_id, item_id, timestamp, position, surface}
Watch event:    {user_id, item_id, timestamp, duration, completion_pct, device}
Rating event:   {user_id, item_id, timestamp, rating, review_text}
Skip event:     {user_id, item_id, timestamp, skip_after_seconds}
```

### Glue Crawlers for Content Partitions

New content arrives in S3 partitioned by `content_type/language/upload_date`.
Crawlers automatically discover new partitions without manual ALTER TABLE.

### Job Bookmarks for Incremental Processing

Each daily run processes only new interactions since last bookmark.
Prevents reprocessing 10B events when only 10B new ones arrive.

### Glue Schema Registry

Event producers register schemas; Glue validates incoming data against
registered schemas, catching breaking changes before they corrupt training data.

### G.2X Workers for Matrix Operations

User profile computation and feature crosses require high-memory workers.
G.2X provides 32 vCPUs, 128GB RAM per worker for large broadcast joins.

### Glue Workflows for DAG Orchestration

```
┌─────────────┐     ┌─────────────┐
│   Job 1     │────▶│   Job 2     │──┐
│ Interactions│     │ User Feats  │  │   ┌─────────────┐    ┌─────────────┐
└─────────────┘     └─────────────┘  ├──▶│   Job 4     │───▶│   Job 5     │
                    ┌─────────────┐  │   │ Train Data  │    │ Eval Data   │
                    │   Job 3     │──┘   └─────────────┘    └─────────────┘
                    │ Item Feats  │
                    └─────────────┘
```

Jobs 2 and 3 run in parallel after Job 1 completes. Job 4 depends on both.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job 1: Interaction Aggregation

```python
# job1_interaction_aggregation.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, FloatType, LongType

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'run_date', 'interactions_database', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']

# ─── Read interaction events from multiple sources using DynamicFrames ───

# Kafka-sourced click events (already landed in S3 by Firehose)
clicks_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=args['interactions_database'],
    table_name="click_events",
    transformation_ctx="clicks_dyf",
    push_down_predicate=f"partition_date = '{run_date}'"
)

# DynamoDB streams - watch/listen history
watch_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=args['interactions_database'],
    table_name="watch_history",
    transformation_ctx="watch_dyf",
    push_down_predicate=f"partition_date = '{run_date}'"
)

# RDS CDC - explicit ratings
ratings_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=args['interactions_database'],
    table_name="ratings_cdc",
    transformation_ctx="ratings_dyf",
    push_down_predicate=f"partition_date = '{run_date}'"
)

# ─── Resolve schema inconsistencies with DynamicFrame ───

# Click events may have nested 'context' field with varying structure
clicks_resolved = clicks_dyf.resolveChoice(
    specs=[
        ('context.position', 'cast:int'),
        ('context.surface', 'cast:string'),
        ('timestamp', 'cast:long')
    ]
)

# ─── Convert to DataFrames for complex transformations ───

clicks_df = clicks_resolved.toDF()
watch_df = watch_dyf.toDF()
ratings_df = ratings_dyf.toDF()

# ─── Compute implicit feedback scores ───

# Click signal: position-aware (higher position = stronger signal)
clicks_scored = clicks_df.withColumn(
    "implicit_score",
    F.when(F.col("position") <= 3, 1.0)
     .when(F.col("position") <= 10, 0.7)
     .otherwise(0.4)
).withColumn(
    "interaction_type", F.lit("click")
).select("user_id", "item_id", "timestamp", "implicit_score", "interaction_type")

# Watch signal: completion-weighted
watch_scored = watch_df.withColumn(
    "implicit_score",
    F.when(F.col("completion_pct") >= 0.9, 5.0)    # Completed
     .when(F.col("completion_pct") >= 0.5, 3.0)    # Watched majority
     .when(F.col("completion_pct") >= 0.2, 1.0)    # Sampled
     .otherwise(0.1)                                 # Bounced
).withColumn(
    "interaction_type", F.lit("watch")
).select("user_id", "item_id", "timestamp", "implicit_score", "interaction_type")

# Explicit ratings: normalized to same scale
ratings_scored = ratings_df.withColumn(
    "implicit_score",
    (F.col("rating") / 5.0) * 5.0  # Scale 1-5 rating to 0-5 score
).withColumn(
    "interaction_type", F.lit("rating")
).select("user_id", "item_id", "timestamp", "implicit_score", "interaction_type")

# ─── Union all interaction types ───

all_interactions = clicks_scored.union(watch_scored).union(ratings_scored)

# ─── Sessionization ───

session_window = Window.partitionBy("user_id").orderBy("timestamp")

sessionized = all_interactions.withColumn(
    "prev_timestamp", F.lag("timestamp").over(session_window)
).withColumn(
    "time_gap_seconds",
    (F.col("timestamp") - F.col("prev_timestamp")) / 1000
).withColumn(
    "new_session",
    F.when(F.col("time_gap_seconds") > 1800, 1).otherwise(0)  # 30 min gap
).withColumn(
    "session_id",
    F.concat(
        F.col("user_id"),
        F.lit("_"),
        F.sum("new_session").over(session_window).cast("string")
    )
)

# ─── Bot/Fraud Filtering ───

# Users with >10000 interactions/day are likely bots
user_daily_counts = all_interactions.groupBy("user_id").agg(
    F.count("*").alias("daily_interactions")
)

valid_users = user_daily_counts.filter(
    (F.col("daily_interactions") < 10000) &
    (F.col("daily_interactions") > 1)  # Also filter single-interaction users
)

filtered_interactions = sessionized.join(
    valid_users.select("user_id"),
    on="user_id",
    how="inner"
)

# ─── Aggregate to user-item level ───

user_item_agg = filtered_interactions.groupBy("user_id", "item_id").agg(
    F.sum("implicit_score").alias("total_score"),
    F.count("*").alias("interaction_count"),
    F.max("timestamp").alias("last_interaction_ts"),
    F.min("timestamp").alias("first_interaction_ts"),
    F.collect_set("interaction_type").alias("interaction_types"),
    F.countDistinct("session_id").alias("num_sessions")
)

# ─── Write aggregated interactions ───

output_dyf = DynamicFrame.fromDF(user_item_agg, glueContext, "output_dyf")

glueContext.write_dynamic_frame.from_options(
    frame=output_dyf,
    connection_type="s3",
    format="iceberg",
    connection_options={
        "path": f"{args['output_path']}/aggregated_interactions",
        "catalog": "glue_catalog",
        "database": "recommendation_pipeline",
        "table": "user_item_interactions",
        "partition_by": ["run_date"],
        "additional_options": {
            "write.metadata.delete-after-commit.enabled": "true",
            "write.metadata.previous-versions-max": "10"
        }
    }
)

job.commit()
```

### Job 2: User Profile Feature Computation

```python
# job2_user_feature_computation.py
import sys
import numpy as np
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import ArrayType, FloatType
from pyspark.ml.feature import Normalizer
from pyspark.ml.linalg import Vectors, VectorUDT

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'run_date', 'output_path', 'lookback_days'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']
lookback_days = int(args['lookback_days'])  # e.g., 90 days

# ─── Read aggregated interactions (output of Job 1) ───

interactions_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="recommendation_pipeline",
    table_name="user_item_interactions",
    transformation_ctx="interactions_dyf",
    push_down_predicate=f"run_date >= date_sub('{run_date}', {lookback_days})"
)

interactions_df = interactions_dyf.toDF()

# Read item metadata for genre/category mapping
items_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="content_catalog",
    table_name="items",
    transformation_ctx="items_dyf"
)
items_df = items_dyf.toDF()

# ─── Genre/Category Affinity Vectors ───

# Join interactions with item genres
interactions_with_genre = interactions_df.join(
    items_df.select("item_id", "genres", "category", "language"),
    on="item_id",
    how="inner"
)

# Explode genres array and compute per-genre scores
genre_scores = interactions_with_genre.withColumn(
    "genre", F.explode("genres")
).groupBy("user_id", "genre").agg(
    F.sum("total_score").alias("genre_score"),
    F.count("*").alias("genre_interaction_count")
)

# Pivot to create genre affinity vector per user
# Get top 50 genres
top_genres = genre_scores.groupBy("genre").agg(
    F.sum("genre_interaction_count").alias("total")
).orderBy(F.desc("total")).limit(50).select("genre").collect()
top_genre_list = [row.genre for row in top_genres]

genre_pivot = genre_scores.filter(
    F.col("genre").isin(top_genre_list)
).groupBy("user_id").pivot("genre", top_genre_list).agg(
    F.coalesce(F.sum("genre_score"), F.lit(0.0))
).na.fill(0.0)

# Normalize genre vectors to unit length
genre_columns = [c for c in genre_pivot.columns if c != "user_id"]
genre_pivot = genre_pivot.withColumn(
    "genre_norm",
    F.sqrt(sum(F.col(c) ** 2 for c in genre_columns))
)
for c in genre_columns:
    genre_pivot = genre_pivot.withColumn(
        f"genre_{c}_norm",
        F.when(F.col("genre_norm") > 0, F.col(c) / F.col("genre_norm")).otherwise(0.0)
    )

# ─── Temporal Patterns ───

# Day-of-week preference (7-dimensional vector)
temporal_df = interactions_df.withColumn(
    "day_of_week", F.dayofweek(F.from_unixtime(F.col("last_interaction_ts") / 1000))
).withColumn(
    "hour_of_day", F.hour(F.from_unixtime(F.col("last_interaction_ts") / 1000))
)

dow_pattern = temporal_df.groupBy("user_id").pivot(
    "day_of_week", list(range(1, 8))
).agg(F.sum("total_score")).na.fill(0.0)

# Time-of-day buckets: morning(6-12), afternoon(12-18), evening(18-24), night(0-6)
temporal_df = temporal_df.withColumn(
    "time_bucket",
    F.when((F.col("hour_of_day") >= 6) & (F.col("hour_of_day") < 12), "morning")
     .when((F.col("hour_of_day") >= 12) & (F.col("hour_of_day") < 18), "afternoon")
     .when((F.col("hour_of_day") >= 18), "evening")
     .otherwise("night")
)

tod_pattern = temporal_df.groupBy("user_id").pivot(
    "time_bucket", ["morning", "afternoon", "evening", "night"]
).agg(F.sum("total_score")).na.fill(0.0)

# ─── Recency-Weighted Engagement ───

# Exponential decay: score * exp(-lambda * days_since_interaction)
decay_lambda = 0.05  # Half-life ~14 days

recency_df = interactions_df.withColumn(
    "days_ago",
    F.datediff(F.lit(run_date), F.from_unixtime(F.col("last_interaction_ts") / 1000))
).withColumn(
    "decayed_score",
    F.col("total_score") * F.exp(-decay_lambda * F.col("days_ago"))
)

user_recency_features = recency_df.groupBy("user_id").agg(
    F.sum("decayed_score").alias("recency_weighted_engagement"),
    F.avg("days_ago").alias("avg_recency_days"),
    F.min("days_ago").alias("days_since_last_interaction"),
    F.count("*").alias("total_items_interacted"),
    F.avg("total_score").alias("avg_interaction_intensity"),
    F.stddev("total_score").alias("interaction_intensity_stddev")
)

# ─── User Activity Level Features ───

activity_features = interactions_df.groupBy("user_id").agg(
    F.sum("interaction_count").alias("total_interactions"),
    F.countDistinct("item_id").alias("unique_items"),
    F.avg("num_sessions").alias("avg_sessions_per_item"),
    F.sum(
        F.when(F.array_contains(F.col("interaction_types"), "rating"), 1).otherwise(0)
    ).alias("explicit_rating_count")
).withColumn(
    "exploration_ratio",
    F.col("unique_items") / F.col("total_interactions")
)

# ─── Assemble User Feature Vector ───

user_features = user_recency_features.join(activity_features, on="user_id", how="outer") \
    .join(dow_pattern, on="user_id", how="outer") \
    .join(tod_pattern, on="user_id", how="outer") \
    .join(
        genre_pivot.select(
            "user_id",
            *[f"genre_{c}_norm" for c in genre_columns]
        ),
        on="user_id",
        how="outer"
    ).na.fill(0.0)

# ─── Write to Feature Store and S3 ───

user_features_dyf = DynamicFrame.fromDF(user_features, glueContext, "user_features_dyf")

# Write to S3 Iceberg for training
glueContext.write_dynamic_frame.from_options(
    frame=user_features_dyf,
    connection_type="s3",
    format="iceberg",
    connection_options={
        "path": f"{args['output_path']}/user_features",
        "catalog": "glue_catalog",
        "database": "recommendation_pipeline",
        "table": "user_features",
        "partition_by": ["run_date"]
    }
)

# Write to SageMaker Feature Store (offline)
glueContext.write_dynamic_frame.from_options(
    frame=user_features_dyf,
    connection_type="custom.spark",
    connection_options={
        "className": "sagemaker.spark.FeatureStoreManager",
        "featureGroupName": "user-recommendation-features",
        "eventTimeColumn": "run_date",
        "recordIdentifierColumn": "user_id"
    }
)

job.commit()
```

### Job 3: Item Feature Enrichment

```python
# job3_item_feature_enrichment.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.ml.feature import HashingTF, IDF, Tokenizer, StopWordsRemover

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'run_date', 'output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']

# ─── Read content catalog ───

catalog_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="content_catalog",
    table_name="items",
    transformation_ctx="catalog_dyf"
)

# Resolve choice for fields that may be string or array
catalog_dyf = catalog_dyf.resolveChoice(
    specs=[
        ('duration_seconds', 'cast:int'),
        ('release_year', 'cast:int')
    ]
)

catalog_df = catalog_dyf.toDF()

# ─── Read aggregated interactions for popularity ───

interactions_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="recommendation_pipeline",
    table_name="user_item_interactions",
    transformation_ctx="interactions_dyf",
    push_down_predicate=f"run_date = '{run_date}'"
)
interactions_df = interactions_dyf.toDF()

# ─── TF-IDF on Item Descriptions ───

# Tokenize descriptions
tokenizer = Tokenizer(inputCol="description", outputCol="words_raw")
catalog_tokenized = tokenizer.transform(
    catalog_df.filter(F.col("description").isNotNull())
)

# Remove stop words
remover = StopWordsRemover(inputCol="words_raw", outputCol="words_clean")
catalog_cleaned = remover.transform(catalog_tokenized)

# Hashing TF (256 features for efficiency at scale)
hashing_tf = HashingTF(inputCol="words_clean", outputCol="tf_features", numFeatures=256)
tf_df = hashing_tf.transform(catalog_cleaned)

# IDF
idf = IDF(inputCol="tf_features", outputCol="tfidf_features")
idf_model = idf.fit(tf_df)
tfidf_df = idf_model.transform(tf_df)

# ─── Popularity Metrics with Time Decay ───

# Aggregate interaction counts per item
item_popularity = interactions_df.groupBy("item_id").agg(
    F.countDistinct("user_id").alias("unique_users"),
    F.sum("total_score").alias("total_engagement"),
    F.avg("total_score").alias("avg_engagement_per_user"),
    F.max("last_interaction_ts").alias("latest_interaction")
)

# Trending score: interactions in last 7 days vs last 30 days
# (Requires reading multiple date partitions - simplified here)
item_popularity = item_popularity.withColumn(
    "popularity_percentile",
    F.percent_rank().over(Window.orderBy("total_engagement"))
)

# ─── Freshness Score ───

catalog_with_freshness = catalog_df.withColumn(
    "days_since_release",
    F.datediff(F.lit(run_date), F.col("release_date"))
).withColumn(
    "freshness_score",
    F.exp(-0.01 * F.col("days_since_release"))  # Exponential decay
)

# ─── Content Features ───

content_features = catalog_with_freshness.select(
    "item_id",
    "genres",
    "category",
    "language",
    "duration_seconds",
    "release_year",
    "creator_id",
    "freshness_score",
    "days_since_release"
).withColumn(
    "num_genres", F.size("genres")
).withColumn(
    "is_new_release",
    F.when(F.col("days_since_release") <= 30, 1).otherwise(0)
).withColumn(
    "duration_bucket",
    F.when(F.col("duration_seconds") < 300, "short")
     .when(F.col("duration_seconds") < 1800, "medium")
     .when(F.col("duration_seconds") < 7200, "long")
     .otherwise("very_long")
)

# ─── Join all item features ───

item_features = content_features.join(
    item_popularity, on="item_id", how="left"
).join(
    tfidf_df.select("item_id", "tfidf_features"), on="item_id", how="left"
).na.fill({
    "unique_users": 0,
    "total_engagement": 0.0,
    "avg_engagement_per_user": 0.0,
    "popularity_percentile": 0.0
})

# ─── Write enriched item features ───

item_features_dyf = DynamicFrame.fromDF(item_features, glueContext, "item_features_dyf")

glueContext.write_dynamic_frame.from_options(
    frame=item_features_dyf,
    connection_type="s3",
    format="iceberg",
    connection_options={
        "path": f"{args['output_path']}/item_features",
        "catalog": "glue_catalog",
        "database": "recommendation_pipeline",
        "table": "item_features",
        "partition_by": ["run_date"]
    }
)

job.commit()
```

### Job 4: Training Dataset Assembly with Negative Sampling

```python
# job4_training_dataset_assembly.py
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
    'JOB_NAME', 'run_date', 'output_path', 'negative_ratio'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']
negative_ratio = int(args['negative_ratio'])  # e.g., 4 negatives per positive

# ─── Read user features, item features, interactions ───

user_features = spark.read.format("iceberg").load(
    "glue_catalog.recommendation_pipeline.user_features"
).filter(F.col("run_date") == run_date)

item_features = spark.read.format("iceberg").load(
    "glue_catalog.recommendation_pipeline.item_features"
).filter(F.col("run_date") == run_date)

interactions = spark.read.format("iceberg").load(
    "glue_catalog.recommendation_pipeline.user_item_interactions"
).filter(F.col("run_date") == run_date)

# ─── Positive Examples ───

# Users who interacted with items (label = 1)
positives = interactions.select(
    "user_id", "item_id", "total_score"
).withColumn("label", F.lit(1.0)).withColumn(
    # Confidence weight: higher score = more confident positive
    "sample_weight",
    F.log1p(F.col("total_score"))
)

num_positives = positives.count()
print(f"Positive examples: {num_positives:,}")

# ─── Negative Sampling ───

# Strategy: Sample items the user did NOT interact with,
# weighted by item popularity (popularity-based negative sampling)

# Get all item IDs with their popularity weight
all_items = item_features.select(
    "item_id",
    F.col("popularity_percentile").alias("sampling_weight")
).withColumn(
    # Popularity-sampled negatives (avoids sampling only obscure items)
    "sampling_weight", F.pow(F.col("sampling_weight"), 0.75)  # Smoothed
)

# For each user, get their positive items
user_positive_items = interactions.groupBy("user_id").agg(
    F.collect_set("item_id").alias("positive_items")
)

# Sample negatives: cross join users with candidate items, filter out positives
# Efficient approach: sample globally then filter
num_negatives_needed = num_positives * negative_ratio

# Get candidate negative items (sample more than needed, then filter)
candidate_negatives = user_positive_items.crossJoin(
    all_items.sample(fraction=0.001)  # Sample 0.1% of items per user
).filter(
    ~F.array_contains(F.col("positive_items"), F.col("item_id"))
).select(
    "user_id", "item_id"
).withColumn("label", F.lit(0.0)).withColumn(
    "total_score", F.lit(0.0)
).withColumn(
    "sample_weight", F.lit(1.0)
)

# Limit negatives to desired ratio
negatives = candidate_negatives.orderBy(F.rand(seed=42)).limit(num_negatives_needed)

# ─── Combine Positives and Negatives ───

training_pairs = positives.select(
    "user_id", "item_id", "label", "sample_weight"
).union(
    negatives.select("user_id", "item_id", "label", "sample_weight")
)

# ─── Join with Feature Vectors ───

# Select relevant user feature columns (avoid exploding width)
user_feature_cols = [c for c in user_features.columns
                     if c not in ("user_id", "run_date")]

training_data = training_pairs.join(
    user_features.drop("run_date"),
    on="user_id",
    how="inner"
).join(
    item_features.select(
        "item_id", "popularity_percentile", "freshness_score",
        "num_genres", "duration_seconds", "is_new_release",
        "unique_users", "avg_engagement_per_user"
    ),
    on="item_id",
    how="inner"
)

# ─── Add interaction context features ───

training_data = training_data.withColumn(
    "user_item_genre_overlap",
    F.size(F.array_intersect(
        F.col("user_top_genres"),  # From user features
        F.col("item_genres")       # From item features
    ))
)

# ─── Shuffle and Write ───

training_data = training_data.orderBy(F.rand(seed=123))

# Write versioned training dataset
training_data.writeTo(
    "glue_catalog.recommendation_pipeline.training_data"
).tableProperty("write.format.default", "parquet").option(
    "fanout-enabled", "true"
).overwritePartitions()

# Also write metadata
metadata = spark.createDataFrame([{
    "run_date": run_date,
    "num_positives": num_positives,
    "num_negatives": num_negatives_needed,
    "negative_ratio": negative_ratio,
    "num_users": training_data.select("user_id").distinct().count(),
    "num_items": training_data.select("item_id").distinct().count(),
    "num_features": len(training_data.columns) - 4  # Exclude id, label, weight cols
}])

metadata.write.mode("append").format("iceberg").saveAsTable(
    "glue_catalog.recommendation_pipeline.training_metadata"
)

job.commit()
```

### Job 5: Evaluation Dataset Preparation

```python
# job5_evaluation_dataset.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'run_date', 'output_path', 'train_days', 'val_days', 'test_days'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

run_date = args['run_date']
train_days = int(args['train_days'])  # e.g., 60
val_days = int(args['val_days'])      # e.g., 7
test_days = int(args['test_days'])    # e.g., 7

# ─── Time-Based Split ───
# Train: day -74 to day -14
# Validation: day -14 to day -7
# Test: day -7 to day 0 (run_date)

interactions = spark.read.format("iceberg").load(
    "glue_catalog.recommendation_pipeline.user_item_interactions"
)

interactions = interactions.withColumn(
    "interaction_date",
    F.to_date(F.from_unixtime(F.col("last_interaction_ts") / 1000))
).withColumn(
    "days_before_run",
    F.datediff(F.lit(run_date), F.col("interaction_date"))
)

train_set = interactions.filter(
    (F.col("days_before_run") >= val_days + test_days) &
    (F.col("days_before_run") < train_days + val_days + test_days)
).withColumn("split", F.lit("train"))

val_set = interactions.filter(
    (F.col("days_before_run") >= test_days) &
    (F.col("days_before_run") < val_days + test_days)
).withColumn("split", F.lit("validation"))

test_set = interactions.filter(
    F.col("days_before_run") < test_days
).withColumn("split", F.lit("test"))

# ─── Per-User Holdout (for ranking metrics) ───

# For each user in test set, hold out their last interaction
user_window = Window.partitionBy("user_id").orderBy(F.desc("last_interaction_ts"))

test_with_rank = test_set.withColumn(
    "interaction_rank", F.row_number().over(user_window)
)

# Last interaction per user = ground truth for evaluation
ground_truth = test_with_rank.filter(F.col("interaction_rank") == 1).select(
    "user_id", "item_id", "total_score"
).withColumnRenamed("item_id", "ground_truth_item")

# ─── A/B Test Cohort Segmentation ───

# Read A/B test assignments
ab_assignments = spark.read.format("iceberg").load(
    "glue_catalog.recommendation_pipeline.ab_test_assignments"
).filter(F.col("test_date") == run_date)

# Join test set with A/B cohorts
test_with_cohort = test_set.join(
    ab_assignments.select("user_id", "experiment_id", "variant"),
    on="user_id",
    how="left"
)

# ─── Compute Baseline Metrics ───

# Popularity baseline: recommend most popular items
popular_items = train_set.groupBy("item_id").agg(
    F.countDistinct("user_id").alias("popularity")
).orderBy(F.desc("popularity")).limit(100)

# Hit rate at K for popularity baseline
top_k = 10
popular_item_list = [row.item_id for row in popular_items.limit(top_k).collect()]

baseline_hits = ground_truth.withColumn(
    "popularity_hit",
    F.when(F.col("ground_truth_item").isin(popular_item_list), 1).otherwise(0)
)

baseline_hit_rate = baseline_hits.agg(
    F.avg("popularity_hit").alias("popularity_baseline_hr@10")
).collect()[0][0]

print(f"Popularity baseline Hit Rate@{top_k}: {baseline_hit_rate:.4f}")

# ─── Write Evaluation Datasets ───

for split_name, split_df in [("train", train_set), ("validation", val_set), ("test", test_set)]:
    split_df.write.mode("overwrite").format("iceberg").option(
        "overwrite-mode", "dynamic"
    ).saveAsTable(
        f"glue_catalog.recommendation_pipeline.eval_{split_name}"
    )

ground_truth.write.mode("overwrite").format("iceberg").saveAsTable(
    "glue_catalog.recommendation_pipeline.eval_ground_truth"
)

# Write evaluation metadata
eval_metadata = spark.createDataFrame([{
    "run_date": run_date,
    "train_size": train_set.count(),
    "val_size": val_set.count(),
    "test_size": test_set.count(),
    "num_test_users": ground_truth.count(),
    "popularity_baseline_hr10": float(baseline_hit_rate),
    "train_period": f"{train_days} days",
    "val_period": f"{val_days} days",
    "test_period": f"{test_days} days"
}])

eval_metadata.write.mode("append").format("iceberg").saveAsTable(
    "glue_catalog.recommendation_pipeline.eval_metadata"
)

job.commit()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Cold Start Problem Data Preparation

```python
# Cold start: new users with < 5 interactions, new items with < 10 interactions

def prepare_cold_start_features(interactions_df, user_features_df, item_features_df, run_date):
    """
    For cold-start users: use demographic/contextual features only.
    For cold-start items: use content features only (no collaborative signal).
    """

    # Identify cold-start users
    user_interaction_counts = interactions_df.groupBy("user_id").agg(
        F.count("*").alias("total_interactions")
    )

    cold_users = user_interaction_counts.filter(F.col("total_interactions") < 5)
    warm_users = user_interaction_counts.filter(F.col("total_interactions") >= 5)

    # Cold users get default feature values (population averages)
    population_averages = user_features_df.agg(
        *[F.avg(c).alias(c) for c in user_features_df.columns
          if c not in ("user_id", "run_date")]
    ).collect()[0]

    # Cold-start items: use content-based features, zero out collaborative features
    cold_items = item_features_df.filter(
        (F.col("unique_users") < 10) | (F.col("unique_users").isNull())
    ).withColumn("popularity_percentile", F.lit(0.0)) \
     .withColumn("avg_engagement_per_user", F.lit(0.0)) \
     .withColumn("is_cold_start_item", F.lit(1))

    return cold_users, cold_items
```

### Popularity Bias Correction

```python
def apply_popularity_debiasing(training_data, item_features):
    """
    Correct for popularity bias in training data using inverse propensity scoring.
    Popular items are overrepresented in positive interactions.
    """

    # Compute propensity: P(item observed | item exists)
    total_users = training_data.select("user_id").distinct().count()

    item_propensity = item_features.select(
        "item_id",
        (F.col("unique_users") / total_users).alias("propensity")
    ).withColumn(
        # Clip propensity to avoid extreme weights
        "propensity_clipped",
        F.greatest(F.col("propensity"), F.lit(0.001))
    ).withColumn(
        "ips_weight",
        1.0 / F.col("propensity_clipped")
    ).withColumn(
        # Cap weights to prevent instability
        "ips_weight_capped",
        F.least(F.col("ips_weight"), F.lit(100.0))
    )

    # Apply IPS weights to training examples
    debiased_training = training_data.join(
        item_propensity.select("item_id", "ips_weight_capped"),
        on="item_id",
        how="left"
    ).withColumn(
        "sample_weight",
        F.col("sample_weight") * F.coalesce(F.col("ips_weight_capped"), F.lit(1.0))
    )

    return debiased_training
```

### Dataset Versioning for Reproducibility

```python
def write_versioned_dataset(df, table_name, run_date, version_metadata):
    """
    Write dataset with full lineage tracking using Iceberg snapshots.
    Each run creates a new snapshot that can be time-traveled to.
    """

    # Write data (Iceberg automatically creates a new snapshot)
    df.writeTo(f"glue_catalog.recommendation_pipeline.{table_name}") \
      .tableProperty("write.format.default", "parquet") \
      .tableProperty("write.parquet.compression-codec", "zstd") \
      .overwritePartitions()

    # Record version metadata for explicit tracking
    spark.sql(f"""
        INSERT INTO glue_catalog.recommendation_pipeline.dataset_versions
        VALUES (
            '{table_name}',
            '{run_date}',
            current_timestamp(),
            '{version_metadata["git_commit"]}',
            '{version_metadata["pipeline_version"]}',
            {version_metadata["row_count"]},
            '{version_metadata["schema_hash"]}'
        )
    """)

    # Tag the snapshot for easy retrieval
    spark.sql(f"""
        ALTER TABLE glue_catalog.recommendation_pipeline.{table_name}
        CREATE TAG `v_{run_date.replace('-', '')}`
        AS OF VERSION {version_metadata["snapshot_id"]}
    """)
```

### Feature Store Integration

```python
def sync_to_feature_store(user_features_df, item_features_df, feature_group_config):
    """
    Sync computed features to SageMaker Feature Store for online serving.
    Offline store (S3/Iceberg) used for training, online store for inference.
    """
    import boto3
    from sagemaker.feature_store.feature_group import FeatureGroup

    # User features → online store (for real-time inference)
    user_features_df.write.format("sagemaker-feature-store") \
        .option("featureGroupName", "user-reco-features-v2") \
        .option("targetStores", "OnlineStore,OfflineStore") \
        .option("eventTimeColumn", "run_date") \
        .option("recordIdentifierColumn", "user_id") \
        .mode("append") \
        .save()

    # Item features → online store
    item_features_df.write.format("sagemaker-feature-store") \
        .option("featureGroupName", "item-reco-features-v2") \
        .option("targetStores", "OnlineStore,OfflineStore") \
        .option("eventTimeColumn", "run_date") \
        .option("recordIdentifierColumn", "item_id") \
        .mode("append") \
        .save()
```

### Handling Content Catalog Updates

```python
def handle_catalog_updates(current_catalog, previous_catalog):
    """
    Detect and handle content catalog changes:
    - New items: mark as cold-start
    - Removed items: exclude from training positives
    - Updated metadata: re-compute item features
    """

    new_items = current_catalog.join(
        previous_catalog.select("item_id"),
        on="item_id",
        how="left_anti"
    )

    removed_items = previous_catalog.join(
        current_catalog.select("item_id"),
        on="item_id",
        how="left_anti"
    )

    # Items with changed metadata
    updated_items = current_catalog.alias("curr").join(
        previous_catalog.alias("prev"),
        on="item_id",
        how="inner"
    ).filter(
        (F.col("curr.description") != F.col("prev.description")) |
        (F.col("curr.genres") != F.col("prev.genres")) |
        (F.col("curr.category") != F.col("prev.category"))
    ).select("curr.*")

    print(f"New items: {new_items.count()}, Removed: {removed_items.count()}, "
          f"Updated: {updated_items.count()}")

    return new_items, removed_items, updated_items
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Integration with ML Platform

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### End-to-End ML Pipeline Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE → SAGEMAKER INTEGRATION                              │
│                                                                             │
│  Glue Output (S3/Iceberg)                                                   │
│       │                                                                     │
│       ├──→ SageMaker Processing Job (data validation, statistics)           │
│       │                                                                     │
│       ├──→ SageMaker Training Job                                           │
│       │       ├── Two-Tower Model (user embedding + item embedding)         │
│       │       ├── Neural Collaborative Filtering                            │
│       │       └── Gradient Boosted Trees (ranking stage)                    │
│       │                                                                     │
│       ├──→ SageMaker Model Registry                                         │
│       │       ├── Model version (linked to dataset version)                 │
│       │       ├── Offline metrics (NDCG, HR@K, MRR)                        │
│       │       └── Approval workflow (auto if metrics improve)               │
│       │                                                                     │
│       └──→ SageMaker Endpoint (real-time inference)                         │
│               ├── Multi-model endpoint (200+ models)                        │
│               └── A/B traffic splitting                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Triggering Training from Glue

```python
# At end of Job 5, trigger SageMaker training pipeline
import boto3

def trigger_training_pipeline(run_date, dataset_location, eval_metadata):
    """Trigger SageMaker Pipeline after Glue completes data preparation."""

    sagemaker = boto3.client('sagemaker')

    sagemaker.start_pipeline_execution(
        PipelineName="recommendation-model-training",
        PipelineParameters=[
            {"Name": "TrainingDataPath", "Value": dataset_location},
            {"Name": "DatasetVersion", "Value": run_date},
            {"Name": "BaselineHR10", "Value": str(eval_metadata["popularity_baseline_hr10"])},
            {"Name": "NumTrainSamples", "Value": str(eval_metadata["train_size"])},
            {"Name": "NumFeatures", "Value": str(eval_metadata["num_features"])}
        ],
        PipelineExecutionDescription=f"Triggered by Glue pipeline for {run_date}"
    )
```

### A/B Test Result Aggregation

```python
# job_ab_test_aggregation.py (runs after experiments collect enough data)

def aggregate_ab_results(spark, experiment_id, run_date):
    """
    Aggregate A/B test results to compare model versions.
    Feeds back into Glue pipeline for model selection.
    """

    # Read interaction outcomes for experiment cohorts
    outcomes = spark.read.format("iceberg").load(
        "glue_catalog.recommendation_pipeline.ab_test_outcomes"
    ).filter(
        (F.col("experiment_id") == experiment_id) &
        (F.col("outcome_date") == run_date)
    )

    # Compute metrics per variant
    variant_metrics = outcomes.groupBy("variant").agg(
        # Engagement metrics
        F.avg("clicked").alias("ctr"),
        F.avg("completed").alias("completion_rate"),
        F.avg("time_spent_seconds").alias("avg_time_spent"),

        # Revenue metrics
        F.avg("revenue").alias("avg_revenue_per_user"),
        F.sum("revenue").alias("total_revenue"),

        # Diversity metrics
        F.avg("num_unique_genres_consumed").alias("avg_genre_diversity"),
        F.avg("num_unique_creators_consumed").alias("avg_creator_diversity"),

        # User satisfaction
        F.avg("explicit_rating_given").alias("avg_rating"),
        F.count("*").alias("sample_size")
    )

    # Statistical significance (simplified - use proper stats library in prod)
    variant_metrics = variant_metrics.withColumn(
        "ctr_ci_95",
        1.96 * F.sqrt(F.col("ctr") * (1 - F.col("ctr")) / F.col("sample_size"))
    )

    return variant_metrics
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling: Processing 10B Interactions Daily

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Cluster Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE JOB CONFIGURATIONS                                   │
├──────────────────────┬──────────────┬──────────────┬────────────────────────┤
│  Job                 │  Worker Type │  Workers     │  Rationale             │
├──────────────────────┼──────────────┼──────────────┼────────────────────────┤
│  Job 1: Interactions │  G.2X        │  200         │  High I/O, dedup      │
│  Job 2: User Feats   │  G.2X        │  300         │  Large broadcast      │
│  Job 3: Item Feats   │  G.1X        │  50          │  Smaller dataset      │
│  Job 4: Training     │  G.2X        │  400         │  Cross join negatives │
│  Job 5: Evaluation   │  G.1X        │  100         │  Subset of data       │
├──────────────────────┼──────────────┼──────────────┼────────────────────────┤
│  TOTAL DPU-hours     │              │              │  ~2,400 DPU-hours/day │
└──────────────────────┴──────────────┴──────────────┴────────────────────────┘
```

### Performance Optimizations

```python
# 1. Partition pruning: Only read relevant date partitions
spark.conf.set("spark.sql.iceberg.planning.preserve-data-grouping", "true")

# 2. Broadcast join for item features (item catalog fits in memory)
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "512m")

# 3. Adaptive query execution for skewed user distributions
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256m")

# 4. Columnar compression for feature vectors
spark.conf.set("spark.sql.parquet.compression.codec", "zstd")

# 5. Bucketing for frequent joins on user_id
# Pre-bucket interactions table by user_id (512 buckets for 300M users)
interactions.write.bucketBy(512, "user_id").sortBy("user_id").format("iceberg") \
    .saveAsTable("recommendation_pipeline.interactions_bucketed")
```

### Data Volume Management

```
Daily data flow:
─────────────────
Raw interactions:     10B events × 500 bytes   = 5.0 TB
After dedup/filter:   7B events × 200 bytes    = 1.4 TB
User-item aggregated: 2B pairs × 300 bytes     = 600 GB
User features:        300M users × 2KB         = 600 GB
Item features:        50M items × 4KB          = 200 GB
Training dataset:     10B examples × 1KB       = 10 TB (with features)
Evaluation sets:      500M examples × 1KB      = 500 GB

Total daily output: ~13.3 TB
Monthly retention (with Iceberg snapshots): ~50 TB active
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONTHLY COST BREAKDOWN                                    │
├────────────────────────────────────┬────────────────────────────────────────┤
│  Component                         │  Monthly Cost                          │
├────────────────────────────────────┼────────────────────────────────────────┤
│  Glue Jobs (2,400 DPU-hrs × 30d)  │  $31,680 ($0.44/DPU-hr)              │
│  S3 Storage (50TB active)          │  $1,150                               │
│  S3 Requests (heavy read/write)    │  $2,500                               │
│  Glue Data Catalog                 │  $100                                 │
│  Glue Crawlers                     │  $500                                 │
│  Data Transfer                     │  $800                                 │
├────────────────────────────────────┼────────────────────────────────────────┤
│  TOTAL GLUE PIPELINE               │  ~$36,730/month                       │
├────────────────────────────────────┼────────────────────────────────────────┤
│  SageMaker Training (downstream)   │  ~$15,000/month                       │
│  Feature Store                     │  ~$5,000/month                        │
│  Inference Endpoints               │  ~$50,000/month                       │
├────────────────────────────────────┼────────────────────────────────────────┤
│  TOTAL ML PLATFORM                 │  ~$106,730/month                      │
└────────────────────────────────────┴────────────────────────────────────────┘

Cost per recommendation served: ~$0.000012
Revenue impact: 15-30% of engagement driven by recommendations
ROI: $100K/month cost → $50M+/month revenue attribution
```

### Cost Optimization Strategies

```
1. Auto-scaling workers: Use Glue Flex (spot) for Jobs 3 and 5 (30% savings)
2. Incremental processing: Job bookmarks avoid reprocessing (70% compute savings)
3. Iceberg compaction: Schedule off-peak to reduce small files (20% I/O savings)
4. Feature caching: Cache user features for 24h (reduces Job 2 frequency)
5. Tiered storage: Move datasets older than 30 days to S3 Glacier
6. Right-sizing: Monitor Spark UI for underutilized executors
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Using This Pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Company     │  Scale              │  Key Technique                         │
├──────────────┼─────────────────────┼────────────────────────────────────────┤
│  Netflix     │  230M users,        │  Two-tower retrieval + ranking.        │
│              │  hourly model       │  Batch features computed in Spark.     │
│              │  refresh            │  Contextual bandits for exploration.   │
├──────────────┼─────────────────────┼────────────────────────────────────────┤
│  Spotify     │  600M users,        │  Collaborative filtering on listening  │
│              │  100M tracks        │  sessions. Audio features via CNN.     │
│              │                     │  Discover Weekly: batch pipeline.      │
├──────────────┼─────────────────────┼────────────────────────────────────────┤
│  Amazon      │  300M+ users,       │  Item-to-item collaborative filtering. │
│              │  350M products      │  Feature store for real-time +         │
│              │                     │  batch serving. Multi-objective.       │
├──────────────┼─────────────────────┼────────────────────────────────────────┤
│  YouTube     │  2B+ users,         │  Two-stage: candidate generation      │
│              │  800M videos        │  (batch embeddings) + ranking          │
│              │                     │  (real-time features). Deep neural     │
│              │                     │  networks on batch-computed features.  │
├──────────────┼─────────────────────┼────────────────────────────────────────┤
│  Pinterest   │  450M users,        │  PinSage: graph neural networks.      │
│              │  300B pins          │  Batch computation of pin embeddings   │
│              │                     │  via random walks on user-pin graph.   │
└──────────────┴─────────────────────┴────────────────────────────────────────┘
```

### Common Pattern Across All

Every major recommendation system follows this batch data preparation pattern:

1. **Collect** raw interactions from multiple sources
2. **Aggregate** to user-item level with computed scores
3. **Enrich** with content and contextual features
4. **Assemble** training examples with positive/negative labels
5. **Version** datasets for reproducibility
6. **Evaluate** with time-based holdout splits
7. **Feed** into model training pipelines
8. **Close the loop** with A/B test measurement

AWS Glue handles steps 1-6 as the batch data preparation layer, bridging raw
event streams and the ML training platform.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
