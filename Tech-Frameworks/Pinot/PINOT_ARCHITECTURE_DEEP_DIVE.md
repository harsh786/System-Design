# 🏗️ Apache Pinot Architecture Deep Dive

## 🎯 Why Pinot Does NOT Support Updates

Apache Pinot is an **IMMUTABLE** data store by design. Here's why:

---

## 1️⃣ THE FUNDAMENTAL REASON: SEGMENT-BASED ARCHITECTURE

### What is a Segment?

A **segment** is Pinot's core data structure - think of it as a **frozen block of data**:

```
Segment = Immutable Container of Rows
├── Forward Index (Column Data)
├── Inverted Index (Lookups)
├── Star-Tree Index (Aggregations)
├── Bloom Filters
└── Metadata (Min/Max, Cardinality)
```

**Key Characteristic**: Once created, a segment is **NEVER MODIFIED**.

---

## 2️⃣ SEGMENT LIFECYCLE: REAL-TIME vs OFFLINE

### Architecture Overview:

```
┌─────────────────────────────────────────────────────────────────┐
│                     APACHE PINOT CLUSTER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────┐               │
│  │   KAFKA/PULSAR   │      │   BATCH FILES    │               │
│  │  (Streaming)     │      │   (HDFS/S3)      │               │
│  └────────┬─────────┘      └────────┬─────────┘               │
│           │                         │                          │
│           ▼                         ▼                          │
│  ┌──────────────────┐      ┌──────────────────┐               │
│  │  REAL-TIME       │      │  OFFLINE         │               │
│  │  SERVERS         │      │  JOBS            │               │
│  │  (Consuming)     │      │  (Batch Build)   │               │
│  └────────┬─────────┘      └────────┬─────────┘               │
│           │                         │                          │
│           ▼                         ▼                          │
│  ┌──────────────────────────────────────────┐                 │
│  │      MUTABLE CONSUMING SEGMENTS          │                 │
│  │  (In-Memory, Being Written)              │                 │
│  │  ┌────┐ ┌────┐ ┌────┐                   │                 │
│  │  │ S1 │ │ S2 │ │ S3 │  ← Active writes  │                 │
│  │  └────┘ └────┘ └────┘                   │                 │
│  └────────────────┬─────────────────────────┘                 │
│                   │                                            │
│                   ▼ (When full or time threshold)             │
│  ┌──────────────────────────────────────────┐                 │
│  │      IMMUTABLE SEGMENTS                  │                 │
│  │  (Sealed, Optimized, Ready to Serve)     │                 │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐    │                 │
│  │  │ S1 │ │ S2 │ │ S3 │ │ S4 │ │ S5 │... │                 │
│  │  └────┘ └────┘ └────┘ └────┘ └────┘    │                 │
│  │  (Cannot be modified - only replaced)   │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │          BROKER NODES                    │                 │
│  │  (Query Routing & Aggregation)           │                 │
│  └──────────────────────────────────────────┘                 │
│                   ▲                                            │
│                   │                                            │
│              Client Queries                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3️⃣ REAL-TIME SEGMENTS (Consuming Segments)

### What Happens During Real-Time Ingestion?

```
PHASE 1: CONSUMING (Mutable State)
──────────────────────────────────
Kafka Topic: [event1, event2, event3, ...]
                ↓
Real-Time Server receives events
                ↓
Writes to IN-MEMORY segment (mutable)
                ↓
Segment State: CONSUMING
Size: Growing (0 → 100MB)
Updates: Possible (in memory only)
Queries: YES (can query consuming segment)

PHASE 2: THRESHOLD REACHED
──────────────────────────────────
Trigger conditions:
- Segment size reaches 100MB (configurable)
- Time threshold: 6 hours (configurable)
- Number of rows: 5M rows (configurable)

                ↓

PHASE 3: SEALING (Transition)
──────────────────────────────────
1. Stop accepting new events
2. Flush in-memory data to disk
3. Build all indexes:
   ├── Forward Index
   ├── Inverted Index
   ├── Star-Tree Index
   ├── Bloom Filters
   └── Range Index
4. Compress data
5. Create segment metadata

                ↓

PHASE 4: COMPLETED (Immutable)
──────────────────────────────────
Segment State: ONLINE
Modification: IMPOSSIBLE (sealed)
Storage: Optimized, compressed
Queries: Super fast (all indexes ready)

                ↓

PHASE 5: NEW CONSUMING SEGMENT
──────────────────────────────────
Server creates new CONSUMING segment
Continues from next Kafka offset
```

### Example Timeline:

```
Time: 00:00 → 06:00
┌─────────────────────────────┐
│  Segment_2026011800_0       │
│  State: CONSUMING           │
│  Events: 1M → 5M            │
│  Size: 10MB → 100MB         │
│  Queryable: YES (in-memory) │
└─────────────────────────────┘

Time: 06:00 (Threshold hit)
┌─────────────────────────────┐
│  Segment_2026011800_0       │
│  State: SEALING             │
│  Building indexes...        │
│  Compressing...             │
│  NOT queryable temporarily  │
└─────────────────────────────┘

Time: 06:05 (Sealed)
┌─────────────────────────────┐
│  Segment_2026011800_0       │
│  State: ONLINE              │
│  Events: 5M (frozen)        │
│  Size: 50MB (compressed)    │
│  Queryable: YES (optimized) │
│  IMMUTABLE: Cannot change   │
└─────────────────────────────┘

Time: 06:05 onwards
┌─────────────────────────────┐
│  Segment_2026011806_0       │
│  State: CONSUMING (NEW)     │
│  Events: Starting fresh     │
└─────────────────────────────┘
```

---

## 4️⃣ OFFLINE SEGMENTS (Batch Processing)

### Batch Job Workflow:

```
STEP 1: DATA SOURCE
───────────────────
HDFS/S3/Data Lake
├── /data/2026/01/17/*.parquet
├── /data/2026/01/18/*.parquet
└── /data/2026/01/19/*.parquet

STEP 2: SPARK/HADOOP JOB
────────────────────────
def buildSegment(date):
    data = read_parquet(f"/data/{date}/*.parquet")
    
    # Sort by time column
    data = data.sort_values('timestamp')
    
    # Partition into segments (5M rows each)
    for chunk in partition(data, rows=5_000_000):
        segment = create_segment(
            data=chunk,
            indexes=['timestamp', 'user_id', 'event_type'],
            star_tree=['country', 'device'],
            compression='ZSTD'
        )
        
        upload_to_pinot(segment)

STEP 3: SEGMENT CREATION
─────────────────────────
Segment: events_2026011800_offline_0
├── Rows: 5,000,000
├── Indexes: Pre-built (all types)
├── Compression: Maximum
├── State: ONLINE (immediately queryable)
└── Immutable: YES (never changes)

STEP 4: DEPLOYMENT
──────────────────
Controller assigns segment to servers
Servers download segment
Segment loaded into memory
Ready for queries (instant)
```

---

## 5️⃣ WHY UPDATES ARE IMPOSSIBLE

### The Technical Reasons:

#### A. **Index Invalidation Problem**

If you update one row in a sealed segment:

```
Original Segment:
┌─────────────────────────────────────┐
│ Row 1: user_id=123, status=active  │
│ Row 2: user_id=456, status=active  │
│ Row 3: user_id=789, status=active  │
└─────────────────────────────────────┘

Inverted Index for 'status':
active → [Row 1, Row 2, Row 3]
inactive → []

NOW UPDATE: Row 2 status = 'inactive'
───────────────────────────────────────

Problem 1: Forward index is compressed
→ Need to decompress entire segment
→ Update one value
→ Re-compress entire segment

Problem 2: Inverted index is pre-built
→ Need to rebuild: active → [Row 1, Row 3]
→ Need to rebuild: inactive → [Row 2]

Problem 3: Star-Tree is pre-aggregated
→ Need to recalculate all aggregations
→ Invalidates pre-computed results

Problem 4: Bloom filters are probabilistic
→ Cannot update (need complete rebuild)

Result: The entire segment must be REBUILT!
This defeats the purpose of immutability.
```

#### B. **Performance Degradation**

```
Immutable Segment (Current):
- Query time: 5ms
- Scan 1M rows
- All indexes valid

Mutable Segment (If updates allowed):
- Query time: 500ms (100x slower!)
- Need write locks
- Indexes become stale
- Cache invalidation
- Merge conflicts
- Compaction overhead
```

#### C. **Distributed Consistency**

```
Pinot Cluster:
Server 1: Has Segment A (version 1)
Server 2: Has Segment A (version 1)
Server 3: Has Segment A (version 1)

If UPDATE was allowed:
Server 1: Updates row → Segment A (version 2)
Server 2: Still has Segment A (version 1) ← STALE!
Server 3: Still has Segment A (version 1) ← STALE!

Query hits Server 2:
→ Returns OLD data
→ Data inconsistency!
→ Need distributed transactions (slow!)
```

---

## 6️⃣ HOW TO HANDLE UPDATES IN PINOT

Since direct updates are impossible, here are the patterns:

### **Pattern 1: APPEND-ONLY with Latest Flag** ⭐ RECOMMENDED

```sql
Table Schema:
┌──────────┬──────────┬──────────┬─────────┬────────────┐
│ user_id  │ status   │ timestamp│ version │ is_latest  │
├──────────┼──────────┼──────────┼─────────┼────────────┤
│ 123      │ active   │ Jan 1    │ 1       │ false      │
│ 123      │ inactive │ Jan 15   │ 2       │ false      │
│ 123      │ active   │ Jan 20   │ 3       │ true       │ ← Latest!
└──────────┴──────────┴──────────┴─────────┴────────────┘

Query for current status:
SELECT user_id, status, timestamp
FROM users
WHERE is_latest = true
  AND user_id = 123;

Query for history:
SELECT user_id, status, timestamp
FROM users
WHERE user_id = 123
ORDER BY timestamp DESC;
```

**How to Implement:**

```python
# Real-time ingestion (Kafka consumer)
def process_update_event(event):
    # 1. Mark old records as not latest (via new insert)
    new_record = {
        'user_id': event['user_id'],
        'status': event['status'],
        'timestamp': now(),
        'version': get_next_version(event['user_id']),
        'is_latest': True
    }
    
    # 2. Write to Kafka (will be consumed by Pinot)
    kafka_producer.send('users_topic', new_record)
    
    # Note: Old records remain with is_latest=false
    # They are never modified, just superseded
```

**Pros:**
- ✅ Full audit trail
- ✅ Point-in-time queries
- ✅ No segment rebuilds
- ✅ Real-time updates

**Cons:**
- ❌ Storage grows over time (need retention policy)
- ❌ Queries must filter by is_latest

---

### **Pattern 2: UPSERT via Stream Processing** (Kafka Streams/Flink)

```
ARCHITECTURE:
─────────────

Kafka Topic: user_updates
├── {user_id: 123, status: 'active', ts: Jan 1}
├── {user_id: 123, status: 'inactive', ts: Jan 15}
└── {user_id: 123, status: 'active', ts: Jan 20}
        ↓
Kafka Streams / Flink
├── Group by user_id
├── Keep only latest per key (window)
├── Emit deduplicated stream
        ↓
Kafka Topic: user_latest (compacted)
└── {user_id: 123, status: 'active', ts: Jan 20} ← Only latest
        ↓
Pinot (Consumes deduplicated stream)
└── Segments contain only latest state
```

**Implementation (Kafka Streams):**

```java
StreamsBuilder builder = new StreamsBuilder();

KStream<String, UserEvent> updates = builder.stream("user_updates");

// Keep only latest per user (tumbling window)
KTable<String, UserEvent> latestState = updates
    .groupByKey()
    .aggregate(
        UserEvent::new,
        (key, newValue, aggValue) -> 
            newValue.timestamp > aggValue.timestamp ? newValue : aggValue
    );

// Emit to new topic
latestState.toStream().to("user_latest");

// Pinot consumes from "user_latest"
```

**Pros:**
- ✅ Pinot only stores latest state
- ✅ Reduced storage
- ✅ Fast queries (no is_latest filter needed)

**Cons:**
- ❌ No history/audit trail
- ❌ Additional infrastructure (Kafka Streams)
- ❌ Window-based delays

---

### **Pattern 3: HYBRID (Pinot + MySQL)** ⭐ BEST FOR COMPLEX UPDATES

```
┌─────────────────────────────────────────────────┐
│              APPLICATION LAYER                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  UPDATE user_status(user_id, new_status):      │
│    1. Write to MySQL (OLTP)                     │
│    2. Write event to Kafka                      │
│    3. Return success                            │
│                                                 │
└───────────┬─────────────────────┬───────────────┘
            │                     │
            ▼                     ▼
    ┌───────────────┐     ┌──────────────┐
    │    MySQL      │     │    Kafka     │
    │  (OLTP)       │     │  (Events)    │
    │               │     │              │
    │ Current State │     │ Change Log   │
    │ user_id: 123  │     │ + event 1    │
    │ status: actv  │     │ + event 2    │
    │               │     │ + event 3    │
    │ Fast lookups  │     └──────┬───────┘
    │ Single row    │            │
    └───────────────┘            ▼
                         ┌──────────────┐
                         │    Pinot     │
                         │  (Analytics) │
                         │              │
                         │ Full History │
                         │ Aggregations │
                         │ Dashboards   │
                         └──────────────┘

USE CASES:
──────────
• Get current user status → MySQL
• Get user change history → Pinot
• Count status changes → Pinot
• User behavior trends → Pinot
```

**Example:**

```python
class UserService:
    def update_user_status(self, user_id, new_status):
        # 1. Update OLTP database (source of truth for current state)
        mysql.execute(
            "UPDATE users SET status = %s WHERE id = %s",
            (new_status, user_id)
        )
        
        # 2. Publish change event (for analytics)
        event = {
            'user_id': user_id,
            'old_status': get_old_status(user_id),
            'new_status': new_status,
            'timestamp': now(),
            'event_type': 'status_change'
        }
        kafka.send('user_events', event)
        
        return {'success': True}

    def get_current_status(self, user_id):
        # Fast lookup from MySQL
        return mysql.query("SELECT status FROM users WHERE id = %s", user_id)
    
    def get_status_history(self, user_id):
        # Analytics query from Pinot
        return pinot.query(f"""
            SELECT timestamp, old_status, new_status
            FROM user_events
            WHERE user_id = {user_id}
              AND event_type = 'status_change'
            ORDER BY timestamp DESC
        """)
    
    def get_status_change_stats(self):
        # Aggregation from Pinot
        return pinot.query("""
            SELECT 
                toStartOfHour(timestamp) as hour,
                old_status,
                new_status,
                COUNT(*) as change_count
            FROM user_events
            WHERE event_type = 'status_change'
              AND timestamp >= now() - INTERVAL 24 HOUR
            GROUP BY hour, old_status, new_status
        """)
```

**Pros:**
- ✅ Best of both worlds
- ✅ Fast point lookups (MySQL)
- ✅ Fast analytics (Pinot)
- ✅ Full history preserved
- ✅ True updates in MySQL

**Cons:**
- ❌ Two databases to manage
- ❌ Eventual consistency
- ❌ More complex architecture

---

### **Pattern 4: SEGMENT REPLACEMENT (For Batch/Historical Corrections)**

```
SCENARIO: Need to correct data from 2 weeks ago

STEP 1: IDENTIFY AFFECTED SEGMENTS
───────────────────────────────────
pinot-admin GetSegments \
    --tableNameWithType logs_OFFLINE \
    --startDate 20260101 \
    --endDate 20260107

Result: [logs_20260101_0, logs_20260102_0, logs_20260103_0]

STEP 2: REGENERATE SEGMENTS
────────────────────────────
# Spark job to rebuild segments
spark-submit regenerate_segments.py \
    --date-range 2026-01-01:2026-01-07 \
    --correction "UPDATE status WHERE condition"

Output: New corrected segments

STEP 3: REPLACE OLD SEGMENTS
─────────────────────────────
pinot-admin UploadSegment \
    --segmentDir /path/to/corrected/segments \
    --tableNameWithType logs_OFFLINE \
    --replace true  ← Replace existing

STEP 4: OLD SEGMENTS DELETED
─────────────────────────────
Pinot automatically:
1. Loads new segments
2. Marks old segments for deletion
3. Removes old segments
4. Queries use new data
```

**Use Case:**
- Historical data corrections
- Schema migrations
- Data quality fixes
- GDPR deletions (rebuild without specific user)

**Pros:**
- ✅ Can fix old data
- ✅ Complete segment replacement

**Cons:**
- ❌ Slow (batch rebuild)
- ❌ Not for real-time updates
- ❌ Requires reprocessing source data

---

## 7️⃣ BEST PRACTICES FOR UPDATE PATTERNS

### Choose Based on Your Requirements:

| Requirement | Pattern | Why |
|------------|---------|-----|
| Audit trail needed | Append-only | Keeps all history |
| Only latest matters | Stream dedup | Saves storage |
| High update frequency | Hybrid (MySQL+Pinot) | MySQL handles updates |
| Rare corrections | Segment replacement | One-time fixes |
| Real-time dashboards | Append-only + is_latest | Fast queries |
| Point-in-time queries | Append-only with version | Historical accuracy |

### Storage Considerations:

```
Append-Only Growth:
───────────────────
Day 1: 1M records = 100 MB
Day 2: 1M new + 100K updates = 110 MB
Day 3: 1M new + 100K updates = 110 MB
...
Week 1: 7M records + 700K updates = 770 MB

Solution: Retention Policy
─────────────────────────
pinot-admin AddTable \
    --config '{
        "retentionTimeUnit": "DAYS",
        "retentionTimeValue": "30"
    }'

Auto-deletes segments older than 30 days
```

---

## 8️⃣ COMPARISON: PINOT vs CLICKHOUSE UPDATES

| Feature | Apache Pinot | ClickHouse |
|---------|-------------|------------|
| **Native Updates** | ❌ No | ✅ Yes (via mutations) |
| **Update Speed** | N/A | Slow (async) |
| **Pattern** | Append-only | ALTER DELETE/UPDATE |
| **Use Case** | Event streams | Corrections |
| **Workaround** | Required | Optional |

**ClickHouse Update Example:**

```sql
-- ClickHouse supports this:
ALTER TABLE logs 
UPDATE status = 'inactive' 
WHERE user_id = 123;

-- But it's async and slow!
-- Creates a mutation that processes in background
```

**Why ClickHouse can do updates (but they're slow):**
- Uses MergeTree mutations
- Background process merges parts
- Not real-time (minutes to hours)
- Still immutable at segment level
- Better than Pinot, but not OLTP-fast

---

## 🎯 SUMMARY

### Why Pinot Doesn't Support Updates:

1. **Immutable Segments** - Core architectural decision
2. **Index Optimization** - Updates invalidate pre-built indexes
3. **Query Performance** - Immutability enables sub-second queries
4. **Distributed Consistency** - No need for locks/transactions

### How to Design for Updates:

1. **Event Sourcing** - Store all changes, query latest
2. **Stream Processing** - Deduplicate before Pinot
3. **Hybrid Architecture** - MySQL for state, Pinot for analytics
4. **Segment Replacement** - Batch corrections

### Key Insight:

> **Pinot sacrifices update capability for query speed.**
> 
> For observability/analytics where you query 1000x more than you update,
> this tradeoff is worth it. You get 10-100x faster queries.

**Choose Pinot when:**
- ✅ Mostly inserts (events, logs, metrics)
- ✅ Updates are rare
- ✅ Need real-time analytics
- ✅ Sub-second queries required

**Choose MySQL/PostgreSQL when:**
- ✅ Frequent updates
- ✅ Need transactions
- ✅ CRUD operations
- ✅ Relational data integrity

**Use BOTH (Hybrid) when:**
- ✅ Need both capabilities
- ✅ Operational + analytical workloads
- ✅ Best performance for each use case

---

## 🚀 PRACTICAL EXAMPLE: USER ACTIVITY TRACKING

```python
# WRONG: Trying to update in Pinot
def track_user_session(user_id):
    # This won't work efficiently!
    pinot.execute(f"UPDATE user_sessions SET end_time = now() WHERE user_id = {user_id}")

# RIGHT: Append-only pattern
def track_user_session(user_id):
    # Session start
    event_start = {
        'user_id': user_id,
        'event_type': 'session_start',
        'timestamp': now(),
        'session_id': generate_session_id()
    }
    kafka.send('user_events', event_start)
    
    # ... user activity ...
    
    # Session end
    event_end = {
        'user_id': user_id,
        'event_type': 'session_end',
        'timestamp': now(),
        'session_id': session_id
    }
    kafka.send('user_events', event_end)
    
    # Query session duration (Pinot)
    duration = pinot.query(f"""
        SELECT 
            session_id,
            MAX(timestamp) - MIN(timestamp) as duration
        FROM user_events
        WHERE user_id = {user_id}
        GROUP BY session_id
    """)
```

This is the "Pinot way" - design around immutability, not against it! 🎉
