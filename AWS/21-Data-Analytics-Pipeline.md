# AWS Data & Analytics - Kinesis, Glue, Athena, Redshift, EMR & Lake Formation

---

## 1. Data Architecture Overview

### Modern Data Architecture (Lakehouse)
```
Sources → Ingestion → Storage → Processing → Serving → Consumption

Sources:          Applications, IoT, Databases, SaaS, Logs, Clickstream
Ingestion:        Kinesis, MSK, DMS, DataSync, Firehose, AppFlow
Storage:          S3 Data Lake (raw → processed → curated)
Processing:       Glue ETL, EMR (Spark), Lambda, Step Functions
Catalog:          Glue Data Catalog (central metadata store)
Governance:       Lake Formation (permissions, data sharing)
Serving:          Redshift (warehouse), Athena (ad-hoc), OpenSearch (search)
Consumption:      QuickSight (BI), SageMaker (ML), APIs
```

### Data Lake Zones (Medallion Architecture)
| Zone | Purpose | Format | Access |
|------|---------|--------|--------|
| Bronze (Raw) | Landing zone, immutable copy | Original (JSON, CSV, Avro) | ETL jobs only |
| Silver (Processed) | Cleaned, validated, enriched | Parquet/ORC, partitioned | Analysts, ML |
| Gold (Curated) | Business-ready, aggregated | Parquet, denormalized | BI dashboards, APIs |

---

## 2. Amazon Kinesis (Real-Time Streaming)

### Kinesis Data Streams
- **What:** Real-time data streaming service. Collect, process, analyze data in real-time
- **Concept:** Stream → Shards → Records (partition key, sequence number, data blob)
- **Retention:** 24 hours (default) to 365 days
- **Capacity:** Each shard: 1 MB/sec write (1000 records/sec), 2 MB/sec read
- **Ordering:** Per-partition-key ordering guaranteed within a shard

#### Capacity Modes
| Mode | Scaling | Cost | Use Case |
|------|---------|------|----------|
| Provisioned | Manual (add/remove shards) | Per shard-hour ($0.015/hr) | Predictable traffic |
| On-Demand | Auto (up to 200 MB/sec write) | Per GB ($0.08 ingress, $0.034 retrieval) | Variable/unknown traffic |

#### Producers
- AWS SDK (PutRecord, PutRecords)
- Kinesis Producer Library (KPL): Batching, aggregation, retry, metrics
- Kinesis Agent: Install on servers, tail log files → stream
- CloudWatch Logs subscription, IoT Core rules, DMS

#### Consumers
- **Shared Fan-Out:** All consumers share 2 MB/sec per shard (pull via GetRecords)
- **Enhanced Fan-Out:** Each consumer gets dedicated 2 MB/sec per shard (push via HTTP/2, SubscribeToShard)
- Consumer options: Lambda, KCL (Kinesis Client Library), Flink, Spark Streaming

#### Kinesis Client Library (KCL)
- Coordinates shard processing across multiple workers
- Uses DynamoDB for lease tracking (which worker owns which shard)
- Handles shard splits/merges automatically
- Checkpointing: Resume from last processed record after failure
- **Best practice:** Number of KCL workers ≤ number of shards

#### Shard Operations
- **Split:** Divide hot shard into two (increase capacity)
- **Merge:** Combine two cold shards (reduce cost)
- **Resharding:** Can't split/merge multiple simultaneously (one at a time, or use UpdateShardCount)

### Kinesis Data Firehose
- **What:** Fully managed delivery service. Load streaming data into destinations
- **No code needed:** Just configure source → optional transformation → destination
- **Near real-time:** Buffer interval (60-900 seconds) or buffer size (1-128 MB)
- **Destinations:** S3, Redshift (via S3 COPY), OpenSearch, Splunk, HTTP endpoint, Datadog, MongoDB

#### Firehose Features
- **Transformation:** Lambda function (transform records in-flight)
- **Format conversion:** JSON → Parquet/ORC (using Glue Data Catalog schema)
- **Compression:** GZIP, Snappy, ZIP (for S3 delivery)
- **Partitioning:** Dynamic partitioning (route records to different S3 prefixes based on content)
- **No retention:** If delivery fails, retries for 24 hours. No replay capability
- **Source:** Kinesis Data Streams, Direct PUT, CloudWatch Logs, IoT, MSK

### Kinesis Data Analytics (Managed Flink)
- **What:** Run Apache Flink applications on streaming data (SQL or Java/Python)
- **Use cases:** Real-time dashboards, anomaly detection, streaming ETL, windowed aggregations
- **Sources:** Kinesis Data Streams, MSK
- **Sinks:** Kinesis, Firehose, S3, DynamoDB, Lambda

#### Flink Concepts
- **Windowing:** Tumbling (fixed, non-overlapping), Sliding (overlapping), Session (gap-based)
- **State:** Managed state (checkpointed to S3), exactly-once processing
- **Scaling:** Parallelism (KPU - Kinesis Processing Units)
```sql
-- Real-time aggregation (SQL mode)
CREATE OR REPLACE STREAM "DESTINATION_SQL_STREAM" (
  event_time TIMESTAMP, total_orders INTEGER, avg_amount DOUBLE
);
INSERT INTO "DESTINATION_SQL_STREAM"
SELECT STREAM
  ROWTIME as event_time,
  COUNT(*) as total_orders,
  AVG(amount) as avg_amount
FROM "SOURCE_SQL_STREAM"
GROUP BY STEP("SOURCE_SQL_STREAM".ROWTIME BY INTERVAL '1' MINUTE);
```

### Kinesis vs SQS vs MSK
| Feature | Kinesis | SQS | MSK (Kafka) |
|---------|---------|-----|-------------|
| Model | Stream (replay) | Queue (delete after process) | Stream (replay) |
| Ordering | Per-shard | FIFO only | Per-partition |
| Retention | 1-365 days | 1-14 days | Unlimited (tiered) |
| Consumers | Multiple (fan-out) | Single (per message) | Multiple (consumer groups) |
| Throughput | MB/sec per shard | Unlimited | Very high (partitions) |
| Management | Managed | Fully managed | Semi-managed |
| **Use** | Real-time analytics, logs | Decouple, buffer | High-throughput, ecosystem |

---

## 3. AWS Glue (ETL & Data Catalog)

### Glue Data Catalog
- **What:** Central metadata repository (tables, schemas, partitions, locations)
- **Hive-compatible:** Works as metastore for Athena, Redshift Spectrum, EMR
- **Crawlers:** Auto-discover schemas from S3, JDBC, DynamoDB → create/update tables
- **Databases:** Logical grouping of tables (namespace)
- **Schema versioning:** Track schema changes over time

### Glue ETL Jobs
- **Engine:** Apache Spark (PySpark/Scala) or Python Shell (lightweight)
- **Serverless:** No infrastructure to manage (DPU-based: Data Processing Units)
- **DPU:** 4 vCPU + 16 GB RAM. Min 2 DPU for Spark, configurable up to 100+
- **Job Bookmarks:** Track already-processed data (incremental ETL)
- **Job types:**
  - Spark: Large-scale ETL (distributed)
  - Spark Streaming: Near real-time (micro-batch from Kinesis/MSK)
  - Python Shell: Small tasks (1 DPU max, simple scripts)
  - Ray: Distributed Python (ML workloads)

### Glue Dynamic Frames
```python
# Glue ETL Script Example
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext

sc = SparkContext()
glueContext = GlueContext(sc)

# Read from catalog
datasource = glueContext.create_dynamic_frame.from_catalog(
    database="sales_db",
    table_name="raw_orders"
)

# Transform
mapped = ApplyMapping.apply(
    frame=datasource,
    mappings=[
        ("order_id", "string", "order_id", "string"),
        ("amount", "string", "amount", "double"),
        ("order_date", "string", "order_date", "timestamp")
    ]
)

# Filter
filtered = Filter.apply(frame=mapped, f=lambda x: x["amount"] > 0)

# Write to S3 as Parquet, partitioned
glueContext.write_dynamic_frame.from_options(
    frame=filtered,
    connection_type="s3",
    connection_options={
        "path": "s3://data-lake/processed/orders/",
        "partitionKeys": ["year", "month"]
    },
    format="parquet"
)
```

### Glue Features
- **Glue Studio:** Visual ETL editor (drag and drop)
- **Glue DataBrew:** No-code data preparation (250+ transformations, profiling)
- **Data Quality:** Define rules, validate data during ETL (DQDL - Data Quality Definition Language)
- **Glue Schema Registry:** Apache Avro/JSON schema management for streaming (Kinesis, MSK)
- **Glue Connections:** JDBC, MongoDB, Kafka, Redis, custom connectors (Marketplace)
- **Workflows:** Orchestrate multiple crawlers + jobs (or use Step Functions)

---

## 4. Amazon Athena (Serverless SQL)

### Overview
- **What:** Interactive SQL query service on S3 data (serverless, no infrastructure)
- **Engine:** Presto/Trino (distributed SQL engine)
- **Pricing:** $5 per TB scanned (massive savings with partitioning + columnar formats)
- **Input:** S3 data in CSV, JSON, Parquet, ORC, Avro, and more
- **Output:** Query results → S3 bucket

### Performance Optimization
| Technique | Impact | How |
|-----------|--------|-----|
| Columnar format (Parquet/ORC) | 30-90% less scanned | Glue ETL converts JSON→Parquet |
| Partitioning | 10-100× less scanned | `WHERE year=2024 AND month=01` skips other partitions |
| Compression | 30-50% less scanned | Snappy/GZIP on Parquet files |
| Bucketing | Faster joins | Hash distribute by join key |
| File size optimization | Fewer S3 calls | 128MB-512MB files (not millions of tiny files) |
| CTAS (Create Table As) | Materialize results | Pre-compute expensive queries |

### Athena Features
- **Federated Query:** Query RDS, DynamoDB, Redshift, CloudWatch Logs, on-prem via Lambda connectors
- **Prepared Statements:** Parameterized queries (security, performance)
- **Workgroups:** Isolate queries, control costs (per-query/workgroup cost limits)
- **ACID Transactions:** Apache Iceberg table format (INSERT, UPDATE, DELETE, time travel)
- **Cost control:** Workgroup limit (e.g., max $100/day), partition projection (eliminate Glue crawler)

### Partition Projection
```sql
-- Eliminates need for Glue Crawler on time-based data
CREATE EXTERNAL TABLE logs (
  message STRING,
  level STRING
)
PARTITIONED BY (year STRING, month STRING, day STRING)
LOCATION 's3://my-logs/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.year.type' = 'integer',
  'projection.year.range' = '2020,2030',
  'projection.month.type' = 'integer',
  'projection.month.range' = '1,12',
  'projection.month.digits' = '2',
  'projection.day.type' = 'integer',
  'projection.day.range' = '1,31',
  'projection.day.digits' = '2',
  'storage.location.template' = 's3://my-logs/${year}/${month}/${day}/'
);
```

---

## 5. Amazon Redshift (Data Warehouse)

### Overview
- **What:** Petabyte-scale columnar data warehouse (MPP - Massively Parallel Processing)
- **Use case:** Complex analytical queries, BI reporting, large aggregations
- **Architecture:** Leader node (query planning) + Compute nodes (execution, storage)
- **Pricing:** On-Demand ($0.25/hr per dc2.large), Reserved (1-3 yr, ~50% savings), Serverless

### Redshift Serverless vs Provisioned
| | Provisioned | Serverless |
|--|---|---|
| Management | Choose node type/count | Auto-scaled |
| Scaling | Resize cluster (downtime) or Elastic Resize | Auto (RPU: Redshift Processing Units) |
| Cost | Per-node-hour (always running) | Per RPU-hour (only when queries run) |
| **Use** | Predictable, steady workloads | Variable, intermittent queries |

### Key Features
- **Columnar storage:** Only reads columns needed (not full rows) — 10× less I/O
- **Compression:** Automatic column encoding (AZ64, LZO, Zstandard)
- **Distribution styles:** AUTO, KEY, EVEN, ALL (controls data placement across nodes)
- **Sort keys:** Compound or Interleaved (enables zone maps for predicate pushdown)
- **Materialized views:** Pre-computed aggregations (auto-refresh)
- **Concurrency Scaling:** Auto-adds transient clusters for burst query demand
- **AQUA (Advanced Query Accelerator):** Hardware-accelerated cache layer (10× for certain queries)
- **Data Sharing:** Share live data across Redshift clusters without copying
- **Spectrum:** Query S3 data directly (extend warehouse to data lake without loading)

### Redshift Spectrum
```sql
-- Query S3 data lake from Redshift without loading
CREATE EXTERNAL SCHEMA spectrum_schema
FROM DATA CATALOG
DATABASE 'my_glue_database'
IAM_ROLE 'arn:aws:iam::123:role/RedshiftSpectrumRole';

-- Join warehouse table with S3 data
SELECT w.customer_id, w.name, s.total_orders
FROM warehouse.customers w
JOIN spectrum_schema.order_history s ON w.customer_id = s.customer_id
WHERE s.year = '2024';
```

### Loading Data
- **COPY command:** Most efficient (parallel load from S3, DynamoDB, EMR)
- **Firehose:** Streaming delivery to Redshift (via S3 staging + COPY)
- **DMS:** Continuous replication from OLTP databases
- **Glue:** ETL jobs write to Redshift
- **Best practice:** Use COPY from S3 with multiple files (parallel per-slice loading)

---

## 6. Amazon EMR (Big Data Processing)

### Overview
- **What:** Managed Hadoop/Spark clusters for big data processing
- **Frameworks:** Spark, Hive, Presto, HBase, Flink, Pig, Tez
- **Deployment:** EC2 (cluster), EKS (containers), Serverless
- **Use case:** Massive ETL (petabyte-scale), ML training, genomics, log analysis

### EMR Architecture
```
EMR Cluster:
  Primary node: Resource management, job coordination (YARN)
  Core nodes: HDFS storage + task execution (critical, keep running)
  Task nodes: Compute only, no storage (use Spot, scale up/down)
```

### EMR on EKS
- Run Spark jobs on existing EKS cluster (no separate EMR cluster)
- Share compute resources between Spark and microservices
- Faster startup (no cluster provisioning), Kubernetes-native

### EMR Serverless
- No cluster management. Submit Spark/Hive jobs, auto-scales
- Pre-initialized workers (reduce startup latency)
- Pay per vCPU-hour + memory-hour while job runs
- **Use case:** Intermittent workloads, teams that don't want cluster ops

### EMR vs Glue
| | EMR | Glue |
|--|---|---|
| Flexibility | Full (any Spark config, any framework) | Limited (Glue APIs, DPUs) |
| Management | Semi-managed (cluster lifecycle) | Fully managed (serverless) |
| Cost control | Spot instances, cluster sharing | Per-DPU-second |
| Ecosystem | Hadoop, Hive, Presto, Flink, etc. | Spark only (+ Python shell) |
| **Choose EMR** | Complex Spark tuning, multi-framework, existing Hadoop | |
| **Choose Glue** | Simple ETL, small teams, no ops appetite | |

---

## 7. AWS Lake Formation

### Overview
- **What:** Build, secure, and manage data lakes easily (built on top of Glue + S3 + IAM)
- **Simplifies:** Data ingestion, cataloging, security, governance in one place
- **Key value:** Fine-grained access control (column, row, cell-level permissions)

### Permissions Model
```
Without Lake Formation:
  S3 bucket policies + IAM policies + Glue resource policies = complex, scattered

With Lake Formation:
  Central permission model:
    GRANT SELECT ON TABLE orders (column: customer_id, amount)
    TO ROLE 'analyst-role'
    WHERE department = 'sales'  (row-level filter)
```

### Features
- **Blueprints:** Pre-built ingestion workflows (database → S3, log → S3)
- **Cross-account sharing:** Share tables/columns with other accounts (no S3 bucket policy gymnastics)
- **Data Filters:** Row and cell-level security (like a SQL view but enforced at catalog level)
- **Governed Tables:** ACID transactions on S3 (insert, update, delete with rollback)
- **Tag-based access:** LF-Tags (classify data with tags, grant access by tag)

---

## 8. Amazon MSK (Managed Streaming for Apache Kafka)

### Overview
- **What:** Fully managed Apache Kafka (open-source event streaming platform)
- **Compatible:** Use existing Kafka clients, tools, libraries unchanged
- **Deployment:** MSK Provisioned (you choose brokers) or MSK Serverless (auto-scaled)

### MSK vs Kinesis
| | MSK | Kinesis Data Streams |
|--|---|---|
| Protocol | Kafka native | AWS proprietary API |
| Ecosystem | Rich (Kafka Connect, Schema Registry, MirrorMaker) | AWS SDK, Lambda |
| Consumers | Consumer groups (flexible) | KCL, Lambda |
| Management | Semi-managed (broker config, storage) | Fully managed |
| Retention | Unlimited (tiered storage) | 1-365 days |
| Cost | Per-broker-hour + storage | Per-shard-hour or per-GB |
| **Choose MSK** | Existing Kafka, rich ecosystem, high customization | |
| **Choose Kinesis** | Serverless, tight AWS integration, simpler ops | |

### MSK Connect
- Managed Kafka Connect workers (source and sink connectors)
- Connectors: Debezium CDC, S3 sink, JDBC source, Elasticsearch, etc.
- Serverless or provisioned capacity

---

## 9. Data Pipeline Patterns

### Batch ETL Pipeline
```
S3 (raw) → Glue Crawler (discover schema) → Glue ETL (transform)
  → S3 (processed, Parquet) → Athena (query) / Redshift (warehouse)
  
Orchestration: Step Functions or Glue Workflows
Schedule: EventBridge (daily/hourly trigger)
Monitoring: Glue job metrics → CloudWatch → Alarm on failure
```

### Real-Time Streaming Pipeline
```
Producers → Kinesis Data Streams → Consumers:
  ├── Lambda (real-time alerts, low-latency)
  ├── Kinesis Data Analytics (Flink - windowed aggregation)
  ├── Firehose → S3 (archive, Parquet format)
  └── Firehose → OpenSearch (search/dashboards)

Enrichment: Lambda reads reference data from DynamoDB/ElastiCache
Monitoring: IteratorAge (freshness), IncomingRecords (throughput)
```

### Change Data Capture (CDC) Pipeline
```
Source RDS/Aurora → DMS (CDC replication) → Kinesis Data Streams
  → Lambda (transform) → DynamoDB (real-time serving)
  → Firehose → S3 (data lake history)
  → MSK Connect (Debezium alternative for self-managed)
  
Use case: Sync OLTP to analytics/search without impacting source
```

### Event Sourcing + CQRS
```
Command → API → Kinesis (event store / append only)
  → Lambda (project events → write model: DynamoDB)
  → Lambda (project events → read model: ElastiCache/OpenSearch)
  → Firehose → S3 (event archive for replay)
  
Benefits: Full audit trail, temporal queries, independent read/write scaling
```

---

## 10. Scenario-Based Interview Questions

### Q1: Design real-time analytics for 1 million events/second clickstream
**Answer:**
```
Architecture:
  Web/Mobile SDK → API Gateway → Kinesis Data Streams (On-Demand mode)
    ~1000 shards (1M events × 1KB each = 1 GB/sec input)
    
  Real-time path:
    Kinesis → Managed Flink (Kinesis Data Analytics):
      - Windowed aggregations (page views per minute, unique users per 5 min)
      - Anomaly detection (traffic drop > 50% → alarm)
      - Output → DynamoDB (real-time dashboard backend)
      - Output → CloudWatch custom metrics
      
  Near real-time path:
    Kinesis → Firehose:
      - Buffer: 128 MB or 5 minutes
      - Transform: Lambda adds geo-enrichment
      - Format: Convert JSON → Parquet (Glue schema)
      - Destination: S3 (partitioned by year/month/day/hour)
      
  Batch analytics:
    S3 → Athena (ad-hoc: "what pages did user X visit yesterday?")
    S3 → Redshift Spectrum (join with user table for segmentation)
    S3 → EMR Spark (weekly: build ML recommendation model)
    
  Cost estimate (~$15K/month):
    Kinesis On-Demand: ~$6K (1GB/sec × $0.08/GB)
    Flink: ~$3K (20 KPUs)
    Firehose: ~$2K (ingestion + format conversion)
    S3: ~$1K (30TB compressed Parquet)
    Athena/Redshift: ~$3K (queries)
```

### Q2: Migrate data warehouse from on-prem Oracle to AWS
**Answer:**
```
Assessment:
  - Current: Oracle DW, 50TB, 200 concurrent users, complex stored procedures
  - Workload types: BI dashboards (80%), ad-hoc (15%), data science (5%)
  
Strategy:
  Phase 1: Lift and shift (quick win)
    - AWS SCT (Schema Conversion Tool): Convert DDL to Redshift
    - DMS: Full load + CDC replication (Oracle → Redshift)
    - Run parallel (Oracle + Redshift) for validation
    
  Phase 2: Modernize
    - Separate workloads:
      - BI dashboards → Redshift (provisioned, RI for steady load)
      - Ad-hoc → Athena (serverless, pay per query)
      - Data science → EMR/SageMaker (raw data from S3)
    - ETL: Replace stored procedures with Glue ETL (Spark)
    - Storage: S3 data lake (source of truth) → Redshift loads from S3
    
  Phase 3: Optimize
    - Redshift: Distribution keys, sort keys, materialized views
    - Lake Formation: Govern access centrally
    - Cost: Reserved Instances for Redshift, lifecycle policies on S3
    
  Challenges:
    - Stored procedures: No direct equivalent. Rewrite as Glue/Step Functions
    - Oracle-specific SQL: SCT converts ~80%, manual for complex
    - Data validation: Row counts, checksums, business rule verification
    - User training: New tools (Athena, QuickSight vs Oracle BI)
```

### Q3: How to handle late-arriving data in streaming pipeline?
**Answer:**
```
Problem: Events arrive out of order (mobile offline, network delays)
  Event with timestamp 10:00 arrives at 10:15 (15 min late)
  If window 10:00-10:05 already closed → event is "late"

Solutions:
  1. Watermarks (Flink):
     - Watermark = "current event time - max expected lateness"
     - Window fires when watermark passes window end
     - Configure allowed lateness (e.g., 1 hour)
     - Late events: Update previous window result OR route to side output
     
  2. Lambda architecture:
     - Speed layer: Real-time (may be inaccurate due to late data)
     - Batch layer: Nightly reprocessing (correct, complete)
     - Serving layer: Merge both (real-time overwritten by batch)
     
  3. Kappa architecture:
     - Single streaming layer with Kinesis retention (7-365 days)
     - Reprocess from stream when corrections needed
     - Simpler but needs careful late-event handling
     
  4. Practical approach (most common):
     - Accept 5-min lateness in real-time aggregations
     - Batch job runs hourly: recompute last 2 hours from S3 (overwrites)
     - Final daily batch: authoritative numbers
     - Dashboard shows: "real-time (approximate)" vs "final (T+1 day)"
```

### Q4: Athena queries are slow and expensive. How to optimize?
**Answer:**
```
Current state: CSV files in S3, no partitioning, 10TB scanned per query

Optimization (priority order):
  1. Convert to Parquet/ORC (biggest impact):
     - Glue ETL job: read CSV → write Parquet (columnar + compressed)
     - Result: 90% less data scanned (read only needed columns)
     - Cost: $50/TB → $5/TB per query
     
  2. Partition data:
     - s3://bucket/year=2024/month=01/day=15/data.parquet
     - WHERE year='2024' AND month='01' → scans only that partition
     - Result: Query scans 1 day instead of all data
     
  3. File size optimization:
     - Problem: 1 million tiny files = 1M S3 GET requests = slow
     - Solution: Compact to 128-512 MB files (Glue job or S3 batch)
     
  4. Partition projection:
     - Eliminate Glue Crawler latency for known partition patterns
     - Athena calculates partitions mathematically (instant)
     
  5. CTAS for common queries:
     - Materialize expensive joins as new table
     - Schedule refresh via Step Functions/EventBridge
     
  6. Workgroup cost controls:
     - Per-query limit: Fail if would scan > 1 TB
     - Per-workgroup limit: $100/day maximum
     
  Before: 10 TB scanned, 5 minutes, $50/query
  After: 100 GB scanned, 10 seconds, $0.50/query (100× improvement)
```

### Q5: Design a data mesh architecture on AWS
**Answer:**
```
Principles:
  - Domain ownership (each team owns their data product)
  - Data as a product (discoverable, documented, SLA'd)
  - Self-serve platform (easy to publish and consume)
  - Federated governance (global standards, local implementation)

Architecture:
  Central Platform (Platform Team):
    - Lake Formation: Central governance, tag-based access
    - Glue Data Catalog: Federated (per-domain databases, central discoverability)
    - DataZone: Data marketplace (publish/subscribe to data products)
    - Shared infrastructure: S3 buckets, Kinesis, MSK, networking
    
  Domain A (Orders Team):
    - Own S3 bucket: s3://domain-orders/
    - Own Glue database: orders_domain
    - Publish data products: Lake Formation cross-account sharing
    - Own pipeline: Glue ETL, quality checks
    - SLA: Freshness < 1 hour, completeness > 99.9%
    
  Domain B (Customer Team):
    - Own S3 bucket, own Glue database
    - Consumes: Orders data product (read access via Lake Formation)
    - Publishes: Customer 360 data product
    
  Governance:
    - LF-Tags: classification (PII, financial, public)
    - Auto-applied based on Macie discovery
    - Global rules: PII requires encryption, no cross-region for EU data
    - Audit: CloudTrail + Lake Formation access logs
    
  Discovery:
    - AWS DataZone catalog: Search all data products
    - Each product: Schema, SLA, owner, sample data, lineage
    - Self-serve subscription: Request access → auto-granted by tag match
```

