# Aerospike - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Hybrid Memory Architecture](#hybrid-memory-architecture)
3. [Data Model](#data-model)
4. [Clustering & Distribution](#clustering--distribution)
5. [Consistency & Replication](#consistency--replication)
6. [Performance Characteristics](#performance-characteristics)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Key Design Principles
```
Aerospike is designed for:
- Sub-millisecond latency at scale
- Millions of TPS per node
- Automatic data balancing
- Strong consistency (SC mode) or availability (AP mode)
- Optimized for Flash/SSD storage

Architecture:
┌─────────────────────────────────────────────────┐
│               Aerospike Cluster                   │
│                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │  Node 1   │  │  Node 2   │  │  Node 3   │   │
│  │           │  │           │  │           │   │
│  │ Smart     │  │ Smart     │  │ Smart     │   │
│  │ Client    │  │ Client    │  │ Client    │   │
│  │ Aware     │  │ Aware     │  │ Aware     │   │
│  │           │  │           │  │           │   │
│  │ Index:RAM │  │ Index:RAM │  │ Index:RAM │   │
│  │ Data:SSD  │  │ Data:SSD  │  │ Data:SSD  │   │
│  └───────────┘  └───────────┘  └───────────┘   │
│                                                   │
│  Smart Partitioning: 4096 partitions             │
│  Shared-nothing architecture                      │
│  No single point of failure                      │
└─────────────────────────────────────────────────┘
```

### Hybrid Memory Architecture (HMA)
```
Index layer (always in RAM):
┌────────────────────────────────────┐
│  Primary Index (Red-Black Trees)    │
│  64 bytes per record                │
│  Stored entirely in DRAM            │
│  Enables O(1) record location       │
│                                     │
│  Each index entry:                  │
│  - Key digest (20 bytes, RIPEMD-160)│
│  - Memory/device address            │
│  - Generation count                 │
│  - Void time (expiration)           │
│  - Set membership                   │
└────────────────────────────────────┘

Data layer (configurable):
Option 1: Data in RAM (fastest)
- Sub-100μs latency
- Limited by memory capacity
- Use for: Hot caches, session stores

Option 2: Data on SSD (most common)
- Sub-1ms latency (single SSD read)
- Bypasses filesystem (direct device I/O)
- Aerospike's custom log-structured store
- Use for: Large datasets, cost-effective

Option 3: Data on persistent memory (Intel Optane)
- Sub-microsecond latency
- Byte-addressable, persistent
- Best of both worlds (speed + capacity)
```

---

## Data Model

### Namespace → Set → Record → Bin
```
Namespace: Top-level container (like database)
├── Set: Collection of records (like table, but optional)
│   ├── Record: Single entity (identified by key)
│   │   ├── Bin 1: name="John" (like column, but schema-free)
│   │   ├── Bin 2: age=30
│   │   ├── Bin 3: tags=["premium","active"]
│   │   └── Bin 4: metadata={...}
│   └── Record 2...
└── Set 2...

Key characteristics:
- No predefined schema (bins added per record)
- Each record has: Key (digest), Generation, TTL, Bins
- Max record size: 1MB (configurable up to 8MB)
- Supported types: Integer, Double, String, Bytes, List, Map, GeoJSON
```

### Secondary Indexes
```
Types:
- Numeric (Long/Double range queries)
- String (equality)
- Geospatial (GeoJSON within region)
- List/Map element indexes

// Create secondary index
asinfo -v "sindex-create:ns=test;set=users;indexname=idx_age;indextype=numeric;indexdata=age,numeric"

Limitations:
- Secondary index queries scan all partitions
- Not as efficient as primary key lookup
- Best for: Filtering within bounded result sets
- Not for: Full table scans or high-selectivity queries
```

---

## Clustering & Distribution

### Smart Partitioning
```
4096 logical partitions (fixed):
- Key → RIPEMD-160 hash → partition_id (first 12 bits)
- Each partition assigned to a node (master) + replica nodes
- Automatic rebalancing on node add/remove

Data distribution:
Record Key "user:12345"
    → RIPEMD-160 hash → 20-byte digest
    → First 12 bits → Partition 2847
    → Partition 2847 master: Node 3
    → Partition 2847 replica: Node 1

Smart Client:
- Client maintains partition map (which node owns which partition)
- Sends requests directly to correct node (no proxy hop)
- Single network round-trip for reads/writes
- Partition map refreshed on cluster change
```

### Rack Awareness
```
Rack-aware replication:
- Master and replica on different racks
- Survives entire rack failure
- Configuration: rack-id per node
- Roster-based: Define exactly which nodes hold which data
```

---

## Consistency & Replication

### Strong Consistency Mode (SC)
```
Aerospike 4.0+ offers linearizable reads:
- Uses Raft-like consensus per partition
- Each partition has a "regime" (leader epoch)
- Writes require majority acknowledgment
- Reads are linearizable (always see latest committed write)

Write path (SC):
1. Client → Master (partition owner)
2. Master writes to its copy
3. Master replicates to RF-1 replicas
4. Majority ACK → Committed
5. Master responds to client

Split-brain handling:
- Partition with majority of replicas continues
- Minority side rejects writes
- On rejoin: Conflict resolution via regime number
```

### Availability Mode (AP - Default)
```
- Last-write-wins conflict resolution
- No majority requirement
- Lower latency, higher availability
- Eventual consistency (replicas converge)
- Conflict resolution: Generation count + last-update-time
```

---

## Performance Characteristics

### Why Aerospike is Fast
```
1. Direct SSD I/O (bypasses filesystem):
   - No page cache interference
   - Predictable latency (no OS buffer management)
   - Custom log-structured write (sequential writes, random reads)

2. Index in RAM (O(1) lookup):
   - Primary index always in memory
   - 64 bytes per record (efficient)
   - 1 billion records = 64GB index RAM

3. Smart Client (single hop):
   - Client knows partition map
   - Direct to owning node (no proxy)
   - Reduces latency by eliminating hops

4. Parallelism:
   - Multi-threaded transaction processing
   - Per-partition locking (fine-grained)
   - Pipelining of network I/O

Performance numbers:
- Read: <1ms P99 (SSD), <100μs P99 (RAM)
- Write: <1ms P99 (SSD)
- Throughput: 1M+ TPS per node (mixed workload)
- Scaling: Linear to 100+ nodes
```

---

## Staff Architect Interview Questions

**Q1: When would you choose Aerospike over Redis?**
**A:**
- **Aerospike**: Data too large for RAM (>50GB per node), need SSD economics with sub-ms latency, need strong consistency, need automatic clustering without manual sharding
- **Redis**: Pure in-memory (fastest possible), rich data structures (sorted sets, streams), Lua scripting, simpler operations for smaller datasets, pub/sub
- Key difference: Aerospike stores index in RAM + data on SSD = 10x data capacity at similar latency. Redis is all-RAM = limited by memory cost.

**Q2: Explain Aerospike's approach to SSD usage and why it bypasses the filesystem.**
**A:** Aerospike writes directly to raw block devices:
- Filesystem overhead (journaling, metadata, buffer cache) adds latency
- OS page cache conflicts with Aerospike's own memory management
- Direct I/O enables predictable P99 latency (no cache eviction spikes)
- Log-structured writes: Sequential writes to SSD (write-friendly)
- Random reads: SSD excels at random reads (index in RAM tells exact offset)
- Defragmentation: Background process reclaims dead space

**Q3: How does the Smart Client architecture reduce latency?**
**A:** Traditional architecture: Client → Proxy → Correct Node (2 hops). Aerospike Smart Client: Client → Correct Node (1 hop). The client maintains a partition map (4096 entries) showing which node owns each partition. On key lookup: hash key → partition → node address → direct connection. Map refreshed on cluster topology changes (transparent to application).

---

## Scenario-Based Questions

### Scenario 1: Ad-Tech Real-Time Bidding (RTB)

**Requirements:** 500K lookups/sec, <5ms P99, user profiles with bid history.

```
Architecture:
- 6-node Aerospike cluster
- Index in RAM (~100GB total for 1.5B user profiles)
- Data on NVMe SSD (50TB total)
- Replication factor: 2

Data model:
Namespace: adtech
Set: user_profiles
Record key: user_id (cookie/device_id)
Bins:
  - segments: List<String>  [interest categories]
  - bid_history: Map<timestamp, bid_data>  [last 100 bids]
  - frequency_caps: Map<campaign_id, count>
  - last_seen: Integer (epoch)

Performance:
- Read path: Key → Index (RAM) → Single SSD read → Return
- Latency: 0.5ms average, 2ms P99
- Each node handles ~100K reads/sec
- 6 nodes = 600K reads/sec capacity (with headroom)

TTL strategy:
- User profiles: 90 days TTL (auto-expire inactive users)
- Reduces storage growth automatically
```

### Scenario 2: Session Store Migration from Redis Cluster

**Problem:** Redis cluster at 500GB, expensive RAM. Migrate to Aerospike for cost reduction.

**Migration plan:**
```
1. Data model mapping:
   Redis: HSET session:<id> field1 val1 field2 val2
   Aerospike: Record with key=session_id, bins=field1,field2,...

2. Dual-write phase:
   - Application writes to both Redis and Aerospike
   - Aerospike configured: data on SSD, index in RAM
   - TTL matches Redis EXPIRE

3. Shadow-read phase:
   - Read from both, compare results
   - Measure Aerospike latency vs Redis
   - Expected: Redis <0.5ms, Aerospike <1ms (acceptable)

4. Cutover:
   - Switch reads to Aerospike
   - Monitor latency P99
   - Keep Redis as fallback for 1 week

5. Cost savings:
   - Redis: 500GB RAM = expensive (r6g.16xlarge × 3 = ~$15K/month)
   - Aerospike: 32GB RAM (index) + 500GB SSD = (i3.4xlarge × 3 = ~$5K/month)
   - ~65% cost reduction with <1ms additional latency
```

