# Streaming Pipelines for Real-Time ML

## Batch vs Streaming vs Micro-batch

```
┌─────────────────────────────────────────────────────────────────┐
│  PROCESSING PARADIGMS                                            │
├──────────────┬───────────────┬───────────────┬──────────────────┤
│              │ Batch         │ Micro-batch   │ True Streaming   │
├──────────────┼───────────────┼───────────────┼──────────────────┤
│ Latency      │ Minutes-hours │ Seconds       │ Milliseconds     │
│ Example      │ Airflow+Spark │ Spark Stream  │ Flink, Kafka Str │
│ Complexity   │ Low           │ Medium        │ High             │
│ Cost         │ Low           │ Medium        │ High             │
│ Use case     │ Reports, ML   │ Near-real-time│ Fraud, real-time │
│              │ training      │ dashboards    │ recommendations  │
└──────────────┴───────────────┴───────────────┴──────────────────┘

Rule: Use batch unless you have a business reason for lower latency.
Real-time is 5-10x more expensive and complex.
```

---

## Apache Kafka

```
┌──────────────────────────────────────────────────────────────┐
│                    KAFKA ARCHITECTURE                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Producers ──→ Topic (Partitioned Log) ──→ Consumer Groups   │
│                                                               │
│  Topic: "user_events"                                        │
│  ┌──────────────────────────────────────┐                    │
│  │ Partition 0: [msg1][msg3][msg5][msg7] │ ──→ Consumer A    │
│  │ Partition 1: [msg2][msg4][msg6][msg8] │ ──→ Consumer B    │
│  │ Partition 2: [msg9][msg10][msg11]     │ ──→ Consumer C    │
│  └──────────────────────────────────────┘                    │
│                                                               │
│  • Messages within a partition are ordered                    │
│  • Partitions enable parallelism                             │
│  • Consumer group: each partition → one consumer             │
│  • Retention: time-based or size-based                       │
└──────────────────────────────────────────────────────────────┘
```

### Kafka Producer/Consumer (Python)

```python
from confluent_kafka import Producer, Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
import json

# Producer
producer = Producer({
    "bootstrap.servers": "broker:9092",
    "acks": "all",  # Wait for all replicas
    "enable.idempotence": True,  # Exactly-once producer
})

def publish_event(user_id: int, event_type: str, properties: dict):
    event = {
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "properties": properties,
    }
    producer.produce(
        topic="user_events",
        key=str(user_id),  # Partition by user_id (ordering per user)
        value=json.dumps(event).encode("utf-8"),
    )
    producer.flush()

# Consumer
consumer = Consumer({
    "bootstrap.servers": "broker:9092",
    "group.id": "feature-computation",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,  # Manual commit for exactly-once
})

consumer.subscribe(["user_events"])

while True:
    msg = consumer.poll(timeout=1.0)
    if msg is None:
        continue
    if msg.error():
        handle_error(msg.error())
        continue
    
    event = json.loads(msg.value().decode("utf-8"))
    process_event(event)
    consumer.commit(msg)  # Commit after successful processing
```

### Schema Registry

```python
# Avro schema for type safety and evolution
schema_str = """
{
  "type": "record",
  "name": "UserEvent",
  "fields": [
    {"name": "user_id", "type": "long"},
    {"name": "event_type", "type": "string"},
    {"name": "timestamp", "type": "string"},
    {"name": "properties", "type": {"type": "map", "values": "string"}, "default": {}}
  ]
}
"""
# Schema evolution rules:
# - Adding fields with defaults: BACKWARD compatible
# - Removing fields with defaults: FORWARD compatible
# - FULL compatibility: both backward and forward
```

---

## Apache Flink (True Stream Processing)

```python
# PyFlink example: Real-time feature computation
from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.expressions import col, lit
from pyflink.table.window import Tumble, Slide, Session

env_settings = EnvironmentSettings.in_streaming_mode()
t_env = TableEnvironment.create(env_settings)

# Source: Kafka
t_env.execute_sql("""
    CREATE TABLE user_events (
        user_id BIGINT,
        event_type STRING,
        amount DECIMAL(10,2),
        event_time TIMESTAMP(3),
        WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'user_events',
        'properties.bootstrap.servers' = 'broker:9092',
        'format' = 'json',
        'scan.startup.mode' = 'latest-offset'
    )
""")

# Tumbling window: events per minute
t_env.execute_sql("""
    CREATE TABLE user_features_1min (
        user_id BIGINT,
        window_start TIMESTAMP(3),
        event_count BIGINT,
        total_amount DECIMAL(10,2),
        PRIMARY KEY (user_id, window_start) NOT ENFORCED
    ) WITH (
        'connector' = 'upsert-kafka',
        'topic' = 'user_features_1min',
        'properties.bootstrap.servers' = 'broker:9092',
        'key.format' = 'json',
        'value.format' = 'json'
    )
""")

t_env.execute_sql("""
    INSERT INTO user_features_1min
    SELECT
        user_id,
        TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
        COUNT(*) AS event_count,
        SUM(amount) AS total_amount
    FROM user_events
    GROUP BY user_id, TUMBLE(event_time, INTERVAL '1' MINUTE)
""")
```

### Flink Key Concepts

```
┌─────────────────────────────────────────────────────────────┐
│  EVENT TIME vs PROCESSING TIME                               │
│  • Event time: When event actually occurred                  │
│  • Processing time: When system processes it                 │
│  • Always prefer event time for correctness                  │
├─────────────────────────────────────────────────────────────┤
│  WATERMARKS                                                  │
│  • "No events with timestamp < W will arrive after this"    │
│  • Triggers window computation                               │
│  • Trade-off: tight watermark = less latency, may miss data │
├─────────────────────────────────────────────────────────────┤
│  STATE                                                       │
│  • Flink maintains state per key (user_id)                  │
│  • Checkpointed to durable storage (S3)                     │
│  • Enables exactly-once with checkpointing                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Windowing Strategies

```
Time axis: ──────────────────────────────────────────→

TUMBLING WINDOW (fixed, non-overlapping):
|  Window 1  |  Window 2  |  Window 3  |
|  0-5 min   |  5-10 min  | 10-15 min  |

SLIDING WINDOW (fixed, overlapping):
|  Window 1 (0-10 min)     |
     |  Window 2 (5-15 min)     |
          |  Window 3 (10-20 min)    |
Slide = 5 min, Size = 10 min

SESSION WINDOW (dynamic, gap-based):
|  Session 1  |    gap    |  Session 2      |   gap   | S3 |
Events define boundaries; gap = inactivity threshold
```

```sql
-- Flink SQL windowing examples

-- Tumbling: Hourly aggregates
SELECT user_id,
       TUMBLE_START(event_time, INTERVAL '1' HOUR) AS hour,
       COUNT(*) AS events
FROM user_events
GROUP BY user_id, TUMBLE(event_time, INTERVAL '1' HOUR);

-- Sliding: 24-hour rolling window, updated every hour
SELECT user_id,
       HOP_START(event_time, INTERVAL '1' HOUR, INTERVAL '24' HOUR) AS window_start,
       COUNT(*) AS events_24h
FROM user_events
GROUP BY user_id, HOP(event_time, INTERVAL '1' HOUR, INTERVAL '24' HOUR);

-- Session: User sessions with 30-min gap
SELECT user_id,
       SESSION_START(event_time, INTERVAL '30' MINUTE) AS session_start,
       SESSION_END(event_time, INTERVAL '30' MINUTE) AS session_end,
       COUNT(*) AS events_in_session
FROM user_events
GROUP BY user_id, SESSION(event_time, INTERVAL '30' MINUTE);
```

---

## Real-Time ML Feature Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│            REAL-TIME FEATURE COMPUTATION ARCHITECTURE             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Action ──→ Kafka ──→ Flink ──→ Feature Store (Redis)      │
│                              │                    │               │
│                              │                    ▼               │
│                              │           ML Inference Service     │
│                              │                    │               │
│                              ▼                    ▼               │
│                        Offline Store        Response to User      │
│                        (for training)                             │
│                                                                  │
│  Example: Fraud Detection                                        │
│  1. Payment event → Kafka                                        │
│  2. Flink computes: tx_count_1h, avg_amount_24h, new_device?    │
│  3. Features → Redis                                             │
│  4. ML model reads features → predict fraud → approve/decline    │
│  5. Total latency: < 100ms                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Change Data Capture (CDC) with Debezium

```
┌─────────────────────────────────────────────────────────────┐
│  Database ──→ Debezium ──→ Kafka ──→ Downstream Systems     │
│  (MySQL/PG)   (captures     (event    (Flink, Feature Store,│
│               every INSERT/  stream)   Search Index, Cache) │
│               UPDATE/DELETE)                                 │
└─────────────────────────────────────────────────────────────┘
```

```json
// Debezium CDC event (Kafka message)
{
  "before": {"user_id": 123, "plan": "free", "updated_at": "2024-01-01"},
  "after":  {"user_id": 123, "plan": "pro",  "updated_at": "2024-06-01"},
  "source": {"table": "users", "db": "app"},
  "op": "u",  // c=create, u=update, d=delete
  "ts_ms": 1717200000000
}
```

Use cases for ML:
- Keep feature store in sync with source databases
- Build event-sourced feature computation
- Real-time model retraining triggers

---

## Stream-Table Duality

```
┌─────────────────────────────────────────────────────────────┐
│  A STREAM is an unbounded sequence of events                 │
│  A TABLE is a point-in-time snapshot of accumulated state    │
│                                                              │
│  Stream → Table: Aggregate events into current state         │
│  Table → Stream: Capture every change as an event (CDC)      │
│                                                              │
│  Example:                                                    │
│  Stream: [user1:+$50, user1:+$30, user1:-$20]              │
│  Table:  {user1: balance=$60}                                │
│                                                              │
│  For ML: Streams give you features at any point in time      │
│          Tables give you current features for serving        │
└─────────────────────────────────────────────────────────────┘
```

---

## Late Data Handling

```python
# Strategy 1: Watermarks + allowed lateness (Flink)
# Watermark = event_time - 5 seconds (normal lateness)
# Allowed lateness = 1 hour (late but still process)
# Beyond 1 hour: dropped or sent to side output

# Strategy 2: Retractions/Updates
# When late data arrives, emit correction:
# Original: {user:1, count:5, window:"10:00-10:05"}
# Update:   {user:1, count:7, window:"10:00-10:05"}  # late events included

# Strategy 3: Lambda Architecture
# Batch layer recomputes correct values periodically
# Speed layer provides approximate real-time values
# Serving layer merges both
```

---

## Event-Driven ML Architecture

```python
# Complete example: Real-time recommendation update

# 1. User clicks product → Kafka event
# 2. Flink updates user interest profile in real-time
# 3. Updated profile → Redis (online feature store)
# 4. Next recommendation request uses fresh profile

# Flink job for user interest decay
"""
CREATE TABLE user_interests (
    user_id BIGINT,
    category STRING,
    interest_score DOUBLE,
    last_interaction TIMESTAMP(3),
    PRIMARY KEY (user_id, category) NOT ENFORCED
) WITH ('connector' = 'upsert-kafka', ...);

INSERT INTO user_interests
SELECT
    user_id,
    category,
    -- Exponential decay: recent interactions worth more
    SUM(
        CASE event_type
            WHEN 'purchase' THEN 1.0
            WHEN 'add_to_cart' THEN 0.5
            WHEN 'page_view' THEN 0.1
        END * EXP(-0.1 * TIMESTAMPDIFF(HOUR, event_time, CURRENT_TIMESTAMP))
    ) AS interest_score,
    MAX(event_time) AS last_interaction
FROM user_events
GROUP BY user_id, category;
"""
```

---

## Kafka Streams (Lightweight Alternative)

```java
// Java example: Kafka Streams for feature aggregation
StreamsBuilder builder = new StreamsBuilder();

KStream<String, UserEvent> events = builder.stream("user_events");

// Count events per user in 5-minute windows
KTable<Windowed<String>, Long> eventCounts = events
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)))
    .count(Materialized.as("event-counts-store"));

// Expose via interactive queries (REST API)
// GET /features/{userId}/event_count_5m
```

---

## Cost Considerations

| Component | Cost Driver | Optimization |
|-----------|-------------|--------------|
| Kafka | Storage (retention) + throughput | Reduce retention, compress, tiered storage |
| Flink | Compute (parallelism) + state size | Right-size parallelism, tune checkpointing |
| Redis (online store) | Memory per key | TTL eviction, compress values |
| Network | Cross-AZ traffic | Co-locate producers/consumers |

**Total cost comparison for 1M events/sec:**
- Batch (hourly): ~$500/month
- Micro-batch (1 min): ~$2,000/month  
- True streaming (< 1s): ~$5,000-10,000/month

---

## Interview Questions

1. **When would you choose streaming over batch for ML features?**
   - Fraud detection, real-time recommendations, dynamic pricing — where feature freshness directly impacts business value.

2. **Explain exactly-once semantics in Kafka.**
   - Idempotent producer (no duplicate writes) + transactional consumer (atomic read-process-write) + consumer offset commit.

3. **What are watermarks and why do they matter?**
   - Progress indicator for event time; triggers window computation; trade-off between completeness and latency.

4. **How do you handle out-of-order events?**
   - Event-time processing + watermarks + allowed lateness + late data side outputs.

5. **What's the difference between Kafka Streams and Flink?**
   - Kafka Streams: library (runs in your app), simpler, Kafka-only. Flink: standalone cluster, more powerful (event time, complex state), multiple sources.

6. **Explain consumer groups and partition assignment.**
   - Each partition assigned to exactly one consumer in a group. More partitions = more parallelism. Consumers > partitions = idle consumers.

7. **How do you ensure feature consistency between training and serving?**
   - Same computation logic in both paths; feature store as single source of truth; stream results also saved to offline store for training.

8. **What's CDC and why use it for ML?**
   - Captures database changes as events. Keeps feature store in sync without polling; enables event-time feature computation.

9. **How do you handle backpressure in streaming systems?**
   - Kafka: consumer lag monitoring. Flink: back-propagates to source. Solutions: scale consumers, increase partitions, buffer.

10. **What's the Lambda architecture and its criticism?**
    - Batch + speed layers merged at serving. Criticism: maintaining two codepaths. Alternative: Kappa architecture (stream-only with reprocessing).
