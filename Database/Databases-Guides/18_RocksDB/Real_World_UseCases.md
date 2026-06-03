# RocksDB - Real World Use Cases & Production Guide

## Table of Contents
- [Core Concepts](#core-concepts)
- [Real-World Use Cases](#real-world-use-cases)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Core Concepts

### LSM Tree Architecture

RocksDB is an **embedded key-value store** based on Log-Structured Merge (LSM) trees, optimized for fast storage (SSD/NVMe).

```
                         WRITE PATH
                            │
                            ▼
                    ┌──────────────┐
                    │     WAL      │  (Write-Ahead Log - sequential append)
                    │  (on disk)   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   MemTable   │  (In-memory skiplist/hash, ~64MB default)
                    │  (active)    │
                    └──────┬───────┘
                           │ (when full)
                           ▼
                    ┌──────────────┐
                    │  Immutable   │  (Read-only, awaiting flush)
                    │  MemTable    │
                    └──────┬───────┘
                           │ FLUSH
                           ▼
              ┌─────────────────────────┐
              │     Level 0 (L0)        │  (Overlapping SST files)
              │  [SST][SST][SST][SST]   │  (Each ~64MB, up to 4 files)
              └────────────┬────────────┘
                           │ COMPACTION
                           ▼
              ┌─────────────────────────┐
              │     Level 1 (L1)        │  (Non-overlapping, ~256MB total)
              │  [SST][SST][SST][SST]   │
              └────────────┬────────────┘
                           │ COMPACTION (size ratio = 10x)
                           ▼
              ┌─────────────────────────┐
              │     Level 2 (L2)        │  (~2.56GB total)
              │  [SST][SST]...[SST]     │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │     Level N (Ln)        │  (Largest level, most data)
              │  [SST][SST]......[SST]  │
              └─────────────────────────┘

    Each SST file internally:
    ┌─────────────────────────────────────┐
    │  Data Block 1  │  Data Block 2  │...│
    ├─────────────────────────────────────┤
    │  Meta Block (Bloom Filter)          │
    ├─────────────────────────────────────┤
    │  Index Block (block offsets)        │
    ├─────────────────────────────────────┤
    │  Footer                             │
    └─────────────────────────────────────┘
```

### Write Path (Detail)

```
    Client: Put(key, value)
         │
         ▼
    ┌─────────────┐
    │ Write Group │  (Leader batches multiple writers)
    └──────┬──────┘
           │
           ├──────────────────────┐
           ▼                      ▼
    ┌─────────────┐       ┌─────────────┐
    │  WAL Append │       │  MemTable   │
    │ (fsync or   │       │   Insert    │
    │  group sync)│       │ (skiplist)  │
    └─────────────┘       └─────────────┘
           │
           ▼
    Write returns to client (durable after WAL sync)

    Background:
    ┌──────────────────────────────────────────────┐
    │ Flush Thread:  MemTable → L0 SST file        │
    │ Compaction Thread: Ln + Ln+1 → Ln+1 (merge)  │
    └──────────────────────────────────────────────┘
```

**Write performance**: Single Put ~3-5 μs (with WAL sync disabled), ~30-50 μs (with fsync per write), ~5-10 μs (with group commit).

### Read Path (Detail)

```
    Client: Get(key)
         │
         ▼
    ┌─────────────┐     Found?
    │  MemTable   │ ──────────── → Return value
    │  (active)   │
    └──────┬──────┘
           │ Not found
           ▼
    ┌─────────────┐     Found?
    │  Immutable  │ ──────────── → Return value
    │  MemTables  │
    └──────┬──────┘
           │ Not found
           ▼
    ┌─────────────┐     Bloom Filter → Definitely not here
    │   Level 0   │     (check ALL L0 files, they overlap)
    │  SST files  │     Found? → Return value
    └──────┬──────┘
           │ Not found
           ▼
    ┌─────────────┐     Bloom Filter → skip file
    │   Level 1   │     Binary search index → find block
    │  (1 file)   │     Read data block → find key
    └──────┬──────┘
           │ Not found
           ▼
    ┌─────────────┐
    │   Level 2   │  ... (same process, one file per level)
    │   ...       │
    │   Level N   │
    └─────────────┘
           │ Not found at any level
           ▼
        Return: NotFound
```

**Read amplification**: Worst case = 1 (MemTable) + N_immutable + L0_files + (Lmax - 1) disk reads. With bloom filters (10 bits/key, ~1% FPR), most levels are skipped.

### Bloom Filters

```
    Memory cost: bits_per_key × num_keys
    
    bits_per_key │ False Positive Rate │ Memory per 1B keys
    ─────────────┼─────────────────────┼────────────────────
         10      │       ~1.0%         │     ~1.2 GB
         15      │       ~0.1%         │     ~1.8 GB
         20      │       ~0.01%        │     ~2.4 GB

    Full filters (per SST file) vs Partitioned filters (per block):
    - Full: loaded entirely into memory, faster lookup
    - Partitioned: only load needed partition, lower memory
```

### Compaction Strategies

```
    ┌────────────────────────────────────────────────────────────────────┐
    │  Strategy   │ Write Amp │ Read Amp │ Space Amp │ Best For          │
    ├─────────────┼───────────┼──────────┼───────────┼───────────────────┤
    │ Leveled     │  10-30x   │   1x     │   ~1.1x   │ Read-heavy        │
    │ Universal   │   2-5x    │   Nx     │   ~2x     │ Write-heavy       │
    │ FIFO        │    1x     │   Nx     │   ~1x     │ TTL/time-series   │
    └────────────────────────────────────────────────────────────────────┘
```

**Leveled Compaction** (default):
```
    L0:  [a-z][a-z][a-z][a-z]    ← overlapping, trigger compaction at 4 files
          │
          ▼ Pick one L0 file, merge with overlapping L1 files
    L1:  [a-f][g-m][n-s][t-z]    ← sorted, non-overlapping, 256MB total
          │
          ▼ Pick one L1 file, merge with overlapping L2 files  
    L2:  [a-c][d-f]...[x-z]      ← 10x larger than L1
```

Write amplification for leveled = O(size_ratio × num_levels) ≈ 10 × 6 = **~60x** worst case, typically **10-30x** in practice.

**Universal Compaction**:
```
    Sorted Runs: [R1][R2][R3][R4][R5]
                  newest → oldest
    
    Trigger: when num_runs > max_size_amplification_percent threshold
    Action:  merge adjacent runs (R1+R2 or R1+R2+R3+...)
    
    Write amplification: typically 2-5x (much better for write-heavy)
    Space amplification: up to 2x (needs temporary space during compaction)
```

### Merge Operator

Avoids read-modify-write for counters/append workloads:

```
    Without Merge:                    With Merge:
    val = Get(key)                    Merge(key, delta)
    val += delta                      // No read needed!
    Put(key, val)                     // Merged during compaction or read
    (2 I/Os)                          (1 I/O for write)

    On read: stack of merges applied lazily
    key: [base_value] + [delta1] + [delta2] + [delta3]
         └─────── merged at read time or compaction ───────┘
```

### Transactions

```
    Pessimistic (default TransactionDB):
    ┌─────────────────────────────────────────────┐
    │ BeginTransaction()                          │
    │   GetForUpdate(key) → acquires row lock     │
    │   Put(key, new_val)                         │
    │ Commit() → write to WAL + MemTable          │
    │   (locks released)                          │
    └─────────────────────────────────────────────┘
    - Uses lock manager, deadlock detection
    - Better for high-contention workloads

    Optimistic (OptimisticTransactionDB):
    ┌─────────────────────────────────────────────┐
    │ BeginTransaction()                          │
    │   Get(key) → record read set                │
    │   Put(key, new_val)                         │
    │ Commit() → validate no conflicts → write    │
    │   (retry if conflict)                       │
    └─────────────────────────────────────────────┘
    - No locks during transaction
    - Validation at commit time
    - Better for low-contention workloads
```

### WriteBatch

```cpp
WriteBatch batch;
batch.Put("key1", "val1");
batch.Put("key2", "val2");
batch.Delete("key3");
db->Write(write_options, &batch);
// Atomic: all-or-nothing, single WAL entry
```

### Iterators and Prefix Seeks

```
    Full scan:          iter->SeekToFirst(); iter->Next()...
    Range scan:         iter->Seek("prefix_"); while valid && starts_with("prefix_")
    Prefix seek:        ReadOptions.prefix_same_as_start = true
                        (uses prefix bloom filter, much faster)
    
    Prefix extractor:   SliceTransform (e.g., first 8 bytes)
    ┌────────────────────────────────────────┐
    │ Key: "user:12345:profile"              │
    │ Prefix: "user:123" (first 8 bytes)    │
    │ Bloom filter built on prefix           │
    │ Seek("user:12345:") → only check       │
    │   SST files where prefix bloom matches │
    └────────────────────────────────────────┘
```

---

## Real-World Use Cases

---

### 1. Facebook/Meta's MySQL Storage (MyRocks)

**Problem**: InnoDB (B-tree) uses 2x more storage than necessary. At Meta's scale (petabytes), this means billions in hardware costs.

**Solution**: MyRocks = MySQL + RocksDB storage engine. LSM trees compress better and have less space amplification than B-trees.

#### Architecture

```
    ┌─────────────────────────────────────────────────────────┐
    │                    MySQL Server                          │
    │  ┌─────────────┐  ┌──────────┐  ┌────────────────┐     │
    │  │   Parser    │  │ Optimizer│  │  Executor      │     │
    │  └─────────────┘  └──────────┘  └───────┬────────┘     │
    │                                          │              │
    │  ┌───────────────────────────────────────┴──────────┐   │
    │  │          MySQL Storage Engine API                 │   │
    │  │    (handler interface: open, read, write, etc.)   │   │
    │  └──────────┬──────────────────────────┬────────────┘   │
    │             │                          │                │
    │  ┌──────────▼──────────┐   ┌──────────▼──────────┐     │
    │  │   InnoDB (B-tree)   │   │   MyRocks (LSM)     │     │
    │  │   - Primary tables  │   │   - Archive tables  │     │
    │  │   - Hot data        │   │   - Bulk data       │     │
    │  └─────────────────────┘   └──────────┬──────────┘     │
    │                                        │                │
    └────────────────────────────────────────┼────────────────┘
                                             │
                                    ┌────────▼────────┐
                                    │    RocksDB      │
                                    │                 │
                                    │ CF: default     │ (primary key → row)
                                    │ CF: index_cf    │ (secondary indexes)
                                    │ CF: system_cf   │ (metadata)
                                    │                 │
                                    │ ┌─────────────┐ │
                                    │ │  MemTable   │ │
                                    │ │  (128MB)    │ │
                                    │ └──────┬──────┘ │
                                    │        ▼        │
                                    │ ┌─────────────┐ │
                                    │ │ L0-L6 SSTs  │ │
                                    │ │ (ZSTD comp) │ │
                                    │ └─────────────┘ │
                                    └─────────────────┘
                                             │
                                    ┌────────▼────────┐
                                    │   NVMe SSDs     │
                                    └─────────────────┘
```

#### Configuration Tuning

```ini
# MyRocks configuration at Meta scale
rocksdb_max_open_files=-1                    # Keep all files open
rocksdb_max_background_jobs=8                # Flush + compaction threads
rocksdb_max_total_wal_size=4G               
rocksdb_block_size=16384                     # 16KB blocks (larger for sequential)
rocksdb_block_cache_size=32G                 # Large block cache
rocksdb_table_cache_numshardbits=6           # 64 shards for concurrency

# Compaction
rocksdb_max_subcompactions=4                 # Parallel sub-compactions
rocksdb_compaction_style=LEVEL               # Leveled for read-heavy SQL
rocksdb_level0_file_num_compaction_trigger=4
rocksdb_target_file_size_base=64M
rocksdb_max_bytes_for_level_base=512M
rocksdb_max_bytes_for_level_multiplier=8     # 8x instead of default 10x

# Compression per level (critical for space savings)
rocksdb_compression_per_level=kNoCompression:kNoCompression:kLZ4Compression:kLZ4Compression:kZSTD:kZSTD:kZSTD

# Bloom filters
rocksdb_whole_key_filtering=1
rocksdb_default_cf_options="bloom_bits=10;prefix_extractor=capped:24"
```

#### Write/Read Patterns

```
    Write pattern: SQL INSERT/UPDATE → Row encoded as KV pair
    ┌────────────────────────────────────────────────────┐
    │ Primary Key encoding:                              │
    │   Key = table_id + packed_primary_key              │
    │   Value = packed_row_data                          │
    │                                                    │
    │ Secondary Index encoding:                          │
    │   Key = index_id + packed_index_columns + PK       │
    │   Value = (empty or covering columns)              │
    └────────────────────────────────────────────────────┘

    Read pattern:
    - Point lookups (SELECT by PK): Get() → bloom filter effective
    - Range scans (SELECT with range): Iterator with bounds
    - Secondary index: seek index CF → get PK → seek default CF
```

#### Why RocksDB for This Workload

| Metric | InnoDB (B-tree) | MyRocks (LSM) | Improvement |
|--------|----------------|---------------|-------------|
| Storage used | 1x | 0.5x | **50% less** |
| Write throughput | 1x | 1.5-2x | Better writes |
| Read latency (point) | 1x | 1.1x | Slightly worse |
| Write amplification | 2-3x (page splits) | 10-20x | Worse but managed |

**Key insight**: At Meta's scale, 50% storage reduction = hundreds of millions in savings. The slightly higher read latency is acceptable for the massive storage and cost benefits.

#### Performance Numbers (from Meta's published data)

- **Storage reduction**: 50% compared to compressed InnoDB
- **QPS**: Handles 10M+ queries/sec per shard cluster
- **Compression ratio**: 2.5-3.5x with ZSTD on bottom levels
- **Migration**: Moved UDB (User Database), Messages, and other services

---

### 2. CockroachDB's Storage Layer

**Problem**: Need a fast, embeddable sorted KV store for each node in a distributed SQL database. Must support range scans, atomic writes, and snapshots efficiently.

**Solution**: Originally RocksDB, now Pebble (Go rewrite inspired by RocksDB). Same LSM architecture.

#### Architecture

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                      CockroachDB Cluster                        │
    │                                                                 │
    │  ┌──────────┐      ┌──────────┐      ┌──────────┐             │
    │  │  Node 1  │      │  Node 2  │      │  Node 3  │             │
    │  └────┬─────┘      └────┬─────┘      └────┬─────┘             │
    │       │                 │                  │                    │
    └───────┼─────────────────┼──────────────────┼────────────────────┘
            │                 │                  │
    ┌───────▼─────────────────▼──────────────────▼────────────────────┐
    │                        Raft Consensus                           │
    │         (Each range = Raft group, 3 replicas)                   │
    └───────┬─────────────────┬──────────────────┬────────────────────┘
            │                 │                  │
    ┌───────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐
    │   Range 1    │  │   Range 2    │  │   Range 3    │
    │  [a - f)     │  │  [f - m)     │  │  [m - z)     │
    └───────┬──────┘  └──────┬───────┘  └──────┬───────┘
            │                │                  │
    ┌───────▼────────────────▼──────────────────▼─────────────────────┐
    │                    Storage Engine (per Node)                     │
    │                                                                  │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │                   Pebble (RocksDB-like)                   │   │
    │  │                                                           │   │
    │  │  Key encoding:                                            │   │
    │  │  /Table/TableID/IndexID/Key/Timestamp → Value            │   │
    │  │                                                           │   │
    │  │  MVCC: Multiple versions per key (newest first)           │   │
    │  │  /Table/1/1/"user123"/1609459200.000000001 → {data}      │   │
    │  │  /Table/1/1/"user123"/1609459100.000000001 → {old_data}  │   │
    │  │                                                           │   │
    │  │  ┌─────────┐  ┌──────┐  ┌──────┐  ┌──────┐             │   │
    │  │  │MemTable │→ │  L0  │→ │  L1  │→ │  L2+ │             │   │
    │  │  └─────────┘  └──────┘  └──────┘  └──────┘             │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

#### Configuration Tuning

```go
// CockroachDB/Pebble configuration (representative)
opts := &pebble.Options{
    // Write buffer
    MemTableSize:                64 << 20,  // 64MB MemTable
    MemTableStopWritesThreshold: 4,

    // Level configuration
    L0CompactionThreshold: 2,       // Aggressive L0 compaction
    L0StopWritesThreshold: 12,
    LBaseMaxBytes:         64 << 20, // 64MB base level
    MaxOpenFiles:          10000,
    
    // Compaction
    MaxConcurrentCompactions: func() int { return 3 },
    
    Levels: []pebble.LevelOptions{
        {TargetFileSize: 2 << 20, Compression: pebble.NoCompression},     // L0
        {TargetFileSize: 2 << 20, Compression: pebble.NoCompression},     // L1
        {TargetFileSize: 4 << 20, Compression: pebble.SnappyCompression}, // L2
        {TargetFileSize: 8 << 20, Compression: pebble.SnappyCompression}, // L3
        {TargetFileSize: 16 << 20, Compression: pebble.SnappyCompression},// L4
        {TargetFileSize: 32 << 20, Compression: pebble.SnappyCompression},// L5
        {TargetFileSize: 64 << 20, Compression: pebble.SnappyCompression},// L6
    },
    
    // Bloom filters: 10 bits per key
    // Block size: 32KB (larger for sequential MVCC scans)
}
```

#### Write/Read Patterns

```
    Write path (SQL INSERT):
    ┌─────────────────────────────────────────────────────────┐
    │ SQL: INSERT INTO users VALUES (...)                      │
    │         │                                                │
    │         ▼                                                │
    │ KV: Put(/Table/52/1/"user123"/ts, encoded_row)          │
    │         │                                                │
    │         ▼                                                │
    │ Raft: Replicate to 3 nodes                              │
    │         │                                                │
    │         ▼                                                │
    │ Pebble: WriteBatch (atomically apply Raft log entry)    │
    │   - Intent key (txn record)                             │
    │   - MVCC data key                                       │
    └─────────────────────────────────────────────────────────┘

    Read path (SQL SELECT):
    ┌─────────────────────────────────────────────────────────┐
    │ Seek to /Table/52/1/"user123"/max_ts                    │
    │ Find latest version ≤ read_timestamp                     │
    │ Check for write intents (conflicts)                      │
    │ Return row                                               │
    └─────────────────────────────────────────────────────────┘
    
    MVCC GC: Background process compacts old versions (older than GC TTL)
```

#### Why RocksDB/Pebble

- **Sorted keys**: Range scans map directly to SQL range queries
- **MVCC natural fit**: Keys sorted by timestamp suffix, newest first
- **Snapshots**: Cheap consistent reads without locks
- **WriteBatch**: Atomic application of Raft log entries
- **Prefix bloom**: Fast point lookups by primary key
- **Compaction**: Cleans up old MVCC versions automatically

#### Performance Numbers

- **Write throughput**: 50K-100K writes/sec per node (with Raft)
- **Read latency**: P50 ~1ms, P99 ~10ms (distributed, including network)
- **Storage efficiency**: ~2x compression with Snappy
- **Range split/merge**: Leverages RocksDB's range deletion tombstones

---

### 3. Kafka Streams State Store

**Problem**: Stream processing needs fast local state (counts, aggregations, joins) that survives restarts without re-processing entire topic from beginning.

**Solution**: Kafka Streams uses RocksDB as the default local state store, with changelog topics for fault tolerance.

#### Architecture

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                     Kafka Cluster                                │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
    │  │ Input Topic   │  │ Changelog     │  │ Output Topic  │       │
    │  │ (partitioned) │  │ Topic         │  │               │       │
    │  └───────┬───────┘  └───────▲───────┘  └───────▲───────┘       │
    └──────────┼──────────────────┼──────────────────┼────────────────┘
               │                  │                  │
    ┌──────────▼──────────────────┼──────────────────┼────────────────┐
    │          Kafka Streams Application Instance                      │
    │                                                                  │
    │  ┌─────────────────────────────────────────────────────────┐    │
    │  │              Stream Processing Topology                   │    │
    │  │                                                          │    │
    │  │  source ──→ map ──→ groupByKey ──→ aggregate ──→ sink   │    │
    │  │                          │              │                 │    │
    │  │                          │         read/write             │    │
    │  │                          │              │                 │    │
    │  └──────────────────────────┼──────────────┼────────────────┘    │
    │                             │              │                      │
    │  ┌──────────────────────────▼──────────────▼────────────────┐    │
    │  │              State Store (per partition)                   │    │
    │  │                                                           │    │
    │  │  ┌─────────────────────────────────────────────────┐     │    │
    │  │  │              RocksDB Instance                     │     │    │
    │  │  │                                                  │     │    │
    │  │  │  Key: grouping_key (bytes)                       │     │    │
    │  │  │  Value: aggregate_state (bytes)                  │     │    │
    │  │  │                                                  │     │    │
    │  │  │  /tmp/kafka-streams/app-id/0_0/rocksdb/store    │     │    │
    │  │  │                                                  │     │    │
    │  │  │  Operations:                                     │     │    │
    │  │  │   - put(key, value)    [on each record]          │     │    │
    │  │  │   - get(key)           [for joins/lookups]       │     │    │
    │  │  │   - range(from, to)    [for windowed queries]    │     │    │
    │  │  │   - all()              [for iteration]           │     │    │
    │  │  └─────────────────────────────────────────────────┘     │    │
    │  │                                                           │    │
    │  │  Changelog: every put() → produce to changelog topic     │    │
    │  │  Recovery: consume changelog topic → replay into RocksDB  │    │
    │  └───────────────────────────────────────────────────────────┘    │
    │                                                                    │
    └────────────────────────────────────────────────────────────────────┘

    Fault tolerance:
    ┌────────────┐         ┌─────────────┐         ┌────────────┐
    │ Instance 1 │ ──put──→│  Changelog  │←─replay─│ Instance 2 │
    │ (active)   │         │   Topic     │         │ (standby)  │
    │  RocksDB   │         │             │         │  RocksDB   │
    └────────────┘         └─────────────┘         └────────────┘
```

#### Configuration Tuning

```java
// Kafka Streams RocksDB configuration
Properties props = new Properties();
props.put(StreamsConfig.ROCKSDB_CONFIG_SETTER_CLASS_CONFIG, 
          CustomRocksDBConfig.class.getName());

public class CustomRocksDBConfig implements RocksDBConfigSetter {
    @Override
    public void setConfig(String storeName, Options options, Map<String, Object> configs) {
        // Write buffer
        options.setWriteBufferSize(16 * 1024 * 1024);        // 16MB (smaller per partition)
        options.setMaxWriteBufferNumber(3);
        
        // Block cache shared across all stores in this instance
        BlockBasedTableConfig tableConfig = new BlockBasedTableConfig();
        tableConfig.setBlockCacheSize(50 * 1024 * 1024);     // 50MB per store
        tableConfig.setBlockSize(4096);
        tableConfig.setCacheIndexAndFilterBlocks(true);       // Critical for memory control
        tableConfig.setPinL0FilterAndIndexBlocksInCache(true);
        
        // Bloom filter
        tableConfig.setFilterPolicy(new BloomFilter(10, false));
        options.setTableFormatConfig(tableConfig);
        
        // Compaction (write-heavy streaming workload)
        options.setCompactionStyle(CompactionStyle.UNIVERSAL);  // Less write amp
        options.setMaxBackgroundCompactions(2);
        options.setMaxBackgroundFlushes(1);
        
        // Compression
        options.setCompressionType(CompressionType.LZ4_COMPRESSION);
        
        // Rate limiter (don't starve stream processing)
        options.setRateLimiter(new RateLimiter(50 * 1024 * 1024)); // 50MB/s
    }
}
```

#### Write/Read Patterns

```
    Streaming aggregation (e.g., count per user per window):
    
    For each incoming record:
      1. Get(user_key) → current_count           [point read]
      2. Put(user_key, current_count + 1)        [point write]
    
    Windowed store key format:
      Key = [original_key][window_start_ms][seq_num]
    
    Window query:
      iter.Seek([key][window_start])
      while iter.key starts_with [key] && within window:
          collect results
    
    Pattern: Write-heavy with frequent updates to same keys
    - Same key gets overwritten as aggregate evolves
    - Compaction naturally merges old values (tombstones + overwrites)
```

#### Why RocksDB for This Workload

- **Embedded**: No external dependency, runs in-process with JVM
- **Fast writes**: LSM absorbs high-velocity streaming writes
- **Bounded memory**: Configurable block cache + write buffers
- **Sorted iteration**: Enables windowed range queries
- **Crash recovery**: WAL ensures state survives crashes (plus changelog for full rebuild)
- **Small footprint per partition**: Can run 100s of RocksDB instances per JVM

#### Performance Numbers

- **Write throughput**: 500K-1M state updates/sec per instance
- **Read latency**: <100μs for in-cache point reads
- **Recovery time**: Minutes (from local RocksDB) vs hours (from changelog replay)
- **Memory**: ~200MB per store (cache + write buffers), manageable per partition

---

### 4. Netflix's EVCache with RocksDB

**Problem**: Pure in-memory cache (memcached) is expensive at Netflix scale. Need a persistent caching tier that's cheaper but still fast enough for less-hot data.

**Solution**: EVCache uses RocksDB as a persistent SSD-based tier below the in-memory tier.

#### Architecture

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                    Netflix Microservice                           │
    │                         │                                        │
    └─────────────────────────┼────────────────────────────────────────┘
                              │ get(key) / set(key, value, TTL)
                              ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                     EVCache Client                                │
    │          (consistent hashing, replication, fallback)              │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                  ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │   Tier 1: Memory    │          │   Tier 2: SSD       │
    │   (Memcached)       │          │   (RocksDB)         │
    │                     │          │                     │
    │  - Hot data         │          │  - Warm data        │
    │  - Sub-ms latency   │          │  - 1-5ms latency   │
    │  - Expensive $/GB   │          │  - Cheap $/GB      │
    │  - Limited capacity │          │  - TB capacity     │
    │                     │          │                     │
    └─────────────────────┘          └──────────┬──────────┘
                                                │
                                     ┌──────────▼──────────┐
                                     │     RocksDB         │
                                     │                     │
                                     │  ┌───────────────┐  │
                                     │  │  Block Cache  │  │
                                     │  │  (8-16GB RAM) │  │
                                     │  └───────┬───────┘  │
                                     │          │ miss     │
                                     │          ▼          │
                                     │  ┌───────────────┐  │
                                     │  │  SST Files    │  │
                                     │  │  (NVMe SSD)   │  │
                                     │  │  with Bloom   │  │
                                     │  └───────────────┘  │
                                     │                     │
                                     │  TTL: FIFO or       │
                                     │  compaction filter   │
                                     └─────────────────────┘
    
    Data flow:
    ┌─────────────────────────────────────────────────────┐
    │ Write: set(key, val, TTL=24h)                       │
    │   → Write to Memory tier (hot access)               │
    │   → Async write to SSD tier (persistence)           │
    │                                                     │
    │ Read: get(key)                                      │
    │   → Check Memory tier                               │
    │   → If miss: Check SSD tier (RocksDB)               │
    │   → If hit: Promote to Memory tier                  │
    │                                                     │
    │ Eviction:                                           │
    │   Memory tier: LRU eviction                         │
    │   SSD tier: TTL via compaction filter               │
    └─────────────────────────────────────────────────────┘
```

#### Configuration Tuning

```cpp
// Netflix EVCache RocksDB configuration (representative)
Options options;

// Optimized for cache workload (point lookups with TTL)
options.OptimizeForPointLookup(16);  // 16MB block cache hint

// Large block cache (main performance driver for reads)
BlockBasedTableOptions table_options;
table_options.block_cache = NewLRUCache(16ULL * 1024 * 1024 * 1024);  // 16GB
table_options.block_size = 4096;
table_options.cache_index_and_filter_blocks = true;
table_options.pin_l0_filter_and_index_blocks_in_cache = true;
table_options.filter_policy.reset(NewBloomFilterPolicy(10));

// FIFO compaction for TTL workloads
options.compaction_style = kCompactionStyleFIFO;
options.compaction_options_fifo.max_table_files_size = 500ULL * 1024 * 1024 * 1024; // 500GB
options.compaction_options_fifo.allow_compaction = true;

// OR: Leveled with compaction filter for TTL
// options.compaction_filter = new TTLCompactionFilter(24 * 3600); // 24hr TTL

// Write buffer
options.write_buffer_size = 256 * 1024 * 1024;  // 256MB
options.max_write_buffer_number = 4;

// Compression (cache values often already compressed)
options.compression = kLZ4Compression;

// Direct I/O for large dataset that doesn't fit OS page cache
options.use_direct_reads = true;
options.use_direct_io_for_flush_and_compaction = true;
```

#### Write/Read Patterns

```
    Cache write pattern:
    - Random key writes (cache key = hashed)
    - Values: 1KB - 1MB (serialized objects, JSON, protobuf)
    - High write rate during cache warming
    - Moderate steady-state writes (cache misses → populate)
    
    Cache read pattern:
    - 100% point lookups (Get by exact key)
    - No range scans
    - Hot keys served from block cache
    - Bloom filters eliminate most disk reads for missing keys
    
    TTL management:
    - Keys have embedded TTL timestamp in value
    - Compaction filter checks TTL, drops expired keys
    - FIFO compaction: oldest SST files dropped entirely
```

#### Why RocksDB for This Workload

- **Cost efficiency**: NVMe SSD storage 10x cheaper than DRAM per GB
- **Bloom filters**: Essential for cache (many lookups for non-existent keys)
- **FIFO compaction**: Minimal write amplification for TTL workloads
- **Direct I/O**: Bypass OS page cache, manage own block cache
- **Embedded**: No network hop for cache lookups (in-process)

#### Performance Numbers

- **Read latency**: P50 ~200μs, P99 ~2ms (SSD tier)
- **Write throughput**: 200K-500K writes/sec per instance
- **Cost savings**: 5-10x reduction vs all-DRAM caching
- **Capacity**: 1-2 TB per node (vs 64-128GB for memcached)
- **Bloom filter effectiveness**: 99%+ of negative lookups avoided without disk I/O

---

### 5. LinkedIn's Espresso (Storage Engine)

**Problem**: Need a document store that supports secondary indexes, change capture, and per-document TTL at LinkedIn's scale, with online schema changes.

**Solution**: Espresso uses RocksDB as its storage engine for each partition, storing documents as key-value pairs with a document model on top.

#### Architecture

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                     LinkedIn Application                         │
    │                          │  REST API                            │
    └──────────────────────────┼──────────────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     Espresso Router                              │
    │           (routes request to correct partition/node)             │
    │           (consistent hashing, partition awareness)              │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
    ┌──────────┐          ┌──────────┐          ┌──────────┐
    │  Node 1  │          │  Node 2  │          │  Node 3  │
    │          │          │          │          │          │
    │ ┌──────────────┐   │ ┌──────────────┐   │ ┌──────────────┐
    │ │ Partition 0  │   │ │ Partition 1  │   │ │ Partition 2  │
    │ │              │   │ │              │   │ │              │
    │ │ ┌──────────┐ │   │ │ ┌──────────┐ │   │ │ ┌──────────┐ │
    │ │ │ RocksDB  │ │   │ │ │ RocksDB  │ │   │ │ │ RocksDB  │ │
    │ │ │          │ │   │ │ │          │ │   │ │ │          │ │
    │ │ │ CF: docs │ │   │ │ │ CF: docs │ │   │ │ │ CF: docs │ │
    │ │ │ CF: idx1 │ │   │ │ │ CF: idx1 │ │   │ │ │ CF: idx1 │ │
    │ │ │ CF: idx2 │ │   │ │ │ CF: idx2 │ │   │ │ │ CF: idx2 │ │
    │ │ │ CF: meta │ │   │ │ │ CF: meta │ │   │ │ │ CF: meta │ │
    │ │ └──────────┘ │   │ │ └──────────┘ │   │ │ └──────────┘ │
    │ └──────────────┘   │ └──────────────┘   │ └──────────────┘
    │                │   │                │   │                │
    │ Replication:   │   │                │   │                │
    │ Master→Slave   │   │                │   │                │
    │ via databus    │   │                │   │                │
    └────────┬───────┘   └────────────────┘   └────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   Databus       │  (Change capture stream)
    │   (CDC)         │  (Consumers: search index, analytics, etc.)
    └─────────────────┘

    Document storage layout in RocksDB:
    ┌─────────────────────────────────────────────────────────┐
    │ CF: documents                                           │
    │   Key: [db_id][table_id][partition_key][document_key]   │
    │   Value: [schema_version][serialized_document(Avro)]    │
    │                                                         │
    │ CF: secondary_index_1                                   │
    │   Key: [index_id][indexed_field_value][document_key]    │
    │   Value: (empty or included columns)                    │
    │                                                         │
    │ CF: metadata                                            │
    │   Key: [table_schema][version]                          │
    │   Value: [Avro schema definition]                       │
    └─────────────────────────────────────────────────────────┘
```

#### Configuration Tuning

```cpp
// LinkedIn Espresso RocksDB configuration (representative)
Options options;

// Per-partition RocksDB (many instances per node)
options.write_buffer_size = 32 * 1024 * 1024;     // 32MB per partition
options.max_write_buffer_number = 3;
options.min_write_buffer_number_to_merge = 2;

// Leveled compaction (read-heavy document queries)
options.compaction_style = kCompactionStyleLevel;
options.level0_file_num_compaction_trigger = 4;
options.max_bytes_for_level_base = 256 * 1024 * 1024;  // 256MB
options.max_bytes_for_level_multiplier = 10;
options.target_file_size_base = 64 * 1024 * 1024;

// Column families for isolation
ColumnFamilyOptions doc_cf_options;
doc_cf_options.compression = kZSTD;
doc_cf_options.bottommost_compression = kZSTD;

ColumnFamilyOptions index_cf_options;
index_cf_options.compression = kLZ4Compression;
// Index CF: smaller values, more prefix seeks
index_cf_options.prefix_extractor.reset(NewFixedPrefixTransform(16));
index_cf_options.memtable_prefix_bloom_size_ratio = 0.1;

// Block cache (shared across all CFs on a node)
auto cache = NewLRUCache(32ULL * 1024 * 1024 * 1024);  // 32GB shared
BlockBasedTableOptions table_options;
table_options.block_cache = cache;
table_options.filter_policy.reset(NewBloomFilterPolicy(10));
table_options.cache_index_and_filter_blocks = true;

// Rate limiter (prevent compaction from affecting serving)
options.rate_limiter.reset(NewGenericRateLimiter(100 * 1024 * 1024)); // 100MB/s
```

#### Write/Read Patterns

```
    Document write:
    ┌─────────────────────────────────────────────────────────┐
    │ PUT /espresso/MemberDB/Member/12345                      │
    │ Body: {"name": "John", "company": "LinkedIn", ...}      │
    │                                                          │
    │ → WriteBatch:                                            │
    │     doc_cf.Put([db:1][tbl:1][12345], serialize(doc))     │
    │     idx_cf.Put([idx:1]["LinkedIn"][12345], "")            │
    │     idx_cf.Delete([idx:1]["OldCompany"][12345])          │
    │   (atomic: document + index update in single batch)      │
    └─────────────────────────────────────────────────────────┘

    Document read (by primary key):
    ┌─────────────────────────────────────────────────────────┐
    │ GET /espresso/MemberDB/Member/12345                      │
    │ → doc_cf.Get([db:1][tbl:1][12345])                      │
    │ → Bloom filter: skip irrelevant SSTs                     │
    │ → Typically in block cache (hot documents)              │
    └─────────────────────────────────────────────────────────┘

    Secondary index query:
    ┌─────────────────────────────────────────────────────────┐
    │ GET /espresso/MemberDB/Member?company=LinkedIn&limit=10  │
    │ → idx_cf.Seek([idx:1]["LinkedIn"])                       │
    │ → Iterate: collect document keys                        │
    │ → MultiGet on doc_cf for each document key              │
    └─────────────────────────────────────────────────────────┘
```

#### Why RocksDB for This Workload

- **Column families**: Isolate document storage from indexes (different compaction/compression)
- **WriteBatch**: Atomic document + index updates
- **Prefix iterators**: Efficient secondary index scans
- **Compression**: ZSTD compresses JSON/Avro documents well (3-5x)
- **Embedded**: One RocksDB per partition, simple replication model
- **Merge operator**: Used for counter fields, append-to-list operations

#### Performance Numbers

- **Read latency**: P50 ~1ms, P99 ~5ms (including routing)
- **Write throughput**: 100K+ document writes/sec per node
- **Compression ratio**: 3-4x with ZSTD for document data
- **Index lookups**: Sub-millisecond with prefix bloom filters
- **Serves**: LinkedIn's messaging, feed, profile, and other services

---

## Replication

RocksDB is an **embedded, single-node** library. It has no built-in replication. Systems build replication on top.

### Approaches to Replication with RocksDB

```
    ┌─────────────────────────────────────────────────────────────────┐
    │              Replication Strategies over RocksDB                  │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  1. WAL Shipping (MySQL/MyRocks binlog approach)                │
    │  ┌────────┐    binlog/WAL    ┌────────┐                        │
    │  │ Master │ ───────────────→ │ Slave  │                        │
    │  │RocksDB │                  │RocksDB │                        │
    │  └────────┘                  └────────┘                        │
    │                                                                  │
    │  2. Raft + RocksDB (CockroachDB, TiKV approach)                │
    │  ┌────────┐  Raft log   ┌────────┐  Raft log   ┌────────┐    │
    │  │ Node 1 │◄───────────►│ Node 2 │◄───────────►│ Node 3 │    │
    │  │RocksDB │  consensus  │RocksDB │             │RocksDB │    │
    │  │(Leader)│             │(Follow)│             │(Follow)│    │
    │  └────────┘             └────────┘             └────────┘    │
    │                                                                  │
    │  Flow: Client → Leader → Raft replicate → Apply to RocksDB     │
    │        (each node independently applies committed log entries)   │
    │                                                                  │
    │  3. Application-level replication (Espresso/Databus approach)   │
    │  ┌────────┐   Change events   ┌────────────┐   ┌────────┐    │
    │  │ Master │ ─────────────────→ │  Databus/  │ → │ Slave  │    │
    │  │RocksDB │                    │  Kafka     │   │RocksDB │    │
    │  └────────┘                    └────────────┘   └────────┘    │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
```

### Checkpointing for Backup

```cpp
// Create a point-in-time snapshot (hard links, nearly instant)
Checkpoint* checkpoint;
Checkpoint::Create(db, &checkpoint);
checkpoint->CreateCheckpoint("/backup/path/snap_20240101");

// The checkpoint is a fully functional RocksDB directory
// Can be:
//   - Copied to remote storage (S3, GCS)
//   - Used to bootstrap a new replica
//   - Used for backup/restore
```

### TiKV's Approach (Raft + RocksDB)

```
    ┌─────────────────────────────────────────────────────┐
    │                     TiKV Node                        │
    │                                                      │
    │  ┌──────────────────────────────────────────────┐   │
    │  │              Raft Layer                        │   │
    │  │   - Receives proposals                       │   │
    │  │   - Replicates log entries                   │   │
    │  │   - Commits when majority ack               │   │
    │  └──────────────────┬───────────────────────────┘   │
    │                     │ Committed entries              │
    │                     ▼                                │
    │  ┌──────────────────────────────────────────────┐   │
    │  │           Apply Worker                        │   │
    │  │   - Applies committed entries                │   │
    │  │   - WriteBatch to RocksDB                    │   │
    │  └──────────────────┬───────────────────────────┘   │
    │                     │                                │
    │         ┌───────────┴───────────┐                   │
    │         ▼                       ▼                   │
    │  ┌─────────────┐       ┌─────────────┐             │
    │  │ RocksDB:    │       │ RocksDB:    │             │
    │  │ raft-engine │       │ kv-engine   │             │
    │  │ (raft logs) │       │ (user data) │             │
    │  └─────────────┘       └─────────────┘             │
    │                                                      │
    │  Snapshot transfer for new replicas:                 │
    │  - CreateCheckpoint() of kv-engine                  │
    │  - Stream SST files to new node                     │
    │  - IngestExternalFile() on receiver                 │
    └──────────────────────────────────────────────────────┘
```

---

## Scalability

### Write Amplification Analysis

```
    Write Amplification (WA) = Total bytes written to disk / Bytes written by user

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Leveled Compaction WA                         │
    │                                                                  │
    │  User writes 1 byte:                                            │
    │    1. WAL write:              1x                                 │
    │    2. MemTable flush to L0:   1x                                │
    │    3. L0 → L1 compaction:     ~1x (L0 similar size to L1)      │
    │    4. L1 → L2 compaction:     ~10x (L2 is 10x L1)             │
    │    5. L2 → L3 compaction:     ~10x                             │
    │    ...                                                           │
    │                                                                  │
    │  Total WA ≈ 1 + num_levels × size_ratio                        │
    │           ≈ 1 + 6 × 10 = ~60x (theoretical worst)              │
    │           ≈ 10-30x (typical, not all data reaches bottom)       │
    │                                                                  │
    │  With size_ratio = 8: WA ≈ 1 + 7 × 8 = ~56x                   │
    │  With size_ratio = 4: WA ≈ 1 + 10 × 4 = ~40x (more levels)    │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │                   Universal Compaction WA                        │
    │                                                                  │
    │  Sorted runs merged when count exceeds threshold                │
    │                                                                  │
    │  Best case: merge all runs at once → WA ≈ 2x                   │
    │  Typical: WA ≈ 2-5x                                            │
    │  Controlled by: max_size_amplification_percent                   │
    │                                                                  │
    │  Trade-off: lower WA but higher space amplification (2x)        │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │                     FIFO Compaction WA                           │
    │                                                                  │
    │  No compaction! Just drop oldest files when size limit reached. │
    │  WA = 1x (only flush, no rewriting)                             │
    │  Only works for TTL/time-series data                            │
    └─────────────────────────────────────────────────────────────────┘
```

### Read Amplification Analysis

```
    Read Amplification (RA) = Number of I/O operations per user read

    ┌─────────────────────────────────────────────────────────────────┐
    │  Point lookup (best → worst):                                   │
    │                                                                  │
    │  Best case:   1 (found in MemTable or block cache)              │
    │  With bloom:  1-2 disk reads (bloom eliminates most levels)     │
    │  Worst case:  L0_files + num_levels disk reads                  │
    │               (if key doesn't exist and bloom has FP)            │
    │                                                                  │
    │  Leveled:  RA = 1 per level (non-overlapping, bloom helps)      │
    │  Universal: RA = N sorted runs (overlapping, all checked)       │
    │                                                                  │
    │  Each disk read involves:                                       │
    │    1. Read index block (usually cached)                         │
    │    2. Read bloom filter block (usually cached)                  │
    │    3. Read data block (may or may not be cached)                │
    └─────────────────────────────────────────────────────────────────┘
```

### Space Amplification Analysis

```
    Space Amplification (SA) = Total disk used / Actual live data size

    ┌─────────────────────────────────────────────────────────────────┐
    │  Leveled:    SA ≈ 1.1x (very good)                             │
    │    - Dead data only in files being compacted                    │
    │    - Temporary: ~11% extra during compaction (1/size_ratio)     │
    │                                                                  │
    │  Universal:  SA ≈ up to 2x                                     │
    │    - Multiple sorted runs may contain obsolete versions         │
    │    - During compaction: old + new copy coexist briefly          │
    │                                                                  │
    │  FIFO:       SA ≈ 1x (all data is "live" until TTL expires)    │
    └─────────────────────────────────────────────────────────────────┘

    The three amplifications are in tension:
    ┌─────────────────────────────────────────────────┐
    │         Pick two (like CAP theorem):            │
    │                                                  │
    │         Low Write Amp                            │
    │            /\                                    │
    │           /  \                                   │
    │          /    \     ← Universal                  │
    │         /      \                                 │
    │        /________\                                │
    │  Low Read Amp    Low Space Amp                   │
    │       ↑               ↑                          │
    │    Leveled          Leveled                      │
    │                                                  │
    │  Leveled: low read amp + low space amp           │
    │  Universal: low write amp (sacrifice read/space) │
    └─────────────────────────────────────────────────┘
```

### Column Families for Workload Isolation

```
    ┌────────────────────────────────────────────────────┐
    │              Single RocksDB Instance                │
    │                                                     │
    │  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │
    │  │  CF: default │  │ CF: indexes  │  │ CF: meta│  │
    │  │              │  │              │  │         │  │
    │  │ MemTable 64M│  │ MemTable 32M│  │ MemT 4M│  │
    │  │ Leveled     │  │ Universal    │  │ Leveled │  │
    │  │ ZSTD comp   │  │ LZ4 comp    │  │ No comp│  │
    │  │ 10-bit bloom│  │ Prefix bloom│  │ No bloom│  │
    │  └──────────────┘  └──────────────┘  └─────────┘  │
    │                                                     │
    │  Shared: WAL, block cache, rate limiter, threads   │
    │  Independent: MemTables, compaction, SST files     │
    └────────────────────────────────────────────────────┘
```

### Rate Limiter

```cpp
// Prevent compaction from consuming all I/O bandwidth
options.rate_limiter.reset(NewGenericRateLimiter(
    100 * 1024 * 1024,   // 100 MB/s total rate
    100 * 1000,          // refill period: 100ms
    10,                  // fairness factor
    RateLimiter::Mode::kWritesOnly  // only limit background writes
));

// Auto-tuned rate limiter (adjusts based on I/O capacity)
options.rate_limiter.reset(NewGenericRateLimiter(
    200 * 1024 * 1024,
    100 * 1000,
    10,
    RateLimiter::Mode::kAllIo,
    true  // auto_tuned
));
```

---

## Production Setup

### Tuning by Workload Type

#### Write-Heavy (Logging, Time-Series, Streaming)

```cpp
Options options;
// Large write buffers to batch more before flush
options.write_buffer_size = 256 * 1024 * 1024;           // 256MB
options.max_write_buffer_number = 5;
options.min_write_buffer_number_to_merge = 2;

// Universal compaction for lower write amplification
options.compaction_style = kCompactionStyleUniversal;
options.level0_file_num_compaction_trigger = 8;          // Less aggressive
options.level0_slowdown_writes_trigger = 16;
options.level0_stop_writes_trigger = 24;

// Disable WAL if durability not critical (e.g., cache)
// write_options.disableWAL = true;

// Group commit for better throughput
options.enable_pipelined_write = true;
options.max_total_wal_size = 4ULL * 1024 * 1024 * 1024; // 4GB WAL

// More background threads for compaction
options.max_background_compactions = 8;
options.max_background_flushes = 4;

// Allow concurrent MemTable inserts
options.allow_concurrent_memtable_write = true;
options.enable_write_thread_adaptive_yield = true;
```

#### Read-Heavy (Serving, Cache, Lookups)

```cpp
Options options;
// Leveled compaction for read optimization
options.compaction_style = kCompactionStyleLevel;
options.level_compaction_dynamic_level_bytes = true;

// Large block cache
BlockBasedTableOptions table_options;
table_options.block_cache = NewLRUCache(32ULL * 1024 * 1024 * 1024); // 32GB
table_options.block_size = 16 * 1024;  // 16KB blocks
table_options.cache_index_and_filter_blocks = true;
table_options.pin_l0_filter_and_index_blocks_in_cache = true;
table_options.partition_filters = true;  // Partitioned bloom for huge datasets

// Aggressive bloom filter
table_options.filter_policy.reset(NewBloomFilterPolicy(10));
table_options.whole_key_filtering = true;

// Minimize L0 files (each L0 file is a read-amp penalty)
options.level0_file_num_compaction_trigger = 2;
options.level0_slowdown_writes_trigger = 8;

// Direct I/O to avoid double-caching
options.use_direct_reads = true;

// Readahead for iterators
options.compaction_readahead_size = 2 * 1024 * 1024; // 2MB
```

#### Space-Efficient (Archival, Cold Storage)

```cpp
Options options;
// Maximum compression
options.compression = kZSTD;
options.bottommost_compression = kZSTD;
options.bottommost_compression_opts.max_dict_bytes = 16384; // Dictionary compression
options.bottommost_compression_opts.zstd_max_train_bytes = 1 << 20;

// Leveled for best space amplification
options.compaction_style = kCompactionStyleLevel;
options.level_compaction_dynamic_level_bytes = true;
options.max_bytes_for_level_multiplier = 10;

// Smaller blocks compress better
BlockBasedTableOptions table_options;
table_options.block_size = 4096;

// Enable key-value separation for large values (BlobDB)
options.enable_blob_files = true;
options.min_blob_size = 1024;          // Values > 1KB → blob file
options.blob_compression_type = kZSTD;
```

### Compression Per Level Strategy

```
    Level │ Compression │ Rationale
    ──────┼─────────────┼─────────────────────────────────────────
     L0   │ None        │ Recently written, likely read soon, 
          │             │ compacted away quickly
     L1   │ None/LZ4    │ Small level, fast access needed
     L2   │ LZ4         │ Good speed/ratio trade-off
     L3   │ LZ4         │ 
     L4   │ ZSTD        │ Large levels, data lives longer
     L5   │ ZSTD        │ Compression ratio matters more
     L6   │ ZSTD+Dict   │ Maximum compression for bulk data

    options.compression_per_level = {
        kNoCompression,       // L0
        kNoCompression,       // L1
        kLZ4Compression,      // L2
        kLZ4Compression,      // L3
        kZSTD,                // L4
        kZSTD,                // L5
        kZSTD                 // L6
    };
```

### Block Cache Configuration

```cpp
// Shared LRU cache (most common)
auto cache = NewLRUCache(
    32ULL * 1024 * 1024 * 1024,  // 32GB capacity
    6,                            // num_shard_bits (64 shards for concurrency)
    false,                        // strict_capacity_limit
    0.5                           // high_pri_pool_ratio (50% for index/filter)
);

// Clock cache (better concurrency, no mutex per shard)
auto cache = NewClockCache(32ULL * 1024 * 1024 * 1024);

// Memory budget rule of thumb:
//   Block cache: 1/3 of available RAM
//   OS page cache: 1/3 (for non-direct I/O)
//   MemTables + other: 1/3
```

### WAL Configuration

```cpp
// Sync modes:
WriteOptions wo;
wo.sync = true;                    // fsync every write (safest, slowest)
wo.sync = false;                   // OS buffer, risk last writes on crash
wo.disableWAL = true;             // No WAL (fastest, lose data on crash)

// WAL management:
options.wal_dir = "/fast-ssd/wal";              // Separate WAL on faster device
options.max_total_wal_size = 2ULL * 1024 * 1024 * 1024;  // 2GB max
options.wal_bytes_per_sync = 512 * 1024;        // Background sync every 512KB
options.recycle_log_file_num = 4;               // Reuse WAL files (avoid alloc)

// Manual WAL flush for group commit:
FlushOptions fo;
fo.wait = true;
db->FlushWAL(true);  // Explicit sync point
```

### Monitoring and Statistics

```cpp
// Enable statistics collection
options.statistics = CreateDBStatistics();

// Periodic dump
std::string stats;
db->GetProperty("rocksdb.stats", &stats);               // General stats
db->GetProperty("rocksdb.cfstats", &stats);             // Per-CF stats
db->GetProperty("rocksdb.levelstats", &stats);          // Per-level stats
db->GetProperty("rocksdb.estimate-num-keys", &stats);   // Key count estimate
db->GetProperty("rocksdb.cur-size-all-mem-tables", &stats); // MemTable memory

// Key metrics to monitor:
// - rocksdb.block.cache.hit / rocksdb.block.cache.miss  (cache hit rate)
// - rocksdb.compaction.times.micros                      (compaction latency)
// - rocksdb.stall.micros                                 (write stalls!)
// - rocksdb.num-running-compactions
// - rocksdb.estimate-pending-compaction-bytes
// - rocksdb.num-files-at-levelN

// PerfContext for per-request tracing
SetPerfLevel(kEnableTimeExceptForMutex);
get_perf_context()->Reset();
db->Get(read_options, key, &value);
// get_perf_context()->block_read_count
// get_perf_context()->block_cache_hit_count
// get_perf_context()->get_from_memtable_count

// Event listener for compaction/flush events
class MyListener : public EventListener {
    void OnCompactionCompleted(DB* db, const CompactionJobInfo& info) override {
        // Log compaction stats, alert on high write amp
    }
    void OnStallConditionsChanged(const WriteStallInfo& info) override {
        // ALERT: write stall detected!
    }
};
options.listeners.push_back(std::make_shared<MyListener>());
```

### Critical Alerts to Set Up

```
    ┌─────────────────────────────────────────────────────────────┐
    │  Alert                    │ Threshold        │ Impact        │
    ├───────────────────────────┼──────────────────┼───────────────┤
    │  Write stalls             │ Any occurrence   │ Latency spike │
    │  L0 file count           │ > slowdown_trigger│ Near stall    │
    │  Pending compaction bytes │ > 100GB          │ Falling behind│
    │  Block cache hit rate    │ < 90%            │ Read perf     │
    │  Compaction CPU          │ > 80%            │ Saturation    │
    │  Disk space              │ > 80% used       │ Space amp      │
    └─────────────────────────────────────────────────────────────┘
```

---

## Summary: When to Use RocksDB

```
    ┌─────────────────────────────────────────────────────────────────┐
    │  USE RocksDB when:                                              │
    │  ✓ Write-heavy or write-balanced workloads                      │
    │  ✓ Need embedded KV store (no network overhead)                 │
    │  ✓ Space efficiency matters (better compression than B-trees)   │
    │  ✓ SSD/NVMe storage (LSM designed for flash)                   │
    │  ✓ Need sorted keys for range queries                          │
    │  ✓ Building a database/cache/streaming system's storage layer  │
    │                                                                  │
    │  AVOID RocksDB when:                                            │
    │  ✗ Need distributed/replicated storage (use system built on it)│
    │  ✗ Extreme read-heavy with random reads (B-tree may be better) │
    │  ✗ HDD storage (random reads during compaction hurt)           │
    │  ✗ Need SQL directly (use MyRocks/CockroachDB instead)         │
    │  ✗ Simple caching with no persistence needed (use Redis/Memcached)│
    └─────────────────────────────────────────────────────────────────┘
```
