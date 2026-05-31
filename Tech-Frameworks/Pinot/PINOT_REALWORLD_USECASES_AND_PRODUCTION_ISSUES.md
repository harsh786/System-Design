# Apache Pinot — Real-World Use Cases & Production War Stories

## Who Uses Pinot and Why?

```
┌─────────────────────────────────────────────────────────────────────┐
│  Company        │  Scale                │  Use Case                  │
├─────────────────┼───────────────────────┼────────────────────────────┤
│  LinkedIn       │  100K+ QPS            │  Who Viewed My Profile     │
│  Uber           │  Millions events/sec  │  Real-time pricing/surge   │
│  Stripe         │  Billions txns/day    │  Payment analytics         │
│  Walmart        │  Peak holiday traffic │  Inventory analytics       │
│  Confluent      │  Internal metrics     │  Cloud usage monitoring    │
│  Startree       │  SaaS analytics       │  Multi-tenant OLAP         │
│  Razorpay       │  Millions txns        │  Merchant dashboards       │
└─────────────────┴───────────────────────┴────────────────────────────┘
```

---

## Use Case 1: User-Facing Analytics (LinkedIn "Who Viewed My Profile")

### The Problem

LinkedIn needs to show every user who viewed their profile, with filtering by company, title, time range — in under 100ms at 100K+ QPS.

### Why Not Traditional DBs?

```
PostgreSQL at LinkedIn Scale:
- 900M+ members
- Billions of profile view events per day
- Each user query = complex aggregation
- Result: 5-15 second query latency (unacceptable for UI)

Elasticsearch:
- Good for search, poor for aggregations at this scale
- Expensive memory footprint for high-cardinality data
- Ingestion lag issues during peak hours
```

### How Pinot Solves It

```
Architecture:
┌──────────────┐    ┌───────────┐    ┌─────────────────────────┐
│  Profile View │    │           │    │  Apache Pinot           │
│  Event       │───▶│  Kafka    │───▶│  - Real-time ingestion  │
│  (Kafka)     │    │           │    │  - Star-Tree index on   │
└──────────────┘    └───────────┘    │    (viewer_company,     │
                                     │     viewer_title,       │
                                     │     viewed_profile_id)  │
                                     │  - Sorted index on time │
                                     └───────────┬─────────────┘
                                                 │
                                                 ▼
                                     ┌─────────────────────────┐
                                     │  Query: < 50ms P99      │
                                     │  "Who from Google       │
                                     │   viewed my profile     │
                                     │   this week?"           │
                                     └─────────────────────────┘
```

### Key Design Decisions

1. **Star-Tree Index** on (company, title, time_bucket) → pre-aggregates common query patterns
2. **Sorted Index** on `event_timestamp` → time-range queries are sequential disk reads
3. **Inverted Index** on `viewer_company` → fast filtering without full scan
4. **Retention**: 90 days real-time, older data in offline segments (quarterly batch rebuild)

---

## Use Case 2: Real-Time Surge Pricing (Uber-Style)

### The Problem

Compute supply/demand ratio per geo-cell every 30 seconds to determine surge multiplier. Must handle 10M+ events/minute during peak.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  REAL-TIME PIPELINE                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Driver GPS Pings (10M/min)                                  │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────┐     ┌──────────────┐     ┌───────────────┐    │
│  │  Kafka   │────▶│ Flink (ETL)  │────▶│  Kafka (out)  │    │
│  │  (raw)   │     │  Geo-hash    │     │  (enriched)   │    │
│  └──────────┘     │  assignment  │     └───────┬───────┘    │
│                   └──────────────┘             │             │
│                                                ▼             │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Apache Pinot                                       │     │
│  │  Table: driver_supply                               │     │
│  │  Columns: geo_h3_cell, timestamp, driver_id,        │     │
│  │           is_available, vehicle_type                 │     │
│  │                                                     │     │
│  │  Star-Tree: (geo_h3_cell, vehicle_type, time_5min)  │     │
│  │  → pre-aggregated count of available drivers        │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  Rider Requests (1M/min)                                     │
│       │                                                      │
│       ▼                                                      │
│  Same pipeline → Pinot table: rider_demand                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Query Layer:
  SELECT 
    geo_h3_cell,
    COUNT(*) FILTER (WHERE is_available = true) as supply,
    (SELECT COUNT(*) FROM rider_demand 
     WHERE geo_h3_cell = d.geo_h3_cell 
     AND timestamp > ago('5m')) as demand
  FROM driver_supply d
  WHERE timestamp > ago('5m')
  GROUP BY geo_h3_cell

  → Returns surge_multiplier = demand / supply per cell
  → Latency: < 200ms even at peak
```

### Why Pinot Over Alternatives

| System | Issue at This Scale |
|--------|-------------------|
| Redis | Memory cost for 100M geo-cells × time windows = $$$$ |
| Druid | Higher ingestion latency (seconds, not sub-second) |
| ClickHouse | Single-node bottleneck for this QPS; sharding is manual |
| Pinot | Sub-second ingestion, built-in multi-tenancy, auto-rebalance |

---

## Use Case 3: Merchant Payment Dashboard (Razorpay/Stripe-Style)

### The Problem

100K+ merchants need real-time dashboards showing:
- Transaction volume by payment method
- Success/failure rates
- Settlement status
- Revenue by time period

Each merchant sees ONLY their data (multi-tenant isolation).

### Schema Design

```sql
-- Table: merchant_transactions (REALTIME)
{
  "tableName": "merchant_transactions_REALTIME",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "30",
    "replication": "2"
  },
  "tenantConfig": {
    "broker": "payments_broker",
    "server": "payments_server"
  },
  "tableIndexConfig": {
    "sortedColumn": ["merchant_id"],
    "invertedIndexColumns": ["payment_method", "status", "currency"],
    "starTreeIndexConfigs": [{
      "dimensionsSplitOrder": ["merchant_id", "payment_method", "status"],
      "functionColumnPairs": ["COUNT__*", "SUM__amount_cents"],
      "maxLeafRecords": 10000
    }]
  },
  "streamConfig": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "payment_events",
    "stream.kafka.consumer.type": "lowlevel",
    "realtime.segment.flush.threshold.rows": "500000",
    "realtime.segment.flush.threshold.time": "1h"
  }
}
```

### Multi-Tenant Query Pattern

```sql
-- Every query MUST include merchant_id (enforced by query rewriter)
SELECT 
  payment_method,
  status,
  COUNT(*) as txn_count,
  SUM(amount_cents) / 100.0 as total_amount
FROM merchant_transactions
WHERE merchant_id = 'merchant_abc123'       -- MANDATORY filter
  AND event_timestamp > ago('24h')
GROUP BY payment_method, status
ORDER BY txn_count DESC
LIMIT 10

-- Query latency: < 80ms (Star-Tree answers directly)
```

### Multi-Tenancy Enforcement

```
┌─────────────────────────────────────────────────┐
│  API Gateway                                    │
│  - Extracts merchant_id from JWT token          │
│  - Injects WHERE merchant_id = '...' into query │
│  - Rejects queries without merchant_id filter   │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Pinot Broker (Query Rewriter)                  │
│  - Validates merchant_id is in WHERE clause     │
│  - Star-Tree lookup → skips irrelevant segments │
│  - Sorted index on merchant_id → binary search  │
└─────────────────────────────────────────────────┘
```

---

## Use Case 4: Observability / Metrics Platform

### The Problem

Internal metrics platform ingesting 50B+ data points/day from 10K+ services. Engineers query for:
- P99 latency for service X in last 5 minutes
- Error rate spike detection
- Top-N slow endpoints

### Architecture

```
Services (10K+)
    │
    ▼ (OTEL/StatsD/Prometheus remote write)
┌──────────────┐
│  Collector   │
│  (OTEL)      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌───────────────────────────────────┐
│  Kafka       │────▶│  Pinot                            │
│  (metrics)   │     │                                   │
└──────────────┘     │  Table: service_metrics           │
                     │  - service_name (inverted index)  │
                     │  - endpoint (inverted index)      │
                     │  - latency_ms (range index)       │
                     │  - status_code (inverted index)   │
                     │  - timestamp (sorted)             │
                     │                                   │
                     │  Star-Tree:                       │
                     │  (service, endpoint, status_code) │
                     │  → PERCENTILE, COUNT, SUM, AVG    │
                     └───────────────────────────────────┘
```

### Why Pinot for Metrics (vs Prometheus/M3DB/VictoriaMetrics)

```
Prometheus:
  ✗ Single node, limited retention
  ✗ Pull-based doesn't scale to 10K services
  ✗ No ad-hoc SQL queries across dimensions

M3DB / VictoriaMetrics:
  ✓ Scales better than Prometheus
  ✗ Limited query expressiveness (PromQL only)
  ✗ No joins, no complex GROUP BY

Apache Pinot:
  ✓ SQL queries with arbitrary GROUP BY
  ✓ Star-Tree for instant percentile queries
  ✓ Handles 50B+ data points/day
  ✓ Sorted + Inverted indexes for flexible filtering
  ✓ Multi-tenant (each team sees only their services)
```

---

## Production Issues & War Stories

### Issue 1: Kafka Consumer Lag Causes Data Delay

**Symptoms**:
- Dashboard shows data 5 minutes stale (instead of < 30 seconds)
- Kafka consumer group lag increasing
- No errors in Pinot server logs

**Root Cause**:
```
CONSUMING segment was holding too many rows before sealing.

Configuration:
  realtime.segment.flush.threshold.rows = 5,000,000  ← TOO HIGH
  realtime.segment.flush.threshold.time = 6h         ← TOO HIGH

What happened:
  - Segment accumulated 5M rows over 4 hours
  - During this time, it was building indexes in memory
  - Memory pressure caused GC pauses
  - GC pauses caused Kafka consumer to fall behind
  - Consumer lag snowballed
```

**Fix**:
```json
{
  "realtime.segment.flush.threshold.rows": "500000",
  "realtime.segment.flush.threshold.time": "1h"
}

// Also tuned:
"realtime.segment.flush.autotune.initialRows": "100000"
```

**Prevention**:
- Monitor `pinot.server.consumingSegmentRows` metric
- Alert when consumer lag > 1 minute
- Set conservative flush thresholds (smaller segments = faster sealing)

---

### Issue 2: Segment Skew Causing Hot Servers

**Symptoms**:
- 3 out of 12 servers at 90% CPU while others at 30%
- Query latency P99 spikes on specific partitions
- Uneven segment distribution

**Root Cause**:
```
Problem: Kafka topic had 12 partitions, but data was skewed by merchant_id.
         Top 3 merchants produced 60% of all events.
         Kafka partition assignment (hash of merchant_id) concentrated 
         these merchants on 3 partitions → 3 Pinot servers got 60% of work.

Visualization:
  Partition 0: ███████████████████████░░░░░  (merchant_big_1)
  Partition 1: ███████████████████████░░░░░  (merchant_big_2)  
  Partition 2: ███████████████████████░░░░░  (merchant_big_3)
  Partition 3: ██████░░░░░░░░░░░░░░░░░░░░░
  Partition 4: █████░░░░░░░░░░░░░░░░░░░░░░
  ...
  Partition 11: ████░░░░░░░░░░░░░░░░░░░░░░
```

**Fix**:
```
Option A (Chose this): Increase Kafka partitions to 48, re-key by 
         composite key (merchant_id + event_hour) to spread load.

Option B: Use Pinot's segment assignment strategy with replica groups
         to ensure hot segments are spread across servers.

Option C: Use tiered storage — move hot merchants to dedicated 
         Pinot tenant (server tag: "high_traffic").
```

**Applied Configuration**:
```json
{
  "tenantConfig": {
    "broker": "default_broker",
    "server": "high_traffic_server"    // Dedicated servers for hot tenants
  },
  "instanceAssignmentConfigMap": {
    "CONSUMING": {
      "replicaGroupPartitionConfig": {
        "numReplicaGroups": 3,
        "numInstancesPerReplicaGroup": 4
      }
    }
  }
}
```

---

### Issue 3: OOM During Segment Seal (Memory Explosion)

**Symptoms**:
- Server restarts repeatedly during segment sealing
- OOM killer in kernel logs
- Segments stuck in CONSUMING state after restart

**Root Cause**:
```
During segment seal, Pinot:
1. Builds all indexes (inverted, sorted, star-tree, range) IN MEMORY
2. Compresses columns
3. Writes to disk

For a segment with:
- 5M rows × 50 columns
- High-cardinality columns (user_id with 2M unique values)
- Star-Tree with 5 dimensions

Memory required during seal:
  Raw data:         ~2 GB
  Inverted indexes: ~3 GB (high cardinality)
  Star-Tree:        ~1 GB
  Sorted index:     ~500 MB
  Temporary buffers: ~1 GB
  ─────────────────────────
  Total:            ~7.5 GB for ONE segment seal

  Server heap: 8 GB ← Not enough!
```

**Fix**:
```bash
# 1. Reduce segment size (fewer rows = less memory during seal)
realtime.segment.flush.threshold.rows = 200000   # was 5M

# 2. Increase server heap
JAVA_OPTS="-Xmx16g -Xms16g -XX:MaxDirectMemorySize=8g"

# 3. Use off-heap for consuming segments
pinot.server.instance.realtime.alloc.offheap=true

# 4. Limit star-tree dimensions (fewer = less memory)
starTreeIndexConfigs.maxLeafRecords = 50000      # was 10000
# Higher maxLeafRecords = fewer tree nodes = less memory
```

---

### Issue 4: Query Timeout on High-Cardinality GROUP BY

**Symptoms**:
- Queries with `GROUP BY user_id` timing out at 10s
- Only happens on tables with > 1B rows
- Same query on smaller time ranges works fine

**Root Cause**:
```
Query:
  SELECT user_id, COUNT(*) 
  FROM events 
  WHERE timestamp > ago('30d') 
  GROUP BY user_id 
  ORDER BY COUNT(*) DESC 
  LIMIT 100

Problem:
  - 30 days of data = 500 segments × 12 servers
  - user_id cardinality = 50M unique values
  - Each server computes GROUP BY locally → 50M entries per server
  - Broker merges 12 × 50M intermediate results
  - Broker OOM or timeout during merge
```

**Fix**:
```sql
-- Option 1: Use Star-Tree (if pre-configured for this query pattern)
-- Pre-aggregates eliminate the GROUP BY at query time

-- Option 2: Approximate query with DISTINCTCOUNTHLL
SELECT DISTINCTCOUNTHLL(user_id) as approx_unique_users
FROM events
WHERE timestamp > ago('30d')

-- Option 3: Reduce cardinality with bucketing in schema
-- Instead of raw user_id, use user_id_bucket = hash(user_id) % 10000

-- Option 4: Set query limits
SET queryOptions = 'groupByMode=sql;responseFormat=sql;maxServerResponseSizeBytes=100000000';
SET maxRowsInJoin = 100000;
```

**Broker-level protection**:
```json
{
  "queryConfig": {
    "maxQueryResponseSizeBytes": "100000000",
    "maxServerResponseSizeBytes": "50000000",
    "groupByMaxKeys": "1000000",
    "timeoutMs": "15000"
  }
}
```

---

### Issue 5: Rebalance Storm After Server Failure

**Symptoms**:
- One server crashes (hardware failure)
- Remaining servers suddenly overwhelmed
- Cascading failures across the cluster
- All queries failing with timeout

**Root Cause**:
```
Timeline:
  T+0:    Server-7 dies (held 50 segments)
  T+10s:  Helix detects failure
  T+15s:  Controller starts rebalance → moves 50 segments to other servers
  T+20s:  All 11 remaining servers start downloading segments from deep store
  T+30s:  Network saturated (S3 downloads × 11 servers simultaneously)
  T+45s:  Servers can't serve queries while downloading → timeouts
  T+60s:  Health check failures → more servers marked unhealthy
  T+90s:  Cascade: controller tries to rebalance AGAIN
  T+120s: Cluster is down
```

**Fix (Immediate)**:
```bash
# 1. Pause rebalance
curl -X PUT "http://controller:9000/cluster/configs" \
  -d '{"allowParticipantAutoJoin":"false"}'

# 2. Bring back failed server or add new one

# 3. Resume with throttled rebalance
curl -X POST "http://controller:9000/tables/myTable/rebalance?type=OFFLINE" \
  -d '{
    "minAvailableReplicas": 1,
    "downtime": false,
    "reassignInstances": true,
    "bootstrap": false,
    "bestEfforts": true,
    "externalViewCheckIntervalInMs": 10000,
    "externalViewStabilizationTimeoutInMs": 60000
  }'
```

**Prevention**:
```json
// In table config:
{
  "segmentsConfig": {
    "replication": "3"           // More replicas = survive more failures
  },
  "instanceAssignmentConfigMap": {
    "replicaGroupPartitionConfig": {
      "numReplicaGroups": 3,    // Spread replicas across groups
      "numInstancesPerReplicaGroup": 4
    }
  }
}

// In cluster config:
{
  "controller.segment.download.rateLimit": "50000000",  // 50 MB/s per server
  "controller.rebalance.maxSegmentsToMove": "10"        // Move 10 at a time
}
```

---

### Issue 6: Schema Evolution Breaks Consuming Segments

**Symptoms**:
- Added a new column to schema
- Existing CONSUMING segments throwing `NullPointerException`
- New records failing to be indexed

**Root Cause**:
```
Problem: Schema change (add column) was applied BEFORE reloading table config.

What happened:
1. Schema updated: added "payment_method" column
2. Old CONSUMING segments don't have this column
3. New records from Kafka HAVE the column
4. Mismatch: record has field, segment schema doesn't recognize it
5. Server-side NPE when trying to index the new field

Correct Order:
1. Add column with DEFAULT value to schema
2. Reload table config (propagates to all servers)
3. Wait for current CONSUMING segments to seal
4. New CONSUMING segments have updated schema
5. Then (optional) backfill old offline segments
```

**Fix**:
```bash
# Correct procedure:
# Step 1: Update schema with default
curl -X PUT "http://controller:9000/schemas/myTable" \
  -H "Content-Type: application/json" \
  -d '{
    "schemaName": "myTable",
    "dimensionFieldSpecs": [
      {"name": "payment_method", "dataType": "STRING", "defaultNullValue": "UNKNOWN"}
    ]
  }'

# Step 2: Reload table (propagates schema to servers)
curl -X POST "http://controller:9000/tables/myTable/reload"

# Step 3: Verify consuming segments pick up new schema
curl -X GET "http://controller:9000/tables/myTable/consumingSegmentsInfo"
```

---

## Production Debugging Playbook

### Step 1: Identify the Layer

```
┌────────────────────────────────────────────────────────────┐
│  Symptom                      │  Likely Layer              │
├───────────────────────────────┼────────────────────────────┤
│  All queries slow             │  Broker (overloaded)       │
│  Specific table slow          │  Server (segment issue)    │
│  Data delayed/missing         │  Ingestion (Kafka lag)     │
│  Cluster instability          │  Controller/Helix/ZK       │
│  Intermittent failures        │  Network/Deep Store        │
│  OOM/restarts                 │  Server memory config      │
└───────────────────────────────┴────────────────────────────┘
```

### Step 2: Key Metrics to Check

```bash
# Kafka consumer lag (data freshness)
curl "http://server:8097/metrics" | grep "kafka_consumer_lag"

# Query latency breakdown
curl "http://broker:8099/metrics" | grep "query_execution_time"

# Segment count per server (detect skew)
curl "http://controller:9000/tables/myTable/size?detailed=true"

# Server health
curl "http://server:8097/health"

# Consuming segment info
curl "http://controller:9000/tables/myTable/consumingSegmentsInfo"
```

### Step 3: Common Queries for Debugging

```sql
-- Check segment count and time range per server
SELECT $segmentName, $hostName, 
       MIN(event_timestamp) as earliest,
       MAX(event_timestamp) as latest,
       COUNT(*) as row_count
FROM myTable
GROUP BY $segmentName, $hostName
LIMIT 1000

-- Check for data gaps
SELECT DATETIMECONVERT(event_timestamp, '1:MILLISECONDS:EPOCH', 
       '1:MINUTES:EPOCH', '5:MINUTES') as time_bucket,
       COUNT(*) as events
FROM myTable
WHERE event_timestamp > ago('6h')
GROUP BY time_bucket
ORDER BY time_bucket
-- Look for buckets with 0 or low counts
```

---

## Capacity Planning Guidelines

### Sizing Formula

```
Storage per server = 
  (daily_events × bytes_per_event × retention_days × replication_factor)
  ÷ num_servers
  × 1.3 (overhead for indexes)

Memory per server =
  (num_consuming_segments × segment_memory_footprint)
  + (query_concurrency × avg_query_memory)
  + JVM_overhead

Example:
  100M events/day × 500 bytes × 30 days × 2 replicas = 3 TB total
  ÷ 6 servers = 500 GB storage per server
  × 1.3 = 650 GB per server (with indexes)

  Memory: 4 consuming segments × 2 GB + 100 queries × 50 MB + 4 GB JVM
        = 8 + 5 + 4 = 17 GB → Use 24 GB heap servers
```

### Recommended Starting Configuration

```
Small (< 1B events/day):
  - 3 servers, 16 GB RAM, 500 GB SSD
  - 1 controller, 1 broker
  - Replication: 2

Medium (1-10B events/day):
  - 6-12 servers, 32 GB RAM, 1 TB SSD
  - 2 controllers, 3 brokers
  - Replication: 2-3

Large (> 10B events/day):
  - 20+ servers, 64 GB RAM, 2 TB NVMe
  - 3 controllers, 6+ brokers (auto-scale)
  - Replication: 3
  - Tiered storage (hot: NVMe, cold: S3)
```

---

## Anti-Patterns to Avoid

### 1. Using Pinot as a Transactional Database
```
❌ WRONG:
   - Point lookups by primary key (use Redis/DynamoDB)
   - Frequent single-row updates (use PostgreSQL)
   - Transactions with ACID guarantees (use MySQL)

✅ RIGHT:
   - Aggregations over millions of rows
   - Time-series analytics with GROUP BY
   - User-facing dashboards with sub-second latency
```

### 2. Unbounded Queries Without Filters
```
❌ WRONG:
   SELECT * FROM events                     -- scans ALL segments
   SELECT COUNT(*) FROM events              -- no time filter
   SELECT user_id, COUNT(*) GROUP BY user_id -- 50M groups

✅ RIGHT:
   SELECT * FROM events WHERE ts > ago('1h') LIMIT 100
   SELECT COUNT(*) FROM events WHERE ts > ago('24h')
   SELECT user_id, COUNT(*) GROUP BY user_id 
     WHERE ts > ago('1h') ORDER BY 2 DESC LIMIT 100
```

### 3. Over-Indexing
```
❌ WRONG:
   Inverted index on EVERY column
   Star-Tree with 10 dimensions
   → Result: 3x storage, slow segment sealing, OOM during build

✅ RIGHT:
   Inverted index on columns actually used in WHERE clauses
   Star-Tree with 3-5 most queried dimensions
   → Profile queries first, then add indexes
```

### 4. Ignoring Segment Size Tuning
```
❌ WRONG:
   flush.threshold.rows = 10,000,000    (too large → OOM during seal)
   flush.threshold.rows = 1,000         (too small → millions of segments)

✅ RIGHT:
   flush.threshold.rows = 100,000 - 500,000
   flush.threshold.time = "30m" - "2h"
   Target: segments between 100 MB - 500 MB on disk
```

---

## Summary: When to Use Pinot

| Scenario | Use Pinot? | Alternative |
|----------|-----------|-------------|
| Real-time dashboards (< 200ms) | ✅ YES | — |
| Ad-hoc analytics on streaming data | ✅ YES | — |
| High QPS aggregation queries | ✅ YES | — |
| Time-series metrics at scale | ✅ YES | VictoriaMetrics for simpler |
| User-facing analytics | ✅ YES | — |
| OLTP / transactions | ❌ NO | PostgreSQL, MySQL |
| Point lookups by key | ❌ NO | Redis, DynamoDB |
| Full-text search | ❌ NO | Elasticsearch, OpenSearch |
| Complex JOINs across tables | ⚠️ Limited | Trino, Spark |
| Data with frequent updates | ⚠️ Use upsert | PostgreSQL + CDC → Pinot |
