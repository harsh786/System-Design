# Streaming Databases & Semantic Layer - Deep Dive

## Table of Contents
1. [Streaming Database Paradigm](#1-streaming-database-paradigm)
2. [Materialize](#2-materialize)
3. [RisingWave](#3-risingwave)
4. [Redpanda](#4-redpanda)
5. [dbt Semantic Layer / MetricFlow](#5-dbt-semantic-layer--metricflow)
6. [Cube](#6-cube)
7. [Apache Superset](#7-apache-superset)
8. [Serving Layer Patterns](#8-serving-layer-patterns)
9. [Integration Patterns](#9-integration-patterns)
10. [Decision Frameworks](#10-decision-frameworks)
11. [Production Checklist](#11-production-checklist)

---

## 1. Streaming Database Paradigm

### What Is a Streaming Database?

```
Traditional (Batch):
  Source → ETL (hourly/daily) → Materialized View → Query
  Staleness: minutes to hours
  
Streaming Database:
  Source → Continuous ingestion → Incrementally maintained view → Query
  Staleness: milliseconds to seconds
  
Key Insight: Instead of re-computing the entire query on each request,
maintain the RESULT incrementally as new data arrives.

                Traditional OLAP              Streaming Database
                ─────────────────            ──────────────────
  Query time:   Scan full table              Lookup pre-computed result
  Freshness:    Last ETL run                 Real-time (sub-second)
  Cost:         Per-query compute            Per-update compute
  Best for:     Ad-hoc exploration           Known queries, real-time
```

### Incremental View Maintenance

```sql
-- Example: streaming database maintains this result automatically
CREATE MATERIALIZED VIEW revenue_by_region AS
SELECT 
    region,
    COUNT(*) as order_count,
    SUM(amount) as total_revenue,
    AVG(amount) as avg_order_value
FROM orders
GROUP BY region;

-- When a new row arrives in 'orders':
-- Instead of re-scanning entire table:
--   1. Identify affected group (region)
--   2. Update count: count + 1
--   3. Update sum: sum + new_amount
--   4. Update avg: new_sum / new_count
-- Result: O(1) update instead of O(N) full scan
```

### Streaming DB vs Stream Processor vs OLAP

| Dimension | Streaming DB (Materialize/RisingWave) | Stream Processor (Flink) | OLAP (ClickHouse) |
|-----------|--------------------------------------|--------------------------|---------------------|
| Interface | SQL (PostgreSQL wire protocol) | Java/Python/SQL API | SQL |
| Query model | Pre-defined views (always fresh) | Pre-defined jobs | Ad-hoc queries |
| Freshness | Milliseconds (incremental) | Milliseconds (streaming) | Minutes (batch insert) |
| Ad-hoc queries | Limited (must create view first) | Not designed for this | Excellent |
| Complex joins | Excellent (streaming joins) | Excellent | Good (at query time) |
| State management | Automatic | Manual (state backends) | Automatic (storage) |
| Ops complexity | Low (SQL-only) | High (JVM, state, checkpoints) | Medium |
| Best for | Known queries needing real-time | Complex event processing | Interactive analytics |

---

## 2. Materialize

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Materialize Architecture                        │
│                                                                    │
│  ┌────────────────┐                                               │
│  │  Adapter Layer │ ← PostgreSQL wire protocol (pgclient works!) │
│  │  (pgwire)      │                                               │
│  └───────┬────────┘                                               │
│          │                                                         │
│  ┌───────▼────────────────────────────────────────────────────┐  │
│  │            Compute Layer (Differential Dataflow)             │  │
│  │                                                              │  │
│  │  Timely Dataflow: distributed, parallel streaming engine    │  │
│  │  Differential Dataflow: incremental computation on top      │  │
│  │                                                              │  │
│  │  Key insight: tracks DIFFERENCES (inserts/deletes) and      │  │
│  │  propagates only CHANGES through the dataflow graph         │  │
│  │                                                              │  │
│  │  ┌────────┐    ┌──────────┐    ┌────────────────┐         │  │
│  │  │ Source │───▶│  Filter  │───▶│  Aggregate     │──┐      │  │
│  │  └────────┘    │  /Join   │    │  (incremental) │  │      │  │
│  │                └──────────┘    └────────────────┘  │      │  │
│  │                                                     ▼      │  │
│  │                                              ┌──────────┐  │  │
│  │                                              │  Index   │  │  │
│  │                                              │ (in-mem) │  │  │
│  │                                              └──────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │            Storage Layer (Persist)                           │  │
│  │  • Durable storage of source data and materialized state   │  │
│  │  • S3-backed for cost efficiency                           │  │
│  │  • Enables recovery without re-reading from source         │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### SQL Examples

```sql
-- Create source from Kafka
CREATE SOURCE orders_source
FROM KAFKA CONNECTION kafka_conn (TOPIC 'orders')
FORMAT AVRO USING CONFLUENT SCHEMA REGISTRY CONNECTION csr_conn
ENVELOPE DEBEZIUM;

-- Create source from PostgreSQL CDC
CREATE SOURCE pg_orders
FROM POSTGRES CONNECTION pg_conn (PUBLICATION 'orders_pub')
FOR TABLES (public.orders, public.customers);

-- Multi-stream join (maintained incrementally!)
CREATE MATERIALIZED VIEW enriched_orders AS
SELECT 
    o.order_id,
    o.amount,
    o.status,
    c.name as customer_name,
    c.segment as customer_segment,
    p.name as product_name,
    p.category
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN products p ON o.product_id = p.id
WHERE o.status != 'cancelled';

-- Real-time aggregation with temporal filter
CREATE MATERIALIZED VIEW revenue_last_hour AS
SELECT 
    date_trunc('minute', created_at) as minute,
    region,
    COUNT(*) as orders,
    SUM(amount) as revenue
FROM orders
WHERE mz_now() - created_at < INTERVAL '1 hour'
GROUP BY 1, 2;

-- Sink results to Kafka (for downstream consumers)
CREATE SINK revenue_sink
FROM revenue_last_hour
INTO KAFKA CONNECTION kafka_conn (TOPIC 'revenue-metrics')
FORMAT JSON
ENVELOPE DEBEZIUM;

-- Query with standard PostgreSQL client
-- psql -h materialize-host -p 6875 -U materialize
-- SELECT * FROM enriched_orders WHERE customer_segment = 'enterprise';
-- (sub-millisecond response, always up-to-date!)

-- SUBSCRIBE: push changes to client
SUBSCRIBE enriched_orders WITH (PROGRESS);
-- Returns a stream of (timestamp, diff, columns) as view updates
```

---

## 3. RisingWave

### Architecture (Cloud-Native, Disaggregated)

```
┌──────────────────────────────────────────────────────────────────┐
│                    RisingWave Architecture                         │
│                                                                    │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  Frontend  │  │     Meta     │  │       Compute             │ │
│  │  (SQL)     │  │  (Catalog +  │  │                           │ │
│  │            │  │  Scheduling) │  │  ┌─────────┐ ┌─────────┐ │ │
│  │  • Parser  │  │              │  │  │Streaming│ │  Batch   │ │ │
│  │  • Planner │  │  • Catalog   │  │  │ Actors  │ │  Query   │ │ │
│  │  • PG wire │  │  • Barrier   │  │  │         │ │  Engine  │ │ │
│  │            │  │    mgmt      │  │  └─────────┘ └─────────┘ │ │
│  └────────────┘  └──────────────┘  └─────────────┬────────────┘ │
│                                                    │              │
│                                          ┌─────────▼─────────┐   │
│                                          │    Compactor       │   │
│                                          │ (LSM compaction)   │   │
│                                          └─────────┬─────────┘   │
│                                                    │              │
│                                          ┌─────────▼─────────┐   │
│                                          │   Object Storage   │   │
│                                          │   (S3 / MinIO)     │   │
│                                          │                     │   │
│                                          │   Hummock: custom  │   │
│                                          │   LSM-tree on S3   │   │
│                                          └───────────────────┘   │
└──────────────────────────────────────────────────────────────────┘

Key Design Decisions:
• Disaggregated compute/storage (scale independently)
• State stored in S3 via Hummock (cost-efficient, durable)
• Barrier-based checkpointing (similar to Flink)
• PostgreSQL-compatible SQL interface
```

### SQL Examples

```sql
-- Source from Kafka
CREATE SOURCE kafka_orders (
    order_id INT,
    customer_id INT,
    amount DECIMAL,
    status VARCHAR,
    event_time TIMESTAMP
) WITH (
    connector = 'kafka',
    topic = 'orders',
    properties.bootstrap.server = 'kafka:9092',
    scan.startup.mode = 'earliest'
) FORMAT PLAIN ENCODE JSON;

-- Materialized view with streaming join
CREATE MATERIALIZED VIEW order_summary AS
SELECT 
    o.customer_id,
    c.name,
    c.segment,
    COUNT(*) as total_orders,
    SUM(o.amount) as total_spent,
    MAX(o.event_time) as last_order
FROM kafka_orders o
JOIN customers c ON o.customer_id = c.id
GROUP BY o.customer_id, c.name, c.segment;

-- Temporal join (point-in-time lookup)
CREATE MATERIALIZED VIEW enriched_events AS
SELECT 
    e.*,
    r.exchange_rate
FROM events e
JOIN exchange_rates FOR SYSTEM_TIME AS OF e.event_time r
ON e.currency = r.currency;

-- Sink to Iceberg (lake materialization!)
CREATE SINK orders_to_iceberg AS
SELECT * FROM order_summary
WITH (
    connector = 'iceberg',
    type = 'upsert',
    primary_key = 'customer_id',
    catalog.type = 'storage',
    warehouse.path = 's3://lake/iceberg/',
    database.name = 'analytics',
    table.name = 'order_summary'
);

-- Sink to Kafka (for downstream streaming)
CREATE SINK revenue_events AS
SELECT customer_id, total_spent, segment
FROM order_summary
WHERE total_spent > 10000
WITH (
    connector = 'kafka',
    topic = 'high-value-customers',
    properties.bootstrap.server = 'kafka:9092'
) FORMAT PLAIN ENCODE JSON;
```

### RisingWave vs Flink SQL

| Dimension | RisingWave | Flink SQL |
|-----------|-----------|-----------|
| Deployment | Single binary, K8s native | Complex (JM + TMs + ZK/K8s) |
| State storage | S3 (Hummock, cheap) | RocksDB (local SSD, expensive) |
| SQL compatibility | PostgreSQL dialect | ANSI SQL with extensions |
| Ease of use | `CREATE MATERIALIZED VIEW` done | Job deployment, savepoints, configs |
| Sinks | Kafka, JDBC, Iceberg, Delta, ES | Any Flink connector |
| Batch queries | Yes (on materialized state) | Separate batch mode |
| Performance | Good for SQL workloads | Better for complex custom logic |
| UDFs | Limited (Python, SQL) | Full Java/Python UDFs |
| Ecosystem | Growing | Massive |
| Cost at scale | Lower (S3 state) | Higher (SSD state) |
| Best for | SQL-heavy streaming ETL | Complex event processing, custom logic |

---

## 4. Redpanda

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Redpanda Architecture                           │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Single Binary (C++)                         │  │
│  │                                                              │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │         Seastar Framework (thread-per-core)          │   │  │
│  │  │                                                       │   │  │
│  │  │  Core 0: Partition 1, 4, 7    ← Each core owns      │   │  │
│  │  │  Core 1: Partition 2, 5, 8      specific partitions  │   │  │
│  │  │  Core 2: Partition 3, 6, 9    ← No locks between    │   │  │
│  │  │  ...                            cores (shared-nothing)│   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │                                                              │  │
│  │  ┌───────────────┐  ┌────────────────┐  ┌──────────────┐ │  │
│  │  │ Raft Consensus│  │ Schema Registry│  │  HTTP Admin  │ │  │
│  │  │ (replaces ZK) │  │ (built-in)     │  │  API         │ │  │
│  │  └───────────────┘  └────────────────┘  └──────────────┘ │  │
│  │                                                              │  │
│  │  ┌───────────────────────────────────────────────────────┐ │  │
│  │  │          Tiered Storage (S3 offload)                   │ │  │
│  │  │  Hot: local NVMe/SSD    Cold: S3 (automatic)         │ │  │
│  │  └───────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  NO JVM • NO ZooKeeper • NO separate controller                  │
│  Kafka wire-compatible (all Kafka clients work unchanged)         │
└──────────────────────────────────────────────────────────────────┘
```

### Key Differentiators

| Feature | Redpanda | Apache Kafka |
|---------|----------|--------------|
| Language | C++ (Seastar) | Java/Scala (JVM) |
| Coordination | Built-in Raft | ZooKeeper → KRaft migration |
| Latency (p99) | < 10ms | 30-100ms typical |
| Throughput | Comparable or better | Well-established |
| Schema Registry | Built-in | Confluent Schema Registry (separate) |
| Admin UI | Built-in (Redpanda Console) | Separate tools (Kafka UI, AKHQ) |
| Tiered Storage | Native S3 integration | KIP-405 (newer, less mature) |
| Wasm transforms | In-broker data transforms | Not available (need Connect/Streams) |
| Binary size | ~50MB single binary | JVM + many JARs |
| Memory model | Fixed (no GC pauses) | JVM GC tuning required |
| Wire protocol | Kafka-compatible | Native Kafka |
| Ecosystem | Uses Kafka ecosystem | Native Kafka ecosystem |
| Community | Smaller, growing | Massive |
| Enterprise | Commercial features | Confluent commercial |

### Migration from Kafka to Redpanda

```
Step 1: Deploy Redpanda cluster alongside Kafka
Step 2: Configure MirrorMaker 2 (or Redpanda's built-in) to replicate topics
Step 3: Switch producers to Redpanda (same client config, different bootstrap servers)
Step 4: Wait for consumers to catch up on Kafka
Step 5: Switch consumers to Redpanda
Step 6: Decommission Kafka cluster

# Client config change (only bootstrap.servers changes):
# Before: bootstrap.servers=kafka-1:9092,kafka-2:9092,kafka-3:9092
# After:  bootstrap.servers=redpanda-1:9092,redpanda-2:9092,redpanda-3:9092
# Everything else (serializers, configs, consumer groups) stays the same!
```

### Redpanda Connect (Benthos-Based)

```yaml
# redpanda-connect.yaml - declarative data pipelines
input:
  kafka:
    addresses: [redpanda:9092]
    topics: [raw-events]
    consumer_group: transform-pipeline

pipeline:
  processors:
    - mapping: |
        root.event_id = this.id
        root.timestamp = this.ts.ts_parse("2006-01-02T15:04:05Z")
        root.amount = this.amount.number()
        root.enriched = true
    
    - branch:
        request_map: 'root = this.customer_id'
        processors:
          - http:
              url: http://customer-service/api/customers/${!this}
              verb: GET
        result_map: 'root.customer_name = this.name'

output:
  kafka:
    addresses: [redpanda:9092]
    topic: enriched-events
```

---

## 5. dbt Semantic Layer / MetricFlow

### What Problem It Solves

```
Without semantic layer:
  • Team A defines revenue = SUM(amount) WHERE status = 'completed'
  • Team B defines revenue = SUM(amount) WHERE status IN ('completed', 'shipped')
  • Dashboard shows different numbers → trust erodes
  
With semantic layer:
  • ONE definition of "revenue" in code
  • All consumers (BI tools, APIs, notebooks) get same number
  • Changes are versioned and reviewed (PR-based)
```

### MetricFlow YAML Definition

```yaml
# models/semantic/orders_semantic.yml
semantic_models:
  - name: orders
    description: "Order events fact table"
    model: ref('fct_orders')
    
    defaults:
      agg_time_dimension: order_date
    
    entities:
      - name: order_id
        type: primary
      - name: customer_id
        type: foreign
      - name: product_id
        type: foreign
    
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
      - name: status
        type: categorical
      - name: region
        type: categorical
      - name: channel
        type: categorical
        expr: acquisition_channel
    
    measures:
      - name: order_count
        agg: count
        expr: order_id
      - name: revenue
        agg: sum
        expr: amount
        description: "Total revenue from completed orders"
      - name: avg_order_value
        agg: average
        expr: amount
      - name: unique_customers
        agg: count_distinct
        expr: customer_id

# models/semantic/metrics.yml
metrics:
  - name: revenue
    type: simple
    label: "Total Revenue"
    type_params:
      measure: revenue
    filter: |
      {{ Dimension('status') }} = 'completed'
  
  - name: revenue_growth
    type: derived
    label: "Revenue Growth Rate"
    type_params:
      expr: (current_revenue - previous_revenue) / previous_revenue
      metrics:
        - name: current_revenue
          offset_window: 0
        - name: previous_revenue
          offset_window: 1
          offset_to_grain: month
  
  - name: cumulative_revenue
    type: cumulative
    label: "Cumulative Revenue (MTD)"
    type_params:
      measure: revenue
      window: 1 month
      grain_to_date: month
  
  - name: conversion_rate
    type: conversion
    label: "Purchase Conversion Rate"
    type_params:
      entity: customer_id
      calculation: conversions / base
      base_measure: visits
      conversion_measure: purchases
      window: 7 days
```

### Querying the Semantic Layer

```python
# Python SDK (dbt Cloud)
from dbtsl import SemanticLayerClient

client = SemanticLayerClient(
    environment_id=123,
    auth_token="dbt_cloud_token"
)

# Query metrics with dimensions and filters
result = client.query(
    metrics=["revenue", "order_count"],
    group_by=["metric_time__month", "region"],
    where=["{{ Dimension('channel') }} = 'organic'"],
    order_by=["-metric_time__month"],
    limit=100
)

# Available via JDBC (any BI tool can connect)
# jdbc:arrow-flight-sql://semantic-layer.cloud.getdbt.com:443?token=xxx

# GraphQL API
# POST https://semantic-layer.cloud.getdbt.com/api/graphql
# { query { metrics(environmentId: 123) { name, description, type } } }
```

---

## 6. Cube

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Cube Architecture                            │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    API Layer                                 │  │
│  │  REST API │ GraphQL API │ SQL API (PG wire protocol)       │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                     │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Query Orchestrator                              │  │
│  │  • Query planning (which pre-agg to use)                   │  │
│  │  • Cache management                                         │  │
│  │  • Multi-tenancy routing                                    │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                     │
│         ┌────────────────────┼────────────────────┐               │
│         ▼                    ▼                    ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Pre-Agg     │  │  Cube Store  │  │  Source Database      │  │
│  │  (cached     │  │  (Rust OLAP  │  │  (Redshift, PG,      │  │
│  │   results)   │  │   engine)    │  │   ClickHouse, etc.)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Data Model

```javascript
// schema/Orders.js
cube(`Orders`, {
  sql_table: `silver.orders`,
  
  joins: {
    Customers: {
      relationship: `many_to_one`,
      sql: `${CUBE}.customer_id = ${Customers}.id`
    }
  },
  
  measures: {
    count: { type: `count` },
    revenue: { 
      type: `sum`, 
      sql: `amount`,
      format: `currency`
    },
    avgOrderValue: { 
      type: `avg`, 
      sql: `amount` 
    },
    uniqueCustomers: {
      type: `count_distinct`,
      sql: `customer_id`
    }
  },
  
  dimensions: {
    status: { type: `string`, sql: `status` },
    region: { type: `string`, sql: `region` },
    createdAt: { type: `time`, sql: `created_at` }
  },
  
  segments: {
    completed: { sql: `${CUBE}.status = 'completed'` },
    highValue: { sql: `${CUBE}.amount > 1000` }
  },
  
  // Pre-aggregations (the magic for performance)
  preAggregations: {
    // Daily rollup (refreshes every hour)
    dailyRevenue: {
      measures: [revenue, count, uniqueCustomers],
      dimensions: [region, status],
      timeDimension: createdAt,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`
      },
      buildRangeStart: { sql: `SELECT DATE_SUB(NOW(), INTERVAL 1 YEAR)` },
      buildRangeEnd: { sql: `SELECT NOW()` }
    },
    
    // Hourly for real-time dashboard
    hourlyRevenue: {
      measures: [revenue, count],
      timeDimension: createdAt,
      granularity: `hour`,
      refreshKey: { every: `5 minute` }
    }
  }
});
```

---

## 7. Apache Superset

### Architecture and Deployment

```yaml
# Helm values for production Superset on K8s
supersetNode:
  replicaCount: 3
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
  connections:
    db_host: postgres.internal
    db_name: superset
    redis_host: redis.internal

supersetWorker:
  replicaCount: 4  # Celery workers for async queries
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"

# Security: Row-Level Security
# In Superset, RLS policies can filter data per user/role:
# Role: "US Analyst" → Filter: region = 'US' on all datasets
# Role: "EMEA Analyst" → Filter: region IN ('UK', 'DE', 'FR')

# Embedding (for internal apps):
# Superset supports iframe embedding with guest tokens
# POST /api/v1/security/guest_token/
# { "user": {...}, "resources": [{"type": "dashboard", "id": "..."}], "rls": [...] }
```

### Superset vs Metabase vs Tableau

| Dimension | Superset | Metabase | Tableau |
|-----------|----------|----------|---------|
| Cost | Free (OSS) | Free (OSS) / paid | $$$$ (commercial) |
| SQL support | Full SQL Lab | Question builder + SQL | Visual + custom SQL |
| Databases | 50+ (SQLAlchemy) | 20+ | Many (native connectors) |
| Viz types | 50+ chart types | 15+ | 100+ |
| Row-level security | Yes (built-in) | Sandboxing (limited) | Yes (row-level) |
| Embedding | Guest tokens, iframe | Static embedding (paid) | Embedded analytics |
| Semantic layer | External (Cube, dbt) | Limited (models) | Proprietary |
| Self-hosted | Easy (Docker/K8s) | Easy (Docker/K8s) | Complex |
| Best for | Data eng teams, SQL-heavy | Business users, simple | Enterprise BI, exec dashboards |

---

## 8. Serving Layer Patterns

### Pattern Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                  Serving Layer Patterns                       │
├────────────────────┬─────────────────┬──────────────────────┤
│  OLAP Cube         │  Headless BI    │  Embedded Analytics  │
│  (Pre-computed)    │  (API-first)    │  (In-app)            │
├────────────────────┼─────────────────┼──────────────────────┤
│  Cube pre-aggs     │  Cube/dbt API   │  Superset iframe     │
│  ClickHouse MV     │  GraphQL/REST   │  Custom React charts │
│  Redshift MV       │  JDBC endpoint  │  Embedded dashboards │
├────────────────────┼─────────────────┼──────────────────────┤
│  Fastest queries   │  Flexible,      │  Product feature     │
│  Fixed dimensions  │  programmatic   │  (not just internal) │
│  Internal BI       │  Multi-consumer │  Customer-facing     │
└────────────────────┴─────────────────┴──────────────────────┘
```

### Caching Strategy

```
Layer 1: Result Cache (Redis/Memcached)
  • Cache full query results
  • TTL based on data freshness requirements
  • Key: hash(query + parameters + user_context)

Layer 2: Pre-Aggregation (Cube Store / Materialized Views)
  • Pre-compute rollups at various granularities
  • Refresh periodically (every N minutes)
  • Query planner selects appropriate pre-agg

Layer 3: Query Cache (database-level)
  • Redshift result caching
  • ClickHouse query cache
  • Automatic invalidation on data change

Layer 4: CDN (for embedded analytics)
  • Cache static dashboard renders
  • Edge-compute for global users
```

---

## 9. Integration Patterns

### End-to-End: CDC → Streaming DB → Semantic → BI

```
┌─────────┐    ┌─────────┐    ┌──────────────┐    ┌──────┐    ┌────────┐
│ Source  │───▶│ Kafka   │───▶│ RisingWave/  │───▶│ Cube │───▶│Superset│
│ DB (PG) │CDC │(Redpanda)│    │ Materialize  │    │ API  │    │        │
└─────────┘    └─────────┘    │              │    └──────┘    └────────┘
                               │ Materialized │
                               │ Views (SQL)  │         ┌────────┐
                               └──────────────┘    ────▶│ React  │
                                                        │ App    │
                                                        └────────┘

Data flow:
1. PostgreSQL changes captured via CDC (Debezium or native)
2. Events flow through Kafka/Redpanda
3. Streaming DB maintains real-time materialized views
4. Cube provides semantic layer + caching + API
5. Superset/React apps consume via Cube API
6. Result: sub-second fresh data in dashboards
```

---

## 10. Decision Frameworks

### Streaming Database Selection

```
Need real-time materialized views?
├── Yes → Complex multi-way streaming joins?
│   ├── Yes → Materialize (differential dataflow excels at joins)
│   └── No → Cloud-native, cost-sensitive?
│       ├── Yes → RisingWave (S3 state, cheaper)
│       └── No → Materialize (simpler ops if budget allows)
│
Need Kafka alternative (message broker)?
├── Yes → Redpanda (simpler ops, lower latency, Kafka-compatible)
│
Need semantic layer?
├── Yes → dbt team? → dbt Semantic Layer / MetricFlow
│         Non-dbt? → Cube (more flexible, self-hosted)
│
Need BI/visualization?
├── Yes → Budget? → Superset (free, powerful)
│                 → Metabase (simpler, business-friendly)
```

---

## 11. Production Checklist

### Streaming Databases
- [ ] State size monitored (Materialize memory / RisingWave S3 usage)
- [ ] Checkpoint interval tuned (RisingWave: barrier interval)
- [ ] Source lag monitored (time behind Kafka head)
- [ ] Materialized view refresh time tracked
- [ ] Query latency SLOs defined and monitored
- [ ] Cluster scaling policy defined

### Redpanda
- [ ] Tiered storage configured for long-retention topics
- [ ] Consumer lag monitored (same as Kafka)
- [ ] Schema Registry enabled and compatibility mode set
- [ ] Rack awareness configured for HA
- [ ] Benchmark: validate throughput meets requirements
- [ ] Migration plan from Kafka documented (if applicable)

### Semantic Layer
- [ ] All business metrics defined in code (single source of truth)
- [ ] Metric definitions reviewed by stakeholders
- [ ] Cache refresh schedule aligned with SLAs
- [ ] Access control per metric/dimension
- [ ] BI tools connected via supported integration
- [ ] Metric versioning and deprecation process defined

### BI / Superset
- [ ] Row-level security configured per role
- [ ] Async query enabled for expensive queries
- [ ] Result caching configured (Redis backend)
- [ ] Dashboard refresh rates set appropriately
- [ ] Embedding tokens rotated regularly
- [ ] Database connection pooling tuned
