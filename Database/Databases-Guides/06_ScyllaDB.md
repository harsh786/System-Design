# ScyllaDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Shard-per-Core Design](#shard-per-core-design)
3. [Storage Engine](#storage-engine)
4. [Consistency & Replication](#consistency--replication)
5. [Performance Architecture](#performance-architecture)
6. [ScyllaDB vs Cassandra](#scylladb-vs-cassandra)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Shard-per-Core Architecture
```
┌─────────────────────────────────────────────────┐
│              ScyllaDB Node                        │
│                                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  │ Shard 0 │ │ Shard 1 │ │ Shard 2 │ │Shard N│ │
│  │ (Core 0)│ │ (Core 1)│ │ (Core 2)│ │(Core N│ │
│  │         │ │         │ │         │ │       │ │
│  │ Own:    │ │ Own:    │ │ Own:    │ │Own:   │ │
│  │-Memtable│ │-Memtable│ │-Memtable│ │-Memtbl│ │
│  │-SSTables│ │-SSTables│ │-SSTables│ │-SSTbls│ │
│  │-Network │ │-Network │ │-Network │ │-Netwrk│ │
│  │-Memory  │ │-Memory  │ │-Memory  │ │-Memory│ │
│  └─────────┘ └─────────┘ └─────────┘ └───────┘ │
│                                                   │
│  No locks, no shared state between shards         │
│  Cross-shard communication via message passing    │
│  Based on Seastar framework (async I/O)          │
└─────────────────────────────────────────────────┘

vs Cassandra (JVM-based):
┌─────────────────────────────────────────────────┐
│            Cassandra Node (JVM)                   │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │         Shared Heap (GC pauses!)             │ │
│  │  Thread pools: Read(32) Write(32) ...        │ │
│  │  Shared memtables, shared SSTables          │ │
│  │  Lock contention, GC stop-the-world         │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Seastar Framework
```
Seastar provides:
1. Future/Promise async programming model
2. Zero-copy networking (userspace TCP stack: DPDK or POSIX)
3. Per-core memory allocation (no inter-core sharing)
4. Cooperative scheduling (no preemption, no context switches)
5. I/O scheduler (prioritizes latency-sensitive operations)

Result:
- No GC pauses (C++, manual memory management)
- No lock contention (shared-nothing)
- Predictable latency (no JVM warmup, no GC)
- Full hardware utilization (each core independent)
- Sub-millisecond P99 latency achievable
```

### Key Differences from Cassandra
```
| Feature | ScyllaDB | Cassandra |
|---------|----------|-----------|
| Language | C++ (Seastar) | Java (JVM) |
| Threading | Shard-per-core | Thread pools |
| GC | None (manual memory) | GC pauses (G1/CMS) |
| Performance | 5-10x throughput per node | Baseline |
| Latency P99 | Sub-ms achievable | 5-50ms typical |
| CPU cores | Fully utilized (all cores) | ~30-50% utilization typical |
| Memory | Direct, per-shard | Heap + off-heap |
| Compatible | CQL wire protocol | Native |
| Compaction | Parallel per-shard | Single compaction thread per table |
| Workload priority | Built-in scheduler | No native prioritization |
```

---

## Shard-per-Core Design

### Data Ownership
```
Token assignment to shards:
- Token ring divided among nodes (same as Cassandra)
- Within each node, tokens further divided among CPU shards
- Each shard owns specific token ranges

Partition routing:
Client → Node → Shard (based on partition key hash)

Cross-shard request:
1. Request arrives at wrong shard
2. Forward to owning shard (message passing, no lock)
3. Owning shard processes and responds

Benefits:
- No contention on memtables (each shard has own)
- No contention on caches (each shard has own)
- Compaction runs per-shard (parallel across cores)
- Network I/O handled per-shard
```

### I/O Scheduler
```
ScyllaDB I/O scheduler prioritizes workloads:

Priority classes:
1. Interactive (user-facing reads/writes) - HIGHEST
2. Streaming (repair, bootstrap) 
3. Compaction
4. Maintenance - LOWEST

Configuration:
# workload_prioritization: true (default in enterprise)
# Ensures compaction doesn't starve user queries

I/O queue:
- Per-shard I/O queue
- Tracks IOPS + bandwidth budget
- Prevents I/O starvation
- Adaptive: learns disk capabilities at startup
```

---

## Storage Engine

### Improved Compaction
```
ScyllaDB compaction improvements over Cassandra:
1. Per-shard compaction (parallel, no shared state)
2. Incremental Compaction Strategy (ICS) - Enterprise
3. Better large-partition handling
4. Compaction runs at full I/O when system is idle
5. Backs off when user queries need I/O

ICS (Incremental Compaction Strategy):
- Runs like LCS but with less space amplification
- Compacts SSTable fragments incrementally
- Never needs 2x temporary space
- Space overhead: ~5% (vs 10% LCS, vs 100% STCS)
```

### Workload Conditioning
```
ScyllaDB auto-tunes for workload:
1. Cache warming (preloads hot data on startup)
2. Row cache with invalidation (not just key cache)
3. Automatic memory allocation between:
   - Memtables
   - Row cache
   - Key cache
   - Operating system page cache
4. Dynamic adjustment based on access patterns
```

---

## Consistency & Replication

### Same as Cassandra but with Additions
```
ScyllaDB maintains Cassandra compatibility:
- Same consistency levels (ONE, QUORUM, ALL, etc.)
- Same replication strategies (Simple, NetworkTopology)
- Same tunable consistency model (R + W > RF)

Additional features:
1. Tablets (ScyllaDB 6.0+):
   - Replacement for vnodes
   - Finer-grained data distribution
   - Faster rebalancing (move tablets not token ranges)
   - Less streaming during topology changes

2. Raft-based schema management:
   - Consistent schema across nodes
   - No schema disagreement issues
   - Eliminates Cassandra's schema version conflicts
```

---

## Performance Architecture

### Benchmark Comparison
```
Typical benchmarks (YCSB, similar hardware):

Workload A (50% read, 50% write):
- ScyllaDB: 1M ops/sec per node (3 nodes = 3M)
- Cassandra: 100-200K ops/sec per node

Workload B (95% read, 5% write):
- ScyllaDB: 1.5M ops/sec per node
- Cassandra: 150-300K ops/sec per node

Latency (P99):
- ScyllaDB: 1-5ms
- Cassandra: 10-100ms (GC dependent)

TCO advantage:
- 5-10x fewer nodes for same throughput
- 3 ScyllaDB nodes can replace 30 Cassandra nodes
- Significant hardware cost savings
```

### When to Choose ScyllaDB over Cassandra
```
Choose ScyllaDB when:
1. Need predictable low latency (P99 < 5ms)
2. High throughput requirements (>500K ops/sec per node)
3. Want to reduce cluster size (cost optimization)
4. Latency-sensitive applications (gaming, ad-tech, financial)
5. Already using Cassandra but fighting GC pauses
6. Need workload prioritization

Choose Cassandra when:
1. Existing Cassandra expertise in team
2. Need specific Cassandra features not yet in ScyllaDB
3. Prefer open-source only (ScyllaDB Enterprise has features not in OSS)
4. Large existing Cassandra ecosystem tooling
5. Running on lower-spec hardware (ScyllaDB needs modern hardware)
```

---

## Staff Architect Interview Questions

**Q1: How does shard-per-core design eliminate the need for locks?**
**A:** Each CPU core (shard) owns its portion of data exclusively. No two shards access the same memtable, SSTable, or cache entry. Communication between shards uses message passing (like actor model). This eliminates:
- Mutex contention on memtable writes
- Lock contention on cache access
- Synchronization overhead on compaction
- Thread pool scheduling overhead
The trade-off is more complex programming model (futures/promises, cooperative scheduling) but results in near-linear scalability with core count.

**Q2: Why does ScyllaDB achieve better tail latency than Cassandra?**
**A:**
- No GC pauses (C++ vs JVM): Eliminates 50-500ms stop-the-world pauses
- I/O scheduler: Prevents compaction from starving reads
- Cooperative scheduling: No thread preemption overhead
- Per-shard architecture: No lock wait times
- Userspace networking (DPDK): Kernel bypass for network I/O
- Result: P99 latency is 10-100x better than Cassandra

**Q3: When would you NOT recommend ScyllaDB?**
**A:**
- Small datasets (< 100GB): Over-engineered, PostgreSQL is simpler
- Light workloads (< 10K ops/sec): Any database works
- Heavy ad-hoc analytics: Consider ClickHouse or Spark
- Strong multi-row transactions: Consider CockroachDB
- Complex queries (JOINs, subqueries): Use PostgreSQL
- Teams without operational expertise for distributed databases
- Workloads that need ACID transactions across partitions

---

## Scenario-Based Questions

### Scenario 1: Cassandra to ScyllaDB Migration

**Steps:**
```
1. Validate compatibility:
   - CQL compatibility (99%+ compatible)
   - Check for unsupported features (some MV limitations)
   - Test with ScyllaDB's cassandra-stress equivalent

2. Migration approaches:
   
   Option A: Dual-write + backfill
   - Write to both clusters
   - Backfill ScyllaDB using Spark/sstableloader
   - Validate data consistency
   - Switch reads to ScyllaDB
   - Remove Cassandra writes

   Option B: ScyllaDB Migrator (spark-based)
   - Reads from Cassandra, writes to ScyllaDB
   - Preserves timestamps and TTLs
   - Can run incrementally

   Option C: sstableloader
   - Export SSTables from Cassandra
   - Convert and load into ScyllaDB
   - Fastest for bulk migration

3. Sizing:
   - ScyllaDB needs 3-10x fewer nodes
   - Each node needs: NVMe SSD, 16+ cores, 64GB+ RAM
   - Typical: 3 i3.4xlarge replaces 30 Cassandra i3.xlarge

4. Validation:
   - Run parallel reads, compare results
   - Load test ScyllaDB cluster independently
   - Monitor P99 latency under production-like load
```

### Scenario 2: Handling 10M ops/sec with ScyllaDB

**Architecture:**
```
Requirements: 10M mixed reads/writes per second

Sizing:
- ScyllaDB can handle ~1M ops/sec per node (modern hardware)
- 10 nodes with RF=3 → 10M ops/sec capacity
- Add 50% headroom → 15 nodes

Hardware per node:
- CPU: 32+ cores (AMD EPYC or Intel Xeon)
- RAM: 256GB (large row cache, reduce disk reads)
- Storage: 4x NVMe SSDs (RAID0 or JBOD)
- Network: 25Gbps (10Gbps minimum)

Configuration:
- Shard count = CPU cores (automatic)
- Compaction: ICS (Enterprise) or LCS (Open Source)
- Consistency: LOCAL_QUORUM for strong, ONE for eventual
- Write concern: Based on data criticality
- Driver: shard-aware (routes to correct shard directly)

Client optimization:
- Shard-aware driver (skip coordinator hop)
- Prepared statements (compiled once, reused)
- Token-aware routing (send to owning node)
- Connection per shard (maximize parallelism)
```

