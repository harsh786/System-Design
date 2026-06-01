# Data Infrastructure for ML

## Overview

Data infrastructure is the foundation of any production ML system. Models are only as good as the data that feeds them. This section covers the storage, processing, quality, and governance layers that enable reliable ML at scale.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML DATA INFRASTRUCTURE STACK                                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  CONSUMPTION LAYER                                                │     │
│  │  Feature Store │ Training Pipelines │ Analytics │ Serving        │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  PROCESSING LAYER                                                 │     │
│  │  Batch (Spark) │ Streaming (Flink/Kafka) │ Compute (Dask/Ray)   │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  QUALITY & GOVERNANCE LAYER                                       │     │
│  │  Validation │ Lineage │ Catalog │ Privacy │ Schema Registry     │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  STORAGE LAYER                                                    │     │
│  │  Object Store (S3) │ Data Lake │ Warehouse │ Vector DB │ Cache  │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  INGESTION LAYER                                                  │     │
│  │  CDC │ APIs │ Event Streams │ File Drops │ Scraping │ IoT       │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Lake vs Data Warehouse vs Lakehouse

### Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  DATA LAKE                  DATA WAREHOUSE            LAKEHOUSE             │
│  ┌──────────────┐          ┌──────────────┐         ┌──────────────┐      │
│  │              │          │              │         │              │      │
│  │  Raw files   │          │  Structured  │         │  Structured  │      │
│  │  Any format  │          │  Schema-on-  │         │  on Object   │      │
│  │  Schema-on-  │          │  write       │         │  Storage     │      │
│  │  read        │          │              │         │              │      │
│  │              │          │  SQL-first   │         │  ACID + SQL  │      │
│  │  S3/GCS/ADLS│          │  Optimized   │         │  + ML        │      │
│  │              │          │  Queries     │         │              │      │
│  └──────────────┘          └──────────────┘         └──────────────┘      │
│                                                                              │
│  Examples:                  Examples:                Examples:               │
│  S3 + Hive/Glue            Snowflake                Delta Lake             │
│  HDFS                      BigQuery                 Apache Iceberg         │
│  Azure Data Lake           Redshift                 Apache Hudi            │
│                             Synapse                  Databricks Lakehouse   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Feature | Data Lake | Data Warehouse | Lakehouse |
|---------|-----------|----------------|-----------|
| Schema | On-read | On-write | On-write (flexible) |
| ACID | No | Yes | Yes |
| Format | Any (JSON, CSV, Parquet) | Proprietary | Open (Parquet + metadata) |
| Cost (Storage) | $ (cheapest) | $$$$ | $ (object storage) |
| Cost (Compute) | $$ | $$$ | $$ |
| ML Support | Good (native access) | Poor (export needed) | Excellent |
| Query Performance | Medium | Excellent | Good-Excellent |
| Time Travel | No (unless LakeFS) | Limited | Yes (built-in) |
| Data Types | Any | Structured | Structured + Semi |
| Governance | Manual | Built-in | Built-in |

### Lakehouse Architecture (Delta Lake / Iceberg)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAKEHOUSE ARCHITECTURE                                                     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Table Format Layer (Delta Lake / Iceberg / Hudi)                 │     │
│  │                                                                    │     │
│  │  Features:                                                        │     │
│  │  - ACID transactions on object storage                           │     │
│  │  - Schema enforcement and evolution                              │     │
│  │  - Time travel (query historical versions)                       │     │
│  │  - Partition evolution (change partitioning without rewrite)     │     │
│  │  - Merge/Upsert operations                                      │     │
│  │                                                                    │     │
│  │  ┌────────────────────────────────────────────────────────────┐ │     │
│  │  │  Metadata (JSON/Avro)                                       │ │     │
│  │  │  ├── Snapshot 1 → manifest → data files                   │ │     │
│  │  │  ├── Snapshot 2 → manifest → data files                   │ │     │
│  │  │  └── Snapshot 3 → manifest → data files (current)         │ │     │
│  │  └────────────────────────────────────────────────────────────┘ │     │
│  │                              │                                    │     │
│  │                              ▼                                    │     │
│  │  ┌────────────────────────────────────────────────────────────┐ │     │
│  │  │  Data Files (Parquet)                                       │ │     │
│  │  │  s3://bucket/table/partition=2024-01/data-001.parquet      │ │     │
│  │  │  s3://bucket/table/partition=2024-01/data-002.parquet      │ │     │
│  │  └────────────────────────────────────────────────────────────┘ │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  For ML:                                                                   │
│  - Time travel → reproducible training datasets                           │
│  - Schema enforcement → catch data pipeline bugs                          │
│  - ACID → consistent feature computation                                  │
│  - Partition pruning → fast data access for training                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Streaming Pipelines

### Kafka + Flink Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STREAMING DATA PIPELINE FOR ML                                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │  Sources                                                         │      │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐             │      │
│  │  │App     │  │Clickstr│  │Payment │  │IoT     │             │      │
│  │  │Events  │  │eam     │  │Events  │  │Sensors │             │      │
│  │  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘             │      │
│  └──────┼────────────┼──────────┼────────────┼───────────────────┘      │
│         │            │          │            │                            │
│         ▼            ▼          ▼            ▼                            │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  Apache Kafka (Event Bus)                                     │       │
│  │  ┌──────────────────────────────────────────────────────┐   │       │
│  │  │  Topics:                                              │   │       │
│  │  │  user.actions (1000 partitions, 7-day retention)     │   │       │
│  │  │  transactions (500 partitions, 30-day retention)     │   │       │
│  │  │  ml.features (100 partitions, 1-day retention)       │   │       │
│  │  │  ml.predictions (100 partitions, 7-day retention)    │   │       │
│  │  └──────────────────────────────────────────────────────┘   │       │
│  └──────────────────────────────┬───────────────────────────────┘       │
│                                  │                                        │
│                                  ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  Apache Flink (Stream Processing)                             │       │
│  │                                                                │       │
│  │  Job 1: Feature Computation                                   │       │
│  │  ├── Tumbling window (5 min): count, sum, avg               │       │
│  │  ├── Sliding window (1 hour): moving averages               │       │
│  │  └── Session window: session-level aggregates               │       │
│  │                                                                │       │
│  │  Job 2: Real-time Scoring                                    │       │
│  │  ├── Enrich event with features                             │       │
│  │  ├── Call model (embedded or remote)                        │       │
│  │  └── Emit prediction to output topic                        │       │
│  │                                                                │       │
│  │  Job 3: Data Quality                                         │       │
│  │  ├── Schema validation                                      │       │
│  │  ├── Null rate monitoring                                   │       │
│  │  └── Volume anomaly detection                               │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                  │                                        │
│              ┌───────────────────┼───────────────────┐                   │
│              ▼                   ▼                   ▼                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Online      │  │  Data Lake   │  │  Alerting    │                  │
│  │  Feature     │  │  (archive)   │  │  (PagerDuty) │                  │
│  │  Store(Redis)│  │  (Iceberg)   │  │              │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Streaming Platform Comparison

| Feature | Kafka | Kinesis | Pulsar | Flink |
|---------|-------|---------|--------|-------|
| Type | Message broker | Managed stream | Message broker | Processor |
| Throughput | 1M+ msg/sec | 1M msg/sec | 1M+ msg/sec | Depends on source |
| Latency | <10ms | ~200ms | <10ms | Processing time |
| Retention | Configurable (∞) | 7 days (max 365) | Configurable (∞) | N/A |
| Ordering | Per partition | Per shard | Per partition | Watermarks |
| Managed | Confluent, MSK | AWS native | StreamNative | AWS, Confluent |
| Cost | $$-$$$ | $$ | $$-$$$ | $$ (compute) |
| ML Integration | Good (Connect) | Good (Lambda) | Good | Excellent (native) |

---

## Batch Processing

### Spark for ML Pipelines

```
┌─────────────────────────────────────────────────────────────────┐
│  SPARK ML PIPELINE ARCHITECTURE                                  │
│                                                                   │
│  ┌───────────────────────────────────────────────────┐          │
│  │  Spark Application                                 │          │
│  │                                                     │          │
│  │  Stage 1: Data Load & Validation                   │          │
│  │  df = spark.read.format("delta").load("s3://...")  │          │
│  │  validate(df, expectations)                        │          │
│  │                                                     │          │
│  │  Stage 2: Feature Engineering                      │          │
│  │  features = (df                                    │          │
│  │    .withColumn("amount_zscore", ...)              │          │
│  │    .withColumn("rolling_avg_7d", window_fn(...)) │          │
│  │    .withColumn("user_embedding", udf_embed(...)) │          │
│  │  )                                                 │          │
│  │                                                     │          │
│  │  Stage 3: Training Data Assembly                   │          │
│  │  training_set = features.join(labels, "entity_id")│          │
│  │                                                     │          │
│  │  Stage 4: Write to Feature Store                   │          │
│  │  feast_offline.write(features)                    │          │
│  │  feast_online.materialize(features)               │          │
│  └───────────────────────────────────────────────────┘          │
│                                                                   │
│  Cluster Sizing for ML:                                          │
│  ┌───────────────────────────────────────────────────┐          │
│  │  Data Size  │  Nodes  │  Type        │  Cost/hr  │          │
│  │  <100GB     │  5-10   │  r5.2xlarge  │  $5-10    │          │
│  │  100GB-1TB  │  20-50  │  r5.4xlarge  │  $50-100  │          │
│  │  1TB-10TB   │  50-200 │  r5.8xlarge  │  $200-800 │          │
│  │  >10TB      │  200+   │  r5.16xlarge │  $1000+   │          │
│  └───────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Spark vs Dask vs Ray

| Feature | Spark | Dask | Ray |
|---------|-------|------|-----|
| Best for | ETL, SQL, large data | Pandas-like, medium data | ML training, serving |
| API | DataFrame, SQL | Pandas-compatible | Flexible (actors, tasks) |
| Scale | 10K+ nodes | 100s of nodes | 1000s of nodes |
| GPU Support | Limited | Basic | Excellent |
| ML Libraries | MLlib | Scikit-learn compatible | Ray Tune, Ray Train |
| Streaming | Spark Structured Streaming | Limited | Ray Serve |
| Overhead | High (JVM startup) | Low (Python native) | Low |
| When to choose | Large ETL, SQL-heavy | Replace pandas at scale | Distributed ML training |

---

## Data Quality Frameworks

### Great Expectations Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA QUALITY WITH GREAT EXPECTATIONS                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Expectation Suite: "training_data_quality"                       │     │
│  │                                                                    │     │
│  │  Expectations:                                                    │     │
│  │  ├── expect_column_values_to_not_be_null("user_id")             │     │
│  │  ├── expect_column_values_to_be_between("age", 0, 120)         │     │
│  │  ├── expect_column_mean_to_be_between("amount", 10, 1000)      │     │
│  │  ├── expect_column_distinct_values_to_be_in_set("country",     │     │
│  │  │       ["US", "UK", "CA", ...])                               │     │
│  │  ├── expect_table_row_count_to_be_between(1_000_000, 2_000_000)│     │
│  │  └── expect_column_kl_divergence_to_be_less_than(              │     │
│  │          "feature_x", reference_dist, 0.1)                      │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Pipeline Integration:                                                     │
│  ┌─────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  Data   │───▶│  Validate    │───▶│  Pass?   │───▶│  Continue    │   │
│  │  Source │    │  (GE Suite)  │    │          │    │  Pipeline    │   │
│  └─────────┘    └──────────────┘    └──────────┘    └──────────────┘   │
│                                           │                               │
│                                      Fail │                               │
│                                           ▼                               │
│                                    ┌──────────────┐                      │
│                                    │  Alert +     │                      │
│                                    │  Quarantine  │                      │
│                                    │  Bad Data    │                      │
│                                    └──────────────┘                      │
│                                                                              │
│  ML-Specific Quality Checks:                                              │
│  1. Label distribution stability (no sudden class imbalance)              │
│  2. Feature correlation stability (relationships preserved)               │
│  3. Training/serving distribution similarity (PSI check)                  │
│  4. Freshness checks (data not stale)                                    │
│  5. Join completeness (no missing after joins)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Schema Evolution and Management

```
┌─────────────────────────────────────────────────────────────────┐
│  SCHEMA EVOLUTION FOR ML                                         │
│                                                                   │
│  Schema Registry (Confluent / AWS Glue)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Schema: user_features_v3                                │   │
│  │                                                           │   │
│  │  v1: {user_id, age, country}                            │   │
│  │  v2: {user_id, age, country, tenure_days}  ← ADD FIELD │   │
│  │  v3: {user_id, age_bucket, country, tenure_days}  ← CHANGE│ │
│  │                                                           │   │
│  │  Compatibility modes:                                    │   │
│  │  - BACKWARD: new schema can read old data (safe for ML) │   │
│  │  - FORWARD: old schema can read new data                │   │
│  │  - FULL: both directions                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ML Impact of Schema Changes:                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Change Type     │  Impact          │  Action Required  │   │
│  │──────────────────┼──────────────────┼───────────────────│   │
│  │  Add column      │  Low             │  Retrain (new feat)│  │
│  │  Remove column   │  HIGH            │  Retrain required │   │
│  │  Rename column   │  HIGH            │  Update pipeline  │   │
│  │  Change type     │  HIGH            │  Update + retrain │   │
│  │  Change semantics│  CRITICAL        │  Full audit       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Best Practice: Feature pipelines should be resilient to        │
│  additive schema changes but FAIL LOUDLY on breaking changes.   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Lineage Tracking

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA LINEAGE FOR ML                                                        │
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│  │ Raw Data │───▶│  Clean   │───▶│ Features │───▶│  Model   │           │
│  │ (S3)     │    │  (Delta) │    │ (Store)  │    │(Registry)│           │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘           │
│       │               │               │               │                  │
│       ▼               ▼               ▼               ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  Lineage Graph (OpenLineage / Marquez / Datahub)             │       │
│  │                                                               │       │
│  │  Question: "Why did model predictions change on Jan 15?"     │       │
│  │  Answer:                                                      │       │
│  │  └── Model v2.1 was retrained Jan 14                        │       │
│  │      └── Used features from feature_store@v3.2              │       │
│  │          └── Feature "user_score" computation changed Jan 13 │       │
│  │              └── Upstream table had schema change Jan 12     │       │
│  │                  └── Source system migrated databases        │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  Tools:                                                                    │
│  - OpenLineage: Open standard for lineage                                 │
│  - Marquez: Open-source lineage server                                    │
│  - DataHub (LinkedIn): Metadata platform with lineage                     │
│  - Apache Atlas: Hadoop ecosystem lineage                                 │
│  - Amundsen (Lyft): Discovery + lineage                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Privacy and Compliance

### GDPR/Privacy Architecture for ML

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PRIVACY-AWARE ML DATA ARCHITECTURE                                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Data Classification                                              │     │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │     │
│  │  │   PUBLIC   │  │  INTERNAL  │  │CONFIDENTIAL│  │RESTRICTED│ │     │
│  │  │(aggregates)│  │(pseudonym) │  │   (PII)    │  │(secrets) │ │     │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘ │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ML-Specific Privacy Techniques:                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  1. Differential Privacy (training)                               │     │
│  │     - Add calibrated noise to gradients                          │     │
│  │     - Guarantees: individual records can't be extracted          │     │
│  │     - Tool: TensorFlow Privacy, Opacus (PyTorch)                │     │
│  │     - Trade-off: ε=1 (strong privacy, ~5% accuracy loss)       │     │
│  │                                                                    │     │
│  │  2. Federated Learning                                            │     │
│  │     - Train on device, aggregate gradients                       │     │
│  │     - Data never leaves user's device                            │     │
│  │     - Tool: PySyft, TFF, NVIDIA FLARE                           │     │
│  │                                                                    │     │
│  │  3. Anonymization Pipeline                                        │     │
│  │     - K-anonymity: each record indistinguishable from K-1 others │     │
│  │     - L-diversity: sensitive values are diverse within groups     │     │
│  │     - T-closeness: distribution matches population               │     │
│  │                                                                    │     │
│  │  4. Right to be Forgotten (GDPR Art. 17)                         │     │
│  │     - Must delete user's data AND retrain model                  │     │
│  │     - Machine unlearning techniques (approximate)                │     │
│  │     - Practical: periodic full retraining with deleted users     │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  GDPR Compliance Checklist for ML:                                        │
│  ☐ Data minimization (only collect what's needed)                         │
│  ☐ Purpose limitation (document why each feature exists)                  │
│  ☐ Storage limitation (define retention periods)                          │
│  ☐ Right to explanation (model must be explainable)                       │
│  ☐ Right to deletion (process for removing user data)                     │
│  ☐ Data protection impact assessment (for high-risk models)              │
│  ☐ Consent management (track consent for data usage)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Storage Formats

### Format Comparison

| Format | Columnar | Compression | Schema | ACID | Best For |
|--------|----------|-------------|--------|------|----------|
| Parquet | Yes | Excellent (snappy/zstd) | Embedded | No | Analytics, ML training |
| Delta Lake | Yes (Parquet) | Same as Parquet | Registry | Yes | Lakehouse |
| Iceberg | Yes (Parquet/ORC) | Same as Parquet | Catalog | Yes | Multi-engine lakehouse |
| ORC | Yes | Excellent | Embedded | No | Hive ecosystem |
| Avro | Row | Good | Registry | No | Streaming, event data |
| JSON | Row | Poor | None | No | Flexibility, debugging |
| Arrow | Columnar | In-memory | Schema | No | Inter-process, analytics |

### Storage Strategy for ML

```
┌─────────────────────────────────────────────────────────────────┐
│  ML DATA STORAGE STRATEGY                                        │
│                                                                   │
│  HOT (< 7 days)    WARM (7-90 days)    COLD (> 90 days)       │
│  ┌──────────────┐  ┌──────────────┐    ┌──────────────┐       │
│  │ S3 Standard  │  │ S3 IA       │    │ S3 Glacier   │       │
│  │ or SSD       │  │             │    │              │       │
│  │              │  │             │    │              │       │
│  │ Active       │  │ Recent      │    │ Archive      │       │
│  │ training     │  │ training    │    │ Compliance   │       │
│  │ Serving data │  │ data        │    │ Audit        │       │
│  │              │  │             │    │              │       │
│  │ $0.023/GB    │  │ $0.0125/GB  │    │ $0.004/GB   │       │
│  └──────────────┘  └──────────────┘    └──────────────┘       │
│                                                                   │
│  ML-specific considerations:                                    │
│  - Training data: WARM (accessed weekly for retraining)        │
│  - Feature archives: WARM → COLD (lineage/audit)              │
│  - Model artifacts: HOT (serving) + COLD (all versions)       │
│  - Prediction logs: HOT (monitoring) → COLD (analysis)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Vector Databases

### Vector DB Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  VECTOR DATABASE ARCHITECTURE                                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Write Path                                                       │     │
│  │  Embedding → Shard Assignment → Index Update (HNSW/IVF)        │     │
│  │                                                                    │     │
│  │  Read Path (Query)                                                │     │
│  │  Query Vector → Multi-Shard Search → Merge Results → Top-K      │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Index Types                                                      │     │
│  │                                                                    │     │
│  │  HNSW (Hierarchical Navigable Small World):                      │     │
│  │  - Best recall/speed trade-off                                   │     │
│  │  - Memory: ~1.5x raw vector size                                │     │
│  │  - Query: O(log N)                                               │     │
│  │  - Build: Slow (hours for billions)                              │     │
│  │                                                                    │     │
│  │  IVF (Inverted File Index):                                      │     │
│  │  - Cluster vectors, search nearest clusters                      │     │
│  │  - Memory: ~1.1x raw vector size                                │     │
│  │  - Query: O(√N) with nprobe tuning                              │     │
│  │  - Build: Fast                                                    │     │
│  │                                                                    │     │
│  │  PQ (Product Quantization):                                      │     │
│  │  - Compress vectors (128D float → 32 bytes)                     │     │
│  │  - 4-8x memory reduction                                        │     │
│  │  - Slight recall loss (95-99%)                                   │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Vector DB Comparison

| Feature | Pinecone | Milvus | Weaviate | Qdrant | Chroma |
|---------|----------|--------|----------|--------|--------|
| Managed | Yes (only) | Optional | Optional | Optional | No |
| Scale | Billions | Billions | 100Ms | Billions | Millions |
| Latency (p99) | <50ms | <20ms | <30ms | <15ms | <50ms |
| Filtering | Metadata | Hybrid | GraphQL | Payload | Metadata |
| Multi-tenancy | Yes | Yes | Yes | Yes | No |
| Cost (1M vectors) | $70/mo | $20/mo (self) | $25/mo | $15/mo (self) | Free |
| Disk-based | No | Yes | Yes | Yes | Yes |
| Best For | Managed simplicity | Large-scale | Semantic search | Performance | Prototyping |

### Vector DB Sizing Example

```
Scenario: E-commerce product search
- 10M products
- 768-dim embeddings (BERT)
- 10K QPS

Memory calculation:
- Raw vectors: 10M × 768 × 4 bytes = 30.7 GB
- HNSW index overhead: ~1.5x = 46 GB
- With PQ compression: ~12 GB

Hardware:
- 3 nodes × 32GB RAM (with replication)
- Or: Milvus with disk index (cheaper, slightly slower)

Cost:
- Self-managed (3x r6g.xlarge): ~$500/month
- Pinecone (s1 pod): ~$700/month
- Qdrant Cloud: ~$450/month
```

---

## Data Cataloging and Discovery

```
┌─────────────────────────────────────────────────────────────────┐
│  DATA CATALOG FOR ML TEAMS                                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Catalog Entry: "user_transaction_features"              │   │
│  │                                                           │   │
│  │  Description: Aggregated transaction features per user   │   │
│  │  Owner: data-engineering@company.com                     │   │
│  │  Freshness: Updated daily at 3 AM UTC                   │   │
│  │  Quality Score: 98.5%                                   │   │
│  │  PII: No (aggregated, anonymized)                       │   │
│  │                                                           │   │
│  │  Schema:                                                 │   │
│  │  ├── user_id: STRING (PK)                               │   │
│  │  ├── total_amount_30d: FLOAT                            │   │
│  │  ├── transaction_count_30d: INT                         │   │
│  │  └── avg_amount_30d: FLOAT                              │   │
│  │                                                           │   │
│  │  Used by Models:                                         │   │
│  │  ├── fraud-detection-v2 (production)                    │   │
│  │  ├── credit-scoring-v1 (staging)                        │   │
│  │  └── churn-prediction-v3 (experiment)                   │   │
│  │                                                           │   │
│  │  Lineage: raw_transactions → clean_transactions → this  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Tools: DataHub, Amundsen, Apache Atlas, Collibra, Alation     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Real-World Case Studies

### Case Study: Uber's Data Platform (Michelangelo)
- **Scale**: 100+ PB data lake, 10K+ datasets
- **Architecture**: Kafka → Flink → Hive/HDFS (batch) + Redis (online)
- **Key Innovation**: Unified feature store serving both offline training and online serving from same definitions
- **Learning**: Invest in data discovery — data scientists spend 80% of time finding/understanding data

### Case Study: Netflix Data Mesh
- **Challenge**: Centralized data team became bottleneck
- **Solution**: Domain-oriented data ownership; each team owns their data products
- **ML Impact**: Teams can independently publish features; consumer teams self-serve
- **Learning**: Data mesh works when teams are mature; requires strong governance standards

### Production Incident: Silent Schema Change
- **Symptom**: Model accuracy dropped 20% over 2 days
- **Root Cause**: Upstream team changed a column from dollars to cents without notifying downstream
- **Impact**: 48 hours of degraded fraud detection (estimated $2M in missed fraud)
- **Fix**: Schema registry with breaking change detection, mandatory downstream notification
- **Learning**: Treat data as a contract; schema changes need the same rigor as API changes

### Production Incident: Data Lake Partition Corruption
- **Symptom**: Training pipeline produced model with 50% accuracy (random)
- **Root Cause**: S3 eventual consistency caused training to read partially-written partition
- **Fix**: Moved to Delta Lake (ACID writes), added data completeness checks
- **Learning**: Object stores have consistency gotchas; use table formats that provide ACID

---

## Interview Questions

1. **Design a data platform for an ML team processing 10TB/day with real-time features**
   - Focus: Lambda/Kappa, Kafka→Flink→Feature Store, batch layer for training

2. **How would you handle GDPR right-to-deletion when user data is embedded in ML models?**
   - Focus: Machine unlearning, periodic retraining, differential privacy

3. **Compare Delta Lake vs Iceberg for an ML-heavy organization**
   - Focus: Time travel for reproducibility, schema evolution, engine compatibility

4. **Design a data quality framework that prevents bad data from reaching ML models**
   - Focus: Great Expectations, schema registry, circuit breakers, quarantine zones

5. **How would you architect a vector search system for 1B embeddings with <20ms latency?**
   - Focus: Sharding strategy, index selection (HNSW+PQ), caching, hardware sizing

---

## Key Numbers to Remember

| Metric | Value | Context |
|--------|-------|---------|
| Parquet vs CSV read speed | 10-100x faster | Columnar + compression |
| Kafka throughput | 1M msg/sec per broker | With proper partitioning |
| Redis latency | <1ms p99 | For feature serving |
| S3 GET latency | 50-200ms | First byte; use caching |
| Delta Lake time travel | Any version in history | Default 30-day retention |
| Vector search (HNSW) | <5ms for 10M vectors | In-memory, single node |
| Flink checkpoint interval | 1-5 min typical | Balance: freshness vs overhead |
| Great Expectations validation | 10-60s per suite | Depends on data volume |
