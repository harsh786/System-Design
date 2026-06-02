# Apache HBase - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Model](#data-model)
3. [Storage Architecture](#storage-architecture)
4. [Region Management](#region-management)
5. [Read/Write Path](#readwrite-path)
6. [Cluster Architecture](#cluster-architecture)
7. [Compaction Strategies](#compaction-strategies)
8. [Replication & DR](#replication--dr)
9. [Coprocessors & Secondary Indexes](#coprocessors--secondary-indexes)
10. [Performance Optimization](#performance-optimization)
11. [Production Deployment](#production-deployment)
12. [Integration & Ecosystem](#integration--ecosystem)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is Apache HBase?
```
Apache HBase is a distributed, scalable, wide-column store modeled after
Google's Bigtable paper. It runs on top of HDFS (Hadoop Distributed File
System) and provides random, real-time read/write access to big data.

Key characteristics:
- Wide-column store (column families + qualifiers)
- Sorted by row key (lexicographic ordering)
- Built on HDFS (fault-tolerant distributed storage)
- Strong consistency (single-row atomicity)
- Automatic sharding (regions split as they grow)
- Billions of rows × millions of columns × thousands of versions
- Written in Java, runs on JVM
- Linear scalability (add RegionServers to scale)

NOT designed for:
- SQL queries (use Phoenix on top for SQL)
- Small datasets (< 100 million rows)
- Cross-row transactions (single-row atomic only)
- Complex joins or aggregations
- Low-latency requirements (< 1ms) without careful tuning
- Relational data with many foreign keys

Comparison:
┌────────────────────┬────────────┬──────────────┬──────────────┬────────────┐
│                    │ HBase      │ Cassandra    │ ScyllaDB     │ BigTable   │
├────────────────────┼────────────┼──────────────┼──────────────┼────────────┤
│ Consistency        │ Strong     │ Tunable      │ Tunable      │ Strong     │
│ Data Model         │ Wide-column│ Wide-column  │ Wide-column  │ Wide-column│
│ Storage            │ HDFS       │ Local disk   │ Local disk   │ Colossus   │
│ Scaling            │ Manual(ish)│ Automatic    │ Automatic    │ Automatic  │
│ Architecture       │ Master-Slave│ Peer-to-Peer│ Peer-to-Peer│ Managed    │
│ Secondary Index    │ Phoenix    │ Native       │ Native       │ Native     │
│ ZooKeeper needed   │ Yes        │ No           │ No           │ No         │
│ HDFS dependency    │ Yes        │ No           │ No           │ No         │
│ Operational cost   │ High       │ Medium       │ Low          │ Zero(mgd)  │
│ Best for           │ Hadoop eco │ Multi-DC     │ Low latency  │ GCP native │
│ Community          │ Apache     │ Apache+DS    │ ScyllaDB Inc │ Google     │
└────────────────────┴────────────┴──────────────┴──────────────┴────────────┘
```

### Full Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       APACHE HBASE CLUSTER ARCHITECTURE                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       CLIENT LAYER                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ Java     │  │ Thrift   │  │ REST     │  │ Phoenix (SQL)    │    │   │
│  │  │ Client   │  │ Gateway  │  │ Gateway  │  │ JDBC Driver      │    │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │   │
│  │       └──────────────┴─────────────┴──────────────────┘              │   │
│  │                         │                                             │   │
│  │  Client caches region locations from META table                      │   │
│  │  Talks directly to RegionServers (no Master in data path)           │   │
│  └─────────────────────────┼────────────────────────────────────────────┘   │
│                             │                                                │
│  ┌──────────────────────────┼───────────────────────────────────────────┐   │
│  │                          ▼                                            │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    HBASE MASTER (Active)                      │    │   │
│  │  │                                                               │    │   │
│  │  │  Responsibilities:                                            │    │   │
│  │  │  - Region assignment to RegionServers                        │    │   │
│  │  │  - Region balancing across cluster                           │    │   │
│  │  │  - Schema changes (DDL: create/alter/drop table)            │    │   │
│  │  │  - Monitoring RegionServer health                            │    │   │
│  │  │  - Failover: detect dead RegionServers → reassign regions   │    │   │
│  │  │                                                               │    │   │
│  │  │  NOT in data path (clients talk directly to RegionServers)   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  (Backup Master for HA)                        │   │
│  │  │ HBASE MASTER    │                                                 │   │
│  │  │ (Standby)       │                                                 │   │
│  │  └─────────────────┘                                                 │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                 REGIONSERVERS (Data Nodes)                    │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │    │   │
│  │  │  │ RegionServer 1│  │ RegionServer 2│  │ RegionServer 3│   │    │   │
│  │  │  │               │  │               │  │               │   │    │   │
│  │  │  │ ┌───────────┐│  │ ┌───────────┐│  │ ┌───────────┐│   │    │   │
│  │  │  │ │ Region A  ││  │ │ Region D  ││  │ │ Region G  ││   │    │   │
│  │  │  │ │ Region B  ││  │ │ Region E  ││  │ │ Region H  ││   │    │   │
│  │  │  │ │ Region C  ││  │ │ Region F  ││  │ │ Region I  ││   │    │   │
│  │  │  │ └───────────┘│  │ └───────────┘│  │ └───────────┘│   │    │   │
│  │  │  │               │  │               │  │               │   │    │   │
│  │  │  │ WAL (HLog)   │  │ WAL (HLog)   │  │ WAL (HLog)   │   │    │   │
│  │  │  │ BlockCache   │  │ BlockCache   │  │ BlockCache   │   │    │   │
│  │  │  └───────────────┘  └───────────────┘  └───────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    ZOOKEEPER ENSEMBLE (3 or 5 nodes)          │    │   │
│  │  │                                                               │    │   │
│  │  │  - Master election (active/standby)                          │    │   │
│  │  │  - RegionServer liveness tracking                            │    │   │
│  │  │  - ROOT/META table location                                  │    │   │
│  │  │  - Cluster configuration                                     │    │   │
│  │  │  - Region state transitions                                  │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    HDFS (Hadoop Distributed File System)               │   │
│  │                                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │DataNode 1│  │DataNode 2│  │DataNode 3│  │DataNode N│            │   │
│  │  │          │  │          │  │          │  │          │            │   │
│  │  │ HFiles   │  │ HFiles   │  │ HFiles   │  │ HFiles   │            │   │
│  │  │ WAL files│  │ WAL files│  │ WAL files│  │ WAL files│            │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│  │                                                                       │   │
│  │  Replication factor: 3 (default)                                     │   │
│  │  HBase files stored in: /hbase/ on HDFS                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Wide-Column Model
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HBASE DATA MODEL                                           │
│                                                                              │
│  Table: "user_activity"                                                      │
│  Column Families: "info", "activity"                                        │
│                                                                              │
│  ┌──────────────┬─────────────────────────────┬─────────────────────────┐  │
│  │              │ Column Family: "info"        │ Column Family: "activity"│  │
│  │  Row Key     ├───────────┬─────────────────┼──────────┬──────────────┤  │
│  │              │ info:name │ info:email       │ act:login│ act:purchase │  │
│  ├──────────────┼───────────┼─────────────────┼──────────┼──────────────┤  │
│  │ user001      │ "Alice"   │ "a@example.com" │ t1: "web"│ t1: "$50"   │  │
│  │              │ (t3)      │ (t2)            │ t2: "app"│              │  │
│  ├──────────────┼───────────┼─────────────────┼──────────┼──────────────┤  │
│  │ user002      │ "Bob"     │ "b@example.com" │ t1: "web"│ t1: "$30"   │  │
│  │              │ (t1)      │ (t1)            │          │ t2: "$75"   │  │
│  ├──────────────┼───────────┼─────────────────┼──────────┼──────────────┤  │
│  │ user003      │ "Charlie" │                 │ t1: "ios"│              │  │
│  └──────────────┴───────────┴─────────────────┴──────────┴──────────────┘  │
│                                                                              │
│  Key concepts:                                                               │
│  - Row Key: Unique identifier, sorted lexicographically                     │
│  - Column Family: Declared at table creation, stored together on disk       │
│  - Column Qualifier: Dynamic within a family (no schema required)           │
│  - Cell: (Row Key, Family:Qualifier, Timestamp) → Value                     │
│  - Versions: Multiple timestamps per cell (configurable max versions)       │
│  - TTL: Automatic expiration per column family                              │
│                                                                              │
│  Physical storage coordinate:                                                │
│  (RowKey, ColumnFamily:ColumnQualifier, Timestamp) → Value                  │
│                                                                              │
│  Sorted order on disk:                                                       │
│  user001/info:email/t2 → "a@example.com"                                   │
│  user001/info:name/t3  → "Alice"                                            │
│  user001/info:name/t1  → "Al"  (old version)                               │
│  user002/info:email/t1 → "b@example.com"                                   │
│  ...                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Row Key Design Principles
```
Row key design is the MOST critical decision in HBase:

GOOD patterns:
1. Salted keys: hash_prefix + entity_id
   - Prevents hotspotting on sequential writes
   - Example: md5(user_id)[0:2] + user_id
   
2. Reversed timestamp: (Long.MAX_VALUE - timestamp) + entity_id
   - Most recent data at top of table
   - Efficient "get latest N" scans

3. Composite keys: entity_type + entity_id + reversed_timestamp
   - Example: "user#12345#9999999999999"
   - Enables prefix scans for all activity of a user

BAD patterns:
1. Sequential IDs: 1, 2, 3, 4...
   - All writes go to one region (hot region)
   
2. Timestamps as row key start:
   - All writes go to latest region (hotspot)
   
3. Unpadded numbers: "1", "10", "2"
   - Lexicographic sort ≠ numeric sort

Hotspot mitigation:
┌─────────────────────────────────────────────────────────────┐
│ Without salting:          │ With salting (4 buckets):        │
│                           │                                  │
│ Region 1: [0000-3333]    │ Region 1: [00|...] 25% writes   │
│ Region 2: [3333-6666]    │ Region 2: [01|...] 25% writes   │
│ Region 3: [6666-9999] ← │ Region 3: [10|...] 25% writes   │
│            ALL WRITES!   │ Region 4: [11|...] 25% writes   │
│                           │ ← Evenly distributed!            │
└─────────────────────────────────────────────────────────────┘
```

---

## Storage Architecture

### Region/Store/HFile Hierarchy
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REGION INTERNAL STRUCTURE                                  │
│                                                                              │
│  Table "orders" split into Regions by row key range:                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ REGION (row keys: "A000" to "F999")                                  │    │
│  │ Hosted on: RegionServer 2                                            │    │
│  │                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────┐  │    │
│  │  │ STORE (one per Column Family)                                   │  │    │
│  │  │ Column Family: "order_info"                                     │  │    │
│  │  │                                                                 │  │    │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ MEMSTORE (in-memory sorted buffer)                        │  │  │    │
│  │  │  │ - ConcurrentSkipListMap (sorted by key)                   │  │  │    │
│  │  │  │ - Default size: 128MB (hbase.hregion.memstore.flush.size)│  │  │    │
│  │  │  │ - Flushed to HFile when full                              │  │  │    │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │    │
│  │  │                                                                 │  │    │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ STOREFILES (HFiles on HDFS)                               │  │  │    │
│  │  │  │                                                            │  │  │    │
│  │  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │  │    │
│  │  │  │  │ HFile 1  │ │ HFile 2  │ │ HFile 3  │ │ HFile 4  │   │  │  │    │
│  │  │  │  │ (oldest) │ │          │ │          │ │ (newest) │   │  │  │    │
│  │  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │  │    │
│  │  │  │                                                            │  │  │    │
│  │  │  │  HFile structure:                                          │  │  │    │
│  │  │  │  ┌────────────────────────────────────────────────────┐   │  │  │    │
│  │  │  │  │ [Data Blocks] [Meta Blocks] [FileInfo] [Index]     │   │  │  │    │
│  │  │  │  │ [Trailer]                                           │   │  │  │    │
│  │  │  │  │                                                     │   │  │  │    │
│  │  │  │  │ Data Block (64KB default):                          │   │  │  │    │
│  │  │  │  │   Sorted KeyValue pairs                             │   │  │  │    │
│  │  │  │  │   [key_len][val_len][row][cf][qualifier][ts][type]  │   │  │  │    │
│  │  │  │  │   [value]                                           │   │  │  │    │
│  │  │  │  │                                                     │   │  │  │    │
│  │  │  │  │ Block Index: row_key → block_offset (B+ tree-like) │   │  │  │    │
│  │  │  │  │ Bloom Filter: quickly check if key might exist      │   │  │  │    │
│  │  │  │  └────────────────────────────────────────────────────┘   │  │  │    │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │    │
│  │  └────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────┐  │    │
│  │  │ STORE: Column Family "payment_info"                             │  │    │
│  │  │  (same structure: MemStore + HFiles)                            │  │    │
│  │  └────────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Read/Write Path

### Write Path
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HBASE WRITE PATH                                           │
│                                                                              │
│  Client: Put(row="user123", "info:name"="Alice")                            │
│     │                                                                        │
│     │ 1. Find region location (from cached META or ZooKeeper)               │
│     ▼                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ RegionServer                                                          │   │
│  │                                                                       │   │
│  │  Step 2: Acquire row lock (for atomicity within a row)               │   │
│  │     │                                                                 │   │
│  │     ▼                                                                 │   │
│  │  Step 3: Write to WAL (Write-Ahead Log / HLog)                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ WAL (sequential append, one per RegionServer)                   │  │   │
│  │  │ - Written to HDFS (replicated to 3 DataNodes)                  │  │   │
│  │  │ - Sequential write = fast                                       │  │   │
│  │  │ - fsync configurable (SYNC_WAL vs ASYNC_WAL vs SKIP_WAL)      │  │   │
│  │  │ - Purpose: crash recovery (replay WAL to recover MemStore)     │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │     │                                                                 │   │
│  │     ▼                                                                 │   │
│  │  Step 4: Write to MemStore (in-memory sorted map)                    │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ MemStore                                                        │  │   │
│  │  │ - ConcurrentSkipListMap (thread-safe, sorted)                  │  │   │
│  │  │ - Insert into sorted position                                   │  │   │
│  │  │ - Very fast (pure in-memory)                                   │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │     │                                                                 │   │
│  │     ▼                                                                 │   │
│  │  Step 5: Release row lock, return success to client                  │   │
│  │                                                                       │   │
│  │  Step 6 (async): MemStore flush when size threshold reached          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ Flush triggers:                                                  │  │   │
│  │  │ - MemStore size > flush.size (128MB default)                   │  │   │
│  │  │ - Total MemStores > global memstore limit (40% heap)          │  │   │
│  │  │ - WAL file count > max WAL files                               │  │   │
│  │  │                                                                 │  │   │
│  │  │ Flush process:                                                   │  │   │
│  │  │ - Snapshot MemStore (freeze, create new empty one)             │  │   │
│  │  │ - Write snapshot as HFile to HDFS                              │  │   │
│  │  │ - Clear WAL entries for flushed data                           │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Write latency: 1-5ms (WAL sync) + <1ms (MemStore insert) ≈ 2-6ms         │
│  Durability: Data safe after WAL sync (even if RegionServer crashes)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Read Path
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HBASE READ PATH                                            │
│                                                                              │
│  Client: Get(row="user123", "info:name")                                    │
│     │                                                                        │
│     ▼                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ RegionServer                                                          │   │
│  │                                                                       │   │
│  │  Step 1: Check BlockCache (LRU cache in memory)                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ BLOCKCACHE                                                      │  │   │
│  │  │ - LRU cache of HFile data blocks                               │  │   │
│  │  │ - On-heap (LRUBlockCache) or off-heap (BucketCache)           │  │   │
│  │  │ - Typical size: 40% of heap or dedicated off-heap              │  │   │
│  │  │ - If HIT → return immediately (fastest path)                   │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │     │ MISS                                                            │   │
│  │     ▼                                                                 │   │
│  │  Step 2: Check MemStore (most recent writes)                         │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ MEMSTORE                                                        │  │   │
│  │  │ - Contains unflushed writes                                     │  │   │
│  │  │ - Sorted → binary search                                       │  │   │
│  │  │ - May have the most recent version                             │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │     │                                                                 │   │
│  │     ▼                                                                 │   │
│  │  Step 3: Check HFiles (on HDFS, possibly multiple)                   │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ For each HFile (newest to oldest):                              │  │   │
│  │  │                                                                 │  │   │
│  │  │  3a. Bloom Filter check: "Could row exist in this file?"       │  │   │
│  │  │      - If NO → skip file entirely (very fast)                  │  │   │
│  │  │      - If MAYBE → continue to next step                        │  │   │
│  │  │                                                                 │  │   │
│  │  │  3b. Block Index: Find data block containing the row           │  │   │
│  │  │      - Binary search on block index (loaded in memory)         │  │   │
│  │  │                                                                 │  │   │
│  │  │  3c. Read data block from HDFS (or BlockCache)                 │  │   │
│  │  │      - 64KB block read from disk                                │  │   │
│  │  │      - Decompress if compressed                                 │  │   │
│  │  │      - Cache in BlockCache for future reads                    │  │   │
│  │  │                                                                 │  │   │
│  │  │  3d. Binary search within block for the key                    │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │     │                                                                 │   │
│  │     ▼                                                                 │   │
│  │  Step 4: Merge results (MemStore + HFiles)                           │   │
│  │  - Take latest version (highest timestamp)                           │   │
│  │  - Apply version/TTL filters                                          │   │
│  │  - Return to client                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Read latency:                                                               │
│  - BlockCache hit: < 1ms                                                    │
│  - MemStore: < 1ms                                                          │
│  - Single HFile (with bloom): 2-10ms                                        │
│  - Multiple HFiles (no compaction): 5-50ms                                  │
│  - HDFS read (cold): 10-100ms                                               │
│                                                                              │
│  Optimization: Fewer HFiles = faster reads → COMPACTION is critical!        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Region Management

### Splitting & Balancing
```
Region splitting:
- Automatic when region exceeds max size (10GB default)
- Split point: middle of the region's row key range
- IncreasingToUpperBoundRegionSplitPolicy (default HBase 2.x):
  min(region_count^3 * flush_size * 2, max_region_size)

Pre-splitting (critical for new tables):
  # Create table with pre-split regions
  create 'orders', 'info', SPLITS => ['10', '20', '30', '40', '50', '60', '70', '80', '90']
  
  # Or HexStringSplit for hash-prefixed keys
  create 'events', 'data', {NUMREGIONS => 64, SPLITALGO => 'HexStringSplit'}

Region balancing:
  ┌───────────────────────────────────────────────────────────────────────┐
  │ Before balancing:                                                      │
  │ RS1: [R1, R2, R3, R4, R5, R6, R7, R8]  ← overloaded                 │
  │ RS2: [R9, R10]                           ← underloaded               │
  │ RS3: [R11, R12, R13]                     ← normal                    │
  │                                                                        │
  │ After balancing (SimpleLoadBalancer):                                  │
  │ RS1: [R1, R2, R3, R4, R5]               ← balanced                   │
  │ RS2: [R9, R10, R6, R7]                  ← balanced                   │
  │ RS3: [R11, R12, R13, R8]                ← balanced                   │
  └───────────────────────────────────────────────────────────────────────┘
```

---

## Compaction Strategies

### Minor vs Major Compaction
```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPACTION TYPES                               │
│                                                                   │
│  MINOR COMPACTION:                                               │
│  - Merges a few small HFiles into larger ones                   │
│  - Does NOT delete expired/deleted data                          │
│  - Triggered: when file count > threshold (default: 3)          │
│  - I/O impact: moderate                                          │
│                                                                   │
│  Before: [HF1(10MB)] [HF2(15MB)] [HF3(8MB)] [HF4(200MB)]     │
│  Minor:  [HF_merged(33MB)]                   [HF4(200MB)]      │
│  (only small files merged, large file untouched)                 │
│                                                                   │
│  MAJOR COMPACTION:                                               │
│  - Merges ALL HFiles in a store into one                        │
│  - Deletes expired/deleted data permanently                      │
│  - Rewrites ALL data (very I/O intensive)                       │
│  - Triggered: by schedule (default: 7 days) or manual           │
│                                                                   │
│  Before: [HF1] [HF2] [HF3] [HF4] [HF5]                       │
│  Major:  [HF_single_large_file]                                  │
│  (all data rewritten, tombstones removed)                        │
│                                                                   │
│  PRODUCTION RECOMMENDATION:                                      │
│  - Disable automatic major compaction (set period = 0)          │
│  - Schedule manually during off-peak hours                       │
│  - Rolling major compaction across RegionServers                │
└─────────────────────────────────────────────────────────────────┘

Compaction strategies:
┌──────────────────┬───────────────────────────────────────────────┐
│ Strategy         │ Best for                                       │
├──────────────────┼───────────────────────────────────────────────┤
│ Default (size)   │ General workloads                              │
│ Date-tiered      │ Time-series (compact older data aggressively) │
│ Stripe           │ Large regions (parallel compaction per stripe) │
│ FIFO             │ TTL-only data (just drop expired files)       │
│ MOB              │ Medium objects (100KB-10MB values)            │
└──────────────────┴───────────────────────────────────────────────┘
```

---

## Replication & DR

### Cluster Replication
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HBASE REPLICATION ARCHITECTURE                             │
│                                                                              │
│  ┌───────────────────────────────┐    ┌───────────────────────────────┐    │
│  │  PRIMARY CLUSTER (Active)      │    │  REPLICA CLUSTER (Passive)    │    │
│  │                                │    │                                │    │
│  │  ┌─────────────────────────┐  │    │  ┌─────────────────────────┐  │    │
│  │  │ RegionServer 1          │  │    │  │ RegionServer 1          │  │    │
│  │  │                         │  │    │  │                         │  │    │
│  │  │  WAL entries:           │  │    │  │  Applies edits from     │  │    │
│  │  │  [edit1][edit2][edit3]  │──├────├──│  primary cluster WAL    │  │    │
│  │  │                         │  │    │  │                         │  │    │
│  │  │  ReplicationSource:     │  │    │  │  ReplicationSink:       │  │    │
│  │  │  - Reads WAL entries    │  │    │  │  - Receives edits       │  │    │
│  │  │  - Ships to peer       │  │    │  │  - Writes locally       │  │    │
│  │  │  - Tracks position     │  │    │  │  - Applies to MemStore  │  │    │
│  │  └─────────────────────────┘  │    │  └─────────────────────────┘  │    │
│  │                                │    │                                │    │
│  └───────────────────────────────┘    └───────────────────────────────┘    │
│                                                                              │
│  Replication modes:                                                          │
│  1. ASYNC (default): Best-effort, low latency impact on primary             │
│  2. SYNC: Wait for replica ACK before responding to client                  │
│  3. SERIAL: Preserve order across regions (for cross-row consistency)       │
│                                                                              │
│  Topologies:                                                                 │
│  - Master-Slave: Primary → Replica (DR)                                     │
│  - Master-Master: A ↔ B (active-active, conflict resolution needed)        │
│  - Chain: A → B → C (multi-hop)                                            │
│  - Hub-Spoke: Primary → Replica1, Replica2, Replica3                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Performance Optimization

### Critical Tuning Parameters
```
Memory allocation (for 64GB heap RegionServer):
┌──────────────────────────────────────────────────────────────────┐
│ Component          │ Config                     │ Recommended     │
├────────────────────┼────────────────────────────┼─────────────────┤
│ MemStore (writes)  │ hbase.regionserver         │ 40% = 25.6 GB   │
│                    │ .global.memstore.size=0.4  │                 │
│ BlockCache (reads) │ hfile.block.cache.size=0.4 │ 40% = 25.6 GB   │
│ Other (overhead)   │ Remaining                  │ 20% = 12.8 GB   │
├────────────────────┼────────────────────────────┼─────────────────┤
│ Total              │                            │ 100% = 64 GB     │
└────────────────────┴────────────────────────────┴─────────────────┘

Or use BucketCache (off-heap):
- On-heap BlockCache: 10GB (index + meta blocks)
- Off-heap BucketCache: 100GB+ (data blocks)
- MemStore: 40% of heap
- Benefit: Very large cache without GC pressure

Key performance configs:
  hbase.hregion.memstore.flush.size = 128MB      # MemStore flush threshold
  hbase.hstore.compactionThreshold = 3           # Min files for compaction
  hbase.hstore.blockingStoreFiles = 16           # Block writes if too many files
  hbase.regionserver.handler.count = 100         # RPC handler threads
  hbase.client.scanner.caching = 100             # Rows per scanner fetch
  hbase.hregion.max.filesize = 10GB              # Region split threshold

Bloom filter types:
  ROW: Check if row key exists in HFile (default)
  ROWCOL: Check if row+column exists (more precise, more space)
  NONE: No bloom filter (saves space, slower reads)
  
  Impact: Bloom filters eliminate 90%+ of unnecessary HFile reads
```

---

## Production Deployment

### Sizing Guidelines
```
┌───────────────────────────────────────────────────────────────────────────┐
│ Workload           │ RegionServers │ CPU/RS │ RAM/RS │ Disk/RS │ Regions │
├────────────────────┼───────────────┼────────┼────────┼─────────┼─────────┤
│ Small (100GB)      │ 3-5           │ 8      │ 32 GB  │ 1 TB    │ 30-100  │
│ Medium (1TB)       │ 5-10          │ 16     │ 64 GB  │ 4 TB    │ 100-500 │
│ Large (10TB)       │ 10-30         │ 32     │ 128 GB │ 12 TB   │ 500-3K  │
│ Very Large (100TB) │ 30-100        │ 32     │ 128 GB │ 24 TB   │ 3K-30K  │
│ Massive (1PB+)     │ 100-500+      │ 32     │ 256 GB │ 48 TB   │ 30K+    │
└────────────────────┴───────────────┴────────┴────────┴─────────┴─────────┘

GC tuning (critical for HBase):
  # Use G1GC for heaps > 32GB
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=100
  -XX:G1NewSizePercent=2
  -XX:G1MaxNewSizePercent=15
  -XX:InitiatingHeapOccupancyPercent=65
  -XX:+ParallelRefProcEnabled
  
  # Monitor GC pauses: > 500ms causes ZK session timeout
  # ZK session timeout default: 90s (increase for large heaps)

HDFS recommendations:
  - Short-circuit reads: Enable (bypass DataNode for local reads)
  - Rack awareness: Configure for fault tolerance
  - Replication: 3 (standard), 2 (for WAL if latency-sensitive)
  - Block size: 64MB (HBase uses its own block format within)
```

---

## Use Case Architectures

### Time-Series at Scale (Facebook Messages pattern)
```
┌─────────────────────────────────────────────────────────────────┐
│          TIME-SERIES / MESSAGING WITH HBASE                      │
│                                                                   │
│  Row Key Design: user_id + reversed_timestamp                    │
│  Example: "user123#9999999999999" (newest first)                │
│                                                                   │
│  Table: messages                                                 │
│  Column Family: "m" (short name = less storage)                  │
│  Columns: m:body, m:from, m:to, m:read                          │
│                                                                   │
│  Write pattern:                                                   │
│  - Sequential writes per user (reversed time = always new region)│
│  - Salt with hash prefix for write distribution                  │
│                                                                   │
│  Read pattern:                                                    │
│  - Scan: prefix="user123#", limit=50 (latest 50 messages)      │
│  - Single-row: exact message lookup                              │
│                                                                   │
│  Scale: Facebook used HBase for messaging                        │
│  - 100+ billion messages                                         │
│  - Millions of writes/second                                     │
│  - Sub-10ms reads for recent messages                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: Why would you choose HBase over Cassandra?
```
Answer:
Choose HBase when:
1. Strong consistency required (financial data, counters)
2. Already have Hadoop ecosystem (HDFS, Spark, MapReduce)
3. Need ordered scans (row keys sorted, range scans efficient)
4. Need coprocessors (server-side computation)
5. Batch processing integration (native MapReduce/Spark)
6. Need secondary indexes via Phoenix SQL layer

Choose Cassandra when:
1. Multi-datacenter active-active replication
2. No single point of failure required (no Master)
3. Tunable consistency per query
4. Simpler operations (no ZooKeeper, no HDFS)
5. Higher write throughput (peer-to-peer, all nodes accept writes)
6. Lightweight transactions sufficient (Paxos-based)
```

### Q2: Explain the META table and region lookup process
```
Answer:
META table (.META.) contains location of every region in the cluster:

Lookup process (3-step, now 2-step since HBase 2.x):
1. Client asks ZooKeeper for META table location
2. Client reads META to find region for requested row key
3. Client connects directly to RegionServer hosting that region
4. Client caches region location (avoids repeated META lookups)

META table structure:
  Row key: table_name,region_start_key,region_id
  Column: info:regioninfo (region metadata)
  Column: info:server (RegionServer hostname:port)
  Column: info:serverstartcode

Cache invalidation:
- Client gets NotServingRegionException → clear cache → re-lookup META
- Happens on: region split, region move, RegionServer failure
```

### Q3: How to handle hot regions?
```
Answer:
Hot region = one region receiving disproportionate traffic

Causes:
- Sequential row keys (timestamp-based)
- Popular entity (celebrity user, viral content)
- Unbalanced splits

Solutions:
1. Pre-splitting: Create many regions upfront with known key ranges
2. Salting: Prefix row key with hash (distributes across regions)
3. Reverse key: Reverse domain/timestamp for better distribution
4. Per-request routing: Application-level load shedding
5. Region hot-split: Manually split hot region at the midpoint
6. Read replicas: RegionServer groups for read-heavy workloads

Monitoring:
- hbase.regionserver.Store.storeFileSize per region
- hbase.regionserver.Server.totalRequestCount per RS
- hbase.regionserver.Server.readRequestCount
```

### Q4-Q10: Additional Questions
```
Q4: What happens when a RegionServer dies?
1. ZooKeeper detects session timeout (90s default)
2. Master notified of dead RegionServer
3. Master starts WAL splitting (split dead RS's WAL into per-region logs)
4. Master assigns orphaned regions to other RegionServers
5. New hosting RegionServers replay WAL to recover MemStore state
6. Regions become available again
Recovery time: 90s (ZK detection) + WAL split + region open = 2-10 minutes

Q5: Explain WAL splitting and why it's critical
- One WAL per RegionServer contains edits for ALL regions on that server
- On failure: Must split into per-region WALs for recovery
- Each region's new RS only replays its own edits
- Distributed log splitting: Master coordinates, multiple RS help split
- SplitLogManager assigns WAL files to available workers

Q6: How does HBase achieve strong consistency?
- Each region hosted by exactly ONE RegionServer at any time
- All reads/writes for a region go through same server
- WAL provides durability (replicated via HDFS)
- Row-level atomicity (all columns in a Put committed together)
- No multi-row transactions (use frameworks like Tephra/Omid for that)

Q7: Block encoding vs compression - when to use each?
Block encoding: Reduces storage by encoding key similarities
- PREFIX: Common prefix shared (good for similar row keys)
- DIFF: Delta encoding between adjacent keys
- FAST_DIFF: Optimized DIFF
- Use when: row keys are similar (saves significant space)

Compression: Compresses entire data block
- SNAPPY: Fast, moderate compression (recommended default)
- LZ4: Fastest decompression, moderate compression
- ZSTD: Best compression ratio, moderate speed
- GZ: Good compression, slow (avoid for real-time)
- Use: Always enable compression in production

Combine both for maximum space efficiency.

Q8: How to design HBase schema for IoT telemetry?
Row key: device_type#device_id#reversed_timestamp
Column family: "d" (short = efficient)
Columns: d:temp, d:humidity, d:battery, d:signal
TTL: 90 days
Versions: 1 (latest only)
Pre-split: By device_type hash

Q9: What are MOB (Medium Object) files?
- For values 100KB - 10MB (images, documents)
- Normal HFile storage = terrible for large values (compaction writes all data)
- MOB: Large values stored in separate MOB files
- Only references stored in normal HFiles
- MOB compaction runs separately, less frequently
- Reduces write amplification for large values

Q10: Explain Phoenix and its role with HBase
- Phoenix = SQL layer on top of HBase
- Compiles SQL to HBase API calls (scans, gets)
- Provides: Secondary indexes, JOINs, transactions
- Secondary index types: covered, functional, local, global
- Global secondary index: separate HBase table (strong consistency)
- Use case: Interactive SQL analytics on HBase data
- Performance: Near-native HBase speed for point queries
```

---

## Scenario-Based Questions

### Scenario 1: Read latency P99 spiked from 10ms to 500ms
```
Diagnosis:
1. GC pauses? → Check GC logs (> 100ms pauses cause tail latency)
2. Compaction storm? → Too many HFiles open (check storeFileCount)
3. HDFS read latency? → DataNode issues, short-circuit reads disabled?
4. BlockCache miss rate? → Cache eviction due to scan queries
5. Region hotspot? → One region getting all traffic

Solutions by cause:
- GC: Tune G1GC, reduce heap (use BucketCache off-heap instead)
- HFiles: Lower compactionThreshold, trigger major compaction
- HDFS: Enable short-circuit reads, check DataNode health
- Cache: Increase BucketCache size, use CACHE_BLOCKS=false for scans
- Hotspot: Pre-split or salt row keys
```

### Scenario 2: RegionServer OOM during bulk loading
```
Cause: MemStore backpressure during high-throughput writes

Solutions:
1. Use bulk load (HFile generation via MapReduce):
   - Generate HFiles offline
   - Use LoadIncrementalHFiles to load directly
   - Bypasses WAL and MemStore entirely
   - 10x faster than Put operations

2. If Puts required:
   - Increase flush.size (256MB)
   - Disable WAL for bulk loads (risk of data loss)
   - Use BufferedMutator with autoFlush=false
   - Rate-limit client writes
   - Add more RegionServers
```

### Scenario 3: Design HBase for 100 billion row messaging system
```
Architecture:
- Row key: hash(sender_id)[0:2] + sender_id + (MAX_LONG - timestamp)
- Column family: "m" (messages), "meta" (read status, flags)
- Pre-split: 256 regions (4-bit hex prefix)
- Compression: SNAPPY
- Bloom filter: ROW
- Versions: 1
- TTL: 365 days

Cluster sizing:
- Data: 100B rows × 1KB avg = 100TB raw
- With compression (3x): 33TB
- With replication (3x HDFS): 100TB on disk
- RegionServers: 50 nodes × 24TB disk = 1.2PB capacity
- RAM per RS: 128GB (BlockCache: 50GB BucketCache, MemStore: 50GB)
- Regions: ~5000 (100TB / 10GB per region = 10,000 with growth room)

Performance targets:
- Write: 1M messages/second (distributed across 50 RS)
- Read: 5M reads/second (80% from BlockCache)
- Scan: Latest 50 messages per user in < 20ms
```

### Scenario 4: Migrating from HBase to Cassandra
```
Assessment:
1. Why migrate?
   - Reduce operational complexity (no ZK, no HDFS, no Master)
   - Multi-DC active-active replication
   - Better auto-scaling (peer-to-peer)

2. Challenges:
   - HBase strong consistency → Cassandra eventual (by default)
   - HBase coprocessors → Cassandra has no equivalent
   - Phoenix SQL layer → Cassandra CQL (simpler)
   - Row key ordering → Partition key hashing (different access patterns)
   - Wide scans → Cassandra limits partition scans

3. Migration strategy:
   - Phase 1: Dual-write (application writes to both)
   - Phase 2: Validate data consistency
   - Phase 3: Switch reads to Cassandra
   - Phase 4: Decommission HBase

4. What breaks:
   - Ordered range scans (must redesign data model)
   - Server-side processing (coprocessors)
   - Multi-version reads
   - Single-row strong consistency (need LOCAL_QUORUM)
```

### Scenario 5: HBase cluster performing poorly after 6 months
```
Common causes after prolonged operation:

1. Region count explosion:
   - Automatic splitting created too many regions
   - Fix: Merge small regions, tune split policy
   - Target: 20-200 regions per RegionServer

2. Compaction debt:
   - Major compactions disabled but never run manually
   - Hundreds of HFiles per store
   - Fix: Schedule rolling major compactions

3. HDFS imbalance:
   - Data locality degraded after splits/moves
   - Fix: Run HDFS balancer, region reassignment for locality

4. Stale BlockCache:
   - Full table scans polluting cache
   - Fix: Use CACHE_BLOCKS=false for batch scans

5. WAL accumulation:
   - Old WAL files not cleaned up
   - Fix: Check replication lag, clean up completed WALs

Maintenance schedule:
- Daily: Monitor metrics, compaction queue
- Weekly: Rolling restart if needed, defrag
- Monthly: Major compaction (rolling across RS)
- Quarterly: Capacity planning, region merging/splitting review
```
