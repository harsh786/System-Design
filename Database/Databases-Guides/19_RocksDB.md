# RocksDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [LSM-Tree Internals](#lsm-tree-internals)
3. [MemTable & Write-Ahead Log](#memtable--write-ahead-log)
4. [SSTable Format](#sstable-format)
5. [Compaction Strategies](#compaction-strategies)
6. [Block Cache & Read Performance](#block-cache--read-performance)
7. [Write Performance & Tuning](#write-performance--tuning)
8. [Memory Management](#memory-management)
9. [Transactions & Concurrency Control](#transactions--concurrency-control)
10. [Production Configuration & Tuning](#production-configuration--tuning)
11. [Use Case Architectures](#use-case-architectures)
12. [Backup, Restore & Operations](#backup-restore--operations)
13. [Staff Architect Interview Questions](#staff-architect-interview-questions)
14. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is RocksDB?
```
RocksDB is an embedded, persistent key-value store optimized for fast storage
(SSD/NVMe). Originally forked from LevelDB by Facebook in 2012.

Key characteristics:
- Embedded library (no client-server, runs in-process)
- LSM-tree based (write-optimized)
- Keys and values are arbitrary byte arrays
- Keys are sorted (supports range scans)
- Optimized for flash storage (SSD/NVMe)
- Written in C++ with bindings for Java, Python, Go, Rust

NOT a standalone database - it's a storage ENGINE used by:
- MySQL (MyRocks) - Facebook's MySQL fork
- TiKV - Storage layer for TiDB
- CockroachDB - Pebble (inspired by RocksDB)
- Apache Flink - State backend
- Kafka Streams - State store
- YugabyteDB - DocDB layer
- Apache Spark - Structured Streaming state
```

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION                                │
│                   (CockroachDB, TiKV, MyRocks, etc.)            │
├─────────────────────────────────────────────────────────────────┤
│                        RocksDB API                                │
│              Put() / Get() / Delete() / Iterator                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    WRITE PATH                             │    │
│  │                                                           │    │
│  │  Client Write                                             │    │
│  │      │                                                    │    │
│  │      ▼                                                    │    │
│  │  ┌──────────┐    ┌──────────────────────────────────┐    │    │
│  │  │   WAL    │    │         MemTable (Active)         │    │    │
│  │  │(Write    │◄──►│  (SkipList - sorted in memory)   │    │    │
│  │  │ Ahead    │    └──────────────────────────────────┘    │    │
│  │  │  Log)    │    ┌──────────────────────────────────┐    │    │
│  │  └──────────┘    │      Immutable MemTable(s)        │    │    │
│  │                   │    (Waiting to be flushed)        │    │    │
│  │                   └───────────────┬──────────────────┘    │    │
│  │                                   │ Flush                  │    │
│  │                                   ▼                        │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   STORAGE (SST Files)                     │    │
│  │                                                           │    │
│  │  Level 0:  [SST] [SST] [SST] [SST]  (overlapping keys)  │    │
│  │                    │ Compaction                            │    │
│  │                    ▼                                       │    │
│  │  Level 1:  [SST] [SST] [SST] [SST] [SST]  (sorted)     │    │
│  │                    │ Compaction                            │    │
│  │                    ▼                                       │    │
│  │  Level 2:  [SST][SST][SST][SST][SST][SST][SST] (10x)   │    │
│  │                    │                                       │    │
│  │                    ▼                                       │    │
│  │  Level N:  [...many more SST files...] (10x each level)  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    READ PATH                              │    │
│  │                                                           │    │
│  │  Client Read (Get/Iterator)                               │    │
│  │      │                                                    │    │
│  │      ▼                                                    │    │
│  │  MemTable → Immutable MemTables → Block Cache             │    │
│  │      │              │                   │                  │    │
│  │      └──────────────┴───────────────────┘                 │    │
│  │                     │ (miss)                               │    │
│  │                     ▼                                      │    │
│  │  Bloom Filters → SST L0 → SST L1 → SST L2 → ... Ln     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles
```
1. Write Optimization (LSM-tree):
   - Sequential writes to WAL + in-memory sort
   - No random I/O for writes
   - Batch writes amortize overhead

2. Space Efficiency:
   - Aggressive compression (LZ4, ZSTD, Snappy)
   - Prefix compression in keys
   - Compact SST format

3. Read Optimization (despite LSM penalty):
   - Bloom filters eliminate unnecessary disk reads
   - Block cache for hot data
   - Prefix bloom for range scans
   - Compaction reduces read amplification over time

4. Tunability:
   - 100+ configurable options
   - Different compaction strategies
   - Workload-specific optimization
```

---

## LSM-Tree Internals

### How LSM-Tree Works
```
LSM = Log-Structured Merge Tree

Core Idea:
- Convert random writes → sequential writes
- Buffer writes in memory (MemTable)
- Periodically flush to sorted files on disk (SST)
- Background compaction merges and sorts files

Trade-off Triangle:
┌─────────────────────────────────────────────┐
│                                              │
│         Write Amplification (WA)            │
│              /          \                    │
│             /            \                   │
│            /              \                  │
│           /   YOU CAN'T    \                 │
│          /   OPTIMIZE ALL   \                │
│         /    THREE AT ONCE   \               │
│        /                      \              │
│       ▼                        ▼             │
│  Read Amplification      Space Amplification │
│       (RA)                    (SA)           │
│                                              │
│  WA = bytes written to storage / bytes       │
│       written by application                 │
│  RA = bytes read from storage / bytes        │
│       requested by application               │
│  SA = size of storage / size of data         │
└─────────────────────────────────────────────┘

Level Compaction: WA=10-30x, RA=low, SA=~1.1x
Universal Compaction: WA=low, RA=higher, SA=2x
FIFO: WA=1x, RA=high, SA=1x
```

### Write Path (Detailed)
```
Application: db->Put(key, value)
         │
         ▼
┌────────────────────┐
│  Write Batch       │  (Group multiple writes together)
│  (optional)        │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Write to WAL      │  (Sequential append to log file)
│  (fsync optional)  │  (Guarantees durability)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Insert into       │  (Concurrent inserts with SkipList)
│  Active MemTable   │  (Sorted by key)
└────────┬───────────┘
         │
         │  When MemTable size >= write_buffer_size (default 64MB)
         ▼
┌────────────────────┐
│  Switch MemTable   │  Active → Immutable
│  Create new active │  (Write continues to new MemTable)
└────────┬───────────┘
         │
         │  Background flush thread
         ▼
┌────────────────────┐
│  Flush Immutable   │  Write sorted data to SST file in L0
│  MemTable to L0    │  (Delete WAL for flushed data)
└────────┬───────────┘
         │
         │  When L0 files >= level0_file_num_compaction_trigger
         ▼
┌────────────────────┐
│  Compaction         │  Merge L0 → L1, L1 → L2, etc.
│  (Background)       │  (Merge-sort, remove tombstones)
└─────────────────────┘

Write Throughput (typical):
- Single writer: 40-80 MB/s on NVMe
- With WAL sync: 10-30K ops/sec
- Without WAL sync: 200-500K ops/sec
- Bulk load (IngestExternalFile): 500+ MB/s
```

### Read Path (Detailed)
```
Application: db->Get(key)
         │
         ▼
┌────────────────────┐
│  Active MemTable   │  O(log N) lookup in SkipList
│  Found? → Return   │
└────────┬───────────┘
         │ (not found)
         ▼
┌────────────────────┐
│  Immutable         │  Check each immutable MemTable
│  MemTables         │  (newest to oldest)
└────────┬───────────┘
         │ (not found)
         ▼
┌────────────────────┐
│  Block Cache       │  LRU cache of SST data blocks
│  (in memory)       │  Hit rate typically 90-99%
└────────┬───────────┘
         │ (cache miss)
         ▼
┌────────────────────┐
│  Bloom Filter      │  Check per-SST bloom filter
│  (per SST file)    │  False positive rate: ~1%
│                    │  If negative → skip this SST
└────────┬───────────┘
         │ (might be in this SST)
         ▼
┌────────────────────┐
│  Index Block       │  Binary search in SST index
│  (per SST file)    │  Find data block containing key
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Data Block        │  Read block from disk
│  (from disk/cache) │  Binary search within block
└─────────────────────┘

Read Amplification (Level Compaction):
- Best case: 1 read (found in MemTable or cache)
- Worst case: L0_files + 1 per level (L1..Ln)
- With bloom filters: typically 1-2 disk reads
- Point lookup latency: 50-200 μs (SSD), <50 μs (NVMe)
```

### Level Structure
```
┌──────────────────────────────────────────────────────────────┐
│                    LEVEL STRUCTURE                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Level 0 (L0): 4 files (default trigger)                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                       │
│  │[a-z] │ │[b-x] │ │[c-w] │ │[a-y] │  ← OVERLAPPING       │
│  └──────┘ └──────┘ └──────┘ └──────┘    (each is a flush)  │
│                                                               │
│  Level 1 (L1): 256 MB total (max_bytes_for_level_base)       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                       │
│  │[a-d] │ │[e-h] │ │[i-p] │ │[q-z] │  ← NON-OVERLAPPING   │
│  └──────┘ └──────┘ └──────┘ └──────┘    (sorted,disjoint)  │
│                                                               │
│  Level 2 (L2): 2.56 GB total (10x L1)                       │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐         │
│  │a-b ││c-d ││e-f ││g-i ││j-m ││n-q ││r-u ││v-z │         │
│  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘          │
│                                                               │
│  Level 3 (L3): 25.6 GB total (10x L2)                       │
│  [...many more files, each target_file_size_base (64MB)...]  │
│                                                               │
│  Level 4 (L4): 256 GB total (10x L3)                        │
│  Level 5 (L5): 2.56 TB total (10x L4)                       │
│  Level 6 (L6): 25.6 TB total (10x L5)                       │
│                                                               │
│  Size Ratio = max_bytes_for_level_multiplier (default: 10)   │
│  L(n+1) = L(n) * 10                                         │
└──────────────────────────────────────────────────────────────┘
```

---

## MemTable & Write-Ahead Log

### MemTable Implementations
```
┌───────────────────────────────────────────────────────────────┐
│ MemTable Type     │ Use Case                  │ Complexity     │
├───────────────────┼───────────────────────────┼────────────────┤
│ SkipList          │ Default, general purpose  │ O(log N) all   │
│ (default)         │ Good for range scans      │ operations     │
├───────────────────┼───────────────────────────┼────────────────┤
│ HashSkipList      │ Point lookups + prefix    │ O(1) point     │
│                   │ range scans               │ O(log N) range │
├───────────────────┼───────────────────────────┼────────────────┤
│ HashLinkList      │ Point lookups only        │ O(1) lookup    │
│                   │ No range scan support     │ No ordering    │
├───────────────────┼───────────────────────────┼────────────────┤
│ Vector            │ Bulk loading only         │ O(1) write     │
│                   │ (keys must be in order)   │ Not for reads  │
└───────────────────────────────────────────────────────────────┘

SkipList MemTable (Default):
┌─────────────────────────────────────────────────┐
│  Level 3:  ─────────────────────●───────────●   │
│  Level 2:  ───●─────────●───────●───────────●   │
│  Level 1:  ───●────●────●───●───●────●──●───●   │
│  Level 0:  ───●──●─●──●─●─●─●─●─●──●─●──●──●   │
│             (sorted keys, O(log N) operations)   │
└─────────────────────────────────────────────────┘
```

### Write-Ahead Log (WAL)
```
WAL Purpose:
- Durability guarantee before data is flushed to SST
- Recovery on crash (replay WAL to rebuild MemTable)
- Sequential append-only writes (fast on any storage)

WAL File Format:
┌─────────────────────────────────────────────┐
│  Block 1 (32KB)                              │
│  ┌───────────────────────────────────────┐  │
│  │ Record: [CRC | Length | Type | Data]  │  │
│  │ Record: [CRC | Length | Type | Data]  │  │
│  │ ...                                   │  │
│  └───────────────────────────────────────┘  │
├─────────────────────────────────────────────┤
│  Block 2 (32KB)                              │
│  ┌───────────────────────────────────────┐  │
│  │ Records continue...                   │  │
│  └───────────────────────────────────────┘  │
├─────────────────────────────────────────────┤
│  ...                                         │
└─────────────────────────────────────────────┘

Record Types:
- kFullType (1): Complete record in one block
- kFirstType (2): Start of multi-block record
- kMiddleType (3): Middle of multi-block record
- kLastType (4): End of multi-block record

WAL Modes:
- sync = true: fsync after every write (durable, slower)
- sync = false: OS buffer (faster, risk data loss on crash)
- manual WAL flush: application controls when to sync

WAL Lifecycle:
1. Created when new MemTable is created
2. Appended with every write operation
3. Archived when MemTable becomes immutable
4. Deleted after MemTable is successfully flushed to SST
```

### Column Families
```
Column Families = Logical partitions within one DB instance

┌─────────────────────────────────────────────────┐
│                  RocksDB Instance                 │
│                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │   CF:       │  │   CF:       │  │  CF:    │ │
│  │  "default"  │  │  "metadata" │  │ "index" │ │
│  │             │  │             │  │         │ │
│  │ MemTable    │  │ MemTable    │  │MemTable │ │
│  │ SST files   │  │ SST files   │  │SST files│ │
│  │ (own levels)│  │ (own levels)│  │(own lvl)│ │
│  └─────────────┘  └─────────────┘  └─────────┘ │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │         SHARED WAL (single file)           │   │
│  │  (writes from all CFs interleaved)        │   │
│  └───────────────────────────────────────────┘   │
│                                                   │
│  Benefits:                                        │
│  - Atomic writes across column families          │
│  - Independent compaction per CF                 │
│  - Different options per CF (compression, etc.)  │
│  - Shared WAL reduces I/O                        │
└─────────────────────────────────────────────────┘

Use cases for Column Families:
- TiKV: separate CF for data, lock, write columns
- MyRocks: map MySQL column families
- Separate hot/cold data with different compression
```

---

## SSTable Format

### SST File Internal Layout
```
┌─────────────────────────────────────────────────────────────┐
│                    SST FILE (Block-Based Table)               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Data Block 1                                        │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │ Key1:Value1 | Key2:Value2 | ... | KeyN:ValueN│   │    │
│  │  │ (sorted, prefix-compressed keys)             │   │    │
│  │  │ Restart points every 16 keys (default)       │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  │  [Compression] [CRC32]                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Data Block 2 ... Data Block N                       │    │
│  │  (each block is ~4KB, configurable)                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Filter Block (Bloom Filter)                         │    │
│  │  - Per-block or per-table bloom filter              │    │
│  │  - bits_per_key determines false positive rate      │    │
│  │  - 10 bits/key → ~1% FP rate                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Index Block                                         │    │
│  │  - Maps key ranges to data block offsets            │    │
│  │  - Binary searchable                                │    │
│  │  - Can be partitioned for large files               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Meta-Index Block                                    │    │
│  │  - Points to filter block and other metadata        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Footer (fixed size, 48 bytes)                       │    │
│  │  - Offset to meta-index block                       │    │
│  │  - Offset to index block                            │    │
│  │  - Magic number (identifies file format)            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Compression Options
```
┌────────────────────────────────────────────────────────────┐
│ Algorithm │ Ratio │ Compress Speed │ Decompress │ Use Case │
├───────────┼───────┼────────────────┼────────────┼──────────┤
│ None      │ 1x    │ N/A            │ N/A        │ Testing  │
│ Snappy    │ 1.5x  │ 500 MB/s       │ 500 MB/s   │ Default  │
│ LZ4       │ 2.0x  │ 400 MB/s       │ 800 MB/s   │ Fast     │
│ LZ4HC     │ 2.5x  │ 100 MB/s       │ 800 MB/s   │ Balanced │
│ ZSTD      │ 3-4x  │ 200 MB/s       │ 500 MB/s   │ Best     │
│ Zlib      │ 3-4x  │ 50 MB/s        │ 200 MB/s   │ Legacy   │
└────────────────────────────────────────────────────────────┘

Recommended per-level compression:
  Level 0-1: No compression or LZ4 (fast access, recent data)
  Level 2+:  ZSTD (best ratio, cold data)

  options.compression_per_level = {
    kNoCompression,     // L0
    kLZ4Compression,    // L1
    kZSTD,              // L2
    kZSTD,              // L3
    kZSTD,              // L4
    kZSTD,              // L5
    kZSTD               // L6
  };
```

### Bloom Filters
```
Purpose: Avoid unnecessary disk reads for non-existent keys

How it works:
1. During SST creation, hash each key into bloom filter bit array
2. During read, check bloom filter BEFORE reading data blocks
3. If bloom says "not present" → definitely not in this SST (skip)
4. If bloom says "maybe present" → read the data block (might be FP)

                    bits_per_key vs False Positive Rate
┌───────────────────────────────────────────────────────────┐
│  bits_per_key │  FP Rate   │  Memory per 1M keys         │
├───────────────┼────────────┼─────────────────────────────┤
│      5        │   ~10%     │   625 KB                     │
│      8        │   ~2.5%    │   1 MB                       │
│     10        │   ~1%      │   1.25 MB (recommended)      │
│     15        │   ~0.1%    │   1.875 MB                   │
│     20        │   ~0.01%   │   2.5 MB                     │
└───────────────────────────────────────────────────────────┘

Types:
- Full bloom filter: One filter per SST file (whole-key)
- Prefix bloom filter: Filter on key prefix (for prefix scans)
- Partitioned filters: Split across multiple blocks (for large SSTs)
  - Better cache behavior for large datasets
  - Only load relevant filter partitions
```

---

## Compaction Strategies

### Level Compaction (Default)
```
Trigger: L0 file count >= level0_file_num_compaction_trigger (default: 4)

Process:
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  L0:  [a-z] [b-y] [c-x] [d-w]  ← 4 overlapping files      │
│         │     │     │     │                                   │
│         └─────┴─────┴─────┘                                  │
│                  │                                             │
│                  ▼  COMPACTION (merge sort)                   │
│                                                               │
│  L1:  [a-g] [h-n] [o-t] [u-z]  ← sorted, non-overlapping   │
│                                                               │
│  When L1 size > max_bytes_for_level_base (256MB):            │
│                                                               │
│  Pick one file from L1: [h-n]                                │
│  Find overlapping files in L2: [g-i] [j-l] [m-o]            │
│  Merge them together:                                        │
│                                                               │
│  L1: [h-n]  +  L2: [g-i][j-l][m-o]                         │
│       │              │    │    │                              │
│       └──────────────┴────┴────┘                             │
│                    │                                          │
│                    ▼  MERGE SORT                              │
│                                                               │
│  L2: [g-h] [i-k] [l-n] [o-o]  ← new files replace old      │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Write Amplification Analysis:
- Each key is rewritten once per level
- With 7 levels: WA ≈ (level_multiplier/2) * (num_levels - 1)
- Default: (10/2) * 6 = 30x theoretical max
- Practical: 10-30x depending on workload

Pros: Low space amplification (~10%), good read performance
Cons: High write amplification
```

### Universal Compaction
```
All files exist conceptually on one "level" (sorted runs):

┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  Sorted Run 1 (newest): [SST] [SST] [SST]                  │
│  Sorted Run 2:          [SST] [SST] [SST] [SST]            │
│  Sorted Run 3:          [SST] [SST] [SST] [SST] [SST]     │
│  Sorted Run 4 (oldest): [SST] [SST] [SST] [SST] [SST]     │
│                                                               │
│  Compaction triggers when:                                   │
│  - Number of sorted runs > max_size_amplification_percent   │
│  - Size ratio between consecutive runs                       │
│                                                               │
│  Strategies:                                                  │
│  1. Size-ratio triggered: merge small runs                   │
│  2. Space amplification: merge all into one run             │
│                                                               │
│  Write Amplification: 2-5x (much lower than Level)          │
│  Space Amplification: up to 2x (temporary during compaction)│
│  Read Amplification: higher (more sorted runs to check)     │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Best for:
- Write-heavy workloads (logging, streaming)
- When write amplification must be minimized
- Workloads tolerant of temporary space spikes
```

### FIFO Compaction
```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  Newest ──────────────────────────────────────── Oldest     │
│  [SST] [SST] [SST] [SST] [SST] [SST] [SST] → DELETE       │
│                                                               │
│  - No merge, no rewrite                                      │
│  - Simply drop oldest files when total size exceeds limit    │
│  - Write amplification: 1x (minimum possible)               │
│  - TTL-based: drop files older than max_table_files_size    │
│                                                               │
│  Use cases:                                                   │
│  - Time-series with fixed retention                          │
│  - Cache-like workloads                                      │
│  - When data has natural TTL                                 │
│                                                               │
│  Limitations:                                                 │
│  - No updates/deletes (tombstones don't get cleaned)        │
│  - Point lookups are slow (no compaction to reduce files)   │
│  - All files in L0 (overlapping key ranges)                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Compaction Filters
```
Custom logic executed during compaction:

class MyCompactionFilter : public CompactionFilter {
  Decision FilterV2(int level, const Slice& key,
                    ValueType type, const Slice& value,
                    std::string* new_value) {
    if (IsExpired(key)) return kRemove;
    if (NeedTransform(value)) {
      *new_value = Transform(value);
      return kChangeValue;
    }
    return kKeep;
  }
};

Use cases:
- TTL expiration (remove expired keys during compaction)
- Data transformation (schema migration)
- Garbage collection (remove orphaned references)
- Statistics collection during compaction
```

---

## Block Cache & Read Performance

### Cache Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     READ CACHES                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────┐                │
│  │          Row Cache (optional)            │                │
│  │  - Caches entire key-value pairs        │                │
│  │  - Best for point lookup workloads      │                │
│  │  - Bypasses block cache + decompression │                │
│  └──────────────────┬──────────────────────┘                │
│                     │ (miss)                                  │
│                     ▼                                         │
│  ┌─────────────────────────────────────────┐                │
│  │       Block Cache (LRU / Clock)          │                │
│  │  - Caches uncompressed data blocks      │                │
│  │  - Default: 8MB (TOO SMALL for prod)    │                │
│  │  - Recommended: 30-50% of RAM           │                │
│  │  - Shared across all SST files          │                │
│  │  - Also caches index + filter blocks    │                │
│  └──────────────────┬──────────────────────┘                │
│                     │ (miss)                                  │
│                     ▼                                         │
│  ┌─────────────────────────────────────────┐                │
│  │  Compressed Block Cache (optional)       │                │
│  │  - Caches compressed blocks from disk   │                │
│  │  - Avoids disk I/O, still needs decomp  │                │
│  │  - Use when data >> RAM                 │                │
│  └──────────────────┬──────────────────────┘                │
│                     │ (miss)                                  │
│                     ▼                                         │
│  ┌─────────────────────────────────────────┐                │
│  │  Table Cache (fd cache)                  │                │
│  │  - Caches open file descriptors         │                │
│  │  - Default: 1000 file descriptors       │                │
│  │  - Also caches SST metadata             │                │
│  └──────────────────┬──────────────────────┘                │
│                     │ (miss)                                  │
│                     ▼                                         │
│  ┌─────────────────────────────────────────┐                │
│  │  OS Page Cache                           │                │
│  │  - Kernel file system cache             │                │
│  │  - Can cause double-buffering           │                │
│  │  - Use Direct I/O to bypass             │                │
│  └─────────────────────────────────────────┘                │
│                                                               │
└─────────────────────────────────────────────────────────────┘

LRU Cache vs Clock Cache:
┌──────────────┬──────────────────┬─────────────────────┐
│ Feature      │ LRU Cache        │ Clock Cache          │
├──────────────┼──────────────────┼─────────────────────┤
│ Lock         │ Per-shard mutex  │ Lock-free (CAS)     │
│ Concurrency  │ Moderate         │ High                │
│ Overhead     │ Linked list      │ Circular buffer     │
│ CPU cores    │ Good for < 16    │ Better for 16+      │
│ Accuracy     │ True LRU         │ Approximate LRU     │
└──────────────┴──────────────────┴─────────────────────┘
```

### Iterator Optimization
```
ReadOptions for different patterns:

// Point lookup (single key)
ReadOptions opts;
opts.fill_cache = true;           // Cache the result
opts.verify_checksums = false;    // Skip for speed (prod)

// Range scan (many keys)
ReadOptions opts;
opts.fill_cache = false;          // Don't pollute cache
opts.readahead_size = 2 * 1024 * 1024;  // 2MB readahead
opts.async_io = true;             // Prefetch next blocks

// Prefix scan
ReadOptions opts;
opts.prefix_same_as_start = true; // Stop at prefix boundary
opts.auto_prefix_mode = true;     // Use prefix bloom

// Tailing iterator (for streaming new data)
ReadOptions opts;
opts.tailing = true;              // Follow new writes
```

---

## Write Performance & Tuning

### Write Optimizations
```
┌─────────────────────────────────────────────────────────────┐
│                  WRITE OPTIMIZATION TECHNIQUES                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Write Batching (Group Commit)                            │
│  ┌─────────────────────────────────────────────┐            │
│  │  Thread 1: Put(k1,v1) ──┐                   │            │
│  │  Thread 2: Put(k2,v2) ──┼── WriteBatch ──── │            │
│  │  Thread 3: Put(k3,v3) ──┘   (single WAL     │            │
│  │                              write + fsync)  │            │
│  └─────────────────────────────────────────────┘            │
│  - Leader thread writes batch for all waiting writers        │
│  - Reduces fsync calls from N to 1                           │
│  - enable_pipelined_write = true for better throughput       │
│                                                               │
│  2. Disable WAL (for non-critical data)                      │
│  WriteOptions opts;                                           │
│  opts.disableWAL = true;  // 3-5x faster writes             │
│  // Risk: lose unflushed data on crash                       │
│                                                               │
│  3. Bulk Loading (IngestExternalFile)                         │
│  ┌─────────────────────────────────────────────┐            │
│  │  External Process:                           │            │
│  │  1. Build SST file with SstFileWriter       │            │
│  │  2. Sort keys externally                     │            │
│  │  3. IngestExternalFile() → move to L0/Lmax  │            │
│  │                                              │            │
│  │  Benefits:                                   │            │
│  │  - Bypass MemTable + WAL entirely           │            │
│  │  - No write stalls                          │            │
│  │  - 500+ MB/s ingestion rate                 │            │
│  └─────────────────────────────────────────────┘            │
│                                                               │
│  4. Rate Limiter                                             │
│  - Limit compaction + flush I/O to prevent write stalls      │
│  - rate_limiter = NewGenericRateLimiter(100MB/s)            │
│  - Smooth out I/O spikes                                     │
│                                                               │
│  5. Unordered Writes                                         │
│  WriteOptions opts;                                           │
│  opts.unordered_write = true;  // Skip write ordering       │
│  // Safe only if no concurrent readers need consistency      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Write Stalls
```
Write stalls occur when background work can't keep up:

┌─────────────────────────────────────────────────────────────┐
│ Condition                            │ Action               │
├──────────────────────────────────────┼──────────────────────┤
│ L0 files >= slowdown_trigger (20)    │ Slow down writes     │
│ L0 files >= stop_trigger (36)        │ STOP all writes      │
│ Pending compaction bytes > soft      │ Slow down writes     │
│ Pending compaction bytes > hard      │ STOP all writes      │
│ MemTables >= max_write_buffer_number │ STOP all writes      │
└─────────────────────────────────────────────────────────────┘

Solutions:
1. Increase max_background_jobs (more compaction parallelism)
2. Increase write_buffer_size (fewer flushes)
3. Increase max_write_buffer_number (buffer more before stall)
4. Use rate limiter to smooth I/O
5. Increase level0_slowdown_writes_trigger
6. Use faster storage (NVMe)
```

---

## Memory Management

### Memory Budget Breakdown
```
┌─────────────────────────────────────────────────────────────┐
│              MEMORY USAGE (typical 32GB budget)              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Block Cache:          16 GB  (50%)                          │
│  ┌──────────────────────────────────────────────┐           │
│  │████████████████████████████████████████████  │           │
│  └──────────────────────────────────────────────┘           │
│                                                               │
│  MemTables:             4 GB  (12.5%)                        │
│  ┌────────────┐                                              │
│  │████████████│ = write_buffer_size × max_write_buffer ×    │
│  └────────────┘   num_column_families                        │
│                                                               │
│  Index + Filter:        8 GB  (25%)                          │
│  ┌──────────────────────────────────┐                       │
│  │██████████████████████████████████│                       │
│  └──────────────────────────────────┘                       │
│  (can pin in cache or keep in separate memory)              │
│                                                               │
│  Table Readers:         2 GB  (6.25%)                        │
│  ┌──────┐                                                    │
│  │██████│ (metadata per open SST file)                      │
│  └──────┘                                                    │
│                                                               │
│  Misc (iterators, etc): 2 GB  (6.25%)                       │
│  ┌──────┐                                                    │
│  │██████│                                                    │
│  └──────┘                                                    │
│                                                               │
│  Formula:                                                     │
│  Total ≈ block_cache_size                                    │
│        + write_buffer_size * max_write_buffer_number * CFs   │
│        + index_and_filter_size (per SST)                     │
│        + table_reader_overhead                               │
│                                                               │
└─────────────────────────────────────────────────────────────┘

WriteBufferManager:
- Global control over total MemTable memory across all CFs
- Prevents MemTable memory from growing unbounded
- Triggers flush when approaching limit
- write_buffer_manager = new WriteBufferManager(4GB, cache)
```

---

## Transactions & Concurrency Control

### Transaction Types
```
┌─────────────────────────────────────────────────────────────┐
│              PESSIMISTIC TRANSACTIONS                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  TransactionDB* txn_db;                                      │
│  Transaction* txn = txn_db->BeginTransaction(write_opts);    │
│                                                               │
│  txn->Put("key1", "val1");   // Acquires lock on key1       │
│  txn->Get(read_opts, "key2", &val);  // Read (snapshot)     │
│  txn->Put("key2", "new_val");  // Lock on key2              │
│  txn->Commit();  // Release all locks, write atomically     │
│                                                               │
│  Lock granularity: per-key (hash-based lock table)           │
│  Deadlock detection: wait-die or wound-wait                  │
│  Lock timeout: configurable (default 1 second)               │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│              OPTIMISTIC TRANSACTIONS                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  OptimisticTransactionDB* otxn_db;                           │
│  Transaction* txn = otxn_db->BeginTransaction(write_opts);   │
│                                                               │
│  txn->Put("key1", "val1");   // No lock acquired            │
│  txn->Get(read_opts, "key2", &val);                         │
│  txn->Commit();  // Validate: check if keys were modified   │
│                  // If conflict → Status::Busy()             │
│                                                               │
│  Better for: low-contention workloads                        │
│  No lock overhead, no deadlocks                              │
│  Retry on conflict                                           │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│              TWO-PHASE COMMIT (2PC)                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  // Used by distributed systems (TiKV, CockroachDB)         │
│  txn->SetName("txn_001");                                    │
│  txn->Put("key1", "val1");                                   │
│  txn->Prepare();   // Write to WAL, don't commit yet        │
│  // ... coordinate with other nodes ...                      │
│  txn->Commit();    // or txn->Rollback();                    │
│                                                               │
│  Survives crash between Prepare and Commit                   │
│  Recovery replays prepared transactions from WAL             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Merge Operator
```
Problem: Read-Modify-Write is expensive (Get + Put = 2 operations)

Solution: Merge operator defers computation

// Without merge: 3 operations for counter increment
val = db->Get("counter");
val = val + 1;
db->Put("counter", val);

// With merge: 1 operation (deferred computation)
db->Merge("counter", "1");  // Just log the delta

// Actual computation happens during:
// 1. Get() → applies all pending merges
// 2. Compaction → consolidates merge operands

┌─────────────────────────────────────────────────────────────┐
│  MemTable: Merge("counter", "+1")                           │
│  L0:       Merge("counter", "+5")                           │
│  L1:       Put("counter", "100")                            │
│                                                               │
│  Get("counter") → applies: 100 + 5 + 1 = 106               │
│  After compaction: Put("counter", "106")                    │
└─────────────────────────────────────────────────────────────┘

Use cases:
- Counters (atomic increment without read)
- Append to list/string
- Partial JSON updates
- HyperLogLog merge
```

---

## Production Configuration & Tuning

### Hardware Recommendations
```
┌─────────────────────────────────────────────────────────────┐
│ Component    │ Minimum        │ Recommended      │ Optimal   │
├──────────────┼────────────────┼──────────────────┼───────────┤
│ Storage      │ SATA SSD       │ NVMe SSD         │ NVMe RAID │
│ RAM          │ 8 GB           │ 32-64 GB         │ 128+ GB   │
│ CPU          │ 4 cores        │ 16 cores         │ 32+ cores │
│ Filesystem   │ ext4           │ XFS              │ XFS       │
│ OS           │ Linux 4.x      │ Linux 5.x+       │ 5.15+     │
└─────────────────────────────────────────────────────────────┘
```

### Workload-Specific Tuning
```
═══════════════════════════════════════════════════════════════
WRITE-HEAVY WORKLOAD (streaming, logging, 90% writes)
═══════════════════════════════════════════════════════════════
write_buffer_size = 256MB              // Larger MemTable
max_write_buffer_number = 6            // More buffers before stall
min_write_buffer_number_to_merge = 2   // Merge before flush
level0_file_num_compaction_trigger = 8 // Delay L0 compaction
max_background_jobs = 8                // More compaction threads
compaction_style = kUniversalCompaction // Lower write amp
compression_type = kLZ4Compression     // Fast compression
disable_auto_compactions = false       // Keep compaction running
rate_limiter = 200MB/s                 // Limit compaction I/O

═══════════════════════════════════════════════════════════════
READ-HEAVY WORKLOAD (serving, point lookups, 90% reads)
═══════════════════════════════════════════════════════════════
block_cache_size = 70% of RAM          // Large cache
bloom_bits_per_key = 10                // Low false positive
optimize_filters_for_hits = true       // Don't build last-level filter
pin_l0_filter_and_index_blocks = true  // Keep hot data in memory
cache_index_and_filter_blocks = true   // Cache metadata
compression_type = kZSTD               // Best ratio (less I/O)
compaction_style = kLevelCompaction    // Best read perf
max_open_files = -1                    // Keep all fds open

═══════════════════════════════════════════════════════════════
SPACE-CONSTRAINED (limited SSD)
═══════════════════════════════════════════════════════════════
compression_type = kZSTD               // Best compression
bottommost_compression = kZSTD         // Extra compress bottom
compaction_style = kLevelCompaction    // Low space amp (1.1x)
target_file_size_base = 64MB           // Standard file size
enable_blob_files = true               // Separate large values
min_blob_size = 1024                   // Values > 1KB to blob
blob_compression_type = kZSTD          // Compress blobs too

═══════════════════════════════════════════════════════════════
BALANCED (general purpose)
═══════════════════════════════════════════════════════════════
write_buffer_size = 64MB
max_write_buffer_number = 3
block_cache_size = 50% of RAM
bloom_bits_per_key = 10
max_background_jobs = 4
level0_file_num_compaction_trigger = 4
target_file_size_base = 64MB
max_bytes_for_level_base = 256MB
compression_per_level = [kLZ4, kLZ4, kZSTD, kZSTD, kZSTD, kZSTD, kZSTD]
```

### Key Monitoring Metrics
```
// Statistics (enable with options.statistics = CreateDBStatistics())
rocksdb.block.cache.hit           // Cache hit count
rocksdb.block.cache.miss          // Cache miss count
rocksdb.bloom.filter.useful       // Bloom filter saved reads
rocksdb.compaction.times.micros   // Time spent in compaction
rocksdb.stall.micros              // Write stall duration
rocksdb.num.keys.written          // Keys written
rocksdb.num.keys.read             // Keys read
rocksdb.bytes.written             // Total bytes written
rocksdb.bytes.read                // Total bytes read

// PerfContext (per-thread operation breakdown)
perf_context.block_read_time      // Time reading blocks from disk
perf_context.block_cache_hit_count
perf_context.bloom_filter_useful
perf_context.get_from_memtable_time

// IOStatsContext
iostats_context.bytes_read
iostats_context.bytes_written
```

---

## Use Case Architectures

### As Storage Engine for Distributed Databases (TiKV)
```
┌─────────────────────────────────────────────────────────────┐
│                        TiDB Cluster                          │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │   TiDB   │  │   TiDB   │  │   TiDB   │  (SQL Layer)    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │              │              │                         │
│       └──────────────┼──────────────┘                        │
│                      │                                        │
│  ┌───────────────────┼───────────────────────────────┐      │
│  │                  TiKV Cluster                      │      │
│  │                                                    │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │      │
│  │  │  TiKV Node │  │  TiKV Node │  │  TiKV Node │  │      │
│  │  │            │  │            │  │            │  │      │
│  │  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │  │      │
│  │  │ │RocksDB │ │  │ │RocksDB │ │  │ │RocksDB │ │  │      │
│  │  │ │ (Raft  │ │  │ │ (Raft  │ │  │ │ (Raft  │ │  │      │
│  │  │ │  Log)  │ │  │ │  Log)  │ │  │ │  Log)  │ │  │      │
│  │  │ ├────────┤ │  │ ├────────┤ │  │ ├────────┤ │  │      │
│  │  │ │RocksDB │ │  │ │RocksDB │ │  │ │RocksDB │ │  │      │
│  │  │ │ (KV    │ │  │ │ (KV    │ │  │ │ (KV    │ │  │      │
│  │  │ │  Data) │ │  │ │  Data) │ │  │ │  Data) │ │  │      │
│  │  │ └────────┘ │  │ └────────┘ │  │ └────────┘ │  │      │
│  │  └────────────┘  └────────────┘  └────────────┘  │      │
│  │                                                    │      │
│  │  Each TiKV node has 2 RocksDB instances:          │      │
│  │  1. Raft log store (WAL for consensus)            │      │
│  │  2. KV data store (actual user data)              │      │
│  └───────────────────────────────────────────────────┘      │
│                                                               │
│  ┌─────────────┐                                             │
│  │     PD      │  (Placement Driver - cluster metadata)     │
│  └─────────────┘                                             │
└─────────────────────────────────────────────────────────────┘
```

### As MySQL Storage Engine (MyRocks at Facebook)
```
┌─────────────────────────────────────────────────────────────┐
│                    Facebook MySQL (MyRocks)                   │
│                                                               │
│  ┌───────────────────────────────────────────────────┐      │
│  │                MySQL Server Layer                   │      │
│  │  (Parser, Optimizer, Handler API)                  │      │
│  └───────────────────────┬───────────────────────────┘      │
│                          │                                    │
│  ┌───────────────────────┼───────────────────────────┐      │
│  │              Storage Engine Layer                   │      │
│  │                                                    │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │      │
│  │  │  InnoDB  │  │  MyRocks  │  │  Other   │       │      │
│  │  │(B-tree)  │  │ (RocksDB) │  │          │       │      │
│  │  └──────────┘  └─────┬────┘  └──────────┘       │      │
│  └───────────────────────┼───────────────────────────┘      │
│                          │                                    │
│  ┌───────────────────────┼───────────────────────────┐      │
│  │              RocksDB Library                        │      │
│  │                                                    │      │
│  │  Primary Key Index: key = PK, value = full row    │      │
│  │  Secondary Index: key = SK+PK, value = empty      │      │
│  │                                                    │      │
│  │  Benefits over InnoDB:                             │      │
│  │  - 2x better compression (50% storage savings)   │      │
│  │  - Lower write amplification for write workloads  │      │
│  │  - Better SSD endurance                           │      │
│  │                                                    │      │
│  │  Facebook results:                                 │      │
│  │  - 50% less storage for UDB (social graph)       │      │
│  │  - 10x lower write amplification vs InnoDB       │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### As Streaming State Store (Kafka Streams / Flink)
```
┌─────────────────────────────────────────────────────────────┐
│              Kafka Streams Application                        │
│                                                               │
│  ┌───────────────────────────────────────────────────┐      │
│  │              Stream Processing Topology             │      │
│  │                                                    │      │
│  │  Source Topic → Processor → Processor → Sink Topic │      │
│  │                     │                              │      │
│  │                     ▼                              │      │
│  │              ┌──────────────┐                     │      │
│  │              │  State Store  │                     │      │
│  │              │  (RocksDB)    │                     │      │
│  │              │              │                     │      │
│  │              │  - Windowed  │                     │      │
│  │              │    aggregates│                     │      │
│  │              │  - KV lookup │                     │      │
│  │              │  - Joins     │                     │      │
│  │              └──────┬───────┘                     │      │
│  │                     │                              │      │
│  │                     ▼                              │      │
│  │              ┌──────────────┐                     │      │
│  │              │  Changelog   │ (backup to Kafka   │      │
│  │              │  Topic       │  for fault-tolerance)│      │
│  │              └──────────────┘                     │      │
│  └───────────────────────────────────────────────────┘      │
│                                                               │
│  Each partition → own RocksDB instance (local disk)         │
│  Scales horizontally by adding partitions                    │
│  State restored from changelog on failover                   │
│                                                               │
│  RocksDB config for streaming:                               │
│  - Small write_buffer_size (16MB per partition)             │
│  - Aggressive compaction (low latency)                       │
│  - Bloom filters for windowed lookups                       │
│  - TTL compaction filter for window expiry                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Backup, Restore & Operations

### Backup Strategies
```
┌─────────────────────────────────────────────────────────────┐
│                    BACKUP OPTIONS                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Checkpoint (fastest, local copy)                         │
│  ┌─────────────────────────────────────────────┐            │
│  │  Checkpoint* cp;                             │            │
│  │  db->NewCheckpoint(&cp);                     │            │
│  │  cp->CreateCheckpoint("/backup/path");       │            │
│  │                                              │            │
│  │  - Creates hard-links to SST files (instant) │            │
│  │  - Copies WAL and MANIFEST                   │            │
│  │  - Consistent point-in-time snapshot         │            │
│  │  - Zero impact on writes                     │            │
│  └─────────────────────────────────────────────┘            │
│                                                               │
│  2. BackupEngine (full + incremental)                        │
│  ┌─────────────────────────────────────────────┐            │
│  │  BackupEngine* engine;                       │            │
│  │  BackupEngine::Open(env, options, &engine);  │            │
│  │  engine->CreateNewBackup(db);                │            │
│  │                                              │            │
│  │  - Copies files to backup directory          │            │
│  │  - Incremental: only new SST files           │            │
│  │  - Verifies backup checksum                  │            │
│  │  - Supports remote storage (S3, etc.)       │            │
│  └─────────────────────────────────────────────┘            │
│                                                               │
│  3. Live Replication (for distributed systems)               │
│  - Replicate WAL entries to followers                       │
│  - Used by TiKV (Raft) and CockroachDB                    │
│  - Application-level replication, not built into RocksDB   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: Explain write amplification in RocksDB and how to minimize it.
```
Write amplification (WA) = total bytes written to disk / bytes written by app

Sources of WA:
1. WAL write (1x) - every write goes to WAL
2. MemTable flush (1x) - flush to L0
3. Compaction (dominant factor):
   - Level compaction: each level rewrite = 10x multiplier
   - Through all levels: WA = 10 + 10 + 10... = 10 * (num_levels - 1)
   - Practical: 10-30x for level compaction

Minimization strategies:
1. Use Universal Compaction (WA ≈ 2-5x vs 10-30x)
2. Increase write_buffer_size (fewer flushes)
3. Increase level size ratio (fewer levels, but more space amp)
4. Use leveled_compaction_dynamic_level_bytes = true
5. Increase target_file_size_base (fewer files to compact)
6. Key-value separation (BlobDB): large values bypass compaction

Facebook measured: MyRocks = 10-15x WA vs InnoDB = 30-40x WA
```

### Q2: When would you choose RocksDB over a B-tree engine?
```
Choose RocksDB (LSM-tree) when:
- Write-heavy workload (> 50% writes)
- Sequential write patterns (time-series, logs, events)
- Space efficiency is critical (better compression)
- SSD endurance matters (less write amplification vs random B-tree writes)
- Large datasets with good compression ratios
- Bulk loading is frequent

Choose B-tree (InnoDB, PostgreSQL) when:
- Read-heavy workload (> 80% reads)
- Frequent point updates to existing keys
- Need strong transactional guarantees (full ACID)
- Range scans are dominant operation
- Predictable latency is critical (no compaction spikes)
- Data fits in memory (B-tree cache is simpler)

Hybrid approach (what Facebook does):
- MyRocks for write-heavy tables (social graph, messages)
- InnoDB for read-heavy tables (user profiles, auth)
```

### Q3: How does RocksDB handle read performance despite being write-optimized?
```
LSM penalty: reads must check multiple levels
RocksDB mitigations:

1. Bloom filters: Eliminate 99% of unnecessary SST reads
   - 10 bits/key = 1% false positive rate
   - For N levels with bloom: expected reads ≈ 1 + 0.01*N

2. Block cache: 90-99% hit rate for working set
   - LRU eviction
   - Pin L0 and L1 blocks in cache

3. Compaction: Reduces sorted runs over time
   - Level compaction: max 1 file per level to check
   - Without compaction: O(N) files to check

4. Prefix bloom: Fast prefix range scans
   - Skip entire SST files that don't contain prefix

5. Partitioned index/filters: Only load relevant partitions
   - Critical for datasets >> RAM

6. Direct I/O: Bypass OS page cache for predictable latency

7. Iterator optimization: Async I/O, prefetch, heap merge

Result: Point lookup in 50-200 μs on NVMe with proper tuning
```

### Q4: Explain Column Families and their production use cases.
```
Column Families = separate MemTables + SST files, shared WAL

TiKV uses 3 Column Families:
1. "default" - actual key-value data
2. "write" - MVCC write records (commit timestamps)
3. "lock" - transaction lock information

Benefits:
- Different compaction settings per CF
- "lock" CF: small, aggressive compaction (frequent writes/deletes)
- "default" CF: large, standard level compaction
- Independent flush (only flush the CF that's full)
- Atomic writes across CFs (shared WAL)

Trade-offs:
- Shared WAL means one slow CF blocks WAL deletion for all
- More memory (each CF has own MemTable budget)
- More compaction threads needed
- Recovery time increases (more WAL to replay)
```

### Q5: How would you debug a sudden latency spike in production?
```
Debugging checklist:

1. Check write stalls:
   - rocksdb.stall.micros increasing?
   - L0 file count > slowdown_trigger?
   - Pending compaction bytes > threshold?
   → Solution: tune compaction speed, add background threads

2. Check compaction:
   - Large compaction running? (rocksdb.compaction.times.micros)
   - I/O bandwidth saturated?
   → Solution: rate limiter, sub-compaction

3. Check block cache:
   - Hit rate dropped? (cache.hit / (cache.hit + cache.miss))
   - Working set changed? (new access pattern)
   → Solution: increase cache size, check for scan pollution

4. Check memory:
   - RSS growing? MemTable memory unbounded?
   - Swap usage?
   → Solution: WriteBufferManager, monitor RSS

5. Check OS:
   - iostat: I/O latency spikes?
   - vmstat: swap activity?
   - dmesg: disk errors?
   → Solution: faster storage, more RAM

6. Check bloom filter effectiveness:
   - rocksdb.bloom.filter.useful low?
   - Doing many negative lookups without bloom?
   → Solution: verify bloom filter is enabled, check bits_per_key
```

### Q6: How would you size RocksDB for 10TB of data?
```
Capacity Planning:

Data: 10 TB (after compression, assuming 3x ratio = ~3.3 TB on disk)

Storage:
- Data: 3.3 TB
- Space amplification (level compaction): 1.1x → 3.6 TB
- Temporary compaction space: +10-20% → 4.3 TB
- Recommendation: 6 TB NVMe (50% headroom)

RAM (32-64 GB minimum):
- Block cache: 30-40 GB (covers ~1% of data, hot working set)
- MemTables: 4 GB (4 CFs × 256MB × 4 buffers)
- Index/Filter blocks: 8-16 GB
  - ~50 bytes index per 64KB data block
  - 10 bits per key for bloom (10TB / avg_value_size keys)
- Total: 64-128 GB recommended

CPU:
- 16-32 cores
- Compaction uses 4-8 threads
- Compression (ZSTD) uses significant CPU
- Read serving uses remaining cores

Configuration:
- max_background_jobs = 8
- max_subcompactions = 4
- write_buffer_size = 256MB
- max_bytes_for_level_base = 1GB
- target_file_size_base = 128MB
- num_levels = 7 (enough for 10TB)
```

---

## Scenario-Based Questions

### Scenario 1: Design a time-series store using RocksDB
```
Requirements: Store 1M metrics, 10-second intervals, 30-day retention

Key Design:
- Key: [metric_id (4B)][timestamp (8B, big-endian descending)]
- Value: [float64 value (8B)][optional tags]

Why descending timestamp: Recent data accessed first,
  iterator starts at newest data without seeking to end.

Column Families:
- "current_day": uncompressed, fast access
- "historical": ZSTD compressed, less frequent access

Compaction: FIFO for TTL-based deletion (simple, low WA)
  - max_table_files_size = 30 days of data
  - Oldest files automatically deleted

Compression strategy:
- Current day: LZ4 (fast decompression for real-time queries)
- Historical: ZSTD (maximize compression for archival)

Ingestion optimization:
- WriteBatch: group 1000 samples per batch
- Disable WAL (acceptable: time-series can re-scrape)
- Large MemTable (256MB) to reduce flushes

Query optimization:
- Prefix bloom on metric_id (fast single-metric queries)
- ReadOptions.iterate_upper_bound for time range scans
- Pin L0 filters in memory for recent data

Expected performance:
- Write: 1M samples/sec (batched, no WAL)
- Read: 100K point queries/sec
- Storage: ~500 GB for 30 days (with ZSTD)
```

### Scenario 2: Optimize RocksDB for a write-heavy streaming workload
```
Context: Kafka Streams state store, 500K writes/sec, 50K reads/sec

Problems to solve:
1. Write stalls from compaction not keeping up
2. High tail latency (p99 > 100ms)
3. SSD wearing out from write amplification

Solution:

Step 1: Reduce write amplification
  compaction_style = kUniversalCompaction  // WA: 2-5x vs 10-30x
  // OR use dynamic level with higher multiplier:
  level_compaction_dynamic_level_bytes = true
  max_bytes_for_level_multiplier = 8

Step 2: Smooth out write stalls
  max_write_buffer_number = 6         // Buffer before stall
  write_buffer_size = 128MB           // Larger MemTable
  level0_file_num_compaction_trigger = 8
  level0_slowdown_writes_trigger = 20
  level0_stop_writes_trigger = 36
  max_background_jobs = 8             // More compaction threads
  rate_limiter = NewGenericRateLimiter(300 * 1024 * 1024)  // 300MB/s

Step 3: Optimize for streaming pattern
  // Keys are mostly sequential (time-ordered)
  allow_concurrent_memtable_write = true
  enable_pipelined_write = true
  
  // Disable WAL if Kafka changelog provides durability
  WriteOptions write_opts;
  write_opts.disableWAL = true;       // 3-5x faster
  
Step 4: Memory management
  write_buffer_manager = new WriteBufferManager(2GB)  // Cap MemTable RAM
  block_cache = NewLRUCache(8GB)      // Modest cache (read-light)

Step 5: Monitor and iterate
  - Track: stall.micros, compaction.bytes_written, WA ratio
  - Alert on: L0 files > 12, pending_compaction > 50GB
```

### Scenario 3: Debug sudden latency spike in RocksDB-backed service
```
Symptom: p99 latency jumped from 5ms to 500ms

Investigation steps:

1. Check write stalls:
   $ grep "Stalling" LOG
   > "Stalling writes because L0 files (24) >= slowdown trigger (20)"
   
   ROOT CAUSE: L0 files accumulated → write stalls

2. Why did L0 accumulate?
   $ check compaction stats
   > Compaction I/O saturated at 100MB/s (disk bandwidth limit)
   > Large L0→L1 compaction blocked by ongoing L1→L2

3. Why is compaction slow?
   $ iostat -x 1
   > %util = 99%, r_await = 50ms (disk is saturated)
   > Found: backup process running on same disk

4. Fix:
   Immediate: Kill backup process, CompactRange() to clear L0
   Short-term: 
   - Move backups to off-peak hours
   - rate_limiter for compaction (leave I/O for reads)
   - Increase max_background_compactions from 2 to 4
   Long-term:
   - Separate backup to different disk
   - Add NVMe for hot data
   - Set level0_slowdown_writes_trigger = 30 (more buffer)
   - Sub-compaction for faster L0→L1 (max_subcompactions = 4)

5. Prevention:
   - Alert on L0 file count > 12
   - Alert on pending_compaction_bytes > 10GB
   - Dashboard: write stall duration, compaction pending bytes
   - Rate limit external I/O (backups, bulk reads)
```

### Scenario 4: Design multi-tenant RocksDB instance
```
Requirement: 100 tenants sharing one RocksDB, isolation needed

Approach 1: Column Families per tenant
  Pros: Separate compaction, flush, compression settings
  Cons: Max ~100 CFs practical, shared WAL bottleneck
  
  Implementation:
  - One CF per tenant
  - WriteBufferManager with per-CF limits
  - Rate limiter per CF for compaction
  - Independent compression levels

Approach 2: Key-prefix per tenant
  Key format: [tenant_id (4B)][user_key]
  Pros: Simple, scales to 1000s of tenants
  Cons: No isolation (one tenant's compaction affects all)
  
  Implementation:
  - Prefix bloom for tenant-scoped reads
  - Compaction filter for per-tenant TTL
  - Prefix extractor: first 4 bytes

Approach 3: Separate DB instances per tenant
  Pros: Complete isolation, easy to move/backup per tenant
  Cons: More memory overhead, more file descriptors
  
  Recommendation for 100 tenants:
  - Column Families approach
  - Group small tenants into shared CF
  - Large tenants get dedicated CF
  - WriteBufferManager caps total memory
  - Monitor per-CF compaction stats
```

### Scenario 5: Migrating from InnoDB to MyRocks
```
Context: 20TB MySQL database, 70% writes, SSD wearing out

Migration plan:

Phase 1: Shadow writes
- Set up MyRocks as secondary engine
- Dual-write to both InnoDB and MyRocks tables
- Compare read results for correctness

Phase 2: Benchmarking
- Expected improvements:
  - Storage: 20TB → 8TB (2.5x compression)
  - Write amplification: 40x → 12x
  - SSD endurance: 3x longer lifespan
  - Write throughput: 20% improvement
  
- Expected trade-offs:
  - Point read latency: +10-20% (LSM vs B-tree)
  - Range scan: comparable (good compaction)
  - CPU usage: +15% (compression overhead)

Phase 3: Schema considerations
- Primary key must be defined (RocksDB needs sorted key)
- Remove redundant indexes (each index = separate CF)
- Reverse key order for time-series tables (recent first)

Phase 4: Configuration
- rocksdb_max_background_jobs = 8
- rocksdb_block_cache_size = 64GB (50% of RAM)
- rocksdb_default_cf_options = "compression=kZSTD;
    write_buffer_size=256m;max_write_buffer_number=4"

Phase 5: Cutover
- mysqldump → MyRocks table
- Verify row counts and checksums
- Switch traffic with quick failback plan
- Monitor: query latency, CPU, disk I/O, space usage
```
