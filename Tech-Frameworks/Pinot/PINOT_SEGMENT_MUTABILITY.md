# 🔒 Pinot Segment Mutability - The Complete Truth

## ❓ Key Question: Are Sealed Segments Immutable?

**SHORT ANSWER**: YES! Once a segment is sealed (whether online or offline), it is **100% IMMUTABLE**.

---

## 🎯 The Golden Rule of Pinot

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   ALL SEALED SEGMENTS ARE IMMUTABLE                     │
│                                                         │
│   ✓ Offline Segments: Immutable                         │
│   ✓ Online Sealed Segments: Immutable                   │
│   ✗ Updates: NOT ALLOWED on ANY sealed segment          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Segment States and Mutability

### 1️⃣ CONSUMING Segment (Real-Time ONLY)
```
State: CONSUMING
Type: Real-Time / Online
Mutable: ✅ YES (ONLY state that allows writes)
Location: Memory (Heap/Off-Heap)
Duration: Until segment size/time threshold reached
```

**What You Can Do**:
- ✅ **INSERT**: New records continuously added
- ✅ **APPEND**: Stream data arrives and gets added
- ❌ **UPDATE**: Not supported (even in consuming state)
- ❌ **DELETE**: Not supported

**Example**:
```
Kafka Stream → Pinot Server → CONSUMING Segment
                               ↓ (accumulating)
                               10,000 rows
                               20,000 rows
                               50,000 rows
                               ↓ (threshold reached)
                               Sealed!
```

---

### 2️⃣ ONLINE Segment (Sealed)
```
State: ONLINE
Type: Real-Time segment that was sealed
Mutable: ❌ NO (100% immutable)
Location: Disk
Duration: Permanent (until manually deleted/replaced)
```

**What You Can Do**:
- ✅ **READ**: Query anytime
- ❌ **INSERT**: Cannot add new rows
- ❌ **UPDATE**: Cannot modify existing rows
- ❌ **DELETE**: Cannot delete individual rows
- ⚠️ **REPLACE**: Can only replace entire segment

**Example Timeline**:
```
Time 00:00  →  CONSUMING segment (mutable)
               Rows: 0 → 10K → 50K
Time 00:15  →  Threshold reached, SEAL triggered
               Segment becomes ONLINE (immutable forever)
Time 00:16  →  New CONSUMING segment starts
               Old segment: ONLINE, read-only
```

---

### 3️⃣ OFFLINE Segment
```
State: OFFLINE
Type: Batch-loaded historical data
Mutable: ❌ NO (100% immutable from birth)
Location: Disk
Duration: Permanent (until manually deleted/replaced)
```

**What You Can Do**:
- ✅ **READ**: Query anytime
- ❌ **INSERT**: Cannot add rows
- ❌ **UPDATE**: Cannot modify rows
- ❌ **DELETE**: Cannot delete rows
- ⚠️ **REPLACE**: Can only replace entire segment

---

## 🔍 Deep Dive: Why Are Sealed Segments Immutable?

### 1. **Columnar Storage Optimization**

When a segment is sealed:
```
Original Data in Memory (CONSUMING):
Row 1: [col1, col2, col3, col4]
Row 2: [col1, col2, col3, col4]
Row 3: [col1, col2, col3, col4]

Sealed on Disk (ONLINE/OFFLINE):
Column 1: [val1, val2, val3] → Compressed with LZ4
Column 2: [val1, val2, val3] → Dictionary encoded
Column 3: [val1, val2, val3] → Run-length encoded
Column 4: [val1, val2, val3] → Bitmap indexed
```

**Why immutable?**
- Compression is optimized for the exact data
- Indexes are built for specific value distribution
- Updating one row would require:
  1. Decompress entire column
  2. Update value
  3. Rebuild indexes
  4. Re-compress with potentially different ratio
  5. **Result**: Destroys all optimizations!

### 2. **Forward Index Structure**

```
Forward Index (Document ID → Values):
┌──────┬─────────────┬─────────────┬─────────────┐
│ Doc  │  Column 1   │  Column 2   │  Column 3   │
├──────┼─────────────┼─────────────┼─────────────┤
│  0   │   Value A   │   Value X   │   Value P   │
│  1   │   Value B   │   Value Y   │   Value Q   │
│  2   │   Value C   │   Value Z   │   Value R   │
└──────┴─────────────┴─────────────┴─────────────┘
       ↑
       Tightly packed, sequential storage
```

**To update row 1**:
- Would need to shift all subsequent rows
- Or leave gaps (wastes space, fragments data)
- Breaks sequential I/O patterns
- **Solution**: Don't allow updates!

### 3. **Inverted Index Structure**

```
Inverted Index (Value → Document IDs):
┌──────────┬────────────────────────────────┐
│  Value   │      Document IDs (Bitmap)     │
├──────────┼────────────────────────────────┤
│ Value A  │  [0, 5, 10, 15, 20, ...]       │
│ Value B  │  [1, 6, 11, 16, 21, ...]       │
│ Value C  │  [2, 7, 12, 17, 22, ...]       │
└──────────┴────────────────────────────────┘
```

**To update doc 1 from "Value B" to "Value A"**:
1. Remove doc 1 from "Value B" bitmap
2. Add doc 1 to "Value A" bitmap
3. Rebuild bitmap compression
4. Update all affected index nodes
5. **Result**: Expensive and complex!

### 4. **Star-Tree Index**

```
Star-Tree (Pre-aggregated data):
service_name=api, status=200, region=us → count=1000, sum=5000ms
service_name=api, status=500, region=eu → count=50, sum=2000ms
```

**To update one row**:
- Affects multiple pre-aggregated nodes
- Need to recalculate aggregations
- Rebuild entire star-tree branch
- **Result**: Defeats purpose of pre-aggregation!

---

## 🚫 What Happens If You Try to Update?

### Scenario: Update a row in a sealed segment

```bash
# Attempt to update
UPDATE myTable 
SET status = 'completed' 
WHERE order_id = '12345';
```

**Pinot's Response**:
```
❌ ERROR: Updates are not supported on sealed segments
```

**Why?**
```
1. Pinot checks: Is segment sealed?
   └─→ YES: Reject immediately
   └─→ NO (CONSUMING): Still reject (updates not supported)

2. Design Philosophy:
   "Append-only, immutable data for maximum query performance"
```

---

## 🔄 How to "Update" Data in Pinot (Workarounds)

Since updates aren't allowed, here are the patterns:

### Pattern 1: Upsert (Partial Support)

**Available in**: Pinot 0.11.0+ with Upsert-enabled tables

```sql
-- Table configuration
"tableIndexConfig": {
  "enableDefaultStarTree": false,
  "enableDynamicStarTreeCreation": false,
  "upsertConfig": {
    "mode": "FULL",  // or "PARTIAL"
    "primaryKeyColumns": ["order_id"],
    "comparisonColumn": "updated_at"
  }
}
```

**How it works**:
```
1. New record arrives with same primary key
2. Pinot marks old record as "deleted" (soft delete)
3. Adds new record
4. Query layer filters out deleted records
5. Background task eventually compacts segments
```

**Limitations**:
- ⚠️ Only works for REAL-TIME tables
- ⚠️ Increased memory usage (keeps deleted records)
- ⚠️ Slower queries (must filter deleted records)
- ⚠️ Requires compaction to reclaim space
- ❌ NOT available for OFFLINE segments

---

### Pattern 2: Reload Entire Segment

**For OFFLINE segments**:

```bash
# Step 1: Generate new segment with updated data
java -jar pinot-admin.jar CreateSegment \
  -dataDir /path/to/updated/data \
  -segmentName segment_2026-01-18_v2 \
  -tableName myTable \
  -format CSV

# Step 2: Upload new segment
curl -X POST \
  -F file=@segment_2026-01-18_v2.tar.gz \
  http://pinot-controller:9000/v2/segments

# Step 3: Delete old segment
curl -X DELETE \
  http://pinot-controller:9000/segments/myTable/segment_2026-01-18_v1
```

**Process**:
```
Old Segment (Immutable):
[Row 1: order_id=123, status=pending]  ← Want to update this
[Row 2: order_id=456, status=completed]
        ↓
Generate new segment from source with updates
        ↓
New Segment (Immutable):
[Row 1: order_id=123, status=completed]  ← Updated!
[Row 2: order_id=456, status=completed]
        ↓
Upload new, delete old → Atomic swap
```

---

### Pattern 3: Versioned Records (Append-Only)

**Best Practice for Audit Trails**:

```sql
-- Table schema
CREATE TABLE order_events (
  order_id STRING,
  status STRING,
  updated_at TIMESTAMP,
  version INT,
  is_latest BOOLEAN  -- Denormalized flag
) WITH (
  ...
)
```

**Insert pattern**:
```sql
-- Original insert
INSERT: order_id=123, status=pending, version=1, is_latest=true

-- "Update" = Insert new version
INSERT: order_id=123, status=processing, version=2, is_latest=true

-- Query latest only
SELECT * FROM order_events 
WHERE is_latest = true;

-- Query history
SELECT * FROM order_events 
WHERE order_id = 123 
ORDER BY version DESC;
```

**Benefits**:
- ✅ Full history preserved
- ✅ No segment reloading needed
- ✅ Works with both ONLINE and OFFLINE
- ⚠️ Increased storage (keeps all versions)

---

### Pattern 4: Hybrid Architecture (Recommended)

**Lambda Architecture with Pinot**:

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  PostgreSQL/MySQL (OLTP)                            │
│  - Source of truth                                  │
│  - Supports updates, deletes                        │
│  - Stores current state                             │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ├─── Change Data Capture (CDC)
                   │    (Debezium, Maxwell, etc.)
                   ↓
┌─────────────────────────────────────────────────────┐
│  Kafka (Event Stream)                               │
│  - Captures all changes                             │
│  - order.updated, order.created, order.deleted      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────┐
│  Apache Pinot (OLAP - Analytics)                    │
│  - Real-time ingestion from Kafka                   │
│  - Immutable segments                               │
│  - Blazing fast aggregations                        │
│  - No updates needed                                │
└─────────────────────────────────────────────────────┘
```

**Example Flow**:
```
1. User updates order in app
   └→ PostgreSQL: UPDATE orders SET status='completed' WHERE id=123

2. CDC captures change
   └→ Kafka: {"type":"update", "order_id":123, "status":"completed", "ts":"..."}

3. Pinot ingests event
   └→ New record in CONSUMING segment
   └→ Query layer handles deduplication if using Upsert mode

4. Analytics queries
   └→ Pinot: Fast aggregations on append-only data
   └→ PostgreSQL: Transactional operations
```

---

## 📊 Comparison: Segment States

| Aspect | CONSUMING | ONLINE (Sealed) | OFFLINE |
|--------|-----------|----------------|---------|
| **Mutable** | ✅ YES (only for appends) | ❌ NO | ❌ NO |
| **Inserts** | ✅ Continuous | ❌ No | ❌ No |
| **Updates** | ❌ No | ❌ No | ❌ No |
| **Deletes** | ❌ No | ❌ No | ❌ No |
| **Location** | Memory | Disk | Disk |
| **Indexed** | Partial | Full | Full |
| **Compressed** | No | Yes | Yes |
| **Query Speed** | Slower | Fast | Fast |
| **Duration** | Minutes to hours | Permanent | Permanent |
| **Can Replace** | ❌ No | ✅ Yes (entire segment) | ✅ Yes (entire segment) |

---

## 🎯 Key Takeaways

### ✅ What IS Possible:

1. **CONSUMING segments**: Continuous appends from streams
2. **Upsert mode**: Soft deletes + new records (real-time only)
3. **Segment replacement**: Replace entire segments with new versions
4. **Versioned records**: Append new versions of records
5. **CDC patterns**: Stream changes from source of truth

### ❌ What IS NOT Possible:

1. **Direct updates**: Modify existing rows in sealed segments
2. **Direct deletes**: Remove specific rows from sealed segments
3. **In-place edits**: Change values without full segment rebuild
4. **Partial segment updates**: Modify subset of segment data

---

## 🏗️ Architectural Recommendations

### For Different Use Cases:

#### 1. **Real-Time Analytics (No Updates Needed)**
```
Use: Pure Pinot with append-only streaming
Example: Click streams, metrics, logs
```

#### 2. **Dimensional Data (Rare Updates)**
```
Use: Pinot OFFLINE + Daily batch reloads
Example: Product catalog, user profiles
```

#### 3. **Event Sourcing (Full History)**
```
Use: Pinot with versioned records
Example: Order lifecycle, user actions
```

#### 4. **Transactional + Analytics**
```
Use: PostgreSQL (source) + CDC → Kafka → Pinot
Example: E-commerce, SaaS applications
```

---

## 💡 Final Answer to Your Question

**Q: Is an online sealed segment immutable like an offline segment? Does it allow updates?**

**A**: 
- ✅ **YES**, online sealed segments are **100% immutable** just like offline segments
- ❌ **NO**, sealed segments do **NOT allow updates** of any kind
- ⚠️ Only **CONSUMING segments** allow new data (inserts only, not updates)
- 🔄 To "update" data, you must use workarounds like upsert mode, segment replacement, or versioned records

**The Philosophy**:
```
Pinot trades update flexibility for query performance.
Immutable segments enable aggressive optimizations that make
queries 100-1000x faster than traditional databases.
```

---

## 🔗 Related Concepts

- **MergeTree in ClickHouse**: Similar immutability but better update support
- **Parquet files in Data Lakes**: Also immutable
- **LSM Trees**: Write-optimized with compaction (used by Cassandra, RocksDB)
- **Event Sourcing**: Append-only by design

---

## 📚 Further Reading

- [Pinot Upsert Documentation](https://docs.pinot.apache.org/basics/data-import/upsert)
- [Segment Management](https://docs.pinot.apache.org/operators/operating-pinot/tuning/segments)
- [Real-Time Tables](https://docs.pinot.apache.org/basics/data-import/pinot-stream-ingestion)
- [Batch vs Streaming](https://docs.pinot.apache.org/basics/data-import/batch-ingestion)

---

**Remember**: The immutability of sealed segments is a **feature, not a bug**. It's what enables Pinot's incredible query performance! 🚀
