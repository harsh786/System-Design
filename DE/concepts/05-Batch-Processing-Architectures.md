# Batch Processing Architectures - Staff Architect Deep Dive

## Table of Contents
1. [Fundamentals](#1-fundamentals)
2. [MapReduce](#2-mapreduce)
3. [Apache Hive](#3-apache-hive)
4. [Presto/Trino](#4-prestotrino)
5. [dbt](#5-dbt-data-build-tool)
6. [Apache Beam](#6-apache-beam)
7. [File Formats Deep Dive](#7-file-formats-deep-dive)
8. [Compression](#8-compression)
9. [Partitioning Strategies](#9-partitioning-strategies)
10. [Small Files Problem](#10-small-files-problem)
11. [Data Quality](#11-data-quality)
12. [Cost Optimization](#12-cost-optimization)
13. [Orchestration Comparison](#13-orchestration-comparison)

---

## 1. Fundamentals

### Batch vs Stream Processing

```
┌──────────────────────────────────────────────────────────────┐
│                    PROCESSING SPECTRUM                        │
│                                                               │
│  BATCH              MICRO-BATCH          STREAM               │
│  ◄─────────────────────┼───────────────────────────────────►  │
│                         │                                     │
│  MapReduce             Spark Streaming    Flink               │
│  Spark (batch)         (100ms-minutes)    Kafka Streams       │
│  Hive                                    Storm                │
│  Presto/Trino                                                │
│                                                               │
│  Latency: minutes-hours  seconds-minutes  milliseconds-seconds│
│  Data: bounded           micro-bounded    unbounded           │
│  Completeness: complete  near-complete    approximate         │
│  Complexity: low         medium           high                │
└──────────────────────────────────────────────────────────────┘
```

### ETL vs ELT

```
ETL (Extract-Transform-Load):
┌────────┐    ┌─────────────┐    ┌────────────┐
│ Source  │──▶│  ETL Server  │──▶│ Data       │
│ Systems│    │  Transform   │    │ Warehouse  │
└────────┘    │  here        │    └────────────┘
              └─────────────┘
Use when: Legacy systems, sensitive data (transform before load)
Tools: Informatica, Talend, SSIS, DataStage

ELT (Extract-Load-Transform):
┌────────┐    ┌────────────┐    ┌─────────────────┐
│ Source  │──▶│ Data Lake / │──▶│ Transform in     │
│ Systems│    │ Warehouse   │    │ warehouse (SQL)  │
└────────┘    │ (raw zone)  │    │ dbt, Spark SQL   │
              └────────────┘    └─────────────────┘
Use when: Cloud-native, cheap storage, powerful compute
Tools: Fivetran+dbt, Airbyte+dbt, Spark, BigQuery
```

---

## 2. MapReduce

### Programming Model

```
Input Data → Split → Map → Shuffle & Sort → Reduce → Output

Example: Word Count

Input:     "hello world hello"    "world hello world"
           ┌───────────────┐      ┌───────────────┐
           │   InputSplit 0 │      │   InputSplit 1 │
           └───────┬───────┘      └───────┬───────┘
                   │                       │
            ┌──────▼──────┐        ┌──────▼──────┐
            │   Mapper 0   │        │   Mapper 1   │
            │              │        │              │
            │ hello → 1    │        │ world → 1    │
            │ world → 1    │        │ hello → 1    │
            │ hello → 1    │        │ world → 1    │
            └──────┬──────┘        └──────┬──────┘
                   │                       │
            ┌──────▼───────────────────────▼──────┐
            │         SHUFFLE & SORT               │
            │  Group by key, sort                  │
            │  hello: [1, 1, 1]                    │
            │  world: [1, 1, 1]                    │
            └──────────────┬──────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
       ┌──────────┐             ┌──────────┐
       │ Reducer 0 │             │ Reducer 1 │
       │           │             │           │
       │ hello → 3 │             │ world → 3 │
       └──────────┘             └──────────┘
```

### Combiners and Partitioners

```java
// Combiner: Local reduce BEFORE shuffle (reduces network I/O)
// Must be commutative and associative

// Without combiner:
//   Map output: hello:1, hello:1, hello:1 → shuffle ALL to reducer
//   Network: 3 records

// With combiner:
//   Map output: hello:1, hello:1, hello:1
//   Combiner:   hello:3                    → shuffle COMBINED to reducer
//   Network: 1 record

job.setCombinerClass(IntSumReducer.class);

// Partitioner: Decides which reducer gets which key
// Default: HashPartitioner → hash(key) % numReducers
// Custom: Route specific keys to specific reducers

public class GeoPartitioner extends Partitioner<Text, IntWritable> {
    @Override
    public int getPartition(Text key, IntWritable value, int numPartitions) {
        String region = key.toString().split(":")[0];
        if (region.equals("US")) return 0;
        if (region.equals("EU")) return 1;
        return 2;
    }
}
```

### Speculative Execution

```
Problem: One slow task (straggler) delays entire job
Solution: Launch duplicate of slow task on another node

Timeline:
Task A: ████████████████████████████████ (slow - disk issue)
Task B: ████████████ done
Task C: ██████████████ done

With speculation:
Task A:  ████████████████████████████████ (original - killed)
Task A': ██████████████ done (speculative copy - wins!)
Task B:  ████████████ done
Task C:  ██████████████ done

Config:
  mapreduce.map.speculative = true
  mapreduce.reduce.speculative = true
  mapreduce.job.speculative.slowtaskthreshold = 1.0  # Progress threshold

WARNING: Only safe with idempotent operations!
         Non-idempotent writes → duplicates
```

---

## 3. Apache Hive

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      APACHE HIVE                              │
│                                                               │
│  ┌────────────┐    ┌──────────────────────────────────┐      │
│  │ HiveServer2│    │          Metastore               │      │
│  │ (Thrift)   │    │   (MySQL / PostgreSQL / Derby)    │      │
│  │            │    │                                   │      │
│  │ JDBC/ODBC  │    │  - Table schemas                  │      │
│  │ Beeline    │───▶│  - Partition metadata              │      │
│  │ HUE        │    │  - Storage locations               │      │
│  └────────────┘    │  - SerDe information               │      │
│                    │  - Statistics                      │      │
│                    └──────────────────────────────────┘      │
│                                                               │
│  Execution Engines:                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐        │
│  │ MapReduce  │  │    Tez     │  │     Spark       │        │
│  │ (legacy)   │  │ (DAG-based)│  │ (in-memory)    │        │
│  └────────────┘  └────────────┘  └────────────────┘        │
│                                                               │
│  Storage: HDFS / S3 / ADLS / GCS                             │
│  Formats: ORC, Parquet, Avro, TextFile, SequenceFile         │
└──────────────────────────────────────────────────────────────┘
```

### Partitioning and Bucketing

```sql
-- PARTITIONING: Physical directory structure
-- Best for: High cardinality filtering columns (date, region)
CREATE TABLE orders (
    order_id BIGINT,
    customer_id STRING,
    amount DECIMAL(10,2),
    product_category STRING
)
PARTITIONED BY (order_date STRING, region STRING)
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZSTD');

-- Directory structure:
-- /warehouse/orders/order_date=2024-01-15/region=US/
-- /warehouse/orders/order_date=2024-01-15/region=EU/
-- /warehouse/orders/order_date=2024-01-16/region=US/

-- Dynamic partitioning
SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;

INSERT OVERWRITE TABLE orders PARTITION(order_date, region)
SELECT order_id, customer_id, amount, product_category, order_date, region
FROM staging_orders;

-- BUCKETING: Hash-distributed files within partition
-- Best for: Join optimization, sampling
CREATE TABLE orders_bucketed (
    order_id BIGINT,
    customer_id STRING,
    amount DECIMAL(10,2)
)
PARTITIONED BY (order_date STRING)
CLUSTERED BY (customer_id) SORTED BY (customer_id) INTO 32 BUCKETS
STORED AS ORC;

-- Benefits:
-- 1. Bucket map join (no shuffle if both tables bucketed by same key)
-- 2. Sampling: SELECT * FROM orders TABLESAMPLE(BUCKET 1 OUT OF 32)
-- 3. Sorted merge join (if sorted within buckets)
```

### ORC vs Parquet Comparison

```
┌────────────────────┬──────────────────┬──────────────────┐
│ Feature            │ ORC              │ Parquet           │
├────────────────────┼──────────────────┼──────────────────┤
│ Origin             │ Hive (Hortonworks)│ Twitter/Cloudera  │
│ Primary ecosystem  │ Hive, Presto     │ Spark, Impala     │
│ Compression        │ ZLIB, Snappy,    │ Snappy, GZIP,     │
│                    │ LZO, ZSTD        │ LZO, ZSTD         │
│ Default compress   │ ZLIB             │ Snappy             │
│ Encoding           │ RLE, Dictionary, │ RLE, Dictionary,   │
│                    │ Bit-packing      │ Delta, Bit-packing │
│ Nested types       │ Struct, List, Map│ Full (Dremel model)│
│ Index              │ Bloom filter,    │ Min/max stats      │
│                    │ Min/max, row idx │ Bloom filter (1.4+)│
│ ACID support       │ Yes (Hive 3.x)   │ No (Delta Lake)    │
│ Schema evolution   │ Add/remove cols  │ Add/remove cols    │
│ Predicate pushdown │ Stripe/row group │ Row group level    │
│ Best for           │ Hive workloads   │ Spark, cross-engine│
│ Compression ratio  │ Slightly better  │ Good               │
│ Read performance   │ Similar          │ Similar            │
└────────────────────┴──────────────────┴──────────────────┘

Recommendation: Use Parquet for new projects (broader ecosystem support)
                Use ORC for Hive-heavy environments
```

### Hive LLAP (Live Long And Process)

```
Traditional Hive: Job starts → JVM spins up → process → JVM dies
Problem: JVM startup overhead for interactive queries

LLAP: Long-running daemons with persistent cache

┌────────────────────────────────────────────┐
│              LLAP Architecture              │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │         LLAP Daemon (per node)        │  │
│  │                                       │  │
│  │  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │  Executors   │  │  In-Memory    │  │  │
│  │  │  (threads)   │  │  Cache        │  │  │
│  │  │              │  │  (off-heap)   │  │  │
│  │  │  Process     │  │              │  │  │
│  │  │  fragments   │  │  Columnar    │  │  │
│  │  │  of query    │  │  format      │  │  │
│  │  └─────────────┘  └───────────────┘  │  │
│  │                                       │  │
│  │  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │  I/O Layer   │  │  Security     │  │  │
│  │  │  (async,     │  │  (fine-grain  │  │  │
│  │  │   predicate  │  │   per-column) │  │  │
│  │  │   pushdown)  │  │              │  │  │
│  │  └─────────────┘  └───────────────┘  │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘

Benefits:
  - Sub-second query latency (cached data)
  - No JVM startup overhead
  - Intelligent caching (hot columns cached)
  - Fine-grained security (column-level)
```

---

## 4. Presto/Trino

### MPP Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     TRINO CLUSTER                             │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    COORDINATOR                        │    │
│  │                                                       │    │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │    │
│  │  │ Parser   │  │ Planner   │  │  Scheduler        │  │    │
│  │  │ (ANTLR)  │  │ (CBO)     │  │  (stage-based)    │  │    │
│  │  └──────────┘  └───────────┘  └──────────────────┘  │    │
│  │                                                       │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │           Connector Catalog                    │    │    │
│  │  │  Hive │ Iceberg │ Delta │ MySQL │ Postgres    │    │    │
│  │  │  Kafka│ Mongo   │ Redis │ Elastic│ Pinot      │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────┘    │
│                              │                                │
│              ┌───────────────┼───────────────┐               │
│              ▼               ▼               ▼               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │   Worker 0   │ │   Worker 1   │ │   Worker N   │        │
│  │              │ │              │ │              │        │
│  │  Splits      │ │  Splits      │ │  Splits      │        │
│  │  processing  │ │  processing  │ │  processing  │        │
│  │              │ │              │ │              │        │
│  │  Memory pool │ │  Memory pool │ │  Memory pool │        │
│  │  (query-     │ │  (query-     │ │  (query-     │        │
│  │   scoped)    │ │   scoped)    │ │   scoped)    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Query Execution Model

```
Query: SELECT region, SUM(amount)
       FROM hive.warehouse.orders
       WHERE order_date > '2024-01-01'
       GROUP BY region

Execution Plan (Stages):
Stage 0 (Leaf - on workers):
  TableScan → Filter(date > 2024-01-01) → Partial Aggregation
  Each worker processes assigned splits (file chunks)
  Predicate pushdown to storage layer

Stage 1 (Intermediate - on workers):
  Shuffle by region → Final Aggregation
  
Stage 2 (Root - on coordinator):
  Collect results → Return to client

Key differences from Spark:
  - Pipeline execution (no materialization between stages when possible)
  - Memory-based (spill to disk only in fault-tolerant mode)
  - No persistent state (pure query engine, not data processing framework)
  - Connector-based (query any data source without moving data)
```

### Trino Performance Tuning

```properties
# Worker configuration
query.max-memory=50GB
query.max-memory-per-node=10GB
query.max-total-memory-per-node=12GB

# Join optimization
join-reordering-strategy=AUTOMATIC
join-distribution-type=AUTOMATIC

# Resource groups (WLM equivalent)
resource-groups.configuration-manager=file
resource-groups.config-file=/etc/trino/resource-groups.json

# Fault-tolerant execution (Trino 400+)
retry-policy=TASK
fault-tolerant-execution-target-task-input-size=4GB
```

```json
// resource-groups.json - Workload management
{
  "rootGroups": [
    {
      "name": "interactive",
      "maxQueued": 100,
      "hardConcurrencyLimit": 20,
      "schedulingWeight": 10,
      "jmxExport": true,
      "subGroups": [
        {
          "name": "dashboard",
          "maxQueued": 50,
          "hardConcurrencyLimit": 10,
          "softMemoryLimit": "30%"
        }
      ]
    },
    {
      "name": "batch",
      "maxQueued": 500,
      "hardConcurrencyLimit": 5,
      "schedulingWeight": 1,
      "softMemoryLimit": "50%"
    }
  ]
}
```

---

## 5. dbt (Data Build Tool)

### Architecture and Concepts

```
┌──────────────────────────────────────────────────────────────┐
│                        dbt PROJECT                            │
│                                                               │
│  dbt_project.yml              ← Project configuration         │
│                                                               │
│  models/                      ← SQL transformations           │
│  ├── staging/                                                │
│  │   ├── stg_orders.sql       ← Source → Staging models       │
│  │   └── stg_customers.sql                                   │
│  ├── intermediate/                                           │
│  │   └── int_orders_joined.sql ← Business logic joins        │
│  └── marts/                                                  │
│      ├── fct_orders.sql        ← Fact tables                  │
│      └── dim_customers.sql     ← Dimension tables             │
│                                                               │
│  tests/                       ← Custom data tests             │
│  macros/                      ← Reusable SQL templates        │
│  snapshots/                   ← SCD Type 2 tracking           │
│  seeds/                       ← CSV lookup data               │
│  analyses/                    ← Ad-hoc SQL (not materialized) │
└──────────────────────────────────────────────────────────────┘
```

### Materializations

```sql
-- 1. VIEW (default) - Creates a database view
-- {{ config(materialized='view') }}
-- Pros: No storage cost, always fresh
-- Cons: Slow for complex queries, recomputed every query

-- 2. TABLE - Creates a physical table (DROP + CREATE)
-- {{ config(materialized='table') }}
-- Pros: Fast queries, pre-computed
-- Cons: Full rebuild every run, slow for large tables

-- 3. INCREMENTAL - Appends/merges new data
-- {{ config(materialized='incremental', unique_key='order_id') }}
SELECT *
FROM {{ source('raw', 'orders') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
-- Pros: Fast (only new data), efficient for large tables
-- Cons: Complex logic, potential data quality issues

-- Incremental strategies:
-- {{ config(
--     materialized='incremental',
--     incremental_strategy='merge',        -- merge (default for most)
--     unique_key='order_id',
--     on_schema_change='append_new_columns'
-- ) }}

-- Strategies:
-- 'append'         → Simple INSERT (no dedup)
-- 'merge'          → MERGE/UPSERT (dedup by unique_key)
-- 'delete+insert'  → DELETE matching + INSERT
-- 'insert_overwrite' → Overwrite partitions (BigQuery, Spark)

-- 4. EPHEMERAL - CTE inlined into downstream models
-- {{ config(materialized='ephemeral') }}
-- Pros: No object created, reduces warehouse clutter
-- Cons: Re-executed in each downstream model
```

### Snapshots (SCD Type 2)

```sql
-- snapshots/customer_snapshot.sql
{% snapshot customer_snapshot %}
{{
    config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='timestamp',
        updated_at='updated_at',
        invalidate_hard_deletes=True
    )
}}

SELECT
    customer_id,
    customer_name,
    email,
    tier,
    updated_at
FROM {{ source('raw', 'customers') }}

{% endsnapshot %}

-- Result table has:
-- customer_id | customer_name | tier   | dbt_valid_from      | dbt_valid_to
-- C001        | Alice         | Gold   | 2024-01-01 00:00:00 | 2024-06-15 00:00:00
-- C001        | Alice         | Plat   | 2024-06-15 00:00:00 | NULL (current)
```

### Tests

```yaml
# schema.yml
models:
  - name: fct_orders
    description: "Fact table for orders"
    columns:
      - name: order_id
        description: "Primary key"
        tests:
          - unique
          - not_null
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      - name: order_amount
        tests:
          - not_null
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0
              max_value: 1000000
      - name: order_status
        tests:
          - accepted_values:
              values: ['pending', 'shipped', 'delivered', 'cancelled']
```

```sql
-- tests/assert_positive_revenue.sql (custom generic test)
SELECT
    order_date,
    SUM(amount) AS daily_revenue
FROM {{ ref('fct_orders') }}
GROUP BY order_date
HAVING SUM(amount) < 0
-- Returns rows that FAIL the test (should return 0 rows)
```

### dbt Mesh (Multi-Project)

```yaml
# Project A: dbt_project.yml
name: 'finance'
models:
  finance:
    +access: public   # Models can be referenced by other projects
    marts:
      +group: finance_team

# Project B: uses Project A's models
# packages.yml
packages:
  - project: finance
    installed: true

# In Project B's model:
SELECT * FROM {{ ref('finance', 'fct_revenue') }}
```

---

## 6. Apache Beam

### Unified Model

```
┌──────────────────────────────────────────────────────────────┐
│                    APACHE BEAM                                │
│                                                               │
│  ┌────────────────────────────────────────────────┐          │
│  │              Beam SDK (Java / Python / Go)      │          │
│  │                                                  │          │
│  │  Pipeline → PCollection → PTransform → ...       │          │
│  └────────────────────────┬─────────────────────────┘          │
│                           │                                   │
│                    ┌──────▼──────┐                            │
│                    │   Runner    │                            │
│                    └──────┬──────┘                            │
│                           │                                   │
│           ┌───────────────┼───────────────┐                  │
│           ▼               ▼               ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ DirectRunner │ │ DataflowRunner│ │ FlinkRunner  │        │
│  │ (local test) │ │ (GCP)        │ │              │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                      ┌──────────────┐        │
│                                      │ SparkRunner  │        │
│                                      └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Beam Pipeline Example

```python
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows
from apache_beam.transforms.trigger import AfterWatermark, AfterCount, AccumulationMode

options = PipelineOptions([
    '--runner=DataflowRunner',
    '--project=my-gcp-project',
    '--region=us-central1',
    '--temp_location=gs://my-bucket/temp',
    '--streaming'
])

with beam.Pipeline(options=options) as p:
    events = (
        p
        | 'Read' >> beam.io.ReadFromPubSub(topic='projects/proj/topics/events')
        | 'Parse' >> beam.Map(parse_json)
        | 'Window' >> beam.WindowInto(
            FixedWindows(60),  # 60-second windows
            trigger=AfterWatermark(
                early=AfterCount(100),      # Early firing every 100 events
                late=AfterCount(1)          # Late firing for each late event
            ),
            accumulation_mode=AccumulationMode.ACCUMULATING,
            allowed_lateness=beam.transforms.window.Duration(seconds=3600)
        )
        | 'Key' >> beam.Map(lambda e: (e['user_id'], e['amount']))
        | 'Sum' >> beam.CombinePerKey(sum)
        | 'Format' >> beam.Map(format_output)
        | 'Write' >> beam.io.WriteToBigQuery(
            table='project:dataset.user_spending',
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
        )
    )
```

---

## 7. File Formats Deep Dive

### Parquet Internals

```
┌─────────────────────────────────────────────────────────────┐
│                    PARQUET FILE STRUCTURE                     │
│                                                              │
│  ┌───────────────────────────────────────────────────┐      │
│  │ Magic Number: "PAR1" (4 bytes)                     │      │
│  ├───────────────────────────────────────────────────┤      │
│  │                  ROW GROUP 0                       │      │
│  │  ┌─────────────────────────────────────────────┐  │      │
│  │  │ Column Chunk: order_id (INT64)               │  │      │
│  │  │  ┌────────────┐ ┌────────────┐              │  │      │
│  │  │  │  Page 0    │ │  Page 1    │  ...         │  │      │
│  │  │  │ (data page)│ │ (data page)│              │  │      │
│  │  │  │            │ │            │              │  │      │
│  │  │  │ Rep levels │ │ Rep levels │              │  │      │
│  │  │  │ Def levels │ │ Def levels │              │  │      │
│  │  │  │ Values     │ │ Values     │              │  │      │
│  │  │  │ (encoded)  │ │ (encoded)  │              │  │      │
│  │  │  └────────────┘ └────────────┘              │  │      │
│  │  └─────────────────────────────────────────────┘  │      │
│  │  ┌─────────────────────────────────────────────┐  │      │
│  │  │ Column Chunk: customer_name (STRING)         │  │      │
│  │  │  ┌────────────┐ ┌────────────┐              │  │      │
│  │  │  │ Dict Page  │ │ Data Page  │  ...         │  │      │
│  │  │  │ (dictionary│ │ (indices)  │              │  │      │
│  │  │  │  values)   │ │            │              │  │      │
│  │  │  └────────────┘ └────────────┘              │  │      │
│  │  └─────────────────────────────────────────────┘  │      │
│  │  ┌─────────────────────────────────────────────┐  │      │
│  │  │ Column Chunk: amount (DOUBLE)                │  │      │
│  │  │  ...                                         │  │      │
│  │  └─────────────────────────────────────────────┘  │      │
│  ├───────────────────────────────────────────────────┤      │
│  │                  ROW GROUP 1                       │      │
│  │  ...                                               │      │
│  ├───────────────────────────────────────────────────┤      │
│  │                 FOOTER                              │      │
│  │  - File metadata (schema, row groups)              │      │
│  │  - Column metadata (min/max stats per chunk)       │      │
│  │  - Key-value metadata                              │      │
│  ├───────────────────────────────────────────────────┤      │
│  │ Footer length (4 bytes)                            │      │
│  │ Magic Number: "PAR1" (4 bytes)                     │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘

Key sizing:
  Row group: 128MB - 1GB (default 128MB in Spark)
  Page: 1MB (default, unit of compression)
  Dictionary page: Auto-disabled if cardinality > threshold
```

### Encoding Strategies

```
1. PLAIN: Raw values (no encoding)
   Use: Fallback when other encodings not beneficial

2. DICTIONARY (DICT): 
   Values:  ["US", "EU", "US", "APAC", "US", "EU"]
   Dict:    {0: "US", 1: "EU", 2: "APAC"}
   Encoded: [0, 1, 0, 2, 0, 1]  ← Much smaller!
   Use: Low-medium cardinality columns (< ~60K unique values)
   Auto-falls back to PLAIN if dict too large

3. RLE (Run-Length Encoding):
   Values:  [1, 1, 1, 1, 1, 2, 2, 2, 3, 3]
   Encoded: [(1, 5), (2, 3), (3, 2)]  ← (value, count)
   Use: Repeated values (sorted columns, boolean, def/rep levels)

4. DELTA_BINARY_PACKED:
   Values:  [1000, 1001, 1002, 1005, 1010]
   Deltas:  [1, 1, 3, 5]  ← Store differences
   Use: Monotonically increasing values (timestamps, IDs)

5. DELTA_LENGTH_BYTE_ARRAY:
   For strings with common prefixes
   Use: URLs, file paths

6. BYTE_STREAM_SPLIT:
   Splits IEEE 754 floats by byte position
   Use: Float/double columns with poor dictionary compression
```

### File Format Comparison Matrix

```
┌────────────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ Feature        │ Parquet │ ORC     │ Avro    │ JSON    │ CSV     │
├────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Storage model  │Columnar │Columnar │Row      │Row      │Row      │
│ Schema         │Embedded │Embedded │Embedded │None     │None     │
│ Compression    │Excellent│Excellent│Good     │Poor     │Poor     │
│ Nested types   │Full     │Full     │Full     │Full     │No       │
│ Splittable     │Yes      │Yes      │Yes(block│No*     │No*      │
│ Schema evolve  │Yes      │Yes      │Yes      │Flexible│No       │
│ Analytics perf │Best     │Best     │Poor     │Poor     │Poor     │
│ Write speed    │Moderate │Moderate │Fast     │Fast     │Fast     │
│ Human readable │No       │No       │No       │Yes      │Yes      │
│ Ecosystem      │Broad    │Hive     │Kafka    │Universal│Universal│
│ Best for       │Analytics│Hive DW  │Streaming│APIs     │Legacy   │
│ Predicate PD   │Yes      │Yes      │No       │No       │No       │
│ Column pruning │Yes      │Yes      │No       │No       │No       │
└────────────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
* Splittable when compressed with splittable codec (bzip2, lz4 frame)
```

---

## 8. Compression

### Compression Algorithm Comparison

```
┌────────────┬────────────┬────────────┬────────────┬───────────┬───────────┐
│ Algorithm  │ Ratio      │ Compress   │ Decompress │ Splittable│ Best For  │
│            │            │ Speed      │ Speed      │           │           │
├────────────┼────────────┼────────────┼────────────┼───────────┼───────────┤
│ None       │ 1.0x       │ N/A        │ N/A        │ Yes       │ Fast I/O  │
│ Snappy     │ ~1.7x      │ 500 MB/s   │ 1500 MB/s  │ Block*    │ Balance   │
│ LZ4        │ ~2.1x      │ 700 MB/s   │ 3000 MB/s  │ Frame*    │ Speed     │
│ ZSTD       │ ~2.8x      │ 300 MB/s   │ 1200 MB/s  │ Frame*    │ Ratio     │
│ Gzip       │ ~2.5x      │ 50 MB/s    │ 300 MB/s   │ No        │ Legacy    │
│ Bzip2      │ ~3.0x      │ 20 MB/s    │ 100 MB/s   │ Yes       │ Archive   │
│ Brotli     │ ~3.2x      │ 30 MB/s    │ 400 MB/s   │ No        │ Web/cold  │
└────────────┴────────────┴────────────┴────────────┴───────────┴───────────┘
* Splittable when used within columnar formats (Parquet/ORC handle page-level)

Decision matrix:
  Hot path (low latency): LZ4 or Snappy
  Cold storage (max compression): ZSTD or Brotli
  Balanced production: ZSTD (level 3 default)
  Legacy compatibility: Gzip
  
ZSTD compression levels:
  Level 1:  Fast, moderate ratio
  Level 3:  Default, good balance
  Level 9:  Slow compress, good ratio
  Level 19: Very slow, best ratio (offline only)
```

---

## 9. Partitioning Strategies

### Time-Based Partitioning

```
Most common for event/transaction data:

Daily partitioning (most common):
  /data/events/dt=2024-01-15/
  /data/events/dt=2024-01-16/
  
Hourly partitioning (high volume):
  /data/events/dt=2024-01-15/hr=00/
  /data/events/dt=2024-01-15/hr=01/

Monthly partitioning (small volume):
  /data/events/year=2024/month=01/

Sizing guidelines:
  Target file size: 128MB - 1GB
  Target files per partition: 1-100
  
  If daily partition < 128MB → use monthly partitioning
  If daily partition > 100GB → use hourly partitioning
  If hourly partition < 128MB → stay with daily
```

### Hash Partitioning

```python
# For join optimization (co-locate related data)

# Spark bucketing
df.write \
    .bucketBy(32, "customer_id") \
    .sortBy("customer_id") \
    .saveAsTable("orders_bucketed")

# Iceberg bucket transform
CREATE TABLE orders (
    order_id BIGINT,
    customer_id STRING,
    order_date DATE
) USING iceberg
PARTITIONED BY (days(order_date), bucket(16, customer_id));
```

### Partition Evolution

```sql
-- Iceberg partition evolution (no data rewrite!)

-- Start with monthly partitioning
ALTER TABLE events SET PARTITION SPEC (month(event_time));

-- Traffic grows → switch to daily
ALTER TABLE events SET PARTITION SPEC (day(event_time));

-- Old data: still monthly partitions
-- New data: daily partitions  
-- Queries work seamlessly across both!
-- Iceberg handles partition pruning for both specs
```

---

## 10. Small Files Problem

### Problem Description

```
Cause: Many tasks writing small files
  200 Spark tasks × 10 partitions = 2000 files per write!
  
  /data/events/dt=2024-01-15/
  ├── part-00000-abc.parquet  (2MB)
  ├── part-00001-abc.parquet  (3MB)
  ├── part-00002-abc.parquet  (1MB)
  ... 2000 files averaging 2MB each

Impact:
  - NameNode memory pressure (150 bytes per file in HDFS)
  - Slow listing operations (S3: 1000 files per LIST request)
  - Poor read performance (metadata overhead per file)
  - High task scheduling overhead (1 task per file)
  - Cloud cost (per-request pricing)

Target: 128MB - 1GB per file
```

### Solutions

```python
# Solution 1: Coalesce/Repartition before write
df.coalesce(10).write.parquet("output/")        # No shuffle, uneven sizes
df.repartition(10).write.parquet("output/")      # Shuffle, even sizes

# Solution 2: maxRecordsPerFile
df.write.option("maxRecordsPerFile", 1000000).parquet("output/")

# Solution 3: AQE coalescing (Spark 3.0+)
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128m")

# Solution 4: Post-write compaction
# Read small files, write fewer large files
spark.read.parquet("output/dt=2024-01-15/") \
    .repartition(5) \
    .write.mode("overwrite") \
    .parquet("output/dt=2024-01-15/")

# Solution 5: Delta Lake OPTIMIZE
spark.sql("OPTIMIZE delta.`s3://lake/events`")
# Compacts small files into ~1GB files

# Solution 6: Iceberg compaction
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        options => map('target-file-size-bytes', '134217728')  -- 128MB
    )
""")

# Solution 7: Hive concatenation
ALTER TABLE events PARTITION (dt='2024-01-15') CONCATENATE;
```

---

## 11. Data Quality

### Great Expectations

```python
import great_expectations as gx

context = gx.get_context()

# Define expectations
validator = context.sources.pandas_default.read_csv("orders.csv")

validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_be_unique("order_id")
validator.expect_column_values_to_be_between("amount", min_value=0, max_value=1000000)
validator.expect_column_values_to_be_in_set("status", 
    ["pending", "shipped", "delivered", "cancelled"])
validator.expect_column_pair_values_a_to_be_greater_than_b(
    "ship_date", "order_date", or_equal=True)
validator.expect_table_row_count_to_be_between(min_value=1000, max_value=10000000)

# Run validation
results = validator.validate()

# Checkpoint: Run expectations as part of pipeline
checkpoint = context.add_or_update_checkpoint(
    name="orders_checkpoint",
    validations=[{
        "batch_request": batch_request,
        "expectation_suite_name": "orders_suite"
    }],
    action_list=[
        {"name": "store_result", "action": {"class_name": "StoreValidationResultAction"}},
        {"name": "slack_notify", "action": {"class_name": "SlackNotificationAction",
                                             "slack_webhook": "https://..."}}
    ]
)
```

### Amazon Deequ (for Spark)

```scala
import com.amazon.deequ.VerificationSuite
import com.amazon.deequ.checks.{Check, CheckLevel}
import com.amazon.deequ.analyzers._

val verificationResult = VerificationSuite()
    .onData(ordersDF)
    .addCheck(
        Check(CheckLevel.Error, "data quality checks")
            .isComplete("order_id")
            .isUnique("order_id")
            .isNonNegative("amount")
            .isContainedIn("status", Array("pending", "shipped", "delivered"))
            .hasSize(_ >= 1000)
            .hasCompleteness("email", _ >= 0.95)
    )
    .addCheck(
        Check(CheckLevel.Warning, "soft checks")
            .hasApproxCountDistinct("customer_id", _ >= 100)
            .hasMean("amount", _ >= 10.0)
    )
    .run()

// Anomaly detection
val anomalyDetection = AnomalyDetection()
    .onData(ordersDF)
    .addAnomalyCheck(
        RelativeRateOfChangeStrategy(maxRateIncrease = Some(2.0)),
        Size()
    )
    .run()
```

### Data Contracts

```yaml
# data-contract.yaml
apiVersion: v1
kind: DataContract
metadata:
  name: orders-v2
  owner: order-service-team
  domain: commerce
  
schema:
  type: avro
  specification:
    type: record
    name: Order
    fields:
      - name: order_id
        type: string
        constraints:
          - unique
          - not_null
      - name: amount
        type: double
        constraints:
          - not_null
          - min: 0
      - name: order_date
        type: string
        format: "YYYY-MM-DD"
        constraints:
          - not_null

quality:
  - type: freshness
    max_delay: "1 hour"
  - type: completeness
    column: customer_id
    min: 0.99
  - type: volume
    min_rows: 1000
    max_rows: 10000000

sla:
  availability: 99.9%
  latency: "< 15 minutes from source"

compatibility:
  mode: BACKWARD
```

---

## 12. Cost Optimization

### Spot/Preemptible Instance Strategy

```
┌──────────────────────────────────────────────────────────┐
│              SPOT INSTANCE STRATEGY                        │
│                                                           │
│  Driver: ON-DEMAND (always, never spot)                   │
│  Core executors: ON-DEMAND (min required for stability)   │
│  Task executors: SPOT (up to 80% savings)                 │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Driver   │  │ Core x2  │  │ Task x10 │               │
│  │ ON-DEMAND│  │ ON-DEMAND│  │ SPOT     │               │
│  │ (stable) │  │ (stable) │  │ (cheap)  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│                                                           │
│  Best practices:                                          │
│  1. Diversify instance types (m5.xlarge, m5a.xlarge, etc)│
│  2. Use multiple AZs                                     │
│  3. Set max spot price = on-demand price                 │
│  4. Handle interruptions gracefully (checkpointing)      │
│  5. Use external shuffle service (survive executor loss) │
│  6. Enable graceful decommission                         │
└──────────────────────────────────────────────────────────┘
```

### Storage Tiering

```
┌──────────────────────────────────────────────────────────┐
│                 S3 STORAGE CLASSES                         │
│                                                           │
│  Hot data (< 30 days):     S3 Standard                   │
│  Warm data (30-90 days):   S3 Standard-IA                │
│  Cold data (90-365 days):  S3 Glacier Instant Retrieval  │
│  Archive (> 1 year):       S3 Glacier Deep Archive       │
│                                                           │
│  Lifecycle policy:                                        │
│  {                                                        │
│    "Rules": [{                                            │
│      "ID": "data-lifecycle",                              │
│      "Status": "Enabled",                                 │
│      "Transitions": [                                     │
│        {"Days": 30, "StorageClass": "STANDARD_IA"},      │
│        {"Days": 90, "StorageClass": "GLACIER_IR"},       │
│        {"Days": 365, "StorageClass": "DEEP_ARCHIVE"}     │
│      ],                                                   │
│      "Expiration": {"Days": 2555}  // 7 years            │
│    }]                                                     │
│  }                                                        │
│                                                           │
│  Cost comparison (per TB/month):                          │
│  Standard:         $23.00                                 │
│  Standard-IA:      $12.50  (45% savings)                 │
│  Glacier IR:       $4.00   (83% savings)                 │
│  Glacier Deep:     $0.99   (96% savings)                 │
└──────────────────────────────────────────────────────────┘
```

---

## 13. Orchestration Comparison

```
┌────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Feature        │ Airflow  │ Dagster  │ Prefect  │ Luigi    │ Argo     │
├────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Language       │ Python   │ Python   │ Python   │ Python   │ YAML     │
│ DAG definition │ Python   │ Python   │ Python   │ Python   │ YAML     │
│ Scheduling     │ Cron     │ Cron+    │ Cron+    │ External │ Cron     │
│                │ Dataset  │ Sensors  │ Events   │          │ Events   │
│ UI             │ Excellent│ Good     │ Excellent│ Basic    │ Good     │
│ Data-aware     │ Datasets │ Assets   │ No       │ No       │ No       │
│ Testing        │ Good     │ Excellent│ Good     │ Fair     │ Fair     │
│ Scalability    │ High     │ High     │ High     │ Medium   │ Very High│
│ K8s native     │ Executor │ K8s      │ K8s      │ No       │ Native   │
│ Community      │ Largest  │ Growing  │ Growing  │ Stable   │ Large    │
│ Cloud managed  │ MWAA,    │ Dagster  │ Prefect  │ No       │ Argo CD  │
│                │ Composer │ Cloud    │ Cloud    │          │          │
│ Best for       │ General  │ Data     │ ML Ops   │ Simple   │ K8s-     │
│                │ purpose  │ platform │ Modern   │ ETL      │ native   │
│ Maturity       │ Very High│ Medium   │ Medium   │ High     │ High     │
│ Data lineage   │ Basic    │ Built-in │ Basic    │ None     │ None     │
│ Asset-centric  │ No       │ Yes      │ No       │ No       │ No       │
│ Backfill       │ Built-in │ Built-in │ Manual   │ Manual   │ Manual   │
└────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘

When to use what:
  Airflow:  General purpose, large teams, broad ecosystem
  Dagster:  Software-defined assets, data-aware, testing-first
  Prefect:  Modern Python-native, simple deployment, ML focus
  Luigi:    Simple DAGs, minimal infrastructure
  Argo:     Kubernetes-native, multi-language, CI/CD + data
  Temporal: Long-running workflows, microservice orchestration
```

---

## Production Checklist

```
[ ] File format: Parquet or ORC (never CSV/JSON for analytical workloads)
[ ] Compression: ZSTD for storage, LZ4/Snappy for hot path
[ ] Partitioning: Time-based, right granularity (not too many, not too few)
[ ] Target file size: 128MB - 1GB
[ ] Small file compaction scheduled (OPTIMIZE / manual job)
[ ] Data quality checks in pipeline (Great Expectations / Deequ)
[ ] Schema evolution strategy with compatibility checks
[ ] Idempotent writes (partition overwrite / MERGE)
[ ] Data contracts between producer and consumer teams
[ ] Monitoring: Pipeline latency, data freshness, quality scores
[ ] Cost optimization: Spot instances, storage tiering, right-sizing
[ ] Orchestration: HA setup, monitoring, alerting
[ ] Backfill strategy documented and tested
[ ] DR plan: Cross-region replication for critical data
```
