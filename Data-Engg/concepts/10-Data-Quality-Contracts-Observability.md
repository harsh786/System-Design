# Data Quality, Contracts, Observability & NoSQL Deep Dive - Staff Architect Reference

---

## Part A: NoSQL & Ancillary Data Systems

### 1. Apache Cassandra

```
Architecture (Peer-to-Peer, No Master):
┌──────────────────────────────────────────────────────────────┐
│                    CASSANDRA RING                              │
│                                                               │
│              Node A (token: 0-24)                             │
│                ╱             ╲                                │
│     Node F   ╱                 ╲   Node B                    │
│  (token:     ╱    Gossip        ╲  (token: 25-49)            │
│   125-149)  │    Protocol        │                            │
│              │   (peer-to-peer)  │                            │
│     Node E   ╲                 ╱   Node C                    │
│  (token:      ╲               ╱   (token: 50-74)             │
│   100-124)     ╲             ╱                                │
│              Node D (token: 75-99)                            │
│                                                               │
│  Consistent Hashing:                                         │
│  partition_key → hash → token → responsible node             │
│                                                               │
│  Replication Factor = 3:                                     │
│  Data on primary node + next 2 clockwise nodes               │
│                                                               │
│  Virtual nodes (vnodes): Each physical node owns ~256 tokens  │
│  → Better distribution, easier rebalancing                    │
└──────────────────────────────────────────────────────────────┘

Consistency Levels:
┌──────────────┬─────────────────────────────────────────────┐
│ Level        │ Description                                 │
├──────────────┼─────────────────────────────────────────────┤
│ ONE          │ 1 replica acks (lowest latency)             │
│ QUORUM       │ ⌊RF/2⌋ + 1 replicas ack (strong)           │
│ LOCAL_QUORUM │ Quorum in local DC only                     │
│ EACH_QUORUM  │ Quorum in each DC                           │
│ ALL          │ All replicas ack (highest consistency)       │
│ ANY          │ Even hinted handoff counts (highest avail.)  │
└──────────────┴─────────────────────────────────────────────┘

Strong consistency formula: R + W > N
  Read CL=QUORUM + Write CL=QUORUM → Strong consistency
  Read CL=ONE + Write CL=ALL → Strong consistency

Write path:
  Client → Coordinator → Commit Log (append) → Memtable → SSTable (flush)

Read path:
  Client → Coordinator → Bloom Filter → Key Cache → SSTable
  Merge results from Memtable + SSTables

Compaction strategies:
  SizeTiered (STCS): Good for write-heavy (default)
  Leveled (LCS): Good for read-heavy, more predictable
  TimeWindow (TWCS): Good for time-series (TTL data)

Data modeling rules:
  1. Model around QUERIES, not entities
  2. Denormalize aggressively (no joins)
  3. One table per query pattern
  4. Partition key determines data distribution
  5. Clustering key determines sort order within partition
  6. Keep partitions < 100MB, < 100K rows

Anti-patterns:
  - Large partitions (unbounded growth)
  - Secondary indexes on high-cardinality columns
  - Read-before-write patterns
  - Using Cassandra like a relational DB
```

### 2. Elasticsearch

```
Architecture:
┌──────────────────────────────────────────────────────────────┐
│                    ELASTICSEARCH CLUSTER                       │
│                                                               │
│  ┌──────────────────────────────────────────────────┐        │
│  │         Master-eligible nodes (3 minimum)         │        │
│  │  - Cluster state management                       │        │
│  │  - Index creation/deletion                        │        │
│  │  - Shard allocation decisions                     │        │
│  │  - Node membership (via Zen Discovery / Raft)     │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  Index: orders (5 primary shards, 1 replica each)            │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ Data     │    │ Data     │    │ Data     │               │
│  │ Node 0   │    │ Node 1   │    │ Node 2   │               │
│  │          │    │          │    │          │               │
│  │ P0  R2   │    │ P1  R3   │    │ P2  R4   │               │
│  │ P3  R1   │    │ P4  R0   │    │ R1  R3   │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│                                                               │
│  P = Primary shard, R = Replica shard                        │
│  Each shard is a Lucene index                                │
│                                                               │
│  Write path:                                                 │
│  Client → Coordinating node → Primary shard → Replica(s)    │
│  In-memory buffer → Refresh (1s) → Segment (searchable)     │
│  Transaction log → Flush → Lucene commit                     │
│                                                               │
│  Read path:                                                  │
│  Client → Coordinating → Scatter to shards → Gather + Merge │
│  Two phases: Query (get doc IDs) → Fetch (get documents)     │
└──────────────────────────────────────────────────────────────┘

Key concepts:
  Inverted Index: term → [doc_id1, doc_id2, ...] (fast text search)
  Analyzer: Character filters → Tokenizer → Token filters
  Mapping: Schema definition (dynamic or explicit)
  
  Index lifecycle (ILM):
    Hot → Warm → Cold → Frozen → Delete
    
  Shard sizing guidelines:
    - 10-50 GB per shard (sweet spot: 20-40 GB)
    - Max ~20 shards per GB of heap
    - Fewer larger shards > many small shards

Performance tuning:
  - Bulk indexing (500-5000 docs per batch)
  - Refresh interval: 30s for indexing-heavy workloads (vs 1s default)
  - Disable replicas during bulk reindex, re-enable after
  - Use doc_values for aggregations, fielddata for text (avoid)
  - Routing: co-locate related docs on same shard
```

### 3. Redis for Data Engineering

```
Use cases in data pipelines:
┌──────────────────────────────────────────────────────────────┐
│                    REDIS IN DATA ENGINEERING                   │
│                                                               │
│  1. CACHING / LOOKUP ENRICHMENT                              │
│     Stream event → Redis lookup (user profile) → Enriched    │
│     SET user:123 '{"name":"Alice","tier":"Gold"}'            │
│     GET user:123 → enrich streaming event                    │
│                                                               │
│  2. DEDUPLICATION                                            │
│     SETEX event:abc123 86400 1  (TTL 24h)                    │
│     If key exists → duplicate, skip                          │
│     If not → new event, process                              │
│     HyperLogLog: PFADD unique_users user_123                 │
│     PFCOUNT unique_users → approximate distinct count        │
│                                                               │
│  3. RATE LIMITING                                            │
│     INCR api:user:123:minute                                 │
│     EXPIRE api:user:123:minute 60                            │
│     If count > limit → throttle                              │
│                                                               │
│  4. REAL-TIME LEADERBOARDS                                   │
│     ZADD leaderboard 1500 user:123                           │
│     ZREVRANGE leaderboard 0 9 WITHSCORES → top 10            │
│                                                               │
│  5. STREAM PROCESSING (Redis Streams)                        │
│     XADD orders * user_id 123 amount 99.99                   │
│     XREADGROUP GROUP cg1 consumer1 COUNT 10 BLOCK 0          │
│       STREAMS orders >                                       │
│     XACK orders cg1 <message_id>                             │
│                                                               │
│  6. DISTRIBUTED LOCKS                                        │
│     SET lock:resource1 owner123 NX PX 30000                  │
│     RedLock algorithm for multi-instance                     │
│                                                               │
│  Data structures for DE:                                     │
│  - String: Simple K/V, counters                              │
│  - Hash: Object storage (user profiles)                      │
│  - Set: Membership checks, intersections                     │
│  - Sorted Set: Rankings, time-series indices                 │
│  - HyperLogLog: Cardinality estimation (12KB per key!)       │
│  - Bloom Filter: Probabilistic membership (RedisBloom)       │
│  - Stream: Append-only log (like mini-Kafka)                 │
└──────────────────────────────────────────────────────────────┘

Persistence modes:
  RDB: Point-in-time snapshots (fork + dump)
  AOF: Append-only file (every write logged)
  RDB + AOF: Best of both (recommended for durability)
  
Clustering:
  Redis Cluster: Hash slots (16384 total), auto-sharding
  Sentinel: HA for non-clustered setup (failover)
```

### 4. Data Catalog Systems

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA CATALOG LANDSCAPE                      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                  DataHub (LinkedIn)                    │    │
│  │  - Metadata graph (entities + relationships)          │    │
│  │  - Push/pull ingestion (Kafka-based)                  │    │
│  │  - Lineage: column-level, cross-platform              │    │
│  │  - Actions framework (metadata-driven automation)     │    │
│  │  - GraphQL API for programmatic access                │    │
│  │  - Timeline: Track metadata changes over time         │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Apache Atlas (Hadoop ecosystem)          │    │
│  │  - Type system (entities, classifications, glossary)  │    │
│  │  - Hook-based ingestion (Hive, Spark, Kafka hooks)    │    │
│  │  - JanusGraph backend for metadata                    │    │
│  │  - Classification propagation through lineage         │    │
│  │  - REST API                                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                   OpenMetadata                        │    │
│  │  - Schema-first (JSON Schema for metadata)            │    │
│  │  - Built-in data quality (Great Expectations based)    │    │
│  │  - Collaboration (tasks, conversations on data)       │    │
│  │  - Lineage from query parsing                         │    │
│  │  - API-first design                                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  Commercial: Atlan, Alation, Collibra, Informatica           │
│                                                               │
│  Key catalog capabilities:                                   │
│  ✓ Discovery (search, browse, tags)                          │
│  ✓ Lineage (column-level, cross-platform)                    │
│  ✓ Governance (classification, access policies)              │
│  ✓ Collaboration (owners, descriptions, glossary)            │
│  ✓ Quality (profiling, validation results)                   │
│  ✓ Automation (metadata-driven actions/policies)             │
└──────────────────────────────────────────────────────────────┘
```

---

## Part B: Data Contracts

### 1. What Are Data Contracts?

```
Problem:
  Producer team changes column name: user_id → userId
  20 downstream consumers break silently
  Nobody knew about the dependency

Solution: Explicit interface between data producer and consumer

┌──────────────────────────────────────────────────────────────┐
│                    DATA CONTRACT                              │
│                                                               │
│  PRODUCER                          CONSUMER                   │
│  (Orders team)                     (Analytics team)           │
│       │                                  │                    │
│       │     ┌──────────────────┐         │                    │
│       │     │  DATA CONTRACT   │         │                    │
│       ├────▶│                  │◀────────┤                    │
│       │     │  Schema          │         │                    │
│       │     │  SLAs            │         │                    │
│       │     │  Quality rules   │         │                    │
│       │     │  Ownership       │         │                    │
│       │     │  Semantics       │         │                    │
│       │     │  Change policy   │         │                    │
│       │     └──────────────────┘         │                    │
│       │                                  │                    │
│  Breaking change?                        │                    │
│  → Contract violation                    │                    │
│  → CI/CD blocks deployment              │                    │
│  → Negotiate with consumers first        │                    │
└──────────────────────────────────────────────────────────────┘
```

### 2. Data Contract Specification (YAML)

```yaml
# data_contract.yaml
apiVersion: v1
kind: DataContract
metadata:
  name: orders-events
  version: 2.1.0
  owner: orders-team
  domain: commerce
  
schema:
  type: avro  # or protobuf, json-schema
  fields:
    - name: order_id
      type: string
      required: true
      pii: false
      description: "Unique order identifier (UUID v4)"
    - name: customer_id
      type: string
      required: true
      pii: true
      classification: CONFIDENTIAL
    - name: amount
      type: decimal(10,2)
      required: true
      constraints:
        minimum: 0.01
        maximum: 999999.99
    - name: order_date
      type: timestamp
      required: true
      format: "yyyy-MM-dd'T'HH:mm:ss.SSSZ"
    - name: status
      type: string
      required: true
      enum: [CREATED, CONFIRMED, SHIPPED, DELIVERED, CANCELLED]
    - name: items
      type: array<struct>
      fields:
        - name: product_id
          type: string
          required: true
        - name: quantity
          type: integer
          required: true
          constraints:
            minimum: 1

quality:
  rules:
    - name: orders_not_null
      type: not_null
      columns: [order_id, customer_id, amount]
    - name: amount_positive
      type: custom_sql
      sql: "SELECT COUNT(*) FROM {table} WHERE amount <= 0"
      threshold: 0  # zero violations allowed
    - name: freshness
      type: freshness
      max_delay: "PT30M"  # ISO 8601 duration: 30 minutes
    - name: volume
      type: row_count
      min: 1000
      max: 1000000
      period: daily
    - name: uniqueness
      type: unique
      columns: [order_id]
    - name: referential_integrity
      type: foreign_key
      column: customer_id
      references: customers.customer_id
      threshold: 0.99  # 99% match rate

sla:
  availability: 99.9%
  latency:
    p50: 5s
    p99: 30s
  freshness: 30m  # data must be no older than 30 minutes
  
compatibility:
  mode: BACKWARD  # New schema must be backward compatible
  # BACKWARD: new schema can read old data
  # FORWARD: old schema can read new data
  # FULL: both backward and forward
  # NONE: no compatibility check
  
delivery:
  channel: kafka
  topic: commerce.orders.v2
  format: avro
  partitioning: customer_id
  
governance:
  retention: 7 years
  encryption: AES-256
  access:
    - team: analytics
      permission: read
    - team: ml-platform
      permission: read
    - team: orders-team
      permission: write
```

### 3. Contract Enforcement Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              CONTRACT ENFORCEMENT PIPELINE                     │
│                                                               │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │ Producer │    │   Schema     │    │   Quality    │        │
│  │ writes   │───▶│   Registry   │───▶│   Gate       │        │
│  │ data     │    │              │    │              │        │
│  └──────────┘    │ Validate     │    │ Run quality  │        │
│                  │ schema       │    │ rules from   │        │
│                  │ compatibility│    │ contract     │        │
│                  └──────────────┘    └──────┬───────┘        │
│                                             │                 │
│                                    ┌────────▼────────┐       │
│                                    │   Pass?         │       │
│                                    │                 │       │
│                                    │  YES → Publish  │       │
│                                    │  NO  → Alert +  │       │
│                                    │        Block    │       │
│                                    └─────────────────┘       │
│                                                               │
│  CI/CD Integration:                                          │
│  1. PR adds new column → Contract CI checks compatibility     │
│  2. PR removes column → Contract CI BLOCKS (breaking change) │
│  3. PR changes type → Contract CI BLOCKS or warns             │
│  4. Deploy → Runtime quality checks on first batch            │
│  5. Runtime → Continuous monitoring against SLAs              │
│                                                               │
│  Tools:                                                      │
│  - Soda: Contract-as-code, CI/CD integration                 │
│  - DataHub: Contract support in metadata platform             │
│  - Great Expectations: Quality checks as contract rules       │
│  - Schema Registry: Schema compatibility enforcement          │
│  - Custom: dbt tests + Airflow callbacks                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Part C: Data Quality

### 1. Data Quality Dimensions

```
┌──────────────────────────────────────────────────────────────┐
│                DATA QUALITY DIMENSIONS                        │
│                                                               │
│  COMPLETENESS: Are all expected values present?              │
│    Metric: % of non-null values in required columns           │
│    Example: 99.8% of orders have customer_id                  │
│    Check: SELECT COUNT(*) WHERE customer_id IS NULL            │
│                                                               │
│  ACCURACY: Do values correctly represent reality?             │
│    Metric: % of values matching authoritative source          │
│    Example: Email format valid, zip code exists               │
│    Check: Regex validation, reference data lookup              │
│                                                               │
│  CONSISTENCY: Same data = same value across systems?          │
│    Metric: % match between systems                            │
│    Example: User count in DW = user count in source           │
│    Check: Cross-system reconciliation queries                  │
│                                                               │
│  TIMELINESS: Is data available when expected?                 │
│    Metric: Delay from event to availability                   │
│    Example: Orders available within 15 min of placement       │
│    Check: MAX(event_time) vs current_time                      │
│                                                               │
│  UNIQUENESS: No unintended duplicates?                       │
│    Metric: % of distinct keys vs total rows                   │
│    Example: 0 duplicate order_ids                             │
│    Check: COUNT(*) vs COUNT(DISTINCT order_id)                 │
│                                                               │
│  VALIDITY: Values within expected domain?                    │
│    Metric: % of values in valid range/enum                    │
│    Example: Status in [CREATED,SHIPPED,DELIVERED]             │
│    Check: COUNT(*) WHERE status NOT IN (...)                   │
│                                                               │
│  FRESHNESS: How recent is the latest data?                   │
│    Metric: Age of newest record                               │
│    Example: Latest order < 30 minutes old                     │
│    Check: DATEDIFF(NOW(), MAX(created_at)) < 30               │
│                                                               │
│  VOLUME: Expected number of records?                         │
│    Metric: Row count within expected range                    │
│    Example: 50K-200K orders per day (weekday)                 │
│    Check: COUNT(*) BETWEEN min AND max for time window         │
│                                                               │
│  SCHEMA: Structure matches expectation?                      │
│    Metric: Column names, types, ordering                      │
│    Example: No unexpected columns, types unchanged            │
│    Check: Compare current schema vs registered schema          │
└──────────────────────────────────────────────────────────────┘
```

### 2. Great Expectations Framework

```python
# great_expectations_example.py

import great_expectations as gx

# Initialize context
context = gx.get_context()

# Define data source
datasource = context.sources.add_pandas("my_datasource")
data_asset = datasource.add_dataframe_asset("orders")

# Create expectation suite
suite = context.add_expectation_suite("orders_quality")

# Column-level expectations
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeUnique(column="order_id")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="amount", min_value=0.01, max_value=999999.99
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="status",
        value_set=["CREATED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"]
    )
)

# Table-level expectations
suite.add_expectation(
    gx.expectations.ExpectTableRowCountToBeBetween(
        min_value=1000, max_value=1000000
    )
)

# Column pair expectations
suite.add_expectation(
    gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="total_amount", column_B="discount_amount"
    )
)

# Run validation
batch_request = data_asset.build_batch_request(dataframe=df)
results = context.run_checkpoint(
    checkpoint_name="orders_checkpoint",
    batch_request=batch_request,
    expectation_suite_name="orders_quality"
)

# Check results
if not results.success:
    failed = [r for r in results.results if not r.success]
    for f in failed:
        print(f"FAILED: {f.expectation_config.expectation_type}")
        print(f"  Observed: {f.result}")
    raise DataQualityException(f"{len(failed)} quality checks failed")
```

### 3. dbt Data Quality Testing

```sql
-- schema.yml (dbt tests)
version: 2

models:
  - name: fct_orders
    description: "Order fact table"
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('dim_customer')
              field: customer_id
      - name: amount
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1000000
      - name: status
        tests:
          - accepted_values:
              values: ['CREATED', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED']
    tests:
      - dbt_utils.recency:
          datepart: hour
          field: created_at
          interval: 1
      - dbt_utils.equal_rowcount:
          compare_model: ref('stg_orders')

-- Custom generic test: tests/generic/test_no_orphan_records.sql
{% test no_orphan_records(model, column_name, parent_model, parent_column) %}
SELECT {{ column_name }}
FROM {{ model }}
WHERE {{ column_name }} NOT IN (
    SELECT {{ parent_column }} FROM {{ parent_model }}
)
{% endtest %}

-- Custom singular test: tests/assert_total_revenue_positive.sql
SELECT
    date_trunc('day', order_date) as order_day,
    SUM(amount) as daily_revenue
FROM {{ ref('fct_orders') }}
GROUP BY 1
HAVING SUM(amount) <= 0
-- This query should return 0 rows (no days with negative revenue)
```

### 4. Data Quality Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                DATA QUALITY ARCHITECTURE                          │
│                                                                    │
│  LAYER 1: Schema Validation (Preventive)                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Schema Registry / Contract checks                        │    │
│  │  → Block bad data at ingestion                            │    │
│  │  → Type checking, required fields, compatibility          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  LAYER 2: Pipeline Validation (Detective - In-pipeline)          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  dbt tests / Great Expectations / Soda                    │    │
│  │  → Run after each transformation                          │    │
│  │  → Null checks, range checks, referential integrity       │    │
│  │  → Fail pipeline on critical violations                   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  LAYER 3: Statistical Monitoring (Detective - Post-pipeline)     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Anomaly detection on metrics:                            │    │
│  │  - Row count: ±3σ from 30-day rolling average             │    │
│  │  - Null rate: Spike detection                             │    │
│  │  - Distribution shift: KL divergence, PSI                 │    │
│  │  - Freshness: SLA breach detection                        │    │
│  │  → Alert but don't block (avoid false positives)          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  LAYER 4: Reconciliation (Corrective)                            │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Cross-system counts and checksums                        │    │
│  │  Source system record count = DW record count?            │    │
│  │  Source SUM(amount) = DW SUM(amount)?                     │    │
│  │  → Daily reconciliation jobs                              │    │
│  │  → Drift reports for data stewards                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  LAYER 5: Human Review (Governance)                              │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Data quality dashboards                                  │    │
│  │  Incident management for data issues                      │    │
│  │  Quality score per dataset (composite metric)             │    │
│  │  → Weekly data quality reviews                            │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part D: Data Observability

### 1. Data Observability vs Monitoring

```
┌──────────────────────────────────────────────────────────────┐
│         DATA OBSERVABILITY vs DATA MONITORING                 │
│                                                               │
│  MONITORING (Known unknowns):                                │
│  - Predefined checks: "Is order_id null?"                    │
│  - Manual rule creation                                      │
│  - Reactive: Only catches what you test for                  │
│  - Tools: dbt tests, Great Expectations                      │
│                                                               │
│  OBSERVABILITY (Unknown unknowns):                           │
│  - Automated anomaly detection                               │
│  - ML-based pattern learning                                 │
│  - Proactive: Catches issues you didn't anticipate           │
│  - Includes lineage for root cause analysis                  │
│  - Tools: Monte Carlo, Bigeye, Metaplane                     │
│                                                               │
│  FIVE PILLARS OF DATA OBSERVABILITY:                         │
│  ┌─────────────┐                                             │
│  │ 1. FRESHNESS│ Is data arriving on time?                   │
│  │             │ Metric: time since last update              │
│  ├─────────────┤                                             │
│  │ 2. VOLUME   │ Is the expected amount of data arriving?    │
│  │             │ Metric: row count, byte size                │
│  ├─────────────┤                                             │
│  │ 3. SCHEMA   │ Has the structure changed unexpectedly?     │
│  │             │ Metric: column additions/removals/type chg  │
│  ├─────────────┤                                             │
│  │ 4. QUALITY  │ Are values within expected ranges?          │
│  │             │ Metric: null rates, distribution, outliers  │
│  ├─────────────┤                                             │
│  │ 5. LINEAGE  │ Where did data come from? What broke?       │
│  │             │ Metric: upstream/downstream dependency graph │
│  └─────────────┘                                             │
└──────────────────────────────────────────────────────────────┘
```

### 2. Observability Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              DATA OBSERVABILITY ARCHITECTURE                      │
│                                                                    │
│  DATA SOURCES:                                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│  │Kafka │ │Spark │ │Airflw│ │Snowfl│ │dbt   │                  │
│  │      │ │      │ │      │ │      │ │      │                  │
│  │Broker│ │Job   │ │Task  │ │Query │ │Model │                  │
│  │metrics│ │metrics│ │logs │ │logs  │ │logs  │                  │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘                  │
│     └────────┴────────┴────────┴────────┘                        │
│                        │                                          │
│              ┌─────────▼──────────┐                               │
│              │  METADATA STORE    │                               │
│              │                    │                               │
│              │  Table statistics  │                               │
│              │  Schema history    │                               │
│              │  Lineage graph     │                               │
│              │  Quality metrics   │                               │
│              │  Pipeline metadata │                               │
│              └─────────┬──────────┘                               │
│                        │                                          │
│              ┌─────────▼──────────┐                               │
│              │  ANOMALY DETECTION │                               │
│              │                    │                               │
│              │  Statistical:      │                               │
│              │  - Z-score         │                               │
│              │  - IQR             │                               │
│              │  - Seasonal decomp │                               │
│              │                    │                               │
│              │  ML-based:         │                               │
│              │  - Prophet         │                               │
│              │  - Isolation Forest│                               │
│              │  - Autoencoders    │                               │
│              └─────────┬──────────┘                               │
│                        │                                          │
│              ┌─────────▼──────────┐                               │
│              │  ALERTING + RCA    │                               │
│              │                    │                               │
│              │  Alert routing:    │                               │
│              │  - Severity-based  │                               │
│              │  - Team-based      │                               │
│              │  - Escalation      │                               │
│              │                    │                               │
│              │  Root cause:       │                               │
│              │  - Lineage trace   │                               │
│              │  - Correlated      │                               │
│              │    anomalies       │                               │
│              │  - Change events   │                               │
│              └────────────────────┘                               │
│                                                                    │
│  Key metrics to track:                                            │
│  - Data freshness per table (last update time)                    │
│  - Row count trends (daily/hourly)                                │
│  - Column null rates over time                                    │
│  - Schema change events                                           │
│  - Pipeline duration trends                                       │
│  - Cross-system reconciliation deltas                             │
│  - Data quality score (composite)                                 │
│  - Incident count and MTTR                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 3. Building a Data Quality Score

```
DATA QUALITY SCORECARD:

Table-level score = Weighted average of dimension scores

┌──────────────┬────────┬──────────────────────────────────────┐
│ Dimension    │ Weight │ Calculation                          │
├──────────────┼────────┼──────────────────────────────────────┤
│ Completeness │ 25%    │ 1 - (null_count / total_count)       │
│ Freshness    │ 20%    │ 1 if within SLA, decay function      │
│ Volume       │ 15%    │ 1 if within ±2σ of expected          │
│ Uniqueness   │ 15%    │ distinct_keys / total_rows            │
│ Validity     │ 15%    │ valid_values / total_values           │
│ Consistency  │ 10%    │ matched_records / total_records       │
├──────────────┼────────┼──────────────────────────────────────┤
│ TOTAL        │ 100%   │ Weighted sum (0.0 - 1.0)             │
└──────────────┴────────┴──────────────────────────────────────┘

Score interpretation:
  0.95 - 1.00: Excellent (green)
  0.90 - 0.94: Good (yellow)
  0.80 - 0.89: Needs attention (orange)
  < 0.80:      Critical (red)

Tracking over time:
  Store daily scores in a time-series table
  Alert on score drops > 5% day-over-day
  Weekly reports to data stewards
  Monthly trends for leadership

SQL implementation:
  SELECT
    table_name,
    ROUND(
      0.25 * completeness_score +
      0.20 * freshness_score +
      0.15 * volume_score +
      0.15 * uniqueness_score +
      0.15 * validity_score +
      0.10 * consistency_score
    , 3) AS quality_score,
    CASE
      WHEN quality_score >= 0.95 THEN 'EXCELLENT'
      WHEN quality_score >= 0.90 THEN 'GOOD'
      WHEN quality_score >= 0.80 THEN 'NEEDS_ATTENTION'
      ELSE 'CRITICAL'
    END AS quality_tier,
    scored_at
  FROM data_quality_metrics
  WHERE scored_at = CURRENT_DATE
  ORDER BY quality_score ASC;
```

### 4. Incident Management for Data Issues

```
DATA INCIDENT LIFECYCLE:
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  DETECT → TRIAGE → INVESTIGATE → RESOLVE → POSTMORTEM          │
│                                                                  │
│  1. DETECT                                                      │
│     Automated:                                                   │
│     - Anomaly detection fires alert                              │
│     - dbt test fails in pipeline                                 │
│     - SLA breach notification                                    │
│     Manual:                                                      │
│     - Analyst reports wrong numbers                              │
│     - Dashboard shows unexpected data                            │
│                                                                  │
│  2. TRIAGE (within 15 min)                                      │
│     Severity levels:                                             │
│     SEV1: Revenue-impacting, customer-facing, regulatory        │
│     SEV2: Internal analytics broken, data delayed >2h           │
│     SEV3: Minor quality issues, non-critical tables             │
│     SEV4: Cosmetic issues, documentation gaps                   │
│                                                                  │
│  3. INVESTIGATE                                                  │
│     Use lineage to trace upstream:                               │
│     Bad table → upstream table → pipeline → source change       │
│     Check:                                                       │
│     - Source system changes (deploys, schema changes)            │
│     - Pipeline failures (Airflow tasks, Spark jobs)             │
│     - Infrastructure issues (cluster, network, storage)         │
│     - Volume spikes/drops                                       │
│                                                                  │
│  4. RESOLVE                                                      │
│     - Fix source issue or add defensive handling                │
│     - Backfill affected data (with idempotent pipelines)        │
│     - Validate fix with quality checks                          │
│     - Communicate resolution to stakeholders                    │
│                                                                  │
│  5. POSTMORTEM                                                  │
│     - Root cause analysis (5 whys)                              │
│     - Impact assessment (tables, reports, decisions affected)   │
│     - Prevention: New tests/monitors added                      │
│     - Process improvements                                      │
│                                                                  │
│  METRICS:                                                       │
│  - MTTD: Mean time to detect (target: < 30 min)                │
│  - MTTR: Mean time to resolve (target: < 4 hours for SEV1)     │
│  - Incident frequency (trending down = improving)              │
│  - Data downtime hours per month                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part E: Schema Evolution

### 1. Schema Evolution Strategies

```
┌──────────────────────────────────────────────────────────────┐
│               SCHEMA EVOLUTION STRATEGIES                     │
│                                                               │
│  AVRO SCHEMA EVOLUTION:                                      │
│                                                               │
│  Backward Compatible (Consumer can read old data):           │
│  ✓ Add field with default value                              │
│  ✓ Remove field (consumer ignores unknown fields)            │
│  ✗ Remove field without default in old schema                │
│  ✗ Change field type (int → string)                          │
│                                                               │
│  Forward Compatible (Old consumer can read new data):        │
│  ✓ Add field (old consumer ignores)                          │
│  ✓ Remove field with default value                           │
│  ✗ Add required field without default                        │
│                                                               │
│  Full Compatible:                                            │
│  ✓ Add field with default value                              │
│  ✓ Remove field with default value                           │
│  ✗ Add/remove field without default                          │
│                                                               │
│  Protobuf Evolution:                                         │
│  ✓ Add new fields (must use new field numbers)               │
│  ✓ Remove fields (old number must never be reused)           │
│  ✓ Rename fields (wire format uses numbers, not names)       │
│  ✗ Change field numbers                                      │
│  ✗ Change field types (mostly)                               │
│                                                               │
│  Best practice: Use reserved keyword for removed fields      │
│  message Order {                                             │
│    reserved 3, 6;  // Previously used field numbers          │
│    reserved "old_field_name";  // Never reuse                │
│    string order_id = 1;                                      │
│    int64 amount = 2;                                         │
│    // field 3 was 'legacy_status' — REMOVED                  │
│    string status = 4;                                        │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘

TABLE FORMAT SCHEMA EVOLUTION:

┌────────────────┬──────────────────────────────────────────────┐
│ Format         │ Schema Evolution Support                     │
├────────────────┼──────────────────────────────────────────────┤
│ Apache Iceberg │ Full evolution: add, drop, rename, reorder, │
│                │ widen types. Column IDs (not names) for      │
│                │ tracking. No rewrite needed.                 │
│ Delta Lake     │ Add columns, change nullability. Column      │
│                │ mapping mode for renames/drops. May need     │
│                │ overwriteSchema for breaking changes.        │
│ Apache Hudi    │ Add columns (append to end). Type promotion  │
│                │ (int→long). Schema-on-read for evolution.    │
│ Parquet        │ Schema merging (read union of schemas).      │
│                │ Column-by-name matching. No renames.         │
└────────────────┴──────────────────────────────────────────────┘
```

### 2. Schema Registry Patterns

```
Schema Registry Deployment:
┌──────────────────────────────────────────────────────────────┐
│                                                               │
│  Producer App ──▶ Schema Registry ──▶ Kafka                  │
│                    │                                          │
│                    │ 1. Register schema (or get cached ID)    │
│                    │ 2. Validate compatibility                │
│                    │ 3. Return schema ID                      │
│                    │                                          │
│  Consumer App ◀── Schema Registry                            │
│                    │                                          │
│                    │ 1. Get schema by ID from message header  │
│                    │ 2. Cache locally                         │
│                    │ 3. Deserialize with correct schema       │
│                                                               │
│  Wire format:                                                │
│  [Magic Byte (1)] [Schema ID (4)] [Avro Payload (N)]         │
│                                                               │
│  Subject naming strategies:                                  │
│  TopicNameStrategy: <topic>-value, <topic>-key              │
│  RecordNameStrategy: <fully.qualified.record.name>           │
│  TopicRecordNameStrategy: <topic>-<record.name>              │
│                                                               │
│  Multi-DC Schema Registry:                                   │
│  - Schema Registry leader-follower replication               │
│  - Or: Schema linking (Confluent)                            │
│  - Schemas must be identical across DCs                      │
│  - Register in primary, replicate to secondary               │
└──────────────────────────────────────────────────────────────┘
```

---

## Part F: Data Governance

### 1. Governance Framework

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA GOVERNANCE FRAMEWORK                      │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                 ORGANIZATION                             │     │
│  │  Chief Data Officer (CDO)                                │     │
│  │  Data Governance Council                                 │     │
│  │  Domain Data Stewards                                    │     │
│  │  Data Engineers (implementation)                         │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ DATA     │  │ DATA     │  │ DATA     │  │ DATA     │        │
│  │ QUALITY  │  │ PRIVACY  │  │ SECURITY │  │ LIFECYCLE│        │
│  │          │  │          │  │          │  │          │        │
│  │ Standards│  │ PII      │  │ RBAC     │  │ Retention│        │
│  │ Metrics  │  │ GDPR     │  │ Column   │  │ Archival │        │
│  │ SLAs     │  │ CCPA     │  │ masking  │  │ Deletion │        │
│  │ Testing  │  │ Consent  │  │ Encrypt  │  │ Tiering  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                    │
│  PII HANDLING:                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Classification → Detection → Protection → Monitoring     │    │
│  │                                                          │    │
│  │ Detection: Pattern matching, NLP, column naming rules    │    │
│  │ Protection:                                              │    │
│  │   - Encryption at rest (AES-256) and in transit (TLS)   │    │
│  │   - Column-level encryption (sensitive fields)          │    │
│  │   - Tokenization (replace PII with tokens)              │    │
│  │   - Dynamic masking (mask at query time by role)        │    │
│  │   - Hashing (irreversible, for matching)                │    │
│  │   - k-anonymity / l-diversity / t-closeness             │    │
│  │ Monitoring: Access logs, anomaly detection on PII access│    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ACCESS CONTROL PATTERNS:                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ RBAC: Role → Permissions                                 │    │
│  │   analyst_role → SELECT on analytics.* (no PII columns) │    │
│  │   engineer_role → ALL on staging.*                       │    │
│  │                                                          │    │
│  │ ABAC: Attribute → Permissions                            │    │
│  │   IF user.team = 'finance' AND data.classification       │    │
│  │      = 'FINANCIAL' THEN ALLOW                            │    │
│  │                                                          │    │
│  │ Column-level security:                                   │    │
│  │   CREATE MASKING POLICY pii_mask AS (val STRING)         │    │
│  │   RETURNS STRING ->                                      │    │
│  │     CASE WHEN current_role() IN ('PII_READER')           │    │
│  │       THEN val                                           │    │
│  │       ELSE '***MASKED***'                                │    │
│  │     END;                                                 │    │
│  │                                                          │    │
│  │ Row-level security:                                      │    │
│  │   CREATE ROW ACCESS POLICY region_filter AS (region STR) │    │
│  │   RETURNS BOOLEAN ->                                     │    │
│  │     region = current_user_region();                      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Interview Topics Summary

```
TOP QUESTIONS FROM THIS FILE:

1. Compare Cassandra consistency levels. When would you use QUORUM vs LOCAL_QUORUM?
2. How do you design a Cassandra data model? What are the anti-patterns?
3. Explain Elasticsearch shard sizing. How do you handle reindexing at scale?
4. When would you use Redis vs Memcached in a data pipeline?
5. What is a data contract? How do you enforce it in CI/CD?
6. Name the dimensions of data quality. How do you measure each?
7. What is the difference between data monitoring and data observability?
8. How do you handle schema evolution in a Kafka + Avro pipeline?
9. Compare SCD Type 2 vs Type 4. When would you use each?
10. What is Data Vault 2.0? When does it beat star schema?
11. Explain Data Mesh. What are the 4 pillars?
12. How do you build a data quality scorecard?
13. What is a semantic layer / metrics layer? Why does it matter?
14. How do you handle PII in a data lake? (encryption, masking, tokenization)
15. Walk through a data incident from detection to postmortem.
```
