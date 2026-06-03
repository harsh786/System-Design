# FoundationDB - Real World Use Cases & Production Guide

## Overview

FoundationDB is a distributed, ordered key-value store with **strict serializability** (the strongest consistency guarantee possible). It provides a minimal but powerful KV API upon which higher-level data models ("layers") are built.

**Key Properties:**
- Strict serializability (linearizability + serializability)
- Multi-key ACID transactions across the entire keyspace
- Ordered keys enabling efficient range reads
- 5-second transaction time limit (enforced)
- 10MB transaction size limit
- Optimistic concurrency control (OCC) with MVCC

---

## Core Concepts

### Strict Serializability Guarantee

```
Client A: BEGIN ──── Read(x)=1 ──── Write(x=2) ──── COMMIT ✓
                                                        │ (committed at version 100)
Client B:                          BEGIN ──── Read(x) ──┼── sees x=2 (version > 100)
                                                        │
Client C: BEGIN ──── Write(x=3) ────────────── COMMIT ✗ (conflict: x modified at v100)
```

- Every transaction sees a **consistent snapshot** (MVCC)
- Commits are checked against conflicts (OCC)
- If two transactions write overlapping key ranges, one aborts
- External consistency: if T1 commits before T2 starts, T2 sees T1's writes

### Optimistic Concurrency Control (OCC)

```
┌─────────────────────────────────────────────────────────────┐
│                    Transaction Lifecycle                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. BEGIN  ─── Get read version (snapshot timestamp)         │
│       │                                                      │
│  2. READ   ─── Read from storage servers at that version     │
│       │        (keys read are tracked as "read conflict      │
│       │         ranges")                                     │
│       │                                                      │
│  3. WRITE  ─── Buffer writes locally (not sent yet)          │
│       │                                                      │
│  4. COMMIT ─── Send read conflict ranges + writes to proxy   │
│       │        Proxy checks with Resolver:                   │
│       │        "Were any of these keys modified since         │
│       │         my read version?"                            │
│       │                                                      │
│       ├── NO  ──► COMMITTED (writes go to tLogs)             │
│       └── YES ──► ABORTED (client retries with new version)  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### MVCC with Version Stamps

- Each committed transaction gets a monotonically increasing version (logical timestamp)
- Storage servers maintain multiple versions of each key (garbage collected after ~5s)
- `Versionstamp` - 10-byte value: 8-byte version + 2-byte batch order
- Used for: global ordering, conflict-free unique IDs, change tracking

### Key Ordering and Range Reads

```
Keys are raw bytes, ordered lexicographically:

  \x00              ← smallest possible key
  \x01\x00          
  \x01\x01          
  \x02              
  users/alice       
  users/bob         
  users/charlie     
  \xFF              ← reserved (system keyspace)

Range read: get_range("users/a", "users/d") → returns alice, bob, charlie
```

### Watches for Change Notifications

```python
@fdb.transactional
def watch_key(tr, key):
    current_value = tr.get(key)
    watch = tr.watch(key)  # Set up notification
    return current_value, watch

value, watch = watch_key(db, b'config/setting')
watch.wait()  # Blocks until key changes (or transaction duration limit)
print("Key changed!")
```

### Atomic Operations

Mutations that don't require a read (no conflict on the key):
- `atomic_add` - increment counter without read conflict
- `atomic_min` / `atomic_max`
- `atomic_and` / `atomic_or` / `atomic_xor`
- `set_versionstamped_key` / `set_versionstamped_value`
- `compare_and_clear`

### 5-Second Transaction Limit + Retry Loops

```python
# The @fdb.transactional decorator handles retry automatically
@fdb.transactional
def transfer(tr, from_acct, to_acct, amount):
    # This entire function may be called multiple times
    # Must be idempotent in its reads/writes
    balance = struct.unpack('<i', tr.get(from_acct))[0]
    if balance < amount:
        raise Exception("Insufficient funds")
    tr.add(from_acct, struct.pack('<i', -amount))
    tr.add(to_acct, struct.pack('<i', amount))

# If transaction takes > 5 seconds → aborted
# If conflict detected → retried with exponential backoff
# Retry loop uses: initial_backoff=10ms, max_retries=configurable
```

### Layers Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Application Layer                        │
├───────────────┬───────────────┬───────────────────────────┤
│  Record Layer │ Document Layer│  Custom Layers            │
│  (SQL-like    │ (MongoDB-like │  (Graph, Queue,           │
│   schemas,    │  documents,   │   Spatial, Time-series)   │
│   indexes)    │  indexes)     │                           │
├───────────────┴───────────────┴───────────────────────────┤
│              Directory Layer + Tuple Layer                  │
│  (Hierarchical namespaces + structured key encoding)       │
├───────────────────────────────────────────────────────────┤
│              FoundationDB Key-Value Store                   │
│  (Ordered keys, ACID transactions, 0-10MB values)          │
└───────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FoundationDB Cluster                              │
│                                                                      │
│  ┌──────────────┐     ┌─────────────────────┐                       │
│  │ Coordinators │     │  Cluster Controller  │                       │
│  │  (Paxos)     │────►│  (leader election,   │                       │
│  │  3 or 5      │     │   role assignment)    │                       │
│  └──────────────┘     └──────────┬───────────┘                       │
│                                  │ assigns roles                     │
│         ┌────────────────────────┼────────────────────┐              │
│         ▼                        ▼                    ▼              │
│  ┌─────────────┐      ┌──────────────┐      ┌─────────────┐        │
│  │   Proxies   │      │  Resolvers   │      │    tLogs     │        │
│  │ (commit     │─────►│ (conflict    │      │ (transaction │        │
│  │  proxies)   │      │  detection)  │      │   logs)      │        │
│  │  N=3-12     │      │  N=1-4       │      │  N=3-8+      │        │
│  └──────┬──────┘      └──────────────┘      └──────┬───────┘        │
│         │                                           │                │
│         │ read path                                 │ write path     │
│         ▼                                           ▼                │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              Storage Servers (SS)                            │     │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ... ┌────┐           │     │
│  │  │SS-1│ │SS-2│ │SS-3│ │SS-4│ │SS-5│     │SS-N│           │     │
│  │  │    │ │    │ │    │ │    │ │    │     │    │           │     │
│  │  │a-f │ │a-f │ │f-m │ │f-m │ │m-z │     │m-z │           │     │
│  │  └────┘ └────┘ └────┘ └────┘ └────┘     └────┘           │     │
│  │  (each shard replicated to multiple SS based on            │     │
│  │   replication mode; SQLite/RocksDB B-tree storage)         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Data Flow:
  Client ──► Proxy (get read version) ──► Storage Server (reads)
  Client ──► Proxy (commit) ──► Resolver (check conflicts) 
         ──► tLogs (persist mutations) ──► Storage Servers (apply async)
```

### Transaction Limits & Performance

| Metric | Limit/Typical |
|--------|---------------|
| Transaction size | 10 MB max |
| Transaction duration | 5 seconds max |
| Key size | 10 KB max |
| Value size | 100 KB max (recommended) |
| Read throughput | 500K-2M+ reads/sec/cluster |
| Write throughput | 100K-500K+ writes/sec/cluster |
| Latency (reads) | 1-3 ms (same DC) |
| Latency (commits) | 3-10 ms (same DC) |
| Cluster size | Up to 500+ processes |
| Data capacity | Tested to 100+ TB |

---

## Real-World Use Cases

### 1. Apple CloudKit (iCloud Backbone)

**Scale:** Billions of user accounts, exabytes of metadata, largest known FDB deployment.

Apple uses FoundationDB as the metadata backbone for iCloud services (CloudKit). Every iCloud account (photos, documents, health, keychain) has its metadata stored in FDB.

```
┌─────────────────────────────────────────────────────────────┐
│                    Apple CloudKit Architecture                │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │  iPhone  │   │   Mac    │   │  iPad    │                │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘                │
│       │               │              │                       │
│       ▼               ▼              ▼                       │
│  ┌──────────────────────────────────────────┐               │
│  │          CloudKit API Servers             │               │
│  │  (stateless, route by account hash)       │               │
│  └─────────────────────┬────────────────────┘               │
│                        │                                     │
│            ┌───────────┼───────────┐                         │
│            ▼           ▼           ▼                         │
│  ┌──────────────┐ ┌────────┐ ┌──────────────┐              │
│  │ Record Layer  │ │  Blob  │ │  Index       │              │
│  │ (metadata,    │ │ Store  │ │  Service     │              │
│  │  schemas,     │ │ (S3)   │ │              │              │
│  │  versions)    │ │        │ │              │              │
│  └──────┬───────┘ └────────┘ └──────┬───────┘              │
│         │                            │                       │
│         ▼                            ▼                       │
│  ┌──────────────────────────────────────────┐               │
│  │          FoundationDB Clusters            │               │
│  │  (multiple clusters, sharded by account)  │               │
│  │                                           │               │
│  │  Cluster-1: accounts 0x00-0x3F            │               │
│  │  Cluster-2: accounts 0x40-0x7F            │               │
│  │  Cluster-3: accounts 0x80-0xBF            │               │
│  │  Cluster-4: accounts 0xC0-0xFF            │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key-Value Layer Design:**

```
Directory Layer:
  /cloudkit/                          ← top-level directory
  /cloudkit/{app_id}/                 ← per-application
  /cloudkit/{app_id}/{user_hash}/     ← per-user partition
  /cloudkit/{app_id}/{user_hash}/records/
  /cloudkit/{app_id}/{user_hash}/indexes/
  /cloudkit/{app_id}/{user_hash}/subscriptions/

Key Encoding (Tuple Layer):
  (app_id, user_hash, "record", record_type, record_id) → protobuf(record_metadata)
  (app_id, user_hash, "index", index_name, field_value, record_id) → empty/pointer
  (app_id, user_hash, "zone", zone_id, "change", versionstamp) → change_token

Example Keys:
  ("com.apple.photos", 0xA3F2, "record", "Photo", "uuid-123")
    → {created: ts, modified: ts, blob_ref: "s3://...", size: 4200000}
  
  ("com.apple.photos", 0xA3F2, "index", "byDate", 20240115, "uuid-123")
    → ""
```

**Transaction Patterns:**

```python
@fdb.transactional
def save_record(tr, app_id, user, record_type, record_id, data):
    # All within a single ACID transaction:
    
    # 1. Write the record
    record_key = dir.pack((app_id, user, "record", record_type, record_id))
    tr.set(record_key, encode(data))
    
    # 2. Update all indexes
    for index_name, field_value in extract_index_fields(data):
        idx_key = dir.pack((app_id, user, "index", index_name, field_value, record_id))
        tr.set(idx_key, b'')
    
    # 3. Write change token with versionstamp for sync
    change_key = dir.pack((app_id, user, "zone", "default", "change"))
    tr.set_versionstamped_value(change_key, fdb.tuple.Versionstamp._INCOMPLETE)
    
    # 4. Atomic increment of record count
    count_key = dir.pack((app_id, user, "meta", "count", record_type))
    tr.add(count_key, struct.pack('<q', 1))
```

**Scale Numbers:**
- Billions of active accounts
- Multiple FDB clusters, each 100s of processes
- Strict serializability for conflict resolution across devices
- Record Layer provides SQL-like schemas on top of FDB
- Open-sourced as `fdb-record-layer`

---

### 2. Snowflake Metadata Store

**Scale:** Manages metadata for one of the largest cloud data warehouses; millions of concurrent queries, petabytes of table metadata.

Snowflake uses FoundationDB to store all metadata: table definitions, partitions, micro-partition statistics, transaction state, and query coordination.

```
┌─────────────────────────────────────────────────────────────┐
│                  Snowflake Architecture                       │
│                                                              │
│  ┌───────────────────────────────────────────┐              │
│  │            Cloud Services Layer            │              │
│  │  (Query parsing, optimization, scheduling) │              │
│  └────────────────────┬──────────────────────┘              │
│                       │                                      │
│         ┌─────────────┼─────────────┐                        │
│         ▼             ▼             ▼                        │
│  ┌────────────┐ ┌──────────┐ ┌──────────────┐              │
│  │  Metadata  │ │  Query   │ │   Access     │              │
│  │  Store     │ │  State   │ │   Control    │              │
│  │            │ │          │ │              │              │
│  └─────┬──────┘ └────┬─────┘ └──────┬───────┘              │
│        │              │              │                       │
│        ▼              ▼              ▼                       │
│  ┌──────────────────────────────────────────┐               │
│  │           FoundationDB Cluster            │               │
│  │                                           │               │
│  │  Table schemas, partition metadata,       │               │
│  │  file listings, statistics, locks,        │               │
│  │  transaction manifests                    │               │
│  └──────────────────────────────────────────┘               │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────┐               │
│  │     Virtual Warehouses (Compute)          │               │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │               │
│  │  │ XS  │ │  S  │ │  M  │ │  L  │       │               │
│  │  └─────┘ └─────┘ └─────┘ └─────┘       │               │
│  └──────────────────────────────────────────┘               │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────┐               │
│  │        Cloud Storage (S3/GCS/Azure)       │               │
│  │        (actual table data files)          │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key-Value Layer Design:**

```
Directory Structure:
  /snowflake/accounts/{account_id}/
  /snowflake/accounts/{account_id}/databases/{db_id}/
  /snowflake/accounts/{account_id}/databases/{db_id}/schemas/{schema_id}/
  /snowflake/accounts/{account_id}/databases/{db_id}/schemas/{schema_id}/tables/{table_id}/

Key Encoding:
  (account, db, schema, table, "meta") → {columns, clustering_keys, owner, created_at}
  (account, db, schema, table, "partitions", partition_id) → {file_path, row_count, min_max_stats}
  (account, db, schema, table, "stats", column_id) → {ndv, null_count, histogram}
  (account, "txn", txn_id) → {state, timestamp, manifest_files[], write_set}
  (account, "locks", resource_type, resource_id) → {holder_txn, mode, acquired_at}
```

**Transaction Patterns:**

```python
@fdb.transactional
def commit_dml(tr, account, table, new_partitions, deleted_partitions):
    # Atomic table mutation - consistent metadata update
    
    # 1. Add new micro-partitions
    for p in new_partitions:
        key = pack((account, db, schema, table, "partitions", p.id))
        tr.set(key, encode(p.metadata))
    
    # 2. Remove old partitions (mark as tombstone for time-travel)
    for p_id in deleted_partitions:
        key = pack((account, db, schema, table, "partitions", p_id))
        tr.clear(key)
        tombstone = pack((account, db, schema, table, "history", versionstamp, p_id))
        tr.set_versionstamped_key(tombstone, tr.get(key))
    
    # 3. Update table statistics atomically
    stats_key = pack((account, db, schema, table, "row_count"))
    delta = sum(p.rows for p in new_partitions) - deleted_row_count
    tr.add(stats_key, struct.pack('<q', delta))
```

**Scale Numbers:**
- Millions of concurrent metadata operations
- Sub-10ms metadata lookups
- Multi-region FDB clusters
- Enables Snowflake's time-travel and zero-copy cloning features

---

### 3. Wavefront/VMware (Time-Series Metadata)

**Scale:** Millions of unique time-series, billions of data points/day, millisecond metadata lookups.

Wavefront uses FoundationDB's ordered key-value store to manage time-series metadata: metric names, tag indexes, source mappings, and series ID assignments.

```
┌─────────────────────────────────────────────────────────────┐
│                 Wavefront Architecture                        │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │         Wavefront Proxies                 │               │
│  │  (ingest, parse, route metrics)           │               │
│  └────────────────────┬─────────────────────┘               │
│                       │                                      │
│          ┌────────────┼────────────┐                         │
│          ▼            ▼            ▼                         │
│  ┌─────────────┐ ┌─────────┐ ┌──────────────┐              │
│  │  Metadata   │ │  Data   │ │   Query      │              │
│  │  (FDB)      │ │  Store  │ │   Engine     │              │
│  │             │ │  (chunk │ │              │              │
│  │  - metric   │ │  files) │ │              │              │
│  │    names    │ │         │ │              │              │
│  │  - tag idx  │ │         │ │              │              │
│  │  - series   │ │         │ │              │              │
│  │    IDs      │ │         │ │              │              │
│  └─────────────┘ └─────────┘ └──────────────┘              │
│         │                            │                       │
│         ▼                            │                       │
│  ┌──────────────┐                    │                       │
│  │ FoundationDB │◄───────────────────┘                       │
│  │   Cluster    │  (query resolves metric→seriesID→chunks)   │
│  └──────────────┘                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key-Value Layer Design:**

```
Key Encoding (exploiting lexicographic ordering):

  Metric Registry:
    ("metrics", "name", "cpu.usage") → series_id_list
    ("metrics", "name", "disk.io")   → series_id_list

  Tag Index (inverted index for fast lookups):
    ("tags", "host", "web-01", series_id) → ""
    ("tags", "host", "web-02", series_id) → ""
    ("tags", "region", "us-east", series_id) → ""
    ("tags", "env", "prod", series_id) → ""

  Series Metadata:
    ("series", series_id) → {metric: "cpu.usage", tags: {host: "web-01", region: "us-east"}}

  ID Assignment (monotonic counter):
    ("counters", "next_series_id") → uint64

Query: "cpu.usage WHERE host=web-01 AND region=us-east"
  1. Range scan ("tags", "host", "web-01", ...) → {id1, id2, id3}
  2. Range scan ("tags", "region", "us-east", ...) → {id1, id4, id5}
  3. Intersect → {id1}
  4. Fetch ("series", id1) → full metadata
```

**Transaction Patterns:**

```python
@fdb.transactional
def register_new_series(tr, metric_name, tags):
    # Check if series already exists
    existing = lookup_series(tr, metric_name, tags)
    if existing:
        return existing
    
    # Atomic ID assignment
    counter_key = pack(("counters", "next_series_id"))
    tr.add(counter_key, struct.pack('<Q', 1))
    new_id = struct.unpack('<Q', tr.get(counter_key))[0]
    
    # Register series
    tr.set(pack(("series", new_id)), encode({metric_name, tags}))
    
    # Update tag indexes
    for tag_key, tag_value in tags.items():
        tr.set(pack(("tags", tag_key, tag_value, new_id)), b'')
    
    # Update metric name index
    tr.set(pack(("metrics", "name", metric_name, new_id)), b'')
    
    return new_id
```

**Scale Numbers:**
- 10M+ unique time-series
- Tag index queries in <5ms
- Handles bursty metric registration (new containers spinning up)
- Consistent reads for tag-based aggregation queries

---

### 4. Doxel AI Construction (IoT Progress Tracking)

**Scale:** Thousands of construction sites, millions of IoT data points, real-time progress tracking with photo/LiDAR analysis.

Doxel uses FoundationDB to track construction progress by correlating BIM models with reality-capture data (photos, LiDAR scans) for automated progress verification.

```
┌─────────────────────────────────────────────────────────────┐
│              Doxel Construction Platform                      │
│                                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │  Drones   │  │  Cameras  │  │  LiDAR    │               │
│  │  (photos) │  │  (360°)   │  │  Scanners │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │               │              │                      │
│        ▼               ▼              ▼                      │
│  ┌──────────────────────────────────────────┐               │
│  │         Ingestion Pipeline                │               │
│  │  (upload, register, queue for ML)         │               │
│  └────────────────────┬─────────────────────┘               │
│                       │                                      │
│         ┌─────────────┼─────────────┐                        │
│         ▼             ▼             ▼                        │
│  ┌────────────┐ ┌──────────┐ ┌──────────────┐              │
│  │ ML Pipeline│ │  BIM     │ │  Progress    │              │
│  │ (object   │ │  Model   │ │  Tracker     │              │
│  │  detect,  │ │  Store   │ │  (compare    │              │
│  │  segment) │ │          │ │   plan vs    │              │
│  │           │ │          │ │   actual)    │              │
│  └─────┬─────┘ └────┬─────┘ └──────┬───────┘              │
│        │             │              │                       │
│        ▼             ▼              ▼                       │
│  ┌──────────────────────────────────────────┐               │
│  │           FoundationDB Cluster            │               │
│  │  (project state, element tracking,        │               │
│  │   scan metadata, progress records)        │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key-Value Layer Design:**

```
Directory Structure:
  /doxel/{project_id}/
  /doxel/{project_id}/elements/        ← BIM elements
  /doxel/{project_id}/scans/           ← capture sessions
  /doxel/{project_id}/progress/        ← computed progress
  /doxel/{project_id}/schedule/        ← planned timeline

Key Encoding:
  (project, "element", element_id) → {type: "wall", floor: 3, zone: "A", planned_start, planned_end}
  (project, "scan", scan_date, scan_id) → {drone_id, coverage_pct, file_refs[]}
  (project, "progress", element_id, scan_date) → {status: "in_progress", pct: 65, confidence: 0.92}
  (project, "progress_idx", floor, zone, status, element_id) → "" (index for dashboard queries)
  (project, "alert", versionstamp) → {type: "behind_schedule", element_id, days_behind: 3}
```

**Transaction Patterns:**

```python
@fdb.transactional
def update_element_progress(tr, project, element_id, scan_date, ml_result):
    # Atomic progress update after ML analysis
    
    # 1. Write progress observation
    progress_key = pack((project, "progress", element_id, scan_date))
    tr.set(progress_key, encode(ml_result))
    
    # 2. Update element status
    elem_key = pack((project, "element", element_id))
    element = decode(tr.get(elem_key))
    old_status = element['status']
    element['status'] = ml_result['status']
    element['last_observed'] = scan_date
    tr.set(elem_key, encode(element))
    
    # 3. Update index (remove old, add new)
    old_idx = pack((project, "progress_idx", element['floor'], element['zone'], old_status, element_id))
    tr.clear(old_idx)
    new_idx = pack((project, "progress_idx", element['floor'], element['zone'], ml_result['status'], element_id))
    tr.set(new_idx, b'')
    
    # 4. Generate alert if behind schedule
    if is_behind_schedule(element, ml_result):
        alert_key = pack((project, "alert"))
        tr.set_versionstamped_key(alert_key + fdb.tuple.Versionstamp._INCOMPLETE, 
                                   encode({"element": element_id, "delay": compute_delay(element)}))
```

**Scale Numbers:**
- Thousands of active construction projects
- Millions of BIM elements tracked
- Daily scan ingestion with ML pipeline
- Real-time dashboards querying progress indexes
- ACID guarantees prevent double-counting or missed elements

---

### 5. Tiger Global / FinTech (Financial Records)

**Scale:** Millions of financial transactions/day, strict audit requirements, multi-account atomic transfers.

Financial technology companies use FoundationDB for ledger systems requiring serializable ACID transactions, perfect audit trails, and regulatory compliance.

```
┌─────────────────────────────────────────────────────────────┐
│               FinTech Ledger Platform                         │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Mobile  │  │   Web    │  │   API    │                  │
│  │   App    │  │   App    │  │ Partners │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │              │             │                         │
│       ▼              ▼             ▼                         │
│  ┌──────────────────────────────────────────┐               │
│  │          API Gateway / Auth               │               │
│  └────────────────────┬─────────────────────┘               │
│                       │                                      │
│       ┌───────────────┼───────────────┐                      │
│       ▼               ▼               ▼                      │
│  ┌─────────┐   ┌──────────┐   ┌──────────────┐             │
│  │ Payment │   │  Ledger  │   │  Compliance  │             │
│  │ Service │   │  Service │   │  Service     │             │
│  └────┬────┘   └────┬─────┘   └──────┬───────┘             │
│       │              │                │                      │
│       ▼              ▼                ▼                      │
│  ┌──────────────────────────────────────────┐               │
│  │           FoundationDB Cluster            │               │
│  │                                           │               │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────┐ │               │
│  │  │Accounts │ │  Journal │ │  Audit    │ │               │
│  │  │ (bal-   │ │  (immu-  │ │  Trail    │ │               │
│  │  │  ances) │ │   table  │ │           │ │               │
│  │  │         │ │   log)   │ │           │ │               │
│  │  └─────────┘ └──────────┘ └───────────┘ │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key-Value Layer Design:**

```
Directory Structure:
  /ledger/accounts/{account_id}/
  /ledger/journal/
  /ledger/audit/
  /ledger/idempotency/

Key Encoding:
  ("account", account_id, "balance", currency) → int64 (cents/smallest unit)
  ("account", account_id, "holds", hold_id) → {amount, expires_at, reason}
  ("account", account_id, "meta") → {name, type, status, created_at, limits}
  
  ("journal", versionstamp) → {from, to, amount, currency, type, reference}
  ("journal_idx", account_id, versionstamp) → "" (per-account transaction history)
  
  ("idempotency", client_txn_id) → {result, expires_at}
  
  ("audit", date, versionstamp) → {action, actor, details, ip}
```

**Transaction Patterns:**

```python
@fdb.transactional
def transfer_funds(tr, from_acct, to_acct, amount, currency, client_txn_id):
    # Idempotency check
    idemp_key = pack(("idempotency", client_txn_id))
    existing = tr.get(idemp_key)
    if existing:
        return decode(existing)  # Already processed
    
    # Read balances
    from_bal_key = pack(("account", from_acct, "balance", currency))
    to_bal_key = pack(("account", to_acct, "balance", currency))
    
    from_balance = to_int64(tr.get(from_bal_key))
    
    # Check available balance (balance - holds)
    holds = get_active_holds(tr, from_acct, currency)
    available = from_balance - sum(h['amount'] for h in holds)
    
    if available < amount:
        raise InsufficientFunds(available, amount)
    
    # Atomic balance updates
    tr.add(from_bal_key, struct.pack('<q', -amount))
    tr.add(to_bal_key, struct.pack('<q', amount))
    
    # Immutable journal entry with versionstamp ordering
    journal_key = pack(("journal",)) + fdb.tuple.Versionstamp._INCOMPLETE.to_bytes()
    entry = encode({"from": from_acct, "to": to_acct, "amount": amount, 
                    "currency": currency, "ref": client_txn_id})
    tr.set_versionstamped_key(journal_key, entry)
    
    # Per-account index
    for acct in [from_acct, to_acct]:
        idx_key = pack(("journal_idx", acct)) + fdb.tuple.Versionstamp._INCOMPLETE.to_bytes()
        tr.set_versionstamped_key(idx_key, b'')
    
    # Idempotency record
    result = {"status": "success", "ref": client_txn_id}
    tr.set(idemp_key, encode(result))
    
    # Audit trail
    audit_key = pack(("audit", today())) + fdb.tuple.Versionstamp._INCOMPLETE.to_bytes()
    tr.set_versionstamped_key(audit_key, encode({"action": "transfer", "details": result}))
    
    return result
```

**Scale Numbers:**
- Millions of transactions/day
- Zero double-spends (serializable isolation)
- Sub-10ms transfer latency
- Complete audit trail with global ordering via versionstamps
- Idempotency guarantees for exactly-once processing

---

## Replication

### Replication Modes

| Mode | Write Copies | Read Quorum | Tolerates | Use Case |
|------|-------------|-------------|-----------|----------|
| `single` | 1 | 1 | 0 failures | Development |
| `double` | 2 | 1 | 1 failure | Small production |
| `triple` | 3 | 1 | 2 failures | Standard production |
| `three_datacenter` | 3 (across DCs) | 1 | 1 DC failure | Multi-DC HA |
| `three_data_hall` | 3 (across halls) | 1 | 1 hall failure | Single-site HA |

### Transaction Log (tLog) Replication

```
┌─────────────────────────────────────────────────────────────────┐
│              tLog Replication (triple mode)                       │
│                                                                  │
│  Proxy commits transaction:                                      │
│                                                                  │
│  ┌─────────┐                                                     │
│  │  Proxy  │──── Write mutations ────┬──────────┬──────────┐    │
│  └─────────┘                         │          │          │    │
│       │                              ▼          ▼          ▼    │
│       │                         ┌────────┐ ┌────────┐ ┌────────┐│
│       │                         │ tLog-1 │ │ tLog-2 │ │ tLog-3 ││
│       │                         │  (DC1) │ │  (DC1) │ │  (DC2) ││
│       │                         └───┬────┘ └───┬────┘ └───┬────┘│
│       │                             │          │          │     │
│       │    ◄── ACK (durable) ───────┴──────────┴──────────┘     │
│       │    (waits for ALL replicas in triple mode)               │
│       │                                                          │
│       ▼                                                          │
│  Transaction committed                                           │
│  (client notified)                                               │
│                                                                  │
│  Asynchronously:                                                 │
│  tLogs ──► Storage Servers pull mutations and apply              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Write path: Proxy → ALL tLog replicas (synchronous, must all ACK)
Read path:  Client → ANY storage server with the data (no quorum needed)
```

### Storage Server Replication

```
┌─────────────────────────────────────────────────────────────────┐
│              Storage Server Replication                           │
│                                                                  │
│  Key range [a-m] replicated to 3 storage servers:                │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │    SS-1      │   │    SS-2      │   │    SS-3      │        │
│  │  keys: a-m   │   │  keys: a-m   │   │  keys: a-m   │        │
│  │  (team "A")  │   │  (team "A")  │   │  (team "A")  │        │
│  │              │   │              │   │              │        │
│  │  Pulls from  │   │  Pulls from  │   │  Pulls from  │        │
│  │  tLogs       │   │  tLogs       │   │  tLogs       │        │
│  │  independently│   │  independently│   │  independently│        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
│                                                                  │
│  Client reads go to ANY one of SS-1, SS-2, SS-3                  │
│  (load balanced by client library)                               │
│                                                                  │
│  If SS-2 fails:                                                  │
│  - Data Distributor notices missing replica                      │
│  - Assigns new SS to team "A"                                    │
│  - New SS copies data from healthy peer                          │
│  - Begins pulling from tLogs once caught up                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Recovery from Failures

```
Failure Scenarios and Recovery:

1. Storage Server Failure:
   ┌─────┐     ┌─────┐     ┌─────┐
   │SS-1 │     │SS-2 │     │SS-3 │
   │ OK  │     │ ✗✗✗ │     │ OK  │
   └─────┘     └─────┘     └─────┘
   → Reads continue from SS-1 and SS-3
   → Data Distributor recruits replacement
   → No data loss, no downtime

2. tLog Failure (triple mode):
   ┌──────┐    ┌──────┐    ┌──────┐
   │tLog-1│    │tLog-2│    │tLog-3│
   │  OK  │    │ ✗✗✗  │    │  OK  │
   └──────┘    └──────┘    └──────┘
   → Cluster Controller triggers recovery
   → New tLog set recruited
   → Old tLogs' data copied to new set
   → Brief write unavailability (~1-5 seconds)
   → NO committed data lost (still on tLog-1 and tLog-3)

3. Full Recovery Process:
   a) Cluster Controller detects failure
   b) Recruits new transaction system (proxies + resolvers + tLogs)
   c) New tLogs start at the last committed version
   d) Proxies resume accepting transactions
   e) Typical recovery time: 1-5 seconds
```

### Multi-DC with Satellite Logs

```
┌─────────────────────────────────────────────────────────────────┐
│           Multi-DC Deployment (three_datacenter)                  │
│                                                                  │
│  ┌──────────────── DC-1 (Primary) ─────────────────┐            │
│  │  Coordinators (2/5)                              │            │
│  │  Proxies, Resolvers                              │            │
│  │  tLogs (primary set)                             │            │
│  │  Storage Servers                                 │            │
│  └──────────────────────────────────────────────────┘            │
│                         │                                        │
│           ┌─────────────┼─────────────┐                          │
│           │ sync repl   │             │ sync repl                │
│           ▼             │             ▼                          │
│  ┌────── DC-2 ──────┐  │  ┌────── DC-3 ──────┐                 │
│  │  Coordinators(2/5)│  │  │  Coordinator(1/5)│                 │
│  │  Satellite tLogs  │  │  │  Satellite tLogs │                 │
│  │  Storage Servers  │  │  │  Storage Servers │                 │
│  └───────────────────┘  │  └──────────────────┘                 │
│                         │                                        │
│  Commit requires:       │                                        │
│  - ALL primary tLogs ACK (in DC-1)                               │
│  - At least 1 satellite per remote DC                            │
│                                                                  │
│  If DC-1 fails:                                                  │
│  - DC-2 or DC-3 elected new primary (via coordinators)           │
│  - Satellite logs ensure no committed data lost                  │
│  - Recovery in ~5-10 seconds                                     │
│                                                                  │
│  Read latency: local DC (1-3ms)                                  │
│  Write latency: cross-DC RTT (~10-30ms depending on distance)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scalability

### Key Range Sharding

```
┌─────────────────────────────────────────────────────────────────┐
│                    Automatic Sharding                             │
│                                                                  │
│  Total Keyspace: [\x00 ... \xFE]                                 │
│                                                                  │
│  Initial: one shard covers entire range                          │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                    SS-1: [\x00, \xFE]                 │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  After growth (automatic split at ~500MB per shard):             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │  SS-1   │ │  SS-2   │ │  SS-3   │ │  SS-4   │              │
│  │[\x00,\x40)│[\x40,\x80)│[\x80,\xC0)│[\xC0,\xFE]│              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
│                                                                  │
│  Data Distributor responsibilities:                              │
│  - Monitor shard sizes                                           │
│  - Split shards that exceed threshold                            │
│  - Merge shards that are too small                               │
│  - Move shards for load balancing                                │
│  - Maintain replication factor                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                       Layer Examples                              │
│                                                                  │
│  Record Layer (Apple):                                           │
│  - Typed schemas with evolution (like protobuf + SQL)            │
│  - Secondary indexes maintained transactionally                  │
│  - Query planner for index selection                             │
│  - Used in production for CloudKit                               │
│                                                                  │
│  Document Layer (MongoDB-compatible):                            │
│  - JSON documents stored as flattened KV pairs                   │
│  - {"a": {"b": 1}} → key=(doc_id, "a", "b") val=1              │
│  - Partial document updates without full rewrite                 │
│  - MongoDB wire protocol compatible                              │
│                                                                  │
│  Custom Layers:                                                  │
│  - Queue: (queue_name, versionstamp) → item                     │
│  - Graph: (node_id, edge_type, target_id) → properties          │
│  - Spatial: geohash prefix encoding for range queries            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Characteristics

```
Scaling behavior:
- Reads scale linearly with storage server count
- Writes scale with tLog count (up to resolver bottleneck)
- Cross-shard transactions: same cost as single-shard (global ordering)
- Adding machines: automatic rebalancing within minutes

Typical cluster sizes:
  Small:    3-9 processes    (~50K ops/sec)
  Medium:   20-50 processes  (~200K ops/sec)
  Large:    100-500 processes (~1M+ ops/sec)
  Apple:    1000s of processes (custom)

Bottlenecks to watch:
- Resolver: single-threaded conflict checking (~100K txn/sec per resolver)
- Proxy: commit processing (~50K commits/sec per proxy)
- Hot shards: single key range receiving disproportionate load
- Transaction size: approaching 10MB causes memory pressure
```

---

## Production Setup

### Cluster Configuration (fdbcli)

```bash
# Connect to cluster
$ fdbcli -C /etc/foundationdb/fdb.cluster

# Set replication mode
fdb> configure triple ssd

# Set redundancy for multi-DC
fdb> configure three_datacenter

# Set storage engine
fdb> configure ssd-2          # RocksDB-based (recommended)
fdb> configure ssd-redwood-1  # Redwood engine (newer)

# View cluster status
fdb> status details

# Set coordinators
fdb> coordinators 10.0.1.1:4500 10.0.1.2:4500 10.0.1.3:4500 10.0.2.1:4500 10.0.2.2:4500

# Exclude a machine for maintenance
fdb> exclude 10.0.1.5:4500
fdb> include 10.0.1.5:4500    # bring back

# Profile
fdb> profile client get
fdb> throttle on tag "batch_job" with 100 priority default
```

### Process Classes and Roles

```
# foundationdb.conf (per process)
[fdbserver.4500]
class = stateless        # Can be: proxy, resolver, cluster_controller, master

[fdbserver.4501]
class = transaction      # tLog processes

[fdbserver.4502]
class = storage          # Storage server processes

[fdbserver.4503]
class = log              # Dedicated log class

Process Class → Role Mapping:
┌──────────────┬───────────────────────────────────────┐
│ Class        │ Eligible Roles                         │
├──────────────┼───────────────────────────────────────┤
│ stateless    │ Proxy, Resolver, ClusterController     │
│ transaction  │ tLog, Resolver                         │
│ storage      │ StorageServer, tLog (fallback)         │
│ log          │ tLog only                              │
│ unset        │ Any role (not recommended)             │
└──────────────┴───────────────────────────────────────┘

Recommended minimum (triple replication):
- 3 stateless processes (proxies + resolvers + coordinator)
- 3 log processes (tLogs)
- 3+ storage processes
- 5 coordinators (odd number for Paxos majority)
```

### Monitoring

```bash
# Quick health check
$ fdbcli --exec "status minimal"
# Output: The database is available.

# Detailed status (JSON)
$ fdbcli --exec "status json" | jq '.cluster.workload'
{
  "transactions": {
    "started": {"hz": 45000},
    "committed": {"hz": 42000},
    "conflicted": {"hz": 300}
  },
  "operations": {
    "reads": {"hz": 500000},
    "writes": {"hz": 150000}
  }
}

# Key metrics to monitor:
# - transactions.conflicted.hz / transactions.committed.hz  (conflict rate)
# - storage_server.queue_depth (how far behind SS are from tLogs)
# - log_server.queue_disk_available (tLog disk pressure)
# - process.cpu_usage, process.memory_usage
# - cluster.data.moving_data (rebalancing in progress)

# Tracing (structured logs)
# FDB writes XML trace files to configured trace directory
# /var/log/foundationdb/trace.*.xml
# Fields: Severity, Time, Type, Machine, details...
# Use: fdbserver --trace_format=json for JSON traces
```

### Backup and DR

```bash
# Continuous backup to blob store
$ fdbbackup start \
    -d "blobstore://account:key@backup-bucket/cluster1?bucket=fdb-backups" \
    -C /etc/foundationdb/fdb.cluster

# Check backup status
$ fdbbackup status -C /etc/foundationdb/fdb.cluster

# Restore to a different cluster
$ fdbrestore start \
    -r "blobstore://account:key@backup-bucket/cluster1?bucket=fdb-backups" \
    -C /etc/foundationdb/fdb-restore.cluster \
    --target_version <version>

# DR (continuous replication to standby cluster)
$ fdbdr start \
    -s /etc/foundationdb/fdb-primary.cluster \
    -d /etc/foundationdb/fdb-standby.cluster

# DR switchover
$ fdbdr switch \
    -s /etc/foundationdb/fdb-primary.cluster \
    -d /etc/foundationdb/fdb-standby.cluster

# Backup supports:
# - Point-in-time restore (to any version)
# - Incremental (only logs since last snapshot)
# - S3, Azure Blob, GCS via blobstore:// URLs
```

### Kubernetes Deployment

```yaml
# Using the FoundationDB Kubernetes Operator (fdb-kubernetes-operator)
apiVersion: apps.foundationdb.org/v1beta2
kind: FoundationDBCluster
metadata:
  name: production-cluster
spec:
  version: 7.3.25
  
  databaseConfiguration:
    redundancy_mode: triple
    storage_engine: ssd-2
    usable_regions: 1
  
  processCounts:
    stateless: 4      # proxies + resolvers
    log: 5            # tLogs
    storage: 12       # storage servers
    cluster_controller: 1
  
  processes:
    general:
      podTemplate:
        spec:
          containers:
            - name: foundationdb
              resources:
                requests:
                  cpu: "2"
                  memory: "8Gi"
                limits:
                  cpu: "4"
                  memory: "16Gi"
      volumeClaimTemplate:
        spec:
          storageClassName: fast-ssd
          resources:
            requests:
              storage: 500Gi
    
    storage:
      podTemplate:
        spec:
          containers:
            - name: foundationdb
              resources:
                requests:
                  cpu: "4"
                  memory: "16Gi"
      volumeClaimTemplate:
        spec:
          resources:
            requests:
              storage: 2Ti
  
  routing:
    headlessService: true
  
  sidecarContainer:
    enableLivenessProbe: true
    enableReadinessProbe: true

---
# Access from application pods:
# Mount the cluster file from a ConfigMap
# Connect using: fdb.open('/var/fdb/fdb.cluster')
```

---

## Summary: When to Use FoundationDB

**Choose FDB when you need:**
- Strict serializability across distributed data
- Multi-key ACID transactions at scale
- Ordered keys for efficient range scans
- A flexible data model (build your own layer)
- Proven at massive scale (Apple, Snowflake)

**Avoid FDB when:**
- You need transactions > 10MB or > 5 seconds
- You need a full SQL engine out of the box (use CockroachDB/Spanner)
- Single-node is sufficient (use PostgreSQL)
- You need built-in full-text search (use Elasticsearch)
- Eventual consistency is acceptable (use Cassandra/DynamoDB for higher write throughput)

**Throughput Summary:**
- Single cluster: 100K-1M+ ops/sec depending on size
- Read latency: 1-3ms (local), 10-30ms (cross-DC)
- Write latency: 3-10ms (local), 15-50ms (cross-DC)
- Recovery time: 1-5 seconds (automatic)
- Max tested: 500+ processes, 100+ TB data
