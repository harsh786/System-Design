# 🔄 Apache Pin│  ✓ Immutable         │        │  ✓ Mutable*          │      │
│  ✓ Pre-aggregated    │        │  ✓ Fresh data        │      │
│  ✓ Highly compressed │        │  ✓ Being consumed    │      │
│  ✓ Optimized indexes │        │  ✓ Lower compression │      │
│                      │        │                      │      │
│  * Only CONSUMING segments are mutable                      │
│  * Once sealed → IMMUTABLE forever                          │
│  * See PINOT_SEGMENT_MUTABILITY.md for details              │Online vs Offline Segments - Deep Dive

## 📊 Overview: The Dual-Segment Architecture

Apache Pinot uses a **hybrid architecture** with two types of segments:

```
┌─────────────────────────────────────────────────────────────────┐
│                      PINOT TABLE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐        ┌──────────────────────┐      │
│  │   OFFLINE SEGMENTS   │        │   ONLINE SEGMENTS    │      │
│  │   (Batch/Historical) │        │   (Real-time/Kafka)  │      │
│  │                      │        │                      │      │
│  │  ✓ Immutable         │        │  ✓ Mutable           │      │
│  │  ✓ Pre-aggregated    │        │  ✓ Fresh data        │      │
│  │  ✓ Highly compressed │        │  ✓ Being consumed    │      │
│  │  ✓ Optimized indexes │        │  ✓ Lower compression │      │
│  └──────────────────────┘        └──────────────────────┘      │
│           ↑                               ↑                     │
│           │                               │                     │
│    Batch Ingestion                Stream Ingestion             │
│    (Hadoop/Spark)                  (Kafka/Kinesis)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ OFFLINE SEGMENTS (Batch/Historical Data)

### What are Offline Segments?

**Offline segments** are **immutable, pre-built segments** created from batch data sources.

### Characteristics:

```
┌─────────────────────────────────────────────────────────────┐
│ OFFLINE SEGMENT                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📅 Time Range: 2026-01-01 to 2026-01-31 (Full month)     │
│  📦 Size: 1 GB (compressed)                                 │
│  🔒 State: IMMUTABLE (cannot be modified)                   │
│  💾 Storage: Deep storage (S3, HDFS, NFS)                   │
│  🚀 Optimizations:                                          │
│     - Sorted and indexed                                    │
│     - Highly compressed                                     │
│     - Pre-aggregated if needed                              │
│     - Bloom filters built                                   │
│     - Star-tree indexes created                             │
│                                                             │
│  ⚡ Query Performance: VERY FAST                            │
│  💰 Cost: LOW (cold storage)                                │
└─────────────────────────────────────────────────────────────┘
```

### Creation Process:

```
Step 1: Batch Job (Hadoop/Spark)
┌──────────────────────────────────────────────────────┐
│  SELECT * FROM logs                                  │
│  WHERE date BETWEEN '2026-01-01' AND '2026-01-31'   │
│  ORDER BY timestamp                                  │
└──────────────────────────────────────────────────────┘
                    ↓
Step 2: Segment Generation
┌──────────────────────────────────────────────────────┐
│  - Sort data by timestamp                            │
│  - Create forward indexes                            │
│  - Create inverted indexes                           │
│  - Build bloom filters                               │
│  - Compress with Snappy/LZ4/ZSTD                     │
│  - Generate metadata                                 │
└──────────────────────────────────────────────────────┘
                    ↓
Step 3: Upload to Deep Storage
┌──────────────────────────────────────────────────────┐
│  S3: s3://bucket/segments/logs_2026-01_v1            │
│  HDFS: hdfs:///pinot/segments/logs_2026-01_v1        │
└──────────────────────────────────────────────────────┘
                    ↓
Step 4: Register with Controller
┌──────────────────────────────────────────────────────┐
│  Pinot Controller adds metadata to ZooKeeper         │
│  Segment is now queryable!                           │
└──────────────────────────────────────────────────────┘
```

### Use Cases:

✅ **Historical Analysis**: "Show all logs from last year"
✅ **Compliance/Audit**: "Retrieve logs from Q3 2025"
✅ **Long-term Trends**: "Compare sales data year-over-year"
✅ **Data Warehouse**: Replace traditional data warehouses

---

## 2️⃣ ONLINE SEGMENTS (Real-time/Streaming Data)

### What are Online Segments?

**Online segments** are **mutable, actively consuming segments** built from streaming data sources.

### Characteristics:

```
┌─────────────────────────────────────────────────────────────┐
│ ONLINE SEGMENT (Consuming State)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📅 Time Range: 2026-01-18 10:00 to NOW (Active)          │
│  📦 Size: 100 MB (growing)                                  │
│  🔓 State: MUTABLE (actively receiving data)                │
│  💾 Storage: Memory + Local disk                            │
│  🔄 Status: CONSUMING                                       │
│                                                             │
│  Data Flow:                                                 │
│  Kafka → Consumer → In-Memory Buffer → Disk Flush          │
│                                                             │
│  ⚡ Query Performance: FAST (but slower than offline)       │
│  💰 Cost: HIGH (hot storage, memory)                        │
│                                                             │
│  ⏱️ Commit Interval: Every 10 minutes                       │
└─────────────────────────────────────────────────────────────┘
```

### Lifecycle:

```
┌─────────────────────────────────────────────────────────────────┐
│                 ONLINE SEGMENT LIFECYCLE                        │
└─────────────────────────────────────────────────────────────────┘

Phase 1: CONSUMING (Mutable)
┌───────────────────────────────────────────────────────────┐
│  Time: 0 - 10 minutes (configurable)                      │
│  State: MUTABLE                                            │
│  Action: Actively consuming from Kafka                     │
│                                                            │
│  Kafka Topic: logs                                         │
│  Partition: 0                                              │
│  Offset: 1000 → 5000 (consuming)                          │
│                                                            │
│  Memory Buffer:                                            │
│  [Row 1] [Row 2] [Row 3] ... [Row N]                      │
│                                                            │
│  Every few seconds: Flush to disk                          │
│  Indexes: Partially built (incremental)                    │
│  Compression: None or minimal                              │
│  Queries: Can query this segment!                          │
└───────────────────────────────────────────────────────────┘
                        ↓
              (Time threshold reached OR
               Size threshold reached OR
               Row count threshold reached)
                        ↓
Phase 2: ONLINE (Sealed/Immutable)
┌───────────────────────────────────────────────────────────┐
│  Time: After commit                                        │
│  State: IMMUTABLE                                          │
│  Action: Segment sealed, no more data accepted             │
│                                                            │
│  Final Operations:                                         │
│  - Complete all indexes                                    │
│  - Apply compression                                       │
│  - Optimize for queries                                    │
│  - Persist to disk                                         │
│                                                            │
│  New consuming segment started:                            │
│  logs_2026-01-18_10-10_CONSUMING                          │
│                                                            │
│  This segment:                                             │
│  logs_2026-01-18_10-00_ONLINE                             │
└───────────────────────────────────────────────────────────┘
                        ↓
              (Retention policy trigger)
                        ↓
Phase 3: OFFLINE (Optional Migration)
┌───────────────────────────────────────────────────────────┐
│  Background job converts online → offline segment          │
│                                                            │
│  Process:                                                  │
│  1. Download online segment                                │
│  2. Reprocess with offline optimizations                   │
│  3. Upload to deep storage (S3/HDFS)                       │
│  4. Replace online segment with offline segment            │
│  5. Delete online segment from local storage               │
│                                                            │
│  Benefits:                                                 │
│  - Better compression                                      │
│  - Advanced indexes (star-tree)                            │
│  - Cheaper storage                                         │
│  - Faster queries                                          │
└───────────────────────────────────────────────────────────┘
```

---

## 3️⃣ HOW QUERIES WORK ACROSS BOTH SEGMENT TYPES

### Query Execution:

```
Query: SELECT COUNT(*) FROM logs 
       WHERE level = 'ERROR' 
       AND timestamp >= '2026-01-01'

┌─────────────────────────────────────────────────────────────┐
│                    PINOT BROKER                             │
├─────────────────────────────────────────────────────────────┤
│  1. Parse query                                             │
│  2. Check routing table in ZooKeeper                        │
│  3. Identify relevant segments:                             │
│                                                             │
│     OFFLINE SEGMENTS:                                       │
│     - logs_2026-01_v1 (Jan 1-31)                           │
│     - logs_2026-02_v1 (Feb 1-28)                           │
│     ... (10 segments)                                       │
│                                                             │
│     ONLINE SEGMENTS:                                        │
│     - logs_2026-01-18_10-00_ONLINE (sealed)                │
│     - logs_2026-01-18_10-10_CONSUMING (active)             │
│     ... (5 segments)                                        │
│                                                             │
│  4. Send sub-queries to servers                             │
└─────────────────────────────────────────────────────────────┘
                        ↓
          ┌─────────────┴─────────────┐
          ↓                           ↓
┌──────────────────┐        ┌──────────────────┐
│  PINOT SERVER 1  │        │  PINOT SERVER 2  │
│                  │        │                  │
│  Offline Segments│        │  Online Segments │
│  - Query 10 segs │        │  - Query 5 segs  │
│  - Fast (cached) │        │  - Fast (memory) │
│  - Count: 50,000 │        │  - Count: 500    │
└──────────────────┘        └──────────────────┘
          ↓                           ↓
          └─────────────┬─────────────┘
                        ↓
          ┌─────────────────────────┐
          │    BROKER AGGREGATES    │
          │    50,000 + 500         │
          │    = 50,500 errors      │
          └─────────────────────────┘
                        ↓
                  Return to user
```

**Key Points**:
- Queries span BOTH offline and online segments seamlessly
- User doesn't know/care which segment type has the data
- Results are merged by the broker
- Fresh data (online) + historical data (offline) = complete view

---

## 4️⃣ HANDLING UPDATES IN PINOT

### ⚠️ THE FUNDAMENTAL PROBLEM: Pinot has NO UPDATE support!

```
❌ This does NOT work in Pinot:
UPDATE logs SET level = 'WARN' WHERE log_id = 12345;

❌ This does NOT work either:
DELETE FROM logs WHERE log_id = 12345;
```

### Why No Updates?

**1. Immutability by Design**:
```
Offline Segments:
┌─────────────────────────────────────────┐
│  Segment: logs_jan_2026                 │
│  State: SEALED and UPLOADED to S3       │
│  File: segment.tar.gz (1 GB compressed) │
│                                         │
│  To update ONE row:                     │
│  1. Download 1 GB from S3               │
│  2. Decompress                          │
│  3. Modify ONE row                      │
│  4. Re-index everything                 │
│  5. Re-compress                         │
│  6. Upload back to S3                   │
│                                         │
│  Cost: Minutes + High I/O               │
│  Benefit: Change 1 row out of 10M       │
│                                         │
│  ❌ NOT WORTH IT!                       │
└─────────────────────────────────────────┘
```

**2. Performance Trade-off**:
- Immutability enables extreme compression
- Immutability enables aggressive caching
- Immutability enables parallel processing
- Updates would destroy all these benefits

**3. Distributed Challenge**:
```
Segment replicated across 3 servers:
Server 1: logs_jan_2026 (replica 1)
Server 2: logs_jan_2026 (replica 2)
Server 3: logs_jan_2026 (replica 3)

To update 1 row:
- Update all 3 replicas
- Ensure consistency
- Handle conflicts
- Manage distributed transactions

Result: Complexity explosion!
```

---

## 5️⃣ WORKAROUNDS FOR UPDATE SCENARIOS

### Scenario 1: Late-Arriving Data (Out-of-Order Events)

**Problem**: Event from 2 hours ago arrives now

```
Current Time: 2026-01-18 12:00
Event Time: 2026-01-18 10:00  ← Late by 2 hours!

Segment timeline:
├─ logs_10-00_ONLINE (sealed) ─┤─ logs_11-00_ONLINE (sealed) ─┤─ logs_12-00_CONSUMING ─┤
   Should be here! ↑              Currently here ↑
```

**Solution A: Append-Only with Time Travel**
```sql
-- Original record (arrived on time)
{
  "log_id": "12345",
  "timestamp": "2026-01-18 10:30:00",
  "level": "INFO",
  "message": "Request started",
  "version": 1,
  "is_deleted": false
}

-- Correction record (late arrival)
{
  "log_id": "12345",
  "timestamp": "2026-01-18 10:30:00",  ← Same logical time
  "level": "ERROR",  ← Updated value
  "message": "Request failed",
  "version": 2,  ← Higher version
  "is_deleted": false,
  "arrived_at": "2026-01-18 12:00:00"  ← Actual arrival time
}

-- Query with deduplication:
SELECT log_id, timestamp, level, message
FROM logs
WHERE timestamp >= '2026-01-18 10:00'
  AND is_deleted = false
ORDER BY log_id, version DESC
LIMIT 1 BY log_id  ← Get latest version only
```

**Solution B: Segment Replacement (Batch)**
```
Daily job at midnight:
┌────────────────────────────────────────────────────────────┐
│ 1. Collect all late-arriving data from last 24 hours      │
│ 2. Regenerate affected offline segments                    │
│ 3. Replace old segments with new versions                  │
└────────────────────────────────────────────────────────────┘

Before:
logs_2026-01-17_v1.tar.gz (without late data)

After:
logs_2026-01-17_v2.tar.gz (with late data included)

Pinot automatically switches to v2!
```

---

### Scenario 2: Data Corrections/Updates

**Problem**: Need to update a field in historical data

**Example**: User's email changed, need to update all their logs

```
Original records:
┌─────────┬─────────────────────┬──────────────────────┐
│ user_id │ email               │ timestamp            │
├─────────┼─────────────────────┼──────────────────────┤
│ 123     │ old@example.com     │ 2026-01-15 10:00:00  │
│ 123     │ old@example.com     │ 2026-01-15 11:00:00  │
│ 123     │ old@example.com     │ 2026-01-16 09:00:00  │
└─────────┴─────────────────────┴──────────────────────┘

Need to update to: new@example.com
```

**Solution A: Soft Delete + Insert Pattern**
```sql
-- Step 1: Mark old records as deleted (append tombstones)
INSERT INTO logs VALUES
(123, 'old@example.com', '2026-01-15 10:00:00', true),  -- is_deleted=true
(123, 'old@example.com', '2026-01-15 11:00:00', true),
(123, 'old@example.com', '2026-01-16 09:00:00', true);

-- Step 2: Insert corrected records
INSERT INTO logs VALUES
(123, 'new@example.com', '2026-01-15 10:00:00', false),
(123, 'new@example.com', '2026-01-15 11:00:00', false),
(123, 'new@example.com', '2026-01-16 09:00:00', false);

-- Step 3: Query with filter
SELECT user_id, email, timestamp
FROM logs
WHERE user_id = 123 
  AND is_deleted = false  ← Filter out old data
ORDER BY timestamp;
```

**Solution B: Lookup Table Pattern**
```sql
-- Separate dimension table (updated frequently)
CREATE TABLE users_dim (
  user_id INT,
  email STRING,
  updated_at TIMESTAMP
)

-- Fact table (immutable)
CREATE TABLE logs (
  user_id INT,
  timestamp TIMESTAMP,
  message STRING
)

-- Query with JOIN (Pinot supports JOINs!)
SELECT 
  l.user_id,
  u.email,  ← Always get latest email
  l.timestamp,
  l.message
FROM logs l
JOIN users_dim u ON l.user_id = u.user_id
WHERE l.timestamp >= '2026-01-15';
```

**Solution C: Nightly Segment Rebuild**
```
Scheduled Job (Airflow/Cron):
┌────────────────────────────────────────────────────────────┐
│ Run at 2 AM daily:                                         │
│                                                            │
│ 1. Identify segments needing updates                       │
│    - Check update_queue table                              │
│    - Find affected date ranges                             │
│                                                            │
│ 2. For each affected segment:                              │
│    a. Export data from Pinot                               │
│    b. Load into Spark                                      │
│    c. Apply updates/corrections                            │
│    d. Regenerate segment with new data                     │
│    e. Upload as new version (v2, v3, etc.)                 │
│                                                            │
│ 3. Pinot Controller:                                       │
│    - Detects new version                                   │
│    - Marks old version for deletion                        │
│    - Routes queries to new version                         │
│                                                            │
│ 4. Cleanup:                                                │
│    - Delete old segment files                              │
│    - Update metadata                                       │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario 3: GDPR/Data Deletion Requests

**Problem**: User requests data deletion (right to be forgotten)

**Solution: Deletion Marker + Background Compaction**

```
┌────────────────────────────────────────────────────────────┐
│              DATA DELETION WORKFLOW                        │
└────────────────────────────────────────────────────────────┘

Step 1: User submits deletion request
┌────────────────────────────────────────┐
│ DELETE user_id: 123                    │
│ Reason: GDPR right to be forgotten     │
│ Submitted: 2026-01-18 14:00:00         │
└────────────────────────────────────────┘
                  ↓
Step 2: Write to deletion_log table
┌────────────────────────────────────────┐
│ INSERT INTO deletion_log VALUES        │
│ (123, '2026-01-18 14:00:00', 'GDPR')  │
└────────────────────────────────────────┘
                  ↓
Step 3: Immediate query-time filtering
┌────────────────────────────────────────┐
│ SELECT * FROM logs                     │
│ WHERE user_id NOT IN (                 │
│   SELECT user_id FROM deletion_log     │
│ )                                      │
│                                        │
│ OR use Pinot query rewriter:           │
│ Auto-inject deletion filter            │
└────────────────────────────────────────┘
                  ↓
Step 4: Background compaction (nightly)
┌────────────────────────────────────────┐
│ For each segment with deleted users:   │
│ 1. Download segment                    │
│ 2. Filter out deleted user_ids         │
│ 3. Regenerate segment                  │
│ 4. Upload new version                  │
│ 5. Switch to new version               │
│ 6. Delete old version                  │
└────────────────────────────────────────┘
                  ↓
Step 5: Physical deletion complete
┌────────────────────────────────────────┐
│ User data physically removed           │
│ Audit log updated                      │
│ Compliance requirement met             │
└────────────────────────────────────────┘
```

---

## 6️⃣ SYSTEM DESIGN: UPDATE-FRIENDLY ARCHITECTURE

### Design Pattern: Lambda Architecture for Updates

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE SYSTEM DESIGN                       │
└─────────────────────────────────────────────────────────────────┘

                        ┌─────────────┐
                        │  DATA SOURCE │
                        └──────┬───────┘
                               │
                ┌──────────────┴──────────────┐
                ↓                             ↓
        ┌───────────────┐            ┌───────────────┐
        │  BATCH PATH   │            │  SPEED PATH   │
        │  (Offline)    │            │  (Real-time)  │
        └───────┬───────┘            └───────┬───────┘
                ↓                             ↓
        ┌───────────────┐            ┌───────────────┐
        │   Hadoop/     │            │     Kafka     │
        │     Spark     │            │               │
        │               │            │               │
        │ - Full data   │            │ - Latest data │
        │ - Reprocess   │            │ - Low latency │
        │ - Corrections │            │ - Mutable     │
        └───────┬───────┘            └───────┬───────┘
                ↓                             ↓
        ┌───────────────┐            ┌───────────────┐
        │ OFFLINE       │            │ ONLINE        │
        │ SEGMENTS      │            │ SEGMENTS      │
        │               │            │               │
        │ - Immutable   │            │ - Consuming   │
        │ - Optimized   │            │ - Fresh       │
        │ - Historical  │            │ - Recent      │
        └───────┬───────┘            └───────┬───────┘
                └──────────────┬──────────────┘
                               ↓
                    ┌──────────────────┐
                    │   PINOT CLUSTER  │
                    │                  │
                    │  Queries merge   │
                    │  both paths      │
                    └──────────────────┘
```

### Component Details:

**1. Update Queue Service**
```python
# Microservice to handle updates
class UpdateQueueService:
    def update_log(self, log_id, updates):
        # Write to update queue
        kafka.produce('updates-topic', {
            'log_id': log_id,
            'updates': updates,
            'timestamp': now()
        })
        
        # Write to cache for immediate queries
        redis.setex(f"update:{log_id}", 3600, updates)
        
        # Schedule segment regeneration
        scheduler.schedule_rebuild(
            affected_segments=[identify_segments(log_id)]
        )
```

**2. Query-Time Merge Service**
```python
# Apply updates at query time
class QueryMerger:
    def query_with_updates(self, query):
        # Execute base query on Pinot
        base_results = pinot.query(query)
        
        # Get pending updates from cache
        updates = redis.mget([f"update:{r.log_id}" 
                              for r in base_results])
        
        # Merge results
        final_results = []
        for result, update in zip(base_results, updates):
            if update:
                result.apply(update)  # Apply update
            if not result.is_deleted:
                final_results.append(result)
        
        return final_results
```

**3. Segment Regeneration Job**
```python
# Nightly job to rebuild segments
class SegmentRebuilder:
    def rebuild_segments(self):
        # Get list of segments with updates
        segments = get_segments_with_updates()
        
        for segment in segments:
            # Download segment data
            data = download_segment(segment)
            
            # Get all updates for this segment's time range
            updates = get_updates(
                start=segment.start_time,
                end=segment.end_time
            )
            
            # Apply updates in Spark
            updated_data = spark.sql(f"""
                SELECT 
                    COALESCE(u.col, d.col) as col,
                    ...
                FROM data d
                LEFT JOIN updates u ON d.id = u.id
                WHERE NOT COALESCE(u.is_deleted, false)
            """)
            
            # Generate new segment
            new_segment = generate_segment(updated_data)
            
            # Upload and activate
            upload_segment(new_segment)
            activate_segment(new_segment)
            
            # Cleanup
            deactivate_segment(segment)
            delete_applied_updates(updates)
```

---

## 7️⃣ BEST PRACTICES

### ✅ DO's:

1. **Design for Immutability First**
   - Avoid updates if possible
   - Use append-only patterns
   - Version your records

2. **Use Proper Time Windows**
   ```
   Consuming Segment Duration: 10-15 minutes
   - Too short: Too many small segments
   - Too long: Longer to seal, higher memory
   ```

3. **Implement Soft Deletes**
   ```sql
   ALTER TABLE logs ADD COLUMN is_deleted BOOLEAN DEFAULT false;
   ```

4. **Partition by Time**
   ```
   OFFLINE segments: Daily or hourly
   ONLINE segments: Every 10-15 minutes
   ```

5. **Monitor Segment Health**
   ```bash
   # Check segment sizes
   curl http://pinot-controller:9000/segments/logs
   
   # Check consuming lag
   curl http://pinot-controller:9000/consumingSegmentsInfo
   ```

### ❌ DON'Ts:

1. **Don't Treat Pinot as OLTP Database**
   - No frequent updates
   - No transaction support
   - Not for operational queries

2. **Don't Make Segments Too Large**
   - Max 500MB-1GB per segment
   - Larger = slower queries
   - Harder to replace

3. **Don't Ignore Consuming Lag**
   ```
   Lag > 1 hour = Problem!
   - Increase parallelism
   - Optimize Kafka consumers
   - Scale up servers
   ```

4. **Don't Mix Update Patterns**
   - Choose ONE pattern (soft delete OR rebuild)
   - Don't combine multiple approaches
   - Consistency is key

---

## 8️⃣ MONITORING & TROUBLESHOOTING

### Key Metrics to Watch:

```sql
-- Segment count by type
SELECT 
    segmentName,
    status,
    COUNT(*) as count
FROM pinot.segments
GROUP BY status;

-- Consuming lag
SELECT 
    tableName,
    partitionId,
    currentOffset,
    latestOffset,
    (latestOffset - currentOffset) as lag
FROM pinot.consumingSegments
WHERE lag > 10000;  -- Alert if lag > 10K messages

-- Query latency by segment type
SELECT 
    segmentType,
    AVG(queryTimeMs) as avg_latency,
    P99(queryTimeMs) as p99_latency
FROM pinot.queryStats
GROUP BY segmentType;
```

---

## 🎯 SUMMARY

| Aspect | Offline Segments | Online Segments |
|--------|-----------------|-----------------|
| **Data Source** | Batch (Hadoop/Spark) | Stream (Kafka/Kinesis) |
| **State** | Immutable | Mutable → Immutable |
| **Storage** | Deep (S3/HDFS) | Hot (Memory/SSD) |
| **Optimization** | Maximum | Moderate |
| **Compression** | High (10-20x) | Low (2-5x) |
| **Query Speed** | Fastest | Fast |
| **Cost** | Low | High |
| **Updates** | Rebuild required | Append during consuming |
| **Use Case** | Historical analysis | Real-time monitoring |

### Update Handling Summary:

| Update Type | Solution | Latency | Cost |
|-------------|----------|---------|------|
| **Late Data** | Time travel versioning | Immediate | Low |
| **Corrections** | Soft delete + reinsert | Minutes | Low |
| **Bulk Updates** | Nightly rebuild | Hours | Medium |
| **GDPR Delete** | Marker + compaction | 24 hours | Medium |
| **Critical Fix** | Emergency rebuild | 1 hour | High |

---

## 🔥 THE GOLDEN RULE

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  If you need frequent updates/deletes:                      │
│  → DON'T use Pinot (use ClickHouse/Druid instead)          │
│                                                             │
│  If you need real-time analytics on append-only data:       │
│  → Pinot is PERFECT!                                        │
│                                                             │
│  If you need both:                                          │
│  → Use Lambda Architecture (batch + stream)                 │
│  → Handle updates outside Pinot                             │
│  → Rebuild segments periodically                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Remember**: Pinot's immutability is not a bug—it's the feature that makes it blazing fast! 🚀
