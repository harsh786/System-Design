# AWS Data Services - Deep Dive

## Table of Contents
1. [Amazon Kinesis](#1-amazon-kinesis)
2. [Amazon MSK](#2-amazon-msk)
3. [AWS Glue](#3-aws-glue)
4. [Amazon Athena](#4-amazon-athena)
5. [AWS Lake Formation](#5-aws-lake-formation)
6. [AWS DMS](#6-aws-dms)
7. [Amazon EMR](#7-amazon-emr)
8. [Amazon Redshift](#8-amazon-redshift)
9. [AWS Step Functions for Data](#9-aws-step-functions-for-data)
10. [Cost Optimization Framework](#10-cost-optimization-framework)
11. [Decision Frameworks](#11-decision-frameworks)

---

## 1. Amazon Kinesis

### Architecture: Data Streams

```
┌────────────────────────────────────────────────────────────────────┐
│                    Amazon Kinesis Data Streams                       │
│                                                                      │
│  Producers                   Shards                  Consumers       │
│  ┌──────┐                 ┌─────────┐             ┌──────────┐     │
│  │App 1 │───┐             │ Shard 1 │────────────▶│Consumer 1│     │
│  └──────┘   │  Partition  ├─────────┤  Standard:  ├──────────┤     │
│  ┌──────┐   ├───Key───▶   │ Shard 2 │  2MB/s     │Consumer 2│     │
│  │App 2 │───┤  Hashing    ├─────────┤  shared    ├──────────┤     │
│  └──────┘   │             │ Shard 3 │            │Consumer 3│     │
│  ┌──────┐   │             ├─────────┤  Enhanced:  └──────────┘     │
│  │Agent │───┘             │ Shard N │  2MB/s per                    │
│  └──────┘                 └─────────┘  consumer                     │
│                                                                      │
│  Write: 1MB/s or 1000 records/s per shard                           │
│  Read:  2MB/s per shard (shared) or per consumer (enhanced fan-out) │
└────────────────────────────────────────────────────────────────────┘
```

### Kinesis Data Streams - Key Concepts

| Concept | Details |
|---------|---------|
| Shard | Base unit of throughput (1MB/s in, 2MB/s out) |
| Partition Key | Determines shard placement (MD5 hash) |
| Sequence Number | Unique per-record ID within shard (monotonically increasing) |
| Retention | 24h default, up to 365 days |
| On-Demand | Auto-scales shards (4MB/s write default, up to 200MB/s) |
| Provisioned | Fixed shard count, manual scaling |

### KCL (Kinesis Client Library) Internals

```python
# KCL 2.x uses lease table in DynamoDB for coordination
# Table name: <application_name>
# Key: leaseKey (shard-id)
# Attributes: checkpoint, leaseOwner, leaseCounter, parentShardIds

# DynamoDB Lease Table Schema:
# ┌─────────────┬────────────────┬───────────────┬──────────────┐
# │ leaseKey    │ checkpoint     │ leaseOwner    │ leaseCounter │
# ├─────────────┼────────────────┼───────────────┼──────────────┤
# │ shardId-001 │ 4958723...     │ worker-1      │ 42           │
# │ shardId-002 │ 4958724...     │ worker-2      │ 38           │
# │ shardId-003 │ 4958725...     │ worker-1      │ 45           │
# └─────────────┴────────────────┴───────────────┴──────────────┘

# KCL Worker Coordination:
# 1. Workers compete for leases (heartbeat via leaseCounter increment)
# 2. If worker dies, lease expires → another worker takes over
# 3. Checkpoint stored in DynamoDB → exactly-once processing possible
# 4. Shard splitting/merging → new leases created, old ones closed

import boto3
from amazon_kclpy import kcl

class RecordProcessor:
    def initialize(self, initialize_input):
        self.shard_id = initialize_input.shard_id
        self.largest_seq = None
    
    def process_records(self, process_records_input):
        for record in process_records_input.records:
            data = record.data.decode('utf-8')
            self.process_record(data)
            self.largest_seq = record.sequence_number
        
        # Checkpoint after batch (stores in DynamoDB)
        if self.largest_seq:
            process_records_input.checkpointer.checkpoint(self.largest_seq)
    
    def shutdown(self, shutdown_input):
        if shutdown_input.reason == 'TERMINATE':
            shutdown_input.checkpointer.checkpoint()
```

### Enhanced Fan-Out

```python
# Standard: 2MB/s shared across ALL consumers on a shard
# Enhanced Fan-Out: 2MB/s DEDICATED per consumer (push model via HTTP/2)

import boto3
kinesis = boto3.client('kinesis')

# Register consumer for enhanced fan-out
response = kinesis.register_stream_consumer(
    StreamARN='arn:aws:kinesis:us-east-1:123456789:stream/orders',
    ConsumerName='analytics-consumer'
)
consumer_arn = response['Consumer']['ConsumerARN']

# Subscribe to shard (push-based, no polling)
response = kinesis.subscribe_to_shard(
    ConsumerARN=consumer_arn,
    ShardId='shardId-000000000001',
    StartingPosition={'Type': 'LATEST'}
)

# Events pushed via HTTP/2 stream
for event in response['EventStream']:
    if 'SubscribeToShardEvent' in event:
        records = event['SubscribeToShardEvent']['Records']
        for record in records:
            process(record)
```

### Kinesis Data Firehose

```
┌────────────┐    ┌─────────────────────────────────────────┐    ┌─────────┐
│  Sources   │───▶│           Firehose Delivery Stream       │───▶│ Targets │
│            │    │                                           │    │         │
│ • Kinesis  │    │  ┌────────┐  ┌──────────┐  ┌────────┐  │    │ • S3    │
│ • Direct   │    │  │ Buffer │→ │ Lambda   │→ │ Format │  │    │ •Redshift│
│   PUT      │    │  │(size/  │  │Transform │  │Convert │  │    │ • ES    │
│ • MSK      │    │  │ time)  │  │(optional)│  │(opt.)  │  │    │ • HTTP  │
│ • CloudWatch│   │  └────────┘  └──────────┘  └────────┘  │    │ •Splunk │
└────────────┘    └─────────────────────────────────────────┘    └─────────┘
```

### Dynamic Partitioning (S3 Target)

```python
# Firehose can partition S3 output by record content
# Example: partition by customer_id and event_type from JSON records

# Source record: {"customer_id": "c123", "event_type": "purchase", "amount": 99.99}
# S3 output: s3://bucket/customer_id=c123/event_type=purchase/2024/01/15/file.parquet

# Configuration via boto3:
firehose = boto3.client('firehose')
firehose.create_delivery_stream(
    DeliveryStreamName='events-to-s3',
    ExtendedS3DestinationConfiguration={
        'BucketARN': 'arn:aws:s3:::data-lake-raw',
        'Prefix': 'events/customer_id=!{partitionKeyFromQuery:customer_id}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/',
        'ErrorOutputPrefix': 'errors/',
        'BufferingHints': {
            'SizeInMBs': 128,      # Buffer size (1-128 MB)
            'IntervalInSeconds': 60  # Buffer time (60-900s)
        },
        'CompressionFormat': 'UNCOMPRESSED',  # For Parquet, compression is in format
        'DataFormatConversionConfiguration': {
            'Enabled': True,
            'InputFormatConfiguration': {
                'Deserializer': {'OpenXJsonSerDe': {}}
            },
            'OutputFormatConfiguration': {
                'Serializer': {
                    'ParquetSerDe': {
                        'Compression': 'SNAPPY',
                        'EnableDictionaryCompression': True
                    }
                }
            },
            'SchemaConfiguration': {
                'DatabaseName': 'events_db',
                'TableName': 'events',
                'Region': 'us-east-1',
                'RoleARN': 'arn:aws:iam::123:role/firehose-glue'
            }
        },
        'DynamicPartitioningConfiguration': {
            'Enabled': True,
            'RetryOptions': {'DurationInSeconds': 300}
        },
        'ProcessingConfiguration': {
            'Enabled': True,
            'Processors': [{
                'Type': 'MetadataExtraction',
                'Parameters': [{
                    'ParameterName': 'MetadataExtractionQuery',
                    'ParameterValue': '{customer_id:.customer_id}'
                }, {
                    'ParameterName': 'JsonParsingEngine',
                    'ParameterValue': 'JQ-1.6'
                }]
            }]
        }
    }
)
```

### Kinesis vs MSK Decision

| Dimension | Kinesis Data Streams | Amazon MSK |
|-----------|---------------------|------------|
| Pricing model | Per-shard-hour + PUT payload units | Per-broker-hour + storage |
| Scaling | Shard split/merge (minutes) or On-Demand | Add brokers (hours) |
| Throughput/unit | 1MB/s in, 2MB/s out per shard | Depends on instance (m5.large: ~30MB/s) |
| Retention | 24h-365d | Unlimited (with tiered storage) |
| Consumers | KCL, Lambda, Firehose, EFO | Any Kafka client, MSK Connect |
| Ordering | Per-shard | Per-partition |
| Replay | Iterator types (TRIM_HORIZON, AT_TIMESTAMP) | Consumer offset reset |
| Ecosystem | AWS-native only | Full Kafka ecosystem |
| Ops | Zero (serverless-like) | Broker management (even if managed) |
| Cost at 1GB/s | ~$50K/month (On-Demand) | ~$15K/month (m5.4xlarge × 6) |
| Best for | Serverless/Lambda, small-medium scale | Kafka ecosystem, large scale, many consumers |

---

## 2. Amazon MSK

### Provisioned vs Serverless

| Dimension | MSK Provisioned | MSK Serverless |
|-----------|----------------|----------------|
| Broker management | Choose instance type, count | Fully auto-scaled |
| Storage | EBS (auto-expand possible) | Included, auto-scaled |
| Max throughput | Instance-dependent | Up to 200MB/s per cluster |
| Networking | Customer VPC, multi-AZ | Customer VPC |
| Auth | IAM, SASL/SCRAM, mTLS, unauthenticated | IAM only |
| Pricing | Per-broker-hour + storage | Per-cluster-hour + data in/out + storage |
| Configuration | Full Kafka config control | Limited (~30 configs) |
| Kafka Connect | MSK Connect (managed) | MSK Connect |
| Best for | Production at scale, full control | Dev/test, variable workloads, simplicity |

### MSK Tiered Storage

```
┌──────────────────────────────────────────────────────┐
│                MSK Tiered Storage                      │
│                                                        │
│  Hot Data (Local EBS)          Cold Data (S3)         │
│  ┌─────────────────────┐     ┌────────────────────┐  │
│  │ Recent segments      │     │ Older segments     │  │
│  │ (hours-days)         │────▶│ (days-years)       │  │
│  │ Fast reads           │     │ Slower first-byte  │  │
│  │ $0.10/GB-month (gp3) │     │ $0.023/GB-month    │  │
│  └─────────────────────┘     └────────────────────┘  │
│                                                        │
│  Config:                                               │
│    log.retention.hours = 8760  (1 year total)         │
│    remote.storage.enable = true                        │
│    local.retention.hours = 48   (2 days hot)          │
│                                                        │
│  Cost savings: 80%+ for long-retention topics         │
└──────────────────────────────────────────────────────┘
```

### MSK Production Configuration

```hcl
# Terraform
resource "aws_msk_cluster" "production" {
  cluster_name           = "data-platform-prod"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 6  # 2 per AZ × 3 AZs

  broker_node_group_info {
    instance_type   = "kafka.m5.4xlarge"  # 16 vCPU, 64GB RAM
    client_subnets  = var.private_subnet_ids
    security_groups = [aws_security_group.msk.id]
    storage_info {
      ebs_storage_info {
        volume_size = 2000  # 2TB per broker
        provisioned_throughput {
          enabled           = true
          volume_throughput  = 250  # MB/s
        }
      }
    }
  }

  # Enable tiered storage
  storage_mode = "TIERED"
}
```

---

## 3. AWS Glue

### Glue Jobs Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      AWS Glue Job Execution                        │
│                                                                    │
│  ┌──────────────┐                                                 │
│  │ Glue Service │                                                 │
│  │  • Job mgmt  │                                                 │
│  │  • Scheduling│                                                 │
│  │  • Bookmarks │                                                 │
│  └──────┬───────┘                                                 │
│         │ Launches                                                 │
│         ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │           Spark Environment (per Job Run)                  │    │
│  │                                                            │    │
│  │  ┌────────┐     ┌────────────────────────────────────┐   │    │
│  │  │ Driver │     │          Worker Fleet               │   │    │
│  │  │        │     │  ┌────────┐ ┌────────┐ ┌────────┐  │   │    │
│  │  │  • DAG │────▶│  │Worker 1│ │Worker 2│ │Worker N│  │   │    │
│  │  │  • Book│     │  │(Exec.) │ │(Exec.) │ │(Exec.) │  │   │    │
│  │  │  • Coord│    │  └────────┘ └────────┘ └────────┘  │   │    │
│  │  └────────┘     └────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Worker Types Deep Dive

| Worker Type | vCPU | Memory | Disk | GPU | Cost/DPU-hour | Best For |
|-------------|------|--------|------|-----|---------------|----------|
| **G.1X** | 4 | 16 GB | 64 GB | No | $0.44 | Light transforms, small data |
| **G.2X** | 8 | 32 GB | 128 GB | No | $0.88 | Standard ETL, joins, aggregations |
| **G.4X** | 16 | 64 GB | 256 GB | No | $1.76 | Memory-intensive (large shuffles) |
| **G.8X** | 32 | 128 GB | 512 GB | No | $3.52 | Very large datasets, complex ML |
| **Z.2X** | 8 | 64 GB | 128 GB | Yes | $1.32 | ML inference, GPU-accelerated |

**Selection Guide:**
```
Data size < 50GB → G.1X (2-10 workers)
Data size 50-500GB → G.2X (5-20 workers)
Data size 500GB-5TB, complex joins → G.4X (10-50 workers)
Data size > 5TB, heavy shuffle → G.8X (20-100 workers)
ML workloads → Z.2X
```

### DynamicFrame vs DataFrame

```python
# DynamicFrame: Glue-specific, handles schema inconsistencies
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame

glueContext = GlueContext(SparkContext.getOrCreate())

# DynamicFrame: self-describing (each record can have different schema)
dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
    database="raw_db",
    table_name="orders",
    transformation_ctx="orders_source",  # Required for bookmarks!
    push_down_predicate="partition_date >= '2024-01-01'"  # Partition pruning
)

# Handle schema inconsistencies (e.g., "price" is sometimes string, sometimes double)
resolved = dynamic_frame.resolveChoice(
    choice="cast:double",  # Cast all ambiguous to double
    specs=[("price", "cast:double"), ("quantity", "cast:int")]
)

# Flatten nested structures
flattened = dynamic_frame.relationalize(
    root_table_name="orders",
    staging_path="s3://temp-bucket/relationalize/"
)

# Convert to DataFrame for complex operations
df = dynamic_frame.toDF()

# DataFrame advantages:
# ✅ Full Spark SQL API
# ✅ Better performance for known schemas
# ✅ Catalyst optimizer
# ✅ Native Iceberg/Delta support

# Convert back to DynamicFrame (for Glue-specific sinks)
output_dynamic_frame = DynamicFrame.fromDF(df, glueContext, "output")

# When to use which:
# DynamicFrame: Unknown/inconsistent schemas, Glue Catalog source/sink, bookmarks
# DataFrame: Known schema, complex transforms, Iceberg/Delta, performance-critical
```

### Job Bookmarks Deep Dive

```python
# Job Bookmarks track what's been processed (incremental processing)
# Works by tracking: 
#   - For JDBC: primary key range or timestamp column
#   - For S3: file modification timestamps + paths
#   - For Catalog: partition values

# How bookmarks work internally:
# 1. On first run: process ALL data, save bookmark state
# 2. On subsequent runs: only process NEW data since last bookmark
# 3. Bookmark state stored in Glue service (per job + per transformation_ctx)

# CRITICAL: transformation_ctx MUST be unique per source in the job
# If missing → bookmarks don't work → full reprocessing every run

from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME'])
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# S3 source with bookmarks
source = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    format="parquet",
    connection_options={
        "paths": ["s3://data-lake/raw/orders/"],
        "recurse": True,
        # Bookmark options for S3:
        "jobBookmarkKeys": ["partition_date"],  # Custom bookmark key
        "jobBookmarkKeysSortOrder": "asc"
    },
    transformation_ctx="s3_orders_source"  # REQUIRED for bookmarks
)

# JDBC source with bookmarks
jdbc_source = glueContext.create_dynamic_frame.from_catalog(
    database="source_db",
    table_name="orders",
    transformation_ctx="jdbc_orders_source",  # REQUIRED
    additional_options={
        "jobBookmarkKeys": ["updated_at"],  # Column to track
        "jobBookmarkKeysSortOrder": "asc"
    }
)

# ... transforms ...

# Commit bookmark (marks current data as processed)
job.commit()

# Bookmark Gotchas:
# 1. If job fails before job.commit() → data reprocessed next run (at-least-once)
# 2. transformation_ctx MUST be set on EVERY source/sink that needs tracking
# 3. S3 bookmarks track by file modification time (not content)
# 4. Bookmark reset: aws glue reset-job-bookmark --job-name my-job
```

### Auto-Scaling and Flex Execution

```python
# Auto-scaling: dynamically adjusts workers based on workload
# Config in job creation:
# --enable-auto-scaling true
# NumberOfWorkers = MAX workers (auto-scale down from this)

# Flex execution: uses Spot instances (70% cheaper)
# Limitations:
#   - Jobs may take longer to start (waiting for spot capacity)
#   - Workers can be reclaimed (Glue handles restart transparently)
#   - Not suitable for time-sensitive jobs (SLA-bound)
#   - Not available for streaming jobs

# Terraform
resource "aws_glue_job" "flex_job" {
  name         = "batch-etl-flex"
  role_arn     = aws_iam_role.glue.arn
  glue_version = "4.0"
  
  # Standard execution (for SLA-bound jobs):
  # execution_class = "STANDARD"
  
  # Flex execution (for cost-optimized batch):
  execution_class   = "FLEX"
  worker_type       = "G.2X"
  number_of_workers = 20
  
  default_arguments = {
    "--enable-auto-scaling" = "true"  # Scale within 2-20 workers
  }
}
```

### Glue Streaming Jobs

```python
# Glue Streaming = Spark Structured Streaming (micro-batch)
from awsglue.context import GlueContext
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window
from pyspark.sql.types import StructType, StringType, DoubleType, TimestampType

spark = SparkSession.builder.getOrCreate()
glueContext = GlueContext(spark.sparkContext)

# Read from Kinesis
kinesis_options = {
    "streamARN": "arn:aws:kinesis:us-east-1:123:stream/orders",
    "startingPosition": "TRIM_HORIZON",
    "classification": "json",
    "inferSchema": "true"
}

# Or read from Kafka/MSK
kafka_options = {
    "connectionName": "msk-connection",
    "topicName": "orders",
    "startingOffsets": "latest",
    "classification": "json",
    "inferSchema": "true"
}

data_frame_datasource = glueContext.create_data_frame.from_options(
    connection_type="kinesis",
    connection_options=kinesis_options
)

schema = StructType() \
    .add("order_id", StringType()) \
    .add("amount", DoubleType()) \
    .add("event_time", TimestampType())

# Process stream
parsed = data_frame_datasource \
    .select(from_json(col("data"), schema).alias("parsed")) \
    .select("parsed.*")

# Windowed aggregation
windowed = parsed \
    .withWatermark("event_time", "10 minutes") \
    .groupBy(window("event_time", "5 minutes")) \
    .agg({"amount": "sum", "order_id": "count"})

# Write to S3 (with checkpointing)
glueContext.forEachBatch(
    frame=windowed,
    batch_function=lambda df, epoch_id: df.write.mode("append").parquet(
        f"s3://data-lake/streaming/orders/"),
    options={
        "windowSize": "60 seconds",
        "checkpointLocation": "s3://checkpoints/streaming-orders/"
    }
)
```

### Glue Crawlers - When NOT to Use

```
USE Crawlers when:
  ✅ Exploring unknown data for the first time
  ✅ Schema is simple and well-structured (CSV, JSON, Parquet)
  ✅ Partitions follow standard Hive-style (dt=2024-01-15/)

DO NOT USE Crawlers when:
  ❌ Schema is well-known → register manually (faster, more accurate)
  ❌ Complex/nested structures → custom classifier rarely works well
  ❌ Many small files → crawler is very slow
  ❌ Frequent schema changes → crawler may create wrong versions
  ❌ Iceberg/Delta tables → use native catalog integration instead
  ❌ Production pipelines → crawlers add latency and unpredictability

Common Gotchas:
  1. Crawler infers STRING for everything ambiguous (numeric strings)
  2. Creates too many partition columns from path segments
  3. Merges incompatible schemas (breaking downstream)
  4. Slow on S3 with millions of objects (hours to crawl)
  5. Can't handle schema evolution well (creates new tables)

Alternative: Register schema manually via Terraform/boto3:
```

```python
# Manual table registration (preferred for production)
glue = boto3.client('glue')
glue.create_table(
    DatabaseName='raw_db',
    TableInput={
        'Name': 'orders',
        'StorageDescriptor': {
            'Columns': [
                {'Name': 'order_id', 'Type': 'bigint'},
                {'Name': 'customer_id', 'Type': 'string'},
                {'Name': 'amount', 'Type': 'decimal(10,2)'},
                {'Name': 'status', 'Type': 'string'},
                {'Name': 'created_at', 'Type': 'timestamp'},
            ],
            'Location': 's3://data-lake/raw/orders/',
            'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
            'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
            'SerdeInfo': {
                'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
            }
        },
        'PartitionKeys': [
            {'Name': 'dt', 'Type': 'string'}
        ],
        'TableType': 'EXTERNAL_TABLE',
        'Parameters': {
            'classification': 'parquet',
            'compressionType': 'snappy'
        }
    }
)
```

### Glue Data Quality (DQDL)

```python
# DQDL (Data Quality Definition Language)
# Rules in Glue Studio or programmatic

dqdl_rules = """
Rules = [
    # Completeness
    Completeness "order_id" = 1.0,
    Completeness "amount" >= 0.99,
    
    # Uniqueness
    IsUnique "order_id",
    
    # Freshness
    Freshness "created_at" <= 24 hours,
    
    # Value ranges
    ColumnValues "amount" between 0 and 100000,
    ColumnValues "status" in ["pending", "shipped", "delivered", "cancelled"],
    
    # Row count
    RowCount >= 1000,
    RowCount <= 10000000,
    
    # Custom SQL
    CustomSql "SELECT COUNT(*) FROM primary WHERE amount < 0" = 0,
    
    # Statistical
    StandardDeviation "amount" <= 500,
    Mean "amount" between 10 and 1000,
    
    # Schema
    ColumnExists "order_id",
    ColumnDataType "amount" = "DECIMAL"
]
"""

# In Glue job:
from awsglue.transforms import EvaluateDataQuality

result = EvaluateDataQuality.apply(
    frame=dynamic_frame,
    ruleset=dqdl_rules,
    publishing_options={
        "dataQualityEvaluationContext": "orders_quality",
        "enableDataQualityCloudWatchMetrics": True,
        "enableDataQualityResultsPublishing": True
    }
)

# Route good/bad records
good_records = result.filter(lambda r: r["dataQualityEvaluationResult"] == "Pass")
bad_records = result.filter(lambda r: r["dataQualityEvaluationResult"] == "Fail")
```

### DQDL vs Great Expectations vs Soda

| Dimension | DQDL (Glue) | Great Expectations | Soda Core |
|-----------|-------------|-------------------|-----------|
| Integration | Native Glue | Spark/Pandas/SQL | Any SQL + Spark |
| Config format | DQDL (custom DSL) | Python/YAML | SodaCL (YAML) |
| Anomaly detection | Basic | Custom expectations | Built-in ML |
| Cloud lock-in | AWS only | None | None |
| Cost | Included in Glue | Free (OSS) | Free (OSS) / Cloud paid |
| Visualization | Glue Console | Data Docs (HTML) | Soda Cloud |
| CI/CD integration | Limited | Good | Excellent |
| Best for | All-Glue pipelines | Spark-heavy, Python teams | SQL-first, simple setup |

---

## 4. Amazon Athena

### Query Optimization

```sql
-- 1. Partition pruning (most impactful)
-- BAD: scans all data ($$$)
SELECT * FROM orders WHERE created_at >= '2024-01-01';

-- GOOD: uses partition key (scans only relevant partitions)
SELECT * FROM orders WHERE dt >= '2024-01-01' AND dt < '2024-02-01';

-- 2. Columnar format + compression
-- Parquet/ORC with Snappy: 3-10x less data scanned vs CSV/JSON

-- 3. CTAS for optimized tables
CREATE TABLE optimized_orders
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['dt'],
    bucketed_by = ARRAY['customer_id'],
    bucket_count = 32,
    external_location = 's3://lake/optimized/orders/'
)
AS SELECT * FROM raw_orders;

-- 4. Iceberg tables (Athena v3)
CREATE TABLE iceberg_orders (
    order_id BIGINT,
    customer_id STRING,
    amount DECIMAL(10,2),
    status STRING,
    created_at TIMESTAMP
)
PARTITIONED BY (month(created_at))
LOCATION 's3://lake/iceberg/orders/'
TBLPROPERTIES ('table_type' = 'ICEBERG');

-- Time travel
SELECT * FROM iceberg_orders FOR TIMESTAMP AS OF TIMESTAMP '2024-01-15 00:00:00';

-- MERGE (upsert)
MERGE INTO iceberg_orders t
USING staging_orders s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET status = s.status, amount = s.amount
WHEN NOT MATCHED THEN INSERT (order_id, customer_id, amount, status, created_at)
  VALUES (s.order_id, s.customer_id, s.amount, s.status, s.created_at);

-- 5. Workgroups for cost control
-- Each workgroup can have: per-query limit, per-workgroup limit
-- Example: analyst workgroup limited to $100/day
```

### Athena Cost Model

```
Pricing: $5.00 per TB of data scanned

Optimization math:
  Raw JSON (1TB) → $5.00/query
  Parquet (1TB → 100GB compressed) → $0.50/query  (10x savings)
  Parquet + partition pruning (scan 10GB) → $0.05/query (100x savings)
  
Cancelled queries: charged for data scanned before cancellation
DDL queries: free
Failed queries: NOT charged
```

---

## 5. AWS Lake Formation

### Fine-Grained Access Model

```
┌────────────────────────────────────────────────────────────────┐
│               Lake Formation Permission Hierarchy               │
│                                                                  │
│  Database Level:                                                │
│    GRANT SELECT ON DATABASE silver TO analyst_role              │
│                                                                  │
│  Table Level:                                                   │
│    GRANT SELECT ON TABLE silver.orders TO analyst_role          │
│                                                                  │
│  Column Level:                                                  │
│    GRANT SELECT (order_id, amount, status) ON silver.orders    │
│    -- Excludes: customer_email, phone (PII columns)            │
│                                                                  │
│  Row Level (Data Filters):                                     │
│    CREATE DATA FILTER us_only_filter                            │
│    ON silver.orders                                             │
│    COLUMNS (order_id, amount, region)                          │
│    ROW FILTER (region = 'US')                                  │
│                                                                  │
│  Cell Level (Column + Row combined):                           │
│    Shows only US rows AND only non-PII columns                 │
└────────────────────────────────────────────────────────────────┘
```

### LF-Tags (Attribute-Based Access Control)

```
Instead of granting per-table/per-column (N×M matrix):
  Use tags: Classification={public,internal,confidential,restricted}
            Domain={orders,payments,customers}

Example:
  Tag tables/columns with classification
  Grant: "Analysts can access classification=[public,internal]"
  
  New table tagged "public" → analysts automatically get access
  No per-table grants needed → scales to 1000s of tables
```

---

## 6. AWS DMS

(Covered in detail in file 11-Data-Integration-CDC-Tools.md)

Key additions for AWS context:
```python
# DMS Serverless - auto-scaling CDC
dms = boto3.client('dms')
response = dms.create_replication_config(
    ReplicationConfigIdentifier='cdc-serverless',
    SourceEndpointArn='arn:aws:dms:...:endpoint:source',
    TargetEndpointArn='arn:aws:dms:...:endpoint:target',
    ReplicationType='cdc',
    ComputeConfig={
        'MinCapacityUnits': 1,    # Min 1 DCU
        'MaxCapacityUnits': 128,  # Max 128 DCU
        'MultiAZ': True,
        'VpcSecurityGroupIds': ['sg-xxx'],
        'ReplicationSubnetGroupId': 'subnet-group'
    },
    TableMappings='{"rules":[{"rule-type":"selection","rule-id":"1","rule-name":"include-all","object-locator":{"schema-name":"%","table-name":"%"},"rule-action":"include"}]}'
)
```

---

## 7. Amazon EMR

### EMR on EC2 vs EKS vs Serverless

| Dimension | EMR on EC2 | EMR on EKS | EMR Serverless |
|-----------|-----------|------------|----------------|
| Infrastructure | EC2 instances (you manage cluster) | EKS pods (shared K8s) | No infrastructure |
| Scaling | Auto-scaling groups (minutes) | Pod scaling (seconds) | Automatic (seconds) |
| Multi-tenancy | 1 cluster per workload (or YARN queues) | Shared EKS cluster | Isolated per application |
| Cost control | Instance fleets + Spot | Pod resource requests | Pay per vCPU-hour + memory-hour |
| Startup time | 5-15 minutes | Seconds (if EKS warm) | Seconds (pre-initialized) |
| Customization | Full (bootstrap, AMI) | Container image | Pre-built runtime |
| Long-running | Yes (persistent clusters) | Yes | No (job-based) |
| Best for | Legacy, Hadoop ecosystem | K8s-native orgs, multi-engine | Serverless Spark, cost optimization |
| Spot savings | 60-90% (task nodes) | K8s spot nodes | Built-in |

### EMR vs Glue Decision Framework

| Dimension | EMR | Glue |
|-----------|-----|------|
| Engine | Spark, Hive, Presto, Flink, HBase | Spark (+ Python Shell, Ray) |
| Control | Full (any Spark config, custom JARs) | Limited (Glue APIs, some configs) |
| Startup | 5-15 min (EC2) / seconds (EKS, Serverless) | 1-3 min (cold) |
| Cost (100TB) | Lower (~40% less at scale) | Higher (DPU pricing premium) |
| Cost (10GB) | Higher (min cluster cost) | Lower (min 2 DPU × time) |
| Bookmarks | Manual (checkpointing) | Built-in (job bookmarks) |
| Catalog | Glue Catalog / Hive Metastore | Glue Catalog (native) |
| Streaming | Spark SS, Flink (first-class) | Spark SS (limited) |
| Iceberg | Full support (custom JARs) | Supported (Glue 4.0) |
| Operations | More ops (even if managed) | Zero ops (serverless) |
| Best for | Large scale, multi-engine, custom | Simple ETL, small-medium, no-ops |

### EMR Serverless Example

```python
import boto3

emr_serverless = boto3.client('emr-serverless')

# Create application (reusable)
app = emr_serverless.create_application(
    name='spark-etl',
    releaseLabel='emr-6.15.0',
    type='SPARK',
    autoStartConfiguration={'enabled': True},
    autoStopConfiguration={'enabled': True, 'idleTimeoutMinutes': 5},
    maximumCapacity={
        'cpu': '400 vCPU',
        'memory': '3000 GB',
        'disk': '20000 GB'
    },
    # Pre-initialized capacity (warm start)
    initialCapacity={
        'DRIVER': {
            'workerCount': 2,
            'workerConfiguration': {'cpu': '4 vCPU', 'memory': '16 GB'}
        },
        'EXECUTOR': {
            'workerCount': 10,
            'workerConfiguration': {'cpu': '4 vCPU', 'memory': '32 GB'}
        }
    }
)

# Submit job
job = emr_serverless.start_job_run(
    applicationId=app['applicationId'],
    executionRoleArn='arn:aws:iam::123:role/emr-serverless-role',
    jobDriver={
        'sparkSubmit': {
            'entryPoint': 's3://scripts/daily-etl.py',
            'entryPointArguments': ['--date', '2024-01-15'],
            'sparkSubmitParameters': (
                '--conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions '
                '--conf spark.executor.memory=16g '
                '--conf spark.executor.cores=4 '
                '--conf spark.dynamicAllocation.enabled=true '
                '--conf spark.dynamicAllocation.maxExecutors=50'
            )
        }
    },
    configurationOverrides={
        'monitoringConfiguration': {
            's3MonitoringConfiguration': {
                'logUri': 's3://emr-logs/serverless/'
            }
        }
    }
)
```

---

## 8. Amazon Redshift

### Distribution and Sort Keys

```sql
-- Distribution styles determine how data is spread across slices

-- KEY: rows with same key value → same slice (good for joins)
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    amount DECIMAL(10,2),
    order_date DATE
)
DISTSTYLE KEY
DISTKEY (customer_id)  -- Co-locate with customers table
SORTKEY (order_date);  -- Range-restricted scans on date

-- EVEN: round-robin (when no obvious join key)
-- ALL: full copy on every slice (small dimension tables)
-- AUTO: Redshift decides (default, recommended for most)

-- Sort key types:
-- COMPOUND: multi-column, left-to-right prefix
-- INTERLEAVED: equal weight per column (slower VACUUM)

-- Redshift Serverless (recommended for new workloads):
-- No cluster management, auto-scales, pay per RPU-hour
-- 1 RPU = ~$0.375/hour (billed per second)
```

### Redshift Spectrum

```sql
-- Query S3 data directly without loading into Redshift
-- Uses Glue Data Catalog for schema

CREATE EXTERNAL SCHEMA lake_schema
FROM DATA CATALOG
DATABASE 'silver'
IAM_ROLE 'arn:aws:iam::123:role/redshift-spectrum-role'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

-- Join Redshift local table with S3 external table
SELECT 
    r.customer_name,
    SUM(s.amount) as total_spend
FROM redshift_schema.customers r
JOIN lake_schema.orders s ON r.customer_id = s.customer_id
WHERE s.dt >= '2024-01-01'
GROUP BY 1;

-- Cost: $5/TB scanned (same as Athena) + Redshift compute
```

---

## 9. AWS Step Functions for Data

### Distributed Map for Batch Processing

```json
{
  "Comment": "Process 500K S3 files in parallel",
  "StartAt": "BatchProcess",
  "States": {
    "BatchProcess": {
      "Type": "Map",
      "ItemProcessor": {
        "ProcessorConfig": {
          "Mode": "DISTRIBUTED",
          "ExecutionType": "STANDARD"
        },
        "StartAt": "ProcessFile",
        "States": {
          "ProcessFile": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName": "process-file",
              "Payload.$": "$"
            },
            "Retry": [{"ErrorEquals": ["States.ALL"], "MaxAttempts": 3}],
            "End": true
          }
        }
      },
      "ItemReader": {
        "Resource": "arn:aws:states:::s3:listObjectsV2",
        "Parameters": {
          "Bucket": "data-lake",
          "Prefix": "raw/2024-01-15/"
        }
      },
      "MaxConcurrency": 10000,
      "ToleratedFailurePercentage": 1,
      "End": true
    }
  }
}
```

---

## 10. Cost Optimization Framework

### Per-Service Monthly Cost (100TB/day ingest)

| Service | Configuration | Monthly Cost |
|---------|--------------|-------------|
| MSK | 6× kafka.m5.4xlarge, 2TB/broker | ~$15,000 |
| Glue | 100 job-hours/day × G.2X × 10 workers | ~$26,000 |
| EMR Serverless | 500 vCPU-hours/day | ~$8,000 |
| S3 | 500TB storage + requests | ~$12,000 |
| Athena | 50TB scanned/month | ~$250 |
| Redshift Serverless | 1000 RPU-hours/month | ~$375 |
| Kinesis | 100 shards On-Demand | ~$10,000 |
| DMS | dms.r5.2xlarge Multi-AZ | ~$3,000 |
| **Total** | | **~$75,000/month** |

### Optimization Levers

```
1. Compute (40% of cost):
   - Glue Flex execution: -70% (where SLA allows)
   - EMR Spot instances: -60-90% (task nodes)
   - Right-size workers: monitor DPU utilization, reduce if < 50%
   - Auto-scaling: scale down during off-hours

2. Storage (25% of cost):
   - S3 Intelligent-Tiering: automatic tier optimization
   - Lifecycle policies: Standard (30d) → IA (90d) → Glacier (365d)
   - Iceberg expire_snapshots: delete old data files
   - Parquet compression: Zstd > Snappy (30% smaller, similar speed)

3. Data Transfer (15% of cost):
   - VPC endpoints: avoid NAT Gateway charges for S3
   - Same-region processing: avoid cross-region transfer ($0.02/GB)
   - Compression before transfer

4. Query (10% of cost):
   - Partition pruning (Athena): 10-100x less scanned
   - Result caching (Redshift): repeat queries are free
   - Workgroup limits (Athena): prevent expensive queries
   - Materialized views: pre-compute expensive aggregations
```

---

## 11. Decision Frameworks

### EMR vs Glue

```
Use Glue when:
  ✅ Simple ETL (read → transform → write)
  ✅ Team wants zero infrastructure management
  ✅ Data < 500GB per job
  ✅ Standard transformations (no custom JARs/libraries)
  ✅ Job Bookmarks meet incremental needs
  ✅ Budget is flexible (DPU premium acceptable)

Use EMR when:
  ✅ Complex multi-engine workloads (Spark + Flink + Presto)
  ✅ Data > 500GB per job
  ✅ Need custom libraries, AMIs, or bootstrap scripts
  ✅ Long-running clusters (interactive notebooks, streaming)
  ✅ Cost-sensitive at scale (60%+ savings over Glue)
  ✅ Need fine-grained Spark tuning (AQE, shuffle configs)
  ✅ Streaming with Flink (Glue streaming is limited)
```

### Kinesis vs MSK

```
Use Kinesis when:
  ✅ Serverless/Lambda architecture
  ✅ < 50 shards (small-medium scale)
  ✅ Firehose integration (auto-delivery to S3/Redshift)
  ✅ Don't need Kafka ecosystem (Connect, Streams, KSQL)
  ✅ Minimal ops desired
  ✅ Enhanced fan-out for few high-throughput consumers

Use MSK when:
  ✅ Existing Kafka expertise/clients
  ✅ High throughput (> 100MB/s)
  ✅ Many consumers (consumer groups)
  ✅ Need Kafka Connect ecosystem
  ✅ Long retention (months/years with tiered storage)
  ✅ Cross-region replication (MirrorMaker 2 / MSK Replicator)
  ✅ Cost-sensitive at scale
```

### Athena vs Redshift vs EMR (Query Workloads)

| Dimension | Athena | Redshift | EMR (Presto/Trino) |
|-----------|--------|----------|---------------------|
| Best for | Ad-hoc queries, infrequent | Repeated dashboards, BI | Complex analytics, many users |
| Data location | S3 (external) | Local + Spectrum (S3) | S3 (external) |
| Concurrency | Low-medium (DML: 20/account) | High (concurrency scaling) | High (cluster-dependent) |
| Latency | Seconds-minutes | Sub-second (cached) | Seconds |
| Cost model | Per-TB scanned ($5/TB) | Per-RPU-hour or RI | Per-instance-hour |
| Cheap at | Small queries, infrequent | Heavy, repeated queries | Large-scale analytics |
| Expensive at | Full table scans, frequent | Idle time (provisioned) | Small queries |
