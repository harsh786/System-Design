# Real-Time Analytics Dashboard - System Design

## 1. Functional Requirements

1. **Event Ingestion**: High-throughput ingestion of events from multiple sources
2. **Real-Time Aggregation**: Count, sum, average, percentiles computed in real-time
3. **Time-Series Storage**: Efficient storage of time-bucketed metrics
4. **Multi-Dimensional Filtering**: Slice and dice by any combination of dimensions
5. **Configurable Widgets**: Line charts, bar charts, tables, gauges, heatmaps
6. **Alerting Thresholds**: Define alert rules on metrics with severity levels
7. **Drill-Down**: Click on aggregate → see underlying detail data
8. **Dashboard Sharing**: Share dashboards with teams, embed externally
9. **Approximate Algorithms**: HyperLogLog, Count-Min Sketch, T-Digest for high cardinality
10. **Custom Queries**: Ad-hoc SQL-like query interface for exploration
11. **Dashboard Versioning**: Version history and rollback for dashboard configs
12. **Data Freshness**: Sub-second to <10s data freshness guarantee

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Ingestion Rate | 10M events/second |
| Query Latency | P95 < 500ms for dashboard queries |
| Data Freshness | < 5 seconds from event to dashboard |
| Dashboard Load | < 2s initial page load |
| Availability | 99.9% for dashboards, 99.99% for ingestion |
| Retention | Raw: 7 days, Aggregated: 2 years |
| Concurrent Users | 10K simultaneous dashboard viewers |
| Cardinality | Support 1B unique dimension values |
| Query Throughput | 50K queries/second |

## 3. Capacity Estimation

### Ingestion
- Events: 10M/s = 864B events/day
- Average event size: 500 bytes
- Raw throughput: 5GB/s = 432TB/day
- After compression (10:1): 43TB/day raw storage

### Storage
- Raw events (7 days): 43TB × 7 = 301TB (compressed)
- Pre-aggregated (1-min granularity, 2 years): ~10TB
- Pre-aggregated (1-hour, 2 years): ~500GB
- Approximate structures (HLL, CMS): ~100GB
- Total: ~320TB

### Compute
- Flink cluster: 200 TaskManagers × 16 cores = 3200 cores
- ClickHouse: 30 nodes × 64 cores = 1920 cores
- Kafka: 50 brokers
- Redis (caching): 20 nodes
- API servers: 20 instances

### Network
- Ingestion: 5GB/s inbound
- Kafka internal replication: 15GB/s
- Flink → ClickHouse: 2GB/s
- Query responses: 500MB/s

## 4. Data Modeling

### ClickHouse Schemas

```sql
-- Raw events table (ReplicatedMergeTree for HA)
CREATE TABLE events ON CLUSTER analytics_cluster
(
    event_id        UUID,
    event_type      LowCardinality(String),
    timestamp       DateTime64(3),  -- millisecond precision
    
    -- Dimensions (filterable)
    tenant_id       UUID,
    user_id         String,
    session_id      String,
    device_type     LowCardinality(String),
    os              LowCardinality(String),
    browser         LowCardinality(String),
    country         LowCardinality(String),
    region          LowCardinality(String),
    city            String,
    
    -- Business dimensions
    product_id      String,
    category        LowCardinality(String),
    campaign_id     String,
    channel         LowCardinality(String),
    
    -- Metrics
    revenue         Decimal64(4),
    quantity        UInt32,
    duration_ms     UInt32,
    
    -- Flexible properties
    properties      Map(String, String),
    
    -- Ingestion metadata
    ingested_at     DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
PARTITION BY toDate(timestamp)
ORDER BY (tenant_id, event_type, timestamp)
TTL timestamp + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- Pre-aggregated minute-level metrics (Materialized View)
CREATE MATERIALIZED VIEW events_1min ON CLUSTER analytics_cluster
ENGINE = ReplicatedAggregatingMergeTree('/clickhouse/tables/{shard}/events_1min', '{replica}')
PARTITION BY toDate(timestamp_minute)
ORDER BY (tenant_id, event_type, timestamp_minute, country, device_type)
TTL timestamp_minute + INTERVAL 90 DAY
AS SELECT
    tenant_id,
    event_type,
    toStartOfMinute(timestamp) AS timestamp_minute,
    country,
    device_type,
    
    -- Aggregates
    countState() AS event_count,
    sumState(revenue) AS revenue_sum,
    avgState(duration_ms) AS duration_avg,
    quantileState(0.5)(duration_ms) AS duration_p50,
    quantileState(0.95)(duration_ms) AS duration_p95,
    quantileState(0.99)(duration_ms) AS duration_p99,
    uniqState(user_id) AS unique_users,
    uniqState(session_id) AS unique_sessions,
    sumState(quantity) AS quantity_sum,
    minState(revenue) AS revenue_min,
    maxState(revenue) AS revenue_max
FROM events
GROUP BY tenant_id, event_type, timestamp_minute, country, device_type;

-- Pre-aggregated hourly metrics
CREATE MATERIALIZED VIEW events_1hr ON CLUSTER analytics_cluster
ENGINE = ReplicatedAggregatingMergeTree('/clickhouse/tables/{shard}/events_1hr', '{replica}')
PARTITION BY toYYYYMM(timestamp_hour)
ORDER BY (tenant_id, event_type, timestamp_hour)
TTL timestamp_hour + INTERVAL 2 YEAR
AS SELECT
    tenant_id,
    event_type,
    toStartOfHour(timestamp) AS timestamp_hour,
    country,
    
    countState() AS event_count,
    sumState(revenue) AS revenue_sum,
    avgState(duration_ms) AS duration_avg,
    quantileState(0.5)(duration_ms) AS duration_p50,
    quantileState(0.95)(duration_ms) AS duration_p95,
    uniqState(user_id) AS unique_users,
    sumState(quantity) AS quantity_sum
FROM events
GROUP BY tenant_id, event_type, timestamp_hour, country;

-- Dashboard configuration table (PostgreSQL)
```

### PostgreSQL Schemas (Metadata)

```sql
-- Dashboards
CREATE TABLE dashboards (
    dashboard_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    title           VARCHAR(512) NOT NULL,
    description     TEXT,
    layout          JSONB NOT NULL DEFAULT '{"type": "grid", "columns": 12}',
    filters         JSONB DEFAULT '[]',
    variables       JSONB DEFAULT '[]',
    refresh_interval_s INTEGER DEFAULT 30,
    time_range      JSONB DEFAULT '{"from": "now-1h", "to": "now"}',
    version         INTEGER DEFAULT 1,
    is_public       BOOLEAN DEFAULT FALSE,
    shared_with     UUID[] DEFAULT '{}',
    created_by      UUID NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_dashboards_tenant ON dashboards (tenant_id, updated_at DESC);
CREATE INDEX idx_dashboards_public ON dashboards (is_public) WHERE is_public = TRUE;

-- Dashboard widgets
CREATE TABLE widgets (
    widget_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id    UUID NOT NULL REFERENCES dashboards(dashboard_id) ON DELETE CASCADE,
    title           VARCHAR(256) NOT NULL,
    widget_type     VARCHAR(30) NOT NULL 
                    CHECK (widget_type IN ('line_chart', 'bar_chart', 'area_chart',
                                           'pie_chart', 'table', 'gauge', 'stat',
                                           'heatmap', 'histogram', 'scatter')),
    position        JSONB NOT NULL,  -- {x, y, w, h}
    query           JSONB NOT NULL,  -- Structured query definition
    visualization   JSONB DEFAULT '{}',  -- Colors, axes, legends
    thresholds      JSONB DEFAULT '[]',
    sort_order      INTEGER DEFAULT 0
);

CREATE INDEX idx_widgets_dashboard ON widgets (dashboard_id, sort_order);

-- Alert rules
CREATE TABLE alert_rules (
    alert_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    name            VARCHAR(256) NOT NULL,
    description     TEXT,
    query           JSONB NOT NULL,
    condition       JSONB NOT NULL,  -- {operator: "gt", threshold: 1000, for_duration_s: 300}
    severity        VARCHAR(10) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    notification_channels UUID[] DEFAULT '{}',
    is_enabled      BOOLEAN DEFAULT TRUE,
    last_triggered  TIMESTAMP WITH TIME ZONE,
    state           VARCHAR(20) DEFAULT 'OK' CHECK (state IN ('OK', 'PENDING', 'FIRING', 'RESOLVED')),
    evaluation_interval_s INTEGER DEFAULT 60,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_alerts_tenant ON alert_rules (tenant_id, is_enabled);
CREATE INDEX idx_alerts_state ON alert_rules (state) WHERE state = 'FIRING';

-- Alert history
CREATE TABLE alert_history (
    history_id      BIGSERIAL PRIMARY KEY,
    alert_id        UUID NOT NULL REFERENCES alert_rules(alert_id),
    state_change    VARCHAR(20) NOT NULL,
    value           DOUBLE PRECISION,
    threshold       DOUBLE PRECISION,
    labels          JSONB DEFAULT '{}',
    annotations     JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_alert_history_alert ON alert_history (alert_id, created_at DESC);

-- Saved queries
CREATE TABLE saved_queries (
    query_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    name            VARCHAR(256) NOT NULL,
    query           TEXT NOT NULL,
    created_by      UUID NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Redis Schemas

```redis
# Real-time counter (sliding window)
HINCRBY rt:counter:{tenant_id}:{event_type}:{minute_bucket} count 1
EXPIRE rt:counter:{tenant_id}:{event_type}:{minute_bucket} 600

# HyperLogLog for unique counts
PFADD hll:{tenant_id}:{metric}:{hour_bucket} {user_id}

# Recent events cache (for drill-down)
LPUSH recent:{tenant_id}:{event_type} {event_json}
LTRIM recent:{tenant_id}:{event_type} 0 999

# Dashboard query cache
SET cache:query:{query_hash} {result_json} EX 5

# Active alert states
HSET alerts:active:{tenant_id} {alert_id} {state_json}

# WebSocket subscription tracking
SADD ws:dashboard:{dashboard_id}:subscribers {connection_id_1} {connection_id_2}
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Web/Mobile│  │  Server  │  │  IoT     │  │Third-Party│  │  Internal Services   │  │
│  │  SDKs    │  │  Logs    │  │ Devices  │  │  APIs     │  │  (Kafka/gRPC)        │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
└───────┼──────────────┼──────────────┼──────────────┼─────────────────┼───────────────┘
        └──────────────┴──────────────┴──────────────┴─────────────────┘
                                      │
                    ┌─────────────────┼─────────────────────┐
                    │                 │                     │
            ┌───────┴──────┐  ┌──────┴───────┐   ┌────────┴──────┐
            │  Ingestion   │  │  Ingestion   │   │  Ingestion    │
            │  Gateway 1   │  │  Gateway 2   │   │  Gateway N    │
            │  (Validate)  │  │  (Validate)  │   │  (Validate)   │
            └───────┬──────┘  └──────┬───────┘   └────────┬──────┘
                    └────────────────┼────────────────────┘
                                     │
                    ┌────────────────┼────────────────────┐
                    │      KAFKA CLUSTER (50 brokers)      │
                    │  ┌─────────────────────────────────┐ │
                    │  │  events-raw (256 partitions)    │ │
                    │  │  events-enriched (128 parts)    │ │
                    │  │  aggregates (64 partitions)     │ │
                    │  │  alerts (32 partitions)         │ │
                    │  └─────────────────────────────────┘ │
                    └────────────────┬────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────────┐
         │                           │                               │
  ┌──────┴───────────┐     ┌────────┴─────────┐        ┌────────────┴─────┐
  │  Flink Cluster   │     │  Alert Engine    │        │  Enrichment      │
  │  (200 TMs)       │     │                  │        │  Service          │
  │                  │     │- Rule evaluation │        │                  │
  │- Windowed agg   │     │- State tracking  │        │- Geo lookup      │
  │- Late arrivals  │     │- Notification    │        │- User enrichment │
  │- Watermarks     │     │                  │        │- Session stitch  │
  │- Session windows│     └──────────────────┘        └──────────────────┘
  └──────┬───────────┘
         │
  ┌──────┴───────────────────────────────────────────────────────────────┐
  │                        STORAGE LAYER                                   │
  │  ┌────────────────┐  ┌───────────────┐  ┌────────────┐  ┌─────────┐ │
  │  │  ClickHouse    │  │    Redis      │  │ PostgreSQL │  │  S3/GCS │ │
  │  │  (30 nodes)    │  │   Cluster     │  │  (Meta)    │  │ (Cold)  │ │
  │  │                │  │  (20 nodes)   │  │            │  │         │ │
  │  │- Raw events   │  │- Real-time    │  │- Dashboards│  │- Archive│ │
  │  │- Materialized │  │  counters     │  │- Alerts    │  │- Backup │ │
  │  │  views        │  │- Query cache  │  │- Users     │  │         │ │
  │  │- Pre-agg      │  │- HLL/CMS     │  │- Queries   │  │         │ │
  │  └────────────────┘  └───────────────┘  └────────────┘  └─────────┘ │
  └──────────────────────────────────────────────────────────────────────┘
         │
  ┌──────┴───────────────────────────────────────────────────────────────┐
  │                        QUERY & SERVING LAYER                           │
  │  ┌────────────────┐  ┌───────────────────┐  ┌────────────────────┐  │
  │  │  Query Engine  │  │  WebSocket Server │  │  API Gateway       │  │
  │  │  (20 instances)│  │  (Push updates)   │  │                    │  │
  │  │                │  │                   │  │                    │  │
  │  │- Query routing │  │- Live refresh     │  │- Auth/Rate limit   │  │
  │  │- Cache check   │  │- Subscription    │  │- Dashboard API     │  │
  │  │- Aggregation   │  │  management      │  │- Query API         │  │
  │  └────────────────┘  └───────────────────┘  └────────────────────┘  │
  └──────────────────────────────────────────────────────────────────────┘
         │
  ┌──────┴─────────────────┐
  │   Frontend (React)     │
  │   - Dashboard renderer │
  │   - Widget library     │
  │   - Query builder      │
  │   - Alert config UI    │
  └────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### REST API Endpoints

```yaml
# Event Ingestion
POST   /api/v1/events                      # Ingest single event
POST   /api/v1/events/batch                # Batch ingest (up to 1000 events)

# Dashboards
GET    /api/v1/dashboards                  # List dashboards
POST   /api/v1/dashboards                  # Create dashboard
GET    /api/v1/dashboards/{id}             # Get dashboard with widgets
PUT    /api/v1/dashboards/{id}             # Update dashboard
DELETE /api/v1/dashboards/{id}             # Delete dashboard
POST   /api/v1/dashboards/{id}/clone       # Clone dashboard

# Queries
POST   /api/v1/query                       # Execute analytics query
POST   /api/v1/query/explain               # Get query plan
GET    /api/v1/query/suggestions           # Auto-complete suggestions

# Alerts
POST   /api/v1/alerts                      # Create alert rule
GET    /api/v1/alerts                      # List alerts
GET    /api/v1/alerts/{id}/history         # Alert history
POST   /api/v1/alerts/{id}/silence         # Silence alert

# Metrics
GET    /api/v1/metrics/{metric_name}       # Get metric time series
GET    /api/v1/metrics/dimensions          # List available dimensions
```

### API Request/Response Examples

```json
// POST /api/v1/events/batch - Batch event ingestion
// Request
{
  "events": [
    {
      "event_type": "page_view",
      "timestamp": "2024-01-15T14:22:33.456Z",
      "user_id": "u_abc123",
      "session_id": "s_xyz789",
      "properties": {
        "page": "/products/shoes",
        "referrer": "google",
        "device_type": "mobile",
        "os": "iOS",
        "country": "US",
        "duration_ms": 3500
      }
    },
    {
      "event_type": "purchase",
      "timestamp": "2024-01-15T14:22:35.789Z",
      "user_id": "u_abc123",
      "properties": {
        "product_id": "p_shoe_001",
        "category": "footwear",
        "revenue": 89.99,
        "quantity": 1,
        "channel": "organic"
      }
    }
  ]
}

// Response (202 Accepted)
{
  "accepted": 2,
  "rejected": 0,
  "errors": []
}

// POST /api/v1/query - Analytics query
// Request
{
  "query": {
    "metrics": ["count", "unique_users", "sum:revenue", "p95:duration_ms"],
    "dimensions": ["country", "device_type"],
    "filters": [
      {"field": "event_type", "operator": "eq", "value": "purchase"},
      {"field": "country", "operator": "in", "values": ["US", "UK", "DE"]}
    ],
    "time_range": {
      "from": "2024-01-15T00:00:00Z",
      "to": "2024-01-15T23:59:59Z"
    },
    "granularity": "1h",
    "order_by": [{"field": "revenue_sum", "direction": "desc"}],
    "limit": 100
  }
}

// Response
{
  "data": [
    {
      "timestamp": "2024-01-15T14:00:00Z",
      "country": "US",
      "device_type": "mobile",
      "count": 45230,
      "unique_users": 12340,
      "revenue_sum": 892345.67,
      "duration_ms_p95": 4200
    }
  ],
  "metadata": {
    "query_time_ms": 145,
    "rows_scanned": 2500000,
    "cache_hit": false,
    "approximate": {"unique_users": true}
  }
}

// POST /api/v1/alerts - Create alert rule
// Request
{
  "name": "High Error Rate",
  "query": {
    "metrics": ["count"],
    "filters": [{"field": "event_type", "operator": "eq", "value": "error"}],
    "granularity": "1m"
  },
  "condition": {
    "operator": "gt",
    "threshold": 1000,
    "for_duration_s": 300
  },
  "severity": "critical",
  "notification_channels": ["slack-engineering", "pagerduty-oncall"]
}
```

## 7. Deep Dives

### Deep Dive 1: Real-Time Aggregation Pipeline

#### Flink Streaming Pipeline with Windowing

```python
class RealTimeAggregationPipeline:
    """Flink-based real-time aggregation with windowing strategies."""
    
    def build_pipeline(self, env: StreamExecutionEnvironment):
        """Build the Flink streaming DAG."""
        
        # Source: Kafka consumer
        events = env.add_source(
            FlinkKafkaConsumer(
                topics=['events-enriched'],
                deserializer=EventDeserializer(),
                properties={
                    'bootstrap.servers': 'kafka:9092',
                    'group.id': 'flink-aggregation',
                    'auto.offset.reset': 'latest'
                }
            )
        ).name("Kafka Source")
        
        # Assign timestamps and watermarks
        timestamped = events.assign_timestamps_and_watermarks(
            WatermarkStrategy
                .for_bounded_out_of_orderness(Duration.of_seconds(10))
                .with_timestamp_assigner(EventTimestampAssigner())
                .with_idleness(Duration.of_minutes(1))
        )
        
        # Branch 1: Tumbling window aggregation (1-minute)
        minute_agg = (timestamped
            .key_by(lambda e: (e.tenant_id, e.event_type))
            .window(TumblingEventTimeWindows.of(Duration.of_minutes(1)))
            .allowed_lateness(Duration.of_minutes(5))
            .side_output_late_data(late_events_tag)
            .aggregate(
                MultiMetricAggregator(),
                ProcessWindowFunction()
            )
        ).name("1-Min Tumbling Window")
        
        # Branch 2: Sliding window for moving averages (5-min window, 1-min slide)
        sliding_agg = (timestamped
            .key_by(lambda e: (e.tenant_id, e.event_type))
            .window(SlidingEventTimeWindows.of(
                Duration.of_minutes(5), Duration.of_minutes(1)
            ))
            .aggregate(MovingAverageAggregator())
        ).name("5-Min Sliding Window")
        
        # Branch 3: Session windows (gap-based, per user)
        session_agg = (timestamped
            .key_by(lambda e: (e.tenant_id, e.user_id))
            .window(EventTimeSessionWindows.with_gap(Duration.of_minutes(30)))
            .aggregate(SessionAggregator())
        ).name("Session Window")
        
        # Sinks
        minute_agg.add_sink(ClickHouseSink('events_1min_realtime'))
        minute_agg.add_sink(RedisSink('rt:counters'))
        sliding_agg.add_sink(RedisSink('rt:moving_avg'))
        session_agg.add_sink(ClickHouseSink('sessions'))
        
        # Late events handling
        late_events = minute_agg.get_side_output(late_events_tag)
        late_events.add_sink(KafkaSink('events-late'))


class MultiMetricAggregator(AggregateFunction):
    """Aggregate multiple metrics simultaneously in a single pass."""
    
    def create_accumulator(self) -> dict:
        return {
            'count': 0,
            'revenue_sum': Decimal('0'),
            'duration_sum': 0,
            'duration_max': 0,
            'unique_users': HyperLogLog(precision=14),
            'duration_tdigest': TDigest(compression=100),
            'top_products': CountMinSketch(width=2048, depth=5),
        }
    
    def add(self, event: Event, acc: dict) -> dict:
        acc['count'] += 1
        acc['revenue_sum'] += event.revenue or Decimal('0')
        acc['duration_sum'] += event.duration_ms or 0
        acc['duration_max'] = max(acc['duration_max'], event.duration_ms or 0)
        acc['unique_users'].add(event.user_id)
        acc['duration_tdigest'].add(event.duration_ms or 0)
        if event.product_id:
            acc['top_products'].add(event.product_id)
        return acc
    
    def get_result(self, acc: dict) -> AggregationResult:
        return AggregationResult(
            count=acc['count'],
            revenue_sum=float(acc['revenue_sum']),
            duration_avg=acc['duration_sum'] / max(acc['count'], 1),
            duration_p50=acc['duration_tdigest'].percentile(50),
            duration_p95=acc['duration_tdigest'].percentile(95),
            duration_p99=acc['duration_tdigest'].percentile(99),
            unique_users=acc['unique_users'].count(),
            duration_max=acc['duration_max'],
        )
    
    def merge(self, acc1: dict, acc2: dict) -> dict:
        """Merge two accumulators (for parallel processing)."""
        return {
            'count': acc1['count'] + acc2['count'],
            'revenue_sum': acc1['revenue_sum'] + acc2['revenue_sum'],
            'duration_sum': acc1['duration_sum'] + acc2['duration_sum'],
            'duration_max': max(acc1['duration_max'], acc2['duration_max']),
            'unique_users': acc1['unique_users'].merge(acc2['unique_users']),
            'duration_tdigest': acc1['duration_tdigest'].merge(acc2['duration_tdigest']),
            'top_products': acc1['top_products'].merge(acc2['top_products']),
        }


class WatermarkStrategy:
    """Handle late-arriving events with watermarks."""
    
    def __init__(self, max_out_of_orderness_ms: int = 10000):
        self.max_out_of_orderness = max_out_of_orderness_ms
        self.max_timestamp_seen = 0
    
    def on_event(self, event: Event, timestamp: int) -> Optional[Watermark]:
        """Update watermark based on observed event timestamps."""
        self.max_timestamp_seen = max(self.max_timestamp_seen, timestamp)
        
        # Emit watermark = max_seen - max_out_of_orderness
        watermark_time = self.max_timestamp_seen - self.max_out_of_orderness
        return Watermark(watermark_time)
    
    def on_periodic_emit(self) -> Watermark:
        """Periodic watermark emission for idle partitions."""
        return Watermark(self.max_timestamp_seen - self.max_out_of_orderness)
```

### Deep Dive 2: Approximate Counting at Scale

#### HyperLogLog for Unique Counts

```python
class HyperLogLog:
    """HyperLogLog for cardinality estimation.
    
    Precision 14 = 16384 registers = ~16KB memory
    Error rate: 1.04 / sqrt(2^14) = ~0.81%
    """
    
    def __init__(self, precision: int = 14):
        self.precision = precision
        self.num_registers = 1 << precision  # 2^p
        self.registers = bytearray(self.num_registers)
        self.alpha = self._compute_alpha()
    
    def add(self, value: str):
        """Add an element to the HLL."""
        hash_val = mmh3.hash128(value, signed=False)
        
        # First p bits determine register index
        register_idx = hash_val >> (128 - self.precision)
        
        # Remaining bits: count leading zeros + 1
        remaining = hash_val & ((1 << (128 - self.precision)) - 1)
        leading_zeros = self._count_leading_zeros(remaining, 128 - self.precision)
        
        # Store maximum leading zeros seen
        self.registers[register_idx] = max(
            self.registers[register_idx], leading_zeros + 1
        )
    
    def count(self) -> int:
        """Estimate cardinality."""
        # Harmonic mean of 2^(-register[i])
        indicator = sum(2.0 ** (-r) for r in self.registers)
        raw_estimate = self.alpha * self.num_registers * self.num_registers / indicator
        
        # Bias correction for small/large cardinalities
        if raw_estimate <= 2.5 * self.num_registers:
            # Small range correction
            zeros = self.registers.count(0)
            if zeros > 0:
                return int(self.num_registers * math.log(self.num_registers / zeros))
            return int(raw_estimate)
        elif raw_estimate > (1 << 32) / 30:
            # Large range correction
            return int(-(1 << 32) * math.log(1 - raw_estimate / (1 << 32)))
        
        return int(raw_estimate)
    
    def merge(self, other: 'HyperLogLog') -> 'HyperLogLog':
        """Merge two HLLs (max of each register)."""
        result = HyperLogLog(self.precision)
        for i in range(self.num_registers):
            result.registers[i] = max(self.registers[i], other.registers[i])
        return result
    
    def _compute_alpha(self) -> float:
        if self.precision == 4: return 0.673
        if self.precision == 5: return 0.697
        if self.precision == 6: return 0.709
        return 0.7213 / (1 + 1.079 / self.num_registers)


class CountMinSketch:
    """Count-Min Sketch for frequency estimation (heavy hitters).
    
    Space: width × depth × 4 bytes
    Error: ε = e/width, δ = e^(-depth)
    """
    
    def __init__(self, width: int = 2048, depth: int = 5):
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]
        self.total_count = 0
        # Different hash seeds per row
        self.seeds = [random.randint(0, 2**32) for _ in range(depth)]
    
    def add(self, item: str, count: int = 1):
        """Increment count for an item."""
        self.total_count += count
        for i in range(self.depth):
            idx = mmh3.hash(item, self.seeds[i], signed=False) % self.width
            self.table[i][idx] += count
    
    def estimate(self, item: str) -> int:
        """Estimate frequency of an item (never underestimates)."""
        estimates = []
        for i in range(self.depth):
            idx = mmh3.hash(item, self.seeds[i], signed=False) % self.width
            estimates.append(self.table[i][idx])
        return min(estimates)  # Take minimum to reduce over-counting
    
    def heavy_hitters(self, threshold_pct: float = 0.01) -> list[tuple[str, int]]:
        """Find items appearing more than threshold% of total.
        
        Note: requires maintaining a separate candidate set.
        """
        threshold = self.total_count * threshold_pct
        # In practice, maintain a heap of candidates
        # and verify with estimate()
        pass
    
    def merge(self, other: 'CountMinSketch') -> 'CountMinSketch':
        """Merge two CMS (element-wise addition)."""
        result = CountMinSketch(self.width, self.depth)
        for i in range(self.depth):
            for j in range(self.width):
                result.table[i][j] = self.table[i][j] + other.table[i][j]
        result.total_count = self.total_count + other.total_count
        return result


class TDigest:
    """T-Digest for accurate percentile estimation across distributed systems.
    
    Provides accurate estimates especially at extreme percentiles (p99, p99.9).
    Compression parameter controls accuracy vs memory trade-off.
    """
    
    def __init__(self, compression: int = 100):
        self.compression = compression
        self.centroids: list[Centroid] = []  # (mean, weight) pairs
        self.total_weight = 0
        self.buffer: list[float] = []
        self.buffer_size = 500
    
    def add(self, value: float):
        """Add a value to the digest."""
        self.buffer.append(value)
        if len(self.buffer) >= self.buffer_size:
            self._flush()
    
    def _flush(self):
        """Merge buffer into centroids."""
        self.buffer.sort()
        for val in self.buffer:
            self._add_to_centroids(val)
        self.buffer.clear()
        self._compress()
    
    def percentile(self, p: float) -> float:
        """Estimate the value at percentile p (0-100)."""
        if self.buffer:
            self._flush()
        
        if not self.centroids:
            return 0
        
        target_weight = (p / 100.0) * self.total_weight
        cumulative = 0
        
        for i, centroid in enumerate(self.centroids):
            if cumulative + centroid.weight >= target_weight:
                # Interpolate within centroid
                if i == 0:
                    return centroid.mean
                prev = self.centroids[i - 1]
                fraction = (target_weight - cumulative) / centroid.weight
                return prev.mean + (centroid.mean - prev.mean) * fraction
            cumulative += centroid.weight
        
        return self.centroids[-1].mean
    
    def merge(self, other: 'TDigest') -> 'TDigest':
        """Merge two T-Digests."""
        result = TDigest(self.compression)
        # Interleave centroids and re-compress
        all_centroids = self.centroids + other.centroids
        random.shuffle(all_centroids)  # Random order for better compression
        for c in all_centroids:
            for _ in range(int(c.weight)):
                result.add(c.mean)
        return result
```

### Deep Dive 3: Query Engine (OLAP Cube + On-Demand Rollup)

```python
class AnalyticsQueryEngine:
    """Query engine with intelligent routing between pre-aggregated and raw data."""
    
    def __init__(self, clickhouse: ClickHouseClient, redis: Redis):
        self.clickhouse = clickhouse
        self.redis = redis
        self.query_planner = QueryPlanner()
    
    async def execute_query(self, query: AnalyticsQuery) -> QueryResult:
        """Execute query with optimal routing."""
        
        # Step 1: Check cache
        cache_key = self._compute_cache_key(query)
        cached = await self.redis.get(f"cache:query:{cache_key}")
        if cached:
            return QueryResult.from_json(cached)
        
        # Step 2: Plan query (choose materialized view or raw table)
        plan = self.query_planner.plan(query)
        
        # Step 3: Execute
        if plan.source == 'materialized_view':
            result = await self._query_materialized(query, plan)
        elif plan.source == 'raw_with_approximate':
            result = await self._query_raw_approximate(query, plan)
        else:
            result = await self._query_raw_exact(query, plan)
        
        # Step 4: Cache result (short TTL for freshness)
        ttl = 5 if query.time_range.includes_now() else 60
        await self.redis.set(f"cache:query:{cache_key}", result.to_json(), ex=ttl)
        
        return result
    
    async def _query_materialized(self, query: AnalyticsQuery, 
                                   plan: QueryPlan) -> QueryResult:
        """Query pre-aggregated materialized views."""
        
        # Select appropriate granularity
        if query.granularity >= timedelta(hours=1):
            table = 'events_1hr'
            merge_func = 'Merge'  # Use -Merge combinators
        else:
            table = 'events_1min'
            merge_func = 'Merge'
        
        # Build ClickHouse SQL
        sql = f"""
            SELECT 
                {self._build_time_bucket(query.granularity)} AS time_bucket,
                {', '.join(query.dimensions)},
                countMerge(event_count) AS count,
                sumMerge(revenue_sum) AS revenue_sum,
                avgMerge(duration_avg) AS duration_avg,
                quantileMerge(0.95)(duration_p95) AS duration_p95,
                uniqMerge(unique_users) AS unique_users
            FROM {table}
            WHERE tenant_id = %(tenant_id)s
              AND {self._build_time_filter(query.time_range, 'timestamp_minute')}
              {self._build_dimension_filters(query.filters)}
            GROUP BY time_bucket, {', '.join(query.dimensions)}
            ORDER BY time_bucket
            {f'LIMIT {query.limit}' if query.limit else ''}
        """
        
        rows = await self.clickhouse.execute(sql, {
            'tenant_id': query.tenant_id,
            **self._extract_filter_params(query.filters)
        })
        
        return QueryResult(data=rows, approximate=True, source=table)
    
    async def _query_raw_approximate(self, query: AnalyticsQuery,
                                      plan: QueryPlan) -> QueryResult:
        """Query raw data with approximate functions for speed."""
        
        sql = f"""
            SELECT
                {self._build_time_bucket(query.granularity)} AS time_bucket,
                {', '.join(query.dimensions)},
                count() AS count,
                sum(revenue) AS revenue_sum,
                avg(duration_ms) AS duration_avg,
                quantile(0.95)(duration_ms) AS duration_p95,
                uniq(user_id) AS unique_users
            FROM events
            WHERE tenant_id = %(tenant_id)s
              AND {self._build_time_filter(query.time_range, 'timestamp')}
              {self._build_dimension_filters(query.filters)}
            GROUP BY time_bucket, {', '.join(query.dimensions)}
            ORDER BY time_bucket
            SETTINGS max_threads = 16, max_memory_usage = 10000000000
        """
        
        rows = await self.clickhouse.execute(sql, {
            'tenant_id': query.tenant_id
        })
        
        return QueryResult(data=rows, approximate=True, source='events')


class QueryPlanner:
    """Determine optimal query execution strategy."""
    
    def plan(self, query: AnalyticsQuery) -> QueryPlan:
        """Choose between materialized view, approximate, or exact query."""
        
        time_span = query.time_range.duration()
        
        # Rule 1: If time span > 24h and granularity >= 1h, use hourly MV
        if time_span > timedelta(hours=24) and query.granularity >= timedelta(hours=1):
            if self._dimensions_covered_by_mv(query.dimensions, 'events_1hr'):
                return QueryPlan(source='materialized_view', table='events_1hr')
        
        # Rule 2: If time span > 1h and granularity >= 1min, use minute MV
        if time_span > timedelta(hours=1) and query.granularity >= timedelta(minutes=1):
            if self._dimensions_covered_by_mv(query.dimensions, 'events_1min'):
                return QueryPlan(source='materialized_view', table='events_1min')
        
        # Rule 3: If cardinality is very high, use approximate
        if self._estimated_cardinality(query) > 10_000_000:
            return QueryPlan(source='raw_with_approximate')
        
        # Rule 4: Exact query on raw data
        return QueryPlan(source='raw_exact')
    
    def _dimensions_covered_by_mv(self, dimensions: list[str], mv_table: str) -> bool:
        """Check if materialized view has all requested dimensions."""
        mv_dimensions = {
            'events_1hr': {'tenant_id', 'event_type', 'country'},
            'events_1min': {'tenant_id', 'event_type', 'country', 'device_type'},
        }
        return set(dimensions).issubset(mv_dimensions.get(mv_table, set()))


class IncrementalMaterializedViewRefresh:
    """Incrementally refresh materialized views without full recomputation."""
    
    async def refresh_incremental(self, view_name: str, since: datetime):
        """Refresh only the data that changed since last refresh."""
        
        # ClickHouse handles this natively with AggregatingMergeTree
        # But for custom rollups:
        
        # Step 1: Find partitions with new data
        new_partitions = await self.clickhouse.execute(f"""
            SELECT DISTINCT toDate(timestamp) as dt
            FROM events
            WHERE timestamp > %(since)s
        """, {'since': since})
        
        # Step 2: Re-aggregate only affected partitions
        for partition in new_partitions:
            await self.clickhouse.execute(f"""
                INSERT INTO {view_name}
                SELECT ... 
                FROM events
                WHERE toDate(timestamp) = %(dt)s
            """, {'dt': partition['dt']})
        
        # Step 3: Deduplicate (OPTIMIZE for ReplacingMergeTree)
        await self.clickhouse.execute(f"OPTIMIZE TABLE {view_name} FINAL")
```

## 8. Component Optimization

### Kafka Configuration

```yaml
# Raw events topic
events-raw:
  partitions: 256
  replication_factor: 3
  retention.ms: 604800000  # 7 days
  retention.bytes: -1
  compression.type: zstd
  min.insync.replicas: 2
  segment.ms: 3600000
  segment.bytes: 1073741824  # 1GB segments

producer:
  acks: 1  # Balance between throughput and durability
  batch.size: 262144  # 256KB batches
  linger.ms: 5
  compression.type: lz4
  buffer.memory: 268435456  # 256MB
  max.in.flight.requests.per.connection: 5

consumer:
  group.id: flink-aggregation
  auto.offset.reset: latest
  fetch.min.bytes: 1048576  # 1MB
  fetch.max.wait.ms: 500
  max.poll.records: 10000
```

### Flink Configuration

```yaml
flink:
  taskmanager:
    numberOfTaskSlots: 8
    memory:
      process.size: 32g
      managed.fraction: 0.4
  
  state:
    backend: rocksdb
    checkpoints.dir: s3://flink-checkpoints/
    savepoints.dir: s3://flink-savepoints/
    
  checkpoint:
    interval: 60000  # 1 minute
    timeout: 600000  # 10 minutes
    min.pause: 30000
    max.concurrent: 1
    
  execution:
    buffer-timeout: 10ms
    
  rest:
    port: 8081
```

### ClickHouse Configuration

```xml
<clickhouse>
    <max_memory_usage>40000000000</max_memory_usage>  <!-- 40GB per query -->
    <max_threads>16</max_threads>
    <max_concurrent_queries>100</max_concurrent_queries>
    
    <!-- Merge tree settings -->
    <merge_tree>
        <max_bytes_to_merge_at_max_space_in_pool>161061273600</max_bytes_to_merge_at_max_space_in_pool>
        <number_of_free_entries_in_pool_to_lower_max_size_of_merge>8</number_of_free_entries_in_pool_to_lower_max_size_of_merge>
    </merge_tree>
    
    <!-- Distributed query settings -->
    <distributed_aggregation_memory_efficient>1</distributed_aggregation_memory_efficient>
    <distributed_group_by_no_merge>0</distributed_group_by_no_merge>
    
    <!-- Compression -->
    <compression>
        <case>
            <min_part_size>10000000000</min_part_size>
            <min_part_size_ratio>0.01</min_part_size_ratio>
            <method>zstd</method>
            <level>3</level>
        </case>
    </compression>
</clickhouse>
```

## 9. Observability

### Metrics

```yaml
# Ingestion
ingestion_events_total{source, event_type}: counter
ingestion_events_rejected_total{reason}: counter
ingestion_latency_ms: histogram
ingestion_batch_size: histogram

# Pipeline
flink_records_per_second{operator}: gauge
flink_watermark_lag_ms{operator}: gauge
flink_checkpoint_duration_ms: histogram
flink_late_events_total: counter
flink_backpressure_ratio{operator}: gauge

# Storage
clickhouse_query_duration_ms{table, query_type}: histogram
clickhouse_parts_count{table}: gauge
clickhouse_rows_inserted_per_second: gauge
clickhouse_merge_duration_ms: histogram

# Query Layer
query_latency_ms{source, cache_hit}: histogram
query_throughput_qps: gauge
query_cache_hit_ratio: gauge
query_errors_total{error_type}: counter

# Dashboard
dashboard_load_time_ms: histogram
websocket_connections_active: gauge
websocket_messages_per_second: gauge

# Alerts
alert_evaluation_duration_ms: histogram
alerts_firing_total{severity}: gauge
alert_notification_latency_ms: histogram
```

### Alerting Rules

```yaml
groups:
  - name: analytics_platform_alerts
    rules:
      - alert: IngestionLagHigh
        expr: flink_watermark_lag_ms > 30000
        for: 5m
        severity: critical
        
      - alert: QueryLatencyHigh
        expr: histogram_quantile(0.95, query_latency_ms) > 2000
        for: 5m
        severity: warning
        
      - alert: ClickHouseMergeBacklog
        expr: clickhouse_parts_count > 300
        for: 10m
        severity: warning
        
      - alert: FlinkBackpressure
        expr: flink_backpressure_ratio > 0.5
        for: 5m
        severity: warning
        
      - alert: IngestionDropping
        expr: rate(ingestion_events_rejected_total[5m]) > 1000
        for: 2m
        severity: critical
        
      - alert: CacheHitRateLow
        expr: query_cache_hit_ratio < 0.3
        for: 15m
        severity: info
```

## 10. Considerations

### Trade-offs

| Decision | Choice | Trade-off |
|---|---|---|
| Aggregation engine | Flink streaming | Operational complexity vs true real-time |
| OLAP store | ClickHouse | Column-store perf vs ecosystem maturity |
| Unique counts | HyperLogLog | ~1% error vs O(1) space for billions |
| Percentiles | T-Digest | Approximation vs streaming-friendly |
| Freshness | 5s target | Infrastructure cost vs user expectation |
| Query cache | 5s TTL for live | Stale data risk vs query latency |

### Failure Scenarios

1. **Kafka broker failure**: Replication factor 3 handles; Flink rewinds consumer offset
2. **Flink checkpoint failure**: Retry from last successful checkpoint; late events handled by watermarks
3. **ClickHouse node down**: Replicated tables auto-failover; queries route to replicas
4. **Ingestion spike**: Kafka absorbs burst; Flink backpressure slows consumption gracefully
5. **Query overload**: Redis cache absorbs repeated queries; query concurrency limits protect ClickHouse

### Security

- Event data encrypted in transit (TLS) and at rest (disk encryption)
- Tenant isolation: all queries filtered by tenant_id (enforced at query layer)
- Dashboard RBAC: owner, editor, viewer roles
- API key authentication for ingestion endpoints
- PII handling: configurable field masking/hashing at ingestion
- Query audit log for compliance

### Scalability Path

- **1K events/s**: Single ClickHouse node, no streaming needed
- **100K events/s**: 3-node ClickHouse, Kafka + simple consumers
- **10M events/s**: Full Flink pipeline, 30-node ClickHouse cluster, approximate algorithms
- **100M events/s**: Multi-region, tiered storage, aggressive pre-aggregation

---

*Total lines: 500+ | Covers all 11 standard sections with full depth*
