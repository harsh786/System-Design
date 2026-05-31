# Architecture 04: ML Feature Store

## Why Feature Stores Exist

```
THE PROBLEM WITHOUT A FEATURE STORE:
═════════════════════════════════════

Data Scientist Alice:
  "I computed customer_avg_order_value in my Jupyter notebook.
   I used pandas, queried the orders table, did a 90-day rolling avg."

ML Engineer Bob (deploying Alice's model to production):
  "How exactly did you compute that feature? Let me rewrite it in Java/SQL
   for the online serving path. Hope I get the same numbers..."

Production Issue (3 months later):
  "Model accuracy dropped. Turns out Bob's Java implementation handles
   NULL orders differently than Alice's pandas code. The feature values
   DRIFT between training and serving."

THIS IS CALLED: TRAINING-SERVING SKEW
  • #1 cause of ML model degradation in production
  • Extremely hard to debug (model seems fine, but inputs are wrong)
  • Gets worse with more features and more models

FEATURE STORE SOLVES:
  ✓ Single definition of each feature (computed ONCE, used everywhere)
  ✓ Same code produces training data AND serving data (no skew)
  ✓ Feature reuse across teams (don't recompute same thing 10 times)
  ✓ Point-in-time correctness for training (no data leakage)
  ✓ Low-latency serving for inference (pre-computed, cached)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML FEATURE STORE ARCHITECTURE                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  FEATURE DEFINITIONS (Code as Source of Truth)                    │       │
│  │  ─────────────────────────────────────────────                    │       │
│  │                                                                   │       │
│  │  @feature_view(                                                   │       │
│  │    entities=[customer],                                           │       │
│  │    ttl=timedelta(hours=24),                                       │       │
│  │    online=True,                                                   │       │
│  │    offline=True,                                                  │       │
│  │  )                                                                │       │
│  │  def customer_features(orders: DataFrame) -> DataFrame:           │       │
│  │    return orders.group_by("customer_id").agg(                     │       │
│  │      avg("amount").alias("avg_order_value"),                      │       │
│  │      count("*").alias("total_orders"),                            │       │
│  │      max("order_date").alias("last_order_date"),                  │       │
│  │    )                                                              │       │
│  │                                                                   │       │
│  │  → SAME definition used for batch (training) and online (serving) │       │
│  └──────────────────────────────────┬───────────────────────────────┘       │
│                                      │                                       │
│  ┌───────────────────────────────────┼──────────────────────────────┐       │
│  │                                   │                               │       │
│  │  ┌───────────────────┐    ┌───────▼──────────┐                   │       │
│  │  │  OFFLINE STORE     │    │ MATERIALIZATION   │                   │       │
│  │  │  (Batch Features)  │    │ (Scheduled Jobs)  │                   │       │
│  │  │                    │    │                   │                   │       │
│  │  │  Storage:          │    │ Spark/Flink job:  │                   │       │
│  │  │  • Delta Lake / S3 │◀───│ Compute features  │                   │       │
│  │  │  • Partitioned by  │    │ every 15 min /    │                   │       │
│  │  │    entity + time   │    │ hourly / daily    │                   │       │
│  │  │                    │    │                   │                   │       │
│  │  │  Used for:         │    │ Write to both:    │───┐               │       │
│  │  │  • Training data   │    │ offline + online  │   │               │       │
│  │  │  • Batch scoring   │    └───────────────────┘   │               │       │
│  │  │  • Backfilling     │                            │               │       │
│  │  │  • Point-in-time   │                            ▼               │       │
│  │  │    joins           │    ┌───────────────────────────┐           │       │
│  │  └───────────────────┘    │  ONLINE STORE              │           │       │
│  │                            │  (Real-time Features)      │           │       │
│  │                            │                            │           │       │
│  │                            │  Storage:                  │           │       │
│  │                            │  • Redis / DynamoDB        │           │       │
│  │                            │  • Key: entity_id          │           │       │
│  │                            │  • Value: latest features  │           │       │
│  │                            │                            │           │       │
│  │                            │  Latency: < 5ms P99        │           │       │
│  │                            │  QPS: 100,000+             │           │       │
│  │                            │                            │           │       │
│  │                            │  Used for:                 │           │       │
│  │                            │  • Real-time inference     │           │       │
│  │                            │  • Model serving           │           │       │
│  │                            └───────────────────────────┘           │       │
│  │                                                                    │       │
│  └────────────────────────────────────────────────────────────────────┘      │
│                                                                              │
│  CONSUMERS                                                                   │
│  ═════════                                                                   │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │ TRAINING       │  │ BATCH SCORING  │  │ ONLINE SERVING │                │
│  │                │  │                │  │                │                │
│  │ get_historical │  │ get_historical │  │ get_online     │                │
│  │ _features(     │  │ _features(     │  │ _features(     │                │
│  │   entity_ids,  │  │   entity_ids,  │  │   entity_ids   │                │
│  │   timestamps   │  │   timestamps   │  │ )              │                │
│  │ )              │  │ )              │  │                │                │
│  │                │  │                │  │ → Redis lookup │                │
│  │ → Point-in-   │  │ → Batch read   │  │ → < 5ms       │                │
│  │   time join    │  │   from offline │  │ → Latest value │                │
│  │ → No leakage  │  │   store        │  │                │                │
│  └────────────────┘  └────────────────┘  └────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Point-in-Time Correctness (Critical Concept)

```
WHY POINT-IN-TIME MATTERS:
══════════════════════════

WRONG (Data Leakage):
  Training sample: Predict if customer will churn on Jan 15.
  Feature: avg_order_value computed using ALL orders (including Jan 16-31)
  → Model sees FUTURE data during training → inflated accuracy
  → Model fails in production (can't see future at serving time)

CORRECT (Point-in-Time):
  Training sample: Predict if customer will churn on Jan 15.
  Feature: avg_order_value AS OF Jan 14 (only orders before prediction time)
  → Model only sees past data → realistic accuracy
  → Production behavior matches training behavior

IMPLEMENTATION:

  Feature table (offline store):
  ┌─────────────┬──────────────────┬──────────────────┬────────────┐
  │ customer_id │ event_timestamp  │ avg_order_value  │ total_orders│
  ├─────────────┼──────────────────┼──────────────────┼────────────┤
  │ C-001       │ 2024-01-01       │ 45.00            │ 5          │
  │ C-001       │ 2024-01-08       │ 52.00            │ 7          │ ← use this for
  │ C-001       │ 2024-01-15       │ 48.00            │ 8          │   Jan 15 prediction
  │ C-001       │ 2024-01-22       │ 55.00            │ 10         │
  └─────────────┴──────────────────┴──────────────────┴────────────┘
  
  Point-in-time join:
  SELECT f.*
  FROM features f
  WHERE f.customer_id = 'C-001'
    AND f.event_timestamp <= '2024-01-14'  -- strictly BEFORE prediction time
  ORDER BY f.event_timestamp DESC
  LIMIT 1;
  
  → Returns row from Jan 8 (last known state BEFORE prediction date)
```

## Streaming Features (Real-Time Computation)

```
SOME FEATURES CAN'T WAIT FOR BATCH:
═══════════════════════════════════

Batch features (materialized hourly/daily):
  • avg_order_value_90d (doesn't change fast)
  • total_lifetime_orders (changes slowly)
  • customer_segment (changes weekly)

Streaming features (must be real-time):
  • transactions_last_5_min (fraud detection needs this NOW)
  • session_page_views (real-time personalization)
  • error_count_last_minute (operational alerting)

STREAMING FEATURE PIPELINE:
  
  Kafka → Flink → Online Store (Redis)
  
  Flink job:
  events
    .keyBy(event -> event.customerId)
    .window(SlidingEventTimeWindows.of(Time.minutes(5), Time.minutes(1)))
    .aggregate(new CountAggregator())
    .addSink(new RedisSink("customer_txn_count_5min"));
  
  → Feature updated every minute with sliding 5-min window
  → Available in Redis for inference within seconds

ARCHITECTURE FOR STREAMING FEATURES:
  
  ┌────────────┐      ┌─────────┐      ┌───────────────┐
  │ Kafka      │─────▶│ Flink   │─────▶│ Redis         │
  │ (events)   │      │ (window │      │ (online store)│
  │            │      │  agg)   │      │               │
  └────────────┘      └─────────┘      └───────┬───────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │ Model Server  │
                                        │ (inference)   │
                                        └───────────────┘
```

## Technology Choices

```
FEATURE STORE PLATFORMS:
═══════════════════════

┌───────────────────┬────────────────────────────────────────────────────────┐
│ Platform          │ When to Use                                             │
├───────────────────┼────────────────────────────────────────────────────────┤
│ Feast (OSS)       │ • Full control, self-hosted                             │
│                   │ • Works with any infra (S3, Redis, BigQuery)            │
│                   │ • Python SDK, dbt integration                           │
│                   │ • Good for: teams that want flexibility                 │
├───────────────────┼────────────────────────────────────────────────────────┤
│ Tecton            │ • Managed service (by Feast creators)                   │
│                   │ • Best streaming feature support                        │
│                   │ • Built-in monitoring + alerting                        │
│                   │ • Good for: production-critical ML at scale             │
├───────────────────┼────────────────────────────────────────────────────────┤
│ Databricks        │ • Already on Databricks                                 │
│ Feature Store     │ • Tight Unity Catalog integration                       │
│                   │ • Lineage + governance built-in                         │
│                   │ • Good for: Databricks-centric shops                    │
├───────────────────┼────────────────────────────────────────────────────────┤
│ SageMaker         │ • AWS-native, minimal infra management                  │
│ Feature Store     │ • Offline (S3) + Online (DynamoDB) built-in             │
│                   │ • Good for: AWS shops wanting managed solution           │
├───────────────────┼────────────────────────────────────────────────────────┤
│ Vertex AI         │ • GCP-native                                            │
│ Feature Store     │ • BigQuery offline + Bigtable online                    │
│                   │ • Good for: GCP shops                                   │
└───────────────────┴────────────────────────────────────────────────────────┘

RECOMMENDATION:
  Starting out / small team: Feast (free, learn the concepts)
  Production at scale: Tecton (if budget allows) or Databricks FS
  Cloud-native / simple: SageMaker or Vertex (managed, less flexible)
```

## Sizing & Cost

```
SCENARIO: 50 ML Models, 500 Features, 100M Entities
════════════════════════════════════════════════════

OFFLINE STORE (Delta Lake on S3):
  500 features × 100M entities × 52 weeks of history
  = 2.6 trillion feature values
  Storage: ~5 TB (compressed Parquet)
  Cost: 5 TB × $0.023/GB = $115/month
  
  Training read: Fetch 100M entities × 50 features × 12 months
  = Spark job scans ~500 GB per training run
  Compute: 10 r5.2xlarge × 30 min = ~$3 per training job

ONLINE STORE (Redis Cluster):
  100M entities × 50 features each × 100 bytes avg
  = 500 GB in Redis
  
  Redis cluster: 10 × r6g.2xlarge (52 GB RAM each) = 520 GB capacity
  Cost: 10 × $0.40/hr × 24 × 30 = $2,880/month
  
  QPS: 100,000 feature lookups/sec
  Latency: P50 < 1ms, P99 < 5ms

MATERIALIZATION (Spark jobs):
  500 features computed hourly
  Average compute: 5 min per feature group (batched)
  Cluster: 20 r5.2xlarge × 2 hours/day
  Cost: 20 × $0.504/hr × 2 × 30 = $604/month

TOTAL MONTHLY COST:
  Offline store: $115
  Online store: $2,880
  Materialization: $604
  Monitoring/Infra: ~$500
  TOTAL: ~$4,100/month (~$50,000/year)
  
  PER MODEL: ~$1,000/year (cheap for production ML infrastructure)
```

## Feature Monitoring & Drift Detection

```
CRITICAL MONITORING:
═══════════════════

1. FEATURE FRESHNESS:
   "When was this feature last updated?"
   Alert: If feature > 2x expected refresh interval old
   Example: Hourly feature not updated for 3 hours → stale inference

2. FEATURE DISTRIBUTION DRIFT:
   "Are feature values changing unexpectedly?"
   Compare: Current distribution vs training distribution
   Metrics: KL divergence, PSI (Population Stability Index), JS divergence
   Alert: If PSI > 0.2 (significant drift) → retrain model
   
3. FEATURE COVERAGE:
   "What % of inference requests have all features available?"
   Target: > 99.5% feature availability
   Alert: If feature is NULL for > 1% of requests → data issue
   
4. ONLINE-OFFLINE CONSISTENCY:
   "Do online values match what offline would compute?"
   Check: Sample entities, compute offline, compare with online store
   Tolerance: < 0.1% difference
   Alert: If divergence → training-serving skew (the whole point of feature stores!)

MONITORING ARCHITECTURE:
  
  [Feature Store] → [Metrics Exporter] → [Prometheus/DataDog]
                                                    │
                                        ┌───────────▼───────────┐
                                        │ Grafana Dashboard     │
                                        │ • Freshness per feat  │
                                        │ • Drift scores        │
                                        │ • Coverage %          │
                                        │ • Online/Offline diff │
                                        └───────────────────────┘
```
