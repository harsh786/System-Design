# E-Commerce Recommendation System Data Pipeline

## The Production Problem at Scale

Building a recommendation system at Netflix/Amazon scale means processing behavioral signals from **500 million users** interacting with **100 million items**, generating **50 billion interaction events per month** (~19,000 events/second sustained, 200K+ peak). The data pipeline must:

1. Collect every user signal (views, clicks, purchases, ratings, dwell time, scroll depth)
2. Compute user and item features from historical behavior
3. Generate training datasets for ML models (collaborative filtering, deep learning)
4. Serve fresh features for real-time inference (<50ms p99 latency)
5. Support A/B testing across dozens of concurrent experiments

The pipeline is not the model — it is everything that makes the model possible.

---

## Why Iceberg (Not Hive or Raw Parquet)

### The Breaking Points at Scale

| Problem | Hive/Raw Parquet | Iceberg Solution |
|---------|-----------------|------------------|
| 50B events/month → millions of small files | Manual compaction scripts, unreliable | Built-in compaction with bin-pack and sort order |
| User lookup across 3 years of history | Full partition scan (read TBs) | Predicate pushdown + file-level min/max pruning |
| Late events (mobile offline sync, 72h delay) | Overwrite entire partition or accept duplicates | MERGE INTO with row-level deduplication |
| Training dataset reproducibility | No versioning, "what data did model v47 train on?" | Time-travel snapshots pinned to training runs |
| Schema evolution (new event types monthly) | Break downstream consumers | Schema evolution with column ID tracking |
| Concurrent reads/writes (Spark + Flink + Trino) | Corrupt reads, inconsistent state | MVCC snapshot isolation |
| Feature backfill (recompute 90 days) | Partition lock contention | Concurrent writers with optimistic locking |

### The Core Insight

A recommendation pipeline has **two fundamentally different access patterns**:

1. **Time-series append**: Events stream in chronologically → partition by time
2. **Entity lookup**: "Give me all events for user X" or "all interactions with item Y" → partition by entity

Iceberg's **hidden partitioning** and **partition evolution** let you optimize for both without rewriting data or breaking queries.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        EVENT COLLECTION LAYER                                    │
│                                                                                  │
│  Mobile App ──┐                                                                  │
│  Web App ─────┼──→ API Gateway ──→ Kafka (partitioned by user_id hash)          │
│  Smart TV ────┘         │              │                                         │
│                         │              ├──→ Topic: user.events (raw)             │
│                         │              ├──→ Topic: user.events.enriched          │
│                         │              └──→ Topic: user.events.deadletter        │
│                         ▼                                                        │
│                   Event Schema                                                   │
│                   Registry (Avro)                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     REAL-TIME PROCESSING (Flink)                                 │
│                                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐                    │
│  │ Dedup &     │──→ │ Session      │──→ │ Real-time       │──→ Feature Store   │
│  │ Validation  │    │ Stitching    │    │ Feature Compute │    (Redis/DynamoDB) │
│  └─────────────┘    └──────────────┘    └─────────────────┘                    │
│         │                                        │                               │
│         ▼                                        ▼                               │
│   S3/Iceberg: events_raw               S3/Iceberg: real_time_features           │
└─────────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     BATCH PROCESSING (Spark + dbt)                                │
│                                                                                  │
│  ┌──────────────────┐   ┌───────────────────┐   ┌────────────────────┐         │
│  │ User Feature     │   │ Item Feature      │   │ Training Dataset   │         │
│  │ Engineering      │   │ Engineering       │   │ Generation         │         │
│  │ (daily/hourly)   │   │ (daily)           │   │ (on-demand)        │         │
│  └────────┬─────────┘   └────────┬──────────┘   └────────┬───────────┘         │
│           ▼                      ▼                        ▼                      │
│  Iceberg: user_features  Iceberg: item_features  Iceberg: training_datasets     │
└─────────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     MODEL TRAINING & SERVING                                     │
│                                                                                  │
│  ┌────────────────┐    ┌─────────────────┐    ┌──────────────────┐             │
│  │ SageMaker      │──→ │ Model Registry  │──→ │ Inference Service │            │
│  │ Training Jobs  │    │ (MLflow)        │    │ (SageMaker EP)    │            │
│  └────────────────┘    └─────────────────┘    └──────────────────┘             │
│         ▲                                              │                         │
│         │                                              ▼                         │
│  Iceberg: training_datasets              Feature Store (online) + Iceberg (offline)│
│  (time-travel snapshot pinned)                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ANALYSIS & MONITORING                                         │
│                                                                                  │
│  Trino/Athena ──→ A/B test analysis, feature drift detection                   │
│  Grafana ──→ Pipeline latency, data freshness, SLA dashboards                  │
│  Great Expectations ──→ Data quality checks on every write                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Table Definitions (DDL)

### Events Table — The Foundation

```sql
CREATE TABLE recommendation.events (
    event_id          STRING      COMMENT 'UUID v7 (time-ordered) for natural dedup',
    user_id           BIGINT      COMMENT 'Internal user identifier',
    item_id           BIGINT      COMMENT 'Product/content identifier',
    event_type        STRING      COMMENT 'view|click|add_to_cart|purchase|rate|search|scroll',
    event_timestamp   TIMESTAMP   COMMENT 'Client-side event time (UTC)',
    server_timestamp  TIMESTAMP   COMMENT 'Server receipt time for late-arrival detection',
    session_id        STRING      COMMENT 'Client session identifier',
    
    -- Context
    platform          STRING      COMMENT 'ios|android|web|tv|api',
    device_type       STRING      COMMENT 'phone|tablet|desktop|tv',
    page_type         STRING      COMMENT 'home|search|pdp|category|cart',
    referrer_type     STRING      COMMENT 'organic|paid|email|push|direct',
    
    -- Interaction details
    position          INT         COMMENT 'Position in list/carousel where item appeared',
    dwell_time_ms     BIGINT      COMMENT 'Time spent on item (views only)',
    scroll_depth_pct  FLOAT       COMMENT 'How far user scrolled on item page',
    rating_value      FLOAT       COMMENT 'Explicit rating (1-5) if event_type=rate',
    purchase_amount   DECIMAL(12,2) COMMENT 'Purchase value if event_type=purchase',
    currency          STRING,
    
    -- A/B Testing
    experiment_ids    ARRAY<STRING> COMMENT 'Active experiment assignments',
    variant_ids       ARRAY<STRING> COMMENT 'Variant for each experiment',
    
    -- Recommendation attribution
    rec_model_id      STRING      COMMENT 'Which model generated this recommendation',
    rec_request_id    STRING      COMMENT 'Unique recommendation request ID',
    rec_score         FLOAT       COMMENT 'Model score at time of recommendation',
    
    -- Processing metadata
    ingestion_time    TIMESTAMP   COMMENT 'Pipeline processing time',
    is_bot            BOOLEAN     COMMENT 'Bot detection flag',
    event_date        DATE        COMMENT 'Derived from event_timestamp for partitioning'
)
USING iceberg
PARTITIONED BY (
    days(event_timestamp),
    bucket(256, user_id)
)
TBLPROPERTIES (
    'write.distribution-mode' = 'hash',
    'write.parquet.row-group-size-bytes' = '134217728',
    'write.metadata.compression-codec' = 'gzip',
    'write.parquet.compression-codec' = 'zstd',
    'read.split.target-size' = '268435456',
    'write.spark.fanout.enabled' = 'true',
    'format-version' = '2'
);
```

**Why this partitioning?**

- `days(event_timestamp)`: Batch jobs process daily windows; time-travel queries are time-bounded
- `bucket(256, user_id)`: User-centric lookups scan 1/256th of each day's data. 256 buckets = good parallelism for Spark (matches typical cluster size)

At 50B events/month:
- ~1.67B events/day → each daily partition: ~1.67B rows
- Each bucket within a day: ~6.5M rows → compacted to ~50-100 files of 128MB each
- Total daily data: ~2TB compressed (Zstd) → manageable for parallel reads

### User Features Table

```sql
CREATE TABLE recommendation.user_features (
    user_id                BIGINT,
    computed_at            TIMESTAMP    COMMENT 'When this feature vector was computed',
    feature_version        INT          COMMENT 'Feature engineering version for reproducibility',
    
    -- Engagement features (multiple time windows)
    views_1d               BIGINT,
    views_7d               BIGINT,
    views_30d              BIGINT,
    views_90d              BIGINT,
    clicks_1d              BIGINT,
    clicks_7d              BIGINT,
    clicks_30d             BIGINT,
    purchases_7d           BIGINT,
    purchases_30d          BIGINT,
    purchases_90d          BIGINT,
    
    -- Behavioral features
    avg_session_duration_7d    FLOAT,
    avg_items_per_session_7d   FLOAT,
    avg_dwell_time_ms_7d       FLOAT,
    click_through_rate_7d      FLOAT,
    conversion_rate_30d        FLOAT,
    cart_abandonment_rate_30d  FLOAT,
    
    -- Preference features
    top_categories_30d     ARRAY<STRUCT<category_id: BIGINT, affinity_score: FLOAT>>,
    top_brands_30d         ARRAY<STRUCT<brand_id: BIGINT, affinity_score: FLOAT>>,
    price_sensitivity      FLOAT        COMMENT 'Normalized price elasticity score',
    avg_purchase_value_90d DECIMAL(10,2),
    preferred_platform     STRING,
    
    -- Temporal patterns
    active_hours           ARRAY<INT>   COMMENT 'Most active hours (0-23)',
    active_days            ARRAY<INT>   COMMENT 'Most active days (1-7)',
    days_since_last_visit  INT,
    days_since_last_purchase INT,
    
    -- User embedding (from deep learning model)
    user_embedding         ARRAY<FLOAT> COMMENT '128-dim user representation vector',
    
    -- Metadata
    total_events_processed BIGINT,
    first_event_date       DATE,
    last_event_date        DATE
)
USING iceberg
PARTITIONED BY (bucket(128, user_id))
TBLPROPERTIES (
    'write.distribution-mode' = 'hash',
    'write.parquet.compression-codec' = 'zstd',
    'write.update.mode' = 'merge-on-read',
    'format-version' = '2'
);
```

**Why bucket-only partitioning?** User features are accessed by user_id (point lookups for serving, range scans for batch). No time partitioning because we keep only the latest version per user (MERGE INTO upserts). The `merge-on-read` mode enables fast upserts without rewriting entire files.

### Item Features Table

```sql
CREATE TABLE recommendation.item_features (
    item_id                BIGINT,
    computed_at            TIMESTAMP,
    feature_version        INT,
    
    -- Static attributes (from catalog)
    category_id            BIGINT,
    category_path          ARRAY<BIGINT>  COMMENT 'Full category hierarchy',
    brand_id               BIGINT,
    price                  DECIMAL(10,2),
    price_bucket           STRING         COMMENT 'budget|mid|premium|luxury',
    release_date           DATE,
    
    -- Popularity features
    views_1d               BIGINT,
    views_7d               BIGINT,
    views_30d              BIGINT,
    unique_viewers_7d      BIGINT,
    purchases_7d           BIGINT,
    purchases_30d          BIGINT,
    revenue_30d            DECIMAL(12,2),
    
    -- Quality signals
    avg_rating             FLOAT,
    rating_count           BIGINT,
    return_rate_90d        FLOAT,
    avg_dwell_time_ms      FLOAT          COMMENT 'Avg time spent viewing this item',
    
    -- Interaction features
    click_through_rate_7d  FLOAT,
    conversion_rate_7d     FLOAT,
    add_to_cart_rate_7d    FLOAT,
    
    -- Co-occurrence features
    frequently_bought_with ARRAY<BIGINT>  COMMENT 'Top 20 co-purchased items',
    frequently_viewed_with ARRAY<BIGINT>  COMMENT 'Top 20 co-viewed items',
    
    -- Item embedding
    item_embedding         ARRAY<FLOAT>   COMMENT '128-dim item representation vector',
    
    -- Content features (from NLP/CV pipelines)
    title_embedding        ARRAY<FLOAT>   COMMENT '64-dim title text embedding',
    image_embedding        ARRAY<FLOAT>   COMMENT '256-dim image embedding',
    
    -- Freshness/trending
    velocity_score_24h     FLOAT          COMMENT 'Rate of interaction acceleration',
    trending_score         FLOAT          COMMENT 'Bayesian trending score'
)
USING iceberg
PARTITIONED BY (bucket(64, item_id))
TBLPROPERTIES (
    'write.distribution-mode' = 'hash',
    'write.parquet.compression-codec' = 'zstd',
    'write.update.mode' = 'merge-on-read',
    'format-version' = '2'
);
```

### Training Datasets Table

```sql
CREATE TABLE recommendation.training_datasets (
    dataset_id         STRING       COMMENT 'Unique dataset generation run ID',
    model_type         STRING       COMMENT 'collaborative_filtering|deep_ranking|session_based',
    split_type         STRING       COMMENT 'train|validation|test',
    
    user_id            BIGINT,
    item_id            BIGINT,
    label              FLOAT        COMMENT '1.0=positive, 0.0=negative (or rating value)',
    label_type         STRING       COMMENT 'purchase|click|implicit_positive|negative_sample',
    
    -- Features at interaction time (point-in-time correct)
    user_features      STRUCT<
        views_7d: BIGINT,
        clicks_7d: BIGINT,
        purchases_30d: BIGINT,
        avg_session_duration_7d: FLOAT,
        user_embedding: ARRAY<FLOAT>
    >,
    item_features      STRUCT<
        views_7d: BIGINT,
        avg_rating: FLOAT,
        price: DECIMAL(10,2),
        item_embedding: ARRAY<FLOAT>
    >,
    
    -- Context features
    hour_of_day        INT,
    day_of_week        INT,
    days_since_user_last_active INT,
    user_item_prior_interactions INT,
    
    -- Metadata
    event_timestamp    TIMESTAMP    COMMENT 'Original interaction time',
    generated_at       TIMESTAMP    COMMENT 'When this training example was created'
)
USING iceberg
PARTITIONED BY (model_type, dataset_id)
TBLPROPERTIES (
    'write.parquet.compression-codec' = 'zstd',
    'write.target-file-size-bytes' = '536870912',
    'format-version' = '2'
);
```

**Why partition by `(model_type, dataset_id)`?** Each training run reads exactly one dataset_id. Partition pruning means SageMaker reads only the relevant files. Large target file size (512MB) optimizes for sequential read throughput during training.

### Interaction Matrix (Sparse)

```sql
CREATE TABLE recommendation.interaction_matrix (
    user_id            BIGINT,
    item_id            BIGINT,
    interaction_score  FLOAT        COMMENT 'Weighted interaction: view=0.1, click=0.3, purchase=1.0',
    interaction_count  INT,
    first_interaction  TIMESTAMP,
    last_interaction   TIMESTAMP,
    interaction_types  ARRAY<STRING>,
    computed_date      DATE
)
USING iceberg
PARTITIONED BY (computed_date, bucket(256, user_id))
TBLPROPERTIES (
    'write.distribution-mode' = 'hash',
    'write.parquet.compression-codec' = 'zstd',
    'write.sort-order' = 'user_id ASC, interaction_score DESC',
    'format-version' = '2'
);
```

---

## Spark Pipeline Code

### 1. User Behavior Aggregation

```python
"""
User behavior aggregation pipeline.
Runs hourly (micro-batch) and daily (full recompute).
Reads from events table, writes to user_features.
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import *
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def create_spark_session():
    """Configure Spark with Iceberg catalog optimized for this workload."""
    return (
        SparkSession.builder
        .appName("recommendation-user-features")
        .config("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
        .config("spark.sql.catalog.glue.warehouse", "s3://data-lake-prod/warehouse")
        .config("spark.sql.catalog.glue.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        # Performance tuning for 500M user aggregation
        .config("spark.sql.shuffle.partitions", "2048")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        .config("spark.sql.iceberg.planning.preserve-data-grouping", "true")
        # Memory for large aggregations
        .config("spark.executor.memory", "32g")
        .config("spark.executor.memoryOverhead", "8g")
        .config("spark.driver.memory", "16g")
        .getOrCreate()
    )


def compute_user_engagement_features(spark, reference_date, lookback_days_map):
    """
    Compute time-windowed engagement features for all active users.
    
    Args:
        reference_date: The date to compute features as-of
        lookback_days_map: Dict mapping window name to days, e.g. {'1d': 1, '7d': 7, '30d': 30}
    """
    max_lookback = max(lookback_days_map.values())
    start_date = reference_date - timedelta(days=max_lookback)
    
    # Read events with partition pruning (Iceberg pushes down the timestamp filter)
    events = (
        spark.read
        .format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(start_date)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("is_bot") == False)
        )
        .select(
            "user_id", "event_type", "event_timestamp",
            "dwell_time_ms", "session_id", "item_id",
            "purchase_amount", "position"
        )
    )
    
    # Cache because we'll scan multiple times for different windows
    events.cache()
    logger.info(f"Loaded {events.count()} events for feature computation")
    
    # Compute features for each time window
    feature_dfs = []
    for window_name, days in lookback_days_map.items():
        window_start = reference_date - timedelta(days=days)
        windowed = events.filter(F.col("event_timestamp") >= F.lit(window_start))
        
        agg_features = (
            windowed.groupBy("user_id")
            .agg(
                # Count by event type
                F.count(F.when(F.col("event_type") == "view", 1)).alias(f"views_{window_name}"),
                F.count(F.when(F.col("event_type") == "click", 1)).alias(f"clicks_{window_name}"),
                F.count(F.when(F.col("event_type") == "purchase", 1)).alias(f"purchases_{window_name}"),
                
                # Only for certain windows to avoid column explosion
                *([
                    F.avg(F.when(F.col("event_type") == "view", F.col("dwell_time_ms")))
                        .alias(f"avg_dwell_time_ms_{window_name}"),
                    F.countDistinct("session_id").alias(f"sessions_{window_name}"),
                    F.countDistinct("item_id").alias(f"unique_items_{window_name}"),
                ] if days <= 30 else [])
            )
        )
        feature_dfs.append(agg_features)
    
    # Join all windows together
    result = feature_dfs[0]
    for df in feature_dfs[1:]:
        result = result.join(df, on="user_id", how="outer")
    
    events.unpersist()
    return result


def compute_user_behavioral_features(spark, reference_date):
    """Compute derived behavioral signals: CTR, conversion, session patterns."""
    lookback_30d = reference_date - timedelta(days=30)
    lookback_7d = reference_date - timedelta(days=7)
    
    events = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(lookback_30d)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("is_bot") == False)
        )
    )
    
    # Session-level aggregation first
    session_stats = (
        events.groupBy("user_id", "session_id")
        .agg(
            (F.max("event_timestamp").cast("long") - F.min("event_timestamp").cast("long"))
                .alias("session_duration_sec"),
            F.countDistinct("item_id").alias("items_in_session"),
            F.count("*").alias("events_in_session")
        )
    )
    
    # User-level behavioral features
    behavioral = (
        session_stats
        .groupBy("user_id")
        .agg(
            F.avg("session_duration_sec").alias("avg_session_duration_7d"),
            F.avg("items_in_session").alias("avg_items_per_session_7d"),
            F.percentile_approx("session_duration_sec", 0.5).alias("median_session_sec")
        )
    )
    
    # CTR and conversion rate
    impression_clicks = (
        events
        .filter(F.col("event_timestamp") >= F.lit(lookback_7d))
        .groupBy("user_id")
        .agg(
            F.count(F.when(F.col("event_type") == "view", 1)).alias("impressions"),
            F.count(F.when(F.col("event_type") == "click", 1)).alias("clicks"),
            F.count(F.when(F.col("event_type") == "purchase", 1)).alias("purchases"),
            F.count(F.when(F.col("event_type") == "add_to_cart", 1)).alias("add_to_carts")
        )
        .withColumn("click_through_rate_7d",
            F.when(F.col("impressions") > 0, F.col("clicks") / F.col("impressions")).otherwise(0.0))
        .withColumn("conversion_rate_30d",
            F.when(F.col("clicks") > 0, F.col("purchases") / F.col("clicks")).otherwise(0.0))
        .withColumn("cart_abandonment_rate_30d",
            F.when(F.col("add_to_carts") > 0,
                1.0 - (F.col("purchases") / F.col("add_to_carts"))).otherwise(0.0))
        .select("user_id", "click_through_rate_7d", "conversion_rate_30d", "cart_abandonment_rate_30d")
    )
    
    return behavioral.join(impression_clicks, on="user_id", how="outer")


def compute_user_preference_features(spark, reference_date):
    """Compute category/brand affinity using weighted interactions."""
    lookback = reference_date - timedelta(days=30)
    
    # Weight different interaction types
    interaction_weights = {
        "view": 0.1, "click": 0.3, "add_to_cart": 0.5,
        "purchase": 1.0, "rate": 0.7
    }
    
    events_with_items = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(lookback)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("is_bot") == False)
        )
        .join(
            spark.read.format("iceberg").load("glue.recommendation.item_catalog")
                .select("item_id", "category_id", "brand_id", "price"),
            on="item_id",
            how="inner"
        )
        .withColumn("interaction_weight",
            F.when(F.col("event_type") == "purchase", 1.0)
            .when(F.col("event_type") == "add_to_cart", 0.5)
            .when(F.col("event_type") == "click", 0.3)
            .when(F.col("event_type") == "rate", 0.7)
            .otherwise(0.1)
        )
    )
    
    # Top categories per user
    category_affinity = (
        events_with_items
        .groupBy("user_id", "category_id")
        .agg(F.sum("interaction_weight").alias("affinity_score"))
    )
    
    # Rank and keep top 10 categories per user
    w = Window.partitionBy("user_id").orderBy(F.desc("affinity_score"))
    top_categories = (
        category_affinity
        .withColumn("rank", F.row_number().over(w))
        .filter(F.col("rank") <= 10)
        .groupBy("user_id")
        .agg(
            F.collect_list(
                F.struct("category_id", "affinity_score")
            ).alias("top_categories_30d")
        )
    )
    
    # Price sensitivity (coefficient of variation of purchase prices)
    price_features = (
        events_with_items
        .filter(F.col("event_type") == "purchase")
        .groupBy("user_id")
        .agg(
            F.avg("price").alias("avg_purchase_value_90d"),
            (F.stddev("price") / F.avg("price")).alias("price_sensitivity")
        )
    )
    
    return top_categories.join(price_features, on="user_id", how="outer")


def write_user_features(spark, features_df, reference_date):
    """
    MERGE INTO user_features table (upsert pattern).
    Uses Iceberg's merge-on-read for efficient updates.
    """
    features_final = (
        features_df
        .withColumn("computed_at", F.lit(datetime.utcnow()))
        .withColumn("feature_version", F.lit(3))  # Increment on feature engineering changes
    )
    
    # Register as temp view for SQL MERGE
    features_final.createOrReplaceTempView("new_features")
    
    spark.sql("""
        MERGE INTO glue.recommendation.user_features target
        USING new_features source
        ON target.user_id = source.user_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    
    logger.info(f"Merged {features_final.count()} user feature vectors")


def run_user_feature_pipeline(reference_date=None):
    """Main entry point for user feature computation."""
    if reference_date is None:
        reference_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    spark = create_spark_session()
    
    try:
        # Compute all feature groups
        engagement = compute_user_engagement_features(
            spark, reference_date,
            lookback_days_map={'1d': 1, '7d': 7, '30d': 30, '90d': 90}
        )
        behavioral = compute_user_behavioral_features(spark, reference_date)
        preferences = compute_user_preference_features(spark, reference_date)
        
        # Join all feature groups
        all_features = (
            engagement
            .join(behavioral, on="user_id", how="outer")
            .join(preferences, on="user_id", how="outer")
            .fillna(0, subset=[c for c in engagement.columns if c != "user_id"])
        )
        
        write_user_features(spark, all_features, reference_date)
        
    finally:
        spark.stop()


if __name__ == "__main__":
    run_user_feature_pipeline()
```

### 2. Item Feature Computation

```python
"""
Item feature computation pipeline.
Computes popularity, quality, and co-occurrence features for all active items.
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from datetime import datetime, timedelta


def compute_item_popularity_features(spark, reference_date):
    """Compute time-decayed popularity metrics for items."""
    lookback_90d = reference_date - timedelta(days=90)
    
    events = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(lookback_90d)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("is_bot") == False)
        )
    )
    
    # Multi-window popularity
    windows = {'1d': 1, '7d': 7, '30d': 30}
    popularity_dfs = []
    
    for window_name, days in windows.items():
        window_start = reference_date - timedelta(days=days)
        windowed = events.filter(F.col("event_timestamp") >= F.lit(window_start))
        
        pop = (
            windowed.groupBy("item_id")
            .agg(
                F.count(F.when(F.col("event_type") == "view", 1)).alias(f"views_{window_name}"),
                F.count(F.when(F.col("event_type") == "purchase", 1)).alias(f"purchases_{window_name}"),
                F.countDistinct(
                    F.when(F.col("event_type") == "view", F.col("user_id"))
                ).alias(f"unique_viewers_{window_name}"),
            )
        )
        popularity_dfs.append(pop)
    
    result = popularity_dfs[0]
    for df in popularity_dfs[1:]:
        result = result.join(df, on="item_id", how="outer")
    
    return result


def compute_item_quality_signals(spark, reference_date):
    """Compute quality signals: ratings, dwell time, return rate."""
    lookback = reference_date - timedelta(days=90)
    
    events = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(lookback)) &
            (F.col("event_timestamp") < F.lit(reference_date))
        )
    )
    
    quality = (
        events.groupBy("item_id")
        .agg(
            F.avg(F.when(F.col("event_type") == "rate", F.col("rating_value")))
                .alias("avg_rating"),
            F.count(F.when(F.col("event_type") == "rate", 1))
                .alias("rating_count"),
            F.avg(F.when(F.col("event_type") == "view", F.col("dwell_time_ms")))
                .alias("avg_dwell_time_ms"),
        )
    )
    
    # Click-through and conversion rates
    rates = (
        events
        .filter(F.col("event_timestamp") >= F.lit(reference_date - timedelta(days=7)))
        .groupBy("item_id")
        .agg(
            F.count(F.when(F.col("event_type") == "view", 1)).alias("views"),
            F.count(F.when(F.col("event_type") == "click", 1)).alias("clicks"),
            F.count(F.when(F.col("event_type") == "purchase", 1)).alias("buys"),
        )
        .withColumn("click_through_rate_7d",
            F.when(F.col("views") > 10, F.col("clicks") / F.col("views")).otherwise(None))
        .withColumn("conversion_rate_7d",
            F.when(F.col("clicks") > 5, F.col("buys") / F.col("clicks")).otherwise(None))
        .select("item_id", "click_through_rate_7d", "conversion_rate_7d")
    )
    
    return quality.join(rates, on="item_id", how="outer")


def compute_co_occurrence_features(spark, reference_date):
    """
    Compute item co-occurrence from session-level co-views and co-purchases.
    This is the basis for 'frequently bought together' recommendations.
    """
    lookback = reference_date - timedelta(days=30)
    
    # Get user-item interactions within sessions
    sessions = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(lookback)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("event_type").isin("view", "click", "purchase"))
        )
        .select("user_id", "session_id", "item_id", "event_type")
    )
    
    # Self-join within sessions to find co-occurring items
    co_purchased = (
        sessions.filter(F.col("event_type") == "purchase").alias("a")
        .join(
            sessions.filter(F.col("event_type") == "purchase").alias("b"),
            (F.col("a.session_id") == F.col("b.session_id")) &
            (F.col("a.item_id") < F.col("b.item_id"))
        )
        .groupBy(F.col("a.item_id").alias("item_id"), F.col("b.item_id").alias("co_item_id"))
        .agg(F.count("*").alias("co_purchase_count"))
        .filter(F.col("co_purchase_count") >= 3)  # Minimum support threshold
    )
    
    # Keep top 20 co-purchased items per item
    w = Window.partitionBy("item_id").orderBy(F.desc("co_purchase_count"))
    top_co_purchased = (
        co_purchased
        .withColumn("rank", F.row_number().over(w))
        .filter(F.col("rank") <= 20)
        .groupBy("item_id")
        .agg(F.collect_list("co_item_id").alias("frequently_bought_with"))
    )
    
    return top_co_purchased


def compute_trending_score(spark, reference_date):
    """
    Bayesian trending score: items with accelerating interactions.
    Score = (interactions_last_24h / interactions_prior_7d_daily_avg) * confidence
    """
    last_24h_start = reference_date - timedelta(hours=24)
    prior_7d_start = reference_date - timedelta(days=8)
    
    events = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(prior_7d_start)) &
            (F.col("event_timestamp") < F.lit(reference_date)) &
            (F.col("event_type").isin("view", "click", "purchase"))
        )
    )
    
    recent = (
        events.filter(F.col("event_timestamp") >= F.lit(last_24h_start))
        .groupBy("item_id")
        .agg(F.count("*").alias("interactions_24h"))
    )
    
    baseline = (
        events.filter(F.col("event_timestamp") < F.lit(last_24h_start))
        .groupBy("item_id")
        .agg((F.count("*") / 7.0).alias("daily_avg_prior"))
    )
    
    trending = (
        recent.join(baseline, on="item_id", how="inner")
        .withColumn("velocity_score_24h",
            F.col("interactions_24h") / F.greatest(F.col("daily_avg_prior"), F.lit(1.0)))
        # Bayesian smoothing: don't trust items with few total interactions
        .withColumn("confidence",
            1.0 - (1.0 / (1.0 + F.col("interactions_24h") / 100.0)))
        .withColumn("trending_score",
            F.col("velocity_score_24h") * F.col("confidence"))
        .select("item_id", "velocity_score_24h", "trending_score")
    )
    
    return trending
```

### 3. Training Dataset Generation

```python
"""
Training dataset generation pipeline.
Creates point-in-time correct training examples with negative sampling.
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from datetime import datetime, timedelta
import uuid


def generate_training_dataset(
    spark,
    model_type: str,
    train_start: datetime,
    train_end: datetime,
    negative_ratio: int = 4,
    dataset_id: str = None
):
    """
    Generate a training dataset with:
    - Positive examples: actual user-item interactions
    - Negative examples: randomly sampled non-interactions
    - Point-in-time features: user/item features AS OF interaction time
    
    Args:
        model_type: Type of model (collaborative_filtering, deep_ranking)
        train_start: Start of training window
        train_end: End of training window
        negative_ratio: Number of negatives per positive
        dataset_id: Unique ID for this dataset (auto-generated if None)
    """
    if dataset_id is None:
        dataset_id = f"{model_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # --- Positive examples ---
    positives = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_timestamp") >= F.lit(train_start)) &
            (F.col("event_timestamp") < F.lit(train_end)) &
            (F.col("event_type").isin("purchase", "click", "add_to_cart")) &
            (F.col("is_bot") == False)
        )
        .select("user_id", "item_id", "event_type", "event_timestamp")
        .withColumn("label",
            F.when(F.col("event_type") == "purchase", 1.0)
            .when(F.col("event_type") == "add_to_cart", 0.7)
            .otherwise(0.3)  # click
        )
        .withColumn("label_type",
            F.when(F.col("event_type") == "purchase", "purchase")
            .when(F.col("event_type") == "add_to_cart", "implicit_positive")
            .otherwise("click")
        )
        # Deduplicate: keep highest-value interaction per user-item pair per day
        .withColumn("rank", F.row_number().over(
            Window.partitionBy("user_id", "item_id", F.to_date("event_timestamp"))
            .orderBy(F.desc("label"))
        ))
        .filter(F.col("rank") == 1)
        .drop("rank", "event_type")
    )
    
    positive_count = positives.count()
    
    # --- Negative sampling ---
    # Get all active items and users
    all_items = (
        spark.read.format("iceberg")
        .load("glue.recommendation.item_features")
        .select("item_id")
        .distinct()
    )
    
    all_users = positives.select("user_id").distinct()
    
    # Sample random user-item pairs that are NOT in positives
    # Strategy: for each positive user, sample N random items they didn't interact with
    user_item_positives = positives.select("user_id", "item_id").distinct()
    
    # Broadcast items for efficient cross-join sampling
    item_list = all_items.collect()
    item_broadcast = spark.sparkContext.broadcast([row.item_id for row in item_list])
    
    @F.udf(returnType=ArrayType(LongType()))
    def sample_negative_items(interacted_items, n_samples):
        """Sample items not in user's interaction history."""
        import random
        all_items_set = set(item_broadcast.value)
        interacted_set = set(interacted_items) if interacted_items else set()
        candidates = list(all_items_set - interacted_set)
        return random.sample(candidates, min(n_samples, len(candidates)))
    
    # Get each user's interacted items
    user_interactions = (
        user_item_positives
        .groupBy("user_id")
        .agg(F.collect_set("item_id").alias("interacted_items"))
    )
    
    negatives = (
        user_interactions
        .withColumn("negative_items",
            sample_negative_items(F.col("interacted_items"), F.lit(negative_ratio * 10)))
        .select("user_id", F.explode("negative_items").alias("item_id"))
        .withColumn("label", F.lit(0.0))
        .withColumn("label_type", F.lit("negative_sample"))
        .withColumn("event_timestamp", F.lit(train_end))  # Use end of window
        .limit(positive_count * negative_ratio)
    )
    
    # --- Combine and enrich with features ---
    all_examples = positives.unionByName(negatives)
    
    # Join point-in-time user features (using time-travel for historical correctness)
    # Read user features as they were at the END of training window
    user_features_snapshot = (
        spark.read.format("iceberg")
        .option("as-of-timestamp", train_end.strftime("%Y-%m-%d %H:%M:%S"))
        .load("glue.recommendation.user_features")
        .select(
            "user_id",
            F.struct(
                "views_7d", "clicks_7d", "purchases_30d",
                "avg_session_duration_7d", "user_embedding"
            ).alias("user_features")
        )
    )
    
    item_features_snapshot = (
        spark.read.format("iceberg")
        .option("as-of-timestamp", train_end.strftime("%Y-%m-%d %H:%M:%S"))
        .load("glue.recommendation.item_features")
        .select(
            "item_id",
            F.struct(
                "views_7d", "avg_rating", "price", "item_embedding"
            ).alias("item_features")
        )
    )
    
    # Enrich with features and context
    training_data = (
        all_examples
        .join(user_features_snapshot, on="user_id", how="left")
        .join(item_features_snapshot, on="item_id", how="left")
        .withColumn("hour_of_day", F.hour("event_timestamp"))
        .withColumn("day_of_week", F.dayofweek("event_timestamp"))
        .withColumn("dataset_id", F.lit(dataset_id))
        .withColumn("model_type", F.lit(model_type))
        .withColumn("generated_at", F.lit(datetime.utcnow()))
    )
    
    # --- Split into train/validation/test ---
    # Time-based split: train=80%, val=10%, test=10% (by event_timestamp)
    time_quantiles = training_data.approxQuantile(
        "event_timestamp", [0.8, 0.9], 0.01
    )
    
    train_split = training_data.filter(F.col("event_timestamp") < F.lit(time_quantiles[0]))
    val_split = training_data.filter(
        (F.col("event_timestamp") >= F.lit(time_quantiles[0])) &
        (F.col("event_timestamp") < F.lit(time_quantiles[1]))
    )
    test_split = training_data.filter(F.col("event_timestamp") >= F.lit(time_quantiles[1]))
    
    # Write each split
    for split_name, split_df in [("train", train_split), ("validation", val_split), ("test", test_split)]:
        (
            split_df
            .withColumn("split_type", F.lit(split_name))
            .writeTo("glue.recommendation.training_datasets")
            .append()
        )
    
    # Log the snapshot ID for reproducibility
    snapshot_id = (
        spark.sql("SELECT snapshot_id FROM glue.recommendation.training_datasets.snapshots ORDER BY committed_at DESC LIMIT 1")
        .collect()[0][0]
    )
    
    return {
        "dataset_id": dataset_id,
        "snapshot_id": snapshot_id,
        "positive_count": positive_count,
        "negative_count": positive_count * negative_ratio,
        "total_examples": positive_count * (1 + negative_ratio),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
    }
```

---

## Production Handling

### Deduplication

Events arrive via multiple paths (client retry, Kafka redelivery, replay). Deduplication uses `event_id` (UUID v7, time-ordered):

```python
def deduplicate_events(spark, raw_events_df):
    """
    Two-stage deduplication:
    1. Within-batch: window function dedup
    2. Cross-batch: MERGE INTO with conflict resolution
    """
    # Stage 1: Within-batch dedup (keep earliest server_timestamp)
    w = Window.partitionBy("event_id").orderBy("server_timestamp")
    deduped_batch = (
        raw_events_df
        .withColumn("_row_num", F.row_number().over(w))
        .filter(F.col("_row_num") == 1)
        .drop("_row_num")
    )
    
    # Stage 2: Cross-batch dedup via MERGE
    deduped_batch.createOrReplaceTempView("incoming_events")
    
    spark.sql("""
        MERGE INTO glue.recommendation.events target
        USING incoming_events source
        ON target.event_id = source.event_id
        WHEN NOT MATCHED THEN INSERT *
    """)
    
    return deduped_batch
```

### Late Event Handling

Mobile users go offline, events arrive up to 72 hours late:

```python
def handle_late_events(spark, events_df):
    """
    Late events strategy:
    - Events < 24h late: normal processing path
    - Events 24h-72h late: process but flag, update features incrementally
    - Events > 72h late: log to dead letter, don't update features
    """
    now = datetime.utcnow()
    
    return (
        events_df
        .withColumn("arrival_delay_hours",
            (F.col("server_timestamp").cast("long") - F.col("event_timestamp").cast("long")) / 3600)
        .withColumn("late_event_category",
            F.when(F.col("arrival_delay_hours") <= 24, "on_time")
            .when(F.col("arrival_delay_hours") <= 72, "late_acceptable")
            .otherwise("late_rejected")
        )
        .filter(F.col("late_event_category") != "late_rejected")
    )
```

### Session Stitching

Users switch devices mid-session. The Flink job handles this:

```sql
-- Session stitching logic: connect anonymous + authenticated events
-- When user logs in on device B, retroactively assign prior anonymous events
-- to their user_id using a 30-minute session window

-- Implemented in Flink SQL:
CREATE TABLE stitched_sessions AS
SELECT
    COALESCE(auth.user_id, anon.device_fingerprint_user_id) AS resolved_user_id,
    e.*
FROM events e
LEFT JOIN user_device_mapping auth ON e.device_id = auth.device_id
    AND e.event_timestamp BETWEEN auth.login_time AND auth.logout_time
LEFT JOIN anonymous_user_mapping anon ON e.anonymous_id = anon.anonymous_id;
```

### A/B Test Attribution

Every event carries experiment context. Attribution ensures correct measurement:

```python
def attribute_ab_test_metrics(spark, reference_date):
    """
    Compute per-experiment, per-variant metrics for recommendation models.
    Critical: use FIRST exposure as attribution point (not last).
    """
    experiment_events = (
        spark.read.format("iceberg")
        .load("glue.recommendation.events")
        .filter(
            (F.col("event_date") == reference_date) &
            (F.size("experiment_ids") > 0)
        )
        .select(
            "user_id", "event_type", "purchase_amount",
            F.explode(F.arrays_zip("experiment_ids", "variant_ids")).alias("exp")
        )
        .select(
            "user_id", "event_type", "purchase_amount",
            F.col("exp.experiment_ids").alias("experiment_id"),
            F.col("exp.variant_ids").alias("variant_id")
        )
    )
    
    metrics = (
        experiment_events
        .groupBy("experiment_id", "variant_id")
        .agg(
            F.countDistinct("user_id").alias("unique_users"),
            F.count(F.when(F.col("event_type") == "purchase", 1)).alias("purchases"),
            F.sum(F.when(F.col("event_type") == "purchase", F.col("purchase_amount")))
                .alias("revenue"),
            F.count(F.when(F.col("event_type") == "click", 1)).alias("clicks"),
            F.count(F.when(F.col("event_type") == "view", 1)).alias("views"),
        )
        .withColumn("conversion_rate", F.col("purchases") / F.col("unique_users"))
        .withColumn("revenue_per_user", F.col("revenue") / F.col("unique_users"))
    )
    
    return metrics
```

---

## Optimization: Compaction and Partition Strategy

### Compaction Configuration

```python
"""
Compaction schedules differ by table access pattern:
- events: append-heavy, read by time range → bin-pack within partitions
- user_features: update-heavy, read by user_id → sort-order compaction
- training_datasets: write-once read-many → optimize on write
"""

# Events table: run every 2 hours to consolidate streaming micro-batches
spark.sql("""
    CALL glue.system.rewrite_data_files(
        table => 'recommendation.events',
        strategy => 'binpack',
        options => map(
            'target-file-size-bytes', '134217728',    -- 128MB target
            'min-file-size-bytes', '67108864',        -- Don't rewrite files > 64MB
            'max-file-size-bytes', '201326592',       -- 192MB max
            'min-input-files', '5',                   -- Only compact if 5+ small files
            'partial-progress.enabled', 'true',       -- Commit progress incrementally
            'partial-progress.max-commits', '10'
        ),
        where => 'event_timestamp >= current_timestamp() - INTERVAL 48 HOURS'
    )
""")

# User features: sort-order compaction for efficient lookups
spark.sql("""
    CALL glue.system.rewrite_data_files(
        table => 'recommendation.user_features',
        strategy => 'sort',
        sort_order => 'user_id ASC',
        options => map(
            'target-file-size-bytes', '268435456',    -- 256MB (fewer files, sequential reads)
            'min-input-files', '3'
        )
    )
""")

# Expire old snapshots (keep 7 days for time-travel, except training pinned snapshots)
spark.sql("""
    CALL glue.system.expire_snapshots(
        table => 'recommendation.events',
        older_than => TIMESTAMP '${seven_days_ago}',
        retain_last => 168,  -- Keep at least 168 snapshots (hourly for 7 days)
        max_concurrent_deletes => 100
    )
""")

# Remove orphan files (dangling from failed writes)
spark.sql("""
    CALL glue.system.remove_orphan_files(
        table => 'recommendation.events',
        older_than => TIMESTAMP '${three_days_ago}'
    )
""")
```

### Partition Strategy by Access Pattern

| Table | Partition Scheme | Rationale |
|-------|-----------------|-----------|
| events | `days(event_timestamp), bucket(256, user_id)` | Time-range scans for batch + user lookups for feature serving |
| user_features | `bucket(128, user_id)` | Point lookups and range scans by user; no time dimension (latest only) |
| item_features | `bucket(64, item_id)` | Fewer items than users, larger feature vectors per row |
| training_datasets | `model_type, dataset_id` | Each training job reads exactly one partition |
| interaction_matrix | `computed_date, bucket(256, user_id)` | Daily snapshots + user-centric access |

### File Pruning in Action

Query: "Get all purchase events for user 12345 in the last 7 days"

```
Without Iceberg: Scan all files for last 7 days → ~14TB read
With Iceberg partition pruning: 
  - days() partition: 7 daily partitions selected (out of 365+)
  - bucket(256, user_id): 1 bucket selected per day (1/256th)
  - Column statistics: skip files where min(user_id) > 12345 or max(user_id) < 12345
  - Result: ~200MB read (70,000x reduction)
```

---

## Monitoring

### Data Freshness

```python
# Freshness monitoring: alert if features are stale
freshness_query = """
SELECT
    'user_features' AS table_name,
    MAX(computed_at) AS last_update,
    CURRENT_TIMESTAMP - MAX(computed_at) AS staleness,
    CASE
        WHEN CURRENT_TIMESTAMP - MAX(computed_at) > INTERVAL '2' HOUR THEN 'CRITICAL'
        WHEN CURRENT_TIMESTAMP - MAX(computed_at) > INTERVAL '1' HOUR THEN 'WARNING'
        ELSE 'OK'
    END AS status
FROM glue.recommendation.user_features

UNION ALL

SELECT
    'events' AS table_name,
    MAX(ingestion_time) AS last_update,
    CURRENT_TIMESTAMP - MAX(ingestion_time) AS staleness,
    CASE
        WHEN CURRENT_TIMESTAMP - MAX(ingestion_time) > INTERVAL '15' MINUTE THEN 'CRITICAL'
        WHEN CURRENT_TIMESTAMP - MAX(ingestion_time) > INTERVAL '5' MINUTE THEN 'WARNING'
        ELSE 'OK'
    END AS status
FROM glue.recommendation.events
WHERE event_date = CURRENT_DATE
"""
```

### Feature Drift Detection

```python
def detect_feature_drift(spark, feature_table, reference_date):
    """
    Compare current feature distributions to 7-day-ago baseline.
    Alert if KL divergence exceeds threshold.
    """
    current = (
        spark.read.format("iceberg")
        .load(f"glue.recommendation.{feature_table}")
    )
    
    # Time-travel to 7 days ago
    baseline = (
        spark.read.format("iceberg")
        .option("as-of-timestamp",
            (reference_date - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        .load(f"glue.recommendation.{feature_table}")
    )
    
    numeric_cols = [f.name for f in current.schema.fields
                    if f.dataType in (FloatType(), DoubleType(), IntegerType(), LongType())]
    
    drift_metrics = []
    for col_name in numeric_cols:
        curr_stats = current.select(
            F.mean(col_name).alias("mean"),
            F.stddev(col_name).alias("std"),
            F.percentile_approx(col_name, [0.25, 0.5, 0.75]).alias("quantiles")
        ).collect()[0]
        
        base_stats = baseline.select(
            F.mean(col_name).alias("mean"),
            F.stddev(col_name).alias("std"),
        ).collect()[0]
        
        # Population Stability Index (PSI)
        if base_stats["std"] and base_stats["std"] > 0:
            mean_shift = abs(curr_stats["mean"] - base_stats["mean"]) / base_stats["std"]
            drift_metrics.append({
                "feature": col_name,
                "mean_shift_stddevs": mean_shift,
                "alert": mean_shift > 2.0  # Alert if shifted > 2 standard deviations
            })
    
    return drift_metrics
```

### Pipeline Latency SLAs

```yaml
# Monitoring thresholds (Grafana/CloudWatch)
sla_definitions:
  event_ingestion:
    description: "Time from client event to S3/Iceberg"
    target_p99: 60s       # 1 minute
    critical_threshold: 300s
    
  user_feature_freshness:
    description: "Time since last user_features update"
    target: 3600s         # 1 hour (hourly pipeline)
    critical_threshold: 7200s
    
  item_feature_freshness:
    description: "Time since last item_features update"
    target: 86400s        # 24 hours (daily pipeline)
    critical_threshold: 172800s
    
  training_dataset_generation:
    description: "Time to generate full training dataset"
    target: 7200s         # 2 hours
    critical_threshold: 14400s
    
  feature_serving_latency:
    description: "Feature store read latency for inference"
    target_p99: 10ms      # Online serving requirement
    critical_threshold: 50ms

# Iceberg-specific metrics to monitor
iceberg_health:
  - metric: "files_per_partition"
    alert_threshold: 1000   # Too many small files
    action: "trigger_compaction"
    
  - metric: "orphan_files_size_gb"
    alert_threshold: 100
    action: "run_orphan_cleanup"
    
  - metric: "snapshot_count"
    alert_threshold: 5000
    action: "expire_snapshots"
    
  - metric: "manifest_file_count"
    alert_threshold: 500    # Too many manifests slows planning
    action: "rewrite_manifests"
```

---

## Scale Numbers: What This Handles

| Dimension | Volume | Storage | Notes |
|-----------|--------|---------|-------|
| Raw events/month | 50B rows | ~60TB (Zstd) | ~1.2KB avg compressed row |
| Events retained | 2 years | ~1.4PB | Older data in cheaper storage class |
| User features | 500M rows | ~2TB | 128-dim embeddings dominate size |
| Item features | 100M rows | ~800GB | Larger per-row (multiple embeddings) |
| Training dataset (single) | ~5B examples | ~6TB | Generated on-demand, GC'd after 30 days |
| Interaction matrix (daily) | ~10B edges | ~200GB/day | Sparse, heavily compressed |
| Daily Spark compute | ~200K vCPU-hours | - | Auto-scaling EMR clusters |
| Flink streaming | ~500 vCPUs sustained | - | Always-on for real-time features |

### Cost Optimization

- **S3 Intelligent-Tiering** on events > 30 days: saves ~40% on storage
- **Iceberg's file pruning** reduces Athena scan costs by 100-1000x vs full scans
- **Compaction** reduces file count from millions to thousands: faster metadata operations, cheaper LIST calls
- **Partition evolution**: started with `months()`, evolved to `days()` as volume grew — zero data rewrite

---

## dbt Integration

```yaml
# dbt_project.yml (relevant section)
models:
  recommendation:
    materialized: incremental
    incremental_strategy: merge
    file_format: iceberg
    
    staging:
      +materialized: ephemeral
      
    features:
      +materialized: incremental
      +incremental_strategy: merge
      +unique_key: ['user_id']
      +merge_update_columns: ['views_1d', 'views_7d', 'clicks_7d', 'computed_at']
```

```sql
-- models/features/user_features_daily.sql
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='user_id',
        file_format='iceberg',
        partition_by=['bucket(128, user_id)'],
        table_properties={
            'write.update.mode': 'merge-on-read',
            'write.parquet.compression-codec': 'zstd'
        }
    )
}}

WITH daily_events AS (
    SELECT *
    FROM {{ ref('stg_events') }}
    WHERE event_date = '{{ var("run_date") }}'
),

aggregated AS (
    SELECT
        user_id,
        COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views_1d,
        COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks_1d,
        COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) AS purchases_1d,
        CURRENT_TIMESTAMP AS computed_at
    FROM daily_events
    GROUP BY user_id
)

SELECT * FROM aggregated
```

---

## Incremental Reads for Streaming Feature Updates

Iceberg's incremental read capability enables Flink to process only new data:

```java
// Flink Iceberg source: read only new appends since last checkpoint
TableLoader tableLoader = TableLoader.fromCatalog(
    catalogLoader, TableIdentifier.of("recommendation", "events"));

DataStream<RowData> newEvents = FlinkSource.forRowData()
    .tableLoader(tableLoader)
    .streaming(true)
    .startSnapshotId(lastProcessedSnapshotId)  // Resume from checkpoint
    .build();

// Process new events → update real-time features in Redis/DynamoDB
newEvents
    .keyBy(row -> row.getLong(/* user_id position */))
    .process(new RealTimeFeatureUpdater())
    .addSink(new FeatureStoreSink());
```

This replaces the pattern of "re-scan entire table" with "read only the delta" — critical when 50B rows exist but only 1M are new since last read.

---

## Key Takeaways

1. **Iceberg's partition pruning + column statistics** turn a 14TB scan into a 200MB read — this makes ad-hoc analysis economically feasible at 50B events/month.

2. **Time-travel snapshots** solve ML reproducibility: pin the exact data a model trained on, audit later.

3. **MERGE INTO** handles the dual nature of this pipeline: events are append-only, features are upsert.

4. **Partition evolution** means you never have to rewrite petabytes when access patterns change — start with monthly, move to daily, add bucketing, all without data migration.

5. **Concurrent access** (Spark batch + Flink streaming + Trino analysis) works safely through MVCC — no more "wait for the batch job to finish before querying."

6. **Compaction as a first-class operation** keeps the table healthy despite high-frequency streaming writes generating thousands of small files per hour.
