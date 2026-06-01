# Log-Structured Merge Trees (LSM Trees)

## 1. Problem Statement

B-Trees are the default indexing structure in most traditional databases. They maintain sorted data in a tree of fixed-size pages (typically 4KB-16KB). However, B-Trees suffer from a fundamental problem for write-heavy workloads:

**Random Write Amplification in B-Trees:**
- Updating a single key requires reading the page, modifying it, and writing the entire page back
- Pages are scattered across disk → random I/O
- A single logical write can trigger page splits cascading up the tree
- Write amplification factor: typically 10-30x for B-Trees on SSDs

```
B-Tree Write (Random I/O):

    Disk Seeks Required:
    ┌─────────┐
    │  Root   │ ← Read page (random seek #1)
    └────┬────┘
         │
    ┌────▼────┐
    │Internal │ ← Read page (random seek #2)
    └────┬────┘
         │
    ┌────▼────┐
    │  Leaf   │ ← Read page (random seek #3)
    └────┬────┘   Write page back (random seek #4)
         │        Possibly split → write parent (random seek #5)
```

**The LSM Insight:** Convert random writes into sequential writes by buffering mutations in memory and periodically flushing them as sorted, immutable files. Sequential I/O is 100-1000x faster than random I/O on both HDDs and SSDs.

```
Throughput Comparison (approximate):

    Random 4KB Writes:    ~1,000 - 10,000 IOPS  (HDD/SSD)
    Sequential Writes:    ~100 - 500 MB/s        (HDD)
                          ~1,000 - 5,000 MB/s    (SSD NVMe)

    LSM sequential write throughput >> B-Tree random write throughput
```

---

## 2. Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LSM-Tree Architecture                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MEMORY                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                      │   │
│   │   ┌───────────────┐         ┌───────────────────┐                   │   │
│   │   │     WAL       │         │    MemTable       │                   │   │
│   │   │ (Write-Ahead  │ ──────► │  (Active, Mutable)│                   │   │
│   │   │    Log)       │         │  Skip List / RBT  │                   │   │
│   │   │  Sequential   │         │  ~64MB - 256MB    │                   │   │
│   │   │  Append-Only  │         └────────┬──────────┘                   │   │
│   │   └───────────────┘                  │                              │   │
│   │                                      │ (when full)                  │   │
│   │                            ┌─────────▼──────────┐                   │   │
│   │                            │  Immutable MemTable │                   │   │
│   │                            │  (Being flushed)    │                   │   │
│   │                            └─────────┬──────────┘                   │   │
│   │                                      │                              │   │
│   └──────────────────────────────────────┼──────────────────────────────┘   │
│                                          │ FLUSH                             │
│   DISK                                   ▼                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                      │   │
│   │   Level 0 (L0):  SSTables may OVERLAP in key range                  │   │
│   │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │   │
│   │   │SST-1 │ │SST-2 │ │SST-3 │ │SST-4 │   (max ~4 files)            │   │
│   │   │[a-z] │ │[d-p] │ │[b-m] │ │[f-w] │                              │   │
│   │   └──────┘ └──────┘ └──────┘ └──────┘                              │   │
│   │        │         │         │        │                                │   │
│   │        └─────────┴─────────┴────────┘                               │   │
│   │                      │ COMPACTION                                    │   │
│   │                      ▼                                               │   │
│   │   Level 1 (L1):  Non-overlapping, ~10MB total                       │   │
│   │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                    │   │
│   │   │[a-d] │ │[e-h] │ │[i-m] │ │[n-r] │ │[s-z] │                    │   │
│   │   └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                    │   │
│   │                      │ COMPACTION                                    │   │
│   │                      ▼                                               │   │
│   │   Level 2 (L2):  Non-overlapping, ~100MB total                      │   │
│   │   ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐   │   │
│   │   │a-b ││c-d ││e-f ││g-h ││i-k ││l-n ││o-q ││r-t ││u-w ││x-z │   │   │
│   │   └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘   │   │
│   │                      │ COMPACTION                                    │   │
│   │                      ▼                                               │   │
│   │   Level 3 (L3):  Non-overlapping, ~1GB total                        │   │
│   │   ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐...┌──┐           │   │
│   │   │  ││  ││  ││  ││  ││  ││  ││  ││  ││  ││  │   │  │           │   │
│   │   └──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘   └──┘           │   │
│   │                      │                                               │   │
│   │                      ▼                                               │   │
│   │   Level N (LN):  Non-overlapping, 10^N MB total                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 MemTable (Memory Component)

The MemTable is a sorted in-memory data structure that buffers all incoming writes.

**Common Implementations:**
- **Skip List** (used by LevelDB, RocksDB): O(log n) insert/lookup, lock-free concurrent variants, cache-friendly
- **Red-Black Tree**: O(log n) guaranteed, but pointer-heavy
- **B-Tree in memory** (WiredTiger): better cache locality

```
Skip List MemTable:

Level 4:  HEAD ──────────────────────────────────────────► NIL
Level 3:  HEAD ───────────► 15 ──────────────────► 55 ──► NIL
Level 2:  HEAD ───► 7 ───► 15 ───► 28 ──────────► 55 ──► NIL
Level 1:  HEAD ─► 3 ► 7 ► 15 ► 22 ► 28 ► 34 ► 42 ► 55 ► NIL

    Insert "key=30": Start at top-left, move right until overshoot,
    drop down one level, repeat. O(log n) expected.
```

**Typical MemTable size:** 64MB - 256MB (configurable via `write_buffer_size` in RocksDB).

### 2.2 Write-Ahead Log (WAL)

Before any write enters the MemTable, it is first appended to the WAL—a sequential, append-only file on disk. This ensures durability: if the process crashes, the MemTable can be reconstructed from the WAL.

```
WAL File (Sequential Append):
┌────────────────────────────────────────────────────────────┐
│ [SeqNo:1][PUT key1=val1] [SeqNo:2][DEL key2]              │
│ [SeqNo:3][PUT key3=val3] [SeqNo:4][PUT key1=val4]         │
│ [SeqNo:5][MERGE key5 += delta] ...                         │
└────────────────────────────────────────────────────────────┘
         ▲
         │ Always append here (sequential I/O only)
```

**WAL lifecycle:**
1. Created when a new MemTable is allocated
2. Receives all writes synchronously (fsync per write or per batch)
3. Deleted after its corresponding MemTable is successfully flushed to SSTable

### 2.3 Immutable MemTable → Flush

When the active MemTable reaches its size threshold:
1. It becomes **immutable** (no more writes accepted)
2. A new MemTable + WAL is created for incoming writes
3. A background thread flushes the immutable MemTable to disk as a sorted SSTable at Level 0

### 2.4 SSTables (Sorted String Tables)

SSTables are the on-disk format: immutable, sorted files containing key-value pairs.

```
SSTable File Format:
┌─────────────────────────────────────────────────────────────────┐
│                         SSTable File                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Data Block 0  (4KB - 64KB, sorted key-value pairs)       │    │
│  │ [key1:val1] [key2:val2] [key3:val3] ... [keyN:valN]      │    │
│  │ (prefix-compressed keys, restart points every 16 keys)    │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Data Block 1                                              │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Data Block 2                                              │    │
│  └──────────────────────────────────────────────────────────┘    │
│         ...                                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Data Block N                                              │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Meta Block: Bloom Filter (per SSTable or per block)       │    │
│  │ Bit array: [0110100101001011010011...]                     │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Index Block: [last_key_of_block → offset, size]           │    │
│  │ Block0: "apple"  → offset 0,    size 4096                │    │
│  │ Block1: "mango"  → offset 4096, size 4096                │    │
│  │ Block2: "zebra"  → offset 8192, size 4096                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Footer: magic number, index block handle, meta block      │    │
│  │         handle, format version                            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Write Path

```
Write Path:

  Client Write (PUT key=value)
       │
       ▼
  ┌─────────────────────┐
  │ 1. Append to WAL    │  ◄── Sequential disk write (fsync)
  │    (durability)     │      Latency: ~10-100μs (SSD)
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ 2. Insert into      │  ◄── In-memory operation
  │    MemTable         │      Latency: ~1-5μs
  │    (sorted insert)  │
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ 3. Return ACK to    │  ◄── Write is durable and visible
  │    client           │
  └──────────┬──────────┘
             │
             │  (Asynchronous, when MemTable full)
             ▼
  ┌─────────────────────┐
  │ 4. Freeze MemTable  │  ◄── Mark as immutable
  │    (make immutable) │      Allocate new MemTable + WAL
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ 5. Background Flush │  ◄── Sequential write of sorted data
  │    → Level 0 SSTable│      Throughput: hundreds of MB/s
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ 6. Delete old WAL   │  ◄── No longer needed for recovery
  └─────────────────────┘
```

**Key Properties:**
- **Latency to client:** Only steps 1-3 (WAL append + memory insert) → typically < 100μs
- **All disk writes are sequential:** WAL is append-only, flush writes sorted data in one pass
- **Batch optimization:** Multiple writes can share one fsync (group commit)

**Write Batching (RocksDB WriteBatch):**
```
Multiple concurrent writers:
  Writer 1 ─┐
  Writer 2 ─┼──► Group into single WAL write (one fsync)
  Writer 3 ─┘    Then each inserts into MemTable
```

---

## 4. Read Path

```
Read Path (Point Lookup for key K):

  Client Read (GET key=K)
       │
       ▼
  ┌──────────────────────────────────────────────────────┐
  │ 1. Check Active MemTable                             │
  │    O(log n) lookup in skip list                      │
  │    Found? → Return value                             │
  └──────────────────────┬───────────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │ 2. Check Immutable MemTable(s)                       │
  │    (being flushed, still in memory)                  │
  │    Found? → Return value                             │
  └──────────────────────┬───────────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │ 3. Check Level 0 SSTables (ALL of them, newest first)│
  │    ┌─────────────────────────────────────────────┐   │
  │    │ For each L0 SSTable (may overlap):          │   │
  │    │   a) Check Bloom filter → skip if negative  │   │
  │    │   b) Binary search index block              │   │
  │    │   c) Read data block, search for key        │   │
  │    └─────────────────────────────────────────────┘   │
  │    Found? → Return value (newest version wins)       │
  └──────────────────────┬───────────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │ 4. Check Level 1 SSTables                            │
  │    ┌─────────────────────────────────────────────┐   │
  │    │ Non-overlapping → binary search to find the │   │
  │    │ ONE SSTable whose range contains K          │   │
  │    │   a) Check Bloom filter                     │   │
  │    │   b) Binary search index block              │   │
  │    │   c) Read data block                        │   │
  │    └─────────────────────────────────────────────┘   │
  │    Found? → Return value                             │
  └──────────────────────┬───────────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │ 5. Check Level 2 ... Level N (same as Level 1)       │
  │    One SSTable per level max (non-overlapping)       │
  └──────────────────────┬───────────────────────────────┘
                         │ NOT FOUND at any level
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │ 6. Return NOT FOUND                                  │
  └──────────────────────────────────────────────────────┘
```

**Read Amplification (Worst Case):**
- MemTable: 1 lookup
- L0: up to 4 SSTables (each needs bloom + index + data block read)
- L1-L6: 1 SSTable per level (with bloom filter check)
- **Worst case without bloom filters:** ~15-20 disk reads
- **With bloom filters (1% FPR):** ~1-2 disk reads on average

**Bloom Filters:**
```
Bloom Filter Check:

  Key "user:12345"
       │
       ├── Hash1(key) → bit position 47  → bit[47] = 1? ✓
       ├── Hash2(key) → bit position 183 → bit[183] = 1? ✓
       ├── Hash3(key) → bit position 912 → bit[912] = 0? ✗
       │
       ▼
  DEFINITELY NOT IN THIS SSTABLE (skip it!)

  If all bits = 1 → MAYBE in this SSTable (proceed with lookup)
  False positive rate: ~1% with 10 bits per key
```

**Block Cache:**
```
Block Cache (LRU, typically GB-sized):
┌───────────────────────────────────────────────────┐
│  Recently accessed data blocks and index blocks   │
│  Hit ratio target: > 95% for hot data            │
│                                                   │
│  [L2/SST5/Block3] [L1/SST2/Block0] [L3/SST1/B7] │
│  [Index/L2/SST5]  [Index/L1/SST2]  ...           │
└───────────────────────────────────────────────────┘
```

---

## 5. Compaction Strategies

### 5.1 Size-Tiered Compaction (STCS)

Used by: Cassandra (default), HBase, ScyllaDB

**Concept:** Group SSTables of similar size together and merge them when enough accumulate.

```
Size-Tiered Compaction:

  Time ──────────────────────────────────────────────────────►

  Flush:   [4MB] [4MB] [4MB] [4MB]        ← 4 similar-size SSTables
                    │
                    ▼ (compact when count reaches threshold, e.g., 4)
  Tier 1:        [16MB]  [16MB]  [16MB]  [16MB]
                           │
                           ▼
  Tier 2:               [64MB]    [64MB]    [64MB]    [64MB]
                                    │
                                    ▼
  Tier 3:                        [256MB]      [256MB]
                                               │
                                               ▼
  Tier 4:                                   [512MB]


  Compaction trigger: When N SSTables exist in the same size bucket
  (default N = 4 in Cassandra)
```

**Properties:**
- Low write amplification (each datum written ~O(log N) times)
- SSTables at same tier may have overlapping key ranges
- Read must check multiple SSTables at each tier
- **Space amplification:** During compaction, need 2x space temporarily (old + new)
- During steady state, obsolete data persists until its tier compacts

### 5.2 Leveled Compaction (LCS)

Used by: LevelDB, RocksDB (default), Cassandra (option)

**Concept:** Maintain levels where Level N+1 is 10x the size of Level N. Within each level (except L0), SSTables are non-overlapping and have fixed max size (e.g., 64MB).

```
Leveled Compaction:

  Level 0 (L0):  Overlapping SSTables from flush (max 4 files)
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
  │ [a-z]  │ │ [c-w]  │ │ [b-x]  │ │ [d-m]  │
  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
      └───────────┴──────────┴──────────┘
                      │
                      ▼  L0 → L1 Compaction
  Level 1 (L1):  Non-overlapping, total ~10MB (target)
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
  │[a-c] │ │[d-f] │ │[g-k] │ │[l-p] │ │[q-z] │   each ~2MB
  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
                      │
                      ▼  Pick one L1 SSTable, merge with overlapping L2 SSTables
  Level 2 (L2):  Non-overlapping, total ~100MB (target)
  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐
  │a-b ││c-d ││e-f ││g-h ││i-j ││k-l ││m-n ││o-r ││s-v ││w-z │ each ~10MB
  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘
                      │
                      ▼
  Level 3 (L3):  Non-overlapping, total ~1GB (target)
  [100 SSTables, each ~10MB, covering full key range]

                      │
                      ▼
  Level 4 (L4):  Non-overlapping, total ~10GB
  Level 5 (L5):  Non-overlapping, total ~100GB
  Level 6 (L6):  Non-overlapping, total ~1TB  (last level)
```

**Leveled Compaction Process:**
```
Picking what to compact (L1 → L2 example):

  L1: [a-c] [d-f] [g-k] [l-p] [q-z]
                    ▲
                    │ (picked: score = actual_size / target_size)
                    │
  L2: [a-b] [c-d] [e-f] [g-h] [i-j] [k-l] [m-n] ...
                    ▲     ▲     ▲     ▲
                    │     │     │     │
              overlapping SSTables in L2

  Merge [g-k] from L1 with [e-f][g-h][i-j][k-l] from L2
  → Produce new non-overlapping SSTables in L2
  → Delete old files atomically (via MANIFEST)
```

### 5.3 FIFO Compaction

Used for: Time-series data, logs, caches where old data can simply be dropped.

```
FIFO Compaction:

  Time ──────────────────────────────────────────►

  [SST-old] [SST-2] [SST-3] [SST-4] [SST-new]
      │
      ▼
  DELETE (exceeded TTL or total size limit)

  No merge operation. Just delete oldest SSTables.
  Zero write amplification from compaction.
```

### 5.4 Universal Compaction (RocksDB)

A generalization of size-tiered compaction with more flexibility:
- Can merge any subset of consecutive (by time) SSTables
- Reduces space amplification vs pure STCS by allowing partial merges
- Configurable triggers: size ratio, max files, space amplification percent

### 5.5 Comparison Table

| Strategy | Write Amp | Read Amp | Space Amp | Best For |
|----------|-----------|----------|-----------|----------|
| **Size-Tiered (STCS)** | Low (~3-5x) | High (many SSTables per tier) | High (up to 2x during compaction, stale data) | Write-heavy, ingest-heavy |
| **Leveled (LCS)** | High (~10-30x) | Low (1 SSTable per level) | Low (~1.1x) | Read-heavy, space-constrained |
| **FIFO** | None (0x) | Medium | Low (bounded by config) | TTL data, logs, time-series |
| **Universal** | Medium (~5-10x) | Medium | Medium (~1.5x) | Balanced workloads |

---

## 6. Write Amplification Analysis

**Write Amplification (WA):** The ratio of total bytes written to disk vs. bytes written by the application.

### Leveled Compaction WA:

```
Worst case analysis (Leveled, size ratio = 10):

  A key-value pair at Level L will be compacted into Level L+1.
  When merging one L(N) SSTable into L(N+1):
    - Read: 1 SSTable from L(N) + ~10 overlapping SSTables from L(N+1)
    - Write: ~10 new SSTables at L(N+1)
    
  Per level: WA ≈ 10 (size ratio)
  Total levels: log10(total_data / L1_size) ≈ 5-7 levels
  
  Total WA = 10 × (num_levels - 1) ≈ 10 × 6 = 60x (theoretical worst case)
  
  Practical WA: ~10-30x (not all data reaches bottom level)
```

### Size-Tiered Compaction WA:

```
  Each compaction merges ~4 SSTables into 1 (size ratio = 4):
  
  Total tiers: log4(total_data / flush_size)
  WA per tier: ~1 (write input once, output once)
  Total WA ≈ number_of_tiers ≈ 4-6x
```

### Why Write Amplification Matters:

```
SSD Lifespan Impact:

  SSD rated for: 1 DWPD (Drive Write Per Day) × 3 years
  Example: 1TB SSD → can write 1TB/day for 3 years

  Application write rate: 100 MB/s
  Daily writes: 100 MB/s × 86400s = 8.6 TB/day (logical)
  
  With WA = 30x (leveled): 8.6 × 30 = 258 TB/day physical writes
  SSD lifespan: 1095 TB ÷ 258 TB/day = 4.2 days ← SSD DEATH

  With WA = 5x (size-tiered): 8.6 × 5 = 43 TB/day
  SSD lifespan: 1095 TB ÷ 43 TB/day = 25 days ← still problematic

  → Must balance WA with SSD endurance. Use NVMe with high TBW ratings.
```

---

## 7. Optimizations

### 7.1 Bloom Filters

- Typically 10 bits per key → ~1% false positive rate
- Stored per SSTable (or per data block for large SSTables)
- Eliminates >99% of unnecessary disk reads for non-existent keys
- RocksDB: configurable bits_per_key, prefix bloom filters for range scans

### 7.2 Block Indexes and Partitioned Indexes

```
Standard Index (in memory):
  [last_key_block_0 → offset] [last_key_block_1 → offset] ...
  Problem: For a 256GB database, index alone can be several GB

Partitioned Index (RocksDB):
  Top-level index (small, always in memory)
       │
       ▼
  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
  │ Index Part 1│ │ Index Part 2│ │ Index Part 3│  ← cached on demand
  └─────────────┘ └─────────────┘ └─────────────┘
  
  Reduces memory usage, index partitions cached in block cache
```

### 7.3 Compression

| Algorithm | Ratio | Speed (Compress) | Speed (Decompress) | Use Case |
|-----------|-------|-------------------|---------------------|----------|
| Snappy | ~1.5-2x | ~500 MB/s | ~500 MB/s | Default, low latency |
| LZ4 | ~2-2.5x | ~400 MB/s | ~800 MB/s | Good balance |
| Zstd | ~2.5-3.5x | ~200 MB/s | ~500 MB/s | Bottom levels |

**Per-level compression strategy (RocksDB recommendation):**
- L0-L2: No compression or LZ4 (fast access, small data)
- L3+: Zstd (large data, worth the compression ratio)

### 7.4 Rate Limiting Compaction

- Prevent compaction from saturating disk bandwidth
- RocksDB: `rate_limiter` controls bytes/sec for compaction I/O
- Allows foreground reads/writes to maintain latency SLAs

### 7.5 Direct I/O

- **Compaction:** Use Direct I/O (bypass OS page cache) — avoids polluting cache with data read once during merge
- **User reads:** Use buffered I/O — benefit from OS page cache + block cache

### 7.6 Other Optimizations

- **Prefix seek:** Bloom filters on key prefixes for efficient range scans within a prefix
- **Column families:** Separate LSM trees sharing the same WAL (RocksDB)
- **Merge operator:** Deferred read-modify-write (e.g., counters, append operations)
- **Trivial move:** If a compaction input has no overlap with the next level, just move the file pointer (no I/O)
- **Subcompactions:** Parallelize a single compaction across multiple threads

---

## 8. Real-World Implementations

### 8.1 RocksDB (Facebook/Meta)

- Fork of LevelDB, heavily optimized for production
- Foundation for: MyRocks (MySQL), CockroachDB, TiKV (TiDB), Kafka Streams
- Features: column families, merge operators, universal compaction, transactions, backup/checkpoint
- Tuning: 100+ configuration options

### 8.2 LevelDB (Google)

- Original clean LSM implementation by Jeff Dean and Sanjay Ghemawat
- Single-threaded compaction, no column families
- Good for learning, used in Chrome (IndexedDB backend)

### 8.3 Apache Cassandra

- SSTable engine with pluggable compaction: STCS, LCS, TWCS (Time-Window), UCS (Unified)
- **TWCS:** Groups SSTables by time window, ideal for time-series (never compacts across windows)
- Distributed: each node runs its own LSM tree for its partition range

### 8.4 Apache HBase

- LSM-based on HDFS (SSTables = HFiles stored in HDFS)
- MemStore (MemTable) → flush to HFile
- Major compaction merges all HFiles for a region

### 8.5 ScyllaDB

- C++ rewrite of Cassandra with advanced compaction scheduling
- Incremental Compaction Strategy (ICS): avoids space amplification spikes
- Per-shard LSM trees (shared-nothing architecture)

### 8.6 InfluxDB (TSM - Time-Structured Merge Tree)

- LSM variant optimized for time-series: keys are measurement+tags+field+timestamp
- WAL → Cache (MemTable) → TSM files (columnar SSTable format)
- Compaction: time-range based, similar to TWCS

### 8.7 WiredTiger (MongoDB)

- Hybrid: supports both B-Tree and LSM modes
- MongoDB uses B-Tree mode by default (better for mixed workloads)
- LSM mode available for write-heavy use cases
- Hazard pointers for concurrent access

---

## 9. LSM vs B-Tree Comparison

| Dimension | LSM Tree | B-Tree |
|-----------|----------|--------|
| **Write throughput** | High (sequential I/O) | Lower (random I/O) |
| **Write latency** | Low (memory + WAL append) | Medium (page read-modify-write) |
| **Read latency (point)** | Higher (multiple levels) | Lower (single tree traversal) |
| **Range scan** | Merge across levels | Single sorted traversal |
| **Write amplification** | 10-30x (leveled) | 10-30x (page rewrites + splits) |
| **Read amplification** | Higher without bloom filters | 1x (one path through tree) |
| **Space amplification** | 1.1x (leveled) to 2x (tiered) | ~1x (page fill factor ~70%) |
| **Concurrency** | Simple (immutable SSTables) | Complex (latches, lock coupling) |
| **Compression** | Excellent (large sequential blocks) | Moderate (fragmented pages) |
| **Predictable latency** | Worse (compaction spikes) | Better (consistent) |

```
Workload Spectrum:

  Write-Heavy                                    Read-Heavy
  ◄──────────────────────────────────────────────────────────►
  │                                                          │
  │  LSM Tree                                    B-Tree      │
  │  =========                                   ======      │
  │  - Ingestion pipelines                       - OLTP      │
  │  - Time-series                               - Point     │
  │  - Event logging                               queries   │
  │  - Message queues                            - Indexes   │
  │  - Write-ahead state                         - Catalogs  │
  │                                                          │
```

---

## 10. Operational Concerns

### 10.1 Compaction Debt

When write rate exceeds compaction throughput, uncompacted SSTables accumulate:

```
Compaction Debt:

  Healthy:     L0: [2 files]    ← under threshold
  Warning:     L0: [8 files]    ← approaching limit
  Critical:    L0: [20 files]   ← WRITE STALL triggered

  Monitoring: pending_compaction_bytes, num_files_at_level0
```

**Mitigation:**
- Increase compaction parallelism (`max_background_compactions`)
- Increase L0 file limit (trades read perf for write throughput)
- Use faster storage for compaction output
- Rate-limit incoming writes proactively

### 10.2 Write Stalls

RocksDB triggers write stalls (slows or stops writes) when:
- L0 file count exceeds `level0_slowdown_writes_trigger` (default 20)
- L0 file count exceeds `level0_stop_writes_trigger` (default 36)
- Pending compaction bytes exceed threshold

### 10.3 Space Amplification Monitoring

```
Space amplification = total_size_on_disk / logical_data_size

  Leveled:     ~1.1x (tight)
  Size-Tiered: ~2-3x (during compaction, stale duplicates)

  Monitor: actual disk usage vs. estimated live data size
  Alert if: space_amp > 2.0 (indicates compaction falling behind)
```

### 10.4 Tuning for SSD vs HDD

| Parameter | SSD | HDD |
|-----------|-----|-----|
| Compaction threads | 4-8 | 1-2 (limited by seeks) |
| Compaction style | Leveled (WA ok, IOPS available) | Size-tiered (minimize WA) |
| Block size | 4-16KB | 64-128KB (amortize seek) |
| Bloom filter | 10 bits/key | 10 bits/key (even more critical) |
| Direct I/O | Yes for compaction | Less beneficial |
| Compression | Zstd (save space, CPU cheap) | Zstd (reduce I/O) |

---

## 11. Architect's Guide

### When to Choose LSM Tree:

1. **Write throughput > 10K ops/sec** sustained
2. **Write-heavy ratio** (>70% writes)
3. **Append-mostly workloads** (time-series, events, logs)
4. **SSD storage** (sequential writes extend SSD life)
5. **Compression matters** (LSM achieves 2-3x better compression than B-Tree)
6. **Range deletes** (tombstones + compaction efficiently reclaims space)

### When to Choose B-Tree:

1. **Read-heavy workloads** (>70% reads)
2. **Latency-sensitive reads** (predictable single-digit ms)
3. **Strong transaction isolation** (page-level locking, MVCC on pages)
4. **Small datasets** fitting in memory (both perform similarly)
5. **Predictable latency requirements** (no compaction jitter)

### Tuning Decision Matrix:

```
                    Space          Write          Read
                  Constrained?    Heavy?         Heavy?
                       │             │              │
            ┌──────────┼─────────────┼──────────────┼──────────┐
            │          ▼             ▼              ▼          │
            │    ┌──────────┐  ┌──────────┐  ┌──────────┐     │
            │    │ Leveled  │  │  Size-   │  │ Leveled  │     │
            │    │Compaction│  │  Tiered  │  │Compaction│     │
            │    └──────────┘  └──────────┘  └──────────┘     │
            │                                                   │
            │    Time-series with TTL?  → FIFO / TWCS          │
            │    Balanced workload?     → Universal             │
            └───────────────────────────────────────────────────┘
```

### Production Checklist:

- [ ] Set MemTable size based on flush frequency target (aim for flush every 1-5 minutes)
- [ ] Configure bloom filters (10 bits/key standard, more for high read workloads)
- [ ] Set block cache to ~50-70% of available memory
- [ ] Configure compaction parallelism to match available I/O bandwidth
- [ ] Monitor: L0 file count, pending compaction bytes, write stall duration
- [ ] Set up alerts: compaction debt > 10GB, L0 files > 10, space amp > 2x
- [ ] Enable compression: none/LZ4 for L0-L2, Zstd for L3+
- [ ] Configure WAL: sync mode vs. batch sync based on durability requirements
- [ ] Test recovery time: crash and measure WAL replay duration
- [ ] Benchmark with realistic workload before production deployment

---

## Summary

LSM Trees trade read amplification for write throughput by converting random writes into sequential I/O through a multi-level structure of sorted, immutable files. The key insight is that sequential I/O (both on HDD and SSD) is orders of magnitude faster than random I/O, and that maintaining sorted order across levels through background compaction amortizes the cost of organizing data.

The choice between LSM and B-Tree, and between compaction strategies, fundamentally comes down to the write/read ratio of your workload and your tolerance for space amplification vs. write amplification vs. read amplification—the "RUM conjecture" (Read, Update, Memory—optimize two at the cost of the third).
