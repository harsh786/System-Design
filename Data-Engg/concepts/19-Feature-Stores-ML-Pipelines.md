# Feature Stores and ML Data Pipelines

## 1. Feature Store Fundamentals

### The Problem Feature Stores Solve

Without a feature store, ML teams face:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Problems Without Feature Stores                    │
│                                                                      │
│  1. TRAINING-SERVING SKEW                                           │
│     - Features computed differently in training vs serving           │
│     - Subtle bugs cause model degradation in production              │
│                                                                      │
│  2. FEATURE DUPLICATION                                              │
│     - Team A computes "user_lifetime_value" one way                  │
│     - Team B recomputes it slightly differently                      │
│     - No single source of truth for feature definitions              │
│                                                                      │
│  3. DATA LEAKAGE                                                     │
│     - Using future data when training (point-in-time violation)      │
│     - Model appears great in training, fails in production           │
│                                                                      │
│  4. SLOW ITERATION                                                   │
│     - Each new model requires rebuilding feature pipelines           │
│     - No reuse across teams or models                                │
│                                                                      │
│  5. ONLINE SERVING LATENCY                                           │
│     - Computing features at request time is too slow (>100ms)        │
│     - Need pre-computed features with low-latency lookup             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Online vs Offline Store

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Feature Store Dual Architecture                    │
│                                                                      │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐│
│  │      OFFLINE STORE           │  │       ONLINE STORE           ││
│  │                              │  │                              ││
│  │  Purpose: Training data      │  │  Purpose: Low-latency        ││
│  │           generation         │  │           serving            ││
│  │                              │  │                              ││
│  │  Access: Batch reads         │  │  Access: Point lookups       ││
│  │          (minutes-hours)     │  │          (<10ms p99)         ││
│  │                              │  │                              ││
│  │  Storage: S3/GCS, Redshift,  │  │  Storage: Redis,            ││
│  │           BigQuery, Spark    │  │           DynamoDB, Bigtable ││
│  │                              │  │                              ││
│  │  Data: Full history          │  │  Data: Latest values only    ││
│  │        (time-series)         │  │        (key-value)           ││
│  │                              │  │                              ││
│  │  Users: Data scientists      │  │  Users: ML services          ││
│  │         (training)           │  │         (inference)          ││
│  └──────────────────────────────┘  └──────────────────────────────┘│
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              MATERIALIZATION                                    │  │
│  │                                                                │  │
│  │  Offline → Online: Batch job copies latest feature values      │  │
│  │  Streaming: Real-time updates to online store                  │  │
│  │  Push: Application writes directly to online store             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Point-in-Time Correctness

The most critical concept in feature stores:

```
Timeline:
─────────────────────────────────────────────────────────────────────
  t1        t2        t3        t4        t5        t6
  │         │         │         │         │         │
  Feature   Feature   Label     Feature   Feature   Label
  Update    Update    Event     Update    Update    Event
  v=10      v=20      (buy)     v=30      v=40      (no buy)

CORRECT (point-in-time):
  Training example 1: features at t2 (v=20) → label at t3 (buy)
  Training example 2: features at t5 (v=40) → label at t6 (no buy)

INCORRECT (data leakage):
  Training example 1: features at t4 (v=30) → label at t3 (buy)
  ← Uses future feature values! Model cheats during training.
```

### Feature Reuse Across Teams

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Feature Reuse Architecture                         │
│                                                                      │
│  Feature Definitions (shared registry):                              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  user_features:                                                 │ │
│  │    - user_lifetime_value (computed: sum of all purchases)       │ │
│  │    - user_activity_7d (computed: events in last 7 days)         │ │
│  │    - user_segment (computed: k-means cluster assignment)        │ │
│  │                                                                 │ │
│  │  product_features:                                              │ │
│  │    - product_popularity_score (computed: views/impressions)     │ │
│  │    - product_avg_rating (computed: mean of ratings)             │ │
│  │    - product_return_rate (computed: returns/purchases)          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Consumers:                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Recommender  │  │  Fraud       │  │  Pricing     │             │
│  │ Model        │  │  Detection   │  │  Model       │             │
│  │              │  │              │  │              │             │
│  │ Uses:        │  │ Uses:        │  │ Uses:        │             │
│  │ - user_ltv   │  │ - user_ltv   │  │ - product_   │             │
│  │ - product_   │  │ - user_      │  │   popularity │             │
│  │   popularity │  │   activity   │  │ - product_   │             │
│  │ - user_      │  │              │  │   return_rate│             │
│  │   segment    │  │              │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Feast Deep Dive

### Overview

Feast (Feature Store) is the most widely adopted open-source feature store.
It provides a declarative approach to feature management with pluggable backends.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Feast Architecture                              │
│                                                                      │
│  ┌──────────────┐     ┌──────────────────────────────────────────┐ │
│  │  Feature     │     │          Feature Registry                 │ │
│  │  Repo        │────▶│  (SQLite / S3 / GCS / Snowflake)         │ │
│  │  (Python)    │     │  - Feature definitions                    │ │
│  │              │     │  - Entity definitions                     │ │
│  │  - entities  │     │  - Data source configs                    │ │
│  │  - features  │     │  - Materialization state                  │ │
│  │  - services  │     └──────────────────────────────────────────┘ │
│  └──────────────┘                                                   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Offline Store                                │  │
│  │         (S3+Athena / Redshift / BigQuery / Spark)             │  │
│  │                                                                │  │
│  │  - Historical feature retrieval                                │  │
│  │  - Point-in-time joins                                        │  │
│  │  - Training dataset generation                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                           │
│                          │ Materialization                            │
│                          ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Online Store                                 │  │
│  │            (Redis / DynamoDB / Bigtable / Postgres)            │  │
│  │                                                                │  │
│  │  - Low-latency feature retrieval (<10ms)                      │  │
│  │  - Latest feature values per entity                           │  │
│  │  - Key-value lookup by entity key                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                           │
│                          │ Serves                                    │
│                          ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Feature Server                                 │  │
│  │          (Python HTTP / Go gRPC / AWS Lambda)                  │  │
│  │                                                                │  │
│  │  - Online feature serving API                                  │  │
│  │  - Feature transformation (on-demand)                          │  │
│  │  - Request logging for monitoring                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Complete Code Example

```python
"""Complete Feast feature store setup and usage."""

# ============================================================
# feature_repo/entities.py - Define entities
# ============================================================
from feast import Entity, ValueType

user = Entity(
    name="user_id",
    value_type=ValueType.INT64,
    description="Unique user identifier",
    join_keys=["user_id"],
)

product = Entity(
    name="product_id",
    value_type=ValueType.STRING,
    description="Product SKU identifier",
    join_keys=["product_id"],
)


# ============================================================
# feature_repo/features.py - Define feature views
# ============================================================
from feast import (
    FeatureView, Field, FileSource, RedshiftSource,
    OnDemandFeatureView, FeatureService, PushSource,
)
from feast.types import Float32, Float64, Int64, String
from feast.data_format import ParquetFormat
from datetime import timedelta

# Data source: S3 Parquet files (offline)
user_activity_source = FileSource(
    name="user_activity_source",
    path="s3://my-bucket/features/user_activity/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    created_timestamp_column="created_at",
)

# Alternative: Redshift source
user_profile_source = RedshiftSource(
    name="user_profile_source",
    query="""
        SELECT user_id, age, country, account_age_days,
               lifetime_value, event_timestamp
        FROM analytics.user_profiles
    """,
    timestamp_field="event_timestamp",
    database="analytics",
)

# Push source for real-time features
user_realtime_source = PushSource(
    name="user_realtime_push",
    batch_source=user_activity_source,  # Fallback for historical
)

# Feature View: User activity features (batch)
user_activity_fv = FeatureView(
    name="user_activity_features",
    entities=[user],
    schema=[
        Field(name="session_count_7d", dtype=Int64),
        Field(name="total_time_minutes_7d", dtype=Float64),
        Field(name="pages_viewed_7d", dtype=Int64),
        Field(name="last_active_days_ago", dtype=Int64),
        Field(name="avg_session_duration", dtype=Float64),
    ],
    source=user_activity_source,
    ttl=timedelta(days=1),  # Features expire after 1 day in online store
    online=True,
    tags={"team": "growth", "priority": "P0"},
)

# Feature View: User profile features
user_profile_fv = FeatureView(
    name="user_profile_features",
    entities=[user],
    schema=[
        Field(name="age", dtype=Int64),
        Field(name="country", dtype=String),
        Field(name="account_age_days", dtype=Int64),
        Field(name="lifetime_value", dtype=Float64),
    ],
    source=user_profile_source,
    ttl=timedelta(days=7),
    online=True,
    tags={"team": "identity"},
)

# On-Demand Feature View: Computed at request time
@on_demand_feature_view(
    sources=[user_activity_fv, user_profile_fv],
    schema=[
        Field(name="activity_per_account_age", dtype=Float64),
        Field(name="is_power_user", dtype=Int64),
    ],
)
def user_computed_features(inputs: dict) -> dict:
    """Features computed on-the-fly from other features."""
    import pandas as pd
    df = pd.DataFrame()

    activity = inputs["user_activity_features"]
    profile = inputs["user_profile_features"]

    df["activity_per_account_age"] = (
        activity["session_count_7d"] / profile["account_age_days"].clip(lower=1)
    )
    df["is_power_user"] = (activity["session_count_7d"] > 20).astype(int)
    return df


# Feature Service: Group features for a model
recommendation_service = FeatureService(
    name="recommendation_model_v2",
    features=[
        user_activity_fv[["session_count_7d", "avg_session_duration"]],
        user_profile_fv[["country", "lifetime_value"]],
        user_computed_features,
    ],
    tags={"model": "recommendation", "version": "v2"},
)


# ============================================================
# feature_repo/feature_store.yaml - Configuration
# ============================================================
FEATURE_STORE_YAML = """
project: my_ml_platform
provider: aws
registry:
  registry_type: sql
  path: postgresql://feast:feast@postgres:5432/feast_registry
  cache_ttl_seconds: 60

online_store:
  type: redis
  connection_string: redis-cluster.internal:6379,redis_password=secret
  redis_type: redis_cluster

offline_store:
  type: redshift
  region: us-east-1
  cluster_id: feast-redshift-cluster
  database: analytics
  user: feast_user
  s3_staging_location: s3://feast-staging/redshift/
  iam_role: arn:aws:iam::123456789:role/FeastRedshiftRole

entity_key_serialization_version: 2
"""


# ============================================================
# Training: Generate training dataset
# ============================================================
from feast import FeatureStore
import pandas as pd
from datetime import datetime

store = FeatureStore(repo_path="feature_repo/")

# Entity DataFrame: defines WHAT entities at WHAT timestamps
entity_df = pd.DataFrame({
    "user_id": [1001, 1002, 1003, 1004, 1005],
    "event_timestamp": [
        datetime(2024, 1, 10, 12, 0),
        datetime(2024, 1, 11, 8, 30),
        datetime(2024, 1, 11, 14, 0),
        datetime(2024, 1, 12, 9, 0),
        datetime(2024, 1, 12, 16, 45),
    ],
    "label": [1, 0, 1, 0, 1],  # Target variable
})

# Get historical features (point-in-time correct!)
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "user_activity_features:session_count_7d",
        "user_activity_features:avg_session_duration",
        "user_profile_features:lifetime_value",
        "user_profile_features:country",
        "user_computed_features:is_power_user",
    ],
).to_df()

print(training_df.head())
# user_id | event_timestamp | label | session_count_7d | avg_session_duration | ...
# Each row has features AS OF that timestamp (no leakage!)


# ============================================================
# Materialization: Offline → Online
# ============================================================
from datetime import datetime, timedelta

# Materialize features to online store
store.materialize(
    start_date=datetime(2024, 1, 1),
    end_date=datetime.utcnow(),
)

# Incremental materialization (only new data)
store.materialize_incremental(end_date=datetime.utcnow())


# ============================================================
# Online Serving: Low-latency feature retrieval
# ============================================================
# Get features for real-time inference
online_features = store.get_online_features(
    features=[
        "user_activity_features:session_count_7d",
        "user_activity_features:avg_session_duration",
        "user_profile_features:lifetime_value",
        "user_computed_features:is_power_user",
    ],
    entity_rows=[
        {"user_id": 1001},
        {"user_id": 1002},
    ],
).to_dict()

print(online_features)
# {
#   "user_id": [1001, 1002],
#   "session_count_7d": [15, 3],
#   "avg_session_duration": [12.5, 4.2],
#   "lifetime_value": [250.0, 45.0],
#   "is_power_user": [0, 0],
# }


# ============================================================
# Push-based ingestion (streaming/real-time)
# ============================================================
from feast import FeatureStore
import pandas as pd
from datetime import datetime

store = FeatureStore(repo_path="feature_repo/")

# Push real-time features (e.g., from Kafka consumer)
realtime_df = pd.DataFrame({
    "user_id": [1001],
    "session_count_7d": [16],  # Updated count
    "total_time_minutes_7d": [195.5],
    "pages_viewed_7d": [89],
    "last_active_days_ago": [0],
    "avg_session_duration": [12.2],
    "event_timestamp": [datetime.utcnow()],
})

store.push("user_realtime_push", realtime_df, to=PushMode.ONLINE_AND_OFFLINE)
```

### Feast on AWS (Production Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Feast on AWS Architecture                          │
│                                                                      │
│  ┌────────────────┐         ┌────────────────────────────────────┐ │
│  │  S3 Bucket     │         │  Feature Registry                   │ │
│  │  (Feature      │         │  (RDS PostgreSQL or S3)             │ │
│  │   Parquet)     │         └────────────────────────────────────┘ │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          ▼                                                           │
│  ┌────────────────┐    Materialization    ┌─────────────────────┐  │
│  │  Offline Store │ ──────────────────── ▶│   Online Store      │  │
│  │                │    (EMR / Lambda /    │                     │  │
│  │  - Redshift    │     ECS Fargate)     │  - DynamoDB         │  │
│  │  - Athena      │                      │  - ElastiCache      │  │
│  │  - Spark on EMR│                      │    (Redis)          │  │
│  └────────────────┘                      └──────────┬──────────┘  │
│                                                      │              │
│                                                      ▼              │
│                                           ┌─────────────────────┐  │
│                                           │  Feature Server     │  │
│                                           │                     │  │
│                                           │  Option A: Lambda   │  │
│                                           │  Option B: ECS/EKS  │  │
│                                           │  Option C: AppRunner│  │
│                                           └─────────────────────┘  │
│                                                      │              │
│                                                      ▼              │
│                                           ┌─────────────────────┐  │
│                                           │  ML Model Service   │  │
│                                           │  (SageMaker /       │  │
│                                           │   ECS / Lambda)     │  │
│                                           └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Feast Kubernetes Deployment

```yaml
# feast-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: feast-feature-server
  namespace: ml-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: feast-feature-server
  template:
    metadata:
      labels:
        app: feast-feature-server
    spec:
      containers:
        - name: feature-server
          image: feastdev/feature-server:0.35.0
          ports:
            - containerPort: 6566
          env:
            - name: FEATURE_STORE_YAML_BASE64
              valueFrom:
                secretKeyRef:
                  name: feast-config
                  key: feature_store_yaml
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
          readinessProbe:
            httpGet:
              path: /health
              port: 6566
            initialDelaySeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 6566
            initialDelaySeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: feast-feature-server
  namespace: ml-platform
spec:
  selector:
    app: feast-feature-server
  ports:
    - port: 6566
      targetPort: 6566
  type: ClusterIP
---
# Materialization CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: feast-materialize
  namespace: ml-platform
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: materialize
              image: my-registry/feast-materialize:latest
              command: ["feast", "materialize-incremental", "$(date -u +%Y-%m-%dT%H:%M:%S)"]
              env:
                - name: FEATURE_STORE_YAML_BASE64
                  valueFrom:
                    secretKeyRef:
                      name: feast-config
                      key: feature_store_yaml
              resources:
                requests:
                  cpu: "2"
                  memory: "8Gi"
          restartPolicy: OnFailure
```

---

## 3. AWS SageMaker Feature Store

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              AWS SageMaker Feature Store Architecture                 │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Feature Group                                │ │
│  │                                                                │ │
│  │  ┌─────────────────────┐    ┌─────────────────────────────┐  │ │
│  │  │   Online Store      │    │     Offline Store            │  │ │
│  │  │   (managed)         │    │     (S3 + Glue Catalog)      │  │ │
│  │  │                     │    │                              │  │ │
│  │  │  - <10ms lookups    │    │  - Parquet on S3             │  │ │
│  │  │  - Latest values    │    │  - Auto-registered in Glue   │  │ │
│  │  │  - Auto-scaled      │    │  - Queryable via Athena      │  │ │
│  │  │  - Encryption       │    │  - Time-travel queries       │  │ │
│  │  └─────────────────────┘    └─────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Ingestion:                                                          │
│  - PutRecord API (real-time, single records)                        │
│  - Batch ingestion via SageMaker Processing Jobs                     │
│  - Streaming ingestion via Kinesis Data Streams                      │
│                                                                      │
│  Retrieval:                                                          │
│  - GetRecord / BatchGetRecord (online, <10ms)                       │
│  - Athena SQL queries (offline, historical)                          │
│  - SageMaker Training integration (automatic)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Code Example

```python
"""AWS SageMaker Feature Store - Complete example."""
import boto3
import sagemaker
from sagemaker.feature_store.feature_group import FeatureGroup
from sagemaker.feature_store.feature_definition import (
    FeatureDefinition, FeatureTypeEnum
)
from sagemaker.session import Session
import pandas as pd
import time

sagemaker_session = Session()
role = sagemaker.get_execution_role()
region = boto3.session.Session().region_name

# Define Feature Group
user_feature_group = FeatureGroup(
    name="user-engagement-features",
    sagemaker_session=sagemaker_session,
)

# Define schema
user_feature_group.load_feature_definitions(
    data_frame=pd.DataFrame({
        "user_id": pd.Series(dtype="str"),
        "session_count_7d": pd.Series(dtype="int"),
        "avg_session_minutes": pd.Series(dtype="float"),
        "lifetime_value": pd.Series(dtype="float"),
        "user_segment": pd.Series(dtype="str"),
        "event_time": pd.Series(dtype="str"),  # Required timestamp
    })
)

# Create Feature Group (both online + offline)
user_feature_group.create(
    s3_uri=f"s3://my-feature-store-bucket/features/",
    record_identifier_name="user_id",
    event_time_feature_name="event_time",
    role_arn=role,
    enable_online_store=True,
    online_store_security_config={
        "KmsKeyId": "arn:aws:kms:us-east-1:123456789:key/abc-123"
    },
    offline_store_config={
        "S3StorageConfig": {
            "S3Uri": "s3://my-feature-store-bucket/offline/",
            "KmsKeyId": "arn:aws:kms:us-east-1:123456789:key/abc-123",
        },
        "DataCatalogConfig": {
            "TableName": "user_engagement_features",
            "Catalog": "AwsDataCatalog",
            "Database": "ml_features",
        },
    },
    tags=[
        {"Key": "team", "Value": "ml-platform"},
        {"Key": "environment", "Value": "production"},
    ],
)

# Ingest records
records = pd.DataFrame({
    "user_id": ["u001", "u002", "u003"],
    "session_count_7d": [15, 3, 28],
    "avg_session_minutes": [12.5, 4.2, 22.1],
    "lifetime_value": [250.0, 45.0, 580.0],
    "user_segment": ["power", "casual", "power"],
    "event_time": [str(int(time.time()))] * 3,
})

user_feature_group.ingest(data_frame=records, max_workers=3, wait=True)

# Online retrieval (low-latency)
featurestore_client = boto3.client("sagemaker-featurestore-runtime")
response = featurestore_client.get_record(
    FeatureGroupName="user-engagement-features",
    RecordIdentifierValueAsString="u001",
    FeatureNames=["session_count_7d", "avg_session_minutes", "lifetime_value"],
)
print(response["Record"])

# Batch retrieval (online)
batch_response = featurestore_client.batch_get_record(
    Identifiers=[
        {
            "FeatureGroupName": "user-engagement-features",
            "RecordIdentifiersValueAsString": ["u001", "u002"],
            "FeatureNames": ["session_count_7d", "lifetime_value"],
        }
    ]
)

# Offline retrieval (historical via Athena)
query = user_feature_group.athena_query()
query_string = """
    SELECT user_id, session_count_7d, lifetime_value, event_time
    FROM "ml_features"."user_engagement_features"
    WHERE event_time >= '2024-01-01'
    ORDER BY event_time DESC
"""
query.run(query_string=query_string, output_location="s3://my-bucket/athena-results/")
query.wait()
df = query.as_dataframe()
```

### SageMaker Feature Store vs Feast

| Criteria | SageMaker FS | Feast |
|----------|-------------|-------|
| Managed | Fully managed | Self-managed |
| Online store | Built-in (<10ms) | Pluggable (Redis, DynamoDB) |
| Offline store | S3 + Glue + Athena | Pluggable (Redshift, BQ, files) |
| Cost model | Per-read/write + storage | Infrastructure cost only |
| Point-in-time joins | Via Athena SQL | Built-in `get_historical_features` |
| Streaming ingestion | Kinesis integration | Push API |
| Multi-cloud | AWS only | Any cloud |
| Customization | Limited | Highly extensible |
| Best for | AWS-native ML teams | Multi-cloud, open-source preference |

---

## 4. MLflow for Data Engineers

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MLflow Architecture                             │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  MLflow Tracking │  │  Model Registry  │  │  MLflow Models  │  │
│  │                  │  │                  │  │                 │  │
│  │  - Experiments   │  │  - Model versions│  │  - Packaging    │  │
│  │  - Runs          │  │  - Stage mgmt   │  │  - Flavors      │  │
│  │  - Parameters    │  │    (staging/prod)│  │  - Serving      │  │
│  │  - Metrics       │  │  - Approval flow │  │  - Signatures   │  │
│  │  - Artifacts     │  │  - Lineage       │  │                 │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    MLflow Projects                              │  │
│  │                                                                │  │
│  │  - Reproducible runs (conda/docker environments)              │  │
│  │  - Git-backed project definitions                              │  │
│  │  - Parameterized entry points                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Storage Backend:                                                    │
│  - Tracking DB: PostgreSQL / MySQL                                  │
│  - Artifact Store: S3 / GCS / Azure Blob                           │
└─────────────────────────────────────────────────────────────────────┘
```

### MLflow with Spark and Airflow

```python
"""MLflow integration with Spark MLlib and Airflow."""
import mlflow
import mlflow.spark
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator

# Configure MLflow
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("user-churn-prediction")

spark = SparkSession.builder.appName("ChurnModel").getOrCreate()

# Load training data (from feature store or data warehouse)
train_df = spark.read.parquet("s3://ml-data/training/churn_features/")
test_df = spark.read.parquet("s3://ml-data/testing/churn_features/")

# Define pipeline
feature_cols = ["session_count_7d", "avg_session_minutes", "lifetime_value",
                "days_since_last_login", "support_tickets_30d"]

with mlflow.start_run(run_name="gbt_churn_v3") as run:
    # Log parameters
    mlflow.log_param("model_type", "GBTClassifier")
    mlflow.log_param("max_depth", 6)
    mlflow.log_param("num_trees", 100)
    mlflow.log_param("feature_columns", feature_cols)
    mlflow.log_param("training_data_path", "s3://ml-data/training/churn_features/")
    mlflow.log_param("training_rows", train_df.count())

    # Build pipeline
    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
    scaler = StandardScaler(inputCol="features", outputCol="scaled_features")
    gbt = GBTClassifier(
        featuresCol="scaled_features",
        labelCol="churned",
        maxDepth=6,
        maxIter=100,
    )
    pipeline = Pipeline(stages=[assembler, scaler, gbt])

    # Train
    model = pipeline.fit(train_df)

    # Evaluate
    predictions = model.transform(test_df)
    evaluator = BinaryClassificationEvaluator(labelCol="churned")
    auc = evaluator.evaluate(predictions)

    # Log metrics
    mlflow.log_metric("auc_roc", auc)
    mlflow.log_metric("test_rows", test_df.count())

    # Log model
    mlflow.spark.log_model(
        model,
        artifact_path="spark-model",
        registered_model_name="churn-prediction-model",
    )

    # Log feature importance
    gbt_model = model.stages[-1]
    importance = dict(zip(feature_cols, gbt_model.featureImportances.toArray()))
    mlflow.log_dict(importance, "feature_importance.json")

    print(f"Run ID: {run.info.run_id}, AUC: {auc:.4f}")
```

### Airflow + MLflow Integration

```python
"""Airflow DAG for ML training pipeline with MLflow."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.emr import EmrAddStepsOperator
from datetime import datetime

def register_model_if_better(**context):
    """Promote model to staging if metrics exceed threshold."""
    import mlflow
    from mlflow.tracking import MlflowClient

    client = MlflowClient("http://mlflow-server:5000")
    run_id = context["ti"].xcom_pull(task_ids="train_model", key="run_id")
    run = client.get_run(run_id)
    auc = run.data.metrics["auc_roc"]

    if auc > 0.85:
        # Transition to staging
        model_version = client.get_latest_versions(
            "churn-prediction-model", stages=["None"]
        )[0]
        client.transition_model_version_stage(
            name="churn-prediction-model",
            version=model_version.version,
            stage="Staging",
        )
        return f"Model v{model_version.version} promoted to Staging (AUC={auc:.4f})"
    return f"Model not promoted (AUC={auc:.4f} < 0.85)"


with DAG(
    dag_id="ml_training_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@weekly",
    catchup=False,
) as dag:

    generate_features = PythonOperator(
        task_id="generate_training_features",
        python_callable=generate_training_dataset,
    )

    train = PythonOperator(
        task_id="train_model",
        python_callable=train_churn_model,
    )

    evaluate = PythonOperator(
        task_id="evaluate_and_register",
        python_callable=register_model_if_better,
    )

    generate_features >> train >> evaluate
```

---

## 5. Ray

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Ray Architecture                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Ray Libraries                              │  │
│  │                                                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │
│  │  │ Ray Data │  │Ray Train │  │Ray Tune  │  │Ray Serve │    │  │
│  │  │          │  │          │  │          │  │          │    │  │
│  │  │ Distrib  │  │ Distrib  │  │ Hyper-   │  │ Model    │    │  │
│  │  │ data     │  │ training │  │ parameter│  │ serving  │    │  │
│  │  │ process  │  │ (PyTorch │  │ tuning   │  │ (HTTP/   │    │  │
│  │  │          │  │  TF, etc)│  │          │  │  gRPC)   │    │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Ray Core                                   │  │
│  │                                                                │  │
│  │  - Tasks (stateless functions)                                │  │
│  │  - Actors (stateful classes)                                  │  │
│  │  - Objects (distributed shared memory)                        │  │
│  │  - Scheduling and resource management                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Ray Cluster                                    │  │
│  │                                                                │  │
│  │  Head Node (GCS, scheduler) + Worker Nodes (execute tasks)    │  │
│  │  Auto-scaling based on workload                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Ray Data for ML Preprocessing

```python
"""Ray Data for distributed ML preprocessing."""
import ray
import ray.data
from ray.data.preprocessors import StandardScaler, OneHotEncoder

ray.init()

# Read data (distributed)
ds = ray.data.read_parquet("s3://ml-data/raw/user_events/")

# Distributed transformations
def compute_features(batch: dict) -> dict:
    """Compute features from raw events (runs in parallel across cluster)."""
    import numpy as np

    batch["session_duration_log"] = np.log1p(batch["session_duration_seconds"])
    batch["events_per_minute"] = batch["event_count"] / (batch["session_duration_seconds"] / 60 + 1)
    batch["is_weekend"] = np.isin(batch["day_of_week"], [5, 6]).astype(int)
    return batch

# Apply transformations in parallel
ds = ds.map_batches(compute_features, batch_format="numpy")

# Filter
ds = ds.filter(lambda row: row["session_duration_seconds"] > 0)

# Aggregate per user
ds_grouped = ds.groupby("user_id").map_groups(
    lambda group: {
        "user_id": [group["user_id"][0]],
        "avg_session_duration": [group["session_duration_seconds"].mean()],
        "total_events": [group["event_count"].sum()],
        "session_count": [len(group["user_id"])],
    }
)

# Write back
ds_grouped.write_parquet("s3://ml-data/features/user_aggregates/")

# Use for training directly
from ray.train.xgboost import XGBoostTrainer
from ray.air.config import ScalingConfig

trainer = XGBoostTrainer(
    label_column="churned",
    num_boost_round=100,
    scaling_config=ScalingConfig(num_workers=4, use_gpu=False),
    params={"max_depth": 6, "eta": 0.1, "objective": "binary:logistic"},
    datasets={"train": ds_grouped},
)
result = trainer.fit()
```

### Ray vs Spark Trade-offs

| Criteria | Ray | Spark |
|----------|-----|-------|
| Best for | ML workloads, Python-native | ETL, SQL, large-scale batch |
| Language | Python-first | Scala/Java (PySpark wrapper) |
| Latency | Low (milliseconds) | Higher (JVM startup, stages) |
| GPU support | Native | Limited (Rapids) |
| Streaming | Ray Serve (inference) | Structured Streaming |
| Ecosystem | ML-focused | Data engineering |
| State management | Actors (in-memory) | Stateful streaming (checkpoints) |
| When to choose Ray | Online inference, distributed training, reinforcement learning |
| When to choose Spark | Large ETL, SQL analytics, data lake processing |

### KubeRay Deployment

```yaml
# kuberay-cluster.yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: ml-ray-cluster
  namespace: ml-platform
spec:
  rayVersion: "2.9.0"
  headGroupSpec:
    rayStartParams:
      dashboard-host: "0.0.0.0"
    template:
      spec:
        containers:
          - name: ray-head
            image: rayproject/ray-ml:2.9.0
            ports:
              - containerPort: 6379  # GCS
              - containerPort: 8265  # Dashboard
              - containerPort: 10001 # Client
            resources:
              requests:
                cpu: "4"
                memory: "8Gi"
              limits:
                cpu: "8"
                memory: "16Gi"
  workerGroupSpecs:
    - groupName: default-workers
      replicas: 4
      minReplicas: 2
      maxReplicas: 10
      rayStartParams: {}
      template:
        spec:
          containers:
            - name: ray-worker
              image: rayproject/ray-ml:2.9.0
              resources:
                requests:
                  cpu: "4"
                  memory: "16Gi"
                limits:
                  cpu: "8"
                  memory: "32Gi"
    - groupName: gpu-workers
      replicas: 2
      minReplicas: 0
      maxReplicas: 4
      rayStartParams:
        num-gpus: "1"
      template:
        spec:
          containers:
            - name: ray-worker
              image: rayproject/ray-ml:2.9.0-gpu
              resources:
                requests:
                  cpu: "4"
                  memory: "16Gi"
                  nvidia.com/gpu: "1"
                limits:
                  cpu: "8"
                  memory: "32Gi"
                  nvidia.com/gpu: "1"
```

---

## 6. ML Data Pipeline Patterns

### Batch Feature Computation

```python
"""Batch feature computation pipeline (Spark + Feast)."""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from datetime import datetime, timedelta

spark = SparkSession.builder.appName("FeatureComputation").getOrCreate()

# Read raw events
events = spark.read.parquet("s3://data-lake/raw/user_events/")

# Compute windowed features
window_7d = Window.partitionBy("user_id").orderBy("event_timestamp").rangeBetween(
    -7 * 86400,  # 7 days in seconds
    0
)
window_30d = Window.partitionBy("user_id").orderBy("event_timestamp").rangeBetween(
    -30 * 86400,
    0
)

user_features = events.groupBy("user_id").agg(
    F.count("*").alias("total_events_7d"),
    F.countDistinct("session_id").alias("session_count_7d"),
    F.avg("session_duration_seconds").alias("avg_session_duration"),
    F.sum(F.when(F.col("event_type") == "purchase", F.col("amount")).otherwise(0)).alias("revenue_7d"),
    F.max("event_timestamp").alias("event_timestamp"),
)

# Write to offline store (Parquet)
user_features.write.mode("overwrite").parquet(
    "s3://feature-store/offline/user_activity_features/"
)
```

### Streaming Feature Computation

```python
"""Streaming feature computation with Flink (PyFlink)."""
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings

env = StreamExecutionEnvironment.get_execution_environment()
t_env = StreamTableEnvironment.create(env)

# Define Kafka source
t_env.execute_sql("""
    CREATE TABLE user_events (
        user_id STRING,
        event_type STRING,
        amount DOUBLE,
        event_time TIMESTAMP(3),
        WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'user-events',
        'properties.bootstrap.servers' = 'kafka:9092',
        'format' = 'json',
        'scan.startup.mode' = 'latest-offset'
    )
""")

# Compute real-time features with tumbling window
t_env.execute_sql("""
    CREATE TABLE user_realtime_features (
        user_id STRING,
        event_count_5min INT,
        total_amount_5min DOUBLE,
        window_start TIMESTAMP(3),
        PRIMARY KEY (user_id) NOT ENFORCED
    ) WITH (
        'connector' = 'upsert-kafka',
        'topic' = 'user-realtime-features',
        'properties.bootstrap.servers' = 'kafka:9092',
        'key.format' = 'json',
        'value.format' = 'json'
    )
""")

t_env.execute_sql("""
    INSERT INTO user_realtime_features
    SELECT
        user_id,
        COUNT(*) as event_count_5min,
        SUM(amount) as total_amount_5min,
        TUMBLE_START(event_time, INTERVAL '5' MINUTE) as window_start
    FROM user_events
    GROUP BY user_id, TUMBLE(event_time, INTERVAL '5' MINUTE)
""")
```

### Feature Validation and Drift Detection

```python
"""Feature validation and drift detection."""
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
from scipy import stats


@dataclass
class FeatureStats:
    name: str
    mean: float
    std: float
    min_val: float
    max_val: float
    null_rate: float
    distribution: np.ndarray  # histogram


@dataclass
class DriftResult:
    feature_name: str
    drift_detected: bool
    score: float  # KS statistic or PSI
    threshold: float
    method: str


def compute_psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index for drift detection."""
    ref_hist, bin_edges = np.histogram(reference, bins=bins, density=True)
    cur_hist, _ = np.histogram(current, bins=bin_edges, density=True)

    # Avoid division by zero
    ref_hist = np.clip(ref_hist, 1e-6, None)
    cur_hist = np.clip(cur_hist, 1e-6, None)

    # Normalize
    ref_hist = ref_hist / ref_hist.sum()
    cur_hist = cur_hist / cur_hist.sum()

    psi = np.sum((cur_hist - ref_hist) * np.log(cur_hist / ref_hist))
    return psi


def detect_drift(
    reference_data: Dict[str, np.ndarray],
    current_data: Dict[str, np.ndarray],
    psi_threshold: float = 0.2,
    ks_threshold: float = 0.05,
) -> List[DriftResult]:
    """Detect feature drift using PSI and KS test."""
    results = []

    for feature_name in reference_data:
        ref = reference_data[feature_name]
        cur = current_data[feature_name]

        # PSI
        psi = compute_psi(ref, cur)
        psi_drift = psi > psi_threshold

        # KS test
        ks_stat, ks_pvalue = stats.ks_2samp(ref, cur)
        ks_drift = ks_pvalue < ks_threshold

        results.append(DriftResult(
            feature_name=feature_name,
            drift_detected=psi_drift or ks_drift,
            score=psi,
            threshold=psi_threshold,
            method="PSI + KS",
        ))

    return results
```

---

## 7. Point-in-Time Joins Deep Dive

### The Data Leakage Problem

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Leakage in Feature Joins                      │
│                                                                      │
│  Entity DF (training labels):                                        │
│  ┌─────────┬────────────────────┬────────┐                         │
│  │ user_id │ event_timestamp    │ label  │                         │
│  ├─────────┼────────────────────┼────────┤                         │
│  │ 1001    │ 2024-01-15 12:00   │ 1      │                         │
│  │ 1002    │ 2024-01-16 08:00   │ 0      │                         │
│  └─────────┴────────────────────┴────────┘                         │
│                                                                      │
│  Feature Table (multiple versions per entity):                       │
│  ┌─────────┬────────────────────┬───────────────┐                  │
│  │ user_id │ feature_timestamp  │ session_7d    │                  │
│  ├─────────┼────────────────────┼───────────────┤                  │
│  │ 1001    │ 2024-01-10 00:00   │ 5             │                  │
│  │ 1001    │ 2024-01-14 00:00   │ 12            │  ← correct      │
│  │ 1001    │ 2024-01-16 00:00   │ 18            │  ← LEAKAGE!     │
│  │ 1002    │ 2024-01-15 00:00   │ 3             │  ← correct      │
│  │ 1002    │ 2024-01-17 00:00   │ 7             │  ← LEAKAGE!     │
│  └─────────┴────────────────────┴───────────────┘                  │
│                                                                      │
│  CORRECT join: For user 1001 at 2024-01-15 12:00,                   │
│    use feature from 2024-01-14 (latest BEFORE event)                │
│                                                                      │
│  WRONG join: Using 2024-01-16 feature for 2024-01-15 event         │
│    = using future information = data leakage                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation with Spark Window Functions

```python
"""Point-in-time join using Spark window functions."""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("PITJoin").getOrCreate()

# Entity DataFrame (labels with timestamps)
entity_df = spark.createDataFrame([
    (1001, "2024-01-15 12:00:00", 1),
    (1002, "2024-01-16 08:00:00", 0),
    (1003, "2024-01-16 14:00:00", 1),
], ["user_id", "event_timestamp", "label"])
entity_df = entity_df.withColumn("event_timestamp", F.to_timestamp("event_timestamp"))

# Feature table (historical features)
features_df = spark.createDataFrame([
    (1001, "2024-01-10 00:00:00", 5, 10.2),
    (1001, "2024-01-14 00:00:00", 12, 15.5),
    (1001, "2024-01-16 00:00:00", 18, 20.1),  # Future - should NOT be used for 1001
    (1002, "2024-01-12 00:00:00", 2, 3.5),
    (1002, "2024-01-15 00:00:00", 3, 4.2),
    (1002, "2024-01-17 00:00:00", 7, 8.1),    # Future - should NOT be used for 1002
], ["user_id", "feature_timestamp", "session_count_7d", "avg_duration"])
features_df = features_df.withColumn("feature_timestamp", F.to_timestamp("feature_timestamp"))

# Point-in-time join
# Step 1: Join all features, filter to only those BEFORE the event
joined = entity_df.join(features_df, on="user_id", how="left")
joined = joined.filter(F.col("feature_timestamp") <= F.col("event_timestamp"))

# Step 2: For each entity+event, keep only the LATEST feature before the event
window = Window.partitionBy("user_id", "event_timestamp").orderBy(F.desc("feature_timestamp"))
pit_joined = joined.withColumn("rank", F.row_number().over(window)) \
    .filter(F.col("rank") == 1) \
    .drop("rank", "feature_timestamp")

pit_joined.show()
# +-------+-------------------+-----+----------------+------------+
# |user_id|    event_timestamp|label|session_count_7d|avg_duration|
# +-------+-------------------+-----+----------------+------------+
# |   1001|2024-01-15 12:00:00|    1|              12|        15.5|  ← Uses Jan 14 (correct!)
# |   1002|2024-01-16 08:00:00|    0|               3|         4.2|  ← Uses Jan 15 (correct!)
# +-------+-------------------+-----+----------------+------------+
```

### Feast Point-in-Time Join (Built-in)

```python
"""Feast handles point-in-time joins automatically."""
from feast import FeatureStore
import pandas as pd
from datetime import datetime

store = FeatureStore(repo_path="feature_repo/")

# Entity DataFrame with timestamps
entity_df = pd.DataFrame({
    "user_id": [1001, 1002, 1003],
    "event_timestamp": [
        datetime(2024, 1, 15, 12, 0),
        datetime(2024, 1, 16, 8, 0),
        datetime(2024, 1, 16, 14, 0),
    ],
})

# Feast automatically does point-in-time correct joins
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "user_activity_features:session_count_7d",
        "user_activity_features:avg_session_duration",
        "user_profile_features:lifetime_value",
    ],
).to_df()
# Each row gets features AS OF the event_timestamp (no leakage)
```

### Performance Optimization for PIT Joins

```python
"""Optimized point-in-time join for large datasets."""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .config("spark.sql.shuffle.partitions", "200") \
    .config("spark.sql.adaptive.enabled", "true") \
    .getOrCreate()

def optimized_pit_join(entity_df, feature_df, entity_key, entity_ts, feature_ts):
    """
    Optimized PIT join using asof-join pattern.
    Key optimizations:
    1. Partition both DataFrames by entity key
    2. Sort by timestamp within partitions
    3. Use range join condition to limit comparisons
    """
    # Add TTL filter: don't use features older than 30 days
    ttl_seconds = 30 * 86400

    # Broadcast hint for small entity_df
    if entity_df.count() < 1_000_000:
        entity_df = F.broadcast(entity_df)

    # Join with time bounds (reduces shuffle)
    joined = entity_df.join(
        feature_df,
        on=[entity_key],
        how="left"
    ).filter(
        (F.col(feature_ts) <= F.col(entity_ts)) &
        (F.unix_timestamp(F.col(entity_ts)) - F.unix_timestamp(F.col(feature_ts)) <= ttl_seconds)
    )

    # Keep latest feature per entity+event
    window = Window.partitionBy(entity_key, entity_ts).orderBy(F.desc(feature_ts))
    result = joined.withColumn("_rank", F.row_number().over(window)) \
        .filter(F.col("_rank") == 1) \
        .drop("_rank", feature_ts)

    return result
```

---

## 8. Online/Offline Consistency

### The Dual-Write Problem

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Online/Offline Consistency Challenge               │
│                                                                      │
│  PROBLEM: Features must be computed identically for training         │
│  (offline) and serving (online), but the systems are different.      │
│                                                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────┐        │
│  │  Training Pipeline      │    │  Serving Pipeline        │        │
│  │  (Spark batch)          │    │  (Python real-time)      │        │
│  │                         │    │                          │        │
│  │  avg = df.groupBy(...)  │    │  avg = sum(vals)/len(.. │        │
│  │    .agg(F.avg("x"))     │    │                          │        │
│  │                         │    │  Different rounding?     │        │
│  │  Result: 15.4999998     │    │  Result: 15.5            │        │
│  └─────────────────────────┘    └─────────────────────────┘        │
│                                                                      │
│  Even tiny differences compound across features and degrade model!  │
│                                                                      │
│  SOLUTIONS:                                                          │
│  1. Single computation path (compute once, serve everywhere)        │
│  2. Feature store materialization (Feast pattern)                    │
│  3. Shared feature transformation code (tested for parity)          │
└─────────────────────────────────────────────────────────────────────┘
```

### Lambda vs Kappa Architecture for Features

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAMBDA Architecture for Features                                    │
│                                                                      │
│  Raw Events ──┬──▶ Batch Layer (Spark) ──▶ Offline Store            │
│               │        (hourly/daily)          (training)            │
│               │                                                      │
│               └──▶ Speed Layer (Flink) ──▶ Online Store             │
│                        (real-time)             (serving)             │
│                                                                      │
│  Pros: Accurate batch + fast streaming                               │
│  Cons: Two code paths = consistency risk, complex ops                │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  KAPPA Architecture for Features                                     │
│                                                                      │
│  Raw Events ──▶ Stream Processing (Flink) ──┬──▶ Online Store       │
│                    (single path)             │      (serving)        │
│                                             └──▶ Offline Store      │
│                                                    (training)        │
│                                                                      │
│  Pros: Single code path = guaranteed consistency                     │
│  Cons: Complex windowed aggregations, reprocessing cost              │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  RECOMMENDED: Feast Pattern                                          │
│                                                                      │
│  Batch compute ──▶ Offline Store ──materialize──▶ Online Store      │
│                                                                      │
│  Single computation, single source of truth, materialization         │
│  syncs to online. Add push for real-time features where needed.     │
└─────────────────────────────────────────────────────────────────────┘
```

### Testing Online/Offline Parity

```python
"""Testing feature parity between training and serving paths."""
import numpy as np
from typing import Dict, List


def test_feature_parity(
    offline_features: Dict[str, float],
    online_features: Dict[str, float],
    tolerance: float = 1e-6,
) -> List[str]:
    """Compare offline (training) and online (serving) features."""
    mismatches = []

    for feature_name in offline_features:
        offline_val = offline_features[feature_name]
        online_val = online_features.get(feature_name)

        if online_val is None:
            mismatches.append(f"{feature_name}: missing in online store")
            continue

        if not np.isclose(offline_val, online_val, rtol=tolerance):
            mismatches.append(
                f"{feature_name}: offline={offline_val}, online={online_val}, "
                f"diff={abs(offline_val - online_val)}"
            )

    return mismatches


# Integration test: compare Feast offline vs online for same entity
def integration_test_feast_parity():
    """End-to-end parity test."""
    from feast import FeatureStore
    import pandas as pd
    from datetime import datetime

    store = FeatureStore(repo_path="feature_repo/")

    # Get online features
    online = store.get_online_features(
        features=["user_activity_features:session_count_7d"],
        entity_rows=[{"user_id": 1001}],
    ).to_dict()

    # Get offline features at latest timestamp
    entity_df = pd.DataFrame({
        "user_id": [1001],
        "event_timestamp": [datetime.utcnow()],
    })
    offline = store.get_historical_features(
        entity_df=entity_df,
        features=["user_activity_features:session_count_7d"],
    ).to_df()

    # Compare
    assert online["session_count_7d"][0] == offline["session_count_7d"].iloc[0], \
        "Online/offline feature mismatch detected!"
```

---

## 9. Data Versioning

### DVC (Data Version Control)

```yaml
# .dvc/config
[core]
    remote = s3store
[remote "s3store"]
    url = s3://my-ml-data/dvc-store
    region = us-east-1
```

```bash
# Track a dataset
dvc add data/training/features.parquet
git add data/training/features.parquet.dvc .gitignore
git commit -m "Add training features v1"
dvc push

# Create a version tag
git tag -a "data-v1.0" -m "Initial feature set"

# Update dataset and create new version
dvc add data/training/features.parquet
git add data/training/features.parquet.dvc
git commit -m "Update features: add session_count"
git tag -a "data-v1.1" -m "Added session count feature"
dvc push

# Checkout previous version
git checkout data-v1.0
dvc checkout
```

### LakeFS

```python
"""LakeFS for data versioning (Git-like for object storage)."""
import lakefs_client
from lakefs_client.client import LakeFSClient

client = LakeFSClient(
    configuration=lakefs_client.Configuration(
        host="http://lakefs:8000/api/v1",
        username="access_key",
        password="secret_key",
    )
)

# Create branch for experimentation
client.branches.create_branch(
    repository="ml-data",
    branch_creation={"name": "experiment/new-features", "source": "main"},
)

# Upload data to branch (doesn't affect main)
with open("features.parquet", "rb") as f:
    client.objects.upload_object(
        repository="ml-data",
        branch="experiment/new-features",
        path="training/features.parquet",
        content=f,
    )

# Commit
client.commits.commit(
    repository="ml-data",
    branch="experiment/new-features",
    commit_creation={"message": "Add new feature columns"},
)

# Merge to main when validated
client.refs.merge_into_branch(
    repository="ml-data",
    source_ref="experiment/new-features",
    destination_branch="main",
)

# Create tag for reproducibility
client.tags.create_tag(
    repository="ml-data",
    tag_creation={"id": "training-data-v2.0", "ref": "main"},
)
```

### Delta Lake Time Travel

```python
"""Delta Lake time travel for feature versioning."""
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .getOrCreate()

# Read features as of a specific version
features_v5 = spark.read.format("delta") \
    .option("versionAsOf", 5) \
    .load("s3://feature-store/delta/user_features/")

# Read features as of a specific timestamp
features_historical = spark.read.format("delta") \
    .option("timestampAsOf", "2024-01-15 00:00:00") \
    .load("s3://feature-store/delta/user_features/")

# View history
from delta.tables import DeltaTable
dt = DeltaTable.forPath(spark, "s3://feature-store/delta/user_features/")
dt.history(10).show()

# Restore to previous version
dt.restoreToVersion(5)
```

---

## 10. Production Architecture

### End-to-End ML Data Platform

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Production ML Data Platform                             │
│                                                                          │
│  DATA SOURCES                                                            │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                          │
│  │Postgres│ │ Kafka  │ │  S3    │ │ APIs   │                          │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘                          │
│      │          │          │          │                                  │
│      ▼          ▼          ▼          ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              INGESTION LAYER                                       │  │
│  │  CDC (Debezium) │ Kafka Connect │ Airbyte │ Custom                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              DATA LAKE (S3 / Iceberg / Delta)                     │  │
│  │  Raw → Cleaned → Curated                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│              ┌───────────────┼───────────────┐                          │
│              ▼               ▼               ▼                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐     │
│  │ BATCH FEATURE│  │STREAM FEATURE│  │   DATA QUALITY            │     │
│  │ COMPUTATION  │  │ COMPUTATION  │  │   (Great Expectations)    │     │
│  │ (Spark/EMR)  │  │ (Flink)      │  │                           │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘     │
│         │                  │                                             │
│         ▼                  ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              FEATURE STORE (Feast)                                 │  │
│  │                                                                    │  │
│  │  ┌─────────────────┐           ┌─────────────────────────────┐   │  │
│  │  │  Offline Store  │──materialize──▶│  Online Store (Redis)   │   │  │
│  │  │  (S3/Redshift)  │           │                             │   │  │
│  │  └─────────────────┘           └──────────────┬──────────────┘   │  │
│  └───────────┬────────────────────────────────────┼──────────────────┘  │
│              │                                    │                      │
│              ▼                                    ▼                      │
│  ┌──────────────────┐                 ┌──────────────────────────┐     │
│  │  MODEL TRAINING  │                 │   MODEL SERVING           │     │
│  │                  │                 │                           │     │
│  │  - MLflow        │                 │  - SageMaker Endpoints   │     │
│  │  - Ray Train     │                 │  - Ray Serve             │     │
│  │  - SageMaker     │                 │  - KServe                │     │
│  └──────────────────┘                 └──────────────────────────┘     │
│                                                   │                      │
│                                                   ▼                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              MONITORING & OBSERVABILITY                            │  │
│  │                                                                    │  │
│  │  Feature drift │ Model performance │ Data quality │ Latency SLAs  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Team Responsibilities

| Team | Responsibilities | Tools |
|------|-----------------|-------|
| Data Platform | Feature store infra, online/offline stores, materialization | Feast, Redis, K8s |
| Data Engineering | Feature computation pipelines, data quality | Spark, Flink, Airflow, GE |
| ML Engineering | Model training, serving, monitoring | MLflow, Ray, SageMaker |
| Data Science | Feature definitions, model development | Feast SDK, notebooks |
| MLOps | CI/CD for models, deployment automation | GitHub Actions, ArgoCD |

### SLAs

| Component | SLA | Metric |
|-----------|-----|--------|
| Online feature serving | p99 < 10ms | Feature server latency |
| Feature freshness (batch) | < 2 hours stale | Time since last materialization |
| Feature freshness (streaming) | < 5 minutes stale | End-to-end latency |
| Training data generation | < 30 minutes | `get_historical_features` time |
| Model inference | p99 < 100ms | End-to-end prediction latency |
| Feature availability | 99.9% | Online store uptime |

### Cost Optimization

```python
"""Feature store cost optimization strategies."""

COST_STRATEGIES = {
    "online_store": {
        "Redis": {
            "optimization": "Use TTL aggressively, evict unused features",
            "tip": "Only store features needed for <10ms serving",
            "alternative": "DynamoDB on-demand for bursty workloads",
        },
        "DynamoDB": {
            "optimization": "Use on-demand for unpredictable traffic",
            "tip": "Batch writes during materialization (25 items/batch)",
            "cost_driver": "Read capacity units * number of feature lookups",
        },
    },
    "offline_store": {
        "optimization": "Partition by date, use columnar format (Parquet)",
        "tip": "Only scan needed time ranges for PIT joins",
        "cleanup": "Delete features older than training window (e.g., 2 years)",
    },
    "materialization": {
        "optimization": "Incremental materialization (only new data)",
        "tip": "Use Spot instances for batch materialization jobs",
        "schedule": "Align with feature freshness SLA (not more frequent)",
    },
    "feature_computation": {
        "optimization": "Share computed features across models",
        "tip": "Deduplicate: 100 models × same feature = compute once",
        "monitoring": "Track cost per feature, retire unused features",
    },
}
```

---

## 11. Decision Framework

### Feature Store Selection

| Criteria | Feast | SageMaker FS | Tecton | Hopsworks |
|----------|-------|-------------|--------|-----------|
| **Open source** | Yes | No | No | Partially |
| **Cloud** | Any | AWS only | Any | Any |
| **Real-time features** | Push API | Kinesis | Native streaming | Native streaming |
| **Point-in-time joins** | Built-in | Manual (Athena) | Built-in | Built-in |
| **Managed** | No (self-manage) | Fully managed | Fully managed | Managed option |
| **Streaming engine** | External | External | Built-in (Spark/Flink) | Built-in (Flink) |
| **Cost** | Infra only | Pay per use | License | License |
| **Best for** | Platform teams, multi-cloud | AWS-native teams | Large-scale real-time | End-to-end ML platform |
| **Complexity** | Medium | Low | High | Medium |

### When to Build vs Buy

**Build (Feast + custom) when:**
- Multi-cloud or hybrid requirements
- Strong platform engineering team (3+ engineers)
- Need deep customization of storage backends
- Cost sensitivity at scale (>100M features)

**Buy (Tecton/Hopsworks/SageMaker) when:**
- Time-to-value is critical
- Small ML platform team (<3 engineers)
- Need managed streaming feature computation
- Want vendor support and SLAs

### ML Pipeline Orchestrator Selection

| | Airflow | Dagster | Prefect | Kubeflow |
|---|---------|---------|---------|----------|
| ML focus | General + ML | General + ML | General + ML | ML-specific |
| Feature store integration | Good (Feast plugin) | Good (native) | Good | Native |
| Experiment tracking | Via MLflow | Via MLflow | Via MLflow | Built-in (KFP) |
| K8s native | Via K8sExecutor | Via K8s | Via K8s agent | Yes |
| Best for | General-purpose | Data + ML teams | Simple workflows | K8s-first ML |

---

## Summary

The ML data platform stack combines:

1. **Feature Store (Feast)**: Central feature management, online/offline consistency, point-in-time correctness
2. **SageMaker Feature Store**: AWS-native alternative, fully managed, integrated with SageMaker
3. **MLflow**: Experiment tracking, model registry, deployment lifecycle
4. **Ray**: Distributed ML compute (preprocessing, training, serving)
5. **Streaming features**: Flink/Kafka for real-time feature computation
6. **Data versioning**: DVC/LakeFS/Delta time travel for reproducibility
7. **Monitoring**: Drift detection, parity testing, SLA tracking

The key architectural principle: **compute features once, serve everywhere** — with
point-in-time correctness guaranteeing no data leakage between training and serving.
