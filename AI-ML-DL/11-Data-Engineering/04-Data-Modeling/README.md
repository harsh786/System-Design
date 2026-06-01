# Data Modeling for ML

## Why Data Modeling Matters for ML

Bad data models lead to:
- Slow feature queries (hours instead of seconds)
- Data leakage in training (future data leaking into past)
- Inconsistent features between training and serving
- Impossible point-in-time correctness

---

## Relational Modeling (Normalization)

```
┌─────────────────────────────────────────────────────────────┐
│  NORMAL FORMS                                                │
├─────────────────────────────────────────────────────────────┤
│  1NF: Atomic values, no repeating groups                    │
│  2NF: 1NF + no partial dependencies on composite keys       │
│  3NF: 2NF + no transitive dependencies                      │
│  BCNF: Every determinant is a candidate key                 │
│                                                              │
│  For OLTP (apps): Normalize to 3NF (reduce redundancy)      │
│  For OLAP (analytics/ML): Denormalize (reduce joins)        │
└─────────────────────────────────────────────────────────────┘
```

```sql
-- 1NF violation (repeating groups)
-- ❌ user_id | tags: "ml,python,sql"
-- ✅ Separate table: user_tags(user_id, tag)

-- 3NF: Remove transitive dependencies
-- ❌ orders(order_id, user_id, user_email)  -- email depends on user_id, not order_id
-- ✅ orders(order_id, user_id) + users(user_id, email)
```

---

## Dimensional Modeling (Star Schema)

```
                    ┌─────────────────┐
                    │   dim_users     │
                    │ ─────────────── │
                    │ user_key (SK)   │
                    │ user_id (NK)    │
                    │ name            │
                    │ country         │
                    │ segment         │
                    └────────┬────────┘
                             │
┌──────────────┐    ┌───────┴────────────┐    ┌──────────────┐
│  dim_date    │    │   fact_orders      │    │ dim_product  │
│ ──────────── │    │ ────────────────── │    │ ──────────── │
│ date_key(SK) ├────┤ order_id           │────┤ product_key  │
│ full_date    │    │ user_key (FK)      │    │ product_id   │
│ year         │    │ product_key (FK)   │    │ name         │
│ quarter      │    │ date_key (FK)      │    │ category     │
│ month        │    │ quantity           │    │ brand        │
│ day_of_week  │    │ amount             │    └──────────────┘
│ is_weekend   │    │ discount           │
└──────────────┘    └────────────────────┘

Star Schema: Fact table at center, dimension tables around it.
- Facts: Measurable events (orders, clicks, transactions)
- Dimensions: Context (who, what, when, where)
```

### When to Use What

| Model | Use Case | Query Speed | Storage |
|-------|----------|-------------|---------|
| 3NF | OLTP apps | Fast writes | Minimal |
| Star Schema | BI/Analytics | Fast reads | Moderate |
| OBT (One Big Table) | ML Training | Fastest reads | High |
| Data Vault | Enterprise, audit | Flexible | High |

---

## Slowly Changing Dimensions (SCD)

```sql
-- SCD Type 1: Overwrite (lose history)
UPDATE dim_users SET country = 'UK' WHERE user_id = 123;

-- SCD Type 2: Add new row (keep full history) ← Most common for ML
-- dim_users
-- | user_key | user_id | country | valid_from | valid_to   | is_current |
-- | 1        | 123     | US      | 2020-01-01 | 2024-06-15 | false      |
-- | 2        | 123     | UK      | 2024-06-15 | 9999-12-31 | true       |

-- Point-in-time lookup for ML (critical for avoiding data leakage!)
SELECT f.*, d.country, d.segment
FROM fact_orders f
JOIN dim_users d ON f.user_key = d.user_key
    AND f.order_date BETWEEN d.valid_from AND d.valid_to;

-- SCD Type 3: Add column for previous value
-- | user_id | current_country | previous_country | change_date |
```

---

## One Big Table (OBT) for ML

```sql
-- Denormalized table optimized for ML training
CREATE TABLE ml_training_data AS
SELECT
    -- User features
    u.user_id,
    u.signup_date,
    u.country,
    u.plan_type,
    DATE_DIFF(CURRENT_DATE, u.signup_date, DAY) AS account_age_days,
    
    -- Order aggregates
    COUNT(o.order_id) AS total_orders,
    SUM(o.total_amount) AS lifetime_value,
    AVG(o.total_amount) AS avg_order_value,
    STDDEV(o.total_amount) AS std_order_value,
    MAX(o.order_date) AS last_order_date,
    DATE_DIFF(CURRENT_DATE, MAX(o.order_date), DAY) AS recency_days,
    
    -- Product diversity
    COUNT(DISTINCT p.category) AS categories_purchased,
    
    -- Event features
    COUNT(DISTINCT e.session_id) AS total_sessions,
    SUM(CASE WHEN e.event_type = 'page_view' THEN 1 ELSE 0 END) AS total_page_views,
    
    -- Target variable
    CASE WHEN MAX(o.order_date) < CURRENT_DATE - 90 THEN 1 ELSE 0 END AS churned
    
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN events e ON u.user_id = e.user_id
GROUP BY u.user_id, u.signup_date, u.country, u.plan_type;
```

**Pros:** Fast training reads, no joins at training time, simple  
**Cons:** Expensive to build, data redundancy, staleness

---

## Feature Stores

```
┌────────────────────────────────────────────────────────────────┐
│                    FEATURE STORE ARCHITECTURE                    │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Batch Pipeline ──→ Offline Store (S3/BQ) ──→ Training         │
│                           │                                     │
│                           │ Materialize                         │
│                           ▼                                     │
│  Stream Pipeline ──→ Online Store (Redis/DynamoDB) ──→ Serving │
│                                                                 │
│  Key Properties:                                                │
│  • Feature reuse across models                                  │
│  • Point-in-time correctness (no leakage)                      │
│  • Consistent features: training = serving                      │
│  • Feature discovery and documentation                          │
└────────────────────────────────────────────────────────────────┘
```

### Online vs Offline Features

| | Offline Store | Online Store |
|---|---|---|
| Purpose | Training data | Real-time serving |
| Latency | Minutes-hours | < 10ms |
| Storage | Data lake/warehouse | Redis, DynamoDB |
| Data | Historical (time-travel) | Latest values only |
| Cost | Cheap (object storage) | Expensive (in-memory) |

### Point-in-Time Correctness

```
Timeline:  ──────────────────────────────────────────→ time
User signs up         Orders          Prediction
     │                  │ │              │
     ▼                  ▼ ▼              ▼
  Jan 1              Mar  Apr          Jun 1

For a model predicting churn on Jun 1:
  ✅ Features computed from data BEFORE Jun 1
  ❌ Features using data from AFTER Jun 1 (DATA LEAKAGE!)

For training on historical data (e.g., predict churn on Mar 1):
  ✅ Features from data before Mar 1 only
  ❌ Using Apr order data to predict Mar churn
```

---

## Feast Feature Store

```python
# feature_repo/features.py
from feast import Entity, Feature, FeatureView, FileSource, ValueType
from feast.types import Float32, Int64
from datetime import timedelta

# Entity
user = Entity(name="user_id", value_type=ValueType.INT64)

# Source
user_features_source = FileSource(
    path="s3://features/user_features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# Feature View
user_features = FeatureView(
    name="user_features",
    entities=[user],
    ttl=timedelta(days=1),
    schema=[
        Feature(name="total_orders", dtype=Int64),
        Feature(name="lifetime_value", dtype=Float32),
        Feature(name="avg_order_value", dtype=Float32),
        Feature(name="days_since_last_order", dtype=Int64),
        Feature(name="total_sessions", dtype=Int64),
    ],
    source=user_features_source,
    online=True,  # Materialize to online store
)
```

```python
# Training: Point-in-time join
from feast import FeatureStore

store = FeatureStore(repo_path="feature_repo/")

# Entity DataFrame with timestamps (when each prediction would be made)
entity_df = pd.DataFrame({
    "user_id": [1, 2, 3, 1, 2],
    "event_timestamp": pd.to_datetime([
        "2024-01-15", "2024-01-15", "2024-01-15",
        "2024-03-01", "2024-03-01"
    ])
})

# Get historical features (point-in-time correct!)
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "user_features:total_orders",
        "user_features:lifetime_value",
        "user_features:avg_order_value",
    ]
).to_df()

# Serving: Get latest features for real-time inference
online_features = store.get_online_features(
    features=["user_features:total_orders", "user_features:lifetime_value"],
    entity_rows=[{"user_id": 123}]
).to_dict()
```

---

## Event Sourcing for ML

```
┌─────────────────────────────────────────────────────────────┐
│  Instead of storing current state, store ALL events:         │
│                                                              │
│  Event Log:                                                  │
│  ┌──────────────────────────────────────────────────┐       │
│  │ {user:1, type:"signup", ts:"2024-01-01"}         │       │
│  │ {user:1, type:"order", amount:50, ts:"2024-01-15"}│      │
│  │ {user:1, type:"plan_change", plan:"pro", ts:...}  │      │
│  │ {user:1, type:"order", amount:120, ts:"2024-02-01"}│     │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  Benefits for ML:                                            │
│  • Perfect point-in-time reconstruction                      │
│  • Any feature can be computed for any historical moment     │
│  • No data loss from overwrites                              │
│  • Natural fit for streaming feature computation             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Vault Modeling

```
┌─────────┐    ┌──────────────┐    ┌─────────┐
│   HUB   │    │     LINK     │    │   HUB   │
│ (Users) │◄───┤ (User-Order) │───►│(Orders) │
│         │    └──────────────┘    │         │
└────┬────┘                        └────┬────┘
     │                                  │
┌────┴─────┐                      ┌────┴─────┐
│SATELLITE │                      │SATELLITE │
│(User     │                      │(Order    │
│ details) │                      │ details) │
│ load_ts  │                      │ load_ts  │
└──────────┘                      └──────────┘

- Hubs: Business keys (immutable)
- Links: Relationships between hubs
- Satellites: Descriptive attributes (versioned with timestamps)

Use for: Enterprise, audit trails, multiple source integration
```

---

## Interview Questions

1. **Star schema vs snowflake schema?**
   - Star: denormalized dimensions (one join). Snowflake: normalized dimensions (multiple joins). Star is faster for queries.

2. **What is data leakage and how does data modeling prevent it?**
   - Using future information to predict the past. SCD Type 2 + point-in-time joins ensure features reflect only past data.

3. **When would you use a feature store vs a simple table?**
   - Feature store when: multiple models share features, need online serving, need point-in-time correctness, need feature versioning.

4. **Explain SCD Type 2 and why it matters for ML.**
   - Tracks full history with valid_from/valid_to dates. Enables accurate historical feature reconstruction without leakage.

5. **What's the trade-off between normalized and denormalized models?**
   - Normalized: less storage, consistency, slower reads. Denormalized: faster reads, redundancy, harder updates.

6. **How do you handle feature freshness in online serving?**
   - TTL on online store, streaming updates for critical features, batch for stable features, staleness monitoring.

7. **What's the difference between a fact and a dimension?**
   - Facts: measurable events/metrics (numeric, additive). Dimensions: descriptive context (who, what, when, where).

8. **How do you handle late-arriving facts in a star schema?**
   - Special "unknown" dimension members, periodic reprocessing, or separate reconciliation tables.

9. **What's the One Big Table approach and its trade-offs?**
   - Single denormalized table for ML. Pro: fast reads, simple. Con: expensive builds, staleness, storage.

10. **How does Feast handle point-in-time correctness?**
    - Temporal joins: for each entity+timestamp pair, retrieves feature values as of that timestamp (not latest).

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|---|---|---|
| Using latest features for historical training | Data leakage | Point-in-time joins |
| One giant fact table with all metrics | Slow, hard to maintain | Separate fact tables by process |
| No surrogate keys | Can't handle SCD | Always use surrogate keys + natural keys |
| Storing computed features in source DB | Coupling, perf impact | Separate feature tables |
| No schema versioning | Breaking changes | Schema registry, migrations |
| Features computed differently in training vs serving | Training-serving skew | Feature store with single definition |
