# Apache Pinot — Segment Updation: Mechanics of Change in an Immutable World

## The Paradox: How Do You "Update" Immutable Data?

Pinot's sealed segments are permanently immutable — no in-place row edits, no deletes, no modifications. Yet production systems require corrections, late-arriving data, schema evolution, and state changes. Pinot resolves this through **segment-level atomic replacement**, **upsert with soft-delete bitmaps**, and **background compaction tasks**.

This document covers the **internal mechanics** — controller orchestration, server-side data structures, comparison logic, and operational workflows.

---

## Table of Contents

1. [Offline Segment Replacement (Push-Replace)](#1-offline-segment-replacement-push-replace)
2. [Real-Time Segment Completion & Replacement](#2-real-time-segment-completion--replacement)
3. [Upsert Internals — The Full Machinery](#3-upsert-internals--the-full-machinery)
4. [Partial Upsert — Column-Level Merging](#4-partial-upsert--column-level-merging)
5. [Delete Support via Upsert](#5-delete-support-via-upsert)
6. [Minion Tasks — Background Compaction Engine](#6-minion-tasks--background-compaction-engine)
7. [Segment Refresh & Reload](#7-segment-refresh--reload)
8. [Schema Evolution Without Downtime](#8-schema-evolution-without-downtime)
9. [Failure Scenarios & Recovery](#9-failure-scenarios--recovery)
10. [Production Patterns & Anti-Patterns](#10-production-patterns--anti-patterns)

---

## 1. Offline Segment Replacement (Push-Replace)

### The Fundamental Mechanism

For offline (batch) tables, "updating" means generating a new segment with corrected data and replacing the old one atomically.

```
┌──────────────────────────────────────────────────────────────────┐
│                  OFFLINE SEGMENT REPLACEMENT FLOW                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  External System (Spark/Flink/Airflow)                            │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────┐                                          │
│  │ Generate New Segment │  (same name OR same time range)          │
│  │ with corrected data  │                                          │
│  └──────────┬──────────┘                                          │
│             │                                                      │
│             ▼                                                      │
│  ┌─────────────────────────────────────────┐                      │
│  │ Upload to Controller                     │                      │
│  │ POST /v2/segments?tableName=X           │                      │
│  └──────────┬──────────────────────────────┘                      │
│             │                                                      │
│             ▼                                                      │
│  ┌─────────────────────────────────────────┐                      │
│  │ Controller Orchestration:                │                      │
│  │   1. Validate segment metadata          │                      │
│  │   2. Upload to deep store (S3)          │                      │
│  │   3. Update ZooKeeper segment ZNode     │                      │
│  │   4. Assign to servers via IdealState   │                      │
│  │   5. Old segment marked for deletion    │                      │
│  └──────────┬──────────────────────────────┘                      │
│             │                                                      │
│             ▼                                                      │
│  ┌─────────────────────────────────────────┐                      │
│  │ Server Actions:                          │                      │
│  │   1. Download new segment from S3       │                      │
│  │   2. Load into memory                   │                      │
│  │   3. Swap query routing atomically      │                      │
│  │   4. Unload old segment                 │                      │
│  │   5. Delete old segment from disk       │                      │
│  └─────────────────────────────────────────┘                      │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Three Replacement Strategies

#### Strategy 1: Same Segment Name (Version Bump)

```
Segment name format: myTable_2026-01-15_2026-01-16_3
                     [table]_[start]_[end]_[sequenceId]

Old: myTable_2026-01-15_2026-01-16_3  (CRC: abc123)
New: myTable_2026-01-15_2026-01-16_3  (CRC: def456)

Controller detects CRC mismatch → triggers replacement
```

The controller compares the CRC checksum. If the segment name matches but CRC differs, it treats this as a replacement, not a duplicate upload.

#### Strategy 2: lineage-based replacement (startReplaceSegments API)

This is the **production-grade** approach for atomic multi-segment replacement:

```
Phase 1: START REPLACEMENT
─────────────────────────
POST /segments/{tableName}/startReplaceSegments
Body: {
  "segmentsFrom": ["seg_day1_v1", "seg_day2_v1"],   // segments to replace
  "segmentsTo": ["seg_day1_v2", "seg_day2_v2"]       // new segments
}
Response: { "segmentLineageEntryId": "entry_12345" }

Phase 2: UPLOAD NEW SEGMENTS
─────────────────────────────
POST /v2/segments?tableName=myTable
(upload seg_day1_v2.tar.gz)
(upload seg_day2_v2.tar.gz)

Phase 3: END REPLACEMENT
─────────────────────────
POST /segments/{tableName}/endReplaceSegments
Body: { "segmentLineageEntryId": "entry_12345" }

→ Controller atomically swaps routing from old → new
→ Old segments scheduled for deletion after retention period
```

**Why this matters in production**: Without the lineage API, there's a window where queries might hit a mix of old and new segments, producing inconsistent results. The lineage protocol guarantees atomic visibility.

#### Strategy 3: Time-Range Based Replacement

```json
// Table config: segmentsConfig
{
  "retentionTimeUnit": "DAYS",
  "retentionTimeValue": "90",
  "segmentPushType": "APPEND",    // or "REFRESH"
  "segmentAssignmentStrategy": "BalanceNumSegmentAssignmentStrategy"
}
```

- **APPEND**: New segments are added alongside existing ones for the same time range
- **REFRESH**: New segments with overlapping time ranges replace old ones automatically

### Controller-Side Replacement Logic (Internal)

```java
// Simplified controller logic for segment replacement
public void handleSegmentUpload(SegmentMetadata newSegment) {
    String tableName = newSegment.getTableName();
    String segmentName = newSegment.getName();
    
    // Check if segment already exists
    SegmentZKMetadata existingZKMetadata = 
        ZKMetadataProvider.getSegmentZKMetadata(tableName, segmentName);
    
    if (existingZKMetadata != null) {
        long existingCRC = existingZKMetadata.getCrc();
        long newCRC = newSegment.getCrc();
        
        if (existingCRC == newCRC) {
            // Same content — skip (idempotent upload)
            return;
        }
        
        // Different content — this is a REPLACEMENT
        // Step 1: Upload new segment to deep store
        pinotFS.copyFromLocalDir(localDir, deepStoreURI);
        
        // Step 2: Update ZK metadata with new CRC, size, indexes
        ZKMetadataUtils.updateSegmentMetadata(zkMetadata, newSegment);
        
        // Step 3: Trigger server reload via state transition
        // ONLINE → ONLINE transition with new download URL
        idealStateHelper.triggerSegmentRefresh(tableName, segmentName);
    }
}
```

### Server-Side Segment Swap (Zero-Downtime)

```
Timeline on a single server:

T0: Serving queries against segment_v1
    ┌──────────────┐
    │  segment_v1  │ ←── query routing active
    └──────────────┘

T1: Download segment_v2 from deep store (background)
    ┌──────────────┐    ┌──────────────┐
    │  segment_v1  │    │  segment_v2  │ (loading, not yet queryable)
    └──────────────┘    └──────────────┘

T2: Atomic swap — query routing changes
    ┌──────────────┐    ┌──────────────┐
    │  segment_v1  │    │  segment_v2  │ ←── query routing active
    └──────────────┘    └──────────────┘
    (unload pending)

T3: Old segment unloaded and deleted from disk
                        ┌──────────────┐
                        │  segment_v2  │ ←── query routing active
                        └──────────────┘

Key: During T1→T2, queries still hit v1 (no gaps)
     At T2, routing switches atomically (no partial state)
     After T3, disk is reclaimed
```

---

## 2. Real-Time Segment Completion & Replacement

### The Segment Completion Protocol

When a CONSUMING segment reaches its threshold, it undergoes a state transition that creates an immutable replacement:

```
CONSUMING SEGMENT LIFECYCLE:
════════════════════════════

State: CONSUMING (mutable, in-memory)
│
│  Records flowing in from Kafka
│  Offset: 1000 → 5000 → 10000 → 50000
│
▼  [Threshold reached: rows.threshold=50000 OR time.threshold=1h]
│
│  COMMIT PROTOCOL BEGINS:
│  ────────────────────────
│  1. Server stops consuming from Kafka partition
│  2. Server builds columnar indexes on in-memory data
│  3. Server serializes to segment tar format
│  4. Server uploads sealed segment to deep store (S3)
│  5. Server notifies controller: "segment committed at offset 50000"
│  6. Controller updates ZK: segment state → ONLINE
│  7. Controller creates new CONSUMING segment starting at offset 50001
│
▼
State: ONLINE (immutable, disk-backed)
```

### What "Replacement" Means for Real-Time Segments

Real-time segments get replaced in two scenarios:

#### Scenario A: Segment Completion (Normal Flow)

The CONSUMING segment is replaced by its own sealed (ONLINE) version. This isn't really an "update" — it's a state transition from mutable to immutable format.

#### Scenario B: Server Failure Recovery

```
Server A was consuming partition 3, building segment_p3_seq5

Server A crashes at offset 45000 (segment not yet committed)

Controller detects: segment stuck in CONSUMING state > threshold

Controller action:
  1. Re-assigns partition 3 to Server B
  2. Server B creates NEW consuming segment for partition 3
  3. Server B starts from last committed offset (start of segment)
  4. Server B re-consumes offsets 0→50000, commits normally
  5. Old incomplete segment on Server A is orphaned and cleaned up
```

This means the same data range might be processed twice during recovery, but the segment replacement is atomic — queries never see partial results.

---

## 3. Upsert Internals — The Full Machinery

### Architecture Overview

Upsert enables "last-writer-wins" semantics in a system of immutable segments. Instead of modifying existing records, it **marks old records as invalid** and **routes queries to the newest version**.

```
┌────────────────────────────────────────────────────────────────┐
│                     UPSERT DATA FLOW                            │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Kafka Partition 0                                               │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ key=user_1, {name:"Alice", age:30}   offset=100     │        │
│  │ key=user_2, {name:"Bob", age:25}     offset=101     │        │
│  │ key=user_1, {name:"Alice", age:31}   offset=200     │  ←UPDATE│
│  └───────────────────────────┬─────────────────────────┘        │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────┐          │
│  │           SERVER (Partition Owner)                  │          │
│  │                                                     │          │
│  │  ┌─────────────────────────────────────────────┐   │          │
│  │  │     PRIMARY KEY LOOKUP TABLE (ConcurrentMap) │   │          │
│  │  │                                               │   │          │
│  │  │  user_1 → {segment: seg_3, docId: 42,        │   │          │
│  │  │            comparisonValue: 200}              │   │          │
│  │  │  user_2 → {segment: seg_2, docId: 17,        │   │          │
│  │  │            comparisonValue: 101}              │   │          │
│  │  └─────────────────────────────────────────────┘   │          │
│  │                                                     │          │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────┐   │          │
│  │  │  Segment 1   │  │  Segment 2   │  │ Seg 3  │   │          │
│  │  │ (sealed)     │  │ (sealed)     │  │(active)│   │          │
│  │  │              │  │              │  │        │   │          │
│  │  │ validDocIds: │  │ validDocIds: │  │        │   │          │
│  │  │ [0,1,0,1,1] │  │ [1,1,0,1,0] │  │        │   │          │
│  │  └──────────────┘  └──────────────┘  └────────┘   │          │
│  │                                                     │          │
│  └───────────────────────────────────────────────────┘          │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### The validDocIds Bitmap — Core Data Structure

Each segment maintains a **RoaringBitmap** called `validDocIds` that tracks which document IDs (rows) are still "alive":

```
Segment: orders_realtime_p0_seq3
Total docs: 10,000

validDocIds bitmap:
  Position:  0  1  2  3  4  5  6  7  8  9 ...
  Bit:       1  1  0  1  1  0  1  1  1  0 ...
             ↑        ↑        ↑           ↑
           alive   replaced  alive     replaced

Query execution:
  SELECT * FROM orders WHERE region='US'
  
  Step 1: Apply column predicates → candidate docIds = [0, 2, 5, 7, 9]
  Step 2: AND with validDocIds bitmap → final docIds = [0, 7]
  Step 3: Return only docs 0 and 7
```

**Memory cost**: ~1 bit per document. For a segment with 1M docs, validDocIds costs ~125 KB.

### Primary Key Index — Record Location Tracker

The primary key index is a **server-level ConcurrentHashMap** that maps each primary key to its current location:

```java
// Internal structure (simplified)
class RecordLocation {
    IndexSegment segment;      // which segment contains the latest version
    int docId;                 // document ID within that segment
    long comparisonValue;      // timestamp or sequence for ordering
}

ConcurrentHashMap<PrimaryKey, RecordLocation> primaryKeyIndex;
```

**Memory cost per key**:
- PrimaryKey object: ~40 bytes (for a single column key like user_id)
- RecordLocation: ~32 bytes
- HashMap overhead: ~48 bytes per entry
- **Total: ~120 bytes per unique primary key**

For 100M unique keys: ~12 GB heap just for the upsert index.

### The Upsert Decision Algorithm

```
NEW RECORD ARRIVES: {pk: "user_1", comparison: 200, data: {...}}

Step 1: LOOKUP
────────────────
  existing = primaryKeyIndex.get("user_1")
  
  Case A: existing == null
    → First time seeing this key
    → Insert record normally
    → Update primaryKeyIndex: "user_1" → {currentSegment, newDocId, 200}
    → DONE

  Case B: existing != null AND existing.comparisonValue < 200
    → New record is NEWER (wins)
    → Insert new record into current consuming segment
    → Mark old record as invalid:
        existing.segment.validDocIds.remove(existing.docId)
    → Update primaryKeyIndex: "user_1" → {currentSegment, newDocId, 200}
    → DONE
    
  Case C: existing != null AND existing.comparisonValue >= 200
    → New record is OLDER or SAME (loses — out of order)
    → FULL mode: Discard the new record entirely
    → PARTIAL mode: Still discard (comparison column determines winner)
    → DONE (new record is dead on arrival)
```

### Comparison Column — The Ordering Mechanism

The comparison column determines which version of a record "wins":

```json
{
  "upsertConfig": {
    "mode": "FULL",
    "comparisonColumns": ["updated_at"]
  }
}
```

**Single comparison column** (default):
- Higher value wins
- Typical: timestamp, sequence number, Kafka offset

**Multiple comparison columns** (Pinot 0.12+):
```json
{
  "comparisonColumns": ["updated_at", "version"]
}
```
- Compared lexicographically: first column is primary comparator
- Tie-breaking: if updated_at is equal, version determines winner

**No comparison column specified**:
- Uses **Kafka offset** as implicit comparison value
- Later offset always wins (monotonically increasing)

### Upsert During Segment Sealing

When a consuming segment seals, its upsert state must be preserved:

```
BEFORE SEALING:
  Consuming Segment (seq=5):
    doc 0: pk=A, valid
    doc 1: pk=B, valid  
    doc 2: pk=A, valid (newer version, doc 0 already invalidated in seg 4)
    doc 3: pk=C, valid

  Primary Key Index:
    A → {seg5, doc2}
    B → {seg5, doc1}
    C → {seg5, doc3}

AFTER SEALING:
  Sealed Segment (seq=5):
    validDocIds: [0=false, 1=true, 2=true, 3=true]
    (doc 0 might have been invalidated by a newer record arriving later)
    
  Primary Key Index:
    A → {seg5, doc2}   ← still points here until a newer version arrives
    B → {seg5, doc1}
    C → {seg5, doc3}
    
  New Consuming Segment (seq=6):
    (starts empty, ready for new records)
```

### Snapshot During Segment Completion

For DOWNLOAD mode segment completion, the server must take a snapshot of the validDocIds at seal time:

```
Server persists with segment:
  segment_metadata.properties:
    validDocIds.snapshot.offset = 50000  (Kafka offset at seal time)
    
  validDocIds.bitmap:
    (serialized RoaringBitmap of valid docs at seal time)
```

When another server downloads this segment, it loads the bitmap and then applies any later invalidations from its own primary key index.

---

## 4. Partial Upsert — Column-Level Merging

### Full vs Partial Upsert

```
FULL UPSERT:
  Old record: {pk:"user_1", name:"Alice", age:30, email:"a@x.com"}
  New record: {pk:"user_1", name:"Alice", age:31, email:null}
  Result:     {pk:"user_1", name:"Alice", age:31, email:null}
  → Entire old record replaced (including null fields)

PARTIAL UPSERT:
  Old record: {pk:"user_1", name:"Alice", age:30, email:"a@x.com"}
  New record: {pk:"user_1", name:null,    age:31, email:null}
  Result:     {pk:"user_1", name:"Alice", age:31, email:"a@x.com"}
  → Only non-null fields from new record are applied
  → Null fields retain their previous values
```

### Partial Upsert Configuration

```json
{
  "upsertConfig": {
    "mode": "PARTIAL",
    "partialUpsertStrategies": {
      "name": "OVERWRITE",
      "age": "OVERWRITE",
      "total_orders": "INCREMENT",
      "last_login": "MAX",
      "first_seen": "MIN",
      "tags": "UNION",
      "email": "IGNORE"
    },
    "defaultPartialUpsertStrategy": "OVERWRITE",
    "comparisonColumns": ["updated_at"]
  }
}
```

### Merge Strategies Available

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| OVERWRITE | New value replaces old (if non-null) | Most fields |
| IGNORE | Always keep old value | Immutable fields like created_at |
| INCREMENT | new = old + delta | Counters (total_orders, page_views) |
| APPEND | new = old + new (for multi-value) | Adding tags, categories |
| UNION | new = set(old) ∪ set(new) | Deduped multi-value fields |
| MAX | keep max(old, new) | Latest timestamp |
| MIN | keep min(old, new) | First occurrence |

### How Partial Upsert Works Internally

```
Step 1: New partial record arrives: {pk:"u1", age:31, total_orders:1}

Step 2: Look up existing location
  primaryKeyIndex.get("u1") → {segment: seg3, docId: 42}

Step 3: Read existing record from seg3, doc 42
  existing = {pk:"u1", name:"Alice", age:30, total_orders:100, email:"a@x.com"}

Step 4: Apply merge strategies per column:
  name:         null (new) + "Alice" (old)    → OVERWRITE → "Alice" (keep old, new is null)
  age:          31 (new) + 30 (old)           → OVERWRITE → 31
  total_orders: 1 (new) + 100 (old)           → INCREMENT → 101
  email:        null (new) + "a@x.com" (old)  → OVERWRITE → "a@x.com" (keep old)

Step 5: Write MERGED record to consuming segment:
  {pk:"u1", name:"Alice", age:31, total_orders:101, email:"a@x.com"}
  
Step 6: Invalidate old record in seg3
  seg3.validDocIds.remove(42)

Step 7: Update primary key index
  primaryKeyIndex.put("u1", {currentSeg, newDocId, newComparison})
```

**Critical implication**: Partial upsert requires **reading from sealed segments** during ingestion. This means:
- The segment must be loaded on the same server (partition affinity required)
- Cross-segment reads add latency to ingestion
- Memory-mapped segments help avoid disk I/O for these reads

---

## 5. Delete Support via Upsert

### Soft Deletes Using Delete Column

Pinot supports "deleting" records by marking them with a special column:

```json
{
  "upsertConfig": {
    "mode": "FULL",
    "deleteRecordColumn": "is_deleted",
    "comparisonColumns": ["updated_at"]
  }
}
```

### How Delete Works

```
Record in Pinot:    {pk:"order_1", status:"active", is_deleted:false}

Delete event arrives from Kafka:
  {pk:"order_1", is_deleted:true, updated_at: newer_timestamp}

Pinot's actions:
  1. Normal upsert logic applies (new record wins based on comparison)
  2. New record written to consuming segment with is_deleted=true
  3. Old record invalidated in validDocIds
  4. Query layer: filters out records where is_deleted=true
  
Post-compaction:
  Records with is_deleted=true are physically removed from segments
```

### Query Filtering for Deletes

```
Query: SELECT * FROM orders WHERE region='US'

Internal execution:
  1. Apply predicate: region='US' → docIds [0, 3, 7, 12]
  2. Apply validDocIds bitmap → docIds [0, 7, 12]
  3. Apply delete filter: is_deleted != true → docIds [0, 12]
  4. Return docs 0, 12
```

The delete filter is an additional scan cost on every query — this is why compaction matters.

---

## 6. Minion Tasks — Background Compaction Engine

### What Are Minion Tasks?

Minions are **worker processes** that execute background maintenance jobs. They run as separate JVM processes (not on servers or controllers) to avoid impacting query latency.

```
┌──────────────────────────────────────────────────────────┐
│                    PINOT CLUSTER                           │
│                                                            │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐       │
│  │ Controller │   │  Server 1  │   │  Server 2  │       │
│  │            │   │ (queries)  │   │ (queries)  │       │
│  └─────┬──────┘   └────────────┘   └────────────┘       │
│        │                                                   │
│        │ Schedules tasks                                   │
│        ▼                                                   │
│  ┌────────────┐   ┌────────────┐                         │
│  │  Minion 1  │   │  Minion 2  │   (worker pool)        │
│  │            │   │            │                         │
│  │ - Download │   │ - Download │                         │
│  │   segment  │   │   segment  │                         │
│  │ - Process  │   │ - Process  │                         │
│  │ - Upload   │   │ - Upload   │                         │
│  └────────────┘   └────────────┘                         │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### Task 1: MergeRollupTask

Merges small segments and rolls up (pre-aggregates) data to reduce segment count and improve query performance.

```json
// Table config
{
  "task": {
    "taskTypeConfigsMap": {
      "MergeRollupTask": {
        "input.filter.function": "lastCompletedAt > ago('P1D')",
        "merge.type": "ROLLUP",
        "merge.rollup.aggregation.columnName.count": "SUM",
        "merge.rollup.aggregation.columnName.revenue": "SUM",
        "merge.rollup.aggregation.columnName.latency_p99": "MAX",
        "roundBucketTimePeriod": "1d",
        "maxNumRecordsPerSegment": "5000000",
        "maxNumRecordsPerTask": "50000000"
      }
    }
  }
}
```

**What happens internally**:
```
BEFORE MERGE:
  seg_hour_00 (5,000 rows)  — granularity: per-event
  seg_hour_01 (3,000 rows)
  seg_hour_02 (8,000 rows)
  seg_hour_03 (4,000 rows)
  Total: 4 segments, 20,000 rows

AFTER ROLLUP (merge by day):
  seg_day_2026-01-15 (500 rows) — granularity: per-minute aggregates
  Total: 1 segment, 500 rows

Rollup groups by: [timestamp_bucket, dimension1, dimension2]
Aggregates: SUM(count), SUM(revenue), MAX(latency_p99)
```

### Task 2: RealtimeToOfflineTask

Converts sealed real-time segments into optimized offline segments (better compression, sorted, with star-tree indexes).

```json
{
  "task": {
    "taskTypeConfigsMap": {
      "RealtimeToOfflineSegmentsTask": {
        "bucketTimePeriod": "1d",
        "bufferTimePeriod": "2d",
        "roundBucketTimePeriod": "1d",
        "mergeType": "CONCAT",
        "maxNumRecordsPerSegment": "10000000"
      }
    }
  }
}
```

**Flow**:
```
Real-time segments (small, many, not fully optimized):
  rt_seg_p0_seq100 (committed 2h ago)
  rt_seg_p0_seq101 (committed 1.5h ago)
  rt_seg_p0_seq102 (committed 1h ago)
  rt_seg_p1_seq50  (committed 2h ago)
  
  ↓ RealtimeToOfflineTask runs (buffer: 2 days ago)
  
Offline segments (large, few, fully optimized):
  offline_seg_2026-01-13_0   (sorted, star-tree, dictionary-encoded)
  
  + Real-time segments for recent data still exist
  + Old real-time segments deleted after conversion
```

**Why convert?** Offline segments have:
- Sorted data (better compression ratio: 5-10x)
- Star-tree indexes (pre-aggregated for common queries)
- Optimal dictionary encoding (built with full knowledge of value distribution)
- Fewer segments to scan (merged from many small segments)

### Task 3: UpsertCompactionTask

For upsert tables, removes invalidated records and reclaims space:

```json
{
  "task": {
    "taskTypeConfigsMap": {
      "UpsertCompactionTask": {
        "invalidRecordsThresholdPercent": "30",
        "invalidRecordsThresholdCount": "100000"
      }
    }
  }
}
```

**What happens**:
```
BEFORE COMPACTION:
  Segment seg_p0_seq5:
    Total docs: 100,000
    validDocIds: 65,000 set (65% valid)
    Invalid docs: 35,000 (35% wasted space)
    
  Trigger: invalidRecordsThresholdPercent > 30% → compact!

COMPACTION PROCESS:
  1. Minion downloads seg_p0_seq5 from deep store
  2. Reads validDocIds bitmap
  3. Creates NEW segment with ONLY valid records
  4. Rebuilds all indexes on the subset
  5. Uploads new segment to deep store
  6. Controller performs atomic replacement

AFTER COMPACTION:
  Segment seg_p0_seq5 (replaced):
    Total docs: 65,000
    validDocIds: all set (100% valid)
    Space saved: ~35% reduction
```

### Task 4: PurgeTask

Permanently removes records matching a predicate (GDPR compliance):

```json
{
  "task": {
    "taskTypeConfigsMap": {
      "PurgeTask": {
        "numTasks": "4"
      }
    }
  }
}
```

Triggered via API:
```bash
POST /tasks/schedule?taskType=PurgeTask&tableName=users_OFFLINE
Body: {
  "purgeFilter": "user_id IN ('user_123', 'user_456')"
}
```

The minion downloads each segment, removes matching records, rebuilds the segment, and uploads the replacement.

### Task Scheduling

```json
{
  "task": {
    "taskTypeConfigsMap": {
      "MergeRollupTask": { ... }
    },
    "schedulerEnabled": true,
    "frequencyPeriod": "1h"
  }
}
```

Or trigger manually:
```bash
POST /tasks/schedule?taskType=MergeRollupTask&tableName=events_OFFLINE
```

### Task Execution Model

```
Controller (Scheduler):
  1. Determine which segments need processing (based on config thresholds)
  2. Generate task configs: [{segment: X, action: merge}, {segment: Y, ...}]
  3. Submit to Helix task framework
  4. Helix assigns tasks to available minion workers

Minion (Worker):
  1. Receive task assignment
  2. Download source segment(s) from deep store
  3. Process (merge/compact/purge/convert)
  4. Upload result segment to deep store
  5. Notify controller: task complete
  6. Controller triggers segment replacement on servers

Parallelism:
  - Multiple minions can process different segments concurrently
  - One segment is processed by exactly one minion (no conflicts)
  - Controller ensures no two tasks target the same segment simultaneously
```

---

## 7. Segment Refresh & Reload

### When Refresh Happens

Segment refresh re-downloads and re-loads a segment on a server. It does NOT change the segment content — it ensures the server has the latest version.

Triggers:
1. **ZK metadata change**: Controller updates segment CRC → servers detect mismatch → refresh
2. **Manual API call**: `POST /segments/{tableName}/{segmentName}/reload`
3. **Table-level reload**: `POST /segments/{tableName}/reload`
4. **Schema change**: Adding a new index type triggers rebuild + reload
5. **Server restart**: Downloads all assigned segments from deep store

### Reload vs Refresh vs Replace

| Operation | What Changes | Initiated By | Downtime |
|-----------|-------------|--------------|----------|
| Reload | Server re-downloads same segment from deep store | Admin API call | None (swap) |
| Refresh | Server detects CRC mismatch, re-downloads | ZK watch trigger | None (swap) |
| Replace | New segment version uploaded, old deleted | Segment upload | None (swap) |

### Adding Indexes to Existing Segments

You can add inverted indexes, range indexes, or text indexes to existing segments without re-ingesting data:

```json
// Update table config to add inverted index on "status" column
{
  "tableIndexConfig": {
    "invertedIndexColumns": ["status", "region"],
    "rangeIndexColumns": ["amount"],
    "bloomFilterColumns": ["user_id"]
  }
}
```

After updating config:
```bash
# Trigger reload — servers rebuild indexes locally
POST /segments/orders_OFFLINE/reload

# What happens on each server:
# 1. Read segment from disk
# 2. Build new inverted index for "status" column
# 3. Build range index for "amount"
# 4. Build bloom filter for "user_id"
# 5. Write updated segment to disk
# 6. Swap queryable reference atomically
```

The server builds the index locally without downloading from deep store — it uses its existing local copy.

---

## 8. Schema Evolution Without Downtime

### Adding Columns

```json
// Add new column to schema
POST /schemas
Body: {
  "schemaName": "orders",
  "dimensionFieldSpecs": [
    ... existing fields ...,
    {"name": "priority", "dataType": "STRING", "defaultNullValue": "NORMAL"}
  ]
}
```

What happens:
```
1. Schema updated in ZK
2. Existing segments: DON'T have the column
   → Queries against "priority" return defaultNullValue ("NORMAL")
3. New segments: WILL have the column
   → Records ingested after schema change include "priority"
4. To backfill old segments: run batch job to regenerate them

Query handling:
  SELECT priority FROM orders
  
  Segment seg_old (no priority column):
    → Returns "NORMAL" for all rows (default null value)
  
  Segment seg_new (has priority column):
    → Returns actual values
```

### Removing Columns

You cannot remove a column from existing segments. Steps:
1. Remove column from schema
2. Remove from table config (indexes, etc.)
3. Old segments still contain the data (wasted space)
4. Run RealtimeToOfflineTask or manual segment rebuild to physically remove

### Changing Column Types

Not supported in-place. Requires:
1. Add new column with desired type
2. Backfill via batch job
3. Remove old column from schema
4. Rebuild segments to reclaim space

---

## 9. Failure Scenarios & Recovery

### Scenario 1: Minion Task Fails Mid-Processing

```
Problem: Minion downloads segment, starts processing, crashes

Recovery:
  - Helix detects minion heartbeat loss
  - Task state: RUNNING → ERROR
  - Controller reschedules task to another minion
  - No data corruption (source segment untouched in deep store)
  - Idempotent: re-running produces same result
```

### Scenario 2: Segment Replace Upload Succeeds but ZK Update Fails

```
Problem: New segment in S3, but ZK still points to old version

Recovery:
  - Controller detects inconsistency during periodic validation
  - Segment lineage entry status: IN_PROGRESS (timeout)
  - Admin can retry: POST /segments/{table}/endReplaceSegments
  - Or revert: POST /segments/{table}/revertReplaceSegments
  - Deep store has both versions (old not yet deleted)
```

### Scenario 3: Upsert Primary Key Index Corruption

```
Problem: Server crash during upsert processing, index partially updated

Recovery:
  - On restart, server must REBUILD primary key index
  - Process: scan ALL segments for the partition, reconstruct index
  - For each record in each segment:
      If validDocIds[docId] == true:
        primaryKeyIndex.put(pk, {segment, docId, comparisonValue})
  - Order: process segments oldest-first so newest wins
  - Duration: O(total_records_in_partition) — can take minutes for large tables
  
  Optimization (Pinot 0.12+):
  - Persist primary key index snapshots to disk periodically
  - On restart, load snapshot + replay only segments committed after snapshot
  - Reduces rebuild time from minutes to seconds
```

### Scenario 4: Out-of-Order Arrivals with Upsert

```
Problem: Events arrive out of order due to Kafka partition rebalancing

Timeline:
  T1: Record {pk:A, comparison:100} arrives → stored
  T2: Record {pk:A, comparison:200} arrives → replaces (wins)
  T3: Record {pk:A, comparison:150} arrives → DISCARDED (loses to 200)

This is CORRECT behavior:
  - comparison=200 is the latest version
  - comparison=150 arriving late is stale data
  - Discard prevents regression to older state

If you need ALL events (not just latest):
  - Use append-only table (no upsert)
  - Or use versioned records pattern with query-time dedup
```

### Scenario 5: Compaction During Active Queries

```
Problem: UpsertCompactionTask replaces segment while queries are running

Safety guarantee:
  1. New compacted segment uploaded to deep store
  2. Controller updates IdealState in ZK
  3. Server downloads new segment in background
  4. Server swaps query routing atomically
  5. In-flight queries on old segment complete normally
  6. After last in-flight query finishes, old segment is released

  → No query ever sees partial state
  → No query fails due to missing segment
  → Brief period where both versions exist on disk (extra space)
```

---

## 10. Production Patterns & Anti-Patterns

### Pattern: Tiered Updation Strategy

```
┌─────────────────────────────────────────────────────────┐
│              TIERED UPDATE ARCHITECTURE                   │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  HOT (0-2 hours):  Real-time upsert table               │
│    - Latest data, upsert mode for corrections            │
│    - High write throughput, slightly higher query cost    │
│                                                           │
│  WARM (2h - 7 days): Converted offline segments         │
│    - RealtimeToOfflineTask compacts and optimizes        │
│    - Star-tree indexes added for fast aggregation        │
│    - Upsert compaction removes invalidated records       │
│                                                           │
│  COLD (7+ days): Rolled-up archive segments             │
│    - MergeRollupTask aggregates to hourly/daily          │
│    - Minimal segments, maximum compression               │
│    - Rarely updated (only for corrections/GDPR)          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Anti-Pattern: High-Cardinality Primary Keys with Upsert

```
Problem:
  - 500M unique user_ids with upsert
  - Primary key index: 500M × 120 bytes = 60 GB heap
  - GC pauses: 2-5 seconds during major GC
  - Query latency spikes correlate with GC

Solutions:
  1. Partition by primary key to distribute index across servers
  2. Use off-heap primary key storage (RocksDB-backed, Pinot 1.0+)
  3. Set TTL on primary key entries for keys that stop updating
  4. Consider if upsert is truly needed vs. append + query-time dedup
```

### Anti-Pattern: Frequent Full Segment Replacement

```
Problem:
  - Hourly batch job replaces all segments (100+ segments)
  - Each replacement: download from S3 + load + swap
  - Cumulative: servers spend 50% of time loading segments

Solutions:
  1. Use lineage API for atomic multi-segment replacement (single swap)
  2. Replace only segments with actual data changes (diff-based)
  3. Increase segment granularity (daily instead of hourly)
  4. Stagger replacements across hours to spread server load
```

### Pattern: Correction Workflow for Offline Tables

```bash
# Production correction workflow

# Step 1: Identify affected segments
GET /segments/orders_OFFLINE
# Response: list of segment names with time ranges

# Step 2: Start atomic replacement
POST /segments/orders_OFFLINE/startReplaceSegments
Body: {
  "segmentsFrom": ["orders_2026-01-15_0", "orders_2026-01-15_1"],
  "segmentsTo": ["orders_2026-01-15_corrected_0"]
}
# Response: {"segmentLineageEntryId": "abc123"}

# Step 3: Generate corrected segment (in your batch system)
# spark-submit ... --output /tmp/corrected_segment/

# Step 4: Upload corrected segment
POST /v2/segments?tableName=orders_OFFLINE
# (multipart upload of corrected segment tar.gz)

# Step 5: Commit replacement
POST /segments/orders_OFFLINE/endReplaceSegments
Body: {"segmentLineageEntryId": "abc123"}

# Step 6: Verify
GET /segments/orders_OFFLINE/orders_2026-01-15_corrected_0/metadata
# Confirm: segment is ONLINE, correct row count, correct CRC
```

### Production Monitoring for Update Operations

| Metric | Alert Threshold | Meaning |
|--------|----------------|---------|
| `pinot_server_upsertPrimaryKeyCount` | >80% of estimated max | Primary key index approaching memory limit |
| `pinot_server_upsertOutOfOrderCount` | Sudden spike | Kafka rebalancing or producer issues |
| `pinot_minion_taskInProgress` | >30 min for compaction | Task stuck or overloaded minion |
| `pinot_server_segmentReloadTimeMs` | >60s | Large segment or slow deep store |
| `pinot_controller_segmentReplacementDurationMs` | >5 min | Replacement hanging, check ZK |
| `pinot_server_validDocIdsPercent` | <50% for any segment | Segment needs compaction urgently |
| `pinot_server_upsertPreloadTimeMs` | >5 min on restart | Primary key index rebuild is slow |

---

## Summary: When to Use Each Update Mechanism

| Scenario | Mechanism | Config |
|----------|-----------|--------|
| Batch data correction | Segment replacement (lineage API) | segmentPushType: REFRESH |
| Real-time state changes | Upsert (FULL mode) | upsertConfig.mode: FULL |
| Partial field updates | Upsert (PARTIAL mode) | upsertConfig.mode: PARTIAL |
| Record deletion (GDPR) | Delete column + compaction | deleteRecordColumn |
| Data compaction | UpsertCompactionTask | task.taskTypeConfigsMap |
| Small → large segment merge | MergeRollupTask | merge.type: CONCAT/ROLLUP |
| RT → optimized offline | RealtimeToOfflineTask | bucketTimePeriod |
| Add index to existing data | Reload API | tableIndexConfig + reload |
| Schema evolution | Schema API + default values | defaultNullValue |

---

## Key Insight: Immutability Enables Simplicity

Every "update" mechanism in Pinot follows the same fundamental pattern:

```
1. Create new version (segment, record, bitmap state)
2. Make new version visible atomically
3. Garbage collect old version in background

Never:
- Modify data in place
- Hold locks during writes
- Block readers during updates
```

This pattern is what allows Pinot to serve analytical queries at sub-second latency even during heavy write loads — readers never contend with writers because they never touch the same data structures simultaneously.
