# AWS Glue at Production Scale

## Context: Why This Exists

This folder explains **every AWS Glue concept** through **10 real production problems** that companies
like Netflix, Amazon, Capital One, Expedia, and major banks face when building **serverless ETL
pipelines processing petabytes of data daily**.

Instead of learning Glue in isolation, each problem teaches specific concepts in the context of
real-world data engineering challenges where traditional approaches (EC2-managed Spark, manual schema
management, hand-rolled job orchestration) fail.

---

## What is AWS Glue?

### The Problem It Solves

```
BEFORE AWS GLUE (Traditional ETL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Manual ETL scripts on EC2 → cluster management overhead
- No centralized schema management → data swamp
- No incremental processing → full table scans every run
- No auto-discovery → manual table definitions
- Cluster sizing guesswork → over/under-provisioning
- No built-in data quality → silent data corruption
- Manual dependency management → Python/Java version hell
- No visual authoring → data engineers only, no analysts
- No schema evolution tracking → breaking downstream consumers
- Manual retry/checkpoint → data loss on failures

AFTER AWS GLUE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Fully serverless → zero cluster management
- Centralized Data Catalog → Hive-compatible metastore for all AWS services
- Job Bookmarks → automatic incremental processing
- Crawlers → auto-discover schemas from S3, JDBC, DynamoDB
- Auto-scaling workers → pay only for what you use
- Built-in Data Quality (DQDL) → proactive quality checks
- Managed Spark/Python/Ray runtimes → zero dependency management
- Glue Studio → visual ETL for analysts and engineers
- Schema Registry → versioned schema evolution with compatibility checks
- Automatic retry with checkpointing → exactly-once processing
```

---

## History & Adoption Timeline

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2017 Q3 │ AWS Glue GA (Spark 2.2, Python 2.7) - Glue 0.9
         │ Data Catalog replaces Hive Metastore for Athena/EMR/Redshift Spectrum
2018     │ Glue 1.0: Spark 2.4, Python 3.6, Scala support
         │ Crawlers support 30+ data formats, JDBC connections
         │ Capital One adopts Glue for PCI-compliant data pipelines
2019     │ Glue Studio launched (visual ETL editor)
         │ SageMaker integration for ML feature engineering
         │ Streaming ETL support (Kafka, Kinesis sources)
2020     │ Glue 2.0: 10x faster startup (cold start: 10min → 1min)
         │ Elastic Views preview (materialized views across datastores)
         │ Development Endpoints for interactive debugging
2021     │ Glue 3.0: Spark 3.1, Python 3.7, 2x faster Spark shuffles
         │ Glue DataBrew GA (no-code data preparation)
         │ Schema Registry GA (Avro, JSON Schema)
         │ Auto-scaling (dynamic worker allocation)
2022     │ Glue 4.0: Spark 3.3, Python 3.10, optimized Spark runtime
         │ Glue Data Quality (DQDL rules engine)
         │ Flex execution class (non-urgent jobs at 34% cost savings)
         │ Custom connectors marketplace
2023     │ Glue 5.0: Ray support for Python-native distributed computing
         │ Amazon Q integration for natural language ETL
         │ Native Iceberg, Hudi, Delta Lake support
         │ G.4X and G.8X worker types (memory-intensive workloads)
2024     │ Zero-ETL integrations (Aurora→Redshift, DynamoDB→OpenSearch)
         │ Glue for Apache Spark optimized runtime (3-5x faster)
         │ Enhanced auto-scaling with predictive scaling
         │ AWS Lake Formation deep integration
2025     │ Z.2X workers (cost-optimized Spark)
         │ Glue Data Quality anomaly detection (ML-powered)
         │ Native vector transform support for GenAI pipelines
         │ Sub-second Interactive Sessions startup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Core Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                         AWS GLUE PRODUCTION ARCHITECTURE                             │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           GLUE DATA CATALOG                                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐   │   │
│  │  │Databases │  │ Tables   │  │ Partitions   │  │ Schema Registry       │   │   │
│  │  │(namespaces)│ │(metadata)│  │(partition keys)│ │(Avro/JSON/Protobuf)  │   │   │
│  │  └──────────┘  └──────────┘  └──────────────┘  └───────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│          ▲                    ▲                    ▲                                 │
│          │ register           │ read               │ validate                        │
│          │                    │                    │                                 │
│  ┌───────┴─────────┐  ┌─────┴──────────────────────────────────────────────┐      │
│  │   CRAWLERS       │  │              ETL ENGINE                             │      │
│  │                  │  │                                                     │      │
│  │ ┌─────────────┐ │  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │      │
│  │ │ Classifiers │ │  │  │  Apache   │  │  Python  │  │    Ray (5.0)     │ │      │
│  │ │ (built-in + │ │  │  │  Spark    │  │  Shell   │  │ (distributed Py) │ │      │
│  │ │  custom)    │ │  │  │  (3.3+)   │  │  (3.10+) │  │                  │ │      │
│  │ └─────────────┘ │  │  └──────────┘  └──────────┘  └──────────────────┘ │      │
│  │ ┌─────────────┐ │  │                                                     │      │
│  │ │ Scheduling  │ │  │  ┌──────────────────────────────────────────────┐   │      │
│  │ │ (cron/event)│ │  │  │           Streaming ETL                       │   │      │
│  │ └─────────────┘ │  │  │  (Kafka, Kinesis, MSK continuous processing) │   │      │
│  └──────────────────┘  │  └──────────────────────────────────────────────┘   │      │
│                         └────────────────────────────────────────────────────┘      │
│          │                              │                                           │
│          │                              │                                           │
│  ┌───────┴────────────────────┐  ┌─────┴──────────────────────────────────────┐   │
│  │   JOB BOOKMARKS            │  │          CONNECTIONS                        │   │
│  │                            │  │                                             │   │
│  │  State management for      │  │  ┌────────┐ ┌────────┐ ┌────────────────┐ │   │
│  │  incremental processing    │  │  │  JDBC  │ │ Kafka  │ │    Custom      │ │   │
│  │  (tracks processed files,  │  │  │(RDS,   │ │(MSK,   │ │  Connectors   │ │   │
│  │   timestamps, keys)        │  │  │Redshift)│ │Confluent)│ │(Marketplace)  │ │   │
│  └────────────────────────────┘  │  └────────┘ └────────┘ └────────────────┘ │   │
│                                   └────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      ORCHESTRATION LAYER                                     │   │
│  │                                                                              │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐   │   │
│  │  │ Triggers │  │  Workflows   │  │  EventBridge   │  │  Step Functions│   │   │
│  │  │(scheduled,│  │(multi-job DAG)│ │  (event-driven)│  │  (complex DAG) │   │   │
│  │  │ on-demand,│  │              │  │                │  │                │   │   │
│  │  │ conditional)│ │             │  │                │  │                │   │   │
│  │  └──────────┘  └──────────────┘  └────────────────┘  └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      AUTHORING & DEVELOPMENT                                 │   │
│  │                                                                              │   │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  ┌───────────────┐  │   │
│  │  │Glue Studio │  │ Interactive  │  │   DataBrew     │  │   Notebooks   │  │   │
│  │  │(visual ETL)│  │  Sessions    │  │  (no-code)     │  │  (Jupyter)    │  │   │
│  │  └────────────┘  └──────────────┘  └────────────────┘  └───────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Through the System

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Data Sources│────▶│ Crawlers │────▶│ Data Catalog │────▶│  ETL Jobs    │
│             │     │          │     │  (metadata)  │     │(Spark/Ray)   │
│ • S3        │     │ classify │     │              │     │              │
│ • JDBC (RDS)│     │ + schema │     │ • databases  │     │ • transform  │
│ • DynamoDB  │     │ infer    │     │ • tables     │     │ • enrich     │
│ • Kafka/MSK │     │          │     │ • partitions │     │ • aggregate  │
│ • Kinesis   │     └──────────┘     └──────────────┘     └──────┬───────┘
└─────────────┘                                                   │
                                                                  ▼
                                                    ┌──────────────────────┐
                                                    │   Data Targets       │
                                                    │                      │
                                                    │ • S3 (Parquet/Iceberg)│
                                                    │ • Redshift           │
                                                    │ • OpenSearch         │
                                                    │ • DynamoDB           │
                                                    │ • RDS/Aurora         │
                                                    └──────────────────────┘
```

---

## All AWS Glue Components Explained

### 1. Glue Data Catalog

The **centralized metadata repository** — a Hive-compatible metastore that serves as the single
source of truth for all data assets across AWS analytics services (Athena, EMR, Redshift Spectrum,
Lake Formation, Glue ETL).

```
┌────────────────────────────────────────────────────────────┐
│                  GLUE DATA CATALOG                           │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Database: "production_datalake"                            │
│  ├── Table: "raw_events"                                   │
│  │   ├── Location: s3://lake/raw/events/                   │
│  │   ├── Format: Parquet                                   │
│  │   ├── Schema: {user_id: string, event: string, ts: ts} │
│  │   ├── Partitions: year/month/day/hour                   │
│  │   └── Properties: {classification: "parquet"}           │
│  ├── Table: "curated_orders"                               │
│  │   ├── Location: s3://lake/curated/orders/               │
│  │   ├── Format: Iceberg                                   │
│  │   ├── Schema: {order_id: long, amount: decimal, ...}    │
│  │   └── Table Properties: {table_type: "ICEBERG"}         │
│  └── Table: "aggregated_metrics"                           │
│      └── ...                                               │
│                                                             │
│  Limits:                                                    │
│  • 10,000 databases per account                            │
│  • 1,000,000 tables per database                           │
│  • 10,000,000 partitions per table                         │
│  • 10 partition indexes per table                          │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

**Key Features:**
| Feature | Description | Production Use Case |
|---------|-------------|-------------------|
| Partition Indexes | B-tree indexes on partition keys | 10x faster partition pruning at scale |
| Table Versions | Automatic version history | Rollback bad schema changes |
| Column Statistics | min/max/nulls/distinct counts | Query optimizer hints for Athena/Redshift |
| Resource Links | Cross-account catalog sharing | Multi-account data mesh architectures |
| Lake Formation Tags | Attribute-based access control | Column-level security at scale |

---

### 2. Crawlers

Automated schema discovery that scans data stores and populates the Data Catalog.

```python
# Production crawler configuration
import boto3
glue = boto3.client('glue')

glue.create_crawler(
    Name='production-s3-crawler',
    Role='arn:aws:iam::123456789:role/GlueCrawlerRole',
    DatabaseName='production_datalake',
    Targets={
        'S3Targets': [
            {
                'Path': 's3://data-lake-prod/raw/',
                'Exclusions': ['**/_temporary/**', '**/.spark-staging/**'],
                'SampleSize': 10,  # sample 10 files per partition (scale param)
                'EventQueueArn': 'arn:aws:sqs:us-east-1:123:s3-events'  # event-driven
            }
        ]
    },
    SchemaChangePolicy={
        'UpdateBehavior': 'LOG',           # LOG vs UPDATE_IN_DATABASE
        'DeleteBehavior': 'DEPRECATE_IN_DATABASE'
    },
    RecrawlPolicy={'RecrawlBehavior': 'CRAWL_EVENT_MODE'},  # only new files
    Configuration=json.dumps({
        "Version": 1.0,
        "Grouping": {"TableGroupingPolicy": "CombineCompatibleSchemas"},
        "CrawlerOutput": {
            "Partitions": {"AddOrUpdateBehavior": "InheritFromTable"},
            "Tables": {"AddOrUpdateBehavior": "MergeNewColumns"}
        }
    }),
    Schedule='cron(0 */2 * * ? *)',  # every 2 hours
    Tags={'Environment': 'production', 'Team': 'data-platform'}
)
```

**Classifier Priority Order:**
1. Custom classifiers (user-defined grok patterns, JSON/CSV/XML paths)
2. Built-in classifiers (Parquet, ORC, Avro, JSON, CSV, TSV, Ion, etc.)
3. File extension fallback

---

### 3. ETL Jobs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ETL JOB TYPES                                    │
├─────────────────┬───────────────┬─────────────────┬─────────────────────┤
│   Spark ETL     │  Python Shell │    Ray (5.0)    │  Streaming ETL      │
├─────────────────┼───────────────┼─────────────────┼─────────────────────┤
│ • Distributed   │ • Single node │ • Distributed   │ • Micro-batch on    │
│   processing    │ • Lightweight │   Python-native │   Spark Structured  │
│ • PySpark/Scala │ • pandas, boto│ • No JVM        │   Streaming         │
│ • 2-100 DPUs    │ • 1/16 or 1   │ • ML workloads  │ • Kafka/Kinesis src │
│ • Large-scale   │   DPU max     │ • 2-100 workers │ • Continuous or     │
│   transforms    │ • Small tasks │ • ray.data      │   windowed          │
│ • Joins, agg    │ • API calls   │ • GPU support   │ • Checkpointing     │
└─────────────────┴───────────────┴─────────────────┴─────────────────────┘
```

---

### 4. DynamicFrame vs DataFrame

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DynamicFrame (Glue-native, handles schema inconsistencies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame

glueContext = GlueContext(SparkContext.getOrCreate())

# Read from catalog - handles mixed types automatically
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="production_datalake",
    table_name="raw_events",
    transformation_ctx="raw_events_read",           # bookmark context
    push_down_predicate="year='2025' AND month='01'",  # partition pruning
    additional_options={
        "boundedFiles": 1000,        # limit files per run (scale control)
        "boundedSize": "10737418240" # 10GB max per run
    }
)

# Resolve type ambiguities (e.g., price field is sometimes string, sometimes int)
resolved = dyf.resolveChoice(
    specs=[
        ('price', 'cast:double'),
        ('user_id', 'cast:string')
    ]
)

# Relationalize - flatten nested JSON into relational tables
relationalized = resolved.relationalize(
    root_table_name="events",
    staging_path="s3://temp-bucket/relationalize/"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DataFrame (standard PySpark, for complex transformations)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Convert for PySpark operations
df = dyf.toDF()

# Complex window function (not available in DynamicFrame API)
window = Window.partitionBy("user_id").orderBy("event_ts").rowsBetween(-6, 0)
df_enriched = df.withColumn("rolling_7day_total", F.sum("amount").over(window))

# Convert back for Glue-native writes with bookmarking
dyf_result = DynamicFrame.fromDF(df_enriched, glueContext, "enriched")
```

**When to use which:**
| Scenario | Use DynamicFrame | Use DataFrame |
|----------|-----------------|---------------|
| Mixed schema data (IoT, logs) | Yes | No |
| Job Bookmarks needed | Yes | Convert back |
| Complex window functions | No | Yes |
| ML feature engineering | No | Yes |
| Writing with catalog integration | Yes | Convert back |
| Resolving type conflicts | Yes (resolveChoice) | Manual casting |

---

### 5. Job Bookmarks

State management for **incremental processing** — tracks which data has been processed so jobs
don't reprocess the same files/rows.

```
┌───────────────────────────────────────────────────────────────────┐
│                    JOB BOOKMARK STATE MACHINE                       │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Run 1:  Files processed: [f1, f2, f3]                            │
│          Bookmark state: {last_file: "f3", timestamp: "2025-01-01"}│
│                          ▼                                         │
│  Run 2:  New files since state: [f4, f5]                          │
│          Only processes f4, f5                                     │
│          Bookmark state: {last_file: "f5", timestamp: "2025-01-02"}│
│                          ▼                                         │
│  Run 3:  New files since state: [f6]                              │
│          Only processes f6                                         │
│          Bookmark state: {last_file: "f6", timestamp: "2025-01-03"}│
│                                                                    │
│  BOOKMARK KEYS:                                                    │
│  • S3: file modification timestamp + path                         │
│  • JDBC: user-specified bookmark column (e.g., updated_at)        │
│  • DynamoDB: N/A (uses full table scan)                           │
│                                                                    │
│  OPERATIONS:                                                       │
│  • glue.reset_job_bookmark(JobName="...") → reprocess everything  │
│  • transformation_ctx parameter → per-source bookmark tracking    │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

```python
# JDBC bookmark example - incremental from RDS
jdbc_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="production",
    table_name="orders_rds",
    transformation_ctx="orders_incremental",  # CRITICAL: enables bookmarking
    additional_options={
        "jobBookmarkKeys": ["updated_at"],          # column to track
        "jobBookmarkKeysSortOrder": "asc"           # ascending order
    }
)
```

---

### 6. Connections

```
┌────────────────────────────────────────────────────────────────┐
│                     GLUE CONNECTIONS                             │
├──────────────────┬─────────────────────────────────────────────┤
│ Connection Type  │ Supported Sources                            │
├──────────────────┼─────────────────────────────────────────────┤
│ JDBC             │ RDS (MySQL, PostgreSQL, Oracle, SQL Server), │
│                  │ Redshift, Aurora, MariaDB, custom JDBC       │
├──────────────────┼─────────────────────────────────────────────┤
│ Kafka            │ Amazon MSK, Confluent Cloud, self-managed    │
├──────────────────┼─────────────────────────────────────────────┤
│ MongoDB          │ MongoDB Atlas, DocumentDB                    │
├──────────────────┼─────────────────────────────────────────────┤
│ Network          │ Any VPC-accessible endpoint (Elasticsearch,  │
│                  │ custom APIs via ENI in VPC)                  │
├──────────────────┼─────────────────────────────────────────────┤
│ Marketplace      │ Snowflake, SAP, Salesforce, Teradata,       │
│                  │ custom connectors (SparkConnector interface) │
├──────────────────┼─────────────────────────────────────────────┤
│ Secrets Manager  │ Credentials stored/rotated in AWS Secrets   │
│ integration      │ Manager (no plaintext passwords in config)  │
└──────────────────┴─────────────────────────────────────────────┘
```

---

### 7. Triggers & Workflows

```python
# Production workflow: event-driven pipeline
glue.create_workflow(Name='daily-etl-pipeline', MaxConcurrentRuns=1)

# Trigger 1: Start on S3 event (new data arrives)
glue.create_trigger(
    Name='on-raw-data-arrival',
    WorkflowName='daily-etl-pipeline',
    Type='EVENT',
    Actions=[{'JobName': 'raw-to-bronze', 'Arguments': {'--DPU': '20'}}],
    EventBatchingCondition={'BatchSize': 100, 'BatchWindow': 300}  # batch events
)

# Trigger 2: Conditional (only if raw-to-bronze succeeds)
glue.create_trigger(
    Name='bronze-to-silver',
    WorkflowName='daily-etl-pipeline',
    Type='CONDITIONAL',
    Predicate={
        'Conditions': [{
            'LogicalOperator': 'EQUALS',
            'JobName': 'raw-to-bronze',
            'State': 'SUCCEEDED'
        }]
    },
    Actions=[{'JobName': 'bronze-to-silver', 'Arguments': {'--DPU': '40'}}]
)

# Trigger 3: Conditional with multiple predecessors (fan-in)
glue.create_trigger(
    Name='aggregate-all',
    WorkflowName='daily-etl-pipeline',
    Type='CONDITIONAL',
    Predicate={
        'Logical': 'AND',
        'Conditions': [
            {'JobName': 'bronze-to-silver', 'State': 'SUCCEEDED'},
            {'JobName': 'enrich-dimensions', 'State': 'SUCCEEDED'}
        ]
    },
    Actions=[{'JobName': 'silver-to-gold', 'Arguments': {'--DPU': '60'}}]
)
```

---

### 8. Glue Studio

Visual ETL authoring tool with:
- Drag-and-drop DAG builder
- 40+ built-in transforms (Join, Filter, Aggregate, Pivot, Custom SQL)
- Custom visual transforms (reusable company-specific logic)
- Auto-generated PySpark code (editable)
- Job run monitoring with per-node metrics
- Data preview at each transform stage

---

### 9. Glue DataBrew

No-code data profiling and preparation:
- 250+ built-in transformations
- Statistical profiling (distributions, correlations, anomalies)
- Recipe-based transformation (version-controlled, repeatable)
- Schedule-driven profiling jobs
- Integration with Data Catalog

---

### 10. Glue Schema Registry

```
┌────────────────────────────────────────────────────────────────┐
│                   SCHEMA REGISTRY                                │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Schema: "user-events-avro"                                    │
│  ├── Version 1: {user_id: string, event: string}              │
│  ├── Version 2: {user_id: string, event: string, ts: long}   │ +field (BACKWARD compat)
│  └── Version 3: {user_id: string, event: string, ts: long,   │
│                   source: string}                               │ +field (BACKWARD compat)
│                                                                 │
│  Compatibility Modes:                                          │
│  • BACKWARD  - new schema can read old data                   │
│  • FORWARD   - old schema can read new data                   │
│  • FULL      - both backward and forward                      │
│  • NONE      - no compatibility checks                        │
│                                                                 │
│  Supported Formats: Avro, JSON Schema, Protobuf               │
│                                                                 │
│  Integration: Kafka producers/consumers, Glue ETL,            │
│               Kinesis Data Streams, MSK                        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

### 11. Glue Data Quality (DQDL)

```python
# Data Quality Definition Language (DQDL) ruleset
ruleset = """
Rules = [
    RowCount between 1000000 and 50000000,
    Completeness "user_id" >= 0.99,
    Completeness "email" >= 0.95,
    Uniqueness "order_id" >= 0.9999,
    ColumnValues "amount" between 0.01 and 999999.99,
    ColumnValues "country_code" in ["US", "UK", "DE", "FR", "JP", "IN"],
    CustomSql "SELECT COUNT(*) FROM primary WHERE amount < 0" <= 0,
    DataFreshness "event_ts" <= 2 hours,
    ReferentialIntegrity "user_id" "dim_users.user_id" >= 0.98,
    ColumnCorrelation "quantity" "total_amount" >= 0.7
]
"""

# Integrate into ETL job
from awsglue.transforms import EvaluateDataQuality

dq_results = EvaluateDataQuality.apply(
    frame=dyf,
    ruleset=ruleset,
    publishing_options={
        "dataQualityEvaluationContext": "order_pipeline_dq",
        "enableDataQualityCloudWatchMetrics": True,
        "enableDataQualityResultsPublishing": True
    }
)

# Route: pass good rows, quarantine bad rows
good_records = dq_results.filter(f=lambda x: x["dataQualityEvaluationResult"] == "Pass")
bad_records = dq_results.filter(f=lambda x: x["dataQualityEvaluationResult"] == "Fail")
```

---

### 12. Glue Interactive Sessions

```python
# Jupyter notebook magic commands for Glue Interactive Sessions
%glue_version 4.0
%worker_type G.2X
%number_of_workers 10
%idle_timeout 60
%additional_python_modules great_expectations,delta-spark

# Session starts in seconds, full Glue environment available
# Ideal for: development, debugging, ad-hoc exploration
# Cost: billed per-second after session starts (DPU-second)
```

---

### 13. Security Model

```
┌────────────────────────────────────────────────────────────────┐
│                    GLUE SECURITY LAYERS                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: IAM                                                  │
│  • Glue service role (access S3, Catalog, CloudWatch)          │
│  • Resource-based policies on Catalog (cross-account)          │
│  • Fine-grained: per-database, per-table, per-column           │
│                                                                 │
│  Layer 2: Lake Formation                                       │
│  • Column-level permissions (GRANT SELECT on col)              │
│  • Row-level filtering (data filters)                          │
│  • Tag-based access control (classification tags)              │
│  • Cell-level security (column + row intersection)             │
│                                                                 │
│  Layer 3: Encryption                                           │
│  • Data Catalog encryption (KMS)                               │
│  • Job bookmark encryption (KMS)                               │
│  • Connection password encryption (KMS)                        │
│  • S3 data encryption (SSE-S3, SSE-KMS, CSE-KMS)             │
│  • CloudWatch Logs encryption                                  │
│                                                                 │
│  Layer 4: Network                                              │
│  • VPC endpoints (no internet traversal)                       │
│  • ENI in customer VPC (for JDBC/network connections)          │
│  • Security groups on Glue ENIs                                │
│  • No public IP on Glue workers                                │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Execution Models & Worker Types

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         WORKER TYPES & DPU ALLOCATION                            │
├──────────┬──────────┬──────────┬───────────────────────────────────────────────┤
│ Worker   │ vCPU     │ Memory   │ Use Case                                      │
│ Type     │          │          │                                               │
├──────────┼──────────┼──────────┼───────────────────────────────────────────────┤
│ Standard │ 4 vCPU   │ 16 GB   │ General ETL, balanced workloads               │
│ G.1X     │ 4 vCPU   │ 16 GB   │ Memory-moderate jobs (1 DPU per worker)       │
│ G.2X     │ 8 vCPU   │ 32 GB   │ Memory-intensive (ML, large joins) 2 DPU/wkr │
│ G.4X     │ 16 vCPU  │ 64 GB   │ Very large shuffles, 4 DPU per worker        │
│ G.8X     │ 32 vCPU  │ 128 GB  │ Extreme memory needs, 8 DPU per worker       │
│ Z.2X     │ 8 vCPU   │ 32 GB   │ Cost-optimized (similar to G.2X, lower cost) │
├──────────┼──────────┼──────────┼───────────────────────────────────────────────┤
│ EXECUTION CLASSES                                                               │
├──────────┬──────────────────────────────────────────────────────────────────────┤
│ Standard │ Immediate start, SLA-backed, production workloads                    │
│ Flex     │ Best-effort start (may queue), 34% cheaper, non-urgent/overnight     │
└──────────┴──────────────────────────────────────────────────────────────────────┘

Auto-scaling (Glue 3.0+):
━━━━━━━━━━━━━━━━━━━━━━━━━
• Set: --number-of-workers (max), auto-scaling removes idle workers
• Scales down during low-parallelism phases
• Scales up when shuffle/join stages need more executors
• Minimum: 2 workers always running
• Metric: GlueAutoScaling.WorkerUtilization in CloudWatch
```

```python
# Production job configuration for 5TB daily processing
job_args = {
    '--job-language': 'python',
    '--job-bookmark-option': 'job-bookmark-enable',
    '--TempDir': 's3://glue-temp-prod/temp/',
    '--enable-metrics': 'true',
    '--enable-continuous-cloudwatch-log': 'true',
    '--enable-spark-ui': 'true',
    '--spark-event-logs-path': 's3://glue-spark-ui/logs/',
    '--enable-auto-scaling': 'true',
    '--conf': 'spark.sql.adaptive.enabled=true'
             '--conf spark.sql.shuffle.partitions=2000'
             '--conf spark.sql.files.maxPartitionBytes=134217728'  # 128MB
             '--conf spark.dynamicAllocation.enabled=true',
}

# Worker allocation: G.2X with 60 workers max = 120 DPU max
# Auto-scaling will use 10-60 workers depending on stage
glue.create_job(
    Name='production-daily-etl',
    GlueVersion='4.0',
    WorkerType='G.2X',
    NumberOfWorkers=60,
    ExecutionClass='STANDARD',
    Timeout=180,  # 3 hour timeout
    MaxRetries=2,
    DefaultArguments=job_args
)
```

---

## AWS Glue vs Alternatives

```
┌──────────────────┬──────────────┬──────────────┬───────────────┬──────────────┬───────────┐
│ Dimension        │ AWS Glue     │ EMR          │ Databricks    │ Airflow+Spark│ Lambda    │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Management       │ Serverless   │ Managed      │ Managed       │ Self-managed │ Serverless│
│                  │ (zero ops)   │ (some ops)   │ (low ops)     │ (high ops)   │ (zero ops)│
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Startup time     │ ~30s (4.0)   │ 5-10 min     │ 2-5 min       │ N/A          │ <1s       │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Max scale        │ 100 DPU      │ 1000s nodes  │ 1000s nodes   │ Unlimited    │ 10GB mem  │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Cost model       │ DPU-second   │ EC2+EMR fee  │ DBU-hour      │ EC2 cost     │ Per-invoke│
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Cost (5TB daily) │ ~$150-300/day│ ~$80-200/day │ ~$200-500/day │ ~$100-250/day│ N/A       │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Data Catalog     │ Built-in     │ Uses Glue    │ Unity Catalog │ External     │ N/A       │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Schema mgmt      │ Crawlers+    │ Manual/Glue  │ Auto-infer    │ Manual       │ N/A       │
│                  │ Registry     │              │               │              │           │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Orchestration    │ Workflows    │ Step Funcs   │ Jobs/Workflows│ DAGs         │ Step Funcs│
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Streaming        │ Structured   │ Full Spark   │ Full Spark    │ Full Spark   │ Event-    │
│                  │ Streaming    │ Streaming    │ Streaming     │ Streaming    │ driven    │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ ML integration   │ SageMaker    │ Full Spark ML│ MLflow native │ Any          │ SageMaker │
├──────────────────┼──────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Best for         │ AWS-native   │ Heavy custom │ Advanced      │ Complex DAGs │ Small     │
│                  │ ETL, catalog │ Spark, Hadoop│ analytics, ML │ multi-tool   │ transforms│
│                  │ management   │ ecosystem    │ collaboration │ orchestration│ <10min    │
└──────────────────┴──────────────┴──────────────┴───────────────┴──────────────┴───────────┘
```

---

## Pricing Model (us-east-1, 2025)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         AWS GLUE PRICING                                         │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ETL Jobs:                                                                     │
│  ━━━━━━━━━                                                                     │
│  • Standard execution: $0.44 per DPU-hour (billed per second, 1-min minimum)  │
│  • Flex execution:     $0.29 per DPU-hour (34% savings)                       │
│  • Ray jobs:           $0.44 per DPU-hour                                     │
│  • Python Shell:       $0.44 per DPU-hour (1/16 DPU or 1 DPU)               │
│                                                                                 │
│  Interactive Sessions:                                                         │
│  ━━━━━━━━━━━━━━━━━━━━                                                         │
│  • $0.44 per DPU-hour (billed per second after session starts)                │
│  • Idle timeout configurable (default: 2880 min)                              │
│                                                                                 │
│  Data Catalog:                                                                 │
│  ━━━━━━━━━━━━━                                                                 │
│  • First 1M objects stored free, then $1.00 per 100K objects/month            │
│  • First 1M requests free, then $1.00 per 1M requests                        │
│                                                                                 │
│  Crawlers:                                                                     │
│  ━━━━━━━━━                                                                     │
│  • $0.44 per DPU-hour (billed per second, 10-min minimum)                    │
│                                                                                 │
│  DataBrew:                                                                     │
│  ━━━━━━━━━                                                                     │
│  • Interactive sessions: $1.00 per session (30 min)                           │
│  • DataBrew jobs: $0.48 per node-hour                                         │
│                                                                                 │
│  Data Quality:                                                                 │
│  ━━━━━━━━━━━━━                                                                 │
│  • $0.10 per 1000 rule evaluations (first 1M free/month)                     │
│                                                                                 │
│  ╔══════════════════════════════════════════════════════════════════════════╗   │
│  ║  EXAMPLE: Daily 5TB pipeline, 60 G.2X workers, 45 min avg runtime      ║   │
│  ║  Cost = 60 workers × 2 DPU × 0.75 hr × $0.44 = $39.60/run            ║   │
│  ║  Monthly = $39.60 × 30 = $1,188/month                                 ║   │
│  ║                                                                         ║   │
│  ║  With Flex (overnight batch): $26.10/run → $783/month (34% savings)   ║   │
│  ╚══════════════════════════════════════════════════════════════════════════╝   │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10 Production Problems This Folder Solves

```
┌────┬──────────────────────────────────────┬─────────────────────────────┬──────────────────┐
│ #  │ Problem                              │ Glue Concepts Used          │ Scale            │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 01 │ Multi-source data lake ingestion     │ Crawlers, Connections,      │ 500+ sources,    │
│    │ (Netflix-scale raw zone)             │ DynamicFrames, Bookmarks    │ 50TB/day         │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 02 │ Schema evolution & compatibility     │ Schema Registry, Data       │ 10K+ schemas,    │
│    │ (streaming platform)                 │ Catalog versioning          │ 1M events/sec    │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 03 │ Incremental processing with exactly- │ Job Bookmarks, DynamicFrame │ 2B records/day,  │
│    │ once semantics (financial platform)  │ bounded execution           │ zero duplicates  │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 04 │ Real-time streaming ETL              │ Streaming jobs, Kafka       │ 500K events/sec, │
│    │ (e-commerce clickstream)             │ connection, windowing       │ sub-minute lag   │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 05 │ Data quality at scale with auto-     │ DQDL rules, quality scores, │ 100+ pipelines,  │
│    │ remediation (banking compliance)     │ CloudWatch alerting         │ 99.9% SLA        │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 06 │ Cross-account data mesh with         │ Resource links, Lake        │ 50+ accounts,    │
│    │ governance (enterprise platform)     │ Formation, catalog sharing  │ 10K+ tables      │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 07 │ Cost optimization & auto-scaling     │ Flex execution, auto-scale, │ $500K/mo→$180K/mo│
│    │ (startup scaling from 1TB to 100TB)  │ worker type selection       │ 10x growth       │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 08 │ ML feature store pipeline            │ Ray jobs, Interactive       │ 5000 features,   │
│    │ (recommendation engine)              │ Sessions, SageMaker integ.  │ 100M users       │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 09 │ CDC pipeline (database to lakehouse) │ JDBC connections, Bookmarks,│ 200+ tables,     │
│    │ (legacy migration)                   │ Workflows, Iceberg writes   │ 10K TPS source   │
├────┼──────────────────────────────────────┼─────────────────────────────┼──────────────────┤
│ 10 │ Multi-format data standardization    │ Custom classifiers,         │ 50+ formats,     │
│    │ (healthcare data platform)           │ DataBrew, Relationalize     │ HIPAA-compliant  │
└────┴──────────────────────────────────────┴─────────────────────────────┴──────────────────┘
```

---

## When to Use / When NOT to Use AWS Glue

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DECISION MATRIX                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ✅ USE AWS GLUE WHEN:                                                          │
│  ━━━━━━━━━━━━━━━━━━━━━                                                          │
│  • You need a serverless ETL with zero cluster management                       │
│  • Your data is primarily in AWS (S3, RDS, DynamoDB, Redshift)                 │
│  • You need a centralized data catalog (metadata management)                    │
│  • Jobs run < 48 hours and fit within 100 DPU limit                            │
│  • You want built-in incremental processing (bookmarks)                         │
│  • Non-engineering teams need visual ETL (Glue Studio/DataBrew)                │
│  • You need schema discovery for unknown/evolving data sources                  │
│  • Compliance requires data lineage and governance (Lake Formation)             │
│  • Cost predictability matters (DPU-second billing, no idle clusters)           │
│  • You process 100GB - 50TB per job run                                        │
│                                                                                  │
│  ❌ DO NOT USE AWS GLUE WHEN:                                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━                                                    │
│  • Jobs need > 100 DPU (use EMR for 1000+ node clusters)                       │
│  • Sub-second latency required (use Flink, Kinesis Analytics)                   │
│  • Heavy ML training on GPU clusters (use SageMaker, EMR with GPU)             │
│  • Custom Hadoop ecosystem tools needed (HBase, Presto tuning → EMR)           │
│  • Multi-cloud requirement (use Databricks, Spark on K8s)                      │
│  • Simple file transformations < 5 min (use Lambda, Step Functions)             │
│  • Interactive SQL queries only (use Athena directly)                           │
│  • Real-time stream processing with complex event processing (use Flink)        │
│  • Budget-sensitive with very large scale (EMR Spot can be 60-80% cheaper)     │
│  • You need custom Spark versions or bleeding-edge libraries                    │
│                                                                                  │
│  🤔 EVALUATE CAREFULLY:                                                         │
│  ━━━━━━━━━━━━━━━━━━━━━━                                                         │
│  • 10-50TB daily → Glue works but compare EMR Spot pricing                     │
│  • Mixed batch + streaming → Glue Streaming works, but Flink may be better     │
│  • Existing Airflow → Glue jobs can be called from Airflow operators           │
│  • Databricks already deployed → use Databricks, don't add Glue                │
│  • Need custom Spark configs → Glue supports many, but EMR gives full control  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Decision Flowchart

```
                    ┌─────────────────────────┐
                    │ Need ETL on AWS?        │
                    └───────────┬─────────────┘
                                │ Yes
                    ┌───────────▼─────────────┐
                    │ Data volume per job?    │
                    └───────────┬─────────────┘
                       ┌────────┼────────┐
                  <100MB   100MB-50TB   >50TB
                       │        │        │
                  ┌────▼───┐ ┌──▼────┐ ┌─▼──────┐
                  │Lambda/ │ │ AWS   │ │ EMR or │
                  │Step Fn │ │ Glue  │ │Databricks│
                  └────────┘ └───┬───┘ └─────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Need real-time (<1s)?   │
                    └───────────┬─────────────┘
                           No / │ \ Yes
                              │    └──→ Flink/KDA
                    ┌─────────▼──────────┐
                    │ Glue Spark or Ray?  │
                    └────────────────────┘
                    Spark: joins, SQL, aggregations
                    Ray: Python-native ML, pandas-heavy
```

---

## Quick Reference: Essential Glue CLI Commands

```bash
# List all jobs
aws glue get-jobs --query 'Jobs[].Name'

# Start a job run with overrides
aws glue start-job-run \
  --job-name "production-daily-etl" \
  --arguments='{"--DPU":"80","--enable-auto-scaling":"true"}' \
  --worker-type G.2X \
  --number-of-workers 40

# Check job run status
aws glue get-job-run --job-name "production-daily-etl" --run-id "jr_xxxxx"

# Reset bookmark (reprocess all data)
aws glue reset-job-bookmark --job-name "production-daily-etl"

# Get table from catalog
aws glue get-table --database-name "production" --name "orders"

# Start crawler
aws glue start-crawler --name "production-s3-crawler"

# Get data quality results
aws glue get-data-quality-result --result-id "dqresult-xxxxx"
```

---

## File Organization in This Folder

```
10-aws-glue-production-at-scale/
├── 00-overview.md                    ← You are here
├── 01-multi-source-ingestion.md      ← Problem 1: 500+ source lake ingestion
├── 02-schema-evolution.md            ← Problem 2: Schema registry at scale
├── 03-incremental-processing.md      ← Problem 3: Exactly-once with bookmarks
├── 04-streaming-etl.md               ← Problem 4: Real-time clickstream
├── 05-data-quality.md                ← Problem 5: DQDL compliance pipelines
├── 06-data-mesh-governance.md        ← Problem 6: Cross-account data mesh
├── 07-cost-optimization.md           ← Problem 7: Auto-scaling & Flex execution
├── 08-ml-feature-pipeline.md         ← Problem 8: Ray + feature store
├── 09-cdc-pipeline.md                ← Problem 9: Database to lakehouse CDC
└── 10-multi-format-standardization.md← Problem 10: Healthcare data platform
```
